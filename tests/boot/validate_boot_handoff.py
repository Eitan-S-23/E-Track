#!/usr/bin/env python3
"""Validate the frozen P1-4 Boot-to-App handoff sequence and branch stub."""

from __future__ import annotations

import argparse
from pathlib import Path
import re
import shutil
import subprocess


ROOT = Path(__file__).resolve().parents[2]


def find_objdump(build_dir: Path, explicit: Path | None) -> Path:
    if explicit is not None:
        return explicit.resolve()

    found = shutil.which("arm-none-eabi-objdump")
    if found:
        return Path(found)

    cache = (build_dir / "CMakeCache.txt").read_text(
        encoding="utf-8", errors="replace"
    )
    compiler = re.search(r"(?m)^CMAKE_C_COMPILER:FILEPATH=(.+)$", cache)
    if compiler:
        suffix = ".exe" if compiler.group(1).lower().endswith(".exe") else ""
        candidate = Path(compiler.group(1)).with_name(
            f"arm-none-eabi-objdump{suffix}"
        )
        if candidate.exists():
            return candidate
    raise SystemExit("P1-4: arm-none-eabi-objdump not found")


def function_body(disassembly: str, name: str) -> str:
    match = re.search(
        rf"(?ms)^[0-9a-f]+ <{re.escape(name)}>:\n(?P<body>.*?)"
        r"(?=^[0-9a-f]+ <|\Z)",
        disassembly,
    )
    if not match:
        raise SystemExit(f"P1-4: disassembly symbol missing: {name}")
    return match.group("body")


def validate(build_dir: Path, objdump: Path | None) -> None:
    source = (ROOT / "boot/platform/at32/boot_handoff_at32.c").read_text(
        encoding="ascii"
    )
    handoff = source[source.index("void boot_handoff_to_app(void)"):]
    compact = re.sub(r"\s+", " ", handoff)

    if "BOOT_NVIC_BANK_COUNT = 8" not in source:
        raise SystemExit("P1-4: NVIC bank count is not exactly eight")
    if ("__disable_irq" in handoff or "cpsid" in handoff.lower() or
            "__set_PRIMASK(1u)" in handoff):
        raise SystemExit("P1-4: handoff must not depend on PRIMASK masking")

    icer = compact.find("NVIC->ICER[index] = UINT32_MAX")
    icpr = compact.find("NVIC->ICPR[index] = UINT32_MAX")
    if icer < 0 or icpr < 0 or icer >= icpr:
        raise SystemExit("P1-4: all ICER banks must be cleared before ICPR")

    required_order = (
        "validate_app(&header)",
        "NVIC->ICER[index] = UINT32_MAX",
        "NVIC->ICPR[index] = UINT32_MAX",
        "SysTick->CTRL = 0u",
        "SysTick->LOAD = 0u",
        "SysTick->VAL = 0u",
        "SCB->ICSR = SCB_ICSR_PENDSTCLR_Msk | SCB_ICSR_PENDSVCLR_Msk",
        "__set_PRIMASK(0u)",
        "__set_BASEPRI(0u)",
        "__set_FAULTMASK(0u)",
        "__set_CONTROL(0u)",
        "SCB->VTOR = OTA_APP_ORIGIN",
        "__DSB()",
        "__ISB()",
        "initial_msp = *(const volatile uint32_t *)(uintptr_t)OTA_APP_ORIGIN",
        "reset_handler = *(const volatile uint32_t *)(uintptr_t)(OTA_APP_ORIGIN + 4u)",
        "boot_branch_to_app(initial_msp, reset_handler)",
    )
    position = -1
    for token in required_order:
        next_position = compact.find(token, position + 1)
        if next_position < 0:
            raise SystemExit(f"P1-4: handoff step missing/out of order: {token}")
        position = next_position

    map_text = (build_dir / "boot/X-Track-Boot.map").read_text(
        encoding="utf-8", errors="replace"
    )
    for symbol in (
        "boot_handoff_to_app",
        "boot_fw_header_validate",
        "boot_platform_watchdog_start",
    ):
        if symbol not in map_text:
            raise SystemExit(f"P1-4: linked symbol missing: {symbol}")

    app_map = (build_dir / "app-gcc/X-Track-App-GCC.map").read_text(
        encoding="utf-8", errors="replace"
    )
    for symbol in (
        "ota_handoff_capture",
        "ota_handoff_report",
        "g_ota_handoff_primask",
        "g_ota_handoff_ispr_or",
    ):
        if symbol not in app_map:
            raise SystemExit(f"P1-4: App evidence symbol missing: {symbol}")

    objdump_path = find_objdump(build_dir, objdump)
    elf = build_dir / "boot/X-Track-Boot.elf"
    result = subprocess.run(
        [str(objdump_path), "-d", str(elf)],
        check=True,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
    )
    branch = function_body(result.stdout, "boot_branch_to_app").lower()
    handoff_asm = function_body(result.stdout, "boot_handoff_to_app").lower()
    for pattern in (r"\bmsr\s+msp,\s*r0", r"\bdsb\b", r"\bisb\b", r"\bbx\s+r1"):
        if not re.search(pattern, branch):
            raise SystemExit(f"P1-4: final branch instruction missing: {pattern}")
    if "cpsid" in handoff_asm:
        raise SystemExit("P1-4: compiled handoff disables PRIMASK")

    print(
        "P1_4_BOOT_HANDOFF_ASSERTIONS=PASS "
        "nvic_banks=8 primask=0 basepri=0 faultmask=0 control=0 "
        "vtor=0x08010000 branch=MSP/DSB/ISB/BX"
    )


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--build-dir", required=True, type=Path)
    parser.add_argument("--objdump", type=Path)
    args = parser.parse_args()
    validate(args.build_dir.resolve(), args.objdump)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
