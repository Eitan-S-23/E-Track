#!/usr/bin/env python3
"""Encode and validate the evidence-only P2-2 package control block."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import re
import struct
import zlib


ROOT = Path(__file__).resolve().parents[2]
CONTROL_HEADER = ROOT / "Libraries/OTA/ota_p2_2_test.h"
PACKAGE_HEADER = ROOT / "Libraries/OTA/ota_package.h"
LAYOUT_HEADER = ROOT / "Libraries/OTA/ota_layout.h"
GOLDEN_PACKAGE_SHA256 = (
    "d8e26e51cf574570d69842b6dcc926c7becb2f050a2f996702c1075fc1617bfc"
)
GOLDEN_IMAGE_SHA256 = (
    "f68f357c708c2d65e6b1547648e955ea47949d81bd52f2cded684a8f640e21c3"
)


def load_literal_macros(path: Path, prefix: str) -> dict[str, int]:
    text = path.read_text(encoding="ascii")
    values: dict[str, int] = {}
    pattern = re.compile(
        rf"^\s*#define\s+({re.escape(prefix)}[A-Z0-9_]+)\s+"
        r"(0x[0-9A-Fa-f]+|[0-9]+)[uUlL]*\s*$",
        re.MULTILINE,
    )
    for match in pattern.finditer(text):
        values[match.group(1)] = int(match.group(2), 0)
    return values


def load_control_values() -> dict[str, int]:
    text = CONTROL_HEADER.read_text(encoding="ascii")
    values = load_literal_macros(CONTROL_HEADER, "OTA_P2_2_")
    enum_pattern = re.compile(
        r"^\s*(OTA_P2_2_STATUS_[A-Z0-9_]+)\s*=\s*([0-9]+)\s*,?\s*$",
        re.MULTILINE,
    )
    for match in enum_pattern.finditer(text):
        values[match.group(1)] = int(match.group(2), 10)
    required = {
        "OTA_P2_2_CONTROL_SIZE",
        "OTA_P2_2_PACKAGE_OFFSET",
        "OTA_P2_2_PACKAGE_CAPACITY",
        "OTA_P2_2_COMMAND_MAGIC",
        "OTA_P2_2_DONE_MAGIC",
        "OTA_P2_2_VERSION",
        "OTA_P2_2_OPCODE_APPLY",
        "OTA_P2_2_COOKIE",
        "OTA_P2_2_OFF_MAGIC",
        "OTA_P2_2_OFF_VERSION",
        "OTA_P2_2_OFF_OPCODE",
        "OTA_P2_2_OFF_OPCODE_INVERSE",
        "OTA_P2_2_OFF_COOKIE",
        "OTA_P2_2_OFF_COOKIE_INVERSE",
        "OTA_P2_2_OFF_PACKAGE_LEN",
        "OTA_P2_2_OFF_CURRENT_VCODE",
        "OTA_P2_2_OFF_EXPECTED_RESULT",
        "OTA_P2_2_OFF_PACKAGE_CRC32",
        "OTA_P2_2_OFF_COMMAND_CRC32",
        "OTA_P2_2_COMMAND_CRC_OFFSET",
        "OTA_P2_2_COMMAND_CRC_LENGTH",
        "OTA_P2_2_OFF_STATUS",
        "OTA_P2_2_OFF_ACTUAL_RESULT",
        "OTA_P2_2_OFF_DETAIL",
        "OTA_P2_2_OFF_TARGET_VCODE",
        "OTA_P2_2_OFF_IMAGE_LEN",
        "OTA_P2_2_OFF_WORKSPACE_PEAK",
        "OTA_P2_2_OFF_PAYLOAD_LEN",
        "OTA_P2_2_OFF_PAYLOAD_CRC32",
        "OTA_P2_2_OFF_CANDIDATE_PREPARES",
        "OTA_P2_2_OFF_CANDIDATE_PROGRAMS",
        "OTA_P2_2_OFF_CANDIDATE_BYTES",
        "OTA_P2_2_OFF_STAGING_ERASES",
        "OTA_P2_2_OFF_STAGING_PROGRAMS",
        "OTA_P2_2_OFF_WORKSPACE_ZERO",
        "OTA_P2_2_OFF_CANDIDATE_HEADER_ERASED",
        "OTA_P2_2_OFF_BCB_EQUAL",
        "OTA_P2_2_OFF_ACTUAL_PACKAGE_CRC32",
        "OTA_P2_2_OFF_IMAGE_SHA256",
        "OTA_P2_2_OFF_BCB_BEFORE",
        "OTA_P2_2_OFF_BCB_AFTER",
        "OTA_P2_2_BCB_SNAPSHOT_SIZE",
        "OTA_P2_2_OFF_RESULT_CRC32",
        "OTA_P2_2_RESULT_CRC_OFFSET",
        "OTA_P2_2_RESULT_CRC_LENGTH",
        "OTA_P2_2_STATUS_ARMED",
        "OTA_P2_2_STATUS_PASS",
    }
    missing = sorted(required - values.keys())
    if missing:
        raise ValueError(f"literal P2-2 macros missing: {', '.join(missing)}")
    return values


def load_package_results() -> dict[str, int]:
    text = PACKAGE_HEADER.read_text(encoding="ascii")
    pattern = re.compile(
        r"^\s*(OTA_PACKAGE_(?:OK|ERR_[A-Z0-9_]+))\s*=\s*(-?[0-9]+)\s*,?\s*$",
        re.MULTILINE,
    )
    values = {match.group(1): int(match.group(2)) for match in pattern.finditer(text)}
    required = {
        "OTA_PACKAGE_OK",
        "OTA_PACKAGE_ERR_HEADER_CRC",
        "OTA_PACKAGE_ERR_PAYLOAD_CRC",
        "OTA_PACKAGE_ERR_VERSION",
    }
    missing = sorted(required - values.keys())
    if missing:
        raise ValueError(f"P2-2 result values missing: {', '.join(missing)}")
    return values


def put_u32(block: bytearray, offset: int, value: int) -> None:
    struct.pack_into("<I", block, offset, value & 0xFFFFFFFF)


def get_u32(block: bytes | bytearray, offset: int) -> int:
    return struct.unpack_from("<I", block, offset)[0]


def get_i32(block: bytes | bytearray, offset: int) -> int:
    return struct.unpack_from("<i", block, offset)[0]


def sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def mutate_package(case: str, package: bytes) -> tuple[bytes, int, int]:
    results = load_package_results()
    mutated = bytearray(package)
    target_vcode = get_u32(mutated, 40)

    if case == "success":
        return bytes(mutated), target_vcode - 1, results["OTA_PACKAGE_OK"]
    if case == "bad-header-crc":
        mutated[60] ^= 0x01
        return (
            bytes(mutated),
            target_vcode - 1,
            results["OTA_PACKAGE_ERR_HEADER_CRC"],
        )
    if case == "bad-payload":
        mutated[-1] ^= 0x01
        return (
            bytes(mutated),
            target_vcode - 1,
            results["OTA_PACKAGE_ERR_PAYLOAD_CRC"],
        )
    if case == "equal-version":
        return (
            bytes(mutated),
            target_vcode,
            results["OTA_PACKAGE_ERR_VERSION"],
        )
    raise ValueError(f"unsupported case: {case}")


def build_command(case: str, source_package: bytes) -> tuple[bytearray, dict[str, object]]:
    m = load_control_values()
    package, current_vcode, expected_result = mutate_package(case, source_package)
    if len(package) > m["OTA_P2_2_PACKAGE_CAPACITY"]:
        raise ValueError("package does not fit the P2-2 control block")

    block = bytearray(m["OTA_P2_2_CONTROL_SIZE"])
    put_u32(block, m["OTA_P2_2_OFF_MAGIC"], m["OTA_P2_2_COMMAND_MAGIC"])
    put_u32(block, m["OTA_P2_2_OFF_VERSION"], m["OTA_P2_2_VERSION"])
    opcode = m["OTA_P2_2_OPCODE_APPLY"]
    put_u32(block, m["OTA_P2_2_OFF_OPCODE"], opcode)
    put_u32(block, m["OTA_P2_2_OFF_OPCODE_INVERSE"], ~opcode)
    cookie = m["OTA_P2_2_COOKIE"]
    put_u32(block, m["OTA_P2_2_OFF_COOKIE"], cookie)
    put_u32(block, m["OTA_P2_2_OFF_COOKIE_INVERSE"], ~cookie)
    put_u32(block, m["OTA_P2_2_OFF_PACKAGE_LEN"], len(package))
    put_u32(block, m["OTA_P2_2_OFF_CURRENT_VCODE"], current_vcode)
    put_u32(block, m["OTA_P2_2_OFF_EXPECTED_RESULT"], expected_result)
    put_u32(block, m["OTA_P2_2_OFF_PACKAGE_CRC32"], zlib.crc32(package))
    crc_start = m["OTA_P2_2_COMMAND_CRC_OFFSET"]
    crc_len = m["OTA_P2_2_COMMAND_CRC_LENGTH"]
    put_u32(
        block,
        m["OTA_P2_2_OFF_COMMAND_CRC32"],
        zlib.crc32(block[crc_start : crc_start + crc_len]),
    )
    put_u32(block, m["OTA_P2_2_OFF_STATUS"], m["OTA_P2_2_STATUS_ARMED"])
    package_offset = m["OTA_P2_2_PACKAGE_OFFSET"]
    block[package_offset : package_offset + len(package)] = package
    metadata = {
        "case": case,
        "package_len": len(package),
        "package_crc32": f"0x{zlib.crc32(package):08X}",
        "package_sha256": sha256(package),
        "current_vcode": current_vcode,
        "expected_result": expected_result,
        "target_vcode": get_u32(package, 40),
    }
    return block, metadata


def staged_command(block: bytearray) -> tuple[bytearray, int]:
    m = load_control_values()
    staged = bytearray(block)
    magic = get_u32(staged, m["OTA_P2_2_OFF_MAGIC"])
    put_u32(staged, m["OTA_P2_2_OFF_MAGIC"], 0)
    return staged, magic


def decode_control(block: bytes) -> dict[str, object]:
    m = load_control_values()
    if len(block) != m["OTA_P2_2_CONTROL_SIZE"]:
        raise ValueError(f"control block must be {m['OTA_P2_2_CONTROL_SIZE']} bytes")

    fields: dict[str, object] = {
        "magic": get_u32(block, m["OTA_P2_2_OFF_MAGIC"]),
        "version": get_u32(block, m["OTA_P2_2_OFF_VERSION"]),
        "opcode": get_u32(block, m["OTA_P2_2_OFF_OPCODE"]),
        "opcode_inverse": get_u32(block, m["OTA_P2_2_OFF_OPCODE_INVERSE"]),
        "cookie": get_u32(block, m["OTA_P2_2_OFF_COOKIE"]),
        "cookie_inverse": get_u32(block, m["OTA_P2_2_OFF_COOKIE_INVERSE"]),
        "package_len": get_u32(block, m["OTA_P2_2_OFF_PACKAGE_LEN"]),
        "current_vcode": get_u32(block, m["OTA_P2_2_OFF_CURRENT_VCODE"]),
        "expected_result": get_i32(block, m["OTA_P2_2_OFF_EXPECTED_RESULT"]),
        "package_crc32": get_u32(block, m["OTA_P2_2_OFF_PACKAGE_CRC32"]),
        "command_crc32": get_u32(block, m["OTA_P2_2_OFF_COMMAND_CRC32"]),
        "status": get_u32(block, m["OTA_P2_2_OFF_STATUS"]),
        "actual_result": get_i32(block, m["OTA_P2_2_OFF_ACTUAL_RESULT"]),
        "detail": get_u32(block, m["OTA_P2_2_OFF_DETAIL"]),
        "target_vcode": get_u32(block, m["OTA_P2_2_OFF_TARGET_VCODE"]),
        "image_len": get_u32(block, m["OTA_P2_2_OFF_IMAGE_LEN"]),
        "workspace_peak": get_u32(block, m["OTA_P2_2_OFF_WORKSPACE_PEAK"]),
        "payload_len": get_u32(block, m["OTA_P2_2_OFF_PAYLOAD_LEN"]),
        "payload_crc32": get_u32(block, m["OTA_P2_2_OFF_PAYLOAD_CRC32"]),
        "candidate_prepares": get_u32(block, m["OTA_P2_2_OFF_CANDIDATE_PREPARES"]),
        "candidate_programs": get_u32(block, m["OTA_P2_2_OFF_CANDIDATE_PROGRAMS"]),
        "candidate_bytes": get_u32(block, m["OTA_P2_2_OFF_CANDIDATE_BYTES"]),
        "staging_erases": get_u32(block, m["OTA_P2_2_OFF_STAGING_ERASES"]),
        "staging_programs": get_u32(block, m["OTA_P2_2_OFF_STAGING_PROGRAMS"]),
        "workspace_zero": get_u32(block, m["OTA_P2_2_OFF_WORKSPACE_ZERO"]),
        "candidate_header_erased": get_u32(
            block, m["OTA_P2_2_OFF_CANDIDATE_HEADER_ERASED"]
        ),
        "bcb_equal": get_u32(block, m["OTA_P2_2_OFF_BCB_EQUAL"]),
        "actual_package_crc32": get_u32(
            block, m["OTA_P2_2_OFF_ACTUAL_PACKAGE_CRC32"]
        ),
        "result_crc32": get_u32(block, m["OTA_P2_2_OFF_RESULT_CRC32"]),
    }
    image_sha_offset = m["OTA_P2_2_OFF_IMAGE_SHA256"]
    fields["image_sha256"] = block[image_sha_offset : image_sha_offset + 32].hex()
    package_len = int(fields["package_len"])
    package_offset = m["OTA_P2_2_PACKAGE_OFFSET"]
    package = block[package_offset : package_offset + package_len]
    fields["package_sha256"] = sha256(package)
    fields["package_crc_valid"] = fields["package_crc32"] == zlib.crc32(package)
    command_start = m["OTA_P2_2_COMMAND_CRC_OFFSET"]
    command_len = m["OTA_P2_2_COMMAND_CRC_LENGTH"]
    fields["command_crc_valid"] = fields["command_crc32"] == zlib.crc32(
        block[command_start : command_start + command_len]
    )
    result_start = m["OTA_P2_2_RESULT_CRC_OFFSET"]
    result_len = m["OTA_P2_2_RESULT_CRC_LENGTH"]
    fields["result_crc_valid"] = fields["result_crc32"] == zlib.crc32(
        block[result_start : result_start + result_len]
    )
    fields["command_fields_valid"] = (
        fields["version"] == m["OTA_P2_2_VERSION"]
        and fields["opcode"] == m["OTA_P2_2_OPCODE_APPLY"]
        and (int(fields["opcode"]) ^ int(fields["opcode_inverse"])) == 0xFFFFFFFF
        and fields["cookie"] == m["OTA_P2_2_COOKIE"]
        and (int(fields["cookie"]) ^ int(fields["cookie_inverse"])) == 0xFFFFFFFF
        and fields["command_crc_valid"]
        and fields["package_crc_valid"]
    )
    fields["kind"] = {
        m["OTA_P2_2_COMMAND_MAGIC"]: "command",
        m["OTA_P2_2_DONE_MAGIC"]: "done",
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


def verify_evidence(args: argparse.Namespace) -> dict[str, object]:
    m = load_control_values()
    checks: list[str] = []
    command_raw = args.command.read_bytes()
    command_readback = args.command_readback.read_bytes()
    final_raw = args.final_control.read_bytes()
    header_before = args.candidate_header_before.read_bytes()
    header_after = args.candidate_header_after.read_bytes()
    image_before = args.candidate_image_before.read_bytes()
    image_after = args.candidate_image_after.read_bytes()
    expected_image = args.expected_image.read_bytes()

    require_equal(checks, "magic-last command readback", command_readback, command_raw)
    command = decode_control(command_raw)
    final = decode_control(final_raw)
    require_equal(checks, "command kind", command["kind"], "command")
    require_true(checks, "command fields", command["command_fields_valid"])
    require_equal(checks, "final kind", final["kind"], "done")
    require_true(checks, "final command fields", final["command_fields_valid"])
    require_true(checks, "final result CRC", final["result_crc_valid"])
    require_equal(
        checks,
        "command fields preserved",
        final_raw[m["OTA_P2_2_OFF_VERSION"] : m["OTA_P2_2_OFF_STATUS"]],
        command_raw[m["OTA_P2_2_OFF_VERSION"] : m["OTA_P2_2_OFF_STATUS"]],
    )
    package_offset = m["OTA_P2_2_PACKAGE_OFFSET"]
    package_len = int(command["package_len"])
    require_equal(
        checks,
        "package bytes preserved",
        final_raw[package_offset : package_offset + package_len],
        command_raw[package_offset : package_offset + package_len],
    )
    require_equal(checks, "firmware status", final["status"], m["OTA_P2_2_STATUS_PASS"])
    require_equal(checks, "firmware detail", final["detail"], 0)
    require_equal(checks, "actual result", final["actual_result"], command["expected_result"])
    require_equal(
        checks,
        "actual package CRC",
        final["actual_package_crc32"],
        command["package_crc32"],
    )
    require_equal(checks, "staging erase count", final["staging_erases"], 1)
    require_equal(checks, "staging program count", final["staging_programs"], 1)
    require_equal(checks, "workspace wipe", final["workspace_zero"], 1)
    require_equal(checks, "BCB equality flag", final["bcb_equal"], 1)
    bcb_size = m["OTA_P2_2_BCB_SNAPSHOT_SIZE"]
    bcb_before = final_raw[
        m["OTA_P2_2_OFF_BCB_BEFORE"] : m["OTA_P2_2_OFF_BCB_BEFORE"] + bcb_size
    ]
    bcb_after = final_raw[
        m["OTA_P2_2_OFF_BCB_AFTER"] : m["OTA_P2_2_OFF_BCB_AFTER"] + bcb_size
    ]
    require_equal(checks, "BCB raw bytes unchanged", bcb_after, bcb_before)
    require_equal(checks, "candidate header dump size before", len(header_before), 4096)
    require_equal(checks, "candidate header dump size after", len(header_after), 4096)
    require_equal(checks, "candidate image dump size before", len(image_before), 4096)
    require_equal(checks, "candidate image dump size after", len(image_after), 4096)

    results = load_package_results()
    layout = load_literal_macros(LAYOUT_HEADER, "OTA_")
    if int(command["expected_result"]) == results["OTA_PACKAGE_OK"]:
        require_equal(checks, "candidate prepare count", final["candidate_prepares"], 1)
        require_equal(checks, "candidate program count", final["candidate_programs"], 4)
        require_equal(checks, "candidate programmed bytes", final["candidate_bytes"], 4096)
        require_equal(checks, "candidate header erased flag", final["candidate_header_erased"], 1)
        require_true(checks, "candidate header bytes erased", all(value == 0xFF for value in header_after))
        require_equal(checks, "candidate image exact", image_after, expected_image)
        require_equal(checks, "candidate raw SHA", sha256(image_after), GOLDEN_IMAGE_SHA256)
        require_equal(checks, "target vcode", final["target_vcode"], get_u32(command_raw, package_offset + 40))
        require_equal(checks, "image length", final["image_len"], len(expected_image))
        require_true(
            checks,
            "workspace peak bounded",
            0
            < int(final["workspace_peak"])
            <= layout["OTA_OVERLAY_WORKSPACE_LENGTH"],
        )
        require_equal(checks, "payload length", final["payload_len"], get_u32(command_raw, package_offset + 32))
        require_equal(checks, "payload CRC", final["payload_crc32"], get_u32(command_raw, package_offset + 36))
        header_offset = layout["OTA_FW_HEADER_OFFSET"]
        fw_sha = expected_image[header_offset + 40 : header_offset + 72]
        require_equal(checks, "fw_header double-zero SHA", final["image_sha256"], fw_sha.hex())
    else:
        require_equal(checks, "candidate prepare count", final["candidate_prepares"], 0)
        require_equal(checks, "candidate program count", final["candidate_programs"], 0)
        require_equal(checks, "candidate programmed bytes", final["candidate_bytes"], 0)
        require_equal(checks, "candidate header unchanged", header_after, header_before)
        require_equal(checks, "candidate image unchanged", image_after, image_before)

    args.extract_dir.mkdir(parents=True, exist_ok=True)
    (args.extract_dir / "bcb-before.bin").write_bytes(bcb_before)
    (args.extract_dir / "bcb-after.bin").write_bytes(bcb_after)
    result = {
        "result": "PASS",
        "checks": len(checks),
        "case": args.case,
        "expected_result": command["expected_result"],
        "actual_result": final["actual_result"],
        "package_sha256": command["package_sha256"],
        "candidate_before_sha256": sha256(image_before),
        "candidate_after_sha256": sha256(image_after),
        "bcb_sha256": sha256(bcb_before),
        "workspace_peak": final["workspace_peak"],
        "checks_detail": checks,
    }
    args.output.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    return result


def command_action(args: argparse.Namespace) -> None:
    source = args.package.read_bytes()
    if sha256(source) != GOLDEN_PACKAGE_SHA256:
        raise ValueError("input package is not the frozen toy-full.etu")
    block, metadata = build_command(args.case, source)
    staged, magic = staged_command(block)
    args.output.write_bytes(staged)
    args.committed_output.write_bytes(block)
    args.magic_output.write_text(f"0x{magic:08X}\n", encoding="ascii")
    args.metadata_output.write_text(
        json.dumps(metadata, indent=2) + "\n", encoding="utf-8"
    )
    print(
        f"P2_2_COMMAND=PASS case={args.case} len={metadata['package_len']} "
        f"expected={metadata['expected_result']}"
    )


def selftest_action(args: argparse.Namespace) -> None:
    source = args.package.read_bytes()
    if sha256(source) != GOLDEN_PACKAGE_SHA256:
        raise ValueError("input package is not the frozen toy-full.etu")
    checks = 0
    for case in ("success", "bad-header-crc", "bad-payload", "equal-version"):
        block, metadata = build_command(case, source)
        staged, magic = staged_command(block)
        decoded = decode_control(block)
        if get_u32(staged, 0) != 0 or magic != load_control_values()["OTA_P2_2_COMMAND_MAGIC"]:
            raise ValueError(f"{case}: magic-last staging failed")
        checks += 1
        if not decoded["command_fields_valid"]:
            raise ValueError(f"{case}: command fields invalid")
        checks += 1
        if decoded["package_sha256"] != metadata["package_sha256"]:
            raise ValueError(f"{case}: package identity mismatch")
        checks += 1
        if decoded["expected_result"] != metadata["expected_result"]:
            raise ValueError(f"{case}: expected result mismatch")
        checks += 1
    print(f"P2_2_PROTOCOL=PASS checks={checks}")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    subparsers = parser.add_subparsers(dest="command_name", required=True)

    command_parser = subparsers.add_parser("command")
    command_parser.add_argument(
        "--case",
        required=True,
        choices=("success", "bad-header-crc", "bad-payload", "equal-version"),
    )
    command_parser.add_argument("--package", type=Path, required=True)
    command_parser.add_argument("--output", type=Path, required=True)
    command_parser.add_argument("--committed-output", type=Path, required=True)
    command_parser.add_argument("--magic-output", type=Path, required=True)
    command_parser.add_argument("--metadata-output", type=Path, required=True)
    command_parser.set_defaults(action=command_action)

    verify_parser = subparsers.add_parser("verify")
    verify_parser.add_argument("--case", required=True)
    verify_parser.add_argument("--command", type=Path, required=True)
    verify_parser.add_argument("--command-readback", type=Path, required=True)
    verify_parser.add_argument("--final-control", type=Path, required=True)
    verify_parser.add_argument("--candidate-header-before", type=Path, required=True)
    verify_parser.add_argument("--candidate-header-after", type=Path, required=True)
    verify_parser.add_argument("--candidate-image-before", type=Path, required=True)
    verify_parser.add_argument("--candidate-image-after", type=Path, required=True)
    verify_parser.add_argument("--expected-image", type=Path, required=True)
    verify_parser.add_argument("--extract-dir", type=Path, required=True)
    verify_parser.add_argument("--output", type=Path, required=True)
    verify_parser.set_defaults(action=lambda args: print(
        f"P2_2_VERIFY=PASS case={args.case} checks={verify_evidence(args)['checks']}"
    ))

    selftest_parser = subparsers.add_parser("selftest")
    selftest_parser.add_argument("--package", type=Path, required=True)
    selftest_parser.set_defaults(action=selftest_action)
    return parser


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()
    args.action(args)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
