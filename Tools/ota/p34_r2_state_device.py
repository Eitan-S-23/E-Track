"""One bounded passive R2-A/UI observation from the closed checkpoint, not OTA."""
import argparse
import ctypes
import hashlib
import json
import os
from pathlib import Path
import re
import sys
import time

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'Tools/ota'))
import p34_probe_acquire as base
import p34_online_log_probe as setup
import p34_r2_state_ui_tests as component
from recovery_confirm.r2_state_ui import Probe, READS
from recovery_confirm.ap_journal import JournalSDK
from recovery_confirm.mutation_audit import SealedGate
from recovery_confirm.online_log import OnlineLog

cli, host = base.cli, base.host
SELF = Path(__file__).resolve()
LOGS = tuple('sdk-%03d.log' % i for i in range(3))
FILES = (*LOGS, 'plan.json', 'parent.json', 'worker.json', 'worker.log',
         'events.jsonl', 'callbacks.log', 'project.jlink')
CHECKPOINT = ROOT / '.cache/p34-r2-checkpoint1'
REVIEW = ROOT / '.cache/p34-r2-checkpoint1-independent-review1/result.json'
REVIEW_SHA = '4c62015646915103c526288a7368b216ff2674485b9b10ac3708c1515fe2a772'
COMPONENT_TESTS = ROOT / '.cache/p34-r2-state-ui-tests1/result.json'
ASSETS = dict(image=ROOT / '.cache/p34-recovery-sources1/r2-a.bin',
              map_bytes=ROOT / '.cache/p34-early-usb-r2/on/b/app-gcc/X-Track-App-GCC.map')
SCOPE = 'R2-A30276 passive RAM/MMIO/UI only; no halt/reset/NOR/EEPROM/phone/target payload stores'
WORKER_SECONDS, PARENT_SECONDS = 180, 240


def execute(dap, observation, persist, initial, paths, record, remaining, image, map_bytes,
            *, clock=time.monotonic, sleep=time.sleep, guard=base.guarded):
    result = dict(result='FAILED', close_returned=False, target_payload_writes=0,
                  reset_performed=False, physical_bcb_observed=False,
                  backup_observed=False, ota_ready=False)
    logs = probe = None
    normal = False
    try:
        observation.connect()
        cli.require(dap.original_csw == dap.word_csw == 0x23000052,
                    'qualified native word profile required')
        acquisition, restore = setup.dp_plan(dap.metadata)
        logs = OnlineLog(dap, SealedGate(paths, dap.metadata, record), persist,
                         remaining, initial_rows=initial, clock=clock)
        logs.switch(read_allowed=lambda _: False, expected_stores=[], expected_dp_writes=acquisition)
        probe = Probe(dap, logs, image, map_bytes,
                      lambda: observation.connected and not observation.closed,
                      remaining, clock=clock, sleep=sleep, guard=guard)
        result['state'] = probe.run()
        logs.prepare_close()
        normal = True
    except BaseException as error:
        result['error'] = type(error).__name__ + ': ' + str(error)
    finally:
        try:
            observation.close()
        except BaseException as error:
            normal = False
            result['close_error'] = type(error).__name__ + ': ' + str(error)
        result.update(close_returned=dap.close_returned, dap=dict(dap.metadata), native_ap_error=dap.sdk.error)
        if probe: result['probe_error'] = probe.error
        if normal:
            try:
                final = guard(lambda: logs.finish(read_allowed=lambda _: False,
                    expected_stores=[], expected_dp_writes=restore), seconds=min(60, remaining()))
                unchanged_dp = not dap.power_changed and dap.original_dp & 0xf0000000 == 0xf0000000
                cli.require(dap.close_returned and dap.metadata['tar_restored'] and
                    dap.metadata['csw_restored'] and (dap.metadata['dp_restored'] or unchanged_dp),
                    'state AP/native restoration incomplete')
                cli.require(logs.gate.cursor.target_writes == 0 and final['native_close_completed'] == 1,
                            'state is not a closed read-only observation')
                result.update(result='R2_STATE_NATIVE_CLOSED', final_trace=final,
                    logs=list(logs.gate.records), native_close_audited=True,
                    original_dp_preserved_without_write=unchanged_dp)
            except BaseException as error:
                result['final_audit_error'] = type(error).__name__ + ': ' + str(error)
        if logs: result.update(log_mode=logs.mode, log_error=logs.error, sealed=list(logs.gate.records))
    return result


