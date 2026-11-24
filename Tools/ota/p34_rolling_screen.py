"""Finite rolling-credit comparison; no new APK, END, installation or reset."""
import argparse
import json
import os
from pathlib import Path
import subprocess
import sys

sys.path.insert(0, str(Path(__file__).resolve().parent))
import p34_batch_screen as batch

capacity = batch.capacity
ROOT = batch.ROOT
AREA = ROOT / ".cache/p34-rolling28"
SESSION = "session-w28"
WINDOW = 28
TESTS = AREA / "tests/result.json"
PRIOR = ROOT / ".cache/p34ab/screen/session-w31"
PINS = {
    "result.json": "31eca0110c352512cf9ed7b13d2244d62af4aeffc729fd1b9a388d6a3e5f346d",
    "mcu/closure.json": "3c7f00dbe24f685c7f6ace3915fe9a5cc6d315177e60989d8b986601646751b5",
    "owner/closed.json": "cb7e529976fc1b830732f860497b3d615724bc243551e8ce8ef1b1f5bbe018ef",
    "phone/usb/closed.json": "2642d86598dbcaec1d0b4a21c8a6169b051fbafcf9891f60c46976ce22aa9656",
}
FAILED = ROOT / ".cache/p34-rolling/session-w31"
FAILURE_PINS = {
    "result.json": "a21e5e0f6de8d6ea37a6e8ac17b34720d0e89f11a95476f2f3913363d615e3f6",
    "mcu/closure.json": "346e1d0f5a5a9f1e04a3e98c01624663a52f1d7f50da244936d5d37bda37efda",
    "owner/closed.json": "34dfc42ff59e1d1d02f07d5e5e2329abb0e22cbf00872d826e1711b22f90986d",
    "phone/usb/closed.json": "46858b573f9f5445b12f114d557ce5a647fd38d4ebc082b13b7dd9ee5584d871",
}


def verify_previous():
    for path, sha in PINS.items():
        capacity.require(capacity.record(PRIOR / path)["sha256"] == sha, "prior screen/closure changed")
    for path, sha in FAILURE_PINS.items():
        capacity.require(capacity.record(FAILED / path)["sha256"] == sha, "reconciled failure changed")


def context(out):
    verify_previous()
    return batch.context(out)


def configure():
    capacity.AREA, capacity.SESSION, capacity.WINDOW = AREA, SESSION, WINDOW
    capacity.TARGET_VERSION, capacity.TARGET_LABEL = 30237, "3.2.37-p34b"
    capacity.context = context


def sources():
    paths = ["Tools/ota/p34_rolling_screen.py", "tests/ota/test_p34_rolling_screen.py",
             "Tools/ota/p34_rolling_capacity.js", "Tools/ota/test_p34_rolling_capacity.cjs",
             "Tools/ota/p34_batch_screen.py", "tests/ota/test_p34_batch_screen.py",
             "Tools/ota/p34_capacity_session.py", "tests/ota/test_p34_capacity_session.py",
             "Tools/ota/p34_capacity_control.html", "Tools/ota/p34_link_capacity.js",
             "Tools/ota/uart_probe.js", "Tools/ota/test_p34_link_capacity.cjs"]
    return [capacity.record(ROOT / p) for p in paths]


def test():
    # Reuse only the contained host environment, never its delivery/commit entry.
    g = capacity.load("rolling_host_env", ROOT / ".cache/project-governance-20260922/run.py")
    g.OUT = TESTS.parent
    capacity.require(not TESTS.exists(), "preserve test evidence")
    env = g.environment()
    commands = [[sys.executable, "-I", "-S", "-B", "-X", "utf8", "-c",
        "import sys,unittest;sys.path.insert(0,'tests/ota');"
        "s=unittest.defaultTestLoader.loadTestsFromNames(['test_p34_rolling_screen',"
        "'test_p34_batch_screen','test_p34_capacity_session']);"
        "r=unittest.TextTestRunner(verbosity=2).run(s);sys.exit(not r.wasSuccessful())"],
        ["node", "--test", "Tools/ota/test_p34_rolling_capacity.cjs", "Tools/ota/test_p34_link_capacity.cjs"]]
    results = []
    for i, command in enumerate(commands):
        path = g.checked(TESTS.parent / (str(i) + ".log"))
        p = subprocess.run(command, cwd=ROOT, env=env, capture_output=True, timeout=180,
                           creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
        with path.open("xb") as stream:
            stream.write(p.stdout + p.stderr)
        results.append(dict(command=command, exit=p.returncode, log=capacity.record(path)))
    value = dict(passed=all(v["exit"] == 0 for v in results), results=results, sources=sources())
    g.io.write_json(ROOT, TESTS, value)
    print(json.dumps(value))
    return 0 if value["passed"] else 1


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=("test", "prepare", "start", "worker", "status"))
    args = parser.parse_args()
    capacity.require(Path.cwd() == ROOT and sys.flags.isolated and sys.flags.no_site and
                     sys.dont_write_bytecode, "explicit root and isolated Python required")
    configure()
    if args.command == "status":
        p = AREA / SESSION / "status.json"
        print(p.read_text() if p.exists() else '{"result":"NOT_STARTED"}')
        return 0
    if args.command == "test":
        return test()
    tests = json.loads(TESTS.read_bytes())
    capacity.require(tests["passed"] is True and tests["sources"] == sources(), "current tests required")
    _, _, _, c = context(AREA / ("assets" if args.command == "prepare" else SESSION))
    if args.command == "prepare":
        capacity.require(not c.OUT.exists(), "preserve assets")
        old = ROOT / ".cache/p34ab/screen/assets/result.json"
        value = c.read(old)
        for key in ("package", "target", "retained", "boot", "decoder"):
            item = value[key]
            capacity.require(capacity.record(Path(item["path"])) == item, "original asset changed")
        capacity.require(value["expected"] == dict(version=30235, imageSha256=batch.IMAGE_SHA),
                         "exact retained image required")
        value["reused_from"] = capacity.record(old)
        value["reason"] = "Same package and firmware; only sender scheduling changes. No decode/build rerun."
        c.save(c.OUT / "result.json", value)
        print("ROLLING_ASSETS_PREPARED")
        return 0
    if args.command == "worker":
        return capacity.worker(baud=921600, chunks=(142, 244), sender="rolling-credit-v1")
    capacity.require(not c.OUT.exists(), "spent screen; preserve outcome")
    bound = (batch.sources(c) + sources() + [capacity.record(PRIOR / p) for p in PINS] +
             [capacity.record(FAILED / p) for p in FAILURE_PINS])
    bound = sorted({v["path"]: v for v in bound}.values(), key=lambda v: v["path"])
    for name in ("admission.json", "owner", "phone", "mcu"):
        c.checked(c.OUT / name)
    os.environ.update(c.environment())
    c.save(c.OUT / "admission.json", dict(tests=capacity.record(TESTS),
        assets=capacity.record(AREA / "assets/result.json"), sources=bound,
        sender="rolling-credit-v1", baud=921600, window=WINDOW, chunks=[142, 244],
        no_end=True, no_install=True, system_reports=0))
    print(json.dumps(c.supervisor.owned.launch(c.OUT / "owner", Path(__file__), ["worker"], 900)), flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
