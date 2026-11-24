"""Host regression for the old-USB binding and passive recovery adapters."""
import inspect
from pathlib import Path
import runpy
import unittest

SELF = Path(__file__).resolve()
subject = runpy.run_path(str(SELF.with_name("baud_advance.py")), run_name="advance_subject")
front, recovery = subject["runtime"]()


class Cases(unittest.TestCase):
    def test_current_private_usb_route(self):
        self.assertEqual(recovery.PHONE, front.PHONE)
        self.assertEqual(recovery.PHONE.name, "phone-r3")
        self.assertEqual(recovery.phone().RUNTIME, front.PHONE)

    def test_new_cell_uses_same_foreground_sender(self):
        self.assertIs(recovery.start, front.start)
        self.assertIs(recovery.start.__globals__["m"], front.m)

    def test_original_restore_expectation_preserved(self):
        restore = recovery.load("advance_test_restore", SELF.with_name("baud_restore.py"))
        prepared = recovery.read(recovery.b.OUT/"recovery/result.json")
        self.assertEqual(restore.expectation(), prepared["expected"])
        for field in ("baseline", "target"):
            self.assertEqual(restore.expectation()["group"][field], front.m.verified_assets()["groups"]["screen"][field])

    def test_native_recovery_reader_preserves_mutation_guards(self):
        restore = recovery.load("advance_test_reader", SELF.with_name("baud_restore.py"))
        helper = restore.load("advance_test_helper", front.b.ROOT/".cache/p34-restore-20260922/restore_device.py")
        original = helper.Link.__bases__[0]
        self.assertEqual(helper.c.host_presence.__name__, "native_presence")
        self.assertEqual(restore.m.c.host_presence.__name__, "native_presence")
        self.assertIs(helper.Link.publish_command, original.publish_command)
        self.assertIs(helper.Link.write, original.write)
        self.assertIs(helper.Link.running, original.running)
        self.assertIn("disable_cache", inspect.getclosurevars(helper.Link.connect).globals)

    def test_failed_or_final_predecessor_rejected(self):
        for run in ("baud-115200-r6", "baud-921600"):
            with self.subTest(run=run), self.assertRaisesRegex(RuntimeError, "finite"):
                subject["admit"](front, run)

    def test_real_completed_cell_admitted_without_io(self):
        result = subject["admit"](front, "baud-115200-f1")
        self.assertEqual(result, front.b.record(front.cell("baud-115200-f1")/"completed.json"))


if __name__ == "__main__":
    front.b.require(Path.cwd() == front.b.ROOT, "explicit root required")
    path = front.b.checked(front.b.OUT/"foreground/advance-host-tests-001/result.json")
    front.b.require(not path.exists(), "preserve original tests")
    result = unittest.TextTestRunner(verbosity=2).run(unittest.defaultTestLoader.loadTestsFromTestCase(Cases))
    front.save(path, dict(passed=result.wasSuccessful(), tests=result.testsRun, errors=len(result.errors),
               failures=len(result.failures), hardware=False, source=front.b.record(SELF.with_name("baud_advance.py")),
               parent=front.b.record(SELF.with_name("baud_foreground.py")), test_source=front.b.record(SELF),
               sources=front.sources()))
    raise SystemExit(0 if result.wasSuccessful() else 1)
