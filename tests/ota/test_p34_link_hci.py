"""The scoped report adapter preserves history and uses current completed evidence."""
from pathlib import Path
import sys
import unittest
from unittest.mock import Mock, patch

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "Tools/ota"))
import p34_link_hci as f


class Tests(unittest.TestCase):
    def data(self):
        pointer = {"path": "report", "sha256": "report-hash"}
        report = {"summary": {"input": {"targetVersionCode": 30266}}}
        status = dict(result="HCI_STATUS_READ", prior=pointer, usb_closed=True,
            properties={"persist.sys.bluetooth.btsnooplogmode": "full"})
        closed = dict(worker_exit=0, forced_termination=False)
        return pointer, report, status, closed

    def test_current_closed_inputs(self):
        pointer, report, status, closed = self.data()
        s = Mock(); s.read.side_effect = [report, status, closed]
        with patch.object(f.link, "inputs", return_value=(pointer, {"apk": "current"})):
            self.assertEqual(f.inputs(s), (pointer, {"apk": "current"}))

    def test_stale_status_or_wrong_target_rejected(self):
        for field in ("target", "prior", "logging", "closure"):
            pointer, report, status, closed = self.data()
            if field == "target": report["summary"]["input"]["targetVersionCode"] = 30252
            if field == "prior": status["prior"] = {}
            if field == "logging": status["properties"]["persist.sys.bluetooth.btsnooplogmode"] = "disable"
            if field == "closure": closed["forced_termination"] = True
            s = Mock(); s.read.side_effect = [report, status, closed]
            with patch.object(f.link, "inputs", return_value=(pointer, {})), self.assertRaises(RuntimeError):
                f.inputs(s)

    def test_clone_binds_new_output_without_mutating_original(self):
        original = dict(f.previous.worker.__globals__)
        called = Mock()
        with patch.object(f.link.previous.measure.batch, "clone", return_value=called) as clone:
            s = Mock(); f.worker(s)
        self.assertEqual(f.previous.worker.__globals__, original)
        self.assertEqual(clone.call_args.kwargs["OUT"], f.OUT)
        self.assertEqual(clone.call_args.kwargs["TESTS"], f.TESTS)
        self.assertIs(clone.call_args.kwargs["status"].inputs, f.inputs)
        called.assert_called_once_with(s)


if __name__ == "__main__":
    unittest.main(verbosity=2)
