"""Reconcile a completed config move interrupted before window-32 admission."""
import json
from pathlib import Path
import time

import p34_session as cli


def verify_usb(value):
    cli.require(value.get("port_closed") is True and
                all(value.get(key) == 0 for key in ("stop_exit", "server_exit", "launcher_exit")) and
                value.get("key_before") == value.get("key_after") and "cleanup_error" not in value,
                "retirement USB closure unresolved")


def failure(store, run, profile_path):
    out = store.run(run)
    cell = out / "cells/s04"
    plan = store.read(out / "plan.json")
    cli.require(store.read(cell / "intent.json").get("plan") == cli.record(out / "plan.json"),
                "failed plan differs from its original cell intent")
    cli.require(plan.get("group") == cli.SPEED32_GROUP and
                plan.get("profile") == cli.record(store.checked(profile_path)) and
                (plan.get("receiver_version"), plan.get("target_version")) == (30225, 30226),
                "retirement recovery only accepts the original window-32 plan")
    cli.require({p.name for p in cell.iterdir()} ==
                {"intent.json", "network-borrowed.json", "previous-app", "result.json", "status.json", "usb"},
                "native admission, provision or launch may have occurred; no retirement recovery")
    for name in (*cli.CELLS, "network"):
        owner = cli.owner_state(store, out / "runtime" / name)
        cli.require(owner["state"] in ("NOT_STARTED", "CLOSED") and
                    not owner.get("receipt", {}).get("forced_termination"), "failed owner closure unresolved")
        if name in ("s04", "network"):
            cli.require(owner["state"] == "CLOSED", "failed owners must be closed")
    result = store.read(cell / "result.json")
    cli.require(result.get("result") == "FULL_INSTALL_INCOMPLETE" and
                result.get("error") == "RuntimeError: ADB command failed; preserve/reconcile its receipt" and
                not any(key in result for key in ("before", "summary", "after", "native_trace")),
                "not the diagnosed pre-admission ADB failure")
    previous = cli.completed_full_predecessor(store, plan["predecessor"], group=cli.SPEED16_GROUP)
    intent = store.read(cell / "previous-app/retire-intent.json")
    observed = intent["observation"]
    config = previous["report"]["inputs"]["config"]
    archive = "files/p34-retired-configs/" + config["sha256"] + ".json"
    cli.require(intent["archive"] == archive and intent["reconciled_terminal"] == previous["descriptor"]["report"] and
                observed.get("pid") is None and observed.get("pid_checked_before_after") is True and
                observed.get("stable_completed") is True and
                cli.record(store.checked(observed["config"]["path"])) == observed["config"] and
                (observed["config"]["bytes"], observed["config"]["sha256"]) == (config["bytes"], config["sha256"]),
                "retirement does not bind the completed predecessor configuration")
    cli.require(not (cell / "previous-app/retired.json").exists(), "retirement was already confirmed")
    commands = [json.loads(line) for line in (cell / "usb/commands.jsonl").read_text(encoding="utf-8").splitlines()]
    moved, failed = commands[-2:]
    pkg = moved["args"][2]
    cli.require(pkg == "com.wen.gaia.gaia.p34probe" and
                moved["args"] == ["shell", "run-as", pkg, "mv", "files/p34-experiment.json", archive] and
                moved["exit"] == 0 and not moved["stderr"] and
                sum(row["args"] == moved["args"] for row in commands) == 1 and
                failed["args"] == ["shell", "run-as", pkg, "sh", "-c",
                    "'if [ -e files/p34-experiment.json ] || [ -L files/p34-experiment.json ]; then printf PRESENT; else printf ABSENT; fi'"] and
                failed["exit"] != 0 and failed["stdout_bytes"] == 0 and "not found" in failed["stderr"],
                "original move/readback receipt differs from the diagnosed failure")
    verify_usb(store.read(cell / "usb/closed.json"))
    inputs = {name: cli.record(store.checked(out / name)) for name in (
        "plan.json", "cells/s04/intent.json", "cells/s04/result.json", "cells/s04/status.json",
        "cells/s04/previous-app/retire-intent.json", "cells/s04/previous-app/runtime-config.json",
        "cells/s04/usb/commands.jsonl", "cells/s04/usb/closed.json",
        "runtime/s04/closed.json", "runtime/network/closed.json")}
    return dict(run=run, inputs=inputs, previous=previous, config=config, archive=archive,
                capture_directories=observed["capture_directories"])


