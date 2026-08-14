#!/usr/bin/env python3
"""Guard the SDIO command-response waits against unbounded MCU spins."""

from __future__ import annotations

from pathlib import Path
import re


ROOT = Path(__file__).resolve().parents[2]
SOURCE = ROOT / "MDK-ARM_F435/Platform/Core/at32_sdio.c"
FUNCTIONS = (
    "command_error",
    "command_rsp7_error",
    "command_rsp1_error",
    "command_rsp3_error",
    "command_rsp2_error",
    "command_rsp4_error",
    "command_rsp5_error",
    "command_rsp6_error",
    "check_card_programming",
)


def function_body(source: str, name: str) -> str:
    match = re.search(rf"\b{re.escape(name)}\s*\([^;]*?\)\s*\{{", source, re.S)
    if match is None:
        raise AssertionError(f"function not found: {name}")

    start = match.end() - 1
    depth = 0
    for index in range(start, len(source)):
        char = source[index]
        if char == "{":
            depth += 1
        elif char == "}":
            depth -= 1
            if depth == 0:
                return source[start + 1:index]
    raise AssertionError(f"unterminated function body: {name}")


def main() -> int:
    source = SOURCE.read_text(encoding="utf-8")
    for name in FUNCTIONS:
        body = function_body(source, name)
        assert "uint32_t timeout = SDIO_CMD0TIMEOUT;" in body, name
        assert re.search(r"while\s*\(\s*timeout\s*>\s*0\s*\)", body), name
        assert re.search(r"\btimeout\s*--;", body), name
        assert "SD_CMD_RSP_TIMEOUT" in body, name
        assert not re.search(r"while\s*\(\s*1\s*\)", body), name
        assert not re.search(r"while\s*\(\s*timeout\s*--\s*\)", body), name

    assert not re.search(r"while\s*\(\s*timeout\s*--\s*\)", source)
    print(f"SDIO_COMMAND_TIMEOUTS=PASS functions={len(FUNCTIONS)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
