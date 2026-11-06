"""Admission and phone-original guards for the P5 execution adapter."""
from pathlib import Path
import sys
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'Tools/ota/p51-acceptance'))
import run
import observation as obs
import pipeline_cloud as cloud


class ExecutionGuards(unittest.TestCase):
    def test_real_cli_normalizes_relative_input_before_recording(self):
        argv = ['run.py', 'cell', '--inputs', '.cache/input.json', '--out', '.cache/not-created',
                '--contract', 'docs/contract.json', '--matrix', '.cache/matrix.json', '--command-id', 'SD-FULL']
        def record(path):
            self.assertEqual(path, ROOT / '.cache/input.json')
            return {}
        with patch.object(sys, 'argv', argv), patch.object(run.h, 'read_json', return_value={}), \
                patch.object(run, 'validate', return_value={}), patch.object(run.h, 'record', side_effect=record), \
                patch.object(run.h, 'fresh', return_value=ROOT / '.cache/not-created'), patch.object(run.h, 'save'), \
                patch.object(run, 'gate', side_effect=RuntimeError('stop before device')) as gate, \
                patch.object(run.m, 'MCU') as mcu, self.assertRaisesRegex(RuntimeError, 'stop before device'):
            run.main()
        gate.assert_called_once()
        mcu.assert_not_called()

    def test_successor_requires_pinned_actual_predecessor(self):
        self.assertEqual(run.predecessor_arguments({'version': 1}), [])
        with self.assertRaises(RuntimeError):
            run.predecessor_arguments({'version': 2})
        prior = dict(contract={'path': 'first'}, matrix={'path': 'second'})
        with patch.object(run.h, 'pinned', side_effect=lambda pin: pin['path']):
            self.assertEqual(run.predecessor_arguments(dict(version=2, predecessor_bundle=prior)),
                             ['--previous-contract', 'first', '--previous-matrix', 'second'])

    def test_cloud_proxy_is_explicit_bound_connect_with_target_tls(self):
        context = object()
        with patch.object(cloud.http.client, 'HTTPSConnection') as connection:
            direct = cloud.Cloud({}, Path('.cache/not-created'), None)
            direct.connect(cloud.ADMIN, context)
            connection.assert_called_once_with('e-track-firmware-p43-admin-test.pages.dev', timeout=25, context=context)
            connection.return_value.set_tunnel.assert_not_called()
            connection.reset_mock()
            proxied = cloud.Cloud({'https_proxy': 'http://127.0.0.1:7897'}, Path('.cache/not-created'), None)
            proxied.connect(cloud.ADMIN, context)
            connection.assert_called_once_with('127.0.0.1', 7897, timeout=25, context=context)
            connection.return_value.set_tunnel.assert_called_once_with('e-track-firmware-p43-admin-test.pages.dev', 443)
            for value in ('http://elsewhere:7897', 'http://127.0.0.1:80', 'http://user:pass@127.0.0.1:7897'):
                with self.subTest(value=value), self.assertRaises(Exception):
                    cloud.Cloud({'https_proxy': value}, Path('.cache/not-created'), None).connect(cloud.ADMIN, context)

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
