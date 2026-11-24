"""Preserve a foreground durable timeout and reconcile it without device writes."""
from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import re
import runpy
import shlex
import struct
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[2]
SELF = Path(__file__).resolve()
PARENT = SELF.with_name("baud_interruption.py")
FIXTURE = SELF.with_name("baud_session_layout.c")
FIELDS = ("state", "session_id", "next_session_id", "expected_seq", "total_len",
          "package_sha256", "target_vcode", "pkg_kind", "durable_off", "segment_bitmap",
          "resumed", "complete", "last_frame_ms", "last_data_ms", "last_liveness_ms",
          "last_ack_cmd", "last_ack_seq", "receiver", "isr_active", "tx_frame", "parser_bad_frames")
prior = runpy.run_path(str(PARENT), run_name="durable_failure_primitives")
require = prior["require"]


def runtime():
    return runpy.run_path(str(SELF.with_name("baud_foreground.py")),
                         run_name="durable_failure_runtime")["runtime"]()


def classify(records, timeout_ms):
    value = prior["classify"](records, timeout_ms)
    require(value["statistics"]["failure"] == dict(stage="transfer", reason="transport:NO_DURABLE_PROGRESS"),
            "not a durable timeout")
    start = next(i for i, item in enumerate(records) if item.get("kind") == "upgrade-start")
    end = next(i for i, item in enumerate(records) if item.get("kind") == "upgrade-end")
    lines = [item["message"] for item in records[start+1:end] if item.get("kind") == "line"]
    require(not any(line.startswith("OTA_MONO MONO_PAUSE ") for line in lines),
            "foreground diagnosis cannot include an in-transfer pause")
    resets, failures = [], []
    for line in lines:
        match = re.fullmatch(r"OTA_MONO MONO_BUDGET_RESET monoUs=(\d+) wallUs=\d+ durable=(\d+)", line)
        if match:
            resets.append((int(match[1]), int(match[2])))
        match = re.fullmatch(r"OTA_MONO MONO_FAIL_AT monoUs=(\d+) wallUs=\d+ code=NO_DURABLE_PROGRESS", line)
        if match:
            failures.append(int(match[1]))
    require(resets and len(failures) == 1 and resets[-1][1] == value["durable_off"],
            "missing or inconsistent final budget boundary")
    elapsed = failures[0]-resets[-1][0]
    require(elapsed >= timeout_ms*1000, "durable deadline not reached")
    value.update(result="FOREGROUND_NO_DURABLE_PROGRESS", idle_us=elapsed,
                 root_cause="UNPROVEN; distinguish receive loss from recovery starvation")
    return value


def terminated_runs(events):
    runs = []
    for event in events:
        if event.get("kind") != "rtt-line":
            continue
        match = re.fullmatch(r"P34PERF: ready run=(\d+) bytes=(\d+) terminal=1 size=288\r?\n", event["line"])
        if match:
            runs.append(dict(run=int(match[1]), total_len=int(match[2]), time=event["time"]))
    require(runs and [item["run"] for item in runs] == list(range(1, len(runs)+1)),
            "missing or ambiguous internal MCU sessions")
    return runs


