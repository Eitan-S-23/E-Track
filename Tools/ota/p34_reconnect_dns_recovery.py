"""Recover the exact closed pre-cell DNS failure without changing device state."""
import copy
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "Tools/ota"))
import p34_session as cli

FAILED = "20261001T155444-25400"
PREVIOUS = "20261001T112936-16300"
OUT = ROOT / ".cache/p34-reconnect/dns-recovery"


def validate(value):
    cli.require(value["current"] == FAILED and value["group"] == "reconnect-measure" and not value["cells"],
                "wrong owner or a device cell was attempted")
    cli.require(value["failure"] == dict(result="NETWORK_INCOMPLETE", device_operations=0,
        error="RuntimeError", detail="fresh service DNS window exhausted; preserve this origin and stop"),
        "not the bound DNS-only failure")
    cli.require(value["worker_exit"] == 1 and not value["forced"] and value["listener_closed"] and
                value["worker_stopped"] and value["usb_closed"] and value["idle_phone"], "closure/phone not safe")
    cli.require(len(value["dns"]) == 7 and all(e["id"] == "dns-readiness" and e["state"] == "failed" and
        e["error"] == "gaierror" and e["errno"] == 11001 and e["attempt"] == i
        for i, e in enumerate(value["dns"], 1)) and len({e["host"] for e in value["dns"]}) == 1,
        "original seven DNS failures required")


def tests():
    value = dict(current=FAILED, group="reconnect-measure", cells=False,
        failure=dict(result="NETWORK_INCOMPLETE", device_operations=0, error="RuntimeError",
                     detail="fresh service DNS window exhausted; preserve this origin and stop"),
        worker_exit=1, forced=False, listener_closed=True, worker_stopped=True, usb_closed=True, idle_phone=True,
        dns=[dict(id="dns-readiness", state="failed", error="gaierror", errno=11001, attempt=i, host="fixture")
             for i in range(1, 8)])
    validate(value)
    variants = [dict(value, **{k: x}) for k, x in (
        ("current", "wrong"), ("group", "erase-measure"), ("cells", True), ("worker_exit", 0),
        ("forced", True), ("listener_closed", False), ("worker_stopped", False), ("usb_closed", False),
        ("idle_phone", False), ("dns", value["dns"][:-1]))]
    bad = copy.deepcopy(value)
    bad["failure"]["device_operations"] = 1
    variants.append(bad)
    for variant in variants:
        try:
            validate(variant)
        except RuntimeError:
            continue
        raise RuntimeError("unsafe recovery admitted")
    return 12


def main():
    s = cli.Store(ROOT)
    s.checked(OUT / "result.json")
    cli.require(not OUT.exists(), "preserve DNS recovery receipt")
    checked = tests()
    with s.command_lock():
        regression = cli.verify_tests(s)
        out = s.run(FAILED)
        plan = s.read(out / "plan.json")
        failed = s.read(out / "network-result.json")
        owner = s.read(out / "runtime/network/closed.json")
        service = s.read(out / "network-owner/network/closed.json")
        phone = s.read(out / "prestart-phone/result.json")
        usb = s.read(out / "prestart-phone/usb/closed.json")
        events = [json.loads(l) for l in (out / "actions.jsonl").read_text().splitlines()]
        value = dict(current=s.current(), group=plan["group"], cells=(out / "cells").exists() or
            any((out / "runtime" / c).exists() for c in cli.CELLS),
            failure={k:failed[k] for k in ("result", "device_operations", "error", "detail")},
            worker_exit=owner["worker_exit"], forced=owner["forced_termination"],
            listener_closed=service["listener_closed"], worker_stopped=service["worker_stopped"],
            usb_closed=usb["port_closed"] and usb["stop_exit"] == usb["server_exit"] == usb["launcher_exit"] == 0 and
                       usb["key_before"] == usb["key_after"],
            idle_phone=phone["pid"] is None and phone["config"] is None and phone["safe_idle"] and
                       phone["health"]["upgradeStarts"] == phone["health"]["upgradeEnds"] == 0,
            dns=[e for e in events if e["id"] == "dns-readiness"])
        validate(value)
        cli.require(not (out / "live-network.json").exists() and plan["predecessor"]["run"] == PREVIOUS and
            cli.record(plan["profile"]["path"]) == plan["profile"], "admitted service or source drift")
        previous = cli.completed_full_predecessor(s, plan["predecessor"], group="erase-measure")
        cli.require(previous["plan"]["target_bindings"] == plan["bindings"], "retained MCU changed")
        preserved = [cli.record(out / n) for n in ("plan.json", "network-result.json", "runtime/network/closed.json",
            "network-owner/network/closed.json", "network-owner/network/tunnel.log", "actions.jsonl",
            "prestart-phone/result.json", "prestart-phone/usb/closed.json")]
        s.write(OUT / "intent.json", dict(result="CLOSED_DNS_FAILURE_RECONCILED", failed_run=FAILED,
            previous_run=PREVIOUS, profile=plan["profile"], regression=regression, host_checks=checked,
            source=cli.record(__file__), preserved=preserved, no_device_operation=True,
            direction="fresh temporary hostname; no global DNS changes or source changes"))
        s.write(s.base / "current.json", dict(run=PREVIOUS, created=cli.now(),
            network_recovery=cli.record(OUT / "intent.json")), replace=True)
        s.write(OUT / "result.json", dict(result="PRE_CELL_DNS_POINTER_RECOVERED", previous_run=PREVIOUS,
            preserved_failure=FAILED, host_checks=checked, device_operations=0))
        print("PRE_CELL_DNS_POINTER_RECOVERED", PREVIOUS)


if __name__ == "__main__":
    cli.require(Path.cwd() == ROOT and sys.flags.isolated and sys.flags.no_site and sys.dont_write_bytecode,
                "isolated explicit root required")
    main()
