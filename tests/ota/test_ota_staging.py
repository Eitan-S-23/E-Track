#!/usr/bin/env python3
"""Run portable staging faults and the real HAL with a NOR/XIP model."""

from __future__ import annotations

import os
from pathlib import Path
import shutil
import subprocess
import tempfile


ROOT = Path(__file__).resolve().parents[2]


def compile_test(output: Path) -> None:
    sources = [
        ROOT / "tests/ota/test_ota_staging.c",
        ROOT / "Libraries/OTA/ota_staging.c",
    ]
    includes = [ROOT / "Libraries"]
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
            f'{quoted_includes} {quoted_sources} /Fe:"{output}" '
            f'/Fo:"{output.parent.as_posix()}/" /Fd:"{output.parent / "staging.pdb"}"'
        )
        subprocess.run(["cmd", "/d", "/s", "/c", command], cwd=ROOT,
                       check=True)
        return

    raise RuntimeError("No host C compiler found")


def compile_hal_test(output: Path, *, qe_reuse: bool = False,
                     block_erase: bool = False) -> None:
    sources = [
        ROOT / "tests/ota" / ("test_p34_staging_erase.cpp" if block_erase
                              else "test_ota_staging_hal.cpp"),
        ROOT / "USER/HAL/HAL_OTA_Staging.cpp",
        ROOT / "Libraries/OTA/ota_staging.c",
    ]
    includes = [ROOT / "tests/ota/staging_hal_stubs", ROOT / "USER", ROOT / "Libraries"]
    cxx = shutil.which("c++") or shutil.which("g++") or shutil.which("clang++")
    if cxx:
        subprocess.run([
            cxx, "-x", "c++", "-std=c++11", "-Wall", "-Wextra", "-Werror", "-O2",
            *(["-DCONFIG_OTA_STAGING_QE_REUSE=1"] if qe_reuse else []),
            *(["-DCONFIG_OTA_STAGING_BLOCK_ERASE=1"] if block_erase else []),
            *[f"-I{path}" for path in includes], *[str(path) for path in sources],
            "-o", str(output),
        ], cwd=ROOT, check=True)
        return
    vcvars = Path(r"D:\vs2019\VC\Auxiliary\Build\vcvars64.bat")
    if os.name == "nt" and vcvars.exists():
        quoted_sources = " ".join(f'"{path}"' for path in sources)
        quoted_includes = " ".join(f'/I"{path}"' for path in includes)
        defines = "/DCONFIG_OTA_STAGING_QE_REUSE=1 " if qe_reuse else ""
        if block_erase:
            defines += "/DCONFIG_OTA_STAGING_BLOCK_ERASE=1 "
        command = (
            f'call "{vcvars}" >nul && '
            f'cl /nologo /TP /std:c++14 /O2 /W4 /WX /D_CRT_SECURE_NO_WARNINGS '
            f'{defines}{quoted_includes} {quoted_sources} /Fe:"{output}" '
            f'/Fo:"{output.parent.as_posix()}/" /Fd:"{output.parent / "staging-hal.pdb"}"'
        )
        subprocess.run(["cmd", "/d", "/s", "/c", command], cwd=ROOT, check=True)
        return
    raise RuntimeError("No host C++ compiler found for real HAL staging test")


def main() -> int:
    with tempfile.TemporaryDirectory(
        prefix="etrack-p2-1-staging-", ignore_cleanup_errors=True
    ) as temp_dir:
        executable = Path(temp_dir) / (
            "test_ota_staging.exe" if os.name == "nt" else "test_ota_staging"
        )
        compile_test(executable)
        subprocess.run([str(executable)], cwd=ROOT, check=True)
        hal_executable = Path(temp_dir) / (
            "test_ota_staging_hal.exe" if os.name == "nt" else "test_ota_staging_hal"
        )
        compile_hal_test(hal_executable)
        subprocess.run([str(hal_executable)], cwd=ROOT, check=True)
        reuse_executable = hal_executable.with_name("test_ota_staging_hal_reuse" + hal_executable.suffix)
        compile_hal_test(reuse_executable, qe_reuse=True)
        subprocess.run([str(reuse_executable)], cwd=ROOT, check=True)
        for qe_reuse in (False, True):
            bulk_executable = hal_executable.with_name(
                "test_ota_staging_erase_" + str(int(qe_reuse)) + hal_executable.suffix)
            compile_hal_test(bulk_executable, qe_reuse=qe_reuse, block_erase=True)
            subprocess.run([str(bulk_executable)], cwd=ROOT, check=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
