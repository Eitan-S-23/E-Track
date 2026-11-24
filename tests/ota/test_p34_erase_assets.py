"""Real erase asset, lineage, profile and HTTP contracts; no device I/O."""
import copy
import json
import os
from pathlib import Path
from types import SimpleNamespace
import unittest
import urllib.parse
from unittest import mock
import p34_session as cli

ROOT = Path(__file__).resolve().parents[2]
assets = cli.load_module("tested_erase_assets", ROOT / "Tools/ota/p34_erase_assets.py")


class Tests(unittest.TestCase):
    def test_actual_assets_and_header_only_measurement(self):
        value = assets.load()
        a, b = (value["groups"][n] for n in ("bootstrap", "measure"))
        self.assertEqual((a["target_identity"]["version_code"], b["target_identity"]["version_code"]), (30241, 30242))
        self.assertEqual(b["receiver"], a["target"])
        self.assertEqual(a["target_bindings"]["whole_boot"]["sha256"], assets.boot.BOOT_SHA)
        self.assertEqual(len(a["negatives"]), 4)
        self.assertEqual(len(b["negatives"]), 4)

    def test_axes_and_old_dependencies_remain_separate(self):
        for group in cli.ERASE_GROUPS:
            self.assertEqual(cli.cells_for(group)["s04"], (921600, 28))
        self.assertEqual(cli.PREDECESSOR_GROUPS["erase-bootstrap"], "cost-measure")
        self.assertEqual(cli.PREDECESSOR_GROUPS["erase-measure"], "erase-bootstrap")
        self.assertNotIn("erase-bootstrap", cli.patch_asset_groups("cost-measure"))
        self.assertEqual(cli.patch_asset_groups("erase-measure"), (*cli.patch_asset_groups("cost-measure"), "erase-bootstrap", "erase-measure"))

    def test_wrong_receiver_and_boot_fail_without_context_mutation(self):
        g = assets.load()["groups"]["bootstrap"]
        for wrong in ("version", "boot", "target"):
            c = SimpleNamespace(receiver_version=30240, bindings=copy.deepcopy(g["receiver_bindings"]),
                                previous_assets=dict(target=g["receiver"]))
            if wrong == "version": c.receiver_version = 30239
            if wrong == "boot": c.bindings["whole_boot"] = {}
            if wrong == "target": c.previous_assets["target"] = {}
            before = copy.deepcopy(c.__dict__)
            with self.subTest(wrong=wrong), self.assertRaises(RuntimeError):
                assets.load_for_context(c, cli.ERASE_GROUPS["erase-bootstrap"])
            self.assertEqual(c.__dict__, before)

    def context_check(self, group):
        store = cli.Store(ROOT)
        path = store.base / "profile-cost-measure.json"
        profile = dict(store.read(path), patch_group=group, install_cost=True, block_erase=True,
            patch_assets=cli.record(ROOT / assets.RELATIVE),
            patch_prior_assets={cli.ALL_PATCH_GROUPS[n]["assets"]: cli.record(ROOT / cli.ALL_PATCH_GROUPS[n]["assets"])
                                for n in cli.patch_asset_groups(group)[:-1]})
        module = cli.load_module("erase_backend_tests", ROOT / "Tools/ota/p34_session_backend.py")
        api = module.Backend(store, path, profile, group)
        c = api.context(Path(os.environ["P34_TEST_OUT"]) / group)
        spec = cli.ERASE_GROUPS[group]
        self.assertEqual((c.receiver_version, c.target_version), (spec["receiver"], spec["target_version"]))
        self.assertEqual(c.BOOT_SHA, assets.boot.BOOT_SHA)
        self.assertEqual(c.full_assets["target_bindings"]["whole_boot"], c.bindings["whole_boot"])
        self.assertIn(str(ROOT / "Tools/ota/p34_erase_assets.py"), {x["path"] for x in c.sources()})
        phone = api.phone(c, "erase_" + group)
        origin = "https://fixture.trycloudflare.com"
        config = phone.config(c, "s04", 921600, 28, origin)
        self.assertEqual((config["transferMode"], config["senderWindowSegments"], config["targetVersionCode"]), ("full", 28, spec["target_version"]))
        notes = phone.service_config(c, origin)["releases"][c.release_key]["releaseNotes"]
        self.assertIn("diagnostic", notes)
        service = c.service.V2ServiceState(phone.service_config(c, origin), str(ROOT),
            active_release=c.release_key, now_fn=lambda: 1000)
        status, _, body = service.handle_latest(list(phone.latest_query(c).items()), request_id="erase-test")
        self.assertEqual(status, 200)
        metadata = json.loads(body)
        api.validate_served(c, metadata, origin)
        query = urllib.parse.parse_qsl(urllib.parse.urlsplit(metadata["asset"]["downloadUrl"]).query)
        status, _, data = service.handle_download(query, None, None, request_id="erase-test")
        self.assertEqual((status, data), (200, c.screen_bytes))
        bad = copy.deepcopy(metadata)
        bad["asset"]["fileName"] = bad["asset"]["fileName"].replace("-full.etu", ".etu")
        with self.assertRaisesRegex(RuntimeError, "filename"):
            api.validate_served(c, bad, origin)
        self.assertIn(assets.diagnostic_package(), api.known_staging_packages(c))
        prior = dict(plan=dict(target_bindings=copy.deepcopy(c.bindings)))
        with mock.patch.object(cli, "completed_full_predecessor", return_value=prior):
            self.assertIs(api.predecessor(c), prior)
            prior["plan"]["target_bindings"]["whole_boot"] = {}
            with self.assertRaises(RuntimeError): api.predecessor(c)
        for flag in ("install_cost", "block_erase", "boot_copy", "ack_batch"):
            with self.subTest(flag=flag), self.assertRaises(RuntimeError):
                module.Backend(store, path, dict(profile, **{flag: False}), group)

    def test_real_bootstrap_context_service_and_predecessor(self):
        self.context_check("erase-bootstrap")

    def test_real_measure_context_service_and_predecessor(self):
        self.context_check("erase-measure")
