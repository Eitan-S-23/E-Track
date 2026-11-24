"""Deterministic read-only startup probe checks; no native library is loaded."""
import importlib.util
from pathlib import Path
import struct
import unittest

spec = importlib.util.spec_from_file_location("startup_tested", Path(__file__).with_name("baud_startup_trace.py"))
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)


class Link:
    def __init__(self):
        self.ram_reads = []
        self.prefix, self.tick, self.loops, self.cfsr = b"x" * 0x460, 2000, 0, 0
        self.reads = []
        self.p = dict(version=30208, prefix=self.prefix, tick=0x20000100, health=0x20000200,
                      state=0x20000300, sd_ready=0x20000400, rtt=0x20000500)
        self.running_calls = 0

    def running(self):
        self.running_calls += 1

    def read(self, address, size):
        self.reads.append((address, size))
        values = {module.APP: self.prefix, self.p["tick"]: struct.pack("<I", self.tick),
                  self.p["health"]: struct.pack("<9I", 30000, 30, 1000, 0, self.loops, self.loops, 0, 1, int(self.loops > 0)),
                  self.p["state"]: b"\x03\x01\x00", self.p["sd_ready"]: b"\x01",
                  module.PCSR: struct.pack("<I", 0x08041234), module.ICSR: struct.pack("<I", 0),
                  module.CFSR: struct.pack("<5I", self.cfsr, 0, 0, 0, 0)}
        return values.get(address, bytes(size))


class ProbeTests(unittest.TestCase):
    def test_stalled_startup_preserves_stack_without_writes(self):
        link = Link()
        probe = module.StartupProbe(link, [link.p])
        sample = probe.sample()
        self.assertEqual(len(sample["stack_top_4k"]), 8192)
        self.assertEqual(sample["health"][4], 0)
        self.assertEqual(link.running_calls, 2)
        self.assertNotIn("stack_top_4k", probe.sample())

    def test_running_loop_does_not_dump_stack(self):
        link = Link()
        link.loops = 10
        self.assertNotIn("stack_top_4k", module.StartupProbe(link, [link.p]).sample())

    def test_fault_forces_stack_snapshot(self):
        link = Link()
        link.loops, link.cfsr = 10, 0x200
        self.assertIn("stack_top_4k", module.StartupProbe(link, [link.p]).sample())

    def test_new_boot_gets_new_snapshot(self):
        link = Link()
        probe = module.StartupProbe(link, [link.p])
        probe.sample()
        link.tick = 1600
        sample = probe.sample()
        self.assertEqual(sample["epoch"], 1)
        self.assertIn("stack_top_4k", sample)

    def test_baseline_excluded_by_default(self):
        link = Link()
        link.p["version"] = 30207
        self.assertIsNone(module.StartupProbe(link, [link.p]).sample())

    def test_unknown_image_reads_no_symbols(self):
        link = Link()
        link.p["prefix"] = b"y" * 0x460
        self.assertIsNone(module.StartupProbe(link, [link.p]).sample())
        self.assertEqual(link.reads, [(module.APP, 0x460)])

    def test_sampling_has_finite_bound(self):
        link = Link()
        probe = module.StartupProbe(link, [link.p])
        probe.count = 240
        self.assertIsNone(probe.sample())
        self.assertEqual(link.reads, [])


if __name__ == "__main__":
    unittest.main()
