"""Boot replacement is explicit, source-bound, and cannot change App identity."""
import copy
import importlib.util
import os
from pathlib import Path
from types import SimpleNamespace
import unittest
from unittest import mock

ROOT = Path(__file__).resolve().parents[2]
SPEC = importlib.util.spec_from_file_location("boot_ota_tested", ROOT / "Tools/ota/p34_boot_ota_assets.py")
M = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(M)


class Tests(unittest.TestCase):
    def test_predecessor_admits_only_verified_boot_transition(self):
        cli = M.cli
        module = cli.load_module("p34_boot_predecessor_tests", ROOT / "Tools/ota/p34_session_backend.py")
        api = object.__new__(module.Backend)
        api.group, api.store, api.profile, api.patch_api = M.GROUP, object(), {"predecessor": {}}, M
        old, current = M.transition()
        previous = dict(plan=dict(target_bindings=old))
        with mock.patch.object(cli, "completed_full_predecessor", return_value=previous):
            self.assertIs(api.predecessor(SimpleNamespace(bindings=current)), previous)
            for field in ("whole_boot", "profile", "layout", "boot_map"):
                bad = copy.deepcopy(current)
                bad[field] = {}
                with self.subTest(field=field), self.assertRaises(RuntimeError):
                    api.predecessor(SimpleNamespace(bindings=bad))
            api.group = "ack-batch-bootstrap"
            self.assertIs(api.predecessor(SimpleNamespace(bindings=old)), previous)
            with self.assertRaisesRegex(RuntimeError, "receiver differs"):
                api.predecessor(SimpleNamespace(bindings=current))

    def test_assets_and_exact_boot_transition(self):
        value = M.load()
        M.verify_transition(value["historical_receiver_bindings"], value["receiver_bindings"])
        for field in ("whole_boot", "profile", "layout"):
            bad = copy.deepcopy(value["receiver_bindings"])
            bad[field] = {}
            with self.subTest(field=field), self.assertRaises(RuntimeError):
                M.verify_transition(value["historical_receiver_bindings"], bad)

    def test_group_is_forward_and_old_groups_do_not_depend_on_it(self):
        cli = M.cli
        self.assertEqual(cli.FULL_VERSIONS[M.GROUP], (30235, 30238))
        self.assertEqual(cli.cells_for(M.GROUP)["s04"], (921600, 28))
        self.assertEqual(cli.patch_asset_groups(M.GROUP), (*cli.patch_asset_groups("ack-batch-bootstrap"), M.GROUP))
        self.assertNotIn(M.GROUP, cli.patch_asset_groups("ack-batch-bootstrap"))

    def test_loader_rejects_wrong_receiver_without_mutation(self):
        value = M.load()
        c = SimpleNamespace(receiver_version=30232, bindings=copy.deepcopy(value["historical_receiver_bindings"]),
                            previous_assets=dict(target=value["receiver"]))
        before = copy.deepcopy(c.bindings)
        with self.assertRaises(RuntimeError):
            M.load_for_context(c, M.cli.ALL_PATCH_GROUPS[M.GROUP])
        self.assertEqual(c.bindings, before)

    def test_context_and_service_bind_replacement_boot_and_window28(self):
        cli = M.cli
        store = cli.Store(ROOT)
        path = store.base / "profile-ack-batch-bootstrap.json"
        profile = dict(store.read(path), patch_group=M.GROUP, ack_gap=True, ack_batch=True, boot_copy=True,
            patch_assets=cli.record(ROOT / M.RELATIVE),
            patch_prior_assets={cli.ALL_PATCH_GROUPS[n]["assets"]: cli.record(ROOT / cli.ALL_PATCH_GROUPS[n]["assets"])
                                for n in cli.patch_asset_groups(M.GROUP)[:-1]})
        module = cli.load_module("p34_session_backend", ROOT / "Tools/ota/p34_session_backend.py")
        api = module.Backend(store, path, profile, M.GROUP)
        c = api.context(Path(os.environ["P34_TEST_OUT"]) / "boot-copy-context")
        self.assertEqual((c.receiver_version, c.target_version), (30235, 30238))
        self.assertEqual(c.bindings["whole_boot"]["sha256"], M.BOOT_SHA)
        self.assertEqual(c.BOOT_SHA, M.BOOT_SHA)
        self.assertEqual(api.legacy["core"]["Context"].BOOT_SHA, M.device.BOOT_SHA)
        self.assertEqual(c.full_assets["target_bindings"]["boot_map"], c.bindings["boot_map"])
        phone = api.phone(c, "boot-copy-test-phone")
        config = phone.config(c, "s04", 921600, 28, "https://fixture.trycloudflare.com")
        self.assertEqual((config["currentVersionCode"], config["targetVersionCode"]), (30235, 30238))
        self.assertEqual((config["transferMode"], config["prefixBytes"], config["senderWindowSegments"]), ("full", 0, 28))
        self.assertIn(M.diagnostic_package(), api.known_staging_packages(c))
        with self.assertRaises(RuntimeError):
            module.Backend(store, path, dict(profile, boot_copy=False), M.GROUP)


if __name__ == "__main__":
    unittest.main(verbosity=2)
