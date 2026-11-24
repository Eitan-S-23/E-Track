"""Host-only negative cases for pre-END failure reconciliation."""
from __future__ import annotations

import argparse
import copy
import hashlib
import json
from pathlib import Path
import runpy
import struct
import unittest
import zlib

SELF = Path(__file__).resolve()
subject = runpy.run_path(str(SELF.with_name("baud_interruption.py")), run_name="test_subject")
classify = subject["classify"]
decode = subject["decode_journal"]


def journal(durable=45056, total=290810):
    data = bytearray(b"\xff"*4096)
    etrj = b"ETRJ"+hashlib.sha256(b"fixture").digest()+struct.pack("<I", total)
    data[0x40:0x6c] = etrj+struct.pack("<I", zlib.crc32(etrj) & 0xffffffff)
    for block in range((durable+4095)//4096):
        data[0x70+block//8] &= ~(1 << (block % 8))
    return data


class Cases(unittest.TestCase):
    sha = hashlib.sha256(b"fixture").hexdigest()

    def test_durable_prefix(self):
        self.assertEqual(decode(journal(), self.sha, 290810)["durable_off"], 45056)

    def test_zero_prefix(self):
        self.assertEqual(decode(journal(0), self.sha, 290810)["durable_off"], 0)

    def test_bad_crc(self):
        data = journal()
        data[0x68] ^= 1
        with self.assertRaisesRegex(RuntimeError, "CRC"):
            decode(data, self.sha, 290810)

    def test_wrong_package(self):
        with self.assertRaisesRegex(RuntimeError, "identity"):
            decode(journal(), "00"*32, 290810)

    def test_wrong_length(self):
        with self.assertRaisesRegex(RuntimeError, "identity"):
            decode(journal(), self.sha, 290811)

    def test_committed_header(self):
        data = journal()
        data[28:32] = b"TMOC"
        with self.assertRaisesRegex(RuntimeError, "committed"):
            decode(data, self.sha, 290810)

    def test_bitmap_hole(self):
        data = journal()
        data[0x70] |= 2
        with self.assertRaisesRegex(RuntimeError, "bitmap"):
            decode(data, self.sha, 290810)

    def test_out_of_range_block(self):
        data = journal()
        data[0x70+20] &= 0xfe
        with self.assertRaisesRegex(RuntimeError, "bitmap"):
            decode(data, self.sha, 290810)

    def test_complete_is_not_interrupted(self):
        with self.assertRaisesRegex(RuntimeError, "complete staging"):
            decode(journal(290810), self.sha, 290810)

    def test_short_journal(self):
        with self.assertRaisesRegex(RuntimeError, "bounds"):
            decode(journal()[:-1], self.sha, 290810)

    def test_real_original(self):
        result = classify(self.original, 30000)
        self.assertEqual(result["result"], "BACKGROUND_PAUSE_ABORTED_PRE_END")
        self.assertEqual([p["duration_us"] for p in result["pauses"]], [6000796, 105284339])
        self.assertEqual(result["durable_off"], 45056)
        self.assertFalse(result["full_package_throughput_eligible"])

    def test_without_long_pause_is_not_background_diagnosis(self):
        result = classify(self.original, 120000)
        self.assertEqual(result["result"], "PRE_END_FAILURE_NEEDS_TRIAGE")

    def test_success_rejected(self):
        data = copy.deepcopy(self.original)
        next(item for item in data if item.get("kind") == "upgrade-end")["outcome"] = "completed"
        with self.assertRaisesRegex(RuntimeError, "success"):
            classify(data, 30000)

    def test_missing_end_rejected(self):
        with self.assertRaisesRegex(RuntimeError, "finished"):
            classify([item for item in self.original if item.get("kind") != "upgrade-end"], 30000)

    def test_repeated_start_rejected(self):
        with self.assertRaisesRegex(RuntimeError, "finished"):
            classify(self.original+[{"kind": "upgrade-start"}], 30000)

    def test_backward_clock_rejected(self):
        data = copy.deepcopy(self.original)
        for item in data:
            if item.get("kind") == "line" and item["message"].startswith("OTA_MONO MONO_RESUME monoUs=333606878"):
                item["message"] = "OTA_MONO MONO_RESUME monoUs=1 wallUs=1"
        with self.assertRaisesRegex(RuntimeError, "nonmonotonic"):
            classify(data, 30000)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", required=True)
    args = parser.parse_args()
    r = subject["runtime"]()
    r.authority()
    out = r.b.checked(Path(args.out))
    require = subject["require"]
    require(Path.cwd() == r.b.ROOT and not out.exists(), "explicit root and fresh test output required")
    r.b.checked(out/"result.json")
    original = r.cell("baud-115200-r6")/"finished/snapshot.jsonl"
    Cases.original = [json.loads(line) for line in original.read_bytes().splitlines()]
    suite = unittest.defaultTestLoader.loadTestsFromTestCase(Cases)
    result = unittest.TextTestRunner(verbosity=2).run(suite)
    r.save(out/"result.json", dict(passed=result.wasSuccessful(), tests=result.testsRun,
           failures=len(result.failures), errors=len(result.errors), hardware=False,
           source=r.b.record(SELF.with_name("baud_interruption.py")), test_source=r.b.record(SELF),
           original=r.b.record(original), runtime_sources=r.sources()))
    raise SystemExit(0 if result.wasSuccessful() else 1)


if __name__ == "__main__":
    main()
