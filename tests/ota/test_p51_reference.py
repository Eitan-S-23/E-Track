"""Exact-base reference preparation; no device, subprocess or package generation."""
import importlib.util
from pathlib import Path
import struct
import sys
import sysconfig
import unittest

ROOT = Path(__file__).resolve().parents[2]
sys.path[:0] = [str(ROOT / 'Tools'), sysconfig.get_path('purelib'), sysconfig.get_path('platlib')]
import etu_pack as pack
import etu_unpack as unpack

spec = importlib.util.spec_from_file_location('p51_reference', ROOT / 'Tools/ota/p34-acceptance/reference.py')
reference = importlib.util.module_from_spec(spec)
spec.loader.exec_module(reference)


class ExactBaseTests(unittest.TestCase):
    def setUp(self):
        image = bytearray((n * 37 + 13) % 256 for n in range(8192))
        image[0x400:0x460] = pack.build_fw_header(bytes(image), '3.3.13', 1793038630)
        self.raw = bytes(image)

    def prepare(self, raw=None, base='3.3.13', target='3.3.16', timestamp=1793038630, preserve=True):
        return reference.prepare_images(self.raw if raw is None else raw, base, target,
                                        timestamp, preserve, pack, unpack)

    def test_preserve_base_byte_exact(self):
        base, target = self.prepare(timestamp=1793038631)
        self.assertEqual(base, self.raw)
        self.assertEqual(struct.unpack_from('<I', target, 0x41c)[0], 1793038631)

    def test_target_only_changes_header(self):
        _, target = self.prepare()
        self.assertEqual(target[:0x400], self.raw[:0x400])
        self.assertEqual(target[0x460:], self.raw[0x460:])
        unpack.verify_fw_header(target)
        self.assertEqual(struct.unpack_from('<I', target, 0x408)[0], 30316)

    def test_legacy_finalization_is_unchanged(self):
        base, target = self.prepare(timestamp=1786320000, preserve=False)
        for actual, version in ((base, '3.3.13'), (target, '3.3.16')):
            expected = bytearray(self.raw)
            expected[0x400:0x460] = pack.build_fw_header(self.raw, version, 1786320000)
            self.assertEqual(actual, bytes(expected))
        self.assertNotEqual(base, self.raw)

    def test_wrong_declared_base_rejected(self):
        for version in ('3.3.12', '3.3.13-other'):
            with self.subTest(version=version), self.assertRaisesRegex(ValueError, 'declared base'):
                self.prepare(base=version)

    def test_corrupted_base_rejected(self):
        for offset in (0x410, 0x500):
            changed = bytearray(self.raw)
            changed[offset] ^= 1
            with self.subTest(offset=offset), self.assertRaises(ValueError):
                self.prepare(raw=bytes(changed))

    def test_truncated_base_rejected(self):
        with self.assertRaises(ValueError):
            self.prepare(raw=self.raw[:0x45f])

    def test_nonforward_target_rejected(self):
        for version in ('3.3.13', '3.3.12'):
            with self.subTest(version=version), self.assertRaisesRegex(ValueError, 'newer'):
                self.prepare(target=version)

    def test_invalid_timestamp_rejected(self):
        for timestamp in (-1, 2**32, True, 1.5):
            with self.subTest(timestamp=timestamp), self.assertRaisesRegex(ValueError, 'uint32'):
                self.prepare(timestamp=timestamp)


if __name__ == '__main__':
    unittest.main(verbosity=2)
