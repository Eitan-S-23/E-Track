"""Compare a sequential receiver control/bootstrap/measurement without device I/O."""
import argparse
import json
import math
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "Tools/ota"))
import p34_staging_erase_review as staging

cli = staging.cli


def positive(value):
    return type(value) in (int, float) and math.isfinite(value) and value > 0


def pump_profile(native):
    cli.require(native["clean_counters"] is True and native["clock_ok"] == 1,
                "unclean native profile")
    hz, entries = native["clock_hz"], native["pump_entries"]
    cli.require(type(hz) is int and hz > 0 and type(entries) is int and entries > 1,
                "invalid pump clock/count")
    values = [native[k] for k in ("pump_gap_cycles_lo", "pump_gap_cycles_hi", "pump_gap_max_cycles")]
    cli.require(all(type(x) is int and 0 <= x <= 0xffffffff for x in values),
                "invalid pump cycle words")
    lo, hi, maximum = values
    cycles = (hi << 32) | lo
    cli.require(0 < maximum <= cycles <= maximum * entries, "invalid pump gap total")
    work = native["phases"]["pump_work"]
    # BEGIN may activate profiling inside a pump: its work counts, its entry does not.
    cli.require(type(work["calls"]) is int and work["calls"] in (entries, entries + 1)
                and work["errors"] == 0 and positive(work["seconds"]),
                "incomplete pump work samples")
    return dict(entries=entries, work_calls=work["calls"], work_seconds=work["seconds"], gap_seconds=cycles / hz,
                max_gap_seconds=maximum / hz, mean_gap_seconds=cycles / hz / entries,
                scope="One gap per active entry, first from profile activation; gaps include work. "
                      "BEGIN-in-pump can add one work call. Native and App clocks overlap.")


def sample(store, root):
    row = staging.sample(store, root)
    report = store.read(row["report"]["path"])
    before = report["before"]
    cli.require(cli.record(store.checked(before["path"])) == before, "receiver evidence changed")
    row["pump"] = pump_profile(report["native_trace"]["profile"])
    return row


def compare(rows):
    cli.require(set(rows) == {"control", "bootstrap", "measure"}, "complete receiver matrix required")
    ordered = [rows[name] for name in ("control", "bootstrap", "measure")]
    control, bootstrap, measure = ordered
    for row in ordered:
        inp = row["input"]
        versions = [inp[k] for k in ("currentVersionCode", "targetVersionCode")]
        cli.require(all(type(v) is int and 0 < v <= 2100000000 for v in versions)
                    and versions[1] == versions[0] + 1, "legal header successor required")
        cli.require(row["policy"] == staging.POLICY and row["binding"] ==
                    dict(writeMode="without", mtuChunkBytes=244, mtuSource="negotiated"),
                    "receiver comparison link policy differs")
        cli.require(inp["appLifecycle"] == "resumed", "foreground comparison required")
        cli.require(type(inp["packageBytes"]) is int and 0 < inp["packageBytes"] <= 1048576,
                    "invalid complete package size")
        for key in ("transfer_seconds", "installation_reconnect_seconds", "payload_erase_seconds"):
            cli.require(positive(row[key]), "invalid measurement")
        for key in ("currentImageSha256", "targetImageSha256"):
            value = inp[key]
            cli.require(isinstance(value, str) and len(value) == 64
                        and all(c in "0123456789abcdef" for c in value), "invalid raw image identity")
        cli.require(inp["currentImageSha256"] != inp["targetImageSha256"], "successor image unchanged")
    for key in ("apk_sha256", "boot_sha256"):
        cli.require(len({row[key] for row in ordered}) == 1, "APK/Boot changed")
    cli.require(len({row["input"]["deviceAddress"].lower() for row in ordered}) == 1, "device changed")
    cli.require(control["header_only"] is True and measure["header_only"] is True
                and bootstrap["header_only"] is False, "bootstrap and measurement workloads confused")
    for prior, following in zip(ordered, ordered[1:]):
        cli.require(prior["input"]["targetVersionCode"] == following["input"]["currentVersionCode"]
                    and prior["input"]["targetImageSha256"] == following["input"]["currentImageSha256"],
                    "actual predecessor identity is discontinuous")
    old_rate = control["input"]["packageBytes"] / 1000 / control["transfer_seconds"]
    new_rate = measure["input"]["packageBytes"] / 1000 / measure["transfer_seconds"]
    return dict(control_kb_s=old_rate, measure_kb_s=new_rate,
        throughput_gain_percent=(new_rate / old_rate - 1) * 100,
        transfer_seconds_saved=control["transfer_seconds"] - measure["transfer_seconds"],
        installation_reconnect_seconds_added=measure["installation_reconnect_seconds"] - control["installation_reconnect_seconds"],
        useful_transfer_screening_gain=new_rate > old_rate,
        transfer_target_met=new_rate >= 50,
        installation_target_met=measure["installation_reconnect_seconds"] <= 20,
        strict_same_package_ab=False, independent_acceptance=False,
        scope="One sample per role, sequential different legal FULL packages, not reference-size reliability. "
              "Bootstrap installs code and is not optimized reception. Native times are not additive App savings.")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ("control", "bootstrap", "measure", "out"):
        parser.add_argument("--" + name, type=Path, required=True)
    args = parser.parse_args()
    cli.require(Path.cwd() == ROOT and sys.flags.isolated and sys.flags.no_site and sys.dont_write_bytecode,
                "explicit isolated root required")
    store = cli.Store(ROOT)
    out = store.checked(args.out)
    cli.require(not out.exists(), "preserve prior comparison")
    rows = {name: sample(store, store.checked(getattr(args, name)))
            for name in ("control", "bootstrap", "measure")}
    value = dict(result="RECEIVER_SCREEN_REVIEWED", source=cli.record(__file__),
                 device_operations=0, samples=rows, comparison=compare(rows))
    store.write(out, value)
    print(json.dumps(value["comparison"]))


if __name__ == "__main__":
    main()
