"""After-evidence successor adapter; C4 observations remain the reuse origin."""
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
LEGACY_PREDECESSOR = (PREDECESSOR_COMMIT, PREDECESSOR_BUNDLE, PREDECESSOR_INDEX)
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
C6_TOOL = "6fffaa25442bdcd863f3a3f4e93e20ebe180a2c1"
BRANCH = "dev/p4-4/config-integration-20261018"
REPO_API = INSPECT.REPO_API
REUSED = {"P44-CONFIGURATION", "P44-RAW-RUNS", "P44-REHEARSAL", "P44-RAW-READBACK"}
EXECUTED = {"formal-history", "formal-before", "formal-negatives", "formal-after",
            "formal-assemble-complete", "formal-approvals", "formal-states", "formal-privacy"}
FAILED = "snapshots/after/protected-audit_logs-rows8-16.http.json"
TAIL = "snapshots/after-tail-v6"
PRIVATE_WIRE = ".cache/p44/private/capture-failures/P4-4-v6/"
PARTIAL_FIELDS = {"partial_body_sha256", "partial_body_size_bytes", "partial_projection", "private_wire", "wire_received_size_bytes"}
LEGACY_RESERVATION = RECOVERY + "/after-reservation.json"
RESUME_SCHEMA = "p44-after-resume-reservation-v1"
ATTEMPT_RESULT_SCHEMA = "p44-after-attempt-result-v1"
RECOVERY_RESULT_SCHEMA = "p44-after-recovery-result-v2"
LEGACY_KEYS = {"first_missing", "old_complete", "old_failed", "predecessor_bundle_commit", "predecessor_commit",
               "predecessor_index_commit", "product_commit", "source_bundle_commit", "started", "tool_commit"}
RESUME_KEYS = {"attempt", "first_missing", "head", "predecessor_bundle_commit", "predecessor_commit",
               "predecessor_index_commit", "previous_attempts", "product_commit", "reused_complete", "reused_failures",
               "reused_records", "schema", "source_bundle_commit", "started", "tool_commit", "tool_sha256"}
RESULT_KEYS = {"attempt", "complete_labels", "ended", "failure_labels", "failures", "new_reads", "ok", "reservation",
               "reservation_sha256", "schema", "started"}
RESULT_OPTIONAL = {"error_code"}
RECOVERY_KEYS = {"source_commit", "source_bundle_commit", "tool_commit", "predecessor_commit", "predecessor_bundle_commit",
                 "predecessor_index_commit", "input", "complete_originals", "failed_originals", "private_verify_failure",
                 "attempts", "reused_complete", "reused_failures", "reused_records", "new_reads", "first_missing",
                 "interpretation"}
DESCRIPTOR_KEYS = {"schema", "source_commit", "source_bundle_commit", "source_index_commit",
                   "source_contract", "source_matrix", "target", "before", "negatives", "run_a", "run_b",
                   "reviewer_attestation", "after_complete", "after_failed", "files", "predecessor_commit",
                   "predecessor_bundle_commit", "predecessor_index_commit", "predecessor_contract",
                   "predecessor_matrix", "private_verify_failure", "offline_identity"}
PACKAGE_SPEC = None
PACKAGE_SPEC_PATH = None


def configure_package(name):
    global PACKAGE_SPEC, PACKAGE_SPEC_PATH, PACKAGE, DATA, CONTRACT, PARENT, PARENT_CONTRACT, PARENT_MATRIX
    global PREDECESSOR_COMMIT, PREDECESSOR_BUNDLE, PREDECESSOR_INDEX, PARENT_HASH, PARENT_MATRIX_HASH
    global FIXTURE, FIXTURE_ID, RECOVERY, COMMANDS, PRIVATE_WIRE
    assert PACKAGE_SPEC is None, "PACKAGE_ALREADY_SELECTED"
    assert re.fullmatch(r"[a-zA-Z0-9_./-]+", name) and all(part not in {"", ".", ".."} for part in name.split("/")), "PACKAGE_PATH"
    value = read(ROOT / name)
    assert set(value) == {"schema", "version", "package", "predecessor", "round_id", "max_after_invocations"}, "PACKAGE_FIELDS"
    assert value["schema"] == "p44-after-package-v1" and type(value["version"]) is int and value["version"] >= 7, "PACKAGE_VERSION"
    assert value["package"] == "docs/acceptance-contracts/P4-4-v" + str(value["version"]), "PACKAGE_PATH"
    assert type(value["max_after_invocations"]) is int and value["max_after_invocations"] == 2, "INVOCATION_LIMIT"
    assert re.fullmatch(r"P44-[a-zA-Z0-9-]+", value["round_id"]), "PACKAGE_ROUND"
    previous = value["predecessor"]
    assert set(previous) == {"commit", "bundle_commit", "index_commit", "contract_sha256", "matrix_sha256"}, "PACKAGE_PREDECESSOR"
    assert all(re.fullmatch(r"[0-9a-f]{40}", previous[key]) for key in ("commit", "bundle_commit", "index_commit")), "PACKAGE_COMMIT"
    assert all(re.fullmatch(r"[0-9a-f]{64}", previous[key]) for key in ("contract_sha256", "matrix_sha256")), "PACKAGE_HASH"
    PACKAGE_SPEC, PACKAGE_SPEC_PATH = value, name
    PACKAGE = b.guard(ROOT / value["package"])
    DATA, CONTRACT = PACKAGE / "evidence", PACKAGE.with_suffix(".contract.json")
    PARENT = ROOT / ("docs/acceptance-contracts/P4-4-v" + str(value["version"] - 1))
    PARENT_CONTRACT, PARENT_MATRIX = PARENT.with_suffix(".contract.json"), PARENT / "final-evidence-matrix.json"
    PREDECESSOR_COMMIT, PREDECESSOR_BUNDLE, PREDECESSOR_INDEX = (previous[key] for key in ("commit", "bundle_commit", "index_commit"))
    PARENT_HASH, PARENT_MATRIX_HASH = (previous[key].upper() for key in ("contract_sha256", "matrix_sha256"))
    FIXTURE_ID = "after-recovery-v" + str(value["version"])
    FIXTURE = "inputs/" + FIXTURE_ID + ".json"
    RECOVERY, COMMANDS = "recovery-v" + str(value["version"]), "recovery-commands-v" + str(value["version"])
    PRIVATE_WIRE = ".cache/p44/private/capture-failures/P4-4-v" + str(value["version"]) + "/"
    return value


def package_args():
    return ["--package-spec", PACKAGE_SPEC_PATH] if PACKAGE_SPEC else []


def previous_stem():
    return "c" + str(PACKAGE_SPEC["version"] - 1 if PACKAGE_SPEC else 5)


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


def reuse_source_packages():
    """按目标轮次推导复用来源包：v6 仅 C4，v7 为 C4+C5，依此类推。"""
    version = PACKAGE_SPEC["version"] if PACKAGE_SPEC else 6
    return [ROOT / ("docs/acceptance-contracts/P4-4-v" + str(number)) for number in range(4, version - 1)]


def reuse_source_paths():
    return [(package.with_suffix(".contract.json"), package / "final-evidence-matrix.json")
            for package in reuse_source_packages()]


def _load_reuse_source(package, expected_matrix_hash):
    """加载并核验一个复用来源包，缺失、篡改或身份漂移都必须失败。"""
    contract_path, matrix_path = package.with_suffix(".contract.json"), package / "final-evidence-matrix.json"
    assert contract_path.is_file() and matrix_path.is_file(), "REUSE_SOURCE_MISSING"
    contract, matrix, contract_hash, matrix_hash = RULES._load_bundle(b.guard(contract_path), b.guard(matrix_path))
    assert matrix_hash == expected_matrix_hash.upper(), "REUSE_SOURCE_HASH"
    version = contract.get("version")
    assert package.name == "P4-4-v" + str(version), "REUSE_SOURCE_IDENTITY"
    assert contract.get("contract_id") == package.name, "REUSE_SOURCE_IDENTITY"
    assert matrix.get("contract_id") == contract.get("contract_id"), "REUSE_SOURCE_IDENTITY"
    assert str(matrix.get("contract_sha256", "")).upper() == contract_hash, "REUSE_SOURCE_IDENTITY"
    assert not RULES.validate_contract(contract) and not RULES.validate_matrix(matrix, contract, contract_hash), "REUSE_SOURCE_INVALID"
    return {"contract": contract, "matrix": matrix, "contract_sha256": contract_hash,
            "matrix_sha256": matrix_hash, "bundle_directory": package}


