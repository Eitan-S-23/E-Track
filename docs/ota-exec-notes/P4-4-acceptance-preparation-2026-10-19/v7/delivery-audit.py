"""V7 staged-delivery hygiene only; no collection, mutation or formal criterion."""
import argparse
import base64
import hashlib
import importlib.util
import io
import json
import os
from pathlib import Path
import re
import subprocess
import sys
import time
import zipfile

ROOT = Path(__file__).absolute().parents[1]
SPEC = importlib.util.spec_from_file_location("p44_delivery_after", ROOT / "Tools/ota/p44-after-bundle.py")
m = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(m)
b = m.b
PACKAGE = "docs/acceptance-contracts/P4-4-v7/"
ROOT_INDEX_SHA = "2907ee569cb8415877c8c688b3e09b5948a789d6430796eab99ae3ad43f3a3dd"
LOGS = ROOT / ".cache/p44-v7-development/delivery-audit"
COMMON = {"PLAN-OTA-EXEC.md", "docs/ota-exec-notes/P4-4-s3-preacceptance-2026-10-19.md",
          "docs/acceptance-contracts/P4-4-v7.package.json"}
SOURCE = COMMON | {"Tools/ota/p44-after-recovery.cjs", "Tools/ota/p44-after-bundle.py",
                   "tests/ota/test_p44_after_recovery.cjs", "tests/ota/test_p44_after_bundle.py"}
BUNDLE = COMMON | {"docs/acceptance-contracts/P4-4-v7.contract.json"}
PREPARATION = "docs/ota-exec-notes/P4-4-acceptance-preparation-2026-10-19/v7/"
TOKEN = re.compile(rb"(?:gh[posur]_|github_pat_)[A-Za-z0-9_]{20,}")
ZIP_MEMBER_BYTES = 32 * 1024 * 1024
ZIP_TOTAL_BYTES = 256 * 1024 * 1024


def relative(name):
    assert isinstance(name, str) and name and "\\" not in name and ":" not in name, "DELIVERY_PATH"
    assert all(part not in {"", ".", ".."} for part in name.split("/")), "DELIVERY_PATH"
    assert not any(ord(char) < 32 for char in name), "DELIVERY_PATH"
    return name


def allowed(name, mode):
    relative(name)
    assert mode in {"source", "bundle"}, "DELIVERY_MODE"
    return name in (SOURCE if mode == "source" else BUNDLE) or name.startswith(PREPARATION if mode == "source" else PACKAGE)


def git(*args):
    for key in ("GIT_INDEX_FILE", "GIT_DIR", "GIT_WORK_TREE", "GIT_OBJECT_DIRECTORY", "GIT_ALTERNATE_OBJECT_DIRECTORIES",
                "GIT_TRACE", "GIT_TRACE2", "GIT_TRACE2_EVENT", "GIT_TRACE2_PERF"):
        assert not os.environ.get(key), "UNREVIEWED_GIT_OVERRIDE"
    env = dict(os.environ, GIT_NO_LAZY_FETCH="1", GIT_OPTIONAL_LOCKS="0", GIT_TERMINAL_PROMPT="0")
    result = subprocess.run(["git", "--no-optional-locks", "-c", "core.fsmonitor=false", *args],
                            cwd=ROOT, env=env, stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=60)
    assert result.returncode == 0 and len(result.stdout) <= 128 * 1024 * 1024, "GIT_READ_FAILED"
    return result.stdout


def staged_objects(raw):
    result = {}
    for record in raw.split(b"\0"):
        if not record:
            continue
        metadata, name = record.split(b"\t", 1)
        mode, oid, stage = metadata.decode("ascii").split()
        name = relative(name.decode("utf-8"))
        assert stage == "0" and re.fullmatch(r"[0-9a-f]{40}", oid), "INDEX_ENTRY_INVALID"
        assert name not in result, "INDEX_ENTRY_DUPLICATE"
        result[name] = (mode, oid)
    return result


def exact_blob(raw, entry):
    mode, oid = entry
    assert mode in {"100644", "100755"}, "UNREVIEWED_INDEX_MODE"
    assert hashlib.sha1(b"blob " + str(len(raw)).encode("ascii") + b"\0" + raw).hexdigest() == oid, "STAGED_BYTE_DRIFT"


def digest(raw, expected, code):
    assert isinstance(expected, str) and re.fullmatch(r"[0-9a-fA-F]{64}", expected), code
    assert b.sha(raw) == expected.lower(), code


