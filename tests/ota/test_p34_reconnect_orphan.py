"""Offline safety checks for abandoned reconnect observation retrieval."""
from pathlib import Path
import sys
import unittest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "Tools/ota"))
import p34_reconnect_orphan as orphan


class UnusedCaptureTests(unittest.TestCase):
    def setUp(self):
        self.health = dict(captureId=orphan.CAPTURE, healthy=True, lost=0, error=None,
                           upgradeStarts=0, upgradeEnds=0, outcome=None)

    def test_original_unused(self):
        self.assertTrue(orphan.unused(self.health, []))

    def test_started_or_completed_is_never_unused(self):
        for starts, ends, outcome in ((1, 0, None), (1, 1, "completed"), (1, 1, "not-completed")):
            with self.subTest(starts=starts, ends=ends, outcome=outcome):
                self.assertFalse(orphan.unused(dict(self.health, upgradeStarts=starts,
                    upgradeEnds=ends, outcome=outcome), []))

    def test_snapshot_disqualifies_unused(self):
        self.assertFalse(orphan.unused(self.health, ["snapshot-1.jsonl"]))

    def test_health_and_identity_fail_closed(self):
        for key, value in (("healthy", False), ("lost", 1), ("error", "disk"),
                           ("outcome", "completed"), ("captureId", "other")):
            with self.subTest(key=key):
                self.assertFalse(orphan.unused(dict(self.health, **{key: value}), []))

    def test_missing_fields_fail_closed(self):
        for key in ("captureId", "healthy", "lost", "upgradeStarts", "upgradeEnds"):
            value = dict(self.health)
            del value[key]
            self.assertFalse(orphan.unused(value, []))

    def test_boolean_counters_are_not_zero(self):
        for key in ("upgradeStarts", "upgradeEnds"):
            self.assertFalse(orphan.unused(dict(self.health, **{key: False}), []))


class PhoneListingTests(unittest.TestCase):
    def test_space_or_tab_separator(self):
        for separator in ("\t", "        "):
            self.assertTrue(orphan.phone_available("List of devices attached\nserial" + separator +
                                                  "device model:V2312A\n", "serial"))

    def test_absent_unauthorized_offline_or_ambiguous(self):
        for listing in ("", "other device", "serial unauthorized", "serial offline", "serial",
                        "serial device\nserial device"):
            self.assertFalse(orphan.phone_available(listing, "serial"))


class RecoveryBindingTests(unittest.TestCase):
    def test_exact_unused_binding_only(self):
        health = dict(captureId=orphan.CAPTURE, healthy=True, lost=0, error=None,
                      upgradeStarts=0, upgradeEnds=0, outcome=None)
        observed = dict(pid=23723, pid_checked_before_after=True, safe_idle=True,
                        remote="files/p34-observations/" + orphan.CAPTURE,
                        config=dict(sha256="bound"), health=health, snapshots=[])
        orphan.validate_phone(observed, dict(sha256="bound"))
        for key, value in (("pid", 2), ("pid_checked_before_after", False), ("safe_idle", False),
                           ("remote", "other"), ("config", dict(sha256="other")),
                           ("snapshots", ["snapshot-1.jsonl"]), ("health", {})):
            with self.subTest(key=key), self.assertRaises(RuntimeError):
                orphan.validate_phone(dict(observed, **{key: value}), dict(sha256="bound"))


if __name__ == "__main__":
    unittest.main(verbosity=2)
