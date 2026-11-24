"""Read-only post-END blackout diagnosis; never retry, reset, halt or flash."""
from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import runpy
import struct
import sys
import time

ROOT = Path(__file__).resolve().parents[2]
SELF = Path(__file__).resolve()
AREA = ROOT / ".cache/p34q/irqscreen/triage"
RUN = "irq-460800"
RAM, RAM_END = 0x20000000, 0x20058000


def require(value, reason):
    if not value:
        raise RuntimeError(reason)


def runtime():
    return runpy.run_path(str(SELF.with_name("irq_screen.py")))["runtime"]()


def context(r):
    r.authority()
    out = r.cell(RUN)
    require(not (out / "completed.json").exists(), "do not reinterpret a completed run")
    for name in ("capture-" + RUN, "coordinate-" + RUN):
        closed = r.read(r.RUNTIME / name / "closed.json")
        require(not closed["forced_termination"] and closed["worker_exit"] in (0, 1), "prior owner is not closed")
    require(r.read(out / "mcu/result.json")["reader_closed"], "prior MCU reader still owns the link")
    return out


def decode_rtt(ram, address):
    offset = address - RAM
    require(0 <= offset <= len(ram) - 168, "RTT outside captured RAM")
    data = ram[offset:offset + 168]
    result = dict(address=address, raw=data.hex(), signature=data[:16].hex())
    if data[:10] != b"SEGGER RTT":
        result["valid"] = False
        return result
    count_up, count_down = struct.unpack_from("<II", data, 16)
    result.update(up_count=count_up, down_count=count_down, descriptors=[])
    for name, base in (("up0", 24), ("down0", 96)):
        label, buffer, size, wr, rd, flags = struct.unpack_from("<6I", data, base)
        valid = RAM <= buffer < buffer + size <= RAM_END and 0 < size <= 16384 and wr < size and rd < size
        item = dict(name=name, label=label, buffer=buffer, size=size, wr=wr, rd=rd, flags=flags, valid=valid)
        if valid and buffer + size - RAM <= len(ram):
            ring = ram[buffer-RAM:buffer-RAM+size]
            item["physical_ring"] = ring.hex()
            item["unread"] = (ring[rd:wr] if wr >= rd else ring[rd:] + ring[:wr]).hex()
        result["descriptors"].append(item)
    result["valid"] = count_up == count_down == 3 and all(x["valid"] for x in result["descriptors"])
    return result


def analyze(r):
    out = context(r)
    parser = r.phone(RUN).envelope
    raw = (out / "finished/snapshot.jsonl").read_bytes()
    capture, messages = parser.verify(raw, sentinel=r.apk()["metadata"]["device_observation"]["sentinel"], target=r.TARGET)
    config = r.read(out / "config.json")
    group = config["assets"]
    require(capture["outcome"] == "not-completed" and capture["pid"] == r.read(out / "launched.json")["pid"] and
            capture["input"]["packageSha256"] == group["package"]["sha256"] and
            capture["input"]["currentImageSha256"] == group["baseline"]["sha256"] and
            capture["input"]["targetImageSha256"] == group["target"]["sha256"], "failed original input differs")
    r.experiment_line(messages, config)
    stats = [json.loads(line.split(" ", 1)[1]) for line in messages.splitlines() if line.startswith("OTA_LINK_STATS ")]
    transfers = [x for x in stats if x["label"] == "upgrade" and x["transfer"]["outcome"] is not None]
    require(len(transfers) == 1, "ambiguous transfer history")
    result = dict(time=r.b.now(), capture=capture, transfer=transfers[0],
        end_ack_events=sum(x.startswith("OTA_MONO MONO_END_ACK_OK ") for x in messages.splitlines()),
        mcu_profile=r.b.record(out / "mcu/profile.json"), original_snapshot=r.b.record(out / "finished/snapshot.jsonl"),
        original_collector_error=r.read(out / "mcu/result.json")["error"],
        result="TRANSFER_COMPLETE_POST_END_BLACKOUT_UNRESOLVED", ota_success=False, hardware_writes=0,
        source=r.b.record(SELF), independent_acceptance=False)
    require(result["end_ack_events"] == 1 and transfers[0]["transfer"]["durable"]["finalOff"] == group["package"]["bytes"],
            "transfer did not complete; not this post-END probe")
    r.save(AREA / "analysis.json", result)
    print("ORIGINAL_FAILURE_VERIFIED", json.dumps(dict(seconds=transfers[0]["transfer"]["elapsedUs"] / 1e6,
        snapshot=result["original_snapshot"], transfer=transfers[0]["transfer"])), flush=True)


