"""Fixed-certificate in-place update after fully verified30244; preserve all evidence."""
import argparse
import json
from pathlib import Path
import runpy
import sys

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "Tools/ota"))
import p34_session as cli

AREA = ROOT / ".cache/p34-discovery-fix"
OUT = AREA / "install-001"
PKG = "com.wen.gaia.gaia.p34probe"
REMOTE = "files/p34-observations/1790891079051299-33907bf1f4188996f192722e"
COMMIT = "89fee42f548e99eb5bc437aa736d2e9cc8ddf5de"
OLD_APK = "5fd96270b90f64c706ce8eaeba4b88a3c3df1b1ea90763369e118adb9f23a366"


def worker(s):
    b, d, p, lock = runpy.run_path(str(ROOT / "Tools/ota/p34_signing_migration.py"))["runtime"]()
    cert = runpy.run_path(str(ROOT / "Tools/ota/p34_signing_artifacts.py"))
    report = s.read(AREA / "apk-g1/apk.json")
    cli.require(report["sha"] == COMMIT and report["metadata"]["application_id"] == PKG and
                report["certificate_sha256"] == cert["CERT"] and
                cli.record(report["apk"]["path"]) == report["apk"] and
                cert["apk_certificate"](Path(report["apk"]["path"]).read_bytes()) == cert["CERT"],
                "fixed certificate/commit/APK mismatch")
    hosts = set()
    for item in report["host_reports"]:
        cli.require(cli.record(item["path"]) == item, "CI report changed")
        data = s.read(item["path"])
        cli.require(data["development_result"] == "PASS" and data["scope"] == "all" and
                    data["source_before"]["head"] == COMMIT, "exact both-host PASS required")
        hosts.add(json.dumps(data["host"], sort_keys=True))
    cli.require(len(hosts) == len(report["host_reports"]) == 2, "two distinct CI hosts required")
    original = ROOT / ".cache/p34-connect-fix/followup/trial-001"
    cli.require(s.read(original / "cells/s04/result.json")["result"] == "FULL_INSTALL_VERIFIED",
                "original completed OTA must remain verified")
    for name in ("s04", "network", "coordinator"):
        owner = s.read(original / "runtime" / name / "closed.json")
        cli.require(owner["worker_exit"] == 0 and owner["forced_termination"] is False, "old owner unresolved")
    expected = (original / "cells/s04/finished/snapshot.jsonl").read_bytes()
    value = dict(result="IN_PLACE_UPDATE_INCOMPLETE", no_ota=True, no_uninstall=True, no_data_clear=True)
    try:
        with lock.device_lock(), d["usb"](b, p, OUT):
            p.phone_identity()
            cli.require(d["installed"](b, p, OLD_APK) is not None, "installed source APK changed")
            pid = p.command(["shell", "pidof", PKG], check=False).strip()
            cli.require(pid in ("", "1998"), "different App process requires reconciliation")
            health_raw = p.file_bytes(PKG, REMOTE + "/health.json", 8192)
            health = json.loads(health_raw)
            cli.require(health["healthy"] and health["lost"] == 0 and health["error"] is None and
                        health["upgradeStarts"] == health["upgradeEnds"] == 1 and health["outcome"] == "completed",
                        "App is no longer the completed invocation")
            raw = p.file_bytes(PKG, REMOTE + "/snapshot-1.jsonl", 16 * 1024 * 1024)
            cli.require(raw == expected, "successful original snapshot changed")
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
            cli.require(value["installed"] is not None, "installed APK mismatch")
            cli.require(p.file_bytes(PKG, REMOTE + "/snapshot-1.jsonl", 16 * 1024 * 1024) == raw and
                        p.file_bytes(PKG, "files/p34-experiment.json", 8192) == config,
                        "data changed during in-place update")
            after = d["permission_state"](p.command(["shell", "dumpsys", "package", PKG]), 0)
            cli.require(permissions == after, "permissions changed during update")
            value.update(result="FIXED_SIGNER_DISCOVERY_UPDATE_VERIFIED", original_snapshot_preserved=True,
                configuration_preserved=True, permissions=after, app_launched=False)
        value["usb_closed"] = True
    except Exception as error:
        value.update(error=type(error).__name__, detail=str(error))
    s.write(OUT / "result.json", dict(time=cli.now(), **value))
    print(json.dumps(value), flush=True)
    cli.require("error" not in value, "preserve installation outcome before another attempt")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("mode", choices=("launch", "worker"))
    args = parser.parse_args()
    s = cli.Store(ROOT)
    supervisor = cli.load_module("discovery_install_owner", ROOT / ".cache/p3-4-screening-20260922/supervisor.py")
    if args.mode == "launch":
        cli.require(not OUT.exists(), "install already reserved; inspect original result")
        for name in ("intent.json", "result.json", "stop-intent.json", "install-intent.json", "health.json",
                     "snapshot.jsonl", "runtime-config.json", "usb", "host"):
            s.checked(OUT / name)
        s.write(OUT / "intent.json", dict(time=cli.now(), source=cli.record(__file__),
            apk_report=cli.record(AREA / "apk-g1/apk.json"), no_uninstall=True, no_data_clear=True, no_ota=True))
        print(supervisor.owned.launch(AREA / "runtime/install", Path(__file__), ["worker"], 900), flush=True)
    else:
        cli.require(supervisor.owned.in_job(), "finite owned installation required")
        worker(s)


if __name__ == "__main__":
    cli.require(Path.cwd() == ROOT and sys.flags.isolated and sys.flags.no_site and sys.dont_write_bytecode,
                "explicit root and isolated Python required")
    main()
