"""Read-only archival identity tests; no stale evidence is rewritten."""
import copy
from pathlib import Path
import unittest
from unittest import mock
import p34_session as cli
import p34_historical_inputs as historical


class Tests(unittest.TestCase):
    def test_exact_current_record_is_not_redirected(self):
        item = cli.record(historical.ROOT / "Libraries/OTA/ota_backup.h")
        self.assertEqual(historical.resolve(item), Path(item["path"]))

    def test_archived_bytes_match_original_record_without_mutating_it(self):
        for name, (relative, digest) in historical.ARCHIVES.items():
            snapshot = historical.ROOT / relative
            item = dict(cli.record(snapshot), path=str(historical.ROOT / name))
            before = copy.deepcopy(item)
            self.assertEqual(item["sha256"], digest)
            self.assertEqual(historical.resolve(item), snapshot)
            self.assertEqual(item, before)

    def test_wrong_hash_or_length_cannot_use_archive(self):
        snapshot = historical.ROOT / historical.ARCHIVES["Libraries/OTA/ota_backup.h"][0]
        item = dict(cli.record(snapshot), path=str(historical.ROOT / "Libraries/OTA/ota_backup.h"))
        for bad in (dict(item, sha256="0" * 64), dict(item, bytes=item["bytes"] + 1)):
            with self.assertRaises(RuntimeError): historical.resolve(bad)

    def test_unlisted_path_cannot_borrow_header_archive(self):
        snapshot = historical.ROOT / historical.ARCHIVES["Libraries/OTA/ota_backup.h"][0]
        item = dict(cli.record(snapshot), path=str(historical.ROOT / "Libraries/OTA/ota_backup.c"))
        with self.assertRaises(RuntimeError): historical.resolve(item)

    def test_corrupted_archive_fails(self):
        snapshot = historical.ROOT / historical.ARCHIVES["Libraries/OTA/ota_backup.h"][0]
        item = dict(cli.record(snapshot), path=str(historical.ROOT / "Libraries/OTA/ota_backup.h"))
        original = Path.read_bytes
        def read(path):
            return b"corrupted" if path == snapshot else original(path)
        with mock.patch.object(Path, "read_bytes", read), self.assertRaises(RuntimeError):
            historical.resolve(item)

    def test_runtime_record_remains_actual_current_bytes(self):
        path = historical.ROOT / "Libraries/OTA/ota_backup.h"
        self.assertNotEqual(cli.record(path)["sha256"], historical.ARCHIVES["Libraries/OTA/ota_backup.h"][1])

    def test_original_decoder_equivalence_is_preserved(self):
        assets = cli.load_module("historical_equivalence_test", historical.ROOT / "Tools/ota/p34_patch_assets.py")
        old = assets.prep.read(assets.OUT / "result.json")
        self.assertEqual(assets.decoder_equivalence(assets.prep.read(assets.prep.HOST_TESTS)), old["decoder_equivalence"])
