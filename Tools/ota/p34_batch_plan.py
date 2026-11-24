"""Offline DATA batching geometry; not a sender or a throughput prediction."""
import argparse
import json
from pathlib import Path
import sys


def positive(value, limit, name):
    if type(value) is not int or not 1 <= value <= limit:
        raise ValueError(name + " is outside its integer bound")


def plan_batch(frames, offsets, *, chunk_bytes, credit, maximum_frames):
    """Reserve complete DATA frames from one block before writing any bytes.

    Callers must supply actual free credit, not the negotiated window. A batch
    owns the stream until its last complete frame; cancellation cannot inject
    ABORT between its chunks. This function grants no runtime authority.
    """
    positive(chunk_bytes, 512, "chunk bytes")
    positive(credit, 32, "free credit")
    positive(maximum_frames, 32, "maximum frames")
    if not frames or len(frames) != len(offsets) or len(frames) > 32:
        raise ValueError("one bounded block candidate list required")
    for frame, offset in zip(frames, offsets):
        if type(frame) is not bytes or not 15 <= len(frame) <= 142:
            raise ValueError("DATA frame geometry required")
        if type(offset) is not int or offset < 0 or offset % 128:
            raise ValueError("aligned nonnegative DATA offset required")
    if offsets != sorted(set(offsets)):
        raise ValueError("DATA offsets must be unique and ordered")
    if any(len(frame) != 142 for frame in frames[:-1]):
        raise ValueError("short DATA frame may only terminate the candidate list")
    count = 0
    for offset in offsets[:min(credit, maximum_frames)]:
        if offset // 4096 != offsets[0] // 4096:
            break
        count += 1
    selected = frames[:count]
    stream = b"".join(selected)
    chunks = [stream[i:i + chunk_bytes] for i in range(0, len(stream), chunk_bytes)]
    ends, end = [], 0
    for frame in selected:
        end += len(frame)
        ends.append((end - 1) // chunk_bytes)
    return dict(count=count, chunks=chunks, frame_completion_chunks=ends,
                bytes=len(stream), offsets=offsets[:count])


def geometry(total, chunk_bytes, maximum_frames, credit):
    positive(total, 1048576, "package bytes")
    positive(chunk_bytes, 512, "chunk bytes")
    positive(maximum_frames, 32, "maximum frames")
    positive(credit, 32, "free credit")
    offsets = list(range(0, total, 128))
    original_calls = sum((min(128, total - off) + 14 + chunk_bytes - 1) // chunk_bytes
                         for off in offsets)
    calls = batches = max_batch_chunks = 0
    for start in range(0, len(offsets), 32):
        pending = offsets[start:start + 32]
        while pending:
            frames = [bytes(min(128, total - off) + 14) for off in pending]
            batch = plan_batch(frames, pending, chunk_bytes=chunk_bytes,
                               credit=credit, maximum_frames=maximum_frames)
            calls += len(batch["chunks"])
            batches += 1
            max_batch_chunks = max(max_batch_chunks, len(batch["chunks"]))
            pending = pending[batch["count"]:]
    return dict(package_bytes=total, data_frames=len(offsets), chunk_bytes=chunk_bytes,
                maximum_frames=maximum_frames, assumed_free_credit=credit,
                original_data_calls=original_calls, batched_data_calls=calls,
                calls_saved=original_calls - calls, batches=batches,
                max_batch_chunks=max_batch_chunks, measured_speedup=False,
                scope="geometry only; assumes credit available before each batch; excludes control frames, retries and timing")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--report", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    root = Path(__file__).resolve().parents[2]
    if Path.cwd() != root or not (sys.flags.isolated and sys.flags.no_site and sys.dont_write_bytecode):
        raise ValueError("explicit root and isolated Python required")
    sys.path.insert(0, str(root / "Tools/ota"))
    import p34_session as cli
    store = cli.Store(root)
    out = store.checked(args.out)
    if out.exists():
        raise ValueError("preserve previous analysis")
    report = store.read(store.checked(args.report))
    if report["result"] != "FULL_INSTALL_VERIFIED":
        raise ValueError("verified source report required")
    for key in ("snapshot", "plan"):
        item = report["inputs"][key]
        if cli.record(store.checked(item["path"])) != item:
            raise ValueError("original evidence changed")
    metrics = report["full_metrics"]
    if metrics["binding"]["writeMode"] != "without":
        raise ValueError("this experiment is scoped to without-response writes")
    total = report["summary"]["input"]["packageBytes"]
    mtu = metrics["binding"]["mtuChunkBytes"]
    window = report["experiment"]["senderWindowSegments"]
    result = dict(result="OFFLINE_BATCH_GEOMETRY", device_operations=0,
                  source=cli.record(__file__), original_report=cli.record(args.report),
                  candidates=[geometry(total, mtu, n, window) for n in (1, 2, 3, 4, 8)],
                  runtime_integration=False, measured_speedup=False)
    store.write(out, result)
    print(json.dumps(result))


if __name__ == "__main__":
    main()
