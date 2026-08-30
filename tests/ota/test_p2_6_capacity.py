#!/usr/bin/env python3
"""Run the P2-6 FULL/PATCH host capacity-boundary regression."""

from __future__ import annotations

import os
from pathlib import Path
import shutil
import subprocess


ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / ".cache" / "p2-6-host-regression"
TMP = ROOT / ".cache" / "p2-6-test-tmp"


def env() -> dict[str, str]:
    result = os.environ.copy()
    for key in ("TEMP", "TMP", "TMPDIR"):
        result[key] = str(TMP)
    result["PIP_CACHE_DIR"] = str(ROOT / ".cache" / "p2-6-tool-cache")
    result["CCACHE_DIR"] = str(ROOT / ".cache" / "p2-6-tool-cache" / "ccache")
    result["PYTHONPYCACHEPREFIX"] = str(ROOT / ".cache" / "p2-6-pycache")
    return result


def compiler() -> str:
    value = shutil.which("cc") or shutil.which("gcc") or shutil.which("clang")
    if not value:
        raise RuntimeError("No host C compiler found")
    return value


def compile_one(name: str, harness: str, ota_source: str) -> Path:
    cc = compiler()
    output = OUT / (name + (".exe" if os.name == "nt" else ""))
    includes = [
        ROOT / "Libraries",
        ROOT / "boot/include",
        ROOT / "bsdiff_lzma_AES128-main/bspatch/lzma",
        ROOT / "bsdiff_lzma_AES128-main/bspatch/AES128_CTR",
    ]
    sources = [
        ROOT / "tests/ota" / harness,
        ROOT / ota_source,
        ROOT / "Libraries/OTA/ota_keys.c",
        ROOT / "boot/src/boot_crc32.c",
        ROOT / "boot/src/boot_sha256.c",
        ROOT / "boot/src/boot_fw_header.c",
        ROOT / "bsdiff_lzma_AES128-main/bspatch/lzma/LzmaDec.c",
        ROOT / "bsdiff_lzma_AES128-main/bspatch/AES128_CTR/aes_core.c",
    ]
    command = [
        cc,
        "-std=c99",
        "-Wall",
        "-Wextra",
        "-Werror",
        "-O2",
        "-DOTA_P2_6_HOST_ARENA_CAPACITY_OVERRIDE=1",
        *(f"-I{path}" for path in includes),
        *(str(path) for path in sources),
        "-o",
        str(output),
    ]
    completed = subprocess.run(command, cwd=ROOT, env=env(),
                               capture_output=True, text=True)
    log = OUT / (name + ".compile.log")
    log.write_text(completed.stdout + completed.stderr, encoding="utf-8")
    if completed.returncode != 0:
        raise RuntimeError(f"{name} compile failed; see {log}")
    return output


def run_one(name: str, executable: Path) -> None:
    completed = subprocess.run([str(executable)], cwd=ROOT, env=env(),
                               capture_output=True, text=True)
    log = OUT / (name + ".run.log")
    log.write_text(completed.stdout + completed.stderr, encoding="utf-8")
    print(completed.stdout, end="")
    if completed.returncode != 0:
        raise RuntimeError(f"{name} run failed; see {log}")


def main() -> int:
    OUT.mkdir(parents=True, exist_ok=True)
    TMP.mkdir(parents=True, exist_ok=True)
    package = compile_one("p2-6-capacity-full",
                          "test_p2_6_capacity_package.c",
                          "Libraries/OTA/ota_package.c")
    patch = compile_one("p2-6-capacity-patch",
                        "test_p2_6_capacity_patch.c",
                        "Libraries/OTA/ota_patch.c")
    run_one("p2-6-capacity-full", package)
    run_one("p2-6-capacity-patch", patch)
    print("P2_6_CAPACITY=PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
