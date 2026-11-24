"""Exclusive CI development signing remediation; never production signing."""
import argparse
from pathlib import Path
import runpy
import sys
import types

ROOT = Path(__file__).resolve().parents[2]
SELF = Path(__file__).resolve()
OUT = ROOT / ".cache/p34-signing"
SOURCE = ROOT / ".cache/p34-reconnect/src"
BASE = "64a53a7f4aa3fb64804c768c2857d939e168ae1a"
BRANCH = "dev/flutter/fixed-development-signing-20261001"
SCOPE = {
    ".github/workflows/flutter-dev-checks.yml",
    "Tools/flutter/dev_apk.py",
    "app/bluetooth_flutter_Trace/android/app/build.gradle.kts",
    "tests/ota/test_flutter_dev_apk.py",
    "tests/ota/test_flutter_dev_checks.py",
    "docs/flutter-development-validation.md",
}


def runtime():
    old = runpy.run_path(str(ROOT / "Tools/ota/p34_reconnect_validation.py"))
    b = old["runtime"]()
    b.OUT, b.SRC, b.BRANCH, b.host.OUT = OUT, OUT / "src", BRANCH, OUT
    b.ALTERNATES = (SOURCE / ".git/objects", *b.ALTERNATES)
    b.scope_allowed = lambda path: path in SCOPE
    prepare = runpy.run_path(str(ROOT / "Tools/ota/durable_retry_validation.py"))["prepare"]
    scope = dict(prepare.__globals__, ROOT=ROOT, SELF=SELF, OUT=OUT,
                 SOURCE=SOURCE, BASE=BASE, BRANCH=BRANCH, SCOPE=SCOPE)
    b.prepare_signing = types.FunctionType(prepare.__code__, scope, prepare.__name__)
    return b


def preflight(b):
    for path in (OUT, b.SRC, b.SRC / ".git", OUT / "commands.jsonl", OUT / "prepared.json"):
        b.checked(path)
    for name in SCOPE:
        b.checked(b.SRC / name)
    if (b.SRC / ".git").exists():
        for path in (b.SRC / ".git").rglob("*"):
            b.checked(path)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("mode", choices=("prepare", "stage", "commit", "push", "status", "host-tests"))
    args = parser.parse_args()
    b = runtime()
    b.require(Path.cwd() == ROOT and sys.flags.isolated and sys.flags.no_site and sys.dont_write_bytecode,
              "isolated explicit root required")
    preflight(b)
    if args.mode == "prepare":
        b.prepare_signing(b)
    elif args.mode == "commit":
        b.unchanged_original()
        staged = b.latest("stage")
        b.require(b.git("branch", "--show-current") == BRANCH and b.git("write-tree") == staged["tree"], "stage drift")
        b.require(all(b.record(b.SRC / p) == r for p, r in staged["files"].items()), "source drift")
        b.git("-c", "user.name=eitan", "-c", "user.email=example@ggbond", "commit", "-m",
              "WIP: pin dedicated development APK signing")
        sha = b.git("rev-parse", "HEAD")
        b.save(b.numbered("commit"), dict(time=b.now(), sha=sha, branch=BRANCH, stage=staged))
        b.unchanged_original()
        print("DEVELOPMENT_COMMIT", sha)
    else:
        getattr(b, args.mode.replace("-", "_"))()
