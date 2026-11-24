"""Reject stale/unconfirmed receivers before opening any device route."""
import copy
import importlib.util
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[2]
SPEC = importlib.util.spec_from_file_location("gap_screen", ROOT / "Tools/ota/p34_gap_screen.py")
M = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(M)


class Tests(unittest.TestCase):
    def values(self):
        report = dict(result="FULL_INSTALL_VERIFIED", summary=dict(input=dict(
            targetVersionCode=30232, targetImageSha256=M.IMAGE_SHA)))
        closure = dict(retained_verified=True, reader_closed=True,
            final_identity=dict(app=dict(sha256=M.IMAGE_SHA), boot=dict(sha256=M.BOOT_SHA)),
            final_state=dict(bcb_state=4, confirm_done=1, sd_ready=1, retained_word=0x5034f708,
                             session=dict(state=0, isr_active=0)))
        owner = dict(state="CLOSED", receipt=dict(forced_termination=False, worker_exit=0))
        state = dict(result="FULL_INSTALL_VERIFIED", worker=copy.deepcopy(owner), network=copy.deepcopy(owner))
        return report, closure, state

    def test_confirmed_gap_is_admitted(self):
        M.verify_prior(*self.values())

    def test_old_target_rejected(self):
        values = self.values()
        values[0]["summary"]["input"]["targetVersionCode"] = 30230
        with self.assertRaises(RuntimeError):
            M.verify_prior(*values)

    def test_full_hash_and_original_boot_required(self):
        for field in ("app", "boot"):
            values = self.values()
            values[1]["final_identity"][field]["sha256"] = "00" * 32
            with self.subTest(field=field), self.assertRaises(RuntimeError):
                M.verify_prior(*values)

    def test_unconfirmed_busy_or_wrong_rate_rejected(self):
        for key, bad in (("bcb_state", 3), ("confirm_done", 0), ("sd_ready", 0), ("retained_word", 0)):
            values = self.values()
            values[1]["final_state"][key] = bad
            with self.subTest(key=key), self.assertRaises(RuntimeError):
                M.verify_prior(*values)
        for key in ("state", "isr_active"):
            values = self.values()
            values[1]["final_state"]["session"][key] = 1
            with self.subTest(key=key), self.assertRaises(RuntimeError):
                M.verify_prior(*values)

    def test_live_or_forced_owner_rejected(self):
        for key in ("worker", "network"):
            values = self.values()
            values[2][key]["state"] = "LIVE"
            with self.assertRaises(RuntimeError):
                M.verify_prior(*values)
            values = self.values()
            values[2][key]["receipt"]["forced_termination"] = True
            with self.assertRaises(RuntimeError):
                M.verify_prior(*values)

    def test_new_context_and_legal_target_are_explicit(self):
        M.configure()
        self.assertIs(M.capacity.context, M.context)
        self.assertEqual(M.capacity.TARGET_VERSION, 30234)
        self.assertEqual(M.capacity.WINDOW, 4)
        self.assertEqual(M.capacity.AREA, M.AREA)


if __name__ == "__main__":
    unittest.main(verbosity=2)
