"""Resume an unused receive-bootstrap App after a stale-download host failure.

The original run stays immutable. A new observation owns the same PID/capture
and already downloaded bytes; it never starts a service, App, download or OTA.
"""
from __future__ import annotations

import argparse
import datetime as dt
import os
from pathlib import Path
import sys
import time

sys.path.insert(0, str(Path(__file__).resolve().parent))
import p34_session as cli

SELF = Path(__file__).resolve()
GROUP = "receive-bootstrap"
CHANGED_SOURCES = frozenset(("Tools/ota/p34_session.py", "Tools/ota/p34_session_backend.py",
                            "tests/ota/test_p34_session.py", "tests/ota/test_p34_full.py"))


def verify_failure(plan, result, worker, network, *, admitted):
    cli.require(plan.get("group") == GROUP and not plan.get("cached_resume") and
                result.get("result") == "FULL_INSTALL_INCOMPLETE" and
                result.get("error") == "RuntimeError: App file size bound" and
                not any(key in result for key in ("summary", "after", "analysis")) and not admitted,
                "not an unadmitted stale-cache failure; do not replay")
    cli.require(worker.get("worker_exit") == 1 and network.get("worker_exit") == 0 and
                worker.get("forced_termination") is False and network.get("forced_termination") is False,
                "original owners have not closed normally")


def verify_phone(observed, prior):
    health = observed.get("health", {})
    cli.require(observed.get("pid") == prior["pid"] and observed.get("safe_idle") is True and
                observed.get("pid_checked_before_after") is True and not observed.get("snapshots") and
                observed.get("remote") == prior["remote"] and
                observed.get("config", {}).get("sha256") == prior["config"]["sha256"] and
                health.get("captureId") == prior["capture_id"] and health.get("healthy") is True and
                health.get("lost") == 0 and health.get("error") is None and
                health.get("upgradeStarts") == health.get("upgradeEnds") == 0 and
                health.get("outcome") is None,
                "cached resume requires the same unused App PID/config/capture")


def admission(store, run):
    cli.require(run == store.current(), "cached resume must own the actual current failed run")
    old = store.run(run)
    cell = old / "cells/s04"
    plan, result = store.read(old / "plan.json"), store.read(cell / "result.json")
    verify_failure(plan, result, store.read(old / "runtime/s04/closed.json"),
                   store.read(old / "runtime/network/closed.json"),
                   admitted=(cell / "queries/result.json").exists() or (cell / "finished").exists())
    usb = store.read(cell / "usb/closed.json")
    native = store.read(result["native_trace"]["path"])
    cli.require(usb["stop_exit"] == usb["server_exit"] == usb["launcher_exit"] == 0 and
                usb["port_closed"] and usb["key_before"] == usb["key_after"] and native["reader_closed"],
                "old USB/native ownership unresolved")
    for item in plan["sources"]:
        path = Path(item["path"])
        relative = path.relative_to(store.root).as_posix() if path.is_relative_to(store.root) else None
        if relative not in CHANGED_SOURCES:
            cli.require(cli.record(path) == item, "unrelated original source/input changed")
    for item in (plan["profile"], result["before"], result["native_trace"]):
        cli.require(cli.record(store.checked(item["path"])) == item, "original failure evidence changed")
    config = cli.record(cell / "runtime-config.json")
    launch = store.read(cell / "launch.json")
    health = store.read(cell / "health-live.json")["health"]
    cli.require(store.read(cell / "provision.json")["config"] == config and
                health["upgradeStarts"] == health["upgradeEnds"] == 0,
                "old App configuration or start count changed")
    return dict(run=run, plan=cli.record(old / "plan.json"), result=cli.record(cell / "result.json"),
                config=config, launch=cli.record(cell / "launch.json"), pid=launch["pid"],
                capture_id=health["captureId"], remote="files/p34-observations/" + health["captureId"],
                original_network=cli.record(old / "live-network.json"))


def start(store, run):
    with store.command_lock():
        tests = cli.verify_tests(store)
        prior = admission(store, run)
        old_plan = store.read(prior["plan"]["path"])
        api = cli.backend(store, Path(old_plan["profile"]["path"]), GROUP)
        name = dt.datetime.now(dt.timezone.utc).strftime("%Y%m%dT%H%M%S") + "-cached-" + str(time.time_ns() % 100000)
        out = store.run(name)
        c = api.context(out)
        api.preflight(c, out)
        api.verify_install_checkpoint(c, store.read(prior["result"]["path"])["before"]["path"])
        for leaf in ("origin-record.json", "resume-intent.json", "cells/s04/resume-phone"):
            store.checked(out / leaf)
        origin = store.read(prior["original_network"]["path"])["origin"]
        store.write(out / "origin-record.json", dict(origin=origin, original=prior["original_network"],
                    service="CLOSED", use="previously verified cached download only"))
        store.write(out / "root-before.json", c.root_state())
        store.write(out / "resume-intent.json", dict(time=cli.now(), prior=prior, tests=tests,
                    source=cli.record(SELF), no_app_restart=True, no_service=True, no_deletion=True))
        store.write(out / "plan.json", dict(old_plan, time=cli.now(), sources=c.sources(), tests=tests,
                    cached_resume=cli.record(out / "resume-intent.json")))
        original_cell = store.run(run) / "cells/s04"
        store.raw(out / "cells/s04/runtime-config.json", (original_cell / "runtime-config.json").read_bytes())
        store.write(out / "cells/s04/provision.json", dict(store.read(original_cell / "provision.json"),
                    config=cli.record(out / "cells/s04/runtime-config.json"),
                    original_provision=cli.record(original_cell / "provision.json"), configuration_reused=True))
        store.write(out / "cells/s04/intent.json", dict(time=cli.now(), cell="s04", plan=cli.record(out / "plan.json")))
        store.write(store.base / "current.json", dict(run=name, created=cli.now()), replace=True)
        c.supervisor.owned.launch(out / "runtime/s04", SELF,
            ["_worker", "--root", str(store.root), "--run", name], cli.CELL_SECONDS)
        return cli.status(store, name, "s04")


