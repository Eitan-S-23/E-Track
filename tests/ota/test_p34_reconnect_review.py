"""Prevent mixed-input/clock claims in reusable INFO-timeout reviews."""
import copy
import io
import json
from pathlib import Path
import sys
import unittest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "Tools/ota"))
import p34_reconnect_review as f


def pair():
    before = dict(config={f.AXIS: 2000, "senderWindowSegments": 28},
        header_only=True, apk_sha256="apk", boot_sha256="boot", binding={"mtuChunkBytes": 244},
        input=dict(currentVersionCode=1, targetVersionCode=2, targetImageSha256="two",
            currentImageSha256="one", appLifecycle="resumed", packageSha256="a"),
        public=dict(transfer_seconds=17., installation_reconnect_seconds=22.,
            total_seconds=39., throughput_kb_s=17.))
    after = copy.deepcopy(before)
    after["config"][f.AXIS] = 1000
    after["input"].update(currentVersionCode=2, targetVersionCode=3,
        currentImageSha256="two", targetImageSha256="three", packageSha256="b")
    after["public"].update(transfer_seconds=18., installation_reconnect_seconds=20.5,
        total_seconds=38.5, throughput_kb_s=16.)
    return before, after


def lines():
    return "\n".join(("OTA_LINK_SAMPLE label=probe kind=get_info us=1009000 ok=0",
        "OTA_LINK_SAMPLE label=probe kind=get_info us=836765 ok=1",
        "OTA_LINK_STATS " + json.dumps(dict(label="probe", attempt=1,
            getInfo=dict(calls=2, failures=1, totalUs=1845765)))))


class Tests(unittest.TestCase):
    def test_single_sample_does_not_prove_cause_or_repeatability(self):
        result = f.cohort(*pair())
        self.assertAlmostEqual(result["total_seconds_saved"], .5)
        self.assertLess(result["throughput_gain_percent"], 0)
        self.assertFalse(result["causal_timeout_speedup_proven"])
        self.assertFalse(result["repeatability_proven"])
        self.assertFalse(result["strict_same_package_ab"])

    def test_reject_second_axis_or_unchanged_axis(self):
        for delta in ({"senderWindowSegments": 32}, {f.AXIS: 2000}, {"extra": 1}):
            a, b = pair()
            b["config"].update(delta)
            with self.assertRaises(RuntimeError): f.cohort(a, b)

    def test_reject_identity_or_runtime_change(self):
        for key, value in (("apk_sha256", "other"), ("boot_sha256", "other"),
                           ("header_only", False), ("binding", {})):
            a, b = pair()
            b[key] = value
            with self.assertRaises(RuntimeError): f.cohort(a, b)
        for key, value in (("currentImageSha256", "other"), ("currentVersionCode", 1),
                           ("appLifecycle", "paused")):
            a, b = pair()
            b["input"][key] = value
            with self.assertRaises(RuntimeError): f.cohort(a, b)

    def test_reject_unsupported_timeouts(self):
        for value in (True, 499, 10001, 1000.):
            a, b = pair()
            b["config"][f.AXIS] = value
            with self.assertRaises(RuntimeError): f.cohort(a, b)

    def test_successful_info_is_not_assumed_instant(self):
        result = f.info_samples(lines())
        self.assertEqual(result["successful_us"], [836765])
        self.assertEqual(len(result["attempts"][0]["samples"]), 2)

    def test_reject_missing_corrupt_duplicate_or_late_samples(self):
        good = lines()
        for bad in (good.split("\n", 1)[1], good.replace("1009000", "1009001"),
                    good + "\n" + good, good + "\nOTA_LINK_LATE label=probe attempt=1 kind=get_info",
                    good.replace("ok=1", "ok=2"), good + "\nOTA_LINK_SAMPLE label=probe kind=get_info us=1 ok=1"):
            with self.assertRaises(RuntimeError): f.info_samples(bad)

    def test_empty_failed_or_nonsequential_attempts_rejected(self):
        for bad in ("", lines().replace('"attempt": 1', '"attempt": 2'),
                    lines().replace("ok=1", "ok=0").replace('"failures": 1', '"failures": 2')):
            with self.assertRaises(RuntimeError): f.info_samples(bad)

    def test_original_completed_snapshot(self):
        root = ROOT / ".cache/p34-info-timeout/trial/cells/s04/finished/snapshot.jsonl"
        _, messages = f.phy.phy.fixed_envelope().verify(root.read_bytes(),
            sentinel="OTAOBS96bb2c74d5ad6ccecaf30e40", target="02:00:00:00:00:01")
        result = f.info_samples(messages)
        self.assertEqual(result["successful_us"], [836765])
        self.assertEqual([len(x["samples"]) for x in result["attempts"]], [0, 3, 0, 3])
        self.assertAlmostEqual(f.phy.public_metrics(messages, 293472)["total_seconds"], 38.393737)

    def test_original_closed_reports_end_to_end(self):
        store = f.cli.Store(ROOT)
        before = f.sample(store, ROOT / ".cache/p34-phy-logfix/trials/prefer2m")
        after = f.sample(store, ROOT / ".cache/p34-info-timeout/trial")
        result = f.cohort(before, after)
        self.assertAlmostEqual(result["installation_reconnect_seconds_saved"], 1.310809)
        self.assertAlmostEqual(result["total_seconds_saved"], .581135)
        self.assertFalse(after["public"]["installation_target_met"])
        self.assertFalse(after["public"]["transfer_target_met"])
        self.assertEqual(after["info_samples"]["successful_us"], [836765])

    def test_shared_reader_rejects_conflicting_repeated_config(self):
        path = ROOT / ".cache/p34-info-timeout/trial/cells/s04/finished/snapshot.jsonl"
        rows = [json.loads(x) for x in path.read_text().splitlines()]
        messages = [r["message"] for r in rows if r.get("kind") == "line"]
        reader = f.phy.phy.fixed_envelope()
        config = reader.experiment_record(messages)
        config[f.AXIS] = 500
        with self.assertRaises(reader.CaptureError):
            reader.experiment_record(messages + ["OTA_EXPERIMENT " + json.dumps(config)])


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
