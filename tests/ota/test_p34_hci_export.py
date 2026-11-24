"""In-memory export/parser checks; no phone, archive extraction or temp files."""
import importlib.util
from contextlib import redirect_stdout
import io
from pathlib import Path
import struct
import unittest
from unittest.mock import patch
import warnings
import zipfile

ROOT = Path(__file__).resolve().parents[2]
SPEC = importlib.util.spec_from_file_location("hci_export", ROOT / "Tools/ota/p34_hci_export.py")
M = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(M)


def snoop(packet=b"\x04\x0e\x00", *, original=None, drops=0, flags=3):
    return (b"btsnoop\0" + struct.pack(">II", 1, 1002) +
            struct.pack(">IIIIQ", original or len(packet), len(packet), flags, drops, 123456) + packet)


def archive(items):
    output = io.BytesIO()
    with zipfile.ZipFile(output, "w", zipfile.ZIP_DEFLATED) as z:
        with warnings.catch_warnings():
            warnings.simplefilter("ignore", UserWarning)
            for name, data in items:
                item = zipfile.ZipInfo(name)
                # Windows ZipInfo normalizes backslashes; preserve the hostile raw name.
                item.filename = name
                z.writestr(item, data)
    return output.getvalue()


class Tests(unittest.TestCase):
    def test_report_number_bound_precedes_device_access(self):
        for number in (0, 3, True):
            with self.subTest(number=number), self.assertRaises(ValueError):
                M.collect(None, None, None, number=number)

    def test_alias_is_canonicalized(self):
        self.assertEqual(M.report_path("/bugreports/bugreport-test.zip"), M.REMOTE + "/bugreport-test.zip")

    def test_external_nested_and_shell_paths_rejected(self):
        for path in ("/data/bugreports/a.zip", M.REMOTE + "-other/a.zip",
                     "/bugreports/../a.zip", "/bugreports/sub/a.zip", "/bugreports/a;id.zip"):
            with self.subTest(path=path), self.assertRaises(ValueError):
                M.report_path(path)

    def test_progress_binds_same_report(self):
        self.assertEqual(M.completed_report(b"BEGIN:/bugreports/a.zip\r\nPROGRESS:1/9\r\nOK:/bugreports/a.zip\r\n"),
                         M.REMOTE + "/a.zip")

    def test_failed_partial_or_ambiguous_report_rejected(self):
        for raw in (b"FAIL:denied\n", b"BEGIN:/bugreports/a.zip\n", b"OK:/bugreports/a.zip\nOK:/bugreports/a.zip\n",
                    b"BEGIN:/bugreports/b.zip\nOK:/bugreports/a.zip\n", b"junk\nOK:/bugreports/a.zip\n"):
            with self.subTest(raw=raw), self.assertRaises(ValueError):
                M.completed_report(raw)

    def test_late_progress_does_not_erase_unique_completion(self):
        raw = b"BEGIN:/bugreports/a.zip\nPROGRESS:8995/11521\nOK:/bugreports/a.zip\nPROGRESS:9103/11521\n"
        self.assertEqual(M.completed_report(raw), M.REMOTE + "/a.zip")

    def test_only_progress_is_admitted_after_completion(self):
        for tail in (b"FAIL:denied\n", b"junk\n", b"BEGIN:/bugreports/a.zip\n",
                     b"OK:/bugreports/a.zip\n", b"PROGRESS:invalid\n"):
            with self.subTest(tail=tail), self.assertRaises(ValueError):
                M.completed_report(b"OK:/bugreports/a.zip\n" + tail)

    def test_original_packet_summary_not_target_or_speed(self):
        summary = M.snoop_summary(snoop())
        self.assertEqual(summary["packets"], 1)
        self.assertEqual(summary["packet_types"], {4: 1})
        self.assertEqual(summary["target_connection"], "NOT_ANALYZED")
        self.assertEqual(summary["throughput"], "NOT_MEASURED")

    def test_incomplete_file_and_wrong_header_rejected(self):
        for raw in (snoop()[:-1], snoop()[:16], b"bad" + snoop()[3:], snoop() + b"x"):
            with self.subTest(raw=raw), self.assertRaises(ValueError):
                M.snoop_summary(raw)

    def test_filtered_records_and_drop_counters_not_hidden(self):
        summary = M.snoop_summary(snoop(original=7, drops=2))
        self.assertEqual(summary["truncated_packets"], 1)
        self.assertEqual(summary["reported_drops"], 2)

    def test_packet_lengths_and_flags_checked(self):
        for raw in (snoop(b"\x04\x0e\x03"), snoop(b"\x02\x01\x20\x08\x00"),
                    snoop(b"\x01\x00\x00\x01"), snoop(flags=4), snoop(b"\xff")):
            with self.subTest(raw=raw), self.assertRaises(ValueError):
                M.snoop_summary(raw)

    def test_acl_and_command_are_supported(self):
        for packet in (b"\x02\x01\x20\x00\x00", b"\x01\x01\x00\x00"):
            self.assertEqual(M.snoop_summary(snoop(packet))["packets"], 1)

    def test_only_bluetooth_packet_members_are_extracted(self):
        blob = archive([("report.txt", b"unrelated private diagnostic"),
                        ("FS/data/misc/bluetooth/logs/btsnoop_hci.log", snoop())])
        members, names = M.hci_members(blob)
        self.assertEqual(len(members), 1)
        self.assertEqual(members[0][1], snoop())
        self.assertEqual(len(names), 1)

    def test_no_packet_file_is_not_an_export(self):
        self.assertEqual(M.hci_members(archive([("report.txt", b"text only")]))[0], [])

    def test_zip_traversal_and_duplicates_rejected(self):
        for items in ([("../btsnoop_hci.log", snoop())], [("/btsnoop_hci.log", snoop())],
                      [("a\\btsnoop_hci.log", snoop())], [("a", b"1"), ("a", b"2")]):
            with self.subTest(items=items), self.assertRaises(ValueError):
                M.hci_members(archive(items))

    def test_too_many_snoop_members_rejected(self):
        with self.assertRaises(ValueError):
            M.hci_members(archive([("%d/btsnoop_hci.log" % i, snoop()) for i in range(9)]))

    def test_fake_named_log_is_not_packet_evidence(self):
        members, _ = M.hci_members(archive([("btsnoop_hci.log", b"logging enabled, no packets")]))
        self.assertEqual(members[0][2]["format"], "UNVERIFIED")
        self.assertIsNone(members[0][2].get("packets"))

    def test_vendor_cfa_name_is_not_assumed_to_be_a_different_format(self):
        name = "FS/data/misc/bluetooth/logs/bt_hci_20260930_010605_d.cfa"
        members, _ = M.hci_members(archive([(name, snoop())]))
        self.assertEqual(members[0][0], name)
        self.assertEqual(members[0][1], snoop())
        self.assertEqual(members[0][2]["packets"], 1)

    def test_unknown_vendor_format_is_preserved_but_not_verified(self):
        name = "FS/data/misc/bluetooth/logs/bt_hci_20260930_010605_d.cfa"
        members, _ = M.hci_members(archive([(name, b"unknown vendor container")]))
        self.assertEqual(members[0][2]["format"], "UNVERIFIED")
        self.assertIsNone(members[0][2].get("reported_drops"))

    def test_preflight_failure_never_generates_report(self):
        calls = []
        class Phone:
            def command(self, *args, **kwargs):
                calls.append(args)
        with patch.object(M, "remote_preflight", side_effect=ValueError("outside boundary")):
            with self.assertRaisesRegex(ValueError, "outside boundary"):
                M.collect(None, Phone(), Path("unused"))
        self.assertEqual(calls, [])

    def test_uncertain_generation_keeps_intent_without_retry(self):
        saved, calls = {}, []
        class Context:
            def save(self, path, value):
                saved[path.name] = value
        class Phone:
            def command(self, args, **kwargs):
                calls.append(args)
                raise TimeoutError("original uncertain generation")
        with patch.object(M, "remote_preflight", return_value=[]), redirect_stdout(io.StringIO()):
            with self.assertRaisesRegex(TimeoutError, "original uncertain generation"):
                M.collect(Context(), Phone(), Path("unused"))
        self.assertEqual(calls, [["shell", "bugreportz", "-p"]])
        self.assertIn("generation-intent.json", saved)
        self.assertNotIn("generated.json", saved)


if __name__ == "__main__":
    unittest.main(verbosity=2)
