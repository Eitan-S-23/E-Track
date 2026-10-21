"""Evaluate existing P4-4 originals offline, without repeating their operations.

Input schema: p44-originals-v1. source_commit and candidate_commit bind history;
history.inventory and configuration.inventory are {path, size_bytes, sha256}.
Configuration CLI evaluation also requires deployment.inventory in that shape.
References stay below the manifest directory; inventory members stay below their
inventory directory. Private original paths are provenance labels, never inputs.
"""

from __future__ import annotations

import argparse
from collections import Counter
from datetime import datetime, timezone
from email import policy as email_policy
from email.parser import BytesParser
import hashlib
import importlib.util
import io
import json
import os
from pathlib import Path, PurePosixPath
import posixpath
import re
import stat
import subprocess
import sys
import zipfile

sys.dont_write_bytecode = True

SOURCE_COMMIT = "b56534d7b6c993c0795010d0404fb8a81f7eeb9d"
REPOSITORY = "Eitan-S-23/E-Track"
ORIGINAL_WORKTREE = "D:/github/my/E-Track/.cache/p4-4-integration-20261018"
PROJECT = "D:/github/my/E-Track"
PROFILE_PATH = "Tools/provenance/manifest_profiles.json"
SOURCE_ID = "ec3e3b40801a2af2676d699686429cc49d1fea95afb328d8efb9ac519b31d666"
OLD_SOURCE_ID = "0c22488a9bee1355603d8d61faca06fcacbdafccfed8a4ba7dc490af7cacdedc"
GROUPS = {
    "6a018a9f2fc74eb6b293b0c548f38b39": "Workers R2 Storage Bucket Item Read",
    "2efd5506f9c8494dacb1fa10a3e7d5b6": "Workers R2 Storage Bucket Item Write",
}
TOKENS = {
    "production": {
        "name": "e-track-firmware-production-s3-ci-20261019",
        "bucket": "e-track-firmware-production-releases",
        "id_sha256": "eb673c4ae5e4fe5a023669fb1a945c1f366dc7b0c04aaa5638abb11238e7fd49",
        "issued_on": "2026-10-19T07:40:38Z",
    },
    "rehearsal": {
        "name": "e-track-firmware-rehearsal-s3-ci-20261019",
        "bucket": "e-track-firmware-p41-test-releases",
        "id_sha256": "e96e395a2e6866581f0c4aa1b46579026683ea9f4fbfab48b9b2f8b45a22a508",
        "issued_on": "2026-10-19T07:40:50Z",
    },
}
BUILD = "Build firmware (arm-none-eabi-gcc)"
DEVELOPMENT = "Release tooling development checks (no cloud credentials)"
SKIPPED_JOBS = {
    "Isolated firmware binding qualification (not rehearsal)",
    "Firmware production (shared release implementation)",
    "Firmware rehearsal (shared release implementation)",
}
SKIPPED_STEPS = {
    BUILD: {"Build the P3-4 acceptance candidate", "Preserve the P3-4 candidate build evidence"},
    "Flutter debugging skill (ubuntu-latest)": {
        "Test host helpers (Windows)", "Test P3-4 controlled service and live adapters (Windows)"},
    "Flutter debugging skill (windows-latest)": {
        "Test host helpers (Linux)", "Test P3-4 controlled service and live adapters (Linux)"},
}
HISTORY_LABELS = (
    "checks-dispatch-01", "ci-full-log-01", "ci-full-log-02", "ci-state-01",
    "ci-state-02", "governance-dispatch-01", "governance-full-log-01",
    "governance-host-01", "governance-state-01", "npm-audit-01",
    "pipeline-host-01", "pr-context-01", "sdk-01", "source-commit-01",
    "source-push-01", "stage-01", "types-01", "workflow-01",
)
HISTORY_FILES = {
    "remediation-" + label + suffix for label in HISTORY_LABELS for suffix in (".json", ".log")
} | {"remediation-delivery-01.json", "remediation-precommit-01.json"}
CONFIGURATION_FILES = {
    "create-s3-02.json", "verify-perm-01.json", "create_s3_02.py", "agent-handoff.md",
    "credential-readback-01.json", "credential-readback.cjs",
    "credential-protection-01.json", "protect-credential-inputs.cjs",
}
DEPLOYMENT_FILES = {
    "preparation/worker-input-01.json", "preparation/worker-input-02.json",
    "preparation/worker-input-01.zip",
    "preparation/deploy/staging/redaction-recovery-02.json",
    "preparation/curl-recover-staging-02/02.body",
    "preparation/curl-recover-staging-02/04.body",
    "preparation/curl-recover-staging-02/06.body",
    "preparation/curl-recover-staging-02/06.headers",
    "preparation/deploy/production/deploy-04.json",
    "preparation/curl-deploy-production-04/08.body",
    "preparation/curl-deploy-production-04/09.body",
    "preparation/curl-deploy-production-04/11.body",
    "preparation/curl-deploy-production-04/11.headers",
    "preparation/deploy/staging/deploy.json",
    "preparation/deploy/staging/redaction-recovery.json",
    "preparation/deploy/production/deploy-03.json",
}
WORKER_ZIP_SHA256 = "7bee78195841780046c3333d4dc6c0b3ec9d442f8a99399051d204844a7e2f6f"
WORKER_MODULE_SHA256 = "1ad919d795a2354cd4c7d9617f3e3c9805f831967d1a2cdd5930ba61e4c3303f"
DEPLOYMENTS = {
    "staging": {
        "worker": "e-track-firmware-p41-test", "database": "2617e1e1-956f-42ce-a465-da56d84abf06",
        "bucket": "e-track-firmware-p41-test-releases", "environment": "staging",
        "deployment": "88983ae0-75b1-487b-af0d-788b6cf976ec", "version": "bb3d44fd-4a84-489e-9e04-6adfc54a458e",
        "receipt": "preparation/deploy/staging/redaction-recovery-02.json",
        "prefix": "preparation/curl-recover-staging-02/", "deployment_ordinal": 2,
        "settings_ordinal": 4, "content_ordinal": 6,
    },
    "production": {
        "worker": "e-track-firmware-production", "database": "1cd5db26-6bbd-4595-abef-72ff51ecdaf3",
        "bucket": "e-track-firmware-production-releases", "environment": "prod",
        "deployment": "b76395f1-f2bf-4adb-b936-0a291edf6e45", "version": "e1653d60-03cb-4397-b154-78efd681ebbc",
        "receipt": "preparation/deploy/production/deploy-04.json",
        "prefix": "preparation/curl-deploy-production-04/", "deployment_ordinal": 9,
        "settings_ordinal": 8, "content_ordinal": 11,
    },
}
COLLECTOR_HASHES = {
    "create_s3_02.py": "c7757d1788d43f3c4838933eefc3c6dee03f55a80b932f4fcc70ee501950ec2d",
    "credential-readback.cjs": "59bce0fb6b8bd68b1cd4a4d29261e658141c0103fe9b9676f0a0cf6374706c32",
    "protect-credential-inputs.cjs": "26564647d88012764181a5695d8c233d52bdfd0d6e04cba0054044cbc6aea165",
}
HASH = re.compile(r"[0-9a-f]{64}\Z")
OID = re.compile(r"[0-9a-f]{40}\Z")
ANSI = re.compile(r"(?:\x1b|\^\[)\[[0-?]*[ -/]*[@-~]")
MAX_FILE = 16 * 1024 * 1024


class EvidenceError(ValueError):
    """Only fixed codes, never evidence text or paths, leave the evaluator."""


class SafeArgumentParser(argparse.ArgumentParser):
    def error(self, message):
        print(json.dumps({"ok": False, "error_code": "INVALID_ARGUMENTS", "output_written": False}))
        raise SystemExit(2)


def require(condition, code):
    if not condition:
        raise EvidenceError(code)


def sha256(data):
    return hashlib.sha256(data).hexdigest()


def integer(value, minimum=0):
    return type(value) is int and value >= minimum


def json_bytes(data):
    def unique(pairs):
        result = {}
        for key, value in pairs:
            require(key not in result, "DUPLICATE_JSON_KEY")
            result[key] = value
        return result

    def constant(_):
        raise EvidenceError("INVALID_JSON_NUMBER")

    try:
        return json.loads(data, object_pairs_hook=unique, parse_constant=constant)
    except (UnicodeError, json.JSONDecodeError):
        raise EvidenceError("INVALID_JSON") from None


