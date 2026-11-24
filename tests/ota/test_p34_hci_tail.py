"""Pure tail-classification tests; no historical device fixtures required."""
import io
from pathlib import Path
import sys
import unittest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "Tools/ota"))
import p34_hci_tail as f


def block(index, length=4096, tail=10, completion=4):
    return dict(block=index, durable=index*4096+length, tail_ms=tail,
                controller_report_ms=completion, after_controller_report_ms=tail-completion)


class Tests(unittest.TestCase):
    def test_boundary_and_partial_classification(self):
        rows = [block(i) for i in range(16)] + [block(16, 128)]
        groups = f.summarize(rows)["groups"]
        self.assertEqual(groups["boundary_64k"]["count"], 1)
        self.assertEqual(groups["ordinary_full"]["count"], 15)
        self.assertEqual(groups["partial_final"]["count"], 1)
        self.assertEqual(sum(g["totals_ms"]["tail_ms"] for g in groups.values()), 170)

    def test_signed_reporting_lag_preserved(self):
        value = f.summarize([block(0, tail=3, completion=8)])
        group = value["groups"]["ordinary_full"]
        self.assertEqual(group["negative_after_report_count"], 1)
        self.assertEqual(group["totals_ms"]["after_controller_report_ms"], -5)

    def test_median_and_empty_group(self):
        value = f.summarize([block(0, tail=3), block(1, tail=9)])
        self.assertEqual(value["groups"]["ordinary_full"]["median_tail_ms"], 6)
        self.assertIsNone(value["groups"]["boundary_64k"]["median_tail_ms"])

    def test_invalid_layout_rejected(self):
        for rows in ([], [block(1)], [block(0), block(0)],
                     [block(0, 128), block(1)], [block(0, 4097)],
                     [dict(block(0), durable=True)]):
            with self.subTest(rows=rows), self.assertRaises(RuntimeError):
                f.summarize(rows)

    def test_invalid_timing_rejected(self):
        for value in (float("nan"), float("inf"), "10", True):
            with self.subTest(value=value), self.assertRaises(RuntimeError):
                f.summarize([dict(block(0), tail_ms=value)])
        for row in (block(0, tail=-1), block(0, completion=-1),
                    dict(block(0), after_controller_report_ms=7)):
            with self.assertRaises(RuntimeError): f.summarize([row])


if __name__ == "__main__":
    f.cli.require(Path.cwd() == ROOT and sys.flags.isolated and sys.flags.no_site and
                  sys.dont_write_bytecode, "explicit isolated root required")
    store = f.cli.Store(ROOT)
    out = store.checked(Path(sys.argv[1]))
    f.cli.require(not out.exists(), "preserve prior tests")
    for name in ("tests.log", "result.json"): store.checked(out / name)
    stream = io.StringIO()
    result = unittest.TextTestRunner(stream=stream, verbosity=2).run(
        unittest.defaultTestLoader.loadTestsFromTestCase(Tests))
    store.raw(out / "tests.log", stream.getvalue().encode())
    store.write(out / "result.json", dict(passed=result.wasSuccessful(), count=result.testsRun,
        source=f.cli.record(f.__file__), test=f.cli.record(__file__), device_operations=0))
    print(stream.getvalue())
    sys.exit(not result.wasSuccessful())
