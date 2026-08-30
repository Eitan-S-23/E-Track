#!/usr/bin/env python3
"""Prepare and verify P1-5 App and recovery assets."""

from __future__ import annotations

import argparse
import hashlib
import os
import re
import struct
import sys
import zlib
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
LAYOUT_TEXT = (ROOT / "Libraries/OTA/ota_layout.h").read_text(encoding="ascii")


def parse_layout_macro(name: str) -> int:
    match = re.search(
        rf"(?m)^\s*#define\s+{re.escape(name)}\s+(0x[0-9A-Fa-f]+|[0-9]+)\s*$",
        LAYOUT_TEXT,
    )
    if match is None:
        raise RuntimeError(f"layout macro is absent or non-literal: {name}")
    return int(match.group(1), 0)


def parse_expected_bytes(value: str) -> bytes:
    try:
        return bytes.fromhex(value)
    except ValueError as exc:
        raise argparse.ArgumentTypeError(
            "expected bytes must be hexadecimal"
        ) from exc


FW_HEADER_OFFSET = parse_layout_macro("OTA_FW_HEADER_OFFSET")
FW_HEADER_SIZE = parse_layout_macro("OTA_FW_HEADER_SIZE")
FW_SHA_OFFSET = 40
FW_SHA_SIZE = 32
FW_CRC_OFFSET = 92
APP_ORIGIN = parse_layout_macro("OTA_APP_ORIGIN")
APP_LENGTH = parse_layout_macro("OTA_APP_LENGTH")
RAM_ORIGIN = parse_layout_macro("OTA_RAM_ORIGIN")
RAM_END = parse_layout_macro("OTA_OVERLAY_ORIGIN") + parse_layout_macro(
    "OTA_OVERLAY_LENGTH"
)

class ValidationError(ValueError):
    pass


def crc32(data: bytes) -> int:
    return zlib.crc32(data) & 0xFFFFFFFF


def u32(data: bytes, offset: int) -> int:
    return struct.unpack_from("<I", data, offset)[0]


def validate_app(image: bytes) -> dict[str, int | str]:
    if not (FW_HEADER_OFFSET + FW_HEADER_SIZE <= len(image) <= APP_LENGTH):
        raise ValidationError(f"image length out of range: {len(image)}")

    header = image[FW_HEADER_OFFSET : FW_HEADER_OFFSET + FW_HEADER_SIZE]
    if header[0:4] != b"ETFW":
        raise ValidationError("fw_header magic is not ETFW")
    if u32(header, 4) != 1:
        raise ValidationError("fw_header version is not 1")
    if u32(header, 36) != len(image):
        raise ValidationError("fw_header image_len does not match the file")
    if u32(header, FW_CRC_OFFSET) != crc32(header[:FW_CRC_OFFSET]):
        raise ValidationError("fw_header CRC32 mismatch")

    zeroed = bytearray(image)
    zeroed[
        FW_HEADER_OFFSET + FW_SHA_OFFSET :
        FW_HEADER_OFFSET + FW_SHA_OFFSET + FW_SHA_SIZE
    ] = bytes(FW_SHA_SIZE)
    zeroed[
        FW_HEADER_OFFSET + FW_CRC_OFFSET :
        FW_HEADER_OFFSET + FW_CRC_OFFSET + 4
    ] = bytes(4)
    if header[FW_SHA_OFFSET : FW_SHA_OFFSET + FW_SHA_SIZE] != hashlib.sha256(
        zeroed
    ).digest():
        raise ValidationError("fw_header double-zero image SHA256 mismatch")

    version_field = header[12:28]
    terminator = version_field.find(b"\x00")
    if terminator <= 0 or any(version_field[terminator:]):
        raise ValidationError("version_name is not non-empty and zero padded")
    try:
        version_name = version_field[:terminator].decode("ascii")
    except UnicodeDecodeError as exc:
        raise ValidationError("version_name is not ASCII") from exc

    if u32(header, 32) != 1:
        raise ValidationError("hw_rev is not 1")
    if header[72] != 1:
        raise ValidationError("layout_id is not 1")
    if header[73] > 1:
        raise ValidationError("min_boot_ver exceeds Boot version 1")
    if header[74:92] != bytes([0xFF]) * 18:
        raise ValidationError("fw_header padding is not all 0xFF")

    initial_msp = u32(image, 0)
    reset_handler = u32(image, 4)
    if not (RAM_ORIGIN <= initial_msp <= RAM_END):
        raise ValidationError(f"initial MSP out of range: 0x{initial_msp:08X}")
    reset_address = reset_handler & ~1
    if not (reset_handler & 1) or not (
        APP_ORIGIN <= reset_address < APP_ORIGIN + APP_LENGTH
    ):
        raise ValidationError(
            f"Reset_Handler is not a Thumb App address: 0x{reset_handler:08X}"
        )

    return {
        "version_code": u32(header, 8),
        "version_name": version_name,
        "build_ts": u32(header, 28),
        "image_len": len(image),
        "image_crc32": crc32(image),
        "initial_msp": initial_msp,
        "reset_handler": reset_handler,
    }