def verify_phone(store, observed, failed):
    report = failed["previous"]["report"]
    names = observed.get("snapshots", [])
    snapshot = observed.get("snapshot_records", {}).get(names[0]) if len(names) == 1 else None
    expected = report["inputs"]["snapshot"]
    cli.require(observed.get("result") == "APP_INSPECTED" and observed.get("stable_completed") is True and
                observed.get("pid_checked_before_after") is True and observed.get("pid") is None and
                observed.get("config") is None and observed.get("capture_directories") == failed["capture_directories"] and
                observed.get("remote") == "files/p34-observations/" + report["summary"]["captureId"] and
                snapshot is not None and (snapshot["bytes"], snapshot["sha256"]) == (expected["bytes"], expected["sha256"]),
                "phone process/configuration/capture changed after interrupted retirement")
    cli.require(cli.record(store.checked(snapshot["path"])) == snapshot, "phone snapshot bytes changed")


def reconcile(store, run):
    with store.command_lock():
        tests = cli.verify_tests(store)
        cli.require(store.current() == run, "recovery must bind the current failed owner")
        profile = Path(store.read(store.run(run) / "plan.json")["profile"]["path"])
        failed = failure(store, run, profile)
        impl = cli.backend(store, profile, cli.SPEED32_GROUP)
        out = store.checked(store.base / "retirement-recovery" / str(time.time_ns()))
        c = impl.context(out)
        impl.preflight(c, out)
        phone = impl.phone(c, "p34_retirement_readback")
        lock = c.load("p34_retirement_lock", store.root / "Tools/ota/repeat_cycle.py")
        value = dict(result="RETIREMENT_RECOVERY_FAILED", failed_run=run, inputs=failed["inputs"],
                     sources=c.sources(), tests=tests, phone_mutations=0, mcu_operations=0)
        store.write(out / "intent.json", dict(time=cli.now(), **value))
        try:
            with lock.device_lock(), phone.usb(c, out / "phone") as p:
                observed = impl.capture(c, p, phone, out / "phone/app")
                verify_phone(store, observed, failed)
                checked_path = cli.load_module("p34_retirement_backend", store.root / "Tools/ota/p34_session_backend.py").checked_phone_path
                resolved = checked_path(c, p, failed["archive"])
                raw = p.file_bytes(c.PKG, failed["archive"], 8192)
                cli.require(raw == Path(failed["config"]["path"]).read_bytes(), "archived configuration bytes differ")
                archived = store.raw(out / "archived-config.json", raw)
                cli.require(not phone.exists(p, c.PKG, "files/p34-experiment.json") and
                            not p.command(["shell", "pidof", c.PKG], check=False).strip() and
                            p.command(["get-state"]).strip() == "device" and
                            p.file_bytes(c.PKG, failed["archive"], 8192) == raw,
                            "phone changed during retirement reconciliation")
            usb = out / "phone/usb/closed.json"
            verify_usb(store.read(usb))
            value.update(result="RETIREMENT_RECONCILED", no_launch=True, no_transfer=True,
                         archive=archived, resolved_archive=resolved, usb=cli.record(usb),
                         observation=cli.record(out / "phone/app/result.json"))
        except Exception as error:
            value.update(error=type(error).__name__, detail=str(error))
        store.write(out / "result.json", dict(time=cli.now(), **value))
        return dict(value, report=cli.record(out / "result.json"))


def load_recovery(store, path, profile):
    path = store.checked(path)
    cli.require(path.name == "result.json" and path.parent.parent == store.base / "retirement-recovery",
                "recovery report must be in its owned recovery directory")
    value = store.read(path)
    cli.require(value.get("result") == "RETIREMENT_RECONCILED" and value.get("no_launch") is True and
                value.get("no_transfer") is True and value.get("phone_mutations") == value.get("mcu_operations") == 0,
                "retirement reconciliation did not pass")
    failed = failure(store, value["failed_run"], profile)
    cli.require(value["inputs"] == failed["inputs"], "failed run inputs changed after reconciliation")
    # Pinned tools may be outside the workspace; hashing them is read-only.
    for item in value["sources"]:
        cli.require(Path(item["path"]).is_absolute() and cli.record(item["path"]) == item,
                    "retirement recovery source changed")
    for item in [value["archive"], value["usb"], value["observation"]]:
        cli.require(cli.record(store.checked(item["path"])) == item, "retirement recovery source/evidence changed")
    verify_usb(store.read(value["usb"]["path"]))
    verify_phone(store, store.read(value["observation"]["path"]), failed)
    cli.require((value["archive"]["bytes"], value["archive"]["sha256"]) ==
                (failed["config"]["bytes"], failed["config"]["sha256"]), "retired config identity changed")
    return dict(failure=failed, value=value, report=cli.record(path))
