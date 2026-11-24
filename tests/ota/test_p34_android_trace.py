"""Host-only native observation and fixed-Y diagnostic admission tests."""
from contextlib import nullcontext
import io
import json
import os
from pathlib import Path
import queue
import sys
import types
import unittest
from unittest import mock
import uuid

ROOT = Path(__file__).resolve().parents[2]
cli = sys.modules["p34_session"]
m = cli.load_module("p34_android_trace_tested", ROOT / "Tools/ota/p34_android_trace.py")
backend = cli.load_module("p34_android_backend_tested", ROOT / "Tools/ota/p34_session_backend.py")
OUTPUT = Path(os.environ["P34_TEST_OUT"])


def line(us, body, *, pid=123, tid=7, level="D"):
    return (f"1790600000.{us:06d} {pid:5d} {tid:5d} {level} [FBP-Android]: [FBP] {body}\n").encode()


def sample():
    return b"".join((line(1, "onMethodCall: writeCharacteristic"),
        line(101, "onCharacteristicWrite:", tid=8), line(102, "  chr: fff2", tid=8),
        line(103, "  status: GATT_SUCCESS (0)", tid=8),
        line(301, "onCharacteristicChanged:", tid=8), line(302, "  chr: fff1", tid=8)))


class MarkerTests(unittest.TestCase):
    def test_query_requires_real_write_and_notification(self):
        value = m.query_gate(sample(), 123)
        self.assertEqual(value["writes"][0]["elapsed_us"], 100)
        self.assertEqual(len(value["notifications_us"]), 1)
        self.assertIn("not durable ACK", value["callback_semantics"])

    def test_empty_or_method_only_cannot_admit(self):
        for raw in (b"", line(1, "onMethodCall: writeCharacteristic")):
            with self.subTest(raw=raw), self.assertRaises(RuntimeError):
                m.query_gate(raw, 123)

    def test_wrong_pid_rejected(self):
        with self.assertRaisesRegex(RuntimeError, "PID"):
            m.query_gate(sample(), 124)

    def test_bad_status_characteristic_and_error_fail(self):
        for before, after in ((b"GATT_SUCCESS (0)", b"GATT_FAILURE (257)"),
                              (b"chr: fff2", b"chr: fff3"), (b"chr: fff1", b"chr: fff4"),
                              (b" D ", b" E ")):
            with self.subTest(after=after), self.assertRaises(RuntimeError):
                m.query_gate(sample().replace(before, after), 123)

    def test_missing_or_overlapping_method_fails(self):
        for raw in (b"\n".join(sample().split(b"\n")[1:]),
                    line(0, "onMethodCall: writeCharacteristic") + sample()):
            with self.subTest(raw=raw), self.assertRaises(RuntimeError):
                m.query_gate(raw, 123)

    def test_backward_clock_rejected(self):
        with self.assertRaisesRegex(RuntimeError, "backwards"):
            m.query_gate(sample() + line(1, "onMethodCall: getAdapterState"), 123)

    def test_clock_precision_and_equal_timestamps(self):
        raw = sample().replace(b".000001", b".000000").replace(b".000101", b".000000")
        self.assertEqual(m.query_gate(raw, 123)["writes"][0]["elapsed_us"], 0)

    def test_partial_tail_cannot_prove_completed_trace(self):
        self.assertEqual(len(m.markers(sample() + b"1790", 123)["writes"]), 1)
        with self.assertRaises(RuntimeError):
            m.markers(sample() + b"1790", 123, complete=True)
        with self.assertRaises(RuntimeError):
            m.markers(sample() + line(303, "onCharacteristicChanged:"), 123, complete=True)

    def test_bad_format_size_and_pid_fail_closed(self):
        for raw, pid in ((b"ADB connection refused\n", 123), (b"\xff", 123), (sample(), True)):
            with self.subTest(pid=pid), self.assertRaises((RuntimeError, UnicodeError)):
                m.query_gate(raw, pid)
        with mock.patch.object(m, "MAX_BYTES", 1), self.assertRaises(RuntimeError):
            m.query_gate(sample(), 123)

    def test_command_has_exact_serial_pid_port_and_no_buffer_clear(self):
        p = types.SimpleNamespace(ADB=Path("adb.exe"), PORT=5062, SERIAL="exact-phone")
        args = m.command(p, 123)
        self.assertEqual(args[:7], ["adb.exe", "-H", "127.0.0.1", "-P", "5062", "-s", "exact-phone"])
        self.assertIn("--pid=123", args)
        self.assertNotIn("-c", args)
        self.assertNotIn("-G", args)
        for pid in (None, "123", -1, 0, True):
            with self.assertRaises(RuntimeError):
                m.command(p, pid)


