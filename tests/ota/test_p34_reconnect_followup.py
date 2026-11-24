"""Offline guards for the reconciled-timeout successor, no device operations."""
import copy
import io
import os
from pathlib import Path
import sys
import unittest
from unittest import mock

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "Tools/ota"))
import p34_reconnect_followup as f


class Guards(unittest.TestCase):
    def setUp(self):
        self.summary = dict(outcome="not-completed", input=dict(currentVersionCode=30242,
            targetVersionCode=30243, targetImageSha256=f.RAW_SHA, packageBytes=293079))
        self.transfer = dict(outcome="ok", elapsedUs=51714236, durable=dict(finalOff=293079))
        identities = dict(app=dict(sha256=f.RAW_SHA, bytes=616540), boot=dict(sha256=f.BOOT_SHA, bytes=65536))
        self.closure = dict(retained_verified=True, reader_closed=True, no_reset=True, no_halt=True,
            no_flash=True, no_nvic_write=True, initial_identity=copy.deepcopy(identities),
            final_identity=copy.deepcopy(identities), final_state=dict(bcb_state=4, confirm_done=1,
                state_snapped=1, sd_ready=1))
        self.query = dict(successfulQueries=1, pid=17018,
            captureId="1790886478814858-966a83c7a649c78702af5243")
        self.identities = ["addr=02:00:00:00:00:01 result=ok wire=E-Track model=e-track-at32f435 "
            "vcode=30243 hw=1 layout=1 boot=1 proto=1 window=32 sha=" + f.RAW_SHA]

    def validate(self):
        f.validate_reconciliation(self.summary, self.transfer, self.closure, self.query, self.identities)

    def test_reconciled_failure_is_not_success(self):
        self.validate()
        self.assertEqual(self.summary["outcome"], "not-completed")

    def test_reject_relabelled_history(self):
        self.summary["outcome"] = "completed"
        with self.assertRaisesRegex(RuntimeError, "original failed"):
            self.validate()

    def test_reject_partial_transfer(self):
        self.transfer["durable"]["finalOff"] -= 1
        with self.assertRaisesRegex(RuntimeError, "durable END"):
            self.validate()

    def test_reject_wrong_current_version(self):
        self.summary["input"]["targetVersionCode"] = 30343
        with self.assertRaises(RuntimeError):
            self.validate()

    def test_reject_changed_raw_images(self):
        for phase in ("initial_identity", "final_identity"):
            for key in ("app", "boot"):
                with self.subTest(phase=phase, image=key):
                    old = self.closure[phase][key]["sha256"]
                    self.closure[phase][key]["sha256"] = "0" * 64
                    with self.assertRaisesRegex(RuntimeError, "raw App/Boot"):
                        self.validate()
                    self.closure[phase][key]["sha256"] = old

    def test_reject_unconfirmed_or_unready(self):
        for key in ("bcb_state", "confirm_done", "state_snapped", "sd_ready"):
            old = self.closure["final_state"][key]
            self.closure["final_state"][key] = 0
            with self.subTest(key=key), self.assertRaisesRegex(RuntimeError, "confirmation"):
                self.validate()
            self.closure["final_state"][key] = old

    def test_reject_unclean_native_closure(self):
        self.closure["reader_closed"] = False
        with self.assertRaisesRegex(RuntimeError, "checkpoint"):
            self.validate()

    def test_reject_query_from_wrong_process(self):
        self.query["pid"] = 17127
        with self.assertRaisesRegex(RuntimeError, "query evidence"):
            self.validate()

    def test_reject_query_without_raw_identity(self):
        self.identities = []
        with self.assertRaisesRegex(RuntimeError, "App-origin"):
            self.validate()

    def test_reject_forced_worker_exit(self):
        store = mock.Mock()
        store.read.return_value = dict(worker_exit=0, forced_termination=True)
        with self.assertRaisesRegex(RuntimeError, "close normally"):
            f.closed(store, ROOT / ".cache/fake-owner")

    def test_fixed_axes_and_all_identity_fields(self):
        assets = dict(target=dict(sha256="a" * 64), package=dict(bytes=293081, sha256="b" * 64))
        config = dict(schema=3, runId="s04", requestedBaud=921600, senderWindowSegments=28,
            reuseGatt=True, withoutResponse=True, transferMode="full", prefixBytes=0,
            rebootInfoTimeoutMs=2000, rebootProbeIntervalMs=500, currentVersionCode=30243,
            targetVersionCode=30244, currentImageSha256=f.RAW_SHA, targetImageSha256="a" * 64,
            packageBytes=293081, packageSha256="b" * 64)
        f.validate_config(config, assets)
        for key, value in config.items():
            wrong = copy.deepcopy(config)
            wrong[key] = not value if type(value) is bool else value + 1 if type(value) is int else value + "x"
            with self.subTest(key=key), self.assertRaises(RuntimeError):
                f.validate_config(wrong, assets)
        config["prefixBytes"] = False
        with self.assertRaises(RuntimeError):
            f.validate_config(config, assets)

    def test_terminal_app_not_silently_retired(self):
        api = object.__new__(f.Followup)
        with self.assertRaisesRegex(RuntimeError, "idle query-only"):
            api.completed_capture(None, dict(safe_idle=False, stable_terminal=True))
        self.assertIsNone(api.completed_capture(None, dict(safe_idle=True)))

    def test_wrong_receiver_not_admitted(self):
        api = object.__new__(f.Followup)
        api.assets = dict(receiver_bindings=dict(version=30243))
        with self.assertRaisesRegex(RuntimeError, "wrong reconciled receiver"):
            api.predecessor(mock.Mock(bindings=dict(version=30242)))

    def test_full_log_retrieved_even_after_snapshot_failure(self):
        api = object.__new__(f.Followup)
        c, p = mock.Mock(), mock.Mock()
        with mock.patch.object(f.backend.Backend, "finish_install_snapshot", side_effect=RuntimeError("timeout")):
            with self.assertRaisesRegex(RuntimeError, "timeout"):
                api.finish_install_snapshot(c, p, None, ROOT / ".cache/fake-cell", 123, "remote", {})
        p.command.assert_called_once_with(["logcat", "-d", "-v", "threadtime", "--pid=123"], timeout=45, binary=True)
        c.raw.assert_called_once()


if __name__ == "__main__":
    f.cli.require(Path.cwd() == ROOT and sys.flags.isolated and sys.flags.no_site and sys.dont_write_bytecode,
                  "explicit root and isolated Python required")
    s = f.cli.Store(ROOT)
    out = f.AREA / "tests"
    f.cli.require(not out.exists(), "preserve self-test evidence")
    os.environ.update(f.host.environment(s, out))
    stream = io.StringIO()
    result = unittest.TextTestRunner(stream=stream, verbosity=2).run(unittest.defaultTestLoader.loadTestsFromTestCase(Guards))
    log = s.raw(out / "tests.log", stream.getvalue().encode())
    s.write(out / "result.json", dict(result="PASS" if result.wasSuccessful() else "FAIL",
        tests=result.testsRun, errors=len(result.errors), failures=len(result.failures), log=log,
        source=f.cli.record(f.__file__), test=f.cli.record(__file__), hardware=False))
    print(stream.getvalue())
    sys.exit(not result.wasSuccessful())
