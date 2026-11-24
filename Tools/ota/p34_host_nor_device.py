"""One finite, recovery-only provisioning transaction with durable preservation."""
import argparse
import ctypes
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import sys
import time

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT/'Tools/ota'))
import p34_host_nor_mapped as prior
import p34_host_writer as writer_build
from recovery_entry import host_nor_device as nd, host_writer as hw, host_bcb as hb
from recovery_entry.control_probe import Control

base, cli, host = prior.base, prior.cli, prior.host
SELF = Path(__file__).resolve()
REGIONS = {'candidate-backup': (0, 0x200000), 'tail': (0x299000, 0x300000),
           'staging': (0x300000, 0x500000), 'recovery': (0x200000, 0x299000)}
BCB_SHA = '72b8eb65d7a99b3c0a085b225dde0b6d7d680015b874366a97f1c36cbb89e049'
SOURCES = list(dict.fromkeys([*prior.SOURCES, *writer_build.SOURCES, SELF, *(ROOT/n for n in (
    'Tools/ota/recovery_entry/host_nor_device.py', 'Tools/ota/recovery_entry/nor_profile.py',
    'Tools/ota/recovery_entry/host_bcb.py', 'tests/boot/test_p34_host_nor_device.py',
    '.cache/p34-host-writer-test2/result.json', '.cache/p34-host-writer-test2/writer.dll',
    '.cache/p34-host-bcb-test2/result.json', '.cache/p34-host-bcb-test2/bcb-reader.dll',
    '.cache/p34-host-bcb1/capture-raw.bin', '.cache/p34-host-bcb1/worker.json',
    '.cache/p34-nor-profile1/result.json', '.cache/p34-host-nor-mapped1/worker.json',
    '.cache/p34-host-nor-mapped1/parent.json', '.cache/p34-host-nor-read1/sfdp.bin',
    '.cache/p34-native-acquire1/boot-readback.bin', '.cache/p34-native-image1/app-readback.bin',
    '.cache/p34-native-acquire1/parent.json', '.cache/p34-native-image1/parent.json',
    '.cache/p34-recovery-admission2/result.json'))]))
FILES = (*prior.FILES, 'progress.json', 'preimages.json', 'bcb-before.bin', 'bcb-after.bin',
         'progress.json.tmp',
         'boot-after.bin', 'app-after.bin', 'recovery-physical-slot.bin', 'admission.log', 'admission.json',
         *(f'{side}-{name}.bin' for side in ('before', 'after') for name in REGIONS))


class LongObservation(base.Observation):
    def __init__(self, backend, emit, *, clock=time.monotonic):
        # Reuse the reviewed connection/read/close policy, with a distinct finite
        # lifetime. The historical read-only constructor's 600s cap is unchanged.
        self.backend, self.emit, self.clock = backend, emit, clock
        self.seconds, self.started = 13800, None
        self.consumed = self.open_attempted = self.connected = self.closed = False


def validate_preimages(store, out, receipt):
    cli.require(receipt['result'] == 'RECOVERY_PREIMAGES_DURABLE' and
                receipt['recovery_range'] == [hw.LOW, hw.HIGH] and receipt['bcb_pair_sha256'] == BCB_SHA and
                receipt['source_sha256'] == hw.PINNED and set(receipt['regions']) == set(REGIONS),
                'preimage receipt identity/ranges changed')
    for name, (start, end) in REGIONS.items():
        record = receipt['regions'][name]
        expected = store.checked(out/('before-'+name+'.bin'))
        cli.require(record['path'] == str(expected) and record['bytes'] == end-start and
                    cli.record(expected) == record, 'durable preimage binding failed: '+name)


def preflight(store, out):
    cli.require(not out.exists(), 'preserve provisioning evidence')
    for n in FILES: store.checked(out/n)
    for p in SOURCES: store.checked(out/'source'/p.relative_to(ROOT))


def snapshot(store, out):
    inputs = [cli.record(p) for p in SOURCES]; env = host.environment(store, out)
    for p in SOURCES: store.raw(out/'source'/p.relative_to(ROOT), p.read_bytes())
    return inputs, env


