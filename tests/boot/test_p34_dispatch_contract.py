from pathlib import Path
import os
import struct
import sys
import unittest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "Tools/ota"))
from recovery_entry.load_contract import inspect
from recovery_entry.stack_audit import analyze


class DispatchContract(unittest.TestCase):
    def setUp(self):
        self.build = Path(os.environ["RE_ENTRY_TEST_BUILD"])
        self.capability = os.environ.get("RE_ENTRY_TEST_CAPABILITY", "nor")
        self.elf = bytearray((self.build / "entry.elf").read_bytes())
        self.ph = struct.unpack_from("<I", self.elf, 28)[0]
        self.code = struct.unpack_from("<I", self.elf, self.ph+32+4)[0]

    def check(self):
        return inspect(self.elf, dispatched=self.capability == "nor", bcb_capture=self.capability == "bcb")

    def test_actual(self):
        end = "0x2006254c" if self.capability == "bcb" else "0x20062040"
        self.assertEqual(self.check()["zero_ranges"], [["0x20062000", end]])

    def test_scaffold_not_dispatch(self):
        old = (ROOT / ".cache/p34-entry-supervisor2/entry.elf").read_bytes()
        with self.assertRaisesRegex(ValueError, "BSS"):
            inspect(old, dispatched=True)

    def test_lma_outside(self):
        struct.pack_into("<I", self.elf, self.ph+12, 0x08000000)
        with self.assertRaisesRegex(ValueError, "LMA"):
            self.check()

    def test_zero_loop_overwrites_input(self):
        struct.pack_into("<I", self.elf, self.code+0xa0, 0x20062900)
        with self.assertRaisesRegex(ValueError, "zero-loop"):
            self.check()

    def test_zero_loop_misses_state(self):
        end = 0x20062148 if self.capability == "bcb" else 0x20062004
        struct.pack_into("<I", self.elf, self.code+0xa0, end)
        with self.assertRaisesRegex(ValueError, "zero-loop"):
            self.check()

    def test_stack_overlap(self):
        struct.pack_into("<I", self.elf, self.ph+64+20, 0x5000)
        with self.assertRaises(ValueError):
            self.check()

    def test_vector(self):
        vectors = struct.unpack_from("<I", self.elf, self.ph+4)[0]
        struct.pack_into("<I", self.elf, vectors+12, 0x08000101)
        with self.assertRaisesRegex(ValueError, "vector"):
            self.check()

    def test_chain_includes_dispatch(self):
        report = analyze(self.elf, (self.build / "symbols.log").read_text(),
                         (self.build / "disassembly.log").read_text(),
                         [p.read_text() for p in sorted(self.build.glob("*.su"))], capability=self.capability)
        path = report["entries"]["re_bootstrap_entry"]["chain"]
        if self.capability == "bcb":
            self.assertIn("re_bcb_entry_dispatch", path)
            self.assertIn("re_bcb_dispatch_once", path)
            self.assertIn("re_capture_target_once", path)
        else:
            self.assertIn("re_entry_dispatch", path)
            self.assertIn("re_dispatch_once", path)
            self.assertIn("re_supervise_once", path)


if __name__ == "__main__":
    unittest.main()
