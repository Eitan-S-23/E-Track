"""Resume the clean three-rate screen with one fresh, equivalent FULL envelope."""
from __future__ import annotations

import argparse
import copy
import json
import os
from pathlib import Path
import runpy
import sys

ROOT = Path(__file__).resolve().parents[2]
SELF = Path(__file__).resolve()
PARENT = SELF.with_name("baud_resume_clock.py")
OUT = ROOT/".cache/p34m/foreground"
RUNS = ("baud-115200-f1", "baud-460800", "baud-921600")


def base_runtime():
    return runpy.run_path(str(PARENT), run_name="foreground_parent")["runtime"]()


def equivalent(old, new):
    for name in ("baseline", "target", "baseline_identity", "target_identity"):
        if old[name] != new[name]:
            raise RuntimeError("raw firmware identity changed: "+name)
    if old["package"]["bytes"] != new["package"]["bytes"] or old["package"]["sha256"] == new["package"]["sha256"]:
        raise RuntimeError("new nonce must change only the same-length package identity")
    for key in ("passed", "byte_identical", "boot_ok", "guards_ok", "workspace_lifecycle_ok"):
        if new["decoder"].get(key) is not True:
            raise RuntimeError("actual decoder verification missing: "+key)


def failure_closed(r):
    source = r.cell("baud-115200-r6")
    readback = source/"failure/readback-interruption/result.json"
    value = r.read(readback)
    owner = r.read(r.RUNTIME/"readback-baud-115200-r6-interruption/closed.json")
    r.b.require(value["result"] == "BASELINE_AND_DURABLE_PREFIX_VERIFIED" and value["reader_closed"] and
                owner["worker_exit"] == 0 and not owner["forced_termination"] and
                value["journal"]["durable_off"] == 45056 and not value["journal"]["committed"],
                "previous interruption/readback unresolved")
    return r.b.record(readback)


def prepare():
    r = base_runtime()
    r.authority()
    prior = failure_closed(r)
    old_assets = r.m.verified_assets()
    old = old_assets["groups"]["screen"]
    r.b.require(not OUT.exists() and not os.environ.get("OTA_AES_KEY"), "preserve preparation; public fixture key only")
    for name in ("logs", "tmp", "negative", "screen.etu", "decoded.bin", "assets.json", "assets-failed.json"):
        r.b.checked(OUT/name)
    for name in ("logs", "tmp", "negative"):
        (OUT/name).mkdir(parents=True, exist_ok=True)
    original = r.a.OUT
    r.a.OUT = OUT
    checks = []
    try:
        package, decoded = OUT/"screen.etu", OUT/"decoded.bin"
        decoder = r.b.OUT/"assets/bin/full_image_host.exe"
        r.a.run("pack", r.a.python_tool("etu_pack.py", ["pack-full", "--app", old["target"]["path"],
                "--out", package, "--target-vcode", "30209"]))
        data = package.read_bytes()
        header = r.a.package_info(data, 30208, 30209)
        r.a.run("unpack", r.a.python_tool("etu_unpack.py", [package, "--out", decoded, "--verify-fw-header"]))
        r.b.require(decoded.read_bytes() == Path(old["target"]["path"]).read_bytes(), "unpacked raw target differs")
        result = json.loads(r.a.run("decode", [decoder, package, old["baseline"]["path"], old["target"]["path"], "ok"]))
        new = dict(old, package=r.b.record(package), header=header, decoder=result)
        equivalent(old, new)
        checks.extend(["fresh-nonce-same-length", "identical-raw-target", "real-decoder-and-Boot"])
        for name, mutation, expected in r.a.negatives(data, 30208):
            path = r.a.write_bytes("negative/"+name+".etu", mutation)
            negative = json.loads(r.a.run(name, [decoder, path, old["baseline"]["path"], old["target"]["path"], expected]))
            r.b.require(negative["passed"] and negative["prepares"] == 0, "negative did not fail before device preparation")
            checks.append("reject-"+name)
        assets = copy.deepcopy(old_assets)
        assets["groups"]["screen"] = new
        inputs = [r.b.record(path) for path in (SELF, PARENT, decoder, r.a.FW/"Tools/etu_pack.py",
                  r.a.FW/"Tools/etu_unpack.py", Path(old["baseline"]["path"]), Path(old["target"]["path"]))]
        r.save(OUT/"assets.json", dict(result="HOST_READY", time=r.b.now(), assets=assets, source=r.b.record(SELF),
               original_assets=r.b.record(original/"manifest.json"), inputs=inputs,
               originals=prior, checks=checks, new_firmware_builds=0, new_apk_builds=0, hardware=False))
    except Exception as error:
        r.save(OUT/"assets-failed.json", dict(time=r.b.now(), checks=checks, error=type(error).__name__+": "+str(error)))
        raise
    finally:
        r.a.OUT = original
    print("FOREGROUND_PACKAGE_READY", json.dumps(new["package"]), flush=True)