def probe(r, label):
    out = context(r)
    require(r.supervisor.owned.in_job(), "bounded probe owner required")
    r.m.native_authority()
    plan = r.read(AREA / (label + "-plan.json"))
    require(plan["source"] == r.b.record(SELF) and plan["config"] == r.b.record(out / "config.json"), "probe source drift")
    c, m = r.m.c, r.m
    directory = r.b.checked(AREA / label)

    class Evidence(c.Evidence):
        NAMES = (*c.Evidence.NAMES, "samples.json", "ram.bin", "boot-region.bin", "prefix.bin", "rtt-snapshot.json")

    for name in Evidence.NAMES:
        r.b.checked(directory / name)
    e = Evidence(directory)
    link = m.BoundLink(e, writable=False)
    result = dict(started=r.b.now(), result="PROBE_INCOMPLETE", source=r.b.record(SELF),
        reset=0, halt=0, flash=0, target_writes=0, rtt_pointer_writes=0, native_before=c.record(c.MRU))

    def read(address, size):
        if (address, address+size) not in link.ram_reads:
            link.ram_reads.append((address, address+size))
        # Unlike a successful-App verifier, this read-only probe must also
        # preserve Boot/fault/halted state without trying to make it run.
        data, deadline = bytearray(), time.monotonic() + 70
        while len(data) < size:
            require(time.monotonic() < deadline, "diagnostic read deadline")
            data.extend(link.read(address + len(data), min(16384, size - len(data))))
        return bytes(data)

    def word(address):
        return struct.unpack("<I", read(address, 4))[0]

    try:
        try:
            link.connect()
        except c.ControlError as error:
            # Observation of Boot or a pre-existing halt must not resume/reset it.
            require(str(error) in ("unexpected VTOR", "MCU halted; no automatic resume") and
                    link.opened and link.sdk.JLINKARM_IsConnected() and word(0xE000ED00) == 0x410FC241,
                    "read-only diagnostic connection failed: " + str(error))
            result["normal_app_admission_error"] = str(error)
            cache = runpy.run_path(str(SELF.with_name("baud_uncached.py")))
            cache["disable_cache"](link)
            link.command("InvalidateCache")
        link.command("ExcludeFlashCacheRange 0x08000000-0x0800FFFF")
        prefix = read(c.APP, 0x460)
        result["prefix"] = r.raw(directory / "prefix.bin", prefix)
        profiles = m.load_bindings()["profiles"]
        matched = [p for p in profiles.values() if prefix == bytes.fromhex(p["prefix"])]
        result["matched_prefix_versions"] = [p["identity"]["version_code"] for p in matched]
        symbols = profiles["30210"]["symbols"]
        samples = []
        for _ in range(8):
            faults = struct.unpack("<7I", read(0xE000ED24, 28))
            item = dict(time=r.b.now(), halted=bool(link.sdk.JLINKARM_IsHalted()),
                dhcsr=word(0xE000EDF0), vtor=word(0xE000ED08), icsr=word(0xE000ED04), pcsr=word(0xE000101C),
                systick=read(0xE000E010, 16).hex(), faults=dict(zip(
                    ("shcsr", "cfsr", "hfsr", "dfsr", "mmfar", "bfar", "afsr"), faults)),
                app_tick=word(symbols["tick"]), core_clock=word(symbols["core_clock"]),
                sd_ready=read(symbols["sd_ready"], 1)[0])
            samples.append(item)
            e.emit("passive-state", sample=item)
            print("PASSIVE_STATE", json.dumps(item), flush=True)
            time.sleep(.25)
        r.save(directory / "samples.json", samples)
        ram = read(RAM, RAM_END-RAM)
        result["ram"] = r.raw(directory / "ram.bin", ram)
        r.save(directory / "rtt-snapshot.json", decode_rtt(ram, symbols["rtt"]))
        image = read(c.APP, 613264)
        result["image"] = r.raw(directory / "image.bin", image)
        result["matching_full_images"] = [p["identity"]["version_code"] for p in profiles.values()
            if result["image"]["sha256"] == p["image"]["sha256"]]
        boot = read(0x08000000, 65536)
        result["boot"] = r.raw(directory / "boot-region.bin", boot)
        result["whole_boot_unchanged"] = result["boot"]["sha256"] == m.load_bindings()["whole_boot"]["sha256"]
        result["prefix_stable"] = read(c.APP, 0x460) == prefix
        result.update(result="PASSIVE_BLACKOUT_STATE_SAVED", samples=len(samples))
    except Exception as error:
        result["error"] = type(error).__name__ + ": " + str(error)
    finally:
        link.close()
        result.update(ended=r.b.now(), reader_closed=not link.opened, native_after=c.record(c.MRU))
        e.save("result.json", result)
        e.events.close()
        e.ledger.close()
    print("BLACKOUT_PROBE_RESULT", json.dumps(result), flush=True)
    return 0 if result["result"] == "PASSIVE_BLACKOUT_STATE_SAVED" else 1


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("mode", choices=("analyze", "launch", "probe-worker"))
    parser.add_argument("--probe-id", choices=("probe-r2",), default="probe-r2")
    args = parser.parse_args()
    require(Path.cwd() == ROOT and sys.flags.isolated and sys.flags.no_site and sys.dont_write_bytecode,
            "isolated explicit root required")
    r = runtime()
    r.b.checked(AREA)
    if args.mode == "analyze":
        analyze(r)
        return
    out = context(r)
    os.environ.update(r.environment())
    if args.mode == "launch":
        previous = r.read(r.RUNTIME / "blackout-probe/closed.json")
        require(previous["worker_exit"] == 1 and not previous["forced_termination"] and
                r.read(AREA / "probe/result.json")["target_writes"] == 0,
                "original read-only probe must be reconciled before host repair")
        analysis = r.read(AREA / "analysis.json")
        require(analysis["result"] == "TRANSFER_COMPLETE_POST_END_BLACKOUT_UNRESOLVED", "original failure not reconciled")
        r.save(AREA / (args.probe_id + "-plan.json"), dict(time=r.b.now(), root=str(ROOT), source=r.b.record(SELF),
            config=r.b.record(out / "config.json"), analysis=r.b.record(AREA / "analysis.json"),
            operations="one non-halting read-only MCU attachment, registers/RAM/App/Boot; no RTT consumption or writes",
            limit_seconds=240, native=r.m.native_authority()))
        print(json.dumps(r.supervisor.owned.launch(r.RUNTIME / ("blackout-" + args.probe_id), SELF,
            ["probe-worker", "--probe-id", args.probe_id], 240)), flush=True)
    else:
        lock = r.load("irq_blackout_lock", SELF.with_name("repeat_cycle.py"))
        with lock.device_lock():
            raise SystemExit(probe(r, args.probe_id))


if __name__ == "__main__":
    main()
