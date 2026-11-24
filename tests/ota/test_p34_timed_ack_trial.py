"""Timed ACK lineage, existing APK, policy and negative package checks."""
from pathlib import Path
import sys
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "Tools/ota"))
import p34_timed_ack_trial as f


class Tests(unittest.TestCase):
    def test_bootstrap_uses_confirmed_receiver_and_same_apk(self):
        api = f.Trial(f.cli.Store(ROOT), "bootstrap")
        self.assertEqual((api.receiver_version, api.target_version), (30271, 30272))
        self.assertEqual(api.report["sha"], f.old.COMMIT)
        self.assertEqual(api.proof["descriptor"]["kind"], "FULL_INSTALL_VERIFIED")

    def test_measure_requires_real_predecessor(self):
        store = f.cli.Store(ROOT)
        original = store.read
        missing = f.TRIALS / "bootstrap/analysis/latest.json"
        def read(path):
            if Path(path) == missing: raise FileNotFoundError(str(path))
            return original(path)
        with patch.object(store, "read", side_effect=read):
            with self.assertRaises(FileNotFoundError):
                f.Trial(store, "measure")

    def test_packages_and_executable_lineage(self):
        groups = [f.assets(f.cli.Store(ROOT), arm) for arm in f.ORDER]
        self.assertEqual(groups[0]["target"], groups[1]["receiver"])
        a, b = [Path(group["target"]["path"]).read_bytes() for group in groups]
        self.assertNotEqual(a, b)
        self.assertEqual(a[:0x400] + a[0x460:], b[:0x400] + b[0x460:])
        for group in groups:
            self.assertEqual(group["receiver_bindings"]["whole_boot"], group["target_bindings"]["whole_boot"])
            self.assertEqual(len(group["negatives"]), 4)

    def test_existing_schema9_policy_and_changed_fields(self):
        s = f.cli.Store(ROOT)
        for arm in f.ORDER:
            group = f.assets(s, arm)
            value = s.read(f.PRIOR / "cells/s04/runtime-config.json")
            spec = group["specification"]
            value.update(currentVersionCode=spec["receiver"], targetVersionCode=spec["target_version"],
                currentImageSha256=group["receiver"]["sha256"], targetImageSha256=group["target"]["sha256"],
                packageBytes=group["package"]["bytes"], packageSha256=group["package"]["sha256"])
            f.old.validate(value, group)
            for key, wrong in (("rebootInfoMaxAttempts", 3), ("dataBatchFrames", 3),
                               ("requestedBaud", 115200), ("androidPhyPolicy", "observe")):
                with self.assertRaises(RuntimeError): f.old.validate(dict(value, **{key: wrong}), group)


if __name__ == "__main__":
    unittest.main(verbosity=2)
