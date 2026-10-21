"""V3 failure-sealer adaptation: preview, prepare metadata, then seal after privacy."""
import copy
from datetime import datetime
import importlib.util
import json
from pathlib import Path
import sys
from urllib.parse import quote

ROOT = Path(__file__).absolute().parents[1]
spec = importlib.util.spec_from_file_location("p44_frozen_bundle", ROOT / "Tools/acceptance/p44/bundle.py")
b = importlib.util.module_from_spec(spec)
spec.loader.exec_module(b)
PACKAGE, DATA = b.PACKAGE, b.DATA
C = "2756ca95e26ec636216313271708b3304d61a5cc"
TREE = "77549b4b756f1e88de8b854b4673857021a65783"
HASH = "86764FA47B8C52D748BF93B83C5735352CEAB69519D8FFCC4C6BFC706F8939B5"
FAILED = "snapshots/after/protected-audit_logs-rows8-16"
EXITS = {
    "formal-history": 0, "formal-configuration": 0, "formal-before": 0,
    "formal-negatives": 0, "formal-dispatch-a": 0, "formal-finish-a": 0,
    "formal-dispatch-b": 0, "formal-finish-b": 0, "formal-assemble-rehearsal": 0,
    "formal-rehearsal": 0, "formal-readbacks": 0, "formal-production-preflight": 0,
    "formal-after": 1, "formal-privacy": 0,
}
PASSED = {"P44-HISTORY", "P44-CONFIGURATION", "P44-RAW-RUNS", "P44-REHEARSAL",
          "P44-RAW-READBACK", "P44-HYGIENE"}
ARCHIVE = DATA / "sealing/p44-v4-gap-close.py"
REPORT = DATA / "failure-report.json"
FINAL = PACKAGE / "final-evidence-matrix.json"


def digest(file):
    return b.sha(b.guard(file).read_bytes())


def checked(reference, base=DATA):
    file = b.guard(base / reference["path"])
    assert b.ref(file, base) == reference, "ORIGINAL_REFERENCE_CHANGED"
    return file


def receipt(contract, name):
    value = b.read(DATA / "commands" / (name + ".json"))
    assert value["label"] == name and value["process_closed"] is True and value["signal"] is None
    assert value["exitCode"] == EXITS[name] and Path(value["cwd"]).absolute() == ROOT
    actual = " ".join(["node", "Tools/acceptance/p44/run.cjs", name, value["command"], *value["args"]])
    assert actual == next(item["command"] for item in contract["commands"] if item["id"] == name)
    checked(value["output"])
    return value, actual


def context(final=False):
    assert Path.cwd().absolute() == ROOT and sys.flags.optimize == 0 and sys.dont_write_bytecode
    assert b.guard(Path(__file__)) == ROOT / ".cache/p44-v4-gap-close.py"
    assert b.git("rev-parse", "HEAD") == C and b.git("rev-parse", "HEAD^{tree}") == TREE
    assert digest(b.CONTRACT).upper() == HASH
    assert not b.git("diff", "--name-only", "HEAD", "--", "Tools", "tests")
    for file in (ARCHIVE, REPORT, FINAL):
        b.guard(file)
        assert file.exists() == (final and file != FINAL), "SEALING_OUTPUT_STATE"
    contract, initial = b.read(b.CONTRACT), b.read(PACKAGE / "evidence-matrix.json")
    assert contract["freeze_commit"] == C and contract["freeze_tree"] == TREE
    assert initial["overall_result"] == "NOT_RUN" and not initial["commands"] and not initial["artifacts"]
    assert all(item["result"] == "NOT_OBSERVED" for item in initial["criteria"])
    rules = b.validator()
    assert not rules.validate_contract(contract) and not rules.validate_matrix(initial, contract, HASH)
    plan = b.read(PACKAGE / "rerun-plan.json")
    assert plan == b.computed_plan(contract, initial) and not plan["reusable_criteria"]
    assert set(plan["required_commands"]) == {item["id"] for item in contract["commands"]}
    assert b.read(DATA / b.PREDECESSOR) == b.predecessor_plan()[1]
    for name in ("snapshots/after.json", "manifest.json", "approvals-result.json", "states-result.json"):
        assert not b.guard(DATA / name).exists(), "UNEXPECTED_DOWNSTREAM_OBSERVATION"
    for item in contract["commands"]:
        name = item["id"]
        executed = name in EXITS and (final or name != "formal-privacy")
        assert (DATA / "commands" / (name + ".json")).exists() == executed, "COMMAND_RECEIPT_SET"
        if executed:
            receipt(contract, name)
    for name, key in (("formal-precheck", "precheck"), ("formal-rerun-plan", "plan")):
        value = b.read(DATA / "commands" / (name + ".json"))
        assert value["exitCode"] == 0 and value["process_closed"] is True and value["signal"] is None
        assert Path(value["cwd"]).absolute() == ROOT
        assert " ".join([value["command"], *value["args"]]) == b.validation_commands()[key]
        checked(value["output"])
    return contract, initial, plan, rules


