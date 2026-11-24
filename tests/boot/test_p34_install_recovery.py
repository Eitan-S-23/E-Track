import io
import json
import os
from pathlib import Path
import sys
from types import SimpleNamespace
import unittest
from unittest import mock

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT/'Tools/ota'))
sys.path.insert(0,str(ROOT/'tests/boot'))
import p34_install_recovery as run
from test_p34_online_log_probe import LoggingSDK,PathModel
from test_p34_mutation_audit import record


class Tests(unittest.TestCase):
    def area(self,name):
        store = run.cli.Store(ROOT)
        out = store.checked(Path(os.environ['P34_TEST_OUT'])/name)
        run.preflight(store,out,[])
        store.checked(out).mkdir(parents=True)
        return store,out

    def test_all_exact_archives_fsync_and_readback_before_completion(self):
        store,out = self.area('archive-complete')
        archives = run.Archives(store,out)
        with self.assertRaises(RuntimeError): archives.finish()
        for name,size in run.ARCHIVES.items():
            for offset in range(0,size,32768):
                archives.write(name,offset,bytes([len(name)])*min(32768,size-offset))
        records = archives.finish()
        self.assertEqual(set(records),set(run.ARCHIVES))
        self.assertEqual(len(records),29)
        self.assertTrue(all(records[name]['bytes']==size for name,size in run.ARCHIVES.items()))
        archives.close()
        self.assertTrue(all(stream.closed for stream in archives.streams.values()))

    def test_archive_offset_replay_and_failure_are_preserved(self):
        store,out = self.area('archive-partial')
        archives = run.Archives(store,out)
        archives.write('before-bcb',0,b'x'*64)
        with self.assertRaises(RuntimeError): archives.write('before-bcb',0,b'y'*64)
        with self.assertRaises(RuntimeError): archives.write('before-bcb',64,b'z'*64)
        archives.close()
        self.assertEqual((out/'before-bcb.bin').read_bytes(),b'x'*64)
        with self.assertRaises(RuntimeError): run.Archives(store,out)

    def session(self,fault=None,original_dp=0x40,retained=False):
        paths = [PathModel(name,'') for name in run.LOGS]
        sdk = LoggingSDK(paths,'close' if fault=='close' else None)
        sdk.dp = original_dp
        rows,initial = [],[]
        def persist(event,**fields): rows.append(dict(event=event,**fields))
        def collect(event,**fields):
            persist(event,**fields)
            initial.append(dict(event=event,**fields))
        archives = SimpleNamespace(finish=lambda:{},close=lambda:None,write=lambda *a:None)
        if fault=='archive':
            def failed(): raise OSError('archive final validation failed')
            archives.finish = failed
        holder = []
        class Body:
            phase = 'TEST_BODY'
            app_may_have_changed = False
            flash_sequence = eeprom_wire = exit_port = None
            released = False
            results = {'confirmation':{'after':b'BCB bytes'}}
            def __init__(self,dap,observation,logs,*args,**kwargs):
                if fault=='construct-read':
                    def fail_read(): raise OSError('injected close-time DP read failure')
                    dap._power_ready = fail_read
                if fault in ('construct','construct-read'): raise ValueError('injected constructor failure')
                self.logs = logs
                def close():
                    dap.power_changed = False
                    observation.close()
                self.control = SimpleNamespace(mutation_attempted=fault!='early',close=close)
                holder.append(self)
            def run(self):
                if fault in ('body','early'): raise ValueError('injected body stop')
                for _ in range(run.BODY_SEGMENTS):
                    self.logs.switch(read_allowed=lambda _:False,expected_stores=[])
                self.phase = 'READY_FOR_FINAL_NATIVE_CLOSE'
                self.released = True
                return dict(result=self.phase)
        with mock.patch('recovery_entry.native_probe.guarded',side_effect=lambda f,*a,**k:f(*a)),mock.patch.object(run,'Install',Body):
            dap = run.base.Dap(sdk,paths[0],'unused-model-project.jlink',io.BytesIO())
            dap.sdk = run.JournalSDK(sdk,collect)
            if fault=='connect-validation':
                original_connected = dap.connected
                def connected():
                    if dap.ready: raise ValueError('injected post-acquisition validation failure')
                    return original_connected()
                dap.connected = connected
            observation = run.base.Observation(dap,collect,seconds=600)
            result = run.execute(dap,observation,persist,initial,paths,record,lambda:28000,
                                 archives,{},None,guard=lambda f,*a,**k:f(*a),retained_entry={} if retained else None)
        return result,sdk,holder

    def test_real_setup_and_final_native_close_with_body_standin(self):
        for original_dp in (0x40,0xf0000040):
            result,sdk,_ = self.session(original_dp=original_dp)
            self.assertEqual(result['result'],'R2_INSTALLED_ORIGINAL_BOOT_CLOSED',result)
            self.assertEqual(len(result['logs']),721)
            self.assertEqual(sdk.target_accesses,0)
            self.assertEqual(sum(name=='JLINKARM_Close' for name,_ in sdk.calls),1)
            self.assertEqual(sdk.dp,original_dp)
            self.assertFalse(result['historical_sdk_audit_passed'])
            self.assertEqual(result['original_dp_preserved_without_write'],original_dp==0xf0000040)

    def test_body_archive_and_uncertain_close_never_report_install_success(self):
        for fault in ('body','archive','close'):
            result,sdk,_ = self.session(fault)
            self.assertEqual(result['result'],'FAILED')
            self.assertEqual(sum(name=='JLINKARM_Close' for name,_ in sdk.calls),1)
            self.assertEqual(sdk.target_accesses,0)
            self.assertFalse(result.get('runtime_health_observed',False))

    def test_binary_bcb_result_has_lossless_json_representation(self):
        raw = bytes(range(256))
        value = json.loads(json.dumps(run.json_result({'component_results':[{'after':raw}]})))
        result = value['component_results'][0]['after']
        self.assertEqual(result['bytes'],256)
        self.assertEqual(bytes.fromhex(result['hex']),raw)

    def test_retained_failure_before_first_selector_keeps_debug_requests(self):
        for fault in ('construct','early','construct-read','connect-validation'):
            result,sdk,_ = self.session(fault,retained=True)
            self.assertEqual(result['result'],'FAILED')
            self.assertTrue(result['close_returned'])
            self.assertFalse(result['dap']['dp_restored'])
            self.assertEqual(sdk.dp,0xf0000040)
            self.assertEqual(sdk.target_accesses,0)
            self.assertEqual(sum(name=='JLINKARM_Close' for name,_ in sdk.calls),1)
            if fault=='construct-read': self.assertIn('close_error',result)


if __name__=='__main__': unittest.main()
