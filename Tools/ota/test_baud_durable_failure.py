"""Host-only regression tests for the bounded durable-failure reader."""
from __future__ import annotations

import argparse
import copy
import json
from pathlib import Path
import runpy
import struct
import unittest

SELF = Path(__file__).resolve()
subject = runpy.run_path(str(SELF.with_name("baud_durable_failure.py")), run_name="durable_test_subject")
classify, runs = subject["classify"], subject["terminated_runs"]


class Cases(unittest.TestCase):
    def test_real_foreground_failure(self):
        result = classify(self.original, 30000)
        self.assertEqual(result["result"], "FOREGROUND_NO_DURABLE_PROGRESS")
        self.assertEqual(result["durable_off"], 4096)
        self.assertEqual(result["idle_us"], 30036034)
        self.assertEqual(result["statistics"]["transfer"]["retransmitFrames"], 96)
        self.assertFalse(result["ota_success"])

    def test_background_before_invocation_is_not_its_pause(self):
        data = [{"kind": "line", "message": "OTA_MONO MONO_PAUSE monoUs=1 wallUs=1"}]+self.original
        self.assertEqual(classify(data, 30000)["result"], "FOREGROUND_NO_DURABLE_PROGRESS")

    def test_background_inside_invocation_rejected(self):
        data = copy.deepcopy(self.original)
        at = next(i for i, item in enumerate(data) if item.get("kind") == "upgrade-start")+1
        data.insert(at, {"kind": "line", "message": "OTA_MONO MONO_PAUSE monoUs=1 wallUs=1"})
        with self.assertRaisesRegex(RuntimeError, "in-transfer pause"):
            classify(data, 30000)

    def test_different_failure_rejected(self):
        data = copy.deepcopy(self.original)
        for item in data:
            if item.get("kind") == "line" and item["message"].startswith("OTA_LINK_STATS "):
                item["message"] = item["message"].replace("transport:NO_DURABLE_PROGRESS", "mcu-ack-0xff")
        with self.assertRaisesRegex(RuntimeError, "not a durable timeout"):
            classify(data, 30000)

    def test_deadline_not_reached_rejected(self):
        with self.assertRaisesRegex(RuntimeError, "deadline not reached"):
            classify(self.original, 31000)

    def test_success_rejected(self):
        data = copy.deepcopy(self.original)
        next(x for x in data if x.get("kind") == "upgrade-end")["outcome"] = "completed"
        with self.assertRaisesRegex(RuntimeError, "success"):
            classify(data, 30000)

    def test_four_internal_sessions_not_four_user_upgrades(self):
        self.assertEqual([x["run"] for x in runs(self.events)], [1, 2, 3, 4])
        self.assertEqual(sum(x.get("kind") == "upgrade-start" for x in self.original), 1)

    def test_missing_internal_session_rejected(self):
        data = [e for e in self.events if "ready run=2 " not in e.get("line", "")]
        with self.assertRaisesRegex(RuntimeError, "ambiguous"):
            runs(data)

    def test_latest_profile_is_not_required_to_equal_first(self):
        data = bytearray(self.profile)
        struct.pack_into("<I", data, 16, 4)
        value = subject["profile_record"](self.r, data, 4, 290810, 460800)
        self.assertEqual(value["run"], 4)

    def test_unobserved_profile_rejected(self):
        with self.assertRaisesRegex(RuntimeError, "identity changed"):
            subject["profile_record"](self.r, self.profile, 4, 290810, 460800)

    def test_active_profile_rejected(self):
        data = bytearray(self.profile)
        struct.pack_into("<I", data, 28, 1)
        with self.assertRaisesRegex(RuntimeError, "terminated"):
            subject["profile_record"](self.r, data, 1, 290810, 460800)

    def test_wrong_baud_rejected(self):
        with self.assertRaisesRegex(RuntimeError, "identity changed"):
            subject["profile_record"](self.r, self.profile, 1, 290810, 921600)

    def test_short_layout_rejected(self):
        with self.assertRaisesRegex(RuntimeError, "length"):
            subject["decode_layout"](b"bad")

    def test_out_of_bounds_layout_rejected(self):
        words = [0x50334C59, 576, len(subject["FIELDS"])]+[575, 4]*len(subject["FIELDS"])
        with self.assertRaisesRegex(RuntimeError, "outside"):
            subject["decode_layout"](struct.pack("<"+"I"*len(words), *words))

    def test_short_session_rejected(self):
        with self.assertRaisesRegex(RuntimeError, "length"):
            subject["decode_session"](b"", dict(size=576))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", required=True)
    args = parser.parse_args()
    r = subject["runtime"]()
    r.authority()
    out = r.b.checked(Path(args.out))
    subject["require"](Path.cwd() == r.b.ROOT and not out.exists(), "explicit root and fresh output required")
    r.b.checked(out/"result.json")
    original = r.cell("baud-460800")
    Cases.original = [json.loads(line) for line in (original/"finished/snapshot.jsonl").read_bytes().splitlines()]
    Cases.events = [json.loads(line) for line in (original/"mcu/events.jsonl").read_bytes().splitlines()]
    Cases.profile, Cases.r = (original/"mcu/profile.bin").read_bytes(), r
    result = unittest.TextTestRunner(verbosity=2).run(unittest.defaultTestLoader.loadTestsFromTestCase(Cases))
    r.save(out/"result.json", dict(passed=result.wasSuccessful(), tests=result.testsRun,
        failures=len(result.failures), errors=len(result.errors), hardware=False,
        sources=subject["source_records"](r), runtime_sources=r.sources()))
    raise SystemExit(0 if result.wasSuccessful() else 1)


if __name__ == "__main__":
    main()
