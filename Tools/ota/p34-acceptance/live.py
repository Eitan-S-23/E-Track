"""Finite P3-4 command entry. Hardware needs the actual frozen contract gate."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import secrets
import shlex
import sys
import time

sys.path.insert(0, str(Path(__file__).resolve().parent))
import live_host as h
from live_mcu import MCU
from live_phone import Network, Phone, config, acceptance_stats, observation_capture
import metrics

COMMON_RUNNERS = ["Tools/ota/p34-acceptance/live.py", "Tools/ota/p34-acceptance/live_host.py",
    "Tools/ota/p34-acceptance/live_mcu.py", "Tools/ota/p34-acceptance/live_phone.py",
    "Tools/ota/p34-acceptance/build.py", "Tools/flutter/dev_checks.py",
    ".agents/skills/e-track-flutter-debug/scripts/host_io.py",
    "Tools/ota/p3-3-service/service.py", "Tools/ota/p34-acceptance/metrics.py",
    "Tools/ota/p3-4-link-stats/acceptance_stats.py", "Tools/ota/p3-4-link-stats/observation_capture.py",
    "Tools/ota/p3-4-link-stats/batch_timing.py", "Tools/acceptance/validate_bundle.py",
    "Tools/provenance/manifest_profiles.json"]


def validate_inputs(plan):
    h.require(plan.get("schema") == 1 and plan.get("device") == "C30286", "wrong task/device input")
    h.require(plan.get("phone_serial") == "10ADA4197U001CK" and plan.get("phone_model") == "V2312A" and
        plan.get("ble_address") == "E3:49:E1:14:D6:CB" and plan.get("app_id") == "com.wen.gaia.gaia.p34probe",
        "device scope expansion is not authorized")
    h.require(plan.get("adb_port") == 5062 and str(plan.get("probe_serial")) == "123456", "wrong private tool binding")
    h.require(re.fullmatch(r"OTAOBS[0-9a-f]{24}", plan.get("sentinel", "")), "APK sentinel")
    for name in ("commander", "rttlogger", "nm", "objdump", "objcopy", "adb", "cloudflared", "python", "git"):
        h.pinned(plan["tools"][name])
    h.require(h.pinned(plan["tools"]["python"]) == Path(sys.executable).resolve(), "wrong interpreter")
    companions = {h.pinned(item) for item in plan["tool_dependencies"]}
    required_dlls = [h.pinned(plan["tools"]["commander"]).parent / "JLinkARM.dll",
                     *(h.pinned(plan["tools"]["adb"]).parent / name for name in ("AdbWinApi.dll", "AdbWinUsbApi.dll"))]
    h.require({path.resolve() for path in required_dlls} <= companions, "unbound tool companion DLL")
    h.require(plan["boot"]["bytes"] == 65536 and plan["boot"]["sha256"] ==
        "01e4b9e162bfaaf9fda070aa13c0cec3f377b8d696db01f731e0ab3d1464e527", "group16 Boot binding")
    for name in ("boot", "package", "apk", "apk_metadata", "adb_key"):
        h.pinned(plan[name])
    h.pinned(plan["source_lock"])
    apk = h.read_json(h.pinned(plan["apk_metadata"]))
    h.require(apk.get("sha256") == plan["apk"]["sha256"] and apk.get("bytes") == plan["apk"]["bytes"] and
        apk.get("application_id") == plan["app_id"] and apk.get("device_observation", {}).get("sentinel") == plan["sentinel"] and
        apk["device_observation"].get("target") == plan["ble_address"] and
        apk.get("requested_ota_link_candidate", {}).get("runtime_config") is True, "APK/runtime/sentinel binding")
    h.require(plan["package"]["bytes"] == 1048576 and plan["package"]["sha256"] ==
        "8373305b6817081106ad35c840ef87bf2d4210ffa2e8b9e881e0799ad1ff9e47", "unchanged reference ETU required")
    h.require(set(plan["images"]) == {"initial", "base", "target", "maintenance", "restore"}, "image roles incomplete")
    for role, item in plan["images"].items():
        for name in ("image", "elf", "map"):
            h.pinned(item[name])
        h.require(0x460 <= item["image"]["bytes"] <= 0xf0000, "image crosses App bounds")
    base = h.pinned(plan["images"]["base"]["image"]).read_bytes()
    target = h.pinned(plan["images"]["target"]["image"]).read_bytes()
    h.require(len(base) == len(target) == 613952 and base[:0x400] == target[:0x400] and
        base[0x460:] == target[0x460:], "base/target executable or RAM layout changed")
    h.require(plan["images"]["base"]["image"]["sha256"] ==
        "9b3a4a21409c59b916976385ec877b7d90bd7e4c90b3553f0b8df2b02fd787dc" and
        plan["images"]["target"]["image"]["sha256"] ==
        "58eebd962ba1b39369f85954a167516ec5f5e519c5d894c3db5eb0edccea76a1", "selected reference images changed")
    h.require(isinstance(plan.get("owned_configs"), list) and isinstance(plan.get("replace_apk_sha256"), list), "explicit prior App ownership required")
    for digest in plan["owned_configs"] + plan["replace_apk_sha256"]:
        h.require(isinstance(digest, str) and re.fullmatch(r"[0-9a-f]{64}", digest), "invalid prior ownership hash")
    return plan


def frozen_invocation(command, argv):
    """Compare the full declared action, including parameters and output, not a substring."""
    tokens = shlex.split(command)
    entry = "Tools/ota/p34-acceptance/live.py"
    h.require(len(tokens) >= 8 and tokens[1:7] == ["-I", "-S", "-B", "-X", "utf8", entry], "frozen isolated entry required")
    def normalized(parts):
        paths = {"--inputs", "--out", "--contract", "--matrix", "--observe-root", "--previous-cell"}
        result = list(parts)
        for i, part in enumerate(result[:-1]):
            if part in paths:
                result[i + 1] = str((h.ROOT / result[i + 1]).resolve()).lower() if os.name == "nt" else str((h.ROOT / result[i + 1]).resolve())
        return result
    h.require(normalized(tokens[7:]) == normalized(argv[1:]), "actual arguments differ from the frozen command")


def contract_gate(args, out, plan=None):
    h.require(args.contract and args.matrix and args.command_id, "hardware requires actual contract/matrix/command ID")
    contract = h.read_json(args.contract)
    h.require(contract.get("task_id") == "P3-4" and contract.get("status") == "FROZEN" and
        contract.get("approved_by") and contract.get("approved_at"), "no approved frozen P3-4 contract")
    commands = [c for c in contract["commands"] if c["id"] == args.command_id]
    h.require(len(commands) == 1 and set(COMMON_RUNNERS) <= set(commands[0].get("runner_paths", [])),
              "actual command has undeclared transitive runners")
    frozen_invocation(commands[0]["command"], sys.argv)
    digest = hashlib.sha256(args.inputs.read_bytes()).hexdigest()
    h.require(any(x.get("fingerprint") == "sha256:" + digest for x in contract.get("external_inputs", [])),
              "live input file is not an external input of this contract")
    env = h.environment(out)
    if plan is not None:
        env["PATH"] = str(h.pinned(plan["tools"]["git"]).parent) + os.pathsep + env.get("PATH", "")
    h.command(out, "contract-precheck", [sys.executable, "-I", "-S", "-B", "-X", "utf8",
        h.ROOT / "Tools/acceptance/validate_bundle.py", "--contract", args.contract,
        "--matrix", args.matrix, "--repo-root", h.ROOT], env, seconds=90)


def phone_cell(plan, out, args):
    mcu = MCU(plan, h.fresh(out / "mcu"))
    network = Network(plan, out / "network")
    phone = Phone(plan, out / "phone", args.seconds)
    error = None
    try:
        before = mcu.inspect("base", "pre-transfer-current-boot")
        h.require(args.run_role in ("clean", "soak", "disconnect", "resume"), "unplanned phone role")
        h.require(args.run_role not in ("disconnect", "resume") or
            args.checkpoint_kib in (8, 64, 256, 512, 768), "recovery checkpoint required")
        h.require(before["storage"]["journal"]["expected_begin_durable"] ==
            (args.checkpoint_kib * 1024 if args.run_role == "resume" else 0), "wrong reference starting journal")
        if args.run_role == "resume":
            h.require(args.previous_cell is not None, "resume needs its original disconnect cell")
            previous = h.read_json(args.previous_cell / "phone/statistics.json")
            h.require(previous.get("failure", {}).get("stage") == "transfer" and
                previous["failure"].get("reason") in ("transport:DISCONNECTED", "transport:DEVICE_LINK_CHANGED") and
                previous.get("finalDurable") == args.checkpoint_kib * 1024, "missing actual checkpoint disconnect")
        origin = network.start()
        phone.start()
        package_path = "app_flutter/firmware/e-track-at32f435-v3.2.86-to-v3.2.87-patch.etu"
        previous_stamp = phone.file_stamp(package_path) if phone.exists(package_path) else None
        cfg = config(plan, args.run_id, origin, args.baud, args.timeout_ms)
        pid, capture = phone.provision(cfg, args.previous_cell)
        rtt = mcu.start_logger("base", "transfer")
        h.save(out / "query-ready.json", dict(pid=pid, capture=capture, origin=origin,
            next_user_action="connect device, check/download in original firmware UI; do not start until start-ready.json"))
        print("P34_QUERY_READY " + str(out / "query-ready.json"), flush=True)
        h.wait_for(lambda: phone.downloaded(package_path, previous_stamp), min(300, args.seconds - 450), interval=1)
        h.save(out / "start-ready.json", dict(pid=pid, capture=capture, runtime=h.record(phone.out / "runtime.json"),
            package=h.record(phone.out / "downloaded.etu"), role=args.run_role, checkpoint_kib=args.checkpoint_kib,
            next_user_action="tap Start BLE transfer once in the original UI; any physical fault follows the frozen operator command"))
        print("P34_START_READY " + str(out / "start-ready.json"), flush=True)
        deadline = time.monotonic() + min(300, phone.deadline - time.monotonic() - 150)
        decoded = None
        def terminal_capture():
            data = rtt.read_bytes()
            lines = [line for line in data.splitlines(keepends=True) if line.startswith(b"P34_METRICS ") and line.endswith(b"\n")]
            if not lines:
                return None
            h.require(len(lines) == 1, "duplicate terminal metrics; wrong session/reader")
            mcu.stop_logger()
            result = metrics.from_rtt(rtt.read_bytes())
            mcu.transfer_snapshot(bytes.fromhex(lines[0].strip()[12:].decode("ascii")))
            return result
        while time.monotonic() < deadline:
            if decoded is None:
                decoded = terminal_capture()
            health = phone.health(capture)
            h.require(health.get("lost") == 0 and health.get("error") is None, "App observation failed; retrieve existing originals")
            if health.get("upgradeStarts") == health.get("upgradeEnds") == 1:
                break
            h.require((decoded is not None or mcu.logger.alive()) and network.tunnel.alive(), "collector/service exited; no OTA replay")
            time.sleep(.5)
        else:
            raise RuntimeError("App observation deadline; collect existing snapshot before any new action")
        value = phone.finished(pid, capture, cfg)
        if decoded is None:
            decoded = h.wait_for(terminal_capture, 45)
        _, messages = observation_capture.verify((phone.out / "snapshot.jsonl").read_bytes(),
            sentinel=plan["sentinel"], target=plan["ble_address"])
        begins = [line for line in messages.splitlines() if " kind=begin_ack " in line]
        h.require(begins, "missing actual App BEGIN binding")
        epoch = int(re.search(r"\bepoch=(\d+)", begins[0])[1])
        h.require(decoded["epoch"] == epoch and decoded["total_len"] == 1048576 and
            decoded["package_sha256"] == plan["package"]["sha256"] and
            abs(decoded["uart_baud_actual"] - args.baud) <= args.baud // 33, "MCU/App session or baud mismatch")
        h.save(out / "metrics.json", decoded)
        if args.run_role == "disconnect":
            h.require(not value["success"] and value.get("failure", {}).get("stage") == "transfer" and
                value["failure"].get("reason") in ("transport:DISCONNECTED", "transport:DEVICE_LINK_CHANGED") and
                value["finalDurable"] == args.checkpoint_kib * 1024 and decoded["terminal"] == 1,
                "not the planned actual disconnect; ABORT/cancellation does not qualify")
            mcu.inspect("base", "post-disconnect-readback")
        else:
            h.require(value["success"] and decoded["terminal"] == 0, "observed OTA failure; preserve originals")
            h.require(value["initialDurable"] == (args.checkpoint_kib * 1024 if args.run_role == "resume" else 0), "wrong zero/resume initial state")
            if args.run_role == "resume":
                h.require(previous["parameters"] == value["parameters"], "cross-parameter recovery pair")
            mcu.wait_boot("target")
            mcu.inspect("target", "post-transfer-full-readback")
        phone.archive_capture()
        h.save(out / "observations.json", dict(outcome="OBSERVATIONS_CAPTURED", statistics=h.record(phone.out / "statistics.json"),
            snapshot=h.record(phone.out / "snapshot.jsonl"), mcu_metrics=h.record(out / "metrics.json"),
            role=args.run_role, checkpoint_kib=args.checkpoint_kib, independent_acceptance=False))
    except BaseException as caught:
        error = caught
        try:
            phone.salvage()
        except BaseException as salvage_error:
            h.save(out / "salvage-failed.json", dict(error=str(salvage_error)))
    finally:
        for close in (mcu.stop_logger, phone.close, network.close):
            try:
                close()
            except BaseException as caught:
                if error is None:
                    error = caught
    if error is not None:
        raise error


def soak_clock(out, observed_root, seconds):
    """One host process records elapsed time and observed action/idle intervals."""
    h.require(1 <= seconds <= 18000 and observed_root.is_dir(), "bounded existing campaign required")
    path = h.checked(out / "monotonic.jsonl")
    h.require(out != observed_root and not observed_root.is_relative_to(out), "observer cannot watch itself")
    names = ("intent.json", "result.json", "failed.json", "start-ready.json")
    files = lambda: sorted({item for name in names for item in observed_root.glob("*/" + name) if item.parent != out})
    seen = {str(p.resolve()): None for p in files()}
    start, last = time.monotonic_ns(), 0
    clock_id, observed, max_gap = secrets.token_hex(16), 0, 0
    with path.open("x", encoding="utf-8", newline="\n") as stream:
        def emit(kind, **fields):
            event = dict(schema=1, kind=kind, pid=os.getpid(), clock_id=clock_id,
                         elapsed_ns=time.monotonic_ns()-start, **fields)
            stream.write(json.dumps(event, sort_keys=True) + "\n")
            stream.flush()
            return event
        emit("start", planned_seconds=seconds, clock=time.get_clock_info("monotonic").implementation,
             baseline=seen)
        while (time.monotonic_ns()-start) / 1e9 < seconds:
            for item in files():
                h.checked(item)
                identity, raw = str(item.resolve()), item.read_bytes()
                try:
                    json.loads(raw)
                except (ValueError, UnicodeError):
                    emit("incomplete_original", path=identity)
                    continue
                digest = hashlib.sha256(raw).hexdigest()
                if identity in seen:
                    h.require(seen[identity] is None or seen[identity] == digest, "observed original changed")
                    seen[identity] = digest
                else:
                    emit("action_observed", original=dict(path=str(item.relative_to(h.ROOT)), bytes=len(raw), sha256=digest))
                    seen[identity] = digest
                    observed += 1
            now = time.monotonic_ns()-start
            max_gap = max(max_gap, now-last)
            emit("heartbeat", observed_actions=observed, gap_ns=now-last)
            last = now
            time.sleep(min(1, max(0, seconds-(time.monotonic_ns()-start)/1e9)))
        stop = emit("stop", observed_actions=observed, gap_ns=time.monotonic_ns()-start-last)
        max_gap = max(max_gap, stop["gap_ns"])
    h.save(out / "clock-result.json", dict(log=h.record(path), elapsed_seconds=stop["elapsed_ns"]/1e9,
        observed_actions=observed, max_heartbeat_gap_ns=max_gap, independent_acceptance=False,
        scope="Observer-monotonic duration including idle; not summed App times or a soak PASS. Inspect gaps/actions in the raw log."))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=("validate", "inspect", "install", "baud", "restore", "install-apk", "phone", "clock"))
    parser.add_argument("--inputs", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--role", choices=("initial", "base", "target", "maintenance"), default="base")
    parser.add_argument("--install-role", choices=("base", "maintenance"), default="base")
    parser.add_argument("--baud", type=int, choices=(115200, 230400, 460800, 921600), default=921600)
    parser.add_argument("--timeout-ms", type=int, default=2000)
    parser.add_argument("--run-id", default="p34-qualified-run")
    parser.add_argument("--run-role", choices=("clean", "soak", "disconnect", "resume"), default="clean")
    parser.add_argument("--checkpoint-kib", type=int, choices=(8, 64, 256, 512, 768))
    parser.add_argument("--previous-cell", type=Path)
    parser.add_argument("--seconds", type=int, default=900)
    parser.add_argument("--observe-root", type=Path)
    parser.add_argument("--contract", type=Path)
    parser.add_argument("--matrix", type=Path)
    parser.add_argument("--command-id")
    args = parser.parse_args()
    h.require(Path.cwd() == h.ROOT and sys.flags.isolated and sys.flags.no_site and sys.dont_write_bytecode,
              "explicit candidate cwd and Python -I -S -B required")
    h.require(750 <= args.seconds <= 18000, "keep transfer/apply/cleanup allowance; finite upper bound")
    plan = validate_inputs(h.read_json(args.inputs))
    out = h.fresh(args.out)
    h.save(out / "intent.json", dict(action=args.action, inputs=h.record(args.inputs),
        argv=sys.argv, started_monotonic_ns=time.monotonic_ns(), formal_acceptance=False))
    device_attempted = False
    try:
        if args.action == "validate":
            mcu = MCU(plan, h.fresh(out / "mcu"))
            for role in plan["images"]:
                mcu.bind(role)
            h.save(out / "result.json", dict(runner_paths=COMMON_RUNNERS, device_operations=0, formal_freeze=False))
            return
        contract_gate(args, out, plan)
        if args.action == "clock":
            h.require(args.observe_root is not None, "explicit observed campaign root")
            soak_clock(out, h.checked(args.observe_root), args.seconds)
            return
        with h.device_owner(out, read_only=args.action == "inspect"):
            device_attempted = True
            if args.action == "phone":
                phone_cell(plan, out, args)
            elif args.action == "install-apk":
                phone = Phone(plan, out / "phone", args.seconds)
                try:
                    phone.install()
                finally:
                    phone.close()
            else:
                mcu = MCU(plan, h.fresh(out / "mcu"))
                try:
                    if args.action == "inspect":
                        mcu.inspect(args.role)
                    elif args.action == "install":
                        mcu.install(args.role, args.install_role)
                    elif args.action == "baud":
                        mcu.baud(args.baud)
                    elif args.action == "restore":
                        mcu.restore()
                finally:
                    mcu.stop_logger()
        h.save(out / "result.json", dict(action=args.action, tool_operations_completed=True,
            independent_acceptance=False, ended_monotonic_ns=time.monotonic_ns(),
            **(dict(phone_capture=h.record(out / "phone/closed-capture.json"),
                    phone_closed=h.record(out / "phone/closed.json"),
                    network_closed=h.record(out / "network/closed.json")) if args.action == "phone" else {})))
    except BaseException as error:
        h.save(out / "failed.json", dict(error_type=type(error).__name__, message=str(error),
            unknown_outcome_requires_reconciliation=device_attempted, device_attempted=device_attempted,
            no_automatic_retry=True))
        raise


if __name__ == "__main__":
    main()
