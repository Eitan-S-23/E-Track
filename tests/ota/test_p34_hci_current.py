"""No-device regressions for the current single-report adapter."""
import datetime as dt
from pathlib import Path
import sys
from types import SimpleNamespace
import unittest
from unittest.mock import Mock, patch

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'Tools/ota'))
import p34_hci_current as m


class Tests(unittest.TestCase):
    def test_deadline_allows_generation_retrieval_and_cleanup(self):
        self.assertGreaterEqual(m.USB_SECONDS, 900 + 180 + 120)
        io = Mock()
        ready = Path('session/usb/ready.json')
        adapter = m.DeadlineIO(io, ready)
        adapter.write_json(ROOT, ready, {'deadline': 'old'})
        value = io.write_json.call_args.args[2]
        remaining = (dt.datetime.fromisoformat(value['deadline']) - dt.datetime.now(dt.timezone.utc)).total_seconds()
        self.assertGreater(remaining, 1490)
        self.assertLessEqual(remaining, 1500)
        self.assertEqual(value['maximum_seconds'], 1500)
        with self.assertRaises(Exception):
            adapter.write_json(ROOT, ready, {})

    def test_other_receipts_unchanged(self):
        io = Mock()
        value = {'deadline': 'untouched'}
        m.DeadlineIO(io, Path('ready')).write_json(ROOT, Path('closed'), value)
        self.assertIs(io.write_json.call_args.args[2], value)

    def test_uncertain_report_is_never_retried(self):
        c, p = Mock(), Mock()
        p.command.side_effect = TimeoutError('USB lost')
        with patch.object(m.export, 'remote_preflight', return_value=[]), \
                patch.object(Path, 'exists', return_value=False), self.assertRaises(TimeoutError):
            m.generate(c, p, Path('unused'))
        p.command.assert_called_once_with(['shell', 'bugreportz', '-p'],
                                         timeout=900, binary=True, check=False)
        intent = c.save.call_args.args[1]
        self.assertEqual(intent['maximum_reports'], 1)
        self.assertFalse(intent['upload'])
        self.assertFalse(intent['delete_existing'])

    def test_spent_intent_rejected_before_phone_access(self):
        p = Mock()
        with patch.object(Path, 'exists', return_value=True), self.assertRaises(Exception):
            m.generate(Mock(), p, Path('unused'))
        p.command.assert_not_called()

    def test_preflight_failure_does_not_generate(self):
        p = Mock()
        with patch.object(Path, 'exists', return_value=False), \
                patch.object(m.export, 'remote_preflight', side_effect=ValueError('boundary')), \
                self.assertRaises(ValueError):
            m.generate(Mock(), p, Path('unused'))
        p.command.assert_not_called()


if __name__ == '__main__':
    unittest.main(verbosity=2)
