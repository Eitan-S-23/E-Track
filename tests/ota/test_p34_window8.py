"""U-to-V window-8 lifecycle tests; all device boundaries are modeled."""
from __future__ import annotations

import copy
from contextlib import contextmanager, nullcontext
import json
import os
from pathlib import Path
import sys
import types
import unittest
from unittest import mock
import uuid

ROOT = Path(__file__).resolve().parents[2]
cli = sys.modules["p34_session"]
backend = cli.load_module("p34_window8_backend_tests", ROOT / "Tools/ota/p34_session_backend.py")
assets = cli.load_module("p34_window8_assets_tests", ROOT / "Tools/ota/p34_window8_assets.py")
OUTPUT = Path(os.environ["P34_TEST_OUT"])


class Window8Tests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        # Share immutable real inputs, not repeated APK hashing or device admission.
        cls.real_store = cli.Store(ROOT)
        cls.api = cli.backend(cls.real_store, cls.real_store.base / "profile-n03-window8.json", "n03-window8")
        cls.context = cls.api.context(OUTPUT / "window8-context")
        cls.previous = cli.completed_full_predecessor(cls.real_store, cls.api.profile["predecessor"])

    def setUp(self):
        self.store = cli.Store(ROOT)
        self.store.base = self.store.checked(OUTPUT / "window8-fixtures" / uuid.uuid4().hex)

    def test_old_matrix_is_unchanged_and_window8_has_separate_axes(self):
        expected = {"s01": (460800, 4), "s02": (460800, 8), "s03": (460800, 16), "s04": (921600, 4)}
        for group in cli.GROUPS:
            wanted = (dict(expected, s04=(921600, 28)) if group in cli.NEW_BOOT_GROUPS else
                      dict(expected, s04=(921600, 32)) if group == cli.SPEED32_GROUP or group in (*cli.PATCH32_GROUPS, *cli.RECEIVE_GROUPS, *cli.ACK_GAP_GROUPS) else
                      dict(expected, s04=(921600, 16)) if group in ("n04-window16", cli.SPEED16_GROUP) else
                      dict(expected, s04=(921600, 8)) if group in cli.WINDOW8_GROUPS else expected)
            self.assertEqual(cli.cells_for(group), wanted)
        changed = cli.cells_for("n03-window8")
        changed["s01"] = (115200, 1)
        self.assertEqual(cli.CELLS, expected)
        self.assertEqual(cli.cells_for("n03-window8")["s01"], expected["s01"])

    def test_real_context_binds_U_to_V_and_full_window8_configuration(self):
        c = self.context
        self.assertEqual((c.receiver_version, c.target_version), (30217, 30218))
        self.assertEqual(c.bindings, c.u_assets["target_bindings"])
        self.assertEqual(c.receiver_image_sha, c.u_assets["target"]["sha256"])
        self.assertEqual(c.screen["bytes"], 291005)
        self.assertEqual(c.instrumentation["size"], 336)
        phone = self.api.phone(c, "window8_config_test", producer=True)
        config = phone.config(c, "s04", 921600, 8, "https://fixture.trycloudflare.com")
        self.assertEqual((config["transferMode"], config["prefixBytes"]), ("full", 0))
        self.assertEqual((config["currentVersionCode"], config["targetVersionCode"]), (30217, 30218))
        self.assertEqual((config["requestedBaud"], config["senderWindowSegments"]), (921600, 8))
        self.assertTrue(config["reuseGatt"] and config["withoutResponse"])
        self.assertEqual(config["currentImageSha256"], c.u_assets["target"]["sha256"])
        self.assertEqual(config["packageSha256"], c.full_assets["package"]["sha256"])
        for cell, baud, window in (("s04", 921600, 4), ("s01", 460800, 4), ("s04", 460800, 8)):
            with self.subTest(cell=cell, baud=baud, window=window), self.assertRaisesRegex(RuntimeError, "unplanned"):
                phone.config(c, cell, baud, window, "https://fixture.trycloudflare.com")
        served = phone.service_config(c, "https://fixture.trycloudflare.com")
        release = served["releases"][c.release_key]
        self.assertIn(assets.SERVED_NAME, json.dumps(release))
        self.assertIn("retain the N03 executable", release["releaseNotes"])
        paths = {Path(item["path"]) for item in c.sources()}
        for name in ("Tools/ota/p34_window8_assets.py", "tests/ota/test_p34_window8.py", assets.RELATIVE):
            self.assertIn(ROOT / name, paths)

    def test_final_context_keeps_MAP_Boot_and_layout_but_requires_full_V(self):
        c = self.context
        installed = self.api.installed_context(self.store.base / "after")
        self.assertEqual(installed.receiver_version, 30218)
        self.assertEqual(installed.receiver_image_sha, c.target["sha256"])
        self.assertEqual(installed.bindings, c.full_assets["target_bindings"])
        self.assertEqual(installed.bindings["whole_boot"], c.bindings["whole_boot"])
        self.assertEqual(installed.bindings["layout"], c.bindings["layout"])
        self.assertEqual(installed.bindings["profile"]["map"], c.bindings["profile"]["map"])
        self.assertEqual(installed.flash_addresses, c.flash_addresses)

    def test_frozen_V_is_header_only_and_reuse_never_runs_packers(self):
        c = self.context
        before = Path(c.u_assets["target"]["path"]).read_bytes()
        after = Path(c.target["path"]).read_bytes()
        self.assertEqual(len(before), len(after))
        self.assertEqual(before[:0x400] + before[0x460:], after[:0x400] + after[0x460:])
        self.assertNotEqual(before[0x400:0x460], after[0x400:0x460])
        manifest, package = cli.record(ROOT / assets.RELATIVE), cli.record(c.screen["path"])
        with mock.patch.object(assets.subprocess, "run", side_effect=AssertionError("package regeneration")):
            result = assets.prepare(c)
        self.assertTrue(result["reused"])
        self.assertEqual(result["device_operations"], 0)
        self.assertEqual(result["manifest"], manifest)
        self.assertEqual(cli.record(c.screen["path"]), package)

    def test_asset_tampering_and_old_receivers_fail_closed(self):
        c, original = self.context, self.context.read
        cases = (("receiver_bindings", "profile", "symbols", "rtt"),
                 ("target_bindings", "profile", "symbols", "rtt"),
                 ("target_identity", "version_code"), ("decoded", "image_bytes"))
        for keys in cases:
            changed = copy.deepcopy(c.full_assets)
            parent = changed
            for key in keys[:-1]:
                parent = parent[key]
            parent[keys[-1]] += 1
            def read(path):
                return changed if Path(path) == ROOT / assets.RELATIVE else original(path)
            with self.subTest(keys=keys), mock.patch.object(c, "read", side_effect=read), self.assertRaises(RuntimeError):
                assets.load(c)
        for version in (30214, 30215, 30216, 30218):
            with self.subTest(version=version), mock.patch.object(c, "receiver_version", version), self.assertRaises(RuntimeError):
                assets.receiver(c)

    def test_changed_asset_bytes_or_missing_negative_gates_are_rejected(self):
        c = self.context
        original_read, original_record = c.read, c.record
        changed = copy.deepcopy(c.full_assets)
        changed["negatives"] = changed["negatives"][:-1]
        with mock.patch.object(c, "read", side_effect=lambda path: changed if Path(path) == ROOT / assets.RELATIVE else original_read(path)):
            with self.assertRaisesRegex(RuntimeError, "negative package gates"):
                assets.load(c)
        def record(path):
            item = original_record(path)
            return dict(item, sha256="0" * 64) if Path(path) == Path(c.target["path"]) else item
        with mock.patch.object(c, "record", side_effect=record), self.assertRaisesRegex(RuntimeError, "input/output changed"):
            assets.load(c)

    def test_real_predecessor_is_complete_U_not_B_or_R(self):
        previous = self.previous
        self.assertEqual(previous["out"].name, "20260927T114731-53800")
        self.assertEqual(previous["plan"]["target_bindings"], self.context.bindings)
        self.assertEqual(previous["report"]["full_metrics"]["transfer_seconds"], 96.513806)
        self.assertEqual(cli.current_full_descriptor(self.real_store, previous["out"].name), previous["descriptor"])
        with self.assertRaises(RuntimeError):
            cli.completed_full_predecessor(self.real_store, previous["plan"]["predecessor"])

    def test_complete_U_gate_rejects_resume_retries_wrong_target_or_incomplete_DATA(self):
        previous = self.previous
        cases = (("n03_receive_measurement", False), ("initial_state_evidence", dict(source="RESUMED")))
        reports = [dict(previous["report"], **{key: value}) for key, value in cases]
        for key in ("segmentsUnique", "segmentSendTotal", "retransmitFrames"):
            changed = copy.deepcopy(previous["report"])
            changed["full_metrics"]["transfer"][key] += 1
            reports.append(changed)
        changed = copy.deepcopy(previous["report"])
        changed["full_metrics"]["transfer"]["durable"]["finalOff"] -= 128
        reports.append(changed)
        changed = copy.deepcopy(previous["report"])
        changed["summary"]["input"]["targetVersionCode"] = 30216
        reports.append(changed)
        for report in reports:
            with self.subTest(report=reports.index(report)), mock.patch.object(cli, "full_predecessor", return_value={}), \
                    mock.patch.object(cli, "installed_predecessor", return_value=dict(previous, report=report)), \
                    self.assertRaisesRegex(RuntimeError, "complete U receive"):
                cli.completed_full_predecessor(self.real_store, previous["descriptor"])

    def test_unclosed_U_owners_cannot_become_a_predecessor(self):
        actual = cli.owner_state
        blocked = self.previous["out"] / "runtime/network"
        with mock.patch.object(cli, "owner_state", side_effect=lambda store, path: dict(state="UNCERTAIN") if path == blocked else actual(store, path)):
            with self.assertRaisesRegex(RuntimeError, "owners must be closed"):
                cli.completed_full_predecessor(self.real_store, self.previous["descriptor"])

    def quiesce_fixture(self, case):
        report = self.previous["report"]
        config = Path(report["inputs"]["config"]["path"]).read_bytes()
        pid = report["summary"]["pid"]
        observed = dict(stable_completed=True, stable_terminal=False, safe_idle=False,
            snapshots=["snapshot-1.jsonl"], snapshot_records={"snapshot-1.jsonl": report["inputs"]["snapshot"]},
            config=report["inputs"]["config"], health=dict(captureId=report["summary"]["captureId"]),
            pid=pid, pid_checked_before_after=True)
        if case == "absent":
            observed["pid"] = None
        elif case == "wrong-pid":
            observed["pid"] += 1
        elif case == "wrong-config":
            observed["config"] = dict(observed["config"], sha256="0" * 64)
        elif case == "wrong-snapshot":
            observed["snapshot_records"] = {"snapshot-1.jsonl": dict(report["inputs"]["snapshot"], sha256="0" * 64)}
        elif case == "wrong-capture":
            observed["health"]["captureId"] = "other"
        elif case == "active":
            observed["stable_completed"] = False
        elif case == "unverified-absence":
            observed.update(pid=None, pid_checked_before_after=False)
        live = [str(observed["pid"]) if observed["pid"] else ""]
        if case == "pid-race":
            live[0] = str(pid + 1)
        commands, events = [], []
        def command(args, check=True):
            commands.append(args)
            if args == ["shell", "pidof", self.context.PKG]:
                return live[0]
            if args == ["shell", "am", "force-stop", self.context.PKG]:
                live[0] = ""
                return ""
            raise AssertionError("unexpected device command: " + str(args))
        def file_bytes(pkg, path, limit):
            self.assertEqual((pkg, path), (self.context.PKG, "files/p34-experiment.json"))
            return config + b" " if case == "config-race" else config
        @contextmanager
        def usb(*args):
            events.append("opened")
            try:
                yield types.SimpleNamespace(command=command, file_bytes=file_bytes)
            finally:
                events.append("closed")
        api = object.__new__(backend.Backend)
        api.root, api.store = ROOT, self.store
        api.capture = lambda *args: observed
        api.phone = lambda *args: types.SimpleNamespace(usb=usb)
        c = types.SimpleNamespace(PKG=self.context.PKG, checked=self.store.checked, save=self.store.write, now=cli.now)
        c.load = lambda name, path: types.SimpleNamespace(device_lock=nullcontext)
        return api, c, commands, events

    def test_quiesce_stops_only_exact_completed_U_and_preserves_configuration(self):
        for case in ("live", "absent"):
            api, c, commands, events = self.quiesce_fixture(case)
            path = self.store.base / case
            value = api.quiesce(c, path, self.previous)
            with self.subTest(case=case):
                self.assertEqual(value["result"], "APP_QUIESCED", value)
                self.assertTrue(value["process_absent"] and value["configuration_preserved"] and value["usb_closed"])
                self.assertEqual(sum(args[1:3] == ["am", "force-stop"] for args in commands), int(case == "live"))
                self.assertEqual(events, ["opened", "closed"])
                intent = self.store.read(path / "intent.json")
                self.assertFalse(intent["archive_config"] or intent["delete_captures"])
                self.assertTrue(all(args[1] in ("pidof", "am") for args in commands))

    def test_quiesce_rejects_identity_active_and_race_cases_before_mutation(self):
        for case in ("wrong-pid", "wrong-config", "wrong-snapshot", "wrong-capture", "active",
                     "unverified-absence", "pid-race", "config-race"):
            api, c, commands, events = self.quiesce_fixture(case)
            path = self.store.base / case
            value = api.quiesce(c, path, self.previous)
            with self.subTest(case=case):
                self.assertEqual(value["result"], "APP_QUIESCE_FAILED")
                self.assertFalse(any(args[1:3] == ["am", "force-stop"] for args in commands))
                self.assertFalse((path / "intent.json").exists())
                self.assertEqual(events, ["opened", "closed"])

    def test_quiesce_requires_current_full_owner_and_current_tests(self):
        self.store.write(self.store.base / "current.json", dict(run="current-u"))
        with mock.patch.object(cli, "backend", side_effect=AssertionError("device backend")):
            for run, cell in (("other", "s04"), ("current-u", "s01")):
                with self.assertRaisesRegex(RuntimeError, "current completed full owner"):
                    cli.quiesce(self.store, run, cell)
            with self.assertRaisesRegex(RuntimeError, "run p34 test"):
                cli.quiesce(self.store, "current-u", "s04")

    def test_U_advances_once_to_window8_and_attempted_V_is_never_replayed(self):
        old = self.store.run("completed-u")
        profile = self.store.base / "profile.json"
        previous = dict(out=old, descriptor={})
        self.store.write(profile, dict(predecessor={}))
        self.store.write(self.store.base / "current.json", dict(run=old.name))
        self.store.write(old / "plan.json", dict(group="n03-full"))
        self.store.write(old / "runtime/s04/closed.json", dict(worker_exit=0))
        self.store.write(old / "runtime/network/closed.json", dict(worker_exit=0))
        self.store.write(old / "cells/s04/health-live.json", dict(health=dict(upgradeStarts=1, upgradeEnds=1)))
        self.store.write(old / "cells/s04/result.json", dict(result="FULL_INSTALL_VERIFIED"))
        original = cli.record(old / "cells/s04/result.json")
        launched = []
        def launch(path, *args):
            launched.append(path.name)
            if path.name == "network":
                self.store.write(path.parent.parent / "live-network.json", {})
        context = types.SimpleNamespace(supervisor=types.SimpleNamespace(owned=types.SimpleNamespace(launch=launch)))
        api = types.SimpleNamespace(context=lambda out: context, preflight=lambda *args: None,
            inspect=lambda *args: dict(result="APP_INSPECTED"), network_ready=lambda *args: None,
            prepare=lambda c, out, phone, tests: self.store.write(out / "plan.json", dict(group="n03-window8")))
        state = dict(result="fixture", network=dict(state="CLOSED"))
        with mock.patch.object(cli, "verify_tests", return_value={}), mock.patch.object(cli, "status", return_value=state), \
                mock.patch.object(cli, "completed_full_predecessor", return_value=previous), \
                mock.patch.object(cli, "backend", return_value=api) as factory:
            cli.start(self.store, profile, "s04", "n03-window8")
            factory.assert_called_once()
            factory.reset_mock()
            for group in ("n03-window8", "n03-full", "n03-install", "n03-a"):
                self.assertEqual(cli.start(self.store, profile, "s04", group), state)
            factory.assert_not_called()
        self.assertEqual(launched, ["network", "s04"])
        self.assertNotEqual(self.store.current(), old.name)
        self.assertEqual(cli.record(original["path"]), original)

    def test_window8_cannot_use_prefix_axes_or_a_different_U_owner(self):
        profile = self.store.base / "profile.json"
        self.store.write(profile, dict(predecessor={}))
        self.store.write(self.store.base / "current.json", dict(run="different-u"))
        self.store.write(self.store.run("different-u") / "plan.json", dict(group="n03-full"))
        with mock.patch.object(cli, "verify_tests", return_value={}), \
                mock.patch.object(cli, "completed_full_predecessor", return_value=dict(out=self.store.run("bound-u"))), \
                mock.patch.object(cli, "backend", side_effect=AssertionError("new service")):
            with self.assertRaisesRegex(RuntimeError, "only s04"):
                cli.start(self.store, profile, "s01", "n03-window8")
            with self.assertRaisesRegex(RuntimeError, "actual completed U owner"):
                cli.start(self.store, profile, "s04", "n03-window8")

    def test_window8_worker_observes_before_launch_and_closes_trace_before_V_readback(self):
        events, axes = [], []
        class Trace:
            def __init__(self, *args):
                pass
            def start(self):
                events.append("trace ready")
            def stop(self):
                events.append("trace closed")
                return {}
        api = object.__new__(backend.Backend)
        api.root, api.group = ROOT, "n03-window8"
        phone = types.SimpleNamespace(usb=lambda *args: nullcontext("usb"), network=lambda *args: nullcontext("origin"),
            release_old=lambda *args: events.append("archive U configuration"),
            config=lambda c, cell, baud, window, origin: axes.append((baud, window)) or {},
            provision=lambda *args: events.append("launch V observation") or 123)
        api.phone = lambda *args: phone
        api.install_checkpoint = lambda c, out, before=False: events.append("U readback closed" if before else "V verified") or dict(path="fixture")
        api.verify_install_checkpoint = lambda *args: None
        api.initial_sample = lambda *args: dict(profile=dict(run=0))
        api.observe_install = lambda *args, **kwargs: events.append("full V snapshot") or {}
        api.installed_context = lambda *args: "V"
        api.analyze_install = lambda *args: dict(result="FULL_INSTALL_VERIFIED")
        c = types.SimpleNamespace(load=lambda name, path: types.SimpleNamespace(Trace=Trace, device_lock=nullcontext),
            action=lambda *args, **kwargs: None, save=self.store.write, now=cli.now)
        with mock.patch("builtins.print"):
            result = api.install_worker(c, self.store.base, "s04")
        self.assertEqual(result, 0)
        self.assertEqual(axes, [(921600, 8)])
        self.assertEqual(events, ["archive U configuration", "U readback closed", "trace ready", "launch V observation",
                                  "full V snapshot", "trace closed", "V verified"])
