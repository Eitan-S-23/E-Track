import ctypes
import contextlib
import io
import json
import os
from pathlib import Path
import sys
import types
import unittest
from unittest import mock

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT/'Tools/ota'))
sys.path.insert(0, str(ROOT/'tests/boot'))
from recovery_entry import host_nor as hn, host_nor_device as dev, host_writer as hw
from recovery_entry.dap_probe import Dap
import test_p34_host_nor_mapped as previous

SOURCE = (ROOT/'.cache/p34-recovery-sources1/r2-a.bin').read_bytes()
RECEIPT = dict(result='RECOVERY_PREIMAGES_DURABLE', recovery_range=[hw.LOW, hw.HIGH],
               bcb_pair_sha256='72b8eb65d7a99b3c0a085b225dde0b6d7d680015b874366a97f1c36cbb89e049',
               source_sha256=hw.PINNED)


class Model(previous.prior.Model):
    def __init__(self):
        super().__init__()
        self.nor = bytearray(b'\xa5'*0x500000)
        self.sfdp = (ROOT/'.cache/p34-host-nor-read1/sfdp.bin').read_bytes()
        self.pending, self.physical, self.tx_words = None, [], []
        self.protected, self.keep_wel, self.wren_ignored, self.busy_forever = False, False, False, False
    def payload(self, opcode, address, size):
        return self.sfdp[address:address+size] if opcode == 0x5a else bytes(self.nor[address:address+size])
    def write(self, address, value):
        if address != hn.BASE+12 or value >> 24 not in (6, 2, 0x20):
            return super().write(address, value)
        self.operations += 1; self.writes.append((address, value)); self.registers[address] = value
        assert self.order == [0, 4, 8]
        self.order = []; opcode = value >> 24
        start, size = self.registers[hn.BASE], self.registers[hn.BASE+8]
        assert value & 0xffffff == 2
        self.registers[hn.CMDSTS] = 1
        if opcode == 6:
            assert start == size == 0 and self.registers[hn.BASE+4] == 0x1000000
            if not self.wren_ignored: self.sr1 = 2
        else:
            assert self.sr1 == 2 and self.registers[hn.BASE+4] == 0x1000003
            hw.scope(start, 4096 if opcode == 0x20 else size)
            if opcode == 0x20:
                assert start % 4096 == size == 0
                if not self.protected: self.nor[start:start+4096] = b'\xff'*4096
                self.physical.append(('erase', start, 4096))
                self.sr1 = 3 if self.busy_forever else (2 if self.keep_wel else 0)
            else:
                assert 0 < size <= 256 and start % 256+size <= 256
                self.pending = (start, size, bytearray())
                self.registers[hn.CMDSTS] = 0
    def tx_word(self, value):
        assert self.pending is not None
        address, size, data = self.pending
        self.tx_words.append(value); data.extend(value.to_bytes(4, 'little'))
        assert len(data) <= size
        if len(data) == size:
            if not self.protected:
                for i, b in enumerate(data): self.nor[address+i] &= b
            self.physical.append(('program', address, size))
            self.pending = None; self.registers[hn.CMDSTS] = 1
            self.sr1 = 3 if self.busy_forever else (2 if self.keep_wel else 0)


class DirectPort(dev.Port):
    def __init__(self, model):
        self.m = model; self.emit = lambda *a, **k: None
        self.intent, self.intent_phase, self.tx_remaining, self.tar = None, 0, 0, 0
        self.dap = types.SimpleNamespace(_power_ready=lambda: 0xf0000040)
    def owner(self): self.m.owner()
    def read(self, address): return self.m.read(address)
    def write(self, address, value): self.m.write(address, value)
    def apwrite(self, index, value):
        if index == 1: self.tar = value
        elif index == 3: self.m.write(self.tar, value)
        else: raise AssertionError('unexpected AP setup')
    def rdid_bytes(self): return self.m.rdid_bytes()
    def fifo_words(self, size):
        assert len(self.m.fifo) == size
        data = bytes(self.m.fifo); self.m.fifo = []; self.m.registers[hn.FIFO] = 1
        return data
    def mapped(self, address, size):
        assert self.m.registers[hn.CTRL] == hn.XIP|hn.IDLE|7
        assert self.m.registers[previous.mapped.XIP3] & 1
        return self.m.payload(3, address, size)
    def tx(self, data):
        assert self.intent is not None and 0 < len(data) <= 128
        for i in range(0, len(data), 4): self.m.tx_word(int.from_bytes(data[i:i+4], 'little'))
        self.tx_remaining -= len(data)


