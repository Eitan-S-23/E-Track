"""Host checks for the offline census boundary and strict result consumer."""
from __future__ import annotations

import argparse
import copy
import io
from pathlib import Path
import runpy
import sys
import unittest

ROOT = Path(__file__).resolve().parents[2]
M = runpy.run_path(str(ROOT / "Tools/ota/install_workload.py"))


def inputs():
    return {"package": {"bytes": 748}, "current": {"bytes": 4096},
            "target": {"bytes": 4096}, "current_vcode": 20700, "target_vcode": 20800}


def normal():
    phases = {}
    for name in M["PHASES"]:
        phases[name] = {
            "ran": name != "boot_resume", "interrupted": False,
            "result_code": None if name == "boot_resume" else 0,
            "io": {resource: {op: {"calls": 0, "bytes": 0} for op in M["OPERATIONS"]}
                   for resource in M["RESOURCES"]},
        }
    phases["candidate"]["io"]["candidate"]["program"] = {"calls": 4, "bytes": 4096}
    phases["backup"]["io"]["backup"]["program"] = {"calls": 3, "bytes": 4128}
    phases["confirmation_commit"]["io"]["eeprom"]["program"] = {"calls": 1, "bytes": 64}
    return {"schema": 1, "kind": "HOST_INSTALL_WORKLOAD", "hardware": False,
            "hardware_timing": False, "scenario": "normal", "cut_block": 0,
            "injection_seen": False, "passed": True, "checks": 20, "failures": 0,
            "package_bytes": 748, "current_bytes": 4096, "target_bytes": 4096,
            "final_bcb_state": 4, "final_vcode": 20800, "phases": phases}


class WorkloadTests(unittest.TestCase):
    def validate(self, value):
        return M["validate_result"](value, "normal", 0, inputs())

    def rejected(self, value):
        with self.assertRaises(ValueError):
            self.validate(value)

    def test_model_result_is_not_hardware_evidence(self):
        self.assertIs(self.validate(normal())["hardware"], False)

    def test_hardware_or_timing_promotion_rejected(self):
        for name in ("hardware", "hardware_timing"):
            with self.subTest(name=name):
                value = normal()
                value[name] = True
                self.rejected(value)

    def test_actual_checks_required(self):
        for key, replacement in (("passed", False), ("passed", 1), ("checks", 0),
                                 ("checks", True), ("failures", 1), ("failures", False),
                                 ("schema", True), ("cut_block", False)):
            with self.subTest(key=key, replacement=replacement):
                value = normal()
                value[key] = replacement
                self.rejected(value)

    def test_return_code_cannot_be_hidden_by_passed_flag(self):
        value = normal()
        value["phases"]["backup"]["result_code"] = -16
        self.rejected(value)

    def test_missing_phase_rejected(self):
        value = normal()
        del value["phases"]["backup"]
        self.rejected(value)

    def test_unexecuted_phase_cannot_have_io_or_success_code(self):
        value = normal()
        value["phases"]["boot_resume"]["result_code"] = 0
        self.rejected(value)
        value = normal()
        value["phases"]["boot_resume"]["io"]["internal"]["read"] = {"calls": 1, "bytes": 4}
        self.rejected(value)

    def test_invalid_counts_rejected(self):
        for count in ({"calls": True, "bytes": 4}, {"calls": -1, "bytes": 4},
                      {"calls": 0, "bytes": 4}, {"calls": 1, "bytes": 2**32}):
            with self.subTest(count=count):
                value = normal()
                value["phases"]["boot"]["io"]["internal"]["read"] = count
                self.rejected(value)

    def test_zero_payload_or_missing_commit_not_success(self):
        for phase, resource in (("candidate", "candidate"), ("backup", "backup"),
                                ("confirmation_commit", "eeprom")):
            with self.subTest(phase=phase):
                value = normal()
                value["phases"][phase]["io"][resource]["program"] = {"calls": 0, "bytes": 0}
                self.rejected(value)

    def test_input_or_final_identity_drift_rejected(self):
        for key, replacement in (("package_bytes", 749), ("current_bytes", 4097),
                                 ("target_bytes", 4097), ("final_vcode", 20700),
                                 ("final_bcb_state", 3), ("scenario", "cut-after"),
                                 ("injection_seen", True)):
            with self.subTest(key=key):
                value = normal()
                value[key] = replacement
                self.rejected(value)

    def test_small_fixture_cut_positions_are_deduplicated(self):
        cases = M["cases_for"](4096)
        self.assertEqual(len(cases), 9)
        self.assertEqual(len(cases), len(set(cases)))
        self.assertEqual([n for mode, n in cases if mode == "cut-after"], [1])

    def test_real_image_has_first_middle_last_boundaries(self):
        cases = M["cases_for"](613344)
        self.assertEqual(len(cases), 13)
        self.assertEqual([n for mode, n in cases if mode == "cut-before"], [1, 75, 150])
        self.assertEqual([n for mode, n in cases if mode == "cut-after"], [1, 75, 150])

    def test_invalid_capacity_not_admitted(self):
        for length in (0, True, 0x45f, 0xF0001):
            with self.subTest(length=length), self.assertRaises(ValueError):
                M["cases_for"](length)

    def test_bound_fixture_hash_verified_without_writing_input(self):
        item = M["record"](ROOT / "tests/ota-vectors/toy-new.bin")
        self.assertEqual(M["verify_record"](item), item)
        changed = copy.deepcopy(item)
        changed["sha256"] = "0" * 64
        with self.assertRaises(ValueError):
            M["verify_record"](changed)
        self.assertEqual(M["record"](item["path"]), item)

    def test_existing_output_refused_without_overwrite(self):
        with self.assertRaises(ValueError):
            M["Run"](ROOT, ROOT / "tests/ota")

    def test_external_sibling_refused_before_mkdir(self):
        with self.assertRaises(ValueError):
            M["Run"](ROOT, ROOT.parent / (ROOT.name + "-workload-outside"))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    M["require"](sys.flags.isolated and sys.flags.no_site and sys.dont_write_bytecode,
                 "use Python -I -S -B -X utf8")
    M["require"](args.root.is_absolute() and args.root.resolve() == ROOT and
                 Path.cwd().resolve() == ROOT, "explicit active project root/cwd required")
    out = M["IO"]["checked_output"](ROOT, args.out)
    M["require"](not out.exists(), "test output already exists")
    for name in ("unittest.log", "result.json"):
        M["IO"]["checked_output"](ROOT, out / name)
    out.mkdir(parents=True)
    stream = io.StringIO()
    result = unittest.TextTestRunner(stream=stream, verbosity=2).run(
        unittest.defaultTestLoader.loadTestsFromTestCase(WorkloadTests))
    text = stream.getvalue()
    with M["IO"]["checked_output"](ROOT, out / "unittest.log").open("x", encoding="utf-8") as log:
        log.write(text)
    M["IO"]["write_json"](ROOT, out / "result.json", {
        "passed": result.wasSuccessful(), "tests": result.testsRun,
        "failures": len(result.failures), "errors": len(result.errors),
        "skipped": len(result.skipped), "sources": M["source_records"](),
        "test_source": M["record"](__file__), "hardware": False,
    })
    print(text)
    return 0 if result.wasSuccessful() else 1


if __name__ == "__main__":
    raise SystemExit(main())
