"""Receive-restore asset, lineage and no-replay host regressions."""
import copy
import os
from pathlib import Path
import sys
import types
import unittest
from unittest import mock
import uuid

ROOT = Path(__file__).resolve().parents[2]
OUTPUT = Path(os.environ["P34_TEST_OUT"])
sys.path.insert(0, str(ROOT / "Tools/ota"))
import p34_session as cli


class ReceiveTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.store = cli.Store(ROOT)
        cls.assets = cli.patch_assets_api(cls.store, "receive-bootstrap")
        cls.manifest = cls.assets.load()
        cls.path = ROOT / ".cache/p34-session/profile-receive-bootstrap.json"
        cls.profile = cls.store.read(cls.path)
        cls.apis, cls.contexts = {}, {}
        for group in cli.RECEIVE_GROUPS:
            profile = dict(cls.profile, patch_group=group)
            api = (cli.backend(cls.store, cls.path, group) if group == "receive-bootstrap" else
                   type(cls.apis["receive-bootstrap"])(cls.store, cls.path, profile, group))
            cls.apis[group] = api
            cls.contexts[group] = api.context(OUTPUT / "receive-context" / group)

    def fixture(self):
        store = cli.Store(ROOT)
        store.base = store.checked(OUTPUT / "receive-fixtures" / uuid.uuid4().hex)
        return store

    def test_actual30228_and_new_build_are_bound(self):
        admission = self.assets.verify_admission(self.store)
        self.assertEqual(admission["predecessor"], self.profile["predecessor"])
        self.assertEqual(admission["predecessor"]["run"], "20260929T081420-42700")
        build = self.store.read(ROOT / self.assets.BUILD_REPORT)
        self.assertEqual((build["result"], build["app_bytes"], build["staging_context_bytes"]),
                         ("RECEIVE_APP_BUILD_PASS", 614632, 16))
        self.assertFalse(build["boot_built"])
        self.assertTrue(build["qe_reuse"])

    def test_old_private_engines_keep_their_defaults(self):
        for group, versions in (("patch-bootstrap", (30223, 30224)), ("patch32-bootstrap", (30227, 30228))):
            api = cli.patch_assets_api(self.store, group)
            old = api if group == "patch-bootstrap" else api.engine()
            self.assertEqual((old.prep.AA, old.prep.AB), versions)
            self.assertEqual(old.EXPECTED_BUILD_RESULT, "PATCH_APP_BUILD_PASS")
            self.assertNotEqual(old.OUT, self.assets.engine().OUT)
            old.load()

    def test_successors_only_differ_in_headers_and_keep_Boot(self):
        aa, ab = (self.manifest["images"][key] for key in ("aa", "ab"))
        raw = [Path(p["image"]["path"]).read_bytes() for p in (aa, ab)]
        self.assertEqual(raw[0][:0x400] + raw[0][0x460:], raw[1][:0x400] + raw[1][0x460:])
        self.assertEqual((aa["identity"]["version_code"], ab["identity"]["version_code"]), (30229, 30230))
        for item in (aa, ab):
            self.assertEqual(item["bindings"]["whole_boot"], self.manifest["historical_receiver_bindings"]["whole_boot"])

    def test_legal_exact_pressure_and_both_decoders(self):
        self.assertFalse(self.manifest["formal_reference_admitted"])
        self.assertEqual(self.manifest["groups"]["pressure"]["package"]["bytes"], 1048576)
        self.assertNotIn("receive-compact", cli.GROUPS)
        for name, group in self.manifest["groups"].items():
            self.assertTrue(group["native"]["passed"])
            self.assertEqual(Path(group["decoded"]["path"]).read_bytes(), Path(group["target"]["path"]).read_bytes())
            self.assertTrue(all(case["native"]["passed"] and case["native"]["prepares"] == 0 for case in group["negatives"]))
            if name != "bootstrap":
                self.assertTrue(group["legacy_native"]["passed"])

    def test_axes_and_old_lineage_are_explicit(self):
        for group in cli.RECEIVE_GROUPS:
            self.assertEqual(cli.cells_for(group)["s04"], (921600, 32))
            self.assertEqual(cli.patch_asset_groups(group)[:2], ("patch32-bootstrap", "patch32-pressure"))
        self.assertEqual(cli.patch_asset_groups("patch32-pressure"), ("patch32-bootstrap", "patch32-pressure"))
        self.assertEqual(cli.patch_asset_groups("receive-pressure")[-2:], ("receive-bootstrap", "receive-pressure"))

    def test_context_uses_new_receiver_MAP_only_after_bootstrap(self):
        a, b = self.contexts["receive-bootstrap"], self.contexts["receive-pressure"]
        self.assertEqual((a.receiver_version, a.target_version, b.receiver_version, b.target_version), (30228, 30229, 30229, 30230))
        self.assertNotEqual(a.bindings["profile"]["map"], b.bindings["profile"]["map"])
        self.assertEqual(b.bindings, a.full_assets["target_bindings"])
        self.assertEqual(b.flash_addresses, b.bindings["flash_admission_addresses"])

    def test_phone_and_service_preserve_window_and_PATCH_base(self):
        for group, c in self.contexts.items():
            phone = self.apis[group].phone(c, "receive-phone-test")
            config = phone.config(c, "s04", 921600, 32, "https://fixture.trycloudflare.com")
            self.assertEqual((config["transferMode"], config["prefixBytes"], config["senderWindowSegments"]), ("full", 0, 32))
            self.assertTrue(config["reuseGatt"] and config["withoutResponse"])
            with self.assertRaises(RuntimeError):
                phone.config(c, "s04", 921600, 8, "https://fixture.trycloudflare.com")
            asset = phone.service_config(c, "https://fixture.trycloudflare.com")["releases"][c.release_key]["asset"]
            self.assertEqual(asset["kind"], c.package_kind)
            self.assertEqual(asset["baseVersionCode"], c.receiver_version if c.package_kind == "patch" else 0)

    def test_wrong_profile_flags_and_prior_assets_fail_closed(self):
        for change in (dict(receive_restore=False), dict(native_diagnostic=True), dict(tunnel_protocol="http2")):
            with self.subTest(change=change), self.assertRaisesRegex(RuntimeError, "receive-restore profile"):
                type(self.apis["receive-bootstrap"])(self.store, self.path, dict(self.profile, **change), "receive-bootstrap")
        profile = dict(self.profile, patch_prior_assets={})
        api = type(self.apis["receive-bootstrap"])(self.store, self.path, profile, "receive-bootstrap")
        with self.assertRaisesRegex(RuntimeError, "prior PATCH asset"):
            api.context(OUTPUT / "bad-prior")

    def test_wrong_manifest_spec_rejected(self):
        for change in (dict(receiver=30227), dict(target_version=30229), dict(kind="full"), dict(assets="other.json")):
            with self.subTest(change=change), self.assertRaises(RuntimeError):
                self.assets.load_for_context(self.contexts["receive-pressure"], dict(cli.RECEIVE_GROUPS["receive-pressure"], **change))

    def test_wrong_candidate_build_is_not_admitted(self):
        read = cli.Store.read
        for change in (dict(result="PATCH_APP_BUILD_PASS"), dict(qe_reuse=False),
                       dict(boot_built=True), dict(finalized=True), dict(staging_context_bytes=20)):
            def changed(store, path):
                value = read(store, path)
                return dict(value, **change) if Path(path) == ROOT / self.assets.BUILD_REPORT else value
            with self.subTest(change=change), mock.patch.object(cli.Store, "read", changed), \
                 self.assertRaisesRegex(RuntimeError, "receive-restore candidate"):
                self.assets.verified_build()

    def test_two_transitions_start_once(self):
        for prior_group, group in (("patch32-pressure", "receive-bootstrap"),
                                   ("receive-bootstrap", "receive-pressure")):
            store = self.fixture()
            old, profile = store.run("previous"), store.base / "profile.json"
            store.write(profile, dict(predecessor={}))
            store.write(store.base / "current.json", dict(run=old.name))
            store.write(old / "plan.json", dict(group=prior_group))
            calls = []
            def launch(path, *args):
                calls.append(path.name)
                if path.name == "network":
                    store.write(path.parent.parent / "live-network.json", {})
            c = types.SimpleNamespace(supervisor=types.SimpleNamespace(owned=types.SimpleNamespace(launch=launch)))
            api = types.SimpleNamespace(context=lambda out: c, preflight=lambda *args: None,
                inspect=lambda *args: dict(result="APP_INSPECTED"), network_ready=lambda *args: None,
                prepare=lambda c, out, phone, tests: store.write(out / "plan.json", dict(group=group)))
            state = dict(result="fixture", network=dict(state="CLOSED"))
            with mock.patch.object(cli, "verify_tests", return_value={}), mock.patch.object(cli, "status", return_value=state), \
                 mock.patch.object(cli, "completed_full_predecessor", return_value=dict(out=old, descriptor={})), \
                 mock.patch.object(cli, "backend", return_value=api) as factory:
                cli.start(store, profile, "s04", group)
                factory.reset_mock()
                self.assertEqual(cli.start(store, profile, "s04", group), state)
                factory.assert_not_called()
            self.assertEqual(calls, ["network", "s04"])

    def test_pressure_profile_requires_actual_completed30229(self):
        with mock.patch.object(self.store, "current", return_value="20260929T081420-42700"), \
             mock.patch.object(cli, "backend", side_effect=AssertionError("future predecessor")), \
             self.assertRaisesRegex(RuntimeError, "actual completed predecessor"):
            cli.prepare_patch(self.store, "receive-pressure")

    def test_source_pins_and_known_staging_exclude_new_target(self):
        for group, c in self.contexts.items():
            known = self.apis[group].known_staging_packages(c)
            self.assertIn(c.previous_assets["package"], known)
            self.assertNotIn(c.screen, known)
            paths = {Path(p["path"]) for p in c.sources()}
            self.assertIn(ROOT / "Tools/ota/p34_receive_assets.py", paths)
            self.assertIn(ROOT / "tests/ota/test_p34_receive.py", paths)
            self.assertIn(ROOT / ".cache/p34-patch32/assets/result.json", paths)

    def test_cleanup_selects_only_original30227_and_protects30228(self):
        with mock.patch.object(self.store, "current", return_value="20260929T081420-42700"):
            selected = cli.completed_capture_target(self.store, "20260929T075409-91600")
            self.assertEqual(selected["capture"], "1790668713353005-ef0d63b6ae7d5f5566f7396b")
            with self.assertRaises(RuntimeError):
                cli.completed_capture_target(self.store, "20260929T081420-42700")

    def test_asset_reuse_never_repacks(self):
        before = cli.record(ROOT / self.assets.RELATIVE)
        with mock.patch.object(self.assets, "engine", wraps=self.assets.engine):
            result = self.assets.prepare(self.store)
        self.assertTrue(result["reused"])
        self.assertEqual(cli.record(ROOT / self.assets.RELATIVE), before)

    def test_fast_recovery_preserves_search_failures_and_packages(self):
        api = self.assets.engine()
        self.assertEqual(self.store.read(api.OUT / "failed.json")["error"],
                         "Bounded compression budget exhausted; no exact witness")
        intent = self.store.read(api.OUT / "neighbor-recovery/intent.json")
        api.prep.verify_records(intent["originals"])
        self.assertEqual(intent["max_new_measurements"], 128)
        self.assertEqual(intent["helper_binding"]["version_mapping"], {"30226": 30228, "30227": 30229, "30228": 30230})
        self.assertEqual(self.store.read(api.OUT / "neighbor-recovery/failed.json")["error"],
                         "neighbor budget exhausted; preserve all original assets")
        for record in (intent["source"], intent["helper_binding"]["original"], intent["helper_binding"]["generated"]):
            self.assertEqual(cli.record(record["path"]), record)
        tail = self.store.read(api.OUT / "tail-recovery/intent.json")
        api.prep.verify_records(tail["originals"])
        self.assertEqual(tail["max_new_measurements"], 128)
        self.assertTrue(tail["no_padding"])
        self.assertEqual(self.store.read(api.OUT / "tail-recovery/failed.json")["error"], "consumed-seek budget exhausted")
        fast = self.store.read(api.OUT / "fast-recovery/intent.json")
        api.prep.verify_records(fast["originals"])
        self.assertEqual(fast["max_new_measurements"], 512)
        self.assertEqual(fast["encoder"], dict(mode="FAST", nice_len=32, match_finder="HC3", depth=8,
                                              dict_size=16384, lc=2, lp=0, pb=0))
        self.assertTrue(self.store.read(api.OUT / "fast-recovery/result.json")["originals_unchanged"])
        witness = self.store.read(api.OUT / "fast-recovery/pressure/proof/witness.json")
        self.assertTrue(witness["lzma_full_consumption"] and witness["bspatch_byte_identical"])

    def test_completed_pressure_has_no_implicit_successor(self):
        store = self.fixture()
        out = store.run("attempted")
        store.write(store.base / "current.json", dict(run=out.name))
        store.write(out / "plan.json", dict(group="receive-pressure"))
        with mock.patch.object(cli, "verify_tests", return_value={}), \
             mock.patch.object(cli, "status", return_value=dict(result="original")), \
             mock.patch.object(cli, "backend", side_effect=AssertionError("replay")):
            for group in cli.GROUPS:
                if cli.PREDECESSOR_GROUPS.get(group) == "receive-pressure":
                    # Only a direct successor can request a prepared profile;
                    # merely advancing the group cannot launch a device worker.
                    with self.assertRaises(FileNotFoundError):
                        cli.start(store, store.base / "unused.json", "s04", group)
                else:
                    self.assertEqual(cli.start(store, store.base / "unused.json", "s04", group)["result"], "original")


TEST_CLASSES = (ReceiveTests,)
