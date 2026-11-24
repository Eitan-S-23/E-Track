"""Fresh development validation for PHY recorder integration; no device work."""
import argparse
import re
from pathlib import Path
import runpy
import sys
import types

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / ".cache/p34-phy-logfix"
SOURCE = ROOT / ".cache/p34-phy/src"
BASE = "41d147a94294911929fba08478ab0b5337ed1107"
BRANCH = "dev/flutter/p3-4-phy-logfix-20261004"
APP = "app/bluetooth_flutter_Trace/"
SCOPE = {APP + name for name in (
    "lib/ota/ota_observation_log.dart", "test/ota/ota_observation_log_test.dart",
    "test/ota/ota_service_upgrade_test.dart")}
SCOPE.add("docs/ota-exec-notes/P3-4-phy-logfix-2026-10-04.md")
SCOPE.update({"Tools/ota/p3-4-link-stats/observation_capture.py",
              "tests/ota/test_p3_4_observation_capture.py"})


def runtime():
    b = runpy.run_path(str(ROOT / "Tools/ota/p34_phy_validation.py"))["runtime"]()
    b.OUT, b.SRC, b.BRANCH, b.host.OUT = OUT, OUT / "src", BRANCH, OUT
    b.ALTERNATES = (SOURCE / ".git/objects", *b.ALTERNATES)
    b.scope_allowed = lambda path: path in SCOPE
    prepare = runpy.run_path(str(ROOT / "Tools/ota/durable_retry_validation.py"))["prepare"]
    b.prepare_candidate = types.FunctionType(prepare.__code__, dict(prepare.__globals__,
        ROOT=ROOT, SELF=Path(__file__), OUT=OUT, SOURCE=SOURCE, BASE=BASE,
        BRANCH=BRANCH, SCOPE=SCOPE), prepare.__name__)
    return b


def host_tests(b):
    out = b.checked(OUT / b.numbered("host-tests").removesuffix(".json"))
    b.require(not out.exists(), "preserve host test evidence")
    for path in (out, out / "tests.log", out / "result.json",
                 b.SRC / ".cache/p3-4-observation-capture-tests"):
        b.checked(path)
    b.git("diff", "--check")
    print(b.git("diff", "--stat"), flush=True)
    test = b.SRC / "tests/ota/test_p3_4_observation_capture.py"
    result = b.command([sys.executable, "-I", "-S", "-B", "-X", "utf8", str(test)],
                       cwd=b.SRC, check=False, timeout=180)
    raw = result.stdout + result.stderr
    out.mkdir(parents=True)
    with b.checked(out / "tests.log").open("xb") as stream:
        stream.write(raw)
    counts = re.findall(rb"Ran (\d+) tests", raw)
    value = dict(passed=result.returncode == 0, exit=result.returncode,
        count=int(counts[-1]) if counts else None, test=b.record(test),
        log=b.record(out / "tests.log"), flutter_executed=False)
    b.save(out / "result.json", value)
    print(raw.decode("utf-8", "replace")[-6000:], flush=True)
    b.require(value["passed"] and value["count"] is not None, "host tests failed")


if __name__ == "__main__":
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("mode", choices=("prepare", "stage", "commit", "push", "status", "host-tests"))
    a = p.parse_args()
    if not (Path.cwd() == ROOT and sys.flags.isolated and sys.flags.no_site and sys.dont_write_bytecode):
        raise RuntimeError("isolated explicit root required")
    b = runtime()
    for path in (OUT, OUT / "host", OUT / "commands.jsonl", b.SRC, b.SRC / ".git"):
        b.checked(path)
    if a.mode == "prepare":
        b.prepare_candidate(b)
    elif a.mode == "host-tests":
        host_tests(b)
    elif a.mode == "commit":
        b.unchanged_original()
        staged = b.latest("stage")
        b.require(b.git("branch", "--show-current") == BRANCH and
                  b.git("write-tree") == staged["tree"], "stage drift")
        b.require(all(b.record(b.SRC / path) == item for path, item in staged["files"].items()), "source drift")
        b.git("-c", "user.name=eitan", "-c", "user.email=example@ggbond", "commit", "-m",
              "fix(p3-4): register PHY diagnostics and test the enabled capture sink")
        sha = b.git("rev-parse", "HEAD")
        b.save(b.numbered("commit"), dict(time=b.now(), sha=sha, branch=BRANCH, stage=staged))
        b.unchanged_original()
        print("DEVELOPMENT_COMMIT", sha, flush=True)
    else:
        getattr(b, a.mode)()
