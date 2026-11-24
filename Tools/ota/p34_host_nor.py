"""Contained, status-only qualification of a halted-host NOR controller route."""
import argparse
import ctypes
import json
import os
from pathlib import Path
import re
import sys

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT/'Tools/ota'))
import p34_halted_probe as previous
from recovery_entry.control_probe import Control
from recovery_entry.owner_probe import Reader, collect
from recovery_entry import host_nor as hn

base, cli, host = previous.base, previous.cli, previous.host
SELF = Path(__file__).resolve()
SOURCES = list(dict.fromkeys([*previous.SOURCES, SELF, *(ROOT/n for n in (
    'Tools/ota/recovery_entry/host_nor.py', 'tests/boot/test_p34_host_nor.py',
    '.cache/p34-entry-owner1/worker.json', '.cache/p34-entry-owner1/parent.json',
    '.cache/p34-host-bcb1/worker.json', '.cache/p34-host-bcb1/capture-raw.bin',
    '.cache/p34-erase/references/w25q128.pdf',
    '.cache/p34-erase/references/pdftotext.log',
    '.cache/p34-entry-qspi-manual1/page-0634.txt',
    '.cache/p34-entry-qspi-manual1/page-0642.txt',
    '.cache/p34-entry-qspi-manual1/page-0643.txt',
    '.cache/p34-entry-qspi-manual1/page-0644.txt',
    '.cache/p34-entry-qspi-manual1/page-0645.txt',
    '.cache/p34-entry-qspi-manual1/page-0646.txt'))]))
FILES = previous.predecessor.FILES


def preflight(store, out):
    cli.require(not out.exists(), 'preserve NOR status evidence')
    for name in FILES: store.checked(out/name)
    for p in SOURCES: store.checked(out/'source'/p.relative_to(ROOT))


def snapshot(store, out):
    inputs = [cli.record(p) for p in SOURCES]
    env = host.environment(store, out)
    for p in SOURCES: store.raw(out/'source'/p.relative_to(ROOT), p.read_bytes())
    return inputs, env


def owners(control, dap, emit):
    samples = [control.media(), control.media()]
    for s in samples: hn.qualify_masters(s)
    pages = [collect(Reader(dap, emit)), collect(Reader(dap, emit))]
    cli.require(pages[0] == pages[1] and pages[0]['no_scheduled_sd_ota_owner'] and
                not pages[0]['updater_error_observed'], 'updater owner not idle/stable')
    return dict(samples=samples, pages=pages)