def split_asset(data: bytes, input_kind: str) -> tuple[bytes, str]:
    trailer_valid = False
    if len(data) >= 8:
        trailer_len, trailer_crc = struct.unpack_from("<II", data, len(data) - 8)
        payload = data[:-8]
        trailer_valid = trailer_len == len(payload) and trailer_crc == crc32(payload)

    if input_kind == "recovery" and not trailer_valid:
        raise ValidationError("recovery trailer length or CRC32 is invalid")
    if input_kind == "app":
        return data, "app"
    if trailer_valid:
        return data[:-8], "recovery"
    return data, "app"


def path_key(path: Path) -> str:
    return os.path.normcase(str(path.resolve()))


def validate_expected_identity(
    image: bytes,
    *,
    expected_bytes: int | None,
    expected_sha256: str | None,
    flash_address: int | None,
    expected_bytes_at: bytes,
) -> str:
    digest = hashlib.sha256(image).hexdigest()
    if expected_bytes is not None and len(image) != expected_bytes:
        raise ValidationError(
            f"image length {len(image)} does not match expected {expected_bytes}"
        )
    if expected_sha256 is not None and digest.upper() != expected_sha256.upper():
        raise ValidationError("image SHA-256 does not match expected value")
    if flash_address is not None:
        if not expected_bytes_at:
            raise ValidationError("--expected-bytes-at is required with --flash-address")
        flash_end = flash_address + len(expected_bytes_at)
        if flash_address < APP_ORIGIN or flash_end > APP_ORIGIN + len(image):
            raise ValidationError("flash address range is outside the App image")
        offset = flash_address - APP_ORIGIN
        actual = image[offset : offset + len(expected_bytes_at)]
        if actual != expected_bytes_at:
            raise ValidationError(
                f"bytes at 0x{flash_address:08X} do not match expected value"
            )
    elif expected_bytes_at:
        raise ValidationError("--flash-address is required with --expected-bytes-at")
    return digest


def assert_repo_output_file(path: Path) -> Path:
    output = path.resolve()
    try:
        output.relative_to(ROOT)
    except ValueError as exc:
        raise ValidationError("restore output must be inside the repository") from exc
    if output.exists():
        raise ValidationError(f"restore output already exists: {output}")
    if not output.parent.is_dir():
        raise ValidationError(f"restore output parent is absent: {output.parent}")

    current = output.parent
    while True:
        attributes = getattr(current.stat(), "st_file_attributes", 0)
        if current.is_symlink() or attributes & 0x400:
            raise ValidationError(f"restore output parent is a reparse point: {current}")
        if current == ROOT:
            break
        current = current.parent
    return output


def cmd_prepare(args: argparse.Namespace) -> int:
    source = args.input.resolve()
    output = args.output.resolve()
    recovery = (
        args.recovery_output.resolve()
        if args.recovery_output is not None
        else None
    )

    if path_key(source) == path_key(output):
        raise ValidationError("input and output paths must differ")
    if recovery is not None:
        if path_key(recovery) == path_key(source):
            raise ValidationError("recovery output must differ from input")
        if path_key(recovery) == path_key(output):
            raise ValidationError("recovery output must differ from App output")

    data = source.read_bytes()
    image, detected_kind = split_asset(data, args.input_kind)
    fields = validate_app(image)

    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_bytes(image)
    if output.read_bytes() != image:
        raise ValidationError("prepared App readback mismatch")

    if recovery is not None:
        recovery.parent.mkdir(parents=True, exist_ok=True)
        trailer = struct.pack("<II", len(image), crc32(image))
        recovery.write_bytes(image + trailer)
        recovered, kind = split_asset(recovery.read_bytes(), "recovery")
        if kind != "recovery" or recovered != image:
            raise ValidationError("generated recovery container readback mismatch")

    if source.read_bytes() != data:
        raise ValidationError("source asset changed during preparation")

    print(
        "P1_5_APP_PREPARE=PASS "
        f"kind={detected_kind} len={fields['image_len']} "
        f"vcode={fields['version_code']} crc32={fields['image_crc32']:08x}"
    )
    print(
        f"version={fields['version_name']} msp=0x{fields['initial_msp']:08x} "
        f"reset=0x{fields['reset_handler']:08x} sha256={hashlib.sha256(image).hexdigest()}"
    )
    print(f"prepared={output}")
    if recovery is not None:
        print(f"recovery={recovery}")
    print(f"source_sha256={hashlib.sha256(data).hexdigest()} source_preserved=1")
    return 0


