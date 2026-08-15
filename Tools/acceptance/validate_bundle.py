#!/usr/bin/env python3
import argparse
import hashlib
import json
import operator
import re
import subprocess
import sys
from pathlib import Path


CONTRACT_SCHEMA = "etrack-acceptance-contract-v2"
MATRIX_SCHEMA = "etrack-evidence-matrix-v2"
RERUN_SCHEMA = "etrack-rerun-plan-v1"
INPUT_MANIFEST_SCHEMA = "etrack-input-manifest-v2"
INPUT_MANIFEST_ORDERING = "UTF-8 normalized slash paths, bytewise Ordinal ascending"
INPUT_MANIFEST_ENCODING = "UTF-8 without BOM, CRLF, one trailing newline"
OVERALL_RESULTS = {
    "PASS",
    "PRODUCT_FAIL",
    "HARNESS_FAIL",
    "EVIDENCE_GAP",
    "ENV_BLOCKED",
    "NOT_RUN",
}
FINAL_RESULTS = OVERALL_RESULTS - {"NOT_RUN"}
CRITERION_RESULTS = {"PASS", "FAIL", "NOT_OBSERVED"}
FAILURE_OWNERS = {"product", "harness", "evidence", "environment"}
RESULT_TAXONOMY = FINAL_RESULTS - {"NOT_RUN"}
EXECUTION_MODES = {"EXECUTED", "REUSED"}
GATE_TYPES = {"boolean", "numeric", "state_chain"}
GATE_BASES = {
    "frozen_requirement",
    "product_sla",
    "safety_ratio",
    "protocol_contract",
}
PERFORMANCE_GATE_BASES = {"product_sla", "safety_ratio", "protocol_contract"}
NUMERIC_OPERATORS = {
    "lt": operator.lt,
    "le": operator.le,
    "eq": operator.eq,
    "ge": operator.ge,
    "gt": operator.gt,
}
REQUIRED_INPUT_GROUPS = {
    "production": ("Production", "production_source"),
    "validation": ("Validation", "validation_inputs"),
    "governance": ("Governance", "governance_inputs"),
}
MANIFEST_PROFILE_CONFIG_PATH = (
    Path(__file__).resolve().parents[1] / "provenance" / "manifest_profiles.json"
)
EXTERNAL_INPUT_CATEGORIES = {"fixture", "hardware_state", "toolchain", "environment"}
CRITERION_KINDS = {"functional", "safety", "performance", "visual", "process"}
SHA256_RE = re.compile(r"^[0-9A-Fa-f]{64}$")


