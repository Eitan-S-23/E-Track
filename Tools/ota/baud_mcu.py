"""Image-bound MCU observation for the three-rate development screen."""
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


def load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


b = load("baud_mcu_common", Path(__file__).with_name("baud_sweep.py"))
a = load("baud_mcu_assets", Path(__file__).with_name("prepare_baud_assets.py"))
base = load("baud_mcu_primitives", b.P3 / "Tools/ota/p3-4-device/link_baseline_capture.py")
c, passive, epoch = base.c, base.passive, base.epoch
c.ROOT = b.ROOT
c.guard = lambda path, root=b.ROOT: b.io.checked_output(root, path)
PHASES = ("payload_read", "payload_program", "payload_erase", "journal_read", "journal_program",
          "journal_erase", "ack_write_call", "pump_work")
HEADERS = ("magic", "schema", "size", "ready", "run", "clock_hz", "clock_ok", "active",
           "uart_baud_actual", "retained_baud", "total_len", "terminal", "rx_session_bytes",
           "hw_queue_peak", "rx_ring_peak", "overlay_dropped", "hw_buffer_dropped", "uart_error_events",
           "uart_error_flags", "parser_bad_frames", "pump_entries", "pump_gap_max_cycles",
           "pump_gap_cycles_lo", "pump_gap_cycles_hi")
PHASE_FIELDS = ("calls", "errors", "bytes_requested", "cycles_lo", "cycles_hi", "max_cycles")
DWT_CTRL, DWT_COUNT, DEMCR = 0xE0001000, 0xE0001004, 0xE000EDFC
RESERVE_SECONDS = 900 + 300 + 70 + 10
ERTC_DT20 = 0x4000289C  # ERTC_BASE + 0x50 + (ERTC_DT20 enum value 19) * 4.


def baud_word(baud):
    b.require(type(baud) is int and baud in (115200, 460800, 921600), "baud outside screening matrix")
    slot = {115200: 5, 460800: 7, 921600: 8}[baud]
    return 0x50340000 | ((slot ^ 0xFF) << 8) | slot


