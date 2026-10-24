"""Finite P3-4 command entry. Hardware needs the actual frozen contract gate."""
import argparse
from datetime import datetime, timedelta, timezone
import hashlib
import json
import math
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

# Host observation limits, not BLE performance thresholds. The terminal phase
# reserves the existing 180 s Commander read, the App's full 180 s identity
# window, and 60 s for observation/teardown. Boot/readback retain their 300 s
# tool limits plus 45 s for process ownership/closure. Unused time is not slept.
PHONE_PHASE_SECONDS = dict(prepare=600, download=300, start=120, transfer=300,
    terminal=180 + 180 + 60, snapshot=300, boot=300 + 45,
    readback=300 + 45, archive=300)
PHONE_SALVAGE_SECONDS = 300
PHONE_CLOSE_SECONDS = 60
DEFAULT_PHONE_SECONDS = sum(PHONE_PHASE_SECONDS.values()) + PHONE_SALVAGE_SECONDS + PHONE_CLOSE_SECONDS


class StartNotices:
    """Thin operator adapter: send(kind, text, seconds) must verify its real receipt.

    Poll while the existing live process runs; an error withdraws its invitation,
    not its collectors. Inspect error only after collecting the live process exit.
    """
    START_TEXT = "\u624b\u673a\u7aef\u5347\u7ea7\u5305\u548c\u67e5\u8be2\u5df2\u6838\u5bf9\u3002\u8bf7\u5728 {expires_at} \u524d\u4ec5\u70b9\u4e00\u6b21\u5f00\u59cb BLE \u5347\u7ea7\uff08\u53d1\u4fe1\u65f6\u5269\u4f59 {remaining} \u79d2\uff09\u3002\u8fc7\u671f\u540e\u4e0d\u8981\u5f00\u59cb\uff1b\u5df2\u7ecf\u5f00\u59cb\u5219\u4fdd\u6301 App \u524d\u53f0\u3001\u4eae\u5c4f\u548c\u8fde\u63a5\uff0c\u7b49\u5f85\u5b8c\u6210\uff0c\u4e0d\u8981\u53d6\u6d88\u6216\u91cd\u8bd5\u3002\u65e0\u9700\u56de\u590d\u804a\u5929\u3002"
    EXPIRED_TEXT = "\u672c\u6b21\u5f00\u59cb\u9080\u8bf7\u5df2\u5931\u6548\u3002\u82e5\u5c1a\u672a\u5f00\u59cb\uff0c\u8bf7\u4e0d\u8981\u518d\u70b9\u5347\u7ea7\uff1b\u5982\u679c\u5df2\u7ecf\u5f00\u59cb\uff0c\u8bf7\u4fdd\u6301 App \u524d\u53f0\u3001\u4eae\u5c4f\u548c\u8fde\u63a5\uff0c\u8ba9\u672c\u6b21\u5347\u7ea7\u7ed3\u675f\uff0c\u4e0d\u8981\u53d6\u6d88\u3001\u91cd\u8bd5\u6216\u5207\u56de\u804a\u5929\u3002\u91c7\u96c6\u6b63\u5728\u6709\u754c\u6536\u5c3e\uff0c\u65e0\u9700\u56de\u590d\u3002"

    def __init__(self, out, package, send):
        self.out, self.package, self.send = h.checked(out), package, send
        self.error = None

    def _withdraw(self, reason):
        path = self.out / "start-withdrawn.json"
        if not path.exists():
            h.save(path, dict(reason=reason, monotonic=time.monotonic(), no_ota_cancel=True))

    def _send_once(self, kind, body, seconds, ready, *, deadline=None):
        intent = self.out / ("notice-" + kind + ".intent.json")
        if intent.exists():
            try:
                sent = self.out / ("notice-" + kind + ".sent.json")
                h.require(sent.is_file(), "previous notification result is unknown")
                receipt = h.read_json(sent)
                h.require(receipt.get("delivered") is True and h.pinned(receipt["intent"]) == intent.resolve(),
                          "previous notification delivery receipt is invalid")
            except Exception as error:
                self.error = error
                self._withdraw("previous notification outcome must not be retried")
            return  # Includes unknown outcomes: never resend an invitation.
        h.save(intent, dict(kind=kind, body=body, ready=h.record(ready),
            attempted_monotonic=time.monotonic(), seconds=seconds, no_chat_reply_required=True))
        if kind == "start":
            if time.monotonic() >= deadline:
                self._withdraw("start deadline reached before notification invocation")
                return
            if any((self.out / name).exists() for name in
                   ("start-observed.json", "start-expired.json", "start-withdrawn.json", "failed.json")):
                return
            seconds = min(seconds, deadline - time.monotonic())
        try:
            h.require(self.send(kind, body, seconds) is True, "notification delivery not confirmed")
            h.save(self.out / ("notice-" + kind + ".sent.json"),
                   dict(delivered=True, monotonic=time.monotonic(), intent=h.record(intent)))
        except Exception as error:
            self.error = error
            h.save(self.out / ("notice-" + kind + ".failed.json"),
                   dict(error_type=type(error).__name__, message=str(error), no_automatic_retry=True))
            self._withdraw("notification result missing or failed")

    def poll(self, *, owner_alive):
        h.require(type(owner_alive) is bool, "explicit live owner state required")
        ready_path = self.out / "start-ready.json"
        if not owner_alive or not ready_path.is_file():
            return
        expired = lambda: any((self.out / name).exists() for name in
            ("start-expired.json", "start-withdrawn.json", "failed.json"))
        if expired():
            return self._send_once("expired", self.EXPIRED_TEXT, 30, ready_path)
        if (self.out / "start-observed.json").exists():
            return
        try:
            ready = h.read_json(ready_path)
            phase_path = h.pinned(ready["phase"])
            h.require(phase_path == (self.out / "phase-start.json").resolve(), "foreign start phase")
            phase = h.read_json(phase_path)
            started, deadline = phase["started_monotonic"], phase["deadline_monotonic"]
            h.require(all(type(x) in (int, float) and math.isfinite(x) for x in (started, deadline)) and
                phase["phase"] == "start" and deadline > started and
                deadline - started == PHONE_PHASE_SECONDS["start"], "invalid original start boundary")
            state = ready["start_state"]
            h.require(type(ready["pid"]) is int and ready["pid"] > 0 and
                isinstance(ready["capture"], str) and bool(ready["capture"]) and
                isinstance(ready["run_id"], str) and bool(ready["run_id"]) and
                state == dict(pid=ready["pid"], capture=ready["capture"], run_id=ready["run_id"],
                              upgradeStarts=0, upgradeEnds=0) and
                type(state["upgradeStarts"]) is int and type(state["upgradeEnds"]) is int,
                "missing or mismatched explicit start state")
            h.require(datetime.fromisoformat(ready["expires_at"]).utcoffset() is not None,
                      "start expiry display needs an explicit timezone")
            for key, leaf in (("runtime", "runtime.json"), ("package", "downloaded.etu")):
                h.require(h.pinned(ready[key]) == (self.out / "phone" / leaf).resolve(),
                          "notification input belongs to another cell")
            h.require(all(ready["package"][k] == self.package[k] for k in ("bytes", "sha256")),
                      "notification package differs from reference")
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                self._withdraw("original start deadline reached")
            elif not expired() and not (self.out / "start-observed.json").exists():
                self._send_once("start", self.START_TEXT.format(expires_at=ready["expires_at"],
                    remaining=math.floor(remaining)), min(30, remaining), ready_path, deadline=deadline)
            if time.monotonic() >= deadline:
                self._withdraw("start invitation expired, including delivery time")
        except Exception as error:
            self.error = error
            self._withdraw("invalid start notification admission")
        if expired():
            self._send_once("expired", self.EXPIRED_TEXT, 30, ready_path)


