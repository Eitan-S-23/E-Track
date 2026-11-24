"""Isolated development CI for P3-4 durable-timeout remediation, never release."""
from __future__ import annotations

import argparse
from pathlib import Path
import runpy
import sys

ROOT = Path(__file__).resolve().parents[2]
SELF = Path(__file__).resolve()
BASE = "4f206cfa9f619b336fe1ecda95df19bcec52e664"
OUT = ROOT/".cache/p34d"
SOURCE = ROOT/".cache/p34b/src"
BRANCH = "dev/flutter/p3-4-durable-retry"
SCOPE = {"app/bluetooth_flutter_Trace/lib/ota/ota_ble_transport.dart",
         "app/bluetooth_flutter_Trace/test/ota/ota_ble_transport_test.dart"}


def runtime():
    original = runpy.run_path(str(SELF.with_name("baud_sweep.py")), run_name="retry_validation_loader")
    b = original["load"]("retry_validation_base", SELF.with_name("baud_sweep.py"))
    b.OUT, b.SRC, b.BRANCH, b.host.OUT = OUT, OUT/"src", BRANCH, OUT
    b.ALTERNATES = (SOURCE/".git/objects", *b.ALTERNATES)
    b.scope_allowed = lambda path: path in SCOPE
    return b


def prepare(b):
    b.require(not b.SRC.exists() and not (OUT/"prepared.json").exists(), "preserve validation preparation")
    for path in (b.SRC, b.SRC/".git", OUT/"prepared.json", OUT/"host/empty-template"):
        b.checked(path)
    token = b.credential()
    b.require(b.api("/repos/"+b.REPO+"/git/ref/heads/"+BRANCH, token, missing=True)[0] == 404,
              "do not overwrite an existing validation branch")
    remote = b.command(["git", "--no-optional-locks", "-C", str(ROOT), "remote", "get-url", "origin"]).stdout.decode().strip()
    b.require(remote in ("https://github.com/"+b.REPO+".git", "git@github.com:"+b.REPO+".git"), "remote mismatch")
    base = b.command(["git", "--no-optional-locks", "-C", str(SOURCE), "rev-parse", "HEAD"]).stdout.decode().strip()
    b.require(base == BASE, "installed APK source commit drift")
    listing = b.command(["git", "--no-optional-locks", "-C", str(SOURCE), "ls-tree", "-r", "-z", BASE]).stdout
    for entry in listing.split(b"\0"):
        if not entry:
            continue
        meta, raw_path = entry.split(b"\t", 1)
        path = raw_path.decode("utf-8")
        if any(path == item.strip("/") or path.startswith(item.strip("/")+"/") for item in b.SPARSE):
            b.require(meta.split()[0] in (b"100644", b"100755"), "linked source rejected")
            b.checked(b.SRC/path)
    before = b.original_state()
    b.command(["git", "-c", "credential.helper=", "init",
               "--template="+str(OUT/"host/empty-template"), str(b.SRC)])
    b.git("sparse-checkout", "set", "--no-cone", "--stdin", input_bytes=("\n".join(b.SPARSE)+"\n").encode())
    b.git("checkout", "-b", BRANCH, BASE)
    b.require(not b.git("status", "--porcelain"), "new development tree is not clean")
    b.save("prepared.json", dict(time=b.now(), root=str(ROOT), source=str(b.SRC), branch=BRANCH,
        base=BASE, original=before, scope=sorted(SCOPE), hardware=False,
        authorization="Flutter development-only standing self-test authorization; no merge/release/deploy"))
    print("DEVELOPMENT_SOURCE_READY", b.SRC, BRANCH, flush=True)


def commit(b):
    b.unchanged_original()
    value = b.latest("stage")
    b.require(b.git("branch", "--show-current") == BRANCH and b.git("write-tree") == value["tree"], "stage drift")
    b.require(all(b.record(b.SRC/path) == item for path, item in value["files"].items()), "source drift")
    b.git("-c", "user.name=eitan", "-c", "user.email=example@ggbond", "commit", "-m",
          "WIP(p3-4): validate durable timeout recovery")
    sha = b.git("rev-parse", "HEAD")
    b.save(b.numbered("commit"), dict(time=b.now(), sha=sha, branch=BRANCH, stage=value))
    b.unchanged_original()
    print("DEVELOPMENT_COMMIT", sha, flush=True)


def dispatch(b):
    b.unchanged_original()
    sha = b.latest("commit")["sha"]
    b.require(not (OUT/"apk-dispatch-intent.json").exists(), "reconcile an existing dispatch, do not repeat it")
    token = b.credential()
    b.require(b.api("/repos/"+b.REPO+"/git/ref/heads/"+BRANCH, token)[1]["object"]["sha"] == sha,
              "remote source drift")
    inputs = dict(test_scope="all", build_apk="true", app_id_suffix=".p34retry",
        device_observation="true", observation_target="02:00:00:00:00:01",
        observation_firmware_latest_url="https://p34-runtime-required.invalid/api/public/firmware/latest",
        ota_link_candidate="runtime")
    b.save("apk-dispatch-intent.json", dict(time=b.now(), sha=sha, branch=BRANCH, inputs=inputs))
    code, _ = b.api("/repos/"+b.REPO+"/actions/workflows/flutter-dev-checks.yml/dispatches", token,
                    data=dict(ref=BRANCH, inputs=inputs))
    b.require(code == 204, "dispatch outcome uncertain")
    b.save("apk-dispatch-accepted.json", dict(time=b.now(), sha=sha, status=code, inputs=inputs))
    print("DEBUG_APK_DISPATCH_ACCEPTED", sha, flush=True)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("mode", choices=("prepare", "stage", "commit", "push", "status", "dispatch"))
    args = parser.parse_args()
    b = runtime()
    b.require(Path.cwd() == ROOT and sys.flags.isolated and sys.flags.no_site and sys.dont_write_bytecode,
              "isolated explicit-root execution required")
    for path in (OUT, OUT/"host", OUT/"commands.jsonl", b.SRC, b.SRC/".git"):
        b.checked(path)
    if args.mode == "prepare":
        prepare(b)
    elif args.mode == "commit":
        commit(b)
    elif args.mode == "dispatch":
        dispatch(b)
    else:
        getattr(b, args.mode)()


if __name__ == "__main__":
    main()
