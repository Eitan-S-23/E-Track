"""One new HCI-backed window4 screen; reuse closed, unchanged capacity primitives."""
from __future__ import annotations

import argparse
from contextlib import contextmanager
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import socket
import sys

ROOT = Path(__file__).resolve().parents[2]
AREA = ROOT / ".cache/p34-target50"
SESSION = "session-hci-w4"
PROOF = AREA / "hci-export/cfa-retrieved/result.json"
TESTS = AREA / "hci-export/session-tests-r1/result.json"


def require(value, message):
    if not value:
        raise ValueError(message)


def load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def record(path):
    data = Path(path).read_bytes()
    return dict(path=str(path), bytes=len(data), sha256=hashlib.sha256(data).hexdigest())


def source_paths():
    return [ROOT / name for name in (
        "Tools/ota/p34_hci_session.py", "tests/ota/test_p34_hci_session.py",
        "Tools/ota/p34_capacity_session.py", "tests/ota/test_p34_capacity_session.py",
        "Tools/ota/p34_capacity_control.html", "Tools/ota/p34_link_capacity.js",
        "Tools/ota/uart_probe.js", "Tools/ota/test_p34_link_capacity.cjs",
        "Tools/ota/p34_hci_export.py", "tests/ota/test_p34_hci_export.py",
        "Tools/ota/p34_hci_att.py", "tests/ota/test_p34_hci_att.py")]


def proof_ready(value):
    require(value.get("result") == "ORIGINAL_HCI_EXPORT_VERIFIED" and value.get("usb_closed") is True,
            "original HCI export and its USB closure required")
    require(any(item["summary"].get("packets", 0) > 0 and
                item["summary"].get("truncated_packets") == item["summary"].get("reported_drops") == 0
                for item in value.get("extracted", [])), "no complete original HCI packets")


def validate_proof():
    value = json.loads(PROOF.read_bytes())
    proof_ready(value)
    for item in value["extracted"]:
        require(record(Path(item["original"]["path"])) == item["original"], "original HCI file changed")
    return record(PROOF)


def validate_tests():
    value = json.loads(TESTS.read_bytes())
    require(value["passed"] and value["sources"] == [record(path) for path in source_paths()],
            "source-bound HCI screen self-tests required")
    return value


def configure(capacity):
    capacity.SESSION, capacity.WINDOW = SESSION, 4
    original_context = capacity.context

    def context(out):
        cli, store, impl, c = original_context(out)
        original_phone = impl.phone

        def phone(*args, **kwargs):
            result = original_phone(*args, **kwargs)
            original_usb = result.usb

            @contextmanager
            def usb(ctx, dest):
                ctx.checked(out / "hci-runtime.json")
                with original_usb(ctx, dest) as p:
                    require(p.command(["shell", "getprop", "persist.sys.bluetooth.btsnooplogmode"]).strip() == "full",
                            "full HCI logging changed before screen")
                    ctx.save(out / "hci-runtime.json", dict(full_logging=True, time=ctx.now(),
                             original_export=validate_proof(), report_during_probe=False,
                             chunk_cells=[142, 244], window=4))
                    yield p
            result.usb = usb
            return result

        impl.phone = phone
        return cli, store, impl, c
    capacity.context = context


def closed_probe(owner, native, usb, trial):
    require(owner.get("worker_exit") in (0, 1) and owner.get("forced_termination") is False,
            "probe worker not normally closed")
    require(native.get("reader_closed") is True and native.get("retained_verified") is True and
            "cleanup_error" not in native, "native state/closure unresolved")
    final = native["final_state"]
    require(final["bcb_state"] == 4 and final["confirm_done"] == final["sd_ready"] == 1 and
            final["session"]["state"] == final["session"]["isr_active"] == 0,
            "retained confirmed/idle state required")
    require(usb.get("port_closed") is True and
            usb.get("stop_exit") == usb.get("server_exit") == usb.get("launcher_exit") == 0,
            "probe USB not normally closed")
    require(trial.get("endSent") is False and any(item.get("kind") == "write" and
            item.get("hex", "").startswith("a55a02") for item in trial.get("events", [])),
            "do not spend report2 without an actual non-installing DATA probe")


def report(capacity):
    probe = AREA / SESSION
    read = lambda name: json.loads((probe / name).read_bytes())
    closed_probe(read("owner/closed.json"), read("mcu/closure.json"),
                 read("phone/usb/closed.json"), read("trial-142.json"))
    for port in (5062, capacity.PORT):
        with socket.socket() as sock:
            sock.settimeout(.25)
            require(sock.connect_ex(("127.0.0.1", port)) != 0, "probe port still owned")
    out = AREA / "hci-export/probe-evidence"
    _, _, impl, c = capacity.context(out)
    require(not out.exists(), "report2 already attempted; retrieve it, do not repeat")
    for name in ("preflight.json", "generation-intent.json", "generation.stdout", "generated.json",
                 "archive.json", "result.json", "phone"):
        c.checked(out / name)
    for i in range(1, 9):
        c.checked(out / ("hci-%02d.btsnoop" % i))
    os.environ.update(c.environment())
    exporter = load("hci_post_probe_export", ROOT / "Tools/ota/p34_hci_export.py")
    phone = impl.phone(c, "hci_post_probe_phone")
    lock = c.load("hci_post_probe_lock", ROOT / "Tools/ota/repeat_cycle.py")
    c.checked(lock.RUNS / "device.lock")
    value = dict(result="POST_PROBE_EXPORT_INCOMPLETE")
    try:
        with lock.device_lock(), phone.usb(c, out / "phone") as p:
            value = exporter.collect(c, p, out, number=2)
        value["usb_closed"] = True
    except Exception as error:
        value.update(error=type(error).__name__ + ": " + str(error),
                     next="Reconcile the existing report after USB re-enumeration; never generate again")
    c.save(out / "result.json", value)
    print(json.dumps(value), flush=True)
    return 0 if value["result"] == "ORIGINAL_HCI_EXPORT_VERIFIED" else 1


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=("start", "worker", "status", "report"))
    args = parser.parse_args()
    require(Path.cwd() == ROOT and sys.flags.isolated and sys.flags.no_site and
            sys.dont_write_bytecode, "explicit root and isolated Python required")
    if args.command == "status":
        path = AREA / SESSION / "status.json"
        print(path.read_text() if path.exists() else '{"result":"NOT_STARTED"}')
        return 0
    tests, proof = validate_tests(), validate_proof()
    capacity = load("hci_capacity", ROOT / "Tools/ota/p34_capacity_session.py")
    if args.command == "report":
        return report(capacity)
    configure(capacity)
    if args.command == "worker":
        admitted = json.loads((AREA / SESSION / "admission.json").read_bytes())
        require(admitted["hci_export"] == proof, "admitted HCI export changed")
        return capacity.worker()
    _, _, _, c = capacity.context(AREA / SESSION)
    require(not c.OUT.exists(), "spent HCI screen; no replay")
    c.checked(c.OUT / "admission.json")
    c.checked(c.OUT / "owner")
    os.environ.update(c.environment())
    c.save(c.OUT / "admission.json", dict(tests=record(TESTS), hci_export=proof,
        assets=record(AREA / "assets/result.json"), sources=tests["sources"]))
    print(json.dumps(c.supervisor.owned.launch(c.OUT / "owner", Path(__file__), ["worker"], 900)), flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
