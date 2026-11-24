"""Offline DATA queue accounting using original HCI completion reports."""
import argparse
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "Tools/ota"))
import p34_hci_trial as trial

cli, original = trial.cli, trial.previous


def verify_record(store, item):
    path = store.checked(item["path"])
    cli.require(cli.record(path) == dict(item, path=str(path)), "correlation input changed")
    return path


def queue_events(writes, completed):
    cli.require(writes and len({r["end_record"] for r in writes}) == len(writes), "unique DATA packets required")
    events = []
    for row in writes:
        record = row["end_record"]
        cli.require(row["start_record"] == record and row["start_timestamp"] == row["end_timestamp"],
                    "fragmented HCI DATA requires explicit multi-ACL accounting")
        cli.require(record in completed, "DATA completion report missing")
        done = completed[record]
        cli.require(done["record"] > record and done["timestamp"] >= row["start_timestamp"],
                    "completion precedes DATA")
        events.extend([(record, row["start_timestamp"], 1), (done["record"], done["timestamp"], -1)])
    events.sort()
    cli.require(all(a[1] <= b[1] for a, b in zip(events, events[1:])), "HCI clock moved backwards")
    count = 0
    for _, _, delta in events:
        count += delta
        cli.require(count >= 0, "negative DATA queue")
    cli.require(count == 0, "DATA queue never closes")
    return events


def span(events, first, last):
    cli.require(type(first) is int and type(last) is int and first <= last, "invalid queue time range")
    count, peak, empty, occupied, cursor = 0, 0, 0, 0, first
    for _, stamp, delta in events:
        if stamp > last:
            break
        if stamp >= first:
            elapsed = stamp - cursor
            if count == 0: empty += elapsed
            else: occupied += elapsed
            cursor = stamp
        count += delta
        peak = count if stamp < first else max(peak, count)
    if count == 0: empty += last - cursor
    else: occupied += last - cursor
    cli.require(empty >= 0 and occupied >= 0 and empty + occupied == last - first, "queue partition does not close")
    return dict(span_us=last - first, no_reported_outstanding_data_us=empty,
                reported_outstanding_data_us=occupied, peak_reported_outstanding_data=peak)


def analyze(raw, correlated, peer):
    cli.require(correlated["result"] == "ORIGINAL_OTA_HCI_CORRELATED", "complete correlation required")
    decoded = original.att.analyze(raw, peer)
    generation = correlated["generation"]
    connections = [c for c in decoded["connections"] if c["generation"] == generation]
    cli.require(len(connections) == 1, "correlated connection missing")
    connection = dict(connections[0], end_record=connections[0].get("end_record", decoded["capture"]["packets"]))
    rows = [r for r in decoded["att"] if r["generation"] == generation and
            r["direction"] == "tx" and r.get("value_handle") == correlated["tx_handle"]]
    frames = [f for f in original.frames(rows) if f["command"] == 2]
    cli.require(len(frames) == correlated["data_frames"], "DATA frame count differs")
    writes = [r for r in rows if frames[0]["start_record"] <= r["start_record"] <= frames[-1]["end_record"]]
    cli.require(len(writes) == correlated["data_att_chunks"], "DATA packet count differs")
    completed = original.completions(raw, connection)
    events = queue_events(writes, completed)
    blocks = []
    for offset in range(0, len(frames), 32):
        first, last = frames[offset], frames[min(offset + 31, len(frames) - 1)]
        blocks.append(dict(block=offset // 32, first_record=first["start_record"], last_record=last["end_record"],
            **span(events, first["start_timestamp"], last["end_timestamp"])))
    totals = {k: sum(row[k] for row in blocks) for k in (
        "span_us", "no_reported_outstanding_data_us", "reported_outstanding_data_us")}
    cli.require(abs(totals["span_us"] / 1000 - correlated["block_timing"]["totals"]["send_ms"]) < 1e-6,
                "feeding intervals differ from original block accounting")
    return dict(result="HCI_DATA_QUEUE_ACCOUNTED", generation=generation, data_att_chunks=len(writes),
        blocks=blocks, totals=totals,
        peak_reported_outstanding_data=max(row["peak_reported_outstanding_data"] for row in blocks),
        scope="Only original target DATA ACL packets; no Android queue capacity assumption. "
              "Intervals run from first to last DATA write in each durable block, excluding durable tails. "
              "Completion reports include reporting latency: outstanding is not radio airtime or proof of buffer fullness. "
              "Empty intervals can include credit/callback/scheduling waits; they do not alone prove a Flutter bottleneck.")


if __name__ == "__main__":
    cli.require(Path.cwd() == ROOT and sys.flags.isolated and sys.flags.no_site and sys.dont_write_bytecode,
                "explicit isolated root required")
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--correlation", type=Path, required=True)
    p.add_argument("--out", type=Path, required=True)
    a = p.parse_args()
    s = cli.Store(ROOT)
    output = s.checked(a.out)
    cli.require(not output.exists(), "preserve previous queue accounting")
    correlation = s.read(s.checked(a.correlation))
    for item in (correlation["hci"], correlation["report"], correlation["package"], correlation["archive"]):
        verify_record(s, item)
    report = s.read(correlation["report"]["path"])
    raw = Path(correlation["hci"]["path"]).read_bytes()
    package = Path(correlation["package"]["path"]).read_bytes()
    verified = trial.analyze(raw, package, report["summary"]["input"])
    cli.require(all(correlation[k] == v for k, v in verified.items()), "correlation no longer matches originals")
    result = analyze(raw, correlation, report["summary"]["input"]["deviceAddress"])
    result.update(correlation=cli.record(s.checked(a.correlation)), hci=correlation["hci"], device_operations=0,
        sources=[cli.record(m.__file__) for m in (trial, original, original.att, original.compare)], source=cli.record(__file__))
    s.write(output, result)
    print(json.dumps({k: v for k, v in result.items() if k != "blocks"}))
