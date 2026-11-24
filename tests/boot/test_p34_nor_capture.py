import ctypes
from pathlib import Path
import sys
import unittest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT/'Tools/ota'))
sys.path.insert(0,str(ROOT/'tests/boot'))
from recovery_confirm import nor_capture as nc
from recovery_confirm.ap_journal import JournalSDK
from recovery_confirm.mutation_audit import SealedGate
from recovery_confirm.online_log import OnlineLog
from test_p34_mutation_audit import MemoryPath, record, META
from p34_eeprom_wire_model import Clock
import test_p34_online_log as online

EXPECTED = (ROOT/'.cache/p34-host-nor-rebuild1/after-recovery.bin').read_bytes()


class BufferedPath(MemoryPath):
    @property
    def data(self): return ''.join(self.parts)
    @data.setter
    def data(self,value): self.parts = [value]
    def append(self,value): self.parts.append(value)


class Native(online.Native):
    def __init__(self,paths,clock):
        super().__init__(paths)
        self.clock = clock
        self.memory.update({nc.QSPI_REGS[k]:v for k,v in nc.hn.CONFIG.items()})
        self.memory.update({nc.DHCSR:0x30003,nc.PAUSE:0x1000,nc.hn.FIFO:1,nc.hn.RSTS:0})
        self.payload = bytearray(EXPECTED)
        self.stores = []
        self.read_words = 0
        self.fail_store = None
        self.fail_word = None
        self.status_bad = False
    def log(self,text):
        if self.index and self.fault=='new-blank': return
        self.paths[self.index].append(text)
    def JLINKARM_CORESIGHT_ReadAPDPReg(self,index,ap,out):
        self.clock.value += .0005
        address = self.tar
        if (index,ap)==(3,1) and nc.MAPPED+0x200000<=address<nc.MAPPED+0x299000:
            assert self.memory[nc.hn.CTRL]==nc.hn.XIP|nc.hn.IDLE|7
            assert self.memory[nc.XIP3]&1 and self.csw&META['ap_csw']==META['ap_csw']
            self.memory[nc.XIP3] |= 8
            off = address-nc.MAPPED-0x200000
            self.memory[address] = int.from_bytes(self.payload[off:off+4],'little')
            self.read_words += 1
        result = super().JLINKARM_CORESIGHT_ReadAPDPReg(index,ap,out)
        if (index,ap)==(3,1):
            # The real AP may wrap at 1 KiB. Every next chunk must reload TAR.
            self.tar = (address&~1023)|((address+4)&1023)
        return -1 if self.fail_word is not None and self.read_words==self.fail_word else result
    def JLINKARM_CORESIGHT_WriteAPDPReg(self,index,ap,value):
        self.clock.value += .0005
        address = self.tar
        result = super().JLINKARM_CORESIGHT_WriteAPDPReg(index,ap,value)
        if (index,ap)==(3,1):
            self.stores.append((address,value))
            if address==nc.hn.CTRL:
                self.memory[address] = value|nc.hn.IDLE
            elif address==nc.hn.CMDSTS:
                assert value==1
                self.memory[address] = 0
            elif address==nc.hn.BASE+12:
                assert value in (0x0500000c,0x3500000c)
                assert [self.memory[nc.hn.BASE+i] for i in (0,4,8)]==[0,0x1000000,0]
                self.memory[nc.hn.CMDSTS] = 1
                self.memory[nc.hn.RSTS] = (1 if self.status_bad else 0) if value>>24==5 else 2
            assert address<nc.MAPPED or address>=nc.MAPPED+0x1000000
            if len(self.stores)==self.fail_store: return -1
        return result


