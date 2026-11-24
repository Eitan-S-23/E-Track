from pathlib import Path
import sys
import unittest
from unittest import mock

ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT/'Tools/ota'));sys.path.insert(0,str(ROOT/'tests/boot'))
import test_p34_r2_health as legacy
from recovery_confirm.r2_paired_health import Monitor


class Tests(unittest.TestCase):
    def test_both_images_inherit_all_five_original_fault_and_boundary_tests(self):
        for name in ('r2-a.bin','r2-b.bin'):
            image=(ROOT/'.cache/p34-recovery-sources1'/name).read_bytes()
            with mock.patch.object(legacy,'IMAGE',image),mock.patch.object(legacy.rh,'Monitor',Monitor):
                result=unittest.TestResult()
                unittest.defaultTestLoader.loadTestsFromTestCase(legacy.Tests).run(result)
                self.assertEqual(result.testsRun,5)
                self.assertTrue(result.wasSuccessful(),result.errors+result.failures)

    def test_explicit_version_digest_and_no_eeprom_or_backup_claim(self):
        for name,version in (('r2-a.bin',30276),('r2-b.bin',30277)):
            image=(ROOT/'.cache/p34-recovery-sources1'/name).read_bytes()
            with mock.patch.object(legacy,'IMAGE',image),mock.patch.object(legacy.rh,'Monitor',Monitor):
                _,_,_,monitor=legacy.Tests().make()
                result=monitor.run()
            self.assertEqual(result['version_code'],version)
            self.assertFalse(result['eeprom_observed'])
            self.assertFalse(result['backup_observed'])
            self.assertFalse(result['reset_seen'])

    def test_consumed_reset_and_external_latch_prevent_later_reads(self):
        with mock.patch.object(legacy.rh,'Monitor',Monitor):
            for external in (False,True):
                _,native,_,monitor=legacy.Tests().make('reset' if not external else None)
                if external:monitor.owner=lambda:False
                with self.assertRaises(ValueError):monitor.run()
                if not external:
                    self.assertTrue(monitor.reset_seen)
                    native.memory[legacy.rh.DHCSR]=0
                before=tuple(path.data for path in native.paths)
                with self.assertRaises(ValueError):monitor.run()
                self.assertEqual(tuple(path.data for path in native.paths),before)


if __name__=='__main__':unittest.main()
