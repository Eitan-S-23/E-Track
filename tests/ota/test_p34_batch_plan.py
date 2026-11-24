"""Pure host checks for byte preservation and bounded DATA batching."""
import importlib.util
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[2]
SPEC = importlib.util.spec_from_file_location("batch", ROOT / "Tools/ota/p34_batch_plan.py")
batch = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(batch)


class Tests(unittest.TestCase):
    def plan(self, frames=None, offsets=None, **options):
        frames = frames if frames is not None else [bytes([i]) * 142 for i in range(3)]
        offsets = offsets if offsets is not None else [0, 128, 256]
        return batch.plan_batch(frames, offsets, **dict(
            dict(chunk_bytes=244, credit=28, maximum_frames=3), **options))

    def test_three_frames_preserve_all_bytes_in_two_writes(self):
        value = self.plan()
        self.assertEqual([len(c) for c in value["chunks"]], [244, 182])
        self.assertEqual(b"".join(value["chunks"]), b"".join(bytes([i]) * 142 for i in range(3)))
        self.assertEqual(value["frame_completion_chunks"], [0, 1, 1])

    def test_actual_free_credit_caps_reservation(self):
        self.assertEqual(self.plan(credit=1)["count"], 1)
        with self.assertRaises(ValueError):
            self.plan(credit=0)

    def test_never_crosses_durable_block(self):
        self.assertEqual(self.plan(offsets=[3968, 4096, 4224])["count"], 1)

    def test_resume_gaps_remain_ordered_without_fabricating_frames(self):
        self.assertEqual(self.plan(offsets=[0, 512, 1024])["offsets"], [0, 512, 1024])

    def test_short_tail_bytes_are_preserved(self):
        frames = [b"a" * 142, b"b" * 15]
        value = self.plan(frames, [4096, 4224])
        self.assertEqual(value["chunks"], [b"".join(frames)])
        with self.assertRaises(ValueError):
            self.plan(list(reversed(frames)), [4096, 4224])

    def test_fragmented_mtu_keeps_completion_mapping(self):
        value = self.plan(chunk_bytes=20)
        self.assertEqual(value["frame_completion_chunks"], [7, 14, 21])
        self.assertEqual(sum(map(len, value["chunks"])), 426)

    def test_bad_offsets_and_frame_geometry_rejected(self):
        for offsets in ([128, 0, 256], [0, 0, 256], [0, 129, 256], [-128, 0, 128]):
            with self.subTest(offsets=offsets), self.assertRaises(ValueError):
                self.plan(offsets=offsets)
        for frames in ([], [b"a" * 143], [bytearray(142)]):
            with self.subTest(frames=frames), self.assertRaises(ValueError):
                self.plan(frames, [0] * len(frames))

    def test_scalar_types_and_bounds_rejected(self):
        for key, value in (("credit", True), ("maximum_frames", 33), ("chunk_bytes", 0)):
            with self.subTest(key=key), self.assertRaises(ValueError):
                self.plan(**{key: value})
        with self.assertRaises(ValueError):
            batch.geometry(0, 244, 3, 28)

    def test_single_frame_is_identical_call_geometry(self):
        value = batch.geometry(293036, 244, 1, 28)
        self.assertEqual(value["original_data_calls"], 2290)
        self.assertEqual(value["calls_saved"], 0)
        self.assertFalse(value["measured_speedup"])

    def test_two_frames_do_not_save_full_frame_writes_at_mtu247(self):
        value = batch.geometry(4096, 244, 2, 28)
        self.assertEqual(value["calls_saved"], 0)
        self.assertEqual(batch.geometry(4096, 244, 3, 28)["batched_data_calls"], 22)

    def test_all_supported_lengths_and_mtu_preserve_geometry(self):
        for total in (1, 128, 129, 4095, 4096, 4097, 293036):
            for mtu in (20, 142, 244, 512):
                value = batch.geometry(total, mtu, 3, 28)
                self.assertGreater(value["batched_data_calls"], 0)
                self.assertGreaterEqual(value["calls_saved"], 0)


if __name__ == "__main__":
    unittest.main(verbosity=2)
