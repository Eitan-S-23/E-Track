from pathlib import Path
import sys
import unittest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "Tools/ota"))
from recovery_entry.stack_audit import analyze, bound


class Stack(unittest.TestCase):
    def setUp(self):
        build = ROOT / ".cache/p34-entry-supervisor2"
        self.elf = (build / "entry.elf").read_bytes()
        self.nm = (build / "symbols.log").read_text()
        self.dis = (build / "disassembly.log").read_text()
        self.su = [p.read_text() for p in sorted(build.glob("*.su"))]

    def run_audit(self):
        return analyze(self.elf, self.nm, self.dis, self.su)

    def test_actual(self):
        r = self.run_audit()
        self.assertEqual(r["entries"]["re_supervise_once"]["software_bytes"], 288)
        self.assertEqual(r["entries"]["re_bootstrap_entry"]["software_bytes"], 0)

    def test_disassembly_drift(self):
        self.dis = self.dis.replace("b5f8", "b5f0", 1)
        with self.assertRaisesRegex(ValueError, "differs"):
            self.run_audit()

    def test_dynamic_frame(self):
        self.su = [s.replace("static", "dynamic", 1) for s in self.su]
        with self.assertRaisesRegex(ValueError, "dynamic"):
            self.run_audit()

    def test_missing_frame(self):
        self.su = []
        with self.assertRaisesRegex(ValueError, "missing target frame"):
            self.run_audit()

    def test_unknown_target(self):
        self.dis = self.dis.replace("<qualified>", "<missing>")
        # Numeric targets remain authority; renamed symbol headings lose body.
        with self.assertRaisesRegex(ValueError, "missing instructions"):
            self.run_audit()

    def test_recursion(self):
        with self.assertRaisesRegex(ValueError, "recursive"):
            bound("a", {"a": {"a"}}, {"a": 8})

    def test_tail_conservative(self):
        self.assertEqual(bound("a", {"a": {"b"}, "b": set()}, {"a": 8, "b": 16})[0], 24)


if __name__ == "__main__":
    unittest.main()
