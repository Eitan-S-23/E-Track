"""Repeat the admitted P3-4 restore/observe/collect cycle without replaying writes.

This is a concrete adapter for the verified 2026-09-22 backend, not a flasher.
The user still owns permission dialogs, BLE connection and the OTA start button.
"""
from __future__ import annotations

import argparse
import contextlib
import datetime as dt
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import re
import sys
import time

ROOT = Path(__file__).resolve().parents[2]
SELF = Path(__file__).resolve()
HERE = ROOT / ".cache/p3-4-screening-20260922"
REGISTRY = HERE / "batch-r3"
RUNS = ROOT / ".cache/p34-cycles"
RESTORE = ROOT / ".cache/p34-restore-20260922"
SOURCE_ARCHIVE = ROOT / ".cache/p34-cycle-source-archive"
MATRIX_SHA = "90972cd91170723487e745449466c7a9ffb25c40403aacc9b0a4d81627d79ba4"
BASE_SHA = "415589cb342ffe1986fd141cc29ba192489a85bd13b86cbb9c0939cf85ffad3b"
TARGET_SHA = "16b4442d4d88aed0195513808862b64459159b4b40afdf5b94b2ecc30e2929fe"
BOOT_SHA = "e6618f50b6fce014beb2b8fe5cd4317b904d609d05c07a86e510a4bd772f2b7c"
PACKAGE_SHA = "da82725792afeb88b353de7c595596eafa47f1c1db9bfa4905803693b159d600"
PACKAGE_BYTES = 284643
TARGET = "02:00:00:00:00:01"
CANDIDATES = ("reuse-with", "discover-without", "reuse-without")
PREPARE_SECONDS, START_WAIT_SECONDS, RESERVE_SECONDS = 1800, 900, 1280
CAPTURE_SECONDS = PREPARE_SECONDS + START_WAIT_SECONDS + RESERVE_SECONDS + 120
COORDINATOR_SECONDS = 900 + CAPTURE_SECONDS


def load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


io = load("repeat_host_io", ROOT / ".agents/skills/e-track-flutter-debug/scripts/host_io.py")


def require(condition, message):
    if not condition:
        raise RuntimeError(message)


def checked(path):
    return io.checked_output(ROOT, path)


def read(path):
    return json.loads(Path(path).read_text(encoding="utf-8"))


def record(path):
    path = Path(path)
    return dict(path=str(path), bytes=path.stat().st_size,
                sha256=hashlib.sha256(path.read_bytes()).hexdigest())


def now():
    return dt.datetime.now(dt.timezone.utc).isoformat()


def write(path, value, *, replace=False):
    return io.write_json(ROOT, path, value, replace=replace)


def unchanged(item):
    require(record(item["path"]) == item, "source/evidence changed: " + item["path"])


def unchanged_source(item, *, completed=False):
    if Path(item["path"]).is_file() and record(item["path"]) == item:
        return
    require(completed, "source/evidence changed: " + item["path"])
    checked(item["path"])
    require(re.fullmatch(r"[0-9a-f]{64}", item["sha256"]), "invalid archived source digest")
    matches = []
    for name in ("manifest-v1.json", "manifest-v2.json"):
        manifest = read(checked(SOURCE_ARCHIVE / name))
        require(manifest["root"] == str(ROOT) and manifest["all_cycle_workers_closed"] is True,
                "source archive does not bind closed project runs")
        matches.extend(entry for entry in manifest["files"] if entry["original"] == item)
    require(len(matches) == 1, "changed source has no exact preserved archive binding")
    path = checked(SOURCE_ARCHIVE / (item["sha256"] + ".py"))
    require(matches[0]["archive"] == str(path) and path.is_file(), "missing original source archive")
    actual = record(path)
    require(actual["sha256"] == item["sha256"] and actual["bytes"] == item["bytes"],
            "original source archive changed")


def valid_name(name):
    require(re.fullmatch(r"[a-z][a-z0-9-]{0,47}", name), "simple unique run name required")
    return name


