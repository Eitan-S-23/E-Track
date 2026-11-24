"""Review same-APK INFO-timeout screens from closed evidence, without device I/O."""
import argparse
import json
from pathlib import Path
import re
import sys
from urllib.parse import urlsplit

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "Tools/ota"))
import p34_phy_review as phy

cli = phy.cli
IDENTITY_FIELDS = frozenset(("runId", "firmwareLatestUrl", "packageBytes", "packageSha256",
    "currentVersionCode", "currentImageSha256", "targetVersionCode", "targetImageSha256"))
AXIS = "rebootInfoTimeoutMs"


def info_samples(messages):
    pending, attempts = [], []
    pattern = re.compile(r"OTA_LINK_SAMPLE label=probe kind=get_info us=(\d+) ok=([01])")
    for line in messages.splitlines():
        cli.require(not line.startswith("OTA_LINK_LATE label=probe "), "late probe samples need separate attribution")
        if line.startswith("OTA_LINK_SAMPLE label=probe kind=get_info "):
            match = pattern.fullmatch(line)
            cli.require(match is not None, "malformed INFO sample")
            pending.append(dict(us=int(match[1]), ok=match[2] == "1"))
        elif line.startswith("OTA_LINK_STATS "):
            value = json.loads(line[len("OTA_LINK_STATS "):])
            if value["label"] != "probe" or value["attempt"] is None:
                continue
            info = value["getInfo"]
            cli.require(len(pending) == info["calls"] and
                sum(not x["ok"] for x in pending) == info["failures"] and
                sum(x["us"] for x in pending) == info["totalUs"], "INFO samples differ from original summary")
            attempts.append(dict(attempt=value["attempt"], samples=pending))
            pending = []
    cli.require(not pending and attempts, "unclosed or absent INFO attempts")
    cli.require([x["attempt"] for x in attempts] == list(range(1, len(attempts) + 1)), "INFO attempt sequence differs")
    success = [x["us"] for a in attempts for x in a["samples"] if x["ok"]]
    cli.require(success, "completed identity needs a successful INFO sample")
    return dict(attempts=attempts, successful_us=success,
        scope="Measured call durations include writes/wait/scheduling; not isolated air latency or a timeout forecast.")


def cohort(before, after):
    configs = [row["config"] for row in (before, after)]
    cli.require(set(configs[0]) == set(configs[1]), "configuration fields changed")
    changed = {key for key in configs[0] if key not in IDENTITY_FIELDS and configs[0][key] != configs[1][key]}
    cli.require(changed == {AXIS}, "only the declared INFO-timeout axis may change")
    for row in (before, after):
        value = row["config"][AXIS]
        cli.require(type(value) is int and 500 <= value <= 10000, "unsupported INFO timeout")
        cli.require(row["header_only"] is True and row["input"]["appLifecycle"] == "resumed",
                    "header-only foreground screens required")
        cli.require(row["input"]["targetVersionCode"] == row["input"]["currentVersionCode"] + 1,
                    "legal sequential successor required")
    for key in ("apk_sha256", "boot_sha256", "binding"):
        cli.require(before[key] == after[key], "APK, Boot or negotiated binding changed")
    for target, current in (("targetVersionCode", "currentVersionCode"),
                            ("targetImageSha256", "currentImageSha256")):
        cli.require(before["input"][target] == after["input"][current], "predecessor identity discontinuity")
    result = phy.compare(before, after)
    result.pop("causal_phy_speedup_proven")
    result.update(axis=AXIS, before_ms=configs[0][AXIS], after_ms=configs[1][AXIS],
        causal_timeout_speedup_proven=False, repeatability_proven=False,
        scope="One sequential legal package per timeout; package headers and lengths differ. Not matched A/B or reliability acceptance.")
    return result


def sample(store, root):
    row = phy.sample(store, root)
    report = store.read(row["report"]["path"])
    _, messages = phy.phy.fixed_envelope().verify(Path(report["inputs"]["snapshot"]["path"]).read_bytes(),
        sentinel=report["summary"]["sentinel"], target=report["summary"]["target"])
    config_path = store.checked(root / "cells/s04/runtime-config.json")
    config = store.read(config_path)
    # Startup and BEGIN repeat the same configuration; the shared reader
    # rejects conflicting records without mistaking that repetition for replay.
    observed = phy.phy.fixed_envelope().experiment_record(messages.splitlines())
    cli.require(observed == report["experiment"] and
                observed["configSha256"] == cli.record(config_path)["sha256"], "config observation changed")
    for key in set(config) - {"firmwareLatestUrl", "target"}:
        cli.require(type(config[key]) is type(observed[key]) and config[key] == observed[key],
                    "runtime configuration differs from original producer")
    cli.require(urlsplit(config["firmwareLatestUrl"]).hostname == observed["endpointHost"], "endpoint config differs")
    cli.require(config["target"].lower() == row["input"]["deviceAddress"].lower(), "device config differs")
    actual = phy.phy.old.verify_phy(messages, config, cli.record(config_path)["sha256"])
    row.update(config=config, config_input=cli.record(config_path), actual_pre_begin_phy=actual,
               info_samples=info_samples(messages))
    return row


def review(store, control, current, out):
    out = store.checked(out)
    cli.require(not out.exists(), "preserve earlier review")
    before, after = (sample(store, store.checked(p)) for p in (control, current))
    comparison = cohort(before, after)
    value = dict(result="RECONNECT_TIMEOUT_SCREEN_REVIEWED", control=before, current=after,
        comparison=comparison, sources=[cli.record(__file__), cli.record(phy.__file__)],
        device_operations=0, independent_acceptance=False,
        warning="A shorter failed INFO wait is not an equivalent reduction in total install/reconnect time.")
    store.write(out, value)
    print(json.dumps(dict(result=value["result"], public=after["public"], comparison=comparison)))


if __name__ == "__main__":
    cli.require(Path.cwd() == ROOT and sys.flags.isolated and sys.flags.no_site and sys.dont_write_bytecode,
                "explicit isolated project root required")
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ("control", "current", "out"):
        parser.add_argument("--" + name, type=Path, required=True)
    args = parser.parse_args()
    review(cli.Store(ROOT), args.control, args.current, args.out)
