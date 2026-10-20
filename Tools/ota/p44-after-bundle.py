"""Fixed C5-to-C6 after-evidence adapter; C4 observations remain the reuse origin."""
import argparse
import base64
import copy
from contextlib import contextmanager
from datetime import datetime, timezone
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import re
import subprocess
import sys
import zipfile

ROOT = Path(__file__).absolute().parents[2]
spec = importlib.util.spec_from_file_location("p44_c4_bundle", ROOT / "Tools/acceptance/p44/bundle.py")
b = importlib.util.module_from_spec(spec)
spec.loader.exec_module(b)
RULES, INSPECT = b.validator(), b.inspector()
SOURCE_COMMIT = "2756ca95e26ec636216313271708b3304d61a5cc"
SOURCE_BUNDLE = "da37711799a21c4eb2c5d082dab1a7b81d028511"
SOURCE_INDEX = "7168568489ab0eb67a9e7a05106f245e7243421e"
SOURCE_HASH = "86764FA47B8C52D748BF93B83C5735352CEAB69519D8FFCC4C6BFC706F8939B5"
SOURCE_MATRIX_HASH = "25D71CCB7707C83A62ACE11E6662B2BDEAB5E85DF45FAA557326010219F038D7"
SOURCE_PACKAGE = ROOT / "docs/acceptance-contracts/P4-4-v4"
SOURCE_CONTRACT = SOURCE_PACKAGE.with_suffix(".contract.json")
SOURCE_MATRIX = SOURCE_PACKAGE / "final-evidence-matrix.json"
PREDECESSOR_COMMIT = "9bfc48573a5eed190583411ac465bd847424a286"
PREDECESSOR_BUNDLE = "21fa17f7da91a0d336ae1f1a7f1a93910beb2ab7"
PREDECESSOR_INDEX = "7ae9112dcb8a910a541005df3421ed75fe8be3cb"
PARENT_HASH = "AC95899A5DFDC8010DFC26FF350A2FFD94A72328412DD7A56705F72A99D83687"
PARENT_MATRIX_HASH = "0C79B01BBB97D276AA2FCE322C0AB7F4AA5BE65BC183A1457C75CA69F4C1F5DC"
PARENT = ROOT / "docs/acceptance-contracts/P4-4-v5"
PARENT_CONTRACT = PARENT.with_suffix(".contract.json")
PARENT_MATRIX = PARENT / "final-evidence-matrix.json"
PACKAGE = ROOT / "docs/acceptance-contracts/P4-4-v6"
DATA = PACKAGE / "evidence"
CONTRACT = PACKAGE.with_suffix(".contract.json")
FIXTURE = "inputs/after-recovery-v6.json"
FIXTURE_ID = "after-recovery-v6"
RECOVERY = "recovery-v6"
COMMANDS = "recovery-commands-v6"
OFFLINE_IDENTITY = {
    "source_path": ".cache/p41-dev-20261015/.cache/cf-readonly-20261015-r1/token-status.json",
    "size_bytes": 483, "sha256": "693ac971c7473e03f2fe526d117efe8b295cd403d24f8f66961ecb31ca563afa",
    "id_pointer": "/body/result/id", "id_sha256": "0c22488a9bee1355603d8d61faca06fcacbdafccfed8a4ba7dc490af7cacdedc",
    "mode": "offline-no-fallback",
}
NODE = "Tools/ota/p44-after-recovery.cjs"
PYTHON = "Tools/ota/p44-after-bundle.py"
REUSED = {"P44-CONFIGURATION", "P44-RAW-RUNS", "P44-REHEARSAL", "P44-RAW-READBACK"}
EXECUTED = {"formal-history", "formal-before", "formal-negatives", "formal-after",
            "formal-assemble-complete", "formal-approvals", "formal-states", "formal-privacy"}
FAILED = "snapshots/after/protected-audit_logs-rows8-16.http.json"
DESCRIPTOR_KEYS = {"schema", "source_commit", "source_bundle_commit", "source_index_commit",
                   "source_contract", "source_matrix", "target", "before", "negatives", "run_a", "run_b",
                   "reviewer_attestation", "after_complete", "after_failed", "files", "predecessor_commit",
                   "predecessor_bundle_commit", "predecessor_index_commit", "predecessor_contract",
                   "predecessor_matrix", "private_verify_failure", "offline_identity"}


def read(file):
    return INSPECT.json_bytes(b.guard(file).read_bytes())


def sha(file):
    return b.sha(b.guard(file).read_bytes())


def ref(file, base=None):
    return b.ref(b.guard(file), DATA if base is None else base)


def outputs_absent(files):
    guarded = [b.guard(file) for file in files]
    assert len(guarded) == len(set(guarded)), "DUPLICATE_OUTPUT_TARGET"
    for file in guarded:
        assert not file.exists(), "OUTPUT_ALREADY_EXISTS"


def lineage_fields():
    return {"source_commit": SOURCE_COMMIT, "source_bundle_commit": SOURCE_BUNDLE,
            "predecessor_commit": PREDECESSOR_COMMIT, "predecessor_bundle_commit": PREDECESSOR_BUNDLE,
            "predecessor_index_commit": PREDECESSOR_INDEX}


def reuse_sources():
    contract, matrix, contract_hash, matrix_hash = RULES._load_bundle(b.guard(SOURCE_CONTRACT), b.guard(SOURCE_MATRIX))
    assert contract_hash == SOURCE_HASH and matrix_hash == SOURCE_MATRIX_HASH, "ORIGIN_HASH"
    assert contract["freeze_commit"] == SOURCE_COMMIT and matrix["overall_result"] == "EVIDENCE_GAP"
    assert not RULES.validate_contract(contract) and not RULES.validate_matrix(matrix, contract, contract_hash)
    for file in (SOURCE_CONTRACT, SOURCE_MATRIX):
        assert b.git_bytes("show", SOURCE_BUNDLE + ":" + file.relative_to(ROOT).as_posix()) == file.read_bytes(), "ORIGIN_GIT_BYTES"
    return {matrix_hash: {"contract": contract, "matrix": matrix, "contract_sha256": contract_hash,
                         "matrix_sha256": matrix_hash, "bundle_directory": SOURCE_PACKAGE}}