def decode_layout(data):
    require(len(data) == (3+2*len(FIELDS))*4, "layout table length")
    words = struct.unpack("<"+"I"*(len(data)//4), data)
    require(words[0] == 0x50334C59 and words[2] == len(FIELDS) and 0 < words[1] <= 1024,
            "layout table identity/size")
    members = {name: dict(offset=words[3+2*i], size=words[4+2*i]) for i, name in enumerate(FIELDS)}
    require(all(0 < m["size"] and m["offset"]+m["size"] <= words[1] for m in members.values()),
            "layout member outside session")
    require(members["package_sha256"]["size"] == 32 and members["expected_seq"]["size"] == 2 and
            all(members[name]["size"] in (1, 2, 4) for name in FIELDS if name not in ("package_sha256", "tx_frame")),
            "layout member type mismatch")
    return dict(size=words[1], members=members)


def decode_session(data, layout):
    require(len(data) == layout["size"], "session read length")
    result = {}
    for name, member in layout["members"].items():
        raw = data[member["offset"]:member["offset"]+member["size"]]
        result[name] = raw.hex() if name in ("package_sha256", "tx_frame") else int.from_bytes(raw, "little")
    return result


def profile_record(r, data, run, total, baud):
    require(len(data) == 288, "profile read length")
    words = struct.unpack("<72I", data)
    value = dict(zip(r.m.HEADERS, words[:24]))
    require(tuple(value[k] for k in ("magic", "schema", "size", "ready", "active", "terminal")) ==
            (0x50334250, 1, 288, 1, 0, 1), "not a terminated internal session")
    require(value["run"] == run and value["total_len"] == total and value["retained_baud"] == baud and
            r.m.actual_baud_matches(baud, value["uart_baud_actual"]), "current profile/session identity changed")
    value["phases"] = {name: dict(zip(r.m.PHASE_FIELDS, words[24+i*6:30+i*6]))
                       for i, name in enumerate(r.m.PHASES)}
    return value


def source_records(r):
    return [r.b.record(p) for p in (SELF, PARENT, FIXTURE, SELF.with_name("test_baud_durable_failure.py"))]


def make_layout(r, destination):
    destination = r.b.checked(destination)
    require(not destination.exists(), "preserve layout probe")
    names = ("layout.o", "layout.su", "layout.bin", "compile.stdout", "compile.stderr",
             "objcopy.stdout", "objcopy.stderr", "result.json")
    for name in names:
        r.b.checked(destination/name)
    database = r.b.OUT/"build/compile_commands.json"
    entries = [e for e in r.read(database) if e["file"].endswith("ota_ble_session.c") and
               "X_Track_App_GCC.dir" in e["command"]]
    require(len(entries) == 1, "exact running-image C command missing")
    args = shlex.split(entries[0]["command"], posix=False)
    require(all('"' not in arg for arg in args) and args.count("-o") == args.count("-c") == 1 and
            args[-2:] == ["-c", str(Path(entries[0]["file"]))] and
            not any(arg in ("-MD", "-MMD", "-MF", "-save-temps") for arg in args), "unsupported compiler outputs")
    args[args.index("-o")+1], args[-1] = str(destination/"layout.o"), str(FIXTURE)
    env = r.environment()
    destination.mkdir(parents=True)
    commands = [args, [str(Path(args[0]).with_name("arm-none-eabi-objcopy.exe")), "-O", "binary",
                       "--only-section=.rodata.p34_session_layout", str(destination/"layout.o"),
                       str(destination/"layout.bin")]]
    for name, command in zip(("compile", "objcopy"), commands):
        result = subprocess.run(command, cwd=ROOT, env=env, capture_output=True, timeout=45,
                                creationflags=subprocess.CREATE_NO_WINDOW)
        r.raw(destination/(name+".stdout"), result.stdout)
        r.raw(destination/(name+".stderr"), result.stderr)
        require(result.returncode == 0, name+" failed; inspect preserved output")
    layout = decode_layout((destination/"layout.bin").read_bytes())
    r.save(destination/"result.json", dict(layout=layout, commands=commands,
        inputs=[r.b.record(p) for p in (database, FIXTURE, Path(entries[0]["file"]),
                r.a.FW/"Libraries/OTA/ota_ble_session.h", r.a.FW/"Libraries/OTA/ota_staging.h")],
        table=r.b.record(destination/"layout.bin"), firmware_rebuilt=False, hardware=False))
    return layout


def analyze(r, run):
    out, config = prior["context"](r, run)
    destination = r.b.checked(out/"failure/durable.json")
    require(not destination.exists(), "preserve failure analysis")
    obs = r.apk()["metadata"]["device_observation"]
    parser = r.load("durable_failure_envelope", r.b.SRC/"Tools/ota/p3-4-link-stats/observation_capture.py")
    raw = (out/"finished/snapshot.jsonl").read_bytes()
    capture, messages = parser.verify(raw, sentinel=obs["sentinel"], target=r.TARGET)
    expected = r.read(config["runtime_config"]["path"])
    require(all(capture["input"][key] == expected[key] for key in
                ("packageSha256", "packageBytes", "currentVersionCode", "targetVersionCode",
                 "currentImageSha256", "targetImageSha256")), "failed invocation input drift")
    r.experiment_line(messages, config)
    result = classify([json.loads(line) for line in raw.splitlines()], 30000)
    runs = terminated_runs([json.loads(line) for line in (out/"mcu/events.jsonl").read_bytes().splitlines()])
    require(all(item["total_len"] == expected["packageBytes"] for item in runs), "internal session input drift")
    profile = profile_record(r, (out/"mcu/profile.bin").read_bytes(), runs[0]["run"],
                             expected["packageBytes"], config["baud"])
    result.update(time=r.b.now(), run=run, sources=source_records(r), runtime_sources=r.sources(),
                  capture=capture, first_internal_profile=profile, internal_sessions=runs,
                  originals=[r.b.record(out/name) for name in ("config.json", "finished/snapshot.jsonl",
                             "mcu/events.jsonl", "mcu/result.json", "mcu/profile.bin")],
                  full_post_failure_readback="REQUIRED")
    r.b.checked(r.RUNTIME/"actions.jsonl")
    r.save(destination, result)
    r.event("durable-timeout-analysis", "failed", run=run, receipt=r.b.record(destination))
    return result


def readback(r, run):
    out, config = prior["context"](r, run)
    b, m, c = r.b, r.m, r.m.c
    require(r.supervisor.owned.in_job(), "owned bounded worker required")
    m.native_authority()
    analysis_path, layout_path = out/"failure/durable.json", out/"failure/layout/result.json"
    analysis, layout_record = r.read(analysis_path), r.read(layout_path)
    require(analysis["sources"] == source_records(r) and analysis["runtime_sources"] == r.sources() and
            analysis["result"] == "FOREGROUND_NO_DURABLE_PROGRESS", "analysis binding changed")
    require(all(b.record(item["path"]) == item for item in analysis["originals"]+layout_record["inputs"]+
                [layout_record["table"]]), "original failure/layout inputs changed")
    layout = decode_layout(Path(layout_record["table"]["path"]).read_bytes())
    require(layout == layout_record["layout"], "layout receipt drift")
    group, bindings = config["assets"], m.load_bindings()
    profile = bindings["profiles"][str(group["baseline_identity"]["version_code"])]
    for item in (group["baseline"], group["package"], profile["map"], bindings["whole_boot"]):
        require(b.record(item["path"]) == item, "readback input changed")
    expected = Path(group["baseline"]["path"]).read_bytes()
    package = Path(group["package"]["path"]).read_bytes()
    boot = Path(bindings["whole_boot"]["path"]).read_bytes()
    map_text = Path(profile["map"]["path"]).read_text(encoding="utf-8")
    addresses = dict(bcb_state=m.map_bss(map_text, "_ZL20g_ota_state_snapshot", 1),
                     confirm_done=m.map_bss(map_text, "_ZL18g_ota_confirm_done", 1),
                     state_snapped=m.map_bss(map_text, "_ZL19g_ota_state_snapped", 1),
                     health=m.map_bss(map_text, "_ZL12g_ota_health", 36),
                     session=m.map_bss(map_text, "_ZL13s_ble_session", layout["size"]))
    destination = b.checked(out/"failure/readback")

    class Evidence(c.Evidence):
        NAMES = (*c.Evidence.NAMES, "boot-region.bin", "staging-journal.bin", "staging-prefix.bin",
                 "profile.bin", "session.bin", "state-before.json", "state-after.json")

    for name in Evidence.NAMES:
        b.checked(destination/name)
    b.checked(r.RUNTIME/"actions.jsonl")
    for key in ("HOME", "USERPROFILE", "APPDATA", "LOCALAPPDATA", "TEMP", "TMP", "TMPDIR"):
        require(key in os.environ, "missing contained environment: "+key)
        b.checked(Path(os.environ[key]))
    evidence = Evidence(destination)
    link = m.BoundLink(evidence, writable=False)
    result = dict(started=b.now(), run=run, sources=source_records(r), analysis=b.record(analysis_path),
                  result="READBACK_INCOMPLETE", flash=0, reset=0, at=0, target_memory_writes=0,
                  native_history_before=c.record(c.MRU), independent_acceptance=False)

    def read(address, size):
        return m.read_region(link, address, size)

    def state(name):
        symbols = profile["symbols"]
        value = dict(time=b.now(), vtor=m.u32(read(0xE000ED08, 4)),
                     sd_ready=read(symbols["sd_ready"], 1)[0],
                     health_words=struct.unpack("<9I", read(addresses["health"], 36)),
                     backup_word=m.u32(read(m.ERTC_DT20, 4)))
        value.update({key: read(addresses[key], 1)[0] for key in ("bcb_state", "confirm_done", "state_snapped")})
        value.update({key: m.u32(read(symbols[key], 4)) for key in
                      ("tick", "boot_baud", "retained_word", "retention_error")})
        evidence.save(name, value)
        return value

    try:
        link.connect()
        require(link.read(c.APP, 0x460) == expected[:0x460], "not the expected retained baseline")
        result["before"] = state("state-before.json")
        actual = m.base.read_image(link, len(expected))
        result["image"] = r.raw(destination/"image.bin", actual)
        require(actual == expected, "full retained App mismatch")
        link.command("ExcludeFlashCacheRange 0x08000000-0x0800FFFF")
        actual_boot = read(0x08000000, len(boot))
        result["boot"] = r.raw(destination/"boot-region.bin", actual_boot)
        require(actual_boot == boot, "whole Boot changed")
        journal = read(0x90300000, 4096)
        result["journal_raw"] = r.raw(destination/"staging-journal.bin", journal)
        result["journal"] = prior["decode_journal"](journal, group["package"]["sha256"], len(package))
        durable = result["journal"]["durable_off"]
        require(durable == analysis["durable_off"] and durable > 0, "durable state changed since failure")
        prefix = read(0x90301000, durable)
        result["staging_prefix"] = r.raw(destination/"staging-prefix.bin", prefix)
        require(prefix == package[:durable], "durable prefix mismatch")
        frozen = read(profile["symbols"]["profile"], 288)
        result["profile_raw"] = r.raw(destination/"profile.bin", frozen)
        result["last_internal_profile"] = profile_record(r, frozen, analysis["internal_sessions"][-1]["run"],
                                                        len(package), config["baud"])
        session_raw = read(addresses["session"], layout["size"])
        result["session_raw"] = r.raw(destination/"session.bin", session_raw)
        session = decode_session(session_raw, layout)
        result["session"] = session
        require(session["state"] == session["isr_active"] == session["session_id"] == session["receiver"] == 0 and
                session["total_len"] == len(package) and session["package_sha256"] == group["package"]["sha256"] and
                session["durable_off"] == durable and session["complete"] == 0, "unreconciled current MCU session")
        require(read(0x90300000, 4096) == journal and read(profile["symbols"]["profile"], 288) == frozen and
                link.read(c.APP, 0x460) == expected[:0x460], "App/session/journal changed during readback")
        result["after"] = state("state-after.json")
        prior["valid_health"](result["before"], result["after"], config["baud"], m.baud_word(config["baud"]))
        result.update(result="BASELINE_AND_DURABLE_PREFIX_VERIFIED", identity=c.image_identity(actual),
                      bcb="fresh RAM confirmation flags and original same-boot RTT; no EEPROM access",
                      next="Host recovery regression first; preserve failed cell, do not advance it")
    except Exception as error:
        result["error"] = type(error).__name__+": "+str(error)
    finally:
        link.close()
        result.update(ended=b.now(), reader_closed=not link.opened, native_history_after=c.record(c.MRU))
        evidence.save("result.json", result)
        evidence.events.close()
        evidence.ledger.close()
    r.event("durable-timeout-passive-readback", "completed" if "error" not in result else "failed",
            run=run, receipt=b.record(destination/"result.json"))
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("mode", choices=("analyze", "layout", "launch-readback", "readback-worker"))
    parser.add_argument("--run", default="baud-460800")
    args = parser.parse_args()
    require(Path.cwd() == ROOT and sys.flags.isolated and sys.flags.no_site and sys.dont_write_bytecode,
            "isolated explicit project-root execution required")
    r = runtime()
    r.authority()
    out, _ = prior["context"](r, args.run)
    tests = r.read(out/"failure/host-tests-001/result.json")
    require(tests["passed"] and tests["sources"] == source_records(r) and tests["runtime_sources"] == r.sources(),
            "source-bound host tests required")
    os.environ.update(r.environment())
    if args.mode == "analyze":
        print(json.dumps(analyze(r, args.run)), flush=True)
    elif args.mode == "layout":
        print(json.dumps(make_layout(r, out/"failure/layout")), flush=True)
    elif args.mode == "launch-readback":
        r.m.native_authority()
        print(r.supervisor.owned.launch(r.RUNTIME/("readback-"+args.run+"-durable"), SELF,
              ["readback-worker", "--run", args.run], 240), flush=True)
    else:
        cycle = r.load("durable_readback_lock", SELF.with_name("repeat_cycle.py"))
        with cycle.device_lock():
            result = readback(r, args.run)
        print(json.dumps(result), flush=True)
        raise SystemExit(0 if result["result"] == "BASELINE_AND_DURABLE_PREFIX_VERIFIED" else 1)


if __name__ == "__main__":
    main()
