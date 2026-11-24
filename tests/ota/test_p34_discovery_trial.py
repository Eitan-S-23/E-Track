"""Discovery successor admission and fixed-axis tests; host-only, no device use."""
import copy
import io
import os
from pathlib import Path
import sys
import unittest
from unittest import mock

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "Tools/ota"))
import p34_discovery_trial as f


class Guards(unittest.TestCase):
    def setUp(self):
        self.group = dict(target=dict(sha256="a" * 64), package=dict(bytes=292945, sha256="b" * 64))
        self.config = dict(schema=3, runId="s04", requestedBaud=921600, senderWindowSegments=28,
            reuseGatt=True, withoutResponse=True, transferMode="full", prefixBytes=0,
            rebootInfoTimeoutMs=2000, rebootProbeIntervalMs=500, currentVersionCode=30244,
            targetVersionCode=30245, currentImageSha256=f.RAW_SHA, targetImageSha256="a" * 64,
            packageBytes=292945, packageSha256="b" * 64)

    def test_exact_config(self):
        f.validate_config(self.config, self.group)

    def test_every_axis_rejected_on_drift(self):
        for key, value in self.config.items():
            wrong = dict(self.config)
            wrong[key] = not value if type(value) is bool else value + 1 if type(value) is int else value + "x"
            with self.subTest(key=key), self.assertRaises(RuntimeError):
                f.validate_config(wrong, self.group)

    def test_boolean_not_integer(self):
        self.config["prefixBytes"] = False
        with self.assertRaises(RuntimeError):
            f.validate_config(self.config, self.group)

    def test_old_successor_rejected(self):
        self.config.update(currentVersionCode=30243, targetVersionCode=30244)
        with self.assertRaises(RuntimeError):
            f.validate_config(self.config, self.group)

    def test_receiver_binding_must_match(self):
        api = object.__new__(f.Discovery)
        api.assets = dict(receiver_bindings=dict(version=30244))
        api.proof = dict(descriptor=dict(kind="FULL_INSTALL_VERIFIED"))
        self.assertEqual(api.predecessor(mock.Mock(bindings=dict(version=30244))), api.proof)
        with self.assertRaises(RuntimeError):
            api.predecessor(mock.Mock(bindings=dict(version=30243)))

    def test_completed_old_capture_not_query(self):
        api = object.__new__(f.Discovery)
        with self.assertRaises(RuntimeError):
            api.completed_capture(None, dict(safe_idle=False, stable_completed=True))
        self.assertIsNone(api.completed_capture(None, dict(safe_idle=True)))

    def test_unclean_owner_rejected(self):
        store = mock.Mock()
        for changes in (dict(worker_exit=1), dict(forced_termination=True)):
            store.read.return_value = dict(dict(worker_exit=0, forced_termination=False), **changes)
            with self.assertRaises(RuntimeError):
                f.parent.closed(store, ROOT / ".cache/fake-owner")

    def test_snapshot_failure_still_collects_console(self):
        api, c, p = object.__new__(f.Discovery), mock.Mock(), mock.Mock()
        with mock.patch.object(f.backend.Backend, "finish_install_snapshot", side_effect=RuntimeError("timeout")):
            with self.assertRaises(RuntimeError):
                api.finish_install_snapshot(c, p, None, ROOT / ".cache/fake-cell", 45, "remote", {})
        p.command.assert_called_once_with(["logcat", "-d", "-v", "threadtime", "--pid=45"], timeout=45, binary=True)

    def test_actual_assets_are_legal_header_only_successor(self):
        group = f.load_assets(f.cli.Store(ROOT))
        self.assertEqual(group["target_identity"]["version_code"], 30245)
        self.assertEqual(group["receiver_bindings"]["profile"]["identity"]["version_code"], 30244)

    def test_predecessor_raw_and_boot_gate(self):
        group = f.load_assets(f.cli.Store(ROOT))
        proof = f.predecessor(f.cli.Store(ROOT), group)
        self.assertEqual(proof["descriptor"]["version"], 30244)
        wrong = copy.deepcopy(group)
        wrong["receiver"]["sha256"] = "0" * 64
        with self.assertRaises(RuntimeError):
            f.predecessor(f.cli.Store(ROOT), wrong)

    def test_real_apk_bound_to_both_hosts_and_signer(self):
        report = f.apk(f.cli.Store(ROOT))
        self.assertEqual(report["run"], 36935410469)
        self.assertEqual(report["sha"], f.COMMIT)


if __name__ == "__main__":
    f.cli.require(Path.cwd() == ROOT and sys.flags.isolated and sys.flags.no_site and sys.dont_write_bytecode,
                  "explicit root and isolated Python required")
    s, out = f.cli.Store(ROOT), f.AREA / "tests"
    f.cli.require(not out.exists(), "preserve host tests")
    os.environ.update(f.host.environment(s, out))
    stream = io.StringIO()
    result = unittest.TextTestRunner(stream=stream, verbosity=2).run(unittest.defaultTestLoader.loadTestsFromTestCase(Guards))
    log = s.raw(out / "tests.log", stream.getvalue().encode())
    s.write(out / "result.json", dict(result="PASS" if result.wasSuccessful() else "FAIL", tests=result.testsRun,
        errors=len(result.errors), failures=len(result.failures), log=log,
        source=f.cli.record(f.__file__), test=f.cli.record(__file__), hardware=False))
    print(stream.getvalue(), flush=True)
    sys.exit(not result.wasSuccessful())