def healthy(value, *, unused=False):
    require(value["healthy"] and value["lost"] == 0 and value["error"] is None,
            "unhealthy App observation; preserve evidence and reconcile")
    if unused:
        require(value["upgradeStarts"] == value["upgradeEnds"] == 0 and
                value["outcome"] is None, "App has already started; do not arm/replay")


def ready_state(value, age):
    state = value["state"]
    if state["epoch"] is None:
        require(not value.get("error") and not value["preflight_ready"] and
                not any(state[key] for key in ("begin_reserved", "baseline_confirmed",
                    "target_bcb_observed", "ready_to_begin", "ready_for_final_readback")) and
                state.get("begin_epoch") is None,
                "unobserved epoch conflicts with prior readiness or activity")
        return False
    require(not value.get("error"), "MCU observation has an error")
    require(state["epoch"] == 0 and not state["begin_reserved"] and
            not state["target_bcb_observed"] and not state["ready_for_final_readback"] and
            state.get("begin_epoch") is None,
            "MCU is no longer an unused baseline; do not recover as a prelaunch failure")
    return (0 <= age < 10 and value["preflight_ready"] and state["baseline_confirmed"] and
            state["ready_to_begin"])


def wait_ready(snapshot, closed, *, seconds=10, clock=time.monotonic, sleep=time.sleep):
    """The immutable preflight can precede its next periodic status projection."""
    deadline = clock() + seconds
    while True:
        require(not closed(), "MCU observer closed; no App launch")
        value, age = snapshot()
        if value is not None and ready_state(value, age):
            return value
        require(clock() < deadline, "live baseline status did not become ready within its bound")
        sleep(.1)


def verify_board(path, *, restored=False):
    value = read(path)
    expected = "RESTORED_326_VERIFIED" if restored else "TARGET_VERIFIED_RETAINED"
    require(value["result"] == expected and value["reader_closed"] and value["sd_ready"] == 1,
            "full device verification/reader closure/SD readiness required")
    for key, sha, size in (("final_image", BASE_SHA if restored else TARGET_SHA, 603764),
                           ("final_boot", BOOT_SHA, 65536)):
        item = value[key]
        actual = record(item["path"])
        require(actual["sha256"] == item["sha256"] == sha and actual["bytes"] == size,
                "wrong full " + key)
    if restored:
        require(value["final_bcb_confirmation"] == "OTA: BCB already CONFIRMED vcode=30206" and
                Path(value["final_journal"]["path"]).read_bytes() == b"\xff" * 4096,
                "fresh baseline confirmation and erased staging required")
    else:
        require(value["state"]["target_bcb_observed"] and value["state"]["ready_for_final_readback"],
                "fresh target Boot confirmation required")
    return value


def verify_finished(path):
    value = read(path)
    summary, inputs = value["summary"], value["summary"]["input"]
    require(value["parser_exit"] == 0 and summary["outcome"] == "completed" and
            summary["target"].lower() == TARGET and inputs["deviceAddress"].lower() == TARGET and
            inputs["packageSha256"] == PACKAGE_SHA and inputs["packageBytes"] == PACKAGE_BYTES and
            inputs["currentVersionCode"] == 30206 and inputs["currentImageSha256"] == BASE_SHA and
            inputs["targetVersionCode"] == 30207 and inputs["targetImageSha256"] == TARGET_SHA,
            "finished snapshot identity/outcome mismatch")
    require(record(Path(path).parent / "snapshot.jsonl")["sha256"] == summary["rawSha256"] and
            record(Path(path).parent / "parsed/observations.log")["sha256"] == summary["unwrappedSha256"],
            "original snapshot or unwrapped log changed")
    return value


