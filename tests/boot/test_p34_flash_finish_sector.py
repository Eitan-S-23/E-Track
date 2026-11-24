from pathlib import Path
import sys
import unittest

ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT/'Tools/ota'));sys.path.insert(0,str(ROOT/'tests/boot'))
import p34_flash_finish_sector as run
from test_p34_install_bridges import Buffer,Logged
from test_p34_mutation_audit import META,record
import test_p34_online_log as online
import test_p34_recovery_ports as model
from test_p34_flash_remainder import Tests as RemainderTests


class Tests(unittest.TestCase):
    def test_real_remainder_and_online_seal_or_failure_barrier(self):
        class Native(Logged,model.FlashSDK):pass
        partial=run.prior.EXPECTED.read_bytes()
        for failure in (None,'seal','delivered'):
            clock=model.Clock();native=Native(clock,partial,'delivered' if failure=='delivered' else None)
            native.memory[run.prior.flash.BANKS[0][2]]=1
            paths=[Buffer('sdk-'+str(i),'') for i in range(6)]
            native.initialize_log(paths)
            dap=online.Dap(run.prior.JournalSDK(native,lambda *a,**k:None,clock=clock))
            logs=run.prior.OnlineLog(dap,run.prior.SealedGate(paths,META,record),lambda *a,**k:None,
                                   lambda:150-clock.value,clock=clock)
            for _ in range(4):logs.switch(read_allowed=lambda _:False,expected_stores=[])
            if failure=='delivered':native.fault='delivered'
            if failure=='seal':native.hook=lambda:setattr(native,'fault','blank')
            if failure:
                with self.assertRaises((ValueError,OSError)):
                    run.complete_sector(dap,logs,partial,model.IMAGE,lambda:150-clock.value,
                                        clock=clock,sleep=clock.sleep,guard=lambda f,*a,**k:f(*a))
                self.assertFalse(logs.target_allowed())
                if failure=='delivered':self.assertEqual(native.write_log,[(0x40023c0c,0x34),(0x08011228,int.from_bytes(model.IMAGE[0x1228:0x122c],'little'))])
            else:
                result=run.complete_sector(dap,logs,partial,model.IMAGE,lambda:150-clock.value,
                                           clock=clock,sleep=clock.sleep,guard=lambda f,*a,**k:f(*a))
                self.assertEqual(result['result'],'THIRD_SECTOR_FINISHED_AUDITED')
                self.assertEqual(result['trace']['target_writes'],750)
                self.assertEqual(logs.gate.index,5)
                self.assertEqual(native.flash[4096:6144],model.IMAGE[4096:6144])
            self.assertEqual(native.flash[:4096],partial[:4096])
            self.assertEqual(native.flash[6144:],partial[6144:])

    def test_partial_prewrite_drift_busy_owner_and_mode_have_no_stores(self):
        partial=run.prior.EXPECTED.read_bytes()
        for fault in ('bytes','busy','mode','owner'):
            clock=model.Clock();native=model.FlashSDK(clock,partial)
            native.memory[run.prior.flash.BANKS[0][2]]=1
            if fault=='bytes':native.flash[4096]^=1
            if fault=='busy':native.memory[run.prior.flash.BANKS[0][1]]=1
            if fault=='mode':native.memory[run.prior.flash.BANKS[0][2]]=0x80
            port=run.PartialSector(model.Dap(native),model.IMAGE,partial,lambda:fault!='owner',lambda *a,**k:None,
                                   clock=clock,sleep=clock.sleep,guard=lambda f,*a,**k:f(*a))
            with self.subTest(fault=fault),self.assertRaises(ValueError):port.run()
            self.assertFalse(native.write_log)
            before=len(native.calls)
            with self.assertRaises(ValueError):port.run()
            self.assertEqual(len(native.calls),before)


if __name__=='__main__':unittest.main()
