"""One-use P4-1 evidence copier. It never executes a product or cloud operation."""
import argparse
import hashlib
import json
import re
import stat
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DEST = ROOT / "docs/ota-exec-notes/P4-1-ci-2026-10-15"
COMMIT = "fa74905e84c489cccc248617d37ab9f56c8f961c"


def sha(data):
    return hashlib.sha256(data).hexdigest()


def encoded(value):
    return (json.dumps(value, ensure_ascii=True, indent=2) + "\n").encode()


def guard(target):
    actual = target.resolve(strict=False)
    actual.relative_to(ROOT)
    for parent in (target, *target.parents):
        if parent.exists() and getattr(parent.lstat(), "st_file_attributes", 0) & stat.FILE_ATTRIBUTE_REPARSE_POINT:
            raise RuntimeError("Reparse point: " + str(parent))
    return actual


def original(path):
    return guard(ROOT / path).read_bytes()


assert Path.cwd().resolve() == ROOT
parser = argparse.ArgumentParser()
parser.add_argument("--apply", action="store_true")
parser.add_argument("--expected-plan-sha")
args = parser.parse_args()
payloads = {}
origins = {}


def add(name, data, source):
    assert name not in payloads
    payloads[name] = data
    origins[name] = source


for source_dir, destination in ((".cache/github", "github"), (".cache/logs", "local")):
    for source in sorted((ROOT / source_dir).iterdir()):
        if source.is_file() and source.suffix in (".json", ".txt", ".zip"):
            relative = source.relative_to(ROOT).as_posix()
            add(destination + "/" + source.name, original(relative), relative)
for name in ("run.cjs", "gh.cjs", "archive-p41.py"):
    add("local/" + name, original(".cache/" + name), ".cache/" + name)

api = json.loads(original(".cache/github/batch5-artifacts.json"))
archives = {
    11931006831: "batch5-artifact-gcc.zip",
    11930961851: "batch5-artifact-app-retry.zip",
    11930422285: "batch5-artifact-boot.zip",
    11930178698: "batch5-artifact-tests.zip",
}
artifact_rows = []
member_rows = []
for item in api["artifacts"]:
    filename = archives[item["id"]]
    data = original(".cache/github/" + filename)
    assert "sha256:" + sha(data) == item["digest"]
    assert len(data) == item["size_in_bytes"]
    assert item["workflow_run"]["head_sha"] == COMMIT
    assert item["workflow_run"]["id"] == 38642386248
    artifact_rows.append({**item, "archivedAs": "github/" + filename})
    with zipfile.ZipFile(ROOT / ".cache/github" / filename) as archive:
        for info in archive.infolist():
            content = archive.read(info)
            member_rows.append({"archive": "github/" + filename, "member": info.filename,
                                "sizeBytes": len(content), "sha256": sha(content),
                                "zipTimestamp": list(info.date_time)})

with zipfile.ZipFile(ROOT / ".cache/github/batch5-logs.zip") as archive:
    tooling_name = next(n for n in archive.namelist() if "/" not in n and "Release tooling" in n)
    tooling = re.sub(r"\x1b\[[0-9;]*[A-Za-z]", "", archive.read(tooling_name).decode("utf-8-sig"))
    fixture = json.loads(next(line.split("BYTE_FIXTURE ", 1)[1] for line in tooling.splitlines() if "BYTE_FIXTURE " in line))
    cli = json.loads(next(line.split("PREPARATION_CLI ", 1)[1] for line in tooling.splitlines() if "PREPARATION_CLI " in line))
    assert cli["exitCode"] == 0 and cli["missingKeyExit"] == 2
    counts = [int(n) for n in re.findall(r"\bTests\s+(\d+) passed", tooling)]
    node_counts = [int(n) for n in re.findall(r"\u2139 tests (\d+)", tooling)]
    python_counts = [int(n) for n in re.findall(r"Ran (\d+) tests", tooling)]
    assert counts == [34, 20, 156] and node_counts == [15, 19] and python_counts == [8, 9]
    build_name = next(n for n in archive.namelist() if n.endswith("/11_Build firmware.txt"))
    build_log = archive.read(build_name).decode("utf-8-sig")
    compiler_warnings = len(re.findall(r"(?im)^.*\bwarning:.*$", build_log))
    compiler_errors = len(re.findall(r"(?im)^.*\berror:.*$", build_log))
    assert compiler_warnings == 640 and compiler_errors == 0


