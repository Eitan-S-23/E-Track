from pathlib import Path
import struct
import sys
import unittest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT/'Tools/ota'))
import p34_finalized_vtor_capture as cap


class Memory:
    def __init__(self, image, vtor=cap.policy.RUNTIME, fault=None):
        self.image, self.vtor, self.fault = image, vtor, fault
        self.calls, self.now = [], 0.0
    def clock(self): return self.now
    def owner(self):
        n = len(self.calls)
        value = dict(owned=True, connection_generation='owned-connection', boot_generation=7, reset_seen=False)
        if n >= 4:
            if self.fault == 'owner': value['owned'] = False
            if self.fault == 'connection': value['connection_generation'] = 'reconnected'
            if self.fault == 'generation': value['boot_generation'] += 1
            if self.fault == 'consumed-reset': value['reset_seen'] = True
            if self.fault == 'owner-error': raise OSError('lost owner')
        return value
    def read(self, address, size, timeout):
        assert 0 < timeout <= 300
        self.calls.append((address, size)); self.now += .001
        n = len(self.calls)
        if n == 4:
            if self.fault == 'io': raise OSError('read failed')
            if self.fault == 'timeout': self.now += 301
            if self.fault == 'clock': self.now -= 1
        if address == cap.DHCSR:
            bits = {'reset': 1 << 25, 'halt': 1 << 17, 'lockup': 1 << 19}.get(self.fault, 0)
            if self.fault == 'final-reset' and n > 2: bits = 1 << 25
            data = struct.pack('<I', bits)
        elif address == cap.VTOR:
            vtor = cap.policy.ORIGIN if self.fault == 'switch' and n > 2 else self.vtor
            data = struct.pack('<I', vtor)
        else:
            data = self.image[address-cap.policy.ORIGIN:address-cap.policy.ORIGIN+size]
            if self.fault == 'table' and size == cap.policy.TABLE: data = bytes(size)
        if n == 4:
            if self.fault == 'short': return data[:-1]
            if self.fault == 'type': return bytearray(data)
        return data


class CaptureTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.images = {n: (ROOT/'.cache/p34-recovery-sources1'/n).read_bytes() for n in cap.policy.IDENTITIES}
    def invoke(self, memory, name='r2-a.bin', **overrides):
        digest = cap.policy.IDENTITIES[name]
        args = dict(image_sha256=digest, version=cap.PLANNED[digest], connection_generation='owned-connection',
                    boot_generation=7, clock=memory.clock)
        args.update(overrides)
        return cap.capture(memory.read, memory.owner, **args)

    def test_each_exact_finalized_image_and_both_tables(self):
        for name, image in self.images.items():
            for table in (cap.policy.ORIGIN, cap.policy.RUNTIME):
                with self.subTest(name=name, table=table):
                    memory = Memory(image, table); result = self.invoke(memory, name)
                    self.assertEqual(len(memory.calls), 157)
                    self.assertEqual(result['raw_image'], image)
                    self.assertEqual(result['operational_readiness'], 'NOT_ESTABLISHED')
                    self.assertFalse(result['native_route_validated'])

    def test_cross_planned_versions_rejected(self):
        for actual, planned in (('r2-a.bin', 'r2-b.bin'), ('r2-b.bin', 'r2-a.bin')):
            memory = Memory(self.images[actual])
            with self.assertRaisesRegex(cap.CaptureError, 'digest mismatch'): self.invoke(memory, planned)
            self.assertEqual(len(memory.calls), 154)

    def test_old_app_or_corrupted_image_rejected(self):
        old = (ROOT/'.cache/p34-native-image1/app-readback.bin').read_bytes().ljust(cap.IMAGE_BYTES, b'\xff')
        for image in (old, bytes(cap.IMAGE_BYTES)):
            memory = Memory(image)
            with self.assertRaisesRegex(cap.CaptureError, 'digest mismatch'): self.invoke(memory)

    def test_faults_stop_without_retry_and_retain_read_evidence(self):
        expected = dict(io=4, timeout=4, clock=4, short=4, type=4, owner=4, connection=4, generation=4,
                        **{'consumed-reset':4, 'owner-error':4, 'reset':1, 'halt':1, 'lockup':1,
                           'final-reset':157, 'switch':157, 'table':157})
        for fault, count in expected.items():
            with self.subTest(fault=fault):
                memory = Memory(self.images['r2-a.bin'], fault=fault)
                with self.assertRaises(cap.CaptureError) as raised: self.invoke(memory)
                self.assertEqual(len(memory.calls), count)
                self.assertEqual(len(raised.exception.reads), count)
                self.assertEqual(len(raised.exception.raw_reads), count-(fault in ('io', 'short', 'type')))

    def test_invalid_plan_and_deadlines_do_not_read(self):
        cases = [dict(version=30277), dict(version=True), dict(image_sha256='0'*64), dict(image_sha256=[]),
                 dict(connection_generation=''), dict(boot_generation=True), dict(boot_generation=-1)]
        cases += [dict(seconds=s) for s in (0, -1, 301, True, float('inf'), float('nan'))]
        for fields in cases:
            memory = Memory(self.images['r2-a.bin'])
            with self.assertRaises(cap.CaptureError): self.invoke(memory, **fields)
            self.assertFalse(memory.calls)

    def test_unbound_initial_vector_stops_before_image(self):
        memory = Memory(self.images['r2-a.bin'], 0x20000000)
        with self.assertRaises(cap.CaptureError): self.invoke(memory)
        self.assertEqual(len(memory.calls), 2)


if __name__ == '__main__': unittest.main()
