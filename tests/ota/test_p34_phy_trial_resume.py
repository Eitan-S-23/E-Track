"""Installation handoff regressions; no physical operations."""
import io
from pathlib import Path
import sys
import unittest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "Tools/ota"))
import p34_phy_trial_resume as f


class Guards(unittest.TestCase):
    def test_success_uses_resumed_receipt(self):
        s = f.cli.Store(ROOT)
        report = f.original.apk(s)
        self.assertEqual(report["apk"]["sha256"], f.install.TARGET_SHA)
        self.assertEqual(f.original.install.OUT.name, "install-002")
        self.assertEqual(s.read(f.install.original.OUT / "result.json")["result"], "NEEDS_PHONE_WAKE_NO_INSTALL_ATTEMPTED")
        self.assertIn(str(f.AREA / "runtime/install-002/closed.json"), [x["path"] for x in f.bindings()])

    def test_unresolved_installation_is_not_admitted(self):
        actual = f.cli.Store(ROOT)
        class Store:
            def __getattr__(self, name): return getattr(actual, name)
            def read(self, path):
                value = actual.read(path)
                return dict(value, permissions_preserved=False) if Path(path) == f.install.OUT / "result.json" else value
        with self.assertRaises(RuntimeError): f.original.apk(Store())


if __name__ == "__main__":
    f.cli.require(Path.cwd() == ROOT and sys.flags.isolated and sys.flags.no_site and sys.dont_write_bytecode,
                  "isolated explicit root required")
    s = f.cli.Store(ROOT)
    s.checked(f.HOST)
    f.cli.require(not f.HOST.exists(), "preserve tests")
    stream = io.StringIO()
    result = unittest.TextTestRunner(stream=stream, verbosity=2).run(unittest.defaultTestLoader.loadTestsFromTestCase(Guards))
    log = s.raw(f.HOST / "tests.log", stream.getvalue().encode())
    s.write(f.HOST / "result.json", dict(result="PASS" if result.wasSuccessful() else "FAIL",
        bindings=f.bindings(), tests=result.testsRun, log=log, hardware=False))
    print(stream.getvalue())
    sys.exit(not result.wasSuccessful())
