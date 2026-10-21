"""Bounded offline checks of P4-4 original evidence; no platform operations."""

from __future__ import annotations

import argparse
import collections
from datetime import datetime, timedelta, timezone
import gzip
import hashlib
import importlib.util
import io
import json
import os
from pathlib import Path
import re
import stat
import sys
from urllib.parse import parse_qs, quote, urlsplit
import xml.etree.ElementTree as ET
import zipfile
import zlib

sys.dont_write_bytecode = True

REPOSITORY = "Eitan-S-23/E-Track"
REPO_API = "/repos/" + REPOSITORY
WORKFLOW = ".github/workflows/firmware-build.yml"
REVIEWER = "Eitan-S-23"
REVIEWER_ID = 204050265
ENVIRONMENT = "firmware-rehearsal"
PROTOCOL = "s3-worker-preflight-v1"
REHEARSAL_JOB = "Firmware rehearsal (shared release implementation)"
PRODUCTION_JOB = "Firmware production (shared release implementation)"
BINDINGS_JOB = "Isolated firmware binding qualification (not rehearsal)"
BUILD_JOB = "Build firmware (arm-none-eabi-gcc)"
DEVELOPMENT_JOB = "Release tooling development checks (no cloud credentials)"
REQUIRED_STEPS = (
    "Enforce isolated locked-gate rehearsal",
    "Build matching GCC inputs with the protected packaging key",
    "Run the shared finalize verify upload register pipeline",
    "Check private key cleanup before archiving",
    "Preserve release attempt originals (not an approval)",
)
RESOURCES = {
    "production": ("1cd5db26-6bbd-4595-abef-72ff51ecdaf3", "e-track-firmware-production-releases"),
    "protected": ("0133ad9e-d4a2-4fef-a659-4f2bf3d3a645", "trace-update-staging-releases"),
    "staging": ("2617e1e1-956f-42ce-a465-da56d84abf06", "e-track-firmware-p41-test-releases"),
}
SCHEMA_SQL = "SELECT name,type,sql FROM sqlite_master ORDER BY type,name"
LEGACY_INSPECT = "docs/acceptance-contracts/P4-1-v2/tools/inspect.py"
RECOVERY_OWNER = "Tools/jlink/prepare-bootstrap-app.py"
HASH = re.compile(r"[0-9a-f]{64}\Z")
UUID = re.compile(r"[0-9a-f]{8}(?:-[0-9a-f]{4}){3}-[0-9a-f]{12}\Z")
MAX_FILE_BYTES = 256 * 1024 * 1024
MAX_HTTP_BYTES = 16 * 1024 * 1024


class EvidenceError(ValueError):
    """Only fixed, non-sensitive codes may leave the evaluator."""


def require(condition, code):
    if not condition:
        raise EvidenceError(code)


def integer(value, minimum=0):
    return type(value) is int and value >= minimum


def dispatch_boolean(value, expected):
    return (type(value) is bool and value is expected) or (type(value) is str and value == str(expected).lower())


def digest(data):
    return hashlib.sha256(data).hexdigest()


def canonical(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False, allow_nan=False)


def json_bytes(data):
    def unique(pairs):
        value = {}
        for key, item in pairs:
            require(key not in value, "DUPLICATE_JSON_KEY")
            value[key] = item
        return value

    try:
        return json.loads(data, object_pairs_hook=unique,
                          parse_constant=lambda _: (_ for _ in ()).throw(EvidenceError("INVALID_JSON_NUMBER")))
    except (UnicodeError, json.JSONDecodeError):
        raise EvidenceError("INVALID_JSON") from None


def timestamp(value):
    require(isinstance(value, str), "INVALID_TIMESTAMP")
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        raise EvidenceError("INVALID_TIMESTAMP") from None
    require(parsed.tzinfo is not None, "INVALID_TIMESTAMP")
    return parsed.astimezone(timezone.utc)


def decode_d1_wire(wire, headers):
    """Recompute a D1 representation from its bounded, original HTTP body."""
    require(isinstance(wire, bytes) and len(wire) <= MAX_HTTP_BYTES, "HTTP_WIRE_SIZE_LIMIT")
    require(isinstance(headers, dict) and all(isinstance(k, str) and isinstance(v, str)
                                            for k, v in headers.items()), "INVALID_HTTP_HEADERS")
    normalized = {name.lower(): value for name, value in headers.items()}
    require(len(normalized) == len(headers), "DUPLICATE_HTTP_HEADER")
    encoding = normalized.get("content-encoding", "identity").strip().lower()
    require(encoding in ("identity", "gzip"), "HTTP_ENCODING_UNSUPPORTED")
    length = normalized.get("content-length")
    require(length is None or length == str(len(wire)), "HTTP_WIRE_LENGTH")
    if encoding == "identity":
        return wire
    require(wire.startswith(b"\x1f\x8b"), "HTTP_GZIP_INVALID")
    try:
        # GzipFile checks CRC/EOF and limits each underlying decompress call.
        with gzip.GzipFile(fileobj=io.BytesIO(wire), mode="rb") as stream:
            decoded = stream.read(MAX_HTTP_BYTES + 1)
    except (OSError, EOFError, zlib.error):
        raise EvidenceError("HTTP_GZIP_INVALID") from None
    require(len(decoded) <= MAX_HTTP_BYTES, "HTTP_DECODED_SIZE_LIMIT")
    return decoded


def guarded_path(root, value, base=None):
    root = Path(os.path.abspath(root))
    path = Path(value)
    path = Path(os.path.abspath(path if path.is_absolute() else (base or root) / path))
    try:
        path.relative_to(root)
    except ValueError:
        raise EvidenceError("PATH_OUTSIDE_WORKTREE") from None
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
        raise EvidenceError("PATH_OUTSIDE_WORKTREE") from None
    return path


