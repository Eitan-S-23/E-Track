"""Offline PATCH assets, complete-transfer routing and observation regressions."""
from __future__ import annotations

import copy
import hashlib
import json
import os
from pathlib import Path
import sys
import types
import unittest
from unittest import mock
import uuid
import urllib.parse

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "Tools/ota"))
import p34_session as cli
import p34_patch_assets as assets
import p34_patch_preparation as prep
import p34_full_trace as trace

backend = cli.load_module("p34_patch_session_backend_test", ROOT / "Tools/ota/p34_session_backend.py")
OUTPUT = Path(os.environ["P34_TEST_OUT"])
ORIGIN = "https://fixture.trycloudflare.com"


class PatchAssetsTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.value = assets.load()

    def setUp(self):
        self.store = cli.Store(ROOT)
        self.store.base = self.store.checked(OUTPUT / "patch-assets" / uuid.uuid4().hex)

    def test_three_packages_bind_actual_Y_then_the_same_AA_AB_pair(self):
        value = self.value
        self.assertEqual(set(value["groups"]), {"bootstrap", "compact", "pressure"})
        self.assertEqual(value["historical_receiver"]["sha256"],
                         "ab5bddfc7ab7b35f7d6a4896232c97f7b4d52c4ae92caad5e1fa7cec14bb48d0")
        for name, item in value["groups"].items():
            with self.subTest(name=name):
                self.assertEqual((item["receiver"], item["target_version"]),
                                 (30221, 30223) if name == "bootstrap" else (30223, 30224))
                self.assertTrue(item["native"]["passed"] and item["native"]["boot_ok"])
                self.assertTrue(all(case["native"]["passed"] and case["native"]["prepares"] == 0
                                    for case in item["negatives"]))
        self.assertFalse(value["hardware"] or value["independent_acceptance"] or value["formal_reference_admitted"])

    def test_new_pressure_is_exactly_one_MiB_and_not_the_old_witness(self):
        group = self.value["groups"]["pressure"]
        self.assertEqual(group["package"]["bytes"], 1048576)
        self.assertNotEqual(group["package"]["sha256"],
                            "131624717d5972039ee76847d4a410fc21edebf9a5b4730d37b9dfe2ab04573e")
        self.assertEqual(group["native"]["program_calls"], (group["target"]["bytes"] + 1023) // 1024)
        self.assertGreater(group["legacy_native"]["program_calls"], group["native"]["program_calls"])
        self.assertEqual(group["native"]["base_reads"], group["legacy_native"]["base_reads"])

    def test_AB_changes_only_the_standard_header_not_AA_executable(self):
        images = self.value["images"]
        aa, ab = (Path(images[name]["image"]["path"]).read_bytes() for name in ("aa", "ab"))
        self.assertEqual(aa[:0x400] + aa[0x460:], ab[:0x400] + ab[0x460:])
        self.assertNotEqual(aa[0x400:0x460], ab[0x400:0x460])
        self.assertEqual(images["aa"]["bindings"]["whole_boot"], self.value["historical_receiver_bindings"]["whole_boot"])

    def test_reuse_cannot_rebuild_repack_or_overwrite_any_nonce(self):
        with mock.patch.object(prep.common, "run", side_effect=AssertionError("rerun")), \
                mock.patch.object(prep, "raw", side_effect=AssertionError("write")), \
                mock.patch.object(prep, "save", side_effect=AssertionError("write")):
            self.assertEqual(assets.prepare(), dict(result=assets.RESULT, reused=True))

    def test_changed_binding_kind_or_native_result_is_rejected(self):
        for keys, replacement in ((('historical_receiver', 'sha256'), '0' * 64),
                (('groups', 'compact', 'kind'), 'full'),
                (('groups', 'pressure', 'native', 'program_calls'), 1),
                (('images', 'aa', 'bindings', 'flash_admission_addresses', 'jedec'), 0x20000000)):
            value = copy.deepcopy(self.value)
            at = value
            for key in keys[:-1]:
                at = at[key]
            at[keys[-1]] = replacement
            with self.subTest(keys=keys), self.assertRaises(RuntimeError):
                assets.validate_manifest(value)

    def test_decoder_provenance_allows_only_CRLF_normalization(self):
        root = self.store.base
        original = root / "Libraries/OTA/fixture.c"
        candidate = root / "candidate/Libraries/OTA/fixture.c"
        self.store.raw(original, b"int value;\r\n")
        self.store.raw(candidate, b"int value;\n")
        host = dict(inputs=[cli.record(original)], binaries=[])
        with mock.patch.object(assets, "ROOT", root), mock.patch.object(prep, "FW", root / "candidate"):
            result = assets.decoder_equivalence(host)
            self.assertEqual(result[0]["comparison"], "CRLF/LF-only")
            bad = copy.deepcopy(host)
            bad["inputs"][0]["sha256"] = "0" * 64
            with self.assertRaisesRegex(RuntimeError, "bound input changed"):
                assets.decoder_equivalence(bad)
        changed = root / "changed/Libraries/OTA/fixture.c"
        self.store.raw(changed, b"int other;\n")
        with mock.patch.object(assets, "ROOT", root), mock.patch.object(prep, "FW", root / "changed"), \
                self.assertRaisesRegex(RuntimeError, "source differs"):
            assets.decoder_equivalence(host)


class PatchSessionTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.real_store = cli.Store(ROOT)
        cls.profile_path = ROOT / ".cache/p34-session/profile-patch-bootstrap.json"
        cls.profile = cls.real_store.read(cls.profile_path)
        cls.apis, cls.contexts = {}, {}
        for group in cli.PATCH_GROUPS:
            # Alternative contexts are static binding fixtures, not installed-AA evidence.
            profile = dict(cls.profile, patch_group=group)
            api = backend.Backend(cls.real_store, cls.profile_path, profile, group)
            cls.apis[group], cls.contexts[group] = api, api.context(OUTPUT / "patch-contexts" / group)

    def setUp(self):
        self.store = cli.Store(ROOT)
        self.store.base = self.store.checked(OUTPUT / "patch-session" / uuid.uuid4().hex)
        self.out = self.store.run("fixture")

    def test_bootstrap_profile_uses_original_completed_Y_without_installing_AA(self):
        prior = self.profile["predecessor"]
        self.assertEqual(prior["run"], "20260927T162548-11400")
        self.assertEqual(prior["report"], cli.record(prep.Y_RESULT))
        self.assertEqual(self.real_store.read(prior["plan"]["path"])["target_version"], 30221)
        self.assertIn("P34-WAIT-01", self.profile["scope"])
        self.assertEqual(self.profile["patch_group"], "patch-bootstrap")

    def test_groups_keep_window8_and_do_not_acquire_Z_dependencies(self):
        for group in cli.PATCH_GROUPS:
            self.assertEqual(cli.cells_for(group)["s04"], (921600, 8))
            self.assertEqual(cli.n04_asset_groups(group), ("n04-bootstrap", "n04-measure"))
        self.assertEqual(cli.patch_asset_groups("patch-compact"), ("patch-bootstrap", "patch-compact"))
        self.assertEqual(cli.patch_asset_groups("patch-pressure"), ("patch-bootstrap", "patch-pressure"))
        self.assertEqual(cli.cells_for("n04-window16")["s04"], (921600, 16))
        with self.assertRaises(RuntimeError):
            cli.patch_asset_groups("n04-window16")

    def test_actual_context_binds_package_receiver_ABI_and_new_flash_addresses(self):
        for group, c in self.contexts.items():
            with self.subTest(group=group):
                spec = cli.PATCH_GROUPS[group]
                self.assertEqual((c.receiver_version, c.target_version), (spec["receiver"], spec["target_version"]))
                self.assertEqual(c.package_kind, spec["kind"])
                self.assertEqual(c.receiver_image_sha, c.full_assets["receiver"]["sha256"])
                self.assertEqual(c.instrumentation["size"], 336)
                if c.package_kind == "patch":
                    self.assertEqual(c.flash_addresses, c.bindings["flash_admission_addresses"])
                    self.assertNotEqual(c.bindings["profile"]["map"],
                                        self.contexts["patch-bootstrap"].bindings["profile"]["map"])
                    self.assertNotEqual(c.receiver_image_sha, self.contexts["patch-bootstrap"].receiver_image_sha)

    def test_context_view_rejects_kind_spec_receiver_and_manifest_mismatch(self):
        c = self.contexts["patch-compact"]
        spec = cli.PATCH_GROUPS["patch-compact"]
        for key, value in (("kind", "full"), ("assets", "other.json"), ("target_version", 30225),
                           ("served_name", "other-patch.etu")):
            with self.subTest(key=key), self.assertRaises(RuntimeError):
                assets.load_for_context(c, dict(spec, **{key: value}))
        with mock.patch.object(c, "receiver_version", 30221), self.assertRaises(RuntimeError):
            assets.load_for_context(c, spec)

    def test_complete_transfer_config_and_HTTP_kind_are_independent(self):
        for group, c in self.contexts.items():
            api = self.apis[group]
            phone = api.phone(c, "patch_config_test", producer=True)
            config = phone.config(c, "s04", 921600, 8, ORIGIN)
            self.assertEqual((config["transferMode"], config["prefixBytes"], config["senderWindowSegments"]), ("full", 0, 8))
            release = phone.service_config(c, ORIGIN)["releases"][c.release_key]
            asset = release["asset"]
            self.assertEqual(asset["kind"], c.package_kind)
            self.assertEqual(asset["baseVersionCode"], c.receiver_version if c.package_kind == "patch" else 0)
            self.assertEqual(asset["baseImageSha256"], c.receiver_image_sha if c.package_kind == "patch" else None)
            self.assertTrue(asset["fileName"].endswith("-" + c.package_kind + ".etu"))
            for cell, baud, window in (("s01", 921600, 8), ("s04", 460800, 8), ("s04", 921600, 16)):
                with self.assertRaises(RuntimeError):
                    phone.config(c, cell, baud, window, ORIGIN)

    def metadata(self, group):
        c, api = self.contexts[group], self.apis[group]
        release = api.phone(c, "patch_metadata_test", producer=True).service_config(c, ORIGIN)["releases"][c.release_key]
        value = dict(release, schemaVersion=2, updateAvailable=True, errorCode=None, appId="trace",
            deviceModel=c.service.DEVICE_MODEL, channel="stable", transport="ble", requestId="fixture")
        value["asset"] = dict(release["asset"], expiresAt=1, downloadUrl=ORIGIN + "/" + api.served_name)
        return value

    def test_HTTP_validation_accepts_complete_bound_full_and_patch_metadata(self):
        for group, c in self.contexts.items():
            self.assertIsNone(self.apis[group].validate_served(c, self.metadata(group), ORIGIN))

    def test_real_service_metadata_signed_download_and_range_use_actual_PATCH(self):
        for group in ("patch-compact", "patch-pressure"):
            c, api = self.contexts[group], self.apis[group]
            phone = api.phone(c, "patch_real_service", producer=True)
            config = phone.service_config(c, ORIGIN)
            original = copy.deepcopy(config)
            state = c.service.V2ServiceState(config, str(ROOT), active_release=c.release_key, now_fn=lambda: 1000)
            self.assertEqual(config, original)
            status, _, body = state.handle_latest(list(phone.latest_query(c).items()), request_id="fixture")
            value = json.loads(body)
            self.assertEqual(status, 200)
            api.validate_served(c, value, ORIGIN)
            query = urllib.parse.parse_qsl(urllib.parse.urlsplit(value["asset"]["downloadUrl"]).query)
            status, _, data = state.handle_download(query, None, None, request_id="fixture")
            self.assertEqual((status, data), (200, c.screen_bytes))
            status, headers, data = state.handle_download(query, "bytes=1-", None, request_id="fixture")
            self.assertEqual((status, data), (206, c.screen_bytes[1:]))
            self.assertIn("Content-Range", dict(headers))
            altered = [(key, "full" if key == "kind" else value) for key, value in query]
            with self.assertRaises(c.service.ServiceError):
                state.handle_download(altered, None, None, request_id="fixture")
            state.now_fn = lambda: 1300
            with self.assertRaises(c.service.ServiceError):
                state.handle_download(query, None, None, request_id="fixture")

    def test_real_PATCH_service_rejects_wrong_base_and_leaves_FULL_service_unchanged(self):
        c, api = self.contexts["patch-compact"], self.apis["patch-compact"]
        phone = api.phone(c, "patch_base_service", producer=True)
        config = phone.service_config(c, ORIGIN)
        state = c.service.V2ServiceState(config, str(ROOT))
        for key, value in (("currentVersionCode", "30221"), ("currentImageSha", "0" * 64)):
            query = dict(phone.latest_query(c), **{key: value})
            with self.assertRaises(c.service.ServiceError):
                state.handle_latest(list(query.items()), request_id="fixture")
        bad = copy.deepcopy(config)
        bad["releases"][c.release_key]["asset"]["baseImageSha256"] = "0" * 64
        with self.assertRaises(RuntimeError):
            c.service.V2ServiceState(bad, str(ROOT))
        original_service = self.contexts["patch-bootstrap"].service
        with self.assertRaises(original_service.ServiceConfigError):
            original_service.V2ServiceState(config, str(ROOT))

    def test_PATCH_HTTP_rejects_full_kind_wrong_base_short_hash_and_wrong_filename(self):
        group, c = "patch-pressure", self.contexts["patch-pressure"]
        value = self.metadata(group)
        for key, item in (("kind", "full"), ("baseVersionCode", 0), ("baseVersionCode", True),
                          ("baseImageSha256", c.receiver_image_sha[:16]), ("baseImageSha256", None),
                          ("baseImageSha256", "0" * 64), ("fileName", "p34-coalesce-pressure-full.etu"),
                          ("sizeBytes", 1048575)):
            bad = dict(value, asset=dict(value["asset"], **{key: item}))
            with self.subTest(key=key, item=item), self.assertRaises(RuntimeError):
                self.apis[group].validate_served(c, bad, ORIGIN)
        bad = copy.deepcopy(value)
        del bad["asset"]["baseImageSha256"]
        with self.assertRaises(RuntimeError):
            self.apis[group].validate_served(c, bad, ORIGIN)

    def test_fresh_begin_knows_only_predecessors_not_target_or_other_alternative(self):
        for group, c in self.contexts.items():
            known = self.apis[group].known_staging_packages(c)
            self.assertIn(c.previous_assets["package"], known)
            self.assertNotIn(c.screen, known)
            if c.package_kind == "patch":
                other = "patch-pressure" if group == "patch-compact" else "patch-compact"
                self.assertNotIn(self.contexts[other].screen, known)

    def test_patch_source_pins_include_driver_build_and_frozen_assets(self):
        c = self.contexts["patch-pressure"]
        paths = {Path(item["path"]) for item in c.sources()}
        for name in ("Tools/ota/p34_patch_assets.py", "Tools/ota/p34_patch_preparation.py",
                     "tests/ota/test_p34_patch_session.py", assets.RELATIVE, assets.BUILD_REPORT):
            self.assertIn(ROOT / name, paths)
        self.assertNotIn(ROOT / cli.N04_GROUPS["n04-window16"]["assets"], paths)

    def fixture_current(self, group):
        self.store.write(self.store.base / "current.json", dict(run=self.out.name))
        self.store.write(self.out / "plan.json", dict(group=group))

    def test_alternative_preparation_refuses_Y_without_fabricating_installed_AA(self):
        self.fixture_current("n04-measure")
        with mock.patch.object(cli, "backend", side_effect=AssertionError("unverified AA")):
            for group in ("patch-compact", "patch-pressure"):
                with self.assertRaisesRegex(RuntimeError, "actual completed predecessor"):
                    cli.prepare_patch(self.store, group)
                self.assertFalse((self.store.base / ("profile-" + group + ".json")).exists())

    def test_preparation_refuses_missing_wrong_or_unreconciled_predecessor(self):
        with self.assertRaises(RuntimeError):
            cli.prepare_patch(self.store, "patch-bootstrap")
        self.fixture_current("n04-measure")
        with mock.patch.object(cli, "current_full_descriptor", return_value={}), \
                mock.patch.object(cli, "completed_full_predecessor", return_value=dict(report={})), \
                mock.patch.object(cli, "backend", side_effect=AssertionError("unreconciled timing")), \
                self.assertRaisesRegex(RuntimeError, "timing must be reconciled"):
            cli.prepare_patch(self.store, "patch-bootstrap")

    def test_attempted_alternatives_are_terminal_and_never_replay_or_advance(self):
        for terminal in ("patch-compact", "patch-pressure"):
            store = cli.Store(ROOT)
            store.base = self.store.checked(self.store.base / terminal)
            out = store.run("attempted")
            store.write(store.base / "current.json", dict(run=out.name))
            store.write(out / "plan.json", dict(group=terminal))
            state = dict(result="original-attempt")
            with mock.patch.object(cli, "verify_tests", return_value={}), mock.patch.object(cli, "status", return_value=state), \
                    mock.patch.object(cli, "backend", side_effect=AssertionError("replay")):
                for group in cli.GROUPS:
                    self.assertEqual(cli.start(store, store.base / "unused.json", "s04", group), state)

    def test_explicit_Y_AA_and_AA_AB_transitions_start_each_owner_once(self):
        for prior_group, group in (("n04-measure", "patch-bootstrap"),
                                  ("patch-bootstrap", "patch-compact"), ("patch-bootstrap", "patch-pressure")):
            store = cli.Store(ROOT)
            store.base = self.store.checked(self.store.base / group)
            old, profile = store.run("previous"), store.base / "profile.json"
            store.write(profile, dict(predecessor={}))
            store.write(store.base / "current.json", dict(run=old.name))
            store.write(old / "plan.json", dict(group=prior_group))
            for name in ("s04", "network"):
                store.write(old / "runtime" / name / "closed.json", dict(worker_exit=0))
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
                    mock.patch.object(cli, "completed_full_predecessor", return_value=dict(out=old, descriptor={})) as previous, \
                    mock.patch.object(cli, "backend", return_value=api) as factory:
                cli.start(store, profile, "s04", group)
                previous.assert_called_once_with(store, {}, group=prior_group)
                factory.reset_mock()
                self.assertEqual(cli.start(store, profile, "s04", group), state)
                factory.assert_not_called()
            self.assertEqual(calls, ["network", "s04"])

    def test_actual_trace_analysis_passes_PATCH_kind_and_never_accepts_FULL_as_PATCH(self):
        cell = self.out / "cells/s04"
        native = cell / "native-trace"
        self.store.write(cell / "fresh-begin.json", dict(before=dict(profile=dict(run=0))))
        profile = self.store.raw(native / "profile.bin", b"profile-fixture")
        samples = self.store.raw(native / "samples.jsonl", b"")
        text = "BLEACT: ok apply=100ms stage=20ms vcode=30224\r\n"
        text += "".join("P34INSTALL: phase=" + name + " rc=0 opt=1 hz=288000000 calls=3 reused=2 "
            "fail=0 invalid=0 ticks=7 legacy=0:2880000 reuse=0:57600 max=2880000\r\n" for name in ("patch", "backup"))
        channel = self.store.raw(native / "channel.log", text.encode("ascii"))
        package = dict(bytes=1048576)
        self.store.write(native / "result.json", dict(reader_closed=True, result="TRACE_CLOSED", bindings={},
            package=package, target_bindings={}, expected_run=1, profile=profile,
            channels=[dict(version=30223, raw=channel)], retained_tail=None, samples=samples))
        c = types.SimpleNamespace(read=self.store.read, checked=self.store.checked, record=cli.record,
            bindings={}, full_assets=dict(target_bindings={}), screen=package,
            helper=types.SimpleNamespace(decode_terminal=lambda *args, **kwargs: dict(clean_counters=True, clock_ok=1, clock_hz=288000000)),
            m=None, instrumentation={}, receiver_version=30223, target_version=30224,
            install_restore_expected=True, package_kind="patch")
        value = trace.analyze(c, cell)
        self.assertEqual(value["install_restore"]["result"], "INSTALL_RESTORE_PROFILE_VERIFIED")
        self.assertEqual(set(value["install_restore"]["phases"]), {"patch", "backup"})
        c.package_kind = "full"
        self.assertEqual(trace.analyze(c, cell)["install_restore"]["result"], "EVIDENCE_GAP")


class PatchObservationTests(unittest.TestCase):
    def limits(self):
        source = ROOT / ".cache/p34-next/validation/src/app/bluetooth_flutter_Trace/lib/ota/ota_observation_log.dart"
        return prep.capture_limits(source.read_text(encoding="utf-8"))

    def test_limits_match_the_existing_APK_and_host_capture_boundary(self):
        limits = self.limits()
        self.assertEqual((limits["defaultMaxBytes"], limits["defaultMaxPendingBytes"], limits["defaultMaxStoreBytes"]),
                         (64 * 1024 * 1024, 1024 * 1024, 256 * 1024 * 1024))
        self.assertEqual((limits["directories"], limits["_batchBytes"], limits["maxLineBytes"]), (8, 32768, 16384))

    def test_missing_duplicate_or_nonliteral_limits_fail_closed(self):
        for text in ("", "static const defaultMaxBytes = 64 + 1;", "static const defaultMaxBytes = 64;\n" * 2):
            with self.assertRaises(RuntimeError):
                prep.capture_limits(text)

    def test_projection_is_a_labelled_estimate_not_a_runtime_capacity_guarantee(self):
        result = prep.capture_projection(1042565, 9330, 2278, 1048576, self.limits())
        self.assertEqual((result["data_segments"], result["durable_blocks"]), (8192, 256))
        self.assertTrue(result["estimate_only"] and result["estimated_below_capture_limit"])
        self.assertFalse(result["proves_pending_queue_capacity"] or result["proves_free_phone_storage"])
        for bad in (0, -1, True, 1.5):
            with self.assertRaises(RuntimeError):
                prep.capture_projection(bad, 9330, 2278, 1048576, self.limits())

    def test_warning_comparison_normalizes_roots_but_preserves_multiplicity(self):
        old, new = ROOT / "old", ROOT / "new"
        first = str(old / "x.c") + ":10: warning: fixture\n"
        second = str(new / "x.c") + ":10: warning: fixture\n"
        self.assertEqual(prep.warning_lines(first, old), prep.warning_lines(second, new))
        self.assertNotEqual(prep.warning_lines(first, old), prep.warning_lines(second * 2, new))
        first = first.replace("\\", "/").replace(":/", "_/")
        second = second.replace("\\", "/").replace(":/", "_/")
        self.assertEqual(prep.warning_lines(first, old), prep.warning_lines(second, new))

    def test_missing_blob_reconciliation_requires_exact_committed_bytes(self):
        data = b"source\n"
        blob = hashlib.sha1(b"blob 7\0" + data).hexdigest()
        self.assertEqual(prep.verified_git_blob(data, blob), data)
        self.assertEqual(prep.verified_git_blob(b"source\r\n", blob), data)
        for candidate, expected in ((b"different\n", blob), (data, "0" * 40), (data, "short")):
            with self.assertRaises(RuntimeError):
                prep.verified_git_blob(candidate, expected)


TEST_CLASSES = (PatchAssetsTests, PatchSessionTests, PatchObservationTests)
