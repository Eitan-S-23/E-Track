"""Pure timing model checks and immutable original pressure-log regressions."""
import json
from pathlib import Path
import sys
import unittest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "Tools/ota"))
import p34_wait_analysis as wait


class WaitTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        path = ROOT / ".cache/p34-session/runs/20260929T081420-42700/cells/s04/finished/snapshot.jsonl"
        rows = [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines()]
        cls.messages = "\n".join(row["message"] for row in rows if row.get("kind") == "line")

    def test_original_pressure_partition_closes_without_mixing_clocks(self):
        result = wait.analyze(self.messages, 1048576, 32)
        self.assertEqual(sum(result["transfer_partition_us"].values()), 138987678)
        self.assertEqual((result["data_segments"], len(result["blocks"])), (8192, 256))
        self.assertEqual(result["transfer_partition_us"]["gatt_us"], 56767572)

    def test_free_credit_is_not_fabricated_as_ack_wait(self):
        result = wait.infer_gap(1000, 1500, 200, [1600], 32)
        self.assertEqual((result["credit_wait_est_us"], result["after_credit_est_us"]), (0, 300))

    def test_full_credit_shared_ack(self):
        result = wait.infer_gap(1000, 1500, 200, [1200] * 32, 32)
        self.assertEqual((result["credit_wait_est_us"], result["after_credit_est_us"]), (200, 100))

    def test_old_window8_model_keeps_its_semantics(self):
        self.assertEqual(wait.infer_gap(1000, 1510, 300, [1200] * 8, 8)["after_credit_est_us"], 10)

    def test_invalid_timing_and_overfull_credit_fail(self):
        for args in ((1000, 1100, 200, [], 32), (1000, 1250, 200, [1300] * 32, 32),
                     (1000, 1500, 200, [1200] * 33, 32), (1000, 1500, 200, [], 0)):
            with self.subTest(args=args), self.assertRaises(ValueError):
                wait.infer_gap(*args)

    def test_empty_metrics_do_not_invent_samples(self):
        self.assertEqual(wait.metric([])["count"], 0)
        self.assertIsNone(wait.metric([])["p99_us"])
        self.assertEqual(wait.metric([12, 4, 9])["p50_us"], 9)

    def test_missing_and_duplicate_summary_rejected(self):
        lines = self.messages.splitlines()
        summary = next(line for line in lines if line.startswith('OTA_LINK_STATS ') and '"label":"upgrade"' in line)
        for text in (self.messages.replace(summary, ""), self.messages + "\n" + summary):
            with self.assertRaises(ValueError):
                wait.analyze(text, 1048576, 32)

    def test_missing_data_or_wrong_total_rejected(self):
        line = next(line for line in self.messages.splitlines() if 'label=upgrade kind=segment_first_send' in line)
        with self.assertRaises(ValueError):
            wait.analyze(self.messages.replace(line, "", 1), 1048576, 32)
        with self.assertRaises(ValueError):
            wait.analyze(self.messages, 1048448, 32)


if __name__ == "__main__":
    unittest.main(verbosity=2)