def audit_trace(paths, rows, metadata, record, native_closed):
    groups, current = [], []
    for row in rows:
        if row['event'] == 'online-log-switch-returned':
            cli.require((row['old'], row['new']) == (len(groups), len(groups)+1), 'state log order differs')
            groups.append(current)
            current = []
        current.append(row)
    groups.append(current)
    cli.require(len(paths) == len(groups) == 3, 'complete three-log state layout required')
    acquisition, restore = setup.dp_plan(metadata)
    gate = SealedGate(paths, metadata, record)
    for index, group in enumerate(groups):
        gate.begin(index)
        trace = gate.seal(index, group, read_allowed=lambda a: index == 1 and a in READS,
            expected_stores=[], expected_dp_writes=acquisition if index == 0 else restore if index == 2 else [],
            final=index == 2, native_closed=native_closed if index == 2 else False)
        heads = [r for r in group if r['event'] == 'online-log-head-verified']
        if index:
            cli.require(heads, 'state active head absent')
            for head in heads:
                prefix = head['record']
                cli.require(prefix['path'] == str(paths[index]) and type(prefix['bytes']) is int and
                            0 < prefix['bytes'] <= 65536, 'state head extent differs')
                with paths[index].open('rb') as stream: raw = stream.read(prefix['bytes'])
                cli.require(len(raw) == prefix['bytes'] and hashlib.sha256(raw).hexdigest() == prefix['sha256'],
                            'state original head changed')
                cli.require(head['trace']['native_calls'] == 3 and
                    head['trace']['sequence'] == previous['sequence']+3 and
                    [tuple(x) for x in head['trace']['first']] == list(previous['tail']), 'state head journal differs')
        previous = trace
    cli.require(gate.cursor.target_writes == 0 and trace['native_close_completed'] == 1, 'state close/stores differ')
    return dict(logs=gate.records, target_reads=gate.cursor.target_reads, target_writes=gate.cursor.target_writes,
                native_calls=gate.cursor.native_calls, native_close=trace['native_close_completed'])


def predecessor(store):
    cli.require(cli.record(REVIEW)['sha256'] == REVIEW_SHA, 'fixed independently closed checkpoint required')
    review = store.read(REVIEW)
    cli.require(review['result'] == 'R2A_FULL_IMAGE_BOOT_HEALTH_CLOSED_INDEPENDENT_REVIEW_PASS' and
        review['runtime_health_independently_reconciled'] is True and
        review['native_close_independently_reconciled'] is True and
        review['all_native_archive_words_matched'] is True and review['image_version'] == 30276 and
        review['backup_observed'] is False and review['ota_ready'] is False and
        review['transport']['target_writes'] == 0 and review['transport']['native_close'] == 1,
        'checkpoint scope differs')
    for item in (*review['original_inputs'], *review['source_inputs'], review['script']):
        cli.require(cli.record(store.checked(item['path'])) == item, 'closed checkpoint evidence changed')
    parent, worker, plan = (store.read(CHECKPOINT / (n+'.json')) for n in ('parent', 'worker', 'plan'))
    cli.require(parent == review['parent'] and parent['exit'] == 0 and parent['timeout'] is False and
        not parent['presence_after']['debugger_processes'] and parent['after_history'] == plan['before_history'] and
        worker['result'] == 'R2_CHECKPOINT_NATIVE_CLOSED' and worker['sources_unchanged_after_close'] is True and
        worker['archives'] == review['archives'] and worker['logs'] == review['transport']['logs'],
        'checkpoint owner/evidence unresolved')
    return dict(kind='CLOSED_READ_ONLY_R2A_CHECKPOINT', review=cli.record(REVIEW),
                parent=cli.record(CHECKPOINT/'parent.json'), worker=cli.record(CHECKPOINT/'worker.json'),
                version=30276, historical_ota_predecessor=False, backup_observed=False)


