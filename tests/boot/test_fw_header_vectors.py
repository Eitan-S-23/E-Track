#!/usr/bin/env python3
"""Compile the MCU validator for the host and run P1-1 golden-vector cases."""

from __future__ import annotations

import os
import hashlib
from pathlib import Path
import re
import shutil
import struct
import subprocess
import tempfile
import zlib


ROOT = Path(__file__).resolve().parents[2]
LAYOUT_TEXT = (ROOT / "Libraries/OTA/ota_layout.h").read_text(encoding="ascii")


def parse_layout_macro(name: str) -> int:
    match = re.search(
        rf"(?m)^\s*#define\s+{re.escape(name)}\s+(0x[0-9A-Fa-f]+|[0-9]+)\b",
        LAYOUT_TEXT,
    )
    if not match:
        raise RuntimeError(f"missing OTA layout macro: {name}")
    return int(match.group(1), 0)


FW_HEADER_OFFSET = parse_layout_macro("OTA_FW_HEADER_OFFSET")
FW_HEADER_SIZE = parse_layout_macro("OTA_FW_HEADER_SIZE")
FW_HEADER_CRC_OFFSET = FW_HEADER_SIZE - 4
MAX_IMAGE_LEN = parse_layout_macro("OTA_APP_LENGTH")
APP_ORIGIN = parse_layout_macro("OTA_APP_ORIGIN")
RAM_ORIGIN = parse_layout_macro("OTA_RAM_ORIGIN")
RAM_END = (
    parse_layout_macro("OTA_OVERLAY_ORIGIN")
    + parse_layout_macro("OTA_OVERLAY_LENGTH")
)


def seal_header(image: bytearray, header: bytearray) -> bytes:
    header[40:72] = b"\x00" * 32
    header[FW_HEADER_CRC_OFFSET:FW_HEADER_CRC_OFFSET + 4] = b"\x00" * 4
    image[FW_HEADER_OFFSET:FW_HEADER_OFFSET + FW_HEADER_SIZE] = header
    header[40:72] = hashlib.sha256(image).digest()
    struct.pack_into(
        "<I", header, FW_HEADER_CRC_OFFSET,
        zlib.crc32(header[:FW_HEADER_CRC_OFFSET]) & 0xFFFFFFFF,
    )
    image[FW_HEADER_OFFSET:FW_HEADER_OFFSET + FW_HEADER_SIZE] = header
    return bytes(image)


def finalized(base: bytes, *, hw_rev: int = 1, layout_id: int = 1,
               min_boot_ver: int = 1) -> bytes:
    image = bytearray(base)
    if not (FW_HEADER_OFFSET + FW_HEADER_SIZE <= len(image) <= MAX_IMAGE_LEN):
        raise ValueError("test image length is outside the firmware contract")

    header = bytearray(b"\x00" * FW_HEADER_SIZE)
    header[0:4] = b"ETFW"
    struct.pack_into("<II", header, 4, 1, 20800)
    header[12:28] = b"2.8.0\x00".ljust(16, b"\x00")
    struct.pack_into("<III", header, 28, 1721000000, hw_rev, len(image))
    header[72] = layout_id
    header[73] = min_boot_ver
    header[74:92] = b"\xFF" * 18
    return seal_header(image, header)


def mutate_header(image: bytes, offset: int, data: bytes) -> bytes:
    updated = bytearray(image)
    header = bytearray(updated[FW_HEADER_OFFSET:FW_HEADER_OFFSET + FW_HEADER_SIZE])
    header[offset:offset + len(data)] = data
    return seal_header(updated, header)


def compile_validator(output: Path) -> None:
    sources = [
        ROOT / "tests/boot/fw_header_validator_host.c",
        ROOT / "boot/src/boot_fw_header.c",
        ROOT / "boot/src/boot_crc32.c",
        ROOT / "boot/src/boot_sha256.c",
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
    golden = bytearray((ROOT / "tests/ota-vectors/toy-new.bin").read_bytes())
    struct.pack_into(
        "<II", golden, 0,
        RAM_ORIGIN + 0x1000,
        APP_ORIGIN + FW_HEADER_OFFSET + FW_HEADER_SIZE + 1,
    )
    valid = finalized(bytes(golden))

    cases: list[tuple[str, bytes, str]] = [("valid", valid, "ok")]

    bad_magic = bytearray(valid)
    bad_magic[FW_HEADER_OFFSET] ^= 0x01
    cases.append(("bad-magic", bytes(bad_magic), "magic"))

    bad_header = bytearray(valid)
    bad_header[FW_HEADER_OFFSET + 8] ^= 0x01
    cases.append(("bad-header-crc", bytes(bad_header), "header_crc"))

    cases.append((
        "bad-header-version",
        mutate_header(valid, 4, struct.pack("<I", 2)),
        "header_version",
    ))
    cases.append((
        "bad-image-length",
        mutate_header(valid, 36, struct.pack("<I", FW_HEADER_OFFSET)),
        "image_length",
    ))

    bad_sha = bytearray(valid)
    bad_sha[FW_HEADER_OFFSET + FW_HEADER_SIZE + 0xA0] ^= 0x01
    cases.append(("bad-sha", bytes(bad_sha), "image_sha"))

    cases.append(("wrong-hardware", finalized(bytes(golden), hw_rev=2), "hardware_rev"))
    cases.append(("wrong-layout", finalized(bytes(golden), layout_id=2), "layout_id"))
    cases.append(("boot-too-old", finalized(bytes(golden), min_boot_ver=2), "min_boot_version"))

    bad_msp = bytearray(golden)
    struct.pack_into("<I", bad_msp, 0, RAM_ORIGIN - 4)
    cases.append(("bad-msp", finalized(bytes(bad_msp)), "vector_msp"))

    bad_reset = bytearray(golden)
    struct.pack_into("<I", bad_reset, 4, (APP_ORIGIN - 4) | 1)
    cases.append(("bad-reset", finalized(bytes(bad_reset)), "vector_reset"))

    top_msp = bytearray(golden)
    struct.pack_into("<I", top_msp, 0, RAM_END)
    cases.append(("top-of-ram-msp", finalized(bytes(top_msp)), "ok"))

    cases.append((
        "bad-version-name",
        mutate_header(valid, 12, b"X" * 16),
        "version_name",
    ))
    cases.append((
        "empty-version-name",
        mutate_header(valid, 12, b"\x00" * 16),
        "version_name",
    ))
    cases.append((
        "dirty-version-padding",
        mutate_header(valid, 12, b"2.8.0\x00X".ljust(16, b"\x00")),
        "version_name",
    ))
    cases.append((
        "bad-padding",
        mutate_header(valid, 74, b"\x00"),
        "padding",
    ))

    # Windows virus scanners can briefly retain the freshly linked executable.
    with tempfile.TemporaryDirectory(
        prefix="etrack-p1-1-", ignore_cleanup_errors=True
    ) as temp_dir:
        temp = Path(temp_dir)
        validator = temp / ("fw_header_validator.exe" if os.name == "nt" else "fw_header_validator")
        compile_validator(validator)

        for name, image, expected in cases:
            path = temp / f"{name}.bin"
            path.write_bytes(image)
            subprocess.run([str(validator), str(path), expected], cwd=ROOT, check=True)

    print(f"P1_1_FW_HEADER_VECTORS=PASS cases={len(cases)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
