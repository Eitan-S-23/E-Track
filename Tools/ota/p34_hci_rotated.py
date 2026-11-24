"""Join immutable HCI rotations and bound OTA timing to first target identity."""
import argparse
import hashlib
import json
from pathlib import Path
import struct
import sys

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "Tools/ota"))
import p34_hci_trial as trial

cli, original = trial.cli, trial.previous


def records(raw):
    at, result = 16, []
    while at < len(raw):
        cli.require(at + 24 <= len(raw), "short HCI record")
        _, length, _, _, stamp = struct.unpack_from(">IIIIQ", raw, at)
        at += 24 + length
        cli.require(at <= len(raw), "partial HCI packet")
        result.append((stamp, at))
    cli.require(result and all(a[0] <= b[0] for a, b in zip(result, result[1:])), "invalid HCI record clock")
    return result


def join(parts):
    cli.require(1 <= len(parts) <= 8 and len({hashlib.sha256(p).digest() for p in parts}) == len(parts),
                "unique bounded capture parts required")
    values = []
    for raw in parts:
        summary = original.att.EXPORT.snoop_summary(raw)
        cli.require(summary["truncated_packets"] == summary["reported_drops"] == 0,
                    "lossy capture cannot be joined for timing")
        rows = records(raw)
        values.append((rows[0][0], rows[-1][0], raw))
    values.sort(key=lambda v: v[0])
    cli.require(len({v[2][:16] for v in values}) == 1 and all(a[1] < b[0] for a, b in zip(values, values[1:])),
                "incompatible or overlapping rotations; never deduplicate/sort packets")
    return values[0][2] + b"".join(v[2][16:] for v in values[1:])


def analyze(raw, package, expected):
    decoded = original.att.analyze(raw, expected["deviceAddress"])
    begins, ends, identities, all_begins = [], [], [], []
    for connection in decoded["connections"]:
        rows = [r for r in decoded["att"] if r["generation"] == connection["generation"]]
        if not rows:
            continue
        tx, rx = original.declarations(rows)
        for direction, handle in (("tx", tx), ("rx", rx)):
            frames = original.frames([r for r in rows if r["direction"] == direction and r.get("value_handle") == handle])
            for frame in frames:
                payload = frame["payload"]
                if direction == "tx" and frame["command"] == 1:
                    cli.require(len(payload) == 101, "invalid BEGIN")
                    all_begins.append(dict(record=frame["start_record"], generation=connection["generation"],
                                           package_sha256=payload[5:37].hex()))
                    if payload[5:37].hex() == expected["packageSha256"]:
                        begins.append(dict(frame, generation=connection["generation"],
                                           connection_start_record=connection["start_record"]))
                if direction == "rx" and frame["command"] == 0x83:
                    ends.append(dict(frame, generation=connection["generation"]))
                if direction == "rx" and frame["command"] == 0x80:
                    cli.require(len(payload) == 50, "invalid INFO")
                    identities.append(dict(record=frame["end_record"], version=int.from_bytes(payload[12:16], "little"),
                        sha256=payload[16:48].hex(), generation=connection["generation"]))
    cli.require(len(begins) == 1, "one exact package BEGIN required")
    begin = begins[0]
    ends = [f for f in ends if f["generation"] == begin["generation"] and f["start_record"] > begin["end_record"]]
    cli.require(len(ends) == 1, "one END ACK required")
    targets = [v for v in identities if v["record"] > ends[0]["end_record"] and
               v["version"] == expected["targetVersionCode"] and v["sha256"] == expected["targetImageSha256"]]
    cli.require(targets, "post-END target identity missing")
    cutoff = min(v["record"] for v in targets)
    index = records(raw)
    earlier = [v for v in all_begins if v["record"] < begin["start_record"] and
               v["package_sha256"] != expected["packageSha256"]]
    first = begin["connection_start_record"] if earlier else 1
    start = index[first - 2][1] if first > 1 else 16
    prefix = raw[:16] + raw[start:index[cutoff - 1][1]]
    # No timestamps or packets are edited. The original strict verifier must
    # still prove every DATA/ACK/package byte and both old/new image identities.
    verified = trial.analyze(prefix, package, expected)
    verified.update(analysis_range=dict(first_record=first, last_record=cutoff, original_records=len(index),
        prefix_bytes=len(prefix), original_bytes=len(raw),
        derived_record_offset=first - 1,
        reason="Select the complete exact-package connection through first target INFO; earlier upgrades and later queries stay in originals"),
        all_original_begins=all_begins, earlier_unrelated_upgrades=earlier,
        all_original_identities=identities, later_target_queries=[v for v in targets if v["record"] > cutoff])
    return verified, prefix


if __name__ == "__main__":
    cli.require(Path.cwd() == ROOT and sys.flags.isolated and sys.flags.no_site and sys.dont_write_bytecode,
                "explicit isolated root required")
    p = argparse.ArgumentParser(description=__doc__)
    for name in ("archive", "trial", "out"): p.add_argument("--" + name, type=Path, required=True)
    a = p.parse_args()
    s = cli.Store(ROOT)
    out = s.checked(a.out)
    cli.require(not out.exists(), "preserve previous correlation")
    for leaf in ("joined.btsnoop", "analysis-range.btsnoop", "result.json"): s.checked(out / leaf)
    pointer, report = trial.review.load_report(s, s.checked(a.trial))
    archive = s.read(s.checked(a.archive))
    originals = [v["original"] for v in archive["extracted"]]
    for item in originals: cli.require(cli.record(s.checked(item["path"])) == item, "rotated original changed")
    raw = join([Path(v["path"]).read_bytes() for v in originals])
    package = report["inputs"]["download"]
    value, prefix = analyze(raw, Path(package["path"]).read_bytes(), report["summary"]["input"])
    value.update(report=pointer, archive=cli.record(a.archive), package=package,
        hci=s.raw(out / "analysis-range.btsnoop", prefix), joined=s.raw(out / "joined.btsnoop", raw),
        rotated_originals=originals, derived_capture=True, device_operations=0,
        sources=[cli.record(m.__file__) for m in (trial, original, original.att, original.compare)], source=cli.record(__file__))
    s.write(out / "result.json", value)
    print(json.dumps({k: v for k, v in value.items() if k not in ("block_timing", "identities", "all_original_identities")}))
