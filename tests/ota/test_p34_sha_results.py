"""Closed-evidence comparison guards, with output captured only in memory."""
import copy
import contextlib
import io
from pathlib import Path
import sys
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "Tools/ota"))
import p34_sha_results as f


class Tests(unittest.TestCase):
    def setUp(self):
        self.store = f.trial.cli.Store(ROOT)
        self.output = ROOT / ".cache/p34-sha-candidate/comparison-tests-unused.json"

    def execute(self):
        with patch.object(self.store, "write") as write, contextlib.redirect_stdout(io.StringIO()):
            f.compare(self.store, self.output)
            self.assertEqual(write.call_count, 1)
            return write.call_args.args[1]

    def test_closed_matrix_keeps_bootstrap_separate(self):
        value = self.execute()
        self.assertFalse(value["samples"]["bootstrap"]["header_only"])
        self.assertFalse(value["causal_speedup_proven"])
        self.assertFalse(value["repeatability_proven"])
        self.assertAlmostEqual(value["installation_reconnect_seconds_saved"], 0.076703)

    def test_unclosed_owner_rejected(self):
        with patch.object(f.previous, "closed", side_effect=RuntimeError("owner live")):
            with self.assertRaises(RuntimeError): self.execute()

    def test_wrong_version_rejected(self):
        api = f.trial.old.old.review
        original = api.load_report
        def changed(store, root):
            pointer, report = original(store, root)
            report = copy.deepcopy(report)
            report["summary"]["input"]["targetVersionCode"] = 1
            return pointer, report
        with patch.object(api, "load_report", side_effect=changed):
            with self.assertRaises(RuntimeError): self.execute()

    def test_changed_boot_rejected(self):
        original = f.trial.assets
        def changed(store, arm):
            value = copy.deepcopy(original(store, arm))
            value["target_bindings"]["whole_boot"] = {"changed": True}
            return value
        with patch.object(f.trial, "assets", side_effect=changed):
            with self.assertRaises(RuntimeError): self.execute()


if __name__ == "__main__":
    cli = f.trial.cli
    cli.require(Path.cwd() == ROOT and sys.flags.isolated and sys.flags.no_site and
                sys.dont_write_bytecode, "explicit isolated root required")
    s = cli.Store(ROOT)
    out = s.checked(Path(sys.argv[1]))
    cli.require(not out.exists(), "preserve tests")
    for name in ("tests.log", "result.json"): s.checked(out / name)
    stream = io.StringIO()
    result = unittest.TextTestRunner(stream=stream, verbosity=2).run(
        unittest.defaultTestLoader.loadTestsFromTestCase(Tests))
    s.raw(out / "tests.log", stream.getvalue().encode())
    s.write(out / "result.json", dict(passed=result.wasSuccessful(), count=result.testsRun,
        source=cli.record(f.__file__), test=cli.record(__file__), device_operations=0))
    print(stream.getvalue())
    sys.exit(not result.wasSuccessful())
