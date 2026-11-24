"""One AP-register-only native log visibility cell; no target memory operation."""
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
sys.path.insert(0, str(ROOT/'Tools/ota'))
import p34_probe_acquire as base
import p34_online_log_tests as prior
import p34_nor_audit as parser
from recovery_confirm.ap_journal import JournalSDK
from recovery_confirm.mutation_audit import SealedGate
from recovery_confirm.online_log import OnlineLog

cli, host = base.cli, base.host
SELF = Path(__file__).resolve()
LOGS = ('sdk-000.log', 'sdk-001.log')
FILES = (*LOGS, 'plan.json', 'worker.json', 'parent.json', 'worker.log', 'events.jsonl',
         'callbacks.log', 'project.jlink', 'audit.json', 'tests.json', 'tests.log', 'result.json')


def sources(store):
    receipt = ROOT/'.cache/p34-online-log-tests3/result.json'
    tested = store.read(receipt)
    cli.require(tested['result'] == 'ONLINE_LOG_HOST_PASS', 'reviewed online log tests required')
    for item in tested['inputs']:
        cli.require(cli.record(item['path']) == item, 'online log dependency drift')
    return list(dict.fromkeys([*base.SOURCES, *prior.sources(store), SELF,
                              ROOT/'tests/boot/test_p34_online_log_probe.py', receipt]))


def preflight(store, out, inputs):
    cli.require(not out.exists(), 'preserve AP-only probe evidence')
    for name in FILES: store.checked(out/name)
    prior.prior.preflight(store, out, inputs)


def dp_plan(metadata):
    value = metadata['original_dp']
    cli.require(type(value) is int and value in (0, 0x40, 0xf0000000, 0xf0000040), 'original DP scope')
    bit = value & 0x40
    return ([bit | 0x50000000], [bit | 0x10000000, bit]) if not value & 0xf0000000 else ([], [])


def execute(dap, observation, persist, initial_rows, paths, record, left, *, clock=time.monotonic):
    result = dict(result='FAILED', target_memory_accesses=0, mutation_logging_qualified=False)
    log = None
    normal = False
    try:
        observation.connect()
        cli.require(dap.original_csw == dap.word_csw == 0x23000052, 'qualified word CSW required')
        setup, restore = dp_plan(dap.metadata)
        gate = SealedGate(paths, dap.metadata, record)
        log = OnlineLog(dap, gate, persist, left, initial_rows=initial_rows, clock=clock)
        result['old_segment'] = log.switch(read_allowed=lambda _:False, expected_stores=[], expected_dp_writes=setup)
        log.prepare_close()
        normal = True
    except BaseException as error:
        result['error'] = type(error).__name__+': '+str(error)
    finally:
        # This is the sole outer close path. An uncertain log does not grant
        # normal restoration or a retry; Dap still attempts Native Close once.
        try:
            observation.close()
        except BaseException as error:
            normal = False
            result['close_error'] = type(error).__name__+': '+str(error)
        result['close_returned'] = dap.close_returned
        result['dap'] = dict(dap.metadata)
        result['native_ap_error'] = dap.sdk.error
        if normal:
            try:
                result['final_segment'] = log.finish(read_allowed=lambda _:False, expected_stores=[], expected_dp_writes=restore)
                cli.require(log.gate.cursor.target_reads == log.gate.cursor.target_writes == 0, 'unexpected target access')
                result.update(result='ONLINE_LOG_AP_ONLY_CLOSED', logs=list(log.gate.records),
                              native_calls=log.gate.cursor.native_calls, active_head_visible=True)
            except BaseException as error:
                result['audit_error'] = type(error).__name__+': '+str(error)
        if log:
            result.update(log_mode=log.mode, log_error=log.error, sealed=list(log.gate.records))
    return result


