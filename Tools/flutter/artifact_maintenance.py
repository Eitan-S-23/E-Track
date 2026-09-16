#!/usr/bin/env python3
"""Bounded default-branch maintenance of development APK artifacts, not runs."""

from datetime import datetime, timedelta, timezone
import argparse
import http.client
import json
import os
from pathlib import Path
import re
import ssl
import subprocess
import sys
from urllib.error import HTTPError, URLError
from urllib.request import HTTPRedirectHandler, HTTPSHandler, Request, build_opener
import uuid


sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from Tools.flutter.dev_checks import checked_path, diagnostic_json, make_directory, redact_diagnostics


SCOPE = {
    "schema": "etrack-artifact-maintenance-v1",
    "repository": "Eitan-S-23/E-Track",
    "repository_id": 1310649784,
    "workflow_path": ".github/workflows/flutter-dev-checks.yml",
    "branch_prefix": "dev/flutter/",
    "artifact_prefix": "flutter-dev-debug-apk-",
}
REPO_ROUTE = "/repos/" + SCOPE["repository"]
MAINTENANCE_WORKFLOW = ".github/workflows/artifact-maintenance.yml"
NAME = re.compile(r"flutter-dev-debug-apk-([0-9a-f]{40})-([1-9][0-9]*)-([1-9][0-9]*)\Z")
POLICY_PATH = "Tools/flutter/artifact_maintenance_policy.json"


class ApiError(RuntimeError):
    def __init__(self, message, *, status=None, uncertain=False):
        super().__init__(message)
        self.status = status
        self.uncertain = uncertain


class NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


class GitHubAPI:
    def __init__(self, token):
        if not token or any(char.isspace() for char in token):
            raise ValueError("A job token is required")
        self.token = token
        # Do not inherit SSLKEYLOGFILE or follow a redirect carrying authorization.
        context = ssl.SSLContext(ssl.PROTOCOL_TLS_CLIENT)
        context.load_default_certs()
        self.opener = build_opener(NoRedirect(), HTTPSHandler(context=context))

    def request(self, method, route):
        if method not in ("GET", "DELETE") or not route.startswith(REPO_ROUTE + "/"):
            if not (method == "GET" and route == REPO_ROUTE):
                raise ValueError("Request outside the authorized repository")
        if method == "DELETE" and not re.fullmatch(REPO_ROUTE + r"/actions/artifacts/[1-9][0-9]*", route):
            raise ValueError("Only exact artifact IDs may be deleted")
        request = Request("https://api.github.com" + route, method=method, headers={
            "Authorization": "Bearer " + self.token,
            "Accept": "application/vnd.github+json",
            "X-GitHub-Api-Version": "2022-11-28",
            "User-Agent": "E-Track-bounded-artifact-maintenance",
        })
        try:
            with self.opener.open(request, timeout=30) as response:
                expected = 204 if method == "DELETE" else 200
                if response.status != expected:
                    raise ApiError(f"{method} returned unexpected HTTP {response.status}",
                                   status=response.status, uncertain=method == "DELETE")
                if method == "DELETE":
                    return None
                payload = response.read(8 * 1024 * 1024 + 1)
                if len(payload) > 8 * 1024 * 1024:
                    raise ApiError("GitHub JSON response exceeds the bounded page size")
                try:
                    return json.loads(payload)
                except (ValueError, UnicodeError):
                    raise ApiError("GitHub returned malformed JSON") from None
        except HTTPError as exc:
            raise ApiError(f"{method} {route} returned HTTP {exc.code}", status=exc.code,
                           uncertain=method == "DELETE" and exc.code >= 500) from None
        except (URLError, OSError, http.client.HTTPException) as exc:
            raise ApiError(f"{method} {route} transport failure ({type(exc).__name__})",
                           uncertain=method == "DELETE") from None


def integer(value, label, minimum=0):
    if type(value) is not int or value < minimum:
        raise ValueError("Invalid integer: " + label)
    return value


