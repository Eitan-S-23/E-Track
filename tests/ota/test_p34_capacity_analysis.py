"""Pure host tests. No device access, generated files or global temp directory."""
import importlib.util
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[2]
SPEC = importlib.util.spec_from_file_location("capacity", ROOT / "Tools/ota/p34_capacity_analysis.py")
M = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(M)


def sample(tick, confirmed=False, start=10, end=20):
    return dict(phase="app", final_phase="app", version=30230, initialized=True,
                confirmed=confirmed, tick=tick, start_ns=start, end_ns=end)


class Tests(unittest.TestCase):
    def test_decimal_binary_targets_are_separate(self):
        value = M.budgets(1048576, 116.718954, 11.760218, 1.741045)
        self.assertEqual([x["payload_Bps"] for x in value["targets"]], [50000, 51200])
        self.assertEqual(value["targets"][1]["transfer_seconds"], 20.48)
        self.assertTrue(all(x["serial_model_exceeds_budget"] for x in value["targets"]))
        self.assertAlmostEqual(value["uart_payload_ceiling_Bps"], 83073.8028169)

    def test_invalid_costs_are_not_evidence(self):
        for value in (float("nan"), float("inf"), -1, 0, True):
            with self.subTest(value=value), self.assertRaises(ValueError):
                M.budgets(1048576, value, 1, 1)
        with self.assertRaises(ValueError):
            M.budgets(4097, 1, 1, 1)

    def test_trace_ends_before_health_window(self):
        value = M.confirmation_coverage([sample(18064)], 30229, 30230, 30000)
        self.assertTrue(value["ended_before_window_from_zero"])
        self.assertEqual(value["result"], "EVIDENCE_GAP")
        self.assertIsNone(value["confirmed_bracket_ns"])

    def test_later_unconfirmed_sample_does_not_prove_health(self):
        value = M.confirmation_coverage([sample(35000)], 30229, 30230, 30000)
        self.assertFalse(value["ended_before_window_from_zero"])
        self.assertEqual(value["result"], "EVIDENCE_GAP")

    def test_confirmation_has_original_bracket_only(self):
        value = M.confirmation_coverage([sample(31000, True)], 30229, 30230, 30000)
        self.assertEqual(value["confirmed_bracket_ns"], [10, 20])
        self.assertEqual(value["result"], "CONFIRMATION_OBSERVED")

    def test_clock_or_epoch_ambiguity_fails_closed(self):
        for values in ([sample(18, start=20, end=10)],
                       [sample(20), sample(1, start=30, end=40)],
                       [sample(20), sample(30, start=15, end=40)]):
            with self.subTest(values=values), self.assertRaises(ValueError):
                M.confirmation_coverage(values, 30229, 30230, 30000)

    def test_uninitialized_target_is_not_ready(self):
        value = sample(31000, True)
        value["initialized"] = False
        with self.assertRaises(ValueError):
            M.confirmation_coverage([value], 30229, 30230, 30000)


if __name__ == "__main__":
    unittest.main(verbosity=2)