class Pipe:
    def __init__(self):
        self.q = queue.Queue()
        self.closed = False

    def read1(self, count):
        return self.q.get(timeout=10)

    def close(self):
        self.closed = True


class Process:
    def __init__(self):
        self.stdout, self.returncode = Pipe(), None

    def poll(self):
        return self.returncode

    def terminate(self):
        self.returncode = 1
        self.stdout.q.put(b"")

    def kill(self):
        self.terminate()

    def wait(self, timeout):
        if self.returncode is None:
            raise RuntimeError("fake process was not stopped")
        return self.returncode


class CollectorTests(unittest.TestCase):
    def setUp(self):
        self.store = cli.Store(ROOT)
        self.out = self.store.checked(OUTPUT / "native-fixtures" / uuid.uuid4().hex)
        self.c = types.SimpleNamespace(checked=self.store.checked, save=self.store.write,
            raw=self.store.raw, record=cli.record, now=cli.now, ROOT=ROOT, PKG="diagnostic.app",
            apk=dict(apk=dict(sha256="a" * 64)))
        self.p = types.SimpleNamespace(ADB=Path("adb.exe"), PORT=5062, SERIAL="exact-phone",
            alive=lambda: True, command=lambda args: "123", environment=lambda: {"CONTAINED": "yes"})

    def test_stream_is_owned_exact_bounded_and_closed(self):
        process = Process()
        with mock.patch.object(m.subprocess, "Popen", return_value=process) as popen:
            trace = m.Trace(self.c, self.p, self.out, 123)
            trace.start()
            process.stdout.q.put(sample())
            cli.wait_until(lambda: trace.count == len(sample()), seconds=3)
            proof = trace.admit_queries()
            self.assertEqual(self.store.read(proof["path"])["result"], "NATIVE_QUERY_MARKERS_OBSERVED")
            result = self.store.read(trace.stop()["path"])
        self.assertEqual(result["result"], "NATIVE_LOG_COLLECTED")
        self.assertTrue(result["thread_closed"] and result["host_client_stop_requested"])
        self.assertEqual(popen.call_args.kwargs["cwd"], ROOT)
        self.assertEqual(popen.call_args.kwargs["env"], {"CONTAINED": "yes"})
        self.assertEqual(self.out.joinpath("logcat.txt").read_bytes(), sample())
        self.assertTrue(process.stdout.closed)

    def test_missing_live_pid_never_launches(self):
        self.p.command = lambda args: "124"
        with mock.patch.object(m.subprocess, "Popen") as popen, self.assertRaises(RuntimeError):
            m.Trace(self.c, self.p, self.out, 123).start()
        popen.assert_not_called()

    def test_overflow_keeps_failure_and_closes(self):
        process = Process()
        with mock.patch.object(m.subprocess, "Popen", return_value=process), mock.patch.object(m, "MAX_BYTES", 5):
            trace = m.Trace(self.c, self.p, self.out, 123)
            trace.start()
            process.stdout.q.put(b"too much data")
            cli.wait_until(lambda: trace.error is not None, seconds=3)
            with self.assertRaises(RuntimeError):
                trace.admit_queries()
            self.assertEqual(self.store.read(trace.stop()["path"])["result"], "NATIVE_LOG_FAILED")

    def test_deadline_closes_without_touching_device(self):
        process = Process()
        with mock.patch.object(m.subprocess, "Popen", return_value=process):
            trace = m.Trace(self.c, self.p, self.out, 123)
            trace.start()
            trace._expire()
            self.assertEqual(self.store.read(trace.stop()["path"])["result"], "NATIVE_LOG_FAILED")


class DiagnosticTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.store = cli.Store(ROOT)
        cls.old_path = cls.store.base / "profile-n04-window16.json"
        cls.old = cls.store.read(cls.old_path)
        cls.profile = dict(cls.old, native_diagnostic=True)
        cls.api = backend.Backend(cls.store, cls.old_path, cls.profile, cli.NATIVE_DIAGNOSTIC_GROUP)
        cls.context = cls.api.context(OUTPUT / "diagnostic-context")

    def test_fixed_Y_Z_bytes_and_old_window16_remain_unchanged(self):
        self.assertEqual(cli.cells_for(cli.NATIVE_DIAGNOSTIC_GROUP)["s04"], (921600, 8))
        self.assertEqual(cli.cells_for("n04-window16")["s04"], (921600, 16))
        self.assertEqual((self.context.receiver_version, self.context.target_version), (30221, 30222))
        old = backend.Backend(self.store, self.old_path, self.old, "n04-window16").context(OUTPUT / "old-z-context")
        self.assertEqual((old.screen, old.bindings, old.full_assets["target_bindings"]),
                         (self.context.screen, self.context.bindings, self.context.full_assets["target_bindings"]))

    def test_explicit_profile_and_only_window8_are_required(self):
        with self.assertRaisesRegex(RuntimeError, "flag missing"):
            backend.Backend(self.store, self.old_path, self.old, cli.NATIVE_DIAGNOSTIC_GROUP)
        phone = self.api.phone(self.context, "diagnostic_config_tests")
        self.assertEqual(phone.config(self.context, "s04", 921600, 8, "https://fixture.trycloudflare.com")["senderWindowSegments"], 8)
        with self.assertRaises(RuntimeError):
            phone.config(self.context, "s04", 921600, 16, "https://fixture.trycloudflare.com")

    def test_source_pins_and_readiness_gates_are_bound(self):
        paths = {Path(item["path"]) for item in self.context.sources()}
        self.assertTrue({ROOT / "Tools/ota/p34_android_trace.py", ROOT / "tests/ota/test_p34_android_trace.py"} <= paths)
        self.assertEqual(cli.PREDECESSOR_GROUPS[cli.NATIVE_DIAGNOSTIC_GROUP], "n04-measure")
        self.assertEqual([name for name, prior in cli.PREDECESSOR_GROUPS.items()
                          if prior == cli.NATIVE_DIAGNOSTIC_GROUP], [cli.SPEED16_GROUP])

    def test_quic_profile_reuses_frozen_phone_without_global_subprocess_mutation(self):
        import subprocess
        original = subprocess.Popen
        api = backend.Backend(self.store, self.old_path, dict(self.profile, tunnel_protocol="quic"), cli.NATIVE_DIAGNOSTIC_GROUP)
        before = cli.record(ROOT / ".cache/p34-next/prefix_phone.py")
        phone = api.phone(self.context, "quic_phone_test")
        self.assertIs(subprocess.Popen, original)
        self.assertIsNot(phone.subprocess, subprocess)
        self.assertEqual(cli.record(ROOT / ".cache/p34-next/prefix_phone.py"), before)
        self.assertEqual(phone.config(self.context, "s04", 921600, 8, "https://fixture.trycloudflare.com")["senderWindowSegments"], 8)

    def test_prepare_preserves_old_profile_without_build_or_device(self):
        store = cli.Store(ROOT)
        store.base = store.checked(OUTPUT / "prepare-native" / uuid.uuid4().hex)
        store.write(store.base / "profile-n04-window16.json", self.old)
        previous = dict(descriptor=self.old["predecessor"], report=dict(n04_install_measurement=True))
        with mock.patch.object(store, "current", return_value="Y"), \
             mock.patch.object(cli, "current_full_descriptor", return_value={}), \
             mock.patch.object(cli, "completed_full_predecessor", return_value=previous), \
             mock.patch.object(cli, "backend", side_effect=AssertionError("device/build")):
            result = cli.prepare_diagnostic(store)
            self.assertEqual(result, cli.prepare_diagnostic(store))
            self.assertEqual(store.read(store.base / "profile-n04-window16.json"), self.old)
            self.assertTrue(store.read(result["profile"]["path"])["native_diagnostic"])
            previous["descriptor"] = {}
            with self.assertRaisesRegex(RuntimeError, "different predecessor"):
                cli.prepare_diagnostic(store)


