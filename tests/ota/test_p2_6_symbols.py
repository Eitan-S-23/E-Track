#!/usr/bin/env python3
"""Validate the frozen P2-6 L1/L2/L3 configuration and symbol boundaries."""

from __future__ import annotations

import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import unittest


ROOT = Path(__file__).resolve().parents[2]


def select_build(env_name: str, candidates: tuple[str, ...]) -> Path:
    configured = os.environ.get(env_name)
    if configured:
        path = Path(configured).resolve()
        try:
            path.relative_to(ROOT.resolve())
        except ValueError as exc:
            raise RuntimeError(
                f"{env_name} must point inside the repository: {path}"
            ) from exc
        return path
    for candidate in candidates:
        path = ROOT / ".cache" / candidate
        if path.exists():
            return path
    return ROOT / ".cache" / candidates[0]


def select_output(env_name: str, default: Path) -> Path:
    configured = os.environ.get(env_name)
    path = Path(configured).resolve() if configured else default.resolve()
    try:
        path.relative_to(ROOT.resolve())
    except ValueError as exc:
        raise RuntimeError(
            f"{env_name} must point inside the repository: {path}"
        ) from exc
    return path


# Keep symbol checks aligned with the stack-closure and RTT driver frozen
# artifacts.  The older final-r2 builds predate StartupStackScanProbe.
PROD = select_build(
    "P2_6_PROD_STACK_BUILD",
    (
        "p2-6a-cmake-prod-stack",
        "p2-6-cmake-prod-stack-final",
        "p2-6-cmake-prod-stack-r2",
    ),
)
TEST = select_build(
    "P2_6_TEST_STACK_BUILD",
    (
        "p2-6a-cmake-test-stack",
        "p2-6-cmake-test-stack-final",
        "p2-6-cmake-test-stack-r2",
    ),
)
OUT = select_output("P2_6_SYMBOL_OUT", ROOT / ".cache" / "p2-6-symbol-scan")
TMP = select_output("P2_6_TEST_TMP", ROOT / ".cache" / "p2-6-test-tmp")
NM = shutil.which("arm-none-eabi-nm")
OBJDUMP = shutil.which("arm-none-eabi-objdump")
STRINGS = shutil.which("arm-none-eabi-strings")


def run(command: list[str]) -> str:
    environment = os.environ.copy()
    environment["TEMP"] = str(TMP)
    environment["TMP"] = str(TMP)
    environment["TMPDIR"] = str(TMP)
    environment["PIP_CACHE_DIR"] = str(ROOT / ".cache" / "p2-6-tool-cache")
    environment["PYTHONPYCACHEPREFIX"] = str(ROOT / ".cache" / "p2-6-pycache")
    result = subprocess.run(command, cwd=ROOT, env=environment,
                            check=True, capture_output=True, text=True)
    return result.stdout + result.stderr


def read(path: Path) -> str:
    return path.read_text(encoding="utf-8")


