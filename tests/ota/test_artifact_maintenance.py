#!/usr/bin/env python3
"""Offline maintenance guards. No fixture sends a real GitHub mutation."""

import copy
from datetime import datetime, timedelta, timezone
import io
import json
import os
from pathlib import Path
import re
import sys
from types import SimpleNamespace
import unittest
from unittest import mock
import uuid


sys.dont_write_bytecode = True
ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from Tools.flutter import artifact_maintenance as M


NOW = datetime(2026, 9, 17, 12, tzinfo=timezone.utc)


def policy():
    return {**M.SCOPE, "max_age_hours": 72, "keep_newest_per_branch": 2,
            "max_deletions": 50, "warning_budget_bytes": None, "pinned_artifacts": []}


def artifact(artifact_id, *, hours=96, branch="dev/flutter/demo", attempt=1):
    created = NOW - timedelta(hours=hours)
    sha = f"{artifact_id:040x}"
    run_id = artifact_id + 10000
    return {
        "id": artifact_id, "name": f"flutter-dev-debug-apk-{sha}-{run_id}-{attempt}",
        "size_in_bytes": 100 + artifact_id, "digest": "sha256:" + "a" * 64,
        "created_at": created.isoformat(), "expires_at": (created + timedelta(days=14)).isoformat(),
        "expired": False,
        "workflow_run": {"id": run_id, "head_sha": sha, "head_branch": branch,
                         "repository_id": M.SCOPE["repository_id"], "head_repository_id": M.SCOPE["repository_id"]},
    }


class FakeAPI:
    def __init__(self, items):
        self.items = {item["id"]: copy.deepcopy(item) for item in items}
        self.calls, self.runs, self.attempts = [], {}, {}
        self.before_request = None
        self.page_transform = None
        self.delete_behavior = {}
        self.repo = {"id": M.SCOPE["repository_id"], "full_name": M.SCOPE["repository"], "default_branch": "main"}
        self.workflow = {"id": 1234, "path": M.SCOPE["workflow_path"]}
        for item in items:
            if "workflow_run" not in item:
                continue
            source = item["workflow_run"]
            run = {"id": source["id"], "head_sha": source["head_sha"], "head_branch": source["head_branch"],
                   "workflow_id": 1234, "path": M.SCOPE["workflow_path"], "run_attempt": 1,
                   "repository": {"id": M.SCOPE["repository_id"]}, "head_repository": {"id": M.SCOPE["repository_id"]},
                   "event": "push", "status": "completed", "conclusion": "success"}
            self.runs[run["id"]] = run
            self.attempts[(run["id"], 1)] = copy.deepcopy(run)

    def request(self, method, route):
        self.calls.append((method, route))
        if self.before_request:
            self.before_request(method, route)
        if method == "DELETE":
            match = re.fullmatch(M.REPO_ROUTE + r"/actions/artifacts/(\d+)", route)
            if not match:
                raise AssertionError("A test attempted an out-of-scope DELETE")
            artifact_id = int(match[1])
            behavior = self.delete_behavior.get(artifact_id)
            if behavior == "denied":
                raise M.ApiError("DELETE denied", status=403)
            if behavior != "timeout_present":
                self.items.pop(artifact_id)
            if behavior in ("timeout_removed", "timeout_present"):
                raise M.ApiError("DELETE uncertain", uncertain=True)
            return None
        if method != "GET":
            raise AssertionError("Unexpected method")
        if route == M.REPO_ROUTE:
            return copy.deepcopy(self.repo)
        if route == M.REPO_ROUTE + "/actions/workflows/flutter-dev-checks.yml":
            return copy.deepcopy(self.workflow)
        if "/actions/artifacts?" in route:
            page = int(route.rsplit("page=", 1)[1])
            items = sorted(self.items.values(), key=lambda item: item["id"])
            body = {"total_count": len(items), "artifacts": copy.deepcopy(items[(page - 1) * 100:page * 100])}
            return self.page_transform(body, page) if self.page_transform else body
        artifact_match = re.fullmatch(M.REPO_ROUTE + r"/actions/artifacts/(\d+)", route)
        if artifact_match:
            item = self.items.get(int(artifact_match[1]))
            if item is None:
                raise M.ApiError("Not found", status=404)
            return copy.deepcopy(item)
        run_match = re.fullmatch(M.REPO_ROUTE + r"/actions/runs/(\d+)(?:/attempts/(\d+))?", route)
        if run_match:
            run_id = int(run_match[1])
            if run_match[2]:
                return copy.deepcopy(self.attempts[(run_id, int(run_match[2]))])
            return copy.deepcopy(self.runs[run_id])
        raise AssertionError("Unexpected API route: " + route)

    @property
    def deletes(self):
        return [route for method, route in self.calls if method == "DELETE"]


