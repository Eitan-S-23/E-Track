"""Only the reboot INFO deadline changes; installed code and safety gates stay."""
from pathlib import Path
import sys
import unittest
from unittest.mock import Mock, patch

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "Tools/ota"))
import p34_info_timeout as f


class Tests(unittest.TestCase):
    def test_one_axis_is_normalized_for_inherited_validator(self):
        group = object()
        with patch.object(f.phy, "validate") as validate:
            f.validate(dict(rebootInfoTimeoutMs=1000, other="unchanged"), group)
        validate.assert_called_once_with(dict(rebootInfoTimeoutMs=2000, other="unchanged"), group)
        for value in (True, 500, 1000.0, 2000):
            with self.assertRaises(RuntimeError): f.validate(dict(rebootInfoTimeoutMs=value), group)

    def test_real_config_and_other_axes(self):
        s = f.cli.Store(ROOT)
        group = f.assets(s)
        value = s.read(f.PRIOR / "cells/s04/runtime-config.json")
        value.update(rebootInfoTimeoutMs=1000, currentVersionCode=30268, targetVersionCode=30269,
            currentImageSha256=group["receiver"]["sha256"], targetImageSha256=group["target"]["sha256"],
            packageBytes=group["package"]["bytes"], packageSha256=group["package"]["sha256"])
        f.validate(value, group)
        for name, change in (("rebootProbeIntervalMs", 100), ("androidPhyPolicy", "observe"),
                             ("dataBatchFrames", 3), ("requestedBaud", 115200), ("targetVersionCode", 30268)):
            with self.assertRaises(RuntimeError): f.validate(dict(value, **{name: change}), group)

    def test_exact_completed_predecessor_and_same_apk(self):
        s = f.cli.Store(ROOT)
        api = f.Trial(s)
        self.assertEqual((api.receiver_version, api.target_version), (30268, 30269))
        self.assertEqual(api.proof["descriptor"]["kind"], "FULL_INSTALL_VERIFIED")
        self.assertEqual(api.assets["receiver"]["sha256"], api.proof["report"]["summary"]["input"]["targetImageSha256"])
        self.assertEqual(api.report["apk"]["sha256"], "aef3d433a54da801b594f5ddce64b5bdf80f0c0f1c2016a42f1188e04ae96934")

    def test_assets_are_header_only_and_all_native_guards_pass(self):
        group = f.assets(f.cli.Store(ROOT))
        a, b = (Path(group[k]["path"]).read_bytes() for k in ("receiver", "target"))
        self.assertNotEqual(a, b)
        self.assertEqual(a[:0x400] + a[0x460:], b[:0x400] + b[0x460:])
        self.assertTrue(group["decoded"]["passed"])
        self.assertEqual(len(group["negatives"]), 4)
        self.assertTrue(all(n["native"]["passed"] and n["native"]["prepares"] == 0 for n in group["negatives"]))

    def test_repaired_envelope_is_reused_not_old_capture_prefixes(self):
        reader = f.repaired.fixed_envelope()
        self.assertIn("OTA_PHY ", reader.PREFIXES)
        self.assertIn("OTA_PHY_CANCEL ", reader.PREFIXES)


if __name__ == "__main__":
    unittest.main(verbosity=2)