def worker(store, run):
    out = store.run(run)
    plan = store.read(out / "plan.json")
    intent_path = out / "resume-intent.json"
    intent = store.read(intent_path)
    cli.require(run == store.current() and cli.record(intent_path) == plan["cached_resume"] and
                cli.record(SELF) == intent["source"] and cli.verify_tests(store) == intent["tests"],
                "cached observation source/owner/test binding changed")
    prior = intent["prior"]
    for key in ("plan", "result", "config", "launch", "original_network"):
        cli.require(cli.record(store.checked(prior[key]["path"])) == prior[key], "original recovery input changed")
    api = cli.backend(store, Path(plan["profile"]["path"]), GROUP)
    c = api.context(out)
    cli.require(c.supervisor.owned.in_job(), "cached worker requires its finite owned supervisor")
    api.validate(c, out)
    os.environ.update(c.environment())
    c.cell = "s04"
    cell = out / "cells/s04"
    phone = api.phone(c, "p34_cached_observation")
    lock = c.load("p34_cached_lock", store.root / "Tools/ota/repeat_cycle.py")
    result = dict(result="CACHED_OBSERVATION_INCOMPLETE", original_failure=prior["result"],
                  no_app_restart=True, no_download=True, no_service=True, no_deletion=True)
    trace = None
    c.save(cell / "status.json", dict(time=c.now(), result="PREPARING"), replace=True)
    original_read = c.p.file_bytes
    def file_bytes(pkg, path, limit):
        data = original_read(pkg, path, limit)
        if path.endswith("/health.json"):
            c.save(cell / "health-live.json", dict(observed=c.now(), health=cli.json.loads(data)), replace=True)
        return data
    c.p.file_bytes = file_bytes
    try:
        with lock.device_lock(), phone.usb(c, cell) as p:
            observed = api.capture(c, p, phone, cell / "resume-phone")
            verify_phone(observed, prior)
            cli.require(api.downloaded_package(c, p) == c.screen_bytes, "current cached package is not verified")
            expected = c.read(cell / "runtime-config.json")
            messages = (cell / "resume-phone/observations.log").read_text(encoding="utf-8")
            module = cli.load_module("p34_cached_contract", store.root / "Tools/ota/p34_session_backend.py")
            module.verify_experiment(c.envelope, messages, expected, prior["config"]["sha256"])
            result["before"] = api.install_checkpoint(c, cell, before=True)
            api.verify_install_checkpoint(c, result["before"]["path"])
            try:
                reader = c.load("p34_cached_trace", store.root / "Tools/ota/p34_full_trace.py")
                generation = (api.initial_sample(c, cell)["profile"]["run"] + 1) & 0xffffffff
                trace = reader.Trace(c, cell / "native-trace", generation)
                trace.start()
                launch = store.read(prior["launch"]["path"])
                c.save(cell / "launch.json", dict(launch, original_launch=prior["launch"],
                       observation_resumed_at=c.now(), app_restarted=False))
                result["summary"] = api.observe_install(c, p, phone, cell, prior["pid"], expected, observer=trace)
            finally:
                if trace:
                    result["native_trace"] = trace.stop()
            result["after"] = api.install_checkpoint(api.installed_context(out), cell)
        result["analysis"] = api.analyze_install(c, out, "s04")
        result["result"] = result["analysis"]["result"]
    except Exception as error:
        result["error"] = type(error).__name__ + ": " + str(error)
    finally:
        c.p.file_bytes = original_read
    c.save(cell / "result.json", dict(time=c.now(), **result))
    c.save(cell / "status.json", dict(time=c.now(), result=result["result"], error=result.get("error"), closed=True), replace=True)
    print(cli.json.dumps(result), flush=True)
    return int("error" in result)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=("start", "_worker"))
    parser.add_argument("--root", required=True, type=Path)
    parser.add_argument("--run", required=True)
    args = parser.parse_args()
    cli.require(args.root == SELF.parents[2] == Path.cwd() and sys.flags.isolated and
                sys.flags.no_site and sys.dont_write_bytecode, "isolated explicit project root required")
    store = cli.Store(args.root)
    if args.command == "_worker":
        raise SystemExit(worker(store, args.run))
    print(cli.json.dumps(start(store, args.run)), flush=True)
