"""Correlate a closed OTA while retaining, but not decoding, ATT-empty connections."""
import argparse
import json
from pathlib import Path
import sys
from types import SimpleNamespace

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "Tools/ota"))
import p34_hci_ota as previous
import p34_batch_review as review

cli = review.cli


def analyze(data, package, expected):
    decoded = previous.att.analyze(data, expected["deviceAddress"])
    active = {row["generation"] for row in decoded["att"]}
    empty = [connection for connection in decoded["connections"] if connection["generation"] not in active]
    selected = dict(decoded, connections=[c for c in decoded["connections"] if c["generation"] in active])

    def prepared(raw, peer):
        cli.require(raw == data and peer == expected["deviceAddress"], "decoded capture binding changed")
        return selected

    # No packets, timestamps, ATT rows or generation IDs are changed. Every
    # connection with any ATT data still passes the original strict analyzer.
    run = review.trial.clone(previous.analyze, att=SimpleNamespace(analyze=prepared))
    value = run(data, package, expected)
    value.update(att_empty_connections=empty, original_connection_count=len(decoded["connections"]),
                 packet_selection="Original entire capture; only ATT-empty connection metadata excluded from characteristic decoding")
    return value


if __name__ == "__main__":
    cli.require(Path.cwd() == ROOT and sys.flags.isolated and sys.flags.no_site and sys.dont_write_bytecode,
                "explicit isolated root required")
    p = argparse.ArgumentParser(description=__doc__)
    for name in ("hci", "archive", "trial", "out"): p.add_argument("--" + name, type=Path, required=True)
    a = p.parse_args(); s = cli.Store(ROOT)
    out = s.checked(a.out)
    cli.require(not out.exists(), "preserve prior correlation")
    pointer, report = review.load_report(s, s.checked(a.trial))
    archive = s.read(s.checked(a.archive))
    hci = cli.record(s.checked(a.hci))
    cli.require(any(item["original"] == hci for item in archive["extracted"]), "HCI bytes differ from original export")
    package = report["inputs"]["download"]
    value = analyze(Path(hci["path"]).read_bytes(), Path(package["path"]).read_bytes(), report["summary"]["input"])
    value.update(report=pointer, hci=hci, archive=cli.record(a.archive), package=package,
        sources=[cli.record(m.__file__) for m in (previous, previous.att, previous.compare)],
        source=cli.record(__file__), device_operations=0)
    s.write(out, value)
    print(json.dumps({k: v for k, v in value.items() if k not in ("block_timing", "identities")}))
