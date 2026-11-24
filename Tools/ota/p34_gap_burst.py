"""Escalate the clean gap window-four screen to one window-31 pair."""
import argparse
import json
import os
from pathlib import Path
import subprocess
import sys

sys.path.insert(0, str(Path(__file__).resolve().parent))
import p34_gap_screen as gap

capacity = gap.capacity
ROOT, AREA = gap.ROOT, gap.AREA
SESSION = "session-w31"
TESTS = AREA / "tests-w31/result.json"
PRIOR = AREA / "session-w4"


def verify_screen(result, native, owner, usb):
    capacity.require(result.get("result") == "CAPACITY_SCREEN_VERIFIED" and
                     result.get("no_end") is True and result.get("no_install") is True and
                     len(result["trials"]) == 1 and result["trials"][0]["window"] == 4 and
                     result["trials"][0]["native"]["clean_counters"] is True,
                     "clean window-four prerequisite missing")
    capacity.require(owner.get("forced_termination") is False and owner.get("worker_exit") == 0 and
                     usb.get("port_closed") is True and all(usb.get(k) == 0 for k in
                     ("stop_exit", "server_exit", "launcher_exit")), "prior screen owners unresolved")
    capacity.require(native.get("retained_verified") is True and native.get("reader_closed") is True and
                     native["final_identity"]["app"]["sha256"] == gap.IMAGE_SHA and
                     native["final_identity"]["boot"]["sha256"] == gap.BOOT_SHA and
                     native["final_state"]["retained_word"] == 0x5034f708, "prior retained image/rate changed")
    capacity.noncommitted_terminal(native["final_state"], result["trials"][0]["frames"])


def prior_records():
    names = ("result.json", "mcu/closure.json", "owner/closed.json", "phone/usb/closed.json")
    values = [json.loads((PRIOR / n).read_bytes()) for n in names]
    verify_screen(*values)
    original = values[0]["trials"][0]["original"]
    capacity.require(capacity.record(Path(original["path"])) == original, "original window-four trial changed")
    for item in values[1]["final_identity"].values():
        capacity.require(capacity.record(Path(item["path"])) == item, "prior full readback changed")
    return [capacity.record(PRIOR / n) for n in names] + [original]


def sources(c):
    return gap.sources(c) + [capacity.record(ROOT / n) for n in (
        "Tools/ota/p34_gap_burst.py", "tests/ota/test_p34_gap_burst.py")]


def run_worker(api=capacity):
    api.SESSION, api.WINDOW = SESSION, 31
    return api.worker(baud=921600, chunks=(142, 244))


def test(c):
    capacity.require(not TESTS.exists(), "preserve test evidence")
    env = c.environment()
    commands = ([sys.executable, "-I", "-S", "-B", "-X", "utf8", "-c",
                 "import sys,unittest; sys.path.insert(0,'tests/ota'); "
                 "s=unittest.defaultTestLoader.loadTestsFromNames(['test_p34_gap_burst',"
                 "'test_p34_gap_screen','test_p34_capacity_session','test_p34_serial_return']); "
                 "r=unittest.TextTestRunner(verbosity=2).run(s); sys.exit(not r.wasSuccessful())"],
                ["node", "--test", "Tools/ota/test_p34_link_capacity.cjs"])
    results = []
    for i, command in enumerate(commands):
        log = c.checked(c.OUT / (str(i) + ".log"))
        run = subprocess.run(command, cwd=ROOT, env=env, capture_output=True, timeout=180,
                             creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
        results.append(dict(command=command, exit=run.returncode, log=c.raw(log, run.stdout + run.stderr)))
    passed = all(v["exit"] == 0 for v in results)
    c.save(TESTS, dict(passed=passed, sources=sources(c), results=results))
    print(json.dumps(dict(passed=passed, report=str(TESTS))))
    return 0 if passed else 1


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=("test", "start", "worker", "status"))
    args = parser.parse_args()
    capacity.require(Path.cwd() == ROOT and sys.flags.isolated and sys.flags.no_site and
                     sys.dont_write_bytecode, "explicit root and isolated Python required")
    if args.command == "status":
        path = AREA / SESSION / "status.json"
        print(path.read_text() if path.exists() else '{"result":"NOT_STARTED"}')
        return 0
    gap.configure()
    prior = prior_records()
    _, _, _, c = gap.context(AREA / ("tests-w31" if args.command == "test" else SESSION))
    if args.command == "test":
        return test(c)
    tests = c.read(TESTS)
    capacity.require(tests["passed"] is True and tests["sources"] == sources(c), "current burst self-tests required")
    if args.command == "worker":
        capacity.require(c.read(c.OUT / "admission.json")["prior"] == prior, "prior screen evidence changed")
        return run_worker()
    capacity.require(not c.OUT.exists(), "spent pair; no replay")
    for name in ("admission.json", "owner", "phone", "mcu"):
        c.checked(c.OUT / name)
    os.environ.update(c.environment())
    c.save(c.OUT / "admission.json", dict(tests=capacity.record(TESTS), prior=prior,
        assets=capacity.record(AREA / "assets/result.json"), sources=tests["sources"],
        baud=921600, window=31, chunks=[142, 244], no_end=True, no_install=True, system_reports=0))
    print(json.dumps(c.supervisor.owned.launch(c.OUT / "owner", Path(__file__), ["worker"], 900)), flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
