"""Full N03 host checks, including the real reader over a modeled native link."""
from __future__ import annotations

import copy
from contextlib import nullcontext
import io
import json
import os
from pathlib import Path
import struct
import sys
import time
import types
import unittest
from unittest import mock
import uuid

ROOT = Path(__file__).resolve().parents[2]
cli = sys.modules["p34_session"]
backend = cli.load_module("p34_full_backend_tests", ROOT / "Tools/ota/p34_session_backend.py")
assets = cli.load_module("p34_full_assets_tests", ROOT / "Tools/ota/p34_full_assets.py")
trace = cli.load_module("p34_full_trace_tests", ROOT / "Tools/ota/p34_full_trace.py")
OUTPUT = Path(os.environ["P34_TEST_OUT"])


class FullTests(unittest.TestCase):
    def setUp(self):
        self.store = cli.Store(ROOT)
        self.store.base = self.store.checked(OUTPUT / "full-fixtures" / uuid.uuid4().hex)

    def real_context(self):
        store = cli.Store(ROOT)
        api = cli.backend(store, store.base / "profile-n03-full.json", "n03-full")
        return api, api.context(self.store.base / "context")

    def test_header_only_successor_cannot_change_vectors_body_or_length(self):
        source = bytes(0x500)
        changed = bytearray(source)
        changed[0x410] = 1
        assets.same_executable(source, changed)
        for offset in (0, 0x3ff, 0x460, 0x4ff):
            target = bytearray(changed)
            target[offset] ^= 1
            with self.subTest(offset=offset), self.assertRaisesRegex(RuntimeError, "executable byte"):
                assets.same_executable(source, target)
        with self.assertRaises(RuntimeError):
            assets.same_executable(source, source[:-1])

    def test_real_full_context_binds_U_not_T_and_both_receiver_epochs(self):
        api, c = self.real_context()
        self.assertEqual((c.receiver_version, c.target_version), (30215, 30217))
        self.assertEqual(c.instrumentation["size"], 336)
        self.assertEqual(c.screen["bytes"], 290969)
        self.assertEqual(c.target["bytes"], 613580)
        self.assertNotEqual(c.screen, c.n03["groups"]["probe"]["package"])
        installed = api.installed_context(self.store.base / "after")
        self.assertEqual(installed.receiver_version, 30217)
        self.assertEqual(installed.receiver_image_sha, c.target["sha256"])
        self.assertEqual(installed.bindings["profile"]["map"], c.bindings["profile"]["map"])
        self.assertEqual(installed.flash_addresses, c.flash_addresses)
        phone = api.phone(c, "full_config_test", producer=True)
        config = phone.config(c, "s04", 921600, 4, "https://fixture.trycloudflare.com")
        self.assertEqual((config["transferMode"], config["prefixBytes"]), ("full", 0))
        self.assertEqual((config["currentVersionCode"], config["targetVersionCode"]), (30215, 30217))
        self.assertEqual(config["packageSha256"], c.screen["sha256"])
        served = phone.service_config(c, "https://fixture.trycloudflare.com")
        release = served["releases"][c.release_key]
        self.assertIn("retain the N03 executable", release["releaseNotes"])
        self.assertIn(assets.SERVED_NAME, json.dumps(release))
        with self.assertRaises(RuntimeError):
            phone.config(c, "s01", 460800, 4, "https://fixture.trycloudflare.com")

    def test_real_full_predecessor_is_completed_B_not_A_or_installation(self):
        api, c = self.real_context()
        value = api.predecessor(c)
        self.assertEqual(value["out"].name, "20260927T091758-93000")
        old = cli.Store(ROOT).read(value["plan"]["profile"]["path"])
        for descriptor in (old["predecessor"], old["installation"]):
            with self.assertRaises(RuntimeError):
                cli.full_predecessor(cli.Store(ROOT), descriptor)

    def test_prepared_asset_reuse_never_regenerates_nonce_or_runs_commands(self):
        api, _ = self.real_context()
        c = cli.backend(cli.Store(ROOT), api.profile_path, "n03-b").context(self.store.base / "reuse")
        with mock.patch.object(assets.subprocess, "run", side_effect=AssertionError("asset replay")):
            result = assets.prepare(c)
        self.assertTrue(result["reused"])
        self.assertEqual(result["device_operations"], 0)

    def test_successor_layout_and_receiver_tampering_fail_closed(self):
        api, _ = self.real_context()
        c = cli.backend(cli.Store(ROOT), api.profile_path, "n03-b").context(self.store.base / "tamper")
        original = c.read
        for key in ("receiver_bindings", "target_bindings"):
            manifest = copy.deepcopy(original(ROOT / assets.RELATIVE))
            manifest[key]["profile"]["symbols"]["rtt"] += 4
            with self.subTest(key=key), mock.patch.object(c, "read", return_value=manifest), self.assertRaises(RuntimeError):
                assets.load(c)

    def test_full_replay_returns_attempt_including_failure_without_backend(self):
        out = self.store.run("already-full")
        self.store.write(self.store.base / "current.json", dict(run=out.name))
        self.store.write(out / "plan.json", dict(group="n03-full"))
        self.store.write(out / "cells/s04/status.json", dict(result="FULL_INSTALL_INCOMPLETE"))
        self.store.write(out / "runtime/s04/closed.json", dict(worker_exit=1))
        for group in ("n03-full", "n03-a", "n03-install"):
            with mock.patch.object(cli, "verify_tests", return_value={}), mock.patch.object(cli, "backend",
                    side_effect=AssertionError("replay")):
                result = cli.start(self.store, self.store.base / "unused.json", "s04", group)
            self.assertEqual(result["result"], "FULL_INSTALL_INCOMPLETE")
            self.assertEqual(result["cell"], "s04")

    def test_full_rejects_unplanned_axes_before_any_backend(self):
        with mock.patch.object(cli, "verify_tests", return_value={}), self.assertRaisesRegex(RuntimeError, "only s04"):
            cli.start(self.store, self.store.base / "unused.json", "s02", "n03-full")

    def test_full_store_stops_before_plan_network_and_mcu_preparation(self):
        api = object.__new__(backend.Backend)
        api.predecessor = mock.Mock(side_effect=AssertionError("preparation must not continue"))
        for count in (8, 9, None, -1, True):
            with self.subTest(count=count), self.assertRaisesRegex(RuntimeError, "free slot"):
                api.prepare(None, self.store.base / "unused", dict(capture_directories=count), {})
        api.predecessor.assert_not_called()
        self.assertFalse(self.store.base.exists())
        for count in (0, 7):
            with self.assertRaisesRegex(AssertionError, "preparation must not continue"):
                api.prepare(None, self.store.base / "unused", dict(capture_directories=count), {})

    def test_new_process_cannot_consume_a_previous_process_snapshot(self):
        api = object.__new__(backend.Backend)
        capture = "1790500881632914-6e3a13cdcca1e84e5e34d497"
        remote = "files/p34-observations/" + capture
        phone = types.SimpleNamespace(location=lambda *args: (30282, remote), exists=lambda *args: True)
        p = mock.Mock()
        header = dict(seq=1, kind="open", schema=1, pid=17852, captureId=capture,
                      sentinel="fixture", target="02:00:00:00:00:01")
        stamp = dict(seq=2, kind="line", message="fixture stamp")
        p.command.return_value = json.dumps(header) + "\n" + json.dumps(stamp) + "\n"
        c = types.SimpleNamespace(PKG="fixture", TARGET=header["target"],
            apk=dict(metadata=dict(device_observation=dict(sentinel="fixture"))),
            envelope=types.SimpleNamespace(same_device=lambda a, b: a == b))
        with mock.patch.object(backend, "verify_experiment") as verify:
            self.assertIsNone(api.launched_capture(c, p, phone, self.store.base, 30282, {}))
            verify.assert_not_called()
            header["pid"] = 30282
            p.command.return_value = json.dumps(header) + "\n" + json.dumps(stamp) + "\n"
            self.store.write(self.store.base / "runtime-config.json", {})
            self.assertEqual(api.launched_capture(c, p, phone, self.store.base, 30282, {}), remote)
            verify.assert_called_once()
            verify.side_effect = RuntimeError("wrong configuration")
            with self.assertRaisesRegex(RuntimeError, "wrong configuration"):
                api.launched_capture(c, p, phone, self.store.base, 30282, {})
        p.command.return_value = json.dumps(header) + "\n"
        self.assertIsNone(api.launched_capture(c, p, phone, self.store.base, 30282, {}))

    def test_stale_download_size_waits_without_reading_old_package(self):
        api = object.__new__(backend.Backend)
        api.served_name = "fixture.etu"
        c = types.SimpleNamespace(PKG="fixture", screen_bytes=b"current")
        for size in ("0", "6", "8", "291771", "99999999999999999999"):
            p = mock.Mock()
            p.command.return_value = size + "\n"
            self.assertIsNone(api.downloaded_package(c, p))
            p.file_bytes.assert_not_called()

    def test_download_admission_still_requires_exact_bytes(self):
        api = object.__new__(backend.Backend)
        api.served_name = "fixture.etu"
        c = types.SimpleNamespace(PKG="fixture", screen_bytes=b"current")
        p = mock.Mock()
        p.command.return_value = "7\n"
        p.file_bytes.return_value = b"oldfile"
        self.assertIsNone(api.downloaded_package(c, p))
        p.file_bytes.return_value = c.screen_bytes
        self.assertEqual(api.downloaded_package(c, p), c.screen_bytes)
        p.file_bytes.assert_called_with("fixture", "app_flutter/firmware/fixture.etu", 8)
        p.file_bytes.side_effect = RuntimeError("USB disconnected")
        with self.assertRaisesRegex(RuntimeError, "USB disconnected"):
            api.downloaded_package(c, p)
        for size in ("", "-1", "+7", "7 extra", "07", "1" * 21):
            p.command.return_value = size
            with self.assertRaisesRegex(RuntimeError, "invalid download cache size"):
                api.downloaded_package(c, p)

    def test_observer_waits_for_current_download_before_admitting_start(self):
        api = object.__new__(backend.Backend)
        api.group, api.served_name = "receive-bootstrap", "fixture.etu"
        stage = [0]
        health = dict(healthy=True, lost=0, error=None, upgradeStarts=0, upgradeEnds=0)
        def read(pkg, path, limit):
            if path.endswith("health.json"):
                return json.dumps(dict(health, upgradeStarts=int(stage[0] == 2),
                                       upgradeEnds=int(stage[0] == 2))).encode()
            return b"events"
        p = types.SimpleNamespace(file_bytes=read, query=types.SimpleNamespace(validate=lambda *args, **kwargs:
            (dict(successfulQueries=1), b"checkpoint", "messages")))
        phone = types.SimpleNamespace(exists=lambda *args: True)
        api.launched_capture = lambda *args: "files/capture"
        api.downloaded_package = mock.Mock(side_effect=[None, b"current"])
        api.finish_install_snapshot = lambda *args: dict(completed=True)
        c = types.SimpleNamespace(save=self.store.write, raw=self.store.raw, now=cli.now, cell="s04",
            PKG="fixture", TARGET="fixture", target_version=30229, envelope=types.SimpleNamespace(MAX_BYTES=4096),
            apk=dict(metadata=dict(device_observation=dict(sentinel="fixture"))))
        self.store.write(self.store.base / "runtime-config.json", {})
        def advance(seconds):
            if stage[0] == 0:
                self.assertFalse((self.store.base / "queries/result.json").exists())
            stage[0] += 1
        with mock.patch.object(backend, "verify_experiment"), mock.patch.object(backend.time, "sleep", side_effect=advance):
            result = api.observe_install(c, p, phone, self.store.base, 8312, {})
        self.assertTrue(result["completed"])
        self.assertEqual(api.downloaded_package.call_count, 2)
        self.assertTrue(self.store.read(self.store.base / "queries/result.json")["start_inputs_verified_before"])

    def full_failure(self):
        store = cli.Store(ROOT)
        return cli.failed_full_prestart(store, "20260927T103556-51500", store.base / "profile-n03-full.json")

    def test_prestart_failure_binds_real_originals_without_repeating_the_transfer(self):
        before = cli.record(ROOT / ".cache/p34-session/runs/20260927T103556-51500/cells/s04/result.json")
        value = self.full_failure()
        self.assertEqual(value["pid"], 30282)
        self.assertEqual(value["previous"]["report"]["summary"]["pid"], 17852)
        self.assertEqual(value["inputs"]["result"], before)
        self.assertEqual(cli.record(before["path"]), before)

    def test_prestart_failure_refuses_observed_transfer_wrong_store_or_unclosed_owner(self):
        store = cli.Store(ROOT)
        out = store.run("20260927T103556-51500")
        read = store.read
        cases = ((out / "cells/s04/result.json", "summary", {}),
                 (out / "prestart-phone/result.json", "capture_directories", 7),
                 (out / "runtime/s04/closed.json", "forced_termination", True))
        for path, key, bad in cases:
            def changed(target):
                value = read(target)
                if Path(target) == path:
                    value[key] = bad
                return value
            with self.subTest(key=key), mock.patch.object(store, "read", side_effect=changed), self.assertRaises(RuntimeError):
                cli.failed_full_prestart(store, out.name, store.base / "profile-n03-full.json")

    def recovery_observation(self, failure):
        value = cli.Store(ROOT).read(Path(failure["inputs"]["prestart"]["path"]))
        value.update(pid=failure["pid"], config=failure["inputs"]["config"])
        return value

    def test_recovery_phone_requires_exact_pid_config_and_B_snapshot(self):
        api, c = self.real_context()
        failure = self.full_failure()
        observed = self.recovery_observation(failure)
        api.recovery_phone(c, observed, failure)
        for key, value in (("pid", 99999), ("config", None), ("remote", "files/p34-observations/other"),
                           ("pid_checked_before_after", False), ("capture_directories", 7)):
            with self.subTest(key=key), self.assertRaises(RuntimeError):
                api.recovery_phone(c, dict(observed, **{key: value}), failure)
        retired = dict(observed, pid=None, config=None, capture_directories=7)
        api.recovery_phone(c, retired, failure, retired=True)
        for bad in (dict(retired, pid=30282), dict(retired, config=observed["config"])):
            with self.assertRaises(RuntimeError):
                api.recovery_phone(c, bad, failure, retired=True)

    def test_recovery_native_requires_fresh_same_generation_full_R_and_Boot(self):
        api, c = self.real_context()
        failure = self.full_failure()
        path = ROOT / ".cache/p34-session/identity/1790506263041433700/mcu/closure.json"
        self.assertEqual(api.recovery_native(c, failure, path), cli.record(path))
        old = copy.deepcopy(failure)
        old["before"]["final_state"]["session"]["next_session_id"] += 1
        with self.assertRaisesRegex(RuntimeError, "generation/terminal changed"):
            api.recovery_native(c, old, path)

    def test_phone_mutation_path_rejects_redirected_ancestry(self):
        c = types.SimpleNamespace(PKG="fixture.pkg")
        root = "/data/user/0/fixture.pkg"
        p = mock.Mock()
        p.command.side_effect = [root, root + "/files/p34-observations/entry"]
        self.assertEqual(backend.checked_phone_path(c, p, "files/p34-observations/entry"),
                         root + "/files/p34-observations/entry")
        p.command.side_effect = [root, "/sdcard/redirected"]
        with self.assertRaisesRegex(RuntimeError, "redirected"):
            backend.checked_phone_path(c, p, "files/p34-observations/entry")
        for path in ("/data/other", "files/../other"):
            with self.assertRaisesRegex(RuntimeError, "App-relative"):
                backend.checked_phone_path(c, p, path)

    def test_idle_abort_sequence_is_not_a_new_generation_but_other_changes_still_fail(self):
        root = cli.Store(ROOT).run("20260927T103556-51500")
        before = self.store.read(root / "cells/s04/mcu/closure.json")["final_state"]
        live = self.store.read(root / "recoveries/1790508884238208300/mcu/samples/recovery-before/state.json")
        self.assertEqual((before["session"]["last_ack_seq"], live["session"]["last_ack_seq"]), (257, 0))
        with self.assertRaises(RuntimeError):
            backend.same_terminal(live, before)
        backend.same_terminal(live, before, idle_abort_sequence=True)
        for group, key, value in (("session", "state", 1), ("session", "last_ack_cmd", 0x81),
                                  ("session", "next_session_id", 3), ("profile", "active", 1),
                                  ("profile_raw", "sha256", "0" * 64)):
            changed = copy.deepcopy(live)
            changed[group][key] = value
            with self.subTest(key=key), self.assertRaises(RuntimeError):
                backend.same_terminal(changed, before, idle_abort_sequence=True)

    def test_recovery_closes_exact_unrecorded_App_and_never_launches_or_deletes(self):
        for changed in (None, "pid", "config", "mcu"):
            api, c = self.real_context()
            failure = self.full_failure()
            observed = self.recovery_observation(failure)
            out = self.store.base / (changed or "valid")
            config_path = "files/p34-experiment.json"
            config = Path(failure["inputs"]["config"]["path"]).read_bytes()
            files = {config_path: config}
            live, commands = [str(failure["pid"])], []
            root = "/data/user/0/" + c.PKG
            if changed == "pid":
                observed["pid"] += 1
            if changed == "config":
                observed["config"] = None
            state = copy.deepcopy(failure["before"]["final_state"])
            state["tick"] += 10000
            if changed == "mcu":
                state["session"]["next_session_id"] += 1
            def command(args, check=True):
                commands.append(args)
                if args[1] == "pidof":
                    return live[0]
                if args[1:3] == ["am", "force-stop"]:
                    live[0] = ""
                    return ""
                if args[3] == "readlink":
                    return root + ("" if args[-1] == "." else "/" + args[-1])
                if args[3] == "mkdir":
                    return ""
                if args[3] == "mv":
                    files[args[-1]] = files.pop(args[-2])
                    return ""
                raise AssertionError("unexpected device command: " + str(args))
            p = types.SimpleNamespace(command=command, file_bytes=lambda pkg, path, limit: files[path])
            phone = types.SimpleNamespace(usb=lambda *args: nullcontext(p),
                exists=lambda p, pkg, path: path in files or path == "files/p34-retired-configs")
            mcu = mock.Mock()
            mcu.sample.return_value = state
            mcu.close.return_value = failure["before"]
            api.phone = lambda *args: phone
            c.environment = lambda: {}
            c.load = lambda name, path: (types.SimpleNamespace(device_lock=nullcontext) if path.name == "repeat_cycle.py"
                                         else types.SimpleNamespace(Mcu=lambda *args: mcu))
            def capture(c, p, phone, destination):
                self.store.write(destination / "result.json", observed)
                return observed
            api.capture = capture
            api.recovery_native = lambda c, failure, path: cli.record(path)
            result = api.recover_prestart(c, out, failure)
            with self.subTest(changed=changed):
                self.assertEqual(result["result"], "PRESTART_RECOVERED" if changed is None else "PRESTART_RECOVERY_FAILED", result)
                self.assertEqual(sum(args[1:3] == ["am", "force-stop"] for args in commands), int(changed is None))
                self.assertFalse(any("rm" in args or "start" in args for args in commands))
                mcu.close.assert_called_once_with(restore=False)
                if changed:
                    self.assertFalse((out / "retire-intent.json").exists())

    def test_explicit_recovery_advances_once_without_replaying_the_old_run(self):
        failed, b = self.store.run("failed-full"), self.store.run("completed-b")
        profile = self.store.base / "profile.json"
        previous = dict(out=b, descriptor={})
        recovery = dict(pointer={"path": "fixture-recovery"}, failure=dict(run=failed.name, previous=previous))
        self.store.write(profile, dict(predecessor={}))
        self.store.write(self.store.base / "current.json", dict(run=failed.name))
        self.store.write(failed / "plan.json", dict(group="n03-full"))
        self.store.write(failed / "runtime/s04/closed.json", dict(worker_exit=1))
        self.store.write(failed / "runtime/network/closed.json", dict(worker_exit=0))
        self.store.write(failed / "cells/s04/health-live.json", dict(health=dict(upgradeStarts=1)))
        self.store.write(failed / "cells/s04/result.json", dict(result="FULL_INSTALL_INCOMPLETE"))
        original = cli.record(failed / "cells/s04/result.json")
        launched = []
        def launch(path, *args):
            launched.append(path.name)
            if path.name == "network":
                self.store.write(path.parent.parent / "live-network.json", {})
        context = types.SimpleNamespace(supervisor=types.SimpleNamespace(owned=types.SimpleNamespace(launch=launch)))
        def prepare(c, out, phone, tests):
            self.store.write(out / "plan.json", dict(group="n03-full", prestart_recovery=recovery["pointer"]))
        api = types.SimpleNamespace(context=lambda out: context, preflight=lambda *args: None,
            inspect=lambda *args: dict(result="APP_INSPECTED"), prepare=prepare, network_ready=lambda *args: None)
        state = dict(result="fixture", network=dict(state="CLOSED"))
        with mock.patch.object(cli, "verify_tests", return_value={}), mock.patch.object(cli, "status", return_value=state), \
                mock.patch.object(cli, "full_predecessor", return_value=previous), \
                mock.patch.object(cli, "prestart_recovery", return_value=recovery), mock.patch.object(cli, "backend", return_value=api) as factory:
            cli.start(self.store, profile, "s04", "n03-full", Path("explicit"))
            factory.assert_called_once()
            factory.reset_mock()
            cli.start(self.store, profile, "s04", "n03-full", Path("explicit"))
            factory.assert_not_called()
        self.assertEqual(launched, ["network", "s04"])
        self.assertNotEqual(self.store.current(), failed.name)
        self.assertEqual(cli.record(original["path"]), original)

    def test_recovery_flag_is_scoped_and_wrong_run_cannot_open_backend(self):
        with self.assertRaisesRegex(RuntimeError, "only valid for start"):
            cli.main(["--root", str(ROOT), "--prestart-recovery", "fixture", "status"])
        with mock.patch.object(cli, "verify_tests", return_value={}), mock.patch.object(cli, "backend") as factory:
            with self.assertRaisesRegex(RuntimeError, "current full group"):
                cli.start(self.store, self.store.base / "unused", "s04", "n03-a", Path("fixture"))
            factory.assert_not_called()

    def profile(self, c, run=2, terminal=0):
        values = dict.fromkeys(c.m.HEADERS, 0)
        values.update(magic=0x50334250, schema=2, size=336, ready=1, run=run, clock_hz=288000000,
                      clock_ok=1, uart_baud_actual=923076, retained_baud=921600, total_len=c.screen["bytes"], terminal=terminal)
        return struct.pack("<84I", *(values[key] for key in c.m.HEADERS), *([0] * 60))

    def test_schema_two_full_END_is_not_ABORT_prefix_or_wrong_generation(self):
        _, c = self.real_context()
        raw = self.profile(c)
        arguments = dict(run=2, baud=921600, total=c.screen["bytes"], layout=c.instrumentation, terminal=0)
        result = c.helper.decode_terminal(c.m, raw, **arguments)
        self.assertEqual(result["schema"], 2)
        self.assertEqual(result["terminal"], 0)
        self.assertIn("not installation success", result["meaning"])
        for index, value in ((1, 1), (2, 288), (4, 1), (11, 1)):
            changed = bytearray(raw)
            struct.pack_into("<I", changed, index * 4, value)
            with self.subTest(index=index), self.assertRaises(RuntimeError):
                c.helper.decode_terminal(c.m, changed, **arguments)
        with self.assertRaises(RuntimeError):
            c.helper.decode_terminal(c.m, raw, **dict(arguments, terminal=2))

    def test_full_zero_proof_requires_complete_original_DATA_not_resume(self):
        text = "\n".join(("OTA_LINK_SAMPLE label=upgrade kind=durable us=1 off=0",
            "OTA_LINK_SAMPLE label=upgrade kind=segment_first_send us=2 off=0 len=128",
            "OTA_LINK_SAMPLE label=upgrade kind=segment_first_send us=3 off=128 len=1"))
        self.assertIn("COMPLETE_DATA", backend.zero_before_data(text, "upgrade", 129)["source"])
        for bad in (text.replace("off=0", "off=4096", 1), text.rsplit("\n", 1)[0], text + "\n" + text.splitlines()[-1]):
            with self.assertRaises(RuntimeError):
                backend.zero_before_data(bad, "upgrade", 129)

    def test_existing_original_full_metrics_are_reused_without_a_device(self):
        path = ROOT / ".cache/p34-session/runs/20260927T085435-69100/analysis/1790500408298299800/observations.log"
        messages = path.read_text(encoding="utf-8")
        value = trace.full_metrics(messages, 290996, "02:00:00:00:00:01")
        self.assertEqual(value["transfer_seconds"], 105.414422)
        self.assertEqual(value["installation_reconnect_seconds"], 63.366035)
        backend.zero_before_data(messages, "upgrade", 290996)
        with self.assertRaises(RuntimeError):
            trace.full_metrics(messages, 290969, "02:00:00:00:00:01")
        with self.assertRaises(RuntimeError):
            trace.full_metrics(messages.replace('"retransmitFrames":0', '"retransmitFrames":1'), 290996, "02:00:00:00:00:01")
        with self.assertRaises(RuntimeError):
            trace.full_metrics(messages.replace("MONO_REBOOT_VERIFIED", "MISSING"), 290996, "02:00:00:00:00:01")

    def test_phase_gate_never_treats_Boot_reset_or_halt_as_App(self):
        self.assertEqual(trace.phase(trace.APP, 0, False), "app")
        self.assertEqual(trace.phase(trace.BOOT, 0, False), "boot")
        self.assertEqual(trace.phase(trace.APP, 1 << 25, False), "reset")
        for args in ((trace.APP, 0, True), (0x90000000, 0, False)):
            with self.assertRaises(RuntimeError):
                trace.phase(*args)

    def test_retained_ring_wrap_and_invalid_layout(self):
        header = b"SEGGER RTT" + bytes(6) + struct.pack("<II", 3, 3)
        desc = struct.pack("<6I", 0, 0x20004000, 16, 2, 13, 0)
        raw = bytes(range(16))
        self.assertEqual(trace.ring_tail(header, desc, raw)[0], bytes((13, 14, 15, 0, 1)))
        for values in ((header[:20], desc, raw), (header, desc, raw[:-1]),
                       (header, struct.pack("<6I", 0, 0x90004000, 16, 2, 13, 0), raw)):
            with self.assertRaises(RuntimeError):
                trace.ring_tail(*values)

    def test_activation_ticks_are_not_reported_as_wall_seconds(self):
        text = "BLEACT: ok apply=321ms stage=456ms vcode=30217\r\n"
        value = trace.apply_timing([text, text], 30217)
        self.assertEqual(value["candidate_apply_ticks_ms"], 321)
        self.assertFalse(value["wall_seconds"])
        for messages in ([text.replace("30217", "30216")], [text, text.replace("321", "322")], ["partial"]):
            with self.assertRaises(RuntimeError):
                trace.apply_timing(messages, 30217)

    def test_boot_interval_requires_two_identity_boundaries_and_monotonic_brackets(self):
        def row(n, phase, version=None):
            return dict(start_ns=n * 1_000_000_000, end_ns=n * 1_000_000_000 + 50_000_000,
                        phase=phase, version=version, initialized=True, confirmed=True)
        values = [row(1, "app", 30215), row(2, "boot"), row(4, "boot"), row(5, "app", 30217)]
        value = trace.boot_interval(values, 30215, 30217)
        self.assertEqual(value["lower_seconds"], 1.95)
        self.assertEqual(value["upper_seconds"], 4.05)
        self.assertFalse(value["outcome_fields_are_per_block_progress"])
        for bad in (values[1:], values[:-1], values[:2] + [row(3, "app", 30215)] + values[2:], list(reversed(values))):
            with self.assertRaises(RuntimeError):
                trace.boot_interval(bad, 30215, 30217)

    def test_trace_readiness_rejects_wrong_epoch_stale_or_closed_owner(self):
        value = trace.Trace(types.SimpleNamespace(checked=lambda path: path), self.store.base, 2)
        value.thread = mock.Mock()
        value.thread.is_alive.return_value = True
        value.ready.set()
        value.start_ready, value.last_sample_ns = True, time.monotonic_ns()
        value.require_ready()
        value.start_ready = False
        with self.assertRaises(RuntimeError):
            value.require_ready()
        value.start_ready, value.last_sample_ns = True, 0
        with self.assertRaises(RuntimeError):
            value.require_ready()
        value.last_sample_ns = time.monotonic_ns()
        value.thread.is_alive.return_value = False
        with self.assertRaises(RuntimeError):
            value.require_ready()

    def test_boot_residency_never_invents_missing_confirmation(self):
        def row(n, phase, version=None):
            return dict(start_ns=n * 1000000000, end_ns=n * 1000000000 + 50000000,
                        phase=phase, version=version, initialized=True, confirmed=False)
        rows = [row(1, "app", 30215), row(2, "boot"), row(4, "boot"), row(5, "app", 30217)]
        with self.assertRaisesRegex(RuntimeError, "CONFIRMED sample missing"):
            trace.boot_interval(rows, 30215, 30217)
        value = trace.boot_interval(rows, 30215, 30217, require_confirmation=False)
        self.assertEqual((value["lower_seconds"], value["upper_seconds"]), (1.95, 4.05))
        self.assertIsNone(value["target_confirmed_bracket_ns"])
        self.assertFalse(value["confirmation_observed"])
        for bad in (rows[1:], rows[:-1], list(reversed(rows)),
                    rows[:2] + [row(3, "app", 30215)] + rows[2:],
                    rows[:-1] + [dict(rows[-1], initialized=False)]):
            with self.assertRaises(RuntimeError):
                trace.boot_interval(bad, 30215, 30217, require_confirmation=False)

    def test_real_full_boot_samples_remain_a_partial_observation_without_replay(self):
        path = ROOT / ".cache/p34-session/runs/20260927T114731-53800/cells/s04/native-trace/samples.jsonl"
        rows = [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines()]
        original = cli.record(path)
        with self.assertRaisesRegex(RuntimeError, "CONFIRMED sample missing"):
            trace.boot_interval(rows, 30215, 30217)
        value = trace.boot_interval(rows, 30215, 30217, require_confirmation=False)
        self.assertLessEqual(value["lower_seconds"], value["upper_seconds"])
        self.assertGreater(value["samples"], 1)
        self.assertFalse(value["confirmation_observed"])
        self.assertEqual(cli.record(path), original)

    def test_trace_joins_before_new_identity_and_prestart_failure_cannot_launch_App(self):
        for broken in (False, True):
            with self.subTest(broken=broken):
                events, path = [], self.store.base / str(broken)
                class FakeTrace:
                    def __init__(self, *args):
                        pass
                    def start(self):
                        events.append("trace start")
                        if broken:
                            raise RuntimeError("trace admission")
                    def stop(self):
                        events.append("trace closed")
                        return {}
                api = object.__new__(backend.Backend)
                api.root, api.group = ROOT, "n03-full"
                phone = types.SimpleNamespace(usb=lambda *args: nullcontext("usb"), network=lambda *args: nullcontext("origin"),
                    release_old=lambda *args: events.append("retire B"), config=lambda *args: {},
                    provision=lambda *args: events.append("launch App") or 123)
                api.phone = lambda *args: phone
                api.install_checkpoint = lambda c, out, before=False: events.append("R closed" if before else "U verified") or dict(path="fixture")
                api.verify_install_checkpoint = lambda *args: None
                api.initial_sample = lambda *args: dict(profile=dict(run=1))
                api.observe_install = lambda *args, **kwargs: events.append("full snapshot") or {}
                api.installed_context = lambda *args: "U"
                api.analyze_install = lambda *args: dict(result="FULL_INSTALL_VERIFIED")
                c = types.SimpleNamespace(load=lambda name, path: types.SimpleNamespace(Trace=FakeTrace, device_lock=lambda: nullcontext()),
                    action=lambda *args, **kwargs: None, save=self.store.write, now=cli.now)
                with mock.patch("builtins.print"):
                    result = api.install_worker(c, path, "s04")
                self.assertEqual(result, int(broken))
                self.assertEqual(events, ["retire B", "R closed", "trace start"] +
                    (["trace closed"] if broken else ["launch App", "full snapshot", "trace closed", "U verified"]))

    def test_actual_reader_and_trace_cross_Boot_without_stale_RTT_writes(self):
        _, c = self.real_context()
        cell = self.store.base / "model"
        self.store.write(cell / "fresh-begin.json", dict(before=dict(profile=dict(run=1))))
        native_history = self.store.raw(cell / "history.ini", b"fixture")
        samples = [0]
        writes = []
        test = self
        class Stop:
            def is_set(self):
                return samples[0] >= 6
            def wait(self, seconds):
                time.sleep(.06)
                samples[0] += 1
        class Evidence:
            NAMES = c.m.Evidence.NAMES
            def __init__(self, out):
                self.out = test.store.checked(out)
                self.out.mkdir(parents=True, exist_ok=True)
                self.events, self.ledger = io.StringIO(), io.StringIO()
            def emit(self, *args, **kwargs):
                pass
        class Link:
            def __init__(self, e, writable):
                self.e, self.opened, self.ram_reads, self.ram_writes = e, False, [], []
                self.sdk = types.SimpleNamespace(JLINKARM_IsHalted=lambda: False)
                self.rd = 0
            def connect(self):
                self.opened = True
            def close(self):
                self.opened = False
            def running(self):
                if samples[0] == 3:
                    raise c.m.passive.Transition("modeled Boot")
            def read(self, address, size):
                index = samples[0]
                current = c.full_assets["target_bindings"]["profile"] if index >= 4 else c.bindings["profile"]
                symbols = current["symbols"]
                words = {trace.DHCSR: 0, trace.VTOR: trace.BOOT if index == 3 else trace.APP,
                    symbols["tick"]: 600 + (index - 4) * 100 if index >= 4 else 1000 + index * 100,
                    symbols["core_clock"]: 288000000, symbols["systick_reload"]: 287999}
                if address in words:
                    return struct.pack("<I", words[address])
                if address == trace.APP:
                    return bytes.fromhex(current["prefix"])[:size]
                if address == symbols["profile"]:
                    return test.profile(c, run=2 if index >= 2 else 1, terminal=0 if index >= 2 else 1)
                layout = c.bindings["layout"]
                if address in (layout["bcb_state"], layout["confirm_done"]):
                    return bytes([4 if address == layout["bcb_state"] else 1])
                first = b"P34PERF: ready run=2 bytes=290969 terminal=0 size=336\r\n"
                tail = b"BLEACT: ok apply=321ms stage=456ms vcode=30217\r\nBLEACT: reset\r\n"
                payload = first + tail if index == 3 else first if index == 2 else b""
                if address == symbols["rtt"]:
                    return (b"SEGGER RTT" + bytes(6) + struct.pack("<II", 3, 3))[:size]
                if address == symbols["rtt"] + 24:
                    return struct.pack("<6I", 0, 0x20004000, 256, len(payload), self.rd if index < 4 else 0, 0)
                if 0x20004000 <= address < 0x20004100:
                    return payload.ljust(256, b"\0")[address - 0x20004000:address - 0x20004000 + size]
                if 0x20001000 <= address <= 0x20001030:
                    return struct.pack("<I", 1000 if address == 0x20001030 else 0)
                raise AssertionError("unexpected native read: " + hex(address))
            def write(self, address, data):
                self.running()
                test.assertEqual(address, c.bindings["profile"]["symbols"]["rtt"] + 40)
                self.rd = struct.unpack("<I", data)[0]
                writes.append((samples[0], address))
        observer = trace.Trace(c, cell / "native-trace", 2)
        observer.stop_requested = Stop()
        with mock.patch.object(c, "native_authority", return_value={}), mock.patch.object(c.m, "Evidence", Evidence), \
                mock.patch.object(c.tune, "ControlLink", Link), mock.patch.object(c.m.c, "MRU", Path(native_history["path"])), \
                mock.patch.object(c.m.ImageReader, "check_dwt", return_value={}):
            observer.run()
        result = self.store.read(cell / "native-trace/result.json")
        self.assertEqual(result["result"], "TRACE_CLOSED", result.get("error"))
        self.assertTrue(result["reader_closed"])
        self.assertEqual([item["version"] for item in result["channels"]], [30215, 30217])
        self.assertEqual([index for index, _ in writes], [2])
        decoded = trace.analyze(c, cell)
        self.assertEqual(decoded["profile"]["terminal"], 0)
        self.assertEqual(decoded["activation"]["candidate_apply_ticks_ms"], 321)
        self.assertIn("upper_seconds", decoded["boot"])
