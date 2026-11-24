"""Offline archive and rename checks. No device commands or data extraction."""
import io
from pathlib import Path
import runpy
import tarfile
import unittest

ROOT = Path(__file__).resolve().parents[2]
m = runpy.run_path(str(ROOT / "Tools/ota/p34_signing_migration.py"))


def archive(extra=(), omit=None):
    stream = io.BytesIO()
    with tarfile.open(fileobj=stream, mode="w") as out:
        for name in m["ROOTS"]:
            if name == omit:
                continue
            item = tarfile.TarInfo(name)
            item.type = tarfile.DIRTYPE
            out.addfile(item)
        for name, kind in extra:
            item = tarfile.TarInfo(name)
            item.type = kind
            item.size = 3 if kind == tarfile.REGTYPE else 0
            if kind in (tarfile.SYMTYPE, tarfile.LNKTYPE): item.linkname = "../escape"
            out.addfile(item, io.BytesIO(b"abc") if kind == tarfile.REGTYPE else None)
    return stream.getvalue()


class Tests(unittest.TestCase):
    def test_archive_and_byte_preserving_restore(self):
        data = archive([(n, tarfile.REGTYPE) for n in (
            "files/p34-experiment.json", "files/p34-observations/capture/snapshot-1.jsonl",
            "app_flutter/firmware/old.etu", "databases/app.db", "shared_prefs/Flutter.xml")])
        original = m["archive_manifest"](data)
        restored, manifest = m["restore_archive"](data)
        self.assertEqual(m["archive_manifest"](restored), manifest)
        self.assertEqual(manifest, {m["restore_name"](k): v for k, v in original.items()})
        self.assertIn("files/p34-migration-original-config.json", manifest)
        self.assertNotIn("files/p34-experiment.json", manifest)
        self.assertIn("files/p34-migration-observations/capture/snapshot-1.jsonl", manifest)

    def test_bad_paths_and_links(self):
        for name, kind in (("../escape", tarfile.REGTYPE), ("files/../escape", tarfile.REGTYPE),
                           ("/files/a", tarfile.REGTYPE), ("cache/a", tarfile.REGTYPE),
                           ("files/a\\b", tarfile.REGTYPE), ("files/link", tarfile.SYMTYPE),
                           ("files/hard", tarfile.LNKTYPE), ("files/fifo", tarfile.FIFOTYPE)):
            with self.subTest(name=name, kind=kind), self.assertRaises(ValueError):
                m["archive_manifest"](archive([(name, kind)]))

    def test_missing_root_and_duplicate(self):
        with self.assertRaises(ValueError):
            m["archive_manifest"](archive(omit="files"))
        with self.assertRaises(ValueError):
            m["archive_manifest"](archive([("files/x", tarfile.REGTYPE)] * 2))

    def test_mapping_collision_rejected(self):
        with self.assertRaises(ValueError):
            m["restore_archive"](archive([("files/p34-experiment.json", tarfile.REGTYPE),
                                        ("files/p34-migration-original-config.json", tarfile.REGTYPE)]))

    def test_empty_archive_rejected(self):
        with self.assertRaises(ValueError):
            m["archive_manifest"](b"")


if __name__ == "__main__":
    result = unittest.TextTestRunner(verbosity=2).run(unittest.defaultTestLoader.loadTestsFromTestCase(Tests))
    b, _, _, _ = m["runtime"]()
    b.save("migration/tests.json", dict(passed=result.wasSuccessful(), tests=result.testsRun,
        source=b.record(ROOT / "Tools/ota/p34_signing_migration.py"),
        test_source=b.record(Path(__file__)), device_operations=0))
    raise SystemExit(not result.wasSuccessful())
