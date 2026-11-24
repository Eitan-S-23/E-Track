from pathlib import Path
import sys
import unittest

ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT/'Tools/ota'));sys.path.insert(0,str(ROOT/'tests/boot'))
from recovery_confirm.r2_checkpoint import Checkpoint,LOG_COUNT
from p34_finalized_vtor_capture import CaptureError
from recovery_confirm import r2_health as health
from recovery_confirm.ap_journal import JournalSDK
from recovery_confirm.mutation_audit import SealedGate
from recovery_confirm.online_log import OnlineLog
from test_p34_install_bridges import Buffer,Logged
from test_p34_mutation_audit import record,META
import test_p34_recovery_ports as model
import test_p34_online_log as online

MAP=(ROOT/'.cache/p34-early-usb-r2/on/b/app-gcc/X-Track-App-GCC.map').read_bytes()


class Native(Logged,model.FlashSDK):
    def __init__(self,clock,image,problem):
        super().__init__(clock,image)
        self.problem,self.injected=problem,False
        self.memory.update({health.DHCSR:0,health.VTOR:health.RUNTIME,health.CFSR:0,health.HFSR:0,
                            health.FLAGS:0x010104,health.SD:1,health.DIAG:1,health.FAULT:0})
        for offset in range(0,65536,4):self.memory[0x08000000+offset]=int.from_bytes(model.BOOT[offset:offset+4],'little')
        if problem=='boot':self.memory[0x08000000]^=1

    def JLINKARM_CORESIGHT_ReadAPDPReg(self,index,ap,out):
        address=self.tar
        now=self.clock.value
        self.memory[health.TICK]=int(now*1000)
        values=(30000,30,1000,0,int(now*100),int(now*100),0,1,1)
        for i,value in enumerate(values):self.memory[health.HEALTH+4*i]=value
        if self.problem=='reset' and not self.injected and (index,ap)==(3,1) and address==0x08014000:
            self.injected=True;self.memory[health.DHCSR]|=0x02000000
        result=super().JLINKARM_CORESIGHT_ReadAPDPReg(index,ap,out)
        if (index,ap)==(3,1) and address==health.DHCSR:self.memory[health.DHCSR]&=~0x02000000
        return result


class Tests(unittest.TestCase):
    def make(self,name='r2-a.bin',problem=None):
        image=(ROOT/'.cache/p34-recovery-sources1'/name).read_bytes()
        clock=model.Clock();paths=[Buffer('checkpoint-'+str(i),'') for i in range(LOG_COUNT)]
        native=Native(clock,image,problem);native.initialize_log(paths)
        dap=online.Dap(JournalSDK(native,lambda *a,**k:None,clock=clock))
        logs=OnlineLog(dap,SealedGate(paths,META,record),lambda *a,**k:None,lambda:900-clock.value,clock=clock)
        logs.switch(read_allowed=lambda _:False,expected_stores=[])
        saved={}
        def archive(name,raw):
            if problem=='archive':raise OSError('archive failure')
            self.assertNotIn(name,saved);saved[name]=raw
        checkpoint=Checkpoint(dap,logs,lambda:900-clock.value,archive,image,model.BOOT,MAP,
            connection_generation='test-one',clock=clock,sleep=clock.sleep,guard=lambda f,*a,**k:f(*a))
        return checkpoint,native,logs,saved

    def test_real_reader_words_health_and_24_log_layout_for_both_images(self):
        for name,version in (('r2-a.bin',30276),('r2-b.bin',30277)):
            cp,native,logs,saved=self.make(name)
            result=cp.run()
            self.assertEqual(result['result'],'R2_IMAGE_BOOT_HEALTH_CHECKPOINT')
            self.assertEqual(result['version'],version)
            self.assertEqual(result['health']['version_code'],version)
            self.assertEqual(saved,dict(app=cp.image,boot=model.BOOT))
            self.assertEqual(logs.gate.index,23)
            self.assertEqual(len(logs.gate.records),23)
            self.assertFalse(native.write_log)
            self.assertFalse(result['native_close_audited'])
            self.assertFalse(result['physical_bcb_observed'])
            self.assertFalse(result['backup_observed'])
            before=len(native.calls)
            with self.assertRaises(ValueError):cp.run()
            self.assertEqual(len(native.calls),before)

    def test_consumed_reset_archive_and_boot_errors_latch_without_replay(self):
        for problem in ('reset','archive','boot'):
            cp,native,logs,saved=self.make(problem=problem)
            with self.assertRaises((ValueError,RuntimeError,OSError)):cp.run()
            self.assertIsNotNone(cp.error)
            self.assertFalse(native.write_log)
            self.assertFalse(cp.active)
            self.assertIsNone(cp.monitor)
            if problem=='reset':
                self.assertTrue(cp.reader.reset_seen)
                self.assertEqual(native.memory[health.DHCSR]&0x02000000,0)
            before=len(native.calls)
            with self.assertRaises(ValueError):cp.run()
            self.assertEqual(len(native.calls),before)

    def test_lost_owner_seal_and_unknown_identity_reject(self):
        cp,native,logs,_=self.make()
        native.hook=lambda:setattr(native,'fault','blank')
        with self.assertRaisesRegex(CaptureError,'reader failed; no automatic retry'):cp.run()
        self.assertIsNotNone(cp.error)
        self.assertFalse(cp.active)
        self.assertFalse(logs.target_allowed())
        self.assertFalse(native.write_log)
        cp,native,logs,_=self.make()
        cp.remaining=lambda:90
        before=len(native.calls)
        with self.assertRaises((ValueError,RuntimeError)):cp.run()
        self.assertEqual(len(native.calls),before)
        cp,native,logs,_=self.make()
        before=len(native.calls)
        with self.assertRaises(ValueError):
            Checkpoint(cp.dap,logs,lambda:900,lambda *a:None,cp.image[:-4],cp.boot,MAP,connection_generation='bad')
        self.assertEqual(len(native.calls),before)


if __name__=='__main__':unittest.main()
