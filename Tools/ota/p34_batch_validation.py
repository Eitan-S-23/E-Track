"""Default-off three-frame sender development checks; no APK or hardware action."""
import argparse
from pathlib import Path
import runpy
import sys
import types

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / ".cache/p34-batch-fix"
SOURCE = ROOT / ".cache/p34-radio-fix/src"
BASE = "24ce23842d80241731eee335e60688447a55380b"
BRANCH = "dev/flutter/p3-4-three-frame-20261002"
APP = "app/bluetooth_flutter_Trace/"
SCOPE = {APP + name for name in (
    "lib/ota/ota_ble_transport.dart", "test/ota/ota_ble_transport_test.dart",
    "lib/ota/ota_experiment_config.dart", "test/ota/ota_experiment_config_test.dart",
    "lib/ota/ota_link_stats.dart", "lib/services/ota_service.dart",
    "test/ota/ota_service_upgrade_test.dart")}
SCOPE.add("docs/ota-exec-notes/P3-4-three-frame-2026-10-02.md")
SCOPE.update({"Tools/ota/p3-4-link-stats/batch_timing.py", "tests/ota/test_p34_batch_timing.py"})
SCOPE.add(".github/workflows/flutter-dev-checks.yml")


def runtime():
    b = runpy.run_path(str(ROOT / "Tools/ota/p34_radio_validation.py"))["runtime"]()
    b.OUT, b.SRC, b.BRANCH, b.host.OUT = OUT, OUT / "src", BRANCH, OUT
    b.ALTERNATES = (SOURCE / ".git/objects", *b.ALTERNATES)
    b.scope_allowed = lambda path: path in SCOPE
    prepare = runpy.run_path(str(ROOT / "Tools/ota/durable_retry_validation.py"))["prepare"]
    b.prepare_batch = types.FunctionType(prepare.__code__, dict(prepare.__globals__,
        ROOT=ROOT, SELF=Path(__file__), OUT=OUT, SOURCE=SOURCE, BASE=BASE,
        BRANCH=BRANCH, SCOPE=SCOPE), prepare.__name__)
    return b


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("mode", choices=("prepare", "stage", "commit", "push", "status"))
    args = parser.parse_args()
    assert Path.cwd() == ROOT and sys.flags.isolated and sys.flags.no_site and sys.dont_write_bytecode
    b = runtime()
    for path in (OUT, OUT / "host", OUT / "commands.jsonl", b.SRC, b.SRC / ".git"):
        b.checked(path)
    if args.mode == "prepare":
        b.prepare_batch(b)
    elif args.mode == "commit":
        b.unchanged_original()
        staged = b.latest("stage")
        b.require(b.git("branch", "--show-current") == BRANCH and
                  b.git("write-tree") == staged["tree"], "stage drift")
        b.require(all(b.record(b.SRC / p) == item for p, item in staged["files"].items()), "source drift")
        b.git("-c", "user.name=eitan", "-c", "user.email=example@ggbond", "commit", "-m",
              "WIP(p3-4): validate default-off bounded DATA batching")
        sha = b.git("rev-parse", "HEAD")
        b.save(b.numbered("commit"), dict(time=b.now(), sha=sha, branch=BRANCH, stage=staged))
        b.unchanged_original()
        print("DEVELOPMENT_COMMIT", sha)
    else:
        getattr(b, args.mode)()
