"""Measurement lineage and coordinator error preservation, no hardware access."""
import copy
import io
from pathlib import Path
import sys
import unittest
from unittest import mock

ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT/'Tools/ota'))
import p34_crc_measure as f


class Tests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.s=f.cli.Store(ROOT); cls.group=f.assets(cls.s)

    def test_measurement_is_header_only(self):
        before,after=(Path(self.group[k]['path']).read_bytes() for k in ('receiver','target'))
        self.assertEqual(before[:0x400]+before[0x460:],after[:0x400]+after[0x460:])
        self.assertNotEqual(before,after)

    def test_real_confirmed_crc_predecessor(self):
        p=f.predecessor(self.s,self.group)
        self.assertEqual(p['report']['summary']['input']['targetVersionCode'],30251)

    def test_wrong_receiver_hash_rejected(self):
        g=copy.deepcopy(self.group); g['receiver']['sha256']='0'*64
        with self.assertRaises(RuntimeError): f.predecessor(self.s,g)

    def test_measurement_cannot_be_bootstrap(self):
        with self.assertRaises(RuntimeError): f.Measure(self.s,'bootstrap')

    def test_boot_and_map_retained(self):
        a,b=(self.group[k] for k in ('receiver_bindings','target_bindings'))
        self.assertEqual(a['whole_boot'],b['whole_boot'])
        self.assertEqual(a['profile']['map'],b['profile']['map'])

    def test_no_new_apk(self):
        self.assertEqual(f.batch.apk(self.s)['apk']['sha256'],
                         '97cacd39f163357e6844098d1840adefde4c1aee24cf52edd8e6fd003fb8320a')

    def test_primary_and_cleanup_failure_both_preserved(self):
        store,owner,api,c=mock.Mock(),mock.Mock(),mock.Mock(),mock.Mock()
        with mock.patch.object(f,'tests',return_value={}), \
             mock.patch.object(f.cli,'wait_until',side_effect=[PermissionError('read failed'),TimeoutError('cleanup waited')]):
            with self.assertRaisesRegex(RuntimeError,'needs reconciliation'):
                f.coordinate(store,api,c,owner)
        value=store.write.call_args_list[-1].args[1]
        self.assertEqual(value['error'],'PermissionError')
        self.assertEqual(value['cleanup_error']['error'],'TimeoutError')


if __name__=='__main__':
    s=f.cli.Store(ROOT); f.cli.require(not f.HOST.exists(),'preserve tests')
    stream=io.StringIO()
    result=unittest.TextTestRunner(stream=stream,verbosity=2).run(unittest.defaultTestLoader.loadTestsFromTestCase(Tests))
    s.raw(f.HOST/'tests.log',stream.getvalue().encode())
    s.write(f.HOST/'result.json',dict(result='PASS' if result.wasSuccessful() else 'FAIL',tests=result.testsRun,
        source=f.cli.record(f.__file__),test=f.cli.record(__file__),hardware=False))
    print(stream.getvalue()); sys.exit(not result.wasSuccessful())
