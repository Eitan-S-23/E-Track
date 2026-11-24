"""Offline package, source, radio and predecessor guards for staging erase."""
import io
from pathlib import Path
import sys
from types import SimpleNamespace
import unittest
from unittest import mock

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "Tools/ota"))
import p34_staging_erase_trial as f


class Guards(unittest.TestCase):
    def setUp(self):
        self.s = f.cli.Store(ROOT)

    def config(self, group):
        helper = f.cli.load_module("staging_config_fixture", ROOT / "tests/ota/test_p34_batch12_trial.py")
        return helper.Guards().config(group)

    def test_assets_native_checks_and_same_boot(self):
        for arm in f.ORDER:
            group = f.assets(self.s, arm)
            self.assertEqual(group["receiver_bindings"]["whole_boot"], group["target_bindings"]["whole_boot"])
            self.assertEqual(len(group["negatives"]), 4)
            self.assertTrue(all(x["native"]["passed"] and x["native"]["prepares"] == 0 for x in group["negatives"]))

    def test_bootstrap_changes_code_and_measurement_does_not(self):
        first, second = [f.assets(self.s, x) for x in f.ORDER]
        before, after, measured = [Path(x["path"]).read_bytes() for x in (first["receiver"], first["target"], second["target"])]
        self.assertNotEqual(before[:0x400] + before[0x460:], after[:0x400] + after[0x460:])
        self.assertEqual(after[:0x400] + after[0x460:], measured[:0x400] + measured[0x460:])
        self.assertEqual(first["target"], second["receiver"])
        self.assertEqual(first["target_bindings"], second["receiver_bindings"])

    def test_predecessor_is_actual30259_and_measurement_needs_bootstrap(self):
        proof = f.predecessor(self.s, "bootstrap", f.assets(self.s, "bootstrap"))
        self.assertEqual(proof["report"]["summary"]["input"]["targetVersionCode"], 30259)
        spy = mock.Mock(return_value="verified")
        with mock.patch.object(f.batch, "clone", return_value=spy) as clone:
            self.assertEqual(f.predecessor(self.s, "measure", "group"), "verified")
        self.assertEqual(clone.call_args.kwargs, dict(ORDER=("bootstrap", "next"), TRIALS=f.TRIALS))
        spy.assert_called_once_with(self.s, "next", "group")

    def test_same_apk_and_radio_policy(self):
        apk = f.old.apk(self.s)
        self.assertEqual(apk["apk"]["sha256"], "a48549082f74a234d5acf0affdfa0d4120f2099fffefa8a40dc0302cac444387")
        for arm in f.ORDER:
            group = f.assets(self.s, arm); config = self.config(group)
            f.old.validate(config, group)
            self.assertEqual(config["dataBatchFrames"], 3)
            for key, value in (("dataBatchFrames", 12), ("requestedBaud", 460800),
                               ("senderWindowSegments", 32), ("rebootProbeIntervalMs", 100),
                               ("reuseRebootInfoLink", False), ("withoutResponse", False)):
                with self.subTest(arm=arm, key=key), self.assertRaises(RuntimeError):
                    f.old.validate(dict(config, **{key: value}), group)

    def test_inherited_phone_wrapper_uses_new_assets(self):
        for arm in f.ORDER:
            api = object.__new__(f.Trial); api.assets = f.assets(self.s, arm)
            expected = self.config(api.assets)
            parent = dict(expected, schema=6, rebootProbeIntervalMs=100)
            with mock.patch.object(f.old.prior.Cadence, "phone", return_value=SimpleNamespace(config=lambda *a: parent)):
                self.assertEqual(api.phone(None, "fixture").config(), expected)
            self.assertEqual(parent["schema"], 6)

    def test_build_and_host_matrix_are_bound(self):
        built = self.s.read(f.AREA / "build/result.json")
        self.assertEqual(built["result"], "STAGING_ERASE_APP_BUILT")
        self.assertFalse(built["boot_built"])
        self.assertFalse(built["new_warnings"])
        checked = self.s.read(built["tests"]["path"])
        self.assertEqual(set(checked["variants"]), {"bulk0-qe0", "bulk0-qe1", "bulk1-qe0", "bulk1-qe1"})
        self.assertTrue(all("failures=0" in value for value in checked["variants"].values()))
        self.assertTrue(all(f.cli.record(x["path"]) == x for x in checked["sources"]))

    def test_unlisted_arm_is_rejected(self):
        with self.assertRaises(RuntimeError): f.assets(self.s, "repeat")
        with self.assertRaises(RuntimeError): f.predecessor(self.s, "repeat", None)


if __name__ == "__main__":
    f.cli.require(Path.cwd() == ROOT and sys.flags.isolated and sys.flags.no_site and sys.dont_write_bytecode,
                  "isolated explicit root required")
    s = f.cli.Store(ROOT); s.checked(f.HOST)
    f.cli.require(not f.HOST.exists(), "preserve trial tests")
    stream = io.StringIO()
    result = unittest.TextTestRunner(stream=stream, verbosity=2).run(unittest.defaultTestLoader.loadTestsFromTestCase(Guards))
    log = s.raw(f.HOST / "tests.log", stream.getvalue().encode())
    s.write(f.HOST / "result.json", dict(result="PASS" if result.wasSuccessful() else "FAIL", tests=result.testsRun,
        source=f.cli.record(f.__file__), test=f.cli.record(__file__), assets_source=f.cli.record(f.asset_api.__file__),
        log=log, hardware=False))
    print(stream.getvalue())
    sys.exit(not result.wasSuccessful())
