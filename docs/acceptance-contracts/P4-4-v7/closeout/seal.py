"""Seal the actual C7 pre-request failure without altering closed evidence."""
import copy
import importlib.util
import json
from pathlib import Path
import sys

ROOT = Path(__file__).absolute().parents[1]
spec = importlib.util.spec_from_file_location("p44_c7_closeout", ROOT / "Tools/ota/p44-after-bundle.py")
m = importlib.util.module_from_spec(spec)
spec.loader.exec_module(m)
m.configure_package("docs/acceptance-contracts/P4-4-v7.package.json")
b, DATA, PACKAGE = m.b, m.DATA, m.PACKAGE
C7 = "371baeeb8519a0340a79c96b6a7cd6406b2e0346"
CONTRACT_HASH = "587258cde323692569733470045a2e174ec1bef32c67088ba0cc3e76e1223314"
NODE_HASH = "037c66a8388156382847702e72c21c1d3b01f96f5ca4976579a772c43bb3c8d2"
EXITS = {"formal-history": 0, "formal-before": 0, "formal-negatives": 0,
         "formal-after": 1, "formal-privacy": 0}


def receipt(name, contract, ctx):
    stem = m.COMMANDS + "/" + ("formal-after-invocation-1" if name == "formal-after" else name)
    row = m.read(DATA / (stem + ".json"))
    assert row["label"] == name and row["exitCode"] == EXITS[name]
    assert row["closed"] is True and row["process_closed"] is True
    assert row["signal"] is None and row["spawn_failed"] is False and Path(row["cwd"]).absolute() == ROOT
    reserve = m.read(DATA / (stem + "-reservation.json"))
    assert reserve == {key: row[key] for key in ("label", "command", "args", "cwd", "started")}
    actual = " ".join(["node", m.NODE, *m.package_args(), "run", name, row["command"], *row["args"]])
    assert actual == next(item["command"] for item in contract["commands"] if item["id"] == name)
    assert row["output"]["path"] == stem + ".log"
    ctx.read(row["output"])
    return {"id": name, "command": actual, "exit_code": row["exitCode"],
            "output_evidence": "evidence/" + row["output"]["path"]}


