"""Keep public, internal and native clocks separate in PHY screening reviews."""
import copy
import io
from pathlib import Path
import sys
import unittest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "Tools/ota"))
import p34_phy_review as f


def messages(start=100, end=5869999, reboot=25869999):
    return (f"OTA_MONO MONO_BUDGET_START monoUs={start} wallUs=999999\n"
            f"OTA_MONO MONO_END_ACK_OK monoUs={end} wallUs=1 durable=293495\n"
            f"OTA_MONO MONO_REBOOT_VERIFIED monoUs={reboot} wallUs=8\n")


class Tests(unittest.TestCase):
    def test_original_closed_trials_end_to_end(self):
        store = f.cli.Store(ROOT)
        current = f.sample(store, f.CURRENT)
        self.assertEqual(current["phy"]["observation"]["txPhy"], 2)
        self.assertEqual(current["phy"]["observation"]["rxPhy"], 2)
        self.assertEqual(current["public_minus_internal_transfer_us"], 2941)
        self.assertAlmostEqual(current["public"]["transfer_seconds"], 17.015007)
        self.assertAlmostEqual(current["public"]["installation_reconnect_seconds"], 21.959865)
        for root in f.CONTROLS.values():
            result = f.compare(f.sample(store, root), current)
            self.assertFalse(result["whole_upgrade_screening_gain"])
            self.assertFalse(result["causal_phy_speedup_proven"])

    def test_monotonic_not_wall_clock(self):
        v = f.public_metrics(messages(), 293495)
        self.assertAlmostEqual(v["transfer_seconds"], 5.869899)
        self.assertEqual(v["installation_reconnect_seconds"], 20)
        self.assertTrue(v["transfer_target_met"])
        self.assertTrue(v["installation_target_met"])

    def test_public_exact_thresholds(self):
        self.assertTrue(f.public_metrics(messages(end=5870000), 293495)["transfer_target_met"])
        self.assertFalse(f.public_metrics(messages(end=5870001), 293495)["transfer_target_met"])
        self.assertFalse(f.public_metrics(messages(reboot=25870000), 293495)["installation_target_met"])

    def test_reject_missing_duplicate_wrong_durable(self):
        good = messages()
        for bad in (good.split("\n", 1)[1], good + good, good.replace("293495", "293494"),
                    good.replace("wallUs=1 ", "wallUs=bad ")):
            with self.assertRaises(RuntimeError): f.public_metrics(bad, 293495)

    def test_reject_bad_clock_or_size(self):
        for bad in (messages(end=100), messages(start=1000, end=999), messages(reboot=200)):
            with self.assertRaises(RuntimeError): f.public_metrics(bad, 293495)
        for size in (True, 0, -1, 1.5, 1048577):
            with self.assertRaises(RuntimeError): f.public_metrics(messages(), size)

    def test_origin_shift_does_not_change_durations(self):
        self.assertEqual(f.public_metrics(messages(100, 200, 300), 293495),
                         f.public_metrics(messages(1100, 1200, 1300), 293495))

    def test_faster_transfer_can_have_slower_whole_upgrade(self):
        a = dict(public=f.public_metrics(messages(0, 18000000, 38000000), 293495),
                 apk_sha256="a", input=dict(packageSha256="b"))
        b = dict(public=f.public_metrics(messages(0, 17000000, 39000000), 293495),
                 apk_sha256="c", input=dict(packageSha256="d"))
        v = f.compare(a, b)
        self.assertGreater(v["throughput_gain_percent"], 0)
        self.assertFalse(v["whole_upgrade_screening_gain"])
        self.assertEqual(v["total_seconds_saved"], -1)
        self.assertTrue(v["apk_changed"])
        self.assertFalse(v["causal_phy_speedup_proven"])

    def test_internal_and_native_timing_not_added(self):
        a = dict(public=f.public_metrics(messages(), 293495), apk_sha256="a", input=dict(packageSha256="b"))
        b = copy.deepcopy(a)
        expected = f.compare(a, b)
        b.update(internal_transfer_seconds=1, native_profile=dict(installation=999999))
        self.assertEqual(f.compare(a, b), expected)


if __name__ == "__main__":
    f.cli.require(Path.cwd() == ROOT and sys.flags.isolated and sys.flags.no_site and sys.dont_write_bytecode,
                  "explicit isolated root required")
    s = f.cli.Store(ROOT)
    out = s.checked(Path(sys.argv[1]))
    f.cli.require(not out.exists(), "preserve tests")
    for name in ("tests.log", "result.json"): s.checked(out / name)
    stream = io.StringIO()
    result = unittest.TextTestRunner(stream=stream, verbosity=2).run(unittest.defaultTestLoader.loadTestsFromTestCase(Tests))
    s.raw(out / "tests.log", stream.getvalue().encode())
    s.write(out / "result.json", dict(result="PASS" if result.wasSuccessful() else "FAIL", tests=result.testsRun,
        source=f.cli.record(f.__file__), test=f.cli.record(__file__), device_operations=0))
    print(stream.getvalue())
    sys.exit(not result.wasSuccessful())
