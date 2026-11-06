"""Admission and phone-original guards for the P5 execution adapter."""
from pathlib import Path
import sys
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'Tools/ota/p51-acceptance'))
import run
import observation as obs


class ExecutionGuards(unittest.TestCase):
    def test_exact_frozen_arguments(self):
        argv = ['cell', '--inputs', '.cache/in.json', '--out', '.cache/out', '--channel', 'sd',
                '--contract', 'docs/c.json', '--matrix', '.cache/m.json', '--command-id', 'sd-full']
        command = 'python -I -S -B -X utf8 Tools/ota/p51-acceptance/run.py ' + ' '.join(argv)
        run.invocation(command, argv)
        for old, new in (('sd-full', 'ble-full'), ('--channel sd', '--channel ble'),
                         ('--out .cache/out', '--out .cache/other'), ('-I -S', '-S -I')):
            with self.subTest(old=old), self.assertRaises(RuntimeError):
                run.invocation(command.replace(old, new), argv)

    def test_ui_actions_never_automated(self):
        for method in (obs.Observer.tap, obs.Observer.scroll):
            with self.assertRaises(RuntimeError):
                method(None)

    def test_identity_requires_post_boundary_real_event(self):
        row = dict(seq=3, event='identity', deviceAddress='e3:49:e1:14:d6:cb',
            linkConnected=True, freshConnection=True, currentVersionCode=30319,
            currentImageSha256='a'*64)
        self.assertEqual(obs.identity([row], 30319, 'a'*64, row['deviceAddress'], 2), row)
        for change in ({'event': 'heartbeat'}, {'seq': 2}, {'currentVersionCode': 30317},
                       {'currentImageSha256': 'b'*64}):
            self.assertIsNone(obs.identity([dict(row, **change)], 30319, 'a'*64, row['deviceAddress'], 2))
        for change in ({'linkConnected': False}, {'freshConnection': False}, {'deviceAddress': '00:00:00:00:00:00'}):
            with self.assertRaises(RuntimeError):
                obs.identity([dict(row, **change)], 30319, 'a'*64, row['deviceAddress'], 2)

    def test_sd_never_mutates_channels(self):
        with run.channel({}, Path('.cache/not-created'), False):
            pass

    def test_restore_rejects_missing_result_before_constructing_mcu(self):
        with patch.object(run.m, 'MCU') as mcu, self.assertRaises(RuntimeError):
            run.restore({}, Path('.cache/not-created'), None)
        mcu.assert_not_called()

    def test_recording_failure_does_not_restart_a_transfer(self):
        fake = object.__new__(obs.Observer)
        fake.capture_id = None
        fake.capture_resolved = False
        with patch.object(fake, 'cmd') as command:
            fake.preserve_failure()
        command.assert_not_called()


if __name__ == '__main__':
    unittest.main()