class Context:
    def __init__(self, root, manifest):
        self.root = Path(os.path.abspath(root))
        self.manifest = guarded_path(self.root, manifest)
        self.base = self.manifest.parent
        self.checked_files = {}

    def read(self, reference):
        require(isinstance(reference, dict) and set(reference) == {"path", "size_bytes", "sha256"},
                "INVALID_FILE_REFERENCE")
        require(isinstance(reference["path"], str) and reference["path"], "INVALID_FILE_REFERENCE")
        require(integer(reference["size_bytes"]) and reference["size_bytes"] <= MAX_FILE_BYTES,
                "FILE_SIZE_BOUND")
        require(isinstance(reference["sha256"], str) and HASH.fullmatch(reference["sha256"]),
                "INVALID_FILE_DIGEST")
        path = guarded_path(self.root, reference["path"], self.base)
        require(path.is_file() and path.stat().st_size == reference["size_bytes"], "FILE_SIZE_MISMATCH")
        data = path.read_bytes()
        require(len(data) == reference["size_bytes"] and digest(data) == reference["sha256"],
                "FILE_DIGEST_MISMATCH")
        self.checked_files[path.relative_to(self.root).as_posix()] = reference["sha256"]
        return data

    def file_path(self, reference):
        self.read(reference)
        return guarded_path(self.root, reference["path"], self.base)

    def document(self, reference):
        return json_bytes(self.read(reference))

    def response(self, record, method, path, status=200):
        require(isinstance(record, dict), "INVALID_HTTP_RECORD")
        require(record.get("completed", True) is True, "HTTP_TRANSPORT_INCOMPLETE")
        require(record.get("method") == method and record.get("path") == path
                and record.get("status") == status, "HTTP_BINDING_MISMATCH")
        require(timestamp(record.get("started")) <= timestamp(record.get("ended")), "HTTP_TIME_ORDER")
        headers = record.get("response_headers")
        require(isinstance(headers, dict) and all(isinstance(k, str) and isinstance(v, str)
                                                for k, v in headers.items()), "INVALID_HTTP_HEADERS")
        require(len({name.lower() for name in headers}) == len(headers), "DUPLICATE_HTTP_HEADER")
        require(not ({name.lower() for name in headers} & {"authorization", "set-cookie", "cookie"}),
                "SENSITIVE_HTTP_HEADER")
        d1 = method == "POST" and path in {
            "/accounts/[ACCOUNT]/d1/database/" + database + "/query" for database, _ in RESOURCES.values()}
        if d1:
            require(isinstance(record.get("body"), dict) and integer(record["body"].get("size_bytes"))
                    and record["body"]["size_bytes"] <= MAX_HTTP_BYTES, "HTTP_WIRE_SIZE_LIMIT")
        wire = self.read(record["body"])
        if not d1:
            require("decoded_body" not in record, "HTTP_UNEXPECTED_DECODED")
            return wire
        decoded = decode_d1_wire(wire, headers)
        if header(record, "content-encoding") is not None and header(record, "content-encoding").strip().lower() == "gzip":
            reference = record.get("decoded_body")
            require(isinstance(reference, dict) and integer(reference.get("size_bytes"))
                    and reference["size_bytes"] <= MAX_HTTP_BYTES, "HTTP_DECODED_REFERENCE")
            require(self.read(reference) == decoded, "HTTP_DECODED_MISMATCH")
        else:
            require("decoded_body" not in record, "HTTP_UNEXPECTED_DECODED")
        return decoded


def header(record, name):
    return next((value for key, value in record["response_headers"].items() if key.lower() == name), None)


def page_path(path, base, number):
    parts = urlsplit(path)
    require(not parts.scheme and not parts.netloc and not parts.fragment and parts.path == base,
            "PAGINATION_ROUTE_MISMATCH")
    require(parse_qs(parts.query, keep_blank_values=True) == {"per_page": ["100"], "page": [str(number)]},
            "PAGINATION_QUERY_MISMATCH")


def next_page(record, base, number):
    value = header(record, "link")
    if not value:
        return False
    links = {}
    for part in value.split(","):
        match = re.fullmatch(r'\s*<([^>]+)>;\s*rel="([a-z]+)"\s*', part)
        require(match is not None and match[2] not in links, "INVALID_PAGINATION_LINK")
        url = urlsplit(match[1])
        require(url.scheme == "https" and url.netloc == "api.github.com"
                and not url.fragment and url.path == base, "PAGINATION_LINK_SCOPE")
        links[match[2]] = url
    if "next" not in links:
        return False
    url = links["next"]
    page_path(url.path + "?" + url.query, base, number + 1)
    return True


def github_pages(ctx, pages, base, collection=None):
    require(isinstance(pages, list) and 1 <= len(pages) <= 50, "PAGINATION_REQUIRED")
    values, totals, seen = [], set(), set()
    for number, record in enumerate(pages, 1):
        page_path(record["path"], base, number)
        body = json_bytes(ctx.response(record, "GET", record["path"]))
        if collection:
            require(isinstance(body, dict) and integer(body.get("total_count")), "PAGINATION_COUNT_REQUIRED")
            totals.add(body["total_count"])
            current = body.get(collection)
        else:
            current = body
        require(isinstance(current, list) and len(current) <= 100, "PAGINATION_BODY_INVALID")
        for item in current:
            require(isinstance(item, dict) and integer(item.get("id"), 1) and item["id"] not in seen,
                    "PAGINATION_DUPLICATE_OR_MISSING_ID")
            seen.add(item["id"])
        require(next_page(record, base, number) == (number < len(pages)), "PAGINATION_INCOMPLETE")
        values.extend(current)
    if collection:
        require(totals == {len(values)}, "PAGINATION_COUNT_MISMATCH")
    return values


def target_input(ctx, manifest):
    require(manifest.get("schema") == "p44-observations-v1", "MANIFEST_SCHEMA")
    target = ctx.document(manifest["target"])
    require(target.get("repository") == REPOSITORY, "TARGET_REPOSITORY")
    require(isinstance(target.get("branch"), str) and target["branch"].startswith("dev/p4-4/")
            and not re.search(r"[\s~^:?*\[\\]", target["branch"]), "TARGET_BRANCH")
    require(re.fullmatch(r"[0-9a-f]{40}", target.get("commitSha", "")), "TARGET_COMMIT")
    require(re.fullmatch(r"(?:0|[1-9][0-9]*)\.(?:0|[1-9][0-9]?)\.(?:0|[1-9][0-9]?)",
                         target.get("versionName", "")), "TARGET_VERSION")
    require(HASH.fullmatch(target.get("keySha256", "")), "TARGET_KEY_BINDING")
    descriptor = target.get("descriptor")
    require(isinstance(descriptor, dict)
            and descriptor.get("targetCommitSha") == target["commitSha"]
            and descriptor.get("targetVersionName") == target["versionName"], "TARGET_DESCRIPTOR_BINDING")
    require(digest(canonical(descriptor).encode()) == target.get("descriptorSha256"), "TARGET_DESCRIPTOR_DIGEST")
    return target


