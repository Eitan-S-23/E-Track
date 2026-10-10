"""Compile the production metrics core and reject missing/aliased/torn MCU data."""
import importlib.util
from pathlib import Path
import os
import shutil
import struct
import subprocess
import tempfile
import unittest
import zlib

ROOT = Path(__file__).resolve().parents[2]
spec = importlib.util.spec_from_file_location("metrics", ROOT / "Tools/ota/p34-acceptance/metrics.py")
m = importlib.util.module_from_spec(spec)
spec.loader.exec_module(m)


class Tests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        spec = importlib.util.spec_from_file_location("guard", ROOT / ".agents/skills/e-track-flutter-debug/scripts/host_io.py")
        guard = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(guard)
        parent = guard.checked_output(ROOT, ROOT / ".cache/ota-link-metrics-tests")
        parent.mkdir(parents=True, exist_ok=True)
        cls.tmp = tempfile.TemporaryDirectory(dir=parent)
        exe = guard.checked_output(ROOT, Path(cls.tmp.name) / ("metrics.exe" if os.name == "nt" else "metrics"))
        cc = shutil.which("gcc") or shutil.which("cc")
        if cc is None:
            raise RuntimeError("native C compiler required")
        subprocess.run([cc, "-std=c99", "-Wall", "-Wextra", "-Werror", "-O2",
            "-I" + str(ROOT / "USER/HAL"), str(ROOT / "tests/ota/test_ota_link_metrics.c"),
            "-o", str(exe)], cwd=ROOT, check=True, timeout=60)
        cls.log = subprocess.check_output([str(exe)], cwd=ROOT, timeout=10)
        print(cls.log.decode("ascii"), end="")
        cls.raw = bytes.fromhex(cls.log.split(b"P34_METRICS ")[1].decode().strip())

    @classmethod
    def tearDownClass(cls):
        cls.tmp.cleanup()

    def changed(self, index, value):
        data = bytearray(self.raw)
        struct.pack_into("<I", data, index * 4, value)
        struct.pack_into("<I", data, m.SIZE - 4, zlib.crc32(data[:-4]))
        return bytes(data)

    def test_real_core_and_rtt_line(self):
        value = m.from_rtt(self.log)
        self.assertTrue(value["clean"])
        self.assertEqual(value["phase"]["payload_read"]["elapsed_us"], 10)
        self.assertEqual(value["package_sha256"], "aa" * 32)
        self.assertEqual(value["epoch"], 123)

    def test_clock_counter_and_publication_fail_closed(self):
        for index, value in ((0, 0), (1, 2), (2, 336), (3, 0), (4, 1), (6, 0), (7, 0), (8, 1)):
            with self.subTest(index=index), self.assertRaises(ValueError):
                m.decode(self.changed(index, value))

    def test_missing_required_phase_and_rx_bytes_rejected(self):
        data = bytearray(self.raw)
        data[44 * 4:50 * 4] = bytes(24)
        struct.pack_into("<I", data, m.SIZE - 4, zlib.crc32(data[:-4]))
        with self.assertRaises(ValueError): m.decode(bytes(data))
        with self.assertRaises(ValueError): m.decode(self.changed(20, 100))

    def test_failure_keeps_observed_costs_not_false_clean(self):
        value = m.decode(self.changed(12, 1))
        self.assertFalse(value["clean"])
        self.assertEqual(value["phase"]["payload_program"]["calls"], 1)

    def test_torn_duplicate_missing_and_old_probe_rejected(self):
        for raw in (bytes(336), self.raw[:-1], bytes(420), self.raw[:-1] + bytes([self.raw[-1] ^ 1])):
            with self.assertRaises(ValueError): m.decode(raw)
        for log in (b"", self.log + self.log, self.log[:-3] + b"\n"):
            with self.assertRaises(ValueError): m.from_rtt(log)


if __name__ == "__main__":
    unittest.main(verbosity=2)