def successful_inputs():
    for name in ("history", "configuration"):
        result = b.read(DATA / (name + "-result.json"))
        assert result["ok"] is True and result["manifest_sha256"] == digest(DATA / "inputs/originals.json")
    inspection = b.inspector()
    oracle = inspection.Context(ROOT, DATA / "rehearsal-manifest.json")
    manifest = b.read(oracle.manifest)
    target = inspection.target_input(oracle, manifest)
    runs = {}
    attestation = b.read(DATA / "reviewer-attestation.json")
    assert len(attestation["actions"]) == 2 and attestation["reviewer"] == "Eitan-S-23"
    for role, run_id, conclusion, state in (("a", 39313672925, "failure", "rejected"),
                                           ("b", 39351100037, "success", "approved")):
        capture = manifest["run_" + role]
        run = inspection.run_object(oracle, capture, target)
        inspection.run_object(oracle, capture, target, waiting=True)
        inspection.dispatch_input(oracle, capture, target)
        inspection.checked_jobs(oracle, capture, target, success=role == "b")
        original = b.read(DATA / ("run-" + role + "/final.json"))
        assert run == original["run"] and run["id"] == run_id and run["conclusion"] == conclusion
        reviews = json.loads(oracle.response(capture["reviews"], "GET", capture["reviews"]["path"]))
        assert reviews == original["reviews"] and len(reviews) == 1
        assert reviews[0]["state"] == state and reviews[0]["user"]["login"] == "Eitan-S-23"
        assert [item["name"] for item in reviews[0]["environments"]] == ["firmware-rehearsal"]
        action = next(item for item in attestation["actions"] if item["run_id"] == run_id)
        assert action["state"] == state and action["run_attempt"] == 1 and action["basis"] == "owner_response"
        checked(action["evidence"])
        runs[role] = run
    assert inspection.timestamp(runs["a"]["updated_at"]) < inspection.timestamp(runs["b"]["created_at"])
    result = b.read(DATA / "rehearsal-result.json")
    assert result["ok"] is True and result["manifest_sha256"] == digest(oracle.manifest)
    assert result["observed"]["run_id"] == runs["b"]["id"] and result["observed"]["commit_sha"] == C
    readbacks = b.read(DATA / "readbacks.json")
    assets = result["observed"]["metadata"]["assets"]
    assert len(readbacks) == 3 and set(readbacks) == {asset["r2Key"] for asset in assets}
    for asset in assets:
        record = readbacks[asset["r2Key"]]
        route = "/" + inspection.RESOURCES["staging"][1] + "/" + quote(asset["r2Key"], safe="/")
        raw = oracle.response(record, "GET", route)
        assert len(raw) == asset["sizeBytes"] and b.sha(raw) == asset["sha256"]
    preflight = b.read(DATA / "production-preflight-result.json")
    assert preflight["ok"] is True
    oracle.response(preflight["http"], "POST", "/api/ci/firmware/preflight")
    checked(preflight["http"]["request"])
    assert b.read(DATA / "negatives.json")["ok"] is True
    assert set(b.read(DATA / "snapshots/before.json")["databases"]) == {"production", "protected", "staging"}
    return inspection, oracle


def milliseconds(record):
    return round((datetime.fromisoformat(record["ended"].replace("Z", "+00:00"))
                  - datetime.fromisoformat(record["started"].replace("Z", "+00:00"))).total_seconds() * 1000)


