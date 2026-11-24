"""No-attempt recovery guards; no phone or CI operations."""
import copy
import io
import json
from pathlib import Path
import sys
import unittest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "Tools/ota"))
import p34_batch12_install_resume as f


class Guards(unittest.TestCase):
    def setUp(self):
        self.s = f.cli.Store(ROOT)
        self.values = [self.s.read(p) for p in (f.BEFORE / "result.json",
            f.AREA / "runtime/install-001/closed.json", f.BEFORE / "usb/closed.json")]
        self.commands = [json.loads(x) for x in (f.BEFORE / "usb/commands.jsonl").read_text().splitlines()]

    def check(self, values=None, commands=None, **flags):
        return f.verify_no_attempt(*(self.values if values is None else values),
            self.commands if commands is None else commands,
            install_intent=flags.get("install_intent", False), stop_intent=flags.get("stop_intent", False))

    def test_original_no_attempt_receipts(self):
        self.assertEqual(len(f.reconciled(self.s)), 8)
        self.check()

    def test_other_outcome_rejected(self):
        for outcome in ("BATCH_INSTALL_INCOMPLETE", "FIXED_SIGNER_BATCH_UPDATE_VERIFIED", "unknown"):
            values = copy.deepcopy(self.values)
            values[0]["result"] = outcome
            with self.assertRaises(RuntimeError): self.check(values)

    def test_mutation_or_empty_journal_rejected(self):
        for command in (["install", "-r", "candidate.apk"], ["uninstall", f.trial.PKG],
                        ["shell", "am", "force-stop", f.trial.PKG], ["shell", "pm", "clear", f.trial.PKG]):
            with self.assertRaises(RuntimeError): self.check(commands=self.commands + [dict(args=command)])
        with self.assertRaises(RuntimeError): self.check(commands=[])

    def test_mutation_intent_rejected(self):
        for name in ("install_intent", "stop_intent"):
            with self.assertRaises(RuntimeError): self.check(**{name: True})

    def test_unresolved_closure_rejected(self):
        for index, key, value in ((1, "worker_exit", 1), (1, "forced_termination", True),
                                  (2, "port_closed", False), (2, "server_exit", 1), (2, "key_after", {})):
            values = copy.deepcopy(self.values)
            values[index][key] = value
            with self.assertRaises(RuntimeError): self.check(values)

    def test_trial_success_points_to_resumed_attempt(self):
        self.assertEqual(f.trial.INSTALL, f.OUT)
        self.assertNotEqual(f.BEFORE, f.OUT)
        self.assertEqual(f.TARGET_SHA, "a48549082f74a234d5acf0affdfa0d4120f2099fffefa8a40dc0302cac444387")

    def test_wake_gate_is_armed_before_user_action(self):
        now, calls, announced = [0], [], []
        values = iter(["mWakefulness=Asleep\n", "mWakefulness=Awake\n"])
        def command(args, **kwargs):
            calls.append((args, kwargs))
            return next(values)
        def sleep(n): now[0] += n
        value = f.awake_power(command, lambda: announced.append(True), clock=lambda: now[0], sleep=sleep)
        self.assertEqual(value, "mWakefulness=Awake\n")
        self.assertEqual(announced, [True])
        self.assertEqual([x[0] for x in calls], [["shell", "dumpsys", "power"]] * 2)

    def test_already_awake_needs_no_wait(self):
        self.assertEqual(f.awake_power(lambda *a, **k: "mWakefulness=Awake\n",
            lambda: self.fail("already awake")), "mWakefulness=Awake\n")

    def test_wake_timeout_never_installs_or_changes_settings(self):
        now, calls = [0], []
        def command(args, **kwargs):
            calls.append(args)
            return "mWakefulness=Asleep\n"
        def sleep(n): now[0] += n
        with self.assertRaises(RuntimeError):
            f.awake_power(command, lambda: None, seconds=6, clock=lambda: now[0], sleep=sleep)
        self.assertEqual(calls, [["shell", "dumpsys", "power"]] * 2)

    def test_unknown_power_and_unbounded_wait_rejected(self):
        with self.assertRaises(RuntimeError):
            f.awake_power(lambda *a, **k: "unknown", lambda: None)
        for n in (True, 0, 181, 1.5):
            with self.assertRaises(RuntimeError):
                f.awake_power(lambda *a, **k: self.fail("invalid budget"), lambda: None, seconds=n)


if __name__ == "__main__":
    f.cli.require(Path.cwd() == ROOT and sys.flags.isolated and sys.flags.no_site and sys.dont_write_bytecode,
                  "isolated explicit root required")
    s = f.cli.Store(ROOT)
    s.checked(f.HOST)
    f.cli.require(not f.HOST.exists(), "preserve test output")
    stream = io.StringIO()
    result = unittest.TextTestRunner(stream=stream, verbosity=2).run(unittest.defaultTestLoader.loadTestsFromTestCase(Guards))
    log = s.raw(f.HOST / "tests.log", stream.getvalue().encode())
    s.write(f.HOST / "result.json", dict(result="PASS" if result.wasSuccessful() else "FAIL", tests=result.testsRun,
        source=f.cli.record(f.__file__), test=f.cli.record(__file__), log=log, hardware=False))
    print(stream.getvalue())
    sys.exit(not result.wasSuccessful())
