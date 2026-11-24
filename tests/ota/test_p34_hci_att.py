"""Synthetic HCI framing tests; no device or temporary files."""
import importlib.util
from pathlib import Path
import struct
import unittest

ROOT = Path(__file__).resolve().parents[2]
SPEC = importlib.util.spec_from_file_location("hci_att", ROOT / "Tools/ota/p34_hci_att.py")
M = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(M)
PEER = "02:00:00:00:00:01"


def connection(peer=PEER, enhanced=False):
    data = bytes((10 if enhanced else 1, 0)) + struct.pack("<HBB", 1, 0, 1)
    data += bytes.fromhex(peer.replace(":", ""))[::-1]
    data += bytes(12 if enhanced else 0) + struct.pack("<HHHB", 12, 0, 500, 0)
    return bytes((4, 0x3e, len(data))) + data


def acl(data, boundary=2):
    return b"\x02" + struct.pack("<HH", 1 | boundary << 12, len(data)) + data


def l2cap(att, cid=4):
    return struct.pack("<HH", len(att), cid) + att


def capture(*packets):
    result = b"btsnoop\0" + struct.pack(">II", 1, 1002)
    for i, item in enumerate(packets):
        packet, flags = item if isinstance(item, tuple) else (item, 3 if item[0] == 4 else 1)
        result += struct.pack(">IIIIQ", len(packet), len(packet), flags, 0, 1000 + i) + packet
    return result


class Tests(unittest.TestCase):
    def test_target_value_bytes_are_exact(self):
        result = M.analyze(capture(connection(), acl(l2cap(bytes.fromhex("1b2500a55a82020300")))), PEER)
        self.assertEqual(result["notifications"][0]["value_hex"], "a55a82020300")
        self.assertEqual(result["notifications"][0]["value_handle"], 0x25)
        self.assertEqual(result["throughput"], "NOT_MEASURED")

    def test_acl_fragments_are_reassembled(self):
        data = l2cap(bytes.fromhex("1b250009000000000000010000001c62"))
        result = M.analyze(capture(connection(), acl(data[:7]), acl(data[7:], 1)), PEER)
        row = result["notifications"][0]
        self.assertEqual(row["value_hex"], data[7:].hex())
        self.assertEqual((row["start_record"], row["end_record"]), (2, 3))

    def test_enhanced_connection_event_is_bound(self):
        result = M.analyze(capture(connection(enhanced=True)), PEER)
        self.assertEqual(result["connections"][0]["peer"], PEER)

    def test_unrelated_or_unbound_handle_is_not_target_data(self):
        for packets in ((acl(l2cap(b"\x1b\x25\0private")),),
                        (connection("11:22:33:44:55:66"), acl(l2cap(b"\x1b\x25\0private")))):
            result = M.analyze(capture(*packets), PEER)
            self.assertEqual(result["notifications"], [])
            self.assertEqual(result["result"], "TARGET_CONNECTION_NOT_OBSERVED")

    def test_handle_reuse_gets_a_new_generation(self):
        disconnected = bytes.fromhex("04050400010013")
        result = M.analyze(capture(connection(), disconnected, connection(), acl(l2cap(b"\x1b\x25\0x"))), PEER)
        self.assertTrue(result["connections"][0]["disconnected"])
        self.assertEqual(result["notifications"][0]["generation"], 2)

    def test_duplicate_connection_without_disconnect_is_rejected(self):
        with self.assertRaises(ValueError):
            M.analyze(capture(connection(), connection()), PEER)

    def test_direction_is_not_inferred_from_att_opcode(self):
        result = M.analyze(capture(connection(), (acl(l2cap(b"\x52\x28\0data")), 0)), PEER)
        self.assertEqual(result["notifications"], [])
        self.assertEqual(result["att"][0]["direction"], "tx")

    def test_other_l2cap_channels_are_not_att(self):
        result = M.analyze(capture(connection(), acl(l2cap(b"hello", 5))), PEER)
        self.assertEqual(result["att"], [])

    def test_fragment_loss_and_overflow_fail_closed(self):
        for packets in ((acl(b"abc", 1),), (acl(struct.pack("<HH", 9, 4) + b"x"),),
                        (acl(struct.pack("<HH", 1, 4) + b"xx"),),
                        (acl(struct.pack("<HH", 9, 4)), acl(l2cap(b"x")))):
            with self.subTest(packets=packets), self.assertRaises(ValueError):
                M.analyze(capture(connection(), *packets), PEER)

    def test_partial_frame_at_disconnect_is_not_clean_capture(self):
        with self.assertRaises(ValueError):
            M.analyze(capture(connection(), acl(struct.pack("<HH", 9, 4)), bytes.fromhex("04050400010013")), PEER)

    def test_short_att_value_and_invalid_address_rejected(self):
        with self.assertRaises(ValueError):
            M.analyze(capture(connection(), acl(l2cap(b"\x1b\x25"))), PEER)
        with self.assertRaises(ValueError):
            M.analyze(capture(connection()), "E3:49")


if __name__ == "__main__":
    unittest.main(verbosity=2)
