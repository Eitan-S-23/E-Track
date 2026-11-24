"""Ensure a native ring read cannot turn into a phone operation or replay."""
from pathlib import Path
import sys
import unittest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "Tools/ota"))
import p34_native_ring as ring


class Phone:
    def __init__(self, pid="25095", raw=b"existing log\n"):
        self.pid, self.raw, self.calls = pid, raw, []

    def command(self, args, **kwargs):
        self.calls.append((args, kwargs))
        return self.pid if args[0] == "shell" else self.raw


class RingTests(unittest.TestCase):
    def test_read_only_bounded_original_pid(self):
        p = Phone()
        self.assertEqual(ring.capture(p, 25095), b"existing log\n")
        args, kw = p.calls[-1]
        self.assertEqual(args, ["logcat", "-d", "-b", "main", "-v", "epoch", "-v", "usec",
                               "-t", "30000", "--pid=25095", "[FBP-Android]:V", "*:S"])
        self.assertEqual(kw, dict(timeout=45, binary=True))

    def test_invalid_pid_never_contacts_phone(self):
        for pid in (True, 0, -1, "25095"):
            p = Phone()
            with self.subTest(pid=pid), self.assertRaises(ValueError):
                ring.capture(p, pid)
            self.assertEqual(p.calls, [])

    def test_changed_missing_or_ambiguous_pid_never_dumps_or_restarts(self):
        for pid in ("", "1", "25095 7"):
            p = Phone(pid=pid)
            with self.subTest(pid=pid), self.assertRaises(ValueError):
                ring.capture(p, 25095)
            self.assertEqual(len(p.calls), 1)

    def test_empty_ring_remains_empty(self):
        self.assertEqual(ring.capture(Phone(raw=b""), 25095), b"")

    def test_oversized_ring_rejected(self):
        with self.assertRaises(ValueError):
            ring.capture(Phone(raw=b"x" * (ring.MAX_BYTES + 1)), 25095)


if __name__ == "__main__":
    unittest.main(verbosity=2)