def sources(store):
    paths = component.sources(store)
    tested = store.read(COMPONENT_TESTS)
    cli.require(tested['result'] == 'R2_PASSIVE_UI_HOST_PASS' and
                tested['inputs'] == [cli.record(p) for p in paths], 'current passive/UI component tests required')
    return list(dict.fromkeys([*paths, *base.SOURCES, *setup.sources(store), SELF, COMPONENT_TESTS,
        ROOT/'tests/boot/test_p34_r2_state_device.py', ROOT/'tests/boot/test_p34_r2_checkpoint_device.py',
        ROOT/'Tools/ota/p34_r2_checkpoint_device.py', REVIEW, *ASSETS.values()]))


def preflight(store, out, paths):
    component.prior.prior.prior.prior.preflight(store, out, paths)
    for name in FILES: store.checked(out/name)


def validate_worker_plan(store, plan, out, current):
    cli.require(plan['out'] == str(out) and plan['scope'] == SCOPE and plan['inputs'] == current,
                'state source/scope changed')
    test_path = store.checked(plan['tests']['path'])
    cli.require(cli.record(test_path) == plan['tests'], 'state selftest receipt changed')
    tests = store.read(test_path)
    cli.require(tests['result'] == 'R2_STATE_DEVICE_HOST_PASS' and tests['hardware'] is False and
                tests['inputs'] == current, 'current state selftests required')
    cli.require(plan['predecessor'] == predecessor(store), 'state predecessor changed')
    cli.require(plan['worker_seconds'] == WORKER_SECONDS and plan['parent_seconds'] == PARENT_SECONDS and
        plan['connection_generation'] == 'r2-state-'+out.name and
        plan['before_history'] == base.history(store) and plan['native_history_approved'] == str(base.HISTORY),
        'state lifetime/generation/history changed')


