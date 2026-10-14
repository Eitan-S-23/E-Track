"""Compile the production metrics core and reject missing/aliased/torn MCU data."""
import importlib.util
import hashlib
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

# Byte-exact record from round11/ops/cmd-q-transfer/mcu/transfer.rtt.
# Source SHA-256: 7bb961716dfc19bf08b3f1831547f31b83b68131ecbc6e9ab160675a160fe2cd
V11_RECORD_SHA256 = "f308da01443ee7fcd9063816b09ea403a951832a01b3b4d808f0dd2207aaad55"
V11_FIXTURE = ROOT / "tests/ota/fixtures/p34-v11-metrics.hex"


def v11_record():
    raw = bytes.fromhex(V11_FIXTURE.read_text(encoding="ascii"))
    if hashlib.sha256(raw).hexdigest() != V11_RECORD_SHA256:
        raise ValueError("original v11 fixture identity changed")
    return raw


class Tests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        spec = importlib.util.spec_from_file_location("guard", ROOT / ".agents/skills/e-track-flutter-debug/scripts/host_io.py")
        guard = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(guard)
        parent = guard.checked_output(ROOT, Path(os.environ.get("P34_HOST_TEST_OUT",
                                                               ROOT / ".cache/ota-link-metrics-tests")))
        parent.mkdir(parents=True, exist_ok=True)
        cls.tmp = tempfile.TemporaryDirectory(dir=parent)
        exe = guard.checked_output(ROOT, Path(cls.tmp.name) / ("metrics.exe" if os.name == "nt" else "metrics"))
        cc = shutil.which("gcc") or shutil.which("cc")
        if cc is None:
            raise RuntimeError("native C compiler required")
        sources = ["tests/ota/test_ota_link_metrics.c", "Libraries/OTA/ota_ble_session.c",
            "Libraries/OTA/ota_ble_frame.c", "Libraries/OTA/ota_ble_ring.c", "Libraries/OTA/ota_sd.c",
            "Libraries/OTA/ota_staging.c", "boot/src/boot_crc32.c", "boot/src/boot_sha256.c"]
        command = [cc, "-std=c99", "-Wall", "-Wextra", "-Werror", "-O2",
            *("-I" + str(ROOT / name) for name in ("USER/HAL", "Libraries", "boot/include")),
            *(str(ROOT / name) for name in sources), "-o", str(exe)]
        print("METRICS_COMPILE " + subprocess.list2cmdline(command), flush=True)
        subprocess.run(command, cwd=ROOT, check=True, timeout=60)
        cls.exe = exe
        cls.log = subprocess.check_output([str(exe)], cwd=ROOT, timeout=10)
        print(cls.log.decode("ascii"), end="")
        cls.raw = bytes.fromhex(cls.log.split(b"P34_METRICS ")[1].decode().strip())
        cls.v11 = v11_record()

    @classmethod
    def tearDownClass(cls):
        cls.tmp.cleanup()

    def changed(self, index, value, *, source=None):
        data = bytearray(self.raw if source is None else source)
        struct.pack_into("<I", data, index * 4, value)
        struct.pack_into("<I", data, m.SIZE - 4, zlib.crc32(data[:-4]))
        return bytes(data)

    def test_real_core_and_rtt_line(self):
        value = m.from_rtt(self.log)
        self.assertTrue(value["clean"])
        self.assertEqual(value["phase"]["payload_read"]["elapsed_us"], 10)
        self.assertEqual(value["package_sha256"], "aa" * 32)
        self.assertEqual(value["epoch"], 123)

    def test_zero_origin_session_uses_independent_verify_without_payload_read(self):
        log = subprocess.check_output([str(self.exe), "zero-verify"], cwd=ROOT, timeout=10)
        print(log.decode("ascii"), end="")
        value = m.from_rtt(log)
        self.assertTrue(value["clean"])
        self.assertEqual(value["initial_durable"], 0)
        self.assertEqual(value["final_durable"], 8192)
        self.assertEqual(value["phase"]["payload_read"]["calls"], 0)
        self.assertIsNone(value["phase"]["payload_read"]["elapsed_us"])
        for phase in ("payload_program", "payload_erase", "payload_verify"):
            self.assertEqual(value["phase"][phase]["calls"], 2)
            self.assertEqual(value["phase"][phase]["bytes_requested"], 8192)

    def test_hash_bound_real_v11_zero_origin_record(self):
        value = m.from_rtt(b"P34_METRICS " + self.v11.hex().encode("ascii") + b"\n")
        self.assertTrue(value["clean"])
        self.assertEqual((value["initial_durable"], value["final_durable"], value["terminal"]), (0, 1048576, 0))
        self.assertEqual(value["package_sha256"], "8373305b6817081106ad35c840ef87bf2d4210ffa2e8b9e881e0799ad1ff9e47")
        read = value["phase"]["payload_read"]
        self.assertEqual((read["calls"], read["errors"], read["bytes_requested"], read["cycles"], read["max_cycles"]), (0, 0, 0, 0, 0))
        self.assertIsNone(read["elapsed_us"])
        self.assertIsNone(read["max_us"])
        for phase in ("payload_program", "payload_erase", "payload_verify"):
            self.assertEqual(value["phase"][phase]["calls"], 256)
            self.assertEqual(value["phase"][phase]["bytes_requested"], 1048576)
        print("V11_RECORD sha256=" + V11_RECORD_SHA256 + " decode=PASS payload_read_timing=null")

    def test_clock_counter_and_publication_fail_closed(self):
        for index, value in ((0, 0), (1, 2), (2, 336), (3, 0), (4, 1), (6, 0), (7, 0), (8, 1)):
            with self.subTest(index=index), self.assertRaises(ValueError):
                m.decode(self.changed(index, value))

    def test_missing_required_phase_and_rx_bytes_rejected(self):
        for source in (self.raw, self.v11):
            for phase in ("payload_program", "payload_erase", "payload_verify",
                          "journal_read", "journal_program", "uart_rx_irq", "ack_tx"):
                data = bytearray(source)
                start = (44 + m.PHASES.index(phase) * 6) * 4
                data[start:start + 24] = bytes(24)
                struct.pack_into("<I", data, m.SIZE - 4, zlib.crc32(data[:-4]))
                with self.subTest(phase=phase), self.assertRaises(ValueError):
                    m.decode(bytes(data))
                print("MISSING_PHASE_REJECT phase=%s sha256=%s" % (phase, hashlib.sha256(data).hexdigest()))
        with self.assertRaises(ValueError): m.decode(self.changed(20, 100))

    def test_v11_clock_state_and_counter_negatives_remain_rejected(self):
        mutations = [(0, 0), (1, 2), (2, 336), (3, 0), (4, 1), (5, 0), (6, 0),
            (7, 0), (8, 1), (9, 0), (10, 1), (11, 0), (12, 2), (13, 0), (14, 0),
            (15, 0), (16, 1048577), (17, 1048575), (20, 1),
            (45, 1), (46, 1), (47, 1), (49, 1),  # Uncalled read must stay entirely zero.
            (51, 257), (53, 0), (55, 0xffffffff)]  # errors > calls, missing time, max > sum.
        for index, value in mutations:
            raw = self.changed(index, value, source=self.v11)
            with self.subTest(index=index), self.assertRaises(ValueError):
                m.decode(raw)
            print("V11_REJECT word=%d value=%d sha256=%s" % (index, value, hashlib.sha256(raw).hexdigest()))
        damaged = self.v11[:-1] + bytes([self.v11[-1] ^ 1])
        with self.assertRaisesRegex(ValueError, "CRC"):
            m.decode(damaged)
        print("V11_REJECT crc sha256=" + hashlib.sha256(damaged).hexdigest())

    def test_unclean_v11_keeps_phase_and_transport_errors(self):
        for index in (22, 23, 24, 25, 26, 37, 51):
            with self.subTest(index=index):
                value = m.decode(self.changed(index, 1, source=self.v11))
                self.assertFalse(value["clean"])
                self.assertGreater(value["phase"]["payload_verify"]["elapsed_us"], 0)

    def test_called_payload_read_still_requires_measured_time(self):
        raw = self.changed(44, 1, source=self.v11)
        with self.assertRaisesRegex(ValueError, "missing required MCU stage"):
            m.decode(raw)
        print("CALLED_READ_WITHOUT_TIME_REJECT sha256=" + hashlib.sha256(raw).hexdigest())

    def test_framing_can_precede_semantics_but_not_accept_short_or_ambiguous_data(self):
        log = b"P34_METRICS " + b"0" * 840 + b"\n"
        self.assertEqual(m.raw_from_rtt(log), bytes(420))
        with self.assertRaises(ValueError):
            m.from_rtt(log)
        for bad in (b"", log + log, log[:-3] + b"\n", log.replace(b"00", b"gg", 1)):
            with self.assertRaises(ValueError):
                m.raw_from_rtt(bad)

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
