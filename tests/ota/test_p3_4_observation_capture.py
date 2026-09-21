"""Synthetic snapshot-integrity tests, never device or performance evidence."""
import copy
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[2]
spec = importlib.util.spec_from_file_location("capture", ROOT / "Tools/ota/p3-4-link-stats/observation_capture.py")
m = importlib.util.module_from_spec(spec)
spec.loader.exec_module(m)
SENTINEL = "OTAOBS0123456789abcdef01234567"
TARGET = "AA:BB:CC:DD:EE:FF"
CAPTURE = "1789990000000000-0123456789abcdef01234567"
INPUT = dict(packageSha256="a"*64, packageBytes=284466, currentVersionCode=30206,
             currentImageSha256="b"*64, targetVersionCode=30207,
             targetImageSha256="c"*64, deviceAddress=TARGET, appLifecycle="resumed")


def rows(*, complete=True, outcome="completed"):
    items = [dict(kind="open", schema=1, captureId=CAPTURE, sentinel=SENTINEL,
                  target=TARGET, pid=12345, platform="android", openedAt="2026-09-21T12:00:00Z",
                  limits=dict(captureBytes=67108864, pendingBytes=1048576)),
             dict(kind="line", message="OTA_LINK_SAMPLE label=query kind=get_info us=10 ok=1")]
    if complete:
        items.append(dict(kind="upgrade-start", input=copy.deepcopy(INPUT)))
        for event in ("MONO_BUDGET_START", "MONO_END_ACK_OK", "MONO_REBOOT_VERIFIED"):
            items.append(dict(kind="line", message="OTA_MONO " + event + " monoUs=10 wallUs=100"))
        for phase, version, sha in (("pre-transfer", 30206, "b"*64), ("post-reboot", 30207, "c"*64)):
            items.append(dict(kind="line", message="OTA_IDENTITY " + json.dumps(
                dict(phase=phase, versionCode=version, imageSha256=sha, deviceAddress=TARGET))))
        items.append(dict(kind="upgrade-end", outcome=outcome))
    return [dict(seq=i, **item) for i, item in enumerate(items, 1)]


def encoded(items, footer_changes=None):
    prefix = b"".join((json.dumps(row, separators=(",", ":")) + "\n").encode() for row in items)
    outcomes = [row["outcome"] for row in items if row["kind"] == "upgrade-end"]
    footer = dict(kind="snapshot", schema=1, captureId=CAPTURE, bytes=len(prefix),
                  records=len(items), producerLines=sum(row["kind"] == "line" for row in items),
                  upgradeStarts=sum(row["kind"] == "upgrade-start" for row in items),
                  upgradeEnds=len(outcomes), outcome=outcomes[-1] if outcomes else None,
                  lost=0, error=None, healthy=True, sha256=hashlib.sha256(prefix).hexdigest(),
                  exportedAt="2026-09-21T12:01:00Z")
    footer.update(footer_changes or {})
    return prefix + (json.dumps(footer, separators=(",", ":")) + "\n").encode()


