"""Read-only original phone evidence after the scan arm recorder failure."""
import argparse
import json
from pathlib import Path
import runpy
import sys

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "Tools/ota"))
import p34_radio_install as install
cli = install.cli
AREA = install.AREA
TRIAL = AREA / "trials-v2/scan"
OUT = AREA / "retrieve-scan-001"
REMOTE = "files/p34-observations/1790925192124168-1a3c191610d5b0cc5010d74d"


def worker(s):
    for name in ("network", "coordinator", "s04"):
        closed = s.read(TRIAL / "runtime" / name / "closed.json")
        cli.require(not closed["forced_termination"], "prior owner unresolved")
    b, d, p, lock = runpy.run_path(str(ROOT / "Tools/ota/p34_signing_migration.py"))["runtime"]()
    value = dict(result="RETRIEVAL_INCOMPLETE", no_install=True, no_ota=True, no_app_stop=True)
    try:
        with lock.device_lock(), d["usb"](b, p, OUT):
            p.phone_identity()
            value["installed"] = d["installed"](b, p, s.read(AREA / "apk-g1/apk.json")["apk"]["sha256"])
            value["pid"] = p.command(["shell", "pidof", install.PKG], check=False).strip()
            value["logcat"] = s.raw(OUT / "logcat-full.log", p.command(
                ["logcat", "-d", "-v", "threadtime", "--pid=2078"], timeout=45, binary=True))
            names = p.command(["exec-out", "run-as", install.PKG, "ls", "-1", REMOTE]).splitlines()
            cli.require(set(names) <= {"events.jsonl", "health.json", "health.json.tmp", "snapshot-1.jsonl"},
                        "unexpected capture files; preserve listing")
            value["files"] = {}
            for name in names:
                raw = p.command(["exec-out", "run-as", install.PKG, "head", "-c", "16777217", REMOTE + "/" + name],
                                timeout=30, binary=True)
                cli.require(len(raw) <= 16777216, "capture exceeds retrieval bound")
                value["files"][name] = s.raw(OUT / name, raw)
            config = p.file_bytes(install.PKG, "files/p34-experiment.json", 8192)
            value["config"] = s.raw(OUT / "runtime-config.json", config)
            cli.require(config == (TRIAL / "cells/s04/runtime-config.json").read_bytes(), "configuration changed")
            value["result"] = "ORIGINAL_PHONE_EVIDENCE_RETRIEVED_NOT_VALIDATED"
        value["usb_closed"] = True
    except Exception as error:
        value.update(error=type(error).__name__, detail=str(error))
    s.write(OUT / "result.json", dict(time=cli.now(), **value))
    print(json.dumps(value), flush=True)
    cli.require("error" not in value, "retrieval unresolved; do not repeat device operations")


if __name__ == "__main__":
    cli.require(Path.cwd() == ROOT and sys.flags.isolated and sys.flags.no_site and sys.dont_write_bytecode,
                "explicit root and isolated Python required")
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("mode", choices=("launch", "worker"))
    args = parser.parse_args()
    s = cli.Store(ROOT)
    supervisor = cli.load_module("radio_retrieval_owner", ROOT / ".cache/p3-4-screening-20260922/supervisor.py")
    if args.mode == "launch":
        cli.require(not OUT.exists(), "preserve original retrieval")
        for name in ("intent.json", "result.json", "logcat-full.log", "events.jsonl", "health.json",
                     "health.json.tmp", "snapshot-1.jsonl", "runtime-config.json", "usb", "host"):
            s.checked(OUT / name)
        s.write(OUT / "intent.json", dict(source=cli.record(__file__), no_device_mutation=True, remote=REMOTE))
        print(supervisor.owned.launch(AREA / "runtime/retrieve-scan-001", Path(__file__), ["worker"], 600), flush=True)
    else:
        cli.require(supervisor.owned.in_job(), "finite owned retrieval required")
        worker(s)
