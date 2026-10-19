"""Scoped V3 adaptation of the V2 failure sealer; no platform operation."""
import copy
from datetime import datetime
import importlib.util
import json
from pathlib import Path
import sys

ROOT = Path(__file__).absolute().parents[1]
spec = importlib.util.spec_from_file_location("p44_frozen_bundle", ROOT / "Tools/acceptance/p44/bundle.py")
b = importlib.util.module_from_spec(spec)
spec.loader.exec_module(b)
PACKAGE, DATA = b.PACKAGE, b.DATA
C = "ba952497948a03c40cbd8baebbfc9228621fb44b"
TREE = "5427f4728cfc0e6a3b4760548fb6e03385922c6b"
HASH = "4FC05662F1BB9CA829BB8E769754229F6BEBC41CBB99A3ED38099DB1E5D7E2CD"
FAILED = "snapshots/before/protected-patches-rows8-0"
EXITS = {"formal-history": 0, "formal-configuration": 0, "formal-before": 1, "formal-privacy": 0}
PASSED = {"P44-HISTORY": "history", "P44-CONFIGURATION": "configuration", "P44-HYGIENE": "privacy"}


def digest(file):
    return b.sha(b.guard(file).read_bytes())


def checked(reference, base=DATA):
    file = b.guard(base / reference["path"])
    assert b.ref(file, base) == reference, "ORIGINAL_REFERENCE_CHANGED"
    return file


def context():
    assert Path.cwd().absolute() == ROOT and sys.flags.optimize == 0
    assert b.git("rev-parse", "HEAD") == C and b.git("rev-parse", "HEAD^{tree}") == TREE
    assert digest(b.CONTRACT).upper() == HASH
    assert not b.git("diff", "--name-only", "HEAD", "--", "Tools", "tests")
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
    for name in ("snapshots/before.json", "snapshots/after.json", "run-a/dispatch-intent.json", "run-b/dispatch-intent.json"):
        assert not b.guard(DATA / name).exists(), "UNEXPECTED_DOWNSTREAM_OBSERVATION"
    for item in contract["commands"]:
        if item["id"] not in EXITS:
            assert not b.guard(DATA / "commands" / (item["id"] + ".json")).exists()
    return contract, initial, plan, rules


def receipt(contract, name):
    value = b.read(DATA / "commands" / (name + ".json"))
    assert value["label"] == name and value["process_closed"] is True and value["signal"] is None
    assert value["exitCode"] == EXITS[name] and Path(value["cwd"]).absolute() == ROOT
    actual = " ".join(["node", "Tools/acceptance/p44/run.cjs", name, value["command"], *value["args"]])
    assert actual == next(item["command"] for item in contract["commands"] if item["id"] == name)
    checked(value["output"])
    return value, actual


