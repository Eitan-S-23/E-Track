from pathlib import Path
import struct
import sys
import unittest
ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "Tools/ota/recovery_entry"))
from load_contract import inspect, context_ok


class Contract(unittest.TestCase):
    def setUp(self):
        self.data = bytearray((ROOT / ".cache/p34-entry-bootstrap3/entry.elf").read_bytes())

    def test_actual(self):
        self.assertFalse(inspect(self.data)["device_execute_ready"])

    def test_lma_outside(self):
        ph = struct.unpack_from("<I", self.data, 28)[0]
        struct.pack_into("<I", self.data, ph+12, 0x08000000)
        with self.assertRaisesRegex(ValueError, "LMA"):
            inspect(self.data)

    def test_wrong_entry(self):
        struct.pack_into("<I", self.data, 24, 0x20060405)
        with self.assertRaises(ValueError):
            inspect(self.data)

    def test_wrong_vector(self):
        ph = struct.unpack_from("<I", self.data, 28)[0]
        off = struct.unpack_from("<I", self.data, ph+4)[0]
        struct.pack_into("<I", self.data, off+8, 0x08000101)
        with self.assertRaises(ValueError):
            inspect(self.data)

    def test_zero_range_overlaps_stack(self):
        sh = struct.unpack_from("<I", self.data, 32)[0]
        count = struct.unpack_from("<H", self.data, 48)[0]
        for i in range(count):
            if struct.unpack_from("<I", self.data, sh+i*40+4)[0] == 8:
                struct.pack_into("<I", self.data, sh+i*40+12, 0x20064000)
        with self.assertRaises(ValueError):
            inspect(self.data)

    def test_context(self):
        args = dict(ipsr=0, control=0, primask=1, msp=0x20057f00, fpccr=0)
        self.assertTrue(context_ok(**args))
        for key, value in (("control", 2), ("control", 4), ("control", 1),
                           ("ipsr", 3), ("primask", 0), ("msp", 0x20066000),
                           ("msp", 0x200570d0), ("fpccr", 1)):
            with self.subTest(key=key, value=value):
                self.assertFalse(context_ok(**dict(args, **{key: value})))

    def test_missing_old_stack_margin(self):
        ph = struct.unpack_from("<I", self.data, 28)[0]
        off = struct.unpack_from("<I", self.data, ph+32+4)[0]
        struct.pack_into("<I", self.data, off+0x84, 0x20057000)
        with self.assertRaisesRegex(ValueError, "margin"):
            inspect(self.data)


if __name__ == "__main__":
    unittest.main()
