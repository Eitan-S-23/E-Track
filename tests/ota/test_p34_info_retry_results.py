"""Reject unfinished/forced owners before any offline analysis writes."""
from pathlib import Path
import sys
import unittest
from unittest.mock import Mock

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "Tools/ota"))
import p34_info_retry_results as f


class Tests(unittest.TestCase):
    def store(self, cell=None):
        def read(path):
            if path.name == "closed.json":
                return dict(worker_exit=0, forced_termination=False)
            return cell or dict(result="FULL_INSTALL_OBSERVED")
        return Mock(read=read)

    def test_closed_original_is_admitted(self):
        f.closed(self.store(), ROOT)
        f.closed(self.store(cell=dict(result="FULL_INSTALL_VERIFIED")), ROOT)

    def test_failed_or_forced_owner_is_rejected(self):
        for value in (dict(worker_exit=1, forced_termination=False),
                      dict(worker_exit=0, forced_termination=True)):
            store = Mock(read=lambda path: value)
            with self.assertRaises(RuntimeError): f.closed(store, ROOT)

    def test_incomplete_cell_is_rejected(self):
        for value in (dict(result="FULL_INSTALL_INCOMPLETE"),
                      dict(result="FULL_INSTALL_OBSERVED", error="analysis failed"),
                      dict(result="FULL_INSTALL_OBSERVED", cleanup_error="unclosed")):
            with self.assertRaises(RuntimeError): f.closed(self.store(cell=value), ROOT)

    def test_public_boundaries_remain_separate(self):
        messages = "\n".join(("OTA_MONO MONO_BUDGET_START monoUs=1 wallUs=1",
            "OTA_MONO MONO_END_ACK_OK monoUs=1000001 wallUs=2 durable=50000",
            "OTA_MONO MONO_REBOOT_VERIFIED monoUs=21000001 wallUs=3"))
        result = f.metrics.public_metrics(messages, 50000)
        self.assertEqual(result["throughput_kb_s"], 50)
        self.assertEqual(result["installation_reconnect_seconds"], 20)
        self.assertTrue(result["transfer_target_met"] and result["installation_target_met"])


if __name__ == "__main__":
    unittest.main(verbosity=2)
