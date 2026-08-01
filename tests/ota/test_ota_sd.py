#!/usr/bin/env python3
"""Compile and run the portable P2-4 SD import test suite."""

from __future__ import annotations

import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile


ROOT = Path(__file__).resolve().parents[2]


def compile_test(output: Path) -> None:
    sources = [
        ROOT / "tests/ota/test_ota_sd.c",
        ROOT / "Libraries/OTA/ota_sd.c",
        ROOT / "Libraries/OTA/ota_staging.c",
        ROOT / "boot/src/boot_crc32.c",
        ROOT / "boot/src/boot_sha256.c",
    ]
    includes = [ROOT / "Libraries", ROOT / "boot/include"]
    cc = shutil.which("cc") or shutil.which("gcc") or shutil.which("clang")

    if cc:
        command = [
            cc,
            "-std=c99",
            "-Wall",
            "-Wextra",
            "-Werror",
            "-O2",
            *[f"-I{path}" for path in includes],
            *[str(path) for path in sources],
            "-o",
            str(output),
        ]
        subprocess.run(command, cwd=ROOT, check=True)
        return

    vcvars = Path(r"D:\vs2019\VC\Auxiliary\Build\vcvars64.bat")
    if os.name == "nt" and vcvars.exists():
        quoted_sources = " ".join(f'"{path}"' for path in sources)
        quoted_includes = " ".join(f'/I"{path}"' for path in includes)
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
        prefix="etrack-p2-4-ota-sd-",
        dir=cache_dir,
        ignore_cleanup_errors=True,
    ) as temp_dir:
        executable = Path(temp_dir) / (
            "test_ota_sd.exe" if os.name == "nt" else "test_ota_sd"
        )
        compile_test(executable)
        subprocess.run([str(executable)], cwd=ROOT, check=True)
    subprocess.run(
        [sys.executable, str(ROOT / "tests/ota/test_ota_update.py")],
        cwd=ROOT,
        check=True,
    )
    print("P2_4_OTA_SD_ALL=PASS core_checks=29 adapter_scenarios=5")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