def failure_report(contract, initial, plan):
    inspection, oracle = successful_inputs()
    files = sorted(b.guard(DATA / "snapshots/after").glob("*.http.json"))
    assert len(files) == 32
    complete = []
    for file in files:
        record = b.read(file)
        if record["completed"] is not True:
            assert file == DATA / (FAILED + ".http.json")
            continue
        raw = oracle.response(record, record["method"], record["path"])
        if record["method"] == "POST":
            request = b.read(checked(record["request"]))
            assert set(request) == {"sql"} and request["sql"].startswith("SELECT ")
            body = json.loads(raw)
            assert body["success"] is True and len(body["result"]) == 1
            result = body["result"][0]
            assert result["success"] is True and result["meta"]["rows_written"] == 0 and result["meta"]["changed_db"] is False
        else:
            assert record["method"] == "GET" and file.name == "production-r2-1.http.json"
        complete.append(b.ref(file, PACKAGE))
    assert len(complete) == 31
    failed = b.read(DATA / (FAILED + ".http.json"))
    assert digest(DATA / (FAILED + ".http.json")) == "d3e047b1375d4399b505ec4c9adcfc559d8e845b3642364562223af8470452c5"
    assert failed["completed"] is False and failed["error_code"] == "UND_ERR_CONNECT_TIMEOUT"
    assert all(name not in failed for name in ("status", "body", "decoded_body", "response_headers", "retry_reservation"))
    assert failed["request_attempts"] == 1 and len(failed["request_failures"]) == 1
    attempt_file = checked(failed["request_failures"][0])
    attempt = b.read(attempt_file)
    assert attempt_file == DATA / (FAILED + "-request-failure-1.json")
    assert attempt["attempt"] == 1 and attempt["error_code"] == failed["error_code"]
    assert attempt["final_response_received"] is False and attempt["received_body_bytes"] == 0
    assert attempt["informational_seen"] is False and attempt["informational_count"] == 0 and attempt["first_information"] is None
    sql = 'SELECT * FROM "audit_logs" ORDER BY rowid LIMIT 8 OFFSET 16'
    assert b.read(checked(failed["request"])) == {"sql": sql} and attempt["request"] == failed["request"]
    reservation = b.read(DATA / (FAILED + "-reservation.json"))
    assert reservation["request"] == failed["request"] and reservation["started"] == failed["started"]
    assert milliseconds(attempt) == 10500 and milliseconds(failed) == 13871
    assert not b.guard(DATA / (FAILED + "-retry-2-reservation.json")).exists()
    return {
        "schema": "p44-v4-failure-closeout-v1", "task_id": "P4-4", "contract_id": contract["contract_id"],
        "round_id": initial["round_id"], "freeze_commit": C, "freeze_tree": TREE,
        "formal_observation_attempted": True, "final_matrix_result": "EVIDENCE_GAP", "p44_pass": False,
        "stage_failure": {"command_id": "formal-after", "command_exit_code": 1, "process_closed": True,
            "failure_owner": "environment", "phase": "after-state capture", "error_code": failed["error_code"],
            "classification": "Connection attempt timed out before informational/final HTTP headers or body. No credential denial, D1 error or decode failure is established.",
            "http_status": None, "completed": False, "request_attempts": 1, "automatic_retries": 0,
            "request_elapsed_ms": milliseconds(attempt), "envelope_elapsed_ms": milliseconds(failed),
            "configured_http_deadline_seconds": 60, "request_started": attempt["started"], "request_ended": attempt["ended"],
            "operation": sql, "database_role": "protected Trace",
            "evidence": ["evidence/commands/formal-after.json", "evidence/commands/formal-after.log",
                         "evidence/" + FAILED + ".http.json", "evidence/" + FAILED + ".request.json",
                         "evidence/" + FAILED + "-reservation.json", "evidence/" + FAILED + "-request-failure-1.json"]},
        "complete_after_observations_preserved": complete,
        "after_http_originals": {"complete": 31, "incomplete": 1, "complete_d1": 30, "complete_r2": 1},
        "successful_observations_preserved": {"run_a": 39313672925, "run_a_state": "rejected",
            "run_b": 39351100037, "run_b_state": "approved", "run_b_conclusion": "success",
            "attempts": {"a": 1, "b": 1}, "staging_dispatches": 2, "successful_rehearsals_replayed": 0,
            "evidence": ["evidence/reviewer-attestation.json", "evidence/run-a/final.json", "evidence/run-b/final.json",
                         "evidence/rehearsal-result.json", "evidence/readbacks.json", "evidence/production-preflight-result.json"]},
        "predecessor": {"source_bundle_commit": b.PREVIOUS_BUNDLE, "contract_sha256": b.PREVIOUS_SHA256,
            "matrix_sha256": b.PREVIOUS_MATRIX_SHA256, "manifest": b.ref(DATA / b.PREDECESSOR, PACKAGE),
            "complete_http_originals_retained": 47, "incomplete_http_originals_retained": 3},
        "matrix_disposition": {"raw_state_result": "NOT_OBSERVED", "raw_state_observed": None,
            "reason": "Before and negatives completed; after is incomplete. APPROVALS lacks assemble-complete/approvals execution; ISOLATION was not executed. Do not infer missing results from successful A/B or fabricate exits.",
            "initial_not_run_matrix": b.ref(PACKAGE / "evidence-matrix.json", PACKAGE),
            "actual_rerun_plan": b.ref(PACKAGE / "rerun-plan.json", PACKAGE), "previous_round_id": plan["previous_round_id"]},
        "not_executed_observation_commands": [item["id"] for item in contract["commands"] if item["id"] not in EXITS],
        "privacy_scope": "Prepared metadata precedes the one formal-privacy execution. The final matrix must consume its real closed receipt and successful result, not this report as a privacy verdict. Final sealing bytes remain subject to root staged-byte review.",
        "boundary": "A was personally rejected; B was personally approved and completed the one new staging chain. No production release, gate unlock or device operation. Incomplete after data cannot prove full production/protected-resource isolation.",
        "next": "Preserve B success and all originals. Only justified, separately admitted minimal missing read-only collection/evaluation may resume; no new workflow dispatch, upload or registration.",
    }