def timestamp(value):
    if not isinstance(value, str):
        raise ValueError("Missing UTC artifact timestamp")
    try:
        result = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        raise ValueError("Invalid artifact timestamp") from None
    if result.tzinfo is None or result.utcoffset() != timedelta(0):
        raise ValueError("Artifact timestamps must be explicit UTC")
    return result


def validate_policy(policy):
    if not isinstance(policy, dict) or any(policy.get(key) != value for key, value in SCOPE.items()):
        raise ValueError("Policy may not expand the approved repository/workflow scope")
    if integer(policy.get("max_age_hours"), "max_age_hours", 72) > 8760:
        raise ValueError("Unbounded age policy")
    integer(policy.get("keep_newest_per_branch"), "keep_newest_per_branch", 2)
    if integer(policy.get("max_deletions"), "max_deletions", 1) > 50:
        raise ValueError("At most 50 IDs may be planned")
    if policy.get("warning_budget_bytes") is not None:
        integer(policy["warning_budget_bytes"], "warning_budget_bytes", 1)
    pins = policy.get("pinned_artifacts")
    if not isinstance(pins, list):
        raise ValueError("An explicit pin list is required")
    ids = []
    for pin in pins:
        if not isinstance(pin, dict) or not isinstance(pin.get("reason"), str) or not pin["reason"].strip():
            raise ValueError("Every pin needs an ID and reason")
        ids.append(integer(pin.get("id"), "pin id", 1))
    if len(ids) != len(set(ids)):
        raise ValueError("Duplicate pinned IDs")
    return policy


def inventory(api):
    items, seen, total = [], set(), None
    for page in range(1, 1001):
        body = api.request("GET", REPO_ROUTE + f"/actions/artifacts?per_page=100&page={page}")
        if not isinstance(body, dict) or not isinstance(body.get("artifacts"), list):
            raise ValueError("Malformed artifact inventory page")
        count = integer(body.get("total_count"), "total_count")
        if total is not None and count != total:
            raise ValueError("Inventory changed during pagination; no complete snapshot")
        total = count
        rows = body["artifacts"]
        if len(rows) > 100:
            raise ValueError("Oversized inventory page")
        for item in rows:
            if not isinstance(item, dict) or not isinstance(item.get("name"), str):
                raise ValueError("Malformed artifact entry")
            artifact_id = integer(item.get("id"), "artifact id", 1)
            integer(item.get("size_in_bytes"), "artifact size")
            if artifact_id in seen:
                raise ValueError("Duplicate artifact ID across inventory pages")
            seen.add(artifact_id)
            items.append(item)
        if len(items) == total:
            return items
        if len(items) > total or len(rows) < 100:
            raise ValueError("Incomplete artifact inventory")
    raise ValueError("Artifact inventory exceeds the bounded pagination limit")


def remote_identity(api):
    repo = api.request("GET", REPO_ROUTE)
    if not isinstance(repo, dict) or (repo.get("id"), repo.get("full_name"), repo.get("default_branch")) != (
        SCOPE["repository_id"], SCOPE["repository"], "main",
    ):
        raise ValueError("Unexpected repository identity or default branch")
    workflow = api.request("GET", REPO_ROUTE + "/actions/workflows/flutter-dev-checks.yml")
    if not isinstance(workflow, dict) or workflow.get("path") != SCOPE["workflow_path"]:
        raise ValueError("Unexpected development workflow identity")
    return integer(workflow.get("id"), "workflow id", 1)


