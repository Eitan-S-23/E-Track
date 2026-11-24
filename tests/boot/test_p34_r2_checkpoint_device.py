import copy
import ctypes
import io
from pathlib import Path
import sys
import unittest
from unittest import mock

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'Tools/ota'))
sys.path.insert(0, str(ROOT / 'tests/boot'))
import p34_r2_checkpoint_device as run
from test_p34_online_log_probe import LoggingSDK
from test_p34_install_bridges import Buffer
from test_p34_mutation_audit import record
from test_p34_recovery_ports import Clock, BOOT
from test_p34_r2_checkpoint import MAP


class BinaryBuffer(Buffer):
    def open(self, mode='r', **kwargs):
        return io.BytesIO(self.data.encode('utf-8')) if 'b' in mode else io.StringIO(self.data)


class Native(LoggingSDK):
    def __init__(self, paths, clock, image, fault):
        super().__init__(paths, fault)
        self.clock, self.image = clock, image
        self.special = set()
        self.reset_injected = False

    def log(self, text):
        if self.path is not None and not (self.fault == 'new-empty' and self.path is self.paths[1]):
            self.path.append(text)

    def __getattr__(self, name):
        function = super().__getattr__(name)
        if name == 'JLINKARM_CORESIGHT_ReadAPDPReg' and name not in self.special:
            old = function.callback
            def invoke(index, ap, pointer):
                if (index, ap, self.bank) != (3, 1, 0):
                    return old(index, ap, pointer)
                self.target_accesses += 1
                self.clock.value += .00001
                address = self.tar
                h = run.health
                if 0x08010000 <= address < 0x08010000 + len(self.image):
                    offset = address - 0x08010000
                    value = int.from_bytes(self.image[offset:offset + 4], 'little')
                    if self.fault == 'image' and offset == 0: value ^= 1
                elif 0x08000000 <= address < 0x08010000:
                    offset = address - 0x08000000
                    value = int.from_bytes(BOOT[offset:offset + 4], 'little')
                else:
                    values = (30000, 30, 1000, 0, int(self.clock.value * 100),
                              int(self.clock.value * 100), 0, 1, 1)
                    memory = {h.DHCSR: 0, h.VTOR: h.RUNTIME, h.CFSR: 0, h.HFSR: 0,
                        h.FLAGS: 0x010104, h.SD: 1, h.DIAG: 1, h.FAULT: 0,
                        h.TICK: int(self.clock.value * 1000),
                        **{h.HEALTH + 4 * i: v for i, v in enumerate(values)}}
                    value = memory[address]
                if self.fault == 'reset' and address == h.DHCSR and not self.reset_injected:
                    value |= 0x02000000
                    self.reset_injected = True
                self.tar += 4
                ctypes.cast(pointer, ctypes.POINTER(ctypes.c_uint32))[0] = value
                self.log(f'JLINK_CORESIGHT_ReadAPDPReg(AP reg 0x03)\nValue=0x{value:08X}\n')
                self.log('T0000 000:000.000 - 0.1ms returns 0\n')
                return 0
            function.callback = invoke
            self.special.add(name)
        return function


def session(name='r2-a.bin', fault=None, dp=0x40):
    image = (ROOT / '.cache/p34-recovery-sources1' / name).read_bytes()
    clock = Clock()
    paths = [BinaryBuffer(n, '') for n in run.LOGS]
    native = Native(paths, clock, image, fault)
    native.dp = dp
    rows, initial, saved = [], [], {}
    def persist(event, **fields): rows.append(dict(event=event, **fields))
    def collect(event, **fields):
        persist(event, **fields)
        initial.append(dict(event=event, **fields))
    def archive(name, raw):
        if fault == 'archive': raise OSError('archive failure')
        if name in saved: raise AssertionError('replayed archive')
        saved[name] = raw
    with mock.patch('recovery_entry.native_probe.guarded', side_effect=lambda f, *a, **k: f(*a)):
        dap = run.base.Dap(native, paths[0], ROOT / '.cache/model-only.jlink', io.BytesIO())
        dap.sdk = run.JournalSDK(native, collect, clock=clock)
        observation = run.base.Observation(dap, collect, seconds=600, clock=clock)
        result = run.execute(dap, observation, persist, initial, paths, record, lambda: 900-clock.value,
            archive, image, BOOT, MAP, connection_generation='one-native-test', clock=clock,
            sleep=clock.sleep, guard=lambda f, *a, **k: f(*a))
    return result, rows, paths, native, saved


class Tests(unittest.TestCase):
    def assert_one_close(self, native):
        self.assertEqual(sum(name == 'JLINKARM_Close' for name, _ in native.calls), 1)
        forbidden = {'JLINKARM_Connect', 'JLINKARM_ReadMemEx', 'JLINKARM_Reset',
                     'JLINKARM_Halt', 'JLINKARM_Go'}
        self.assertFalse(forbidden & {name for name, _ in native.calls})
        self.assertFalse(any(name == 'JLINKARM_CORESIGHT_WriteAPDPReg' and args[:2] == (3, 1)
                             for name, args in native.calls))

    def test_real_connect_complete_checkpoint_restore_close_and_offline_trace(self):
        for name, version, dp in (('r2-a.bin', 30276, 0x40), ('r2-b.bin', 30277, 0xf0000040)):
            result, rows, paths, native, saved = session(name, dp=dp)
            self.assertEqual(result['result'], 'R2_CHECKPOINT_NATIVE_CLOSED', result)
            self.assertEqual(result['checkpoint']['version'], version)
            self.assertEqual(saved, dict(app=native.image, boot=BOOT))
            self.assertEqual((native.dp, native.tar, native.csw), (dp, 0xe000ef38, 0x23000052))
            self.assert_one_close(native)
            trace = run.audit_trace(paths, rows, result['dap'], record, True)
            self.assertEqual((trace['target_writes'], trace['native_close']), (0, 1))
            self.assertEqual(trace['logs'], result['logs'])
            self.assertFalse(result['ota_ready'])
            if version == 30276:
                self.check_corruption_rejected(result, rows, paths)

    def check_corruption_rejected(self, result, rows, paths):
        changed = copy.deepcopy(rows)
        head = next(r for r in changed if r['event'] == 'online-log-head-verified')
        head['record']['sha256'] = '0' * 64
        with self.assertRaisesRegex(RuntimeError, 'head changed'):
            run.audit_trace(paths, changed, result['dap'], record, True)
        # Reject absent actual native close without trusting the reported result.
        with self.assertRaises((ValueError, RuntimeError)):
            run.audit_trace(paths, rows, result['dap'], record, False)

    def test_early_failures_close_once_and_never_report_a_checkpoint(self):
        for fault in ('new-empty', 'reset', 'image', 'archive'):
            result, _, _, native, _ = session(fault=fault)
            self.assertEqual(result['result'], 'FAILED', result)
            self.assertTrue(result['close_returned'])
            self.assertNotIn('checkpoint', result)
            self.assert_one_close(native)

    def test_uncertain_close_is_not_retried_or_promoted(self):
        result, _, _, native, _ = session(fault='close')
        self.assertEqual(result['result'], 'FAILED')
        self.assertFalse(result['close_returned'])
        self.assertIn('close_error', result)
        self.assertNotIn('native_close_audited', result)
        self.assert_one_close(native)


if __name__ == '__main__':
    unittest.main()
