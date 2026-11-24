"""Bounded single-App bootstrap of the independently reproduced UART repair."""
from __future__ import annotations

import argparse
import hashlib
import json
import logging
import os
from pathlib import Path
import re
import runpy
import sys
import threading
import time
import urllib.parse
import urllib.request

ROOT = Path(__file__).resolve().parents[2]
SELF = Path(__file__).resolve()
AREA = ROOT / ".cache/p34q/irq"
RUN = "irq-bootstrap-115200"
PACKAGE = "com.wen.gaia.gaia.p34retry"
APK_SHA = "37cdfcb0863546013de84ed5ec26acbbf44af6f50e4a82699669bc73ebca719a"
FILE_NAME = "irq-bootstrap-full.etu"


def require(value, reason):
    if not value:
        raise RuntimeError(reason)


def validate_group(group):
    require(group["baseline_identity"]["version_code"] == 30208 and
            group["target_identity"]["version_code"] == 30210 and
            group["baseline"]["sha256"] == "b7f8542861591f22aa5ba65ff019b01f3fd23b66699db31e3b516855f1df48ed" and
            group["package"]["bytes"] > 64 and group["decoder"]["passed"] is True,
            "IRQ bootstrap input group differs")


def validate_prior(value, closed, owner):
    require(value["result"] == "ORIGINAL_FAILED_SNAPSHOT_VERIFIED" and value["final_durable"] == 24576 and
            value["nak_status_counts"] == {"2": 4, "3": 31} and value["device_mutations"] == 0,
            "original CRC invocation is not reconciled")
    require(closed["port_closed"] and closed["stop_exit"] == 0 and not closed.get("forced_cleanup") and
            not owner["forced_termination"] and owner["worker_exit"] == 1,
            "read-only retrieval owner did not close as recorded")


def runtime():
    r = runpy.run_path(str(SELF.with_name("baud_memory_fix.py")))["configure"]()
    original_sources = [Path(item["path"]) for item in r.sources()]
    for b in (r.b, r.a.b):
        b.OUT = AREA
        b.host.OUT = AREA
    r.a.FW, r.a.OUT, r.a.RAW = AREA / "fw", AREA / "assets", AREA / "build/app-gcc/X-Track-App-GCC.bin"
    r.RUNTIME = AREA / "runtime"
    r.PHONE, r.NETWORK, r.PKG = r.RUNTIME / "phone-r1", r.RUNTIME / "network-r1", PACKAGE
    uncached = runpy.run_path(str(SELF.with_name("baud_uncached.py")))
    cache_evidence = lambda: dict(adapter=r.b.record(SELF), original_cache_proof=r.b.record(
        ROOT / ".cache/p34m/uncached-reader-004.json"))
    r.m.BoundLink = uncached["uncached_link"](r.m.BoundLink, cache_evidence)
    original_load = r.load

    def load(name, path):
        module = original_load(name, path)
        if Path(path).name == "baud_tune.py":
            module.ControlLink.running = r.m.BoundLink.running
            module.ControlLink = uncached["uncached_link"](module.ControlLink, cache_evidence)
        return module

    r.load = load

    def apk():
        value = r.read(ROOT / ".cache/p34d/apk.json")
        require(value["metadata"]["application_id"] == PACKAGE and value["apk"]["sha256"] == APK_SHA and
                r.b.record(value["apk"]["path"]) == value["apk"], "fixed installed APK binding changed")
        return value

    def sources():
        paths = set(original_sources + [SELF, SELF.with_name("test_irq_bootstrap.py"),
            SELF.with_name("baud_uncached.py"), AREA / "assets/manifest.json", AREA / "mcu-bindings.json",
            ROOT / ".cache/p34q/usb-retrieval-001/offline-analysis.json"])
        return [r.b.record(p) for p in sorted(paths)]

    def authority():
        plan = r.read(AREA / "plan.json")
        require(plan["root"] == str(ROOT) and plan["runs"] == [RUN] and plan["baud"] == 115200 and
                plan["sources"] == sources() and plan["apk"] == apk()["apk"] and
                plan["performance_sample"] is False, "IRQ bootstrap plan/source drift")
        validate_group(r.m.verified_assets()["groups"]["screen"])
        return plan

    original_make = r.make_config

    def make_config(assets, origin, token_key):
        value = original_make(assets, origin, token_key)
        for release in value["releases"].values():
            release["asset"]["fileName"] = FILE_NAME
        return value

    r.apk, r.sources, r.authority, r.make_config = apk, sources, authority, make_config
    r.inspect_start = lambda run: inspect_start(r, run)
    r.hostcheck = lambda: hostcheck(r)
    r.launch_worker = lambda name, mode, seconds, run=None: r.supervisor.owned.launch(
        r.RUNTIME / name, SELF, [mode], seconds)
    return r


def target_query(r, group):
    value = r.query_for(group)
    value["currentVersionCode"] = str(group["target_identity"]["version_code"])
    value["currentImageSha"] = group["target"]["sha256"]
    return value


