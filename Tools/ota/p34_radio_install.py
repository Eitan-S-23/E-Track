"""Same-package fixed-signer radio APK update; preserve completed30245 data."""
import argparse
import json
from pathlib import Path
import runpy
import sys

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "Tools/ota"))
import p34_session as cli

AREA = ROOT / ".cache/p34-radio-fix"
OUT = AREA / "install-001"
PKG = "com.wen.gaia.gaia.p34probe"
REMOTE = "files/p34-observations/1790896481244860-1d625871c806583d059b8535"
COMMIT = "254e78507d27aedc636cca3614272003e67bd369"
OLD_APK = "5d7b11ca58927a0ad6441c578a52ae3294e3a08d23980e1ee32561a326d4fc05"


def worker(s):
    b, d, p, lock = runpy.run_path(str(ROOT / "Tools/ota/p34_signing_migration.py"))["runtime"]()
    cert = runpy.run_path(str(ROOT / "Tools/ota/p34_signing_artifacts.py"))
    report = s.read(AREA / "apk-g1/apk.json")
    cli.require(report["sha"] == COMMIT and report["metadata"]["application_id"] == PKG and
                report["certificate_sha256"] == cert["CERT"] and cli.record(report["apk"]["path"]) == report["apk"] and
                cert["apk_certificate"](Path(report["apk"]["path"]).read_bytes()) == cert["CERT"], "APK provenance mismatch")
    hosts = set()
    for item in report["host_reports"]:
        cli.require(cli.record(item["path"]) == item, "CI report changed")
        data = s.read(item["path"])
        cli.require(data["development_result"] == "PASS" and data["scope"] == "all" and
                    data["source_before"]["head"] == COMMIT and data["source_before"]["clean"], "both exact CI passes required")
        hosts.add(json.dumps(data["host"], sort_keys=True))
    cli.require(len(hosts) == len(report["host_reports"]) == 2, "two distinct hosts required")
    original = ROOT / ".cache/p34-discovery-fix/trial-001"
    cli.require(s.read(original / "cells/s04/result.json")["result"] == "FULL_INSTALL_VERIFIED", "confirmed30245 required")
    for name in ("s04", "network", "coordinator"):
        owner = s.read(original / "runtime" / name / "closed.json")
        cli.require(owner["worker_exit"] == 0 and not owner["forced_termination"], "prior owner unresolved")
    expected = (original / "cells/s04/finished/snapshot.jsonl").read_bytes()
    cli.require(cli.record(original / "cells/s04/finished/snapshot.jsonl")["sha256"] ==
                "991a7ac61ba5939ae267f7d60b5b35e421e430031c89376b8907fafa3a5b5eb9", "original snapshot changed")
    value = dict(result="RADIO_UPDATE_INCOMPLETE", no_ota=True, no_uninstall=True, no_data_clear=True)
    try:
        with lock.device_lock(), d["usb"](b, p, OUT):
            p.phone_identity()
            cli.require(d["installed"](b, p, OLD_APK) is not None, "installed source APK changed")
            pid = p.command(["shell", "pidof", PKG], check=False).strip()
            cli.require(pid in ("", "10524"), "different App process requires reconciliation")
            health_raw = p.file_bytes(PKG, REMOTE + "/health.json", 8192)
            health = json.loads(health_raw)
            cli.require(health["healthy"] and health["lost"] == 0 and health["error"] is None and
                        health["upgradeStarts"] == health["upgradeEnds"] == 1 and health["outcome"] == "completed",
                        "App is no longer the completed invocation")
            raw = p.file_bytes(PKG, REMOTE + "/snapshot-1.jsonl", 16 * 1024 * 1024)
            cli.require(raw == expected, "completed snapshot changed")
            config = p.file_bytes(PKG, "files/p34-experiment.json", 8192)
            for name, data in (("health.json", health_raw), ("snapshot.jsonl", raw), ("runtime-config.json", config)):
                s.raw(OUT / name, data)
            permissions = d["permission_state"](p.command(["shell", "dumpsys", "package", PKG]), 0)
            cli.require(all(permissions.values()), "Bluetooth grants changed")
            s.write(OUT / "stop-intent.json", dict(time=cli.now(), completed_capture=health["captureId"]))
            p.command(["shell", "am", "force-stop", PKG])
            cli.require(not p.command(["shell", "pidof", PKG], check=False).strip(), "App did not stop")
            s.write(OUT / "install-intent.json", dict(time=cli.now(), apk=report["apk"], replace=True))
            reply = p.command(["install", "-r", "--no-streaming", report["apk"]["path"]], timeout=180)
            cli.require(reply.strip().splitlines()[-1:] == ["Success"], "installation outcome requires reconciliation")
            value["installed"] = d["installed"](b, p, report["apk"]["sha256"])
            cli.require(value["installed"] is not None, "installed APK differs")
            cli.require(p.file_bytes(PKG, REMOTE + "/snapshot-1.jsonl", 16 * 1024 * 1024) == raw and
                        p.file_bytes(PKG, "files/p34-experiment.json", 8192) == config, "data changed during update")
            after = d["permission_state"](p.command(["shell", "dumpsys", "package", PKG]), 0)
            cli.require(permissions == after, "permissions changed during update")
            value.update(result="FIXED_SIGNER_RADIO_UPDATE_VERIFIED", original_snapshot_preserved=True,
                         configuration_preserved=True, permissions=after, app_launched=False)
        value["usb_closed"] = True
    except Exception as error:
        value.update(error=type(error).__name__, detail=str(error))
    s.write(OUT / "result.json", dict(time=cli.now(), **value))
    print(json.dumps(value), flush=True)
    cli.require("error" not in value, "preserve installation outcome before another attempt")