def run_object(ctx, capture, target, waiting=False):
    run_id = capture.get("run_id")
    require(integer(run_id, 1), "RUN_ID_INVALID")
    route = REPO_API + "/actions/runs/" + str(run_id)
    field = "waiting_run" if waiting else "final_run"
    if not waiting:
        route += "/attempts/1"
    value = json_bytes(ctx.response(capture[field], "GET", route))
    require(integer(value.get("id"), 1) and value["id"] == run_id
            and type(value.get("run_attempt")) is int and value["run_attempt"] == 1, "RUN_ATTEMPT_BINDING")
    require(value.get("head_sha") == target["commitSha"] and value.get("head_branch") == target["branch"],
            "RUN_SOURCE_BINDING")
    require(value.get("path") == WORKFLOW and value.get("event") == "workflow_dispatch"
            and value.get("repository", {}).get("full_name") == REPOSITORY, "RUN_WORKFLOW_BINDING")
    require(timestamp(value.get("created_at")) <= timestamp(value.get("updated_at")), "RUN_TIME_ORDER")
    if waiting:
        require(value.get("status") in {"waiting", "pending"} and value.get("conclusion") is None,
                "RUN_NOT_WAITING")
    else:
        require(value.get("status") == "completed", "RUN_NOT_COMPLETE")
    return value


def dispatch_input(ctx, capture, target):
    record = capture["dispatch"]
    route = REPO_API + "/actions/workflows/firmware-build.yml/dispatches"
    require(ctx.response(record, "POST", route, 204) == b"", "DISPATCH_RESPONSE_NOT_EMPTY")
    value = ctx.document(record["request"])
    require(isinstance(value, dict) and set(value) == {"ref", "inputs"}
            and value["ref"] == target["branch"], "DISPATCH_REF_BINDING")
    inputs = value["inputs"]
    require(isinstance(inputs, dict) and set(inputs) == {"publish", "rehearsal", "check_bindings",
            "approved_rehearsal_run_id", "version_name", "release_notes"}, "DISPATCH_INPUT_SET")
    require(dispatch_boolean(inputs["publish"], False) and dispatch_boolean(inputs["check_bindings"], False)
            and dispatch_boolean(inputs["rehearsal"], True) and inputs["approved_rehearsal_run_id"] == ""
            and inputs["version_name"] == target["versionName"] and isinstance(inputs["release_notes"], str),
            "DISPATCH_SCOPE")
    created = timestamp(ctx.document(capture["final_run"]["body"])["created_at"])
    require(timestamp(record["started"]) - timedelta(seconds=2) <= created
            <= timestamp(record["ended"]) + timedelta(seconds=120), "DISPATCH_RUN_TIME_BINDING")
    return value


def checked_jobs(ctx, capture, target, success):
    route = REPO_API + "/actions/runs/" + str(capture["run_id"]) + "/attempts/1/jobs"
    jobs = github_pages(ctx, capture["jobs_pages"], route, "jobs")
    by_name = {}
    for job in jobs:
        require(job.get("run_id") == capture["run_id"] and job.get("run_attempt") == 1
                and job.get("head_sha") == target["commitSha"] and job.get("head_branch") == target["branch"],
                "JOB_SOURCE_BINDING")
        require(job.get("status") == "completed" and job.get("name") not in by_name, "JOB_INCOMPLETE_OR_DUPLICATE")
        require(isinstance(job.get("steps"), list), "JOB_STEPS_MISSING")
        by_name[job["name"]] = job
    require(set(by_name) == {BUILD_JOB, DEVELOPMENT_JOB, BINDINGS_JOB, REHEARSAL_JOB, PRODUCTION_JOB},
            "JOB_SET_MISMATCH")
    for name in (BUILD_JOB, DEVELOPMENT_JOB):
        require(by_name[name].get("conclusion") == "success", "PREREQUISITE_JOB_FAILED")
    for name in (BINDINGS_JOB, PRODUCTION_JOB):
        require(by_name[name].get("conclusion") == "skipped"
                and all(step.get("conclusion") == "skipped" for step in by_name[name]["steps"]),
                "OUT_OF_SCOPE_JOB_EXECUTED")
    release = by_name[REHEARSAL_JOB]
    if not success:
        require(release.get("conclusion") in {"failure", "skipped"}
                and all(step.get("conclusion") == "skipped" for step in release["steps"]),
                "REJECTED_RELEASE_EXECUTED")
    else:
        require(release.get("conclusion") == "success", "REHEARSAL_JOB_FAILED")
        steps = {}
        for step in release["steps"]:
            require(step.get("name") not in steps and step.get("status") == "completed"
                    and step.get("conclusion") in {"success", "skipped"}, "RELEASE_STEP_FAILED_OR_DUPLICATE")
            steps[step["name"]] = step
        for name in REQUIRED_STEPS:
            require(name in steps and steps[name]["conclusion"] == "success", "REQUIRED_RELEASE_STEP_MISSING")
    return jobs


def approved_run(ctx, manifest, target):
    capture = manifest["run_b"]
    run = run_object(ctx, capture, target)
    require(run.get("conclusion") == "success", "APPROVED_RUN_NOT_SUCCESSFUL")
    checked_jobs(ctx, capture, target, True)
    dispatch = dispatch_input(ctx, capture, target)
    return run, dispatch