class SDK(previous.SDK):
    def __init__(self, model):
        super().__init__(model); self.device_wrapped = set()
    def __getattr__(self, name):
        f = super().__getattr__(name)
        if name not in self.device_wrapped:
            old = f.callback
            def wrapped(*args):
                if name == 'JLINKARM_CORESIGHT_WriteAPDPReg' and args[:2] == (3, 1) and self.tar == hn.DT:
                    assert self.csw & 0x37 == 2, 'TX must be word/noincrement'
                    self.model.tx_word(args[2]); return 0
                return old(*args)
            f.callback = wrapped; self.device_wrapped.add(name)
        return f


def native_port():
    m = Model(); sdk = SDK(m)
    dap = Dap(sdk, ROOT/'.cache/fake.log', ROOT/'.cache/fake.jlink', io.BytesIO())
    dap.open(); dap.connect()
    controls = previous.prior.prior.controls
    sdk.memory[controls.DHCSR] = 0x30001; sdk.memory[controls.PAUSE] = 0x1000
    ctrl = controls.Control(dap, controls.Observer(dap), lambda *a, **k: None, bytes(96), retained=True)
    p = dev.Port(ctrl, lambda *a, **k: None)
    m.registers[hn.CTRL] = hn.IDLE|7; m.registers[hn.FIFO] = 1
    p.intent_for('program', hw.LOW+4096, bytes(range(256)))
    p.mutation_command(6); p.write(hn.CMDSTS, 1); p.mutation_command(2)
    return m, sdk, dap, ctrl, p


