"""Independent offline evaluation of original P4-1 evidence; never builds or deploys."""
import argparse
import hashlib
import importlib.util
import json
import re
import subprocess
import sys
import collections
import xml.etree.ElementTree as ET
import zipfile
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[4]
assert Path.cwd().resolve() == ROOT
HANDOFF = "a52d5b567ddfe5982063f5ac6af5c0a0b0170a18"
RUNTIME = "18c4da4d28c1f2bcf7175f4b461e2a6bf462a23e"
ARCHIVE_COMMIT = "c860b3be7a0b1a3ca1b3a53cf79cc9ef21cc9124"
BASE_DIR = ROOT / "docs/ota-exec-notes/P4-1-bootstrap-baseline-2026-10-15"
KEY_FINGERPRINT = "a94ae0f006b3d6be51279b861dc19b8a0892833939d0a4db5a81ee7af511fe9e"
REPAIR_COMMIT = "5d4d07571451905ac156a1a721fa8b8ce764ed7c"


def digest(data):
    return hashlib.sha256(data).hexdigest()


def read_json(file):
    return json.loads(Path(file).read_bytes())


def guard(value):
    target = Path(value).absolute()
    target.resolve().relative_to(ROOT)
    for parent in [target, *target.parents]:
        if parent.exists():
            assert not parent.is_symlink() and not parent.is_junction(), f"Reparse point: {parent}"
    return target


def identity(file):
    data = Path(file).read_bytes()
    return {"path": Path(file).relative_to(ROOT).as_posix(), "size_bytes": len(data), "sha256": digest(data)}


def checked_bytes(data, size, expected):
    assert len(data) == size and digest(data) == expected.lower(), "Byte identity mismatch"


def inventory(directory):
    data = read_json(directory / "inventory.json")
    seen = set()
    for entry in data["files"]:
        assert entry["path"] not in seen
        seen.add(entry["path"])
        file = directory / entry["path"]
        file.resolve().relative_to(directory.resolve())
        checked_bytes(file.read_bytes(), entry["sizeBytes"], entry["sha256"])
    member_count = 0
    if (directory / "artifact-members.json").exists():
        entries = read_json(directory / "artifact-members.json")
        for archive_name in sorted({entry["archive"] for entry in entries}):
            with zipfile.ZipFile(directory / archive_name) as archive:
                names = archive.namelist()
                assert len(names) == len(set(names)), "Duplicate ZIP members"
                selected = [entry for entry in entries if entry["archive"] == archive_name]
                for entry in selected:
                    checked_bytes(archive.read(entry["member"]), entry["sizeBytes"], entry["sha256"])
                    member_count += 1
    return {"inventory": identity(directory / "inventory.json"), "files_verified": len(seen),
            "zip_members_verified": member_count}