class ArtifactMaintenanceTests(unittest.TestCase):
    def run_maintenance(self, api, selected_policy=None, **kwargs):
        return M.maintain(api, selected_policy or policy(), NOW, **kwargs)

    def test_default_is_a_read_only_dry_run(self):
        api = FakeAPI([artifact(1), {"id": 2, "name": "android-apk", "size_in_bytes": 500}])
        events = []
        report = self.run_maintenance(api, emit=events.append)
        self.assertEqual("DRY_RUN", report["result"])
        self.assertEqual([1], [item["id"] for item in report["plan"]["selected"]])
        self.assertEqual([], api.deletes)
        self.assertEqual(0, report["confirmed_freed_bytes"])
        self.assertEqual("plan", events[0]["event"])

    def test_apply_preserves_non_target_assets_and_records_real_receipts(self):
        items = [artifact(1), artifact(2), {"id": 3, "name": "windows-exe", "size_in_bytes": 500},
                 {"id": 4, "name": "flutter-dev-ubuntu-latest-8-1", "size_in_bytes": 20}]
        api = FakeAPI(items)
        events = []
        report = self.run_maintenance(api, mode="apply", emit=events.append)
        self.assertEqual("PASS", report["result"])
        self.assertEqual(203, report["confirmed_freed_bytes"])
        self.assertEqual({3, 4}, set(api.items))
        self.assertEqual([204, 204], [item["http_status"] for item in report["operations"]])
        self.assertEqual([], report["remaining_selected_ids"])
        self.assertEqual(520, report["capacity_after"]["repository_bytes"])
        self.assertEqual(["plan", "delete_intent", "operation", "delete_intent", "operation"],
                         [item["event"] for item in events])

    def test_approved_id_parser_is_bounded_and_rejects_ambiguous_inputs(self):
        self.assertIsNone(M.parse_approved_ids(""))
        self.assertEqual([2, 1], M.parse_approved_ids("2,1"))
        self.assertEqual(list(range(1, 51)), M.parse_approved_ids(",".join(map(str, range(1, 51)))))
        for value in (None, 1, "0", "-1", "01", "1,1", "1,", "1 2", "1, 2", "1\n",
                      "1;2", "all", ",".join(map(str, range(1, 52)))):
            with self.subTest(value=value), self.assertRaises(ValueError):
                M.parse_approved_ids(value)

    def test_approved_ids_allow_only_the_exact_plan_in_any_order(self):
        api = FakeAPI([artifact(1), artifact(2)])
        report = self.run_maintenance(api, mode="apply", approved_ids=[2, 1])
        self.assertEqual("PASS", report["result"])
        self.assertEqual([2, 1], report["approved_artifact_ids"])
        self.assertEqual(2, len(api.deletes))

    def test_approved_ids_do_not_select_extra_or_partial_candidates(self):
        for ids in ([], [1], [2], [1, 2, 3]):
            api, events = FakeAPI([artifact(1), artifact(2)]), []
            with self.subTest(ids=ids), self.assertRaisesRegex(ValueError, "differs"):
                self.run_maintenance(api, mode="apply", approved_ids=ids, emit=events.append)
            self.assertEqual([], api.deletes)
            self.assertEqual(["plan"], [event["event"] for event in events])

    def test_new_pin_or_active_run_invalidates_reviewed_ids_before_any_delete(self):
        for change in ("pin", "active", "young"):
            api, selected_policy = FakeAPI([artifact(1), artifact(2)]), policy()
            if change == "pin":
                selected_policy["pinned_artifacts"] = [{"id": 2, "reason": "New evidence dependency"}]
            elif change == "active":
                api.runs[10002].update(status="in_progress", conclusion=None)
            else:
                api.items[2].update(artifact(2, hours=1))
            with self.subTest(change=change), self.assertRaisesRegex(ValueError, "differs"):
                self.run_maintenance(api, selected_policy, mode="apply", approved_ids=[1, 2])
            self.assertEqual([], api.deletes)

    def test_invalid_approved_ids_fail_before_api_access(self):
        for ids in ("1", [0], [True], ["1"], [1, 1], list(range(1, 52))):
            api = FakeAPI([artifact(1)])
            with self.subTest(ids=ids), self.assertRaises(ValueError):
                self.run_maintenance(api, mode="apply", approved_ids=ids)
            self.assertEqual([], api.calls)

    def test_approved_dry_run_is_still_read_only(self):
        api = FakeAPI([artifact(1)])
        self.assertEqual("DRY_RUN", self.run_maintenance(api, approved_ids=[1])["result"])
        self.assertEqual([], api.deletes)

    def test_age_count_pins_and_branch_isolation(self):
        items = [artifact(1, hours=1), artifact(2, hours=2), artifact(3, hours=3),
                 artifact(4, hours=72), artifact(5, hours=71.999, branch="dev/flutter/other"),
                 artifact(6, hours=100, branch="dev/flutter/pinned")]
        selected_policy = policy()
        selected_policy["pinned_artifacts"] = [{"id": 6, "reason": "Evidence still required"}]
        report = self.run_maintenance(FakeAPI(items), selected_policy)
        self.assertEqual([4, 3], [item["id"] for item in report["plan"]["selected"]])
        self.assertEqual(["age", "branch_count"], [item["reason"] for item in report["plan"]["selected"]])
        self.assertEqual({1, 2, 5, 6}, {item["id"] for item in report["plan"]["kept"]})

    def test_deterministic_id_tie_break_and_completed_rolling_slots(self):
        api = FakeAPI([artifact(i, hours=1) for i in (4, 2, 3, 1)])
        selected_policy = policy()
        selected_policy["pinned_artifacts"] = [{"id": 4, "reason": "Evidence"}]
        report = self.run_maintenance(api, selected_policy)
        self.assertEqual([1], [item["id"] for item in report["plan"]["selected"]])
        self.assertEqual({2, 3, 4}, {item["id"] for item in report["plan"]["kept"]})

    def test_active_and_expired_artifacts_are_excluded(self):
        api = FakeAPI([artifact(1), artifact(2), artifact(3)])
        api.runs[10001]["status"] = "in_progress"
        api.runs[10001]["conclusion"] = None
        api.items[2]["expired"] = True
        report = self.run_maintenance(api, mode="apply")
        self.assertEqual({1, 2}, set(api.items))
        self.assertEqual([3], [item["id"] for item in report["operations"]])
        self.assertEqual({"active_run", "expired"}, {item["reason"] for item in report["plan"]["kept"]})

    def test_old_attempt_is_checked_against_its_own_run_metadata(self):
        api = FakeAPI([artifact(1)])
        api.runs[10001]["run_attempt"] = 2
        self.assertEqual("PASS", self.run_maintenance(api, mode="apply")["result"])
        self.assertIn(("GET", M.REPO_ROUTE + "/actions/runs/10001/attempts/1"), api.calls)
        api = FakeAPI([artifact(1)])
        api.runs[10001]["run_attempt"] = 2
        api.attempts[(10001, 1)]["run_attempt"] = 2
        with self.assertRaisesRegex(ValueError, "attempt"):
            self.run_maintenance(api, mode="apply")
        self.assertEqual([], api.deletes)

    def test_complete_inventory_is_required_before_any_deletion(self):
        items = [artifact(1)] + [{"id": i, "name": "android-apk", "size_in_bytes": i} for i in range(2, 103)]
        api = FakeAPI(items)
        report = self.run_maintenance(api)
        self.assertEqual(102, report["plan"]["capacity_before"]["artifact_count"])
        self.assertEqual(2, sum("artifacts?" in route for _, route in api.calls))
        for fault in ("truncated", "duplicate", "changed_total", "api_error", "bad_size"):
            api = FakeAPI(items)

            def transform(body, page):
                if page == 2:
                    if fault == "truncated":
                        body["artifacts"] = []
                    elif fault == "duplicate":
                        body["artifacts"][0] = copy.deepcopy(items[0])
                    elif fault == "changed_total":
                        body["total_count"] += 1
                    elif fault == "api_error":
                        raise M.ApiError("rate limited", status=403)
                    else:
                        body["artifacts"][0]["size_in_bytes"] = -1
                return body

            api.page_transform = transform
            with self.subTest(fault=fault), self.assertRaises((ValueError, M.ApiError)):
                self.run_maintenance(api, mode="apply")
            self.assertEqual([], api.deletes)

    def test_forged_or_incomplete_target_metadata_fails_closed(self):
        mutations = {
            "name": lambda api: api.items[1].update(name="flutter-dev-debug-apk-forged"),
            "embedded_sha": lambda api: api.items[1]["workflow_run"].update(head_sha="f" * 40),
            "source_repo": lambda api: api.items[1]["workflow_run"].update(repository_id=99),
            "source_branch": lambda api: api.items[1]["workflow_run"].update(head_branch="main"),
            "workflow": lambda api: api.runs[10001].update(workflow_id=999),
            "run_repo": lambda api: api.runs[10001].update(head_repository={"id": 99}),
            "run_event": lambda api: api.runs[10001].update(event="pull_request"),
            "future_attempt": lambda api: api.items[1].update(name=api.items[1]["name"][:-1] + "3"),
            "missing_digest": lambda api: api.items[1].pop("digest"),
            "missing_run": lambda api: api.items[1].pop("workflow_run"),
            "invalid_time": lambda api: api.items[1].update(created_at="2026-09-17T00:00:00"),
            "future_time": lambda api: api.items[1].update(created_at=(NOW + timedelta(hours=1)).isoformat()),
            "missing_conclusion": lambda api: api.runs[10001].update(conclusion=None),
        }
        for name, mutate in mutations.items():
            api = FakeAPI([artifact(1), artifact(2)])
            mutate(api)
            with self.subTest(mutation=name), self.assertRaises(ValueError):
                self.run_maintenance(api, mode="apply")
            self.assertEqual([], api.deletes)

    def test_repo_workflow_and_policy_cannot_widen_scope(self):
        for key, value in (("repository", "other/repo"), ("artifact_prefix", ""),
                           ("branch_prefix", ""), ("max_deletions", 51), ("max_age_hours", 1),
                           ("keep_newest_per_branch", 0), ("warning_budget_bytes", 0)):
            api, selected_policy = FakeAPI([artifact(1)]), policy()
            selected_policy[key] = value
            with self.subTest(key=key), self.assertRaises(ValueError):
                self.run_maintenance(api, selected_policy, mode="apply")
            self.assertEqual([], api.calls)
        for field in ("id", "full_name", "default_branch"):
            api = FakeAPI([artifact(1)])
            api.repo[field] = "unexpected"
            with self.subTest(field=field), self.assertRaises(ValueError):
                self.run_maintenance(api, mode="apply")
            self.assertEqual([], api.deletes)
        api = FakeAPI([artifact(1)])
        api.workflow["path"] = ".github/workflows/build.yml"
        with self.assertRaises(ValueError):
            self.run_maintenance(api, mode="apply")

    def test_every_id_is_revalidated_and_changes_stop_the_batch(self):
        for changed in ("digest", "active", "response_type"):
            api = FakeAPI([artifact(1), artifact(2)])

            def alter(method, route):
                if method == "GET" and route == M.REPO_ROUTE + "/actions/artifacts/1":
                    if changed == "digest":
                        api.items[1]["digest"] = "sha256:" + "f" * 64
                    elif changed == "active":
                        api.runs[10001].update(status="queued", conclusion=None)
                    else:
                        raise M.ApiError("malformed JSON")

            api.before_request = alter
            with self.subTest(changed=changed):
                report = self.run_maintenance(api, mode="apply")
                self.assertEqual("FAIL", report["result"])
                self.assertEqual([], api.deletes)
                self.assertEqual(0, report["confirmed_freed_bytes"])

    def test_uncertain_delete_is_reconciled_once_without_retry_or_byte_credit(self):
        for behavior, reconciliation in (("timeout_removed", "absent"), ("timeout_present", "still_present")):
            api = FakeAPI([artifact(1), artifact(2)])
            api.delete_behavior[1] = behavior
            report = self.run_maintenance(api, mode="apply")
            with self.subTest(behavior=behavior):
                self.assertEqual("FAIL", report["result"])
                self.assertEqual(1, len(api.deletes))
                self.assertEqual("DELETE_UNCERTAIN", report["operations"][0]["outcome"])
                self.assertEqual(reconciliation, report["operations"][0]["reconciliation"])
                self.assertEqual(0, report["confirmed_freed_bytes"])
                self.assertIn(2, api.items)
                self.assertEqual(2, api.calls.count(("GET", M.REPO_ROUTE + "/actions/artifacts/1")))

    def test_partial_failure_keeps_receipts_and_stops_remaining_ids(self):
        api = FakeAPI([artifact(1), artifact(2), artifact(3)])
        api.delete_behavior[2] = "denied"
        report = self.run_maintenance(api, mode="apply")
        self.assertEqual("FAIL", report["result"])
        self.assertEqual(101, report["confirmed_freed_bytes"])
        self.assertEqual(2, len(api.deletes))
        self.assertEqual({2, 3}, set(api.items))
        self.assertEqual(["DELETED", "NOT_DELETED"], [item["outcome"] for item in report["operations"]])

    def test_journal_failure_before_delete_cannot_start_a_mutation(self):
        api = FakeAPI([artifact(1), artifact(2)])

        def broken(event):
            if event["event"] == "delete_intent":
                raise OSError("Fixture journal cannot persist intent")

        with self.assertRaises(OSError):
            self.run_maintenance(api, mode="apply", emit=broken)
        self.assertEqual([], api.deletes)

    def test_final_inventory_failure_does_not_claim_known_freed_bytes(self):
        api = FakeAPI([artifact(1)])

        def fail_final(method, route):
            if api.deletes and "artifacts?" in route:
                raise M.ApiError("Final inventory unavailable")

        api.before_request = fail_final
        report = self.run_maintenance(api, mode="apply")
        self.assertEqual("FAIL", report["result"])
        self.assertEqual(204, report["operations"][0]["http_status"])
        self.assertIsNone(report["confirmed_freed_bytes"])
        self.assertIsNone(report["capacity_after"])

    def test_delete_cap_reports_backlog_instead_of_expanding_scope(self):
        api = FakeAPI([artifact(i) for i in range(1, 64)])
        report = self.run_maintenance(api, mode="apply")
        self.assertEqual("PASS", report["result"])
        self.assertEqual(50, len(api.deletes))
        self.assertEqual(50, report["plan"]["selected_count"])
        self.assertEqual(13, report["plan"]["backlog_count"])
        self.assertEqual(set(range(51, 64)), set(api.items))

    def test_capacity_warning_is_not_an_account_quota_or_a_deletion_override(self):
        api = FakeAPI([artifact(1, hours=1), {"id": 2, "name": "android-apk", "size_in_bytes": 1000}])
        unknown = self.run_maintenance(api)["plan"]["capacity_before"]
        self.assertIsNone(unknown["warning_budget_bytes"])
        self.assertIsNone(unknown["warning_budget_exceeded"])
        self.assertIsNone(unknown["account_quota_bytes"])
        report = self.run_maintenance(api, mode="apply", budget=100)
        self.assertTrue(report["plan"]["capacity_before"]["warning_budget_exceeded"])
        self.assertEqual(1101, report["plan"]["capacity_before"]["repository_bytes"])
        self.assertEqual([], api.deletes)
        self.assertEqual(101, report["plan"]["capacity_before"]["debug_apk_bytes"])

    def test_production_transport_rejects_non_artifact_deletion_and_redirects(self):
        api = M.GitHubAPI("fixture-job-credential")
        with mock.patch.object(api.opener, "open") as opened:
            for method, route in (("DELETE", M.REPO_ROUTE + "/actions/runs/1"),
                                  ("DELETE", "/repos/other/repo/actions/artifacts/1"),
                                  ("POST", M.REPO_ROUTE + "/actions/artifacts/1"),
                                  ("DELETE", M.REPO_ROUTE + "/actions/artifacts/1/../2")):
                with self.subTest(route=route), self.assertRaises(ValueError):
                    api.request(method, route)
            opened.assert_not_called()
        self.assertIsNone(M.NoRedirect().redirect_request(None, None, 302, "", {}, "https://other.invalid"))
        for method in ("GET", "DELETE"):
            with mock.patch.object(api.opener, "open", side_effect=TimeoutError), self.assertRaises(M.ApiError) as raised:
                api.request(method, M.REPO_ROUTE + "/actions/artifacts/1")
            self.assertEqual(method == "DELETE", raised.exception.uncertain)
            self.assertNotIn("fixture-job-credential", str(raised.exception))

    def test_trusted_ci_context_rejects_forks_refs_events_and_checkout_drift(self):
        env = {
            "GITHUB_ACTIONS": "true", "GITHUB_REPOSITORY": M.SCOPE["repository"],
            "GITHUB_REPOSITORY_ID": str(M.SCOPE["repository_id"]), "GITHUB_REF": "refs/heads/main",
            "GITHUB_WORKFLOW_REF": M.SCOPE["repository"] + "/" + M.MAINTENANCE_WORKFLOW + "@refs/heads/main",
            "GITHUB_WORKSPACE": str(ROOT), "GITHUB_SHA": "a" * 40, "GITHUB_EVENT_NAME": "schedule",
        }
        with mock.patch.object(M.subprocess, "run", return_value=SimpleNamespace(stdout="a" * 40)):
            M.ci_context(ROOT, env)
            for key, value in (("GITHUB_REPOSITORY", "fork/E-Track"), ("GITHUB_REF", "refs/heads/topic"),
                               ("GITHUB_EVENT_NAME", "pull_request_target"), ("GITHUB_ACTIONS", "false"),
                               ("GITHUB_WORKFLOW_REF", "other-workflow"), ("GITHUB_SHA", "b" * 40)):
                with self.subTest(key=key), self.assertRaises(ValueError):
                    M.ci_context(ROOT, {**env, key: value})

    def test_cli_local_entry_never_creates_output_or_api_client(self):
        with mock.patch.dict(os.environ, {"GITHUB_ACTIONS": "false"}), \
                mock.patch.object(M, "GitHubAPI") as client, mock.patch.object(M, "make_directory") as create, \
                mock.patch("sys.stderr", new_callable=io.StringIO):
            self.assertEqual(1, M.main(["--repo-root", str(ROOT)]))
        client.assert_not_called()
        create.assert_not_called()

    def test_manual_apply_requires_reviewed_ids_before_output_or_api_creation(self):
        for value in ("", "1,1", "all"):
            with self.subTest(value=value), mock.patch.object(M, "ci_context"), \
                    mock.patch.dict(os.environ, {"GITHUB_EVENT_NAME": "workflow_dispatch"}), \
                    mock.patch.object(M, "GitHubAPI") as client, \
                    mock.patch.object(M, "make_directory") as create, \
                    mock.patch("sys.stderr", new_callable=io.StringIO):
                self.assertEqual(1, M.main(["--repo-root", str(ROOT), "--mode", "apply",
                                            "--approved-artifact-ids", value]))
            client.assert_not_called()
            create.assert_not_called()

    def test_cli_passes_reviewed_ids_and_keeps_scheduled_policy_behavior(self):
        for event, approved, expected in (("workflow_dispatch", "1", 0),
                                          ("workflow_dispatch", "2", 1), ("schedule", "", 0)):
            fixture = M.make_directory(ROOT, Path(".cache/artifact-maintenance-tests") / uuid.uuid4().hex,
                                       exclusive=True)
            policy_path = M.checked_path(fixture, M.POLICY_PATH)
            M.make_directory(fixture, policy_path.parent)
            policy_path.write_text(json.dumps(policy()), encoding="utf-8")
            api = FakeAPI([artifact(1)])
            with self.subTest(event=event, approved=approved), mock.patch.object(M, "ci_context"), \
                    mock.patch.object(M, "GitHubAPI", return_value=api), \
                    mock.patch.dict(os.environ, {"GITHUB_EVENT_NAME": event, "CI_ARTIFACT_WARN_BYTES": "",
                                                 "ARTIFACT_MAINTENANCE_APPROVED_IDS": approved}), \
                    mock.patch.object(M, "datetime", wraps=datetime) as clock, \
                    mock.patch("sys.stdout", new_callable=io.StringIO), \
                    mock.patch("sys.stderr", new_callable=io.StringIO):
                clock.now.return_value = NOW
                self.assertEqual(expected, M.main(["--repo-root", str(fixture), "--mode", "apply"]))
            self.assertEqual(0 if expected else 1, len(api.deletes))

    def test_cli_dry_run_writes_checked_reports_and_budget_warning_without_upload(self):
        fixture = M.make_directory(ROOT, Path(".cache/artifact-maintenance-tests") / uuid.uuid4().hex, exclusive=True)
        policy_path = M.checked_path(fixture, M.POLICY_PATH)
        M.make_directory(fixture, policy_path.parent)
        policy_path.write_text(json.dumps(policy()), encoding="utf-8")
        api = FakeAPI([artifact(1)])
        with mock.patch.object(M, "ci_context"), mock.patch.object(M, "GitHubAPI", return_value=api), \
                mock.patch.dict(os.environ, {"ARTIFACT_MAINTENANCE_MODE": "dry-run", "CI_ARTIFACT_WARN_BYTES": "100"}), \
                mock.patch.object(M, "datetime", wraps=datetime) as clock, \
                mock.patch("sys.stdout", new_callable=io.StringIO) as console:
            clock.now.return_value = NOW
            self.assertEqual(0, M.main(["--repo-root", str(fixture)]))
        self.assertEqual([], api.deletes)
        path = next(fixture.glob(".cache/artifact-maintenance/runs/*/result.json"))
        report = json.loads(path.read_text())
        self.assertEqual("DRY_RUN", report["result"])
        self.assertEqual(1, report["plan"]["selected_count"])
        journal = [json.loads(line) for line in (path.parent / "operations.jsonl").read_text().splitlines()]
        self.assertEqual(["plan", "result"], [item["event"] for item in journal])
        self.assertIn("::warning title=Artifact storage budget::", console.getvalue())
        self.assertTrue(path.resolve().is_relative_to(ROOT))

    def test_committed_policy_and_workflow_are_bounded_and_governed(self):
        selected_policy = M.validate_policy(json.loads((ROOT / M.POLICY_PATH).read_text()))
        self.assertEqual({10399696022, 10397716463, 10378708222, 10298405373, 10295579024, 10274975471,
                          10269124401, 10195957620, 10195103592, 10178414611, 10142353404, 10114677343},
                         {item["id"] for item in selected_policy["pinned_artifacts"]})
        workflow = (ROOT / M.MAINTENANCE_WORKFLOW).read_text(encoding="utf-8")
        for text in ('cron: "17 2 * * *"', "default: dry-run", "cancel-in-progress: false",
                     "github.repository == 'Eitan-S-23/E-Track'", "github.ref == 'refs/heads/main'",
                     "github.event_name == 'schedule' && 'apply'", "persist-credentials: false",
                     "approved_artifact_ids:", "ARTIFACT_MAINTENANCE_APPROVED_IDS:",
                     "github.event_name == 'workflow_dispatch' && inputs.approved_artifact_ids",
                     "python3 -B Tools/flutter/artifact_maintenance.py --repo-root .", "CI_ARTIFACT_WARN_BYTES"):
            self.assertIn(text, workflow)
        self.assertEqual(1, workflow.count("actions: write"))
        for text in ("pull_request:", "pull_request_target:", "upload-artifact", "continue-on-error", "GITHUB_STEP_SUMMARY"):
            self.assertNotIn(text, workflow)
        governance = (ROOT / ".github/workflows/acceptance-governance.yml").read_text(encoding="utf-8")
        for path in ("Tools/flutter/**", M.MAINTENANCE_WORKFLOW, "tests/ota/test_artifact_maintenance.py"):
            self.assertEqual(2, governance.count(f'      - "{path}"'))
        self.assertIn("python3 -B tests/ota/test_artifact_maintenance.py", governance)
        profiles = json.loads((ROOT / "Tools/provenance/manifest_profiles.json").read_text())["profiles"]
        self.assertIn(M.MAINTENANCE_WORKFLOW, profiles["Validation"]["top_files"])
        self.assertIn("Tools/", profiles["Validation"]["root_patterns"])
        self.assertIn("tests/", profiles["Validation"]["root_patterns"])


if __name__ == "__main__":
    unittest.main(verbosity=2)
