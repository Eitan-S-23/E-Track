"""Thin read-only Android collector; no UI input, permission change or OTA start."""
import argparse
import hashlib
import json
from pathlib import Path
import re
import sys
import time

sys.path.insert(0, str(Path(__file__).resolve().parent))
from prepare import ROOT, Phone, close_phone, fingerprint, h


def capture_header(data, plan, pid, capture):
    line = data.split(b"\n", 1)[0]
    value = json.loads(line)
    h.require(value.get("kind") == "open" and value.get("pid") == pid and
              value.get("captureId") == capture and value.get("sentinel") == plan["sentinel"] and
              isinstance(value.get("target"), str) and
              value["target"].lower() == plan["ble_address"].lower(), "capture/APK/process binding")
    return value


def notification_filter(package):
    h.require(re.fullmatch(r"[a-z][a-z0-9]*(?:\.[a-z][a-z0-9]*)+", package), "invalid package")
    # Retain only this package's NotificationRecord, not unrelated notification text.
    return ("dumpsys notification --noredact | awk '"
            "/^[[:space:]]*NotificationRecord[(]/ {keep=index($0, \"pkg=" + package + " \" )>0} "
            "/^[^[:space:]]|^  [^[:space:]]/ {keep=0} keep {print}'")


def sample(phone, out, index, plan, pid, capture):
    directory = h.fresh(out / ("sample-%04d" % index))
    value = dict(started_unix_ns=time.time_ns(), started_monotonic_ns=time.monotonic_ns())
    commands = {
        "pid": ["shell", "pidof", phone.pkg],
        "services": ["shell", "dumpsys", "activity", "services", phone.pkg],
        "activities": ["shell", "sh", "-c", "dumpsys window | grep -E 'mCurrentFocus|mFocusedApp|mShowingLockscreen|mDreamingLockscreen'"],
        "power": ["shell", "dumpsys", "power"],
        "notification": ["shell", "sh", "-c", notification_filter(phone.pkg)],
    }
    for label, args in commands.items():
        data = phone.cmd(args, seconds=30, success_codes=(0, 1) if label in ("pid", "activities") else (0,))
        h.raw(directory / (label + ".txt"), data)
        if label == "pid":
            h.require(data.strip() == str(pid).encode(), "App process changed; preserve originals, do not restart")
        if label == "activities" and plan.get("capture_screen") is True and phone.pkg.encode() in data:
            h.raw(directory / "screen.png", phone.cmd(["exec-out", "screencap", "-p"], seconds=30))
    health = phone.health(capture)
    h.save(directory / "health.json", health)
    value.update(ended_unix_ns=time.time_ns(), ended_monotonic_ns=time.monotonic_ns())
    h.save(directory / "interval.json", value)
    return health


def gate(args, out):
    from live import frozen_invocation
    h.require(args.contract and args.matrix and args.command_id, "record requires frozen contract/matrix/command")
    contract = h.read_json(args.contract)
    h.require(contract.get("task_id") == "P3-8" and contract.get("status") == "FROZEN" and
              contract.get("approved_by") and contract.get("approved_at"), "unapproved P3-8 contract")
    commands = [c for c in contract["commands"] if c["id"] == args.command_id]
    h.require(len(commands) == 1, "ambiguous contract command")
    frozen_invocation(commands[0]["command"], sys.argv)
    digest = hashlib.sha256(args.inputs.read_bytes()).hexdigest()
    h.require(any(x.get("fingerprint") == "sha256:" + digest for x in contract["external_inputs"]),
              "unbound observation inputs")
    h.command(out, "precheck", [sys.executable, "-I", "-S", "-B", "-X", "utf8",
        ROOT / "Tools/acceptance/validate_bundle.py", "--contract", args.contract,
        "--matrix", args.matrix, "--repo-root", ROOT], h.environment(out), seconds=90)


