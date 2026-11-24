"""Same-package fixed-signer update; retain the original failed OTA snapshot."""
import argparse
import json
from pathlib import Path
import runpy
import sys

ROOT = Path(__file__).resolve().parents[2]
AREA = ROOT / ".cache/p34-connect-fix"
PKG = "com.wen.gaia.gaia.p34probe"
REMOTE = "files/p34-observations/1790882915541398-f0e7c878e47e73001842b7e8"


def main(attempt=1):
    source = runpy.run_path(str(ROOT / "Tools/ota/p34_signing_migration.py"))
    b, d, p, lock = source["runtime"]()
    b.require(attempt in (1, 2), "only the original and user-ready retry are admitted")
    if attempt == 2:
        previous = json.loads((AREA / "install-001/result.json").read_bytes())
        reconciled = json.loads((AREA / "install-reconcile-001/result.json").read_bytes())
        commands = [json.loads(line) for line in (AREA / "install-001/usb/commands.jsonl").read_text().splitlines()]
        installs = [row for row in commands if row["args"][0] == "install"]
        b.require(previous["result"] == "IN_PLACE_UPDATE_INCOMPLETE" and len(installs) == 1 and
                  "INSTALL_FAILED_ABORTED: User rejected permissions" in installs[0].get("stdout", "") and
                  reconciled["result"] == "OLD_APK_AND_DATA_PRESERVED_AFTER_SYSTEM_INSTALL_REJECTION" and
                  reconciled["usb_closed"], "previous installation was not a reconciled system rejection")
    out = b.checked(AREA / ("install-%03d" % attempt))
    b.require(not out.exists(), "installation already attempted; reconcile, never repeat blindly")
    for name in ("intent.json", "result.json", "health.json", "snapshot.jsonl", "runtime-config.json",
                 "stop-intent.json", "install-intent.json", "installed.json", "usb", "host"):
        b.checked(out / name)
    report = json.loads((AREA / "apk-g1/apk.json").read_bytes())
    cert = runpy.run_path(str(ROOT / "Tools/ota/p34_signing_artifacts.py"))
    b.require(report["sha"] == "e29c1392db7a1e0570b588f4d2f2c8d0d9c9c3ad" and
              report["metadata"]["application_id"] == PKG and
              report["certificate_sha256"] == cert["CERT"] and
              b.record(report["apk"]["path"]) == report["apk"] and
              cert["apk_certificate"](Path(report["apk"]["path"]).read_bytes()) == cert["CERT"],
              "same-package fixed-signer APK binding failed")
    b.require(len(report["host_reports"]) == 2, "two host reports required")
    for item in report["host_reports"]:
        b.require(b.record(item["path"]) == item, "host report changed")
        host = json.loads(Path(item["path"]).read_bytes())
        b.require(host["development_result"] == "PASS" and host["scope"] == "all" and
                  host["source_before"]["head"] == report["sha"], "exact both-host PASS required")
    original = ROOT / ".cache/p34-session/runs/20261001T191549-84800/cells/s04/finished/snapshot.jsonl"
    expected_snapshot = original.read_bytes()
    b.io.write_json(ROOT, out / "intent.json", dict(time=b.now(), source=b.record(__file__), apk=report["apk"],
        original_snapshot=b.record(original), no_uninstall=True, no_data_clear=True, no_ota=True))
    value = dict(result="IN_PLACE_UPDATE_INCOMPLETE", no_uninstall=True, no_data_clear=True, no_ota=True)
    try:
        with lock.device_lock(), d["usb"](b, p, out):
            p.phone_identity()
            b.require(d["installed"](b, p, source["NEW_SHA"]) is not None, "installed source changed")
            pid = p.command(["shell", "pidof", PKG], check=False).strip()
            b.require(pid in ("", "17127"), "a different App process requires inspection before installation")
            health_raw = p.file_bytes(PKG, REMOTE + "/health.json", 8192)
            health = json.loads(health_raw)
            b.require(health["healthy"] and health["lost"] == 0 and health["error"] is None and
                      health["upgradeStarts"] == health["upgradeEnds"] == 1 and
                      health["outcome"] == "not-completed", "original App is active or changed")
            raw = p.file_bytes(PKG, REMOTE + "/snapshot-1.jsonl", 16 * 1024 * 1024)
            b.require(raw == expected_snapshot, "original snapshot changed before update")
            config = p.file_bytes(PKG, "files/p34-experiment.json", 8192)
            for name, data in (("health.json", health_raw), ("snapshot.jsonl", raw), ("runtime-config.json", config)):
                source["raw"](b, out / name, data)
            before_permissions = d["permission_state"](p.command(["shell", "dumpsys", "package", PKG]), 0)
            b.io.write_json(ROOT, out / "stop-intent.json", dict(time=b.now(), completed_invocation=True,
                preserved_snapshot=b.record(out / "snapshot.jsonl")))
            p.command(["shell", "am", "force-stop", PKG])
            b.require(not p.command(["shell", "pidof", PKG], check=False).strip(), "old App did not stop")
            b.io.write_json(ROOT, out / "install-intent.json", dict(time=b.now(), apk=report["apk"], replace=True))
            reply = p.command(["install", "-r", "--no-streaming", report["apk"]["path"]], timeout=180)
            b.require(reply.strip().splitlines()[-1:] == ["Success"], "install outcome uncertain; do not repeat")
            installed = d["installed"](b, p, report["apk"]["sha256"])
            b.require(installed is not None, "new installed APK missing")
            b.io.write_json(ROOT, out / "installed.json", installed)
            b.require(p.file_bytes(PKG, REMOTE + "/snapshot-1.jsonl", 16 * 1024 * 1024) == raw and
                      p.file_bytes(PKG, "files/p34-experiment.json", 8192) == config, "App data changed during update")
            after_permissions = d["permission_state"](p.command(["shell", "dumpsys", "package", PKG]), 0)
            b.require(before_permissions == after_permissions and all(after_permissions.values()), "permissions changed")
            value.update(result="FIXED_SIGNER_IN_PLACE_UPDATE_VERIFIED", installed=installed,
                permissions=after_permissions, original_snapshot_preserved=True, configuration_preserved=True,
                app_launched=False)
        value["usb_closed"] = True
    except Exception as error:
        value.update(error=type(error).__name__, detail=str(error))
    b.io.write_json(ROOT, out / "result.json", dict(time=b.now(), **value))
    print(json.dumps(value), flush=True)
    b.require("error" not in value, "in-place update requires reconciliation")


if __name__ == "__main__":
    if not (Path.cwd() == ROOT and sys.flags.isolated and sys.flags.no_site and sys.dont_write_bytecode):
        raise RuntimeError("isolated explicit root required")
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--attempt", type=int, choices=(1, 2), default=1)
    main(parser.parse_args().attempt)
