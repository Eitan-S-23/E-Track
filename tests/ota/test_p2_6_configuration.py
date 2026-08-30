#!/usr/bin/env python3
"""Validate P2-6 CMake configuration boundaries and mutual exclusion."""

from __future__ import annotations

import os
from pathlib import Path
import re
import subprocess


ROOT = Path(__file__).resolve().parents[2]
SOURCE = ROOT / "MDK-ARM_F435/cmake-generated"
OUT = ROOT / ".cache" / "p2-6-config-matrix"
TMP = ROOT / ".cache" / "p2-6-test-tmp"


def env() -> dict[str, str]:
    result = os.environ.copy()
    for key in ("TEMP", "TMP", "TMPDIR"):
        result[key] = str(TMP)
    result["PIP_CACHE_DIR"] = str(ROOT / ".cache" / "p2-6-tool-cache")
    result["PYTHONPYCACHEPREFIX"] = str(ROOT / ".cache" / "p2-6-pycache")
    result["SOURCE_DATE_EPOCH"] = "1786320000"
    return result


def configure(name: str, options: dict[str, str]) -> tuple[int, str, Path]:
    build = OUT / name
    command = [
        "cmake", "-S", str(SOURCE), "-B", str(build), "-G", "Ninja",
        "-DCMAKE_BUILD_TYPE=Release", "-DCMAKE_OBJECT_PATH_MAX=1024",
        "-DCMAKE_EXPORT_COMPILE_COMMANDS=ON",
    ] + [f"-D{key}={value}" for key, value in options.items()]
    completed = subprocess.run(command, cwd=ROOT, env=env(),
                               capture_output=True, text=True)
    log = OUT / f"{name}.log"
    log.parent.mkdir(parents=True, exist_ok=True)
    log.write_text(completed.stdout + completed.stderr, encoding="utf-8")
    return completed.returncode, completed.stdout + completed.stderr, build


def main() -> int:
    OUT.mkdir(parents=True, exist_ok=True)
    TMP.mkdir(parents=True, exist_ok=True)
    failures: list[str] = []

    rc, output, production = configure("production", {})
    if rc != 0:
        failures.append(f"production configure rc={rc}")
    rc, output, test_build = configure("p2-6", {"P2_6_TEST_ENABLE": "ON"})
    if rc != 0:
        failures.append(f"P2-6 configure rc={rc}")

    compile_commands = test_build / "compile_commands.json"
    if compile_commands.exists():
        text = compile_commands.read_text(encoding="utf-8")
        if "P2_6_TEST_ENABLE" not in text:
            failures.append("P2-6 compile_commands lacks P2_6_TEST_ENABLE")
        if "OTA_P2_6_HOST_ARENA_CAPACITY_OVERRIDE" in text:
            failures.append("host capacity override leaked into P2-6 firmware compile")
    else:
        failures.append("P2-6 compile_commands.json missing")

    prod_commands = production / "compile_commands.json"
    if prod_commands.exists():
        text = prod_commands.read_text(encoding="utf-8")
        if "P2_6_TEST_ENABLE" in text or "OTA_P2_6_HOST_ARENA_CAPACITY_OVERRIDE" in text:
            failures.append("production compile_commands contains test-only macro")
    else:
        failures.append("production compile_commands.json missing")

    for option in ("P1_6_TEST_ENABLE", "P2_1_TEST_ENABLE",
                   "P2_2_TEST_ENABLE", "P2_3_TEST_ENABLE"):
        rc, output, _ = configure(
            "pair-" + option.lower(),
            {option: "ON", "P2_6_TEST_ENABLE": "ON"},
        )
        label = option.split("_TEST_ENABLE", 1)[0].replace("_", "-")
        expected = f"{label} and P2-6"
        if rc == 0 or expected not in output:
            failures.append(
                f"{option}+P2_6 expected mutual exclusion rc=1/message={expected!r}, "
                f"got rc={rc}")
        else:
            print(f"[PASS] {option}+P2_6 rejected with frozen mutual exclusion")

    if failures:
        for failure in failures:
            print("[FAIL] " + failure)
        print("P2_6_CONFIGURATION=FAIL")
        return 1
    print("[PASS] production configure rc=0")
    print("[PASS] P2-6 configure rc=0 and compile definition present")
    print("[PASS] production compile definition and host override absent")
    print("P2_6_CONFIGURATION=PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
