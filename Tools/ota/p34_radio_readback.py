"""Read full target/Boot after recorder failure without replaying the scan OTA."""
import argparse
import json
import os
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "Tools/ota"))
import p34_radio_trial as radio

cli = radio.cli
OUT = radio.AREA / "readback-scan-001"


def worker(s):
    for name in ("coordinator", "network", "s04"):
        v = s.read(radio.TRIALS / "scan/runtime" / name / "closed.json")
        cli.require(not v["forced_termination"], "prior owner unresolved")
    v = s.read(radio.AREA / "runtime/retrieve-scan-001/closed.json")
    cli.require(v["worker_exit"] == 0 and not v["forced_termination"], "USB retrieval unresolved")
    api = radio.Radio(s, "scan")
    c = api.installed_context(OUT)
    api.preflight(c, OUT)
    c.native_authority()
    os.environ.update(c.environment())
    value = dict(result="TARGET_READBACK_INCOMPLETE", no_ota=True, no_reset=True, no_halt=True, no_flash=True,
                 original_capture_invalid=True, performance="UNAVAILABLE")
    try:
        lock = c.load("radio_readback_lock", ROOT / "Tools/ota/repeat_cycle.py")
        with lock.device_lock():
            checkpoint = api.install_checkpoint(c, OUT)
            api.verify_install_checkpoint(c, checkpoint["path"])
        value.update(result="TARGET_30247_RAW_CONFIRMED_CAPTURE_INVALID", checkpoint=checkpoint)
    except Exception as error:
        value.update(error=type(error).__name__, detail=str(error))
    s.write(OUT / "result.json", dict(time=cli.now(), **value))
    print(json.dumps(value), flush=True)
    cli.require("error" not in value, "readback outcome requires reconciliation")


if __name__ == "__main__":
    cli.require(Path.cwd() == ROOT and sys.flags.isolated and sys.flags.no_site and sys.dont_write_bytecode,
                "explicit root and isolated Python required")
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("mode", choices=("launch", "worker"))
    args = parser.parse_args()
    s = cli.Store(ROOT)
    supervisor = cli.load_module("radio_readback_owner", ROOT / ".cache/p3-4-screening-20260922/supervisor.py")
    if args.mode == "launch":
        cli.require(not OUT.exists(), "preserve readback attempt")
        for name in ("intent.json", "result.json", "installed-mcu", "host"):
            s.checked(OUT / name)
        s.write(OUT / "intent.json", dict(source=cli.record(__file__), target_version=30247,
            scope="complete raw target and Boot confirmation; no reset, halt, flash or OTA"))
        print(supervisor.owned.launch(radio.AREA / "runtime/readback-scan-001", Path(__file__), ["worker"], 1200), flush=True)
    else:
        cli.require(supervisor.owned.in_job(), "finite readback owner required")
        worker(s)
