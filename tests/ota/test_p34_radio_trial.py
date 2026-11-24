"""Offline schema4, artifact and predecessor gates; never uses the device."""
import copy
import io
import json
import os
from pathlib import Path
import sys
from types import SimpleNamespace
import unittest
from unittest import mock

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "Tools/ota"))
import p34_radio_trial as f
import p34_install_cost as host


class Guards(unittest.TestCase):
    def setUp(self):
        self.s = f.cli.Store(ROOT)
        self.group = f.assets(self.s, "baseline")
        spec = self.group["specification"]
        self.config = dict(schema=4, runId="s04", target="02:00:00:00:00:01", requestedBaud=921600,
            senderWindowSegments=28, reuseGatt=True, withoutResponse=True, transferMode="full", prefixBytes=0,
            **f.EXTRA, pauseScanDuringOta=False, androidHighPriority=False, currentVersionCode=spec["receiver"],
            targetVersionCode=spec["target_version"], currentImageSha256=self.group["receiver"]["sha256"],
            targetImageSha256=self.group["target"]["sha256"], packageBytes=self.group["package"]["bytes"],
            packageSha256=self.group["package"]["sha256"], firmwareLatestUrl="https://offline.trycloudflare.com/api/public/firmware/latest")
        self.item = {k:v for k,v in self.config.items() if k not in ("target", "firmwareLatestUrl")}
        self.item.update(deviceAddress=self.config["target"], endpointHost="offline.trycloudflare.com", configSha256="a" * 64)

    def verify(self):
        return f.verify_radio(f.old.backend.cli.load_module("radio_capture_tests", ROOT / "Tools/ota/p34_observation.py"),
            "OTA_EXPERIMENT " + json.dumps(self.item), self.config, "a" * 64)

    def test_exact_schema4_provenance(self):
        self.assertEqual(self.verify(), self.item)
        f.validate_config(self.config, self.group)

    def test_successful_retry_is_the_installation_anchor(self):
        self.assertEqual(f.INSTALL.name, "install-002")
        self.assertEqual(f.apk(self.s)["sha"], f.COMMIT)
        self.assertEqual(self.s.read(f.AREA / "install-001/result.json")["result"],
                         "RADIO_UPDATE_INCOMPLETE")

    def test_all_served_names_satisfy_real_app_contract(self):
        for arm in f.ORDER:
            group = f.assets(self.s, arm)
            api = object.__new__(f.Radio)
            api.served_name = group["specification"]["served_name"]
            c = SimpleNamespace(service=SimpleNamespace(DEVICE_MODEL="test-model"),
                target_version=group["specification"]["target_version"], target=group["target"],
                screen=group["package"], screen_bytes=Path(group["package"]["path"]).read_bytes(),
                receiver_version=group["specification"]["receiver"], package_kind="full")
            value = dict(schemaVersion=2, updateAvailable=True, errorCode=None, appId="trace",
                deviceModel="test-model", channel="stable", transport="ble", versionCode=c.target_version,
                targetImageSha256=c.target["sha256"], minAppVersionCode=0,
                **{k:"test" for k in ("requestId", "releaseId", "releaseTag", "versionName", "targetHardware")},
                asset=dict(kind="full", fileName=api.served_name, assetId="test", sha256=c.screen["sha256"],
                    sizeBytes=len(c.screen_bytes), baseVersionCode=0, baseImageSha256=None, expiresAt=1,
                    downloadUrl="https://offline.trycloudflare.com/" + api.served_name))
            api.validate_served(c, value, "https://offline.trycloudflare.com")
            original = self.s.read(f.ASSETS)["groups"][arm]
            self.assertEqual(group["package"], original["package"])
            self.assertEqual(group["target"], original["target"])
            value["asset"]["fileName"] = api.served_name = original["specification"]["served_name"]
            with self.assertRaises(RuntimeError):
                api.validate_served(c, value, "https://offline.trycloudflare.com")

    def test_failed_network_closed_before_any_device_cell(self):
        f.verify_pre_cell_failure(self.s)

    def test_each_additional_axis_is_type_and_value_bound(self):
        for key in (*f.EXTRA, "pauseScanDuringOta", "androidHighPriority"):
            saved = self.item[key]
            for wrong in (None, str(saved), not saved if type(saved) is bool else saved + 1):
                with self.subTest(key=key, wrong=wrong):
                    self.item[key] = wrong
                    with self.assertRaises(RuntimeError): self.verify()
            self.item[key] = saved

    def test_unknown_fields_rejected(self):
        self.item["unplanned"] = True
        with self.assertRaises(RuntimeError): self.verify()

    def test_old_schema_not_relabelled(self):
        self.config["schema"] = self.item["schema"] = 3
        with self.assertRaises(RuntimeError): self.verify()

    def test_every_fixed_axis_rejects_drift(self):
        for key, value in self.config.items():
            if key in ("target", "firmwareLatestUrl"): continue
            wrong = dict(self.config)
            wrong[key] = not value if type(value) is bool else value + 1 if type(value) is int else value + "x"
            with self.subTest(key=key), self.assertRaises(RuntimeError): f.validate_config(wrong, self.group)

    def test_acknowledgements_not_config_alone(self):
        expected = dict(pauseScanDuringOta=True, androidHighPriority=True)
        lines = "OTA_RADIO scan=paused\nOTA_RADIO priority=request-accepted negotiated=unknown\n"
        f.validate_radio_markers(lines, expected)
        for broken in ("", lines + lines, lines + "OTA_RADIO cleanup=unresolved error=TimeoutException"):
            with self.assertRaises(RuntimeError): f.validate_radio_markers(broken, expected)

    def test_baseline_must_not_have_enabled_markers(self):
        f.validate_radio_markers("", self.config)
        with self.assertRaises(RuntimeError): f.validate_radio_markers("OTA_RADIO scan=paused", self.config)

    def test_real_confirmed30245_predecessor(self):
        proof = f.confirmed_predecessor(self.s, "baseline", self.group)
        self.assertEqual(proof["report"]["summary"]["input"]["targetVersionCode"], 30245)
        wrong = copy.deepcopy(self.group)
        wrong["receiver"]["sha256"] = "0" * 64
        with self.assertRaises(RuntimeError): f.confirmed_predecessor(self.s, "baseline", wrong)

    def test_prepared_later_image_is_not_an_installed_predecessor(self):
        with self.assertRaises(FileNotFoundError):
            f.confirmed_predecessor(self.s, "scan", f.assets(self.s, "scan"))

    def test_original_backend_has_not_been_mutated(self):
        self.assertIsNot(f.backend, f.old.backend)
        self.assertIsNot(f.old.backend.verify_experiment, f.verify_radio)

    def test_retirement_calls_its_actual_parent(self):
        api = object.__new__(f.Radio)
        c, p, phone = mock.Mock(), mock.Mock(), mock.Mock()
        p.file_bytes.return_value = b"owned"
        phone.exists.return_value = False
        with mock.patch.object(api, "known_configs", return_value={f.hashlib.sha256(b"owned").hexdigest()}), \
             mock.patch.object(f.backend, "checked_phone_path"), \
             mock.patch.object(f.backend.Backend, "retire_initial", return_value="parent-called"):
            self.assertEqual(api.retire_initial(c, p, phone, ROOT / ".cache/fake"), "parent-called")


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
        errors=len(result.errors), failures=len(result.failures), log=log, source=f.cli.record(f.__file__), test=f.cli.record(__file__), hardware=False))
    print(stream.getvalue(), flush=True)
    sys.exit(not result.wasSuccessful())
