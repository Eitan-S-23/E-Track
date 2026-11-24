"""Reusable read-only diagnosis attached to an explicitly named live OTA owner."""
import argparse
import datetime
import json
from pathlib import Path
import re
import runpy
import sys
import time

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "Tools/ota"))
import p34_session as cli
import p34_capture_capacity as capacity


def classify(value):
    if value["installed_sha"] != value["expected_sha"]:
        return "APK_MISMATCH"
    if not value["pid"]:
        return "APP_NOT_RUNNING"
    current = [x for x in value["captures"] if str(x["header"].get("pid")) == value["pid"]]
    if len(current) > 1:
        return "AMBIGUOUS_CURRENT_CAPTURE"
    if not current:
        return "NO_CURRENT_CAPTURE_STORE_FULL" if len(value["captures"]) >= 8 else "CURRENT_CAPTURE_MISSING"
    h = current[0]["health"]
    if h["upgradeStarts"] > h["upgradeEnds"]:
        return "TRANSFER_ACTIVE_OR_UNRESOLVED"
    if not h["healthy"] or h["lost"] or h["error"] is not None:
        return "RECORDER_FAILED"
    if h["upgradeStarts"]:
        return "CAPTURE_ALREADY_USED"
    if value["pid"] != str(value["expected_pid"]):
        return "HOST_PID_CHANGED"
    if not value["config_matches"]:
        return "CONFIG_MISMATCH"
    if not value["network_live"]:
        return "DOWNLOAD_SERVICE_CLOSED"
    if not current[0]["health"]["producerLines"]:
        return "WAITING_FOR_PRODUCER"
    return "RECORDER_READY_PACKAGE_ADMISSION_STILL_REQUIRED"


def worker(s, run, out):
    b, _, phone, _ = runpy.run_path(str(ROOT / "Tools/ota/p34_signing_migration.py"))["runtime"]()
    launch = s.read(run / "cells/s04/launch.json")
    pkg = launch["component"].split("/")[0]
    cli.require(pkg == "com.wen.gaia.gaia.p34probe", "only the bound diagnostic package is supported")
    usb = run / "cells/s04/usb"
    ready = s.read(usb / "ready.json")
    cli.require(ready["source"] == cli.record(phone.__file__) and ready["serial"] == phone.SERIAL and
                ready["port"] == phone.PORT and cli.record(phone.ADB)["sha256"] == phone.ADB_SHA,
                "USB owner/tool binding changed")
    host = cli.load_module("runtime_doctor_host", ROOT / ".cache/project-governance-20260922/run.py")
    host.OUT = out
    env = host.environment()
    android = s.checked(out / "host/home/.android")
    android.mkdir(parents=True, exist_ok=True)
    for name in ("ADB_TRACE", "ADB_SERVER_SOCKET", "ANDROID_SERIAL", "ANDROID_LOG_TAGS"):
        env.pop(name, None)
    env.update(ANDROID_USER_HOME=str(android), ANDROID_SDK_HOME=str(android.parent),
               ADB_VENDOR_KEYS="C:/Users/SU/.android/adbkey", ANDROID_ADB_SERVER_PORT=str(phone.PORT))
    key = cli.record(Path(env["ADB_VENDOR_KEYS"]))
    calls = []
    def command(args, *, binary=False, check=True):
        cli.require(not (usb / "closed.json").exists() and not (run / "runtime/s04/closed.json").exists() and
                    s.read(usb / "ready.json") == ready and phone.alive(), "active USB owner closed; no server restart")
        cli.require(datetime.datetime.fromisoformat(ready["deadline"]).timestamp() - time.time() > 45,
                    "USB owner deadline too near")
        code, data, error = phone.execute(phone.BASE + args, timeout=30, env=env)
        calls.append(dict(args=args, exit=code, bytes=len(data), error=error.decode("utf-8", "replace")))
        s.write(out / "commands.json", calls, replace=(out / "commands.json").exists())
        cli.require(not check or code == 0, "read-only command failed")
        return data if binary else data.decode("utf-8", "replace")
    value = dict(result="DOCTOR_INCOMPLETE", run=str(run), no_phone_mutation=True, no_server_start_or_stop=True,
                 expected_pid=launch["pid"], expected_sha=launch["apk"]["sha256"], captures=[])
    try:
        cli.require(command(["get-serialno"]).strip() == phone.SERIAL and
                    command(["shell", "getprop", "ro.product.model"]).strip() == "V2312A", "wrong phone")
        path = command(["shell", "pm", "path", "--user", "0", pkg]).strip()
        cli.require(re.fullmatch(r"package:/data/app/[A-Za-z0-9/_.=+~-]+/base\.apk", path), "unexpected installed path")
        value["installed_sha"] = command(["shell", "sha256sum", path[8:]]).split()[0]
        value["pid"] = command(["shell", "pidof", pkg], check=False).strip()
        cli.require(not value["pid"] or value["pid"].isdigit(), "ambiguous process")
        power = command(["shell", "dumpsys", "power"])
        s.raw(out / "power.txt", power.encode())
        value["awake"] = "mWakefulness=Awake" in power
        config = command(["exec-out", "run-as", pkg, "head", "-c", "8193", "files/p34-experiment.json"], binary=True)
        cli.require(len(config) <= 8192, "configuration too large")
        value["config"] = s.raw(out / "runtime-config.json", config)
        value["config_matches"] = config == (run / "cells/s04/runtime-config.json").read_bytes()
        names = command(["exec-out", "run-as", pkg, "ls", "-1", "files/p34-observations"]).splitlines()
        cli.require(len(names) <= 16 and len(names) == len(set(names)) and
                    all(re.fullmatch(r"\d{13,20}-[0-9a-f]{24}", n) for n in names), "capture inventory invalid")
        for name in sorted(names):
            remote = "files/p34-observations/" + name
            raw = command(["exec-out", "run-as", pkg, "head", "-c", "8193", remote + "/health.json"], binary=True)
            header = command(["exec-out", "run-as", pkg, "head", "-n", "2", remote + "/events.jsonl"], binary=True)
            cli.require(len(raw) <= 8192 and len(header) <= 32768 and header.splitlines(), "record metadata bound")
            value["captures"].append(dict(name=name, health=json.loads(raw), header=json.loads(header.splitlines()[0]),
                health_record=s.raw(out / name / "health.json", raw), header_record=s.raw(out / name / "header.jsonl", header)))
        if value["pid"]:
            value["logcat"] = s.raw(out / "logcat.log", command(["logcat", "-d", "-v", "threadtime",
                "--pid=" + value["pid"]], binary=True))
        cli.require(command(["shell", "pidof", pkg], check=False).strip() == value["pid"], "process changed during diagnosis")
        value["network_live"] = (run / "live-network.json").exists() and not (run / "runtime/network/closed.json").exists()
        value["result"] = classify(value)
    except Exception as error:
        value.update(error=type(error).__name__, detail=str(error))
    cli.require(cli.record(Path(env["ADB_VENDOR_KEYS"])) == key, "ADB key changed")
    s.write(out / "result.json", dict(time=cli.now(), **value))
    print(json.dumps({k:v for k,v in value.items() if k != "captures"}), flush=True)
    cli.require("error" not in value, "diagnostic collection incomplete; inspect original result")