class DeviceTests(unittest.TestCase):
    def test_complete_c_writer_through_controller_model(self):
        m = Model(); d = dev.Device(DirectPort(m), lambda *a, **k: None, SOURCE)
        d.open(); d.arm(RECEIPT)
        f = hw.bind(ctypes.CDLL(os.environ['P34_WRITER_DLL']))
        result = hw.run(f, d, SOURCE, seconds=13200)
        self.assertEqual(result['result'], 'HOST_WRITER_CALLBACKS_COMPLETED', result)
        self.assertEqual(d.index, 2576)
        self.assertEqual(m.nor[hw.LOW:0x300000], (ROOT/'.cache/p34-ram-writer-cross1/a.bin').read_bytes())
        self.assertEqual(m.nor[:hw.LOW], b'\xa5'*hw.LOW)
        self.assertEqual(m.nor[0x300000:], b'\xa5'*0x200000)
        d.finish(); self.assertTrue(d.gate.restored)

    def test_bad_order_data_and_scope_precede_wren(self):
        for kind, address, data in (('erase', hw.LOW-4096, b''), ('erase', hw.HIGH, b''),
                                    ('program', hw.LOW+28, b'TMOC'), ('erase', hw.LOW+4096, b'')):
            m = Model(); d = dev.Device(DirectPort(m), lambda *a, **k: None, SOURCE)
            d.open(); d.arm(RECEIPT); count = len(m.writes)
            with self.assertRaises(ValueError): d.mutate(kind, address, data)
            self.assertEqual(len(m.writes), count)
            self.assertEqual(m.physical, [])

    def test_missing_receipt_never_arms(self):
        m = Model(); d = dev.Device(DirectPort(m), lambda *a, **k: None, SOURCE); d.open()
        with self.assertRaises(ValueError): d.arm({})
        with self.assertRaises(ValueError): d.erase(hw.LOW)
        self.assertFalse(d.armed)
        self.assertEqual(m.physical, [])

    def test_ignored_wren_never_emits_erase(self):
        m = Model(); d = dev.Device(DirectPort(m), lambda *a, **k: None, SOURCE); d.open(); d.arm(RECEIPT)
        m.wren_ignored = True
        with self.assertRaisesRegex(ValueError, 'WREN'): d.erase(hw.LOW)
        self.assertEqual(m.physical, [])

    def test_protected_erase_with_wel_retained_latches(self):
        m = Model(); d = dev.Device(DirectPort(m), lambda *a, **k: None, SOURCE); d.open(); d.arm(RECEIPT)
        m.protected = m.keep_wel = True
        with self.assertRaisesRegex(ValueError, 'left WEL'): d.erase(hw.LOW)
        count = len(m.writes)
        with self.assertRaises(ValueError): d.erase(hw.LOW)
        self.assertEqual(len(m.writes), count)
        self.assertEqual(m.nor[hw.LOW:hw.LOW+32], b'\xa5'*32)

    def test_protected_erase_return_success_fails_core_verify(self):
        m = Model(); d = dev.Device(DirectPort(m), lambda *a, **k: None, SOURCE); d.open(); d.arm(RECEIPT)
        m.protected = True
        result = hw.run(hw.bind(ctypes.CDLL(os.environ['P34_WRITER_DLL'])), d, SOURCE)
        self.assertEqual(result['native_result'], -4)
        self.assertEqual(d.index, 1)
        with self.assertRaises(ValueError): d.finish()

    def test_protected_program_with_and_without_retained_wel(self):
        for keep_wel in (False, True):
            m = Model(); d = dev.Device(DirectPort(m), lambda *a, **k: None, SOURCE); d.open(); d.arm(RECEIPT)
            original = m.write
            def protect_program(address, value):
                if address == hn.BASE+12 and value >> 24 == 2:
                    m.protected, m.keep_wel = True, keep_wel
                original(address, value)
            m.write = protect_program
            result = hw.run(hw.bind(ctypes.CDLL(os.environ['P34_WRITER_DLL'])), d, SOURCE)
            self.assertEqual(result['result'], 'FAILED')
            self.assertEqual(d.index, 3)
            self.assertNotEqual(m.nor[hw.LOW+28:hw.LOW+32], b'TMOC')

    def test_delivered_marker_error_freezes_without_replay_or_restore(self):
        m = Model(); port = DirectPort(m); d = dev.Device(port, lambda *a, **k: None, SOURCE)
        d.open(); d.arm(RECEIPT)
        original = port.tx
        def marker_error(data):
            original(data)
            if port.intent[1] == hw.LOW+28: raise OSError('marker delivered/error return')
        port.tx = marker_error
        result = hw.run(hw.bind(ctypes.CDLL(os.environ['P34_WRITER_DLL'])), d, SOURCE)
        self.assertEqual(result['result'], 'FAILED')
        self.assertEqual(m.nor[hw.LOW+28:hw.LOW+32], b'TMOC')
        count = len(m.writes)
        with self.assertRaises(ValueError): d.finish()
        self.assertEqual(len(m.writes), count)

    def test_each_mutating_command_word_delivery_error_latches(self):
        for offset in range(1, 9):
            m = Model(); port = DirectPort(m); d = dev.Device(port, lambda *a, **k: None, SOURCE)
            d.open(); d.arm(RECEIPT)
            original = port.mutation_command; counter = [0]
            old_write = m.write
            def command(opcode):
                def failure(address, value):
                    old_write(address, value); counter[0] += 1
                    if counter[0] == offset: raise OSError('command word delivered/error')
                m.write = failure
                try: return original(opcode)
                finally: m.write = old_write
            port.mutation_command = command
            with self.assertRaises(OSError): d.erase(hw.LOW)
            self.assertEqual(counter[0], offset)
            count = len(m.writes)
            with self.assertRaises(ValueError): d.finish()
            self.assertEqual(len(m.writes), count)

    def test_busy_deadline_uses_finite_clock_not_iteration_infinity(self):
        m = Model(); d = dev.Device(DirectPort(m), lambda *a, **k: None, SOURCE, clock=lambda: m.operations*.005)
        d.open(); d.arm(RECEIPT); m.busy_forever = True
        with self.assertRaisesRegex(ValueError, 'deadline'): d.erase(hw.LOW)
        self.assertLess(m.operations, 3000)

    def test_native_program_needs_two_exact_fifo_fills(self):
        m, sdk, dap, ctrl, p = native_port()
        p.tx(bytes(range(128)))
        self.assertIsNotNone(m.pending)
        self.assertEqual(m.registers[hn.CMDSTS], 0)
        p.tx(bytes(range(128, 256)))
        self.assertIsNone(m.pending)
        self.assertEqual(m.registers[hn.CMDSTS], 1)
        self.assertEqual(len(m.tx_words), 64)
        p.restore_ap(); ctrl.close()

    def test_tx_each_word_error_stops_without_restoring_controller(self):
        for fail_word in range(1, 33):
            m, sdk, dap, ctrl, p = native_port()
            old = sdk.JLINKARM_CORESIGHT_WriteAPDPReg.callback
            def failure(*args):
                result = old(*args)
                return -1 if len(m.tx_words) == fail_word else result
            sdk.JLINKARM_CORESIGHT_WriteAPDPReg.callback = failure
            gate = dev.Gate(p, lambda *a, **k: None)
            count = len(m.writes)
            with self.assertRaises(ValueError): gate.call(p.tx, bytes(range(128)))
            self.assertEqual(len(m.tx_words), fail_word)
            with self.assertRaises(ValueError): gate.write(hn.CMDSTS, 1)
            self.assertEqual(len(m.writes), count)
            sdk.JLINKARM_CORESIGHT_WriteAPDPReg.callback = old
            p.restore_ap(); ctrl.close()
            self.assertTrue(dap.close_returned)

    def test_tx_each_word_sticky_error_stops_before_next_store(self):
        for fail_word in (1, 16, 32):
            m, sdk, dap, ctrl, p = native_port()
            old = sdk.JLINKARM_CORESIGHT_WriteAPDPReg.callback
            def failure(*args):
                result = old(*args)
                if len(m.tx_words) == fail_word: sdk.dp |= 0x20
                return result
            sdk.JLINKARM_CORESIGHT_WriteAPDPReg.callback = failure
            gate = dev.Gate(p, lambda *a, **k: None)
            with self.assertRaisesRegex(ValueError, 'DP/callback'): gate.call(p.tx, bytes(range(128)))
            self.assertEqual(len(m.tx_words), fail_word)
            with self.assertRaises(ValueError): ctrl.close()
            self.assertTrue(dap.close_returned)

    def test_long_observation_does_not_inherit_600_second_limit(self):
        import p34_host_nor_device as run
        clock = [0]
        observation = run.LongObservation(None, lambda *a, **k: None, clock=lambda: clock[0])
        observation.started = 0
        clock[0] = 601; observation._check()
        clock[0] = 13799; observation._check()
        clock[0] = 13800
        with self.assertRaises(ValueError): observation._check()

    def test_owned_worker_lifecycle_mocked_control_and_real_dll_archives(self):
        import p34_host_nor_device as run
        store = run.cli.Store(ROOT); out = store.checked(Path(os.environ['P34_TEST_OUT'])/'case-worker')
        run.preflight(store, out)
        m = Model(); port = DirectPort(m)
        baseline = store.read(ROOT/'.cache/p34-entry-owner1/worker.json')['retained']
        image = (ROOT/'.cache/p34-native-image1/app-readback.bin').read_bytes()
        boot = (ROOT/'.cache/p34-native-acquire1/boot-readback.bin').read_bytes()
        m.nor[0x1000:0x1000+len(image)] = image
        m.nor[hw.LOW:hw.LOW+128] = (ROOT/'.cache/p34-host-nor-read1/recovery-prefix.bin').read_bytes()
        def internal(address, size):
            origin, source = (0x08000000, boot) if address < 0x08010000 else (0x08010000, image)
            return source[address-origin:address-origin+size]
        port.internal = internal; port.restore_ap = lambda: None
        class DapStub:
            def __init__(self, *a): self.close_returned, self.metadata = False, {}
        class ObservationStub:
            def __init__(self, dap, emit): self.dap = dap
            def connect(self): pass
            def _check(self): pass
        class ControlStub:
            def __init__(self, dap, *a, **k): self.dap = dap
            def observe_retained(self, original): return baseline
            def context(self): return baseline['context']
            def close(self): self.dap.close_returned = True
        def bcb_stub(store, out, name, *args):
            data = (ROOT/'.cache/p34-host-bcb1/capture-raw.bin').read_bytes()
            return dict(raw=store.raw(out/(name+'.bin'), data))
        plan = dict(inputs=[run.cli.record(p) for p in run.SOURCES], out=str(out), scope=[hw.LOW, hw.HIGH],
            version=30276, native_history_approved=str(run.base.HISTORY),
            writer=run.cli.record(os.environ['P34_WRITER_DLL']),
            bcb_reader=run.cli.record(ROOT/'.cache/p34-host-bcb-test2/bcb-reader.dll'),
            validator=run.cli.record(ROOT/'.cache/p34-recovery-admission2/validator.exe'))
        store.write(out/'plan.json', plan)
        with mock.patch.object(run.base, 'in_job', return_value=True), \
             mock.patch.object(run.base, 'native_presence', return_value=dict(debugger_processes=[])), \
             mock.patch.object(run.base, 'guarded', return_value=object()), \
             mock.patch.object(run.base, 'Dap', DapStub), \
             mock.patch.object(run, 'LongObservation', ObservationStub), \
             mock.patch.object(run, 'Control', ControlStub), \
             mock.patch.object(run, 'bcb', bcb_stub), \
             mock.patch.object(run.nd, 'Port', return_value=port), \
             mock.patch.object(run.prior.prior.prior, 'owners', return_value={}), \
             mock.patch.object(run.os, 'add_dll_directory', return_value=contextlib.nullcontext()):
            self.assertEqual(run.worker(store, out), 0)
        result = store.read(out/'worker.json')
        self.assertEqual(result['result'], 'RECOVERY_30276_VERIFIED_ORIGINAL_APP_HALTED')
        self.assertEqual(result['controller']['mutations'], 2576)
        self.assertTrue(result['close_returned'])
        receipt = store.read(out/'preimages.json')
        run.validate_preimages(store, out, receipt)
        receipt['regions']['tail']['sha256'] = '0'*64
        with self.assertRaises(RuntimeError): run.validate_preimages(store, out, receipt)


if __name__ == '__main__': unittest.main()
