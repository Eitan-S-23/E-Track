"""Bounded post-install query smoke check; never sends BEGIN or starts OTA."""
import argparse
import json
from pathlib import Path
import re
import runpy
import sys
import time

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "Tools/ota"))
import p34_session as cli

AREA = ROOT / ".cache/p34-connect-fix"
OUT = AREA / "query-001"
PKG = "com.wen.gaia.gaia.p34probe"
TARGET = "02:00:00:00:00:01"


def worker(s):
    module = runpy.run_path(str(ROOT / "Tools/ota/p34_signing_migration.py"))
    b, d, p, lock = module["runtime"]()
    report = s.read(AREA / "apk-g1/apk.json")
    installed = s.read(AREA / "install-002/result.json")
    cli.require(installed["result"] == "FIXED_SIGNER_IN_PLACE_UPDATE_VERIFIED" and
                installed["installed"]["sha256"] == report["apk"]["sha256"] and installed["usb_closed"],
                "verified in-place update required")
    for name in ("launch.json", "result.json", "events.jsonl", "health-before.json", "health-after.json",
                 "checkpoint.jsonl", "observations.log", "logcat.log", "usb", "host"):
        s.checked(OUT / name)
    value = dict(result="QUERY_SMOKE_INCOMPLETE", no_ota=True, no_mcu_host_commands=True,
                 post_ota_cold_reconnect_acceptance=False)
    try:
        with lock.device_lock(), d["usb"](b, p, OUT):
            p.phone_identity()
            cli.require(d["installed"](b, p, report["apk"]["sha256"]) is not None, "installed APK changed")
            p.query.m = cli.load_module("connect_query_capture", ROOT / "Tools/ota/p34_observation.py")
            before_pid = p.command(["shell", "pidof", PKG], check=False).strip()
            cli.require(not before_pid or before_pid.isdigit(), "ambiguous App process")
            if not before_pid:
                s.write(OUT / "launch.json", dict(time=cli.now(), apk=report["apk"], start_requested=True))
                p.command(["shell", "am", "start", "-W", "-n", PKG + "/com.wen.gaia.gaia.MainActivity"], timeout=45)
            pid = p.command(["shell", "pidof", PKG]).strip()
            cli.require(pid.isdigit(), "App launch outcome uncertain")
            value["pid"] = int(pid)
            until = time.monotonic() + 150
            while time.monotonic() < until:
                names = p.command(["exec-out", "run-as", PKG, "ls", "-1", "files/p34-observations"]).splitlines()
                cli.require(names and len(names) <= 8 and all(re.fullmatch(r"\d{13,20}-[0-9a-f]{24}", n)
                                                           for n in names), "capture identity/room differs")
                remote = "files/p34-observations/" + sorted(names)[-1]
                header = p.command(["exec-out", "run-as", PKG, "head", "-n", "1", remote + "/events.jsonl"])
                if json.loads(header).get("pid") != int(pid):
                    time.sleep(2)
                    continue
                first = p.file_bytes(PKG, remote + "/health.json", 8192)
                events = p.file_bytes(PKG, remote + "/events.jsonl", 16 * 1024 * 1024)
                last = p.file_bytes(PKG, remote + "/health.json", 8192)
                for raw in (first, last):
                    health = json.loads(raw)
                    cli.require(health["healthy"] and health["lost"] == 0 and health["error"] is None and
                                health["upgradeStarts"] == health["upgradeEnds"] == 0, "unexpected transfer or capture failure")
                if json.loads(last)["producerLines"] == 0:
                    time.sleep(2)
                    continue
                query, checkpoint, messages = p.query.validate(events, first, last, pid=int(pid),
                    sentinel=report["metadata"]["device_observation"]["sentinel"], target=TARGET)
                if query["successfulQueries"]:
                    for name, raw in (("health-before.json", first), ("events.jsonl", events), ("health-after.json", last),
                                      ("checkpoint.jsonl", checkpoint), ("observations.log", messages.encode())):
                        s.raw(OUT / name, raw)
                    value.update(result="NEW_APK_QUERY_SUCCEEDED", query=query, remote=remote)
                    break
                time.sleep(2)
            log = p.command(["logcat", "-d", "-v", "threadtime", "--pid=" + pid], timeout=45, binary=True)
            value["logcat"] = s.raw(OUT / "logcat.log", log)
            lines = log.decode("utf-8", "replace").splitlines()
            identities = [line.split("OTA_OBS identity ", 1)[1] for line in lines
                          if "OTA_OBS identity " in line and "result=ok" in line]
            value["observed_identities"] = identities
            cli.require(p.command(["shell", "pidof", PKG]).strip() == pid, "App process changed while observing")
        value["usb_closed"] = True
    except Exception as error:
        value.update(error=type(error).__name__, detail=str(error))
    s.write(OUT / "result.json", dict(time=cli.now(), **value))
    print(json.dumps({k:v for k,v in value.items() if k != "query"}), flush=True)
    cli.require("error" not in value, "query smoke requires reconciliation")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("mode", choices=("launch", "worker"))
    args = parser.parse_args()
    s = cli.Store(ROOT)
    supervisor = cli.load_module("connect_query_owner", ROOT / ".cache/p3-4-screening-20260922/supervisor.py")
    if args.mode == "launch":
        cli.require(not OUT.exists(), "query smoke already reserved")
        s.write(OUT / "intent.json", dict(time=cli.now(), source=cli.record(__file__), no_ota=True,
            apk=cli.record(AREA / "apk-g1/apk.json"), seconds=600,
            scope="new APK normal connect/query only; not post-END cold reconnect acceptance"))
        print(supervisor.owned.launch(AREA / "runtime/query-001", Path(__file__), ["worker"], 600), flush=True)
    else:
        cli.require(supervisor.owned.in_job(), "finite owned query worker required")
        worker(s)


if __name__ == "__main__":
    cli.require(Path.cwd() == ROOT and sys.flags.isolated and sys.flags.no_site and sys.dont_write_bytecode,
                "isolated explicit root required")
    main()
