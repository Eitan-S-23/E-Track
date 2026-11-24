"""One stop-and-wait ACK discriminator; no installation or baud mutation."""
import argparse
import json
import os
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parent))
import p34_capacity_session as capacity

ROOT = capacity.ROOT
AREA = capacity.AREA
SESSION = "session-serial-w1"
PRIOR = AREA / "session-rate460-w4-usb2"
TESTS = AREA / "serial-tests-r1/result.json"


def sources():
    return [capacity.record(ROOT / name) for name in (
        "Tools/ota/p34_serial_return.py", "tests/ota/test_p34_serial_return.py",
        "Tools/ota/p34_capacity_session.py", "tests/ota/test_p34_capacity_session.py",
        "Tools/ota/p34_capacity_control.html", "Tools/ota/p34_link_capacity.js",
        "Tools/ota/uart_probe.js", "Tools/ota/test_p34_link_capacity.cjs",
        ".cache/p34-next/prefix_mcu.py")]


def verify_closure(native, owner, usb, restored):
    capacity.require(native.get("retained_verified") is True and native.get("reader_closed") is True and
                     "cleanup_error" not in native and owner.get("forced_termination") is False and
                     owner.get("worker_exit") == 1 and usb.get("port_closed") is True and
                     all(usb.get(k) == 0 for k in ("stop_exit", "server_exit", "launcher_exit")),
                     "previous device outcome/owners unresolved")
    capacity.require(restored.get("baud") == 921600 and
                     restored["commands"][-1]["after"]["known"] == 921600 and
                     native["final_state"]["retained_word"] == 0x5034f708,
                     "921600 restoration not verified")


def prior_records():
    names = ("mcu/closure.json", "owner/closed.json", "phone/usb/closed.json",
             "mcu/restore-initial-baud.json", "trial-142.json")
    values = [json.loads((PRIOR / name).read_bytes()) for name in names]
    verify_closure(*values[:4])
    trial = values[4]
    capacity.require(trial.get("result") == "INCOMPLETE" and trial.get("window") == 4 and
                     trial.get("chunkBytes") == 142 and trial.get("endSent") is False and
                     trial.get("writeUncertain") is False and
                     any(e.get("kind") == "notify" and e.get("hex") ==
                         "030009000000000000010000001c62" for e in trial["events"]),
                     "expected lower-rate ACK-prefix failure required")
    return [capacity.record(PRIOR / name) for name in names]


def run_worker(api=capacity):
    api.SESSION, api.WINDOW = SESSION, 1
    return api.worker(baud=921600, chunks=(142,))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=("start", "worker", "status"))
    args = parser.parse_args()
    capacity.require(Path.cwd() == ROOT and sys.flags.isolated and sys.flags.no_site and
                     sys.dont_write_bytecode, "explicit root and isolated Python required")
    if args.command == "status":
        path = AREA / SESSION / "status.json"
        print(path.read_text() if path.exists() else '{"result":"NOT_STARTED"}')
        return 0
    prior = prior_records()
    tests = json.loads(TESTS.read_bytes())
    capacity.require(tests["passed"] is True and tests["sources"] == sources(), "current self-tests required")
    if args.command == "worker":
        admission = json.loads((AREA / SESSION / "admission.json").read_bytes())
        capacity.require(admission["prior"] == prior, "prior evidence changed")
        return run_worker()
    _, _, _, c = capacity.context(AREA / SESSION)
    capacity.require(not c.OUT.exists(), "spent diagnostic; preserve outcome, no replay")
    c.checked(c.OUT / "admission.json")
    c.checked(c.OUT / "owner")
    os.environ.update(c.environment())
    c.save(c.OUT / "admission.json", dict(tests=capacity.record(TESTS), prior=prior,
        assets=capacity.record(AREA / "assets/result.json"), sources=tests["sources"],
        baud=921600, window=1, chunks=[142], firmware_install=False, extra_system_reports=0))
    print(json.dumps(c.supervisor.owned.launch(c.OUT / "owner", Path(__file__), ["worker"], 900)), flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