def approvals(ctx, manifest, target):
    captures = (manifest["run_a"], manifest["run_b"])
    require(captures[0].get("run_id") != captures[1].get("run_id"), "APPROVAL_REQUIRES_TWO_RUNS")
    finals, dispatches, actions = [], [], []
    for capture, state in zip(captures, ("rejected", "approved")):
        waiting = run_object(ctx, capture, target, True)
        final = run_object(ctx, capture, target)
        require(final.get("conclusion") == ("failure" if state == "rejected" else "success"),
                "REVIEW_TERMINAL_MISMATCH")
        require(waiting["created_at"] == final["created_at"], "WAITING_RUN_IDENTITY_CHANGED")
        require(timestamp(waiting["updated_at"]) <= timestamp(final["updated_at"]), "REVIEW_RUN_TIME_ORDER")
        require(timestamp(capture["waiting_run"]["ended"]) <= timestamp(capture["final_run"]["started"]),
                "REVIEW_CAPTURE_TIME_ORDER")
        route = REPO_API + "/actions/runs/" + str(capture["run_id"])
        pending = json_bytes(ctx.response(capture["pending_deployments"], "GET", route + "/pending_deployments"))
        require(isinstance(pending, list) and len(pending) == 1, "PENDING_ENVIRONMENT_MISSING")
        environment = pending[0].get("environment", {})
        require(environment.get("name") == ENVIRONMENT and integer(environment.get("id"), 1),
                "PENDING_ENVIRONMENT_BINDING")
        reviewers = pending[0].get("reviewers", [])
        require(any(item.get("type") == "User" and item.get("reviewer", {}).get("login") == REVIEWER
                    and item["reviewer"].get("id") == REVIEWER_ID for item in reviewers), "PENDING_REVIEWER_MISSING")
        require(timestamp(capture["pending_deployments"]["ended"]) <= timestamp(capture["final_run"]["started"]),
                "REVIEW_CAPTURE_TIME_ORDER")
        reviews = json_bytes(ctx.response(capture["reviews"], "GET", route + "/approvals"))
        require(timestamp(capture["reviews"]["started"]) >= timestamp(capture["pending_deployments"]["ended"]),
                "REVIEW_CAPTURE_TIME_ORDER")
        require(isinstance(reviews, list) and len(reviews) == 1, "REVIEW_EVENT_MISSING_OR_EXTRA")
        review = reviews[0]
        user = review.get("user", {})
        require(review.get("state") == state and user.get("login") == REVIEWER
                and user.get("id") == REVIEWER_ID and user.get("type") == "User", "REVIEW_ACTOR_OR_STATE")
        environments = review.get("environments")
        require(isinstance(environments, list) and len(environments) == 1
                and environments[0].get("name") == ENVIRONMENT
                and environments[0].get("id") == environment["id"], "REVIEW_ENVIRONMENT_BINDING")
        checked_jobs(ctx, capture, target, state == "approved")
        finals.append(final)
        dispatches.append(dispatch_input(ctx, capture, target))
        actions.append((capture["run_id"], state))
    require(canonical(dispatches[0]) == canonical(dispatches[1]), "DISPATCH_INPUTS_CHANGED")
    require(timestamp(finals[0]["updated_at"]) <= timestamp(finals[1]["created_at"]), "SECOND_RUN_BEFORE_REJECTION")
    attestation = ctx.document(manifest["reviewer_attestation"])
    require(attestation.get("schema") == "p44-reviewer-attestation-v1"
            and attestation.get("reviewer") == REVIEWER and attestation.get("reviewer_id") == REVIEWER_ID,
            "REVIEWER_ATTESTATION_IDENTITY")
    receipts = attestation.get("actions")
    require(isinstance(receipts, list) and len(receipts) == 2, "REVIEWER_ATTESTATION_MISSING")
    for receipt, expected in zip(receipts, actions):
        require((receipt.get("run_id"), receipt.get("state")) == expected and receipt.get("run_attempt") == 1
                and receipt.get("basis") in {"owner_response", "root_witness"}, "REVIEWER_ATTESTATION_BINDING")
        require(bool(ctx.read(receipt["evidence"]).strip()), "REVIEWER_ATTESTATION_EMPTY")
    return {"run_a": finals[0]["id"], "run_b": finals[1]["id"], "attempts": [1, 1],
            "review_states": ["rejected", "approved"], "rejected_release_unexecuted": True,
            "complete_approved_workflow": True, "reviewer_attestation_hash_bound": True,
            "human_action_origin_requires_independent_root_judgment": True}


def artifact_input(ctx, manifest, target):
    run, dispatch = approved_run(ctx, manifest, target)
    route = REPO_API + "/actions/runs/" + str(run["id"]) + "/artifacts"
    listing = github_pages(ctx, manifest["artifact_listing"], route, "artifacts")
    require(all(timestamp(page["started"]) >= timestamp(run["updated_at"])
                for page in manifest["artifact_listing"]), "ARTIFACT_CAPTURE_BEFORE_COMPLETE_RUN")
    name = "p41-rehearsal-" + str(run["id"]) + "-1"
    selected = [item for item in listing if item.get("name") == name]
    require(len(selected) == 1, "REHEARSAL_ARTIFACT_MISSING")
    item = selected[0]
    original_run = item.get("workflow_run", {})
    require(original_run.get("id") == run["id"] and original_run.get("head_sha") == target["commitSha"]
            and original_run.get("head_branch") == target["branch"], "ARTIFACT_RUN_BINDING")
    require(item.get("expired") is False and item.get("size_in_bytes") == manifest["artifact"]["size_bytes"]
            and item.get("digest") == "sha256:" + manifest["artifact"]["sha256"], "ARTIFACT_BYTE_BINDING")
    return ctx.file_path(manifest["artifact"]), run, dispatch


