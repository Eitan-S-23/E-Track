"""Exact first16KiB Boot replacement; no reset, App/EEPROM/NOR payload route."""
import argparse
import ctypes
import json
import os
from pathlib import Path
import sys
import time

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'Tools/ota'))
import p34_boot16_program_tests as tests
from recovery_confirm import boot16, boot16_owner as owner, boot16_program as body
from recovery_confirm.boot16_archive import Archive
from recovery_confirm import boot16_reconcile as audit

prior = tests.prior.core
cli, host, base = prior.cli, prior.host, prior.base
SELF = Path(__file__).resolve()
ORIGINAL = ROOT / '.cache/p34-native-acquire1/boot-readback.bin'
CANDIDATE = ROOT / '.cache/p34-bc-target/b16/boot/X-Track-Boot.bin'
PROBE = ROOT / '.cache/p34-boot16-entry-probe3/worker.json'
LOGS = tuple('sdk-%03d.log' % index for index in range(body.LOG_COUNT))
WORKER_SECONDS, PARENT_SECONDS = 6000, 6120
FILES = (*LOGS, 'plan.json', 'parent.json', 'worker.json', 'worker.log', 'events.jsonl',
         'callbacks.log', 'project.jlink', 'prewrite.json', 'before-boot.bin', 'before-app.bin',
         'after-boot.bin', 'after-app.bin')


def sources(store):
    result = cli.record(PROBE)
    cli.require(result['sha256'] == 'ba0e20ed7c9eca7003528dd05ee4f57cda57aaf2779b9ef2a2bc648d338a2ec0',
                'qualified entry original changed')
    return sorted(set([*tests.sources(store), SELF, ORIGINAL, CANDIDATE, PROBE]))


def preflight(store, out, inputs):
    cli.require(not out.exists(), 'preserve consumed Boot16 action')
    for name in FILES: store.checked(out / name)
    for path in inputs: store.checked(out / 'source' / path.relative_to(ROOT))
    for key in ('HOME', 'USERPROFILE', 'APPDATA', 'LOCALAPPDATA', 'TEMP', 'TMP', 'TMPDIR',
                'XDG_CACHE_HOME', 'XDG_CONFIG_HOME', 'XDG_DATA_HOME', 'PYTHONUSERBASE',
                'PYTHONPYCACHEPREFIX', 'CCACHE_DIR', 'SCCACHE_DIR'):
        store.checked(out / 'host' / key.lower())


def retained(store, failure):
    """Recompute from originals now; no caller-authored PASS capability accepted."""
    failure = store.checked(failure)
    worker, parent, plan, checkpoint = (store.read(failure / (n+'.json'))
                                       for n in ('worker', 'parent', 'plan', 'prewrite'))
    cli.require(worker['result'] == 'FAILED' and worker['close_returned'] is True and
        worker.get('sources_unchanged_after_close') is True and worker.get('native_ap_error') is None and
        worker.get('boot_may_have_changed') is True and worker.get('release_started') is False and
        worker.get('release_attempted') is False and worker.get('phase') in ('PROGRAM', 'POST_CAPTURE') and
        parent['exit'] == 1 and not parent['timeout'] and plan['direction'] == 'activate',
        'only closed certain pre-release activation failure is restorable')
    cli.require(plan['inputs'] == [cli.record(item['path']) for item in plan['inputs']], 'predecessor source drift')
    for item in plan['inputs']:
        raw = cli.record(failure / 'source' / Path(item['path']).relative_to(ROOT))
        cli.require((raw['bytes'], raw['sha256']) == (item['bytes'], item['sha256']), 'predecessor source copy drift')
    input_paths = [failure / n for n in ('worker.json', 'parent.json', 'plan.json', 'prewrite.json',
                                       'events.jsonl', 'before-boot.bin', 'before-app.bin')]
    logs = sorted(failure.glob('sdk-*.log'))
    originals = [cli.record(path) for path in [*input_paths, *logs]]
    rows = [json.loads(line) for line in (failure / 'events.jsonl').read_text(encoding='utf-8').splitlines()]
    result = audit.reconcile(logs, rows, worker['dap'], cli.record,
        boot16.Plan(ORIGINAL.read_bytes(), CANDIDATE.read_bytes()), prior.IMAGE.read_bytes(),
        (failure / 'before-boot.bin').read_bytes(), failed=True)
    cli.require(result['before'] == checkpoint['before'] == worker['before'] and
        result['context'] == checkpoint['context'] == worker['context'] and result['phase'] == worker['phase'] and
        checkpoint['binding'] == cli.record(failure / 'plan.json') and checkpoint['direction'] == 'activate',
        'retained context/prewrite binding differs from original native evidence')
    for name in ('before-boot', 'before-app'):
        cli.require(result['archives'][name] == (failure / (name+'.bin')).read_bytes() and
                    checkpoint['archives'][name] == cli.record(failure / (name+'.bin')), 'physical preimage archive mismatch')
    cli.require(originals == [cli.record(item['path']) for item in originals], 'failure originals changed during audit')
    return {key: result[key] for key in ('before', 'context', 'phase', 'release_attempted', 'boot_may_have_changed')}, originals


