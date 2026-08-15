#!/usr/bin/env python3
import hashlib
import os
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
WINDOWS_ARM_GCC = Path(
    r"D:\singlechip\gcc+gdb+openocd\tools\arm-gnu-toolchain-13.3.rel1-ming\bin\arm-none-eabi-gcc.exe"
)


def find_arm_gcc():
    configured = os.environ.get("ARM_GCC")
    if configured:
        resolved = shutil.which(configured) or configured
        if Path(resolved).is_file():
            return str(Path(resolved))

    discovered = shutil.which("arm-none-eabi-gcc")
    if discovered:
        return discovered
    if WINDOWS_ARM_GCC.is_file():
        return str(WINDOWS_ARM_GCC)
    return None


def repo_local_temp_env(directory):
    env = os.environ.copy()
    for name in ("TEMP", "TMP", "TMPDIR"):
        env[name] = str(directory)
    return env


class GccReproducibilityTests(unittest.TestCase):
    def test_date_time_follow_source_date_epoch(self):
        compiler = find_arm_gcc()
        if compiler is None:
            self.fail(
                "GNU Arm compiler is required; set ARM_GCC or add arm-none-eabi-gcc to PATH"
            )

        source = 'const char d[] = __DATE__; const char t[] = __TIME__;\n'
        with tempfile.TemporaryDirectory(dir=ROOT, prefix=".gcc-stamp-test-") as temp_dir:
            temp = Path(temp_dir)
            src = temp / "stamp.c"
            obj1 = temp / "stamp1.o"
            obj2 = temp / "stamp2.o"
            src.write_text(source, encoding="ascii", newline="\n")
            env = repo_local_temp_env(temp)
            env["SOURCE_DATE_EPOCH"] = "0"
            subprocess.run([compiler, "-c", str(src), "-o", str(obj1)], check=True, env=env)
            subprocess.run([compiler, "-c", str(src), "-o", str(obj2)], check=True, env=env)
            self.assertEqual(
                hashlib.sha256(obj1.read_bytes()).digest(),
                hashlib.sha256(obj2.read_bytes()).digest(),
            )
            data = obj1.read_bytes()
            self.assertIn(b"Jan  1 1970", data)
            self.assertIn(b"00:00:00", data)


if __name__ == "__main__":
    unittest.main()