def bcb(store, out, name, function, control, emit):
    raw = control.media()['raw']
    pins = hb.Pins(control, raw, emit); pins.verify(idle=True)
    started = time.monotonic(); time.sleep(.006)
    cli.require(time.monotonic()-started >= .005, 'EEPROM settlement wait')
    value = hb.capture(function, pins, seconds=300)
    data = bytes.fromhex(value['raw_hex']); record = store.raw(out/(name+'.bin'), data)
    cli.require(value['result'] == 'HOST_BCB_CAPTURED' and data ==
                (ROOT/'.cache/p34-host-bcb1/capture-raw.bin').read_bytes() and
                hashlib.sha256(data[:128]).hexdigest() == BCB_SHA, 'actual BCB changed or uncertain')
    pins.verify(idle=True)
    return dict(capture=value, raw=record)


def archive(store, out, name, start, end, read, progress):
    path = store.checked(out/(name+'.bin')); count = 0
    with path.open('xb') as stream:
        while start+count < end:
            take = min(4096, end-start-count)
            data = read(start+count, take)
            cli.require(isinstance(data, bytes) and len(data) == take, 'archive read short')
            stream.write(data); count += take
            if count % 65536 == 0 or start+count == end:
                stream.flush()
                progress(name, count, end-start)
        stream.flush(); os.fsync(stream.fileno())
    record = cli.record(path)
    cli.require(record['bytes'] == end-start, 'archive size mismatch')
    return record


