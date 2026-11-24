"""Bounded R2 checkpoint owner and closed-log audit, without a capture CLI yet."""
import argparse
import hashlib
from pathlib import Path
import re
import sys
import time

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'Tools/ota'))
import p34_probe_acquire as base
import p34_online_log_probe as setup
import p34_r2_checkpoint_tests as component_tests
from recovery_confirm.r2_checkpoint import Checkpoint, LOG_COUNT, APP_READS, BOOT_READS
from recovery_confirm import r2_health as health
from recovery_confirm.ap_journal import JournalSDK
from recovery_confirm.mutation_audit import SealedGate
from recovery_confirm.online_log import OnlineLog

cli, host = base.cli, base.host
SELF = Path(__file__).resolve()
LOGS = tuple('sdk-%03d.log' % i for i in range(LOG_COUNT))


def execute(dap, observation, persist, initial, paths, record, remaining, archive,
            image, boot, map_bytes, *, connection_generation, clock=time.monotonic,
            sleep=time.sleep, guard=base.guarded):
    """One connection/close; no replay or target mutation on any failure."""
    result = dict(result='FAILED', close_returned=False, target_payload_writes=0,
                  reset_performed=False, physical_bcb_observed=False,
                  backup_observed=False, ota_ready=False)
    logs = checkpoint = None
    normal = False
    try:
        observation.connect()
        cli.require(dap.original_csw == dap.word_csw == 0x23000052,
                    'qualified native word profile required')
        acquisition, restore = setup.dp_plan(dap.metadata)
        logs = OnlineLog(dap, SealedGate(paths, dap.metadata, record), persist,
                         remaining, initial_rows=initial, clock=clock)
        logs.switch(read_allowed=lambda _: False, expected_stores=[],
                    expected_dp_writes=acquisition)
        checkpoint = Checkpoint(dap, logs, remaining, archive, image, boot, map_bytes,
            connection_generation=connection_generation, clock=clock, sleep=sleep, guard=guard)
        result['checkpoint'] = checkpoint.run()
        logs.prepare_close()
        normal = True
    except BaseException as error:
        result['error'] = type(error).__name__ + ': ' + str(error)
    finally:
        # Observation marks close consumed before invoking the DLL. Do not retry
        # an uncertain native close or mask a failed segment with new observation.
        try:
            observation.close()
        except BaseException as error:
            normal = False
            result['close_error'] = type(error).__name__ + ': ' + str(error)
        result.update(close_returned=dap.close_returned, dap=dict(dap.metadata),
                      native_ap_error=dap.sdk.error)
        if checkpoint:
            result['checkpoint_error'] = checkpoint.error
        if normal:
            try:
                final = guard(lambda: logs.finish(read_allowed=lambda _: False,
                    expected_stores=[], expected_dp_writes=restore), seconds=min(60, remaining()))
                unchanged_dp = not dap.power_changed and dap.original_dp & 0xf0000000 == 0xf0000000
                cli.require(dap.close_returned and dap.metadata['tar_restored'] and
                    dap.metadata['csw_restored'] and (dap.metadata['dp_restored'] or unchanged_dp),
                    'checkpoint AP/native restoration incomplete')
                cli.require(logs.gate.cursor.target_writes == 0 and final['native_close_completed'] == 1,
                            'checkpoint is not a closed read-only observation')
                result.update(result='R2_CHECKPOINT_NATIVE_CLOSED', final_trace=final,
                    logs=list(logs.gate.records), native_close_audited=True,
                    original_dp_preserved_without_write=unchanged_dp)
            except BaseException as error:
                result['final_audit_error'] = type(error).__name__ + ': ' + str(error)
        if logs:
            result.update(log_mode=logs.mode, log_error=logs.error, sealed=list(logs.gate.records))
    return result