def timestamp(value):
    require(isinstance(value, str), "INVALID_TIMESTAMP")
    try:
        result = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        raise EvidenceError("INVALID_TIMESTAMP") from None
    require(result.tzinfo is not None, "INVALID_TIMESTAMP")
    return result.astimezone(timezone.utc)


def guarded_path(root, value):
    root = Path(os.path.abspath(root))
    path = Path(value)
    path = Path(os.path.abspath(path if path.is_absolute() else root / path))
    try:
        path.relative_to(root)
    except ValueError:
        raise EvidenceError("PATH_OUTSIDE_BOUNDARY") from None
    for part in reversed((path, *path.parents)):
        try:
            info = part.lstat()
        except FileNotFoundError:
            continue
        require(not stat.S_ISLNK(info.st_mode)
                and not (getattr(info, "st_file_attributes", 0) & stat.FILE_ATTRIBUTE_REPARSE_POINT),
                "REPARSE_PATH_REJECTED")
    try:
        path.resolve().relative_to(root.resolve())
    except ValueError:
        raise EvidenceError("PATH_OUTSIDE_BOUNDARY") from None
    return path


def relative(value):
    require(isinstance(value, str) and value and "\\" not in value and ":" not in value
            and "\x00" not in value and not value.startswith("/"), "INVALID_RELATIVE_PATH")
    require(all(part not in {"", ".", ".."} for part in value.split("/")), "INVALID_RELATIVE_PATH")
    return PurePosixPath(value)


class Context:
    def __init__(self, root, manifest):
        self.root = guarded_path(root, root)
        self.manifest = guarded_path(self.root, manifest)
        self.base = self.manifest.parent
        self.checked = {}

    def read(self, reference, base=None):
        require(isinstance(reference, dict) and set(reference) == {"path", "size_bytes", "sha256"},
                "INVALID_FILE_REFERENCE")
        name = relative(reference["path"])
        require(integer(reference["size_bytes"]) and reference["size_bytes"] <= MAX_FILE,
                "FILE_SIZE_BOUND")
        require(isinstance(reference["sha256"], str) and HASH.fullmatch(reference["sha256"]),
                "INVALID_FILE_DIGEST")
        directory = guarded_path(self.base, base or self.base)
        path = guarded_path(directory, directory / name)
        require(path.is_file() and path.stat().st_size == reference["size_bytes"], "FILE_SIZE_MISMATCH")
        data = path.read_bytes()
        require(len(data) == reference["size_bytes"] and sha256(data) == reference["sha256"],
                "FILE_DIGEST_MISMATCH")
        self.checked[path.relative_to(self.base).as_posix()] = reference["sha256"]
        return data

    def inventory(self, reference, mode):
        document = json_bytes(self.read(reference))
        require(isinstance(document, dict), "INVENTORY_INVALID")
        if mode == "configuration":
            require(document.get("schema") == "p44-credential-handoff-inventory-v1", "INVENTORY_SCHEMA")
        rows = document.get("files")
        expected = HISTORY_FILES if mode == "history" else CONFIGURATION_FILES
        require(isinstance(rows, list) and len(rows) == len(expected)
                and all(isinstance(row, dict) and isinstance(row.get("path"), str) for row in rows)
                and {row["path"] for row in rows} == expected, "INVENTORY_INCOMPLETE")
        base = self.base / relative(reference["path"]).parent
        files = {}
        for row in rows:
            key = "sizeBytes" if mode == "history" else "size_bytes"
            data = self.read({"path": row["path"], "size_bytes": row.get(key), "sha256": row.get("sha256")}, base)
            if mode == "configuration":
                require(type(row.get("projection")) is bool
                        and integer(row.get("original_size_bytes"))
                        and isinstance(row.get("original_sha256"), str)
                        and HASH.fullmatch(row["original_sha256"]), "PROJECTION_IDENTITY_MISSING")
                if not row["projection"]:
                    require(row["original_sha256"] == sha256(data)
                            and row["original_size_bytes"] == len(data), "ORIGINAL_IDENTITY_MISMATCH")
                if row["path"] in COLLECTOR_HASHES:
                    require(sha256(data) == COLLECTOR_HASHES[row["path"]], "HISTORICAL_COLLECTOR_CHANGED")
            files[row["path"]] = data
        return document, files

    def deployment_inventory(self, reference):
        document = json_bytes(self.read(reference))
        rows = document.get("entries")
        require(document.get("sourceCommit") == SOURCE_COMMIT and isinstance(rows, list)
                and all(isinstance(row, dict) and isinstance(row.get("path"), str) for row in rows)
                and len({row["path"] for row in rows}) == len(rows), "DEPLOYMENT_INVENTORY_INVALID")
        selected = {row["path"]: row for row in rows if row["path"] in DEPLOYMENT_FILES}
        require(set(selected) == DEPLOYMENT_FILES, "DEPLOYMENT_INVENTORY_INCOMPLETE")
        base = self.base / relative(reference["path"]).parent
        files = {}
        for name, row in selected.items():
            data = self.read({"path": name, "size_bytes": row.get("sizeBytes"), "sha256": row.get("sha256")}, base)
            require(integer(row.get("originalSizeBytes")) and isinstance(row.get("originalSha256"), str)
                    and HASH.fullmatch(row["originalSha256"]) and type(row.get("byteExact")) is bool
                    and isinstance(row.get("transformations"), list), "DEPLOYMENT_PROJECTION_IDENTITY")
            transformations = row["transformations"]
            require(all(isinstance(item, dict) and set(item) == {"kind", "count"}
                        and item["kind"] in {"email-address", "set-cookie-header"}
                        and integer(item["count"], 1) for item in transformations), "DEPLOYMENT_PROJECTION_TRANSFORM")
            if row["byteExact"]:
                require(not transformations and row["originalSizeBytes"] == len(data)
                        and row["originalSha256"] == sha256(data), "DEPLOYMENT_BYTE_EXACT_MISMATCH")
            else:
                require(transformations and row["originalSha256"] != sha256(data), "DEPLOYMENT_PROJECTION_TRANSFORM")
            require(row.get("source") == ".cache/p44-root-acceptance-20261019/" + name.removeprefix("preparation/"),
                    "DEPLOYMENT_ORIGIN_MISMATCH")
            files[name] = data
        return selected, files


def git(root, *args):
    environment = {key: value for key, value in os.environ.items() if not key.upper().startswith("GIT_TRACE")}
    environment.update(GIT_OPTIONAL_LOCKS="0", GIT_NO_LAZY_FETCH="1", GIT_TERMINAL_PROMPT="0")
    result = subprocess.run(["git", "-C", str(root), "-c", "core.quotepath=false", *args],
                            cwd=root, env=environment, capture_output=True, timeout=30, check=False)
    require(result.returncode == 0, "GIT_INPUT_CHECK_FAILED")
    return result.stdout


def input_applicability(root, manifest):
    require(manifest.get("source_commit") == SOURCE_COMMIT, "HISTORY_SOURCE_MISMATCH")
    candidate = manifest.get("candidate_commit")
    require(isinstance(candidate, str) and OID.fullmatch(candidate), "CANDIDATE_COMMIT_INVALID")
    git(root, "merge-base", "--is-ancestor", SOURCE_COMMIT, candidate)
    git(root, "merge-base", "--is-ancestor", candidate, "HEAD")
    entry = guarded_path(root, "Tools/acceptance/validate_bundle.py")
    guarded_path(root, PROFILE_PATH)
    spec = importlib.util.spec_from_file_location("p44_original_profile_rules", entry)
    require(spec is not None and spec.loader is not None, "PROFILE_RULES_UNAVAILABLE")
    rules = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(rules)
    original = json_bytes(git(root, "show", SOURCE_COMMIT + ":" + PROFILE_PATH))
    current = json_bytes(git(root, "show", candidate + ":" + PROFILE_PATH))
    rules._validate_manifest_profile_config(original)
    rules._validate_manifest_profile_config(current)
    require(original["exclude_path_regex"] == current["exclude_path_regex"]
            and all(current["profiles"].get(name) == definition
                    for name, definition in original["profiles"].items()), "HISTORY_PROFILE_CHANGED")

    def tree(commit):
        entries = {}
        for row in git(root, "ls-tree", "-r", "-z", commit).split(b"\0"):
            if row:
                header, name = row.split(b"\t", 1)
                entries[name.decode("utf-8")] = header.decode("ascii")
        return entries

    old_tree, new_tree = tree(SOURCE_COMMIT), tree(candidate)
    compared, additions = {}, {}
    for profile in ("Production", "Validation", "Governance"):
        definition = original["profiles"][profile]
        require(current["profiles"][profile] == definition, "HISTORY_PROFILE_CHANGED")
        old_paths = set(rules._filter_profile_paths(old_tree, definition, re.compile(original["exclude_path_regex"])))
        new_paths = set(rules._filter_profile_paths(new_tree, definition, re.compile(original["exclude_path_regex"])))
        require(old_paths and set(definition["required_paths"]) <= old_paths, "HISTORY_PROFILE_INCOMPLETE")
        if profile == "Validation":
            old_paths.discard(PROFILE_PATH)
            new_paths.discard(PROFILE_PATH)
        else:
            require(old_paths == new_paths, "HISTORICAL_INPUT_SET_CHANGED")
        require(old_paths <= new_paths and all(old_tree[path] == new_tree[path] for path in old_paths),
                "HISTORICAL_INPUT_CHANGED")
        compared[profile] = len(old_paths)
        additions[profile] = sorted(new_paths - old_paths)
    return {"source_commit": SOURCE_COMMIT, "candidate_commit": candidate,
            "compared_existing_paths": compared, "new_paths_not_covered_by_old_tests": additions,
            "profile_rule_reuse": "Tools/acceptance/validate_bundle.py",
            "profile_config_changed": original != current,
            "new_profile_names": sorted(set(current["profiles"]) - set(original["profiles"])),
            "scope": "Git objects only; formal worktree checks and newly added profile/runner tests remain separate"}