def worker(store, out):
    cli.require(base.in_job(), 'owned provisioning worker required')
    plan = store.read(out/'plan.json')
    cli.require(plan['inputs'] == [cli.record(p) for p in SOURCES] and plan['out'] == str(out), 'source/plan drift')
    cli.require(plan['native_history_approved'] == str(base.HISTORY), 'history scope mismatch')
    cli.require(plan['scope'] == [hw.LOW, hw.HIGH] and plan['version'] == 30276, 'authorization scope mismatch')
    cli.require(cli.record(base.JLINK/'JLink_x64.dll')['sha256'] == base.DLL_SHA, 'SDK drift')
    for name in FILES: store.checked(out/name)
    for key in ('writer', 'bcb_reader', 'validator'):
        cli.require(cli.record(store.checked(plan[key]['path'])) == plan[key], 'native artifact drift: '+key)
    result = dict(result='FAILED', close_returned=False, reset_performed=False, automatic_resume=False,
                  original_boot_app_replaced=False, eeprom_payload_bytes_written=0)
    control, dap, port, device = None, None, None, None
    started = time.monotonic()
    with (out/'events.jsonl').open('x', encoding='utf-8') as events, (out/'callbacks.log').open('xb') as callbacks:
        def emit(event, **fields):
            events.write(json.dumps(dict(time=cli.now(), event=event, **fields))+'\n'); events.flush()
        def progress(phase, count=0, total=0):
            cli.require(shutil.disk_usage(ROOT).free >= 10*1024**3, 'insufficient evidence disk reserve')
            cli.require(time.monotonic()-started < 13800, 'provisioning worker budget exhausted')
            store.write(out/'progress.json', dict(time=cli.now(), phase=phase, bytes=count, total=total,
                elapsed_seconds=time.monotonic()-started, mutations=0 if device is None else device.index), replace=True)
        try:
            presence = base.native_presence(); emit('presence', **presence)
            cli.require(not presence['debugger_processes'], 'another debugger present')
            cli.require(shutil.disk_usage(ROOT).free >= 20*1024**3, '20 GiB initial evidence reserve required')
            writer_dll = ctypes.CDLL(plan['writer']['path']); write_function = hw.bind(writer_dll)
            bcb_dll = ctypes.CDLL(plan['bcb_reader']['path']); bcb_function = hb.bind(bcb_dll)
            with os.add_dll_directory(str(base.JLINK)):
                sdk = base.guarded(ctypes.CDLL, str(base.JLINK/'JLink_x64.dll'))
                dap = base.Dap(sdk, out/'sdk.log', out/'project.jlink', callbacks)
                observation = LongObservation(dap, emit)
                image = (ROOT/'.cache/p34-native-image1/app-readback.bin').read_bytes()
                control = Control(dap, observation, emit, image[0x400:0x460], retained=True)
                observation.connect()
                original = store.read(ROOT/'.cache/p34-entry-wfi1/worker.json')
                result['before'] = control.observe_retained(original)
                cli.require(all(s['header_hex'] == image[0x400:0x460].hex()
                            for s in result['before']['state_samples']), 'original App identity changed')
                result['owners_before'] = prior.prior.prior.owners(control, dap, emit)
                progress('bcb-before')
                result['bcb_before'] = bcb(store, out, 'bcb-before', bcb_function, control, emit)
                source = (ROOT/'.cache/p34-recovery-sources1/r2-a.bin').read_bytes()
                port = nd.Port(control, emit); device = nd.Device(port, emit, source)
                result['profile'] = device.open()
                before = {}
                for name, (start, end) in REGIONS.items():
                    before[name] = archive(store, out, 'before-'+name, start, end, device.read, progress)
                cli.require((out/'before-candidate-backup.bin').read_bytes()[0x1000:0x2000] == image[:4096],
                            'candidate preimage disagrees with live App')
                cli.require((out/'before-recovery.bin').read_bytes()[:128] ==
                            (ROOT/'.cache/p34-host-nor-read1/recovery-prefix.bin').read_bytes(), 'recovery preimage changed')
                receipt = dict(result='RECOVERY_PREIMAGES_DURABLE', regions=before, recovery_range=[hw.LOW, hw.HIGH],
                               bcb_pair_sha256=BCB_SHA, source_sha256=hw.PINNED)
                store.write(out/'preimages.json', receipt)
                validate_preimages(store, out, store.read(out/'preimages.json'))
                cli.require(plan['inputs'] == [cli.record(p) for p in SOURCES], 'source drift before first erase')
                cli.require(time.monotonic()-started < 6000, 'insufficient write/verify headroom; no erase')
                result['owners_pre_erase'] = prior.prior.prior.owners(control, dap, emit)
                cli.require(control.context() == original['context'], 'pre-erase context changed')
                device.arm(store.read(out/'preimages.json'))
                progress('recovery-transaction')
                original_emit = device.emit
                def transaction_emit(event, **fields):
                    original_emit(event, **fields)
                    if event == 'nor-mutation-settled' and fields['index'] % 16 == 0:
                        progress('recovery-transaction', fields['index'], len(device.actions))
                device.emit = transaction_emit
                result['transaction'] = hw.run(write_function, device, source, seconds=13200)
                cli.require(result['transaction']['result'] == 'HOST_WRITER_CALLBACKS_COMPLETED',
                            'recovery transaction failed; preserve actual device/controller state')
                after = {}
                for name, (start, end) in REGIONS.items():
                    after[name] = archive(store, out, 'after-'+name, start, end, device.read, progress)
                    if name != 'recovery':
                        cli.require(after[name]['sha256'] == before[name]['sha256'], 'protected region changed: '+name)
                slot = (out/'after-recovery.bin').read_bytes()+(out/'after-tail.bin').read_bytes()
                result['slot'] = store.raw(out/'recovery-physical-slot.bin', slot)
                cli.require(slot[4096:4096+len(source)] == source, 'physical payload differs')
                log = host.command(store, out, 'admission',
                    [plan['validator']['path'], out/'recovery-physical-slot.bin', '0', '0'], dict(os.environ), 30)
                cli.require(b'RECOVERY_ADMISSION result=0' in log and b'version=30276' in log, 'original Boot admission failed')
                result['protected_before'], result['protected_after'] = before, after
                def internal_read(address, size):
                    data = bytearray()
                    while len(data) < size:
                        a = address+len(data); n = min(size-len(data), 1024-a % 1024)
                        data.extend(device.gate.call(port.internal, a, n))
                    return bytes(data)
                for name, address, baseline in (('boot', 0x08000000, '.cache/p34-native-acquire1/boot-readback.bin'),
                                                ('app', 0x08010000, '.cache/p34-native-image1/app-readback.bin')):
                    old = cli.record(ROOT/baseline)
                    record = archive(store, out, name+'-after', address, address+old['bytes'], internal_read, progress)
                    cli.require(record['sha256'] == old['sha256'], 'original internal flash changed: '+name)
                    result[name+'_after'] = record
                progress('bcb-after')
                result['bcb_after'] = bcb(store, out, 'bcb-after', bcb_function, control, emit)
                result['final_configuration'] = device.finish()
                result['owners_after'] = prior.prior.prior.owners(control, dap, emit)
                cli.require(control.context() == original['context'], 'final context changed')
                observation._check(); progress('verified-retained')
                result['result'] = 'RECOVERY_30276_VERIFIED_ORIGINAL_APP_HALTED'
        except BaseException as error:
            result['error'] = type(error).__name__+': '+str(error)
            if device and device.gate.error is None: device.gate.error = result['error']
        finally:
            if device: result['controller'] = dict(error=device.gate.error, mode=device.mode,
                mutations=device.index, restored=device.gate.restored, intent=repr(port.intent))
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
            result['elapsed_seconds'] = time.monotonic()-started
            store.write(out/'worker.json', result)
    print(json.dumps(result))
    return 0 if result['result'] == 'RECOVERY_30276_VERIFIED_ORIGINAL_APP_HALTED' and result['close_returned'] else 1


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action', choices=('selftest', 'rebuild', 'worker'))
    parser.add_argument('--output-dir', type=Path, required=True)
    parser.add_argument('--tests', type=Path)
    parser.add_argument('--native-history-approved', type=Path)
    args = parser.parse_args()
    cli.require(Path.cwd() == ROOT and sys.flags.isolated and sys.flags.no_site and sys.dont_write_bytecode,
                'isolated explicit root required')
    store = cli.Store(ROOT); out = store.checked(args.output_dir)
    if args.action == 'worker': return worker(store, out)
    preflight(store, out); inputs = [cli.record(p) for p in SOURCES]
    writer_tests = store.read(ROOT/'.cache/p34-host-writer-test2/result.json')
    cli.require(writer_tests['result'] == 'HOST_WRITER_DLL_TESTS_PASS' and
                writer_tests['inputs'] == [cli.record(p) for p in writer_build.SOURCES], 'writer DLL tests/source drift')
    writer = writer_tests['writer_dll']
    cli.require(cli.record(store.checked(writer['path'])) == writer, 'writer DLL drift')
    if args.action == 'selftest':
        inputs, env = snapshot(store, out); env['P34_TEST_OUT'] = str(out); env['P34_WRITER_DLL'] = writer['path']
        log = host.command(store, out, 'tests', [sys.executable, '-I', '-S', '-B', '-X', 'utf8',
                           ROOT/'tests/boot/test_p34_host_nor_device.py', '-v'], env, 180)
        match = re.search(rb'Ran (\d+) tests? in .*\r?\n\r?\nOK\b', log)
        cli.require(match and inputs == [cli.record(p) for p in SOURCES], 'device test/source drift')
        store.write(out/'result.json', dict(result='HOST_NOR_DEVICE_TESTS_PASS', tests=int(match[1]), inputs=inputs,
                    writer=writer, hardware=False))
        print('HOST_NOR_DEVICE_TESTS_PASS', int(match[1])); return 0
    cli.require(args.native_history_approved == base.HISTORY, 'exact native history scope required')
    tests = store.read(args.tests)
    cli.require(tests['result'] == 'HOST_NOR_DEVICE_TESTS_PASS' and tests['inputs'] == inputs and tests['writer'] == writer,
                'bound device tests required')
    parent = store.read(ROOT/'.cache/p34-host-nor-mapped1/parent.json')
    cli.require(parent['exit'] == 0 and not parent['timeout'], 'uncertain mapped predecessor')
    before = base.history(store); inputs, env = snapshot(store, out)
    bcb_reader = cli.record(ROOT/'.cache/p34-host-bcb-test2/bcb-reader.dll')
    cli.require(bcb_reader == store.read(ROOT/'.cache/p34-host-bcb-test2/result.json')['reader_dll'], 'BCB DLL drift')
    store.write(out/'plan.json', dict(action='rebuild', out=str(out), inputs=inputs, tests=cli.record(args.tests),
        writer=writer, bcb_reader=bcb_reader, validator=cli.record(ROOT/'.cache/p34-recovery-admission2/validator.exe'),
        native_history_approved=str(base.HISTORY), before_history=before, worker_seconds=14400,
        native_call_seconds=5, scope=[hw.LOW, hw.HIGH], version=30276))
    result = base.owned_run(store, out, [SELF, 'worker', '--output-dir', out], env, timeout=14400)
    result['after_history'] = base.history(store); result['presence_after'] = base.native_presence()
    store.write(out/'parent.json', result); print(json.dumps(result))
    return 0 if result['exit'] == 0 and not result['timeout'] else 1


if __name__ == '__main__': raise SystemExit(main())