class Journal:
    """An intent never authorizes replay; only a verified original result is adopted."""

    def __init__(self, out, binding):
        self.out, self.binding = checked(out), binding

    def phase(self, name, action, evidence, validate=lambda path: read(path)):
        intent = self.out / "actions" / (name + ".intent.json")
        done = self.out / "actions" / (name + ".done.json")
        evidence = checked(evidence)
        for path in (intent, done, evidence):
            checked(path)
        if done.exists():
            value = read(done)
            require(value["binding"] == self.binding and value["evidence"]["path"] == str(evidence),
                    "phase binding changed")
            unchanged(value["evidence"])
            return validate(evidence)
        if evidence.exists():
            result = validate(evidence)
            write(done, dict(time=now(), binding=self.binding, evidence=record(evidence), adopted=True))
            return result
        require(not intent.exists(), name + " outcome uncertain; reconcile original evidence, never replay")
        write(intent, dict(time=now(), binding=self.binding, evidence=str(evidence), status="started"))
        action()
        require(evidence.exists(), name + " returned without evidence; do not repeat")
        result = validate(evidence)
        write(done, dict(time=now(), binding=self.binding, evidence=record(evidence), adopted=False))
        return result

    def status(self, state, **details):
        value = dict(time=now(), state=state, **details)
        write(self.out / "status.json", value, replace=True)
        print(json.dumps(value), flush=True)