def _find_reuse_source(matrix_hash):
    """按矩阵哈希定位唯一的正式来源包；哈希不匹配不能靠目录名冒充。"""
    matches = []
    for package in sorted((ROOT / "docs/acceptance-contracts").glob("P4-4-v*")):
        matrix_path = package / "final-evidence-matrix.json"
        if package.is_dir() and matrix_path.is_file() and \
                hashlib.sha256(b.guard(matrix_path).read_bytes()).hexdigest().upper() == matrix_hash:
            matches.append(package)
    assert len(matches) == 1, "REUSE_SOURCE_MISSING" if not matches else "REUSE_SOURCE_DUPLICATE"
    return matches[0]


def reuse_sources():
    """返回紧邻前驱之前的完整复用谱系；从真实 previous 链回溯并逐级核验。"""
    parent = _load_reuse_source(PARENT, PARENT_MATRIX_HASH)
    assert parent["contract_sha256"] == PARENT_HASH, "REUSE_SOURCE_HASH"
    for file in (PARENT_CONTRACT, PARENT_MATRIX):
        assert b.git_bytes("show", PREDECESSOR_BUNDLE + ":" + file.relative_to(ROOT).as_posix()) == file.read_bytes(), "PARENT_GIT_BYTES"
    sources, seen, current = {}, {parent["matrix_sha256"]}, parent
    while any(item.get("execution") == "REUSED" for item in current["matrix"]["criteria"]):
        required = str(current["matrix"].get("previous_matrix_sha256", "")).upper()
        assert required and required not in seen, "REUSE_SOURCE_CYCLE"
        seen.add(required)
        source = _load_reuse_source(_find_reuse_source(required), required)
        assert not RULES.validate_contract_lineage(current["contract"], source["contract"],
                                                   current["contract_sha256"], source["contract_sha256"]), "REUSE_SOURCE_LINEAGE"
        assert not RULES.validate_matrix_lineage(current["matrix"], source["matrix"],
                                                 current["matrix_sha256"], source["matrix_sha256"]), "REUSE_SOURCE_LINEAGE"
        for file in (source["bundle_directory"].with_suffix(".contract.json"),
                     source["bundle_directory"] / "final-evidence-matrix.json"):
            assert b.git_bytes("show", PREDECESSOR_BUNDLE + ":" + file.relative_to(ROOT).as_posix()) == file.read_bytes(), "REUSE_SOURCE_GIT_BYTES"
        sources[required] = source
        current = source
    assert (current["contract_sha256"], current["matrix_sha256"]) == (SOURCE_HASH, SOURCE_MATRIX_HASH), "REUSE_SOURCE_ORIGIN"
    assert sources[SOURCE_MATRIX_HASH]["contract"]["freeze_commit"] == SOURCE_COMMIT, "REUSE_SOURCE_ORIGIN"
    assert sources[SOURCE_MATRIX_HASH]["matrix"]["overall_result"] == "EVIDENCE_GAP", "REUSE_SOURCE_ORIGIN"
    assert set(sources) == {hashlib.sha256(b.guard(matrix).read_bytes()).hexdigest().upper()
                            for _, matrix in reuse_source_paths()}, "REUSE_SOURCE_SET"
    return sources


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
        "predecessor_contract": {**ref(PARENT_CONTRACT, PARENT_CONTRACT.parent), "path": RECOVERY + "/" + previous_stem() + ".contract.json"},
        "predecessor_matrix": {**ref(PARENT_MATRIX, PARENT), "path": RECOVERY + "/" + previous_stem() + ".final-evidence-matrix.json"},
        "private_verify_failure": by_name["recovery/private-verify-failure.json"], "offline_identity": dict(OFFLINE_IDENTITY),
        "after_complete": complete, "after_failed": failed, "files": references}
    for key, name in {"target": "target.json", "before": "snapshots/before.json", "negatives": "negatives.json",
                      "run_a": "run-a/final.json", "run_b": "run-b/final.json", "reviewer_attestation": "reviewer-attestation.json"}.items():
        descriptor[key] = by_name[name]
    if PACKAGE_SPEC:
        descriptor["package_spec"] = copy.deepcopy(PACKAGE_SPEC)
    plan = [(file, DATA / file.relative_to(base)) for file in files]
    plan += [(PARENT_CONTRACT, DATA / descriptor["predecessor_contract"]["path"]),
             (PARENT_MATRIX, DATA / descriptor["predecessor_matrix"]["path"])]
    return plan, descriptor


def _document(ctx, file):
    reference = b.ref(b.guard(file), ctx.base)
    return reference, ctx.document(reference)


def _optional_document(ctx, file):
    file = b.guard(file)
    return _document(ctx, file) if file.exists() else (None, None)


def _origin(route):
    assert isinstance(route, str) and route.startswith("/") and not re.search(r"[\r\n\0]", route), "AFTER_ROUTE"
    if route.startswith("/accounts/"):
        return "https://api.cloudflare.com"
    if route.startswith("/repos/"):
        return "https://api.github.com"
    return "s3"


def _timing(record, finished):
    start, end = INSPECT.timestamp(record["started"]), INSPECT.timestamp(record["ended"])
    assert start >= finished and end >= start, "AFTER_RECORD_TIME"


def _headers(value):
    assert isinstance(value, dict) and all(isinstance(k, str) and isinstance(v, str) for k, v in value.items()), "AFTER_HEADERS"
    assert all(re.fullmatch(r"[a-z0-9-]+", key) for key in value), "AFTER_HEADER_NAME"
    assert not ({"authorization", "cookie", "set-cookie", "proxy-authorization", "x-api-key"} & set(value)), "AFTER_HEADER_SENSITIVE"


def _body(ctx, record):
    wire = ctx.read(record["body"])
    headers = {name.lower(): value for name, value in record.get("response_headers", {}).items()}
    assert len(headers) == len(record.get("response_headers", {})), "AFTER_HEADERS"
    decoded = INSPECT.decode_d1_wire(wire, headers)
    if decoded != wire:
        assert record.get("decoded_body"), "AFTER_DECODED_MISSING"
        assert ctx.read(record["decoded_body"]) == decoded, "AFTER_DECODED_MISMATCH"
    else:
        assert "decoded_body" not in record, "AFTER_DECODED_UNEXPECTED"
    return decoded


def _failure(ctx, directory, label, reference, index, record, finished):
    assert reference["path"] == directory + label + "-request-failure-" + str(index) + ".json", "AFTER_FAILURE_PATH"
    document = ctx.document(reference)
    expected = {"attempt", "ended", "error_code", "final_response_received", "first_information", "informational_count",
                "informational_seen", "method", "path", "received_body_bytes", "schema", "started"}
    if "request" in record:
        expected.add("request")
    assert set(document) == expected and document["schema"] == "p44-request-failure-v1", "AFTER_FAILURE_FIELDS"
    assert document["attempt"] == index and document["method"] == record["method"] and document["path"] == record["path"]
    if "request" in record:
        assert document["request"] == record["request"], "AFTER_FAILURE_REQUEST"
    assert re.fullmatch(r"[A-Z][A-Z0-9_]+", document["error_code"]), "AFTER_FAILURE_CODE"
    assert document["final_response_received"] is False, "AFTER_FAILURE_RESPONSE"
    assert INSPECT.integer(document["received_body_bytes"]) and INSPECT.integer(document["informational_count"])
    assert isinstance(document["informational_seen"], bool) and document["informational_seen"] == (document["informational_count"] > 0)
    if document["informational_seen"]:
        assert isinstance(document["first_information"], dict) and INSPECT.integer(document["first_information"].get("status"))
    else:
        assert document["first_information"] is None
    _timing(document, finished)
    return document


def _private_bytes(name):
    return b.guard(ROOT / name).read_bytes()


