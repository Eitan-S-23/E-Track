"""ACK batching retains complete original bytes and a new forward-only group."""
import copy
import importlib.util
import os
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[2]
SPEC = importlib.util.spec_from_file_location("batch_assets_tested", ROOT / "Tools/ota/p34_ack_batch_assets.py")
M = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(M)


class Tests(unittest.TestCase):
    def test_actual_manifest_and_rejections(self):
        value = M.load()
        for key, bad in (("hardware", True), ("source_delta", [])):
            changed = copy.deepcopy(value); changed[key] = bad
            with self.subTest(key=key), self.assertRaises(RuntimeError):
                M.validate(changed)
        changed = copy.deepcopy(value)
        changed["groups"]["bootstrap"]["negatives"][0]["native"]["prepares"] = 1
        with self.assertRaises(RuntimeError):
            M.validate(changed)

    def test_forward_group_preserves_old_lineage(self):
        cli = M.cli
        self.assertEqual(cli.FULL_VERSIONS[M.GROUP], (30232, 30235))
        self.assertEqual(cli.PREDECESSOR_GROUPS[M.GROUP], "ack-gap-bootstrap")
        self.assertEqual(cli.cells_for(M.GROUP)["s04"], (921600, 32))
        self.assertEqual(cli.patch_asset_groups(M.GROUP), (*cli.patch_asset_groups("ack-gap-bootstrap"), M.GROUP))
        for name in ("ack-gap-bootstrap", "receive-pressure", "patch32-pressure"):
            self.assertNotIn(M.GROUP, cli.patch_asset_groups(name))

    def test_context_and_service_bind_exact_assets(self):
        cli = M.cli
        store = cli.Store(ROOT)
        path = store.base / "profile-ack-gap-bootstrap.json"
        profile = dict(store.read(path), patch_group=M.GROUP, ack_gap=True, ack_batch=True,
            patch_assets=cli.record(ROOT / M.RELATIVE),
            patch_prior_assets={cli.ALL_PATCH_GROUPS[n]["assets"]: cli.record(ROOT / cli.ALL_PATCH_GROUPS[n]["assets"])
                                for n in cli.patch_asset_groups(M.GROUP)[:-1]})
        module = cli.load_module("p34_session_backend", ROOT / "Tools/ota/p34_session_backend.py")
        api = module.Backend(store, path, profile, M.GROUP)
        c = api.context(Path(os.environ["P34_TEST_OUT"]) / "batch-context")
        self.assertEqual((c.receiver_version, c.target_version), (30232, 30235))
        self.assertEqual(c.full_assets["target_bindings"]["whole_boot"], c.bindings["whole_boot"])
        phone = api.phone(c, "batch-test-phone")
        config = phone.config(c, "s04", 921600, 32, "https://fixture.trycloudflare.com")
        self.assertEqual((config["currentVersionCode"], config["targetVersionCode"]), (30232, 30235))
        self.assertEqual((config["transferMode"], config["prefixBytes"]), ("full", 0))
        self.assertIn(M.diagnostic_package(), api.known_staging_packages(c))
        self.assertNotIn(c.screen, api.known_staging_packages(c))
        with self.assertRaises(RuntimeError):
            module.Backend(store, path, dict(profile, ack_batch=False), M.GROUP)

    def test_fifo_header_matches_compiled_candidate(self):
        self.assertEqual((ROOT / "Tools/ota/p34_ack_batch.h").read_bytes(),
                         (M.AREA / "f/USER/HAL/p34_ack_batch.h").read_bytes())
        source = (M.AREA / "f/USER/HAL/HAL_Bluetooth.cpp").read_text(encoding="utf-8")
        self.assertIn("data_ok && durable == s_p34_ack_durable", source)
        self.assertIn("s_p34_ack_batch.end(ble_uart_send)", source)
        self.assertIn("USART_TDC_FLAG", source)
        self.assertIn("288000u, 576000u", source)


if __name__ == "__main__":
    unittest.main(verbosity=2)
