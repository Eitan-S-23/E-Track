"""Execute a frozen, host-only link-stats acceptance input plan.

The plan defines parser controls, not physical OTA performance thresholds.
Original captures and synthetic controls remain explicitly distinct.
"""

import argparse
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import stat
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[3]
HERE = Path(__file__).resolve().parent


def require(condition, message):
    if not condition:
        raise ValueError(message)


def guarded(path):
    path = Path(os.path.abspath(path))
    for parent in [path] + list(path.parents):
        try:
            info = parent.lstat()
        except FileNotFoundError:
            continue
        require(not stat.S_ISLNK(info.st_mode)
                and not getattr(info, "st_file_attributes", 0) & 0x400,
                "reparse/symlink output: " + str(parent))
    require(path.resolve().is_relative_to(ROOT), "output outside worktree: " + str(path))
    return path


def bundle_path(bundle, relative):
    relative = Path(relative)
    require(not relative.is_absolute() and ".." not in relative.parts,
            "invalid bundle-relative path")
    path = guarded(bundle / relative)
    require(path.resolve().is_relative_to(bundle), "path escapes bundle")
    return path


def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def save(path, data):
    path = guarded(path)
    require(not path.exists(), "refusing to overwrite evidence: " + str(path))
    guarded(path.parent).mkdir(parents=True, exist_ok=True)
    guarded(path)
    with path.open("xb") as handle:
        handle.write(data)
    return {"bytes": len(data), "sha256": hashlib.sha256(data).hexdigest()}


def load_plan(bundle):
    plan_path = bundle_path(bundle, "inputs/plan.json")
    plan = json.loads(plan_path.read_bytes())
    require(plan.get("schema") == "p34-parser-acceptance-inputs-v1", "unsupported input plan")
    for item in plan["files"]:
        path = bundle_path(bundle, item["path"])
        require(path.is_file() and path.stat().st_size == item["bytes"]
                and digest(path) == item["sha256"], "input identity mismatch: " + item["path"])
    return plan


def child_environment(bundle):
    temp = bundle_path(bundle, "scratch/tmp")
    guarded(temp).mkdir(parents=True, exist_ok=True)
    result = dict(os.environ)
    for key in ("TEMP", "TMP", "TMPDIR"):
        result[key] = str(temp)
    result.update(PYTHONDONTWRITEBYTECODE="1", PYTHONUTF8="1", PYTHONOPTIMIZE="0", GIT_OPTIONAL_LOCKS="0")
    return result


def execute(bundle, phase, name, argv):
    outputs = [bundle_path(bundle, "raw/%s/%s.%s" % (phase, name, stream))
               for stream in ("stdout", "stderr")]
    for path in outputs:
        require(not path.exists(), "evidence already exists: " + str(path))
    process = subprocess.run(argv, cwd=ROOT, env=child_environment(bundle),
                             capture_output=True, timeout=120)
    record = {"argv": argv, "cwd": str(ROOT), "exit": process.returncode}
    for path, stream, data in zip(outputs, ("stdout", "stderr"), (process.stdout, process.stderr)):
        record[stream] = dict(save(path, data), path=path.relative_to(bundle).as_posix())
    return record, process


def lookup(value, path):
    for key in path.split("."):
        require(isinstance(value, dict) and key in value, "missing observed field: " + path)
        value = value[key]
    return value


def check_case(code, payload, expected):
    issues = []
    if code != expected["exit"]:
        issues.append("exit mismatch")
    findings = payload.get("findings")
    if not isinstance(findings, list):
        return issues + ["findings missing"]
    fatal = sorted({f.get("code") for f in findings if f.get("severity") == "fatal"})
    if fatal != expected["fatal_codes"]:
        issues.append("fatal code set mismatch: " + repr(fatal))
    for path, value in expected["equals"].items():
        try:
            actual = lookup(payload, path)
        except ValueError as exc:
            issues.append(str(exc))
            continue
        if type(actual) is not type(value) or actual != value:
            issues.append("field mismatch: " + path)
    if expected.get("distinct_exclusion_sources"):
        sources = {r["source"] for r in payload["report"]["excluded"]}
        if len(sources) != expected["distinct_exclusion_sources"]:
            issues.append("exclusion source count mismatch")
        if not sources <= {r["sourceId"] for r in payload["inputs"]}:
            issues.append("unresolvable exclusion source")
    if expected.get("duplicate"):
        inputs = payload.get("inputs", [])
        if len(inputs) != 2 or inputs[1].get("duplicateOf") != inputs[0].get("sourceId"):
            issues.append("duplicate source binding mismatch")
    return issues


def parser_cases(bundle, plan, phase):
    rows = []
    for case in plan[phase]:
        argv = [sys.executable, "-X", "utf8", "-S", "-B", str(HERE / "link_stats.py")]
        for position, relative in enumerate(case["logs"]):
            path = bundle_path(bundle, relative)
            argument = path.relative_to(ROOT) if position in case.get("relative_logs", []) else path
            argv += ["--log", str(argument)]
        if case.get("group"):
            argv += ["--group", str(bundle_path(bundle, case["group"]))]
        if case.get("strict"):
            argv.append("--device-capture")
        argv.append("--json")
        command, result = execute(bundle, phase, case["id"], argv)
        try:
            payload = json.loads(result.stdout)
            issues = check_case(result.returncode, payload, case["expected"])
        except (ValueError, TypeError, KeyError) as exc:
            payload, issues = None, ["invalid parser result: " + str(exc)]
        if result.stderr:
            issues.append("unexpected stderr")
        rows.append({"id": case["id"], "command": command, "issues": issues,
                     "passed": not issues, "observed": payload})
    return {"passed": bool(rows) and all(r["passed"] for r in rows), "cases": rows}


