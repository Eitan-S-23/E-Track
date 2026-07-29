#!/usr/bin/env python3
"""Encode and decode the evidence-only P1-6 RAM control block."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import re
import struct
import zlib


ROOT = Path(__file__).resolve().parents[2]
HEADER = ROOT / "Libraries/OTA/ota_p1_6_test.h"


def load_macros(path: Path = HEADER) -> dict[str, int]:
    text = path.read_text(encoding="utf-8")
    values: dict[str, int] = {}
    pattern = re.compile(
        r"^\s*#define\s+(OTA_P1_6_[A-Z0-9_]+)\s+"
        r"(0x[0-9A-Fa-f]+|[0-9]+)[uUlL]*\s*$",
        re.MULTILINE,
    )
    for match in pattern.finditer(text):
        values[match.group(1)] = int(match.group(2), 0)
    required = {
        "OTA_P1_6_CONTROL_SIZE",
        "OTA_P1_6_COMMAND_MAGIC",
        "OTA_P1_6_ARM_MAGIC",
        "OTA_P1_6_DONE_MAGIC",
        "OTA_P1_6_VERSION",
        "OTA_P1_6_COOKIE",
        "OTA_P1_6_OFF_MAGIC",
        "OTA_P1_6_OFF_VERSION",
        "OTA_P1_6_OFF_OPCODE",
        "OTA_P1_6_OFF_OPCODE_INVERSE",
        "OTA_P1_6_OFF_COOKIE",
        "OTA_P1_6_OFF_COOKIE_INVERSE",
        "OTA_P1_6_OFF_ARG0",
        "OTA_P1_6_OFF_ARG1",
        "OTA_P1_6_OFF_ARG2",
        "OTA_P1_6_OFF_ARG3",
        "OTA_P1_6_OFF_COMMAND_CRC32",
        "OTA_P1_6_COMMAND_CRC_LENGTH",
        "OTA_P1_6_OFF_STATUS",
        "OTA_P1_6_OFF_TARGET_CHECKPOINT",
        "OTA_P1_6_OFF_TARGET_ARG0",
        "OTA_P1_6_OFF_TARGET_ARG1",
        "OTA_P1_6_TARGET_CRC_LENGTH",
        "OTA_P1_6_OFF_TARGET_CRC32",
        "OTA_P1_6_OFF_RESULT_CRC32",
    }
    missing = sorted(required - values.keys())
    if missing:
        raise ValueError(f"literal P1-6 macros missing: {', '.join(missing)}")
    values["OTA_P1_6_RESULT_CRC_OFFSET"] = values["OTA_P1_6_OFF_STATUS"]
    values["OTA_P1_6_RESULT_CRC_LENGTH"] = (
        values["OTA_P1_6_OFF_RESULT_CRC32"]
        - values["OTA_P1_6_RESULT_CRC_OFFSET"]
    )
    return values


def put_u32(block: bytearray, offset: int, value: int) -> None:
    struct.pack_into("<I", block, offset, value & 0xFFFFFFFF)


def get_u32(block: bytes | bytearray, offset: int) -> int:
    return struct.unpack_from("<I", block, offset)[0]


def build_command(opcode: int, args: tuple[int, int, int, int]) -> bytearray:
    m = load_macros()
    block = bytearray(m["OTA_P1_6_CONTROL_SIZE"])
    put_u32(block, m["OTA_P1_6_OFF_MAGIC"], m["OTA_P1_6_COMMAND_MAGIC"])
    put_u32(block, m["OTA_P1_6_OFF_VERSION"], m["OTA_P1_6_VERSION"])
    put_u32(block, m["OTA_P1_6_OFF_OPCODE"], opcode)
    put_u32(block, m["OTA_P1_6_OFF_OPCODE_INVERSE"], ~opcode)
    put_u32(block, m["OTA_P1_6_OFF_COOKIE"], m["OTA_P1_6_COOKIE"])
    put_u32(block, m["OTA_P1_6_OFF_COOKIE_INVERSE"], ~m["OTA_P1_6_COOKIE"])
    for offset_name, value in zip(
        ("OTA_P1_6_OFF_ARG0", "OTA_P1_6_OFF_ARG1",
         "OTA_P1_6_OFF_ARG2", "OTA_P1_6_OFF_ARG3"),
        args,
    ):
        put_u32(block, m[offset_name], value)
    crc = zlib.crc32(block[: m["OTA_P1_6_COMMAND_CRC_LENGTH"]])
    put_u32(block, m["OTA_P1_6_OFF_COMMAND_CRC32"], crc)
    return block


def build_arm(checkpoint: int, arg0: int, arg1: int) -> bytearray:
    m = load_macros()
    block = bytearray(m["OTA_P1_6_CONTROL_SIZE"])
    put_u32(block, m["OTA_P1_6_OFF_MAGIC"], m["OTA_P1_6_ARM_MAGIC"])
    put_u32(block, m["OTA_P1_6_OFF_VERSION"], m["OTA_P1_6_VERSION"])
    put_u32(block, m["OTA_P1_6_OFF_COOKIE"], m["OTA_P1_6_COOKIE"])
    put_u32(block, m["OTA_P1_6_OFF_COOKIE_INVERSE"], ~m["OTA_P1_6_COOKIE"])
    put_u32(block, m["OTA_P1_6_OFF_STATUS"], 0)
    put_u32(block, m["OTA_P1_6_OFF_TARGET_CHECKPOINT"], checkpoint)
    put_u32(block, m["OTA_P1_6_OFF_TARGET_ARG0"], arg0)
    put_u32(block, m["OTA_P1_6_OFF_TARGET_ARG1"], arg1)
    start = m["OTA_P1_6_OFF_TARGET_CHECKPOINT"]
    crc = zlib.crc32(block[start : start + m["OTA_P1_6_TARGET_CRC_LENGTH"]])
    put_u32(block, m["OTA_P1_6_OFF_TARGET_CRC32"], crc)
    return block


def staged_payload(block: bytearray) -> tuple[bytearray, int]:
    m = load_macros()
    magic = get_u32(block, m["OTA_P1_6_OFF_MAGIC"])
    staged = bytearray(block)
    put_u32(staged, m["OTA_P1_6_OFF_MAGIC"], 0)
    return staged, magic


def decode(block: bytes) -> dict[str, object]:
    m = load_macros()
    if len(block) != m["OTA_P1_6_CONTROL_SIZE"]:
        raise ValueError(f"control block must be {m['OTA_P1_6_CONTROL_SIZE']} bytes")
    fields = {
        name.removeprefix("OTA_P1_6_OFF_").lower(): get_u32(block, offset)
        for name, offset in m.items()
        if name.startswith("OTA_P1_6_OFF_") and offset + 4 <= len(block)
    }
    result_start = m["OTA_P1_6_RESULT_CRC_OFFSET"]
    result_length = m["OTA_P1_6_RESULT_CRC_LENGTH"]
    observed_crc = fields["result_crc32"]
    expected_crc = zlib.crc32(block[result_start : result_start + result_length])
    fields["result_crc_valid"] = observed_crc == expected_crc
    fields["done"] = fields["magic"] == m["OTA_P1_6_DONE_MAGIC"]
    fields["command_crc_valid"] = (
        fields["command_crc32"]
        == zlib.crc32(block[: m["OTA_P1_6_COMMAND_CRC_LENGTH"]])
    )
    target_start = m["OTA_P1_6_OFF_TARGET_CHECKPOINT"]
    fields["target_crc_valid"] = (
        fields["target_crc32"]
        == zlib.crc32(block[target_start : target_start + m["OTA_P1_6_TARGET_CRC_LENGTH"]])
    )
    fields["cookie_inverse_valid"] = (
        fields["cookie"] ^ fields["cookie_inverse"]
    ) == 0xFFFFFFFF
    fields["opcode_inverse_valid"] = (
        fields["opcode"] ^ fields["opcode_inverse"]
    ) == 0xFFFFFFFF
    magic_names = {
        m["OTA_P1_6_COMMAND_MAGIC"]: "command",
        m["OTA_P1_6_ARM_MAGIC"]: "arm",
        m["OTA_P1_6_DONE_MAGIC"]: "done",
    }
    fields["kind"] = magic_names.get(fields["magic"], "unknown")
    fields["command_valid"] = (
        fields["kind"] == "command"
        and fields["version"] == m["OTA_P1_6_VERSION"]
        and fields["cookie"] == m["OTA_P1_6_COOKIE"]
        and fields["cookie_inverse_valid"]
        and fields["opcode_inverse_valid"]
        and fields["command_crc_valid"]
    )
    fields["arm_valid"] = (
        fields["kind"] == "arm"
        and fields["version"] == m["OTA_P1_6_VERSION"]
        and fields["cookie"] == m["OTA_P1_6_COOKIE"]
        and fields["cookie_inverse_valid"]
        and fields["target_crc_valid"]
    )
    fields["bcb_a_raw"] = block[192:256].hex()
    fields["bcb_b_raw"] = block[256:320].hex()
    fields["app_sha256"] = block[136:168].hex()
    fields["slot_sha8"] = block[184:192].hex()
    fields["slot_header_raw_hex"] = block[336:368].hex()
    return fields


def parse_u32(value: str) -> int:
    return int(value, 0) & 0xFFFFFFFF


def main() -> int:
    parser = argparse.ArgumentParser()
    subparsers = parser.add_subparsers(dest="mode", required=True)

    command = subparsers.add_parser("command")
    command.add_argument("--opcode", required=True, type=parse_u32)
    for name in ("arg0", "arg1", "arg2", "arg3"):
        command.add_argument(f"--{name}", default=0, type=parse_u32)
    command.add_argument("--output", required=True, type=Path)
    command.add_argument("--magic-output", required=True, type=Path)
    command.add_argument("--committed-output", type=Path)

    arm = subparsers.add_parser("arm")
    arm.add_argument("--checkpoint", required=True, type=parse_u32)
    arm.add_argument("--arg0", default=0xFFFFFFFF, type=parse_u32)
    arm.add_argument("--arg1", default=0xFFFFFFFF, type=parse_u32)
    arm.add_argument("--output", required=True, type=Path)
    arm.add_argument("--magic-output", required=True, type=Path)
    arm.add_argument("--committed-output", type=Path)

    decode_parser = subparsers.add_parser("decode")
    decode_parser.add_argument("--input", required=True, type=Path)
    decode_parser.add_argument("--output", type=Path)

    args = parser.parse_args()
    if args.mode == "command":
        block = build_command(args.opcode, (args.arg0, args.arg1, args.arg2, args.arg3))
        staged, magic = staged_payload(block)
        args.output.write_bytes(staged)
        args.magic_output.write_text(f"0x{magic:08X}\n", encoding="ascii")
        if args.committed_output:
            args.committed_output.write_bytes(block)
        return 0
    if args.mode == "arm":
        block = build_arm(args.checkpoint, args.arg0, args.arg1)
        staged, magic = staged_payload(block)
        args.output.write_bytes(staged)
        args.magic_output.write_text(f"0x{magic:08X}\n", encoding="ascii")
        if args.committed_output:
            args.committed_output.write_bytes(block)
        return 0

    decoded = decode(args.input.read_bytes())
    output = json.dumps(decoded, indent=2, sort_keys=True) + "\n"
    if args.output:
        args.output.write_text(output, encoding="ascii")
    else:
        print(output, end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