def _partial_body(ctx, directory, label, record):
    assert INSPECT.integer(record.get("status"), 100) and record["status"] < 600, "AFTER_STATUS"
    assert "decoded_body" not in record, "AFTER_PARTIAL_DECODED"
    assert isinstance(record.get("partial_body_sha256"), str) and re.fullmatch(r"[0-9a-f]{64}", record["partial_body_sha256"]), "AFTER_PARTIAL_DIGEST"
    size = record.get("partial_body_size_bytes")
    assert INSPECT.integer(size) and size <= 16 * 1024 * 1024, "AFTER_PARTIAL_SIZE"
    raw = None
    if "body" in record:
        assert record["body"]["path"] == directory + label + ".partial.body", "AFTER_PARTIAL_PATH"
        assert "response_headers" in record and "private_wire" not in record and "partial_projection" not in record, "AFTER_PARTIAL_STORAGE"
        if record["method"] == "POST":
            assert record["response_headers"].get("content-encoding", "identity").strip().lower() == "identity", "AFTER_PRIVATE_ENCODING"
        raw = ctx.read(record["body"])
    elif "private_wire" in record:
        assert record["method"] == "POST" and record.get("request_headers", {}).get("accept-encoding") == "gzip", "AFTER_PRIVATE_ENCODING"
        if "response_headers" in record:
            encoding = record["response_headers"].get("content-encoding")
            assert isinstance(encoding, str) and encoding.strip() and encoding.strip().lower() != "identity", "AFTER_PRIVATE_ENCODING"
        assert record.get("partial_projection") == "Encoded failure retained privately; public hash/length/location only", "AFTER_PARTIAL_PROJECTION"
        reference = record["private_wire"]
        assert isinstance(reference, dict) and set(reference) == {"path", "size_bytes", "sha256"}, "AFTER_PRIVATE_REFERENCE"
        assert INSPECT.integer(reference["size_bytes"]), "AFTER_PRIVATE_REFERENCE"
        private_root = PRIVATE_WIRE
        if PACKAGE_SPEC:
            descriptor = read(DATA / FIXTURE)
            originals = {item["path"]: item for item in descriptor["files"]}
            original_name = directory + label + ".http.json"
            if original_name in originals:
                assert ctx.document(originals[original_name]) == record, "AFTER_PRIVATE_ORIGINAL"
                match = re.match(r"^\.cache/p44/private/capture-failures/P4-4-v[0-9]+/", reference["path"])
                assert match, "AFTER_PRIVATE_PATH"
                private_root = match[0]
        assert reference["path"] == private_root + directory + label + ".wire.body", "AFTER_PRIVATE_PATH"
        assert reference["size_bytes"] == size and reference["sha256"] == record["partial_body_sha256"], "AFTER_PRIVATE_REFERENCE"
        raw = _private_bytes(reference["path"])
    else:
        assert record.get("partial_projection") == "Known sensitive value: original hash/length only, no public plaintext copy", "AFTER_PARTIAL_PROJECTION"
    if raw is not None:
        assert len(raw) == size, "AFTER_PARTIAL_SIZE"
        assert b.sha(raw) == record["partial_body_sha256"], "AFTER_PARTIAL_DIGEST"
    if "wire_received_size_bytes" in record:
        assert INSPECT.integer(record["wire_received_size_bytes"]) and record["wire_received_size_bytes"] >= size, "AFTER_PARTIAL_RECEIVED_SIZE"


def _after_source(ctx, directory, number, finished, admin, allow_attempt_dirs=False):
    directory = b.guard(directory)
    relative = directory.relative_to(ctx.base).as_posix() + "/"
    entries = sorted(directory.iterdir(), key=lambda item: item.name)
    files = [item.name for item in entries if item.is_file()]
    dirs = [item.name for item in entries if item.is_dir()]
    if allow_attempt_dirs:
        assert all(re.fullmatch(r"attempt-(?:[2-9]|[1-9][0-9]+)", name) for name in dirs), "AFTER_UNKNOWN_DIRECTORY"
    else:
        assert not dirs, "AFTER_UNKNOWN_DIRECTORY"
    names, expected = set(files), set()
    complete, failures, record_ends, record_refs, seen = {}, {}, [], [], set()
    if admin:
        expected.add("attempt-reservation.json")
    result_ref, result = _optional_document(ctx, directory / "attempt-result.json")
    if result_ref:
        expected.add("attempt-result.json")
    http_names = sorted(name for name in files if name.endswith(".http.json"))
    for name in http_names:
        label = name[:-len(".http.json")]
        assert label not in seen, "AFTER_DUPLICATE_PREFIX"
        seen.add(label)
        record_ref, record = _document(ctx, directory / name)
        record_refs.append(record_ref)
        expected.add(name)
        assert isinstance(record, dict) and record.get("method") in {"POST", "GET"}, "AFTER_RECORD"
        assert isinstance(record.get("completed"), bool) and INSPECT.integer(record.get("request_attempts"), 1) \
            and record["request_attempts"] in {1, 2}, "AFTER_RECORD"
        assert isinstance(record.get("request_failures"), list), "AFTER_RECORD"
        assert isinstance(record.get("path"), str) and _origin(record["path"]), "AFTER_RECORD"
        _timing(record, finished)
        reservation_ref, reservation = _document(ctx, directory / (label + "-reservation.json"))
        expected.add(label + "-reservation.json")
        wanted = {"method": record["method"], "origin": _origin(record["path"]), "path": record["path"],
                  "started": record["started"], "note": "Reserved before request; a lost response is not permission to replay a mutation."}
        if "request" in record:
            wanted["request"] = record["request"]
        if "request_headers" in record:
            wanted["request_headers"] = record["request_headers"]
        assert reservation == wanted, "AFTER_RESERVATION"
        if "request_headers" in record:
            assert record["request_headers"] == {"accept-encoding": "gzip"}, "AFTER_REQUEST_HEADERS"
        if record.get("response_headers") is not None:
            _headers(record["response_headers"])
        checked = []
        for index, reference in enumerate(record["request_failures"], 1):
            document = _failure(ctx, relative, label, reference, index, record, finished)
            if index == 1 and record["request_attempts"] == 2:
                assert document["error_code"] == "ECONNRESET" and document["final_response_received"] is False
                assert document["informational_seen"] is False and document["received_body_bytes"] == 0
            checked.append(document)
            expected.add(label + "-request-failure-" + str(index) + ".json")
        if record.get("request") is not None:
            request_ref = record["request"]
            assert isinstance(request_ref, dict) and set(request_ref) == {"path", "size_bytes", "sha256"}, "AFTER_REQUEST"
            assert request_ref["path"] == relative + label + ".request.json", "AFTER_REQUEST_PATH"
            request = INSPECT.json_bytes(ctx.read(request_ref))
            assert isinstance(request, dict) and isinstance(request.get("sql"), str) and set(request) == {"sql"}, "AFTER_SQL"
            expected.add(label + ".request.json")
        if record.get("body") is not None:
            assert "response_headers" in record, "AFTER_BODY_HEADERS"
            if record["completed"]:
                assert record["body"]["path"] == relative + label + ".body", "AFTER_BODY_PATH"
                _body(ctx, record)
            expected.add(label + (".body" if record["completed"] else ".partial.body"))
        if record.get("decoded_body") is not None:
            assert "body" in record, "AFTER_DECODED_BODY"
            expected.add(label + ".decoded.body")
        if record.get("retry_reservation") is not None:
            retry_ref, retry = _document(ctx, directory / (label + "-retry-2-reservation.json"))
            expected.add(label + "-retry-2-reservation.json")
            retry_keys = {"attempt", "delay_ms", "first_failure", "method", "path", "schema", "started"}
            if "request" in record:
                retry_keys.add("request")
            assert set(retry) == retry_keys and retry.get("schema") == "p44-request-retry-reservation-v1" and retry.get("attempt") == 2
            assert INSPECT.timestamp(checked[0]["ended"]) <= INSPECT.timestamp(retry["started"]) <= INSPECT.timestamp(record["ended"]), "AFTER_RETRY_TIME"
            assert retry.get("delay_ms") == 500
            assert retry.get("first_failure") == record["request_failures"][0]
            assert retry.get("method") == record["method"] and retry.get("path") == record["path"]
            if "request" in record:
                assert retry.get("request") == record["request"]
            assert INSPECT.timestamp(retry["started"]) >= INSPECT.timestamp(checked[0]["started"])
        if record["completed"]:
            assert not PARTIAL_FIELDS.intersection(record), "AFTER_PARTIAL_AS_COMPLETE"
            assert len(checked) == record["request_attempts"] - 1 and "error_code" not in record, "AFTER_RECORD"
            assert INSPECT.integer(record.get("status"), 100) and record["status"] < 600, "AFTER_STATUS"
            assert record.get("body"), "AFTER_BODY"
            if record["request_attempts"] == 1:
                assert reservation["started"] == record["started"], "AFTER_RESERVATION_TIME"
            else:
                assert "retry_reservation" in record, "AFTER_RETRY_MISSING"
            if record["method"] == "POST":
                assert "request" in record and "request_headers" in record, "AFTER_REQUEST"
            else:
                assert "request" not in record, "AFTER_REQUEST_UNEXPECTED"
            complete[label] = {"label": label, "record": record, "record_ref": record_ref, "reservation": reservation,
                               "reservation_ref": reservation_ref, "source": "c4" if number == 0 else "attempt-" + str(number),
                               "attempt": number}
            if record["request_failures"]:
                failures[label] = [{"label": label, "kind": "retry-prior", "ref": reference, "doc": document,
                                    "source": complete[label]["source"], "attempt": number, "index": index}
                                   for index, (reference, document) in enumerate(zip(record["request_failures"], checked), 1)]
        else:
            received = "status" in record
            assert len(checked) == record["request_attempts"] - int(received), "AFTER_ATTEMPTS"
            assert re.fullmatch(r"[A-Z][A-Z0-9_]+", str(record.get("error_code"))), "AFTER_FAILURE_CODE"
            if received:
                _partial_body(ctx, relative, label, record)
            else:
                assert record["error_code"] == checked[-1]["error_code"], "AFTER_FAILURE_CODE"
                assert not (PARTIAL_FIELDS | {"body", "decoded_body", "response_headers"}).intersection(record), "AFTER_PRE_RESPONSE_BODY"
            assert ("retry_reservation" in record) == (record["request_attempts"] == 2), "AFTER_RETRY_UNEXPECTED"
            if record["request_attempts"] == 1:
                assert reservation["started"] == record["started"], "AFTER_RESERVATION_TIME"
            failures[label] = [{"label": label, "kind": "record", "ref": record_ref, "record": record,
                                "source": "c4" if number == 0 else "attempt-" + str(number), "attempt": number}]
        record_ends.append(record["ended"])
    orphans = sorted(names - expected)
    missing = sorted(expected - names)
    assert not orphans, "AFTER_ORPHAN_FILE:" + ",".join(orphans)
    assert not missing, "AFTER_MISSING_FILE:" + ",".join(missing)
    attempt = {"number": number, "dir": directory, "complete": complete, "failures": failures,
               "records": http_names, "record_refs": record_refs, "result_ref": result_ref, "result": result,
               "ended": max(record_ends) if record_ends else None}
    if admin:
        reservation_ref, reservation = _document(ctx, directory / "attempt-reservation.json")
        attempt["reservation_ref"], attempt["reservation"] = reservation_ref, reservation
        attempt["ended"] = max([reservation["started"], *record_ends, *([result["ended"]] if result else [])])
    else:
        attempt["reservation_ref"], attempt["reservation"] = None, None
    return attempt


