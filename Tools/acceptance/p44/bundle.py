"""P4-4 adaptation of the existing v3 bundle format, not a release controller."""
import argparse
import base64
import copy
from datetime import datetime, timezone
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import re
import stat
import subprocess
import sys
import zipfile

ROOT = Path(__file__).absolute().parents[3]
PACKAGE = ROOT / "docs/acceptance-contracts/P4-4-v4"
DATA = PACKAGE / "evidence"
CONTRACT = ROOT / "docs/acceptance-contracts/P4-4-v4.contract.json"
PREVIOUS = ROOT / "docs/acceptance-contracts/P4-4-v3"
PREVIOUS_CONTRACT = ROOT / "docs/acceptance-contracts/P4-4-v3.contract.json"
PREVIOUS_MATRIX = PREVIOUS / "final-evidence-matrix.json"
PREVIOUS_SHA256 = "4FC05662F1BB9CA829BB8E769754229F6BEBC41CBB99A3ED38099DB1E5D7E2CD"
PREVIOUS_MATRIX_SHA256 = "41C328859FE3289567FFFF409375766148D826D76F79918CF34ED14740413895"
PREVIOUS_SOURCE = "ba952497948a03c40cbd8baebbfc9228621fb44b"
PREVIOUS_BUNDLE = "20febda2ac2e05e5f4b761a9f365091b177516b6"
PREDECESSOR = "inputs/predecessor-before.json"
PREDECESSOR_ROOT = "p"
HISTORY = {
    "P4-4-v3": {"source_commit": PREVIOUS_SOURCE, "source_bundle_commit": PREVIOUS_BUNDLE,
                "contract_sha256": PREVIOUS_SHA256, "matrix_sha256": PREVIOUS_MATRIX_SHA256, "root": PREDECESSOR_ROOT},
    "P4-4-v2": {"source_commit": "70193ce7fb7cc4e426029d07cf7b50c1fcbfef1c",
                "source_bundle_commit": "84268ac2ad34727b76250ff944211b7efba1cfb3",
                "contract_sha256": "CFFF5E841B6FBE6F251A8A931C450907B477B678E890DCD6B00C2081E07D719A",
                "matrix_sha256": "C335006F0B166535CE957C345ADF579440E087B6B980239BACA96500F019A46C",
                "root": "inputs/predecessor-before"},
    "P4-4-v1": {"source_commit": "08afb97ddae316b3b305354f1582afdb836d7633",
                "source_bundle_commit": "e5994fb28466e46c99a1f247494473e6cba9cc03",
                "contract_sha256": "5EDFE3AA67DB573730F0D095A72E8EAD3F9E49E5D2457B2982480F8FC068BDB9",
                "matrix_sha256": "021346D79CF0E01848C09ACC33A7D5854400B2DDB82BA10E1ADDF0DF049DCA0E",
                "root": "inputs/predecessor-before"},
}
SOURCE = "b56534d7b6c993c0795010d0404fb8a81f7eeb9d"
TOOLS = "Tools/acceptance/p44/"
DATA_REL = "docs/acceptance-contracts/P4-4-v4/evidence/"


def guard(value, root=ROOT):
    value = Path(os.path.abspath(value))
    value.relative_to(root)
    for part in (value, *value.parents):
        try:
            info = part.lstat()
        except FileNotFoundError:
            continue
        assert not stat.S_ISLNK(info.st_mode) and not getattr(info, "st_file_attributes", 0) & 0x400, "REPARSE_PATH"
    value.resolve().relative_to(root.resolve())
    return value


def sha(data):
    return hashlib.sha256(data).hexdigest()


def read(file):
    return json.loads(guard(file).read_bytes())


def write(file, value):
    file = guard(file)
    assert not file.exists(), "ORIGINAL_EXISTS"
    data = value if isinstance(value, bytes) else (json.dumps(value, indent=2, ensure_ascii=True) + "\n").encode()
    file.parent.mkdir(parents=True, exist_ok=True)
    with guard(file).open("xb") as stream:
        stream.write(data)
    return data


def ref(file, base=DATA):
    data = guard(file).read_bytes()
    return {"path": file.relative_to(base).as_posix(), "size_bytes": len(data), "sha256": sha(data)}


def git_bytes(*args):
    env = dict(os.environ, GIT_NO_LAZY_FETCH="1", GIT_OPTIONAL_LOCKS="0", GIT_TERMINAL_PROMPT="0")
    return subprocess.check_output(["git", "--no-optional-locks", "-c", "core.fsmonitor=false", *args], cwd=ROOT, env=env)


def git(*args):
    return git_bytes(*args).decode().strip()


