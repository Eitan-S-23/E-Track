#!/usr/bin/env python3
"""Host checks for the P1-5 asset and bootstrap command utility."""

from __future__ import annotations

import hashlib
import os
import re
import struct
import subprocess
import sys
import zlib
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
TOOL = ROOT / "Tools" / "jlink" / "prepare-bootstrap-app.py"
JLINK_COMMON = ROOT / "Tools" / "jlink" / "jlink-common.ps1"
LAYOUT_TEXT = (ROOT / "Libraries/OTA/ota_layout.h").read_text(encoding="ascii")


def parse_layout_macro(name: str) -> int:
    match = re.search(
        rf"(?m)^\s*#define\s+{re.escape(name)}\s+(0x[0-9A-Fa-f]+|[0-9]+)\s*$",
        LAYOUT_TEXT,
    )
    if match is None:
        raise AssertionError(f"layout macro is absent or non-literal: {name}")
    return int(match.group(1), 0)


FW_OFFSET = parse_layout_macro("OTA_FW_HEADER_OFFSET")
FW_SIZE = parse_layout_macro("OTA_FW_HEADER_SIZE")
APP_ORIGIN = parse_layout_macro("OTA_APP_ORIGIN")
RAM_END = parse_layout_macro("OTA_OVERLAY_ORIGIN") + parse_layout_macro(
    "OTA_OVERLAY_LENGTH"
)
IMAGE_LENGTH = FW_OFFSET + 0x200


def run(*args: str, expect: int = 0) -> subprocess.CompletedProcess[str]:
    result = subprocess.run(
        [sys.executable, str(TOOL), *args],
        cwd=ROOT,
        text=True,
        capture_output=True,
    )
    if result.returncode != expect:
        raise AssertionError(
            f"unexpected exit {result.returncode} (expected {expect})\n"
            f"stdout={result.stdout}\nstderr={result.stderr}"
        )
    return result


def make_image() -> bytes:
    image = bytearray((index * 17 + 3) & 0xFF for index in range(IMAGE_LENGTH))
    struct.pack_into("<I", image, 0, RAM_END)
    struct.pack_into("<I", image, 4, APP_ORIGIN + 0x101)
    header = bytearray(FW_SIZE)
    header[0:4] = b"ETFW"
    struct.pack_into("<II", header, 4, 1, 20800)
    header[12:28] = b"2.8.0\x00" + bytes(10)
    struct.pack_into("<III", header, 28, 1720000000, 1, IMAGE_LENGTH)
    header[72:74] = bytes((1, 1))
    header[74:92] = bytes([0xFF]) * 18
    image[FW_OFFSET : FW_OFFSET + FW_SIZE] = header
    digest_image = bytearray(image)
    digest_image[FW_OFFSET + 40 : FW_OFFSET + 72] = bytes(32)
    digest_image[FW_OFFSET + 92 : FW_OFFSET + 96] = bytes(4)
    image[FW_OFFSET + 40 : FW_OFFSET + 72] = hashlib.sha256(digest_image).digest()
    struct.pack_into(
        "<I", image, FW_OFFSET + 92, zlib.crc32(image[FW_OFFSET : FW_OFFSET + 92])
    )
    return bytes(image)


def main() -> int:
    checks = 0
    common_text = JLINK_COMMON.read_text(encoding="ascii")
    assert (
        "if ($Operation -like 'install-*' -or $Operation -eq 'stage-slots')"
        in common_text
    )
    checks += 1

    cache = ROOT / ".cache"
    cache.mkdir(exist_ok=True)
    work = cache / f"p1-5-tool-{os.getpid()}"
    app = work.with_name(work.name + "-app.bin")
    prepared = work.with_name(work.name + "-prepared.bin")
    recovery = work.with_name(work.name + "-recovery.bin")
    app.write_bytes(make_image())

    result = run(
        "prepare",
        "--input",
        str(app),
        "--input-kind",
        "app",
        "--output",
        str(prepared),
        "--recovery-output",
        str(recovery),
    )
    assert "P1_5_APP_PREPARE=PASS" in result.stdout
    assert prepared.read_bytes() == app.read_bytes()
    assert len(recovery.read_bytes()) == IMAGE_LENGTH + 8
    checks += 3

    result = run("verify", "--input", str(recovery), "--input-kind", "recovery")
    assert "P1_5_APP_VERIFY=PASS" in result.stdout
    checks += 1

    command = work.with_name(work.name + "-command.bin")
    result = run(
        "command",
        "--operation",
        "install-recovery",
        "--output",
        str(command),
    )
    raw_command = command.read_bytes()
    assert len(raw_command) == 128
    assert struct.unpack_from("<I", raw_command, 0)[0] == 0x424A5445
    assert struct.unpack_from("<I", raw_command, 32)[0] == (
        zlib.crc32(raw_command[:32]) & 0xFFFFFFFF
    )
    assert "P1_5_BOOTSTRAP_COMMAND=PASS" in result.stdout
    checks += 4

    bad_recovery = work.with_name(work.name + "-bad-recovery.bin")
    bad_recovery.write_bytes(recovery.read_bytes()[:-1] + b"\x00")
    run("verify", "--input", str(bad_recovery), "--input-kind", "recovery", expect=1)
    checks += 1

    done = bytearray(128)
    struct.pack_into("<I", done, 0, 0x444A5445)
    struct.pack_into("<II", done, 36, 2, 0)
    struct.pack_into("<I", done, 96, zlib.crc32(done[36:96]) & 0xFFFFFFFF)
    result_file = work.with_name(work.name + "-result.bin")
    result_file.write_bytes(done)
    result = run("result", "--input", str(result_file))
    assert "P1_5_BOOTSTRAP_RESULT=PASS" in result.stdout
    checks += 1

    failed_snapshot = bytearray(done)
    struct.pack_into("<I", failed_snapshot, 8, 4)
    struct.pack_into("<I", failed_snapshot, 52, 0xFFFFFFFF)
    struct.pack_into(
        "<I",
        failed_snapshot,
        96,
        zlib.crc32(failed_snapshot[36:96]) & 0xFFFFFFFF,
    )
    failed_snapshot_file = work.with_name(work.name + "-failed-snapshot.bin")
    failed_snapshot_file.write_bytes(failed_snapshot)
    result = run("result", "--input", str(failed_snapshot_file), expect=1)
    assert "BCB arbitration I/O failed" in result.stderr
    checks += 1

    print(f"P1_5_PREPARE_TOOL=PASS checks={checks}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
