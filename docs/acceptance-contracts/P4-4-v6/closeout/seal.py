"""Seal the closed C6 observation as EVIDENCE_GAP without touching its DATA."""
import copy
from datetime import datetime
import importlib.util
import json
from pathlib import Path
import sys

ROOT = Path(__file__).absolute().parents[2]
spec = importlib.util.spec_from_file_location("p44_base_bundle", ROOT / "Tools/acceptance/p44/bundle.py")
b = importlib.util.module_from_spec(spec)
spec.loader.exec_module(b)
rules = b.validator()
PACKAGE = ROOT / "docs/acceptance-contracts/P4-4-v6"
DATA = PACKAGE / "evidence"
CONTRACT = ROOT / "docs/acceptance-contracts/P4-4-v6.contract.json"
C6 = "6fffaa25442bdcd863f3a3f4e93e20ebe180a2c1"
TREE = "8f077f4c2f74acc453d279cc9b21a74ca68776a8"
CONTRACT_HASH = "dbb6bf4bf986b320dfe91a7a3b6817cd4031a156be310b9f87bbad51e65120a9"
INITIAL_HASH = "800ed3630af106d38e922e1b7a884b9359421e4e58612795ab20d801f57e2141"
PLAN_HASH = "f2fc380ca47fa7104e2debb5454058a2abf19693a336a5851accd9c1018af8ac"
DESCRIPTOR_HASH = "673b18612e00f77a850f1b3be8f3ee48e3330d8394163c92239819e0f00b79ff"
REUSED = {"P44-CONFIGURATION", "P44-RAW-RUNS", "P44-REHEARSAL", "P44-RAW-READBACK"}
EXITS = {"formal-history": 0, "formal-before": 0, "formal-negatives": 0,
         "formal-after": 1, "formal-privacy": 0}
REPORT = PACKAGE / "closeout/failure-report.json"
ARCHIVE = PACKAGE / "closeout/seal.py"
FINAL = PACKAGE / "final-evidence-matrix.json"


def digest(file):
    return b.sha(b.guard(file).read_bytes())


def reference(file):
    return b.ref(file, PACKAGE)


def elapsed(record):
    def parse(value):
        return datetime.fromisoformat(value.replace("Z", "+00:00"))
    return round((parse(record["ended"]) - parse(record["started"])).total_seconds() * 1000)


def receipt(name, contract):
    record = b.read(DATA / "recovery-commands-v6" / (name + ".json"))
    assert record["label"] == name and record["closed"] is True and record["process_closed"] is True
    assert record["exitCode"] == EXITS[name] and record["signal"] is None and record["spawn_failed"] is False
    assert Path(record["cwd"]).absolute() == ROOT
    command = " ".join(["node", "Tools/ota/p44-after-recovery.cjs", "run", name, record["command"], *record["args"]])
    assert command == next(row["command"] for row in contract["commands"] if row["id"] == name)
    assert record["output"]["path"] == "recovery-commands-v6/" + name + ".log"
    b.history_reference(DATA, record["output"])
    reservation = b.read(DATA / "recovery-commands-v6" / (name + "-reservation.json"))
    assert reservation == {key: record[key] for key in ("label", "command", "args", "cwd", "started")}
    return {"id": name, "command": command, "exit_code": record["exitCode"],
            "output_evidence": "evidence/" + record["output"]["path"]}


