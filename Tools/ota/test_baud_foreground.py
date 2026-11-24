"""Verify nonce-only screening migration without device access."""
import copy
import json
from pathlib import Path
import runpy
import unittest

SELF = Path(__file__).resolve()
subject = runpy.run_path(str(SELF.with_name("baud_foreground.py")), run_name="foreground_test_subject")
r = subject["runtime"]()
old = subject["base_runtime"]().m.verified_assets()["groups"]["screen"]
new = r.m.verified_assets()["groups"]["screen"]


class Cases(unittest.TestCase):
    def test_real_new_package_equivalent(self):
        subject["equivalent"](old, new)

    def test_same_package_rejected(self):
        with self.assertRaisesRegex(RuntimeError, "nonce"):
            subject["equivalent"](old, old)

    def test_length_change_rejected(self):
        value = copy.deepcopy(new)
        value["package"]["bytes"] += 1
        with self.assertRaisesRegex(RuntimeError, "same-length"):
            subject["equivalent"](old, value)

    def test_raw_identity_changes_rejected(self):
        for name in ("baseline", "target", "baseline_identity", "target_identity"):
            with self.subTest(name=name):
                value = copy.deepcopy(new)
                value[name] = {}
                with self.assertRaisesRegex(RuntimeError, "firmware identity"):
                    subject["equivalent"](old, value)

    def test_each_decoder_guard_required(self):
        for name in ("passed", "byte_identical", "boot_ok", "guards_ok", "workspace_lifecycle_ok"):
            with self.subTest(name=name):
                value = copy.deepcopy(new)
                value["decoder"][name] = False
                with self.assertRaisesRegex(RuntimeError, "decoder"):
                    subject["equivalent"](old, value)

    def test_all_three_configs_share_input(self):
        configs = [r.experiment_config(run, new, baud, "https://foreground-fixture.trycloudflare.com")
                   for run, baud in zip(subject["RUNS"], (115200, 460800, 921600))]
        for config in configs:
            self.assertEqual(config["packageSha256"], new["package"]["sha256"])
            self.assertEqual(config["currentImageSha256"], old["baseline"]["sha256"])
            self.assertEqual(config["targetImageSha256"], old["target"]["sha256"])
        self.assertEqual([x["requestedBaud"] for x in configs], [115200, 460800, 921600])

    def test_original_recovery_still_matches_raw_images(self):
        previous = subject["base_runtime"]()
        restore = previous.load("foreground_test_restore", SELF.with_name("baud_restore.py"))
        expected = restore.expectation()
        prepared = previous.read(previous.b.OUT/"recovery/result.json")
        self.assertEqual(prepared["expected"], expected)
        for name in ("baseline", "target", "baseline_identity", "target_identity"):
            self.assertEqual(expected["group"][name], new[name])

    def test_failed_cell_not_advanceable(self):
        with self.assertRaisesRegex(RuntimeError, "finite"):
            r.advance("baud-115200-r6")

    def test_final_cell_not_advanceable(self):
        with self.assertRaisesRegex(RuntimeError, "finite"):
            r.advance("baud-921600")


if __name__ == "__main__":
    r.b.require(Path.cwd() == r.b.ROOT, "explicit project root required")
    out = r.b.checked(subject["OUT"]/"host-tests/result.json")
    r.b.require(not out.exists(), "preserve original tests")
    result = unittest.TextTestRunner(verbosity=2).run(unittest.defaultTestLoader.loadTestsFromTestCase(Cases))
    r.save(out, dict(passed=result.wasSuccessful(), tests=result.testsRun, failures=len(result.failures),
           errors=len(result.errors), hardware=False, sources=r.sources(), assets=r.b.record(subject["OUT"]/"assets.json")))
    raise SystemExit(0 if result.wasSuccessful() else 1)
