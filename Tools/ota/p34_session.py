"""Reusable P3-4 session lifecycle. Status and stop never import the device backend."""
from __future__ import annotations

import argparse
from contextlib import contextmanager
import datetime as dt
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import re
import subprocess
import sys
import time

NETWORK_SECONDS = 5400
NETWORK_SUPERVISOR_SECONDS = 5480
NETWORK_READY_WAIT_SECONDS = 900
CELL_SECONDS = 3900
APP_START_SECONDS = 1500
CELLS = {"s01": (460800, 4), "s02": (460800, 8), "s03": (460800, 16), "s04": (921600, 4)}
# Comparison groups as declared by the frozen prefix entry.  This tuple only keeps the
# command line honest; the backend validates membership and reports any drift.
SUCCESSORS = {"n03-window8-repeat": dict(receiver=30218, target_version=30219, version_name="3.2.19-p34n",
    served_name="prefix-n03w8-repeat-full.etu", release_key="p34-n03-window8-repeat",
    assets=".cache/p34-session/n03-window8-repeat/assets/result.json",
    parent_assets=".cache/p34-session/n03-window8/assets/result.json")}
N04_GROUPS = {
    "n04-bootstrap": dict(receiver=30219, target_version=30220, version_name="3.2.20-p34i",
        served_name="prefix-n04-bootstrap-full.etu", release_key="p34-n04-bootstrap",
        assets=".cache/p34-session/n04/assets/x/result.json",
        parent_assets=SUCCESSORS["n03-window8-repeat"]["assets"], predecessor_group="n03-window8-repeat"),
    "n04-measure": dict(receiver=30220, target_version=30221, version_name="3.2.21-p34i",
        served_name="prefix-n04-measure-full.etu", release_key="p34-n04-measure",
        assets=".cache/p34-session/n04/assets/y/result.json",
        parent_assets=".cache/p34-session/n04/assets/x/result.json", predecessor_group="n04-bootstrap"),
    "n04-window16": dict(receiver=30221, target_version=30222, version_name="3.2.22-p34i",
        served_name="prefix-n04-window16-full.etu", release_key="p34-n04-window16",
        assets=".cache/p34-session/n04-window16/assets/result.json",
        parent_assets=".cache/p34-session/n04/assets/y/result.json", predecessor_group="n04-measure"),
}
PATCH_GROUPS = {
    "patch-bootstrap": dict(receiver=30221, target_version=30223, version_name="3.2.23-p34c",
        served_name="p34-coalesce-bootstrap-full.etu", release_key="p34-patch-bootstrap", kind="full",
        assets=".cache/p34-patch-next/assets/result.json", asset_group="bootstrap", predecessor_group="n04-measure"),
    "patch-compact": dict(receiver=30223, target_version=30224, version_name="3.2.24-p34c",
        served_name="p34-coalesce-compact-patch.etu", release_key="p34-patch-compact", kind="patch",
        assets=".cache/p34-patch-next/assets/result.json", asset_group="compact", predecessor_group="patch-bootstrap"),
    "patch-pressure": dict(receiver=30223, target_version=30224, version_name="3.2.24-p34c",
        served_name="p34-coalesce-pressure-patch.etu", release_key="p34-patch-pressure", kind="patch",
        assets=".cache/p34-patch-next/assets/result.json", asset_group="pressure", predecessor_group="patch-bootstrap"),
}
NATIVE_DIAGNOSTIC_GROUP = "n04-diagnostic8"
# Same immutable Y-to-Z asset as the paused window-16 arm, separate axes/owner.
N04_GROUPS[NATIVE_DIAGNOSTIC_GROUP] = dict(N04_GROUPS["n04-window16"])
SPEED16_GROUP = "speed-window16"
N04_GROUPS[SPEED16_GROUP] = dict(receiver=30222, target_version=30225, version_name="3.2.25-p34s",
    served_name="p34-speed-window16-full.etu", release_key="p34-speed-window16",
    assets=".cache/p34-session/speed-window16/assets/result.json",
    parent_assets=N04_GROUPS["n04-window16"]["assets"], predecessor_group=NATIVE_DIAGNOSTIC_GROUP)
SPEED32_GROUP = "speed-window32"
N04_GROUPS[SPEED32_GROUP] = dict(receiver=30225, target_version=30226, version_name="3.2.26-p34s",
    served_name="p34-speed-window32-full.etu", release_key="p34-speed-window32",
    assets=".cache/p34-session/speed-window32/assets/result.json",
    parent_assets=N04_GROUPS[SPEED16_GROUP]["assets"], predecessor_group=SPEED16_GROUP)
PATCH32_GROUPS = {
    "patch32-bootstrap": dict(receiver=30226, target_version=30227, version_name="3.2.27-p34c",
        served_name="p34-coalesce-bootstrap-full.etu", release_key="p34-patch32-bootstrap", kind="full",
        assets=".cache/p34-patch32/assets/result.json", asset_group="bootstrap", predecessor_group=SPEED32_GROUP),
    "patch32-pressure": dict(receiver=30227, target_version=30228, version_name="3.2.28-p34c",
        served_name="p34-coalesce-pressure-patch.etu", release_key="p34-patch32-pressure", kind="patch",
        assets=".cache/p34-patch32/assets/result.json", asset_group="pressure", predecessor_group="patch32-bootstrap"),
}
BOOT_COPY_GROUP = "boot-copy-measure"
COST_GROUPS = {
    "cost-bootstrap": dict(receiver=30238, target_version=30239, version_name="3.2.39-p34c",
        served_name="p34-cost-bootstrap-full.etu", release_key="p34-cost-bootstrap", kind="full",
        assets=".cache/p34-cost/assets/result-v2.json", asset_group="bootstrap", predecessor_group=BOOT_COPY_GROUP),
    "cost-measure": dict(receiver=30239, target_version=30240, version_name="3.2.40-p34c",
        served_name="p34-cost-measure-full.etu", release_key="p34-cost-measure", kind="full",
        assets=".cache/p34-cost/assets/result-v2.json", asset_group="measure", predecessor_group="cost-bootstrap"),
}
ERASE_GROUPS = {
    "erase-bootstrap": dict(receiver=30240, target_version=30241, version_name="3.2.41-p34e",
        served_name="p34-erase-bootstrap-full.etu", release_key="p34-erase-bootstrap", kind="full",
        assets=".cache/p34-erase/assets/result.json", asset_group="bootstrap", predecessor_group="cost-measure"),
    "erase-measure": dict(receiver=30241, target_version=30242, version_name="3.2.42-p34e",
        served_name="p34-erase-measure-full.etu", release_key="p34-erase-measure", kind="full",
        assets=".cache/p34-erase/assets/result.json", asset_group="measure", predecessor_group="erase-bootstrap"),
}
RECONNECT_GROUP = "reconnect-measure"
RECONNECT_SPEC = dict(receiver=30242, target_version=30243, version_name="3.2.43-p34r",
    served_name="p34-reconnect-full.etu", release_key="p34-reconnect", kind="full",
    assets=".cache/p34-reconnect/assets/result.json", asset_group="measure", predecessor_group="erase-measure")
NEW_BOOT_GROUPS = (BOOT_COPY_GROUP, *COST_GROUPS, *ERASE_GROUPS, RECONNECT_GROUP)
ACK_GAP_GROUPS = {
    RECONNECT_GROUP: RECONNECT_SPEC,
    **ERASE_GROUPS,
    **COST_GROUPS,
    BOOT_COPY_GROUP: dict(receiver=30235, target_version=30238, version_name="3.2.38-p34b",
        served_name="p34-boot-copy-full.etu", release_key="p34-boot-copy", kind="full",
        assets=".cache/p34-boot/ota-assets/validated.json", asset_group="bootstrap", predecessor_group="ack-batch-bootstrap"),
    "ack-batch-bootstrap": dict(receiver=30232, target_version=30235, version_name="3.2.35-p34b",
        served_name="p34-ack-batch-full.etu", release_key="p34-ack-batch", kind="full",
        assets=".cache/p34ab/assets/session-assets.json", asset_group="bootstrap", predecessor_group="ack-gap-bootstrap"),
    "ack-gap-bootstrap": dict(receiver=30230, target_version=30232, version_name="3.2.32-p34g",
        served_name="p34-ack-gap-full.etu", release_key="p34-ack-gap", kind="full",
        assets=".cache/p34ag/assets/session-assets.json", asset_group="bootstrap", predecessor_group="receive-pressure"),
}
RECEIVE_GROUPS = {
    "receive-bootstrap": dict(receiver=30228, target_version=30229, version_name="3.2.29-p34r",
        served_name="p34-coalesce-bootstrap-full.etu", release_key="p34-receive-bootstrap", kind="full",
        assets=".cache/p34-receive-screen/assets/result.json", asset_group="bootstrap", predecessor_group="patch32-pressure"),
    "receive-pressure": dict(receiver=30229, target_version=30230, version_name="3.2.30-p34r",
        served_name="p34-coalesce-pressure-patch.etu", release_key="p34-receive-pressure", kind="patch",
        assets=".cache/p34-receive-screen/assets/result.json", asset_group="pressure", predecessor_group="receive-bootstrap"),
}
ALL_PATCH_GROUPS = {**PATCH_GROUPS, **PATCH32_GROUPS, **RECEIVE_GROUPS, **ACK_GAP_GROUPS}
N04_LINEAGE_GROUPS = (*N04_GROUPS, *ALL_PATCH_GROUPS)
WINDOW8_GROUPS = ("n03-window8", *SUCCESSORS, "n04-bootstrap", "n04-measure", NATIVE_DIAGNOSTIC_GROUP, *PATCH_GROUPS)
FULL_SUCCESSOR_GROUPS = (*WINDOW8_GROUPS, "n04-window16", SPEED16_GROUP, SPEED32_GROUP, *PATCH32_GROUPS, *RECEIVE_GROUPS, *ACK_GAP_GROUPS)
MEASURED_FULL_GROUPS = ("n03-full", *FULL_SUCCESSOR_GROUPS)
INSTALL_GROUPS = ("n03-install", *MEASURED_FULL_GROUPS)
GROUPS = ("screen", "n03-a", "n03-b", *INSTALL_GROUPS)
FULL_VERSIONS = {"n03-install": (30214, 30215), "n03-full": (30215, 30217), "n03-window8": (30217, 30218)}
FULL_VERSIONS.update({name: (spec["receiver"], spec["target_version"]) for name, spec in
                      {**SUCCESSORS, **N04_GROUPS, **ALL_PATCH_GROUPS}.items()})
