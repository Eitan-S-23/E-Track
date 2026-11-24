"""CRC bootstrap gates use the actually confirmed batch predecessor."""
import copy
import io
from pathlib import Path
import sys
import unittest
from unittest import mock

ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT/'Tools/ota'))
import p34_crc_trial as f


class Tests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.s=f.cli.Store(ROOT); cls.group=f.assets(cls.s)

    def test_real_predecessor(self):
        p=f.predecessor(self.s,self.group)
        self.assertEqual(p['report']['summary']['input']['targetVersionCode'],30250)

    def test_prepared_image_is_not_actual_receiver(self):
        g=copy.deepcopy(self.group); g['receiver']['sha256']='0'*64
        with self.assertRaises(RuntimeError): f.predecessor(self.s,g)

    def test_unchanged_apk(self):
        self.assertEqual(f.batch.apk(self.s)['apk']['sha256'],
                         '97cacd39f163357e6844098d1840adefde4c1aee24cf52edd8e6fd003fb8320a')

    def test_closed_archive(self):
        self.assertEqual(len(f.archive_ready(self.s)['remaining']),7)

    def test_boot_retained_new_map_bound(self):
        a,b=(self.group[k] for k in ('receiver_bindings','target_bindings'))
        self.assertEqual(a['whole_boot'],b['whole_boot'])
        self.assertNotEqual(a['profile']['map'],b['profile']['map'])
        self.assertEqual(f.cli.record(b['profile']['map']['path']),b['profile']['map'])

    def test_measure_cannot_launch_as_bootstrap(self):
        with self.assertRaises(RuntimeError): f.Crc(self.s,'measure')

    def test_original_crc_resolves_exact_archive_only(self):
        record=f.cli.record(f.OLD_CRC)
        record['path']=str(ROOT/'boot/src/boot_crc32.c')
        self.assertEqual(f.history.resolve(record),f.OLD_CRC)
        record['sha256']='0'*64
        with self.assertRaises(RuntimeError): f.history.resolve(record)

    def test_failed_window_closed_without_device_cell(self):
        f.reconciled_preflight(self.s)

    def test_primary_error_saved_before_cleanup(self):
        store=mock.Mock()
        result=f.preserve_failure(store,ROOT/'.cache/fake',PermissionError('read failed'))
        self.assertEqual(result['error'],'PermissionError')
        self.assertEqual(result['detail'],'read failed')
        store.write.assert_called_once_with(ROOT/'.cache/fake/coordinator-failure.json',result)

    def test_cleanup_error_cannot_replace_primary_failure(self):
        store,owner,api=mock.Mock(),mock.Mock(),mock.Mock()
        store.read.return_value={'sources':[]}
        api.context.return_value.sources.return_value=[]
        with mock.patch.object(f.cli,'Store',return_value=store), \
             mock.patch.object(f.cli,'load_module',return_value=owner), \
             mock.patch.object(f,'Crc',return_value=api), \
             mock.patch.object(f,'tests',return_value={}), \
             mock.patch.object(f.cli,'wait_until',side_effect=[PermissionError('read failed'),TimeoutError('cleanup waited')]):
            with self.assertRaisesRegex(RuntimeError,'needs reconciliation'):
                f.coordinator()
        saved=store.write.call_args_list[-1].args[1]
        self.assertEqual(saved['error'],'PermissionError')
        self.assertEqual(saved['cleanup_error']['error'],'TimeoutError')

    def test_available_capacity_does_not_stop_app(self):
        p,c=mock.Mock(),mock.Mock()
        p.command.return_value='1790954680231324-f5d44eb6a9ba4f1484798e4d'
        f.prepare_capacity(mock.Mock(),p,ROOT/'.cache/fake',c,set())
        self.assertEqual(p.command.call_count,1)
        p.file_bytes.assert_not_called()

    def test_unknown_capture_inventory_cannot_stop_app(self):
        p,c=mock.Mock(),mock.Mock(); p.command.return_value='unknown'
        with self.assertRaises(RuntimeError): f.prepare_capacity(mock.Mock(),p,ROOT/'.cache/fake',c,set())
        self.assertEqual(p.command.call_count,1)


if __name__=='__main__':
    s=f.cli.Store(ROOT); f.cli.require(not f.HOST.exists(),'preserve tests')
    stream=io.StringIO()
    result=unittest.TextTestRunner(stream=stream,verbosity=2).run(unittest.defaultTestLoader.loadTestsFromTestCase(Tests))
    s.raw(f.HOST/'tests.log',stream.getvalue().encode())
    s.write(f.HOST/'result.json',dict(result='PASS' if result.wasSuccessful() else 'FAIL',tests=result.testsRun,
        source=f.cli.record(f.__file__),test=f.cli.record(__file__),hardware=False))
    print(stream.getvalue()); sys.exit(not result.wasSuccessful())
