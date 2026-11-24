"""Bounded real-component seams; not a full physical installation model."""
import ctypes
import io
import os
from pathlib import Path
import sys
import unittest
from unittest import mock

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT/'Tools/ota'))
sys.path.insert(0,str(ROOT/'tests/boot'))
from recovery_confirm import install as body, r2_health as rh
from recovery_confirm.ap_journal import JournalSDK
from recovery_confirm.mutation_audit import SealedGate
from recovery_confirm.online_log import OnlineLog
from recovery_confirm.flash_sequence import Sequence
from test_p34_mutation_audit import MemoryPath,record,META
import test_p34_online_log as online
import test_p34_recovery_ports as ports
import p34_gpio_session_model as entry_model
import p34_install_recovery as host


class Buffer(MemoryPath):
    @property
    def data(self): return ''.join(self.parts)
    @data.setter
    def data(self,value): self.parts = [value]
    def append(self,value): self.parts.append(value)


class Logged:
    """A raw SDK sink independent from JournalSDK's event rendering."""
    def initialize_log(self,paths):
        self.paths,self.index,self.switches = paths,0,0
        self.fault = None
        self.hook = lambda:None
    def log(self,text): self.paths[self.index].append(text)
    JLINKARM_SetLogFile = online.Native.JLINKARM_SetLogFile
    def JLINKARM_CORESIGHT_ReadAPDPReg(self,index,ap,out):
        self.log(f'JLINK_CORESIGHT_ReadAPDPReg({"AP" if ap else "DP"} reg 0x{index:02X})\n')
        if (index,ap)==(1,1):
            ctypes.cast(out,ctypes.POINTER(ctypes.c_uint32))[0] = self.tar
            result = 0
        else: result = super().JLINKARM_CORESIGHT_ReadAPDPReg(index,ap,out)
        value = ctypes.cast(out,ctypes.POINTER(ctypes.c_uint32))[0]
        self.log(f'Value=0x{value:08X}\nT0000 000:000.000 - 0.1ms returns {result}\n')
        return result
    def JLINKARM_CORESIGHT_WriteAPDPReg(self,index,ap,value):
        self.log(f'JLINK_CORESIGHT_WriteAPDPReg({"AP" if ap else "DP"} reg 0x{index:02X}, 0x{value:08X})\n')
        result = super().JLINKARM_CORESIGHT_WriteAPDPReg(index,ap,value)
        self.log(f'T0000 000:000.000 - 0.1ms returns {result}\n')
        return result