def new_chain(archive_path, target, run, dispatch):
    with zipfile.ZipFile(archive_path) as archive:
        members = archive.infolist()
        names = [item.filename for item in members]
        require(len(names) == len(set(names)) and len(names) <= 512, "ZIP_DUPLICATE_OR_TOO_MANY_MEMBERS")
        require(sum(item.file_size for item in members) <= MAX_FILE_BYTES, "ZIP_SIZE_BOUND")
        require(all(not name.startswith(("/", "\\")) and ".." not in name.split("/")
                    and "\\" not in name for name in names), "ZIP_MEMBER_PATH")
        read = lambda name: json_bytes(archive.read(name))
        metadata_bytes = archive.read("prepared/cloudflare-firmware-release-metadata.json")
        metadata = json_bytes(metadata_bytes)
        evidence = read("prepared/release-evidence.json")
        preparation = archive.read("prepared/verification.json")
        steps = read("prepared/release-steps.json")
        require(metadata.get("commitSha") == target["commitSha"] == evidence.get("commitSha")
                and metadata.get("versionName") == target["versionName"], "METADATA_SOURCE_BINDING")
        require(metadata.get("runId") == str(run["id"]) == evidence.get("canonicalRunId")
                == evidence.get("executionRunId") and evidence.get("executionAttempt") == "1", "METADATA_RUN_BINDING")
        require(metadata.get("releaseNotes") == dispatch["inputs"]["release_notes"], "RELEASE_NOTES_BINDING")
        require(metadata_bytes == (canonical(metadata) + "\n").encode(), "METADATA_NOT_CANONICAL")
        require(evidence.get("publicationProtocol") == PROTOCOL and evidence.get("mode") == "rehearsal"
                and evidence.get("github") is None, "PUBLICATION_PROTOCOL_MISMATCH")
        require(evidence.get("metadataSha256") == digest(metadata_bytes)
                and evidence.get("preparationSha256") == digest(preparation), "EVIDENCE_DIGEST_MISMATCH")
        preflight = evidence.get("preflight", {})
        require(preflight.get("ok") is True and preflight.get("schemaVersion") == 1
                and preflight.get("environment") == "staging"
                and preflight.get("metadataSha256") == digest(metadata_bytes)
                and preflight.get("unresolvedLegacyChannels") == 0
                and UUID.fullmatch(preflight.get("requestId", "")), "PREFLIGHT_BINDING_MISMATCH")
        code = metadata.get("versionCode")
        parts = [int(part) for part in target["versionName"].split(".")]
        require(integer(code) and code <= 4294967295 and code == parts[0] * 10000 + parts[1] * 100 + parts[2],
                "VERSION_CODE_BINDING")
        require(metadata.get("appId") == "trace" and metadata.get("deviceModel") == "e-track-at32f435"
                and metadata.get("schemaVersion") == 2 and metadata.get("isFormalRelease") is True
                and metadata.get("transport") == "ble" and metadata.get("targetHardware") == "AT32F435RGT7"
                and metadata.get("minAppVersionCode") == target.get("minAppVersionCode")
                and metadata.get("minProtocolVersion") == target.get("minProtocolVersion"), "METADATA_TARGET_SCOPE")
        for field in ("maxVersionCode", "legacyMaxVersionCode"):
            require(field in preflight and (preflight[field] is None or integer(preflight[field])), "PREFLIGHT_VERSION_INVALID")
        require((preflight["maxVersionCode"] is None or preflight["maxVersionCode"] <= code)
                and (preflight["legacyMaxVersionCode"] is None or preflight["legacyMaxVersionCode"] < code),
                "PREFLIGHT_MONOTONICITY")
        assets = metadata.get("assets")
        require(isinstance(assets, list) and [asset.get("kind") for asset in assets] == ["full", "patch", "recovery"],
                "THREE_ASSET_KINDS_REQUIRED")
        require(len({asset.get("fileName") for asset in assets}) == 3
                and len({asset.get("r2Key") for asset in assets}) == 3, "ASSET_IDENTITY_DUPLICATE")
        uploads = evidence.get("uploads")
        require(isinstance(uploads, list) and len(uploads) == 3, "UPLOAD_COUNT_MISMATCH")
        for asset, upload in zip(assets, uploads):
            name = asset.get("fileName")
            require(isinstance(name, str) and re.fullmatch(r"[a-zA-Z0-9.-]+", name), "ASSET_FILENAME_INVALID")
            require(asset.get("r2Key") == "trace/firmware/e-track-at32f435/" + str(code)
                    + "-" + metadata["releaseTag"] + "/" + name, "ASSET_R2_SCOPE")
            data = archive.read("prepared/" + name)
            require(integer(asset.get("sizeBytes"), 1) and len(data) == asset["sizeBytes"]
                    and digest(data) == asset.get("sha256") and asset.get("r2Verified") is True, "ASSET_BYTES_MISMATCH")
            require(upload.get("ok") is True and upload.get("status") in {"UPLOADED", "ALREADY_PRESENT"}
                    and all(upload.get(key) == asset.get(key) for key in ("fileName", "sha256", "sizeBytes", "r2Key")),
                    "UPLOAD_IDENTITY_MISMATCH")
        registration, replay = evidence.get("registration", {}), evidence.get("replay", {})
        for item in (registration, replay):
            require(item.get("ok") is True and item.get("state") == "ready" and item.get("assetsRegistered") == 3
                    and UUID.fullmatch(item.get("requestId", "")) and isinstance(item.get("releaseId"), str)
                    and bool(item["releaseId"]), "REGISTRATION_NOT_READY")
        require(registration.get("idempotent") is False and replay.get("idempotent") is True
                and registration["releaseId"] == replay["releaseId"], "REGISTRATION_IDEMPOTENCY")
        expected = [{"step": "preflight", **preflight}, *({"step": "r2-readback", **item} for item in uploads),
                    {"step": "register", **registration}, {"step": "idempotent-replay", **replay}]
        require(steps == expected, "RELEASE_EVENT_ORDER_OR_IDENTITY")
        return metadata, evidence


def original_byte_evaluator(ctx, archive_path, target_reference):
    require(sys.flags.optimize == 0, "OPTIMIZED_ASSERTIONS_FORBIDDEN")
    entry = guarded_path(ctx.root, LEGACY_INSPECT)
    guarded_path(ctx.root, RECOVERY_OWNER)
    guarded_path(ctx.root, "docs/ota-exec-notes/P4-1-bootstrap-baseline-2026-10-15/app-final.bin")
    spec = importlib.util.spec_from_file_location("p44_existing_byte_evaluator", entry)
    require(spec is not None and spec.loader is not None, "LEGACY_EVALUATOR_UNAVAILABLE")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    try:
        return module.rehearsal(archive_path.absolute(), ctx.file_path(target_reference).absolute())
    except Exception:
        raise EvidenceError("ORIGINAL_BYTE_EVALUATION_FAILED") from None


