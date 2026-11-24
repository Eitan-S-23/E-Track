"""Bounded R2 stop/release qualification; deliberately no Flash programming CLI."""
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
import p34_boot16_entry_tests as entry_tests
import p34_r2_postcheck as post
from recovery_confirm import boot16_entry as entry
from recovery_confirm import r2_paired_health as health
from recovery_confirm.online_log import OnlineLog
from recovery_confirm.mutation_audit import SealedGate
from recovery_confirm.ap_journal import JournalSDK

cli, host = base.cli, base.host
SELF = Path(__file__).resolve()
IMAGE = ROOT / '.cache/p34-recovery-sources1/r2-b.bin'
MAP = ROOT / '.cache/p34-early-usb-r2/on/b/app-gcc/X-Track-App-GCC.map'
PRIOR = ROOT / '.cache/p34-r2-post-identity2/worker.json'
LOGS = tuple('sdk-%03d.log' % n for n in range(6))
WORKER_SECONDS, PARENT_SECONDS = 600, 720


def execute(dap, observation, persist, initial, paths, record, remaining, image, map_bytes,
            *, clock=time.monotonic, sleep=time.sleep, guard=base.guarded,
            control_type=entry.Control, monitor_type=health.Monitor):
    result = dict(result='FAILED', close_returned=False, boot_written=False, reset_performed=False,
                  physical_bcb_observed=False, full_image_read_this_cell=False)
    logs = control = monitor = None
    normal = False
    original_close = observation.close
    def close():
        try:
            if control and control.mutation_attempted and not normal:
                # A failed/uncertain halt or release never authorizes power-request
                # removal. This is logical DAP retention, not a 3.3V supply command.
                dap.power_changed = False
                dap.metadata['dp_restore_deferred_for_halt'] = True
                if dap.ready: dap.metadata['retained_dp_ctrlstat'] = dap._power_ready()
        finally:
            original_close()
    observation.close = close
    try:
        observation.connect()
        cli.require(dap.original_csw == dap.word_csw == 0x23000052, 'qualified AP word profile required')
        acquisition, restore = setup.dp_plan(dap.metadata)
        logs = OnlineLog(dap, SealedGate(paths, dap.metadata, record), persist,
                         remaining, initial_rows=initial, clock=clock)
        logs.switch(read_allowed=lambda _: False, expected_stores=[], expected_dp_writes=acquisition)
        def owner(): return logs.target_allowed() and remaining() > 90
        control = control_type(dap, image, map_bytes, owner, logs.emit, seconds=480,
                               clock=clock, sleep=sleep, guard=guard)
        result['entry'] = control.acquire()
        selectors = [(entry.DCRSR, value) for value in (15, 16, 17, 20)]
        stores = [(entry.PAUSE, control.before['pause'] | 0x1000), (entry.COMP, entry.WFI_COMPARATOR)]
        stores += selectors + [(entry.COMP, 0)] + selectors
        result['entry_trace'] = guard(lambda: logs.switch(read_allowed=lambda a: a in entry.READS,
            expected_stores=stores), seconds=min(60, remaining()-90))
        # This cell never writes Flash or executes Boot. It validates the live
        # entry/release primitives only, referencing the prior complete identity.
        result['release'] = control.release(lambda: logs.target_allowed() and
            result['entry']['result'] == 'R2_B_WFI_HELD' and remaining() > 180)
        stores = selectors + ([] if control.before['dfsr'] & 2 else [(entry.REGS['dfsr'], 2)])
        stores += [(entry.DHCSR, 0xa05f0001)]
        result['release_trace'] = guard(lambda: logs.switch(read_allowed=lambda a: a in entry.READS,
            expected_stores=stores), seconds=min(60, remaining()-90))
        result['pause'] = control.restore_pause_running()
        result['pause_trace'] = guard(lambda: logs.switch(read_allowed=lambda a: a in entry.READS,
            expected_stores=[(entry.PAUSE, control.before['pause'])]), seconds=min(60, remaining()-90))
        monitor = monitor_type(dap, image, map_bytes, owner, logs, remaining,
                              clock=clock, sleep=sleep, guard=guard)
        result['health'] = monitor.run()
        cli.require(result['health']['result'] == 'R2_RUNTIME_HEALTH_OBSERVED', 'health phase incomplete')
        logs.prepare_close()
        normal = True
    except BaseException as error:
        result['error'] = type(error).__name__+': '+str(error)
    finally:
        try: observation.close()
        except BaseException as error:
            normal = False
            result['close_error'] = type(error).__name__+': '+str(error)
        result.update(close_returned=dap.close_returned, dap=dict(dap.metadata), native_ap_error=dap.sdk.error)
        if control:
            result.update(control_error=control.error, mutation_attempted=control.mutation_attempted,
                release_attempted=control.release_attempted, release_returned=control.release_returned,
                pause_restored=control.pause_restored, context=control.context_before, before=control.before)
        if normal:
            try:
                result['final_trace'] = guard(lambda: logs.finish(read_allowed=lambda _: False,
                    expected_stores=[], expected_dp_writes=restore), seconds=min(60, remaining()))
                unchanged = not dap.power_changed and dap.original_dp & 0xf0000000 == 0xf0000000
                cli.require(dap.close_returned and dap.metadata['tar_restored'] and dap.metadata['csw_restored']
                    and (dap.metadata['dp_restored'] or unchanged), 'final native/AP restoration incomplete')
                result.update(result='BOOT16_R2_ENTRY_QUALIFIED_CLOSED', logs=list(logs.gate.records),
                              native_close_audited=True, original_boot_executed=False)
            except BaseException as error: result['final_audit_error'] = type(error).__name__+': '+str(error)
        if logs:
            result.update(log_mode=logs.mode, log_error=logs.error, sealed=list(logs.gate.records))
    return result


