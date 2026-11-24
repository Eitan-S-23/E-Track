from pathlib import Path
import sys
import unittest
from unittest import mock

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'Tools/ota'))
sys.path.insert(0, str(ROOT / 'tests/boot'))
import p34_boot16_display as run
from recovery_confirm import boot16_display_entry as d
from test_p34_boot16_entry import SDK, IMAGE, MAP, Clock, Dap
import test_p34_boot16_probe as original


class Tests(unittest.TestCase):
    def make(self, problem=None):
        clock = Clock()
        sdk = SDK(clock)
        e = d.prior
        count_address = e.state_probe.REGISTERS['display_dma_count']
        sdk.memory.update({e.DMA['dma1_3']: 0x1093, e.ENDPOINTS['display_peripheral']: 0x4001300c,
            e.ENDPOINTS['display_memory']: 0x200271df, count_address: 8300})
        held_reads = [0]
        old = sdk.JLINKARM_CORESIGHT_ReadAPDPReg
        def read(index, ap, pointer):
            if (index, ap, sdk.tar) == (3, 1, count_address) and sdk.memory[e.DHCSR] & 0x20000:
                held_reads[0] += 1
                values = [8300, 100, 0] if problem != 'immediate' else [0]
                sdk.memory[count_address] = values[min(held_reads[0]-1, len(values)-1)]
                if problem == 'stuck': sdk.memory[count_address] = 8300
                if problem == 'increase': sdk.memory[count_address] = 8300+held_reads[0]
                if problem == 'endpoint' and held_reads[0] > 1: sdk.memory[e.ENDPOINTS['display_memory']] += 4
                if problem == 'mode' and held_reads[0] > 1: sdk.memory[e.DMA['dma1_3']] |= 0x20
                if problem == 'reset' and held_reads[0] > 1: sdk.memory[e.DHCSR] |= 0x02000000
            return old(index, ap, pointer)
        sdk.JLINKARM_CORESIGHT_ReadAPDPReg = read
        c = d.Control(Dap(sdk), IMAGE, MAP, lambda: True, lambda *a, **k: None,
            clock=clock, sleep=clock.sleep, guard=lambda fn, *a, **k: fn(*a))
        return sdk, c, held_reads

    def test_running_and_one_held_completion_then_unchanged_release(self):
        for problem in (None, 'immediate'):
            sdk, c, reads = self.make(problem)
            result = c.acquire()
            self.assertEqual(result['result'], 'R2_B_WFI_HELD')
            self.assertTrue(c.display_waited)
            c.release(lambda: True)
            c.restore_pause_running()
            self.assertEqual([v for a, v in sdk.writes if a == d.prior.DHCSR], [0xa05f0001])
            self.assertGreaterEqual(reads[0], 3)

    def test_stuck_increasing_changed_endpoint_mode_or_reset_never_releases(self):
        for problem in ('stuck', 'increase', 'endpoint', 'mode', 'reset'):
            sdk, c, _ = self.make(problem)
            with self.subTest(problem=problem), self.assertRaises(ValueError): c.acquire()
            self.assertTrue(c.display_waited)
            self.assertFalse(c.release_attempted)
            self.assertEqual(sdk.memory[d.prior.PAUSE], 0x1004)

    def test_running_display_does_not_hide_storage_usb_wwdt_or_range_blockers(self):
        e = d.prior
        for address, value in ((0x40002c00, 0x80), (e.USB_CONNECTION, 3), (e.USB_BOT, 2),
            (e.state_probe.REGISTERS['sd_dma_count'], 1), (e.state_probe.REGISTERS['sd_data_cache_status'], 1),
            (e.ENDPOINTS['display_memory'], e.ui.SRAM_END-65534)):
            sdk, c, _ = self.make()
            sdk.memory[address] = value
            with self.assertRaises(ValueError): c.acquire()
            self.assertFalse(sdk.writes)

    def test_frozen_owner_log_and_close_regressions_with_new_control(self):
        actual = run.prior.execute
        def execute(*args, **kwargs): return actual(*args, **kwargs, control_type=d.Control)
        suite = unittest.defaultTestLoader.loadTestsFromTestCase(original.Tests)
        with mock.patch.object(original.run, 'execute', side_effect=execute):
            result = unittest.TestResult()
            suite.run(result)
        self.assertTrue(result.wasSuccessful(), result.errors+result.failures)
        self.assertEqual(result.testsRun, 5)

    def test_each_completion_native_call_capped_by_one_second_remaining(self):
        _, c, _ = self.make()
        caps = []
        def guard(fn, *args, seconds):
            if c.display_deadline is not None:
                left = c.display_deadline-c.clock()
                self.assertTrue(0 < seconds <= left <= 1.)
                caps.append(seconds)
            return fn(*args)
        c.guard = guard
        c.acquire()
        self.assertTrue(caps)


if __name__ == '__main__': unittest.main()