class Backend:
    def __init__(self, config):
        self.config, self.out = config, checked(config["out"])
        require(record(HERE / "matrix_run.py")["sha256"] == MATRIX_SHA, "admitted matrix backend changed")
        self.m = load("repeat_matrix", HERE / "matrix_run.py")
        self.b = self.m.b
        require(self.m.ROOT == ROOT, "backend/project root mismatch")
        self.m.authority()
        test = read(HERE / "resume/matrix-tests-r1.json")
        require(test["passed"] and test["source"] == self.b.record(HERE / "matrix_run.py"),
                "original matrix regression missing")
        for key in ("capture", "restore"):
            require(self.b.record(test[key]["path"]) == test[key], "tested backend changed")
        self.original_phone, self.original_collector = self.m.phones.phone, self.m.collector
        self.m.phones.phone = self.m.d.phone = self.phone
        self.m.collector = self.m.d.collector = self.collector
        self.label = "cycle-" + config["run"]
        self.m.LABELS[config["candidate"]] = self.label
        self.cell = checked(self.out / "cells" / config["candidate"])
        self.runtime = checked(self.out / "phone-r1")
        self.supervisor = self.b.load("repeat_supervisor", HERE / "supervisor.py")
        self.journal = Journal(self.out, config.get("binding", config["run"]))

    def phone(self):
        p = self.original_phone()
        p.RUNTIME = self.runtime
        p.cell = lambda candidate: checked(self.out / "cells" / candidate)
        return p

    def collector(self):
        c = self.original_collector()
        c.OUT, c.SECONDS = self.out, CAPTURE_SECONDS
        require(c.base.MIN_START_WINDOW == RESERVE_SECONDS, "transfer reserve changed")
        return c

    def preflight(self):
        destinations = [self.out, RUNS / "device.lock", self.b.OUT / "actions.jsonl",
                        self.b.OUT / "host", RESTORE / "host", RESTORE / self.label,
                        RESTORE / "finalized" / self.label, RESTORE / ("execute-" + self.label),
                        RESTORE / ("flash-" + self.label + ".log"),
                        RESTORE / ("flash-" + self.label + ".json")]
        for path in destinations:
            checked(path)
        # Stable existing children, not another worker's ephemeral *.tmp files.
        for parent in (self.out, self.b.OUT / "host", RESTORE / "host"):
            if parent.exists():
                for directory, children, files in os.walk(parent, followlinks=False):
                    for name in children + [f for f in files if not f.endswith(".tmp")]:
                        checked(Path(directory) / name)
        for item in self.config.get("sources", []):
            unchanged(item)
        os.environ.update(self.b.environment())

    def worker(self, name, mode, seconds):
        out = self.out / name
        return self.journal.phase(name, lambda: self.supervisor.owned.launch(
            out, SELF, [mode, "--run", self.config["run"]], seconds), out / "ready.json",
            lambda path: self.validate_runtime(path))

    @staticmethod
    def validate_runtime(path):
        value = read(path)
        require(value["detached_from_job"], "worker did not detach from agent lifetime")
        return value

    def await_file(self, path, seconds=90):
        deadline = time.monotonic() + seconds
        while not Path(path).exists():
            require(time.monotonic() < deadline, "readiness deadline: " + str(path))
            time.sleep(.5)
        return read(path)

    def start_phone(self):
        p = self.phone()
        if not (self.out / "adb/ready.json").exists():
            old = read(Path(self.config["prior_phone"]) / "closed.json")
            closed = read(Path(self.config["prior_phone_supervisor"]) / "closed.json")
            require(old["result"] == "SERVER_STOPPED" and old["port_closed"] and
                    old.get("stop_exit") == 0 and not old.get("forced_cleanup") and
                    closed["worker_exit"] == 0 and not closed["forced_termination"] and
                    not closed.get("error") and not p.alive(), "prior private ADB closure unresolved")
        self.worker("adb", "phone-worker", 5430)
        ready = self.await_file(self.runtime / "ready.json", 30)
        require(not (self.runtime / "closed.json").exists() and p.alive() and
                dt.datetime.fromisoformat(ready["deadline"]).timestamp() > time.time() + 90,
                "private ADB window closed; reconcile/renew host only, never replay device work")
        p.phone_identity()

    def release(self):
        previous, p = self.config["previous"], self.phone()
        finished = verify_finished(Path(self.config["previous_cell"]) / "finished/binding.json")
        verify_board(self.config["previous_board"])
        require(p.installed(previous), "exact previous APK required")
        require(p.apk(previous)["apk"] == finished["apk"], "previous snapshot/APK mismatch")
        pkg = p.package(previous)
        pid = p.command(["shell", "pidof", pkg], check=False).strip()
        if pid:
            actual_pkg, actual_pid, remote = p.location(previous)
            value = json.loads(p.file_bytes(actual_pkg, remote + "/health.json", 8192))
            healthy(value)
            require(actual_pid == finished["pid"] and remote == finished["remote"] and
                    value["upgradeStarts"] == value["upgradeEnds"] == 1 and
                    value["outcome"] == "completed", "previous App may be active; do not stop it")
            write(self.out / "release-request.json", dict(time=now(), package=pkg, pid=actual_pid,
                  health=value, reason="release only verified completed debug App; preserve data"))
            p.command(["shell", "am", "force-stop", pkg])
        require(not p.command(["shell", "pidof", pkg], check=False).strip(), "previous App not stopped")
        write(self.out / "released.json", dict(time=now(), package=pkg, stopped=True))

    def restore(self):
        c = self.config["candidate"]
        self.journal.phase("admit", lambda: self.m.admit(c),
            RESTORE / self.label / "live-before/result.json", self.admission)
        self.journal.phase("restore", lambda: self.m.restore(c),
            RESTORE / ("execute-" + self.label) / "result.json",
            lambda path: verify_board(path, restored=True))

    @staticmethod
    def admission(path):
        value = read(path)
        require(value["result"] == "BACKUP_AND_BOOT_VERIFIED" and value["reader_closed"] and
                value["boot_region"]["sha256"] == BOOT_SHA and
                value["backup_image"]["sha256"] == BASE_SHA,
                "full physical backup/Boot admission failed")
        return value

    def launch_app(self):
        c, p = self.config["candidate"], self.phone()
        require(p.installed(c), "candidate APK missing; no automatic replacement")
        pid = p.command(["shell", "pidof", p.package(c)], check=False).strip()
        require(not pid, "candidate already running; reconcile its original process before launch")
        p.launch(c)

    def app_state(self, *, allow_unready=False):
        p = self.phone()
        if allow_unready:
            pkg = p.package(self.config["candidate"])
            pid = p.command(["shell", "pidof", pkg], check=False).strip()
            if not pid:
                return None
            names = p.command(["exec-out", "run-as", pkg, "ls", "-1", "files/p34-observations"], check=False)
            if not names.strip() or "No such file" in names:
                return None
        pkg, pid, remote = p.location(self.config["candidate"])
        value = json.loads(p.file_bytes(pkg, remote + "/health.json", 8192))
        healthy(value)
        return dict(package=pkg, pid=pid, remote=remote, health=value)

    def query_ready(self):
        state, p = self.app_state(allow_unready=True), self.phone()
        if state is None:
            return None
        healthy(state["health"], unused=True)
        path = "app_flutter/firmware/baseline-full.etu"
        size = p.command(["exec-out", "run-as", state["package"], "stat", "-c", "%s", path], check=False).strip()
        if not size.isdigit():
            require("No such file" in size, "download status unknown: inspect original ADB receipt")
            return None
        if int(size) < PACKAGE_BYTES:
            return None
        require(int(size) == PACKAGE_BYTES, "downloaded package length mismatch")
        p.inspect(self.config["candidate"])
        paths = sorted((self.cell / "queries").glob("*/start-inputs.json"))
        return paths[-1] if paths else None

    def monitor(self):
        c = self.config["candidate"]
        arm = self.cell / "mcu/ota-reserved.json"
        query_deadline = time.monotonic() + PREPARE_SECONDS
        if not arm.exists():
            self.journal.status("NEEDS_USER", action="Connect BLE in the selected App, query firmware and download; do not start OTA yet.",
                                candidate=c, package=self.phone().package(c))
            while not arm.exists():
                require(time.monotonic() < query_deadline, "phone preparation window ended; no OTA initiated by host")
                require(not (self.cell / "mcu/result.json").exists(), "MCU observer ended before arm")
                inputs = self.query_ready()
                if inputs:
                    state = read(self.cell / "mcu/state.json")
                    require(state["remaining_seconds"] >= START_WAIT_SECONDS + RESERVE_SECONDS,
                            "not enough separate user-start plus transfer/verification time")
                    self.journal.phase("arm", lambda: self.m.d.arm(c), arm)
                    break
                self.journal.status("NEEDS_USER", candidate=c,
                                    action="Connect BLE and download the package in the selected App; do not start OTA yet.")
                time.sleep(8)
        self.journal.status("READY_TO_START", candidate=c,
                            action="Tap upgrade once in the foreground App; no chat acknowledgement needed.",
                            start_wait_seconds=START_WAIT_SECONDS, transfer_reserve_seconds=RESERVE_SECONDS)
        while True:
            board = self.cell / "mcu/result.json"
            if board.exists():
                verify_board(board)
            state = self.app_state()
            h = state["health"]
            require(h["upgradeStarts"] <= 1 and h["upgradeEnds"] <= 1, "multiple App invocations; reconcile")
            if h["upgradeEnds"]:
                require(h["outcome"] == "completed", "App transfer failed; preserve snapshot, no automatic retry")
                self.journal.phase("finished", lambda: self.phone().finished(c),
                                   self.cell / "finished/binding.json", verify_finished)
                if board.exists():
                    break
            self.journal.status("OBSERVING" if h["upgradeStarts"] else "READY_TO_START", candidate=c,
                                actual_starts=h["upgradeStarts"], actual_ends=h["upgradeEnds"],
                                policy="A suggested start deadline never abandons a possibly active transfer.")
            time.sleep(8)
        self.finish_cycle()

    def finish_cycle(self):
        c = self.config["candidate"]
        board = self.cell / "mcu/result.json"
        verify_finished(self.cell / "finished/binding.json")
        verify_board(board)
        self.await_file(self.out / "mcu-worker/closed.json", 30)
        closed = read(self.out / "mcu-worker/closed.json")
        require(closed["worker_exit"] == 0 and not closed["forced_termination"] and not closed.get("error"),
                "MCU supervisor closure unresolved")
        self.journal.phase("measurement", lambda: write(self.cell / "measurement.json", measurement(self.cell, board, c)),
                           self.cell / "measurement.json")
        if not (self.out / "completed.json").exists():
            write(self.out / "completed.json", dict(time=now(), candidate=c, result="TARGET_VERIFIED_RETAINED",
                  measurement=record(self.cell / "measurement.json"), independent_acceptance=False))
        self.journal.status("COMPLETED", candidate=c, measurement=str(self.cell / "measurement.json"))

    def run(self):
        self.preflight()
        if (self.out / "completed.json").exists():
            unchanged(read(self.out / "completed.json")["measurement"])
            self.journal.status("COMPLETED", reused=True)
            return
        if (self.cell / "finished/binding.json").exists() and (self.cell / "mcu/result.json").exists():
            self.finish_cycle()
            return
        self.start_phone()
        self.journal.status("PREPARING", candidate=self.config["candidate"])
        self.journal.phase("release", self.release, self.out / "released.json")
        self.restore()
        self.worker("mcu-worker", "capture-worker", CAPTURE_SECONDS + 30)
        self.await_file(self.cell / "mcu/preflight.json", 120)
        if not (self.cell / "launched.json").exists():
            self.fresh_baseline()
        self.journal.phase("launch", self.launch_app, self.cell / "launched.json")
        self.monitor()

    def fresh_baseline(self):
        path = self.cell / "mcu/state.json"
        def snapshot():
            return (read(path), time.time() - path.stat().st_mtime) if path.exists() else (None, 0)
        def closed():
            return any(p.exists() for p in (self.cell / "mcu/result.json",
                self.out / "mcu-worker/closed.json", self.cell / "stop.json"))
        return wait_ready(snapshot, closed)