class AdmissionTests(unittest.TestCase):
    def test_worker_starts_android_before_queries_and_closes_both_readers_on_failure(self):
        for fail in (False, True):
            with self.subTest(fail=fail):
                events = []
                store = cli.Store(ROOT)
                out = store.checked(OUTPUT / "native-worker" / uuid.uuid4().hex)
                api = object.__new__(backend.Backend)
                api.root, api.group = ROOT, cli.NATIVE_DIAGNOSTIC_GROUP
                phone = types.SimpleNamespace(usb=lambda *args: nullcontext("usb"),
                    network=lambda *args: nullcontext("https://fixture"),
                    release_old=lambda *args: events.append("retire"), config=lambda *args: {},
                    provision=lambda *args: events.append("launch") or 123)
                api.phone = lambda *args: phone
                api.install_checkpoint = lambda c, out, before=False: events.append("before" if before else "after") or dict(path="fixture")
                api.verify_install_checkpoint = lambda *args: None
                api.initial_sample = lambda *args: dict(profile=dict(run=1))
                api.installed_context = lambda *args: "installed"
                api.analyze_install = lambda *args: dict(result="FULL_INSTALL_VERIFIED")
                def reader(name):
                    return types.SimpleNamespace(process=object(), start=lambda: events.append(name + " start"),
                        stop=lambda: events.append(name + " stop") or {})
                native, android = reader("MCU"), reader("Android")
                def load(name, path):
                    if path.name == "p34_full_trace.py":
                        return types.SimpleNamespace(Trace=lambda *args: native)
                    if path.name == "p34_android_trace.py":
                        return types.SimpleNamespace(Trace=lambda *args: android)
                    return types.SimpleNamespace(device_lock=lambda: nullcontext())
                def observe(*args, **kwargs):
                    self.assertIs(kwargs["observer"], native)
                    self.assertIs(kwargs["android"], android)
                    events.append("observe")
                    if fail:
                        raise RuntimeError("missing markers")
                    return {}
                api.observe_install = observe
                c = types.SimpleNamespace(load=load, action=lambda *args, **kwargs: None, save=store.write, now=cli.now)
                with mock.patch("builtins.print"):
                    self.assertEqual(api.install_worker(c, out, "s04"), int(fail))
                self.assertEqual(events, ["retire", "before", "MCU start", "launch", "Android start",
                                          "observe", "Android stop", "MCU stop"] + ([] if fail else ["after"]))

    def test_native_marker_gate_precedes_ready_and_preserves_failure(self):
        for failure in (False, True):
            with self.subTest(failure=failure):
                store = cli.Store(ROOT)
                out = store.checked(OUTPUT / "native-admission" / uuid.uuid4().hex)
                store.write(out / "runtime-config.json", {})
                api = object.__new__(backend.Backend)
                api.group, api.served_name = cli.NATIVE_DIAGNOSTIC_GROUP, "prefix-n04-window16-full.etu"
                api.launched_capture = lambda *args: "files/p34-observations/fixture"
                api.finish_install_snapshot = mock.Mock(return_value=dict(outcome="completed"))
                healthy = dict(healthy=True, lost=0, error=None, upgradeStarts=0, upgradeEnds=0)
                terminal = dict(healthy, upgradeStarts=1, upgradeEnds=1)
                raw = json.dumps(healthy).encode()
                p = mock.Mock()
                p.command.return_value = str(len(b"package")) + "\n"
                p.file_bytes.side_effect = [raw, b"events", raw, b"package", raw, json.dumps(terminal).encode()]
                p.query.validate.return_value = (dict(successfulQueries=1), b"checkpoint", "messages")
                c = types.SimpleNamespace(save=store.write, raw=store.raw, now=cli.now, cell="s04", PKG="fixture",
                    TARGET="target", target_version=30222, screen_bytes=b"package",
                    envelope=types.SimpleNamespace(MAX_BYTES=1024),
                    apk=dict(metadata=dict(device_observation=dict(sentinel="marker"))))
                native = mock.Mock()
                native.admit_queries.return_value = dict(sha256="verified-query")
                if failure:
                    native.admit_queries.side_effect = RuntimeError("query markers absent")
                phone = types.SimpleNamespace(exists=lambda *args: True)
                with mock.patch.object(backend, "verify_experiment"), mock.patch.object(backend.time, "sleep"):
                    if failure:
                        with self.assertRaisesRegex(RuntimeError, "query markers absent"):
                            api.observe_install(c, p, phone, out, 123, {}, android=native)
                        self.assertFalse((out / "queries/result.json").exists())
                        self.assertNotEqual(store.read(out / "status.json")["result"], "READY_FOR_FULL_INSTALL_START")
                        api.finish_install_snapshot.assert_not_called()
                    else:
                        self.assertEqual(api.observe_install(c, p, phone, out, 123, {}, android=native)["outcome"], "completed")
                        self.assertEqual(store.read(out / "queries/result.json")["android_native"], dict(sha256="verified-query"))
                native.admit_queries.assert_called_once()

    def test_diagnostic_cannot_omit_collector(self):
        api = object.__new__(backend.Backend)
        api.group = cli.NATIVE_DIAGNOSTIC_GROUP
        with self.assertRaisesRegex(RuntimeError, "requires its Android collector"):
            api.observe_install(None, None, None, None, 123, {})


