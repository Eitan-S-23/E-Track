"""Pure admission/closure tests for the new HCI-backed screen."""
import copy
from contextlib import contextmanager
import importlib.util
from pathlib import Path
import types
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[2]
SPEC = importlib.util.spec_from_file_location("hci_session_tests", ROOT / "Tools/ota/p34_hci_session.py")
M = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(M)


def closure():
    return (dict(worker_exit=1, forced_termination=False),
            dict(reader_closed=True, retained_verified=True,
                 final_state=dict(bcb_state=4, confirm_done=1, sd_ready=1,
                                  session=dict(state=0, isr_active=0))),
            dict(port_closed=True, stop_exit=0, server_exit=0, launcher_exit=0),
            dict(endSent=False, events=[dict(kind="write", hex="a55a0202")]))


class Tests(unittest.TestCase):
    def runtime_phone(self, mode):
        saved = {}
        @contextmanager
        def usb(c, out):
            yield types.SimpleNamespace(command=lambda args: mode)
        context = types.SimpleNamespace(checked=lambda value: value,
            save=lambda path, value: saved.update(value), now=lambda: "test-time")
        impl = types.SimpleNamespace(phone=lambda *args: types.SimpleNamespace(usb=usb))
        capacity = types.SimpleNamespace(context=lambda out: (None, None, impl, context))
        M.configure(capacity)
        _, _, wrapped, c = capacity.context(Path("unused"))
        return wrapped.phone(c, "test"), c, saved

    def test_runtime_refuses_changed_logging_before_yielding(self):
        phone, c, saved = self.runtime_phone("disable")
        with self.assertRaises(ValueError):
            with phone.usb(c, Path("unused")):
                self.fail("must not open a probe without full logging")
        self.assertEqual(saved, {})

    def test_runtime_records_full_logging_and_no_report_overlap(self):
        phone, c, saved = self.runtime_phone("full")
        with patch.object(M, "validate_proof", return_value={"verified": True}):
            with phone.usb(c, Path("unused")):
                self.assertTrue(saved["full_logging"])
                self.assertFalse(saved["report_during_probe"])
                self.assertEqual(saved["window"], 4)

    def test_hci_screen_uses_new_name_and_unchanged_four_frame_window(self):
        capacity = types.SimpleNamespace(context=lambda out: None)
        M.configure(capacity)
        self.assertEqual(capacity.SESSION, "session-hci-w4")
        self.assertEqual(capacity.WINDOW, 4)

    def test_export_requires_actual_packets_and_closed_usb(self):
        value = dict(result="ORIGINAL_HCI_EXPORT_VERIFIED", usb_closed=True,
                     extracted=[dict(summary=dict(packets=1, truncated_packets=0, reported_drops=0))])
        M.proof_ready(value)
        for key, wrong in (("result", "VENDOR_LOG_FORMAT_UNVERIFIED"), ("usb_closed", False), ("extracted", [])):
            changed = dict(value); changed[key] = wrong
            with self.subTest(key=key), self.assertRaises(ValueError):
                M.proof_ready(changed)

    def test_failed_measurement_can_still_need_packet_evidence(self):
        M.closed_probe(*closure())

    def test_forced_or_unclosed_owner_blocks_report(self):
        for idx, key, value in ((0, "forced_termination", True), (0, "worker_exit", None),
                                (1, "reader_closed", False), (1, "retained_verified", False),
                                (2, "port_closed", False), (2, "launcher_exit", 1)):
            values = copy.deepcopy(closure()); values[idx][key] = value
            with self.subTest(key=key), self.assertRaises(ValueError):
                M.closed_probe(*values)

    def test_uncertain_mcu_state_blocks_report(self):
        values = closure(); values[1]["final_state"]["session"]["state"] = 1
        with self.assertRaises(ValueError):
            M.closed_probe(*values)

    def test_no_data_or_end_is_not_this_diagnostic(self):
        for trial in (dict(endSent=False, events=[]), dict(endSent=True, events=[dict(kind="write", hex="a55a02")])):
            values = list(closure()); values[3] = trial
            with self.assertRaises(ValueError):
                M.closed_probe(*values)


if __name__ == "__main__":
    unittest.main(verbosity=2)
