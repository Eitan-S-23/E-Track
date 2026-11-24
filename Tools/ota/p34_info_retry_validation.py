"""Development-only validation of bounded same-link INFO retries; no device I/O."""
import argparse
from pathlib import Path
import runpy
import sys
import types

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / ".cache/p34-info-retry"
SOURCE = ROOT / ".cache/p34-phy-logfix/src"
BASE = "b85f50aae66f51895aa4f9bbb9a82732138bae3b"
BRANCH = "dev/flutter/p3-4-info-retry-20261004"
APP = "app/bluetooth_flutter_Trace/"
SCOPE = {APP + name for name in (
    "lib/ota/ota_probe_retry.dart", "lib/ota/ota_experiment_config.dart",
    "lib/services/ota_service.dart", "test/ota/ota_probe_retry_test.dart",
    "test/ota/ota_experiment_config_test.dart", "test/ota/ota_service_upgrade_test.dart")}
SCOPE.add("docs/ota-exec-notes/P3-4-info-retry-2026-10-04.md")


def runtime():
    b = runpy.run_path(str(ROOT / "Tools/ota/p34_phy_logfix_validation.py"))["runtime"]()
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
    p.add_argument("mode", choices=("prepare", "stage", "commit", "push", "status", "logs", "dispatch", "collect"))
    p.add_argument("--run", type=int)
    p.add_argument("--attempt", type=int, choices=(1, 2, 3), default=1)
    a = p.parse_args()
    if not (Path.cwd() == ROOT and sys.flags.isolated and sys.flags.no_site and sys.dont_write_bytecode):
        raise RuntimeError("isolated explicit project root required")
    b = runtime()
    for path in (OUT, OUT / "host", OUT / "commands.jsonl", b.SRC, b.SRC / ".git"):
        b.checked(path)
    if a.mode in ("logs", "dispatch", "collect"):
        if a.mode == "dispatch":
            original_save = b.save
            def save(path, value):
                if path == "apk-g1/intent.json":
                    value = dict(value, purpose="bounded same-link INFO retry experiment; same package and fixed signer")
                return original_save(path, value)
            b.save = save
        entry = runpy.run_path(str(ROOT / "Tools/ota/p34_phy_artifacts.py"))["main"]
        original = runpy.run_path
        def load(path):
            if Path(path) == ROOT / "Tools/ota/p34_phy_validation.py":
                return dict(runtime=lambda: b)
            return original(path)
        entry.__globals__["runpy"] = types.SimpleNamespace(run_path=load)
        entry()
    elif a.mode == "prepare":
        b.prepare_candidate(b)
    elif a.mode == "commit":
        b.unchanged_original()
        staged = b.latest("stage")
        b.require(b.git("branch", "--show-current") == BRANCH and
                  b.git("write-tree") == staged["tree"], "stage drift")
        b.require(all(b.record(b.SRC / path) == item for path, item in staged["files"].items()), "source drift")
        b.git("-c", "user.name=eitan", "-c", "user.email=example@ggbond", "commit", "-m",
              "WIP(p3-4): validate configurable bounded same-link INFO retries")
        sha = b.git("rev-parse", "HEAD")
        b.save(b.numbered("commit"), dict(time=b.now(), sha=sha, branch=BRANCH, stage=staged))
        b.unchanged_original()
        print("DEVELOPMENT_COMMIT", sha, flush=True)
    else:
        getattr(b, a.mode)()