def validated_target(api, item, workflow_id, now, cache=None):
    if not isinstance(item, dict):
        raise ValueError("Malformed target artifact response")
    match = NAME.fullmatch(item.get("name", ""))
    if not match:
        raise ValueError("Malformed development APK artifact name")
    sha, run_id, attempt = match[1], int(match[2]), int(match[3])
    source = item.get("workflow_run")
    if not isinstance(source, dict) or (source.get("id"), source.get("head_sha")) != (run_id, sha):
        raise ValueError("Artifact name disagrees with its source run/commit")
    if any(source.get(key) != SCOPE["repository_id"] for key in ("repository_id", "head_repository_id")):
        raise ValueError("Artifact source repository is not authorized")
    branch = source.get("head_branch")
    if not isinstance(branch, str) or not branch.startswith(SCOPE["branch_prefix"]) or branch == SCOPE["branch_prefix"]:
        raise ValueError("Artifact source branch is not a development branch")
    created = timestamp(item.get("created_at"))
    expires = timestamp(item.get("expires_at"))
    if created > now or expires <= created or type(item.get("expired")) is not bool:
        raise ValueError("Contradictory artifact lifetime metadata")
    if not isinstance(item.get("digest"), str) or not re.fullmatch(r"sha256:[0-9a-f]{64}", item["digest"]):
        raise ValueError("A valid artifact digest is required")

    def read_run(route):
        if cache is not None and route in cache:
            return cache[route]
        run = api.request("GET", route)
        if not isinstance(run, dict):
            raise ValueError("Malformed source run")
        if cache is not None:
            cache[route] = run
        return run

    def check_run(run):
        if any(run.get(key) != value for key, value in {
            "id": run_id, "head_sha": sha, "head_branch": branch,
            "workflow_id": workflow_id, "path": SCOPE["workflow_path"],
        }.items()):
            raise ValueError("Run metadata disagrees with the approved artifact source")
        for key in ("repository", "head_repository"):
            if not isinstance(run.get(key), dict) or run[key].get("id") != SCOPE["repository_id"]:
                raise ValueError("Run belongs to another repository or a fork")
        if run.get("event") not in ("push", "workflow_dispatch"):
            raise ValueError("Unapproved source run event")
        integer(run.get("run_attempt"), "run_attempt", 1)
        if not isinstance(run.get("status"), str):
            raise ValueError("Missing source run status")
        if run["status"] == "completed" and (not isinstance(run.get("conclusion"), str) or not run["conclusion"]):
            raise ValueError("Completed run has no conclusion")

    run = read_run(REPO_ROUTE + f"/actions/runs/{run_id}")
    check_run(run)
    if run["run_attempt"] < attempt:
        raise ValueError("Artifact names a nonexistent future run attempt")
    active = run["status"] != "completed"
    if not active and attempt != run["run_attempt"]:
        old = read_run(REPO_ROUTE + f"/actions/runs/{run_id}/attempts/{attempt}")
        check_run(old)
        if old["run_attempt"] != attempt:
            raise ValueError("Source run attempt does not match the artifact name")
        active = old["status"] != "completed"
    return {
        "id": integer(item.get("id"), "artifact id", 1), "name": item["name"],
        "size_in_bytes": integer(item.get("size_in_bytes"), "artifact size"),
        "digest": item["digest"], "created_at": item["created_at"],
        "expires_at": item["expires_at"], "expired": item["expired"],
        "run_id": run_id, "attempt": attempt, "sha": sha, "branch": branch,
        "active": active,
    }


def capacity(items, budget):
    debug = [item for item in items if item["name"].startswith(SCOPE["artifact_prefix"])]
    size = sum(item["size_in_bytes"] for item in items)
    return {
        "artifact_count": len(items), "repository_bytes": size,
        "debug_apk_count": len(debug), "debug_apk_bytes": sum(item["size_in_bytes"] for item in debug),
        "warning_budget_bytes": budget,
        "warning_budget_exceeded": size >= budget if budget is not None else None,
        "account_quota_bytes": None,
    }


