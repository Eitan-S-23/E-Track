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
import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest import mock


ROOT = Path(__file__).resolve().parents[2]
VALIDATOR_PATH = ROOT / "Tools" / "acceptance" / "validate_bundle.py"
CONTRACT_TEMPLATE = ROOT / "docs" / "acceptance-contracts" / "template.contract.json"
MATRIX_TEMPLATE = ROOT / "docs" / "acceptance-contracts" / "template.evidence-matrix.json"
FREEZE_INDEX = ROOT / "docs" / "acceptance-contracts" / "FREEZE-INDEX.md"
PROFILE_CONFIG_PATH = ROOT / "Tools" / "provenance" / "manifest_profiles.json"
BOARD_PATH = "PLAN-OTA-EXEC.md"
SYMLINK_TEST_REQUIRED_ENV = "OTA_REQUIRE_SYMLINK_TEST"
# 合同单元测试用的占位冻结点：格式合法（40-hex），但不指向任何真实对象；
# 凡要走 git 对象核对的用例都必须改用 fixture 仓库的真实提交（见 write_bundle）。
PLACEHOLDER_OID = "0" * 40
ABSENT_OID = "1" * 40

SPEC = importlib.util.spec_from_file_location("acceptance_validator", VALIDATOR_PATH)
VALIDATOR = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(VALIDATOR)


def symlink_security_test_required():
    return (
        os.environ.get(SYMLINK_TEST_REQUIRED_ENV) == "1"
        or os.environ.get("GITHUB_ACTIONS", "").lower() == "true"
    )


