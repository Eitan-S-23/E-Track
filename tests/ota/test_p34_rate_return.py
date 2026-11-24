"""Pure checks for the evidence-bound reversible baud discriminator."""
import importlib.util
from pathlib import Path
import types
import unittest

ROOT = Path(__file__).resolve().parents[2]
SPEC = importlib.util.spec_from_file_location("rate_tests", ROOT / "Tools/ota/p34_rate_return.py")
M = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(M)


class Tests(unittest.TestCase):
    def test_only_reconciled_pre_device_failure_allows_fresh_usb_scope(self):
        result = dict(error="RuntimeError: exact phone did not become online in the bounded USB window", trials=[])
        owner = dict(worker_exit=1, forced_termination=False)
        M.retry_ready(result, dict(online=False), owner)
        for altered in (dict(result, error="bad ACK"), dict(result, trials=[{}])):
            with self.assertRaises(RuntimeError):
                M.retry_ready(altered, dict(online=False), owner)
        with self.assertRaises(RuntimeError):
            M.retry_ready(result, dict(online=True), owner)

    def test_one_new_window4_worker_at460800(self):
        calls = []
        capacity = types.SimpleNamespace(worker=lambda **kwargs: calls.append(kwargs) or 0)
        self.assertEqual(M.run_worker(capacity), 0)
        self.assertEqual(capacity.SESSION, "session-rate460-w4")
        self.assertEqual(capacity.WINDOW, 4)
        self.assertEqual(calls, [dict(baud=460800)])

    def test_only_actual_prior_hci_corruption_admits_the_discriminator(self):
        value = dict(result="CORRUPTION_ALREADY_PRESENT_AT_HCI", notifications_byte_identical=True,
                     retained_verified=True, missing_ack3_prefix_hex="a55a82010300")
        M.require_prior(value)
        for key, wrong in (("result", "HCI_COMPLETE_BROWSER_DIFFERS"), ("notifications_byte_identical", False),
                           ("retained_verified", False), ("missing_ack3_prefix_hex", None)):
            altered = dict(value); altered[key] = wrong
            with self.subTest(key=key), self.assertRaises(RuntimeError):
                M.require_prior(altered)

    def test_rate_worker_restores_on_normal_and_error_closure(self):
        source = (ROOT / "Tools/ota/p34_capacity_session.py").read_text()
        self.assertEqual(source.count("mcu.close(restore=baud != 921600)"), 2)
        self.assertIn('mcu.tune_rate(baud, "selected-capacity-baud")', source)
        self.assertIn('run=armed["run"], baud=baud', source)


if __name__ == "__main__":
    unittest.main(verbosity=2)
