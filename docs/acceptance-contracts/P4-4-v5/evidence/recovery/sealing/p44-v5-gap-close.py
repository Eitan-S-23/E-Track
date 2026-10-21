"""Fixed C5 gap closeout; preview, prepare metadata, then seal after real privacy."""
import copy
from datetime import datetime
import importlib.util
import json
from pathlib import Path
import sys

ROOT = Path(__file__).absolute().parents[1]
spec = importlib.util.spec_from_file_location("p44_frozen_recovery", ROOT / "Tools/ota/p44-after-bundle.py")
m = importlib.util.module_from_spec(spec)
spec.loader.exec_module(m)
b, PACKAGE, DATA = m.b, m.PACKAGE, m.DATA
C = "9bfc48573a5eed190583411ac465bd847424a286"
TREE = "bd28d777ee526166d9c1050c23e487dddf8eac0a"
HASH = "AC95899A5DFDC8010DFC26FF350A2FFD94A72328412DD7A56705F72A99D83687"
INITIAL_HASH = "b24fe963392fd35c35bfaa8df73c014bdb3f5c9f6a5615897e9f076c7d6e66fa"
PLAN_HASH = "d81c8af9a8f6d10d63bb2db1fcda8c5045d640f7f91688642d28ede4e78c842c"
EXITS = {"formal-history": 0, "formal-before": 0, "formal-negatives": 0,
         "formal-after": 1, "formal-privacy": 0}
NEW_PASSES = {"P44-HISTORY", "P44-HYGIENE"}
ARCHIVE = DATA / "recovery/sealing/p44-v5-gap-close.py"
REPORT = DATA / "recovery/failure-report.json"
FINAL = PACKAGE / "final-evidence-matrix.json"


def milliseconds(record):
    return round((datetime.fromisoformat(record["ended"].replace("Z", "+00:00"))
                  - datetime.fromisoformat(record["started"].replace("Z", "+00:00"))).total_seconds() * 1000)


def receipt(name, contract, ctx):
    value = m.read(DATA / "recovery-commands" / (name + ".json"))
    assert value["label"] == name and value["closed"] is True and value["process_closed"] is True
    assert value["exitCode"] == EXITS[name] and value["signal"] is None and value["spawn_failed"] is False
    assert Path(value["cwd"]).absolute() == ROOT
    actual = " ".join(["node", m.NODE, "run", name, value["command"], *value["args"]])
    assert actual == next(item["command"] for item in contract["commands"] if item["id"] == name)
    assert value["output"]["path"] == "recovery-commands/" + name + ".log"
    ctx.read(value["output"])
    return {"id": name, "command": actual, "exit_code": value["exitCode"],
            "output_evidence": "evidence/" + value["output"]["path"]}


def context(final=False):
    assert Path.cwd().absolute() == ROOT and sys.flags.optimize == 0 and sys.dont_write_bytecode
    assert b.guard(Path(__file__)) == ROOT / ".cache/p44-v5-gap-close.py"
    assert b.git("rev-parse", "HEAD") == C and b.git("rev-parse", "HEAD^{tree}") == TREE
    assert m.sha(m.CONTRACT).upper() == HASH
    assert m.sha(PACKAGE / "evidence-matrix.json") == INITIAL_HASH
    assert m.sha(PACKAGE / "rerun-plan.json") == PLAN_HASH
    for file in (ARCHIVE, REPORT, FINAL):
        assert b.guard(file).exists() == (final and file != FINAL), "SEALING_OUTPUT_STATE"
    contract, initial, plan, previous, descriptor, ctx = m.ready()
    assert not initial["commands"] and not initial["artifacts"] and initial["overall_result"] == "NOT_RUN"
    assert all(item["result"] == "NOT_OBSERVED" for item in initial["criteria"])
    for command in contract["commands"]:
        name = command["id"]
        executed = name in EXITS and (final or name != "formal-privacy")
        assert b.guard(DATA / "recovery-commands" / (name + ".json")).exists() == executed, "NEW_RECEIPT_SET"
        if executed:
            receipt(name, contract, ctx)
    for name in ("snapshots/after.json", "manifest.json", "approvals-result.json", "states-result.json",
                 "recovery/after-result.json", "recovery/assemble-result.json", "recovery/private-verify.json"):
        assert not b.guard(DATA / name).exists(), "UNEXPECTED_DOWNSTREAM_RESULT"
    tail = b.guard(DATA / "snapshots/after-tail")
    assert not tail.exists() or not any(b.guard(file).is_file() for file in tail.rglob("*")), "UNEXPECTED_NEW_AFTER_CAPTURE"
    if not final:
        assert not b.guard(DATA / "recovery/privacy-result.json").exists()
    return contract, initial, plan, previous, descriptor, ctx


