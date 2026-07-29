#!/usr/bin/env python3
"""Host checks for the P1-6 RAM control-block protocol."""

from __future__ import annotations

import importlib.util
from pathlib import Path
import zlib


ROOT = Path(__file__).resolve().parents[2]
TOOL_PATH = ROOT / "Tools/jlink/p1_6_protocol.py"
SPEC = importlib.util.spec_from_file_location("p1_6_protocol", TOOL_PATH)
assert SPEC and SPEC.loader
TOOL = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(TOOL)


def main() -> int:
    m = TOOL.load_macros()
    command = TOOL.build_command(5, (1, 64, 2, 3))
    assert len(command) == 512
    assert TOOL.get_u32(command, m["OTA_P1_6_OFF_MAGIC"]) == m["OTA_P1_6_COMMAND_MAGIC"]
    assert TOOL.get_u32(command, m["OTA_P1_6_OFF_OPCODE_INVERSE"]) == 0xFFFFFFFA
    assert TOOL.get_u32(command, m["OTA_P1_6_OFF_COOKIE_INVERSE"]) == (~m["OTA_P1_6_COOKIE"] & 0xFFFFFFFF)
    assert TOOL.get_u32(command, m["OTA_P1_6_OFF_COMMAND_CRC32"]) == zlib.crc32(command[:40])

    staged_command, command_magic = TOOL.staged_payload(command)
    assert TOOL.get_u32(staged_command, 0) == 0
    assert command_magic == m["OTA_P1_6_COMMAND_MAGIC"]
    decoded_command = TOOL.decode(bytes(command))
    assert decoded_command["kind"] == "command"
    assert decoded_command["command_valid"] is True
    assert decoded_command["opcode_inverse_valid"] is True
    assert decoded_command["cookie_inverse_valid"] is True

    arm = TOOL.build_arm(6, 1, 65)
    assert TOOL.get_u32(arm, m["OTA_P1_6_OFF_MAGIC"]) == m["OTA_P1_6_ARM_MAGIC"]
    start = m["OTA_P1_6_OFF_TARGET_CHECKPOINT"]
    assert TOOL.get_u32(arm, m["OTA_P1_6_OFF_TARGET_CRC32"]) == zlib.crc32(arm[start:start + 12])
    damaged = bytearray(arm)
    damaged[m["OTA_P1_6_OFF_TARGET_ARG0"]] ^= 1
    assert TOOL.get_u32(damaged, m["OTA_P1_6_OFF_TARGET_CRC32"]) != zlib.crc32(damaged[start:start + 12])
    decoded_arm = TOOL.decode(bytes(arm))
    assert decoded_arm["kind"] == "arm"
    assert decoded_arm["arm_valid"] is True
    assert decoded_arm["target_crc_valid"] is True
    assert TOOL.decode(bytes(damaged))["arm_valid"] is False

    result = bytearray(arm)
    TOOL.put_u32(result, m["OTA_P1_6_OFF_MAGIC"], m["OTA_P1_6_DONE_MAGIC"])
    TOOL.put_u32(result, m["OTA_P1_6_OFF_STATUS"], 2)
    crc_start = m["OTA_P1_6_RESULT_CRC_OFFSET"]
    crc_length = m["OTA_P1_6_RESULT_CRC_LENGTH"]
    TOOL.put_u32(result, m["OTA_P1_6_OFF_RESULT_CRC32"], zlib.crc32(result[crc_start:crc_start + crc_length]))
    decoded = TOOL.decode(bytes(result))
    assert decoded["done"] is True
    assert decoded["result_crc_valid"] is True
    result[100] ^= 1
    assert TOOL.decode(bytes(result))["result_crc_valid"] is False

    print("P1_6_PROTOCOL=PASS checks=21 failures=0")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
