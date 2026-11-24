"""Affected offline preparation checks, without replaying the device campaign."""
from __future__ import annotations

import argparse
import ast
import copy
import hashlib
import json
import os
from pathlib import Path
import sys
import unittest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "Tools/ota"))
import p34_patch_preparation as prep
import p34_full_trace as trace

OUT: Path
UNIT_FUNCTIONS = {
    "Tools/ota/p34_patch_preparation.py": (
        "build_command", "sections_from_objdump", "layout_constants", "memory_checks", "raw"),
    "Tools/ota/p34_full_trace.py": ("install_restore_timing",),
}


def function_bindings():
    result = {}
    for path, names in UNIT_FUNCTIONS.items():
        tree = ast.parse((ROOT / path).read_text(encoding="utf-8"))
        found = {node.name: node for node in tree.body if isinstance(node, ast.FunctionDef)}
        for name in names:
            result[path + ":" + name] = hashlib.sha256(
                ast.dump(found[name], include_attributes=False).encode("utf-8")).hexdigest()
    return result


# Reuse the original FULL summary assertions without its unrelated device-chain
# setUpClass. Only these pure methods are executed against the changed parser.
old_tree = ast.parse((ROOT / "tests/ota/test_p34_install.py").read_text(encoding="utf-8"))
old_class = next(node for node in old_tree.body if isinstance(node, ast.ClassDef) and node.name == "InstallTests")
OLD_METHODS = (
    "summaries", "test_restore_timing_keeps_cycle_totals_separate_from_wall_time",
    "test_identical_duplicate_summaries_are_not_counted_twice",
    "test_missing_malformed_or_conflicting_summaries_fail",
    "test_invalid_clock_error_and_disabled_optimization_fail",
    "test_impossible_counts_cycles_and_uint32_overflow_fail", "test_64bit_cycle_carry_is_not_truncated",
    "test_all_fallbacks_are_measured_without_fabricating_a_reuse_benefit")
methods = [node for node in old_class.body if isinstance(node, ast.FunctionDef) and node.name in OLD_METHODS]
assert {node.name for node in methods} == set(OLD_METHODS)
namespace = {"trace": trace}
exec(compile(ast.Module(body=methods, type_ignores=[]), "tests/ota/test_p34_install.py", "exec"), namespace)
FullSummaryRegressionTests = type("FullSummaryRegressionTests", (unittest.TestCase,),
                                  {name: namespace[name] for name in OLD_METHODS})


class PreparationUnitTests(unittest.TestCase):
    def test_layout_comes_from_the_frozen_header_not_a_remembered_address(self):
        constants = prep.layout_constants()
        self.assertEqual(constants["OTA_OVERLAY_ORIGIN"], 0x20058000)
        self.assertEqual(constants["OTA_OVERLAY_WORKSPACE_LENGTH"], 40960)
        actual = prep.sections_from_objdump(prep.original_command("sections").decode("utf-8"))
        self.assertIn("RAMCODE", actual)
        memory = prep.memory_checks(actual, constants)
        self.assertGreater(memory["heap_after_link_reserve_bytes"], 0)
        self.assertFalse(memory["runtime_stack_high_water"])

    def test_wrong_overlay_and_changed_stack_guard_header_heap_are_rejected(self):
        actual = prep.sections_from_objdump(prep.original_command("sections").decode("utf-8"))
        mutations = ((".ota_overlay", "address", 0x20048000), (".ota_overlay", "bytes", 40959),
                     (".ota_stack", "bytes", 8191), (".ota_stack_guard", "bytes", 31),
                     (".fw_header", "address", 0x08010404), (".fw_header", "bytes", 95),
                     ("._user_heap_stack", "address", actual[".ota_stack_guard"]["address"] + 1))
        for section, key, value in mutations:
            with self.subTest(section=section, key=key), self.assertRaises(RuntimeError):
                bad = copy.deepcopy(actual)
                bad[section][key] = value
                prep.memory_checks(bad)

    def test_missing_and_duplicate_sections_are_rejected(self):
        with self.assertRaises(RuntimeError):
            prep.memory_checks({})
        line = " 1 .text 00000400 08010000 08010000 00001000 2**0\n"
        with self.assertRaises(RuntimeError):
            prep.sections_from_objdump(line + line)

    def test_build_reuses_inherited_flags_and_redirects_all_named_outputs(self):
        original = prep.read(prep.N04 / "logs/configure.json")["args"]
        before = copy.deepcopy(original)
        args = prep.build_command(original)
        self.assertEqual(original, before)
        self.assertEqual(args[args.index("-S") + 1], str(prep.FW / "MDK-ARM_F435/cmake-generated"))
        self.assertEqual(args[args.index("-B") + 1], str(prep.BUILD))
        self.assertIn("-DCMAKE_C_FLAGS:STRING=-DOTA_PATCH_COALESCE_WRITES=1", args)
        cxx = next(arg for arg in args if arg.startswith("-DCMAKE_CXX_FLAGS:STRING="))
        for flag in ("CONFIG_OTA_INSTALL_QE_REUSE", "CONFIG_OTA_INSTALL_PROFILE", "OTA_PATCH_COALESCE_WRITES"):
            self.assertIn("-D" + flag + "=1", cxx)
        self.assertFalse(any(str(prep.N04) in arg for arg in args))

    def test_ambiguous_or_unexpected_build_flags_are_rejected(self):
        original = prep.read(prep.N04 / "logs/configure.json")["args"]
        for extra in (("-B", "wrong"), ("-DCMAKE_C_FLAGS:STRING=unexpected",)):
            with self.subTest(extra=extra), self.assertRaises(RuntimeError):
                prep.build_command(original + list(extra))
        with self.assertRaises(RuntimeError):
            prep.build_command([arg for arg in original if not arg.startswith("-DCMAKE_CXX_FLAGS:STRING=")])

    def test_new_output_does_not_overwrite_an_existing_file(self):
        path = OUT / "preserved.bin"
        before = prep.raw(path, b"original")
        with self.assertRaises(FileExistsError):
            prep.raw(path, b"replacement")
        self.assertEqual(prep.record(path), before)

    def test_sibling_output_is_rejected_before_creation(self):
        with self.assertRaises(prep.common.IO["OutputBoundaryError"]):
            prep.raw(ROOT.parent / (ROOT.name + "-not-authorized") / "fixture", b"x")