def known_needles():
    needles = set(m.known_needles())
    project = ROOT.parents[1]
    source = project / ".cache/p41-dev-20261015/.cache/cf-firmware-setup-20261015/d1-edit-r2/wrangler.json"
    account = json.loads(b.guard(source, project).read_bytes())["account_id"].encode("utf-8")
    digest(account, "01910e669500c221e2154f608e9f4e856b0a08297026e1ea98f1d18dd8cf9742", "ACCOUNT_IDENTITY")
    needles.update((account, base64.b64encode(account)))
    # Explicit parity with v6 cloudInputs and the later offline-identity sentinel.
    provisioning = b.guard(project / ".cache/p41-dev-20261015/.cache/cf-auth-input/token.txt", project).read_bytes().strip()
    identity = m.offline_identifier().encode("ascii")
    for raw in (provisioning, hashlib.sha256(provisioning).hexdigest().encode("ascii"), identity):
        assert raw and raw in needles and base64.b64encode(raw) in needles, "V6_SENTINEL_MISSING"
    assert all(needles), "EMPTY_SENTINEL"
    return needles


def sensitive(raw, needles):
    return any(needle in raw for needle in needles) or TOKEN.search(raw) is not None


def scan_archive(name, raw, needles):
    failures, members, total = [], 0, 0
    with zipfile.ZipFile(io.BytesIO(raw)) as archive:
        entries = [item for item in archive.infolist() if not item.is_dir()]
        assert len(entries) <= 1024, "ZIP_MEMBER_LIMIT"
        assert sum(item.file_size for item in entries) <= ZIP_TOTAL_BYTES, "ZIP_TOTAL_LIMIT"
        for item in entries:
            assert item.file_size <= ZIP_MEMBER_BYTES and not item.flag_bits & 1, "ZIP_MEMBER_LIMIT"
            with archive.open(item) as stream:
                data = stream.read(ZIP_MEMBER_BYTES + 1)
            assert len(data) == item.file_size and len(data) <= ZIP_MEMBER_BYTES, "ZIP_MEMBER_SIZE"
            total += len(data)
            assert total <= ZIP_TOTAL_BYTES, "ZIP_TOTAL_LIMIT"
            members += 1
            if sensitive(data, needles):
                failures.append(name + "::" + item.filename)
    return members, failures


def audit(mode):
    assert git("rev-parse", "--show-object-format").strip() == b"sha1", "GIT_OBJECT_FORMAT"
    names = [relative(name.decode("utf-8")) for name in git("diff", "--cached", "--name-only", "-z").split(b"\0") if name]
    assert names and len(names) == len(set(names)) and all(allowed(name, mode) for name in names), "UNREVIEWED_DELIVERY_SCOPE"
    staged = staged_objects(git("ls-files", "--stage", "-z"))
    assert set(names) <= set(staged), "STAGED_FILE_MISSING"
    index = b.guard(ROOT.parents[1] / ".git/index", ROOT.parents[1])
    digest(index.read_bytes(), ROOT_INDEX_SHA, "ROOT_INDEX_CHANGED")
    hashes = {}
    if mode == "bundle":
        matrix_name = PACKAGE + "final-evidence-matrix.json"
        assert matrix_name in names, "FINAL_MATRIX_NOT_STAGED"
        matrix_raw = b.guard(ROOT / matrix_name).read_bytes()
        exact_blob(matrix_raw, staged[matrix_name])
        matrix = json.loads(matrix_raw)
        assert matrix["contract_id"] == "P4-4-v7", "FINAL_MATRIX_SCOPE"
        hashes = {PACKAGE + relative(name): value for name, value in matrix["evidence_hashes"].items()}
        assert hashes and set(hashes) <= set(names), "BOUND_EVIDENCE_MISSING"
    needles = known_needles()
    failures, members, checked = [], 0, 0
    for name in sorted(names):
        raw = b.guard(ROOT / name).read_bytes()
        exact_blob(raw, staged[name])
        if name in hashes:
            digest(raw, hashes[name], "BOUND_EVIDENCE_DRIFT")
            checked += 1
        if sensitive(raw, needles):
            failures.append(name)
        if name.endswith(".zip"):
            count, bad = scan_archive(name, raw, needles)
            members += count
            failures.extend(bad)
    assert checked == len(hashes), "BOUND_EVIDENCE_MISSING"
    digest(index.read_bytes(), ROOT_INDEX_SHA, "ROOT_INDEX_CHANGED")
    # Recheck the index file identity without another Git process.
    return {"ok": not failures, "indexed": True, "mode": mode, "files": len(names), "archive_members": members,
            "byte_exact_staged": len(names), "bound_evidence_checked": checked, "root_index_unchanged": True,
            "offline_identity_checked": True, "failed_paths": failures, "git_processes": 3,
            "scan": "V6 known credential/encoding and token-shape checks; bounded in-memory ZIP members", "platform_operations": 0}