def worker(store, out):
    cli.require(base.in_job(), 'owned native worker required')
    plan = store.read(out/'plan.json')
    cli.require(plan['inputs'] == [cli.record(p) for p in SOURCES] and plan['out'] == str(out),
                'source/plan drift')
    cli.require(plan['native_history_approved'] == str(base.HISTORY), 'history scope mismatch')
    cli.require(cli.record(base.JLINK/'JLink_x64.dll')['sha256'] == base.DLL_SHA, 'SDK drift')
    for n in FILES: store.checked(out/n)
    result = dict(result='FAILED', close_returned=False, nor_payload_bytes_written=0,
                  reset_performed=False, automatic_resume=False, nor_write_admitted=False)
    control, dap, status, port = None, None, None, None
    with (out/'events.jsonl').open('x', encoding='utf-8') as events, (out/'callbacks.log').open('xb') as callbacks:
        def emit(event, **fields):
            events.write(json.dumps(dict(time=cli.now(), event=event, **fields))+'\n')
            events.flush()
        try:
            presence = base.native_presence()
            emit('presence', **presence)
            cli.require(not presence['debugger_processes'], 'other debugger present')
            with os.add_dll_directory(str(base.JLINK)):
                sdk = base.guarded(ctypes.CDLL, str(base.JLINK/'JLink_x64.dll'))
                dap = base.Dap(sdk, out/'sdk.log', out/'project.jlink', callbacks)
                observation = base.Observation(dap, emit, seconds=80)
                image = (ROOT/'.cache/p34-native-image1/app-readback.bin').read_bytes()
                control = Control(dap, observation, emit, image[0x400:0x460], retained=True)
                observation.connect()
                original = store.read(ROOT/'.cache/p34-entry-wfi1/worker.json')
                result['before'] = control.observe_retained(original)
                cli.require(all(s['header_hex'] == image[0x400:0x460].hex()
                            for s in result['before']['state_samples']), 'live App identity changed')
                result['owners_before'] = owners(control, dap, emit)
                port = hn.Port(control, emit)
                status = hn.Status(port, emit)
                result['status'] = status.execute()
                result['owners_after'] = owners(control, dap, emit)
                cli.require(control.context() == original['context'], 'NOR post-status context changed')
                observation._check()
                result['result'] = 'HOST_NOR_STATUS_RESTORED_RETAINED'
        except BaseException as error:
            result['error'] = type(error).__name__+': '+str(error)
        finally:
            if status:
                result['controller'] = dict(error=status.error, switched=status.switched,
                    restored=status.restored, commands=status.commands, original=status.original)
            try:
                if port: port.restore_ap()
            except BaseException as error:
                result.update(result='FAILED', ap_close_error=type(error).__name__+': '+str(error))
            if port: result['ap_csw_restored'] = port.ap_csw_restored
            try:
                if control: control.close()
            except BaseException as error:
                result.update(result='FAILED', close_error=type(error).__name__+': '+str(error))
            result['close_returned'] = bool(dap and dap.close_returned)
            if dap: result['dap'] = dap.metadata
            store.write(out/'worker.json', result)
    print(json.dumps(result))
    return 0 if result['result'] == 'HOST_NOR_STATUS_RESTORED_RETAINED' and result['close_returned'] else 1


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action', choices=('selftest', 'status', 'worker'))
    parser.add_argument('--output-dir', type=Path, required=True)
    parser.add_argument('--tests', type=Path)
    parser.add_argument('--native-history-approved', type=Path)
    args = parser.parse_args()
    cli.require(Path.cwd() == ROOT and sys.flags.isolated and sys.flags.no_site and sys.dont_write_bytecode,
                'isolated explicit root required')
    store = cli.Store(ROOT)
    out = store.checked(args.output_dir)
    if args.action == 'worker': return worker(store, out)
    preflight(store, out)
    inputs = [cli.record(p) for p in SOURCES]
    if args.action == 'selftest':
        inputs, env = snapshot(store, out)
        env['P34_TEST_OUT'] = str(out)
        data = host.command(store, out, 'tests', [sys.executable, '-I', '-S', '-B', '-X', 'utf8',
                            ROOT/'tests/boot/test_p34_host_nor.py', '-v'], env, 90)
        match = re.search(rb'Ran (\d+) tests? in .*\r?\n\r?\nOK\b', data)
        cli.require(match and inputs == [cli.record(p) for p in SOURCES], 'test/input drift')
        store.write(out/'result.json', dict(result='HOST_NOR_STATUS_TESTS_PASS', tests=int(match[1]),
                    inputs=inputs, hardware=False))
        print('HOST_NOR_STATUS_TESTS_PASS', int(match[1])); return 0
    cli.require(args.native_history_approved == base.HISTORY, 'exact history scope required')
    tests = store.read(args.tests)
    cli.require(tests['result'] == 'HOST_NOR_STATUS_TESTS_PASS' and tests['inputs'] == inputs,
                'bound tests required')
    for name in ('p34-entry-owner1', 'p34-host-bcb1'):
        p = store.read(ROOT/'.cache'/name/'parent.json')
        cli.require(p['exit'] == 0 and not p['timeout'], 'uncertain predecessor')
    before = base.history(store)
    inputs, env = snapshot(store, out)
    store.write(out/'plan.json', dict(action='status', inputs=inputs, out=str(out), tests=cli.record(args.tests),
        native_history_approved=str(base.HISTORY), before_history=before, worker_seconds=90,
        native_call_seconds=5, scope='NOR-21-STATUS; 05/35/9F only; CTRL divisor/XIP only; halted/no reset/no WREN'))
    result = base.owned_run(store, out, [SELF, 'worker', '--output-dir', out], env, timeout=90)
    result['after_history'] = base.history(store)
    result['presence_after'] = base.native_presence()
    store.write(out/'parent.json', result)
    print(json.dumps(result))
    return 0 if result['exit'] == 0 and not result['timeout'] else 1


if __name__ == '__main__': raise SystemExit(main())