def measurement(cell, board, candidate):
    cell = Path(cell)
    finished, physical = verify_finished(cell / "finished/binding.json"), verify_board(board)
    rows = [json.loads(line.split("OTA_LINK_STATS ", 1)[1]) for line in
            (cell / "finished/parsed/observations.log").read_text(encoding="utf-8").splitlines()
            if line.startswith("OTA_LINK_STATS ")]
    upgrades = [v for v in rows if v["label"] == "upgrade" and v["transfer"]["elapsedUs"] is not None]
    require(len(upgrades) == 1, "one original upgrade summary required")
    value, transfer = upgrades[0], upgrades[0]["transfer"]
    require(transfer["elapsedUs"] > 0 and value["device"].lower() == TARGET, "invalid measured transfer")
    seconds = transfer["elapsedUs"] / 1e6
    reconnect = [v["phases"]["reconnect"] for v in rows if "reconnect" in v["phases"]]
    return dict(candidate=candidate, package_bytes=PACKAGE_BYTES, package_sha256=PACKAGE_SHA,
        apk=finished["apk"], transfer_seconds=seconds, payload_kib_s=PACKAGE_BYTES / 1024 / seconds,
        data_segments_unique=transfer["segmentsUnique"], data_retransmit_frames=transfer["retransmitFrames"],
        write_mode=value["bind"]["writeMode"], mtu_chunk_bytes=value["bind"]["mtuChunkBytes"],
        gatt_writes=value["gattWrites"], discovers=value["discovers"], platform_writes=value["platformWrites"],
        ack_sample_status=transfer["ackSamples"], ack_early_invalid=transfer["ackEarlyInvalid"],
        reconnect_phase_seconds=(reconnect[0][1] - reconnect[0][0]) / 1e6 if len(reconnect) == 1 else None,
        threshold_eligible=False, independent_acceptance="NOT_RUN",
        limits="Screening only. Partial/early ACKs cannot establish P99; discovery is nested in GATT time.",
        binding=record(cell / "finished/binding.json"), statistics=record(cell / "finished/statistics.json"),
        device_result=record(board), final_image_sha256=physical["final_image"]["sha256"],
        whole_boot_sha256=physical["final_boot"]["sha256"], sd_ready=physical["sd_ready"])


