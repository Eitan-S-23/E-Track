"""Evaluate existing software and admission originals without a new device action."""
import argparse
import hashlib
import json
from pathlib import Path
import re
import sys
import xml.etree.ElementTree as ET
import zipfile

sys.path.insert(0, str(Path(__file__).resolve().parent))
from prepare import ROOT, firmware_identity, fingerprint, h, runtime_observations


def test_counts(text):
    matches = re.findall(r"\+(\d+)(?:\s+~(\d+))?(?:\s+-(\d+))?: All tests passed!", text)
    h.require(len(matches) == 1, "missing/ambiguous successful test summary")
    passed, skipped, failed = matches[0]
    h.require(not failed or int(failed) == 0, "failed tests")
    return dict(passed=int(passed), skipped=int(skipped or 0), failed=int(failed or 0))


def native_cases(data):
    suite = ET.fromstring(data)
    cases = suite.findall("testcase")
    h.require(suite.tag == "testsuite" and suite.get("name") == "com.wen.gaia.gaia.DeviceOtaServiceTest" and
              len(cases) == int(suite.get("tests", "-1")) == 18 and
              all(suite.get(k) == "0" for k in ("failures", "errors", "skipped")) and
              not any(c.find(k) is not None for c in cases for k in ("failure", "error", "skipped")),
              "native Service cases incomplete/failed")
    names = [c.get("name") for c in cases]
    h.require(len(set(names)) == 18 and all(names), "native case identities")
    return names


def software(plan, out):
    reports = []
    for item in plan["development"]:
        path = h.pinned(item["report"])
        report = h.read_json(path)
        h.require(report["development_result"] == "PASS" and report["scope"] == "all" and
                  report["source_before"]["head"] == plan["commit"] and report["lockfile_unchanged"] and
                  report["diagnostics_complete"], "development report scope/source/result")
        commands = {c["name"]: c for c in report["commands"]}
        for name in ("sdk_version", "analyze", "tests"):
            command = commands[name]
            h.require(command["status"] == "PASS" and command["exit_code"] == 0 and not command["timed_out"],
                      "failed development command")
        counts = test_counts(h.pinned(item["tests"]).read_text(encoding="utf-8"))
        h.require(counts == commands["tests"]["diagnostics"]["test_counts"] == item["counts"], "test counts differ")
        h.require("No issues found!" in h.pinned(item["analyze"]).read_text(encoding="utf-8"), "analyzer not clean")
        sdk = commands["sdk_version"]["diagnostics"]["sdk_identity"]
        h.require(sdk and sdk["frameworkVersion"] == "3.47.8", "unbound SDK")
        reports.append(dict(host=report["host"], counts=counts, sdk=sdk, report=fingerprint(path),
                            toolchain_regen=report.get("toolchain_regen", [])))
    h.require(len(reports) == 2 and any("Windows" in r["host"] for r in reports) and
              any("Linux" in r["host"] for r in reports), "both actual hosts required")
    names = native_cases(h.pinned(plan["native_xml"]).read_bytes())
    env = h.environment(out)
    h.command(out, "native-inputs", ["git", "diff", "--exit-code", "27048aa1", plan["commit"], "--",
        "app/bluetooth_flutter_Trace/android"], env, seconds=30)
    tree = h.command(out, "app-tree", ["git", "rev-parse", plan["commit"] + ":app/bluetooth_flutter_Trace"], env, seconds=30).decode().strip()
    h.require(tree == plan["app_tree"], "wrong App tree")
    products = {name: h.pinned(item) for name, item in plan["standard"].items()}
    with zipfile.ZipFile(products["windows_zip"]) as z:
        h.require(z.testzip() is None, "Windows archive CRC")
        embedded = [n for n in z.namelist() if n.endswith("/ble_monitor.exe") or n == "ble_monitor.exe"]
        h.require(len(embedded) == 1 and z.read(embedded[0]) == products["exe"].read_bytes(), "embedded EXE mismatch")
    warnings = {}
    with zipfile.ZipFile(products["logs"]) as z:
        for member in plan["standard_logs"]:
            raw = z.read(member["member"])
            h.require(len(raw) == member["bytes"] and hashlib.sha256(raw).hexdigest() == member["sha256"],
                      "standard original log changed")
            lines = raw.decode("utf-8", "replace").splitlines()
            for witness in member.get("decisive", []):
                h.require(0 < witness["line"] <= len(lines) and
                          lines[witness["line"] - 1] == witness["text"], "standard result witness mismatch")
            warnings[member["member"]] = [line for line in lines if re.search(r"\bwarning\b", line, re.I)]
    with zipfile.ZipFile(products["apk"]) as z:
        h.require(z.testzip() is None, "standard APK CRC")
    return dict(result="EXISTING_SOFTWARE_ORIGINALS_VERIFIED", reports=reports, native_cases=names,
                standards={name: fingerprint(path) for name, path in products.items()},
                no_new_build_or_hardware=True, original_standard_run=39829695971,
                standard_warning_lines=warnings)


def admission(plan, out):
    originals = {name: h.pinned(item) for name, item in plan["originals"].items()}
    image = firmware_identity(originals["app_region"].read_bytes())
    h.require(image["version_code"] == 30287 and image["raw_sha256"] == plan["base_sha256"], "baseline mismatch")
    data = {name: h.pinned(item).read_bytes() for name, item in plan["state"].items()}
    runtime = runtime_observations(data)
    h.require(all(runtime[k] for k in ("confirmed", "ota_idle", "fault_free", "same_boot_advancing")), "initial runtime gate")
    candidate = firmware_identity(originals["target"].read_bytes())
    h.require(candidate["version_code"] == 30288 and candidate["raw_sha256"] == plan["target_sha256"], "target mismatch")
    h.require(originals["package"].stat().st_size == 1048576, "not the bound 1MiB fixture")
    reference = h.read_json(originals["reference"])
    h.require(reference["positive"]["passed"] and reference["positive"]["byte_identical"] and
              reference["positive"]["boot_ok"] and len(reference["negatives"]) == 4 and
              all(n["result"]["passed"] for n in reference["negatives"]), "decoder reference failed")
    h.require(h.read_json(originals["installed"])["result"] == "SIDE_BY_SIDE_INSTALLED_HASH_VERIFIED", "APK not installed")
    return dict(result="ADMISSION_ORIGINALS_VERIFIED_NOT_A_NEW_SAMPLE", baseline=image, target=candidate,
                runtime=runtime, originals={name: fingerprint(path) for name, path in originals.items()},
                no_device_action=True, live_identity_required_before_transfer=True)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=("software", "admission"))
    parser.add_argument("--inputs", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    h.require(Path.cwd() == ROOT and sys.flags.isolated and sys.flags.no_site and sys.dont_write_bytecode,
              "explicit root and isolated Python required")
    out = h.checked(args.out)
    for name in ("host", "result.json"):
        h.checked(out / name)
    plan = h.read_json(args.inputs)
    h.fresh(out)
    result = software(plan, out) if args.action == "software" else admission(plan, out)
    h.save(out / "result.json", result)
    print(json.dumps(result), flush=True)


if __name__ == "__main__":
    main()
