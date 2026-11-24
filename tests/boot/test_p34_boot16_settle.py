from pathlib import Path
import sys
import unittest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'Tools/ota'))
sys.path.insert(0, str(ROOT / 'tests/boot'))
from recovery_confirm import boot16_settle as settle
from test_p34_boot16 import BootSDK, ORIGINAL, Clock, Dap


class Tests(unittest.TestCase):
    def make(self, mode):
        clock = Clock()
        sdk = BootSDK(clock, ORIGINAL)
        _, status, ctrl, addr = settle.flash.BANKS[0]
        sdk.memory.update({status: 0x20, ctrl: mode, addr: 0x08001000})
        # Bank2 address is passively read, never changed.
        port = settle.LockOnly(Dap(sdk), lambda: True, lambda *a, **k: None,
                              clock=clock, guard=lambda f, *a, **k: f(*a))
        return sdk, port

    def test_only_exact_mode_clear_lock_and_no_payload_mutation(self):
        for mode in (0, 1, 2, 0x80):
            sdk, port = self.make(mode)
            result = port.run()
            wanted = [] if mode == 0x80 else [(settle.flash.BANKS[0][2], 0), (settle.flash.BANKS[0][2], 0x80)]
            self.assertEqual(result['stores'], wanted)
            self.assertEqual(sdk.write_log, wanted)
            self.assertEqual(bytes(sdk.flash), ORIGINAL)
            self.assertFalse(sdk.mutations)
            with self.assertRaises(ValueError): port.run()

    def test_busy_errors_foreign_mode_or_address_reject_without_writes(self):
        _, status, ctrl, addr = settle.flash.BANKS[0]
        cases = ((status, 1), (status, 0x10), (status, 0), (ctrl, 0x42),
                 (addr, 0x08004000), (addr, 0x08000004), (settle.flash.PAUSE, 0),
                 (settle.flash.DHCSR, 0x10001), (settle.flash.FLASH+0x60, 0),
                 (settle.flash.BANKS[1][2], 0))
        for address, value in cases:
            sdk, port = self.make(1)
            sdk.memory[address] = value
            with self.assertRaises(ValueError): port.run()
            self.assertFalse(sdk.write_log)

    def test_uncertain_first_store_does_not_relock_or_retry(self):
        sdk, port = self.make(1)
        original = sdk.JLINKARM_CORESIGHT_WriteAPDPReg
        def write(index, ap, value):
            result = original(index, ap, value)
            return -1 if (index, ap) == (3, 1) else result
        sdk.JLINKARM_CORESIGHT_WriteAPDPReg = write
        with self.assertRaises(OSError): port.run()
        self.assertEqual(sdk.write_log, [(settle.flash.BANKS[0][2], 0)])
        calls = len(sdk.calls)
        with self.assertRaises(ValueError): port.run()
        self.assertEqual(len(sdk.calls), calls)

    def test_between_stores_reset_or_controller_drift_never_relocks(self):
        _, status, ctrl, _ = settle.flash.BANKS[0]
        for address, value in ((settle.flash.DHCSR, 0x02030003),
                               (status, 1), (status, 0),
                               (settle.flash.BANKS[1][2], 0),
                               (settle.flash.PAUSE, 0)):
            sdk, port = self.make(1)
            original = sdk.JLINKARM_CORESIGHT_WriteAPDPReg
            def write(index, ap, data):
                result = original(index, ap, data)
                if sdk.write_log == [(ctrl, 0)]: sdk.memory[address] = value
                return result
            sdk.JLINKARM_CORESIGHT_WriteAPDPReg = write
            with self.assertRaises(ValueError): port.run()
            self.assertEqual(sdk.write_log, [(ctrl, 0)])
            self.assertFalse(sdk.mutations)

    def test_mid_snapshot_reset_owner_and_full_pause_drift_block_second_store(self):
        for problem in ('reset', 'owner', 'pause'):
            sdk, port = self.make(1)
            owned = [True]
            port.owner = lambda: owned[0]
            original = port.words.read32
            fired = []
            def read(address):
                value = original(address)
                if not fired and sdk.write_log and address == settle.flash.PAUSE:
                    fired.append(True)
                    if problem == 'owner': owned[0] = False
                    if problem == 'reset': sdk.memory[settle.flash.DHCSR] = 0x02030003
                    if problem == 'pause': sdk.memory[settle.flash.PAUSE] ^= 1
                return value
            port.words.read32 = read
            with self.assertRaises(ValueError): port.run()
            self.assertEqual(sdk.write_log, [(settle.flash.BANKS[0][2], 0)])
            self.assertFalse(port.done)
            with self.assertRaises(ValueError): port.run()


if __name__ == '__main__': unittest.main()
