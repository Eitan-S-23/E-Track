"""Fixed C4-to-C5 after-evidence adapter; no release or network controller."""
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
SOURCE = "2756ca95e26ec636216313271708b3304d61a5cc"
BUNDLE = "da37711799a21c4eb2c5d082dab1a7b81d028511"
INDEX = "7168568489ab0eb67a9e7a05106f245e7243421e"
PARENT_HASH = "86764FA47B8C52D748BF93B83C5735352CEAB69519D8FFCC4C6BFC706F8939B5"
PARENT_MATRIX_HASH = "25D71CCB7707C83A62ACE11E6662B2BDEAB5E85DF45FAA557326010219F038D7"
PARENT = ROOT / "docs/acceptance-contracts/P4-4-v4"
PARENT_CONTRACT = PARENT.with_suffix(".contract.json")
PARENT_MATRIX = PARENT / "final-evidence-matrix.json"
PACKAGE = ROOT / "docs/acceptance-contracts/P4-4-v5"
DATA = PACKAGE / "evidence"
CONTRACT = PACKAGE.with_suffix(".contract.json")
FIXTURE = "inputs/after-recovery.json"
NODE = "Tools/ota/p44-after-recovery.cjs"
PYTHON = "Tools/ota/p44-after-bundle.py"
REUSED = {"P44-CONFIGURATION", "P44-RAW-RUNS", "P44-REHEARSAL", "P44-RAW-READBACK"}
EXECUTED = {"formal-history", "formal-before", "formal-negatives", "formal-after",
            "formal-assemble-complete", "formal-approvals", "formal-states", "formal-privacy"}
FAILED = "snapshots/after/protected-audit_logs-rows8-16.http.json"
DESCRIPTOR_KEYS = {"schema", "source_commit", "source_bundle_commit", "source_index_commit",
                   "source_contract", "source_matrix", "target", "before", "negatives", "run_a", "run_b",
                   "reviewer_attestation", "after_complete", "after_failed", "files"}


def read(file):
    return INSPECT.json_bytes(b.guard(file).read_bytes())


def sha(file):
    return b.sha(b.guard(file).read_bytes())


def ref(file, base=None):
    return b.ref(b.guard(file), DATA if base is None else base)


def outputs_absent(files):
    for file in files:
        assert not b.guard(file).exists(), "OUTPUT_ALREADY_EXISTS"


def source_identity():
    for left, right in ((SOURCE, BUNDLE), (BUNDLE, INDEX), (INDEX, "HEAD")):
        b.git("merge-base", "--is-ancestor", left, right)
    contract, matrix = read(PARENT_CONTRACT), read(PARENT_MATRIX)
    assert sha(PARENT_CONTRACT).upper() == PARENT_HASH and sha(PARENT_MATRIX).upper() == PARENT_MATRIX_HASH
    for file in (PARENT_CONTRACT, PARENT_MATRIX):
        assert b.git_bytes("show", BUNDLE + ":" + file.relative_to(ROOT).as_posix()) == file.read_bytes(), "PARENT_GIT_BYTES"
    assert contract["freeze_commit"] == SOURCE and matrix["overall_result"] == "EVIDENCE_GAP"
    assert not RULES.validate_contract(contract) and not RULES.validate_matrix(matrix, contract, PARENT_HASH)
    return contract, matrix


