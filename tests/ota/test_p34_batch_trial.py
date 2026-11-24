"""Host-only batch trial gates and original timing quality regression checks."""
import copy
import io
import json
import os
from pathlib import Path
import sys
from types import SimpleNamespace
import unittest
from unittest import mock

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'Tools/ota'))
import p34_batch_trial as f
import p34_install_cost as host


class Guards(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.s = f.cli.Store(ROOT)
        cls.group = f.assets(cls.s)

    def setUp(self):
        spec = self.group['specification']
        self.config = dict(schema=5, dataBatchFrames=3, runId='s04', target='02:00:00:00:00:01',
            requestedBaud=921600, senderWindowSegments=28, reuseGatt=True, withoutResponse=True,
            transferMode='full', prefixBytes=0, **f.radio.EXTRA,
            pauseScanDuringOta=True, androidHighPriority=True, currentVersionCode=spec['receiver'],
            targetVersionCode=spec['target_version'], currentImageSha256=self.group['receiver']['sha256'],
            targetImageSha256=self.group['target']['sha256'], packageBytes=self.group['package']['bytes'],
            packageSha256=self.group['package']['sha256'],
            firmwareLatestUrl='https://offline.trycloudflare.com/api/public/firmware/latest')
        self.item = {k:v for k,v in self.config.items() if k not in ('target', 'firmwareLatestUrl')}
        self.item.update(deviceAddress=self.config['target'], endpointHost='offline.trycloudflare.com', configSha256='a'*64)

    def verify(self):
        capture = f.cli.load_module('batch_guard_capture', ROOT / 'Tools/ota/p34_observation.py')
        return f.verify_batch(capture, 'OTA_EXPERIMENT ' + json.dumps(self.item), self.config, 'a'*64)

    def test_exact_schema5(self):
        f.validate_config(self.config, self.group)
        self.assertEqual(self.verify(), self.item)

    def test_fixed_axes_reject_drift(self):
        for key, value in self.config.items():
            if key in ('target', 'firmwareLatestUrl'):
                continue
            bad = dict(self.config)
            bad[key] = not value if type(value) is bool else value+1 if type(value) is int else value+'x'
            with self.subTest(key=key), self.assertRaises(RuntimeError):
                f.validate_config(bad, self.group)
        for value in (True, '3', 1):
            with self.assertRaises(RuntimeError):
                f.validate_config(dict(self.config, dataBatchFrames=value), self.group)

    def test_observation_unknown_or_altered_fields(self):
        good = dict(self.item)
        for key in (*f.radio.EXTRA, 'pauseScanDuringOta', 'androidHighPriority', 'dataBatchFrames', 'schema'):
            self.item = dict(good)
            self.item[key] = str(self.item[key])
            with self.subTest(key=key), self.assertRaises(RuntimeError):
                self.verify()
        self.item = dict(good, unknown=True)
        with self.assertRaises(RuntimeError):
            self.verify()

    def test_real_apk_and_closed_archive(self):
        self.assertEqual(f.apk(self.s)['sha'], f.install.artifact.SHA)
        self.assertEqual(len(f.archive_ready(self.s)['remaining']), 7)

    def test_real_predecessor_and_reject_wrong_raw(self):
        proof = f.predecessor(self.s, self.group)
        self.assertEqual(proof['report']['summary']['input']['targetVersionCode'], 30249)
        bad = copy.deepcopy(self.group)
        bad['receiver']['sha256'] = '0'*64
        with self.assertRaises(RuntimeError):
            f.predecessor(self.s, bad)

    def test_capacity_failure_prevents_provision(self):
        api = object.__new__(f.Batch)
        api.store, api.assets = self.s, self.group
        phone = SimpleNamespace(config=lambda *a: dict(self.config, schema=4), provision=mock.Mock())
        original = phone.provision
        c = SimpleNamespace(PKG='test', TARGET=self.config['target'],
            apk={'metadata': {'device_observation': {'sentinel': 'test'}}})
        with mock.patch.object(f.radio.Radio, 'phone', return_value=phone), \
             mock.patch.object(api, 'known_configs', return_value=set()), \
             mock.patch.object(f.capacity, 'ensure_capacity', side_effect=RuntimeError('full')):
            wrapped = api.phone(c, 'test')
            self.assertEqual(wrapped.config()['dataBatchFrames'], 3)
            with self.assertRaises(RuntimeError):
                wrapped.provision(c, mock.Mock(), ROOT / '.cache/fake', self.config)
            original.assert_not_called()

    def fixture(self):
        module = f.cli.load_module('batch_timing_fixture', f.AREA / 'src/tests/ota/test_p34_batch_timing.py')
        lines = module.fixture()
        value = json.loads(lines[-1][len('OTA_LINK_STATS '):])
        value.update(device=self.config['target'], bind=dict(writeMode='without', mtuChunkBytes=244,
            mtuSource='negotiated'), discovers={}, platformWrites={})
        value['transfer'].update(durable={'finalOff':384}, ackEarlyUnsent=0, ackLatency={'count':2})
        return lines[:-1], value

    def metrics(self, lines, value, markers=None):
        return f.full_metrics('\n'.join(lines + ['OTA_LINK_STATS '+json.dumps(value)] +
            (markers if markers is not None else ['OTA_MONO MONO_END_ACK_OK monoUs=1000 wallUs=1000 durable=384',
             'OTA_MONO MONO_REBOOT_VERIFIED monoUs=22001000 wallUs=22001000'])), 384, self.config['target'])

    def test_partial_ack_is_not_threshold_evidence(self):
        lines, value = self.fixture()
        result = self.metrics(lines, value)
        self.assertFalse(result['ack_threshold_eligible'])
        self.assertFalse(result['formal_reference_admitted'])
        self.assertEqual(result['ack_sample_integrity'], 'partial:early=1')
        self.assertEqual(result['installation_reconnect_seconds'], 22)
        self.assertEqual(result['data_gatt_seconds'], .0002)

    def test_link_and_durable_mismatch_rejected(self):
        lines, good = self.fixture()
        for field, key, wrong in [('bind','mtuChunkBytes',243), ('bind','writeMode','with'),
                                  ('bind','mtuSource','fallback'), ('transfer','durable',{'finalOff':383})]:
            bad = copy.deepcopy(good)
            bad[field][key] = wrong
            with self.subTest(key=key), self.assertRaises(RuntimeError):
                self.metrics(lines, bad)
        good['device'] = 'other'
        with self.assertRaises(RuntimeError):
            self.metrics(lines, good)

    def test_original_unique_reboot_markers_required(self):
        lines, value = self.fixture()
        for markers in ([], ['OTA_MONO MONO_END_ACK_OK monoUs=1000 wallUs=1000 durable=384']*2):
            with self.assertRaises(RuntimeError):
                self.metrics(lines, value, markers)

    def test_private_backend_only(self):
        self.assertIs(f.radio.backend.verify_experiment, f.verify_batch)
        self.assertIsNot(f.radio.old.backend.verify_experiment, f.verify_batch)


if __name__ == '__main__':
    f.cli.require(Path.cwd() == ROOT and sys.flags.isolated and sys.flags.no_site and sys.dont_write_bytecode,
                  'explicit root and isolated Python required')
    s, out = f.cli.Store(ROOT), f.HOST_TESTS
    f.cli.require(not out.exists(), 'preserve original tests')
    os.environ.update(host.environment(s, out))
    stream = io.StringIO()
    result = unittest.TextTestRunner(stream=stream, verbosity=2).run(unittest.defaultTestLoader.loadTestsFromTestCase(Guards))
    log = s.raw(out / 'tests.log', stream.getvalue().encode())
    s.write(out / 'result.json', dict(result='PASS' if result.wasSuccessful() else 'FAIL', tests=result.testsRun,
        errors=len(result.errors), failures=len(result.failures), log=log, source=f.cli.record(f.__file__),
        test=f.cli.record(__file__), reader=f.cli.record(f.READER), hardware=False))
    print(stream.getvalue(), flush=True)
    sys.exit(not result.wasSuccessful())
