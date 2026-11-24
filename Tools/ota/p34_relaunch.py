"""Bounded receive-bootstrap relaunch after the unused App was killed by Android."""
from __future__ import annotations

import argparse
import datetime as dt
import json
import os
from pathlib import Path
import sys
import time

sys.path.insert(0, str(Path(__file__).resolve().parent))
import p34_session as cli

ROOT = Path(__file__).resolve().parents[2]
SELF = Path(__file__).resolve()
AREA = ROOT / ".cache/p34-receive-screen/relaunch"
AUTH = ROOT / ".cache/p34-receive-screen/relaunch-authorization.json"
RUN = "20260929T115119-cached-56200"
CAPTURE = "1790680525007381-6ccf9b4b5965b93430950b73"
REMOTE = "files/p34-observations/" + CAPTURE
RESOLVED = "/data/user/0/com.wen.gaia.gaia.p34probe/" + REMOTE
GROUP = "receive-bootstrap"


def verify_unused(observed, config, events, expected_events):
    health = observed.get("health", {})
    cli.require(observed.get("pid") is None and observed.get("pid_checked_before_after") is True and
                observed.get("remote") == REMOTE and observed.get("safe_idle") is True and
                not observed.get("snapshots") and observed.get("config", {}).get("sha256") == config["sha256"] and
                health.get("captureId") == CAPTURE and health.get("healthy") is True and health.get("lost") == 0 and
                health.get("error") is None and health.get("outcome") is None and
                health.get("upgradeStarts") == health.get("upgradeEnds") == 0 and events == expected_events,
                "unused capture/process/config/bytes changed; no deletion or relaunch")


def verify_room(observed, previous, remaining):
    report = previous["report"]
    snapshots = observed.get("snapshot_records", {})
    cli.require(observed.get("pid") is None and observed.get("pid_checked_before_after") is True and
                observed.get("config") is None and observed.get("stable_completed") is True and
                observed.get("capture_directories") == len(remaining) == 7 and
                observed.get("remote") == "files/p34-observations/" + report["summary"]["captureId"] and
                len(snapshots) == 1 and
                next(iter(snapshots.values()))["sha256"] == report["inputs"]["snapshot"]["sha256"],
                "stopped/config-retired/protected30228/free-slot state changed")


def verify_tests(store):
    core = cli.verify_tests(store)
    path = AREA / "tests/result.json"
    value = store.read(path)
    cli.require(value.get("passed") is True and value.get("device_operations") == 0 and
                value["core_tests"] == core and all(cli.record(x["path"]) == x for x in value["sources"]),
                "relaunch helper needs current source-bound self-tests")
    return dict(core=core, relaunch=cli.record(path))


def admission(store):
    cli.require(store.current() == RUN, "relaunch is limited to the current closed App-exit owner")
    out = store.run(RUN)
    plan = store.read(out / "plan.json")
    cli.require(plan.get("group") == GROUP and plan.get("cached_resume") and
                store.read(out / "cells/s04/result.json").get("result") == "CACHED_OBSERVATION_INCOMPLETE",
                "not the diagnosed cached-observer App exit")
    for name in (*cli.CELLS, "network"):
        state = cli.owner_state(store, out / "runtime" / name)
        cli.require(state["state"] in ("NOT_STARTED", "CLOSED") and
                    not state.get("receipt", {}).get("forced_termination"), "previous ownership unresolved")
    for item in plan["sources"]:
        cli.require(cli.record(item["path"]) == item, "original observer source changed")
    closure = store.read(out / "cells/s04/usb/closed.json")
    cli.require(closure["port_closed"] and closure["stop_exit"] == closure["server_exit"] == closure["launcher_exit"] == 0 and
                closure["key_before"] == closure["key_after"], "previous USB closure differs")
    result = store.read(out / "cells/s04/result.json")
    cli.require(cli.record(result["native_trace"]["path"]) == result["native_trace"] and
                store.read(result["native_trace"]["path"])["reader_closed"], "native reader closure differs")
    config = cli.record(out / "cells/s04/runtime-config.json")
    health = store.read(out / "cells/s04/health-live.json")["health"]
    cli.require(health["captureId"] == CAPTURE and health["upgradeStarts"] == health["upgradeEnds"] == 0,
                "old observation contains a started upgrade")
    commands = [json.loads(line) for line in (out / "cells/s04/usb/commands.jsonl").read_text(encoding="utf-8").splitlines()]
    last = commands[-1]
    cli.require(last["args"] == ["shell", "pidof", "com.wen.gaia.gaia.p34probe"] and
                last["exit"] == 1 and last["stdout_bytes"] == 0, "not the recorded missing-App exit")
    auth = store.read(AUTH)
    cli.require(auth.get("status") == "EXPLICIT_USER_APPROVED" and auth.get("resolved_phone_path") == RESOLVED and
                auth.get("app_data_clear") is False, "exact unused-record deletion authorization required")
    return plan, config


