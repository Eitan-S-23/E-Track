"""Prepare one 460800 recovery with the verified retry fix, not a clean screen."""
from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import runpy
import sys
import urllib.parse
import urllib.request

ROOT = Path(__file__).resolve().parents[2]
SELF = Path(__file__).resolve()
OUT = ROOT/".cache/p34d/retry"
RUN = "retry-460800-fix"
SHA = "f30d71f3bd29238b01eb0c599e7b58e0d31e14b0"
PKG = "com.wen.gaia.gaia.p34retry"
foreground = runpy.run_path(str(SELF.with_name("baud_foreground.py")), run_name="retry_foreground")


def require(value, message):
    if not value:
        raise RuntimeError(message)


def reconcile(value, owner):
    require(value["result"] == "BASELINE_AND_DURABLE_PREFIX_VERIFIED" and value["reader_closed"] and
            owner["worker_exit"] == 0 and not owner["forced_termination"], "failure reader is unresolved")
    require(value["identity"]["version_code"] == 30208 and value["journal"]["durable_off"] == 4096 and
            not value["journal"]["committed"] and value["session"]["state"] == 0 and
            value["last_internal_profile"]["run"] == 4, "failure state differs from the diagnosed case")
    for key in ("flash", "reset", "at", "target_memory_writes"):
        require(value[key] == 0, "not a passive failure reconciliation")


def runtime():
    r = foreground["runtime"]()
    r.authority()
    original_sources, original_save = r.sources, r.save
    r.PKG, r.PHONE = PKG, r.RUNTIME/"phone-r4"
    r.sources = lambda: sorted(original_sources()+[r.b.record(p) for p in
        (SELF, SELF.with_name("test_baud_retry.py"), SELF.with_name("baud_uncached.py"))], key=lambda x: x["path"])

    def apk():
        value = r.read(ROOT/".cache/p34d/apk.json")
        require(value["sha"] == SHA and value["metadata"]["commit"] == SHA and
                value["metadata"]["application_id"] == PKG and not value["metadata"]["release_signing"] and
                r.b.record(value["apk"]["path"]) == value["apk"], "verified retry APK changed")
        return value

    def authority():
        plan = r.read(OUT/"plan.json")
        require(plan["root"] == str(ROOT) and plan["runs"] == [RUN] and plan["baud"] == 460800 and
                plan["sources"] == r.sources() and plan["apk"] == r.b.record(ROOT/".cache/p34d/apk.json") and
                plan["initial_durable_off"] == 4096 and plan["full_package_throughput_eligible"] is False,
                "retry plan/source binding changed")
        for item in plan["originals"]:
            require(r.b.record(item["path"]) == item, "original failure evidence changed")
        apk()
        return plan

    def save(path, value, **kwargs):
        if Path(path) == r.cell(RUN)/"config.json":
            value = dict(value, plan=r.b.record(OUT/"plan.json"),
                         purpose="targeted recovery after sender fix", initial_durable_off=4096,
                         full_package_throughput_eligible=False)
        return original_save(path, value, **kwargs)

    r.apk, r.authority, r.save = apk, authority, save
    r.launch_worker = lambda name, mode, seconds, run=None: r.supervisor.owned.launch(
        r.RUNTIME/name, SELF, [mode]+(["--run", run] if run else []), seconds)
    return r


def freeze(r):
    tests_path = OUT/"host-tests/result.json"
    tests = r.read(tests_path)
    require(tests["passed"] and tests["sources"] == r.sources(), "source-bound retry tests required")
    failure = r.cell("baud-460800")/"failure/readback/result.json"
    owner = r.RUNTIME/"readback-baud-460800-durable/closed.json"
    result = r.read(failure)
    reconcile(result, r.read(owner))
    group = r.m.verified_assets()["groups"]["screen"]
    require(result["image"] ["sha256"] == group["baseline"]["sha256"] and
            result["journal"]["package_sha256"] == group["package"]["sha256"], "recovery input drift")
    r.apk()
    r.save(OUT/"plan.json", dict(time=r.b.now(), root=str(ROOT), runs=[RUN], baud=460800,
        sources=r.sources(), apk=r.b.record(ROOT/".cache/p34d/apk.json"), tests=r.b.record(tests_path),
        originals=[r.b.record(p) for p in (failure, owner, r.cell("baud-460800")/"failure/durable.json",
                   r.b.OUT/"foreground/plan.json")], initial_durable_off=4096,
        purpose="one targeted recovery after a reproduced and CI-tested sender fix",
        operations="renew owned USB; install side-by-side debug APK; one matched cold start; one user-started recovery",
        firmware_flashes=0, at_commands=0, staging_erases_by_host=0, full_package_throughput_eligible=False,
        later_matrix=[115200, 460800, 921600],
        later_gate="after this recovery is reconciled, prepare equal-input clean cells with the same fixed APK",
        final_state="verified 30209 retained", independent_acceptance=False))


def renew_phone(r):
    old = foreground["runtime"]()
    for p in (old.PHONE/"stop.json", r.PHONE, r.RUNTIME/"phone-worker-r4"):
        r.b.checked(p)
    if not (old.PHONE/"closed.json").exists():
        require(not (old.PHONE/"stop.json").exists(), "existing phone stop must be reconciled")
        r.save(old.PHONE/"stop.json", dict(time=r.b.now(), reason="finished failure preserved; renew for tested retry APK"))
    closed = r.wait_file(old.PHONE/"closed.json", 30)
    owner = r.wait_file(r.RUNTIME/"phone-worker-r3/closed.json", 30)
    require(closed["port_closed"] and closed["stop_exit"] == 0 and not closed.get("forced_cleanup") and
            owner["worker_exit"] == 0 and not owner["forced_termination"] and not old.phone().alive(),
            "old private USB route not normally closed")
    r.launch_worker("phone-worker-r4", "phone-worker", 5430)
    r.wait_file(r.PHONE/"ready.json", 30)
    r.phone().phone_identity()
    old.PHONE = r.PHONE
    return old


