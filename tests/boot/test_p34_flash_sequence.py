from pathlib import Path
import sys
from types import SimpleNamespace
import unittest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT/'Tools/ota'))
sys.path.insert(0, str(ROOT/'tests/boot'))
from recovery_confirm.flash_sequence import Sequence
from recovery_confirm.native_io import Budget
from recovery_confirm.ap_journal import JournalSDK
from recovery_confirm.mutation_audit import SealedGate, flash_stores
from recovery_confirm.online_log import OnlineLog
from test_p34_mutation_audit import MemoryPath, record, META
import test_p34_online_log as online_model
import test_p34_recovery_ports as model
import ctypes

PREIMAGE = (ROOT/'.cache/p34-recovery-preflight1/envelope.bin').read_bytes()


class LogModel:
    def __init__(self, fail=None, dap=None):
        self.dap = dap
        self.gate = SimpleNamespace(index=1, paths=tuple(range(305)), boundary=[])
        self.calls = []
        self.fail = fail
    def target_allowed(self): return True
    def verify_head(self): pass
    def switch(self, *, read_allowed, expected_stores):
        self.calls.append(self.gate.index-1)
        if self.gate.index-1 == self.fail: raise OSError('sealed log failed')
        self.gate.index += 1
        return dict(target_writes=len(expected_stores), log_file_closed=1, native_close=0)


