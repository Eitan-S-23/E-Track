"""Offline checks for the finite retry APK/device route."""
from __future__ import annotations

import copy
from pathlib import Path
import runpy
import unittest

SELF = Path(__file__).resolve()
subject = runpy.run_path(str(SELF.with_name("baud_retry.py")), run_name="retry_test_subject")


class Cases(unittest.TestCase):
    def test_original_failed_state_is_reconciled(self):
        subject["reconcile"](self.result, self.owner)

    def test_unclosed_reader_rejected(self):
        value = copy.deepcopy(self.result)
        value["reader_closed"] = False
        with self.assertRaisesRegex(RuntimeError, "unresolved"):
            subject["reconcile"](value, self.owner)

    def test_forced_owner_exit_rejected(self):
        owner = dict(self.owner, forced_termination=True)
        with self.assertRaisesRegex(RuntimeError, "unresolved"):
            subject["reconcile"](self.result, owner)

    def test_changed_durable_rejected(self):
        value = copy.deepcopy(self.result)
        value["journal"]["durable_off"] = 8192
        with self.assertRaisesRegex(RuntimeError, "differs"):
            subject["reconcile"](value, self.owner)

    def test_committed_staging_rejected(self):
        value = copy.deepcopy(self.result)
        value["journal"]["committed"] = True
        with self.assertRaisesRegex(RuntimeError, "differs"):
            subject["reconcile"](value, self.owner)

    def test_nonpassive_reconciliation_rejected(self):
        value = dict(self.result, reset=1)
        with self.assertRaisesRegex(RuntimeError, "passive"):
            subject["reconcile"](value, self.owner)

    def test_runtime_uses_new_apk_and_current_owned_route(self):
        self.assertEqual(self.r.PKG, "com.wen.gaia.gaia.p34retry")
        self.assertEqual(self.r.PHONE.name, "phone-r4")
        self.assertEqual(self.r.NETWORK.name, "network-r2")

    def test_runtime_binds_new_sources_and_original_assets(self):
        sources = {Path(item["path"]).name for item in self.r.sources()}
        self.assertTrue({"baud_retry.py", "test_baud_retry.py", "baud_uncached.py"} <= sources)
        group = self.r.m.verified_assets()["groups"]["screen"]
        self.assertEqual(group["package"]["sha256"], self.result["journal"]["package_sha256"])
        self.assertEqual(group["baseline"]["sha256"], self.result["image"]["sha256"])


def main():
    r = subject["runtime"]()
    out = r.b.checked(subject["OUT"]/"host-tests/result.json")
    subject["require"](Path.cwd() == r.b.ROOT and not out.exists(), "explicit root and fresh tests required")
    Cases.r = r
    Cases.result = r.read(r.cell("baud-460800")/"failure/readback/result.json")
    Cases.owner = r.read(r.RUNTIME/"readback-baud-460800-durable/closed.json")
    result = unittest.TextTestRunner(verbosity=2).run(unittest.defaultTestLoader.loadTestsFromTestCase(Cases))
    r.save(out, dict(passed=result.wasSuccessful(), tests=result.testsRun, sources=r.sources(),
                    failures=len(result.failures), errors=len(result.errors), hardware=False))
    raise SystemExit(0 if result.wasSuccessful() else 1)


if __name__ == "__main__":
    main()
