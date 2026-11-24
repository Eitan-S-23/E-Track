"""Source-bound window-four ACK-gap screen on the confirmed 30232 receiver."""
import argparse
import json
import os
from pathlib import Path
import subprocess
import sys

sys.path.insert(0, str(Path(__file__).resolve().parent))
import p34_capacity_session as capacity

ROOT = capacity.ROOT
AREA = ROOT / ".cache/p34ag/screen"
RUN = "20260930T074117-47400"
REPORT = ROOT / ".cache/p34-session/runs" / RUN / "analysis/1790755606402319800/result.json"
REPORT_SHA = "4cda7db7bbd2f3f4c6e57f324dac0f0996bde3661c0a42a1a2953c43a1d4c4f0"
IMAGE_SHA = "ec6bde8aae98a7ae481c1e511191d45d3e3a08b00e198ccd647fc9a5311f10b3"
BOOT_SHA = "55200bb8b9399b5b2fa3e9b9d02d0504bec066f7624d0f293d82cb4244505f62"
TESTS = AREA / "tests/result.json"


def verify_prior(report, closure, state):
    require = capacity.require
    require(report.get("result") == "FULL_INSTALL_VERIFIED" and
            report["summary"]["input"]["targetVersionCode"] == 30232 and
            report["summary"]["input"]["targetImageSha256"] == IMAGE_SHA,
            "confirmed gap installation required")
    require(closure.get("retained_verified") is True and closure.get("reader_closed") is True and
            closure["final_identity"]["app"]["sha256"] == IMAGE_SHA and
            closure["final_identity"]["boot"]["sha256"] == BOOT_SHA,
            "full gap image/original Boot readback required")
    final = closure["final_state"]
    require(final["bcb_state"] == 4 and final["confirm_done"] == final["sd_ready"] == 1 and
            final["session"]["state"] == final["session"]["isr_active"] == 0 and
            final["retained_word"] == 0x5034f708, "confirmed idle 921600 receiver required")
    require(state.get("result") == "FULL_INSTALL_VERIFIED" and all(
        state[k]["state"] == "CLOSED" and state[k]["receipt"].get("forced_termination") is False and
        state[k]["receipt"].get("worker_exit") == 0 for k in ("worker", "network")),
        "bootstrap owners must close normally")


def context(out):
    cli = capacity.load("p34_session", ROOT / "Tools/ota/p34_session.py")
    store = cli.Store(ROOT)
    store.checked(out)
    capacity.require(capacity.record(REPORT)["sha256"] == REPORT_SHA, "bootstrap report changed")
    report = store.read(REPORT)
    for item in (report["inputs"]["plan"], report["after"], report["inputs"]["snapshot"]):
        capacity.require(capacity.record(Path(item["path"])) == item, "bootstrap original changed")
    plan = store.read(report["inputs"]["plan"]["path"])
    closure = store.read(report["after"]["path"])
    verify_prior(report, closure, cli.status(store, RUN, "s04"))
    impl = cli.backend(store, Path(plan["profile"]["path"]), "ack-gap-bootstrap")
    c = impl.context(out)
    c.bindings, c.receiver_version = plan["target_bindings"], 30232
    profile = c.bindings["profile"]
    capacity.require(profile["identity"]["version_code"] == 30232 and
                     profile["image"]["sha256"] == IMAGE_SHA, "wrong sampler identity")
    for item in (profile["image"], profile["map"], c.bindings["whole_boot"]):
        capacity.require(capacity.record(Path(item["path"])) == item, "sampler input changed")
    symbols = c.helper.bind_receiver(c.m, Path(profile["map"]["path"]).read_text(encoding="utf-8"),
                                     Path(profile["image"]["path"]).read_bytes(), profile)
    capacity.require(symbols == profile["symbols"], "new map binding mismatch")
    gate = impl.legacy["named"]["restored"]["clock"]["gate"]
    c.flash_addresses = sys.modules["p34_session_backend"].bind_flash_gate(profile, gate["symbol"])
    impl.preflight(c, out)
    return cli, store, impl, c


def configure():
    capacity.AREA, capacity.SESSION, capacity.WINDOW = AREA, "session-w4", 4
    capacity.TARGET_VERSION, capacity.TARGET_LABEL = 30234, "3.2.34-p34g"
    capacity.context = context


def sources(c):
    names = ("Tools/ota/p34_gap_screen.py", "tests/ota/test_p34_gap_screen.py",
             "Tools/ota/p34_capacity_session.py", "tests/ota/test_p34_capacity_session.py",
             "Tools/ota/p34_capacity_control.html", "Tools/ota/p34_link_capacity.js",
             "Tools/ota/uart_probe.js", "Tools/ota/test_p34_link_capacity.cjs",
             "tests/ota/test_p34_serial_return.py", "Tools/ota/p34_serial_return.py")
    records = c.sources() + [capacity.record(ROOT / n) for n in names] + [capacity.record(REPORT)]
    return sorted({v["path"]: v for v in records}.values(), key=lambda v: v["path"])


def test(c):
    capacity.require(not TESTS.exists(), "preserve existing test result")
    env = c.environment()
    commands = ([sys.executable, "-I", "-S", "-B", "-X", "utf8", "-c",
                 "import sys,unittest; sys.path.insert(0,'tests/ota'); "
                 "s=unittest.defaultTestLoader.loadTestsFromNames(['test_p34_gap_screen',"
                 "'test_p34_capacity_session','test_p34_serial_return']); "
                 "r=unittest.TextTestRunner(verbosity=2).run(s); sys.exit(not r.wasSuccessful())"],
                ["node", "--test", "Tools/ota/test_p34_link_capacity.cjs"])
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
        path = AREA / "session-w4/status.json"
        print(path.read_text() if path.exists() else '{"result":"NOT_STARTED"}')
        return 0
    _, _, _, c = context(AREA / ("tests" if args.command == "test" else
                                "assets" if args.command == "prepare" else "session-w4"))
    if args.command == "test":
        return test(c)
    tests = c.read(TESTS)
    capacity.require(tests["passed"] is True and tests["sources"] == sources(c), "current source-bound tests required")
    if args.command == "prepare":
        capacity.prepare()
        return 0
    assets = c.read(AREA / "assets/result.json")
    capacity.require(assets["expected"] == dict(version=30232, imageSha256=IMAGE_SHA), "old diagnostic assets rejected")
    if args.command == "worker":
        return capacity.worker(baud=921600, chunks=(142,))
    capacity.require(not c.OUT.exists(), "spent screen; preserve outcome")
    for name in ("admission.json", "owner", "phone", "mcu"):
        c.checked(c.OUT / name)
    os.environ.update(c.environment())
    c.save(c.OUT / "admission.json", dict(tests=capacity.record(TESTS),
        assets=capacity.record(AREA / "assets/result.json"), sources=tests["sources"],
        baud=921600, window=4, chunks=[142], no_end=True, no_install=True, system_reports=0))
    print(json.dumps(c.supervisor.owned.launch(c.OUT / "owner", Path(__file__), ["worker"], 900)), flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
