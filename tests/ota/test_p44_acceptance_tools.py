"""Offline positive/negative P4-4 adapter tests; all fixtures stay in --output-dir."""

import argparse
import copy
from datetime import datetime, timezone
import importlib.util
import io
import json
import os
from pathlib import Path
import sqlite3
import subprocess
import sys
import unittest
from unittest import mock
from urllib.parse import quote
import xml.etree.ElementTree as ET
import zipfile

sys.dont_write_bytecode = True
ROOT = Path(__file__).absolute().parents[2]
ENTRY = ROOT / "Tools/acceptance/p44/inspect.py"
SPEC = importlib.util.spec_from_file_location("p44_acceptance_tools", ENTRY)
p44 = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(p44)
OUTPUT = None


def raw(value):
    return (p44.canonical(value) + "\n").encode()


def run_fixture(run_id, success=True, waiting=False):
    hour = "09" if run_id == 101 else "10"
    return {"id": run_id, "run_attempt": 1, "head_sha": "a" * 40,
            "head_branch": "dev/p4-4/config-integration-20261018", "path": p44.WORKFLOW,
            "event": "workflow_dispatch", "repository": {"full_name": p44.REPOSITORY},
            "created_at": "2026-10-19T" + hour + ":00:00Z",
            "updated_at": "2026-10-19T" + hour + (":05:00Z" if waiting else ":10:00Z"),
            "status": "waiting" if waiting else "completed",
            "conclusion": None if waiting else ("success" if success else "failure")}


def target_fixture():
    descriptor = {"targetCommitSha": "a" * 40, "targetVersionName": "3.2.9",
                  "provenanceKind": "inaugural-bootstrap-v1", "isFormalRelease": False,
                  "versionName": "3.2.7", "versionCode": 30207, "imageSha256": "b" * 64}
    return {"repository": p44.REPOSITORY, "branch": "dev/p4-4/config-integration-20261018",
            "commitSha": "a" * 40, "versionName": "3.2.9", "descriptor": descriptor,
            "descriptorSha256": p44.digest(p44.canonical(descriptor).encode()), "keySha256": "c" * 64,
            "minAppVersionCode": 0, "minProtocolVersion": 1}


def jobs_fixture(run_id, success):
    jobs = []
    names = [p44.BUILD_JOB, p44.DEVELOPMENT_JOB, p44.BINDINGS_JOB, p44.REHEARSAL_JOB, p44.PRODUCTION_JOB]
    for number, name in enumerate(names):
        conclusion = "success"
        if name in (p44.BINDINGS_JOB, p44.PRODUCTION_JOB):
            conclusion = "skipped"
        if name == p44.REHEARSAL_JOB and not success:
            conclusion = "failure"
        steps = []
        if name == p44.REHEARSAL_JOB and success:
            steps = [{"name": value, "status": "completed", "conclusion": "success"} for value in p44.REQUIRED_STEPS]
        jobs.append({"id": run_id * 10 + number, "run_id": run_id, "run_attempt": 1,
                     "head_sha": "a" * 40, "head_branch": "dev/p4-4/config-integration-20261018",
                     "name": name, "status": "completed", "conclusion": conclusion, "steps": steps})
    return jobs


def dispatch_fixture():
    return {"ref": "dev/p4-4/config-integration-20261018", "inputs": {
        "publish": "false", "rehearsal": "true", "check_bindings": "false",
        "approved_rehearsal_run_id": "", "version_name": "3.2.9", "release_notes": "P4-4 bounded staging candidate"}}


def chain_fixture():
    files = {}
    assets = []
    tag = "mcu-e-track-at32f435-v3.2.9"
    for kind, name in [("full", "e-track-at32f435-v3.2.9-full.etu"),
                       ("patch", "e-track-at32f435-v3.2.7-to-v3.2.9-patch.etu"),
                       ("recovery", "recovery-v3.2.9.bin")]:
        data = ("independently-bound-" + kind).encode()
        files["prepared/" + name] = data
        assets.append({"kind": kind, "fileName": name, "sha256": p44.digest(data), "sizeBytes": len(data),
                       "r2Key": "trace/firmware/e-track-at32f435/30209-" + tag + "/" + name,
                       "r2Verified": True, "baseVersionCode": 30207 if kind == "patch" else 0,
                       "baseImageSha256": "b" * 64 if kind == "patch" else "",
                       "githubUrl": "https://github.com/" + p44.REPOSITORY + "/releases/download/" + tag + "/" + name})
    metadata = {"schemaVersion": 2, "appId": "trace", "deviceModel": "e-track-at32f435",
                "commitSha": "a" * 40, "versionName": "3.2.9", "versionCode": 30209, "runId": "102",
                "releaseTag": tag, "releaseNotes": dispatch_fixture()["inputs"]["release_notes"],
                "targetImageSha256": "d" * 64, "hardwareRevision": 1, "layoutId": 1, "minBootVersion": 1,
                "minProtocolVersion": 1, "minAppVersionCode": 0, "targetHardware": "AT32F435RGT7",
                "transport": "ble", "isFormalRelease": True, "assets": assets}
    files["prepared/verification.json"] = raw({"scope": "unit-fixture-not-a-real-firmware-build"})
    preflight = {"ok": True, "schemaVersion": 1, "environment": "staging",
                 "requestId": "10000000-0000-4000-8000-000000000000", "metadataSha256": p44.digest(raw(metadata)),
                 "maxVersionCode": 30208, "legacyMaxVersionCode": None, "unresolvedLegacyChannels": 0}
    registration = {"ok": True, "requestId": "20000000-0000-4000-8000-000000000000", "releaseId": "fw_new",
                    "state": "ready", "idempotent": False, "assetsRegistered": 3}
    replay = {**registration, "requestId": "30000000-0000-4000-8000-000000000000", "idempotent": True}
    uploads = [{**{name: asset[name] for name in ("fileName", "sha256", "sizeBytes", "r2Key")},
                "ok": True, "status": "UPLOADED"} for asset in assets]
    evidence = {"publicationProtocol": p44.PROTOCOL, "preflight": preflight, "mode": "rehearsal",
                "commitSha": "a" * 40, "canonicalRunId": "102", "executionRunId": "102", "executionAttempt": "1",
                "metadataSha256": p44.digest(raw(metadata)),
                "preparationSha256": p44.digest(files["prepared/verification.json"]),
                "github": None, "uploads": uploads, "registration": registration, "replay": replay}
    return files, metadata, evidence


def object_fixture(key, size="11"):
    return {"Key": key, "Size": size, "ETag": '"fixture-etag"', "LastModified": "2026-10-19T10:01:00Z",
            "StorageClass": "STANDARD"}