class Bridges(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.assets = {name:path.read_bytes() for name,path in host.ASSETS.items()}
        cls.dll,cls.function = ports.core.bind(Path(os.environ['P34_CONFIRM_DLL']))

    def instance(self,native,clock):
        paths = [Buffer(f'sdk-{i}','') for i in range(721)]
        native.initialize_log(paths)
        dap = online.Dap(JournalSDK(native,lambda *a,**k:None,clock=clock))
        logs = OnlineLog(dap,SealedGate(paths,META,record),lambda *a,**k:None,lambda:21600-clock.value,clock=clock)
        logs.switch(read_allowed=lambda _:False,expected_stores=[])
        saved = []
        install = body.Install(dap,object(),logs,lambda:21600-clock.value,lambda *a:saved.append(a),
            self.assets,self.function,clock=clock,sleep=clock.sleep,guard=lambda f,*a,**k:f(*a))
        install.active = install.held = True
        return install,logs,saved

    def test_real_parent_internal_blocks_and_two_delegated_sectors_use_real_logs(self):
        class Native(Logged,ports.FlashSDK): pass
        for corrupt in (False,True):
            clock = ports.Clock()
            native = Native(clock,self.assets['envelope'])
            for offset in range(0,65536,4):
                native.memory[0x08000000+offset] = int.from_bytes(self.assets['boot'][offset:offset+4],'little')
            install,logs,saved = self.instance(native,clock)
            install.internal('before')
            self.assertEqual(len(logs.gate.records),22)
            self.assertEqual(b''.join(row[2] for row in saved if row[0]=='before-envelope'),self.assets['envelope'])
            sequence = Sequence(install.dap,self.assets['image'],self.assets['envelope'],install.owner,
                logs.emit,logs,install.remaining,clock=clock,sleep=clock.sleep,native_guard=install.native_guard)
            if corrupt: native.hook = lambda:setattr(native,'fault','blank')
            else:
                def emit(event,**fields):
                    logs.emit(event,**fields)
                    if event=='flash-sequence-sector-audited' and fields['index']==1:
                        raise ValueError('deliberate two-sector stop')
                sequence.emit = emit
            with self.assertRaises(ValueError): install.component(sequence.run)
            self.assertEqual(len(sequence.completed),0 if corrupt else 2)
            self.assertEqual(install.index,logs.gate.index)
            self.assertFalse(install.delegating)
            limit = 2048 if corrupt else 4096
            self.assertEqual(bytes(native.flash[limit:]),self.assets['envelope'][limit:])

    def test_real_parent_gpio_pair_binds_every_edge_to_current_log_segment(self):
        class Native(Logged,ports.SDK): pass
        for failure in (False,True):
            clock = ports.Clock()
            native = Native(ports.Slave(clock,ports.BEFORE+b'R'*128))
            install,logs,saved = self.instance(native,clock)
            install.pin_config = native.original
            if failure:
                native.hook = lambda:setattr(native,'fault','blank')
                with self.assertRaises(ValueError): install.pair('before',self.assets['bcb'])
                self.assertEqual(len(saved),1)
                self.assertEqual(native.slave.segments,[(0xa0,0),(0xa1,)])
                self.assertFalse(logs.target_allowed())
            else:
                pair = install.pair('before',self.assets['bcb'])
                self.assertEqual(pair,self.assets['bcb'])
                self.assertEqual(len(logs.gate.records),5)
                self.assertEqual(install.index,5)
                self.assertEqual(b''.join(row[2] for row in saved),pair)
                logs.verify_head()

    def test_first_internal_seal_failure_prevents_app_capture_or_programming(self):
        class Native(Logged,ports.FlashSDK): pass
        clock = ports.Clock()
        native = Native(clock,self.assets['envelope'])
        for offset in range(0,65536,4):
            native.memory[0x08000000+offset] = int.from_bytes(self.assets['boot'][offset:offset+4],'little')
        install,logs,saved = self.instance(native,clock)
        native.hook = lambda:setattr(native,'fault','blank')
        with self.assertRaises(ValueError): install.internal('before')
        self.assertEqual([(name,offset,len(raw)) for name,offset,raw in saved],[('before-boot',0,32768)])
        self.assertFalse(native.write_log)
        self.assertFalse(logs.target_allowed())

    def test_real_entry_control_owner_and_new_log_audit_or_failure_stop(self):
        class SDK(entry_model.SDK):
            def __init__(self,clock,slave,paths,broken):
                super().__init__(clock,slave)
                self.paths,self.log_path,self.logged,self.broken = paths,None,set(),broken
            def __getattr__(self,name):
                function = super().__getattr__(name)
                if name not in self.logged:
                    old = function.callback
                    def call(*args):
                        if name=='JLINKARM_SetLogFile':
                            if self.log_path is not None:
                                self.log_path.append('JLINK_SetLogFile()\nT0000 000:000.100 Closed\n')
                                if self.broken and self.log_path is self.paths[1]: self.log_path.data = '\n'
                            self.log_path = next(p for p in self.paths if str(p).encode('ascii')==args[0])
                            return None
                        if name=='JLINKARM_ExecCommand': return int(args[0]==b'InhibitConnectRetries = 1')
                        result = old(*args)
                        if name in ('JLINKARM_CORESIGHT_ReadAPDPReg','JLINKARM_CORESIGHT_WriteAPDPReg'):
                            index,ap = args[:2]
                            port = 'AP' if ap else 'DP'
                            if name.endswith('ReadAPDPReg'):
                                value = ctypes.cast(args[2],ctypes.POINTER(ctypes.c_uint32))[0]
                                self.log_path.append(f'JLINK_CORESIGHT_ReadAPDPReg({port} reg 0x{index:02X})\nValue=0x{value:08X}\n')
                            else: self.log_path.append(f'JLINK_CORESIGHT_WriteAPDPReg({port} reg 0x{index:02X}, 0x{args[2]:08X})\n')
                            self.log_path.append(f'T0000 000:000.000 - 0.1ms returns {result}\n')
                        return result
                    function.callback = call
                    self.logged.add(name)
                return function
        for retained,broken,bad in ((False,False,None),(False,True,None),(True,False,None),
                                    (True,True,None),(True,False,'context'),(True,False,'dma'),
                                    (True,False,'header')):
            clock = ports.Clock()
            paths = [Buffer(f'sdk-{i}','') for i in range(721)]
            native = SDK(clock,ports.Slave(clock,ports.BEFORE+b'R'*128),paths,broken)
            previous = None
            if retained:
                previous = host.failed_entry.predecessor(host.cli.Store(ROOT))
                sample = previous['state_samples'][0]
                native.memory.update({entry_model.controls.REGISTERS[key]:value for key,value in sample['raw'].items()})
                context = previous['context']
                native.core.update({15:context['pc'],16:context['xpsr'],17:context['msp'],20:context['control']<<24})
                native.memory[body.control_probe.DHCSR] = 0x30003
                native.memory[0xe000ef34] = context['fpccr']
                if bad=='context': native.core[17] += 4
                if bad=='dma': native.memory[entry_model.controls.REGISTERS['display_dma_count']] = 1
                if bad=='header': native.memory[0x08010400] ^= 1
            rows = []
            def collect(event,**fields): rows.append(dict(event=event,**fields))
            with mock.patch('recovery_entry.native_probe.guarded',side_effect=lambda f,*a,**k:f(*a)):
                project = host.cli.Store(ROOT).checked(Path(os.environ['P34_TEST_OUT'])/'model-only.jlink')
                dap = host.base.Dap(native,paths[0],project,io.BytesIO())
                dap.sdk = JournalSDK(native,collect,clock=clock)
                observation = host.base.Observation(dap,collect,seconds=600,clock=clock)
                observation.connect()
                logs = OnlineLog(dap,SealedGate(paths,dap.metadata,record),lambda *a,**k:None,
                                 lambda:21600-clock.value,initial_rows=rows,clock=clock)
                logs.switch(read_allowed=lambda _:False,expected_stores=[],expected_dp_writes=host.setup.dp_plan(dap.metadata)[0])
                install = body.Install(dap,observation,logs,lambda:21600-clock.value,lambda *a:None,
                    self.assets,self.function,clock=clock,sleep=clock.sleep,guard=lambda f,*a,**k:f(*a),
                    retained_entry=previous)
                if broken or bad:
                    install.internal = lambda *a:self.fail('internal capture after failed entry seal')
                    with self.assertRaises(ValueError): install.run()
                    if broken: self.assertIsNotNone(logs.error)
                    self.assertFalse(install.app_may_have_changed)
                    if retained: self.assertTrue(install.control.retain_debug_requests)
                else:
                    install.active = True
                    install.entry()
                    self.assertEqual(install.results['entry_audit']['target_writes'],12 if retained else 15)
                    self.assertEqual(logs.gate.index,2)
                    self.assertTrue(install.held)

    def test_real_boot_reset_seal_release_seal_health_chain_and_barriers(self):
        class Native(Logged,ports.ResetSDK):
            runtime = False
            def JLINKARM_CORESIGHT_WriteAPDPReg(self,index,ap,value):
                address = self.tar
                result = super().JLINKARM_CORESIGHT_WriteAPDPReg(index,ap,value)
                if (index,ap,address,value)==(3,1,rh.DHCSR,0xa05f0001): self.runtime = True
                return result
            def JLINKARM_CORESIGHT_ReadAPDPReg(self,index,ap,out):
                if self.runtime:
                    self.clock.value += .001
                    self.memory.update({rh.VTOR:rh.RUNTIME,rh.CFSR:0,rh.HFSR:0,rh.SD:1,rh.DIAG:1,
                                        rh.FAULT:0,rh.FLAGS:0x010104,rh.TICK:int(self.clock.value*1000)})
                    values = (30000,30,1000,0,int(self.clock.value*100),int(self.clock.value*100),0,1,1)
                    for i,value in enumerate(values): self.memory[rh.HEALTH+4*i] = value
                return super().JLINKARM_CORESIGHT_ReadAPDPReg(index,ap,out)
        for failure in (None,'ORIGINAL_BOOT_RESET','ORIGINAL_BOOT_RELEASE'):
            clock = ports.Clock()
            native = Native(clock)
            for start,stop in ((0x400,0x460),(0x800,0x800+524)):
                for offset in range(start,stop,4):
                    native.memory[rh.PRIMARY+offset] = int.from_bytes(self.assets['image'][offset:offset+4],'little')
            install,logs,_ = self.instance(native,clock)
            # Prior stages are outside this seam; retain the real final indices.
            for _ in range(716): logs.switch(read_allowed=lambda _:False,expected_stores=[])
            install.index = logs.gate.index
            install.final_confirmed = True
            if failure:
                def hook():
                    if install.phase==failure: native.fault = 'blank'
                native.hook = hook
                with self.assertRaises(ValueError): install.boot_and_health()
                self.assertNotIn('health',install.results)
                self.assertEqual(install.exit_port.release_attempted,failure=='ORIGINAL_BOOT_RELEASE')
            else:
                install.boot_and_health()
                self.assertEqual(install.results['health']['result'],'R2_RUNTIME_HEALTH_OBSERVED')
                self.assertEqual(logs.gate.index,720)
                self.assertTrue(install.released)
            count = len(native.write_log)
            self.assertEqual(count,7 if failure=='ORIGINAL_BOOT_RESET' else 13)
            with self.assertRaises(ValueError): install.boot_and_health()
            self.assertEqual(len(native.write_log),count)


if __name__=='__main__': unittest.main()
