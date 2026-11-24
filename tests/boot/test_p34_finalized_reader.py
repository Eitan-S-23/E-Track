import ctypes
from pathlib import Path
import struct
import sys
from types import SimpleNamespace
import unittest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT/'Tools/ota'))
import p34_finalized_vtor_capture as cap
from recovery_entry import finalized_reader as port


class SDK:
    def __init__(self, image):
        self.image, self.tar, self.calls, self.fail_at = image, 0, [], None
        self.dp, self.dhcsr, self.csw = 0xf0000040, 0x10001, 0x23000052
    def JLINKARM_CORESIGHT_WriteAPDPReg(self, index, ap, value):
        self.calls.append(('write', index, ap, value))
        assert (index, ap) == (1, 1), 'target/AP data write forbidden'
        self.tar = value
        return -1 if len(self.calls) == self.fail_at else 0
    def JLINKARM_CORESIGHT_ReadAPDPReg(self, index, ap, pointer):
        self.calls.append(('read', index, ap, self.tar))
        if (index, ap) == (0, 1): value = self.csw
        elif (index, ap) == (1, 0): value = self.dp
        else:
            assert (index, ap) == (3, 1)
            if self.tar == port.DHCSR: value = self.dhcsr
            elif self.tar == port.VTOR: value = cap.policy.RUNTIME
            else:
                offset = self.tar-port.ORIGIN
                assert 0 <= offset < len(self.image)
                value = int.from_bytes(self.image[offset:offset+4], 'little')
            self.tar = (self.tar & ~1023) | ((self.tar+4) & 1023)
        ctypes.cast(pointer, ctypes.POINTER(ctypes.c_uint32))[0] = value
        return -1 if len(self.calls) == self.fail_at else 0


class ReaderTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls): cls.image = (ROOT/'.cache/p34-recovery-sources1/r2-a.bin').read_bytes()
    def setup_port(self):
        self.sdk, self.now, self.bounds, self.events = SDK(self.image), 0., [], []
        self.state = dict(owned=True, connection_generation='c1', boot_generation=7, reset_seen=False)
        dap = SimpleNamespace(sdk=self.sdk, ready=True, word_csw=self.sdk.csw, callback_error=None)
        def guard(function, *args, seconds):
            self.bounds.append(seconds); return function(*args)
        return port.Reader(dap, lambda e, **kw:self.events.append((e,kw)), lambda:dict(self.state),
                           connection_generation='c1', boot_generation=7, clock=lambda:self.now, guard=guard)

    def test_full_capture_through_actual_port_and_mock_sdk(self):
        reader = self.setup_port()
        result = cap.capture(reader.read, reader.owner, image_sha256=cap.policy.IDENTITIES['r2-a.bin'], version=30276,
                             connection_generation='c1', boot_generation=7, clock=lambda:self.now)
        self.assertEqual(result['raw_image'], self.image)
        self.assertEqual(reader.api_reads, 157)
        self.assertGreater(reader.target_chunks, 157)
        self.assertTrue(all(0 < x <= 5 for x in self.bounds))
        self.assertTrue(all(c[1:3] == (1,1) for c in self.sdk.calls if c[0] == 'write'))
        self.assertFalse(result['native_route_validated'])

    def test_tar_boundary_split_and_final_image_word(self):
        reader = self.setup_port(); self.assertEqual(reader.read(port.ORIGIN+1020, 8, 10), self.image[1020:1028])
        addresses = [c[3] for c in self.sdk.calls if c[0] == 'write']
        self.assertEqual(addresses, [port.ORIGIN+1020, port.ORIGIN+1024])
        self.assertEqual(reader.read(port.ORIGIN+port.LENGTH-4, 4, 10), self.image[-4:])

    def test_out_of_scope_never_reaches_sdk(self):
        for address,size in ((0x08000000,4), (0x90000000,4), (0xe000ed0c,4), (port.DHCSR,8),
                             (port.ORIGIN+port.LENGTH,4), (port.ORIGIN+1,4), (port.ORIGIN,4097)):
            reader = self.setup_port()
            with self.assertRaises(ValueError): reader.read(address,size,10)
            self.assertFalse(self.sdk.calls)

    def test_every_small_read_native_step_failure_latches(self):
        for index in range(1,6):
            reader = self.setup_port(); self.sdk.fail_at = index
            with self.assertRaises(ValueError): reader.read(port.ORIGIN,8,10)
            calls = len(self.sdk.calls)
            with self.assertRaises(ValueError): reader.read(port.ORIGIN,8,10)
            self.assertEqual(len(self.sdk.calls), calls)
            self.assertFalse(any(n == 'finalized-read-returned' for n,_ in self.events))

    def test_dp_error_and_format_change_fail_closed(self):
        for kind in ('dp','csw'):
            reader = self.setup_port()
            if kind == 'dp': self.sdk.dp |= 2
            else: self.sdk.csw ^= 0x10
            with self.assertRaises(ValueError): reader.read(port.ORIGIN,4,10)
            self.assertIsNotNone(reader.error)
            self.assertFalse(any(n == 'finalized-read-returned' for n,_ in self.events))

    def test_owner_generation_and_reset_latches(self):
        for field, value in (('connection_generation','c2'), ('boot_generation',8), ('reset_seen',True), ('owned',False)):
            reader = self.setup_port(); self.state[field] = value
            with self.assertRaises(ValueError): reader.read(port.ORIGIN,4,10)
            self.assertFalse(self.sdk.calls)
        reader = self.setup_port(); self.sdk.dhcsr |= 0x02000000
        self.assertTrue(reader.owner()['reset_seen'])
        self.sdk.dhcsr &= ~0x02000000; before = len(self.sdk.calls)
        with self.assertRaises(ValueError): reader.read(port.ORIGIN,4,10)
        self.assertEqual(len(self.sdk.calls), before)

    def test_deadline_backward_clock_and_subfive_second_bound(self):
        reader = self.setup_port(); reader.read(port.ORIGIN,4,.25)
        self.assertTrue(all(0 < x <= .25 for x in self.bounds))
        for now in (-1,181,float('nan')):
            reader = self.setup_port(); self.now=now
            with self.assertRaises(ValueError): reader.read(port.ORIGIN,4,10)
            self.assertFalse(self.sdk.calls)
        reader = self.setup_port()
        def late(function,*args,seconds):
            value=function(*args); self.now+=11; return value
        reader.guard=late
        with self.assertRaises(ValueError): reader.read(port.ORIGIN,4,10)
        self.assertEqual(len(self.sdk.calls),1)

    def test_initial_lease_time_counts_against_caller_deadline(self):
        reader = self.setup_port()
        def delayed():
            self.now += 1
            return dict(self.state)
        reader.lease = delayed
        with self.assertRaises(ValueError): reader.read(port.ORIGIN,4,.25)
        self.assertFalse(self.sdk.calls)
        self.assertIsNotNone(reader.error)

    def test_final_emit_delay_rejects_bytes_and_latches_failure(self):
        reader = self.setup_port()
        def delayed(name, **fields):
            if name == 'finalized-read-returned': self.now += .5
        reader.emit = delayed
        with self.assertRaises(ValueError): reader.read(port.ORIGIN,4,.25)
        count=len(self.sdk.calls)
        with self.assertRaises(ValueError): reader.read(port.ORIGIN,4,10)
        self.assertEqual(len(self.sdk.calls),count)

    def test_owner_halt_or_lockup_latches_failure(self):
        for flag in (0x20000,0x80000):
            reader=self.setup_port(); self.sdk.dhcsr|=flag
            with self.assertRaises(ValueError): reader.owner()
            count=len(self.sdk.calls)
            with self.assertRaises(ValueError): reader.read(port.ORIGIN,4,10)
            self.assertEqual(len(self.sdk.calls),count)


if __name__ == '__main__': unittest.main()