PREDECESSOR_GROUPS = {"n03-window8": "n03-full", "n03-window8-repeat": "n03-window8",
                     **{name: spec["predecessor_group"] for name, spec in {**N04_GROUPS, **ALL_PATCH_GROUPS}.items()}}
INSTALL_CELL = "s04"
INSTALL_ACTIVE_SECONDS = 900
HOST_TEST_SECONDS = 900
RUN_NAME = re.compile(r"[a-zA-Z0-9-]{1,64}")


def require(value, message):
    if not value:
        raise RuntimeError(message)


def cells_for(group):
    if group in NEW_BOOT_GROUPS:
        return dict(CELLS, s04=(921600, 28))
    if group == SPEED32_GROUP or group in (*PATCH32_GROUPS, *RECEIVE_GROUPS, *ACK_GAP_GROUPS):
        return dict(CELLS, s04=(921600, 32))
    if group in ("n04-window16", SPEED16_GROUP):
        return dict(CELLS, s04=(921600, 16))
    return dict(CELLS, s04=(921600, 8)) if group in WINDOW8_GROUPS else dict(CELLS)


def n04_asset_groups(group):
    require(group in N04_LINEAGE_GROUPS, "unknown N04 asset group")
    # X/Y were frozen together; later groups must not become old-run dependencies.
    if group == SPEED32_GROUP or group in (*PATCH32_GROUPS, *RECEIVE_GROUPS, *ACK_GAP_GROUPS):
        return ("n04-bootstrap", "n04-measure", "n04-window16", SPEED16_GROUP, SPEED32_GROUP)
    if group == SPEED16_GROUP:
        return ("n04-bootstrap", "n04-measure", "n04-window16", SPEED16_GROUP)
    return ("n04-bootstrap", "n04-measure", "n04-window16") if group in ("n04-window16", NATIVE_DIAGNOSTIC_GROUP) else ("n04-bootstrap", "n04-measure")


def patch_asset_groups(group):
    require(group in ALL_PATCH_GROUPS, "unknown prepared PATCH group")
    if group == RECONNECT_GROUP:
        return (*patch_asset_groups("erase-measure"), group)
    if group in ERASE_GROUPS:
        return (*patch_asset_groups("cost-measure"), "erase-bootstrap") + (
            ("erase-measure",) if group == "erase-measure" else ())
    if group in COST_GROUPS:
        return (*patch_asset_groups(BOOT_COPY_GROUP), "cost-bootstrap") + (
            ("cost-measure",) if group == "cost-measure" else ())
    if group == BOOT_COPY_GROUP:
        return (*patch_asset_groups("ack-batch-bootstrap"), group)
    if group == "ack-batch-bootstrap":
        return (*patch_asset_groups("ack-gap-bootstrap"), group)
    if group == "ack-gap-bootstrap":
        return ("patch32-bootstrap", "patch32-pressure", "receive-bootstrap", "receive-pressure", group)
    if group in RECEIVE_GROUPS:
        return ("patch32-bootstrap", "patch32-pressure", "receive-bootstrap") + (
            ("receive-pressure",) if group == "receive-pressure" else ())
    if group in PATCH32_GROUPS:
        return ("patch32-bootstrap",) if group == "patch32-bootstrap" else ("patch32-bootstrap", group)
    return ("patch-bootstrap",) if group == "patch-bootstrap" else ("patch-bootstrap", group)


def patch_assets_api(store, group):
    require(group in ALL_PATCH_GROUPS, "unknown PATCH assets adapter")
    name = ("p34_reconnect_assets" if group == RECONNECT_GROUP else
            "p34_erase_assets" if group in ERASE_GROUPS else
            "p34_cost_assets" if group in COST_GROUPS else
            "p34_boot_ota_assets" if group == BOOT_COPY_GROUP else
            "p34_ack_batch_assets" if group == "ack-batch-bootstrap" else
            "p34_ack_gap_assets" if group == "ack-gap-bootstrap" else
            "p34_receive_assets" if group in RECEIVE_GROUPS else
            "p34_patch32_assets" if group in PATCH32_GROUPS else "p34_patch_assets")
    return load_module(name, store.root / "Tools/ota" / (name + ".py"))


def now():
    return dt.datetime.now(dt.timezone.utc).isoformat()


def record(path):
    path = Path(path)
    data = path.read_bytes()
    return dict(path=str(path), bytes=len(data), sha256=hashlib.sha256(data).hexdigest())


