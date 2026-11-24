"""Review closed PHY screening evidence without another device operation."""
import argparse
import json
from pathlib import Path
import re
import sys

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "Tools/ota"))
import p34_half_erase_review as half
import p34_phy_logfix_trial as phy

cli = half.cli
CURRENT = ROOT / ".cache/p34-phy-logfix/trials/prefer2m"
CONTROLS = dict(half_erase=half.TRIALS["measure"], batch12=half.TRIALS["control"])


def public_metrics(messages, total):
    cli.require(type(total) is int and 0 < total <= 1048576, "invalid package size")
    stamps = {}
    for name, suffix in (("BUDGET_START", r""), ("END_ACK_OK", r" durable=(\d+)"),
                         ("REBOOT_VERIFIED", r"")):
        pattern = r"^OTA_MONO MONO_" + name + r" monoUs=(\d+) wallUs=\d+" + suffix + r"\r?$"
        rows = re.findall(pattern, messages, re.M)
        cli.require(len(rows) == 1, "one original " + name + " marker required")
        if name == "END_ACK_OK":
            cli.require(int(rows[0][1]) == total, "incomplete durable END")
            stamps[name] = int(rows[0][0])
        else:
            stamps[name] = int(rows[0])
    start, end, reboot = (stamps[k] for k in ("BUDGET_START", "END_ACK_OK", "REBOOT_VERIFIED"))
    cli.require(0 <= start < end < reboot, "invalid public monotonic clock")
    transfer, install = (end - start) / 1e6, (reboot - end) / 1e6
    return dict(transfer_seconds=transfer, installation_reconnect_seconds=install,
        total_seconds=(reboot - start) / 1e6, throughput_kb_s=total / 1000 / transfer,
        package_bytes=total, boundary="OTA_MONO BUDGET_START / END_ACK_OK / REBOOT_VERIFIED",
        transfer_target_met=total * 20 >= end - start, installation_target_met=reboot - end <= 20000000)


def compare(before, after):
    saved = before["public"]["total_seconds"] - after["public"]["total_seconds"]
    return dict(throughput_gain_percent=(after["public"]["throughput_kb_s"] /
        before["public"]["throughput_kb_s"] - 1) * 100,
        transfer_seconds_saved=before["public"]["transfer_seconds"] - after["public"]["transfer_seconds"],
        installation_reconnect_seconds_saved=before["public"]["installation_reconnect_seconds"] -
            after["public"]["installation_reconnect_seconds"], total_seconds_saved=saved,
        whole_upgrade_screening_gain=saved > 0, strict_same_package_ab=False,
        apk_changed=before["apk_sha256"] != after["apk_sha256"],
        package_changed=before["input"]["packageSha256"] != after["input"]["packageSha256"],
        independent_acceptance=False, causal_phy_speedup_proven=False,
        scope="Historical sequential screening, not a matched PHY control or repeatability claim.")


def sample(store, root):
    # The inherited reader checks raw App/Boot identities and all three closures.
    row = half.receiver.sample(store, root)
    report = store.read(row["report"]["path"])
    raw = Path(report["inputs"]["snapshot"]["path"]).read_bytes()
    summary = report["summary"]
    cli.require(summary["target"].lower() == row["input"]["deviceAddress"].lower(),
                "capture/report device differs")
    _, messages = phy.fixed_envelope().verify(raw, sentinel=summary["sentinel"],
                                             target=summary["target"])
    row["public"] = public_metrics(messages, row["input"]["packageBytes"])
    row["internal_transfer_seconds"] = row.pop("transfer_seconds")
    row["public_minus_internal_transfer_us"] = round(
        row["public"]["transfer_seconds"] * 1e6) - row["timing"]["total_us"]
    # Compare durations only; these stopwatches have different origins/boundaries.
    cli.require(row["public"]["installation_reconnect_seconds"] ==
                row["installation_reconnect_seconds"], "END/reboot duration differs")
    costs = half.installation_costs(store, row)
    row["installation"] = {k: costs[k] for k in ("phases", "inputs", "clock")}
    row["native_profile"] = report["native_trace"]["profile"]
    if root == CURRENT:
        config = store.checked(root / "cells/s04/runtime-config.json")
        observed = store.read(root / "cells/s04/phy-observation.json")
        value = phy.old.verify_phy(messages, store.read(config), cli.record(config)["sha256"])
        cli.require(observed["result"] == "PRE_BEGIN_PHY_OBSERVED" and
                    observed["observation"] == value and observed["continuous_data_phy"] is False and
                    observed["snapshot"] == report["inputs"]["snapshot"], "PHY receipt differs")
        row["phy"] = dict(observation=value, continuous_data_phy=False,
            input=cli.record(root / "cells/s04/phy-observation.json"), config=cli.record(config))
    return row


def review(store, out):
    cli.require(not out.exists(), "preserve previous review")
    current = sample(store, CURRENT)
    controls = {name: sample(store, path) for name, path in CONTROLS.items()}
    native = current["native_profile"]
    phases = native["phases"]
    value = dict(result="PHY_SCREEN_REVIEWED", current=current, controls=controls,
        comparisons={name: compare(row, current) for name, row in controls.items()},
        device_operations=0, independent_acceptance=False, measured_speedup=False,
        sources=[cli.record(m.__file__) for m in (half, half.receiver, half.receiver.staging,
            half.receiver.staging.timing, half.receiver.staging.review, phy, phy.old)] +
            [cli.record(__file__), cli.record(phy.ENVELOPE)],
        diagnosis=dict(actual_pre_begin_bidirectional_2m=True,
            data_platform_seconds=current["timing"]["nested_data_platform_us"] / 1e6,
            target_transfer_budget_seconds=current["input"]["packageBytes"] / 50000,
            native_staging_io_seconds=sum(phases[k]["seconds"] for k in (
                "payload_erase", "payload_program", "payload_verify", "journal_read",
                "journal_program", "journal_erase", "journal_verify")),
            native_ack_uart_call_seconds=phases["ack_write_call"]["seconds"],
            physical_costs_are_not_app_partitions=True,
            next="Inspect platform callback/connection scheduling and durable ACK return latency. "
                 "Do not repeat PHY or change baud blindly; retain current firmware/APK."))
    store.write(out, value)
    print(json.dumps(dict(result=value["result"], public=current["public"],
        comparisons=value["comparisons"], diagnosis=value["diagnosis"])))


if __name__ == "__main__":
    cli.require(Path.cwd() == ROOT and sys.flags.isolated and sys.flags.no_site and sys.dont_write_bytecode,
                "explicit isolated project root required")
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    store = cli.Store(ROOT)
    review(store, store.checked(args.out))
