import ctypes
from pathlib import Path
import sys
import unittest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'Tools/ota'))
sys.path.insert(0, str(ROOT / 'tests/boot'))
from recovery_confirm import boot16_entry as e
from test_p34_recovery_ports import Clock, Dap
from test_p34_rendezvous import media

IMAGE = (ROOT / '.cache/p34-recovery-sources1/r2-b.bin').read_bytes()
MAP = (ROOT / '.cache/p34-early-usb-r2/on/b/app-gcc/X-Track-App-GCC.map').read_bytes()


class SDK:
    def __init__(self, clock):
        self.clock, self.tar, self.writes, self.calls = clock, 0, [], 0
        self.fault = None
        self.memory = {address: 0 for address in e.READS if not e.ui.SRAM_START <= address < e.ui.SRAM_END}
        self.memory.update({a: 0 for a in e.REGS.values()})
        raw = media()['raw']
        self.memory.update({e.state_probe.REGISTERS[k]: v for k, v in raw.items()})
        self.memory.update({a: 0 for a in e.passive.FIELDS.values()})
        self.memory.update({e.passive.CLOCK_ADDR[k]: v for k, v in e.passive.CLOCK.items()})
        self.memory.update({e.passive.QSPI[k]: v for k, v in e.passive.CONFIG.items()})
        for key, value in dict(jedec=0xef4018, retained=0x5034f708, boot_baud=921600,
            core_clock=288000000, baud_divider=156, uart_ctrl1=0x200c).items():
            self.memory[e.passive.FIELDS[key]] = value
        for base, data in ((e.health.PRIMARY+0x400, IMAGE[0x400:0x460]),
                           (e.health.RUNTIME, IMAGE[0x800:0xa0c]), (e.WFI, e.WFI_BYTES)):
            self.memory.update({base+i: int.from_bytes(data[i:i+4], 'little') for i in range(0, len(data), 4)})
        self.memory.update({e.DHCSR: 0x10001, e.health.VTOR: e.health.RUNTIME, e.PAUSE: 4,
            e.FPCTRL: 0x261, 0xe000ed00: 0x410fc241, e.REGS['systick_ctrl']: 7,
            e.REGS['systick_load']: 287999, e.REGS['systick_value']: 100,
            e.health.FLAGS: 0x010104, e.health.HEALTH+32: 1, e.USB_CONNECTION: 1, e.USB_BOT: 0})
        obj, pool, ui = 0x20010000, 0x20040000, e.ui
        self.memory.update({ui.GUARD: 1, ui.MANAGER+4: pool, ui.MANAGER+8: pool+4,
            ui.MANAGER+12: pool+4, pool: obj, obj: ui.VPTR, ui.COST_ACTIVE: 0,
            **{obj+k: 0 for k in ui.FIELD_OFFSETS.values()}, obj+8: ui.MANAGER, obj+12: ui.NAME})
        self.core = {15: e.WFI, 16: 0x01000000, 17: 0x20057da0, 20: 4 << 24}

    def JLINKARM_CORESIGHT_ReadAPDPReg(self, index, ap, output):
        self.clock.value += .000001
        self.calls += 1
        if (index, ap) == (0, 1): value = 0x23000052
        elif (index, ap) == (1, 0): value = 0xf0000040
        elif (index, ap) == (3, 1):
            value = self.memory[self.tar]
            if self.tar == e.DHCSR: self.memory[self.tar] &= ~0x02000000
            self.tar += 4
        else: raise AssertionError((index, ap))
        ctypes.cast(output, ctypes.POINTER(ctypes.c_uint32))[0] = value
        return 0

    def JLINKARM_CORESIGHT_WriteAPDPReg(self, index, ap, value):
        self.clock.value += .000001
        self.calls += 1
        if (index, ap) == (1, 1): self.tar = value; return 0
        if (index, ap) != (3, 1): raise AssertionError((index, ap))
        address = self.tar
        self.tar += 4
        self.writes.append((address, value))
        if address == e.COMP:
            self.memory[address] = value
            if value:
                self.memory[e.DHCSR] = 0x30003
                self.memory[e.REGS['dfsr']] |= 2
        elif address == e.DCRSR: self.memory[e.DCRDR] = self.core[value]
        elif address == e.DHCSR:
            self.memory[address] = 0x10001
            if self.fault == 'release': return -1
        elif address == e.REGS['dfsr']: self.memory[address] &= ~value
        elif address == e.PAUSE:
            if self.fault != 'pause-restore' or value != 4: self.memory[address] = value
        else: raise AssertionError(hex(address))
        return 0


