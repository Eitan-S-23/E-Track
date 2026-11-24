import copy
import hashlib
import io
from pathlib import Path
import sys
import unittest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT/'Tools/ota'))
sys.path.insert(0, str(ROOT/'tests/boot'))
from recovery_confirm.mutation_audit import Cursor, SealedGate, flash_stores, journal
from recovery_confirm.ap_journal import JournalSDK
import test_p34_recovery_ports as model

META = dict(ap_csw=0x23000052, original_tar=0xe000ef38, original_dp=0x40)


def rows_for(operations, start=0):
    rows = []
    for seq, (op, port, reg, value, data) in enumerate(operations, start+1):
        rows.extend((dict(event='ap-call-attempt', sequence=seq, operation=op,
                          ap=int(port=='AP'), index=reg, value=value),
                     dict(event='ap-call-returned', sequence=seq, rc=0, read_value=data,
                          started=float(seq), ended=seq+.1)))
    return rows


def native_lines(rows, start=0, previous=None, close=False):
    for (op, port, reg, value, data, rc), _, _ in journal(rows, start, previous):
        if op == 'read':
            yield f'JLINK_CORESIGHT_ReadAPDPReg({port} reg 0x{reg:02X})\n'
            yield f'Value=0x{data:08X}\n'
        else:
            yield f'JLINK_CORESIGHT_WriteAPDPReg({port} reg 0x{reg:02X}, 0x{value:08X})\n'
        yield f'T0000 000:000.000 - 0.1ms returns {rc}\n'
    if close:
        yield 'JLINK_Close()\n'
        yield 'T565C 097:837.264   Closed\n'


class MemoryPath:
    """Artifact-free fixture, never a replacement for a physical original log."""
    def __init__(self, name, data):
        self.name, self.data = name, data
        self.after_read = None
    def __str__(self):
        return self.name
    def open(self, *args, **kwargs):
        result = io.StringIO(self.data)
        if self.after_read:
            self.after_read()
        return result


def record(path):
    raw = path.data.encode('utf-8')
    return dict(path=str(path), bytes=len(raw), sha256=hashlib.sha256(raw).hexdigest())


