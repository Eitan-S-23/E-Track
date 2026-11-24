"""Isolated, checks-only development of bounded post-reboot INFO retries."""
import argparse
from pathlib import Path
import runpy
import sys
import types

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / ".cache/p34-probe-fix"
SOURCE = ROOT / ".cache/p34-batch-fix/src"
BASE = "70a41c848099b3051a5244abaae899bd9d6027d5"
BRANCH = "dev/flutter/p3-4-probe-reuse-20261003"
APP = "app/bluetooth_flutter_Trace/"
SCOPE = {APP + name for name in (
    "lib/services/ota_service.dart", "lib/ota/ota_probe_retry.dart",
    "lib/ota/ota_experiment_config.dart", "test/ota/ota_experiment_config_test.dart",
    "test/ota/ota_probe_retry_test.dart", "test/ota/ota_service_upgrade_test.dart")}
SCOPE.add("docs/ota-exec-notes/P3-4-probe-reuse-2026-10-03.md")


def runtime():
    b = runpy.run_path(str(ROOT / "Tools/ota/p34_batch_validation.py"))["runtime"]()
    b.OUT, b.SRC, b.BRANCH, b.host.OUT = OUT, OUT / "src", BRANCH, OUT
    b.ALTERNATES = (SOURCE / ".git/objects", *b.ALTERNATES)
    b.scope_allowed = lambda path: path in SCOPE
    prepare = runpy.run_path(str(ROOT / "Tools/ota/durable_retry_validation.py"))["prepare"]
    b.prepare_probe = types.FunctionType(prepare.__code__, dict(prepare.__globals__,
        ROOT=ROOT, SELF=Path(__file__), OUT=OUT, SOURCE=SOURCE, BASE=BASE,
        BRANCH=BRANCH, SCOPE=SCOPE), prepare.__name__)
    return b


if __name__ == "__main__":
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("mode", choices=("prepare", "stage", "commit", "push", "status"))
    a = p.parse_args()
    if not (Path.cwd() == ROOT and sys.flags.isolated and sys.flags.no_site and sys.dont_write_bytecode):
        raise RuntimeError("isolated explicit root required")
    b = runtime()
    for path in (OUT, OUT / "host", OUT / "commands.jsonl", b.SRC, b.SRC / ".git"):
        b.checked(path)
    if a.mode == "prepare":
        b.prepare_probe(b)
    elif a.mode == "commit":
        b.unchanged_original()
        staged = b.latest("stage")
        b.require(b.git("branch", "--show-current") == BRANCH and
                  b.git("write-tree") == staged["tree"], "stage drift")
        b.require(all(b.record(b.SRC / path) == item for path, item in staged["files"].items()),
                  "source drift")
        b.git("-c", "user.name=eitan", "-c", "user.email=example@ggbond", "commit", "-m",
              "WIP(p3-4): validate bounded same-link reboot INFO retries")
        sha = b.git("rev-parse", "HEAD")
        b.save(b.numbered("commit"), dict(time=b.now(), sha=sha, branch=BRANCH, stage=staged))
        b.unchanged_original()
        print("DEVELOPMENT_COMMIT", sha, flush=True)
    else:
        getattr(b, a.mode)()