def verified_package(archive_name, prefix, label, expected_patch):
    with zipfile.ZipFile(ROOT / ".cache/github" / archive_name) as archive:
        def read(name):
            return archive.read(prefix + name)
        metadata_data = read("cloudflare-firmware-release-metadata.json")
        metadata = json.loads(metadata_data)
        summary_data = read("verification.json")
        summary = json.loads(summary_data)
        final = read("app-final.bin")
        assert sha(final) == metadata["targetImageSha256"] == summary["finalImage"]["sha256"]
        assert summary["preparedMetadataSha256"] == sha(metadata_data)
        assert summary["fullByteEqual"] is True and summary["recoveryVerified"] is True
        assert summary["patchByteEqual"] is expected_patch
        assert read("work/full-candidate.bin") == final == read("work/recovery-app.bin")
        if expected_patch:
            assert read("work/patch-candidate.bin") == final
        for asset in metadata["assets"]:
            data = read(asset["fileName"])
            assert len(data) == asset["sizeBytes"] and sha(data) == asset["sha256"]
            assert asset["r2Verified"] is False
        for step in summary["steps"]:
            assert step["exitCode"] == 0
            assert sha(read("steps/" + step["label"] + ".stdout.txt")) == step["stdoutSha256"]
            assert sha(read("steps/" + step["label"] + ".stderr.txt")) == step["stderrSha256"]
        for name, content in (("cloudflare-firmware-release-metadata.json", metadata_data), ("verification.json", summary_data)):
            add("selected/" + label + "/" + name, content, "github/" + archive_name + "!" + prefix + name)
        return {"archive": "github/" + archive_name, "prefix": prefix,
                "finalImage": summary["finalImage"], "assets": metadata["assets"],
                "metadataSizeBytes": len(metadata_data), "metadataSha256": sha(metadata_data),
                "verificationSizeBytes": len(summary_data), "verificationSha256": sha(summary_data),
                "toolSteps": summary["steps"], "r2Verified": False}


fixture_prefix = "firmware-release-tests/" + fixture["path"].split("/.cache/firmware-release-tests/", 1)[1] + "/"
fixture_result = verified_package("batch5-artifact-tests.zip", fixture_prefix, "synthetic-three-assets", True)
gcc_result = verified_package("batch5-artifact-gcc.zip", "", "gcc-development", None)
with zipfile.ZipFile(ROOT / ".cache/github/batch5-artifact-gcc.zip") as archive:
    marker = archive.read("DEVELOPMENT-ONLY.json")
    assert json.loads(marker)["installable"] is False
    add("selected/gcc-development/DEVELOPMENT-ONLY.json", marker, "github/batch5-artifact-gcc.zip!DEVELOPMENT-ONLY.json")
with zipfile.ZipFile(ROOT / ".cache/github/batch5-artifact-app-retry.zip") as app_archive:
    inputs_data = app_archive.read("gcc-build-inputs.json")
    build = json.loads(inputs_data)
    assert build["commitSha"] == COMMIT
    assert sha(app_archive.read(build["app"]["fileName"])) == build["app"]["sha256"]
    with zipfile.ZipFile(ROOT / ".cache/github/batch5-artifact-boot.zip") as boot_archive:
        assert sha(boot_archive.read(build["boot"]["fileName"])) == build["boot"]["sha256"]
    add("selected/gcc-build-inputs.json", inputs_data, "github/batch5-artifact-app-retry.zip!gcc-build-inputs.json")

