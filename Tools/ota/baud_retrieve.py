"""Retrieve an existing failed App snapshot without launching or changing it."""
from __future__ import annotations

import argparse
import datetime as dt
import json
import os
from pathlib import Path
import re
import runpy
import sys
import threading

ROOT = Path(__file__).resolve().parents[2]
SELF = Path(__file__).resolve()
OUT = ROOT / ".cache/p34q/usb-retrieval-001"
RUN = "retry-460800-fix"
CAPTURE = "1790111283453873-0ea0151f5ee2c762df276d3e"
PID = 27721
SECONDS = 600


def runtime():
    r = runpy.run_path(str(SELF.with_name("baud_retry.py")))["runtime"]()
    r.authority()
    r.PHONE = r.RUNTIME / "phone-r5"
    return r


def preflight(r):
    for directory in (OUT, r.PHONE, r.RUNTIME / "phone-worker-r5", r.b.OUT / "host"):
        r.b.checked(directory)
        for parent, dirs, files in os.walk(directory, followlinks=False):
            for name in dirs + files:
                # The supervisor owns its transient atomic-replacement leaf.
                if directory.name == "phone-worker-r5" and name == "state.json.tmp":
                    continue
                r.b.checked(Path(parent) / name)
    r.b.checked(r.RUNTIME / "actions.jsonl")
    for name in ("plan.json", "before.json", "identity.json", "inventory.json", "result.json", "audit.json"):
        r.b.checked(OUT / name)


def protected(r):
    paths = [ROOT / ".git/index", Path("C:/Users/SU/.android/adbkey"),
             Path("C:/Users/SU/AppData/Roaming/SEGGER/JLinkDLL.ini")]
    for kind in ("Microsoft/PowerShell", "Microsoft/Windows/PowerShell"):
        paths.append(Path("C:/Users/SU/AppData/Local") / kind / "StartupProfileData-NonInteractive")
    app = ROOT / "app/bluetooth_flutter_Trace"
    paths.extend(app / name for name in (
        "lib/ota/ota_ble_transport.dart", "lib/services/bluetooth_service.dart",
        "lib/services/ota_service.dart", "test/ota/ota_ble_transport_test.dart",
        "test/ota/ota_service_session_test.dart", "test/ota/ota_service_upgrade_test.dart"))
    return [{**r.b.record(path), "mtime_ns": path.stat().st_mtime_ns} if path.is_file()
            else dict(path=str(path), missing=True) for path in paths]


def launch(r):
    preflight(r)
    p = r.phone(RUN)
    old = r.read(r.RUNTIME / "phone-r4/closed.json")
    owner = r.read(r.RUNTIME / "phone-worker-r4/closed.json")
    r.b.require(old["port_closed"] and old["stop_exit"] == 0 and not old.get("forced_cleanup")
                and owner["worker_exit"] == 0 and not owner["forced_termination"] and not p.alive(),
                "old USB ownership unresolved")
    r.b.require(not OUT.exists() and not r.PHONE.exists(), "preserve previous retrieval")
    r.save(OUT / "before.json", dict(time=r.b.now(), protected=protected(r)))
    r.save(OUT / "plan.json", dict(time=r.b.now(), root=str(ROOT), source=r.b.record(SELF),
        sources=r.sources(), run=RUN, capture=CAPTURE, pid=PID, apk=r.apk()["apk"],
        private_port=p.PORT, serial=p.SERIAL, seconds=SECONDS,
        outputs=[str(OUT), str(r.PHONE), str(r.RUNTIME / "phone-worker-r5"),
                 str(r.b.OUT / "host"), str(r.RUNTIME / "actions.jsonl")],
        purpose="retrieve original CRC failure; no new OTA, install, launch, reset or AT command",
        device_mutations=0, independent_acceptance=False))
    print(json.dumps(r.supervisor.owned.launch(r.RUNTIME / "phone-worker-r5", SELF,
                                             ["worker"], SECONDS + 30)), flush=True)


