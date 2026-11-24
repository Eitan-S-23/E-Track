"""Preserve a failed baud-screen bootstrap and reconcile it without a retry."""
from __future__ import annotations

import argparse
import importlib.util
import json
import os
from pathlib import Path
import re
import struct
import sys
import time
import zlib


def require(value, message):
    if not value:
        raise RuntimeError(message)


def startup_summary(events):
    boots = []
    for event in events:
        if event.get("kind") != "rtt-line":
            continue
        line = event["line"].strip()
        if line.startswith("Reset:"):
            boots.append(dict(observed_at=event["time"], reset=line[6:].split(),
                              diagnostic=False, confirmed=None))
        elif line.startswith("P34BOOT:") and boots:
            boots[-1]["diagnostic"] = True
            boots[-1]["baud_report"] = line
        elif boots and (match := re.fullmatch(r"OTA: BCB (?:already )?CONFIRMED vcode=(\d+)", line)):
            boots[-1]["confirmed"] = int(match[1])
    return boots


def classify(capture, messages, boots, baseline, target):
    require(capture["outcome"] == "not-completed", "only a finished failed invocation is eligible")
    require(capture["input"]["currentVersionCode"] == baseline and
            capture["input"]["targetVersionCode"] == target, "failed input identity changed")
    stats = [json.loads(line.removeprefix("OTA_LINK_STATS ")) for line in messages.splitlines()
             if line.startswith("OTA_LINK_STATS ")]
    transfer = [item for item in stats if item["label"] == "upgrade" and
                item["transfer"]["outcome"] is not None]
    require(len(transfer) == 1, "one unambiguous transfer outcome required")
    new_boots = [index for index, boot in enumerate(boots) if boot["diagnostic"]]
    returned = bool(new_boots and any(boot["confirmed"] == baseline for boot in boots[max(new_boots)+1:]))
    end_ack = sum(line.startswith("OTA_MONO MONO_END_ACK_OK ") for line in messages.splitlines())
    watchdog = sum("WDT" in boot["reset"] for boot in boots[min(new_boots)+1:]) if new_boots else 0
    return dict(result="WATCHDOG_ROLLBACK_OBSERVED" if returned and watchdog else "FAILED_NEEDS_TRIAGE",
                transfer=transfer[0], end_ack_events=end_ack, diagnostic_startups=len(new_boots),
                later_watchdog_resets=watchdog, baseline_confirmation_after_target=returned,
                boots=boots, exact_startup_cause="NOT_ESTABLISHED", full_post_failure_readback="REQUIRED",
                ota_success=False, independent_acceptance=False)


