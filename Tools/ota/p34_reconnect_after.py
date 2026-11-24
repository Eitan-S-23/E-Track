"""Retrieve delayed console output after the completed30244 OTA, never replay it."""
import argparse
import json
from pathlib import Path
import runpy
import sys

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "Tools/ota"))
import p34_session as cli

AREA = ROOT / ".cache/p34-connect-fix/followup"
OUT = AREA / "late-logcat-002"
TRIAL = AREA / "trial-001"
PKG = "com.wen.gaia.gaia.p34probe"
REMOTE = "files/p34-observations/1790891079051299-33907bf1f4188996f192722e"


def worker(s):
    for name in ("coordinator", "network", "s04"):
        state = s.read(TRIAL / "runtime" / name / "closed.json")
        cli.require(state["worker_exit"] == 0 and state["forced_termination"] is False, "previous owner unresolved")
    result = s.read(TRIAL / "cells/s04/result.json")
    cli.require(result["result"] == "FULL_INSTALL_VERIFIED", "completed target required")
    module = runpy.run_path(str(ROOT / "Tools/ota/p34_signing_migration.py"))
    b, d, p, lock = module["runtime"]()
    value = dict(result="LATE_LOGCAT_INCOMPLETE", no_ota=True, no_mcu=True, no_app_mutation=True)
    try:
        with lock.device_lock(), d["usb"](b, p, OUT):
            p.phone_identity()
            report = s.read(ROOT / ".cache/p34-connect-fix/apk-g1/apk.json")
            cli.require(d["installed"](b, p, report["apk"]["sha256"]) is not None, "installed APK changed")
            log = p.command(["logcat", "-d", "-v", "threadtime", "--pid=1998"], timeout=45, binary=True)
            value["logcat"] = s.raw(OUT / "logcat.log", log)
            snapshot = p.file_bytes(PKG, REMOTE + "/snapshot-1.jsonl", 16 * 1024 * 1024)
            cli.require(snapshot == (TRIAL / "cells/s04/finished/snapshot.jsonl").read_bytes(), "original snapshot changed")
            value["snapshot"] = s.raw(OUT / "snapshot.jsonl", snapshot)
            value["health"] = s.raw(OUT / "health.json", p.file_bytes(PKG, REMOTE + "/health.json", 8192))
            value["pid_now"] = p.command(["shell", "pidof", PKG], check=False).strip()
        value.update(result="ORIGINAL_30244_LOGS_RETRIEVED", usb_closed=True)
    except Exception as error:
        value.update(error=type(error).__name__, detail=str(error))
    s.write(OUT / "result.json", dict(time=cli.now(), **value))
    print(json.dumps(value), flush=True)
    cli.require("error" not in value, "late log retrieval failed; retain the existing upgrade")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("mode", choices=("launch", "worker"))
    args = parser.parse_args()
    s = cli.Store(ROOT)
    supervisor = cli.load_module("after_reconnect_owner", ROOT / ".cache/p3-4-screening-20260922/supervisor.py")
    if args.mode == "launch":
        cli.require(not OUT.exists(), "retrieval already reserved")
        for name in ("intent.json", "result.json", "logcat.log", "snapshot.jsonl", "health.json", "usb", "host"):
            s.checked(OUT / name)
        s.write(AREA / "late-logcat-001/result.json", dict(time=cli.now(), result="NOT_RUN_USB_ALREADY_CLOSED",
            device_commands=0, reason="borrow attempt stopped at owner preflight; fresh finite read-only window follows"))
        s.write(OUT / "intent.json", dict(time=cli.now(), source=cli.record(__file__), seconds=600,
            original=cli.record(TRIAL / "cells/s04/finished/snapshot.jsonl"), no_app_mutation=True, no_ota=True))
        print(supervisor.owned.launch(AREA / "runtime/late-logcat", Path(__file__), ["worker"], 600), flush=True)
    else:
        cli.require(supervisor.owned.in_job(), "finite owned retrieval required")
        worker(s)


if __name__ == "__main__":
    cli.require(Path.cwd() == ROOT and sys.flags.isolated and sys.flags.no_site and sys.dont_write_bytecode,
                "explicit root and isolated Python required")
    main()