def stop_phone(r, reason):
    if r.PHONE.exists() and not (r.PHONE / "closed.json").exists() and not (r.PHONE / "stop.json").exists():
        r.save(r.PHONE / "stop.json", dict(time=r.b.now(), reason=reason))


def validate_health(value):
    if not (value["captureId"] == CAPTURE and value["healthy"] is True
            and value["lost"] == 0 and value["error"] is None and value["upgradeStarts"] == 1
            and value["upgradeEnds"] == 1 and value["outcome"] == "not-completed"):
        raise RuntimeError("original failed capture identity/health mismatch")


def collect(r, p):
    p.phone_identity()
    installed = p.installed("runtime")
    r.b.require(installed is not None, "fixed debug APK is absent; no automatic installation")
    current_pid = p.command(["shell", "pidof", r.PKG], check=False).strip()
    r.save(OUT / "identity.json", dict(time=r.b.now(), serial=p.SERIAL, model="V2312A",
        installed=installed, current_pid=current_pid, original_pid=PID, apk=r.apk()["apk"]))
    print("PHONE_AND_INSTALLED_APK_VERIFIED", p.SERIAL, current_pid or "not-running", flush=True)
    base = "files/p34-observations"
    names = p.command(["exec-out", "run-as", r.PKG, "ls", "-1", base]).splitlines()
    r.b.require(1 <= len(names) <= 8 and all(re.fullmatch(r"\d{13,20}-[0-9a-f]{24}", n) for n in names),
                "unexpected capture directory inventory")
    r.save(OUT / "inventory.json", dict(time=r.b.now(), names=names, requested=CAPTURE))
    r.b.require(CAPTURE in names, "original failed capture missing; do not launch or replay")
    remote = base + "/" + CAPTURE
    leaves = p.command(["exec-out", "run-as", r.PKG, "ls", "-1", remote]).splitlines()
    snapshots = sorted(n for n in leaves if re.fullmatch(r"snapshot-[1-4]\.jsonl", n))
    destination = OUT / "captures" / CAPTURE
    for name in ("health-before.json", "health-after.json", "events.jsonl", "binding.json", *snapshots):
        r.b.checked(destination / name)
    before = p.file_bytes(r.PKG, remote + "/health.json", 8192)
    r.raw(destination / "health-before.json", before)
    events = p.file_bytes(r.PKG, remote + "/events.jsonl", p.envelope.MAX_BYTES)
    r.raw(destination / "events.jsonl", events)
    for name in snapshots:
        r.raw(destination / name, p.file_bytes(r.PKG, remote + "/" + name, p.envelope.MAX_BYTES + 8192))
    after = p.file_bytes(r.PKG, remote + "/health.json", 8192)
    r.raw(destination / "health-after.json", after)
    validate_health(json.loads(before))
    validate_health(json.loads(after))
    r.b.require({k: v for k, v in json.loads(before).items() if k != "time"}
                == {k: v for k, v in json.loads(after).items() if k != "time"},
                "capture counters changed during retrieval; preserve original bytes")
    r.b.require(snapshots, "no immutable snapshot; preserved events are not a finished envelope")
    config = r.read(r.cell(RUN) / "config.json")
    expected = r.read(config["runtime_config"]["path"])
    obs = r.apk()["metadata"]["device_observation"]
    results = []
    for name in snapshots:
        parsed = destination / ("parsed-" + Path(name).stem)
        summary = p.envelope.extract(destination / name, parsed, obs["sentinel"], obs["target"])
        r.b.require(summary["captureId"] == CAPTURE and summary["pid"] == PID
                    and summary["outcome"] == "not-completed", "failed snapshot binding differs")
        for key in ("packageSha256", "packageBytes", "currentVersionCode", "targetVersionCode",
                    "currentImageSha256", "targetImageSha256"):
            r.b.require(summary["input"][key] == expected[key], "immutable input mismatch: " + key)
        r.b.require(summary["input"]["deviceAddress"] == expected["target"], "immutable target mismatch")
        raw = (destination / name).read_bytes()
        prefix = b"".join(raw.splitlines(keepends=True)[:-1])
        r.b.require(events.startswith(prefix), "snapshot differs from preserved original events")
        r.experiment_line((parsed / "observations.log").read_text(encoding="utf-8"), config)
        results.append(dict(snapshot=r.b.record(destination / name), summary=summary))
    binding = dict(time=r.b.now(), result="ORIGINAL_FAILED_SNAPSHOT_VERIFIED", remote=remote,
        current_pid=current_pid, original_pid=PID, installed=installed, snapshots=results,
        health=json.loads(after), device_mutations=0, independent_acceptance=False)
    r.save(destination / "binding.json", binding)
    return dict(result=binding["result"], capture=CAPTURE, snapshots=len(results),
                binding=r.b.record(destination / "binding.json"))