def receipt(files, label, command=None, args=None, exit_code=0):
    key = "remediation-" + label
    result = json_bytes(files[key + ".json"])
    require(result.get("label") == key and result.get("exitCode") == exit_code
            and type(result.get("exitCode")) is int and result.get("signal") is None,
            "COMMAND_RECEIPT_FAILED")
    require(timestamp(result.get("startedAt")) <= timestamp(result.get("endedAt")), "COMMAND_TIME_ORDER")
    require(result.get("cwd", "").replace("\\", "/") == ORIGINAL_WORKTREE
            and result.get("logPath", "").replace("\\", "/")
            == ORIGINAL_WORKTREE + "/.cache/p44/logs/" + key + ".log", "COMMAND_ORIGIN_MISMATCH")
    if command is not None:
        require(result.get("command") == command and result.get("args") == args, "COMMAND_BINDING_MISMATCH")
    return files[key + ".log"].decode("utf-8")


def run_state(files, label, run_id, expected_jobs):
    value = json_bytes(receipt(files, label, "gh", ["run", "view", str(run_id), "--repo", REPOSITORY,
                       "--json", "headSha,status,conclusion,event,jobs,url"]))
    url = "https://github.com/" + REPOSITORY + "/actions/runs/" + str(run_id)
    require(value.get("url") == url and value.get("headSha") == SOURCE_COMMIT
            and value.get("event") == "workflow_dispatch" and value.get("status") == "completed"
            and value.get("conclusion") == "success", "CI_RUN_NOT_SUCCESSFUL")
    jobs = value.get("jobs")
    require(isinstance(jobs, list) and len(jobs) == len(expected_jobs)
            and {job.get("name") for job in jobs} == set(expected_jobs), "CI_JOB_SCOPE")
    for job in jobs:
        require(job.get("status") == "completed" and job.get("conclusion") == expected_jobs[job["name"]],
                "CI_JOB_NOT_SUCCESSFUL")
        require(integer(job.get("databaseId"), 1) and job.get("url") == url + "/job/" + str(job["databaseId"]),
                "CI_JOB_IDENTITY")
        steps = job.get("steps")
        require(isinstance(steps, list), "CI_STEPS_MISSING")
        if expected_jobs[job["name"]] == "skipped":
            require(not steps, "UNEXPECTED_RELEASE_EXECUTION")
        else:
            require(steps and len({step.get("name") for step in steps}) == len(steps), "CI_STEPS_MISSING")
            for step in steps:
                expected = "skipped" if step["name"] in SKIPPED_STEPS.get(job["name"], set()) else "success"
                require(step.get("status") == "completed" and step.get("conclusion") == expected,
                        "CI_STEP_FAILED")
    return value


def full_log(files, label, run_id, state):
    raw = receipt(files, label, "gh", ["run", "view", str(run_id), "--repo", REPOSITORY, "--log"])
    jobs = {job["name"]: job for job in state["jobs"]}
    groups = {}
    for line in raw.splitlines():
        if not line:
            continue
        parts = line.split("\t", 2)
        require(len(parts) == 3 and parts[0] in jobs, "CI_LOG_SOURCE_MISMATCH")
        job, step, message = parts
        require(step in {item["name"] for item in jobs[job]["steps"]}, "CI_LOG_STEP_MISMATCH")
        date, separator, rest = message.partition(" ")
        # GitHub prefixes each step with a BOM and leaves multiline path values untimed.
        if re.fullmatch(r"\ufeff?\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}\.\d+Z", date):
            timestamp(date.removeprefix("\ufeff"))
            message = rest
        else:
            require((job, step) in groups and step in {
                "Upload firmware artifact", "Upload Boot artifact",
                "Preserve development byte fixtures and step originals",
                "Preserve P3-4 adapter self-test originals",
            } and (not message or re.fullmatch(
                r"(?:/home/runner/work/E-Track/E-Track/)?\.cache/[A-Za-z0-9_./*-]+", message)),
                "CI_LOG_TIMESTAMP_MISSING")
        groups.setdefault((job, step), []).append(ANSI.sub("", message))
    for job in jobs.values():
        if job["conclusion"] == "success":
            require((job["name"], "Complete job") in groups, "CI_FULL_LOG_INCOMPLETE")
            for step in job["steps"]:
                if step["conclusion"] == "success":
                    require((job["name"], step["name"]) in groups, "CI_FULL_LOG_INCOMPLETE")
    return {key: "\n".join(lines) for key, lines in groups.items()}, raw


def node_counts(text, expected):
    clean = ANSI.sub("", text)
    expected_values = {"tests": expected, "pass": expected, "fail": 0, "cancelled": 0, "skipped": 0, "todo": 0}
    for field, value in expected_values.items():
        matches = re.findall(r"^[\s\u2139#]*" + field + r"\s+(\d+)\s*$", clean, re.MULTILINE)
        require(matches == [str(value)], "NODE_TEST_COUNTS_MISMATCH")
    return expected


def vitest_counts(text, files, tests):
    clean = ANSI.sub("", text)
    for field, number in (("Test Files", files), ("Tests", tests)):
        matches = re.findall(r"^\s*" + field + r"\s+(\d+) passed\s+\((\d+)\)\s*$", clean, re.MULTILINE)
        require(matches == [(str(number), str(number))], "VITEST_COUNTS_MISMATCH")
    require(not re.search(r"^\s*(?:Test Files|Tests)\s+.*\bfailed\b", clean, re.MULTILINE), "VITEST_FAILURE")
    return tests


