import os
from pathlib import Path
import sys
from types import SimpleNamespace
import unittest
from unittest import mock

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'Tools/ota'))
from p34_session import Store
from recovery_confirm.boot16_archive import Archive, SIZES


class ArchiveTests(unittest.TestCase):
    def make(self):
        store = Store(ROOT)
        out = store.checked(Path(os.environ['P34_BOOT16_TEST_OUT']) / self._testMethodName)
        for name in (*[n+'.bin' for n in SIZES], 'prewrite.json'): store.checked(out / name)
        self.assertFalse(out.exists())
        out.mkdir(parents=True)
        return Archive(store, out, {'source': 'host-fixture'}), out

    def capture(self, archive, name, raw):
        for offset in range(0, len(raw), 32768): archive(name, offset, raw[offset:offset+32768])

    def test_archive_durable_exact_prewrite_and_no_overwrite(self):
        archive, out = self.make()
        boot, image = b'B'*65536, b'A'*619580
        for label in ('before', 'after'):
            self.capture(archive, label+'-boot', boot)
            self.capture(archive, label+'-app', image)
            self.assertEqual(len(archive.verify(label, boot, image)), 2)
        body = SimpleNamespace(phase='PROGRAM', boot_may_have_changed=False, preimage=boot, image=image,
            desired=boot, direction='activate', control=SimpleNamespace(before={'pause': 4}, context_before={'msp': 123}))
        archive.checkpoint(body)
        value = archive.store.read(out / 'prewrite.json')
        self.assertEqual(value['context'], {'msp': 123})
        with self.assertRaises(ValueError): archive.checkpoint(body)
        with self.assertRaises(ValueError): Archive(archive.store, out, {})

    def test_archive_wrong_offset_failure_is_latched(self):
        archive, _ = self.make()
        with self.assertRaises(ValueError): archive('before-boot', 32768, b'B'*32768)
        with self.assertRaises(ValueError): archive('before-boot', 0, b'B'*32768)
        self.assertTrue(archive.failed)

    def test_archive_full_bytes_checked_not_just_size(self):
        archive, _ = self.make()
        self.capture(archive, 'before-boot', b'B'*65536)
        self.capture(archive, 'before-app', b'A'*619580)
        with self.assertRaises(ValueError): archive.verify('before', b'C'*65536, b'A'*619580)

    def test_archive_fsync_failure_is_consumed_without_checkpoint(self):
        archive, _ = self.make()
        with mock.patch('recovery_confirm.boot16_archive.os.fsync', side_effect=OSError('injected fsync')):
            with self.assertRaises(OSError): archive('before-boot', 0, b'B'*32768)
        self.assertFalse(archive.checkpointed)
        with self.assertRaises(ValueError): archive('before-boot', 0, b'B'*32768)

    def test_short_write_is_latched(self):
        archive, _ = self.make()
        file = mock.MagicMock()
        file.__enter__.return_value = file
        file.write.return_value = 5
        with mock.patch('pathlib.Path.open', return_value=file):
            with self.assertRaises(OSError): archive('before-boot', 0, b'B'*32768)
        self.assertTrue(archive.failed)
        self.assertFalse(archive.checkpointed)

    def test_checkpoint_failure_consumes_capability(self):
        archive, _ = self.make()
        boot, image = b'B'*65536, b'A'*619580
        self.capture(archive, 'before-boot', boot)
        self.capture(archive, 'before-app', image)
        body = SimpleNamespace(phase='PROGRAM', boot_may_have_changed=False, preimage=boot, image=image,
            desired=boot, direction='activate', control=SimpleNamespace(before={}, context_before={}))
        with mock.patch.object(archive.store, 'write', side_effect=OSError('checkpoint failure')):
            with self.assertRaises(OSError): archive.checkpoint(body)
        self.assertFalse(archive.checkpointed)
        self.assertTrue(archive.failed)
        with self.assertRaises(ValueError): archive.checkpoint(body)


if __name__ == '__main__': unittest.main()
