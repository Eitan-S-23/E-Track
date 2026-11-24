"""Result reconciliation is offline and separates bootstrap from measurement."""
from pathlib import Path
import sys
import unittest
from unittest.mock import Mock, patch

ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT/'Tools/ota'))
import p34_ui_result as m


def report(speed=20,transfer=15,reconnect=25,target=30254):
    return dict(summary=dict(input=dict(targetVersionCode=target)),
                full_metrics=dict(throughput_kib_s=speed,transfer_seconds=transfer,
                                  installation_reconnect_seconds=reconnect))


class Tests(unittest.TestCase):
    def test_dns_route_is_separate_from_failed_main_route(self):
        self.assertEqual(m.trial_root('dns'),m.trial.AREA/'trials-dns')
        self.assertNotEqual(m.trial_root('dns'),m.trial_root('main'))
        with self.assertRaises(RuntimeError):m.trial_root('other')

    def test_closed_requires_all_three_normal_owners(self):
        store=Mock();store.read.return_value=dict(worker_exit=0,forced_termination=False)
        m.closed(store,Path('unused'))
        self.assertEqual(store.read.call_count,3)
        for value in (dict(worker_exit=1,forced_termination=False),dict(worker_exit=0,forced_termination=True)):
            store.read.return_value=value
            with self.assertRaises(RuntimeError):m.closed(store,Path('unused'))

    def test_bootstrap_is_not_a_cadence_measurement(self):
        s=Mock()
        with patch.object(m,'closed'), \
             patch.object(m.review,'load_report',return_value=({},report(target=30253))):
            m.worker(s,'bootstrap')
        value=s.write.call_args.args[1]
        self.assertFalse(value['cadence_effect_measured'])
        self.assertNotIn('transfer_speed_change_percent',value)
        self.assertTrue(value['no_device_operations'])

    def test_measurement_reports_both_targets_without_mixing_best_cases(self):
        s=Mock()
        with patch.object(m,'closed'), \
             patch.object(m.review,'load_report',side_effect=[({},report()),({},report(10,30,20))]):
            m.worker(s,'measure')
        value=s.write.call_args.args[1]
        self.assertAlmostEqual(value['transfer_speed_change_percent'],100)
        self.assertEqual(value['reconnect_seconds_saved'],-5)
        self.assertFalse(value['targets_met'])

    def test_partial_install_never_becomes_full_verdict(self):
        s=Mock()
        with patch.object(m,'closed'),patch.object(m.review,'load_report',side_effect=RuntimeError('partial report')),self.assertRaises(RuntimeError):
            m.worker(s,'bootstrap')
        s.write.assert_not_called()

    def test_wrong_cell_report_rejected(self):
        s=Mock()
        with patch.object(m,'closed'),patch.object(m.review,'load_report',return_value=({},report())),self.assertRaises(RuntimeError):
            m.worker(s,'bootstrap')
        s.write.assert_not_called()


if __name__=='__main__':
    unittest.main(verbosity=2)