def build_plan(api, policy, now, budget):
    workflow_id = remote_identity(api)
    items = inventory(api)
    targets, cache = [], {}
    for item in items:
        if item["name"].startswith(policy["artifact_prefix"]):
            targets.append(validated_target(api, item, workflow_id, now, cache))
    pins = {pin["id"] for pin in policy["pinned_artifacts"]}
    kept, eligible, branches = [], [], {}
    for item in targets:
        if item["id"] in pins or item["active"] or item["expired"]:
            reason = "pinned" if item["id"] in pins else "active_run" if item["active"] else "expired"
            kept.append({"id": item["id"], "reason": reason})
        else:
            branches.setdefault(item["branch"], []).append(item)
    for branch in sorted(branches):
        group = sorted(branches[branch], key=lambda a: (timestamp(a["created_at"]), a["id"]), reverse=True)
        for index, item in enumerate(group):
            aged = timestamp(item["created_at"]) <= now - timedelta(hours=policy["max_age_hours"])
            excess = index >= policy["keep_newest_per_branch"]
            if aged or excess:
                eligible.append(dict(item, reason="age" if aged else "branch_count"))
            else:
                kept.append({"id": item["id"], "reason": "newest_within_age"})
    eligible.sort(key=lambda a: (timestamp(a["created_at"]), a["id"]))
    selected = eligible[:policy["max_deletions"]]
    return {
        "repository": policy["repository"], "workflow_id": workflow_id,
        "at": now.isoformat(), "capacity_before": capacity(items, budget),
        "selected": selected, "selected_count": len(selected),
        "selected_bytes": sum(item["size_in_bytes"] for item in selected),
        "backlog_count": len(eligible) - len(selected), "kept": kept,
        "kept_count": len(items) - len(selected),
    }


def maintain(api, policy, now, *, mode="dry-run", budget=None, emit=lambda event: None):
    validate_policy(policy)
    if mode not in ("dry-run", "apply") or now.tzinfo is None or now.utcoffset() != timedelta(0):
        raise ValueError("Maintenance requires an explicit mode and UTC clock")
    budget = policy.get("warning_budget_bytes") if budget is None else integer(budget, "warning budget", 1)
    plan = build_plan(api, policy, now, budget)
    report = {"schema": "etrack-artifact-maintenance-result-v1", "mode": mode,
              "result": "DRY_RUN" if mode == "dry-run" else "PASS", "plan": plan,
              "operations": [], "confirmed_freed_bytes": 0, "capacity_after": None}
    emit({"event": "plan", **plan})
    if mode == "dry-run" or not plan["selected"]:
        return report
    for item in plan["selected"]:
        route = REPO_ROUTE + "/actions/artifacts/" + str(item["id"])
        operation = {"id": item["id"], "bytes": item["size_in_bytes"], "outcome": "NOT_DELETED"}
        report["operations"].append(operation)
        try:
            current = validated_target(api, api.request("GET", route), plan["workflow_id"], now)
            if current != {key: value for key, value in item.items() if key != "reason"}:
                raise ValueError("Selected artifact or source run changed before DELETE")
            emit({"event": "delete_intent", "id": item["id"]})
            try:
                api.request("DELETE", route)
                operation.update(outcome="DELETED", http_status=204)
            except ApiError as exc:
                if exc.uncertain:
                    # A read-only reconciliation is not a retry and proves no byte credit.
                    operation["outcome"] = "DELETE_UNCERTAIN"
                    try:
                        api.request("GET", route)
                        operation["reconciliation"] = "still_present"
                    except ApiError as check:
                        operation["reconciliation"] = "absent" if check.status == 404 else "unresolved"
                raise
        except (ApiError, ValueError) as exc:
            operation["error"] = str(exc)
            report["result"] = "FAIL"
            emit({"event": "operation", **operation})
            break
        emit({"event": "operation", **operation})
    try:
        after = inventory(api)
        present = {item["id"] for item in after}
        deleted = [op for op in report["operations"] if op["outcome"] == "DELETED"]
        report["confirmed_freed_bytes"] = sum(op["bytes"] for op in deleted if op["id"] not in present)
        report["capacity_after"] = capacity(after, budget)
        report["remaining_selected_ids"] = [item["id"] for item in plan["selected"] if item["id"] in present]
        if any(op["id"] in present for op in deleted):
            raise ValueError("An HTTP 204 artifact is still present in the final inventory")
    except (ApiError, ValueError) as exc:
        report.update(result="FAIL", reconciliation_error=str(exc))
        if report["capacity_after"] is None:
            report["confirmed_freed_bytes"] = None
    return report