class NetworkTests(unittest.TestCase):
    def test_recovery_command_requires_exact_run_and_cell(self):
        for suffix in ([], ["--run", "failed", "--cell", "s01"]):
            with self.subTest(suffix=suffix), self.assertRaises(RuntimeError):
                cli.main(["--root", str(ROOT), "recover-network", *suffix])
        with mock.patch.object(cli, "recover_network", return_value={}) as recover, mock.patch("builtins.print"):
            cli.main(["--root", str(ROOT), "recover-network", "--run", "failed", "--cell", "s04"])
        self.assertEqual(recover.call_args.args[1], "failed")

    def test_private_protocol_adapter_changes_only_owned_tunnel_not_ADB(self):
        tunnel = str(ROOT / ".cache/worktrees/p3-4-link-stats/.cache/p3-4-single-ota-20260921/bin/cloudflared.exe")
        args = [tunnel, "tunnel", "--no-autoupdate", "--protocol", "http2", "--edge-ip-version", "4",
                "--metrics", "127.0.0.1:0", "--url", "http://127.0.0.1:52482"]
        for command in (args, ["adb.exe", "-P", "5062", "nodaemon", "server"]):
            stream = io.BytesIO()
            original = types.SimpleNamespace(Popen=lambda *a, **k: types.SimpleNamespace(stdin=stream))
            phone = types.SimpleNamespace(subprocess=original)
            backend.tunnel_protocol_adapter(phone, ROOT, "quic")
            self.assertIsNot(phone.subprocess, original)
            process = phone.subprocess.Popen(["launcher"])
            process.stdin.write((json.dumps(command) + "\n").encode())
            result = json.loads(stream.getvalue())
            expected = command.copy()
            if command[0] == tunnel:
                expected[4] = "quic"
            self.assertEqual(result, expected)
            self.assertNotEqual(phone.subprocess.Popen, original.Popen)

    def test_adapter_rejects_changed_tunnel_shape_and_unknown_protocol(self):
        stream = io.BytesIO()
        phone = types.SimpleNamespace(subprocess=types.SimpleNamespace(
            Popen=lambda *a, **k: types.SimpleNamespace(stdin=stream)))
        with self.assertRaises(RuntimeError):
            backend.tunnel_protocol_adapter(phone, ROOT, "udp")
        backend.tunnel_protocol_adapter(phone, ROOT, "quic")
        tunnel = str(ROOT / ".cache/worktrees/p3-4-link-stats/.cache/p3-4-single-ota-20260921/bin/cloudflared.exe")
        with self.assertRaises(RuntimeError):
            phone.subprocess.Popen([]).stdin.write(json.dumps([tunnel, "unexpected"]).encode())
        self.assertEqual(stream.getvalue(), b"")

    def fixture(self):
        store = cli.Store(ROOT)
        store.base = store.checked(OUTPUT / "network-recovery" / uuid.uuid4().hex)
        run = "failed-native-network"
        out = store.run(run)
        profile = store.base / "profile.json"
        store.write(profile, dict(native_diagnostic=True))
        store.write(store.base / "current.json", dict(run=run))
        store.write(out / "plan.json", dict(group=cli.NATIVE_DIAGNOSTIC_GROUP, profile=cli.record(profile), predecessor={}))
        store.write(out / "runtime/network/closed.json", dict(worker_exit=1, forced_termination=False))
        store.write(out / "network-result.json", dict(device_operations=0, detail="tunnel readiness deadline"))
        store.write(out / "network-owner/network/closed.json", dict(listener_closed=True, worker_stopped=True))
        store.raw(out / "network-owner/network/tunnel.log", b'details="HTTP/2 connection is blocked or unreachable" '
            b'status=fail target=region1.v2.argotunnel.com\ndetails="QUIC connection successful"\nsuggested_protocol=quic\n')
        return store, run, out

    def test_no_cell_network_failure_restores_only_completed_host_pointer(self):
        store, run, out = self.fixture()
        before = cli.record(out / "plan.json")
        with mock.patch.object(cli, "verify_tests", return_value={}), \
             mock.patch.object(cli, "completed_full_predecessor", return_value=dict(descriptor=dict(run="Y"))), \
             mock.patch.object(cli, "backend", side_effect=AssertionError("device backend must not run")):
            result = cli.recover_network(store, run)
            self.assertEqual(store.current(), "Y")
            self.assertEqual(store.read(result["profile"]["path"])["tunnel_protocol"], "quic")
            self.assertEqual(cli.record(out / "plan.json"), before)
            self.assertFalse((out / "cells").exists())
            with self.assertRaises(RuntimeError):
                cli.recover_network(store, run)

    def test_gap_read_timeout_recovery_requires_both_served_responses_and_no_cell(self):
        for missing in (None, "download", "cell", "timeout"):
            store, run, out = self.fixture()
            plan = store.read(out / "plan.json")
            store.write(out / "plan.json", dict(plan, group="ack-gap-bootstrap"), replace=True)
            store.write(out / "network-result.json", dict(device_operations=0, error="TimeoutError",
                detail="wrong" if missing == "timeout" else "The read operation timed out"), replace=True)
            with store.checked(out / "network-owner/network/tunnel.log").open("wb") as stream:
                stream.write(b'Registered tunnel connection protocol=quic\n')
            lines = 'GET /api/public/firmware/latest?x -> 200 (1 bytes)\n'
            if missing != "download":
                lines += 'GET /api/public/firmware/download?x -> 200 (2 bytes)\n'
            store.raw(out / "network-owner/network/service.log", lines.encode())
            store.raw(out / "actions.jsonl", b'{"id":"https-readiness","error":"TimeoutError"}\n')
            if missing == "cell":
                store.write(out / "cells/s04/intent.json", {})
            with mock.patch.object(cli, "verify_tests", return_value={}), \
                 mock.patch.object(cli, "completed_full_predecessor", return_value=dict(descriptor=dict(run="old30230"))) as previous, \
                 mock.patch.object(cli, "backend", side_effect=AssertionError("no device backend")):
                if missing is None:
                    cli.recover_network(store, run)
                    self.assertEqual(store.current(), "old30230")
                    self.assertEqual(previous.call_args.kwargs["group"], "receive-pressure")
                else:
                    with self.assertRaises(RuntimeError):
                        cli.recover_network(store, run)
                    previous.assert_not_called()

    def test_recovery_rejects_cell_presence_unclosed_or_undiscriminated_failure(self):
        for kind in ("cell", "closure", "evidence", "profile"):
            store, run, out = self.fixture()
            if kind == "cell":
                store.write(out / "cells/s04/intent.json", {})
            elif kind == "closure":
                store.write(out / "runtime/network/closed.json", dict(worker_exit=1, forced_termination=True), replace=True)
            elif kind == "profile":
                store.write(store.base / "profile.json", dict(changed=True), replace=True)
            else:
                store.write(out / "network-result.json", dict(device_operations=0, detail="unknown failure"), replace=True)
            with self.subTest(kind=kind), mock.patch.object(cli, "verify_tests", return_value={}), \
                 mock.patch.object(cli, "completed_full_predecessor", side_effect=AssertionError("must reject early")), \
                 self.assertRaises(RuntimeError):
                cli.recover_network(store, run)
            self.assertEqual(store.current(), run)
            self.assertFalse((store.base / "network-recovery").exists())


TEST_CLASSES = (MarkerTests, CollectorTests, DiagnosticTests, AdmissionTests, NetworkTests)
