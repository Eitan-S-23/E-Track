"""Resume a verified, unarmed cycle after a host-only prelaunch failure.

Keep the original source-pinned MCU reader alive. Never restore, reset, release
an App, reinstall, start another MCU reader, or repeat an uncertain launch here.
"""
from __future__ import annotations

import argparse
import importlib.util
import io
from pathlib import Path
import sys
import time
import unittest

SELF = Path(__file__).resolve()
spec = importlib.util.spec_from_file_location("resume_cycle_engine", SELF.with_name("repeat_cycle.py"))
r = importlib.util.module_from_spec(spec)
spec.loader.exec_module(r)


ready_state, wait_ready = r.ready_state, r.wait_ready


def missing_launch(cell, out):
    paths = [cell / name for name in ("launch-started.json", "launched.json", "arm.json", "stop.json")]
    paths += [out / "actions" / name for name in ("launch.intent.json", "launch.done.json", "arm.intent.json")]
    r.require(not any(path.exists() for path in paths), "prior launch/arm/stop must be reconciled, not repeated")


class Recovery(r.Backend):
    def __init__(self, config, label):
        super().__init__(config)
        self.recovery = r.valid_name(label)
        self.home = r.checked(self.out / ("host-recovery-" + label))
        self.runtime = r.checked(self.out / ("phone-recovery-" + label))
        self.adb_out = r.checked(self.out / ("adb-recovery-" + label))

    def snapshot(self):
        path = self.cell / "mcu/state.json"
        if not path.exists():
            return None, 0
        return r.read(path), time.time() - path.stat().st_mtime

    def observer_closed(self):
        return any(path.exists() for path in (self.cell / "mcu/result.json",
                   self.out / "mcu-worker/closed.json", self.cell / "stop.json"))

    def fresh_baseline(self):
        return wait_ready(self.snapshot, self.observer_closed)

    def admit(self):
        self.preflight()
        missing_launch(self.cell, self.out)
        r.require(not (self.out / "completed.json").exists(), "cycle already completed")
        for path in self.out.glob("coordinator-*/ready.json"):
            closed = r.read(path.parent / "closed.json")
            r.require(not closed["forced_termination"] and not closed.get("error"),
                      "old coordinator termination unresolved")
        failure = r.read(self.out / "status.json")
        r.require(failure["state"] == "RECONCILE_REQUIRED" and failure["error"] ==
                  "RuntimeError: live unarmed baseline observer required before App launch",
                  "this entry only reconciles the observed preflight/status publication race")
        old, supervisor = r.read(self.out / "phone-r1/closed.json"), r.read(self.out / "adb/closed.json")
        r.require(old["result"] == "SERVER_STOPPED" and old["port_closed"] and old["stop_exit"] == 0 and
                  not old.get("forced_cleanup") and supervisor["worker_exit"] == 0 and
                  not supervisor["forced_termination"] and not supervisor.get("error") and
                  not self.phone().alive(), "old private ADB has not closed normally")
        r.verify_board(r.RESTORE / ("execute-" + self.label) / "result.json", restored=True)
        preflight = r.read(self.cell / "mcu/preflight.json")
        r.require(preflight["preflight_ready"] and preflight["state"]["baseline_confirmed"] and
                  preflight["baseline_image"]["sha256"] == r.BASE_SHA and
                  preflight["baseline_boot"]["sha256"] == r.BOOT_SHA,
                  "original complete cold-start admission missing")
        state = self.fresh_baseline()
        r.require(state["remaining_seconds"] >= r.START_WAIT_SECONDS + r.RESERVE_SECONDS + 300,
                  "insufficient independent preparation/start/transfer budget; no reset or reflash")
        return state

    def validate_plan(self):
        plan = r.read(self.home / "plan.json")
        for key in ("source", "engine", "tests", "original_config", "preflight", "old_coordinator"):
            r.unchanged(plan[key])
        r.require(plan["run"] == self.config["run"] and plan["recovery"] == self.recovery,
                  "recovery plan/run mismatch")
        return plan

    def launch_phone(self):
        self.journal.phase("adb-recovery-" + self.recovery, lambda: self.supervisor.owned.launch(
            self.adb_out, SELF, ["phone-worker", "--run", self.config["run"], "--recovery", self.recovery], 5430),
            self.adb_out / "ready.json", self.validate_runtime)
        self.await_file(self.runtime / "ready.json", 30)
        r.require(not (self.runtime / "closed.json").exists() and self.phone().alive(), "new private ADB not live")
        self.phone().phone_identity()

    def execute(self):
        self.validate_plan()
        self.admit()
        self.launch_phone()
        state = self.fresh_baseline()
        # Host repair consumes preparation time, never the independent start or
        # transfer/apply/readback reserves. The original MCU deadline is unchanged.
        r.PREPARE_SECONDS = min(r.PREPARE_SECONDS, int(state["remaining_seconds"]) -
                                r.START_WAIT_SECONDS - r.RESERVE_SECONDS - 120)
        r.require(r.PREPARE_SECONDS >= 120, "too little phone preparation time")
        self.journal.phase("launch", self.launch_app, self.cell / "launched.json")
        self.monitor()


