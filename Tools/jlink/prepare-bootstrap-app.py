#!/usr/bin/env python3
"""Prepare and verify P1-5 App assets and J-Link bootstrap messages."""

from __future__ import annotations

import argparse
import hashlib
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

COMMAND_SIZE = 128
COMMAND_MAGIC = 0x424A5445
DONE_MAGIC = 0x444A5445
COMMAND_VERSION = 1
COMMAND_COOKIE = 0x51A7B007

OFF_MAGIC = 0
OFF_VERSION = 4
OFF_OPCODE = 8
OFF_OPCODE_INVERSE = 12
OFF_COOKIE = 16
OFF_COOKIE_INVERSE = 20
OFF_ARG0 = 24
OFF_ARG1 = 28
OFF_COMMAND_CRC = 32
OFF_STATUS = 36
OFF_DETAIL = 40
OFF_PROGRESS = 44
OFF_TOTAL = 48
OFF_ACTIVE = 52
OFF_STATE = 56
OFF_BOOT_TRY = 60
OFF_COPY_PHASE = 64
OFF_RESUME_BLOCK = 68
OFF_CUR_VCODE = 72
OFF_CAND_VCODE = 76
OFF_BACKUP_VCODE = 80
OFF_IMAGE_VCODE = 84
OFF_IMAGE_LEN = 88
OFF_IMAGE_CRC = 92
OFF_RESULT_CRC = 96

STATUS_PASS = 2

COMMANDS = {
    "clear-bcb": (1, 0),
    "install-candidate": (2, 1),
    "install-backup": (2, 2),
    "install-recovery": (2, 4),
    "stage-slots": (3, 0),
    "snapshot-bcb": (4, 0),
}

DETAIL_NAMES = {
    0: "none",
    1: "command",
    2: "eeprom",
    3: "qspi_init",
    4: "bcb_locked",
    5: "app_invalid",
    6: "slot_argument",
    7: "slot_erase",
    8: "slot_program",
    9: "slot_verify",
    10: "slot_header",
    11: "stage_validate",
    12: "stage_commit",
}


class ValidationError(ValueError):
    pass


def crc32(data: bytes) -> int:
    return zlib.crc32(data) & 0xFFFFFFFF


def u32(data: bytes, offset: int) -> int:
    return struct.unpack_from("<I", data, offset)[0]


def put_u32(data: bytearray, offset: int, value: int) -> None:
    struct.pack_into("<I", data, offset, value & 0xFFFFFFFF)


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


def cmd_prepare(args: argparse.Namespace) -> int:
    source = args.input.resolve()
    output = args.output.resolve()
    data = source.read_bytes()
    image, detected_kind = split_asset(data, args.input_kind)
    fields = validate_app(image)

    output.parent.mkdir(parents=True, exist_ok=True)
    if source == output and detected_kind == "app":
        raise ValidationError("input and output paths must differ")
    output.write_bytes(image)
    if output.read_bytes() != image:
        raise ValidationError("prepared App readback mismatch")

    if args.recovery_output is not None:
        recovery = args.recovery_output.resolve()
        recovery.parent.mkdir(parents=True, exist_ok=True)
        trailer = struct.pack("<II", len(image), crc32(image))
        recovery.write_bytes(image + trailer)
        recovered, kind = split_asset(recovery.read_bytes(), "recovery")
        if kind != "recovery" or recovered != image:
            raise ValidationError("generated recovery container readback mismatch")

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
    if args.recovery_output is not None:
        print(f"recovery={args.recovery_output.resolve()}")
    return 0


def cmd_verify(args: argparse.Namespace) -> int:
    image, kind = split_asset(args.input.read_bytes(), args.input_kind)
    fields = validate_app(image)
    print(
        "P1_5_APP_VERIFY=PASS "
        f"kind={kind} len={fields['image_len']} vcode={fields['version_code']} "
        f"crc32={fields['image_crc32']:08x} sha256={hashlib.sha256(image).hexdigest()}"
    )
    return 0


def cmd_command(args: argparse.Namespace) -> int:
    opcode, arg0 = COMMANDS[args.operation]
    command = bytearray(COMMAND_SIZE)
    put_u32(command, OFF_MAGIC, COMMAND_MAGIC)
    put_u32(command, OFF_VERSION, COMMAND_VERSION)
    put_u32(command, OFF_OPCODE, opcode)
    put_u32(command, OFF_OPCODE_INVERSE, ~opcode)
    put_u32(command, OFF_COOKIE, COMMAND_COOKIE)
    put_u32(command, OFF_COOKIE_INVERSE, ~COMMAND_COOKIE)
    put_u32(command, OFF_ARG0, arg0)
    put_u32(command, OFF_ARG1, 0)
    put_u32(command, OFF_COMMAND_CRC, crc32(command[:OFF_COMMAND_CRC]))
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_bytes(command)
    print(
        "P1_5_BOOTSTRAP_COMMAND=PASS "
        f"operation={args.operation} opcode={opcode} arg0={arg0} "
        f"crc32={u32(command, OFF_COMMAND_CRC):08x} output={args.output.resolve()}"
    )
    return 0


def cmd_result(args: argparse.Namespace) -> int:
    result = args.input.read_bytes()
    if len(result) != COMMAND_SIZE:
        raise ValidationError(f"bootstrap result size is {len(result)}, expected 128")
    if u32(result, OFF_MAGIC) != DONE_MAGIC:
        raise ValidationError("bootstrap result magic is not complete")
    stored_crc = u32(result, OFF_RESULT_CRC)
    calculated_crc = crc32(result[OFF_STATUS:OFF_RESULT_CRC])
    if stored_crc != calculated_crc:
        raise ValidationError(
            f"bootstrap result CRC mismatch: {stored_crc:08x} != {calculated_crc:08x}"
        )

    status = u32(result, OFF_STATUS)
    detail = u32(result, OFF_DETAIL)
    values = {
        "progress": u32(result, OFF_PROGRESS),
        "total": u32(result, OFF_TOTAL),
        "active": u32(result, OFF_ACTIVE),
        "state": u32(result, OFF_STATE),
        "boot_try": u32(result, OFF_BOOT_TRY),
        "copy_phase": u32(result, OFF_COPY_PHASE),
        "resume_block": u32(result, OFF_RESUME_BLOCK),
        "cur_vcode": u32(result, OFF_CUR_VCODE),
        "cand_vcode": u32(result, OFF_CAND_VCODE),
        "backup_vcode": u32(result, OFF_BACKUP_VCODE),
        "image_vcode": u32(result, OFF_IMAGE_VCODE),
        "image_len": u32(result, OFF_IMAGE_LEN),
        "image_crc32": u32(result, OFF_IMAGE_CRC),
    }
    outcome = "PASS" if status == STATUS_PASS else "FAIL"
    print(
        f"P1_5_BOOTSTRAP_RESULT={outcome} status={status} "
        f"detail={detail}:{DETAIL_NAMES.get(detail, 'unknown')} "
        f"progress={values['progress']}/{values['total']}"
    )
    print(" ".join(f"{name}={value}" for name, value in values.items()))
    if status != STATUS_PASS:
        raise ValidationError("bootstrap operation reported failure")
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
    verify.set_defaults(func=cmd_verify)

    command = subparsers.add_parser("command")
    command.add_argument("--operation", choices=tuple(COMMANDS), required=True)
    command.add_argument("--output", type=Path, required=True)
    command.set_defaults(func=cmd_command)

    result = subparsers.add_parser("result")
    result.add_argument("--input", type=Path, required=True)
    result.set_defaults(func=cmd_result)
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