def sources():
    paths = [SELF, SELF.with_name("test_repeat_cycle.py"), SELF.with_name("resume_cycle.py"), Path(io.__file__)]
    paths += [HERE / (name + ".py") for name in ("matrix_run", "device_run", "phone_window", "phone",
              "capture", "supervisor", "service_run", "batch", "resume", "download")]
    paths += [RESTORE / (name + ".py") for name in ("inspect_device", "restore_device", "build_helper")]
    return [record(path) for path in paths]


def config_for(run, *, completed=False):
    out = checked(RUNS / valid_name(run))
    path = out / "config.json"
    value = read(path)
    require(value["run"] == run and value["out"] == str(out) and value["root"] == str(ROOT), "run root changed")
    if completed:
        result = read(out / "completed.json")
        require(result["candidate"] == value["candidate"] and result["result"] == "TARGET_VERIFIED_RETAINED",
                "only verified completed runs may use preserved historical source")
        unchanged(result["measurement"])
    for item in value["sources"]:
        unchanged_source(item, completed=completed)
    value["binding"] = record(path)
    return value


def completed_phone_route(out):
    routes = []
    for ready_path in Path(out).glob("phone-*/ready.json"):
        runtime = ready_path.parent
        if runtime.name == "phone-r1":
            supervisor = Path(out) / "adb"
        else:
            require(runtime.name.startswith("phone-recovery-"), "unknown private ADB runtime")
            label = valid_name(runtime.name.removeprefix("phone-recovery-"))
            supervisor = Path(out) / ("adb-recovery-" + label)
        require((runtime / "closed.json").exists() and (supervisor / "closed.json").exists(),
                "previous private ADB route is not closed")
        ready, closed, owned = read(ready_path), read(runtime / "closed.json"), read(supervisor / "closed.json")
        require(ready["port"] == closed["port"] == 5062 and
                ready["serial"] == closed["serial"] == "10ADA4197U001CK" and
                closed["result"] == "SERVER_STOPPED" and closed["port_closed"] and
                closed.get("stop_exit") == 0 and not closed.get("forced_cleanup") and
                owned["worker_exit"] == 0 and not owned["forced_termination"] and not owned.get("error"),
                "previous private ADB closure/identity unresolved")
        routes.append((dt.datetime.fromisoformat(ready["time"]), runtime, supervisor))
    require(routes, "completed predecessor has no private ADB route")
    _, runtime, supervisor = max(routes, key=lambda item: item[0])
    return runtime, supervisor


