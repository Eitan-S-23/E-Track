#!/usr/bin/env python3
"""Compile and run the portable P2-3 patch-package test suite."""

from __future__ import annotations

import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile


ROOT = Path(__file__).resolve().parents[2]


def _load_unpack_module():
    sys.path.insert(0, str(ROOT / "tools"))
    import etu_unpack  # type: ignore

    return etu_unpack


def _decode_patch(package: bytes):
    unpack = _load_unpack_module()
    outer = unpack.parse_etu_header(package)
    key = bytes.fromhex(unpack.DEFAULT_KEY_HEX)
    plaintext = unpack.aesctr(
        key, outer["nonce"], outer["payload"], encrypt=False
    )
    inner = unpack.parse_patch_header(plaintext[: unpack.PATCH_HEADER_SIZE])
    stream = plaintext[unpack.PATCH_HEADER_SIZE :]
    if inner["ph_psize"] != len(stream):
        raise AssertionError("static P2-3 vector ph_psize mismatch")
    decoded = unpack.lzma_decompress_stream(
        inner["props"], inner["ph_orig"], stream
    )
    return unpack, outer, inner, decoded


def _parse_controls(unpack, decoded: bytes, new_size: int):
    controls = []
    offset = 0
    newpos = 0
    while newpos < new_size:
        if offset + 24 > len(decoded):
            raise AssertionError("static P2-3 vector control stream truncated")
        ctrl = tuple(
            unpack.offtin(decoded[offset + i * 8 : offset + (i + 1) * 8])
            for i in range(3)
        )
        offset += 24
        if ctrl[0] < 0 or ctrl[1] < 0:
            raise AssertionError(f"static P2-3 vector has invalid control {ctrl}")
        offset += ctrl[0] + ctrl[1]
        newpos += ctrl[0] + ctrl[1]
        controls.append(ctrl)
        if len(controls) > new_size:
            raise AssertionError("static P2-3 vector control count exceeds bound")
    if newpos != new_size or offset != len(decoded):
        raise AssertionError("static P2-3 vector decoded length mismatch")
    return controls


def verify_regression_vectors() -> None:
    vectors = ROOT / "tests/ota-vectors"
    old = (vectors / "toy-old.bin").read_bytes()
    expected = (vectors / "p2-3-vendor-oldpos-new.bin").read_bytes()
    package = (vectors / "p2-3-vendor-oldpos.etu").read_bytes()
    unpack, outer, inner, decoded = _decode_patch(package)
    controls = _parse_controls(unpack, decoded, inner["ph_nsize"])
    expected_controls = [
        (1500, 333, 2560),
        *[(0, 0, -256)] * 9,
        (2263, 0, -179),
    ]
    if controls != expected_controls:
        raise AssertionError(f"vendor control regression changed: {controls}")
    candidate = unpack.bspatch_apply(old, inner["ph_nsize"], decoded)
    if candidate != expected:
        raise AssertionError("vendor control regression candidate mismatch")
    unpack.verify_fw_header(candidate, "p2-3-vendor-oldpos")
    if outer["target_vcode"] != 20802:
        raise AssertionError("vendor control regression target version changed")

    invalid = (vectors / "p2-3-invalid-control.etu").read_bytes()
    unpack, _, inner, decoded = _decode_patch(invalid)
    first = tuple(unpack.offtin(decoded[i * 8 : (i + 1) * 8])
                  for i in range(3))
    if first != (0, 0, 0) or len(decoded) != inner["ph_orig"]:
        raise AssertionError("invalid PATCH_CONTROL regression changed")

    print(
        "P2_3_VECTOR_PREFLIGHT=PASS "
        "vendor_controls=11 oldpos_only=9 invalid_control=[0,0,0]",
        flush=True,
    )


def compile_test(output: Path) -> None:
    sources = [
        ROOT / "tests/ota/test_ota_patch.c",
        ROOT / "Libraries/OTA/ota_patch.c",
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
    verify_regression_vectors()
    with tempfile.TemporaryDirectory(
        prefix="etrack-p2-3-patch-", ignore_cleanup_errors=True
    ) as temp_dir:
        executable = Path(temp_dir) / (
            "test_ota_patch.exe" if os.name == "nt" else "test_ota_patch"
        )
        compile_test(executable)
        subprocess.run([str(executable)], cwd=ROOT, check=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
