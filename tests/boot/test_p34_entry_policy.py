"""New physical-order policy scenarios, not a rerun of BCB transaction tests."""
from dataclasses import replace
from pathlib import Path
import sys
import unittest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT/"Tools/ota/recovery_confirm"))
from entry_policy import Binding, Settlement, binding_reason, settlement_reason, route_result


class EntryPolicyTests(unittest.TestCase):
    plan = Binding("synthetic-operation", "synthetic-board", "synthetic-probe", "synthetic-epoch",
                   "boot-digest-fixture", "app-digest-fixture", "bcb-digest-fixture")
    evidence = Settlement("synthetic-epoch", 100, 6200, 5000,
                          "synthetic-part-proof", "synthetic-clock-proof", "synthetic-ack-proof",
                          6100, True, True, True)

    def route(self, evidence=None, code="RC_CONFIRMED", equal=True, exact=True):
        return route_result(self.plan, self.plan, evidence or self.evidence, code,
                            observations_equal=equal, exact_target_pair=exact)

    def test_positive_is_not_device_authorization(self):
        self.assertEqual(self.route(), "COMPLETION_CLASSIFIABLE_IN_MODEL")

    def test_all_binding_dimensions(self):
        for field in Binding.__dataclass_fields__:
            with self.subTest(field=field):
                self.assertNotEqual(binding_reason(self.plan, replace(self.plan, **{field: "other"})), "BOUND_IN_MODEL")
                self.assertEqual(binding_reason(self.plan, replace(self.plan, **{field: ""})), "UNKNOWN_BINDING")

    def test_identical_early_reads_do_not_prove_settlement(self):
        # A delayed write can leave two identical old reads, then become new.
        def stored(at):
            return "old-pair" if at < 5100 else "target-pair"
        self.assertEqual(stored(1000), stored(2000))
        self.assertNotEqual(stored(2000), stored(6200))
        early = replace(self.evidence, observed_us=2000, ready_ack_us=1900)
        self.assertEqual(self.route(early), "HOLD_NO_RETRY_OR_RESET")
        self.assertEqual(self.route(), "COMPLETION_CLASSIFIABLE_IN_MODEL")

    def test_unknown_last_stop(self):
        self.assertEqual(self.route(replace(self.evidence, last_possible_stop_us=None)), "HOLD_NO_RETRY_OR_RESET")

    def test_late_stop_restarts_required_horizon(self):
        self.assertEqual(self.route(replace(self.evidence, last_possible_stop_us=4000)), "HOLD_NO_RETRY_OR_RESET")

    def test_missing_part_or_clock_or_ack_basis(self):
        for field in ("part_evidence", "clock_evidence", "ack_semantics_evidence"):
            with self.subTest(field=field):
                self.assertEqual(self.route(replace(self.evidence, **{field: None})), "HOLD_NO_RETRY_OR_RESET")

    def test_reset_epoch_cannot_reuse_settlement(self):
        self.assertEqual(self.route(replace(self.evidence, epoch="after-reset")), "HOLD_NO_RETRY_OR_RESET")

    def test_clock_invalid(self):
        for values in ({"observed_us": 99}, {"last_possible_stop_us": True}, {"max_write_us": 0}):
            self.assertEqual(self.route(replace(self.evidence, **values)), "HOLD_NO_RETRY_OR_RESET")

    def test_lines_high_not_equivalent_to_protocol_idle(self):
        self.assertEqual(self.route(replace(self.evidence, protocol_idle=False)), "HOLD_NO_RETRY_OR_RESET")

    def test_other_writer_or_power_uncertainty(self):
        for field in ("exclusive", "power_stable"):
            self.assertEqual(self.route(replace(self.evidence, **{field: False})), "HOLD_NO_RETRY_OR_RESET")

    def test_stale_or_future_ack(self):
        for ack in (1000, 7000, None):
            self.assertEqual(self.route(replace(self.evidence, ready_ack_us=ack)), "HOLD_NO_RETRY_OR_RESET")

    def test_rejected_already_branch_stops(self):
        self.assertEqual(self.route(code="RC_REJECTED", equal=False), "STOP_READ_ONLY_RECONCILIATION")

    def test_unknown_never_reexecutes(self):
        self.assertEqual(self.route(code="RC_UNKNOWN"), "STOP_READ_ONLY_RECONCILIATION")

    def test_not_confirmed_does_not_claim_unchanged(self):
        self.assertEqual(self.route(code="RC_NOT_CONFIRMED", exact=False), "STOP_NOT_CONFIRMED_NO_RETRY")

    def test_completion_requires_exact_target(self):
        self.assertEqual(self.route(exact=False), "STOP_UNEXPECTED_RESULT")
        self.assertEqual(self.route(equal=False), "STOP_READ_ONLY_RECONCILIATION")


if __name__ == "__main__":
    unittest.main(verbosity=2)