def _failure_entries(attempt):
    return [{"label": label, **{key: entry[key] for key in ("source", "attempt", "kind")}, "record": entry["ref"]}
            for label, entries in attempt["failures"].items() for entry in entries]


def _records(complete):
    return [{"label": label, "record": entry["record_ref"], "reservation": entry["reservation_ref"]}
            for label, entry in complete.items()]


def _attempt_summary(attempt):
    value = {"attempt": attempt["number"], "reservation": attempt["reservation_ref"],
             "reservation_sha256": attempt["reservation_ref"]["sha256"], "complete": len(attempt["complete"]),
             "failures": sum(len(entries) for entries in attempt["failures"].values()),
             "complete_labels": sorted(attempt["complete"]), "failure_labels": sorted(attempt["failures"]),
             "ended": attempt["ended"]}
    if attempt["result_ref"]:
        value["result"], value["result_sha256"] = attempt["result_ref"], attempt["result_ref"]["sha256"]
    return value


def _counter(values):
    return sorted(INSPECT.canonical(value) for value in values)


def _walk_records(value):
    if isinstance(value, dict):
        if {"method", "path", "started", "ended", "body"} <= set(value):
            yield value
        else:
            for item in value.values():
                yield from _walk_records(item)
    elif isinstance(value, list):
        for item in value:
            yield from _walk_records(item)


def _plan_records(ctx, after):
    records = {}
    def add(label, record, kind="github", role=None):
        assert label not in records, "AFTER_DUPLICATE_LABEL"
        records[label] = {"record": record, "kind": kind, "role": role}
    for role in INSPECT.RESOURCES:
        schema = after["databases"][role]["schema"]
        add(role + "-schema", schema, "d1", role)
        tables = after["databases"][role]["tables"]
        rows = INSPECT.d1_rows(ctx, schema, INSPECT.RESOURCES[role][0], INSPECT.SCHEMA_SQL)
        for row in rows:
            name = row["name"]
            if row["type"] != "table" or name.startswith(("sqlite_", "_cf_")):
                continue
            table = tables[name]
            add(role + "-" + name + "-count", table["count"], "d1", role)
            for index, record in enumerate(table["pages"]):
                add(role + "-" + name + "-rows8-" + str(index * 8), record, "d1", role)
        for index, record in enumerate(after["buckets"][role]):
            add(role + "-r2-" + str(index + 1), record, "s3", role)
    for index, record in enumerate(after["github"]["releases"]):
        add("releases-" + str(index + 1), record)
    add("target-tag", after["target_tag"]["ref"])
    for index, record in enumerate(after["target_tag"]["peeled"]):
        add("target-tag-" + str(index), record)
    releases = INSPECT.github_pages(ctx, after["github"]["releases"], REPO_API + "/releases")
    for release in releases:
        identity = str(release["id"])
        for index, record in enumerate(after["github"]["assets"][identity]):
            add("assets-" + identity + "-" + str(index + 1), record)
    for role in ("production", "rehearsal"):
        configuration = after["protected_configuration"][role]
        add("config-" + role + "-environment", configuration["configuration"])
        for key, stem in (("variables", "variables"), ("secrets", "secrets"), ("branches", "branches")):
            for index, record in enumerate(configuration[key]):
                add("config-" + role + "-" + stem + "-" + str(index + 1), record)
    add("config-repository-gate", after["protected_configuration"]["repository_gate"])
    add("config-tool-ref", after["protected_configuration"]["tool_ref"])
    return records


def _configuration_pages(ctx, records, route, field):
    assert isinstance(records, list) and 1 <= len(records) <= 30, "AFTER_CONFIGURATION_PAGES"
    items, totals = [], set()
    for number, record in enumerate(records, 1):
        INSPECT.page_path(record["path"], route, number)
        body = INSPECT.json_bytes(ctx.response(record, "GET", record["path"]))
        assert isinstance(body, dict) and INSPECT.integer(body.get("total_count")), "AFTER_CONFIGURATION_COUNT"
        batch = body.get(field)
        assert isinstance(batch, list) and len(batch) <= 100 and all(isinstance(row, dict) for row in batch), "AFTER_CONFIGURATION_PAGE"
        assert INSPECT.next_page(record, route, number) == (number < len(records)), "AFTER_CONFIGURATION_INCOMPLETE"
        totals.add(body["total_count"])
        items.extend(batch)
    assert totals == {len(items)}, "AFTER_CONFIGURATION_COUNT"
    return items


