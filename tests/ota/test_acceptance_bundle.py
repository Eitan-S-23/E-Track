#!/usr/bin/env python3
import ast
import contextlib
import copy
import hashlib
import importlib.util
import io
import json
import os
import re
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest import mock


ROOT = Path(__file__).resolve().parents[2]
VALIDATOR_PATH = ROOT / "Tools" / "acceptance" / "validate_bundle.py"
CONTRACT_TEMPLATE = ROOT / "docs" / "acceptance-contracts" / "template.contract.json"
MATRIX_TEMPLATE = ROOT / "docs" / "acceptance-contracts" / "template.evidence-matrix.json"
MANIFEST_SCRIPT = ROOT / "Tools" / "provenance" / "source_manifest.ps1"
POWERSHELL = shutil.which("powershell.exe") or shutil.which("pwsh")

SPEC = importlib.util.spec_from_file_location("acceptance_validator", VALIDATOR_PATH)
VALIDATOR = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(VALIDATOR)


def valid_contract():
    return {
        "schema": "etrack-acceptance-contract-v2",
        "contract_id": "P2-6-v1",
        "version": 1,
        "task_id": "P2-6",
        "parent_contract_sha256": None,
        "status": "FROZEN",
        "approved_by": "user",
        "approved_at": "2026-08-14T12:00:00+08:00",
        "implementation_ref": "0123456789abcdef",
        "result_taxonomy": [
            "PASS",
            "PRODUCT_FAIL",
            "HARNESS_FAIL",
            "EVIDENCE_GAP",
            "ENV_BLOCKED",
        ],
        "invalidation_policy": "docs/acceptance-execution-contract.md",
        "input_groups": [
            {
                "id": "production",
                "profile": "Production",
                "category": "production_source",
                "manifest_path": "manifest-production/source-manifest.json",
                "manifest_sha256": "A" * 64,
                "manifest_json_sha256": "1" * 64,
            },
            {
                "id": "validation",
                "profile": "Validation",
                "category": "validation_inputs",
                "manifest_path": "manifest-validation/source-manifest.json",
                "manifest_sha256": "B" * 64,
                "manifest_json_sha256": "2" * 64,
            },
            {
                "id": "governance",
                "profile": "Governance",
                "category": "governance_inputs",
                "manifest_path": "manifest-governance/source-manifest.json",
                "manifest_sha256": "C" * 64,
                "manifest_json_sha256": "3" * 64,
            },
        ],
        "external_inputs": [],
        "commands": [
            {
                "id": "CMD-FUNC-1",
                "description": "Observe FUNC-1.",
                "command": "run-func-1",
                "expected_exit_codes": [0],
                "output_required": True,
            }
        ],
        "artifacts": [
            {
                "id": "ART-FIRMWARE",
                "description": "Firmware used for FUNC-1.",
                "path": "artifacts/fw.bin",
            }
        ],
        "criteria": [
            {
                "id": "FUNC-1",
                "description": "A frozen observable behavior.",
                "required": True,
                "kind": "functional",
                "evidence_types": ["raw_log"],
                "input_groups": ["production", "validation", "governance"],
                "external_inputs": [],
                "command_ids": ["CMD-FUNC-1"],
                "artifact_ids": ["ART-FIRMWARE"],
                "gate": {
                    "type": "boolean",
                    "basis": "frozen_requirement",
                    "expected": True,
                },
            }
        ],
        "performance_gates": [],
    }


