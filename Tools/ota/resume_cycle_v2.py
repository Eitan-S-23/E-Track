"""Compatibility recovery entry using the shared initial-epoch readiness guard.

The completed C3 adapter is preserved in the v2 source archive. This entry still
creates no MCU reader and retains the existing recovery journal/lifecycle.
"""
from __future__ import annotations

import importlib.util
from pathlib import Path

SELF = Path(__file__).resolve()
spec = importlib.util.spec_from_file_location("epoch_recovery_engine", SELF.with_name("resume_cycle.py"))
engine = importlib.util.module_from_spec(spec)
spec.loader.exec_module(engine)
r = engine.r


ready_state, wait_ready = r.ready_state, r.wait_ready


class Recovery(engine.Recovery):
    def admit(self):
        self.preflight()
        engine.missing_launch(self.cell, self.out)
        r.require(not (self.out / "completed.json").exists(), "cycle already completed")
        for path in self.out.glob("coordinator-*/ready.json"):
            closed = r.read(path.parent / "closed.json")
            r.require(not closed["forced_termination"] and not closed.get("error"),
                      "old coordinator termination unresolved")
        failure = r.read(self.out / "status.json")
        known = {
            "RuntimeError: live unarmed baseline observer required before App launch",
            "RuntimeError: MCU is no longer an unused baseline; do not recover as a prelaunch failure",
        }
        r.require(failure["state"] == "RECONCILE_REQUIRED" and failure["error"] in known,
                  "unknown failure; only the diagnosed prelaunch publication cases are admitted")
        old = r.read(self.out / "phone-r1/closed.json")
        supervisor = r.read(self.out / "adb/closed.json")
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


class RecoveryTests(engine.RecoveryTests):
    def actual_capture_state(self):
        b = r.Backend(dict(out=str(r.RUNS / "host-test-unused"), run="host-test-unused", candidate="reuse-without"))
        return b.collector().base.CaptureState()

    def test_actual_capture_constructor_is_pending_not_changed_epoch(self):
        state = self.actual_capture_state()
        initial = dict(preflight_ready=False, state=state.snapshot())
        self.assertIsNone(initial["state"]["epoch"])
        self.assertFalse(ready_state(initial, 0))
        self.assertFalse(r.ready_state(initial, 0))

    def test_actual_capture_initial_to_confirmed_sequence(self):
        state = self.actual_capture_state()
        initial = dict(preflight_ready=False, state=state.snapshot())
        state.observe(dict(sample=dict(epoch=0), lines=["OTA: BCB already CONFIRMED vcode=30206\r\n"]))
        self.assertTrue(state.can_begin())
        confirmed = dict(preflight_ready=True, state=state.snapshot())
        values = iter([(initial, 0), (confirmed, 0)])
        self.assertTrue(wait_ready(lambda: next(values), lambda: False, sleep=lambda _: None)["preflight_ready"])

    def test_none_epoch_after_prior_readiness_is_rejected(self):
        state = self.actual_capture_state()
        with self.assertRaisesRegex(RuntimeError, "conflicts"):
            ready_state(dict(preflight_ready=True, state=state.snapshot()), 0)

    def test_none_epoch_cannot_hide_a_reservation_or_error(self):
        state = self.actual_capture_state().snapshot()
        for key in ("begin_reserved", "baseline_confirmed", "target_bcb_observed", "ready_to_begin",
                    "ready_for_final_readback"):
            with self.subTest(key=key), self.assertRaisesRegex(RuntimeError, "conflicts"):
                ready_state(dict(preflight_ready=False, state=dict(state, **{key: True})), 0)
        with self.assertRaisesRegex(RuntimeError, "conflicts"):
            ready_state(dict(preflight_ready=False, state=state, error="gap"), 0)


# The launcher still requires exact live source/configuration bindings.
engine.SELF = SELF
engine.Recovery = Recovery
engine.RecoveryTests = RecoveryTests
engine.ready_state, engine.wait_ready = ready_state, wait_ready


if __name__ == "__main__":
    engine.main()
