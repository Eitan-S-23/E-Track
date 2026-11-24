"""Reject mixed receiver workloads/identities and overlapping timing arithmetic."""
import copy
import io
from pathlib import Path
import sys
import unittest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "Tools/ota"))
import p34_receiver_review as f


def fixture():
    rows = {}
    for name, version, size, seconds, install in (
        ("control", 30260, 300000, 30, 22),
        ("bootstrap", 30261, 300100, 31, 38),
        ("measure", 30262, 300200, 28, 21)):
        rows[name] = dict(input=dict(currentVersionCode=version, targetVersionCode=version + 1,
            currentImageSha256=format(version, "064x"), targetImageSha256=format(version + 1, "064x"),
            packageBytes=size, deviceAddress="AA:BB", appLifecycle="resumed"),
            policy=copy.deepcopy(f.staging.POLICY),
            binding=dict(writeMode="without", mtuChunkBytes=244, mtuSource="negotiated"),
            apk_sha256="same-apk", boot_sha256="same-boot", header_only=name != "bootstrap",
            transfer_seconds=seconds, installation_reconnect_seconds=install, payload_erase_seconds=1.6)
    return rows


def native():
    return dict(clean_counters=True, clock_ok=1, clock_hz=1000, pump_entries=11,
                pump_gap_cycles_lo=10000, pump_gap_cycles_hi=0, pump_gap_max_cycles=2000,
                phases=dict(pump_work=dict(calls=11, errors=0, seconds=3)))


class Tests(unittest.TestCase):
    def reject(self, path, value):
        rows = fixture()
        target = rows
        for key in path[:-1]: target = target[key]
        target[path[-1]] = value
        with self.assertRaises(RuntimeError): f.compare(rows)

    def test_rates_and_separate_clocks(self):
        rows = fixture()
        result = f.compare(rows)
        self.assertEqual(result["transfer_seconds_saved"], 2)
        self.assertAlmostEqual(result["measure_kb_s"], 300200 / 28000)
        self.assertEqual(result["installation_reconnect_seconds_added"], -1)
        self.assertTrue(result["useful_transfer_screening_gain"])
        self.assertFalse(result["strict_same_package_ab"])
        self.assertFalse(result["independent_acceptance"])
        self.assertFalse(result["transfer_target_met"])
        self.assertFalse(result["installation_target_met"])
        rows["measure"]["pump"] = dict(work_seconds=500, gap_seconds=900)
        self.assertEqual(f.compare(rows), result)

    def test_missing_role(self):
        rows = fixture(); del rows["bootstrap"]
        with self.assertRaises(RuntimeError): f.compare(rows)

    def test_identity_policy_and_device(self):
        for role in fixture():
            for key in ("apk_sha256", "boot_sha256"):
                self.reject((role, key), "changed")
            self.reject((role, "input", "deviceAddress"), "CC:DD")
            self.reject((role, "policy", "dataBatchFrames"), 12)
            self.reject((role, "binding", "mtuChunkBytes"), 20)
            self.reject((role, "input", "appLifecycle"), "paused")

    def test_both_predecessors_and_versions(self):
        for role in ("bootstrap", "measure"):
            self.reject((role, "input", "currentImageSha256"), "f" * 64)
            self.reject((role, "input", "currentVersionCode"), 1)
        self.reject(("control", "input", "targetVersionCode"), True)

    def test_workloads(self):
        for role in fixture():
            self.reject((role, "header_only"), role == "bootstrap")

    def test_invalid_times_sizes_and_hashes(self):
        for key in ("transfer_seconds", "installation_reconnect_seconds", "payload_erase_seconds"):
            for value in (0, -1, True, float("nan"), float("inf")):
                self.reject(("measure", key), value)
        for value in (0, True, 1048577, 1.5):
            self.reject(("measure", "input", "packageBytes"), value)
        self.reject(("control", "input", "currentImageSha256"), "wrong-domain")

    def test_size_normalization_not_duration_only(self):
        rows = fixture(); rows["measure"]["input"]["packageBytes"] = 200000
        self.assertFalse(f.compare(rows)["useful_transfer_screening_gain"])

    def test_target_boundaries(self):
        rows = fixture(); rows["measure"].update(transfer_seconds=6.004, installation_reconnect_seconds=20)
        result = f.compare(rows)
        self.assertTrue(result["transfer_target_met"])
        self.assertTrue(result["installation_target_met"])

    def test_native_gap_clock(self):
        result = f.pump_profile(native())
        self.assertEqual(result["gap_seconds"], 10)
        self.assertEqual(result["work_seconds"], 3)
        self.assertEqual(result["mean_gap_seconds"], 10 / 11)
        self.assertEqual(result["max_gap_seconds"], 2)
        value = native(); value.update(pump_gap_cycles_hi=1, pump_gap_max_cycles=1000000000)
        self.assertEqual(f.pump_profile(value)["gap_seconds"], (2**32 + 10000) / 1000)

    def test_begin_inside_pump_has_one_extra_work_call(self):
        value = native(); value["phases"]["pump_work"]["calls"] = 12
        self.assertEqual(f.pump_profile(value)["work_calls"], 12)
        value["phases"]["pump_work"]["calls"] = 13
        with self.assertRaises(RuntimeError): f.pump_profile(value)

    def test_native_invalid_samples(self):
        for key, value in (("clock_hz", 0), ("pump_entries", 1), ("clean_counters", False),
                           ("clock_ok", 0), ("pump_gap_cycles_hi", -1),
                           ("pump_gap_max_cycles", 100), ("pump_gap_cycles_lo", True)):
            sample = native(); sample[key] = value
            with self.assertRaises(RuntimeError): f.pump_profile(sample)
        for key, value in (("calls", 10), ("errors", 1), ("seconds", float("nan"))):
            sample = native(); sample["phases"]["pump_work"][key] = value
            with self.assertRaises(RuntimeError): f.pump_profile(sample)


if __name__ == "__main__":
    f.cli.require(Path.cwd() == ROOT and sys.flags.isolated and sys.flags.no_site and sys.dont_write_bytecode,
                  "explicit isolated root required")
    store = f.cli.Store(ROOT)
    out = store.checked(Path(sys.argv[1]))
    f.cli.require(not out.exists(), "preserve test output")
    stream = io.StringIO()
    result = unittest.TextTestRunner(stream=stream, verbosity=2).run(unittest.defaultTestLoader.loadTestsFromTestCase(Tests))
    store.raw(out / "tests.log", stream.getvalue().encode())
    store.write(out / "result.json", dict(result="PASS" if result.wasSuccessful() else "FAIL",
        tests=result.testsRun, source=f.cli.record(f.__file__), test=f.cli.record(__file__), hardware=False))
    print(stream.getvalue())
    sys.exit(not result.wasSuccessful())
