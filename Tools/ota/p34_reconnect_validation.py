"""Exclusive development validation for configurable post-OTA INFO probes."""
import argparse
from pathlib import Path
import runpy
import sys
import types

ROOT = Path(__file__).resolve().parents[2]
SELF = Path(__file__).resolve()
OUT = ROOT / ".cache/p34-reconnect"
SOURCE = ROOT / ".cache/p34-next/validation/src"
BASE = "aea62c6490a529a47f74dde86669dc3e3c7605ff"
BRANCH = "dev/flutter/p3-4-reconnect-20261001"
APP = "app/bluetooth_flutter_Trace/"
SCOPE = {
    APP + "lib/ota/ota_experiment_config.dart",
    APP + "lib/services/ota_service.dart",
    APP + "test/ota/ota_experiment_config_test.dart",
    APP + "test/ota/ota_service_upgrade_test.dart",
    "docs/ota-exec-notes/P3-4-reconnect-probe-2026-10-01.md",
}


def runtime():
    old = runpy.run_path(str(ROOT / ".cache/p34-next/validate.py"))
    b = old["runtime"]()
    b.OUT, b.SRC, b.BRANCH, b.host.OUT = OUT, OUT / "src", BRANCH, OUT
    b.ALTERNATES = (SOURCE / ".git/objects", *b.ALTERNATES)
    b.scope_allowed = lambda path: path in SCOPE
    prepare = runpy.run_path(str(ROOT / "Tools/ota/durable_retry_validation.py"))["prepare"]
    namespace = dict(prepare.__globals__, ROOT=ROOT, SELF=SELF, OUT=OUT,
                     SOURCE=SOURCE, BASE=BASE, BRANCH=BRANCH, SCOPE=SCOPE)
    b.prepare_reconnect = types.FunctionType(prepare.__code__, namespace, prepare.__name__)
    for name in ("preflight", "dispatch"):
        fn = old[name]
        scope = dict(fn.__globals__, ROOT=ROOT, SELF=SELF, OUT=OUT,
                     SOURCE=SOURCE, BASE=BASE, BRANCH=BRANCH, SCOPE=SCOPE)
        setattr(b, "reconnect_" + name, types.FunctionType(fn.__code__, scope, name))
    return b


def commit(b):
    b.unchanged_original()
    value = b.latest("stage")
    b.require(b.git("branch", "--show-current") == BRANCH and b.git("write-tree") == value["tree"], "stage drift")
    b.require(all(b.record(b.SRC / path) == item for path, item in value["files"].items()), "source drift")
    b.git("-c", "user.name=eitan", "-c", "user.email=example@ggbond", "commit", "-m",
          "WIP(p3-4): validate bounded post-OTA reconnect probes")
    sha = b.git("rev-parse", "HEAD")
    b.save(b.numbered("commit"), dict(time=b.now(), sha=sha, branch=BRANCH, stage=value))
    b.unchanged_original()
    print("DEVELOPMENT_COMMIT", sha, flush=True)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("mode", choices=("preflight", "prepare", "stage", "commit", "push", "status", "dispatch", "host-tests"))
    args = parser.parse_args()
    b = runtime()
    b.require(Path.cwd() == ROOT and sys.flags.isolated and sys.flags.no_site and sys.dont_write_bytecode,
              "isolated explicit project root required")
    b.reconnect_preflight(b)
    if args.mode == "preflight":
        print("OUTPUT_BOUNDARY_VERIFIED", ROOT, flush=True)
    elif args.mode == "prepare":
        b.prepare_reconnect(b)
    elif args.mode == "commit":
        commit(b)
    elif args.mode == "dispatch":
        b.reconnect_dispatch(b)
    else:
        getattr(b, args.mode.replace("-", "_"))()