def validator():
    spec = importlib.util.spec_from_file_location("p44_bundle_validator", ROOT / "Tools/acceptance/validate_bundle.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def inspector():
    spec = importlib.util.spec_from_file_location("p44_privacy_inspector", ROOT / TOOLS / "inspect.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def definitions():
    commands, artifacts, criteria = [], [], []

    def command(name, exe, args, groups, runners, description):
        commands.append({"id": name, "command": " ".join(["node", TOOLS + "run.cjs", name, exe, *args]),
                         "description": description, "input_groups": sorted(set(groups)),
                         "runner_paths": sorted(set([TOOLS + "run.cjs", *runners])),
                         "expected_exit_codes": [0, 1, 2], "success_exit_code": 0, "output_required": True})
        return name

    def capture(name, mode, groups=None):
        args = [TOOLS + "capture.cjs", mode]
        before_description = ""
        if mode == "before":
            args.append(PREDECESSOR)
            before_description = ("Review the direct v3 and inherited v2/v1 originals: consume 47 complete, exactly matching read-only responses "
                                  "without network replay, including legacy LIMIT 500 and LIMIT 8 pages. "
                                  "Retain both partial responses and the pre-response connection failure; collect only unfinished rows with LIMIT 8. ")
        return command(name, "node", args, groups or ["cloudflare", "capture"],
                       [TOOLS + "capture.cjs"], "Raw capture under the fixed P4-4 plan; one invocation; Undici HTTP <=60s, standard gh archive <=180s, wrapper watchdog <=60 minutes; "
                       "complete bounded pages; fixed D1 POST queries use standard gzip negotiation and strictly bounded decoding, preserving wire and decoded originals, "
                       "with unsafe/incomplete new compressed wire retained privately and publicly identified only by hash/size. "
                       "Only capture-admitted GET and fixed D1 SELECT POST may retry request() pre-response ECONNRESET once, "
                       "after an abortable 500ms wait within the same 60s signal; retain each failure and retry reservation. "
                       "No retry after an HTTP response, during body collection, for other errors, private verification or business writes. "
                       + before_description + "Only two planned staging dispatches; never approve/reject by API, "
                       "publish, register directly, upload/delete objects, migrate, unlock gates or operate devices. "
                       "Waiting/discovery reads are bounded, not repeated business operations. Uncertain mutations are not retried.")

    def offline(name, script, mode, manifest, output, groups, runners=()):
        return command(name, "python", ["-I", "-S", "-B", TOOLS + script, mode, "--repo-root", ROOT.as_posix(),
                       "--input", DATA_REL + manifest, "--output", DATA_REL + output], groups,
                       [TOOLS + script, *runners], "Offline independent evaluation of hash-bound original bytes; "
                       "not a repeated CI/build/cloud/device operation. Wrapper watchdog <=60 minutes; preserve failures.")

    def criterion(name, ids, paths, description, kind="functional", external=("target", "host")):
        groups = sorted({g for cmd in commands if cmd["id"] in ids for g in cmd["input_groups"]})
        artifact_ids = []
        for index, file in enumerate(paths):
            aid = name + "-" + str(index + 1)
            artifacts.append({"id": aid, "description": description, "path": "evidence/" + file})
            artifact_ids.append(aid)
        criteria.append({"id": name, "description": description, "required": True, "kind": kind,
                         "evidence_types": ["raw_log"], "input_groups": groups,
                         "dependency_rationale": "Only listed dependencies apply: Firmware supplies GCC/key inputs; P41Release supplies "
                         "workflow/build/packing; Cloudflare supplies fixed Worker/schema/S3 consumers and locked SDK inputs; "
                         "P44Capture supplies raw HTTP/process capture. Evidence/P41Evaluation supply offline interpretation, "
                         "Validation supplies the original host test inputs, Governance supplies configuration/authority criteria. "
                         "Raw capture and interpretation are separate criteria so parser changes do not authorize replay.",
                         "external_inputs": list(external),
                         "command_ids": ids, "artifact_ids": artifact_ids,
                         "gate": {"type": "boolean", "basis": "frozen_requirement", "expected": True}})

    history = offline("formal-history", "origins.py", "history", "inputs/originals.json", "history-result.json",
                      ["firmware", "release", "cloudflare", "validation", "evidence", "governance"],
                      ["Tools/acceptance/validate_bundle.py"])
    criterion("P44-HISTORY", [history], ["history-result.json"],
              "Independently interpret unchanged-source original CI, host negative/redaction and remediation evidence; retain original failures and advisories.",
              external=("originals", "host"))
    config = offline("formal-configuration", "origins.py", "configuration", "inputs/originals.json", "configuration-result.json",
                     ["release", "cloudflare", "evidence", "governance"], ["Tools/acceptance/validate_bundle.py"])
    criterion("P44-CONFIGURATION", [config], ["configuration-result.json"],
              "Correct names/types/scopes, exact independent bucket policies, retained reviewer/gates and verified ACL correction; "
              "original deployed modules match the source-bound CI artifact and exact Worker versions/DB/R2/settings. "
              "Historical deployment observations and secret presence are not continuous monitoring or production workflow execution.",
              external=("originals", "host"))
    before = capture("formal-before", "before")
    negatives = capture("formal-negatives", "negatives")
    dispatch_a = capture("formal-dispatch-a", "dispatch-a", ["firmware", "release", "cloudflare", "capture"])
    finish_a = capture("formal-finish-a", "finish-a", ["firmware", "release", "cloudflare", "capture"])
    dispatch_b = capture("formal-dispatch-b", "dispatch-b", ["firmware", "release", "cloudflare", "capture"])
    finish_b = capture("formal-finish-b", "finish-b", ["firmware", "release", "cloudflare", "capture"])
    criterion("P44-RAW-RUNS", [dispatch_a, finish_a, dispatch_b, finish_b],
              ["run-a/final.json", "run-b/final.json", "artifact.json", "run-a/logs.json", "run-b/logs.json"],
              "Two distinct same-source attempt-1 runs: A actually rejected and terminal before B; B actually approved and successful. "
              "Capture original waiting, reviews, complete jobs and artifact. No proxy action. Run A cannot be rerun; old-chain rehearsal is not new-chain qualification.",
              external=("target", "bootstrap-app", "bootstrap-proof", "host"))
    assemble1 = capture("formal-assemble-rehearsal", "assemble", ["evidence"])
    rehearsal = offline("formal-rehearsal", "inspect.py", "rehearsal", "rehearsal-manifest.json", "rehearsal-result.json",
                        ["firmware", "release", "cloudflare", "evidence", "legacy-evaluation"],
                        ["docs/acceptance-contracts/P4-1-v2/tools/inspect.py", "Tools/jlink/prepare-bootstrap-app.py"])
    criterion("P44-REHEARSAL", [assemble1, rehearsal], ["rehearsal-result.json", "rehearsal-manifest.json"],
              "One new shared S3/preflight staging chain consumes protected inputs, verifies all GCC/pack/recovery bytes, "
              "three immutable uploads/full readbacks, ready registration and exactly one idempotent replay.",
              external=("target", "bootstrap-app", "bootstrap-proof", "host"))
    readbacks = capture("formal-readbacks", "readbacks", ["cloudflare", "capture", "evidence"])
    production = capture("formal-production-preflight", "production-preflight", ["cloudflare", "capture", "evidence"])
    after = capture("formal-after", "after")
    criterion("P44-RAW-STATE", [before, negatives, after],
              ["snapshots/before.json", "negatives.json", "snapshots/after.json"],
              "Bounded original three-resource SELECT/list captures. Before independently reviews 47 complete v1/v2/v3 originals "
              "(legacy LIMIT 500 and LIMIT 8 pages) with no network replay, then collects unfinished rows with fixed LIMIT 8 pages; "
              "after uses entirely new LIMIT 8 pages. Standard gzip, bounded wire/decoded originals and the unchanged 60-second deadline "
              "address the documented large-response transport failure; a public gzip probe is not D1 acceptance. "
              "Capture-admitted read-only pre-response ECONNRESET has at most one recorded retry after 500ms abortable wait "
              "under the original 60s signal; response/body errors and mutations are never retried. "
              "Three actual missing/cross-Worker 401s and two cross-bucket 403s. "
              "No production object write, register, channel mutation, Release or device action; no incomplete predecessor criterion is REUSED.",
              external=("target", "host", "predecessor-before"))
    criterion("P44-RAW-READBACK", [readbacks, production], ["readbacks.json", "production-preflight-result.json"],
              "Three immutable GET bodies and one correct production SELECT-only preflight use the validated artifact metadata. "
              "Evidence dependency reflects the actual parser-produced metadata; any affected recapture remains read-only, not another workflow.")
    assemble2 = capture("formal-assemble-complete", "assemble", ["evidence"])
    approvals = offline("formal-approvals", "inspect.py", "approvals", "manifest.json", "approvals-result.json", ["release", "evidence"])
    criterion("P44-APPROVALS", [assemble2, approvals], ["approvals-result.json", "reviewer-attestation.json"],
              "Independently bind waiting/rejection/approval actor/environment/steps and original human-action provenance. "
              "GitHub login alone does not prove a human click; root must adjudicate actual owner response or witnessed dashboard action.")
    states = offline("formal-states", "inspect.py", "states", "manifest.json", "states-result.json", ["release", "cloudflare", "evidence"])
    criterion("P44-ISOLATION", [states], ["states-result.json"],
              "Production and protected Trace D1/schema/channel/R2 and GitHub Releases/assets unchanged; staging adds only this candidate, "
              "three assets/objects and one exact registration audit. Complete byte readbacks match; before/after times bracket B, not continuous monitoring.")
    privacy = command("formal-privacy", "python", ["-I", "-S", "-B", TOOLS + "bundle.py", "privacy"],
                      ["evidence", "governance"], [TOOLS + "bundle.py", TOOLS + "inspect.py"],
                      "Offline exact-known-secret and signed-URL scan of public bundle text and ZIP members; compressed D1 wire/decoded pairs "
                      "use the same strict inspection oracle before decoded-byte scanning. Incomplete compressed wire stays private. "
                      "Explicit ownership/rotation/revocation record; no key generation or rotation.")
    criterion("P44-HYGIENE", [privacy], ["privacy-result.json", "inputs/lifecycle.json"],
              "No known credential values in public outputs; no claim of never-exposed local ACLs. Owner, operator-enforced deadline, "
              "safe replacement/revocation and temporary-management-source identity are recorded; no provider TTL or automation is fabricated.", "process")
    criteria[-1]["external_inputs"] = ["lifecycle", "originals", "host"]
    return commands, artifacts, criteria


def base_contract():
    value = read(ROOT / "docs/acceptance-contracts/template.contract.json")
    commands, artifacts, criteria = definitions()
    value.update(contract_id="P4-4-v4", version=4, task_id="P4-4", parent_contract_sha256=PREVIOUS_SHA256,
                 commands=commands, artifacts=artifacts, criteria=criteria)
    value["input_groups"] += [{"id": name, "profile": profile, "category": category} for name, profile, category in [
        ("firmware", "Firmware", "production_source"), ("release", "P41Release", "production_source"),
        ("cloudflare", "Cloudflare", "production_source"), ("capture", "P44Capture", "validation_inputs"),
        ("evidence", "Evidence", "validation_inputs"), ("legacy-evaluation", "P41Evaluation", "validation_inputs")]]
    value["external_inputs"] = []
    return value


def inventory_selection(inventory, role, expected=None):
    rows = inventory["entries" if role == "deployment" else "files"]
    assert isinstance(rows, list), "INVENTORY_ROWS"
    if expected is not None:
        rows = [item for item in rows if item["path"] in expected]
        assert len(rows) == len(expected) and {item["path"] for item in rows} == expected, "INVENTORY_SELECTION"
    return rows


def history_reference(root, reference):
    assert set(reference) == {"path", "size_bytes", "sha256"}, "INHERITED_REFERENCE"
    file = guard(root / reference["path"], root)
    assert reference["path"] == file.relative_to(root).as_posix(), "INHERITED_REFERENCE_PATH"
    raw = file.read_bytes()
    assert len(raw) == reference["size_bytes"] and sha(raw) == reference["sha256"], "INHERITED_REFERENCE_BYTES"
    return raw


def history_layers(contract, data):
    assert contract["version"] in (2, 3, 4) and contract["contract_id"] == "P4-4-v" + str(contract["version"]), "HISTORY_SCOPE"
    rules, frames, container, current, link = validator(), [], guard(data), contract, None
    for version in range(contract["version"] - 1, 0, -1):
        identity = "P4-4-v" + str(version)
        expected = HISTORY[identity]
        manifest_file = guard(container / PREDECESSOR, container)
        raw = manifest_file.read_bytes()
        anchors = [item for item in current["external_inputs"] if item["id"] == "predecessor-before"]
        assert len(anchors) == 1 and anchors[0]["evidence_path"] == "evidence/" + PREDECESSOR, "INHERITED_ANCHOR"
        assert anchors[0]["evidence_sha256"].upper() == sha(raw).upper(), "INHERITED_ANCHOR_HASH"
        assert anchors[0]["fingerprint"] == "sha256:" + sha(raw), "INHERITED_FINGERPRINT"
        if link is not None:
            assert link["path"] == PREDECESSOR and history_reference(container, link) == raw, "INHERITED_MANIFEST_LINK"
        manifest = json.loads(raw)
        assert manifest["schema"] == "p44-predecessor-before-v1" and manifest["predecessor_contract_id"] == identity, "INHERITED_IDENTITY"
        assert manifest["source_evidence_root"] == expected["root"], "INHERITED_ROOT"
        assert all(manifest[field] == expected[field] for field in ("source_commit", "source_bundle_commit")), "INHERITED_SOURCE"
        root = guard(container / expected["root"], container)
        ancestor_raw = history_reference(root, manifest["predecessor_contract"])
        matrix_raw = history_reference(root, manifest["predecessor_final_matrix"])
        assert sha(ancestor_raw).upper() == expected["contract_sha256"] == current["parent_contract_sha256"].upper(), "INHERITED_PARENT_HASH"
        assert manifest["predecessor_contract_sha256"].upper() == expected["contract_sha256"], "INHERITED_CONTRACT_HASH"
        assert sha(matrix_raw).upper() == expected["matrix_sha256"], "INHERITED_MATRIX_HASH"
        ancestor, matrix = json.loads(ancestor_raw), json.loads(matrix_raw)
        assert ancestor["contract_id"] == identity and ancestor["freeze_commit"] == expected["source_commit"], "INHERITED_SOURCE"
        assert not rules.validate_contract(ancestor), "INHERITED_CONTRACT_INVALID"
        assert not rules.validate_matrix(matrix, ancestor, expected["contract_sha256"]), "INHERITED_MATRIX_INVALID"
        assert matrix["overall_result"] == "EVIDENCE_GAP", "INHERITED_RESULT_CHANGED"
        git("merge-base", "--is-ancestor", expected["source_commit"], expected["source_bundle_commit"])
        git("merge-base", "--is-ancestor", expected["source_bundle_commit"], current["freeze_commit"])
        for reference in manifest["files"]:
            history_reference(root, reference)
        frames.append({"root": root, "manifest": manifest, "contract": ancestor})
        link = manifest.get("inherited_predecessor")
        assert (link is None) == (version == 1), "INHERITED_DEPTH"
        container, current = root, ancestor
    return frames


def predecessor_plan():
    previous_raw = guard(PREVIOUS_CONTRACT).read_bytes()
    matrix_raw = guard(PREVIOUS_MATRIX).read_bytes()
    assert sha(previous_raw).upper() == PREVIOUS_SHA256, "PREDECESSOR_CONTRACT_CHANGED"
    assert sha(matrix_raw).upper() == PREVIOUS_MATRIX_SHA256, "PREDECESSOR_MATRIX_CHANGED"
    previous, matrix = json.loads(previous_raw), json.loads(matrix_raw)
    assert previous["contract_id"] == "P4-4-v3" and previous["freeze_commit"] == PREVIOUS_SOURCE
    assert matrix["overall_result"] == "EVIDENCE_GAP", "PREDECESSOR_RESULT_CHANGED"
    rules = validator()
    assert not rules.validate_contract(previous), "PREDECESSOR_CONTRACT_INVALID"
    assert not rules.validate_matrix(matrix, previous, PREVIOUS_SHA256), "PREDECESSOR_MATRIX_INVALID"
    git("merge-base", "--is-ancestor", PREVIOUS_SOURCE, PREVIOUS_BUNDLE)
    git("merge-base", "--is-ancestor", PREVIOUS_BUNDLE, "HEAD")
    for file, raw in ((PREVIOUS_CONTRACT, previous_raw), (PREVIOUS_MATRIX, matrix_raw)):
        assert git_bytes("show", PREVIOUS_BUNDLE + ":" + file.relative_to(ROOT).as_posix()) == raw, "PREDECESSOR_GIT_BYTES"
    base = PREVIOUS / "evidence"
    files = sorted(file for file in guard(base / "snapshots/before").rglob("*") if file.is_file())
    assert files, "PREDECESSOR_SNAPSHOTS_MISSING"
    files += [base / "commands/formal-before.json", base / "commands/formal-before.log", base / "failure-report.json"]
    inherited_file = guard(base / PREDECESSOR)
    inherited_root = history_layers(previous, base)[0]["root"]
    files += [inherited_file, *sorted(file for file in inherited_root.rglob("*") if file.is_file())]
    references = []
    for file in files:
        item = ref(file, base)
        assert matrix["evidence_hashes"]["evidence/" + item["path"]].upper() == item["sha256"].upper(), "PREDECESSOR_EVIDENCE_CHANGED"
        references.append(item)
    receipt = read(base / "commands/formal-before.json")
    assert receipt["label"] == "formal-before" and receipt["exitCode"] == 1 and receipt["process_closed"] is True
    target = DATA / PREDECESSOR_ROOT
    planned = [(source, target / source.relative_to(base)) for source in files]
    planned += [(PREVIOUS_CONTRACT, target / "predecessor.contract.json"),
                (PREVIOUS_MATRIX, target / "predecessor.final-evidence-matrix.json")]
    manifest = {"schema": "p44-predecessor-before-v1", "predecessor_contract_id": "P4-4-v3",
                "predecessor_contract_sha256": PREVIOUS_SHA256, "source_commit": PREVIOUS_SOURCE,
                "source_bundle_commit": PREVIOUS_BUNDLE, "source_evidence_root": PREDECESSOR_ROOT,
                "predecessor_contract": {"path": "predecessor.contract.json", "size_bytes": len(previous_raw), "sha256": sha(previous_raw)},
                "predecessor_final_matrix": {"path": "predecessor.final-evidence-matrix.json", "size_bytes": len(matrix_raw), "sha256": sha(matrix_raw)},
                "inherited_predecessor": ref(inherited_file, base),
                "files": references}
    return planned, manifest


def initial_matrix(contract, digest):
    matrix = read(ROOT / "docs/acceptance-contracts/template.evidence-matrix.json")
    template = matrix["criteria"][0]
    matrix.update(contract_id=contract["contract_id"], contract_sha256=digest.upper(), round_id="P44-20261020-04",
                  criteria=[{**copy.deepcopy(template), "id": item["id"],
                             "notes": "NOT_RUN under the v4 plan; all three actual predecessor failures remain recorded; history and quotas are not reset by the date change"}
                            for item in contract["criteria"]])
    return matrix


def validation_commands():
    common = ["python", "-I", "-S", "-B", "Tools/acceptance/validate_bundle.py", "--contract", CONTRACT.relative_to(ROOT).as_posix(),
              "--repo-root", ROOT.as_posix(), "--previous-contract", PREVIOUS_CONTRACT.relative_to(ROOT).as_posix(),
              "--previous-matrix", PREVIOUS_MATRIX.relative_to(ROOT).as_posix()]
    initial = [*common, "--matrix", (PACKAGE / "evidence-matrix.json").relative_to(ROOT).as_posix()]
    final = [*common, "--matrix", (PACKAGE / "final-evidence-matrix.json").relative_to(ROOT).as_posix()]
    return {"precheck": " ".join(initial), "plan": " ".join([*initial, "--write-rerun-plan", "rerun-plan.json"]),
            "final": " ".join(final)}


def computed_plan(contract, matrix):
    return validator().compute_rerun_plan(
        contract, read(PREVIOUS_CONTRACT), read(PREVIOUS_MATRIX),
        current_contract_sha256=sha(guard(CONTRACT).read_bytes()).upper(),
        previous_contract_sha256=PREVIOUS_SHA256, previous_matrix_sha256=PREVIOUS_MATRIX_SHA256,
        current_round_id=matrix["round_id"], repo_root=ROOT)


def prepare():
    assert git("branch", "--show-current") == "dev/p4-4/config-integration-20261018"
    sources = [("history", "P4-4-s3-remediation-2026-10-19", "raw-output-inventory.json"),
               ("configuration", "P4-4-credential-handoff-2026-10-19-v2", "inventory.json"),
               ("deployment", "P4-4-root-review-2026-10-19", "raw-output-inventory.json")]
    spec = importlib.util.spec_from_file_location("p44_originals_selection", ROOT / TOOLS / "origins.py")
    originals = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(originals)
    planned, inventories = [], {}
    for role, folder, filename in sources:
        source = ROOT / "docs/ota-exec-notes" / folder
        inventory = read(source / filename)
        target = DATA / "inputs" / role
        inventories[role] = target / filename
        planned += [(source / filename, target / filename)]
        selected = inventory_selection(inventory, role, originals.DEPLOYMENT_FILES if role == "deployment" else None)
        planned += [(source / item["path"], target / item["path"]) for item in selected]
    for name in ("app-final.bin", "provenance.json"):
        planned.append((ROOT / "docs/ota-exec-notes/P4-1-bootstrap-baseline-2026-10-15" / name, DATA / "inputs/bootstrap" / name))
    assert len(planned) == 67, "ORIGINAL_INPUT_SCOPE"
    predecessor_files, predecessor = predecessor_plan()
    planned += predecessor_files
    for source, output in planned:
        guard(source); guard(output); assert source.is_file() and not output.exists()
    for name in ("originals.json", "lifecycle.json", "host.json"):
        assert not guard(DATA / "inputs" / name).exists()
    assert not guard(DATA / PREDECESSOR).exists()
    for source, output in planned:
        write(output, source.read_bytes())
    write(DATA / PREDECESSOR, predecessor)
    manifest = {"schema": "p44-originals-v1", "source_commit": SOURCE, "candidate_commit": git("rev-parse", "HEAD")}
    for role, inventory in inventories.items():
        manifest[role] = {"inventory": ref(inventory, DATA / "inputs")}
    write(DATA / "inputs/originals.json", manifest)
    write(DATA / "inputs/lifecycle.json", {"schema": "p44-lifecycle-v1", "owner": "Eitan-S-23", "gate": False,
          "decision_author": "Independent root under the user's explicit autonomous P4-4 delegation; not a reviewer action",
          "provider_expires_on": {"production": None, "rehearsal": None}, "provider_ttl_configured": False,
          "operator_review_rotation_deadline": {"production": "2027-01-17T07:40:38Z", "rehearsal": "2027-01-17T07:40:50Z"},
          "automatic_job_configured": False, "scope": "Bounded configuration/rehearsal; P5 promotion rechecks active scope, age and ownership",
          "rotation": "One environment at a time, same single bucket/two Item groups, install both new secret fields securely, verify authorized new run, then revoke old verified ID",
          "emergency": "Keep gate=false, disable the identified compromised token; preserve firmware objects and evidence",
          "temporary_management_id_sha256": "ec3e3b40801a2af2676d699686429cc49d1fea95afb328d8efb9ac519b31d666",
          "temporary_management": "Only actual supplied local source; not old token.txt or e-track-ci. Never export management authority to workflow",
          "historical_limits": ["Initial broad private ACL was repaired, not proof no one could read it",
                                "Initial public candidate projection omitted Track identifier redaction; retained in ignored cache and superseded by v2",
                                "No original initial-400 or historical gh-set/list receipts were supplied"]})
    modules = ROOT / "app/bluetooth_flutter_Trace/cloudflare/update-service/worker/node_modules"
    packages = {name: read(modules / name / "package.json")["version"] for name in ("undici", "@smithy/core", "@smithy/signature-v4", "@aws-sdk/client-s3")}
    write(DATA / "inputs/host.json", {"python": sys.version, "python_executable": sys.executable,
          "node": subprocess.check_output(["node", "--version"], cwd=ROOT).decode().strip(), "packages": packages,
          "transport": "Existing bounded Undici/OpenSSL proxy, standard gzip with strict bounded decoding, and AWS SigV4; no Schannel HTTP", "outputs": str(PACKAGE),
          "external_write_limit": "Selected-command/output audit only; prior external PowerShell/Schannel cache attribution remains unresolved"})
    print(json.dumps({"copied_files": len(planned), "original_inputs": 67, "predecessor_files": len(predecessor_files), "platform_operations": 0}))


def freeze():
    commit = git("rev-parse", "HEAD")
    assert read(DATA / "target.json")["commitSha"] == commit
    assert read(DATA / "inputs/originals.json")["candidate_commit"] == commit
    read(DATA / "configured.json")
    assert read(DATA / PREDECESSOR) == predecessor_plan()[1], "PREDECESSOR_MANIFEST_CHANGED"
    value = base_contract()
    value.update(status="FROZEN", approved_by="Independent Codex root; explicit owner delegation to finish P4-4 autonomously",
                 approved_at=datetime.now(timezone.utc).isoformat(), implementation_ref=SOURCE,
                 freeze_commit=commit, freeze_tree=git("rev-parse", "HEAD^{tree}"),
                 profile_config_blob=git("rev-parse", "HEAD:Tools/provenance/manifest_profiles.json"))
    for name, relative in [("target", "target.json"), ("originals", "inputs/originals.json"),
                           ("lifecycle", "inputs/lifecycle.json"), ("bootstrap-app", "inputs/bootstrap/app-final.bin"),
                           ("bootstrap-proof", "inputs/bootstrap/provenance.json"), ("host", "inputs/host.json"),
                           ("predecessor-before", PREDECESSOR)]:
        fingerprint = sha(guard(DATA / relative).read_bytes())
        value["external_inputs"].append({"id": name, "category": "environment" if name == "host" else "fixture",
            "description": "Hash-bound " + name + "; historical operations retain their original date/operator/source and limitations; no replay implied",
            "fingerprint": "sha256:" + fingerprint, "evidence_path": "evidence/" + relative, "evidence_sha256": fingerprint})
    errors = validator().validate_contract(value)
    assert not errors, "CONTRACT_SCHEMA"
    raw = write(CONTRACT, value)
    matrix = initial_matrix(value, sha(raw))
    assert not validator().validate_matrix(matrix, value, sha(raw).upper()), "MATRIX_SCHEMA"
    write(PACKAGE / "evidence-matrix.json", matrix)
    print(json.dumps({"contract_sha256": sha(raw).upper(), "freeze_commit": commit, "formal_executions": 0,
                      "commands": len(value["commands"]), "criteria": len(value["criteria"]),
                      "validation_commands": validation_commands(),
                      "sealing_logs": "Run assess/final validation through the existing .cache/p44-run.cjs adapter, outside evidence DATA"}))


def contains_secret(data, needles):
    return any(value and value in data for value in needles) or bool(re.search(
        rb"(?:gh[posur]_|github_pat_)[A-Za-z0-9_]{20,}|https://[^\s\"<>]+[?&](?:X-Amz-Signature|token|signature|jwt)=[^\s\"<>]+", data))


def public_d1_decoded(record, inspection, context):
    routes = {"/accounts/[ACCOUNT]/d1/database/" + database + "/query" for database, _ in inspection.RESOURCES.values()}
    if record.get("method") != "POST" or record.get("path") not in routes:
        return None
    headers = record.get("response_headers", {})
    encodings = [value.strip().lower() for name, value in headers.items() if name.lower() == "content-encoding"]
    if record.get("decoded_body") is None and (not encodings or encodings == ["identity"]):
        return None
    if record.get("completed") is False:
        assert record.get("body") is None and record.get("decoded_body") is None, "COMPRESSED_FAILURE_MUST_BE_PRIVATE"
        return None
    return context.response(record, "POST", record["path"], status=record["status"])


def privacy_contexts(inspection, contract, data):
    roots = [guard(data), *(frame["root"] for frame in history_layers(contract, data))]
    return {root: inspection.Context(ROOT, root / "manifest.json") for root in roots}


def select_privacy_context(file, contexts):
    file = guard(file)
    for root in sorted(contexts, key=lambda value: len(value.parts), reverse=True):
        try:
            file.relative_to(root)
        except ValueError:
            continue
        return contexts[root]
    raise AssertionError("PRIVACY_CONTEXT_OUTSIDE_BOUND_ROOTS")


def privacy():
    project = ROOT.parents[1]
    needles = set()
    sources = ["app/bluetooth_flutter_Trace/cloudflare/update-service/.github-actions-secrets.staging.local.json",
               ".cache/p44-cred-20261019/private/p44-s3-credentials-20261019.json",
               ".cache/p4-4-integration-20261018/.cache/p44/private/production-secrets.json",
               ".cache/p41-dev-20261015/.cache/cf-auth-input/firmware-test-secrets.json",
               ".cache/p41-dev-20261015/.cache/cf-auth-input/p41-rehearsal-ota-key.json"]
    secret_fields = {"cloudflare_account_id", "cloudflare_api_token", "ota_aes_key", "trace_deploy_token", "download_hmac_key_current",
                     "download_hmac_key_previous", "token_id_access_key_id", "token_value", "secret_access_key_sha256", "keyhex"}
    def collect(value):
        if isinstance(value, dict):
            for key, item in value.items():
                if isinstance(item, str) and len(item) >= 16 and key.lower() in secret_fields:
                    needles.add(item.encode())
                collect(item)
        elif isinstance(value, list):
            for item in value:
                collect(item)
    for relative in sources:
        collect(json.loads(guard(project / relative, project).read_bytes()))
    for name in ("token.txt", "p41-ci-token.txt"):
        needles.add(guard(project / ".cache/p41-dev-20261015/.cache/cf-auth-input" / name, project).read_bytes().strip())
    directory = json.loads(guard(project / ".cache/p44-root-acceptance-20261019/private/credential-readback-01/03.json", project).read_bytes())
    for token in directory["result"]:
        assert re.fullmatch(r"[0-9a-f]{32}", token["id"])
        needles.add(token["id"].encode())
    env = dict(os.environ, GH_CONFIG_DIR="C:/Users/SU/AppData/Roaming/GitHub CLI", GH_TOKEN="", GITHUB_TOKEN="",
               GH_NO_UPDATE_NOTIFIER="1", GH_NO_EXTENSION_UPDATE_NOTIFIER="1", GH_PROMPT_DISABLED="1")
    auth = subprocess.run(["gh", "auth", "token", "--hostname", "github.com", "--user", "Eitan-S-23"],
                          cwd=ROOT, env=env, stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=30)
    assert auth.returncode == 0 and auth.stdout.strip(), "LOCAL_GITHUB_AUTH_UNAVAILABLE"
    needles.add(auth.stdout.strip())
    for value in list(needles):
        needles.add(base64.b64encode(value))
    assert all(needles), "EMPTY_SECRET_SENTINEL"
    lifecycle = read(DATA / "inputs/lifecycle.json")
    assert lifecycle["owner"] == "Eitan-S-23" and lifecycle["gate"] is False
    assert lifecycle["provider_expires_on"] == {"production": None, "rehearsal": None}
    assert lifecycle["provider_ttl_configured"] is False and lifecycle["automatic_job_configured"] is False
    assert lifecycle["operator_review_rotation_deadline"] == {"production": "2027-01-17T07:40:38Z", "rehearsal": "2027-01-17T07:40:50Z"}
    assert all(lifecycle[key] for key in ("decision_author", "rotation", "emergency", "temporary_management"))
    inspection = inspector()
    contexts = privacy_contexts(inspection, read(CONTRACT), DATA)
    files, members, decoded_d1, failures = 0, 0, 0, []
    excluded = {DATA / "commands/formal-privacy.log", DATA / "commands/formal-privacy.json", DATA / "privacy-result.json"}
    for file in sorted(DATA.rglob("*")):
        guard(file)
        if not file.is_file() or file in excluded:
            continue
        files += 1
        if contains_secret(file.read_bytes(), needles):
            failures.append(file.relative_to(DATA).as_posix())
        if file.name.endswith(".http.json"):
            decoded = public_d1_decoded(read(file), inspection, select_privacy_context(file, contexts))
            if decoded is not None:
                decoded_d1 += 1
                if contains_secret(decoded, needles):
                    failures.append(file.relative_to(DATA).as_posix() + "::decoded_body")
        if file.suffix == ".zip":
            with zipfile.ZipFile(file) as archive:
                assert len(archive.infolist()) <= 1024 and sum(item.file_size for item in archive.infolist()) <= 256 * 1024 * 1024
                for item in archive.infolist():
                    if not item.is_dir():
                        members += 1
                        if contains_secret(archive.read(item), needles):
                            failures.append(file.relative_to(DATA).as_posix() + "::" + item.filename)
    result = {"ok": not failures, "files_scanned": files, "zip_members_scanned": members, "decoded_d1_scanned": decoded_d1, "known_secret_forms": len(needles),
              "failed_paths": failures, "lifecycle_checked": True, "platform_operations": 0,
              "limits": "Known values/encodings, verified compressed D1 decoded bytes and signed-URL patterns; private failed wire is not published or scanned here; not proof of never-exposure or arbitrary unknown-secret detection"}
    write(DATA / "privacy-result.json", result)
    assert result["ok"], "PUBLIC_SECRET_FOUND"
    print(json.dumps({key: result[key] for key in ("ok", "files_scanned", "zip_members_scanned", "decoded_d1_scanned", "lifecycle_checked")}))


def assess():
    contract, matrix = read(CONTRACT), read(PACKAGE / "evidence-matrix.json")
    assert matrix["overall_result"] == "NOT_RUN", "FINAL_RESULT_IMMUTABLE"
    rules = validator()
    digest = sha(guard(CONTRACT).read_bytes()).upper()
    assert not rules.validate_matrix(matrix, contract, digest), "INITIAL_MATRIX_INVALID"
    assert read(DATA / PREDECESSOR) == predecessor_plan()[1], "PREDECESSOR_MANIFEST_CHANGED"
    plan = read(PACKAGE / "rerun-plan.json")
    assert plan == computed_plan(contract, matrix), "RERUN_PLAN_MISMATCH"
    assert not plan["reusable_criteria"], "UNEXPECTED_REUSE_REQUIRES_ADJUDICATION"
    assert set(plan["required_commands"]) == {item["id"] for item in contract["commands"]}, "COMMAND_PLAN_MISMATCH"
    results = {"P44-HISTORY": read(DATA / "history-result.json")["ok"],
               "P44-CONFIGURATION": read(DATA / "configuration-result.json")["ok"],
               "P44-REHEARSAL": read(DATA / "rehearsal-result.json")["ok"],
               "P44-APPROVALS": read(DATA / "approvals-result.json")["ok"],
               "P44-ISOLATION": read(DATA / "states-result.json")["ok"],
               "P44-HYGIENE": read(DATA / "privacy-result.json")["ok"]}
    results["P44-RAW-RUNS"] = read(DATA / "run-a/final.json")["run"]["conclusion"] == "failure" and read(DATA / "run-b/final.json")["run"]["conclusion"] == "success"
    results["P44-RAW-STATE"] = read(DATA / "negatives.json")["ok"] and all(set(read(DATA / "snapshots" / (phase + ".json"))["databases"]) == {"production", "protected", "staging"} for phase in ("before", "after"))
    results["P44-RAW-READBACK"] = read(DATA / "production-preflight-result.json")["ok"] and len(read(DATA / "readbacks.json")) == 3
    for command in contract["commands"]:
        receipt = read(DATA / "commands" / (command["id"] + ".json"))
        actual = " ".join(["node", TOOLS + "run.cjs", command["id"], receipt["command"], *receipt["args"]])
        assert actual == command["command"] and Path(receipt["cwd"]) == ROOT and receipt["process_closed"] is True
        assert receipt["exitCode"] == 0, "COMMAND_NOT_SUCCESSFUL"
        matrix["commands"].append({"id": command["id"], "command": actual, "exit_code": receipt["exitCode"],
                                   "output_evidence": "evidence/commands/" + command["id"] + ".log"})
    for artifact in contract["artifacts"]:
        file = guard(PACKAGE / artifact["path"])
        matrix["artifacts"].append({"id": artifact["id"], "path": artifact["path"], "size": file.stat().st_size, "sha256": sha(file.read_bytes())})
    assert all(results.values()), "ADJUDICATION_REQUIRED_FOR_FAILURE"
    for item in matrix["criteria"]:
        item.update(result="PASS", observed=True, failure_owner=None,
                    evidence=[artifact["path"] for artifact in contract["artifacts"] if artifact["id"] in next(c for c in contract["criteria"] if c["id"] == item["id"])["artifact_ids"]],
                    notes="Independent original-byte adjudication; no production release/P5/gate unlock. Human reviewer provenance separately witnessed by root.")
        if item["id"] == "P44-RAW-STATE":
            item["evidence"].append("rerun-plan.json")
            item["notes"] += " The actual v3 and inherited v2/v1 EVIDENCE_GAP rounds, both incomplete streams and the connection failure remain bound by predecessor-before; this is not a REUSED criterion."
    matrix["evidence_hashes"] = {file.relative_to(PACKAGE).as_posix(): sha(guard(file).read_bytes()) for file in DATA.rglob("*") if file.is_file()}
    matrix["evidence_hashes"]["rerun-plan.json"] = sha(guard(PACKAGE / "rerun-plan.json").read_bytes())
    matrix["overall_result"] = "PASS"
    assert all(matrix[field] is None for field in ("previous_matrix_sha256", "rerun_plan_path", "rerun_plan_sha256")), "NONREUSE_BINDING_FIELDS"
    assert not rules.validate_matrix(matrix, contract, digest), "FINAL_MATRIX_INVALID"
    assert not rules.validate_planned_execution(matrix, contract, plan), "UNPLANNED_EXECUTION"
    write(PACKAGE / "final-evidence-matrix.json", matrix)
    print(json.dumps({"overall_result": "PASS", "criteria": len(results), "previous_contract_sha256": PREVIOUS_SHA256,
                      "previous_matrix_sha256": PREVIOUS_MATRIX_SHA256, "rerun_plan_sha256": matrix["evidence_hashes"]["rerun-plan.json"],
                      "final_validation_command": validation_commands()["final"], "final_validation_log": "Outside evidence DATA"}))


def selftest():
    import gzip

    value = base_contract()
    value["external_inputs"] = [{"id": name, "category": "fixture", "description": "Offline schema fixture", "fingerprint": "sha256:" + "0" * 64,
                                 "evidence_path": name + ".json", "evidence_sha256": "0" * 64}
                                for name in ("target", "originals", "lifecycle", "bootstrap-app", "bootstrap-proof", "host", "predecessor-before")]
    rules = validator()
    errors = rules.validate_contract(value, allow_draft=True)
    assert not errors, "CONTRACT_SCHEMA"
    invalid = copy.deepcopy(value)
    invalid["criteria"][0]["input_groups"].remove("evidence")
    assert rules.validate_contract(invalid, allow_draft=True), "OMITTED_DEPENDENCY_ACCEPTED"
    digest = sha(b"v4 contract fixture")
    matrix = initial_matrix(value, digest)
    assert not rules.validate_matrix(matrix, value, digest.upper()), "MATRIX_UPPERCASE_REJECTED"
    invalid_matrix = copy.deepcopy(matrix)
    invalid_matrix["contract_sha256"] = digest.lower()
    assert rules.validate_matrix(invalid_matrix, value, digest.upper()) == ["matrix.contract_sha256 does not match the contract file"], "LOWERCASE_REGRESSION_NOT_REPRODUCED"
    invalid_matrix["contract_sha256"] = "0" * 64
    assert rules.validate_matrix(invalid_matrix, value, digest.upper()), "WRONG_MATRIX_DIGEST_ACCEPTED"
    assert contains_secret(b"fixture-secret", {b"fixture-secret"}) and not contains_secret(b"clean", {b"fixture-secret"})
    assert contains_secret(b"https://example.invalid/?X-Amz-Signature=signed", set())
    assert contains_secret(b"ghs_" + b"A" * 36, set()) and not contains_secret(b"ghs_ token type", set())
    inspection = inspector()
    context = inspection.Context(ROOT, ROOT / ".cache/p44/privacy-memory.json")
    plain = b'{"message":"fixture-secret"}'
    memory = {"wire.body": gzip.compress(plain, mtime=0), "decoded.body": plain, "wrong.body": b'{"message":"wrong"}'}

    def memory_ref(name):
        return {"path": name, "size_bytes": len(memory[name]), "sha256": sha(memory[name])}

    def memory_read(reference):
        data = memory[reference["path"]]
        assert reference == memory_ref(reference["path"])
        return data

    context.read = memory_read
    record = {"method": "POST", "path": "/accounts/[ACCOUNT]/d1/database/" + inspection.RESOURCES["production"][0] + "/query",
              "status": 200, "completed": True, "started": "2026-10-19T08:00:00Z", "ended": "2026-10-19T08:00:01Z",
              "response_headers": {"content-encoding": "gzip", "content-length": str(len(memory["wire.body"]))},
              "body": memory_ref("wire.body"), "decoded_body": memory_ref("decoded.body")}
    decoded = public_d1_decoded(record, inspection, context)
    assert decoded == plain, "PRIVACY_GZIP_NOT_DECODED"
    assert contains_secret(decoded, {b"fixture-secret"}), "COMPRESSED_SECRET_IGNORED"
    wrong = copy.deepcopy(record)
    wrong["decoded_body"] = memory_ref("wrong.body")
    rejected = False
    try:
        public_d1_decoded(wrong, inspection, context)
    except inspection.EvidenceError:
        rejected = True
    assert rejected, "PRIVACY_SIDECAR_MISMATCH_ACCEPTED"
    partial = copy.deepcopy(record)
    partial["completed"] = False
    rejected = False
    try:
        public_d1_decoded(partial, inspection, context)
    except AssertionError:
        rejected = True
    assert rejected, "PUBLIC_PARTIAL_COMPRESSED_WIRE_ACCEPTED"
    partial.pop("body")
    partial.pop("decoded_body")
    assert public_d1_decoded(partial, inspection, context) is None, "PRIVATE_PARTIAL_REFERENCE_READ"
    offline_commands = [item for item in value["commands"] if "--repo-root" in item["command"]]
    assert len(offline_commands) == 5 and all("--repo-root " + ROOT.as_posix() + " " in item["command"] for item in offline_commands)
    assert len(value["commands"]) == 17 and len(value["criteria"]) == 9, "FORMAL_SCOPE_CHANGED"
    assert next(item for item in value["commands"] if item["id"] == "formal-before")["command"].endswith(" before " + PREDECESSOR)
    assert [item["id"] for item in value["criteria"] if "predecessor-before" in item["external_inputs"]] == ["P44-RAW-STATE"]
    assert TOOLS + "inspect.py" in next(item for item in value["commands"] if item["id"] == "formal-privacy")["runner_paths"]
    for command in validation_commands().values():
        assert "--previous-contract " + PREVIOUS_CONTRACT.relative_to(ROOT).as_posix() in command
        assert "--previous-matrix " + PREVIOUS_MATRIX.relative_to(ROOT).as_posix() in command
    fixture = [{"path": "selected"}, {"path": "not-selected"}]
    assert inventory_selection({"files": fixture}, "history") == fixture
    assert inventory_selection({"entries": fixture}, "deployment", {"selected"}) == fixture[:1]
    rejected = False
    try:
        inventory_selection({"entries": fixture}, "deployment", {"missing"})
    except AssertionError:
        rejected = True
    assert rejected, "MISSING_DEPLOYMENT_ORIGINAL_ACCEPTED"
    predecessor_files, predecessor = predecessor_plan()
    envelopes = [read(source) for source, _ in predecessor_files if source.name.endswith(".http.json")]
    assert len(envelopes) == 50 and sum(item.get("completed") is True for item in envelopes) == 47
    assert sum(item.get("completed") is False for item in envelopes) == 3, "FAILED_PREDECESSOR_LOST"
    assert predecessor["inherited_predecessor"]["path"] == PREDECESSOR, "INHERITED_MANIFEST_PATH"
    assert predecessor["source_evidence_root"] == PREDECESSOR_ROOT == "p", "PREDECESSOR_PATH_SCOPE"
    assert max(len(str(destination)) for _, destination in predecessor_files) == 239, "PREDECESSOR_PATH_LENGTH"
    previous, previous_matrix = read(PREVIOUS_CONTRACT), read(PREVIOUS_MATRIX)
    previous_errors = rules._physical_errors(previous, previous_matrix, PREVIOUS, ROOT)
    assert not previous_errors, "PREDECESSOR_PHYSICAL_VALIDATION"
    # Preview only: the real C4 freeze/precheck recomputes profile changes after source commit.
    preview = copy.deepcopy(value)
    preview.update(status="FROZEN", freeze_commit=git("rev-parse", "HEAD"), freeze_tree=git("rev-parse", "HEAD^{tree}"),
                   profile_config_blob=git("rev-parse", "HEAD:Tools/provenance/manifest_profiles.json"))
    plan = rules.compute_rerun_plan(preview, previous, previous_matrix,
                                   current_contract_sha256=digest.upper(), previous_contract_sha256=PREVIOUS_SHA256,
                                   previous_matrix_sha256=PREVIOUS_MATRIX_SHA256, current_round_id=matrix["round_id"], repo_root=ROOT)
    assert not plan["reusable_criteria"] and len(plan["rerun_criteria"]) == 9 and len(plan["required_commands"]) == 17
    assert plan["previous_round_id"] == previous_matrix["round_id"] and plan["previous_matrix_sha256"] == PREVIOUS_MATRIX_SHA256
    assert not rules.validate_planned_execution(matrix, preview, plan), "PREVIEW_PLAN_INVALID"
    fixture = guard(ROOT / ".cache/p44/tmp/p44-v4-bundle-fixturexxxxxx")
    assert len(str(fixture)) == len(str(DATA)), "PATH_FIXTURE_BASE_LENGTH"
    copies = [(guard(fixture / destination.relative_to(DATA)), guard(source).read_bytes())
              for source, destination in predecessor_files]
    manifest_raw = (json.dumps(predecessor, indent=2, ensure_ascii=True) + "\n").encode()
    copies.append((guard(fixture / PREDECESSOR), manifest_raw))
    for destination, data in copies:
        if destination.exists():
            assert destination.read_bytes() == data, "EXISTING_FIXTURE_CHANGED"
    for destination, data in copies:
        if not destination.exists():
            write(destination, data)
        assert guard(destination).read_bytes() == data, "PATH_FIXTURE_READBACK"
    current = copy.deepcopy(preview)
    anchor = next(item for item in current["external_inputs"] if item["id"] == "predecessor-before")
    anchor.update(evidence_path="evidence/" + PREDECESSOR, evidence_sha256=sha(manifest_raw), fingerprint="sha256:" + sha(manifest_raw))
    contexts = privacy_contexts(inspection, current, fixture)
    assert [root.relative_to(fixture).as_posix() for root in contexts] == [".", "p", "p/inputs/predecessor-before",
                                                                          "p/inputs/predecessor-before/inputs/predecessor-before"]
    assert select_privacy_context(fixture / "p-other/untracked.http.json", contexts).base == fixture, "CONTEXT_PREFIX_COLLISION"
    decoded_originals, gzip_record, gzip_context = 0, None, None
    for destination, _ in copies:
        if destination.name.endswith(".http.json"):
            record = read(destination)
            context = select_privacy_context(destination, contexts)
            decoded = public_d1_decoded(record, inspection, context)
            if decoded is not None:
                assert context.base == fixture / "p", "INHERITED_GZIP_CONTEXT"
                decoded_originals += 1
                gzip_record, gzip_context = record, context
    assert decoded_originals == 12, "INHERITED_GZIP_SKIPPED"
    wrong = copy.deepcopy(gzip_record)
    wrong["decoded_body"] = wrong["body"]
    rejected = False
    try:
        public_d1_decoded(wrong, inspection, gzip_context)
    except inspection.EvidenceError:
        rejected = True
    assert rejected, "INHERITED_GZIP_SIDECAR_MISMATCH_ACCEPTED"
    print(json.dumps({"ok": True, "schema_positive": 1, "dependency_negative": 1, "privacy_checks": 5,
                      "compressed_privacy_checks": 5,
                      "matrix_checks": 3, "previous_parameter_checks": 3, "predecessor_source_bundle": predecessor["source_bundle_commit"],
                      "predecessor_files": len(predecessor_files), "predecessor_complete_responses": 47, "predecessor_incomplete_responses": 3,
                      "path_fixture": str(fixture), "path_fixture_files": len(copies), "longest_path_written_and_read": 239,
                      "privacy_contexts": len(contexts), "inherited_gzip_originals": decoded_originals,
                      "context_boundary_checks": 1, "inherited_gzip_negative_checks": 1,
                      "previous_physical_validation": True, "plan_preview_rerun_criteria": len(plan["rerun_criteria"]),
                      "plan_preview_required_commands": len(plan["required_commands"]), "preview_is_formal_admission": False,
                      "absolute_root_commands": len(offline_commands),
                      "inventory_schema_checks": 3,
                      "commands": len(value["commands"]), "criteria": len(value["criteria"]), "platform_operations": 0}))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("mode", choices=("prepare", "freeze", "privacy", "assess", "selftest", "commands", "validation-commands"))
    mode = parser.parse_args().mode
    assert Path.cwd().absolute() == ROOT and sys.flags.optimize == 0, "EXECUTION_CONTEXT"
    if mode == "commands":
        print("\n".join(item["command"] for item in definitions()[0]))
    elif mode == "validation-commands":
        print(json.dumps(validation_commands(), indent=2))
    else:
        globals()[mode]()


if __name__ == "__main__":
    try:
        main()
    except Exception as error:
        print(json.dumps({"ok": False, "error_code": type(error).__name__}))
        raise SystemExit(1)
