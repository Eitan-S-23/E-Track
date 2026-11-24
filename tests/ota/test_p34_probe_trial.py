"""Check new trial wiring without opening USB, BLE or native readers."""
import copy
import io
from pathlib import Path
import sys
from types import SimpleNamespace
import unittest
from unittest import mock

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'Tools/ota'))
import p34_probe_trial as f


class Guards(unittest.TestCase):
    def setUp(self):
        self.s = f.cli.Store(ROOT)

    def test_real_predecessor(self):
        group = f.profile.assets(self.s, 'control')
        proof = f.predecessor(self.s, 'control', group)
        self.assertEqual(proof['report']['summary']['input']['targetVersionCode'], 30254)
        bad = copy.deepcopy(group)
        bad['receiver']['sha256'] = '0'*64
        with self.assertRaises(RuntimeError): f.predecessor(self.s, 'control', bad)

    def test_reuse_requires_actual_control(self):
        with self.assertRaises((OSError, RuntimeError)):
            f.predecessor(self.s, 'reuse', f.profile.assets(self.s, 'reuse'))

    def test_observation_verifier_is_private_schema6(self):
        self.assertIs(f.batch.radio.backend.verify_experiment, f.profile.verify)
        self.assertIsNot(f.batch.radio.old.backend.verify_experiment, f.profile.verify)

    def test_both_config_switches(self):
        for arm in f.ORDER:
            api = object.__new__(f.Probe)
            api.assets = f.profile.assets(self.s, arm)
            base = {'schema': 5}
            phone = SimpleNamespace(config=lambda *a: base)
            with mock.patch.object(f.ui.Ui, 'phone', return_value=phone), \
                 mock.patch.object(f.profile, 'validate_config') as validate:
                actual = api.phone(None, 'test').config()
            self.assertEqual(actual['schema'], 6)
            self.assertIs(actual['reuseRebootInfoLink'], arm == 'reuse')
            validate.assert_called_once_with(actual, api.assets)

    def test_dns_keeps_exact_asset_verifier(self):
        api = object.__new__(f.Probe)
        with mock.patch.object(f.dns, 'verify', return_value='verified') as verify:
            self.assertEqual(api.verify_served('context', 'origin'), 'verified')
        verify.assert_called_once_with(api, 'context', 'origin')


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
        source=f.cli.record(f.__file__), test=f.cli.record(__file__), profile=f.cli.record(f.profile.__file__), log=log, hardware=False))
    print(stream.getvalue())
    sys.exit(not result.wasSuccessful())
