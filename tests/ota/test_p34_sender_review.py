"""A sender screen cannot mix receiver workloads or report local-only savings."""
import io
from pathlib import Path
import sys
import unittest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "Tools/ota"))
import p34_sender_review as f


def fixture():
    result = {}
    for name, first, frames, size, elapsed in (("control", 30262, 3, 300000, 18), ("measure", 30263, 12, 300200, 17)):
        result[name] = dict(policy=dict(f.receiver.staging.POLICY, dataBatchFrames=frames),
            binding=dict(writeMode="without", mtuChunkBytes=244, mtuSource="negotiated"),
            header_only=True, apk_sha256="same-apk", boot_sha256="same-boot",
            transfer_seconds=elapsed, installation_reconnect_seconds=21,
            input=dict(currentVersionCode=first, targetVersionCode=first + 1,
                       currentImageSha256=format(first, "064x"), targetImageSha256=format(first + 1, "064x"),
                       packageSha256=format(first + 100, "064x"), packageBytes=size,
                       deviceAddress="AA:BB", appLifecycle="resumed"))
    return result


class Tests(unittest.TestCase):
    def reject(self, path, value):
        rows = fixture()
        target = rows["measure"]
        for key in path[:-1]: target = target[key]
        target[path[-1]] = value
        with self.assertRaises(RuntimeError): f.compare(**rows)

    def test_normalized_rates_and_clock_separation(self):
        rows = fixture()
        result = f.compare(**rows)
        self.assertAlmostEqual(result["measure_kb_s"], 300200 / 17000)
        self.assertEqual(result["transfer_seconds_saved"], 1)
        self.assertEqual(result["installation_reconnect_seconds_added"], 0)
        self.assertEqual(result["retain_batch_frames"], 12)
        self.assertFalse(result["strict_same_package_ab"])
        self.assertFalse(result["independent_acceptance"])
        rows["measure"]["pump"] = dict(gap_seconds=999, work_seconds=999)
        self.assertEqual(f.compare(**rows), result)

    def test_faster_small_package_is_not_gain(self):
        rows = fixture(); rows["measure"]["input"]["packageBytes"] = 200000
        self.assertEqual(f.compare(**rows)["retain_batch_frames"], 3)

    def test_same_policy_except_declared_batch(self):
        self.reject(("policy", "dataBatchFrames"), 3)
        self.reject(("policy", "rebootProbeIntervalMs"), 100)
        self.reject(("binding", "mtuChunkBytes"), 20)

    def test_executable_apk_boot_device(self):
        self.reject(("header_only",), False)
        self.reject(("apk_sha256",), "other")
        self.reject(("boot_sha256",), "other")
        self.reject(("input", "deviceAddress"), "CC:DD")
        self.reject(("input", "appLifecycle"), "paused")

    def test_real_predecessor_and_no_replay(self):
        self.reject(("input", "currentImageSha256"), "f" * 64)
        self.reject(("input", "currentVersionCode"), 30262)
        self.reject(("input", "targetVersionCode"), True)
        self.reject(("input", "packageSha256"), fixture()["control"]["input"]["packageSha256"])
        self.reject(("input", "targetImageSha256"), "bad")

    def test_invalid_sizes_and_times(self):
        for value in (True, 0, -1, 1.5, 1048577):
            self.reject(("input", "packageBytes"), value)
        for key in ("transfer_seconds", "installation_reconnect_seconds"):
            for value in (True, 0, -1, float("nan"), float("inf")):
                self.reject((key,), value)

    def test_targets_separate(self):
        rows = fixture(); rows["measure"].update(transfer_seconds=6.004)
        value = f.compare(**rows)
        self.assertTrue(value["transfer_target_met"])
        self.assertFalse(value["installation_target_met"])
        rows["measure"]["installation_reconnect_seconds"] = 20
        self.assertTrue(f.compare(**rows)["installation_target_met"])


if __name__ == "__main__":
    f.cli.require(Path.cwd() == ROOT and sys.flags.isolated and sys.flags.no_site and sys.dont_write_bytecode,
                  "isolated explicit root required")
    s = f.cli.Store(ROOT)
    out = s.checked(Path(sys.argv[1]))
    f.cli.require(not out.exists(), "preserve tests")
    stream = io.StringIO()
    result = unittest.TextTestRunner(stream=stream, verbosity=2).run(unittest.defaultTestLoader.loadTestsFromTestCase(Tests))
    s.raw(out / "tests.log", stream.getvalue().encode())
    s.write(out / "result.json", dict(result="PASS" if result.wasSuccessful() else "FAIL", tests=result.testsRun,
        source=f.cli.record(f.__file__), test=f.cli.record(__file__), hardware=False))
    print(stream.getvalue())
    sys.exit(not result.wasSuccessful())
