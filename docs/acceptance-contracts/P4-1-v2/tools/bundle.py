"""Prepare and seal P4-1 evidence using the existing v3 contract and validator."""
import argparse
import copy
import hashlib
import importlib.util
import json
import subprocess
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[4]
WORK = ROOT / ".cache/p41-acceptance-20261017"
TOOLS = "docs/acceptance-contracts/P4-1-v2/tools/"
CONTRACT = ROOT / "docs/acceptance-contracts/P4-1-v2.contract.json"
MATRIX = WORK / "evidence-matrix.json"
PREVIOUS_CONTRACT = ROOT / "docs/acceptance-contracts/P4-1-v1.contract.json"
PREVIOUS_MATRIX = ROOT / "docs/acceptance-contracts/P4-1-v1/evidence/evidence-matrix.json"
REPAIR_COMMIT = "5d4d07571451905ac156a1a721fa8b8ce764ed7c"
assert Path.cwd().resolve() == ROOT


def sha(data):
    return hashlib.sha256(data).hexdigest()


def read(file):
    return json.loads(Path(file).read_bytes())


def guard(file):
    file = Path(file).absolute()
    file.resolve().relative_to(ROOT)
    for parent in [file, *file.parents]:
        if parent.exists():
            assert not parent.is_symlink() and not getattr(parent.stat(), "st_file_attributes", 0) & 0x400
    return file


def write(file, value):
    file = guard(file)
    assert not file.exists(), "Preserve previous evidence: " + str(file)
    file.parent.mkdir(parents=True, exist_ok=True)
    data = (json.dumps(value, indent=2, ensure_ascii=True) + "\n").encode()
    with guard(file).open("xb") as output:
        output.write(data)
    return data


def git(*args):
    return subprocess.check_output(["git", "--no-optional-locks", "-c", "core.fsmonitor=false", *args], cwd=ROOT).decode().strip()


