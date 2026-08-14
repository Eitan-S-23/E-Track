#!/usr/bin/env python3
"""P2-5 backup/STAGED 与 App 自检健康门宿主测试入口。"""

from __future__ import annotations

import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[2]

BACKUP_SOURCES = [
    ROOT / "tests/ota/test_ota_backup.c",
    ROOT / "Libraries/OTA/ota_backup.c",
    ROOT / "Libraries/OTA/ota_slot_header.c",
    ROOT / "Libraries/EEPROM/eeprom_bcb.c",
    ROOT / "boot/src/boot_crc32.c",
    ROOT / "boot/src/boot_sha256.c",
    ROOT / "boot/src/boot_fw_header.c",
]

HEALTH_SOURCES = [
    ROOT / "tests/ota/test_ota_confirm_health.c",
    ROOT / "Libraries/OTA/ota_confirm_health.c",
]

INCLUDES = [ROOT / "Libraries", ROOT / "boot/include"]


def compile_sources(sources: list[Path], output: Path) -> None:
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
            *[str(path) for path in sources],
            "-o",
            str(output),
        ]
        subprocess.run(command, cwd=ROOT, check=True)
        return

    vcvars = Path(r"D:\vs2019\VC\Auxiliary\Build\vcvars64.bat")
    if os.name == "nt" and vcvars.exists():
        quoted_sources = " ".join(f'"{path}"' for path in sources)
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
        prefix="etrack-p2-5-ota-backup-",
        dir=cache_dir,
        ignore_cleanup_errors=True,
    ) as temp_dir:
        backup_exe = Path(temp_dir) / (
            "test_ota_backup.exe" if os.name == "nt" else "test_ota_backup"
        )
        health_exe = Path(temp_dir) / (
            "test_ota_confirm_health.exe"
            if os.name == "nt" else "test_ota_confirm_health"
        )
        compile_sources(BACKUP_SOURCES, backup_exe)
        compile_sources(HEALTH_SOURCES, health_exe)
        subprocess.run([str(backup_exe)], cwd=ROOT, check=True)
        subprocess.run([str(health_exe)], cwd=ROOT, check=True)
    print("P2_5_OTA_BACKUP_ALL=PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())