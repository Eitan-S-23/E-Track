"""Read-only staging-erase comparison from original closed trial evidence."""
import argparse
import json
import math
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "Tools/ota"))
import p34_batch_review as review
import p34_batch_timing as timing

cli = review.cli
AREA = ROOT / ".cache/p34-staging-erase"
TRIALS = dict(control=ROOT / ".cache/p34-batch12/resumed-trials/control",
              bootstrap=AREA / "trials/bootstrap", measure=AREA / "trials/measure")
POLICY = dict(schema=7, requestedBaud=921600, reuseGatt=True, withoutResponse=True,
              senderWindowSegments=28, transferMode="full", prefixBytes=0,
              rebootInfoTimeoutMs=2000, rebootProbeIntervalMs=500,
              pauseScanDuringOta=True, androidHighPriority=True,
              dataBatchFrames=3, reuseRebootInfoLink=True)


def header_only(before, after):
    cli.require(min(len(before), len(after)) >= 0x460, "short firmware image")
    return before != after and before[:0x400] + before[0x460:] == after[:0x400] + after[0x460:]


def sample(s, root):
    pointer, report = review.load_report(s, root)
    inp = report["summary"]["input"]
    launch = s.read(report["inputs"]["launch"]["path"])
    before, after = (s.read(report[k]["path"]) for k in ("before", "after"))
    images = [x["final_identity"]["app"] for x in (before, after)]
    for item in images:
        cli.require(cli.record(s.checked(item["path"])) == item, "raw image changed")
    cli.require([x["sha256"] for x in images] ==
                [inp["currentImageSha256"], inp["targetImageSha256"]], "raw identity binding differs")
    raw = Path(report["inputs"]["snapshot"]["path"]).read_text(encoding="utf-8")
    messages = "\n".join(x["message"] for x in map(json.loads, raw.splitlines()) if x.get("kind") == "line")
    account = timing.analyze(messages, inp["packageBytes"])
    metrics = report["full_metrics"]
    cli.require(math.isclose(account["total_us"] / 1e6, metrics["transfer_seconds"], abs_tol=1e-9),
                "original transfer clocks differ")
    native = report["native_trace"]["profile"]
    cli.require(native["clean_counters"] and native["clock_ok"] == 1 and native["clock_hz"] == 288000000,
                "unclean or invalid native measurement")
    erase = native["phases"]["payload_erase"]
    cli.require(erase["errors"] == 0 and erase["calls"] > 0, "payload erase samples incomplete")
    return dict(report=pointer, input=inp, policy={k: report["experiment"][k] for k in POLICY},
        apk_sha256=launch["apk"]["sha256"], boot_sha256=after["final_identity"]["boot"]["sha256"],
        header_only=header_only(*(Path(x["path"]).read_bytes() for x in images)),
        binding={k: metrics["binding"][k] for k in ("writeMode", "mtuChunkBytes", "mtuSource")},
        transfer_seconds=metrics["transfer_seconds"],
        installation_reconnect_seconds=metrics["installation_reconnect_seconds"],
        payload_erase_seconds=erase["seconds"], payload_erase_calls=erase["calls"],
        timing=account, reconnect=review.probes(messages))


def compare(rows):
    cli.require(set(rows) == {"control", "bootstrap", "measure"}, "complete declared matrix required")
    control, bootstrap, measure = (rows[k] for k in ("control", "bootstrap", "measure"))
    for name, versions in (("control", (30257, 30258)), ("bootstrap", (30259, 30260)), ("measure", (30260, 30261))):
        row = rows[name]
        cli.require(tuple(row["input"][k] for k in ("currentVersionCode", "targetVersionCode")) == versions,
                    "wrong matrix role/version")
        cli.require(row["policy"] == POLICY and row["binding"] ==
                    dict(writeMode="without", mtuChunkBytes=244, mtuSource="negotiated"), "link policy differs")
        cli.require(row["input"]["appLifecycle"] == "resumed", "foreground comparison required")
        for key in ("transfer_seconds", "installation_reconnect_seconds", "payload_erase_seconds"):
            cli.require(type(row[key]) in (int, float) and math.isfinite(row[key]) and row[key] > 0,
                        "invalid measurement")
        size = row["input"]["packageBytes"]
        cli.require(type(size) is int and 0 < size <= 1048576, "invalid complete package size")
    for key in ("apk_sha256", "boot_sha256"):
        cli.require(len({row[key] for row in rows.values()}) == 1, "APK/Boot changed")
    cli.require(len({row["input"]["deviceAddress"].lower() for row in rows.values()}) == 1, "device changed")
    cli.require(control["header_only"] and measure["header_only"] and not bootstrap["header_only"],
                "bootstrap and measurement workloads confused")
    cli.require(bootstrap["input"]["targetImageSha256"] == measure["input"]["currentImageSha256"],
                "measurement does not follow actual bootstrap")
    old_rate = control["input"]["packageBytes"] / 1000 / control["transfer_seconds"]
    new_rate = measure["input"]["packageBytes"] / 1000 / measure["transfer_seconds"]
    return dict(transfer_seconds_saved=control["transfer_seconds"] - measure["transfer_seconds"],
        control_kb_s=old_rate, measure_kb_s=new_rate, throughput_gain_percent=(new_rate / old_rate - 1) * 100,
        installation_reconnect_seconds_added=measure["installation_reconnect_seconds"] - control["installation_reconnect_seconds"],
        native_erase_seconds_saved=control["payload_erase_seconds"] - measure["payload_erase_seconds"],
        transfer_target_met=new_rate >= 50, installation_target_met=measure["installation_reconnect_seconds"] <= 20,
        useful_transfer_screening_gain=new_rate > old_rate and measure["payload_erase_seconds"] < control["payload_erase_seconds"],
        strict_same_package_ab=False, independent_acceptance=False,
        scope="Sequential legal FULL screening groups; different package identities/lengths. "
              "Bootstrap is not the optimized receiver measurement. Native times overlap App times. "
              "One sample per role does not prove repeatability or reference-size reliability.")


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--out", type=Path, required=True)
    args = p.parse_args()
    cli.require(Path.cwd() == ROOT and sys.flags.isolated and sys.flags.no_site and sys.dont_write_bytecode,
                "explicit isolated root required")
    s = cli.Store(ROOT)
    out = s.checked(args.out)
    cli.require(not out.exists(), "preserve earlier comparison")
    rows = {name: sample(s, root) for name, root in TRIALS.items()}
    value = dict(result="STAGING_ERASE_SCREEN_REVIEWED", source=cli.record(__file__),
                 device_operations=0, samples=rows, comparison=compare(rows))
    s.write(out, value)
    print(json.dumps(value["comparison"]))


if __name__ == "__main__":
    main()