def audit_trace(paths, rows, metadata, record, native_closed):
    """Offline reparse of all native segments, not a copy of worker PASS flags."""
    groups, current = [], []
    for row in rows:
        if row['event'] == 'online-log-switch-returned':
            cli.require((row['old'], row['new']) == (len(groups), len(groups)+1), 'probe segment order')
            groups.append(current)
            current = []
        current.append(row)
    groups.append(current)
    cli.require(len(paths) == len(groups) == 6, 'complete six-segment probe required')
    before = {}
    for row in groups[1]:
        if row['event'] == 'recovery-word-read' and row['address'] in (entry.PAUSE, entry.REGS['dfsr']):
            before.setdefault(row['address'], row['value'])
    cli.require(set(before) == {entry.PAUSE, entry.REGS['dfsr']}, 'original debug values missing')
    selectors = [(entry.DCRSR, value) for value in (15, 16, 17, 20)]
    stores = {0: [], 1: [(entry.PAUSE, before[entry.PAUSE] | 0x1000), (entry.COMP, entry.WFI_COMPARATOR)]
        + selectors + [(entry.COMP, 0)] + selectors,
        2: selectors + ([] if before[entry.REGS['dfsr']] & 2 else [(entry.REGS['dfsr'], 2)])
        + [(entry.DHCSR, 0xa05f0001)], 3: [(entry.PAUSE, before[entry.PAUSE])], 4: [], 5: []}
    acquisition, restore = setup.dp_plan(metadata)
    gate = SealedGate(paths, metadata, record)
    previous = None
    for index, group in enumerate(groups):
        reads = entry.READS if index in (1, 2, 3) else health.old.READS if index == 4 else set()
        gate.begin(index)
        trace = gate.seal(index, group, read_allowed=lambda a: a in reads, expected_stores=stores[index],
            expected_dp_writes=acquisition if index == 0 else restore if index == 5 else [],
            final=index == 5, native_closed=native_closed if index == 5 else False)
        heads = [row for row in group if row['event'] == 'online-log-head-verified']
        if index:
            cli.require(heads, 'probe active head missing')
            for head in heads:
                item = head['record']
                cli.require(item['path'] == str(paths[index]) and type(item['bytes']) is int and
                            0 < item['bytes'] <= 65536, 'probe active head extent')
                with paths[index].open('rb') as stream: raw = stream.read(item['bytes'])
                cli.require(len(raw) == item['bytes'] and hashlib.sha256(raw).hexdigest() == item['sha256'],
                            'probe original active head changed')
                cli.require(head['trace']['native_calls'] == 3 and
                    head['trace']['sequence'] == previous['sequence']+3 and
                    [tuple(x) for x in head['trace']['first']] == list(previous['tail']), 'probe head AP continuity')
        previous = trace
    cli.require(trace['native_close_completed'] == 1, 'one completed native Close required')
    return dict(result='BOOT16_PROBE_NATIVE_TRACE_RECONCILED', logs=gate.records,
        native_calls=gate.cursor.native_calls, target_reads=gate.cursor.target_reads,
        target_writes=gate.cursor.target_writes, boot_payload_writes=0, reset_commands=0,
        health_independently_reconciled=False)


