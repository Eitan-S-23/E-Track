"""Reconnect lineage, exact APK, cadence and original-observation host checks."""
import copy
import json
import os
from pathlib import Path
from types import SimpleNamespace
import unittest
from unittest import mock

import p34_session as cli

ROOT = Path(__file__).resolve().parents[2]
assets = cli.load_module("reconnect_test_assets", ROOT / "Tools/ota/p34_reconnect_assets.py")
profile_api = cli.load_module("reconnect_test_profile", ROOT / "Tools/ota/p34_reconnect_profile.py")
backend = cli.load_module("reconnect_test_backend", ROOT / "Tools/ota/p34_session_backend.py")
capture = cli.load_module("reconnect_test_capture", ROOT / "Tools/ota/p34_observation.py")


class Tests(unittest.TestCase):
    def test_archive_selects_only_completed30241_and_protects30242(self):
        archive = cli.load_module("reconnect_archive_test", ROOT / "Tools/ota/p34_cost_archive.py")
        with mock.patch.object(cli.Store, "current", return_value=assets.PREDECESSOR), \
             mock.patch.object(cli, "verify_tests"), \
             mock.patch.object(cli, "backend", side_effect=RuntimeError("stop-before-device")) as load:
            with self.assertRaisesRegex(RuntimeError, "stop-before-device"):
                archive.run(reconnect=True)
            self.assertEqual(load.call_args.args[1:],
                             (ROOT / ".cache/p34-session/profile-erase-measure.json", "erase-measure"))
        with mock.patch.object(cli.Store, "current", return_value="wrong-owner"), \
             mock.patch.object(cli, "backend") as load:
            with self.assertRaisesRegex(RuntimeError, "current owner changed"):
                archive.run(reconnect=True)
            load.assert_not_called()
        with self.assertRaisesRegex(RuntimeError, "choose one"):
            archive.run(reconnect=True, erase=True)

    def test_header_only_assets_and_axes(self):
        g = assets.load()["groups"]["measure"]
        self.assertEqual(g["specification"], cli.RECONNECT_SPEC)
        self.assertEqual(cli.cells_for(cli.RECONNECT_GROUP)["s04"], (921600, 28))
        self.assertEqual(cli.PREDECESSOR_GROUPS[cli.RECONNECT_GROUP], "erase-measure")
        self.assertEqual(cli.patch_asset_groups(cli.RECONNECT_GROUP),
                         (*cli.patch_asset_groups("erase-measure"), cli.RECONNECT_GROUP))
        self.assertNotIn(cli.RECONNECT_GROUP, cli.patch_asset_groups("erase-measure"))

    def test_wrong_receiver_binding_rejected_without_mutation(self):
        g = assets.load()["groups"]["measure"]
        for field in ("version", "boot", "target"):
            c = SimpleNamespace(receiver_version=30242, bindings=copy.deepcopy(g["receiver_bindings"]),
                                previous_assets=dict(target=g["receiver"]))
            if field == "version": c.receiver_version = 30241
            if field == "boot": c.bindings["whole_boot"] = {}
            if field == "target": c.previous_assets["target"] = {}
            before = copy.deepcopy(vars(c))
            with self.subTest(field=field), self.assertRaises(RuntimeError):
                assets.load_for_context(c, assets.SPEC)
            self.assertEqual(vars(c), before)

    def context(self):
        store = cli.Store(ROOT)
        path = store.base / "profile-erase-measure.json"
        profile = dict(store.read(path), patch_group=cli.RECONNECT_GROUP, reconnect_probe=True,
            reconnect_apk=cli.record(ROOT / profile_api.APK_REPORT),
            patch_assets=cli.record(ROOT / assets.RELATIVE),
            patch_prior_assets={cli.ALL_PATCH_GROUPS[n]["assets"]: cli.record(ROOT / cli.ALL_PATCH_GROUPS[n]["assets"])
                                for n in cli.patch_asset_groups(cli.RECONNECT_GROUP)[:-1]})
        api = backend.Backend(store, path, profile, cli.RECONNECT_GROUP)
        return api, api.context(Path(os.environ["P34_TEST_OUT"]) / "reconnect"), profile

    def test_context_apk_config_service_and_predecessor(self):
        api, c, profile = self.context()
        self.assertEqual(c.apk["sha"], profile_api.SHA)
        self.assertEqual(c.APK_SHA, c.apk["apk"]["sha256"])
        self.assertNotEqual(c.APK_SHA, api.legacy["core"]["APK_SHA"])
        self.assertEqual((c.receiver_version, c.target_version), (30242, 30243))
        self.assertEqual(c.BOOT_SHA, assets.erase.boot.BOOT_SHA)
        phone = api.phone(c, "reconnect_test_phone")
        origin = "https://fixture.trycloudflare.com"
        config = phone.config(c, "s04", 921600, 28, origin)
        profile_api.validate_cadence(config)
        self.assertEqual(config["schema"], 3)
        self.assertEqual(config["targetImageSha256"], c.target["sha256"])
        self.assertIn(str(ROOT / "Tools/ota/p34_reconnect_profile.py"), {x["path"] for x in c.sources()})
        service = c.service.V2ServiceState(phone.service_config(c, origin), str(ROOT),
            active_release=c.release_key, now_fn=lambda: 1000)
        status, _, body = service.handle_latest(list(phone.latest_query(c).items()), request_id="reconnect-test")
        self.assertEqual(status, 200)
        api.validate_served(c, json.loads(body), origin)
        for flag in ("install_cost", "block_erase", "reconnect_probe", "boot_copy", "ack_batch"):
            with self.subTest(flag=flag), self.assertRaises(RuntimeError):
                backend.Backend(api.store, api.profile_path, dict(profile, **{flag: False}), cli.RECONNECT_GROUP)
        prior = dict(plan=dict(target_bindings=copy.deepcopy(c.bindings)))
        with mock.patch.object(cli, "completed_full_predecessor", return_value=prior):
            self.assertIs(api.predecessor(c), prior)

    def test_original_experiment_requires_both_exact_cadence_values(self):
        api, c, _ = self.context()
        expected = api.phone(c, "reconnect_stamp").config(c, "s04", 921600, 28, "https://fixture.trycloudflare.com")
        item = {k: v for k, v in expected.items() if k not in ("target", "firmwareLatestUrl")}
        item.update(configSha256="a" * 64, deviceAddress=expected["target"], endpointHost="fixture.trycloudflare.com")
        line = lambda value: "OTA_EXPERIMENT " + json.dumps(value)
        self.assertEqual(backend.verify_experiment(capture, line(item), expected, "a" * 64), item)
        for field in profile_api.CADENCE:
            for value in (None, True, str(item[field]), item[field] + 1):
                bad = dict(item, **{field: value})
                with self.subTest(field=field, value=value), self.assertRaises(RuntimeError):
                    backend.verify_experiment(capture, line(bad), expected, "a" * 64)
            bad = dict(item)
            del bad[field]
            with self.assertRaises(RuntimeError):
                backend.verify_experiment(capture, line(bad), expected, "a" * 64)

    def test_cadence_rejects_prefix_and_wrong_axes(self):
        base = dict(schema=2, transferMode="full", prefixBytes=0, currentVersionCode=30242,
                    targetVersionCode=30243, requestedBaud=921600, senderWindowSegments=28)
        self.assertEqual(profile_api.config(base)["rebootInfoTimeoutMs"], 2000)
        for field, value in (("schema", 3), ("transferMode", "prefix"), ("prefixBytes", 128),
                             ("currentVersionCode", 30241), ("targetVersionCode", 30242),
                             ("requestedBaud", 460800), ("senderWindowSegments", 32)):
            with self.subTest(field=field), self.assertRaises(RuntimeError):
                profile_api.config(dict(base, **{field: value}))
