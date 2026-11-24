"""Exclusive development validation for independently switchable radio policies."""
import argparse
from pathlib import Path
import runpy
import sys
import types

ROOT = Path(__file__).resolve().parents[2]
SELF = Path(__file__).resolve()
OUT = ROOT / ".cache/p34-radio-fix"
SOURCE = ROOT / ".cache/p34-discovery-fix/src"
BASE = "89fee42f548e99eb5bc437aa736d2e9cc8ddf5de"
BRANCH = "dev/flutter/p3-4-radio-policy-20261002"
APP = "app/bluetooth_flutter_Trace/"
SCOPE = {APP + name for name in (
    "lib/ota/ota_experiment_config.dart", "lib/ota/ota_scan_pause.dart",
    "lib/ota/ota_radio_lease.dart", "lib/services/bluetooth_service.dart", "lib/services/ota_service.dart",
    "test/ota/ota_experiment_config_test.dart", "test/ota/ota_scan_pause_test.dart",
    "test/ota/ota_radio_lease_test.dart", "test/ota/bluetooth_ota_radio_policy_test.dart",
    "test/ota/ota_service_upgrade_test.dart")}
SCOPE.add("docs/ota-exec-notes/P3-4-radio-policy-2026-10-02.md")
SCOPE.update({APP + "lib/ota/ota_observation_log.dart",
              APP + "test/ota/ota_observation_log_test.dart",
              "Tools/ota/p3-4-link-stats/observation_capture.py"})


def runtime():
    b = runpy.run_path(str(ROOT / "Tools/ota/p34_discovery_validation.py"))["runtime"]()
    b.OUT, b.SRC, b.BRANCH, b.host.OUT = OUT, OUT / "src", BRANCH, OUT
    b.ALTERNATES = (SOURCE / ".git/objects", *b.ALTERNATES)
    b.scope_allowed = lambda path: path in SCOPE
    prepare = runpy.run_path(str(ROOT / "Tools/ota/durable_retry_validation.py"))["prepare"]
    b.prepare_radio = types.FunctionType(prepare.__code__, dict(prepare.__globals__,
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
        b.prepare_radio(b)
    elif args.mode == "commit":
        b.unchanged_original()
        staged = b.latest("stage")
        b.require(b.git("branch", "--show-current") == BRANCH and b.git("write-tree") == staged["tree"], "stage drift")
        b.require(all(b.record(b.SRC / p) == record for p, record in staged["files"].items()), "source drift")
        b.git("-c", "user.name=eitan", "-c", "user.email=example@ggbond", "commit", "-m",
              "WIP(p3-4): validate owned scan pause and Android priority experiments")
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
