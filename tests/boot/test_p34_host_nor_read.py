import ctypes
import io
from pathlib import Path
import sys
import unittest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT/'Tools/ota'))
sys.path.insert(0, str(ROOT/'tests/boot'))
from recovery_entry import host_nor as hn, host_nor_read as nr
from recovery_entry.dap_probe import Dap
import test_p34_host_nor as prior


class Model(prior.Model):
    def __init__(self):
        super().__init__()
        self.image = (ROOT/'.cache/p34-native-image1/app-readback.bin').read_bytes()
        self.sfdp = bytes(range(256))
        self.data_commands = []
    def payload(self, opcode, address, size):
        if opcode == 0x5a: return self.sfdp[address:address+size]
        if 0x1000 <= address < 0x2000: return self.image[address-0x1000:address-0x1000+size]
        return bytes((address+i) & 255 for i in range(size))
    def write(self, address, value):
        if address != hn.BASE+12 or value >> 24 not in (3, 0x5a):
            return super().write(address, value)
        self.operations += 1; self.writes.append((address, value)); self.registers[address] = value
        assert self.order == [0, 4, 8]
        self.order = []
        opcode = value >> 24
        start, size = self.registers[hn.BASE], self.registers[hn.BASE+8]
        assert self.registers[hn.BASE+4] == (0x01080003 if opcode == 0x5a else 0x01000003)
        assert 0 < size <= 128 and size % 4 == 0
        data = self.payload(opcode, start, size)
        assert len(data) == size
        self.fifo = list(data)
        self.registers[hn.CMDSTS] = 1
        self.registers[hn.FIFO] = 3
        self.data_commands.append((opcode, start, size))
        if self.fail_write == len(self.writes): raise OSError('delivered read trigger error')


class SDK(prior.SDK):
    def __init__(self, model):
        super().__init__(model)
        self.read_wrapped, self.word_reads = set(), []
    def __getattr__(self, name):
        func = super().__getattr__(name)
        if name not in self.read_wrapped:
            old = func.callback
            def invoke(*args):
                if name == 'JLINKARM_CORESIGHT_ReadAPDPReg' and args[:2] == (3, 1) and self.bank == 0 and self.tar == hn.DT and self.csw & 7 == 2:
                    assert self.csw & 0x37 == 2, 'word FIFO auto-increment enabled'
                    assert len(self.model.fifo) >= 4, 'word FIFO overread'
                    self.word_reads.append((self.tar, self.csw))
                    data = bytes(self.model.fifo[:4]); del self.model.fifo[:4]
                    if not self.model.fifo: self.model.registers[hn.FIFO] = 1
                    ctypes.cast(args[2], ctypes.POINTER(ctypes.c_uint32))[0] = int.from_bytes(data, 'little')
                    return 0
                return old(*args)
            func.callback = invoke; self.read_wrapped.add(name)
        return func


def fixture():
    m = Model(); sdk = SDK(m)
    dap = Dap(sdk, ROOT/'.cache/fake.log', ROOT/'.cache/fake.jlink', io.BytesIO())
    dap.open(); dap.connect()
    sdk.memory[prior.controls.DHCSR] = 0x30001; sdk.memory[prior.controls.PAUSE] = 0x1000
    control = prior.controls.Control(dap, prior.controls.Observer(dap), lambda *a, **k: None, bytes(96), retained=True)
    port = nr.Port(control, lambda *a, **k: None)
    reader = nr.Reader(port, lambda *a, **k: None)
    return m, sdk, dap, control, port, reader


