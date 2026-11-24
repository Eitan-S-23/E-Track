from pathlib import Path
import sys
import unittest
from unittest import mock

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'Tools/ota'))
sys.path.insert(0, str(ROOT / 'tests/boot'))
import p34_boot16_usb as run
from recovery_confirm import boot16_usb_entry as usb
import test_p34_boot16_display as display_tests
import test_p34_boot16_probe as original
from test_p34_boot16_entry import SDK, IMAGE, MAP, Clock, Dap


class Tests(unittest.TestCase):
    def test_exact_suspend_exception_and_negative_words(self):
        self.assertTrue(usb.usb_idle(0x104, 0))
        snapshot = usb.usb_snapshot(0x104, 0)
        self.assertEqual((snapshot['old_connection'], snapshot['device_address'], snapshot['remote_wakeup']), (1, 0, 0))
        self.assertEqual(snapshot['reason'], 'suspended_from_default_exact')
        self.assertFalse(snapshot['physical_disconnect_proven'])
        for connection, bot in ((4, 0), (0x204, 0), (0x304, 0), (0x10104, 0),
                                (0x1000104, 0), (0x104, 7), (0x104, 0x10000), (3, 0), (2, 0)):
            self.assertFalse(usb.usb_idle(connection, bot))
        for connection, bot in ((True, 0), (-1, 0), (0x104, None)):
            with self.assertRaises(ValueError): usb.usb_idle(connection, bot)

    def test_exact_physical_usb_words_rechecked_while_running_and_held(self):
        for changed in (False, True):
            clock = Clock()
            sdk = SDK(clock)
            sdk.memory[usb.prior.USB_CONNECTION] = 0x104
            sdk.memory[usb.prior.USB_BOT] = 0
            c = usb.Control(Dap(sdk), IMAGE, MAP, lambda: True, lambda *a, **k: None,
                clock=clock, sleep=clock.sleep, guard=lambda fn, *a, **k: fn(*a))
            original_write = sdk.JLINKARM_CORESIGHT_WriteAPDPReg
            def write(index, ap, value):
                address = sdk.tar
                result = original_write(index, ap, value)
                if changed and (index, ap, address, value) == (3, 1, usb.prior.COMP, usb.prior.WFI_COMPARATOR):
                    sdk.memory[usb.prior.USB_CONNECTION] = 0x304
                return result
            sdk.JLINKARM_CORESIGHT_WriteAPDPReg = write
            if changed:
                with self.assertRaises(ValueError): c.acquire()
                self.assertFalse(c.release_attempted)
            else:
                c.acquire()
                c.release(lambda: True)
                c.restore_pause_running()

    def test_new_control_with_all_original_native_owner_regressions(self):
        actual = run.core.execute
        def execute(*args, **kwargs): return actual(*args, **kwargs, control_type=usb.Control)
        suite = unittest.defaultTestLoader.loadTestsFromTestCase(original.Tests)
        with mock.patch.object(original.run, 'execute', side_effect=execute):
            result = unittest.TestResult()
            suite.run(result)
        self.assertTrue(result.wasSuccessful(), result.errors+result.failures)
        self.assertEqual(result.testsRun, 5)

    def test_display_completion_storage_and_deadline_regressions_preserved(self):
        suite = unittest.TestSuite(unittest.defaultTestLoader.loadTestsFromName(name, display_tests.Tests)
            for name in ('test_running_and_one_held_completion_then_unchanged_release',
                         'test_stuck_increasing_changed_endpoint_mode_or_reset_never_releases',
                         'test_running_display_does_not_hide_storage_usb_wwdt_or_range_blockers',
                         'test_each_completion_native_call_capped_by_one_second_remaining'))
        with mock.patch.object(display_tests.d, 'Control', usb.Control):
            result = unittest.TestResult()
            suite.run(result)
        self.assertTrue(result.wasSuccessful(), result.errors+result.failures)
        self.assertEqual(result.testsRun, 4)


if __name__ == '__main__': unittest.main()
