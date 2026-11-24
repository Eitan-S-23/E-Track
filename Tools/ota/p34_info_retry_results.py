"""Offline INFO retry analysis using the trial's original strict validators."""
import argparse
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "Tools/ota"))
import p34_info_retry_trial as trial
import p34_phy_review as metrics

cli = trial.cli


def closed(s, out):
    for name in ("coordinator", "network", "s04"):
        value = s.read(out / "runtime" / name / "closed.json")
        cli.require(value["worker_exit"] == 0 and not value["forced_termination"],
                    "all original owners must close normally before analysis")
    value = s.read(out / "cells/s04/result.json")
    cli.require(value["result"] in ("FULL_INSTALL_OBSERVED", "FULL_INSTALL_VERIFIED") and
                "error" not in value and "cleanup_error" not in value,
                "original cell unresolved; no replay")


def analyze(s, arm):
    out = trial.TRIALS / arm
    closed(s, out)
    trial.tests(s)
    if (out / "analysis/latest.json").exists():
        pointer, result = trial.old.review.load_report(s, out)
        print(json.dumps(dict(result=result["result"], existing_report=pointer)))
        return
    api = trial.Trial(s, arm)
    c = api.context(out)
    api.preflight(c, out)
    for leaf in ("analysis", "analysis/latest.json", "analysis/latest.json.tmp"):
        s.checked(out / leaf)
    cli.require(c.sources() == s.read(out / "intent.json")["sources"], "trial sources changed")
    result = api.analyze_install(c, out, "s04")
    cli.require(result["result"] == "FULL_INSTALL_VERIFIED", "complete raw identity still required")
    print(json.dumps(dict(result=result["result"], evidence=result["evidence"])))


def summarize(s, arm, output):
    out = trial.TRIALS / arm
    closed(s, out)
    output = s.checked(output)
    cli.require(not output.exists(), "preserve prior summary")
    pointer, report = trial.old.review.load_report(s, out)
    summary = report["summary"]
    _, messages = trial.old.repaired.fixed_envelope().verify(
        Path(report["inputs"]["snapshot"]["path"]).read_bytes(),
        sentinel=summary["sentinel"], target=summary["target"])
    config = s.read(out / "cells/s04/runtime-config.json")
    trial.validate(config, trial.assets(s, arm))
    experiment = trial.verify(trial.old.repaired.fixed_envelope(), messages, config,
                              report["inputs"]["config"]["sha256"])
    cli.require(experiment == report["experiment"], "original experiment differs")
    value = dict(result="INFO_RETRY_CELL_REVIEWED", arm=arm, report=pointer,
        public=metrics.public_metrics(messages, summary["input"]["packageBytes"]),
        reconnect=trial.old.review.probes(messages), attempts=config["rebootInfoMaxAttempts"],
        source=cli.record(__file__), device_operations=0, independent_acceptance=False,
        strict_same_package_ab=False, repeatability_proven=False)
    s.write(output, value)
    print(json.dumps(dict(result=value["result"], public=value["public"], attempts=value["attempts"])))


if __name__ == "__main__":
    cli.require(Path.cwd() == ROOT and sys.flags.isolated and sys.flags.no_site and sys.dont_write_bytecode,
                "explicit isolated project root required")
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("mode", choices=("analyze", "summarize"))
    parser.add_argument("--arm", choices=trial.ORDER, required=True)
    parser.add_argument("--out", type=Path)
    args = parser.parse_args()
    store = cli.Store(ROOT)
    if args.mode == "analyze":
        analyze(store, args.arm)
    else:
        cli.require(args.out is not None, "explicit project-local summary output required")
        summarize(store, args.arm, args.out)