def hostcheck(r):
    out = r.b.checked(AREA / "http-tests-v2")
    require(not out.exists(), "preserve existing HTTP self-test")
    for name in ("result.json", "service.log"):
        r.b.checked(out / name)
    out.mkdir(parents=True)
    log = logging.getLogger("irq-bootstrap-http")
    log.propagate = False
    sink = logging.FileHandler(out / "service.log", mode="x", encoding="utf-8")
    log.addHandler(sink)
    handler = type("IrqHttpCheck", (r.service.P33RequestHandler,), dict(log=log, timeout=5))
    server = r.service.ThreadingHTTPServer(("127.0.0.1", 0), handler)
    origin = "http://127.0.0.1:%d" % server.server_port
    assets = r.m.verified_assets()
    handler.state = r.RoutingState(assets, origin)
    worker = threading.Thread(target=server.serve_forever, kwargs={"poll_interval": .1}, daemon=True)
    worker.start()
    opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
    checks = []
    try:
        group = assets["groups"]["screen"]
        query = origin + r.service.LATEST_PATH + "?" + urllib.parse.urlencode(r.query_for(group))
        with opener.open(query, timeout=5) as response:
            body = json.loads(response.read(16384))
        r.verify_latest(body, group)
        require(body["asset"]["fileName"] == FILE_NAME, "unique download filename changed")
        with opener.open(body["asset"]["downloadUrl"], timeout=5) as response:
            data = response.read(group["package"]["bytes"] + 1)
        require(data == Path(group["package"]["path"]).read_bytes(), "HTTP package bytes differ")
        checks += ["latest-bound", "unique-download-name", "exact-full-download"]
        request = urllib.request.Request(body["asset"]["downloadUrl"], headers={"Range": "bytes=16-"})
        with opener.open(request, timeout=5) as response:
            require(response.status == 206 and response.read() == data[16:], "HTTP range mismatch")
        checks.append("range")
        query = origin + r.service.LATEST_PATH + "?" + urllib.parse.urlencode(target_query(r, group))
        with opener.open(query, timeout=5) as response:
            require(json.loads(response.read())["updateAvailable"] is False, "actual final target offered another update")
        checks.append("actual-target-no-update")
    finally:
        server.shutdown()
        server.server_close()
        worker.join(timeout=5)
        log.removeHandler(sink)
        sink.close()
    require(not worker.is_alive() and server.socket.fileno() == -1, "HTTP self-test did not close")
    r.save(out / "result.json", dict(passed=True, checks=checks, source=r.b.record(SELF),
        listener_closed=True, hardware=False, previous="runtime-hostcheck-003 used a hardcoded old final version"))


def inspect_start(r, run):
    require(run == RUN, "wrong bootstrap run")
    out, p = r.cell(run), r.phone(run)
    config = r.read(out / "config.json")
    pkg, pid, remote = p.location("runtime")
    before = p.file_bytes(pkg, remote + "/health.json", 8192)
    events = p.file_bytes(pkg, remote + "/events.jsonl", p.envelope.MAX_BYTES)
    after = p.file_bytes(pkg, remote + "/health.json", 8192)
    obs = r.apk()["metadata"]["device_observation"]
    result, prefix, lines = p.query.validate(events, before, after, pid=pid, sentinel=obs["sentinel"], target=r.TARGET)
    result["experiment"] = r.experiment_line(lines, config)
    location = r.b.checked(out / "queries" / str(time.time_ns()))
    for name, data in (("health-before.json", before), ("health-after.json", after), ("events.jsonl", events),
                       ("checkpoint.jsonl", prefix), ("observations.log", lines.encode("utf-8"))):
        r.raw(location / name, data)
    r.save(location / "result.json", result)
    require(p.command(["shell", "pidof", pkg]).strip() == str(pid), "App changed during checkpoint retrieval")
    if not result["successfulQueries"]:
        return None
    remote_package = "app_flutter/firmware/" + FILE_NAME
    if p.command(["exec-out", "run-as", pkg, "ls", remote_package], check=False).strip() != remote_package:
        return None
    package = config["assets"]["package"]
    data = p.file_bytes(pkg, remote_package, package["bytes"] + 1)
    require(len(data) == package["bytes"] and hashlib.sha256(data).hexdigest() == package["sha256"],
            "downloaded IRQ package mismatch")
    if not (out / "downloaded-full.etu").exists():
        r.raw(out / "downloaded-full.etu", data)
    r.save(location / "start-inputs.json", dict(time=r.b.now(), query=r.b.record(location / "result.json"),
        package=r.b.record(out / "downloaded-full.etu"), apk=r.apk()["apk"], pid=pid,
        experiment=result["experiment"], result="PHONE_QUERY_AND_PACKAGE_VERIFIED"))
    return r.b.record(location / "start-inputs.json")


