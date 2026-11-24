"""N04 host admission, asset, clock-summary, and finite-transition regressions."""
from __future__ import annotations

import copy
import os
from pathlib import Path
import sys
import types
import unittest
from unittest import mock
import uuid

ROOT = Path(__file__).resolve().parents[2]
cli = sys.modules["p34_session"]
backend = cli.load_module("p34_n04_backend_tests", ROOT / "Tools/ota/p34_session_backend.py")
assets = cli.load_module("p34_n04_assets_tests", ROOT / "Tools/ota/p34_install_assets.py")
builder = cli.load_module("p34_n04_builder_tests", ROOT / "Tools/ota/p34_install_candidate.py")
trace = cli.load_module("p34_n04_trace_tests", ROOT / "Tools/ota/p34_full_trace.py")
window_tests = sys.modules["p34_window8_tests"]
OUTPUT = Path(os.environ["P34_TEST_OUT"])


class InstallTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.real_store = cli.Store(ROOT)
        profile = cls.real_store.base / "profile-n04-bootstrap.json"
        cls.api = cli.backend(cls.real_store, profile, "n04-bootstrap")
        cls.context = cls.api.context(OUTPUT / "n04-context")
        cls.previous = cli.completed_full_predecessor(cls.real_store, cls.api.profile["predecessor"],
                                                      group="n03-window8-repeat")
        # This fixture belongs to completed W even after the physical chain advances.
        with mock.patch.object(cls.real_store, "current", return_value=cls.previous["out"].name):
            cls.selection = cli.completed_capture_target(cls.real_store, cls.previous["plan"]["predecessor"]["run"])
        # Prepared Y is usable as a host fixture, not an executed X predecessor.
        cls.measure_api = backend.Backend(cls.real_store, profile, cls.api.profile, "n04-measure")
        cls.measure = cls.measure_api.context(OUTPUT / "n04-measure-context")

    def setUp(self):
        self.store = cli.Store(ROOT)
        self.store.base = self.store.checked(OUTPUT / "n04-fixtures" / uuid.uuid4().hex)

    def test_bootstrap_binds_actual_W_and_new_X(self):
        c = self.context
        self.assertEqual((c.receiver_version, c.target_version), (30219, 30220))
        self.assertEqual(c.bindings, self.previous["plan"]["target_bindings"])
        self.assertEqual(c.receiver_image_sha, c.w_assets["target"]["sha256"])
        self.assertFalse(c.install_restore_expected)
        self.assertNotEqual(c.bindings["profile"]["map"], c.full_assets["target_bindings"]["profile"]["map"])
        self.assertEqual(c.full_assets["target"]["bytes"], c.read(ROOT / assets.BUILD)["app_bytes"])
        self.assertIn(b"P34INSTALL:", Path(c.full_assets["target"]["path"]).read_bytes())

    def test_measurement_binds_X_to_header_only_Y(self):
        c = self.measure
        self.assertEqual((c.receiver_version, c.target_version), (30220, 30221))
        self.assertTrue(c.install_restore_expected)
        self.assertEqual(c.bindings, self.context.full_assets["target_bindings"])
        before, after = (Path(item["path"]).read_bytes() for item in (c.previous_assets["target"], c.target))
        self.assertEqual(before[:0x400] + before[0x460:], after[:0x400] + after[0x460:])
        self.assertNotEqual(before[0x400:0x460], after[0x400:0x460])

    def test_new_MAP_rebinds_all_runtime_addresses_without_changing_layout_or_Boot(self):
        c = self.measure
        self.assertEqual(c.bindings["layout"]["members"], self.context.bindings["layout"]["members"])
        self.assertEqual(c.instrumentation["size"], 336)
        self.assertEqual(c.bindings["whole_boot"], self.context.bindings["whole_boot"])
        text = Path(c.bindings["profile"]["map"]["path"]).read_text(encoding="utf-8")
        self.assertEqual(c.bindings["layout"]["session"],
                         c.m.map_bss(text, "_ZL13s_ble_session", c.bindings["layout"]["members"]["size"]))
        for name, symbol in (("bcb_state", "_ZL20g_ota_state_snapshot"),
                             ("confirm_done", "_ZL18g_ota_confirm_done"), ("state_snapped", "_ZL19g_ota_state_snapped")):
            self.assertEqual(c.bindings["layout"][name], c.m.map_bss(text, symbol, 1))
        installed = self.api.installed_context(self.store.base / "installed")
        self.assertEqual(installed.receiver_version, 30220)
        self.assertEqual(installed.flash_addresses, c.flash_addresses)

    def test_configs_use_new_receivers_and_keep_window8_full_mode(self):
        for api, c in ((self.api, self.context), (self.measure_api, self.measure)):
            with self.subTest(group=api.group):
                phone = api.phone(c, "n04_config_test", producer=True)
                config = phone.config(c, "s04", 921600, 8, "https://fixture.trycloudflare.com")
                self.assertEqual(config["currentVersionCode"], c.receiver_version)
                self.assertEqual(config["targetVersionCode"], c.target_version)
                self.assertEqual(config["currentImageSha256"], c.receiver_image_sha)
                self.assertEqual((config["senderWindowSegments"], config["prefixBytes"], config["transferMode"]), (8, 0, "full"))
                notes = phone.service_config(c, "https://fixture.trycloudflare.com")["releases"][c.release_key]["releaseNotes"]
                self.assertIn("not an N04 speed result" if api.group == "n04-bootstrap" else "Measure N04 installation", notes)
                for cell, baud, window in (("s01", 460800, 4), ("s04", 921600, 4), ("s04", 460800, 8)):
                    with self.assertRaises(RuntimeError):
                        phone.config(c, cell, baud, window, "https://fixture.trycloudflare.com")

    def test_only_known_prior_packages_admit_a_fresh_zero_start(self):
        for api, c, prior in ((self.api, self.context, self.context.w_assets),
                              (self.measure_api, self.measure, self.measure.previous_assets)):
            with self.subTest(group=api.group):
                known = api.known_staging_packages(c)
                self.assertIn(prior["package"], known)
                self.assertNotIn(c.screen, known)
                self.assertNotEqual(prior["package"], c.screen)

    def test_assets_reuse_never_rebuilds_or_changes_nonce(self):
        for group, c in (("n04-bootstrap", self.context), ("n04-measure", self.measure)):
            before = cli.record(c.screen["path"])
            with mock.patch.object(assets.subprocess, "run", side_effect=AssertionError("asset replay")):
                self.assertTrue(assets.prepare(c, cli.N04_GROUPS[group])["reused"])
            self.assertEqual(cli.record(c.screen["path"]), before)

    def test_new_assets_fail_closed_on_binding_or_native_proof_tampering(self):
        c, spec = self.context, cli.N04_GROUPS["n04-bootstrap"]
        original = c.read
        for keys in (("specification", "target_version"), ("target_bindings", "profile", "symbols", "rtt"),
                     ("target_bindings", "layout", "session"), ("decoded", "image_bytes"), ("generator", "bytes")):
            value = copy.deepcopy(c.full_assets)
            at = value
            for key in keys[:-1]:
                at = at[key]
            at[keys[-1]] += 1
            def read(path):
                return value if Path(path) == ROOT / spec["assets"] else original(path)
            with self.subTest(keys=keys), mock.patch.object(c, "read", side_effect=read), self.assertRaises(RuntimeError):
                assets.load(c, spec)

    def test_bootstrap_refuses_a_wrong_live_receiver_binding(self):
        with mock.patch.object(self.context, "receiver_version", 30218), self.assertRaises(RuntimeError):
            assets.load(self.context, cli.N04_GROUPS["n04-bootstrap"])

    def test_source_pins_include_new_asset_and_observation_checks(self):
        for c in (self.context, self.measure):
            paths = {Path(item["path"]) for item in c.sources()}
            for name in ("Tools/ota/p34_install_assets.py", "Tools/ota/p34_full_trace.py", "tests/ota/test_p34_install.py"):
                self.assertIn(ROOT / name, paths)
            self.assertTrue({ROOT / cli.N04_GROUPS[name]["assets"] for name in cli.n04_asset_groups(c.group)} <= paths)

    def test_W_predecessor_is_original_full_receive_not_old_V(self):
        self.assertEqual(self.previous["descriptor"]["run"], "20260927T141330-27800")
        self.assertEqual(self.previous["report"]["full_metrics"]["transfer_seconds"], 58.164197)
        self.assertEqual(self.api.predecessor(self.context)["descriptor"], self.previous["descriptor"])
        with self.assertRaises(RuntimeError):
            cli.completed_full_predecessor(self.real_store, self.previous["plan"]["predecessor"], group="n03-window8-repeat")

    def test_cleanup_targets_V_from_original_W_chain_and_never_current_W(self):
        selected, protected = self.selection["selected"], self.selection["protected"]
        self.assertEqual(protected["descriptor"], self.previous["descriptor"])
        self.assertEqual(selected["descriptor"], self.previous["plan"]["predecessor"])
        query = self.real_store.read(selected["report"]["inputs"]["query"]["path"])
        self.assertEqual(self.selection["remote"], query["remote"])
        self.assertEqual(self.selection["capture"], selected["report"]["summary"]["captureId"])
        for run in (protected["out"].name, selected["plan"]["predecessor"]["run"], "another"):
            with self.subTest(run=run), mock.patch.object(self.real_store, "current", return_value=protected["out"].name), \
                    self.assertRaises(RuntimeError):
                cli.completed_capture_target(self.real_store, run)

    def test_quiesce_is_bound_to_completed_W_and_still_rejects_active_or_racing_App(self):
        for case in ("live", "absent", "wrong-pid", "wrong-config", "active", "pid-race", "config-race"):
            api, c, commands, events = window_tests.Window8Tests.quiesce_fixture(self, case)
            value = api.quiesce(c, self.store.base / case, self.previous)
            with self.subTest(case=case):
                self.assertEqual(value["result"], "APP_QUIESCED" if case in ("live", "absent") else "APP_QUIESCE_FAILED")
                self.assertEqual(sum(args[1:3] == ["am", "force-stop"] for args in commands), int(case == "live"))
                self.assertEqual(events, ["opened", "closed"])

    def test_finite_W_X_Y_transition_has_no_replay_or_skip(self):
        for old_group, next_group in (("n03-window8-repeat", "n04-bootstrap"), ("n04-bootstrap", "n04-measure"),
                                     ("n04-measure", "n04-window16")):
            store = cli.Store(ROOT)
            store.base = store.checked(self.store.base / old_group)
            old = store.run("previous")
            profile = store.base / "profile.json"
            store.write(profile, dict(predecessor={}))
            store.write(store.base / "current.json", dict(run=old.name))
            store.write(old / "plan.json", dict(group=old_group))
            store.write(old / "runtime/s04/closed.json", dict(worker_exit=0))
            store.write(old / "runtime/network/closed.json", dict(worker_exit=0))
            calls = []
            def launch(path, *args):
                calls.append(path.name)
                if path.name == "network":
                    store.write(path.parent.parent / "live-network.json", {})
            c = types.SimpleNamespace(supervisor=types.SimpleNamespace(owned=types.SimpleNamespace(launch=launch)))
            api = types.SimpleNamespace(context=lambda out: c, preflight=lambda *args: None,
                inspect=lambda *args: dict(result="APP_INSPECTED"), network_ready=lambda *args: None,
                prepare=lambda c, out, phone, tests: store.write(out / "plan.json", dict(group=next_group)))
            state = dict(result="fixture", network=dict(state="CLOSED"))
            with mock.patch.object(cli, "verify_tests", return_value={}), mock.patch.object(cli, "status", return_value=state), \
                    mock.patch.object(cli, "completed_full_predecessor", return_value=dict(out=old, descriptor={})) as previous, \
                    mock.patch.object(cli, "backend", return_value=api) as factory:
                for wrong in (old_group, "screen", "n03-window8"):
                    self.assertEqual(cli.start(store, profile, "s04", wrong), state)
                factory.assert_not_called()
                cli.start(store, profile, "s04", next_group)
                previous.assert_called_once_with(store, {}, group=old_group)
                factory.assert_called_once()
                factory.reset_mock()
                self.assertEqual(cli.start(store, profile, "s04", next_group), state)
                factory.assert_not_called()
            self.assertEqual(calls, ["network", "s04"])

    def test_new_group_refuses_wrong_predecessor_before_backend(self):
        old = self.store.run("wrong-owner")
        profile = self.store.base / "profile.json"
        self.store.write(profile, dict(predecessor={}))
        self.store.write(self.store.base / "current.json", dict(run=old.name))
        self.store.write(old / "plan.json", dict(group="n03-window8-repeat"))
        with mock.patch.object(cli, "verify_tests", return_value={}), \
                mock.patch.object(cli, "completed_full_predecessor", return_value=dict(out=self.store.run("real-W"))), \
                mock.patch.object(cli, "backend", side_effect=AssertionError("unadmitted device operation")):
            with self.assertRaisesRegex(RuntimeError, "actual completed owner"):
                cli.start(self.store, profile, "s04", "n04-bootstrap")

    def summaries(self):
        return ["P34INSTALL: phase=" + name + " rc=0 opt=1 hz=288000000 calls=3 reused=2 "
                "fail=0 invalid=0 ticks=7 legacy=0:2880000 reuse=0:57600 max=2880000\r\n"
                for name in ("full", "backup")]

    def test_restore_timing_keeps_cycle_totals_separate_from_wall_time(self):
        value = trace.install_restore_timing(self.summaries(), 288000000)
        self.assertFalse(value["whole_installation_wall_time"] or value["strict_same_package_AB"])
        for phase in value["phases"].values():
            self.assertEqual((phase["calls"], phase["legacy_calls"], phase["reused_status_writes"]), (3, 1, 2))
            self.assertEqual(phase["legacy_seconds"], .01)
            self.assertEqual(phase["reuse_seconds"], .0002)

    def test_identical_duplicate_summaries_are_not_counted_twice(self):
        lines = self.summaries()
        self.assertEqual(trace.install_restore_timing(lines, 288000000),
                         trace.install_restore_timing(lines + lines, 288000000))

    def test_missing_malformed_or_conflicting_summaries_fail(self):
        lines = self.summaries()
        for bad in ([], lines[:1], [lines[0][:-2], lines[1]], [lines[0].replace("phase=full", "phase=patch"), lines[1]],
                    lines + [lines[0].replace("ticks=7", "ticks=8")]):
            with self.subTest(bad=bad), self.assertRaises(RuntimeError):
                trace.install_restore_timing(bad, 288000000)

    def test_invalid_clock_error_and_disabled_optimization_fail(self):
        for old, new in (("rc=0", "rc=-1"), ("opt=1", "opt=0"), ("hz=288000000", "hz=144000000"),
                         ("fail=0", "fail=1"), ("invalid=0", "invalid=1")):
            with self.subTest(new=new), self.assertRaises(RuntimeError):
                trace.install_restore_timing([line.replace(old, new) for line in self.summaries()], 288000000)

    def test_impossible_counts_cycles_and_uint32_overflow_fail(self):
        for old, new in (("calls=3", "calls=0"), ("reused=2", "reused=3"), ("max=2880000", "max=0"),
                         ("reuse=0:57600", "reuse=0:0"), ("legacy=0:2880000", "legacy=0:0"),
                         ("max=2880000", "max=1"), ("ticks=7", "ticks=4294967296")):
            with self.subTest(new=new), self.assertRaises(RuntimeError):
                trace.install_restore_timing([line.replace(old, new) for line in self.summaries()], 288000000)

    def test_64bit_cycle_carry_is_not_truncated(self):
        lines = [line.replace("calls=3", "calls=4").replace("reused=2", "reused=3")
                 .replace("reuse=0:57600", "reuse=1:5").replace("max=2880000", "max=2147483648")
                 for line in self.summaries()]
        value = trace.install_restore_timing(lines, 288000000)
        self.assertEqual(value["phases"]["full"]["reuse_cycles"], 4294967301)

    def test_all_fallbacks_are_measured_without_fabricating_a_reuse_benefit(self):
        lines = [line.replace("reused=2", "reused=0").replace("reuse=0:57600", "reuse=0:0")
                 for line in self.summaries()]
        value = trace.install_restore_timing(lines, 288000000)
        self.assertEqual(value["phases"]["full"]["reused_status_writes"], 0)

    def test_symbol_parser_handles_original_windows_and_unix_lines_identically(self):
        path = ROOT / ".cache/p34-session/n04/firmware/logs/symbols.stdout"
        raw = path.read_bytes().decode("utf-8")
        self.assertIn("\r\n", raw)
        parsed = builder.selected_symbols(raw)
        self.assertEqual(parsed, builder.selected_symbols(raw.replace("\r\n", "\n")))
        self.assertEqual(parsed["g_p34_ble_profile"]["bytes"], 336)
        self.assertEqual(parsed["qspi_xip_restore_checked"]["kind"], "T")

    def test_symbol_parser_rejects_duplicate_bound_symbols(self):
        line = "20000000 00000150 B g_p34_ble_profile\r\n"
        with self.assertRaisesRegex(RuntimeError, "duplicate"):
            builder.selected_symbols(line + line)