def valid_contract():
    return {
        "schema": "etrack-acceptance-contract-v3",
        "contract_id": "P2-6-v1",
        "version": 1,
        "task_id": "P2-6",
        "parent_contract_sha256": None,
        "status": "FROZEN",
        "approved_by": "user",
        "approved_at": "2026-08-14T12:00:00+08:00",
        "implementation_ref": "0123456789abcdef",
        "freeze_commit": PLACEHOLDER_OID,
        "freeze_tree": PLACEHOLDER_OID,
        "profile_config_blob": PLACEHOLDER_OID,
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
            },
            {
                "id": "validation",
                "profile": "Validation",
                "category": "validation_inputs",
            },
            {
                "id": "governance",
                "profile": "Governance",
                "category": "governance_inputs",
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
                "dependency_rationale": (
                    "Production supplies the firmware, Validation the runner, "
                    "and Governance the process assertions in this combined fixture."
                ),
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


def git_fixture(repo_root, *arguments):
    result = subprocess.run(
        [
            "git",
            "-C",
            str(repo_root),
            "-c",
            "core.quotepath=false",
            "-c",
            "user.name=fixture",
            "-c",
            "user.email=fixture@example.invalid",
            "-c",
            f"core.hooksPath={repo_root / '.no-hooks'}",
            *arguments,
        ],
        check=True,
        cwd=ROOT,
        capture_output=True,
    )
    return result.stdout.decode("utf-8").strip()


def commit_fixture_files(repo_root, files, message="fixture"):
    """\u5199\u5165\u5e76\u63d0\u4ea4\u4e00\u7ec4\u6587\u4ef6\uff0c\u8fd4\u56de\u65b0\u63d0\u4ea4\u7684\u4e09\u4e2a\u51bb\u7ed3\u5bf9\u8c61 id\u3002"""
    for relative, payload in files.items():
        target = repo_root.joinpath(*relative.split("/"))
        if payload is None:
            target.unlink()
            continue
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(payload)
    git_fixture(repo_root, "add", "-A", ".")
    git_fixture(repo_root, "commit", "-q", "--allow-empty", "-m", message)
    return fixture_freeze(repo_root)


def fixture_freeze(repo_root, revision="HEAD"):
    """\u8fd4\u56de (commit, tree, profile config blob) \u4e09\u4e2a\u51bb\u7ed3\u5bf9\u8c61\u3002"""
    commit = git_fixture(repo_root, "rev-parse", "--verify", f"{revision}^{{commit}}")
    tree = git_fixture(repo_root, "rev-parse", "--verify", f"{revision}^{{tree}}")
    config_blob = git_fixture(
        repo_root,
        "rev-parse",
        "--verify",
        f"{revision}:{VALIDATOR.PROFILE_CONFIG_REPO_PATH}",
    )
    return commit, tree, config_blob


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
    files[VALIDATOR.PROFILE_CONFIG_REPO_PATH] = PROFILE_CONFIG_PATH.read_bytes()
    files.update(extra_files or {})
    subprocess.run(["git", "init", "-q", str(path)], check=True, cwd=ROOT)
    subprocess.run(
        ["git", "-C", str(path), "config", "core.autocrlf", "false"],
        check=True,
        cwd=ROOT,
    )
    (path / ".no-hooks").mkdir()
    commit_fixture_files(path, files)
    return path


def rewrite_contract_and_matrix(contract_path, matrix_path, contract, matrix):
    contract_path.write_text(json.dumps(contract, indent=2) + "\n", encoding="utf-8")
    matrix["contract_id"] = contract["contract_id"]
    matrix["contract_sha256"] = hashlib.sha256(contract_path.read_bytes()).hexdigest().upper()
    matrix_path.write_text(json.dumps(matrix, indent=2) + "\n", encoding="utf-8")


def write_bundle(bundle, repo_root, contract=None, matrix=None, revision="HEAD"):
    contract = copy.deepcopy(contract or valid_contract())
    matrix = copy.deepcopy(matrix or valid_matrix(contract))
    (
        contract["freeze_commit"],
        contract["freeze_tree"],
        contract["profile_config_blob"],
    ) = fixture_freeze(repo_root, revision)

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

    def test_frozen_not_run_matrix_performs_execution_preflight(self):
        with tempfile.TemporaryDirectory(dir=ROOT, prefix=".acceptance-validator-test-") as temp_dir:
            root = Path(temp_dir)
            repo = create_fixture_repo(root / "repo")
            contract = valid_contract()
            matrix = valid_matrix(contract, result="NOT_OBSERVED", overall="NOT_RUN")
            contract_path, matrix_path, _, _ = write_bundle(
                root / "bundle", repo, contract, matrix
            )
            untracked = repo / "USER" / "implicit-input.c"
            untracked.parent.mkdir(parents=True, exist_ok=True)
            untracked.write_bytes(b"int implicit_input;\n")
            result, _, stderr = run_main(
                [
                    "--contract",
                    str(contract_path),
                    "--matrix",
                    str(matrix_path),
                    "--repo-root",
                    str(repo),
                ]
            )
            self.assertEqual(1, result)
            self.assertIn("dirty or untracked Production", stderr)

    def test_tree_enumeration_matches_worktree_enumeration_on_fixture(self):
        # \u9a8c\u6536\u8f93\u5165\u7684\u552f\u4e00\u5b9a\u4e49\u662f git tree\uff1b\u5de5\u4f5c\u6811\u679a\u4e3e\u53ea\u7528\u4e8e\u6cbb\u7406\u6d4b\u8bd5\u5bf9\u7167\uff0c
        # \u4e24\u8005\u5728\u5e72\u51c0\u68c0\u51fa\u4e0a\u5fc5\u987b\u9010\u8def\u5f84\u76f8\u7b49\uff0c\u4e14\u975e ASCII \u8def\u5f84\u4e0d\u5f97\u56e0\u5f15\u53f7\u8f6c\u4e49\u4e22\u5931\u3002
        _, tree, _ = fixture_freeze(self.repo_root)
        for profile in sorted(VALIDATOR.PROFILE_NAMES):
            tree_paths = VALIDATOR._profile_tree_paths(self.repo_root, tree, profile)
            self.assertTrue(tree_paths, profile)
            self.assertEqual(VALIDATOR._profile_paths(self.repo_root, profile), tree_paths)
            self.assertTrue(
                VALIDATOR.PROFILE_REQUIRED_PATHS[profile].issubset(tree_paths), profile
            )
        self.assertIn(
            "Tools/\u56fe\u6807/README.md",
            VALIDATOR._profile_tree_paths(self.repo_root, tree, "Validation"),
        )

    def test_worktree_enumeration_does_not_report_deleted_index_entries(self):
        with tempfile.TemporaryDirectory(dir=ROOT, prefix=".acceptance-repo-fixture-") as temp_dir:
            repo = create_fixture_repo(Path(temp_dir) / "repo")
            _, tree, _ = fixture_freeze(repo)
            deleted = repo / "Tools" / "acceptance" / "validate_bundle.py"
            deleted.unlink()
            self.assertNotIn(
                "Tools/acceptance/validate_bundle.py",
                VALIDATOR._profile_paths(repo, "Validation"),
            )
            self.assertIn(
                "Tools/acceptance/validate_bundle.py",
                VALIDATOR._profile_tree_paths(repo, tree, "Validation"),
            )

    def test_real_repository_head_tree_contains_required_profile_paths(self):
        # \u771f\u4ed3\u5e93\u7684 HEAD tree \u5fc5\u987b\u8ba9\u4e09\u4e2a profile \u90fd\u975e\u7a7a\u4e14\u8986\u76d6 required_paths\uff1b
        # \u8fd9\u662f v3 \u5408\u540c\u5728\u4efb\u4f55\u68c0\u51fa\u4e0a\u90fd\u80fd\u7528 git \u5bf9\u8c61\u6838\u5bf9\u7684\u524d\u63d0\u3002
        for profile in sorted(VALIDATOR.PROFILE_NAMES):
            paths = set(VALIDATOR._profile_tree_paths(ROOT, "HEAD^{tree}", profile))
            self.assertTrue(paths, profile)
            self.assertEqual(
                set(),
                VALIDATOR.PROFILE_REQUIRED_PATHS[profile] - paths,
                f"{profile} required_paths \u5fc5\u987b\u5b58\u5728\u4e8e HEAD tree",
            )

    def test_board_and_freeze_index_are_outside_every_profile(self):
        # \u770b\u677f\u6bcf\u6b21\u6536\u53e3\u5fc5\u7136\u56de\u5199\uff0c\u51bb\u7ed3\u70b9\u7d22\u5f15\u6bcf\u6b21\u6536\u53e3\u5fc5\u7136\u8ffd\u52a0\uff1a\u4e8c\u8005\u82e5\u843d\u5728\u4efb\u4f55 profile \u5185\uff0c
        # \u6536\u53e3\u52a8\u4f5c\u672c\u8eab\u5c31\u4f1a\u6253\u7ea2\u521a\u51bb\u7ed3\u7684\u5305\uff08\u81ea\u6307\u73af\uff09\u3002
        for profile in sorted(VALIDATOR.PROFILE_NAMES):
            definition = VALIDATOR._profile_definition(profile)
            self.assertEqual(
                [],
                VALIDATOR._filter_profile_paths(
                    [BOARD_PATH, VALIDATOR.FREEZE_INDEX_PATH], definition
                ),
                profile,
            )
            self.assertNotIn(BOARD_PATH, definition["required_paths"])

    def test_freeze_index_rows_bind_reachable_bundle_and_input_commits(self):
        rows = []
        for line in FREEZE_INDEX.read_text(encoding="utf-8").splitlines():
            if not re.match(r"^\|\s*P\d", line):
                continue
            cells = [cell.strip().strip("`") for cell in line.strip().strip("|").split("|")]
            self.assertEqual(6, len(cells), line)
            rows.append(cells)
        self.assertEqual(7, len(rows))

        seen = set()
        for contract_id, schema, bundle_commit, freeze_commit, freeze_tree, result in rows:
            self.assertNotIn(contract_id, seen)
            seen.add(contract_id)
            self.assertRegex(bundle_commit, r"^[0-9a-f]{40}$")
            self.assertRegex(freeze_commit, r"^[0-9a-f]{40}$")
            self.assertRegex(freeze_tree, r"^[0-9a-f]{40}$")
            self.assertEqual("PASS", result)
            self.assertEqual("commit", git_fixture(ROOT, "cat-file", "-t", bundle_commit))
            self.assertEqual("commit", git_fixture(ROOT, "cat-file", "-t", freeze_commit))
            self.assertEqual(freeze_tree, git_fixture(ROOT, "rev-parse", f"{freeze_commit}^{{tree}}"))
            git_fixture(ROOT, "merge-base", "--is-ancestor", freeze_commit, bundle_commit)
            git_fixture(ROOT, "merge-base", "--is-ancestor", bundle_commit, "HEAD")

            contract_text = git_fixture(
                ROOT,
                "show",
                f"{bundle_commit}:docs/acceptance-contracts/{contract_id}.contract.json",
            )
            contract = json.loads(contract_text)
            self.assertEqual(f"etrack-acceptance-contract-{schema}", contract["schema"])
            if schema == "v2":
                self.assertEqual(bundle_commit, freeze_commit)
            elif schema == "v3":
                self.assertEqual(freeze_commit, contract["freeze_commit"])
                self.assertEqual(freeze_tree, contract["freeze_tree"])
                self.assertRegex(contract["profile_config_blob"], r"^[0-9a-fA-F]{40}$")
            else:
                self.fail(f"unsupported schema in freeze index: {schema}")

    def test_contract_requires_all_three_input_groups(self):
        contract = valid_contract()
        contract["input_groups"] = contract["input_groups"][:1]
        errors = VALIDATOR.validate_contract(contract)
        self.assertTrue(any("missing required groups" in error for error in errors))

    def test_legacy_v2_contract_is_rejected_with_freeze_index_pointer(self):
        contract = valid_contract()
        contract["schema"] = "etrack-acceptance-contract-v2"
        errors = VALIDATOR.validate_contract(contract)
        self.assertEqual(1, len(errors), errors)
        self.assertIn("etrack-acceptance-contract-v3", errors[0])
        self.assertIn(VALIDATOR.FREEZE_INDEX_PATH, errors[0])
        self.assertTrue((ROOT / VALIDATOR.FREEZE_INDEX_PATH).is_file())

    def test_contract_freeze_point_must_be_git_object_ids(self):
        for field in ("freeze_commit", "freeze_tree", "profile_config_blob"):
            for bad in (None, "", "abc", "0" * 39, "g" * 40, "0" * 64):
                contract = valid_contract()
                contract[field] = bad
                errors = VALIDATOR.validate_contract(contract)
                self.assertEqual(
                    [f"contract.{field} must be a 40-hex Git object id"], errors, (field, bad)
                )

    def test_input_groups_reject_manifest_fields(self):
        contract = valid_contract()
        contract["input_groups"][0]["manifest_path"] = "manifest-production/source-manifest.json"
        contract["input_groups"][0]["manifest_sha256"] = "A" * 64
        errors = VALIDATOR.validate_contract(contract)
        self.assertEqual(1, len(errors), errors)
        self.assertIn("unsupported fields: manifest_path, manifest_sha256", errors[0])

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

    def test_freeze_objects_pass_for_the_committed_fixture(self):
        with tempfile.TemporaryDirectory(dir=ROOT, prefix=".acceptance-validator-test-") as temp_dir:
            _, _, contract, _ = write_bundle(Path(temp_dir), self.repo_root)
            commit, tree, config_blob = fixture_freeze(self.repo_root)
            self.assertEqual(
                (commit, tree, config_blob),
                (
                    contract["freeze_commit"],
                    contract["freeze_tree"],
                    contract["profile_config_blob"],
                ),
            )
            self.assertEqual([], VALIDATOR.validate_freeze_objects(contract, self.repo_root))
            # 大小写不影响对象解析，校验器统一按小写比较。
            contract["freeze_commit"] = commit.upper()
            contract["freeze_tree"] = tree.upper()
            self.assertEqual([], VALIDATOR.validate_freeze_objects(contract, self.repo_root))

    def test_freeze_objects_use_the_profile_config_from_the_frozen_tree(self):
        with tempfile.TemporaryDirectory(dir=ROOT, prefix=".acceptance-repo-fixture-") as temp_dir:
            repo = create_fixture_repo(Path(temp_dir) / "repo")
            contract = valid_contract()
            (
                contract["freeze_commit"],
                contract["freeze_tree"],
                contract["profile_config_blob"],
            ) = fixture_freeze(repo)
            with mock.patch.object(VALIDATOR, "MANIFEST_PROFILE_CONFIG", {"profiles": {}}):
                self.assertEqual([], VALIDATOR.validate_freeze_objects(contract, repo))

            contract["profile_config_blob"] = git_fixture(repo, "rev-parse", "HEAD:AGENTS.md")
            errors = VALIDATOR.validate_freeze_objects(contract, repo)
            self.assertEqual(1, len(errors), errors)
            self.assertIn("profile_config_blob does not match", errors[0])

    def test_execution_worktree_rejects_dirty_and_untracked_profile_inputs(self):
        with tempfile.TemporaryDirectory(dir=ROOT, prefix=".acceptance-repo-fixture-") as temp_dir:
            repo = create_fixture_repo(Path(temp_dir) / "repo")
            contract = valid_contract()
            (
                contract["freeze_commit"],
                contract["freeze_tree"],
                contract["profile_config_blob"],
            ) = fixture_freeze(repo)
            self.assertEqual([], VALIDATOR.validate_execution_worktree(contract, repo))

            tracked = repo / "build_f435_and_simulator.bat"
            tracked.write_bytes(b"dirty tracked input\n")
            errors = VALIDATOR.validate_execution_worktree(contract, repo)
            self.assertTrue(any("dirty or untracked Production" in error for error in errors), errors)

        with tempfile.TemporaryDirectory(dir=ROOT, prefix=".acceptance-repo-fixture-") as temp_dir:
            repo = create_fixture_repo(Path(temp_dir) / "repo")
            contract = valid_contract()
            (
                contract["freeze_commit"],
                contract["freeze_tree"],
                contract["profile_config_blob"],
            ) = fixture_freeze(repo)
            untracked = repo / "USER" / "untracked-input.c"
            untracked.parent.mkdir(parents=True, exist_ok=True)
            untracked.write_bytes(b"int untracked_input;\n")
            errors = VALIDATOR.validate_execution_worktree(contract, repo)
            self.assertTrue(any("dirty or untracked Production" in error for error in errors), errors)

    def test_execution_worktree_allows_bundle_only_commits_but_rejects_profile_drift(self):
        with tempfile.TemporaryDirectory(dir=ROOT, prefix=".acceptance-repo-fixture-") as temp_dir:
            repo = create_fixture_repo(Path(temp_dir) / "repo")
            contract = valid_contract()
            (
                contract["freeze_commit"],
                contract["freeze_tree"],
                contract["profile_config_blob"],
            ) = fixture_freeze(repo)
            commit_fixture_files(
                repo,
                {"docs/acceptance-contracts/P9-9-v1.contract.json": b"{}\n"},
                "commit bundle bytes outside profiles",
            )
            self.assertEqual([], VALIDATOR.validate_execution_worktree(contract, repo))

            commit_fixture_files(
                repo,
                {"USER/App/App.cpp": b"// changed after acceptance freeze\n"},
                "change a frozen production input",
            )
            errors = VALIDATOR.validate_execution_worktree(contract, repo)
            self.assertTrue(any("execution HEAD changes frozen Production" in error for error in errors), errors)

    def test_execution_worktree_rejects_a_present_but_unreachable_freeze_commit(self):
        with tempfile.TemporaryDirectory(dir=ROOT, prefix=".acceptance-repo-fixture-") as temp_dir:
            repo = create_fixture_repo(Path(temp_dir) / "repo")
            _, tree, config_blob = fixture_freeze(repo)
            unreachable = git_fixture(repo, "commit-tree", tree, "-m", "unreachable fixture")
            contract = valid_contract()
            contract["freeze_commit"] = unreachable
            contract["freeze_tree"] = tree
            contract["profile_config_blob"] = config_blob
            self.assertEqual([], VALIDATOR.validate_freeze_objects(contract, repo))
            errors = VALIDATOR.validate_execution_worktree(contract, repo)
            self.assertEqual(1, len(errors), errors)
            self.assertIn("not an ancestor", errors[0])

    def test_freeze_objects_reject_missing_or_mistyped_objects(self):
        contract = valid_contract()
        commit, tree, config_blob = fixture_freeze(self.repo_root)
        contract["profile_config_blob"] = config_blob
        blob = git_fixture(self.repo_root, "rev-parse", "HEAD:AGENTS.md")

        contract["freeze_commit"], contract["freeze_tree"] = ABSENT_OID, tree
        errors = VALIDATOR.validate_freeze_objects(contract, self.repo_root)
        self.assertEqual(1, len(errors), errors)
        self.assertIn(f"freeze_commit object is not present in this repository: {ABSENT_OID}", errors[0])
        self.assertIn(VALIDATOR.FREEZE_INDEX_PATH, errors[0])

        contract["freeze_commit"], contract["freeze_tree"] = commit, ABSENT_OID
        errors = VALIDATOR.validate_freeze_objects(contract, self.repo_root)
        self.assertEqual([f"freeze_tree object is not present in this repository: {ABSENT_OID}"], errors)

        contract["freeze_commit"], contract["freeze_tree"] = tree, tree
        errors = VALIDATOR.validate_freeze_objects(contract, self.repo_root)
        self.assertEqual([f"freeze_commit is a tree, not a commit: {tree}"], errors)

        contract["freeze_commit"], contract["freeze_tree"] = commit, blob
        errors = VALIDATOR.validate_freeze_objects(contract, self.repo_root)
        self.assertEqual([f"freeze_tree is a blob, not a tree: {blob}"], errors)

    def test_freeze_tree_must_match_freeze_commit_tree(self):
        contract = valid_contract()
        commit, tree, config_blob = fixture_freeze(self.repo_root)
        contract["profile_config_blob"] = config_blob
        subtree = git_fixture(self.repo_root, "rev-parse", "HEAD:Tools")
        contract["freeze_commit"], contract["freeze_tree"] = commit, subtree
        errors = VALIDATOR.validate_freeze_objects(contract, self.repo_root)
        self.assertEqual(
            [f"freeze_tree does not match freeze_commit^{{tree}}: contract={subtree} commit={tree}"],
            errors,
        )

    def test_freeze_tree_must_keep_every_profile_non_empty_with_required_paths(self):
        with tempfile.TemporaryDirectory(dir=ROOT, prefix=".acceptance-repo-fixture-") as temp_dir:
            repo = create_fixture_repo(Path(temp_dir) / "repo")
            contract = valid_contract()

            # 删掉一个 Validation 必需路径：其余路径仍在，报“缺必需路径”。
            (
                contract["freeze_commit"],
                contract["freeze_tree"],
                contract["profile_config_blob"],
            ) = commit_fixture_files(repo, {"Tools/acceptance/validate_bundle.py": None}, "drop validator")
            errors = VALIDATOR.validate_freeze_objects(contract, repo)
            self.assertEqual(
                ["freeze_tree is missing required Validation paths: Tools/acceptance/validate_bundle.py"],
                errors,
            )

            # 删掉全部 Governance 路径：报“profile 为空”，而不是列一长串缺失路径。
            governance = VALIDATOR._profile_tree_paths(repo, contract["freeze_tree"], "Governance")
            (
                contract["freeze_commit"],
                contract["freeze_tree"],
                contract["profile_config_blob"],
            ) = commit_fixture_files(repo, {path: None for path in governance}, "drop governance")
            errors = VALIDATOR.validate_freeze_objects(contract, repo)
            self.assertIn("freeze_tree contains no Governance paths", errors)
            self.assertFalse(any("missing required Governance" in error for error in errors), errors)

            # 历史提交不受后续删除影响：回到初始提交仍然干净。
            (
                contract["freeze_commit"],
                contract["freeze_tree"],
                contract["profile_config_blob"],
            ) = fixture_freeze(repo, "HEAD~2")
            self.assertEqual([], VALIDATOR.validate_freeze_objects(contract, repo))

    def test_freeze_objects_require_a_git_worktree_root(self):
        contract = valid_contract()
        (
            contract["freeze_commit"],
            contract["freeze_tree"],
            contract["profile_config_blob"],
        ) = fixture_freeze(self.repo_root)
        with tempfile.TemporaryDirectory(dir=ROOT, prefix=".acceptance-validator-test-") as temp_dir:
            errors = VALIDATOR.validate_freeze_objects(contract, temp_dir)
        self.assertEqual(1, len(errors), errors)
        self.assertIn("repository root is invalid", errors[0])
        # 结构错误（非 40-hex）由 validate_contract 报告，这里不重复报。
        contract["freeze_commit"] = "not-an-oid"
        self.assertEqual([], VALIDATOR.validate_freeze_objects(contract, self.repo_root))

    def test_absent_freeze_commit_is_rejected_end_to_end(self):
        with tempfile.TemporaryDirectory(dir=ROOT, prefix=".acceptance-validator-test-") as temp_dir:
            bundle = Path(temp_dir)
            contract_path, matrix_path, contract, matrix = write_bundle(bundle, self.repo_root)
            contract["freeze_commit"] = ABSENT_OID
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
            self.assertIn("freeze_commit object is not present in this repository", stderr)
            self.assertNotIn("worktree", stderr)

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

    def test_rerun_ignores_the_commit_id_when_the_freeze_tree_is_unchanged(self):
        # squash / rebase / cherry-pick 会换掉 commit id，但 tree 相同即输入字节相同，
        # 不得据此要求重跑；tree 相同的比较也不需要仓库。
        previous_contract = valid_contract()
        (
            previous_contract["freeze_commit"],
            previous_contract["freeze_tree"],
            previous_contract["profile_config_blob"],
        ) = fixture_freeze(self.repo_root)
        previous_matrix = valid_matrix(previous_contract)
        current = successor_contract(previous_contract)
        current["freeze_commit"] = ABSENT_OID
        plan = VALIDATOR.compute_rerun_plan(current, previous_contract, previous_matrix)
        self.assertEqual([], plan["changed_input_groups"])
        self.assertEqual([], plan["rerun_criteria"])
        self.assertEqual(["FUNC-1"], plan["reusable_criteria"])

    def test_rerun_invalidates_only_the_profiles_whose_tree_paths_changed(self):
        with tempfile.TemporaryDirectory(dir=ROOT, prefix=".acceptance-repo-fixture-") as temp_dir:
            repo = create_fixture_repo(Path(temp_dir) / "repo")
            previous_contract = valid_contract()
            (
                previous_contract["freeze_commit"],
                previous_contract["freeze_tree"],
                previous_contract["profile_config_blob"],
            ) = fixture_freeze(repo)
            previous_matrix = valid_matrix(previous_contract)

            current = successor_contract(previous_contract)
            (
                current["freeze_commit"],
                current["freeze_tree"],
                current["profile_config_blob"],
            ) = commit_fixture_files(
                repo,
                {"tests/ota/test_acceptance_bundle.py": b"# fixture edit\n"},
                "touch a validation input",
            )
            plan = VALIDATOR.compute_rerun_plan(
                current, previous_contract, previous_matrix, repo_root=repo
            )
            self.assertEqual(["validation"], plan["changed_input_groups"])
            self.assertEqual(["FUNC-1"], [item["id"] for item in plan["rerun_criteria"]])
            self.assertIn("input_group_changed:validation", plan["rerun_criteria"][0]["reasons"])
            self.assertEqual(["CMD-FUNC-1"], plan["required_commands"])
            self.assertEqual(["ART-FIRMWARE"], plan["required_artifacts"])

            # 收口回写看板与冻结点索引都在 profile 之外，不得让任何判据失效。
            outside = successor_contract(current)
            (
                outside["freeze_commit"],
                outside["freeze_tree"],
                outside["profile_config_blob"],
            ) = commit_fixture_files(
                repo,
                {
                    BOARD_PATH: b"board writeback\n",
                    VALIDATOR.FREEZE_INDEX_PATH: b"| P9-9-v1 | v3 | ... |\n",
                },
                "write the board back",
            )
            plan = VALIDATOR.compute_rerun_plan(
                outside, current, valid_matrix(current), repo_root=repo
            )
            self.assertEqual([], plan["changed_input_groups"])
            self.assertEqual(["FUNC-1"], plan["reusable_criteria"])

    def test_rerun_uses_each_tree_profile_config_and_invalidates_definition_changes(self):
        with tempfile.TemporaryDirectory(dir=ROOT, prefix=".acceptance-repo-fixture-") as temp_dir:
            repo = create_fixture_repo(Path(temp_dir) / "repo")
            previous = valid_contract()
            (
                previous["freeze_commit"],
                previous["freeze_tree"],
                previous["profile_config_blob"],
            ) = fixture_freeze(repo)
            previous_matrix = valid_matrix(previous)

            config = json.loads(PROFILE_CONFIG_PATH.read_text(encoding="utf-8"))
            config["profiles"]["Production"]["root_patterns"].remove("USER/")
            current = successor_contract(previous)
            (
                current["freeze_commit"],
                current["freeze_tree"],
                current["profile_config_blob"],
            ) = commit_fixture_files(
                repo,
                {
                    VALIDATOR.PROFILE_CONFIG_REPO_PATH: (
                        json.dumps(config, indent=2, ensure_ascii=False) + "\n"
                    ).encode("utf-8")
                },
                "change the Production profile definition",
            )
            plan = VALIDATOR.compute_rerun_plan(
                current, previous, previous_matrix, repo_root=repo
            )
            self.assertEqual(["production", "validation"], plan["changed_input_groups"])
            self.assertEqual(["FUNC-1"], [item["id"] for item in plan["rerun_criteria"]])

    def test_rerun_requires_a_repository_root_when_the_freeze_tree_differs(self):
        previous_contract = valid_contract()
        (
            previous_contract["freeze_commit"],
            previous_contract["freeze_tree"],
            previous_contract["profile_config_blob"],
        ) = fixture_freeze(self.repo_root)
        previous_matrix = valid_matrix(previous_contract)
        current = successor_contract(previous_contract)
        current["freeze_tree"] = ABSENT_OID
        with self.assertRaisesRegex(ValueError, "repository root is required"):
            VALIDATOR.compute_rerun_plan(current, previous_contract, previous_matrix)
        current["freeze_tree"] = "not-an-oid"
        with self.assertRaisesRegex(ValueError, "40-hex freeze_tree"):
            VALIDATOR.compute_rerun_plan(
                current, previous_contract, previous_matrix, repo_root=self.repo_root
            )

    def test_rerun_rejects_cross_task_same_version_and_wrong_parent(self):
        previous_contract = valid_contract()
        previous_matrix = valid_matrix(previous_contract)

        cross_task = successor_contract(previous_contract)
        cross_task["task_id"] = "P9-9"
        cross_task["contract_id"] = "P9-9-v2"
        with self.assertRaisesRegex(ValueError, "task_id"):
            VALIDATOR.compute_rerun_plan(cross_task, previous_contract, previous_matrix)

        same_version = copy.deepcopy(previous_contract)
        same_version["freeze_commit"] = ABSENT_OID
        with self.assertRaisesRegex(ValueError, "next contract version"):
            VALIDATOR.compute_rerun_plan(same_version, previous_contract, previous_matrix)

        wrong_parent = successor_contract(previous_contract)
        wrong_parent["parent_contract_sha256"] = "0" * 64
        with self.assertRaisesRegex(ValueError, "parent_contract_sha256"):
            VALIDATOR.compute_rerun_plan(wrong_parent, previous_contract, previous_matrix)

    def test_reuse_is_rejected_when_dependency_changed(self):
        with tempfile.TemporaryDirectory(dir=ROOT, prefix=".acceptance-repo-fixture-") as temp_dir:
            repo = create_fixture_repo(Path(temp_dir) / "repo")
            previous_contract = valid_contract()
            (
                previous_contract["freeze_commit"],
                previous_contract["freeze_tree"],
                previous_contract["profile_config_blob"],
            ) = fixture_freeze(repo)
            previous_matrix = valid_matrix(previous_contract)
            current_contract = successor_contract(previous_contract)
            (
                current_contract["freeze_commit"],
                current_contract["freeze_tree"],
                current_contract["profile_config_blob"],
            ) = commit_fixture_files(
                repo,
                {"USER/App/App.cpp": b"// fixture edit\n"},
                "touch a production input",
            )
            current_matrix = copy.deepcopy(previous_matrix)
            current_matrix["contract_id"] = current_contract["contract_id"]
            current_matrix["criteria"][0]["execution"] = "REUSED"
            current_matrix["criteria"][0]["reused_from_round"] = previous_matrix["round_id"]
            plan = VALIDATOR.compute_rerun_plan(
                current_contract, previous_contract, previous_matrix, repo_root=repo
            )
            self.assertEqual(["production"], plan["changed_input_groups"])
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
                if symlink_security_test_required():
                    self.fail(f"symlink creation is required in governance CI: {exc}")
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
                    "--write-rerun-plan",
                    "linked-output/rerun-plan.json",
                ]
            )
            self.assertEqual(1, result)
            self.assertIn("link or reparse point", stderr)
            self.assertFalse((outside_dir / "rerun-plan.json").exists())

    def test_symlink_security_requirement_detection(self):
        with mock.patch.dict(os.environ, {}, clear=True):
            self.assertFalse(symlink_security_test_required())
        with mock.patch.dict(os.environ, {SYMLINK_TEST_REQUIRED_ENV: "1"}, clear=True):
            self.assertTrue(symlink_security_test_required())
        with mock.patch.dict(os.environ, {"GITHUB_ACTIONS": "true"}, clear=True):
            self.assertTrue(symlink_security_test_required())

    def test_governance_ci_requires_symlink_security_case(self):
        workflow = (ROOT / ".github" / "workflows" / "acceptance-governance.yml").read_text(
            encoding="utf-8"
        )
        governance_step = workflow.split("- name: Run governance regression tests", 1)[1].split(
            "- name:", 1
        )[0]
        self.assertEqual(
            1,
            governance_step.count(f'{SYMLINK_TEST_REQUIRED_ENV}: "1"'),
            "Governance CI 必须把 symlink 安全用例设为不可跳过",
        )

    def test_governance_ci_fetches_history_for_freeze_reachability(self):
        workflow = (ROOT / ".github" / "workflows" / "acceptance-governance.yml").read_text(
            encoding="utf-8"
        )
        checkout = workflow.split("- name: Checkout", 1)[1].split("- name:", 1)[0]
        self.assertIn(
            "fetch-depth: 0",
            checkout,
            "冻结提交与证据包提交的祖先关系需要完整 Git 历史",
        )

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
                ]
            )
            self.assertEqual(1, result)
            self.assertIn("current and previous matrix files must be different", stderr)
            self.assertIn("round_id must be different", stderr)

    def test_previous_contract_and_matrix_must_be_supplied_together(self):
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
                    "--previous-contract",
                    str(contract_path),
                ]
            )
            self.assertEqual(1, result)
            self.assertIn("previous contract and matrix must be supplied together", stderr)


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


