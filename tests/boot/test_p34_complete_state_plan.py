from pathlib import Path
import sys
import unittest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'Tools/ota'))
from recovery_confirm.flash_plan import APP_START, BANK2_START, geometry, model_manifest, simulate

IMAGE = (ROOT / '.cache/p34-recovery-sources1/r2-a.bin').read_bytes()
CAPTURE = (ROOT / '.cache/p34-finalized-reader-device1/readback.bin').read_bytes()


class PlanTests(unittest.TestCase):
    def model(self):
        # Deliberately non-FF synthetic bytes, never called a physical preimage.
        extent = geometry(IMAGE)
        suffix = bytes(i % 251 for i in range(extent.collateral))
        return model_manifest(IMAGE, CAPTURE + suffix), suffix

    def test_minimal_geometry_and_both_banks(self):
        e = geometry(IMAGE)
        self.assertEqual((e.start, e.payload_end, e.erase_end, e.collateral),
                         (0x08010000, 0x080A743C, 0x080A7800, 964))
        self.assertEqual(len(e.sectors), 303)
        self.assertEqual([sum(bank == n for _, bank in e.sectors) for n in (1, 2)], [224, 79])
        self.assertEqual(e.sectors[224], (BANK2_START, 2))

    def test_existing_4k_port_has_a_different_scope(self):
        e = geometry(IMAGE, unit=4096)
        self.assertEqual((e.erase_end, e.collateral, len(e.sectors)), (0x080A8000, 3012, 304))

    def test_reject_wrong_image_and_geometry(self):
        for data in (IMAGE[:-1], IMAGE+b'X', bytes([IMAGE[0]^1])+IMAGE[1:], bytearray(IMAGE)):
            with self.assertRaises(ValueError): geometry(data)
        for unit in (True, 1, 1024, 8192, 2048.0):
            with self.assertRaises(ValueError): geometry(IMAGE, unit=unit)

    def test_current_capture_is_insufficient_and_must_not_be_ff_padded(self):
        self.assertEqual(len(CAPTURE), len(IMAGE))
        for raw in (CAPTURE, CAPTURE+b'X'*963, CAPTURE+b'X'*965, bytearray(CAPTURE+b'X'*964)):
            with self.assertRaises(ValueError): model_manifest(IMAGE, raw)

    def test_complete_model_preserves_every_collateral_byte(self):
        plan, suffix = self.model()
        done = simulate(plan)
        self.assertEqual(done['actual'], IMAGE + suffix)
        self.assertTrue(done['complete'])
        self.assertFalse(done['reset_allowed'])
        self.assertFalse(plan['physical_preimage_verified'])
        self.assertEqual(done['completed'], 606)

    def test_all_606_interruption_boundaries_preserve_unattempted_sectors(self):
        plan, _ = self.model()
        before = b''.join(item['before'] for item in plan['sectors'])
        for cut in range(606):
            with self.subTest(cut=cut):
                stopped = simulate(plan, fail_after=cut)
                self.assertFalse(stopped['complete'])
                self.assertFalse(stopped['reset_allowed'])
                self.assertEqual(stopped['completed'], cut)
                written, erased = divmod(cut, 2)
                end = (written+erased)*2048
                self.assertEqual(stopped['actual'][:written*2048], plan['desired'][:written*2048])
                if erased: self.assertEqual(stopped['actual'][written*2048:end], b'\xff'*2048)
                self.assertEqual(stopped['actual'][end:], before[end:])
                self.assertTrue(all(APP_START <= s['address'] < 0x080A7800 for s in plan['sectors']))

    def test_invalid_model_cuts_reject_and_final_cut_completes(self):
        plan, _ = self.model()
        for cut in (-1, 607, True, 1.5):
            with self.assertRaises(ValueError): simulate(plan, fail_after=cut)
        self.assertTrue(simulate(plan, fail_after=606)['complete'])


if __name__ == '__main__': unittest.main()
