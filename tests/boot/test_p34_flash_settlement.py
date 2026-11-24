import copy
import io
from pathlib import Path
import sys
import unittest
from unittest import mock

ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT/'Tools/ota'));sys.path.insert(0,str(ROOT/'tests/boot'))
import p34_flash_settlement as run
from test_p34_online_log_probe import LoggingSDK,PathModel
import test_p34_control_probe as controls


class Tests(unittest.TestCase):
    def model(self,fault=None):
        expected=run.EXPECTED.read_bytes()[:6144]
        context=run.cli.Store(ROOT).read(run.AREA/'worker.json')['component_results']['entry']['context']
        class Port:
            def __init__(self):
                self.memory=dict.fromkeys(run.META,0)
                self.memory.update(run.flash.CLOCK)
                self.memory.update({run.flash.DHCSR:0x30003,run.flash.PAUSE:0x1000,
                                    run.flash.IDCODE:0x70083347,run.flash.FSIZE:1024,
                                    run.flash.BANKS[0][1]:0x20,run.flash.BANKS[0][2]:1,
                                    run.flash.BANKS[1][2]:0x80})
                self.reads=[]
            def read32(self,address):return self.memory[address]
            def read_bytes(self,address,size):
                self.reads.append((address,size));offset=address-0x08010000
                raw=bytearray(expected[offset:offset+size])
                if fault=='word' and offset==4096:raw[0x224]^=1
                return bytes(raw)
        class Control:
            def initial(self):return dict(halted=True,lockup=False,reset_sticky=False,dhcsr_control=3,
                vtor=0x08010000,comparators=[0]*6,debug_apb1_frz=0x1000)
            def context(self):return dict(context,msp=context['msp']+4) if fault=='context' else context
        port=Port();sealed=[];saved=[]
        if fault=='busy':port.memory[run.flash.BANKS[0][1]]=1
        if fault=='error':port.memory[run.flash.BANKS[0][1]]=0x24
        if fault=='reset':port.memory[run.flash.DHCSR]|=0x02000000
        def seal(reads,stores,bind):
            sealed.append((stores,bind))
            if fault=='seal':raise ValueError('injected seal failure')
        return port,Control(),expected,context,seal,saved,sealed

    def test_exact6k_observed_without_repair_or_reset(self):
        port,control,expected,context,seal,saved,sealed=self.model()
        result=run.capture(port,control,expected,context,seal,saved.append,bounded=lambda f,*a:f(*a))
        self.assertEqual(result['result'],'PARTIAL_FLASH_SETTLED_READ_ONLY')
        self.assertEqual(saved,[expected])
        self.assertEqual(result['next_address'],0x08011228)
        self.assertFalse(result['repair_admitted'])
        self.assertEqual([len(stores) for stores,_ in sealed],[4,0,4])
        self.assertTrue(all(a==run.DCRSR and v in (15,16,17,20) for stores,_ in sealed for a,v in stores))

    def test_busy_error_reset_context_or_seal_stop_before_flash_reads(self):
        for fault in ('busy','error','reset','context','seal'):
            port,control,expected,context,seal,saved,sealed=self.model(fault)
            with self.subTest(fault=fault),self.assertRaises(ValueError):
                run.capture(port,control,expected,context,seal,saved.append,bounded=lambda f,*a:f(*a))
            self.assertFalse(port.reads)
            self.assertFalse(saved)

    def test_last_word_difference_is_archived_but_not_accepted(self):
        port,control,expected,context,seal,saved,sealed=self.model('word')
        with self.assertRaises(ValueError):run.capture(port,control,expected,context,seal,saved.append,bounded=lambda f,*a:f(*a))
        self.assertEqual(len(saved[0]),6144)
        self.assertNotEqual(saved[0],expected)
        self.assertEqual(len(sealed),1)

    def test_native_retained_close_connect_and_optional_read_failures(self):
        for fault in (None,'connect','read'):
            sdk=LoggingSDK([PathModel('sdk','')])
            with mock.patch('recovery_entry.native_probe.guarded',side_effect=lambda f,*a,**k:f(*a)):
                dap=run.base.Dap(sdk,sdk.paths[0],'unused-model-project.jlink',io.BytesIO())
                observer=run.RetainedObservation(dap,lambda *a,**k:None,seconds=60)
                if fault=='connect':
                    original=dap.connected
                    def connected():
                        if dap.ready:raise ValueError('post-acquisition connection failure')
                        return original()
                    dap.connected=connected
                    with self.assertRaises(ValueError):observer.connect()
                else:
                    observer.connect()
                    if fault=='read':
                        def fail():raise OSError('retained DP read failure')
                        dap._power_ready=fail
                        with self.assertRaises(OSError):observer.close()
                    else:observer.close()
                observer.close()
            self.assertEqual(sum(name=='JLINKARM_Close' for name,_ in sdk.calls),1)
            self.assertTrue(dap.close_returned)
            self.assertFalse(dap.metadata['dp_restored'])
            self.assertEqual(sdk.dp,0xf0000040)
            self.assertEqual(sdk.target_accesses,0)

    def test_real_dap_control_words_capture_is_covered_by_exact_seals(self):
        fixture,_,expected,context,_,_,_=self.model()
        sdk=controls.SDK()
        sdk.memory.update(fixture.memory)
        sdk.memory.update({0xe000ef34:context['fpccr'],0x40002c00:0})
        for offset in range(0,len(expected),4):
            sdk.memory[0x08010000+offset]=int.from_bytes(expected[offset:offset+4],'little')
        sdk.core.update({15:context['pc'],16:context['xpsr'],17:context['msp'],20:context['control']<<24})
        reads=[];stores=[];seals=[]
        read=sdk.JLINKARM_CORESIGHT_ReadAPDPReg.callback
        write=sdk.JLINKARM_CORESIGHT_WriteAPDPReg.callback
        def read_call(index,ap,out):
            if (index,ap,sdk.bank)==(3,1,0):reads.append(sdk.tar)
            return read(index,ap,out)
        def write_call(index,ap,value):
            if (index,ap,sdk.bank)==(3,1,0):stores.append((sdk.tar,value))
            return write(index,ap,value)
        sdk.JLINKARM_CORESIGHT_ReadAPDPReg.callback=read_call
        sdk.JLINKARM_CORESIGHT_WriteAPDPReg.callback=write_call
        def seal(allowed,wanted,bind):
            self.assertTrue(set(reads).issubset(allowed),set(reads)-allowed)
            self.assertEqual(stores,list(wanted))
            seals.append((len(reads),len(stores),run.WFI in reads))
            reads.clear();stores.clear()
        with mock.patch('recovery_entry.native_probe.guarded',side_effect=lambda f,*a,**k:f(*a)):
            dap=run.base.Dap(sdk,'unused-model-sdk.log','unused-model-project.jlink',io.BytesIO())
            dap.open();dap.connect()
            observer=controls.Observer(dap)
            control=run.Control(dap,observer,lambda *a,**k:None,expected[0x400:0x460],retained=True)
            port=run.Words(dap,lambda *a,**k:None,reads=run.READS,write_allowed=lambda a,v:False,
                           seconds=90,guard=lambda f,*a,**k:f(*a))
            saved=[]
            result=run.capture(port,control,expected,context,seal,saved.append,
                               bounded=run.Boundary(port,lambda:150,guard=lambda f,*a,**k:f(*a)))
            control.close()
        self.assertEqual(saved,[expected])
        self.assertEqual(result['result'],'PARTIAL_FLASH_SETTLED_READ_ONLY')
        self.assertEqual([s[1] for s in seals],[4,0,4])
        self.assertTrue(seals[0][2])

    def test_control_return_over_reserve_stops_before_selector_reads_or_seal(self):
        port,control,expected,context,seal,saved,sealed=self.model()
        clock=[0.0];limits=[]
        port.check=lambda:90-clock[0]
        def guard(function,*args,seconds):
            limits.append(seconds)
            result=function(*args)
            clock[0]+=.02
            return result
        bounded=run.Boundary(port,lambda:60.01-clock[0],guard=guard)
        with mock.patch.object(control,'context',wraps=control.context) as selector:
            with self.assertRaises(ValueError):
                run.capture(port,control,expected,context,seal,saved.append,bounded=bounded)
            selector.assert_not_called()
        self.assertEqual(len(limits),1)
        self.assertTrue(0<limits[0]<=.010001)
        self.assertFalse(port.reads or saved or sealed)


if __name__=='__main__':unittest.main()