class PhoneBudget:
    def __init__(self, phone, out):
        self.phone, self.out = phone, out
        self.phase, self.deadline, self.entered = None, None, set()

    def enter(self, phase):
        h.require(phase not in self.entered, "phone phase cannot be restarted: " + phase)
        now = time.monotonic()
        seconds = PHONE_SALVAGE_SECONDS if phase == "salvage" else PHONE_PHASE_SECONDS[phase]
        required = seconds + PHONE_CLOSE_SECONDS
        if phase != "salvage":
            required += PHONE_SALVAGE_SECONDS
        if phase in ("download", "start"):
            names = list(PHONE_PHASE_SECONDS)
            required += sum(PHONE_PHASE_SECONDS[name] for name in names[names.index(phase) + 1:])
        available = self.phone.deadline - now
        h.require(available >= required,
            "insufficient phone phase budget before %s: need %.1fs, have %.1fs; do not invite transfer" %
            (phase, required, available))
        self.phase, self.deadline = phase, now + seconds
        self.entered.add(phase)
        self.phone.operation_deadline = self.deadline
        h.save(self.out / ("phase-" + phase + ".json"), dict(phase=phase,
            started_monotonic=now, deadline_monotonic=self.deadline,
            lifetime_deadline_monotonic=self.phone.deadline, required_seconds=required,
            available_seconds=available, scope="host observation budget, not transfer timing or PASS"))

    def check(self):
        h.require(time.monotonic() < self.deadline,
            "phone %s phase deadline; preserve existing originals, no OTA replay" % self.phase)


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


