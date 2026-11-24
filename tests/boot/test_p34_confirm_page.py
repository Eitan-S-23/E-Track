import os
from pathlib import Path
import sys
import unittest

ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT/'Tools/ota'))
import p34_confirm_page as core
from recovery_confirm.page_port import PagePort

BEFORE=(ROOT/'.cache/p34-host-nor-rebuild1/bcb-before.bin').read_bytes()[:128]
BOOT=(ROOT/'.cache/p34-native-acquire1/boot-readback.bin').read_bytes()
IMAGE=(ROOT/'.cache/p34-recovery-sources1/r2-a.bin').read_bytes()


class Clock:
    def __init__(self):self.value=0.
    def __call__(self):return self.value
    def sleep(self,seconds):self.value+=seconds


class EEPROM:
    host_only=True
    def __init__(self,clock,fault=None,page=1,prefix=0):
        self.clock,self.fault,self.fault_page,self.prefix=clock,fault,page,prefix
        self.data=bytearray(BEFORE+b'R'*128)
        self.pages=[];self.reads=[];self.acks=[];self.busy_until=0
    def read(self,address,size,timeout):
        assert 0<timeout<=15 and size in (8,64)
        self.reads.append((address,size,self.clock()))
        if size==8 and len(self.pages)==self.fault_page and self.fault=='read-error':raise OSError('read STOP unknown')
        return bytes(self.data[address:address+size])
    def page(self,address,data,timeout):
        assert len(data)==8 and address%8==0 and 0<timeout<=15
        self.pages.append((address,bytes(data),self.clock()))
        fault=self.fault if len(self.pages)==self.fault_page else None
        take=0 if self.fault=='protected' else self.prefix if fault=='prefix' else 8
        self.data[address:address+take]=data[:take]
        self.busy_until=self.clock()+.005
        stop=self.clock()
        if fault=='deadline':self.clock.value+=61
        return dict(status=-1 if fault in ('prefix','error') else 0,
                    released=fault!='release',stop_upper=None if fault=='stop' else stop+1 if fault=='future-stop' else stop)
    def ack(self,timeout):
        assert 0<timeout<=15
        self.acks.append(self.clock())
        if self.fault=='busy' and len(self.pages)==self.fault_page:return False
        return self.clock()>=self.busy_until


class PageTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.dll,cls.fn=core.bind(Path(os.environ['P34_CONFIRM_DLL']))
        proposed=[]
        result=core.confirm(cls.fn,BEFORE,BOOT,IMAGE,lambda a,n:BEFORE[a:a+n],
                            lambda a,d:(proposed.append((a,d)) or -1))
        assert result['status']==0 and len(proposed)==1
        cls.address,cls.target=proposed[0]
    def make(self,fault=None,page=1,prefix=0):
        clock=Clock();io=EEPROM(clock,fault,page,prefix)
        port=PagePort(io,self.address,self.target,clock=clock,sleep=clock.sleep)
        return clock,io,port
    def execute(self,port,image=IMAGE):return core.confirm(self.fn,BEFORE,BOOT,image,port.read,port.write)
    def protected(self,io):
        other=64 if self.address==0 else 0
        self.assertEqual(bytes(io.data[other:other+64]),BEFORE[other:other+64])
        self.assertEqual(bytes(io.data[128:]),b'R'*128)

    def test_actual_preimage_through_original_core_and_eight_pages(self):
        clock,io,port=self.make();result=self.execute(port)
        self.assertEqual(result['status'],1)
        self.assertEqual(len(io.pages),8);self.assertEqual(port.attempts,1)
        self.assertEqual([x[0] for x in io.pages],list(range(self.address,self.address+64,8)))
        self.assertEqual(bytes(io.data[self.address:self.address+64]),self.target)
        self.assertEqual(int.from_bytes(self.target[28:32],'little'),30276)
        self.assertTrue(all(ack>=page[2]+.005 for ack,page in zip(io.acks,io.pages)))
        self.protected(io)

    def test_current_old_app_never_reaches_eeprom_io(self):
        _,io,port=self.make()
        old=(ROOT/'.cache/p34-native-image1/app-readback.bin').read_bytes()
        self.assertEqual(self.execute(port,old)['status'],-1)
        self.assertFalse(io.pages);self.assertFalse(io.reads)

    def test_wrong_record_and_replay_do_not_emit_pages(self):
        _,io,port=self.make()
        self.assertEqual(port.write(self.address^64,self.target),-1)
        self.assertFalse(io.pages)
        _,io,port=self.make();self.assertEqual(self.execute(port)['status'],1)
        count=len(io.pages);self.assertEqual(port.write(self.address,self.target),-1)
        self.assertEqual(len(io.pages),count)

    def test_protected_writes_fail_by_readback_without_retry(self):
        _,io,port=self.make('protected');result=self.execute(port)
        self.assertEqual(result['status'],0)
        self.assertEqual(bytes(io.data[:128]),BEFORE)
        self.assertLess(len(io.pages),8);self.protected(io)

    def test_delivered_error_is_arbitrated_not_assumed_unwritten(self):
        for page in range(1,9):
            with self.subTest(page=page):
                _,io,port=self.make('error',page);result=self.execute(port)
                self.assertEqual(result['status'],1 if page==8 else 0)
                self.assertEqual(len(io.pages),page);self.assertTrue(port.observe_allowed)
                self.assertIsNotNone(port.error);self.protected(io)

    def test_all_eight_page_prefix_tears_use_actual_surviving_bytes(self):
        for page in range(1,9):
            for prefix in range(8):
                with self.subTest(page=page,prefix=prefix):
                    _,io,port=self.make('prefix',page,prefix);result=self.execute(port)
                    expected=1 if bytes(io.data[self.address:self.address+64])==self.target else 0
                    self.assertEqual(result['status'],expected)
                    self.assertEqual(len(io.pages),page);self.protected(io)

    def test_unknown_stop_busy_or_read_failure_blocks_observer(self):
        for fault in ('stop','release','future-stop','busy','read-error','deadline'):
            with self.subTest(fault=fault):
                _,io,port=self.make(fault);result=self.execute(port)
                self.assertEqual(result['status'],-2)
                self.assertEqual(len(io.pages),1);self.assertFalse(port.observe_allowed)
                if fault in ('stop','release','future-stop','deadline'):self.assertFalse(io.acks)
                self.protected(io)

    def test_short_wait_and_backward_clock_stop_payload_and_observation(self):
        clock,io,port=self.make();port.sleep=lambda seconds:None
        self.assertEqual(self.execute(port)['status'],-2);self.assertFalse(io.acks)
        clock,io,port=self.make();clock.value=-1
        self.assertEqual(self.execute(port)['status'],-2)
        self.assertFalse(io.pages);self.assertFalse(io.reads)
        clock.value=0
        with self.assertRaises(ValueError):port.read(0,64)

    def test_initial_read_failure_permanently_blocks_same_port_mutations(self):
        _,io,port=self.make();original=io.read
        def failed(address,size,timeout):
            io.reads.append((address,size,io.clock()))
            raise OSError('STOP unknown')
        io.read=failed
        self.assertEqual(self.execute(port)['status'],-2)
        self.assertIn('STOP unknown',port.error)
        io.read=original
        counts=(len(io.reads),len(io.pages),len(io.acks))
        self.assertEqual(port.write(self.address,self.target),-1)
        with self.assertRaises(ValueError):port.read(0,64)
        self.assertEqual((len(io.reads),len(io.pages),len(io.acks)),counts)
        self.assertIn('STOP unknown',port.error)


if __name__=='__main__':unittest.main()
