"""Preserve a healthy query-only capture after the host identity-adapter failure."""
import argparse
import hashlib
import json
from pathlib import Path
import runpy
import sys

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "Tools/ota"))
import p34_radio_followup as f

cli = f.cli
FAILED = f.AREA / "trials/priority"
OUT = f.AREA / "startup-recovery-002"


def idle(raw, capture):
    h = json.loads(raw)
    cli.require(h["captureId"] == capture and h["healthy"] is True and h["lost"] == 0 and
                h["error"] is None and h["upgradeStarts"] == h["upgradeEnds"] == 0 and h["outcome"] is None,
                "transfer may have started; preserve and reconcile, never replay")


def worker(s):
    inspected = s.read(f.AREA / "startup-inspect-001/result.json")
    cli.require(inspected["result"] == "CURRENT_APP_INSPECTED_NO_MUTATION" and inspected["usb_closed"], "inspection unresolved")
    prior = s.read(f.AREA / "startup-recovery-001/result.json")
    cli.require(prior["detail"] == "different App invocation" and
                not (f.AREA / "startup-recovery-001/stop-intent.json").exists(), "prior attempt may have mutated App")
    failure = s.read(FAILED / "cells/s04/result.json")
    cli.require(failure["error"] == "AttributeError: module 'recorder_fixed_envelope' has no attribute 'same_device'",
                "different startup failure")
    for name in ("s04", "network", "coordinator"):
        v = s.read(FAILED / "runtime" / name / "closed.json")
        cli.require(not v["forced_termination"], "old owner unresolved")
    b, d, p, lock = runpy.run_path(str(ROOT / "Tools/ota/p34_signing_migration.py"))["runtime"]()
    pkg = f.recovery.install.previous.PKG
    checked = lambda path, new=False: f.radio.backend.checked_phone_path(f.recovery.install.previous, p, path, new_leaf=new)
    def read(path):
        raw = p.command(["exec-out", "run-as", pkg, "head", "-c", "16777217", path], timeout=30, binary=True)
        cli.require(len(raw) <= 16777216, "file too large")
        return raw
    def exists(path):
        return p.command(["exec-out", "run-as", pkg, "ls", "-d", path], check=False).strip() == path
    def listing(path):
        return p.command(["exec-out", "run-as", pkg, "ls", "-1", path]).splitlines()
    value = dict(result="STARTUP_RECOVERY_INCOMPLETE", no_ota=True, no_delete=True)
    try:
        with lock.device_lock(), d["usb"](b, p, OUT):
            p.phone_identity()
            d["installed"](b, p, s.read(f.AREA / "apk-g1/apk.json")["apk"]["sha256"])
            launch = s.read(FAILED / "cells/s04/launch.json")
            pid = inspected["pid"]
            cli.require(p.command(["shell", "pidof", pkg], check=False).strip() == pid, "different App invocation")
            s.raw(OUT / "logcat.log", p.command(["logcat", "-d", "-v", "threadtime", "--pid=" + pid], timeout=45, binary=True))
            names = listing("files/p34-observations")
            cli.require(names == inspected["names"], "capture inventory changed since process reconciliation")
            cli.require(len(names) == len(set(names)) == 8 and all(f.radio.backend.CAPTURE_NAME.fullmatch(n) for n in names),
                        "unexpected capture inventory")
            capture = sorted(names)[-1]
            cli.require(capture != f.recovery.CAPTURE and capture != f.recovery.PROTECTED, "old capture selected")
            remote = "files/p34-observations/" + capture
            checked(remote)
            before = read(remote + "/health.json")
            s.raw(OUT / "health-before.json", before)
            idle(before, capture)
            config = read("files/p34-experiment.json")
            cli.require(config == (FAILED / "cells/s04/runtime-config.json").read_bytes(), "config changed")
            events = read(remote + "/events.jsonl")
            rows = events.splitlines()
            cli.require(len(rows) >= 2, "no original producer stamp")
            header, stamp = (json.loads(row) for row in rows[:2])
            cli.require(header["pid"] == launch["pid"] and header["captureId"] == capture and
                        header["sentinel"] == s.read(f.AREA / "apk-g1/apk.json")["metadata"]["device_observation"]["sentinel"],
                        "capture identity differs")
            f.radio.verify_radio(f.fixed_envelope(), stamp["message"], json.loads(config), hashlib.sha256(config).hexdigest())
            idle(read(remote + "/health.json"), capture)
            s.write(OUT / "stop-intent.json", dict(pid=pid, capture=capture, zero_starts=True))
            p.command(["shell", "am", "force-stop", pkg])
            cli.require(not p.command(["shell", "pidof", pkg], check=False).strip(), "App not stopped")
            files = listing(remote)
            cli.require(set(files) in ({"health.json", "events.jsonl"}, {"health.json", "events.jsonl", "health.json.tmp"}),
                        "unexpected query capture files")
            data = {}
            for name in files:
                checked(remote + "/" + name)
                data[name] = read(remote + "/" + name)
            idle(data["health.json"], capture)
            inspected_capture = next(item for item in inspected["captures"] if item["name"] == capture)
            cli.require(data["events.jsonl"] == Path(inspected_capture["events"]["path"]).read_bytes(),
                        "old query capture changed after process reconciliation")
            cli.require(not any(json.loads(row).get("kind") in ("upgrade-start", "upgrade-end")
                                for row in data["events.jsonl"].splitlines()), "invocation appeared; do not retire")
            target = "files/p34-archived-observations/" + capture
            retired = "files/p34-retired-configs/" + hashlib.sha256(config).hexdigest() + ".json"
            checked(target, True)
            checked(retired, True)
            cli.require(not exists(target) and not exists(retired), "archive collision")
            copies = {name:s.raw(OUT / "capture" / name, raw) for name, raw in data.items()}
            config_copy = s.raw(OUT / "runtime-config.json", config)
            cli.require(all(cli.record(item["path"]) == item for item in [*copies.values(), config_copy]), "host backup changed")
            s.write(OUT / "move-intent.json", dict(source=checked(remote), target=checked(target, True),
                config_source=checked("files/p34-experiment.json"), config_target=checked(retired, True), files=copies, config=config_copy))
            p.command(["exec-out", "run-as", pkg, "mv", "-n", remote, target])
            cli.require(not exists(remote) and set(listing(target)) == set(data) and
                        all(read(target + "/" + name) == raw for name,raw in data.items()), "capture move unresolved")
            p.command(["exec-out", "run-as", pkg, "mv", "-n", "files/p34-experiment.json", retired])
            cli.require(not exists("files/p34-experiment.json") and read(retired) == config and
                        set(listing("files/p34-observations")) == set(names) - {capture}, "retirement unresolved")
            value.update(result="PRESTART_QUERY_ARCHIVED_NO_TRANSFER", capture=capture, files=copies, config=config_copy,
                         zero_upgrade_starts=True, app_stopped=True, original_failure=cli.record(FAILED / "cells/s04/result.json"))
        value["usb_closed"] = True
    except Exception as error:
        value.update(error=type(error).__name__, detail=str(error))
    s.write(OUT / "result.json", dict(time=cli.now(), **value))
    print(json.dumps(value), flush=True)
    cli.require("error" not in value, "startup recovery unresolved; no blind retry")


if __name__ == "__main__":
    cli.require(Path.cwd() == ROOT and sys.flags.isolated and sys.flags.no_site and sys.dont_write_bytecode,
                "explicit root and isolated Python required")
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("mode", choices=("launch", "worker"))
    args = parser.parse_args()
    s = cli.Store(ROOT)
    supervisor = cli.load_module("startup_recovery_owner", ROOT / ".cache/p3-4-screening-20260922/supervisor.py")
    if args.mode == "launch":
        cli.require(not OUT.exists(), "preserve startup recovery")
        for name in ("intent.json", "result.json", "logcat.log", "health-before.json", "stop-intent.json", "move-intent.json",
                     "capture", "runtime-config.json", "usb", "host"):
            s.checked(OUT / name)
        s.write(OUT / "intent.json", dict(source=cli.record(__file__), no_ota=True, no_delete=True,
            scope="verify zero starts, archive exact query capture and retired configuration; no firmware change"))
        print(supervisor.owned.launch(f.radio.AREA / "runtime/startup-recovery-002", Path(__file__), ["worker"], 600), flush=True)
    else:
        cli.require(supervisor.owned.in_job(), "finite recovery owner required")
        worker(s)
