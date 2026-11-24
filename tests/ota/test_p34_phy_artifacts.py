"""Exact native checkout encoding and immutable receipt reuse; no network."""
import hashlib
import io
from pathlib import Path
import runpy
import sys
import unittest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "Tools/ota"))
import p34_phy_artifacts as f


class Guards(unittest.TestCase):
    def test_exact_blob_and_windows_checkout(self):
        raw = b"package fixture;\nclass A {}\n"
        sha = lambda data: hashlib.sha256(data).hexdigest()
        self.assertEqual(f.native_encoding(raw, sha(raw), windows=False), "git-blob-bytes")
        self.assertEqual(f.native_encoding(raw, sha(raw.replace(b"\n", b"\r\n")), windows=True), "windows-crlf-checkout")
        with self.assertRaises(RuntimeError): f.native_encoding(raw, sha(raw.replace(b"\n", b"\r\n")), windows=False)
        for changed in (raw + b" ", raw.replace(b"A", b"B"), raw.replace(b"\n", b"\r\r\n")):
            with self.assertRaises(RuntimeError): f.native_encoding(raw, sha(changed), windows=True)

    def test_existing_original_receipts_are_discovered(self):
        area = ROOT / ".cache/p34-phy/ci/37137779427"
        records = f.existing_receipts(area, 11279135927)
        self.assertEqual(len(records), 2)
        self.assertTrue(all(p.is_file() for p in records))
        self.assertEqual(f.existing_receipts(area, 0), [])


if __name__ == "__main__":
    if not (Path.cwd() == ROOT and sys.flags.isolated and sys.flags.no_site and sys.dont_write_bytecode):
        raise RuntimeError("isolated explicit root required")
    h = runpy.run_path(str(ROOT / ".agents/skills/e-track-flutter-debug/scripts/host_io.py"))
    out = h["checked_output"](ROOT, ROOT / ".cache/p34-phy/artifact-tests-001/result.json")
    stream = io.StringIO()
    result = unittest.TextTestRunner(stream=stream, verbosity=2).run(unittest.defaultTestLoader.loadTestsFromTestCase(Guards))
    h["write_json"](ROOT, out, dict(passed=result.wasSuccessful(), count=result.testsRun, log=stream.getvalue(),
        source_sha256=hashlib.sha256(Path(f.__file__).read_bytes()).hexdigest(), network=False))
    print(stream.getvalue())
    sys.exit(not result.wasSuccessful())
