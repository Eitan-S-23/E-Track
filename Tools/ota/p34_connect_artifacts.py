"""One fixed-signer APK request and verified collection for the reconnect repair."""
import argparse
import http.client
from pathlib import Path
import runpy
import sys
import time
import types
import urllib.error

ROOT = Path(__file__).resolve().parents[2]
SHA = "e29c1392db7a1e0570b588f4d2f2c8d0d9c9c3ad"


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("mode", choices=("dispatch", "collect"))
    parser.add_argument("--attempt", type=int, choices=(1, 2, 3), default=1)
    args = parser.parse_args()
    adapter = runpy.run_path(str(ROOT / "Tools/ota/p34_connect_validation.py"))
    b = adapter["runtime"]()
    for p in (b.OUT, b.OUT / "apk-g1", b.OUT / "commands.jsonl", b.OUT / "host"):
        b.checked(p)
    b.unchanged_original()
    api = b.api
    def bounded_api(path, token, **kwargs):
        if kwargs.get("data") is not None:
            return api(path, token, **kwargs)
        for attempt in range(1, 4):
            try:
                return api(path, token, **kwargs)
            except (urllib.error.URLError, http.client.RemoteDisconnected) as error:
                if isinstance(error, urllib.error.HTTPError):
                    raise
                b.save(b.numbered("read-retry"), dict(path=path, attempt=attempt,
                    error=type(error).__name__, read_only=True))
                if attempt == 3:
                    raise
                time.sleep(attempt * 2)
    b.api = bounded_api
    if args.mode == "collect":
        original = runpy.run_path(str(ROOT / "Tools/ota/p34_signing_artifacts.py"))["main"]
        def signing_runtime(path):
            b.require(Path(path) == ROOT / "Tools/ota/p34_signing_validation.py", "unexpected collector loader")
            return dict(runtime=lambda: b, preflight=lambda current: current.checked(current.OUT))
        original.__globals__.update(SHA=SHA, runpy=types.SimpleNamespace(run_path=signing_runtime))
        sys.argv = [__file__, "collect", "--generation", "1", "--attempt", str(args.attempt)]
        original()
        return
    b.require(not (b.OUT / "apk-g1").exists(), "APK dispatch already reserved; reconcile instead")
    checks = b.latest("status")
    b.require(checks["sha"] == SHA and any(r["event"] == "push" and r["conclusion"] == "success"
        and len(r["jobs"]) == 2 and all(j["conclusion"] == "success" for j in r["jobs"])
        for r in checks["runs"]), "both-host green checks required")
    token = b.credential()
    b.require(b.api("/repos/" + b.REPO + "/git/ref/heads/" + b.BRANCH, token)[1]["object"]["sha"] == SHA,
              "remote commit differs")
    prior = b.api("/repos/" + b.REPO + "/actions/runs?head_sha=" + SHA + "&per_page=100", token)[1]["workflow_runs"]
    inputs = dict(test_scope="all", build_apk="true", app_id_suffix=".p34probe", device_observation="true",
        observation_target="02:00:00:00:00:01", ota_link_candidate="runtime",
        observation_firmware_latest_url="https://p34-runtime-required.invalid/api/public/firmware/latest")
    b.save("apk-g1/intent.json", dict(time=b.now(), sha=SHA, inputs=inputs, prior_ids=[r["id"] for r in prior],
        purpose="mobile reconnect repair; same package ID and fixed development signer"))
    status, _ = b.api("/repos/" + b.REPO + "/actions/workflows/flutter-dev-checks.yml/dispatches", token,
                      data=dict(ref=b.BRANCH, inputs=inputs))
    b.require(status == 204, "dispatch outcome unresolved")
    b.save("apk-g1/accepted.json", dict(time=b.now(), status=status, sha=SHA))
    print("RECONNECT_REPAIR_APK_DISPATCH_ACCEPTED", SHA)


if __name__ == "__main__":
    if not (Path.cwd() == ROOT and sys.flags.isolated and sys.flags.no_site and sys.dont_write_bytecode):
        raise RuntimeError("isolated explicit root required")
    main()
