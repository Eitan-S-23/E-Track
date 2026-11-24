"""The staging comparison must separate workloads and independent clocks."""
import copy
import io
import json
from pathlib import Path
import sys
import unittest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "Tools/ota"))
import p34_staging_erase_review as f


def fixture():
    result = {}
    for name, first, last, size, seconds, install, erase in (
        ("control", 30257, 30258, 300000, 30, 21, 3),
        ("bootstrap", 30259, 30260, 300100, 31, 38, 3),
        ("measure", 30260, 30261, 300200, 28, 22, 1)):
        result[name] = dict(input=dict(currentVersionCode=first, targetVersionCode=last,
            currentImageSha256=str(first), targetImageSha256=str(last), packageBytes=size,
            deviceAddress="AA:BB", appLifecycle="resumed"), policy=copy.deepcopy(f.POLICY),
            binding=dict(writeMode="without", mtuChunkBytes=244, mtuSource="negotiated"),
            apk_sha256="same-apk", boot_sha256="same-boot", header_only=name != "bootstrap",
            transfer_seconds=seconds, installation_reconnect_seconds=install, payload_erase_seconds=erase)
    return result


class Tests(unittest.TestCase):
    def test_separate_rates_clocks_and_install_regression(self):
        v = f.compare(fixture())
        self.assertEqual(v["transfer_seconds_saved"], 2)
        self.assertAlmostEqual(v["measure_kb_s"], 300200 / 28000)
        self.assertEqual(v["installation_reconnect_seconds_added"], 1)
        self.assertEqual(v["native_erase_seconds_saved"], 2)
        self.assertTrue(v["useful_transfer_screening_gain"])
        self.assertFalse(v["strict_same_package_ab"])
        self.assertFalse(v["transfer_target_met"])
        self.assertFalse(v["installation_target_met"])

    def reject(self, group, key, value):
        rows = fixture()
        rows[group][key] = value
        with self.assertRaises(RuntimeError):
            f.compare(rows)

    def test_missing_arm(self):
        rows = fixture()
        del rows["bootstrap"]
        with self.assertRaises(RuntimeError): f.compare(rows)

    def test_workload_role(self):
        self.reject("measure", "header_only", False)
        self.reject("bootstrap", "header_only", True)

    def test_boot_and_apk(self):
        self.reject("measure", "boot_sha256", "changed")
        self.reject("control", "apk_sha256", "changed")

    def test_policy_and_mtu(self):
        self.reject("measure", "policy", dict(f.POLICY, dataBatchFrames=12))
        self.reject("measure", "binding", dict(writeMode="without", mtuChunkBytes=20, mtuSource="fallback"))

    def test_measurement_predecessor(self):
        inp = fixture()["measure"]["input"]
        inp["currentImageSha256"] = "prepared-but-not-installed"
        self.reject("measure", "input", inp)

    def test_wrong_version_foreground_or_device(self):
        for key, value in (("targetVersionCode", 30262), ("appLifecycle", "paused"), ("deviceAddress", "CC:DD")):
            inp = fixture()["measure"]["input"]
            inp[key] = value
            self.reject("measure", "input", inp)

    def test_invalid_measurement(self):
        for key in ("transfer_seconds", "installation_reconnect_seconds", "payload_erase_seconds"):
            for value in (0, -1, True, float("nan"), float("inf")):
                self.reject("measure", key, value)

    def test_no_false_gain_from_size_or_erase_only(self):
        rows = fixture()
        rows["measure"]["input"]["packageBytes"] = 200000
        self.assertFalse(f.compare(rows)["useful_transfer_screening_gain"])
        rows = fixture()
        rows["measure"]["payload_erase_seconds"] = 4
        self.assertFalse(f.compare(rows)["useful_transfer_screening_gain"])

    def test_actual_header_only_bytes(self):
        before = bytes(2048)
        after = bytearray(before)
        after[0x410] = 1
        self.assertTrue(f.header_only(before, bytes(after)))
        after[0x500] = 1
        self.assertFalse(f.header_only(before, bytes(after)))
        self.assertFalse(f.header_only(before, before))
        with self.assertRaises(RuntimeError): f.header_only(b"short", b"short")


if __name__ == "__main__":
    f.cli.require(Path.cwd() == ROOT and sys.flags.isolated and sys.flags.no_site and sys.dont_write_bytecode,
                  "explicit isolated root required")
    s = f.cli.Store(ROOT)
    out = s.checked(Path(sys.argv[1]))
    f.cli.require(not out.exists(), "preserve test output")
    stream = io.StringIO()
    result = unittest.TextTestRunner(stream=stream, verbosity=2).run(unittest.defaultTestLoader.loadTestsFromTestCase(Tests))
    s.raw(out / "tests.log", stream.getvalue().encode())
    s.write(out / "result.json", dict(result="PASS" if result.wasSuccessful() else "FAIL", tests=result.testsRun,
        source=f.cli.record(f.__file__), test=f.cli.record(__file__), hardware=False))
    print(stream.getvalue())
    sys.exit(not result.wasSuccessful())
