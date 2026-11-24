from pathlib import Path
import sys
import unittest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT/'Tools/ota'))
sys.path.insert(0, str(ROOT/'tests/boot'))
from recovery_confirm.held_window import Window
from recovery_entry.state_probe import STATE_WORDS, HEADER_WORDS
import test_p34_recovery_ports as model


class Tests(unittest.TestCase):
    def make(self, **kwargs):
        clock = model.Clock()
        sdk = model.SDK(model.Slave(clock, model.BEFORE+b'R'*128))
        sdk.memory.update(dict.fromkeys(STATE_WORDS, 0))
        header = model.IMAGE[0x400:0x460]
        for i, address in enumerate(HEADER_WORDS):
            sdk.memory[address] = int.from_bytes(header[i*4:i*4+4], 'little')
        rows = []
        window = Window(model.Dap(sdk), lambda event,**fields:rows.append(dict(event=event,**fields)),
                        kwargs.pop('owner', lambda:True), kwargs.pop('remaining', lambda:300),
                        clock=clock, guard=lambda fn,*a,**kw:fn(*a), **kwargs)
        return clock, sdk, rows, window

    def test_existing_owner_passive_snapshot_has_no_ownership_or_write_claim(self):
        _, sdk, rows, window = self.make()
        result = window.capture()
        self.assertEqual(result['header_hex'], model.IMAGE[0x400:0x460].hex())
        self.assertTrue(result['header_crc_valid'])
        self.assertFalse(result['atomic_snapshot'])
        self.assertFalse(result['media_safe_reset_proven'])
        self.assertFalse(result['device_execute_ready'])
        self.assertEqual(window.words.read_count, len(STATE_WORDS))
        self.assertFalse(window.words.writes)
        self.assertFalse(any(call[0] == 'write' and call[1:3] == (3,1) for call in sdk.calls))
        before = len(sdk.calls)
        with self.assertRaises(ValueError): window.capture()
        self.assertEqual(len(sdk.calls), before)

    def test_scope_rejects_commands_fifos_reset_and_nonword_reads(self):
        for name, address, size in (('connect',0,4), ('read',0xa0001100,4), ('read',0xe000ed0c,4),
                                    ('write',0x40020418,4), ('read',HEADER_WORDS[0],8), ('read',True,4)):
            _, sdk, _, window = self.make()
            with self.assertRaises(ValueError): window._call(name, address, size)
            self.assertFalse(sdk.calls)

    def test_local_and_global_expiry_owner_loss_and_nonmonotonic_allowance_latch(self):
        for fault in ('local', 'global', 'owner', 'increase', 'nan'):
            clock, sdk, _, window = self.make()
            if fault == 'local': clock.value = 31
            if fault == 'global': window.remaining = lambda:0
            if fault == 'owner': window.owner = lambda:False
            if fault == 'increase': window.remaining = lambda:301
            if fault == 'nan': window.remaining = lambda:float('nan')
            with self.assertRaises(ValueError): window.capture()
            self.assertFalse(sdk.calls)
            with self.assertRaises(ValueError): window._call('read', HEADER_WORDS[0],4)
            self.assertFalse(sdk.calls)

    def test_owner_lost_after_one_read_stops_without_reconnect(self):
        alive = [True]
        _, sdk, _, window = self.make(owner=lambda:alive[0])
        original = window.words.emit
        def emit(event, **fields):
            original(event, **fields)
            if event == 'recovery-word-read': alive[0] = False
        window.words.emit = emit
        with self.assertRaises(ValueError): window._call('read',HEADER_WORDS[0],4)
        self.assertEqual(window.words.read_count, 1)
        before = len(sdk.calls)
        with self.assertRaises(ValueError): window._call('read',HEADER_WORDS[1],4)
        self.assertEqual(len(sdk.calls), before)

    def test_positive_global_shrink_bounds_native_guard_and_stops_before_target_read(self):
        clock, sdk, _, window = self.make()
        window.remaining = lambda:.01-clock.value
        timeouts = []
        def guard(function, *args, seconds):
            timeouts.append(seconds)
            result = function(*args)
            clock.value += .02
            return result
        window.native_guard = guard
        with self.assertRaises(ValueError): window._call('read',HEADER_WORDS[0],4)
        self.assertEqual(len(sdk.calls), 1)
        self.assertTrue(0 < timeouts[0] <= .01)
        self.assertFalse(any(call[1:3] == (3,1) for call in sdk.calls))
        self.assertLessEqual(window.words.budget.end, .01)
        with self.assertRaises(ValueError): window._call('read',HEADER_WORDS[0],4)
        self.assertEqual(len(sdk.calls), 1)

    def test_normally_decreasing_global_budget_does_not_extend_local_window(self):
        clock, _, _, window = self.make()
        end = window.words.budget.end
        window.remaining = lambda:300-clock.value
        def guard(function, *args, seconds):
            result = function(*args)
            clock.value += .0001
            return result
        window.native_guard = guard
        self.assertTrue(window.capture()['header_crc_valid'])
        self.assertLessEqual(window.words.budget.end, end)

    def test_invalid_window_configuration_never_accesses_native(self):
        for seconds in (True, 0, 61, float('inf')):
            with self.assertRaises(ValueError): self.make(seconds=seconds)
        for left in (True, 0, float('nan'), float('inf')):
            with self.assertRaises(ValueError): self.make(remaining=lambda:left)


if __name__ == '__main__': unittest.main()
