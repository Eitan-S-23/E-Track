"""Inspect the abandoned reconnect window without replaying any device action."""
import argparse
import datetime as dt
import json
import os
from pathlib import Path
import re
import runpy
import socket
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "Tools/ota"))
import p34_session as cli

RUN = "20261001T161736-81500"
AREA = ROOT / ".cache/p34-reconnect/orphan"
PKG = "com.wen.gaia.gaia.p34probe"
CAPTURE = "1790873190640854-e74f259a6cf81bd47609ba5e"
APK_SHA = "1ec71e54f738abacbf5f4360ba421076061e2026a666ef484c8e3a17759884da"
PREVIOUS = "20261001T112936-16300"


def phone_available(listing, serial):
    matches = [line.split() for line in listing.splitlines() if line.split()[:1] == [serial]]
    return len(matches) == 1 and matches[0][1:2] == ["device"]


def unused(health, snapshots):
    return (health.get("captureId") == CAPTURE and health.get("healthy") is True and
            type(health.get("upgradeStarts")) is int and health["upgradeStarts"] == 0 and
            type(health.get("upgradeEnds")) is int and health["upgradeEnds"] == 0 and
            health.get("lost") == 0 and health.get("error") is None and
            health.get("outcome") is None and not snapshots)


def validate_phone(observed, config):
    cli.require(observed.get("pid") == 23723 and observed.get("pid_checked_before_after") is True and
                observed.get("safe_idle") is True and
                observed.get("remote") == "files/p34-observations/" + CAPTURE and
                observed.get("config", {}).get("sha256") == config["sha256"] and
                unused(observed.get("health", {}), observed.get("snapshots", [])),
                "original unused App/PID/config changed; collect instead of restarting")


def host_state(store):
    old = store.run(RUN)
    cli.require(store.current() == RUN, "only inspect the current abandoned window")
    plan = store.read(old / "plan.json")
    cli.require(plan["group"] == cli.RECONNECT_GROUP and plan["receiver_version"] == 30242 and
                plan["target_version"] == 30243, "wrong reconnect plan")
    live = store.read(old / "live-network.json")
    cli.require(dt.datetime.fromisoformat(live["expires"]) < dt.datetime.now(dt.timezone.utc),
                "service has not expired")
    processes = runpy.run_path(str(ROOT / "Tools/ota/baud_uncached.py"))["process_inventory"]()
    pids = {int(pid) for _, pid in processes}
    owners = {}
    for name in ("s04", "network"):
        path = old / "runtime" / name
        state = store.read(path / "state.json")
        cli.require(not (path / "closed.json").exists() and
                    not {state["supervisor_pid"], state["worker_pid"]} & pids,
                    "owner has closed or still exists; reconcile instead")
        owners[name] = dict(state=cli.record(path / "state.json"),
                            supervisor_absent=True, worker_absent=True, graceful_closure=False)
    usb = store.read(old / "cells/s04/usb/ready.json")
    cli.require(usb["pid"] not in pids, "old USB launcher remains")
    ports = (usb["port"], store.read(old / "network-owner/network/ready.json")["local_port"])
    for port in ports:
        with socket.socket() as channel:
            channel.settimeout(.3)
            cli.require(channel.connect_ex(("127.0.0.1", port)) != 0, "old port remains occupied")
    return dict(run=RUN, plan=cli.record(old / "plan.json"), owners=owners,
                ports_not_listening=list(ports), original_closures_missing=True)