class CaptureTests(unittest.TestCase):
    def setUp(self):
        self.base = m.checked(ROOT / ".cache/p3-4-observation-capture-tests")
        self.base.mkdir(exist_ok=True, parents=True)
        self.tmp = m.checked(Path(tempfile.mkdtemp(prefix="case-", dir=self.base)))

    def tearDown(self):
        shutil.rmtree(m.checked(self.tmp))

    def verify(self, data, **kwargs):
        return m.verify(data, sentinel=SENTINEL, target=TARGET, **kwargs)

    def test_complete_envelope_is_not_performance_acceptance(self):
        data = encoded(rows())
        result, log = self.verify(data)
        self.assertEqual(result["rawSha256"], hashlib.sha256(data).hexdigest())
        self.assertFalse(result["eligibleForThreshold"])
        self.assertEqual(result["independentAcceptance"], "NOT_RUN")
        self.assertEqual(result["input"], INPUT)
        self.assertIn("MONO_REBOOT_VERIFIED", log)

    def test_query_capture_is_only_a_readiness_check(self):
        data = encoded(rows(complete=False))
        result, _ = self.verify(data, require_upgrade=False)
        self.assertIsNone(result["outcome"])
        with self.assertRaises(m.CaptureError): self.verify(data)

    def test_header_only_or_host_marker_cannot_prove_app_logging(self):
        items = rows(complete=False)
        for bad in (items[:1], [items[0], dict(seq=2, kind="line", message="P34_CAPTURE_PROBE host")]):
            with self.subTest(rows=len(bad)), self.assertRaises(m.CaptureError):
                self.verify(encoded(bad), require_upgrade=False)

    def test_truncated_or_appended_export_is_rejected(self):
        data = encoded(rows())
        for bad in (data[:-1], data[:-100], b"\xef\xbb\xbf"+data, data+b"{}\n", data.replace(b"\n", b"\r\n")):
            with self.subTest(size=len(bad)), self.assertRaises(m.CaptureError): self.verify(bad)

    def test_digest_and_all_footer_counters_are_checked(self):
        for changes in (dict(sha256="d"*64), dict(bytes=1), dict(bytes=True), dict(records=1),
                        dict(producerLines=100), dict(upgradeStarts=0), dict(upgradeEnds=0),
                        dict(healthy=False), dict(healthy=1), dict(lost=1), dict(lost=False),
                        dict(error="io-write"), dict(outcome="not-completed"), dict(schema=True)):
            with self.subTest(changes=changes), self.assertRaises(m.CaptureError):
                self.verify(encoded(rows(), changes))

    def test_missing_duplicate_and_reordered_rows_fail_even_with_new_hash(self):
        original = rows()
        variants = [original[:2]+original[3:], original[:2]+[original[1]]+original[2:],
                    [original[0], original[2], original[1]]+original[3:]]
        for value in variants:
            with self.assertRaises(m.CaptureError): self.verify(encoded(value))

    def test_duplicate_json_keys_rejected_not_last_value_wins(self):
        data = encoded(rows()).replace(b'"seq":1,', b'"seq":1,"seq":1,', 1)
        prefix, footer = data.rsplit(b"\n", 2)[:2]
        meta = json.loads(footer)
        prefix += b"\n"
        meta.update(bytes=len(prefix), sha256=hashlib.sha256(prefix).hexdigest())
        bad = prefix+(json.dumps(meta)+"\n").encode()
        with self.assertRaisesRegex(m.CaptureError, "duplicate"): self.verify(bad)

    def test_wrong_build_or_target_is_rejected(self):
        for changes in (dict(sentinel="OTAOBS"+"f"*24), dict(target="different"),
                        dict(captureId="1789990000000001-"+"f"*24)):
            items = rows()
            items[0].update(changes)
            with self.assertRaises(m.CaptureError): self.verify(encoded(items))

    def test_input_identity_domains_and_unknown_fields(self):
        for changes in (dict(packageBytes=True), dict(packageBytes=63), dict(currentVersionCode=-1),
                        dict(targetVersionCode=0x100000000), dict(packageSha256="A"*64),
                        dict(appLifecycle="assumed-foreground"), dict(deviceAddress="https://invalid/"),
                        dict(extra="unbound")):
            items = rows()
            items[2]["input"].update(changes)
            with self.subTest(changes=changes), self.assertRaises(m.CaptureError): self.verify(encoded(items))

    def test_multiple_invocations_not_merged_into_one(self):
        items = rows()
        items += [dict(seq=len(items)+1, kind="upgrade-start", input=copy.deepcopy(INPUT))]
        with self.assertRaises(m.CaptureError): self.verify(encoded(items))

    def test_missing_end_is_not_a_complete_capture(self):
        with self.assertRaises(m.CaptureError): self.verify(encoded(rows()[:-1]), require_upgrade=False)

    def test_success_requires_actual_before_after_identity_and_sender_events(self):
        for fragment in ("MONO_END_ACK_OK", "MONO_REBOOT_VERIFIED", "MONO_BUDGET_START", "post-reboot", "pre-transfer"):
            items = [row for row in rows() if fragment not in row.get("message", "")]
            for i, row in enumerate(items, 1): row["seq"] = i
            with self.subTest(fragment=fragment), self.assertRaises(m.CaptureError): self.verify(encoded(items))

    def test_changed_post_reboot_sha_cannot_be_called_success(self):
        items = rows()
        for row in items:
            if "post-reboot" in row.get("message", ""):
                row["message"] = row["message"].replace("c"*64, "d"*64)
        with self.assertRaises(m.CaptureError): self.verify(encoded(items))

    def test_failed_invocation_can_be_preserved_without_success_events(self):
        items = rows(outcome="not-completed")
        items = [row for row in items if not row.get("message", "").startswith(("OTA_IDENTITY", "OTA_MONO"))]
        for i, row in enumerate(items, 1): row["seq"] = i
        result, _ = self.verify(encoded(items))
        self.assertEqual(result["outcome"], "not-completed")
        self.assertFalse(result["eligibleForThreshold"])

    def test_arbitrary_multiline_or_sensitive_content_is_not_exportable(self):
        for message in ("ordinary console line", "OTA_MONO token=fixture", "OTA_MONO https://invalid/",
                        "OTA_LINK_STATS {}\nOTA_MONO fake", "OTA_MONO "+"x"*16384):
            items = rows()
            items[1]["message"] = message
            with self.assertRaises(m.CaptureError): self.verify(encoded(items))

    def test_invalid_input_creates_no_output_and_preserves_source(self):
        source, out = self.tmp / "source.jsonl", self.tmp / "extracted"
        data = encoded(rows(), dict(lost=1))
        source.write_bytes(data)
        with self.assertRaises(m.CaptureError): m.extract(source, out, SENTINEL, TARGET)
        self.assertFalse(out.exists())
        self.assertEqual(data, source.read_bytes())

    def test_scoped_extraction_will_not_overwrite_evidence(self):
        source, out = self.tmp / "source.jsonl", self.tmp / "extracted"
        data = encoded(rows())
        source.write_bytes(data)
        result = m.extract(source, out, SENTINEL, TARGET)
        self.assertEqual(source.read_bytes(), data)
        unwrapped = (out / "observations.log").read_bytes()
        self.assertEqual(hashlib.sha256(unwrapped).hexdigest(), result["unwrappedSha256"])
        with self.assertRaises(m.CaptureError): m.extract(source, out, SENTINEL, TARGET)

    def test_outside_worktree_and_prefix_collision_are_rejected(self):
        source = self.tmp / "source.jsonl"
        source.write_bytes(encoded(rows()))
        for out in (ROOT.parent / ("outside-"+self.tmp.name), Path(str(ROOT)+"-other") / self.tmp.name):
            with self.assertRaises(m.CaptureError): m.extract(source, out, SENTINEL, TARGET)
            self.assertFalse(out.exists())

    def test_cli_executes_and_returns_nonzero_for_corruption(self):
        source = self.tmp / "source.jsonl"
        source.write_bytes(encoded(rows()))
        cmd = [sys.executable, "-I", "-S", "-B", "-X", "utf8", m.__file__, "extract",
               "--input", str(source), "--expect-sentinel", SENTINEL, "--expect-target", TARGET,
               "--out-root", str(self.tmp / "cli")]
        good = subprocess.run(cmd, cwd=ROOT, capture_output=True, timeout=15)
        self.assertEqual(0, good.returncode, good.stderr.decode(errors="replace"))
        source.write_bytes(encoded(rows(), dict(sha256="f"*64)))
        cmd[-1] = str(self.tmp / "bad-cli")
        bad = subprocess.run(cmd, cwd=ROOT, capture_output=True, timeout=15)
        self.assertEqual(2, bad.returncode)
        self.assertFalse((self.tmp / "bad-cli").exists())


if __name__ == "__main__":
    unittest.main(verbosity=2)