def freeze(r):
    require(not (AREA / "plan.json").exists(), "preserve existing bootstrap plan")
    prior = ROOT / ".cache/p34q/usb-retrieval-001/offline-analysis.json"
    validate_prior(r.read(prior), r.read(ROOT / ".cache/p34m/runtime/phone-r5/closed.json"),
                   r.read(ROOT / ".cache/p34m/runtime/phone-worker-r5/closed.json"))
    validate_group(r.m.verified_assets()["groups"]["screen"])
    tests = r.read(AREA / "host-tests-v2/result.json")
    require(tests["passed"] and tests["source"] == r.b.record(SELF) and
            tests["test_source"] == r.b.record(SELF.with_name("test_irq_bootstrap.py")), "source-bound host tests required")
    r.hostcheck()
    r.save(AREA / "plan.json", dict(time=r.b.now(), root=str(ROOT), runs=[RUN], baud=115200,
        sources=r.sources(), apk=r.apk()["apk"], tests=r.b.record(AREA / "host-tests-v2/result.json"),
        prior_failure=r.b.record(prior), performance_sample=False,
        operations="reuse exact installed App; verified AT return to 115200 and matched cold start; user-started legal FULL OTA",
        current_version=30208, target_version=30210, purpose="install IRQ-only repair before its physical reliability test",
        package_filename=FILE_NAME, old_downloads_preserved=True, boot_replacement=False,
        final_state="verified 30210 retained", recovery="no downgrade in this bootstrap; unknown outcome pauses dependent mutation",
        later_matrix=[115200, 460800, 921600], qspi_comparison="separate input-controlled group after IRQ repair is verified",
        independent_acceptance=False))
    print("IRQ_BOOTSTRAP_PREPARED", flush=True)


def setup(r):
    result = dict(time=r.b.now(), result="SETUP_FAILED")
    try:
        r.launch_worker("network-worker", "network-worker", 10830)
        r.wait_file(r.NETWORK / "ready.json", 100)
        r.https_check()
        require(not r.phone(RUN).alive(), "private ADB port has another owner")
        r.launch_worker("phone-worker", "phone-worker", 5430)
        r.wait_file(r.PHONE / "ready.json", 30)
        p = r.phone(RUN)
        p.phone_identity()
        require(p.installed("runtime") is not None, "exact App absent; do not reinstall for setup")
        require(not p.command(["shell", "pidof", PACKAGE], check=False).strip(),
                "App is running; reconcile its activity before firmware preparation")
        tune = r.load("irq_bootstrap_tune", SELF.with_name("baud_tune.py"))
        lock = r.load("irq_bootstrap_lock", SELF.with_name("repeat_cycle.py"))
        with lock.device_lock():
            tune.tune(RUN, 115200, 30208)
        r.start(RUN, 115200, "screen")
        result["result"] = "WAITING_FOR_USER_CONNECT_AND_DOWNLOAD"
    except Exception as error:
        result["error"] = type(error).__name__ + ": " + str(error)
    r.save(AREA / "setup-result.json", result)
    print(json.dumps(result), flush=True)
    return 0 if "error" not in result else 1


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("mode", choices=("freeze", "launch", "setup-worker", "phone-worker", "network-worker",
                                         "capture-worker", "coordinate", "status", "close"))
    args = parser.parse_args()
    require(Path.cwd() == ROOT and sys.flags.isolated and sys.flags.no_site and sys.dont_write_bytecode,
            "isolated explicit project root required")
    r = runtime()
    if args.mode == "freeze":
        freeze(r)
        return
    r.authority()
    os.environ.update(r.environment())
    if args.mode == "launch":
        require(not (AREA / "launch-intent.json").exists(), "prior setup must be reconciled, not replayed")
        r.save(AREA / "launch-intent.json", dict(time=r.b.now(), plan=r.b.record(AREA / "plan.json")))
        print(json.dumps(r.launch_worker("setup-worker", "setup-worker", 900)), flush=True)
        return
    if args.mode == "status":
        for path in (AREA / "setup-result.json", r.cell(RUN) / "status.json", r.cell(RUN) / "mcu/state.json"):
            if path.exists():
                print(path.name, json.dumps(r.read(path)), flush=True)
        return
    if args.mode == "close":
        for directory in (r.PHONE, r.NETWORK, r.cell(RUN)):
            if directory.exists() and not (directory / "stop.json").exists():
                r.save(directory / "stop.json", dict(time=r.b.now(), reason="close owned bootstrap observers"))
        return
    require(r.supervisor.owned.in_job(), "owned bounded worker required")
    if args.mode == "setup-worker":
        raise SystemExit(setup(r))
    if args.mode == "phone-worker":
        r.phone(RUN).server()
    elif args.mode == "network-worker":
        r.network_worker()
    elif args.mode == "capture-worker":
        lock = r.load("irq_capture_lock", SELF.with_name("repeat_cycle.py"))
        with lock.device_lock():
            raise SystemExit(r.m.capture(RUN))
    else:
        r.coordinate(RUN)
        result = r.read(r.cell(RUN) / "coordinator-result.json")
        if result["result"] != "COMPLETED_RETAINED" and not (r.cell(RUN) / "stop.json").exists():
            r.save(r.cell(RUN) / "stop.json", dict(reason="preserve incomplete bootstrap; no replay"))


if __name__ == "__main__":
    main()