def main():
    assert Path.cwd().absolute() == ROOT and sys.dont_write_bytecode and sys.flags.optimize == 0
    assert b.git("rev-parse", "HEAD") == C7 and m.sha(m.CONTRACT) == CONTRACT_HASH
    assert m.sha(ROOT / m.NODE) == NODE_HASH
    contract, initial, plan, previous, descriptor, ctx = m.ready()
    for name in ("snapshots/after.json", "manifest.json", "approvals-result.json", "states-result.json",
                 "recovery-v7/after-result.json", "recovery-v7/assemble-result.json",
                 "recovery-v7/continuation-2.json", "snapshots/after-tail-v6/attempt-2"):
        assert not b.guard(DATA / name).exists(), "UNEXPECTED_AFTER_OUTPUT"
    expected_names = set(EXITS) | {"formal-precheck", "formal-rerun-plan"}
    stems = {"formal-after-invocation-1" if name == "formal-after" else name for name in expected_names}
    expected_files = {stem + suffix for stem in stems for suffix in (".json", ".log", "-reservation.json")}
    assert {file.name for file in (DATA / m.COMMANDS).iterdir()} == expected_files, "UNEXPECTED_COMMAND_SET"
    for name in EXITS:
        receipt(name, contract, ctx)
    for kind in ("before", "negatives"):
        assert m.read(DATA / m.RECOVERY / (kind + "-result.json")) == m.verify_existing_bytes(kind, descriptor, ctx)
    history = m.read(DATA / m.RECOVERY / "history-result.json")
    assert history["ok"] is True and history["manifest_sha256"] == m.sha(DATA / "inputs/originals.json")
    tail = [m.read(file) for file in (DATA / m.TAIL).glob("*.http.json")]
    assert len(tail) == 40 and sum(row.get("completed") is True for row in tail) == 39
    assert len(descriptor["after_complete"]) == 31
    privacy = m.read(DATA / m.RECOVERY / "privacy-result.json")
    assert privacy["ok"] is True and privacy["lifecycle_checked"] is True and not privacy["failed_paths"]
    hashes = {file.relative_to(PACKAGE).as_posix(): m.sha(file) for file in DATA.rglob("*") if file.is_file()}
    excluded = {m.COMMANDS + "/formal-privacy.log", m.COMMANDS + "/formal-privacy.json", m.RECOVERY + "/privacy-result.json"}
    scanned = {name.removeprefix("evidence/"): value for name, value in hashes.items() if name.removeprefix("evidence/") not in excluded}
    assert privacy["file_hashes"] == scanned and privacy["files_scanned"] == len(scanned), "POST_PRIVACY_DRIFT"
    probe_path = ROOT / ".cache/p44/logs/p44-successor05-root-repro01.log"
    probe_bytes = b.guard(probe_path).read_bytes()
    probe = json.loads(probe_bytes)
    assert probe["reproduced"] is True and probe["failure"]["message"] == "RECOVERY_PATH"
    assert probe["write_attempts"] == probe["network_attempts"] == 0 and probe["source_sha256"] == NODE_HASH
    failed = m.read(DATA / m.COMMANDS / "formal-after-invocation-1.json")
    report = {"schema": "p44-c7-gap-closeout-v1", "finding": "P44-SUCCESSOR-05", "task_id": "P4-4",
        "contract_sha256": CONTRACT_HASH, "freeze_commit": C7, "product_commit": m.SOURCE_COMMIT,
        "overall_result": "EVIDENCE_GAP", "p44_pass": False, "failure_owner": "harness",
        "failure": {"command_id": "formal-after", "slot": 1, "exit_code": 1,
            "started": failed["started"], "ended": failed["ended"], "process_closed": True,
            "cause": "startAttempt passes a trailing-slash directory to production makeIO.exists; relative() rejects it with RECOVERY_PATH before attempt reservation or HTTP.",
            "source_path": m.NODE, "source_sha256": NODE_HASH,
            "receipt": m.ref(DATA / m.COMMANDS / "formal-after-invocation-1.json", PACKAGE)},
        "retained_complete_after": 70, "new_cloud_requests": 0, "new_complete_after": 0,
        "after_slots_used": 1, "second_slot_used": False, "continuation_admitted": False,
        "reason_for_no_continuation": "No failed attempt-result exists and the unchanged path assertion must be repaired; do not blindly retry or alter the frozen tool.",
        "not_observed": ["P44-RAW-STATE", "P44-APPROVALS", "P44-ISOLATION"],
        "executed_pass": ["P44-HISTORY", "P44-HYGIENE"], "reused_pass": sorted(m.REUSED),
        "independent_probe": {"path": "closeout/independent-probe.log", "size_bytes": len(probe_bytes), "sha256": b.sha(probe_bytes)},
        "privacy_files_unchanged": len(scanned),
        "privacy_scope": "Closed DATA scan unchanged; closeout metadata is separately checked by the staged delivery audit.",
        "boundary": "No product change, new cloud request, business replay, production release, gate unlock, device action or automatic continuation.",
        "next_owner": "External implementation agent selected by user; root independently reviews the repair and successor admission."}
    outputs = {"closeout/failure-report.json": (json.dumps(report, indent=2) + "\n").encode(),
               "closeout/independent-probe.log": probe_bytes,
               "closeout/independent-probe-receipt.json": b.guard(ROOT / ".cache/p44/logs/p44-successor05-root-repro01.json").read_bytes(),
               "closeout/seal.py": b.guard(Path(__file__)).read_bytes()}
    final = PACKAGE / "final-evidence-matrix.json"
    m.outputs_absent([PACKAGE / name for name in outputs] + [final])
    hashes.update({name: b.sha(raw) for name, raw in outputs.items()})
    for name in ("evidence-matrix.json", "rerun-plan.json"):
        hashes[name] = m.sha(PACKAGE / name)
    matrix = copy.deepcopy(initial)
    matrix.update(overall_result="EVIDENCE_GAP", previous_matrix_sha256=m.PARENT_MATRIX_HASH,
                  rerun_plan_path="rerun-plan.json", rerun_plan_sha256=hashes["rerun-plan.json"], evidence_hashes=hashes)
    sources = m.reuse_sources()
    original = sources[m.SOURCE_MATRIX_HASH]["matrix"]
    old_commands = {row["id"]: row for row in original["commands"]}
    reused_commands = {name for item in contract["criteria"] if item["id"] in m.REUSED for name in item["command_ids"]}
    for item in contract["commands"]:
        name = item["id"]
        if name in EXITS:
            matrix["commands"].append(receipt(name, contract, ctx))
        elif name in reused_commands:
            matrix["commands"].append(copy.deepcopy(old_commands[name]))
    assert len(matrix["commands"]) == 14 and len(reused_commands) == 9
    for index, item in enumerate(matrix["criteria"]):
        if item["id"] in m.REUSED:
            old = next(row for row in original["criteria"] if row["id"] == item["id"])
            assert old["execution"] == "EXECUTED" and old["result"] == "PASS"
            origin = plan["reuse_origins"][item["id"]]
            matrix["criteria"][index] = {**copy.deepcopy(old), "execution": "REUSED", "reused_from_round": origin["round_id"],
                "origin_contract_sha256": origin["contract_sha256"], "origin_matrix_sha256": origin["matrix_sha256"]}
            continue
        definition = next(row for row in contract["criteria"] if row["id"] == item["id"])
        item["evidence"] = ["closeout/failure-report.json", "closeout/independent-probe.log"]
        item["notes"] = "NOT_OBSERVED: a local pre-request path assertion prevented new capture; no complete after/manifest or dependent adjudication was produced. The cause is a harness defect, not an observed product failure."
        if item["id"] in {"P44-HISTORY", "P44-HYGIENE"}:
            item.update(result="PASS", observed=True)
            item["evidence"] += [row["path"] for row in contract["artifacts"] if row["id"] in definition["artifact_ids"]]
            item["evidence"] += ["evidence/" + m.COMMANDS + "/" + name + ".json" for name in definition["command_ids"]]
            item["notes"] = "Actual closed independent offline evaluation; no new product observation."
    for item in contract["artifacts"]:
        file = b.guard(PACKAGE / item["path"])
        if file.is_file():
            matrix["artifacts"].append({"id": item["id"], "path": item["path"], "sha256": m.sha(file), "size": file.stat().st_size})
    assert not m.RULES.validate_matrix(matrix, contract, CONTRACT_HASH.upper()), "FINAL_MATRIX_INVALID"
    assert not m.RULES.validate_reuse(matrix, contract, previous, plan, sources), "REUSE_INVALID"
    assert not m.RULES.validate_planned_execution(matrix, contract, plan), "UNPLANNED_EXECUTION"
    for name, raw in outputs.items():
        b.write(PACKAGE / name, raw)
    b.write(final, matrix)
    print(json.dumps({"overall_result": "EVIDENCE_GAP", "cause": "P44-SUCCESSOR-05", "commands": 14,
        "retained_complete_after": 70, "new_cloud_requests": 0, "privacy_files_unchanged": len(scanned),
        "matrix": m.ref(final, PACKAGE), "final_validation_command": m.validation_commands()["final"]}))


if __name__ == "__main__":
    main()