class CriterionDependencyTests(unittest.TestCase):
    def test_single_group_does_not_require_rationale(self):
        for group in ("production", "validation", "governance"):
            with self.subTest(group=group):
                contract = valid_contract()
                contract["criteria"][0]["input_groups"] = [group]
                contract["criteria"][0].pop("dependency_rationale")
                self.assertEqual([], VALIDATOR.validate_contract(contract))

    def test_multiple_groups_require_a_structured_rationale(self):
        for groups in (["production", "validation"], list(VALIDATOR.REQUIRED_INPUT_GROUPS)):
            with self.subTest(groups=groups):
                contract = valid_contract()
                criterion = contract["criteria"][0]
                criterion["input_groups"] = groups
                self.assertEqual([], VALIDATOR.validate_contract(contract))
                criterion.pop("dependency_rationale")
                criterion["description"] = "A prose explanation cannot replace the structured field."
                self.assertEqual(
                    ["contract.criteria[0].dependency_rationale is required when multiple input_groups are used"],
                    VALIDATOR.validate_contract(contract),
                )

    def test_present_rationale_must_be_nonempty_text(self):
        for groups in (["production"], ["production", "validation"]):
            for value in (None, "", " \t\n", False, 1, [], {}):
                with self.subTest(groups=groups, value=value):
                    contract = valid_contract()
                    contract["criteria"][0]["input_groups"] = groups
                    contract["criteria"][0]["dependency_rationale"] = value
                    self.assertEqual(
                        ["contract.criteria[0].dependency_rationale must be a non-empty string when set"],
                        VALIDATOR.validate_contract(contract),
                    )

    def test_duplicate_groups_are_rejected_even_with_a_rationale(self):
        for groups in (["production", "production"], ["production", "validation", "production"]):
            with self.subTest(groups=groups):
                contract = valid_contract()
                contract["criteria"][0]["input_groups"] = groups
                self.assertEqual(
                    ["contract.criteria[0].input_groups must not contain duplicates"],
                    VALIDATOR.validate_contract(contract),
                )

    def test_malformed_dependencies_fail_closed(self):
        for groups in (None, "production", [], [""], [{}], ["Production"], ["unknown"]):
            with self.subTest(groups=groups):
                contract = valid_contract()
                contract["criteria"][0]["input_groups"] = groups
                errors = VALIDATOR.validate_contract(contract)
                self.assertTrue(any(".input_groups" in error for error in errors), errors)