class ReadTests(unittest.TestCase):
    def test_complete_read_cell_native_boundary(self):
        m, sdk, dap, ctrl, p, r = fixture()
        result = nr.collect(r)
        self.assertEqual(bytes.fromhex(result['sfdp_hex']), bytes(range(256)))
        self.assertEqual(bytes.fromhex(result['candidate_prefix_hex']), m.image[:4096])
        self.assertEqual(result['read_commands'], 36)
        self.assertEqual(len(sdk.word_reads), 36*32)
        self.assertEqual(m.data_commands[:2], [(0x5a, 0, 128), (0x5a, 128, 128)])
        self.assertEqual(m.data_commands[-2:], [(3, 0x200000, 128), (3, 0x299000, 128)])
        self.assertTrue(r.restored)
        self.assertFalse(result['nor_write_admitted'])
        p.restore_ap(); ctrl.close()
        self.assertTrue(dap.close_returned)

    def test_command_boundaries_reject_before_target_write(self):
        m, sdk, dap, ctrl, p, r = fixture()
        for args in ((6, 0, 128), (2, 0x200000, 128), (3, -1, 128), (3, 0xffffff, 4),
                     (3, 0, 0), (3, 0, 129), (3, 0, 3), (0x5a, 256, 128), (0x5a, 0, 64)):
            with self.assertRaises(ValueError): p.read_command(*args)
        self.assertEqual(m.writes, [])
        ctrl.close()

    def test_each_command_write_failure_no_replay(self):
        for phase in range(1, 5):
            m, sdk, dap, ctrl, p, r = fixture(); r.open()
            before = len(m.writes); m.fail_write = before+phase
            with self.assertRaises(OSError): r.data(3, 0x1000, 128)
            self.assertEqual(len(m.writes), before+phase)
            with self.assertRaises(ValueError): r.finish()
            self.assertEqual(len(m.writes), before+phase)
            p.restore_ap(); ctrl.close()

    def test_every_native_burst_substep_failure_ap_only_cleanup(self):
        m, sdk, dap, ctrl, p, r = fixture()
        m.fifo = list(range(128)); m.registers[hn.CMDSTS] = 1; m.registers[hn.FIFO] = 3
        before = len(sdk.calls); r.call(p.fifo_words, 128); total = len(sdk.calls)-before
        ctrl.close()
        for fail_at in range(1, total+1):
            m, sdk, dap, ctrl, p, r = fixture()
            m.fifo = list(range(128)); m.registers[hn.CMDSTS] = 1; m.registers[hn.FIFO] = 3
            counter = [0]
            for name in ('JLINKARM_CORESIGHT_ReadAPDPReg', 'JLINKARM_CORESIGHT_WriteAPDPReg'):
                func = getattr(sdk, name); old = func.callback
                def injected(*args, old=old):
                    value = old(*args); counter[0] += 1
                    return -1 if counter[0] == fail_at else value
                func.callback = injected
            with self.assertRaises(ValueError): r.call(p.fifo_words, 128)
            consumed = len(sdk.word_reads)
            with self.assertRaises(ValueError): r.write(hn.CMDSTS, 1)
            p.restore_ap(); ctrl.close()
            self.assertEqual(len(sdk.word_reads), consumed)
            self.assertEqual(m.writes, [])
            self.assertEqual(sdk.csw, dap.original_csw)

    def test_sticky_errors_after_each_word_stop_consumption(self):
        for word in range(1, 33):
            m, sdk, dap, ctrl, p, r = fixture()
            m.fifo = list(range(128)); m.registers[hn.CMDSTS] = 1; m.registers[hn.FIFO] = 3
            old = sdk.JLINKARM_CORESIGHT_ReadAPDPReg.callback
            def injected(*args):
                value = old(*args)
                if len(sdk.word_reads) == word: sdk.dp |= 0x20
                return value
            sdk.JLINKARM_CORESIGHT_ReadAPDPReg.callback = injected
            with self.assertRaisesRegex(ValueError, 'DP/callback'): r.call(p.fifo_words, 128)
            self.assertEqual(len(sdk.word_reads), word)
            self.assertEqual(m.writes, [])
            with self.assertRaises(ValueError): ctrl.close()
            self.assertTrue(dap.close_returned)

    def test_byte_tail_and_overlarge_fifo_requests_rejected(self):
        m, sdk, dap, ctrl, p, r = fixture()
        for n in (0, 1, 3, 127, 129, 256):
            with self.assertRaises(ValueError): p.fifo_words(n)
        self.assertEqual(sdk.word_reads, [])
        ctrl.close()

    def test_stale_complete_or_rx_stops_before_read_trigger(self):
        for address, value in ((hn.CMDSTS, 1), (hn.FIFO, 3)):
            m, sdk, dap, ctrl, p, r = fixture(); r.open()
            m.registers[address] = value; count = len(m.writes)
            with self.assertRaises(ValueError): r.data(3, 0x1000, 128)
            self.assertEqual(len(m.writes), count)
            ctrl.close()


if __name__ == '__main__': unittest.main()
