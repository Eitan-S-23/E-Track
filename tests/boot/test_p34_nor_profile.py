from pathlib import Path
import sys
import unittest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT/'Tools/ota'))
from recovery_entry import nor_profile as p


class ProfileTests(unittest.TestCase):
    def setUp(self): self.raw = (ROOT/'.cache/p34-host-nor-read1/sfdp.bin').read_bytes()
    def test_physical_profile_and_timing(self):
        v = p.pinned(self.raw)
        self.assertEqual(v['density_bytes'], 16*1024*1024)
        self.assertEqual(v['address_bytes'], 3)
        self.assertEqual(v['page_bytes'], 256)
        self.assertEqual([(e['bytes'], e['opcode'], e['maximum_ms']) for e in v['erases']],
                         [(4096, 0x20, 896), (32768, 0x52, 1792), (65536, 0xd8, 2240)])
        self.assertEqual(v['page_program_maximum_us'], 4224)
        self.assertEqual(v['qer'], 4)
        self.assertFalse(v['device_write_admitted'])
        self.assertFalse(v['qer_used_for_configuration'])
    def test_truncated_absent_or_unknown_header_rejected(self):
        for raw in (b'', b'\xff'*256, self.raw[:15], self.raw[:190], self.raw[:7]+b'\0'+self.raw[8:]):
            with self.assertRaises(ValueError): p.decode(raw)
    def test_bfpt_pointer_outside_capture_requires_more_evidence(self):
        raw = bytearray(self.raw); raw[12:15] = b'\0\1\0'
        with self.assertRaisesRegex(ValueError, 'additional'): p.decode(bytes(raw))
    def test_geometry_changes_not_admitted(self):
        for offset, value in ((8, 1), (11, 9), (130, 0xfd), (132, 0), (156, 13), (169, 0)):
            raw = bytearray(self.raw); raw[offset] = value
            with self.assertRaises(ValueError): p.pinned(bytes(raw))
    def test_all_physical_profile_byte_changes_reject(self):
        for i in range(256):
            raw = bytearray(self.raw); raw[i] ^= 1
            with self.assertRaises(ValueError): p.pinned(bytes(raw))


if __name__ == '__main__': unittest.main()
