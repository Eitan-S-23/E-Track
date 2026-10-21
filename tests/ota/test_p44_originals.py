"""Offline P4-4 original evaluation regressions; fixtures never contact a service."""

from __future__ import annotations

import contextlib
import copy
import importlib.util
import io
import json
import os
from pathlib import Path
import shutil
import stat
import sys
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch

sys.dont_write_bytecode = True
ROOT = Path(__file__).absolute().parents[2]
SPEC = importlib.util.spec_from_file_location("p44_origins", ROOT / "Tools/acceptance/p44/origins.py")
origins = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(origins)
TEST_ROOT = ROOT / ".cache/p44-original-tests-20261019"
HISTORY_ROOT = ROOT / "docs/ota-exec-notes/P4-4-s3-remediation-2026-10-19"
CONFIG_ROOT = ROOT / "docs/ota-exec-notes/P4-4-credential-handoff-2026-10-19-v2"
DEPLOYMENT_ROOT = ROOT / "docs/ota-exec-notes/P4-4-root-review-2026-10-19"


def read_files(directory, names):
    return {name: origins.guarded_path(ROOT, directory / name).read_bytes() for name in names}


def changed_json(files, name, change):
    result = dict(files)
    value = json.loads(result[name])
    change(value)
    result[name] = (json.dumps(value, ensure_ascii=True, indent=2) + "\n").encode("utf-8")
    return result


class ConfigurationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.files = read_files(CONFIG_ROOT, origins.CONFIGURATION_FILES)

    def reject(self, change, code, filename="credential-readback-01.json"):
        with self.assertRaisesRegex(origins.EvidenceError, "^" + code + "$"):
            origins.configuration(changed_json(self.files, filename, change))

    def policy(self, change, code):
        self.reject(lambda value: change(value["observations"]["productionPolicy"]["response"]["result"]), code)

    def test_actual_configuration_originals(self):
        result = origins.configuration(self.files)
        self.assertEqual(result["successful_gets"], 15)
        self.assertEqual(result["original_collector_assertions"], 28)
        self.assertEqual(result["provider_expiration"], {"production": None, "rehearsal": None})
        self.assertEqual(result["acl"]["targets"], 7)
        self.assertEqual(result["existing_sigv4_listobjects_http_200"], 2)
        self.assertIn("not PUT", " ".join(result["limitations"]))
        self.assertNotEqual(result["source_management_id_sha256"], result["old_management_id_sha256"])

    def test_summary_pass_does_not_hide_added_management_permission(self):
        self.policy(lambda token: token["policies"][0]["permission_groups"].append(
            {"id": "synthetic", "name": "Account API Tokens Write"}), "TOKEN_PERMISSION_SCOPE")

    def test_missing_item_permission_rejected(self):
        self.policy(lambda token: token["policies"][0]["permission_groups"].pop(), "TOKEN_PERMISSION_SCOPE")

    def test_duplicate_item_permission_rejected(self):
        self.policy(lambda token: token["policies"][0].update(permission_groups=[
            token["policies"][0]["permission_groups"][0]] * 2), "TOKEN_PERMISSION_SCOPE")

    def test_second_policy_rejected(self):
        self.policy(lambda token: token["policies"].append(copy.deepcopy(token["policies"][0])), "TOKEN_POLICY_COUNT")

    def test_deny_effect_rejected(self):
        self.policy(lambda token: token["policies"][0].update(effect="deny"), "TOKEN_POLICY_EFFECT_OR_FIELDS")

    def test_missing_jurisdiction_rejected(self):
        self.policy(lambda token: token["policies"][0].update(resources={
            "com.cloudflare.edge.r2.bucket.[REDACTED]_e-track-firmware-production-releases": "*"}), "TOKEN_RESOURCE_SCOPE")

    def test_wrong_resource_value_rejected(self):
        self.policy(lambda token: token["policies"][0].update(resources={
            next(iter(token["policies"][0]["resources"])): {"*": "*"}}), "TOKEN_RESOURCE_SCOPE")

    def test_cross_bucket_rejected(self):
        self.policy(lambda token: token["policies"][0].update(resources={
            "com.cloudflare.edge.r2.bucket.[REDACTED]_default_e-track-firmware-p41-test-releases": "*"}), "TOKEN_RESOURCE_SCOPE")

    def test_token_condition_rejected(self):
        self.policy(lambda token: token.update(condition={"request.ip": {"in": ["192.0.2.0/24"]}}),
                    "TOKEN_CONDITIONS_OR_LIFETIME")

    def test_fabricated_ninety_day_provider_expiry_rejected(self):
        self.policy(lambda token: token.update(expires_on="2027-01-17T07:40:38Z"), "TOKEN_CONDITIONS_OR_LIFETIME")

    def test_additional_directory_token_rejected(self):
        self.reject(lambda value: value["observations"]["tokenDirectory"]["response"]["result"].append(
            {"name": "unplanned", "id": "[REDACTED]"}), "TOKEN_DIRECTORY_INCOMPLETE")

    def test_unredacted_synthetic_token_identifier_rejected(self):
        self.reject(lambda value: value["observations"]["tokenDirectory"]["response"]["result"][-1].update(
            id="a" * 32), "TOKEN_IDENTIFIER_NOT_REDACTED")

    def test_wrong_reviewer_id_rejected(self):
        self.reject(lambda value: value["observations"]["productionEnvironment"]["response"]["protection_rules"][0][
            "reviewers"][0]["reviewer"].update(id=1), "REVIEWER_POLICY_MISMATCH")

    def test_production_self_review_rejected(self):
        self.reject(lambda value: value["observations"]["productionEnvironment"]["response"]["protection_rules"][0].update(
            prevent_self_review=False), "REVIEWER_POLICY_MISMATCH")

    def test_staging_history_not_silently_reinterpreted(self):
        self.reject(lambda value: value["observations"]["rehearsalEnvironment"]["response"]["protection_rules"][0].update(
            prevent_self_review=True), "REVIEWER_POLICY_MISMATCH")

    def test_main_only_policy_rejected_if_wildcard(self):
        self.reject(lambda value: value["observations"]["productionBranches"]["response"]["branch_policies"][0].update(
            name="*"), "HISTORICAL_BRANCH_SCOPE")

    def test_secret_moved_out_of_expected_environment_rejected(self):
        self.reject(lambda value: value["observations"]["productionSecrets"]["response"]["secrets"][3].update(
            name="FIRMWARE_REHEARSAL_TRACE_R2_ACCESS_KEY_ID"), "ENVIRONMENT_SECRET_MISSING")

    def test_secret_collection_truncation_rejected(self):
        self.reject(lambda value: value["observations"]["productionSecrets"]["response"].update(total_count=99),
                    "GITHUB_COLLECTION_INCOMPLETE")

    def test_environment_gate_unlock_rejected(self):
        self.reject(lambda value: value["observations"]["productionVariables"]["response"]["variables"][0].update(value="true"),
                    "ENVIRONMENT_GATE_UNLOCKED")

    def test_repository_gate_unlock_rejected(self):
        self.reject(lambda value: value["observations"]["repositoryGate"]["response"].update(value="true"),
                    "REPOSITORY_GATE_UNLOCKED")

    def test_private_original_registry_mismatch_rejected(self):
        self.reject(lambda value: value["requests"][0].update(sha256="a" * 64), "PRIVATE_ORIGINAL_REGISTRY_MISMATCH")

    def test_post_must_not_be_counted_as_get(self):
        self.reject(lambda value: value["requests"][0].update(method="POST"), "READBACK_HTTP_BINDING")

    def test_missing_get_rejected(self):
        self.reject(lambda value: value["requests"].pop(), "READBACK_REQUESTS_INCOMPLETE")

    def test_old_source_cannot_be_called_new_success(self):
        self.reject(lambda value: value["source"].update(managementIdSha256=origins.OLD_SOURCE_ID),
                    "MANAGEMENT_SOURCE_MISMATCH")

    def test_incomplete_collector_not_rewritten_as_success(self):
        self.reject(lambda value: value["checks"][0].update(passed=False), "READBACK_COLLECTOR_FAILED")

    def test_summary_current_user_only_cannot_hide_real_extra_grant(self):
        self.reject(lambda value: value["targets"][1].update(afterAcl=value["targets"][1]["afterAcl"]
                    + "\nBUILTIN\\Users:(R)\n"), "ACL_NOT_CURRENT_USER_ONLY", "credential-protection-01.json")

    def test_missing_acl_receipt_rejected(self):
        self.reject(lambda value: value["targets"][1].update(beforeAcl=""),
                    "ACL_RAW_RECEIPT_MISSING", "credential-protection-01.json")

    def test_acl_incomplete_target_scope_rejected(self):
        self.reject(lambda value: value["targets"].pop(), "ACL_TARGET_SCOPE", "credential-protection-01.json")

    def test_failed_content_comparison_rejected(self):
        self.reject(lambda value: value["targets"][1].update(contentUnchanged=False),
                    "ACL_COLLECTOR_FAILED", "credential-protection-01.json")

    def test_listing_failure_not_upgraded_to_put_success(self):
        self.reject(lambda value: value["jobs"]["production"].update(s3_sigv4_listobjects_http=403),
                    "CREATION_OBSERVATION_MISMATCH", "create-s3-02.json")


class HistoryTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.files = read_files(HISTORY_ROOT, origins.HISTORY_FILES)

    def reject_json(self, name, change, code):
        with self.assertRaisesRegex(origins.EvidenceError, "^" + code + "$"):
            origins.history(changed_json(self.files, name, change))

    def test_actual_historical_originals(self):
        result = origins.history(self.files)
        self.assertEqual(result["original_files"], 38)
        self.assertEqual(result["test_counts"]["native"], 283)
        self.assertEqual(result["test_counts"]["pipeline"], 147)
        self.assertEqual(result["test_counts"]["sdk_workflow"], 112)
        self.assertEqual(result["dependency_debt"]["total"], 11)
        self.assertGreater(result["warning_word_occurrences"]["firmware_full_log"], 0)
        self.assertEqual(len(result["preserved_failures"]), 2)

    def test_raw_ci_failure_rejected(self):
        self.reject_json("remediation-ci-state-02.log", lambda value: value.update(conclusion="failure"),
                         "CI_RUN_NOT_SUCCESSFUL")

    def test_wrong_ci_source_rejected(self):
        self.reject_json("remediation-ci-state-02.log", lambda value: value.update(headSha="a" * 40),
                         "CI_RUN_NOT_SUCCESSFUL")

    def test_unplanned_production_job_rejected(self):
        self.reject_json("remediation-ci-state-02.log", lambda value: value["jobs"][-2].update(conclusion="success"),
                         "CI_JOB_NOT_SUCCESSFUL")

    def test_typecheck_step_cannot_be_skipped_behind_successful_job(self):
        self.reject_json("remediation-ci-state-02.log", lambda value: next(
            step for step in value["jobs"][1]["steps"] if step["name"] == "Check Worker and shared script types"
        ).update(conclusion="skipped"), "CI_STEP_FAILED")

    def test_multiline_filename_cannot_supply_fabricated_test_counts(self):
        files = dict(self.files)
        key = "remediation-ci-full-log-02.log"
        marker = b"Upload firmware artifact\t/home/runner/work/E-Track/E-Track/.cache/etfw/app-gcc/X-Track-App-GCC.hex"
        self.assertIn(marker, files[key])
        files[key] = files[key].replace(marker, b"Upload firmware artifact\tTests 999 passed (999)")
        with self.assertRaisesRegex(origins.EvidenceError, "^CI_LOG_TIMESTAMP_MISSING$"):
            origins.history(files)

    def test_dispatch_result_must_name_observed_run(self):
        files = dict(self.files)
        files["remediation-checks-dispatch-01.log"] = b"https://github.com/Eitan-S-23/E-Track/actions/runs/1\n"
        with self.assertRaisesRegex(origins.EvidenceError, "^DISPATCH_RUN_BINDING$"):
            origins.history(files)

    def test_audit_command_not_inferred_from_json_shape(self):
        self.reject_json("remediation-npm-audit-01.json", lambda value: value.update(command="untrusted"),
                         "COMMAND_BINDING_MISMATCH")

    def test_real_test_count_read_from_stdout(self):
        files = dict(self.files)
        key = "remediation-ci-full-log-02.log"
        self.assertIn(b"283 passed", files[key])
        files[key] = files[key].replace(b"283 passed", b"282 passed")
        with self.assertRaisesRegex(origins.EvidenceError, "^VITEST_COUNTS_MISMATCH$"):
            origins.history(files)

    def test_sdk_count_not_taken_from_ci_summary(self):
        files = dict(self.files)
        files["remediation-sdk-01.log"] = files["remediation-sdk-01.log"].replace(b"tests 23", b"tests 24")
        with self.assertRaisesRegex(origins.EvidenceError, "^NODE_TEST_COUNTS_MISMATCH$"):
            origins.history(files)

    def test_command_receipt_run_binding_rejected(self):
        self.reject_json("remediation-ci-state-02.json", lambda value: value["args"].__setitem__(2, "1"),
                         "COMMAND_BINDING_MISMATCH")

    def test_missing_complete_job_rejected(self):
        files = dict(self.files)
        key = "remediation-ci-full-log-02.log"
        files[key] = b"\n".join(line for line in files[key].splitlines()
                               if b"Release tooling development checks" not in line or b"\tComplete job\t" not in line)
        with self.assertRaisesRegex(origins.EvidenceError, "^CI_FULL_LOG_INCOMPLETE$"):
            origins.history(files)

    def test_failed_receipt_exit_not_rewritten(self):
        self.reject_json("remediation-ci-full-log-01.json", lambda value: value.update(exitCode=0),
                         "COMMAND_RECEIPT_FAILED")

    def test_failed_tls_original_preserved(self):
        files = dict(self.files)
        files["remediation-ci-full-log-01.log"] = b"successful log retrieval\n"
        with self.assertRaisesRegex(origins.EvidenceError, "^FAILED_ORIGINAL_MISSING$"):
            origins.history(files)

    def test_dependency_debt_not_zeroed(self):
        self.reject_json("remediation-npm-audit-01.log", lambda value: value["metadata"]["vulnerabilities"].update(total=0),
                         "DEPENDENCY_DEBT_CHANGED")

    def test_historical_time_order_rejected(self):
        self.reject_json("remediation-sdk-01.json", lambda value: value.update(endedAt="2020-01-01T00:00:00Z"),
                         "COMMAND_TIME_ORDER")

    def test_governance_stdout_counts_required(self):
        files = dict(self.files)
        files["remediation-governance-full-log-01.log"] = files["remediation-governance-full-log-01.log"].replace(
            b"Ran 137 tests", b"Ran 136 tests")
        with self.assertRaisesRegex(origins.EvidenceError, "^GOVERNANCE_REGRESSION_OUTPUT_MISMATCH$"):
            origins.history(files)


class ApplicabilityTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.original_tree = origins.git(ROOT, "ls-tree", "-r", "-z", origins.SOURCE_COMMIT)
        cls.original_config = origins.git(ROOT, "show", origins.SOURCE_COMMIT + ":" + origins.PROFILE_PATH)

    def evaluate(self, current_tree=None, current_config=None):
        candidate = "a" * 40

        def fake_git(root, *arguments):
            if arguments[0] == "merge-base":
                return b""
            if arguments[0] == "ls-tree":
                if arguments[-1] == origins.SOURCE_COMMIT:
                    return self.original_tree
                return current_tree if current_tree is not None else self.original_tree
            if arguments[0] == "show":
                if arguments[-1].startswith(origins.SOURCE_COMMIT + ":"):
                    return self.original_config
                return current_config if current_config is not None else self.original_config
            self.fail("Unexpected Git command in offline fixture")

        with patch.object(origins, "git", fake_git):
            return origins.input_applicability(ROOT, {"source_commit": origins.SOURCE_COMMIT, "candidate_commit": candidate})

    def test_existing_product_change_rejected(self):
        rows = self.original_tree.split(b"\0")
        index = next(i for i, row in enumerate(rows) if row.endswith(b"\t.github/scripts/firmware-release.mjs"))
        header, path = rows[index].split(b"\t", 1)
        rows[index] = header.rsplit(b" ", 1)[0] + b" " + b"f" * 40 + b"\t" + path
        with self.assertRaisesRegex(origins.EvidenceError, "^HISTORICAL_INPUT_CHANGED$"):
            self.evaluate(b"\0".join(rows))

    def test_added_product_path_rejected(self):
        tree = self.original_tree + b"100644 blob " + b"f" * 40 + b"\t.github/scripts/unseen.mjs\0"
        with self.assertRaisesRegex(origins.EvidenceError, "^HISTORICAL_INPUT_SET_CHANGED$"):
            self.evaluate(tree)

    def test_deleted_existing_test_rejected(self):
        tree = b"\0".join(row for row in self.original_tree.split(b"\0")
                           if not row.endswith(b"\ttests/ota/test_firmware_s3.mjs"))
        with self.assertRaisesRegex(origins.EvidenceError, "^HISTORICAL_INPUT_CHANGED$"):
            self.evaluate(tree)

    def test_new_harness_is_explicitly_outside_old_tests(self):
        tree = self.original_tree + b"100644 blob " + b"f" * 40 + b"\tTools/acceptance/p44/new-fixture.py\0"
        result = self.evaluate(tree)
        self.assertEqual(result["new_paths_not_covered_by_old_tests"]["Validation"], ["Tools/acceptance/p44/new-fixture.py"])

    def test_existing_component_profile_cannot_be_changed(self):
        config = json.loads(self.original_config)
        config["profiles"]["P41Evaluation"]["root_patterns"].append("unapproved/")
        with self.assertRaisesRegex(origins.EvidenceError, "^HISTORY_PROFILE_CHANGED$"):
            self.evaluate(current_config=json.dumps(config).encode("utf-8"))

    def test_additive_new_component_profile_is_disclosed(self):
        config = json.loads(self.original_config)
        config["profiles"]["P44Fixture"] = {"category": "validation_inputs", "root_patterns": [],
            "top_files": ["Tools/acceptance/p44/new-fixture.py"], "exclude_prefixes": [],
            "required_paths": ["Tools/acceptance/p44/new-fixture.py"]}
        result = self.evaluate(current_config=json.dumps(config).encode("utf-8"))
        self.assertTrue(result["profile_config_changed"])
        self.assertEqual(result["new_profile_names"], ["P44Fixture"])


class DeploymentTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.files = read_files(DEPLOYMENT_ROOT, origins.DEPLOYMENT_FILES)
        inventory = json.loads(origins.guarded_path(ROOT, DEPLOYMENT_ROOT / "raw-output-inventory.json").read_bytes())
        cls.rows = {row["path"]: row for row in inventory["entries"] if row["path"] in origins.DEPLOYMENT_FILES}
        with origins.zipfile.ZipFile(io.BytesIO(cls.files["preparation/worker-input-01.zip"])) as archive:
            cls.runtime = archive.read("index.js")

    def reject(self, name, change, code):
        files = changed_json(self.files, name, change)
        with patch.object(origins, "worker_archive", return_value=self.runtime):
            with self.assertRaisesRegex(origins.EvidenceError, "^" + code + "$"):
                origins.deployment(ROOT, files, self.rows)

    def test_actual_deployment_module_map_versions_and_bindings(self):
        result = origins.deployment(ROOT, self.files, self.rows)
        self.assertEqual(result["selected_files"], 16)
        self.assertEqual(result["source_map_git_paths"], 16)
        self.assertEqual(result["declared_projections"], 4)
        self.assertEqual(len(result["preserved_failures"]), 4)
        self.assertEqual(result["workers"]["production"]["module_sha256"], origins.WORKER_MODULE_SHA256)

    def test_source_map_checks_actual_git_bytes(self):
        with patch.object(origins, "git", return_value=b"changed Git source\n"):
            with self.assertRaisesRegex(origins.EvidenceError, "^WORKER_SOURCE_MAP_GIT_MISMATCH$"):
                origins.worker_archive(ROOT, self.files, self.rows)

    def test_artifact_source_commit_cannot_be_swapped(self):
        files = changed_json(self.files, "preparation/worker-input-02.json", lambda value: value.update(commit="a" * 40))
        with self.assertRaisesRegex(origins.EvidenceError, "^WORKER_INPUT_CI_BINDING$"):
            origins.worker_archive(ROOT, files, self.rows)

    def test_artifact_http_failure_not_hidden_by_copied_summary(self):
        files = changed_json(self.files, "preparation/worker-input-01.json", lambda value: value["requests"][0].update(status=403))
        with self.assertRaisesRegex(origins.EvidenceError, "^WORKER_INPUT_HTTP_BINDING$"):
            origins.worker_archive(ROOT, files, self.rows)

    def test_zip_bytes_cannot_be_changed(self):
        files = dict(self.files)
        files["preparation/worker-input-01.zip"] += b"unexpected bytes"
        with self.assertRaisesRegex(origins.EvidenceError, "^WORKER_ZIP_IDENTITY$"):
            origins.worker_archive(ROOT, files, self.rows)

    def test_latest_deployment_not_summary_selects_version(self):
        self.reject("preparation/curl-deploy-production-04/09.body",
                    lambda value: value["result"]["deployments"][0]["versions"][0].update(version_id="wrong"),
                    "DEPLOYMENT_ACTIVE_VERSION")

    def test_split_traffic_rejected(self):
        self.reject("preparation/curl-deploy-production-04/09.body",
                    lambda value: value["result"]["deployments"][0]["versions"].append(
                        {"version_id": "unexpected", "percentage": 1}), "DEPLOYMENT_ACTIVE_VERSION")

    def test_protected_trace_database_rejected(self):
        self.reject("preparation/curl-deploy-production-04/08.body",
                    lambda value: next(item for item in value["result"]["bindings"] if item["name"] == "DB").update(
                        id="0133ad9e-d4a2-4fef-a659-4f2bf3d3a645", database_id="0133ad9e-d4a2-4fef-a659-4f2bf3d3a645"),
                    "DEPLOYMENT_DATABASE_BINDING")

    def test_protected_trace_bucket_rejected(self):
        self.reject("preparation/curl-deploy-production-04/08.body",
                    lambda value: next(item for item in value["result"]["bindings"] if item["name"] == "RELEASES_BUCKET").update(
                        bucket_name="trace-update-staging-releases"), "DEPLOYMENT_BUCKET_BINDING")

    def test_plaintext_secret_binding_rejected(self):
        self.reject("preparation/curl-deploy-production-04/08.body",
                    lambda value: next(item for item in value["result"]["bindings"] if item["name"] == "DEPLOY_TOKEN_SHA256").update(
                        type="plain_text", text="synthetic"), "DEPLOYMENT_SECRET_TYPE")

    def test_enabled_direct_admin_rejected(self):
        self.reject("preparation/curl-deploy-production-04/08.body",
                    lambda value: next(item for item in value["result"]["bindings"] if item["name"] == "ENABLE_DIRECT_ADMIN_API").update(
                        text="true"), "DEPLOYMENT_ENVIRONMENT_BINDING")

    def test_disabled_query_redaction_rejected(self):
        self.reject("preparation/curl-deploy-production-04/08.body",
                    lambda value: value["result"]["observability"].update(redact_query_string=False),
                    "DEPLOYMENT_QUERY_REDACTION")

    def test_http_failure_not_hidden_by_matching_module(self):
        self.reject("preparation/deploy/production/deploy-04.json",
                    lambda value: value["requests"][-1].update(status=403), "DEPLOYMENT_HTTP_BINDING")

    def test_original_http_hash_not_compared_to_projected_body_hash(self):
        self.reject("preparation/deploy/production/deploy-04.json", lambda value: value["requests"][8].update(
            sha256=self.rows["preparation/curl-deploy-production-04/09.body"]["sha256"]),
            "DEPLOYMENT_HTTP_ORIGINAL_BINDING")

    def test_changed_multipart_module_rejected(self):
        target = origins.DEPLOYMENTS["production"]
        report = json.loads(self.files[target["receipt"]])
        body = self.files[target["prefix"] + "11.body"]
        self.assertIn(self.runtime, body)
        changed = body.replace(self.runtime, b"!" + self.runtime[1:])
        with self.assertRaisesRegex(origins.EvidenceError, "^DEPLOYMENT_MODULE_IDENTITY$"):
            origins.deployed_multipart(changed, self.files[target["prefix"] + "11.headers"], report["content"])

    def test_duplicate_multipart_module_rejected(self):
        target = origins.DEPLOYMENTS["production"]
        report = json.loads(self.files[target["receipt"]])
        body = self.files[target["prefix"] + "11.body"]
        boundary = b"--" + report["content"]["contentType"].split("boundary=", 1)[1].encode("ascii")
        parts = body.split(boundary)
        self.assertEqual(len(parts), 3)
        changed = boundary.join([parts[0], parts[1], parts[1], parts[2]])
        content = dict(report["content"], sha256=origins.sha256(changed))
        with self.assertRaisesRegex(origins.EvidenceError, "^DEPLOYMENT_MODULE_SET$"):
            origins.deployed_multipart(changed, self.files[target["prefix"] + "11.headers"], content)

    def test_missing_failed_deployment_original_rejected(self):
        files = dict(self.files)
        del files["preparation/deploy/production/deploy-03.json"]
        with self.assertRaisesRegex(origins.EvidenceError, "^DEPLOYMENT_INVENTORY_INCOMPLETE$"):
            origins.deployment(ROOT, files, self.rows)

    def test_failed_deployment_not_rewritten_as_success(self):
        self.reject("preparation/deploy/production/deploy-03.json", lambda value: value["command"].update(exitCode=0),
                    "DEPLOYMENT_PRODUCTION_FAILURE_HISTORY")