def source_plan():
    contract, matrix = source_identity()
    base = PARENT / "evidence"
    hashes = {name.removeprefix("evidence/"): value for name, value in matrix["evidence_hashes"].items()
              if name.startswith("evidence/")}
    files = sorted(b.guard(file) for file in base.rglob("*") if file.is_file())
    assert {file.relative_to(base).as_posix() for file in files} == set(hashes), "PARENT_FILE_SET"
    git_files = {}
    for line in b.git_bytes("ls-tree", "-r", "-z", BUNDLE, "--", base.relative_to(ROOT).as_posix()).split(b"\0"):
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
    descriptor = {"schema": "p44-after-recovery-v1", "source_commit": SOURCE, "source_bundle_commit": BUNDLE,
        "source_index_commit": INDEX, "source_contract": {**ref(PARENT_CONTRACT, PARENT_CONTRACT.parent), "path": "recovery/c4.contract.json"},
        "source_matrix": {**ref(PARENT_MATRIX, PARENT), "path": "recovery/c4.final-evidence-matrix.json"},
        "after_complete": complete, "after_failed": failed, "files": references}
    for key, name in {"target": "target.json", "before": "snapshots/before.json", "negatives": "negatives.json",
                      "run_a": "run-a/final.json", "run_b": "run-b/final.json", "reviewer_attestation": "reviewer-attestation.json"}.items():
        descriptor[key] = by_name[name]
    plan = [(file, DATA / file.relative_to(base)) for file in files]
    plan += [(PARENT_CONTRACT, DATA / descriptor["source_contract"]["path"]),
             (PARENT_MATRIX, DATA / descriptor["source_matrix"]["path"])]
    return plan, descriptor


def verify_import(data=DATA):
    descriptor = read(data / FIXTURE)
    assert set(descriptor) == DESCRIPTOR_KEYS and descriptor["schema"] == "p44-after-recovery-v1", "RECOVERY_SCHEMA"
    assert (descriptor["source_commit"], descriptor["source_bundle_commit"], descriptor["source_index_commit"]) == (SOURCE, BUNDLE, INDEX), "RECOVERY_ANCHOR"
    ctx = INSPECT.Context(ROOT, data / "manifest.json")
    assert descriptor["source_contract"]["path"] == "recovery/c4.contract.json"
    assert descriptor["source_matrix"]["path"] == "recovery/c4.final-evidence-matrix.json"
    parent_raw, matrix_raw = ctx.read(descriptor["source_contract"]), ctx.read(descriptor["source_matrix"])
    assert b.sha(parent_raw).upper() == PARENT_HASH and b.sha(matrix_raw).upper() == PARENT_MATRIX_HASH, "RECOVERY_PARENT_HASH"
    parent, matrix = INSPECT.json_bytes(parent_raw), INSPECT.json_bytes(matrix_raw)
    expected = {name.removeprefix("evidence/"): value.upper() for name, value in matrix["evidence_hashes"].items() if name.startswith("evidence/")}
    files = descriptor["files"]
    assert len(files) == len(expected) and {item["path"]: item["sha256"].upper() for item in files} == expected, "RECOVERY_FILE_SET"
    by_name = {item["path"]: item for item in files}
    for item in files:
        ctx.read(item)
    for key, name in {"target": "target.json", "before": "snapshots/before.json", "negatives": "negatives.json",
                      "run_a": "run-a/final.json", "run_b": "run-b/final.json", "reviewer_attestation": "reviewer-attestation.json"}.items():
        assert descriptor[key] == by_name[name], "RECOVERY_INPUT_REFERENCE"
    target, run_a, run_b = (ctx.document(descriptor[key]) for key in ("target", "run_a", "run_b"))
    assert target["commitSha"] == SOURCE and target["versionName"] == "3.2.9", "PRODUCT_TARGET_CHANGED"
    assert run_a["run"]["id"] == 39313672925 and run_a["run"]["conclusion"] == "failure"
    assert run_b["run"]["id"] == 39351100037 and run_b["run"]["conclusion"] == "success"
    assert all(value["run"]["head_sha"] == SOURCE and value["run"]["run_attempt"] == 1 for value in (run_a, run_b))
    complete = [item for item in files if item["path"].startswith("snapshots/after/") and item["path"].endswith(".http.json")
                and ctx.document(item)["completed"] is True]
    assert descriptor["after_complete"] == complete and len(complete) == 31
    assert descriptor["after_failed"] == [by_name[FAILED]] and ctx.document(by_name[FAILED])["completed"] is False
    assert len(b.history_layers(parent, data)) == 3, "HISTORY_DEPTH"
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
        "formal-history": offline("Tools/acceptance/p44/origins.py", "history", "inputs/originals.json", "recovery/history-result.json"),
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
    value.update(contract_id="P4-4-v5", version=5, parent_contract_sha256=PARENT_HASH, implementation_ref=SOURCE)
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
        command["description"] = ("C5 after-evidence recovery only; retain C4 product target and original timestamps. "
            "One invocation, original IDs, no new dispatch/upload/register/approval/device action. ")
        if name == "formal-after":
            command["description"] += ("Reuse 31 verified complete after responses without network replay; collect only missing fixed SELECT/list data. "
                "Standard proxyTls.timeout/requestTls.timeout=30000, rejectUnauthorized=true, HTTP total signal<=60s, wire/decoded<=16MiB. "
                "Only original admitted read-only pre-response ECONNRESET retry once; no CONNECT_TIMEOUT/HTTP/body/business retry. "
                "If the protected bucket AccessKeyID is absent, one authenticated token verify attempt without retry is allowed as a read-only credential preflight; "
                "retain only its fingerprint publicly. Connect recovery is not D1 acceptance. Wrapper watchdog<=60min.")
        else:
            command["description"] += "Offline original-byte verification/assembly only; wrapper watchdog<=60min; preserve all failures."
    for item in value["criteria"]:
        if item["id"] not in REUSED:
            item["input_groups"] = sorted(set(item["input_groups"]) | {"validation"})
            item["external_inputs"] = sorted(set(item["external_inputs"]) | {"after-recovery"})
            item["dependency_rationale"] += " Validation additionally binds the C5-only recovery adapter; product and C4 observations are unchanged."
        if item["id"] == "P44-RAW-STATE":
            item["description"] = ("Independently verify the complete C4 before snapshot and five authentication denials offline. "
                "Retain all 31 completed C4 after responses at their original timestamps and the connect failure; "
                "collect only missing fixed SELECT/list data, then require complete three-resource after evidence. "
                "No replay of successful observations, dispatch, registration, production write, gate unlock or device action.")
    for artifact in value["artifacts"]:
        if artifact["id"] in {"P44-HISTORY-1", "P44-HYGIENE-1"}:
            artifact["path"] = artifact["path"].replace("evidence/", "evidence/recovery/", 1)
        if artifact["id"].startswith("P44-RAW-STATE-"):
            artifact["description"] = ("Complete C4 before/negative originals are verified offline; C5 after joins 31 unchanged complete originals "
                "with only missing fixed read-only captures. Retain original times, failed attempts and all predecessor bytes.")
    value["external_inputs"].append({"id": "after-recovery", "category": "fixture",
        "description": "C4 immutable bundle and exact after prefix; only missing read-only evidence may be collected; no quota reset.",
        "fingerprint": "sha256:" + recovery_reference["sha256"], "evidence_path": "evidence/" + FIXTURE,
        "evidence_sha256": recovery_reference["sha256"]})
    return value