def worker(store, out):
    cli.require(base.in_job(), 'owned state worker required')
    plan = store.read(out/'plan.json')
    validate_worker_plan(store, plan, out, [cli.record(p) for p in sources(store)])
    cli.require(cli.record(base.JLINK/'JLink_x64.dll')['sha256'] == base.DLL_SHA, 'native DLL changed')
    for name in (*LOGS, 'events.jsonl', 'callbacks.log', 'project.jlink', 'worker.json'):
        cli.require(not store.checked(out/name).exists(), 'preserve state; worker cannot replay')
    assets = {k: p.read_bytes() for k, p in ASSETS.items()}
    deadline = time.monotonic()+WORKER_SECONDS
    result = dict(result='FAILED', close_returned=False)
    dap = observation = None
    with (out/'events.jsonl').open('x', encoding='utf-8') as stream, (out/'callbacks.log').open('xb') as callbacks:
        initial = []
        def persist(event, **fields):
            stream.write(json.dumps(dict(time=cli.now(), event=event, **fields))+'\n')
            stream.flush()
            if event == 'online-log-sealed':
                os.fsync(stream.fileno())
                print('SEALED', fields['index'], flush=True)
        def collect(event, **fields):
            persist(event, **fields)
            initial.append(dict(event=event, **fields))
        try:
            cli.require(not base.native_presence()['debugger_processes'], 'competing debugger present')
            with os.add_dll_directory(str(base.JLINK)):
                sdk = base.guarded(ctypes.CDLL, str(base.JLINK/'JLink_x64.dll'))
                dap = base.Dap(sdk, out/LOGS[0], out/'project.jlink', callbacks)
                dap.sdk = JournalSDK(sdk, collect)
                observation = base.Observation(dap, collect, seconds=120)
                result = execute(dap, observation, persist, initial, [out/n for n in LOGS], cli.record,
                                 lambda: deadline-time.monotonic(), **assets)
        except BaseException as error:
            result.update(result='FAILED', outer_error=type(error).__name__+': '+str(error))
            try:
                if observation is not None: observation.close()
                elif dap is not None and dap._opened: dap.close()
            except BaseException as close: result['outer_close_error'] = str(close)
        try:
            result['sources_unchanged_after_close'] = plan['inputs'] == [cli.record(p) for p in sources(store)]
        except BaseException as error:
            result.update(sources_unchanged_after_close=False, source_check_error=str(error))
        if not result['sources_unchanged_after_close']: result['result'] = 'FAILED'
        store.write(out/'worker.json', result)
    print(result['result'], flush=True)
    return 0 if result['result'] == 'R2_STATE_NATIVE_CLOSED' else 1


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action', choices=('selftest', 'capture', 'worker', 'check'))
    parser.add_argument('--output-dir', type=Path, required=True)
    parser.add_argument('--tests', type=Path)
    parser.add_argument('--native-history-approved', type=Path)
    args = parser.parse_args()
    cli.require(Path.cwd() == ROOT and sys.flags.isolated and sys.flags.no_site and sys.dont_write_bytecode,
                'isolated explicit root required')
    store = cli.Store(ROOT)
    out = store.checked(args.output_dir)
    if args.action == 'worker': return worker(store, out)
    paths = sources(store)
    preflight(store, out, paths)
    records = [cli.record(p) for p in paths]
    if args.action == 'check':
        print('STATE_OUTPUT_PREFLIGHT_PASS', len(records)); return 0
    if args.action == 'capture':
        cli.require(args.native_history_approved == base.HISTORY, 'exact native history permission required')
        test_path = store.checked(args.tests)
        tested = store.read(test_path)
        cli.require(tested['result'] == 'R2_STATE_DEVICE_HOST_PASS' and tested['hardware'] is False and
                    tested['inputs'] == records, 'current state selftests required')
        proof, before = predecessor(store), base.history(store)
        cli.require(not base.native_presence()['debugger_processes'], 'competing debugger present')
    env = host.environment(store, out)
    for path in paths: store.raw(out/'source'/path.relative_to(ROOT), path.read_bytes())
    if args.action == 'selftest':
        log = host.command(store, out, 'tests', [sys.executable, '-I', '-S', '-B', '-X', 'utf8',
            ROOT/'tests/boot/test_p34_r2_state_device.py', '-v'], env, 120)
        count = re.search(rb'Ran (\d+) tests? in .*\r?\n\r?\nOK\b', log)
        cli.require(count and records == [cli.record(p) for p in paths], 'state test/source drift')
        store.write(out/'result.json', dict(result='R2_STATE_DEVICE_HOST_PASS', tests=int(count[1]),
                                            inputs=records, hardware=False))
        print('R2_STATE_DEVICE_HOST_PASS', int(count[1])); return 0
    store.write(out/'plan.json', dict(out=str(out), scope=SCOPE, inputs=records, tests=cli.record(test_path),
        predecessor=proof, before_history=before, native_history_approved=str(base.HISTORY),
        worker_seconds=WORKER_SECONDS, parent_seconds=PARENT_SECONDS, connection_generation='r2-state-'+out.name))
    result = base.owned_run(store, out, [SELF, 'worker', '--output-dir', out], env, timeout=PARENT_SECONDS)
    result.update(after_history=base.history(store), presence_after=base.native_presence())
    store.write(out/'parent.json', result)
    print(json.dumps(result))
    return 0 if result['exit'] == 0 and not result['timeout'] else 1


if __name__ == '__main__': raise SystemExit(main())
