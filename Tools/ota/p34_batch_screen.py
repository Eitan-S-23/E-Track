"""One non-installing window-31 pair on the verified ACK-batching receiver."""
import argparse
import json
import os
from pathlib import Path
import subprocess
import sys

sys.path.insert(0, str(Path(__file__).resolve().parent))
import p34_capacity_session as capacity

ROOT = capacity.ROOT
AREA = ROOT / ".cache/p34ab/screen"
RUN = "20260930T094904-31700"
REPORT = ROOT / ".cache/p34-session/runs" / RUN / "analysis/1790763251018904100/result.json"
REPORT_SHA = "0d4d621240500ec40f669f404426630cebb2c211d29aaa34e6f40d9c3c25ef29"
IMAGE_SHA = "20712c2f50a85177a1de80b29c9080753bb3b0545778bf389e258c50074608b1"
BOOT_SHA = "55200bb8b9399b5b2fa3e9b9d02d0504bec066f7624d0f293d82cb4244505f62"
TESTS = AREA / "tests/result.json"
SESSION = "session-w31"
_context = None


def verify_prior(report, closure, state):
    require = capacity.require
    require(report.get("result") == "FULL_INSTALL_VERIFIED" and
            report["summary"]["input"]["targetVersionCode"] == 30235 and
            report["summary"]["input"]["targetImageSha256"] == IMAGE_SHA,
            "verified batch installation required")
    require(closure.get("retained_verified") is True and closure.get("reader_closed") is True and
            closure["final_identity"]["app"]["sha256"] == IMAGE_SHA and
            closure["final_identity"]["boot"]["sha256"] == BOOT_SHA,
            "complete batch image/original Boot required")
    final = closure["final_state"]
    require(final["bcb_state"] == 4 and final["confirm_done"] == final["sd_ready"] == 1 and
            final["session"]["state"] == final["session"]["isr_active"] == 0 and
            final["retained_word"] == 0x5034f708, "confirmed idle921600 receiver required")
    require(state.get("result") == "FULL_INSTALL_VERIFIED" and all(
        state[k]["state"] == "CLOSED" and state[k]["receipt"].get("forced_termination") is False and
        state[k]["receipt"].get("worker_exit") == 0 for k in ("worker", "network")),
        "bootstrap owners must close normally")


def build_context(out):
    cli = capacity.load("p34_session", ROOT / "Tools/ota/p34_session.py")
    store = cli.Store(ROOT)
    store.checked(out)
    capacity.require(capacity.record(REPORT)["sha256"] == REPORT_SHA, "bootstrap report changed")
    report = store.read(REPORT)
    for item in (report["inputs"]["plan"], report["after"], report["inputs"]["snapshot"]):
        capacity.require(capacity.record(Path(item["path"])) == item, "bootstrap original changed")
    plan, closure = store.read(report["inputs"]["plan"]["path"]), store.read(report["after"]["path"])
    verify_prior(report, closure, cli.status(store, RUN, "s04"))
    impl = cli.backend(store, Path(plan["profile"]["path"]), "ack-batch-bootstrap")
    c = impl.context(out)
    c.bindings, c.receiver_version = plan["target_bindings"], 30235
    profile = c.bindings["profile"]
    capacity.require(profile["identity"]["version_code"] == 30235 and profile["image"]["sha256"] == IMAGE_SHA,
                     "old sampler rejected")
    for item in (profile["image"], profile["map"], c.bindings["whole_boot"]):
        capacity.require(capacity.record(Path(item["path"])) == item, "sampler input changed")
    symbols = c.helper.bind_receiver(c.m, Path(profile["map"]["path"]).read_text(encoding="utf-8"),
                                     Path(profile["image"]["path"]).read_bytes(), profile)
    capacity.require(symbols == profile["symbols"], "batch map binding mismatch")
    gate = impl.legacy["named"]["restored"]["clock"]["gate"]
    c.flash_addresses = sys.modules["p34_session_backend"].bind_flash_gate(profile, gate["symbol"])
    impl.preflight(c, out)
    return cli, store, impl, c