def source_identity():
    for left, right in ((SOURCE_COMMIT, SOURCE_BUNDLE), (SOURCE_BUNDLE, SOURCE_INDEX),
                        (SOURCE_INDEX, PREDECESSOR_COMMIT), (PREDECESSOR_COMMIT, PREDECESSOR_BUNDLE),
                        (PREDECESSOR_BUNDLE, PREDECESSOR_INDEX), (PREDECESSOR_INDEX, "HEAD")):
        b.git("merge-base", "--is-ancestor", left, right)
    contract, matrix = read(PARENT_CONTRACT), read(PARENT_MATRIX)
    assert sha(PARENT_CONTRACT).upper() == PARENT_HASH and sha(PARENT_MATRIX).upper() == PARENT_MATRIX_HASH
    for file in (PARENT_CONTRACT, PARENT_MATRIX):
        assert b.git_bytes("show", PREDECESSOR_BUNDLE + ":" + file.relative_to(ROOT).as_posix()) == file.read_bytes(), "PARENT_GIT_BYTES"
    assert contract["freeze_commit"] == PREDECESSOR_COMMIT and matrix["overall_result"] == "EVIDENCE_GAP"
    assert not RULES.validate_contract(contract) and not RULES.validate_matrix(matrix, contract, PARENT_HASH)
    sources = reuse_sources()
    previous = {"contract": contract, "matrix": matrix, "contract_sha256": PARENT_HASH,
                "matrix_sha256": PARENT_MATRIX_HASH, "bundle_directory": PARENT}
    assert not RULES._validate_reuse_history(previous, sources, ROOT, set(), set()), "PREDECESSOR_REUSE_HISTORY"
    return contract, matrix


def source_plan():
    contract, matrix = source_identity()
    base = PARENT / "evidence"
    hashes = {name.removeprefix("evidence/"): value for name, value in matrix["evidence_hashes"].items()
              if name.startswith("evidence/")}
    files = sorted(b.guard(file) for file in base.rglob("*") if file.is_file())
    assert {file.relative_to(base).as_posix() for file in files} == set(hashes), "PARENT_FILE_SET"
    git_files = {}
    for line in b.git_bytes("ls-tree", "-r", "-z", PREDECESSOR_BUNDLE, "--", base.relative_to(ROOT).as_posix()).split(b"\0"):
        if line:
            header, name = line.split(b"\t")
            mode, kind, oid = header.decode().split()
            assert mode in {"100644", "100755"} and kind == "blob", "PARENT_FILE_MODE"
            git_files[name.decode()] = oid
    assert set(git_files) == {file.relative_to(ROOT).as_posix() for file in files}, "PARENT_GIT_FILE_SET"
    references = []
    for file in files:
        raw = file.read_bytes()
        name = file.relative_to(base).as_posix()
        assert b.sha(raw).upper() == hashes[name].upper(), "PARENT_FILE_HASH"
        assert hashlib.sha1(b"blob " + str(len(raw)).encode() + b"\0" + raw).hexdigest() == git_files[file.relative_to(ROOT).as_posix()], "PARENT_GIT_BLOB"
        references.append(ref(file, base))
    by_name = {item["path"]: item for item in references}
    complete, failed = [], []
    for file in sorted((base / "snapshots/after").glob("*.http.json")):
        (complete if read(file)["completed"] is True else failed).append(by_name[file.relative_to(base).as_posix()])
    assert len(complete) == 31 and [item["path"] for item in failed] == [FAILED], "AFTER_PREFIX_SET"
    descriptor = {"schema": "p44-after-recovery-v2", **lineage_fields(), "source_index_commit": SOURCE_INDEX,
        "source_contract": by_name["recovery/c4.contract.json"], "source_matrix": by_name["recovery/c4.final-evidence-matrix.json"],
        "predecessor_contract": {**ref(PARENT_CONTRACT, PARENT_CONTRACT.parent), "path": RECOVERY + "/c5.contract.json"},
        "predecessor_matrix": {**ref(PARENT_MATRIX, PARENT), "path": RECOVERY + "/c5.final-evidence-matrix.json"},
        "private_verify_failure": by_name["recovery/private-verify-failure.json"], "offline_identity": dict(OFFLINE_IDENTITY),
        "after_complete": complete, "after_failed": failed, "files": references}
    for key, name in {"target": "target.json", "before": "snapshots/before.json", "negatives": "negatives.json",
                      "run_a": "run-a/final.json", "run_b": "run-b/final.json", "reviewer_attestation": "reviewer-attestation.json"}.items():
        descriptor[key] = by_name[name]
    plan = [(file, DATA / file.relative_to(base)) for file in files]
    plan += [(PARENT_CONTRACT, DATA / descriptor["predecessor_contract"]["path"]),
             (PARENT_MATRIX, DATA / descriptor["predecessor_matrix"]["path"])]
    return plan, descriptor


