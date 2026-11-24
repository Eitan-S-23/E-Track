"""Window-31 follow-up requires a clean, closed non-installing predecessor."""
import importlib.util
from pathlib import Path
from types import SimpleNamespace
import unittest

ROOT = Path(__file__).resolve().parents[2]
SPEC = importlib.util.spec_from_file_location("gap_burst", ROOT / "Tools/ota/p34_gap_burst.py")
M = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(M)


class Tests(unittest.TestCase):
    def values(self):
        result = dict(result="CAPACITY_SCREEN_VERIFIED", no_end=True, no_install=True,
                      trials=[dict(window=4, frames=252, native=dict(clean_counters=True))])
        native = dict(retained_verified=True, reader_closed=True,
                      final_identity=dict(app=dict(sha256=M.gap.IMAGE_SHA), boot=dict(sha256=M.gap.BOOT_SHA)),
                      final_state=dict(retained_word=0x5034f708, bcb_state=4, confirm_done=1, sd_ready=1,
                          session=dict(state=0, isr_active=0, durable_off=0, segment_bitmap=1,
                                       last_ack_cmd=0x84, last_ack_seq=254)))
        return result, native, dict(forced_termination=False, worker_exit=0), dict(
            port_closed=True, stop_exit=0, server_exit=0, launcher_exit=0)

    def test_clean_closed_prerequisite(self):
        M.verify_screen(*self.values())

    def test_failed_or_durable_predecessor_rejected(self):
        values = self.values()
        values[0]["result"] = "CAPACITY_INCOMPLETE"
        with self.assertRaises(RuntimeError):
            M.verify_screen(*values)
        values = self.values()
        values[1]["final_state"]["session"]["durable_off"] = 4096
        with self.assertRaises(RuntimeError):
            M.verify_screen(*values)

    def test_unclosed_usb_or_forced_worker_rejected(self):
        for index, key in ((2, "forced_termination"), (3, "port_closed")):
            values = self.values()
            values[index][key] = not values[index][key]
            with self.assertRaises(RuntimeError):
                M.verify_screen(*values)

    def test_exact_pair_without_rate_change(self):
        calls = []
        api = SimpleNamespace(worker=lambda **kw: calls.append(kw) or 0)
        self.assertEqual(M.run_worker(api), 0)
        self.assertEqual((api.SESSION, api.WINDOW), ("session-w31", 31))
        self.assertEqual(calls, [dict(baud=921600, chunks=(142, 244))])


if __name__ == "__main__":
    unittest.main(verbosity=2)