def load_runtime():
    path = Path(__file__).with_name("baud_runtime.py")
    spec = importlib.util.spec_from_file_location("baud_failure_runtime", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def context(runtime, run="bootstrap"):
    runtime.authority()
    out = runtime.cell(run)
    closed = runtime.read(out / "mcu/result.json")
    supervisor = runtime.read(runtime.RUNTIME / ("capture-" + run) / "closed.json")
    require(closed["reader_closed"] and closed["run"] == run and
            supervisor["worker_exit"] in (0, 1) and not supervisor["forced_termination"], "original reader is not closed")
    require(not (out / "completed.json").exists(), "do not reinterpret a completed run")
    return out, runtime.read(out / "config.json")


def analyze(runtime, run="bootstrap"):
    out, config = context(runtime, run)
    destination = runtime.b.checked(out / "failure/analysis.json")
    require(not destination.exists(), "preserve existing failure analysis")
    obs = runtime.apk()["metadata"]["device_observation"]
    parser = runtime.load("baud_failure_envelope", runtime.b.SRC / "Tools/ota/p3-4-link-stats/observation_capture.py")
    capture, messages = parser.verify((out / "finished/snapshot.jsonl").read_bytes(),
                                     sentinel=obs["sentinel"], target=runtime.TARGET)
    group = config["assets"]
    require(capture["input"]["packageSha256"] == group["package"]["sha256"] and
            capture["input"]["currentImageSha256"] == group["baseline"]["sha256"] and
            capture["input"]["targetImageSha256"] == group["target"]["sha256"], "failed asset binding changed")
    runtime.experiment_line(messages, config)
    with (out / "mcu/events.jsonl").open(encoding="utf-8") as stream:
        boots = startup_summary(json.loads(line) for line in stream)
    result = classify(capture, messages, boots, 30207, 30208)
    result.update(time=runtime.b.now(), capture=capture, source=runtime.b.record(__file__),
                  originals=[runtime.b.record(out / name) for name in (
                      "config.json", "finished/snapshot.jsonl", "mcu/events.jsonl", "mcu/result.json")])
    runtime.save(destination, result)
    runtime.event("bootstrap-failure", "failed", analysis=runtime.b.record(destination), result=result["result"])
    print(json.dumps(result), flush=True)


def readback(runtime, run="bootstrap"):
    out, config = context(runtime, run)
    b, m, c = runtime.b, runtime.m, runtime.m.c
    require(runtime.supervisor.owned.in_job(), "bounded owned runtime required")
    m.native_authority()
    bindings = m.load_bindings()
    group = config["assets"]
    expected = Path(group["baseline"]["path"]).read_bytes()
    target = Path(group["target"]["path"]).read_bytes()
    whole_boot = Path(bindings["whole_boot"]["path"]).read_bytes()
    require(b.record(group["baseline"]["path"]) == group["baseline"] and
            b.record(group["target"]["path"]) == group["target"] and
            b.record(bindings["whole_boot"]["path"]) == bindings["whole_boot"], "image input drift")
    directory = b.checked(out / "failure/readback")

    class Evidence(c.Evidence):
        NAMES = (*c.Evidence.NAMES, "boot-region.bin", "backup-header.bin", "backup.bin",
                 "candidate-header.bin", "candidate.bin", "staging-journal.bin", "state-before.json", "state-after.json")

    for name in Evidence.NAMES:
        b.checked(directory / name)
    os.environ.update(runtime.supervisor.owned.environment(directory.parent))
    evidence = Evidence(directory)
    link = c.Link(evidence, writable=False)
    profile = bindings["profiles"]["30207"]
    map_text = Path(profile["map"]["path"]).read_text(encoding="utf-8")
    state_address = m.map_bss(map_text, "_ZL20g_ota_state_snapshot", 1)
    health_address = m.map_bss(map_text, "_ZL12g_ota_health", 36)
    symbols = profile["symbols"]
    lv_peak = m.map_bss(map_text, "max_used", 4) if ".bss.max_used\n" in map_text else None
    result = dict(started=b.now(), result="READBACK_INCOMPLETE", flash=0, reset=0,
                  at=0, eeprom_write=0, qspi_write=0, rtt_read_pointer_write=0,
                  native_history_before=c.record(c.MRU), source=b.record(__file__))

    def read(address, size):
        link.ram_reads.append((address, address + size))
        return m.read_region(link, address, size)

    def save(name, data):
        return runtime.raw(directory / name, data)

    def state(name):
        tick = m.u32(read(symbols["tick"], 4))
        data = dict(time=b.now(), tick=tick, vtor=m.u32(read(0xE000ED08, 4)),
                    sd_ready=read(symbols["sd_ready"], 1)[0],
                    ota_state_bytes=read(state_address, 3).hex(),
                    health_words=struct.unpack("<9I", read(health_address, 36)),
                    retained_word=m.u32(read(m.ERTC_DT20, 4)))
        if lv_peak is not None:
            data["lvgl_heap_peak"] = m.u32(read(lv_peak, 4))
        runtime.save(directory / name, data)
        return data

    try:
        link.connect()
        require(link.read(c.APP, 0x460) == expected[:0x460], "not the expected returned baseline")
        result["state_before"] = state("state-before.json")
        image = m.base.read_image(link, len(expected))
        result["image"] = save("image.bin", image)
        require(image == expected, "full baseline readback mismatch")
        link.command("ExcludeFlashCacheRange 0x08000000-0x0800FFFF")
        boot = read(0x08000000, 65536)
        result["boot"] = save("boot-region.bin", boot)
        require(boot == whole_boot, "whole Boot changed")
        for label, address, image in (("candidate", 0x90000000, target), ("backup", 0x90100000, expected)):
            header = read(address, 32)
            result[label + "_header"] = save(label + "-header.bin", header)
            length, crc, version = struct.unpack_from("<III", header, 8)
            require(length == len(image) and header[:4] == b"ETSL" and
                    struct.unpack_from("<I", header, 28)[0] == 0x434F4D54, "slot header shape: " + label)
            actual = read(address + 4096, length)
            result[label] = save(label + ".bin", actual)
            require(actual == image and crc == zlib.crc32(actual) & 0xFFFFFFFF and
                    version == c.image_identity(actual)["version_code"] and
                    read(address, 32) == header, "slot identity or stability mismatch: " + label)
        result["journal"] = save("staging-journal.bin", read(0x90300000, 4096))
        result["state_after"] = state("state-after.json")
        require(link.read(c.APP, 0x460) == expected[:0x460], "App changed during readback")
        require(result["state_after"]["ota_state_bytes"] == "040101" and
                result["state_after"]["health_words"][8] == 1 and
                0 < (result["state_after"]["tick"] - result["state_before"]["tick"]) % 2**32 < 240000,
                "baseline is not healthy and confirmed")
        result.update(result="BASELINE_RETAINED_BOOT_AND_SLOTS_VERIFIED", identity=c.image_identity(expected),
                      bcb="Current App RAM cache and original RTT confirmation; no direct EEPROM read or write")
    except Exception as error:
        result["error"] = type(error).__name__ + ": " + str(error)
    finally:
        link.close()
        result.update(ended=b.now(), reader_closed=not link.opened, native_history_after=c.record(c.MRU))
        evidence.save("result.json", result)
        evidence.events.close()
        evidence.ledger.close()
    runtime.event("bootstrap-passive-readback", "completed" if "error" not in result else "failed",
                  receipt=b.record(directory / "result.json"), result=result["result"])
    print(json.dumps(result), flush=True)
    return 0 if result["result"] == "BASELINE_RETAINED_BOOT_AND_SLOTS_VERIFIED" else 1


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("mode", choices=("analyze", "launch-readback", "readback-worker"))
    parser.add_argument("--run", default="bootstrap")
    args = parser.parse_args()
    runtime = load_runtime()
    require(Path.cwd().resolve() == runtime.b.ROOT and sys.flags.isolated and
            sys.flags.no_site and sys.dont_write_bytecode, "isolated explicit-root execution required")
    if args.mode == "analyze":
        analyze(runtime, args.run)
    elif args.mode == "launch-readback":
        context(runtime, args.run)
        print(runtime.supervisor.owned.launch(runtime.RUNTIME / ("readback-" + args.run + "-r1"), Path(__file__).resolve(),
                                             ["readback-worker", "--run", args.run], 240), flush=True)
    else:
        cycle = runtime.load("baud_failure_lock", Path(__file__).with_name("repeat_cycle.py"))
        with cycle.device_lock():
            raise SystemExit(readback(runtime, args.run))


if __name__ == "__main__":
    main()