def verify_import(data=DATA):
    descriptor = read(data / FIXTURE)
    assert set(descriptor) == DESCRIPTOR_KEYS and descriptor["schema"] == "p44-after-recovery-v2", "RECOVERY_SCHEMA"
    assert all(descriptor[key] == value for key, value in lineage_fields().items()) and descriptor["source_index_commit"] == SOURCE_INDEX, "RECOVERY_ANCHOR"
    assert descriptor["offline_identity"] == OFFLINE_IDENTITY, "OFFLINE_IDENTITY_SCOPE"
    ctx = INSPECT.Context(ROOT, data / "manifest.json")
    assert descriptor["source_contract"]["path"] == "recovery/c4.contract.json"
    assert descriptor["source_matrix"]["path"] == "recovery/c4.final-evidence-matrix.json"
    assert descriptor["predecessor_contract"]["path"] == RECOVERY + "/c5.contract.json"
    assert descriptor["predecessor_matrix"]["path"] == RECOVERY + "/c5.final-evidence-matrix.json"
    parent_raw, matrix_raw = ctx.read(descriptor["predecessor_contract"]), ctx.read(descriptor["predecessor_matrix"])
    assert b.sha(parent_raw).upper() == PARENT_HASH and b.sha(matrix_raw).upper() == PARENT_MATRIX_HASH, "RECOVERY_PARENT_HASH"
    parent, matrix = INSPECT.json_bytes(parent_raw), INSPECT.json_bytes(matrix_raw)
    expected = {name.removeprefix("evidence/"): value.upper() for name, value in matrix["evidence_hashes"].items() if name.startswith("evidence/")}
    files = descriptor["files"]
    assert len(files) == len(expected) and {item["path"]: item["sha256"].upper() for item in files} == expected, "RECOVERY_FILE_SET"
    by_name = {item["path"]: item for item in files}
    for item in files:
        ctx.read(item)
    assert descriptor["source_contract"] == by_name["recovery/c4.contract.json"] and descriptor["source_matrix"] == by_name["recovery/c4.final-evidence-matrix.json"]
    assert b.sha(ctx.read(descriptor["source_contract"])).upper() == SOURCE_HASH
    assert b.sha(ctx.read(descriptor["source_matrix"])).upper() == SOURCE_MATRIX_HASH
    assert descriptor["private_verify_failure"] == by_name["recovery/private-verify-failure.json"]
    private_failure = ctx.document(descriptor["private_verify_failure"])
    assert set(private_failure) == {"ok", "started", "ended", "attempts", "error_code"}
    assert private_failure["ok"] is False and private_failure["attempts"] == 1 and private_failure["error_code"] == "ECONNRESET"
    for key, name in {"target": "target.json", "before": "snapshots/before.json", "negatives": "negatives.json",
                      "run_a": "run-a/final.json", "run_b": "run-b/final.json", "reviewer_attestation": "reviewer-attestation.json"}.items():
        assert descriptor[key] == by_name[name], "RECOVERY_INPUT_REFERENCE"
    target, run_a, run_b = (ctx.document(descriptor[key]) for key in ("target", "run_a", "run_b"))
    assert target["commitSha"] == SOURCE_COMMIT and target["versionName"] == "3.2.9", "PRODUCT_TARGET_CHANGED"
    assert run_a["run"]["id"] == 39313672925 and run_a["run"]["conclusion"] == "failure"
    assert run_b["run"]["id"] == 39351100037 and run_b["run"]["conclusion"] == "success"
    assert all(value["run"]["head_sha"] == SOURCE_COMMIT and value["run"]["run_attempt"] == 1 for value in (run_a, run_b))
    complete = [item for item in files if item["path"].startswith("snapshots/after/") and item["path"].endswith(".http.json")
                and ctx.document(item)["completed"] is True]
    assert descriptor["after_complete"] == complete and len(complete) == 31
    assert descriptor["after_failed"] == [by_name[FAILED]] and ctx.document(by_name[FAILED])["completed"] is False
    assert len(b.history_layers(ctx.document(descriptor["source_contract"]), data)) == 3, "HISTORY_DEPTH"
    return descriptor, parent, matrix, ctx


def prepare():
    plan, descriptor = source_plan()
    outputs_absent([destination for _, destination in plan] + [DATA / FIXTURE])
    for source, destination in plan:
        b.write(destination, source.read_bytes())
    b.write(DATA / FIXTURE, descriptor)
    verify_import()
    print(json.dumps({"copied_files": len(plan), "fixture": ref(DATA / FIXTURE), "platform_operations": 0}))


def command_arguments():
    relative = DATA.relative_to(ROOT).as_posix() + "/"
    common = ["-I", "-S", "-B"]
    offline = lambda script, mode, source, output: ["python", *common, script, mode, "--repo-root", ROOT.as_posix(),
                                                   "--input", relative + source, "--output", relative + output]
    return {
        "formal-history": offline("Tools/acceptance/p44/origins.py", "history", "inputs/originals.json", RECOVERY + "/history-result.json"),
        "formal-before": ["python", *common, PYTHON, "verify-existing", "before"],
        "formal-negatives": ["python", *common, PYTHON, "verify-existing", "negatives"],
        "formal-after": ["node", NODE, "after"],
        "formal-assemble-complete": ["node", NODE, "assemble"],
        "formal-approvals": offline("Tools/acceptance/p44/inspect.py", "approvals", "manifest.json", "approvals-result.json"),
        "formal-states": ["python", *common, PYTHON, "states"],
        "formal-privacy": ["python", *common, PYTHON, "privacy"],
    }


