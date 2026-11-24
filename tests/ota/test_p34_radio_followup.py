"""Offline gates for repaired-recorder remaining arms; never accesses hardware."""
import copy
import io
import json
import os
from pathlib import Path
import sys
import unittest
from types import SimpleNamespace
from unittest import mock

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "Tools/ota"))
import p34_radio_followup as f
import p34_install_cost as host


class Guards(unittest.TestCase):
    def setUp(self):
        self.s = f.cli.Store(ROOT)

    def test_raw_confirmed_invalid_capture_is_not_relabelled(self):
        p = f.predecessor(self.s, "priority", f.radio.assets(self.s, "priority"))
        self.assertEqual(p["descriptor"]["kind"], "RAW_CONFIRMED_CAPTURE_INVALID")
        self.assertEqual(p["descriptor"]["performance"], "UNAVAILABLE")
        self.assertEqual(p["report"]["result"], "TARGET_30247_RAW_CONFIRMED_CAPTURE_INVALID")

    def test_wrong_receiver_rejected(self):
        group = copy.deepcopy(f.radio.assets(self.s, "priority"))
        group["receiver"]["sha256"] = "0" * 64
        with self.assertRaises(RuntimeError): f.predecessor(self.s, "priority", group)

    def test_combined_requires_real_priority_success(self):
        self.assertEqual(f.predecessor(self.s, "combined", f.radio.assets(self.s, "combined"))["report"]["result"], "FULL_INSTALL_VERIFIED")
        original = self.s.read
        def invalid(path):
            value = original(path)
            if value.get("result") == "FULL_INSTALL_VERIFIED" and "summary" in value:
                return dict(value, result="INVALID")
            return value
        with mock.patch.object(self.s, "read", side_effect=invalid), self.assertRaises(RuntimeError):
            f.predecessor(self.s, "combined", f.radio.assets(self.s, "combined"))

    def test_capacity_is_checked_inside_provision_not_only_preflight(self):
        api = object.__new__(f.Followup)
        api.store = self.s
        original = mock.Mock(return_value=123)
        phone = SimpleNamespace(provision=original)
        c = SimpleNamespace(PKG="test", TARGET="AA:BB", apk=dict(metadata=dict(device_observation=dict(sentinel="test"))))
        with mock.patch.object(f.radio.Radio, "phone", return_value=phone), mock.patch.object(api, "known_configs", return_value={"known"}), \
             mock.patch.object(f.capacity, "ensure_capacity") as guard:
            wrapped = api.phone(c, "test")
            self.assertEqual(wrapped.provision(c, mock.Mock(), ROOT / ".cache/test-only", {}), 123)
            guard.assert_called_once()
            original.reset_mock()
            guard.side_effect = RuntimeError("full")
            with self.assertRaises(RuntimeError): wrapped.provision(c, mock.Mock(), ROOT / ".cache/test-only", {})
            original.assert_not_called()

    def test_no_replay_of_completed_arms(self):
        for arm in ("baseline", "scan"):
            with self.assertRaises(RuntimeError): f.Followup(self.s, arm)

    def test_exact_repaired_apk(self):
        self.assertEqual(f.apk(self.s)["sha"], f.artifacts.SHA)

    def test_recovery_preserves_invalid_health(self):
        r = f.recovered(self.s)
        f.recovery.invalid_health(Path(r["source_files"]["health.json"]["path"]).read_bytes())
        self.assertTrue(r["no_delete"])

    def test_startup_recovery_proves_no_ota(self):
        self.assertTrue(f.startup_recovered(self.s)["zero_upgrade_starts"])

    def test_repaired_reader_accepts_radio_but_not_corruption(self):
        fixture = f.cli.load_module("radio_envelope_fixture", f.radio.AREA / "src/tests/ota/test_p3_4_observation_capture.py")
        reader = f.fixed_envelope()
        old = f.cli.load_module("radio_envelope_original_test", ROOT / "Tools/ota/p34_observation.py")
        rows = fixture.rows()
        rows.insert(3, dict(kind="line", message="OTA_RADIO priority=request-accepted negotiated=unknown"))
        rows = [dict(row, seq=i) for i,row in enumerate(rows,1)]
        raw = fixture.encoded(rows)
        self.assertEqual(reader.verify(raw, sentinel=fixture.SENTINEL, target=fixture.TARGET)[0]["outcome"], "completed")
        with self.assertRaises(old.CaptureError): old.verify(raw, sentinel=fixture.SENTINEL, target=fixture.TARGET)
        for changes in (dict(lost=1), dict(healthy=False), dict(error="invalid-record")):
            with self.assertRaises(reader.CaptureError):
                reader.verify(fixture.encoded(rows, changes), sentinel=fixture.SENTINEL, target=fixture.TARGET)
        rows[3]["message"] = "OTA_RADIO token=fixture"
        with self.assertRaises(reader.CaptureError):
            reader.verify(fixture.encoded(rows), sentinel=fixture.SENTINEL, target=fixture.TARGET)

    def test_actual_launched_capture_keeps_runtime_identity_api(self):
        out = f.AREA / "trials/priority/cells/s04"
        expected = self.s.read(out / "runtime-config.json")
        stamp = {k:v for k,v in expected.items() if k not in ("target", "firmwareLatestUrl")}
        stamp.update(deviceAddress=expected["target"], endpointHost=f.radio.backend.urllib.parse.urlsplit(
            expected["firmwareLatestUrl"]).hostname, configSha256=f.cli.record(out / "runtime-config.json")["sha256"])
        pid, capture = 12345, "1790925192124168-1a3c191610d5b0cc5010d74d"
        remote = "files/p34-observations/" + capture
        c = SimpleNamespace(PKG="test", TARGET=expected["target"], envelope=f.fixed_envelope(),
            apk=dict(metadata=dict(device_observation=dict(sentinel="test-sentinel"))))
        header = dict(kind="open", schema=1, seq=1, pid=pid, captureId=capture,
                      sentinel="test-sentinel", target=expected["target"].lower())
        p, phone = mock.Mock(), mock.Mock()
        phone.location.return_value = (pid, remote)
        phone.exists.return_value = True
        p.command.return_value = json.dumps(header) + "\n" + json.dumps(dict(kind="line", seq=2,
            message="OTA_EXPERIMENT " + json.dumps(stamp))) + "\n"
        api = object.__new__(f.Followup)
        self.assertEqual(api.launched_capture(c, p, phone, out, pid, expected), remote)
        c.TARGET = "AA:BB:CC:DD:EE:FF"
        with self.assertRaises(RuntimeError): api.launched_capture(c, p, phone, out, pid, expected)


if __name__ == "__main__":
    f.cli.require(Path.cwd() == ROOT and sys.flags.isolated and sys.flags.no_site and sys.dont_write_bytecode,
                  "explicit root and isolated Python required")
    s, out = f.cli.Store(ROOT), f.HOST_TESTS
    f.cli.require(not out.exists(), "preserve original tests")
    os.environ.update(host.environment(s, out))
    stream = io.StringIO()
    result = unittest.TextTestRunner(stream=stream, verbosity=2).run(unittest.defaultTestLoader.loadTestsFromTestCase(Guards))
    log = s.raw(out / "tests.log", stream.getvalue().encode())
    s.write(out / "result.json", dict(result="PASS" if result.wasSuccessful() else "FAIL", tests=result.testsRun,
        errors=len(result.errors), failures=len(result.failures), source=f.cli.record(f.__file__), test=f.cli.record(__file__),
        envelope=f.cli.record(f.ENVELOPE), log=log, hardware=False))
    print(stream.getvalue(), flush=True)
    sys.exit(not result.wasSuccessful())