def ci_context(root, env):
    expected = {
        "GITHUB_ACTIONS": "true", "GITHUB_REPOSITORY": SCOPE["repository"],
        "GITHUB_REPOSITORY_ID": str(SCOPE["repository_id"]), "GITHUB_REF": "refs/heads/main",
        "GITHUB_WORKFLOW_REF": SCOPE["repository"] + "/" + MAINTENANCE_WORKFLOW + "@refs/heads/main",
    }
    if any(env.get(key) != value for key, value in expected.items()):
        raise ValueError("Maintenance is restricted to the trusted main-branch workflow")
    if env.get("GITHUB_EVENT_NAME") not in ("schedule", "workflow_dispatch"):
        raise ValueError("Unapproved maintenance event")
    if not env.get("GITHUB_WORKSPACE") or Path(os.path.abspath(env["GITHUB_WORKSPACE"])) != root:
        raise ValueError("Repository root must equal GITHUB_WORKSPACE")
    identity = subprocess.run(["git", "--no-optional-locks", "-c", "core.fsmonitor=false", "rev-parse", "HEAD"],
                              cwd=root, check=True, capture_output=True, text=True, timeout=15).stdout.strip()
    if not re.fullmatch(r"[0-9a-f]{40}", identity) or identity != env.get("GITHUB_SHA"):
        raise ValueError("Checkout does not match the maintenance workflow commit")


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo-root", type=Path, required=True)
    parser.add_argument("--mode", choices=("dry-run", "apply"),
                        default=os.environ.get("ARTIFACT_MAINTENANCE_MODE", "dry-run"))
    args = parser.parse_args(argv)
    try:
        root = checked_path(args.repo_root, Path("."))
        ci_context(root, os.environ)
        policy = validate_policy(json.loads(checked_path(root, POLICY_PATH).read_text(encoding="utf-8")))
        raw_budget = os.environ.get("CI_ARTIFACT_WARN_BYTES", "")
        if raw_budget and not re.fullmatch(r"[1-9][0-9]*", raw_budget):
            raise ValueError("CI_ARTIFACT_WARN_BYTES must be a positive byte count or unset")
        budget = int(raw_budget) if raw_budget else None
        api = GitHubAPI(os.environ.get("GITHUB_TOKEN", ""))
        run = make_directory(root, Path(".cache/artifact-maintenance/runs") / uuid.uuid4().hex, exclusive=True)
        journal = checked_path(root, run / "operations.jsonl")
        with journal.open("x", encoding="utf-8", newline="\n") as stream:
            def emit(event):
                line = diagnostic_json(event, os.environ)
                stream.write(line + "\n")
                stream.flush()
                os.fsync(stream.fileno())
                print("ARTIFACT_MAINTENANCE " + line, flush=True)
                if event["event"] == "plan":
                    usage = event["capacity_before"]
                    if usage["warning_budget_bytes"] is None:
                        print("ARTIFACT_CAPACITY warning_budget=unconfigured account_quota=unknown", flush=True)
                    elif usage["warning_budget_exceeded"]:
                        print("::warning title=Artifact storage budget::Repository artifact bytes exceed the configured "
                              "warning budget. This budget is not the GitHub account quota.", flush=True)

            report = maintain(api, policy, datetime.now(timezone.utc), mode=args.mode, budget=budget, emit=emit)
            with checked_path(root, run / "result.json").open("x", encoding="utf-8", newline="\n") as output:
                output.write(json.dumps(report, indent=2, ensure_ascii=True) + "\n")
            emit({"event": "result", **report})
            return 1 if report["result"] == "FAIL" else 0
    except (ApiError, OSError, ValueError, subprocess.SubprocessError) as exc:
        print("ARTIFACT_MAINTENANCE_ERROR " + redact_diagnostics(str(exc), os.environ), file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