def state_fixture(metadata, evidence):
    tables = {name: [] for name in ("firmware_releases", "firmware_release_assets", "audit_logs", "firmware_channels", "apps")}
    tables["firmware_channels"] = [{"id": "old_channel", "current_release_id": "old_release", "revision": 3}]
    tables["apps"] = [{"id": "trace"}]
    schema = [{"name": name, "type": "table", "sql": 'CREATE TABLE "' + name + '" (id TEXT PRIMARY KEY)'} for name in tables]
    before = {"databases": {role: {"schema": copy.deepcopy(schema), "tables": copy.deepcopy(tables)} for role in p44.RESOURCES},
              "buckets": {role: {"old-object": object_fixture("old-object")} for role in p44.RESOURCES},
              "github": {"releases": [], "assets": {}}}
    after = copy.deepcopy(before)
    new = after["databases"]["staging"]["tables"]
    release = {"id": "fw_new", "state": "ready", "version_code": metadata["versionCode"], "archived": 0,
               "registration_json": p44.canonical(metadata)}
    fields = {"app_id": "appId", "device_model": "deviceModel", "version_name": "versionName",
              "release_tag": "releaseTag", "commit_sha": "commitSha", "run_id": "runId", "release_notes": "releaseNotes",
              "target_image_sha256": "targetImageSha256", "hardware_rev": "hardwareRevision", "layout_id": "layoutId",
              "min_boot_version": "minBootVersion", "min_protocol_version": "minProtocolVersion", "target_hardware": "targetHardware",
              "transport": "transport", "min_app_version_code": "minAppVersionCode"}
    release.update({field: metadata[name] for field, name in fields.items()})
    new["firmware_releases"] = [release]
    for asset in metadata["assets"]:
        fields = {"kind": "kind", "file_name": "fileName", "sha256": "sha256", "size_bytes": "sizeBytes", "r2_key": "r2Key",
                  "github_url": "githubUrl", "base_image_sha256": "baseImageSha256", "base_vcode": "baseVersionCode"}
        new["firmware_release_assets"].append({"id": "asset_" + asset["kind"], "release_id": "fw_new", "r2_state": "available",
                                               **{field: asset[name] for field, name in fields.items()}})
        after["buckets"]["staging"][asset["r2Key"]] = object_fixture(asset["r2Key"], str(asset["sizeBytes"]))
    new["audit_logs"] = [{"id": "audit-new", "action": "register_firmware_release", "target_type": "firmware_release",
                          "target_id": "fw_new", "actor": "github-actions", "actor_type": "ci", "app_id": "trace",
                          "request_id": evidence["registration"]["requestId"],
                          "after_json": p44.canonical({"releaseId": "fw_new", "state": "ready", "assetsRegistered": 3})}]
    return before, after


