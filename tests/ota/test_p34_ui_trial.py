"""UI trial asset lineage and failure-preservation checks, no hardware."""
import copy
import io
from pathlib import Path
import sys
import unittest
from unittest import mock

ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT/'Tools/ota'))
import p34_ui_trial as f


class Tests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.s=f.cli.Store(ROOT)

    def test_header_only_measurement(self):
        group=f.assets(self.s,'measure')
        a,b=(Path(group[k]['path']).read_bytes() for k in ('receiver','target'))
        self.assertEqual(a[:0x400]+a[0x460:],b[:0x400]+b[0x460:])
        self.assertNotEqual(a,b)

    def test_current_30252_predecessor(self):
        g=f.assets(self.s,'bootstrap');p=f.predecessor(self.s,'bootstrap',g)
        self.assertEqual(p['report']['summary']['input']['targetVersionCode'],30252)

    def test_wrong_receiver_rejected(self):
        g=copy.deepcopy(f.assets(self.s,'bootstrap'));g['receiver']['sha256']='0'*64
        with self.assertRaises(RuntimeError):f.predecessor(self.s,'bootstrap',g)

    def test_same_apk_and_boot(self):
        self.assertEqual(f.batch.apk(self.s)['apk']['sha256'],
                         '97cacd39f163357e6844098d1840adefde4c1aee24cf52edd8e6fd003fb8320a')
        for arm in ('bootstrap','measure'):
            g=f.assets(self.s,arm)
            self.assertEqual(g['receiver_bindings']['whole_boot'],g['target_bindings']['whole_boot'])

    def test_unlisted_arm_rejected(self):
        with self.assertRaises(RuntimeError):f.assets(self.s,'other')

    def test_only_exact_historical_hal_bytes_resolve(self):
        original=f.cli.record(ROOT/'.cache/p34-crc-screen/f/USER/HAL/HAL_OTA_Package.cpp')
        original['path']=str(ROOT/'USER/HAL/HAL_OTA_Package.cpp')
        self.assertEqual(f.base.history.resolve(original),
                         ROOT/'.cache/p34-crc-screen/f/USER/HAL/HAL_OTA_Package.cpp')
        original['sha256']='0'*64
        with self.assertRaises(RuntimeError):f.base.history.resolve(original)

    def test_primary_cleanup_failures_preserved(self):
        s,api,c,owner=mock.Mock(),mock.Mock(),mock.Mock(),mock.Mock()
        with mock.patch.object(f,'tests',return_value={}), \
             mock.patch.object(f.cli,'wait_until',side_effect=[PermissionError('read'),TimeoutError('cleanup')]):
            with self.assertRaisesRegex(RuntimeError,'needs reconciliation'):
                f.coordinate(s,api,c,owner,Path('unused'),'bootstrap')
        result=s.write.call_args_list[-1].args[1]
        self.assertEqual(result['error'],'PermissionError')
        self.assertEqual(result['cleanup_error']['error'],'TimeoutError')


if __name__=='__main__':
    s=f.cli.Store(ROOT);f.cli.require(not f.HOST.exists(),'preserve tests')
    stream=io.StringIO()
    result=unittest.TextTestRunner(stream=stream,verbosity=2).run(unittest.defaultTestLoader.loadTestsFromTestCase(Tests))
    s.raw(f.HOST/'tests.log',stream.getvalue().encode())
    s.write(f.HOST/'result.json',dict(result='PASS' if result.wasSuccessful() else 'FAIL',tests=result.testsRun,
        source=f.cli.record(f.__file__),test=f.cli.record(__file__),hardware=False))
    print(stream.getvalue());sys.exit(not result.wasSuccessful())