def definitions():
    commands = []
    artifacts = []
    criteria = []

    def command(name, executable, args, groups, runners, description):
        invocation = ["node", TOOLS + "session.cjs", "run", name, ".", executable, *args]
        record = {"id": name, "description": description, "command": " ".join(invocation),
                  "input_groups": sorted(set(groups + ["execution"])),
                  "runner_paths": sorted(set(runners + [TOOLS + "session.cjs"])),
                  "expected_exit_codes": [0, 1, 2], "success_exit_code": 0, "output_required": True}
        commands.append(record)
        return name

    def inspect(name, mode, extra=(), groups=None):
        return command(name, "python", ["-X", "utf8", "-B", TOOLS + "inspect.py", mode,
                       "--output", str(WORK.relative_to(ROOT)).replace("\\", "/") + "/review/" + mode + "-formal.json", *extra],
                       groups or ["firmware", "release", "cloudflare", "evaluation"],
                       [TOOLS + "inspect.py", "Tools/jlink/prepare-bootstrap-app.py", "Libraries/OTA/ota_layout.h"],
                       "evidence: independently evaluate retained originals, no rebuild/device action; timeout 15 minutes.")

    def campaign(name, mode, label=None, groups=None):
        return command(name, "node", [TOOLS + "campaign.cjs", mode, *([label] if label else [])],
                       groups or ["firmware", "release", "cloudflare"], [TOOLS + "campaign.cjs"],
                       "preflight/control: exact approved source and test environment only; each HTTP request <=60 seconds. "
                       "Dispatch/approval reserve once before POST; uncertain responses require reconciliation, never blind retry.")

    def cloud(name, mode, label, extra=()):
        return command(name, "node", [TOOLS + "cloud-read.cjs", mode, label, *extra],
                       ["cloudflare"], [TOOLS + "cloud-read.cjs"],
                       "preflight/evidence: read-only existing protected/test D1, R2 and Worker bindings; "
                       "<=120 requests, <=60 seconds each, bounded pagination; no deployment, upload or SQL mutation.")

    def criterion(name, ids, files, description):
        groups = sorted({group for cmd in commands if cmd["id"] in ids for group in cmd["input_groups"]})
        aid = []
        for index, file in enumerate(files):
            key = name + "-" + str(index + 1)
            artifacts.append({"id": key, "description": description, "path": file})
            aid.append(key)
        criteria.append({"id": name, "description": description, "required": True, "kind": "functional",
                         "evidence_types": ["raw_log"], "input_groups": groups,
                         "dependency_rationale": "Firmware supplies layout/build inputs; release supplies actual GCC and byte tools; "
                         "cloudflare supplies schema, runtime/uploader/register consumers where listed. Execution owns API/process capture; "
                         "evaluation owns offline interpretation. Only groups consumed by the listed commands are included.",
                         "external_inputs": ["target", "history"], "command_ids": ids, "artifact_ids": aid,
                         "gate": {"type": "boolean", "basis": "frozen_requirement", "expected": True}})

    origins = inspect("formal-origins", "origins", groups=["firmware", "release", "cloudflare", "evaluation", "validation"])
    criterion("P41-ORIGINS", [origins], ["review/origins-formal.json"],
              "Independently evaluate original CI/raw bootstrap/synthetic negatives; not a new native or device campaign.")
    oracle = inspect("formal-oracle", "selftest")
    controller = campaign("formal-controller", "selftest")
    ci = campaign("formal-ci", "ci", groups=["firmware", "release", "cloudflare", "validation", "governance"])
    criterion("P41-ADMISSION", [oracle, controller, ci], ["review/selftest-formal.json", "formal/ci.json"],
              "Discriminating acceptance oracle and actual source-bound PR CI pass; APK/EXE skipped jobs are not new builds.")
    gb = campaign("formal-github-before", "github-snapshot", "github-before")
    cb = cloud("formal-cloud-before", "snapshot", "before")
    ds = campaign("formal-dispatch", "dispatch")
    discover = campaign("formal-discover", "discover", "dispatch-discovery")
    approve = campaign("formal-approve", "approve", "approval-check")
    collect = campaign("formal-collect", "collect")
    criterion("P41-REHEARSAL", [ds, discover, approve, collect], ["formal/collected.json", "formal/approval-reservation.json",
              "formal/completed/rehearsal.zip"], "One repair-bound successor staging workflow after P41-NATIVE-01, same shared implementation, real protected GCC key; "
              "required reviewer preserved and explicit delegated approval, no production job or release. Workflow finite job limits apply; "
              "root observes at <=1-minute intervals and stops at terminal state. The actual v1 run 38897470681 remains PRODUCT_FAIL; "
              "one prior staging execution and one new v2 dispatch are counted. Lost responses are reconciled, not redispatched; "
              "any further execution needs changed evidence, reviewed scope and a new minimum-rerun decision.")
    byte = inspect("formal-bytes", "rehearsal", ["--artifact", ".cache/p41-acceptance-20261017/formal/completed/rehearsal.zip",
                   "--target", ".cache/p41-acceptance-20261017/formal/target.json"])
    criterion("P41-BYTES", [byte], ["review/rehearsal-formal.json"],
              "Exact approved key/source, eight GCC artifacts, actual full/patch candidate bytes, recovery trailer and metadata agree.")
    rb = cloud("formal-r2", "assets", "assets", [".cache/p41-acceptance-20261017/review/rehearsal-formal.json"])
    criterion("P41-R2", [rb], ["cloud/assets/receipt.json"], "Independent S3 GET retains all three exact R2 object bodies and checks full SHA/length.")
    ca = cloud("formal-cloud-after", "snapshot", "after")
    ga = campaign("formal-github-after", "github-snapshot", "github-after")
    state = inspect("formal-state", "states")
    criterion("P41-STATE", [gb, cb, ca, ga, state], ["review/states-formal.json", "cloud/before/receipt.json", "cloud/after/receipt.json",
              "formal/github-before/snapshot.json", "formal/github-after/snapshot.json"],
              "Protected D1/R2/channel/GitHub Release snapshots unchanged; only one new test ready release, three assets and one audit row; "
              "idempotent replay and unchanged pre-existing test data. Wrangler temporary preview state is not claimed globally absent.")
    return commands, artifacts, criteria


def groups():
    return [{"id": name, "profile": profile, "category": category} for name, profile, category in [
        ("firmware", "Firmware", "production_source"), ("cloudflare", "Cloudflare", "production_source"),
        ("release", "P41Release", "production_source"), ("execution", "P41Execution", "validation_inputs"),
        ("evaluation", "P41Evaluation", "validation_inputs")]]


