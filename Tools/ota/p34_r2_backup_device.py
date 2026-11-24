"""Owned mapped-logical old-backup observation; no NOR write or OTA entry."""
import argparse
import ctypes
import hashlib
import json
import os
from pathlib import Path
import re
import sys
import time
from types import FunctionType

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT/'Tools/ota'))
import p34_r2_state_device as owner
import p34_r2_mapped_backup_tests as component
from recovery_confirm import r2_mapped_backup as mapped

cli, host, base = owner.cli, owner.host, owner.base
SELF = Path(__file__).resolve()
LOGS = tuple('sdk-%03d.log' % i for i in range(mapped.LOG_COUNT))
FILES = (*LOGS, 'plan.json', 'parent.json', 'worker.json', 'worker.log', 'events.jsonl',
         'callbacks.log', 'project.jlink', 'backup-header.bin', 'backup-payload.bin')
REVIEW = ROOT/'.cache/p34-r2-state1-independent-review1/result.json'
REVIEW_SHA = '57474293d8bf3e849ba3d684fd7784539fe23bddd5fd56f74492137acd526d7d'
COMPONENT_TESTS = ROOT/'.cache/p34-r2-mapped-backup-tests2/result.json'
STATE = ROOT/'.cache/p34-r2-state1'
SCOPE = 'R2-A old30274 backup mapped-logical read only; no halt/reset/EEPROM/NOR-write/phone/power action'
WORKER_SECONDS, PARENT_SECONDS = 900, 1020


def execute(dap, observation, persist, initial, paths, record, remaining, image, map_bytes,
            archive, emit_archive, **options):
    def probe(*args, **kwargs): return mapped.Capture(*args, archive, emit_archive, **kwargs)
    # Bind a private copy of the reviewed lifecycle, not its module globals.
    # The executed state observer and its frozen source remain unchanged.
    lifecycle = FunctionType(owner.execute.__code__, dict(owner.execute.__globals__, Probe=probe),
                             owner.execute.__name__, owner.execute.__defaults__, owner.execute.__closure__)
    lifecycle.__kwdefaults__ = dict(owner.execute.__kwdefaults__)
    result = lifecycle(dap, observation, persist, initial, paths, record, remaining, image, map_bytes, **options)
    if result['result'] == 'R2_STATE_NATIVE_CLOSED': result['result'] = 'R2_BACKUP_MAPPED_NATIVE_CLOSED'
    result.update(mapped_logical_only=True, uncached_chip_read=False, ota_ready=False)
    return result


def audit_trace(paths, rows, metadata, record, native_closed):
    groups, current = [], []
    for row in rows:
        if row['event'] == 'online-log-switch-returned':
            cli.require((row['old'], row['new']) == (len(groups), len(groups)+1), 'backup segment order differs')
            groups.append(current)
            current = []
        current.append(row)
    groups.append(current)
    cli.require(len(paths) == len(groups) == mapped.LOG_COUNT, 'complete backup log layout required')
    acquisition, restore = owner.setup.dp_plan(metadata)
    gate = owner.SealedGate(paths, metadata, record)
    for index, group in enumerate(groups):
        final = index == len(paths)-1
        gate.begin(index)
        trace = gate.seal(index, group, read_allowed=lambda a: 0 < index < len(paths)-1 and a in mapped.READS,
            expected_stores=[], expected_dp_writes=acquisition if index == 0 else restore if final else [],
            final=final, native_closed=native_closed if final else False)
        heads = [r for r in group if r['event'] == 'online-log-head-verified']
        if index:
            cli.require(heads, 'backup active head missing')
            for head in heads:
                prefix = head['record']
                cli.require(prefix['path'] == str(paths[index]) and type(prefix['bytes']) is int and
                            0 < prefix['bytes'] <= 65536, 'backup head extent differs')
                with paths[index].open('rb') as stream: raw = stream.read(prefix['bytes'])
                cli.require(len(raw) == prefix['bytes'] and hashlib.sha256(raw).hexdigest() == prefix['sha256'],
                            'backup original head changed')
                cli.require(head['trace']['native_calls'] == 3 and
                    head['trace']['sequence'] == previous['sequence']+3 and
                    [tuple(x) for x in head['trace']['first']] == list(previous['tail']), 'backup head journal differs')
        previous = trace
    cli.require(gate.cursor.target_writes == 0 and trace['native_close_completed'] == 1, 'backup stores/close differ')
    return dict(logs=gate.records, target_reads=gate.cursor.target_reads, target_writes=gate.cursor.target_writes,
                native_calls=gate.cursor.native_calls, native_close=trace['native_close_completed'])


