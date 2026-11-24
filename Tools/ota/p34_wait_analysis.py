"""Partition original App timing without calling a device or mixing clocks."""
import argparse
import json
import math
from pathlib import Path
import re
import sys


def require(value, message):
    if not value:
        raise ValueError(message)


def metric(values):
    values = sorted(values)
    result = dict(count=len(values), sum_us=sum(values))
    for name, fraction in (("p50_us", .5), ("p95_us", .95), ("p99_us", .99)):
        result[name] = values[math.ceil(len(values) * fraction) - 1] if values else None
    result["max_us"] = max(values) if values else None
    return result


def infer_gap(previous_end, next_end, next_gatt, ack_times, window):
    require(type(window) is int and 1 <= window <= 32, "invalid window")
    outstanding = [stamp for stamp in ack_times if stamp > previous_end]
    require(len(outstanding) <= window and next_end > previous_end and next_gatt > 0, "invalid send/window")
    ready = min(outstanding) if len(outstanding) == window else previous_end
    nonwrite, after = next_end - previous_end - next_gatt, next_end - next_gatt - ready
    require(nonwrite >= 0 and after >= 0, "negative inferred timing; preserve original samples")
    return dict(outstanding=len(outstanding), nonwrite_us=nonwrite,
                credit_wait_est_us=ready - previous_end, after_credit_est_us=after)


