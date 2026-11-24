import os
from pathlib import Path
import sys
from types import SimpleNamespace
import unittest
import ctypes

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT/'Tools/ota'))
sys.path.insert(0,str(ROOT/'tests/boot'))
import test_p34_recovery_ports as model
from recovery_confirm.eeprom_sequence import Wire, stores
from recovery_confirm.ap_journal import JournalSDK
from recovery_confirm.mutation_audit import SealedGate
from recovery_confirm.online_log import OnlineLog
from test_p34_mutation_audit import MemoryPath, record, META
import test_p34_online_log as online_model


class Tests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.dll,cls.fn = model.core.bind(Path(os.environ['P34_CONFIRM_DLL']))
        cls.plan = model.confirm_io.draft(cls.fn,model.BEFORE*2,model.BOOT,model.IMAGE)

    def make(self,fail=None):
        clock = model.Clock()
        slave = model.Slave(clock,model.BEFORE+b'R'*128)
        sdk = model.SDK(slave)
        dap = model.Dap(sdk)
        calls = []
        class Log:
            def __init__(self):
                self.dap = dap
                self.gate = SimpleNamespace(index=1,paths=tuple(range(32)),boundary=[])
                self.error = None
                self.start = 0
            def verify_head(self): pass
            def target_allowed(self): return self.error is None
            def switch(self,*,read_allowed,expected_stores):
                actual = tuple((row[3],row[4]) for row in sdk.calls[self.start:]
                               if row[:3] == ('write',3,1))
                assert actual == expected_stores
                assert all(read_allowed(row[3]) for row in sdk.calls[self.start:] if row[:3] == ('read',3,1))
                self.start = len(sdk.calls)
                calls.append(actual)
                if len(calls)-1 == fail:
                    self.error = 'injected seal failure'
                    raise ValueError(self.error)
                self.gate.index += 1
                return dict(target_writes=len(actual),log_file_closed=1,native_close=0)
        log = Log()
        wire = Wire(dap,sdk.original,self.plan,lambda:True,lambda *a,**k:None,log,
                    lambda:3600-clock.value,lambda *a:None,clock=clock,sleep=clock.sleep,guard=lambda f,*a,**k:f(*a))
        return clock,slave,sdk,wire,log,calls

    def test_original_c_transaction_real_words_and_slave_match_all_30_oracles(self):
        clock,slave,sdk,wire,log,calls = self.make()
        result = model.confirm_io.Transaction(self.fn,self.plan,wire,clock=clock,sleep=clock.sleep).run()
        self.assertEqual(result['result'],'EEPROM_BYTES_CONFIRMED',result)
        self.assertIsNone(result['error'])
        self.assertEqual(len(calls),30)
        self.assertEqual(len(wire.completed),30)
        self.assertEqual(slave.data[:128],self.plan.target)
        self.assertEqual(slave.data[64:],model.BEFORE[64:]+b'R'*128)
        self.assertFalse(result['reset_qualified'])
        before = len(sdk.calls)
        with self.assertRaises(ValueError): wire.read(0,64,300)
        self.assertEqual(len(sdk.calls),before)

    def test_first_read_page_ack_and_postread_seal_failures_stop_without_replay(self):
        for failure in (0,2,3,4):
            clock,slave,sdk,wire,log,calls = self.make(failure)
            result = model.confirm_io.Transaction(self.fn,self.plan,wire,clock=clock,sleep=clock.sleep).run()
            self.assertNotEqual(result['result'],'EEPROM_BYTES_CONFIRMED')
            self.assertEqual(len(calls),failure+1)
            self.assertEqual(len(wire.completed),failure)
            before = len(sdk.calls)
            for call in (lambda:wire.read(0,64,300),lambda:wire.ack(30),lambda:wire.page(0,self.plan.record[:8],120)):
                with self.assertRaises(ValueError): call()
            self.assertEqual(len(sdk.calls),before)
            self.assertFalse(result['reset_qualified'])

    def test_page_stop_archive_failure_cannot_send_ready_ack(self):
        clock,slave,sdk,wire,log,calls = self.make()
        def archive(index,kind,address,result):
            if kind=='page': raise OSError('archive failed after STOP')
        wire.archive = archive
        result = model.confirm_io.Transaction(self.fn,self.plan,wire,clock=clock,sleep=clock.sleep).run()
        self.assertEqual(result['result'],'EEPROM_OUTCOME_UNKNOWN')
        self.assertEqual(len(calls),2)
        self.assertIsNotNone(wire.pending_stop)
        self.assertFalse(wire.ack_attempted)
        self.assertEqual(slave.data[64:],model.BEFORE[64:]+b'R'*128)

    def test_final_seal_owner_or_reserve_loss_is_not_confirmation(self):
        for fault in ('owner','reserve'):
            clock,slave,sdk,wire,log,calls = self.make()
            original = log.switch
            def switch(**kwargs):
                result = original(**kwargs)
                if len(calls)==30:
                    if fault=='owner': wire.owner = lambda:False
                    else: wire.remaining = lambda:899
                return result
            log.switch = switch
            result = model.confirm_io.Transaction(self.fn,self.plan,wire,clock=clock,sleep=clock.sleep).run()
            self.assertEqual(result['result'],'EEPROM_OUTCOME_UNKNOWN')
            self.assertEqual(len(wire.completed),30)
            self.assertEqual(slave.data[:128],self.plan.target)

    def test_oracle_and_native_scope_reject_other_record_or_unsettled_write(self):
        for call in (lambda:stores('page',64,b'x'*8),lambda:stores('read',8,size=64),
                     lambda:stores('read',0,size=7),lambda:stores('ack',1),lambda:stores('page',True,b'x'*8)):
            with self.assertRaises(ValueError): call()
        clock,slave,sdk,wire,_,_ = self.make()
        with self.assertRaises(ValueError): wire.page(64,self.plan.record[:8],120)
        self.assertFalse(sdk.calls)

    def test_real_page_ack_read8_journal_and_online_gate_compose(self):
        clock = model.Clock()
        slave = model.Slave(clock,model.BEFORE+b'R'*128)
        class BufferedPath(MemoryPath):
            @property
            def data(self): return ''.join(self.parts)
            @data.setter
            def data(self,value): self.parts = [value]
            def append(self,value): self.parts.append(value)
        paths = [BufferedPath(f'log-{i}','') for i in range(32)]
        class Native(model.SDK):
            def __init__(self):
                super().__init__(slave)
                self.paths,self.index,self.switches = paths,0,0
                self.fault = None
                self.hook = lambda:None
            def log(self,text): self.paths[self.index].append(text)
            JLINKARM_SetLogFile = online_model.Native.JLINKARM_SetLogFile
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
        native = Native()
        dap = online_model.Dap(JournalSDK(native,lambda *a,**k:None,clock=clock))
        log = OnlineLog(dap,SealedGate(paths,META,record),lambda *a,**k:None,lambda:3600-clock.value,clock=clock)
        log.switch(read_allowed=lambda _:False,expected_stores=[])
        wire = Wire(dap,native.original,self.plan,lambda:True,log.emit,log,lambda:3600-clock.value,
                    lambda *a:None,clock=clock,sleep=clock.sleep,guard=lambda f,*a,**k:f(*a))
        page = wire.page(0,self.plan.record[:8],120)
        self.assertEqual(page['status'],0)
        self.assertIsNotNone(wire.pending_stop)
        clock.sleep(.005)
        self.assertTrue(wire.ack(30))
        self.assertEqual(wire.read(0,8,300),self.plan.record[:8])
        self.assertEqual(len(log.gate.records),4)
        self.assertEqual([p['kind'] for p in wire.completed],['page','ack','read'])
        log.verify_head()
        self.assertEqual(slave.data[8:],model.BEFORE[8:]+b'R'*128)

    def test_global_deadline_is_checked_before_and_after_each_native_call(self):
        clock,slave,sdk,wire,_,_ = self.make()
        def guard(function,*args,seconds):
            value = function(*args)
            if function.__name__.startswith('JLINK'):
                self.assertLessEqual(seconds,.010001)
                clock.value += .02
            return value
        wire.native_guard = guard
        wire.remaining = lambda:900.01-clock.value
        with self.assertRaises(ValueError): wire.read(0,64,300)
        self.assertEqual(len(sdk.calls),1)
        self.assertFalse(slave.edges)
        count = len(sdk.calls)
        with self.assertRaises(ValueError): wire.read(0,64,300)
        self.assertEqual(len(sdk.calls),count)

    def test_archive_guard_is_bounded_and_late_page_archive_retains_stop(self):
        clock,slave,sdk,wire,log,calls = self.make()
        guards = []
        inside = [False]
        def archive(index,kind,address,result):
            self.assertTrue(inside[0])
            if kind=='page': clock.value += 1801
        def guard(function,*args,seconds):
            if function is archive:
                self.assertGreater(seconds,0)
                self.assertLessEqual(seconds,wire.left()-wire.reserve)
                self.assertLessEqual(seconds,wire.budget.left())
                self.assertLessEqual(seconds,wire.pins.words.budget.left())
                guards.append(seconds)
                inside[0] = True
                try: return function(*args)
                finally: inside[0] = False
            return function(*args)
        wire.archive,wire.native_guard = archive,guard
        result = model.confirm_io.Transaction(self.fn,self.plan,wire,clock=clock,sleep=clock.sleep).run()
        self.assertEqual(result['result'],'EEPROM_OUTCOME_UNKNOWN')
        self.assertEqual(len(guards),3)
        self.assertEqual(len(calls),2)
        self.assertIsNotNone(wire.pending_stop)
        self.assertFalse(wire.ack_attempted)
        before = len(sdk.calls)
        with self.assertRaises(ValueError): wire.ack(30)
        self.assertEqual(len(sdk.calls),before)


if __name__=='__main__': unittest.main()