class P44ToolsTests(unittest.TestCase):
    def setUp(self):
        self.directory = p44.guarded_path(ROOT, OUTPUT / self._testMethodName)
        self.directory.mkdir()
        self.sequence = 0
        self.ctx = p44.Context(ROOT, self.directory / "manifest.json")
        self.target = target_fixture()

    def save(self, data):
        self.sequence += 1
        data = data if isinstance(data, bytes) else raw(data)
        path = p44.guarded_path(ROOT, self.directory / (str(self.sequence) + ".original"))
        with path.open("xb") as stream:
            stream.write(data)
        return {"path": str(path), "size_bytes": len(data), "sha256": p44.digest(data)}

    def http(self, value, path, method="GET", request=None, status=200, started="2026-10-19T09:11:00Z",
             ended="2026-10-19T09:11:01Z", headers=None):
        record = {"method": method, "path": path, "status": status, "started": started, "ended": ended,
                  "response_headers": headers or {}, "body": self.save(value)}
        if request is not None:
            record["request"] = self.save(request)
        return record

    def changed_body(self, record, update):
        value = self.ctx.document(record["body"])
        update(value)
        record["body"] = self.save(value)

    def collection(self, values, base, name=None):
        body = {"total_count": len(values), name: values} if name else values
        return [self.http(body, base + "?per_page=100&page=1")]

    def manifest(self):
        manifest = {"schema": "p44-observations-v1", "target": self.save(self.target)}
        actions = []
        for label, run_id, approved in [("run_a", 101, False), ("run_b", 102, True)]:
            route = p44.REPO_API + "/actions/runs/" + str(run_id)
            final = run_fixture(run_id, approved)
            hour = "09" if run_id == 101 else "10"
            pending = [{"environment": {"id": 1234, "name": p44.ENVIRONMENT},
                        "reviewers": [{"type": "User", "reviewer": {"login": p44.REVIEWER, "id": p44.REVIEWER_ID}}]}]
            reviews = [{"user": {"login": p44.REVIEWER, "id": p44.REVIEWER_ID, "type": "User"},
                        "state": "approved" if approved else "rejected",
                        "comment": "Independent reviewer action", "environments": [{"id": 1234, "name": p44.ENVIRONMENT}]}]
            capture = {"run_id": run_id,
                       "dispatch": self.http(b"", p44.REPO_API + "/actions/workflows/firmware-build.yml/dispatches",
                                             "POST", dispatch_fixture(), 204,
                                             started="2026-10-19T" + hour + ":00:00Z", ended="2026-10-19T" + hour + ":00:01Z"),
                       "waiting_run": self.http(run_fixture(run_id, approved, True), route,
                                                started="2026-10-19T" + hour + ":05:01Z", ended="2026-10-19T" + hour + ":05:02Z"),
                       "pending_deployments": self.http(pending, route + "/pending_deployments",
                                                        started="2026-10-19T" + hour + ":05:03Z", ended="2026-10-19T" + hour + ":05:04Z"),
                       "final_run": self.http(final, route + "/attempts/1",
                                              started="2026-10-19T" + hour + ":11:00Z", ended="2026-10-19T" + hour + ":11:01Z"),
                       "reviews": self.http(reviews, route + "/approvals",
                                            started="2026-10-19T" + hour + ":11:00Z", ended="2026-10-19T" + hour + ":11:01Z"),
                       "jobs_pages": self.collection(jobs_fixture(run_id, approved), route + "/attempts/1/jobs", "jobs")}
            manifest[label] = capture
            actions.append({"run_id": run_id, "run_attempt": 1, "state": "approved" if approved else "rejected",
                            "basis": "root_witness", "evidence": self.save(b"Unit-test attestation, not a real approval.\n")})
        manifest["reviewer_attestation"] = self.save({"schema": "p44-reviewer-attestation-v1", "reviewer": p44.REVIEWER,
                                                     "reviewer_id": p44.REVIEWER_ID, "actions": actions})
        return manifest

    def archive(self, files, metadata, evidence, steps=None):
        contents = dict(files)
        contents["prepared/cloudflare-firmware-release-metadata.json"] = raw(metadata)
        contents["prepared/release-evidence.json"] = raw(evidence)
        if steps is None:
            steps = [{"step": "preflight", **evidence.get("preflight", {})},
                     *({"step": "r2-readback", **item} for item in evidence["uploads"]),
                     {"step": "register", **evidence["registration"]}, {"step": "idempotent-replay", **evidence["replay"]}]
        contents["prepared/release-steps.json"] = raw(steps)
        data = io.BytesIO()
        with zipfile.ZipFile(data, "w") as archive:
            for name, value in contents.items():
                archive.writestr(name, value)
        reference = self.save(data.getvalue())
        return Path(reference["path"]), reference

    def artifact_manifest(self):
        manifest = self.manifest()
        files, metadata, evidence = chain_fixture()
        _, reference = self.archive(files, metadata, evidence)
        manifest["artifact"] = reference
        artifact = {"id": 401, "name": "p41-rehearsal-102-1", "workflow_run": {
                    "id": 102, "head_sha": self.target["commitSha"], "head_branch": self.target["branch"]},
                    "expired": False, "size_in_bytes": reference["size_bytes"], "digest": "sha256:" + reference["sha256"]}
        manifest["artifact_listing"] = self.collection([artifact], p44.REPO_API + "/actions/runs/102/artifacts", "artifacts")
        manifest["artifact_listing"][0].update(started="2026-10-19T10:11:00Z", ended="2026-10-19T10:11:01Z")
        return manifest

    def assert_bad(self, code, action):
        with self.assertRaisesRegex(p44.EvidenceError, "^" + code + "$"):
            action()

    def test_approval_happy_path(self):
        result = p44.approvals(self.ctx, self.manifest(), self.target)
        self.assertEqual(result["review_states"], ["rejected", "approved"])
        self.assertTrue(result["human_action_origin_requires_independent_root_judgment"])

    def test_cancel_is_not_rejection(self):
        manifest = self.manifest()
        self.changed_body(manifest["run_a"]["final_run"], lambda value: value.update(conclusion="cancelled"))
        self.assert_bad("REVIEW_TERMINAL_MISMATCH", lambda: p44.approvals(self.ctx, manifest, self.target))

    def test_wrong_review_actor(self):
        manifest = self.manifest()
        self.changed_body(manifest["run_a"]["reviews"], lambda value: value[0]["user"].update(login="different-user"))
        self.assert_bad("REVIEW_ACTOR_OR_STATE", lambda: p44.approvals(self.ctx, manifest, self.target))

    def test_bot_cannot_be_required_reviewer(self):
        manifest = self.manifest()
        self.changed_body(manifest["run_b"]["reviews"], lambda value: value[0]["user"].update(type="Bot"))
        self.assert_bad("REVIEW_ACTOR_OR_STATE", lambda: p44.approvals(self.ctx, manifest, self.target))

    def test_wrong_run_id(self):
        manifest = self.manifest()
        self.changed_body(manifest["run_a"]["final_run"], lambda value: value.update(id=103))
        self.assert_bad("RUN_ATTEMPT_BINDING", lambda: p44.approvals(self.ctx, manifest, self.target))

    def test_wrong_attempt(self):
        manifest = self.manifest()
        self.changed_body(manifest["run_b"]["final_run"], lambda value: value.update(run_attempt=2))
        self.assert_bad("RUN_ATTEMPT_BINDING", lambda: p44.approvals(self.ctx, manifest, self.target))

    def test_boolean_attempt_is_rejected(self):
        manifest = self.manifest()
        self.changed_body(manifest["run_b"]["final_run"], lambda value: value.update(run_attempt=True))
        self.assert_bad("RUN_ATTEMPT_BINDING", lambda: p44.approvals(self.ctx, manifest, self.target))

    def test_wrong_source(self):
        manifest = self.manifest()
        self.changed_body(manifest["run_b"]["final_run"], lambda value: value.update(head_sha="b" * 40))
        self.assert_bad("RUN_SOURCE_BINDING", lambda: p44.approvals(self.ctx, manifest, self.target))

    def test_wrong_job_attempt(self):
        manifest = self.manifest()
        self.changed_body(manifest["run_b"]["jobs_pages"][0], lambda value: value["jobs"][0].update(run_attempt=2))
        self.assert_bad("JOB_SOURCE_BINDING", lambda: p44.approvals(self.ctx, manifest, self.target))

    def test_successful_steps_do_not_replace_complete_run(self):
        manifest = self.artifact_manifest()
        self.changed_body(manifest["run_b"]["final_run"], lambda value: value.update(status="in_progress"))
        self.assert_bad("RUN_NOT_COMPLETE", lambda: p44.artifact_input(self.ctx, manifest, self.target))

    def test_rejected_release_step_executed(self):
        manifest = self.manifest()
        self.changed_body(manifest["run_a"]["jobs_pages"][0], lambda value: value["jobs"][3]["steps"].append(
            {"name": p44.REQUIRED_STEPS[2], "conclusion": "success", "status": "completed"}))
        self.assert_bad("REJECTED_RELEASE_EXECUTED", lambda: p44.approvals(self.ctx, manifest, self.target))

    def test_missing_required_pipeline_step(self):
        manifest = self.manifest()
        self.changed_body(manifest["run_b"]["jobs_pages"][0], lambda value: value["jobs"][3]["steps"].pop(2))
        self.assert_bad("REQUIRED_RELEASE_STEP_MISSING", lambda: p44.approvals(self.ctx, manifest, self.target))

    def test_production_job_never_runs(self):
        manifest = self.manifest()
        self.changed_body(manifest["run_b"]["jobs_pages"][0], lambda value: value["jobs"][4].update(conclusion="success"))
        self.assert_bad("OUT_OF_SCOPE_JOB_EXECUTED", lambda: p44.approvals(self.ctx, manifest, self.target))

    def test_dispatch_inputs_cannot_change_between_runs(self):
        manifest = self.manifest()
        value = dispatch_fixture()
        value["inputs"]["release_notes"] = "different reviewed input"
        manifest["run_b"]["dispatch"]["request"] = self.save(value)
        self.assert_bad("DISPATCH_INPUTS_CHANGED", lambda: p44.approvals(self.ctx, manifest, self.target))

    def test_numeric_dispatch_boolean_rejected(self):
        manifest = self.manifest()
        value = dispatch_fixture()
        value["inputs"]["rehearsal"] = 1
        manifest["run_b"]["dispatch"]["request"] = self.save(value)
        self.assert_bad("DISPATCH_SCOPE", lambda: p44.approvals(self.ctx, manifest, self.target))

    def test_reuse_same_rejected_run_forbidden(self):
        manifest = self.manifest()
        manifest["run_b"]["run_id"] = 101
        self.assert_bad("APPROVAL_REQUIRES_TWO_RUNS", lambda: p44.approvals(self.ctx, manifest, self.target))

    def test_second_run_before_rejection_forbidden(self):
        manifest = self.manifest()
        for field in ("waiting_run", "final_run"):
            self.changed_body(manifest["run_b"][field], lambda value: value.update(created_at="2026-10-19T09:00:00Z"))
        manifest["run_b"]["dispatch"].update(started="2026-10-19T09:00:00Z", ended="2026-10-19T09:00:01Z")
        self.assert_bad("SECOND_RUN_BEFORE_REJECTION", lambda: p44.approvals(self.ctx, manifest, self.target))

    def test_missing_review_event_not_replaced_by_comment(self):
        manifest = self.manifest()
        self.changed_body(manifest["run_a"]["reviews"], lambda value: value[0].update(state="pending", comment="rejected approved PASS"))
        self.assert_bad("REVIEW_ACTOR_OR_STATE", lambda: p44.approvals(self.ctx, manifest, self.target))

    def test_wrong_review_environment_id(self):
        manifest = self.manifest()
        self.changed_body(manifest["run_a"]["reviews"], lambda value: value[0]["environments"][0].update(id=9999))
        self.assert_bad("REVIEW_ENVIRONMENT_BINDING", lambda: p44.approvals(self.ctx, manifest, self.target))

    def test_empty_reviewer_attestation_fails(self):
        manifest = self.manifest()
        value = self.ctx.document(manifest["reviewer_attestation"])
        value["actions"][0]["evidence"] = self.save(b" \n")
        manifest["reviewer_attestation"] = self.save(value)
        self.assert_bad("REVIEWER_ATTESTATION_EMPTY", lambda: p44.approvals(self.ctx, manifest, self.target))

    def test_jobs_total_count_detects_omission(self):
        manifest = self.manifest()
        self.changed_body(manifest["run_b"]["jobs_pages"][0], lambda value: value.update(total_count=6))
        self.assert_bad("PAGINATION_COUNT_MISMATCH", lambda: p44.approvals(self.ctx, manifest, self.target))

    def test_artifact_original_binding(self):
        manifest = self.artifact_manifest()
        path, run, _ = p44.artifact_input(self.ctx, manifest, self.target)
        self.assertTrue(path.is_absolute())
        self.assertEqual(run["id"], 102)

    def test_artifact_wrong_source(self):
        manifest = self.artifact_manifest()
        self.changed_body(manifest["artifact_listing"][0], lambda value: value["artifacts"][0]["workflow_run"].update(head_sha="b" * 40))
        self.assert_bad("ARTIFACT_RUN_BINDING", lambda: p44.artifact_input(self.ctx, manifest, self.target))

    def test_artifact_digest_mismatch(self):
        manifest = self.artifact_manifest()
        self.changed_body(manifest["artifact_listing"][0], lambda value: value["artifacts"][0].update(digest="sha256:" + "0" * 64))
        self.assert_bad("ARTIFACT_BYTE_BINDING", lambda: p44.artifact_input(self.ctx, manifest, self.target))

    def test_new_chain_success(self):
        files, metadata, evidence = chain_fixture()
        path, _ = self.archive(files, metadata, evidence)
        actual = p44.new_chain(path, self.target, run_fixture(102), dispatch_fixture())
        self.assertEqual(actual, (metadata, evidence))

    def chain_bad(self, code, mutate):
        files, metadata, evidence = chain_fixture()
        mutate(files, metadata, evidence)
        path, _ = self.archive(files, metadata, evidence)
        self.assert_bad(code, lambda: p44.new_chain(path, self.target, run_fixture(102), dispatch_fixture()))

    def test_legacy_chain_protocol_rejected(self):
        self.chain_bad("PUBLICATION_PROTOCOL_MISMATCH", lambda _, __, evidence: evidence.pop("publicationProtocol"))

    def test_missing_preflight_rejected(self):
        self.chain_bad("PREFLIGHT_BINDING_MISMATCH", lambda _, __, evidence: evidence.pop("preflight"))

    def test_preflight_wrong_digest_rejected(self):
        self.chain_bad("PREFLIGHT_BINDING_MISMATCH", lambda _, __, evidence: evidence["preflight"].update(metadataSha256="0" * 64))

    def test_preflight_wrong_environment_rejected(self):
        self.chain_bad("PREFLIGHT_BINDING_MISMATCH", lambda _, __, evidence: evidence["preflight"].update(environment="prod"))

    def test_preflight_stale_candidate_rejected(self):
        self.chain_bad("PREFLIGHT_MONOTONICITY", lambda _, __, evidence: evidence["preflight"].update(maxVersionCode=40000))

    def test_preflight_unresolved_channel_rejected(self):
        self.chain_bad("PREFLIGHT_BINDING_MISMATCH", lambda _, __, evidence: evidence["preflight"].update(unresolvedLegacyChannels=1))

    def test_preflight_missing_version_field_rejected(self):
        self.chain_bad("PREFLIGHT_VERSION_INVALID", lambda _, __, evidence: evidence["preflight"].pop("legacyMaxVersionCode"))

    def test_wrong_canonical_run_rejected(self):
        self.chain_bad("METADATA_RUN_BINDING", lambda _, __, evidence: evidence.update(canonicalRunId="101"))

    def test_wrong_release_evidence_source_rejected(self):
        self.chain_bad("METADATA_SOURCE_BINDING", lambda _, __, evidence: evidence.update(commitSha="b" * 40))

    def test_incorrect_asset_bytes_rejected(self):
        def mutate(files, metadata, _):
            files["prepared/" + metadata["assets"][0]["fileName"]] = b"incorrect"
        self.chain_bad("ASSET_BYTES_MISMATCH", mutate)

    def test_replay_different_release_rejected(self):
        self.chain_bad("REGISTRATION_IDEMPOTENCY", lambda _, __, evidence: evidence["replay"].update(releaseId="wrong"))

    def test_ready_missing_rejected(self):
        self.chain_bad("REGISTRATION_NOT_READY", lambda _, __, evidence: evidence["registration"].update(state="draft"))

    def test_second_nonidempotent_registration_rejected(self):
        self.chain_bad("REGISTRATION_IDEMPOTENCY", lambda _, __, evidence: evidence["replay"].update(idempotent=False))

    def test_event_order_is_not_summary_only(self):
        files, metadata, evidence = chain_fixture()
        path, _ = self.archive(files, metadata, evidence, [])
        self.assert_bad("RELEASE_EVENT_ORDER_OR_IDENTITY", lambda: p44.new_chain(path, self.target, run_fixture(102), dispatch_fixture()))

    def test_existing_byte_evaluator_is_reused_not_campaign(self):
        manifest = self.artifact_manifest()
        files, metadata, evidence = chain_fixture()
        expected = {"metadata": metadata, "remote_evidence": evidence}
        with mock.patch.object(p44, "original_byte_evaluator", return_value=expected) as original:
            result = p44.rehearsal(self.ctx, manifest, self.target)
        self.assertEqual(original.call_count, 1)
        self.assertEqual(result["original_byte_evaluator_reused"], p44.LEGACY_INSPECT)
        self.assertTrue(original.call_args.args[1].is_absolute())

    def test_state_delta_success(self):
        _, metadata, evidence = chain_fixture()
        before, after = state_fixture(metadata, evidence)
        p44.state_delta(before, after, metadata, evidence)

    def state_bad(self, code, mutate):
        _, metadata, evidence = chain_fixture()
        before, after = state_fixture(metadata, evidence)
        mutate(after)
        self.assert_bad(code, lambda: p44.state_delta(before, after, metadata, evidence))

    def test_production_d1_difference(self):
        self.state_bad("PROTECTED_D1_CHANGED", lambda after: after["databases"]["production"]["tables"]["apps"].append({"id": "other"}))

    def test_production_r2_difference(self):
        self.state_bad("PROTECTED_R2_CHANGED", lambda after: after["buckets"]["production"].update(new=object_fixture("new")))

    def test_protected_trace_d1_difference(self):
        self.state_bad("PROTECTED_D1_CHANGED", lambda after: after["databases"]["protected"]["tables"]["apps"].clear())

    def test_schema_difference(self):
        self.state_bad("D1_SCHEMA_CHANGED", lambda after: after["databases"]["production"]["schema"][0].update(sql="changed"))

    def test_github_release_difference(self):
        self.state_bad("GITHUB_RELEASES_CHANGED", lambda after: after["github"]["releases"].append({"id": 10}))

    def test_staging_channel_cannot_change(self):
        self.state_bad("STAGING_EXISTING_ROW_CHANGED", lambda after: after["databases"]["staging"]["tables"]["firmware_channels"][0].update(revision=4))

    def test_staging_unrelated_row_cannot_be_added(self):
        self.state_bad("STAGING_OUT_OF_SCOPE_CHANGE", lambda after: after["databases"]["staging"]["tables"]["apps"].append({"id": "other"}))

    def test_staging_extra_r2_key_rejected(self):
        self.state_bad("STAGING_R2_ADDITION_SCOPE", lambda after: after["buckets"]["staging"].update(extra=object_fixture("extra")))

    def test_staging_duplicate_registration_audit_rejected(self):
        self.state_bad("STAGING_ADDITION_COUNT", lambda after: after["databases"]["staging"]["tables"]["audit_logs"].append({"id": "second"}))

    def test_staging_wrong_audit_target_rejected(self):
        self.state_bad("STAGING_AUDIT_IDENTITY", lambda after: after["databases"]["staging"]["tables"]["audit_logs"][0].update(target_id="other"))

    def test_staging_wrong_audit_request_rejected(self):
        self.state_bad("STAGING_AUDIT_IDENTITY", lambda after: after["databases"]["staging"]["tables"]["audit_logs"][0].update(request_id="wrong"))

    def test_staging_registration_json_does_not_hide_wrong_columns(self):
        self.state_bad("STAGING_RELEASE_COLUMNS_MISMATCH", lambda after: after["databases"]["staging"]["tables"]["firmware_releases"][0].update(commit_sha="b" * 40))

    def test_staging_asset_base_identity_rejected(self):
        self.state_bad("STAGING_ASSET_ROW_IDENTITY", lambda after: after["databases"]["staging"]["tables"]["firmware_release_assets"][1].update(base_vcode=30206))

    def r2_page(self, role="staging", keys=("key",), truncated=False, token=None, requested=None):
        bucket = p44.RESOURCES[role][1]
        document = ET.Element("ListBucketResult", xmlns="http://s3.amazonaws.com/doc/2006-03-01/")
        ET.SubElement(document, "Name").text = bucket
        for key in keys:
            element = ET.SubElement(document, "Contents")
            for field, value in object_fixture(key).items():
                ET.SubElement(element, field).text = value
        ET.SubElement(document, "IsTruncated").text = str(truncated).lower()
        ET.SubElement(document, "MaxKeys").text = "1000"
        ET.SubElement(document, "KeyCount").text = str(len(keys))
        if token is not None:
            ET.SubElement(document, "NextContinuationToken").text = token
        path = "/" + bucket + "/?list-type=2&max-keys=1000"
        if requested is not None:
            path += "&continuation-token=" + quote(requested, safe="")
        return self.http(ET.tostring(document), path)

    def test_r2_real_xml_pagination(self):
        pages = [self.r2_page(keys=("one",), truncated=True, token="next+/="),
                 self.r2_page(keys=("two",), requested="next+/=")]
        self.assertEqual(set(p44.bucket_snapshot(self.ctx, pages, "staging")), {"one", "two"})

    def test_r2_missing_terminal_page(self):
        self.assert_bad("R2_PAGINATION_INCOMPLETE", lambda: p44.bucket_snapshot(
            self.ctx, [self.r2_page(truncated=True, token="next")], "staging"))

    def test_r2_wrong_requested_cursor(self):
        pages = [self.r2_page(truncated=True, token="next"), self.r2_page(keys=("other",), requested="wrong")]
        self.assert_bad("R2_PAGINATION_REQUEST_BINDING", lambda: p44.bucket_snapshot(self.ctx, pages, "staging"))

    def test_r2_wrong_bucket_scope(self):
        self.assert_bad("R2_PAGINATION_REQUEST_BINDING", lambda: p44.bucket_snapshot(self.ctx, [self.r2_page("protected")], "staging"))

    def test_r2_duplicate_keys(self):
        self.assert_bad("R2_OBJECT_IDENTITY_INVALID", lambda: p44.bucket_snapshot(self.ctx, [self.r2_page(keys=("same", "same"))], "staging"))

    def test_r2_filtered_listing(self):
        page = self.r2_page()
        data = self.ctx.read(page["body"]).replace(b"</ListBucketResult>", b"<Prefix>narrow/</Prefix></ListBucketResult>")
        page["body"] = self.save(data)
        self.assert_bad("R2_INVENTORY_FILTERED", lambda: p44.bucket_snapshot(self.ctx, [page], "staging"))

    def test_github_pagination_link_chain(self):
        base = p44.REPO_API + "/releases"
        first = self.http([{"id": 1}], base + "?per_page=100&page=1", headers={
            "Link": '<https://api.github.com' + base + '?page=2&per_page=100>; rel="next"'})
        second = self.http([{"id": 2}], base + "?per_page=100&page=2")
        self.assertEqual(p44.github_pages(self.ctx, [first, second], base), [{"id": 1}, {"id": 2}])

    def test_github_missing_page(self):
        base = p44.REPO_API + "/releases"
        first = self.http([{"id": 1}], base + "?per_page=100&page=1", headers={
            "link": '<https://api.github.com' + base + '?page=2&per_page=100>; rel="next"'})
        self.assert_bad("PAGINATION_INCOMPLETE", lambda: p44.github_pages(self.ctx, [first], base))

    def test_release_requires_separate_assets_listing(self):
        item = {"releases": self.collection([{"id": 1, "assets": []}], p44.REPO_API + "/releases"), "assets": {}}
        self.assert_bad("GITHUB_ASSET_SCOPE_INCOMPLETE", lambda: p44.release_snapshot(self.ctx, item))

    def d1(self, rows, sql, role="staging", written=0):
        body = {"success": True, "result": [{"success": True, "results": rows,
                "meta": {"rows_written": written, "changed_db": False}}]}
        return self.http(body, "/accounts/[ACCOUNT]/d1/database/" + p44.RESOURCES[role][0] + "/query", "POST", {"sql": sql})

    def test_d1_raw_count_and_pages(self):
        schema = [{"name": "apps", "type": "table", "sql": "CREATE TABLE apps(id TEXT)"}]
        rows = [{"id": str(index)} for index in range(501)]
        item = {"schema": self.d1(schema, p44.SCHEMA_SQL), "tables": {"apps": {
            "count": self.d1([{"count": 501}], 'SELECT COUNT(*) AS count FROM "apps"'),
            "pages": [self.d1(rows[:500], 'SELECT * FROM "apps" ORDER BY rowid LIMIT 500 OFFSET 0'),
                      self.d1(rows[500:], 'SELECT * FROM "apps" ORDER BY rowid LIMIT 500 OFFSET 500')]}}}
        self.assertEqual(p44.database_snapshot(self.ctx, item, "staging")["tables"]["apps"], rows)
        item["tables"]["apps"]["pages"].pop()
        self.assert_bad("D1_PAGINATION_INCOMPLETE", lambda: p44.database_snapshot(self.ctx, item, "staging"))

    def test_d1_wrong_query_is_not_raw_evidence(self):
        record = self.d1([], "SELECT id FROM apps")
        self.assert_bad("D1_QUERY_BINDING", lambda: p44.d1_rows(self.ctx, record, p44.RESOURCES["staging"][0], p44.SCHEMA_SQL))

    def test_d1_reported_write_is_rejected(self):
        record = self.d1([], p44.SCHEMA_SQL, written=1)
        self.assert_bad("D1_UNEXPECTED_WRITE", lambda: p44.d1_rows(self.ctx, record, p44.RESOURCES["staging"][0], p44.SCHEMA_SQL))

    def d1_page_fixture(self, count, specifications):
        schema = [{"name": "apps", "type": "table", "sql": "CREATE TABLE apps(id TEXT)"}]
        pages = []
        for limit, offset, length in specifications:
            query = 'SELECT * FROM "apps" ORDER BY rowid LIMIT ' + str(limit) + ' OFFSET ' + str(offset)
            pages.append(self.d1([{"id": value} for value in range(offset, offset + length)], query))
        return {"schema": self.d1(schema, p44.SCHEMA_SQL), "tables": {"apps": {
            "count": self.d1([{"count": count}], 'SELECT COUNT(*) AS count FROM "apps"'), "pages": pages}}}

    def test_eight_row_pages_cover_original_count_in_order(self):
        item = self.d1_page_fixture(17, [(8, 0, 8), (8, 8, 8), (8, 16, 1)])
        result = p44.database_snapshot(self.ctx, item, "staging")
        self.assertEqual(result["tables"]["apps"], [{"id": value} for value in range(17)])

    def test_mixed_old_500_and_new_eight_pages_preserve_order(self):
        item = self.d1_page_fixture(510, [(500, 0, 500), (8, 500, 8), (8, 508, 2)])
        result = p44.database_snapshot(self.ctx, item, "staging")
        self.assertEqual(result["tables"]["apps"], [{"id": value} for value in range(510)])

    def test_eight_row_page_missing_final_page(self):
        item = self.d1_page_fixture(17, [(8, 0, 8), (8, 8, 8)])
        self.assert_bad("D1_PAGINATION_INCOMPLETE", lambda: p44.database_snapshot(self.ctx, item, "staging"))

    def test_eight_row_page_gap_rejected(self):
        item = self.d1_page_fixture(17, [(8, 0, 8), (8, 16, 1)])
        self.assert_bad("D1_PAGE_OFFSET_MISMATCH", lambda: p44.database_snapshot(self.ctx, item, "staging"))

    def test_eight_row_duplicate_offset_rejected(self):
        item = self.d1_page_fixture(17, [(8, 0, 8), (8, 0, 8), (8, 16, 1)])
        self.assert_bad("D1_PAGE_OFFSET_MISMATCH", lambda: p44.database_snapshot(self.ctx, item, "staging"))

    def test_large_body_cannot_claim_eight_row_limit(self):
        item = self.d1_page_fixture(501, [(8, 0, 500), (8, 500, 1)])
        self.assert_bad("D1_PAGE_COUNT_MISMATCH", lambda: p44.database_snapshot(self.ctx, item, "staging"))

    def test_unapproved_page_width_rejected(self):
        item = self.d1_page_fixture(17, [(16, 0, 16), (8, 16, 1)])
        self.assert_bad("D1_QUERY_BINDING", lambda: p44.database_snapshot(self.ctx, item, "staging"))

    def test_capture_consumes_real_bundle_predecessor_plan(self):
        specification = importlib.util.spec_from_file_location("p44_real_predecessor_plan", ROOT / "Tools/acceptance/p44/bundle.py")
        bundle = importlib.util.module_from_spec(specification)
        specification.loader.exec_module(bundle)
        planned, manifest = bundle.predecessor_plan()
        packet = {"scope": "bundle.predecessor_plan", "manifest": manifest,
                  "originals": [{"path": target.relative_to(bundle.DATA).as_posix(), "source": str(source)} for source, target in planned]}
        self.save(packet)
        env = os.environ.copy()
        for name in ("TEMP", "TMP", "TMPDIR", "HOME", "USERPROFILE", "APPDATA", "LOCALAPPDATA",
                     "XDG_CONFIG_HOME", "XDG_CACHE_HOME", "XDG_DATA_HOME"):
            env[name] = str(self.directory)
        for name in ("NODE_OPTIONS", "NODE_V8_COVERAGE", "NODE_COMPILE_CACHE", "SSLKEYLOGFILE"):
            env.pop(name, None)
        result = subprocess.run(["node", str(ROOT / "tests/ota/test_p44_capture.cjs"), "--predecessor-stdin"],
                                input=raw(packet), cwd=ROOT, env=env, capture_output=True, timeout=60, check=False)
        self.save(result.stdout)
        self.save(result.stderr)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        observed = json.loads(result.stdout)
        self.assertEqual(observed["source"], "bundle.predecessor_plan")
        self.assertEqual((observed["complete_old_reads"], observed["incomplete_old_reads"]), (31, 1))
        self.assertTrue(observed["uppercase_originals_accepted"] and observed["wrong_digest_rejected"]
                        and observed["wrong_matrix_digest_rejected"])
        self.assertEqual(observed["network_requests"], 0)

    def test_real_migrations_support_rowid_selects_and_audit_fields(self):
        database = sqlite3.connect(":memory:")
        migrations = ROOT / "app/bluetooth_flutter_Trace/cloudflare/update-service/migrations"
        try:
            for path in sorted(migrations.glob("*.sql")):
                database.executescript(path.read_text(encoding="utf-8"))
            schema = database.execute(p44.SCHEMA_SQL).fetchall()
            tables = [row[0] for row in schema if row[1] == "table" and not row[0].startswith(("sqlite_", "_cf_"))]
            self.assertTrue({"firmware_releases", "firmware_release_assets", "firmware_channels", "audit_logs"} <= set(tables))
            for table in tables:
                database.execute('SELECT * FROM "' + table + '" ORDER BY rowid LIMIT 500 OFFSET 0').fetchall()
            fields = {row[1] for row in database.execute("PRAGMA table_info(audit_logs)")}
            self.assertTrue({"action", "target_type", "target_id", "request_id", "after_json", "actor", "actor_type"} <= fields)
        finally:
            database.close()

    def test_file_hash_mismatch(self):
        reference = self.save(b"original")
        reference["sha256"] = "0" * 64
        self.assert_bad("FILE_DIGEST_MISMATCH", lambda: self.ctx.read(reference))

    def test_partial_http_200_valid_json_is_incomplete(self):
        route = p44.REPO_API + "/actions/runs/102/attempts/1"
        record = self.http(run_fixture(102), route)
        original = self.ctx.read(record["body"])
        self.assertEqual(p44.json_bytes(original)["status"], "completed")
        record.update(completed=False, error_code="TRANSPORT_STREAM_FAILED")
        self.assert_bad("HTTP_TRANSPORT_INCOMPLETE", lambda: self.ctx.response(record, "GET", route))
        self.assertEqual(self.ctx.read(record["body"]), original)

    def test_complete_and_legacy_http_records_remain_accepted(self):
        route = p44.REPO_API + "/actions/runs/102/attempts/1"
        record = self.http(run_fixture(102), route)
        original = self.ctx.read(record["body"])
        self.assertEqual(self.ctx.response(record, "GET", route), original)
        record["completed"] = True
        self.assertEqual(self.ctx.response(record, "GET", route), original)

    def test_nonboolean_http_completion_fails_closed(self):
        route = p44.REPO_API + "/actions/runs/102/attempts/1"
        record = self.http(run_fixture(102), route)
        for value in (None, 0, 1, "false", "true"):
            with self.subTest(completed=value):
                record["completed"] = value
                self.assert_bad("HTTP_TRANSPORT_INCOMPLETE", lambda: self.ctx.response(record, "GET", route))

    def test_approval_rejects_interrupted_valid_review_response(self):
        manifest = self.manifest()
        manifest["run_a"]["reviews"].update(completed=False, error_code="TRANSPORT_STREAM_FAILED")
        self.assert_bad("HTTP_TRANSPORT_INCOMPLETE", lambda: p44.approvals(self.ctx, manifest, self.target))

    def test_duplicate_json_keys_rejected(self):
        self.assert_bad("DUPLICATE_JSON_KEY", lambda: p44.json_bytes(b'{"ok":false,"ok":true}'))

    def test_outside_and_sibling_paths_rejected(self):
        self.assert_bad("PATH_OUTSIDE_WORKTREE", lambda: p44.guarded_path(ROOT, ROOT.parent / (ROOT.name + "-other") / "file"))
        self.assert_bad("PATH_OUTSIDE_WORKTREE", lambda: p44.guarded_path(ROOT, "../escape"))

    def test_reparse_parent_rejected_without_writing(self):
        original = Path.lstat
        target = self.directory / "output.json"
        def information(path):
            if path == self.directory:
                return type("Info", (), {"st_mode": 0, "st_file_attributes": 0x400})()
            return original(path)
        with mock.patch.object(Path, "lstat", information):
            self.assert_bad("REPARSE_PATH_REJECTED", lambda: p44.guarded_path(ROOT, target))
        self.assertFalse(target.exists())

    def test_output_is_exclusive(self):
        output = self.directory / "result.json"
        p44.write_result(ROOT, output, {"ok": False})
        saved = output.read_bytes()
        self.assert_bad("OUTPUT_ALREADY_EXISTS", lambda: p44.write_result(ROOT, output, {"ok": True}))
        self.assertEqual(output.read_bytes(), saved)

    def test_cli_failure_is_redacted_and_originals_preserved(self):
        manifest = p44.guarded_path(ROOT, self.directory / "input.json")
        with manifest.open("xb") as stream:
            stream.write(b'{"SAMPLE_NOT_REAL_SECRET":"must-not-echo",')
        output = self.directory / "result.json"
        env = os.environ.copy()
        for name in ("TEMP", "TMP", "TMPDIR", "HOME", "USERPROFILE", "APPDATA", "LOCALAPPDATA", "XDG_CACHE_HOME"):
            env[name] = str(self.directory)
        result = subprocess.run([sys.executable, "-I", "-S", "-B", str(ENTRY), "approvals", "--repo-root", str(ROOT),
                                 "--input", str(manifest), "--output", str(output)], cwd=ROOT, env=env,
                                capture_output=True, timeout=20, check=False)
        self.assertEqual(result.returncode, 1)
        self.assertEqual(json.loads(output.read_bytes())["error_code"], "INVALID_JSON")
        self.assertNotIn(b"must-not-echo", result.stdout + result.stderr + output.read_bytes())
        self.assertTrue(manifest.read_bytes().endswith(b","))

    def test_cli_help_has_no_platform_action_commands(self):
        result = subprocess.run([sys.executable, "-I", "-S", "-B", str(ENTRY), "--help"], cwd=ROOT,
                                capture_output=True, timeout=20, check=False)
        self.assertEqual(result.returncode, 0)
        self.assertIn(b"{rehearsal,approvals,states}", result.stdout)
        self.assertNotIn(b"{dispatch", result.stdout)

    def test_dispatch_time_binds_original_run(self):
        manifest = self.manifest()
        manifest["run_b"]["dispatch"].update(started="2026-10-18T10:00:00Z", ended="2026-10-18T10:00:01Z")
        self.assert_bad("DISPATCH_RUN_TIME_BINDING", lambda: p44.approvals(self.ctx, manifest, self.target))

    def test_reviews_cannot_precede_waiting_observation(self):
        manifest = self.manifest()
        manifest["run_b"]["reviews"].update(started="2026-10-19T09:00:00Z", ended="2026-10-19T09:00:01Z")
        self.assert_bad("REVIEW_CAPTURE_TIME_ORDER", lambda: p44.approvals(self.ctx, manifest, self.target))

    def test_cli_approvals_positive(self):
        manifest = self.save(self.manifest())
        output = self.directory / "approval-result.json"
        result = subprocess.run([sys.executable, "-I", "-S", "-B", str(ENTRY), "approvals", "--repo-root", str(ROOT),
                                 "--input", manifest["path"], "--output", str(output)], cwd=ROOT,
                                capture_output=True, timeout=20, check=False)
        self.assertEqual(result.returncode, 0, result.stdout)
        self.assertEqual(json.loads(output.read_bytes())["observed"]["review_states"], ["rejected", "approved"])

    def snapshot_manifest(self, snapshot, before):
        actual = {"databases": {}, "buckets": {}, "github": {"releases": self.collection([], p44.REPO_API + "/releases"), "assets": {}}}
        for role in p44.RESOURCES:
            database = snapshot["databases"][role]
            tables = {}
            for name, rows in database["tables"].items():
                tables[name] = {"count": self.d1([{"count": len(rows)}], 'SELECT COUNT(*) AS count FROM "' + name + '"', role),
                                "pages": [] if not rows else [self.d1(rows, 'SELECT * FROM "' + name + '" ORDER BY rowid LIMIT 500 OFFSET 0', role)]}
            actual["databases"][role] = {"schema": self.d1(database["schema"], p44.SCHEMA_SQL, role), "tables": tables}
            page = self.r2_page(role, keys=())
            document = ET.fromstring(self.ctx.read(page["body"]))
            document.find("{*}KeyCount").text = str(len(snapshot["buckets"][role]))
            for values in snapshot["buckets"][role].values():
                element = ET.SubElement(document, "Contents")
                for field, value in values.items():
                    ET.SubElement(element, field).text = value
            page["body"] = self.save(ET.tostring(document))
            actual["buckets"][role] = [page]
        def times(value):
            if isinstance(value, dict):
                if "method" in value:
                    hour = "08" if before else "11"
                    value.update(started="2026-10-19T" + hour + ":00:00Z", ended="2026-10-19T" + hour + ":00:01Z")
                else:
                    for child in value.values():
                        times(child)
            elif isinstance(value, list):
                for child in value:
                    times(child)
        times(actual)
        return actual

    def complete_states(self):
        manifest = self.artifact_manifest()
        files, metadata, evidence = chain_fixture()
        before, after = state_fixture(metadata, evidence)
        manifest["snapshots"] = {"before": self.snapshot_manifest(before, True), "after": self.snapshot_manifest(after, False)}
        manifest["readbacks"] = {}
        for asset in metadata["assets"]:
            route = "/" + p44.RESOURCES["staging"][1] + "/" + quote(asset["r2Key"], safe="/")
            manifest["readbacks"][asset["r2Key"]] = self.http(files["prepared/" + asset["fileName"]], route,
                started="2026-10-19T11:00:00Z", ended="2026-10-19T11:00:01Z")
        return manifest

    def test_complete_states_raw_capture_success(self):
        manifest = self.complete_states()
        result = p44.states(self.ctx, manifest, self.target)
        self.assertEqual(result["independent_r2_byte_readbacks"], 3)

    def test_before_snapshot_cannot_be_taken_after_run(self):
        manifest = self.complete_states()
        record = manifest["snapshots"]["before"]["buckets"]["production"][0]
        record.update(started="2026-10-19T11:00:00Z", ended="2026-10-19T11:00:01Z")
        self.assert_bad("BEFORE_SNAPSHOT_AFTER_RUN_STARTED", lambda: p44.states(self.ctx, manifest, self.target))

    def test_after_snapshot_cannot_be_copied_from_before_run(self):
        manifest = self.complete_states()
        record = manifest["snapshots"]["after"]["buckets"]["production"][0]
        record.update(started="2026-10-19T08:00:00Z", ended="2026-10-19T08:00:01Z")
        self.assert_bad("AFTER_SNAPSHOT_BEFORE_RUN_COMPLETED", lambda: p44.states(self.ctx, manifest, self.target))

    def test_independent_readback_wrong_bytes_rejected(self):
        manifest = self.complete_states()
        manifest["readbacks"][next(iter(manifest["readbacks"]))]["body"] = self.save(b"wrong independent original")
        self.assert_bad("R2_READBACK_BYTES_MISMATCH", lambda: p44.states(self.ctx, manifest, self.target))