class SelectiveRerunTests(unittest.TestCase):
    def setUp(self):
        template = valid_contract()
        observations = valid_matrix(template)
        self.contract = copy.deepcopy(template)
        self.matrix = copy.deepcopy(observations)
        for field in ("criteria", "commands", "artifacts"):
            self.contract[field] = []
            self.matrix[field] = []
        for group in VALIDATOR.REQUIRED_INPUT_GROUPS:
            criterion = copy.deepcopy(template["criteria"][0])
            criterion.update(
                id=group,
                input_groups=[group],
                command_ids=[f"CMD-{group}"],
                artifact_ids=[f"ART-{group}"],
            )
            criterion.pop("dependency_rationale")
            command = dict(template["commands"][0], id=f"CMD-{group}", command=f"observe-{group}")
            artifact = dict(template["artifacts"][0], id=f"ART-{group}", path=f"artifacts/{group}.bin")
            self.contract["criteria"].append(criterion)
            self.contract["commands"].append(command)
            self.contract["artifacts"].append(artifact)
            self.matrix["criteria"].append(dict(observations["criteria"][0], id=group))
            self.matrix["commands"].append(
                dict(observations["commands"][0], id=command["id"], command=command["command"])
            )
            self.matrix["artifacts"].append(
                dict(observations["artifacts"][0], id=artifact["id"], path=artifact["path"])
            )
        self.matrix["contract_sha256"] = contract_hash(self.contract)
        self.assertEqual([], VALIDATOR.validate_contract(self.contract))
        self.assertEqual(
            [], VALIDATOR.validate_matrix(self.matrix, self.contract, contract_hash(self.contract))
        )

    def assert_scope(self, plan, groups):
        self.assertEqual(sorted(groups), sorted(item["id"] for item in plan["rerun_criteria"]))
        self.assertEqual(sorted(f"CMD-{group}" for group in groups), plan["required_commands"])
        self.assertEqual(sorted(f"ART-{group}" for group in groups), plan["required_artifacts"])
        self.assertEqual(
            sorted(set(VALIDATOR.REQUIRED_INPUT_GROUPS) - set(groups)), plan["reusable_criteria"]
        )

    def test_git_changes_select_only_the_criteria_that_depend_on_the_profile(self):
        with tempfile.TemporaryDirectory(dir=ROOT, prefix=".acceptance-repo-fixture-") as temp_dir:
            repo = create_fixture_repo(Path(temp_dir) / "repo")
            for group, path in (
                ("production", "USER/behavior.c"),
                ("validation", "Tools/measure.py"),
                ("governance", "AGENTS.md"),
            ):
                with self.subTest(group=group):
                    previous = copy.deepcopy(self.contract)
                    (
                        previous["freeze_commit"],
                        previous["freeze_tree"],
                        previous["profile_config_blob"],
                    ) = fixture_freeze(repo)
                    current = successor_contract(previous)
                    (
                        current["freeze_commit"],
                        current["freeze_tree"],
                        current["profile_config_blob"],
                    ) = commit_fixture_files(repo, {path: b"changed input\n"})
                    plan = VALIDATOR.compute_rerun_plan(current, previous, self.matrix, repo_root=repo)
                    self.assertEqual([group], plan["changed_input_groups"])
                    self.assert_scope(plan, [group])
                    self.assertIn(f"input_group_changed:{group}", plan["rerun_criteria"][0]["reasons"])

                    reused = copy.deepcopy(self.matrix)
                    for item in reused["criteria"]:
                        item.update(execution="REUSED", reused_from_round=self.matrix["round_id"])
                    errors = VALIDATOR.validate_reuse(reused, current, self.matrix, plan)
                    self.assertEqual(1, len(errors), errors)
                    self.assertIn("reuses invalidated evidence", errors[0])
                    for item in reused["criteria"]:
                        if item["id"] == group:
                            item.update(execution="EXECUTED", reused_from_round=None)
                    self.assertEqual([], VALIDATOR.validate_reuse(reused, current, self.matrix, plan))

                    if group == "validation":
                        # A real runner dependency must still invalidate the product observation.
                        previous["criteria"][0]["input_groups"].append("validation")
                        previous["criteria"][0]["dependency_rationale"] = "The runner measures this product gate."
                        current["criteria"] = copy.deepcopy(previous["criteria"])
                        current["parent_contract_sha256"] = contract_hash(previous)
                        self.assertEqual([], VALIDATOR.validate_contract(current))
                        plan = VALIDATOR.compute_rerun_plan(current, previous, self.matrix, repo_root=repo)
                        self.assert_scope(plan, ["production", "validation"])

    def test_failures_do_not_invalidate_unrelated_passes(self):
        for group, result, owner, overall in (
            ("production", "FAIL", "product", "PRODUCT_FAIL"),
            ("validation", "FAIL", "harness", "HARNESS_FAIL"),
            ("production", "NOT_OBSERVED", None, "EVIDENCE_GAP"),
            ("production", "FAIL", "environment", "ENV_BLOCKED"),
        ):
            with self.subTest(overall=overall):
                previous_matrix = copy.deepcopy(self.matrix)
                previous_matrix["overall_result"] = overall
                for item in previous_matrix["criteria"]:
                    if item["id"] == group:
                        item.update(
                            result=result,
                            failure_owner=owner,
                            observed=False if owner == "product" else None,
                        )
                self.assertEqual(
                    [], VALIDATOR.validate_matrix(previous_matrix, self.contract, contract_hash(self.contract))
                )
                plan = VALIDATOR.compute_rerun_plan(self.contract, self.contract, previous_matrix)
                self.assert_scope(plan, [group])
                self.assertIn("previous_result_not_pass", plan["rerun_criteria"][0]["reasons"])

    def test_definition_changes_only_rerun_their_consumers(self):
        for field, changed_key, value, reason in (
            ("commands", "command", "observe-product-v2", "command_definition_changed:CMD-production"),
            ("artifacts", "path", "artifacts/new-product.bin", "artifact_definition_changed:ART-production"),
            ("criteria", "description", "An updated requirement.", "criterion_definition_changed"),
        ):
            with self.subTest(field=field):
                current = successor_contract(self.contract)
                current[field][0][changed_key] = value
                plan = VALIDATOR.compute_rerun_plan(current, self.contract, self.matrix)
                self.assert_scope(plan, ["production"])
                self.assertIn(reason, plan["rerun_criteria"][0]["reasons"])

    def test_external_state_changes_only_rerun_their_consumers(self):
        previous = copy.deepcopy(self.contract)
        previous["external_inputs"] = [
            {
                "id": "board",
                "category": "hardware_state",
                "description": "Target readiness.",
                "fingerprint": "before",
                "evidence_path": "raw/board.log",
                "evidence_sha256": "A" * 64,
            }
        ]
        previous["criteria"][0]["external_inputs"] = ["board"]
        current = successor_contract(previous)
        current["external_inputs"][0]["fingerprint"] = "after"
        current["external_inputs"][0]["evidence_sha256"] = "B" * 64
        self.assertEqual([], VALIDATOR.validate_contract(current))
        plan = VALIDATOR.compute_rerun_plan(current, previous, self.matrix)
        self.assert_scope(plan, ["production"])
        self.assertEqual(["board"], plan["changed_external_inputs"])
        self.assertIn("external_input_changed:board", plan["rerun_criteria"][0]["reasons"])