def prepare():
    assert Path.cwd().absolute() == ROOT and sys.dont_write_bytecode and sys.flags.optimize == 0
    assert b.git("rev-parse", "HEAD") == C6 and b.git("rev-parse", "HEAD^{tree}") == TREE
    for name in ("Tools/acceptance/p44/bundle.py", "Tools/acceptance/validate_bundle.py"):
        assert b.guard(ROOT / name).read_bytes() == b.git_bytes("show", C6 + ":" + name), "SEALING_HELPER_CHANGED"
    assert digest(CONTRACT) == CONTRACT_HASH
    assert digest(PACKAGE / "evidence-matrix.json") == INITIAL_HASH
    assert digest(PACKAGE / "rerun-plan.json") == PLAN_HASH
    assert digest(DATA / "inputs/after-recovery-v6.json") == DESCRIPTOR_HASH
    for file in (REPORT, ARCHIVE, FINAL):
        assert not b.guard(file).exists(), "CLOSEOUT_ALREADY_EXISTS"
    contract, initial, plan = (b.read(file) for file in (CONTRACT, PACKAGE / "evidence-matrix.json", PACKAGE / "rerun-plan.json"))
    descriptor = b.read(DATA / "inputs/after-recovery-v6.json")
    source_contract = json.loads(b.history_reference(DATA, descriptor["source_contract"]))
    source_matrix = json.loads(b.history_reference(DATA, descriptor["source_matrix"]))
    parent = json.loads(b.history_reference(DATA, descriptor["predecessor_contract"]))
    previous = json.loads(b.history_reference(DATA, descriptor["predecessor_matrix"]))
    sources = {descriptor["source_matrix"]["sha256"].upper(): {
        "contract": source_contract, "matrix": source_matrix,
        "contract_sha256": descriptor["source_contract"]["sha256"].upper(),
        "matrix_sha256": descriptor["source_matrix"]["sha256"].upper()}}
    assert not rules.validate_contract(contract)
    assert not rules.validate_matrix(initial, contract, CONTRACT_HASH.upper())
    assert not rules.validate_external_inputs(contract, PACKAGE)
    assert initial["overall_result"] == "NOT_RUN" and not initial["commands"] and not initial["artifacts"]
    actual_plan = rules.compute_rerun_plan(contract, parent, previous,
        current_contract_sha256=CONTRACT_HASH.upper(), previous_contract_sha256=descriptor["predecessor_contract"]["sha256"].upper(),
        previous_matrix_sha256=descriptor["predecessor_matrix"]["sha256"].upper(),
        current_round_id=initial["round_id"], repo_root=ROOT, reuse_sources=sources)
    assert plan == actual_plan and set(plan["reusable_criteria"]) == REUSED, "RERUN_PLAN_CHANGED"
    names = set(EXITS) | {"formal-precheck", "formal-rerun-plan"}
    expected_receipts = {name + suffix for name in names for suffix in (".json", "-reservation.json")}
    assert {file.name for file in (DATA / "recovery-commands-v6").glob("*.json")} == expected_receipts
    for name in EXITS:
        receipt(name, contract)
    for name in ("snapshots/after.json", "manifest.json", "approvals-result.json", "states-result.json",
                 "recovery-v6/after-result.json", "recovery-v6/assemble-result.json"):
        assert not b.guard(DATA / name).exists(), "UNEXPECTED_DOWNSTREAM_RESULT"
    history = b.read(DATA / "recovery-v6/history-result.json")
    assert history["ok"] is True and history["manifest_sha256"] == digest(DATA / "inputs/originals.json")
    for kind in ("before", "negatives"):
        result = b.read(DATA / "recovery-v6" / (kind + "-result.json"))
        assert result["ok"] is True and result["kind"] == kind and result["source"] == descriptor[kind]
        assert result["platform_operations"] == 0 and result["source_commit"] == descriptor["source_commit"]
        assert result["predecessor_bundle_commit"] == descriptor["predecessor_bundle_commit"]
        b.history_reference(DATA, result["source"])
    privacy = b.read(DATA / "recovery-v6/privacy-result.json")
    assert privacy["ok"] is True and privacy["lifecycle_checked"] is True and not privacy["failed_paths"]
    assert (privacy["files_scanned"], privacy["decoded_d1_scanned"], privacy["zip_members_scanned"]) == (1411, 141, 132)
    files = [b.guard(file) for file in DATA.rglob("*") if file.is_file()]
    hashes = {file.relative_to(PACKAGE).as_posix(): digest(file) for file in files}
    excluded = {"recovery-commands-v6/formal-privacy.json", "recovery-commands-v6/formal-privacy.log", "recovery-v6/privacy-result.json"}
    scanned = {name.removeprefix("evidence/"): value for name, value in hashes.items() if name.removeprefix("evidence/") not in excluded}
    assert privacy["file_hashes"] == scanned and len(scanned) == 1411, "POST_PRIVACY_BYTES_CHANGED"
    tail_files = sorted((DATA / "snapshots/after-tail-v6").glob("*.http.json"))
    complete = [file for file in tail_files if b.read(file).get("completed") is True]
    failed = [file for file in tail_files if b.read(file).get("completed") is False]
    assert len(complete) == 39 and len(failed) == 1 and len(tail_files) == 40
    assert failed[0].name == "protected-patches-rows8-16.http.json"
    assert all(b.read(file)["request_attempts"] == 1 for file in tail_files)
    assert all(b.read(file)["status"] == 200 for file in complete)
    failure = b.read(failed[0])
    assert failure["error_code"] == "UND_ERR_SOCKET" and len(failure["request_failures"]) == 1
    request_failure = json.loads(b.history_reference(DATA, failure["request_failures"][0]))
    assert request_failure["error_code"] == "UND_ERR_SOCKET" and request_failure["attempt"] == 1
    assert request_failure["final_response_received"] is False and request_failure["received_body_bytes"] == 0
    assert request_failure["informational_seen"] is False and request_failure["informational_count"] == 0
    assert len(descriptor["after_complete"]) == 31 and len(descriptor["after_failed"]) == 1
    reservation = b.read(DATA / "recovery-v6/after-reservation.json")
    assert reservation["tool_commit"] == C6 and reservation["product_commit"] == descriptor["source_commit"]
    assert (reservation["old_complete"], reservation["old_failed"], reservation["first_missing"]) == (31, 1, "protected-audit_logs-rows8-16")
    command = b.read(DATA / "recovery-commands-v6/formal-after.json")
    assert command["output"]["sha256"] == "3905175dfdac979c90a7e5387e8f7fca9605626c29a6c709f6ddb245b1cc957e"
    report = {"schema": "p44-v6-failure-closeout-v1", "task_id": "P4-4", "contract_id": contract["contract_id"],
        "round_id": initial["round_id"], "freeze_commit": C6, "freeze_tree": TREE,
        "product_commit": descriptor["source_commit"], "final_matrix_result": "EVIDENCE_GAP", "p44_pass": False,
        "failure": {"command_id": "formal-after", "exit_code": 1, "process_closed": True,
            "started": command["started"], "ended": command["ended"], "elapsed_ms": elapsed(command),
            "classification": "Pre-response transport failure; no product-failure conclusion and no retry.",
            "first_missing": "protected-patches-rows8-16", "error_code": "UND_ERR_SOCKET", "attempts": 1,
            "final_response_received": False, "informational_count": 0, "received_body_bytes": 0,
            "envelope": reference(failed[0]), "request_failure": {**failure["request_failures"][0], "path": "evidence/" + failure["request_failures"][0]["path"]},
            "command_receipt": reference(DATA / "recovery-commands-v6/formal-after.json")},
        "retained": {"c4_complete_after": 31, "c6_complete_after": 39, "total_complete_after": 70,
            "c6_read_only_http_attempts": 40, "c6_automatic_retries": 0,
            "c6_complete_envelopes": [reference(file) for file in complete],
            "run_a": 39313672925, "run_b": 39351100037, "business_replays": 0},
        "predecessor": {key: descriptor[key] for key in ("predecessor_commit", "predecessor_bundle_commit", "predecessor_index_commit", "predecessor_contract", "predecessor_matrix")},
        "disposition": {"reused_pass": sorted(REUSED), "executed_pass": ["P44-HISTORY", "P44-HYGIENE"],
            "not_observed": ["P44-RAW-STATE", "P44-APPROVALS", "P44-ISOLATION"],
            "not_executed": ["formal-assemble-complete", "formal-approvals", "formal-states"]},
        "privacy": {"closed_result": reference(DATA / "recovery-v6/privacy-result.json"), "unchanged_scanned_files": 1411,
            "scope": "C6 DATA remains byte-identical. This closeout is outside DATA and separately checked by the delivery privacy audit."},
        "boundary": "No new cloud request, dispatch, upload, registration, readback, production release, gate unlock or device action during sealing.",
        "next": "Use the actual C6 predecessor under an independently approved successor; preserve the 70 complete responses and all failures. Collect only the missing fixed SELECT/list frontier."}
    matrix = copy.deepcopy(initial)
    matrix.update(overall_result="EVIDENCE_GAP", previous_matrix_sha256=plan["previous_matrix_sha256"],
                  rerun_plan_path="rerun-plan.json", rerun_plan_sha256=PLAN_HASH, evidence_hashes=hashes)
    original_commands = {item["id"]: item for item in source_matrix["commands"]}
    reused_commands = {name for item in contract["criteria"] if item["id"] in REUSED for name in item["command_ids"]}
    for definition in contract["commands"]:
        name = definition["id"]
        if name in EXITS:
            matrix["commands"].append(receipt(name, contract))
        elif name in reused_commands:
            matrix["commands"].append(copy.deepcopy(original_commands[name]))
    assert len(reused_commands) == 9 and len(matrix["commands"]) == 14
    for index, item in enumerate(matrix["criteria"]):
        if item["id"] in REUSED:
            original = next(row for row in source_matrix["criteria"] if row["id"] == item["id"])
            assert original["execution"] == "EXECUTED" and original["result"] == "PASS"
            origin = plan["reuse_origins"][item["id"]]
            matrix["criteria"][index] = {**copy.deepcopy(original), "execution": "REUSED", "reused_from_round": origin["round_id"],
                "origin_contract_sha256": origin["contract_sha256"], "origin_matrix_sha256": origin["matrix_sha256"]}
            continue
        definition = next(row for row in contract["criteria"] if row["id"] == item["id"])
        item["evidence"] = ["closeout/failure-report.json"]
        item["notes"] = "NOT_OBSERVED: after capture is incomplete; no complete assembly or dependent approval/isolation adjudication ran. Retain original failures and C4 business success."
        if item["id"] in {"P44-HISTORY", "P44-HYGIENE"}:
            item.update(result="PASS", observed=True)
            item["evidence"] += [row["path"] for row in contract["artifacts"] if row["id"] in definition["artifact_ids"]]
            item["evidence"] += ["evidence/recovery-commands-v6/" + name + ".json" for name in definition["command_ids"]]
            item["notes"] = "EXECUTED original-byte offline evaluation; closed command, result and unchanged scanned bytes verified. Not a new product operation."
        elif item["id"] == "P44-RAW-STATE":
            item["evidence"] += ["evidence/recovery-commands-v6/formal-after.json", "evidence/recovery-commands-v6/formal-after.log",
                "evidence/recovery-v6/before-result.json", "evidence/recovery-v6/negatives-result.json", "rerun-plan.json"]
    for artifact in contract["artifacts"]:
        file = b.guard(PACKAGE / artifact["path"])
        if file.is_file():
            matrix["artifacts"].append({"id": artifact["id"], "path": artifact["path"], "sha256": digest(file), "size": file.stat().st_size})
    matrix["evidence_hashes"].update({"evidence-matrix.json": INITIAL_HASH, "rerun-plan.json": PLAN_HASH})
    return contract, previous, sources, plan, report, matrix


