"""Bounded full window-16 screening on the verified Z receiver, host-only."""
import os
from pathlib import Path
import sys
import unittest
from unittest import mock

ROOT = Path(__file__).resolve().parents[2]
cli = sys.modules["p34_session"]
OUTPUT = Path(os.environ["P34_TEST_OUT"])
assets = cli.load_module("p34_speed16_asset_checks", ROOT / "Tools/ota/p34_install_assets.py")


class Speed16Tests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.store = cli.Store(ROOT)
        cls.profile = cls.store.base / "profile-speed-window16.json"
        cls.api = cli.backend(cls.store, cls.profile, cli.SPEED16_GROUP)
        cls.c = cls.api.context(OUTPUT / "speed16-context")

    def test_only_window_changes_and_original_Boot_executable_are_preserved(self):
        c = self.c
        self.assertEqual((c.receiver_version, c.target_version), (30222, 30225))
        self.assertEqual(cli.cells_for(cli.SPEED16_GROUP)["s04"], (921600, 16))
        self.assertEqual(cli.cells_for(cli.NATIVE_DIAGNOSTIC_GROUP)["s04"], (921600, 8))
        before, after = (Path(x["path"]).read_bytes() for x in (c.previous_assets["target"], c.target))
        self.assertEqual(before[:0x400] + before[0x460:], after[:0x400] + after[0x460:])
        self.assertEqual(c.bindings["profile"]["map"], c.full_assets["target_bindings"]["profile"]["map"])
        self.assertEqual(c.bindings["whole_boot"], c.full_assets["target_bindings"]["whole_boot"])
        self.assertNotEqual(c.screen, c.previous_assets["package"])

    def test_full_config_and_quic_route_do_not_require_native_epoch_logging(self):
        phone = self.api.phone(self.c, "speed16_phone_test")
        value = phone.config(self.c, "s04", 921600, 16, "https://fixture.trycloudflare.com")
        self.assertEqual((value["transferMode"], value["prefixBytes"], value["senderWindowSegments"]), ("full", 0, 16))
        self.assertTrue(value["reuseGatt"] and value["withoutResponse"])
        self.assertFalse(self.api.profile["native_diagnostic"])
        self.assertEqual(self.api.profile["tunnel_protocol"], "quic")
        notes = phone.service_config(self.c, "https://fixture.trycloudflare.com")["releases"][self.c.release_key]["releaseNotes"]
        self.assertIn("Window-16 speed screen", notes)
        for cell, baud, window in (("s01", 460800, 4), ("s04", 921600, 8), ("s04", 460800, 16)):
            with self.subTest(cell=cell, window=window), self.assertRaises(RuntimeError):
                phone.config(self.c, cell, baud, window, "https://fixture.trycloudflare.com")

    def test_actual_Z_predecessor_and_Y_cleanup_remain_exact(self):
        previous = cli.completed_full_predecessor(self.store, self.api.profile["predecessor"], group=cli.NATIVE_DIAGNOSTIC_GROUP)
        self.assertEqual(previous["descriptor"]["run"], "20260928T144139-55600")
        self.assertEqual(previous["report"]["full_metrics"]["transfer_seconds"], 61.957856)
        with mock.patch.object(self.store, "current", return_value=previous["out"].name):
            selected = cli.completed_capture_target(self.store, "20260927T162548-11400")
            self.assertEqual(selected["capture"], "1790526764868470-ce28d15e511394dcc11d74d0")
            self.assertEqual(selected["protected"]["report"]["summary"]["captureId"], "1790606692563314-ee73468a16dc2b5a592c55c7")
            with self.assertRaises(RuntimeError):
                cli.completed_capture_target(self.store, previous["out"].name)

    def test_reserved_version_skip_is_exact_and_old_groups_are_unchanged(self):
        spec = cli.N04_GROUPS[cli.SPEED16_GROUP]
        self.assertEqual(assets.receiver(self.c, spec), self.c.previous_assets["target"])
        for change in (dict(target_version=30226), dict(target_version=30221), dict(predecessor_group="n04-measure")):
            with self.subTest(change=change), self.assertRaises(RuntimeError):
                assets.receiver(self.c, dict(spec, **change))
        self.assertEqual(cli.n04_asset_groups("n04-measure"), ("n04-bootstrap", "n04-measure"))
        self.assertNotIn(cli.SPEED16_GROUP, cli.n04_asset_groups(cli.NATIVE_DIAGNOSTIC_GROUP))

    def test_preparation_is_reusable_and_rejects_a_non_Z_owner(self):
        with mock.patch.object(self.store, "current", return_value="20260928T144139-55600"), \
             mock.patch.object(assets.subprocess, "run", side_effect=AssertionError("must not repack")):
            result = cli.prepare_speed16(self.store)
        self.assertEqual(result["profile"], cli.record(self.profile))
        with mock.patch.object(self.store, "current", return_value="20260927T162548-11400"), \
             mock.patch.object(cli, "backend", side_effect=AssertionError("must reject before backend")), \
             self.assertRaises(RuntimeError):
            cli.prepare_speed16(self.store)

    def test_sources_and_known_staging_never_include_the_target_as_old_state(self):
        known = self.api.known_staging_packages(self.c)
        self.assertIn(self.c.previous_assets["package"], known)
        self.assertNotIn(self.c.screen, known)
        paths = {Path(item["path"]) for item in self.c.sources()}
        self.assertIn(ROOT / "tests/ota/test_p34_speed16.py", paths)
        self.assertNotIn(ROOT / "Tools/ota/p34_android_trace.py", paths)
        self.assertEqual({name for name, prior in cli.PREDECESSOR_GROUPS.items() if prior == cli.SPEED16_GROUP},
                         {cli.SPEED32_GROUP})
        self.assertEqual({name for name, prior in cli.PREDECESSOR_GROUPS.items() if prior == cli.SPEED32_GROUP},
                         {"patch32-bootstrap"})


TEST_CLASSES = (Speed16Tests,)