class Tests(unittest.TestCase):
    def make(self, *, fail=None, bad_result=False):
        memory = bytearray(PREIMAGE)
        called = []
        log = LogModel(fail)
        def factory(dap, image, preimage, index, owner, emit, *, seconds, clock, sleep, guard):
            called.append(index)
            def run():
                assert owner()
                offset = index*2048
                assert memory[offset:offset+2048] == preimage[offset:offset+2048]
                desired = image+preimage[len(image):]
                memory[offset:offset+2048] = desired[offset:offset+2048]
                count = sum(desired[i:i+4] != b'\xff'*4 for i in range(offset,offset+2048,4))
                return dict(address=0x08010000+offset, bank=1 if index<224 else 2,
                            programmed_words=count, complete=not bad_result, reset_allowed=False)
            return SimpleNamespace(run=run, words=SimpleNamespace(reads=set(), budget=Budget(seconds,clock)))
        sequence = Sequence(None,model.IMAGE,PREIMAGE,lambda:True,lambda *a,**k:None,log,lambda:21600,
                            sector_factory=factory,native_guard=lambda f,*a,**k:f(*a))
        return sequence, log, memory, called

    def test_whole_orchestration_model_visits_303_sectors_and_preserves_suffix(self):
        seq, log, memory, called = self.make()
        result = seq.run()
        self.assertEqual(result['result'], 'ALL_FLASH_SECTORS_AUDITED')
        self.assertEqual(called, list(range(303)))
        self.assertEqual(log.calls, called)
        self.assertEqual(memory, model.IMAGE+PREIMAGE[len(model.IMAGE):])
        self.assertEqual(sum(item['bank']==1 for item in seq.completed), 224)
        self.assertFalse(result['reset_allowed'])
        self.assertFalse(result['eeprom_confirmed'])
        with self.assertRaises(ValueError): seq.run()
        self.assertEqual(len(called), 303)

    def test_any_seal_failure_stops_before_following_sector_and_never_replays(self):
        for failure in (0,1,223,224,302):
            seq, log, _, called = self.make(fail=failure)
            with self.assertRaises(OSError): seq.run()
            self.assertEqual(called, list(range(failure+1)))
            self.assertEqual(len(seq.completed), failure)
            self.assertTrue(seq.app_may_have_changed)
            self.assertFalse(seq.active)
            with self.assertRaises(ValueError): seq.run()
            self.assertEqual(len(log.calls), failure+1)

    def test_owner_reserve_or_result_failure_does_not_open_next_phase(self):
        seq, log, _, called = self.make()
        seq.remaining = lambda:3800
        with self.assertRaises(ValueError): seq.run()
        self.assertFalse(called)
        self.assertFalse(seq.app_may_have_changed)
        seq, log, _, called = self.make(bad_result=True)
        with self.assertRaises(ValueError): seq.run()
        self.assertEqual(called, [0])
        self.assertFalse(log.calls)

    def test_actual_sector_guard_obeys_tightened_global_limit_before_target_read(self):
        clock = model.Clock()
        sdk = model.FlashSDK(clock, PREIMAGE)
        end = [6000.]
        timeouts = []
        def guard(fn, *args, seconds):
            native = fn.__name__.startswith('JLINK')
            if native: timeouts.append(seconds)
            result = fn(*args)
            if native: clock.value += .02
            return result
        def factory(*args, **kwargs):
            port = model.flash.Sector(*args, **kwargs)
            end[0] = 3600.01
            return port
        dap = model.Dap(sdk)
        seq = Sequence(dap,model.IMAGE,PREIMAGE,lambda:True,lambda *a,**k:None,LogModel(dap=dap),
                       lambda:end[0]-clock.value,clock=clock,sleep=clock.sleep,native_guard=guard,sector_factory=factory)
        # Constructor prefix verification is host-only, not a target call.
        timeouts.clear()
        with self.assertRaises(ValueError): seq.run()
        self.assertEqual(len(sdk.calls), 1)
        self.assertTrue(0 < timeouts[0] <= .010001)
        self.assertFalse(sdk.write_log)
        self.assertFalse(sdk.mutations)

    def test_wrong_preimage_and_inadequate_log_positions_reject_without_calls(self):
        log = LogModel()
        with self.assertRaises(ValueError):
            Sequence(None,model.IMAGE,bytes(len(PREIMAGE)),lambda:True,lambda *a,**k:None,log,lambda:21600)
        log.gate.paths = tuple(range(304))
        with self.assertRaises(ValueError):
            Sequence(None,model.IMAGE,PREIMAGE,lambda:True,lambda *a,**k:None,log,lambda:21600)
        self.assertFalse(log.calls)

    def test_seal_and_final_emit_owner_or_reserve_loss_never_returns_success(self):
        for where in (0,302):
            for fault in ('owner','reserve','emit'):
                seq, log, _, called = self.make()
                owned, left = [True], [21600]
                seq.owner, seq.remaining = lambda:owned[0], lambda:left[0]
                original = log.switch
                def switch(**kwargs):
                    result = original(**kwargs)
                    if log.calls[-1] == where and fault != 'emit':
                        if fault == 'owner': owned[0] = False
                        else: left[0] = 3599
                    return result
                def emit(event, **fields):
                    if event == 'flash-sequence-sector-audited' and fields['index'] == where and fault == 'emit':
                        owned[0] = False
                log.switch, seq.emit = switch, emit
                with self.assertRaises(ValueError): seq.run()
                self.assertEqual(called, list(range(where+1)))
                self.assertEqual(len(seq.completed), where+1)
                self.assertTrue(seq.app_may_have_changed)

    def real_bridge(self):
        clock = model.Clock()
        class BufferedPath(MemoryPath):
            @property
            def data(self): return ''.join(self.parts)
            @data.setter
            def data(self, value): self.parts = [value]
            def append(self, value): self.parts.append(value)
        paths = [BufferedPath(f'log-{i}', '') for i in range(305)]
        class Native(model.FlashSDK):
            def __init__(self):
                super().__init__(clock, PREIMAGE)
                self.paths, self.index, self.switches = paths, 0, 0
                self.fault = None
                self.hook = lambda:None
            def log(self, text):
                if self.index and self.fault == 'new-blank': return
                self.paths[self.index].append(text)
            JLINKARM_SetLogFile = online_model.Native.JLINKARM_SetLogFile
            def JLINKARM_CORESIGHT_ReadAPDPReg(self, index, ap, out):
                self.log(f'JLINK_CORESIGHT_ReadAPDPReg({"AP" if ap else "DP"} reg 0x{index:02X})\n')
                if (index,ap) == (1,1):
                    ctypes.cast(out,ctypes.POINTER(ctypes.c_uint32))[0] = self.tar
                    result = 0
                else:
                    result = super().JLINKARM_CORESIGHT_ReadAPDPReg(index,ap,out)
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
        log = OnlineLog(dap,SealedGate(paths,META,record),lambda *a,**k:None,lambda:21600-clock.value,clock=clock)
        log.switch(read_allowed=lambda _:False,expected_stores=[])
        seq = Sequence(dap,model.IMAGE,PREIMAGE,lambda:True,log.emit,log,lambda:21600-clock.value,
                       clock=clock,sleep=clock.sleep,native_guard=lambda f,*a,**k:f(*a))
        return seq,native,log

    def test_two_real_adjacent_sectors_and_clean_heads_then_deliberate_stop(self):
        seq,native,log = self.real_bridge()
        def emit(event, **fields):
            log.emit(event,**fields)
            if event == 'flash-sequence-sector-audited' and fields['index'] == 1:
                raise ValueError('deliberate stop before third sector')
        seq.emit = emit
        with self.assertRaisesRegex(ValueError,'deliberate stop'): seq.run()
        self.assertEqual(tuple(native.write_log),flash_stores(model.IMAGE,PREIMAGE,0)+flash_stores(model.IMAGE,PREIMAGE,1))
        self.assertEqual(bytes(native.flash[:4096]),model.IMAGE[:4096])
        self.assertEqual(bytes(native.flash[4096:]),PREIMAGE[4096:])
        self.assertEqual(len(seq.completed),2)
        self.assertEqual(len(log.gate.records),3)
        log.verify_head()

    def test_real_sealed_file_or_new_head_failure_prevents_following_sector(self):
        for fault in ('blank','new-blank'):
            seq,native,log = self.real_bridge()
            native.hook = lambda:setattr(native,'fault',fault)
            with self.assertRaises(ValueError): seq.run()
            self.assertEqual(tuple(native.write_log),flash_stores(model.IMAGE,PREIMAGE,0))
            self.assertEqual(bytes(native.flash[2048:]),PREIMAGE[2048:])
            self.assertFalse(log.target_allowed())
            self.assertFalse(seq.completed)

    def test_dap_mismatch_or_dirty_initial_segment_rejects_before_target_access(self):
        for fault in ('dap','dirty','unsealed'):
            seq,native,log = self.real_bridge()
            if fault == 'dap': log.dap = object()
            elif fault == 'dirty':
                log.emit('recovery-word-read',address=0x08010000,value=1)
            else: log.gate.boundary = None
            before = list(native.calls)
            with self.assertRaises(ValueError):
                Sequence(seq.dap,model.IMAGE,PREIMAGE,lambda:True,log.emit,log,lambda:21600,
                         native_guard=lambda f,*a,**k:f(*a))
            self.assertEqual(native.calls,before)
            self.assertFalse(native.mutations)


if __name__ == '__main__': unittest.main()
