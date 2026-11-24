import copy
import json
from pathlib import Path
import sys
import unittest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'Tools/ota'))
sys.path.insert(0, str(ROOT / 'tests/boot'))
from recovery_confirm import r2_passive_state as state
from recovery_confirm.ap_journal import JournalSDK
from recovery_confirm.online_log import OnlineLog
from recovery_confirm.mutation_audit import SealedGate
from test_p34_install_bridges import Buffer, Logged
from test_p34_mutation_audit import record, META
from test_p34_recovery_ports import FlashSDK, Clock
from test_p34_online_log import Dap
from test_p34_r2_checkpoint import MAP


class Native(Logged, FlashSDK):
    def __init__(self, clock, image, problem):
        super().__init__(clock, image)
        self.problem, self.dhcsr_reads = problem, 0
        self.memory.update({state.health.DHCSR: 0, state.health.VTOR: state.health.RUNTIME})
        self.memory.update({address: 0 for address in state.FIELDS.values()})
        self.memory.update({state.CLOCK_ADDR[k]: v for k, v in state.CLOCK.items()})
        self.memory.update({state.QSPI[k]: v for k, v in state.CONFIG.items()})
        for key, value in dict(jedec=0xef4018, retained=0x5034f708, boot_baud=921600,
            core_clock=288000000, baud_divider=156, uart_ctrl1=0x200c).items():
            self.memory[state.FIELDS[key]] = value
        if problem == 'identity': self.flash[0x400] ^= 1
        if problem == 'active': self.memory[state.FIELDS['session']] = 1

    def JLINKARM_CORESIGHT_ReadAPDPReg(self, index, ap, out):
        if (index, ap, self.tar) == (3, 1, state.health.DHCSR):
            self.dhcsr_reads += 1
            if self.problem == 'reset' and self.dhcsr_reads == 3:
                self.memory[state.health.DHCSR] = 0x02000000
            else: self.memory[state.health.DHCSR] = 0
        return super().JLINKARM_CORESIGHT_ReadAPDPReg(index, ap, out)


class Tests(unittest.TestCase):
    def make(self, problem=None):
        clock = Clock()
        image = (ROOT / '.cache/p34-recovery-sources1/r2-a.bin').read_bytes()
        native = Native(clock, image, problem)
        paths = [Buffer(str(i), '') for i in range(3)]
        native.initialize_log(paths)
        dap = Dap(JournalSDK(native, lambda *a, **k: None, clock=clock))
        logs = OnlineLog(dap, SealedGate(paths, META, record), lambda *a, **k: None,
                         lambda: 180-clock.value, clock=clock)
        logs.switch(read_allowed=lambda _: False, expected_stores=[])
        probe = state.Probe(dap, logs, image, MAP, lambda: True, lambda: 180-clock.value,
                            clock=clock, sleep=clock.sleep, guard=lambda f, *a, **k: f(*a))
        return probe, native, logs

    def test_real_words_passive_two_samples_never_claim_nor_qualification(self):
        for problem in (None, 'active'):
            probe, native, logs = self.make(problem)
            result = probe.run()
            self.assertEqual(result['result'], 'R2_PASSIVE_STATE_OBSERVED')
            self.assertEqual(result['after']['idle_observed'], problem != 'active')
            self.assertEqual(result['after']['actual_uart_baud'], 923076)
            self.assertTrue(result['after']['retained_921600'])
            self.assertFalse(result['after']['other_nor_writers_excluded'])
            self.assertFalse(result['after']['live_mapping_qualified'])
            self.assertFalse(result['ota_ready'])
            self.assertEqual(result['nor_bytes_read'], 0)
            self.assertEqual(logs.gate.index, 2)
            self.assertFalse(native.write_log)
            before = len(native.calls)
            with self.assertRaises(ValueError): probe.run()
            self.assertEqual(len(native.calls), before)

    def test_reset_identity_owner_and_log_failures_latch(self):
        for problem in ('reset', 'identity', 'owner', 'log'):
            probe, native, logs = self.make(problem)
            if problem == 'owner': probe.owner = lambda: False
            if problem == 'log': native.hook = lambda: setattr(native, 'fault', 'blank')
            with self.assertRaises((RuntimeError, ValueError)): probe.run()
            self.assertIsNotNone(probe.error)
            self.assertFalse(native.write_log)
            if problem == 'reset': self.assertTrue(probe.reset_seen)

    def test_fields_equal_original_r2_cross_compiled_session_abi(self):
        layout = json.loads((ROOT / '.cache/p34-r2-live-layout1/result.json').read_text())
        self.assertEqual(layout['result'], 'R2_SESSION_ABI_DERIVED')
        base = layout['symbols']['_ZL13s_ble_session']
        self.assertEqual(state.FIELDS['session'], base + layout['members']['state']['offset'])
        self.assertEqual(state.FIELDS['isr_active'], base + layout['members']['isr_active']['offset'])
        self.assertEqual(state.FIELDS['epoch'], layout['symbols']['s_ble_epoch'])
        self.assertFalse(any(0x90000000 <= a < 0x91000000 for a in state.READS))
        self.assertNotIn(0xa0001100, state.READS)
        self.assertNotIn(0xa0001018, state.READS)

    def test_unknown_clock_bad_divider_or_retention_are_not_guessed(self):
        probe, _, _ = self.make()
        probe.active = True
        row = probe.sample()
        for key, value in (('core_clock', 0), ('baud_divider', 0), ('retained', 0), ('retention_error', 1)):
            changed = copy.deepcopy(row)
            changed['fields'][key] = value
            result = state.decode(changed)
            self.assertFalse(result['ota_ready'])
            if key in ('core_clock', 'baud_divider'): self.assertIsNone(result['actual_uart_baud'])
            else: self.assertFalse(result['retained_921600'])
        with self.assertRaises(ValueError): state.decode(dict(row, fields={}))


if __name__ == '__main__': unittest.main()