def recover(s, run, out, diagnosis):
    observed = s.read(s.checked(diagnosis))
    cli.require(observed["run"] == str(run) and observed["result"] == "NO_CURRENT_CAPTURE_STORE_FULL" and
                observed["config_matches"] and observed["installed_sha"] == observed["expected_sha"],
                "recovery is limited to diagnosed missing-current-capture capacity failures")
    for name in ("coordinator", "network", "s04"):
        owner = s.read(run / "runtime" / name / "closed.json")
        cli.require(not owner["forced_termination"], "prior owner unresolved")
    launch = s.read(run / "cells/s04/launch.json")
    pkg = launch["component"].split("/")[0]
    metadata = s.read(s.checked(Path(launch["apk"]["path"]).with_suffix(".json")))
    cli.require(cli.record(launch["apk"]["path"]) == launch["apk"] and metadata["sha256"] == launch["apk"]["sha256"],
                "APK evidence changed")
    config = (run / "cells/s04/runtime-config.json").read_bytes()
    expected = json.loads(config)
    known = set()
    for path in (run / "cells/s04/runtime-config.json", run / "prestart-phone/app/runtime-config.json",
                 run / "cells/s04/previous-app/runtime-config.json"):
        if path.exists():
            known.add(cli.record(s.checked(path))["sha256"])
    b,d,p,lock = runpy.run_path(str(ROOT / "Tools/ota/p34_signing_migration.py"))["runtime"]()
    value = dict(result="PRESTART_RECOVERY_INCOMPLETE", no_ota=True, no_delete=True, diagnosis=cli.record(diagnosis))
    try:
        with lock.device_lock(), d["usb"](b,p,out):
            p.phone_identity()
            cli.require(d["installed"](b,p,observed["expected_sha"]) is not None, "installed App changed")
            cli.require(p.command(["shell","pidof",pkg],check=False).strip() == observed["pid"], "diagnosed process changed")
            names = p.command(["exec-out","run-as",pkg,"ls","-1","files/p34-observations"]).splitlines()
            cli.require(set(names) == {x["name"] for x in observed["captures"]}, "capture inventory changed")
            for item in observed["captures"]:
                remote = "files/p34-observations/" + item["name"]
                header = json.loads(p.command(["exec-out","run-as",pkg,"head","-n","1",remote+"/events.jsonl"]))
                health = json.loads(p.file_bytes(pkg,remote+"/health.json",8192))
                cli.require(str(header["pid"]) != observed["pid"] and health["upgradeStarts"] == health["upgradeEnds"],
                            "current/unfinished recording appeared; preserve state")
            cli.require(p.file_bytes(pkg,"files/p34-experiment.json",8192) == config, "configuration changed")
            s.write(out/"stop-intent.json",dict(pid=observed["pid"], reason="exact process has no recorder at full capacity; OTA is fail-closed"))
            p.command(["shell","am","force-stop",pkg])
            capacity.ensure_capacity(s,p,out/"capacity",package=pkg,sentinel=metadata["device_observation"]["sentinel"],
                target=expected["target"],known_configs=known)
            raw = s.raw(out/"runtime-config.json",config)
            target = "files/p34-retired-configs/"+raw["sha256"]+".json"
            ctx = type("Context",(),{"PKG":pkg})()
            capacity.backend.checked_phone_path(ctx,p,target,new_leaf=True)
            cli.require(p.command(["exec-out","run-as",pkg,"ls","-d",target],check=False).strip()!=target,
                        "configuration already archived")
            source = capacity.backend.checked_phone_path(ctx,p,"files/p34-experiment.json")
            cli.require(p.file_bytes(pkg,"files/p34-experiment.json",8192)==config,"configuration changed after stopping")
            s.write(out/"retire-intent.json",dict(source=source,target=target,config=raw))
            p.command(["exec-out","run-as",pkg,"mv","-n","files/p34-experiment.json",target])
            cli.require(p.file_bytes(pkg,target,8192)==config and
                        p.command(["exec-out","run-as",pkg,"ls","files/p34-experiment.json"],check=False).strip()!=
                        "files/p34-experiment.json", "configuration retirement unresolved")
            value.update(result="PRESTART_CAPACITY_RECOVERED", app_stopped=True, config=raw,
                         capacity=cli.record(out/"capacity/result.json"))
        value["usb_closed"]=True
    except Exception as error:
        value.update(error=type(error).__name__,detail=str(error))
    s.write(out/"result.json",dict(time=cli.now(),**value))
    print(json.dumps(value),flush=True)
    cli.require("error" not in value,"recovery needs reconciliation; do not replay")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("mode", choices=("launch", "worker", "recover", "recover-worker"))
    parser.add_argument("--run", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--diagnosis", type=Path)
    args = parser.parse_args()
    s = cli.Store(ROOT)
    run, out = s.checked(args.run), s.checked(args.out)
    cli.require(run.is_dir() and not out.is_relative_to(run), "separate owned diagnostic output required")
    supervisor = cli.load_module("runtime_doctor_owner", ROOT / ".cache/p3-4-screening-20260922/supervisor.py")
    if args.mode in ("launch", "recover"):
        cli.require(not out.exists(), "preserve diagnostic attempt")
        for name in ("intent.json", "result.json", "commands.json", "power.txt", "runtime-config.json", "logcat.log", "host", "runtime",
                     "capacity", "stop-intent.json", "retire-intent.json"):
            s.checked(out / name)
        s.write(out / "intent.json", dict(source=cli.record(__file__), run=str(run), read_only_phone=args.mode == "launch"))
        worker_args = ["worker", "--run", str(run), "--out", str(out)]
        if args.mode == "recover":
            cli.require(args.diagnosis is not None, "exact diagnostic receipt required")
            worker_args = ["recover-worker", "--run", str(run), "--out", str(out),
                           "--diagnosis", str(s.checked(args.diagnosis))]
        print(supervisor.owned.launch(out / "runtime", Path(__file__),
            worker_args, 600), flush=True)
    else:
        cli.require(supervisor.owned.in_job(), "finite diagnostic owner required")
        if args.mode == "recover-worker":
            cli.require(args.diagnosis is not None, "diagnostic receipt required")
            recover(s,run,out,s.checked(args.diagnosis))
        else:
            worker(s, run, out)


if __name__ == "__main__":
    cli.require(Path.cwd() == ROOT and sys.flags.isolated and sys.flags.no_site and sys.dont_write_bytecode,
                "explicit root and isolated Python required")
    main()
