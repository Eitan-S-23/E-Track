"""Account for batched DATA timing from original App logs, without device work."""
import argparse
from bisect import bisect_right
import json
from pathlib import Path
import re
import sys


def require(value, message):
    if not value:
        raise ValueError(message)


def analyze(messages, total):
    require(type(total) is int and 0 < total <= 1048576, "invalid package size")
    offsets = list(range(0, total, 128))
    lengths = [min(128, total - off) for off in offsets]
    ends, wire = [], 0
    for length in lengths:
        wire += length + 14
        ends.append(wire)
    writes, chunks, segments, durable, summaries = [], [], [], [], []
    acks = {}
    platform = last = None
    wire_done = pending = 0
    for line in messages.splitlines():
        if line.startswith("OTA_LINK_STATS "):
            value = json.loads(line.removeprefix("OTA_LINK_STATS "))
            if value["label"] == "upgrade":
                summaries.append(value)
        match = re.fullmatch(r"OTA_LINK_SAMPLE label=upgrade kind=(\w+) us=(\d+)(.*)", line)
        if not match:
            require(not line.startswith("OTA_LINK_SAMPLE label=upgrade "), "malformed sample")
            continue
        kind, stamp = match[1], int(match[2])
        fields = match[3].split()
        require(all(re.fullmatch(r"\w+=\d+", f) for f in fields), "malformed sample fields")
        extra = {k: int(v) for k, v in (f.split("=") for f in fields)}
        require(len(extra) == len(fields) and not extra.get("error"), "duplicate field or write error")
        if kind == "platform_write":
            require(platform is None and pending == 0, "unpaired platform write or frame completion")
            platform = dict(us=stamp, bytes=extra["bytes"])
        elif kind == "gatt_write":
            require(platform is not None and 0 < platform["us"] <= stamp and
                    platform["bytes"] == extra["bytes"], "platform/GATT pairing differs")
            last = dict(gatt_us=stamp, platform_us=platform["us"], bytes=extra["bytes"], assigned=False)
            writes.append(last)
            platform = None
        elif kind == "batch_chunk":
            require(last is not None and not last["assigned"] and platform is None and pending == 0 and
                    0 < extra["bytes"] == last["bytes"] and len(segments) < len(offsets), "chunk/write pairing differs")
            block = len(segments) // 32
            wire_done += extra["bytes"]
            completed = bisect_right(ends, wire_done)
            pending = completed - len(segments)
            require(wire_done <= ends[min((block + 1) * 32, len(ends)) - 1] and
                    pending == extra["frames"], "chunk crosses block or frame geometry differs")
            require(not chunks or stamp > chunks[-1]["end_us"], "chunk clock moved backwards")
            last["assigned"] = True
            chunks.append(dict(last, end_us=stamp, block=block, frames=pending))
        elif kind == "segment_first_send":
            index = len(segments)
            require(pending > 0 and index < len(offsets) and extra["off"] == offsets[index] and
                    extra["len"] == lengths[index] and stamp >= chunks[-1]["end_us"], "frame completion differs")
            require(not segments or stamp >= segments[-1]["end_us"], "segment clock moved backwards")
            segments.append(dict(off=extra["off"], end_us=stamp))
            pending -= 1
        elif kind == "ack_latency":
            require(extra["off"] not in acks, "duplicate ACK sample")
            acks[extra["off"]] = stamp
        elif kind == "durable":
            durable.append(dict(off=extra["off"], us=stamp))
        elif kind == "segment_retransmit":
            raise ValueError("retransmission is outside this clean-run accounting")
        else:
            require(kind in ("discover", "get_info"), "unsupported upgrade sample")
    require(len(summaries) == 1 and platform is None and pending == 0, "incomplete upgrade")
    summary = summaries[0]
    transfer = summary["transfer"]
    require(summary["clock"] == "stopwatch-mono-us" and transfer["outcome"] == "ok" and
            transfer["elapsedUs"] == transfer["endAckUs"] - transfer["startUs"] > 0 and
            transfer["segmentsUnique"] == transfer["segmentSendTotal"] == len(offsets) and
            transfer["retransmitFrames"] == transfer["ackEarlyInvalid"] == transfer["ackEarlyUnsent"] == 0 and
            transfer["ackSamples"] == "complete", "invalid transfer/ACK summary")
    require(transfer["acks"]["ok"] == len(offsets) and all(transfer["acks"][k] == 0 for k in
            ("duplicate", "error", "malformed", "noProgress", "abort")), "unclean ACK summary")
    batch = transfer["dataBatch"]
    require(batch["schema"] == 1 and batch["chunks"] == len(chunks) and
            batch["bytes"] == wire_done == wire and len(segments) == len(offsets) and set(acks) == set(offsets),
            "DATA coverage/count differs")
    require(len(writes) == summary["gattWrites"]["calls"] == summary["platformWrites"]["calls"] and
            sum(x["bytes"] for x in writes) == summary["gattWrites"]["bytes"] == summary["platformWrites"]["bytes"] and
            summary["gattWrites"]["errors"] == summary["platformWrites"]["errors"] == 0 and
            [x["bytes"] for x in writes if not x["assigned"]] == [10, 111, 42], "control/write coverage differs")
    require([x["off"] for x in durable] == [*range(0, total, 4096), total] and
            transfer["durable"]["events"] == len(durable) and transfer["durable"]["finalOff"] == total,
            "durable coverage differs")
    blocks = []
    for index, (before, after) in enumerate(zip(durable, durable[1:])):
        points = [x for x in chunks if x["block"] == index]
        require(points and before["us"] <= points[0]["end_us"] <= points[-1]["end_us"] <= after["us"],
                "chunk outside durable block")
        for segment in segments[index * 32:(index + 1) * 32]:
            require(before["us"] <= segment["end_us"] <= segment["end_us"] + acks[segment["off"]] <= after["us"],
                    "segment or ACK outside durable block")
        gatt = sum(x["gatt_us"] for x in points)
        row = dict(index=index, span_us=after["us"] - before["us"], data_gatt_us=gatt,
            before_last_chunk_nonwrite_us=points[-1]["end_us"] - before["us"] - gatt,
            last_chunk_to_durable_us=after["us"] - points[-1]["end_us"])
        require(all(v >= 0 for v in row.values()), "negative block accounting")
        blocks.append(row)
    partition = {k: sum(x[k] for x in blocks) for k in
                 ("data_gatt_us", "before_last_chunk_nonwrite_us", "last_chunk_to_durable_us")}
    partition.update(begin_to_zero_durable_us=durable[0]["us"] - transfer["startUs"],
                     final_durable_to_end_ack_us=transfer["endAckUs"] - durable[-1]["us"])
    require(all(v >= 0 for v in partition.values()) and sum(partition.values()) == transfer["elapsedUs"],
            "transfer accounting does not close")
    platform_us = sum(x["platform_us"] for x in chunks)
    wrapper_us = partition["data_gatt_us"] - platform_us
    return dict(transfer_partition_us=partition, total_us=transfer["elapsedUs"], blocks=blocks,
        data_chunks=len(chunks), data_segments=len(segments), data_wire_bytes=wire,
        nested_data_platform_us=platform_us, nested_service_wrapper_us=wrapper_us,
        target_50kb_s_budget_us=total * 20,
        platform_alone_exceeds_target_budget=platform_us > total * 20,
        scope="App-clock accounting, not isolated physical costs. Platform/wrapper are nested in GATT; "
              "nonwrite includes scheduling/credit; durable tail is not isolated Flash. No speed prediction.")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--trial", required=True, type=Path)
    parser.add_argument("--out", required=True, type=Path)
    args = parser.parse_args()
    root = Path(__file__).resolve().parents[2]
    require(Path.cwd() == root and sys.flags.isolated and sys.flags.no_site and sys.dont_write_bytecode,
            "explicit isolated project root required")
    sys.path.insert(0, str(root / "Tools/ota"))
    import p34_batch_review as review
    store = review.cli.Store(root)
    output = store.checked(args.out)
    require(not output.exists(), "preserve previous analysis")
    pointer, report = review.load_report(store, store.checked(args.trial))
    raw = Path(report["inputs"]["snapshot"]["path"]).read_text(encoding="utf-8")
    rows = [json.loads(line) for line in raw.splitlines()]
    messages = "\n".join(x["message"] for x in rows if x.get("kind") == "line")
    value = analyze(messages, report["summary"]["input"]["packageBytes"])
    value.update(result="BATCH_TIMING_ACCOUNTED", report=pointer, inputs=report["inputs"],
                 source=review.cli.record(__file__), device_operations=0, measured_speedup=False)
    store.write(output, value)
    print(json.dumps({k: v for k, v in value.items() if k not in ("blocks", "inputs")}))


if __name__ == "__main__":
    main()