def worker(store, out):
    deadline = time.monotonic()+WORKER_SECONDS
    cli.require(base.in_job(), 'owned Boot16 job required')
    plan = store.read(out / 'plan.json')
    cli.require(plan['out'] == str(out) and plan['inputs'] == [cli.record(path) for path in sources(store)], 'Boot16 source drift')
    cli.require(plan['native_history_approved'] == str(base.HISTORY) and
                cli.record(base.JLINK / 'JLink_x64.dll')['sha256'] == base.DLL_SHA, 'native identity/authority changed')
    saved = None
    if plan['direction'] == 'restore':
        saved, records = retained(store, Path(plan['failure']))
        cli.require(saved == plan['retained'] and records == plan['failure_inputs'], 'restore binding changed')
    archive = Archive(store, out, cli.record(out / 'plan.json'))
    result = dict(result='FAILED', close_returned=False)
    dap = observation = None
    with (out / 'events.jsonl').open('x', encoding='utf-8') as events, (out / 'callbacks.log').open('xb') as callbacks:
        initial = []
        def persist(event, **fields):
            events.write(json.dumps(dict(time=cli.now(), event=event, **fields))+'\n')
            events.flush()
            if event in ('online-log-sealed', 'boot16-program-phase', 'boot16-prewrite-checkpoint-returned', 'boot16-media'):
                os.fsync(events.fileno())
                print(json.dumps(dict(event=event, index=fields.get('index'), phase=fields.get('phase'),
                                      remaining=deadline-time.monotonic())), flush=True)
        def collect(event, **fields):
            persist(event, **fields)
            initial.append(dict(event=event, **fields))
        try:
            cli.require(not base.native_presence()['debugger_processes'], 'competing debugger')
            with os.add_dll_directory(str(base.JLINK)):
                sdk = base.guarded(ctypes.CDLL, str(base.JLINK / 'JLink_x64.dll'))
                dap = base.Dap(sdk, out / LOGS[0], out / 'project.jlink', callbacks)
                dap.sdk = prior.JournalSDK(sdk, collect)
                observation = base.Observation(dap, collect, seconds=540)
                result = owner.execute(dap, observation, persist, initial, [out / name for name in LOGS], cli.record,
                    lambda: deadline-time.monotonic(), prior.IMAGE.read_bytes(), prior.MAP.read_bytes(),
                    boot16.Plan(ORIGINAL.read_bytes(), CANDIDATE.read_bytes()), archive,
                    direction=plan['direction'], retained=saved)
        except BaseException as error:
            result['outer_error'] = type(error).__name__+': '+str(error)
            if observation is None and dap is not None and dap._opened:
                try: dap.close()
                except BaseException as close: result['outer_close_error'] = str(close)
        result['sources_unchanged_after_close'] = plan['inputs'] == [cli.record(path) for path in sources(store)]
        if not result['sources_unchanged_after_close']: result['result'] = 'FAILED'
        store.write(out / 'worker.json', result)
    print(json.dumps(dict(result=result['result'], close_returned=result['close_returned'])), flush=True)
    return 0 if result['result'] == 'BOOT16_PROGRAMMED_VERIFIED_CLOSED' else 1


def main():
    cli.require(Path.cwd() == ROOT and sys.flags.isolated and sys.flags.no_site and sys.dont_write_bytecode,
                'isolated explicit project root required')
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action', choices=('activate', 'restore', 'worker'))
    parser.add_argument('--output-dir', type=Path, required=True)
    parser.add_argument('--tests', type=Path)
    parser.add_argument('--failure', type=Path)
    parser.add_argument('--native-history-approved', type=Path)
    args = parser.parse_args()
    store = cli.Store(ROOT)
    out = store.checked(args.output_dir)
    if args.action == 'worker': return worker(store, out)
    inputs = sources(store)
    preflight(store, out, inputs)
    records = [cli.record(path) for path in inputs]
    tested = store.read(args.tests)
    cli.require(tested['result'] == 'BOOT16_PROGRAM_HOST_PASS' and tested['inputs'] == records, 'current bound coordinator tests required')
    cli.require(args.native_history_approved == base.HISTORY, 'exact native history authority required')
    saved, failure_inputs = None, []
    if args.action == 'restore':
        saved, failure_inputs = retained(store, args.failure)
        digest = cli.record(args.failure / 'worker.json')['sha256']
        cli.require(out == ROOT / ('.cache/p34-boot16-restore-'+digest), 'one deterministic consumed restore action required')
    else:
        cli.require(args.failure is None, 'activation cannot carry retained failure')
    before_history = base.history(store)
    env = host.environment(store, out)
    for path in inputs: store.raw(out / 'source' / path.relative_to(ROOT), path.read_bytes())
    store.write(out / 'plan.json', dict(out=str(out), direction=args.action, inputs=records,
        tests=cli.record(args.tests), native_history_approved=str(base.HISTORY), before_history=before_history,
        worker_seconds=WORKER_SECONDS, parent_seconds=PARENT_SECONDS, failure=str(args.failure) if args.failure else None,
        failure_inputs=failure_inputs, retained=saved, boot_range=[boot16.START, boot16.END],
        reset_commands=0, app_payload_writes=0, eeprom_payload_writes=0, nor_payload_writes=0,
        authority='User explicitly authorized Boot first16KiB group16 replacement and exact original-prefix restoration',
        power='Keep existing J-Link 3.3V/GND connected; no power commands'))
    value = base.owned_run(store, out, [SELF, 'worker', '--output-dir', out], env, timeout=PARENT_SECONDS)
    value.update(after_history=base.history(store), presence_after=base.native_presence())
    store.write(out / 'parent.json', value)
    print(json.dumps(value), flush=True)
    return 0 if value['exit'] == 0 and not value['timeout'] else 1


if __name__ == '__main__': raise SystemExit(main())