class PatchSummaryTests(unittest.TestCase):
    def summaries(self):
        return [line.replace("phase=full", "phase=patch") for line in namespace["summaries"](self)]

    def test_explicit_patch_kind_and_duplicate_summaries(self):
        value = trace.install_restore_timing(self.summaries(), 288000000, package_kind="patch")
        self.assertEqual(set(value["phases"]), {"patch", "backup"})
        self.assertEqual(value, trace.install_restore_timing(self.summaries() * 2, 288000000, package_kind="patch"))
        self.assertFalse(value["whole_installation_wall_time"])

    def test_default_full_does_not_silently_accept_patch(self):
        with self.assertRaises(RuntimeError):
            trace.install_restore_timing(self.summaries(), 288000000)

    def test_patch_rejects_mixed_missing_or_truncated_phases(self):
        lines = self.summaries()
        for bad in ([], lines[:1], [lines[0][:-2], lines[1]],
                    lines + [lines[0].replace("phase=patch", "phase=full")],
                    lines + [lines[0].replace("ticks=7", "ticks=8")]):
            with self.subTest(bad=bad), self.assertRaises(RuntimeError):
                trace.install_restore_timing(bad, 288000000, package_kind="patch")

    def test_patch_rejects_errors_and_invalid_clock_or_cycle_counts(self):
        for old, new in (("rc=0", "rc=-1"), ("opt=1", "opt=0"), ("hz=288000000", "hz=144000000"),
                         ("fail=0", "fail=1"), ("invalid=0", "invalid=1"), ("calls=3", "calls=0"),
                         ("reused=2", "reused=3"), ("reuse=0:57600", "reuse=0:0"),
                         ("ticks=7", "ticks=4294967296")):
            with self.subTest(new=new), self.assertRaises(RuntimeError):
                trace.install_restore_timing([line.replace(old, new) for line in self.summaries()],
                                            288000000, package_kind="patch")

    def test_unknown_kind_is_rejected(self):
        for kind in ("", "recovery", None, True):
            with self.subTest(kind=kind), self.assertRaises(RuntimeError):
                trace.install_restore_timing(self.summaries(), 288000000, package_kind=kind)


def main():
    global OUT
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", required=True)
    parser.add_argument("--out", required=True)
    args = parser.parse_args()
    prep.require(Path(args.root) == ROOT and Path.cwd() == ROOT and sys.flags.isolated and
                 sys.flags.no_site and sys.dont_write_bytecode, "isolated project root required")
    OUT = prep.checked(args.out)
    prep.require(OUT.is_relative_to(ROOT / ".cache") and not OUT.exists(), "fresh project-local output required")
    for name in ("intent.json", "unittest.log", "result.json", "preserved.bin"):
        prep.checked(OUT / name)
    paths = {name: prep.checked(OUT / "host" / leaf) for name, leaf in {
        "HOME": "home", "USERPROFILE": "home", "APPDATA": "appdata", "LOCALAPPDATA": "localappdata",
        "TEMP": "tmp", "TMP": "tmp", "TMPDIR": "tmp", "XDG_CACHE_HOME": "cache",
        "PYTHONUSERBASE": "python", "PYTHONPYCACHEPREFIX": "pycache"}.items()}
    inputs = [prep.record(path) for path in (Path(__file__), Path(prep.__file__), Path(trace.__file__),
              ROOT / "tests/ota/test_p34_install.py", prep.FW / "Libraries/OTA/ota_layout.h",
              prep.FW / "cmake/linker/x-track-app-gcc.ld.S")]
    OUT.mkdir(parents=True)
    for name, path in paths.items():
        path.mkdir(parents=True, exist_ok=True)
        os.environ[name] = str(path)
    prep.save(OUT / "intent.json", dict(inputs=inputs, functions=function_bindings(),
        environment={name: str(path) for name, path in paths.items()}, hardware=False))
    suite = unittest.TestSuite(unittest.defaultTestLoader.loadTestsFromTestCase(cls) for cls in
                               (FullSummaryRegressionTests, PreparationUnitTests, PatchSummaryTests))
    with (OUT / "unittest.log").open("x", encoding="utf-8", newline="\n") as stream:
        result = unittest.TextTestRunner(stream=stream, verbosity=2).run(suite)
    prep.verify_records(inputs)
    value = dict(result="HOST_UNIT_PASS" if result.wasSuccessful() else "HOST_UNIT_FAIL", tests=result.testsRun,
        failures=len(result.failures), errors=len(result.errors), skipped=len(result.skipped), inputs=inputs,
        functions=function_bindings(), hardware=False, independent_acceptance=False, log=prep.record(OUT / "unittest.log"))
    prep.save(OUT / "result.json", value)
    print(json.dumps({key: value[key] for key in ("result", "tests", "failures", "errors", "skipped")}),
          str(OUT / "result.json"))
    if not result.wasSuccessful():
        print((OUT / "unittest.log").read_text(encoding="utf-8"))
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