def _verify_configuration(ctx, after, before):
    for role in ("production", "rehearsal"):
        item, original = after[role], before[role]
        route = REPO_API + "/environments/firmware-" + role
        environment = INSPECT.json_bytes(ctx.response(item["configuration"], "GET", route))
        prior = INSPECT.json_bytes(ctx.response(original["configuration"], "GET", route))
        assert environment["name"] == "firmware-" + role
        for key in ("id", "name", "protection_rules", "deployment_branch_policy", "can_admins_bypass"):
            assert environment.get(key) == prior.get(key), "AFTER_CONFIGURATION_ENVIRONMENT"
        rows = {}
        for key, endpoint, field in (("variables", "variables", "variables"), ("secrets", "secrets", "secrets"),
                                     ("branches", "deployment-branch-policies", "branch_policies")):
            rows[key] = _configuration_pages(ctx, item[key], route + "/" + endpoint, field)
        values = {row["name"]: row["value"] for row in rows["variables"]}
        assert len(values) == len(rows["variables"]), "AFTER_CONFIGURATION_DUPLICATE_VARIABLE"
        assert values == item["values"] == original["values"], "AFTER_CONFIGURATION_VALUES"
        assert values["OTA_BOOT_CHAIN_READY"] == "false"
        assert rows["branches"] == item["rules"] == original["rules"], "AFTER_CONFIGURATION_RULES"
        assert [rule["name"] for rule in item["rules"] if rule["type"] == "branch"]
        if role == "production":
            assert [(rule["name"], rule["type"]) for rule in item["rules"]] == [("main", "branch")]
        else:
            assert BRANCH in [rule["name"] for rule in item["rules"]]
        previous_secrets = _configuration_pages(ctx, original["secrets"], route + "/secrets", "secrets")
        identity = lambda entries: sorted(tuple(row[key] for key in ("name", "created_at", "updated_at")) for row in entries)
        assert identity(rows["secrets"]) == identity(previous_secrets), "AFTER_CONFIGURATION_SECRETS"
        names = {row["name"] for row in rows["secrets"]}
        assert len(names) == len(rows["secrets"]), "AFTER_CONFIGURATION_DUPLICATE_SECRET"
        prefix = "" if role == "production" else "FIRMWARE_REHEARSAL_"
        for name in ("CLOUDFLARE_ACCOUNT_ID", "OTA_AES_KEY", "TRACE_DEPLOY_TOKEN", "TRACE_UPDATE_SERVICE_URL",
                     "TRACE_R2_ACCESS_KEY_ID", "TRACE_R2_SECRET_ACCESS_KEY"):
            assert prefix + name in names, "AFTER_CONFIGURATION_SECRET"


