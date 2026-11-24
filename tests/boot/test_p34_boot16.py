import unittest
from pathlib import Path
import sys
from types import FunctionType

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'Tools/ota'))
sys.path.insert(0, str(ROOT / 'tests/boot'))
from recovery_confirm import boot16 as boot
from recovery_confirm import flash_port as flash
from test_p34_recovery_ports import FlashSDK, Dap, Clock

ORIGINAL = (ROOT / '.cache/p34-native-acquire1/boot-readback.bin').read_bytes()
CANDIDATE = (ROOT / '.cache/p34-bc-target/b16/boot/X-Track-Boot.bin').read_bytes()
PLAN = boot.Plan(ORIGINAL, CANDIDATE)


def relocate(function):
    return FunctionType(function.__code__, dict(function.__globals__, APP_START=boot.START),
                        function.__name__, function.__defaults__, function.__closure__)


class BootSDK(FlashSDK):
    # The model's storage origin changes; real port I/O is not translated.
    JLINKARM_CORESIGHT_ReadAPDPReg = relocate(FlashSDK.JLINKARM_CORESIGHT_ReadAPDPReg)
    JLINKARM_CORESIGHT_WriteAPDPReg = relocate(FlashSDK.JLINKARM_CORESIGHT_WriteAPDPReg)


class Tests(unittest.TestCase):
    def model(self, index=0, direction='activate', preimage=ORIGINAL, fault=None):
        clock = Clock()
        sdk = BootSDK(clock, preimage + b'APP!'*1024, fault)
        port = boot.Sector(Dap(sdk), PLAN, preimage, index, direction,
            lambda: True, lambda *a, **k: None, clock=clock, sleep=clock.sleep,
            guard=lambda fn, *a, **k: fn(*a))
        return clock, sdk, port

    def test_all_eight_activate_and_restore_sectors_exact_stores(self):
        for direction, before in (('activate', ORIGINAL), ('restore', PLAN.activated)):
            for index in range(8):
                with self.subTest(direction=direction, index=index):
                    _, sdk, port = self.model(index, direction, before)
                    result = port.run()
                    expected = PLAN.desired(direction, before)
                    start, end = index*2048, (index+1)*2048
                    self.assertEqual(bytes(sdk.flash[start:end]), expected[start:end])
                    self.assertEqual(bytes(sdk.flash[:start]), before[:start])
                    self.assertEqual(bytes(sdk.flash[end:65536]), before[end:])
                    self.assertEqual(bytes(sdk.flash[65536:]), b'APP!'*1024)
                    self.assertEqual(tuple(sdk.write_log), boot.stores(PLAN, before, index, direction))
                    self.assertEqual((result['bank'], result['reset_allowed']), (1, False))
                    self.assertEqual([x for x in sdk.mutations if x[0] == 'erase'],
                                     [('erase', boot.START+start)])
                    calls = len(sdk.calls)
                    with self.assertRaises(ValueError): port.run()
                    self.assertEqual(len(sdk.calls), calls)

    def test_partial_first16k_can_only_restore_known_original(self):
        partial = b'\xff'*2048 + PLAN.activated[2048:8192] + ORIGINAL[8192:]
        for index in (0, 3, 7):
            _, sdk, port = self.model(index, 'restore', partial)
            port.run()
            self.assertEqual(bytes(sdk.flash[index*2048:(index+1)*2048]),
                             ORIGINAL[index*2048:(index+1)*2048])
        with self.assertRaises(ValueError): PLAN.desired('activate', partial)

    def test_bad_assets_geometry_direction_and_suffix_rejected_before_native(self):
        for original, candidate in ((ORIGINAL[:-1], CANDIDATE), (ORIGINAL, CANDIDATE[:-1]),
                                    (ORIGINAL, bytes(14800))):
            with self.assertRaises(ValueError): boot.Plan(original, candidate)
        for index in (-1, 8, True, 1.0):
            with self.assertRaises(ValueError): self.model(index)
            with self.assertRaises(ValueError): boot.stores(PLAN, ORIGINAL, index, 'activate')
        for direction, data in (('other', ORIGINAL), ('restore', ORIGINAL[:-1]),
                                ('restore', ORIGINAL[:16384]+bytes(49152)),
                                ('activate', PLAN.activated)):
            with self.assertRaises(ValueError): self.model(0, direction, data)

    def test_arbitrary_write_is_denied_before_native(self):
        for address, value in ((boot.END, 0), (0x08010000, 0), (flash.FLASH+8, 0),
                               (flash.FLASH+0x1c, 0), (0xe000ed0c, 0x05fa0004)):
            _, sdk, port = self.model()
            with self.assertRaises(ValueError): port.words.write32(address, value)
            self.assertFalse(sdk.calls)
            self.assertFalse(sdk.mutations)

    def test_admission_faults_reject_before_flash_mutation(self):
        for fault in ('running', 'reset', 'pause', 'clock', 'protection', 'preimage', 'csw', 'dp'):
            _, sdk, port = self.model()
            if fault == 'running': sdk.memory[flash.DHCSR] &= ~0x20000
            if fault == 'reset': sdk.memory[flash.DHCSR] |= 0x02000000
            if fault == 'pause': sdk.memory[flash.PAUSE] = 0
            if fault == 'clock': sdk.memory[0x40023800] ^= 1
            if fault == 'protection': sdk.memory[flash.FLASH+0x2c] = 0
            if fault == 'preimage': sdk.flash[0] ^= 1
            if fault == 'csw': sdk.csw ^= 1
            if fault == 'dp': sdk.dp |= 0x20
            with self.assertRaises((ValueError, OSError)): port.run()
            self.assertFalse(sdk.mutations)

    def test_flash_failures_latch_without_cleanup_or_resume(self):
        for fault in ('stale', 'ignored', 'busy', 'protected', 'noerase', 'delivered', 'dp-after'):
            with self.subTest(fault=fault):
                _, sdk, port = self.model(fault=fault)
                with self.assertRaises((ValueError, OSError)): port.run()
                self.assertFalse(port.done)
                self.assertIsNotNone(port.error)
                calls = len(sdk.calls)
                with self.assertRaises(ValueError): port.run()
                self.assertEqual(len(sdk.calls), calls)
                self.assertFalse(any(a in (0xe000ed0c, 0xe000edf0) for a, _ in sdk.write_log))
                self.assertEqual(bytes(sdk.flash[16384:65536]), ORIGINAL[16384:])

    def test_late_settled_observation_is_not_false_program_failure(self):
        clock, sdk, port = self.model()
        port.used = True
        sdk.memory[port.status_reg] = 0x20
        original = port.check
        def check(**kwargs):
            original(**kwargs)
            clock.value += .6
        port.check = check
        port.wait(.5)
        self.assertFalse(sdk.mutations)


if __name__ == '__main__':
    unittest.main()
