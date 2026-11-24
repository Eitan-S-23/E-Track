"""Actual inspector regressions for known cached-package coordinator recovery."""
import io
import json
from pathlib import Path
import runpy
import sys
import unittest

ROOT = Path(__file__).resolve().parents[2]
helper = runpy.run_path(str(Path(__file__).with_name("baud_download_resume.py")), run_name="tested_download_resume")
r = helper["runtime"]()
OUT = r.b.checked(r.b.OUT / "host-tests-download-resume-001")


class DownloadResumeTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cell = r.cell("bootstrap")
        cls.config = r.read(cell / "config.json")
        query = sorted((cell / "queries").iterdir())[0]
        cls.before = (query / "health-before.json").read_bytes()
        cls.after = (query / "health-after.json").read_bytes()
        cls.events = (query / "events.jsonl").read_bytes()
        cls.pid = r.read(cell / "launched.json")["pid"]
        cls.stale = r.read(ROOT / ".cache/p34b/assets/result.json")["groups"]["bootstrap"]["package"]
        cls.old_bytes = Path(cls.stale["path"]).read_bytes()
        cls.new_bytes = Path(cls.config["assets"]["package"]["path"]).read_bytes()

    def setUp(self):
        self.cell = r.b.checked(OUT / "fixtures" / self._testMethodName)
        r.save(self.cell / "config.json", self.config)
        self.directory = self.cell / "host-download-resume-001"
        self.data = self.old_bytes
        self.health = self.after
        self.health_reads = 0
        self.old_cell, self.old_phone = r.cell, r.phone
        test = self

        class Phone:
            query = r.phone("bootstrap").query
            envelope = r.phone("bootstrap").envelope

            def location(self, _):
                return r.PKG, test.pid, "fixture-observation"

            def file_bytes(self, pkg, path, *args, **kwargs):
                if path.endswith("health.json"):
                    test.health_reads += 1
                    return test.before if test.health_reads % 2 else test.health
                if path.endswith("events.jsonl"):
                    return test.events
                return test.data

            def command(self, args, **kwargs):
                return str(test.pid) if "pidof" in args else args[-1]

        self.phone = Phone()
        r.cell, r.phone = lambda _: self.cell, lambda _: self.phone
        self.unbind = helper["bind"](r, "bootstrap", self.stale, self.directory)

    def tearDown(self):
        self.unbind()
        r.cell, r.phone = self.old_cell, self.old_phone

    def test_known_old_package_waits_without_admitting_input(self):
        self.assertIsNone(r.inspect_start("bootstrap"))
        value = r.read(self.directory / "known-stale-package.json")
        self.assertEqual(value["observed"], helper["identity"](self.old_bytes))
        self.assertFalse((self.cell / "downloaded-full.etu").exists())

    def test_new_exact_package_passes_original_query_and_digest_guards(self):
        self.data = self.new_bytes
        value = r.inspect_start("bootstrap")
        self.assertEqual(r.read(value["path"])["result"], "PHONE_QUERY_AND_PACKAGE_VERIFIED")
        self.assertEqual((self.cell / "downloaded-full.etu").read_bytes(), self.new_bytes)

    def test_unknown_corruption_still_fails_closed(self):
        self.data = b"not a known package"
        with self.assertRaisesRegex(RuntimeError, "downloaded package differs"):
            r.inspect_start("bootstrap")
        self.assertFalse((self.directory / "known-stale-package.json").exists())

    def test_ota_activity_is_not_hidden_by_cached_package(self):
        health = json.loads(self.health)
        health["upgradeStarts"] = 1
        self.health = json.dumps(health).encode()
        with self.assertRaises(RuntimeError):
            r.inspect_start("bootstrap")
        self.assertFalse((self.directory / "known-stale-package.json").exists())

    def test_repeated_wait_preserves_first_cache_evidence(self):
        r.inspect_start("bootstrap")
        path = self.directory / "known-stale-package.json"
        before = path.read_bytes()
        self.assertIsNone(r.inspect_start("bootstrap"))
        self.assertEqual(path.read_bytes(), before)

    def test_reader_is_restored_after_failure(self):
        original = self.phone.file_bytes
        self.data = b"unknown"
        with self.assertRaises(RuntimeError):
            r.inspect_start("bootstrap")
        self.assertEqual(self.phone.file_bytes, original)

    def test_old_coordinator_result_is_not_overwritten(self):
        r.b.io.write_json(ROOT, self.cell / "coordinator-result.json", dict(error="original"))
        r.save(self.cell / "coordinator-result.json", dict(result="new"))
        self.assertEqual(r.read(self.cell / "coordinator-result.json"), dict(error="original"))
        self.assertEqual(r.read(self.directory / "coordinator-result.json"), dict(result="new"))

    def test_wrong_run_is_rejected(self):
        with self.assertRaisesRegex(RuntimeError, "different run"):
            r.inspect_start("baud-460800")


class AdmissionTests(unittest.TestCase):
    def test_only_healthy_zero_activity_is_admitted(self):
        health = dict(healthy=True, error=None, lost=0, upgradeStarts=0, upgradeEnds=0)
        helper["no_upgrade"](health)
        for patch in (dict(healthy=False), dict(error="failed"), dict(lost=1),
                      dict(upgradeStarts=1), dict(upgradeEnds=1), dict(upgradeStarts=False)):
            with self.subTest(patch=patch), self.assertRaises(RuntimeError):
                helper["no_upgrade"](dict(health, **patch))


if __name__ == "__main__":
    r.b.require(Path.cwd().resolve() == ROOT and sys.flags.isolated and sys.flags.no_site and
                sys.dont_write_bytecode, "isolated explicit root required")
    r.b.require(not OUT.exists(), "preserve prior test receipt")
    for leaf in ("result.json", "fixtures"):
        r.b.checked(OUT / leaf)
    output = io.StringIO()
    result = unittest.TextTestRunner(stream=output, verbosity=2).run(unittest.defaultTestLoader.loadTestsFromModule(sys.modules[__name__]))
    r.save(OUT / "result.json", dict(passed=result.wasSuccessful(), tests=result.testsRun,
        failures=len(result.failures), errors=len(result.errors), output=output.getvalue(), hardware=False,
        source=r.b.record(Path(__file__).with_name("baud_download_resume.py")),
        test_source=r.b.record(Path(__file__)), runtime_sources=r.sources()))
    print(output.getvalue(), flush=True)
    raise SystemExit(0 if result.wasSuccessful() else 1)