def verify_after_recovery(contract, descriptor, ctx):
    after_result = read(DATA / RECOVERY / "after-result.json")
    required = {"schema", "ok", "snapshot", "reused_complete", "new_reads", "first_new", "first_missing", "attempts",
                "product_commit", "tool_commit", "source_commit", "source_bundle_commit", "freeze_commit",
                "predecessor_commit", "predecessor_bundle_commit", "predecessor_index_commit"}
    assert set(after_result) == required and after_result["schema"] == RECOVERY_RESULT_SCHEMA and after_result["ok"] is True, "AFTER_RESULT"
    assert INSPECT.integer(after_result["reused_complete"]) and INSPECT.integer(after_result["new_reads"]), "AFTER_RESULT_COUNTS"
    assert all(after_result[key] == value for key, value in lineage_fields().items()), "AFTER_RESULT_LINEAGE"
    assert after_result["freeze_commit"] == contract["freeze_commit"] and after_result["product_commit"] == SOURCE_COMMIT
    assert after_result["tool_commit"] == contract["freeze_commit"], "CAPTURE_SOURCE_BINDING"
    assert after_result["first_missing"] is None
    after_ref = after_result["snapshot"]
    assert after_ref == ref(DATA / "snapshots/after.json"), "AFTER_RESULT_SNAPSHOT"
    after = ctx.document(after_ref)
    recovery = after["recovery"]
    assert set(recovery) == RECOVERY_KEYS, "AFTER_RECOVERY_FIELDS"
    assert all(recovery[key] == value for key, value in lineage_fields().items()), "AFTER_RECOVERY_LINEAGE"
    assert recovery["tool_commit"] == after_result["tool_commit"]
    assert recovery["input"] == ref(DATA / FIXTURE), "AFTER_RECOVERY_INPUT"
    assert recovery["complete_originals"] == descriptor["after_complete"], "AFTER_RECOVERY_ORIGINALS"
    assert recovery["failed_originals"] == descriptor["after_failed"], "AFTER_RECOVERY_ORIGINALS"
    assert recovery["private_verify_failure"] == descriptor["private_verify_failure"]
    finished = INSPECT.timestamp(ctx.document(descriptor["run_b"])["run"]["updated_at"])

    old = _after_source(ctx, DATA / "snapshots/after", 0, finished, False)
    expected_c4 = {item["path"].removeprefix("snapshots/after/") for item in descriptor["files"]
                   if item["path"].startswith("snapshots/after/")}
    assert {item.name for item in b.guard(DATA / "snapshots/after").iterdir() if item.is_file()} == expected_c4, "AFTER_C4_FILES"
    assert sorted(entry["record_ref"]["path"] for entry in old["complete"].values()) == \
        sorted(item["path"] for item in descriptor["after_complete"]), "AFTER_C4_COMPLETE"
    assert sorted(entry["record"]["path"] for entry in _failure_entries(old) if entry["kind"] == "record") == \
        sorted(item["path"] for item in descriptor["after_failed"]), "AFTER_C4_FAILED"

    tail = b.guard(DATA / TAIL)
    legacy_ref, legacy = _document(ctx, DATA / LEGACY_RESERVATION)
    c6 = _after_source(ctx, tail, 1, finished, False, True)
    c6["reservation_ref"], c6["reservation"] = legacy_ref, legacy
    c6["ended"] = max(legacy["started"], c6["ended"] or legacy["started"])
    attempts = [c6]
    numbers = sorted(int(item.name.removeprefix("attempt-")) for item in tail.iterdir() if item.is_dir())
    assert numbers == list(range(2, 2 + len(numbers))), "AFTER_ATTEMPT_GAP"
    for number in numbers:
        attempt = _after_source(ctx, tail / ("attempt-" + str(number)), number, finished, True)
        assert attempt["reservation"] is not None and attempt["result"] is not None, "AFTER_ATTEMPT_RESULT_MISSING"
        attempts.append(attempt)

    def validate_result(attempt):
        value = attempt["result"]
        assert isinstance(value.get("ok"), bool), "AFTER_ATTEMPT_RESULT_OK"
        assert set(value) == RESULT_KEYS | ({"error_code"} if not value.get("ok") else set()), "AFTER_ATTEMPT_RESULT_FIELDS"
        assert value["schema"] == ATTEMPT_RESULT_SCHEMA and value["attempt"] == attempt["number"]
        assert value["reservation"] == attempt["reservation_ref"] and value["reservation_sha256"] == attempt["reservation_ref"]["sha256"]
        assert value["started"] == attempt["reservation"]["started"] and value["ok"] == ("error_code" not in value)
        assert sorted(value["complete_labels"]) == sorted(attempt["complete"]), "AFTER_ATTEMPT_RESULT_COMPLETE"
        assert sorted(value["failure_labels"]) == sorted(attempt["failures"]), "AFTER_ATTEMPT_RESULT_FAILURES"
        assert _counter(value["new_reads"]) == _counter(attempt["record_refs"]), "AFTER_ATTEMPT_RESULT_READS"
        failure_refs = []
        for entries in attempt["failures"].values():
            for entry in entries:
                if entry["kind"] == "retry-prior":
                    failure_refs.append(entry["ref"])
                else:
                    failure_refs.extend(entry["record"]["request_failures"])
                    if "status" in entry["record"]:
                        failure_refs.append(entry["ref"])
        assert _counter(value["failures"]) == _counter(failure_refs), "AFTER_ATTEMPT_RESULT_FAILURE_REFS"
        terminal = [entry for entries in attempt["failures"].values() for entry in entries if entry["kind"] == "record"]
        assert not value["ok"] or not terminal, "AFTER_ATTEMPT_RESULT_OK"
        if not value["ok"]:
            assert re.fullmatch(r"[A-Z][A-Z0-9_]*", value["error_code"]), "AFTER_ATTEMPT_RESULT_CODE"
            assert len(terminal) <= 1, "AFTER_ATTEMPT_RESULT_CODE"
            if terminal:
                assert value["error_code"] == terminal[0]["record"]["error_code"], "AFTER_ATTEMPT_RESULT_CODE"
        ended = INSPECT.timestamp(value["ended"])
        assert ended >= INSPECT.timestamp(value["started"]), "AFTER_ATTEMPT_RESULT_TIME"
        assert all(ended >= INSPECT.timestamp(entry["record"]["ended"]) for entry in attempt["complete"].values()), "AFTER_ATTEMPT_RESULT_TIME"
        assert all(ended >= INSPECT.timestamp(entry["record"]["ended"]) for entry in terminal), "AFTER_ATTEMPT_RESULT_TIME"

    planned = _plan_records(ctx, after)
    order = list(planned)
    all_complete = {}
    for source in [old, *attempts]:
        assert not (set(all_complete) & set(source["complete"])), "AFTER_DUPLICATE_COMPLETE"
        all_complete.update(source["complete"])
    assert _counter(order) == _counter(all_complete), "AFTER_LABEL_COVERAGE"
    assert all(planned[label]["record"] == entry["record"] for label, entry in all_complete.items()), "AFTER_LABEL_RECORD_BINDING"
    c4_first = next(label for label in order if label not in old["complete"])
    assert sorted(old["complete"]) == sorted(order[:len(old["complete"])]), "AFTER_C4_PREFIX"
    assert len(legacy) == len(LEGACY_KEYS) and set(legacy) == LEGACY_KEYS, "AFTER_ATTEMPT_FIELDS"
    assert legacy["product_commit"] == SOURCE_COMMIT and legacy["source_bundle_commit"] == SOURCE_BUNDLE
    assert tuple(legacy[key] for key in ("predecessor_commit", "predecessor_bundle_commit", "predecessor_index_commit")) == LEGACY_PREDECESSOR
    assert legacy["tool_commit"] == C6_TOOL, "AFTER_ATTEMPT_TOOL"
    assert legacy["old_complete"] == len(old["complete"]) and legacy["old_failed"] == len(_failure_entries(old))
    assert legacy["first_missing"] == c4_first, "AFTER_ATTEMPT_FIRST"
    assert INSPECT.timestamp(legacy["started"]) >= finished, "AFTER_ATTEMPT_TIME"
    assert all(INSPECT.timestamp(entry["record"]["started"]) >= INSPECT.timestamp(legacy["started"])
               for entry in c6["complete"].values()), "AFTER_ATTEMPT_TIME"

    prior_complete = dict(old["complete"])
    prior_failures = _failure_entries(old)
    previous, previous_end = [], finished
    for attempt in attempts:
        reservation = attempt["reservation"]
        assert isinstance(reservation, dict), "AFTER_ATTEMPT_RESERVATION"
        start = INSPECT.timestamp(reservation["started"])
        assert start >= previous_end, "AFTER_ATTEMPT_TIME"
        if attempt["number"] == 1:
            assert len(reservation) == len(LEGACY_KEYS) and set(reservation) == LEGACY_KEYS
        else:
            assert set(reservation) == RESUME_KEYS and reservation["schema"] == RESUME_SCHEMA, "AFTER_ATTEMPT_FIELDS"
            assert reservation["attempt"] == attempt["number"] and reservation["product_commit"] == SOURCE_COMMIT
            assert reservation["source_bundle_commit"] == SOURCE_BUNDLE
            originals = {item["path"]: item for item in descriptor["files"]}
            if PACKAGE_SPEC and attempt["reservation_ref"]["path"] in originals:
                assert attempt["reservation_ref"] == originals[attempt["reservation_ref"]["path"]]
                ctx.read(attempt["reservation_ref"])
            else:
                assert reservation["predecessor_commit"] == PREDECESSOR_COMMIT
                assert reservation["predecessor_bundle_commit"] == PREDECESSOR_BUNDLE and reservation["predecessor_index_commit"] == PREDECESSOR_INDEX
            assert re.fullmatch(r"[0-9a-f]{40}", reservation["tool_commit"]) and re.fullmatch(r"[0-9a-f]{40}", reservation["head"])
            assert re.fullmatch(r"[0-9a-f]{64}", reservation["tool_sha256"])
            b.git("merge-base", "--is-ancestor", reservation["tool_commit"], "HEAD")
            b.git("merge-base", "--is-ancestor", reservation["head"], "HEAD")
            assert b.sha(b.git_bytes("show", reservation["tool_commit"] + ":" + NODE)) == reservation["tool_sha256"], "AFTER_ATTEMPT_TOOL"
            assert reservation["reused_complete"] == len(prior_complete), "AFTER_ATTEMPT_REUSED"
            assert _counter(reservation["reused_failures"]) == _counter(prior_failures), "AFTER_ATTEMPT_FAILURES"
            assert _counter(reservation["reused_records"]) == _counter(_records(prior_complete)), "AFTER_ATTEMPT_RECORDS"
            assert reservation["previous_attempts"] == previous, "AFTER_ATTEMPT_PREVIOUS"
            frontier = next((label for label in order if label not in prior_complete), None)
            assert frontier is not None and reservation["first_missing"] == frontier, "AFTER_ATTEMPT_FIRST"
        first = next((label for label in order if label not in prior_complete), None)
        assert first is not None and first == (c4_first if attempt["number"] == 1 else reservation["first_missing"]), "AFTER_ATTEMPT_FRONTIER"
        index = order.index(first)
        segment = order[index:index + len(attempt["complete"])]
        assert len(segment) == len(attempt["complete"]) and sorted(attempt["complete"]) == sorted(segment), "AFTER_ATTEMPT_SEQUENCE"
        terminal = [(label, entries) for label, entries in attempt["failures"].items()
                    if any(entry["kind"] == "record" for entry in entries)]
        assert len(terminal) <= 1, "AFTER_MULTIPLE_TERMINAL_FAILURES"
        if terminal:
            assert terminal[0][0] == order[index + len(attempt["complete"])], "AFTER_FAILURE_POSITION"
        for label, entries in attempt["failures"].items():
            for entry in entries:
                if entry["kind"] == "retry-prior":
                    assert label in attempt["complete"], "AFTER_RETRY_POSITION"
        if attempt["number"] > 1:
            validate_result(attempt)
        for label, entry in attempt["complete"].items():
            assert INSPECT.timestamp(entry["record"]["started"]) >= start, "AFTER_ATTEMPT_TIME"
            prior_complete[label] = entry
        prior_failures.extend(_failure_entries(attempt))
        previous.append(_attempt_summary(attempt))
        previous_end = INSPECT.timestamp(attempt["ended"])
    final = attempts[-1]
    assert final["reservation"]["tool_commit"] == recovery["tool_commit"], "AFTER_ATTEMPT_TOOL"
    if final["result"] is not None:
        assert final["result"]["ok"] is True, "AFTER_ATTEMPT_FAILED"
    else:
        assert final["number"] == 1 and not [entry for entry in prior_failures if entry["kind"] == "record"], "AFTER_ATTEMPT_FAILED"
    assert len(prior_complete) == len(order), "AFTER_INCOMPLETE"
    reused = {label: entry for source in [old, *attempts[:-1]] for label, entry in source["complete"].items()}
    reused_failures = [entry for source in [old, *attempts[:-1]] for entry in _failure_entries(source)]
    assert recovery["reused_complete"] == len(reused), "AFTER_REUSED_COUNT"
    assert _counter(recovery["reused_failures"]) == _counter(reused_failures), "AFTER_REUSED_FAILURES"
    assert _counter(recovery["reused_records"]) == _counter(_records(reused)), "AFTER_REUSED_RECORDS"
    assert recovery["attempts"] == [_attempt_summary(attempt) for attempt in attempts]
    frontier = next((label for label in order if label not in reused), None)
    assert recovery["first_missing"] == frontier, "AFTER_FIRST_MISSING"
    fresh = [final["complete"][label] for label in order if label in final["complete"]]
    expected_reads = [{"label": entry["label"], "record": entry["record_ref"], "kind": planned[entry["label"]]["kind"],
                       "role": planned[entry["label"]]["role"]} for entry in fresh]
    assert recovery["new_reads"] == expected_reads, "AFTER_NEW_READS"
    assert after_result["new_reads"] == len(fresh) and after_result["reused_complete"] == len(reused)
    assert after_result["first_new"] == (fresh[0]["label"] if fresh else None) and after_result["attempts"] == recovery["attempts"]

    with compatible_snapshots():
        INSPECT.read_snapshot(ctx, after)
    assert _counter(_walk_records(after)) == _counter(entry["record"] for entry in all_complete.values()), "AFTER_SNAPSHOT_RECORDS"

    configuration = after["protected_configuration"]
    assert configuration["product_commit"] == SOURCE_COMMIT and configuration["tool_commit"] == recovery["tool_commit"]
    assert configuration["repository_gate"] and configuration["tool_ref"]
    gate = ctx.response(configuration["repository_gate"], "GET", "/repos/Eitan-S-23/E-Track/actions/variables/OTA_BOOT_CHAIN_READY")
    assert INSPECT.json_bytes(gate)["value"] == "false"
    tool_ref = ctx.response(configuration["tool_ref"], "GET", "/repos/Eitan-S-23/E-Track/git/ref/heads/" + BRANCH)
    assert INSPECT.json_bytes(tool_ref)["object"]["sha"] == recovery["tool_commit"], "AFTER_TOOL_REF"
    _verify_configuration(ctx, configuration, ctx.document(descriptor["before"])["protected_configuration"])
    tag = after["target_tag"]["ref"]
    assert tag["completed"] is True and tag["status"] in {200, 404}, "AFTER_TARGET_TAG"
    version = ctx.document(descriptor["target"])["versionName"]
    tag_body = ctx.response(tag, "GET", REPO_API + "/git/ref/tags/mcu-e-track-at32f435-v" + version, tag["status"])
    if tag["status"] == 404:
        assert not after["target_tag"]["peeled"], "AFTER_TARGET_TAG"
    else:
        object_value = INSPECT.json_bytes(tag_body)["object"]
        for record in after["target_tag"]["peeled"]:
            object_value = INSPECT.json_bytes(ctx.response(record, "GET", REPO_API + "/git/tags/" + object_value["sha"]))["object"]
        assert object_value["type"] == "commit" and object_value["sha"] == SOURCE_COMMIT, "AFTER_TARGET_TAG"
    return {"schema": "p44-after-recovery-verification-v1", "ok": True, "c4_complete": len(old["complete"]),
            "c6_complete": len(c6["complete"]), "total_complete": len(prior_complete), "attempts": len(attempts),
            "first_missing": frontier, "new_reads": len(fresh), "tool_commit": recovery["tool_commit"]}