@contextlib.contextmanager
def device_lock():
    import msvcrt
    path = checked(RUNS / "device.lock")
    checked(path.parent).mkdir(parents=True, exist_ok=True)
    with path.open("a+b") as stream:
        if not path.stat().st_size:
            stream.write(b"0")
            stream.flush()
        stream.seek(0)
        msvcrt.locking(stream.fileno(), msvcrt.LK_NBLCK, 1)
        try:
            yield
        finally:
            stream.seek(0)
            msvcrt.locking(stream.fileno(), msvcrt.LK_UNLCK, 1)


def start(args):
    out = checked(RUNS / valid_name(args.run))
    require(not out.exists(), "run exists; use status/resume, never reuse a label for a new trial")
    for previous in RUNS.glob("*/config.json"):
        require((previous.parent / "completed.json").exists(),
                "another cycle is incomplete; reconcile it before a new device mutation: " + str(previous.parent))
    test = read(checked(args.tests))
    require(test["passed"] and test["hardware_contacted"] is False and
            test["driver"] == record(SELF) and test["tests"] == record(SELF.with_name("test_repeat_cycle.py")),
            "run current host self-tests before hardware")
    previous_cell = REGISTRY / "cells" / args.previous
    prior_phone, prior_sup = REGISTRY / "phone-r2", HERE / "resume/wmi-phone-r4"
    if args.previous_run:
        previous = config_for(args.previous_run, completed=True)
        require(previous["candidate"] == args.previous and (Path(previous["out"]) / "completed.json").exists(),
                "previous run is not a completed candidate")
        previous_cell = Path(previous["out"]) / "cells" / args.previous
        prior_phone, prior_sup = completed_phone_route(previous["out"])
    board = previous_cell / ("mcu-r2/result.json" if args.previous == "baseline" and not args.previous_run else "mcu/result.json")
    verify_finished(previous_cell / "finished/binding.json")
    verify_board(board)
    config = dict(root=str(ROOT), out=str(out), run=args.run, candidate=args.candidate,
                  previous=args.previous, previous_cell=str(previous_cell), previous_board=str(board),
                  prior_phone=str(prior_phone), prior_phone_supervisor=str(prior_sup), created=now(),
                  sources=sources(), tests=record(checked(args.tests)), independent_acceptance=False)
    b = Backend(config)
    b.preflight()
    network = b.b.live()
    require(dt.datetime.fromisoformat(network["expires_at"]).timestamp() > time.time() + COORDINATOR_SECONDS + 60,
            "pinned HTTPS endpoint lacks the complete cycle budget; do not downgrade")
    require(not (RESTORE / b.label).exists() and not (RESTORE / ("execute-" + b.label)).exists(),
            "restore label already used")
    write(out / "config.json", config)
    resume(args.run)