def history(files):
    for label in HISTORY_LABELS:
        receipt(files, label, exit_code=1 if label in {"ci-full-log-01", "npm-audit-01"} else 0)
    firmware_dispatch = receipt(files, "checks-dispatch-01", "gh", ["workflow", "run", "firmware-build.yml", "--repo", REPOSITORY,
            "--ref", "dev/p4-4/config-integration-20261018", "-f", "publish=false", "-f", "rehearsal=false",
            "-f", "check_bindings=false"])
    governance_dispatch = receipt(files, "governance-dispatch-01", "gh", ["workflow", "run", "acceptance-governance.yml", "--repo",
            REPOSITORY, "--ref", "dev/p4-4/config-integration-20261018"])
    for stdout, run_id in ((firmware_dispatch, 39175549010), (governance_dispatch, 39175558187)):
        require(stdout.strip() == "https://github.com/" + REPOSITORY + "/actions/runs/" + str(run_id),
                "DISPATCH_RUN_BINDING")
    firmware = run_state(files, "ci-state-02", 39175549010,
                         {BUILD: "success", DEVELOPMENT: "success", **{name: "skipped" for name in SKIPPED_JOBS}})
    governance = run_state(files, "governance-state-01", 39175558187, {
        "Validate acceptance and build governance": "success",
        "Flutter debugging skill (ubuntu-latest)": "success",
        "Flutter debugging skill (windows-latest)": "success",
    })
    logs, firmware_raw = full_log(files, "ci-full-log-02", 39175549010, firmware)
    governance_logs, governance_raw = full_log(files, "governance-full-log-01", 39175558187, governance)
    observed = {}
    for key, step, file_count, count in (
        ("script_migration", "Run script and migration host tests explicitly (not workerd)", 2, 41),
        ("pipeline", "Run release pipeline with real handlers and SQLite host ports (not rehearsal)", 1, 147),
        ("native", "Run native workerd D1 R2 and registration invariants (not host doubles)", 4, 283),
    ):
        observed[key] = vitest_counts(logs[(DEVELOPMENT, step)], file_count, count)
    observed["sdk_workflow"] = node_counts(logs[(DEVELOPMENT, "Check workflow execution graph and configuration gates")], 112)
    observed["byte"] = node_counts(logs[(DEVELOPMENT, "Execute production byte preparation with isolated fixtures")], 22)
    observed["sdk_host"] = node_counts(receipt(files, "sdk-01", "node", ["--test", "tests/ota/test_firmware_s3.mjs"]), 23)
    observed["workflow_host"] = node_counts(receipt(files, "workflow-01", "node", ["--test", "tests/ota/test_firmware_workflow.mjs"]), 89)
    require(observed["sdk_host"] + observed["workflow_host"] == observed["sdk_workflow"], "SDK_WORKFLOW_COUNT_MISMATCH")
    vitest_counts(receipt(files, "pipeline-host-01", "node", [
        "D:/install/nvm/nodejs/node_modules/npm/bin/npm-cli.js", "test", "--prefix",
        "app/bluetooth_flutter_Trace/cloudflare/update-service/worker", "--", "--config",
        "../../../../../.github/scripts/p41-host.config.mjs"]), 1, 147)
    require(receipt(files, "types-01", "node", [
        "app/bluetooth_flutter_Trace/cloudflare/update-service/worker/node_modules/typescript/bin/tsc", "--noEmit",
        "--project", "app/bluetooth_flutter_Trace/cloudflare/update-service/worker/tsconfig.json"]) == "", "TYPECHECK_OUTPUT_CHANGED")
    require("Total Upload:" in logs[(DEVELOPMENT, "Build tested Worker deployment input without cloud access")],
            "WORKER_BUILD_OUTPUT_MISSING")
    for step in ("Configure (CMake + Ninja)", "Build firmware", "Report firmware artifacts",
                 "Exercise the shared key-bound GCC build without protected credentials"):
        require(logs.get((BUILD, step), "").strip(), "GCC_BUILD_OUTPUT_MISSING")
    regression = governance_logs[("Validate acceptance and build governance", "Run governance regression tests")]
    counts = [int(value) for value in re.findall(r"^Ran (\d+) tests? in [0-9.]+s$", regression, re.MULTILINE)]
    require(counts == [137, 36, 3, 14, 11, 62, 39, 29]
            and len(re.findall(r"^OK(?: \([^\n]+\))?$", regression, re.MULTILINE)) == len(counts),
            "GOVERNANCE_REGRESSION_OUTPUT_MISMATCH")
    failed = receipt(files, "ci-full-log-01", "gh", ["run", "view", "39175549010", "--repo", REPOSITORY, "--log"], 1)
    require("TLS handshake timeout" in failed and "/actions/runs/39175549010" in failed, "FAILED_ORIGINAL_MISSING")
    audit = json_bytes(receipt(files, "npm-audit-01", "node", [
        "D:/install/nvm/nodejs/node_modules/npm/bin/npm-cli.js", "audit", "--json", "--prefix",
        "app/bluetooth_flutter_Trace/cloudflare/update-service/worker", "--registry=https://registry.npmjs.org",
        "--ignore-scripts"], exit_code=1))
    vulnerabilities = audit.get("metadata", {}).get("vulnerabilities")
    require(vulnerabilities == {"info": 0, "low": 0, "moderate": 3, "high": 8, "critical": 0, "total": 11},
            "DEPENDENCY_DEBT_CHANGED")
    require(isinstance(audit.get("vulnerabilities"), dict) and len(audit["vulnerabilities"]) == 11,
            "DEPENDENCY_ORIGINAL_INCOMPLETE")
    return {"ci_runs": {"firmware": 39175549010, "governance": 39175558187}, "original_files": len(files),
            "test_counts": observed, "governance_regression_counts": counts,
            "warning_word_occurrences": {"firmware_full_log": len(re.findall(r"\bwarning\b", firmware_raw, re.I)),
                                         "governance_full_log": len(re.findall(r"\bwarning\b", governance_raw, re.I))},
            "warning_count_scope": "Occurrences in complete stdout, not unique compiler diagnostics",
            "dependency_debt": vulnerabilities,
            "preserved_failures": [{"label": "remediation-ci-full-log-01", "exit_code": 1,
                                    "classification": "historical TLS log-retrieval failure, not converted to PASS"},
                                   {"label": "remediation-npm-audit-01", "exit_code": 1,
                                    "classification": "disclosed dependency debt, not a clean audit"}],
            "scope": "Independent evaluation of historical development originals; no CI rerun or new rehearsal"}


def configuration_responses(report):
    cf = "/client/v4/"
    gh = "/repos/" + REPOSITORY + "/"
    specifications = [
        ("sourceVerification", cf + "user/tokens/verify"),
        ("permissionCatalog", cf + "accounts/[REDACTED]/tokens/permission_groups"),
        ("tokenDirectory", cf + "accounts/[REDACTED]/tokens"),
        ("productionPolicy", cf + "accounts/[REDACTED]/tokens/[REDACTED]"),
        ("rehearsalPolicy", cf + "accounts/[REDACTED]/tokens/[REDACTED]"),
    ]
    for role in TOKENS:
        route = gh + "environments/firmware-" + role
        specifications.extend([(role + "Environment", route), (role + "Secrets", route + "/secrets"),
                               (role + "Variables", route + "/variables"),
                               (role + "Branches", route + "/deployment-branch-policies")])
    specifications.extend([("repositoryGate", gh + "actions/variables/OTA_BOOT_CHAIN_READY"),
                           ("mainRef", gh + "git/ref/heads/main")])
    requests, observations = report.get("requests"), report.get("observations")
    require(isinstance(requests, list) and len(requests) == 15 and isinstance(observations, dict)
            and set(observations) == {name for name, _ in specifications}, "READBACK_REQUESTS_INCOMPLETE")
    start, end = timestamp(report.get("startedAt")), timestamp(report.get("endedAt"))
    values, registry = {}, []
    previous_end = start
    for number, ((name, route), request) in enumerate(zip(specifications, requests), 1):
        origin = "https://api.cloudflare.com" if route.startswith(cf) else "https://api.github.com"
        observation = observations[name]
        require(request.get("method") == "GET" and request.get("origin") == origin
                and request.get("path") == route and request.get("status") == 200
                and observation.get("status") == 200, "READBACK_HTTP_BINDING")
        request_start, request_end = timestamp(request.get("startedAt")), timestamp(request.get("endedAt"))
        require(previous_end <= request_start <= request_end <= end, "READBACK_TIME_ORDER")
        previous_end = request_end
        require(integer(request.get("bytes"), 1) and request["bytes"] == observation.get("originalBytes")
                and isinstance(request.get("sha256"), str) and HASH.fullmatch(request["sha256"])
                and request["sha256"] == observation.get("originalSha256"), "PRIVATE_ORIGINAL_REGISTRY_MISMATCH")
        require(observation.get("original", "").replace("\\", "/")
                == PROJECT + "/.cache/p44-root-acceptance-20261019/private/credential-readback-01/" + f"{number:02d}.json",
                "PRIVATE_ORIGINAL_ORIGIN_MISMATCH")
        body = observation.get("response")
        require(isinstance(body, dict), "READBACK_RESPONSE_MISSING")
        if origin.endswith("cloudflare.com"):
            require(body.get("success") is True and body.get("errors") == [], "CLOUDFLARE_RESPONSE_FAILED")
        values[name] = body
        registry.append({"ordinal": number, "size_bytes": request["bytes"], "sha256": request["sha256"]})
    return values, registry


