import ctypes
import io
import os
from pathlib import Path
import sys
from types import SimpleNamespace
import unittest
from unittest import mock

ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT/'Tools/ota'));sys.path.insert(0,str(ROOT/'tests/boot'))
import p34_install_continue as run
from recovery_confirm import install_continue as body
from recovery_confirm.flash_continue import Remaining
from recovery_confirm.native_io import Budget
import test_p34_recovery_ports as model
import test_p34_install_body as original_tests
import test_p34_install_recovery as host_tests
import test_p34_flash_sequence as sequence_tests
import test_p34_online_log as online
import p34_gpio_session_model as entry_model
from test_p34_install_bridges import Buffer,Logged
from test_p34_mutation_audit import record,META
from test_p34_install_strict_audit import Tests as StrictTests


class Tests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.assets={name:path.read_bytes() for name,path in run.ASSETS.items()}
        cls.dll,cls.function=model.core.bind(Path(os.environ['P34_CONFIRM_DLL']))
        cls.retained=run.prior.failed_entry.predecessor(run.cli.Store(ROOT))

    def instance(self,native=None,real_logs=False):
        clock=model.Clock()
        partial=self.assets['image'][:6144]+self.assets['envelope'][6144:]
        if native is None:native=model.FlashSDK(clock,partial)
        else:clock=native.clock
        dap=model.Dap(native)
        if real_logs:
            paths=[Buffer('sdk-'+str(i),'') for i in range(721)]
            native.initialize_log(paths)
            dap=online.Dap(run.prior.JournalSDK(native,lambda *a,**k:None,clock=clock))
            logs=run.prior.OnlineLog(dap,run.prior.SealedGate(paths,META,record),lambda *a,**k:None,
                                     lambda:21600-clock.value,clock=clock)
            logs.switch(read_allowed=lambda _:False,expected_stores=[])
        else:logs=original_tests.Log(dap)
        saved=[]
        install=body.Install(dap,SimpleNamespace(),logs,lambda:21600-clock.value,lambda *a:saved.append(a),
            self.assets,self.function,clock=clock,sleep=clock.sleep,guard=lambda f,*a,**k:f(*a),retained_entry=self.retained)
        install.active=install.held=True
        return install,clock,native,logs,saved

    def test_real_partial_internal_archive_and_asset_restore_on_failure(self):
        for failure in (None,'bytes','seal'):
            class Native(Logged,model.FlashSDK):pass
            clock=model.Clock();partial=self.assets['image'][:6144]+self.assets['envelope'][6144:]
            native=Native(clock,partial)
            for offset in range(0,65536,4):
                native.memory[0x08000000+offset]=int.from_bytes(self.assets['boot'][offset:offset+4],'little')
            install,_,_,logs,saved=self.instance(native,True)
            original=install.assets
            if failure=='bytes':native.flash[6144]^=1
            if failure=='seal':native.hook=lambda:setattr(native,'fault','blank')
            if failure:
                with self.assertRaises(ValueError):install.internal('before')
            else:
                install.internal('before')
                self.assertEqual(b''.join(row[2] for row in saved if row[0]=='before-envelope'),partial)
                self.assertEqual(logs.gate.index,22)
            self.assertIs(install.assets,original)
            self.assertEqual(install.control.expected_header,self.assets['image'][0x400:0x460])
            self.assertFalse(native.write_log)

    def test_completed_prefix_seals_and_failures_before_any_payload(self):
        for failure in (None,'prefix','capacity','mode','seal','owner'):
            install,_,native,logs,_=self.instance()
            native.memory[body.old.flash.DHCSR]=0x30003
            if failure=='prefix':native.flash[2048]^=1
            if failure=='capacity':native.memory[body.old.flash.FSIZE]=512
            if failure=='mode':native.memory[body.old.flash.BANKS[0][2]]=1
            if failure=='owner':install.held=False
            oldswitch=logs.switch
            if failure=='seal':logs.switch=lambda **kwargs:(_ for _ in ()).throw(ValueError('seal failed'))
            # The inherited retained entry is separately tested with real Dap;
            # this seam isolates the new three physical prefix-read segments.
            def entry(_):logs.gate.index+=1;install.index=logs.gate.index
            with mock.patch.object(body.old.Install,'entry',entry):
                if failure:
                    with self.assertRaises(ValueError):install.entry()
                    self.assertFalse(install.prefix_verified)
                else:
                    install.entry();self.assertTrue(install.prefix_verified)
                    self.assertEqual(logs.gate.index,5)
            self.assertFalse(native.write_log)

    def sequence(self,failure=None):
        partial=self.assets['image'][:6144]+self.assets['envelope'][6144:]
        memory=bytearray(partial);called=[]
        log=sequence_tests.LogModel()
        def factory(dap,image,preimage,index,owner,emit,*,seconds,clock,sleep,guard):
            called.append(index)
            def execute():
                assert owner()
                if failure==index:raise ValueError('injected sector failure')
                offset=index*2048
                assert memory[offset:offset+2048]==preimage[offset:offset+2048]
                desired=image+preimage[len(image):]
                memory[offset:offset+2048]=desired[offset:offset+2048]
                return dict(complete=True,reset_allowed=False,address=0x08010000+offset,bank=1 if index<224 else 2,
                    programmed_words=sum(desired[i:i+4]!=b'\xff'*4 for i in range(offset,offset+2048,4)))
            return SimpleNamespace(run=execute,words=SimpleNamespace(reads=set(),budget=Budget(seconds,clock)))
        seq=Remaining(None,self.assets['image'],self.assets['envelope'],lambda:True,lambda *a,**k:None,
            log,lambda:21600,sector_factory=factory,native_guard=lambda f,*a,**k:f(*a))
        return seq,memory,called,log

    def test_exact_remaining300_and_no_replay_after_boundary_failures(self):
        for failure in (None,3,4,223,224,302):
            seq,memory,called,_=self.sequence(failure)
            if failure:
                with self.assertRaises(ValueError):seq.run()
                self.assertEqual(called,list(range(3,failure+1)))
                self.assertEqual(len(seq.completed),failure-3)
            else:
                self.assertEqual(seq.run()['result'],'REMAINING_300_FLASH_SECTORS_AUDITED')
                self.assertEqual(called,list(range(3,303)))
                self.assertEqual(memory,self.assets['image']+self.assets['envelope'][len(self.assets['image']):])
            self.assertEqual(memory[:6144],self.assets['image'][:6144])
            self.assertEqual(memory[-964:],self.assets['envelope'][-964:])
            before=len(called)
            with self.assertRaises(ValueError):seq.run()
            self.assertEqual(len(called),before)

    def test_real_remaining_adjacent_sectors_and_log_barriers(self):
        for failure in (None,'seal','delivered'):
            class Native(Logged,model.FlashSDK):pass
            clock=model.Clock();partial=self.assets['image'][:6144]+self.assets['envelope'][6144:]
            native=Native(clock,partial)
            install,_,_,logs,_=self.instance(native,True)
            seq=Remaining(install.dap,self.assets['image'],self.assets['envelope'],install.owner,logs.emit,logs,
                install.remaining,clock=clock,sleep=clock.sleep,native_guard=lambda f,*a,**k:f(*a))
            if failure=='seal':native.hook=lambda:setattr(native,'fault','blank')
            if failure=='delivered':native.fault='delivered'
            def emit(event,**fields):
                logs.emit(event,**fields)
                if event=='flash-sequence-sector-audited' and fields['index']==4:raise ValueError('bounded stop')
            seq.emit=emit
            with self.assertRaises((ValueError,OSError)):install.component(seq.run)
            self.assertEqual(native.flash[:6144],partial[:6144])
            self.assertFalse(any(0x08010000<=a<0x08011800 for a,v in native.write_log))
            if failure is None:
                self.assertEqual([x['index'] for x in seq.completed],[3,4])
                self.assertEqual(native.flash[6144:10240],self.assets['image'][6144:10240])
                self.assertEqual(native.flash[10240:],partial[10240:])
            else:self.assertFalse(seq.completed)

    def model_run(self,failure=None):
        install,clock,_,logs,_=self.instance()
        install.active=False
        phases=[];actual=bytearray(self.assets['bcb'][:128])
        def stage(name,count):
            phases.append(name)
            if failure==name:raise ValueError('injected '+name)
            logs.gate.index+=count;install.index=logs.gate.index
        def entry():stage('entry',4);install.held=True;install.prefix_verified=True;install.pin_config={}
        def pair(label,expected):
            stage(label+'-pair',4);self.assertEqual(expected,bytes(actual)*2);return expected
        install.entry=entry
        install.internal=lambda label:stage(label+'-internal',21)
        install.pair=pair
        install.nor=lambda label:stage(label+'-nor',165)
        install.state=lambda:stage('final-state' if install.eeprom_wire else 'before-state',1)
        class Sequence:
            def __init__(self,*args,**kwargs):self.owner=args[3];self.completed=[]
            def run(self):
                stage('flash',0)
                for index in range(3,303):
                    assert self.owner()
                    if failure=='flash'+str(index):raise ValueError('sector fail')
                    logs.gate.index+=1;self.completed.append(index)
                return dict(result='REMAINING_300_FLASH_SECTORS_AUDITED')
        class Wire:
            error=pending_stop=None
            def __init__(self,*args,**kwargs):
                self.owner=args[3];self.count=self.page_index=0
                self.address,self.record=args[2].address,args[2].record
            def advance(self):
                assert self.owner();self.count+=1
                if failure=='eeprom'+str(self.count):self.error='wire fail';raise ValueError(self.error)
                logs.gate.index+=1
            def read(self,address,size,seconds):self.advance();return bytes(actual[address:address+size])
            def page(self,address,data,seconds):
                self.advance();actual[address:address+8]=data;self.page_index+=1
                return dict(status=0,released=True,stop_upper=clock.value)
            def ack(self,seconds):self.advance();return True
        def boot():
            self.assertTrue(install.final_confirmed)
            self.assertEqual(logs.gate.index,717)
            stage('reset',1);stage('release',1);stage('health',1)
            install.released=True;install.held=False
        install.boot_and_health=boot
        with mock.patch.object(body,'Remaining',Sequence),mock.patch.object(body.old,'Wire',Wire):
            try:result=install.run()
            except ValueError:result=None
        return install,result,phases,logs

    def test_original_c_whole_body_719_segments_and_all_phase_barriers(self):
        for failure in (None,'entry','before-internal','before-pair','before-nor','before-state',
                        'flash3','flash302','eeprom3','eeprom25','after-internal','after-nor',
                        'final-state','after-pair','reset','release','health'):
            install,result,phases,logs=self.model_run(failure)
            if failure:
                self.assertIsNone(result)
                if failure not in ('reset','release','health'):self.assertNotIn('reset',phases)
            else:
                self.assertEqual(result['result'],'READY_FOR_FINAL_NATIVE_CLOSE')
                self.assertEqual(logs.gate.index,720)
                self.assertEqual(install.eeprom_wire.page_index,8)
                self.assertFalse(result['historical_sdk_audit_passed'])
            before=logs.gate.index
            with self.assertRaises(ValueError):install.run()
            self.assertEqual(before,logs.gate.index)

    def test_real_host_lifecycle_success_and_retained_failure_with_body_standin(self):
        # Reuse the original raw setup/close fixture, but execute the new host.
        original_execute=host_tests.run.execute
        def execute(*args,**kwargs):
            kwargs['body_factory']=host_tests.run.Install
            kwargs['retained_entry']={}
            return run.execute(*args,**kwargs)
        with mock.patch.object(host_tests.run,'execute',execute):
            fixture=host_tests.Tests()
            for fault in (None,'body','archive','close','construct','construct-read','connect-validation'):
                result,native,_=fixture.session(fault,retained=True)
                self.assertEqual(result['result'],'FAILED' if fault else 'R2_INSTALLED_ORIGINAL_BOOT_CLOSED')
                self.assertEqual(sum(name=='JLINKARM_Close' for name,_ in native.calls),1)
                self.assertEqual(native.target_accesses,0)
                if fault in ('body','construct','construct-read','connect-validation'):
                    self.assertEqual(native.dp,0xf0000040)
                    self.assertFalse(result['dap']['dp_restored'])

    def test_real_retained_entry_r2_header_old_context_and_prefix_log_seams(self):
        class Native(entry_model.SDK):
            def __init__(self,clock,paths):
                super().__init__(clock,model.Slave(clock,model.BEFORE+b'R'*128))
                self.paths,self.log_path,self.logged=paths,None,set()
            def __getattr__(self,name):
                function=super().__getattr__(name)
                if name not in self.logged:
                    old=function.callback
                    def call(*args):
                        if name=='JLINKARM_SetLogFile':
                            if self.log_path is not None:self.log_path.append('JLINK_SetLogFile()\nT0000 000:000.100 Closed\n')
                            self.log_path=next(p for p in self.paths if str(p).encode('ascii')==args[0])
                            return None
                        if name=='JLINKARM_ExecCommand':return int(args[0]==b'InhibitConnectRetries = 1')
                        result=old(*args)
                        if name in ('JLINKARM_CORESIGHT_ReadAPDPReg','JLINKARM_CORESIGHT_WriteAPDPReg'):
                            index,ap=args[:2];port='AP' if ap else 'DP'
                            if name.endswith('ReadAPDPReg'):
                                value=ctypes.cast(args[2],ctypes.POINTER(ctypes.c_uint32))[0]
                                self.log_path.append(f'JLINK_CORESIGHT_ReadAPDPReg({port} reg 0x{index:02X})\nValue=0x{value:08X}\n')
                            else:self.log_path.append(f'JLINK_CORESIGHT_WriteAPDPReg({port} reg 0x{index:02X}, 0x{args[2]:08X})\n')
                            self.log_path.append(f'T0000 000:000.000 - 0.1ms returns {result}\n')
                        return result
                    function.callback=call;self.logged.add(name)
                return function
        for failure in (None,'context','header','dma','prefix','bank'):
            clock=model.Clock();paths=[Buffer('entry-'+str(i),'') for i in range(721)]
            native=Native(clock,paths)
            sample=self.retained['state_samples'][0]
            native.memory.update({entry_model.controls.REGISTERS[k]:v for k,v in sample['raw'].items()})
            context=self.retained['context']
            native.core.update({15:context['pc'],16:context['xpsr'],17:context['msp'],20:context['control']<<24})
            native.memory.update({body.old.flash.DHCSR:0x30003,0xe000ef34:context['fpccr'],
                                  body.old.flash.IDCODE:0x70083347,body.old.flash.FSIZE:1024})
            for _,s,c,_ in body.old.flash.BANKS:native.memory.update({s:0x20,c:0x80})
            for offset in range(0,6144,4):native.memory[0x08010000+offset]=int.from_bytes(self.assets['image'][offset:offset+4],'little')
            if failure=='context':native.core[17]+=4
            if failure=='header':native.memory[0x08010400]^=1
            if failure=='dma':native.memory[entry_model.controls.REGISTERS['display_dma_count']]=1
            if failure=='prefix':native.memory[0x08010800]^=1
            if failure=='bank':native.memory[body.old.flash.BANKS[1][2]]=1
            rows=[]
            def collect(event,**fields):rows.append(dict(event=event,**fields))
            with mock.patch('recovery_entry.native_probe.guarded',side_effect=lambda f,*a,**k:f(*a)):
                project=run.cli.Store(ROOT).checked(Path(os.environ['P34_TEST_OUT'])/'model-only.jlink')
                dap=run.base.Dap(native,paths[0],project,io.BytesIO())
                dap.sdk=run.prior.JournalSDK(native,collect,clock=clock)
                observation=run.base.Observation(dap,collect,seconds=600,clock=clock)
                observation.connect()
                logs=run.prior.OnlineLog(dap,run.prior.SealedGate(paths,dap.metadata,record),lambda *a,**k:None,
                    lambda:21600-clock.value,initial_rows=rows,clock=clock)
                logs.switch(read_allowed=lambda _:False,expected_stores=[],expected_dp_writes=run.prior.setup.dp_plan(dap.metadata)[0])
                install=body.Install(dap,observation,logs,lambda:21600-clock.value,lambda *a:None,self.assets,self.function,
                    clock=clock,sleep=clock.sleep,guard=lambda f,*a,**k:f(*a),retained_entry=self.retained)
                install.active=True
                if failure:
                    with self.assertRaises(ValueError):install.entry()
                    self.assertFalse(install.prefix_verified)
                else:
                    install.entry()
                    self.assertTrue(install.prefix_verified)
                    self.assertEqual(logs.gate.index,5)
                    self.assertEqual(install.results['entry_audit']['target_writes'],12)


if __name__=='__main__':unittest.main()
