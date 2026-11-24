"""Host-only map parsing and isolated repair namespace tests."""
import importlib.util
from pathlib import Path
import unittest

spec = importlib.util.spec_from_file_location("memory_fix_tested", Path(__file__).with_name("baud_memory_fix.py"))
m = importlib.util.module_from_spec(spec)
spec.loader.exec_module(m)


class MemoryTests(unittest.TestCase):
    def test_actual_memory_report_requires_real_free_space(self):
        value = m.memory_report("P34MEM: sysCapacity=5304 sysUsed=1432 lvPool=126976 lvFree=70000 lvLargest=65000\r\n")
        self.assertEqual(value["lvgl_free"], 70000)
        for line in ("P34MEM: sysCapacity=1208 sysUsed=1200 lvPool=126976 lvFree=70000 lvLargest=65000",
                     "P34MEM: sysCapacity=5304 sysUsed=5200 lvPool=126976 lvFree=70000 lvLargest=65000",
                     "P34MEM: sysCapacity=5304 sysUsed=1432 lvPool=131072 lvFree=70000 lvLargest=65000",
                     "P34MEM: sysCapacity=5304 sysUsed=1432 lvPool=126976 lvFree=1000 lvLargest=500", ""):
            with self.assertRaises(RuntimeError):
                m.memory_report(line)

    def test_unknown_header_is_only_transient_during_actual_boot(self):
        r = m.configure()
        class Link:
            ram_reads = []
            ram_writes = []
            rtt_address = None
            boot = False
            def running(self):
                if self.boot:
                    raise r.m.passive.Transition("Boot")
        link = Link()
        reader = r.m.ImageReader(link, {})
        with self.assertRaises(RuntimeError):
            reader.select(bytes(0x460))
        link.boot = True
        with self.assertRaises(r.m.passive.Transition):
            reader.select(bytes(0x460))
        self.assertEqual(link.ram_reads, [])

    def test_zero_clamped_counter_is_valid_without_repeating_probe(self):
        raw = dict(reader_closed=True, heap_base=1000, heap_limit=4208,
                   samples=[dict(lvgl_used=0, lvgl_peak=54600, system_break=2432)]*12)
        result = m.heap_evidence(raw)
        self.assertEqual(result["system_used"], 1432)
        self.assertTrue(result["requires_new_firmware_tlsf_monitor"])

    def test_invalid_break_or_incomplete_probe_rejected(self):
        raw = dict(reader_closed=False, heap_base=1000, heap_limit=4208,
                   samples=[dict(lvgl_used=0, lvgl_peak=54600, system_break=5000)]*12)
        with self.assertRaises(RuntimeError):
            m.heap_evidence(raw)

    def test_short_and_wrapped_allocations(self):
        for gap in (" ", "\n                "):
            text = " .bss.max_used" + gap + "0x200504c8 0x4 file.obj\n"
            self.assertEqual(m.map_section(text, ".bss.max_used", 4), (0x200504c8, 4))

    def test_ambiguous_or_wrong_size_is_rejected(self):
        text = " .bss.max_used 0x200504c8 0x4 file.obj\n"
        for value, size in ((text * 2, 4), (text, 8), ("", 4)):
            with self.assertRaises(RuntimeError):
                m.map_section(value, ".bss.max_used", size)

    def test_owner_disambiguates_static_break(self):
        text = " .data.current.0 0x20001000 0x4 other.obj\n .data.current.0 0x20002000 0x4 gcc_runtime_compat.obj\n"
        self.assertEqual(m.map_section(text, ".data.current.0", 4, "gcc_runtime_compat"), (0x20002000, 4))

    def test_repair_does_not_retarget_original_apk_checkout(self):
        r = m.configure()
        self.assertEqual(r.b.OUT, m.OUT)
        self.assertEqual(r.a.b.OUT, m.OUT)
        self.assertEqual(r.a.FW, m.OUT / "fw")
        self.assertEqual(r.a.RAW, m.OUT / "build/app-gcc/X-Track-App-GCC.bin")
        self.assertEqual(r.b.SRC, m.PREVIOUS / "src")
        self.assertEqual(r.PHONE, m.OUT / "runtime/phone-r1")


if __name__ == "__main__":
    unittest.main()