def actual_baud_matches(requested, actual):
    return (type(requested) is int and requested in (115200, 460800, 921600) and type(actual) is int and
            requested - requested // 33 <= actual <= requested + requested // 33)


def u32(data):
    b.require(len(data) == 4, "uint32 length")
    return struct.unpack("<I", data)[0]


def map_symbol(text, name):
    values = re.findall(r"^\s*(0x[0-9a-fA-F]+)\s+" + re.escape(name) + r"\s*$", text, re.M)
    b.require(len(values) == 1, "missing/ambiguous map symbol: " + name)
    return int(values[0], 16)


def map_bss(text, name, size):
    values = re.findall(r"^\s*\.bss\." + re.escape(name) +
                        r"\s*\n\s*(0x[0-9a-fA-F]+)\s+(0x[0-9a-fA-F]+)\s+[^\n]+$", text, re.M)
    b.require(len(values) == 1 and int(values[0][1], 16) == size, "missing/ambiguous BSS: " + name)
    return int(values[0][0], 16)


def bind_map(text, image, diagnostic):
    tick = map_bss(text, "SystemTickCount", 4)
    handler = map_symbol(text, "SysTick_Handler")
    code = bytes.fromhex("024a136801331360704700bf") + struct.pack("<I", tick)
    offset = handler - c.APP
    b.require(offset >= 0 and image[offset:offset + len(code)] == code, "SysTick bytes/literal do not match map")
    result = dict(rtt=map_symbol(text, "_SEGGER_RTT"), tick=tick,
        core_clock=map_symbol(text, "system_core_clock"), systick_reload=epoch.SYSTICK_RELOAD,
        handler=handler, handler_bytes=code.hex(), sd_ready=map_bss(text, "_ZL10SD_IsReady", 1))
    if diagnostic:
        result.update(profile=map_symbol(text, "g_p34_ble_profile"),
            boot_baud=map_symbol(text, "g_p34_boot_baud"), retained_word=map_symbol(text, "g_p34_retained_word"),
            retention_error=map_symbol(text, "g_p34_retention_error"))
        b.require(map_bss(text, "g_p34_ble_profile", 288) == result["profile"], "profile layout drift")
    for key in ("rtt", "tick", "core_clock", "sd_ready", *( ("profile", "boot_baud", "retained_word", "retention_error") if diagnostic else ())):
        b.require(0x20000000 <= result[key] < 0x20058000, "App RAM symbol outside bound")
    return result


def verified_assets():
    value = json.loads((a.OUT / "result.json").read_text(encoding="utf-8"))
    manifest = json.loads((a.OUT / "manifest.json").read_text(encoding="utf-8"))
    b.require(value["result"] == "HOST_READY" and manifest["metadata"] == value, "asset preparation incomplete")
    b.require(all(b.record(item["path"]) == item for item in manifest["files"] + manifest["inputs"]),
              "prepared asset/input drift")
    return value


def prepare():
    out = b.checked(b.OUT / "mcu-bindings.json")
    b.require(not out.exists(), "preserve existing map bindings")
    assets = verified_assets()
    manifest, original = c.selected_assets("recovery")
    old_map = Path(manifest["assets"]["recovery-3.2.5.map"]["path"])
    boot_map = Path(manifest["assets"]["common-boot.map"]["path"])
    b.require("_SEGGER_RTT" not in boot_map.read_text(encoding="utf-8"), "Boot RTT capability changed")
    new_map = b.OUT / "build/app-gcc/X-Track-App-GCC.map"
    profiles = {}
    for code, item, map_path, body in ((30207, assets["groups"]["bootstrap"]["baseline"], old_map, original),
            (30208, assets["groups"]["screen"]["baseline"], new_map, a.RAW.read_bytes()),
            (30209, assets["groups"]["screen"]["target"], new_map, a.RAW.read_bytes())):
        data = Path(item["path"]).read_bytes()
        b.require(data[:0x400] == body[:0x400] and data[0x460:] == body[0x460:], "map executable body mismatch")
        profiles[str(code)] = dict(image=item, identity=a.legacy.firmware(data), map=b.record(map_path),
            prefix=data[:0x460].hex(), symbols=bind_map(map_path.read_text(encoding="utf-8"), data, code != 30207))
    b.save("mcu-bindings.json", dict(time=b.now(), profiles=profiles, boot_map=b.record(boot_map),
        whole_boot=assets["whole_boot"], source=b.record(Path(__file__)), hardware_contacted=False))
    print("MCU_MAPS_BOUND", json.dumps({key: value["symbols"] for key, value in profiles.items()}), flush=True)


def load_bindings():
    value = b.read("mcu-bindings.json")
    for profile in value["profiles"].values():
        for key in ("image", "map"):
            b.require(b.record(profile[key]["path"]) == profile[key], "image/map binding changed")
    b.require(b.record(value["whole_boot"]["path"]) == value["whole_boot"], "whole Boot binding changed")
    return value


def decode_profile(data, baud, total_len):
    b.require(len(data) == 288, "frozen profile length")
    values = struct.unpack("<72I", data)
    result = dict(zip(HEADERS, values[:24]))
    b.require(tuple(result[key] for key in ("magic", "schema", "size", "ready", "active", "terminal")) ==
              (0x50334250, 1, 288, 1, 0, 0), "profile is not a frozen successful END activation")
    b.require(result["run"] > 0 and result["total_len"] == total_len and actual_baud_matches(baud, result["uart_baud_actual"]) and
              result["retained_baud"] == baud, "profile session/package/actual baud mismatch")
    result["requested_baud"] = baud
    result["uart_divider_error_ppm"] = (result["uart_baud_actual"] - baud) * 1000000 / baud
    b.require(result["clock_hz"] == 288000000 and result["clock_ok"] == 1, "invalid DWT timing")
    phases = {}
    for index, name in enumerate(PHASES):
        item = dict(zip(PHASE_FIELDS, values[24 + index * 6:30 + index * 6]))
        cycles = (item["cycles_hi"] << 32) | item["cycles_lo"]
        b.require((item["calls"] > 0 or (cycles == 0 and item["bytes_requested"] == 0 and item["errors"] == 0)) and
                  item["errors"] <= item["calls"] and item["max_cycles"] <= cycles, "inconsistent profile phase")
        item.update(cycles=cycles, seconds=cycles / result["clock_hz"], max_seconds=item["max_cycles"] / result["clock_hz"])
        phases[name] = item
    b.require(result["pump_entries"] > 0 and result["rx_session_bytes"] >= total_len and
              all(phases[name]["calls"] > 0 and phases[name]["cycles"] > 0 for name in
                  ("payload_program", "journal_program", "ack_write_call", "pump_work")),
              "missing/zero timing is not evidence of free work")
    result.update(phases=phases, clean_counters=all(result[key] == 0 for key in
        ("overlay_dropped", "hw_buffer_dropped", "uart_error_events", "uart_error_flags", "parser_bad_frames")) and
        all(item["errors"] == 0 for item in phases.values()),
        interpretation="nested timings; ACK is write-call duration, not TX completion; END activation is not final OTA verification")
    return result


class CaptureState(base.CaptureState):
    def __init__(self, current, target):
        super().__init__()
        self.current_version, self.target_version = current, target

    def observe(self, observation):
        current = None if observation is None else observation["sample"]["epoch"]
        if current is None or current != self.current_epoch:
            self.baseline_confirmed = self.target_confirmed = False
        self.current_epoch = current
        if observation is not None:
            for line in observation["lines"]:
                self.baseline_confirmed |= passive.confirmation(line, self.current_version)
                self.target_confirmed |= passive.confirmation(line, self.target_version)
        b.require(not (self.baseline_confirmed and self.target_confirmed), "conflicting BCB confirmations in one epoch")


class BoundLink(c.Link):
    def __init__(self, evidence, writable=True):
        super().__init__(evidence, writable)
        self.rtt_address = None

    running = passive.Link.running

    def write(self, address, data):
        b.require(self.rtt_address is not None and address == self.rtt_address + 40 and len(data) == 4,
                  "passive capture can only update its image-bound RTT read pointer")
        self.running()
        super().write(address, data)


class UpChannel(c.Rtt):
    def __init__(self, link, index, profile):
        b.require(0 <= index < len(passive.RAW_NAMES), "too many App epochs")
        self.link, self.e = link, link.e
        self.address = profile["symbols"]["rtt"]
        self.lines, self.partial, self.identities = [], bytearray(), {}
        link.rtt_address = self.address
        link.ram_reads.append((self.address, self.address + 168))
        header = link.read(self.address, 24)
        b.require(header[:10] == b"SEGGER RTT" and struct.unpack_from("<II", header, 16) == (3, 3), "matched RTT not initialized")
        descriptor = self.descriptor(False)
        link.ram_reads.append((descriptor["buffer"], descriptor["buffer"] + descriptor["size"]))
        link.ram_writes = [(self.address + 40, self.address + 44)]
        self.raw = b.checked(self.e.out / passive.RAW_NAMES[index]).open("xb")

    def send(self, command):
        raise RuntimeError("passive upgrade observer does not send AT/RTT-down commands")


class ImageReader:
    def __init__(self, link, profiles, *, gate=None, channel_factory=UpChannel):
        self.link, self.profiles = link, profiles
        self.gate = gate or epoch.AppEpochGate(timeout=60)
        self.channel_factory = channel_factory
        self.profile = self.channel = self.channel_epoch = None
        self.channel_count = self.discarded_partial_bytes = 0

    def close(self):
        if self.channel is not None:
            self.discarded_partial_bytes += len(self.channel.partial)
            self.channel.raw.close()
        self.channel = self.channel_epoch = None
        self.link.ram_writes = []
        self.link.rtt_address = None

    def select(self, prefix):
        found = [value for value in self.profiles.values() if bytes.fromhex(value["prefix"]) == prefix]
        b.require(len(found) == 1, "unknown App executable/header; refuse stale addresses")
        value = found[0]
        if self.profile is not value:
            self.close()
            self.gate.invalidate("App image transition")
            self.profile = value
        return value

    def read32(self, address):
        allowed = (address, address + 4)
        if allowed not in self.link.ram_reads:
            self.link.ram_reads.append(allowed)
        return u32(self.link.read(address, 4))

    def in_app(self):
        try:
            self.link.running()
            return True
        except passive.Transition:
            return False

    def poll(self):
        try:
            if not self.in_app():
                self.close()
                self.gate.sample(lambda: False, lambda: 0, lambda: (0, 0))
                return None
            profile = self.select(self.link.read(c.APP, 0x460))
            symbols = profile["symbols"]
            sample = self.gate.sample(self.in_app, lambda: self.read32(symbols["tick"]),
                lambda: (self.read32(symbols["core_clock"]), self.read32(symbols["systick_reload"])))
            if sample is None:
                self.close()
                return None
            if self.channel_epoch != sample["epoch"]:
                self.close()
                self.channel = self.channel_factory(self.link, self.channel_count, profile)
                self.channel_count += 1
                self.channel_epoch = sample["epoch"]
            first = len(self.channel.lines)
            self.channel.pump()
            self.link.running()
            prefix = self.link.read(c.APP, 0x460)
            self.link.running()
            if prefix != bytes.fromhex(profile["prefix"]):
                # Boot may finish between phase checks. Discard this sample only
                # for a uniquely bound replacement, never an unknown App header.
                matches = [value for value in self.profiles.values() if bytes.fromhex(value["prefix"]) == prefix]
                if len(matches) == 1:
                    raise passive.Transition("mapped App changed during RTT sample")
                raise RuntimeError("App changed during RTT sample")
            return dict(sample=sample, channel=self.channel_count - 1, version=profile["identity"]["version_code"],
                        lines=self.channel.lines[first:])
        except passive.Transition:
            self.gate.invalidate("Boot/reset during RTT sample")
            self.close()
            return None
        except BaseException:
            self.gate.invalidate("observation error")
            self.close()
            raise

    def check_dwt(self):
        b.require(self.profile is not None and "profile" in self.profile["symbols"] and self.gate.ready,
                  "initialized diagnostic App required for timing admission")
        before = (self.read32(DEMCR), self.read32(DWT_CTRL), self.read32(DWT_COUNT))
        time.sleep(.02)
        self.link.running()
        after = (self.read32(DEMCR), self.read32(DWT_CTRL), self.read32(DWT_COUNT))
        b.require(before[0] & (1 << 24) and after[0] & (1 << 24) and before[1] & 1 and after[1] & 1 and
                  0 < ((after[2] - before[2]) & 0xFFFFFFFF) < 288000000,
                  "DWT disabled/frozen after debugger attachment")
        return dict(before=before, after=after, epoch=self.gate.epoch)


class Evidence(c.Evidence):
    NAMES = (*c.Evidence.NAMES, *passive.RAW_NAMES, "preflight.json", "state.json", "state.json.tmp",
             "boot-region.bin", "journal-before.bin", "cold-start-request.json", "cold-start-returned.json",
             "ota-reserved.json", "final-image.bin", "final-boot-region.bin", "final.json",
             "profile.bin", "profile.json", "dwt-admission.json", "backup-header.bin", "backup-image.bin")


def read_region(link, address, length, seconds=70):
    link.ram_reads.append((address, address + length))
    started, data = time.monotonic(), bytearray()
    while len(data) < length:
        b.require(time.monotonic() - started < seconds, "readback deadline")
        link.running()
        data.extend(link.read(address + len(data), min(16384, length - len(data))))
    link.running()
    return bytes(data)


def native_authority():
    receipt = b.ROOT / ".cache/p3-4-screening-20260922/resume/native-history-authorization.json"
    value = json.loads(receipt.read_text(encoding="utf-8"))
    b.require(value["approved"] and value["native_history_only"] and value["root"] == str(b.ROOT) and
              value["resolved_path"] == str(c.MRU), "exact native-history exception missing")
    b.io.checked_output(c.MRU.parent, c.MRU)
    return b.record(receipt)


def capture(run):
    b.require(re.fullmatch(r"[a-z0-9-]{1,48}", run), "run identity")
    cell = b.checked(b.OUT / "runs" / run)
    config = json.loads((cell / "config.json").read_text(encoding="utf-8"))
    b.require(config["id"] == run and config["baud"] in (115200, 460800, 921600) and
              config["capture_seconds"] == 4100 and config["group"] in ("bootstrap", "screen"), "run scope")
    b.require(base.owned.in_job(), "owned bounded runtime required")
    native_authority()
    assets, bindings = verified_assets(), load_bindings()
    group = assets["groups"][config["group"]]
    b.require(group == config["assets"], "run asset binding drift")
    for item in config["sources"]:
        b.require(b.record(item["path"]) == item, "running source binding drift")
    baseline = Path(group["baseline"]["path"]).read_bytes()
    target = Path(group["target"]["path"]).read_bytes()
    boot = Path(assets["whole_boot"]["path"]).read_bytes()
    state = CaptureState(group["baseline_identity"]["version_code"], group["target_identity"]["version_code"])
    out = b.checked(cell / "mcu")
    e, reader = Evidence(out), None
    link = BoundLink(e)
    started = time.monotonic()
    result = dict(started=b.now(), result="CAPTURE_GAP", run=run, config=b.record(cell / "config.json"),
        baseline_sha256=group["baseline"]["sha256"], target_sha256=group["target"]["sha256"],
        requested_baud=config["baud"], preflight_ready=False, reset_started=False,
        flash=0, at=0, ota_frames_sent_by_host=0, native_history_before=c.record(c.MRU), independent_acceptance=False)

    def raw(name, data):
        b.require(name in e.NAMES, "unlisted capture output")
        with b.checked(out / name).open("xb") as stream:
            stream.write(data)
            stream.flush()
            os.fsync(stream.fileno())
        return b.record(out / name)

    def boot_check(name):
        link.command("ExcludeFlashCacheRange 0x08000000-0x0800FFFF")
        data = read_region(link, 0x08000000, 65536)
        item = raw(name, data)
        b.require(data == boot, "whole Boot changed")
        return item

    try:
        link.connect()
        data = base.read_image(link, len(baseline))
        result["baseline_image"] = raw("image.bin", data)
        b.require(data == baseline, "baseline mismatch; no reset allowed")
        result["baseline_boot"] = boot_check("boot-region.bin")
        retained = u32(read_region(link, ERTC_DT20, 4))
        result["retained_word_before"] = retained
        b.require(retained == (0 if config["group"] == "bootstrap" else baud_word(config["baud"])),
                  "backup-register ownership or selected baud is not established")
        journal = read_region(link, 0x90300000, 4096)
        result["journal_before"] = raw("journal-before.bin", journal)
        result["journal_initially_erased"] = journal == b"\xff" * 4096
        reader = ImageReader(link, bindings["profiles"])
        e.save("cold-start-request.json", dict(time=b.now(), reset=1, purpose="planned image-bound cold-start control"))
        result["reset_started"] = True
        reset, go = link.sdk.JLINKARM_Reset, link.sdk.JLINKARM_Go
        reset.argtypes, reset.restype, go.argtypes, go.restype = [], None, [], None
        reset()
        go()
        e.save("cold-start-returned.json", dict(time=b.now(), result="RESET_RETURNED_NOT_YET_CONFIRMED"))
        ready_deadline, last_status = time.monotonic() + 60, 0
        while time.monotonic() - started < config["capture_seconds"]:
            observation = reader.poll()
            state.observe(observation)
            if state.can_begin() and not result["preflight_ready"]:
                b.require(link.read(c.APP, 0x460) == baseline[:0x460], "cold-start image changed")
                if config["group"] == "screen":
                    symbols = reader.profile["symbols"]
                    b.require(reader.read32(symbols["boot_baud"]) == config["baud"] and
                              reader.read32(symbols["retained_word"]) == baud_word(config["baud"]) and
                              reader.read32(symbols["retention_error"]) == 0, "selected baud was not retained on this startup")
                    result["dwt_admission"] = reader.check_dwt()
                    e.save("dwt-admission.json", result["dwt_admission"])
                result["preflight_ready"] = True
                e.save("preflight.json", dict(time=b.now(), **result, state=state.snapshot()))
            b.require(result["preflight_ready"] or time.monotonic() < ready_deadline, "fresh baseline BCB not observed")
            if (cell / "stop.json").exists():
                result["result"] = "CAPTURE_STOPPED"
                break
            if (cell / "arm.json").exists() and not state.begin_reserved:
                arm = json.loads((cell / "arm.json").read_text(encoding="utf-8"))
                b.require(arm["config"] == b.record(cell / "config.json") and
                          b.record(arm["start_inputs"]["path"]) == arm["start_inputs"], "invalid run reservation")
                b.require(config["capture_seconds"] - (time.monotonic() - started) >= RESERVE_SECONDS and
                          reader.gate.current(state.current_epoch) and link.read(c.APP, 0x460) == baseline[:0x460],
                          "reservation requires current baseline and full transfer/apply/readback reserves")
                state.reserve()
                e.save("ota-reserved.json", dict(time=b.now(), run=run, state=state.snapshot(),
                    meaning="user start is admitted; host does not send OTA frames"))
            if state.begin_reserved and config["group"] == "screen" and not (out / "profile.bin").exists() and observation:
                if observation["version"] == state.current_version:
                    address = reader.profile["symbols"]["profile"]
                    if (address, address + 288) not in link.ram_reads:
                        link.ram_reads.append((address, address + 288))
                    if u32(link.read(address + 12, 4)) == 1:
                        frozen = link.read(address, 288)
                        b.require(link.read(address, 288) == frozen, "frozen profile changed during capture")
                        result["profile_raw"] = raw("profile.bin", frozen)
                        try:
                            result["profile"] = decode_profile(frozen, config["baud"], group["package"]["bytes"])
                            e.save("profile.json", dict(epoch=state.current_epoch, **result["profile"]))
                        except RuntimeError as error:
                            result["profile_error"] = str(error)
                            e.save("profile.json", dict(epoch=state.current_epoch, valid=False, error=str(error)))
            if state.can_finish():
                b.require(reader.gate.current(state.current_epoch), "target epoch expired")
                data = base.read_image(link, len(target))
                result["final_image"] = raw("final-image.bin", data)
                b.require(data == target, "full raw target mismatch")
                result["final_boot"] = boot_check("final-boot-region.bin")
                address = reader.profile["symbols"]["sd_ready"]
                link.ram_reads.append((address, address + 1))
                result["sd_ready"] = link.read(address, 1)[0]
                result["final_identity"] = c.image_identity(data)
                result["profile_complete"] = config["group"] == "bootstrap" or "profile" in result
                result["result"] = "TARGET_VERIFIED_RETAINED"
                e.save("final.json", dict(time=b.now(), **result, state=state.snapshot()))
                break
            if time.monotonic() - last_status >= 2:
                b.io.write_json(b.ROOT, out / "state.json", dict(time=b.now(), **result, state=state.snapshot(),
                    remaining_seconds=config["capture_seconds"] - (time.monotonic() - started)), replace=True)
                last_status = time.monotonic()
            time.sleep(.1)
        else:
            result["result"] = "DEVICE_WINDOW_ENDED"
    except Exception as error:
        result["error"] = type(error).__name__ + ": " + str(error)
        e.emit("error", error=result["error"])
    finally:
        if reader:
            reader.close()
        link.close()
        result.update(ended=b.now(), seconds=time.monotonic() - started, state=state.snapshot(),
            reader_closed=not link.opened, native_history_after=c.record(c.MRU),
            discarded_partial_bytes=reader.discarded_partial_bytes if reader else 0)
        e.save("result.json", result)
        e.events.close()
        e.ledger.close()
    print("MCU_CAPTURE_RESULT", json.dumps(result), flush=True)
    return 0 if result["result"] in ("TARGET_VERIFIED_RETAINED", "CAPTURE_STOPPED") else 1


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("mode", choices=("prepare", "capture"))
    parser.add_argument("--run")
    args = parser.parse_args()
    b.require(Path.cwd().resolve() == b.ROOT and sys.flags.isolated and sys.flags.no_site and
              sys.dont_write_bytecode, "isolated explicit project execution required")
    if args.mode == "prepare":
        prepare()
    else:
        os.environ.update(b.environment())
        raise SystemExit(capture(args.run))