def successor(parent, recovery_reference):
    value = copy.deepcopy(parent)
    value.update(contract_id="P4-4-v6", version=6, parent_contract_sha256=PARENT_HASH, implementation_ref=SOURCE_COMMIT)
    arguments = command_arguments()
    for command in value["commands"]:
        name = command["id"]
        if name not in EXECUTED:
            continue
        args = arguments[name]
        command["command"] = " ".join(["node", NODE, "run", name, *args])
        command["input_groups"] = sorted(set(command["input_groups"]) | {"validation"})
        command["runner_paths"] = sorted(set(command["runner_paths"]) | {NODE, PYTHON, "Tools/acceptance/p44/capture.cjs",
            "Tools/acceptance/p44/run.cjs", "Tools/acceptance/p44/bundle.py", "Tools/acceptance/p44/inspect.py",
            "Tools/acceptance/validate_bundle.py"} | {part for part in args if part.endswith((".py", ".cjs"))})
        command["description"] = ("C6 after-evidence recovery only; retain C4 product target, actual C5 predecessor and original timestamps. "
            "One invocation, original IDs, no new dispatch/upload/register/approval/device action. ")
        if name == "formal-after":
            command["description"] += ("Reuse 31 verified complete after responses without network replay; collect only missing fixed SELECT/list data. "
                "Standard proxyTls.timeout/requestTls.timeout=30000, rejectUnauthorized=true, HTTP total signal<=60s, wire/decoded<=16MiB. "
                "Only original admitted read-only pre-response ECONNRESET retry once; no CONNECT_TIMEOUT/HTTP/body/business retry. "
                "Read protected bucket identity only from the fixed hash-bound historical metadata; verify its size, pointer and ID fingerprint offline. "
                "No token verify request, fallback source or API credential discovery. ID and derived key stay in memory. Wrapper watchdog<=60min.")
        else:
            command["description"] += "Offline original-byte verification/assembly only; wrapper watchdog<=60min; preserve all failures."
    for item in value["criteria"]:
        if item["id"] not in REUSED:
            item["input_groups"] = sorted(set(item["input_groups"]) | {"validation"})
            item["external_inputs"] = sorted(set(item["external_inputs"]) | {FIXTURE_ID})
            item["dependency_rationale"] += " Validation additionally binds the C6 offline-identity adapter; C5 failure and C4 observations are unchanged."
        if item["id"] == "P44-RAW-STATE":
            item["description"] = ("Independently verify the complete C4 before snapshot and five authentication denials offline. "
                "Retain all 31 completed C4 after responses at their original timestamps and the connect failure; "
                "retain the C5 private-verify failure without inferring its unrecorded HTTP receive state; "
                "collect only missing fixed SELECT/list data after offline identity checks, then require complete three-resource after evidence. "
                "No replay of successful observations, dispatch, registration, production write, gate unlock or device action.")
    for artifact in value["artifacts"]:
        if artifact["id"] in {"P44-HISTORY-1", "P44-HYGIENE-1"}:
            name = "history" if artifact["id"] == "P44-HISTORY-1" else "privacy"
            artifact["path"] = "evidence/" + RECOVERY + "/" + name + "-result.json"
        if artifact["id"].startswith("P44-RAW-STATE-"):
            artifact["description"] = ("Complete C4 before/negative originals are verified offline; C6 after joins 31 unchanged complete originals "
                "with only missing fixed read-only captures. Retain original times, failed attempts and all predecessor bytes.")
    value["external_inputs"].append({"id": FIXTURE_ID, "category": "fixture",
        "description": "C5 predecessor, C4 original PASS source, unchanged after prefix and fixed offline identity; no verify request or quota reset.",
        "fingerprint": "sha256:" + recovery_reference["sha256"], "evidence_path": "evidence/" + FIXTURE,
        "evidence_sha256": recovery_reference["sha256"]})
    return value


def initial_matrix(contract, digest):
    value = b.initial_matrix(contract, digest)
    value["round_id"] = "P44-20261020-06"
    for item in value["criteria"]:
        item["notes"] = "NOT_RUN: C6 offline-identity recovery; actual predecessor C5 and original C4 PASS remain bound."
    return value


def computed_plan(contract, matrix, parent=None, parent_matrix=None, digest=None):
    parent = parent or read(PARENT_CONTRACT)
    parent_matrix = parent_matrix or read(PARENT_MATRIX)
    return RULES.compute_rerun_plan(contract, parent, parent_matrix,
        current_contract_sha256=(digest or sha(CONTRACT)).upper(), previous_contract_sha256=PARENT_HASH,
        previous_matrix_sha256=PARENT_MATRIX_HASH, current_round_id=matrix["round_id"], repo_root=ROOT,
        reuse_sources=reuse_sources())


def admitted_plan(plan):
    assert set(plan["reusable_criteria"]) == REUSED and set(plan["required_commands"]) == EXECUTED, "RECOVERY_PLAN_DRIFT"
    assert {item["id"] for item in plan["rerun_criteria"]} == {"P44-HISTORY", "P44-RAW-STATE", "P44-APPROVALS", "P44-ISOLATION", "P44-HYGIENE"}
    assert set(plan["reuse_origins"]) == REUSED and all(
        origin == {"contract_sha256": SOURCE_HASH, "matrix_sha256": SOURCE_MATRIX_HASH,
                   "round_id": "P44-20261020-04"} for origin in plan["reuse_origins"].values()), "ORIGIN_PLAN_DRIFT"


def validation_commands():
    common = ["python", "-I", "-S", "-B", "Tools/acceptance/validate_bundle.py", "--contract", CONTRACT.relative_to(ROOT).as_posix(),
              "--repo-root", ROOT.as_posix(), "--previous-contract", PARENT_CONTRACT.relative_to(ROOT).as_posix(),
              "--previous-matrix", PARENT_MATRIX.relative_to(ROOT).as_posix(),
              "--reuse-source", SOURCE_CONTRACT.relative_to(ROOT).as_posix(), SOURCE_MATRIX.relative_to(ROOT).as_posix()]
    initial = [*common, "--matrix", (PACKAGE / "evidence-matrix.json").relative_to(ROOT).as_posix()]
    return {"precheck": " ".join(initial), "plan": " ".join([*initial, "--write-rerun-plan", "rerun-plan.json"]),
            "final": " ".join([*common, "--matrix", (PACKAGE / "final-evidence-matrix.json").relative_to(ROOT).as_posix()])}


def freeze():
    outputs_absent([CONTRACT, PACKAGE / "evidence-matrix.json"])
    source_identity()
    _, parent, _, _ = verify_import()
    value = successor(parent, ref(DATA / FIXTURE))
    value.update(freeze_commit=b.git("rev-parse", "HEAD"), freeze_tree=b.git("rev-parse", "HEAD^{tree}"),
                 approved_at=datetime.now(timezone.utc).isoformat(),
                 approved_by="Independent Codex root; authorized C6 offline-identity after-evidence recovery only",
                 profile_config_blob=b.git("rev-parse", "HEAD:Tools/provenance/manifest_profiles.json"))
    assert value["freeze_commit"] not in {SOURCE_COMMIT, PREDECESSOR_COMMIT} and value["profile_config_blob"] == parent["profile_config_blob"]
    assert not RULES.validate_contract(value) and not RULES.validate_freeze_objects(value, ROOT)
    assert not RULES.validate_execution_worktree(value, ROOT), "DIRTY_RECOVERY_INPUTS"
    raw = (json.dumps(value, indent=2, ensure_ascii=True) + "\n").encode()
    matrix = initial_matrix(value, b.sha(raw))
    plan = computed_plan(value, matrix, digest=b.sha(raw))
    admitted_plan(plan)
    assert not RULES.validate_matrix(matrix, value, b.sha(raw).upper())
    b.write(CONTRACT, raw)
    b.write(PACKAGE / "evidence-matrix.json", matrix)
    print(json.dumps({"contract_sha256": b.sha(raw), "freeze_commit": value["freeze_commit"], "product_commit": SOURCE_COMMIT,
                      "reused_criteria": plan["reusable_criteria"], "commands": validation_commands(), "platform_operations": 0}))


