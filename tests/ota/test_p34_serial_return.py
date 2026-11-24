"""Pure gates for the serial ACK discriminator."""
import importlib.util
from pathlib import Path
import types
import unittest

ROOT = Path(__file__).resolve().parents[2]
SPEC = importlib.util.spec_from_file_location("serial_return", ROOT / "Tools/ota/p34_serial_return.py")
M = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(M)


class Tests(unittest.TestCase):
    def test_single_cell_without_rate_change(self):
        calls = []
        api = types.SimpleNamespace(worker=lambda **kw: calls.append(kw) or 0)
        self.assertEqual(M.run_worker(api), 0)
        self.assertEqual(api.WINDOW, 1)
        self.assertEqual(calls, [dict(baud=921600, chunks=(142,))])

    def test_restored_state_and_all_owners_required(self):
        native = dict(retained_verified=True, reader_closed=True,
                      final_state=dict(retained_word=0x5034f708))
        owner = dict(forced_termination=False, worker_exit=1)
        usb = dict(port_closed=True, stop_exit=0, server_exit=0, launcher_exit=0)
        restored = dict(baud=921600, commands=[dict(after=dict(known=921600))])
        M.verify_closure(native, owner, usb, restored)
        for altered in (dict(native, reader_closed=False), dict(native, cleanup_error="unknown"),
                        dict(native, final_state=dict(retained_word=0x5034f807))):
            with self.assertRaises(RuntimeError):
                M.verify_closure(altered, owner, usb, restored)
        with self.assertRaises(RuntimeError):
            M.verify_closure(native, dict(owner, forced_termination=True), usb, restored)
        with self.assertRaises(RuntimeError):
            M.verify_closure(native, owner, dict(usb, port_closed=False), restored)


if __name__ == "__main__":
    unittest.main(verbosity=2)
