"""Offline schema6 and immutable firmware input guards; no device commands."""
import io
import json
from pathlib import Path
import sys
import unittest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'Tools/ota'))
import p34_probe_profile as f


class Guards(unittest.TestCase):
    def setUp(self):
        self.s = f.cli.Store(ROOT)
        self.group = f.assets(self.s, 'control')
        g = self.group
        self.config = dict(schema=6, runId='s04', target='02:00:00:00:00:01', requestedBaud=921600,
            reuseGatt=True, withoutResponse=True, senderWindowSegments=28, transferMode='full', prefixBytes=0,
            **f.batch.radio.EXTRA, pauseScanDuringOta=True, androidHighPriority=True, dataBatchFrames=3,
            reuseRebootInfoLink=False, currentVersionCode=30254, targetVersionCode=30255,
            currentImageSha256=g['receiver']['sha256'], targetImageSha256=g['target']['sha256'],
            packageBytes=g['package']['bytes'], packageSha256=g['package']['sha256'],
            firmwareLatestUrl='https://offline.trycloudflare.com/api/public/firmware/latest')
        self.item = {k: v for k, v in self.config.items() if k not in ('target', 'firmwareLatestUrl')}
        self.item.update(deviceAddress=self.config['target'], endpointHost='offline.trycloudflare.com', configSha256='a'*64)
        self.capture = f.cli.load_module('probe_profile_capture', ROOT / 'Tools/ota/p34_observation.py')

    def verify(self, item):
        return f.verify(self.capture, 'OTA_EXPERIMENT ' + json.dumps(item), self.config, 'a'*64)

    def test_exact(self):
        f.validate_config(self.config, self.group)
        self.assertEqual(self.verify(self.item), self.item)

    def test_wrong_or_unbounded_axes(self):
        for key in self.config:
            if key in ('target', 'firmwareLatestUrl'):
                continue
            value = self.config[key]
            bad = dict(self.config)
            bad[key] = not value if type(value) is bool else value+1 if type(value) is int else value+'x'
            with self.subTest(key=key), self.assertRaises(RuntimeError):
                f.validate_config(bad, self.group)

    def test_unknown_missing_or_nonboolean_policy(self):
        for value in [dict(self.config, unknown=True), {k:v for k,v in self.config.items() if k != 'reuseRebootInfoLink'},
                      dict(self.config, reuseRebootInfoLink=0)]:
            with self.assertRaises(RuntimeError): f.validate_config(value, self.group)

    def test_observation_drift(self):
        for key in (*f.batch.radio.EXTRA, *f.FLAGS, 'schema', 'configSha256', 'deviceAddress', 'endpointHost'):
            with self.subTest(key=key), self.assertRaises(RuntimeError):
                self.verify(dict(self.item, **{key: str(self.item[key])+'x'}))
        with self.assertRaises(RuntimeError): self.verify(dict(self.item, unknown=True))

    def test_sequential_equal_code_and_size(self):
        next_group = f.assets(self.s, 'reuse')
        a = Path(self.group['target']['path']).read_bytes()
        b = Path(next_group['target']['path']).read_bytes()
        self.assertEqual(a[:0x400]+a[0x460:], b[:0x400]+b[0x460:])
        self.assertEqual(next_group['receiver'], self.group['target'])
        self.assertEqual(next_group['package']['bytes'], self.group['package']['bytes'])
        self.assertTrue(next_group['specification']['reuseRebootInfoLink'])

    def test_unlisted_arm_rejected(self):
        with self.assertRaises(RuntimeError): f.assets(self.s, 'repeat')


if __name__ == '__main__':
    f.cli.require(Path.cwd() == ROOT and sys.flags.isolated and sys.flags.no_site and sys.dont_write_bytecode,
                  'isolated explicit root required')
    s = f.cli.Store(ROOT)
    out = s.checked(f.assets_api.AREA / 'profile-tests-001')
    f.cli.require(not out.exists(), 'preserve test output')
    stream = io.StringIO()
    result = unittest.TextTestRunner(stream=stream, verbosity=2).run(unittest.defaultTestLoader.loadTestsFromTestCase(Guards))
    log = s.raw(out / 'tests.log', stream.getvalue().encode())
    s.write(out / 'result.json', dict(result='PASS' if result.wasSuccessful() else 'FAIL', tests=result.testsRun,
        log=log, source=f.cli.record(f.__file__), test=f.cli.record(__file__), hardware=False))
    print(stream.getvalue())
    sys.exit(not result.wasSuccessful())