def runtime():
    r = base_runtime()
    original_sources, original_assets = r.sources, r.m.verified_assets
    r.NETWORK, r.PHONE = r.RUNTIME/"network-r2", r.RUNTIME/"phone-r3"
    r.sources = lambda: sorted(original_sources()+[r.b.record(path) for path in
        (SELF, PARENT, SELF.with_name("test_baud_foreground.py"), SELF.with_name("baud_download_resume.py"))],
        key=lambda item: item["path"])

    def assets():
        old = original_assets()
        value = r.read(OUT/"assets.json")
        r.b.require(value["result"] == "HOST_READY" and value["source"] == r.b.record(SELF) and
                    all(r.b.record(item["path"]) == item for item in value["inputs"]) and
                    value["original_assets"] == r.b.record(r.a.OUT/"manifest.json"), "package preparation drift")
        new = value["assets"]
        r.b.require(r.b.record(new["groups"]["screen"]["package"]["path"]) == new["groups"]["screen"]["package"],
                    "new FULL bytes changed")
        equivalent(old["groups"]["screen"], new["groups"]["screen"])
        r.b.require(old["whole_boot"] == new["whole_boot"] and
                    old["groups"]["bootstrap"] == new["groups"]["bootstrap"], "unrelated group/Boot changed")
        return new

    def authority():
        prior, plan = r.read(r.b.OUT/"plan.json"), r.read(OUT/"plan.json")
        r.b.require(prior["sources"] == original_sources() and prior["rates"] == [115200, 460800, 921600] and
                    prior["root"] == str(ROOT) and prior["package"] == r.PKG, "original task/source scope changed")
        r.b.require(plan["prior_plan"] == r.b.record(r.b.OUT/"plan.json") and plan["sources"] == r.sources() and
                    plan["assets"] == r.b.record(OUT/"assets.json") and plan["runs"] == list(RUNS),
                    "foreground continuation source/assets drift")
        return plan

    r.m.verified_assets, r.authority = assets, authority
    r.launch_worker = lambda name, mode, seconds, run=None: r.supervisor.owned.launch(r.RUNTIME/name, SELF,
        [mode]+(["--run", run] if run else []), seconds)
    # Restore uses its original package-independent raw-image expectation. The
    # exact baseline/target/Boot are unchanged; start uses the new shared package.
    recovery = base_runtime()
    recovery.start = r.start
    original_advance = recovery.advance

    def advance(run):
        r.b.require(run in RUNS[:2], "only the two remaining finite transitions are allowed")
        completed = r.read(r.cell(run)/"completed.json")
        board = r.read(r.cell(run)/"mcu/result.json")
        r.b.require(completed["result"] == "COMPLETED_RETAINED" and board.get("profile_complete") and
                    board["profile"]["clean_counters"], "clean completed screening required before rate advance")
        original_advance(run)

    r.advance = advance
    return r


def freeze(r):
    r.b.require(not (OUT/"plan.json").exists(), "preserve finite continuation plan")
    tests = r.read(OUT/"host-tests/result.json")
    r.b.require(tests["passed"] and tests["sources"] == r.sources(), "source-bound foreground tests required")
    r.m.verified_assets()
    original = r.b.OUT
    r.b.OUT = OUT
    try:
        r.hostcheck()
    finally:
        r.b.OUT = original
    r.save(OUT/"plan.json", dict(time=r.b.now(), root=str(ROOT), runs=list(RUNS), rates=[115200, 460800, 921600],
        prior_plan=r.b.record(r.b.OUT/"plan.json"), sources=r.sources(), assets=r.b.record(OUT/"assets.json"),
        tests=r.b.record(OUT/"host-tests/result.json"), http=r.b.record(OUT/"runtime-hostcheck-003/result.json"),
        prior_failure=failure_closed(r), apk=r.apk()["apk"], recovery=r.b.record(r.b.OUT/"recovery/manifest.json"),
        operations="one clean full transfer per rate; ordinary matched cold start; original verified raw-image recovery",
        reason="foreground-interrupted r6 is excluded; new package avoids an extra recovery OTA and manual staging erase",
        final_state="verified 30209 retained", hardware_background_support=False, independent_acceptance=False))


