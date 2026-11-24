"""Queue accounting cannot confuse reporting latency with isolated radio costs."""
import io
import json
from pathlib import Path
import sys
import unittest
from unittest.mock import Mock, patch

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "Tools/ota"))
import p34_hci_queue as f


def packet(record, stamp):
    return dict(start_record=record, end_record=record, start_timestamp=stamp, end_timestamp=stamp)


class Tests(unittest.TestCase):
    def test_relative_record_paths_still_require_digest_and_length(self):
        store = Mock()
        absolute = ROOT / "original.bin"
        store.checked.return_value = absolute
        actual = dict(path=str(absolute), bytes=3, sha256="digest")
        relative = dict(actual, path="original.bin")
        with patch.object(f.cli, "record", return_value=actual):
            self.assertEqual(f.verify_record(store, relative), absolute)
            for bad in (dict(relative, bytes=4), dict(relative, sha256="changed")):
                with self.assertRaises(RuntimeError): f.verify_record(store, bad)

    def test_empty_and_nonempty_partition(self):
        events = f.queue_events([packet(1, 10), packet(3, 30)],
            {1: dict(record=2, timestamp=20), 3: dict(record=4, timestamp=40)})
        value = f.span(events, 10, 30)
        self.assertEqual(value["no_reported_outstanding_data_us"], 10)
        self.assertEqual(value["reported_outstanding_data_us"], 10)
        self.assertEqual(value["peak_reported_outstanding_data"], 1)

    def test_completion_reports_can_batch(self):
        events = f.queue_events([packet(1, 10), packet(2, 20)],
            {1: dict(record=3, timestamp=30), 2: dict(record=3, timestamp=30)})
        self.assertEqual(f.span(events, 10, 40)["no_reported_outstanding_data_us"], 10)
        self.assertEqual(f.span(events, 10, 40)["peak_reported_outstanding_data"], 2)

    def test_outside_range_not_added_and_zero_width(self):
        events = [(1, 5, 1), (2, 20, -1)]
        self.assertEqual(f.span(events, 10, 15)["reported_outstanding_data_us"], 5)
        self.assertEqual(f.span(events, 10, 15)["peak_reported_outstanding_data"], 1)
        self.assertEqual(f.span(events, 15, 15)["span_us"], 0)
        with self.assertRaises(RuntimeError): f.span(events, 20, 10)

    def test_incomplete_fragmented_or_reversed_events_rejected(self):
        row = packet(1, 10)
        for writes, completed in (([], {}), ([row, row], {}), ([row], {}),
            ([dict(row, end_record=2)], {2: dict(record=3, timestamp=30)}),
            ([row], {1: dict(record=2, timestamp=9)}),
            ([row], {1: dict(record=1, timestamp=20)}),
            ([row, packet(3, 25)], {1: dict(record=2, timestamp=30), 3: dict(record=4, timestamp=40)})):
            with self.assertRaises(RuntimeError): f.queue_events(writes, completed)

    def test_original_predecessor_capture(self):
        root = ROOT / ".cache/p34-half-erase"
        correlated = json.loads((root / "hci-correlation-002/result.json").read_bytes())
        raw = (root / "hci-export-001/hci-01.btsnoop").read_bytes()
        result = f.analyze(raw, correlated, "02:00:00:00:00:01")
        self.assertEqual(result["data_att_chunks"], 1378)
        self.assertEqual(len(result["blocks"]), 72)
        total = result["totals"]
        self.assertEqual(total["span_us"], total["no_reported_outstanding_data_us"] + total["reported_outstanding_data_us"])


if __name__ == "__main__":
    f.cli.require(Path.cwd() == ROOT and sys.flags.isolated and sys.flags.no_site and sys.dont_write_bytecode,
                  "explicit isolated root required")
    s = f.cli.Store(ROOT)
    out = s.checked(Path(sys.argv[1]))
    f.cli.require(not out.exists(), "preserve tests")
    for name in ("tests.log", "result.json"): s.checked(out / name)
    stream = io.StringIO()
    result = unittest.TextTestRunner(stream=stream, verbosity=2).run(unittest.defaultTestLoader.loadTestsFromTestCase(Tests))
    s.raw(out / "tests.log", stream.getvalue().encode())
    s.write(out / "result.json", dict(passed=result.wasSuccessful(), count=result.testsRun,
        source=f.cli.record(f.__file__), test=f.cli.record(__file__), device_operations=0))
    print(stream.getvalue())
    sys.exit(not result.wasSuccessful())
