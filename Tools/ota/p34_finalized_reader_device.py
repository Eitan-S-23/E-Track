"""Finite nonmutating extended-read qualification on the unchanged old App."""
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
import p34_finalized_vtor_capture as capture
from recovery_entry.finalized_reader import Reader

cli, host = base.cli, base.host
SELF = Path(__file__).resolve()
SOURCES = list(dict.fromkeys([*base.SOURCES, SELF, *(ROOT/n for n in (
    'Tools/ota/recovery_entry/finalized_reader.py', 'Tools/ota/p34_finalized_vtor_capture.py',
    'Tools/ota/p34_finalized_vtor.py', 'Tools/ota/p34_recovery_sources.py',
    'tests/boot/test_p34_finalized_reader.py', 'tests/boot/test_p34_finalized_vtor_capture.py',
    'tests/boot/test_p34_finalized_reader_device.py', '.cache/p34-native-image1/app-readback.bin',
    '.cache/p34-reconciled-resume1/worker.json', '.cache/p34-reconciled-resume1/parent.json'))]))
FILES = ('plan.json', 'worker.json', 'parent.json', 'worker.log', 'events.jsonl', 'callbacks.log',
         'sdk.log', 'project.jlink', 'readback.bin', 'tail-unclassified.bin', 'result.json')


def capture_old(reader, original):
    require = cli.require
    require(len(original) == 617588 and hashlib.sha256(original).hexdigest() == base.APP_SHA, 'original App binding')
    reads = []
    started = previous = reader.clock()
    def read(address, size):
        nonlocal previous
        now = reader.clock()
        require(previous <= now < started+240, 'transport deadline/clock changed')
        previous = now
        owner = reader.owner()
        require(owner['owned'] and not owner['reset_seen'], 'transport owner/reset changed')
        raw = reader.read(address, size, started+240-reader.clock())
        require(type(raw) is bytes and len(raw) == size, 'incomplete transport bytes')
        reads.append(dict(address=address, bytes=size, status='completed', sha256=hashlib.sha256(raw).hexdigest()))
        owner = reader.owner()
        require(owner['owned'] and not owner['reset_seen'], 'transport owner/reset changed after read')
        now = reader.clock()
        require(previous <= now < started+240, 'transport deadline/clock changed after read')
        previous = now
        return raw
    def word(address): return int.from_bytes(read(address,4),'little')
    require(word(capture.DHCSR) & 0x020a0000 == 0 and word(capture.VTOR) == 0x08010000, 'old App phase changed')
    raw = b''.join(read(0x08010000+a,min(4096,619580-a)) for a in range(0,619580,4096))
    require(len(raw) == 619580 and raw[:len(original)] == original, 'original App prefix changed')
    require(read(0x08010400,96) == original[0x400:0x460] and read(0x08010000,524) == original[:524],
            'final old-App header/vector identity changed')
    require(word(capture.VTOR) == 0x08010000 and word(capture.DHCSR) & 0x020a0000 == 0, 'final old-App phase changed')
    return raw, reads


def reject_finalized(raw):
    try:
        capture.policy.classify(raw,before=0x08010000,after=0x08010000,table=raw[:524],dhcsr=0,halted=False)
    except ValueError:
        return 'EXPECTED_OLD_IMAGE_REJECTION'
    raise RuntimeError('old image unexpectedly admitted as finalized R2')


def preflight(store, out):
    cli.require(not out.exists(), 'preserve reader qualification')
    for n in FILES: store.checked(out/n)
    for p in SOURCES: store.checked(out/'source'/p.relative_to(ROOT))