def frozen_invocation(command, argv, *, entry="Tools/ota/p34-acceptance/live.py"):
    """Compare the full declared action, including parameters and output, not a substring."""
    tokens = shlex.split(command)
    h.require(len(tokens) >= 8 and tokens[1:7] == ["-I", "-S", "-B", "-X", "utf8", entry], "frozen isolated entry required")
    def normalized(parts):
        paths = {"--inputs", "--out", "--contract", "--matrix", "--observe-root", "--previous-cell",
                 "--previous-contract", "--previous-matrix"}
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
    budget = PhoneBudget(phone, out)
    error = None
    pid = capture = cfg = rtt = terminal_probe = None
    terminal_state = dict(attempted=False, captured=False)
    start_deadline = None
    try:
        budget.enter("prepare")
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
        origin = network.start(deadline=budget.deadline)
        budget.check()
        phone.start()
        package_path = "app_flutter/firmware/e-track-at32f435-v3.2.86-to-v3.2.87-patch.etu"
        previous_stamp = phone.file_stamp(package_path) if phone.exists(package_path) else None
        cfg = config(plan, args.run_id, origin, args.baud, args.timeout_ms)
        pid, capture = phone.provision(cfg, args.previous_cell)
        rtt = mcu.start_logger("base", "transfer")
        budget.check()
        budget.enter("download")
        h.save(out / "query-ready.json", dict(pid=pid, capture=capture, origin=origin,
            next_user_action="connect device, check/download in original firmware UI; do not start until start-ready.json"))
        print("P34_QUERY_READY " + str(out / "query-ready.json"), flush=True)
        h.wait_for(lambda: phone.downloaded(package_path, previous_stamp), PHONE_PHASE_SECONDS["download"], interval=1)
        budget.check()
        budget.enter("start")
        start_deadline = budget.deadline
        initial_health = phone.health(capture)
        budget.check()
        h.require(initial_health["healthy"] is True and
                  initial_health["upgradeStarts"] == initial_health["upgradeEnds"] == 0,
                  "transfer started before the start invitation")
        ready = dict(pid=pid, capture=capture, run_id=args.run_id,
            start_state=dict(pid=pid, capture=capture, run_id=args.run_id, upgradeStarts=0, upgradeEnds=0),
            phase=h.record(out / "phase-start.json"),
            expires_at=(datetime.now(timezone.utc) + timedelta(seconds=budget.deadline-time.monotonic())).astimezone().isoformat(timespec="seconds"),
            runtime=h.record(phone.out / "runtime.json"),
            package=h.record(phone.out / "downloaded.etu"), role=args.run_role, checkpoint_kib=args.checkpoint_kib,
            phase_budgets_seconds=PHONE_PHASE_SECONDS, salvage_seconds=PHONE_SALVAGE_SECONDS,
            close_seconds=PHONE_CLOSE_SECONDS,
            next_user_action="use StartNotices; invitation expires at the original phase deadline; never start after expiry")
        h.require(not (out / "start-ready.json").exists(), "start invitation already exists")
        h.host.io.write_json(h.ROOT, out / "start-ready.json", ready, replace=True)
        print("P34_START_READY " + str(out / "start-ready.json"), flush=True)
        decoded = None

        def mark_started(source):
            path = out / "start-observed.json"
            if not path.exists():
                observed = time.monotonic()
                h.save(path, dict(pid=pid, capture=capture, run_id=args.run_id, source=source,
                    monotonic=observed, within_start_window=observed < start_deadline,
                    scope="host observation, not an exact user tap timestamp"))

        def collectors_alive():
            h.require((decoded is not None or mcu.logger.alive()) and network.tunnel.alive(),
                      "collector/service exited; no OTA replay")

        def terminal_lines():
            data = rtt.read_bytes()
            lines = [line for line in data.splitlines(keepends=True) if line.startswith(b"P34_METRICS ") and line.endswith(b"\n")]
            h.require(len(lines) <= 1, "duplicate terminal metrics; wrong session/reader")
            return lines

        def terminal_ready():
            return not terminal_state["attempted"] and bool(terminal_lines())

        def terminal_capture():
            if budget.phase != "salvage":
                collectors_alive()
            if terminal_state["attempted"]:
                return None
            lines = terminal_lines()
            if not lines:
                return None
            terminal_state["attempted"] = True
            budget.check()
            raw_metrics = metrics.raw_from_rtt(lines[0])
            mark_started("MCU terminal publication")
            if budget.phase not in ("terminal", "salvage"):
                budget.enter("terminal")
            mcu.stop_logger()
            budget.check()
            # Preserve the single old-App RAM sample before repeatable semantic
            # decoding. Addresses come from the prebound ELF, never this record.
            mcu.transfer_snapshot(raw_metrics, deadline=budget.deadline)
            budget.check()
            terminal_state["captured"] = True
            return metrics.from_rtt(rtt.read_bytes())
        terminal_probe = terminal_capture
        while True:
            budget.check()
            h.require(not (out / "start-withdrawn.json").exists(), "start invitation withdrawn; preserve original outcome")
            if decoded is None:
                decoded = terminal_capture()
            try:
                health = phone.health(capture, terminal_ready=terminal_ready)
            except h.ObservationReady:
                continue
            budget.check()
            h.require(health.get("lost") == 0 and health.get("error") is None, "App observation failed; retrieve existing originals")
            starts, ends = health.get("upgradeStarts"), health.get("upgradeEnds")
            h.require(type(starts) is int and type(ends) is int and 0 <= ends <= starts <= 1,
                      "unexpected App upgrade count; preserve original capture")
            collectors_alive()
            if starts == 1:
                mark_started("App health checkpoint")
            if starts == 1 and budget.phase == "start":
                budget.enter("transfer")
            if starts == ends == 1:
                break
            time.sleep(min(.5, max(0, budget.deadline - time.monotonic())))
        if decoded is None:
            budget.enter("terminal")
            decoded = h.wait_for(terminal_capture, 45)
            budget.check()
        budget.enter("snapshot")
        value = phone.finished(pid, capture, cfg)
        budget.check()
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
            budget.enter("readback")
            mcu.inspect("base", "post-disconnect-readback")
        else:
            h.require(value["success"] and decoded["terminal"] == 0, "observed OTA failure; preserve originals")
            h.require(value["initialDurable"] == (args.checkpoint_kib * 1024 if args.run_role == "resume" else 0), "wrong zero/resume initial state")
            if args.run_role == "resume":
                h.require(previous["parameters"] == value["parameters"], "cross-parameter recovery pair")
            budget.enter("boot")
            mcu.wait_boot("target")
            budget.check()
            budget.enter("readback")
            mcu.inspect("target", "post-transfer-full-readback")
        budget.check()
        budget.enter("archive")
        phone.archive_capture()
        budget.check()
        h.save(out / "observations.json", dict(outcome="OBSERVATIONS_CAPTURED", statistics=h.record(phone.out / "statistics.json"),
            snapshot=h.record(phone.out / "snapshot.jsonl"), mcu_metrics=h.record(out / "metrics.json"),
            role=args.run_role, checkpoint_kib=args.checkpoint_kib, independent_acceptance=False))
    except BaseException as caught:
        error = caught
        drain_start = budget.phase in ("start", "transfer", "terminal") and terminal_probe is not None
        if (out / "start-ready.json").exists():
            h.save(out / "start-expired.json", dict(error_type=type(caught).__name__, message=str(caught),
                start_deadline_monotonic=start_deadline, observed_monotonic=time.monotonic(),
                no_new_start=True, no_ota_cancel=True, original_error_preserved=True))
            print("P34_START_EXPIRED " + str(out / "start-expired.json"), flush=True)
        try:
            budget.enter("salvage")
            if drain_start:
                # Expiry ends admission, not the observation of a possibly late OTA.
                # Do not reset the terminal budget or block it with bulk ADB reads.
                last_health, health_error, terminal_error = None, None, None
                complete = False
                while time.monotonic() < budget.deadline:
                    if not terminal_state["attempted"] and terminal_error is None:
                        try:
                            value = terminal_probe()
                            if value is not None:
                                h.save(out / "salvage-metrics.json", value)
                        except Exception as probe_error:
                            terminal_error = str(probe_error)
                    if time.monotonic() >= budget.deadline:
                        break
                    if health_error is None:
                        try:
                            last_health = phone.health(capture, terminal_ready=terminal_ready if terminal_error is None else None)
                            budget.check()
                            starts, ends = last_health["upgradeStarts"], last_health["upgradeEnds"]
                            h.require(type(starts) is int and type(ends) is int and 0 <= ends <= starts <= 1,
                                      "unknown late-upgrade state")
                            if starts:
                                mark_started("App health checkpoint during failure drain")
                            if terminal_error is None and terminal_ready():
                                continue
                            if starts == ends == 1:
                                complete = True
                                break
                        except h.ObservationReady:
                            continue
                        except Exception as read_error:
                            health_error = str(read_error)
                    time.sleep(min(.5, max(0, budget.deadline-time.monotonic())))
                retrieved = False
                try:
                    if complete and time.monotonic() < budget.deadline:
                        phone.salvage()
                        budget.check()
                        receipt = phone.out / "salvage.json"
                        if receipt.is_file():
                            saved = h.read_json(receipt)
                            retrieved = bool(saved.get("originals")) and not saved.get("errors")
                finally:
                    h.save(out / "start-drain.json", dict(deadline_monotonic=budget.deadline,
                        ended_monotonic=time.monotonic(), last_health=last_health,
                        health_error=health_error, terminal_error=terminal_error, terminal=dict(terminal_state),
                        complete_observed=complete, original_error_preserved=True,
                        no_restart_or_ota=True, pending_phone_retrieval=not retrieved,
                        retained_files_require_strict_verification=True))
                # Otherwise all existing ADB stdout and RTT remain original evidence;
                # retrieving phone files later never authorizes another transfer.
            else:
                phone.salvage()
                budget.check()
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
    parser.add_argument("--seconds", type=int, default=DEFAULT_PHONE_SECONDS,
                        help="finite owner lifetime; phone readiness reserves all remaining phases (default: %(default)s)")
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
