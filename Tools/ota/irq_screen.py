"""Repeatable, fixed-input IRQ receiver screening without QSPI changes."""
from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import json
import os
from pathlib import Path
import re
import runpy
import sys
import time
import types
import urllib.request

ROOT = Path(__file__).resolve().parents[2]
SELF = Path(__file__).resolve()
AREA = ROOT / ".cache/p34q/irqscreen"
PRIOR = ROOT / ".cache/p34q/irq"
PRIOR_RUN = "irq-bootstrap-115200"
FILE_NAME = "irq-fixed-full.etu"
BASE_VERSION, TARGET_VERSION = 30210, 30211
BASE_SHA = "709e0533989d149221dc5322ff0a10ebe872c6faa06ad1e9b630d32423f80e60"
CELLS = (("irq-460800", 460800), ("irq-115200", 115200), ("irq-921600", 921600))
ADAPTER_INPUTS = {
    "baud_tune.py": "789a49905ce69aa7e7a4cb0146b1f594ea2b9c9fa8841bb11a9b3c62a84ddd6d",
    "baud_restore.py": "6bb3489e2c478280da5468ac41c7bd0b331771968fbaed5ea634bf128657a72a",
}
IO = runpy.run_path(str(ROOT / ".agents/skills/e-track-flutter-debug/scripts/host_io.py"))


def require(value, reason):
    if not value:
        raise RuntimeError(reason)


def checked(path):
    return IO["checked_output"](ROOT, path)


def specialize(function, **bindings):
    scope = dict(function.__globals__, **bindings)
    return types.FunctionType(function.__code__, scope, function.__name__, function.__defaults__, function.__closure__)


def prior_complete(r):
    out = PRIOR / "runs" / PRIOR_RUN
    app = r.read(out / "finished/binding.json")
    board = r.read(out / "mcu/result.json")
    require(r.read(out / "completed.json")["result"] == "COMPLETED_RETAINED" and
            r.read(out / "coordinator-result.json")["result"] == "COMPLETED_RETAINED" and
            app["summary"]["outcome"] == "completed" and app["parser_exit"] == 0 and
            app["snapshot"] == r.b.record(out / "finished/snapshot.jsonl") and
            board["result"] == "TARGET_VERIFIED_RETAINED" and board["reader_closed"] and
            board["final_image"]["sha256"] == BASE_SHA and
            r.b.record(board["final_image"]["path"]) == board["final_image"], "bootstrap success is not reconciled")
    for owner in ("capture-" + PRIOR_RUN, "coordinate-" + PRIOR_RUN):
        closed = r.read(PRIOR / "runtime" / owner / "closed.json")
        require(closed["worker_exit"] == 0 and not closed["forced_termination"], "bootstrap owner is not normally closed")
    return [r.b.record(out / name) for name in
            ("completed.json", "coordinator-result.json", "finished/binding.json", "mcu/result.json")]


def validate_group(group):
    require(group["baseline_identity"]["version_code"] == BASE_VERSION and
            group["target_identity"]["version_code"] == TARGET_VERSION and
            group["baseline"]["sha256"] == BASE_SHA and
            group["baseline"]["bytes"] == group["target"]["bytes"] == 613264 and
            64 < group["package"]["bytes"] < group["target"]["bytes"] and
            all(group["decoder"].get(k) is True for k in
                ("passed", "byte_identical", "boot_ok", "guards_ok", "workspace_lifecycle_ok")), "IRQ screening input group differs")


def transform_adapter(name, source):
    require(hashlib.sha256(source.encode("utf-8")).hexdigest() == ADAPTER_INPUTS[name], "original adapter source drift")
    changes = [("30208", "30210", 1 if name == "baud_tune.py" else 13),
               ("30209", "30211", 1 if name == "baud_tune.py" else 8)]
    if name == "baud_restore.py":
        changes += [("RESTORE328", "RESTORE310", 1), ("RESTORED_328", "RESTORED_310", 2),
                    ("3.2.9-r328", "3.2.11-r310", 1), ("0x52333238", "0x52333130", 2),
                    ("0x38325352", "0x30315352", 2)]
    changes.append(('Path(__file__).with_name("baud_mcu.py")', repr(str(SELF.with_name("baud_mcu.py"))), 1))
    for before, after, count in changes:
        require(source.count(before) == count, "reviewed transform count drift: " + before)
        source = source.replace(before, after)
    if name == "baud_restore.py":
        before = '"-DCMAKE_BUILD_TYPE=Release", "-DCMAKE_OBJECT_PATH_MAX=1024"'
        after = before + ', "-DCMAKE_INSTALL_PREFIX=" + str(checked("install"))'
        require(source.count(before) == 1, "recovery configure source drift")
        source = source.replace(before, after, 1)
    compile(source, name, "exec")
    return source