def recovery_owner():
    spec = importlib.util.spec_from_file_location("p41_recovery", ROOT / "Tools/jlink/prepare-bootstrap-app.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def check_finalized(final, placeholder, version, timestamp):
    owner = recovery_owner()
    fields = owner.validate_app(final)
    assert fields["version_name"] == version and fields["build_ts"] == timestamp
    start, size = owner.FW_HEADER_OFFSET, owner.FW_HEADER_SIZE
    assert placeholder[start:start + size] == b"\xff" * size
    assert len(final) == len(placeholder)
    assert final[:start] == placeholder[:start] and final[start + size:] == placeholder[start + size:]
    return fields


def log_text(archive, fragment):
    matches = [name for name in archive.namelist() if "/" in name and fragment in name]
    assert len(matches) == 1, f"Missing/ambiguous original step: {fragment}"
    return re.sub(r"\x1b\[[0-9;]*[A-Za-z]", "", archive.read(matches[0]).decode("utf-8-sig"))


def remediation():
    directory = ROOT / "docs/ota-exec-notes/P4-1-native-01-remediation-2026-10-16"
    checked = [inventory(directory), inventory(directory / "closing")]
    entries = read_json(directory / "zip-members.json")
    for name in sorted({item["archive"] for item in entries}):
        with zipfile.ZipFile(directory / name) as archive:
            selected = [item for item in entries if item["archive"] == name]
            assert len(archive.namelist()) == len(set(archive.namelist()))
            assert set(archive.namelist()) == {item["member"] for item in selected}
            for item in selected:
                checked_bytes(archive.read(item["member"]), item["sizeBytes"], item["sha256"])

    def revision_object(revision, relative):
        return subprocess.check_output(["git", "--no-optional-locks", "rev-parse", revision + ":" + relative], cwd=ROOT).decode().strip()

    final = read_json(directory / "commands/p41-native-01-final-inputs.stdout.txt")
    source_bindings = []
    for item in final["files"]:
        assert revision_object(REPAIR_COMMIT, item["path"]) == item["gitBlob"]
        assert revision_object("HEAD", item["path"]) == item["gitBlob"], "Tested product or regression changed"
        source_bindings.append({"path": item["path"], "gitBlob": item["gitBlob"]})
    old = read_json(directory / "commands/p41-native-01-red-inputs.stdout.txt")
    uploader = "app/bluetooth_flutter_Trace/cloudflare/update-service/scripts/upload-firmware-r2-asset.mjs"
    assert revision_object("53b78608cac6bb5c2e9253362471b6383f5c31ff", uploader) == next(
        item["gitBlob"] for item in old["files"] if item["path"] == uploader)

    def original(label, expected):
        stem = directory / "commands" / ("p41-native-01-" + label)
        receipt = read_json(str(stem) + ".json")
        assert receipt["closed"] is True and receipt["exitCode"] == expected
        assert Path(receipt["cwd"]).resolve() == (ROOT / "app/bluetooth_flutter_Trace/cloudflare/update-service/worker").resolve()
        assert receipt["executable"] == "node"
        assert "--script-shell=cmd.exe" in receipt["args"]
        return [re.sub(r"\x1b\[[0-9;]*[A-Za-z]", "", Path(str(stem) + suffix).read_text(encoding="utf-8"))
                for suffix in [".stdout.txt", ".stderr.txt"]]

    red, red_error = original("red", 1)
    assert re.search(r"\bTests\s+3 failed\s*\|\s*38 passed\s+\(41\)", red)
    assert "DevalueError: Cannot stringify arbitrary non-POJOs" in red_error and "[2].httpMetadata" in red_error
    for kind in ["full", "patch", "recovery"]:
        assert "P41-NATIVE-01 uploads " + kind + " through the real SDK codec" in red + red_error
    for label, count in [("green", 41), ("host-final", 41), ("pipeline", 136)]:
        text, _ = original(label, 0)
        assert [int(value) for value in re.findall(r"\bTests\s+(\d+) passed", text)] == [count]
    type_error, _ = original("types", 2)
    assert "TS2345" in type_error
    original("types-fixed", 0)

    github = directory / "github"
    source = read_json(github / "p41-native-01-source-commit.json")
    checkout = read_json(github / "p41-native-01-checkout-commit.json")
    assert source["sha"] == REPAIR_COMMIT
    assert checkout["sha"] == "9811af20b122442bd8cf91902b8455403e3d84fa"
    assert source["tree"]["sha"] == checkout["tree"]["sha"] == "bd380a8f989bda73f8a4f7221302d3bd35cb5f6a"
    assert subprocess.check_output(["git", "rev-parse", REPAIR_COMMIT + "^{tree}"], cwd=ROOT).decode().strip() == source["tree"]["sha"]
    runs = read_json(github / "p41-native-01-ci-final.json")["workflow_runs"]
    expected = {"firmware-build.yml": 38929267144, "acceptance-governance.yml": 38929267147,
                "cloudflare-update-service.yml": 38929267218, "build.yml": 38929267169}
    for name, run_id in expected.items():
        run = next(item for item in runs if item["id"] == run_id)
        assert run["path"] == ".github/workflows/" + name
        assert run["head_sha"] == REPAIR_COMMIT and run["run_attempt"] == 1
        assert run["status"] == "completed" and run["conclusion"] == "success"
    with zipfile.ZipFile(github / "p41-native-01-fw-logs.zip") as archive:
        counts = {}
        for name, fragment, count in [("host", "Run script and migration host tests explicitly", 41),
            ("pipeline", "Run release pipeline with real handlers", 136),
            ("native", "Run native workerd D1 R2", 156)]:
            text = log_text(archive, fragment)
            assert [int(value) for value in re.findall(r"\bTests\s+(\d+) passed", text)] == [count]
            counts[name] = count
        checkout_logs = "\n".join(archive.read(name).decode("utf-8-sig") for name in archive.namelist()
                                  if "/" in name and "Checkout" in name)
        assert checkout["sha"] in checkout_logs
    assert not subprocess.check_output(["git", "--no-optional-locks", "diff", "--name-only", "53b7860", "HEAD", "--",
        "docs/acceptance-contracts/P4-1-v1", "docs/acceptance-contracts/P4-1-v1.contract.json"], cwd=ROOT)
    return {"scope": "INDEPENDENT_OFFLINE_REVIEW_OF_REMEDIATION_ORIGINALS", "repairCommit": REPAIR_COMMIT,
            "inventories": checked, "zipMembersVerified": len(entries), "sourceBindings": source_bindings,
            "oldProductFailures": 3, "localHost": 41, "localPipeline": 136, "originalCiCounts": counts,
            "ciRuns": expected, "actualCheckout": checkout["sha"], "sourceAndCheckoutTreeEqual": True,
            "historicalTypeFailurePreserved": True, "realR2WriteOrReadyProven": False}


def origins():
    result = {"scope": "INDEPENDENT_OFFLINE_EVALUATION_OF_EXISTING_ORIGINALS", "source_commit": HANDOFF}
    result["remediation_review"] = remediation()
    names = ["P4-1-readiness-2026-10-16", "P4-1-bindings-2026-10-16",
             "P4-1-bootstrap-baseline-2026-10-15", "P4-1-r2-registration-qualification-2026-10-15"]
    result["inventories"] = [inventory(ROOT / "docs/ota-exec-notes" / name) for name in names]
    diff = subprocess.check_output(["git", "--no-optional-locks", "diff", "--name-only", RUNTIME, HANDOFF,
                                   "--", ".github", "Tools", "app"], cwd=ROOT)
    assert not diff, "Reconcile product changes since the development originals"
    result["runtime_equivalence"] = {"from": RUNTIME, "to": HANDOFF, "changed_product_paths": []}

    bindings = ROOT / "docs/ota-exec-notes/P4-1-bindings-2026-10-16"
    run = read_json(bindings / "github/run-1.json")
    assert run["id"] == 38859822756 and run["run_attempt"] == 1 and run["conclusion"] == "success"
    assert run["head_sha"] == "c715ec6b00f8d9b06a820213da72421694b1e44c"
    jobs = read_json(bindings / "github/jobs-1.json")["jobs"]
    native = [job for job in jobs if job["name"] == "Isolated firmware binding qualification (not rehearsal)"]
    assert len(native) == 1 and native[0]["conclusion"] == "success"
    assert all(job["conclusion"] == "skipped" for job in jobs if job["name"].startswith(("Firmware rehearsal", "Firmware production")))
    reviews = read_json(bindings / "github/reviews-1.json")
    assert any(review["state"] == "approved" and review["user"]["login"] == "Eitan-S-23"
               and any(env["name"] == "firmware-rehearsal" for env in review["environments"]) for review in reviews)
    listing = read_json(bindings / "github/artifacts-1.json")["artifacts"]
    artifact = next(item for item in listing if item["id"] == 12029386620)
    blob = (bindings / "github/bindings-1.zip").read_bytes()
    checked_bytes(blob, artifact["size_in_bytes"], artifact["digest"].removeprefix("sha256:"))
    with zipfile.ZipFile(bindings / "github/bindings-1.zip") as archive:
        assert archive.read("result.json") == (bindings / "result.json").read_bytes()
    observed = read_json(bindings / "result.json")
    assert observed["scope"] == "RUNTIME_BINDING_QUALIFICATION" and observed["workerBindingsMatched"] is True
    assert observed["canonicalRehearsal"] == observed["independentAcceptance"] == "NOT_RUN"
    fixture = read_json(ROOT / observed["fixturePath"])
    assert digest((ROOT / observed["fixturePath"]).read_bytes()) == observed["fixtureSha256"]
    for actual, expected in zip(observed["assets"], fixture["assets"], strict=True):
        for field in ["kind", "fileName", "r2Key", "sha256", "sizeBytes"]:
            assert actual[field] == expected[field]
    assert observed["database"]["before"] == observed["database"]["after"]
    assert observed["database"]["before"]["counts"] == {
        "firmware_releases": 1, "firmware_releases_legacy": 0, "firmware_release_assets": 3,
        "firmware_channels": 2, "audit_logs": 1}
    result["native_qualification"] = {"run_id": run["id"], "original_operator": "Eitan-S-23 approved; implementation workflow executed",
        "assets": observed["assets"], "database": observed["database"],
        "control_plane": observed["controlPlane"], "not_full_production_snapshot": True}
    with zipfile.ZipFile(bindings / "github/logs-1.zip") as archive:
        suites = {}
        for name, fragment, count in [
            ("host_script", "Run script and migration host tests explicitly", 34),
            ("pipeline_host", "Run release pipeline with real handlers", 134),
            ("native_workerd", "Run native workerd D1 R2", 156)]:
            text = log_text(archive, fragment)
            assert [int(value) for value in re.findall(r"\bTests\s+(\d+) passed", text)] == [count]
            suites[name] = count
        for name, fragment, count in [("workflow", "Check workflow execution graph", 57),
                                      ("byte", "Execute production byte preparation", 22)]:
            text = log_text(archive, fragment)
            assert f"tests {count}" in text and "fail 0" in text
            suites[name] = count
        text = log_text(archive, "Check real package generation and approved-envelope replay")
        assert [int(value) for value in re.findall(r"Ran (\d+) tests", text)] == [8, 9]
        suites.update(pack=8, golden=9)
        diagnostics = {}
        for name, fragment, expected in [("ordinary_gcc", "/11_Build firmware.txt", 640),
            ("development_key_gcc", "Exercise the shared key-bound GCC build", 640),
            ("vendor", "Build the existing vendor bsdiff", 6)]:
            text = log_text(archive, fragment)
            warnings, errors = len(re.findall(r"warning:", text)), len(re.findall(r"error:", text))
            assert warnings == expected and errors == 0
            diagnostics[name] = {"warnings": warnings, "errors": errors}
        result.update(development_counts=suites, diagnostics=diagnostics)

    proof = read_json(BASE_DIR / "provenance.json")
    verified = proof["verification"]
    assert verified["base"] is None and verified["patchByteEqual"] is None and verified["r2Verified"] is False
    assert proof["developmentOnly"]["installable"] is False
    source = ROOT / proof["retainedOriginals"]["directory"]
    with zipfile.ZipFile(source / "batch5-artifact-gcc.zip") as archive:
        assert digest((source / "batch5-artifact-gcc.zip").read_bytes()) == proof["artifact"]["digest"].removeprefix("sha256:")
        for name in ["app-final.bin", "verification.json", "DEVELOPMENT-ONLY.json"]:
            assert archive.read(name) == (BASE_DIR / name).read_bytes()
    for zip_name, binary in [("batch5-artifact-app-retry.zip", "X-Track-App-GCC.bin"),
                             ("batch5-artifact-boot.zip", "X-Track-Boot.bin")]:
        with zipfile.ZipFile(source / zip_name) as archive:
            assert archive.read(binary) == (BASE_DIR / binary).read_bytes()
    final, placeholder = (BASE_DIR / "app-final.bin").read_bytes(), (BASE_DIR / "X-Track-App-GCC.bin").read_bytes()
    fields = check_finalized(final, placeholder, "3.2.7", 1792014177)
    assert digest(final) == "aaf5ccdb047ef8b3ff4ae0837f9593ceca857d90c98ea0bc09360e411bf4196f"
    for name in ["app-final.bin", "provenance.json", "X-Track-App-GCC.bin", "X-Track-Boot.bin"]:
        saved = subprocess.check_output(["git", "show", ARCHIVE_COMMIT + ":" + (BASE_DIR / name).relative_to(ROOT).as_posix()], cwd=ROOT)
        assert saved == (BASE_DIR / name).read_bytes()
    result["bootstrap"] = {"archive_commit": ARCHIVE_COMMIT, "source_commit": proof["run"]["head_sha"],
        "run_id": proof["run"]["id"], "artifact_id": proof["artifact"]["id"], "header": fields,
        "raw_app": identity(BASE_DIR / "app-final.bin"), "development_labels_preserved": True}

    qualification = read_json(ROOT / "docs/ota-exec-notes/P4-1-r2-registration-qualification-2026-10-15/operations/assets-register.json")
    http = [item for item in qualification["observations"] if item.get("action") == "REAL_REGISTER_HTTP"]
    assert [item["status"] for item in http] == [503, 201, 200, 409]
    assert http[0]["body"]["errorCode"] == "BACKEND_UNAVAILABLE"
    assert http[-1]["body"]["errorCode"] == "RELEASE_CONFLICT"
    assert http[1]["body"]["releaseId"] == http[2]["body"]["releaseId"]
    assert http[1]["body"]["idempotent"] is False and http[2]["body"]["idempotent"] is True
    snapshots = {item["action"]: [part["results"] for part in item["body"]["result"]]
                 for item in qualification["observations"] if item.get("action", "").startswith("D1_") and "body" in item}
    assert snapshots["D1_BEFORE_PARTIAL_ASSETS_NEGATIVE"] == snapshots["D1_AFTER_PARTIAL_ASSETS_NEGATIVE"] == [[], [], [], []]
    assert snapshots["D1_READY_AFTER_201"] == snapshots["D1_AFTER_200_REPLAY"] == snapshots["D1_AFTER_409_CONFLICT"]
    assert [len(rows) for rows in snapshots["D1_READY_AFTER_201"]] == [1, 3, 2, 1]
    result["original_remote_negatives"] = {"statuses": [item["status"] for item in http],
        "no_ready_after_partial_assets": True, "no_d1_change_after_replay_or_conflict": True,
        "scope": "Historical synthetic R2/S3 qualification, independently evaluated offline, not a second rehearsal"}
    return result


def verified_steps(archive, prefix, steps):
    assert steps and len({step["label"] for step in steps}) == len(steps)
    for step in steps:
        assert step["exitCode"] == 0, f"Failed original step: {step['label']}"
        for stream in ["stdout", "stderr"]:
            data = archive.read(prefix + "/steps/" + step["label"] + "." + stream + ".txt")
            assert digest(data) == step[stream + "Sha256"]
    return [step["label"] for step in steps]


def rehearsal(zip_path, target_path):
    target = read_json(target_path)
    with zipfile.ZipFile(zip_path) as archive:
        assert len(archive.namelist()) == len(set(archive.namelist()))
        assert not any("private-key.h" in name or name.endswith("DEVELOPMENT-ONLY.json") for name in archive.namelist())
        read = lambda name: json.loads(archive.read(name))
        build = read("keyed-build/gcc-build-inputs.json")
        compiled = read("keyed-build/keyed-build-evidence.json")
        prepared = read("prepared/verification.json")
        metadata_bytes = archive.read("prepared/cloudflare-firmware-release-metadata.json")
        metadata = json.loads(metadata_bytes)
        evidence = read("prepared/release-evidence.json")
        assert build["commitSha"] == compiled["commitSha"] == prepared["commitSha"] == metadata["commitSha"] == target["commitSha"]
        assert build["versionName"] == metadata["versionName"] == prepared["versionName"] == target["versionName"]
        assert build["keyBinding"] == compiled["keyBinding"]
        assert build["keyBinding"]["source"] == "approved-ci-key-v1"
        assert build["keyBinding"]["keySha256"] == target["keySha256"] == KEY_FINGERPRINT
        key_source = subprocess.check_output(["git", "show", target["commitSha"] + ":Libraries/OTA/ota_keys.c"], cwd=ROOT)
        assert digest(key_source) == build["keyBinding"]["keySourceSha256"]
        assert compiled["compilerCache"] == "DISABLED" and compiled["bootKeyConsumer"] is False
        assert digest(archive.read("keyed-build/CMakeCache.txt")) == compiled["compilerCacheConfigSha256"]
        assert digest(archive.read("keyed-build/compiler-launchers.ninja")) == compiled["compilerLaunchersSha256"]
        assert "ota_keys.c" in compiled["keyCompileCommand"]["file"]
        assert "-include" in compiled["keyCompileCommand"]["command"] and "private-key.h" in compiled["keyCompileCommand"]["command"]
        build_steps = verified_steps(archive, "keyed-build", compiled["steps"])
        assert build_steps == ["configure", "build", "size"]
        for artifact in compiled["artifacts"]:
            checked_bytes(archive.read("keyed-build/" + artifact["path"]), artifact["sizeBytes"], artifact["sha256"])
        assert len(compiled["artifacts"]) == 8
        final = archive.read("prepared/app-final.bin")
        placeholder = archive.read("keyed-build/app/X-Track-App-GCC.bin")
        fields = check_finalized(final, placeholder, target["versionName"], build["buildTimestamp"])
        assert metadata["targetImageSha256"] == digest(final)
        assert prepared["base"] == target["descriptor"]
        assert archive.read("prepared/work/base-final.bin") == (BASE_DIR / "app-final.bin").read_bytes()
        for name in ["full-candidate.bin", "patch-candidate.bin", "recovery-app.bin"]:
            assert archive.read("prepared/work/" + name) == final, "Actual apply result differs: " + name
        owner = recovery_owner()
        recovery, kind = owner.split_asset(archive.read("prepared/recovery-v" + target["versionName"] + ".bin"), "recovery")
        assert kind == "recovery" and recovery == final
        labels = verified_steps(archive, "prepared", prepared["steps"])
        assert {"patch-pack", "patch-apply", "full-apply", "recovery-verify", "base-verify", "finalize"}.issubset(labels)
        assert b"unpack(patch) OK:" in archive.read("prepared/steps/patch-apply.stdout.txt")
        assert prepared["patchByteEqual"] is True and prepared["fullByteEqual"] is True and prepared["recoveryVerified"] is True
        assert [asset["kind"] for asset in metadata["assets"]] == ["full", "patch", "recovery"]
        for asset in metadata["assets"]:
            checked_bytes(archive.read("prepared/" + asset["fileName"]), asset["sizeBytes"], asset["sha256"])
            assert asset["r2Verified"] is True
            actual = [item for item in evidence["uploads"] if item["fileName"] == asset["fileName"]]
            assert len(actual) == 1 and actual[0]["ok"] is True and actual[0]["status"] in ["UPLOADED", "ALREADY_PRESENT"]
            for field in ["sha256", "sizeBytes", "r2Key"]:
                assert actual[0][field] == asset[field]
        assert evidence["mode"] == "rehearsal" and evidence["github"] is None
        assert evidence["metadataSha256"] == digest(metadata_bytes)
        assert evidence["preparationSha256"] == digest(archive.read("prepared/verification.json"))
        assert evidence["canonicalRunId"] == evidence["executionRunId"] == metadata["runId"]
        assert evidence["executionAttempt"] == "1"
        assert evidence["registration"]["state"] == "ready" and evidence["registration"]["idempotent"] is False
        assert evidence["replay"]["idempotent"] is True and evidence["replay"]["releaseId"] == evidence["registration"]["releaseId"]
        assert evidence["registration"]["assetsRegistered"] == evidence["replay"]["assetsRegistered"] == 3
        diagnostics = [{key: step[key] for key in ["label", "exitCode", "warningLines", "errorLines"]} for step in compiled["steps"]]
        return {"scope": "INDEPENDENT_CANONICAL_REHEARSAL_ARTIFACT_EVALUATION", "artifact": identity(zip_path),
            "commitSha": target["commitSha"], "runId": metadata["runId"], "versionName": metadata["versionName"],
            "header": fields, "keyBinding": build["keyBinding"], "diagnostics": diagnostics,
            "metadataSha256": digest(metadata_bytes), "metadata": metadata, "remote_evidence": evidence,
            "eight_gcc_artifacts_verified": True, "actual_full_patch_candidates_equal": True, "recovery_verified": True}


def selftest():
    original = (BASE_DIR / "app-final.bin").read_bytes()
    placeholder = (BASE_DIR / "X-Track-App-GCC.bin").read_bytes()
    check_finalized(original, placeholder, "3.2.7", 1792014177)
    tampered = bytes([placeholder[0] ^ 1]) + placeholder[1:]
    assert tampered != placeholder, "Negative fixture must change the input"
    probes = [("trailing_bytes", (original + b"x", placeholder, "3.2.7", 1792014177)),
              ("wrong_version", (original, placeholder, "3.2.8", 1792014177)),
              ("wrong_timestamp", (original, placeholder, "3.2.7", 1792014178)),
              ("changed_payload", (original, tampered, "3.2.7", 1792014177))]
    rejected = []
    for label, args in probes:
        try:
            check_finalized(*args)
        except (AssertionError, ValueError):
            rejected.append(label)
        else:
            raise AssertionError(f"Negative fixture was accepted: {label}")
    try:
        checked_bytes(original, len(original), "0" * 64)
    except AssertionError:
        rejected.append("wrong_digest")
    assert len(rejected) == 5, "Digest negative fixture was accepted"
    return {"positive": 1, "discriminating_negative_cases": len(rejected),
            "rejected_cases": rejected, "device_or_remote_actions": 0}


def stable(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def r2_objects(receipt, role):
    selected = next(bucket for bucket in receipt["r2"] if bucket["role"] == role)
    assert selected["complete"] is True
    objects = {}
    for page in selected["pages"]:
        body = next(item for item in page["files"] if item["path"].endswith(".body"))
        data = (ROOT / body["path"]).read_bytes()
        checked_bytes(data, body["size_bytes"], body["sha256"])
        document = ET.fromstring(data)
        for element in document.findall("{*}Contents"):
            values = {child.tag.split("}")[-1]: child.text for child in element}
            assert values["Key"] not in objects
            objects[values["Key"]] = values
    return objects


def states():
    working = ROOT / ".cache/p41-acceptance-20261017"
    before, after = [read_json(working / "cloud" / label / "receipt.json") for label in ["before", "after"]]
    assert before["ok"] is True and after["ok"] is True
    assert before["mutationsRequested"] == after["mutationsRequested"] == 0
    for receipt in [before, after]:
        for item in receipt["files"]:
            checked_bytes((ROOT / item["path"]).read_bytes(), item["size_bytes"], item["sha256"])
    assert before["bindings"] == after["bindings"], "Existing Worker bindings changed"
    for worker in ["trace-update-service-staging", "e-track-firmware-p41-test"]:
        old = next(item for item in before["inventory"]["workers"] if item["id"] == worker)
        new = next(item for item in after["inventory"]["workers"] if item["id"] == worker)
        assert old == new, "Existing Worker deployment changed"
    databases = {}
    for role in ["protected", "test"]:
        old, new = [read_json(ROOT / next(db["artifact"]["path"] for db in receipt["databases"] if db["role"] == role))
                    for receipt in [before, after]]
        assert old["schema"] == new["schema"], "D1 schema changed"
        assert old["database"] == new["database"]
        databases[role] = (old["tables"], new["tables"])
    assert databases["protected"][0] == databases["protected"][1], "Protected D1 contents changed"
    assert r2_objects(before, "protected") == r2_objects(after, "protected"), "Protected R2 inventory changed"
    github_before, github_after = [read_json(working / "formal" / label / "snapshot.json")
                                  for label in ["github-before", "github-after"]]
    assert github_before["ok"] is True and github_after["ok"] is True
    assert github_before["complete"] is True and github_after["complete"] is True
    assert github_before["releases"] == github_after["releases"], "GitHub Releases/assets changed"
    assert github_before["environment"] == github_after["environment"], "Protected test approval/configuration changed"
    observed = read_json(working / "review/rehearsal-formal.json")
    assert observed["ok"] is True
    metadata = observed["metadata"]
    release_id = observed["remote_evidence"]["registration"]["releaseId"]
    old, new = databases["test"]
    assert old.keys() == new.keys()
    allowed = {"firmware_releases", "firmware_release_assets", "audit_logs"}
    additions = {}
    for table in old:
        if table not in allowed:
            assert old[table] == new[table], "Unrelated test D1 table changed: " + table
            continue
        previous = collections.Counter(stable(row) for row in old[table])
        current = collections.Counter(stable(row) for row in new[table])
        assert not (previous - current), "Existing test D1 row changed: " + table
        additions[table] = [json.loads(value) for value in (current - previous).elements()]
    assert len(additions["firmware_releases"]) == 1
    release = additions["firmware_releases"][0]
    assert release["id"] == release_id and release["state"] == "ready"
    assert release["version_code"] == metadata["versionCode"]
    assert json.loads(release["registration_json"]) == metadata
    assert len(additions["firmware_release_assets"]) == 3
    for asset in metadata["assets"]:
        row = next(row for row in additions["firmware_release_assets"] if row["file_name"] == asset["fileName"])
        assert row["release_id"] == release_id
        for field, expected in [("sha256", "sha256"), ("size_bytes", "sizeBytes"), ("r2_key", "r2Key"), ("kind", "kind")]:
            assert row[field] == asset[expected]
    assert len(additions["audit_logs"]) == 1, "Replay must not add an audit entry"
    previous_r2, current_r2 = r2_objects(before, "test"), r2_objects(after, "test")
    assert all(current_r2.get(key) == value for key, value in previous_r2.items()), "Existing test R2 object changed"
    new_keys = set(current_r2) - set(previous_r2)
    assert new_keys == {asset["r2Key"] for asset in metadata["assets"]}
    readback = read_json(working / "cloud/assets/receipt.json")
    assert readback["ok"] is True and readback["mutationsRequested"] == 0
    for asset in metadata["assets"]:
        assert int(current_r2[asset["r2Key"]]["Size"]) == asset["sizeBytes"]
        row = next(row for row in readback["assets"] if row["r2Key"] == asset["r2Key"])
        assert row["sha256"] == asset["sha256"] and row["sizeBytes"] == asset["sizeBytes"]
        request = next(request for request in readback["requests"] if request["sequence"] == row["requestSequence"])
        body = next(file for file in request["files"] if file["path"].endswith(".body"))
        checked_bytes((ROOT / body["path"]).read_bytes(), asset["sizeBytes"], asset["sha256"])
    return {"protected_d1_unchanged": True, "protected_r2_unchanged": True, "github_releases_unchanged": True,
            "worker_bindings_unchanged": True, "test_channels_unchanged": True,
            "new_test_release": release_id, "new_test_assets": 3, "new_test_audit_rows": 1,
            "independent_full_byte_r2_readback": True,
            "scope": "Business-resource snapshots, not a claim of no Wrangler preview control-plane state"}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("mode", choices=["origins", "rehearsal", "selftest", "states", "remediation"])
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--artifact", type=Path)
    parser.add_argument("--target", type=Path)
    args = parser.parse_args()
    output = guard(args.output)
    assert not output.exists(), "Do not overwrite an earlier evaluation"
    result = {"started": datetime.now(timezone.utc).isoformat(), "mode": args.mode}
    code = 0
    try:
        if args.mode == "remediation":
            result.update(remediation())
        elif args.mode == "origins":
            result.update(origins())
        elif args.mode == "selftest":
            result.update(selftest())
        elif args.mode == "states":
            result.update(states())
        else:
            result.update(rehearsal(args.artifact, args.target))
        result["ok"] = True
    except Exception as error:
        trace = error.__traceback__
        while trace.tb_next:
            trace = trace.tb_next
        result.update(ok=False, error={"type": type(error).__name__, "message": str(error),
                                     "file": Path(trace.tb_frame.f_code.co_filename).name, "line": trace.tb_lineno})
        code = 1
    result["ended"] = datetime.now(timezone.utc).isoformat()
    output.parent.mkdir(parents=True, exist_ok=True)
    with guard(output).open("x", encoding="utf-8", newline="\n") as stream:
        json.dump(result, stream, indent=2, ensure_ascii=True)
        stream.write("\n")
    print(json.dumps({"ok": result["ok"], "mode": args.mode, "output": output.relative_to(ROOT).as_posix(),
                      "error": result.get("error"), "sha256": digest(output.read_bytes())}))
    return code


if __name__ == "__main__":
    sys.exit(main())