def worker(store, out):
    cli.require(base.in_job(), 'owned qualification worker required')
    plan = store.read(out/'plan.json')
    cli.require(plan['out'] == str(out) and plan['inputs'] == [cli.record(p) for p in SOURCES], 'source/plan drift')
    cli.require(plan['native_history_approved'] == str(base.HISTORY) and
                cli.record(base.JLINK/'JLink_x64.dll')['sha256'] == base.DLL_SHA, 'native scope/DLL drift')
    result = dict(result='FAILED', close_returned=False, reset_performed=False, target_payload_writes=0,
                  finalized_r2_admission=False, native_r2_route_validated=False)
    dap, port, observation = None, None, None
    started = time.monotonic()
    with (out/'events.jsonl').open('x', encoding='utf-8') as events, (out/'callbacks.log').open('xb') as callbacks:
        def emit(event, **fields):
            events.write(json.dumps(dict(time=cli.now(), event=event, **fields))+'\n'); events.flush()
        try:
            cli.require(not base.native_presence()['debugger_processes'], 'other debugger present')
            with os.add_dll_directory(str(base.JLINK)):
                sdk = base.guarded(ctypes.CDLL, str(base.JLINK/'JLink_x64.dll'))
                dap = base.Dap(sdk, out/'sdk.log', out/'project.jlink', callbacks)
                observation = base.Observation(dap, emit, seconds=270)
                observation.connect()
                # Current old-App session is idle; no OTA/ISR ownership transition may be active.
                for _ in range(2):
                    state = int.from_bytes(dap.read(0x20052a54, 4), 'little')
                    isr = int.from_bytes(dap.read(0x20052b34, 4), 'little')
                    cli.require(state & 255 == 0 and isr & 255 == 0, 'active old-App OTA owner')
                generation = plan['connection_generation']
                def lease():
                    return dict(owned=dap.ready, connection_generation=generation, boot_generation=0, reset_seen=False)
                port = Reader(dap, emit, lease, connection_generation=generation, boot_generation=0, seconds=240)
                original = (ROOT/'.cache/p34-native-image1/app-readback.bin').read_bytes()
                raw, reads = capture_old(port, original)
                result['capture'] = store.raw(out/'readback.bin', raw)
                result['tail'] = store.raw(out/'tail-unclassified.bin', raw[len(original):])
                result['reads'] = reads
                result['offline_finalized_policy'] = reject_finalized(raw)
                state = port.owner()
                cli.require(not state['reset_seen'] and port.read(capture.VTOR, 4, 10) == (0x08010000).to_bytes(4, 'little'),
                            'post-capture old-App epoch changed')
                for _ in range(2):
                    state = int.from_bytes(dap.read(0x20052a54, 4), 'little')
                    isr = int.from_bytes(dap.read(0x20052b34, 4), 'little')
                    cli.require(state & 255 == 0 and isr & 255 == 0, 'post-capture OTA owner changed')
                terminal = port.owner()
                cli.require(terminal['owned'] and not terminal['reset_seen'], 'terminal owner/reset changed')
                observation._check()
                result['result'] = 'EXTENDED_OLD_APP_READ_FINALIZED_REJECTED'
        except BaseException as error:
            result['error'] = type(error).__name__+': '+str(error)
        finally:
            if port: result['reader'] = dict(error=port.error, reset_seen=port.reset_seen, api_reads=port.api_reads,
                owner_samples=port.owner_samples, target_chunks=port.target_chunks, target_words=port.target_words)
            try:
                if observation: observation.close()
                elif dap: dap.close()
            except BaseException as error:
                result.update(result='FAILED', close_error=type(error).__name__+': '+str(error))
            result['close_returned'] = bool(dap and dap.close_returned)
            if dap: result['dap'] = dap.metadata
            result['elapsed_seconds'] = time.monotonic()-started
            store.write(out/'worker.json', result)
    print(json.dumps(result))
    return 0 if result['result'] == 'EXTENDED_OLD_APP_READ_FINALIZED_REJECTED' and result['close_returned'] else 1


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action', choices=('selftest', 'qualify', 'worker'))
    parser.add_argument('--output-dir', type=Path, required=True)
    parser.add_argument('--tests', type=Path)
    parser.add_argument('--native-history-approved', type=Path)
    args = parser.parse_args()
    cli.require(Path.cwd() == ROOT and sys.flags.isolated and sys.flags.no_site and sys.dont_write_bytecode, 'isolated root required')
    store = cli.Store(ROOT); out = store.checked(args.output_dir)
    if args.action == 'worker': return worker(store, out)
    preflight(store, out); inputs = [cli.record(p) for p in SOURCES]
    if args.action == 'qualify':
        tests = store.read(args.tests)
        cli.require(tests['result'] == 'FINALIZED_DEVICE_MODEL_PASS' and tests['inputs'] == inputs, 'bound model tests required')
        cli.require(args.native_history_approved == base.HISTORY, 'exact native history scope required')
        old = store.read(ROOT/'.cache/p34-reconciled-resume1/parent.json')
        cli.require(old['exit'] == 0 and not old['timeout'], 'original resume not closed normally')
        before = base.history(store)
    env = host.environment(store, out)
    for p in SOURCES: store.raw(out/'source'/p.relative_to(ROOT), p.read_bytes())
    if args.action == 'selftest':
        env['P34_TEST_OUT'] = str(out)
        log = host.command(store, out, 'tests', [sys.executable, '-I', '-S', '-B', '-X', 'utf8',
                           ROOT/'tests/boot/test_p34_finalized_reader_device.py', '-v'], env, 120)
        match = re.search(rb'Ran (\d+) tests? in .*\r?\n\r?\nOK\b', log)
        cli.require(match and inputs == [cli.record(p) for p in SOURCES], 'tests/source drift')
        store.write(out/'result.json', dict(result='FINALIZED_DEVICE_MODEL_PASS', tests=int(match[1]), inputs=inputs, hardware=False))
        print('FINALIZED_DEVICE_MODEL_PASS', int(match[1])); return 0
    store.write(out/'plan.json', dict(out=str(out), inputs=inputs, tests=cli.record(args.tests), before_history=before,
        native_history_approved=str(base.HISTORY), connection_generation='finalized-read-'+out.name,
        parent_seconds=300, observation_seconds=270, reader_seconds=240, native_call_seconds=5,
        scope='No target data writes: 619580B read, old30275 prefix617588B, unclassified1992B tail, offline finalized rejection'))
    result = base.owned_run(store, out, [SELF, 'worker', '--output-dir', out], env, timeout=300)
    result['after_history'] = base.history(store); result['presence_after'] = base.native_presence()
    store.write(out/'parent.json', result); print(json.dumps(result))
    return 0 if result['exit'] == 0 and not result['timeout'] else 1


if __name__ == '__main__': raise SystemExit(main())