def rehearsal(ctx, manifest, target):
    path, run, dispatch = artifact_input(ctx, manifest, target)
    metadata, evidence = new_chain(path, target, run, dispatch)
    original = original_byte_evaluator(ctx, path, manifest["target"])
    require(original["metadata"] == metadata and original["remote_evidence"] == evidence, "BYTE_EVALUATOR_IDENTITY_MISMATCH")
    return {"publication_protocol": PROTOCOL, "run_id": run["id"], "run_attempt": 1,
            "commit_sha": target["commitSha"], "metadata_sha256": evidence["metadataSha256"],
            "asset_count": 3, "ready_and_idempotent": True, "original_byte_evaluator_reused": LEGACY_INSPECT,
            "artifact_sha256": manifest["artifact"]["sha256"], "metadata": metadata,
            "release_id": evidence["registration"]["releaseId"]}


def d1_rows(ctx, record, database, sql):
    route = "/accounts/[ACCOUNT]/d1/database/" + database + "/query"
    body = json_bytes(ctx.response(record, "POST", route))
    require(ctx.document(record["request"]) == {"sql": sql}, "D1_QUERY_BINDING")
    require(body.get("success") is True and isinstance(body.get("result"), list) and len(body["result"]) == 1,
            "D1_RESPONSE_FAILED")
    result = body["result"][0]
    require(result.get("success") is True and result.get("meta", {}).get("rows_written") == 0
            and result["meta"].get("changed_db") is False, "D1_UNEXPECTED_WRITE")
    require(isinstance(result.get("results"), list), "D1_ROWS_MISSING")
    return result["results"]