def load_module(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


class Store:
    def __init__(self, root):
        root = Path(root)
        require(root.is_absolute() and root.is_dir(), "existing absolute project root required")
        self.io = load_module("p34_session_io", root / ".agents/skills/e-track-flutter-debug/scripts/host_io.py")
        self.root = self.io.checked_output(root, root)
        self.base = self.checked(root / ".cache/p34-session")

    def checked(self, path):
        return self.io.checked_output(self.root, path)

    def read(self, path):
        return json.loads(self.checked(path).read_text(encoding="utf-8"))

    def write(self, path, value, *, replace=False):
        return self.io.write_json(self.root, path, value, replace=replace)

    def raw(self, path, data):
        path = self.checked(path)
        self.checked(path.parent).mkdir(parents=True, exist_ok=True)
        with path.open("xb") as stream:
            stream.write(data)
            stream.flush()
            os.fsync(stream.fileno())
        return record(path)

    def run(self, name):
        require(isinstance(name, str) and RUN_NAME.fullmatch(name), "invalid run identifier")
        return self.checked(self.base / "runs" / name)

    def current(self):
        path = self.base / "current.json"
        return self.read(path)["run"] if path.exists() else None

    @contextmanager
    def command_lock(self):
        path = self.checked(self.base / "command.lock")
        self.checked(path.parent).mkdir(parents=True, exist_ok=True)
        with path.open("x", encoding="ascii") as stream:
            stream.write(json.dumps(dict(pid=os.getpid(), time=now())))
        try:
            yield
        finally:
            require(self.read(path)["pid"] == os.getpid(), "command lock owner changed")
            self.checked(path).unlink()


def owner_state(store, path, *, clock=None):
    closed = path / "closed.json"
    if closed.exists():
        return dict(state="CLOSED", receipt=store.read(closed))
    if not (path / "config.json").exists():
        return dict(state="NOT_STARTED")
    if not (path / "state.json").exists():
        return dict(state="STARTING")
    state, config = store.read(path / "state.json"), store.read(path / "config.json")
    clock = time.time() if clock is None else clock
    age = clock - dt.datetime.fromisoformat(state["time"]).timestamp()
    valid = (config.get("root") == str(store.root) and config.get("out") == str(path) and
             0 <= age < 10 and state.get("worker_alive") is True and
             state.get("session") == config.get("id") and not state.get("forced_termination"))
    return dict(state="LIVE" if valid else "UNCERTAIN", heartbeat_age_seconds=round(age, 3),
                remaining_seconds=max(0, round(config["seconds"] - state["elapsed_seconds"])),
                worker_pid=state.get("worker_pid"))


def status(store, run=None, cell="s01", *, clock=None):
    owner_clock = clock
    clock = time.time() if clock is None else clock
    run = run or store.current()
    if run is None:
        return dict(result="NO_SESSION", next_action="p34 doctor, then p34 start")
    out = store.run(run)
    network = owner_state(store, out / "runtime/network", clock=owner_clock)
    live = out / "live-network.json"
    if live.exists():
        value = store.read(live)
        remaining = dt.datetime.fromisoformat(value["expires"]).timestamp() - clock
        network.update(expires=value["expires"], remaining_service_seconds=max(0, int(remaining)))
        if remaining <= 0:
            network["service"] = "EXPIRED"
        elif network["state"] == "LIVE":
            network["service"] = "VERIFIED"
    worker = owner_state(store, out / "runtime" / cell, clock=owner_clock)
    cell_path = out / "cells" / cell
    progress = store.read(cell_path / "status.json") if (cell_path / "status.json").exists() else {}
    result = progress.get("result", "PREPARING" if network["state"] == "LIVE" else "NOT_READY")
    ready_states = ("PREPARING", "NOT_READY", "APP_LAUNCHED_CONNECT_AND_DOWNLOAD", "READY_FOR_32K_PREFIX_START",
                    "READY_FOR_FULL_INSTALL_START")
    if worker["state"] != "LIVE" and result in ready_states:
        result = "CELL_CLOSED" if worker["state"] == "CLOSED" else "NOT_READY"
    health_path = cell_path / "health-live.json"
    launch_path = cell_path / "launch.json"
    if worker["state"] == "LIVE" and health_path.exists() and launch_path.exists():
        value = store.read(health_path)
        age = (time.time() if owner_clock is None else clock) - dt.datetime.fromisoformat(value["observed"]).timestamp()
        health = value["health"]
        query_path = cell_path / "queries/result.json"
        query = store.read(query_path) if query_path.exists() else {}
        capture_id = query.get("captureId") or query.get("query", {}).get("captureId")
        if capture_id and health.get("captureId") != capture_id:
            result = "CAPTURE_CHANGED"
        elif health.get("upgradeStarts", 0):
            # A stale terminal observation cannot make the old Start button safe again.
            result = "TRANSFER_ACTIVE" if health["upgradeStarts"] > health["upgradeEnds"] else "FINALIZING"
        elif result in ("READY_FOR_32K_PREFIX_START", "READY_FOR_FULL_INSTALL_START") and not (
                0 <= age < 15 and health.get("healthy") is True and health.get("lost") == 0 and health.get("error") is None):
            result = "NOT_READY"
    elif worker["state"] == "LIVE" and result in ("READY_FOR_32K_PREFIX_START", "READY_FOR_FULL_INSTALL_START"):
        result = "NOT_READY"
    if launch_path.exists() and result in ready_states:
        launch = store.read(launch_path)
        launched = dt.datetime.fromisoformat(launch.get("observation_resumed_at", launch["time"])).timestamp()
        worker["remaining_app_start_seconds"] = max(0, int(launched + APP_START_SECONDS - clock))
        if worker["remaining_app_start_seconds"] == 0:
            result = "APP_START_WINDOW_ENDED"
    if network.get("service") == "EXPIRED" and worker["state"] != "LIVE" and result in (*ready_states, "CELL_CLOSED"):
        result = "SESSION_EXPIRED"
    analysis_path = out / "analysis/latest.json"
    analysis = store.read(analysis_path) if analysis_path.exists() else None
    if analysis and analysis.get("cell") != cell:
        analysis = None
    if analysis and analysis.get("result") == "PREFIX_RECONCILED" and worker["state"] == "CLOSED":
        result = "PREFIX_RECONCILED"
    if analysis and analysis.get("result") == "FULL_INSTALL_VERIFIED" and worker["state"] == "CLOSED":
        result = "FULL_INSTALL_VERIFIED"
    return dict(run=run, cell=cell, result=result, network=network, worker=worker, progress=progress, analysis=analysis,
                next_action=("p34 start: safely refresh the service/configuration" if result == "SESSION_EXPIRED" else
                             "use the next planned --cell; do not repeat this completed prefix" if result == "PREFIX_RECONCILED" else
                             "keep the App in the foreground; do not start another transfer" if result in ("TRANSFER_ACTIVE", "FINALIZING") else
                             "connect/download in the App; do not start BLE yet" if result == "APP_LAUNCHED_CONNECT_AND_DOWNLOAD" else
                             "start the 32 KiB prefix in the foreground App" if result == "READY_FOR_32K_PREFIX_START" else
                             "start the bound full upgrade once in the foreground App" if result == "READY_FOR_FULL_INSTALL_START" else
                             "retain the verified target; close owners and never repeat this completed OTA" if result == "FULL_INSTALL_VERIFIED" else
                             "inspect the original result; do not blindly repeat a transfer"))


def can_stop(store, out, cell):
    worker = owner_state(store, out / "runtime" / cell)
    if worker["state"] in ("NOT_STARTED", "CLOSED"):
        return
    require(worker["state"] == "LIVE", "cell ownership is uncertain; inspect before stopping")
    health_path = out / "cells" / cell / "health-live.json"
    require(health_path.exists(), "current App health missing; collect before stop")
    value = store.read(health_path)
    require(0 <= time.time() - dt.datetime.fromisoformat(value["observed"]).timestamp() < 15,
            "App health is stale; collect before stop")
    health = value["health"]
    require(health["healthy"] and health["lost"] == 0 and health["error"] is None and
            health["upgradeStarts"] == health["upgradeEnds"],
            "transfer is active/uncertain: cancel in the App and await ABORT before stopping")


def wait_until(check, *, seconds, clock=time.monotonic, sleep=time.sleep):
    deadline = clock() + seconds
    while True:
        value = check()
        if value:
            return value
        require(clock() < deadline, "bounded wait expired; inspect existing workers, do not relaunch")
        sleep(min(.25, max(0, deadline - clock())))


def stop(store, run, cell):
    with store.command_lock():
        return _stop(store, run, cell)


def _stop(store, run, cell):
    out = store.run(run)
    can_stop(store, out, cell)
    for name in CELLS:
        require(name == cell or owner_state(store, out / "runtime" / name)["state"] in ("NOT_STARTED", "CLOSED"),
                "another cell owns this network")
    if owner_state(store, out / "runtime" / cell)["state"] == "LIVE":
        path = out / "cells" / cell / "stop.json"
        if not path.exists():
            store.write(path, dict(time=now(), reason="p34 stop: idle/terminal App verified"))
        wait_until(lambda: (out / "runtime" / cell / "closed.json").exists(), seconds=90)
    network = owner_state(store, out / "runtime/network")
    require(network["state"] != "UNCERTAIN", "network owner uncertain; preserve its state")
    if network["state"] == "LIVE":
        path = out / "network-stop.json"
        if not path.exists():
            store.write(path, dict(time=now(), reason="p34 stop: cells closed"))
        wait_until(lambda: (out / "runtime/network/closed.json").exists(), seconds=15)
    return status(store, run, cell)


def backend(store, profile_path, group="screen"):
    profile_path = store.checked(profile_path)
    profile = store.read(profile_path)
    require(profile.get("schema") == 1, "unsupported local session profile")
    bootstrap = store.checked(store.root / profile["bootstrap"]["path"])
    require(record(bootstrap)["sha256"] == profile["bootstrap"]["sha256"], "legacy primitive source changed; revalidate the profile")
    module = load_module("p34_session_backend", store.root / "Tools/ota/p34_session_backend.py")
    return module.Backend(store, profile_path, profile, group)


def verify_tests(store):
    path = store.base / "tests/latest.json"
    require(path.exists(), "run p34 test before starting a changed tool")
    report = store.read(path)
    require(report["passed"] and all(record(item["path"]) == item for item in report["sources"]),
            "session tool changed since self-test; run p34 test")
    return record(path)


def paired_predecessor(store, descriptor, *, group="n03-a"):
    require(group in ("n03-a", "n03-b"), "undeclared paired predecessor")
    require(isinstance(descriptor, dict) and set(descriptor) == {"run", "cell", "plan", "report", "readback"},
            "B requires an explicit reconciled A predecessor")
    out, cell = store.run(descriptor["run"]), descriptor["cell"]
    require(cell in CELLS and Path(descriptor["plan"]["path"]) == out / "plan.json",
            "predecessor plan/cell is not in its declared run")
    for name in ("plan", "report", "readback"):
        item = descriptor[name]
        require(record(store.checked(item["path"])) == item, "predecessor evidence changed: " + name)
    plan, report, readback = (store.read(descriptor[key]["path"]) for key in ("plan", "report", "readback"))
    require(plan.get("group") == group and plan["receiver_version"] == (30214 if group == "n03-a" else 30215) and
            report["cell"] == cell and report["result"] == "APP_PREFIX_VERIFIED" and
            report["inputs"]["plan"] == descriptor["plan"] and report["retained_verified"] is True and
            report["mcu_staging_readback"] == "VERIFIED" and report["profile"]["clean_counters"] is True and
            report["prefix"]["sentTotalBytes"] == report["prefix"]["prefixBytes"] == plan["prefix_bytes"] and
            readback["result"] == "PREFIX_READBACK_VERIFIED" and
            readback["journal"] == report["journal"] and readback["prefix"] == report["staging_prefix"],
            "predecessor is not a clean, reconciled N03 A arm")
    require(all(owner_state(store, out / "runtime" / name)["state"] in ("NOT_STARTED", "CLOSED") for name in CELLS) and
            owner_state(store, out / "runtime" / cell)["state"] == "CLOSED" and
            owner_state(store, out / "runtime/network")["state"] == "CLOSED", "predecessor owners must be closed")
    closure = store.read(report["mcu_closure"]["path"])
    require(closure == readback["closure"] and closure["retained_verified"] is True and "cleanup_error" not in closure,
            "predecessor closure differs from its original readback")
    originals = [report["inputs"][key] for key in ("config", "snapshot")]
    originals += [report["mcu_closure"], report["journal"], report["staging_prefix"]]
    originals += [closure[phase][image] for phase in ("initial_identity", "final_identity") for image in ("app", "boot")]
    for item in originals:
        require(record(store.checked(item["path"])) == item, "predecessor original bytes changed")
    return dict(out=out, cell=cell, plan=plan, report=report, readback=readback, descriptor=descriptor)


def full_predecessor(store, descriptor):
    """Advance the reconciled B, not A or the already-used R installation."""
    previous = paired_predecessor(store, descriptor, group="n03-b")
    plan = previous["plan"]
    require(record(store.checked(plan["profile"]["path"])) == plan["profile"], "B profile changed")
    profile = store.read(plan["profile"]["path"])
    arm_a = paired_predecessor(store, profile.get("predecessor"))
    installed = installed_predecessor(store, profile.get("installation"), arm_a)
    require(plan["served"] == arm_a["plan"]["served"] and
            plan["bindings"] == installed["plan"]["target_bindings"], "B does not retain the measured N03 receiver/T")
    return previous


def installed_predecessor(store, descriptor, previous, *, group="n03-install"):
    """Consume the completed normal-OTA bridge without relabelling it as arm A."""
    require(group in FULL_VERSIONS, "undeclared completed full predecessor")
    receiver, target = FULL_VERSIONS[group]
    require(isinstance(descriptor, dict) and set(descriptor) == {"run", "cell", "plan", "report"},
            "B requires the explicit completed R installation")
    out, cell = store.run(descriptor["run"]), descriptor["cell"]
    require(cell == INSTALL_CELL and Path(descriptor["plan"]["path"]) == out / "plan.json",
            "installation plan/cell is outside the declared run")
    for key in ("plan", "report"):
        require(record(store.checked(descriptor[key]["path"])) == descriptor[key], "installation evidence changed")
    plan, report = (store.read(descriptor[key]["path"]) for key in ("plan", "report"))
    require(plan["group"] == group and plan["receiver_version"] == receiver and plan["target_version"] == target and
            plan["predecessor"] == previous["descriptor"] and plan["prefix_bytes"] == 0 and
            plan["no_end"] is False and plan["no_firmware_install"] is False and
            report["result"] == "FULL_INSTALL_VERIFIED" and report["cell"] == cell and
            report["inputs"]["plan"] == descriptor["plan"] and report["summary"]["outcome"] == "completed" and
            report["start_inputs_verified_before"] is True and isinstance(report.get("flash_admission"), dict),
            "R installation is not fully reconciled")
    require(all(owner_state(store, out / "runtime" / name)["state"] in ("NOT_STARTED", "CLOSED") for name in CELLS) and
            owner_state(store, out / "runtime" / cell)["state"] == "CLOSED" and
            owner_state(store, out / "runtime/network")["state"] == "CLOSED", "installation owners must be closed")
    originals = [*report["inputs"].values(), report["flash_admission"]]
    admission = store.read(report["flash_admission"]["path"])
    require(admission["result"] == "BOUND_RECEIVER_ADMITTED" and admission["receiver_version"] == target and
            admission["map"] == plan["target_bindings"]["profile"]["map"] and
            admission["image_sha256"] == plan["target_bindings"]["profile"]["image"]["sha256"],
            "installation admission belongs to a different receiver")
    gate = store.read(admission["flash_gate"]["path"])
    require(gate["disabled"] == 0 and gate["jedec"] == 0xEF4018, "installation Flash gate failed")
    originals.extend((admission["map"], admission["flash_gate"]))
    for name, bindings in (("before", plan["bindings"]), ("after", plan["target_bindings"])):
        item = report[name]
        require(record(store.checked(item["path"])) == item, "installation closure changed")
        closure = store.read(item["path"])
        require(closure.get("retained_verified") is True and closure.get("reader_closed") is True and
                "cleanup_error" not in closure, "installation native closure is unresolved")
        for phase in ("initial_identity", "final_identity"):
            for image, sha in (("app", bindings["profile"]["image"]["sha256"]),
                               ("boot", bindings["whole_boot"]["sha256"])):
                value = closure[phase][image]
                require(value["sha256"] == sha, "installation App/Boot identity differs")
                originals.append(value)
        state = closure["final_state"]
        require(state["bcb_state"] == 4 and state["confirm_done"] == state["state_snapped"] == state["sd_ready"] == 1,
                "installation is not idle/CONFIRMED with SD ready")
        originals.extend(state[key] for key in ("session_raw", "profile_raw"))
    for item in originals:
        require(record(store.checked(item["path"])) == item, "installation original bytes changed")
    return dict(out=out, cell=cell, plan=plan, report=report, descriptor=descriptor)


def completed_full_predecessor(store, descriptor, *, group="n03-full"):
    """Follow only the declared completed chain, never a prefix or replay."""
    require(group in MEASURED_FULL_GROUPS, "undeclared measured full predecessor")
    require(isinstance(descriptor, dict) and set(descriptor) == {"run", "cell", "plan", "report"},
            "window-8 requires the explicit completed U descriptor")
    out = store.run(descriptor["run"])
    require(descriptor["cell"] == INSTALL_CELL and Path(descriptor["plan"]["path"]) == out / "plan.json" and
            record(store.checked(descriptor["plan"]["path"])) == descriptor["plan"],
            "window-8 predecessor plan changed or belongs to another run")
    plan = store.read(descriptor["plan"]["path"])
    require(plan.get("group") == group and isinstance(plan.get("predecessor"), dict),
            "window-8 requires the completed U full plan, not a prefix or R installation")
    prior = (full_predecessor(store, plan["predecessor"]) if group == "n03-full" else
             completed_full_predecessor(store, plan["predecessor"], group=PREDECESSOR_GROUPS[group]))
    previous = installed_predecessor(store, descriptor, prior, group=group)
    if group == BOOT_COPY_GROUP:
        patch_assets_api(store, group).verify_transition(prior["plan"]["target_bindings"], plan["bindings"])
    elif group != "n03-full":
        require(plan["bindings"] == prior["plan"]["target_bindings"], "full successor does not retain its verified receiver")
    report = previous["report"]
    count = (plan["served"]["bytes"] + 127) // 128
    transfer = report["full_metrics"]["transfer"]
    require(report["n03_receive_measurement"] is True and "COMPLETE_DATA" in report["initial_state_evidence"]["source"] and
            transfer["segmentsUnique"] == transfer["segmentSendTotal"] == count and transfer["retransmitFrames"] == 0 and
            transfer["durable"]["finalOff"] == plan["served"]["bytes"] and
            report["summary"]["input"]["targetVersionCode"] == FULL_VERSIONS[group][1],
            "window-8 predecessor lacks the complete U receive" if group == "n03-full" else
            "repeat predecessor lacks the complete V receive")
    return previous


def current_full_descriptor(store, run):
    out = store.run(run)
    latest = store.read(out / "analysis/latest.json")
    require(latest["result"] == "FULL_INSTALL_VERIFIED", "current full installation is not reconciled")
    return dict(run=run, cell=latest["cell"], plan=record(out / "plan.json"), report=latest["report"])


def failed_full_prestart(store, run, profile_path):
    """Recognize the unrecorded full-store failure, not a retryable OTA result."""
    out = store.run(run)
    cell = out / "cells" / INSTALL_CELL
    plan = store.read(out / "plan.json")
    require(plan.get("group") == "n03-full" and plan["profile"] == record(store.checked(profile_path)) and
            (plan["receiver_version"], plan["target_version"], plan["prefix_bytes"]) == (30215, 30217, 0),
            "prestart recovery requires the original R-to-U full plan")
    previous = full_predecessor(store, plan["predecessor"])
    require(plan["bindings"] == previous["plan"]["bindings"], "prestart receiver differs from B")
    for name in (*CELLS, "network"):
        owner = owner_state(store, out / "runtime" / name)
        require(owner["state"] in ("NOT_STARTED", "CLOSED") and
                not owner.get("receipt", {}).get("forced_termination"), "prestart owner closure unresolved")
    require(all(owner_state(store, out / "runtime" / name)["state"] == "CLOSED"
                for name in (INSTALL_CELL, "network")), "full owners must have closed")
    result = store.read(cell / "result.json")
    require(result.get("result") == "FULL_INSTALL_INCOMPLETE" and
            result.get("error") == "RuntimeError: full installation snapshot/input mismatch" and
            result.get("n03_receive_measurement") is False and "summary" not in result and "after" not in result and
            not (cell / "queries/result.json").exists(), "admitted/uncertain full transfer cannot be replayed")
    prestart = store.read(out / "prestart-phone/result.json")
    require(prestart.get("capture_directories") == 8 and prestart.get("stable_terminal") is True and
            prestart.get("pid") == previous["report"]["summary"]["pid"], "failure was not the bound full capture store")
    config = record(cell / "runtime-config.json")
    require(store.read(cell / "provision.json")["config"] == config, "failed configuration/provision changed")
    launch = store.read(cell / "launch.json")
    require(type(launch.get("pid")) is int and launch["pid"] > 0 and launch["pid"] != prestart["pid"],
            "unrecorded launch PID is not distinct from B")
    snapshot = record(cell / "finished/snapshot.jsonl")
    require((snapshot["bytes"], snapshot["sha256"]) ==
            tuple(previous["report"]["inputs"]["snapshot"][key] for key in ("bytes", "sha256")),
            "failed snapshot is not the preserved B original")
    before = store.read(result["before"]["path"])
    require(record(store.checked(result["before"]["path"])) == result["before"] and
            before.get("reader_closed") is True and before.get("retained_verified") is True and
            "cleanup_error" not in before, "prestart native closure is incomplete")
    trace = store.read(result["native_trace"]["path"])
    require(record(store.checked(result["native_trace"]["path"])) == result["native_trace"] and
            trace.get("reader_closed") is True, "prestart trace closure unresolved")
    inputs = {name: record(path) for name, path in dict(plan=out / "plan.json", result=cell / "result.json",
        prestart=out / "prestart-phone/result.json", launch=cell / "launch.json", provision=cell / "provision.json").items()}
    inputs.update(config=config, snapshot=snapshot, before=result["before"], native_trace=result["native_trace"])
    return dict(run=run, cell=INSTALL_CELL, inputs=inputs, previous=previous, before=before, pid=launch["pid"])


def prestart_recovery(store, path, profile_path):
    """Recheck the write-once recovery receipt without contacting a device."""
    path = store.checked(path)
    pointer = store.read(path)
    out = store.run(pointer["run"])
    require(path == out / "prestart-recovery.json", "recovery pointer is outside its failed run")
    report = pointer["report"]
    require(record(store.checked(report["path"])) == report, "prestart recovery report changed")
    value = store.read(report["path"])
    failure = failed_full_prestart(store, out.name, profile_path)
    require(value.get("result") == "PRESTART_RECOVERED" and value["failed_inputs"] == failure["inputs"] and
            value.get("usb_closed") is True and value.get("no_transfer") is True,
            "prestart recovery is incomplete or belongs to another failure")
    for key in ("checkpoint", "retired"):
        require(record(store.checked(value[key]["path"])) == value[key], "recovery evidence changed: " + key)
    retired = store.read(value["retired"]["path"])
    require(retired.get("process_absent") is True and retired.get("configuration_absent") is True and
            retired.get("config") == failure["inputs"]["config"] and retired.get("pid") in (None, failure["pid"]),
            "recovery did not retire the exact failed process/configuration")
    return dict(pointer=record(path), report=report, value=value, failure=failure)


def recover_prestart(store, run):
    with store.command_lock():
        require(run == store.current(), "recover only the current failed full run")
        tests = verify_tests(store)
        old = store.run(run)
        profile = Path(store.read(old / "plan.json")["profile"]["path"])
        pointer = old / "prestart-recovery.json"
        if pointer.exists():
            return prestart_recovery(store, pointer, profile)["value"]
        failure = failed_full_prestart(store, run, profile)
        require(not list((old / "recoveries").glob("*/retire-intent.json")),
                "prior retirement may have acted; reconcile it rather than repeat recovery")
        impl = backend(store, profile, "n03-full")
        out = store.checked(old / "recoveries" / str(time.time_ns()))
        ctx = impl.context(out)
        impl.preflight(ctx, out)
        for name in ("intent.json", "result.json", "checkpoint.json", "retire-intent.json", "retired.json", "phone", "mcu"):
            store.checked(out / name)
        store.checked(pointer)
        store.write(out / "intent.json", dict(time=now(), failed_inputs=failure["inputs"], tests=tests,
                                            sources=ctx.sources(), no_transfer=True))
        value = impl.recover_prestart(ctx, out, failure)
        if value["result"] == "PRESTART_RECOVERED":
            store.write(pointer, dict(run=run, report=record(out / "result.json")))
            value["recovery_pointer"] = str(pointer)
        return value


def retirement_api(store):
    return load_module("p34_retirement_recovery", store.root / "Tools/ota/p34_retirement_recovery.py")


def start(store, profile_path, cell, group="screen", recovery_path=None, retirement_path=None):
    with store.command_lock():
        test_report = verify_tests(store)
        require(group not in INSTALL_GROUPS or cell == INSTALL_CELL,
                "full installation uses only s04 (921600/window %d)" % cells_for(group)[INSTALL_CELL][1])
        current = store.current()
        retirement = None
        if retirement_path:
            require(group == SPEED32_GROUP and not recovery_path, "retirement recovery is window-32 only")
            retirement = retirement_api(store).load_recovery(store, retirement_path, profile_path)
            require(current == retirement["failure"]["run"], "retirement recovery already consumed or wrong current owner")
        reuse = None
        predecessor = None
        recovery = None
        require(not recovery_path or group == "n03-full" and current,
                "prestart recovery only advances the current full group")
        if current:
            state = status(store, current, cell)
            out = store.run(current)
            old_plan = store.read(out / "plan.json") if (out / "plan.json").exists() else {}
            if retirement:
                predecessor = retirement["failure"]["previous"]
            elif old_plan.get("group") in (*SUCCESSORS, *N04_LINEAGE_GROUPS):
                expected_next = {name for name, prior in PREDECESSOR_GROUPS.items() if prior == old_plan["group"]}
                if group not in expected_next:
                    return status(store, current, INSTALL_CELL)
                predecessor = store.read(profile_path).get("predecessor")
                predecessor = completed_full_predecessor(store, predecessor, group=old_plan["group"])
                require(predecessor["out"] == out, "N04 must follow its actual completed owner")
            if old_plan.get("group") == "n03-window8":
                if group != "n03-window8-repeat":
                    return status(store, current, INSTALL_CELL)
                predecessor = completed_full_predecessor(store, store.read(profile_path).get("predecessor"), group="n03-window8")
                require(predecessor["out"] == out, "repeat must follow its actual completed V owner")
            if old_plan.get("group") == "n03-full":
                if group == "n03-window8":
                    predecessor = completed_full_predecessor(store, store.read(profile_path).get("predecessor"))
                    require(predecessor["out"] == out, "window-8 must follow its actual completed U owner")
                elif not recovery_path:
                    return status(store, current, INSTALL_CELL)
                else:
                    recovery = prestart_recovery(store, recovery_path, profile_path)
                    if old_plan.get("prestart_recovery") == recovery["pointer"]:
                        return status(store, current, INSTALL_CELL)
                    require(recovery["failure"]["run"] == current, "recovery does not bind the current failed run")
            else:
                require(not recovery_path, "prestart recovery requires a failed full owner")
            if old_plan.get("group") == "n03-install":
                if group != "n03-b":
                    return status(store, current, INSTALL_CELL)
                predecessor = paired_predecessor(store, store.read(profile_path).get("predecessor"))
                installed = installed_predecessor(store, store.read(profile_path).get("installation"), predecessor)
                require(installed["out"] == out, "B must follow its actual installation owner")
            existing = owner_state(store, out / "runtime" / cell)
            if existing["state"] == "LIVE":
                return state
            health_path = out / "cells" / cell / "health-live.json"
            if recovery is None and group not in FULL_SUCCESSOR_GROUPS and existing["state"] == "CLOSED" and health_path.exists() and store.read(health_path)["health"].get("upgradeStarts", 0):
                plan_path = out / "plan.json"
                if group != "n03-b" or not plan_path.exists() or store.read(plan_path).get("group") == group:
                    return state  # A host error never grants a replay of an invoked cell.
                predecessor = paired_predecessor(store, store.read(profile_path).get("predecessor"))
                require(predecessor["out"] == out and predecessor["cell"] == cell,
                        "B must follow the declared A run and identical cell parameters")
            for name in CELLS:
                require(owner_state(store, out / "runtime" / name)["state"] in ("NOT_STARTED", "CLOSED"),
                        "another/uncertain cell owns the session; inspect status")
            require(state["network"]["state"] not in ("UNCERTAIN", "STARTING"), "network start/closure unresolved")
            if state["network"]["state"] == "LIVE":
                if existing["state"] == "NOT_STARTED" and state["network"].get("remaining_service_seconds", 0) > 3500:
                    require(store.read(out / "plan.json").get("group", "screen") == group,
                            "an existing session of another comparison group cannot be reused")
                    reuse = current
                else:
                    _stop(store, current, cell)
        if group == "n03-b":
            predecessor = predecessor or paired_predecessor(store, store.read(profile_path).get("predecessor"))
            require(predecessor["cell"] == cell, "B must use the same cell parameters as A")
        if group == "n03-install":
            predecessor = paired_predecessor(store, store.read(profile_path).get("predecessor"))
            require(current == predecessor["out"].name, "R installation must follow the completed A owner")
        if group == "n03-full":
            predecessor = full_predecessor(store, store.read(profile_path).get("predecessor"))
            require(current == predecessor["out"].name or recovery is not None and
                    recovery["failure"]["previous"]["descriptor"] == predecessor["descriptor"],
                    "full N03 validation must follow its completed B owner")
        if group in FULL_SUCCESSOR_GROUPS:
            predecessor = predecessor or completed_full_predecessor(store, store.read(profile_path).get("predecessor"),
                group=PREDECESSOR_GROUPS[group])
            require(current == predecessor["out"].name or retirement is not None,
                    "window-8 must follow the verified predecessor owner")
        impl = backend(store, profile_path, group)
        impl.recovery = recovery
        impl.retirement_recovery = retirement
        if reuse:
            out = store.run(reuse)
            ctx = impl.context(out)
            impl.validate(ctx, out)
        else:
            run = dt.datetime.now(dt.timezone.utc).strftime("%Y%m%dT%H%M%S") + "-" + str(time.time_ns() % 100000)
            out = store.run(run)
            ctx = impl.context(out)
            impl.preflight(ctx, out)
            phone = impl.inspect(ctx, out / "prestart-phone")
            require(phone["result"] == "APP_INSPECTED", "phone inspection unavailable; no new service started")
            impl.prepare(ctx, out, phone, test_report)
            store.write(store.base / "current.json", dict(run=run, created=now()), replace=True)
            ctx.supervisor.owned.launch(out / "runtime/network", store.root / "Tools/ota/p34_session.py",
                ["--root", str(store.root), "--run", run, "_network"], NETWORK_SUPERVISOR_SECONDS)
            def network_ready():
                require(not (out / "runtime/network/closed.json").exists(), "service setup failed; original result preserved")
                return (out / "live-network.json").exists()
            wait_until(network_ready, seconds=NETWORK_READY_WAIT_SECONDS)
        run = out.name
        impl.network_ready(ctx, out)
        cell_out = out / "cells" / cell
        require(not cell_out.exists(), "cell already attempted in this session; collect/reconcile before a new run")
        store.write(cell_out / "intent.json", dict(time=now(), cell=cell, plan=record(out / "plan.json")))
        ctx.supervisor.owned.launch(out / "runtime" / cell, store.root / "Tools/ota/p34_session.py",
            ["--root", str(store.root), "--run", run, "--cell", cell, "_cell"], CELL_SECONDS)
        return status(store, run, cell)


def identity(store, profile_path, group):
    """Read-only receiver checkpoint: identity, idle/CONFIRMED and retained rate only.

    Connects the J-Link link and reads the complete App/Boot image, one idle sample and
    the controller status; it never resets, halts, flashes or changes the rate, so it can
    verify that a manual SD install left the expected receiver running.
    """
    verify_tests(store)
    impl = backend(store, profile_path, group)
    out = store.checked(store.base / "identity" / str(time.time_ns()))
    store.checked(out).mkdir(parents=True)
    ctx = impl.context(out)
    result = dict(result="IDENTITY_FAILED", group=group, receiver_version=impl.receiver_version,
                  target_version=impl.target_version, expected_image_sha=ctx.receiver_image_sha,
                  evidence=str(out), no_reset=True, no_halt=True, no_flash=True, no_tuning=True, no_transfer=True)
    try:
        os.environ.update(ctx.environment())
        lock = ctx.load("p34_identity_lock", store.root / "Tools/ota/repeat_cycle.py")
        helper = ctx.load("p34_identity_mcu", ctx.HERE / "prefix_mcu.py")
        with lock.device_lock():
            mcu = helper.Mcu(ctx, out / "mcu")
            try:
                mcu.open()
                result.update(initial=mcu.result["initial_identity"], controller=mcu.result["initial_status"],
                              state=mcu.sample("identity"))
            finally:
                result["closure"] = mcu.close(restore=False)
        result["result"] = "IDENTITY_VERIFIED"
    except Exception as error:
        result.update(error=type(error).__name__, detail=str(error))
    store.write(out / "result.json", result)
    return result


def prune(store, profile_path, names):
    """Free named App capture directories; the backend re-derives eligibility itself."""
    impl = backend(store, profile_path)
    out = store.checked(store.base / "prune" / str(time.time_ns()))
    store.checked(out).mkdir(parents=True)
    ctx = impl.context(out)
    return impl.prune(ctx, out, names)


def completed_capture_target(store, run):
    """Select only the previous completed capture, never a hand-copied suffix."""
    current = store.current()
    require(current and run != current, "cannot prune the current completed recording")
    plan = store.read(store.run(current) / "plan.json")
    group = plan.get("group")
    require(group in ("n03-window8", "n03-window8-repeat", "n04-bootstrap", "n04-measure", NATIVE_DIAGNOSTIC_GROUP, SPEED16_GROUP,
                      SPEED32_GROUP, "patch32-bootstrap", "patch32-pressure", "receive-bootstrap"),
            "completed cleanup group is not declared")
    descriptor = plan.get("predecessor")
    require(isinstance(descriptor, dict) and run == descriptor.get("run") and descriptor.get("cell") == INSTALL_CELL,
            "completed cleanup is limited to the original immediate predecessor")
    protected = completed_full_predecessor(store, current_full_descriptor(store, current), group=group)
    require(protected["plan"]["predecessor"] == descriptor, "cleanup predecessor changed during verification")
    selected = completed_full_predecessor(store, descriptor, group=PREDECESSOR_GROUPS[group])
    query = store.read(selected["report"]["inputs"]["query"]["path"])
    capture = selected["report"]["summary"]["captureId"]
    require(isinstance(capture, str) and re.fullmatch(r"\d+-[a-f0-9]+", capture) and
            query["remote"] == "files/p34-observations/" + capture and
            query["pid"] == selected["report"]["summary"]["pid"] and
            query["config"] == selected["report"]["inputs"]["config"], "original U recording binding differs")
    return dict(selected=selected, protected=protected, capture=capture, remote=query["remote"])


def prune_completed(store, run, *, apply=False):
    with store.command_lock():
        tests = verify_tests(store)
        selection = completed_capture_target(store, run)
        base = store.checked(store.base / "completed-prune")
        for path in base.glob("*/intent.json"):
            intent = store.read(path)
            if intent.get("apply") and intent.get("selected") == selection["selected"]["descriptor"]:
                result = path.parent / "result.json"
                require(result.exists() and store.read(result).get("result") == "COMPLETED_CAPTURE_PRUNED",
                        "prior completed cleanup may have acted; reconcile rather than repeat")
                value = store.read(result)
                require(value.get("selected") == selection["selected"]["descriptor"] and
                        value.get("protected") == selection["protected"]["descriptor"] and
                        value.get("removed") == [selection["capture"]] and value.get("remote") == selection["remote"] and
                        value.get("usb_closed") is True and value.get("phone_mutations") == 1 and
                        all(record(store.checked(item["path"])) == item for item in value["archived"].values()),
                        "prior completed cleanup evidence changed")
                return dict(value, reused=True, phone_mutations_this_call=0)
        previous = selection["protected"]
        group = previous["plan"]["group"]
        impl = backend(store, Path(previous["plan"]["profile"]["path"]), group)
        out = store.checked(base / str(time.time_ns()))
        ctx = impl.context(out)
        impl.preflight(ctx, out)
        return impl.prune_completed(ctx, out, selection, apply=apply, tests=tests)


def prepare_full(store):
    with store.command_lock():
        run = store.current()
        require(run, "completed N03 B required before full preparation")
        out = store.run(run)
        latest = store.read(out / "analysis/latest.json")
        require(latest["result"] == "PREFIX_RECONCILED", "current receiver measurement is not reconciled")
        descriptor = dict(run=run, cell=latest["cell"], plan=record(out / "plan.json"),
                          report=latest["report"], readback=latest["readback"])
        previous = full_predecessor(store, descriptor)
        source_profile = Path(previous["plan"]["profile"]["path"])
        impl = backend(store, source_profile, "n03-b")
        ctx = impl.context(store.checked(store.base / "n03-full"))
        assets = load_module("p34_full_assets", store.root / "Tools/ota/p34_full_assets.py")
        result = assets.prepare(ctx)
        path = store.checked(store.base / "profile-n03-full.json")
        value = dict(schema=1, name="n03-full-after-" + run, bootstrap=impl.profile["bootstrap"],
            owned_configs=[{key: previous["report"]["inputs"]["config"][key] for key in ("path", "sha256")}],
            predecessor=descriptor, full_assets=result["manifest"],
            scope="One zero-start 921600/window-4 full OTA received by N03; retain U/N03 and unchanged Boot. Never install T or replay A/R/B.")
        if path.exists():
            require(store.read(path) == value, "preserve existing full profile")
        else:
            store.write(path, value)
        return dict(result, profile=record(path))


def prepare_window8(store):
    with store.command_lock():
        run = store.current()
        require(run, "completed U required before window-8 preparation")
        descriptor = current_full_descriptor(store, run)
        previous = completed_full_predecessor(store, descriptor)
        source_profile = Path(previous["plan"]["profile"]["path"])
        impl = backend(store, source_profile, "n03-full")
        ctx = impl.installed_context(store.checked(store.base / "n03-window8"))
        ctx.u_assets = ctx.full_assets
        assets = load_module("p34_window8_assets", store.root / "Tools/ota/p34_window8_assets.py")
        result = assets.prepare(ctx)
        path = store.checked(store.base / "profile-n03-window8.json")
        value = dict(schema=1, name="n03-window8-after-" + run, bootstrap=impl.profile["bootstrap"], predecessor=descriptor,
            owned_configs=[{key: previous["report"]["inputs"]["config"][key] for key in ("path", "sha256")}],
            receiver_assets=record(store.root / assets.U_RELATIVE), window_assets=result["manifest"],
            scope="One zero-start 921600/window-8 full OTA from U to V; same N03 executable and unchanged Boot. No U replay.")
        if path.exists():
            require(store.read(path) == value, "preserve existing window-8 profile")
        else:
            store.write(path, value)
        return dict(result, profile=record(path))


def prepare_repeat(store):
    with store.command_lock():
        run = store.current()
        require(run, "completed V required before repeat preparation")
        descriptor = current_full_descriptor(store, run)
        previous = completed_full_predecessor(store, descriptor, group="n03-window8")
        impl = backend(store, Path(previous["plan"]["profile"]["path"]), "n03-window8")
        ctx = impl.installed_context(store.checked(store.base / "n03-window8-repeat"))
        ctx.previous_assets = ctx.full_assets
        assets = load_module("p34_successor_assets", store.root / "Tools/ota/p34_successor_assets.py")
        result = assets.prepare(ctx, SUCCESSORS["n03-window8-repeat"])
        path = store.checked(store.base / "profile-n03-window8-repeat.json")
        value = dict(schema=1, name="n03-window8-repeat-after-" + run, bootstrap=impl.profile["bootstrap"], predecessor=descriptor,
            owned_configs=[{key: previous["report"]["inputs"]["config"][key] for key in ("path", "sha256")}],
            receiver_assets=impl.profile["receiver_assets"], window_assets=impl.profile["window_assets"],
            successor_assets=result["manifest"],
            scope="One zero-start 921600/window-8 full repeat from V to W; same N03 executable/Boot. No V replay or W16 campaign.")
        if path.exists():
            require(store.read(path) == value, "preserve existing repeat profile")
        else:
            store.write(path, value)
        return dict(result, profile=record(path))


def prepare_install(store):
    """Prepare X/Y once; bind each execution profile only after its predecessor."""
    with store.command_lock():
        run = store.current()
        require(run, "completed W or X required before N04 preparation")
        group = store.read(store.run(run) / "plan.json").get("group")
        require(group in ("n03-window8-repeat", "n04-bootstrap"), "N04 only advances completed W then X")
        previous = completed_full_predecessor(store, current_full_descriptor(store, run), group=group)
        impl = backend(store, Path(previous["plan"]["profile"]["path"]), group)
        ctx = impl.installed_context(store.checked(store.base / "n04"))
        api = load_module("p34_install_assets", store.root / "Tools/ota/p34_install_assets.py")
        if group == "n03-window8-repeat":
            ctx.previous_assets = ctx.full_assets
            first = api.prepare(ctx, N04_GROUPS["n04-bootstrap"])
            ctx.previous_assets = api.load(ctx, N04_GROUPS["n04-bootstrap"])
            ctx.bindings = ctx.previous_assets["target_bindings"]
            ctx.receiver_version = N04_GROUPS["n04-measure"]["receiver"]
            second = api.prepare(ctx, N04_GROUPS["n04-measure"])
            manifests = {"n04-bootstrap": first["manifest"], "n04-measure": second["manifest"]}
            next_group = "n04-bootstrap"
        else:
            ctx.previous_assets = ctx.full_assets
            second = api.prepare(ctx, N04_GROUPS["n04-measure"])
            manifests = dict(impl.profile["n04_assets"])
            require(manifests["n04-measure"] == second["manifest"], "preserve the already prepared Y package")
            next_group = "n04-measure"
        path = store.checked(store.base / ("profile-" + next_group + ".json"))
        value = dict(impl.profile, name=next_group + "-after-" + run, predecessor=previous["descriptor"],
            owned_configs=[{key: previous["report"]["inputs"]["config"][key] for key in ("path", "sha256")}],
            n04_assets=manifests,
            scope="Finite N04 sequence W-to-X bootstrap, then X-to-Y installation measurement; retain new target/old Boot. "
                  "One zero-start 921600/window-8 full cell per predecessor. No replay, downgrade or automatic cleanup.")
        if path.exists():
            require(store.read(path) == value, "preserve existing N04 execution profile")
        else:
            store.write(path, value)
        return dict(result="N04_ASSETS_READY", group=next_group, assets=manifests, profile=record(path),
                    device_operations=0, not_installed=True)


def prepare_window16(store):
    """Prepare one Y-to-Z window-16 cell; never build, replay or clean a device."""
    with store.command_lock():
        run = store.current()
        require(run, "completed Y required before window-16 preparation")
        group = store.read(store.run(run) / "plan.json").get("group")
        require(group == "n04-measure", "window-16 preparation requires the completed Y measurement")
        previous = completed_full_predecessor(store, current_full_descriptor(store, run), group=group)
        require(previous["report"].get("n04_install_measurement") is True,
                "Y installation timing must be reconciled before window-16 screening")
        impl = backend(store, Path(previous["plan"]["profile"]["path"]), group)
        ctx = impl.installed_context(store.checked(store.base / "n04-window16"))
        ctx.previous_assets = ctx.full_assets
        api = load_module("p34_install_assets", store.root / "Tools/ota/p34_install_assets.py")
        prepared = api.prepare(ctx, N04_GROUPS["n04-window16"])
        manifests = dict(impl.profile["n04_assets"], **{"n04-window16": prepared["manifest"]})
        path = store.checked(store.base / "profile-n04-window16.json")
        value = dict(impl.profile, name="n04-window16-after-" + run, predecessor=previous["descriptor"],
            owned_configs=[{key: previous["report"]["inputs"]["config"][key] for key in ("path", "sha256")}],
            n04_assets=manifests,
            scope="One zero-start Y-to-Z FULL at 921600/window 16; same N04 executable, Boot and sender. "
                  "Sequential link screening plus installation observation, not same-package A/B or 1 MiB acceptance. "
                  "No replay, automatic follow-up, App stop or recording cleanup.")
        if path.exists():
            require(store.read(path) == value, "preserve existing window-16 execution profile")
        else:
            store.write(path, value)
        return dict(result="WINDOW16_ASSETS_READY", group="n04-window16", assets=manifests,
                    profile=record(path), device_operations=0, not_installed=True)


def prepare_speed16(store):
    """One Z-to-30225 full window screening, with unchanged executable and Boot."""
    with store.command_lock():
        run = store.current()
        require(run and store.read(store.run(run) / "plan.json").get("group") == NATIVE_DIAGNOSTIC_GROUP,
                "speed screening must follow the actual completed Z owner")
        previous = completed_full_predecessor(store, current_full_descriptor(store, run), group=NATIVE_DIAGNOSTIC_GROUP)
        impl = backend(store, Path(previous["plan"]["profile"]["path"]), NATIVE_DIAGNOSTIC_GROUP)
        ctx = impl.installed_context(store.checked(store.base / SPEED16_GROUP))
        ctx.previous_assets = ctx.full_assets
        api = load_module("p34_speed16_assets", store.root / "Tools/ota/p34_install_assets.py")
        prepared = api.prepare(ctx, N04_GROUPS[SPEED16_GROUP])
        manifests = dict(impl.profile["n04_assets"], **{SPEED16_GROUP: prepared["manifest"]})
        path = store.checked(store.base / "profile-speed-window16.json")
        value = dict(impl.profile, name=SPEED16_GROUP + "-after-" + run, predecessor=previous["descriptor"],
            owned_configs=[{key: previous["report"]["inputs"]["config"][key] for key in ("path", "sha256")}],
            n04_assets=manifests, speed_window16=True, native_diagnostic=False, tunnel_protocol="quic",
            scope="One zero-start FULL window-16 screen on Z versus retained window-8 records. "
                  "Same N04 executable/Boot/sender; only legal target header/package differ. "
                  "Sequential screening, not strict same-package A/B; no root-cause or epoch-log gate. "
                  "Retain 30225 on success; no replay, automatic follow-up or recording deletion.")
        if path.exists():
            require(store.read(path) == value, "preserve existing speed screening profile")
        else:
            store.write(path, value)
        return dict(result="SPEED_WINDOW16_PREPARED", profile=record(path), assets=prepared["manifest"],
                    device_operations=0, new_firmware_build=False)


def prepare_speed32(store):
    """One explicit 30225-to-30226 screen; no replay, build or device operation."""
    with store.command_lock():
        run = store.current()
        require(run and store.read(store.run(run) / "plan.json").get("group") == SPEED16_GROUP,
                "window-32 screening must follow the actual completed window-16 owner")
        previous = completed_full_predecessor(store, current_full_descriptor(store, run), group=SPEED16_GROUP)
        impl = backend(store, Path(previous["plan"]["profile"]["path"]), SPEED16_GROUP)
        ctx = impl.installed_context(store.checked(store.base / SPEED32_GROUP))
        ctx.previous_assets = ctx.full_assets
        api = load_module("p34_speed32_assets", store.root / "Tools/ota/p34_install_assets.py")
        prepared = api.prepare(ctx, N04_GROUPS[SPEED32_GROUP])
        manifests = dict(impl.profile["n04_assets"], **{SPEED32_GROUP: prepared["manifest"]})
        path = store.checked(store.base / "profile-speed-window32.json")
        value = dict(impl.profile, name=SPEED32_GROUP + "-after-" + run, predecessor=previous["descriptor"],
            owned_configs=[{key: previous["report"]["inputs"]["config"][key] for key in ("path", "sha256")}],
            n04_assets=manifests, speed_window32=True, native_diagnostic=False, tunnel_protocol="quic",
            scope="One zero-start FULL at 921600/window 32 after verified 30225. "
                  "Same N04 executable/Boot/sender; fresh INFO must admit all 32 segments. "
                  "Sequential screening, not strict same-package A/B or 1 MiB acceptance. "
                  "Retain 30226 on success; no replay, automatic follow-up or recording deletion.")
        if path.exists():
            require(store.read(path) == value, "preserve existing window-32 screening profile")
        else:
            store.write(path, value)
        return dict(result="SPEED_WINDOW32_PREPARED", profile=record(path), assets=prepared["manifest"],
                    device_operations=0, new_firmware_build=False)


def recover_network(store, run):
    """Restore the completed host pointer only when a diagnostic cell never began."""
    with store.command_lock():
        tests = verify_tests(store)
        require(store.current() == run, "network recovery must name the current failed owner")
        out = store.run(run)
        plan = store.read(out / "plan.json")
        gap = plan.get("group") == "ack-gap-bootstrap"
        require((gap or plan.get("group") == NATIVE_DIAGNOSTIC_GROUP) and record(plan["profile"]["path"]) == plan["profile"],
                "not the unchanged native diagnostic profile")
        require(not (out / "cells").exists() and
                {path.name for path in (out / "runtime").iterdir()} == {"network"},
                "a device cell may have started; network-only recovery refused")
        closed = store.read(out / "runtime/network/closed.json")
        result = store.read(out / "network-result.json")
        service = store.read(out / "network-owner/network/closed.json")
        require(closed["worker_exit"] == 1 and not closed["forced_termination"] and
                service["listener_closed"] and service["worker_stopped"] and
                result.get("device_operations") == 0 and
                (result.get("error") == "TimeoutError" and result.get("detail") == "The read operation timed out"
                 if gap else result.get("detail") == "tunnel readiness deadline"),
                "network failure/closure is not the diagnosed no-cell failure")
        log = out / "network-owner/network/tunnel.log"
        text = log.read_text(encoding="utf-8")
        extra = []
        if gap:
            served = out / "network-owner/network/service.log"
            actions = out / "actions.jsonl"
            lines = served.read_text(encoding="utf-8").splitlines()
            events = [json.loads(line) for line in actions.read_text(encoding="utf-8").splitlines()]
            require('Registered tunnel connection' in text and 'protocol=quic' in text and
                    any(line.startswith('GET /api/public/firmware/latest?') and ' -> 200 ' in line for line in lines) and
                    any(line.startswith('GET /api/public/firmware/download?') and ' -> 200 ' in line for line in lines) and
                    events and events[-1].get('id') == 'https-readiness' and
                    events[-1].get('error') == 'TimeoutError', "no bound HTTP read-timeout evidence")
            extra = [record(served), record(actions)]
        else:
            require('status=fail target=region1.v2.argotunnel.com' in text and
                    'details="HTTP/2 connection is blocked or unreachable"' in text and
                    'details="QUIC connection successful"' in text and 'suggested_protocol=quic' in text,
                    "no discriminating QUIC connectivity evidence")
        previous = completed_full_predecessor(store, plan["predecessor"],
                                             group="receive-pressure" if gap else "n04-measure")
        destination = store.checked(store.base / "network-recovery" / run)
        profile = dict(store.read(plan["profile"]["path"]), tunnel_protocol="quic",
                       network_recovery=record(out / "plan.json"))
        profile_path = store.checked(destination / "profile.json")
        store.write(profile_path, profile)
        evidence = dict(result="NETWORK_ONLY_RECOVERY_PREPARED", failed_run=run,
            restored_run=previous["descriptor"]["run"], profile=record(profile_path), tests=tests,
            inputs=[record(out / name) for name in ("plan.json", "network-result.json", "runtime/network/closed.json",
                "network-owner/network/closed.json", "network-owner/network/tunnel.log")] + extra,
            device_operations=0, replayed_transfer=False, original_failure_preserved=True)
        store.write(destination / "intent.json", evidence)
        store.write(store.base / "current.json", dict(run=previous["descriptor"]["run"], created=now(),
                    network_recovery=record(destination / "intent.json")), replace=True)
        store.write(destination / "result.json", dict(evidence, result="NETWORK_ONLY_POINTER_RECOVERED"))
        return store.read(destination / "result.json")


def prepare_diagnostic(store):
    """Rebind frozen Z to a new window-8 observation; do not rebuild or open USB."""
    with store.command_lock():
        run = store.current()
        require(run, "completed Y required before native diagnosis")
        previous = completed_full_predecessor(store, current_full_descriptor(store, run), group="n04-measure")
        require(previous["report"].get("n04_install_measurement") is True, "Y timing must be reconciled")
        source = store.checked(store.base / "profile-n04-window16.json")
        value = store.read(source)
        require(value["predecessor"] == previous["descriptor"], "frozen Z profile has a different predecessor")
        value = dict(value, name=NATIVE_DIAGNOSTIC_GROUP + "-after-" + run, native_diagnostic=True,
            scope="Fixed Y/921600/window 8 with exact-PID native logcat and query marker admission. "
                  "One legal zero-start Y-to-Z FULL; no old-transfer replay or causal attribution without paired evidence. "
                  "No automatic cleanup, follow-up or change to the frozen window-16 profile.")
        path = store.checked(store.base / "profile-n04-diagnostic8.json")
        if path.exists():
            require(store.read(path) == value, "preserve existing native diagnostic profile")
        else:
            store.write(path, value)
        return dict(result="NATIVE_DIAGNOSTIC_PROFILE_PREPARED", profile=record(path),
                    group=NATIVE_DIAGNOSTIC_GROUP, device_operations=0, source_profile=record(source))


def prepare_patch(store, group):
    """Bind prepared bytes to an actual predecessor, without opening any device."""
    require(group in ALL_PATCH_GROUPS, "select an explicit prepared PATCH group")
    with store.command_lock():
        run = store.current()
        require(run, "completed predecessor required before PATCH preparation")
        prior_group = store.read(store.run(run) / "plan.json").get("group")
        require(prior_group == PREDECESSOR_GROUPS[group], "PATCH preparation requires its actual completed predecessor")
        previous = completed_full_predecessor(store, current_full_descriptor(store, run), group=prior_group)
        require(previous["report"].get("n04_install_measurement") is True,
                "predecessor installation timing must be reconciled before PATCH work")
        impl = backend(store, Path(previous["plan"]["profile"]["path"]), prior_group)
        ctx = impl.installed_context(store.checked(store.base / group))
        ctx.previous_assets = ctx.full_assets
        api = patch_assets_api(store, group)
        prepared = api.load_for_context(ctx, ALL_PATCH_GROUPS[group])
        path = store.checked(store.base / ("profile-" + group + ".json"))
        value = dict(impl.profile, name=group + "-after-" + run, predecessor=previous["descriptor"],
            owned_configs=[{key: previous["report"]["inputs"]["config"][key] for key in ("path", "sha256")}],
            patch_group=group, patch_assets=prepared["manifest"],
            scope="Prepared only: resolve P34-WAIT-01 before changing receiver or window. "
                  "Y-to-AA FULL bootstrap, then ONE AA-to-AB PATCH alternative; unchanged Boot. "
                  "Zero-start 921600/window 8, final raw identity required. "
                  "No replay, implicit continuation, cleanup or formal reference admission.")
        if group in PATCH32_GROUPS:
            value.update(native_diagnostic=False, tunnel_protocol="quic", patch32=True,
                scope="Two serial legal cells: 30226-to-30227 FULL introduces the coalescing receiver; "
                      "only actual completed30227 admits one30227-to-30228 exact1MiB PATCH. "
                      "921600/window32, original Boot/APK/protocol guards, final raw/CONFIRMED required. "
                      "Compact PATCH is offline-only. No implicit start, cleanup, replay or formal acceptance.")
        if group in RECEIVE_GROUPS:
            value.update(native_diagnostic=False, tunnel_protocol="quic", receive_restore=True,
                patch_prior_assets={ALL_PATCH_GROUPS[name]["assets"]: record(store.root / ALL_PATCH_GROUPS[name]["assets"])
                                    for name in PATCH32_GROUPS},
                scope="30228-to-30229 FULL installs the checked receive-restore candidate; only actual completed30229 "
                      "admits30229-to-30230 exact1MiB PATCH. Keep921600/window32 and original Boot/APK. "
                      "Bootstrap does not measure the new receiver. No implicit start, cleanup, replay or formal acceptance.")
        if group in ACK_GAP_GROUPS:
            value.update(ack_gap=True, native_diagnostic=False, tunnel_protocol="quic",
                patch_prior_assets={ALL_PATCH_GROUPS[name]["assets"]: record(store.root / ALL_PATCH_GROUPS[name]["assets"])
                                    for name in patch_asset_groups(group) if name != group},
                scope="30230-to-30232 FULL installs the isolated 1ms ACK-gap candidate. "
                      "This bootstrap measures the unchanged30230 receiver, not the candidate. "
                      "Retain original Boot and verified30232; no replay, cleanup or formal acceptance.")
            if group == "ack-batch-bootstrap":
                value.update(ack_batch=True, scope="30232-to-30235 FULL installs byte-preserving ACK batching. "
                    "The bootstrap still measures30232. Preserve every ACK, original Boot, confirmation and full raw identity. "
                    "No automatic replay, firmware downgrade, record deletion or formal acceptance.")
            if group == BOOT_COPY_GROUP:
                value.update(ack_batch=True, boot_copy=True,
                    scope="30235-to-30238 header-only FULL on explicitly verified replacement Boot. "
                          "921600/window28. Functional best-case copy screen, not a representative firmware speed claim. "
                           "Preserve full identity, every checkpoint and30-second healthy confirmation.")
            if group in (*COST_GROUPS, *ERASE_GROUPS):
                value.update(ack_batch=True, boot_copy=True, install_cost=True,
                    scope="30238-to30239 diagnostic bootstrap, then verified30239-to30240 measurement. "
                          "921600/window28 and retained verified Boot. No skipped erase/checkpoint/confirmation. "
                          "Bootstrap cannot measure the new cost collector; no automatic replay or formal acceptance.")
            if group in ERASE_GROUPS:
                value.update(block_erase=True,
                    scope="30240-to30241 block-erase bootstrap, then verified30241-to30242 header-only measurement. "
                          "921600/window28, same APK and verified Boot, separate4KiB header invalidation and exact payload extent. "
                          "Retain readback, marker-last, rollback and30-second confirmation; no replay or formal acceptance.")
            if group == RECONNECT_GROUP:
                candidate = load_module("p34_reconnect_profile", store.root / "Tools/ota/p34_reconnect_profile.py")
                candidate.apk()
                value.update(ack_batch=True, boot_copy=True, install_cost=True, block_erase=True,
                    reconnect_probe=True, reconnect_apk=record(store.root / candidate.APK_REPORT),
                    scope="30242-to30243 header-only FULL, new verified diagnostic APK; INFO2000ms/interval500ms. "
                          "921600/window28, retained Boot and executable, full readback and30-second confirmation. "
                          "No replay, rollback weakening, deletion or formal acceptance.")
        if path.exists():
            require(store.read(path) == value, "preserve existing PATCH execution profile")
        else:
            store.write(path, value)
        return dict(result="PATCH_PROFILE_PREPARED", group=group, profile=record(path),
            assets=prepared["manifest"], device_operations=0, not_installed=True,
            execution_gate=("fresh source-bound device/recording admission" if group in (*PATCH32_GROUPS, *RECEIVE_GROUPS) else
                            "P34-WAIT-01 diagnosis and fresh device/recording admission"))


def quiesce(store, run, cell):
    with store.command_lock():
        require(run == store.current() and cell == INSTALL_CELL, "quiesce only the current completed full owner")
        verify_tests(store)
        group = store.read(store.run(run) / "plan.json").get("group")
        previous = completed_full_predecessor(store, current_full_descriptor(store, run), group=group)
        profile = Path(previous["plan"]["profile"]["path"])
        impl = backend(store, profile, group)
        out = store.checked(store.base / "quiesce" / str(time.time_ns()))
        ctx = impl.context(out)
        impl.preflight(ctx, out)
        return impl.quiesce(ctx, out, previous)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", required=True, type=Path)
    parser.add_argument("--profile", type=Path)
    parser.add_argument("--run")
    parser.add_argument("--cell", choices=tuple(CELLS), default="s01")
    parser.add_argument("--group", choices=GROUPS, default="screen",
                        help="comparison group for start/identity; workers take it from the plan")
    parser.add_argument("--delete", action="append", default=[], metavar="CAPTURE",
                        help="prune: App capture directory to delete; eligibility is re-derived, never assumed")
    parser.add_argument("--apply", action="store_true", help="prune-completed: delete only the verified original predecessor copy after archival")
    parser.add_argument("--offline", action="store_true", help="collect: analyze preserved App/MCU files without device operations")
    parser.add_argument("--verify-mcu", action="store_true", help="collect: reconcile a closed cell with a bounded staging readback; no transfer")
    parser.add_argument("--analysis", help=argparse.SUPPRESS)
    parser.add_argument("--prestart-recovery", type=Path,
                        help="start: exact verified no-BEGIN recovery pointer, never a full OTA retry")
    parser.add_argument("--retirement-recovery", type=Path,
                        help="start: verified pre-admission config-move recovery; no implicit replay")
    parser.add_argument("command", choices=("doctor", "start", "status", "collect", "stop", "test", "identity", "prune", "prepare-full",
                                            "recover-prestart", "recover-retirement", "recover-network", "prepare-window8", "prepare-repeat", "prepare-install", "prepare-window16", "prepare-speed16", "prepare-speed32", "prepare-diagnostic", "prepare-patch", "prune-completed", "quiesce",
                                            "_network", "_cell", "_readback", "_install_readback"))
    args = parser.parse_args(argv)
    require(not args.offline or args.command == "collect", "--offline is only valid for collect")
    require(not args.verify_mcu or args.command == "collect" and not args.offline, "--verify-mcu requires collect without --offline")
    require(not args.analysis or args.command in ("_readback", "_install_readback"), "--analysis is internal to an owned readback")
    require(not args.delete or args.command == "prune", "--delete is only valid for prune")
    require(not args.apply or args.command == "prune-completed", "--apply is only valid for prune-completed")
    require(not args.prestart_recovery or args.command == "start", "--prestart-recovery is only valid for start")
    require(not args.retirement_recovery or args.command == "start", "--retirement-recovery is only valid for start")
    require(args.command in ("start", "identity", "prepare-patch") or args.group == "screen",
            "--group selects a new session; existing sessions carry their group in the plan")
    require(Path.cwd() == args.root and sys.flags.isolated and sys.flags.no_site and sys.dont_write_bytecode,
            "run from the explicit project root with Python -I -S -B")
    store = Store(args.root)
    profile = args.profile or store.base / "profile.json"
    begun = time.monotonic()
    if args.command == "status":
        result = status(store, args.run, args.cell)
    elif args.command == "stop":
        require(args.run or store.current(), "no owned session to stop")
        result = stop(store, args.run or store.current(), args.cell)
    elif args.command == "test":
        out = store.checked(store.base / "tests" / str(time.time_ns()))
        for name in ("console.log", "unittest.log", "timeout.json", "result.json"):
            store.checked(out / name)
        store.checked(out).mkdir(parents=True)
        env = dict(os.environ, P34_TEST_OUT=str(out))
        for key in ("TEMP", "TMP", "TMPDIR", "HOME", "USERPROFILE", "APPDATA", "LOCALAPPDATA"):
            path = store.checked(out / "host" / key.lower())
            path.mkdir(parents=True, exist_ok=True)
            env[key] = str(path)
        command = [sys.executable, "-I", "-S", "-B", "-X", "utf8", str(store.root / "tests/ota/test_p34_session.py")]
        try:
            run = subprocess.run(command, cwd=store.root, env=env, capture_output=True,
                timeout=HOST_TEST_SECONDS, creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
        except subprocess.TimeoutExpired as error:
            console = store.raw(out / "console.log", (error.stdout or b"") + (error.stderr or b""))
            log = store.checked(out / "unittest.log")
            store.write(out / "timeout.json", dict(result="HOST_TEST_TIMEOUT", passed=False, tests=None,
                command=command, cwd=str(store.root), timeout_seconds=HOST_TEST_SECONDS,
                console=console, partial_tests=record(log) if log.is_file() else None, device_operations=0))
            raise RuntimeError("session host tests timed out; preserve partial logs in " + str(out)) from error
        store.raw(out / "console.log", run.stdout + run.stderr)
        result = store.read(out / "result.json")
        require(run.returncode == 0 and result["passed"], "session self-tests failed; see preserved console.log")
        store.write(store.base / "tests/latest.json", result, replace=True)
    elif args.command == "start":
        result = start(store, profile, args.cell, args.group, args.prestart_recovery, args.retirement_recovery)
    elif args.command == "recover-retirement":
        require(args.run and args.cell == INSTALL_CELL, "retirement recovery requires the explicit failed run and s04")
        result = retirement_api(store).reconcile(store, args.run)
    elif args.command == "recover-prestart":
        require(args.run and args.cell == INSTALL_CELL, "prestart recovery requires the explicit failed run and s04")
        result = recover_prestart(store, args.run)
    elif args.command == "recover-network":
        require(args.run and args.cell == INSTALL_CELL, "network recovery requires the exact failed run and s04")
        result = recover_network(store, args.run)
    elif args.command == "identity":
        result = identity(store, profile, args.group)
    elif args.command == "prune":
        result = prune(store, profile, args.delete)
    elif args.command == "prune-completed":
        require(args.run and args.cell == INSTALL_CELL, "completed cleanup requires the original explicit run and s04")
        result = prune_completed(store, args.run, apply=args.apply)
    elif args.command == "prepare-full":
        result = prepare_full(store)
    elif args.command == "prepare-window8":
        result = prepare_window8(store)
    elif args.command == "prepare-repeat":
        result = prepare_repeat(store)
    elif args.command == "prepare-install":
        result = prepare_install(store)
    elif args.command == "prepare-window16":
        result = prepare_window16(store)
    elif args.command == "prepare-speed16":
        result = prepare_speed16(store)
    elif args.command == "prepare-speed32":
        result = prepare_speed32(store)
    elif args.command == "prepare-diagnostic":
        result = prepare_diagnostic(store)
    elif args.command == "prepare-patch":
        result = prepare_patch(store, args.group)
    elif args.command == "quiesce":
        require(args.run, "quiesce requires the explicit completed run")
        result = quiesce(store, args.run, args.cell)
    elif args.command in ("_network", "_cell", "_readback", "_install_readback"):
        require(args.run, "owned worker requires explicit run")
        out = store.run(args.run)
        plan = store.read(out / "plan.json")
        profile = Path(plan["profile"]["path"])
        impl = backend(store, profile, plan.get("group", "screen"))
        ctx = impl.context(out)
        require(ctx.supervisor.owned.in_job(), "internal command requires the owned supervisor")
        if args.command == "_readback":
            return impl.readback_worker(ctx, out, args.cell, args.analysis)
        if args.command == "_install_readback":
            return impl.install_readback_worker(ctx, out, args.cell, args.analysis)
        impl.validate(ctx, out)
        os.environ.update(ctx.environment())
        return impl.network_worker(ctx, out) if args.command == "_network" else impl.cell_worker(ctx, out, args.cell)
    else:
        with store.command_lock():
            if args.command == "doctor":
                impl = backend(store, profile)
                out = store.checked(store.base / "doctor" / str(time.time_ns()))
                ctx = impl.context(out)
                impl.preflight(ctx, out)
                result = impl.inspect(ctx, out / "phone")
                result["previous_session"] = status(store, args.run, args.cell)
                store.write(out / "result.json", result)
            else:
                run = args.run or store.current()
                require(run, "no session to collect")
                out = store.run(run)
                plan = store.read(out / "plan.json")
                impl = backend(store, Path(plan["profile"]["path"]), plan.get("group", "screen"))
                ctx = impl.context(out)
                result = impl.collect(ctx, out, args.cell, offline=args.offline, verify_mcu=args.verify_mcu)
    result["command_elapsed_seconds"] = round(time.monotonic() - begun, 4)
    print(json.dumps(result, ensure_ascii=True), flush=True)
    return int(result.get("result") in ("IDENTITY_FAILED", "PRESTART_RECOVERY_FAILED", "RETIREMENT_RECOVERY_FAILED", "APP_QUIESCE_FAILED", "COMPLETED_CAPTURE_PRUNE_FAILED"))


if __name__ == "__main__":
    sys.modules["p34_session"] = sys.modules[__name__]
    try:
        raise SystemExit(main())
    except (RuntimeError, ValueError, OSError, KeyError) as error:
        print(json.dumps(dict(result="STOPPED", error=type(error).__name__, detail=str(error))), flush=True)
        raise SystemExit(1)
