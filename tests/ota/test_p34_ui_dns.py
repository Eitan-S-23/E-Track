"""Scoped DNS recovery keeps the same OTA and strict TLS/package verifier."""
from pathlib import Path
import sys
import unittest
from unittest.mock import Mock,patch

ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT/'Tools/ota'))
import p34_ui_dns as m


class Tests(unittest.TestCase):
    def test_actual_failed_network_had_no_device_cell(self):
        records=m.reconciled(m.cli.Store(ROOT))
        self.assertEqual(len(records),4)

    def test_only_measurement_is_allowed(self):
        with self.assertRaises(RuntimeError):m.Scoped(Mock(),'bootstrap')

    def test_verifier_delegates_to_scoped_tls_and_asset_checks(self):
        instance=object.__new__(m.Scoped);context=Mock()
        with patch.object(m.dns,'verify',return_value={'verified':True}) as verify:
            self.assertEqual(instance.verify_served(context,'https://test.trycloudflare.com',proxy=True),{'verified':True})
        verify.assert_called_once_with(instance,context,'https://test.trycloudflare.com')

    def test_integrity_failure_is_not_hidden_or_retried(self):
        instance=object.__new__(m.Scoped)
        with patch.object(m.dns,'verify',side_effect=RuntimeError('package differs')) as verify:
            with self.assertRaisesRegex(RuntimeError,'package differs'):
                instance.verify_served(Mock(),'https://test.trycloudflare.com')
        self.assertEqual(verify.call_count,1)


if __name__=='__main__':
    unittest.main(verbosity=2)