def worker(r):
    r.b.require(r.supervisor.owned.in_job(), "owned finite worker required")
    plan = r.read(OUT / "plan.json")
    r.b.require(plan["source"] == r.b.record(SELF) and plan["sources"] == r.sources(), "retrieval source drift")
    preflight(r)
    p = r.phone(RUN)
    original_write = p.write
    deadline = dt.datetime.now(dt.timezone.utc) + dt.timedelta(seconds=SECONDS - 20)

    def write(path, value):
        if Path(path) == r.PHONE / "ready.json":
            value = dict(value, deadline=deadline.isoformat())
        return original_write(path, value)

    p.write = write
    timer = threading.Timer(SECONDS - 10, stop_phone, (r, "bounded retrieval deadline"))
    timer.daemon = True
    server = threading.Thread(target=p.server, daemon=True)
    timer.start()
    server.start()
    result = dict(time=r.b.now(), result="RETRIEVAL_FAILED", device_mutations=0)
    try:
        r.wait_file(r.PHONE / "ready.json", 30)
        result.update(collect(r, p))
    except Exception as error:
        result["error"] = type(error).__name__ + ": " + str(error)
    finally:
        timer.cancel()
        stop_phone(r, "retrieval completed or failed; no replay")
        server.join(timeout=25)
        closed = r.read(r.PHONE / "closed.json") if (r.PHONE / "closed.json").exists() else None
        result.update(ended=r.b.now(), server_thread_closed=not server.is_alive(),
                      port_closed=not p.alive(), server=closed)
        r.save(OUT / "result.json", result)
    print(json.dumps(result), flush=True)
    return 0 if result["result"] == "ORIGINAL_FAILED_SNAPSHOT_VERIFIED" and result["server_thread_closed"] \
        and result["port_closed"] and closed and closed.get("stop_exit") == 0 and not closed.get("forced_cleanup") else 1


def audit(r):
    preflight(r)
    before, after = r.read(OUT / "before.json")["protected"], protected(r)
    changed = [dict(before=left, after=right) for left, right in zip(before, after) if left != right]
    owner = r.read(r.RUNTIME / "phone-worker-r5/closed.json")
    result = r.read(OUT / "result.json")
    r.save(OUT / "audit.json", dict(time=r.b.now(), protected_unchanged=not changed, changes=changed,
        owner=owner, port_closed=not r.phone(RUN).alive(), retrieval=result["result"],
        checked_roots=r.read(OUT / "plan.json")["outputs"]))
    print(json.dumps(dict(protected_unchanged=not changed, changes=changed, owner=owner,
                         retrieval=result["result"])), flush=True)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("mode", choices=("launch", "worker", "audit"))
    args = parser.parse_args()
    if not (Path.cwd() == ROOT and sys.flags.isolated and sys.flags.no_site and sys.dont_write_bytecode):
        raise RuntimeError("isolated explicit project-root execution required")
    r = runtime()
    if args.mode == "worker":
        raise SystemExit(worker(r))
    globals()[args.mode](r)


if __name__ == "__main__":
    main()