def audit_trace(paths, rows, metadata, record, native_closed):
    indexes = [i for i, row in enumerate(rows) if row['event'] == 'online-log-switch-returned']
    cli.require(len(indexes) == 1, 'one completed native log switch required')
    split = indexes[0]
    setup, restore = dp_plan(metadata)
    gate = SealedGate(paths, metadata, record)
    gate.begin(0)
    first = gate.seal(0, rows[:split], read_allowed=lambda _:False, expected_stores=[], expected_dp_writes=setup)
    gate.begin(1)
    last = gate.seal(1, rows[split:], read_allowed=lambda _:False, expected_stores=[],
                     expected_dp_writes=restore, final=True, native_closed=native_closed)
    heads = [row for row in rows if row['event'] == 'online-log-head-verified']
    cli.require(len(heads) == 1 and heads[0]['trace']['native_calls'] == 3 and
                heads[0]['trace']['sequence'] == first['sequence']+3 and
                heads[0]['trace']['first'] == first['tail'], 'active-head journal binding differs')
    prefix = heads[0]['record']
    cli.require(prefix['path'] == str(paths[1]) and type(prefix['bytes']) is int and
                0 < prefix['bytes'] <= 65536, 'active prefix record scope')
    with paths[1].open('rb') as stream:
        raw = stream.read(prefix['bytes'])
    cli.require(len(raw) == prefix['bytes'] and hashlib.sha256(raw).hexdigest() == prefix['sha256'],
                'active head bytes differ from original SDK prefix')
    return dict(native_calls=gate.cursor.native_calls, target_reads=gate.cursor.target_reads,
                target_writes=gate.cursor.target_writes, native_close=last['native_close_completed'],
                logs=gate.records)


def worker(store, out):
    deadline = time.monotonic()+90
    cli.require(base.in_job(), 'owned AP-only worker required')
    plan = store.read(out/'plan.json')
    cli.require(plan['out'] == str(out) and plan['inputs'] == [cli.record(p) for p in sources(store)], 'probe source drift')
    cli.require(plan['native_history_approved'] == str(base.HISTORY) and
                cli.record(base.JLINK/'JLink_x64.dll')['sha256'] == base.DLL_SHA, 'native identity/permission drift')
    result = dict(result='FAILED', close_returned=False)
    dap = observation = None
    with (out/'events.jsonl').open('x', encoding='utf-8') as stream, (out/'callbacks.log').open('xb') as callbacks:
        initial = []
        def persist(event, **fields):
            stream.write(json.dumps(dict(time=cli.now(), event=event, **fields))+'\n')
            stream.flush()
        def collect(event, **fields):
            persist(event, **fields)
            initial.append(dict(event=event, **fields))
        try:
            cli.require(not base.native_presence()['debugger_processes'], 'competing debugger')
            with os.add_dll_directory(str(base.JLINK)):
                sdk = base.guarded(ctypes.CDLL, str(base.JLINK/'JLink_x64.dll'))
                dap = base.Dap(sdk, out/LOGS[0], out/'project.jlink', callbacks)
                dap.sdk = JournalSDK(sdk, collect)
                observation = base.Observation(dap, collect, seconds=90)
                cli.require(deadline-time.monotonic() >= 80, 'setup consumed operation/close allowance')
                result = execute(dap, observation, persist, initial, [out/name for name in LOGS],
                                 cli.record, lambda:deadline-time.monotonic())
        except BaseException as error:
            result['error'] = type(error).__name__+': '+str(error)
            if dap is not None and dap._opened and observation is None:
                try: dap.close()
                except BaseException as close: result['close_error'] = str(close)
            if dap is not None:
                result.update(close_returned=dap.close_returned, dap=dap.metadata)
        store.write(out/'worker.json', result)
    print(json.dumps(result))
    return 0 if result['result'] == 'ONLINE_LOG_AP_ONLY_CLOSED' else 1


