"""Offline budget counterfactuals and known-byte Boot workload classification."""
import argparse
import json
import math
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "Tools/ota"))
import p34_sha_trial as trial
import p34_batch_timing as timing
import p34_phy_review as metrics

cli = trial.cli


def block_workload(before, after, size=4096):
    cli.require(after and type(size) is int and size > 0, "nonempty target and block size required")
    groups = dict(different=[], identical=[], unknown=[])
    for offset in range(0, len(after), size):
        expected = after[offset:offset+size].ljust(size, b"\xff")
        known = before[offset:offset+size]
        # Raw image readbacks do not cover bytes beyond the old header length.
        # Never silently assume that unobserved Flash is erased.
        kind = "different" if known != expected[:len(known)] else (
            "identical" if len(known) == size else "unknown")
        groups[kind].append(offset // size)
    count = sum(map(len, groups.values()))
    return dict(blocks=count, counts={k: len(v) for k, v in groups.items()}, indexes=groups,
        per_block_copy_commits=count, hypothetical_group16_copy_commits=(count+15)//16,
        scope="Known bytes only; partial old final block has unknown padding. "
              "Counts model successful copy-path BCB commits, excluding state transitions/retries.")


def budget(partition, total):
    cli.require(type(total) is int and total > 0, "positive package bytes required")
    cli.require(all(type(v) is int and v >= 0 for v in partition.values()), "invalid timing partition")
    gatt, tail = partition["data_gatt_us"], partition["last_chunk_to_durable_us"]
    rest = sum(partition.values()) - gatt - tail
    cases = {"measured_partition": gatt+tail+rest, "zero_tail_other_costs_fixed": gatt+rest,
             "half_gatt_other_costs_fixed": gatt/2+tail+rest,
             "half_gatt_zero_tail_other_costs_fixed": gatt/2+rest}
    cli.require(all(v > 0 for v in cases.values()), "zero counterfactual denominator")
    return dict(target_budget_us=total*20, gatt_us=gatt, tail_us=tail, other_us=rest,
        cases={k: dict(seconds=v/1e6, decimal_kb_s=total*1000/v) for k, v in cases.items()},
        interpretation="Algebraic counterfactuals holding named costs fixed, NOT predictions or physical limits. "
                       "Halving connection interval does not imply halving GATT time.")


def run(output):
    s = cli.Store(ROOT)
    output = s.checked(output)
    cli.require(not output.exists(), "preserve prior feasibility evidence")
    roots = dict(control=trial.prior.TRIALS / "measure", bootstrap=trial.TRIALS / "bootstrap",
                 measure=trial.TRIALS / "measure")
    samples = {}
    for role, root in roots.items():
        pointer, report = trial.old.old.review.load_report(s, root)
        group = trial.prior.assets(s, "measure") if role == "control" else trial.assets(s, role)
        inp = report["summary"]["input"]
        cli.require(group["target"]["sha256"] == inp["targetImageSha256"] and
                    group["receiver"]["sha256"] == inp["currentImageSha256"], "image lineage differs")
        summary = report["summary"]
        _, messages = trial.old.old.repaired.fixed_envelope().verify(
            Path(report["inputs"]["snapshot"]["path"]).read_bytes(),
            sentinel=summary["sentinel"], target=summary["target"])
        parts = timing.analyze(messages, inp["packageBytes"])
        native = report["native_trace"]
        cli.require(cli.record(native["original"]["path"]) == native["original"], "native trace changed")
        workload = block_workload(*(Path(group[k]["path"]).read_bytes() for k in ("receiver", "target")))
        samples[role] = dict(report=pointer, package=group["package"],
            receiver=group["receiver"], target=group["target"], workload=workload,
            public=metrics.public_metrics(messages, inp["packageBytes"]),
            budget=budget(parts["transfer_partition_us"], inp["packageBytes"]),
            boot_residency=native["boot_residency"], activation=native["activation"])
    preparation = s.read(ROOT / ".cache/p34-boot/preparation/result.json")
    boot_source = next(x for x in preparation["sources"] if x["path"].replace("\\", "/").endswith("boot/src/boot_state_machine.c"))
    cli.require(cli.record(boot_source["path"]) == boot_source, "installed Boot source no longer matches")
    value = dict(result="OFFLINE_FEASIBILITY_EVIDENCE", samples=samples,
        boot_source=boot_source, boot_preparation=cli.record(ROOT / ".cache/p34-boot/preparation/result.json"),
        source=cli.record(__file__), device_operations=0, measured_speedup=False,
        scope="Decision support only. No firmware/protocol change, benchmark, deployment or device command.")
    s.write(output, value)
    print(json.dumps({k: dict(workload=v["workload"]["counts"], budget=v["budget"])
                      for k, v in samples.items()}))


if __name__ == "__main__":
    cli.require(Path.cwd() == ROOT and sys.flags.isolated and sys.flags.no_site and
                sys.dont_write_bytecode, "explicit isolated root required")
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--out", required=True, type=Path)
    run(p.parse_args().out)
