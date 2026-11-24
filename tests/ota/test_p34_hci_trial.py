"""An empty connection is not license to drop a partial or malformed ATT stream."""
import io
import json
from pathlib import Path
import sys
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "Tools/ota"))
import p34_hci_trial as f


class Tests(unittest.TestCase):
    def test_only_empty_metadata_is_removed(self):
        raw = b"original"
        decoded = dict(connections=[dict(generation=1), dict(generation=2)],
                       att=[dict(generation=2)], capture=dict(packets=123), notifications=[])
        before = json.dumps(decoded)
        def run(data, package, expected):
            value = att.analyze(data, expected["deviceAddress"])
            self.assertEqual(value["connections"], [dict(generation=2)])
            self.assertEqual(value["att"], decoded["att"])
            self.assertEqual(value["capture"], decoded["capture"])
            return dict(result="fixture")
        with patch.object(f.previous.att, "analyze", return_value=decoded), patch.object(f.previous, "analyze", run):
            result = f.analyze(raw, b"package", dict(deviceAddress="peer"))
        self.assertEqual(result["att_empty_connections"], [dict(generation=1)])
        self.assertEqual(json.dumps(decoded), before)

    def test_nonempty_bad_declarations_are_not_filtered(self):
        decoded = dict(connections=[dict(generation=1)], att=[dict(generation=1)])
        def run(data, package, expected):
            selected = att.analyze(data, expected["deviceAddress"])
            self.assertEqual(selected["connections"], decoded["connections"])
            self.assertEqual(selected["att"], decoded["att"])
            raise ValueError("FFF declarations required")
        with patch.object(f.previous.att, "analyze", return_value=decoded), patch.object(f.previous, "analyze", run), \
                self.assertRaisesRegex(ValueError, "FFF declarations required"):
            f.analyze(b"original", b"package", dict(deviceAddress="peer"))

    def test_current_original_complete_capture(self):
        area = ROOT / ".cache/p34-half-erase"
        pointer = json.loads((area / "trials/measure/analysis/latest.json").read_text())["report"]
        report = json.loads(Path(pointer["path"]).read_text())
        package = Path(report["inputs"]["download"]["path"]).read_bytes()
        result = f.analyze((area / "hci-export-001/hci-01.btsnoop").read_bytes(), package, report["summary"]["input"])
        self.assertEqual(result["result"], "ORIGINAL_OTA_HCI_CORRELATED")
        self.assertEqual((result["data_frames"], result["ack_frames"], result["data_att_chunks"]), (2293, 2293, 1378))
        self.assertEqual(len(result["att_empty_connections"]), 1)
        self.assertEqual(result["att_empty_connections"][0]["generation"], 1)


if __name__ == "__main__":
    f.cli.require(Path.cwd() == ROOT and sys.flags.isolated and sys.flags.no_site and sys.dont_write_bytecode,
                  "explicit isolated root required")
    s = f.cli.Store(ROOT); out = s.checked(Path(sys.argv[1])); f.cli.require(not out.exists(), "preserve tests")
    for name in ("tests.log", "result.json"): s.checked(out / name)
    stream = io.StringIO()
    result = unittest.TextTestRunner(stream=stream, verbosity=2).run(unittest.defaultTestLoader.loadTestsFromTestCase(Tests))
    s.raw(out / "tests.log", stream.getvalue().encode())
    s.write(out / "result.json", dict(passed=result.wasSuccessful(), count=result.testsRun,
        source=f.cli.record(f.__file__), test=f.cli.record(__file__), device_operations=0))
    print(stream.getvalue()); sys.exit(not result.wasSuccessful())
