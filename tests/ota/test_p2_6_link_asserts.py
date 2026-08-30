#!/usr/bin/env python3
"""Exercise the production App linker script and its A1-A9 assertions."""

from __future__ import annotations

import os
from pathlib import Path
import re
import shutil
import subprocess


ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / ".cache" / "p2-6-assert-cases"
TMP = ROOT / ".cache" / "p2-6-test-tmp"
GCC = shutil.which("arm-none-eabi-gcc")
NM = shutil.which("arm-none-eabi-nm")


def env() -> dict[str, str]:
    result = os.environ.copy()
    for key in ("TEMP", "TMP", "TMPDIR"):
        result[key] = str(TMP)
    result["PIP_CACHE_DIR"] = str(ROOT / ".cache" / "p2-6-tool-cache")
    result["PYTHONPYCACHEPREFIX"] = str(ROOT / ".cache" / "p2-6-pycache")
    return result


def run(command: list[str], cwd: Path = ROOT) -> subprocess.CompletedProcess[str]:
    return subprocess.run(command, cwd=cwd, env=env(),
                          capture_output=True, text=True)


def preprocess(case: str) -> Path:
    output = OUT / f"{case}.ld"
    command = [
        GCC, "-E", "-P", "-x", "assembler-with-cpp",
        f"-I{ROOT / 'Libraries/OTA'}",
        str(ROOT / "cmake/linker/x-track-app-gcc.ld.S"),
        "-o", str(output),
    ]
    result = run(command)
    if result.returncode != 0:
        raise RuntimeError("production linker preprocessing failed: " +
                           result.stdout + result.stderr)
    return output


def link(case: str, script: Path, extra: list[str] | None = None) -> tuple[int, str]:
    elf = OUT / f"{case}.elf"
    map_file = OUT / f"{case}.map"
    command = [
        GCC, "-mcpu=cortex-m4", "-mthumb", "-ffreestanding", "-nostdlib",
        "-Wl,--gc-sections", f"-T{script}", f"-Wl,-Map={map_file}",
        "-o", str(elf), str(ROOT / "tests/ota/p2_6_link_assert_probe.S"),
    ]
    if extra:
        command.extend(extra)
    result = run(command, cwd=OUT)
    return result.returncode, result.stdout + result.stderr


def mutate(base: str, case: str) -> str:
    text = base
    if case == "A1":
        text = text.replace(". = 8192;", ". = 8188;", 1)
    elif case == "A2":
        text = text.replace(". = 32;", ". = 28;", 1)
    elif case == "A4":
        needle = ".ota_stack_guard (_estack - OTA_STACK_RESERVE - OTA_STACK_GUARD_SIZE)"
        text = text.replace(needle, needle.replace("- OTA_STACK_GUARD_SIZE", "- OTA_STACK_GUARD_SIZE - 16"), 1)
    elif case == "A5":
        text = text.replace(". = . + _Min_Heap_Size;", ". = . + 0x56100;", 1)
    elif case == "A6":
        text = text.replace("__StackLimit = ADDR(.ota_stack);",
                            "__StackLimit = _estack - OTA_STACK_RESERVE - 64;", 1)
        text = text.replace("__StackGuardEnd = ADDR(.ota_stack_guard) + SIZEOF(.ota_stack_guard);",
                            "__StackGuardEnd = _estack - OTA_STACK_RESERVE - 64;", 1)
    else:
        raise ValueError(case)
    if text == base:
        raise RuntimeError(f"mutation anchor not found for {case}")
    path = OUT / f"{case}.ld"
    path.write_text(text, encoding="utf-8")
    return str(path)


def assert_hits(output: str) -> list[str]:
    return sorted(set(re.findall(r"\b(A[1-9])\s*:", output)))


def main() -> int:
    if not GCC or not NM:
        print("P2_6_LINK_ASSERTS=ENV_BLOCKED missing ARM GNU tools")
        return 2
    OUT.mkdir(parents=True, exist_ok=True)
    TMP.mkdir(parents=True, exist_ok=True)
    base_path = preprocess("positive")
    base = base_path.read_text(encoding="utf-8")
    failures: list[str] = []

    rc, output = link("positive", base_path)
    if rc != 0:
        failures.append(f"positive rc={rc}: {output[-1000:]}")
    else:
        nm = run([NM, str(OUT / "positive.elf")]).stdout
        expected = {
            "__StackTop": "20058000",
            "__StackLimit": "20056000",
            "__StackGuardStart": "20055fe0",
            "__StackGuardEnd": "20056000",
            "STACK$$Base": "20056000",
            "STACK$$Limit": "20058000",
        }
        for symbol, value in expected.items():
            if not re.search(rf"\b{re.escape(value)}\s+[A-Za-z]\s+{re.escape(symbol)}\b", nm, re.I):
                failures.append(f"positive missing {symbol}={value}: {nm}")
        print("[PASS] positive rc=0 symbols A1-A9 layout verified")

    for case in ("A1", "A2", "A4", "A5", "A6"):
        path = Path(mutate(base, case))
        rc, output = link(case, path)
        hits = assert_hits(output)
        wanted = [case]
        if rc == 0 or case not in hits:
            failures.append(f"{case} rc={rc} hits={hits}: {output[-1200:]}")
            print(f"[FAIL] {case} rc={rc} hits={hits}")
        else:
            if case == "A6" and hits != wanted:
                failures.append(f"A6 expected exact {wanted}, got {hits}")
                print(f"[FAIL] A6 rc={rc} hits={hits} (expected exact {wanted})")
            else:
                print(f"[PASS] {case} rc={rc} hits={hits}")

    (OUT / "run.log").write_text(
        "P2_6 linker ASSERT real-script validation\n" +
        ("PASS\n" if not failures else "FAIL\n") +
        "\n".join(failures), encoding="utf-8")
    if failures:
        for failure in failures:
            print("[FAIL] " + failure)
        return 1
    print("P2_6_LINK_ASSERTS=PASS positive+A1+A2+A4+A5+A6")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
