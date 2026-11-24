"""One reversible460800 return-path discriminator, not a50KB/s configuration."""
import argparse
import importlib.util
import json
import os
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[2]
AREA = ROOT / ".cache/p34-target50"
SESSION = "session-rate460-w4"
TESTS = AREA / "rate460-tests-r2/result.json"
BOUNDARY = AREA / "hci-export/ack-boundary.json"


def load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


CAPACITY = load("rate_capacity", ROOT / "Tools/ota/p34_capacity_session.py")
require, record = CAPACITY.require, CAPACITY.record


def sources():
    return [record(ROOT / name) for name in (
        "Tools/ota/p34_rate_return.py", "tests/ota/test_p34_rate_return.py",
        "Tools/ota/p34_capacity_session.py", "tests/ota/test_p34_capacity_session.py",
        "Tools/ota/p34_capacity_control.html", "Tools/ota/p34_link_capacity.js",
        "Tools/ota/uart_probe.js", "Tools/ota/test_p34_link_capacity.cjs",
        ".cache/p34-next/prefix_mcu.py")]


def require_prior(value):
    require(value.get("result") == "CORRUPTION_ALREADY_PRESENT_AT_HCI" and
            value.get("notifications_byte_identical") is True and value.get("retained_verified") is True and
            value.get("missing_ack3_prefix_hex") == "a55a82010300", "original HCI discriminator required")


def validate_prior():
    value = json.loads(BOUNDARY.read_bytes())
    require_prior(value)
    for item in value["inputs"].values():
        require(record(Path(item["path"])) == item, "original comparison input changed")
    previous = AREA / "session-hci-w4"
    owner = json.loads((previous / "owner/closed.json").read_bytes())
    native = json.loads((previous / "mcu/closure.json").read_bytes())
    usb = json.loads((previous / "phone/usb/closed.json").read_bytes())
    require(owner["forced_termination"] is False and owner["worker_exit"] == 1 and
            native["reader_closed"] is True and native["retained_verified"] is True and
            usb["port_closed"] is True and usb["stop_exit"] == usb["server_exit"] == usb["launcher_exit"] == 0,
            "prior probe outcome/owners unresolved")
    report = json.loads((AREA / "hci-export/probe-evidence/phone/usb/closed.json").read_bytes())
    require(report["port_closed"] is True and report["stop_exit"] == report["server_exit"] == report["launcher_exit"] == 0,
            "report2 USB still active")
    return record(BOUNDARY)


def run_worker(capacity=CAPACITY):
    capacity.SESSION, capacity.WINDOW = SESSION, 4
    return capacity.worker(baud=460800)


def retry_ready(result, readiness, owner):
    require(result.get("error") == "RuntimeError: exact phone did not become online in the bounded USB window" and
            result.get("trials") == [] and readiness.get("online") is False and
            owner.get("worker_exit") == 1 and owner.get("forced_termination") is False,
            "fresh USB scope allowed only for the known pre-device failure")


def main():
    global SESSION
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=("start", "worker", "status"))
    parser.add_argument("--session", choices=("session-rate460-w4", "session-rate460-w4-usb2"), default=SESSION)
    args = parser.parse_args()
    SESSION = args.session
    require(Path.cwd() == ROOT and sys.flags.isolated and sys.flags.no_site and sys.dont_write_bytecode,
            "explicit root and isolated Python required")
    if args.command == "status":
        path = AREA / SESSION / "status.json"
        print(path.read_text() if path.exists() else '{"result":"NOT_STARTED"}')
        return 0
    prior = validate_prior()
    if SESSION.endswith("-usb2"):
        old = AREA / "session-rate460-w4"
        retry_ready(json.loads((old / "result.json").read_bytes()),
                    json.loads((old / "phone/usb/transport-ready.json").read_bytes()),
                    json.loads((old / "owner/closed.json").read_bytes()))
        require(not (old / "mcu/initial-app.bin").exists() and not (old / "mcu/selected-capacity-baud.json").exists(),
                "old rate scope reached MCU; reconcile instead of replaying")
    tests = json.loads(TESTS.read_bytes())
    require(tests["passed"] and tests["sources"] == sources(), "current rate-discriminator tests required")
    if args.command == "worker":
        admission = json.loads((AREA / SESSION / "admission.json").read_bytes())
        require(admission["prior_boundary"] == prior, "admitted prior observation changed")
        return run_worker()
    _, _, _, c = CAPACITY.context(AREA / SESSION)
    require(not c.OUT.exists(), "spent rate discriminator; no replay")
    c.checked(c.OUT / "admission.json")
    c.checked(c.OUT / "owner")
    os.environ.update(c.environment())
    c.save(c.OUT / "admission.json", dict(tests=record(TESTS), prior_boundary=prior,
        assets=record(AREA / "assets/result.json"), sources=tests["sources"],
        selected_baud=460800, restoration_baud=921600, firmware_install=False, extra_system_reports=0))
    print(json.dumps(c.supervisor.owned.launch(c.OUT / "owner", Path(__file__), ["worker", "--session", SESSION], 1200)), flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
