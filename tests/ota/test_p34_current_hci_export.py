"""Current-trial binding and immutable-worker reuse for diagnostic export."""
from pathlib import Path
import sys
import unittest
from unittest.mock import Mock, patch

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "Tools/ota"))
import p34_current_hci_export as f


class Tests(unittest.TestCase):
    def api(self):
        store = Mock()
        store.checked.side_effect = lambda p: Path(p)
        api = f.Exporter(store, "trial", "status", "out", "tests/result.json")
        return store, api

    def test_arbitrary_current_trial_not_fixed_version(self):
        store, api = self.api()
        pointer = dict(path="current", sha256="current-hash")
        status = dict(result="HCI_STATUS_READ", prior=pointer, usb_closed=True,
                      properties={"persist.sys.bluetooth.btsnooplogmode": "full"})
        closed = dict(worker_exit=0, forced_termination=False)
        store.read.side_effect = [status, closed]
        with patch.object(f.old.link, "inputs", return_value=(pointer, {"apk": "current-apk"})) as load:
            self.assertEqual(api.inputs(store), (pointer, {"apk": "current-apk"}))
        load.assert_called_once_with(store, Path("trial"))

    def test_stale_status_logging_or_closure_rejected(self):
        for key in ("prior", "usb", "logging", "forced", "exit"):
            store, api = self.api()
            status = dict(result="HCI_STATUS_READ", prior={"path": "new"}, usb_closed=True,
                          properties={"persist.sys.bluetooth.btsnooplogmode": "full"})
            closed = dict(worker_exit=0, forced_termination=False)
            if key == "prior": status["prior"] = {"path": "old"}
            if key == "usb": status["usb_closed"] = False
            if key == "logging": status["properties"]["persist.sys.bluetooth.btsnooplogmode"] = "filtered"
            if key == "forced": closed["forced_termination"] = True
            if key == "exit": closed["worker_exit"] = 1
            store.read.side_effect = [status, closed]
            with patch.object(f.old.link, "inputs", return_value=({"path": "new"}, {})), self.assertRaises(RuntimeError):
                api.inputs(store)

    def test_reuses_worker_without_mutating_old_globals(self):
        store, api = self.api()
        before = dict(f.old.previous.worker.__globals__)
        called = Mock()
        with patch.object(f.old.link.previous.measure.batch, "clone", return_value=called) as clone:
            api.worker()
        self.assertEqual(before, f.old.previous.worker.__globals__)
        self.assertEqual(clone.call_args.kwargs["OUT"], Path("out"))
        self.assertEqual(clone.call_args.kwargs["TESTS"], Path("tests/result.json"))
        called.assert_called_once_with(store)

    def test_preflight_contains_usb_homes_logs_and_lock(self):
        store, api = self.api()
        api.preflight()
        paths = {call.args[0] for call in store.checked.call_args_list}
        for path in ("usb/host/home/.android", "usb/commands.jsonl", "host/tmp", "runtime/host/tmp",
                     "hci-08.btsnoop", "generation-intent.json"):
            self.assertIn(Path("out") / path, paths)
        self.assertIn(ROOT / ".cache/p34-cycles/device.lock", paths)
        self.assertEqual(api.arguments()[0], "worker")


if __name__ == "__main__":
    unittest.main(verbosity=2)
