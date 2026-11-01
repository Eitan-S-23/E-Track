"""Synthetic tests of the opt-in, bounded startup property owner."""
from collections import deque
import copy
from types import SimpleNamespace
import unittest
from unittest.mock import patch

import runner as r
from test_runner import plan, state


class StartupLoggingTests(unittest.TestCase):
    def driver(self, policy=True):
        clock = patch.object(r.time, 'monotonic', return_value=100)
        clock.start()
        self.addCleanup(clock.stop)
        d = object.__new__(r.Android)
        d.p = plan()
        d.p['preparation'] = {'startup_log_tag': dict(before='M', during='V', seconds=300)} if policy else {}
        d.preparation = SimpleNamespace(total=1000, stage_deadline=900,
            phone=SimpleNamespace(operation_deadline=900), cmd=lambda *args, **kwargs: b'')
        d.total_deadline = 1100
        d.log_tag_touched = d.log_tag_restore_attempted = False
        d.log_tag_started = d.log_tag_saved_deadlines = None
        d.recorded, d.calls = [], []
        d.record = lambda event, **kw: d.recorded.append(dict(event=event, **kw))
        d.value, d.fail_write, d.fail_readback = 'M', None, False

        def command(args, seconds=5):
            self.assertEqual(seconds, 5)
            d.calls.append(args)
            if args[:2] == ['shell', 'getprop']:
                return (d.value + '\n').encode()
            self.assertEqual(args[:3], ['shell', 'setprop', 'log.tag'])
            d.value = args[-1]
            if d.fail_write == args[-1]:
                raise OSError('lost mutation reply')
            if d.fail_readback and args[-1] == 'M':
                d.value = 'V'
            return b''

        d.cmd = command
        return d

    def test_configuration_is_narrow_and_explicit(self):
        p = self.driver().p
        self.assertIs(r.validate_plan(p), p)
        for candidate in (True, {}, dict(before='', during='V', seconds=300),
                dict(before='M', during='D', seconds=300), dict(before='M', during='V', seconds=True),
                dict(before='M', during='V', seconds=301), dict(before='M', during='V', seconds=300, property='other')):
            bad = copy.deepcopy(p)
            bad['preparation']['startup_log_tag'] = candidate
            with self.subTest(candidate=candidate), self.assertRaises(r.Stop):
                r.validate_plan(bad)

    def test_default_never_reads_or_changes_a_property(self):
        d = self.driver(False)
        d.prepare_startup_logging()
        d.restore_startup_logging()
        d.finish_startup_logging()
        self.assertEqual(d.calls, [])

    def test_qualified_info_baseline_is_opt_in_and_never_owned_or_restored(self):
        d = self.driver()
        d.value = 'I'
        with self.assertRaises(r.Stop):
            d.prepare_startup_logging()
        d.p['preparation']['startup_log_tag']['allow_info_baseline'] = True
        r.validate_plan(d.p)
        d.prepare_startup_logging()
        d.value = 'M'  # An untouched setting is not this driver's restoration.
        d.restore_startup_logging()
        d.finish_startup_logging()
        self.assertFalse(d.log_tag_touched)
        self.assertIsNone(d.log_tag_started)
        self.assertEqual((d.preparation.total, d.total_deadline), (1000, 1100))
        self.assertFalse(any(c[1] == 'setprop' for c in d.calls))
        self.assertEqual(d.recorded[-1]['event'], 'startup-log-tag-not-needed')

    def test_info_option_does_not_allow_other_baselines_or_non_boolean_flags(self):
        for baseline in ('D', 'V', '', 'S'):
            d = self.driver()
            d.p['preparation']['startup_log_tag']['allow_info_baseline'] = True
            d.value = baseline
            with self.subTest(baseline=baseline), self.assertRaises(r.Stop):
                d.prepare_startup_logging()
            self.assertFalse(any(c[1] == 'setprop' for c in d.calls))
        for flag in (None, 1, 'true', []):
            p = self.driver().p
            p['preparation']['startup_log_tag']['allow_info_baseline'] = flag
            with self.subTest(flag=flag), self.assertRaises(r.Stop):
                r.validate_plan(p)

    def test_owner_caps_setup_and_restores_exact_deadlines(self):
        d = self.driver()
        with patch.object(r.time, 'monotonic', return_value=100):
            d.prepare_startup_logging()
            self.assertEqual((d.preparation.total, d.total_deadline), (355, 355))
            self.assertEqual(d.value, 'V')
            self.assertTrue(d.log_tag_touched)
            d.restore_startup_logging()
        self.assertEqual((d.preparation.total, d.total_deadline), (1000, 1100))
        self.assertEqual(d.value, 'M')
        self.assertFalse(d.log_tag_touched)
        calls = d.calls.copy()
        d.restore_startup_logging()
        self.assertEqual(d.calls, calls)

    def test_foreign_baseline_and_running_app_prevent_mutation(self):
        for running in (False, True):
            d = self.driver()
            if running:
                d.preparation.cmd = lambda *args, **kwargs: b'123'
            else:
                d.value = 'D'
            with self.assertRaises(r.Stop):
                d.prepare_startup_logging()
            self.assertFalse(any(x[1] == 'setprop' for x in d.calls))
            self.assertFalse(d.log_tag_touched)

    def test_lost_set_reply_is_owned_and_restored_without_repeating_set(self):
        d = self.driver()
        d.fail_write = 'V'
        with self.assertRaises(OSError):
            d.prepare_startup_logging()
        self.assertTrue(d.log_tag_touched)
        d.restore_startup_logging()
        self.assertEqual([x[-1] for x in d.calls if x[1] == 'setprop'], ['V', 'M'])

    def test_unknown_restore_is_not_repeated_or_reported_complete(self):
        for fault in ('lost', 'readback', 'foreign'):
            d = self.driver()
            d.prepare_startup_logging()
            if fault == 'lost':
                d.fail_write = 'M'
            elif fault == 'readback':
                d.fail_readback = True
            else:
                d.value = 'D'
            with self.subTest(fault=fault), self.assertRaises((r.Stop, OSError)):
                d.restore_startup_logging()
            calls = d.calls.copy()
            with self.assertRaises(r.Stop):
                d.restore_startup_logging()
            self.assertEqual(d.calls, calls)
            self.assertTrue(d.log_tag_touched)
            self.assertEqual(d.preparation.total, 1000)

    def test_already_restored_value_needs_no_second_write(self):
        d = self.driver()
        d.prepare_startup_logging()
        d.value = 'M'
        d.restore_startup_logging()
        self.assertFalse(d.log_tag_touched)
        self.assertEqual([x[-1] for x in d.calls if x[1] == 'setprop'], ['V'])

    def test_late_restoration_does_not_qualify_setup(self):
        d = self.driver()
        with patch.object(r.time, 'monotonic', return_value=0):
            d.prepare_startup_logging()
        with patch.object(r.time, 'monotonic', return_value=301), self.assertRaises(r.Stop) as caught:
            d.restore_startup_logging()
        self.assertEqual(caught.exception.code, 'TIMEOUT')
        self.assertFalse(d.log_tag_touched)
        self.assertEqual(d.value, 'M')

    def test_two_new_records_after_restore_are_required(self):
        d = self.driver()
        d.prepare_startup_logging()
        d.decoder = SimpleNamespace(previous={'seq': 10})
        d.queue = deque([state(seq=8)])
        d.pump = lambda: None
        d.enter_stage = lambda *args: None
        rows = iter([state(seq=11, packageBytes=0), state(seq=12, packageBytes=0)])
        d.next_state = lambda seconds: next(rows)
        d.finish_startup_logging()
        self.assertEqual([x['seq'] for x in d.queue], [12])
        self.assertEqual(d.recorded[-1]['freshSeqs'], [11, 12])
        self.assertEqual(d.value, 'M')

    def test_empty_post_restore_stream_still_fails(self):
        d = self.driver()
        d.prepare_startup_logging()
        d.decoder = SimpleNamespace(previous={'seq': 10})
        d.queue = deque()
        d.pump = lambda: None
        d.enter_stage = lambda *args: None
        def missing(seconds):
            raise r.Stop('CAPABILITY_MISSING', 'empty live stream')
        d.next_state = missing
        with self.assertRaises(r.Stop):
            d.finish_startup_logging()
        self.assertFalse(d.log_tag_touched)
        self.assertEqual(d.value, 'M')


if __name__ == '__main__':
    unittest.main()