def verify_import(data=None):
    data = DATA if data is None else data
    descriptor = read(data / FIXTURE)
    assert set(descriptor) == DESCRIPTOR_KEYS | ({"package_spec"} if PACKAGE_SPEC else set()) and descriptor["schema"] == "p44-after-recovery-v2", "RECOVERY_SCHEMA"
    if PACKAGE_SPEC:
        assert descriptor["package_spec"] == PACKAGE_SPEC, "PACKAGE_BINDING"
    assert all(descriptor[key] == value for key, value in lineage_fields().items()) and descriptor["source_index_commit"] == SOURCE_INDEX, "RECOVERY_ANCHOR"
    assert descriptor["offline_identity"] == OFFLINE_IDENTITY, "OFFLINE_IDENTITY_SCOPE"
    ctx = INSPECT.Context(ROOT, data / "manifest.json")
    assert descriptor["source_contract"]["path"] == "recovery/c4.contract.json"
    assert descriptor["source_matrix"]["path"] == "recovery/c4.final-evidence-matrix.json"
    assert descriptor["predecessor_contract"]["path"] == RECOVERY + "/" + previous_stem() + ".contract.json"
    assert descriptor["predecessor_matrix"]["path"] == RECOVERY + "/" + previous_stem() + ".final-evidence-matrix.json"
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
        "formal-before": ["python", *common, PYTHON, *package_args(), "verify-existing", "before"],
        "formal-negatives": ["python", *common, PYTHON, *package_args(), "verify-existing", "negatives"],
        "formal-after": ["node", NODE, *package_args(), "after"],
        "formal-assemble-complete": ["node", NODE, *package_args(), "assemble"],
        "formal-approvals": offline("Tools/acceptance/p44/inspect.py", "approvals", "manifest.json", "approvals-result.json"),
        "formal-states": ["python", *common, PYTHON, *package_args(), "states"],
        "formal-privacy": ["python", *common, PYTHON, *package_args(), "privacy"],
    }


def successor(parent, recovery_reference):
    value = copy.deepcopy(parent)
    version = PACKAGE_SPEC["version"] if PACKAGE_SPEC else 6
    value.update(contract_id="P4-4-v" + str(version), version=version, parent_contract_sha256=PARENT_HASH, implementation_ref=SOURCE_COMMIT)
    arguments = command_arguments()
    for command in value["commands"]:
        name = command["id"]
        if name not in EXECUTED:
            continue
        args = arguments[name]
        command["command"] = " ".join(["node", NODE, *package_args(), "run", name, *args])
        command["input_groups"] = sorted(set(command["input_groups"]) | {"validation"})
        command["runner_paths"] = sorted(set(command["runner_paths"]) | {NODE, PYTHON, "Tools/acceptance/p44/capture.cjs",
            "Tools/acceptance/p44/run.cjs", "Tools/acceptance/p44/bundle.py", "Tools/acceptance/p44/inspect.py",
            "Tools/acceptance/validate_bundle.py"} | {part for part in args if part.endswith((".py", ".cjs"))})
        command["description"] = ("C6 after-evidence recovery only; retain C4 product target, actual C5 predecessor and original timestamps. "
            "One invocation, original IDs, no new dispatch/upload/register/approval/device action. ")
        if name == "formal-after":
            command["description"] += ("Reuse the verified complete after prefix without network replay; collect only missing fixed SELECT/list data. "
                "Standard proxyTls.timeout/requestTls.timeout=30000, rejectUnauthorized=true, HTTP total signal<=60s, wire/decoded<=16MiB. "
                "Only original admitted read-only pre-response ECONNRESET retry once; no CONNECT_TIMEOUT/HTTP/body/business retry. "
                "Read protected bucket identity only from the fixed hash-bound historical metadata; verify its size, pointer and ID fingerprint offline. "
                "No token verify request, fallback source or API credential discovery. ID and derived key stay in memory. Wrapper watchdog<=60min.")
        else:
            command["description"] += "Offline original-byte verification/assembly only; wrapper watchdog<=60min; preserve all failures."
        if PACKAGE_SPEC:
            command["description"] = ("Successor after-evidence recovery; actual preceding frozen gap and C4 original PASS remain bound. "
                "No product replay, credential discovery, deployment, gate unlock or device action. "
                "One offline original-byte verification/assembly invocation; watchdog at most 60 minutes; preserve all failures.")
            if name == "formal-after":
                command["description"] = ("At most two separately invoked slots using this identical command. Never auto-continue. "
                    "Slot 2 requires a root-adjudicated continuation artifact binding prior closed nonzero receipt, failed attempt result, "
                    "unchanged source/frontier and concrete repair or state-change basis. All slot receipts/logs remain hash-bound evidence; "
                    "the one completed slot supplies this command result; earlier nonzero exits remain disclosed, not overwritten. "
                    "Only missing reads; pre-response ECONNRESET retry once within the existing 60-second request budget; no other HTTP/body retry. "
                    "Offline identity only, no verify request. Wrapper watchdog at most 60 minutes.")
    for item in value["criteria"]:
        if item["id"] not in REUSED:
            item["input_groups"] = sorted(set(item["input_groups"]) | {"validation"})
            item["external_inputs"] = sorted(set(item["external_inputs"]) | {FIXTURE_ID})
            item["dependency_rationale"] += (" Validation additionally binds the successor adapters and finite invocation admission; predecessor failures and C4 observations are unchanged."
                                              if PACKAGE_SPEC else " Validation additionally binds the C6 offline-identity adapter; C5 failure and C4 observations are unchanged.")
        if item["id"] == "P44-RAW-STATE":
            item["description"] = ("Independently verify the complete C4 before snapshot and five authentication denials offline. "
                "Retain all verified C4 completed after responses at their original timestamps and the connect failure; "
                "retain the C5 private-verify failure without inferring its unrecorded HTTP receive state; "
                "collect only missing fixed SELECT/list data after offline identity checks, then require complete three-resource after evidence. "
                "No replay of successful observations, dispatch, registration, production write, gate unlock or device action.")
    for artifact in value["artifacts"]:
        if artifact["id"] in {"P44-HISTORY-1", "P44-HYGIENE-1"}:
            name = "history" if artifact["id"] == "P44-HISTORY-1" else "privacy"
            artifact["path"] = "evidence/" + RECOVERY + "/" + name + "-result.json"
        if artifact["id"].startswith("P44-RAW-STATE-"):
            artifact["description"] = ("Complete C4 before/negative originals are verified offline; the after snapshot joins the verified unchanged complete originals "
                "with only missing fixed read-only captures. Retain original times, failed attempts and all predecessor bytes.")
    value["external_inputs"].append({"id": FIXTURE_ID, "category": "fixture",
        "description": ("Actual preceding frozen gap, C4 original PASS source, unchanged after prefix and fixed offline identity; no verify request or quota reset."
                        if PACKAGE_SPEC else "C5 predecessor, C4 original PASS source, unchanged after prefix and fixed offline identity; no verify request or quota reset."),
        "fingerprint": "sha256:" + recovery_reference["sha256"], "evidence_path": "evidence/" + FIXTURE,
        "evidence_sha256": recovery_reference["sha256"]})
    return value


