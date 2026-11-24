import ctypes
from pathlib import Path
import sys
import unittest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT/'Tools/ota'))
sys.path.insert(0, str(ROOT/'tests/boot'))
from recovery_confirm.ap_journal import JournalSDK
from recovery_confirm.mutation_audit import SealedGate
from recovery_confirm.online_log import OnlineLog
from recovery_confirm.native_io import Words
from test_p34_mutation_audit import MemoryPath, record, META


class Native:
    def __init__(self, paths):
        self.paths, self.index = paths, 0
        self.tar, self.csw, self.dp = 0, META['ap_csw'], 0xf0000040
        self.memory, self.switches = {}, 0
        self.fault = None
        self.hook = lambda:None

    def log(self, text):
        if self.index and self.fault == 'new-blank': return
        if self.index and self.fault == 'new-partial' and 'returns' in text: return
        if self.index and self.fault == 'new-value': text = text.replace('Value=0xF0000040', 'Value=0xF0000000')
        self.paths[self.index].data += text

    def JLINKARM_CORESIGHT_WriteAPDPReg(self, index, ap, value):
        self.log(f'JLINK_CORESIGHT_WriteAPDPReg({"AP" if ap else "DP"} reg 0x{index:02X}, 0x{value:08X})\n')
        if (index, ap) == (1, 1): self.tar = value
        elif (index, ap) == (1, 0): self.dp = value
        elif (index, ap) == (3, 1):
            self.memory[self.tar] = value
            self.tar += 4
        else: raise AssertionError((index, ap))
        self.log('T0000 000:000.000 - 0.1ms returns 0\n')
        return 0

    def JLINKARM_CORESIGHT_ReadAPDPReg(self, index, ap, out):
        if (index, ap) == (1, 0): value = self.dp
        elif (index, ap) == (0, 1): value = self.csw
        elif (index, ap) == (1, 1): value = self.tar
        elif (index, ap) == (3, 1):
            value = self.memory[self.tar]
            self.tar += 4
        else: raise AssertionError((index, ap))
        self.log(f'JLINK_CORESIGHT_ReadAPDPReg({"AP" if ap else "DP"} reg 0x{index:02X})\nValue=0x{value:08X}\n')
        self.log('T0000 000:000.000 - 0.1ms returns 0\n')
        ctypes.cast(out, ctypes.POINTER(ctypes.c_uint32))[0] = value
        return 0

    def JLINKARM_SetLogFile(self, path):
        self.hook()
        self.switches += 1
        self.log('JLINK_SetLogFile()\n')
        self.log('T0000 000:000.100 Closed\n')
        self.index += 1
        assert path == str(self.paths[self.index]).encode('ascii')
        if self.fault == 'blank': self.paths[self.index-1].data = '\n'
        if self.fault == 'state': self.dp ^= 0x40
        if self.fault == 'delivered': raise OSError('switch delivered, return failed')

    def JLINKARM_Close(self):
        self.log('JLINK_Close()\nT0000 000:000.100 Closed\n')


class Dap:
    ready = True
    callback_error = None
    word_csw = META['ap_csw']
    close_returned = False
    def __init__(self, sdk): self.sdk = sdk
    def _call(self, name, *args): return getattr(self.sdk, name)(*args)
    def _read_reg(self, index, ap):
        out = ctypes.c_uint32()
        self._call('JLINKARM_CORESIGHT_ReadAPDPReg', index, ap, ctypes.byref(out))
        return out.value
    def close(self):
        self._call('JLINKARM_CORESIGHT_WriteAPDPReg', 1, 1, META['original_tar'])
        self._read_reg(1, 1)
        self._read_reg(0, 1)
        self._call('JLINKARM_CORESIGHT_WriteAPDPReg', 1, 0, 0x40)
        self._read_reg(1, 0)
        self._call('JLINKARM_Close')
        self.close_returned = True
        self.ready = False


