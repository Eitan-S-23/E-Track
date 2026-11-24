import ctypes
import copy
import io
from pathlib import Path
import sys
import unittest
from unittest import mock

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'Tools/ota'))
sys.path.insert(0, str(ROOT / 'tests/boot'))
import p34_boot16_probe as run
from test_p34_boot16_entry import SDK, IMAGE, MAP, Clock
from test_p34_online_log_probe import LoggingSDK
from test_p34_r2_checkpoint_device import BinaryBuffer
from test_p34_mutation_audit import record


class Native(LoggingSDK):
    def __init__(self, paths, clock, fault):
        super().__init__(paths, fault)
        self.model, self.clock, self.special = SDK(clock), clock, set()
        self.problem = fault
        if fault in ('release', 'pause-restore'): self.model.fault = fault
        if fault == 'foreign': self.model.memory[run.entry.COMP] = 1

    def __getattr__(self, name):
        function = super().__getattr__(name)
        if name == 'JLINKARM_SetLogFile' and name not in self.special:
            old = function.callback
            def switch(*args):
                result = old(*args)
                if self.problem == 'release-audit' and self.path is self.paths[3]:
                    self.paths[2].data = '\n'
                return result
            function.callback = switch
            self.special.add(name)
        if name in self.special or name not in ('JLINKARM_CORESIGHT_ReadAPDPReg', 'JLINKARM_CORESIGHT_WriteAPDPReg'):
            return function
        old = function.callback
        def invoke(index, ap, value):
            if (index, ap, self.bank) != (3, 1, 0): return old(index, ap, value)
            self.target_accesses += 1
            h = run.entry.health
            if not self.model.memory[h.DHCSR] & 0x20000:
                values = (30000, 30, 1000, 0, int(self.clock.value*100), int(self.clock.value*100), 0, 1, 1)
                self.model.memory.update({h.TICK: int(self.clock.value*1000), h.SD: 1, h.DIAG: 1, h.FAULT: 0})
                self.model.memory.update({h.HEALTH+4*i: v for i, v in enumerate(values)})
            self.model.tar = self.tar
            if name.endswith('ReadAPDPReg'):
                result = self.model.JLINKARM_CORESIGHT_ReadAPDPReg(index, ap, value)
                observed = ctypes.cast(value, ctypes.POINTER(ctypes.c_uint32))[0]
                self.log(f'JLINK_CORESIGHT_ReadAPDPReg(AP reg 0x03)\nValue=0x{observed:08X}\n')
            else:
                result = self.model.JLINKARM_CORESIGHT_WriteAPDPReg(index, ap, value)
                if self.problem == 'still-halted' and self.tar == run.entry.DHCSR:
                    self.model.memory[run.entry.DHCSR] = 0x30003
                self.log(f'JLINK_CORESIGHT_WriteAPDPReg(AP reg 0x03, 0x{value:08X})\n')
            self.tar = self.model.tar
            self.log(f'T0000 000:000.000 - 0.1ms returns {result}\n')
            return result
        function.callback = invoke
        self.special.add(name)
        return function


def session(fault=None):
    clock = Clock()
    paths = [BinaryBuffer(name, '') for name in run.LOGS]
    native = Native(paths, clock, fault)
    rows, initial = [], []
    def persist(event, **fields): rows.append(dict(event=event, **fields))
    def collect(event, **fields):
        persist(event, **fields)
        initial.append(dict(event=event, **fields))
    with mock.patch('recovery_entry.native_probe.guarded', side_effect=lambda f, *a, **k: f(*a)):
        dap = run.base.Dap(native, paths[0], ROOT / '.cache/model-only.jlink', io.BytesIO())
        dap.sdk = run.JournalSDK(native, collect, clock=clock)
        observer = run.base.Observation(dap, collect, seconds=540, clock=clock)
        result = run.execute(dap, observer, persist, initial, paths, record, lambda: 600-clock.value,
            IMAGE, MAP, clock=clock, sleep=clock.sleep, guard=lambda f, *a, **k: f(*a))
    return result, native, paths, rows


class Tests(unittest.TestCase):
    def test_complete_real_words_logs_health_and_native_close(self):
        result, native, paths, rows = session()
        self.assertEqual(result['result'], 'BOOT16_R2_ENTRY_QUALIFIED_CLOSED', result)
        self.assertEqual(len(result['logs']), 6)
        self.assertGreaterEqual(result['health']['seconds'], 30)
        self.assertEqual(native.model.memory[run.entry.PAUSE], 4)
        self.assertFalse(result['reset_performed'])
        self.assertFalse(result['boot_written'])
        self.assertEqual(sum(name == 'JLINKARM_Close' for name, _ in native.calls), 1)
        self.assertEqual([v for a, v in native.model.writes if a == run.entry.DHCSR], [0xa05f0001])
        self.assertTrue(all(a in (run.entry.PAUSE, run.entry.COMP, run.entry.DCRSR,
            run.entry.DHCSR, run.entry.REGS['dfsr']) for a, _ in native.model.writes))
        trace = run.audit_trace(paths, rows, result['dap'], record, True)
        self.assertEqual(trace['target_writes'], 18)
        self.assertEqual(trace['logs'], result['logs'])

    def test_early_failure_never_attempts_target_mutation(self):
        for fault in ('foreign', 'new-empty'):
            result, native, _, _ = session(fault)
            self.assertEqual(result['result'], 'FAILED')
            self.assertFalse(native.model.writes)
            self.assertEqual(sum(name == 'JLINKARM_Close' for name, _ in native.calls), 1)

    def test_uncertain_release_pause_and_close_never_repeat(self):
        for fault in ('release', 'pause-restore', 'close'):
            result, native, _, _ = session(fault)
            self.assertEqual(result['result'], 'FAILED', result)
            self.assertEqual([v for a, v in native.model.writes if a == run.entry.DHCSR], [0xa05f0001])
            self.assertEqual(sum(name == 'JLINKARM_Close' for name, _ in native.calls), 1)
            self.assertFalse(result.get('native_close_audited', False))

    def test_post_release_unresolved_state_retains_logical_debug_requests(self):
        for fault in ('still-halted', 'release-audit', 'pause-restore'):
            result, native, _, _ = session(fault)
            self.assertEqual(result['result'], 'FAILED')
            self.assertTrue(result['release_returned'])
            self.assertTrue(result['dap']['dp_restore_deferred_for_halt'])
            self.assertEqual(native.dp, 0xf0000040)
            self.assertEqual([v for a, v in native.model.writes if a == run.entry.DHCSR], [0xa05f0001])
            self.assertEqual(sum(name == 'JLINKARM_Close' for name, _ in native.calls), 1)

    def test_offline_audit_rejects_head_mutation_and_missing_native_close(self):
        result, _, paths, rows = session()
        changed = copy.deepcopy(rows)
        head = next(row for row in changed if row['event'] == 'online-log-head-verified')
        head['record']['sha256'] = '0'*64
        with self.assertRaises(RuntimeError): run.audit_trace(paths, changed, result['dap'], record, True)
        with self.assertRaises(ValueError): run.audit_trace(paths, rows, result['dap'], record, False)


if __name__ == '__main__': unittest.main()
