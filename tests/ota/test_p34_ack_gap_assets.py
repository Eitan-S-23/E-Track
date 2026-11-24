"""ACK-gap family routing does not change historical source dependencies."""
import importlib.util
import os
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[2]
SPEC = importlib.util.spec_from_file_location("gap_session_tests", ROOT / "Tools/ota/p34_session.py")
M = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(M)


class Tests(unittest.TestCase):
    def test_actual_gap_context_and_service_bindings(self):
        store = M.Store(ROOT)
        path = store.base / "profile-receive-pressure.json"
        profile = dict(store.read(path), patch_group="ack-gap-bootstrap", ack_gap=True,
                       native_diagnostic=False, tunnel_protocol="quic",
                       patch_assets=M.record(ROOT / M.ACK_GAP_GROUPS["ack-gap-bootstrap"]["assets"]),
                       patch_prior_assets={M.ALL_PATCH_GROUPS[name]["assets"]:
                           M.record(ROOT / M.ALL_PATCH_GROUPS[name]["assets"])
                           for name in M.patch_asset_groups("ack-gap-bootstrap")[:-1]})
        base = M.backend(store, path, "receive-pressure")
        api = type(base)(store, path, profile, "ack-gap-bootstrap")
        out = Path(os.environ["P34_TEST_OUT"]) / "gap-context"
        context = api.context(out)
        self.assertEqual((context.receiver_version, context.target_version), (30230, 30232))
        self.assertEqual(context.full_assets["target_bindings"]["whole_boot"], context.bindings["whole_boot"])
        phone = api.phone(context, "gap-test-phone")
        config = phone.config(context, "s04", 921600, 32, "https://fixture.trycloudflare.com")
        self.assertEqual((config["transferMode"], config["prefixBytes"]), ("full", 0))
        self.assertEqual(config["targetVersionCode"], 30232)
        paths = {Path(item["path"]) for item in context.sources()}
        self.assertIn(ROOT / "Tools/ota/p34_ack_gap_assets.py", paths)
        known = api.known_staging_packages(context)
        self.assertIn(api.patch_api.diagnostic_package(), known)
        self.assertNotIn(context.screen, known)
        with self.assertRaises(RuntimeError):
            type(base)(store, path, dict(profile, ack_gap=False), "ack-gap-bootstrap")

    def test_forward_only_gap_identity(self):
        spec = M.ACK_GAP_GROUPS["ack-gap-bootstrap"]
        self.assertEqual((spec["receiver"], spec["target_version"]), (30230, 30232))
        self.assertEqual(spec["predecessor_group"], "receive-pressure")
        self.assertEqual(M.cells_for("ack-gap-bootstrap")["s04"], (921600, 32))

    def test_only_gap_depends_on_gap_assets(self):
        self.assertEqual(M.patch_asset_groups("ack-gap-bootstrap"),
                         ("patch32-bootstrap", "patch32-pressure", "receive-bootstrap", "receive-pressure", "ack-gap-bootstrap"))
        for group in ("receive-bootstrap", "receive-pressure", "patch32-bootstrap", "patch32-pressure"):
            self.assertNotIn("ack-gap-bootstrap", M.patch_asset_groups(group))

    def test_loader_selection(self):
        store = M.Store(ROOT)
        self.assertEqual(M.patch_assets_api(store, "ack-gap-bootstrap").GROUP, "ack-gap-bootstrap")
        self.assertEqual(M.patch_assets_api(store, "receive-pressure").RELATIVE,
                         ".cache/p34-receive-screen/assets/result.json")


if __name__ == "__main__":
    unittest.main(verbosity=2)
