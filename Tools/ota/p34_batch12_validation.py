"""Exclusive development-only validation of bounded twelve-frame DATA batches."""
import argparse
from pathlib import Path
import runpy
import sys
import types

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / ".cache/p34-batch12"
SOURCE = ROOT / ".cache/p34-probe-fix/src"
BASE = "fedb3fd748e005cd3d1160d44d679eb7e63971e5"
BRANCH = "dev/flutter/p3-4-batch12-20261003"
APP = "app/bluetooth_flutter_Trace/"
SCOPE = {APP + name for name in (
    "lib/ota/ota_ble_transport.dart", "lib/ota/ota_link_stats.dart", "lib/services/ota_service.dart",
    "lib/ota/ota_experiment_config.dart", "test/ota/ota_experiment_config_test.dart",
    "test/ota/ota_ble_transport_test.dart", "test/ota/ota_service_upgrade_test.dart")}
SCOPE.update({"Tools/ota/p3-4-link-stats/batch_timing.py", "tests/ota/test_p34_batch_timing.py",
              "docs/ota-exec-notes/P3-4-batch12-2026-10-03.md"})


def runtime():
    b = runpy.run_path(str(ROOT / "Tools/ota/p34_probe_validation.py"))["runtime"]()
    b.OUT, b.SRC, b.BRANCH, b.host.OUT = OUT, OUT / "src", BRANCH, OUT
    b.ALTERNATES = (SOURCE / ".git/objects", *b.ALTERNATES)
    b.scope_allowed = lambda path: path in SCOPE
    prepare = runpy.run_path(str(ROOT / "Tools/ota/durable_retry_validation.py"))["prepare"]
    b.prepare_candidate = types.FunctionType(prepare.__code__, dict(prepare.__globals__,
        ROOT=ROOT, SELF=Path(__file__), OUT=OUT, SOURCE=SOURCE, BASE=BASE,
        BRANCH=BRANCH, SCOPE=SCOPE), prepare.__name__)
    return b


if __name__ == "__main__":
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("mode", choices=("prepare", "stage", "commit", "push", "status"))
    args = p.parse_args()
    if not (Path.cwd() == ROOT and sys.flags.isolated and sys.flags.no_site and sys.dont_write_bytecode):
        raise RuntimeError("isolated explicit root required")
    b = runtime()
    for path in (OUT, OUT / "host", OUT / "commands.jsonl", b.SRC, b.SRC / ".git"):
        b.checked(path)
    if args.mode == "prepare":
        b.prepare_candidate(b)
    elif args.mode == "commit":
        b.unchanged_original()
        staged = b.latest("stage")
        b.require(b.git("branch", "--show-current") == BRANCH and
                  b.git("write-tree") == staged["tree"], "stage drift")
        b.require(all(b.record(b.SRC / path) == item for path, item in staged["files"].items()), "source drift")
        b.git("-c", "user.name=eitan", "-c", "user.email=example@ggbond", "commit", "-m",
              "WIP(p3-4): validate bounded twelve-frame DATA batching")
        sha = b.git("rev-parse", "HEAD")
        b.save(b.numbered("commit"), dict(time=b.now(), sha=sha, branch=BRANCH, stage=staged))
        b.unchanged_original()
        print("DEVELOPMENT_COMMIT", sha, flush=True)
    else:
        getattr(b, args.mode)()