def sources(store):
    cli.require(cli.record(PRIOR)['sha256'] ==
        'b0db8168b18564a61b7ea65c8b5956ca52f945d3809ff833a0b011cbd6a6052a', 'prior physical identity changed')
    declared = [*entry_tests.sources(), *post.sources(store), *setup.sources(store),
        *base.SOURCES, SELF, ROOT / 'tests/boot/test_p34_boot16_probe.py',
        ROOT / 'tests/boot/test_p34_online_log_probe.py',
        ROOT / 'tests/boot/test_p34_r2_checkpoint_device.py',
        ROOT / 'Tools/ota/recovery_confirm/r2_paired_health.py', PRIOR, IMAGE, MAP]
    test_only = ('tests/boot/p34_gpio_session_model.py', 'tests/boot/test_p34_app_resume.py',
                 'tests/boot/test_p34_control_probe.py', 'tests/boot/test_p34_owner_probe.py')
    # Imports execute module-level code even when their old device APIs are not
    # invoked. Bind that closure rather than trusting an inherited partial list.
    loaded = []
    for module in list(sys.modules.values()):
        filename = getattr(module, '__file__', None)
        if filename:
            path = Path(filename).resolve()
            if path.is_relative_to(ROOT) and path.suffix == '.py': loaded.append(path)
    return sorted(set([*declared, *loaded, *(ROOT / p for p in test_only)]))


def preflight(store, out, inputs):
    cli.require(not out.exists(), 'preserve entry qualification cell')
    for name in (*LOGS, 'plan.json', 'parent.json', 'worker.json', 'worker.log', 'events.jsonl',
                 'callbacks.log', 'project.jlink', 'tests.log', 'tests.json', 'result.json'):
        store.checked(out / name)
    for path in inputs: store.checked(out / 'source' / path.relative_to(ROOT))
    for key in ('HOME', 'USERPROFILE', 'APPDATA', 'LOCALAPPDATA', 'TEMP', 'TMP', 'TMPDIR',
                'XDG_CACHE_HOME', 'XDG_CONFIG_HOME', 'XDG_DATA_HOME', 'PYTHONUSERBASE',
                'PYTHONPYCACHEPREFIX', 'CCACHE_DIR', 'SCCACHE_DIR'):
        store.checked(out / 'host' / key.lower())