class Tests(unittest.TestCase):
    def make(self, fault=None, count=2):
        paths = [MemoryPath(f'log-{i}.txt', '') for i in range(count)]
        native = Native(paths)
        dap = Dap(JournalSDK(native, lambda *a,**k:None))
        gate = SealedGate(paths, META, record)
        rows = []
        log = OnlineLog(dap, gate, lambda e,**kw:rows.append(dict(event=e,**kw)), lambda:300)
        native.fault = fault
        port = Words(dap, log.emit, reads={0x08010000},
                     write_allowed=lambda a,v:log.target_allowed() and (a,v)==(0x08010000,123),
                     seconds=300, guard=lambda f,*a,**k:f(*a))
        return native, dap, gate, log, port, rows

    def test_real_words_journal_switch_and_closed_file_gate_compose(self):
        native, dap, gate, log, port, _ = self.make()
        port.write32(0x08010000, 123)
        native.hook = lambda:self.assertFalse(log.target_allowed())
        result = log.switch(read_allowed=lambda _:False, expected_stores=[(0x08010000,123)])
        self.assertEqual(result['target_writes'], 1)
        self.assertTrue(log.target_allowed())
        self.assertEqual(native.switches, 1)
        log.prepare_close()
        self.assertFalse(log.target_allowed())
        dap.close()
        result = log.finish(read_allowed=lambda _:False, expected_stores=[], expected_dp_writes=[0x40])
        self.assertEqual(result['native_close_completed'], 1)
        self.assertEqual(log.mode, 'FINISHED')
        self.assertEqual(len(gate.records), 2)

    def test_switch_failures_disable_next_target_write_without_retry_or_close(self):
        for fault in ('blank', 'state', 'delivered'):
            native, dap, _, log, port, _ = self.make(fault)
            port.write32(0x08010000,123)
            with self.assertRaises((ValueError,OSError)):
                log.switch(read_allowed=lambda _:False, expected_stores=[(0x08010000,123)])
            self.assertFalse(log.target_allowed())
            before = dict(native.memory)
            with self.assertRaises(ValueError): port.write32(0x08010000,123)
            self.assertEqual(native.memory, before)
            with self.assertRaises(ValueError): log.switch(read_allowed=lambda _:False, expected_stores=[])
            self.assertEqual(native.switches, 1)
            self.assertFalse(dap.close_returned)

    def test_partial_word_or_native_busy_cannot_switch_log(self):
        for fault in ('word', 'native'):
            native, dap, _, log, _, _ = self.make()
            if fault == 'word': log.emit('recovery-chunk-read-attempt', address=0x08010000, bytes=4)
            else: dap.sdk.busy = True
            with self.assertRaises(ValueError): log.switch(read_allowed=lambda _:False, expected_stores=[])
            self.assertEqual(native.switches, 0)
            self.assertFalse(log.target_allowed())

    def test_clock_budget_and_persistence_failures_are_latched(self):
        for fault in ('clock', 'left', 'persist'):
            native, _, _, log, _, _ = self.make()
            if fault == 'clock': log.clock = lambda:float('nan')
            if fault == 'left': log.left = lambda:0
            if fault == 'persist':
                def fail(*a, **k): raise OSError('host journal full')
                log.persist = fail
            with self.assertRaises((ValueError,OSError)):
                log.switch(read_allowed=lambda _:False, expected_stores=[])
            self.assertFalse(log.target_allowed())
            self.assertEqual(native.switches, 0)

    def test_final_return_is_read_from_actual_dap_not_caller_constant(self):
        _, dap, _, log, _, _ = self.make(count=1)
        log.prepare_close()
        self.assertFalse(log.target_allowed())
        with self.assertRaises(ValueError):
            log.finish(read_allowed=lambda _:False, expected_stores=[], expected_dp_writes=[])
        self.assertFalse(dap.close_returned)
        self.assertEqual(log.mode, 'FAILED')

    def test_only_new_log_loss_or_mismatch_cannot_open_next_target_admission(self):
        for fault in ('new-blank', 'new-partial', 'new-value'):
            native, _, gate, log, port, _ = self.make(fault)
            port.write32(0x08010000,123)
            with self.assertRaises(ValueError):
                log.switch(read_allowed=lambda _:False, expected_stores=[(0x08010000,123)])
            self.assertEqual(len(gate.records), 1)
            self.assertFalse(log.target_allowed())
            self.assertFalse(gate.active)
            self.assertEqual(native.switches, 1)
            original = dict(native.memory)
            with self.assertRaises(ValueError): port.write32(0x08010000,123)
            self.assertEqual(native.memory, original)

    def test_normal_close_rejects_inflight_frames_and_missing_allowance_before_native_calls(self):
        for fault in ('chunk', 'word', 'ap', 'budget'):
            native, dap, _, log, _, _ = self.make(count=1)
            if fault == 'chunk': log.emit('recovery-chunk-read-attempt', address=0x08010000, bytes=4)
            if fault == 'word': log.emit('recovery-word-write-attempt', address=0x08010000, value=123)
            if fault == 'ap': log.emit('ap-call-attempt', sequence=1, operation='read', ap=1, index=3, value=None)
            if fault == 'budget': log.left = lambda:59
            with self.assertRaises(ValueError): log.prepare_close()
            self.assertFalse(dap.close_returned)
            self.assertEqual(native.paths[0].data, '')
            self.assertFalse(log.target_allowed())


if __name__ == '__main__': unittest.main()
