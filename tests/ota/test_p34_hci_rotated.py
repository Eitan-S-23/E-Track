"""Rotation joining preserves source bytes and validates the full OTA prefix."""
import io
import json
from pathlib import Path
import struct
import sys
import unittest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "Tools/ota"))
import p34_hci_rotated as f


def capture(stamp, drops=0):
    packet = b"\x04\x0e\0"
    return b"btsnoop\0" + struct.pack(">II", 1, 1002) + struct.pack(">IIIIQ", 3, 3, 3, drops, stamp) + packet


class Tests(unittest.TestCase):
    def test_join_orders_parts_not_packets(self):
        first, second = capture(10), capture(20)
        self.assertEqual(f.join([second, first]), first + second[16:])
        self.assertEqual(f.join([first]), first)

    def test_invalid_rotations_fail_closed(self):
        for parts in ([], [capture(1)] * 2, [capture(10, 1)], [capture(1)[:-1]],
                      [capture(1) + capture(3)[16:], capture(2)],
                      [capture(2) + capture(1)[16:]]):
            with self.assertRaises((RuntimeError, ValueError)): f.join(parts)

    def test_real_rotated_trial_and_later_identity_queries(self):
        r = ROOT / ".cache/p34-phy-logfix"
        originals = [r / "hci-export-001" / name for name in ("hci-01.btsnoop", "hci-02.btsnoop")]
        parts = [p.read_bytes() for p in originals]
        raw = f.join(parts)
        self.assertEqual(raw, parts[1] + parts[0][16:])
        pointer = json.loads((r / "trials/prefer2m/analysis/latest.json").read_bytes())["report"]
        report = json.loads(Path(pointer["path"]).read_bytes())
        package = Path(report["inputs"]["download"]["path"]).read_bytes()
        value, prefix = f.analyze(raw, package, report["summary"]["input"])
        self.assertEqual((value["data_frames"], value["ack_frames"]), (2293, 2293))
        self.assertTrue(value["later_target_queries"])
        self.assertEqual(prefix, raw[:len(prefix)])
        self.assertLess(len(prefix), len(raw))
        with self.assertRaises((RuntimeError, ValueError)):
            f.analyze(raw, package[:-1] + bytes([package[-1] ^ 1]), report["summary"]["input"])

    def test_real_two_upgrades_selects_complete_matching_connection(self):
        r = ROOT / ".cache/p34-info-timeout"
        archive = json.loads((r / "hci-export-001/archive.json").read_bytes())
        raw = f.join([Path(x["original"]["path"]).read_bytes() for x in archive["extracted"]])
        pointer = json.loads((r / "trial/analysis/latest.json").read_bytes())["report"]
        report = json.loads(Path(pointer["path"]).read_bytes())
        package = Path(report["inputs"]["download"]["path"]).read_bytes()
        value, selected = f.analyze(raw, package, report["summary"]["input"])
        window = value["analysis_range"]
        self.assertGreater(window["first_record"], 1)
        self.assertTrue(value["earlier_unrelated_upgrades"])
        self.assertEqual(value["data_frames"], 2293)
        self.assertEqual(value["ack_frames"], 2293)
        records = f.records(raw)
        self.assertEqual(selected, raw[:16] + raw[records[window["first_record"]-2][1]:records[window["last_record"]-1][1]])
        self.assertEqual(window["derived_record_offset"], window["first_record"] - 1)
        # Keeping the earlier OTA in scope must still fail the strict verifier.
        with self.assertRaises((RuntimeError, ValueError)):
            f.trial.analyze(raw[:records[window["last_record"]-1][1]], package, report["summary"]["input"])
        with self.assertRaises((RuntimeError, ValueError)):
            f.analyze(raw, package[:-1], report["summary"]["input"])


if __name__ == "__main__":
    f.cli.require(Path.cwd() == ROOT and sys.flags.isolated and sys.flags.no_site and sys.dont_write_bytecode,
                  "explicit isolated root required")
    s = f.cli.Store(ROOT)
    out = s.checked(Path(sys.argv[1]))
    f.cli.require(not out.exists(), "preserve test output")
    for name in ("tests.log", "result.json"): s.checked(out / name)
    stream = io.StringIO()
    result = unittest.TextTestRunner(stream=stream, verbosity=2).run(unittest.defaultTestLoader.loadTestsFromTestCase(Tests))
    s.raw(out / "tests.log", stream.getvalue().encode())
    s.write(out / "result.json", dict(passed=result.wasSuccessful(), count=result.testsRun,
        source=f.cli.record(f.__file__), test=f.cli.record(__file__), device_operations=0))
    print(stream.getvalue())
    sys.exit(not result.wasSuccessful())