def contract_hash(contract):
    data = json.dumps(contract, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(data).hexdigest().upper()


def successor_contract(previous, previous_sha256=None):
    current = copy.deepcopy(previous)
    current["version"] = previous["version"] + 1
    current["contract_id"] = f"{current['task_id']}-v{current['version']}"
    current["parent_contract_sha256"] = previous_sha256 or contract_hash(previous)
    return current


def valid_matrix(contract, result="PASS", owner=None, overall="PASS"):
    evidence = ["raw/func-1.log"] if result != "NOT_OBSERVED" else []
    observed = True if result == "PASS" else None
    if result == "FAIL" and owner == "product":
        observed = False
    matrix = {
        "schema": "etrack-evidence-matrix-v2",
        "contract_id": contract["contract_id"],
        "contract_sha256": contract_hash(contract),
        "round_id": "20260814-120000",
        "overall_result": overall,
        "previous_matrix_sha256": None,
        "rerun_plan_path": None,
        "rerun_plan_sha256": None,
        "criteria": [
            {
                "id": "FUNC-1",
                "result": result,
                "failure_owner": owner,
                "execution": "EXECUTED",
                "reused_from_round": None,
                "observed": observed,
                "evidence": evidence,
                "notes": "not observed" if result == "NOT_OBSERVED" else "observed",
            }
        ],
        "evidence_hashes": {path: "D" * 64 for path in evidence},
        "commands": [],
        "artifacts": [],
    }
    if result in {"PASS", "FAIL"}:
        matrix["commands"] = [
            {
                "id": "CMD-FUNC-1",
                "command": "run-func-1",
                "exit_code": 0,
                "output_evidence": "raw/func-1.log",
            }
        ]
    if result == "PASS" or (result == "FAIL" and owner in {"product", "harness"}):
        matrix["artifacts"] = [
            {
                "id": "ART-FIRMWARE",
                "path": "artifacts/fw.bin",
                "sha256": "E" * 64,
                "size": 3,
            }
        ]
    return matrix


def create_fixture_repo(path, extra_files=None):
    path.mkdir(parents=True, exist_ok=True)
    files = {
        relative: ("fixture:" + relative + "\n").encode("utf-8")
        for required in VALIDATOR.PROFILE_REQUIRED_PATHS.values()
        for relative in required
    }
    files["MDK-ARM_F435/RTE/Device/-AT32F435RGT7/at32f435_437_gpio.c"] = (
        b"void gpio_fixture(void) {}\n"
    )
    files["MDK-ARM_F435/RTE/_X-Track/RTE_Components.h"] = b"#define RTE_FIXTURE 1\n"
    files["Tools/\u56fe\u6807/README.md"] = b"unicode path fixture\n"
    files.update(extra_files or {})
    for relative, payload in files.items():
        target = path.joinpath(*relative.split("/"))
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(payload)
    subprocess.run(["git", "init", "-q", str(path)], check=True, cwd=ROOT)
    subprocess.run(
        ["git", "-C", str(path), "config", "core.autocrlf", "false"],
        check=True,
        cwd=ROOT,
    )
    hooks = path / ".no-hooks"
    hooks.mkdir()
    subprocess.run(["git", "-C", str(path), "add", "."], check=True, cwd=ROOT)
    subprocess.run(
        [
            "git",
            "-C",
            str(path),
            "-c",
            "user.name=fixture",
            "-c",
            "user.email=fixture@example.invalid",
            "-c",
            f"core.hooksPath={hooks}",
            "commit",
            "-q",
            "-m",
            "fixture",
        ],
        check=True,
        cwd=ROOT,
    )
    return path


def records_for_profile(profile, repo_root):
    return VALIDATOR._collect_profile_records(repo_root, profile)


def write_input_manifest(bundle, group, records=None):
    if records is None:
        raise ValueError("manifest records must be provided by a real fixture worktree")
    records = copy.deepcopy(records)
    manifest_path = bundle / group["manifest_path"]
    manifest_path.parent.mkdir(parents=True, exist_ok=True)
    text_bytes = VALIDATOR._manifest_text_bytes(records)
    text_path = manifest_path.with_name("source-manifest.txt")
    text_path.write_bytes(text_bytes)
    stable_hash = hashlib.sha256(text_bytes).hexdigest().upper()
    manifest = {
        "Schema": VALIDATOR.INPUT_MANIFEST_SCHEMA,
        "Profile": group["profile"],
        "Ordering": VALIDATOR.INPUT_MANIFEST_ORDERING,
        "Encoding": VALIDATOR.INPUT_MANIFEST_ENCODING,
        "FileCount": len(records),
        "ManifestSHA256": stable_hash,
        "Files": records,
    }
    manifest_path.write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    group["manifest_sha256"] = stable_hash
    group["manifest_json_sha256"] = hashlib.sha256(manifest_path.read_bytes()).hexdigest().upper()
    return manifest_path, text_path, manifest


def rewrite_contract_and_matrix(contract_path, matrix_path, contract, matrix):
    contract_path.write_text(json.dumps(contract, indent=2) + "\n", encoding="utf-8")
    matrix["contract_id"] = contract["contract_id"]
    matrix["contract_sha256"] = hashlib.sha256(contract_path.read_bytes()).hexdigest().upper()
    matrix_path.write_text(json.dumps(matrix, indent=2) + "\n", encoding="utf-8")


def write_bundle(bundle, repo_root, contract=None, matrix=None, records_by_profile=None):
    contract = copy.deepcopy(contract or valid_contract())
    matrix = copy.deepcopy(matrix or valid_matrix(contract))
    records_by_profile = records_by_profile or {}
    for group in contract["input_groups"]:
        records = records_by_profile.get(group["profile"])
        if records is None:
            records = records_for_profile(group["profile"], repo_root)
        write_input_manifest(bundle, group, records)

    raw = bundle / "raw" / "func-1.log"
    raw.parent.mkdir(parents=True, exist_ok=True)
    raw.write_bytes(b"observed\n")
    artifact = bundle / "artifacts" / "fw.bin"
    artifact.parent.mkdir(parents=True, exist_ok=True)
    artifact.write_bytes(b"fw\n")

    contract_path = bundle / "contract.json"
    matrix_path = bundle / "evidence-matrix.json"
    matrix["evidence_hashes"] = {
        "raw/func-1.log": hashlib.sha256(raw.read_bytes()).hexdigest().upper()
    }
    if matrix.get("commands"):
        matrix["commands"][0]["output_evidence"] = "raw/func-1.log"
    if matrix.get("artifacts"):
        matrix["artifacts"][0].update(
            {
                "path": "artifacts/fw.bin",
                "sha256": hashlib.sha256(artifact.read_bytes()).hexdigest().upper(),
                "size": artifact.stat().st_size,
            }
        )
    rewrite_contract_and_matrix(contract_path, matrix_path, contract, matrix)
    return contract_path, matrix_path, contract, matrix


def run_main(arguments):
    stdout = io.StringIO()
    stderr = io.StringIO()
    with contextlib.redirect_stdout(stdout), contextlib.redirect_stderr(stderr):
        result = VALIDATOR.main(arguments)
    return result, stdout.getvalue(), stderr.getvalue()


class AcceptanceBundleTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.fixture_temp = tempfile.TemporaryDirectory(
            dir=ROOT, prefix=".acceptance-repo-fixture-"
        )
        cls.repo_root = create_fixture_repo(Path(cls.fixture_temp.name) / "repo")

    @classmethod
    def tearDownClass(cls):
        cls.fixture_temp.cleanup()

    def test_templates_are_valid_json(self):
        contract = json.loads(CONTRACT_TEMPLATE.read_text(encoding="utf-8"))
        matrix = json.loads(MATRIX_TEMPLATE.read_text(encoding="utf-8"))
        self.assertEqual([], VALIDATOR.validate_contract(contract, allow_draft=True))
        self.assertEqual(
            [],
            VALIDATOR.validate_matrix(matrix, contract, "0" * 64, allow_draft=True),
        )

    def test_valid_pass_bundle_is_end_to_end(self):
        with tempfile.TemporaryDirectory(dir=ROOT, prefix=".acceptance-validator-test-") as temp_dir:
            contract_path, matrix_path, _, _ = write_bundle(Path(temp_dir), self.repo_root)
            result, _, stderr = run_main(
                [
                    "--contract",
                    str(contract_path),
                    "--matrix",
                    str(matrix_path),
                    "--repo-root",
                    str(self.repo_root),
                ]
            )
            self.assertEqual(0, result, stderr)

    def test_powershell_manifest_matches_python_worktree_rebuild(self):
        if POWERSHELL is None:
            self.skipTest("PowerShell is unavailable")
        with tempfile.TemporaryDirectory(dir=ROOT, prefix=".acceptance-validator-test-") as temp_dir:
            temp = Path(temp_dir)
            env = os.environ.copy()
            for name in ("TEMP", "TMP", "TMPDIR"):
                env[name] = str(temp)
            for profile in ("Production", "Validation", "Governance"):
                output = self.repo_root / f".manifest-output-{profile.lower()}"
                result = subprocess.run(
                    [
                        POWERSHELL,
                        "-NoProfile",
                        "-ExecutionPolicy",
                        "Bypass",
                        "-File",
                        str(MANIFEST_SCRIPT),
                        "-RepoRoot",
                        str(self.repo_root),
                        "-OutputDirectory",
                        str(output),
                        "-Profile",
                        profile,
                    ],
                    cwd=ROOT,
                    env=env,
                    capture_output=True,
                    text=True,
                )
                self.assertEqual(0, result.returncode, result.stderr)
                manifest = json.loads(
                    (output / "source-manifest.json").read_text(encoding="utf-8-sig")
                )
                self.assertEqual(
                    records_for_profile(profile, self.repo_root), manifest["Files"]
                )
                if profile == "Validation":
                    self.assertIn(
                        "Tools/\u56fe\u6807/README.md",
                        {record["Path"] for record in manifest["Files"]},
                    )

    def test_contract_requires_all_three_manifest_profiles(self):
        contract = valid_contract()
        contract["input_groups"] = contract["input_groups"][:1]
        errors = VALIDATOR.validate_contract(contract)
        self.assertTrue(any("missing required groups" in error for error in errors))

    def test_contract_id_and_parent_must_match_version(self):
        contract = valid_contract()
        contract["contract_id"] = "wrong"
        contract["parent_contract_sha256"] = "A" * 64
        errors = VALIDATOR.validate_contract(contract)
        self.assertTrue(any("contract.contract_id must be" in error for error in errors))
        self.assertTrue(any("must be null for version 1" in error for error in errors))

    def test_criterion_dependencies_must_reference_known_inputs(self):
        contract = valid_contract()
        contract["criteria"][0]["input_groups"] = ["production", "mystery"]
        contract["criteria"][0]["command_ids"] = ["missing-command"]
        errors = VALIDATOR.validate_contract(contract)
        self.assertTrue(any("unknown ids: mystery" in error for error in errors))
        self.assertTrue(any("unknown ids: missing-command" in error for error in errors))

    def test_pass_requires_raw_evidence_commands_and_artifacts(self):
        contract = valid_contract()
        matrix = valid_matrix(contract)
        matrix["criteria"][0]["evidence"] = []
        matrix["commands"] = []
        matrix["artifacts"] = []
        errors = VALIDATOR.validate_matrix(matrix, contract, contract_hash(contract))
        self.assertTrue(any("requires raw evidence" in error for error in errors))
        self.assertTrue(any("missing required commands" in error for error in errors))
        self.assertTrue(any("missing required artifacts" in error for error in errors))
        self.assertTrue(any("overall PASS requires recorded commands" in error for error in errors))
        self.assertTrue(any("overall PASS requires recorded artifacts" in error for error in errors))

    def test_product_fail_requires_command_and_artifact_provenance(self):
        contract = valid_contract()
        matrix = valid_matrix(contract, result="FAIL", owner="product", overall="PRODUCT_FAIL")
        matrix["commands"] = []
        matrix["artifacts"] = []
        errors = VALIDATOR.validate_matrix(matrix, contract, contract_hash(contract))
        self.assertTrue(any("missing required commands" in error for error in errors))
        self.assertTrue(any("missing required artifacts" in error for error in errors))

    def test_evidence_gap_can_remain_not_observed_without_downstream_artifacts(self):
        contract = valid_contract()
        matrix = valid_matrix(contract, result="NOT_OBSERVED", overall="EVIDENCE_GAP")
        self.assertEqual([], VALIDATOR.validate_matrix(matrix, contract, contract_hash(contract)))

    def test_pass_rejects_unexpected_command_exit_and_missing_output(self):
        contract = valid_contract()
        matrix = valid_matrix(contract)
        matrix["commands"][0]["exit_code"] = 1
        matrix["commands"][0]["output_evidence"] = None
        errors = VALIDATOR.validate_matrix(matrix, contract, contract_hash(contract))
        self.assertTrue(any("not an approved expected result" in error for error in errors))
        self.assertTrue(any("must reference hashed evidence" in error for error in errors))

    def test_pass_rejects_command_or_artifact_substitution(self):
        contract = valid_contract()
        matrix = valid_matrix(contract)
        matrix["commands"][0]["command"] = "echo fake-pass"
        matrix["artifacts"][0]["path"] = "artifacts/other.bin"
        errors = VALIDATOR.validate_matrix(matrix, contract, contract_hash(contract))
        self.assertTrue(any("command does not match" in error for error in errors))
        self.assertTrue(any("path does not match" in error for error in errors))

    def test_nonzero_exit_is_allowed_when_frozen_as_expected(self):
        contract = valid_contract()
        contract["commands"][0]["expected_exit_codes"] = [1]
        matrix = valid_matrix(contract)
        matrix["contract_sha256"] = contract_hash(contract)
        matrix["commands"][0]["exit_code"] = 1
        self.assertEqual([], VALIDATOR.validate_matrix(matrix, contract, contract_hash(contract)))

    def test_pass_observed_value_must_satisfy_gate(self):
        contract = valid_contract()
        matrix = valid_matrix(contract)
        matrix["criteria"][0]["observed"] = False
        errors = VALIDATOR.validate_matrix(matrix, contract, contract_hash(contract))
        self.assertTrue(any("does not satisfy the frozen gate" in error for error in errors))

    def test_artifact_path_must_stay_inside_bundle(self):
        contract = valid_contract()
        matrix = valid_matrix(contract)
        matrix["artifacts"][0]["path"] = "../../missing.bin"
        errors = VALIDATOR.validate_matrix(matrix, contract, contract_hash(contract))
        self.assertTrue(any("path must stay inside the bundle" in error for error in errors))

    def test_artifact_file_size_and_hash_are_verified(self):
        with tempfile.TemporaryDirectory(dir=ROOT, prefix=".acceptance-validator-test-") as temp_dir:
            bundle = Path(temp_dir)
            contract_path, matrix_path, _, matrix = write_bundle(bundle, self.repo_root)
            matrix["artifacts"][0]["size"] += 1
            matrix_path.write_text(json.dumps(matrix, indent=2) + "\n", encoding="utf-8")
            result, _, stderr = run_main(
                [
                    "--contract",
                    str(contract_path),
                    "--matrix",
                    str(matrix_path),
                    "--repo-root",
                    str(self.repo_root),
                ]
            )
            self.assertEqual(1, result)
            self.assertIn("artifact size mismatch", stderr)
            matrix["artifacts"][0]["size"] -= 1
            matrix["artifacts"][0]["sha256"] = "0" * 64
            matrix_path.write_text(json.dumps(matrix, indent=2) + "\n", encoding="utf-8")
            result, _, stderr = run_main(
                [
                    "--contract",
                    str(contract_path),
                    "--matrix",
                    str(matrix_path),
                    "--repo-root",
                    str(self.repo_root),
                ]
            )
            self.assertEqual(1, result)
            self.assertIn("artifact SHA-256 mismatch", stderr)
            (bundle / "artifacts" / "fw.bin").unlink()
            result, _, stderr = run_main(
                [
                    "--contract",
                    str(contract_path),
                    "--matrix",
                    str(matrix_path),
                    "--repo-root",
                    str(self.repo_root),
                ]
            )
            self.assertEqual(1, result)
            self.assertIn("artifact file is missing", stderr)

    def test_input_manifests_verify_json_and_stable_hashes(self):
        with tempfile.TemporaryDirectory(dir=ROOT, prefix=".acceptance-validator-test-") as temp_dir:
            bundle = Path(temp_dir)
            _, _, contract, _ = write_bundle(bundle, self.repo_root)
            self.assertEqual(
                [],
                VALIDATOR.validate_input_manifests(contract, bundle, self.repo_root),
            )
            contract["input_groups"][0]["manifest_json_sha256"] = "0" * 64
            errors = VALIDATOR.validate_input_manifests(contract, bundle, self.repo_root)
            self.assertTrue(any("JSON SHA-256 mismatch" in error for error in errors))

    def test_empty_manifest_is_rejected_end_to_end(self):
        with tempfile.TemporaryDirectory(dir=ROOT, prefix=".acceptance-validator-test-") as temp_dir:
            bundle = Path(temp_dir)
            contract_path, matrix_path, contract, matrix = write_bundle(
                bundle, self.repo_root
            )
            write_input_manifest(bundle, contract["input_groups"][0], records=[])
            rewrite_contract_and_matrix(contract_path, matrix_path, contract, matrix)
            result, _, stderr = run_main(
                [
                    "--contract",
                    str(contract_path),
                    "--matrix",
                    str(matrix_path),
                    "--repo-root",
                    str(self.repo_root),
                ]
            )
            self.assertEqual(1, result)
            self.assertIn("Files must be a non-empty list", stderr)

    def test_manifest_rejects_forged_internal_hash_and_missing_text(self):
        with tempfile.TemporaryDirectory(dir=ROOT, prefix=".acceptance-validator-test-") as temp_dir:
            bundle = Path(temp_dir)
            _, _, contract, _ = write_bundle(bundle, self.repo_root)
            group = contract["input_groups"][0]
            manifest_path = bundle / group["manifest_path"]
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
            manifest["ManifestSHA256"] = "0" * 64
            manifest_path.write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
            group["manifest_json_sha256"] = hashlib.sha256(manifest_path.read_bytes()).hexdigest().upper()
            manifest_path.with_name("source-manifest.txt").unlink()
            errors = VALIDATOR.validate_input_manifests(contract, bundle, self.repo_root)
            self.assertTrue(any("stable SHA-256 mismatch" in error for error in errors))
            self.assertTrue(any("text file is missing" in error for error in errors))

    def test_manifest_rejects_out_of_order_duplicate_and_missing_required_paths(self):
        with tempfile.TemporaryDirectory(dir=ROOT, prefix=".acceptance-validator-test-") as temp_dir:
            bundle = Path(temp_dir)
            _, _, contract, _ = write_bundle(bundle, self.repo_root)
            group = contract["input_groups"][1]
            records = records_for_profile("Validation", self.repo_root)
            records[0], records[1] = records[1], records[0]
            write_input_manifest(bundle, group, records)
            errors = VALIDATOR.validate_input_manifests(contract, bundle, self.repo_root)
            self.assertTrue(any("not in ordinal order" in error for error in errors))

            records = records_for_profile("Validation", self.repo_root)
            records[1] = copy.deepcopy(records[0])
            write_input_manifest(bundle, group, records)
            errors = VALIDATOR.validate_input_manifests(contract, bundle, self.repo_root)
            self.assertTrue(any("duplicate paths" in error for error in errors))

            records = records_for_profile("Validation", self.repo_root)[1:]
            write_input_manifest(bundle, group, records)
            errors = VALIDATOR.validate_input_manifests(contract, bundle, self.repo_root)
            self.assertTrue(any("missing required Validation paths" in error for error in errors))

    def test_manifest_rejects_self_consistent_forged_worktree_records(self):
        with tempfile.TemporaryDirectory(dir=ROOT, prefix=".acceptance-validator-test-") as temp_dir:
            bundle = Path(temp_dir)
            _, _, contract, _ = write_bundle(bundle, self.repo_root)
            group = contract["input_groups"][0]
            records = records_for_profile("Production", self.repo_root)
            records[0]["Length"] += 7
            records[0]["SHA256"] = "A" * 64
            write_input_manifest(bundle, group, records)
            errors = VALIDATOR.validate_input_manifests(contract, bundle, self.repo_root)
            self.assertTrue(any("worktree length mismatch" in error for error in errors))
            self.assertTrue(any("worktree SHA-256 mismatch" in error for error in errors))

    def test_production_manifest_cannot_omit_real_rte_inputs(self):
        with tempfile.TemporaryDirectory(dir=ROOT, prefix=".acceptance-validator-test-") as temp_dir:
            bundle = Path(temp_dir)
            _, _, contract, _ = write_bundle(bundle, self.repo_root)
            group = contract["input_groups"][0]
            records = [
                record
                for record in records_for_profile("Production", self.repo_root)
                if not record["Path"].startswith("MDK-ARM_F435/RTE/")
            ]
            write_input_manifest(bundle, group, records)
            errors = VALIDATOR.validate_input_manifests(contract, bundle, self.repo_root)
            self.assertTrue(any("missing worktree files for Production" in error for error in errors))
            self.assertTrue(any("MDK-ARM_F435/RTE/" in error for error in errors))

    def test_historical_performance_gate_is_rejected(self):
        contract = valid_contract()
        contract["performance_gates"] = [
            {
                "id": "PERF-1",
                "metric": "input_to_list",
                "limit": 917,
                "unit": "ms",
                "basis": "historical_measurement",
                "rationale": "817 ms plus a 100 ms polling interval",
            }
        ]
        errors = VALIDATOR.validate_contract(contract)
        self.assertTrue(any("historical measurement" in error for error in errors))

    def test_performance_criterion_cannot_use_frozen_requirement_basis(self):
        contract = valid_contract()
        contract["criteria"][0]["kind"] = "performance"
        errors = VALIDATOR.validate_contract(contract)
        self.assertTrue(any("gate.basis for performance" in error for error in errors))

    def test_overall_result_must_match_failure_owner(self):
        contract = valid_contract()
        matrix = valid_matrix(contract, result="FAIL", owner="harness", overall="PRODUCT_FAIL")
        errors = VALIDATOR.validate_matrix(matrix, contract, contract_hash(contract))
        self.assertTrue(any("product-owned failure" in error for error in errors))
        matrix["overall_result"] = "HARNESS_FAIL"
        self.assertEqual([], VALIDATOR.validate_matrix(matrix, contract, contract_hash(contract)))

    def test_rerun_ignores_manifest_packaging_metadata(self):
        previous_contract = valid_contract()
        previous_matrix = valid_matrix(previous_contract)
        current = successor_contract(previous_contract)
        current["input_groups"][0]["manifest_path"] = "other-root/source-manifest.json"
        current["input_groups"][0]["manifest_json_sha256"] = "F" * 64
        plan = VALIDATOR.compute_rerun_plan(current, previous_contract, previous_matrix)
        self.assertEqual([], plan["rerun_criteria"])
        self.assertEqual(["FUNC-1"], plan["reusable_criteria"])

    def test_rerun_invalidates_only_when_stable_input_hash_changes(self):
        previous_contract = valid_contract()
        previous_matrix = valid_matrix(previous_contract)
        current = successor_contract(previous_contract)
        current["input_groups"][1]["manifest_sha256"] = "F" * 64
        plan = VALIDATOR.compute_rerun_plan(current, previous_contract, previous_matrix)
        self.assertEqual(["FUNC-1"], [item["id"] for item in plan["rerun_criteria"]])
        self.assertIn("input_group_changed:validation", plan["rerun_criteria"][0]["reasons"])
        self.assertEqual(["CMD-FUNC-1"], plan["required_commands"])
        self.assertEqual(["ART-FIRMWARE"], plan["required_artifacts"])

    def test_rerun_rejects_cross_task_same_version_and_wrong_parent(self):
        previous_contract = valid_contract()
        previous_matrix = valid_matrix(previous_contract)

        cross_task = successor_contract(previous_contract)
        cross_task["task_id"] = "P9-9"
        cross_task["contract_id"] = "P9-9-v2"
        with self.assertRaisesRegex(ValueError, "task_id"):
            VALIDATOR.compute_rerun_plan(cross_task, previous_contract, previous_matrix)

        same_version = copy.deepcopy(previous_contract)
        same_version["input_groups"][0]["manifest_sha256"] = "F" * 64
        with self.assertRaisesRegex(ValueError, "next contract version"):
            VALIDATOR.compute_rerun_plan(same_version, previous_contract, previous_matrix)

        wrong_parent = successor_contract(previous_contract)
        wrong_parent["parent_contract_sha256"] = "0" * 64
        with self.assertRaisesRegex(ValueError, "parent_contract_sha256"):
            VALIDATOR.compute_rerun_plan(wrong_parent, previous_contract, previous_matrix)

    def test_reuse_is_rejected_when_dependency_changed(self):
        previous_contract = valid_contract()
        previous_matrix = valid_matrix(previous_contract)
        current_contract = successor_contract(previous_contract)
        current_contract["input_groups"][0]["manifest_sha256"] = "F" * 64
        current_matrix = copy.deepcopy(previous_matrix)
        current_matrix["contract_id"] = current_contract["contract_id"]
        current_matrix["criteria"][0]["execution"] = "REUSED"
        current_matrix["criteria"][0]["reused_from_round"] = previous_matrix["round_id"]
        plan = VALIDATOR.compute_rerun_plan(current_contract, previous_contract, previous_matrix)
        errors = VALIDATOR.validate_reuse(
            current_matrix,
            current_contract,
            previous_matrix,
            plan,
        )
        self.assertTrue(any("reuses invalidated evidence" in error for error in errors))

    def test_reused_result_cannot_be_reused_again(self):
        previous_contract = valid_contract()
        previous_matrix = valid_matrix(previous_contract)
        previous_matrix["criteria"][0]["execution"] = "REUSED"
        previous_matrix["criteria"][0]["reused_from_round"] = "older-round"
        current_contract = copy.deepcopy(previous_contract)
        plan = VALIDATOR.compute_rerun_plan(
            current_contract,
            previous_contract,
            previous_matrix,
            current_round_id="new-round",
        )
        self.assertEqual(["FUNC-1"], [item["id"] for item in plan["rerun_criteria"]])
        self.assertIn("previous_result_not_executed", plan["rerun_criteria"][0]["reasons"])

    def test_rerun_plan_cli_writes_an_enforced_plan_inside_bundle(self):
        with tempfile.TemporaryDirectory(dir=ROOT, prefix=".acceptance-validator-test-") as temp_dir:
            root = Path(temp_dir)
            previous_dir = root / "previous"
            current_dir = root / "current"
            previous_dir.mkdir()
            current_dir.mkdir()
            (
                previous_contract_path,
                previous_matrix_path,
                previous_contract,
                previous_matrix,
            ) = write_bundle(previous_dir, self.repo_root)

            current_contract = copy.deepcopy(previous_contract)
            current_matrix = valid_matrix(current_contract)
            current_matrix["round_id"] = "20260815-120000"
            current_contract_path, current_matrix_path, _, _ = write_bundle(
                current_dir,
                self.repo_root,
                current_contract,
                current_matrix,
            )
            base_args = [
                "--contract",
                str(current_contract_path),
                "--matrix",
                str(current_matrix_path),
                "--repo-root",
                str(self.repo_root),
                "--previous-contract",
                str(previous_contract_path),
                "--previous-matrix",
                str(previous_matrix_path),
                "--previous-repo-root",
                str(self.repo_root),
            ]
            result, stdout, stderr = run_main(
                base_args + ["--write-rerun-plan", "rerun-plan.json"]
            )
            self.assertEqual(0, result, stderr)
            self.assertIn("reusable=1", stdout)
            plan_path = current_dir / "rerun-plan.json"
            plan_bytes = plan_path.read_bytes()
            plan = json.loads(plan_bytes.decode("utf-8"))
            self.assertEqual("same_contract", plan["contract_lineage"])
            self.assertEqual(["FUNC-1"], plan["reusable_criteria"])

            current_matrix = json.loads(current_matrix_path.read_text(encoding="utf-8"))
            current_matrix["criteria"][0]["execution"] = "REUSED"
            current_matrix["criteria"][0]["reused_from_round"] = previous_matrix["round_id"]
            current_matrix["previous_matrix_sha256"] = hashlib.sha256(
                previous_matrix_path.read_bytes()
            ).hexdigest().upper()
            current_matrix["rerun_plan_path"] = "rerun-plan.json"
            current_matrix["rerun_plan_sha256"] = hashlib.sha256(plan_bytes).hexdigest().upper()
            current_matrix_path.write_text(
                json.dumps(current_matrix, indent=2) + "\n", encoding="utf-8"
            )

            plan_path.unlink()
            result, _, stderr = run_main(base_args)
            self.assertEqual(1, result)
            self.assertIn("rerun plan file is missing", stderr)

            plan_path.write_bytes(plan_bytes)
            current_matrix["rerun_plan_sha256"] = "0" * 64
            current_matrix_path.write_text(
                json.dumps(current_matrix, indent=2) + "\n", encoding="utf-8"
            )
            result, _, stderr = run_main(base_args)
            self.assertEqual(1, result)
            self.assertIn("rerun plan SHA-256 mismatch", stderr)

            current_matrix["rerun_plan_sha256"] = hashlib.sha256(plan_bytes).hexdigest().upper()
            current_matrix_path.write_text(
                json.dumps(current_matrix, indent=2) + "\n", encoding="utf-8"
            )
            result, _, stderr = run_main(base_args)
            self.assertEqual(0, result, stderr)

    def test_rerun_plan_output_rejects_symlink_parent(self):
        with tempfile.TemporaryDirectory(dir=ROOT, prefix=".acceptance-validator-test-") as temp_dir:
            root = Path(temp_dir)
            previous_dir = root / "previous"
            current_dir = root / "current"
            outside_dir = root / "outside-plan-target"
            previous_dir.mkdir()
            current_dir.mkdir()
            outside_dir.mkdir()
            previous_contract_path, previous_matrix_path, previous_contract, _ = write_bundle(
                previous_dir, self.repo_root
            )
            current_contract = copy.deepcopy(previous_contract)
            current_matrix = valid_matrix(current_contract)
            current_matrix["round_id"] = "20260815-130000"
            current_contract_path, current_matrix_path, _, _ = write_bundle(
                current_dir,
                self.repo_root,
                current_contract,
                current_matrix,
            )
            link = current_dir / "linked-output"
            try:
                link.symlink_to(outside_dir, target_is_directory=True)
            except OSError as exc:
                self.skipTest(f"symlink creation is unavailable: {exc}")

            result, _, stderr = run_main(
                [
                    "--contract",
                    str(current_contract_path),
                    "--matrix",
                    str(current_matrix_path),
                    "--repo-root",
                    str(self.repo_root),
                    "--previous-contract",
                    str(previous_contract_path),
                    "--previous-matrix",
                    str(previous_matrix_path),
                    "--previous-repo-root",
                    str(self.repo_root),
                    "--write-rerun-plan",
                    "linked-output/rerun-plan.json",
                ]
            )
            self.assertEqual(1, result)
            self.assertIn("link or reparse point", stderr)
            self.assertFalse((outside_dir / "rerun-plan.json").exists())

    def test_rerun_plan_output_walks_parent_chain_without_symlink_privilege(self):
        with tempfile.TemporaryDirectory(dir=ROOT, prefix=".acceptance-validator-test-") as temp_dir:
            bundle_root = Path(temp_dir).resolve()
            blocked_parent = bundle_root / "blocked-parent"
            original_check = VALIDATOR._is_link_or_reparse

            def fake_link_check(path):
                return path == blocked_parent or original_check(path)

            with mock.patch.object(VALIDATOR, "_is_link_or_reparse", side_effect=fake_link_check):
                with self.assertRaisesRegex(ValueError, "link or reparse point"):
                    VALIDATOR._resolve_bundle_output(
                        bundle_root,
                        "blocked-parent/rerun-plan.json",
                    )

    def test_same_matrix_cannot_reuse_itself(self):
        with tempfile.TemporaryDirectory(dir=ROOT, prefix=".acceptance-validator-test-") as temp_dir:
            bundle = Path(temp_dir)
            contract_path, matrix_path, _, matrix = write_bundle(bundle, self.repo_root)
            matrix["criteria"][0]["execution"] = "REUSED"
            matrix["criteria"][0]["reused_from_round"] = matrix["round_id"]
            matrix["previous_matrix_sha256"] = "A" * 64
            matrix["rerun_plan_path"] = "rerun-plan.json"
            matrix["rerun_plan_sha256"] = "B" * 64
            matrix_path.write_text(json.dumps(matrix, indent=2) + "\n", encoding="utf-8")
            result, _, stderr = run_main(
                [
                    "--contract",
                    str(contract_path),
                    "--matrix",
                    str(matrix_path),
                    "--repo-root",
                    str(self.repo_root),
                    "--previous-contract",
                    str(contract_path),
                    "--previous-matrix",
                    str(matrix_path),
                    "--previous-repo-root",
                    str(self.repo_root),
                ]
            )
            self.assertEqual(1, result)
            self.assertIn("current and previous matrix files must be different", stderr)
            self.assertIn("round_id must be different", stderr)


class GovernancePromptScopeTests(unittest.TestCase):
    """守护 docs/ota-prompts/ 不再脱离 Governance profile 与治理 workflow。

    P2-6 派单前置复审发现:派单提示词此前放在 `.claude/`,既不在任何 manifest
    profile 内,也不触发 Acceptance Governance,提示词可被静默替换而无人发现。
    本组测试把「规范文件受治理」变成可执行断言,防止目录被移回或从 profile 摘除。
    """

    PROMPT_DIR = "docs/ota-prompts/"
    REQUIRED_TEMPLATES = (
        "docs/ota-prompts/prompt-template-acceptance.md",
        "docs/ota-prompts/prompt-template-implementation.md",
    )
    # OTA 派单规范文件:卡提示词与两份模板。不含与 OTA 无关的一次性工具提示词。
    #
    # 识别口径按「卡号前缀」而非「-implementation/-acceptance 后缀」:P2-6 派单前置
    # 复审发现 `.claude/prompt-p2-3-bspatch.md` 这类自定义后缀的卡提示词能绕过后缀
    # 白名单,静默停留在不受 manifest 与治理 CI 约束的目录里。凡带 `PRE`/`P<数字>`
    # 卡号的 prompt 一律视为派单提示词;不带卡号的工具提示词
    # (如 `prompt-keil2cmake-portable.md`)不受本约束。
    DISPATCH_PROMPT_RE = re.compile(
        r"^prompt-(?:template-(?:implementation|acceptance)"
        r"|(?:PRE|P\d+)(?:[-_][^/\\]*)?)\.md$",
        re.IGNORECASE,
    )
    @staticmethod
    def enumerate_repo_markdown():
        """全仓枚举 .md(已跟踪 + 未跟踪未忽略),返回 posix 相对路径列表。

        用 `git ls-files -co --exclude-standard` 而不是若干目录的 rglob:
        P2-6 派单前置第三轮复核指出,按目录白名单扫描(`.claude` 全树 +
        仓库顶层 + `docs/` 顶层)漏掉任意嵌套位置 —— `docs/archive/`、
        `notes/`、`scripts/prompts/` 下的派单提示词照样能绕过治理。实测把
        `prompt-P9-7-bspatch.md` 放进 `notes/deep/` 时,旧口径零命中而
        `git ls-files` 命中。

        `-z` 保证含中文的仓库路径不被 git 的 quotepath 转义,因此按字节读
        再解码。枚举失败必须抛错(fail-closed):静默返回空列表会让
        stray 检查退化成恒真断言。
        """
        proc = subprocess.run(
            ["git", "ls-files", "-co", "--exclude-standard", "-z", "--", "*.md"],
            cwd=ROOT,
            capture_output=True,
        )
        if proc.returncode != 0:
            raise RuntimeError(
                "git ls-files 枚举失败,无法判定派单提示词位置: "
                + proc.stderr.decode("utf-8", "replace")
            )
        return [
            chunk.decode("utf-8")
            for chunk in proc.stdout.split(b"\0")
            if chunk
        ]

    @classmethod
    def find_stray_dispatch_prompts(cls, paths):
        """从全仓 .md 列表里挑出落在 docs/ota-prompts/ 之外的派单提示词。"""
        return sorted(
            path
            for path in paths
            if not path.startswith(cls.PROMPT_DIR)
            and cls.DISPATCH_PROMPT_RE.match(path.rsplit("/", 1)[-1])
        )

    def test_prompt_dir_is_in_governance_profile(self):
        governance = VALIDATOR.PROFILE_DEFINITIONS["Governance"]
        self.assertIn(
            self.PROMPT_DIR,
            governance["root_patterns"],
            "Governance profile 必须覆盖 docs/ota-prompts/,否则提示词不受指纹绑定",
        )
        for template in self.REQUIRED_TEMPLATES:
            self.assertIn(
                template,
                governance["required_paths"],
                f"{template} 必须是 Governance 的 required_paths,缺失时 manifest 可静默漏掉模板",
            )

    def test_prompt_files_are_enumerated_by_governance_profile(self):
        paths = set(VALIDATOR._profile_paths(ROOT, "Governance"))
        tracked = {
            path
            for path in paths
            if path.startswith(self.PROMPT_DIR)
        }
        self.assertTrue(
            tracked,
            "Governance profile 实际枚举结果里没有任何 docs/ota-prompts/ 文件",
        )
        on_disk = {
            f"{self.PROMPT_DIR}{item.name}"
            for item in (ROOT / "docs" / "ota-prompts").glob("*.md")
        }
        self.assertEqual(
            on_disk,
            tracked,
            "docs/ota-prompts/ 下的 .md 必须全部被 Governance profile 枚举到",
        )

    def test_governance_workflow_watches_prompt_dir(self):
        workflow = (
            ROOT / ".github" / "workflows" / "acceptance-governance.yml"
        ).read_text(encoding="utf-8")
        occurrences = workflow.count('- "docs/ota-prompts/**"')
        self.assertEqual(
            2,
            occurrences,
            "acceptance-governance.yml 的 push 与 pull_request 都必须监听 docs/ota-prompts/**",
        )

    def test_dispatch_prompts_do_not_live_outside_governed_dir(self):
        stray = self.find_stray_dispatch_prompts(self.enumerate_repo_markdown())
        self.assertEqual(
            [],
            stray,
            "派单提示词必须放在 docs/ota-prompts/ 下,"
            "其余任何位置(`.claude/`、仓库顶层、`docs/` 任意子目录、"
            "`notes/`、`scripts/` 等)都不受治理 CI 与 manifest 约束",
        )

    def test_repo_wide_enumeration_reaches_nested_dirs(self):
        """负例:确认枚举口径真能覆盖任意深度,而不是只扫几个白名单目录。

        没有这条断言时,把 enumerate_repo_markdown 退回浅层 glob 仍会让上一个
        测试全绿 —— 「零 stray」只证明搜索范围写窄了。探针文件放在仓库内的深层
        临时目录(未被 gitignore,因此必须被 `git ls-files -co` 看见),
        用完即删;同类测试在 unittest 下串行执行,不会互相误判。
        """
        with tempfile.TemporaryDirectory(
            dir=ROOT, prefix=".dispatch-scope-probe-"
        ) as tmp:
            probe = Path(tmp) / "docs" / "archive" / "prompt-P9-7-bspatch.md"
            probe.parent.mkdir(parents=True, exist_ok=True)
            probe.write_text("probe\n", encoding="utf-8")
            rel = probe.relative_to(ROOT).as_posix()

            enumerated = self.enumerate_repo_markdown()
            self.assertIn(
                rel,
                enumerated,
                "git ls-files 全仓枚举必须看见深层嵌套的 .md,"
                "否则派单提示词可藏进任意子目录绕过治理",
            )
            self.assertGreaterEqual(
                rel.count("/"),
                3,
                "探针必须位于足够深的嵌套目录才有鉴别力",
            )
            self.assertIn(
                rel,
                self.find_stray_dispatch_prompts(enumerated),
                "深层嵌套的自定义后缀卡提示词必须被判为 stray",
            )

    def test_dispatch_prompt_pattern_has_discriminating_power(self):
        """负例:确认该正则真能识别自定义后缀的卡提示词,且不误伤工具提示词。

        没有这组断言时,正则写窄(例如只认 `-implementation`/`-acceptance` 后缀)
        仍会让上一个测试全绿,「零命中」只证明搜索条件写错了。
        """
        must_match = (
            "prompt-P2-6-implementation.md",
            "prompt-P1-7-acceptance.md",
            "prompt-PRE-4-implementation.md",
            "prompt-p2-3-bspatch.md",  # 实际出现过的自定义后缀
            "prompt-P2-6.md",  # 无后缀
            "prompt-P10-1-implementation.md",  # 两位卡号
            "prompt-template-implementation.md",
            "prompt-template-acceptance.md",
        )
        for name in must_match:
            with self.subTest(name=name):
                self.assertIsNotNone(
                    self.DISPATCH_PROMPT_RE.match(name),
                    f"{name} 应被识别为派单提示词",
                )
        must_not_match = (
            "prompt-keil2cmake-portable.md",  # 与 OTA 无关的一次性工具提示词
            "verification-report-ota-plan.md",
            "context-summary-dialplate-hud.md",
            "prompt-P2-6-implementation.txt",
        )
        for name in must_not_match:
            with self.subTest(name=name):
                self.assertIsNone(
                    self.DISPATCH_PROMPT_RE.match(name),
                    f"{name} 不应被判为派单提示词(会误伤非 OTA 文件)",
                )


class SpecProbeCiWiringTests(unittest.TestCase):
    """守护 P2-6 Spec 探针的远端 CI 接线(2026-08-16 定向复核阻断 2)。

    此前 8 组探针只在本机跑过:`acceptance-governance.yml` 既不监听
    `tests/ota/spec-probes/**`,执行步骤里也没有 `run_all.py`;`firmware-build.yml`
    同样不监听该目录。后果是「远端 Acceptance Governance 变绿」不能证明探针通过,
    而且以后单独修改探针不会触发任何 workflow —— 探针可被静默改坏或删空。

    探针刻意挂在治理工作流而不是固件工作流:它们只需要 arm-none-eabi 工具链与
    宿主 gcc,不需要完整 App+Boot 构建。本组测试把「路径过滤 + 固定工具链版本 +
    执行命令」三件事变成可执行断言,任一被移除即本地与 CI 双红。
    """

    WORKFLOW = ROOT / ".github" / "workflows" / "acceptance-governance.yml"
    FIRMWARE_WORKFLOW = ROOT / ".github" / "workflows" / "firmware-build.yml"
    PROBE_PATH_FILTER = '- "tests/ota/spec-probes/**"'
    TOOLCHAIN_ACTION = "carlosperate/arm-none-eabi-gcc-action@v1"
    TOOLCHAIN_RELEASE = "13.3.Rel1"
    PROBE_COMMAND = "python3 tests/ota/spec-probes/p2-6/run_all.py"
    PROBE_DIR = "tests/ota/spec-probes/"
    AGGREGATOR = "tests/ota/spec-probes/p2-6/run_all.py"
    SELFTEST = "tests/ota/spec-probes/p2-6/selftest/classification_selftest.py"
    # 探针条目数与 run_all.py 的冻结值必须一致。只靠 run_all.py 自己的
    # `EXPECTED_PROBE_COUNT` 门禁不够:同时把 PROBES 删到 1 项、把冻结值改成 1,
    # 运行期门禁依然通过,CI 会以「1/1 通过」变绿。这里在治理侧再钉一次真值。
    EXPECTED_PROBE_COUNT = 8

    @classmethod
    def setUpClass(cls):
        cls.workflow = cls.WORKFLOW.read_text(encoding="utf-8")

    def parse_run_all_constants(self):
        """静态解析 run_all.py 的 PROBES 与 EXPECTED_PROBE_COUNT(不导入模块)。

        用 ast 而不是 import:导入会执行 `_probe_env` 的 stdout 重配置等副作用,
        治理测试不应被被测 harness 改变自身运行环境。
        """
        source = (ROOT / self.AGGREGATOR).read_text(encoding="utf-8")
        values = {}
        for node in ast.parse(source).body:
            if not isinstance(node, ast.Assign) or len(node.targets) != 1:
                continue
            target = node.targets[0]
            if isinstance(target, ast.Name) and target.id in (
                "PROBES",
                "EXPECTED_PROBE_COUNT",
            ):
                values[target.id] = ast.literal_eval(node.value)
        missing = {"PROBES", "EXPECTED_PROBE_COUNT"} - set(values)
        self.assertEqual(
            set(),
            missing,
            f"run_all.py 缺少顶层常量 {sorted(missing)},探针条目数无法被静态核对",
        )
        return values["PROBES"], values["EXPECTED_PROBE_COUNT"]

    def test_governance_workflow_watches_spec_probe_dir(self):
        occurrences = self.workflow.count(self.PROBE_PATH_FILTER)
        self.assertEqual(
            2,
            occurrences,
            "acceptance-governance.yml 的 push 与 pull_request 都必须监听 "
            "tests/ota/spec-probes/**,否则单独改探针不触发任何 workflow",
        )

    def test_governance_workflow_pins_toolchain_used_by_probes(self):
        self.assertIn(
            self.TOOLCHAIN_ACTION,
            self.workflow,
            "治理工作流必须安装 arm-none-eabi 工具链,"
            "否则探针只会以 ENV_BLOCKED 收场(rc=2),证明不了任何 Spec 结论",
        )
        self.assertIn(
            f'release: "{self.TOOLCHAIN_RELEASE}"',
            self.workflow,
            f"工具链版本必须固定为 {self.TOOLCHAIN_RELEASE}:"
            "探针里的栈帧字节数、.su 数值、内联折叠结论都绑定到具体版本",
        )
        for floating in ('release: "latest"', "release: latest"):
            self.assertNotIn(
                floating,
                self.workflow,
                "不得使用浮动版本:工具链一升级,冻结的数值基线会无声漂移",
            )
        firmware = self.FIRMWARE_WORKFLOW.read_text(encoding="utf-8")
        self.assertIn(
            f'release: "{self.TOOLCHAIN_RELEASE}"',
            firmware,
            "治理工作流与固件工作流必须用同一工具链版本,"
            "否则探针结论与生产固件不是同一编译器行为",
        )

    def test_governance_workflow_runs_probe_aggregator(self):
        self.assertIn(
            self.PROBE_COMMAND,
            self.workflow,
            f"治理工作流必须执行 {self.PROBE_COMMAND};"
            "只监听路径不执行等于没有接线",
        )
        self.assertTrue(
            (ROOT / self.AGGREGATOR).is_file(),
            f"{self.AGGREGATOR} 必须实际存在,workflow 不得指向已改名/已删除的入口",
        )

    def test_toolchain_install_precedes_probe_run(self):
        install_at = self.workflow.find(self.TOOLCHAIN_ACTION)
        run_at = self.workflow.find(self.PROBE_COMMAND)
        self.assertNotEqual(-1, install_at)
        self.assertNotEqual(-1, run_at)
        self.assertLess(
            install_at,
            run_at,
            "工具链安装步骤必须排在探针执行步骤之前,"
            "顺序颠倒时 arm-none-eabi-gcc 不在 PATH 上,整轮只会得到 ENV_BLOCKED",
        )

    def test_probe_sources_are_enumerated_by_validation_profile(self):
        paths = set(VALIDATOR._profile_paths(ROOT, "Validation"))
        for required in (self.AGGREGATOR, self.SELFTEST):
            self.assertIn(
                required,
                paths,
                f"{required} 必须被 Validation profile 枚举到,"
                "否则探针与自检可被替换而不改变任何 manifest 指纹",
            )
        on_disk = {
            path.relative_to(ROOT).as_posix()
            for path in (ROOT / "tests" / "ota" / "spec-probes").rglob("*")
            if path.is_file() and "__pycache__" not in path.parts
        }
        self.assertEqual(
            set(),
            on_disk - paths,
            "探针目录下的文件必须全部落在 Validation profile 内(生成物不得入库)",
        )

    def test_probe_entries_match_frozen_count_and_exist(self):
        probes, frozen = self.parse_run_all_constants()
        self.assertEqual(
            self.EXPECTED_PROBE_COUNT,
            frozen,
            "run_all.py 的 EXPECTED_PROBE_COUNT 被改动:"
            "同时下调冻结值与条目数会让运行期门禁失效",
        )
        self.assertEqual(
            self.EXPECTED_PROBE_COUNT,
            len(probes),
            f"PROBES 必须保持 {self.EXPECTED_PROBE_COUNT} 项",
        )
        for name, relative, _purpose in probes:
            with self.subTest(probe=name):
                script = ROOT / "tests" / "ota" / "spec-probes" / "p2-6" / relative
                self.assertTrue(
                    script.is_file(),
                    f"探针 {name} 的脚本 {relative} 不存在:"
                    "缺脚本时 run_all.py 会记 HARNESS_FAIL,但入库前就该被拦住",
                )


if __name__ == "__main__":
    unittest.main()
