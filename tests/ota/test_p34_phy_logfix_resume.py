"""Current no-attempt/wake/output guards; no phone commands or installation."""
import io
import json
from pathlib import Path
import sys
import unittest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "Tools/ota"))
sys.path.insert(0, str(ROOT / "tests/ota"))
import p34_phy_logfix_install_resume as f
import test_p34_phy_logfix_install as prior


class Guards(unittest.TestCase):
    def test_closed_no_attempt_and_distinct_output(self):
        self.assertEqual(len(f.reconciled(f.cli.Store(ROOT))), 4)
        self.assertNotEqual(f.OUT, f.original.OUT)

    def test_mutation_or_uncertain_outcome_prevents_resume(self):
        s = f.cli.Store(ROOT)
        before = s.read(f.original.OUT / "result.json")
        owner = s.read(f.AREA / "runtime/install-001/closed.json")
        usb = s.read(f.original.OUT / "usb/closed.json")
        for change in (dict(result="unknown"), dict(usb_closed=False)):
            with self.assertRaises(RuntimeError):
                f.guards.verify_no_attempt(dict(before, **change), owner, usb, [dict(args=["query"])],
                    install_intent=False, stop_intent=False)
        with self.assertRaises(RuntimeError):
            f.guards.verify_no_attempt(before, owner, usb, [dict(args=["install"])], install_intent=False, stop_intent=False)

    def test_wake_gate_is_read_only_and_bounded(self):
        now, calls, waits = [0], [], []
        states = iter(["mWakefulness=Asleep", "mWakefulness=Awake"])
        def command(args, **kwargs): calls.append(args); return next(states)
        def sleep(seconds): now[0] += seconds
        self.assertEqual(f.guards.awake_power(command, lambda: waits.append(True), clock=lambda: now[0], sleep=sleep),
                         "mWakefulness=Awake")
        self.assertEqual(calls, [["shell", "dumpsys", "power"]] * 2)
        with self.assertRaises(RuntimeError):
            f.guards.awake_power(lambda *a, **k: "mWakefulness=Asleep", lambda: None,
                seconds=3, clock=lambda: now[0], sleep=sleep)


if __name__ == "__main__":
    f.cli.require(Path.cwd() == ROOT and sys.flags.isolated and sys.flags.no_site and sys.dont_write_bytecode,
                  "isolated explicit root required")
    s = f.cli.Store(ROOT)
    s.checked(f.HOST)
    f.cli.require(not f.HOST.exists(), "preserve test evidence")
    # Run the existing real worker-boundary fixtures against the resumed output.
    prior.f = f
    suite = unittest.TestSuite([unittest.defaultTestLoader.loadTestsFromTestCase(Guards),
                               unittest.defaultTestLoader.loadTestsFromTestCase(prior.Guards)])
    stream = io.StringIO()
    result = unittest.TextTestRunner(stream=stream, verbosity=2).run(suite)
    log = s.raw(f.HOST / "tests.log", stream.getvalue().encode())
    s.write(f.HOST / "result.json", dict(passed=result.wasSuccessful(), count=result.testsRun,
        sources=f.sources(), log=log, hardware=False))
    print(stream.getvalue())
    sys.exit(not result.wasSuccessful())