def worker(store, out):
    deadline = time.monotonic()+WORKER_SECONDS
    cli.require(base.in_job(), 'owned probe job required')
    plan = store.read(out / 'plan.json')
    cli.require(plan['out'] == str(out) and plan['inputs'] == [cli.record(p) for p in sources(store)], 'probe source drift')
    cli.require(plan['native_history_approved'] == str(base.HISTORY) and
                cli.record(base.JLINK / 'JLink_x64.dll')['sha256'] == base.DLL_SHA, 'native identity/scope drift')
    result = dict(result='FAILED', close_returned=False)
    dap = observation = None
    with (out / 'events.jsonl').open('x', encoding='utf-8') as events, (out / 'callbacks.log').open('xb') as callbacks:
        initial = []
        def persist(event, **fields):
            events.write(json.dumps(dict(time=cli.now(), event=event, **fields))+'\n')
            events.flush()
            if event in ('online-log-sealed', 'boot16-media'):
                os.fsync(events.fileno())
                print(json.dumps(dict(event=event, index=fields.get('index'), remaining=deadline-time.monotonic())), flush=True)
        def collect(event, **fields):
            persist(event, **fields)
            initial.append(dict(event=event, **fields))
        try:
            cli.require(not base.native_presence()['debugger_processes'], 'competing debugger')
            with os.add_dll_directory(str(base.JLINK)):
                sdk = base.guarded(ctypes.CDLL, str(base.JLINK / 'JLink_x64.dll'))
                dap = base.Dap(sdk, out / LOGS[0], out / 'project.jlink', callbacks)
                dap.sdk = JournalSDK(sdk, collect)
                observation = base.Observation(dap, collect, seconds=540)
                result = execute(dap, observation, persist, initial, [out / n for n in LOGS], cli.record,
                    lambda: deadline-time.monotonic(), IMAGE.read_bytes(), MAP.read_bytes())
        except BaseException as error:
            result['outer_error'] = type(error).__name__+': '+str(error)
            if observation is None and dap is not None and dap._opened:
                try: dap.close()
                except BaseException as close: result['outer_close_error'] = str(close)
        result['sources_unchanged_after_close'] = plan['inputs'] == [cli.record(p) for p in sources(store)]
        if not result['sources_unchanged_after_close']: result['result'] = 'FAILED'
        store.write(out / 'worker.json', result)
    print(json.dumps(dict(result=result['result'], close_returned=result['close_returned'])), flush=True)
    return 0 if result['result'] == 'BOOT16_R2_ENTRY_QUALIFIED_CLOSED' else 1


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action', choices=('selftest', 'capture', 'worker'))
    parser.add_argument('--output-dir', required=True, type=Path)
    parser.add_argument('--tests', type=Path)
    parser.add_argument('--native-history-approved', type=Path)
    args = parser.parse_args()
    cli.require(Path.cwd() == ROOT and sys.flags.isolated and sys.flags.no_site and sys.dont_write_bytecode,
                'isolated explicit root required')
    store = cli.Store(ROOT)
    out = store.checked(args.output_dir)
    if args.action == 'worker': return worker(store, out)
    inputs = sources(store)
    preflight(store, out, inputs)
    records = [cli.record(p) for p in inputs]
    if args.action == 'capture':
        tests = store.read(args.tests)
        cli.require(tests['result'] == 'BOOT16_PROBE_HOST_PASS' and tests['inputs'] == records, 'current owner tests required')
        cli.require(args.native_history_approved == base.HISTORY, 'exact native history permission required')
        before = base.history(store)
    env = host.environment(store, out)
    for path in inputs: store.raw(out / 'source' / path.relative_to(ROOT), path.read_bytes())
    if args.action == 'selftest':
        raw = host.command(store, out, 'tests', [sys.executable, '-I', '-S', '-B', '-X', 'utf8',
            ROOT / 'tests/boot/test_p34_boot16_probe.py', '-v'], env, 120)
        count = re.search(rb'Ran (\d+) tests? in .*\r?\n\r?\nOK\b', raw)
        cli.require(count and records == [cli.record(p) for p in inputs], 'probe test/source drift')
        store.write(out / 'result.json', dict(result='BOOT16_PROBE_HOST_PASS', tests=int(count[1]),
            inputs=records, hardware=False, independent_acceptance=False))
        print('BOOT16_PROBE_HOST_PASS', int(count[1]), flush=True)
        return 0
    store.write(out / 'plan.json', dict(out=str(out), inputs=records, tests=cli.record(args.tests),
        native_history_approved=str(base.HISTORY), before_history=before, worker_seconds=WORKER_SECONDS,
        parent_seconds=PARENT_SECONDS, boot_writes=0, eeprom_writes=0, nor_writes=0, reset_commands=0,
        scope='one fresh R2 WFI rendezvous and same-context release qualification; no Boot replacement'))
    value = base.owned_run(store, out, [SELF, 'worker', '--output-dir', out], env, timeout=PARENT_SECONDS)
    value.update(after_history=base.history(store), presence_after=base.native_presence())
    store.write(out / 'parent.json', value)
    print(json.dumps(value), flush=True)
    return 0 if value['exit'] == 0 and not value['timeout'] else 1


if __name__ == '__main__': raise SystemExit(main())