def predecessor(store):
    checkpoint = owner.predecessor(store)
    cli.require(cli.record(REVIEW)['sha256'] == REVIEW_SHA, 'fixed closed state review required')
    review = store.read(REVIEW)
    for item in (*review['original_inputs'], *review['source_inputs'], review['script']):
        cli.require(cli.record(store.checked(item['path'])) == item, 'original state evidence changed')
    parent, plan, worker = (store.read(STATE/(n+'.json')) for n in ('parent', 'plan', 'worker'))
    cli.require(parent['exit'] == 0 and parent['timeout'] is False and not parent['presence_after']['debugger_processes'] and
        parent['after_history'] == plan['before_history'] and worker['result'] == 'R2_STATE_NATIVE_CLOSED' and
        worker['sources_unchanged_after_close'] is True and worker['native_close_audited'] is True and
        worker['state']['sampled_epoch_stable'] is True and worker['state']['unloaded_ui_idle_observed'] is True,
        'closed state predecessor unresolved')
    return dict(checkpoint=checkpoint, state_review=cli.record(REVIEW),
                parent=cli.record(STATE/'parent.json'), plan=cli.record(STATE/'plan.json'),
                worker=cli.record(STATE/'worker.json'), historical_ota_predecessor=False)


def sources(store):
    paths = component.sources(store)
    tested = store.read(COMPONENT_TESTS)
    cli.require(tested['result'] == 'R2_MAPPED_BACKUP_COMPONENT_HOST_PASS' and
                tested['inputs'] == [cli.record(p) for p in paths], 'current mapped component tests required')
    return list(dict.fromkeys([*paths, SELF, COMPONENT_TESTS, REVIEW,
        ROOT/'tests/boot/test_p34_r2_backup_device.py', *(STATE/(n+'.json') for n in ('plan', 'worker', 'parent'))]))


def preflight(store, out, paths):
    owner.preflight(store, out, paths)
    for name in FILES: store.checked(out/name)


def validate_worker_plan(store, plan, out, current):
    cli.require(plan['out'] == str(out) and plan['scope'] == SCOPE and plan['inputs'] == current,
                'backup source/scope changed')
    test_path = store.checked(plan['tests']['path'])
    cli.require(cli.record(test_path) == plan['tests'], 'backup tests changed')
    tests = store.read(test_path)
    cli.require(tests['result'] == 'R2_BACKUP_DEVICE_HOST_PASS' and tests['hardware'] is False and
                tests['inputs'] == current, 'current backup selftests required')
    cli.require(plan['predecessor'] == predecessor(store), 'backup predecessor changed')
    cli.require(plan['worker_seconds'] == WORKER_SECONDS and plan['parent_seconds'] == PARENT_SECONDS and
        plan['connection_generation'] == 'r2-backup-'+out.name and plan['before_history'] == base.history(store) and
        plan['native_history_approved'] == str(base.HISTORY), 'backup lifetime/generation/history changed')


