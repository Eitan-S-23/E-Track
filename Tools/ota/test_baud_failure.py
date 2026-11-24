"""Offline failure classification; never starts a device runtime."""
import importlib.util
import json
from pathlib import Path
import unittest


spec = importlib.util.spec_from_file_location("baud_failure_tested", Path(__file__).with_name("baud_failure.py"))
subject = importlib.util.module_from_spec(spec)
spec.loader.exec_module(subject)


class FailureTests(unittest.TestCase):
    def fixture(self):
        lines = ["Reset: NRST SW", "OTA: BCB already CONFIRMED vcode=30207", "Reset: NRST SW",
                 "P34BOOT: requested=115200 actual=115200 retained=0 error=0 clock=1",
                 "Reset: NRST WDT", "P34BOOT: requested=115200 actual=115200 retained=0 error=0 clock=1",
                 "Reset: NRST WDT", "OTA: BCB already CONFIRMED vcode=30207"]
        events = [dict(kind="rtt-line", time=str(index), line=line + "\r\n") for index, line in enumerate(lines)]
        capture = dict(outcome="not-completed", input=dict(currentVersionCode=30207, targetVersionCode=30208))
        messages = 'OTA_MONO MONO_END_ACK_OK monoUs=9\nOTA_LINK_STATS ' + json.dumps(
            dict(label="upgrade", transfer=dict(outcome="ok")))
        return capture, messages, subject.startup_summary(events)

    def test_watchdog_fallback_is_not_success(self):
        result = subject.classify(*self.fixture(), 30207, 30208)
        self.assertEqual(result["result"], "WATCHDOG_ROLLBACK_OBSERVED")
        self.assertEqual(result["diagnostic_startups"], 2)
        self.assertEqual(result["later_watchdog_resets"], 2)
        self.assertFalse(result["ota_success"])
        self.assertEqual(result["exact_startup_cause"], "NOT_ESTABLISHED")

    def test_no_target_start_does_not_prove_rollback(self):
        capture, messages, boots = self.fixture()
        result = subject.classify(capture, messages, boots[:1], 30207, 30208)
        self.assertEqual(result["result"], "FAILED_NEEDS_TRIAGE")

    def test_target_without_return_does_not_prove_rollback(self):
        capture, messages, boots = self.fixture()
        result = subject.classify(capture, messages, boots[:-1], 30207, 30208)
        self.assertFalse(result["baseline_confirmation_after_target"])

    def test_completed_snapshot_is_not_reclassified(self):
        capture, messages, boots = self.fixture()
        capture["outcome"] = "completed"
        with self.assertRaises(RuntimeError):
            subject.classify(capture, messages, boots, 30207, 30208)

    def test_conflicting_transfer_summaries_are_rejected(self):
        capture, messages, boots = self.fixture()
        with self.assertRaises(RuntimeError):
            subject.classify(capture, messages + "\n" + messages, boots, 30207, 30208)


if __name__ == "__main__":
    unittest.main()
