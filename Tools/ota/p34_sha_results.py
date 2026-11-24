"""Reuse strict closed-trial analysis for the SHA compiler screen."""
import argparse
import json
from pathlib import Path
import sys
from types import SimpleNamespace

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "Tools/ota"))
import p34_sha_trial as trial
import p34_info_retry_results as previous


def compare(store, output):
    output = store.checked(output)
    trial.cli.require(not output.exists(), "preserve prior comparison")
    roots = dict(control=trial.prior.TRIALS / "measure",
                 bootstrap=trial.TRIALS / "bootstrap", measure=trial.TRIALS / "measure")
    rows = {}
    last_target = None
    boot = None
    for index, (name, root) in enumerate(roots.items()):
        previous.closed(store, root)
        pointer, report = trial.old.old.review.load_report(store, root)
        group = trial.prior.assets(store, "measure") if name == "control" else trial.assets(store, name)
        config = store.read(root / "cells/s04/runtime-config.json")
        trial.old.validate(config, group)
        inp = report["summary"]["input"]
        trial.cli.require([inp[k] for k in ("currentVersionCode", "targetVersionCode")] ==
                          [30272 + index, 30273 + index], "unexpected comparison lineage")
        current_boot = group["target_bindings"]["whole_boot"]
        trial.cli.require(boot is None or current_boot == boot, "comparison Boot changed")
        trial.cli.require(last_target is None or group["receiver"]["sha256"] == last_target,
                          "comparison predecessor discontinuity")
        boot, last_target = current_boot, group["target"]["sha256"]
        before, after = (Path(group[k]["path"]).read_bytes() for k in ("receiver", "target"))
        header_only = before[:0x400] + before[0x460:] == after[:0x400] + after[0x460:]
        trial.cli.require(header_only == (name != "bootstrap"), "comparison workload differs")
        summary = report["summary"]
        _, messages = trial.old.old.repaired.fixed_envelope().verify(
            Path(report["inputs"]["snapshot"]["path"]).read_bytes(),
            sentinel=summary["sentinel"], target=summary["target"])
        rows[name] = dict(report=pointer, header_only=header_only,
            public=previous.metrics.public_metrics(messages, inp["packageBytes"]),
            activation=report["native_trace"]["activation"])
    old, new = (rows[name]["public"] for name in ("control", "measure"))
    value = dict(result="SHA_SCREEN_COMPARED", samples=rows,
        transfer_seconds_saved=old["transfer_seconds"] - new["transfer_seconds"],
        installation_reconnect_seconds_saved=old["installation_reconnect_seconds"] - new["installation_reconnect_seconds"],
        transfer_target_met=new["transfer_target_met"], installation_target_met=new["installation_target_met"],
        causal_speedup_proven=False, repeatability_proven=False, strict_same_package_ab=False,
        device_operations=0, source=trial.cli.record(__file__),
        scope="Sequential legal header-only control/measure, not an identical package A/B. "
              "Changed-executable bootstrap is retained but excluded from gain calculation. "
              "Native ticks are not calibrated App wall durations. Numerical deltas alone do not prove causality.")
    store.write(output, value)
    print(json.dumps({k: v for k, v in value.items() if k != "samples"}))


if __name__ == "__main__":
    cli = trial.cli
    cli.require(Path.cwd() == ROOT and sys.flags.isolated and sys.flags.no_site and
                sys.dont_write_bytecode, "explicit isolated root required")
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("mode", choices=("analyze", "summarize", "compare"))
    parser.add_argument("--arm", choices=trial.ORDER)
    parser.add_argument("--out", type=Path)
    args = parser.parse_args()
    if args.mode == "compare":
        cli.require(args.out is not None and args.arm is None, "comparison needs only an output")
        compare(cli.Store(ROOT), args.out)
        sys.exit(0)
    cli.require(args.arm in trial.ORDER, "analysis arm required")
    adapter = SimpleNamespace(TRIALS=trial.TRIALS, tests=trial.tests, Trial=trial.Trial,
        old=trial.old.old, assets=trial.assets, validate=trial.old.validate, verify=trial.old.verify)
    function = getattr(previous, args.mode)
    execute = trial.batch.clone(function, trial=adapter)
    store = cli.Store(ROOT)
    if args.mode == "analyze":
        execute(store, args.arm)
    else:
        cli.require(args.out is not None, "explicit project-local summary output required")
        execute(store, args.arm, args.out)
