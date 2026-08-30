#!/usr/bin/env python3
"""Lock the SDIO timeout-recovery boundary to an acyclic call structure."""

from __future__ import annotations

from pathlib import Path
import re


ROOT = Path(__file__).resolve().parents[2]
SOURCE = ROOT / "MDK-ARM_F435/Platform/Core/at32_sdio.c"
CMAKE = ROOT / "MDK-ARM_F435/cmake-generated/CMakeLists.txt"

OUTER_TRANSFERS = (
    "sd_block_read",
    "sd_mult_blocks_read",
    "sd_block_write",
    "sd_mult_blocks_write",
    "mmc_stream_read",
    "mmc_stream_write",
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
    helper = function_body(source, "sdio_transfer_recover_timeout")
    primitive = function_body(source, "sdio_command_data_send")
    switch = function_body(source, "sd_switch")

    assert helper.count("sd_init(") == 1
    assert "status == SD_DATA_TIMEOUT" in helper
    assert "sd_init(" not in primitive
    assert "sdio_transfer_recover_timeout(" not in switch
    assert switch.count("sdio_command_data_send(") == 1

    for name in OUTER_TRANSFERS:
        body = function_body(source, name)
        assert body.count("sdio_transfer_recover_timeout(") == 1, name
        assert body.count("sdio_command_data_send(") == 1, name

    assert source.count("sdio_command_data_send(") == len(OUTER_TRANSFERS) + 2

    cmake = CMAKE.read_text(encoding="utf-8")
    match = re.search(
        r"if\(P2_6_TEST_ENABLE\)\s*"
        r"target_link_options\(X_Track_App_GCC PRIVATE(?P<body>.*?)\n\s*\)\s*"
        r"endif\(\)",
        cmake,
        re.S,
    )
    assert match is not None
    link_body = match.group("body")
    assert "--undefined=P2_6_StartupStackScanProbe" in link_body

    stack_usage = re.findall(
        r"target_compile_options\(X_Track_App_GCC PRIVATE -fstack-usage\)",
        cmake,
    )
    assert len(stack_usage) == 1
    compile_guard = re.search(
        r"if\(P2_6_TEST_ENABLE\)\s*"
        r"target_compile_definitions\(X_Track_App_GCC PRIVATE "
        r"\"P2_6_TEST_ENABLE=1\"\)\s*endif\(\)",
        cmake,
        re.S,
    )
    assert compile_guard is not None
    assert "-fstack-usage" not in compile_guard.group(0)
    assert "P2_6_TEST_ENABLE" not in cmake.split("set(OTA_TEST_LINKER_DEFINES)", 1)[1].split(
        "add_custom_command", 1
    )[0]

    print(
        "SDIO_RECOVERY_BOUNDED=PASS "
        f"outer_transfers={len(OUTER_TRANSFERS)} raw_calls={len(OUTER_TRANSFERS) + 2}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
