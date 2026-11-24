"""Host-only regressions. Fixtures and receipts stay in an explicit project directory."""
from __future__ import annotations

import argparse
import contextlib
import copy
import importlib.util
import io
import json
from pathlib import Path
import sys
import unittest
from types import SimpleNamespace
from unittest.mock import patch

SELF = Path(__file__).resolve()
spec = importlib.util.spec_from_file_location("repeat_cycle", SELF.with_name("repeat_cycle.py"))
r = importlib.util.module_from_spec(spec)
spec.loader.exec_module(r)
OUT = None


class RepeatCycleTests(unittest.TestCase):
    def setUp(self):
        self.out = r.checked(OUT / self._testMethodName)
        self.journal = r.Journal(self.out, {"run": "fake", "source": "pinned"})
        self.result = self.out / "original.json"
        self.calls = 0

    def action(self):
        self.calls += 1
        r.write(self.result, {"result": "VERIFIED"})

    def phase(self):
        return self.journal.phase("restore", self.action, self.result,
                                  lambda p: self.validate(r.read(p)))

    @staticmethod
    def validate(value):
        r.require(value["result"] == "VERIFIED", "failed original result")
        return value

    def test_completed_phase_is_not_reexecuted(self):
        self.phase()
        self.phase()
        self.assertEqual(self.calls, 1)

    def test_uncertain_started_mutation_blocks_replay(self):
        r.write(self.out / "actions/restore.intent.json", {"status": "started"})
        with self.assertRaisesRegex(RuntimeError, "uncertain"):
            self.phase()
        self.assertEqual(self.calls, 0)

    def test_completed_original_is_adopted_after_interruption(self):
        r.write(self.out / "actions/restore.intent.json", {"status": "started"})
        self.action()
        self.calls = 0
        self.phase()
        self.assertEqual(self.calls, 0)
        self.assertTrue(r.read(self.out / "actions/restore.done.json")["adopted"])

    def test_failed_original_cannot_be_adopted(self):
        r.write(self.result, {"result": "FAILED"})
        with self.assertRaisesRegex(RuntimeError, "failed original"):
            self.phase()
        self.assertEqual(self.calls, 0)

    def test_changed_phase_source_blocks_resume(self):
        self.phase()
        self.journal.binding = {"run": "fake", "source": "different"}
        with self.assertRaisesRegex(RuntimeError, "binding changed"):
            self.phase()
        self.assertEqual(self.calls, 1)

    def test_changed_completed_evidence_is_rejected(self):
        self.phase()
        with patch.object(r, "record", return_value={"path": str(self.result), "sha256": "changed"}):
            with self.assertRaisesRegex(RuntimeError, "changed"):
                self.phase()

    def test_action_return_without_evidence_is_not_success(self):
        with self.assertRaisesRegex(RuntimeError, "without evidence"):
            self.journal.phase("restore", lambda: None, self.result)
        with self.assertRaisesRegex(RuntimeError, "uncertain"):
            self.phase()
        self.assertEqual(self.calls, 0)

    def test_output_boundary_rejects_sibling_root(self):
        with self.assertRaises(r.io.OutputBoundaryError):
            r.checked(r.ROOT.parent / (r.ROOT.name + "-other") / "out.json")

    def test_relative_escape_is_rejected_before_writing(self):
        with self.assertRaises(r.io.OutputBoundaryError):
            r.Journal(r.ROOT / "../out", "fake")

    def test_labels_cannot_escape_or_alias_existing_paths(self):
        for name in ("../c2", "a/b", "C:\\temp", "", "c2.001"):
            with self.subTest(name=name), self.assertRaises(RuntimeError):
                r.valid_name(name)

    def test_budget_has_independent_human_and_transfer_allowances(self):
        self.assertGreaterEqual(r.CAPTURE_SECONDS,
                                r.PREPARE_SECONDS + r.START_WAIT_SECONDS + 1280 + 120)
        self.assertGreaterEqual(r.COORDINATOR_SECONDS, r.CAPTURE_SECONDS + 900)
        self.assertLess(r.COORDINATOR_SECONDS + 90, 5380)

    def test_active_or_dirty_app_cannot_be_armed(self):
        health = dict(healthy=True, lost=0, error=None, upgradeStarts=0, upgradeEnds=0, outcome=None)
        r.healthy(health, unused=True)
        for key, value in (("healthy", False), ("lost", 1), ("error", "io"), ("upgradeStarts", 1),
                           ("upgradeEnds", 1), ("outcome", "completed")):
            with self.subTest(key=key), self.assertRaises(RuntimeError):
                r.healthy(dict(health, **{key: value}), unused=True)

    def test_wrong_package_device_and_source_are_rejected(self):
        path = r.REGISTRY / "cells/reuse-with/finished/binding.json"
        original = r.read(path)
        for key, value in (("packageSha256", "wrong"), ("packageBytes", 1),
                           ("deviceAddress", "other"), ("currentImageSha256", "other"),
                           ("targetVersionCode", 30208)):
            changed = copy.deepcopy(original)
            changed["summary"]["input"][key] = value
            with self.subTest(key=key), patch.object(r, "read", return_value=changed):
                with self.assertRaisesRegex(RuntimeError, "mismatch"):
                    r.verify_finished(path)

    def test_dirty_staging_blocks_baseline_adoption(self):
        path = r.RESTORE / "execute-screen-c1/result.json"
        value = r.read(path)
        dirty = self.out / "dirty.bin"
        r.checked(dirty.parent).mkdir(parents=True)
        with dirty.open("xb") as stream:
            stream.write(b"\0" * 4096)
        value["final_journal"]["path"] = str(dirty)
        with patch.object(r, "read", return_value=value):
            with self.assertRaisesRegex(RuntimeError, "erased staging"):
                r.verify_board(path, restored=True)

    def test_wrong_board_or_boot_blocks_adoption(self):
        path = r.REGISTRY / "cells/reuse-with/mcu/result.json"
        for key in ("final_image", "final_boot"):
            changed = r.read(path)
            changed[key]["sha256"] = "wrong"
            with self.subTest(key=key), patch.object(r, "read", return_value=changed):
                with self.assertRaisesRegex(RuntimeError, "wrong full"):
                    r.verify_board(path)

    def test_original_c1_measurement_is_not_threshold_acceptance(self):
        cell = r.REGISTRY / "cells/reuse-with"
        value = r.measurement(cell, cell / "mcu/result.json", "reuse-with")
        self.assertAlmostEqual(value["transfer_seconds"], 247.039059)
        self.assertEqual(value["discovers"]["calls"], 1)
        self.assertEqual(value["data_segments_unique"], 2224)
        self.assertEqual(value["data_retransmit_frames"], 0)
        self.assertEqual(value["ack_sample_status"], "partial:missing=11,early=11")
        self.assertFalse(value["threshold_eligible"])
        self.assertEqual(value["independent_acceptance"], "NOT_RUN")

    def test_fake_multi_phase_cycle_resumes_without_device_replay(self):
        calls = []
        for _ in range(2):
            for name in ("release", "admit", "restore", "capture", "launch", "arm", "finished"):
                evidence = self.out / (name + ".json")
                def action(name=name, evidence=evidence):
                    calls.append(name)
                    r.write(evidence, {"result": "VERIFIED"})
                self.journal.phase(name, action, evidence)
        self.assertEqual(len(calls), 7)

    def test_closed_observer_prevents_app_launch(self):
        backend = object.__new__(r.Backend)
        backend.cell = backend.out = self.out
        r.write(self.out / "mcu/state.json", dict(preflight_ready=True,
                state=dict(epoch=0, baseline_confirmed=True, ready_to_begin=True, begin_reserved=False,
                           target_bcb_observed=False, ready_for_final_readback=False)))
        backend.fresh_baseline()
        r.write(self.out / "mcu/result.json", {"result": "DEVICE_WINDOW_ENDED"})
        with self.assertRaisesRegex(RuntimeError, "observer closed"):
            backend.fresh_baseline()

    def test_in_progress_download_is_waited_for_not_retried(self):
        backend = object.__new__(r.Backend)
        health = dict(healthy=True, lost=0, error=None, upgradeStarts=0, upgradeEnds=0, outcome=None)
        backend.app_state = lambda **kw: dict(package="fake", health=health)
        backend.phone = lambda: SimpleNamespace(command=lambda *a, **kw: "12345")
        self.assertIsNone(backend.query_ready())

    def test_missing_original_observation_does_not_start_ota(self):
        backend = object.__new__(r.Backend)
        backend.app_state = lambda **kw: None
        backend.phone = lambda: None
        self.assertIsNone(backend.query_ready())

    def test_backend_outputs_and_apply_allowance_are_bound(self):
        backend = r.Backend(dict(out=str(self.out), run="fake", candidate="discover-without"))
        self.assertEqual(backend.phone().RUNTIME, self.out / "phone-r1")
        self.assertEqual(backend.phone().cell("discover-without"), self.out / "cells/discover-without")
        collector = backend.collector()
        self.assertEqual(collector.OUT, self.out)
        self.assertEqual(collector.SECONDS, r.CAPTURE_SECONDS)
        gate = collector.epoch.AppEpochGate(clock=lambda: 10, timeout=60)
        gate.ready = True
        gate.invalidate("Boot/reset")
        self.assertEqual(gate.deadline, 310)
        gate.invalidate("Boot/reset")
        self.assertEqual(gate.deadline, 310)

    def test_completed_v1_config_uses_verified_source_archive(self):
        value = r.config_for("c3-001", completed=True)
        self.assertEqual(value["candidate"], "reuse-without")

    def test_live_source_drift_is_never_accepted_from_archive(self):
        with self.assertRaisesRegex(RuntimeError, "source/evidence changed"):
            r.config_for("c3-001")

    def test_unknown_archive_binding_is_rejected(self):
        item = dict(r.read(r.SOURCE_ARCHIVE / "manifest-v1.json")["files"][0]["original"])
        item["path"] = str(r.ROOT / "Tools/ota/not-the-preserved-source.py")
        with self.assertRaisesRegex(RuntimeError, "no exact preserved"):
            r.unchanged_source(item, completed=True)

    def test_wrong_archived_digest_is_rejected(self):
        item = dict(r.read(r.SOURCE_ARCHIVE / "manifest-v1.json")["files"][0]["original"])
        item["sha256"] = "0" * 64
        with self.assertRaisesRegex(RuntimeError, "no exact preserved"):
            r.unchanged_source(item, completed=True)

    def test_completed_phone_route_selects_latest_closed_recovery(self):
        runtime, supervisor = r.completed_phone_route(r.RUNS / "c3-001")
        self.assertEqual(runtime.name, "phone-recovery-r1")
        self.assertEqual(supervisor.name, "adb-recovery-r1")

    def test_unclosed_phone_route_blocks_a_new_cycle(self):
        r.write(self.out / "phone-r1/ready.json", dict(time=r.now(), port=5062, serial="10ADA4197U001CK"))
        with self.assertRaisesRegex(RuntimeError, "not closed"):
            r.completed_phone_route(self.out)

    def test_normal_entry_waits_for_the_next_ready_projection(self):
        backend = object.__new__(r.Backend)
        backend.cell = backend.out = self.out
        pending = dict(preflight_ready=False, state=dict(epoch=0, baseline_confirmed=False,
                       ready_to_begin=False, begin_reserved=False, target_bcb_observed=False,
                       ready_for_final_readback=False))
        ready = copy.deepcopy(pending)
        ready["preflight_ready"] = ready["state"]["baseline_confirmed"] = ready["state"]["ready_to_begin"] = True
        r.write(self.out / "mcu/state.json", pending)
        with patch.object(r, "read", side_effect=[pending, ready]) as reads:
            self.assertTrue(backend.fresh_baseline()["preflight_ready"])
        self.assertEqual(reads.call_count, 2)

    def actual_capture_state(self):
        backend = r.Backend(dict(out=str(self.out), run="host-test-unused", candidate="reuse-without"))
        return backend.collector().base.CaptureState()

    def test_normal_entry_waits_for_actual_initial_capture_confirmation(self):
        state = self.actual_capture_state()
        pending = dict(preflight_ready=False, state=state.snapshot())
        self.assertIsNone(pending["state"]["epoch"])
        self.assertFalse(r.ready_state(pending, 0))
        state.observe(dict(sample=dict(epoch=0), lines=["OTA: BCB already CONFIRMED vcode=30206\r\n"]))
        self.assertTrue(state.can_begin())
        ready = dict(preflight_ready=True, state=state.snapshot())
        backend = object.__new__(r.Backend)
        backend.cell = backend.out = self.out
        r.write(self.out / "mcu/state.json", pending)
        with patch.object(r, "read", side_effect=[pending, ready]) as reads:
            self.assertTrue(backend.fresh_baseline()["preflight_ready"])
        self.assertEqual(reads.call_count, 2)

    def test_unobserved_epoch_rejects_any_readiness_activity_or_error(self):
        initial = dict(preflight_ready=False, state=self.actual_capture_state().snapshot())
        for key, value in (("preflight_ready", True), ("error", "gap")):
            with self.subTest(key=key), self.assertRaisesRegex(RuntimeError, "conflicts"):
                r.ready_state(dict(initial, **{key: value}), 0)
        for key, value in (("begin_reserved", True), ("baseline_confirmed", True),
                           ("target_bcb_observed", True), ("ready_to_begin", True),
                           ("ready_for_final_readback", True), ("begin_epoch", 0)):
            changed = dict(initial, state=dict(initial["state"], **{key: value}))
            with self.subTest(key=key), self.assertRaisesRegex(RuntimeError, "conflicts"):
                r.ready_state(changed, 0)

    def test_unobserved_epoch_wait_still_has_a_deadline(self):
        pending = dict(preflight_ready=False, state=self.actual_capture_state().snapshot())
        clock = [0.0]
        def sleep(seconds):
            clock[0] += seconds
        with self.assertRaisesRegex(RuntimeError, "within its bound"):
            r.wait_ready(lambda: (pending, 0), lambda: False, seconds=.2,
                         clock=lambda: clock[0], sleep=sleep)

    def test_recorded_begin_epoch_is_not_an_unused_baseline(self):
        state = self.actual_capture_state()
        state.observe(dict(sample=dict(epoch=0), lines=["OTA: BCB already CONFIRMED vcode=30206\r\n"]))
        value = dict(preflight_ready=True, state=dict(state.snapshot(), begin_epoch=0))
        with self.assertRaisesRegex(RuntimeError, "no longer an unused baseline"):
            r.ready_state(value, 0)

    def test_completed_v2_config_uses_exact_preserved_sources(self):
        self.assertEqual(r.config_for("c3-002", completed=True)["candidate"], "reuse-without")

    def test_live_v2_source_drift_cannot_use_archive(self):
        with self.assertRaisesRegex(RuntimeError, "source/evidence changed"):
            r.config_for("c3-002")

    def test_completed_confirmation_resume_never_constructs_a_device_backend(self):
        output = io.StringIO()
        with patch.object(r, "Backend", side_effect=AssertionError("device backend invoked")):
            with contextlib.redirect_stdout(output):
                r.resume("c3-002")
        result = json.loads(output.getvalue())
        self.assertEqual(result["state"], "COMPLETED")
        self.assertEqual(result["device_commands"], 0)

    def test_corrupted_v2_archive_is_rejected(self):
        entry = r.read(r.SOURCE_ARCHIVE / "manifest-v2.json")["files"][0]
        original_record = r.record
        def corrupted(path):
            result = original_record(path)
            return dict(result, sha256="0" * 64) if str(path) == entry["archive"] else result
        with patch.object(r, "record", side_effect=corrupted):
            with self.assertRaisesRegex(RuntimeError, "original source archive changed"):
                r.unchanged_source(entry["original"], completed=True)