def initial_matrix(contract, digest):
    value = b.initial_matrix(contract, digest)
    value["round_id"] = "P44-20261020-05"
    for item in value["criteria"]:
        item["notes"] = "NOT_RUN: C5 missing-after recovery, retaining C4 business success and all failed originals."
    return value


def computed_plan(contract, matrix, parent=None, parent_matrix=None, digest=None):
    parent = parent or read(PARENT_CONTRACT)
    parent_matrix = parent_matrix or read(PARENT_MATRIX)
    return RULES.compute_rerun_plan(contract, parent, parent_matrix,
        current_contract_sha256=(digest or sha(CONTRACT)).upper(), previous_contract_sha256=PARENT_HASH,
        previous_matrix_sha256=PARENT_MATRIX_HASH, current_round_id=matrix["round_id"], repo_root=ROOT)


def admitted_plan(plan):
    assert set(plan["reusable_criteria"]) == REUSED and set(plan["required_commands"]) == EXECUTED, "RECOVERY_PLAN_DRIFT"
    assert {item["id"] for item in plan["rerun_criteria"]} == {"P44-HISTORY", "P44-RAW-STATE", "P44-APPROVALS", "P44-ISOLATION", "P44-HYGIENE"}


def validation_commands():
    common = ["python", "-I", "-S", "-B", "Tools/acceptance/validate_bundle.py", "--contract", CONTRACT.relative_to(ROOT).as_posix(),
              "--repo-root", ROOT.as_posix(), "--previous-contract", PARENT_CONTRACT.relative_to(ROOT).as_posix(),
              "--previous-matrix", PARENT_MATRIX.relative_to(ROOT).as_posix()]
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
                 approved_by="Independent Codex root; authorized C4 after-evidence recovery only",
                 profile_config_blob=b.git("rev-parse", "HEAD:Tools/provenance/manifest_profiles.json"))
    assert value["freeze_commit"] != SOURCE and value["profile_config_blob"] == parent["profile_config_blob"]
    assert not RULES.validate_contract(value) and not RULES.validate_freeze_objects(value, ROOT)
    assert not RULES.validate_execution_worktree(value, ROOT), "DIRTY_RECOVERY_INPUTS"
    raw = (json.dumps(value, indent=2, ensure_ascii=True) + "\n").encode()
    matrix = initial_matrix(value, b.sha(raw))
    plan = computed_plan(value, matrix, digest=b.sha(raw))
    admitted_plan(plan)
    assert not RULES.validate_matrix(matrix, value, b.sha(raw).upper())
    b.write(CONTRACT, raw)
    b.write(PACKAGE / "evidence-matrix.json", matrix)
    print(json.dumps({"contract_sha256": b.sha(raw), "freeze_commit": value["freeze_commit"], "product_commit": SOURCE,
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
        receipt = read(DATA / "recovery-commands" / (name + ".json"))
        assert receipt["process_closed"] is True and receipt["exitCode"] == 0 and receipt["signal"] is None
        assert receipt["label"] == name and Path(receipt["cwd"]).absolute() == ROOT
        assert " ".join([receipt["command"], *receipt["args"]]) == validation_commands()[key]
        ctx.read(receipt["output"])
    return contract, initial, plan, parent_matrix, descriptor, ctx


def admit():
    contract, _, _, _, _, _ = ready()
    print(json.dumps({"schema": "p44-after-admission-v1", "ok": True, "freeze_commit": contract["freeze_commit"],
        "source_commit": SOURCE, "source_bundle_commit": BUNDLE, "contract_sha256": sha(CONTRACT)}))


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
            "source_bundle_commit": BUNDLE, "platform_operations": 0}


def verify_existing(kind):
    output = DATA / "recovery" / (kind + "-result.json")
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


def known_needles():
    """Same protected sources as C4; only the non-exported loading glue is adapted."""
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
    return secret_forms(needles, local_token)


def scan_public(data, contexts, needles):
    excluded = {data / "recovery-commands/formal-privacy.log", data / "recovery-commands/formal-privacy.json",
                data / "recovery/privacy-result.json"}
    files, members, decoded, failures = {}, 0, 0, []
    for file in sorted(data.rglob("*")):
        b.guard(file)
        if not file.is_file() or file in excluded:
            continue
        raw, name = file.read_bytes(), file.relative_to(data).as_posix()
        files[name] = b.sha(raw)
        if b.contains_secret(raw, needles):
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
    return {"ok": not failures, "files_scanned": len(files), "file_hashes": files, "zip_members_scanned": members,
            "decoded_d1_scanned": decoded, "known_secret_forms": len(needles), "failed_paths": failures,
            "platform_operations": 0, "limits": "Known secret forms and original strict gzip/signed-URL checks; private wire not published; not proof of never-exposure or unknown-secret detection."}


def privacy():
    output = DATA / "recovery/privacy-result.json"
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
    value = read(DATA / "recovery-commands" / (name + ".json"))
    assert value["label"] == name and value["process_closed"] is True and value["signal"] is None and value["exitCode"] == 0, "RECOVERY_COMMAND_FAILED"
    assert Path(value["cwd"]).absolute() == ROOT
    actual = " ".join(["node", NODE, "run", name, value["command"], *value["args"]])
    assert actual == definition["command"] and value["output"]["path"] == "recovery-commands/" + name + ".log", "RECOVERY_RECEIPT_BINDING"
    ctx.read(value["output"])
    return {"id": name, "command": actual, "exit_code": value["exitCode"], "output_evidence": "evidence/" + value["output"]["path"]}


def mixed_matrix(contract, initial, plan, parent_matrix, commands, artifacts, hashes):
    admitted_plan(plan)
    value = copy.deepcopy(initial)
    value.update(overall_result="PASS", previous_matrix_sha256=PARENT_MATRIX_HASH, rerun_plan_path="rerun-plan.json",
                 rerun_plan_sha256=hashes["rerun-plan.json"], commands=commands, artifacts=artifacts, evidence_hashes=hashes)
    for index, item in enumerate(value["criteria"]):
        if item["id"] in REUSED:
            previous = next(row for row in parent_matrix["criteria"] if row["id"] == item["id"])
            assert previous["execution"] == "EXECUTED" and previous["result"] == "PASS"
            origin = plan["reuse_origins"][item["id"]]
            value["criteria"][index] = {**copy.deepcopy(previous), "execution": "REUSED", "reused_from_round": origin["round_id"],
                "origin_contract_sha256": origin["contract_sha256"], "origin_matrix_sha256": origin["matrix_sha256"]}
        else:
            definition = next(row for row in contract["criteria"] if row["id"] == item["id"])
            evidence = [row["path"] for row in contract["artifacts"] if row["id"] in definition["artifact_ids"]]
            evidence += ["evidence/recovery-commands/" + name + ".json" for name in definition["command_ids"]]
            item.update(result="PASS", observed=True, evidence=evidence, notes="C5 required original-byte evaluation or missing read-only capture; C4 business success retained, no replay or gate unlock.")
    assert not RULES.validate_matrix(value, contract, value["contract_sha256"]), "FINAL_MATRIX_SCHEMA"
    assert not RULES.validate_reuse(value, contract, parent_matrix, plan), "REUSE_BINDING"
    assert not RULES.validate_planned_execution(value, contract, plan), "UNPLANNED_EXECUTION"
    return value


def capture_results(contract, descriptor, ctx):
    after_result, assembly = (read(DATA / "recovery" / (name + "-result.json")) for name in ("after", "assemble"))
    for result in (after_result, assembly):
        assert result["ok"] is True and result["source_commit"] == SOURCE and result["source_bundle_commit"] == BUNDLE
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
        result = read(DATA / "recovery" / (name + "-result.json"))
        assert result["ok"] is True, "RECOVERY_RESULT_FAILED"
    assert read(DATA / "recovery/history-result.json")["manifest_sha256"] == sha(DATA / "inputs/originals.json")
    for kind in ("before", "negatives"):
        assert read(DATA / "recovery" / (kind + "-result.json")) == verify_existing_bytes(kind, descriptor, ctx)
    capture_results(contract, descriptor, ctx)
    manifest_hash = sha(DATA / "manifest.json")
    for name in ("approvals", "states"):
        result = read(DATA / (name + "-result.json"))
        assert result["ok"] is True and result["manifest_sha256"] == manifest_hash
    assert set(read(DATA / "snapshots/after.json")["databases"]) == {"production", "protected", "staging"}
    privacy_result = read(DATA / "recovery/privacy-result.json")
    assert privacy_result["lifecycle_checked"] is True and not privacy_result["failed_paths"]
    excluded = {"recovery-commands/formal-privacy.log", "recovery-commands/formal-privacy.json", "recovery/privacy-result.json"}
    hashes = {file.relative_to(PACKAGE).as_posix(): sha(file) for file in DATA.rglob("*") if file.is_file()}
    scanned = {name.removeprefix("evidence/"): digest for name, digest in hashes.items() if name.removeprefix("evidence/") not in excluded}
    assert privacy_result["file_hashes"] == scanned, "POST_PRIVACY_BYTES_CHANGED"
    hashes["rerun-plan.json"] = sha(PACKAGE / "rerun-plan.json")
    hashes["evidence-matrix.json"] = sha(PACKAGE / "evidence-matrix.json")
    previous_commands = {row["id"]: row for row in previous["commands"]}
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