def selftest(bundle, plan):
    for item in plan["selftest_external_captures"]:
        require(digest(item["source"]) == item["sha256"], "original selftest capture changed")
    spec = importlib.util.spec_from_file_location("p34_acceptance_selftest", HERE / "selftest.py")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    discovered = sorted(str(Path(p).resolve()) for _, _, p in module.optional_captures())
    require(discovered == sorted(str(Path(p["source"]).resolve()) for p in plan["selftest_external_captures"]),
            "selftest external input set differs from frozen plan")
    require(not module.leftover_temp_files(), "pre-existing selftest temporary files")
    command, result = execute(bundle, "selftest", "selftest",
                              [sys.executable, "-X", "utf8", "-S", "-B", str(HERE / "selftest.py")])
    lines = result.stdout.decode("utf-8").splitlines()
    passed = sum(line.startswith("PASS  ") for line in lines)
    failures = [line for line in lines if line.lstrip().startswith(("FAIL", "SKIP", "WARN"))]
    mutation_lines = [line for line in lines if line.startswith("      \u9274\u522b\u529b ")]
    slots = sum(len(entry["tests"]) for entry in module.DISCRIMINATION)
    discrimination = (len(mutation_lines) == slots and all(
        "\u5b9e\u9645=AssertionError:" in line and "\u6062\u590d=\u901a\u8fc7" in line for line in mutation_lines))
    untouched = all(digest(item["source"]) == item["sha256"] for item in plan["selftest_external_captures"])
    result_ok = (result.returncode == 0 and not result.stderr and not failures
                 and passed == len(module.TESTS) and not module.leftover_temp_files() and untouched)
    return {"passed": result_ok and discrimination, "selftests_passed": result_ok,
            "discrimination_passed": discrimination, "command": command,
            "test_count": len(module.TESTS), "pass_count": passed, "failures": failures,
            "mutation_slots": slots, "mutation_lines": mutation_lines,
            "external_captures_unchanged": untouched}


def self_check():
    expected = {"exit": 0, "fatal_codes": [], "equals": {"report.runs": 1, "report.eligibleForThreshold": True}}
    valid = {"findings": [], "report": {"runs": 1, "eligibleForThreshold": True}}
    require(not check_case(0, valid, expected), "positive comparator control failed")
    require(check_case(1, valid, expected), "exit negative not detected")
    for field, value in (("runs", 0), ("runs", True), ("eligibleForThreshold", False)):
        changed = json.loads(json.dumps(valid))
        changed["report"][field] = value
        require(check_case(0, changed, expected), "field negative not detected")
    require(check_case(0, {"report": {}}, expected), "missing findings not detected")
    require(check_case(0, {"findings": [], "report": {}}, expected), "missing fields not detected")
    try:
        bundle_path(ROOT, "../outside")
    except ValueError:
        pass
    else:
        raise ValueError("path traversal guard failed")
    print("SELF_CHECK=PASS positive=1 negative=7")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--bundle", type=Path)
    parser.add_argument("--phase", choices=("selftest", "controls", "captures"))
    parser.add_argument("--self-check", action="store_true")
    parser.add_argument("--preflight", action="store_true")
    args = parser.parse_args()
    require(sys.flags.optimize == 0, "optimized Python would disable delivered test assertions")
    require(Path.cwd().resolve() == ROOT, "cwd must be the active worktree root")
    if args.self_check:
        self_check()
        return 0
    require(args.bundle is not None, "--bundle required")
    bundle = guarded(args.bundle).resolve()
    plan = load_plan(bundle)
    for phase in ("selftest", "controls", "captures"):
        guarded(bundle / "results" / (phase + ".json"))
        guarded(bundle / "raw" / phase)
    for name in plan["selftest_temp_paths"]:
        path = guarded(ROOT / name)
        require(not path.exists(), "pre-existing selftest scratch path: " + name)
    if args.preflight:
        print(json.dumps({"input_preflight": True, "files": len(plan["files"]),
                          "controls": len(plan["controls"]), "captures": len(plan["captures"])}))
        return 0
    require(args.phase is not None, "--phase required")
    contract = json.loads((bundle / "contract.json").read_bytes())
    bound = next(item for item in contract["external_inputs"] if item["id"] == "FIX-PLAN")
    require(contract["status"] == "FROZEN" and digest(bundle / "inputs/plan.json") == bound["evidence_sha256"],
            "input plan is not bound to a frozen contract")
    result = selftest(bundle, plan) if args.phase == "selftest" else parser_cases(bundle, plan, args.phase)
    result["phase"] = args.phase
    result["plan_sha256"] = digest(bundle / "inputs/plan.json")
    save(bundle_path(bundle, "results/%s.json" % args.phase),
         (json.dumps(result, ensure_ascii=True, sort_keys=True, indent=2) + "\n").encode())
    print(json.dumps({"phase": args.phase, "passed": result["passed"],
                      "result_path": "results/%s.json" % args.phase}))
    return 0 if result["passed"] else 1


if __name__ == "__main__":
    sys.exit(main())