def runtime():
    bootstrap = runpy.run_path(str(SELF.with_name("irq_bootstrap.py")))
    r = bootstrap["runtime"]()
    old_sources = [Path(x["path"]) for x in r.sources()]
    for common in (r.b, r.a.b):
        common.OUT = AREA
        common.host.OUT = AREA
    r.a.FW, r.a.OUT = PRIOR / "fw", AREA / "assets"
    r.a.RAW = PRIOR / "build/app-gcc/X-Track-App-GCC.bin"
    r.RUNTIME = AREA / "runtime"
    r.PHONE, r.NETWORK = r.RUNTIME / "phone-r1", r.RUNTIME / "network-r1"
    original_load = r.load

    def load(name, path):
        filename = Path(path).name
        if filename in ADAPTER_INPUTS:
            path = AREA / "adapters" / filename
        module = original_load(name, path)
        if filename in ADAPTER_INPUTS:
            module.m, module.b = r.m, r.b
            if filename == "baud_restore.py":
                module.a, module.OUT = r.a, AREA / "recovery"
                primitive_load = module.load

                def restoration_load(name, path):
                    old = primitive_load(name, path)
                    if Path(path).name == "restore_device.py":
                        native = runpy.run_path(str(SELF.with_name("baud_uncached.py")))["native_presence"]
                        old.c.host_presence = native
                        r.m.c.host_presence = native
                    return old

                module.load = restoration_load
        return module

    def sources():
        paths = set(old_sources + [SELF, SELF.with_name("test_irq_screen.py"),
            AREA / "adapters/manifest.json", AREA / "assets/manifest.json", AREA / "mcu-bindings.json",
            AREA / "recovery/manifest.json", *[AREA / "adapters" / n for n in ADAPTER_INPUTS]])
        return [r.b.record(p) for p in sorted(paths)]

    def authority():
        plan = r.read(AREA / "plan.json")
        require(plan["root"] == str(ROOT) and plan["cells"] == [dict(run=n, baud=b) for n, b in CELLS] and
                plan["sources"] == sources() and plan["apk"] == r.apk()["apk"] and
                plan["prior"] == prior_complete(r), "IRQ screening plan/source drift")
        validate_group(r.m.verified_assets()["groups"]["screen"])
        for manifest in ("adapters/manifest.json", "recovery/manifest.json"):
            require(all(r.b.record(x["path"]) == x for x in r.read(AREA / manifest)["files"]), "prepared adapter/recovery drift")
        return plan

    original_config = r.make_config

    def make_config(assets, origin, token_key):
        value = original_config(assets, origin, token_key)
        for release in value["releases"].values():
            release["asset"]["fileName"] = FILE_NAME
        return value

    def inspect_start(run):
        require(run in dict(CELLS), "unplanned IRQ run")
        return specialize(bootstrap["inspect_start"], RUN=run, FILE_NAME=FILE_NAME)(r, run)

    r.load, r.sources, r.authority = load, sources, authority
    r.make_config, r.inspect_start = make_config, inspect_start
    r.hostcheck = lambda: specialize(bootstrap["hostcheck"], AREA=AREA, FILE_NAME=FILE_NAME)(r)
    r.launch_worker = lambda name, mode, seconds, run=None: r.supervisor.owned.launch(
        r.RUNTIME / name, SELF, [mode] + (["--run", run] if run else []), seconds)
    r.https_check = lambda: https_check(r)
    return r


