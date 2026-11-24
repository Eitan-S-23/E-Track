"""Two bounded fixed-signer builds, original artifacts and certificate comparison."""
import argparse
import hashlib
import http.client
import json
import os
from pathlib import Path
import runpy
import struct
import sys
import time
import urllib.error

ROOT = Path(__file__).resolve().parents[2]
SHA = "0dd20fe72940ca26101c5d41f1b26cd039189a8a"
CERT = "9e9b89c5e7fdc802b1fe71806a988a866db49cd988a739caeee56cb69f3df579"


def apk_certificate(data):
    def sized(raw):
        if len(raw) < 4:
            raise ValueError("truncated signing block")
        n = struct.unpack_from("<I", raw)[0]
        if n > len(raw) - 4:
            raise ValueError("invalid signing block length")
        return raw[4:4 + n], raw[4 + n:]
    end = data.rfind(b"PK\x05\x06")
    if end < 0 or end + 22 > len(data) or end + 22 + struct.unpack_from("<H", data, end + 20)[0] != len(data):
        raise ValueError("invalid APK directory footer")
    cd = struct.unpack_from("<I", data, end + 16)[0]
    if not 24 <= cd <= end or data[cd - 16:cd] != b"APK Sig Block 42":
        raise ValueError("APK signing block missing")
    size = struct.unpack_from("<Q", data, cd - 24)[0]
    if not 24 <= size <= cd - 8 or struct.unpack_from("<Q", data, cd - size - 8)[0] != size:
        raise ValueError("invalid signing block size")
    pairs, found = data[cd - size:cd - 24], []
    while pairs:
        if len(pairs) < 12:
            raise ValueError("truncated signing pair")
        n = struct.unpack_from("<Q", pairs)[0]
        if not 4 <= n <= len(pairs) - 8:
            raise ValueError("invalid signing pair size")
        item, pairs = pairs[8:8 + n], pairs[8 + n:]
        if struct.unpack_from("<I", item)[0] == 0x7109871a:
            signers, trailing = sized(item[4:])
            signer, more = sized(signers)
            if trailing or more:
                raise ValueError("ambiguous APK signers")
            signed, _ = sized(signer)
            _, rest = sized(signed)
            certificates, _ = sized(rest)
            certificate, _ = sized(certificates)
            found.append(hashlib.sha256(certificate).hexdigest())
    if len(found) != 1:
        raise ValueError("exact one APK v2 signer required")
    return found[0]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("mode", choices=("dispatch", "collect"))
    parser.add_argument("--generation", type=int, choices=(1, 2), required=True)
    parser.add_argument("--attempt", type=int, choices=(1, 2, 3), default=1)
    args = parser.parse_args()
    v = runpy.run_path(str(ROOT / "Tools/ota/p34_signing_validation.py"))
    b = v["runtime"]()
    v["preflight"](b)
    b.require(Path.cwd() == ROOT and sys.flags.isolated and sys.flags.no_site and sys.dont_write_bytecode,
              "isolated explicit root required")
    b.unchanged_original()
    if args.mode == "collect":
        original_api = b.api
        def read_api(path, credential):
            for attempt in range(1, 4):
                try:
                    return original_api(path, credential)
                except (urllib.error.URLError, http.client.RemoteDisconnected) as error:
                    retryable = (isinstance(error, http.client.RemoteDisconnected) or
                        isinstance(error, urllib.error.URLError) and not isinstance(error, urllib.error.HTTPError))
                    b.save(b.numbered("collection-read-failure"), dict(time=b.now(), path=path,
                        attempt=attempt, error=type(error).__name__, read_only=True))
                    if not retryable or attempt == 3:
                        raise
                    time.sleep(attempt * 2)
        b.api = read_api
    root_out = b.OUT
    area = b.checked(root_out / ("apk-g%d" % args.generation))
    token = b.credential()
    if args.mode == "dispatch":
        b.require(not area.exists(), "reconcile the existing dispatch instead of repeating it")
        checks = b.latest("status")
        b.require(checks["sha"] == SHA and any(r["event"] == "push" and r["conclusion"] == "success"
            and len(r["jobs"]) == 2 and all(j["conclusion"] == "success" for j in r["jobs"])
            for r in checks["runs"]), "both-host green checks required")
        if args.generation == 2:
            first = b.read("apk-g1/apk.json")
            b.require(first["sha"] == SHA and first["certificate_sha256"] == CERT and
                      b.record(first["apk"]["path"]) == first["apk"], "first build must be verified")
        b.require(b.api("/repos/" + b.REPO + "/git/ref/heads/" + b.BRANCH, token)[1]["object"]["sha"] == SHA,
                  "remote source changed")
        inputs = dict(test_scope="all", build_apk="true", app_id_suffix=".p34probe", device_observation="true",
            observation_target="02:00:00:00:00:01", ota_link_candidate="runtime",
            observation_firmware_latest_url="https://p34-runtime-required.invalid/api/public/firmware/latest")
        prior = b.api("/repos/" + b.REPO + "/actions/runs?head_sha=" + SHA + "&per_page=100", token)[1]["workflow_runs"]
        b.save("apk-g%d/intent.json" % args.generation, dict(time=b.now(), sha=SHA, inputs=inputs,
            prior_ids=[r["id"] for r in prior], purpose="two independent fixed-certificate builds"))
        status, _ = b.api("/repos/" + b.REPO + "/actions/workflows/flutter-dev-checks.yml/dispatches", token,
                          data=dict(ref=b.BRANCH, inputs=inputs))
        b.require(status == 204, "dispatch outcome unresolved")
        b.save("apk-g%d/accepted.json" % args.generation, dict(time=b.now(), status=status, sha=SHA))
        print("SIGNING_APK_DISPATCH_ACCEPTED", args.generation, SHA)
        return
    intent = b.read("apk-g%d/intent.json" % args.generation)
    runs = b.api("/repos/" + b.REPO + "/actions/runs?head_sha=" + SHA + "&per_page=100", token)[1]["workflow_runs"]
    selected = [r for r in runs if r["id"] not in intent["prior_ids"] and r["event"] == "workflow_dispatch" and
                r["head_branch"] == b.BRANCH and r["path"] == ".github/workflows/flutter-dev-checks.yml"]
    b.require(len(selected) == 1, "one exact new dispatch required")
    run = selected[0]
    b.require(run["head_sha"] == SHA and run["status"] == "completed" and run["conclusion"] == "success" and
              run["run_attempt"] == 1, "successful exact APK run required")
    jobs = b.api("/repos/" + b.REPO + "/actions/runs/%d/jobs" % run["id"], token)[1]["jobs"]
    b.require(len(jobs) == 2 and all(j["conclusion"] == "success" for j in jobs), "both hosts required")
    listing = b.api("/repos/" + b.REPO + "/actions/runs/%d/artifacts?per_page=100" % run["id"], token)[1]
    artifacts = listing["artifacts"]
    b.require(listing["total_count"] == len(artifacts) == 3 and all(not a["expired"] and
        a["workflow_run"]["head_sha"] == SHA and a["workflow_run"]["id"] == run["id"] for a in artifacts),
        "exact original artifacts required")
    b.OUT = b.host.OUT = area
    os.environ.update(b.environment())
    recovery = b.checked(area / ("download-recovery-%03d" % args.attempt))
    b.require(not recovery.exists() and not (area / "apk.json").exists(), "preserve collection attempts")
    collector = b.load("fixed_signing_download", ROOT / "Tools/ota/collect_baud_apk.py")
    collector.b = collector.d.b = b
    files = [Path(f["path"]) for a in sorted(artifacts, key=lambda a: a["size_in_bytes"])
             for f in collector.fetch(a, token, recovery, "auto", "curl")["files"]]
    reports = [p for p in files if p.name == "result.json"]
    b.require(len(reports) == 2, "two original reports required")
    for path in reports:
        r = json.loads(path.read_bytes())
        b.require(r["development_result"] == "PASS" and r["scope"] == "all" and
            r["source_before"]["head"] == SHA and r["source_before"]["clean"], "host report failed")
    apks = [p for p in files if p.name == "trace-dev-debug.apk"]
    b.require(len(apks) == 1, "one debug APK required")
    apk = b.record(apks[0])
    meta = json.loads(apks[0].with_suffix(".json").read_bytes())
    b.require(meta["commit"] == SHA and meta["sha256"] == apk["sha256"] and meta["release_signing"] is False and
        meta["application_id"] == "com.wen.gaia.gaia.p34probe" and
        meta["development_signing"] == dict(fixed=True, certificate_sha256=CERT) and
        apk_certificate(apks[0].read_bytes()) == CERT, "actual APK certificate/identity mismatch")
    b.save("apk.json", dict(time=b.now(), sha=SHA, run=run["id"], url=run["html_url"], apk=apk,
        metadata=meta, host_reports=[b.record(p) for p in reports], certificate_sha256=CERT,
        installed=False, independent_acceptance=False))
    print("FIXED_SIGNER_APK_VERIFIED", args.generation, CERT, apk["sha256"])
    if args.generation == 2:
        first = json.loads((root_out / "apk-g1/apk.json").read_bytes())
        b.require(first["run"] != run["id"] and first["certificate_sha256"] == CERT and
                  b.record(first["apk"]["path"]) == first["apk"], "independent first APK changed")
        b.io.write_json(ROOT, b.checked(root_out / "signer-comparison.json"), dict(result="TWO_BUILDS_SAME_CERTIFICATE",
            certificate_sha256=CERT, first=first["apk"], second=apk, runs=[first["run"], run["id"]],
            installed=False, device_operations=0))


if __name__ == "__main__":
    main()