def resume(run):
    out = checked(RUNS / valid_name(run))
    if (out / "completed.json").exists():
        config = config_for(run, completed=True)
        cell = out / "cells" / config["candidate"]
        verify_finished(cell / "finished/binding.json")
        verify_board(cell / "mcu/result.json")
        completed_phone_route(out)
        print(json.dumps(dict(state="COMPLETED", run=run, reused=True, device_commands=0)), flush=True)
        return
    config = config_for(run)
    b = Backend(config)
    b.preflight()
    old = sorted(b.out.glob("coordinator-*/ready.json"))
    for path in old:
        require((path.parent / "closed.json").exists(), "coordinator still owns run; use status")
    out = b.out / ("coordinator-%03d" % (len(old) + 1))
    require(not out.exists(), "uncertain coordinator launch; inspect original launch/closure receipts")
    ready = b.supervisor.owned.launch(out, SELF, ["work", "--run", run], COORDINATOR_SECONDS + 30)
    require(ready["detached_from_job"], "coordinator is not independent")
    print(json.dumps(dict(state="COORDINATOR_STARTED", run=run, status=str(b.out / "status.json"))), flush=True)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("mode", choices=("start", "resume", "status", "work", "phone-worker", "capture-worker", "measure"))
    parser.add_argument("--run")
    parser.add_argument("--candidate", choices=CANDIDATES)
    parser.add_argument("--previous", choices=("baseline", *CANDIDATES))
    parser.add_argument("--previous-run")
    parser.add_argument("--tests", default=str(ROOT / ".cache/p34-cycle-tests-r5/result.json"))
    parser.add_argument("--cell", type=Path)
    parser.add_argument("--board", type=Path)
    args = parser.parse_args()
    require(Path.cwd().resolve() == ROOT and sys.flags.isolated and sys.flags.no_site and sys.dont_write_bytecode,
            "explicit project cwd and Python -I -S -B required")
    if args.mode == "measure":
        require(args.cell and args.board and args.candidate, "measure needs cell, board and candidate")
        write(checked(args.cell / "measurement.json"), measurement(args.cell, args.board, args.candidate))
        return
    require(args.run, "run name required")
    if args.mode == "status":
        out = checked(RUNS / valid_name(args.run))
        print(json.dumps(read(out / "status.json") if (out / "status.json").exists() else
                         dict(state="STARTING_OR_UNKNOWN", run=args.run)), flush=True)
        return
    if args.mode == "start":
        require(args.candidate and args.previous, "candidate and completed previous candidate required")
        start(args)
        return
    if args.mode == "resume":
        resume(args.run)
        return
    b = Backend(config_for(args.run))
    b.preflight()
    if args.mode == "phone-worker":
        b.phone().server()
    elif args.mode == "capture-worker":
        raise SystemExit(b.m.capture(b.config["candidate"]))
    else:
        try:
            with device_lock():
                b.run()
        except Exception as error:
            b.journal.status("RECONCILE_REQUIRED", error=type(error).__name__ + ": " + str(error),
                             policy="Do not repeat flash, reset, launch or OTA to repair missing evidence.")
            raise
        finally:
            if (b.runtime / "ready.json").exists() and not (b.runtime / "closed.json").exists():
                stop = b.runtime / "stop.json"
                if not stop.exists():
                    write(stop, dict(time=now(), reason="coordinator finished; close only its private USB route"))


if __name__ == "__main__":
    main()