def main():
    global OUTPUT
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-dir", type=Path, required=True)
    args = parser.parse_args()
    OUTPUT = p44.guarded_path(ROOT, args.output_dir)
    if OUTPUT.exists():
        raise SystemExit("Use a new output label; earlier test evidence is immutable")
    allowed = ROOT / ".cache/p44-runner-tests-20261019"
    try:
        OUTPUT.relative_to(allowed)
    except ValueError:
        raise SystemExit("Output must be in the authorized project-local test directory") from None
    OUTPUT.mkdir(parents=True)
    p44.guarded_path(ROOT, OUTPUT)
    suite = unittest.defaultTestLoader.loadTestsFromTestCase(P44ToolsTests)
    stream = io.StringIO()
    started = datetime.now(timezone.utc).isoformat()
    result = unittest.TextTestRunner(stream=stream, verbosity=2).run(suite)
    output = stream.getvalue()
    with p44.guarded_path(ROOT, OUTPUT / "unittest-original.txt").open("x", encoding="utf-8", newline="\n") as handle:
        handle.write(output)
    print(output, end="")
    p44.write_result(ROOT, OUTPUT / "result.json", {"scope": "OFFLINE_DEVELOPMENT_SELFTEST_ONLY", "started": started,
                     "ended": datetime.now(timezone.utc).isoformat(), "tests_run": result.testsRun,
                     "failures": len(result.failures), "errors": len(result.errors), "skipped": len(result.skipped),
                     "ok": result.wasSuccessful(), "platform_actions": 0, "device_actions": 0})
    return 0 if result.wasSuccessful() else 1


if __name__ == "__main__":
    raise SystemExit(main())