def token_policy(value, expected):
    require(value.get("name") == expected["name"] and value.get("status") == "active"
            and value.get("issued_on") == expected["issued_on"], "TOKEN_IDENTITY_MISMATCH")
    require(value.get("id") == "[REDACTED]", "TOKEN_IDENTIFIER_NOT_REDACTED")
    policies = value.get("policies")
    require(isinstance(policies, list) and len(policies) == 1, "TOKEN_POLICY_COUNT")
    policy = policies[0]
    require(set(policy) == {"id", "effect", "resources", "permission_groups"}
            and policy.get("effect") == "allow", "TOKEN_POLICY_EFFECT_OR_FIELDS")
    require(policy.get("resources") == {
        "com.cloudflare.edge.r2.bucket.[REDACTED]_default_" + expected["bucket"]: "*"}, "TOKEN_RESOURCE_SCOPE")
    groups = policy.get("permission_groups")
    require(isinstance(groups, list) and len(groups) == 2
            and all(isinstance(group, dict) and set(group) == {"id", "name"} for group in groups)
            and {group["id"]: group["name"] for group in groups} == GROUPS, "TOKEN_PERMISSION_SCOPE")
    require(value.get("condition") in (None, {}) and value.get("conditions") in (None, {})
            and value.get("expires_on") is None and value.get("not_before") is None,
            "TOKEN_CONDITIONS_OR_LIFETIME")


def named_collection(body, name):
    values = body.get(name)
    require(isinstance(values, list) and type(body.get("total_count")) is int
            and body["total_count"] == len(values) and len(values) <= 100
            and all(isinstance(value, dict) and isinstance(value.get("name"), str) for value in values)
            and len({value["name"] for value in values}) == len(values), "GITHUB_COLLECTION_INCOMPLETE")
    return {value["name"]: value for value in values}


def acl_receipts(report):
    private = PROJECT + "/.cache/p44-cred-20261019/private"
    expected = {private: True, **{private + "/" + name: False for name in (
        "p44-s3-credentials-20261019.json", "production_access_key_id.txt", "production_secret_access_key.txt",
        "rehearsal_access_key_id.txt", "rehearsal_secret_access_key.txt")},
        PROJECT + "/app/bluetooth_flutter_Trace/cloudflare/update-service/.github-actions-secrets.staging.local.json": False}
    targets = report.get("targets")
    require(isinstance(targets, list) and len(targets) == 7 and all(isinstance(row, dict) for row in targets)
            and {row.get("path", "").replace("\\", "/") for row in targets} == set(expected), "ACL_TARGET_SCOPE")
    require(timestamp(report.get("startedAt")) <= timestamp(report.get("endedAt"))
            and report.get("currentUserSid") == "S-1-5-21-819482931-1251681997-588373447-1001",
            "ACL_ORIGIN_IDENTITY")
    exposures = 0
    for row in targets:
        path = row["path"].replace("\\", "/")
        require(type(row.get("isDirectory")) is bool and row["isDirectory"] == expected[path], "ACL_TARGET_TYPE")
        before, after, operation = row.get("beforeAcl"), row.get("afterAcl"), row.get("operationOutput")
        require(all(isinstance(value, str) and row["path"] in value for value in (before, after, operation)),
                "ACL_RAW_RECEIPT_MISSING")
        grants = [line.strip() for line in after.splitlines() if ":(" in line]
        permissions = "(OI)(CI)(F)" if row["isDirectory"] else "(F)"
        require(grants == [row["path"] + " DESKTOP-AODKGQR\\SU:" + permissions], "ACL_NOT_CURRENT_USER_ONLY")
        require(row.get("currentUserOnly") is True and row.get("contentUnchanged") is True, "ACL_COLLECTOR_FAILED")
        if "BUILTIN\\Users:" in before and "NT AUTHORITY\\Authenticated Users:" in before:
            exposures += 1
    require(exposures == 2, "ACL_EXPOSURE_HISTORY_MISSING")
    require(report.get("complete") is True and report.get("contentChanged") is False
            and report.get("tokenRotation") is False and report.get("platformMutations") is False
            and report.get("formalAcceptance") == "NOT_RUN", "ACL_COLLECTOR_FAILED")
    return {"targets": 7, "current_user_only_after_receipts": 7, "broad_before_receipts": exposures,
            "content_unchanged": "Recorded by the hash-bound collector's before/after SHA256 comparisons; private bytes not reopened",
            "limitation": "An exposure window existed; receipts neither prove access nor establish never exposed"}


def configuration(files):
    readback = json_bytes(files["credential-readback-01.json"])
    values, registry = configuration_responses(readback)
    require(values["sourceVerification"]["result"].get("status") == "active", "SOURCE_TOKEN_INACTIVE")
    source = readback.get("source", {})
    require(source.get("path") == "app/bluetooth_flutter_Trace/cloudflare/update-service/.github-actions-secrets.staging.local.json"
            and source.get("managementIdSha256") == SOURCE_ID and SOURCE_ID != OLD_SOURCE_ID
            and source.get("sameValueAsOldLocal") is False and source.get("sameValueAsExistingCi") is False
            and source.get("sameManagementIdAsOldLocal") is False
            and source.get("accountMatchesApproved") is True and source.get("privateDerivationMatches") is True,
            "MANAGEMENT_SOURCE_MISMATCH")
    catalog = values["permissionCatalog"].get("result")
    require(isinstance(catalog, list), "PERMISSION_CATALOG_INVALID")
    for group_id, name in GROUPS.items():
        matches = [entry for entry in catalog if entry.get("id") == group_id]
        require(len(matches) == 1 and matches[0].get("name") == name
                and matches[0].get("scopes") == ["com.cloudflare.edge.r2.bucket"], "PERMISSION_CATALOG_MISMATCH")
    directory = values["tokenDirectory"]
    tokens, info = directory.get("result"), directory.get("result_info")
    require(isinstance(tokens, list) and len(tokens) == 3
            and {token.get("name") for token in tokens} == {"Track", *(item["name"] for item in TOKENS.values())}
            and isinstance(info, dict) and info.get("page") == 1 and info.get("total_pages") == 1
            and info.get("count") == 3 and info.get("total_count") == 3, "TOKEN_DIRECTORY_INCOMPLETE")
    require(all(token.get("id") == "[REDACTED]" for token in tokens), "TOKEN_IDENTIFIER_NOT_REDACTED")
    stored_names = []
    for role, expected in TOKENS.items():
        token = values[role + "Policy"]["result"]
        token_policy(token, expected)
        listed = next(item for item in tokens if item["name"] == expected["name"])
        token_policy(listed, expected)
        require(listed == token, "TOKEN_DIRECTORY_POLICY_MISMATCH")
        summary = readback.get("tokens", {}).get(role, {})
        require(summary.get("idSha256") == expected["id_sha256"] and summary.get("expiresOn") is None
                and summary.get("notBefore") is None and summary.get("policies") == token["policies"],
                "TOKEN_PROJECTION_BINDING")
        environment = values[role + "Environment"]
        require(environment.get("name") == "firmware-" + role
                and environment.get("deployment_branch_policy")
                == {"protected_branches": False, "custom_branch_policies": True}, "ENVIRONMENT_BINDING")
        rules = environment.get("protection_rules")
        require(isinstance(rules, list) and len(rules) == 2
                and Counter(rule.get("type") for rule in rules) == {"required_reviewers": 1, "branch_policy": 1},
                "ENVIRONMENT_PROTECTION_SCOPE")
        reviewer = next(rule for rule in rules if rule["type"] == "required_reviewers")
        reviewers = reviewer.get("reviewers")
        require(reviewer.get("prevent_self_review") is (role == "production") and isinstance(reviewers, list)
                and len(reviewers) == 1 and reviewers[0].get("type") == "User"
                and reviewers[0].get("reviewer", {}).get("login") == "Eitan-S-23"
                and reviewers[0]["reviewer"].get("id") == 204050265, "REVIEWER_POLICY_MISMATCH")
        secrets = named_collection(values[role + "Secrets"], "secrets")
        prefix = "" if role == "production" else "FIRMWARE_REHEARSAL_"
        names = {prefix + suffix for suffix in ("TRACE_R2_ACCESS_KEY_ID", "TRACE_R2_SECRET_ACCESS_KEY")}
        require(names <= set(secrets), "ENVIRONMENT_SECRET_MISSING")
        for name in names:
            require("value" not in secrets[name] and timestamp(secrets[name]["created_at"])
                    <= timestamp(secrets[name]["updated_at"]), "SECRET_METADATA_INVALID")
        stored_names.extend(sorted(names))
        variables = named_collection(values[role + "Variables"], "variables")
        require(variables.get("OTA_BOOT_CHAIN_READY", {}).get("value") == "false", "ENVIRONMENT_GATE_UNLOCKED")
        branches = named_collection(values[role + "Branches"], "branch_policies")
        branch = "main" if role == "production" else "dev/p4-1/unattended-20261015"
        require(set(branches) == {branch} and branches[branch].get("type") == "branch", "HISTORICAL_BRANCH_SCOPE")
    require(values["repositoryGate"].get("name") == "OTA_BOOT_CHAIN_READY"
            and values["repositoryGate"].get("value") == "false", "REPOSITORY_GATE_UNLOCKED")
    require(values["mainRef"].get("ref") == "refs/heads/main"
            and values["mainRef"].get("object", {}).get("sha") == "0779f677507fa2c8a88c1799c8d2909bbae5a0a0",
            "HISTORICAL_MAIN_MISMATCH")
    checks = readback.get("checks")
    require(isinstance(checks, list) and len(checks) == 28 and all(item.get("passed") is True for item in checks)
            and readback.get("complete") is True and readback.get("mutations") == 0
            and readback.get("formalAcceptance") == "NOT_RUN", "READBACK_COLLECTOR_FAILED")
    creation = json_bytes(files["create-s3-02.json"])
    require(set(creation.get("jobs", {})) == set(TOKENS), "CREATION_JOB_SCOPE")
    for role, expected in TOKENS.items():
        job = creation["jobs"][role]
        require(job.get("http_create") == 200 and job.get("s3_sigv4_listobjects_http") == 200
                and job.get("name") == expected["name"] and job.get("bucket") == expected["bucket"]
                and job.get("resource_scope") == "com.cloudflare.edge.r2.bucket.[REDACTED]_default_" + expected["bucket"]
                and job.get("gh_env") == "firmware-" + role and job.get("token_id") == "[REDACTED]",
                "CREATION_OBSERVATION_MISMATCH")
    previous = json_bytes(files["verify-perm-01.json"])
    require(previous.get("token_list", {}).get("http") == 200 and previous["token_list"].get("count") == 1
            and len(previous["token_list"].get("items", [])) == 1
            and previous["token_list"]["items"][0].get("name") == "Track"
            and previous["token_list"]["items"][0].get("id") == "[REDACTED]"
            and previous.get("perm_groups", {}).get("http") == 200, "PRE_CREATION_DIRECTORY_MISMATCH")
    protection = acl_receipts(json_bytes(files["credential-protection-01.json"]))
    return {"original_files": len(files), "successful_gets": 15, "original_collector_assertions": 28,
            "source_management_id_sha256": SOURCE_ID, "old_management_id_sha256": OLD_SOURCE_ID,
            "source_changed": True, "exact_single_bucket_two_item_groups": True,
            "directory_names": sorted(["Track", *(item["name"] for item in TOKENS.values())]),
            "github_secret_names": stored_names, "provider_expiration": {role: None for role in TOKENS},
            "expiration_scope": "Provider fields absent or null; no 90-day expiry was applied",
            "gates_false": 3, "historical_environment_policies_verified": True,
            "existing_sigv4_listobjects_http_200": 2, "acl": protection,
            "private_original_registry": registry,
            "limitations": [
                "Declared sanitized HTTP projections evaluated; private original bodies only hash-bound, not reopened",
                "Secret names do not prove stored values or workflow consumption",
                "Two prior ListObjectsV2 successes prove listing authentication, not PUT, conflicts, or full byte readback",
                "No original initial HTTP 400 receipt or historical GitHub secret-write receipt was supplied",
                "Historical environment policies precede the planned P4-4 branch addition and reviewer observation",
                "Source comparison and unchanged credential bytes consume reviewed collector results, not fresh private reads",
                "Phase-limited owner rotation and revocation decisions are recorded separately from provider metadata",
            ]}


