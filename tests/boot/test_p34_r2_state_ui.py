from pathlib import Path
import sys
import unittest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'Tools/ota'))
sys.path.insert(0, str(ROOT / 'tests/boot'))
from recovery_confirm import r2_state_ui as combined
from recovery_confirm.ap_journal import JournalSDK
from recovery_confirm.online_log import OnlineLog
from recovery_confirm.mutation_audit import SealedGate
from test_p34_r2_passive_state import Native
from test_p34_install_bridges import Buffer
from test_p34_mutation_audit import record, META
from test_p34_recovery_ports import Clock
from test_p34_online_log import Dap
from test_p34_r2_checkpoint import MAP


class Tests(unittest.TestCase):
    def make(self, problem=None):
        clock = Clock()
        image = (ROOT / '.cache/p34-recovery-sources1/r2-a.bin').read_bytes()
        native = Native(clock, image, problem)
        ui = combined.ui
        obj, pool = 0x20010000, 0x20040000
        native.memory.update({ui.GUARD: 1, ui.MANAGER+4: pool, ui.MANAGER+8: pool+4,
            ui.MANAGER+12: pool+4, pool: obj, obj: ui.VPTR, ui.COST_ACTIVE: 0,
            **{obj+offset: 0 for offset in ui.FIELD_OFFSETS.values()}, obj+8: ui.MANAGER, obj+12: ui.NAME})
        if problem == 'busy-ui': native.memory[obj+ui.FIELD_OFFSETS['mode']] = 2
        if problem == 'bad-ui': native.memory[pool] = 0x90000000
        paths = [Buffer(str(i), '') for i in range(3)]
        native.initialize_log(paths)
        dap = Dap(JournalSDK(native, lambda *a, **k: None, clock=clock))
        logs = OnlineLog(dap, SealedGate(paths, META, record), lambda *a, **k: None,
                         lambda: 180-clock.value, clock=clock)
        logs.switch(read_allowed=lambda _: False, expected_stores=[])
        probe = combined.Probe(dap, logs, image, MAP, lambda: True, lambda: 180-clock.value,
                               clock=clock, sleep=clock.sleep, guard=lambda f, *a, **k: f(*a))
        return probe, native, logs

    def test_real_passive_words_ui_words_and_single_segment_for_idle_or_busy(self):
        for problem in (None, 'busy-ui'):
            probe, native, logs = self.make(problem)
            result = probe.run()
            self.assertEqual(result['result'], 'R2_PASSIVE_UI_STATE_OBSERVED')
            self.assertEqual(result['unloaded_ui_idle_observed'], problem is None)
            self.assertEqual(result['after']['actual_uart_baud'], 923076)
            self.assertEqual(len(result['ui']), 2)
            self.assertFalse(result['ota_ready'])
            self.assertFalse(native.write_log)
            self.assertEqual(logs.gate.index, 2)
            before = len(native.calls)
            with self.assertRaises(ValueError): probe.run()
            self.assertEqual(len(native.calls), before)

    def test_reset_and_ui_or_port_failures_invalidate_combined_owner(self):
        for problem in ('reset', 'bad-ui', 'port'):
            probe, native, _ = self.make(problem)
            if problem == 'port': probe.ui_words.error = 'injected port failure'
            with self.assertRaises(ValueError): probe.run()
            self.assertIsNotNone(probe.error)
            self.assertFalse(native.write_log)
            before = len(native.calls)
            with self.assertRaises(ValueError): probe.run()
            self.assertEqual(len(native.calls), before)


if __name__ == '__main__': unittest.main()
