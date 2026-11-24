"""The reusable read-only adapter binds current originals without changing history."""
import io
from pathlib import Path
import sys
import unittest
from unittest.mock import Mock, patch

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "Tools/ota"))
import p34_link_status as f


class Tests(unittest.TestCase):
    def test_current_closed_trial_and_apk(self):
        s = Mock(); pointer = {"sha256": "report"}; apk = {"path": "apk", "sha256": "actual"}
        s.read.return_value = {"apk": apk}
        report = {"inputs": {"launch": {"path": "launch"}}}
        with patch.object(f.previous.review, "load_report", return_value=(pointer, report)) as load, \
                patch.object(f.cli, "record", return_value=apk):
            self.assertEqual(f.inputs(s, Path("trial")), (pointer, {"apk": apk}))
        load.assert_called_once_with(s, Path("trial"))
        s.read.assert_called_once_with("launch")

    def test_changed_apk_rejected(self):
        s = Mock(); s.read.return_value = {"apk": {"path": "apk", "sha256": "expected"}}
        with patch.object(f.previous.review, "load_report", return_value=({}, {"inputs": {"launch": {"path": "launch"}}})), \
                patch.object(f.cli, "record", return_value={}), self.assertRaises(RuntimeError):
            f.inputs(s, Path("trial"))

    def test_clone_leaves_previous_globals_unchanged(self):
        original = dict(f.previous.worker.__globals__)
        called = Mock()
        with patch.object(f.previous.measure.batch, "clone", return_value=called) as clone:
            store = Mock(); f.worker(store, Path("trial"), Path("out"))
        self.assertEqual(f.previous.worker.__globals__, original)
        self.assertEqual(clone.call_args.kwargs["OUT"], Path("out"))
        self.assertIs(clone.call_args.args[0], f.previous.worker)
        called.assert_called_once_with(store)


if __name__ == "__main__":
    f.cli.require(Path.cwd() == ROOT and sys.flags.isolated and sys.flags.no_site and sys.dont_write_bytecode,
                  "explicit isolated root required")
    s = f.cli.Store(ROOT); out = s.checked(Path(sys.argv[1]))
    f.cli.require(not out.exists(), "preserve tests")
    for name in ("tests.log", "result.json"): s.checked(out / name)
    stream = io.StringIO()
    result = unittest.TextTestRunner(stream=stream, verbosity=2).run(unittest.defaultTestLoader.loadTestsFromTestCase(Tests))
    s.raw(out / "tests.log", stream.getvalue().encode())
    s.write(out / "result.json", dict(result="PASS" if result.wasSuccessful() else "FAIL", tests=result.testsRun,
        source=f.cli.record(f.__file__), test=f.cli.record(__file__), hardware=False))
    print(stream.getvalue()); sys.exit(not result.wasSuccessful())
