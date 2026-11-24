"""Offline guards for non-destructive inactive capture archival."""
import io
import os
from pathlib import Path
import sys
import unittest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "Tools/ota"))
import p34_radio_archive as a
import p34_install_cost as host


class Guards(unittest.TestCase):
    old = "1790896481244860-1d625871c806583d059b8535"
    new = "1790922902993068-85c604a42872fe472af630d8"

    def test_inventory(self):
        a.names_valid([self.old, self.new], self.old, self.new)

    def test_current_or_missing_capture_rejected(self):
        for selected, protected in [(self.new,self.old),(self.new,self.new),(self.old,"missing")]:
            with self.assertRaises(RuntimeError): a.names_valid([self.old,self.new], selected, protected)

    def test_ambiguous_inventory_rejected(self):
        for names in ([self.old], [self.old,self.new,self.old], [self.old,self.new,"../escape"]):
            with self.assertRaises(RuntimeError): a.names_valid(names,self.old,self.new)

    def test_exact_capture_files(self):
        names = ["events.jsonl", "health.json", "snapshot-1.jsonl"]
        a.files_valid(names)
        a.files_valid(names + ["health.json.tmp"])
        for broken in (names + ["unknown"], names[:-1], names + ["events.jsonl"]):
            with self.assertRaises(RuntimeError): a.files_valid(broken)

    def test_original_verified_snapshot(self):
        s = a.cli.Store(ROOT)
        report = a.proof(s, a.radio.TRIALS / "baseline")
        raw = Path(report["inputs"]["snapshot"]["path"]).read_bytes()
        a.equal_snapshot(raw, report)
        with self.assertRaises(RuntimeError): a.equal_snapshot(raw + b"x", report)

    def test_health(self):
        data = dict(captureId=self.old, healthy=True, lost=0, error=None, upgradeStarts=1,
                    upgradeEnds=1, outcome="completed")
        a.healthy(a.json.dumps(data), self.old)
        for key, value in [("lost",1),("healthy",False),("error","x"),("upgradeEnds",0),
                           ("outcome","not-completed"),("captureId",self.new)]:
            with self.assertRaises(RuntimeError): a.healthy(a.json.dumps(dict(data, **{key:value})), self.old)


if __name__ == "__main__":
    a.cli.require(Path.cwd() == ROOT and sys.flags.isolated and sys.flags.no_site and sys.dont_write_bytecode,
                  "explicit root and isolated Python required")
    s, out = a.cli.Store(ROOT), a.AREA / "archive-tests"
    a.cli.require(not out.exists(), "preserve test evidence")
    os.environ.update(host.environment(s, out))
    stream = io.StringIO()
    result = unittest.TextTestRunner(stream=stream, verbosity=2).run(unittest.defaultTestLoader.loadTestsFromTestCase(Guards))
    log = s.raw(out / "tests.log", stream.getvalue().encode())
    s.write(out / "result.json", dict(result="PASS" if result.wasSuccessful() else "FAIL", tests=result.testsRun,
        errors=len(result.errors), failures=len(result.failures), source=a.cli.record(a.__file__),
        test=a.cli.record(__file__), log=log, hardware=False))
    print(stream.getvalue(), flush=True)
    sys.exit(not result.wasSuccessful())