def prepare_assets():
    r = runtime()
    prior_complete(r)
    old = runpy.run_path(str(SELF.with_name("irq_bootstrap.py")))["runtime"]()
    old.authority()
    original, bindings = old.m.verified_assets(), old.m.load_bindings()
    h = runpy.run_path(str(ROOT / ".cache/p34q/prepare_next.py"))
    out = checked(AREA / "assets")
    require(not out.exists() and not (AREA / "adapters").exists(), "preserve previous preparation")
    for name in ("images", "packages", "negative", "logs", "host", "result.json", "manifest.json"):
        checked(out / name)
    for name in ADAPTER_INPUTS:
        checked(AREA / "adapters" / name)
    checked(AREA / "adapters/manifest.json")
    checked(AREA / "mcu-bindings.json")
    generator = r.raw(AREA / "asset-generator.py", SELF.read_bytes())
    transformed = []
    for name in ADAPTER_INPUTS:
        path = SELF.with_name(name)
        data = transform_adapter(name, path.read_text(encoding="utf-8")).encode("ascii")
        transformed.append(r.raw(AREA / "adapters" / name, data))
    r.save(AREA / "adapters/manifest.json", dict(files=transformed,
        inputs=[r.b.record(SELF.with_name(n)) for n in ADAPTER_INPUTS], generator=generator,
        scope="30211 to 30210 identities only; immutable original transaction/guards; contained install prefix"))
    group = original["groups"]["screen"]
    base = out / "images/3.2.10-p34i.bin"
    target = out / "images/3.2.11-p34i.bin"
    boot = out / "images/whole-boot.bin"
    for path, source in ((base, group["target"]), (boot, original["whole_boot"])):
        r.raw(path, Path(source["path"]).read_bytes())
    target.parent.mkdir(parents=True, exist_ok=True)

    def command(tag, args):
        return h["run"](out, tag, args, r.a.FW, 180)

    command("finalize", r.a.python_tool("etu_pack.py", ["finalize", "--app", r.a.RAW,
        "--out", checked(target), "--ver-name", "3.2.11-p34i", "--build-ts", "1786320000"]))
    baseline, data = base.read_bytes(), target.read_bytes()
    require(baseline[:0x400] == data[:0x400] and baseline[0x460:] == data[0x460:], "non-header firmware body changed")
    package = checked(out / "packages" / FILE_NAME)
    package.parent.mkdir(parents=True, exist_ok=True)
    command("pack", r.a.python_tool("etu_pack.py", ["pack-full", "--app", target,
        "--out", package, "--target-vcode", str(TARGET_VERSION)]))
    header = r.a.package_info(package.read_bytes(), BASE_VERSION, TARGET_VERSION)
    decoded = checked(out / "images/decoded.bin")
    command("unpack", r.a.python_tool("etu_unpack.py", [package, "--out", decoded, "--verify-fw-header"]))
    require(decoded.read_bytes() == data, "unpacked image differs")
    decoder = PRIOR / "assets/bin/full_image_host.exe"
    result = json.loads(command("decode", [decoder, package, base, target, "ok"]))
    negatives = []
    for name, mutation, expected in r.a.negatives(package.read_bytes(), BASE_VERSION):
        path = checked(out / "negative" / (name + ".etu"))
        r.raw(path, mutation)
        value = json.loads(command(name, [decoder, path, base, target, expected]))
        require(value["passed"] and value["prepares"] == 0, "negative package reached prepare")
        negatives.append(name)
    group = dict(baseline=r.b.record(base), baseline_identity=r.a.legacy.firmware(baseline),
        target=r.b.record(target), target_identity=r.a.legacy.firmware(data), package=r.b.record(package),
        header=header, decoder=result)
    validate_group(group)
    value = dict(result="HOST_READY", groups=dict(bootstrap=group, screen=group), whole_boot=r.b.record(boot),
        candidate="IRQ repair only; original staging and sender", body_identical_except_header=True,
        negative_cases=negatives, hardware="NOT_RUN", independent_acceptance=False)
    r.save(out / "result.json", value)
    r.save(out / "manifest.json", dict(metadata=value,
        files=[r.b.record(p) for p in sorted(out.rglob("*")) if p.is_file()],
        inputs=[generator, r.b.record(r.a.RAW), r.b.record(decoder),
                r.b.record(PRIOR / "assets/manifest.json"), r.b.record(PRIOR / "build-result.json")]))
    profiles = {}
    for version, image, identity in ((BASE_VERSION, base, group["baseline_identity"]),
                                    (TARGET_VERSION, target, group["target_identity"])):
        profile = dict(bindings["profiles"][str(BASE_VERSION)])
        profile.update(image=r.b.record(image), identity=identity, prefix=image.read_bytes()[:0x460].hex())
        profiles[str(version)] = profile
    r.save(AREA / "mcu-bindings.json", dict(profiles=profiles, whole_boot=value["whole_boot"],
        boot_map=bindings["boot_map"], source=generator, hardware_contacted=False))
    print("IRQ_SCREEN_ASSETS_READY", json.dumps(dict(package=group["package"], target=group["target"])), flush=True)


