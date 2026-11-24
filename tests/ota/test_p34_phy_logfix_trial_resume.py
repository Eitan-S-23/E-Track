"""Resumed APK binding and preserved predecessor tests, without hardware."""
import io
from pathlib import Path
import sys
import unittest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "Tools/ota"))
import p34_phy_logfix_trial_resume as f


class Guards(unittest.TestCase):
    def test_binding_uses_new_output_and_preserves_original_provenance(self):
        self.assertEqual(f.original.install.OUT, f.install.OUT)
        self.assertNotEqual(f.original.install.OUT, f.install.original.OUT)
        self.assertEqual(f.original.install.original.PRIOR, f.install.original.original.PRIOR)
        f.original.tests(f.cli.Store(ROOT))

    def test_success_and_all_preservation_flags_are_required(self):
        report = dict(apk=dict(sha256=f.install.TARGET_SHA))
        proof = dict(checkpoint={"fixture": True})
        value = dict(result="PHY_LOGFIX_SAME_SIGNER_INSTALLED", usb_closed=True,
            original_invalid_capture_preserved=True, configuration_preserved=True,
            permissions_preserved=True, installed=dict(sha256=f.install.TARGET_SHA),
            retained=proof["checkpoint"], app_launched=False)
        closed = dict(worker_exit=0, forced_termination=False)
        f.validate_installed(report, proof, value, closed)
        for update in (dict(result="NEEDS_PHONE_WAKE_NO_INSTALL_ATTEMPTED"), dict(permissions_preserved=False),
                       dict(original_invalid_capture_preserved=False), dict(installed=dict(sha256="wrong")), dict(retained={})): 
            with self.assertRaises(RuntimeError): f.validate_installed(report, proof, dict(value, **update), closed)
        with self.assertRaises(RuntimeError): f.validate_installed(report, proof, value, dict(closed, forced_termination=True))


if __name__ == "__main__":
    f.cli.require(Path.cwd() == ROOT and sys.flags.isolated and sys.flags.no_site and sys.dont_write_bytecode,
                  "isolated explicit root required")
    s = f.cli.Store(ROOT)
    s.checked(f.HOST)
    f.cli.require(not f.HOST.exists(), "preserve test evidence")
    stream = io.StringIO()
    result = unittest.TextTestRunner(stream=stream, verbosity=2).run(unittest.defaultTestLoader.loadTestsFromTestCase(Guards))
    log = s.raw(f.HOST / "tests.log", stream.getvalue().encode())
    s.write(f.HOST / "result.json", dict(passed=result.wasSuccessful(), count=result.testsRun,
        sources=f.sources(), log=log, hardware=False))
    print(stream.getvalue())
    sys.exit(not result.wasSuccessful())
