#!/usr/bin/env python3
"""Compile and run the P3-2 device identity host unit tests.

Links the real identity helper against the real fw_header validation, boot
crypto, and EEPROM BCB arbiter sources with an injected in-memory image
reader and EEPROM fixture (same pattern as test_ota_backup.py). Golden
vectors are read from tests/ota-vectors/*.bin with expected values frozen
from tests/ota-vectors/expected.json.
"""

from __future__ import annotations

import os
from pathlib import Path
import shutil
import subprocess
import tempfile


ROOT = Path(__file__).resolve().parents[2]

SOURCES = [
    ROOT / "tests/ota/test_ota_device_info.c",
    ROOT / "Libraries/OTA/ota_device_info.c",
    ROOT / "boot/src/boot_fw_header.c",
    ROOT / "boot/src/boot_crc32.c",
    ROOT / "boot/src/boot_sha256.c",
    ROOT / "Libraries/EEPROM/eeprom_bcb.c",
]

INCLUDES = [ROOT / "Libraries", ROOT / "boot/include"]


def compile_test(output: Path) -> None:
    cc = shutil.which("cc") or shutil.which("gcc") or shutil.which("clang")

    if cc:
        command = [
            cc,
            "-std=c99",
            "-Wall",
            "-Wextra",
            "-Werror",
            "-O2",
            *[f"-I{path}" for path in INCLUDES],
            *[str(path) for path in SOURCES],
            "-o",
            str(output),
        ]
        subprocess.run(command, cwd=ROOT, check=True)
        return

    vcvars = Path(r"D:\vs2019\VC\Auxiliary\Build\vcvars64.bat")
    if os.name == "nt" and vcvars.exists():
        quoted_sources = " ".join(f'"{path}"' for path in SOURCES)
        quoted_includes = " ".join(f'/I"{path}"' for path in INCLUDES)
        command = (
            f'call "{vcvars}" >nul && '
            f'cl /nologo /std:c11 /O2 /W4 /WX /D_CRT_SECURE_NO_WARNINGS '
            f'{quoted_includes} {quoted_sources} /Fe:"{output}"'
        )
        subprocess.run(["cmd", "/d", "/s", "/c", command], cwd=ROOT,
                       check=True)
        return

    raise RuntimeError("No host C compiler found")


def main() -> int:
    cache_dir = ROOT / ".cache"
    cache_dir.mkdir(exist_ok=True)
    with tempfile.TemporaryDirectory(
        prefix="etrack-p3-2-device-info-",
        dir=cache_dir,
        ignore_cleanup_errors=True,
    ) as temp_dir:
        executable = Path(temp_dir) / (
            "test_ota_device_info.exe" if os.name == "nt"
            else "test_ota_device_info"
        )
        compile_test(executable)
        subprocess.run([str(executable)], cwd=ROOT, check=True)
    print("P3_2_OTA_DEVICE_INFO_ALL=PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