def initial_matrix(contract, digest):
    value = b.initial_matrix(contract, digest)
    value["round_id"] = PACKAGE_SPEC["round_id"] if PACKAGE_SPEC else "P44-20261020-06"
    for item in value["criteria"]:
        item["notes"] = ("NOT_RUN: successor offline-identity recovery; actual preceding frozen gap and original C4 PASS remain bound."
                         if PACKAGE_SPEC else "NOT_RUN: C6 offline-identity recovery; actual predecessor C5 and original C4 PASS remain bound.")
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
              "--previous-matrix", PARENT_MATRIX.relative_to(ROOT).as_posix()]
    for contract, matrix in reuse_source_paths():
        common += ["--reuse-source", contract.relative_to(ROOT).as_posix(), matrix.relative_to(ROOT).as_posix()]
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
                 approved_by="Independent Codex root; authorized offline-identity after-evidence recovery only",
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
    if PACKAGE_SPEC:
        expected = successor(parent, ref(DATA / FIXTURE))
        assert contract["commands"] == expected["commands"], "PACKAGE_COMMAND_BINDING"
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
    stem = COMMANDS + "/" + name
    if PACKAGE_SPEC and name == "formal-after":
        receipts = after_receipts(definition, ctx)
        stem = receipts[-1][0]
    value = read(DATA / (stem + ".json"))
    assert value["label"] == name and value["process_closed"] is True and value["signal"] is None and value["exitCode"] == 0, "RECOVERY_COMMAND_FAILED"
    assert Path(value["cwd"]).absolute() == ROOT
    actual = " ".join(["node", NODE, *package_args(), "run", name, value["command"], *value["args"]])
    assert actual == definition["command"] and value["output"]["path"] == stem + ".log", "RECOVERY_RECEIPT_BINDING"
    ctx.read(value["output"])
    return {"id": name, "command": actual, "exit_code": value["exitCode"], "output_evidence": "evidence/" + value["output"]["path"]}


def after_receipts(definition, ctx):
    receipts = []
    contract = read(CONTRACT)
    descriptor = read(DATA / FIXTURE)
    imported = {item["path"] for item in descriptor["files"]}
    attempts = []
    for file in sorted((DATA / TAIL).glob("attempt-*/attempt-reservation.json")):
        if file.relative_to(DATA).as_posix() not in imported:
            attempts.append((ref(file), read(file), ref(file.with_name("attempt-result.json")), read(file.with_name("attempt-result.json"))))
    for slot in range(1, PACKAGE_SPEC["max_after_invocations"] + 1):
        stem = COMMANDS + "/formal-after-invocation-" + str(slot)
        if not (DATA / (stem + ".json")).exists():
            assert not (DATA / (stem + "-reservation.json")).exists(), "AFTER_INVOCATION_OPEN"
            continue
        assert slot == len(receipts) + 1, "AFTER_INVOCATION_GAP"
        receipt = read(DATA / (stem + ".json"))
        reservation = read(DATA / (stem + "-reservation.json"))
        assert receipt["label"] == "formal-after" and receipt["closed"] is True and receipt["process_closed"] is True
        assert receipt["signal"] is None and receipt["spawn_failed"] is False and type(receipt["exitCode"]) is int, "AFTER_INVOCATION_CLOSED"
        assert all(receipt[key] == reservation[key] for key in ("label", "command", "args", "cwd", "started")), "AFTER_INVOCATION_RESERVATION"
        assert Path(receipt["cwd"]).absolute() == ROOT
        actual = " ".join(["node", NODE, *package_args(), "run", "formal-after", receipt["command"], *receipt["args"]])
        assert actual == definition["command"] and receipt["output"]["path"] == stem + ".log", "AFTER_INVOCATION_COMMAND"
        ctx.read(receipt["output"])
        matched = [item for item in attempts if INSPECT.timestamp(receipt["started"]) <= INSPECT.timestamp(item[1]["started"])
                   <= INSPECT.timestamp(item[3]["ended"]) <= INSPECT.timestamp(receipt["ended"])]
        assert len(matched) == 1, "AFTER_INVOCATION_ATTEMPT"
        attempt = matched[0]
        assert attempt[3]["ok"] == (receipt["exitCode"] == 0), "AFTER_INVOCATION_RESULT"
        assert attempt[1]["tool_commit"] == contract["freeze_commit"] and attempt[1]["tool_sha256"] == sha(ROOT / NODE), "AFTER_INVOCATION_SOURCE"
        if slot > 1:
            prior_stem, prior_receipt, prior_attempt = receipts[-1]
            assert prior_receipt["exitCode"] != 0 and prior_attempt[3]["ok"] is False, "AFTER_INVOCATION_REPLAY"
            approval = read(DATA / RECOVERY / ("continuation-" + str(slot) + ".json"))
            assert set(approval) == {"schema", "slot", "prior_receipt", "prior_attempt_result", "tool_commit", "tool_sha256",
                                     "first_missing", "decision", "basis", "approved_by", "approved_at"}, "AFTER_CONTINUATION_FIELDS"
            assert approval["schema"] == "p44-after-continuation-v1" and approval["slot"] == slot
            assert approval["decision"] == "CONTINUE_MISSING_ONLY"
            assert all(isinstance(approval[key], str) and approval[key].strip() for key in ("basis", "approved_by")), "AFTER_CONTINUATION_BASIS"
            assert approval["prior_receipt"] == ref(DATA / (prior_stem + ".json")) and approval["prior_attempt_result"] == prior_attempt[2]
            assert approval["tool_commit"] == contract["freeze_commit"] and approval["tool_sha256"] == sha(ROOT / NODE)
            assert approval["first_missing"] == attempt[1]["first_missing"], "AFTER_CONTINUATION_FRONTIER"
            assert INSPECT.timestamp(prior_receipt["ended"]) <= INSPECT.timestamp(approval["approved_at"]) <= INSPECT.timestamp(receipt["started"])
        receipts.append((stem, receipt, attempt))
    assert receipts and receipts[-1][1]["exitCode"] == 0 and len(attempts) == len(receipts), "AFTER_INVOCATION_INCOMPLETE"
    allowed = {stem + suffix for stem, _, _ in receipts for suffix in (".json", ".log", "-reservation.json")}
    actual = {file.relative_to(DATA).as_posix() for file in (DATA / COMMANDS).glob("formal-after-invocation-*")}
    assert actual == allowed, "AFTER_INVOCATION_FILE_SET"
    return receipts


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
            item.update(result="PASS", observed=True, evidence=evidence,
                        notes="Required original-byte evaluation or missing read-only capture; predecessor failures and C4 business success retained, no replay or gate unlock.")
            if PACKAGE_SPEC and "formal-after" in definition["command_ids"]:
                evidence.remove("evidence/" + COMMANDS + "/formal-after.json")
                for file in sorted((DATA / COMMANDS).glob("formal-after-invocation-*")):
                    evidence.append("evidence/" + file.relative_to(DATA).as_posix())
                for file in sorted((DATA / RECOVERY).glob("continuation-*.json")):
                    evidence.append("evidence/" + file.relative_to(DATA).as_posix())
                item["notes"] = "Finite successor slots; all failed and completed invocation receipts retained. C4 original PASS and actual predecessor gap unchanged."
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
    verification = verify_after_recovery(contract, descriptor, ctx)
    assert len(collected) == verification["total_complete"], "AFTER_COMPLETE_COUNT"
    return verification


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
    parser.add_argument("--package-spec")
    try:
        args = parser.parse_args(argv)
        assert Path.cwd().absolute() == ROOT and sys.flags.optimize == 0 and sys.dont_write_bytecode, "EXECUTION_CONTEXT"
        if args.package_spec:
            configure_package(args.package_spec)
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
