"""Read already captured failure bytes; not a replacement formal PASS criterion."""
import hashlib
import importlib.util
import json
import zipfile
from pathlib import Path

root = Path.cwd().resolve()
spec = importlib.util.spec_from_file_location("p41_frozen_inspector", root / "docs/acceptance-contracts/P4-1-v1/tools/inspect.py")
inspection = importlib.util.module_from_spec(spec)
spec.loader.exec_module(inspection)
work = root / ".cache/p41-acceptance-20261016"
target = json.loads((work / "formal/target.json").read_bytes())
archive_path = work / "formal/completed/rehearsal.zip"
with zipfile.ZipFile(archive_path) as archive:
    load = lambda name: json.loads(archive.read(name))
    build = load("keyed-build/gcc-build-inputs.json")
    compiled = load("keyed-build/keyed-build-evidence.json")
    prepared = load("prepared/verification.json")
    assert build["commitSha"] == compiled["commitSha"] == prepared["commitSha"] == target["commitSha"]
    assert build["keyBinding"] == compiled["keyBinding"]
    assert build["keyBinding"]["source"] == "approved-ci-key-v1"
    assert build["keyBinding"]["keySha256"] == target["keySha256"]
    assert compiled["compilerCache"] == "DISABLED"
    assert "-include" in compiled["keyCompileCommand"]["command"]
    assert "private-key.h" in compiled["keyCompileCommand"]["command"]
    assert "ota_keys.c" in compiled["keyCompileCommand"]["file"]
    inspection.verified_steps(archive, "keyed-build", compiled["steps"])
    inspection.verified_steps(archive, "prepared", prepared["steps"])
    assert len(compiled["artifacts"]) == 8
    for item in compiled["artifacts"]:
        inspection.checked_bytes(archive.read("keyed-build/" + item["path"]), item["sizeBytes"], item["sha256"])
    final = archive.read("prepared/app-final.bin")
    fields = inspection.check_finalized(final, archive.read("keyed-build/app/X-Track-App-GCC.bin"),
                                        target["versionName"], build["buildTimestamp"])
    assert prepared["base"] == target["descriptor"]
    assert archive.read("prepared/work/base-final.bin") == (inspection.BASE_DIR / "app-final.bin").read_bytes()
    for name in ["full-candidate.bin", "patch-candidate.bin", "recovery-app.bin"]:
        assert archive.read("prepared/work/" + name) == final
    recovered, kind = inspection.recovery_owner().split_asset(archive.read("prepared/recovery-v3.2.8.bin"), "recovery")
    assert kind == "recovery" and recovered == final
    for item in prepared["assets"]:
        inspection.checked_bytes(archive.read("prepared/" + item["fileName"]), item["sizeBytes"], item["sha256"])
        assert item["r2Verified"] is False
    assert [item["step"] for item in load("prepared/release-steps.json")] == ["preflight"]
    assert "prepared/release-evidence.json" not in archive.namelist()
    assert not any("private-key.h" in name or name.endswith("DEVELOPMENT-ONLY.json") for name in archive.namelist())
    print(json.dumps({"ok": True, "scope": "PARTIAL_OFFLINE_FAILURE_TRIAGE_NOT_WHOLE_CRITERION_PASS",
                      "archive_sha256": hashlib.sha256(archive_path.read_bytes()).hexdigest(),
                      "commitSha": target["commitSha"], "keyBinding": build["keyBinding"], "fw_header": fields,
                      "final_sha256": hashlib.sha256(final).hexdigest(), "eight_gcc_artifacts": True,
                      "actual_full_patch_recovery_bytes_equal": True, "r2_registration": "NOT_COMPLETED",
                      "diagnostics": [{k: step[k] for k in ["label", "exitCode", "warningLines", "errorLines"]}
                                      for step in compiled["steps"]], "assets": prepared["assets"]}, indent=2))
