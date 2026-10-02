"""Read-only clean-batch timing checks; never firmware acceptance or a P99 gate."""
import argparse
import json
from pathlib import Path
import re

from observation_capture import require, verify, MAX_BYTES


def analyze(messages, total):
    require(type(total) is int and 64 <= total <= 1048576, "bounded package required")
    summaries, writes, chunks, segments = [], [], [], []
    awaiting = 0
    for line in messages:
        if line.startswith("OTA_LINK_STATS "):
            item = json.loads(line[len("OTA_LINK_STATS "):])
            if item["label"] == "upgrade":
                summaries.append(item)
        match = re.fullmatch(r"OTA_LINK_SAMPLE label=upgrade kind=(\w+) us=(\d+)(.*)", line)
        if not match:
            continue
        kind, stamp = match[1], int(match[2])
        fields = {key: int(value) for key, value in re.findall(r"(\w+)=(\d+)", match[3])}
        if kind == "gatt_write":
            require(not awaiting and not fields.get("error"), "incomplete completion group or failed GATT")
            writes.append(dict(us=stamp, bytes=fields["bytes"], assigned=False))
        elif kind == "batch_chunk":
            require(not awaiting and writes and not writes[-1]["assigned"], "missing/duplicate batch write")
            require(fields["bytes"] == writes[-1]["bytes"] and 0 <= fields["frames"] <= 3,
                    "batch geometry differs")
            writes[-1]["assigned"] = True
            awaiting = fields["frames"]
            chunks.append(dict(at=stamp, frames=awaiting, **writes[-1]))
        elif kind == "segment_first_send":
            require(awaiting > 0 and chunks[-1]["at"] <= stamp, "segment outside completion group")
            segments.append((fields["off"], fields["len"]))
            awaiting -= 1
        elif kind == "segment_retransmit":
            raise ValueError("retransmissions require a separate non-clean analysis")
    require(len(summaries) == 1 and not awaiting and chunks, "incomplete batch capture")
    summary = summaries[0]
    transfer, gatt = summary["transfer"], summary["gattWrites"]
    batch = transfer["dataBatch"]
    count = (total + 127) // 128
    require(summary["schema"] == 1 and summary["clock"] == "stopwatch-mono-us" and
            transfer["outcome"] == "ok" and batch["schema"] == 1 and batch["maxFrames"] == 3,
            "unsupported batch timing schema")
    require(segments == [(off, min(128, total - off)) for off in range(0, total, 128)] and
            transfer["segmentsUnique"] == transfer["segmentSendTotal"] == count and
            transfer["retransmitFrames"] == 0, "incomplete/duplicate DATA coverage")
    require(all(transfer["acks"][key] == 0 for key in ("duplicate", "error", "malformed", "noProgress", "abort")),
            "not a clean transfer")
    require(len(chunks) == batch["chunks"] and sum(c["bytes"] for c in chunks) == batch["bytes"] == total + count * 14,
            "batch byte/count mismatch")
    require(len(writes) == gatt["calls"] and gatt["errors"] == 0 and
            sum(w["bytes"] for w in writes) == gatt["bytes"], "write count/bytes mismatch")
    controls = [w["bytes"] for w in writes if not w["assigned"]]
    require(controls.count(111) == controls.count(42) == 1 and
            all(size in (10, 111, 42) for size in controls),
            "unexpected control writes; this analysis requires unsplit clean controls")
    start, end, elapsed = transfer["startUs"], transfer["endAckUs"], transfer["elapsedUs"]
    require(type(start) is int and type(end) is int and elapsed == end - start > 0 and
            all(start <= c["at"] <= end for c in chunks) and
            [c["at"] for c in chunks] == sorted(c["at"] for c in chunks), "invalid monotonic timing")
    data_us = sum(c["us"] for c in chunks)
    require(0 <= data_us <= elapsed, "write times exceed transfer interval")
    return dict(result="BATCH_TIMING_OBSERVED", transfer_seconds=elapsed / 1e6,
                throughput_kib_s=total / 1024 / (elapsed / 1e6), data_gatt_seconds=data_us / 1e6,
                remaining_transfer_seconds=(elapsed - data_us) / 1e6,
                chunks=len(chunks), data_frames=count,
                ack_sample_integrity=transfer["ackSamples"], ack_early_invalid=transfer["ackEarlyInvalid"],
                scope="App clock only; remainder is not isolated ACK/flash cost; no independent acceptance",
                device_operations=0)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", required=True, type=Path)
    parser.add_argument("--expect-sentinel", required=True)
    parser.add_argument("--expect-target", required=True)
    args = parser.parse_args()
    require(args.input.stat().st_size <= MAX_BYTES + 8192, "oversized snapshot")
    envelope, messages = verify(args.input.read_bytes(), sentinel=args.expect_sentinel,
                                target=args.expect_target)
    require(envelope["outcome"] == "completed", "completed original snapshot required")
    stamps = [json.loads(m[len("OTA_EXPERIMENT "):]) for m in messages if m.startswith("OTA_EXPERIMENT ")]
    require(len(stamps) == 1 and stamps[0]["schema"] == 5 and stamps[0]["dataBatchFrames"] == 3,
            "batch experiment stamp required")
    require(stamps[0]["packageBytes"] == envelope["input"]["packageBytes"] and
            stamps[0]["packageSha256"] == envelope["input"]["packageSha256"], "package stamp mismatch")
    result = analyze(messages, envelope["input"]["packageBytes"])
    result["snapshot_sha256"] = envelope["rawSha256"]
    print(json.dumps(result))


if __name__ == "__main__":
    main()
