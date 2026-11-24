import copy
import io
import json
import os
from pathlib import Path
import sys
import unittest
from unittest import mock

ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT/'Tools/ota'))
sys.path.insert(0,str(ROOT/'tests/boot'))
import p34_gpio_read_device as run
import test_p34_recovery_ports as model

APP=(ROOT/'.cache/p34-native-image1/app-readback.bin').read_bytes()


class SessionTests(unittest.TestCase):
    def execute(self,fault=None):
        clock=model.Clock();slave=model.Slave(clock,model.BEFORE+b'R'*128);sdk=model.SDK(slave)
        dap=model.Dap(sdk);dap.close_returned=False;dap.metadata={}
        dap.read_flash=lambda a,n:(bytes([APP[0]^1])+APP[1:n]) if fault=='vectors' else APP[:n]
        rows=[];saved=[];phase=[]
        original={('gpiob_'+name):sdk.original[address] for address,name in
            ((run.gpio.MODE,'mode'),(run.gpio.TYPE,'type'),(run.gpio.DRIVE,'drive'),
             (run.gpio.PULL,'pull'),(run.gpio.OUTPUT,'output'))}
        context=dict(pc=0x08045a78,msp=0x20057da0,vtor=0x08010000)
        stopped=dict(result='APP_WFI_HALTED_RETAINED_NOT_RESET',media=dict(observed_blockers=[]),
                     context=context,state_samples=[dict(raw=original)]*2,
                     before=dict(debug_apb1_frz=0x1000))
        class Observation:
            def connect(self): phase.append('connect')
            def close(self):
                phase.append('close');dap.close_returned=True
                if fault=='close': raise OSError('closed but host receipt failed')
        observation=Observation()
        class Control:
            reset_seen=False
            mutation_attempted=True
            def __init__(self,*args): self.context_calls=0
            def context(self):
                self.context_calls+=1
                return dict(pc=0) if fault=='context' and self.context_calls>=2 else context
            def media(self): return dict(raw=original)
            def close(self): phase.append('retain');observation.close()
        def stop(*args,**kwargs):
            phase.append('stop')
            return dict(stopped,result='FAILED') if fault=='entry' else copy.deepcopy(stopped)
        owner_count=0
        def owners(*args):
            nonlocal owner_count
            owner_count+=1
            return dict(owner=2 if fault=='owners' and owner_count==3 else 1)
        def resume(*args,**kwargs):
            phase.append('resume')
            args[0].attempted=True
            if fault=='resume': raise OSError('resume outcome unknown')
            args[0].returned=True
            clock.sleep(20)
            return dict(result='ORIGINAL_APP_RESUMED_STABLE')
        def save(raw):
            saved.append(raw)
            if fault=='save': raise OSError('archive failed')
            return dict(bytes=len(raw))
        if fault=='native': sdk.fail_call=100
        words=run.Words
        emit=lambda event,**kw:rows.append(dict(event=event,**kw))
        with mock.patch.object(run,'Control',Control),mock.patch.object(run.rendezvous,'acquire',side_effect=stop), \
             mock.patch.object(run,'owners',side_effect=owners), \
             mock.patch.object(run.rendezvous,'stopped_media_observation',return_value=dict(observed_blockers=['changed'] if fault=='media' else [])), \
             mock.patch.object(run.app_resume,'execute',side_effect=resume), \
             mock.patch.object(run,'Words',side_effect=lambda *a,**kw:words(*a,guard=lambda fn,*v,**k:fn(*v),**kw)):
            result=run.execute(dap,observation,emit,save,APP,
                bytes([model.BEFORE[0]^1])+model.BEFORE[1:64] if fault=='bcb' else model.BEFORE[:64],
                seconds=320 if fault=='budget' else 420,clock=clock,sleep=clock.sleep)
        return result,sdk,slave,phase,saved,rows

    def test_fresh_entry_read_archive_then_same_context_exit(self):
        result,sdk,slave,phase,saved,rows=self.execute()
        self.assertEqual(result['result'],'GPIO_READ_ORIGINAL_APP_RESUMED',result.get('error'))
        self.assertEqual(phase,['connect','stop','resume','close'])
        self.assertEqual(saved,[model.BEFORE[:64]])
        self.assertEqual(slave.data,model.BEFORE+b'R'*128)
        self.assertEqual(result['wire']['gpio_stores'],1435)
        self.assertTrue(result['close_returned'])

    def test_entry_budget_or_native_failures_do_not_resume_or_retry_read(self):
        for fault in ('entry','budget','native'):
            result,sdk,slave,phase,saved,rows=self.execute(fault)
            self.assertEqual(result['result'],'FAILED')
            self.assertNotIn('resume',phase)
            self.assertEqual(phase[-2:],['retain','close'])
            self.assertFalse(saved)
            if fault!='native': self.assertFalse(slave.edges)

    def test_completed_read_is_preserved_but_failed_postchecks_never_resume(self):
        for fault in ('bcb','save','context','owners','media','vectors'):
            with self.subTest(fault=fault):
                result,sdk,slave,phase,saved,rows=self.execute(fault)
                self.assertEqual(result['result'],'FAILED')
                self.assertEqual(saved,[model.BEFORE[:64]])
                self.assertNotIn('resume',phase)
                self.assertEqual(slave.data,model.BEFORE+b'R'*128)

    def test_resume_or_close_failure_retains_original_outcome_without_retry(self):
        for fault in ('resume','close'):
            result,_,_,phase,_,_=self.execute(fault)
            self.assertEqual(result['result'],'FAILED')
            self.assertEqual(phase.count('resume'),1)
            self.assertEqual(phase.count('close'),1)

    def manifest(self):
        rows=[]
        def write(address,value,event):
            rows.append(dict(event=event,address=address,value=value))
            rows.append(dict(event='ap-call-attempt',operation='write',ap=1,index=1,value=address))
            rows.append(dict(event='ap-call-attempt',operation='write',ap=1,index=3,value=value))
        write(run.PAUSE,0x1000,'debug-write-attempt')
        write(run.COMP,run.rendezvous.WFI_COMPARATOR,'debug-write-attempt')
        write(run.COMP,0,'debug-write-attempt')
        start=len(rows);rows.append(dict(event='gpio-read-start'))
        write(run.gpio.SET,0x80,'recovery-word-write-attempt')
        end=len(rows);rows.append(dict(event='gpio-read-returned'))
        write(run.app_resume.DHCSR,0xa05f0001,'resume-write-attempt')
        return rows,start,end

    def test_whole_session_manifest_bounds_gpio_and_requires_single_exit(self):
        rows,start,end=self.manifest()
        result=run.session_writes(rows,start,end,dict(gpio_stores=1))
        self.assertEqual(result['resume_stores'],1)
        self.assertEqual(result['target_writes'],5)
        for fault in ('outside','extra-release','flash','missing-debug-marker'):
            changed=copy.deepcopy(rows)
            if fault=='outside': changed+=copy.deepcopy(rows[start+1:end])
            if fault=='extra-release': changed+=copy.deepcopy(rows[end+1:])
            if fault=='flash':
                changed[start+1]['address']=0x08010000;changed[start+2]['value']=0x08010000
            if fault=='missing-debug-marker': changed[0]['event']='removed'
            with self.assertRaises((ValueError,RuntimeError)):
                run.session_writes(changed,start,end,dict(gpio_stores=1))

    def test_gpio_samples_must_match_native_read_values_and_order(self):
        rows,start,end=self.manifest()
        read=[dict(event='ap-call-attempt',operation='write',ap=1,index=1,value=run.gpio.INPUT),
              dict(event='ap-call-attempt',operation='read',ap=1,index=3,value=None),
              dict(event='ap-call-returned',read_value=0xc0),
              dict(event='recovery-word-read',address=run.gpio.INPUT,value=0xc0)]
        rows[end:end]=read;end+=len(read)
        self.assertEqual(run.session_writes(rows,start,end,dict(gpio_stores=1))['gpio_target_reads'],1)
        for fault in ('value','missing','extra'):
            changed=copy.deepcopy(rows)
            index=end-1
            if fault=='value': changed[index]['value']^=0x80
            if fault=='missing': changed[index]['event']='removed'
            if fault=='extra':
                changed.insert(index,copy.deepcopy(changed[index]))
            with self.assertRaises(RuntimeError):
                run.session_writes(changed,start,end+int(fault=='extra'),dict(gpio_stores=1))

    def test_real_component_native_bridge_success_and_terminal_failure_seams(self):
        import p34_gpio_session_model as bridge
        for fault in (None,'header','gpio','release'):
            with self.subTest(fault=fault):
                result,rows,sdk,slave,saved=bridge.bridge(fault)
                self.assertTrue(result['close_returned'],result)
                self.assertEqual(sum(n=='JLINKARM_Close' for n,a in sdk.calls),1)
                self.assertEqual(bytes(slave.data),model.BEFORE+b'R'*128)
                if fault is None:
                    self.assertEqual(result['result'],'GPIO_READ_ORIGINAL_APP_RESUMED',result)
                    self.assertEqual(result['running_state'],'ORIGINAL_APP_HEALTH_VERIFIED')
                    self.assertEqual(result['exit']['running']['elapsed_seconds'],20)
                    self.assertTrue(result['dap']['tar_restored'])
                    self.assertTrue(result['dap']['csw_restored'])
                    self.assertTrue(result['dap']['dp_restored'])
                else:
                    self.assertEqual(result['result'],'FAILED')
                    if fault=='header':
                        self.assertFalse(result['transport_mutation_attempted'])
                        self.assertEqual(sdk.gpio_stores,0)
                    if fault=='gpio':
                        self.assertEqual(sdk.gpio_stores,1)
                        self.assertFalse(result['release_attempted'])
                    if fault=='release':
                        self.assertTrue(sdk.running)
                        self.assertTrue(result['release_attempted'])
                        self.assertFalse(result['release_returned'])
                        self.assertEqual(result['running_state'],'UNKNOWN_AFTER_RELEASE_ATTEMPT')
                        self.assertFalse(result['dap']['tar_restored'])
                        self.assertIsNotNone(result['native_ap_error'])
                        releases=[row for row in rows if row['event']=='resume-write-attempt']
                        self.assertEqual(len(releases),1)

    def reorder(self,rows,fault):
        changed=copy.deepcopy(rows)
        def block(event,operation=None):
            start=next(i for i,row in enumerate(changed) if row['event']==event+'-attempt' and
                       (operation is None or row.get('operation')==operation))
            end=next(i+1 for i in range(start+1,len(changed)) if changed[i]['event']==event+'-returned' and
                     (operation is None or changed[i].get('operation')==operation))
            return start,end
        if fault=='pause-after-arm':
            a,b=block('debug-write','pause');payload=changed[a:b];del changed[a:b]
            _,b=block('debug-write','arm');changed[b:b]=payload
        elif fault in ('early-release','duplicate-release'):
            a,b=block('resume-write');payload=copy.deepcopy(changed[a:b])
            if fault=='early-release':
                del changed[a:b]
                at=next(i for i,row in enumerate(changed) if row['event']=='gpio-read-start')
            else: at=b
            changed[at:at]=payload
        elif fault in ('post-release-selector','outside-gpio'):
            if fault=='post-release-selector':
                a,b=block('debug-write','selector');payload=copy.deepcopy(changed[a:b])
                _,at=block('resume-write')
            else:
                a,b=block('recovery-word-write');payload=copy.deepcopy(changed[a:b])
                address=changed[a]['address']
                a=max(i for i in range(a) if changed[i]['event']=='ap-call-attempt' and
                      changed[i]['operation']=='write' and changed[i]['ap']==1 and changed[i]['index']==1 and
                      changed[i]['value']==address)
                payload=copy.deepcopy(changed[a:b])
                at=next(i+1 for i,row in enumerate(changed) if row['event']=='gpio-read-returned')
            changed[at:at]=payload
        sequence=0;previous=0
        for row in changed:
            if row['event']=='ap-call-attempt': sequence+=1;row['sequence']=sequence
            elif row['event']=='ap-call-returned':
                row['sequence']=sequence
                row['started']=max(previous,row['started'])
                row['ended']=max(row['started'],row['ended']);previous=row['ended']
        return changed

    def test_composed_original_sdk_auditor_with_real_bridge_and_matched_negative_traces(self):
        import p34_gpio_session_model as bridge
        result,rows,sdk,slave,saved=bridge.bridge()
        self.assertEqual(result['result'],'GPIO_READ_ORIGINAL_APP_RESUMED',result)
        store=run.cli.Store(ROOT)
        out=store.checked(Path(os.environ['P34_TEST_OUT'])/'audit-model')
        inputs=run.sources(store);run.preflight(store,out,inputs)
        for path in inputs: store.raw(out/'source'/path.relative_to(ROOT),path.read_bytes())
        store.write(out/'reuse.json',run.reused_components(store)[1])
        store.write(out/'plan.json',dict(inputs=[run.cli.record(path) for path in inputs],before_history=[],
                                        reuse=run.cli.record(out/'reuse.json'),hardware=False,scope='SYNTHETIC HOST MODEL ONLY'))
        store.write(out/'worker.json',dict(result,hardware=False))
        store.write(out/'parent.json',dict(exit=0,timeout=False,after_history=[],hardware=False))
        store.raw(out/'read.bin',saved[0])
        native=list(bridge.sdk_lines(rows))
        store.raw(out/'sdk.log',('SYNTHETIC HOST MODEL ONLY\n'+''.join(native)).encode('utf-8'))
        store.raw(out/'events.jsonl',('\n'.join(json.dumps(row) for row in rows)+'\n').encode('utf-8'))
        run.audit(store,out)
        self.assertEqual(store.read(out/'audit.json')['result'],'GPIO_SESSION_SDK_AUDIT_PASS')
        original_open=Path.open
        original_read=store.read
        original_record=run.cli.record
        mutations=('pause-after-arm','early-release','duplicate-release','post-release-selector','outside-gpio',
                   'missing-measurement-read','changed-measurement-read','missing-close','restore',
                   'read-count','elapsed','source','snapshot')
        for fault in mutations:
            with self.subTest(fault=fault):
                changed=copy.deepcopy(rows);worker=copy.deepcopy(result)
                if fault in mutations[:5]: changed=self.reorder(rows,fault)
                if fault in ('missing-measurement-read','changed-measurement-read'):
                    i=next(i for i,row in enumerate(changed) if row['event']=='gpio-read-start')
                    row=next(row for row in changed[i:] if row['event']=='recovery-word-read' and row['address']==run.gpio.INPUT)
                    if fault=='missing-measurement-read': row['event']='removed'
                    else: row['value']^=0x80
                if fault=='restore': worker['dap']['tar_restored']=False
                if fault=='read-count': worker['read']['target_reads']+=1
                if fault=='elapsed': worker['read']['elapsed_seconds']+=1
                lines=list(bridge.sdk_lines(changed))
                if fault=='missing-close': lines.pop()
                def opened(path,*args,**kwargs):
                    if kwargs.get('encoding')=='utf-8':
                        if path==out/'sdk.log': return io.StringIO(''.join(lines))
                        if path==out/'events.jsonl': return io.StringIO('\n'.join(json.dumps(row) for row in changed)+'\n')
                    return original_open(path,*args,**kwargs)
                def read(path):
                    return worker if Path(path)==out/'worker.json' else original_read(path)
                def record(path):
                    value=original_record(path)
                    selected=run.SELF if fault=='source' else out/'source'/run.SELF.relative_to(ROOT)
                    if fault in ('source','snapshot') and Path(path)==selected: value['sha256']='0'*64
                    return value
                with mock.patch.object(Path,'open',opened),mock.patch.object(store,'read',side_effect=read), \
                     mock.patch.object(run.cli,'record',side_effect=record):
                    with self.assertRaises((ValueError,RuntimeError)):
                        run.audit(store,out)


if __name__=='__main__': unittest.main()