def https_check(r):
    origin = r.live_network()["origin"]
    group = r.m.verified_assets()["groups"]["screen"]
    opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
    url = origin + r.service.LATEST_PATH + "?" + r.urllib.parse.urlencode(r.query_for(group))
    with opener.open(url, timeout=30) as response:
        body = json.loads(response.read(16384))
    r.verify_latest(body, group)
    parsed = r.urllib.parse.urlsplit(body["asset"]["downloadUrl"])
    require(parsed.scheme + "://" + parsed.netloc == origin, "unexpected package download origin")
    with opener.open(body["asset"]["downloadUrl"], timeout=30) as response:
        data = response.read(group["package"]["bytes"] + 1)
    require(data == Path(group["package"]["path"]).read_bytes(), "HTTPS package differs")
    r.save(r.NETWORK / "verified.json", dict(time=r.b.now(), origin=origin, tls_verified=True,
        proxy=False, package=group["package"], source=r.b.record(SELF)))


def freeze(r):
    require(not (AREA / "plan.json").exists(), "preserve original plan")
    tests = r.read(AREA / "host-tests/result.json")
    require(tests["passed"] and tests["source"] == r.b.record(SELF) and
            tests["test_source"] == r.b.record(SELF.with_name("test_irq_screen.py")), "source-bound tests required")
    recovery = r.read(AREA / "recovery/result.json")
    require(recovery["result"] == "HOST_READY" and recovery["expected"]["from_version"] == TARGET_VERSION and
            recovery["expected"]["to_version"] == BASE_VERSION and recovery["host_tests"] == 18 and
            recovery["errors"] == 0 and not recovery["boot_replacement"], "complete recovery is not prepared")
    validate_group(r.m.verified_assets()["groups"]["screen"])
    r.hostcheck()
    r.save(AREA / "plan.json", dict(time=r.b.now(), root=str(ROOT), cells=[dict(run=n, baud=b) for n, b in CELLS],
        sources=r.sources(), apk=r.apk()["apk"], prior=prior_complete(r),
        host_tests=r.b.record(AREA / "host-tests/result.json"), recovery=r.b.record(AREA / "recovery/manifest.json"),
        owner="root; sole serial physical-link owner", phone=r.original_phone.SERIAL, target=r.TARGET,
        authority="User P3-4 continuation and device-experiment-policy; no per-cell approval", repetitions=1,
        order_reason="screen former CRC failure at 460800 first, then equal-input 115200 and 921600 controls",
        unchanged="IRQ-only body, App, 128-byte DATA, GATT reuse/no-response, window/CRC/SHA/durable/retries",
        initial_state="30210 with zero durable for this package; unmatched and erased journals both rebuild_session",
        recovery_route="complete physical 30210 backup plus tested inactive-BCB helper, ordinary Boot rollback",
        stop_rule="unknown state, integrity/recovery failure or unchanged repeated fault pauses dependent mutations",
        final_state="verified 30211 retained after completed cells; no automatic downgrade at closeout",
        human_actions="permissions and connection/download/start UI only; no automatic taps",
        runtime=dict(phone_seconds=5400, network_seconds=10800, capture_seconds=4100, transfer_reserve=1280),
        qspi=False, boot_replacement=False, clear_app_data=False, release=False, independent_acceptance=False))
    r.authority()
    print("IRQ_SCREEN_PLAN_READY", flush=True)