def ready():
    descriptor, parent, parent_matrix, ctx = verify_import()
    contract, initial = read(CONTRACT), read(PACKAGE / "evidence-matrix.json")
    assert contract["freeze_commit"] == b.git("rev-parse", "HEAD") and contract["freeze_tree"] == b.git("rev-parse", "HEAD^{tree}")
    assert not RULES.validate_contract(contract) and not RULES.validate_matrix(initial, contract, sha(CONTRACT).upper())
    assert not RULES.validate_execution_worktree(contract, ROOT), "DIRTY_RECOVERY_INPUTS"
    assert not RULES.validate_external_inputs(contract, PACKAGE), "EXTERNAL_INPUT_CHANGED"
    assert initial["overall_result"] == "NOT_RUN" and not initial["commands"]
    plan = computed_plan(contract, initial, parent, parent_matrix)
    assert plan == read(PACKAGE / "rerun-plan.json"), "RERUN_PLAN_CHANGED"
    admitted_plan(plan)
    for name, key in (("formal-precheck", "precheck"), ("formal-rerun-plan", "plan")):
        receipt = read(DATA / COMMANDS / (name + ".json"))
        assert receipt["process_closed"] is True and receipt["exitCode"] == 0 and receipt["signal"] is None
        assert receipt["label"] == name and Path(receipt["cwd"]).absolute() == ROOT
        assert " ".join([receipt["command"], *receipt["args"]]) == validation_commands()[key]
        assert receipt["output"]["path"] == COMMANDS + "/" + name + ".log", "ADMISSION_OUTPUT_BINDING"
        ctx.read(receipt["output"])
    return contract, initial, plan, parent_matrix, descriptor, ctx


def admit():
    contract, _, _, _, _, _ = ready()
    print(json.dumps({"schema": "p44-after-admission-v1", "ok": True, "freeze_commit": contract["freeze_commit"],
        **lineage_fields(), "contract_sha256": sha(CONTRACT)}))


