"""Collect the exact reconnect development run; no dispatch or device effects."""
import argparse
import json
import os
from pathlib import Path
import runpy
import sys

ROOT = Path(__file__).resolve().parents[2]
SHA = "64a53a7f4aa3fb64804c768c2857d939e168ae1a"
RUN = 36864019100


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--attempt", type=int, choices=(1, 2, 3), required=True)
    args = parser.parse_args()
    v = runpy.run_path(str(ROOT / "Tools/ota/p34_reconnect_validation.py"))
    b = v["runtime"]()
    b.require(Path.cwd() == ROOT and sys.flags.isolated and sys.flags.no_site and
              sys.dont_write_bytecode, "isolated explicit root required")
    b.reconnect_preflight(b)
    b.unchanged_original()
    recovery = b.checked(b.OUT / ("download-recovery-%d-%03d" % (RUN, args.attempt)))
    for name in ("apk.json", "ci-artifacts.json"):
        b.checked(b.OUT / name)
    b.checked(recovery / "result.json")
    b.require(not recovery.exists() and not (b.OUT / "apk.json").exists(),
              "preserve existing collection; reconcile before retry")
    os.environ.update(b.environment())
    token = b.credential()
    run = b.api("/repos/" + b.REPO + "/actions/runs/" + str(RUN), token)[1]
    b.require(run["head_sha"] == SHA and run["head_branch"] == b.BRANCH and
              run["path"] == ".github/workflows/flutter-dev-checks.yml" and
              run["event"] == "workflow_dispatch" and run["run_attempt"] == 1 and
              run["status"] == "completed" and run["conclusion"] == "success",
              "exact successful APK run required")
    jobs = b.api("/repos/" + b.REPO + "/actions/runs/%d/jobs" % RUN, token)[1]["jobs"]
    b.require(len(jobs) == 2 and {job["name"] for job in jobs} == {
        "Flutter self-tests (ubuntu-latest)", "Flutter self-tests (windows-2022)"} and
        all(job["conclusion"] == "success" for job in jobs), "both hosts required")
    listing = b.api("/repos/" + b.REPO + "/actions/runs/%d/artifacts?per_page=100" % RUN, token)[1]
    artifacts = listing["artifacts"]
    b.require(listing["total_count"] == len(artifacts) == 3 and
        all(not a["expired"] and a["workflow_run"]["id"] == RUN and
            a["workflow_run"]["head_sha"] == SHA and a["digest"].startswith("sha256:")
            for a in artifacts), "three exact original artifacts required")
    inventory = dict(sha=SHA, run=RUN, artifacts=artifacts)
    if (b.OUT / "ci-artifacts.json").exists():
        old = b.read("ci-artifacts.json")
        b.require(old == inventory, "artifact inventory changed")
    else:
        b.save("ci-artifacts.json", inventory)
    collector = b.load("p34_reconnect_download", ROOT / "Tools/ota/collect_baud_apk.py")
    collector.b = b
    collector.d.b = b
    files = [Path(item["path"]) for artifact in sorted(artifacts, key=lambda a: a["size_in_bytes"])
             for item in collector.fetch(artifact, token, recovery, "auto", "curl")["files"]]
    reports = [p for p in files if p.name == "result.json"]
    b.require(len(reports) == 2, "both original host reports required")
    for path in reports:
        report = json.loads(path.read_text(encoding="utf-8"))
        b.require(report["development_result"] == "PASS" and report["scope"] == "all" and
                  report["source_before"]["head"] == SHA and report["source_before"]["clean"],
                  "host report binding failed")
        print("HOST_REPORT", report["host"], json.dumps(report.get("console_summary", {})), flush=True)
    apks = [p for p in files if p.name == "trace-dev-debug.apk"]
    b.require(len(apks) == 1, "one debug APK required")
    apk = b.record(apks[0])
    meta = json.loads(apks[0].with_suffix(".json").read_text(encoding="utf-8"))
    b.require(meta["commit"] == SHA and meta["application_id"] == "com.wen.gaia.gaia.p34probe" and
              meta["release_signing"] is False and meta["sha256"] == apk["sha256"] and
              meta["requested_ota_link_candidate"] == dict(name="runtime", runtime_config=True),
              "APK metadata binding failed")
    b.unchanged_original()
    b.save("apk.json", dict(time=b.now(), sha=SHA, run=RUN, url=run["html_url"], apk=apk,
        metadata=meta, host_reports=[b.record(p) for p in reports], installed=False,
        independent_acceptance=False))
    b.io.write_json(ROOT, recovery / "result.json", dict(result="APK_VERIFIED", apk=apk,
        device_commands=0, ci_dispatches=0, source=b.record(Path(__file__))))
    print("APK_VERIFIED", apk["sha256"], apk["path"], flush=True)


if __name__ == "__main__":
    main()
