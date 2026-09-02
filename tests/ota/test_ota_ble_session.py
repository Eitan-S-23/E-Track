#!/usr/bin/env python3
"""Compile and run the P3-1 BLE session host unit tests.

Links the real session/frame/ring transport against the real staging, SD
header inspection, and boot crypto sources with an injected in-memory NOR
flash fixture (same pattern as test_ota_sd.py).
"""

from __future__ import annotations

import os
from pathlib import Path
import shutil
import subprocess
import tempfile


ROOT = Path(__file__).resolve().parents[2]


def compile_test(output: Path) -> None:
    sources = [
        ROOT / "tests/ota/test_ota_ble_session.c",
        ROOT / "Libraries/OTA/ota_ble_session.c",
        ROOT / "Libraries/OTA/ota_ble_frame.c",
        ROOT / "Libraries/OTA/ota_ble_ring.c",
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
    with tempfile.TemporaryDirectory(
        prefix="etrack-p3-1-ble-session-", ignore_cleanup_errors=True
    ) as temp_dir:
        executable = Path(temp_dir) / (
            "test_ota_ble_session.exe" if os.name == "nt"
            else "test_ota_ble_session"
        )
        compile_test(executable)
        subprocess.run([str(executable)], cwd=ROOT, check=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
