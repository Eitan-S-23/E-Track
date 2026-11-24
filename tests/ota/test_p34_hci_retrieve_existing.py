"""Bind recovery to a unique zero-exit generation and preserve report inventory."""
import hashlib
from pathlib import Path
import sys
import unittest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "Tools/ota"))
import p34_hci_retrieve_existing as f


class Tests(unittest.TestCase):
    def test_late_progress_receipt_is_recoverable(self):
        raw = b"BEGIN:/bugreports/a.zip\nOK:/bugreports/a.zip\nPROGRESS:9/10\n"
        receipt = dict(args=["shell", "bugreportz", "-p"], exit=0, stdout_bytes=len(raw),
                       stdout_sha256=hashlib.sha256(raw).hexdigest())
        self.assertEqual(f.completed_generation(raw, receipt, []), f.export.REMOTE + "/a.zip")
        for key, value in (("exit", 1), ("stdout_bytes", 0), ("stdout_sha256", "bad"), ("args", ["shell", "other"])):
            with self.assertRaises(RuntimeError): f.completed_generation(raw, dict(receipt, **{key: value}), [])
        with self.assertRaises(RuntimeError): f.completed_generation(raw, receipt, ["a.zip"])

    def test_inventory_preserves_exact_zip_sizes(self):
        raw = "total 2\n-rw------- 1 shell shell 123 2026-10-04 17:00 a.zip\n-rw------- 1 shell shell 9 2026-10-04 17:00 log.txt\n"
        self.assertEqual(f.inventory(raw), {"a.zip": 123})
        with self.assertRaises(RuntimeError): f.inventory(raw + raw)
        with self.assertRaises(ValueError): f.inventory(raw.replace("a.zip", "../a.zip"))


if __name__ == "__main__":
    unittest.main(verbosity=2)
