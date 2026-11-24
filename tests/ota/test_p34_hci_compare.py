"""Offline correlation checks, including contradictory and ambiguous evidence."""
import copy
import importlib.util
from pathlib import Path
import struct
import unittest

ROOT = Path(__file__).resolve().parents[2]
SPEC = importlib.util.spec_from_file_location("hci_compare", ROOT / "Tools/ota/p34_hci_compare.py")
M = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(M)


def fixture():
    writes = [M.frame(0, 0, 0, b""), M.frame(1, 0, 1, bytes(101))]
    writes += [M.frame(2, 1, seq, bytes(132)) for seq in range(2, 6)]
    writes += [M.frame(4, 1, 6, b"")]
    info = M.frame(0x80, 0, 0, bytes(50))
    begin = M.frame(0x81, 1, 1, b"\0\x01" + bytes(8))
    acks = [M.frame(0x82, 1, seq, bytes.fromhex("000000000001000000")) for seq in range(2, 6)]
    values = [info, begin, acks[0], acks[1][6:] + acks[2] + acks[3]]
    trial = dict(window=4, chunkBytes=142, endSent=False, session=1,
                 identity=dict(version=0, imageSha256="00" * 32),
                 events=[dict(kind="write", hex=v.hex()) for v in writes] +
                        [dict(kind="notify", hex=v.hex()) for v in values])
    tx = [dict(direction="tx", opcode=0x52, value_hex=v.hex(), value_handle=15,
               generation=1, start_record=10 + i * 10, end_record=10 + i * 10, att_hex="52")
          for i, v in enumerate(writes)]
    rx = [dict(direction="rx", opcode=0x1b, value_hex=v.hex(), value_handle=12,
               generation=1, start_record=n, end_record=n, att_hex="1b")
          for v, n in zip(values, (15, 25, 65, 66))]
    declaration = dict(direction="rx", opcode=9, att_hex="09070b00120c00f1ff0e000c0f00f2ff", generation=1)
    decoded = dict(result="TARGET_ATT_DECODED", capture=dict(truncated_packets=0, reported_drops=0),
                   att=[declaration] + tx + rx, notifications=rx)
    return decoded, trial, acks


class Tests(unittest.TestCase):
    def test_link_parameters_keep_event_order_and_unknown_phy(self):
        packets = [bytes.fromhex(x) for x in (
            "043e1f0a0001000001cbd614e149e300000000000000000000000024000000f40100",
            "043e0b070100fb004808fb004808", "043e0a0300010006000000f401")]
        raw = bytes(16) + b"".join(struct.pack(">IIIIQ", len(p), len(p), 3, 0, i) + p
                                 for i, p in enumerate(packets))
        events = M.link_parameters(raw, dict(start_record=1, end_record=3, handle=1))
        self.assertEqual([e["kind"] for e in events], ["connection", "data-length", "connection-update"])
        self.assertEqual(events[0]["interval_ms"], 45)
        self.assertEqual(events[1]["tx_octets"], 251)
        self.assertEqual(events[2]["interval_ms"], 7.5)
        self.assertFalse(any(e["kind"] == "phy-update" for e in events))

    def test_matching_corruption_is_already_in_hci(self):
        hci, browser, _ = fixture()
        value = M.compare(hci, browser)
        self.assertEqual(value["result"], "CORRUPTION_ALREADY_PRESENT_AT_HCI")
        self.assertTrue(value["notifications_byte_identical"])
        self.assertEqual(value["missing_ack3_prefix_hex"], "a55a82010300")
        self.assertEqual((value["expected_bytes"], value["hci_bytes"]), (156, 150))

    def test_complete_hci_points_to_later_boundary(self):
        hci, browser, acks = fixture()
        hci["notifications"][-1]["value_hex"] = b"".join(acks[1:]).hex()
        self.assertEqual(M.compare(hci, browser)["result"], "HCI_COMPLETE_BROWSER_DIFFERS")

    def test_equal_correct_streams_are_not_called_corrupt(self):
        hci, browser, acks = fixture()
        hci["notifications"][-1]["value_hex"] = b"".join(acks[1:]).hex()
        browser["events"][-1]["hex"] = b"".join(acks[1:]).hex()
        self.assertEqual(M.compare(hci, browser)["result"], "EXPECTED_BYTES_IN_BROWSER")

    def test_conflicting_bad_streams_are_not_overattributed(self):
        hci, browser, _ = fixture()
        hci["notifications"][-1]["value_hex"] = "ff" + hci["notifications"][-1]["value_hex"]
        self.assertEqual(M.compare(hci, browser)["result"], "HCI_BROWSER_DIFFER_BOTH_UNEXPECTED")

    def test_duplicate_run_or_mixed_generation_rejected(self):
        hci, browser, _ = fixture()
        changed = copy.deepcopy(hci); changed["att"] += copy.deepcopy(hci["att"])
        with self.assertRaises(ValueError):
            M.compare(changed, browser)
        hci["att"][2]["generation"] = 2
        with self.assertRaises(ValueError):
            M.compare(hci, browser)

    def test_wrong_characteristic_and_bad_original_crc_rejected(self):
        hci, browser, _ = fixture()
        hci["att"][0]["att_hex"] = "09070b00120c00f3ff0e000c0f00f2ff"
        with self.assertRaises(ValueError):
            M.compare(hci, browser)
        hci, browser, _ = fixture()
        browser["events"][2]["hex"] = browser["events"][2]["hex"][:-2] + "ff"
        with self.assertRaises(ValueError):
            M.compare(hci, browser)


if __name__ == "__main__":
    unittest.main(verbosity=2)
