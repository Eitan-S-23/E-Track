import hashlib
from pathlib import Path
import sys
import unittest
from unittest import mock

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'Tools/ota'))
from recovery_confirm import r2_ui_binding as ui

IMAGE = (ROOT / '.cache/p34-recovery-sources1/r2-a.bin').read_bytes()
MAP = (ROOT / '.cache/p34-early-usb-r2/on/b/app-gcc/X-Track-App-GCC.map').read_bytes()


class Tests(unittest.TestCase):
    def model(self, count=3):
        begin, target = 0x20040000, 0x20010000
        memory = {ui.GUARD: 1, ui.MANAGER + 4: begin, ui.MANAGER + 8: begin + count * 4,
                  ui.MANAGER + 12: begin + count * 4, ui.COST_ACTIVE: 0}
        for i in range(count):
            page = target if i == count-1 else 0x20041000 + i * 8
            memory[begin + i * 4] = page
            memory[page] = ui.VPTR if page == target else 0x08020000
        for key, offset in ui.FIELD_OFFSETS.items(): memory[target + offset] = 0
        memory[target + 8] = ui.MANAGER
        memory[target + 12] = ui.NAME
        reads = []
        def read(address):
            self.assertTrue(ui.sram(address))
            reads.append(address)
            return memory[address]
        return ui.View(IMAGE, MAP, read, lambda: True), memory, reads, target

    def test_bounded_unique_lookup_and_unloaded_idle_state(self):
        for count in (3, 32):
            view, memory, reads, _ = self.model(count)
            result = view.locate()
            self.assertTrue(result['unloaded_idle_ui_observed'])
            self.assertFalse(result['permanent_exclusion'])
            self.assertFalse(result['nor_access_admitted'])
            self.assertLessEqual(len(reads), 128)
            before = len(reads)
            self.assertTrue(view.sample()['unloaded_idle_ui_observed'])
            self.assertEqual(len(reads)-before, 20)
            before = len(reads)
            with self.assertRaises(ValueError): view.locate()
            self.assertEqual(len(reads), before)

    def test_working_with_cleared_pending_and_all_queued_indicators_are_not_idle(self):
        for key, value in (('mode', 2), ('work_flags', 1), ('work_flags', 0x100),
                           ('timer', 0x20030000), ('root', 0x20020000), ('async_flags', 0x10000), ('cost', 1)):
            view, memory, _, target = self.model()
            memory[ui.COST_ACTIVE if key == 'cost' else target + ui.FIELD_OFFSETS[key]] = value
            self.assertFalse(view.locate()['unloaded_idle_ui_observed'], key)

    def test_invalid_pool_pointer_extent_duplicates_and_vptr_reject_before_dereference(self):
        for problem in ('pool', 'count', 'pointer', 'extent', 'duplicate', 'ambiguous', 'missing', 'name'):
            view, memory, reads, target = self.model()
            if problem == 'pool': memory[ui.MANAGER + 4] = 0x90000000
            if problem == 'count': memory[ui.MANAGER + 8] = 0x20040000 + 33*4
            if problem == 'pointer': memory[0x20040000] = 0x90000000
            if problem == 'extent':
                memory[0x20040008] = ui.SRAM_END-4
                memory[ui.SRAM_END-4] = ui.VPTR
            if problem == 'duplicate': memory[0x20040000] = target
            if problem == 'ambiguous': memory[memory[0x20040000]] = ui.VPTR
            if problem == 'missing': memory[target] = 0x08020000
            if problem == 'name': memory[target+12] += 4
            with self.assertRaises(ValueError): view.locate()
            self.assertIsNotNone(view.error)
            self.assertNotIn(0x90000000, reads)
            if problem == 'extent': self.assertNotIn(ui.SRAM_END, reads)

    def test_owner_and_pool_or_object_change_latch_without_retry(self):
        for problem in ('owner', 'pool', 'object', 'vptr'):
            view, memory, reads, target = self.model()
            view.locate()
            if problem == 'owner': view.owner = lambda: False
            if problem == 'pool': memory[ui.MANAGER + 8] -= 4
            if problem == 'object': memory[view.slot] += 4
            if problem == 'vptr': memory[target] += 4
            with self.assertRaises(ValueError): view.sample()
            before = len(reads)
            with self.assertRaises(ValueError): view.sample()
            self.assertEqual(len(reads), before)

    def test_instruction_guard_rejects_changed_code_even_with_injected_identity(self):
        changed = bytearray(IMAGE)
        changed[0x080484da - 0x08010000] ^= 1
        raw = bytes(changed)
        with mock.patch.dict(ui.capture.PLANNED, {hashlib.sha256(raw).hexdigest(): 30276}):
            with self.assertRaisesRegex(ValueError, 'linked instruction differs'):
                ui.verify(raw, MAP)


if __name__ == '__main__': unittest.main()