def database_snapshot(ctx, item, role):
    database = RESOURCES[role][0]
    schema = d1_rows(ctx, item["schema"], database, SCHEMA_SQL)
    require(all(isinstance(row, dict) and set(row) == {"name", "type", "sql"} for row in schema), "D1_SCHEMA_INVALID")
    require(all(not re.search(r"\bWITHOUT\s+ROWID\b", row["sql"] or "", re.IGNORECASE)
                for row in schema if row["type"] == "table"), "D1_WITHOUT_ROWID_UNSUPPORTED")
    table_names = [row["name"] for row in schema if row["type"] == "table"
                   and not row["name"].startswith(("sqlite_", "_cf_"))]
    require(len(table_names) == len(set(table_names))
            and all(re.fullmatch(r"[a-zA-Z_][a-zA-Z0-9_]*", name) for name in table_names), "D1_TABLE_NAME_INVALID")
    tables = item.get("tables")
    require(isinstance(tables, dict) and set(tables) == set(table_names), "D1_TABLE_SCOPE_INCOMPLETE")
    contents = {}
    for name in table_names:
        counted = d1_rows(ctx, tables[name]["count"], database, 'SELECT COUNT(*) AS count FROM "' + name + '"')
        require(len(counted) == 1 and set(counted[0]) == {"count"}
                and integer(counted[0]["count"]) and counted[0]["count"] <= 20000, "D1_COUNT_BOUND")
        count = counted[0]["count"]
        pages = tables[name].get("pages")
        require(isinstance(pages, list) and len(pages) <= (count + 7) // 8, "D1_PAGINATION_INCOMPLETE")
        rows = []
        for record in pages:
            request = ctx.document(record["request"])
            require(isinstance(request, dict) and set(request) == {"sql"} and isinstance(request["sql"], str),
                    "D1_QUERY_BINDING")
            query = request["sql"]
            match = re.fullmatch(r'SELECT \* FROM "' + re.escape(name)
                                 + r'" ORDER BY rowid LIMIT (8|500) OFFSET (0|[1-9][0-9]*)', query)
            require(match is not None, "D1_QUERY_BINDING")
            limit, offset = int(match[1]), int(match[2])
            require(offset == len(rows) and offset < count, "D1_PAGE_OFFSET_MISMATCH")
            page = d1_rows(ctx, record, database, query)
            require(len(page) == min(limit, count - offset), "D1_PAGE_COUNT_MISMATCH")
            rows.extend(page)
        require(len(rows) == count, "D1_PAGINATION_INCOMPLETE")
        contents[name] = rows
    return {"schema": schema, "tables": contents}


def xml_single(document, name, optional=False):
    nodes = document.findall("{*}" + name)
    require(len(nodes) == 1 or (optional and not nodes), "R2_XML_FIELD_MISSING_OR_DUPLICATE")
    return (nodes[0].text or "") if nodes else None


def bucket_snapshot(ctx, pages, role):
    require(isinstance(pages, list) and 1 <= len(pages) <= 20, "R2_PAGINATION_REQUIRED")
    bucket = RESOURCES[role][1]
    objects, continuation, used_tokens = {}, None, set()
    for index, record in enumerate(pages):
        url = urlsplit(record["path"])
        expected = {"list-type": ["2"], "max-keys": ["1000"]}
        if continuation is not None:
            expected["continuation-token"] = [continuation]
        require(not url.scheme and not url.netloc and not url.fragment and url.path == "/" + bucket + "/"
                and parse_qs(url.query, keep_blank_values=True) == expected, "R2_PAGINATION_REQUEST_BINDING")
        raw = ctx.response(record, "GET", record["path"])
        require(b"<!DOCTYPE" not in raw.upper() and b"<!ENTITY" not in raw.upper(), "R2_XML_DECLARATION")
        document = ET.fromstring(raw)
        require(document.tag.split("}")[-1] == "ListBucketResult"
                and xml_single(document, "Name") == bucket, "R2_BUCKET_BINDING")
        require(xml_single(document, "Prefix", True) in {None, ""}
                and xml_single(document, "Delimiter", True) in {None, ""}
                and not document.findall("{*}CommonPrefixes"), "R2_INVENTORY_FILTERED")
        echoed = xml_single(document, "ContinuationToken", True)
        require(echoed is None or echoed == continuation, "R2_CONTINUATION_ECHO")
        elements = document.findall("{*}Contents")
        require(xml_single(document, "KeyCount") == str(len(elements)) and len(elements) <= 1000
                and xml_single(document, "MaxKeys") == "1000", "R2_KEY_COUNT")
        for element in elements:
            values = {}
            for field in element:
                name = field.tag.split("}")[-1]
                require(name not in values and len(field) == 0, "R2_OBJECT_FIELD_INVALID")
                values[name] = field.text or ""
            require(all(name in values for name in ("Key", "Size", "ETag", "LastModified"))
                    and values["Key"] and values["Key"] not in objects
                    and re.fullmatch(r"0|[1-9][0-9]*", values["Size"]), "R2_OBJECT_IDENTITY_INVALID")
            objects[values["Key"]] = values
        truncated = xml_single(document, "IsTruncated")
        require(truncated in {"true", "false"} and (truncated == "true") == (index + 1 < len(pages)),
                "R2_PAGINATION_INCOMPLETE")
        continuation = xml_single(document, "NextContinuationToken", True)
        if truncated == "true":
            require(continuation and continuation not in used_tokens, "R2_CONTINUATION_INVALID")
            used_tokens.add(continuation)
        else:
            require(continuation in {None, ""}, "R2_TERMINAL_CONTINUATION")
    return objects


def release_snapshot(ctx, item):
    releases = github_pages(ctx, item["releases"], REPO_API + "/releases")
    references = item.get("assets")
    require(isinstance(references, dict) and set(references) == {str(release["id"]) for release in releases},
            "GITHUB_ASSET_SCOPE_INCOMPLETE")
    assets = {}
    for release in releases:
        identity = str(release["id"])
        assets[identity] = github_pages(ctx, references[identity], REPO_API + "/releases/" + identity + "/assets")
        require(isinstance(release.get("assets"), list)
                and collections.Counter(canonical(row) for row in release["assets"])
                == collections.Counter(canonical(row) for row in assets[identity]), "GITHUB_EMBEDDED_ASSET_MISMATCH")
    return {"releases": sorted(releases, key=lambda value: value["id"]),
            "assets": {key: sorted(rows, key=lambda value: value["id"]) for key, rows in assets.items()}}


def read_snapshot(ctx, snapshot):
    require(set(snapshot["databases"]) == set(RESOURCES) and set(snapshot["buckets"]) == set(RESOURCES),
            "SNAPSHOT_RESOURCE_SCOPE")
    return {"databases": {role: database_snapshot(ctx, snapshot["databases"][role], role) for role in RESOURCES},
            "buckets": {role: bucket_snapshot(ctx, snapshot["buckets"][role], role) for role in RESOURCES},
            "github": release_snapshot(ctx, snapshot["github"])}


def row_counter(rows):
    return collections.Counter(canonical(row) for row in rows)


def capture_window(value):
    if isinstance(value, dict):
        if {"method", "path", "body", "started", "ended"} <= set(value):
            return [(timestamp(value["started"]), timestamp(value["ended"]))]
        return [item for child in value.values() for item in capture_window(child)]
    if isinstance(value, list):
        return [item for child in value for item in capture_window(child)]
    return []


def state_delta(before, after, metadata, evidence):
    for role in RESOURCES:
        require(row_counter(before["databases"][role]["schema"]) == row_counter(after["databases"][role]["schema"]),
                "D1_SCHEMA_CHANGED")
        require(set(before["databases"][role]["tables"]) == set(after["databases"][role]["tables"]),
                "D1_TABLE_SET_CHANGED")
    for role in ("production", "protected"):
        old, new = before["databases"][role]["tables"], after["databases"][role]["tables"]
        require(all(row_counter(rows) == row_counter(new[name]) for name, rows in old.items()), "PROTECTED_D1_CHANGED")
        require(before["buckets"][role] == after["buckets"][role], "PROTECTED_R2_CHANGED")
    require(before["github"] == after["github"], "GITHUB_RELEASES_CHANGED")
    old, new = before["databases"]["staging"]["tables"], after["databases"]["staging"]["tables"]
    allowed = {"firmware_releases", "firmware_release_assets", "audit_logs"}
    require(allowed <= set(old) and "firmware_channels" in old, "STAGING_REQUIRED_TABLE_MISSING")
    additions = {}
    for name, rows in old.items():
        previous, current = row_counter(rows), row_counter(new[name])
        require(not (previous - current), "STAGING_EXISTING_ROW_CHANGED")
        if name not in allowed:
            require(previous == current, "STAGING_OUT_OF_SCOPE_CHANGE")
        else:
            additions[name] = [json_bytes(value) for value in (current - previous).elements()]
    require(len(additions["firmware_releases"]) == 1 and len(additions["firmware_release_assets"]) == 3
            and len(additions["audit_logs"]) == 1, "STAGING_ADDITION_COUNT")
    release_id = evidence["registration"]["releaseId"]
    release = additions["firmware_releases"][0]
    require(release.get("id") == release_id and release.get("state") == "ready"
            and release.get("version_code") == metadata["versionCode"]
            and json_bytes(release.get("registration_json", "")) == metadata, "STAGING_RELEASE_IDENTITY")
    release_fields = {"app_id": "appId", "device_model": "deviceModel", "version_name": "versionName",
                      "release_tag": "releaseTag", "commit_sha": "commitSha", "run_id": "runId",
                      "release_notes": "releaseNotes", "target_image_sha256": "targetImageSha256",
                      "hardware_rev": "hardwareRevision", "layout_id": "layoutId", "min_boot_version": "minBootVersion",
                      "min_protocol_version": "minProtocolVersion", "target_hardware": "targetHardware",
                      "transport": "transport", "min_app_version_code": "minAppVersionCode"}
    require(all(release.get(field) == metadata[expected] for field, expected in release_fields.items())
            and release.get("archived") == 0, "STAGING_RELEASE_COLUMNS_MISMATCH")
    for asset in metadata["assets"]:
        matches = [row for row in additions["firmware_release_assets"] if row.get("file_name") == asset["fileName"]]
        require(len(matches) == 1 and matches[0].get("release_id") == release_id, "STAGING_ASSET_ROW_IDENTITY")
        mapping = {"kind": "kind", "sha256": "sha256", "size_bytes": "sizeBytes", "r2_key": "r2Key",
                   "github_url": "githubUrl", "base_image_sha256": "baseImageSha256", "base_vcode": "baseVersionCode"}
        require(all(matches[0].get(field) == asset[expected] for field, expected in mapping.items())
                and matches[0].get("r2_state") == "available", "STAGING_ASSET_ROW_IDENTITY")
    audit = additions["audit_logs"][0]
    require(audit.get("action") == "register_firmware_release" and audit.get("target_type") == "firmware_release"
            and audit.get("target_id") == release_id and audit.get("actor") == "github-actions"
            and audit.get("actor_type") == "ci" and audit.get("app_id") == metadata["appId"]
            and audit.get("request_id") == evidence["registration"]["requestId"]
            and json_bytes(audit.get("after_json", "")) == {"releaseId": release_id, "state": "ready", "assetsRegistered": 3},
            "STAGING_AUDIT_IDENTITY")
    old_objects, new_objects = before["buckets"]["staging"], after["buckets"]["staging"]
    require(all(new_objects.get(key) == value for key, value in old_objects.items()), "STAGING_EXISTING_R2_CHANGED")
    require(set(new_objects) - set(old_objects) == {asset["r2Key"] for asset in metadata["assets"]}, "STAGING_R2_ADDITION_SCOPE")
    for asset in metadata["assets"]:
        require(new_objects[asset["r2Key"]]["Size"] == str(asset["sizeBytes"]), "STAGING_R2_SIZE_MISMATCH")


def states(ctx, manifest, target):
    path, run, dispatch = artifact_input(ctx, manifest, target)
    metadata, evidence = new_chain(path, target, run, dispatch)
    before = read_snapshot(ctx, manifest["snapshots"]["before"])
    after = read_snapshot(ctx, manifest["snapshots"]["after"])
    before_times = capture_window(manifest["snapshots"]["before"])
    after_times = capture_window(manifest["snapshots"]["after"])
    require(before_times and max(end for _, end in before_times) <= timestamp(run["created_at"]),
            "BEFORE_SNAPSHOT_AFTER_RUN_STARTED")
    require(after_times and min(start for start, _ in after_times) >= timestamp(run["updated_at"]),
            "AFTER_SNAPSHOT_BEFORE_RUN_COMPLETED")
    state_delta(before, after, metadata, evidence)
    readbacks = manifest.get("readbacks")
    require(isinstance(readbacks, dict) and set(readbacks) == {asset["r2Key"] for asset in metadata["assets"]},
            "R2_READBACK_SCOPE")
    for asset in metadata["assets"]:
        route = "/" + RESOURCES["staging"][1] + "/" + quote(asset["r2Key"], safe="/")
        raw = ctx.response(readbacks[asset["r2Key"]], "GET", route)
        require(timestamp(readbacks[asset["r2Key"]]["started"]) >= timestamp(run["updated_at"]),
                "R2_READBACK_BEFORE_RUN_COMPLETED")
        require(len(raw) == asset["sizeBytes"] and digest(raw) == asset["sha256"], "R2_READBACK_BYTES_MISMATCH")
    return {"production_d1_r2_unchanged": True, "protected_trace_d1_r2_unchanged": True,
            "github_releases_assets_unchanged": True, "staging_existing_rows_channels_unchanged": True,
            "staging_added_releases": 1, "staging_added_assets": 3, "staging_added_audit_rows": 1,
            "staging_added_r2_keys": 3, "independent_r2_byte_readbacks": 3,
            "snapshot_scope": "Bounded before/after observations, not continuous or transactional monitoring"}


def write_result(root, output, result):
    output = guarded_path(root, output)
    require(not output.exists(), "OUTPUT_ALREADY_EXISTS")
    output.parent.mkdir(parents=True, exist_ok=True)
    output = guarded_path(root, output)
    data = (json.dumps(result, indent=2, ensure_ascii=True, allow_nan=False) + "\n").encode()
    with output.open("xb") as stream:
        stream.write(data)
    return digest(data)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("mode", choices=("rehearsal", "approvals", "states"))
    parser.add_argument("--repo-root", required=True, type=Path)
    parser.add_argument("--input", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args(argv)
    result = {"schema": "p44-offline-evaluation-v1", "mode": args.mode,
              "started": datetime.now(timezone.utc).isoformat(), "platform_actions": 0}
    try:
        root = Path(os.path.abspath(args.repo_root))
        require(root == Path(__file__).absolute().parents[3] == Path.cwd().absolute(), "WORKTREE_ROOT_MISMATCH")
        output = guarded_path(root, args.output)
        require(not output.exists(), "OUTPUT_ALREADY_EXISTS")
        require(sys.flags.optimize == 0, "OPTIMIZED_ASSERTIONS_FORBIDDEN")
        ctx = Context(root, args.input)
    except (EvidenceError, OSError, ValueError) as error:
        code = str(error) if isinstance(error, EvidenceError) else "PREFLIGHT_FAILED"
        print(json.dumps({"ok": False, "error_code": code, "output_written": False}))
        return 1
    try:
        require(ctx.manifest.stat().st_size <= 16 * 1024 * 1024, "MANIFEST_SIZE_BOUND")
        manifest_bytes = ctx.manifest.read_bytes()
        manifest = json_bytes(manifest_bytes)
        target = target_input(ctx, manifest)
        result["manifest_sha256"] = digest(manifest_bytes)
        result["observed"] = {"rehearsal": rehearsal, "approvals": approvals, "states": states}[args.mode](ctx, manifest, target)
        result["ok"] = True
    except Exception as error:
        result["ok"] = False
        result["error_code"] = str(error) if isinstance(error, EvidenceError) else "EVIDENCE_INVALID"
    result["files_verified"] = len(ctx.checked_files)
    result["ended"] = datetime.now(timezone.utc).isoformat()
    try:
        sha256 = write_result(root, output, result)
    except (EvidenceError, OSError, ValueError):
        print(json.dumps({"ok": False, "error_code": "OUTPUT_WRITE_FAILED", "output_written": False}))
        return 1
    print(json.dumps({"ok": result["ok"], "mode": args.mode, "error_code": result.get("error_code"),
                      "output": output.relative_to(root).as_posix(), "sha256": sha256}))
    return 0 if result["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
