"""Offline no-replay and fresh-predecessor guards for the batch12 USB recovery."""
import io
from pathlib import Path
import sys
import unittest
from unittest import mock

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "Tools/ota"))
import p34_batch12_recovery as f


class Guards(unittest.TestCase):
    def args(self):
        return [dict(result="UI_TRIAL_INCOMPLETE", error="RuntimeError", detail=f.MISSING),
                dict(result="WORKER_ERROR", worker_exit=1, forced_termination=False),
                dict(port_closed=True, port=5062, stop_exit=0, server_exit=0, launcher_exit=0,
                     key_before={"sha256": "a" * 64}, key_after={"sha256": "a" * 64}),
                [dict(args=["get-state"], exit=1, stdout="", stdout_bytes=0,
                      stderr="error: device '10ADA4197U001CK' not found\r\n")], False]

    def test_exact_missing_device_failure_admitted(self):
        f.verify_unstarted(*self.args())

    def test_started_device_work_rejected(self):
        values = self.args()
        values[-1] = True
        with self.assertRaises(RuntimeError):
            f.verify_unstarted(*values)

    def test_unresolved_owner_usb_or_different_failure_rejected(self):
        cases = [(0, "detail", "timeout"), (0, "result", "FULL_INSTALL_VERIFIED"),
                 (1, "worker_exit", 0), (1, "forced_termination", True),
                 (2, "port_closed", False), (2, "port", 5037), (2, "stop_exit", 1),
                 (2, "server_exit", 1), (2, "launcher_exit", 1),
                 (2, "key_before", None), (2, "key_after", {"sha256": "b" * 64})]
        for index, key, value in cases:
            args = self.args()
            args[index][key] = value
            with self.subTest(index=index, key=key), self.assertRaises(RuntimeError):
                f.verify_unstarted(*args)

    def test_commands_must_only_be_failed_exact_phone_checks(self):
        cases = [("args", ["install", "x.apk"]), ("args", ["shell", "am", "force-stop", "pkg"]),
                 ("exit", 0), ("stdout", "device"), ("stdout_bytes", 6),
                 ("stderr", "device unauthorized"), ("stderr", "error: device 'OTHER' not found")]
        for key, value in cases:
            args = self.args()
            args[3][0][key] = value
            with self.subTest(key=key, value=value), self.assertRaises(RuntimeError):
                f.verify_unstarted(*args)
        args = self.args()
        args[3] = []
        with self.assertRaises(RuntimeError):
            f.verify_unstarted(*args)

    def test_real_original_outcome_and_source_bindings(self):
        records = f.reconciled(f.cli.Store(ROOT))
        self.assertEqual(len(records), 5)
        self.assertTrue(all(f.cli.record(x["path"]) == x for x in records))

    def test_each_possible_started_marker_rejected(self):
        s = f.cli.Store(ROOT)
        for leaf in ("cells", "prestart-phone", "plan.json", "runtime/network", "runtime/s04", "live-network.json"):
            real = Path.exists
            with mock.patch.object(Path, "exists", lambda p: p == f.FAILED / leaf or real(p)):
                with self.subTest(leaf=leaf), self.assertRaises(RuntimeError):
                    f.reconciled(s)

    def test_candidate_uses_new_control_not_failed_or_prepared_assets(self):
        for arm, root in (("control", f.old.PRIOR), ("batch12", f.TRIALS / "control")):
            spy = mock.Mock(return_value="verified")
            with mock.patch.object(f.old.batch, "clone", return_value=spy) as clone:
                self.assertEqual(f.predecessor("store", arm, "group"), "verified")
            self.assertEqual(clone.call_args.kwargs, dict(ORDER=(root.name, "next"), TRIALS=root.parent))
            spy.assert_called_once_with("store", "next", "group")
        with self.assertRaises(RuntimeError):
            f.predecessor(None, "repeat", None)

    def test_trial_injects_only_fresh_predecessor(self):
        target = object.__new__(f.Trial)
        spy = mock.Mock()
        with mock.patch.object(f, "reconciled"), mock.patch.object(f.old.batch, "clone", return_value=spy) as clone:
            target.__init__("store", "batch12")
        clone.assert_called_once_with(f.old.Trial.__init__, predecessor=f.predecessor)
        spy.assert_called_once_with(target, "store", "batch12")

    def test_archive_reuses_original_worker_but_new_control_lineage(self):
        with self.assertRaises(RuntimeError):
            f.archive(None, None, "control", False)
        spy = mock.Mock()
        with mock.patch.object(f, "reconciled"), mock.patch.object(f.old.batch, "clone", return_value=spy) as clone:
            f.archive("store", "owner", "batch12", False)
        clone.assert_called_once_with(f.old.archive, TRIALS=f.TRIALS, __file__=f.__file__)
        spy.assert_called_once_with("store", "owner", "batch12", False)


if __name__ == "__main__":
    f.cli.require(Path.cwd() == ROOT and sys.flags.isolated and sys.flags.no_site and sys.dont_write_bytecode,
                  "isolated explicit root required")
    s = f.cli.Store(ROOT)
    s.checked(f.HOST)
    f.cli.require(not f.HOST.exists(), "preserve recovery tests")
    stream = io.StringIO()
    result = unittest.TextTestRunner(stream=stream, verbosity=2).run(unittest.defaultTestLoader.loadTestsFromTestCase(Guards))
    log = s.raw(f.HOST / "tests.log", stream.getvalue().encode())
    s.write(f.HOST / "result.json", dict(result="PASS" if result.wasSuccessful() else "FAIL", tests=result.testsRun,
        source=f.cli.record(f.__file__), test=f.cli.record(__file__), log=log, hardware=False))
    print(stream.getvalue())
    sys.exit(not result.wasSuccessful())
