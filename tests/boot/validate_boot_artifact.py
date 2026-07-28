#!/usr/bin/env python3
"""Validate the P1-1 Boot linker layout, size, symbols, and redline sources."""

from __future__ import annotations

import argparse
import re
import struct
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]


def parse_macro(layout_text: str, name: str) -> int:
    match = re.search(
        rf"(?m)^\s*#define\s+{re.escape(name)}\s+(0x[0-9A-Fa-f]+|[0-9]+)\b",
        layout_text,
    )
    if not match:
        raise SystemExit(f"Boot layout macro missing: {name}")
    return int(match.group(1), 0)


def map_pair(map_text: str, name: str, suffix: str) -> tuple[int, int]:
    match = re.search(
        rf"(?m)^{re.escape(name)}\s+(0x[0-9A-Fa-f]+)\s+"
        rf"(0x[0-9A-Fa-f]+){suffix}",
        map_text,
    )
    if not match:
        raise SystemExit(f"Boot map entry missing: {name}")
    return tuple(int(value, 16) for value in match.groups())


def validate(build_dir: Path) -> None:
    layout_text = (ROOT / "Libraries/OTA/ota_layout.h").read_text(encoding="ascii")
    boot_origin = parse_macro(layout_text, "OTA_BOOT_ORIGIN")
    boot_length = parse_macro(layout_text, "OTA_BOOT_LENGTH")
    vector_max = parse_macro(layout_text, "OTA_VECTOR_MAX")
    ram_origin = parse_macro(layout_text, "OTA_RAM_ORIGIN")
    ram_length = parse_macro(layout_text, "OTA_RAM_LENGTH")
    overlay_origin = parse_macro(layout_text, "OTA_OVERLAY_ORIGIN")
    overlay_length = parse_macro(layout_text, "OTA_OVERLAY_LENGTH")

    output_dir = build_dir / "boot"
    map_text = (output_dir / "X-Track-Boot.map").read_text(
        encoding="utf-8", errors="replace"
    )
    linker_text = (output_dir / "x-track-boot-gcc.ld").read_text(
        encoding="utf-8", errors="strict"
    )
    raw_bin = (output_dir / "X-Track-Boot.bin").read_bytes()

    if map_pair(map_text, "FLASH", r"\s+") != (boot_origin, boot_length):
        raise SystemExit("P1-1: Boot FLASH region mismatch")
    if map_pair(map_text, "RAM", r"\s+") != (ram_origin, ram_length):
        raise SystemExit("P1-1: Boot RAM region mismatch")
    if map_pair(map_text, "OTA_CMD", r"\s+") != (
        overlay_origin,
        overlay_length,
    ):
        raise SystemExit("P1-5: Boot bootstrap overlay region mismatch")
    vector = map_pair(map_text, ".isr_vector", "")
    if vector[0] != boot_origin or vector[1] > vector_max:
        raise SystemExit("P1-1: Boot vector placement/size mismatch")
    if not raw_bin or len(raw_bin) > boot_length:
        raise SystemExit("P1-1: boot.bin exceeds 64 KiB")

    initial_msp, reset_handler = struct.unpack_from("<II", raw_bin, 0)
    if not (ram_origin <= initial_msp <= ram_origin + ram_length):
        raise SystemExit("P1-1: Boot initial MSP is outside main RAM")
    if (reset_handler & 1) == 0 or not (
        boot_origin <= (reset_handler & ~1) < boot_origin + boot_length
    ):
        raise SystemExit("P1-1: Boot Reset_Handler is outside Boot flash")

    required_symbols = (
        "boot_fw_header_validate",
        "bcb_arbiter",
        "boot_ymodem_receive",
        "boot_platform_qspi_read",
        "boot_platform_qspi_erase_4k",
        "boot_platform_qspi_program",
        "boot_platform_flash_program",
        "boot_platform_recovery_key_held",
        "boot_bootstrap_process",
    )
    missing = [symbol for symbol in required_symbols if symbol not in map_text]
    if missing:
        raise SystemExit(f"P1-1: required Boot symbols missing: {missing}")

    bootstrap_section = re.search(
        r"(?m)^\.boot_bootstrap_noinit\s*\n\s*"
        r"(0x[0-9A-Fa-f]+)\s+(0x[0-9A-Fa-f]+)",
        map_text,
    )
    bootstrap_symbol = re.search(
        r"(?m)^\s*(0x[0-9A-Fa-f]+)\s+g_boot_bootstrap_command\s*$",
        map_text,
    )
    if not bootstrap_section or tuple(
        int(value, 16) for value in bootstrap_section.groups()
    ) != (overlay_origin, 128):
        raise SystemExit("P1-5: bootstrap command section placement drifted")
    if not bootstrap_symbol or int(bootstrap_symbol.group(1), 16) != overlay_origin:
        raise SystemExit("P1-5: bootstrap command symbol placement drifted")

    cmake_text = (ROOT / "MDK-ARM_F435/cmake-generated/CMakeLists.txt").read_text(
        encoding="utf-8"
    )
    source_block = re.search(
        r"set\(BOOT_PROJECT_SOURCES(?P<body>.*?)\n\)", cmake_text, re.S
    )
    if not source_block:
        raise SystemExit("P1-1: BOOT_PROJECT_SOURCES is not explicit")
    include_block = re.search(
        r"target_include_directories\(X_Track_Boot PRIVATE(?P<body>.*?)\n\)",
        cmake_text,
        re.S,
    )
    if not include_block:
        raise SystemExit("P1-1: Boot include set is not isolated")
    definition_block = re.search(
        r"target_compile_definitions\(X_Track_Boot PRIVATE(?P<body>.*?)\n\)",
        cmake_text,
        re.S,
    )
    if not definition_block or "OTA_TARGET_BOOT" not in definition_block.group("body"):
        raise SystemExit("P1-1: Boot target identity macro is missing")
    forbidden = ("lzma", "bspatch", "bluetooth", "tinybt", "aes")
    found_sources = [
        token for token in forbidden if token in source_block.group("body").lower()
    ]
    found_symbols = [
        token for token in forbidden
        if re.search(rf"(?i)(?<![a-z]){re.escape(token)}(?![a-z])", map_text)
    ]
    if found_sources or found_symbols:
        raise SystemExit(
            "P1-1: forbidden Boot dependency: "
            f"sources={found_sources}, linked={found_symbols}"
        )
    forbidden_includes = ("ArduinoAPI", "USER/App", "Bluetooth", "SdFat", "segger_rtt")
    inherited = [
        token for token in forbidden_includes if token in include_block.group("body")
    ]
    if inherited:
        raise SystemExit(f"P1-1: Boot inherited App include paths: {inherited}")
    inherited_definitions = [
        token for token in ("ARDUINO", "LIBRARY_VERSION", "OTA_TARGET_APP")
        if token in definition_block.group("body")
    ]
    if inherited_definitions:
        raise SystemExit(
            f"P1-1: Boot inherited App compile definitions: {inherited_definitions}"
        )

    workflow_text = (ROOT / ".github/workflows/firmware-build.yml").read_text(
        encoding="utf-8"
    )
    for path_filter in ('"boot/**"', '"cmake/**"', '"tests/boot/**"'):
        if workflow_text.count(path_filter) != 2:
            raise SystemExit(f"P1-1: CI path filter is incomplete: {path_filter}")
    firmware_upload = re.search(
        r"(?ms)^      - name: Upload firmware artifact\n(?P<body>.*?)"
        r"(?=^      - name: )",
        workflow_text,
    )
    boot_upload = re.search(
        r"(?ms)^      - name: Upload Boot artifact\n(?P<body>.*?)"
        r"(?=^  [a-zA-Z0-9_-]+:|^      - name: )",
        workflow_text,
    )
    if not firmware_upload or "/boot/" in firmware_upload.group("body"):
        raise SystemExit("P1-1: App release artifact must not change its archive root")
    if not boot_upload or boot_upload.group("body").count("/boot/X-Track-Boot.") != 4:
        raise SystemExit("P1-1: isolated Boot artifact upload is incomplete")

    linker_memory = re.search(
        r"FLASH\s+\(rx\)\s*:\s*ORIGIN\s*=\s*(0x[0-9A-Fa-f]+)\s*,\s*"
        r"LENGTH\s*=\s*(0x[0-9A-Fa-f]+)",
        linker_text,
    )
    if not linker_memory or tuple(int(value, 16) for value in linker_memory.groups()) != (
        boot_origin,
        boot_length,
    ):
        raise SystemExit("P1-1: preprocessed Boot linker MEMORY mismatch")

    print(
        "P1_1_BOOT_ASSERTIONS=PASS "
        f"bin={len(raw_bin)} vector={vector[0]:#010x}/{vector[1]:#x} "
        f"msp={initial_msp:#010x} reset={reset_handler:#010x}"
    )


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--build-dir", required=True, type=Path)
    args = parser.parse_args()
    validate(args.build_dir.resolve())
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