class Tests(unittest.TestCase):
    def make(self):
        clock = Clock()
        paths = [BufferedPath(f'log-{i}','') for i in range(23)]
        native = Native(paths,clock)
        dap = online.Dap(JournalSDK(native,lambda *a,**k:None,clock=clock))
        log = OnlineLog(dap,SealedGate(paths,META,record),lambda *a,**k:None,lambda:21600-clock.value,clock=clock)
        log.switch(read_allowed=lambda _:False,expected_stores=[])
        archived = []
        capture = nc.Capture(dap,'recovery',EXPECTED,lambda:True,log,lambda:21600-clock.value,
            lambda name,offset,raw:archived.append((name,offset,raw)),clock=clock,sleep=clock.sleep,guard=lambda f,*a,**k:f(*a))
        return clock,native,log,capture,archived

    def test_full_real_reader_word_journal_segments_and_exact_restoration(self):
        clock,native,log,capture,archived = self.make()
        result = capture.run()
        self.assertEqual(result['result'],'NOR_REGION_CAPTURED_AUDITED')
        self.assertEqual(b''.join(row[2] for row in archived),EXPECTED)
        self.assertEqual([row[1] for row in archived],list(range(0,len(EXPECTED),32768)))
        self.assertEqual(tuple(native.stores),nc.OPEN+nc.CLOSE)
        self.assertEqual(native.read_words,len(EXPECTED)//4)
        self.assertGreater(clock.value,60)
        self.assertEqual(capture.completed_segments,21)
        self.assertEqual(len(log.gate.records),22)
        self.assertTrue(capture.restored)
        log.verify_head()
        self.assertFalse(result['historical_sdk_audit_passed'])
        self.assertFalse(result['reset_allowed'])
        self.assertEqual(native.payload,EXPECTED)

    def test_data_mismatch_is_archived_but_not_sealed_or_restored(self):
        _,native,log,capture,archived = self.make()
        native.payload[0] ^= 1
        with self.assertRaisesRegex(ValueError,'differs'): capture.run()
        self.assertEqual(len(archived),1)
        self.assertEqual(len(log.gate.records),1)
        self.assertFalse(capture.restored)
        before = list(native.stores)
        with self.assertRaises(ValueError): capture.run()
        self.assertEqual(native.stores,before)

    def test_bad_status_or_any_selected_uncertain_setup_store_stops(self):
        for fail in (1,2,6,12,13,14,'status'):
            _,native,_,capture,archived = self.make()
            if fail=='status': native.status_bad = True
            else: native.fail_store = fail
            with self.assertRaises((ValueError,OSError)): capture.run()
            self.assertFalse(native.read_words)
            self.assertFalse(archived)
            self.assertFalse(capture.restored)
            count = len(native.stores)
            with self.assertRaises(ValueError): capture.write(nc.hn.CTRL,nc.hn.XIP)
            self.assertEqual(len(native.stores),count)

    def test_native_chunk_failure_or_seal_failure_never_advances(self):
        for fail in ('native','old-log','new-head'):
            _,native,log,capture,archived = self.make()
            if fail=='native': native.fail_word = 1
            elif fail=='old-log': native.hook = lambda:setattr(native,'fault','blank')
            else: native.hook = lambda:setattr(native,'fault','new-blank')
            with self.assertRaises((ValueError,OSError)): capture.run()
            self.assertEqual(len(archived),0 if fail=='native' else 1)
            self.assertEqual(native.read_words,1 if fail=='native' else 8192)
            self.assertFalse(capture.restored)

    def test_scope_identity_and_owner_reject_before_native_calls(self):
        _,native,log,capture,_ = self.make()
        for name,data in (('unknown',EXPECTED),('recovery',bytes(len(EXPECTED))),('recovery',EXPECTED[:-4])):
            with self.assertRaises(ValueError):
                nc.Capture(capture.dap,name,data,lambda:True,log,lambda:21600,lambda *a:None)
        self.assertFalse(native.stores)
        capture.owner = lambda:False
        with self.assertRaises(ValueError): capture.run()
        self.assertFalse(native.stores)

    def test_archive_uses_remaining_guard_and_late_return_cannot_seal(self):
        clock,native,log,capture,archived = self.make()
        inside = [False]
        def archive(*args):
            self.assertTrue(inside[0])
            clock.value += 1801
        def guard(function,*args,seconds):
            if function is archive:
                self.assertTrue(0<seconds<=capture.left()-capture.reserve)
                self.assertLessEqual(seconds,capture.words.budget.left())
                inside[0] = True
            try: return function(*args)
            finally: inside[0] = False
        capture.archive,capture.native_guard = archive,guard
        with self.assertRaises(ValueError): capture.run()
        self.assertEqual(native.read_words,8192)
        self.assertEqual(len(log.gate.records),1)
        self.assertFalse(capture.restored)


if __name__=='__main__': unittest.main()
