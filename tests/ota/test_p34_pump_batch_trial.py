"""The interaction uses exact retained executable, a new package, and batch12 only."""
import copy
import io
from pathlib import Path
import sys
from types import SimpleNamespace
import unittest
from unittest import mock

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "Tools/ota"))
import p34_pump_batch_trial as f


class Guards(unittest.TestCase):
    def setUp(self): self.s = f.cli.Store(ROOT)

    def config(self, group):
        helper = f.cli.load_module("interaction_fixture", ROOT / "tests/ota/test_p34_batch12_trial.py")
        return helper.Guards().config(group)

    def test_native_packages_and_boot(self):
        group = f.assets(self.s, "measure")
        self.assertEqual(group["receiver_bindings"]["whole_boot"], group["target_bindings"]["whole_boot"])
        self.assertEqual(len(group["negatives"]), 4)
        self.assertTrue(all(x["native"]["passed"] and x["native"]["prepares"] == 0 for x in group["negatives"]))

    def test_header_only_and_exact_retained_receiver(self):
        group = f.assets(self.s, "measure")
        parent = f.previous.assets(self.s, "measure")
        self.assertEqual(group["receiver"], parent["target"])
        self.assertEqual(group["receiver_bindings"], parent["target_bindings"])
        self.assertNotEqual(group["package"], parent["package"])
        before, after = [Path(group[x]["path"]).read_bytes() for x in ("receiver", "target")]
        self.assertNotEqual(before, after)
        self.assertEqual(before[:0x400] + before[0x460:], after[:0x400] + after[0x460:])
        expected = copy.deepcopy(group["receiver_bindings"])
        expected["profile"].update(image=group["target"], identity=group["target_identity"], prefix=after[:0x460].hex())
        self.assertEqual(expected, group["target_bindings"])

    def test_completed_predecessor_not_bootstrap(self):
        proof = f.predecessor(self.s, "measure", f.assets(self.s, "measure"))
        self.assertEqual(proof["report"]["summary"]["input"]["targetVersionCode"], 30263)
        self.assertEqual(proof["report"]["result"], "FULL_INSTALL_VERIFIED")

    def test_same_apk_and_only_batch_changes(self):
        self.assertEqual(f.old.apk(self.s)["apk"]["sha256"],
                         "a48549082f74a234d5acf0affdfa0d4120f2099fffefa8a40dc0302cac444387")
        group = f.assets(self.s, "measure")
        config = self.config(group)
        f.old.validate(config, group)
        self.assertEqual(config["dataBatchFrames"], 12)
        for key, value in (("dataBatchFrames", 3), ("requestedBaud", 460800), ("senderWindowSegments", 32),
                           ("rebootProbeIntervalMs", 100), ("reuseRebootInfoLink", False), ("withoutResponse", False)):
            with self.subTest(key=key), self.assertRaises(RuntimeError):
                f.old.validate(dict(config, **{key: value}), group)

    def test_inherited_phone_applies_batch12(self):
        api = object.__new__(f.Trial)
        api.assets = f.assets(self.s, "measure")
        expected = self.config(api.assets)
        parent = dict(expected, schema=6, dataBatchFrames=3, rebootProbeIntervalMs=100)
        with mock.patch.object(f.old.prior.Cadence, "phone", return_value=SimpleNamespace(config=lambda *a: parent)):
            self.assertEqual(api.phone(None, "fixture").config(), expected)
        self.assertEqual(parent["dataBatchFrames"], 3)

    def test_changed_manifest_policy_rejected(self):
        original = self.s.read(f.asset_api.OUT / "result.json")
        for key, value in (("target_version", 30265), ("dataBatchFrames", 3), ("receiver", 30262)):
            changed = copy.deepcopy(original)
            changed["groups"]["measure"]["specification"][key] = value
            with mock.patch.object(self.s, "read", return_value=changed), self.assertRaises(RuntimeError):
                f.assets(self.s, "measure")

    def test_unlisted_arm_rejected(self):
        for name in ("bootstrap", "control", "repeat"):
            with self.assertRaises(RuntimeError): f.assets(self.s, name)
            with self.assertRaises(RuntimeError): f.predecessor(self.s, name, None)


if __name__ == "__main__":
    f.cli.require(Path.cwd() == ROOT and sys.flags.isolated and sys.flags.no_site and sys.dont_write_bytecode,
                  "isolated explicit root required")
    s = f.cli.Store(ROOT)
    s.checked(f.HOST)
    f.cli.require(not f.HOST.exists(), "preserve trial tests")
    stream = io.StringIO()
    result = unittest.TextTestRunner(stream=stream, verbosity=2).run(unittest.defaultTestLoader.loadTestsFromTestCase(Guards))
    log = s.raw(f.HOST / "tests.log", stream.getvalue().encode())
    s.write(f.HOST / "result.json", dict(result="PASS" if result.wasSuccessful() else "FAIL", tests=result.testsRun,
        source=f.cli.record(f.__file__), test=f.cli.record(__file__), assets_source=f.cli.record(f.asset_api.__file__),
        log=log, hardware=False))
    print(stream.getvalue())
    sys.exit(not result.wasSuccessful())
