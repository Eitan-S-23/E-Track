"""Exclusive development validation for bounded post-reboot service discovery."""
import argparse
from pathlib import Path
import runpy
import sys
import types

ROOT = Path(__file__).resolve().parents[2]
SELF = Path(__file__).resolve()
OUT = ROOT / ".cache/p34-discovery-fix"
SOURCE = ROOT / ".cache/p34-connect-fix/src"
BASE = "e29c1392db7a1e0570b588f4d2f2c8d0d9c9c3ad"
BRANCH = "dev/flutter/p3-4-reboot-discovery-20261002"
APP = "app/bluetooth_flutter_Trace/"
SCOPE = {APP + name for name in (
    "lib/services/bluetooth_service.dart", "lib/services/ota_service.dart",
    "test/ota/bluetooth_ota_gatt_cache_test.dart", "test/ota/ota_service_upgrade_test.dart",
    "test/ota/ota_service_session_test.dart", "test/ota/ota_probe_late_attribution_test.dart")}
SCOPE.add("docs/ota-exec-notes/P3-4-reboot-discovery-2026-10-02.md")


def runtime():
    b = runpy.run_path(str(ROOT / "Tools/ota/p34_connect_validation.py"))["runtime"]()
    b.OUT, b.SRC, b.BRANCH, b.host.OUT = OUT, OUT / "src", BRANCH, OUT
    b.ALTERNATES = (SOURCE / ".git/objects", *b.ALTERNATES)
    b.scope_allowed = lambda path: path in SCOPE
    prepare = runpy.run_path(str(ROOT / "Tools/ota/durable_retry_validation.py"))["prepare"]
    b.prepare_discovery = types.FunctionType(prepare.__code__, dict(prepare.__globals__,
        ROOT=ROOT, SELF=SELF, OUT=OUT, SOURCE=SOURCE, BASE=BASE, BRANCH=BRANCH, SCOPE=SCOPE), prepare.__name__)
    return b


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("mode", choices=("prepare", "stage", "commit", "push", "status"))
    args = parser.parse_args()
    b = runtime()
    for p in (OUT, OUT / "host", OUT / "commands.jsonl", b.SRC, b.SRC / ".git"):
        b.checked(p)
    if args.mode == "prepare":
        b.prepare_discovery(b)
    elif args.mode == "commit":
        b.unchanged_original()
        staged = b.latest("stage")
        b.require(b.git("branch", "--show-current") == BRANCH and b.git("write-tree") == staged["tree"], "stage drift")
        b.require(all(b.record(b.SRC / p) == r for p, r in staged["files"].items()), "source drift")
        b.git("-c", "user.name=eitan", "-c", "user.email=example@ggbond", "commit", "-m",
              "WIP(p3-4): bound reboot discovery and retire failed probes")
        sha = b.git("rev-parse", "HEAD")
        b.save(b.numbered("commit"), dict(time=b.now(), sha=sha, branch=BRANCH, stage=staged))
        b.unchanged_original()
        print("DEVELOPMENT_COMMIT", sha, flush=True)
    else:
        getattr(b, args.mode)()


if __name__ == "__main__":
    if not (Path.cwd() == ROOT and sys.flags.isolated and sys.flags.no_site and sys.dont_write_bytecode):
        raise RuntimeError("isolated explicit root required")
    main()