def audit_trace(paths, rows, metadata, record, native_closed):
    """Reconcile all raw calls and active heads; not an independent health oracle."""
    groups, current = [], []
    for row in rows:
        if row['event'] == 'online-log-switch-returned':
            cli.require((row['old'], row['new']) == (len(groups), len(groups) + 1),
                        'checkpoint segment order differs')
            groups.append(current)
            current = []
        current.append(row)
    groups.append(current)
    cli.require(len(paths) == len(groups) == LOG_COUNT, 'complete checkpoint log layout required')
    acquisition, restore = setup.dp_plan(metadata)
    gate = SealedGate(paths, metadata, record)
    for index, group in enumerate(groups):
        reads = APP_READS if 1 <= index <= 19 else BOOT_READS if index in (20, 21) else health.READS if index == 22 else set()
        writes = acquisition if index == 0 else restore if index == 23 else []
        gate.begin(index)
        trace = gate.seal(index, group, read_allowed=lambda a: a in reads, expected_stores=[],
            expected_dp_writes=writes, final=index == 23, native_closed=native_closed if index == 23 else False)
        heads = [row for row in group if row['event'] == 'online-log-head-verified']
        if index:
            # Checkpoint/monitor entry may verify the same active head again.
            cli.require(heads, 'checkpoint active head not verified')
            for head in heads:
                prefix = head['record']
                cli.require(prefix['path'] == str(paths[index]) and type(prefix['bytes']) is int and
                            0 < prefix['bytes'] <= 65536, 'checkpoint head extent differs')
                with paths[index].open('rb') as stream:
                    raw = stream.read(prefix['bytes'])
                cli.require(len(raw) == prefix['bytes'] and hashlib.sha256(raw).hexdigest() == prefix['sha256'],
                            'checkpoint original SDK head changed')
                cli.require(head['trace']['native_calls'] == 3 and
                    head['trace']['sequence'] == previous['sequence'] + 3 and
                    [tuple(x) for x in head['trace']['first']] == list(previous['tail']),
                    'checkpoint active head journal differs')
        previous = trace
    cli.require(gate.cursor.target_writes == 0 and trace['native_close_completed'] == 1,
                'checkpoint mutation/close differs')
    return dict(logs=gate.records, target_reads=gate.cursor.target_reads,
        target_writes=gate.cursor.target_writes, native_calls=gate.cursor.native_calls,
        native_close=trace['native_close_completed'], runtime_health_independently_reconciled=False)


def sources(store):
    receipt = ROOT / '.cache/p34-r2-checkpoint-tests2/result.json'
    tested = store.read(receipt)
    inputs = component_tests.sources(store)
    cli.require(tested['result'] == 'R2_CHECKPOINT_COMPONENT_HOST_PASS' and
                tested['inputs'] == [cli.record(p) for p in inputs], 'current checkpoint component tests required')
    return list(dict.fromkeys([*inputs, *base.SOURCES, *setup.sources(store), SELF, receipt,
        ROOT / 'tests/boot/test_p34_r2_checkpoint_device.py']))


def preflight(store, out, inputs):
    component_tests.prior.prior.preflight(store, out, inputs)
    for name in (*LOGS, 'plan.json', 'parent.json', 'worker.json', 'worker.log', 'events.jsonl',
                 'callbacks.log', 'project.jlink', 'app.bin', 'boot.bin', 'audit.json'):
        store.checked(out / name)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action', choices=('selftest',))
    parser.add_argument('--output-dir', type=Path, required=True)
    args = parser.parse_args()
    cli.require(Path.cwd() == ROOT and sys.flags.isolated and sys.flags.no_site and sys.dont_write_bytecode,
                'isolated explicit project root required')
    store = cli.Store(ROOT)
    out = store.checked(args.output_dir)
    inputs = sources(store)
    preflight(store, out, inputs)
    records = [cli.record(p) for p in inputs]
    env = host.environment(store, out)
    for source in inputs:
        store.raw(out / 'source' / source.relative_to(ROOT), source.read_bytes())
    log = host.command(store, out, 'tests', [sys.executable, '-I', '-S', '-B', '-X', 'utf8',
        ROOT / 'tests/boot/test_p34_r2_checkpoint_device.py', '-v'], env, 240)
    count = re.search(rb'Ran (\d+) tests? in .*\r?\n\r?\nOK\b', log)
    cli.require(count and records == [cli.record(p) for p in inputs], 'checkpoint owner test/source drift')
    store.write(out / 'result.json', dict(result='R2_CHECKPOINT_OWNER_HOST_PASS', tests=int(count[1]),
        inputs=records, hardware=False, capture_cli_implemented=False))
    print('R2_CHECKPOINT_OWNER_HOST_PASS', int(count[1]))


if __name__ == '__main__':
    main()
