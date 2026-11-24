"""Classify original HCI durable tails, without equating them to Flash time."""
import argparse
import json
import math
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "Tools/ota"))
import p34_hci_queue as queue

cli = queue.cli
FIELDS = ("tail_ms", "controller_report_ms", "after_controller_report_ms")


def summarize(blocks):
    cli.require(bool(blocks), "complete nonempty block set required")
    groups = {name: [] for name in ("boundary_64k", "ordinary_full", "partial_final")}
    previous = 0
    for index, block in enumerate(blocks):
        durable = block["durable"]
        cli.require(type(durable) is int and type(block["block"]) is int and
                    block["block"] == index and 0 < durable - previous <= 4096,
                    "noncontiguous durable blocks")
        partial = durable - previous < 4096
        cli.require(not partial or index == len(blocks) - 1, "nonfinal partial block")
        for key in FIELDS:
            value = block[key]
            cli.require(type(value) in (int, float) and math.isfinite(value),
                        "invalid HCI duration")
        cli.require(block["tail_ms"] >= 0 and block["controller_report_ms"] >= 0 and
                    math.isclose(block["tail_ms"], block["controller_report_ms"] +
                                 block["after_controller_report_ms"], abs_tol=1e-6),
                    "tail partition does not close")
        # A delayed completion report may arrive AFTER the durable ACK. Preserve
        # that signed observation, rather than manufacturing a Flash duration.
        category = "partial_final" if partial else (
            "boundary_64k" if durable % 65536 == 0 else "ordinary_full")
        groups[category].append(block)
        previous = durable
    result = {}
    for name, rows in groups.items():
        tails = sorted(row["tail_ms"] for row in rows)
        result[name] = dict(count=len(rows),
            totals_ms={key: sum(row[key] for row in rows) for key in FIELDS},
            median_tail_ms=(tails[(len(tails)-1)//2] + tails[len(tails)//2])/2 if tails else None,
            negative_after_report_count=sum(row["after_controller_report_ms"] < 0 for row in rows))
    return dict(groups=result, totals_ms={key: sum(b[key] for b in blocks) for key in FIELDS},
        longest_blocks=sorted(blocks, key=lambda b: b["tail_ms"], reverse=True)[:8],
        scope="64KiB denotes durable payload boundaries, not observed erase commands. "
              "Controller reports include notification latency. Signed after-report spans "
              "are retained and are not isolated MCU processing or Flash durations.")


def run(correlation_path, output):
    store = cli.Store(ROOT)
    output = store.checked(output)
    cli.require(not output.exists(), "preserve prior tail analysis")
    correlation_path = store.checked(correlation_path)
    correlated = store.read(correlation_path)
    for name in ("hci", "report", "package", "archive"):
        queue.verify_record(store, correlated[name])
    report = store.read(correlated["report"]["path"])
    verified = queue.trial.analyze(Path(correlated["hci"]["path"]).read_bytes(),
        Path(correlated["package"]["path"]).read_bytes(), report["summary"]["input"])
    cli.require(all(correlated.get(key) == value for key, value in verified.items()),
                "correlation differs from original inputs")
    value = summarize(verified["block_timing"]["blocks"])
    value.update(result="HCI_DURABLE_TAIL_CLASSIFIED", device_operations=0,
        measured_speedup=False, correlation=cli.record(correlation_path),
        source=cli.record(__file__), dependencies=[cli.record(m.__file__) for m in
            (queue, queue.trial, queue.original, queue.original.att, queue.original.compare)])
    store.write(output, value)
    print(json.dumps({key: value[key] for key in ("result", "groups", "totals_ms")}))


if __name__ == "__main__":
    cli.require(Path.cwd() == ROOT and sys.flags.isolated and sys.flags.no_site and
                sys.dont_write_bytecode, "explicit isolated project root required")
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--correlation", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    run(args.correlation, args.out)