def failure_report(contract, initial, plan, descriptor, ctx):
    history = m.read(DATA / "recovery/history-result.json")
    assert history["ok"] is True and history["manifest_sha256"] == m.sha(DATA / "inputs/originals.json")
    for kind in ("before", "negatives"):
        result = m.read(DATA / "recovery" / (kind + "-result.json"))
        assert result == {"schema": "p44-after-existing-v1", "ok": True, "kind": kind, "source": descriptor[kind],
                          "source_bundle_commit": m.BUNDLE, "platform_operations": 0}
        ctx.read(descriptor[kind])
    failed = m.read(DATA / "recovery/private-verify-failure.json")
    assert set(failed) == {"ok", "started", "ended", "attempts", "error_code"}
    assert failed["ok"] is False and failed["attempts"] == 1 and failed["error_code"] == "ECONNRESET"
    assert m.sha(DATA / "recovery/private-verify-failure.json") == "7ebfa717f21722bf19fd65a5441c10ccae58f16adf3796b0221063cea147326e"
    reserve = m.read(DATA / "recovery/private-verify-reservation.json")
    assert reserve == {"method": "GET", "path": "/user/tokens/verify", "started": failed["started"], "attempts_allowed": 1}
    after = m.read(DATA / "recovery/after-reservation.json")
    assert after["product_commit"] == m.SOURCE and after["tool_commit"] == C and after["source_bundle_commit"] == m.BUNDLE
    assert (after["old_complete"], after["old_failed"], after["first_missing"]) == (31, 1, "protected-audit_logs-rows8-16")
    command = m.read(DATA / "recovery-commands/formal-after.json")
    assert m.sha(DATA / "recovery-commands/formal-after.json") == "cdfe411bbc4e33b067746a2ba1a9f494663bd80c1824080fc88fdb337f5f4e94"
    assert command["output"]["sha256"] == "85b4c969569fe2da52a3cc0590b64122897331c5196d2431484a667926adbb37"
    assert milliseconds(failed) == 4858 and milliseconds(command) == 172832
    return {
        "schema": "p44-v5-failure-closeout-v1", "task_id": "P4-4", "contract_id": contract["contract_id"],
        "round_id": initial["round_id"], "freeze_commit": C, "freeze_tree": TREE,
        "product_commit": m.SOURCE, "final_matrix_result": "EVIDENCE_GAP", "p44_pass": False,
        "stage_failure": {"command_id": "formal-after", "command_exit_code": 1, "process_closed": True,
            "phase": "private credential identity verification before new after data collection",
            "failure_owner": "environment", "error_code": "ECONNRESET", "recorded_helper_attempts": 1,
            "helper_elapsed_ms": milliseconds(failed), "command_elapsed_ms": milliseconds(command),
            "started": failed["started"], "ended": failed["ended"],
            "classification": "The private verification helper failed with ECONNRESET. Its original record does not establish whether informational/final headers or body bytes arrived; this is not evidence of a pre-response-only failure, credential denial or D1 failure.",
            "http_observation": {"status": "not recorded", "informational_headers": "not recorded",
                                 "final_headers": "not recorded", "body_bytes": "not recorded"},
            "capture_retry_policy_applied": False, "new_d1_business_reads": 0, "new_after_tail_files": 0,
            "basis_for_no_new_business_read": "Frozen Node after() awaits protectedPair() before entering the data loop; the verify failure was rethrown. No tail/after result was produced.",
            "evidence": ["evidence/recovery-commands/formal-after.json", "evidence/recovery-commands/formal-after.log",
                         "evidence/recovery/after-reservation.json", "evidence/recovery/private-verify-reservation.json",
                         "evidence/recovery/private-verify-failure.json"]},
        "retained_observations": {"c4_public_files": len(descriptor["files"]), "c4_after_complete": 31, "c4_after_failed": 1,
            "c4_after_complete_envelopes": descriptor["after_complete"], "c4_after_failed_envelope": descriptor["after_failed"][0],
            "earlier_predecessor_layers": 3, "run_a": 39313672925, "run_b": 39351100037,
            "new_staging_dispatches": 0, "successful_rehearsals_replayed": 0,
            "c4_failure_report": m.ref(DATA / "failure-report.json", PACKAGE),
            "recovery_fixture": m.ref(DATA / m.FIXTURE, PACKAGE)},
        "predecessor": {"source_bundle_commit": m.BUNDLE, "source_index_commit": m.INDEX,
            "contract_sha256": m.PARENT_HASH, "matrix_sha256": m.PARENT_MATRIX_HASH, "round_id": plan["previous_round_id"]},
        "matrix_disposition": {"reused_criteria": sorted(m.REUSED), "new_passes_after_required_privacy": ["P44-HISTORY", "P44-HYGIENE"],
            "privacy_condition": "HYGIENE is not adjudicated by this prepared report; seal requires the later real successful privacy command and exact scanned-file hashes.",
            "raw_state_result": "NOT_OBSERVED", "raw_state_observed": None,
            "reason": "Before/negatives were re-evaluated offline; the missing after tail was not collected. Assemble-complete/approvals/states did not execute. Retain C4 business success without inferring these missing results.",
            "initial_not_run_matrix": m.ref(PACKAGE / "evidence-matrix.json", PACKAGE),
            "actual_rerun_plan": m.ref(PACKAGE / "rerun-plan.json", PACKAGE)},
        "not_executed_follow_on_commands": [item["id"] for item in contract["commands"] if item["id"] in m.EXECUTED and item["id"] not in EXITS],
        "privacy_scope": "Archive this report and sealer before the single new formal-privacy call; preserve C4 privacy originals. Root separately reviews final sealing bytes and frozen sources.",
        "boundary": "No new D1 business query, staging dispatch, upload, registration, production release, gate unlock or device operation. HTTP receive-state uncertainty is preserved; no retry is authorized by this report.",
        "next": "Root may inspect already-authorized protected credential metadata and admit only the justified missing read-only recovery under the next actual plan. Do not replay C4 success or silently repeat this private verify.",
    }


