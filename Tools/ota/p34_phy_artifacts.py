"""Source-bound PHY CI logs and one same-signer APK; never installs or operates BLE."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import runpy
import sys
import types

ROOT = Path(__file__).resolve().parents[2]
CERT = "9e9b89c5e7fdc802b1fe71806a988a866db49cd988a739caeee56cb69f3df579"


def native_encoding(original, digest, *, windows):
    if hashlib.sha256(original).hexdigest() == digest:
        return "git-blob-bytes"
    if windows and b"\r" not in original and hashlib.sha256(original.replace(b"\n", b"\r\n")).hexdigest() == digest:
        return "windows-crlf-checkout"
    raise RuntimeError("native report input mismatch beyond exact Git checkout line endings")


def existing_receipts(area, artifact_id):
    return sorted(area.glob("download-*/artifacts/" + str(artifact_id) + "/receipt.json"))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("mode", choices=("dispatch", "collect", "logs"))
    parser.add_argument("--run", type=int)
    parser.add_argument("--attempt", type=int, choices=(1, 2, 3), default=1)
    args = parser.parse_args()
    if not (Path.cwd() == ROOT and sys.flags.isolated and sys.flags.no_site and sys.dont_write_bytecode):
        raise RuntimeError("isolated explicit root required")
    b = runpy.run_path(str(ROOT / "Tools/ota/p34_phy_validation.py"))["runtime"]()
    b.unchanged_original()
    sha = b.latest("commit")["sha"]
    if args.mode == "dispatch":
        entry = runpy.run_path(str(ROOT / "Tools/ota/p34_connect_artifacts.py"))["main"]
        def loader(path):
            if Path(path) != ROOT / "Tools/ota/p34_connect_validation.py":
                raise RuntimeError("unexpected dispatch dependency")
            return dict(runtime=lambda: b)
        original_save = b.save
        def save(path, value):
            if path == "apk-g1/intent.json":
                value = dict(value, purpose="PHY readback experiment; same package and fixed signer")
            return original_save(path, value)
        b.save = save
        entry.__globals__.update(SHA=sha, runpy=types.SimpleNamespace(run_path=loader))
        sys.argv = [__file__, "dispatch"]
        entry()
        return
    token = b.credential()
    if args.mode == "collect":
        intent = b.read("apk-g1/intent.json")
        b.require(intent["sha"] == sha, "APK intent source changed")
        runs = b.api("/repos/" + b.REPO + "/actions/runs?head_sha=" + sha + "&per_page=100", token)[1]["workflow_runs"]
        selected = [r for r in runs if r["id"] not in intent["prior_ids"] and
            r["event"] == "workflow_dispatch" and r["head_branch"] == b.BRANCH and
            r["path"] == ".github/workflows/flutter-dev-checks.yml"]
        b.require(len(selected) == 1, "exactly one original APK dispatch required")
        run = selected[0]
    else:
        b.require(args.run is not None, "logs require explicit run")
        run = b.api("/repos/" + b.REPO + "/actions/runs/" + str(args.run), token)[1]
    b.require(run["head_sha"] == sha and run["head_branch"] == b.BRANCH and
        run["path"] == ".github/workflows/flutter-dev-checks.yml" and run["status"] == "completed",
        "original completed source-bound development run required")
    jobs = b.api("/repos/" + b.REPO + "/actions/runs/%d/jobs" % run["id"], token)[1]["jobs"]
    if args.mode == "collect":
        b.require(run["conclusion"] == "success" and len(jobs) == 2 and
            all(j["conclusion"] == "success" for j in jobs), "both-host green APK run required")
    listing = b.api("/repos/" + b.REPO + "/actions/runs/%d/artifacts?per_page=100" % run["id"], token)[1]
    artifacts = listing["artifacts"]
    b.require(listing["total_count"] == len(artifacts) and all(not a["expired"] and
        a["workflow_run"]["head_sha"] == sha and a["workflow_run"]["id"] == run["id"]
        for a in artifacts), "artifact identity or availability mismatch")
    prefixes = ("flutter-dev-ubuntu-latest-", "flutter-dev-windows-2022-")
    selected = [a for a in artifacts if a["name"].startswith(prefixes)]
    b.require(len(selected) == 2, "two host log artifacts required")
    if args.mode == "collect":
        apk_assets = [a for a in artifacts if a["name"].startswith("flutter-dev-debug-apk-" + sha)]
        b.require(len(apk_assets) == 1, "one APK artifact required")
        selected += apk_assets
    area = b.checked(b.OUT / ("apk-g1" if args.mode == "collect" else "ci/" + str(run["id"])))
    b.OUT = b.host.OUT = area
    os.environ.update(b.environment())
    recovery = b.checked(area / ("download-%03d" % args.attempt))
    b.require(not recovery.exists(), "preserve prior collection; select a fresh bounded attempt")
    collector = b.load("phy_artifact_download", ROOT / "Tools/ota/collect_baud_apk.py")
    collector.b = collector.d.b = b
    files = []
    for artifact in sorted(selected, key=lambda a: a["size_in_bytes"]):
        prior = existing_receipts(area, artifact["id"])
        value = collector.validate_receipt(artifact, json.loads(prior[0].read_bytes())) if prior else \
            collector.fetch(artifact, token, recovery, "auto", "curl")
        files.extend(Path(item["path"]) for item in value["files"])
    reports = [p for p in files if p.name == "result.json"]
    flutter, native, encodings = [], [], []
    for path in reports:
        value = json.loads(path.read_bytes())
        if value.get("schema") == "etrack-flutter-dev-checks-v1":
            b.require(value["source_before"]["head"] == sha, "Flutter report source mismatch")
            flutter.append((path, value))
        elif "android_plugin_compiled" in value and "inputs" in value:
            origins = [a for a in selected if str(a["id"]) in path.parts]
            b.require(len(origins) == 1, "native report artifact origin ambiguous")
            windows = origins[0]["name"].startswith("flutter-dev-windows-2022-")
            for name, digest in value["inputs"].items():
                b.checked(b.SRC / name)
                original = b.command(["git", "--no-optional-locks", "-C", str(b.SRC),
                                      "show", sha + ":" + Path(name).as_posix()]).stdout
                encoding = native_encoding(original, digest, windows=windows)
                encodings.append(dict(report=b.record(path), path=name, sha256=digest, encoding=encoding))
            native.append((path, value))
        else:
            raise RuntimeError("unknown development report")
    b.require(len(flutter) == 2, "two actual Flutter reports required")
    summary = dict(sha=sha, run=run["id"], url=run["html_url"], conclusion=run["conclusion"],
        native_checkout_encodings=encodings,
        host_reports=[b.record(p) for p, _ in flutter], native_reports=[b.record(p) for p, _ in native],
        flutter=[dict(host=v["host"], result=v["development_result"],
            summary=v.get("console_summary"), commands=v["commands"]) for _, v in flutter])
    b.save(b.numbered("reports"), summary)
    for path, value in flutter:
        print("HOST", value["host"], value["development_result"], flush=True)
        for command in value["commands"]:
            if command["status"] != "PASS":
                log = path.parent / command["log"]
                if log.is_file():
                    print(log.read_text(encoding="utf-8", errors="replace")[-9000:], flush=True)
    if args.mode == "logs":
        return
    b.require(all(v["development_result"] == "PASS" and v["scope"] == "all" and
        v["source_before"]["clean"] for _, v in flutter) and len(native) == 2 and
        all(v["passed"] for _, v in native), "complete clean both-host reports required")
    apks = [p for p in files if p.name == "trace-dev-debug.apk"]
    b.require(len(apks) == 1, "one APK file required")
    apk = b.record(apks[0])
    meta = json.loads(apks[0].with_suffix(".json").read_bytes())
    certificate = runpy.run_path(str(ROOT / "Tools/ota/p34_signing_artifacts.py"))["apk_certificate"]
    b.require(meta["commit"] == sha and meta["sha256"] == apk["sha256"] and
        meta["release_signing"] is False and meta["application_id"] == "com.wen.gaia.gaia.p34probe" and
        meta["development_signing"] == dict(fixed=True, certificate_sha256=CERT) and
        certificate(apks[0].read_bytes()) == CERT, "actual APK signer/identity mismatch")
    b.save("apk.json", dict(time=b.now(), sha=sha, run=run["id"], url=run["html_url"],
        apk=apk, metadata=meta, host_reports=summary["host_reports"],
        native_reports=summary["native_reports"], certificate_sha256=CERT,
        installed=False, independent_acceptance=False))
    print("PHY_APK_VERIFIED", sha, apk["sha256"], flush=True)


if __name__ == "__main__":
    main()
