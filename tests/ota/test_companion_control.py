"""Behavioral tests of the production MCU companion control header."""

import hashlib
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[2]
CASES = ("crc", "phone_missing", "check_timeout", "acknowledged_timeout",
         "download_timeout", "timer_wrap", "offer_choice_once", "later_never_installs",
         "duplicate_expiry", "display_binding", "binary_exclusion", "malformed",
         "parser_recovery", "periodic_after_manual", "stale_session_and_request", "send_failure")


class CompanionControlTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cache = ROOT / ".cache/companion-control-tests"
        for entry in (cache, *cache.parents):
            if entry.exists() and (entry.is_symlink() or getattr(entry.lstat(), "st_file_attributes", 0) & 0x400):
                raise RuntimeError("Redirected test output")
        cache.mkdir(parents=True, exist_ok=True)
        compiler = shutil.which("g++")
        if compiler is None:
            raise RuntimeError("Host g++ required")
        cls.directory = tempfile.TemporaryDirectory(dir=cache)
        cls.addClassCleanup(cls.directory.cleanup)
        cls.env = dict(os.environ, TEMP=cls.directory.name, TMP=cls.directory.name, TMPDIR=cls.directory.name)
        cls.executable = str(Path(cls.directory.name) / "companion-control.exe")
        command = [compiler, "-std=c++11", "-Wall", "-Wextra", "-Werror", "-static-libgcc", "-static-libstdc++",
                   "-I", str(ROOT / "Libraries"), "-I", str(ROOT / "USER/App"),
                   str(ROOT / "tests/ota/companion_control_test.cpp"), "-o", cls.executable]
        build = subprocess.run(command, cwd=ROOT, env=cls.env, capture_output=True, text=True, timeout=60)
        if build.returncode:
            raise RuntimeError(build.stdout + build.stderr)
        print("Control source SHA-256: " + hashlib.sha256((ROOT / "Libraries/Bluetooth/CompanionControl.h").read_bytes()).hexdigest())


def test_case(name):
    def run(self):
        result = subprocess.run([self.executable, name], cwd=ROOT, env=self.env,
                                capture_output=True, text=True, timeout=10)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        print(result.stdout.strip())
    return run


for case in CASES:
    setattr(CompanionControlTests, "test_" + case, test_case(case))

if __name__ == "__main__":
    unittest.main(verbosity=2)