inspection = {
    "scope": "Implementation self-test evidence, NOT independent acceptance or real rehearsal",
    "branch": "dev/p4-1/unattended-20261015", "testedCommit": COMMIT,
    "firmwareRun": 38642386248, "backendRun": 38641540543,
    "backendTestedCommit": "1eed86222e1ac3ef14281fc1b1b4a26a94b73375",
    "counts": {"hostScriptsAndMigration": counts[0], "pipelineHost": counts[1], "nativeWorkerd": counts[2],
               "package": python_counts[0], "goldenVectors": python_counts[1], "workflow": node_counts[0], "bytes": node_counts[1]},
    "countPolicy": "Separate suites; no addition of backend native repeats or duplicate aggregate/step logs",
    "diagnostics": {"gccCompilerLinkerWarnings": compiler_warnings, "gccCompilerLinkerErrors": compiler_errors,
                    "vendorWarnings": len(re.findall(r"(?im)^.*\bwarning:.*$", tooling)),
                    "nativeErrorDiagnosticLines": len(re.findall(r"(?im)^.*\berror:.*$", tooling)),
                    "nativeErrorContext": "Expected constraint/rollback exceptions in passing negative tests, not hidden compiler failures"},
    "cliPositiveAndNegativeOriginal": cli, "syntheticFixtureOriginal": fixture,
    "syntheticThreeAssets": fixture_result, "actualGccDevelopment": gcc_result,
    "buildInputs": build, "artifacts": artifact_rows,
    "realObservations": {name: "NOT_RUN" for name in ("formalBase", "remoteUploader", "stagingR2Readback", "realD1ReadyReplay", "productionZeroSideEffects", "independentAcceptance")},
}
add("ci-inspection.json", encoded(inspection), "Derived from the archived original logs and artifact bytes")
add("artifact-members.json", encoded(member_rows), "Derived from all four original artifact ZIPs")

token_pattern = re.compile(rb"\b(?:gh[pousr]_[A-Za-z0-9]{20,}|github_pat_[A-Za-z0-9_]{30,})\b")
for name, data in payloads.items():
    assert not token_pattern.search(data), "Credential pattern in " + name
    if name.endswith(".zip"):
        import io
        with zipfile.ZipFile(io.BytesIO(data)) as archive:
            for member in archive.infolist():
                if member.filename.endswith((".txt", ".json", ".log", ".cjs", ".py")):
                    assert not token_pattern.search(archive.read(member)), "Credential pattern in ZIP member"

attributes = DEST / ".gitattributes"
assert attributes.read_bytes() == b"* -text\n"
inventory = [{"path": ".gitattributes", "sizeBytes": attributes.stat().st_size, "sha256": sha(attributes.read_bytes()), "source": "Manual evidence byte-preservation rule"}]
for name, data in sorted(payloads.items()):
    inventory.append({"path": name, "sizeBytes": len(data), "sha256": sha(data), "source": origins[name]})
add("inventory.json", encoded({"testedCommit": COMMIT, "files": inventory}), "Generated inventory, excluding itself")
targets = [guard(DEST / name) for name in sorted(payloads)]
for target in targets:
    assert not target.exists(), "Refusing to overwrite " + str(target)
plan_sha = sha(encoded([str(target) for target in targets]))
print(json.dumps({"preflight": "PASS", "root": str(ROOT), "targets": [str(t) for t in targets], "planSha256": plan_sha}, indent=2))
if args.apply:
    assert args.expected_plan_sha == plan_sha, "Reviewed output plan changed"
    for name, data in payloads.items():
        target = guard(DEST / name)
        target.parent.mkdir(parents=True, exist_ok=True)
        guard(target)
        with target.open("xb") as stream:
            stream.write(data)
        assert target.read_bytes() == data
    print(json.dumps({"archivedFiles": len(payloads), "bytes": sum(map(len, payloads.values())), "inventorySha256": sha(payloads["inventory.json"])}))