def closed_owner(r, directory):
    value = r.wait_file(directory / "closed.json", 40)
    require(value["worker_exit"] == 0 and not value["forced_termination"], "owned worker closure is not clean")
    return r.b.record(directory / "closed.json")


def stop_completed_app(r, run, out):
    binding = r.read(out / "finished/binding.json")
    require(binding["summary"]["outcome"] == "completed" and binding["parser_exit"] == 0, "App outcome unresolved")
    p = r.phone(run)
    p.phone_identity()
    require(p.installed("runtime") is not None, "completed exact APK absent")
    pid = p.command(["shell", "pidof", r.PKG], check=False).strip()
    if pid:
        require(pid == str(binding["pid"]), "App process changed since completed capture")
        pkg, actual_pid, remote = p.location("runtime")
        health = json.loads(p.file_bytes(pkg, remote + "/health.json", 8192))
        require(actual_pid == binding["pid"] and health["healthy"] and health["lost"] == 0 and
                health["upgradeStarts"] == health["upgradeEnds"] == 1 and health["outcome"] == "completed",
                "App has a new or unresolved invocation")
        r.event("stop-completed-" + run, "started", pid=int(pid))
        p.command(["shell", "am", "force-stop", pkg])
        require(not p.command(["shell", "pidof", pkg], check=False).strip(), "completed App did not stop")
        r.event("stop-completed-" + run, "completed", data_preserved=True)


def stop_service(r, directory, owner, *, phone=False):
    if not (directory / "closed.json").exists() and not (directory / "stop.json").exists():
        r.save(directory / "stop.json", dict(time=r.b.now(), reason="handoff completed IRQ bootstrap to fixed-input screen"))
    value = r.wait_file(directory / "closed.json", 35)
    if phone:
        require(value["port_closed"] and value["stop_exit"] == 0 and not value.get("forced_cleanup") and
                not r.phone(PRIOR_RUN).alive(), "old private USB did not close gracefully")
    else:
        require(value["listener_closed"] and value["worker_stopped"], "old HTTP service did not close")
    closed_owner(r, owner)


def admit_next(r, run):
    require(run in dict(CELLS), "unplanned screening cell")
    index = [name for name, _ in CELLS].index(run)
    require(not r.cell(run).exists() and not (AREA / "rates" / (run + ".json")).exists(),
            "cell preparation may already have executed; reconcile it instead of replaying")
    if index == 0:
        prior_complete(r)
        return None
    previous = CELLS[index - 1][0]
    out = r.cell(previous)
    require(r.read(out / "completed.json")["result"] == "COMPLETED_RETAINED" and
            r.read(out / "coordinator-result.json")["result"] == "COMPLETED_RETAINED", "previous cell not completed")
    app, board = r.read(out / "finished/binding.json"), r.read(out / "mcu/result.json")
    target = r.m.verified_assets()["groups"]["screen"]["target"]
    require(app["summary"]["outcome"] == "completed" and app["parser_exit"] == 0 and
            board["result"] == "TARGET_VERIFIED_RETAINED" and board["reader_closed"] and
            board["final_image"]["sha256"] == target["sha256"], "previous full target/snapshot not verified")
    for name in ("capture-" + previous, "coordinate-" + previous):
        closed_owner(r, r.RUNTIME / name)
    return previous