def remove_exact(c, p, api, out, before, archived):
    names = p.command(["exec-out", "run-as", c.PKG, "ls", "-1", REMOTE]).splitlines()
    cli.require(set(names) == {"events.jsonl", "health.json"}, "unexpected unused-capture files")
    module = cli.load_module("p34_relaunch_path", ROOT / "Tools/ota/p34_session_backend.py")
    resolved = module.checked_phone_path(c, p, REMOTE)
    cli.require(resolved == RESOLVED and CAPTURE in before and len(before) == 8,
                "exact path or capture set differs")
    for name, item in archived.items():
        cli.require(cli.record(item["path"]) == item and
                    p.file_bytes(c.PKG, REMOTE + "/" + name, c.envelope.MAX_BYTES) == Path(item["path"]).read_bytes(),
                    "unused-capture archive equality failed")
    cli.require(not p.command(["shell", "pidof", c.PKG], check=False).strip(), "App restarted; do not delete")
    c.save(out / "delete-intent.json", dict(time=c.now(), resolved=resolved, before=before, archived=archived,
            authorization=cli.record(AUTH)))
    p.command(["shell", "run-as", c.PKG, "rm", "-rf", REMOTE])
    remaining = api.observation_names(c, p)
    cli.require(set(remaining) == set(before) - {CAPTURE}, "deletion changed another capture")
    return remaining


def cleanup(store):
    with store.command_lock():
        tests = verify_tests(store)
        plan, config = admission(store)
        out = store.checked(AREA / "cleanup")
        cli.require(not out.exists(), "cleanup already attempted; preserve/reconcile its receipt")
        api = cli.backend(store, Path(plan["profile"]["path"]), GROUP)
        c = api.context(out)
        api.preflight(c, out)
        phone = api.phone(c, "p34_unused_cleanup")
        lock = c.load("p34_relaunch_lock", ROOT / "Tools/ota/repeat_cycle.py")
        original = ROOT / ".cache/p34-receive-screen/app-exit-inspection/app/events.jsonl"
        value = dict(result="UNUSED_CAPTURE_CLEANUP_INCOMPLETE", tests=tests, authorization=cli.record(AUTH),
                     source=cli.record(SELF), original=cli.record(original), capture_deleted=False)
        c.save(out / "intent.json", dict(time=c.now(), **value))
        try:
            with lock.device_lock(), phone.usb(c, out) as p:
                observed = api.capture(c, p, phone, out / "app")
                events = (out / "app/events.jsonl").read_bytes()
                verify_unused(observed, config, events, original.read_bytes())
                before = api.observation_names(c, p)
                query, checkpoint, messages = p.query.validate(events, (out / "app/health-before.json").read_bytes(),
                    (out / "app/health-after.json").read_bytes(), pid=8312,
                    sentinel=c.apk["metadata"]["device_observation"]["sentinel"], target=c.TARGET)
                c.raw(out / "app/checkpoint.jsonl", checkpoint)
                c.raw(out / "app/observations.log", messages.encode())
                value["query"] = query
                api.retire_initial(c, p, phone, out / "retire")
                cli.require(not phone.exists(p, c.PKG, "files/p34-experiment.json"), "failed config not retired")
                archived = {"events.jsonl": cli.record(out / "app/events.jsonl"),
                            "health.json": cli.record(out / "app/health-after.json")}
                value["remaining"] = remove_exact(c, p, api, out, before, archived)
                value.update(capture_deleted=True, removed=[CAPTURE], archived=archived, config_archived=True)
            value.update(result="UNUSED_CAPTURE_PRUNED", usb_closed=True)
        except Exception as error:
            value["error"] = type(error).__name__ + ": " + str(error)
        c.save(out / "result.json", dict(time=c.now(), **value))
        return value


