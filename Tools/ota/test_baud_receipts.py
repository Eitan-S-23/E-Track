"""Real-file regression for the ACK-bootstrap result publication race."""
from pathlib import Path
import argparse
import io
import json
import runpy
import sys
import threading
import time
import unittest
from unittest import mock

ROOT = Path(__file__).resolve().parents[2]
MODULE = Path(__file__).with_name("baud_receipts.py")
helper = runpy.run_path(str(MODULE))
guard = helper["IO"]["checked_output"]
OUT = None


class Clock:
    def __init__(self, publish=None):
        self.value = 0.
        self.sleeps = 0
        self.publish = publish

    def now(self):
        return self.value

    def sleep(self, seconds):
        self.value += seconds
        self.sleeps += 1
        if self.publish:
            self.publish(self.sleeps)


class ReceiptTests(unittest.TestCase):
    def path(self, name="receipt.json"):
        path = guard(ROOT, OUT / self._testMethodName / name)
        guard(ROOT, path.parent).mkdir(parents=True, exist_ok=True)
        return path

    def wait(self, path, seconds=5, clock=None):
        clock = clock or Clock()
        return helper["wait_json"](ROOT, path, seconds, clock=clock.now, sleep=clock.sleep)

    def test_actual_old_wait_reads_an_empty_published_file(self):
        old = runpy.run_path(str(ROOT / "Tools/ota/baud_runtime.py"))
        path = self.path()
        with path.open("xb"):
            with self.assertRaises(json.JSONDecodeError):
                old["wait_file"](path, .1)

    def test_real_writer_can_finish_the_same_open_file(self):
        path = self.path()
        opened = threading.Event()
        release = threading.Event()
        errors = []

        def writer():
            try:
                with path.open("xb") as stream:
                    opened.set()
                    if not release.wait(2):
                        raise TimeoutError("test writer not released")
                    stream.write(b'{"result":"PASS"}\n')
                    stream.flush()
            except Exception as error:
                errors.append(error)

        thread = threading.Thread(target=writer)
        thread.start()
        try:
            self.assertTrue(opened.wait(2))
            pauses = []

            def sleep(seconds):
                pauses.append(seconds)
                release.set()
                time.sleep(seconds)

            result = helper["wait_json"](ROOT, path, 2, sleep=sleep)
            self.assertEqual(result, {"result": "PASS"})
            self.assertTrue(pauses)
        finally:
            release.set()
            thread.join(3)
        self.assertFalse(thread.is_alive())
        self.assertEqual(errors, [])

    def test_missing_file_uses_the_original_total_deadline(self):
        clock = Clock()
        with self.assertRaises(TimeoutError):
            self.wait(self.path(), .1, clock)
        self.assertLessEqual(clock.value, .101)

    def test_late_creation_then_complete_object_is_accepted(self):
        path = self.path()
        clock = Clock(lambda n: path.write_bytes(b'{"ok":true}\n') if n == 2 else None)
        self.assertEqual(self.wait(path, clock=clock), {"ok": True})
        self.assertEqual(clock.sleeps, 2)

    def test_valid_json_without_publication_newline_is_not_ready(self):
        path = self.path()
        path.write_bytes(b'{"ok":true}')
        clock = Clock(lambda n: path.write_bytes(b'{"ok":true}\n') if n == 3 else None)
        self.assertEqual(self.wait(path, clock=clock), {"ok": True})
        self.assertEqual(clock.sleeps, 3)

    def test_persistent_bad_receipt_fails_within_two_seconds(self):
        for number, data in enumerate((b"", b"{\n", b'{"ok":true}', b"{broken}\n")):
            with self.subTest(data=data):
                path = self.path(str(number) + ".json")
                path.write_bytes(data)
                clock = Clock()
                with self.assertRaisesRegex(ValueError, "incomplete or malformed"):
                    self.wait(path, clock=clock)
                self.assertLessEqual(clock.value, 2.001)
                self.assertEqual(path.read_bytes(), data)

    def test_partial_updates_do_not_restart_the_partial_deadline(self):
        path = self.path()
        path.write_bytes(b"{")
        clock = Clock(lambda n: path.write_bytes(b'{"n":' + str(n).encode()))
        with self.assertRaises(ValueError):
            self.wait(path, clock=clock)
        self.assertLessEqual(clock.value, 2.001)

    def test_non_object_is_not_a_receipt(self):
        path = self.path()
        for data in (b"null\n", b"[]\n", b"1\n"):
            with self.subTest(data=data):
                path.write_bytes(data)
                with self.assertRaisesRegex(ValueError, "JSON object"):
                    self.wait(path)

    def test_oversized_receipt_is_rejected(self):
        path = self.path()
        path.write_bytes(b" " * (helper["MAX_BYTES"] + 1))
        with self.assertRaisesRegex(ValueError, "byte limit"):
            self.wait(path)

    def test_permission_error_is_not_a_publication_retry(self):
        path = self.path()
        clock = Clock()
        with mock.patch.object(Path, "open", side_effect=PermissionError("denied")):
            with self.assertRaises(PermissionError):
                self.wait(path, clock=clock)
        self.assertEqual(clock.sleeps, 0)

    def test_outside_root_is_rejected_without_reading_it(self):
        with self.assertRaises(ValueError):
            self.wait(ROOT.parent / "unapproved-receipt.json")

    def test_invalid_wait_bounds_are_rejected(self):
        for seconds in (True, 0, -1, 601, float("inf"), float("nan")):
            with self.subTest(seconds=seconds), self.assertRaises(ValueError):
                self.wait(self.path(), seconds)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", required=True)
    OUT = guard(ROOT, parser.parse_args().out)
    if Path.cwd() != ROOT or not (sys.flags.isolated and sys.flags.no_site and sys.dont_write_bytecode):
        raise RuntimeError("isolated explicit root required")
    if OUT.exists():
        raise RuntimeError("preserve previous receipt test artifacts")
    guard(ROOT, OUT / "result.json")
    OUT.mkdir(parents=True)
    output = io.StringIO()
    result = unittest.TextTestRunner(stream=output, verbosity=2).run(
        unittest.defaultTestLoader.loadTestsFromTestCase(ReceiptTests))
    import hashlib

    def record(path):
        return dict(path=str(path), bytes=path.stat().st_size,
                    sha256=hashlib.sha256(path.read_bytes()).hexdigest())

    helper["IO"]["write_json"](ROOT, OUT / "result.json", dict(
        passed=result.wasSuccessful(), tests=result.testsRun, failures=len(result.failures),
        errors=len(result.errors), output=output.getvalue(), hardware=False,
        source=record(MODULE), test_source=record(Path(__file__))))
    print(output.getvalue(), flush=True)
    raise SystemExit(0 if result.wasSuccessful() else 1)