def inspect(store):
    before = host_state(store)
    out = store.checked(AREA / ("inspect-" + dt.datetime.now(dt.timezone.utc).strftime("%Y%m%dT%H%M%S")))
    cli.require(not out.exists(), "preserve the original inspection")
    for name in ("intent.json", "result.json", "config.json", "devices.txt", "captures.json", "app"):
        store.checked(out / name)
    module = runpy.run_path(str(ROOT / "Tools/ota/p34_signing_migration.py"))
    b, device, phone, lock = module["runtime"]()
    store.write(out / "intent.json", dict(time=cli.now(), source=cli.record(__file__), host=before,
        no_install=True, no_launch=True, no_mcu=True, no_ota=True, no_phone_file_mutation=True))
    value = dict(result="PHONE_INSPECTION_INCOMPLETE", host=before)
    try:
        with lock.device_lock(), device["usb"](b, phone, out):
            listing = phone.command(["devices", "-l"])
            store.raw(out / "devices.txt", listing.encode())
            cli.require(phone_available(listing, phone.SERIAL), "target phone not available over USB")
            phone.phone_identity()
            cli.require(phone.command(["shell", "am", "get-current-user"]).strip() == "0", "wrong phone user")
            value["installed"] = device["installed"](b, phone, APK_SHA)
            cli.require(value["installed"] is not None, "fixed signer App missing")
            pid_before = phone.command(["shell", "pidof", PKG], check=False).strip()
            cli.require(not pid_before or pid_before.isdigit(), "ambiguous App process")
            config = phone.file_bytes(PKG, "files/p34-experiment.json", 8192)
            value["config"] = store.raw(out / "config.json", config)
            expected = (store.run(RUN) / "cells/s04/runtime-config.json").read_bytes()
            value["config_matches"] = config == expected
            names = phone.command(["exec-out", "run-as", PKG, "ls", "-1", "files/p34-observations"]).splitlines()
            cli.require(1 <= len(names) <= 8 and len(set(names)) == len(names) and
                        all(re.fullmatch(r"\d{13,20}-[0-9a-f]{24}", n) for n in names), "ambiguous captures")
            captures = {}
            for name in sorted(names):
                remote = "files/p34-observations/" + name
                leaves = phone.command(["exec-out", "run-as", PKG, "ls", "-1", remote]).splitlines()
                snapshots = [n for n in leaves if re.fullmatch(r"snapshot-[1-4]\.jsonl", n)]
                records = {}
                for leaf in ("health.json", "events.jsonl", *sorted(snapshots), "health.json"):
                    local = "health-after.json" if leaf in records else leaf
                    raw = phone.file_bytes(PKG, remote + "/" + leaf, 8192 if leaf == "health.json" else 16 * 1024 * 1024)
                    records[local] = store.raw(out / "app" / name / local, raw)
                health = json.loads(Path(records["health-after.json"]["path"]).read_bytes())
                captures[name] = dict(health=health, snapshots=snapshots, records=records,
                    stable_health=Path(records["health.json"]["path"]).read_bytes() ==
                                  Path(records["health-after.json"]["path"]).read_bytes())
            store.write(out / "captures.json", captures)
            pid_after = phone.command(["shell", "pidof", PKG], check=False).strip()
            cli.require(pid_before == pid_after, "App process changed during inspection")
            original = captures.get(CAPTURE, {})
            value.update(pid=int(pid_after) if pid_after else None, capture_count=len(captures),
                latest_capture=sorted(names)[-1], captures=cli.record(out / "captures.json"),
                original_unused=unused(original.get("health", {}), original.get("snapshots", [])),
                result="PHONE_ORIGINALS_RETRIEVED")
        value["usb_closed"] = True
    except Exception as error:
        value.update(error=type(error).__name__, detail=str(error))
    store.write(out / "result.json", dict(time=cli.now(), **value))
    print(json.dumps(dict(evidence=str(out), **value)), flush=True)
    return int("error" in value)


def test(store):
    out = store.checked(AREA / "tests" / dt.datetime.now(dt.timezone.utc).strftime("%Y%m%dT%H%M%S"))
    for name in ("unittest.log", "result.json", "host"):
        store.checked(out / name)
    host = cli.load_module("orphan_test_environment", ROOT / ".cache/project-governance-20260922/run.py")
    host.OUT = out
    command = [sys.executable, "-I", "-S", "-B", "-X", "utf8", str(ROOT / "tests/ota/test_p34_reconnect_orphan.py")]
    result = subprocess.run(command, cwd=ROOT, env=host.environment(), capture_output=True,
                            timeout=30, creationflags=subprocess.CREATE_NO_WINDOW)
    log = store.raw(out / "unittest.log", result.stdout + result.stderr)
    report = dict(passed=result.returncode == 0, log=log, sources=[cli.record(__file__),
        cli.record(ROOT / "tests/ota/test_p34_reconnect_orphan.py")], device_operations=0)
    store.write(out / "result.json", report)
    cli.require(report["passed"], "orphan safety tests failed")
    store.write(AREA / "tests/latest.json", dict(report=cli.record(out / "result.json")), replace=True)
    print((result.stdout + result.stderr).decode(), flush=True)
    return 0


