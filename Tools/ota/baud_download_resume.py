"""Resume a closed pre-OTA coordinator without replacing its live observers."""
from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import json
import os
from pathlib import Path
import runpy
import sys
import time

ROOT = Path(__file__).resolve().parents[2]
SELF = Path(__file__).resolve()
TESTS = ROOT / ".cache/p34m/host-tests-download-resume-001/result.json"


def runtime():
    return runpy.run_path(str(SELF.with_name("baud_memory_fix.py")),
                         run_name="download_resume_adapter")["configure"]()


def identity(data):
    return dict(bytes=len(data), sha256=hashlib.sha256(data).hexdigest())


def no_upgrade(health):
    if not (health.get("healthy") is True and health.get("error") is None and
            all(type(health.get(key)) is int and health[key] == 0
                for key in ("lost", "upgradeStarts", "upgradeEnds"))):
        raise RuntimeError("App activity or observation failure requires reconciliation")


class CachedPackage(RuntimeError):
    pass


def bind(r, run, stale, directory):
    """Adapt only this worker's functions; admitted source files stay immutable."""
    out = r.cell(run)
    config = r.read(out / "config.json")
    expected = config["assets"]["package"]
    remote = "app_flutter/firmware/" + config["group"] + "-full.etu"
    stale_identity = {key: stale[key] for key in ("bytes", "sha256")}
    r.b.require(stale_identity != {key: expected[key] for key in stale_identity},
                "current package cannot be classified as stale")
    original_inspect, original_save = r.inspect_start, r.save

    def inspect(label):
        r.b.require(label == run, "resume cannot inspect a different run")
        p = r.phone(run)
        original_read = p.file_bytes

        def read_package(pkg, path, *args, **kwargs):
            data = original_read(pkg, path, *args, **kwargs)
            if pkg == r.PKG and path == remote and identity(data) == stale_identity:
                raise CachedPackage("known previous firmware download; not admitted")
            return data

        # The original inspector validates the live query/config before reading
        # this exact package. Unknown corruption still reaches its strict guard.
        p.file_bytes = read_package
        try:
            return original_inspect(label)
        except CachedPackage:
            path = directory / "known-stale-package.json"
            if not path.exists():
                original_save(path, dict(time=r.b.now(), result="WAITING_FOR_NEW_DOWNLOAD",
                    observed=stale_identity, expected=expected, remote=remote,
                    mutation="none; retained in App until its normal download replaces it"))
            return None
        finally:
            p.file_bytes = original_read

    def save(path, value, replace=False):
        if Path(path) == out / "coordinator-result.json":
            path = directory / "coordinator-result.json"
        return original_save(path, value, replace=replace)

    r.inspect_start, r.save = inspect, save

    def unbind():
        r.inspect_start, r.save = original_inspect, original_save

    return unbind


def admission(r, run):
    out = r.cell(run)
    prior = r.read(out / "coordinator-result.json")
    closed = r.read(r.RUNTIME / ("coordinate-" + run) / "closed.json")
    r.b.require(prior.get("error") == "RuntimeError: downloaded package differs from group" and
                closed["worker_exit"] == 0 and not closed["forced_termination"],
                "only the reconciled stale-download coordinator can resume")
    r.b.require(not (out / "arm.json").exists() and not (out / "mcu/result.json").exists() and
                not (r.RUNTIME / ("capture-" + run) / "closed.json").exists(),
                "do not replay or replace an armed/closed device observation")
    board = r.read(out / "mcu/state.json")
    age = time.time() - dt.datetime.fromisoformat(board["time"]).timestamp()
    r.b.require(0 <= age <= 15 and board["preflight_ready"] and board["state"]["ready_to_begin"] and
                not board["state"]["begin_reserved"] and board["remaining_seconds"] >= r.m.RESERVE_SECONDS,
                "fresh baseline and complete transfer reserve required")
    p = r.phone(run)
    pkg, pid, remote = p.location("runtime")
    r.b.require(pid == r.read(out / "launched.json")["pid"], "original App process changed")
    health = p.file_bytes(pkg, remote + "/health.json", 8192)
    no_upgrade(json.loads(health))
    r.b.require(p.command(["shell", "pidof", pkg]).strip() == str(pid), "App changed during admission")
    return board, health


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("mode", choices=("launch", "worker"))
    parser.add_argument("--run", default="bootstrap", choices=("bootstrap",))
    args = parser.parse_args()
    r = runtime()
    r.b.require(Path.cwd().resolve() == ROOT and sys.flags.isolated and sys.flags.no_site and
                sys.dont_write_bytecode, "isolated explicit project root required")
    os.environ.update(r.environment())
    r.authority()
    directory = r.b.checked(r.cell(args.run) / "host-download-resume-001")
    worker = r.b.checked(r.RUNTIME / ("coordinate-" + args.run + "-download-r1"))
    for name in ("admission.json", "health-before.json", "known-stale-package.json", "coordinator-result.json"):
        r.b.checked(directory / name)
    tests = r.read(TESTS)
    r.b.require(tests["passed"] and tests["source"] == r.b.record(SELF) and
                tests["test_source"] == r.b.record(SELF.with_name("test_baud_download_resume.py")) and
                tests["runtime_sources"] == r.sources(), "source-bound resume tests required")
    stale = r.read(ROOT / ".cache/p34b/assets/result.json")["groups"]["bootstrap"]["package"]
    r.b.require(r.b.record(stale["path"]) == stale, "known old download changed")
    if args.mode == "launch":
        r.b.require(not directory.exists() and not worker.exists(), "preserve prior resume attempt")
        board, health = admission(r, args.run)
        r.raw(directory / "health-before.json", health)
        r.save(directory / "admission.json", dict(time=r.b.now(), source=r.b.record(SELF),
            tests=r.b.record(TESTS), stale=stale, plan=r.b.record(r.b.OUT / "plan.json"),
            prior=r.b.record(r.cell(args.run) / "coordinator-result.json"),
            purpose="same App and MCU reader; no reset, OTA, install or data clearing",
            remaining_seconds=board["remaining_seconds"]))
        print(r.supervisor.owned.launch(worker, SELF, ["worker", "--run", args.run],
                                       int(board["remaining_seconds"]) + 60), flush=True)
    else:
        r.b.require(r.supervisor.owned.in_job(), "bounded owned worker required")
        record = r.read(directory / "admission.json")
        r.b.require(record["source"] == r.b.record(SELF) and record["stale"] == stale and
                    record["plan"] == r.b.record(r.b.OUT / "plan.json"), "resume inputs drifted")
        admission(r, args.run)
        undo = bind(r, args.run, stale, directory)
        try:
            r.coordinate(args.run)
        finally:
            undo()


if __name__ == "__main__":
    main()
