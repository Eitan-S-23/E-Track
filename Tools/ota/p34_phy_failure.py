"""Read original unhealthy PHY capture and Android ring without any OTA replay."""
import json
from pathlib import Path
import re
import runpy
import sys

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "Tools/ota"))
import p34_session as cli

AREA = ROOT / ".cache/p34-phy"
TRIAL = AREA / "trials/observe"
OUT = AREA / "reconcile-001"
PKG = "com.wen.gaia.gaia.p34probe"
CAPTURE = "1791049540786102-976637933aaa484110151ba7"
PID = 25415


def inputs(s):
    launch = s.read(TRIAL / "cells/s04/launch.json")
    cli.require(launch["pid"] == PID and launch["apk"]["sha256"] ==
        "7cafe0c20956cd6791f9c9a495feeac19843cd390d09b0fdcdee4ecb4edc748a", "original invocation differs")
    for name in ("coordinator", "network", "s04"):
        closed = s.read(TRIAL / "runtime" / name / "closed.json")
        cli.require(not closed["forced_termination"] and closed["worker_exit"] in (0, 1), "old worker unresolved")
    return launch


def worker(s):
    launch = inputs(s)
    b, d, p, lock = runpy.run_path(str(ROOT / "Tools/ota/p34_signing_migration.py"))["runtime"]()
    result = dict(result="PHY_ORIGINAL_COLLECTION_INCOMPLETE", no_ota=True, phone_read_only=True,
                  no_system_report=True, original_capture=CAPTURE, original_pid=PID)
    try:
        with lock.device_lock(), d["usb"](b, p, OUT):
            p.phone_identity()
            cli.require(d["installed"](b, p, launch["apk"]["sha256"]) is not None, "APK changed")
            result["live_pid"] = p.command(["shell", "pidof", PKG], check=False).strip()
            root = "files/p34-observations/" + CAPTURE
            before = p.file_bytes(PKG, root + "/health.json", 8192)
            s.raw(OUT / "health-before.json", before)
            names = p.command(["exec-out", "run-as", PKG, "ls", "-1", root]).splitlines()
            cli.require(set(names) <= {"events.jsonl", "health.json", "health.json.tmp",
                *["snapshot-%d.jsonl" % n for n in range(1, 5)]}, "unknown capture members")
            saved = []
            for name in names:
                if name == "health.json.tmp": continue
                saved.append(s.raw(OUT / "capture" / name, p.file_bytes(PKG, root + "/" + name, 16785408)))
            after = p.file_bytes(PKG, root + "/health.json", 8192)
            s.raw(OUT / "health-after.json", after)
            config = p.file_bytes(PKG, "files/p34-experiment.json", 8192)
            cli.require(config == (TRIAL / "cells/s04/runtime-config.json").read_bytes(), "config changed")
            s.raw(OUT / "runtime-config.json", config)
            raw = p.command(["logcat", "-d", "-v", "threadtime", "-t", "30000", "--pid=" + str(PID)],
                            timeout=45, binary=True)
            cli.require(len(raw) <= 16 * 1024 * 1024, "Android ring bound")
            ring = s.raw(OUT / "android-original.log", raw)
            lines = raw.decode("utf-8", "replace").splitlines()
            markers = [line for line in lines if any(key in line for key in
                ("OTA_PHY ", "MONO_END_ACK_OK", "MONO_REBOOT_VERIFIED", "OTA_IDENTITY ", "OTA_LINK_STATS "))]
            result.update(result="PHY_ORIGINAL_BYTES_COLLECTED", health=json.loads(after), files=saved,
                android_ring=ring, markers=markers, measurement_eligible=False,
                warning="Unhealthy App snapshot remains ineligible; Android ring is only corroboration")
        result["usb_closed"] = True
    except Exception as error:
        result.update(error=type(error).__name__, detail=str(error))
    s.write(OUT / "result.json", dict(time=cli.now(), **result))
    print(json.dumps(result), flush=True)


if __name__ == "__main__":
    cli.require(Path.cwd() == ROOT and sys.flags.isolated and sys.flags.no_site and sys.dont_write_bytecode,
                "isolated explicit root required")
    cli.require(sys.argv[1:] in (["launch"], ["worker"]), "exact mode required")
    s = cli.Store(ROOT)
    inputs(s)
    owner = cli.load_module("phy_failure_owner", ROOT / ".cache/p3-4-screening-20260922/supervisor.py")
    if sys.argv[1] == "launch":
        cli.require(not OUT.exists(), "preserve original collection")
        for name in ("intent.json", "result.json", "capture", "health-before.json", "health-after.json",
                     "runtime-config.json", "android-original.log", "host", "usb"):
            s.checked(OUT / name)
        s.write(OUT / "intent.json", dict(time=cli.now(), source=cli.record(__file__),
            phone_read_only=True, no_ota=True, no_install=True, no_system_report=True))
        print(owner.owned.launch(s.checked(AREA / "runtime/reconcile-001"), Path(__file__), ["worker"], 600))
    else:
        cli.require(owner.owned.in_job() and s.read(OUT / "intent.json")["source"] == cli.record(__file__), "finite source-pinned owner required")
        worker(s)