class AcceptanceExecutionPolicyTests(unittest.TestCase):
    """守护最小依赖和阶段化验收规则，避免新合同退回全量重跑。"""

    CONTRACT_DOC = ROOT / "docs" / "acceptance-execution-contract.md"
    AGENTS_DOC = ROOT / "AGENTS.md"

    def test_template_criterion_does_not_overdeclare_profiles(self):
        template = json.loads(CONTRACT_TEMPLATE.read_text(encoding="utf-8"))
        profiles = {group["id"] for group in template["input_groups"]}
        self.assertEqual(profiles, {"production", "validation", "governance"})
        for criterion in template["criteria"]:
            dependencies = criterion["input_groups"]
            self.assertEqual(
                len(dependencies),
                len(set(dependencies)),
                f"模板判据 {criterion['id']} 的 input_groups 不得重复",
            )
            self.assertLess(
                len(dependencies),
                len(profiles),
                f"模板判据 {criterion['id']} 不得默认绑定全部 profile；只列直接依赖",
            )

    def test_staged_execution_policy_is_documented(self):
        contract = self.CONTRACT_DOC.read_text(encoding="utf-8")
        agents = self.AGENTS_DOC.read_text(encoding="utf-8")
        for marker in (
            "## 7.1 阶段化执行与最小重跑",
            "前置检查（preflight）",
            "产品观测（product）",
            "证据封包（evidence）",
            "只重跑 `required_commands`",
            "禁止以“方便”或“保险”为由重跑整套宿主测试、构建或硬件流程",
            "每项判据的 `input_groups` 必须只列出其直接依赖的最小集合",
            "暂停 WDT 或写入调试域寄存器",
            "dependency_rationale",
            "不授予操作权限或追加配额",
            "已有授权和剩余配额",
            "必要的只读预检、证据整理和完整性校验仍可执行",
        ):
            with self.subTest(marker=marker):
                self.assertIn(marker, contract)
        self.assertIn("验收必须阶段化且按最小范围重跑", agents)

    def test_dispatch_templates_keep_dependency_and_retry_boundaries(self):
        prompt = (ROOT / "docs/ota-prompts/prompt-template-acceptance.md").read_text(
            encoding="utf-8"
        )
        for marker in (
            "dependency_rationale",
            "必须包含 `validation`",
            "不授予操作权限或追加配额",
            "已有授权及剩余配额",
            "只重跑 `required_commands`",
            "已用/剩余观测配额",
        ):
            with self.subTest(marker=marker):
                self.assertIn(marker, prompt)
        implementation = (ROOT / "docs/ota-prompts/prompt-template-implementation.md").read_text(
            encoding="utf-8"
        )
        self.assertIn("仅改治理规范、模板或宿主工具时", implementation)
        self.assertIn("远端治理 CI 要求不变", implementation)

    def test_board_routes_to_git_freeze_inputs_not_worktree_manifests(self):
        board = (ROOT / BOARD_PATH).read_text(encoding="utf-8")
        rules = board.split("## 0.", 1)[1].split("## 1.", 1)[0]
        self.assertIn("freeze_tree", rules)
        self.assertIn("不授予操作权限或追加配额", rules)
        self.assertNotIn("重算 manifest", rules)


