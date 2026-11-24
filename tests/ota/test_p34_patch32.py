"""Host-only legal PATCH32 lineage, old-group isolation and no-replay checks."""
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
cli = sys.modules["p34_session"]


class Patch32Tests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.store = cli.Store(ROOT)
        cls.assets = cli.patch_assets_api(cls.store, "patch32-bootstrap")
        cls.manifest = cls.assets.load()
        cls.profile_path = ROOT / ".cache/p34-session/profile-patch32-bootstrap.json"
        cls.profile = cls.store.read(cls.profile_path)
        cls.apis, cls.contexts = {}, {}
        for group in cli.PATCH32_GROUPS:
            # Static pressure context is not evidence that30227 is installed.
            profile = dict(cls.profile, patch_group=group)
            api = (cli.backend(cls.store, cls.profile_path, group) if group == "patch32-bootstrap" else
                   type(cls.apis["patch32-bootstrap"])(cls.store, cls.profile_path, profile, group))
            cls.apis[group] = api
            cls.contexts[group] = api.context(OUTPUT / "patch32-context" / group)

    def fixture(self):
        store = cli.Store(ROOT)
        store.base = store.checked(OUTPUT / "patch32-fixtures" / uuid.uuid4().hex)
        return store

    def test_actual30226_predecessor_and_candidate_build_are_bound(self):
        admission = self.assets.verify_admission(self.store)
        self.assertEqual(admission["predecessor"], self.profile["predecessor"])
        self.assertEqual(admission["predecessor"]["run"], "20260929T061847-23000")
        build = self.store.read(ROOT / self.assets.BUILD_REPORT)
        self.assertTrue(build["coalesce"])
        self.assertEqual((build["warnings"], build["errors"], build["boot_built"]), (638, 0, False))
        self.assertEqual(self.manifest["historical_receiver"], self.contexts["patch32-bootstrap"].previous_assets["target"])

    def test_private_adapter_does_not_change_legacy_versions_or_outputs(self):
        old = cli.patch_assets_api(self.store, "patch-bootstrap")
        new = self.assets.engine()
        self.assertEqual((old.prep.AA, old.prep.AB), (30223, 30224))
        self.assertEqual((new.prep.AA, new.prep.AB), (30227, 30228))
        self.assertNotEqual(old.OUT, new.OUT)
        old_profile = self.store.read(ROOT / ".cache/p34-session/profile-patch-bootstrap.json")
        self.assertEqual(cli.record(ROOT / old.RELATIVE), old_profile["patch_assets"])
        self.assertEqual(old.load()["groups"]["bootstrap"]["receiver"], 30221)
        self.assertIn(Path(self.assets.__file__), new.EXTRA_INPUTS)

    def test_successor_changes_only_header_and_keeps_original_Boot(self):
        a, b = (self.manifest["images"][name] for name in ("aa", "ab"))
        x, y = (Path(item["image"]["path"]).read_bytes() for item in (a, b))
        self.assertEqual(x[:0x400] + x[0x460:], y[:0x400] + y[0x460:])
        self.assertEqual((a["identity"]["version_code"], b["identity"]["version_code"]), (30227, 30228))
        for item in (a, b):
            self.assertEqual(item["bindings"]["whole_boot"], self.manifest["historical_receiver_bindings"]["whole_boot"])
            self.assertEqual(item["bindings"]["profile"]["profile_size"], 336)

    def test_pressure_is_exact_legal_1MiB_not_formal_acceptance(self):
        groups = self.manifest["groups"]
        self.assertEqual(groups["pressure"]["package"]["bytes"], 1048576)
        self.assertFalse(self.manifest["formal_reference_admitted"])
        self.assertFalse(self.manifest["hardware"])
        self.assertEqual(groups["compact"]["target"], groups["pressure"]["target"])
        self.assertNotIn("patch32-compact", cli.GROUPS)
        for name, item in groups.items():
            self.assertTrue(item["native"]["passed"])
            self.assertEqual(Path(item["decoded"]["path"]).read_bytes(), Path(item["target"]["path"]).read_bytes())
            self.assertTrue(all(case["native"]["passed"] and case["native"]["prepares"] == 0 for case in item["negatives"]))
            if name != "bootstrap":
                self.assertTrue(item["legacy_native"]["passed"])
                self.assertEqual(item["native"]["program_calls"], 601)

    def test_new_axes_and_lineage_do_not_change_legacy_groups(self):
        for group in cli.PATCH32_GROUPS:
            self.assertEqual(cli.cells_for(group)["s04"], (921600, 32))
            self.assertEqual(cli.n04_asset_groups(group), cli.n04_asset_groups(cli.SPEED32_GROUP))
            self.assertNotIn(group, cli.WINDOW8_GROUPS)
        for group in cli.PATCH_GROUPS:
            self.assertEqual(cli.cells_for(group)["s04"], (921600, 8))
            self.assertNotIn(cli.SPEED32_GROUP, cli.n04_asset_groups(group))
        self.assertEqual(cli.patch_asset_groups("patch32-pressure"), ("patch32-bootstrap", "patch32-pressure"))

    def test_context_binds_actual_receiver_MAP_and_PATCH_kind(self):
        for group, c in self.contexts.items():
            spec = cli.PATCH32_GROUPS[group]
            self.assertEqual((c.receiver_version, c.target_version), (spec["receiver"], spec["target_version"]))
            self.assertEqual(c.receiver_image_sha, c.full_assets["receiver"]["sha256"])
            self.assertEqual(c.package_kind, spec["kind"])
            self.assertEqual(c.instrumentation["size"], 336)
        a, b = self.contexts.values()
        self.assertNotEqual(a.bindings["profile"]["map"], b.bindings["profile"]["map"])
        self.assertEqual(b.flash_addresses, b.bindings["flash_admission_addresses"])

    def test_config_requires_window32_and_metadata_binds_the_PATCH_base(self):
        for group, c in self.contexts.items():
            phone = self.apis[group].phone(c, "patch32-phone-test")
            config = phone.config(c, "s04", 921600, 32, "https://fixture.trycloudflare.com")
            self.assertEqual((config["transferMode"], config["prefixBytes"], config["senderWindowSegments"]), ("full", 0, 32))
            self.assertTrue(config["reuseGatt"] and config["withoutResponse"])
            with self.assertRaises(RuntimeError):
                phone.config(c, "s04", 921600, 8, "https://fixture.trycloudflare.com")
            asset = phone.service_config(c, "https://fixture.trycloudflare.com")["releases"][c.release_key]["asset"]
            self.assertEqual(asset["kind"], c.package_kind)
            self.assertEqual(asset["baseVersionCode"], c.receiver_version if c.package_kind == "patch" else 0)
            self.assertEqual(asset["sha256"], c.screen["sha256"])

    def test_wrong_flags_and_wrong_assets_spec_fail_before_device(self):
        for change in (dict(patch32=False), dict(native_diagnostic=True), dict(tunnel_protocol="http2")):
            with self.subTest(change=change), self.assertRaisesRegex(RuntimeError, "PATCH32 profile flags"):
                type(self.apis["patch32-bootstrap"])(self.store, self.profile_path, dict(self.profile, **change), "patch32-bootstrap")
        for key, value in (("kind", "full"), ("receiver", 30223), ("target_version", 30224), ("assets", "other.json")):
            with self.subTest(key=key), self.assertRaises(RuntimeError):
                self.assets.load_for_context(self.contexts["patch32-pressure"], dict(cli.PATCH32_GROUPS["patch32-pressure"], **{key: value}))

    def test_pressure_profile_requires_actual_completed30227(self):
        with mock.patch.object(self.store, "current", return_value=self.profile["predecessor"]["run"]), \
             mock.patch.object(cli, "backend", side_effect=AssertionError("must not create a future profile")), \
             self.assertRaisesRegex(RuntimeError, "actual completed predecessor"):
            cli.prepare_patch(self.store, "patch32-pressure")

    def test_source_and_known_staging_sets_exclude_the_new_target(self):
        for group, c in self.contexts.items():
            api = self.apis[group]
            known = api.known_staging_packages(c)
            self.assertIn(c.previous_assets["package"], known)
            self.assertNotIn(c.screen, known)
            paths = {Path(item["path"]) for item in c.sources()}
            self.assertIn(ROOT / "Tools/ota/p34_patch32_assets.py", paths)
            self.assertIn(ROOT / "tests/ota/test_p34_patch32.py", paths)
        old_api = cli.backend(self.store, ROOT / ".cache/p34-session/profile-speed-window32.json", cli.SPEED32_GROUP)
        old_paths = {Path(x["path"]) for x in old_api.context(OUTPUT / "old32-context").sources()}
        self.assertNotIn(ROOT / self.assets.RELATIVE, old_paths)

    def test_cleanup_can_only_select_the_completed_immediate_predecessor(self):
        with mock.patch.object(self.store, "current", return_value="20260929T061847-23000"):
            selected = cli.completed_capture_target(self.store, "20260929T030709-75800")
            self.assertEqual(selected["capture"], "1790651663430351-f87498813e0925f6ea4ed12c")
            self.assertEqual(selected["protected"]["report"]["summary"]["captureId"], "1790663174745616-da201fb2336519ff9ce4b0f5")
            with self.assertRaises(RuntimeError):
                cli.completed_capture_target(self.store, "20260929T061847-23000")

    def test_completed_assets_reuse_never_repackages_or_changes_old_nonces(self):
        before = cli.record(ROOT / self.assets.RELATIVE)
        with mock.patch.object(self.assets, "engine", wraps=self.assets.engine):
            result = self.assets.prepare(self.store)
        self.assertTrue(result["reused"])
        self.assertEqual(cli.record(ROOT / self.assets.RELATIVE), before)

    def test_search_continuation_preserves_the_failure_and_all_partial_assets(self):
        api = self.assets.engine()
        continuation = self.store.read(api.OUT / "search-continuation/intent.json")
        api.prep.verify_records(continuation["originals"])
        self.assertEqual((continuation["cached_measurements"], continuation["max_new_measurements"]), (128, 384))
        self.assertEqual(self.store.read(api.OUT / "failed.json")["error"],
                         "Bounded compression budget exhausted; no exact witness")
        self.assertEqual(self.store.read(api.OUT / "search-continuation/result.json")["device_operations"], 0)
        source = Path(continuation["source"]["path"])
        self.assertEqual(source.read_bytes(), (ROOT / "Tools/ota/p34_patch32_recovery.py").read_bytes())

    def test_search_continuation_cannot_replay_a_completed_preparation(self):
        recovery = cli.load_module("p34_patch32_recovery_tests", ROOT / "Tools/ota/p34_patch32_recovery.py")
        with mock.patch.object(self.store, "current", return_value=self.profile["predecessor"]["run"]), \
             self.assertRaisesRegex(RuntimeError, "preserve partial recovery"):
            recovery.admit(self.store, self.assets.engine())

    def test_search_continuation_rejects_another_failure_before_outputs(self):
        recovery = cli.load_module("p34_patch32_recovery_failure_tests", ROOT / "Tools/ota/p34_patch32_recovery.py")
        read = self.store.read
        def changed(path):
            return dict(error="native decoder failed") if Path(path).name == "failed.json" else read(path)
        with mock.patch.object(self.store, "current", return_value=self.profile["predecessor"]["run"]), \
             mock.patch.object(self.store, "read", side_effect=changed), \
             self.assertRaisesRegex(RuntimeError, "not a search-budget failure"):
            recovery.admit(self.store, self.assets.engine())

    def test_search_continuation_rejects_an_advanced_owner(self):
        recovery = cli.load_module("p34_patch32_advanced_tests", ROOT / "Tools/ota/p34_patch32_recovery.py")
        with mock.patch.object(self.store, "current", return_value="advanced-owner"), \
             self.assertRaisesRegex(RuntimeError, "unchanged completed30226 owner"):
            recovery.admit(self.store, self.assets.engine())

    def test_attempted_pressure_only_has_explicit_receive_successor(self):
        self.assertEqual({name for name, prior in cli.PREDECESSOR_GROUPS.items() if prior == "patch32-pressure"},
                         {"receive-bootstrap"})
        store = self.fixture()
        out = store.run("attempted")
        store.write(store.base / "current.json", dict(run=out.name))
        store.write(out / "plan.json", dict(group="patch32-pressure"))
        with mock.patch.object(cli, "verify_tests", return_value={}), \
             mock.patch.object(cli, "status", return_value=dict(result="original")), \
             mock.patch.object(cli, "backend", side_effect=AssertionError("replay")):
            for group in cli.GROUPS:
                if group == "receive-bootstrap":
                    continue
                self.assertEqual(cli.start(store, store.base / "unused.json", "s04", group)["result"], "original")

    def test_two_explicit_transitions_start_once_and_keep_original_owner(self):
        for prior_group, group in ((cli.SPEED32_GROUP, "patch32-bootstrap"), ("patch32-bootstrap", "patch32-pressure")):
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


TEST_CLASSES = (Patch32Tests,)
