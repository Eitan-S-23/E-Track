"""Package replay is an identical envelope, not a reusable nonce API."""

import argparse
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "Tools"))
import etu_pack as pack


class PackageReplayTests(unittest.TestCase):
    def setUp(self):
        parent = ROOT / ".cache/firmware-pack-tests"
        parent.resolve().relative_to(ROOT.resolve())
        for ancestor in [parent, *parent.parents]:
            if ancestor.exists() and (ancestor.is_symlink() or getattr(ancestor.stat(), "st_file_attributes", 0) & 0x400):
                raise RuntimeError("reparse output")
        parent.mkdir(parents=True, exist_ok=True)
        self.directory = tempfile.TemporaryDirectory(dir=parent)
        self.addCleanup(self.directory.cleanup)
        self.root = Path(self.directory.name)
        tempdir = patch.object(tempfile, "tempdir", str(self.root))
        tempdir.start()
        self.addCleanup(tempdir.stop)
        self.app = self.root / "app.bin"
        self.app.write_bytes(bytes(range(256)) * 16)
        self.key = patch.dict(os.environ, {"OTA_AES_KEY": "01" * 16,
            "TEMP": str(self.root), "TMP": str(self.root), "TMPDIR": str(self.root)})
        self.key.start()
        self.addCleanup(self.key.stop)

    def arguments(self, name="one.etu", reference=None, version=20801):
        return argparse.Namespace(app=str(self.app), out=str(self.root / name), target_vcode=version,
            ver_name="2.8.1", lzma_dict=16384, key_id=1, reproduce_from=reference)

    def test_replays_actual_full_package(self):
        one = self.arguments()
        self.assertEqual(pack.cmd_pack_full(one), 0)
        two = self.arguments("two.etu", one.out)
        self.assertEqual(pack.cmd_pack_full(two), 0)
        self.assertEqual(Path(one.out).read_bytes(), Path(two.out).read_bytes())

    def test_default_nonce_remains_random(self):
        one, two = self.arguments(), self.arguments("two.etu")
        pack.cmd_pack_full(one); pack.cmd_pack_full(two)
        self.assertNotEqual(Path(one.out).read_bytes()[16:32], Path(two.out).read_bytes()[16:32])

    def test_refuses_different_plaintext_before_output(self):
        one = self.arguments(); pack.cmd_pack_full(one)
        self.app.write_bytes(b"changed image")
        two = self.arguments("two.etu", one.out)
        with self.assertRaisesRegex(ValueError, "differs"):
            pack.cmd_pack_full(two)
        self.assertFalse(Path(two.out).exists())

    def test_refuses_different_key(self):
        one = self.arguments(); pack.cmd_pack_full(one)
        with patch.dict(os.environ, {"OTA_AES_KEY": "02" * 16}):
            with self.assertRaisesRegex(ValueError, "differs"):
                pack.cmd_pack_full(self.arguments("two.etu", one.out))

    def test_refuses_different_header_identity(self):
        one = self.arguments(); pack.cmd_pack_full(one)
        with self.assertRaisesRegex(ValueError, "differs"):
            pack.cmd_pack_full(self.arguments("two.etu", one.out, version=20802))

    def test_refuses_corrupted_reference(self):
        one = self.arguments(); pack.cmd_pack_full(one)
        raw = bytearray(Path(one.out).read_bytes()); raw[-1] ^= 1
        Path(one.out).write_bytes(raw)
        with self.assertRaises(ValueError):
            pack.cmd_pack_full(self.arguments("two.etu", one.out))

    def test_bsdiff_exit_zero_and_a_file_do_not_replace_stdout_verification(self):
        def pretend(command, **kwargs):
            Path(command[3]).write_bytes(bytes(40))
            self.assertEqual(Path(kwargs["cwd"]), Path(command[3]).parent)
            return subprocess.CompletedProcess(command, 0, "failure with exit zero", "")
        with patch.object(pack.subprocess, "run", side_effect=pretend):
            with self.assertRaisesRegex(RuntimeError, "did not report"):
                pack.run_bsdiff(str(self.root / "fake.exe"), b"old", b"new")

    def test_bsdiff_error_line_overrides_success_marker(self):
        with patch.object(pack.subprocess, "run", return_value=subprocess.CompletedProcess([], 0,
            "Successfully created compressed patch: output\n", "Error: failed\n")):
            with self.assertRaisesRegex(RuntimeError, "did not report"):
                pack.run_bsdiff(str(self.root / "fake.exe"), b"old", b"new")


if __name__ == "__main__":
    unittest.main(verbosity=2)
