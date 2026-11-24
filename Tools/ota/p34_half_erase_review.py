"""Compare the declared batch12 half-erase screen from original closed trials."""
import argparse
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "Tools/ota"))
import p34_receiver_review as receiver
import p34_full_trace as trace
import p34_install_cost as cost

cli = receiver.cli
AREA = ROOT / ".cache/p34-half-erase"
TRIALS = dict(control=ROOT / ".cache/p34-pump-batch12/trials/measure",
              bootstrap=AREA / "trials/bootstrap", measure=AREA / "trials/measure")
POLICY = dict(receiver.staging.POLICY, dataBatchFrames=12)


def parse_costs(texts):
    phases = {}
    for text in texts:
        lines = text.splitlines()
        headers = [i for i, line in enumerate(lines) if line.startswith("P34COST:")]
        cli.require(sum(line.startswith("P34COST") for line in lines) == len(headers) * 8,
                    "orphan/truncated installation cost rows")
        for index in headers:
            value = cost.parse_one("\n".join(lines[index:index + 8]))
            cli.require(value["success"] and value["phase"] not in phases,
                        "failed or duplicate installation phase")
            phases[value["phase"]] = value
    cli.require(set(phases) == {"full", "backup"}, "both original installation phases required")
    return phases


def installation_costs(s, row):
    records = []
    def original(item):
        cli.require(cli.record(s.checked(item["path"])) == item, "original native cost input changed")
        records.append(item)
        return Path(item["path"]).read_bytes()
    report = json.loads(original(row["report"]))
    native = json.loads(original(report["native_trace"]["original"]))
    inp = row["input"]
    cli.require(native["result"] == "TRACE_CLOSED" and native["reader_closed"] is True and
                native["receiver"] == inp["currentVersionCode"] and native["target"] == inp["targetVersionCode"] and
                native["package"]["sha256"] == inp["packageSha256"] and
                native["package"]["bytes"] == inp["packageBytes"], "native installation binding differs")
    texts = [original(channel["raw"]).decode("ascii") for channel in native["channels"]
             if channel["version"] == inp["currentVersionCode"]]
    if native["retained_tail"]:
        tail = json.loads(original(native["retained_tail"]))
        values = {key: original(item) for key, item in tail["files"].items()}
        pending, descriptor = trace.ring_tail(values["header"], values["descriptor"], values["ring"])
        cli.require(pending == values["pending"] and descriptor == tail["descriptor"] and
                    tail["consumed"] is False and tail["receiver"] == inp["currentVersionCode"],
                    "retained RTT cost evidence differs")
        # Same descriptor-bound partial/pending reconstruction as the original analyzer.
        texts.append((values["partial"] + pending).decode("ascii"))
    phases = parse_costs(texts)
    expected = (18, 19) if inp["currentVersionCode"] == 30265 else (32, 33)
    observed = tuple(phases[name]["ports"]["erase"]["calls"] for name in ("full", "backup"))
    extent = tuple(phases[name]["ports"]["erase"]["bytes"] for name in ("full", "backup"))
    return dict(phases=phases, inputs=records, expected_erase_calls=expected,
                erase_command_plan_observed=observed == expected and extent == (622592, 626688),
                clock="MCU millis ticks, not calibrated App wall seconds")


def compare(rows):
    cli.require(set(rows) == set(TRIALS), "complete half-erase matrix required")
    ordered = [rows[name] for name in TRIALS]
    for index, row in enumerate(ordered):
        inp = row["input"]
        versions = [inp[k] for k in ("currentVersionCode", "targetVersionCode")]
        cli.require(all(type(v) is int for v in versions) and
                    versions == [30263 + index, 30264 + index], "wrong half-erase role/version")
        cli.require(row["policy"] == POLICY and row["binding"] ==
                    dict(writeMode="without", mtuChunkBytes=244, mtuSource="negotiated"),
                    "half-erase link policy differs")
        cli.require(row["header_only"] is (index != 1) and inp["appLifecycle"] == "resumed",
                    "bootstrap/header-only workload or lifecycle differs")
        cli.require(type(inp["packageBytes"]) is int and 0 < inp["packageBytes"] <= 1048576,
                    "invalid complete package size")
        for key in ("currentImageSha256", "targetImageSha256", "packageSha256"):
            value = inp[key]
            cli.require(isinstance(value, str) and len(value) == 64 and
                        all(c in "0123456789abcdef" for c in value), "invalid image/package identity")
        cli.require(inp["currentImageSha256"] != inp["targetImageSha256"], "unchanged successor image")
        for key in ("transfer_seconds", "installation_reconnect_seconds"):
            cli.require(receiver.positive(row[key]), "invalid App timing")
    for key in ("apk_sha256", "boot_sha256"):
        cli.require(len({row[key] for row in ordered}) == 1, "APK/Boot changed")
    cli.require(len({row["input"]["deviceAddress"].lower() for row in ordered}) == 1, "device changed")
    cli.require(len({row["input"]["packageSha256"] for row in ordered}) == 3, "package replay")
    for before, after in zip(ordered, ordered[1:]):
        cli.require(before["input"]["targetImageSha256"] == after["input"]["currentImageSha256"],
                    "actual predecessor identity is discontinuous")
    control, _, measure = ordered
    old_rate = control["input"]["packageBytes"] / 1000 / control["transfer_seconds"]
    new_rate = measure["input"]["packageBytes"] / 1000 / measure["transfer_seconds"]
    transfer_saved = control["transfer_seconds"] - measure["transfer_seconds"]
    install_saved = control["installation_reconnect_seconds"] - measure["installation_reconnect_seconds"]
    return dict(control_kb_s=old_rate, measure_kb_s=new_rate,
        throughput_gain_percent=(new_rate / old_rate - 1) * 100,
        transfer_seconds_saved=transfer_saved, installation_reconnect_seconds_saved=install_saved,
        transfer_plus_install_seconds_saved=transfer_saved + install_saved,
        useful_installation_screening_gain=install_saved > 0,
        whole_upgrade_screening_gain=transfer_saved + install_saved > 0,
        transfer_target_met=new_rate >= 50, installation_target_met=measure["installation_reconnect_seconds"] <= 20,
        strict_same_package_ab=False, independent_acceptance=False,
        scope="One sequential legal FULL sample per role; control/measure are header-only. "
              "Changed-executable bootstrap is preserved but excluded from gain calculations. "
              "App transfer and END-to-target are disjoint; native ticks/ACK/GATT are not added. "
              "Not repeatability or reference-size reliability. Erase command evidence is reported separately.")


if __name__ == "__main__":
    cli.require(Path.cwd() == ROOT and sys.flags.isolated and sys.flags.no_site and sys.dont_write_bytecode,
                "explicit isolated root required")
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--out", type=Path, required=True)
    args = p.parse_args()
    s = cli.Store(ROOT)
    out = s.checked(args.out)
    cli.require(not out.exists(), "preserve prior comparison")
    rows = {name: receiver.sample(s, root) for name, root in TRIALS.items()}
    costs = {name: installation_costs(s, row) for name, row in rows.items()}
    value = dict(result="HALF_ERASE_SCREEN_REVIEWED", source=cli.record(__file__),
        dependencies=[cli.record(m.__file__) for m in (receiver, receiver.staging, receiver.staging.review,
                                                       receiver.staging.timing, trace, cost)],
        device_operations=0, samples=rows, installation_costs=costs,
        erase_command_plan_observed=all(v["erase_command_plan_observed"] for v in costs.values()),
        comparison=compare(rows))
    s.write(out, value)
    print(json.dumps(value["comparison"]))
