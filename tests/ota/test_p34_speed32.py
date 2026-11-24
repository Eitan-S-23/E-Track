"""Host-only window-32 successor tests; never operate a device."""
import copy
from contextlib import contextmanager, nullcontext
import os
from pathlib import Path
import sys
import types
import unittest
import uuid
from unittest import mock

ROOT = Path(__file__).resolve().parents[2]
cli = sys.modules["p34_session"]
OUTPUT = Path(os.environ["P34_TEST_OUT"])


class Speed32Tests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.store = cli.Store(ROOT)
        cls.profile = cls.store.base / "profile-speed-window32.json"
        cls.api = cli.backend(cls.store, cls.profile, cli.SPEED32_GROUP)
        cls.c = cls.api.context(OUTPUT / "speed32-context")

    def test_header_only_successor_preserves_full_executable_MAP_and_Boot(self):
        c = self.c
        self.assertEqual((c.receiver_version, c.target_version), (30225, 30226))
        before, after = (Path(x["path"]).read_bytes() for x in (c.previous_assets["target"], c.target))
        self.assertEqual(before[:0x400] + before[0x460:], after[:0x400] + after[0x460:])
        self.assertEqual(c.bindings["profile"]["map"], c.full_assets["target_bindings"]["profile"]["map"])
        self.assertEqual(c.bindings["whole_boot"], c.full_assets["target_bindings"]["whole_boot"])
        self.assertFalse(c.full_assets["bootstrap"])
        self.assertNotEqual(c.screen, c.previous_assets["package"])
        self.assertEqual(cli.cells_for(cli.SPEED32_GROUP)["s04"], (921600, 32))
        self.assertEqual(cli.cells_for(cli.SPEED16_GROUP)["s04"], (921600, 16))
        self.assertEqual(cli.cells_for(cli.NATIVE_DIAGNOSTIC_GROUP)["s04"], (921600, 8))

    def test_config_accepts_only_planned_full_32_and_keeps_transport_guards(self):
        phone = self.api.phone(self.c, "speed32_phone_test")
        value = phone.config(self.c, "s04", 921600, 32, "https://fixture.trycloudflare.com")
        self.assertEqual((value["transferMode"], value["prefixBytes"], value["senderWindowSegments"]), ("full", 0, 32))
        self.assertTrue(value["reuseGatt"] and value["withoutResponse"])
        self.assertFalse(self.api.profile["native_diagnostic"])
        self.assertEqual(self.api.profile["tunnel_protocol"], "quic")
        notes = phone.service_config(self.c, "https://fixture.trycloudflare.com")["releases"][self.c.release_key]["releaseNotes"]
        self.assertIn("Window-32 speed screen", notes)
        for cell, baud, window in (("s01", 921600, 32), ("s04", 460800, 32), ("s04", 921600, 16), ("s04", 921600, 33)):
            with self.subTest(cell=cell, baud=baud, window=window), self.assertRaises(RuntimeError):
                phone.config(self.c, cell, baud, window, "https://fixture.trycloudflare.com")

    def test_actual_completed_16_is_required_and_Z_cannot_substitute(self):
        previous = cli.completed_full_predecessor(self.store, self.api.profile["predecessor"], group=cli.SPEED16_GROUP)
        self.assertEqual(previous["out"].name, "20260929T030709-75800")
        self.assertEqual(previous["report"]["full_metrics"]["transfer_seconds"], 42.462693)
        with self.assertRaises(RuntimeError):
            cli.completed_full_predecessor(self.store, self.api.profile["predecessor"], group=cli.NATIVE_DIAGNOSTIC_GROUP)
        self.assertEqual(self.api.profile["owned_configs"], [{key: previous["report"]["inputs"]["config"][key]
            for key in ("path", "sha256")}])

    def test_wrong_profile_flags_fail_before_context_or_device(self):
        for change in (dict(speed_window32=False), dict(native_diagnostic=True), dict(tunnel_protocol="http2")):
            value = dict(self.api.profile, **change)
            with self.subTest(change=change), self.assertRaisesRegex(RuntimeError, "window-32 screening profile"):
                type(self.api)(self.store, self.profile, value, cli.SPEED32_GROUP)

    def test_asset_reuse_does_not_repack_and_wrong_version_fails(self):
        assets = self.api.install_api
        spec = cli.N04_GROUPS[cli.SPEED32_GROUP]
        with mock.patch.object(assets.subprocess, "run", side_effect=AssertionError("must not repack")):
            result = assets.prepare(self.c, spec)
        self.assertTrue(result["reused"])
        self.assertEqual(result["device_operations"], 0)
        for change in (dict(target_version=30227), dict(receiver=30222)):
            with self.subTest(change=change), self.assertRaises(RuntimeError):
                assets.receiver(self.c, dict(spec, **change))

    def test_preparation_is_idempotent_and_rejects_a_wrong_owner(self):
        with mock.patch.object(self.store, "current", return_value="20260929T030709-75800"), \
             mock.patch.object(self.api.install_api.subprocess, "run", side_effect=AssertionError("must not repack")):
            result = cli.prepare_speed32(self.store)
        self.assertEqual(result["profile"], cli.record(self.profile))
        for run in (None, "20260928T144139-55600"):
            with self.subTest(run=run), mock.patch.object(self.store, "current", return_value=run), \
                 mock.patch.object(cli, "backend", side_effect=AssertionError("must reject before backend")), \
                 self.assertRaises(RuntimeError):
                cli.prepare_speed32(self.store)

    def test_only_original_Z_is_cleanup_eligible_and_30225_is_protected(self):
        with mock.patch.object(self.store, "current", return_value="20260929T030709-75800"):
            selected = cli.completed_capture_target(self.store, "20260928T144139-55600")
            self.assertEqual(selected["capture"], "1790606692563314-ee73468a16dc2b5a592c55c7")
            self.assertEqual(selected["protected"]["report"]["summary"]["captureId"],
                             "1790651663430351-f87498813e0925f6ea4ed12c")
            for run in ("20260929T030709-75800", "20260927T162548-11400"):
                with self.subTest(run=run), self.assertRaises(RuntimeError):
                    cli.completed_capture_target(self.store, run)

    def test_source_and_staging_sets_preserve_old_groups_and_never_trust_new_target(self):
        known = self.api.known_staging_packages(self.c)
        self.assertIn(self.c.previous_assets["package"], known)
        self.assertNotIn(self.c.screen, known)
        paths = {Path(item["path"]) for item in self.c.sources()}
        self.assertIn(ROOT / "tests/ota/test_p34_speed32.py", paths)
        self.assertNotIn(ROOT / "Tools/ota/p34_android_trace.py", paths)
        self.assertNotIn(cli.SPEED32_GROUP, cli.n04_asset_groups(cli.SPEED16_GROUP))
        self.assertNotIn(cli.SPEED16_GROUP, cli.n04_asset_groups(cli.NATIVE_DIAGNOSTIC_GROUP))
        self.assertEqual(cli.PREDECESSOR_GROUPS[cli.SPEED32_GROUP], cli.SPEED16_GROUP)
        self.assertEqual({name for name, prior in cli.PREDECESSOR_GROUPS.items() if prior == cli.SPEED32_GROUP},
                         {"patch32-bootstrap"})

    def test_attempted_32_is_latched_for_success_or_failure(self):
        store = cli.Store(ROOT)
        store.base = store.checked(OUTPUT / "speed32-latched")
        out = store.run("attempted32")
        store.write(out / "plan.json", dict(group=cli.SPEED32_GROUP))
        for result in ("FULL_INSTALL_VERIFIED", "FULL_INSTALL_INCOMPLETE"):
            for group in (cli.SPEED32_GROUP, cli.SPEED16_GROUP, cli.NATIVE_DIAGNOSTIC_GROUP):
                with self.subTest(result=result, group=group), \
                     mock.patch.object(store, "current", return_value="attempted32"), \
                     mock.patch.object(cli, "status", return_value=dict(result=result)), \
                     mock.patch.object(cli, "verify_tests", return_value={}), \
                     mock.patch.object(cli, "backend", side_effect=AssertionError("must not restart")):
                    self.assertEqual(cli.start(store, self.profile, "s04", group)["result"], result)


class RetirementRecoveryTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.store = cli.Store(ROOT)
        cls.api = cli.retirement_api(cls.store)
        cls.run_id = "20260929T045644-98600"
        cls.profile = cls.store.base / "profile-speed-window32.json"
        cls.failed = cls.api.failure(cls.store, cls.run_id, cls.profile)
        cls.observed = cls.store.read(cls.store.base / "doctor/1790659867472185600/phone/app/result.json")

    def failure_with(self, change):
        read = self.store.read
        def changed(path):
            value = read(path)
            return change(Path(path), value)
        with mock.patch.object(self.store, "read", side_effect=changed), \
             mock.patch.object(cli, "completed_full_predecessor", return_value=self.failed["previous"]):
            return self.api.failure(self.store, self.run_id, self.profile)

    def test_original_failure_is_pre_admission_and_no_transfer(self):
        self.assertEqual(self.failed["capture_directories"], 7)
        self.assertEqual(self.failed["config"]["sha256"], self.failed["archive"].split("/")[-1][:-5])
        self.assertIn("cells/s04/usb/commands.jsonl", self.failed["inputs"])

    def test_wrong_group_and_started_results_are_rejected(self):
        for change in (dict(group=cli.SPEED16_GROUP), dict(target_version=30227)):
            with self.subTest(change=change), self.assertRaises(RuntimeError):
                self.failure_with(lambda p, v: dict(v, **change) if p.name == "plan.json" else v)
        for change in (dict(before={}), dict(summary={}), dict(result="FULL_INSTALL_VERIFIED")):
            with self.subTest(change=change), self.assertRaises(RuntimeError):
                self.failure_with(lambda p, v: dict(v, **change) if p == self.store.run(self.run_id) / "cells/s04/result.json" else v)

    def test_native_or_app_artifacts_prevent_recovery(self):
        original = Path.iterdir
        cell = self.store.run(self.run_id) / "cells/s04"
        for marker in ("mcu", "provision.json", "launch.json", "runtime-config.json", "queries"):
            def entries(path):
                return iter([*original(path), path / marker]) if path == cell else original(path)
            with self.subTest(marker=marker), mock.patch.object(Path, "iterdir", entries), self.assertRaises(RuntimeError):
                self.api.failure(self.store, self.run_id, self.profile)

    def test_live_or_uncertain_owner_prevents_recovery(self):
        for state in ("LIVE", "UNCERTAIN", "STARTING"):
            with self.subTest(state=state), mock.patch.object(cli, "owner_state", return_value=dict(state=state)), \
                 self.assertRaises(RuntimeError):
                self.api.failure(self.store, self.run_id, self.profile)

    def test_live_pid_or_wrong_retirement_archive_is_rejected(self):
        for field in ("pid", "archive"):
            def change(path, value):
                if path.name == "retire-intent.json":
                    if field == "pid":
                        value["observation"]["pid"] = 123
                    else:
                        value["archive"] += "-wrong"
                return value
            with self.subTest(field=field), self.assertRaises(RuntimeError):
                self.failure_with(change)

    def test_unchanged_completed_phone_and_absent_config_are_required(self):
        self.api.verify_phone(self.store, self.observed, self.failed)
        for change in (dict(pid=123), dict(config=self.failed["config"]), dict(stable_completed=False),
                       dict(capture_directories=8), dict(remote="files/p34-observations/other"), dict(snapshots=[])):
            with self.subTest(change=change), self.assertRaises(RuntimeError):
                self.api.verify_phone(self.store, dict(self.observed, **change), self.failed)

    def test_usb_requires_graceful_closure_and_unchanged_input_key(self):
        good = self.store.read(self.store.run(self.run_id) / "cells/s04/usb/closed.json")
        self.api.verify_usb(good)
        for change in (dict(port_closed=False), dict(stop_exit=1), dict(key_after={}), dict(cleanup_error="fixture")):
            with self.subTest(change=change), self.assertRaises(RuntimeError):
                self.api.verify_usb(dict(good, **change))

    def model_reconcile(self, *, corrupt_archive=False):
        store = cli.Store(ROOT)
        store.base = store.checked(OUTPUT / "retirement-model" / uuid.uuid4().hex)
        store.write(store.run(self.run_id) / "plan.json", dict(profile=dict(path=str(self.profile))))
        observed = copy.deepcopy(self.observed)
        p, impl = mock.Mock(), mock.Mock()
        data = Path(self.failed["config"]["path"]).read_bytes()
        p.file_bytes.return_value = data + b"bad" if corrupt_archive else data
        pkg = "com.wen.gaia.gaia.p34probe"
        def command(args, **kwargs):
            if args == ["get-state"]:
                return "device"
            if args[:2] == ["shell", "pidof"]:
                return ""
            if args[:5] == ["exec-out", "run-as", pkg, "readlink", "-f"]:
                return "/data/user/0/" + pkg + ("" if args[-1] == "." else "/" + args[-1])
            raise AssertionError("unexpected device command: " + str(args))
        p.command.side_effect = command
        c = types.SimpleNamespace(PKG=pkg, sources=lambda: [], raw=store.raw, read=store.read,
            checked=store.checked, load=lambda *a: types.SimpleNamespace(device_lock=nullcontext))
        good_usb = self.store.read(self.store.run(self.run_id) / "cells/s04/usb/closed.json")
        @contextmanager
        def usb(context, out):
            try:
                yield p
            finally:
                store.write(out / "usb/closed.json", good_usb)
        phone = types.SimpleNamespace(usb=usb, exists=lambda *a: False)
        impl.context.return_value = c
        impl.phone.return_value = phone
        def capture(context, device, adapter, out):
            store.write(out / "result.json", observed)
            return observed
        impl.capture.side_effect = capture
        with mock.patch.object(cli, "verify_tests", return_value={}), \
             mock.patch.object(store, "current", return_value=self.run_id), \
             mock.patch.object(self.api, "failure", return_value=self.failed), \
             mock.patch.object(cli, "backend", return_value=impl):
            result = self.api.reconcile(store, self.run_id)
        return store, result, p

    def test_reconciliation_reads_archive_without_replaying_the_move(self):
        store, result, p = self.model_reconcile()
        self.assertEqual(result["result"], "RETIREMENT_RECONCILED")
        self.assertEqual((result["phone_mutations"], result["mcu_operations"]), (0, 0))
        self.assertFalse((store.base / "current.json").exists())
        with mock.patch.object(self.api, "failure", return_value=self.failed):
            loaded = self.api.load_recovery(store, Path(result["report"]["path"]), self.profile)
        self.assertEqual(loaded["failure"]["run"], self.run_id)
        self.assertFalse(any("mv" in call.args[0] or "start" in call.args[0] for call in p.command.call_args_list))

    def test_archive_mismatch_never_produces_a_recovery_token(self):
        store, result, _ = self.model_reconcile(corrupt_archive=True)
        self.assertEqual(result["result"], "RETIREMENT_RECOVERY_FAILED")
        with self.assertRaises(RuntimeError):
            self.api.load_recovery(store, Path(result["report"]["path"]), self.profile)

    def test_external_pinned_tool_is_read_only_not_an_output(self):
        store, result, _ = self.model_reconcile()
        report = Path(result["report"]["path"])
        value = store.read(report)
        external = cli.record(Path(sys.executable))
        value["sources"] = [external]
        store.write(report, value, replace=True)
        with mock.patch.object(self.api, "failure", return_value=self.failed):
            self.api.load_recovery(store, report, self.profile)
            record = cli.record
            def changed(path):
                return dict(external, sha256="0" * 64) if Path(path) == Path(sys.executable) else record(path)
            with mock.patch.object(cli, "record", side_effect=changed), self.assertRaisesRegex(RuntimeError, "source changed"):
                self.api.load_recovery(store, report, self.profile)
            value["archive"] = external
            store.write(report, value, replace=True)
            with self.assertRaises(ValueError):
                self.api.load_recovery(store, report, self.profile)

    def test_recovery_token_cannot_be_reused_after_current_advances(self):
        recovered = dict(failure=self.failed)
        with mock.patch.object(cli, "verify_tests", return_value={}), \
             mock.patch.object(self.store, "current", return_value="new-owner"), \
             mock.patch.object(cli, "retirement_api", return_value=types.SimpleNamespace(load_recovery=lambda *a: recovered)), \
             mock.patch.object(cli, "backend", side_effect=AssertionError("must not start")), \
             self.assertRaisesRegex(RuntimeError, "already consumed"):
            cli.start(self.store, self.profile, "s04", cli.SPEED32_GROUP, retirement_path=Path("fixture"))

    def test_explicit_recovery_creates_one_new_owner_without_rewinding_current(self):
        store = cli.Store(ROOT)
        store.base = store.checked(OUTPUT / "retirement-start" / uuid.uuid4().hex)
        store.write(store.base / "current.json", dict(run=self.run_id))
        old = store.run(self.run_id) / "plan.json"
        store.write(old, dict(group=cli.SPEED32_GROUP))
        original = cli.record(old)
        recovered = dict(failure=self.failed, value={}, report={"fixture": True})
        impl = mock.Mock()
        impl.inspect.return_value = dict(result="APP_INSPECTED")
        impl.prepare.side_effect = lambda c, out, phone, tests: store.write(out / "plan.json", dict(group=cli.SPEED32_GROUP))
        state = dict(result="PREPARING", network=dict(state="CLOSED"))
        with mock.patch.object(cli, "verify_tests", return_value={}), \
             mock.patch.object(cli, "retirement_api", return_value=types.SimpleNamespace(load_recovery=lambda *a: recovered)), \
             mock.patch.object(cli, "status", return_value=state), \
             mock.patch.object(cli, "owner_state", return_value=dict(state="CLOSED")), \
             mock.patch.object(cli, "wait_until", return_value=True), \
             mock.patch.object(cli, "backend", return_value=impl) as backend:
            cli.start(store, self.profile, "s04", cli.SPEED32_GROUP, retirement_path=Path("fixture"))
            new_run = store.current()
            self.assertNotEqual(new_run, self.run_id)
            self.assertNotEqual(new_run, self.failed["previous"]["out"].name)
            self.assertEqual(cli.record(old), original)
            self.assertIs(impl.retirement_recovery, recovered)
            self.assertTrue((store.run(new_run) / "cells/s04/intent.json").is_file())
            cli.start(store, self.profile, "s04", cli.SPEED32_GROUP)
            self.assertEqual(backend.call_count, 1)
            with self.assertRaisesRegex(RuntimeError, "already consumed"):
                cli.start(store, self.profile, "s04", cli.SPEED32_GROUP, retirement_path=Path("fixture"))

    def test_recovery_flag_does_not_enable_other_commands_or_groups(self):
        with self.assertRaises(RuntimeError):
            cli.main(["--root", str(ROOT), "status", "--retirement-recovery", "fixture"])
        with mock.patch.object(cli, "verify_tests", return_value={}), self.assertRaisesRegex(RuntimeError, "window-32 only"):
            cli.start(self.store, self.profile, "s04", cli.SPEED16_GROUP, retirement_path=Path("fixture"))


TEST_CLASSES = (Speed32Tests, RetirementRecoveryTests)
