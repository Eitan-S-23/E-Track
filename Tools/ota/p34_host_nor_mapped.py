"""One finite cache-bypassed mapped-read comparison against original FIFO evidence."""
import argparse
import ctypes
import json
import os
from pathlib import Path
import re
import sys

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT/'Tools/ota'))
import p34_host_nor_read as prior
from recovery_entry import host_nor_mapped as mapped
from recovery_entry.control_probe import Control

base, cli, host = prior.base, prior.cli, prior.host
SELF = Path(__file__).resolve()
SOURCES = list(dict.fromkeys([*prior.SOURCES, SELF, *(ROOT/n for n in (
    'Tools/ota/recovery_entry/host_nor_mapped.py', 'tests/boot/test_p34_host_nor_mapped.py',
    '.cache/p34-entry-qspi-manual1/page-0648.txt', 'Libraries/USB_MSC/msc_diskio.h',
    '.cache/p34-host-nor-read1/worker.json', '.cache/p34-host-nor-read1/parent.json',
    '.cache/p34-host-nor-read1/plan.json', '.cache/p34-host-nor-read1/candidate-prefix.bin',
    '.cache/p34-host-nor-read1/recovery-prefix.bin', '.cache/p34-host-nor-read1/preserved-boundary.bin'))]))
FILES = prior.FILES


def preflight(store, out):
    cli.require(not out.exists(), 'preserve mapped evidence')
    for n in FILES: store.checked(out/n)
    for p in SOURCES: store.checked(out/'source'/p.relative_to(ROOT))


def snapshot(store, out):
    inputs = [cli.record(p) for p in SOURCES]; env = host.environment(store, out)
    for p in SOURCES: store.raw(out/'source'/p.relative_to(ROOT), p.read_bytes())
    return inputs, env


def worker(store, out):
    cli.require(base.in_job(), 'owned worker required')
    plan = store.read(out/'plan.json')
    cli.require(plan['inputs'] == [cli.record(p) for p in SOURCES] and plan['out'] == str(out), 'input drift')
    cli.require(plan['native_history_approved'] == str(base.HISTORY), 'history scope mismatch')
    cli.require(cli.record(base.JLINK/'JLink_x64.dll')['sha256'] == base.DLL_SHA, 'SDK drift')
    for n in FILES: store.checked(out/n)
    result = dict(result='FAILED', close_returned=False, nor_payload_bytes_written=0, reset_performed=False,
                  automatic_resume=False, nor_write_admitted=False)
    control, dap, port, reader = None, None, None, None
    with (out/'events.jsonl').open('x', encoding='utf-8') as events, (out/'callbacks.log').open('xb') as callbacks:
        def emit(event, **fields):
            events.write(json.dumps(dict(time=cli.now(), event=event, **fields))+'\n'); events.flush()
        try:
            presence = base.native_presence(); emit('presence', **presence)
            cli.require(not presence['debugger_processes'], 'another debugger present')
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
                            for s in result['before']['state_samples']), 'App identity changed')
                result['owners_before'] = prior.prior.owners(control, dap, emit)
                port = mapped.Port(control, emit); reader = mapped.Reader(port, emit)
                capture = mapped.collect(reader); result['capture'] = capture
                for name, field in (('candidate-prefix', 'candidate_prefix_hex'), ('recovery-prefix', 'recovery_prefix_hex'),
                                    ('preserved-boundary', 'preserved_boundary_hex')):
                    data = bytes.fromhex(capture[field]); store.raw(out/(name+'.bin'), data)
                    cli.require(data == (ROOT/'.cache/p34-host-nor-read1'/(name+'.bin')).read_bytes(),
                                'mapped/FIFO read mismatch: '+name)
                result['owners_after'] = prior.prior.owners(control, dap, emit)
                cli.require(control.context() == original['context'], 'post-mapped context changed')
                observation._check()
                result['result'] = 'HOST_NOR_MAPPED_RESTORED_RETAINED'
        except BaseException as error:
            result['error'] = type(error).__name__+': '+str(error)
            if reader and reader.error is None: reader.error = result['error']
        finally:
            if reader: result['controller'] = dict(error=reader.error, switched=reader.switched, restored=reader.restored)
            try:
                if port: port.restore_ap()
            except BaseException as error:
                result.update(result='FAILED', ap_close_error=type(error).__name__+': '+str(error))
            try:
                if control: control.close()
            except BaseException as error:
                result.update(result='FAILED', close_error=type(error).__name__+': '+str(error))
            result['close_returned'] = bool(dap and dap.close_returned)
            if dap: result['dap'] = dap.metadata
            store.write(out/'worker.json', result)
    print(json.dumps(result))
    return 0 if result['result'] == 'HOST_NOR_MAPPED_RESTORED_RETAINED' and result['close_returned'] else 1


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action', choices=('selftest', 'read', 'worker'))
    parser.add_argument('--output-dir', type=Path, required=True)
    parser.add_argument('--tests', type=Path)
    parser.add_argument('--native-history-approved', type=Path)
    args = parser.parse_args()
    cli.require(Path.cwd() == ROOT and sys.flags.isolated and sys.flags.no_site and sys.dont_write_bytecode,
                'isolated explicit root required')
    store = cli.Store(ROOT); out = store.checked(args.output_dir)
    if args.action == 'worker': return worker(store, out)
    preflight(store, out); inputs = [cli.record(p) for p in SOURCES]
    if args.action == 'selftest':
        inputs, env = snapshot(store, out); env['P34_TEST_OUT'] = str(out)
        log = host.command(store, out, 'tests', [sys.executable, '-I', '-S', '-B', '-X', 'utf8',
                           ROOT/'tests/boot/test_p34_host_nor_mapped.py', '-v'], env, 120)
        match = re.search(rb'Ran (\d+) tests? in .*\r?\n\r?\nOK\b', log)
        cli.require(match and inputs == [cli.record(p) for p in SOURCES], 'test/source drift')
        store.write(out/'result.json', dict(result='HOST_NOR_MAPPED_TESTS_PASS', tests=int(match[1]), inputs=inputs, hardware=False))
        print('HOST_NOR_MAPPED_TESTS_PASS', int(match[1])); return 0
    cli.require(args.native_history_approved == base.HISTORY, 'exact history scope required')
    tests = store.read(args.tests)
    cli.require(tests['result'] == 'HOST_NOR_MAPPED_TESTS_PASS' and tests['inputs'] == inputs, 'bound tests required')
    parent = store.read(ROOT/'.cache/p34-host-nor-read1/parent.json')
    cli.require(parent['exit'] == 0 and not parent['timeout'], 'uncertain read predecessor')
    before = base.history(store); inputs, env = snapshot(store, out)
    store.write(out/'plan.json', dict(action='read', out=str(out), inputs=inputs, tests=cli.record(args.tests),
        native_history_approved=str(base.HISTORY), before_history=before, worker_seconds=90, native_call_seconds=5,
        scope='NOR-21-MAPPED: BYPASSC1, /12, fixed candidate/recovery/boundary reads; no mapped stores/NOR writes'))
    result = base.owned_run(store, out, [SELF, 'worker', '--output-dir', out], env, timeout=90)
    result['after_history'] = base.history(store); result['presence_after'] = base.native_presence()
    store.write(out/'parent.json', result); print(json.dumps(result))
    return 0 if result['exit'] == 0 and not result['timeout'] else 1


if __name__ == '__main__': raise SystemExit(main())