def main():
    global OUT
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    r.require(Path.cwd().resolve() == r.ROOT and sys.flags.isolated and sys.flags.no_site and sys.dont_write_bytecode,
              "isolated Python and explicit project cwd required")
    OUT = r.checked(args.out)
    r.require(not OUT.exists(), "fresh project-local test output required")
    for name in ("tests.log", "result.json"):
        r.checked(OUT / name)
    OUT.mkdir(parents=True)
    output = io.StringIO()
    recovery = r.load("repeat_recovery_tests", SELF.with_name("resume_cycle_v2.py"))
    suite = unittest.TestSuite((unittest.defaultTestLoader.loadTestsFromTestCase(RepeatCycleTests),
                               unittest.defaultTestLoader.loadTestsFromTestCase(recovery.RecoveryTests)))
    result = unittest.TextTestRunner(stream=output, verbosity=2).run(suite)
    log = r.checked(OUT / "tests.log")
    with log.open("x", encoding="utf-8", newline="\n") as stream:
        stream.write(output.getvalue())
    r.write(OUT / "result.json", dict(time=r.now(), passed=result.wasSuccessful(), count=result.testsRun,
            failures=len(result.failures), errors=len(result.errors), driver=r.record(r.SELF),
            tests=r.record(SELF), log=r.record(log), hardware_contacted=False))
    print(output.getvalue(), end="")
    raise SystemExit(0 if result.wasSuccessful() else 1)


if __name__ == "__main__":
    main()