class P2SixSymbolTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        if not NM or not OBJDUMP or not STRINGS:
            raise unittest.SkipTest("ARM binutils are unavailable")
        OUT.mkdir(parents=True, exist_ok=True)
        TMP.mkdir(parents=True, exist_ok=True)
        cls.prod_elf = PROD / "app-gcc" / "X-Track-App-GCC.elf"
        cls.test_elf = TEST / "app-gcc" / "X-Track-App-GCC.elf"
        cls.prod_map = PROD / "app-gcc" / "X-Track-App-GCC.map"
        cls.test_map = TEST / "app-gcc" / "X-Track-App-GCC.map"
        for path in (cls.prod_elf, cls.test_elf, cls.prod_map, cls.test_map):
            if not path.exists():
                raise unittest.SkipTest(f"missing P2-6 evidence artifact: {path}")
        cls.prod_nm = run([NM, "-a", "-C", str(cls.prod_elf)])
        cls.test_nm = run([NM, "-a", "-C", str(cls.test_elf)])
        cls.prod_nm_raw = run([NM, "-a", str(cls.prod_elf)])
        cls.test_nm_raw = run([NM, "-a", str(cls.test_elf)])
        cls.prod_map_text = read(cls.prod_map)
        cls.test_map_text = read(cls.test_map)
        cls.prod_strings = run([STRINGS, "-a", str(cls.prod_elf)])
        cls.test_strings = run([STRINGS, "-a", str(cls.test_elf)])
        cls.test_disassembly = run([OBJDUMP, "-d", str(cls.test_elf)])

        # Keep the raw machine-readable evidence beside the test result.
        (OUT / "prod-nm.txt").write_text(cls.prod_nm, encoding="utf-8")
        (OUT / "test-nm.txt").write_text(cls.test_nm, encoding="utf-8")
        (OUT / "prod-nm-raw.txt").write_text(cls.prod_nm_raw, encoding="utf-8")
        (OUT / "test-nm-raw.txt").write_text(cls.test_nm_raw, encoding="utf-8")
        (OUT / "prod-map.txt").write_text(cls.prod_map_text, encoding="utf-8")
        (OUT / "test-map.txt").write_text(cls.test_map_text, encoding="utf-8")
        (OUT / "prod-strings.txt").write_text(cls.prod_strings, encoding="utf-8")
        (OUT / "test-strings.txt").write_text(cls.test_strings, encoding="utf-8")
        (OUT / "test-disassembly.txt").write_text(
            cls.test_disassembly, encoding="utf-8")

    def test_l1_test_configuration_contains_all_instrumentation_symbols(self) -> None:
        l1 = [
            r"\bP2_6_sbrk_call_count\b",
            r"\bP2_6_sbrk_peak\b",
            r"\b__wrap_lv_tlsf_malloc\b",
            r"\b__wrap_lv_tlsf_realloc\b",
            r"\b__wrap_lv_tlsf_free\b",
            r"\bP2_6_StartupStackScanProbe\b",
            r"_ZL18p2_6_measure_beginm",
            r"_ZL16p2_6_measure_endv",
            r"_ZL18p2_6_report_common",
            r"_ZN3HAL27OTA_P2_6_ReportPackageApply",
            r"_ZN3HAL25OTA_P2_6_ReportPatchApply",
        ]
        missing = [pattern for pattern in l1
                   if not re.search(pattern, self.test_nm_raw)]
        self.assertFalse(missing, f"L1 missing symbols: {missing}")
        for pattern in l1:
            # The linker map retains mangled C++ names; the corresponding
            # demangled spelling is already checked in the nm output above.
            self.assertRegex(self.test_map_text, pattern,
                             f"L1 map missing {pattern}")

    def test_l1_rtt_format_fragments_are_reachable(self) -> None:
        # The compiler may split adjacent literals, so check the stable printable
        # fragments rather than requiring one unbroken string-table entry.
        fragments = (
            "P2_6 kind=",
            "workspace_peak=",
            "arena_peak_observed=",
            "failed_request_size=",
            "stack_entry=",
            "guard_entry=",
            "sbrk_delta=",
            "tlsf_malloc_delta=",
            "tlsf_realloc_delta=",
            "tlsf_free_delta=",
            "lv_free_entry=",
            "lv_big_entry=",
            "lv_frag_entry=",
            "lv_max_entry=",
            "last_ret=0x",
        )
        missing = [fragment for fragment in fragments
                   if fragment not in self.test_strings]
        self.assertFalse(missing, f"L1 RTT fragments missing: {missing}")

    def test_l2_production_has_no_test_symbols_or_strings(self) -> None:
        forbidden = (
            r"\bP2_6_",
            r"\b__wrap_lv_tlsf_",
            r"\b__real_lv_tlsf_",
            r"\bp2_6_",
            r"OTA_P2_6_HOST_ARENA_CAPACITY_OVERRIDE",
        )
        for pattern in forbidden:
            self.assertNotRegex(self.prod_nm_raw, pattern,
                                f"L2 production nm hit: {pattern}")
            self.assertNotRegex(self.prod_map_text, pattern,
                                f"L2 production map hit: {pattern}")
        self.assertNotIn("P2_6 kind=", self.prod_strings)

    def test_l3_host_only_items_are_absent_from_both_firmware_configs(self) -> None:
        for label, nm_text, map_text in (
            ("production", self.prod_nm, self.prod_map_text),
            ("test", self.test_nm, self.test_map_text),
        ):
            self.assertNotRegex(nm_text, r"\bota_p2_6_host_arena_capacity\b",
                                f"L3 symbol leaked into {label} nm")
            self.assertNotRegex(map_text, r"\bota_p2_6_host_arena_capacity\b",
                                f"L3 symbol leaked into {label} map")

    def test_wrapper_disassembly_forwards_to_real_tlsf_functions(self) -> None:
        expected_calls = {
            "__wrap_lv_tlsf_malloc": "<lv_tlsf_malloc>",
            "__wrap_lv_tlsf_realloc": "<lv_tlsf_realloc>",
            "__wrap_lv_tlsf_free": "<lv_tlsf_free>",
        }
        for wrapper, target in expected_calls.items():
            start = self.test_disassembly.find(f"<{wrapper}>:")
            self.assertGreaterEqual(start, 0, f"missing {wrapper} body")
            next_symbol = re.search(r"\n[0-9a-f]{8} <[^>]+>:",
                                     self.test_disassembly[start + 1:])
            end = start + 1 + next_symbol.start() if next_symbol else len(self.test_disassembly)
            body = self.test_disassembly[start:end]
            self.assertIn(target, body,
                          f"{wrapper} does not call {target}")
        self.assertNotRegex(self.test_nm_raw, r"\bU\s+__real_lv_tlsf_",
                            "unresolved __real wrapper alias")

    def test_macro_media_is_separated_from_elf_symbol_media(self) -> None:
        prod_cache = read(PROD / "CMakeCache.txt")
        test_cache = read(TEST / "CMakeCache.txt")
        prod_commands = read(PROD / "compile_commands.json")
        test_commands = read(TEST / "compile_commands.json")
        self.assertIn("P2_6_TEST_ENABLE:BOOL=OFF", prod_cache)
        self.assertIn("P2_6_TEST_ENABLE:BOOL=ON", test_cache)
        self.assertNotIn("-DP2_6_TEST_ENABLE=1", prod_commands)
        self.assertIn("-DP2_6_TEST_ENABLE=1", test_commands)
        self.assertNotIn("OTA_P2_6_HOST_ARENA_CAPACITY_OVERRIDE", prod_commands)
        self.assertNotIn("OTA_P2_6_HOST_ARENA_CAPACITY_OVERRIDE", test_commands)
        self.assertNotIn("-flto", prod_commands + test_commands)

        instrumented_sources = (
            "gcc_runtime_compat.c",
            "HAL_OTA_Package.cpp",
            "OtaUpdate.cpp",
        )
        test_entries = json.loads(test_commands)
        for source in instrumented_sources:
            entries = [entry for entry in test_entries
                       if Path(entry["file"]).name == source
                       and "X_Track_App_GCC.dir" in entry.get("output", "")]
            self.assertTrue(entries, f"missing compile command for {source}")
            self.assertTrue(all("-DP2_6_TEST_ENABLE=1" in entry["command"]
                                for entry in entries),
                            f"P2_6 macro does not cover every {source} command")


if __name__ == "__main__":
    OUT.mkdir(parents=True, exist_ok=True)
    suite = unittest.defaultTestLoader.loadTestsFromTestCase(P2SixSymbolTests)
    result = unittest.TextTestRunner(verbosity=2).run(suite)
    raise SystemExit(0 if result.wasSuccessful() else 1)
