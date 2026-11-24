"""Rebind existing conservative graph inventory to the EARLY-05 revision."""
from pathlib import Path
import argparse
import sys

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "Tools/ota"))
import p34_early_usb_gate as gate
import p34_early_stack_graph as graph
import p34_early_stack_callbacks as callbacks


def main(retry=False):
    cli = graph.cli
    cli.require(Path.cwd() == ROOT and sys.flags.isolated and sys.flags.no_site and sys.dont_write_bytecode,
                "isolated project root required")
    store = cli.Store(ROOT)
    area = gate.AREA
    if retry:
        import p34_early_usb_retry as revision
        area = revision.AREA
    outputs = [store.checked(area / p) for p in
               ("stack-graph1/result.json", "stack-callbacks1/result.json", "stack-refresh.json")]
    cli.require(not any(p.exists() for p in outputs), "preserve graph evidence")
    paths = [Path(__file__), Path(graph.__file__), Path(callbacks.__file__), Path(gate.__file__),
             area / "validation.json", area / "prepared.json"]
    if retry:
        paths.append(Path(revision.__file__))
    records = [cli.record(p) for p in paths]
    cli.require(store.read(area / "validation.json")["result"] == "EARLY_USB_ARTIFACT_CHECKS_PASS",
                "validated revision required")
    # Runtime module configuration only; no old file, result or source is modified.
    graph.AREA = area
    callbacks.AREA = area
    graph.main()
    callbacks.main()
    cli.require(records == [cli.record(p) for p in paths], "input drift")
    store.write(outputs[2], dict(result="EARLY_USB_STACK_INVENTORY_REFRESHED", inputs=records,
                                outputs=[cli.record(p) for p in outputs[:2]],
                                total_bound=None, status="UNKNOWN_REMAINING_EDGES_FRAMES_AND_NESTING",
                                hardware=False, independent_acceptance=False))


if __name__ == "__main__":
    parser = argparse.ArgumentParser(); parser.add_argument("--retry", action="store_true")
    main(parser.parse_args().retry)
