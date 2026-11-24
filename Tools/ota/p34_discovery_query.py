"""Query-only smoke check for the installed discovery candidate; no OTA start."""
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

AREA = ROOT / ".cache/p34-discovery-fix"
OUT = AREA / "query-001"
PKG = "com.wen.gaia.gaia.p34probe"
TARGET = "02:00:00:00:00:01"
COMMIT = "89fee42f548e99eb5bc437aa736d2e9cc8ddf5de"
RAW_SHA = "175ed1a4494f1945d781321979d207898031854b48aaeccc9f2f40c98e191eee"


def worker(s):
    b, d, p, lock = runpy.run_path(str(ROOT / "Tools/ota/p34_signing_migration.py"))["runtime"]()
    report = s.read(AREA / "apk-g1/apk.json")
    installed = s.read(AREA / "install-001/result.json")
    cli.require(report["sha"] == COMMIT and cli.record(report["apk"]["path"]) == report["apk"] and
                installed["result"] == "FIXED_SIGNER_DISCOVERY_UPDATE_VERIFIED" and
                installed["installed"]["sha256"] == report["apk"]["sha256"] and installed["usb_closed"],
                "verified discovery update required")
    result = dict(result="QUERY_SMOKE_INCOMPLETE", no_ota=True, no_mcu_host_commands=True,
                  post_ota_cold_reconnect_acceptance=False)
    try:
        with lock.device_lock(), d["usb"](b, p, OUT):
            p.phone_identity()
            cli.require(d["installed"](b, p, report["apk"]["sha256"]) is not None, "installed APK changed")
            p.query.m = cli.load_module("discovery_query_capture", ROOT / "Tools/ota/p34_observation.py")
            before_pid = p.command(["shell", "pidof", PKG], check=False).strip()
            cli.require(not before_pid, "unexpected App process; reconcile before launch")
            s.write(OUT / "launch.json", dict(time=cli.now(), apk=report["apk"], no_start_tap=True))
            p.command(["shell", "am", "start", "-W", "-n", PKG + "/com.wen.gaia.gaia.MainActivity"], timeout=45)
            pid = p.command(["shell", "pidof", PKG]).strip()
            cli.require(pid.isdigit(), "App launch outcome uncertain")
            result["pid"] = int(pid)
            until = time.monotonic() + 150
            while time.monotonic() < until:
                names = p.command(["exec-out", "run-as", PKG, "ls", "-1", "files/p34-observations"]).splitlines()
                cli.require(names and len(names) <= 8 and all(re.fullmatch(r"\d{13,20}-[0-9a-f]{24}", n)
                                                           for n in names), "invalid capture store")
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
                                health["upgradeStarts"] == health["upgradeEnds"] == 0,
                                "unexpected transfer or capture failure")
                if json.loads(last)["producerLines"]:
                    query, checkpoint, messages = p.query.validate(events, first, last, pid=int(pid),
                        sentinel=report["metadata"]["device_observation"]["sentinel"], target=TARGET)
                    if query["successfulQueries"]:
                        for name, data in (("health-before.json", first), ("events.jsonl", events),
                                           ("health-after.json", last), ("checkpoint.jsonl", checkpoint),
                                           ("observations.log", messages.encode())):
                            s.raw(OUT / name, data)
                        result.update(query=query, remote=remote)
                        break
                time.sleep(2)
            log = p.command(["logcat", "-d", "-v", "threadtime", "--pid=" + pid], timeout=45, binary=True)
            result["logcat"] = s.raw(OUT / "logcat.log", log)
            identities = [line.split("OTA_OBS identity ", 1)[1] for line in log.decode("utf-8", "replace").splitlines()
                          if "OTA_OBS identity " in line and "result=ok" in line]
            result["observed_identities"] = identities
            expected = ("addr=02:00:00:00:00:01 result=ok wire=E-Track model=e-track-at32f435 "
                        "vcode=30244 hw=1 layout=1 boot=1 proto=1 window=32 sha=" + RAW_SHA)
            cli.require("query" in result and expected in identities, "successful full30244 query not observed")
            cli.require(p.command(["shell", "pidof", PKG]).strip() == pid, "App process changed")
            result["result"] = "DISCOVERY_APK_QUERY_SUCCEEDED"
        result["usb_closed"] = True
    except Exception as error:
        result.update(error=type(error).__name__, detail=str(error))
    s.write(OUT / "result.json", dict(time=cli.now(), **result))
    print(json.dumps(result), flush=True)
    cli.require("error" not in result, "query smoke requires reconciliation")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("mode", choices=("launch", "worker"))
    args = parser.parse_args()
    s = cli.Store(ROOT)
    supervisor = cli.load_module("discovery_query_owner", ROOT / ".cache/p3-4-screening-20260922/supervisor.py")
    for name in ("intent.json", "launch.json", "result.json", "events.jsonl", "health-before.json", "health-after.json",
                 "checkpoint.jsonl", "observations.log", "logcat.log", "usb", "host"):
        s.checked(OUT / name)
    if args.mode == "launch":
        cli.require(not OUT.exists(), "query already reserved; preserve original outcome")
        s.write(OUT / "intent.json", dict(time=cli.now(), source=cli.record(__file__), no_ota=True,
            apk=cli.record(AREA / "apk-g1/apk.json"), seconds=600))
        print(supervisor.owned.launch(AREA / "runtime/query", Path(__file__), ["worker"], 600), flush=True)
    else:
        cli.require(supervisor.owned.in_job(), "finite detached query owner required")
        worker(s)


if __name__ == "__main__":
    cli.require(Path.cwd() == ROOT and sys.flags.isolated and sys.flags.no_site and sys.dont_write_bytecode,
                "isolated explicit root required")
    main()