def open_and_start(r):
    failure_closed(r)
    p = base_runtime().phone("baud-115200-r6")
    r.b.require(p.installed("runtime") is not None, "do not stop an unrelated APK")
    pkg, pid, remote = p.location("runtime")
    health = json.loads(p.file_bytes(pkg, remote+"/health.json", 8192))
    r.b.require(pid == 28108 and health["healthy"] and health["upgradeStarts"] == health["upgradeEnds"] == 1 and
                health["outcome"] == "not-completed" and health["lost"] == 0 and health["error"] is None,
                "old App has new/unreconciled activity; do not stop it")
    r.save(OUT/"release-started.json", dict(time=r.b.now(), pid=pid, health=health, apk=r.apk()["apk"]))
    p.command(["shell", "am", "force-stop", pkg])
    r.b.require(not p.command(["shell", "pidof", pkg], check=False).strip(), "old debug App did not stop")
    r.save(OUT/"released.json", dict(time=r.b.now(), pid=pid, data_preserved=True))
    for directory, owner in ((r.RUNTIME/"phone-r2", r.RUNTIME/"phone-worker-r2"),
                             (r.RUNTIME/"network-r1", r.RUNTIME/"network-worker")):
        r.save(directory/"stop.json", dict(time=r.b.now(), reason="reconciled interruption; renew the clean foreground window"))
        closed = r.wait_file(directory/"closed.json", 30)
        supervisor = r.wait_file(owner/"closed.json", 30)
        r.b.require(supervisor["worker_exit"] == 0 and not supervisor["forced_termination"], "old owner did not close normally")
        if directory.name.startswith("phone"):
            r.b.require(closed["port_closed"] and closed["stop_exit"] == 0 and not closed.get("forced_cleanup") and
                        not p.alive(), "old private ADB not cleanly closed")
        else:
            r.b.require(closed["listener_closed"] and closed["worker_stopped"], "old network not closed")
    r.launch_worker("network-worker-r2", "network-worker", 10830)
    r.wait_file(r.NETWORK/"ready.json", 100)
    r.https_check()
    r.launch_worker("phone-worker-r3", "phone-worker", 5430)
    r.wait_file(r.PHONE/"ready.json", 30)
    r.phone().phone_identity()
    r.b.require(r.phone().installed("runtime") is not None, "unchanged APK missing after observer renewal")
    previous = r.b.OUT/"rates/baud-115200-r6.json"
    rate = r.read(previous)
    r.b.require(rate["result"] == "BAUD_COLD_START_VERIFIED" and rate["baud"] == 115200 and rate["reader_closed"],
                "unchanged 115200 setting not admitted")
    r.save(r.b.OUT/"rates/baud-115200-f1.json", dict(result="BAUD_COLD_START_VERIFIED", run=RUNS[0], baud=115200,
           basis="reuse unchanged rate setting; fresh per-cell image/retention/cold-start guards still required",
           reused=r.b.record(previous), current_readback=failure_closed(r), new_at_commands=0, new_rate_setters=0))
    r.start(RUNS[0], 115200, "screen")


def coordinate(r, run):
    adapter = r.load("foreground_cached_download", SELF.with_name("baud_download_resume.py"))
    stale = base_runtime().m.verified_assets()["groups"]["screen"]["package"]
    directory = r.b.checked(r.cell(run)/"download-replacement")
    undo = adapter.bind(r, run, stale, directory)
    try:
        r.coordinate(run)
    finally:
        undo()
    # The adapter keeps its result separate. Failed original snapshots must not
    # leave the sole MCU observer running until its hard lifetime expires.
    result = r.read(directory/"coordinator-result.json")
    snapshot = r.cell(run)/"finished/snapshot.jsonl"
    if result["result"] != "COMPLETED_RETAINED" and snapshot.exists():
        obs = r.apk()["metadata"]["device_observation"]
        capture, _ = r.phone(run).envelope.verify(snapshot.read_bytes(), sentinel=obs["sentinel"], target=r.TARGET)
        if capture["outcome"] == "not-completed":
            r.save(r.cell(run)/"stop.json", dict(reason="finished failed invocation; preserve and reconcile", snapshot=r.b.record(snapshot)))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("mode", choices=("prepare", "freeze", "launch", "prepare-worker", "network-worker", "phone-worker",
                                        "capture-worker", "coordinate", "advance", "advance-worker"))
    parser.add_argument("--run", choices=RUNS, default=RUNS[0])
    args = parser.parse_args()
    if not (Path.cwd() == ROOT and sys.flags.isolated and sys.flags.no_site and sys.dont_write_bytecode):
        raise RuntimeError("isolated explicit-root execution required")
    if args.mode == "prepare":
        prepare()
        return
    r = runtime()
    if args.mode == "freeze":
        freeze(r)
        return
    r.authority()
    os.environ.update(r.environment())
    if args.mode in ("launch", "advance"):
        mode = "prepare-worker" if args.mode == "launch" else "advance-worker"
        r.b.require(args.mode != "launch" or args.run == RUNS[0], "one first-cell launcher")
        print(r.launch_worker(mode+"-"+args.run+"-foreground", mode, 1800, args.run), flush=True)
        return
    r.b.require(r.supervisor.owned.in_job(), "bounded owned worker required")
    if args.mode == "prepare-worker":
        open_and_start(r)
    elif args.mode == "network-worker":
        r.network_worker()
    elif args.mode == "phone-worker":
        r.phone().server()
    elif args.mode == "coordinate":
        coordinate(r, args.run)
    elif args.mode == "advance-worker":
        r.advance(args.run)
    else:
        cycle = r.load("foreground_capture_lock", SELF.with_name("repeat_cycle.py"))
        with cycle.device_lock():
            raise SystemExit(r.m.capture(args.run))


if __name__ == "__main__":
    main()