class Tests(unittest.TestCase):
    def make(self):
        clock = Clock()
        sdk = SDK(clock)
        control = e.Control(Dap(sdk), IMAGE, MAP, lambda: True, lambda *a, **k: None,
            clock=clock, sleep=clock.sleep, guard=lambda f, *a, **k: f(*a))
        return clock, sdk, control

    def test_native_stop_release_and_pause_restore_without_payload_or_reset(self):
        _, sdk, control = self.make()
        result = control.acquire()
        self.assertEqual(result['result'], 'R2_B_WFI_HELD')
        self.assertEqual(sdk.memory[e.PAUSE], 0x1004)
        control.release(lambda: True)
        control.restore_pause_running()
        self.assertEqual(sdk.memory[e.PAUSE], 4)
        self.assertEqual(sdk.memory[e.REGS['dfsr']], 0)
        self.assertEqual([v for a, v in sdk.writes if a == e.DHCSR], [0xa05f0001])
        self.assertTrue(all(a in (e.PAUSE, e.COMP, e.DCRSR, e.DHCSR, e.REGS['dfsr']) for a, v in sdk.writes))
        self.assertTrue(all(v in (15, 16, 17, 20) for a, v in sdk.writes if a == e.DCRSR))
        calls = sdk.calls
        for fn in (control.acquire, lambda: control.release(lambda: True), control.restore_pause_running):
            with self.assertRaises(ValueError): fn()
        self.assertEqual(sdk.calls, calls)

    def test_bad_identity_owner_and_foreign_breakpoint_reject_without_writes(self):
        for address, value in ((e.WFI, 0), (e.health.VTOR, 0x08010000), (e.COMP, 1),
                               (e.DHCSR, 0x02010001), (e.health.CFSR, 1)):
            _, sdk, control = self.make()
            sdk.memory[address] = value
            with self.assertRaises(ValueError): control.acquire()
            self.assertFalse(sdk.writes)
            calls = sdk.calls
            with self.assertRaises(ValueError): control.acquire()
            self.assertEqual(sdk.calls, calls)

    def test_media_transfer_dirty_cache_ui_and_foreign_dma_block_before_mutation(self):
        cases = ((e.state_probe.REGISTERS['sd_dma_count'], 1),
                 (e.state_probe.REGISTERS['sdio2_sts'], 1),
                 (e.state_probe.REGISTERS['sd_data_cache_status'], 1),
                 (e.DMA['edma_1'], 1), (e.passive.QSPI['qspi_xip3'], 8),
                 (0x20010000+e.ui.FIELD_OFFSETS['timer'], 1), (e.health.FLAGS, 0))
        for address, value in cases:
            _, sdk, control = self.make()
            sdk.memory[address] = value
            with self.assertRaises(ValueError): control.acquire()
            self.assertFalse(sdk.writes)

    def test_wrong_wfi_context_never_disarms_or_releases(self):
        for selector, value in ((15, 0x08019398), (15, 0x0804d586), (16, 0x100000f),
                                (17, 0x20056000), (20, 1)):
            _, sdk, control = self.make()
            sdk.core[selector] = value
            with self.assertRaises(ValueError): control.acquire()
            self.assertNotIn((e.COMP, 0), sdk.writes)
            self.assertEqual(sdk.memory[e.PAUSE], 0x1004)

    def test_exhausted_enabled_dma_accepted_but_transfer_modes_and_usb_rejected(self):
        for problem in (None, 'count', 'circular', 'm2m', 'external', 'stream', 'usb', 'bot'):
            _, sdk, control = self.make()
            sdk.memory.update({e.DMA['dma1_3']: 0x1093, e.DMA['dma2_4']: 0x2a81,
                e.ENDPOINTS['display_peripheral']: 0x4001300c, e.ENDPOINTS['display_memory']: 0x20005001,
                e.ENDPOINTS['sd_peripheral']: 0x50061080, e.ENDPOINTS['sd_memory']: 0x20006000,
                e.state_probe.REGISTERS['sdio2_dtctrl']: 0x9b})
            if problem == 'count': sdk.memory[e.state_probe.REGISTERS['sd_dma_count']] = 1
            if problem == 'circular': sdk.memory[e.DMA['dma2_4']] |= 0x20
            if problem == 'm2m': sdk.memory[e.DMA['dma2_4']] |= 0x4000
            if problem == 'external': sdk.memory[e.ENDPOINTS['sd_memory']] = 0x90000000
            if problem == 'stream': sdk.memory[e.state_probe.REGISTERS['sdio2_dtctrl']] |= 4
            if problem == 'usb': sdk.memory[e.USB_CONNECTION] = 3
            if problem == 'bot': sdk.memory[e.USB_BOT] = 1
            if problem is None:
                self.assertEqual(control.acquire()['result'], 'R2_B_WFI_HELD')
                control.release(lambda: True)
                control.restore_pause_running()
            else:
                with self.assertRaises(ValueError): control.acquire()
                self.assertFalse(sdk.writes)

    def test_context_pending_fault_or_admission_drift_prevents_release(self):
        for fault in ('pc', 'pending', 'admit', 'dfsr'):
            _, sdk, control = self.make()
            control.acquire()
            if fault == 'pc': sdk.core[15] += 2
            if fault == 'pending': sdk.memory[e.REGS['icsr']] = 1 << 31
            if fault == 'dfsr': sdk.memory[e.REGS['dfsr']] |= 4
            with self.assertRaises(ValueError): control.release(lambda: fault != 'admit')
            self.assertFalse(any(a == e.DHCSR for a, _ in sdk.writes))
            self.assertEqual(sdk.memory[e.PAUSE], 0x1004)

    def test_uncertain_release_and_pause_failure_do_not_retry(self):
        for fault in ('release', 'pause-restore'):
            _, sdk, control = self.make()
            control.acquire()
            sdk.fault = fault
            with self.assertRaises((ValueError, OSError)):
                control.release(lambda: True)
                control.restore_pause_running()
            calls = sdk.calls
            with self.assertRaises(ValueError): control.release(lambda: True)
            self.assertEqual(sdk.calls, calls)
            self.assertEqual([v for a, v in sdk.writes if a == e.DHCSR], [0xa05f0001])

    def test_reset_after_first_guard_and_stage_expiry_latch(self):
        for fault in ('reset', 'deadline'):
            clock, sdk, control = self.make()
            original = control.media
            def changed(halted):
                value = original(halted)
                if not halted:
                    if fault == 'reset': sdk.memory[e.DHCSR] |= 0x02000000
                    else: clock.value += 121
                return value
            control.media = changed
            with self.assertRaises(ValueError): control.acquire()
            self.assertFalse(any(a == e.COMP for a, v in sdk.writes))

    def test_strict_emit_callback_and_initialized_usb_idle(self):
        _, sdk, control = self.make()
        rows = []
        def emit(event, **fields): rows.append((event, fields))
        control.emit = control.words.emit = emit
        sdk.memory[e.USB_BOT] = 7
        control.acquire()
        control.release(lambda: True)
        control.restore_pause_running()
        self.assertTrue(any(event == 'state-word' for event, _ in rows))
        self.assertTrue(any(event == 'boot16-media' for event, _ in rows))


if __name__ == '__main__': unittest.main()
