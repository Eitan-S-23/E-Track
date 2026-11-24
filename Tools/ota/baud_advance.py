"""Bind the original verified rollback to the current owned USB window."""
from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import runpy
import sys

ROOT = Path(__file__).resolve().parents[2]
SELF = Path(__file__).resolve()
PARENT = SELF.with_name("baud_foreground.py")


def bind(front, recovery, native):
    recovery.PHONE = front.PHONE
    recovery.start = front.start
    original_load = recovery.load

    def load(name, path):
        module = original_load(name, path)
        if Path(path).name == "baud_restore.py":
            module.m.c.host_presence = native["native_presence"]
            helper_load = module.load

            def load_helper(label, source):
                helper = helper_load(label, source)
                if Path(source).name == "restore_device.py":
                    helper.c.host_presence = native["native_presence"]
                    helper.Link = native["uncached_link"](helper.Link, lambda: dict(adapter=front.b.record(SELF)))
                return helper

            module.load = load_helper
        return module

    recovery.load = load
    return front, recovery


def runtime():
    parent = runpy.run_path(str(PARENT), run_name="current_foreground_route")
    native = runpy.run_path(str(SELF.with_name("baud_uncached.py")), run_name="recovery_native_reads")
    return bind(parent["runtime"](), parent["base_runtime"](), native)


def admit(front, run):
    front.authority()
    front.b.require(run in ("baud-115200-f1", "baud-460800"), "only finite completed predecessor transitions")
    out = front.cell(run)
    completed, board = front.read(out/"completed.json"), front.read(out/"mcu/result.json")
    front.b.require(completed["result"] == "COMPLETED_RETAINED" and board["reader_closed"] and
                    board["result"] == "TARGET_VERIFIED_RETAINED" and board.get("profile_complete") and
                    board["profile"]["clean_counters"], "completed clean target required")
    for owner in ("capture-"+run, "coordinate-"+run):
        receipt = front.read(front.RUNTIME/owner/"closed.json")
        front.b.require(receipt["worker_exit"] == 0 and not receipt["forced_termination"], "original observer still open")
    return front.b.record(out/"completed.json")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("mode", choices=("advance", "worker"))
    parser.add_argument("--run", choices=("baud-115200-f1", "baud-460800"), required=True)
    args = parser.parse_args()
    front, recovery = runtime()
    front.b.require(Path.cwd() == ROOT and sys.flags.isolated and sys.flags.no_site and sys.dont_write_bytecode,
                    "isolated project-root execution required")
    completed = admit(front, args.run)
    tests_path = front.b.OUT/"foreground/advance-host-tests-001/result.json"
    tests = front.read(tests_path)
    front.b.require(tests["passed"] and tests["source"] == front.b.record(SELF) and
                    tests["parent"] == front.b.record(PARENT) and tests["sources"] == front.sources() and
                    tests["test_source"] == front.b.record(SELF.with_name("test_baud_advance.py")),
                    "source-bound recovery route tests required")
    os.environ.update(front.environment())
    receipt = front.b.OUT/"foreground"/("advance-rebound-"+args.run+".json")
    if args.mode == "advance":
        if args.run == "baud-115200-f1":
            previous = front.RUNTIME/"advance-worker-baud-115200-f1-foreground"
            value = front.read(previous/"closed.json")
            front.b.require(value["worker_exit"] == 1 and not value["forced_termination"] and
                            "owned ADB server not live" in (previous/"worker.log").read_text(encoding="utf-8") and
                            not (front.b.OUT/"rates/restore-for-baud-460800.json").exists(),
                            "prior host-only failure must be reconciled, not replayed")
        front.save(receipt, dict(time=front.b.now(), source=front.b.record(SELF), parent=front.b.record(PARENT),
                   tests=front.b.record(tests_path), completed=completed, phone=str(front.PHONE),
                   recovery="unchanged raw-image helper and protocol; current USB route and tested native readers"))
        print(front.supervisor.owned.launch(front.RUNTIME/("advance-rebound-"+args.run), SELF,
              ["worker", "--run", args.run], 1800), flush=True)
    else:
        front.b.require(front.supervisor.owned.in_job(), "owned bounded worker required")
        value = front.read(receipt)
        front.b.require(value["source"] == front.b.record(SELF) and value["completed"] == completed and
                        value["phone"] == str(recovery.PHONE), "admitted route changed")
        recovery.advance(args.run)


if __name__ == "__main__":
    main()