class Window16Tests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.real_store = cli.Store(ROOT)
        cls.api = cli.backend(cls.real_store, cls.real_store.base / "profile-n04-window16.json", "n04-window16")
        cls.context = cls.api.context(OUTPUT / "window16-context")
        cls.previous = cli.completed_full_predecessor(cls.real_store, cls.api.profile["predecessor"], group="n04-measure")
        with mock.patch.object(cls.real_store, "current", return_value=cls.previous["out"].name):
            cls.selection = cli.completed_capture_target(cls.real_store, cls.previous["plan"]["predecessor"]["run"])

    def setUp(self):
        self.store = cli.Store(ROOT)
        self.store.base = self.store.checked(OUTPUT / "window16-fixtures" / uuid.uuid4().hex)

    def test_Y_to_Z_preserves_executable_MAP_layout_and_Boot(self):
        c = self.context
        self.assertEqual((c.receiver_version, c.target_version), (30221, 30222))
        self.assertEqual(c.bindings, self.previous["plan"]["target_bindings"])
        self.assertTrue(c.install_restore_expected)
        self.assertEqual(c.instrumentation["size"], 336)
        before, after = (Path(item["path"]).read_bytes() for item in (c.previous_assets["target"], c.target))
        self.assertEqual(before[:0x400] + before[0x460:], after[:0x400] + after[0x460:])
        self.assertNotEqual(before[0x400:0x460], after[0x400:0x460])
        self.assertFalse(c.full_assets["bootstrap"])
        for key in ("map", "elf", "symbols"):
            self.assertEqual(c.bindings["profile"][key], c.full_assets["target_bindings"]["profile"][key])
        for key in ("layout", "whole_boot"):
            self.assertEqual(c.bindings[key], c.full_assets["target_bindings"][key])

    def test_only_s04_window16_is_admitted_and_old_axes_stay_unchanged(self):
        c = self.context
        self.assertNotIn("n04-window16", cli.WINDOW8_GROUPS)
        self.assertEqual(cli.cells_for("n04-window16")["s04"], (921600, 16))
        self.assertEqual(cli.cells_for("n04-measure")["s04"], (921600, 8))
        phone = self.api.phone(c, "window16_config_test", producer=True)
        config = phone.config(c, "s04", 921600, 16, "https://fixture.trycloudflare.com")
        self.assertEqual((config["currentVersionCode"], config["targetVersionCode"]), (30221, 30222))
        self.assertEqual((config["senderWindowSegments"], config["transferMode"], config["prefixBytes"]), (16, "full", 0))
        self.assertEqual(config["packageSha256"], c.full_assets["package"]["sha256"])
        self.assertTrue(config["reuseGatt"] and config["withoutResponse"])
        for cell, baud, window in (("s03", 460800, 16), ("s04", 460800, 16), ("s04", 921600, 8), ("s04", 921600, 32)):
            with self.subTest(cell=cell, baud=baud, window=window), self.assertRaises(RuntimeError):
                phone.config(c, cell, baud, window, "https://fixture.trycloudflare.com")
        notes = phone.service_config(c, "https://fixture.trycloudflare.com")["releases"][c.release_key]["releaseNotes"]
        self.assertIn("Screen window 16 on Y", notes)

    def test_old_groups_do_not_depend_on_the_future_Z_asset(self):
        for group in ("n04-bootstrap", "n04-measure"):
            self.assertEqual(cli.n04_asset_groups(group), ("n04-bootstrap", "n04-measure"))
        self.assertEqual(cli.n04_asset_groups("n04-window16"), ("n04-bootstrap", "n04-measure", "n04-window16"))
        with self.assertRaises(RuntimeError):
            cli.n04_asset_groups("unknown")
        paths = {Path(item["path"]) for item in self.context.sources()}
        self.assertTrue({ROOT / cli.N04_GROUPS[name]["assets"] for name in cli.n04_asset_groups("n04-window16")} <= paths)

    def test_fresh_BEGIN_knows_actual_Y_and_never_its_target_Z(self):
        c = self.context
        known = self.api.known_staging_packages(c)
        self.assertIn(c.previous_assets["package"], known)
        self.assertNotIn(c.screen, known)
        self.assertEqual(len(known), len({item["sha256"] for item in known}))
        self.assertEqual([item["target_identity"]["version_code"] for item in c.n04_prior_assets], [30220, 30221])

    def test_Z_asset_and_profile_reuse_cannot_invoke_packer_or_device(self):
        before = cli.record(self.context.screen["path"])
        with mock.patch.object(assets.subprocess, "run", side_effect=AssertionError("package or device replay")), \
                mock.patch.object(self.real_store, "current", return_value=self.previous["out"].name):
            self.assertTrue(assets.prepare(self.context, cli.N04_GROUPS["n04-window16"])["reused"])
            result = cli.prepare_window16(self.real_store)
        self.assertEqual(result["profile"], cli.record(self.api.profile_path))
        self.assertEqual(result["device_operations"], 0)
        self.assertEqual(before, cli.record(self.context.screen["path"]))

    def test_cleanup_selects_original_X_only_and_keeps_Y_protected(self):
        value = self.selection
        self.assertEqual(value["protected"]["descriptor"], self.previous["descriptor"])
        self.assertEqual(value["selected"]["plan"]["group"], "n04-bootstrap")
        self.assertEqual(value["remote"], "files/p34-observations/" + value["selected"]["report"]["summary"]["captureId"])
        for run in (self.previous["out"].name, "not-the-original-X"):
            with mock.patch.object(self.real_store, "current", return_value=self.previous["out"].name), self.assertRaises(RuntimeError):
                cli.completed_capture_target(self.real_store, run)

    def test_completed_Y_quiesce_still_requires_exact_idle_App(self):
        for case in ("live", "absent", "wrong-pid", "wrong-config", "active", "pid-race", "config-race"):
            api, c, commands, events = window_tests.Window8Tests.quiesce_fixture(self, case)
            value = api.quiesce(c, self.store.base / case, self.previous)
            with self.subTest(case=case):
                self.assertEqual(value["result"], "APP_QUIESCED" if case in ("live", "absent") else "APP_QUIESCE_FAILED")
                self.assertEqual(sum(args[1:3] == ["am", "force-stop"] for args in commands), int(case == "live"))
                self.assertEqual(events, ["opened", "closed"])

    def test_wrong_cleanup_name_is_rejected_before_reopening_the_whole_history(self):
        with mock.patch.object(self.real_store, "current", return_value=self.previous["out"].name), \
                mock.patch.object(cli, "completed_full_predecessor", side_effect=AssertionError("unnecessary history replay")), \
                self.assertRaisesRegex(RuntimeError, "immediate predecessor"):
            cli.completed_capture_target(self.real_store, "not-the-original-X")

    def test_preparation_refuses_a_missing_or_wrong_predecessor(self):
        with mock.patch.object(cli, "backend", side_effect=AssertionError("unadmitted preparation")):
            with self.assertRaises(RuntimeError):
                cli.prepare_window16(self.store)
            out = self.store.run("old-X")
            self.store.write(self.store.base / "current.json", dict(run=out.name))
            self.store.write(out / "plan.json", dict(group="n04-bootstrap"))
            with self.assertRaisesRegex(RuntimeError, "completed Y"):
                cli.prepare_window16(self.store)

    def test_preparation_refuses_unreconciled_Y_timing(self):
        out = self.store.run("Y-without-timing")
        self.store.write(self.store.base / "current.json", dict(run=out.name))
        self.store.write(out / "plan.json", dict(group="n04-measure"))
        self.store.write(out / "analysis/latest.json", dict(result="FULL_INSTALL_VERIFIED", cell="s04", report={}))
        with mock.patch.object(cli, "completed_full_predecessor", return_value=dict(report=dict(n04_install_measurement=False))), \
                mock.patch.object(cli, "backend", side_effect=AssertionError("missing timing")), self.assertRaisesRegex(RuntimeError, "timing"):
            cli.prepare_window16(self.store)

    def test_attempted_Z_has_no_automatic_next_group_or_replay(self):
        out = self.store.run("attempted-Z")
        self.store.write(self.store.base / "current.json", dict(run=out.name))
        self.store.write(out / "plan.json", dict(group="n04-window16"))
        state = dict(result="preserve-original-result")
        with mock.patch.object(cli, "verify_tests", return_value={}), mock.patch.object(cli, "status", return_value=state), \
                mock.patch.object(cli, "backend", side_effect=AssertionError("replayed Z")):
            for group in cli.GROUPS:
                with self.subTest(group=group):
                    self.assertEqual(cli.start(self.store, self.store.base / "unused.json", "s04", group), state)