class PostP26SpecGovernanceTests(unittest.TestCase):
    """机械守护 P2-6 后共享合同、唯一提示词和 readiness 路由。"""

    CONTRACT = ROOT / "docs" / "ota-cross-system-contracts.md"
    DECISIONS = ROOT / "docs" / "ota-spec-decisions.md"
    BOARD = ROOT / "PLAN-OTA-EXEC.md"
    PROMPT_ROOT = ROOT / "docs" / "ota-prompts"
    MANIFEST_PROFILES = ROOT / "Tools" / "provenance" / "manifest_profiles.json"
    WORKFLOW = ROOT / ".github" / "workflows" / "acceptance-governance.yml"
    MATRIX_START = "<!-- post-p2-6-readiness:start -->"
    MATRIX_END = "<!-- post-p2-6-readiness:end -->"
    TYPE_BY_SUFFIX = {
        "implementation": "IMPLEMENTATION",
        "experiment": "EXPERIMENT",
        "integration": "INTEGRATION",
        "acceptance": "ACCEPTANCE",
    }
    PROMPT_FILENAME_HINT_RE = re.compile(
        r"^prompt-(P\d+-\d+)(?:-.*)?\.md$",
        re.IGNORECASE,
    )
    PROMPT_FILENAME_SHAPE_RE = re.compile(
        r"^prompt-(P\d+-\d+)-(implementation|experiment|integration|acceptance)\.md$",
        re.IGNORECASE,
    )
    PROPAGATED_CONSUMER_CLAUSES = frozenset(
        {
            "OTA-XC-ASSET-SELECTION",
            "OTA-XC-ADMIN-IDEMPOTENCY",
            "OTA-XC-HTTP-ADMIN",
            "OTA-XC-HTTP-DOWNLOAD",
            "OTA-XC-HTTP-LATEST",
            "OTA-XC-HTTP-REGISTER",
            "OTA-XC-HTTP-RESUME",
        }
    )
    ACTIVE_DECISION_STATUSES = frozenset({"OPEN", "PROPOSED"})
    DECISION_REQUIREMENT_RE = re.compile(
        r"必须|不得|只能|应当|固定为|先.{0,80}再|\b(?:must|shall|required)\b",
        re.IGNORECASE,
    )
    DECISION_CANDIDATE_RE = re.compile(r"推荐方案|候选方案|方案\s*[A-Z]\b", re.IGNORECASE)
    REQUIRED_PROMPT_SECTIONS = (
        "任务类型",
        "Readiness 引用",
        "非目标",
        "前置依赖",
        "权威合同",
        "现有组件和代码入口",
        "输入输出与调用方向",
        "状态机与生命周期所有者",
        "错误、超时、重试、取消、恢复与幂等",
        "允许修改范围",
        "禁止修改与生产红线",
        "必须新增或调整的测试",
        "完成判据",
        "停止条件",
        "后续证据",
        "Luna 可自行决定",
        "阻断性决策",
    )
    TASK_STATUS_FIELDS = (
        "content_readiness",
        "governance_maturity",
        "dependency_state",
        "dispatch_eligibility",
    )
    TASK_STATUS_VALUES = frozenset(
        {
            "READY",
            "NEEDS_DECISION",
            "DEFERRED_ACCEPTANCE",
            "DRAFT_PENDING_REVIEW",
            "REVIEWED",
            "FROZEN",
            "SATISFIED",
            "BLOCKED_BY_DEPENDENCY",
            "NOT_APPLICABLE",
            "DISPATCHABLE",
            "NOT_DISPATCHABLE",
        }
    )
    TASK_STATUS_ALIASES = frozenset(
        {
            "READY_FOR_REVIEW",
        }
    )
    TASK_STATUS_TOKEN_RE = re.compile(
        r"(?<![A-Z0-9_])(?:"
        + "|".join(
            re.escape(value)
            for value in sorted(
                TASK_STATUS_VALUES | TASK_STATUS_ALIASES,
                key=lambda value: (-len(value), value),
            )
        )
        + r")(?![A-Z0-9_])"
    )
    PLAN_READINESS_REFERENCE_RE = re.compile(
        r"`PLAN-OTA-EXEC\.md`[^\n]*(?:readiness|矩阵)[^\n]*(?:行|row)",
        re.IGNORECASE,
    )

    @classmethod
    def setUpClass(cls):
        cls.board = cls.BOARD.read_text(encoding="utf-8")
        cls.contract = cls.CONTRACT.read_text(encoding="utf-8")
        cls.decisions = cls.DECISIONS.read_text(encoding="utf-8")

    @classmethod
    def expected_active_prompt_blocking(cls, decision_ids, statuses, declared_blocking, routed_task_ids):
        return {
            decision_id: (
                declared_blocking[decision_id] & routed_task_ids
                if statuses[decision_id] in cls.ACTIVE_DECISION_STATUSES
                else set()
            )
            for decision_id in decision_ids
        }

    @classmethod
    def markdown_logical_blocks(cls, text):
        blocks = []
        section = None
        start_line = None
        parts = []
        list_indent = None

        def flush():
            nonlocal start_line, parts, list_indent
            if parts:
                blocks.append((start_line, section, " ".join(parts)))
            start_line = None
            parts = []
            list_indent = None

        for line_number, raw_line in enumerate(text.splitlines(), 1):
            stripped = raw_line.strip()
            if raw_line.startswith("## "):
                flush()
                section = raw_line[3:].strip()
                continue
            if not stripped:
                flush()
                continue
            if re.match(r"^#{1,6}\s+", stripped):
                flush()
                continue
            list_match = re.match(r"^(?P<indent>\s*)(?:[-+*]|\d+\.)\s+", raw_line)
            if list_match and (
                start_line is None
                or list_indent is None
                or len(list_match.group("indent").expandtabs(4)) <= list_indent
            ):
                flush()
                list_indent = len(list_match.group("indent").expandtabs(4))
            if start_line is None:
                start_line = line_number
            parts.append(stripped)
        flush()
        return blocks

    @classmethod
    def proposed_decision_requirement_violations(cls, text, active_decision_ids):
        violations = []
        for line_number, section, block in cls.markdown_logical_blocks(text):
            if cls.DECISION_CANDIDATE_RE.search(block) and cls.DECISION_REQUIREMENT_RE.search(block):
                violations.append((line_number, block))
                continue
            references = set(re.findall(r"OTA-DEC-\d{3}", block)) & active_decision_ids
            if not references:
                continue
            if section != "阻断性决策" or cls.DECISION_REQUIREMENT_RE.search(block):
                violations.append((line_number, block))
        return violations

    @classmethod
    def readiness_rows(cls):
        if cls.board.count(cls.MATRIX_START) != 1 or cls.board.count(cls.MATRIX_END) != 1:
            raise AssertionError("PLAN-OTA-EXEC.md 必须恰有一个 P2-6 后 readiness 矩阵")
        block = cls.board.split(cls.MATRIX_START, 1)[1].split(cls.MATRIX_END, 1)[0]
        table = [line for line in block.splitlines() if line.startswith("|")]
        if len(table) < 3:
            raise AssertionError("readiness 矩阵表缺失")
        header = [cell.strip() for cell in table[0].strip("|").split("|")]
        rows = []
        for line in table[2:]:
            cells = [cell.strip() for cell in line.strip("|").split("|")]
            if len(cells) != len(header):
                raise AssertionError(f"readiness 行列数错误: {line}")
            rows.append(dict(zip(header, cells)))
        return rows

    @classmethod
    def post_p26_task_ids(cls):
        before_matrix = cls.board.split(cls.MATRIX_START, 1)[0]
        board_ids = re.findall(r"(?m)^#### (P\d+-\d+)\b", before_matrix)
        if board_ids.count("P2-6") != 1:
            raise AssertionError("看板正文必须恰有一个 P2-6 标题")
        task_ids = board_ids[board_ids.index("P2-6") + 1 :]
        if not task_ids or len(task_ids) != len(set(task_ids)):
            raise AssertionError("P2-6 后任务标题缺失或重复")
        return task_ids

    @classmethod
    def prompt_target(cls, row):
        rel = row["prompt_path"]
        reason = row["spec_block_reason"]
        if not rel:
            if not reason:
                raise AssertionError(f"{row['task_id']} 缺少 prompt_path 和 spec_block_reason")
            return None
        if reason:
            raise AssertionError(f"{row['task_id']} 不得同时填写 prompt_path 和 spec_block_reason")
        if rel.startswith(("/", "./")) or "\\" in rel or "//" in rel or ".." in rel.split("/"):
            raise AssertionError(f"非法 prompt_path: {rel}")
        target = (ROOT / Path(*rel.split("/"))).resolve()
        prompt_root = cls.PROMPT_ROOT.resolve()
        if target.parent != prompt_root and prompt_root not in target.parents:
            raise AssertionError(f"prompt_path 越出 docs/ota-prompts: {rel}")
        return target

    @classmethod
    def prompt_records(cls):
        records = []
        for row in cls.readiness_rows():
            target = cls.prompt_target(row)
            if target is None:
                continue
            if not target.is_file():
                raise AssertionError(f"readiness 引用的提示词不存在: {row['prompt_path']}")
            records.append((row, target, target.read_text(encoding="utf-8")))
        return records

    @classmethod
    def prompt_task_status_value_violations(cls, text):
        violations = []
        for line_number, raw_line in enumerate(text.splitlines(), 1):
            matches = list(cls.TASK_STATUS_TOKEN_RE.finditer(raw_line))
            if not matches:
                continue
            if cls.PLAN_READINESS_REFERENCE_RE.search(raw_line):
                continue
            for match in matches:
                violations.append((line_number, match.group(0), raw_line.strip()))
        return violations

    @staticmethod
    def markdown_table_row(text, label):
        rows = [line for line in text.splitlines() if line.startswith(f"| `{label}` |")]
        if len(rows) != 1:
            raise AssertionError(f"合同表格必须恰有一行 `{label}`: {rows}")
        cells = [cell.strip() for cell in rows[0].strip("|").split("|")]
        if len(cells) != 4:
            raise AssertionError(f"合同表格 `{label}` 列数错误: {rows[0]}")
        return cells

    @staticmethod
    def contract_vector_row(text, vector_id):
        rows = [line for line in text.splitlines() if line.startswith(f"| `{vector_id}` |")]
        if len(rows) != 1:
            raise AssertionError(f"合同向量必须恰有一行 `{vector_id}`: {rows}")
        return rows[0]

    def test_readiness_matrix_mirrors_board_order_and_derives_dispatch(self):
        rows = self.readiness_rows()
        self.assertEqual(self.post_p26_task_ids(), [row["task_id"] for row in rows], "readiness 必须镜像看板正文原顺序")
        self.assertEqual([str(index) for index in range(1, len(rows) + 1)], [row["顺序"] for row in rows])
        dispatchable = set()
        for row in rows:
            with self.subTest(task=row["task_id"]):
                self.assertIn(row["type"], set(self.TYPE_BY_SUFFIX.values()))
                self.assertIn(row["content_readiness"], {"READY", "NEEDS_DECISION", "DEFERRED_ACCEPTANCE"})
                self.assertIn(row["governance_maturity"], {"DRAFT_PENDING_REVIEW", "REVIEWED", "FROZEN"})
                self.assertIn(row["dependency_state"], {"SATISFIED", "BLOCKED_BY_DEPENDENCY", "NOT_APPLICABLE"})
                self.assertIn(row["dispatch_eligibility"], {"DISPATCHABLE", "NOT_DISPATCHABLE"})
                expected_content = "DEFERRED_ACCEPTANCE" if row["type"] == "ACCEPTANCE" else "READY"
                self.assertEqual(expected_content, row["content_readiness"])
                self.assertEqual("FROZEN", row["governance_maturity"])
                expected_dispatch = (
                    "DISPATCHABLE"
                    if row["content_readiness"] == "READY"
                    and row["dependency_state"] in {"SATISFIED", "NOT_APPLICABLE"}
                    else "NOT_DISPATCHABLE"
                )
                self.assertEqual(expected_dispatch, row["dispatch_eligibility"])
                if row["dispatch_eligibility"] == "DISPATCHABLE":
                    dispatchable.add(row["task_id"])
                self.assertTrue(bool(row["prompt_path"]) ^ bool(row["spec_block_reason"]))

                target = self.prompt_target(row)
                if target is None:
                    continue
                name_match = self.PROMPT_FILENAME_SHAPE_RE.fullmatch(target.name)
                self.assertIsNotNone(name_match, f"提示词文件名不符合任务类型命名规则: {target.name}")
                self.assertEqual(row["task_id"], name_match.group(1).upper())
                self.assertEqual(row["type"], self.TYPE_BY_SUFFIX[name_match.group(2).lower()])
                text = target.read_text(encoding="utf-8")
                type_section = text.split("## 任务类型", 1)[1].split("## ", 1)[0]
                declared_types = re.findall(r"(?m)^`([A-Z_]+)`$", type_section)
                self.assertEqual([row["type"]], declared_types, f"{target.name} 任务类型与 readiness 不一致")
        self.assertEqual(
            {"P3-1", "P3-2", "P3-4", "P3-6", "P3-7", "P4-2"},
            dispatchable,
            "冻结后可派单集合必须精确受控：P3-1 收口合并解除 P3-4/P3-6 阻塞、P3-6 收口后新增 P3-7 均属治理变更，须与派工书同批登记 §9",
        )

    def test_prompt_paths_and_task_ids_are_unique_in_both_directions(self):
        rows = self.readiness_rows()
        expected_ids = set(self.post_p26_task_ids())
        normalized = set()
        referenced = {}
        for row in rows:
            target = self.prompt_target(row)
            if target is None:
                continue
            rel = row["prompt_path"]
            key = os.path.normcase(str(target))
            self.assertNotIn(key, normalized, f"prompt_path 规范化后重复: {rel}")
            normalized.add(key)
            self.assertTrue(target.is_file(), f"readiness 引用的提示词不存在: {rel}")

            text = target.read_text(encoding="utf-8")
            ids = re.findall(r"(?m)^task_id: (?P<id>\S+)$", text)
            self.assertEqual([row["task_id"]], ids, f"{rel} 必须恰有一个匹配 task_id")
            name_match = self.PROMPT_FILENAME_HINT_RE.fullmatch(target.name)
            self.assertIsNotNone(name_match, f"提示词文件名缺少任务 ID: {target.name}")
            self.assertEqual(row["task_id"], name_match.group(1).upper())
            referenced[row["task_id"]] = target

        reverse = {}
        for path in self.PROMPT_ROOT.rglob("*.md"):
            if path.name.lower().startswith("prompt-template-"):
                continue
            text = path.read_text(encoding="utf-8")
            ids = re.findall(r"(?m)^task_id: (?P<id>\S+)$", text)
            name_id_match = self.PROMPT_FILENAME_HINT_RE.fullmatch(path.name)
            shape_match = self.PROMPT_FILENAME_SHAPE_RE.fullmatch(path.name)
            filename_id = name_id_match.group(1).upper() if name_id_match else None
            declared_expected = [task_id for task_id in ids if task_id in expected_ids]
            if filename_id not in expected_ids and not declared_expected:
                continue
            self.assertIsNotNone(shape_match, f"P2-6 后提示词文件名非法: {path.relative_to(ROOT)}")
            task_id = filename_id
            self.assertEqual([task_id], ids, f"后续任务文件 {path.name} 缺少合法 task_id")
            reverse.setdefault(task_id, []).append(path.resolve())
        self.assertEqual(set(referenced), set(reverse), "有提示词路由的任务必须与反向枚举完全一致")
        for task_id in referenced:
            self.assertEqual([referenced[task_id]], reverse[task_id], f"{task_id} 存在第二份竞争提示词")

    def test_reverse_prompt_hint_recognizes_bare_task_filename(self):
        bare = self.PROMPT_FILENAME_HINT_RE.fullmatch("prompt-P3-1.md")
        self.assertIsNotNone(bare, "裸任务文件名也必须进入反向治理枚举")
        self.assertEqual("P3-1", bare.group(1).upper())
        self.assertIsNone(
            self.PROMPT_FILENAME_SHAPE_RE.fullmatch("prompt-P3-1.md"),
            "裸任务文件名只能作为非法候选被发现，不能冒充正式命名",
        )

    def test_prompts_have_required_sections_without_copying_normative_schemas(self):
        forbidden = (
            r"(?i)CREATE\s+TABLE",
            r"(?i)ALTER\s+TABLE",
            r"```json",
            r"```sql",
            r"\|\s*off\s*\|\s*size\s*\|",
            r'"schemaVersion"\s*:',
        )
        for row, _target, text in self.prompt_records():
            task_id = row["task_id"]
            task_type = row["type"]
            rel = row["prompt_path"]
            with self.subTest(task=task_id):
                for section in self.REQUIRED_PROMPT_SECTIONS:
                    self.assertIn(f"## {section}", text, f"{rel} 缺少章节 {section}")
                target_heading = "## 验收范围" if task_type == "ACCEPTANCE" else "## 目标"
                self.assertIn(target_heading, text)
                if task_type == "ACCEPTANCE":
                    self.assertIn("## 正式 acceptance contract 前置", text)
                for pattern in forbidden:
                    self.assertIsNone(re.search(pattern, text), f"{rel} 复制了共享 schema/DDL/字节表")

    def test_stable_clause_ids_are_defined_once_and_all_references_exist(self):
        definitions = re.findall(r"(?m)^### (OTA-XC-[A-Z0-9-]+)$", self.contract)
        self.assertTrue(definitions, "跨系统合同没有稳定条款 ID")
        self.assertEqual(len(definitions), len(set(definitions)), "稳定条款定义 ID 重复")
        reference_text = self.contract + "\n" + self.decisions + "\n" + self.board
        for _row, _target, text in self.prompt_records():
            reference_text += "\n" + text
        references = set(re.findall(r"OTA-XC-[A-Z0-9-]+", reference_text))
        self.assertEqual(set(), references - set(definitions), "存在未定义的稳定条款引用")

    def test_decision_ids_are_monotonic_and_references_are_valid(self):
        headings = re.findall(r"(?m)^## (OTA-DEC-(\d{3}))\b", self.decisions)
        ids = [decision_id for decision_id, _number in headings]
        numbers = [int(number) for _decision_id, number in headings]
        self.assertEqual(len(ids), len(set(ids)), "decision_id 重复")
        self.assertEqual(sorted(numbers), numbers, "decision_id 必须单调递增且不重排")
        self.assertTrue(ids)
        statuses = re.findall(r"(?m)^- 状态：`([A-Z_]+)`。$", self.decisions)
        self.assertEqual(len(ids), len(statuses), "每项决定必须恰有一个状态")
        self.assertTrue(set(statuses) <= {"OPEN", "PROPOSED", "DECIDED", "SUPERSEDED"})
        self.assertEqual({"DECIDED"}, set(statuses), "用户冻结授权后十二项决定必须全部为 DECIDED")
        status_by_decision = dict(zip(ids, statuses))

        reference_text = self.contract + "\n" + self.board
        for _row, _target, text in self.prompt_records():
            reference_text += "\n" + text
        refs = set(re.findall(r"OTA-DEC-\d{3}", reference_text))
        self.assertEqual(set(), refs - set(ids), "合同或提示词引用了不存在的 decision_id")

        board_ids = set(re.findall(r"(?m)^#### ((?:PRE|P\d+)-\d+)\b", self.board))
        affected_by_decision = {}
        current_decision = None
        for line in self.decisions.splitlines():
            heading = re.match(r"^## (OTA-DEC-\d{3})\b", line)
            if heading:
                current_decision = heading.group(1)
                continue
            if not line.startswith("- 受影响任务："):
                continue
            self.assertIsNotNone(current_decision, "受影响任务字段必须位于 decision_id 标题下")
            affected = set(re.findall(r"`((?:PRE|P\d+)-\d+)`", line))
            self.assertTrue(affected, "决策受影响任务字段不能为空")
            self.assertEqual(set(), affected - board_ids, "决策引用了看板中不存在的任务")
            self.assertNotIn(current_decision, affected_by_decision, "每项决定只能有一个受影响任务字段")
            affected_by_decision[current_decision] = affected
        self.assertEqual(set(ids), set(affected_by_decision), "每项决定必须恰有一个受影响任务字段")

        routed_task_ids = {row["task_id"] for row, _target, _text in self.prompt_records()}
        prompt_blocking = {decision_id: set() for decision_id in ids}
        for row, _target, text in self.prompt_records():
            task_id = row["task_id"]
            section = text.split("## 阻断性决策", 1)[1]
            for decision_id in set(re.findall(r"OTA-DEC-\d{3}", section)):
                prompt_blocking[decision_id].add(task_id)
        expected_prompt_blocking = self.expected_active_prompt_blocking(
            ids,
            status_by_decision,
            affected_by_decision,
            routed_task_ids,
        )
        self.assertEqual(expected_prompt_blocking, prompt_blocking, "未决决定必须与提示词阻断章节双向一致")

    def test_freeze_authorization_and_contract_maturity_are_locked(self):
        authorization = (
            "批准 OTA-DEC-001 至 OTA-DEC-012，授权冻结规范并进入首批实现；"
            "生产部署仍须等待 P5 验收。"
        )
        self.assertIn("### 记录 9", self.decisions)
        self.assertEqual(1, self.decisions.count(authorization))
        self.assertIn("本轮新增条款成熟度：`FROZEN`", self.contract)
        self.assertNotIn("DRAFT_PENDING_REVIEW", self.contract)
        self.assertNotIn("阻断决定：", self.contract)

    def test_decision_status_transition_releases_prompt_blocking(self):
        decision_id = "OTA-DEC-999"
        declared = {decision_id: {"P3-1"}}
        routed = {"P3-1"}
        for status, expected in (
            ("OPEN", {"P3-1"}),
            ("PROPOSED", {"P3-1"}),
            ("DECIDED", set()),
            ("SUPERSEDED", set()),
        ):
            with self.subTest(status=status):
                actual = self.expected_active_prompt_blocking(
                    [decision_id],
                    {decision_id: status},
                    declared,
                    routed,
                )
                self.assertEqual({decision_id: expected}, actual)

    def test_proposed_decision_recommendation_cannot_be_forced_in_prompt(self):
        active = {"OTA-DEC-009"}
        outside_blocking = """## 前置依赖
- `OTA-DEC-009` 推荐方案 A，因此 P4-2 必须先完成。

## 阻断性决策

- `OTA-DEC-009`：P4 实现顺序与 fixture 边界。
"""
        forced_in_blocking = """## 阻断性决策

- `OTA-DEC-009`：P4-2 必须先于 P4-1 完成。
"""
        forced_without_id = """## 前置依赖

- 推荐方案 A，因此 P4-2 必须先于 P4-1 完成。
"""
        forced_wrapped_without_id = """## 前置依赖

- 推荐方案 A，因此 P4-2
  必须先于 P4-1 完成。
"""
        forced_nested_without_id = """## 前置依赖

- 推荐方案 A，因此
  - P4-2 必须先于 P4-1 完成。
"""
        neutral = """## 阻断性决策

- `OTA-DEC-009`：P4 实现顺序与 fixture 边界。
"""
        self.assertTrue(self.proposed_decision_requirement_violations(outside_blocking, active))
        self.assertTrue(self.proposed_decision_requirement_violations(forced_in_blocking, active))
        self.assertTrue(self.proposed_decision_requirement_violations(forced_without_id, active))
        self.assertTrue(self.proposed_decision_requirement_violations(forced_wrapped_without_id, active))
        self.assertTrue(self.proposed_decision_requirement_violations(forced_nested_without_id, active))
        self.assertEqual([], self.proposed_decision_requirement_violations(neutral, active))

    def test_frozen_decisions_leave_no_prompt_blockers(self):
        decision_statuses = dict(
            re.findall(
                r"(?ms)^## (OTA-DEC-\d{3})\b.*?^- 状态：`([A-Z_]+)`。$",
                self.decisions,
            )
        )
        active = {
            decision_id
            for decision_id, status in decision_statuses.items()
            if status in self.ACTIVE_DECISION_STATUSES
        }
        self.assertEqual(set(), active)
        for row, target, text in self.prompt_records():
            with self.subTest(task=row["task_id"]):
                violations = self.proposed_decision_requirement_violations(text, active)
                self.assertEqual([], violations, f"{target.name} 把未决决定写到了执行要求中")
                blocking_section = text.split("## 阻断性决策", 1)[1]
                self.assertNotRegex(blocking_section, r"OTA-DEC-\d{3}")

    def test_task_status_fields_only_appear_in_board_matrix(self):
        files = [self.CONTRACT, self.DECISIONS]
        files.extend(target for _row, target, _text in self.prompt_records())
        for path in files:
            text = path.read_text(encoding="utf-8")
            for field in self.TASK_STATUS_FIELDS:
                self.assertNotRegex(text, rf"\b{field}\b", f"任务级状态字段只能在 readiness 矩阵: {path}")

    def test_prompt_task_status_values_only_reference_plan_readiness(self):
        for row, target, text in self.prompt_records():
            with self.subTest(task=row["task_id"]):
                violations = self.prompt_task_status_value_violations(text)
                self.assertEqual(
                    [],
                    violations,
                    f"{target.name} 复制了任务状态值或非法别名；状态唯一来源必须是 PLAN-OTA-EXEC.md readiness 行",
                )

        allowed_reference = (
            "按 `PLAN-OTA-EXEC.md` readiness 矩阵的 `P3-1` 行执行；"
            "该行的 content_readiness=READY。"
        )
        self.assertEqual([], self.prompt_task_status_value_violations(allowed_reference))
        self.assertEqual(
            [(1, "READY", "content_readiness=READY")],
            self.prompt_task_status_value_violations("content_readiness=READY"),
        )
        self.assertEqual(
            [(1, "READY_FOR_REVIEW", "状态=READY_FOR_REVIEW")],
            self.prompt_task_status_value_violations("状态=READY_FOR_REVIEW"),
        )

    def test_digest_domains_are_explicit_and_non_interchangeable(self):
        identity = self.contract.split("### OTA-XC-IMAGE-IDENTITY", 1)[1].split("### ", 1)[0]
        raw_base = self.markdown_table_row(identity, ".etu base_sha8")
        etsl = self.markdown_table_row(identity, "ETSL.sha8")
        candidate = self.markdown_table_row(identity, "candidateImageSha8")

        self.assertIn("app.bin", raw_base[1])
        self.assertIn("image_len", raw_base[1])
        self.assertIn("raw 镜像 SHA", raw_base[2])
        self.assertNotIn("fw_header.image_sha256", raw_base[1])
        self.assertNotIn("双零", raw_base[1])

        for label, row in (("ETSL.sha8", etsl), ("candidateImageSha8", candidate)):
            with self.subTest(domain=label):
                self.assertIn("fw_header.image_sha256", row[1])
                self.assertIn("双零法", row[1])
                self.assertNotIn("raw", row[1].lower())

        self.assertIn("ETSL.sha8", identity)
        self.assertIn("candidateImageSha8", identity)
        self.assertIn("32B raw", identity)
        self.assertIn("header-integrity", identity)
        self.assertIn("不得作为 patch 基版完整身份", etsl[3])
        self.assertIn("不得替代 32B raw SHA", candidate[3])

        vector = self.contract_vector_row(self.contract, "XC-DIGEST-DOMAINS")
        for token in (
            "raw SHA",
            "fw_header 双零 SHA",
            "各自 SHA8",
            "raw SHA8 与 header SHA8 不同",
            "`.etu base_sha8` 使用 raw 前 8B",
            "ETSL/candidateImageSha8 使用 fw_header 双零摘要前 8B",
            "任何域交叉替代均失败",
        ):
            self.assertIn(token, vector)

    def test_admin_tombstone_and_cron_race_have_stable_boundary_results(self):
        admin_idempotency = self.contract.split("### OTA-XC-ADMIN-IDEMPOTENCY", 1)[1].split("### ", 1)[0]
        for token in (
            "firmware_admin_idempotency_tombstones",
            "永久的",
            "`expired_at`",
            "`tombstoned_at`",
            "PRIMARY KEY/UNIQUE 为 `(actor_canonical,idempotency_key)`",
            "INDEX(expired_at)",
            "tombstone 永久保留",
            "不保存 response body、URL、token、signature 或 secret",
            "fingerprint 相同返回 `IDEMPOTENCY_RESULT_EXPIRED`",
            "fingerprint 不同返回 `IDEMPOTENCY_CONFLICT`",
            "不得重新进入 pending 或业务副作用",
            "`currentEpochSeconds == retainedUntil` 与更晚时刻均已过期",
            "当 `currentEpochSeconds >= retainedUntil` 时",
            "必须先以原 fingerprint/action/release 写入或核对 tombstone",
            "确认成功后才可删除完整结果行",
            "不得先删后补",
            "tombstone 永不删除",
            "先提交者留下 tombstone",
            "后提交者重读该 tombstone",
            "不得因 Cron 先后改变结果或产生新 mutation/token/audit",
        ):
            self.assertIn(token, admin_idempotency)

        boundary = self.contract_vector_row(self.contract, "XC-ADMIN-IDEMPOTENT-BOUNDARY")
        for token in (
            "created=1800000000",
            "retainedUntil=1800086400",
            "1800086400",
            "先写/确认 tombstone",
            "IDEMPOTENCY_RESULT_EXPIRED",
            "均无新副作用",
        ):
            self.assertIn(token, boundary)

        expired_conflict = self.contract_vector_row(self.contract, "XC-ADMIN-IDEMPOTENT-EXPIRED-CONFLICT")
        for token in (
            "结果行存在或已由 Cron 清理",
            "同 fingerprint 为 `IDEMPOTENCY_RESULT_EXPIRED`",
            "不同 fingerprint 为 `IDEMPOTENCY_CONFLICT`",
            "不论清理先后",
        ):
            self.assertIn(token, expired_conflict)

        race = self.contract_vector_row(self.contract, "XC-ADMIN-IDEMPOTENT-TOMBSTONE-RACE")
        for token in (
            "请求事务先提交",
            "Cron 先提交",
            "两者并发",
            "三种调度都只留下一个相同 tombstone",
            "无第二次 mutation/token/audit",
            "响应按 fingerprint 稳定",
        ):
            self.assertIn(token, race)

    def test_interface_matrix_has_required_interface_level_fields(self):
        required = (
            "Producer",
            "Consumer",
            "传输介质",
            "条款 ID",
            "schema 或结构引用",
            "生命周期所有者",
            "错误语义",
            "幂等规则",
            "兼容规则",
            "interface_completeness",
            "clause_maturity",
            "blocking_decisions",
            "affected_tasks",
        )
        section = self.contract.split("## 2. 接口矩阵", 1)[1].split("## 3.", 1)[0]
        table = [line for line in section.splitlines() if line.startswith("|")]
        self.assertGreaterEqual(len(table), 3)
        header = table[0]
        for field in required:
            self.assertIn(field, header)
        columns = [cell.strip() for cell in header.strip("|").split("|")]
        rows = []
        for line in table[2:]:
            cells = [cell.strip() for cell in line.strip("|").split("|")]
            self.assertEqual(len(columns), len(cells), f"接口矩阵列数错误: {line}")
            rows.append(dict(zip(columns, cells)))
        self.assertTrue(rows)
        decision_statuses = dict(
            re.findall(
                r"(?ms)^## (OTA-DEC-\d{3})\b.*?^- 状态：`([A-Z_]+)`。$",
                self.decisions,
            )
        )
        known_decisions = set(decision_statuses)
        blocking_decisions = {
            decision_id
            for decision_id, status in decision_statuses.items()
            if status in {"OPEN", "PROPOSED"}
        }
        self.assertEqual({"DECIDED"}, set(decision_statuses.values()))
        self.assertEqual(set(), blocking_decisions)
        clause_matches = list(re.finditer(r"(?m)^### (OTA-XC-[A-Z0-9-]+)$", self.contract))
        clause_sections = {}
        for index, match in enumerate(clause_matches):
            end = clause_matches[index + 1].start() if index + 1 < len(clause_matches) else len(self.contract)
            clause_sections[match.group(1)] = self.contract[match.end() : end]

        prompt_contract_refs = {}
        for prompt_row, _target, text in self.prompt_records():
            contract_section = text.split("## 权威合同", 1)[1].split("## ", 1)[0]
            prompt_contract_refs[prompt_row["task_id"]] = set(
                re.findall(r"OTA-XC-[A-Z0-9-]+", contract_section)
            )
        board_ids = set(re.findall(r"(?m)^#### ((?:PRE|P\d+)-\d+)\b", self.board))
        for row in rows:
            completeness = row["interface_completeness"].strip("`")
            maturity = row["clause_maturity"].strip("`")
            decisions = set(re.findall(r"OTA-DEC-\d{3}", row["blocking_decisions"]))
            affected_tasks = set(re.findall(r"(?:PRE|P\d+)-\d+", row["affected_tasks"]))
            clauses = set(re.findall(r"OTA-XC-[A-Z0-9-]+", row["条款 ID"]))
            self.assertIn(completeness, {"COMPLETE", "INCOMPLETE", "BLOCKED_BY_DECISION"})
            self.assertEqual("COMPLETE", completeness)
            self.assertEqual("FROZEN", maturity)
            self.assertEqual(set(), decisions, "冻结接口矩阵不得保留决定阻断")
            self.assertEqual(set(), decisions - known_decisions, "接口矩阵引用了不存在的决定")
            self.assertEqual(set(), decisions - blocking_decisions, "接口矩阵只能把 OPEN/PROPOSED 决定列为阻断")
            self.assertEqual(set(), affected_tasks - board_ids, "接口矩阵引用了不存在的任务")
            self.assertEqual(set(), clauses - set(clause_sections), "接口矩阵引用了不存在的稳定条款")

            clause_blockers = set()
            for clause in clauses:
                clause_blockers.update(re.findall(r"OTA-DEC-\d{3}", clause_sections[clause]))
            clause_blockers &= blocking_decisions
            self.assertEqual(
                set(),
                clause_blockers - decisions,
                f"接口矩阵未传播条款正文中的开放决定: {sorted(clauses)}",
            )

            consumer_clauses = clauses & self.PROPAGATED_CONSUMER_CLAUSES
            required_consumers = {
                task_id
                for task_id, references in prompt_contract_refs.items()
                if references & consumer_clauses
            }
            self.assertEqual(
                set(),
                required_consumers - affected_tasks,
                f"接口矩阵未传播逐卡提示词中的接口消费者: {sorted(consumer_clauses)}",
            )
            if decisions:
                self.assertEqual(
                    "BLOCKED_BY_DECISION",
                    completeness,
                    "存在 blocking_decisions 时必须按优先级传播为 BLOCKED_BY_DECISION",
                )
            else:
                self.assertNotEqual(
                    "BLOCKED_BY_DECISION",
                    completeness,
                    "BLOCKED_BY_DECISION 必须列出实际决定",
                )
            if completeness == "COMPLETE":
                self.assertFalse(decisions, "COMPLETE 接口不得保留阻断决定")

    def test_admin_http_contract_covers_release_actions_recovery_and_audit(self):
        section = self.contract.split("### OTA-XC-HTTP-ADMIN", 1)[1].split("### ", 1)[0]
        required_tokens = (
            "/api/admin/firmware/releases/{releaseId}/disable",
            "/api/admin/firmware/releases/{releaseId}/recovery-download",
            '"action": "disable_release"',
            '"action": "issue_recovery_download"',
            "purpose=admin-recovery",
            "RELEASE_NOT_READY",
            "RELEASE_DISABLED",
            "RELEASE_ARCHIVED",
            "RELEASE_IN_USE",
            "RECOVERY_ASSET_UNAVAILABLE",
        )
        for token in required_tokens:
            self.assertIn(token, section, f"Admin HTTP 合同缺少 {token}")

        audit = self.contract.split("### OTA-XC-D1-AUDIT", 1)[1].split("### ", 1)[0]
        audit_tokens = (
            "`disable_release`",
            "`issue_recovery_download`",
            "`target_type=firmware_release`",
            "`target_type=firmware_asset`",
            "`target_id=releaseId`",
            "`target_id=assetId`",
            "`purpose=admin-recovery`",
            "不得包含完整 URL、token、signature",
            "不能承担 release action 的幂等键",
        )
        for token in audit_tokens:
            self.assertIn(token, audit, f"Admin audit 合同缺少 {token}")

    def test_admin_idempotency_and_download_token_migrations_are_decision_governed(self):
        admin_idempotency = self.contract.split("### OTA-XC-ADMIN-IDEMPOTENCY", 1)[1].split("### ", 1)[0]
        for token in (
            "OTA-DEC-011",
            "X-Request-Id",
            "request fingerprint",
            "保存期限",
            "recovery URL 过期",
        ):
            self.assertIn(token, admin_idempotency)

        idempotency_decision = self.decisions.split("## OTA-DEC-011", 1)[1].split("## OTA-DEC-012", 1)[0]
        for token in (
            "Idempotency-Key",
            "Access actor + key",
            "method",
            "canonical JSON body",
            "保存 24 小时",
            "同 key/不同 fingerprint",
            "recovery URL 过期后",
            "新 key",
        ):
            self.assertIn(token, idempotency_decision)

        download = self.contract.split("### OTA-XC-HTTP-DOWNLOAD", 1)[1].split("### ", 1)[0]
        for token in (
            "assetId",
            "releaseId",
            "expiresAt",
            "keyVersion",
            "signature",
            "Unix epoch 秒",
            "OTA-DEC-012",
            "v1 token",
        ):
            self.assertIn(token, download)

        decision = self.decisions.split("## OTA-DEC-012", 1)[1]
        for token in (
            "tokenVersion=2",
            "kind",
            "purpose",
            "HMAC-SHA256 Base64URL 无 padding",
            "部署前已签的 full/patch URL",
            "永不允许 recovery",
        ):
            self.assertIn(token, decision)

    def test_shared_specs_are_required_by_manifest_and_watched_by_ci(self):
        profiles = json.loads(self.MANIFEST_PROFILES.read_text(encoding="utf-8"))
        governance = profiles["profiles"]["Governance"]
        workflow = self.WORKFLOW.read_text(encoding="utf-8")
        for rel in ("docs/ota-cross-system-contracts.md", "docs/ota-spec-decisions.md"):
            self.assertIn(rel, governance["top_files"])
            self.assertIn(rel, governance["required_paths"])
            self.assertEqual(2, workflow.count(f'- "{rel}"'), f"push/PR 必须都监听 {rel}")
            self.assertIn(rel, set(VALIDATOR._profile_paths(ROOT, "Governance")))


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
