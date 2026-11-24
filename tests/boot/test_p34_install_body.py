import os
from pathlib import Path
import sys
from types import SimpleNamespace
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT/'Tools/ota'))
sys.path.insert(0,str(ROOT/'tests/boot'))
from recovery_confirm import install as body
import test_p34_recovery_ports as model


class Log:
    def __init__(self,dap):
        self.dap = dap
        self.gate = SimpleNamespace(index=1,paths=tuple(range(721)),boundary=[])
        self.events = []
    def emit(self,event,**fields): self.events.append((event,fields))
    def target_allowed(self): return True
    def verify_head(self): pass
    def switch(self,*,read_allowed,expected_stores,bind_words=True):
        self.gate.index += 1
        return dict(target_writes=len(expected_stores),native_close=0,log_file_closed=1)


class Tests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.dll,cls.function = model.core.bind(Path(os.environ['P34_CONFIRM_DLL']))
        cls.assets = dict(boot=model.BOOT,old_app=(ROOT/'.cache/p34-native-image1/app-readback.bin').read_bytes(),
            image=model.IMAGE,envelope=(ROOT/'.cache/p34-recovery-preflight1/envelope.bin').read_bytes(),
            bcb=model.BEFORE*2,map=(ROOT/'.cache/p34-early-usb-r2/on/b/app-gcc/X-Track-App-GCC.map').read_bytes())
        cls.assets.update({name:(ROOT/'.cache/p34-host-nor-rebuild1'/('after-'+name+'.bin')).read_bytes() for name in body.REGIONS})

    def make(self):
        clock = model.Clock()
        slave = model.Slave(clock,model.BEFORE+b'R'*128)
        sdk = model.SDK(slave)
        dap = model.Dap(sdk)
        logs = Log(dap)
        saved = []
        install = body.Install(dap,SimpleNamespace(),logs,lambda:21600-clock.value,
            lambda *a:saved.append(a),self.assets,self.function,clock=clock,sleep=clock.sleep,guard=lambda f,*a,**k:f(*a))
        return install,clock,slave,sdk,logs,saved

    def test_real_gpio_pair_and_archives_do_not_inherit_readonly_write_gate(self):
        install,_,slave,sdk,logs,saved = self.make()
        install.active = install.held = True
        install.pin_config = sdk.original
        before = install.pair('before',model.BEFORE*2)
        self.assertEqual(before,model.BEFORE*2)
        self.assertEqual(b''.join(row[2] for row in saved),before)
        self.assertEqual([row[1] for row in saved],[0,64,128,192])
        self.assertEqual(logs.gate.index,5)
        self.assertEqual(slave.data,model.BEFORE+b'R'*128)
        self.assertEqual(install.index,5)

    def test_component_owns_its_advancing_index_then_returns_to_parent(self):
        install,_,_,_,logs,_ = self.make()
        install.active = install.held = True
        def run():
            self.assertTrue(install.owner())
            logs.gate.index += 3
            self.assertTrue(install.owner())
            return 'ok'
        self.assertEqual(install.component(run),'ok')
        self.assertEqual(install.index,4)
        self.assertFalse(install.delegating)
        logs.gate.index += 1
        with self.assertRaises(ValueError): install.owner()

    def test_wrong_bcb_or_log_extent_rejects_before_io(self):
        install,_,_,sdk,logs,_ = self.make()
        wrong = dict(self.assets,bcb=bytes(256))
        with self.assertRaises(ValueError):
            body.Install(install.dap,SimpleNamespace(),logs,lambda:21600,lambda *a:None,wrong,self.function)
        logs.gate.paths = tuple(range(722))
        with self.assertRaises(ValueError):
            body.Install(install.dap,SimpleNamespace(),logs,lambda:21600,lambda *a:None,self.assets,self.function)
        self.assertFalse(sdk.calls)

    def model_run(self,failure=None):
        install,clock,_,sdk,logs,saved = self.make()
        phases = []
        actual = bytearray(model.BEFORE)
        def stage(name,count):
            phases.append(name)
            if failure==name: raise ValueError('injected '+name)
            logs.gate.index += count
            install.index = logs.gate.index
        def entry():
            stage('entry',1)
            install.held = True
            install.pin_config = sdk.original
        def internal(label): stage(label+'-internal',21)
        def pair(label,expected):
            stage(label+'-pair',4)
            self.assertEqual(expected,bytes(actual)*2)
            return expected
        def nor(label): stage(label+'-nor',165)
        def state(): stage('state-after' if install.after_app else 'state-before',1); return []
        install.entry,install.internal,install.pair,install.nor,install.state = entry,internal,pair,nor,state
        class Sequence:
            app_may_have_changed = False
            def __init__(self,dap,image,preimage,owner,*args,**kwargs): self.owner = owner
            def run(self):
                phases.append('flash')
                for index in range(303):
                    assert self.owner()
                    self.app_may_have_changed = True
                    if failure=='flash'+str(index): raise ValueError('injected Flash failure')
                    logs.gate.index += 1
                    assert self.owner()
                return dict(result='ALL_FLASH_SECTORS_AUDITED')
        class Wire:
            error = pending_stop = None
            def __init__(self,dap,config,plan,owner,*args,**kwargs):
                self.address,self.record,self.owner = plan.address,plan.record,owner
                self.count = 0
            def advance(self):
                assert self.owner()
                self.count += 1
                if failure=='eeprom'+str(self.count):
                    self.error = 'injected wire failure'
                    raise ValueError(self.error)
                logs.gate.index += 1
                assert self.owner()
            def read(self,address,size,seconds): self.advance(); return bytes(actual[address:address+size])
            def page(self,address,data,seconds):
                self.advance();actual[address:address+8] = data
                return dict(status=0,released=True,stop_upper=clock.value)
            def ack(self,seconds): self.advance();return True
        class Exit:
            original_demcr,aircr_value = 0x1000000,0x05fa0304
            reset_attempted = release_attempted = False
            def __init__(self,dap,boot,admit,*args,**kwargs): self.admit = admit
            def reset_and_catch(self):
                assert self.admit('before-reset')
                self.reset_attempted = True
                stage('reset',0)
                return dict(result='FRESH_BOOT_CAUGHT',release_allowed=True)
            def release(self):
                assert self.admit('before-release')
                self.release_attempted = True
                stage('release',0)
                return dict(result='FRESH_BOOT_RELEASE_STORE_RETURNED')
        class Monitor:
            def __init__(self,*args,**kwargs): self.owner = args[3]
            def run(self):
                assert self.owner()
                stage('health',1)
                return dict(result='R2_RUNTIME_HEALTH_OBSERVED')
        with patch.object(body,'Sequence',Sequence),patch.object(body,'Wire',Wire),patch.object(body,'Exit',Exit),patch.object(body,'Monitor',Monitor):
            try: result = install.run()
            except ValueError: result = None
        return install,result,phases,logs

    def test_whole_body_model_original_c_transaction_and_719_segments(self):
        install,result,phases,logs = self.model_run()
        self.assertEqual(result['result'],'READY_FOR_FINAL_NATIVE_CLOSE',install.error)
        self.assertEqual(logs.gate.index,720)
        self.assertEqual(install.eeprom_wire.count,30)
        self.assertTrue(install.released)
        self.assertTrue(install.app_may_have_changed)
        self.assertFalse(result['final_native_close_audited'])
        self.assertFalse(result['historical_sdk_audit_passed'])
        self.assertEqual(phases,['entry','before-internal','before-pair','before-nor','state-before','flash',
            'after-internal','after-nor','state-after','after-pair','reset','release','health'])

    def test_each_phase_failure_has_no_later_reset_or_replay(self):
        failures = ('entry','before-internal','before-pair','before-nor','state-before','flash0','flash302',
                    'eeprom3','after-internal','after-nor','state-after','after-pair','reset','release','health')
        for failure in failures:
            with self.subTest(failure=failure):
                install,result,phases,logs = self.model_run(failure)
                self.assertIsNone(result)
                self.assertIsNotNone(install.error)
                self.assertFalse(install.active)
                if failure not in ('reset','release','health'): self.assertNotIn('reset',phases)
                if failure!='health': self.assertNotIn('health',phases)
                before = logs.gate.index
                with self.assertRaises(ValueError): install.run()
                self.assertEqual(logs.gate.index,before)

    def test_real_internal_capture_both_phases_and_collateral(self):
        install,clock,_,_,logs,saved = self.make()
        sdk = model.FlashSDK(clock,self.assets['envelope'])
        for offset in range(0,65536,4):
            sdk.memory[0x08000000+offset] = int.from_bytes(self.assets['boot'][offset:offset+4],'little')
        install.dap.sdk = sdk
        install.active = install.held = True
        install.internal('before')
        self.assertEqual(logs.gate.index,22)
        self.assertEqual(b''.join(row[2] for row in saved if row[0]=='before-boot'),self.assets['boot'])
        self.assertEqual(b''.join(row[2] for row in saved if row[0]=='before-envelope'),self.assets['envelope'])
        install.after_app = True
        desired = self.assets['image']+self.assets['envelope'][len(self.assets['image']):]
        sdk.flash[:] = desired
        install.internal('after')
        self.assertEqual(logs.gate.index,43)
        self.assertEqual(b''.join(row[2] for row in saved if row[0]=='after-envelope'),desired)
        self.assertEqual(desired[-964:],self.assets['envelope'][-964:])
        self.assertFalse(sdk.write_log)

    def test_state_window_native_guard_preserves_parent_close_allowance(self):
        install,clock,_,sdk,logs,_ = self.make()
        install.active = install.held = True
        original = body.Window
        end = [21600]
        active = [False]
        limits = []
        install.remaining = lambda:end[0]-clock.value
        def guard(function,*args,seconds):
            if active[0]: limits.append(seconds)
            result = function(*args)
            if active[0]: clock.value += .02
            return result
        install.native_guard = guard
        def window(*args,**kwargs):
            end[0] = clock.value+90.01
            active[0] = True
            sdk.calls.clear()
            return original(*args,**kwargs)
        with patch.object(body,'Window',window),self.assertRaises(ValueError): install.state()
        self.assertEqual(len(sdk.calls),1)
        self.assertEqual(sdk.calls[0][:3],('read',0,1))
        self.assertTrue(0<limits[0]<=.010001)
        self.assertEqual(logs.gate.index,1)


from test_p34_install_bridges import Bridges
from test_p34_install_entry import EntryTests

if __name__=='__main__': unittest.main()
