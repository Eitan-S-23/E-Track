"""Parser checks only, not target stack or entry acceptance."""
from pathlib import Path
import struct
import sys
import unittest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "Tools/ota"))
from p34_recovery_entry_audit import load_segments


def fixture(*, kind=1, size=4, memory=16, address=0x20058000, machine=40):
    data = bytearray(88)
    data[:7] = b"\x7fELF\x01\x01\x01"
    struct.pack_into("<HHIIIIIHHHHHH", data, 16,
                     2, machine, 1, address, 52, 0, 0, 52, 32, 1, 0, 0, 0)
    struct.pack_into("<IIIIIIII", data, 52,
                     kind, 84, address, address, size, memory, 5, 4)
    return bytes(data)


class LoadSegments(unittest.TestCase):
    def test_memory_extent_includes_zero_fill(self):
        record, = load_segments(fixture())
        self.assertEqual(record["file_bytes"], 4)
        self.assertEqual(record["end"], 0x20058010)

    def test_wrong_architecture(self):
        with self.assertRaises(ValueError):
            load_segments(fixture(machine=3))

    def test_wrong_encoding(self):
        with self.assertRaises(ValueError):
            load_segments(b"invalid")

    def test_truncated_table(self):
        with self.assertRaises(ValueError):
            load_segments(fixture()[:60])

    def test_payload_outside_file(self):
        with self.assertRaises(ValueError):
            load_segments(fixture(size=8))

    def test_memory_smaller_than_file(self):
        with self.assertRaises(ValueError):
            load_segments(fixture(memory=2))

    def test_address_wrap(self):
        with self.assertRaises(ValueError):
            load_segments(fixture(address=0xFFFFFFF8))

    def test_no_load_segments(self):
        with self.assertRaises(ValueError):
            load_segments(fixture(kind=4))


if __name__ == "__main__":
    unittest.main()