def main():
    assert len(sys.argv) == 2 and sys.argv[1] in {"preview", "seal"}
    contract, previous, sources, plan, report, matrix = prepare()
    report_bytes = (json.dumps(report, indent=2, ensure_ascii=True) + "\n").encode()
    source_bytes = b.guard(Path(__file__)).read_bytes()
    matrix["evidence_hashes"].update({"closeout/failure-report.json": b.sha(report_bytes), "closeout/seal.py": b.sha(source_bytes)})
    assert not rules.validate_matrix(matrix, contract, CONTRACT_HASH.upper()), "FINAL_MATRIX_INVALID"
    assert not rules.validate_reuse(matrix, contract, previous, plan, reuse_sources=sources), "REUSE_INVALID"
    assert not rules.validate_planned_execution(matrix, contract, plan), "UNPLANNED_EXECUTION"
    if sys.argv[1] == "seal":
        b.write(REPORT, report_bytes)
        b.write(ARCHIVE, source_bytes)
        b.write(FINAL, matrix)
    print(json.dumps({"mode": sys.argv[1], "overall_result": matrix["overall_result"], "p44_pass": False,
        "commands": len(matrix["commands"]), "unchanged_privacy_files": 1411, "retained_complete_after": 70,
        "matrix": reference(FINAL) if FINAL.exists() else None,
        "next": "Run the unchanged stock final validator in a clean C6 verification worktree with C5 previous and C4 reuse-source."}))


if __name__ == "__main__":
    main()
