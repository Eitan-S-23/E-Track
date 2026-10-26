"""Offline negative controls for the v5 evaluator. No device or network calls."""
import copy
import importlib.util
import json
from pathlib import Path
import sys
import subprocess
import struct
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "Tools/ota/p38-closeout"))
import evaluate as e


class CloseoutTests(unittest.TestCase):
    def setUp(self):
        parent = e.output(e.CACHE / "tests")
        parent.mkdir(parents=True, exist_ok=True)
        self.temp = tempfile.TemporaryDirectory(dir=parent)
        self.root = Path(self.temp.name)
        self.addCleanup(self.temp.cleanup)

    def file(self, name, data):
        path = self.root / name
        path.write_bytes(data)
        return dict(path=name, bytes=len(data), sha256=e.sha(data))

    def test_pinned_input_rejects_modified_bytes_and_escape(self):
        item = self.file("original", b"original")
        self.assertEqual(e.read(item, self.root), b"original")
        with self.assertRaises(ValueError):
            e.read({**item, "sha256": "0" * 64}, self.root)
        for path in ("../outside", str(self.root / "original")):
            with self.assertRaises(ValueError):
                e.read({**item, "path": path}, self.root)

    def test_missing_input_is_not_success(self):
        result = e.evaluate({}, self.root)
        self.assertEqual(result["result"], "EVIDENCE_GAP")
        self.assertEqual(len(result["criteria"]), 7)
        self.assertTrue(all(v["result"] == "NOT_OBSERVED" for v in result["criteria"].values()))

    def test_recovery_requires_same_package_real_offset_and_distinct_capture(self):
        identity = dict(packageBytes=1048576, packageSha256="a" * 64, deviceAddress="aa:bb:cc:dd:ee:ff")
        a = dict(parameters=dict(input=identity), success=False, finalDurable=401408, captureId="old")
        b = dict(parameters=dict(input=identity), success=True, initialDurable=401408,
                 firstSentOffset=401408, finalDurable=1048576, captureId="new")
        self.assertEqual(e.recovery(a, b)["initial"], 401408)
        for key, value in (("initialDurable", 0), ("firstSentOffset", 0), ("success", False), ("captureId", "old")):
            with self.subTest(key=key), self.assertRaises(ValueError):
                e.recovery(a, {**b, key: value})
        wrong = copy.deepcopy(b)
        wrong["parameters"]["input"]["packageSha256"] = "b" * 64
        with self.assertRaises(ValueError):
            e.recovery(a, wrong)

    def test_native_terminal_rejects_either_resource_and_remaining_notification(self):
        e.native_terminal(b"mWakefulness=Awake", b"ACTIVITY MANAGER SERVICES", b"")
        e.native_terminal(b"PARTIAL_WAKE_LOCK 'trace:DeviceOta' REL=-1s", b"", b"")
        for power, services, notification in ((b"PARTIAL_WAKE_LOCK 'trace:DeviceOta' ACQ=-1s", b"", b""),
                                               (b"", b"DeviceOtaService", b""), (b"", b"", b"id=2408")):
            with self.assertRaises(ValueError):
                e.native_terminal(power, services, notification)

    def test_locked_progress_rejects_unrelated_snapshot_pid_and_no_progress(self):
        one = json.dumps(dict(message="OTA_LINK_SAMPLE label=upgrade kind=durable us=1 off=4096")).encode() + b"\n"
        two = one + json.dumps(dict(message="OTA_LINK_SAMPLE label=upgrade kind=durable us=2 off=8192")).encode() + b"\n"
        common = dict(pid=self.file("pid", b"42\n"), power=self.file("power", b"mWakefulness=Asleep\nPARTIAL_WAKE_LOCK 'trace:DeviceOta' ACQ=-1s (uid=1 pid=42)"),
                      activities=self.file("activities", b"mDreamingLockscreen=true"),
                      services=self.file("services", b"DeviceOtaService foregroundId=2408 isForeground=true"))
        samples = [{**common, "events_prefix": dict(bytes=len(raw), sha256=e.sha(raw))} for raw in (one, two)]
        self.assertEqual(e.locked_progress(two, dict(pid=42), samples, self.root), [4096, 8192])
        with self.assertRaises(ValueError):
            e.locked_progress(two, dict(pid=43), samples, self.root)
        with self.assertRaises(ValueError):
            e.locked_progress(two, dict(pid=42), [samples[0], samples[0]], self.root)
        stale = {**samples[0], "power": self.file("released", b"mWakefulness=Asleep\nPARTIAL_WAKE_LOCK 'trace:DeviceOta' REL=-1s")}
        with self.assertRaises(ValueError):
            e.locked_progress(two, dict(pid=42), [stale, samples[1]], self.root)
        background = {**samples[0], "services": self.file("not-foreground", b"DeviceOtaService foregroundId=2408 isForeground=false")}
        with self.assertRaises(ValueError):
            e.locked_progress(two, dict(pid=42), [background, samples[1]], self.root)
        samples[1]["events_prefix"]["sha256"] = "0" * 64
        with self.assertRaises(ValueError):
            e.locked_progress(two, dict(pid=42), samples, self.root)

    def test_output_must_stay_in_authorized_reviewer_scope(self):
        for path in (ROOT.parent / "outside", ROOT / "product-change", ROOT / "docs/acceptance-contracts/P3-8-v4"):
            with self.assertRaises(ValueError):
                e.output(path)

    def test_pause_uses_record_order_not_unrelated_clock_origins(self):
        pause = "OTA_MONO MONO_PAUSE monoUs=100 wallUs=1"
        resume = "OTA_MONO MONO_RESUME monoUs=200 wallUs=2"
        send = "OTA_LINK_SAMPLE label=upgrade kind=segment_first_send us=999999 off=0 len=128"
        self.assertEqual(e.pause_order([send, pause, resume])["pause_record"], 1)
        self.assertEqual(e.pause_order([pause, send, pause, resume])["tail_completion_records"], [1])
        with self.assertRaises(ValueError):
            e.pause_order([pause, send, pause, send, resume])
        for messages in ([], [pause], [resume, pause], [pause, send, resume],
                         [pause, send, pause, pause, send, resume]):
            with self.subTest(messages=messages), self.assertRaises(ValueError):
                e.pause_order(messages)

    def test_test_counts_supports_actual_hosted_reporter_without_guessing(self):
        self.assertEqual(e.test_counts("2026-01-01T00:00Z 772 tests passed, 16 skipped."), dict(passed=772, skipped=16))
        self.assertEqual(e.test_counts("+753 ~35: All tests passed!"), dict(passed=753, skipped=35))
        for text in ("no result", "1 tests passed. 2 tests passed.", "+1 -1: All tests passed!",
                     "1 tests passed.\nSome tests failed.", "1 tests failed."):
            with self.assertRaises(ValueError):
                e.test_counts(text)

    def test_notification_binds_percentage_to_prior_durable_and_current_intent(self):
        lines = [dict(message="OTA_LINK_SAMPLE kind=durable us=1 off=4096"),
                 dict(message="OTA_LINK_SAMPLE kind=durable us=2 off=8192")]
        raw = b"".join(json.dumps(line).encode() + b"\n" for line in lines)
        header = dict(pid=42, captureId="capture")
        intent = b"PendingIntentRecord{abc app startActivity\nrequestIntent=act=com.wen.gaia.gaia.DEVICE_OTA_OPEN dat=trace-device-ota://task/engine_9_2/9/open "
        samples = []
        for n, percentage in ((1, 25), (2, 50)):
            prefix = b"".join(raw.splitlines(keepends=True)[:n])
            health = dict(healthy=True, lost=0, error=None, captureId="capture", upgradeStarts=1, upgradeEnds=0, records=n, bytes=len(prefix))
            text = ("id=2408 android.progress=Integer (%d) android.progressMax=Integer (100) "
                    "android.progressIndeterminate=Boolean (false) Transferring (MCU durable confirmation): %d%% "
                    "contentIntent=PendingIntent{x: PendingIntentRecord{abc app startActivity}") % (percentage, percentage)
            samples.append(dict(health=self.file("h%d" % n, json.dumps(health).encode()),
                                pid=self.file("p%d" % n, b"42"), notification=self.file("n%d" % n, text.encode())))
        self.assertEqual(e.notification_progress(raw, header, samples, 16384, intent, self.root)["samples"][1]["durable"], 8192)
        for changed in (intent.replace(b"{abc ", b"{old "), intent.replace(b"_9_2/9", b"_6_1/9")):
            with self.assertRaises(ValueError):
                e.notification_progress(raw, header, samples, 16384, changed, self.root)
        bad = copy.deepcopy(samples)
        bad[0]["notification"] = self.file("bad", e.read(samples[0]["notification"], self.root).replace(b"25", b"50"))
        with self.assertRaises(ValueError):
            e.notification_progress(raw, header, bad, 16384, intent, self.root)

    def test_formal_output_rejects_unfrozen_entry(self):
        self.assertIsNone(e.formal_precheck(self.root / "input", e.CACHE / "smoke.json", None, None))
        with self.assertRaises(ValueError):
            e.formal_precheck(self.root / "input", e.BUNDLE / "result.json", None, None)

    def test_fixed_signing_requires_real_success_exact_pin_and_unchanged_product(self):
        run = dict(conclusion="success", path=".github/workflows/build.yml", id=1, head_sha="a" * 40)
        jobs = dict(jobs=[dict(name="Build Android APK", conclusion="success", run_id=1, head_sha="a" * 40,
                              steps=[dict(name="Verify release APK signature and identity", conclusion="success")])])
        inputs = dict(run=self.file("run", json.dumps(run).encode()), jobs=self.file("jobs", json.dumps(jobs).encode()),
                      log=self.file("log", b"2026-01-01T00:00Z Verified fixed APK signer SHA-256: 9e9b89c5e7fdc802b1fe71806a988a739caeee56cb69f3df579\n"))
        with patch.object(e, "git", return_value=b""):
            with self.assertRaises(ValueError):
                e.fixed_signing(inputs, self.root)
            inputs["log"] = self.file("right-log", b"2026-01-01T00:00Z Verified fixed APK signer SHA-256: 9e9b89c5e7fdc802b1fe71806a988a866db49cd988a739caeee56cb69f3df579\n" +
                                     b"2026-01-01T00:00Z " + b"a" * 64 + b"  build/app/outputs/flutter-apk/app-release.apk\n2026-01-01T00:00Z 100\n")
            self.assertEqual(e.fixed_signing(inputs, self.root)["run"], 1)
        with patch.object(e, "git", return_value=b"product.dart"):
            with self.assertRaises(ValueError):
                e.fixed_signing(inputs, self.root)

    def test_raw_health_requires_sd_and_advance(self):
        fields = {name: bytes(4) for name in ("owner", "active", "isr", "cfsr", "hfsr", "dhcsr", "sdio")}
        fields.update(state=b"\x04", confirmed=b"\x01", snapped=b"\x01", sd=b"\x01", vtor=(0x08010800).to_bytes(4, "little"),
                      health0=struct.pack("<9I", 0, 0, 0, 0, 1, 1, 0, 1, 1),
                      health1=struct.pack("<9I", 0, 0, 0, 0, 2, 2, 0, 1, 1))
        self.assertTrue(e.healthy_state(fields)["sd_ready"])
        for changed in ({**fields, "sd": b"\0"}, {**fields, "health1": fields["health0"]}):
            with self.assertRaises(ValueError):
                e.healthy_state(changed)

    def test_snapshot_requires_external_apk_target_pid_and_capture(self):
        sys.path.insert(0, str(ROOT / "tests/ota"))
        import test_p34_acceptance_stats as fixture
        raw = fixture.snapshot(*fixture.fixture())
        header = json.loads(raw.splitlines()[0])
        item = self.file("snapshot.jsonl", raw)
        binding = dict(apk_sha256="f" * 64, pid=header["pid"], capture=header["captureId"],
                       sentinel=header["sentinel"], target=header["target"])
        self.assertTrue(e.snapshot(item, binding, self.root)[2]["success"])
        for field, value in (("pid", header["pid"] + 1), ("capture", "other"),
                             ("sentinel", "OTAOBS" + "0" * 24), ("target", "11:22:33:44:55:66")):
            with self.subTest(field=field), self.assertRaises(ValueError):
                e.snapshot(item, {**binding, field: value}, self.root)

    def test_isolated_script_entries_load_before_any_output(self):
        for name in ("prepare.py", "evaluate.py"):
            command = [sys.executable, "-I", "-S", "-B", str(ROOT / "Tools/ota/p38-closeout" / name), "--help"]
            result = subprocess.run(command, cwd=ROOT, capture_output=True, timeout=20)
            self.assertEqual(result.returncode, 0, result.stderr)


if __name__ == "__main__":
    unittest.main(verbosity=2)
