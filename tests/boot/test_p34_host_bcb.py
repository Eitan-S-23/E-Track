import ctypes
import contextlib
import os
from pathlib import Path
import struct
import sys
import unittest
from unittest import mock
import zlib

ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT/"Tools/ota"))
sys.path.insert(0,str(ROOT/"tests/boot"))
from recovery_entry import host_bcb as hb
import test_p34_control_probe as controls


def record(sequence):
    value=bytearray(64)
    struct.pack_into("<I",value,0,0x43425445)
    value[4:8]=bytes((1,4,3,0))
    struct.pack_into("<H",value,8,sequence)
    struct.pack_into("<I",value,28,30275)
    struct.pack_into("<I",value,60,zlib.crc32(value[:60]))
    return bytes(value)


class Model:
    def __init__(self,raw=None):
        raw=raw or record(8)+record(7)+record(8)+record(7)
        self.bits=[]
        for offset in range(0,256,64):
            self.bits.extend((0,0,0))
            self.bits.extend((v>>i)&1 for v in raw[offset:offset+64] for i in range(7,-1,-1))
        self.cursor,self.time=0,0
        self.level={6:1,7:1}; self.stores=[]; self.edges=[]
        self.fail_at=None; self.stuck=False
    def clock(self): self.time+=.00002; return self.time
    def set(self,pin,high):
        if pin==6 and high and not self.level[6]: self.edges.append(self.level[7])
        self.level[pin]=high
        self.stores.append((pin,high))
        if len(self.stores)==self.fail_at: raise OSError("uncertain edge after delivery")
    def read(self,pin):
        if pin==6:
            if self.stuck: raise OSError("SCL held low")
            return 1
        value=self.bits[self.cursor]; self.cursor+=1; return value


class HostBcbTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.library=ctypes.CDLL(os.environ["P34_BCB_DLL"])
        cls.function=hb.bind(cls.library)
    def run_model(self,model,seconds=300):
        return hb.capture(self.function,model,seconds=seconds,clock=model.clock,sleep=lambda _:None)

    def test_existing_c_protocol_exact_read_only_wire_sequence(self):
        model=Model(); result=self.run_model(model)
        self.assertEqual(result["result"],"HOST_BCB_CAPTURED")
        self.assertEqual(result["selected"]["cur_vcode"],30275)
        self.assertEqual(result["active"],1)
        self.assertEqual((model.cursor,len(model.edges)),(2060,2420))
        byte=lambda start:sum(v<<(7-i) for i,v in enumerate(model.edges[start:start+8]))
        for slot in range(4):
            start=slot*605
            self.assertEqual([byte(start),byte(start+9),byte(start+19)],[0xa0,0x40 if slot%2 else 0,0xa1])
            self.assertEqual([model.edges[start+28+i*9+8] for i in range(64)],[0]*63+[1])
        self.assertEqual(model.level,{6:1,7:1})

    def test_no_more_pin_changes_after_uncertain_edge(self):
        normal=Model(); self.run_model(normal)
        for position in (1,2,17,100,len(normal.stores)//2,len(normal.stores)-1,len(normal.stores)):
            model=Model(); model.fail_at=position
            result=self.run_model(model)
            self.assertEqual(result["result"],"FAILED")
            self.assertIn("uncertain edge",result["callback_error"])
            self.assertEqual(len(model.stores),position)

    def test_all_twelve_address_pointer_ack_failures_do_not_retry(self):
        for transaction in range(4):
            for ack in range(3):
                model=Model(); model.bits[transaction*515+ack]=1
                result=self.run_model(model)
                self.assertEqual(result["result"],"FAILED")
                self.assertEqual(result["completed"],transaction)
                self.assertEqual(model.cursor,transaction*515+ack+1)
                self.assertEqual(model.level,{6:1,7:1})

    def test_global_deadline_and_stuck_scl_retain_failure(self):
        model=Model(); result=self.run_model(model,seconds=.002)
        self.assertEqual(result["result"],"FAILED")
        self.assertIn("deadline",result["callback_error"])
        model=Model(); model.stuck=True
        result=self.run_model(model)
        self.assertIn("SCL held low",result["callback_error"])
        self.assertEqual(model.cursor,0)

    def test_base_exceptions_do_not_escape_callback_or_allow_cleanup(self):
        for exception in (KeyboardInterrupt,SystemExit):
            model=Model()
            old=model.set
            def fail(pin,high): old(pin,high); raise exception("injected")
            model.set=fail
            result=self.run_model(model)
            self.assertEqual(result["result"],"FAILED")
            self.assertIn(exception.__name__,result["callback_error"])
            self.assertEqual(len(model.stores),1)
            self.assertIsNone(result["internal_address_pointer_changed"])

    def test_post_arbitration_deadline_is_checked(self):
        model=Model()
        def delayed(*args):
            result=self.function(*args); model.time+=400; return result
        result=hb.capture(delayed,model,clock=model.clock,sleep=lambda _:None)
        self.assertEqual(result["result"],"FAILED")
        self.assertIn("deadline",result["callback_error"])

    def test_pair_change_is_not_stable(self):
        result=self.run_model(Model(record(8)+record(7)+record(9)+record(7)))
        self.assertEqual(result["result"],"FAILED")
        self.assertEqual(result["native_result"],-2)

    def test_two_invalid_records_stay_invalid(self):
        result=self.run_model(Model(bytes([255])*256))
        self.assertEqual(result["result"],"HOST_BCB_CAPTURED")
        self.assertEqual(result["first_pair_valid"],[False,False])
        self.assertFalse(result["bcb_admitted"])
        self.assertIsNone(result["selected"])

    def test_sequence_wrap_and_tie_follow_existing_arbiter(self):
        for a,b,expected in ((65535,0,2),(0,65535,1),(9,9,1),(7,8,2)):
            pair=record(a)+record(b)
            self.assertEqual(self.run_model(Model(pair*2))["active"],expected)

    def test_gpio_adapter_excludes_extra_pins_and_payload_registers(self):
        fixture=controls.ControlTests(); fixture.setUp()
        control=fixture.ctrl
        fixture.sdk.memory[controls.DHCSR]|=0x20000
        fixture.sdk.memory[controls.PAUSE]=0x1000
        raw=controls.policy_tests.media()["raw"]
        raw.update(gpiob_mode=0x5000,gpiob_type=0xc0,gpiob_output=0xc0,gpiob_input=0xc0,
                   crm_ahben1=2,debug_apb1_frz=0x1000,dma1_3=1,dma2_4=1,
                   display_dma_peripheral=0x4001300c,sd_dma_peripheral=0x50061080)
        for name,address in (("gpiob_mode",0x40020400),("gpiob_type",0x40020404),
                             ("gpiob_output",0x40020414),("gpiob_input",0x40020410)):
            fixture.sdk.memory[address]=raw[name]
        pins=hb.Pins(control,raw,lambda *a,**k:None)
        for pin,high in ((5,1),(8,0),(6,2),(7,-1)):
            with self.assertRaises(ValueError): pins.set(pin,high)
        self.assertFalse(any(n=="JLINKARM_CORESIGHT_WriteAPDPReg" and a[:2]==(3,1) for n,a in fixture.sdk.calls))
        fixture.sdk.memory[controls.DHCSR]&=~0x20000
        with self.assertRaisesRegex(ValueError,"lost retained halt"): pins.set(6,0)

    def run_native_worker(self,fault=None):
        import p34_host_bcb as run
        store=run.cli.Store(ROOT)
        out=store.checked(Path(os.environ["P34_TEST_OUT"])/("case-worker-"+(fault or "ok")))
        run.preflight(store,out)
        sdk=controls.SDK(); model=Model()
        original=store.read(ROOT/".cache/p34-entry-wfi1/worker.json")
        context=original["context"]
        for name,address in controls.REGISTERS.items(): sdk.memory[address]=original["state_samples"][-1]["raw"][name]
        sdk.memory[controls.DHCSR]=0x30001
        sdk.memory[0xe000ef34]=context["fpccr"]
        sdk.memory[0x40020410]=sdk.memory[0x40020414]
        sdk.core.update({15:context["pc"],16:context["xpsr"],17:context["msp"],20:context["control"]<<24})
        sdk.sample_data=False
        repeated_reads=[0]
        stores_at_fault=[]
        write_original=sdk.JLINKARM_CORESIGHT_WriteAPDPReg.callback
        read_original=sdk.JLINKARM_CORESIGHT_ReadAPDPReg.callback
        def write(*args):
            address=sdk.tar
            result=write_original(*args)
            if args[:2]==(3,1) and address in (0x40020418,0x40020428):
                mask=args[2]; pin={0x40:6,0x80:7}[mask]; high=int(address==0x40020418)
                model.set(pin,high)
                if high: sdk.memory[0x40020414]|=mask
                else: sdk.memory[0x40020414]&=~mask
                sdk.memory[0x40020410]=sdk.memory[0x40020414]
            return result
        def read(*args):
            if args[:2]==(3,1) and sdk.tar==0x40020410:
                if len(model.edges)==19: repeated_reads[0]+=1
                if ((fault=="missed-start" and len(model.edges)==19 and repeated_reads[0]>=3) or
                        (fault=="rw-bit" and len(model.edges)==26)):
                    if not stores_at_fault: stores_at_fault.append(len(model.stores))
                    ctypes.cast(args[2],ctypes.POINTER(ctypes.c_uint32))[0]=sdk.memory[0x40020410]&~0x80
                    sdk.tar+=4; return 0
            if args[:2]==(3,1) and sdk.tar==0x40020410 and sdk.sample_data:
                sdk.sample_data=False
                value=(sdk.memory[0x40020410]&~0x80)|(model.read(7)<<7)
                ctypes.cast(args[2],ctypes.POINTER(ctypes.c_uint32))[0]=value
                sdk.tar+=4; return 0
            return read_original(*args)
        sdk.JLINKARM_CORESIGHT_WriteAPDPReg.callback=write
        sdk.JLINKARM_CORESIGHT_ReadAPDPReg.callback=read
        OriginalPins=hb.Pins
        class Pins(OriginalPins):
            def read(self,pin):
                if pin==7: sdk.sample_data=True
                return super().read(pin)
        class Observer(controls.Observer):
            def __init__(self,dap,emit,seconds): super().__init__(dap)
            def connect(self): self.dap.open(); self.dap.connect()
            def _check(self): pass
        dll=store.checked(os.environ["P34_BCB_DLL"])
        store.write(out/"plan.json",dict(inputs=[run.cli.record(p) for p in run.SOURCES],out=str(out),
            native_history_approved=str(run.base.HISTORY),reader_dll=run.cli.record(dll)))
        with mock.patch.object(run.base,"in_job",return_value=True), \
             mock.patch.object(run.base,"native_presence",return_value=dict(usb=[],debugger_processes=[])), \
             mock.patch.object(run.base,"guarded",return_value=sdk), \
             mock.patch.object(run.base,"Observation",Observer), \
             mock.patch.object(run.os,"add_dll_directory",return_value=contextlib.nullcontext()), \
             mock.patch.object(hb,"Pins",Pins), \
             mock.patch("recovery_entry.native_probe.guarded",side_effect=lambda fn,*a,**k:fn(*a)):
            self.assertEqual(run.worker(store,out),1 if fault else 0)
        result=store.read(out/"worker.json")
        return result,model,stores_at_fault

    def test_full_worker_with_native_gpio_model(self):
        result,model,_=self.run_native_worker()
        self.assertEqual(result["result"],"HOST_BCB_READ_VERIFIED_RETAINED")
        self.assertTrue(result["bus_released_high"])
        self.assertEqual((model.cursor,len(model.edges)),(2060,2420))
        self.assertTrue(result["close_returned"])

    def test_missed_repeated_start_or_rw_bit_never_sends_payload_or_stop(self):
        for fault,limit in (("missed-start",19),("rw-bit",26)):
            result,model,at_fault=self.run_native_worker(fault)
            self.assertEqual(result["result"],"FAILED")
            self.assertEqual(len(model.edges),limit)
            if fault=="missed-start":
                self.assertEqual(len(model.stores),at_fault[0])
                self.assertIn("physical pre-level",result["capture"]["callback_error"])
            else:
                self.assertIn("master SDA bit",result["capture"]["callback_error"])
            self.assertFalse(result.get("bus_released_high",False))
            self.assertTrue(result["close_returned"])


if __name__=="__main__": unittest.main()
