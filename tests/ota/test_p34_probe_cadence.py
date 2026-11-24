"""Host-only checks for the single-factor100ms probe interval follow-up."""
import io
import json
from pathlib import Path
import sys
from types import SimpleNamespace
import unittest
from unittest import mock

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'Tools/ota'))
import p34_probe_cadence as f


class Guards(unittest.TestCase):
    def setUp(self):
        self.s = f.cli.Store(ROOT)
        self.group = f.assets(self.s)
        g = self.group
        self.config = dict(schema=6, runId='s04', target='02:00:00:00:00:01', requestedBaud=921600,
            reuseGatt=True, withoutResponse=True, senderWindowSegments=28, transferMode='full', prefixBytes=0,
            rebootInfoTimeoutMs=2000, rebootProbeIntervalMs=100, pauseScanDuringOta=True, androidHighPriority=True,
            dataBatchFrames=3, reuseRebootInfoLink=True, currentVersionCode=30256, targetVersionCode=30257,
            currentImageSha256=g['receiver']['sha256'], targetImageSha256=g['target']['sha256'],
            packageBytes=g['package']['bytes'], packageSha256=g['package']['sha256'],
            firmwareLatestUrl='https://offline.trycloudflare.com/api/public/firmware/latest')

    def test_exact_profile_and_original_observation(self):
        f.validate(self.config, self.group)
        item = {k:v for k,v in self.config.items() if k not in ('target', 'firmwareLatestUrl')}
        item.update(deviceAddress=self.config['target'], endpointHost='offline.trycloudflare.com', configSha256='a'*64)
        capture = f.cli.load_module('cadence_capture', ROOT / 'Tools/ota/p34_observation.py')
        self.assertEqual(f.previous.profile.verify(capture, 'OTA_EXPERIMENT '+json.dumps(item), self.config, 'a'*64), item)
        item['rebootProbeIntervalMs'] = 500
        with self.assertRaises(RuntimeError):
            f.previous.profile.verify(capture, 'OTA_EXPERIMENT '+json.dumps(item), self.config, 'a'*64)

    def test_only_declared_axes(self):
        for key, value in self.config.items():
            if key in ('target', 'firmwareLatestUrl'): continue
            bad = dict(self.config)
            bad[key] = not value if type(value) is bool else value+1 if type(value) is int else value+'x'
            with self.subTest(key=key), self.assertRaises(RuntimeError): f.validate(bad, self.group)
        for value in (True, 100.0, '100', 99, 101, 500):
            with self.assertRaises(RuntimeError): f.validate(dict(self.config, rebootProbeIntervalMs=value), self.group)

    def test_wrapper_changes_only_interval(self):
        api = object.__new__(f.Cadence)
        api.assets = self.group
        baseline = dict(self.config, rebootProbeIntervalMs=500)
        with mock.patch.object(f.previous.Probe, 'phone', return_value=SimpleNamespace(config=lambda *a: baseline)):
            actual = api.phone(None, 'test').config()
        self.assertEqual(actual, self.config)
        self.assertEqual(baseline['rebootProbeIntervalMs'], 500)

    def test_receiver_code_and_boot_unchanged(self):
        a, b = [Path(self.group[k]['path']).read_bytes() for k in ('receiver', 'target')]
        self.assertEqual(a[:0x400]+a[0x460:], b[:0x400]+b[0x460:])
        self.assertEqual(self.group['receiver_bindings']['whole_boot'], self.group['target_bindings']['whole_boot'])
        self.assertEqual(len(self.group['negatives']), 4)
        self.assertTrue(all(x['native']['passed'] for x in self.group['negatives']))

    def test_actual_predecessor(self):
        report = f.ui.archival.proof(self.s, f.PRIOR)
        self.assertEqual(report['summary']['input']['targetVersionCode'], 30256)
        self.assertEqual(report['summary']['input']['targetImageSha256'], self.group['receiver']['sha256'])


if __name__ == '__main__':
    f.cli.require(Path.cwd() == ROOT and sys.flags.isolated and sys.flags.no_site and sys.dont_write_bytecode,
                  'isolated explicit root required')
    s = f.cli.Store(ROOT)
    s.checked(f.HOST)
    f.cli.require(not f.HOST.exists(), 'preserve tests')
    stream = io.StringIO()
    result = unittest.TextTestRunner(stream=stream, verbosity=2).run(unittest.defaultTestLoader.loadTestsFromTestCase(Guards))
    log = s.raw(f.HOST / 'tests.log', stream.getvalue().encode())
    s.write(f.HOST / 'result.json', dict(result='PASS' if result.wasSuccessful() else 'FAIL', tests=result.testsRun,
        source=f.cli.record(f.__file__), test=f.cli.record(__file__), log=log, hardware=False))
    print(stream.getvalue())
    sys.exit(not result.wasSuccessful())
