"""Read-only reconciliation after the phone's explicit radio-APK install rejection."""
import argparse
import json
from pathlib import Path
import runpy
import sys

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "Tools/ota"))
import p34_session as cli
import p34_radio_install as install

OUT = install.AREA / "install-reconcile-001"


def worker(s):
    b, d, p, lock = runpy.run_path(str(ROOT / "Tools/ota/p34_signing_migration.py"))["runtime"]()
    failed = s.read(install.OUT / "result.json")
    cli.require(failed["result"] == "RADIO_UPDATE_INCOMPLETE", "unexpected original outcome")
    commands = [json.loads(x) for x in (install.OUT / "usb/commands.jsonl").read_text(encoding="utf-8").splitlines()]
    attempts = [x for x in commands if x["args"][0] == "install"]
    cli.require(len(attempts) == 1 and attempts[0]["exit"] == 1 and
                "INSTALL_FAILED_ABORTED: User rejected permissions" in attempts[0]["stdout"], "exact system rejection required")
    value = dict(result="RECONCILIATION_INCOMPLETE", read_only_device=True, no_install=True, no_ota=True)
    try:
        with lock.device_lock(), d["usb"](b, p, OUT):
            p.phone_identity()
            value["installed"] = d["installed"](b, p, install.OLD_APK)
            cli.require(value["installed"] is not None, "old installed APK missing")
            pid = p.command(["shell", "pidof", install.PKG], check=False).strip()
            value["app_pid"] = pid or None
            snapshot = p.file_bytes(install.PKG, install.REMOTE + "/snapshot-1.jsonl", 16 * 1024 * 1024)
            config = p.file_bytes(install.PKG, "files/p34-experiment.json", 8192)
            cli.require(snapshot == (install.OUT / "snapshot.jsonl").read_bytes() and
                        config == (install.OUT / "runtime-config.json").read_bytes(), "data changed after rejected install")
            value["snapshot"] = s.raw(OUT / "snapshot.jsonl", snapshot)
            value["configuration"] = s.raw(OUT / "runtime-config.json", config)
            value["permissions"] = d["permission_state"](p.command(["shell", "dumpsys", "package", install.PKG]), 0)
            power = p.command(["shell", "dumpsys", "power"], timeout=30)
            value["power"] = s.raw(OUT / "power.txt", power.encode())
            value["power_summary"] = [x.strip() for x in power.splitlines() if any(k in x for k in
                ("mWakefulness=", "mInteractive=", "mIsPowered=", "mDisplayReady="))]
            value.update(result="OLD_APK_DATA_PRESERVED_AFTER_SYSTEM_REJECTION", original_snapshot_preserved=True,
                         configuration_preserved=True, new_apk_installed=False)
        value["usb_closed"] = True
    except Exception as error:
        value.update(error=type(error).__name__, detail=str(error))
    s.write(OUT / "result.json", dict(time=cli.now(), **value))
    print(json.dumps(value), flush=True)
    cli.require("error" not in value, "preserve reconciliation before further mutation")


if __name__ == "__main__":
    cli.require(Path.cwd() == ROOT and sys.flags.isolated and sys.flags.no_site and sys.dont_write_bytecode,
                "explicit root and isolated Python required")
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("mode", choices=("launch", "worker"))
    args = parser.parse_args()
    s = cli.Store(ROOT)
    supervisor = cli.load_module("radio_reconcile_owner", ROOT / ".cache/p3-4-screening-20260922/supervisor.py")
    if args.mode == "launch":
        cli.require(not OUT.exists(), "preserve reconciliation")
        for name in ("intent.json", "result.json", "snapshot.jsonl", "runtime-config.json", "power.txt", "usb", "host"):
            s.checked(OUT / name)
        s.write(OUT / "intent.json", dict(time=cli.now(), source=cli.record(__file__), no_install=True, read_only_device=True))
        print(supervisor.owned.launch(install.AREA / "runtime/install-reconcile", Path(__file__), ["worker"], 600), flush=True)
    else:
        cli.require(supervisor.owned.in_job(), "finite reconciliation owner required")
        worker(s)