def context(out):
    global _context
    # One output per process. Keep the same validated context for prepare/worker;
    # immutable source admission and fresh native readback still run afterward.
    if _context is None:
        _context = build_context(out)
    capacity.require(_context[3].OUT == out, "cannot rebind a live context to another output")
    return _context


def configure():
    capacity.AREA, capacity.SESSION, capacity.WINDOW = AREA, SESSION, 31
    capacity.TARGET_VERSION, capacity.TARGET_LABEL = 30237, "3.2.37-p34b"
    capacity.context = context


def sources(c):
    names = ("Tools/ota/p34_batch_screen.py", "tests/ota/test_p34_batch_screen.py",
             "Tools/ota/p34_capacity_session.py", "tests/ota/test_p34_capacity_session.py",
             "Tools/ota/p34_capacity_control.html", "Tools/ota/p34_link_capacity.js",
             "Tools/ota/uart_probe.js", "Tools/ota/test_p34_link_capacity.cjs")
    records = c.sources() + [capacity.record(ROOT / n) for n in names] + [capacity.record(REPORT)]
    return sorted({v["path"]: v for v in records}.values(), key=lambda v: v["path"])


def test(c):
    capacity.require(not TESTS.exists(), "preserve test evidence")
    env = c.environment()
    commands = ([sys.executable, "-I", "-S", "-B", "-X", "utf8", "-c",
                 "import sys,unittest; sys.path.insert(0,'tests/ota'); "
                 "s=unittest.defaultTestLoader.loadTestsFromNames(['test_p34_batch_screen',"
                 "'test_p34_capacity_session']); r=unittest.TextTestRunner(verbosity=2).run(s); "
                 "sys.exit(not r.wasSuccessful())"], ["node", "--test", "Tools/ota/test_p34_link_capacity.cjs"])
    results = []
    for i, command in enumerate(commands):
        path = c.checked(c.OUT / (str(i) + ".log"))
        run = subprocess.run(command, cwd=ROOT, env=env, capture_output=True, timeout=180,
                             creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
        results.append(dict(command=command, exit=run.returncode, log=c.raw(path, run.stdout + run.stderr)))
    result = dict(passed=all(v["exit"] == 0 for v in results), results=results, sources=sources(c))
    c.save(TESTS, result)
    print(json.dumps(dict(passed=result["passed"], report=str(TESTS))))
    return 0 if result["passed"] else 1


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=("test", "prepare", "start", "worker", "status"))
    args = parser.parse_args()
    capacity.require(Path.cwd() == ROOT and sys.flags.isolated and sys.flags.no_site and
                     sys.dont_write_bytecode, "explicit root and isolated Python required")
    configure()
    if args.command == "status":
        path = AREA / SESSION / "status.json"
        print(path.read_text() if path.exists() else '{"result":"NOT_STARTED"}')
        return 0
    _, _, _, c = context(AREA / ("tests" if args.command == "test" else
                                "assets" if args.command == "prepare" else SESSION))
    if args.command == "test":
        return test(c)
    tests = c.read(TESTS)
    capacity.require(tests["passed"] is True and tests["sources"] == sources(c), "current source-bound tests required")
    if args.command == "prepare":
        capacity.prepare()
        return 0
    assets = c.read(AREA / "assets/result.json")
    capacity.require(assets["expected"] == dict(version=30235, imageSha256=IMAGE_SHA), "old diagnostic assets rejected")
    if args.command == "worker":
        return capacity.worker(baud=921600, chunks=(142, 244))
    capacity.require(not c.OUT.exists(), "spent screen; preserve outcome")
    for name in ("admission.json", "owner", "phone", "mcu"):
        c.checked(c.OUT / name)
    os.environ.update(c.environment())
    c.save(c.OUT / "admission.json", dict(tests=capacity.record(TESTS),
        assets=capacity.record(AREA / "assets/result.json"), sources=tests["sources"],
        baud=921600, window=31, chunks=[142, 244], no_end=True, no_install=True, system_reports=0))
    print(json.dumps(c.supervisor.owned.launch(c.OUT / "owner", Path(__file__), ["worker"], 900)), flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