def cmd_verify(args: argparse.Namespace) -> int:
    image, kind = split_asset(args.input.read_bytes(), args.input_kind)
    fields = validate_app(image)
    digest = validate_expected_identity(
        image,
        expected_bytes=args.expected_bytes,
        expected_sha256=args.expected_sha256,
        flash_address=args.flash_address,
        expected_bytes_at=args.expected_bytes_at,
    )
    print(
        "P1_5_APP_VERIFY=PASS "
        f"kind={kind} len={fields['image_len']} vcode={fields['version_code']} "
        f"crc32={fields['image_crc32']:08x} sha256={digest}"
    )
    return 0


def cmd_stage_restore(args: argparse.Namespace) -> int:
    source = args.input.resolve()
    image, kind = split_asset(source.read_bytes(), args.input_kind)
    fields = validate_app(image)
    digest = validate_expected_identity(
        image,
        expected_bytes=args.expected_bytes,
        expected_sha256=args.expected_sha256,
        flash_address=args.flash_address,
        expected_bytes_at=args.expected_bytes_at,
    )
    output = assert_repo_output_file(args.output)
    if path_key(source) == path_key(output):
        raise ValidationError("restore input and output paths must differ")

    with output.open("xb") as stream:
        stream.write(image)
        stream.flush()
        os.fsync(stream.fileno())
    if output.read_bytes() != image:
        raise ValidationError("staged restore image readback mismatch")

    print(
        "P1_5_APP_RESTORE_STAGE=PASS "
        f"kind={kind} len={fields['image_len']} vcode={fields['version_code']} "
        f"sha256={digest} app_origin=0x{APP_ORIGIN:08X}"
    )
    print(f"source={source}")
    print(f"staged={output}")
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser()
    subparsers = parser.add_subparsers(dest="subcommand", required=True)

    prepare = subparsers.add_parser("prepare")
    prepare.add_argument("--input", type=Path, required=True)
    prepare.add_argument("--output", type=Path, required=True)
    prepare.add_argument(
        "--input-kind", choices=("auto", "app", "recovery"), default="auto"
    )
    prepare.add_argument("--recovery-output", type=Path)
    prepare.set_defaults(func=cmd_prepare)

    verify = subparsers.add_parser("verify")
    verify.add_argument("--input", type=Path, required=True)
    verify.add_argument(
        "--input-kind", choices=("auto", "app", "recovery"), default="auto"
    )
    verify.add_argument("--expected-bytes", type=int)
    verify.add_argument("--expected-sha256")
    verify.add_argument("--flash-address", type=lambda value: int(value, 0))
    verify.add_argument("--expected-bytes-at", type=parse_expected_bytes, default=b"")
    verify.set_defaults(func=cmd_verify)

    stage = subparsers.add_parser("stage-restore")
    stage.add_argument("--input", type=Path, required=True)
    stage.add_argument("--output", type=Path, required=True)
    stage.add_argument(
        "--input-kind", choices=("auto", "app", "recovery"), default="auto"
    )
    stage.add_argument("--expected-bytes", type=int, required=True)
    stage.add_argument("--expected-sha256", required=True)
    stage.add_argument(
        "--flash-address", type=lambda value: int(value, 0), required=True
    )
    stage.add_argument(
        "--expected-bytes-at", type=parse_expected_bytes, required=True
    )
    stage.set_defaults(func=cmd_stage_restore)

    return parser


def main() -> int:
    try:
        args = build_parser().parse_args()
        return args.func(args)
    except (OSError, ValidationError) as exc:
        print(f"P1_5_TOOL=FAIL {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
