"""The independent SHA oracle rejects missing, duplicated and corrupt vectors."""
import hashlib
import io
from pathlib import Path
import sys
import unittest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "Tools/ota"))
import p34_sha_screen as f


class Tests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        pattern = bytes((i * 17 + 3) % 256 for i in range(max(f.LENGTHS) + 2))
        cls.lines = [f"{n} {chunk} {align} " + hashlib.sha256(pattern[align:align+n]).hexdigest()
                     for n in f.LENGTHS for chunk in f.CHUNKS for align in (0, 1)]

    def test_complete_oracle(self):
        self.assertEqual(f.verify_vectors("\n".join(self.lines).encode()), 208)

    def test_missing_or_duplicate(self):
        for rows in (self.lines[:-1], self.lines + self.lines[:1], []):
            with self.assertRaises(RuntimeError): f.verify_vectors("\n".join(rows).encode())

    def test_corrupt_digest(self):
        lines = list(self.lines)
        lines[-1] = lines[-1][:-64] + "0" * 64
        with self.assertRaises(RuntimeError): f.verify_vectors("\n".join(lines).encode())

    def test_bad_shape_or_unknown_tuple(self):
        for line in ("0 1 0", "2 1 0 " + "0" * 64):
            with self.assertRaises(RuntimeError): f.verify_vectors(line.encode())


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
