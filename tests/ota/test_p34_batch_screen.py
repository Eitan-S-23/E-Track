"""Batch screen rejects stale receivers and cross-output context reuse."""
import copy
import importlib.util
from pathlib import Path
from types import SimpleNamespace
import unittest
from unittest import mock

ROOT = Path(__file__).resolve().parents[2]
SPEC = importlib.util.spec_from_file_location("batch_screen", ROOT / "Tools/ota/p34_batch_screen.py")
M = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(M)


class Tests(unittest.TestCase):
    def values(self):
        report = dict(result="FULL_INSTALL_VERIFIED", summary=dict(input=dict(
            targetVersionCode=30235, targetImageSha256=M.IMAGE_SHA)))
        closure = dict(retained_verified=True, reader_closed=True,
            final_identity=dict(app=dict(sha256=M.IMAGE_SHA), boot=dict(sha256=M.BOOT_SHA)),
            final_state=dict(bcb_state=4, confirm_done=1, sd_ready=1, retained_word=0x5034f708,
                             session=dict(state=0, isr_active=0)))
        owner = dict(state="CLOSED", receipt=dict(forced_termination=False, worker_exit=0))
        return report, closure, dict(result="FULL_INSTALL_VERIFIED", worker=copy.deepcopy(owner), network=copy.deepcopy(owner))

    def test_confirmed_batch_is_admitted(self):
        M.verify_prior(*self.values())

    def test_gap_receiver_or_wrong_image_rejected(self):
        for key, bad in (("targetVersionCode", 30232), ("targetImageSha256", "00" * 32)):
            values = self.values(); values[0]["summary"]["input"][key] = bad
            with self.subTest(key=key), self.assertRaises(RuntimeError):
                M.verify_prior(*values)
        values = self.values(); values[1]["final_identity"]["boot"]["sha256"] = "00" * 32
        with self.assertRaises(RuntimeError):
            M.verify_prior(*values)

    def test_unconfirmed_or_wrong_rate_rejected(self):
        for key, bad in (("bcb_state", 3), ("confirm_done", 0), ("sd_ready", 0), ("retained_word", 0)):
            values = self.values(); values[1]["final_state"][key] = bad
            with self.subTest(key=key), self.assertRaises(RuntimeError):
                M.verify_prior(*values)

    def test_active_owner_rejected(self):
        for name in ("worker", "network"):
            values = self.values(); values[2][name]["state"] = "LIVE"
            with self.assertRaises(RuntimeError):
                M.verify_prior(*values)

    def test_context_reuses_only_identical_output_in_one_process(self):
        out = ROOT / ".cache/test-only"
        value = (None, None, None, SimpleNamespace(OUT=out))
        with mock.patch.object(M, "_context", None), mock.patch.object(M, "build_context", return_value=value) as build:
            self.assertIs(M.context(out), value)
            self.assertIs(M.context(out), value)
            build.assert_called_once_with(out)
            with self.assertRaises(RuntimeError):
                M.context(out / "other")

    def test_forward_only_noninstalling_pair_configuration(self):
        M.configure()
        self.assertEqual((M.capacity.WINDOW, M.capacity.TARGET_VERSION), (31, 30237))
        self.assertEqual(M.capacity.AREA, M.AREA)
        self.assertIs(M.capacity.context, M.context)


if __name__ == "__main__":
    unittest.main(verbosity=2)