def analyze(messages, total, window):
    require(type(total) is int and 0 < total <= 1048576, "invalid package length")
    require(type(window) is int and 1 <= window <= 32, "invalid window")
    data, acks, durable, writes, summaries = [], {}, [], [], []
    platform = last = None
    for number, line in enumerate(messages.splitlines(), 1):
        if line.startswith("OTA_LINK_STATS "):
            summary = json.loads(line.removeprefix("OTA_LINK_STATS "))
            if summary["label"] == "upgrade":
                summaries.append(summary)
        match = re.fullmatch(r"OTA_LINK_SAMPLE label=upgrade kind=(\w+) us=(\d+)(.*)", line)
        if not match:
            continue
        kind, us = match[1], int(match[2])
        extra = {key: int(value) for key, value in re.findall(r"(\w+)=(\d+)", match[3])}
        require(not extra.get("error"), "write error")
        if kind == "platform_write":
            require(platform is None, "unpaired platform write")
            platform = dict(us=us, bytes=extra["bytes"])
        elif kind == "gatt_write":
            require(platform and platform["bytes"] == extra["bytes"] and platform["us"] <= us,
                    "GATT/platform pairing differs")
            last = dict(gatt_us=us, platform_us=platform["us"], bytes=extra["bytes"], assigned=False)
            writes.append(last)
            platform = None
        elif kind == "segment_first_send":
            require(last and not last["assigned"] and last["bytes"] == extra["len"] + 14,
                    "DATA/write pairing differs")
            last["assigned"] = True
            data.append(dict(off=extra["off"], length=extra["len"], end_us=us,
                             gatt_us=last["gatt_us"], platform_us=last["platform_us"], line=number))
        elif kind == "segment_retransmit":
            raise ValueError("retransmission is outside this clean-run partition")
        elif kind == "ack_latency":
            require(extra["off"] not in acks, "duplicate ACK sample")
            acks[extra["off"]] = us
        elif kind == "durable":
            durable.append(dict(off=extra["off"], us=us))
    require(len(summaries) == 1 and platform is None, "one complete upgrade summary required")
    summary, count = summaries[0], (total + 127) // 128
    transfer = summary["transfer"]
    require(summary["clock"] == "stopwatch-mono-us" and transfer["outcome"] == "ok" and
            transfer["elapsedUs"] == transfer["endAckUs"] - transfer["startUs"] > 0 and
            transfer["segmentsUnique"] == transfer["segmentSendTotal"] == count and
            transfer["retransmitFrames"] == transfer["ackEarlyInvalid"] == transfer["ackEarlyUnsent"] == 0 and
            transfer["ackSamples"] == "complete", "invalid original timing/ACK summary")
    require(all(transfer["acks"][key] == 0 for key in ("duplicate", "error", "malformed", "noProgress", "abort")),
            "unclean ACK summary")
    require(len(writes) == summary["gattWrites"]["calls"] == summary["platformWrites"]["calls"] and
            len(writes) - len(data) == 3 and len(data) == len(acks) == count, "sample counts differ")
    require(sum(row["bytes"] for row in writes) == summary["gattWrites"]["bytes"] == summary["platformWrites"]["bytes"],
            "write bytes differ")
    require([row["off"] for row in data] == list(range(0, total, 128)) and
            set(acks) == {row["off"] for row in data} and
            all(row["length"] == min(128, total - row["off"]) for row in data), "DATA coverage differs")
    require([row["off"] for row in durable] == [*range(0, total, 4096), total], "durable coverage differs")
    for row in data:
        row["ack_at_us"] = row["end_us"] + acks[row["off"]]
    require(len({row["ack_at_us"] for row in data}) == transfer["acks"]["ok"], "ACK arrival groups differ")
    blocks, gaps = [], []
    for index, (before, after) in enumerate(zip(durable, durable[1:])):
        points = data[index * 32:(index + 1) * 32]
        require(all(before["us"] <= p["end_us"] <= p["ack_at_us"] <= after["us"] for p in points),
                "send or confirmation outside its block")
        local = [infer_gap(points[j - 1]["end_us"], points[j]["end_us"], points[j]["gatt_us"],
                           [p["ack_at_us"] for p in points[:j]], window) for j in range(1, len(points))]
        row = dict(index=index + 1, span_us=after["us"] - before["us"],
            gatt_us=sum(p["gatt_us"] for p in points),
            first_send_preparation_est_us=points[0]["end_us"] - before["us"] - points[0]["gatt_us"],
            last_send_to_durable_us=after["us"] - points[-1]["end_us"],
            credit_wait_est_us=sum(g["credit_wait_est_us"] for g in local),
            after_credit_est_us=sum(g["after_credit_est_us"] for g in local))
        require(all(value >= 0 for value in row.values()) and
                sum(row[key] for key in row if key not in ("index", "span_us")) == row["span_us"],
                "block partition does not close")
        blocks.append(row)
        gaps.extend(local)
    partition = {key: sum(row[key] for row in blocks) for key in blocks[0] if key not in ("index", "span_us")}
    partition.update(begin_to_zero_durable_us=durable[0]["us"] - transfer["startUs"],
                     final_durable_to_end_ack_us=transfer["endAckUs"] - durable[-1]["us"])
    require(all(value >= 0 for value in partition.values()) and sum(partition.values()) == transfer["elapsedUs"],
            "complete transfer partition does not close")
    return dict(transfer_partition_us=partition, total_us=transfer["elapsedUs"], blocks=blocks, window=window,
        data_segments=count, same_block_gaps=len(gaps), full_credit_gaps=sum(g["outstanding"] == window for g in gaps),
        after_credit_est=metric([g["after_credit_est_us"] for g in gaps]),
        scope="App-observable partition, not isolated physical costs; native clocks and overlapping sums are excluded")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", required=True, type=Path)
    parser.add_argument("--report", required=True, type=Path)
    parser.add_argument("--out", required=True, type=Path)
    args = parser.parse_args()
    root = Path(__file__).resolve().parents[2]
    require(args.root == root and Path.cwd() == root and sys.flags.isolated and sys.flags.no_site and sys.dont_write_bytecode,
            "explicit isolated project root required")
    sys.path.insert(0, str(Path(__file__).resolve().parent))
    import p34_session as cli
    store = cli.Store(root)
    output = store.checked(args.out)
    report = store.read(args.report)
    require(report["result"] == "FULL_INSTALL_VERIFIED", "verified original required")
    for key in ("snapshot", "plan"):
        require(cli.record(store.checked(report["inputs"][key]["path"])) == report["inputs"][key], "original input changed")
    plan = store.read(report["inputs"]["plan"]["path"])
    raw = Path(report["inputs"]["snapshot"]["path"]).read_text(encoding="utf-8")
    records = [json.loads(line) for line in raw.splitlines()]
    messages = "\n".join(item["message"] for item in records if item.get("kind") == "line")
    value = analyze(messages, plan["served"]["bytes"], plan["cells"][report["cell"]][1])
    value.update(original_report=cli.record(args.report), inputs=report["inputs"], source=cli.record(Path(__file__)), device_operations=0)
    store.write(output, value)
    print(json.dumps(dict(output=str(output), partition=value["transfer_partition_us"],
                         full_credit_gaps=value["full_credit_gaps"], after_credit_est=value["after_credit_est"])))


if __name__ == "__main__":
    main()