def _load_manifest_profile_config():
    try:
        config = json.loads(MANIFEST_PROFILE_CONFIG_PATH.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise RuntimeError(f"cannot load manifest profile config: {exc}") from exc
    if not isinstance(config, dict) or config.get("schema") != "etrack-manifest-profiles-v1":
        raise RuntimeError("manifest profile config schema is invalid")
    if set(config) != {"schema", "exclude_path_regex", "profiles"}:
        raise RuntimeError("manifest profile config fields are invalid")
    profiles = config.get("profiles")
    if not isinstance(profiles, dict) or set(profiles) != {
        "Legacy",
        "Production",
        "Validation",
        "Governance",
    }:
        raise RuntimeError("manifest profile config must define all four profiles exactly once")
    for profile, definition in profiles.items():
        if not isinstance(definition, dict) or set(definition) != {
            "root_patterns",
            "top_files",
            "exclude_prefixes",
            "required_paths",
        }:
            raise RuntimeError(f"manifest profile fields are invalid: {profile}")
        for field in ("root_patterns", "top_files", "exclude_prefixes", "required_paths"):
            values = definition.get(field)
            if not isinstance(values, list) or not all(
                isinstance(value, str) and value for value in values
            ):
                raise RuntimeError(f"manifest profile {profile}.{field} is invalid")
    try:
        re.compile(config.get("exclude_path_regex"))
    except (TypeError, re.error) as exc:
        raise RuntimeError(f"manifest exclude regex is invalid: {exc}") from exc
    return config


MANIFEST_PROFILE_CONFIG = _load_manifest_profile_config()
PROFILE_DEFINITIONS = MANIFEST_PROFILE_CONFIG["profiles"]
PROFILE_EXCLUDE_RE = re.compile(MANIFEST_PROFILE_CONFIG["exclude_path_regex"])
PROFILE_REQUIRED_PATHS = {
    profile: set(definition["required_paths"])
    for profile, definition in PROFILE_DEFINITIONS.items()
}


def _nonempty(value):
    return isinstance(value, str) and bool(value.strip())


def _is_sha256(value):
    return isinstance(value, str) and SHA256_RE.fullmatch(value) is not None


def _list_of_strings(value, allow_empty=False):
    return (
        isinstance(value, list)
        and (allow_empty or bool(value))
        and all(_nonempty(item) for item in value)
    )


def _list_of_ints(value):
    return (
        isinstance(value, list)
        and bool(value)
        and all(isinstance(item, int) and not isinstance(item, bool) for item in value)
    )


def _is_bundle_relative(value):
    if not _nonempty(value):
        return False
    path = Path(value.replace("\\", "/"))
    return not path.is_absolute() and ".." not in path.parts


def _is_repo_relative(value):
    if not _nonempty(value) or "\\" in value or value.startswith("/"):
        return False
    if re.match(r"^[A-Za-z]:", value):
        return False
    parts = value.split("/")
    return all(part not in {"", ".", ".."} for part in parts)


def _canonical(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True)


def _json_sha256(value):
    return hashlib.sha256(_canonical(value).encode("utf-8")).hexdigest().upper()


def _records_by_id(items):
    return {
        item["id"]: item
        for item in items or []
        if isinstance(item, dict) and _nonempty(item.get("id"))
    }


def _input_group_signature(group):
    if not isinstance(group, dict):
        return None
    return {
        "id": group.get("id"),
        "profile": group.get("profile"),
        "category": group.get("category"),
        "manifest_sha256": group.get("manifest_sha256"),
    }


def _external_input_signature(item):
    if not isinstance(item, dict):
        return None
    return {
        "id": item.get("id"),
        "category": item.get("category"),
        "description": item.get("description"),
        "fingerprint": item.get("fingerprint"),
        "evidence_sha256": item.get("evidence_sha256"),
    }


def _manifest_text_bytes(records):
    lines = [
        f"{record['SHA256'].upper()}  {record['Length']}  {record['Path']}"
        for record in records
    ]
    return (("\r\n".join(lines)) + "\r\n").encode("utf-8")


def _is_link_or_reparse(path):
    if path.is_symlink():
        return True
    is_junction = getattr(path, "is_junction", None)
    if is_junction is not None and is_junction():
        return True
    try:
        attributes = path.lstat().st_file_attributes
    except (AttributeError, OSError):
        return False
    return bool(attributes & 0x400)


def _resolve_git_worktree(repo_root):
    requested = Path(repo_root).absolute()
    if not requested.is_dir():
        raise ValueError(f"repository root is not a directory: {requested}")
    if _is_link_or_reparse(requested):
        raise ValueError(f"repository root must not be a link or reparse point: {requested}")
    result = subprocess.run(
        ["git", "-C", str(requested), "rev-parse", "--show-toplevel"],
        capture_output=True,
        check=False,
    )
    if result.returncode != 0:
        message = result.stderr.decode("utf-8", errors="replace").strip()
        raise ValueError(f"cannot resolve Git worktree root: {message or result.returncode}")
    try:
        git_root = Path(result.stdout.decode("utf-8").strip()).resolve(strict=True)
        requested_root = requested.resolve(strict=True)
    except (OSError, UnicodeError) as exc:
        raise ValueError(f"cannot resolve repository root: {exc}") from exc
    if git_root != requested_root:
        raise ValueError(
            f"repository root must be the Git worktree top level: requested={requested_root} git={git_root}"
        )
    return git_root


def _profile_paths(repo_root, profile):
    definition = PROFILE_DEFINITIONS.get(profile)
    if definition is None:
        raise ValueError(f"manifest profile is not defined: {profile}")
    pathspecs = definition["root_patterns"] + definition["top_files"]
    result = subprocess.run(
        [
            "git",
            "-C",
            str(repo_root),
            "ls-files",
            "-co",
            "--exclude-standard",
            "-z",
            "--",
            *pathspecs,
        ],
        capture_output=True,
        check=False,
    )
    if result.returncode != 0:
        message = result.stderr.decode("utf-8", errors="replace").strip()
        raise ValueError(f"git ls-files failed for {profile}: {message or result.returncode}")
    try:
        candidates = [
            item.decode("utf-8").replace("\\", "/")
            for item in result.stdout.split(b"\0")
            if item
        ]
    except UnicodeError as exc:
        raise ValueError(f"git returned a non-UTF-8 path for {profile}: {exc}") from exc

    selected = set()
    top_files = set(definition["top_files"])
    for path in candidates:
        if ".base@" in Path(path).name:
            continue
        if any(path.startswith(prefix) for prefix in definition["exclude_prefixes"]):
            continue
        if path in top_files:
            selected.add(path)
            continue
        for prefix in definition["root_patterns"]:
            if path.startswith(prefix):
                if not PROFILE_EXCLUDE_RE.search(path):
                    selected.add(path)
                break
    return sorted(selected, key=lambda path: path.encode("utf-8"))


def _collect_profile_records(repo_root, profile):
    root = _resolve_git_worktree(repo_root)
    records = []
    for relative_path in _profile_paths(root, profile):
        if not _is_repo_relative(relative_path):
            raise ValueError(f"profile selected an invalid repository path: {relative_path}")
        source = root.joinpath(*relative_path.split("/"))
        if _is_link_or_reparse(source):
            raise ValueError(f"manifest source is a link or reparse point: {relative_path}")
        if not source.is_file():
            continue
        try:
            resolved = source.resolve(strict=True)
            resolved.relative_to(root)
            data = source.read_bytes()
        except ValueError as exc:
            raise ValueError(f"manifest source escapes the worktree: {relative_path}") from exc
        except OSError as exc:
            raise ValueError(f"cannot read manifest source {relative_path}: {exc}") from exc
        records.append(
            {
                "Path": relative_path,
                "Length": len(data),
                "SHA256": hashlib.sha256(data).hexdigest().upper(),
            }
        )
    return records


def _gate_satisfied(gate, observed):
    if not isinstance(gate, dict):
        return None
    gate_type = gate.get("type")
    if gate_type == "boolean":
        if not isinstance(observed, bool):
            return None
        return observed is gate.get("expected")
    if gate_type == "numeric":
        if not isinstance(observed, dict):
            return None
        value = observed.get("value")
        if not isinstance(value, (int, float)) or isinstance(value, bool):
            return None
        if observed.get("unit") != gate.get("unit"):
            return None
        operation = NUMERIC_OPERATORS.get(gate.get("operator"))
        if operation is None:
            return None
        return operation(value, gate.get("limit"))
    if gate_type == "state_chain":
        if not _list_of_strings(observed):
            return None
        return observed == gate.get("expected")
    return None


def validate_contract(contract, allow_draft=False):
    errors = []
    if not isinstance(contract, dict):
        return ["contract root must be an object"]
    if contract.get("schema") != CONTRACT_SCHEMA:
        errors.append(f"contract schema must be {CONTRACT_SCHEMA}")
    for field in ("contract_id", "task_id", "invalidation_policy"):
        if not _nonempty(contract.get(field)):
            errors.append(f"contract.{field} must be a non-empty string")
    version = contract.get("version")
    if not isinstance(version, int) or isinstance(version, bool) or version < 1:
        errors.append("contract.version must be a positive integer")
    task_id = contract.get("task_id")
    contract_id = contract.get("contract_id")
    if _nonempty(task_id) and isinstance(version, int) and not isinstance(version, bool):
        expected_contract_id = f"{task_id}-v{version}"
        if contract_id != expected_contract_id:
            errors.append(f"contract.contract_id must be {expected_contract_id}")
    parent_hash = contract.get("parent_contract_sha256")
    if version == 1:
        if parent_hash is not None:
            errors.append("contract.parent_contract_sha256 must be null for version 1")
    elif isinstance(version, int) and not isinstance(version, bool) and version > 1:
        if not _is_sha256(parent_hash):
            errors.append("contract.parent_contract_sha256 must bind the previous contract")
    status = contract.get("status")
    if status not in {"DRAFT", "FROZEN"}:
        errors.append("contract.status must be DRAFT or FROZEN")
    if status != "FROZEN" and not allow_draft:
        errors.append("contract must be FROZEN")
    if status == "FROZEN":
        for field in ("approved_by", "approved_at", "implementation_ref"):
            if not _nonempty(contract.get(field)):
                errors.append(f"frozen contract.{field} must be set")

    taxonomy = contract.get("result_taxonomy")
    if not isinstance(taxonomy, list) or set(taxonomy) != RESULT_TAXONOMY:
        errors.append("contract.result_taxonomy must contain the five final results exactly once")
    elif len(taxonomy) != len(set(taxonomy)):
        errors.append("contract.result_taxonomy contains duplicates")

    input_groups = contract.get("input_groups")
    if not isinstance(input_groups, list):
        errors.append("contract.input_groups must be a list")
        input_groups = []
    input_ids = set()
    for index, group in enumerate(input_groups):
        prefix = f"contract.input_groups[{index}]"
        if not isinstance(group, dict):
            errors.append(f"{prefix} must be an object")
            continue
        group_id = group.get("id")
        if not _nonempty(group_id):
            errors.append(f"{prefix}.id must be a non-empty string")
            continue
        if group_id in input_ids:
            errors.append(f"duplicate input group id: {group_id}")
        input_ids.add(group_id)
        expected = REQUIRED_INPUT_GROUPS.get(group_id)
        if expected is None:
            errors.append(f"{prefix}.id must be production, validation, or governance")
        else:
            expected_profile, expected_category = expected
            if group.get("profile") != expected_profile:
                errors.append(f"{prefix}.profile must be {expected_profile}")
            if group.get("category") != expected_category:
                errors.append(f"{prefix}.category must be {expected_category}")
        if not _is_bundle_relative(group.get("manifest_path")):
            errors.append(f"{prefix}.manifest_path must stay inside the bundle")
        if not _is_sha256(group.get("manifest_sha256")):
            errors.append(f"{prefix}.manifest_sha256 must be a stable file-set SHA-256")
        if not _is_sha256(group.get("manifest_json_sha256")):
            errors.append(f"{prefix}.manifest_json_sha256 must be a JSON file SHA-256")
    if input_ids != set(REQUIRED_INPUT_GROUPS):
        missing = sorted(set(REQUIRED_INPUT_GROUPS) - input_ids)
        extra = sorted(input_ids - set(REQUIRED_INPUT_GROUPS))
        if missing:
            errors.append("contract.input_groups is missing required groups: " + ", ".join(missing))
        if extra:
            errors.append("contract.input_groups has unsupported groups: " + ", ".join(extra))

    external_inputs = contract.get("external_inputs", [])
    if not isinstance(external_inputs, list):
        errors.append("contract.external_inputs must be a list")
        external_inputs = []
    external_ids = set()
    for index, item in enumerate(external_inputs):
        prefix = f"contract.external_inputs[{index}]"
        if not isinstance(item, dict):
            errors.append(f"{prefix} must be an object")
            continue
        item_id = item.get("id")
        if not _nonempty(item_id):
            errors.append(f"{prefix}.id must be set")
        elif item_id in external_ids:
            errors.append(f"duplicate external input id: {item_id}")
        else:
            external_ids.add(item_id)
        if item.get("category") not in EXTERNAL_INPUT_CATEGORIES:
            errors.append(f"{prefix}.category is invalid")
        for field in ("description", "fingerprint"):
            if not _nonempty(item.get(field)):
                errors.append(f"{prefix}.{field} must be set")
        if not _is_bundle_relative(item.get("evidence_path")):
            errors.append(f"{prefix}.evidence_path must stay inside the bundle")
        if not _is_sha256(item.get("evidence_sha256")):
            errors.append(f"{prefix}.evidence_sha256 must be a SHA-256")

    commands = contract.get("commands")
    if not isinstance(commands, list) or not commands:
        errors.append("contract.commands must be a non-empty list")
        commands = []
    command_ids = set()
    for index, command in enumerate(commands):
        prefix = f"contract.commands[{index}]"
        if not isinstance(command, dict):
            errors.append(f"{prefix} must be an object")
            continue
        command_id = command.get("id")
        if not _nonempty(command_id):
            errors.append(f"{prefix}.id must be set")
        elif command_id in command_ids:
            errors.append(f"duplicate command id: {command_id}")
        else:
            command_ids.add(command_id)
        for field in ("description", "command"):
            if not _nonempty(command.get(field)):
                errors.append(f"{prefix}.{field} must be set")
        if not _list_of_ints(command.get("expected_exit_codes")):
            errors.append(f"{prefix}.expected_exit_codes must be a non-empty integer list")
        elif len(command["expected_exit_codes"]) != len(set(command["expected_exit_codes"])):
            errors.append(f"{prefix}.expected_exit_codes contains duplicates")
        if not isinstance(command.get("output_required"), bool):
            errors.append(f"{prefix}.output_required must be boolean")

    artifacts = contract.get("artifacts")
    if not isinstance(artifacts, list) or not artifacts:
        errors.append("contract.artifacts must be a non-empty list")
        artifacts = []
    artifact_ids = set()
    for index, artifact in enumerate(artifacts):
        prefix = f"contract.artifacts[{index}]"
        if not isinstance(artifact, dict):
            errors.append(f"{prefix} must be an object")
            continue
        artifact_id = artifact.get("id")
        if not _nonempty(artifact_id):
            errors.append(f"{prefix}.id must be set")
        elif artifact_id in artifact_ids:
            errors.append(f"duplicate artifact id: {artifact_id}")
        else:
            artifact_ids.add(artifact_id)
        if not _nonempty(artifact.get("description")):
            errors.append(f"{prefix}.description must be set")
        if not _is_bundle_relative(artifact.get("path")):
            errors.append(f"{prefix}.path must stay inside the bundle")

    criteria = contract.get("criteria")
    if not isinstance(criteria, list) or not criteria:
        errors.append("contract.criteria must be a non-empty list")
        criteria = []
    criterion_ids = set()
    referenced_commands = set()
    referenced_artifacts = set()
    for index, criterion in enumerate(criteria):
        prefix = f"contract.criteria[{index}]"
        if not isinstance(criterion, dict):
            errors.append(f"{prefix} must be an object")
            continue
        criterion_id = criterion.get("id")
        if not _nonempty(criterion_id):
            errors.append(f"{prefix}.id must be a non-empty string")
        elif criterion_id in criterion_ids:
            errors.append(f"duplicate criterion id: {criterion_id}")
        else:
            criterion_ids.add(criterion_id)
        if not _nonempty(criterion.get("description")):
            errors.append(f"{prefix}.description must be a non-empty string")
        if not isinstance(criterion.get("required"), bool):
            errors.append(f"{prefix}.required must be boolean")
        if criterion.get("kind") not in CRITERION_KINDS:
            errors.append(f"{prefix}.kind is invalid")
        if not _list_of_strings(criterion.get("evidence_types")):
            errors.append(f"{prefix}.evidence_types must be a non-empty string list")

        dependencies = criterion.get("input_groups")
        if not _list_of_strings(dependencies):
            errors.append(f"{prefix}.input_groups must be a non-empty string list")
            dependencies = []
        unknown_inputs = sorted(set(dependencies) - set(REQUIRED_INPUT_GROUPS))
        if unknown_inputs:
            errors.append(f"{prefix}.input_groups has unknown ids: " + ", ".join(unknown_inputs))

        external_dependencies = criterion.get("external_inputs", [])
        if not _list_of_strings(external_dependencies, allow_empty=True):
            errors.append(f"{prefix}.external_inputs must be a string list")
            external_dependencies = []
        unknown_external = sorted(set(external_dependencies) - external_ids)
        if unknown_external:
            errors.append(f"{prefix}.external_inputs has unknown ids: " + ", ".join(unknown_external))

        criterion_commands = criterion.get("command_ids")
        if not _list_of_strings(criterion_commands):
            errors.append(f"{prefix}.command_ids must be a non-empty string list")
            criterion_commands = []
        unknown_commands = sorted(set(criterion_commands) - command_ids)
        if unknown_commands:
            errors.append(f"{prefix}.command_ids has unknown ids: " + ", ".join(unknown_commands))
        referenced_commands.update(criterion_commands)

        criterion_artifacts = criterion.get("artifact_ids")
        if not _list_of_strings(criterion_artifacts):
            errors.append(f"{prefix}.artifact_ids must be a non-empty string list")
            criterion_artifacts = []
        unknown_artifacts = sorted(set(criterion_artifacts) - artifact_ids)
        if unknown_artifacts:
            errors.append(f"{prefix}.artifact_ids has unknown ids: " + ", ".join(unknown_artifacts))
        referenced_artifacts.update(criterion_artifacts)

        gate = criterion.get("gate")
        if not isinstance(gate, dict):
            errors.append(f"{prefix}.gate must be an object")
            continue
        gate_type = gate.get("type")
        gate_basis = gate.get("basis")
        if gate_type not in GATE_TYPES:
            errors.append(f"{prefix}.gate.type is invalid")
        if criterion.get("kind") == "performance" and gate_basis not in PERFORMANCE_GATE_BASES:
            errors.append(
                f"{prefix}.gate.basis for performance must be product_sla, "
                "safety_ratio, or protocol_contract"
            )
        elif gate_basis not in GATE_BASES:
            errors.append(f"{prefix}.gate.basis is invalid or historically fitted")
        if gate_type == "boolean" and not isinstance(gate.get("expected"), bool):
            errors.append(f"{prefix}.gate.expected must be boolean")
        if gate_type == "numeric":
            if gate.get("operator") not in NUMERIC_OPERATORS:
                errors.append(f"{prefix}.gate.operator is invalid")
            if not isinstance(gate.get("limit"), (int, float)) or isinstance(gate.get("limit"), bool):
                errors.append(f"{prefix}.gate.limit must be numeric")
            if not _nonempty(gate.get("unit")):
                errors.append(f"{prefix}.gate.unit must be set")
            if not _nonempty(gate.get("rationale")):
                errors.append(f"{prefix}.gate.rationale must explain the SLA or safety basis")
        if gate_type == "state_chain" and not _list_of_strings(gate.get("expected")):
            errors.append(f"{prefix}.gate.expected must be a non-empty state list")

    unreferenced_commands = sorted(command_ids - referenced_commands)
    unreferenced_artifacts = sorted(artifact_ids - referenced_artifacts)
    if unreferenced_commands:
        errors.append("contract.commands contains unreferenced ids: " + ", ".join(unreferenced_commands))
    if unreferenced_artifacts:
        errors.append("contract.artifacts contains unreferenced ids: " + ", ".join(unreferenced_artifacts))

    performance_gates = contract.get("performance_gates", [])
    if not isinstance(performance_gates, list):
        errors.append("contract.performance_gates must be a list")
    else:
        for index, gate in enumerate(performance_gates):
            prefix = f"contract.performance_gates[{index}]"
            if not isinstance(gate, dict):
                errors.append(f"{prefix} must be an object")
                continue
            for field in ("id", "metric", "unit", "rationale"):
                if not _nonempty(gate.get(field)):
                    errors.append(f"{prefix}.{field} must be set")
            if not isinstance(gate.get("limit"), (int, float)) or isinstance(gate.get("limit"), bool):
                errors.append(f"{prefix}.limit must be numeric")
            if gate.get("basis") not in PERFORMANCE_GATE_BASES:
                errors.append(f"{prefix}.basis must not be a historical measurement")
    return errors


def validate_matrix(matrix, contract, contract_sha256, allow_draft=False):
    errors = []
    if not isinstance(matrix, dict):
        return ["matrix root must be an object"]
    if matrix.get("schema") != MATRIX_SCHEMA:
        errors.append(f"matrix schema must be {MATRIX_SCHEMA}")
    if matrix.get("contract_id") != contract.get("contract_id"):
        errors.append("matrix.contract_id does not match contract")
    matrix_hash = matrix.get("contract_sha256")
    zero_hash = "0" * 64
    if matrix_hash != contract_sha256 and not (allow_draft and matrix_hash == zero_hash):
        errors.append("matrix.contract_sha256 does not match the contract file")
    if not _nonempty(matrix.get("round_id")):
        errors.append("matrix.round_id must be set")
    overall = matrix.get("overall_result")
    if overall not in OVERALL_RESULTS:
        errors.append("matrix.overall_result is invalid")

    evidence_hashes = matrix.get("evidence_hashes")
    if not isinstance(evidence_hashes, dict):
        errors.append("matrix.evidence_hashes must be an object")
        evidence_hashes = {}
    else:
        for path, digest in evidence_hashes.items():
            if not _is_bundle_relative(path):
                errors.append(f"matrix.evidence_hashes path must stay inside the bundle: {path}")
            if not _is_sha256(digest):
                errors.append(f"matrix.evidence_hashes[{path}] must be a SHA-256")

    contract_criteria = _records_by_id(contract.get("criteria"))
    contract_commands = _records_by_id(contract.get("commands"))
    contract_artifacts = _records_by_id(contract.get("artifacts"))
    matrix_criteria = matrix.get("criteria")
    if not isinstance(matrix_criteria, list):
        errors.append("matrix.criteria must be a list")
        matrix_criteria = []
    seen = set()
    results = []
    required_command_ids = set()
    required_artifact_ids = set()
    for index, item in enumerate(matrix_criteria):
        prefix = f"matrix.criteria[{index}]"
        if not isinstance(item, dict):
            errors.append(f"{prefix} must be an object")
            continue
        criterion_id = item.get("id")
        criterion = contract_criteria.get(criterion_id)
        if criterion is None:
            errors.append(f"{prefix}.id is not present in the contract")
        elif criterion_id in seen:
            errors.append(f"duplicate matrix criterion id: {criterion_id}")
        else:
            seen.add(criterion_id)
        result = item.get("result")
        if result not in CRITERION_RESULTS:
            errors.append(f"{prefix}.result is invalid")
            continue
        execution = item.get("execution")
        if execution not in EXECUTION_MODES:
            errors.append(f"{prefix}.execution must be EXECUTED or REUSED")
        reused_from = item.get("reused_from_round")
        if execution == "REUSED":
            if result != "PASS":
                errors.append(f"{prefix} REUSED evidence must remain PASS")
            if not _nonempty(reused_from):
                errors.append(f"{prefix}.reused_from_round must be set for REUSED evidence")
        elif reused_from is not None:
            errors.append(f"{prefix}.reused_from_round must be null for EXECUTED evidence")

        evidence = item.get("evidence")
        if not isinstance(evidence, list) or not all(_nonempty(entry) for entry in evidence):
            errors.append(f"{prefix}.evidence must be a string list")
            evidence = []
        owner = item.get("failure_owner")
        notes = item.get("notes")
        if result in {"PASS", "FAIL"} and not evidence:
            errors.append(f"{prefix} {result} requires raw evidence")
        for evidence_path in evidence:
            if evidence_path not in evidence_hashes:
                errors.append(f"{prefix}.evidence is missing a SHA-256 entry: {evidence_path}")
        if result == "FAIL" and owner not in FAILURE_OWNERS:
            errors.append(f"{prefix}.failure_owner is required for FAIL")
        if result != "FAIL" and owner is not None:
            errors.append(f"{prefix}.failure_owner must be null unless result is FAIL")
        if result == "NOT_OBSERVED" and not _nonempty(notes):
            errors.append(f"{prefix} NOT_OBSERVED requires notes")

        if criterion is not None:
            gate_result = _gate_satisfied(criterion.get("gate"), item.get("observed"))
            if result == "PASS" and gate_result is not True:
                errors.append(f"{prefix}.observed does not satisfy the frozen gate")
            if result == "FAIL" and owner == "product" and gate_result is not False:
                errors.append(f"{prefix}.observed does not demonstrate the product failure")
            if result in {"PASS", "FAIL"}:
                required_command_ids.update(criterion.get("command_ids", []))
            if result == "PASS" or (result == "FAIL" and owner in {"product", "harness"}):
                required_artifact_ids.update(criterion.get("artifact_ids", []))
        results.append((criterion_id, result, owner))

    if seen != set(contract_criteria):
        missing = sorted(set(contract_criteria) - seen)
        extra = sorted(seen - set(contract_criteria))
        if missing:
            errors.append("matrix is missing criteria: " + ", ".join(missing))
        if extra:
            errors.append("matrix has extra criteria: " + ", ".join(extra))

    required_ids = {
        criterion_id
        for criterion_id, criterion in contract_criteria.items()
        if criterion.get("required") is True
    }
    result_by_id = {criterion_id: result for criterion_id, result, _ in results}
    failures = [(result, owner) for _, result, owner in results if result == "FAIL"]
    if overall == "PASS":
        incomplete = sorted(
            criterion_id for criterion_id in required_ids if result_by_id.get(criterion_id) != "PASS"
        )
        if incomplete:
            errors.append("overall PASS requires every required criterion to PASS: " + ", ".join(incomplete))
    elif overall == "PRODUCT_FAIL" and not any(owner == "product" for _, owner in failures):
        errors.append("PRODUCT_FAIL requires a product-owned failure")
    elif overall == "HARNESS_FAIL" and not any(owner == "harness" for _, owner in failures):
        errors.append("HARNESS_FAIL requires a harness-owned failure")
    elif overall == "EVIDENCE_GAP":
        has_gap = any(
            result_by_id.get(criterion_id) == "NOT_OBSERVED" for criterion_id in required_ids
        ) or any(owner == "evidence" for _, owner in failures)
        if not has_gap:
            errors.append("EVIDENCE_GAP requires missing required evidence")
    elif overall == "ENV_BLOCKED" and not any(owner == "environment" for _, owner in failures):
        errors.append("ENV_BLOCKED requires an environment-owned failure")
    if overall in FINAL_RESULTS and contract.get("status") != "FROZEN" and not allow_draft:
        errors.append("a final matrix requires a FROZEN contract")

    has_reuse = any(
        isinstance(item, dict) and item.get("execution") == "REUSED"
        for item in matrix_criteria
    )
    previous_matrix_hash = matrix.get("previous_matrix_sha256")
    rerun_plan_path = matrix.get("rerun_plan_path")
    rerun_plan_hash = matrix.get("rerun_plan_sha256")
    if has_reuse:
        if not _is_sha256(previous_matrix_hash):
            errors.append("matrix.previous_matrix_sha256 must bind the previous matrix file")
        if not _is_bundle_relative(rerun_plan_path):
            errors.append("matrix.rerun_plan_path must stay inside the bundle")
        if not _is_sha256(rerun_plan_hash):
            errors.append("matrix.rerun_plan_sha256 must bind the rerun plan file")
    elif any(
        value is not None
        for value in (previous_matrix_hash, rerun_plan_path, rerun_plan_hash)
    ):
        errors.append("matrix rerun bindings must be null when no criterion is REUSED")

    commands = matrix.get("commands")
    if not isinstance(commands, list):
        errors.append("matrix.commands must be a list")
        commands = []
    command_ids = set()
    for index, command in enumerate(commands):
        prefix = f"matrix.commands[{index}]"
        if not isinstance(command, dict):
            errors.append(f"{prefix} must be an object")
            continue
        command_id = command.get("id")
        specification = contract_commands.get(command_id)
        if not _nonempty(command_id):
            errors.append(f"{prefix}.id must be set")
        elif command_id in command_ids:
            errors.append(f"duplicate command id: {command_id}")
        else:
            command_ids.add(command_id)
        if specification is None:
            errors.append(f"{prefix}.id is not present in the contract")
        if not _nonempty(command.get("command")):
            errors.append(f"{prefix}.command must be set")
        elif specification is not None and command.get("command") != specification.get("command"):
            errors.append(f"{prefix}.command does not match the frozen contract")
        exit_code = command.get("exit_code")
        if not isinstance(exit_code, int) or isinstance(exit_code, bool):
            errors.append(f"{prefix}.exit_code must be an integer")
        elif specification is not None and exit_code not in specification.get("expected_exit_codes", []):
            errors.append(f"{prefix}.exit_code is not an approved expected result")
        output = command.get("output_evidence")
        if specification is not None and specification.get("output_required") is True:
            if not _nonempty(output) or output not in evidence_hashes:
                errors.append(f"{prefix}.output_evidence must reference hashed evidence")
        elif output is not None and (not _nonempty(output) or output not in evidence_hashes):
            errors.append(f"{prefix}.output_evidence must reference hashed evidence")

    artifacts = matrix.get("artifacts")
    if not isinstance(artifacts, list):
        errors.append("matrix.artifacts must be a list")
        artifacts = []
    artifact_ids = set()
    for index, artifact in enumerate(artifacts):
        prefix = f"matrix.artifacts[{index}]"
        if not isinstance(artifact, dict):
            errors.append(f"{prefix} must be an object")
            continue
        artifact_id = artifact.get("id")
        if not _nonempty(artifact_id):
            errors.append(f"{prefix}.id must be set")
        elif artifact_id in artifact_ids:
            errors.append(f"duplicate artifact id: {artifact_id}")
        else:
            artifact_ids.add(artifact_id)
        if artifact_id not in contract_artifacts:
            errors.append(f"{prefix}.id is not present in the contract")
        if not _is_bundle_relative(artifact.get("path")):
            errors.append(f"{prefix}.path must stay inside the bundle")
        elif artifact_id in contract_artifacts and artifact.get("path") != contract_artifacts[artifact_id].get("path"):
            errors.append(f"{prefix}.path does not match the frozen contract")
        if not _is_sha256(artifact.get("sha256")):
            errors.append(f"{prefix}.sha256 must be a SHA-256")
        size = artifact.get("size")
        if not isinstance(size, int) or isinstance(size, bool) or size < 0:
            errors.append(f"{prefix}.size must be a non-negative integer")

    missing_commands = sorted(required_command_ids - command_ids)
    missing_artifacts = sorted(required_artifact_ids - artifact_ids)
    if missing_commands:
        errors.append(
            "executed PASS/FAIL criteria are missing required commands: "
            + ", ".join(missing_commands)
        )
    if missing_artifacts:
        errors.append(
            "PASS or product/harness FAIL criteria are missing required artifacts: "
            + ", ".join(missing_artifacts)
        )
    if overall == "PASS" and not commands:
        errors.append("overall PASS requires recorded commands")
    if overall == "PASS" and not artifacts:
        errors.append("overall PASS requires recorded artifacts")
    return errors


def _resolve_bundle_file(bundle_root, relative_path):
    candidate = (bundle_root / Path(relative_path.replace("\\", "/"))).absolute()
    candidate.relative_to(bundle_root)
    probe = candidate
    while probe != bundle_root:
        if _is_link_or_reparse(probe):
            raise ValueError(f"bundle path contains a link or reparse point: {relative_path}")
        probe = probe.parent
    path = candidate.resolve()
    path.relative_to(bundle_root)
    return path


def _resolve_bundle_output(bundle_root, output_value):
    output = Path(str(output_value).replace("\\", "/"))
    if not output.is_absolute():
        output = bundle_root / output
    output = output.absolute()
    try:
        relative = output.relative_to(bundle_root)
    except ValueError as exc:
        raise ValueError("rerun plan output must stay inside the bundle") from exc
    if not relative.parts:
        raise ValueError("rerun plan output must name a file inside the bundle")
    resolved = _resolve_bundle_file(bundle_root, relative.as_posix())
    if resolved.exists() and not resolved.is_file():
        raise ValueError("rerun plan output must not be an existing directory")
    return resolved


def validate_evidence_files(matrix, bundle_directory):
    errors = []
    evidence_hashes = matrix.get("evidence_hashes")
    if not isinstance(evidence_hashes, dict):
        return ["matrix.evidence_hashes must be an object"]
    bundle_root = Path(bundle_directory).resolve()
    for relative_path, expected_hash in evidence_hashes.items():
        if not _is_bundle_relative(relative_path) or not _is_sha256(expected_hash):
            continue
        try:
            evidence_path = _resolve_bundle_file(bundle_root, relative_path)
        except ValueError:
            errors.append(f"evidence path escapes the bundle: {relative_path}")
            continue
        if not evidence_path.is_file():
            errors.append(f"evidence file is missing: {relative_path}")
            continue
        actual_hash = hashlib.sha256(evidence_path.read_bytes()).hexdigest().upper()
        if actual_hash != expected_hash.upper():
            errors.append(f"evidence SHA-256 mismatch: {relative_path}")
    return errors


def validate_input_manifests(contract, bundle_directory, repo_root):
    errors = []
    input_groups = contract.get("input_groups")
    if not isinstance(input_groups, list):
        return ["contract.input_groups must be a list"]
    try:
        worktree_root = _resolve_git_worktree(repo_root)
    except ValueError as exc:
        return [f"repository root is invalid: {exc}"]
    bundle_root = Path(bundle_directory).resolve()
    for index, group in enumerate(input_groups):
        if not isinstance(group, dict):
            continue
        relative_path = group.get("manifest_path")
        expected_json_hash = group.get("manifest_json_sha256")
        expected_manifest_hash = group.get("manifest_sha256")
        if (
            not _is_bundle_relative(relative_path)
            or not _is_sha256(expected_json_hash)
            or not _is_sha256(expected_manifest_hash)
        ):
            continue
        try:
            manifest_path = _resolve_bundle_file(bundle_root, relative_path)
        except ValueError:
            errors.append(f"input manifest path escapes the bundle: {relative_path}")
            continue
        if not manifest_path.is_file():
            errors.append(f"input manifest file is missing: {relative_path}")
            continue
        data = manifest_path.read_bytes()
        actual_hash = hashlib.sha256(data).hexdigest().upper()
        if actual_hash != expected_json_hash.upper():
            errors.append(f"input manifest JSON SHA-256 mismatch: {relative_path}")
        try:
            manifest = json.loads(data.decode("utf-8"))
        except (UnicodeError, json.JSONDecodeError):
            errors.append(f"input manifest is not valid UTF-8 JSON: {relative_path}")
            continue
        if not isinstance(manifest, dict):
            errors.append(f"input manifest root must be an object: {relative_path}")
            continue
        expected_keys = {
            "Schema",
            "Profile",
            "Ordering",
            "Encoding",
            "FileCount",
            "ManifestSHA256",
            "Files",
        }
        if set(manifest) != expected_keys:
            errors.append(f"input manifest fields are invalid: {relative_path}")
        if manifest.get("Schema") != INPUT_MANIFEST_SCHEMA:
            errors.append(f"input manifest schema mismatch: {relative_path}")
        if manifest.get("Profile") != group.get("profile"):
            errors.append(f"input manifest profile mismatch: {relative_path}")
        if manifest.get("Ordering") != INPUT_MANIFEST_ORDERING:
            errors.append(f"input manifest ordering mismatch: {relative_path}")
        if manifest.get("Encoding") != INPUT_MANIFEST_ENCODING:
            errors.append(f"input manifest encoding mismatch: {relative_path}")

        files = manifest.get("Files")
        records_valid = isinstance(files, list) and bool(files)
        if not records_valid:
            errors.append(f"input manifest Files must be a non-empty list: {relative_path}")
            files = []
        file_count = manifest.get("FileCount")
        if (
            not isinstance(file_count, int)
            or isinstance(file_count, bool)
            or file_count < 1
            or file_count != len(files)
        ):
            errors.append(f"input manifest FileCount mismatch: {relative_path}")

        paths = []
        for record_index, record in enumerate(files):
            record_prefix = f"{relative_path}:Files[{record_index}]"
            if not isinstance(record, dict) or set(record) != {"Path", "Length", "SHA256"}:
                errors.append(f"input manifest file record is invalid: {record_prefix}")
                records_valid = False
                continue
            path = record.get("Path")
            length = record.get("Length")
            digest = record.get("SHA256")
            if not _is_repo_relative(path):
                errors.append(f"input manifest path is invalid: {record_prefix}")
                records_valid = False
            else:
                paths.append(path)
            if not isinstance(length, int) or isinstance(length, bool) or length < 0:
                errors.append(f"input manifest length is invalid: {record_prefix}")
                records_valid = False
            if not _is_sha256(digest):
                errors.append(f"input manifest SHA-256 is invalid: {record_prefix}")
                records_valid = False

        if paths != sorted(paths):
            errors.append(f"input manifest paths are not in ordinal order: {relative_path}")
            records_valid = False
        if len(paths) != len(set(paths)):
            errors.append(f"input manifest contains duplicate paths: {relative_path}")
            records_valid = False
        required_paths = PROFILE_REQUIRED_PATHS.get(group.get("profile"), set())
        missing_paths = sorted(required_paths - set(paths))
        if missing_paths:
            errors.append(
                f"input manifest is missing required {group.get('profile')} paths: "
                + ", ".join(missing_paths)
            )
            records_valid = False

        try:
            expected_records = _collect_profile_records(worktree_root, group.get("profile"))
        except ValueError as exc:
            errors.append(f"cannot rebuild {group.get('profile')} manifest: {exc}")
            expected_records = None
        if expected_records is not None:
            expected_by_path = {record["Path"]: record for record in expected_records}
            actual_by_path = {
                record.get("Path"): record
                for record in files
                if isinstance(record, dict) and _is_repo_relative(record.get("Path"))
            }
            missing_actual = sorted(set(expected_by_path) - set(actual_by_path))
            extra_actual = sorted(set(actual_by_path) - set(expected_by_path))
            if missing_actual:
                errors.append(
                    f"input manifest is missing worktree files for {group.get('profile')}: "
                    + ", ".join(missing_actual)
                )
            if extra_actual:
                errors.append(
                    f"input manifest contains files outside the {group.get('profile')} profile: "
                    + ", ".join(extra_actual)
                )
            for path in sorted(set(expected_by_path) & set(actual_by_path)):
                expected_record = expected_by_path[path]
                actual_record = actual_by_path[path]
                if actual_record.get("Length") != expected_record["Length"]:
                    errors.append(f"input manifest worktree length mismatch: {path}")
                actual_digest = actual_record.get("SHA256")
                if (
                    not isinstance(actual_digest, str)
                    or actual_digest.upper() != expected_record["SHA256"]
                ):
                    errors.append(f"input manifest worktree SHA-256 mismatch: {path}")

        internal_hash = manifest.get("ManifestSHA256")
        if not _is_sha256(internal_hash):
            errors.append(f"input manifest ManifestSHA256 is invalid: {relative_path}")
        elif internal_hash.upper() != expected_manifest_hash.upper():
            errors.append(f"input manifest stable SHA-256 mismatch: {relative_path}")

        if records_valid:
            text_bytes = _manifest_text_bytes(files)
            computed_hash = hashlib.sha256(text_bytes).hexdigest().upper()
            if not _is_sha256(internal_hash) or internal_hash.upper() != computed_hash:
                errors.append(f"input manifest internal SHA-256 mismatch: {relative_path}")
            text_path = manifest_path.with_name("source-manifest.txt")
            if not text_path.is_file():
                errors.append(f"input manifest text file is missing: {text_path.name}")
            elif text_path.read_bytes() != text_bytes:
                errors.append(f"input manifest text content mismatch: {relative_path}")
    return errors


def validate_external_inputs(contract, bundle_directory):
    errors = []
    bundle_root = Path(bundle_directory).resolve()
    for item in contract.get("external_inputs", []):
        if not isinstance(item, dict):
            continue
        relative_path = item.get("evidence_path")
        expected_hash = item.get("evidence_sha256")
        if not _is_bundle_relative(relative_path) or not _is_sha256(expected_hash):
            continue
        try:
            evidence_path = _resolve_bundle_file(bundle_root, relative_path)
        except ValueError:
            errors.append(f"external input evidence escapes the bundle: {relative_path}")
            continue
        if not evidence_path.is_file():
            errors.append(f"external input evidence is missing: {relative_path}")
            continue
        actual_hash = hashlib.sha256(evidence_path.read_bytes()).hexdigest().upper()
        if actual_hash != expected_hash.upper():
            errors.append(f"external input evidence SHA-256 mismatch: {relative_path}")
    return errors


def validate_artifact_files(matrix, bundle_directory):
    errors = []
    bundle_root = Path(bundle_directory).resolve()
    for artifact in matrix.get("artifacts", []):
        if not isinstance(artifact, dict):
            continue
        relative_path = artifact.get("path")
        expected_hash = artifact.get("sha256")
        expected_size = artifact.get("size")
        if not _is_bundle_relative(relative_path) or not _is_sha256(expected_hash):
            continue
        try:
            artifact_path = _resolve_bundle_file(bundle_root, relative_path)
        except ValueError:
            errors.append(f"artifact path escapes the bundle: {relative_path}")
            continue
        if not artifact_path.is_file():
            errors.append(f"artifact file is missing: {relative_path}")
            continue
        actual_size = artifact_path.stat().st_size
        if actual_size != expected_size:
            errors.append(f"artifact size mismatch: {relative_path}")
        actual_hash = hashlib.sha256(artifact_path.read_bytes()).hexdigest().upper()
        if actual_hash != expected_hash.upper():
            errors.append(f"artifact SHA-256 mismatch: {relative_path}")
    return errors


def validate_contract_lineage(
    current_contract,
    previous_contract,
    current_contract_sha256=None,
    previous_contract_sha256=None,
):
    errors = []
    current_hash = (current_contract_sha256 or _json_sha256(current_contract)).upper()
    previous_hash = (previous_contract_sha256 or _json_sha256(previous_contract)).upper()
    same_contract = (
        current_hash == previous_hash
        and _canonical(current_contract) == _canonical(previous_contract)
    )
    if same_contract:
        return errors
    if current_hash == previous_hash:
        return ["contract lineage hashes collide for different contract content"]
    if current_contract.get("task_id") != previous_contract.get("task_id"):
        errors.append("contract lineage task_id does not match the previous contract")
    current_version = current_contract.get("version")
    previous_version = previous_contract.get("version")
    if (
        not isinstance(current_version, int)
        or isinstance(current_version, bool)
        or not isinstance(previous_version, int)
        or isinstance(previous_version, bool)
        or current_version != previous_version + 1
    ):
        errors.append("contract lineage requires the next contract version")
    parent_hash = current_contract.get("parent_contract_sha256")
    if not isinstance(parent_hash, str) or parent_hash.upper() != previous_hash:
        errors.append("contract.parent_contract_sha256 does not bind the previous contract file")
    if current_contract.get("contract_id") == previous_contract.get("contract_id"):
        errors.append("a successor contract must use a new contract_id")
    return errors


def validate_matrix_lineage(
    current_matrix,
    previous_matrix,
    current_matrix_sha256=None,
    previous_matrix_sha256=None,
):
    errors = []
    current_hash = (current_matrix_sha256 or _json_sha256(current_matrix)).upper()
    previous_hash = (previous_matrix_sha256 or _json_sha256(previous_matrix)).upper()
    if current_hash == previous_hash:
        errors.append("current and previous matrix files must be different")
    current_round = current_matrix.get("round_id")
    previous_round = previous_matrix.get("round_id")
    if _nonempty(current_round) and current_round == previous_round:
        errors.append("current and previous matrix round_id must be different")
    return errors


def compute_rerun_plan(
    current_contract,
    previous_contract,
    previous_matrix,
    current_contract_sha256=None,
    previous_contract_sha256=None,
    previous_matrix_sha256=None,
    current_round_id=None,
):
    current_hash = current_contract_sha256 or _json_sha256(current_contract)
    previous_hash = previous_contract_sha256 or _json_sha256(previous_contract)
    lineage_errors = validate_contract_lineage(
        current_contract,
        previous_contract,
        current_contract_sha256=current_hash,
        previous_contract_sha256=previous_hash,
    )
    if lineage_errors:
        raise ValueError("invalid contract lineage: " + "; ".join(lineage_errors))
    current_groups = _records_by_id(current_contract.get("input_groups"))
    previous_groups = _records_by_id(previous_contract.get("input_groups"))
    changed_groups = sorted(
        group_id
        for group_id in set(current_groups) | set(previous_groups)
        if _canonical(_input_group_signature(current_groups.get(group_id)))
        != _canonical(_input_group_signature(previous_groups.get(group_id)))
    )
    current_external = _records_by_id(current_contract.get("external_inputs"))
    previous_external = _records_by_id(previous_contract.get("external_inputs"))
    changed_external = sorted(
        item_id
        for item_id in set(current_external) | set(previous_external)
        if _canonical(_external_input_signature(current_external.get(item_id)))
        != _canonical(_external_input_signature(previous_external.get(item_id)))
    )
    current_criteria = _records_by_id(current_contract.get("criteria"))
    previous_criteria = _records_by_id(previous_contract.get("criteria"))
    current_commands = _records_by_id(current_contract.get("commands"))
    previous_commands = _records_by_id(previous_contract.get("commands"))
    current_artifacts = _records_by_id(current_contract.get("artifacts"))
    previous_artifacts = _records_by_id(previous_contract.get("artifacts"))
    previous_results = _records_by_id(previous_matrix.get("criteria"))

    rerun = []
    reusable = []
    for criterion_id, criterion in current_criteria.items():
        reasons = []
        previous_criterion = previous_criteria.get(criterion_id)
        previous_result = previous_results.get(criterion_id)
        if previous_criterion is None:
            reasons.append("new_criterion")
        elif _canonical(criterion) != _canonical(previous_criterion):
            reasons.append("criterion_definition_changed")
        if previous_result is None or previous_result.get("result") != "PASS":
            reasons.append("previous_result_not_pass")
        elif previous_result.get("execution") != "EXECUTED":
            reasons.append("previous_result_not_executed")
        for group_id in criterion.get("input_groups", []):
            if group_id in changed_groups:
                reasons.append(f"input_group_changed:{group_id}")
        for item_id in criterion.get("external_inputs", []):
            if item_id in changed_external:
                reasons.append(f"external_input_changed:{item_id}")
        for command_id in criterion.get("command_ids", []):
            if _canonical(current_commands.get(command_id)) != _canonical(previous_commands.get(command_id)):
                reasons.append(f"command_definition_changed:{command_id}")
        for artifact_id in criterion.get("artifact_ids", []):
            if _canonical(current_artifacts.get(artifact_id)) != _canonical(previous_artifacts.get(artifact_id)):
                reasons.append(f"artifact_definition_changed:{artifact_id}")
        reasons = sorted(set(reasons))
        if reasons:
            rerun.append({"id": criterion_id, "reasons": reasons})
        else:
            reusable.append(criterion_id)

    rerun_ids = {item["id"] for item in rerun}
    required_commands = sorted(
        {
            command_id
            for criterion_id in rerun_ids
            for command_id in current_criteria[criterion_id].get("command_ids", [])
        }
    )
    required_artifacts = sorted(
        {
            artifact_id
            for criterion_id in rerun_ids
            for artifact_id in current_criteria[criterion_id].get("artifact_ids", [])
        }
    )
    return {
        "schema": RERUN_SCHEMA,
        "current_contract_id": current_contract.get("contract_id"),
        "current_contract_sha256": current_hash,
        "previous_contract_id": previous_contract.get("contract_id"),
        "previous_contract_sha256": previous_hash,
        "contract_lineage": "same_contract" if current_hash == previous_hash else "direct_successor",
        "current_round_id": current_round_id,
        "previous_round_id": previous_matrix.get("round_id"),
        "previous_matrix_sha256": (
            previous_matrix_sha256 or _json_sha256(previous_matrix)
        ).upper(),
        "changed_input_groups": changed_groups,
        "changed_external_inputs": changed_external,
        "rerun_criteria": rerun,
        "reusable_criteria": sorted(reusable),
        "required_commands": required_commands,
        "required_artifacts": required_artifacts,
    }


def _evidence_digests(matrix, criterion):
    hashes = matrix.get("evidence_hashes", {})
    return sorted(hashes.get(path, "").upper() for path in criterion.get("evidence", []))


def _command_signature(matrix, command_id):
    record = _records_by_id(matrix.get("commands")).get(command_id)
    if record is None:
        return None
    output = record.get("output_evidence")
    output_hash = matrix.get("evidence_hashes", {}).get(output, "") if output else ""
    return (record.get("command"), record.get("exit_code"), output_hash.upper())


def _artifact_signature(matrix, artifact_id):
    record = _records_by_id(matrix.get("artifacts")).get(artifact_id)
    if record is None:
        return None
    return (record.get("sha256", "").upper(), record.get("size"))


def validate_reuse(current_matrix, current_contract, previous_matrix, rerun_plan):
    errors = []
    previous_criteria = _records_by_id(previous_matrix.get("criteria"))
    contract_criteria = _records_by_id(current_contract.get("criteria"))
    rerun_ids = {item["id"] for item in rerun_plan.get("rerun_criteria", [])}
    reusable_ids = set(rerun_plan.get("reusable_criteria", []))
    previous_round = previous_matrix.get("round_id")
    for index, criterion in enumerate(current_matrix.get("criteria", [])):
        if not isinstance(criterion, dict):
            continue
        criterion_id = criterion.get("id")
        execution = criterion.get("execution")
        if execution == "REUSED" and criterion_id in rerun_ids:
            errors.append(f"matrix.criteria[{index}] reuses invalidated evidence")
            continue
        if execution != "REUSED":
            continue
        if criterion_id not in reusable_ids:
            errors.append(f"matrix.criteria[{index}] is not reusable according to the rerun plan")
            continue
        previous = previous_criteria.get(criterion_id)
        if previous is None or previous.get("result") != "PASS":
            errors.append(f"matrix.criteria[{index}] has no previous PASS to reuse")
            continue
        if previous.get("execution") != "EXECUTED":
            errors.append(f"matrix.criteria[{index}] cannot reuse a previously REUSED result")
            continue
        if criterion.get("reused_from_round") != previous_round:
            errors.append(f"matrix.criteria[{index}].reused_from_round does not match the baseline")
        if criterion.get("result") != previous.get("result"):
            errors.append(f"matrix.criteria[{index}] result differs from reused evidence")
        if criterion.get("observed") != previous.get("observed"):
            errors.append(f"matrix.criteria[{index}] observed value differs from reused evidence")
        if _evidence_digests(current_matrix, criterion) != _evidence_digests(previous_matrix, previous):
            errors.append(f"matrix.criteria[{index}] evidence hashes differ from the baseline")
        specification = contract_criteria.get(criterion_id, {})
        for command_id in specification.get("command_ids", []):
            if _command_signature(current_matrix, command_id) != _command_signature(previous_matrix, command_id):
                errors.append(f"matrix.criteria[{index}] command {command_id} differs from the baseline")
        for artifact_id in specification.get("artifact_ids", []):
            if _artifact_signature(current_matrix, artifact_id) != _artifact_signature(previous_matrix, artifact_id):
                errors.append(f"matrix.criteria[{index}] artifact {artifact_id} differs from the baseline")
    return errors


def _rerun_plan_bytes(rerun_plan):
    return (json.dumps(rerun_plan, indent=2, ensure_ascii=True) + "\n").encode("utf-8")


def validate_rerun_plan_file(
    matrix,
    bundle_directory,
    rerun_plan,
    previous_matrix_sha256,
):
    has_reuse = any(
        isinstance(item, dict) and item.get("execution") == "REUSED"
        for item in matrix.get("criteria", [])
    )
    if not has_reuse:
        return []
    errors = []
    bound_previous_hash = matrix.get("previous_matrix_sha256")
    if (
        _is_sha256(bound_previous_hash)
        and bound_previous_hash.upper() != previous_matrix_sha256.upper()
    ):
        errors.append("matrix.previous_matrix_sha256 does not match the previous matrix file")
    relative_path = matrix.get("rerun_plan_path")
    expected_hash = matrix.get("rerun_plan_sha256")
    if not _is_bundle_relative(relative_path) or not _is_sha256(expected_hash):
        return errors
    bundle_root = Path(bundle_directory).resolve()
    try:
        plan_path = _resolve_bundle_file(bundle_root, relative_path)
    except ValueError:
        errors.append(f"rerun plan path escapes the bundle: {relative_path}")
        return errors
    if _is_link_or_reparse(plan_path):
        errors.append(f"rerun plan file must not be a link or reparse point: {relative_path}")
        return errors
    if not plan_path.is_file():
        errors.append(f"rerun plan file is missing: {relative_path}")
        return errors
    data = plan_path.read_bytes()
    actual_hash = hashlib.sha256(data).hexdigest().upper()
    if actual_hash != expected_hash.upper():
        errors.append(f"rerun plan SHA-256 mismatch: {relative_path}")
    try:
        stored_plan = json.loads(data.decode("utf-8"))
    except (UnicodeError, json.JSONDecodeError):
        errors.append(f"rerun plan is not valid UTF-8 JSON: {relative_path}")
        return errors
    if _canonical(stored_plan) != _canonical(rerun_plan):
        errors.append("rerun plan content does not match the computed invalidation plan")
    return errors


def load_json(path):
    return json.loads(Path(path).read_text(encoding="utf-8"))


def _load_bundle(contract_path, matrix_path):
    contract_bytes = Path(contract_path).read_bytes()
    matrix_bytes = Path(matrix_path).read_bytes()
    contract = json.loads(contract_bytes.decode("utf-8"))
    matrix = json.loads(matrix_bytes.decode("utf-8"))
    contract_hash = hashlib.sha256(contract_bytes).hexdigest().upper()
    matrix_hash = hashlib.sha256(matrix_bytes).hexdigest().upper()
    return contract, matrix, contract_hash, matrix_hash


def _physical_errors(contract, matrix, bundle_directory, repo_root):
    errors = []
    errors.extend(validate_input_manifests(contract, bundle_directory, repo_root))
    errors.extend(validate_external_inputs(contract, bundle_directory))
    errors.extend(validate_evidence_files(matrix, bundle_directory))
    errors.extend(validate_artifact_files(matrix, bundle_directory))
    return errors


def main(argv=None):
    parser = argparse.ArgumentParser(description="Validate an E-Track acceptance bundle.")
    parser.add_argument("--contract", required=True)
    parser.add_argument("--matrix", required=True)
    parser.add_argument("--repo-root", required=True)
    parser.add_argument("--allow-draft", action="store_true")
    parser.add_argument("--previous-contract")
    parser.add_argument("--previous-matrix")
    parser.add_argument("--previous-repo-root")
    parser.add_argument(
        "--write-rerun-plan",
        help="Write a computed plan inside the current matrix bundle.",
    )
    args = parser.parse_args(argv)

    contract_path = Path(args.contract)
    matrix_path = Path(args.matrix)
    try:
        contract, matrix, contract_hash, matrix_hash = _load_bundle(contract_path, matrix_path)
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        print(f"VALIDATION=FAIL: {exc}", file=sys.stderr)
        return 2

    errors = validate_contract(contract, allow_draft=args.allow_draft)
    errors.extend(validate_matrix(matrix, contract, contract_hash, allow_draft=args.allow_draft))
    needs_physical = matrix.get("overall_result") in FINAL_RESULTS or args.write_rerun_plan
    if needs_physical:
        errors.extend(_physical_errors(contract, matrix, matrix_path.parent, args.repo_root))

    previous_contract = None
    previous_matrix = None
    previous_hash = None
    previous_matrix_hash = None
    rerun_plan = None
    previous_pair = any(
        (args.previous_contract, args.previous_matrix, args.previous_repo_root)
    )
    if previous_pair and not all(
        (args.previous_contract, args.previous_matrix, args.previous_repo_root)
    ):
        errors.append(
            "previous contract, matrix, and repository root must be supplied together"
        )
    elif args.previous_contract and args.previous_matrix and args.previous_repo_root:
        try:
            (
                previous_contract,
                previous_matrix,
                previous_hash,
                previous_matrix_hash,
            ) = _load_bundle(
                args.previous_contract, args.previous_matrix
            )
        except (OSError, UnicodeError, json.JSONDecodeError) as exc:
            errors.append(f"previous bundle cannot be loaded: {exc}")
        if previous_contract is not None:
            previous_errors = validate_contract(previous_contract)
            previous_errors.extend(
                validate_matrix(previous_matrix, previous_contract, previous_hash)
            )
            previous_errors.extend(
                _physical_errors(
                    previous_contract,
                    previous_matrix,
                    Path(args.previous_matrix).parent,
                    args.previous_repo_root,
                )
            )
            errors.extend(f"previous: {error}" for error in previous_errors)
            if not previous_errors:
                lineage_errors = validate_contract_lineage(
                    contract,
                    previous_contract,
                    current_contract_sha256=contract_hash,
                    previous_contract_sha256=previous_hash,
                )
                lineage_errors.extend(
                    validate_matrix_lineage(
                        matrix,
                        previous_matrix,
                        current_matrix_sha256=matrix_hash,
                        previous_matrix_sha256=previous_matrix_hash,
                    )
                )
                errors.extend(lineage_errors)
                if not lineage_errors:
                    rerun_plan = compute_rerun_plan(
                        contract,
                        previous_contract,
                        previous_matrix,
                        current_contract_sha256=contract_hash,
                        previous_contract_sha256=previous_hash,
                        previous_matrix_sha256=previous_matrix_hash,
                        current_round_id=matrix.get("round_id"),
                    )
                    errors.extend(validate_reuse(matrix, contract, previous_matrix, rerun_plan))
                    errors.extend(
                        validate_rerun_plan_file(
                            matrix,
                            matrix_path.parent,
                            rerun_plan,
                            previous_matrix_hash,
                        )
                    )

    has_reuse = any(
        isinstance(item, dict) and item.get("execution") == "REUSED"
        for item in matrix.get("criteria", [])
    )
    if has_reuse and rerun_plan is None:
        errors.append("REUSED evidence requires a valid previous contract and matrix")
    if args.write_rerun_plan and rerun_plan is None:
        errors.append("--write-rerun-plan requires a valid previous contract and matrix")

    if errors:
        for error in errors:
            print(f"ERROR: {error}", file=sys.stderr)
        print(f"VALIDATION=FAIL errors={len(errors)}", file=sys.stderr)
        return 1

    if args.write_rerun_plan:
        bundle_root = matrix_path.parent.resolve()
        try:
            output = _resolve_bundle_output(bundle_root, args.write_rerun_plan)
        except ValueError as exc:
            print(f"VALIDATION=FAIL: {exc}", file=sys.stderr)
            return 1
        try:
            output.parent.mkdir(parents=True, exist_ok=True)
            output = _resolve_bundle_output(bundle_root, output)
            output.write_bytes(_rerun_plan_bytes(rerun_plan))
        except (OSError, ValueError) as exc:
            print(f"VALIDATION=FAIL: cannot write rerun plan safely: {exc}", file=sys.stderr)
            return 1
        print(
            f"RERUN_PLAN={output} rerun={len(rerun_plan['rerun_criteria'])} "
            f"reusable={len(rerun_plan['reusable_criteria'])}"
        )

    print(
        f"VALIDATION=PASS contract={contract.get('contract_id')} "
        f"round={matrix.get('round_id')} overall={matrix.get('overall_result')}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