def worker(store, out):
    cli.require(base.in_job(), 'owned backup worker required')
    plan = store.read(out/'plan.json')
    validate_worker_plan(store, plan, out, [cli.record(p) for p in sources(store)])
    cli.require(cli.record(base.JLINK/'JLink_x64.dll')['sha256'] == base.DLL_SHA, 'native DLL changed')
    for name in (*LOGS, 'events.jsonl', 'callbacks.log', 'project.jlink', 'worker.json', 'backup-header.bin', 'backup-payload.bin'):
        cli.require(not store.checked(out/name).exists(), 'preserve backup; worker cannot replay')
    assets = {k: p.read_bytes() for k, p in owner.ASSETS.items()}
    archive = component.ARCHIVE.read_bytes()
    expected = dict(zip(('backup-header', 'backup-payload'), mapped.expected(archive)))
    deadline = time.monotonic()+WORKER_SECONDS
    result = dict(result='FAILED', close_returned=False)
    dap = observation = None
    archives = {}
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
        def save(name, raw):
            cli.require(name in expected and name not in archives and raw == expected[name], 'fixed backup archive required')
            item = store.raw(out/(name+'.bin'), raw)
            cli.require(cli.record(item['path']) == item, 'durable backup archive differs')
            archives[name] = item
        try:
            cli.require(not base.native_presence()['debugger_processes'], 'competing debugger present')
            with os.add_dll_directory(str(base.JLINK)):
                sdk = base.guarded(ctypes.CDLL, str(base.JLINK/'JLink_x64.dll'))
                dap = base.Dap(sdk, out/LOGS[0], out/'project.jlink', callbacks)
                dap.sdk = owner.JournalSDK(sdk, collect)
                observation = base.Observation(dap, collect, seconds=600)
                result = execute(dap, observation, persist, initial, [out/n for n in LOGS], cli.record,
                    lambda: deadline-time.monotonic(), **assets, archive=archive, emit_archive=save)
        except BaseException as error:
            result.update(result='FAILED', outer_error=type(error).__name__+': '+str(error))
            try:
                if observation is not None: observation.close()
                elif dap is not None and dap._opened: dap.close()
            except BaseException as close: result['outer_close_error'] = str(close)
        result['archives'] = archives
        try:
            result['sources_unchanged_after_close'] = plan['inputs'] == [cli.record(p) for p in sources(store)]
        except BaseException as error:
            result.update(sources_unchanged_after_close=False, source_check_error=str(error))
        if not result['sources_unchanged_after_close']: result['result'] = 'FAILED'
        store.write(out/'worker.json', result)
    print(result['result'], flush=True)
    return 0 if result['result'] == 'R2_BACKUP_MAPPED_NATIVE_CLOSED' else 1


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('action', choices=('selftest', 'capture', 'worker', 'check'))
    p.add_argument('--output-dir', type=Path, required=True)
    p.add_argument('--tests', type=Path)
    p.add_argument('--native-history-approved', type=Path)
    a = p.parse_args()
    cli.require(Path.cwd() == ROOT and sys.flags.isolated and sys.flags.no_site and sys.dont_write_bytecode,
                'isolated explicit root required')
    s = cli.Store(ROOT)
    out = s.checked(a.output_dir)
    if a.action == 'worker': return worker(s, out)
    paths = sources(s)
    preflight(s, out, paths)
    records = [cli.record(p) for p in paths]
    if a.action == 'check':
        print('BACKUP_OUTPUT_PREFLIGHT_PASS', len(paths)); return 0
    if a.action == 'capture':
        cli.require(a.native_history_approved == base.HISTORY, 'exact native history permission required')
        test_path = s.checked(a.tests)
        tested = s.read(test_path)
        cli.require(tested['result'] == 'R2_BACKUP_DEVICE_HOST_PASS' and tested['hardware'] is False and
                    tested['inputs'] == records, 'current backup selftests required')
        proof, before = predecessor(s), base.history(s)
        cli.require(not base.native_presence()['debugger_processes'], 'competing debugger present')
    env = host.environment(s, out)
    for path in paths: s.raw(out/'source'/path.relative_to(ROOT), path.read_bytes())
    if a.action == 'selftest':
        log = host.command(s, out, 'tests', [sys.executable, '-I', '-S', '-B', '-X', 'utf8',
            ROOT/'tests/boot/test_p34_r2_backup_device.py', '-v'], env, 240)
        count = re.search(rb'Ran (\d+) tests? in .*\r?\n\r?\nOK\b', log)
        cli.require(count and records == [cli.record(p) for p in paths], 'backup test/source drift')
        s.write(out/'result.json', dict(result='R2_BACKUP_DEVICE_HOST_PASS', tests=int(count[1]),
                                        inputs=records, hardware=False))
        print('R2_BACKUP_DEVICE_HOST_PASS', int(count[1])); return 0
    s.write(out/'plan.json', dict(out=str(out), scope=SCOPE, inputs=records, tests=cli.record(test_path),
        predecessor=proof, before_history=before, native_history_approved=str(base.HISTORY),
        worker_seconds=WORKER_SECONDS, parent_seconds=PARENT_SECONDS, connection_generation='r2-backup-'+out.name))
    result = base.owned_run(s, out, [SELF, 'worker', '--output-dir', out], env, timeout=PARENT_SECONDS)
    result.update(after_history=base.history(s), presence_after=base.native_presence())
    s.write(out/'parent.json', result)
    print(json.dumps(result))
    return 0 if result['exit'] == 0 and not result['timeout'] else 1


if __name__ == '__main__': raise SystemExit(main())
