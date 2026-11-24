import ctypes
import hashlib
import os
from pathlib import Path
import sys
import unittest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT/'Tools/ota'))
from recovery_entry import host_writer as hw
import p34_install_cost as host


class Memory:
    def __init__(self):
        self.data = bytearray(b'\xa5'*0x100000)
        self.writes, self.reads, self.fail = [], 0, None
    def read(self, address, size):
        hw.scope(address, size)
        self.reads += 1
        return bytes(self.data[address-hw.LOW:address-hw.LOW+size])
    def erase(self, address):
        hw.scope(address, 4096)
        self.writes.append(('erase', address, 4096))
        self.data[address-hw.LOW:address-hw.LOW+4096] = b'\xff'*4096
        return -1 if self.fail == ('erase', address) else 0
    def program(self, address, data):
        hw.scope(address, len(data))
        self.writes.append(('program', address, len(data)))
        for i, b in enumerate(data): self.data[address-hw.LOW+i] &= b
        return -1 if self.fail == ('program', address) else 0


class WriterTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.source = (ROOT/'.cache/p34-recovery-sources1/r2-a.bin').read_bytes()
        cls.library = ctypes.CDLL(os.environ['P34_WRITER_DLL'])
        cls.function = staticmethod(hw.bind(cls.library))

    def test_completed_native_writer_and_unchanged_boot_admission(self):
        m = Memory(); result = hw.run(self.function, m, self.source)
        self.assertEqual(result['result'], 'HOST_WRITER_CALLBACKS_COMPLETED')
        self.assertEqual(m.writes[0], ('erase', hw.LOW, 4096))
        self.assertEqual(m.writes[-2:], [('program', hw.LOW, 28), ('program', hw.LOW+28, 4)])
        self.assertEqual(m.data[4096:4096+hw.LENGTH], self.source)
        self.assertEqual(m.data[hw.HIGH-hw.LOW:], b'\xa5'*(0x300000-hw.HIGH))
        self.assertEqual(m.data, (ROOT/'.cache/p34-ram-writer-cross1/a.bin').read_bytes())
        store = host.cli.Store(ROOT); out = store.checked(Path(os.environ['P34_TEST_OUT']))
        slot = store.checked(out/'physical-model.bin')
        store.raw(slot, bytes(m.data))
        env = dict(os.environ)
        log = host.command(store, out, 'admission',
            [ROOT/'.cache/p34-recovery-admission2/validator.exe', slot, '0', '0'], env, 20)
        self.assertIn(b'RECOVERY_ADMISSION result=0', log)
        self.assertIn(b'version=30276', log)

    def test_bad_source_digest_zero_mutations(self):
        data = bytearray(self.source); data[4096] ^= 1
        m = Memory()
        with self.assertRaises(ValueError): hw.run(self.function, m, bytes(data))
        self.assertEqual(m.writes, [])

    def test_c_admission_wrong_pin_rejects_before_erase(self):
        m = Memory(); g = hw.Guard(m, self.source)
        pin = (ctypes.c_ubyte*32)()
        result = self.function(ctypes.byref(g.io), hw.LENGTH, pin)
        self.assertEqual(result, -2)
        self.assertEqual(m.writes, [])

    def test_callback_ranges_before_port(self):
        invalid = [('erase', hw.LOW-4096, 4096), ('erase', hw.HIGH, 4096),
                   ('erase', hw.LOW+1, 4096), ('program', hw.HIGH, 1),
                   ('program', hw.LOW+4096+255, 2), ('program', hw.LOW, 32),
                   ('program', hw.LOW+31, 1), ('program', hw.LOW+32, 1),
                   ('program', hw.HIGH-1, 2), ('program', hw.LOW+4096+hw.LENGTH, 4)]
        for operation, address, size in invalid:
            m = Memory(); g = hw.Guard(m, self.source)
            buf = (ctypes.c_ubyte*size)()
            fn = getattr(g, operation)
            args = (address,) if operation == 'erase' else (address, buf, size)
            self.assertEqual(g.invoke(fn, *args), -1)
            self.assertEqual(m.writes, [])
            self.assertIsNotNone(g.error)

    def test_delivered_error_header_payload_metadata_marker_never_replayed(self):
        for fault in (('erase', hw.LOW), ('erase', hw.LOW+4096),
                      ('program', hw.LOW+4096), ('program', hw.LOW), ('program', hw.LOW+28)):
            m = Memory(); m.fail = fault
            result = hw.run(self.function, m, self.source)
            self.assertEqual(result['result'], 'FAILED')
            self.assertEqual(m.writes[-1][:2], fault)
            self.assertIsNotNone(result['callback_error'])
            if fault == ('program', hw.LOW+28):
                self.assertEqual(m.data[28:32], b'TMOC')

    def test_short_read_or_baseexception_latches_callbacks(self):
        for kind in ('short', 'exception'):
            m = Memory()
            def read(address, size):
                if kind == 'exception': raise KeyboardInterrupt('callback fault')
                return b'\xff'*(size-1)
            m.read = read
            result = hw.run(self.function, m, self.source)
            self.assertEqual(result['result'], 'FAILED')
            self.assertEqual(m.writes, [('erase', hw.LOW, 4096)])

    def test_deadline_after_delivered_erase_stops(self):
        m = Memory(); clock = [0.0]
        erase = m.erase
        def delayed(address):
            rc = erase(address); clock[0] = 10; return rc
        m.erase = delayed
        result = hw.run(self.function, m, self.source, seconds=1, clock=lambda: clock[0])
        self.assertEqual(result['result'], 'FAILED')
        self.assertEqual(m.writes, [('erase', hw.LOW, 4096)])

    def test_corrupt_readback_never_commits_marker(self):
        m = Memory(); old = m.program
        def corrupt(address, data):
            rc = old(address, data)
            if address == hw.LOW+4096: m.data[4096] ^= 1
            return rc
        m.program = corrupt
        result = hw.run(self.function, m, self.source)
        self.assertEqual(result['native_result'], -4)
        self.assertNotEqual(m.data[28:32], b'TMOC')

    def test_changed_second_source_delivery_fails_before_payload_erase(self):
        m = Memory(); g = hw.Guard(m, self.source)
        old = g.source_read
        def changed(offset, destination, size):
            old(offset, destination, size)
            if m.writes: destination[0] ^= 1
        g.source_read = changed
        pin = (ctypes.c_ubyte*32).from_buffer_copy(bytes.fromhex(hw.PINNED))
        result = self.function(ctypes.byref(g.io), hw.LENGTH, pin)
        self.assertEqual(result, -2)
        self.assertEqual(m.writes, [('erase', hw.LOW, 4096)])

    def test_ignored_protected_erase_or_program_never_commits(self):
        for kind in ('erase', 'program'):
            m = Memory()
            if kind == 'erase':
                def ignored(address):
                    m.writes.append(('erase', address, 4096)); return 0
                m.erase = ignored
            else:
                def ignored(address, data):
                    m.writes.append(('program', address, len(data))); return 0
                m.program = ignored
            result = hw.run(self.function, m, self.source)
            self.assertEqual(result['native_result'], -4)
            self.assertNotIn(('program', hw.LOW+28, 4), m.writes)

    def test_long_cell_deadline_is_explicit_and_still_finite(self):
        guard = hw.Guard(Memory(), self.source, seconds=13200)
        self.assertEqual(guard.seconds, 13200)
        for seconds in (0, -1, 13201, float('inf')):
            with self.assertRaises(ValueError): hw.Guard(Memory(), self.source, seconds=seconds)


if __name__ == '__main__': unittest.main()
