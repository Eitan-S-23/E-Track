#!/usr/bin/env python3
"""Encode and validate the evidence-only P2-1 staging control block."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import re
import secrets
import struct
import zlib


ROOT = Path(__file__).resolve().parents[2]
HEADER = ROOT / "Libraries/OTA/ota_p2_1_test.h"


def load_macros(path: Path = HEADER) -> dict[str, int]:
    text = path.read_text(encoding="utf-8")
    values: dict[str, int] = {}
    pattern = re.compile(
        r"^\s*#define\s+(OTA_P2_1_[A-Z0-9_]+)\s+"
        r"(0x[0-9A-Fa-f]+|[0-9]+)[uUlL]*\s*$",
        re.MULTILINE,
    )
    for match in pattern.finditer(text):
        values[match.group(1)] = int(match.group(2), 0)

    enum_pattern = re.compile(
        r"^\s*(OTA_P2_1_STATUS_[A-Z0-9_]+)\s*=\s*([0-9]+)\s*,?\s*$",
        re.MULTILINE,
    )
    for match in enum_pattern.finditer(text):
        values[match.group(1)] = int(match.group(2), 10)

    required = {
        "OTA_P2_1_CONTROL_SIZE",
        "OTA_P2_1_COMMAND_MAGIC",
        "OTA_P2_1_DONE_MAGIC",
        "OTA_P2_1_VERSION",
        "OTA_P2_1_OPCODE_REENTRY",
        "OTA_P2_1_COOKIE",
        "OTA_P2_1_OFF_MAGIC",
        "OTA_P2_1_OFF_VERSION",
        "OTA_P2_1_OFF_OPCODE",
        "OTA_P2_1_OFF_OPCODE_INVERSE",
        "OTA_P2_1_OFF_COOKIE",
        "OTA_P2_1_OFF_COOKIE_INVERSE",
        "OTA_P2_1_OFF_SESSION_SHA256",
        "OTA_P2_1_OFF_COMMAND_CRC32",
        "OTA_P2_1_COMMAND_CRC_LENGTH",
        "OTA_P2_1_OFF_STATUS",
        "OTA_P2_1_OFF_CHECKPOINT",
        "OTA_P2_1_OFF_RESUMED",
        "OTA_P2_1_OFF_DURABLE_BEFORE",
        "OTA_P2_1_OFF_DURABLE_AFTER",
        "OTA_P2_1_OFF_SEGMENT_BITMAP",
        "OTA_P2_1_OFF_PERSISTENT_BITMAP",
        "OTA_P2_1_OFF_HEADER_ERASES",
        "OTA_P2_1_OFF_DATA_ERASES",
        "OTA_P2_1_OFF_DATA_PROGRAMS",
        "OTA_P2_1_OFF_DETAIL",
        "OTA_P2_1_OFF_RESULT_CRC32",
        "OTA_P2_1_RESULT_CRC_LENGTH",
        "OTA_P2_1_STATUS_ARMED",
        "OTA_P2_1_STATUS_CHECKPOINT",
        "OTA_P2_1_STATUS_PASS",
    }
    missing = sorted(required - values.keys())
    if missing:
        raise ValueError(f"literal P2-1 macros missing: {', '.join(missing)}")
    return values


def put_u32(block: bytearray, offset: int, value: int) -> None:
    struct.pack_into("<I", block, offset, value & 0xFFFFFFFF)


def get_u32(block: bytes | bytearray, offset: int) -> int:
    return struct.unpack_from("<I", block, offset)[0]


def parse_sha256(value: str) -> bytes:
    if not re.fullmatch(r"[0-9A-Fa-f]{64}", value):
        raise argparse.ArgumentTypeError("SHA-256 must contain exactly 64 hex digits")
    return bytes.fromhex(value)


def build_payload() -> bytes:
    return bytes(((index * 17 + 3) & 0xFF) for index in range(4096))


def build_command(session_sha256: bytes) -> bytearray:
    m = load_macros()
    if len(session_sha256) != 32:
        raise ValueError("session SHA-256 must be 32 bytes")

    block = bytearray(m["OTA_P2_1_CONTROL_SIZE"])
    put_u32(block, m["OTA_P2_1_OFF_MAGIC"], m["OTA_P2_1_COMMAND_MAGIC"])
    put_u32(block, m["OTA_P2_1_OFF_VERSION"], m["OTA_P2_1_VERSION"])
    opcode = m["OTA_P2_1_OPCODE_REENTRY"]
    put_u32(block, m["OTA_P2_1_OFF_OPCODE"], opcode)
    put_u32(block, m["OTA_P2_1_OFF_OPCODE_INVERSE"], ~opcode)
    cookie = m["OTA_P2_1_COOKIE"]
    put_u32(block, m["OTA_P2_1_OFF_COOKIE"], cookie)
    put_u32(block, m["OTA_P2_1_OFF_COOKIE_INVERSE"], ~cookie)
    sha_offset = m["OTA_P2_1_OFF_SESSION_SHA256"]
    block[sha_offset : sha_offset + 32] = session_sha256
    crc_start = m["OTA_P2_1_OFF_VERSION"]
    crc_len = m["OTA_P2_1_COMMAND_CRC_LENGTH"]
    put_u32(
        block,
        m["OTA_P2_1_OFF_COMMAND_CRC32"],
        zlib.crc32(block[crc_start : crc_start + crc_len]),
    )
    put_u32(block, m["OTA_P2_1_OFF_STATUS"], m["OTA_P2_1_STATUS_ARMED"])
    return block


def staged_payload(block: bytearray) -> tuple[bytearray, int]:
    m = load_macros()
    staged = bytearray(block)
    magic = get_u32(staged, m["OTA_P2_1_OFF_MAGIC"])
    put_u32(staged, m["OTA_P2_1_OFF_MAGIC"], 0)
    return staged, magic


def decode_control(block: bytes) -> dict[str, object]:
    m = load_macros()
    if len(block) != m["OTA_P2_1_CONTROL_SIZE"]:
        raise ValueError(
            f"control block must be {m['OTA_P2_1_CONTROL_SIZE']} bytes"
        )

    fields = {
        "magic": get_u32(block, m["OTA_P2_1_OFF_MAGIC"]),
        "version": get_u32(block, m["OTA_P2_1_OFF_VERSION"]),
        "opcode": get_u32(block, m["OTA_P2_1_OFF_OPCODE"]),
        "opcode_inverse": get_u32(block, m["OTA_P2_1_OFF_OPCODE_INVERSE"]),
        "cookie": get_u32(block, m["OTA_P2_1_OFF_COOKIE"]),
        "cookie_inverse": get_u32(block, m["OTA_P2_1_OFF_COOKIE_INVERSE"]),
        "command_crc32": get_u32(block, m["OTA_P2_1_OFF_COMMAND_CRC32"]),
        "status": get_u32(block, m["OTA_P2_1_OFF_STATUS"]),
        "checkpoint": get_u32(block, m["OTA_P2_1_OFF_CHECKPOINT"]),
        "resumed": get_u32(block, m["OTA_P2_1_OFF_RESUMED"]),
        "durable_before": get_u32(block, m["OTA_P2_1_OFF_DURABLE_BEFORE"]),
        "durable_after": get_u32(block, m["OTA_P2_1_OFF_DURABLE_AFTER"]),
        "segment_bitmap": get_u32(block, m["OTA_P2_1_OFF_SEGMENT_BITMAP"]),
        "persistent_bitmap": get_u32(
            block, m["OTA_P2_1_OFF_PERSISTENT_BITMAP"]
        ),
        "header_erases": get_u32(block, m["OTA_P2_1_OFF_HEADER_ERASES"]),
        "data_erases": get_u32(block, m["OTA_P2_1_OFF_DATA_ERASES"]),
        "data_programs": get_u32(block, m["OTA_P2_1_OFF_DATA_PROGRAMS"]),
        "detail": get_u32(block, m["OTA_P2_1_OFF_DETAIL"]),
        "result_crc32": get_u32(block, m["OTA_P2_1_OFF_RESULT_CRC32"]),
    }
    sha_offset = m["OTA_P2_1_OFF_SESSION_SHA256"]
    fields["session_sha256"] = block[sha_offset : sha_offset + 32].hex()
    crc_start = m["OTA_P2_1_OFF_VERSION"]
    crc_len = m["OTA_P2_1_COMMAND_CRC_LENGTH"]
    fields["command_crc_valid"] = fields["command_crc32"] == zlib.crc32(
        block[crc_start : crc_start + crc_len]
    )
    result_start = m["OTA_P2_1_OFF_STATUS"]
    result_len = m["OTA_P2_1_RESULT_CRC_LENGTH"]
    fields["result_crc_valid"] = fields["result_crc32"] == zlib.crc32(
        block[result_start : result_start + result_len]
    )
    fields["opcode_inverse_valid"] = (
        fields["opcode"] ^ fields["opcode_inverse"]
    ) == 0xFFFFFFFF
    fields["cookie_inverse_valid"] = (
        fields["cookie"] ^ fields["cookie_inverse"]
    ) == 0xFFFFFFFF
    fields["command_fields_valid"] = (
        fields["version"] == m["OTA_P2_1_VERSION"]
        and fields["opcode"] == m["OTA_P2_1_OPCODE_REENTRY"]
        and fields["cookie"] == m["OTA_P2_1_COOKIE"]
        and fields["opcode_inverse_valid"]
        and fields["cookie_inverse_valid"]
        and fields["command_crc_valid"]
    )
    fields["kind"] = {
        m["OTA_P2_1_COMMAND_MAGIC"]: "command",
        m["OTA_P2_1_DONE_MAGIC"]: "done",
    }.get(fields["magic"], "unknown")
    return fields


def require_equal(checks: list[str], label: str, actual: object, expected: object) -> None:
    if actual != expected:
        raise ValueError(f"{label}: got {actual!r}, expected {expected!r}")
    checks.append(label)


def require_true(checks: list[str], label: str, value: object) -> None:
    if not value:
        raise ValueError(f"{label}: condition is false")
    checks.append(label)


def verify_etrj(
    checks: list[str], label: str, raw: bytes, session_sha256: bytes
) -> None:
    require_equal(checks, f"{label} ETRJ size", len(raw), 44)
    require_equal(checks, f"{label} ETRJ magic", raw[:4], b"ETRJ")
    require_equal(checks, f"{label} ETRJ SHA", raw[4:36], session_sha256)
    require_equal(checks, f"{label} ETRJ total_len", get_u32(raw, 36), 4096)
    require_equal(
        checks,
        f"{label} ETRJ CRC",
        get_u32(raw, 40),
        zlib.crc32(raw[:40]),
    )


def verify_evidence(args: argparse.Namespace) -> dict[str, object]:
    m = load_macros()
    checks: list[str] = []
    committed = args.command.read_bytes()
    command_readback = args.command_readback.read_bytes()
    checkpoint_raw = args.checkpoint_control.read_bytes()
    final_raw = args.final_control.read_bytes()
    checkpoint_header = args.checkpoint_header.read_bytes()
    final_header = args.final_header.read_bytes()
    checkpoint_payload = args.checkpoint_payload.read_bytes()
    final_payload = args.final_payload.read_bytes()

    require_equal(checks, "command magic-last readback", command_readback, committed)
    command = decode_control(committed)
    checkpoint = decode_control(checkpoint_raw)
    final = decode_control(final_raw)
    session_sha256 = bytes.fromhex(str(command["session_sha256"]))

    require_equal(checks, "command kind", command["kind"], "command")
    require_true(checks, "command fields", command["command_fields_valid"])

    checkpoint_expected = {
        "kind": "command",
        "status": m["OTA_P2_1_STATUS_CHECKPOINT"],
        "checkpoint": 3,
        "resumed": 0,
        "durable_before": 0,
        "durable_after": 0,
        "segment_bitmap": 0xFFFFFFFF,
        "persistent_bitmap": 0xFF,
        "header_erases": 1,
        "data_erases": 1,
        "data_programs": 1,
        "detail": 0,
    }
    for name, expected in checkpoint_expected.items():
        require_equal(checks, f"checkpoint control {name}", checkpoint[name], expected)
    require_true(checks, "checkpoint command fields", checkpoint["command_fields_valid"])
    require_true(checks, "checkpoint result CRC", checkpoint["result_crc_valid"])
    require_equal(
        checks,
        "checkpoint session SHA",
        checkpoint["session_sha256"],
        command["session_sha256"],
    )

    final_expected = {
        "kind": "done",
        "status": m["OTA_P2_1_STATUS_PASS"],
        "checkpoint": 3,
        "resumed": 1,
        "durable_before": 0,
        "durable_after": 4096,
        "segment_bitmap": 0,
        "persistent_bitmap": 0xFE,
        "header_erases": 1,
        "data_erases": 2,
        "data_programs": 2,
        "detail": 0,
    }
    for name, expected in final_expected.items():
        require_equal(checks, f"final control {name}", final[name], expected)
    require_true(checks, "final command fields", final["command_fields_valid"])
    require_true(checks, "final result CRC", final["result_crc_valid"])
    require_equal(
        checks,
        "final session SHA",
        final["session_sha256"],
        command["session_sha256"],
    )

    require_equal(checks, "checkpoint header size", len(checkpoint_header), 4096)
    require_equal(checks, "final header size", len(final_header), 4096)
    checkpoint_etsl = checkpoint_header[:32]
    checkpoint_etrj = checkpoint_header[0x40:0x6C]
    checkpoint_bitmap = checkpoint_header[0x70:0xB0]
    final_etsl = final_header[:32]
    final_etrj = final_header[0x40:0x6C]
    final_bitmap = final_header[0x70:0xB0]

    require_true(checks, "checkpoint ETSL erased", all(v == 0xFF for v in checkpoint_etsl))
    verify_etrj(checks, "checkpoint", checkpoint_etrj, session_sha256)
    require_true(
        checks,
        "checkpoint bitmap erased",
        all(v == 0xFF for v in checkpoint_bitmap),
    )
    verify_etrj(checks, "final", final_etrj, session_sha256)
    require_equal(checks, "ETRJ unchanged across reset", final_etrj, checkpoint_etrj)
    require_equal(checks, "final bitmap first byte", final_bitmap[0], 0xFE)
    require_true(
        checks,
        "final bitmap remaining bytes erased",
        all(v == 0xFF for v in final_bitmap[1:]),
    )

    payload = build_payload()
    payload_crc32 = zlib.crc32(payload)
    require_equal(checks, "checkpoint payload", checkpoint_payload, payload)
    require_equal(checks, "final payload", final_payload, payload)

    desired_etsl = bytearray(b"\xFF" * 32)
    desired_etsl[:4] = b"ETSL"
    desired_etsl[4] = 3
    put_u32(desired_etsl, 8, len(payload))
    put_u32(desired_etsl, 12, payload_crc32)
    put_u32(desired_etsl, 16, args.target_vcode)
    desired_etsl[20:28] = session_sha256[:8]
    put_u32(desired_etsl, 28, 0x434F4D54)
    require_equal(checks, "final ETSL", final_etsl, bytes(desired_etsl))

    for label, header in (("checkpoint", checkpoint_header), ("final", final_header)):
        require_true(
            checks,
            f"{label} reserved 0x020..0x03F erased",
            all(v == 0xFF for v in header[0x20:0x40]),
        )
        require_true(
            checks,
            f"{label} ETRJ pad erased",
            all(v == 0xFF for v in header[0x6C:0x70]),
        )
        require_true(
            checks,
            f"{label} header tail erased",
            all(v == 0xFF for v in header[0xB0:]),
        )

    args.output_dir.mkdir(parents=True, exist_ok=True)
    extracts = {
        "checkpoint-etsl.bin": checkpoint_etsl,
        "checkpoint-etrj.bin": checkpoint_etrj,
        "checkpoint-bitmap.bin": checkpoint_bitmap,
        "final-etsl.bin": final_etsl,
        "final-etrj.bin": final_etrj,
        "final-bitmap.bin": final_bitmap,
        "expected-payload.bin": payload,
    }
    for name, data in extracts.items():
        (args.output_dir / name).write_bytes(data)

    return {
        "result": "PASS",
        "checks": len(checks),
        "session_sha256": session_sha256.hex(),
        "payload_crc32": f"0x{payload_crc32:08X}",
        "payload_sha256": hashlib.sha256(payload).hexdigest(),
        "checkpoint_control": checkpoint,
        "final_control": final,
        "checkpoint_header_sha256": hashlib.sha256(checkpoint_header).hexdigest(),
        "final_header_sha256": hashlib.sha256(final_header).hexdigest(),
        "checkpoint_payload_sha256": hashlib.sha256(checkpoint_payload).hexdigest(),
        "final_payload_sha256": hashlib.sha256(final_payload).hexdigest(),
        "check_names": checks,
    }


def write_json(path: Path | None, value: dict[str, object]) -> None:
    output = json.dumps(value, indent=2, sort_keys=True) + "\n"
    if path is None:
        print(output, end="")
    else:
        path.write_text(output, encoding="ascii")


def main() -> int:
    parser = argparse.ArgumentParser()
    subparsers = parser.add_subparsers(dest="mode", required=True)

    command = subparsers.add_parser("command")
    command.add_argument("--session-sha256", type=parse_sha256)
    command.add_argument("--output", required=True, type=Path)
    command.add_argument("--committed-output", required=True, type=Path)
    command.add_argument("--magic-output", required=True, type=Path)
    command.add_argument("--metadata-output", required=True, type=Path)

    decode = subparsers.add_parser("decode")
    decode.add_argument("--input", required=True, type=Path)
    decode.add_argument("--output", type=Path)

    verify = subparsers.add_parser("verify")
    verify.add_argument("--command", required=True, type=Path)
    verify.add_argument("--command-readback", required=True, type=Path)
    verify.add_argument("--checkpoint-control", required=True, type=Path)
    verify.add_argument("--final-control", required=True, type=Path)
    verify.add_argument("--checkpoint-header", required=True, type=Path)
    verify.add_argument("--final-header", required=True, type=Path)
    verify.add_argument("--checkpoint-payload", required=True, type=Path)
    verify.add_argument("--final-payload", required=True, type=Path)
    verify.add_argument("--target-vcode", type=lambda value: int(value, 0), default=20800)
    verify.add_argument("--output-dir", required=True, type=Path)
    verify.add_argument("--output", required=True, type=Path)

    args = parser.parse_args()
    if args.mode == "command":
        session_sha256 = args.session_sha256 or secrets.token_bytes(32)
        committed = build_command(session_sha256)
        staged, magic = staged_payload(committed)
        args.output.write_bytes(staged)
        args.committed_output.write_bytes(committed)
        args.magic_output.write_text(f"0x{magic:08X}\n", encoding="ascii")
        payload = build_payload()
        write_json(
            args.metadata_output,
            {
                "session_sha256": session_sha256.hex(),
                "payload_crc32": f"0x{zlib.crc32(payload):08X}",
                "payload_sha256": hashlib.sha256(payload).hexdigest(),
            },
        )
        return 0
    if args.mode == "decode":
        write_json(args.output, decode_control(args.input.read_bytes()))
        return 0

    write_json(args.output, verify_evidence(args))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