def recover(store):
    out = store.checked(AREA / "recover-001")
    cli.require(not out.exists(), "recovery already attempted; preserve and reconcile its result")
    host = host_state(store)
    test_path = store.read(AREA / "tests/latest.json")["report"]
    cli.require(cli.record(test_path["path"]) == test_path, "test receipt changed")
    tests = store.read(test_path["path"])
    cli.require(tests["passed"] and all(cli.record(x["path"]) == x for x in tests["sources"]),
                "current recovery safety tests required")
    regression = cli.verify_tests(store)
    old = store.run(RUN)
    plan = store.read(old / "plan.json")
    cli.require(plan["predecessor"]["run"] == PREVIOUS and
                cli.record(plan["profile"]["path"]) == plan["profile"], "predecessor/profile changed")
    config = cli.record(old / "cells/s04/runtime-config.json")
    original = store.read(old / "cells/s04/mcu/closure.json")
    for name in ("intent.json", "result.json", "pointer-intent.json", "app", "retire", "installed-mcu", "usb", "host"):
        store.checked(out / name)
    store.write(out / "intent.json", dict(time=cli.now(), source=cli.record(__file__), host=host,
        tests=test_path, regression=regression, no_ota=True, no_reset=True, no_flash=True,
        operation="fresh raw identity and unused App verification; archive expired config; recover pointer"))
    value = dict(result="ORPHAN_RECOVERY_INCOMPLETE", original=host, tests=test_path)
    try:
        with store.command_lock():
            api = cli.backend(store, Path(plan["profile"]["path"]), cli.RECONNECT_GROUP)
            c = api.context(out)
            api.preflight(c, out)
            c.native_authority()
            api.verify_install_checkpoint(c, old / "cells/s04/mcu/closure.json")
            os.environ.update(c.environment())
            phone = api.phone(c, "p34_orphan_recovery")
            lock = c.load("p34_orphan_device_lock", ROOT / "Tools/ota/repeat_cycle.py")
            contracts = cli.load_module("p34_orphan_contract", ROOT / "Tools/ota/p34_session_backend.py")
            with lock.device_lock(), phone.usb(c, out) as p:
                observed = api.capture(c, p, phone, out / "app")
                validate_phone(observed, config)
                value["checkpoint"] = api.install_checkpoint(c, out)
                api.verify_install_checkpoint(c, value["checkpoint"]["path"])
                current = c.read(value["checkpoint"]["path"])["final_state"]
                contracts.same_terminal(current, original["final_state"])
                # Do not manufacture the absent original supervisor/reader closures.
                api.retire_initial(c, p, phone, out / "retire")
                cli.require(not p.command(["shell", "pidof", PKG], check=False).strip() and
                            not phone.exists(p, PKG, "files/p34-experiment.json"), "App retirement unresolved")
                value["retired"] = cli.record(out / "retire/previous-app/retired.json")
            value["usb_closed"] = True
            cli.require(host_state(store) == host, "old host ownership changed during recovery")
            value.update(result="ORPHAN_NO_TRANSFER_RECONCILED", original_closures_still_missing=True,
                         retained_version=30242, no_ota=True, no_reset=True, no_flash=True)
            store.write(out / "pointer-intent.json", dict(time=cli.now(), **value))
            store.write(store.base / "current.json", dict(run=PREVIOUS, created=cli.now(),
                orphan_recovery=cli.record(out / "pointer-intent.json")), replace=True)
            value["pointer_recovered"] = True
    except Exception as error:
        value.update(error=type(error).__name__, detail=str(error))
    store.write(out / "result.json", dict(time=cli.now(), **value))
    print(json.dumps(value), flush=True)
    return int("error" in value)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("mode", choices=("inspect", "test", "recover"))
    args = parser.parse_args()
    cli.require(Path.cwd() == ROOT and sys.flags.isolated and sys.flags.no_site and sys.dont_write_bytecode,
                "isolated explicit root required")
    raise SystemExit({"inspect": inspect, "test": test, "recover": recover}[args.mode](cli.Store(ROOT)))