def seal(contract, initial, plan, rules, report):
    assert ARCHIVE.read_bytes() == b.guard(Path(__file__)).read_bytes(), "SEALER_SOURCE_CHANGED"
    assert b.read(REPORT) == report, "FAILURE_REPORT_CHANGED"
    privacy = b.read(DATA / "privacy-result.json")
    assert privacy["ok"] is True and not privacy["failed_paths"] and privacy["lifecycle_checked"] is True
    excluded = {DATA / "commands/formal-privacy.log", DATA / "commands/formal-privacy.json", DATA / "privacy-result.json"}
    files = [b.guard(file) for file in DATA.rglob("*") if file.is_file()]
    assert privacy["files_scanned"] == sum(file not in excluded for file in files), "PRIVACY_FILE_SET_CHANGED"
    value = copy.deepcopy(initial)
    value["overall_result"] = "EVIDENCE_GAP"
    for name in EXITS:
        original, actual = receipt(contract, name)
        value["commands"].append({"id": name, "command": actual, "exit_code": original["exitCode"],
                                  "output_evidence": "evidence/" + original["output"]["path"]})
    for item in value["criteria"]:
        definition = next(row for row in contract["criteria"] if row["id"] == item["id"])
        item["evidence"] = ["evidence/failure-report.json"]
        item["notes"] = "NOT_OBSERVED: required downstream assembly/evaluation was not executed; actual human actions and business success remain preserved separately."
        if item["id"] in PASSED:
            item.update(result="PASS", observed=True)
            item["evidence"] += [row["path"] for row in contract["artifacts"] if row["id"] in definition["artifact_ids"]]
            item["evidence"] += ["evidence/commands/" + name + ".json" for name in definition["command_ids"]]
            item["notes"] = "EXECUTED with actual command receipts and original-byte checks. No repeated business operation, production release or gate unlock; failure and privacy limitations remain."
        elif item["id"] == "P44-RAW-STATE":
            item["evidence"] += report["stage_failure"]["evidence"] + ["evidence/" + b.PREDECESSOR, "rerun-plan.json",
                "evidence/snapshots/before.json", "evidence/negatives.json"] + [row["path"] for row in report["complete_after_observations_preserved"]]
            item["notes"] = "Partially attempted NOT_OBSERVED aggregate: before/negatives succeeded; 31 after responses completed before a 10500 ms request connect timeout (13871 ms envelope). formal-after exited 1; after.json is absent. No complete isolation verdict is inferred."
    for artifact in contract["artifacts"]:
        file = b.guard(PACKAGE / artifact["path"])
        if file.is_file():
            value["artifacts"].append({"id": artifact["id"], "path": artifact["path"], "sha256": digest(file), "size": file.stat().st_size})
    files += [PACKAGE / "evidence-matrix.json", PACKAGE / "rerun-plan.json"]
    value["evidence_hashes"] = {file.relative_to(PACKAGE).as_posix(): digest(file) for file in sorted(files)}
    assert all(value[key] is None for key in ("previous_matrix_sha256", "rerun_plan_path", "rerun_plan_sha256"))
    assert not rules.validate_matrix(value, contract, HASH) and not rules.validate_planned_execution(value, contract, plan)
    b.write(FINAL, value)
    print(json.dumps({"overall": value["overall_result"], "criteria": {item["id"]: item["result"] for item in value["criteria"]},
        "matrix": b.ref(FINAL, PACKAGE), "commands": EXITS, "sealer_platform_operations": 0,
        "final_validation_command": b.validation_commands()["final"], "final_validation_log": "Outside evidence DATA"}))


def main():
    assert len(sys.argv) == 2 and sys.argv[1] in {"preview", "prepare", "seal"}
    mode = sys.argv[1]
    contract, initial, plan, rules = context(final=mode == "seal")
    report = failure_report(contract, initial, plan)
    if mode == "preview":
        print(json.dumps(report, indent=2))
    elif mode == "prepare":
        b.write(ARCHIVE, b.guard(Path(__file__)).read_bytes())
        b.write(REPORT, report)
        print(json.dumps({"source": b.ref(ARCHIVE, PACKAGE), "report": b.ref(REPORT, PACKAGE),
                          "next": "Run the existing formal-privacy once, then seal; final validation logs stay outside DATA."}))
    else:
        seal(contract, initial, plan, rules, report)


if __name__ == "__main__":
    main()
