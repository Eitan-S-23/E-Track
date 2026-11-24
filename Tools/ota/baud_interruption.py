"""Reconcile a finished pre-END interruption without replaying an OTA."""
from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import re
import runpy
import struct
import sys
import time
import zlib

ROOT = Path(__file__).resolve().parents[2]
SELF = Path(__file__).resolve()
PARENT = SELF.with_name("baud_resume_clock.py")


def require(value, message):
    if not value:
        raise RuntimeError(message)


def runtime():
    return runpy.run_path(str(PARENT), run_name="interruption_runtime")["runtime"]()


def classify(records, timeout_ms):
    starts = [i for i, item in enumerate(records) if item.get("kind") == "upgrade-start"]
    ends = [i for i, item in enumerate(records) if item.get("kind") == "upgrade-end"]
    require(len(starts) == len(ends) == 1 and starts[0] < ends[0], "one finished invocation required")
    require(records[ends[0]]["outcome"] == "not-completed", "do not reinterpret a success")
    lines = [item["message"] for item in records[starts[0]+1:ends[0]] if item.get("kind") == "line"]
    summaries = [json.loads(line[len("OTA_LINK_STATS "):]) for line in lines
                 if line.startswith("OTA_LINK_STATS ")]
    summaries = [item for item in summaries if item["label"] == "upgrade"]
    require(len(summaries) == 1, "one upgrade summary required")
    stats = summaries[0]
    require(stats["transfer"]["outcome"] == "fail" and stats["transfer"]["endAckUs"] is None and
            not any(line.startswith("OTA_MONO MONO_END_ACK_OK ") for line in lines), "not a pre-END failure")
    require(type(timeout_ms) is int and timeout_ms > 0, "positive MCU timeout required")
    pauses, pending = [], None
    for line in lines:
        match = re.fullmatch(r"OTA_MONO MONO_(PAUSE|RESUME) monoUs=(\d+) wallUs=\d+", line)
        if not match:
            continue
        kind, stamp = match[1], int(match[2])
        if kind == "PAUSE" and pending is None:
            pending = stamp
        elif kind == "RESUME" and pending is not None:
            require(stamp >= pending, "nonmonotonic pause interval")
            pauses.append(dict(start_mono_us=pending, end_mono_us=stamp, duration_us=stamp-pending))
            pending = None
    matched = (any(p["duration_us"] > timeout_ms*1000 for p in pauses) and
               stats["failure"] == dict(stage="transfer", reason="mcu-ack-0xff") and
               stats["transfer"]["acks"]["abort"] == 1)
    return dict(result="BACKGROUND_PAUSE_ABORTED_PRE_END" if matched else "PRE_END_FAILURE_NEEDS_TRIAGE",
                pauses=pauses, unmatched_pause=pending, timeout_ms=timeout_ms, statistics=stats,
                durable_off=stats["transfer"]["durable"]["finalOff"], end_ack=False,
                full_package_throughput_eligible=False, ota_success=False, independent_acceptance=False)


