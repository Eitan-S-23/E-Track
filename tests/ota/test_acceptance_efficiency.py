#!/usr/bin/env python3
"""Positive and adversarial checks for bounded, evidence-preserving reruns."""
import copy
import hashlib
import json
import tempfile
import unittest
from pathlib import Path

import test_acceptance_bundle as base


V = base.VALIDATOR


def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest().upper()


class PlannedExecutionTests(unittest.TestCase):
    def setUp(self):
        self.contract = base.valid_contract()
        self.matrix = base.valid_matrix(self.contract)
        self.plan = {"reusable_criteria": ["FUNC-1"], "required_commands": []}

    def test_reusable_success_cannot_start_an_extra_command(self):
        errors = V.validate_planned_execution(self.matrix, self.contract, self.plan)
        self.assertTrue(any("unplanned EXECUTED PASS" in error for error in errors))
        self.assertIn("CMD-FUNC-1", errors[0])

    def test_invalidated_success_can_execute(self):
        self.plan.update({"reusable_criteria": [], "required_commands": ["CMD-FUNC-1"]})
        self.assertEqual([], V.validate_planned_execution(self.matrix, self.contract, self.plan))

    def test_shared_required_command_does_not_force_a_second_run(self):
        self.plan["required_commands"] = ["CMD-FUNC-1"]
        self.assertEqual([], V.validate_planned_execution(self.matrix, self.contract, self.plan))

    def test_shared_command_cannot_pull_in_unplanned_commands(self):
        self.plan["required_commands"] = ["CMD-FUNC-1"]
        self.contract["criteria"][0]["command_ids"].append("CMD-EXTRA")
        errors = V.validate_planned_execution(self.matrix, self.contract, self.plan)
        self.assertTrue(any("CMD-EXTRA" in error for error in errors))

    def test_missing_command_is_not_an_execution_scope_escape(self):
        self.contract["criteria"][0]["command_ids"] = []
        self.assertTrue(V.validate_planned_execution(self.matrix, self.contract, self.plan))

    def test_new_failure_or_gap_is_not_hidden_by_old_pass(self):
        for result in ("FAIL", "NOT_OBSERVED"):
            with self.subTest(result=result):
                self.matrix["criteria"][0]["result"] = result
                self.assertEqual([], V.validate_planned_execution(self.matrix, self.contract, self.plan))

    def test_reused_evidence_is_not_a_new_execution(self):
        self.matrix["criteria"][0]["execution"] = "REUSED"
        self.assertEqual([], V.validate_planned_execution(self.matrix, self.contract, self.plan))


class AcceptanceEfficiencyTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory(dir=base.ROOT, prefix=".acceptance-efficiency-")
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        self.repo = base.create_fixture_repo(self.root / "repo", {
            "Tools/jlink/probe.py": b"print('observation')\n",
            "Tools/acceptance/package.py": b"print('package')\n",
            "USER/product.c": b"int product = 1;\n",
            "app/bluetooth_flutter_Trace/lib/example.dart": b"void main() {}\n",
        })

    def scoped_contract(self):
        contract = base.valid_contract()
        for group_id, profile, category in (
            ("firmware", "Firmware", "production_source"),
            ("capture", "Capture", "validation_inputs"),
            ("evidence", "Evidence", "validation_inputs"),
        ):
            contract["input_groups"].append({"id": group_id, "profile": profile, "category": category})
        contract["commands"][0].update({
            "command": "python Tools/jlink/probe.py",
            "input_groups": ["firmware", "capture"],
            "runner_paths": ["Tools/jlink/probe.py"],
        })
        contract["criteria"][0]["input_groups"] = ["firmware", "capture"]
        contract["commands"].append({
            "id": "CMD-PACK", "description": "Offline packaging only.",
            "command": "python Tools/acceptance/package.py", "expected_exit_codes": [0],
            "output_required": True, "input_groups": ["evidence"],
            "runner_paths": ["Tools/acceptance/package.py"],
        })
        criterion = copy.deepcopy(contract["criteria"][0])
        criterion.update({"id": "PACK-1", "kind": "process", "input_groups": ["evidence"],
                          "command_ids": ["CMD-PACK"]})
        contract["criteria"].append(criterion)
        self.freeze(contract)
        return contract

    def freeze(self, contract):
        (contract["freeze_commit"], contract["freeze_tree"],
         contract["profile_config_blob"]) = base.fixture_freeze(self.repo)

    def changed_plan(self, path):
        previous = self.scoped_contract()
        matrix = base.valid_matrix(previous)
        criterion = copy.deepcopy(matrix["criteria"][0])
        criterion["id"] = "PACK-1"
        matrix["criteria"].append(criterion)
        current = base.successor_contract(previous)
        base.commit_fixture_files(self.repo, {path: b"changed\n"})
        self.freeze(current)
        return V.compute_rerun_plan(current, previous, matrix, repo_root=self.repo)

    def test_packager_change_does_not_repeat_product_observation(self):
        plan = self.changed_plan("Tools/acceptance/package.py")
        self.assertEqual(["CMD-PACK"], plan["required_commands"])
        self.assertEqual(["FUNC-1"], plan["reusable_criteria"])

    def test_collector_change_requires_new_observation(self):
        plan = self.changed_plan("Tools/jlink/probe.py")
        self.assertEqual(["CMD-FUNC-1"], plan["required_commands"])
        self.assertEqual(["PACK-1"], plan["reusable_criteria"])

    def test_product_change_requires_new_observation(self):
        self.assertEqual(["CMD-FUNC-1"], self.changed_plan("USER/product.c")["required_commands"])

    def test_flutter_change_does_not_repeat_firmware_observation(self):
        self.assertEqual([], self.changed_plan("app/bluetooth_flutter_Trace/lib/example.dart")["required_commands"])

    def test_component_profiles_cover_flutter_and_cloudflare(self):
        tree = base.fixture_freeze(self.repo)[1]
        for profile, path in (
            ("Flutter", "app/bluetooth_flutter_Trace/pubspec.yaml"),
            ("Cloudflare", "app/bluetooth_flutter_Trace/cloudflare/update-service/worker/package.json"),
        ):
            self.assertIn(path, V._profile_tree_paths(self.repo, tree, profile))

    def test_scoped_contract_and_frozen_runner_coverage(self):
        contract = self.scoped_contract()
        self.assertEqual([], V.validate_contract(contract))
        self.assertEqual([], V.validate_freeze_objects(contract, self.repo))

    def test_criterion_cannot_omit_command_dependency(self):
        contract = self.scoped_contract()
        contract["criteria"][0]["input_groups"] = ["firmware"]
        self.assertTrue(any("omits command dependencies" in error for error in V.validate_contract(contract)))

    def test_functional_criterion_cannot_omit_product(self):
        contract = self.scoped_contract()
        contract["criteria"][0]["input_groups"] = ["capture"]
        contract["commands"][0]["input_groups"] = ["capture"]
        self.assertTrue(any("must include product" in error for error in V.validate_contract(contract)))

    def test_unknown_profile_and_category_laundering_fail(self):
        for profile, category in (("DoesNotExist", "validation_inputs"), ("Firmware", "validation_inputs")):
            contract = self.scoped_contract()
            contract["input_groups"][3].update({"profile": profile, "category": category})
            self.assertTrue(V.validate_freeze_objects(contract, self.repo))

    def test_undeclared_or_uncovered_runner_fails(self):
        for paths in ([], ["Tools/acceptance/package.py"]):
            contract = self.scoped_contract()
            contract["commands"][0]["runner_paths"] = paths
            self.assertTrue(V.validate_freeze_objects(contract, self.repo))

    def test_module_and_basename_entry_cannot_hide_collector(self):
        for command in ("python -m Tools.jlink.probe", "python -mTools.jlink.probe", "python probe.py"):
            contract = self.scoped_contract()
            contract["commands"][0].update({"command": command, "input_groups": ["firmware", "evidence"],
                                             "runner_paths": []})
            contract["criteria"][0]["input_groups"] = ["firmware", "evidence"]
            self.assertTrue(V.validate_freeze_objects(contract, self.repo))

    def test_module_entry_cannot_be_covered_by_an_unrelated_script(self):
        contract = self.scoped_contract()
        contract["commands"][0].update({"command": "python -m Tools.jlink.probe",
                                         "input_groups": ["firmware", "evidence"],
                                         "runner_paths": ["Tools/acceptance/package.py"]})
        contract["criteria"][0]["input_groups"] = ["firmware", "evidence"]
        self.assertTrue(V.validate_freeze_objects(contract, self.repo))

    def test_registered_product_build_script_is_a_bound_runner(self):
        contract = self.scoped_contract()
        contract["commands"][0].update({"command": "build_f435_and_simulator.bat --no-pause",
                                         "input_groups": ["firmware"],
                                         "runner_paths": ["build_f435_and_simulator.bat"]})
        contract["criteria"][0]["input_groups"] = ["firmware"]
        self.assertEqual([], V.validate_contract(contract))
        self.assertEqual([], V.validate_freeze_objects(contract, self.repo))

    def test_inline_interpreter_variants_cannot_hide_unbound_code(self):
        for command in (
            'python -c"import Tools.jlink.probe"',
            'python -c "import Tools.jlink.probe"',
            'node -e "require(\'./Tools/jlink/probe\')"',
            'node --eval="require(\'./Tools/jlink/probe\')"',
            'bash -lc "python Tools/jlink/probe.py"',
            'pwsh -enc hidden',
            'powershell -c hidden',
            'cmd /c "python -c hidden"',
            'python Tools/acceptance/package.py && python -chidden',
        ):
            with self.subTest(command=command):
                contract = self.scoped_contract()
                contract["commands"][0].update({"command": command, "input_groups": ["firmware", "evidence"],
                                                 "runner_paths": ["Tools/acceptance/package.py"]})
                contract["criteria"][0]["input_groups"] = ["firmware", "evidence"]
                self.assertTrue(V.validate_freeze_objects(contract, self.repo))

    def source(self, bundle):
        cp, mp, contract, matrix = bundle
        return {"contract": contract, "matrix": matrix,
                "contract_sha256": digest(cp), "matrix_sha256": digest(mp)}

    def reuse_round(self, previous, original, round_id):
        pcp, pmp, pc, pm = previous
        source = self.source(original)
        sources = {source["matrix_sha256"]: source}
        matrix = copy.deepcopy(pm)
        matrix["round_id"] = round_id
        matrix["criteria"][0].update({
            "execution": "REUSED", "reused_from_round": original[3]["round_id"],
            "origin_contract_sha256": source["contract_sha256"],
            "origin_matrix_sha256": source["matrix_sha256"],
        })
        current = base.write_bundle(self.root / round_id, self.repo, pc, matrix)
        cp, mp, contract, matrix = current
        plan = V.compute_rerun_plan(
            contract, pc, pm, current_contract_sha256=digest(cp), previous_contract_sha256=digest(pcp),
            previous_matrix_sha256=digest(pmp), current_round_id=round_id,
            repo_root=self.repo, reuse_sources=sources,
        )
        plan_path = mp.parent / "rerun-plan.json"
        plan_path.write_bytes(V._rerun_plan_bytes(plan))
        matrix.update({"previous_matrix_sha256": digest(pmp), "rerun_plan_path": "rerun-plan.json",
                       "rerun_plan_sha256": digest(plan_path)})
        base.rewrite_contract_and_matrix(cp, mp, contract, matrix)
        return current, plan

    def cli_args(self, current, previous, original):
        return ["--contract", str(current[0]), "--matrix", str(current[1]), "--repo-root", str(self.repo),
                "--previous-contract", str(previous[0]), "--previous-matrix", str(previous[1]),
                "--reuse-source", str(original[0]), str(original[1])]

    def test_three_rounds_reuse_original_executed_evidence_end_to_end(self):
        first = base.write_bundle(self.root / "r1", self.repo)
        second, _ = self.reuse_round(first, first, "r2")
        third, plan = self.reuse_round(second, first, "r3")
        self.assertEqual([], plan["required_commands"])
        code, _, errors = base.run_main(self.cli_args(third, second, first))
        self.assertEqual(0, code, errors)

    def test_plan_generation_does_not_approve_unplanned_execution(self):
        previous = base.write_bundle(self.root / "r1", self.repo)
        matrix = copy.deepcopy(previous[3])
        matrix["round_id"] = "r2"
        current = base.write_bundle(self.root / "r2", self.repo, previous[2], matrix)
        args = self.cli_args(current, previous, previous)
        code, output, errors = base.run_main(args + ["--write-rerun-plan", "rerun-plan.json"])
        self.assertEqual(0, code, errors)
        self.assertIn("FINAL_VALIDATION=NOT_RUN mode=plan-only", output)
        self.assertNotIn("VALIDATION=PASS", output)
        code, _, errors = base.run_main(args)
        self.assertEqual(1, code)
        self.assertIn("unplanned EXECUTED PASS", errors)

    def test_new_failure_is_recorded_and_its_fix_can_be_retested(self):
        original = base.write_bundle(self.root / "r1", self.repo)
        matrix = base.valid_matrix(original[2], result="FAIL", owner="product", overall="PRODUCT_FAIL")
        matrix["round_id"] = "r2-failed"
        failed = base.write_bundle(self.root / "r2", self.repo, original[2], matrix)
        code, output, errors = base.run_main(self.cli_args(failed, original, original))
        self.assertEqual(0, code, errors)
        self.assertIn("overall=PRODUCT_FAIL", output)
        fixed_contract = base.successor_contract(original[2], digest(original[0]))
        base.commit_fixture_files(self.repo, {"USER/product.c": b"int product = 2;\n"})
        self.freeze(fixed_contract)
        fixed_matrix = base.valid_matrix(fixed_contract)
        fixed_matrix["round_id"] = "r3-fixed"
        fixed = base.write_bundle(self.root / "r3", self.repo, fixed_contract, fixed_matrix)
        code, _, errors = base.run_main(self.cli_args(fixed, failed, original))
        self.assertEqual(0, code, errors)

    def test_missing_original_fails_without_silent_reexecution(self):
        first = base.write_bundle(self.root / "r1", self.repo)
        second, _ = self.reuse_round(first, first, "r2")
        third, _ = self.reuse_round(second, first, "r3")
        code, _, errors = base.run_main(self.cli_args(third, second, first)[:-3])
        self.assertEqual(1, code)
        self.assertIn("missing previous round in reuse history", errors)

    def test_tampered_original_raw_evidence_fails(self):
        first = base.write_bundle(self.root / "r1", self.repo)
        second, _ = self.reuse_round(first, first, "r2")
        third, _ = self.reuse_round(second, first, "r3")
        (first[1].parent / "raw/func-1.log").write_bytes(b"tampered\n")
        code, _, errors = base.run_main(self.cli_args(third, second, first))
        self.assertEqual(1, code)
        self.assertIn("origin:", errors)

    def test_missing_intermediate_plan_is_not_laundered(self):
        first = base.write_bundle(self.root / "r1", self.repo)
        second, _ = self.reuse_round(first, first, "r2")
        third, _ = self.reuse_round(second, first, "r3")
        (second[1].parent / "rerun-plan.json").unlink()
        code, _, errors = base.run_main(self.cli_args(third, second, first))
        self.assertEqual(1, code)
        self.assertIn("reuse history", errors)

    def test_intermediate_reuse_cannot_launder_a_previous_failure(self):
        first = base.write_bundle(self.root / "r1", self.repo)
        failed_matrix = base.valid_matrix(first[2], result="FAIL", owner="product", overall="PRODUCT_FAIL")
        failed_matrix["round_id"] = "failed-round"
        failed = base.write_bundle(self.root / "failed", self.repo, first[2], failed_matrix)
        second, _ = self.reuse_round(first, first, "forged-round")
        second[3]["previous_matrix_sha256"] = digest(failed[1])
        base.rewrite_contract_and_matrix(*second)
        third, _ = self.reuse_round(second, first, "r4")
        args = self.cli_args(third, second, first) + ["--reuse-source", str(failed[0]), str(failed[1])]
        code, _, errors = base.run_main(args)
        self.assertEqual(1, code)
        self.assertIn("reuses invalidated evidence", errors)

    def test_current_round_cannot_be_its_own_origin(self):
        first = base.write_bundle(self.root / "r1", self.repo)
        second, _ = self.reuse_round(first, first, "r2")
        code, _, errors = base.run_main(self.cli_args(second, first, second))
        self.assertEqual(1, code)
        self.assertIn("cannot be the current matrix or round", errors)

    def test_later_failure_cannot_be_hidden_by_old_pass(self):
        first = base.write_bundle(self.root / "r1", self.repo)
        failed = base.valid_matrix(first[2], result="FAIL", owner="product", overall="PRODUCT_FAIL")
        plan = V.compute_rerun_plan(first[2], first[2], failed,
                                    reuse_sources={digest(first[1]): self.source(first)})
        self.assertEqual(["CMD-FUNC-1"], plan["required_commands"])
        self.assertEqual([], plan["reusable_criteria"])

    def test_forged_origin_and_changed_inputs_are_rejected(self):
        first = base.write_bundle(self.root / "r1", self.repo)
        second, _ = self.reuse_round(first, first, "r2")
        sources = {digest(first[1]): self.source(first)}
        second[3]["criteria"][0]["origin_contract_sha256"] = "F" * 64
        with self.assertRaisesRegex(ValueError, "invalid original"):
            V.compute_rerun_plan(second[2], second[2], second[3], reuse_sources=sources)
        second[3]["criteria"][0]["origin_contract_sha256"] = digest(first[0])
        current = base.successor_contract(second[2], digest(second[0]))
        base.commit_fixture_files(self.repo, {"USER/product.c": b"changed\n"})
        self.freeze(current)
        plan = V.compute_rerun_plan(current, second[2], second[3], previous_contract_sha256=digest(second[0]),
                                    previous_matrix_sha256=digest(second[1]), repo_root=self.repo, reuse_sources=sources)
        self.assertEqual(["CMD-FUNC-1"], plan["required_commands"])


if __name__ == "__main__":
    unittest.main(verbosity=2)
