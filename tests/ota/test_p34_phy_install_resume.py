"""No-attempt and bounded wake guards for the current PHY APK resume."""
import copy
import io
from pathlib import Path
import sys
import unittest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "Tools/ota"))
import p34_phy_install_resume as f


class Guards(unittest.TestCase):
    def test_original_no_attempt_is_closed(self):
        self.assertEqual(len(f.reconciled(f.cli.Store(ROOT))), 4)
        self.assertNotEqual(f.OUT, f.original.OUT)

    def test_mutation_and_unknown_outcome_are_rejected(self):
        s = f.cli.Store(ROOT)
        before = s.read(f.original.OUT / "result.json")
        owner = s.read(f.AREA / "runtime/install-001/closed.json")
        usb = s.read(f.original.OUT / "usb/closed.json")
        for value in (dict(before, result="unknown"), dict(before, usb_closed=False)):
            with self.assertRaises(RuntimeError):
                f.guards.verify_no_attempt(value, owner, usb, [dict(args=["query"])], install_intent=False, stop_intent=False)
        with self.assertRaises(RuntimeError):
            f.guards.verify_no_attempt(before, owner, usb, [dict(args=["install"])], install_intent=False, stop_intent=False)

    def test_wake_wait_only_reads(self):
        now, calls, waits = [0], [], []
        states = iter(["mWakefulness=Asleep", "mWakefulness=Awake"])
        def command(args, **kwargs): calls.append(args); return next(states)
        def sleep(seconds): now[0] += seconds
        self.assertEqual(f.guards.awake_power(command, lambda: waits.append(True), clock=lambda: now[0], sleep=sleep), "mWakefulness=Awake")
        self.assertEqual(calls, [["shell", "dumpsys", "power"]] * 2)
        self.assertEqual(waits, [True])


if __name__ == "__main__":
    f.cli.require(Path.cwd() == ROOT and sys.flags.isolated and sys.flags.no_site and sys.dont_write_bytecode,
                  "explicit isolated root required")
    s = f.cli.Store(ROOT)
    s.checked(f.HOST)
    f.cli.require(not f.HOST.exists(), "preserve tests")
    stream = io.StringIO()
    result = unittest.TextTestRunner(stream=stream, verbosity=2).run(unittest.defaultTestLoader.loadTestsFromTestCase(Guards))
    log = s.raw(f.HOST / "tests.log", stream.getvalue().encode())
    s.write(f.HOST / "result.json", dict(result="PASS" if result.wasSuccessful() else "FAIL",
        sources=f.sources(), tests=result.testsRun, log=log, hardware=False))
    print(stream.getvalue())
    sys.exit(not result.wasSuccessful())