def start(args):
    b = Recovery(r.config_for(args.run), args.recovery)
    r.require(not b.home.exists() and not b.runtime.exists() and not b.adb_out.exists(),
              "preserve existing recovery; do not replay a launch")
    for path in (b.home, b.home / "plan.json", b.home / "coordinator", b.runtime, b.adb_out):
        r.checked(path)
    tests = r.read(r.checked(args.out) / "result.json")
    r.require(tests["passed"] and tests["source"] == r.record(SELF) and tests["engine"] == r.record(r.SELF)
              and tests["hardware_contacted"] is False, "source-bound recovery self-tests required")
    state = b.admit()
    plan = dict(time=r.now(), run=args.run, recovery=args.recovery, source=r.record(SELF), engine=r.record(r.SELF),
                tests=r.record(r.checked(args.out) / "result.json"), original_config=r.record(b.out / "config.json"),
                preflight=r.record(b.cell / "mcu/preflight.json"),
                old_coordinator=r.record(b.out / "coordinator-001/closed.json"),
                failure=r.read(b.out / "status.json"), observed_state=state,
                new_mcu_readers=0, reset=0, flash=0, ota_replays=0)
    r.write(b.home / "plan.json", plan)
    ready = b.supervisor.owned.launch(b.home / "coordinator", SELF,
        ["work", "--run", args.run, "--recovery", args.recovery], int(state["remaining_seconds"]) + 30)
    r.require(ready["detached_from_job"], "recovery coordinator did not detach")
    print("HOST_RECOVERY_STARTED", args.run, "original MCU reader retained", flush=True)


class RecoveryTests(unittest.TestCase):
    def state(self, ready=True):
        return dict(preflight_ready=ready, state=dict(epoch=0, baseline_confirmed=ready,
            begin_reserved=False, target_bcb_observed=False, ready_for_final_readback=False, ready_to_begin=ready))

    def test_projection_publication_race_waits_without_mutation(self):
        values = iter([(self.state(False), 0), (self.state(True), 0)])
        sleeps = []
        result = wait_ready(lambda: next(values), lambda: False, sleep=sleeps.append)
        self.assertTrue(result["preflight_ready"])
        self.assertEqual(sleeps, [.1])

    def test_old_guard_reproduces_false_negative(self):
        self.assertFalse(ready_state(self.state(False), 0))
        self.assertTrue(ready_state(self.state(True), 0))

    def test_closed_reader_is_not_replaced(self):
        with self.assertRaisesRegex(RuntimeError, "observer closed"):
            wait_ready(lambda: (self.state(), 0), lambda: True)

    def test_missing_status_then_ready(self):
        values = iter([(None, 0), (self.state(), 0)])
        self.assertTrue(wait_ready(lambda: next(values), lambda: False, sleep=lambda _: None)["preflight_ready"])

    def test_stale_or_future_projection_is_not_ready(self):
        for age in (-1, 10, 60):
            self.assertFalse(ready_state(self.state(), age))

    def test_ready_wait_is_bounded(self):
        clock = [0.0]
        def sleep(seconds):
            clock[0] += seconds
        with self.assertRaisesRegex(RuntimeError, "within its bound"):
            wait_ready(lambda: (self.state(False), 0), lambda: False,
                       seconds=.2, clock=lambda: clock[0], sleep=sleep)

    def test_any_reserved_or_changed_epoch_blocks_recovery(self):
        for key, value in (("epoch", 1), ("begin_reserved", True), ("target_bcb_observed", True),
                           ("ready_for_final_readback", True)):
            state = self.state()
            state["state"][key] = value
            with self.subTest(key=key), self.assertRaises(RuntimeError):
                ready_state(state, 0)

    def test_reader_error_is_not_retried(self):
        with self.assertRaisesRegex(RuntimeError, "observation has an error"):
            ready_state(dict(self.state(), error="gap"), 0)


def selftest(out):
    out = r.checked(out)
    r.require(not out.exists(), "fresh project-local test output required")
    for name in ("result.json", "tests.log"):
        r.checked(out / name)
    text = io.StringIO()
    result = unittest.TextTestRunner(stream=text, verbosity=2).run(
        unittest.defaultTestLoader.loadTestsFromTestCase(RecoveryTests))
    out.mkdir(parents=True)
    with (out / "tests.log").open("x", encoding="utf-8", newline="\n") as stream:
        stream.write(text.getvalue())
    r.write(out / "result.json", dict(time=r.now(), passed=result.wasSuccessful(), count=result.testsRun,
        source=r.record(SELF), engine=r.record(r.SELF), hardware_contacted=False,
        failures=len(result.failures), errors=len(result.errors)))
    print(text.getvalue(), end="")
    return 0 if result.wasSuccessful() else 1


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("mode", choices=("selftest", "start", "work", "phone-worker"))
    parser.add_argument("--run")
    parser.add_argument("--recovery", default="r1")
    parser.add_argument("--out", type=Path, default=r.ROOT / ".cache/p34-cycle-recovery-tests-r2")
    args = parser.parse_args()
    r.require(Path.cwd().resolve() == r.ROOT and sys.flags.isolated and sys.flags.no_site and sys.dont_write_bytecode,
              "isolated Python and explicit root cwd required")
    if args.mode == "selftest":
        raise SystemExit(selftest(args.out))
    r.require(args.run, "existing run required")
    if args.mode == "start":
        start(args)
        return
    b = Recovery(r.config_for(args.run), args.recovery)
    b.preflight()
    b.validate_plan()
    if args.mode == "phone-worker":
        b.phone().server()
        return
    try:
        with r.device_lock():
            b.execute()
    except Exception as error:
        b.journal.status("RECONCILE_REQUIRED", error=type(error).__name__ + ": " + str(error),
                         recovery=b.recovery, policy="No reset, restore or transfer replay during host recovery.")
        raise
    finally:
        if (b.runtime / "ready.json").exists() and not (b.runtime / "closed.json").exists():
            stop = b.runtime / "stop.json"
            if not stop.exists():
                r.write(stop, dict(time=r.now(), reason="host-recovery coordinator finished"))


if __name__ == "__main__":
    main()