class FilesystemTests(unittest.TestCase):
    def setUp(self):
        origins.guarded_path(ROOT, TEST_ROOT)
        TEST_ROOT.mkdir(parents=True, exist_ok=True)
        origins.guarded_path(ROOT, TEST_ROOT)
        self.directory = Path(tempfile.mkdtemp(prefix="originals-", dir=TEST_ROOT))
        origins.guarded_path(TEST_ROOT, self.directory)

    def tearDown(self):
        directory = origins.guarded_path(TEST_ROOT, self.directory)
        self.assertNotEqual(directory, TEST_ROOT)
        shutil.rmtree(directory)

    def write(self, name, data):
        path = origins.guarded_path(self.directory, self.directory / name)
        path.parent.mkdir(parents=True, exist_ok=True)
        origins.guarded_path(self.directory, path)
        with path.open("xb") as stream:
            stream.write(data)
        return {"path": name, "size_bytes": len(data), "sha256": origins.sha256(data)}

    def fixture(self, mode):
        directory = HISTORY_ROOT if mode == "history" else CONFIG_ROOT
        inventory_name = "raw-output-inventory.json" if mode == "history" else "inventory.json"
        inventory_data = origins.guarded_path(ROOT, directory / inventory_name).read_bytes()
        inventory = json.loads(inventory_data)
        for row in inventory["files"]:
            self.write(mode + "/" + row["path"], origins.guarded_path(ROOT, directory / row["path"]).read_bytes())
        manifest = {"schema": "p44-originals-v1", "source_commit": origins.SOURCE_COMMIT,
                    "candidate_commit": origins.git(ROOT, "rev-parse", "HEAD").decode("ascii").strip(),
                    mode: {"inventory": self.write(mode + "/" + inventory_name, inventory_data)}}
        if mode == "configuration":
            deployment_inventory = origins.guarded_path(ROOT, DEPLOYMENT_ROOT / "raw-output-inventory.json").read_bytes()
            for name in origins.DEPLOYMENT_FILES:
                self.write("deployment/" + name, origins.guarded_path(ROOT, DEPLOYMENT_ROOT / name).read_bytes())
            manifest["deployment"] = {"inventory": self.write("deployment/raw-output-inventory.json", deployment_inventory)}
        self.write("manifest.json", (json.dumps(manifest) + "\n").encode("utf-8"))
        return manifest

    def test_configuration_manifest_real_hash_bound_end_to_end(self):
        self.fixture("configuration")
        out = self.directory / "configuration-result.json"
        stdout = io.StringIO()
        with contextlib.redirect_stdout(stdout):
            result = origins.main(["configuration", "--repo-root", str(ROOT), "--input",
                                   str(self.directory / "manifest.json"), "--output", str(out)])
        self.assertEqual(result, 0, stdout.getvalue())
        document = json.loads(out.read_bytes())
        self.assertTrue(document["ok"])
        self.assertEqual(document["files_verified"], 26)
        self.assertEqual(document["platform_actions"], 0)
        self.assertEqual(document["observed"]["deployment"]["selected_files"], 16)

    def test_deployment_subset_does_not_require_unselected_originals(self):
        manifest = self.fixture("configuration")
        rows, files = origins.Context(ROOT, self.directory / "manifest.json").deployment_inventory(manifest["deployment"]["inventory"])
        self.assertEqual(set(rows), origins.DEPLOYMENT_FILES)
        self.assertEqual(set(files), origins.DEPLOYMENT_FILES)
        self.assertFalse((self.directory / "deployment/preparation/platform.cjs").exists())

    def test_deployment_projection_cannot_claim_byte_exact(self):
        manifest = self.fixture("configuration")
        document = json.loads((self.directory / manifest["deployment"]["inventory"]["path"]).read_bytes())
        next(row for row in document["entries"] if row["path"] == "preparation/curl-deploy-production-04/09.body")["byteExact"] = True
        reference = self.write("deployment/changed-inventory.json", json.dumps(document).encode("utf-8"))
        with self.assertRaisesRegex(origins.EvidenceError, "^DEPLOYMENT_BYTE_EXACT_MISMATCH$"):
            origins.Context(ROOT, self.directory / "manifest.json").deployment_inventory(reference)

    def test_final_configuration_requires_deployment_input(self):
        manifest = self.fixture("configuration")
        del manifest["deployment"]
        self.write("missing-deployment.json", json.dumps(manifest).encode("utf-8"))
        output = self.directory / "missing-deployment-result.json"
        with contextlib.redirect_stdout(io.StringIO()):
            code = origins.main(["configuration", "--repo-root", str(ROOT), "--input",
                                 str(self.directory / "missing-deployment.json"), "--output", str(output)])
        self.assertEqual(code, 1)
        self.assertEqual(json.loads(output.read_bytes())["error_code"], "DEPLOYMENT_INPUT_REQUIRED")

    def test_history_manifest_real_git_and_hash_bound_end_to_end(self):
        self.fixture("history")
        out = self.directory / "history-result.json"
        stdout = io.StringIO()
        with contextlib.redirect_stdout(stdout):
            result = origins.main(["history", "--repo-root", str(ROOT), "--input",
                                   str(self.directory / "manifest.json"), "--output", str(out)])
        self.assertEqual(result, 0, stdout.getvalue())
        document = json.loads(out.read_bytes())
        self.assertTrue(document["ok"])
        self.assertEqual(document["files_verified"], 39)
        self.assertGreater(document["input_applicability"]["compared_existing_paths"]["Production"], 0)

    def test_member_missing_rejected(self):
        manifest = self.fixture("configuration")
        target = origins.guarded_path(self.directory, self.directory / "configuration/create-s3-02.json")
        target.unlink()
        with self.assertRaisesRegex(origins.EvidenceError, "^FILE_SIZE_MISMATCH$"):
            origins.Context(ROOT, self.directory / "manifest.json").inventory(manifest["configuration"]["inventory"], "configuration")

    def test_digest_changed_rejected(self):
        reference = self.write("input.txt", b"x")
        reference["sha256"] = "a" * 64
        with self.assertRaisesRegex(origins.EvidenceError, "^FILE_DIGEST_MISMATCH$"):
            origins.Context(ROOT, self.directory / "manifest.json").read(reference)

    def test_boolean_size_is_not_integer(self):
        reference = self.write("input.txt", b"x")
        reference["size_bytes"] = True
        with self.assertRaisesRegex(origins.EvidenceError, "^FILE_SIZE_BOUND$"):
            origins.Context(ROOT, self.directory / "manifest.json").read(reference)

    def test_file_reference_cannot_leave_manifest_directory(self):
        self.write("outer.txt", b"x")
        context = origins.Context(ROOT, self.directory / "inside/manifest.json")
        for path in ("../outer.txt", "../../outer.txt", str(self.directory / "outer.txt"), "D:/other/file", "..\\outer.txt"):
            with self.subTest(path=path), self.assertRaisesRegex(origins.EvidenceError, "^INVALID_RELATIVE_PATH$"):
                context.read({"path": path, "size_bytes": 1, "sha256": origins.sha256(b"x")})

    def test_inventory_path_cannot_escape_its_subdirectory(self):
        manifest = self.fixture("configuration")
        reference = dict(manifest["configuration"]["inventory"])
        changed = json.loads((self.directory / reference["path"]).read_bytes())
        changed["files"][0]["path"] = "../create-s3-02.json"
        reference = self.write("changed-inventory.json", json.dumps(changed).encode("utf-8"))
        with self.assertRaisesRegex(origins.EvidenceError, "^INVENTORY_INCOMPLETE$"):
            origins.Context(ROOT, self.directory / "manifest.json").inventory(reference, "configuration")

    def test_inventory_missing_file_cannot_be_accepted_as_subset(self):
        manifest = self.fixture("history")
        original = json.loads((self.directory / manifest["history"]["inventory"]["path"]).read_bytes())
        original["files"].pop()
        reference = self.write("changed-inventory.json", json.dumps(original).encode("utf-8"))
        with self.assertRaisesRegex(origins.EvidenceError, "^INVENTORY_INCOMPLETE$"):
            origins.Context(ROOT, self.directory / "manifest.json").inventory(reference, "history")

    def test_original_collector_changes_rejected_even_with_new_public_hash(self):
        manifest = self.fixture("configuration")
        document = json.loads((self.directory / manifest["configuration"]["inventory"]["path"]).read_bytes())
        row = next(row for row in document["files"] if row["path"] == "credential-readback.cjs")
        for other in document["files"]:
            if other["path"] == row["path"]:
                data = b"unreviewed collector\n"
                other.update(size_bytes=len(data), sha256=origins.sha256(data), original_size_bytes=len(data),
                             original_sha256=origins.sha256(data), projection=False)
            else:
                data = (self.directory / "configuration" / other["path"]).read_bytes()
            self.write("changed/" + other["path"], data)
        reference = self.write("changed/inventory.json", json.dumps(document).encode("utf-8"))
        with self.assertRaisesRegex(origins.EvidenceError, "^HISTORICAL_COLLECTOR_CHANGED$"):
            origins.Context(ROOT, self.directory / "manifest.json").inventory(reference, "configuration")

    def test_output_is_exclusive(self):
        output = self.directory / "result.json"
        origins.write_result(ROOT, output, {"ok": False})
        original = output.read_bytes()
        with self.assertRaisesRegex(origins.EvidenceError, "^OUTPUT_ALREADY_EXISTS$"):
            origins.write_result(ROOT, output, {"ok": True})
        self.assertEqual(output.read_bytes(), original)

    def test_reparse_parent_rejected_before_write(self):
        original = Path.lstat
        suspicious = self.directory / "link"

        def fake_lstat(path, *args, **kwargs):
            if path == suspicious:
                return SimpleNamespace(st_mode=stat.S_IFDIR, st_file_attributes=stat.FILE_ATTRIBUTE_REPARSE_POINT)
            return original(path, *args, **kwargs)

        with patch.object(Path, "lstat", fake_lstat):
            with self.assertRaisesRegex(origins.EvidenceError, "^REPARSE_PATH_REJECTED$"):
                origins.write_result(ROOT, suspicious / "out.json", {"ok": True})
        self.assertFalse(suspicious.exists())

    def test_duplicate_json_keys_rejected(self):
        with self.assertRaisesRegex(origins.EvidenceError, "^DUPLICATE_JSON_KEY$"):
            origins.json_bytes(b'{"ok":true,"ok":false}')

    def test_nonfinite_json_rejected(self):
        with self.assertRaisesRegex(origins.EvidenceError, "^INVALID_JSON_NUMBER$"):
            origins.json_bytes(b'{"value":NaN}')

    def test_cli_errors_do_not_echo_arguments(self):
        sentinel = "SYNTHETIC_SECRET_MUST_NOT_BE_PRINTED"
        stdout = io.StringIO()
        with contextlib.redirect_stdout(stdout), self.assertRaises(SystemExit) as stopped:
            origins.main([sentinel])
        self.assertEqual(stopped.exception.code, 2)
        self.assertNotIn(sentinel, stdout.getvalue())
        self.assertEqual(json.loads(stdout.getvalue())["error_code"], "INVALID_ARGUMENTS")

    def test_failure_never_echoes_evidence_value(self):
        sentinel = "SYNTHETIC_SECRET_MUST_NOT_BE_PRINTED"
        self.write("manifest.json", json.dumps({"schema": sentinel}).encode("utf-8"))
        stdout = io.StringIO()
        output = self.directory / "error.json"
        with contextlib.redirect_stdout(stdout):
            code = origins.main(["configuration", "--repo-root", str(ROOT), "--input",
                                 str(self.directory / "manifest.json"), "--output", str(output)])
        self.assertEqual(code, 1)
        self.assertNotIn(sentinel, stdout.getvalue())
        self.assertNotIn(sentinel, output.read_text(encoding="utf-8"))
        self.assertEqual(json.loads(output.read_bytes())["error_code"], "MANIFEST_SCHEMA")


if __name__ == "__main__":
    unittest.main()
