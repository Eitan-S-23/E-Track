"""Host-only regression checks for the three-rate preparation helpers."""
import importlib.util
import json
from pathlib import Path
import sys
import unittest

spec = importlib.util.spec_from_file_location("baud_download_tested", Path(__file__).with_name("collect_baud_apk.py"))
c = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = c
spec.loader.exec_module(c)


class RangeTests(unittest.TestCase):
    def test_empty_download(self):
        self.assertEqual(c.missing_ranges(10, [], 4), [(0, 3), (4, 7), (8, 9)])

    def test_reuses_large_and_small_completed_parts(self):
        parts = [dict(start=0, end=3), dict(start=6, end=6), dict(start=9, end=9)]
        self.assertEqual(c.missing_ranges(10, parts, 4), [(4, 5), (7, 8)])

    def test_complete(self):
        self.assertEqual(c.missing_ranges(10, [dict(start=0, end=9)]), [])

    def test_overlapping(self):
        with self.assertRaises(RuntimeError):
            c.missing_ranges(10, [dict(start=0, end=4), dict(start=4, end=6)])

    def test_unsorted(self):
        with self.assertRaises(RuntimeError):
            c.missing_ranges(10, [dict(start=6, end=7), dict(start=0, end=2)])

    def test_bounds(self):
        for size in (0, -1, True, 300 * 1024 * 1024 + 1):
            with self.subTest(size=size), self.assertRaises(RuntimeError):
                c.missing_ranges(size, [])

    def test_invalid_chunk(self):
        for chunk in (0, -1, True, 2 * 1024 * 1024 + 1):
            with self.subTest(chunk=chunk), self.assertRaises(RuntimeError):
                c.missing_ranges(10, [], chunk)

    def test_coverage_with_many_holes(self):
        size = 91
        parts = [dict(start=10, end=19), dict(start=40, end=59), dict(start=90, end=90)]
        ranges = [(item["start"], item["end"]) for item in parts] + c.missing_ranges(size, parts, 7)
        self.assertEqual(sorted(index for first, last in ranges for index in range(first, last + 1)), list(range(size)))

    def test_content_range_is_strict(self):
        class Response:
            status = 206
            headers = {"Content-Range": "bytes 0-3/10", "Content-Length": "4"}
        response = Response()
        c.d.validate_range(response, 0, 3, 10)
        response.status = 200
        with self.assertRaises(RuntimeError):
            c.d.validate_range(response, 0, 3, 10)
        response.status = 206
        response.headers["Content-Range"] = "bytes 4-7/10"
        with self.assertRaises(RuntimeError):
            c.d.validate_range(response, 0, 3, 10)


if __name__ == "__main__":
    c.b.require(Path.cwd().resolve() == c.b.ROOT and sys.flags.isolated and sys.flags.no_site and
                sys.dont_write_bytecode, "isolated explicit project execution required")
    out = c.b.checked(c.b.OUT / "host-tests-preparation-001")
    c.b.require(not out.exists(), "preserve existing regression output")
    for name in ("result.json",):
        c.b.checked(out / name)
    result = unittest.TextTestRunner(verbosity=2).run(unittest.defaultTestLoader.loadTestsFromModule(sys.modules[__name__]))
    c.b.io.write_json(c.b.ROOT, out / "result.json", dict(passed=result.wasSuccessful(), tests=result.testsRun,
        failures=len(result.failures), errors=len(result.errors), source=c.b.record(Path(__file__)),
        tested_source=c.b.record(Path(c.__file__)), network=False, hardware=False))
    raise SystemExit(0 if result.wasSuccessful() else 1)
