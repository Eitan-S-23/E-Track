from pathlib import Path
import os
import re
import struct
import sys
import unittest
import zlib

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "Tools/ota"))
from recovery_entry.report import decode_bcb


class Reports(unittest.TestCase):
    def setUp(self):
        self.build = Path(os.environ["RE_ENTRY_TEST_BUILD"])
        self.raw = self.read(0)

    def read(self, number):
        text = (self.build / ("bcb_%d.log" % number)).read_text()
        fields = re.findall(r"(?m)^BCB_REPORT_HEX=([0-9a-f]+)$", text)
        self.assertEqual(len(fields), 1)
        return bytes.fromhex(fields[0])

    def decode(self, raw):
        return decode_bcb(raw, expected_epoch=3, expected_operation=b"\x27" * 32)

    def test_all_c_reports(self):
        for n in range(12):
            with self.subTest(scenario=n):
                r = self.decode(self.read(n))
                self.assertEqual(r["capture_complete"], n in (0, 11))
                self.assertFalse(r["device_permission"])

    def test_truncated(self):
        for size in (0, 28, 60, 315):
            with self.assertRaisesRegex(ValueError, "size"):
                self.decode(self.raw[:size])

    def test_identity_and_marker(self):
        for index in (4, 24, 28):
            raw = bytearray(self.raw); raw[index] ^= 1
            with self.assertRaises(ValueError): self.decode(bytes(raw))

    def test_changed_pair(self):
        raw = bytearray(self.raw); raw[188] ^= 1
        with self.assertRaisesRegex(ValueError, "changed"):
            self.decode(bytes(raw))

    def test_forged_active(self):
        raw = bytearray(self.raw); struct.pack_into("<I", raw, 20, 2)
        with self.assertRaisesRegex(ValueError, "arbiter"):
            self.decode(bytes(raw))

    def test_both_invalid_is_not_admitted(self):
        raw = bytearray(self.raw); raw[60:] = bytes(256); struct.pack_into("<I", raw, 20, 0)
        r = self.decode(bytes(raw))
        self.assertTrue(r["capture_complete"])
        self.assertFalse(r["bcb_admitted"])

    def test_sequences(self):
        for a, b, active in ((8, 7, 1), (7, 8, 2), (9, 9, 1), (65535, 0, 2),
                             (0, 65535, 1), (0x8000, 0, 2)):
            raw = bytearray(self.raw)
            for base, seq in ((60, a), (124, b), (188, a), (252, b)):
                struct.pack_into("<H", raw, base+8, seq)
                struct.pack_into("<I", raw, base+60, zlib.crc32(raw[base:base+60]))
            struct.pack_into("<I", raw, 20, active)
            self.assertEqual(self.decode(bytes(raw))["active"], active)

    def test_failure_cannot_claim_stability(self):
        raw = bytearray(self.read(1)); struct.pack_into("<I", raw, 16, 1)
        with self.assertRaisesRegex(ValueError, "failed"):
            self.decode(bytes(raw))


if __name__ == "__main__":
    unittest.main()
