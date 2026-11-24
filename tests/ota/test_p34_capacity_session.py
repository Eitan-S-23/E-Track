"""Host validation for the isolated diagnostic protocol and input gates."""
import importlib.util
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[2]
SPEC = importlib.util.spec_from_file_location("capacity_session", ROOT / "Tools/ota/p34_capacity_session.py")
M = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(M)


def good():
    return dict(kind="repeated-payload-link-capacity", durableThroughput=False, chunkBytes=244,
                window=31, endSent=False, result="ACKED_LINK_SAMPLE", abortConfirmed=True,
                writeUncertain=False, sentFrames=5000, elapsedMs=10000, repeatedPayloadBytes=640000,
                uniquePayloadBytes=128, linkPayloadKiBps=62.5)


class Tests(unittest.TestCase):
    def test_unplanned_chunks_rejected_before_device_access(self):
        for chunks in ((), (244,), (142, 142), (142, 244, 142)):
            with self.subTest(chunks=chunks), self.assertRaises(RuntimeError):
                M.worker(chunks=chunks)

    def test_unplanned_baud_rejected_before_context_or_device_access(self):
        for baud in (115200, 1000000, True):
            with self.subTest(baud=baud), self.assertRaises(RuntimeError):
                M.worker(baud=baud)

    def test_sustained_result_is_not_ota_progress(self):
        M.result_matches(good(), 244)

    def test_smaller_window_is_a_separate_bound_input(self):
        value = good(); value["window"] = 4
        M.result_matches(value, 244, 4)
        with self.assertRaises(RuntimeError):
            M.result_matches(value, 244, 31)

    def test_noncommitted_abort_retains_ram_bitmap_but_not_durable(self):
        value = dict(session=dict(state=0, isr_active=0, durable_off=0, segment_bitmap=1,
                                  last_ack_cmd=0x84, last_ack_seq=33), bcb_state=4, confirm_done=1, sd_ready=1)
        M.noncommitted_terminal(value, 31)
        for key, wrong in (("state", 1), ("segment_bitmap", 0), ("durable_off", 4096), ("last_ack_seq", 32)):
            changed = dict(value, session=dict(value["session"]))
            changed["session"][key] = wrong
            with self.subTest(key=key), self.assertRaises(RuntimeError):
                M.noncommitted_terminal(changed, 31)

    def test_false_capacity_evidence_is_rejected(self):
        for key, value in (("durableThroughput", True), ("endSent", True), ("abortConfirmed", False),
                           ("writeUncertain", True), ("elapsedMs", 9999), ("elapsedMs", 20001),
                           ("elapsedMs", float("nan")), ("sentFrames", 0), ("sentFrames", True),
                           ("sentFrames", 16001), ("repeatedPayloadBytes", 640001),
                           ("linkPayloadKiBps", 100), ("linkPayloadKiBps", float("nan")),
                           ("uniquePayloadBytes", 640000), ("window", 32), ("chunkBytes", 142)):
            value_dict = good(); value_dict[key] = value
            with self.subTest(key=key, value=value), self.assertRaises(RuntimeError):
                M.result_matches(value_dict, 244)

    def test_info_binds_model_version_hash_and_capacity(self):
        expected = dict(version=30230, imageSha256="12" * 32)
        actual = dict(expected, modelHex="452d547261636b00", hardware=1, layout=1, protocol=1, maxWindow=32)
        M.identity_matches(actual, expected)
        for key, value in (("version", 30229), ("imageSha256", "34" * 32), ("modelHex", "00" * 8),
                           ("hardware", 2), ("maxWindow", 8)):
            wrong = dict(actual); wrong[key] = value
            with self.subTest(key=key), self.assertRaises(RuntimeError):
                M.identity_matches(wrong, expected)

    def test_browser_uses_local_origin_bound_token_and_no_end(self):
        html = (ROOT / "Tools/ota/p34_capacity_control.html").read_text()
        self.assertIn('"X-Capacity-Token":cfg.token', html)
        self.assertIn('for (const chunkBytes of cfg.chunks)', html)
        self.assertIn('generation === epoch', html)
        self.assertNotIn('frame(3,', html)


if __name__ == "__main__":
    unittest.main(verbosity=2)