def audit(store, out):
    plan, result, parent = (store.read(out/(name+'.json')) for name in ('plan', 'worker', 'parent'))
    cli.require(plan['inputs'] == [cli.record(p) for p in sources(store)], 'probe audit source drift')
    cli.require(parent['exit'] == 0 and not parent['timeout'] and result['result'] == 'ONLINE_LOG_AP_ONLY_CLOSED' and
                result['close_returned'] is True and result['native_ap_error'] is None and
                parent['after_history'] == plan['before_history'], 'normal original probe closure required')
    for item in plan['inputs']:
        snapshot = cli.record(out/'source'/Path(item['path']).relative_to(ROOT))
        cli.require((snapshot['bytes'], snapshot['sha256']) == (item['bytes'], item['sha256']), 'snapshot changed')
    bound = [cli.record(out/name) for name in (*LOGS, 'events.jsonl', 'plan.json', 'worker.json', 'parent.json')]
    rows = list(parser.events(out/'events.jsonl'))
    for row in rows:
        if row['event'] == 'online-log-head-verified':
            row['trace']['first'] = [tuple(item) for item in row['trace']['first']]
    trace = audit_trace([out/name for name in LOGS], rows, result['dap'], cli.record, result['close_returned'])
    cli.require(trace['target_reads'] == trace['target_writes'] == 0 and trace['logs'] == result['logs'] and
                trace['native_calls'] == result['native_calls'] and
                bound == [cli.record(item['path']) for item in bound], 'probe trace/archive mismatch')
    store.write(out/'audit.json', dict(result='ONLINE_LOG_AP_ONLY_AUDIT_PASS', trace=trace, inputs=bound,
        active_head_visible=True, mutation_logging_qualified=False, historical_nor_sdk_gap_repaired=False))


def main():
    parser_args = argparse.ArgumentParser(description=__doc__)
    parser_args.add_argument('action', choices=('selftest', 'capture', 'worker', 'audit'))
    parser_args.add_argument('--output-dir', type=Path, required=True)
    parser_args.add_argument('--tests', type=Path)
    parser_args.add_argument('--native-history-approved', type=Path)
    args = parser_args.parse_args()
    cli.require(Path.cwd() == ROOT and sys.flags.isolated and sys.flags.no_site and sys.dont_write_bytecode, 'isolated root required')
    store = cli.Store(ROOT)
    out = store.checked(args.output_dir)
    if args.action == 'worker': return worker(store, out)
    if args.action == 'audit': audit(store, out); print('ONLINE_LOG_AP_ONLY_AUDIT_PASS'); return 0
    inputs = sources(store)
    preflight(store, out, inputs)
    records = [cli.record(p) for p in inputs]
    if args.action == 'capture':
        tested = store.read(args.tests)
        cli.require(tested['result'] == 'ONLINE_LOG_PROBE_HOST_PASS' and tested['inputs'] == records, 'source-bound tests required')
        cli.require(args.native_history_approved == base.HISTORY, 'exact native history authority required')
        before = base.history(store)
    env = host.environment(store, out)
    for path in inputs: store.raw(out/'source'/path.relative_to(ROOT), path.read_bytes())
    if args.action == 'selftest':
        log = host.command(store, out, 'tests', [sys.executable, '-I', '-S', '-B', '-X', 'utf8',
            ROOT/'tests/boot/test_p34_online_log_probe.py', '-v'], env, 90)
        match = re.search(rb'Ran (\d+) tests? in .*\r?\n\r?\nOK\b', log)
        cli.require(match and records == [cli.record(p) for p in inputs], 'probe host test/source drift')
        store.write(out/'result.json', dict(result='ONLINE_LOG_PROBE_HOST_PASS', tests=int(match[1]), inputs=records, hardware=False))
        print('ONLINE_LOG_PROBE_HOST_PASS tests='+str(int(match[1]))); return 0
    store.write(out/'plan.json', dict(out=str(out), inputs=records, tests=cli.record(args.tests),
        native_history_approved=str(base.HISTORY), before_history=before, worker_seconds=90, parent_seconds=120,
        scope='One AP-register-only log switch and active-prefix visibility; zero target memory accesses, halt or reset'))
    result = base.owned_run(store, out, [SELF, 'worker', '--output-dir', out], env, timeout=120)
    result['after_history'] = base.history(store)
    result['presence_after'] = base.native_presence()
    store.write(out/'parent.json', result)
    print(json.dumps(result))
    return 0 if result['exit'] == 0 and not result['timeout'] else 1


if __name__ == '__main__': raise SystemExit(main())
