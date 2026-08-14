#!/usr/bin/env python3
import hashlib
import os
import subprocess
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
GUARD = ROOT / "Tools" / "provenance" / "worktree_guard.ps1"
MANIFEST = ROOT / "Tools" / "provenance" / "source_manifest.ps1"
REPRO = ROOT / "cmake" / "reproducible_build.cmake"


class P25BuildProvenanceTests(unittest.TestCase):
    def test_release_requires_source_date_epoch(self):
        text = REPRO.read_text(encoding="ascii")
        self.assertIn('CMAKE_BUILD_TYPE STREQUAL "Release"', text)
        self.assertIn("Release firmware builds require SOURCE_DATE_EPOCH", text)
        self.assertIn('MATCHES "^[0-9]+$"', text)

    def test_manifest_protocol_is_explicit(self):
        text = MANIFEST.read_text(encoding="ascii")
        self.assertIn("[System.StringComparer]::Ordinal", text)
        self.assertIn("UTF-8 without BOM, CRLF, one trailing newline", text)
        self.assertIn("MDK-ARM_F435/cmake-generated/cmake/", text)
        self.assertNotIn("MDK-ARM_F435/RTE/Device", text)

    def test_worktree_guard_rejects_sibling_output(self):
        sibling = ROOT.parent / (ROOT.name + "-outside-test") / "evidence.txt"
        command = (
            f". '{GUARD}'; "
            f"Assert-WorktreeFileOutput -RepoRoot '{ROOT}' -FilePath '{sibling}'"
        )
        result = subprocess.run(
            [
                "powershell.exe",
                "-NoProfile",
                "-ExecutionPolicy",
                "Bypass",
                "-Command",
                command,
            ],
            cwd=ROOT,
            capture_output=True,
            text=True,
        )
        self.assertNotEqual(result.returncode, 0)
        self.assertFalse(sibling.exists())

    def test_gcc_date_time_follow_source_date_epoch(self):
        compiler = os.environ.get(
            "ARM_GCC",
            r"D:\singlechip\gcc+gdb+openocd\tools\arm-gnu-toolchain-13.3.rel1-ming\bin\arm-none-eabi-gcc.exe",
        )
        if not Path(compiler).is_file():
            self.skipTest("GNU Arm compiler is unavailable")

        source = 'const char d[] = __DATE__; const char t[] = __TIME__;\n'
        with tempfile.TemporaryDirectory(dir=ROOT / ".cache") as temp_dir:
            temp = Path(temp_dir)
            src = temp / "stamp.c"
            obj1 = temp / "stamp1.o"
            obj2 = temp / "stamp2.o"
            src.write_text(source, encoding="ascii", newline="\n")
            env = os.environ.copy()
            env["SOURCE_DATE_EPOCH"] = "0"
            subprocess.run([compiler, "-c", str(src), "-o", str(obj1)], check=True, env=env)
            subprocess.run([compiler, "-c", str(src), "-o", str(obj2)], check=True, env=env)
            self.assertEqual(hashlib.sha256(obj1.read_bytes()).digest(), hashlib.sha256(obj2.read_bytes()).digest())
            data = obj1.read_bytes()
            self.assertIn(b"Jan  1 1970", data)
            self.assertIn(b"00:00:00", data)


if __name__ == "__main__":
    unittest.main()
