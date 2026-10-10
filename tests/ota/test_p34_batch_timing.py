"""Synthetic accounting negatives; actual snapshots are tested by Flutter CI."""
import json
from pathlib import Path
import sys
import subprocess
import unittest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "Tools/ota/p3-4-link-stats"))
import batch_timing as timing


def fixture():
    messages = [
        "OTA_LINK_SAMPLE label=upgrade kind=gatt_write us=10 bytes=10",
        "OTA_LINK_SAMPLE label=upgrade kind=gatt_write us=10 bytes=111",
        "OTA_LINK_SAMPLE label=upgrade kind=gatt_write us=100 bytes=244",
        "OTA_LINK_SAMPLE label=upgrade kind=batch_chunk us=200 bytes=244 frames=1",
        "OTA_LINK_SAMPLE label=upgrade kind=segment_first_send us=201 off=0 len=128",
        "OTA_LINK_SAMPLE label=upgrade kind=gatt_write us=100 bytes=182",
        "OTA_LINK_SAMPLE label=upgrade kind=batch_chunk us=400 bytes=182 frames=2",
        "OTA_LINK_SAMPLE label=upgrade kind=segment_first_send us=401 off=128 len=128",
        "OTA_LINK_SAMPLE label=upgrade kind=segment_first_send us=402 off=256 len=128",
        "OTA_LINK_SAMPLE label=upgrade kind=gatt_write us=10 bytes=42",
    ]
    summary = dict(schema=1, label="upgrade", clock="stopwatch-mono-us",
        gattWrites=dict(calls=5, bytes=589, errors=0),
        transfer=dict(startUs=0, endAckUs=1000, elapsedUs=1000, outcome="ok",
            segmentsUnique=3, segmentSendTotal=3, retransmitFrames=0,
            acks=dict(duplicate=0, error=0, malformed=0, noProgress=0, abort=0),
            ackSamples="partial:early=1", ackEarlyInvalid=1,
            dataBatch=dict(schema=1, maxFrames=3, chunks=2, bytes=426)))
    return messages + ["OTA_LINK_STATS " + json.dumps(summary)]


class Tests(unittest.TestCase):
    def test_v2_data_and_control_geometry_and_schema10(self):
        rows = [s.replace("bytes=111", "bytes=115").replace("bytes=42", "bytes=46")
                 .replace("bytes=182", "bytes=194") for s in fixture()]
        value = json.loads(rows[-1][len("OTA_LINK_STATS "):])
        value["gattWrites"]["bytes"] = 609
        value["transfer"]["dataBatch"]["bytes"] = 438
        rows[-1] = "OTA_LINK_STATS " + json.dumps(value)
        self.assertEqual(timing.analyze(rows, 384, protocol=2)["protocol"], 2)
        stamp = dict(schema=10, dataBatchFrames=12, androidPhyPolicy="off",
                     rebootInfoMaxAttempts=8, ackTimeoutMs=2000)
        timing.verify_batch_stamp(stamp, 12)
        with self.assertRaises(ValueError): timing.verify_batch_stamp({**stamp, "ackTimeoutMs": 0}, 12)
        with self.assertRaises(ValueError): timing.verify_batch_stamp({**stamp, "rebootInfoMaxAttempts": 13}, 12)
        with self.assertRaises(ValueError): timing.analyze(rows, 384, protocol=1)

    def test_schema7_twelve_frame_batch_and_old_limits(self):
        for schema, frames in ((5, 3), (6, 3), (7, 3), (7, 12)):
            timing.verify_batch_stamp(dict(schema=schema, dataBatchFrames=frames), frames)
        for stamp, frames in ((dict(schema=5, dataBatchFrames=12), 12),
                              (dict(schema=6, dataBatchFrames=12), 12),
                              (dict(schema=7, dataBatchFrames=3), 12),
                              (dict(schema=7, dataBatchFrames=12), 3),
                              (dict(schema=7, dataBatchFrames=12.0), 12),
                              (dict(schema=8, dataBatchFrames=12), 12)):
            with self.subTest(stamp=stamp, frames=frames), self.assertRaises(ValueError):
                timing.verify_batch_stamp(stamp, frames)

    def test_partial_final_batch_keeps_declared_maximum(self):
        rows = fixture()
        summary = json.loads(rows[-1].removeprefix('OTA_LINK_STATS '))
        summary['transfer']['dataBatch']['maxFrames'] = 12
        rows[-1] = 'OTA_LINK_STATS ' + json.dumps(summary)
        value = timing.analyze(rows, 384)
        self.assertEqual(value['maximum_batch_frames'], 12)
        self.assertEqual(value['chunks'], 2)

    def test_isolated_cli_resolves_only_its_local_reader(self):
        result = subprocess.run([sys.executable, '-I', '-S', '-B',
            str(ROOT / 'Tools/ota/p3-4-link-stats/batch_timing.py'), '--help'],
            cwd=ROOT, capture_output=True, timeout=10)
        self.assertEqual(result.returncode, 0, result.stderr)

    def test_batch_accounting_does_not_sum_shared_frame_writes_twice(self):
        value = timing.analyze(fixture(), 384)
        self.assertEqual(value["data_gatt_seconds"], .0002)
        self.assertEqual(value["remaining_transfer_seconds"], .0008)
        self.assertEqual(value["chunks"], 2)
        self.assertEqual(value["ack_early_invalid"], 1)

    def test_missing_duplicate_and_moved_completion_markers_fail(self):
        good = fixture()
        for bad in [good[:3] + good[4:], good[:4] + [good[3]] + good[4:],
                    good[:3] + [good[4], good[3]] + good[5:]]:
            with self.assertRaises(ValueError):
                timing.analyze(bad, 384)

    def test_wrong_bytes_and_frame_counts_fail(self):
        for old, new in [("bytes=244 frames=1", "bytes=243 frames=1"),
                         ("frames=2", "frames=1"), ("off=256", "off=128")]:
            with self.assertRaises(ValueError):
                timing.analyze([line.replace(old, new) for line in fixture()], 384)

    def test_retransmission_cannot_masquerade_as_clean_batch(self):
        with self.assertRaises(ValueError):
            timing.analyze(fixture() + ["OTA_LINK_SAMPLE label=upgrade kind=segment_retransmit us=500 off=0 len=128"], 384)

    def test_truncated_summary_and_negative_time_rejected(self):
        with self.assertRaises(ValueError):
            timing.analyze(fixture()[:-1], 384)
        bad = fixture()
        value = json.loads(bad[-1][len("OTA_LINK_STATS "):])
        value["transfer"]["endAckUs"] = -1
        bad[-1] = "OTA_LINK_STATS " + json.dumps(value)
        with self.assertRaises(ValueError):
            timing.analyze(bad, 384)


if __name__ == "__main__":
    unittest.main(verbosity=2)