def main():
    global OUT
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("mode", choices=("launch", "worker"))
    parser.add_argument("--attempt", choices=("001", "002"), default="001")
    args = parser.parse_args()
    s = cli.Store(ROOT)
    OUT = AREA / ("install-" + args.attempt)
    if args.attempt == "002":
        reconciled = s.read(AREA / "install-reconcile-001/result.json")
        cli.require(reconciled["result"] == "OLD_APK_DATA_PRESERVED_AFTER_SYSTEM_REJECTION" and
                    reconciled["usb_closed"] and not reconciled["new_apk_installed"],
                    "resolved prior system rejection required")
        for name in ("install", "install-reconcile"):
            closed = s.read(AREA / "runtime" / name / "closed.json")
            cli.require(not closed["forced_termination"] and
                        closed["worker_exit"] == (1 if name == "install" else 0),
                        "prior installation owners must be closed")
    supervisor = cli.load_module("radio_install_owner", ROOT / ".cache/p3-4-screening-20260922/supervisor.py")
    if args.mode == "launch":
        cli.require(not OUT.exists(), "installation already reserved")
        for name in ("intent.json", "result.json", "stop-intent.json", "install-intent.json", "health.json",
                     "snapshot.jsonl", "runtime-config.json", "usb", "host"):
            s.checked(OUT / name)
        s.write(OUT / "intent.json", dict(time=cli.now(), source=cli.record(__file__),
            apk_report=cli.record(AREA / "apk-g1/apk.json"), no_uninstall=True, no_data_clear=True, no_ota=True))
        owner = "install" if args.attempt == "001" else "install-" + args.attempt
        print(supervisor.owned.launch(AREA / "runtime" / owner, Path(__file__),
                                     ["worker", "--attempt", args.attempt], 900), flush=True)
    else:
        cli.require(supervisor.owned.in_job(), "finite owned installation required")
        worker(s)


if __name__ == "__main__":
    cli.require(Path.cwd() == ROOT and sys.flags.isolated and sys.flags.no_site and sys.dont_write_bytecode,
                "explicit root and isolated Python required")
    main()