def database_snapshot(ctx, item, role):
    """C4 inspect.database_snapshot with rowid restriction scoped to enumerated tables."""
    require, d1_rows, integer = INSPECT.require, INSPECT.d1_rows, INSPECT.integer
    database = INSPECT.RESOURCES[role][0]
    schema = d1_rows(ctx, item["schema"], database, INSPECT.SCHEMA_SQL)
    require(all(isinstance(row, dict) and set(row) == {"name", "type", "sql"} for row in schema), "D1_SCHEMA_INVALID")
    table_rows = [row for row in schema if row["type"] == "table" and not row["name"].startswith(("sqlite_", "_cf_"))]
    require(all(not re.search(r"\bWITHOUT\s+ROWID\b", row["sql"] or "", re.IGNORECASE)
                for row in table_rows), "D1_WITHOUT_ROWID_UNSUPPORTED")
    table_names = [row["name"] for row in table_rows]
    require(len(table_names) == len(set(table_names))
            and all(re.fullmatch(r"[a-zA-Z_][a-zA-Z0-9_]*", name) for name in table_names), "D1_TABLE_NAME_INVALID")
    tables = item.get("tables")
    require(isinstance(tables, dict) and set(tables) == set(table_names), "D1_TABLE_SCOPE_INCOMPLETE")
    contents = {}
    for name in table_names:
        counted = d1_rows(ctx, tables[name]["count"], database, 'SELECT COUNT(*) AS count FROM "' + name + '"')
        require(len(counted) == 1 and set(counted[0]) == {"count"}
                and integer(counted[0]["count"]) and counted[0]["count"] <= 20000, "D1_COUNT_BOUND")
        count = counted[0]["count"]
        pages = tables[name].get("pages")
        require(isinstance(pages, list) and len(pages) <= (count + 7) // 8, "D1_PAGINATION_INCOMPLETE")
        rows = []
        for record in pages:
            request = ctx.document(record["request"])
            require(isinstance(request, dict) and set(request) == {"sql"} and isinstance(request["sql"], str), "D1_QUERY_BINDING")
            query = request["sql"]
            match = re.fullmatch(r'SELECT \* FROM "' + re.escape(name)
                                 + r'" ORDER BY rowid LIMIT (8|500) OFFSET (0|[1-9][0-9]*)', query)
            require(match is not None, "D1_QUERY_BINDING")
            limit, offset = int(match[1]), int(match[2])
            require(offset == len(rows) and offset < count, "D1_PAGE_OFFSET_MISMATCH")
            page = d1_rows(ctx, record, database, query)
            require(len(page) == min(limit, count - offset), "D1_PAGE_COUNT_MISMATCH")
            rows.extend(page)
        require(len(rows) == count, "D1_PAGINATION_INCOMPLETE")
        contents[name] = rows
    return {"schema": schema, "tables": contents}


@contextmanager
def compatible_snapshots():
    original = INSPECT.database_snapshot
    INSPECT.database_snapshot = database_snapshot
    try:
        yield
    finally:
        INSPECT.database_snapshot = original


def verify_existing_bytes(kind, descriptor, ctx):
    if kind == "before":
        snapshot = ctx.document(descriptor["before"])
        with compatible_snapshots():
            INSPECT.read_snapshot(ctx, snapshot)
        run = ctx.document(descriptor["run_b"])["run"]
        windows = INSPECT.capture_window(snapshot)
        assert windows and max(end for _, end in windows) <= INSPECT.timestamp(run["created_at"]), "BEFORE_TIME_ORDER"
    else:
        assert kind == "negatives"
        negative = ctx.document(descriptor["negatives"])
        assert negative["ok"] is True and negative["worker_denials"] == 3 and negative["outside_bucket_denials"] == 2
        records = negative["requests"]
        assert len(records) == 5, "NEGATIVE_COUNT"
        labels = ["missing-staging", "production-token-to-staging", "staging-token-to-production",
                  "production-s3-to-staging", "staging-s3-to-production"]
        for index, (record, label) in enumerate(zip(records, labels)):
            assert record["body"]["path"] == "negatives/" + label + ".body", "NEGATIVE_IDENTITY"
            route = "/api/ci/firmware/preflight" if index < 3 else "/" + INSPECT.RESOURCES["staging" if index == 3 else "production"][1] + "/?list-type=2&max-keys=1000"
            body = ctx.response(record, "POST" if index < 3 else "GET", route, 401 if index < 3 else 403)
            if index < 3:
                assert ctx.document(record["request"]) == {}, "NEGATIVE_REQUEST"
                assert INSPECT.json_bytes(body)["errorCode"] == "TOKEN_INVALID", "NEGATIVE_WORKER_CODE"
            else:
                assert INSPECT.xml_single(INSPECT.ET.fromstring(body), "Code") == "AccessDenied", "NEGATIVE_S3_CODE"
    return {"schema": "p44-after-existing-v1", "ok": True, "kind": kind, "source": descriptor[kind],
            **lineage_fields(), "platform_operations": 0}


def verify_existing(kind):
    output = DATA / RECOVERY / (kind + "-result.json")
    outputs_absent([output])
    _, _, _, _, descriptor, ctx = ready()
    result = verify_existing_bytes(kind, descriptor, ctx)
    b.write(output, result)
    print(json.dumps(result))


def states():
    outputs_absent([DATA / "states-result.json"])
    ready()
    with compatible_snapshots():
        code = INSPECT.main(["states", "--repo-root", ROOT.as_posix(), "--input", (DATA / "manifest.json").as_posix(),
                             "--output", (DATA / "states-result.json").as_posix()])
    assert code == 0, "STATE_EVALUATION_FAILED"


def secret_forms(values, local_token):
    needles = set(values) | {local_token, hashlib.sha256(local_token).hexdigest().encode()}
    needles.update(base64.b64encode(item) for item in list(needles))
    assert all(needles), "EMPTY_SECRET_SENTINEL"
    return needles


def offline_id_bytes(raw):
    assert len(raw) == OFFLINE_IDENTITY["size_bytes"] and b.sha(raw) == OFFLINE_IDENTITY["sha256"], "OFFLINE_IDENTITY_BYTES"
    value = INSPECT.json_bytes(raw)
    try:
        identifier = value["body"]["result"]["id"]
    except (KeyError, TypeError):
        raise AssertionError("OFFLINE_IDENTITY_POINTER") from None
    assert isinstance(identifier, str) and re.fullmatch(r"[0-9a-f]{32}", identifier), "OFFLINE_IDENTITY_FORMAT"
    assert b.sha(identifier.encode()) == OFFLINE_IDENTITY["id_sha256"], "OFFLINE_IDENTITY_ID"
    return identifier


def offline_identifier():
    project = ROOT.parents[1]
    return offline_id_bytes(b.guard(project / OFFLINE_IDENTITY["source_path"], project).read_bytes())


def known_needles():
    """C4 protected sources plus the offline ID and derived S3 key, never exported."""
    project, needles = ROOT.parents[1], set()
    sources = ["app/bluetooth_flutter_Trace/cloudflare/update-service/.github-actions-secrets.staging.local.json",
        ".cache/p44-cred-20261019/private/p44-s3-credentials-20261019.json",
        ".cache/p4-4-integration-20261018/.cache/p44/private/production-secrets.json",
        ".cache/p41-dev-20261015/.cache/cf-auth-input/firmware-test-secrets.json",
        ".cache/p41-dev-20261015/.cache/cf-auth-input/p41-rehearsal-ota-key.json"]
    fields = {"cloudflare_account_id", "cloudflare_api_token", "ota_aes_key", "trace_deploy_token", "download_hmac_key_current",
              "download_hmac_key_previous", "token_id_access_key_id", "token_value", "secret_access_key_sha256", "keyhex"}
    def collect(value):
        if isinstance(value, dict):
            for key, item in value.items():
                if isinstance(item, str) and len(item) >= 16 and key.lower() in fields:
                    needles.add(item.encode())
                collect(item)
        elif isinstance(value, list):
            for item in value:
                collect(item)
    for relative in sources:
        collect(json.loads(b.guard(project / relative, project).read_bytes()))
    local_token = b.guard(project / ".cache/p41-dev-20261015/.cache/cf-auth-input/token.txt", project).read_bytes().strip()
    needles.add(b.guard(project / ".cache/p41-dev-20261015/.cache/cf-auth-input/p41-ci-token.txt", project).read_bytes().strip())
    directory = json.loads(b.guard(project / ".cache/p44-root-acceptance-20261019/private/credential-readback-01/03.json", project).read_bytes())
    for token in directory["result"]:
        assert re.fullmatch(r"[0-9a-f]{32}", token["id"])
        needles.add(token["id"].encode())
    env = dict(os.environ, GH_CONFIG_DIR="C:/Users/SU/AppData/Roaming/GitHub CLI", GH_TOKEN="", GITHUB_TOKEN="",
               GH_NO_UPDATE_NOTIFIER="1", GH_NO_EXTENSION_UPDATE_NOTIFIER="1", GH_PROMPT_DISABLED="1")
    auth = subprocess.run(["gh", "auth", "token", "--hostname", "github.com", "--user", "Eitan-S-23"],
                          cwd=ROOT, env=env, stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=30)
    assert auth.returncode == 0 and auth.stdout.strip(), "LOCAL_GITHUB_AUTH_UNAVAILABLE"
    needles.add(auth.stdout.strip())
    needles.add(offline_identifier().encode())
    return secret_forms(needles, local_token)


def scan_public(data, contexts, needles):
    excluded = {data / COMMANDS / "formal-privacy.log", data / COMMANDS / "formal-privacy.json",
                data / RECOVERY / "privacy-result.json"}
    files, scanned, members, decoded, failures = {}, 0, 0, 0, []
    for file in sorted(data.rglob("*")):
        b.guard(file)
        if not file.is_file() or file in excluded:
            continue
        raw, name = file.read_bytes(), file.relative_to(data).as_posix()
        scanned += 1
        digest = b.sha(raw)
        # A token-only file digest can itself be the derived S3 credential.
        sensitive_digest = b.contains_secret(digest.encode(), needles)
        if not sensitive_digest:
            files[name] = digest
        if sensitive_digest or b.contains_secret(raw, needles):
            failures.append(name)
        if file.name.endswith(".http.json"):
            body = b.public_d1_decoded(INSPECT.json_bytes(raw), INSPECT, b.select_privacy_context(file, contexts))
            if body is not None:
                decoded += 1
                if b.contains_secret(body, needles):
                    failures.append(name + "::decoded_body")
        if file.suffix == ".zip":
            with zipfile.ZipFile(file) as archive:
                assert len(archive.infolist()) <= 1024 and sum(item.file_size for item in archive.infolist()) <= 256 * 1024 * 1024
                for item in archive.infolist():
                    if not item.is_dir():
                        members += 1
                        if b.contains_secret(archive.read(item), needles):
                            failures.append(name + "::" + item.filename)
    return {"ok": not failures, "files_scanned": scanned, "file_hashes": files, "zip_members_scanned": members,
            "decoded_d1_scanned": decoded, "known_secret_forms": len(needles), "failed_paths": failures,
            "platform_operations": 0, "limits": "Known secret forms and original strict gzip/signed-URL checks; private wire not published; not proof of never-exposure or unknown-secret detection."}


def privacy():
    output = DATA / RECOVERY / "privacy-result.json"
    outputs_absent([output])
    _, _, _, _, descriptor, ctx = ready()
    lifecycle = read(DATA / "inputs/lifecycle.json")
    assert lifecycle["owner"] == "Eitan-S-23" and lifecycle["gate"] is False
    assert lifecycle["provider_expires_on"] == {"production": None, "rehearsal": None}
    assert lifecycle["provider_ttl_configured"] is False and lifecycle["automatic_job_configured"] is False
    assert lifecycle["operator_review_rotation_deadline"] == {"production": "2027-01-17T07:40:38Z", "rehearsal": "2027-01-17T07:40:50Z"}
    assert all(lifecycle[key] for key in ("decision_author", "rotation", "emergency", "temporary_management"))
    parent = ctx.document(descriptor["source_contract"])
    contexts = b.privacy_contexts(INSPECT, parent, DATA)
    assert len(contexts) == 4
    result = scan_public(DATA, contexts, known_needles())
    result["lifecycle_checked"] = True
    b.write(output, result)
    assert result["ok"], "PUBLIC_SECRET_FOUND"
    print(json.dumps({key: result[key] for key in ("ok", "files_scanned", "decoded_d1_scanned", "zip_members_scanned", "lifecycle_checked")}))


def new_receipt(name, definition, ctx):
    value = read(DATA / COMMANDS / (name + ".json"))
    assert value["label"] == name and value["process_closed"] is True and value["signal"] is None and value["exitCode"] == 0, "RECOVERY_COMMAND_FAILED"
    assert Path(value["cwd"]).absolute() == ROOT
    actual = " ".join(["node", NODE, "run", name, value["command"], *value["args"]])
    assert actual == definition["command"] and value["output"]["path"] == COMMANDS + "/" + name + ".log", "RECOVERY_RECEIPT_BINDING"
    ctx.read(value["output"])
    return {"id": name, "command": actual, "exit_code": value["exitCode"], "output_evidence": "evidence/" + value["output"]["path"]}


def mixed_matrix(contract, initial, plan, parent_matrix, commands, artifacts, hashes):
    admitted_plan(plan)
    sources = reuse_sources()
    value = copy.deepcopy(initial)
    value.update(overall_result="PASS", previous_matrix_sha256=PARENT_MATRIX_HASH, rerun_plan_path="rerun-plan.json",
                 rerun_plan_sha256=hashes["rerun-plan.json"], commands=commands, artifacts=artifacts, evidence_hashes=hashes)
    for index, item in enumerate(value["criteria"]):
        if item["id"] in REUSED:
            origin = plan["reuse_origins"][item["id"]]
            original_matrix = sources[origin["matrix_sha256"]]["matrix"]
            original = next(row for row in original_matrix["criteria"] if row["id"] == item["id"])
            assert original["execution"] == "EXECUTED" and original["result"] == "PASS", "ORIGIN_NOT_EXECUTED_PASS"
            value["criteria"][index] = {**copy.deepcopy(original), "execution": "REUSED", "reused_from_round": origin["round_id"],
                "origin_contract_sha256": origin["contract_sha256"], "origin_matrix_sha256": origin["matrix_sha256"]}
        else:
            definition = next(row for row in contract["criteria"] if row["id"] == item["id"])
            evidence = [row["path"] for row in contract["artifacts"] if row["id"] in definition["artifact_ids"]]
            evidence += ["evidence/" + COMMANDS + "/" + name + ".json" for name in definition["command_ids"]]
            item.update(result="PASS", observed=True, evidence=evidence, notes="C6 required original-byte evaluation or missing read-only capture; C5 failure and C4 business success retained, no replay or gate unlock.")
    assert not RULES.validate_matrix(value, contract, value["contract_sha256"]), "FINAL_MATRIX_SCHEMA"
    assert not RULES.validate_reuse(value, contract, parent_matrix, plan, sources), "REUSE_BINDING"
    assert not RULES.validate_planned_execution(value, contract, plan), "UNPLANNED_EXECUTION"
    return value


def capture_results(contract, descriptor, ctx):
    after_result, assembly = (read(DATA / RECOVERY / (name + "-result.json")) for name in ("after", "assemble"))
    for result in (after_result, assembly):
        assert result["ok"] is True and all(result[key] == value for key, value in lineage_fields().items()), "CAPTURE_SOURCE_BINDING"
        assert result["freeze_commit"] == contract["freeze_commit"], "CAPTURE_SOURCE_BINDING"
    for result, key, path in ((after_result, "snapshot", "snapshots/after.json"), (assembly, "manifest", "manifest.json")):
        assert result[key]["path"] == path and result[key] == ref(DATA / path), "CAPTURE_RESULT_REFERENCE"
        ctx.read(result[key])
    after, manifest = ctx.document(after_result["snapshot"]), ctx.document(assembly["manifest"])
    assert manifest["snapshots"]["after"] == after, "MANIFEST_AFTER_BINDING"
    assert manifest["snapshots"]["before"] == ctx.document(descriptor["before"]), "MANIFEST_BEFORE_BINDING"
    original = read(DATA / "rehearsal-manifest.json")
    assert all(manifest[key] == original[key] for key in ("run_a", "run_b", "target", "artifact")), "MANIFEST_PRODUCT_BINDING"

    def records(value):
        if isinstance(value, dict):
            if {"method", "path", "started", "ended", "body"} <= set(value):
                yield value
            else:
                for item in value.values():
                    yield from records(item)
        elif isinstance(value, list):
            for item in value:
                yield from records(item)

    collected = list(records(after))
    assert all(item["completed"] is True for item in collected)
    assert all(ctx.document(item) in collected for item in descriptor["after_complete"]), "AFTER_PREFIX_MISSING"


def assess():
    outputs_absent([PACKAGE / "final-evidence-matrix.json"])
    contract, initial, plan, previous, descriptor, ctx = ready()
    for name in ("history", "before", "negatives", "after", "assemble", "privacy"):
        result = read(DATA / RECOVERY / (name + "-result.json"))
        assert result["ok"] is True, "RECOVERY_RESULT_FAILED"
    assert read(DATA / RECOVERY / "history-result.json")["manifest_sha256"] == sha(DATA / "inputs/originals.json")
    for kind in ("before", "negatives"):
        assert read(DATA / RECOVERY / (kind + "-result.json")) == verify_existing_bytes(kind, descriptor, ctx)
    capture_results(contract, descriptor, ctx)
    manifest_hash = sha(DATA / "manifest.json")
    for name in ("approvals", "states"):
        result = read(DATA / (name + "-result.json"))
        assert result["ok"] is True and result["manifest_sha256"] == manifest_hash
    assert set(read(DATA / "snapshots/after.json")["databases"]) == {"production", "protected", "staging"}
    privacy_result = read(DATA / RECOVERY / "privacy-result.json")
    assert privacy_result["lifecycle_checked"] is True and not privacy_result["failed_paths"]
    excluded = {COMMANDS + "/formal-privacy.log", COMMANDS + "/formal-privacy.json", RECOVERY + "/privacy-result.json"}
    hashes = {file.relative_to(PACKAGE).as_posix(): sha(file) for file in DATA.rglob("*") if file.is_file()}
    scanned = {name.removeprefix("evidence/"): digest for name, digest in hashes.items() if name.removeprefix("evidence/") not in excluded}
    assert privacy_result["file_hashes"] == scanned, "POST_PRIVACY_BYTES_CHANGED"
    hashes["rerun-plan.json"] = sha(PACKAGE / "rerun-plan.json")
    hashes["evidence-matrix.json"] = sha(PACKAGE / "evidence-matrix.json")
    previous_commands = {row["id"]: row for row in reuse_sources()[SOURCE_MATRIX_HASH]["matrix"]["commands"]}
    commands = [new_receipt(item["id"], item, ctx) if item["id"] in EXECUTED else copy.deepcopy(previous_commands[item["id"]])
                for item in contract["commands"]]
    artifacts = [{"id": item["id"], "path": item["path"], "sha256": sha(PACKAGE / item["path"]),
                  "size": b.guard(PACKAGE / item["path"]).stat().st_size} for item in contract["artifacts"]]
    value = mixed_matrix(contract, initial, plan, previous, commands, artifacts, hashes)
    b.write(PACKAGE / "final-evidence-matrix.json", value)
    print(json.dumps({"overall_result": "PASS", "reused": sorted(REUSED), "executed_commands": sorted(EXECUTED),
                      "final_validation_command": validation_commands()["final"], "sealing_logs": "Outside evidence DATA"}))


class SafeParser(argparse.ArgumentParser):
    def error(self, message):
        raise ValueError("INVALID_ARGUMENTS")


def main(argv=None):
    parser = SafeParser(description=__doc__)
    parser.add_argument("mode", choices=("prepare", "freeze", "privacy", "assess", "verify-existing", "admit", "states"))
    parser.add_argument("kind", nargs="?", choices=("before", "negatives"))
    try:
        args = parser.parse_args(argv)
        assert Path.cwd().absolute() == ROOT and sys.flags.optimize == 0 and sys.dont_write_bytecode, "EXECUTION_CONTEXT"
        assert (args.kind is not None) == (args.mode == "verify-existing"), "MODE_ARGUMENTS"
        if args.mode == "verify-existing":
            verify_existing(args.kind)
        else:
            {"prepare": prepare, "freeze": freeze, "privacy": privacy, "assess": assess, "admit": admit, "states": states}[args.mode]()
        return 0
    except Exception as error:
        code = str(error)
        print(json.dumps({"ok": False, "error_code": code if re.fullmatch(r"[A-Z][A-Z0-9_]{0,79}", code) else "P44_AFTER_FAILED"}))
        return 1


if __name__ == "__main__":
    sys.exit(main())