def selftest():
    checks = 0
    def rejects(action, code):
        nonlocal checks
        try:
            action()
        except AssertionError as error:
            assert str(error) == code
            checks += 1
            return
        raise AssertionError("SELFTEST_NEGATIVE_ACCEPTED")
    raw = b"synthetic bytes\n"
    oid = hashlib.sha1(b"blob " + str(len(raw)).encode() + b"\0" + raw).hexdigest()
    entry = staged_objects(("100644 " + oid + " 0\tTools/ota/p44-after-recovery.cjs\0").encode())
    exact_blob(raw, entry["Tools/ota/p44-after-recovery.cjs"])
    rejects(lambda: exact_blob(raw + b"x", ("100644", oid)), "STAGED_BYTE_DRIFT")
    rejects(lambda: exact_blob(raw, ("120000", oid)), "UNREVIEWED_INDEX_MODE")
    rejects(lambda: staged_objects(("100644 " + oid + " 1\tx\0").encode()), "INDEX_ENTRY_INVALID")
    rejects(lambda: relative("../escape"), "DELIVERY_PATH")
    assert all(allowed(name, "source") for name in SOURCE) and allowed(PREPARATION + "review.json", "source")
    assert all(allowed(name, "bundle") for name in BUNDLE) and allowed(PACKAGE + "closeout/report.json", "bundle")
    assert not allowed(PACKAGE + "evidence/x", "source") and not allowed("Tools/ota/p44-after-recovery.cjs", "bundle")
    assert not allowed("docs/acceptance-contracts/P4-4-v70/evidence/x", "bundle")
    value = b"synthetic-sentinel-only"
    needles = m.secret_forms({value}, b"synthetic-provisioning-only")
    assert all(sensitive(form, needles) for form in needles) and not sensitive(b"public text", needles)
    assert sensitive(b"ghp_" + b"z" * 20, needles) and sensitive(b"github_pat_" + b"z" * 20, needles)
    digest(raw, b.sha(raw), "HASH")
    rejects(lambda: digest(raw + b"x", b.sha(raw), "HASH"), "HASH")
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w") as archive:
        archive.writestr("public.txt", b"public text")
        archive.writestr("sensitive.txt", value)
    assert scan_archive("fixture.zip", buffer.getvalue(), needles) == (2, ["fixture.zip::sensitive.txt"])
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w") as archive:
        for number in range(1025):
            archive.writestr(str(number), b"")
    rejects(lambda: scan_archive("limit.zip", buffer.getvalue(), needles), "ZIP_MEMBER_LIMIT")
    return {"ok": True, "selftest": True, "negative_predicates": checks, "platform_operations": 0,
            "credential_reads": 0, "git_processes": 0, "fixtures": "memory only"}


class Parser(argparse.ArgumentParser):
    def error(self, message):
        raise AssertionError("INVALID_ARGUMENTS")


def main():
    output, started = None, time.monotonic()
    try:
        assert Path.cwd().absolute() == ROOT and sys.flags.optimize == 0 and sys.dont_write_bytecode, "EXECUTION_CONTEXT"
        parser = Parser(description=__doc__)
        parser.add_argument("mode", choices=("source", "bundle", "selftest"))
        parser.add_argument("--output")
        args = parser.parse_args()
        if args.output:
            output = b.guard(ROOT / relative(args.output))
            output.relative_to(LOGS)
            assert not output.exists(), "OUTPUT_EXISTS"
        result = selftest() if args.mode == "selftest" else audit(args.mode)
    except Exception as error:
        code = str(error)
        result = {"ok": False, "error_code": code if re.fullmatch(r"[A-Z][A-Z0-9_]{0,79}", code) else "DELIVERY_AUDIT_FAILED",
                  "platform_operations": 0}
    result["elapsed_seconds"] = round(time.monotonic() - started, 3)
    result["auditor_sha256"] = b.sha(b.guard(Path(__file__)).read_bytes())
    if output is not None:
        b.write(output, result)
    print(json.dumps(result))
    return 0 if result["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
