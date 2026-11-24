from pathlib import Path
import sys
import unittest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT/'Tools/ota'))
sys.path.insert(0, str(ROOT/'tests/boot'))
from recovery_confirm.read_pair import ReadPair
import test_p34_recovery_ports as model


class Tests(unittest.TestCase):
    def make(self, native=False):
        clock = model.Clock()
        slave = model.Slave(clock, model.BEFORE+b'R'*128)
        sdk = model.SDK(slave)
        words = model.Words(model.Dap(sdk), lambda *a,**k:None, reads=model.gpio.READS,
                            write_allowed=model.gpio.allowed_write, seconds=960, clock=clock,
                            guard=lambda fn,*a,**kw:fn(*a))
        pins = model.gpio.Pins(words, sdk.original, lambda:True) if native else slave
        wire = ReadPair(pins, clock=clock, sleep=clock.sleep)
        return clock, slave, sdk, wire

    def test_complete_pair_uses_exact_read_order_and_preserves_all_eeprom_bytes(self):
        _, slave, _, wire = self.make(native=True)
        reads = []
        capture = wire.capture(lambda i,a,d:reads.append((i,a,d)))
        self.assertEqual(capture, model.BEFORE*2)
        self.assertEqual([a for _,a,_ in reads], [0,64,0,64])
        self.assertEqual(bytes(slave.data), model.BEFORE+b'R'*128)
        self.assertEqual(slave.segments, [item for a in (0,64,0,64) for item in ((0xa0,a),(0xa1,))])

    def test_read_sequence_and_last_nack_without_native_model(self):
        _, slave, _, wire = self.make()
        self.assertEqual(wire.capture(), model.BEFORE*2)
        self.assertEqual(slave.segments, [item for a in (0,64,0,64) for item in ((0xa0,a),(0xa1,))])
        self.assertEqual(slave.master_acks, ([0]*63+[1])*4)
        self.assertEqual((slave.starts,slave.stops), (8,4))

    def test_no_page_ack_out_of_sequence_read_or_replay_capability(self):
        for operation in ('page','ack','read'):
            _, slave, _, wire = self.make()
            fn = dict(page=lambda:wire.page(0,bytes(8),120), ack=lambda:wire.ack(30), read=lambda:wire.read(0,64,300))[operation]
            with self.assertRaises(ValueError): fn()
            self.assertFalse(slave.edges)
            with self.assertRaises(ValueError): wire.capture()
            self.assertFalse(slave.edges)
        _, slave, _, wire = self.make()
        wire.capture()
        count = len(slave.edges)
        with self.assertRaises(ValueError): wire.capture()
        self.assertEqual(len(slave.edges), count)

    def test_failed_archive_or_log_hook_stops_before_next_read(self):
        _, slave, _, wire = self.make()
        saved = []
        def fail(index, address, data):
            saved.append(data)
            raise OSError('archive or sealed log failed')
        with self.assertRaises(OSError): wire.capture(fail)
        self.assertEqual(len(saved), 1)
        self.assertEqual(slave.segments, [(0xa0,0),(0xa1,)])
        count = len(slave.edges)
        with self.assertRaises(ValueError): wire.capture()
        self.assertEqual(len(slave.edges), count)

    def test_drift_and_elapsed_total_budget_cannot_become_stable_capture(self):
        for fault in ('drift','deadline'):
            clock, slave, _, wire = self.make()
            def hook(index, address, data):
                if index == 1:
                    if fault == 'drift': slave.data[0] ^= 1
                    else: clock.value = 901
            with self.assertRaises(ValueError): wire.capture(hook)
            self.assertEqual(wire.read_index, 4 if fault=='drift' else 2)
            self.assertFalse(wire.capture_active)


if __name__ == '__main__': unittest.main()