def worker_archive(root, files, rows):
    first = json_bytes(files["preparation/worker-input-01.json"])
    second = json_bytes(files["preparation/worker-input-02.json"])
    require(first.get("error") == "Required preflight source absent from bundle"
            and first.get("complete") is not True and second.get("complete") is True
            and "error" not in second and second.get("requests") == [], "WORKER_INPUT_FAILURE_HISTORY")
    require(timestamp(first["endedAt"]) <= timestamp(second["startedAt"]) <= timestamp(second["endedAt"])
            and second.get("prior", {}).get("path") == "worker-input-01.json"
            and second["prior"].get("sha256") == rows["preparation/worker-input-01.json"]["originalSha256"],
            "WORKER_INPUT_REUSE_BINDING")
    expected_run = {"id": 39175549010, "headSha": SOURCE_COMMIT, "attempt": 1,
                    "status": "completed", "conclusion": "success"}
    for record in (first, second):
        require(record.get("commit") == SOURCE_COMMIT and record.get("runId") == 39175549010
                and record.get("run") == expected_run and record.get("deployed") is False
                and record.get("formalAcceptance") == "NOT_RUN", "WORKER_INPUT_CI_BINDING")
        job, artifact = record.get("toolingJob", {}), record.get("artifact", {})
        require(job.get("id") == 117817345384 and job.get("run_id") == 39175549010
                and job.get("head_sha") == SOURCE_COMMIT and job.get("run_attempt") == 1
                and job.get("name") == DEVELOPMENT and job.get("status") == "completed"
                and job.get("conclusion") == "success", "WORKER_INPUT_CI_BINDING")
        steps = job.get("steps", [])
        require(steps and all(step.get("status") == "completed" and step.get("conclusion") == "success"
                              for step in steps)
                and {"Build tested Worker deployment input without cloud access", "Preserve tested Worker deployment input"}
                <= {step.get("name") for step in steps}, "WORKER_INPUT_CI_STEP")
        require(artifact.get("id") == 12154675551 and artifact.get("size_in_bytes") == 102228
                and artifact.get("digest") == "sha256:" + WORKER_ZIP_SHA256
                and artifact.get("name") == "p41-worker-bundle-" + SOURCE_COMMIT
                and artifact.get("workflow_run", {}).get("id") == 39175549010
                and artifact["workflow_run"].get("head_sha") == SOURCE_COMMIT, "WORKER_ARTIFACT_BINDING")
    require(first["artifact"] == second["artifact"] and first["toolingJob"] == second["toolingJob"],
            "WORKER_INPUT_REUSE_BINDING")
    requests = first.get("requests")
    route = "/repos/" + REPOSITORY + "/actions/runs/39175549010"
    require(isinstance(requests, list) and len(requests) == 3, "WORKER_INPUT_HTTP_BINDING")
    previous_end = timestamp(first["startedAt"])
    for request, suffix in zip(requests, ("", "/attempts/1/jobs", "/artifacts")):
        require(request.get("method") == "GET" and request.get("origin") == "https://api.github.com"
                and request.get("path") == route + suffix and request.get("status") == 200,
                "WORKER_INPUT_HTTP_BINDING")
        require(previous_end <= timestamp(request["startedAt"]) <= timestamp(request["endedAt"])
                <= timestamp(first["endedAt"]), "WORKER_INPUT_HTTP_TIME_ORDER")
        previous_end = timestamp(request["endedAt"])
    download = first.get("operations", [{}])[0]
    require(download.get("executable") == "gh" and download.get("exitCode") == 0
            and download.get("args") == ["api", "repos/" + REPOSITORY + "/actions/artifacts/12154675551/zip"],
            "WORKER_ARTIFACT_DOWNLOAD_BINDING")
    data = files["preparation/worker-input-01.zip"]
    require(rows["preparation/worker-input-01.zip"]["byteExact"] is True
            and len(data) == 102228 and sha256(data) == WORKER_ZIP_SHA256
            and second.get("archive", {}).get("bytes") == len(data)
            and second["archive"].get("sha256") == sha256(data), "WORKER_ZIP_IDENTITY")
    with zipfile.ZipFile(io.BytesIO(data)) as archive:
        members = archive.infolist()
        expected = {"README.md", "index.js", "index.js.map", "purpose.txt", "source-commit.txt"}
        require(len(members) == 5 and {item.filename for item in members} == expected
                and all(not item.is_dir() and not (item.flag_bits & 1)
                        and not stat.S_ISLNK(item.external_attr >> 16) for item in members)
                and sum(item.file_size for item in members) <= 4 * 1024 * 1024, "WORKER_ZIP_MEMBERS")
        require(archive.read("source-commit.txt").decode("utf-8-sig").strip() == SOURCE_COMMIT, "WORKER_ZIP_SOURCE")
        runtime = archive.read("index.js")
        source_map = json_bytes(archive.read("index.js.map"))
    require(len(runtime) == 149013 and sha256(runtime) == WORKER_MODULE_SHA256
            and second.get("runtime", {}).get("bytes") == len(runtime)
            and second["runtime"].get("sha256") == sha256(runtime)
            and b"/api/ci/firmware/preflight" in runtime, "WORKER_MODULE_IDENTITY")
    sources, contents, checks = source_map.get("sources"), source_map.get("sourcesContent"), second.get("sourceChecks")
    require(source_map.get("version") == 3
            and source_map.get("sourceRoot") == "/home/runner/work/E-Track/E-Track/.cache/p41-worker-bundle"
            and isinstance(sources, list) and isinstance(contents, list) and len(sources) == len(contents)
            and len(sources) == len(set(sources)) and isinstance(checks, list) and len(checks) == 16
            and all(isinstance(item, dict) and set(item) == {"path", "gitBytesSha256"} for item in checks)
            and len({item["path"] for item in checks}) == 16, "WORKER_SOURCE_MAP_SHAPE")
    expected_checks = {item["path"]: item["gitBytesSha256"] for item in checks}
    verified = set()
    for source, content in zip(sources, contents):
        require(isinstance(source, str) and isinstance(content, str), "WORKER_SOURCE_MAP_SHAPE")
        name = posixpath.normpath(".cache/p41-worker-bundle/" + source)
        relative(name)
        require(name.startswith("app/bluetooth_flutter_Trace/cloudflare/update-service/"), "WORKER_SOURCE_MAP_SCOPE")
        if "/node_modules/" in name:
            continue
        require(name in expected_checks, "WORKER_SOURCE_MAP_SCOPE")
        original = git(root, "show", SOURCE_COMMIT + ":" + name)
        require(sha256(original) == expected_checks[name]
                and content.replace("\r\n", "\n") == original.decode("utf-8").replace("\r\n", "\n"),
                "WORKER_SOURCE_MAP_GIT_MISMATCH")
        verified.add(name)
    require(verified == set(expected_checks) and all(any(name.endswith(suffix) for name in verified) for suffix in (
        "/worker/src/index.ts", "/worker/src/firmware.ts", "/scripts/firmware-monotonic.mjs")), "WORKER_SOURCE_MAP_SCOPE")
    return runtime