def seal(contract, initial, plan, previous, descriptor, ctx, report):
    assert ARCHIVE.read_bytes() == b.guard(Path(__file__)).read_bytes(), "SEALER_SOURCE_CHANGED"
    assert m.read(REPORT) == report, "FAILURE_REPORT_CHANGED"
    privacy = m.read(DATA / "recovery/privacy-result.json")
    assert privacy["ok"] is True and privacy["lifecycle_checked"] is True and not privacy["failed_paths"]
    files = [b.guard(file) for file in DATA.rglob("*") if file.is_file()]
    hashes = {file.relative_to(PACKAGE).as_posix(): m.sha(file) for file in files}
    excluded = {"recovery-commands/formal-privacy.log", "recovery-commands/formal-privacy.json", "recovery/privacy-result.json"}
    scanned = {name.removeprefix("evidence/"): digest for name, digest in hashes.items() if name.removeprefix("evidence/") not in excluded}
    assert privacy["file_hashes"] == scanned and privacy["files_scanned"] == len(scanned), "POST_PRIVACY_BYTES_CHANGED"
    hashes["evidence-matrix.json"] = INITIAL_HASH
    hashes["rerun-plan.json"] = PLAN_HASH
    value = copy.deepcopy(initial)
    value.update(overall_result="EVIDENCE_GAP", previous_matrix_sha256=m.PARENT_MATRIX_HASH,
                 rerun_plan_path="rerun-plan.json", rerun_plan_sha256=PLAN_HASH, evidence_hashes=hashes)
    original_commands = {item["id"]: item for item in previous["commands"]}
    reused_commands = {name for item in contract["criteria"] if item["id"] in m.REUSED for name in item["command_ids"]}
    assert len(reused_commands) == 9
    for command in contract["commands"]:
        name = command["id"]
        if name in EXITS:
            value["commands"].append(receipt(name, contract, ctx))
        elif name in reused_commands:
            value["commands"].append(copy.deepcopy(original_commands[name]))
    assert len(value["commands"]) == 14
    for index, item in enumerate(value["criteria"]):
        if item["id"] in m.REUSED:
            original = next(row for row in previous["criteria"] if row["id"] == item["id"])
            assert original["execution"] == "EXECUTED" and original["result"] == "PASS"
            origin = plan["reuse_origins"][item["id"]]
            value["criteria"][index] = {**copy.deepcopy(original), "execution": "REUSED", "reused_from_round": origin["round_id"],
                "origin_contract_sha256": origin["contract_sha256"], "origin_matrix_sha256": origin["matrix_sha256"]}
            continue
        definition = next(row for row in contract["criteria"] if row["id"] == item["id"])
        item["evidence"] = ["evidence/recovery/failure-report.json"]
        item["notes"] = "NOT_OBSERVED: required after-dependent assembly/evaluation did not execute. C4 business success remains directly reused, not replayed."
        if item["id"] in NEW_PASSES:
            item.update(result="PASS", observed=True)
            item["evidence"] += [row["path"] for row in contract["artifacts"] if row["id"] in definition["artifact_ids"]]
            item["evidence"] += ["evidence/recovery-commands/" + name + ".json" for name in definition["command_ids"]]
            item["notes"] = "EXECUTED independent offline original-byte evaluation; actual closed command and result verified. No new business observation or unknown HTTP receive state is inferred."
        elif item["id"] == "P44-RAW-STATE":
            item["evidence"] += report["stage_failure"]["evidence"] + ["evidence/recovery/before-result.json",
                "evidence/recovery/negatives-result.json", "evidence/" + m.FIXTURE, "rerun-plan.json"]
            item["notes"] = "Partially attempted NOT_OBSERVED: before/negatives passed offline; formal-after exit 1 at private verify (ECONNRESET, 4858 ms helper window). HTTP receive stages were not recorded. No new D1 data or after tail exists."
    for artifact in contract["artifacts"]:
        file = b.guard(PACKAGE / artifact["path"])
        if file.is_file():
            value["artifacts"].append({"id": artifact["id"], "path": artifact["path"], "sha256": m.sha(file), "size": file.stat().st_size})
    assert not m.RULES.validate_matrix(value, contract, HASH), "FINAL_MATRIX_INVALID"
    assert not m.RULES.validate_reuse(value, contract, previous, plan), "REUSE_BINDING"
    assert not m.RULES.validate_planned_execution(value, contract, plan), "UNPLANNED_EXECUTION"
    b.write(FINAL, value)
    print(json.dumps({"overall": value["overall_result"], "matrix": m.ref(FINAL, PACKAGE), "commands": len(value["commands"]),
        "criteria": {item["id"]: {"result": item["result"], "execution": item["execution"]} for item in value["criteria"]},
        "final_validation_command": m.validation_commands()["final"], "final_validation_log": "Outside evidence DATA", "platform_operations": 0}))


def main():
    assert len(sys.argv) == 2 and sys.argv[1] in {"preview", "prepare", "seal"}
    mode = sys.argv[1]
    contract, initial, plan, previous, descriptor, ctx = context(final=mode == "seal")
    report = failure_report(contract, initial, plan, descriptor, ctx)
    if mode == "preview":
        print(json.dumps(report, indent=2))
    elif mode == "prepare":
        b.write(ARCHIVE, b.guard(Path(__file__)).read_bytes())
        b.write(REPORT, report)
        print(json.dumps({"source": m.ref(ARCHIVE, PACKAGE), "report": m.ref(REPORT, PACKAGE),
                          "next": "Execute actual formal-privacy once, then seal and stock final validation with C4 previous arguments."}))
    else:
        seal(contract, initial, plan, previous, descriptor, ctx, report)


if __name__ == "__main__":
    main()
