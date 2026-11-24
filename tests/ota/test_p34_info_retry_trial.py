"""Retry-axis admission, real assets and observed configuration checks."""
from pathlib import Path
import sys
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "Tools/ota"))
import p34_info_retry_trial as f


class Tests(unittest.TestCase):
    def config(self, arm):
        s = f.cli.Store(ROOT)
        group = f.assets(s, arm)
        value = s.read(f.old.OUT / "cells/s04/runtime-config.json")
        spec = group["specification"]
        value.update(schema=9, rebootInfoMaxAttempts=spec["rebootInfoMaxAttempts"],
            currentVersionCode=spec["receiver"], targetVersionCode=spec["target_version"],
            currentImageSha256=group["receiver"]["sha256"], targetImageSha256=group["target"]["sha256"],
            packageBytes=group["package"]["bytes"], packageSha256=group["package"]["sha256"])
        return value, group

    def test_both_real_configs(self):
        for arm in f.ORDER:
            value, group = self.config(arm)
            f.validate(value, group)
            for key, wrong in (("rebootInfoMaxAttempts", True), ("rebootInfoMaxAttempts", 3.0),
                               ("rebootInfoMaxAttempts", 13), ("schema", 8), ("reuseRebootInfoLink", False),
                               ("rebootInfoTimeoutMs", 500), ("requestedBaud", 115200), ("dataBatchFrames", 3)):
                with self.assertRaises(RuntimeError): f.validate(dict(value, **{key: wrong}), group)

    def test_header_only_chain(self):
        groups = [f.assets(f.cli.Store(ROOT), arm) for arm in f.ORDER]
        self.assertEqual(groups[0]["target"], groups[1]["receiver"])
        for group in groups:
            a, b = (Path(group[k]["path"]).read_bytes() for k in ("receiver", "target"))
            self.assertNotEqual(a, b)
            self.assertEqual(a[:0x400] + a[0x460:], b[:0x400] + b[0x460:])

    def test_installed_control_and_confirmed_predecessor(self):
        api = f.Trial(f.cli.Store(ROOT), "control")
        self.assertEqual((api.receiver_version, api.target_version), (30269, 30270))
        self.assertEqual(api.report["sha"], f.COMMIT)
        self.assertEqual(api.proof["descriptor"]["kind"], "FULL_INSTALL_VERIFIED")

    def test_extended_requires_real_control_not_prepared_header(self):
        with self.assertRaises((FileNotFoundError, RuntimeError)):
            f.Trial(f.cli.Store(ROOT), "extended")

    def test_observation_does_not_drop_new_axis(self):
        value, _ = self.config("control")
        observed = {k: v for k, v in value.items() if k not in ("target", "firmwareLatestUrl")}
        observed.update(deviceAddress=value["target"], endpointHost="example", configSha256="hash")
        with patch.object(f.batch.radio, "original_verify", return_value=observed):
            self.assertEqual(f.verify(None, "", value, "hash"), observed)
            observed["rebootInfoMaxAttempts"] = 12
            with self.assertRaises(RuntimeError): f.verify(None, "", value, "hash")


if __name__ == "__main__":
    unittest.main(verbosity=2)