def validator():
    spec = importlib.util.spec_from_file_location("p41_bundle_validator", ROOT / "Tools/acceptance/validate_bundle.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def selftest():
    contract = read(ROOT / "docs/acceptance-contracts/template.contract.json")
    commands, artifacts, criteria = definitions()
    contract.update(contract_id="P4-1-v2", version=2, parent_contract_sha256=sha(PREVIOUS_CONTRACT.read_bytes()),
                    task_id="P4-1", commands=commands, artifacts=artifacts, criteria=criteria)
    contract["input_groups"] += groups()
    contract["external_inputs"] = [{"id": name, "category": "fixture", "description": "schema fixture",
                                   "fingerprint": "fixture", "evidence_path": name + ".json", "evidence_sha256": "0" * 64}
                                  for name in ["target", "history"]]
    module = validator()
    errors = module.validate_contract(contract, allow_draft=True)
    assert not errors, errors
    broken = copy.deepcopy(contract)
    broken["criteria"][0]["input_groups"].remove("evaluation")
    assert module.validate_contract(broken, allow_draft=True), "Omitted evaluator dependency must fail"
    print(json.dumps({"ok": True, "positive_contract": 1, "missing_dependency_rejected": 1,
                      "commands": len(commands), "criteria": len(criteria)}))


def freeze():
    commit = git("rev-parse", "HEAD")
    target = read(WORK / "formal/target.json")
    assert target["commitSha"] == commit
    previous_hash = sha(PREVIOUS_CONTRACT.read_bytes())
    assert previous_hash == "8ab64574cc062a6fd58c7a25e024d6b2d2cd085caa81b8446d60c6701807597d"
    assert sha(PREVIOUS_MATRIX.read_bytes()) == "aa980b1b64777f9ccf8ec46c0e34945e3c59fee5dcc638ef92c0cc19d3a54da0"
    assert read(PREVIOUS_MATRIX)["overall_result"] == "PRODUCT_FAIL"
    inputs = {"original_operator": "Separate implementation owner plus original independent acceptance reviewer",
              "source_commit": REPAIR_COMMIT, "original_date": "2026-10-16/17",
              "previous_contract_sha256": previous_hash, "previous_matrix_sha256": sha(PREVIOUS_MATRIX.read_bytes()),
              "previous_bundle_commit": "7f014a8887dc79646ff392ee8cfa6a1ce2c9cf67",
              "previous_staging_run": 38897470681, "previous_staging_attempt": 1, "previous_result": "PRODUCT_FAIL",
              "prior_staging_executions": 1, "planned_new_dispatches": 1,
              "bootstrap_archive_commit": "c860b3be7a0b1a3ca1b3a53cf79cc9ef21cc9124",
              "original_evaluation_sha256": sha((WORK / "review/origins-preparation.json").read_bytes()),
              "repair_review_sha256": sha((WORK / "review/remediation-preparation.json").read_bytes()),
              "applicability": "P41-NATIVE-01 changes only the shared R2 metadata representation plus regression tests. "
              "The original failed round and partial key/byte observations are preserved, not relabeled. "
              "One successor canonical workflow supplies the missing real upload/readback/ready and new before/after state evidence. "
              "Its unchanged workflow requires source-bound same-run GCC/pack outputs; no separate qualification or build campaign is added."}
    write(WORK / "inputs/history.json", inputs)
    commands, artifacts, criteria = definitions()
    base = read(ROOT / "docs/acceptance-contracts/template.contract.json")
    base.update(contract_id="P4-1-v2", version=2, parent_contract_sha256=previous_hash, task_id="P4-1", status="FROZEN", approved_by="Codex independent acceptance root, user-delegated P41-STAGING-DELEGATION-20261016",
                approved_at=datetime.now(timezone.utc).isoformat(), implementation_ref=commit, freeze_commit=commit,
                freeze_tree=git("rev-parse", "HEAD^{tree}"), profile_config_blob=git("rev-parse", "HEAD:Tools/provenance/manifest_profiles.json"),
                commands=commands, artifacts=artifacts, criteria=criteria)
    base["input_groups"] += groups()
    for name, file in [("target", "formal/target.json"), ("history", "inputs/history.json")]:
        digest = sha((WORK / file).read_bytes())
        base["external_inputs"].append({"id": name, "category": "fixture", "description": "P4-1 " + name + " exact approved input identity",
                                       "fingerprint": "sha256:" + digest, "evidence_path": file, "evidence_sha256": digest})
    errors = validator().validate_contract(base)
    assert not errors, errors
    raw = write(CONTRACT, base)
    matrix = read(ROOT / "docs/acceptance-contracts/template.evidence-matrix.json")
    template = matrix["criteria"][0]
    matrix.update(contract_id=base["contract_id"], contract_sha256=sha(raw).upper(), round_id="P41-20261017-02",
                  criteria=[{**template, "id": item["id"], "notes": "Not yet observed under this frozen contract"} for item in criteria])
    write(MATRIX, matrix)
    print(json.dumps({"contract_sha256": sha(raw), "freeze_commit": commit, "commands": len(commands), "criteria": len(criteria)}))


def assess():
    contract, matrix = read(CONTRACT), read(MATRIX)
    assert matrix["overall_result"] == "NOT_RUN", "Use a new versioned result instead of overwriting a final matrix"
    results = {
        "P41-ORIGINS": read(WORK / "review/origins-formal.json")["ok"],
        "P41-ADMISSION": read(WORK / "review/selftest-formal.json")["ok"] and read(WORK / "formal/ci.json")["ok"],
        "P41-REHEARSAL": read(WORK / "formal/collected.json")["ok"],
        "P41-BYTES": read(WORK / "review/rehearsal-formal.json")["ok"],
        "P41-R2": read(WORK / "cloud/assets/receipt.json")["ok"],
        "P41-STATE": read(WORK / "review/states-formal.json")["ok"],
    }
    evidence = {}
    for folder in ["commands", "formal", "cloud", "review", "inputs", "github"]:
        for file in (WORK / folder).rglob("*"):
            if file.is_file():
                evidence[file.relative_to(WORK).as_posix()] = sha(file.read_bytes())
    matrix["evidence_hashes"] = evidence
    for command in contract["commands"]:
        receipt = read(WORK / "commands" / (command["id"] + ".json"))
        assert receipt["closed"] is True
        actual = " ".join(["node", TOOLS + "session.cjs", "run", command["id"], ".", receipt["executable"], *receipt["args"]])
        assert actual == command["command"], "Actual command differs from frozen invocation"
        assert Path(receipt["cwd"]).resolve() == ROOT
        if receipt["exitCode"] != 0:
            for criterion in contract["criteria"]:
                if command["id"] in criterion["command_ids"]:
                    results[criterion["id"]] = False
        matrix["commands"].append({"id": command["id"], "command": command["command"],
                                   "exit_code": receipt["exitCode"], "output_evidence": "commands/" + command["id"] + ".stdout.txt"})
    for artifact in contract["artifacts"]:
        raw = (WORK / artifact["path"]).read_bytes()
        matrix["artifacts"].append({"id": artifact["id"], "path": artifact["path"], "size": len(raw), "sha256": sha(raw)})
    assert all(results.values()), "Failed observations require explicit product/harness/environment classification before closing"
    for item in matrix["criteria"]:
        item.update(result="PASS", observed=bool(results[item["id"]]), failure_owner=None,
                    evidence=[artifact["path"] for artifact in contract["artifacts"] if artifact["id"].startswith(item["id"] + "-")],
                    notes="Derived from retained original command results and artifacts; see the independent review report.")
    matrix["overall_result"] = "PASS"
    write(WORK / "final-evidence-matrix.json", matrix)
    print(json.dumps({"overall_result": matrix["overall_result"], "criteria": results, "evidence_files": len(evidence)}))


def archive():
    final = read(WORK / "final-evidence-matrix.json")
    destination = guard(ROOT / "docs/acceptance-contracts/P4-1-v2/evidence")
    assert not destination.exists()
    sources = [(WORK / file, destination / file) for file in final["evidence_hashes"]]
    sources += [(CONTRACT, destination / "contract.json"), (WORK / "final-evidence-matrix.json", destination / "evidence-matrix.json")]
    for source, output in sources:
        guard(output)
        assert source.is_file()
    for source, output in sources:
        output.parent.mkdir(parents=True, exist_ok=True)
        with guard(output).open("xb") as stream:
            stream.write(source.read_bytes())
        assert sha(source.read_bytes()) == sha(output.read_bytes())
    print(json.dumps({"archived_files": len(sources), "directory": destination.relative_to(ROOT).as_posix()}))


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("mode", choices=["freeze", "assess", "archive", "commands", "selftest"])
    args = parser.parse_args()
    if args.mode == "selftest":
        selftest()
    elif args.mode == "freeze":
        freeze()
    elif args.mode == "assess":
        assess()
    elif args.mode == "archive":
        archive()
    else:
        print("\n".join(command["command"] for command in definitions()[0]))


if __name__ == "__main__":
    main()