class Tests(unittest.TestCase):
    def fixture(self):
        address = 0x08010000
        tail = [('read', 'DP', 1, None, 0xf0000040),
                ('read', 'AP', 0, None, META['ap_csw']),
                ('read', 'AP', 1, None, address+4)]
        first = rows_for([('write', 'AP', 1, address, None), ('write', 'AP', 3, 123, None)] + tail)
        first.extend((dict(event='recovery-word-write-attempt', address=address, value=123),
                      dict(event='recovery-word-write-returned', address=address, value=123)))
        second = rows_for(tail + [('write', 'AP', 1, META['original_tar'], None),
                                 ('read', 'AP', 1, None, META['original_tar']),
                                 ('read', 'AP', 0, None, META['ap_csw']),
                                 ('write', 'DP', 1, 0x40, None), ('read', 'DP', 1, None, 0x40)], 5)
        paths = [MemoryPath('first.log', ''.join(native_lines(first))+'JLINK_SetLogFile(...)\nT0000 000:000.100 Closed\n'),
                 MemoryPath('last.log', ''.join(native_lines(second, 5, close=True)))]
        return paths, first, second

    def test_sealed_then_final_preserves_one_real_close_and_contiguous_sequence(self):
        paths, first, last = self.fixture()
        gate = SealedGate(paths, META, record)
        gate.begin(0)
        result = gate.seal(0, first, read_allowed=lambda _:False, expected_stores=[(0x08010000,123)])
        self.assertEqual(result['native_close'], 0)
        gate.begin(1)
        result = gate.seal(1, last, read_allowed=lambda _:False, expected_stores=[],
                           expected_dp_writes=[0x40], final=True, native_closed=True)
        self.assertEqual(result['native_close'], 1)
        self.assertEqual((gate.cursor.native_calls, gate.cursor.target_writes), (13, 1))
        self.assertEqual(gate.cursor.state.sequence, 13)
        with self.assertRaises(ValueError): gate.begin(1)

    def test_no_next_segment_before_audit_and_any_seal_failure_latches(self):
        paths, first, _ = self.fixture()
        gate = SealedGate(paths, META, record)
        gate.begin(0)
        with self.assertRaises(ValueError): gate.begin(1)
        with self.assertRaises(ValueError):
            gate.seal(0, first, read_allowed=lambda _:False, expected_stores=[(0x08010000,123)])
        for fault in ('blank', 'truncated', 'close', 'wrong-plan', 'frame', 'hash'):
            with self.subTest(fault=fault):
                paths, first, _ = self.fixture()
                stores = [(0x08010000, 123)]
                if fault == 'blank': paths[0].data = '\n'*100
                if fault == 'truncated': paths[0].data = paths[0].data.rsplit('\n', 2)[0]+'\n'
                if fault == 'close': paths[0].data += 'JLINK_Close()\n'
                if fault == 'wrong-plan': stores = [(0x08010000, 124)]
                if fault == 'frame': first.pop()
                if fault == 'hash': paths[0].after_read = lambda: setattr(paths[0], 'data', paths[0].data+'\n')
                gate = SealedGate(paths, META, record)
                gate.begin(0)
                with self.assertRaises(ValueError):
                    gate.seal(0, first, read_allowed=lambda _:False, expected_stores=stores)
                with self.assertRaises(ValueError): gate.begin(1)

    def test_native_and_journal_joint_store_change_still_rejected(self):
        paths, rows, _ = self.fixture()
        rows[2]['value'] = 124
        rows[-2]['value'] = rows[-1]['value'] = 124
        paths[0].data = ''.join(native_lines(rows))+'JLINK_SetLogFile(...)\nT0000 000:000.100 Closed\n'
        gate = SealedGate(paths, META, record)
        gate.begin(0)
        with self.assertRaises(ValueError):
            gate.seal(0, rows, read_allowed=lambda _:False, expected_stores=[(0x08010000,123)])

    def test_boundary_state_and_old_file_integrity_are_not_assumed(self):
        for fault in ('head', 'tail', 'old-file', 'sequence', 'clock'):
            paths, first, last = self.fixture()
            gate = SealedGate(paths, META, record)
            gate.begin(0)
            if fault == 'tail':
                first[5]['read_value'] ^= 0x20
                paths[0].data = ''.join(native_lines(first))+'JLINK_SetLogFile(...)\nT0000 000:000.100 Closed\n'
                with self.assertRaises(ValueError):
                    gate.seal(0, first, read_allowed=lambda _:False, expected_stores=[(0x08010000,123)])
                continue
            gate.seal(0, first, read_allowed=lambda _:False, expected_stores=[(0x08010000,123)])
            if fault == 'head':
                last[1]['read_value'] ^= 0x40
                paths[1].data = ''.join(native_lines(last, 5, close=True))
            if fault == 'old-file': paths[0].data += '\n'
            if fault == 'sequence': last[0]['sequence'] = 1
            if fault == 'clock': last[1]['started'] = 0
            gate.begin(1)
            with self.assertRaises(ValueError):
                gate.seal(1, last, read_allowed=lambda _:False, expected_stores=[],
                          expected_dp_writes=[0x40], final=True, native_closed=True)
            self.assertIsNotNone(gate.error)

    def test_missing_extra_native_scope_and_close_are_rejected(self):
        for fault in ('reset', 'write-mem', 'missing-value', 'duplicate-value', 'missing-journal',
                      'native-error', 'target-frame-value', 'nonfinite'):
            paths, rows, _ = self.fixture()
            lines = paths[0].data.splitlines(True)
            if fault == 'reset': lines.insert(0, 'JLINK_Reset()\n')
            if fault == 'write-mem': lines.insert(0, 'JLINK_WriteMem(0x08000000, 4)\n')
            if fault == 'missing-value': lines = [line for line in lines if not line.startswith('Value=')]
            if fault == 'duplicate-value': lines.insert(6, lines[5])
            if fault == 'missing-journal': rows.pop(0)
            if fault == 'native-error': lines[1] = lines[1].replace('returns 0', 'returns -1')
            if fault == 'target-frame-value': rows[-1]['value'] ^= 1
            if fault == 'nonfinite': rows[1]['ended'] = float('nan')
            cursor = Cursor(META)
            with self.assertRaises(ValueError):
                cursor.verify(lines, rows, read_allowed=lambda _:False, expected_stores=[(0x08010000,123)], switched_away=True)
            self.assertEqual(cursor.state.sequence, 0)
            with self.assertRaises(ValueError): cursor.verify([], [], read_allowed=lambda _:True, expected_stores=[])

    def test_unknown_wrap_requires_reload_and_bank_f0_is_identity_only(self):
        for reload in (False, True):
            ops = [('write','AP',1,0x080103fc,None), ('read','AP',3,None,1)]
            if reload: ops.append(('write','AP',1,0x08010400,None))
            ops.append(('read','AP',3,None,2))
            rows = rows_for(ops)
            cursor = Cursor(META)
            action = lambda:cursor.verify(native_lines(rows), rows, read_allowed=lambda a:a in (0x080103fc,0x08010400),
                                         expected_stores=[], bind_words=False)
            if reload: self.assertEqual(action()['target_reads'], 2)
            else:
                with self.assertRaises(ValueError): action()
        for reg in (0, 1):
            rows = rows_for([('write','DP',2,0xf0,None), ('read','AP',reg,None,0)])
            with self.assertRaises(ValueError):
                Cursor(META).verify(native_lines(rows), rows, read_allowed=lambda _:True, expected_stores=[], bind_words=False)

    def test_missing_target_value_cannot_be_hidden_by_two_none_journal_fields(self):
        rows = rows_for([('write','AP',1,0x08010000,None), ('read','AP',3,None,123)])
        rows.append(dict(event='recovery-word-read', address=0x08010000, value=123))
        lines = list(native_lines(rows))
        lines = [line for line in lines if not line.startswith('Value=')]
        rows[3]['read_value'] = rows[-1]['value'] = None
        cursor = Cursor(META)
        with self.assertRaises(ValueError):
            cursor.verify(lines, rows, read_allowed=lambda a:a==0x08010000, expected_stores=[])
        self.assertIsNotNone(cursor.error)
        for bad in (None, True, -1, 0x100000000, float('nan')):
            valid = rows_for([('write','AP',1,0x08010000,None), ('read','AP',3,None,123)])
            valid.append(dict(event='recovery-word-read', address=0x08010000, value=123))
            original = list(native_lines(valid))
            valid[3]['read_value'] = valid[-1]['value'] = bad
            with self.assertRaises(ValueError):
                Cursor(META).verify(original, valid, read_allowed=lambda _:True, expected_stores=[])

    def test_intermediate_dp_drop_and_reacquire_need_independent_phase_plan(self):
        rows = rows_for([('write','DP',1,0x40,None), ('write','DP',1,0x50000040,None),
                         ('read','DP',1,None,0xf0000040), ('read','AP',0,None,META['ap_csw']),
                         ('read','AP',1,None,META['original_tar'])])
        lines = list(native_lines(rows))
        cursor = Cursor(META)
        with self.assertRaises(ValueError):
            cursor.verify(lines, rows, read_allowed=lambda _:False, expected_stores=[])
        self.assertIsNotNone(cursor.error)
        # A separately explicit setup plan may contain the acquisition sequence.
        result = Cursor(META).verify(lines, rows, read_allowed=lambda _:False, expected_stores=[],
                                     expected_dp_writes=[0x40, 0x50000040])
        self.assertEqual(result['native_calls'], 5)

    def test_final_requires_readbacks_dp_and_actual_native_close_completion(self):
        for fault in ('write-only', 'wrong-dp', 'missing-dp', 'no-closed', 'no-return', 'stale-tar'):
            ops = [('write','AP',1,META['original_tar'],None),
                   ('read','AP',1,None,META['original_tar']), ('read','AP',0,None,META['ap_csw']),
                   ('write','DP',1,0x40,None), ('read','DP',1,None,0x40)]
            if fault == 'write-only': ops = [ops[0]]
            if fault == 'wrong-dp': ops[-1] = ('read','DP',1,None,0xf0000040)
            if fault == 'missing-dp': ops.pop()
            if fault == 'stale-tar': ops.append(('write','AP',1,META['original_tar'],None))
            rows = rows_for(ops)
            lines = list(native_lines(rows, close=True))
            if fault == 'no-closed': lines.pop()
            cursor = Cursor(META)
            with self.assertRaises(ValueError):
                cursor.verify(lines, rows, read_allowed=lambda _:False, expected_stores=[], final=True,
                              expected_dp_writes=[] if fault=='write-only' else [0x40], native_closed=fault!='no-return')
            self.assertFalse(cursor.finished)

    def test_file_closed_and_native_closed_are_distinct_barriers(self):
        paths, rows, _ = self.fixture()
        original = paths[0].data
        result = Cursor(META).verify(original.splitlines(True), rows, read_allowed=lambda _:False,
                                     expected_stores=[(0x08010000,123)], switched_away=True)
        self.assertEqual((result['log_file_closed'], result['native_close_completed']), (1, 0))
        for changed in (original.replace('JLINK_SetLogFile(...)\n', ''),
                        original.replace('JLINK_SetLogFile(...)', 'JLINK_Close()'),
                        original.replace('T0000 000:000.100 Closed\n', ''),
                        original+'T0000 000:000.200 Closed\n',
                        original+'JLINK_CORESIGHT_ReadAPDPReg(DP reg 0x01)\n'):
            with self.assertRaises(ValueError):
                Cursor(META).verify(changed.splitlines(True), rows, read_allowed=lambda _:False,
                                    expected_stores=[(0x08010000,123)], switched_away=True)
        with self.assertRaises(ValueError):
            Cursor(META).verify(original.splitlines(True), rows, read_allowed=lambda _:False,
                                expected_stores=[(0x08010000,123)])

    def test_real_sector_ports_match_independent_store_plan_and_word_frames(self):
        preimage = (ROOT/'.cache/p34-recovery-preflight1/envelope.bin').read_bytes()
        clock = model.Clock()
        sdk = model.FlashSDK(clock, preimage)
        cursor = Cursor(META)
        rows = []
        proxy = JournalSDK(sdk, lambda event, **kw:rows.append(dict(event=event, **kw)), clock=clock)
        for index in (0, 1, 223, 224, 302):
            rows.clear()
            start, previous = cursor.state.sequence, cursor.state.previous_end
            port = model.flash.Sector(model.Dap(proxy), model.IMAGE, preimage, index, lambda:True,
                                      lambda event, **kw:rows.append(dict(event=event, **kw)),
                                      clock=clock, sleep=clock.sleep, guard=lambda f,*a,**k:f(*a))
            before = len(sdk.write_log)
            port.run()
            stores = flash_stores(model.IMAGE, preimage, index)
            self.assertEqual(tuple(sdk.write_log[before:]), stores)
            result = cursor.verify(native_lines(rows, start, previous), rows,
                                   read_allowed=lambda a:a in port.words.reads, expected_stores=stores)
            self.assertEqual(result['target_writes'], len(stores))
        self.assertFalse(cursor.finished)
        self.assertEqual(bytes(sdk.flash[-964:]), preimage[-964:])


if __name__ == '__main__': unittest.main()
