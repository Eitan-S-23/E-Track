#!/usr/bin/env python3
"""Compile and run the P1-5 J-Link bootstrap persistent-memory model."""

from __future__ import annotations

import os
from pathlib import Path
import shutil
import subprocess


ROOT = Path(__file__).resolve().parents[2]


def compile_test(output: Path) -> None:
    sources = [
        ROOT / "tests/boot/test_bootstrap.c",
        ROOT / "boot/src/boot_bootstrap.c",
        ROOT / "boot/src/boot_fw_header.c",
        ROOT / "boot/src/boot_slot.c",
        ROOT / "boot/src/boot_crc32.c",
        ROOT / "boot/src/boot_sha256.c",
        ROOT / "Libraries/EEPROM/eeprom_bcb.c",
    ]
    includes = [ROOT / "boot/include", ROOT / "Libraries"]

    cc = shutil.which("cc") or shutil.which("gcc") or shutil.which("clang")
    if cc:
        command = [
            cc, "-std=c99", "-Wall", "-Wextra", "-Werror", "-O2",
            *[f"-I{path}" for path in includes],
            *[str(path) for path in sources], "-o", str(output),
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
        subprocess.run(["cmd", "/d", "/s", "/c", command], cwd=ROOT, check=True)
        return

    raise RuntimeError("No host C compiler found")


def main() -> int:
    build_dir = ROOT / ".cache" / "p1-5-bootstrap-test"
    build_dir.mkdir(parents=True, exist_ok=True)
    executable = build_dir / (
        "test_bootstrap.exe" if os.name == "nt" else "test_bootstrap"
    )
    compile_test(executable)
    subprocess.run([str(executable)], cwd=ROOT, check=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
