#!/usr/bin/env python3
"""Compile and run the portable P2-2 full-package test suite."""

from __future__ import annotations

import os
from pathlib import Path
import shutil
import subprocess
import tempfile


ROOT = Path(__file__).resolve().parents[2]


def compile_test(output: Path) -> None:
    sources = [
        ROOT / "tests/ota/test_ota_package.c",
        ROOT / "Libraries/OTA/ota_package.c",
        ROOT / "Libraries/OTA/ota_keys.c",
        ROOT / "boot/src/boot_crc32.c",
        ROOT / "boot/src/boot_sha256.c",
        ROOT / "boot/src/boot_fw_header.c",
        ROOT / "bsdiff_lzma_AES128-main/bspatch/lzma/LzmaDec.c",
        ROOT / "bsdiff_lzma_AES128-main/bspatch/AES128_CTR/aes_core.c",
    ]
    includes = [
        ROOT / "Libraries",
        ROOT / "boot/include",
        ROOT / "bsdiff_lzma_AES128-main/bspatch/lzma",
        ROOT / "bsdiff_lzma_AES128-main/bspatch/AES128_CTR",
    ]
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
    with tempfile.TemporaryDirectory(
        prefix="etrack-p2-2-package-", ignore_cleanup_errors=True
    ) as temp_dir:
        executable = Path(temp_dir) / (
            "test_ota_package.exe" if os.name == "nt" else "test_ota_package"
        )
        compile_test(executable)
        subprocess.run([str(executable)], cwd=ROOT, check=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