def collect(args, out, plan):
    if args.mode == "record":
        gate(args, out)
    phone = Phone(plan, out / "usb", args.seconds + 420)
    logger = None
    result = dict(result="INCOMPLETE", formal_acceptance="NOT_ADJUDICATED" if args.mode == "record" else "NOT_RUN",
                  inputs=fingerprint(args.inputs), no_ui_input=True, no_ota_start=True)
    try:
        phone.start()
        h.require(phone.cmd(["shell", "am", "get-current-user"]).strip() == b"0", "wrong Android user")
        h.raw(out / "package.txt", phone.cmd(["shell", "dumpsys", "package", phone.pkg]))
        pid_raw = phone.cmd(["shell", "pidof", phone.pkg], success_codes=(0, 1)).strip()
        if args.launch:
            h.require(args.mode == "probe" and not pid_raw, "launch only an absent preparation process")
            component = phone.cmd(["shell", "cmd", "package", "resolve-activity", "--brief", phone.pkg]).decode().strip().splitlines()[-1]
            h.require(component.startswith(phone.pkg + "/") and re.fullmatch(r"[A-Za-z0-9_./]+", component), "activity identity")
            phone.cmd(["shell", "am", "start", "-W", "-n", component], seconds=45)
            pid_raw = phone.cmd(["shell", "pidof", phone.pkg]).strip()
        h.require(pid_raw.isdigit(), "one running App process required")
        pid = int(pid_raw)
        logger = h.Process(out, "logcat", phone.base + ["logcat", "-v", "epoch", "--pid", str(pid)], phone.env)
        h.require(logger.alive(), "logcat not running")
        def matching_capture():
            matches = []
            for name in phone.captures():
                raw = phone.cmd(["exec-out", "run-as", phone.pkg, "head", "-n", "1",
                                 "files/p34-observations/" + name + "/events.jsonl"])
                if json.loads(raw).get("pid") == pid:
                    capture_header(raw, plan, pid, name)
                    matches.append(name)
            h.require(len(matches) <= 1, "ambiguous current capture")
            return matches[0] if matches else None
        capture = h.wait_for(matching_capture, 30, interval=1)
        phone.pid, phone.capture = pid, capture
        result.update(pid=pid, capture=capture)
        deadline = min(time.monotonic() + args.seconds, phone.deadline - 360)
        h.save(out / "ready.json", dict(pid=pid, capture=capture, mode=args.mode, deadline_monotonic=deadline,
                                        allow_user_ota=args.mode == "record"))
        print("P38_READER_READY " + args.mode, flush=True)
        index = 0
        while time.monotonic() + 60 < deadline and not (out / "stop.json").exists():
            index += 1
            health = sample(phone, out, index, plan, pid, capture)
            h.require(health["healthy"], "unhealthy capture; retrieve originals, no replay")
            h.require(args.mode == "record" or health["upgradeStarts"] == 0, "unexpected OTA during preparation")
            h.require(logger.alive() and logger.paths["stdout"].stat().st_size < 128 * 1024 * 1024, "logcat exit/size limit")
            time.sleep(min(10, max(0, deadline - time.monotonic() - 60)))
        result.update(result="OBSERVATIONS_SAVED_NOT_ADJUDICATED", samples=index)
    except BaseException as error:
        result.update(result="COLLECTION_FAILED", error=type(error).__name__ + ": " + str(error))
        raise
    finally:
        errors = []
        for label, operation in (("originals", phone.salvage),
                                 ("logcat", lambda: logger.close("bounded_observation_end") if logger else None),
                                 ("private_adb", lambda: close_phone(phone))):
            try:
                operation()
            except BaseException as error:
                errors.append(dict(step=label, error=type(error).__name__ + ": " + str(error)))
        result.update(cleanup_errors=errors, adb_key_unchanged=fingerprint(plan["adb_key"]["path"]) == plan["adb_key"])
        h.save(out / "result.json", result)
        h.require(not errors, "collection cleanup incomplete; inspect result")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("mode", choices=("probe", "record"))
    parser.add_argument("--inputs", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--seconds", type=int, required=True)
    parser.add_argument("--launch", action="store_true")
    parser.add_argument("--contract", type=Path)
    parser.add_argument("--matrix", type=Path)
    parser.add_argument("--command-id")
    args = parser.parse_args()
    h.require(Path.cwd() == ROOT and sys.flags.isolated and sys.flags.no_site and sys.dont_write_bytecode,
              "explicit worktree and isolated Python required")
    h.require(120 <= args.seconds <= 3600 and (not args.launch or args.mode == "probe"), "bounded observation/launch scope")
    out = h.checked(args.out)
    for name in ("usb", "host", "ready.json", "result.json", "stop.json"):
        h.checked(out / name)
    plan = h.read_json(args.inputs)
    h.require(plan["app_id"] == "com.wen.gaia.gaia.p38acceptance", "only the admitted side-by-side package")
    for name in ("apk", "adb_key"):
        h.pinned(plan[name])
    h.fresh(out)
    collect(args, out, plan)


if __name__ == "__main__":
    main()
