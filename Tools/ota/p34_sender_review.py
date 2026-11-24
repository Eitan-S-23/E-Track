"""Review sequential batch3/12 FULL samples on an executable-identical receiver."""
import argparse
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "Tools/ota"))
import p34_receiver_review as receiver

cli = receiver.cli


def compare(control, measure):
    for row, frames in ((control, 3), (measure, 12)):
        inp = row["input"]
        cli.require(row["policy"] == dict(receiver.staging.POLICY, dataBatchFrames=frames)
                    and row["binding"] == dict(writeMode="without", mtuChunkBytes=244, mtuSource="negotiated"),
                    "sender comparison policy differs")
        cli.require(row["header_only"] is True and inp["appLifecycle"] == "resumed", "wrong workload/lifecycle")
        for key in ("transfer_seconds", "installation_reconnect_seconds"):
            cli.require(receiver.positive(row[key]), "invalid timing")
        cli.require(type(inp["packageBytes"]) is int and 0 < inp["packageBytes"] <= 1048576,
                    "invalid complete package size")
        versions = [inp[k] for k in ("currentVersionCode", "targetVersionCode")]
        cli.require(all(type(v) is int and 0 < v <= 2100000000 for v in versions)
                    and versions[1] == versions[0] + 1, "wrong successor versions")
        for key in ("currentImageSha256", "targetImageSha256", "packageSha256"):
            value = inp[key]
            cli.require(isinstance(value, str) and len(value) == 64
                        and all(c in "0123456789abcdef" for c in value), "invalid raw identity")
        cli.require(inp["currentImageSha256"] != inp["targetImageSha256"], "unchanged image identity")
    for key in ("apk_sha256", "boot_sha256"):
        cli.require(control[key] == measure[key], "APK/Boot differs")
    old, new = control["input"], measure["input"]
    cli.require(old["deviceAddress"].lower() == new["deviceAddress"].lower(), "device differs")
    cli.require(old["targetVersionCode"] == new["currentVersionCode"]
                and old["targetImageSha256"] == new["currentImageSha256"], "predecessor identity differs")
    cli.require(old["packageSha256"] != new["packageSha256"], "successor package replay")
    old_rate = old["packageBytes"] / 1000 / control["transfer_seconds"]
    new_rate = new["packageBytes"] / 1000 / measure["transfer_seconds"]
    gain = new_rate > old_rate
    return dict(control_kb_s=old_rate, measure_kb_s=new_rate,
        throughput_gain_percent=(new_rate / old_rate - 1) * 100,
        transfer_seconds_saved=control["transfer_seconds"] - measure["transfer_seconds"],
        installation_reconnect_seconds_added=measure["installation_reconnect_seconds"] - control["installation_reconnect_seconds"],
        useful_transfer_screening_gain=gain, retain_batch_frames=12 if gain else 3,
        transfer_target_met=new_rate >= 50, installation_target_met=measure["installation_reconnect_seconds"] <= 20,
        strict_same_package_ab=False, independent_acceptance=False,
        scope="One sequential header-only FULL sample per sender group; same receiver executable, different packages. "
              "Not repeatability/reference-size reliability; overlapping native/ACK times are not added as savings.")


if __name__ == "__main__":
    cli.require(Path.cwd() == ROOT and sys.flags.isolated and sys.flags.no_site and sys.dont_write_bytecode,
                "isolated explicit root required")
    p = argparse.ArgumentParser(description=__doc__)
    for name in ("control", "measure", "out"):
        p.add_argument("--" + name, required=True, type=Path)
    a = p.parse_args()
    s = cli.Store(ROOT)
    out = s.checked(a.out)
    cli.require(not out.exists(), "preserve comparison")
    rows = {name: receiver.sample(s, s.checked(getattr(a, name))) for name in ("control", "measure")}
    value = dict(result="SENDER_SCREEN_REVIEWED", source=cli.record(__file__), device_operations=0,
                 samples=rows, comparison=compare(**rows))
    s.write(out, value)
    print(json.dumps(value["comparison"]))