def decode_journal(data, package_sha256, total_len):
    require(len(data) == 4096 and type(total_len) is int and 0 < total_len <= 2093056, "journal/length bounds")
    journal = data[0x40:0x6c]
    require(journal[:4] == b"ETRJ" and journal[4:36].hex() == package_sha256 and
            struct.unpack_from("<I", journal, 36)[0] == total_len and
            struct.unpack_from("<I", journal, 40)[0] == zlib.crc32(journal[:40]) & 0xffffffff,
            "journal identity/CRC mismatch")
    require(data[28:32] == b"\xff"*4, "staging already committed; not a pre-END interruption")
    bits = [(data[0x70+i//8] >> (i % 8)) & 1 for i in range(512)]
    blocks = (total_len+4095)//4096
    first = next((i for i in range(blocks) if bits[i]), blocks)
    require(all(bits[i] for i in range(first, 512)), "noncontiguous/out-of-range durable bitmap")
    durable = min(first*4096, total_len)
    require(durable < total_len, "complete staging requires a different reconciliation")
    return dict(package_sha256=package_sha256, total_len=total_len, durable_off=durable,
                complete_blocks=first, committed=False, continuation="new BEGIN must confirm this durable prefix")


def context(r, run):
    r.authority()
    out = r.cell(run)
    require(not (out/"completed.json").exists(), "do not reinterpret completed run")
    board = r.read(out/"mcu/result.json")
    owner = r.read(r.RUNTIME/("capture-"+run)/"closed.json")
    coordinator = r.read(r.RUNTIME/("coordinate-"+run)/"closed.json")
    require(board["reader_closed"] and board["run"] == run and not board["state"]["target_bcb_observed"] and
            owner["worker_exit"] == 0 and not owner["forced_termination"] and
            coordinator["worker_exit"] == 0 and not coordinator["forced_termination"],
            "original observers not closed or target state changed")
    return out, r.read(out/"config.json")


def analyze(r, run):
    out, config = context(r, run)
    destination = r.b.checked(out/"failure/interruption.json")
    require(not destination.exists(), "preserve original interruption analysis")
    obs = r.apk()["metadata"]["device_observation"]
    parser = r.load("interruption_envelope", r.b.SRC/"Tools/ota/p3-4-link-stats/observation_capture.py")
    raw = (out/"finished/snapshot.jsonl").read_bytes()
    capture, messages = parser.verify(raw, sentinel=obs["sentinel"], target=r.TARGET)
    expected = r.read(config["runtime_config"]["path"])
    require(all(capture["input"][key] == expected[key] for key in
                ("packageSha256", "packageBytes", "currentVersionCode", "targetVersionCode",
                 "currentImageSha256", "targetImageSha256")), "failed input binding changed")
    r.experiment_line(messages, config)
    source = r.a.FW/"USER/HAL/HAL_Config.h"
    matches = re.findall(r"^#define CONFIG_OTA_BLE_SESSION_TIMEOUT_MS (\d+)u", source.read_text(encoding="utf-8"), re.M)
    require(len(matches) == 1, "MCU timeout definition ambiguous")
    result = classify([json.loads(line) for line in raw.splitlines()], int(matches[0]))
    profile = dict(zip(r.m.HEADERS, struct.unpack("<72I", (out/"mcu/profile.bin").read_bytes())[:24]))
    require((profile["magic"], profile["schema"], profile["size"], profile["ready"], profile["active"], profile["terminal"])
            == (0x50334250, 1, 288, 1, 0, 1), "profile is not a frozen interrupted session")
    require(profile["total_len"] == expected["packageBytes"] and
            r.m.actual_baud_matches(config["baud"], profile["uart_baud_actual"]) and
            profile["retained_baud"] == config["baud"], "profile input/baud drift")
    result.update(time=r.b.now(), run=run, source=r.b.record(SELF), parent=r.b.record(PARENT),
                  capture=capture, profile=profile, originals=[r.b.record(out/name) for name in
                  ("config.json", "finished/snapshot.jsonl", "mcu/events.jsonl", "mcu/result.json", "mcu/profile.bin")],
                  timeout_source=r.b.record(source), full_post_failure_readback="REQUIRED")
    r.b.checked(r.RUNTIME/"actions.jsonl")
    r.save(destination, result)
    r.event("pre-end-interruption", "failed", run=run, result=result["result"], analysis=r.b.record(destination))
    return result


def valid_health(before, after, baud, retained):
    for value in (before, after):
        require(value["vtor"] == 0x08010000 and value["sd_ready"] == 1 and value["bcb_state"] == 4 and
                value["confirm_done"] == value["state_snapped"] == 1 and value["health_words"][8] == 1,
                "current baseline is not healthy/confirmed")
        require(value["boot_baud"] == baud and value["retained_word"] == retained and
                value["backup_word"] == retained and value["retention_error"] == 0, "retained baud drift")
    require(0 < (after["tick"]-before["tick"]) % 2**32 < 240000, "App time is not advancing within readback bound")


def readback(r, run):
    out, config = context(r, run)
    b, m, c = r.b, r.m, r.m.c
    require(r.supervisor.owned.in_job(), "owned bounded worker required")
    m.native_authority()
    analysis_path = out/"failure/interruption.json"
    analysis = r.read(analysis_path)
    require(analysis["source"] == b.record(SELF) and analysis["parent"] == b.record(PARENT) and
            analysis["result"] == "BACKGROUND_PAUSE_ABORTED_PRE_END", "reconciliation diagnosis not admitted")
    require(all(b.record(item["path"]) == item for item in analysis["originals"]), "failed evidence changed")
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
                     health=m.map_bss(map_text, "_ZL12g_ota_health", 36))
    destination = b.checked(out/"failure/readback-interruption")

    class Evidence(c.Evidence):
        NAMES = (*c.Evidence.NAMES, "boot-region.bin", "staging-journal.bin", "staging-prefix.bin",
                 "profile.bin", "state-before.json", "state-after.json")

    for name in Evidence.NAMES:
        b.checked(destination/name)
    b.checked(r.RUNTIME/"actions.jsonl")
    for key in ("HOME", "USERPROFILE", "APPDATA", "LOCALAPPDATA", "TEMP", "TMP", "TMPDIR"):
        require(key in os.environ, "missing contained environment: "+key)
        b.checked(Path(os.environ[key]))
    evidence = Evidence(destination)
    link = m.BoundLink(evidence, writable=False)
    result = dict(started=b.now(), run=run, source=b.record(SELF), analysis=b.record(analysis_path),
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
        result["journal"] = decode_journal(journal, group["package"]["sha256"], len(package))
        durable = result["journal"]["durable_off"]
        require(durable == analysis["durable_off"] and durable > 0, "durable state changed since failed snapshot")
        prefix = read(0x90301000, durable)
        result["staging_prefix"] = r.raw(destination/"staging-prefix.bin", prefix)
        require(prefix == package[:durable], "durable package prefix differs")
        frozen = read(profile["symbols"]["profile"], 288)
        result["profile"] = r.raw(destination/"profile.bin", frozen)
        require(frozen == (out/"mcu/profile.bin").read_bytes(), "interruption profile changed")
        require(read(0x90300000, 4096) == journal and link.read(c.APP, 0x460) == expected[:0x460],
                "App/journal changed during readback")
        result["after"] = state("state-after.json")
        valid_health(result["before"], result["after"], config["baud"], m.baud_word(config["baud"]))
        result.update(result="BASELINE_AND_DURABLE_PREFIX_VERIFIED", identity=c.image_identity(actual),
                      bcb="fresh RAM confirmation flags plus original current-boot RTT; no EEPROM access",
                      next="Foreground recovery must begin a new session and confirm durable; not clean screening")
    except Exception as error:
        result["error"] = type(error).__name__+": "+str(error)
    finally:
        link.close()
        result.update(ended=b.now(), reader_closed=not link.opened, native_history_after=c.record(c.MRU))
        evidence.save("result.json", result)
        evidence.events.close()
        evidence.ledger.close()
    r.event("pre-end-passive-readback", "completed" if "error" not in result else "failed", run=run,
            result=result["result"], receipt=b.record(destination/"result.json"))
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("mode", choices=("analyze", "launch-readback", "readback-worker"))
    parser.add_argument("--run", default="baud-115200-r6")
    args = parser.parse_args()
    require(Path.cwd() == ROOT and sys.flags.isolated and sys.flags.no_site and sys.dont_write_bytecode,
            "isolated explicit project-root execution required")
    r = runtime()
    tests = r.read(r.b.OUT/"host-tests-interruption-001/result.json")
    require(tests["passed"] and tests["source"] == r.b.record(SELF) and
            tests["test_source"] == r.b.record(SELF.with_name("test_baud_interruption.py")) and
            tests["runtime_sources"] == r.sources(), "source-bound interruption tests required")
    if args.mode == "analyze":
        result = analyze(r, args.run)
        print(json.dumps(result), flush=True)
    elif args.mode == "launch-readback":
        context(r, args.run)
        r.m.native_authority()
        print(r.supervisor.owned.launch(r.RUNTIME/("readback-"+args.run+"-interruption"), SELF,
              ["readback-worker", "--run", args.run], 240), flush=True)
    else:
        cycle = r.load("interruption_device_lock", SELF.with_name("repeat_cycle.py"))
        with cycle.device_lock():
            result = readback(r, args.run)
        print(json.dumps(result), flush=True)
        raise SystemExit(0 if result["result"] == "BASELINE_AND_DURABLE_PREFIX_VERIFIED" else 1)


if __name__ == "__main__":
    main()