def start(store):
    with store.command_lock():
        tests = verify_tests(store)
        old_plan, _ = admission(store)
        receipt = AREA / "cleanup/result.json"
        cleaned = store.read(receipt)
        cli.require(cleaned.get("result") == "UNUSED_CAPTURE_PRUNED" and cleaned.get("usb_closed") is True and
                    cleaned.get("removed") == [CAPTURE] and cleaned["source"] == cli.record(SELF) and
                    cleaned["tests"] == tests and all(cli.record(x["path"]) == x for x in cleaned["archived"].values()),
                    "verified exact cleanup required")
        cli.require(not (AREA / "start-intent.json").exists(), "relaunch already reserved; inspect its run")
        api = cli.backend(store, Path(old_plan["profile"]["path"]), GROUP)
        name = dt.datetime.now(dt.timezone.utc).strftime("%Y%m%dT%H%M%S") + "-relaunch-" + str(time.time_ns() % 100000)
        out = store.run(name)
        c = api.context(out)
        api.preflight(c, out)
        observed = api.inspect(c, out / "prestart-phone")
        previous = api.predecessor(c)
        verify_room(observed, previous, cleaned["remaining"])
        store.write(AREA / "start-intent.json", dict(time=cli.now(), run=name, cleanup=cli.record(receipt),
                    tests=tests, source=cli.record(SELF), no_transfer_replayed=True))
        plan = dict(old_plan, time=cli.now(), sources=c.sources(), tests=tests["core"],
                    prestart=cli.record(out / "prestart-phone/result.json"),
                    relaunch=cli.record(AREA / "start-intent.json"))
        del plan["cached_resume"]
        store.write(out / "root-before.json", c.root_state())
        store.write(out / "plan.json", plan)
        store.write(store.base / "current.json", dict(run=name, created=cli.now()), replace=True)
        c.supervisor.owned.launch(out / "runtime/network", ROOT / "Tools/ota/p34_session.py",
            ["--root", str(ROOT), "--run", name, "_network"], cli.NETWORK_SUPERVISOR_SECONDS)
        def ready():
            cli.require(not (out / "runtime/network/closed.json").exists(), "service failed; preserve this attempt")
            return (out / "live-network.json").exists()
        cli.wait_until(ready, seconds=450)
        api.network_ready(c, out)
        store.write(out / "cells/s04/intent.json", dict(time=cli.now(), cell="s04", plan=cli.record(out / "plan.json")))
        c.supervisor.owned.launch(out / "runtime/s04", ROOT / "Tools/ota/p34_session.py",
            ["--root", str(ROOT), "--run", name, "--cell", "s04", "_cell"], cli.CELL_SECONDS)
        return cli.status(store, name, "s04")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=("cleanup", "start"))
    parser.add_argument("--root", required=True, type=Path)
    args = parser.parse_args()
    cli.require(args.root == ROOT == Path.cwd() and sys.flags.isolated and sys.flags.no_site and sys.dont_write_bytecode,
                "isolated explicit project root required")
    result = (cleanup if args.command == "cleanup" else start)(cli.Store(ROOT))
    print(json.dumps(result), flush=True)
    raise SystemExit(int("error" in result))
