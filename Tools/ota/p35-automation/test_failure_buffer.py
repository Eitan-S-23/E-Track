"""Forensic snapshots are bounded, read-only, and cannot repair live evidence."""
from pathlib import Path
from types import SimpleNamespace
import json
import unittest
from unittest.mock import patch

import runner as r
from test_runner import plan, state


class FailureBufferTests(unittest.TestCase):
    def test_events_reader_is_explicit_and_does_not_alter_text_policy(self):
        d = self.driver()
        d.base = ['adb', '-P', '5093', '-s', 'SYNTHETIC']
        self.assertNotIn('-b', d.logcat_command())
        d.p['preparation']['log_buffer'] = 'events'
        self.assertEqual(d.logcat_command(), d.base + ['logcat', '-b', 'events', '-v', 'epoch', '--pid=123', '-T', '1', '*:V'])
        d.capture_failure_buffer()
        self.assertEqual(d.calls[1][0][3], 'events')
        self.assertEqual(d.saved[0]['buffer'], 'events')
        p = plan()
        p['preparation'] = {'log_buffer': 'events'}
        r.validate_plan(p)
        p['preparation']['startup_log_tag'] = {'before': 'M', 'during': 'V', 'seconds': 300}
        with self.assertRaises(r.Stop):
            r.validate_plan(p)

    def test_numeric_event_tag_preserves_the_original_state(self):
        row = state()
        raw = ('1793500000.000 123 123 I [1163153461]: ' + r.PREFIX + json.dumps(row) + '\n').encode()
        self.assertEqual(r.Decoder().feed(raw), [row])

    def driver(self):
        d = object.__new__(r.Android)
        d.p = {'preparation': {'capture_failure_buffer': True}, 'app': {'id': 'test.app'}}
        d.preparation = SimpleNamespace(capture_id='a'*32, stream_failed=True, live=[{'seq': 1}])
        d.pid, d.out = '123', Path('synthetic')
        d.calls, d.saved = [], []
        d.h = SimpleNamespace(raw=lambda p, b: {'bytes': len(b)}, save=lambda p, v: d.saved.append(v))
        def cmd(args, seconds=15):
            d.calls.append((args, seconds))
            return b'123\n' if args[:2] == ['shell', 'pidof'] else b'diagnostic-only\n'
        d.cmd = cmd
        return d

    def test_snapshot_is_single_use_and_never_added_to_live(self):
        d = self.driver()
        d.capture_failure_buffer()
        d.capture_failure_buffer()
        self.assertEqual(len(d.calls), 4)
        self.assertEqual(d.calls[1][0], ['logcat', '-d', '-b', 'main', '-v', 'epoch', '--pid=123', '*:V'])
        self.assertTrue(all(0 < seconds <= 5 for _, seconds in d.calls))
        self.assertEqual(d.preparation.live, [{'seq': 1}])
        self.assertTrue(d.preparation.stream_failed)
        self.assertEqual(d.saved[0]['outcome'], 'DIAGNOSTIC_ONLY')
        self.assertFalse(d.saved[0]['usedForReadiness'])

    def test_disabled_or_unowned_capture_makes_no_read(self):
        for changed in ('option', 'capture'):
            d = self.driver()
            if changed == 'option':
                d.p['preparation'].clear()
            else:
                d.preparation.capture_id = None
            d.capture_failure_buffer()
            self.assertEqual(d.calls, [])

    def test_foreign_pid_and_failed_read_do_not_retry_or_clear_failure(self):
        for error in (False, True):
            d = self.driver()
            def cmd(args, seconds=15):
                d.calls.append(args)
                if error:
                    raise r.Stop('TIMEOUT', 'read failed')
                return b'456\n'
            d.cmd = cmd
            d.capture_failure_buffer()
            d.capture_failure_buffer()
            self.assertEqual(len(d.calls), 1)
            self.assertEqual(d.saved[0]['outcome'], 'DIAGNOSTIC_FAILED')
            self.assertTrue(d.preparation.stream_failed)

    def test_whole_snapshot_has_a_fifteen_second_deadline(self):
        d = self.driver()
        with patch.object(r.time, 'monotonic', side_effect=[0, 16]):
            d.capture_failure_buffer()
        self.assertEqual(len(d.calls), 1)
        self.assertEqual(d.saved[0]['code'], 'TIMEOUT')

    def test_diagnostic_receipt_io_failure_cannot_skip_owned_cleanup(self):
        d = self.driver()
        d.final_verified = d.radio_touched = False
        d.restore_startup_logging = lambda: None
        d.decoder = SimpleNamespace(previous=None, closed=None)
        prep = d.preparation
        prep.p = {'limits': {'cleanup_seconds': 90}}
        prep.phone = SimpleNamespace(operation_deadline=None)
        prep.mutation_unknown = False
        prep.prefix = lambda *args: None
        closed = []
        def cleanup():
            closed.append(True)
            return {'complete': True, 'unresolved': False}
        def save(*args):
            raise OSError('diagnostic disk failure')
        prep.cleanup, d.h.save = cleanup, save
        d.close()
        self.assertEqual(closed, [True])
        self.assertEqual(d.cleanup_result['bufferPreservationError'], 'diagnostic disk failure')
        self.assertTrue(prep.stream_failed)


if __name__ == '__main__':
    unittest.main()