def seal():
    contract, initial, plan, rules = context()
    for name in EXITS:
        receipt(contract, name)
    for name in ("history", "configuration"):
        result = b.read(DATA / (name + "-result.json"))
        assert result["ok"] is True and result["manifest_sha256"] == digest(DATA / "inputs/originals.json")
    precheck = b.read(DATA / "commands/formal-precheck.json")
    assert precheck["exitCode"] == 0 and precheck["process_closed"] is True
    assert "--previous-contract" in precheck["args"] and "--previous-matrix" in precheck["args"]
    checked(precheck["output"])
    inspection = b.inspector()
    oracle = inspection.Context(ROOT, DATA / "manifest.json")
    files = sorted(b.guard(DATA / "snapshots/before").glob("*.http.json"))
    assert len(files) == 13
    complete = []
    for file in files:
        record = b.read(file)
        request = b.read(checked(record["request"]))
        assert set(request) == {"sql"} and request["sql"].startswith("SELECT ")
        if record["completed"] is not True:
            assert file == DATA / (FAILED + ".http.json")
            continue
        assert record["status"] == 200
        checked(record["body"])
        checked(record["decoded_body"])
        body = json.loads(oracle.response(record, "POST", record["path"]))
        assert body["success"] is True and len(body["result"]) == 1
        result = body["result"][0]
        assert result["success"] is True and result["meta"]["rows_written"] == 0 and result["meta"]["changed_db"] is False
        complete.append({"envelope": b.ref(file, PACKAGE), "sql": request["sql"], "rows": len(result["results"]),
                         "wire_bytes": record["body"]["size_bytes"], "decoded_bytes": record["decoded_body"]["size_bytes"],
                         "started": record["started"], "ended": record["ended"]})
    assert len(complete) == 12
    failed = b.read(DATA / (FAILED + ".http.json"))
    assert failed["completed"] is False and failed["error_code"] == "ECONNRESET"
    assert all(name not in failed for name in ("status", "body", "decoded_body", "response_headers"))
    assert b.read(checked(failed["request"])) == {"sql": 'SELECT * FROM "patches" ORDER BY rowid LIMIT 8 OFFSET 0'}
    elapsed = round((datetime.fromisoformat(failed["ended"].replace("Z", "+00:00"))
                     - datetime.fromisoformat(failed["started"].replace("Z", "+00:00"))).total_seconds() * 1000)
    assert elapsed == 7087
    privacy = b.read(DATA / "privacy-result.json")
    assert privacy["ok"] is True and privacy["files_scanned"] == 377 and privacy["decoded_d1_scanned"] == 12
    b.write(DATA / "sealing/p44-v3-failure-closeout.py", b.guard(Path(__file__)).read_bytes())
    report = {
        "schema": "p44-v3-failure-closeout-v1", "task_id": "P4-4", "contract_id": contract["contract_id"],
        "round_id": initial["round_id"], "freeze_commit": C, "freeze_tree": TREE,
        "formal_observation_attempted": True, "final_matrix_result": "EVIDENCE_GAP", "p44_pass": False,
        "stage_failure": {"command_id": "formal-before", "command_exit_code": 1, "process_closed": True,
            "failure_owner": "environment", "phase": "before-state capture", "error_code": "ECONNRESET",
            "classification": "Connection reset before any HTTP response status/body was observed; no credential denial or gzip failure is established.",
            "http_status": None, "completed": False, "envelope_elapsed_ms": elapsed,
            "configured_http_deadline_seconds": 60, "request_started": failed["started"], "request_ended": failed["ended"],
            "operation": 'SELECT * FROM "patches" ORDER BY rowid LIMIT 8 OFFSET 0', "database_role": "protected Trace",
            "evidence": ["evidence/commands/formal-before.json", "evidence/commands/formal-before.log",
                         "evidence/" + FAILED + ".http.json", "evidence/" + FAILED + ".request.json",
                         "evidence/" + FAILED + "-reservation.json"]},
        "complete_new_observations_preserved": complete,
        "predecessor": {"source_bundle_commit": b.PREVIOUS_BUNDLE, "contract_sha256": b.PREVIOUS_SHA256,
            "matrix_sha256": b.PREVIOUS_MATRIX_SHA256, "manifest": b.ref(DATA / b.PREDECESSOR, PACKAGE),
            "complete_http_originals_retained": 35, "incomplete_http_originals_retained": 2},
        "total_readonly_originals": {"complete": 47, "incomplete": 3, "successful_rehearsals_replayed": 0},
        "matrix_disposition": {"raw_state_result": "NOT_OBSERVED", "raw_state_observed": None,
            "reason": "Before/negatives/after are one frozen aggregate; only before executed. Do not fabricate downstream exits to label that aggregate FAIL.",
            "initial_not_run_matrix": b.ref(PACKAGE / "evidence-matrix.json", PACKAGE),
            "actual_rerun_plan": b.ref(PACKAGE / "rerun-plan.json", PACKAGE), "previous_round_id": plan["previous_round_id"]},
        "privacy_scope": "The completed formal scan covered all 377 then-present files, five ZIP members and all 12 decoded D1 bodies. Later generated sealing metadata and final matrices also require the scoped staged-byte privacy audit; the successful scan is not replayed.",
        "not_executed_follow_on_plan_commands": [item["id"] for item in contract["commands"] if item["id"] not in EXITS],
        "boundary": "Zero A/B dispatch, reviewer action, registration, R2 object write, firmware publication, gate unlock or device operation. No unchanged deployment/CI was replayed.",
        "next": "Preserve all complete originals and all three failures. Admit only a justified minimal read-only recovery under the actual lineage and rerun plan; no automatic replay of mutations or successful observations.",
    }
    b.write(DATA / "failure-report.json", report)
    value = copy.deepcopy(initial)
    value["overall_result"] = "EVIDENCE_GAP"
    for name in EXITS:
        original, actual = receipt(contract, name)
        value["commands"].append({"id": name, "command": actual, "exit_code": original["exitCode"],
                                  "output_evidence": "evidence/" + original["output"]["path"]})
    for item in value["criteria"]:
        item["evidence"] = ["evidence/failure-report.json"]
        item["notes"] = "NOT_OBSERVED: before-state collection stopped on a pre-response ECONNRESET. No downstream result or action is inferred."
        if item["id"] in PASSED:
            name = PASSED[item["id"]]
            assert b.read(DATA / (name + "-result.json"))["ok"] is True
            item.update(result="PASS", observed=True, evidence=["evidence/" + name + "-result.json",
                "evidence/commands/formal-" + name + ".json", "evidence/commands/formal-" + name + ".log",
                "evidence/inputs/" + ("lifecycle.json" if name == "privacy" else "originals.json")])
            item["notes"] = "EXECUTED offline original-byte evaluation, not a repeated CI, deployment or rehearsal; retained warnings, failures and privacy limits apply."
        elif item["id"] == "P44-RAW-STATE":
            item["evidence"] += report["stage_failure"]["evidence"] + ["evidence/" + b.PREDECESSOR, "rerun-plan.json"]
            item["evidence"] += [row["envelope"]["path"] for row in complete]
            item["notes"] = "Partially attempted NOT_OBSERVED aggregate: 12 new gzip D1 responses completed, then protected patches rows8 OFFSET0 reset before HTTP headers (ECONNRESET, 7087 ms). All 47 complete and three failed originals remain; negatives/after/A/B were not executed."
    for artifact in contract["artifacts"]:
        file = b.guard(PACKAGE / artifact["path"])
        if file.is_file():
            value["artifacts"].append({"id": artifact["id"], "path": artifact["path"], "sha256": digest(file), "size": file.stat().st_size})
    files = [file for file in DATA.rglob("*") if file.is_file()] + [PACKAGE / "evidence-matrix.json", PACKAGE / "rerun-plan.json"]
    value["evidence_hashes"] = {file.relative_to(PACKAGE).as_posix(): digest(file) for file in sorted(files)}
    assert all(value[key] is None for key in ("previous_matrix_sha256", "rerun_plan_path", "rerun_plan_sha256"))
    assert not rules.validate_matrix(value, contract, HASH) and not rules.validate_planned_execution(value, contract, plan)
    b.write(PACKAGE / "final-evidence-matrix.json", value)
    print(json.dumps({"overall": value["overall_result"], "criteria": {item["id"]: item["result"] for item in value["criteria"]},
        "matrix": b.ref(PACKAGE / "final-evidence-matrix.json", PACKAGE), "evidence_files": len(value["evidence_hashes"]),
        "new_complete_http": 12, "new_incomplete_http": 1, "commands": EXITS, "platform_operations": 0}))


assert len(sys.argv) == 1
seal()