def deployment_response(files, rows, report, target, ordinal, route):
    name = target["prefix"] + f"{ordinal:02d}.body"
    request = report["requests"][ordinal - 1]
    row = rows[name]
    require(request.get("method") == "GET" and request.get("origin") == "https://api.cloudflare.com"
            and request.get("path") == "/client/v4/accounts/[REDACTED]/workers/scripts/" + target["worker"] + route
            and request.get("status") == 200 and request.get("exitCode") == 0 and request.get("signal") is None,
            "DEPLOYMENT_HTTP_BINDING")
    require(request.get("bodyPath", "").replace("\\", "/") == PROJECT + "/" + row["source"]
            and request.get("bytes") == row["originalSizeBytes"] and request.get("sha256") == row["originalSha256"],
            "DEPLOYMENT_HTTP_ORIGINAL_BINDING")
    # Request receipts hash private originals; the inventory separately hashes public projections.
    return files[name]


def deployed_settings(body, target):
    value = json_bytes(body)
    require(value.get("success") is True and value.get("errors") == [] and isinstance(value.get("result"), dict),
            "DEPLOYMENT_SETTINGS_RESPONSE")
    settings = value["result"]
    bindings = settings.get("bindings")
    require(isinstance(bindings, list) and all(isinstance(item, dict) and isinstance(item.get("name"), str)
                                            for item in bindings)
            and len({item["name"] for item in bindings}) == len(bindings), "DEPLOYMENT_BINDING_SHAPE")
    by_name = {item["name"]: item for item in bindings}
    require([item for item in bindings if item.get("type") == "d1"] == [by_name.get("DB")]
            and by_name.get("DB") == {"name": "DB", "type": "d1", "id": target["database"],
                                       "database_id": target["database"]}, "DEPLOYMENT_DATABASE_BINDING")
    require([item for item in bindings if item.get("type") == "r2_bucket"] == [by_name.get("RELEASES_BUCKET")]
            and by_name.get("RELEASES_BUCKET") == {"name": "RELEASES_BUCKET", "type": "r2_bucket",
                                                    "bucket_name": target["bucket"]}, "DEPLOYMENT_BUCKET_BINDING")
    for name, text in (("ENVIRONMENT", target["environment"]), ("ENABLE_DIRECT_ADMIN_API", "false")):
        require(by_name.get(name) == {"name": name, "text": text, "type": "plain_text"}, "DEPLOYMENT_ENVIRONMENT_BINDING")
    secrets = {"DEPLOY_TOKEN_SHA256", "DOWNLOAD_HMAC_KEY_CURRENT"}
    require({item["name"] for item in bindings if item.get("type") == "secret_text"} == secrets
            and all(by_name.get(name) == {"name": name, "type": "secret_text"} for name in secrets),
            "DEPLOYMENT_SECRET_TYPE")
    require(settings.get("observability", {}).get("redact_query_string") is True, "DEPLOYMENT_QUERY_REDACTION")
    return settings


def deployed_multipart(body, header_bytes, expected_content):
    headers = {}
    status = None
    for line in header_bytes.decode("latin-1").splitlines():
        if line.startswith("HTTP/"):
            match = re.fullmatch(r"HTTP/[0-9.]+ ([0-9]{3}) .+", line)
            require(match is not None, "DEPLOYMENT_HEADERS_INVALID")
            status, headers = int(match[1]), {}
        elif line:
            key, separator, value = line.partition(":")
            require(status is not None and separator and (key.lower() == "set-cookie" or key.lower() not in headers),
                    "DEPLOYMENT_HEADERS_INVALID")
            headers[key.lower()] = value.strip()
    require(status == 200 and headers.get("cf-entrypoint") == "index.js"
            and headers.get("content-type") == expected_content.get("contentType"), "DEPLOYMENT_CONTENT_HEADERS")
    content_type = headers["content-type"]
    require(re.fullmatch(r"multipart/form-data; boundary=[A-Za-z0-9-]+", content_type), "DEPLOYMENT_CONTENT_HEADERS")
    message = BytesParser(policy=email_policy.default).parsebytes(
        b"MIME-Version: 1.0\r\nContent-Type: " + content_type.encode("ascii") + b"\r\n\r\n" + body)
    require(message.is_multipart() and not message.defects, "DEPLOYMENT_MULTIPART_INVALID")
    parts = list(message.iter_parts())
    require(len(parts) == 1 and not parts[0].defects and parts[0].get_content_disposition() == "form-data"
            and parts[0].get_param("name", header="content-disposition") == "index.js"
            and parts[0].get_filename() == "index.js", "DEPLOYMENT_MODULE_SET")
    module = parts[0].get_payload(decode=True)
    require(expected_content.get("entrypoint") == "index.js" and expected_content.get("sha256") == sha256(body)
            and len(module) == 149013 and sha256(module) == WORKER_MODULE_SHA256
            and expected_content.get("moduleBytes") == len(module)
            and expected_content.get("moduleSha256") == sha256(module), "DEPLOYMENT_MODULE_IDENTITY")
    return module