def release_old(r, old):
    p = old.phone("baud-460800")
    p.phone_identity()
    require(p.installed("runtime") is not None, "old failed APK identity changed")
    pid = p.command(["shell", "pidof", old.PKG], check=False).strip()
    if not pid:
        r.save(OUT/"released.json", dict(time=r.b.now(), stopped_by_host=False, app_data_preserved=True))
        return
    pkg, actual_pid, remote = p.location("runtime")
    expected = r.read(r.cell("baud-460800")/"failure/durable.json")["capture"]
    health = json.loads(p.file_bytes(pkg, remote+"/health.json", 8192))
    require(actual_pid == expected["pid"] and health["captureId"] == expected["captureId"] and
            health["healthy"] and health["upgradeStarts"] == health["upgradeEnds"] == 1 and
            health["outcome"] == "not-completed" and health["lost"] == 0 and health["error"] is None,
            "old App has new or unresolved activity")
    r.save(OUT/"release-started.json", dict(time=r.b.now(), pid=actual_pid, health=health, apk=old.apk()["apk"]))
    p.command(["shell", "am", "force-stop", pkg])
    require(not p.command(["shell", "pidof", pkg], check=False).strip(), "old debug App still running")
    r.save(OUT/"released.json", dict(time=r.b.now(), pid=actual_pid, stopped_by_host=True, app_data_preserved=True))


def check_network(r):
    origin = r.live_network()["origin"]
    group = r.m.verified_assets()["groups"]["screen"]
    opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
    url = origin+r.service.LATEST_PATH+"?"+urllib.parse.urlencode(r.query_for(group))
    with opener.open(url, timeout=30) as response:
        body = json.loads(response.read(16384))
    r.verify_latest(body, group)
    parsed = urllib.parse.urlsplit(body["asset"]["downloadUrl"])
    require(parsed.scheme+"://"+parsed.netloc == origin, "download origin changed")
    with opener.open(body["asset"]["downloadUrl"], timeout=30) as response:
        data = response.read(group["package"]["bytes"]+1)
    require(data == Path(group["package"]["path"]).read_bytes(), "live package differs")
    r.save(OUT/"network-verified.json", dict(time=r.b.now(), origin=origin, package=group["package"],
                                           tls_verification=True, process_local_route="direct"))


def setup(r):
    r.authority()
    r.m.native_authority()
    for name in ("network-verified.json", "release-started.json", "released.json", "install-started.json",
                 "installed.json", "setup-result.json"):
        r.b.checked(OUT/name)
    result = dict(time=r.b.now(), run=RUN, result="SETUP_INCOMPLETE")
    try:
        check_network(r)
        old = renew_phone(r)
        release_old(r, old)
        p = r.phone(RUN)
        present = p.installed("runtime")
        if present is None:
            r.save(OUT/"install-started.json", dict(time=r.b.now(), apk=r.apk()["apk"], package=PKG))
            output = p.command(["install", "--no-streaming", r.apk()["apk"]["path"]], timeout=180)
            require(output.strip().splitlines()[-1:] == ["Success"], "installation outcome requires reconciliation")
            present = p.installed("runtime")
        require(present is not None, "new APK missing after installation")
        r.save(OUT/"installed.json", dict(time=r.b.now(), **present))
        rate = r.read(r.b.OUT/"rates/baud-460800.json")
        require(rate["result"] == "BAUD_COLD_START_VERIFIED" and rate["baud"] == 460800 and rate["reader_closed"],
                "prior supported baud selection unresolved")
        r.save(r.b.OUT/"rates"/(RUN+".json"), dict(result="BAUD_COLD_START_VERIFIED", baud=460800, run=RUN,
            reused=r.b.record(r.b.OUT/"rates/baud-460800.json"), new_at_commands=0,
            basis="unchanged baud; normal capture rechecks full App/Boot and fresh cold-start retention"))
        r.start(RUN, 460800, "screen")
        result["result"] = "WAITING_FOR_USER_CONNECT_AND_DOWNLOAD"
    except Exception as error:
        result["error"] = type(error).__name__+": "+str(error)
    finally:
        r.save(OUT/"setup-result.json", result)
    print(json.dumps(result), flush=True)
    return 0 if "error" not in result else 1


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("mode", choices=("freeze", "launch", "setup-worker", "phone-worker", "capture-worker", "coordinate"))
    parser.add_argument("--run", choices=(RUN,), default=RUN)
    args = parser.parse_args()
    require(Path.cwd() == ROOT and sys.flags.isolated and sys.flags.no_site and sys.dont_write_bytecode,
            "isolated explicit-root execution required")
    r = runtime()
    if args.mode == "freeze":
        freeze(r)
        return
    r.authority()
    os.environ.update(r.environment())
    if args.mode == "launch":
        print(r.launch_worker("retry-setup", "setup-worker", 900), flush=True)
        return
    require(r.supervisor.owned.in_job(), "bounded owned worker required")
    if args.mode == "setup-worker":
        raise SystemExit(setup(r))
    if args.mode == "phone-worker":
        r.phone().server()
    elif args.mode == "coordinate":
        foreground["coordinate"](r, RUN)
    else:
        cycle = r.load("retry_capture_device_lock", SELF.with_name("repeat_cycle.py"))
        with cycle.device_lock():
            raise SystemExit(r.m.capture(RUN))


if __name__ == "__main__":
    main()
