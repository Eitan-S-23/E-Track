from pathlib import Path
import sys
import unittest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT/'Tools/ota'))
sys.path.insert(0,str(ROOT/'tests/boot'))
from recovery_confirm import r2_health as rh
from recovery_confirm.ap_journal import JournalSDK
from recovery_confirm.mutation_audit import SealedGate
from recovery_confirm.online_log import OnlineLog
from test_p34_mutation_audit import MemoryPath, record, META
from p34_eeprom_wire_model import Clock
import test_p34_online_log as online

IMAGE = (ROOT/'.cache/p34-recovery-sources1/r2-a.bin').read_bytes()
MAP = (ROOT/'.cache/p34-early-usb-r2/on/b/app-gcc/X-Track-App-GCC.map').read_bytes()


class Native(online.Native):
    def __init__(self,paths,clock,problem):
        super().__init__(paths)
        self.clock,self.problem = clock,problem
        self.ready_at = 3
        self.memory.update({a:0 for a in rh.READS})
        for offset in range(0x400,0x460,4):
            self.memory[rh.PRIMARY+offset] = int.from_bytes(IMAGE[offset:offset+4],'little')
        for offset in range(0x800,0x800+524,4):
            self.memory[rh.PRIMARY+offset] = int.from_bytes(IMAGE[offset:offset+4],'little')
        self.memory.update({rh.SD:1,rh.DIAG:1,rh.FLAGS:0x010104})
    def JLINKARM_CORESIGHT_ReadAPDPReg(self,index,ap,out):
        self.clock.value += .001
        now = self.clock.value
        self.memory[rh.VTOR] = rh.PRIMARY if now<self.ready_at or self.problem=='early' else rh.RUNTIME
        ticktime = min(now,10) if self.problem=='stuck' else now
        self.memory[rh.TICK] = int(ticktime*1000)
        health = (30000,30,1000,0,int(ticktime*100),int(ticktime*100),0,1,1)
        for i,value in enumerate(health): self.memory[rh.HEALTH+i*4] = value
        if now>10:
            if self.problem=='reset': self.memory[rh.DHCSR] |= 1<<25
            if self.problem=='halt': self.memory[rh.DHCSR] |= 1<<17
            if self.problem=='lockup': self.memory[rh.DHCSR] |= 1<<19
            if self.problem=='fault': self.memory[rh.CFSR] = 1
            if self.problem=='sd': self.memory[rh.SD] = 0
            if self.problem=='epoch': self.memory[rh.HEALTH+12] = 5000
            if self.problem=='flags': self.memory[rh.FLAGS] = 0x010103
            if self.problem=='feed': self.memory[rh.HEALTH+20] = 0
            if self.problem=='table': self.memory[rh.RUNTIME+4] ^= 2
        return super().JLINKARM_CORESIGHT_ReadAPDPReg(index,ap,out)


class Tests(unittest.TestCase):
    def make(self,problem=None):
        clock = Clock()
        paths = [MemoryPath(f'log-{i}','') for i in range(3)]
        native = Native(paths,clock,problem)
        dap = online.Dap(JournalSDK(native,lambda *a,**k:None,clock=clock))
        log = OnlineLog(dap,SealedGate(paths,META,record),lambda *a,**k:None,lambda:600-clock.value,clock=clock)
        log.switch(read_allowed=lambda _:False,expected_stores=[])
        monitor = rh.Monitor(dap,IMAGE,MAP,lambda:True,log,lambda:600-clock.value,
            clock=clock,sleep=clock.sleep,guard=lambda f,*a,**k:f(*a))
        return clock,native,log,monitor

    def test_ready_identity_and_30_second_progress_with_real_log_audit(self):
        clock,native,log,monitor = self.make()
        result = monitor.run()
        self.assertEqual(result['result'],'R2_RUNTIME_HEALTH_OBSERVED')
        self.assertGreaterEqual(result['seconds'],30)
        self.assertGreaterEqual(result['samples'],20)
        self.assertFalse(result['full_install_qualified'])
        self.assertFalse(result['eeprom_observed'])
        self.assertEqual(log.gate.cursor.target_writes,0)
        self.assertEqual(len(log.gate.records),2)
        log.verify_head()
        before = native.paths[2].data
        with self.assertRaises(ValueError): monitor.run()
        self.assertEqual(native.paths[2].data,before)

    def test_false_readiness_reset_fault_and_stalled_main_loop_never_succeed(self):
        for problem in ('reset','halt','lockup','fault','sd','epoch','flags','feed','stuck','early'):
            with self.subTest(problem=problem):
                _,_,log,monitor = self.make(problem)
                message = ('reset/halt/lockup' if problem in ('reset','halt','lockup') else
                           'fault status' if problem=='fault' else
                           'ready state/health epoch' if problem in ('sd','epoch','flags') else
                           'progress missing' if problem in ('feed','stuck') else 'readiness timeout')
                with self.assertRaisesRegex(ValueError,message): monitor.run()
                self.assertEqual(len(log.gate.records),1)
                self.assertIsNotNone(monitor.error)

    def test_wrong_map_image_or_runtime_table_rejected(self):
        for raw in (MAP[:-1],MAP+b'\n',MAP.replace(b'0x20053a9c',b'0x20053a90')):
            with self.assertRaises(ValueError): rh.verify_map(raw)
        _,native,_,monitor = self.make()
        native.memory[rh.RUNTIME+4] ^= 2
        with self.assertRaisesRegex(ValueError,'differs'): monitor.run()
        with self.assertRaises(ValueError):
            rh.Monitor(monitor.dap,IMAGE[:-4],MAP,lambda:True,monitor.logs,lambda:600)

    def test_bad_sleep_and_final_log_failures_are_not_health_completion(self):
        for problem in ('sleep','blank','new-blank'):
            _,native,log,monitor = self.make()
            if problem=='sleep': monitor.sleep = lambda _:None
            else: native.hook = lambda:setattr(native,'fault',problem)
            with self.assertRaises(ValueError): monitor.run()
            self.assertIsNotNone(monitor.error)
            self.assertEqual(native.switches,1 if problem=='sleep' else 2)

    def test_late_ready_and_sample_crossing_fixed_deadline_never_start_window(self):
        for problem in ('late','crossing'):
            clock,native,log,monitor = self.make()
            if problem=='late':
                native.ready_at = 120.1
            else:
                native.ready_at = 0
                original = native.JLINKARM_CORESIGHT_ReadAPDPReg
                crossed = [False]
                def read(index,ap,out):
                    address = native.tar
                    result = original(index,ap,out)
                    if not crossed[0] and (index,ap)==(3,1) and address==rh.TICK:
                        clock.value += 120
                        crossed[0] = True
                    return result
                native.JLINKARM_CORESIGHT_ReadAPDPReg = read
            with self.assertRaisesRegex(ValueError,'readiness timeout'): monitor.run()
            self.assertFalse(monitor.samples)
            self.assertEqual(len(log.gate.records),1)
            self.assertGreaterEqual(clock.value,120)


if __name__=='__main__': unittest.main()