def deployment(root, files, rows):
    require(set(files) == set(rows) == DEPLOYMENT_FILES, "DEPLOYMENT_INVENTORY_INCOMPLETE")
    runtime = worker_archive(root, files, rows)
    observed = {}
    for role, target in DEPLOYMENTS.items():
        report = json_bytes(files[target["receipt"]])
        require(report.get("complete") is True and "error" not in report
                and report.get("formalAcceptance") == "NOT_RUN" and isinstance(report.get("requests"), list)
                and len(report["requests"]) == target["content_ordinal"], "DEPLOYMENT_RECEIPT_INCOMPLETE")
        previous_end = timestamp(report["startedAt"])
        for request in report["requests"]:
            start, end = timestamp(request["startedAt"]), timestamp(request["endedAt"])
            require(previous_end <= start <= end <= timestamp(report["endedAt"]), "DEPLOYMENT_TIME_ORDER")
            previous_end = end
        settings = deployed_settings(deployment_response(files, rows, report, target, target["settings_ordinal"], "/settings"), target)
        summary = report if role == "staging" else report.get("after", {})
        require((report.get("after") if role == "staging" else summary.get("settings")) == settings,
                "DEPLOYMENT_SETTINGS_SUMMARY_MISMATCH")
        response = json_bytes(deployment_response(files, rows, report, target, target["deployment_ordinal"], "/deployments"))
        records = response.get("result", {}).get("deployments")
        require(response.get("success") is True and response.get("errors") == [] and isinstance(records, list) and records
                and len({record.get("id") for record in records}) == len(records), "DEPLOYMENT_VERSION_RESPONSE")
        dates = [timestamp(record["created_on"]) for record in records]
        require(dates == sorted(dates, reverse=True)
                and dates[0] <= timestamp(report["requests"][target["deployment_ordinal"] - 1]["startedAt"])
                and records[0].get("id") == target["deployment"]
                and records[0].get("versions") == [{"version_id": target["version"], "percentage": 100}]
                and summary.get("version") == target["version"] and summary.get("deploymentId") == target["deployment"],
                "DEPLOYMENT_ACTIVE_VERSION")
        ordinal = target["content_ordinal"]
        body_name, header_name = target["prefix"] + f"{ordinal:02d}.body", target["prefix"] + f"{ordinal:02d}.headers"
        body = deployment_response(files, rows, report, target, ordinal, "/content/v2")
        require(rows[body_name]["byteExact"] is True and report["requests"][ordinal - 1].get("headersPath", "").replace("\\", "/")
                == PROJECT + "/" + rows[header_name]["source"], "DEPLOYMENT_CONTENT_ORIGIN")
        module = deployed_multipart(body, files[header_name], report.get("content", {}))
        require(module == runtime, "DEPLOYMENT_ZIP_BYTES_MISMATCH")
        observed[role] = {"worker": target["worker"], "deployment_id": target["deployment"], "version_id": target["version"],
                          "database_id": target["database"], "bucket": target["bucket"], "environment": target["environment"],
                          "module_bytes": len(module), "module_sha256": sha256(module),
                          "direct_admin": False, "query_redaction": True,
                          "observed_from": report["startedAt"], "observed_to": report["endedAt"]}
    initial = json_bytes(files["preparation/deploy/staging/deploy.json"])
    recovery = json_bytes(files["preparation/deploy/staging/redaction-recovery.json"])
    failed_production = json_bytes(files["preparation/deploy/production/deploy-03.json"])
    production = json_bytes(files[DEPLOYMENTS["production"]["receipt"]])
    for role, record in (("staging", initial), ("production", failed_production), ("production", production)):
        expected = DEPLOYMENTS[role]
        require(record.get("role") == role and record.get("sourceCommit") == SOURCE_COMMIT
                and record.get("runtimeSha256") == WORKER_MODULE_SHA256 and record.get("artifactId") == 12154675551
                and record.get("target", {}).get("name") == expected["worker"]
                and record["target"].get("bucket") == expected["bucket"]
                and record["target"].get("d1") == expected["database"]
                and record["target"].get("environment") == expected["environment"], "DEPLOYMENT_ATTEMPT_SOURCE")
    require(recovery.get("version") == DEPLOYMENTS["staging"]["version"]
            and recovery.get("deploymentId") == DEPLOYMENTS["staging"]["deployment"], "DEPLOYMENT_STAGING_FAILURE_HISTORY")
    require(initial.get("complete") is not True and initial.get("command", {}).get("exitCode") == 0
            and initial.get("error") == "Preserve query redaction atomically\n\nfalse !== true\n"
            and recovery.get("complete") is not True and recovery.get("before", {}).get("observability", {}).get("redact_query_string") is False
            and recovery.get("requests", [{}])[-1].get("errorClass") == "ECONNRESET"
            and recovery["requests"][-1].get("method") == "PATCH", "DEPLOYMENT_STAGING_FAILURE_HISTORY")
    require(failed_production.get("complete") is not True and failed_production.get("command", {}).get("exitCode") == 1
            and failed_production.get("error") == "Wrangler did not report success; reconcile, never blindly retry",
            "DEPLOYMENT_PRODUCTION_FAILURE_HISTORY")
    require(timestamp(initial["endedAt"]) <= timestamp(recovery["startedAt"]) <= timestamp(recovery["endedAt"])
            <= timestamp(observed["staging"]["observed_from"])
            and timestamp(failed_production["endedAt"]) <= timestamp(observed["production"]["observed_from"]),
            "DEPLOYMENT_FAILURE_TIME_ORDER")
    return {"source_commit": SOURCE_COMMIT, "ci_run_id": 39175549010, "artifact_id": 12154675551,
            "archive_sha256": WORKER_ZIP_SHA256, "source_map_git_paths": 16, "selected_files": len(files),
            "declared_projections": sum(not row["byteExact"] for row in rows.values()), "workers": observed,
            "preserved_failures": ["worker-input-01 source-path assumption", "staging query-redaction regression",
                                   "staging recovery ECONNRESET", "production deploy-03 Wrangler exit 1"],
            "scope": "Bounded historical deployment readbacks, not continuous or current unchanged-state monitoring"}


def write_result(root, output, result):
    output = guarded_path(root, output)
    require(not output.exists(), "OUTPUT_ALREADY_EXISTS")
    output.parent.mkdir(parents=True, exist_ok=True)
    output = guarded_path(root, output)
    data = (json.dumps(result, ensure_ascii=True, indent=2, allow_nan=False) + "\n").encode("utf-8")
    with output.open("xb") as stream:
        stream.write(data)
    return sha256(data)


def main(argv=None):
    parser = SafeArgumentParser(description=__doc__)
    parser.add_argument("mode", choices=("history", "configuration"))
    parser.add_argument("--repo-root", required=True, type=Path)
    parser.add_argument("--input", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args(argv)
    result = {"schema": "p44-original-evaluation-v1", "mode": args.mode,
              "started": datetime.now(timezone.utc).isoformat(), "platform_actions": 0}
    try:
        require(args.repo_root.is_absolute() and args.repo_root == Path(__file__).absolute().parents[3]
                == Path.cwd().absolute(), "WORKTREE_ROOT_MISMATCH")
        require(sys.flags.optimize == 0, "OPTIMIZED_ASSERTIONS_FORBIDDEN")
        output = guarded_path(args.repo_root, args.output)
        require(not output.exists(), "OUTPUT_ALREADY_EXISTS")
        ctx = Context(args.repo_root, args.input)
    except Exception as error:
        code = str(error) if isinstance(error, EvidenceError) else "PREFLIGHT_FAILED"
        print(json.dumps({"ok": False, "error_code": code, "output_written": False}))
        return 1
    try:
        require(ctx.manifest.is_file() and ctx.manifest.stat().st_size <= MAX_FILE, "MANIFEST_SIZE_BOUND")
        data = ctx.manifest.read_bytes()
        manifest = json_bytes(data)
        require(isinstance(manifest, dict) and manifest.get("schema") == "p44-originals-v1", "MANIFEST_SCHEMA")
        result["manifest_sha256"] = sha256(data)
        inventory, files = ctx.inventory(manifest[args.mode]["inventory"], args.mode)
        if args.mode == "history":
            result["input_applicability"] = input_applicability(ctx.root, manifest)
            result["observed"] = history(files)
        else:
            result["observed"] = configuration(files)
            result["observed"]["declared_projections"] = sum(row["projection"] for row in inventory["files"])
            require(isinstance(manifest.get("deployment"), dict) and "inventory" in manifest["deployment"],
                    "DEPLOYMENT_INPUT_REQUIRED")
            deployment_rows, deployment_files = ctx.deployment_inventory(manifest["deployment"]["inventory"])
            result["observed"]["deployment"] = deployment(ctx.root, deployment_files, deployment_rows)
        result["ok"] = True
    except Exception as error:
        result["ok"] = False
        result["error_code"] = str(error) if isinstance(error, EvidenceError) else "EVIDENCE_INVALID"
    result["files_verified"] = len(ctx.checked)
    result["ended"] = datetime.now(timezone.utc).isoformat()
    try:
        digest = write_result(args.repo_root, output, result)
    except Exception:
        print(json.dumps({"ok": False, "error_code": "OUTPUT_WRITE_FAILED", "output_written": False}))
        return 1
    print(json.dumps({"ok": result["ok"], "mode": args.mode, "error_code": result.get("error_code"),
                      "output": output.relative_to(ctx.root).as_posix(), "sha256": digest}))
    return 0 if result["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
