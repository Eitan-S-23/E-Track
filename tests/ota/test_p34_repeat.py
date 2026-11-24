"""Host regressions for the single V-to-W repeat and original-record cleanup."""
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
backend = cli.load_module("p34_repeat_backend_tests", ROOT / "Tools/ota/p34_session_backend.py")
assets = cli.load_module("p34_successor_assets_tests", ROOT / "Tools/ota/p34_successor_assets.py")
window_tests = sys.modules["p34_window8_tests"]
OUTPUT = Path(os.environ["P34_TEST_OUT"])
GROUP = "n03-window8-repeat"


class RepeatTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.real_store = cli.Store(ROOT)
        cls.api = cli.backend(cls.real_store, cls.real_store.base / "profile-n03-window8-repeat.json", GROUP)
        cls.context = cls.api.context(OUTPUT / "repeat-context")
        cls.previous = cli.completed_full_predecessor(cls.real_store, cls.api.profile["predecessor"], group="n03-window8")
        # This is the historical V-to-W cleanup fixture, not today's device pointer.
        with mock.patch.object(cls.real_store, "current", return_value=cls.previous["out"].name):
            cls.selection = cli.completed_capture_target(cls.real_store, cls.previous["plan"]["predecessor"]["run"])

    def setUp(self):
        self.store = cli.Store(ROOT)
        self.store.base = self.store.checked(OUTPUT / "repeat-fixtures" / uuid.uuid4().hex)

    def test_repeat_binds_actual_V_and_W_not_a_prior_receiver_or_package(self):
        c = self.context
        self.assertEqual((c.receiver_version, c.target_version), (30218, 30219))
        self.assertEqual(c.bindings, c.v_assets["target_bindings"])
        self.assertEqual(c.receiver_image_sha, c.v_assets["target"]["sha256"])
        self.assertEqual(c.screen["bytes"], 290985)
        self.assertEqual(c.instrumentation["size"], 336)
        for old in (c.u_assets, c.v_assets, c.n03["groups"]["probe"]):
            self.assertNotEqual(c.screen, old["package"])
        phone = self.api.phone(c, "repeat_config_test", producer=True)
        config = phone.config(c, "s04", 921600, 8, "https://fixture.trycloudflare.com")
        self.assertEqual((config["currentVersionCode"], config["targetVersionCode"]), (30218, 30219))
        self.assertEqual((config["senderWindowSegments"], config["prefixBytes"], config["transferMode"]), (8, 0, "full"))
        self.assertEqual(config["currentImageSha256"], c.v_assets["target"]["sha256"])
        self.assertTrue(config["reuseGatt"] and config["withoutResponse"])
        for cell, baud, window in (("s01", 460800, 8), ("s04", 921600, 4), ("s04", 460800, 8)):
            with self.subTest(cell=cell, baud=baud, window=window), self.assertRaises(RuntimeError):
                phone.config(c, cell, baud, window, "https://fixture.trycloudflare.com")
        paths = {Path(item["path"]) for item in c.sources()}
        self.assertIn(ROOT / "Tools/ota/p34_successor_assets.py", paths)
        self.assertIn(ROOT / "tests/ota/test_p34_repeat.py", paths)

    def test_repeat_final_context_is_W_with_unchanged_Boot_MAP_and_layout(self):
        installed = self.api.installed_context(self.store.base / "installed")
        self.assertEqual(installed.receiver_version, 30219)
        self.assertEqual(installed.receiver_image_sha, self.context.target["sha256"])
        self.assertEqual(installed.bindings, self.context.full_assets["target_bindings"])
        for key in ("layout", "whole_boot"):
            self.assertEqual(installed.bindings[key], self.context.bindings[key])
        self.assertEqual(installed.flash_addresses, self.context.flash_addresses)

    def test_successor_changes_only_header_and_reuse_never_runs_packers(self):
        c = self.context
        source = Path(c.v_assets["target"]["path"]).read_bytes()
        target = Path(c.target["path"]).read_bytes()
        self.assertEqual(len(source), len(target))
        self.assertEqual(source[:0x400] + source[0x460:], target[:0x400] + target[0x460:])
        self.assertNotEqual(source[0x400:0x460], target[0x400:0x460])
        before = cli.record(c.screen["path"])
        with mock.patch.object(assets.subprocess, "run", side_effect=AssertionError("asset replay")):
            result = assets.prepare(c, cli.SUCCESSORS[GROUP])
        self.assertTrue(result["reused"])
        self.assertEqual(cli.record(c.screen["path"]), before)

    def test_generator_snapshot_preserves_provenance_without_requiring_mutable_origin(self):
        c = self.context
        frozen = c.full_assets["generator_snapshot"]
        self.assertNotEqual(Path(frozen["path"]), Path(assets.__file__))
        self.assertEqual(cli.record(frozen["path"]), frozen)
        original = c.record
        def record(path):
            value = original(path)
            return dict(value, sha256="0" * 64) if Path(path) == Path(assets.__file__) else value
        with mock.patch.object(c, "record", side_effect=record), \
                mock.patch.object(assets.subprocess, "run", side_effect=AssertionError("nonce regeneration")):
            self.assertTrue(assets.prepare(c, cli.SUCCESSORS[GROUP])["reused"])

    def test_successor_rejects_changed_receiver_specification_bindings_or_provenance(self):
        c, spec = self.context, cli.SUCCESSORS[GROUP]
        with mock.patch.object(c, "receiver_version", 30217), self.assertRaisesRegex(RuntimeError, "bound completed receiver"):
            assets.load(c, spec)
        original = c.read
        for keys in (("specification", "target_version"), ("target_bindings", "profile", "symbols", "rtt"),
                     ("generator", "bytes"), ("decoded", "image_bytes")):
            value = copy.deepcopy(c.full_assets)
            parent = value
            for key in keys[:-1]:
                parent = parent[key]
            parent[keys[-1]] += 1
            def read(path):
                return value if Path(path) == ROOT / spec["assets"] else original(path)
            with self.subTest(keys=keys), mock.patch.object(c, "read", side_effect=read), self.assertRaises(RuntimeError):
                assets.load(c, spec)

    def test_repeat_predecessor_consumes_original_V_and_rejects_U_as_V(self):
        self.assertEqual(self.previous["out"].name, "20260927T130601-85100")
        self.assertEqual(self.previous["plan"]["target_bindings"], self.context.bindings)
        self.assertEqual(self.previous["report"]["full_metrics"]["transfer_seconds"], 55.009445)
        with self.assertRaises(RuntimeError):
            cli.completed_full_predecessor(self.real_store, self.previous["plan"]["predecessor"], group="n03-window8")

    def test_unclosed_or_incomplete_V_is_not_a_repeat_predecessor(self):
        actual = cli.owner_state
        blocked = self.previous["out"] / "runtime/network"
        with mock.patch.object(cli, "owner_state", side_effect=lambda store, path: dict(state="UNCERTAIN") if path == blocked else actual(store, path)):
            with self.assertRaisesRegex(RuntimeError, "owners must be closed"):
                cli.completed_full_predecessor(self.real_store, self.previous["descriptor"], group="n03-window8")
        changed = copy.deepcopy(self.previous)
        changed["report"]["full_metrics"]["transfer"]["retransmitFrames"] = 1
        original = cli.installed_predecessor
        def installed(store, descriptor, prior, *, group="n03-install"):
            return changed if group == "n03-window8" else original(store, descriptor, prior, group=group)
        with mock.patch.object(cli, "installed_predecessor", side_effect=installed), self.assertRaisesRegex(RuntimeError, "complete V receive"):
            cli.completed_full_predecessor(self.real_store, self.previous["descriptor"], group="n03-window8")

    def test_known_journal_set_adds_V_for_the_new_zero_start_not_W(self):
        known = self.api.known_staging_packages(self.context)
        self.assertIn(self.context.v_assets["package"], known)
        self.assertIn(self.context.u_assets["package"], known)
        self.assertNotIn(self.context.full_assets["package"], known)

    def test_completed_cleanup_target_is_derived_from_U_original_query(self):
        value = self.selection
        report = value["selected"]["report"]
        query = self.real_store.read(report["inputs"]["query"]["path"])
        self.assertEqual(value["remote"], query["remote"])
        self.assertEqual(value["capture"], report["summary"]["captureId"])
        self.assertEqual(value["protected"]["descriptor"], self.previous["descriptor"])
        self.assertNotEqual(value["capture"], self.previous["report"]["summary"]["captureId"])
        for run in (self.previous["out"].name, "another-recording"):
            with self.subTest(run=run), mock.patch.object(self.real_store, "current", return_value=self.previous["out"].name), \
                    self.assertRaises(RuntimeError):
                cli.completed_capture_target(self.real_store, run)

    def test_quiesce_uses_the_exact_completed_V_not_old_U_pid(self):
        for case in ("live", "absent", "wrong-pid", "wrong-config", "active"):
            api, c, commands, events = window_tests.Window8Tests.quiesce_fixture(self, case)
            result = api.quiesce(c, self.store.base / case, self.previous)
            with self.subTest(case=case):
                self.assertEqual(result["result"], "APP_QUIESCED" if case in ("live", "absent") else "APP_QUIESCE_FAILED")
                self.assertEqual(sum(args[1:3] == ["am", "force-stop"] for args in commands), int(case == "live"))
                self.assertEqual(events, ["opened", "closed"])
                if case == "live":
                    self.assertEqual(result["pid"], self.previous["report"]["summary"]["pid"])

    def cleanup_fixture(self, case="normal", *, apply=False):
        selected, protected = self.selection["selected"], self.selection["protected"]
        capture, remote = self.selection["capture"], self.selection["remote"]
        current = protected["report"]["summary"]["captureId"]
        names = [capture, current]
        snapshot = Path(selected["report"]["inputs"]["snapshot"]["path"]).read_bytes()
        source = protected["out"] / "prestart-phone/app"
        health = self.real_store.read(source / "health-after.json")
        if case == "unhealthy":
            health["lost"] = 1
        if case == "wrong-capture":
            health["captureId"] = current
        data = {"health.json": json.dumps(health).encode(), "events.jsonl": (source / "events.jsonl").read_bytes(),
                "snapshot-1.jsonl": snapshot}
        if case == "wrong-snapshot":
            data["snapshot-1.jsonl"] = snapshot[:-1] + b"X"
        if case == "unknown-file":
            data["private.json"] = b"{}"
        if case == "multiple-snapshots":
            data["snapshot-2.jsonl"] = snapshot
        if case in ("pending-health", "empty-pending-health", "changing-pending-health", "oversize-pending-health"):
            data["health.json.tmp"] = (b"" if case == "empty-pending-health" else
                b"x" * 8193 if case == "oversize-pending-health" else b"interrupted-health-write")
        if case == "missing-protected":
            names.remove(current)
        if case == "missing-selected":
            names.remove(capture)
        calls, commands, events = [0], [], []
        pending_reads = [0]
        app_root = "/data/user/0/" + self.context.PKG
        def command(args, check=True, **kwargs):
            commands.append(args)
            if args[:4] == ["exec-out", "run-as", self.context.PKG, "stat"]:
                return str(len(data["health.json.tmp"]))
            if args[:4] == ["exec-out", "run-as", self.context.PKG, "head"]:
                self.assertEqual(args[4:6], ["-c", "8193"])
                self.assertTrue(kwargs["binary"])
                pending_reads[0] += 1
                raw = data["health.json.tmp"]
                return raw + b"changed" if case == "changing-pending-health" and pending_reads[0] > 1 else raw
            if args[1] == "pidof":
                return str(protected["report"]["summary"]["pid"]) if case == "live-app" else ""
            if args[:4] == ["exec-out", "run-as", self.context.PKG, "ls"]:
                return "\n".join(names if args[-1] == "files/p34-observations" else sorted(data))
            if args[:4] == ["exec-out", "run-as", self.context.PKG, "readlink"]:
                return app_root if args[-1] == "." else "/sdcard/redirected" if case == "redirected" else app_root + "/" + args[-1]
            if args == ["shell", "run-as", self.context.PKG, "rm", "-rf", remote]:
                names.remove(capture)
                return ""
            raise AssertionError("unexpected device command: " + str(args))
        def file_bytes(pkg, path, limit):
            self.assertEqual(pkg, self.context.PKG)
            self.assertTrue(path.startswith(remote + "/"))
            name = path[len(remote) + 1:]
            self.assertNotEqual(name, "health.json.tmp", "the ordinary nonempty-file primitive must stay unchanged")
            if name == "health.json":
                calls[0] += 1
                if case == "changing-health" and calls[0] > 1:
                    return json.dumps(dict(health, records=health["records"] + 1)).encode()
            return data[name]
        @contextmanager
        def usb(*args):
            events.append("opened")
            try:
                yield types.SimpleNamespace(command=command, file_bytes=file_bytes)
            finally:
                events.append("closed")
        api = object.__new__(backend.Backend)
        api.root, api.store = ROOT, self.store
        api.phone = lambda *args: types.SimpleNamespace(usb=usb)
        c = types.SimpleNamespace(PKG=self.context.PKG, checked=self.store.checked, save=self.store.write,
            raw=self.store.raw, read=self.store.read, now=cli.now, apk=self.context.apk, envelope=self.context.envelope)
        c.load = lambda name, path: types.SimpleNamespace(device_lock=nullcontext)
        out = self.store.base / "completed-prune" / case
        result = api.prune_completed(c, out, self.selection, apply=apply, tests={})
        return result, commands, events, out

    def test_completed_cleanup_defaults_to_archive_preview_even_with_a_live_current_App(self):
        result, commands, events, out = self.cleanup_fixture("live-app")
        self.assertEqual(result["result"], "COMPLETED_CAPTURE_ARCHIVED", result)
        self.assertEqual(result["phone_mutations"], 0)
        self.assertTrue(result["full_snapshot_verified"] and result["usb_closed"])
        self.assertFalse(any("rm" in args or "force-stop" in args for args in commands))
        self.assertFalse((out / "intent.json").exists())
        self.assertEqual(events, ["opened", "closed"])
        self.assertEqual(result["archived"]["snapshot-1.jsonl"]["sha256"], self.selection["selected"]["report"]["summary"]["rawSha256"])

    def test_completed_cleanup_apply_removes_only_U_after_real_snapshot_verification(self):
        result, commands, events, out = self.cleanup_fixture(apply=True)
        self.assertEqual(result["result"], "COMPLETED_CAPTURE_PRUNED", result)
        self.assertEqual(result["phone_mutations"], 1)
        self.assertEqual(result["removed"], [self.selection["capture"]])
        self.assertEqual(result["remaining"], [self.previous["report"]["summary"]["captureId"]])
        self.assertTrue(result["usb_closed"])
        self.assertEqual(events, ["opened", "closed"])
        self.assertEqual(sum("rm" in args for args in commands), 1)
        self.assertFalse(any("force-stop" in args or "clear" in args for args in commands))
        intent = self.store.read(out / "intent.json")
        self.assertEqual(intent["remote"], self.selection["remote"])
        self.assertEqual(intent["resolved"], "/data/user/0/" + self.context.PKG + "/" + self.selection["remote"])

    def test_completed_cleanup_rejects_unsafe_or_changed_originals_without_delete(self):
        for case in ("live-app", "unhealthy", "wrong-capture", "wrong-snapshot", "unknown-file", "multiple-snapshots",
                     "missing-protected", "missing-selected", "changing-health", "redirected"):
            result, commands, events, out = self.cleanup_fixture(case, apply=True)
            with self.subTest(case=case):
                self.assertEqual(result["result"], "COMPLETED_CAPTURE_PRUNE_FAILED")
                self.assertFalse(any("rm" in args for args in commands))
                self.assertFalse((out / "intent.json").exists())
                self.assertEqual(events, ["opened", "closed"])

    def test_completed_cleanup_does_not_repeat_a_success_or_an_uncertain_delete(self):
        result, commands, _, out = self.cleanup_fixture(apply=True)
        with mock.patch.object(cli, "verify_tests", return_value={}), \
                mock.patch.object(cli, "completed_capture_target", return_value=self.selection), \
                mock.patch.object(cli, "backend", side_effect=AssertionError("repeated USB scope")):
            self.assertEqual(cli.prune_completed(self.store, self.selection["selected"]["out"].name, apply=True)["removed"], result["removed"])
            self.store.write(out / "result.json", dict(result="COMPLETED_CAPTURE_PRUNE_FAILED"), replace=True)
            with self.assertRaisesRegex(RuntimeError, "may have acted"):
                cli.prune_completed(self.store, self.selection["selected"]["out"].name, apply=True)

    def test_completed_cleanup_preserves_stable_pending_health_without_trusting_it(self):
        for case, expected in (("pending-health", b"interrupted-health-write"), ("empty-pending-health", b"")):
            for apply in (False, True):
                self.setUp()
                result, commands, events, out = self.cleanup_fixture(case, apply=apply)
                self.assertEqual(result["result"], "COMPLETED_CAPTURE_PRUNED" if apply else "COMPLETED_CAPTURE_ARCHIVED", result)
                self.assertEqual((out / "app/health.json.tmp").read_bytes(), expected)
                self.assertEqual(result["archived"]["health.json.tmp"], cli.record(out / "app/health.json.tmp"))
                self.assertTrue(result["full_snapshot_verified"])
                self.assertEqual(sum("rm" in args for args in commands), int(apply))
                self.assertEqual(events, ["opened", "closed"])

    def test_completed_cleanup_rejects_changing_or_oversize_pending_health(self):
        for case in ("changing-pending-health", "oversize-pending-health"):
            result, commands, events, out = self.cleanup_fixture(case, apply=True)
            self.assertEqual(result["result"], "COMPLETED_CAPTURE_PRUNE_FAILED")
            self.assertFalse(any("rm" in args for args in commands))
            self.assertFalse((out / "intent.json").exists())
            self.assertEqual(events, ["opened", "closed"])

    def test_cleanup_apply_flag_cannot_change_other_commands(self):
        with self.assertRaisesRegex(RuntimeError, "only valid for prune-completed"):
            cli.main(["--root", str(ROOT), "--apply", "status"])

    def test_V_advances_once_to_repeat_and_attempted_W_never_replays(self):
        old = self.store.run("completed-v")
        profile = self.store.base / "profile.json"
        self.store.write(profile, dict(predecessor={}))
        self.store.write(self.store.base / "current.json", dict(run=old.name))
        self.store.write(old / "plan.json", dict(group="n03-window8"))
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
            prepare=lambda c, out, phone, tests: self.store.write(out / "plan.json", dict(group=GROUP)))
        state = dict(result="fixture", network=dict(state="CLOSED"))
        with mock.patch.object(cli, "verify_tests", return_value={}), mock.patch.object(cli, "status", return_value=state), \
                mock.patch.object(cli, "completed_full_predecessor", return_value=dict(out=old, descriptor={})) as predecessor, \
                mock.patch.object(cli, "backend", return_value=api) as factory:
            cli.start(self.store, profile, "s04", GROUP)
            predecessor.assert_called_once_with(self.store, {}, group="n03-window8")
            factory.assert_called_once()
            factory.reset_mock()
            for group in (GROUP, "n03-window8", "n03-full", "n03-a"):
                self.assertEqual(cli.start(self.store, profile, "s04", group), state)
            factory.assert_not_called()
        self.assertEqual(launched, ["network", "s04"])
        self.assertNotEqual(self.store.current(), old.name)
        self.assertEqual(cli.record(original["path"]), original)

    def test_repeat_rejects_wrong_axes_and_wrong_V_owner_before_backend(self):
        profile = self.store.base / "profile.json"
        self.store.write(profile, dict(predecessor={}))
        self.store.write(self.store.base / "current.json", dict(run="other-v"))
        self.store.write(self.store.run("other-v") / "plan.json", dict(group="n03-window8"))
        with mock.patch.object(cli, "verify_tests", return_value={}), \
                mock.patch.object(cli, "completed_full_predecessor", return_value=dict(out=self.store.run("bound-v"))), \
                mock.patch.object(cli, "backend", side_effect=AssertionError("new service")):
            with self.assertRaisesRegex(RuntimeError, "only s04"):
                cli.start(self.store, profile, "s01", GROUP)
            with self.assertRaisesRegex(RuntimeError, "actual completed V owner"):
                cli.start(self.store, profile, "s04", GROUP)