def setup(r, run):
    result = dict(time=r.b.now(), run=run, result="SETUP_FAILED", source=r.b.record(SELF))
    try:
        previous = admit_next(r, run)
        if previous is None:
            old = runpy.run_path(str(SELF.with_name("irq_bootstrap.py")))["runtime"]()
            old.authority()
            stop_service(old, old.NETWORK, old.RUNTIME / "network-worker")
            r.launch_worker("network-worker", "network-worker", 10830)
            r.wait_file(r.NETWORK / "ready.json", 100)
            r.https_check()
            stop_completed_app(old, PRIOR_RUN, PRIOR / "runs" / PRIOR_RUN)
            stop_service(old, old.PHONE, old.RUNTIME / "phone-worker", phone=True)
            require(not r.phone(run).alive(), "private USB port already has an owner")
            r.launch_worker("phone-worker", "phone-worker", 5430)
            r.wait_file(r.PHONE / "ready.json", 35)
        else:
            r.live_network()
            require(dt.datetime.fromisoformat(r.read(r.PHONE / "ready.json")["deadline"]).timestamp() - time.time() > 2400,
                    "renew a closed private USB window before the next restoration")
            stop_completed_app(r, previous, r.cell(previous))
        tune = r.load("irq_screen_tune", SELF.with_name("baud_tune.py"))
        lock = r.load("irq_screen_lock", SELF.with_name("repeat_cycle.py"))
        with lock.device_lock():
            if previous is not None:
                label = "restore-for-" + run
                tune.tune(label, 115200, TARGET_VERSION)
                restore = r.load("irq_screen_restore", SELF.with_name("baud_restore.py"))
                restore.execute(label, AREA / "rates" / (label + ".json"))
            tune.tune(run, dict(CELLS)[run], BASE_VERSION)
        r.start(run, dict(CELLS)[run], "screen")
        result["result"] = "WAITING_FOR_USER_CONNECT_AND_DOWNLOAD"
    except Exception as error:
        result["error"] = type(error).__name__ + ": " + str(error)
    r.save(AREA / ("setup-" + run + ".json"), result)
    print(json.dumps(result), flush=True)
    return 0 if "error" not in result else 1


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("mode", choices=("assets", "recovery", "freeze", "launch", "setup-worker",
        "phone-worker", "network-worker", "capture-worker", "coordinate", "status", "close"))
    parser.add_argument("--run", choices=[name for name, _ in CELLS], default=CELLS[0][0])
    args = parser.parse_args()
    require(Path.cwd() == ROOT and sys.flags.isolated and sys.flags.no_site and sys.dont_write_bytecode,
            "isolated explicit project root required")
    checked(AREA)
    if args.mode == "assets":
        prepare_assets()
        return
    r = runtime()
    os.environ.update(r.environment())
    if args.mode == "recovery":
        r.load("irq_screen_restore_prepare", SELF.with_name("baud_restore.py")).prepare()
        return
    if args.mode == "freeze":
        freeze(r)
        return
    r.authority()
    if args.mode == "status":
        for path in (AREA / ("setup-" + args.run + ".json"), r.cell(args.run) / "status.json",
                     r.cell(args.run) / "coordinator-result.json", r.cell(args.run) / "mcu/state.json"):
            if path.exists():
                print(path.name, json.dumps(r.read(path)), flush=True)
        return
    if args.mode == "close":
        for path in (r.PHONE, r.NETWORK, r.cell(args.run)):
            if path.exists() and not (path / "stop.json").exists():
                r.save(path / "stop.json", dict(time=r.b.now(), reason="operator closes owned screening window"))
        return
    if args.mode == "launch":
        admit_next(r, args.run)
        r.save(AREA / ("launch-" + args.run + ".json"), dict(time=r.b.now(), plan=r.b.record(AREA / "plan.json")))
        print(json.dumps(r.launch_worker("setup-" + args.run, "setup-worker", 1800, args.run)), flush=True)
        return
    require(r.supervisor.owned.in_job(), "owned bounded worker required")
    if args.mode == "setup-worker":
        require(r.read(AREA / ("launch-" + args.run + ".json"))["plan"] == r.b.record(AREA / "plan.json"),
                "setup launch not bound to this plan")
        raise SystemExit(setup(r, args.run))
    if args.mode == "phone-worker":
        r.phone().server()
    elif args.mode == "network-worker":
        r.network_worker()
    elif args.mode == "capture-worker":
        lock = r.load("irq_screen_capture_lock", SELF.with_name("repeat_cycle.py"))
        with lock.device_lock():
            raise SystemExit(r.m.capture(args.run))
    else:
        r.coordinate(args.run)
        result = r.read(r.cell(args.run) / "coordinator-result.json")
        if result["result"] != "COMPLETED_RETAINED" and not (r.cell(args.run) / "stop.json").exists():
            r.save(r.cell(args.run) / "stop.json", dict(time=r.b.now(), reason="preserve unresolved outcome; no replay"))


if __name__ == "__main__":
    main()
