"""Image-bound full-receive profiling and coarse install observation, no reset."""
from __future__ import annotations

import json
from pathlib import Path
import re
import struct
import threading
import time

APP, BOOT = 0x08010000, 0x08000000
DHCSR, VTOR = 0xE000EDF0, 0xE000ED08
BOOT_NAMES = ("g_boot_p1_state_resume", "g_boot_p1_state_value", "g_boot_p1_state_action",
              "g_boot_p1_state_status", "g_boot_p1_app_result", "g_boot_p1_qspi_result",
              "g_boot_p1_bcb_result", "g_boot_millis")


def require(value, message):
    if not value:
        raise RuntimeError(message)


def phase(vtor, dhcsr, halted):
    require(not halted, "MCU halted; never automatically resume it")
    require(vtor in (0, BOOT, APP), "unbound vector-table phase")
    return "reset" if dhcsr & (1 << 25) else "app" if vtor == APP else "boot"


def ring_tail(header, descriptor, raw):
    require(header[:10] == b"SEGGER RTT" and len(header) == 24 and
            struct.unpack_from("<II", header, 16) == (3, 3), "retained RTT signature/layout changed")
    require(len(descriptor) == 24, "retained RTT descriptor size")
    _, buffer, size, wr, rd, flags = struct.unpack("<6I", descriptor)
    require(16 <= size <= 16384 and len(raw) == size and
            0x20000000 <= buffer < buffer + size <= 0x20058000 and wr < size and rd < size,
            "invalid retained RTT ring")
    count = (wr - rd) % size
    first = min(count, size - rd)
    pending = raw[rd:rd + first] + raw[:count - first]
    return pending, dict(buffer=buffer, size=size, wr=wr, rd=rd, flags=flags)


def apply_timing(texts, target):
    values = []
    for text in texts:
        values += [(int(a), int(b), int(v)) for a, b, v in re.findall(
            r"(?:^|\n)BLEACT: ok apply=(\d+)ms stage=(\d+)ms vcode=(\d+)\r?\n", text)]
    require(values and len(set(values)) == 1 and values[0][2] == target,
            "missing/conflicting target-bound BLEACT timing")
    apply, stage, _ = values[0]
    require(apply > 0 and stage > 0, "invalid device-tick installation timing")
    return dict(candidate_apply_ticks_ms=apply, backup_staged_ticks_ms=stage,
                clock="receiver millis(); Flash interrupt masking may cause wall-time drift",
                wall_seconds=False, distinct_marker_values=len(set(values)))


def install_restore_timing(texts, clock_hz, *, package_kind="full"):
    """Decode complete, phase-bound N04 summaries, not whole-phase wall time."""
    require(package_kind in ("full", "patch"), "invalid installation package kind")
    require(type(clock_hz) is int and clock_hz > 0, "invalid receiver cycle frequency")
    pattern = re.compile(
        r"P34INSTALL: phase=(full|patch|backup) rc=(-?\d+) opt=(\d+) hz=(\d+) calls=(\d+) reused=(\d+) "
        r"fail=(\d+) invalid=(\d+) ticks=(\d+) legacy=(\d+):(\d+) reuse=(\d+):(\d+) max=(\d+)\r?\n")
    phases = {}
    for text in texts:
        for line in text.splitlines(keepends=True):
            if "P34INSTALL:" not in line:
                continue
            match = pattern.fullmatch(line)
            require(match is not None, "malformed/truncated N04 restore summary")
            phase = match[1]
            numbers = tuple(map(int, match.groups()[1:]))
            require(phase not in phases or phases[phase] == numbers, "conflicting N04 restore summaries")
            phases[phase] = numbers
    require(set(phases) == {package_kind, "backup"}, "missing or mixed N04 install/backup restore summaries")
    result = {}
    for name, numbers in phases.items():
        rc, opt, hz, calls, reused, failures, invalid, ticks, legacy_hi, legacy_lo, reuse_hi, reuse_lo, maximum = numbers
        require(all(0 <= value <= 0xffffffff for value in numbers[1:]), "N04 restore field outside uint32")
        require(rc == 0 and opt == 1 and hz == clock_hz and failures == invalid == 0,
                "N04 restore failed, disabled or has invalid cycle samples")
        require(calls > 1 and 0 <= reused < calls and maximum > 0, "N04 entry/full initialization counts invalid")
        legacy_cycles = (legacy_hi << 32) | legacy_lo
        reuse_cycles = (reuse_hi << 32) | reuse_lo
        require(calls - reused <= legacy_cycles <= (calls - reused) * maximum and
                reused <= reuse_cycles <= reused * maximum and
                maximum <= legacy_cycles + reuse_cycles <= calls * maximum,
                "N04 cycle totals disagree with successful call counts")
        result[name] = dict(calls=calls, reused_status_writes=reused, legacy_calls=calls-reused,
            failures=failures, invalid_cycle_samples=invalid, ticks_ms=ticks,
            legacy_cycles=legacy_cycles, reuse_cycles=reuse_cycles, max_cycles=maximum,
            legacy_seconds=legacy_cycles/clock_hz, reuse_seconds=reuse_cycles/clock_hz)
    return dict(result="INSTALL_RESTORE_PROFILE_VERIFIED", clock_hz=clock_hz, phases=result,
        clock="sum of bounded per-call DWT deltas; unchanged admitted receiver clock required",
        whole_installation_wall_time=False, strict_same_package_AB=False)


def boot_interval(samples, receiver, target, *, require_confirmation=True):
    require(samples, "native samples missing")
    last = -1
    for item in samples:
        require(last <= item["start_ns"] <= item["end_ns"], "invalid native monotonic brackets")
        last = item["end_ns"]
    indexes = [n for n, item in enumerate(samples) if item["phase"] == "boot"]
    require(indexes, "Boot was not sampled")
    first, final = indexes[0], indexes[-1]
    require(all(item["phase"] in ("boot", "reset") for item in samples[first:final + 1]),
            "multiple Boot intervals cannot be merged")
    before = [item for item in samples[:first] if item.get("version") == receiver and item["phase"] == "app"]
    after = [item for item in samples[final + 1:] if item.get("version") == target and item["phase"] == "app"]
    require(before and after, "Boot boundaries lack bound receiver/target App samples")
    require(after[0].get("initialized") is True, "target App boundary is not initialized")
    ready = [item for item in after if item.get("confirmed") is True and item.get("initialized") is True]
    if require_confirmation:
        require(ready, "target App initialized/CONFIRMED sample missing")
    return dict(clock="host monotonic; VTOR-observed Boot interval, not internal copy time",
        lower_seconds=max(0, samples[final]["start_ns"] - samples[first]["end_ns"]) / 1e9,
        upper_seconds=(after[0]["end_ns"] - before[-1]["start_ns"]) / 1e9,
        entry_bracket_ns=[before[-1]["start_ns"], samples[first]["end_ns"]],
        exit_bracket_ns=[samples[final]["start_ns"], after[0]["end_ns"]],
        target_confirmed_bracket_ns=[ready[0]["start_ns"], ready[0]["end_ns"]] if ready else None,
        confirmation_observed=bool(ready), requires_confirmation=require_confirmation,
        scope="Boot residency only; final update confirmation is separate" if not require_confirmation else "Boot and confirmation observation",
        samples=len(indexes), outcome_fields_are_per_block_progress=False)


def full_metrics(messages, total, device):
    values = [json.loads(line.removeprefix("OTA_LINK_STATS ")) for line in messages.splitlines()
              if line.startswith("OTA_LINK_STATS ")]
    values = [item for item in values if item.get("label") == "upgrade"]
    require(len(values) == 1, "one original full-upgrade link summary required")
    value, count = values[0], (total + 127) // 128
    transfer, binding = value["transfer"], value["bind"]
    require(value["device"].lower() == device.lower() and value["clock"] == "stopwatch-mono-us" and
            transfer["outcome"] == "ok" and transfer["elapsedUs"] > 0 and
            transfer["elapsedUs"] == transfer["endAckUs"] - transfer["startUs"] and
            transfer["segmentsUnique"] == transfer["segmentSendTotal"] == count and
            transfer["retransmitFrames"] == 0 and transfer["durable"]["finalOff"] == total and
            transfer["ackSamples"] == "complete" and transfer["ackLatency"]["count"] == count and
            transfer["ackEarlyInvalid"] == transfer["ackEarlyUnsent"] == 0,
            "full transfer has incomplete/invalid samples, nonzero retries or wrong identity")
    require(binding["writeMode"] == "without" and binding["mtuChunkBytes"] == 244 and
            binding["mtuSource"] == "negotiated", "full link mode/MTU differs from the declared cell")
    end = re.findall(r"^OTA_MONO MONO_END_ACK_OK monoUs=(\d+) wallUs=\d+ durable=(\d+)\r?$", messages, re.M)
    reboot = re.findall(r"^OTA_MONO MONO_REBOOT_VERIFIED monoUs=(\d+) wallUs=\d+\r?$", messages, re.M)
    require(len(end) == len(reboot) == 1 and int(end[0][1]) == total and int(reboot[0]) > int(end[0][0]),
            "original END/reboot confirmation markers missing or conflicting")
    return dict(transfer_seconds=transfer["elapsedUs"] / 1e6,
        throughput_kib_s=total / 1024 / (transfer["elapsedUs"] / 1e6),
        installation_reconnect_seconds=(int(reboot[0]) - int(end[0][0])) / 1e6,
        transfer=transfer, binding=binding, gatt_writes=value["gattWrites"],
        discoveries=value["discovers"], platform_writes=value["platformWrites"],
        sample_scope="one complete successor transfer; not same-package A/B or the 1 MiB reference")


class Trace:
    """One thread owns one native link; it is joined before the final readback."""

    def __init__(self, c, out, expected_run):
        self.c, self.out, self.expected_run = c, c.checked(out), expected_run
        self.ready, self.stop_requested = threading.Event(), threading.Event()
        self.error = None
        self.thread = threading.Thread(target=self.run, name="p34-full-native", daemon=True)
        self.channels, self.tail, self.profile = [], None, None
        self.last_sample_ns = 0
        self.start_ready = False

    def start(self):
        self.thread.start()
        require(self.ready.wait(65), "native full observer did not become ready")
        self.require_ready()

    def require_ready(self):
        require(self.ready.is_set() and self.start_ready and self.error is None and self.thread.is_alive() and
                0 <= time.monotonic_ns() - self.last_sample_ns < 10_000_000_000,
                "native full observer unavailable: " + str(self.error))

    def stop(self):
        self.stop_requested.set()
        self.thread.join(20)
        require(not self.thread.is_alive(), "native reader closure uncertain; do not open another reader")
        return self.c.record(self.out / "result.json")

    def run(self):
        c, m, out = self.c, self.c.m, self.out
        link = reader = e = stream = None
        result = dict(result="TRACE_INCOMPLETE", receiver=c.receiver_version, target=c.target_version,
            package=c.screen, bindings=c.bindings, target_bindings=c.full_assets["target_bindings"],
            expected_run=self.expected_run, source=c.record(Path(__file__)),
            host_reset=False, host_flash=False, host_tuning=False, rtt_down_commands=False)
        try:
            c.native_authority()
            boot_record = (c.bindings["boot_map"] if "boot_map" in c.bindings else
                           c.read(c.HERE / "n03/mcu-bindings.json")["boot_map"])
            require(c.record(c.checked(boot_record["path"])) == boot_record, "admitted Boot MAP changed")
            boot_map = Path(boot_record["path"]).read_text(encoding="utf-8")
            boot_symbols = {name: m.map_bss(boot_map, name, 4) for name in BOOT_NAMES}
            require(all(0x20000000 <= address < 0x20057000 for address in boot_symbols.values()), "Boot symbol outside RAM")
            result.update(boot_map=boot_record, boot_symbols=boot_symbols, native_before=c.record(m.c.MRU))
            for name in (*m.Evidence.NAMES, "samples.jsonl", "result.json", "end-profile.bin", "end-profile.json",
                         "retained-rtt-header.bin", "retained-rtt-descriptor.bin", "retained-rtt-ring.bin",
                         "retained-rtt-pending.bin", "retained-rtt-partial.bin", "retained-rtt.json", "tail-gap.json"):
                c.checked(out / name)
            e = m.Evidence(out)
            link = c.tune.ControlLink(e, writable=True)
            link.connect()
            require(link.read(APP, 0x460) == bytes.fromhex(c.bindings["profile"]["prefix"]), "trace receiver changed")

            def read(address, size):
                if (address, address + size) not in link.ram_reads:
                    link.ram_reads.append((address, address + size))
                return link.read(address, size)

            def word(address):
                return struct.unpack("<I", read(address, 4))[0]

            def control():
                dhcsr, vtor = word(DHCSR), word(VTOR)
                return dict(phase=phase(vtor, dhcsr, bool(link.sdk.JLINKARM_IsHalted())), dhcsr=dhcsr, vtor=vtor)

            owner = self

            class Channel(m.UpChannel):
                def __init__(self, link, index, profile):
                    super().__init__(link, index, profile)
                    owner.channels.append(dict(version=profile["identity"]["version_code"], path=self.raw.name))

            class Reader(m.ImageReader):
                def close(self):
                    if self.channel is not None and self.profile["identity"]["version_code"] == c.receiver_version and owner.tail is None:
                        try:
                            if control()["phase"] == "boot":
                                address = self.channel.address
                                header, descriptor = read(address, 24), read(address + 24, 24)
                                _, buffer, size, _, _, _ = struct.unpack("<6I", descriptor)
                                require(16 <= size <= 16384 and 0x20000000 <= buffer < buffer + size <= 0x20058000,
                                        "invalid retained ring address")
                                raw = read(buffer, size)
                                pending, metadata = ring_tail(header, descriptor, raw)
                                require(control()["phase"] == "boot" and read(address, 24) == header and
                                        read(address + 24, 24) == descriptor, "retained RTT changed during Boot read")
                                identity = self.channel.identities[False]
                                require((metadata["buffer"], metadata["size"], metadata["flags"]) == identity,
                                        "retained RTT no longer matches the admitted receiver channel")
                                files = {key: c.raw(out / ("retained-rtt-" + key + ".bin"), value) for key, value in
                                    (("header", header), ("descriptor", descriptor), ("ring", raw), ("pending", pending),
                                     ("partial", bytes(self.channel.partial)))}
                                c.save(out / "retained-rtt.json", dict(files=files, descriptor=metadata,
                                    receiver=c.receiver_version, consumed=False, phase="retained-R-buffer-during-Boot"))
                                owner.tail = c.record(out / "retained-rtt.json")
                        except Exception as error:
                            if not (out / "tail-gap.json").exists():
                                c.save(out / "tail-gap.json", dict(error=type(error).__name__, detail=str(error)))
                    super().close()

            profiles = {str(c.receiver_version): c.bindings["profile"],
                        str(c.target_version): c.full_assets["target_bindings"]["profile"]}
            reader = Reader(link, profiles, channel_factory=Channel)
            stream = c.checked(out / "samples.jsonl").open("x", encoding="utf-8", newline="\n")
            deadline, previous_phase, initialized = time.monotonic() + 2700, None, False
            while not self.stop_requested.is_set():
                require(time.monotonic() < deadline, "finite full native observation deadline")
                start = time.monotonic_ns()
                state = control()
                sample = dict(start_ns=start, **state)
                if state["phase"] == "app":
                    if previous_phase in ("boot", "reset"):
                        reader.close()
                        reader.gate = m.epoch.AppEpochGate(timeout=60)
                    observation = reader.poll()
                    if observation is not None:
                        version = observation["version"]
                        layout = c.bindings["layout"]
                        confirmed = read(layout["bcb_state"], 1) == b"\x04" and read(layout["confirm_done"], 1) == b"\x01"
                        sample.update(version=version, tick=observation["sample"]["tick"], initialized=True, confirmed=confirmed,
                                      channel=observation["channel"], epoch=observation["sample"]["epoch"])
                        if version == c.receiver_version:
                            address, size = reader.profile["symbols"]["profile"], c.instrumentation["size"]
                            frozen = read(address, size)
                            header = dict(zip(m.HEADERS, struct.unpack_from("<24I", frozen)))
                            if header["ready"] == 1 and header["run"] == self.expected_run and self.profile is None:
                                require(read(address, size) == frozen, "frozen END profile changed while reading")
                                link.running()
                                require(link.read(APP, 0x460) == bytes.fromhex(reader.profile["prefix"]),
                                        "receiver changed during END profile read")
                                self.profile = c.raw(out / "end-profile.bin", frozen)
                                decoded = c.helper.decode_terminal(m, frozen, run=self.expected_run, baud=921600,
                                    total=c.screen["bytes"], layout=c.instrumentation, terminal=0)
                                c.save(out / "end-profile.json", decoded)
                        if not initialized:
                            require(version == c.receiver_version and confirmed, "native readiness is not the retained R")
                            reader.check_dwt()
                            initialized = True
                    else:
                        sample["initialized"] = False
                else:
                    reader.close()
                    if previous_phase == "app":
                        reader.gate.invalidate("ordinary OTA reboot")
                    if state["phase"] == "boot":
                        sample["boot"] = {name: word(address) for name, address in boot_symbols.items()}
                final = control()
                sample.update(end_ns=time.monotonic_ns(), final_phase=final["phase"])
                if final["phase"] != state["phase"]:
                    sample["phase"] = "reset"
                    sample.pop("version", None)
                stream.write(json.dumps(sample) + "\n")
                stream.flush()
                self.last_sample_ns = sample["end_ns"]
                self.start_ready = (sample["phase"] == "app" and sample.get("version") == c.receiver_version and
                                    sample.get("initialized") is True and sample.get("confirmed") is True)
                if initialized and self.start_ready:
                    self.ready.set()
                previous_phase = state["phase"]
                self.stop_requested.wait(.1)
            result["result"] = "TRACE_CLOSED"
        except Exception as error:
            self.error = type(error).__name__ + ": " + str(error)
            result["error"] = self.error
        finally:
            if reader:
                reader.close()
            if link:
                link.close()
            if stream:
                stream.close()
            result.update(reader_closed=not link or not link.opened, profile=self.profile, retained_tail=self.tail,
                          channels=[dict(version=item["version"], raw=c.record(item["path"])) for item in self.channels],
                          native_after=c.record(m.c.MRU))
            if (out / "samples.jsonl").exists():
                result["samples"] = c.record(out / "samples.jsonl")
            c.save(out / "result.json", result)
            if e:
                e.events.close()
                e.ledger.close()
            self.ready.set()


def analyze(c, cell_out):
    """Read only original bytes; a missing trace does not replay a successful OTA."""
    out = cell_out / "native-trace"
    result = c.read(out / "result.json")
    require(result["reader_closed"] is True and result["result"] == "TRACE_CLOSED" and
            result["bindings"] == c.bindings and result["package"] == c.screen and
            result["target_bindings"] == c.full_assets["target_bindings"], "full native trace is incomplete or differently bound")
    expected_run = (c.read(cell_out / "fresh-begin.json")["before"]["profile"]["run"] + 1) & 0xffffffff
    require(result["expected_run"] == expected_run and result["profile"], "full receive generation/profile missing")

    def original(item):
        require(c.record(c.checked(item["path"])) == item, "original full trace bytes changed")
        return Path(item["path"]).read_bytes()

    profile = c.helper.decode_terminal(c.m, original(result["profile"]), run=expected_run, baud=921600,
        total=c.screen["bytes"], layout=c.instrumentation, terminal=0)
    require(profile["clean_counters"], "full receive MCU error counters are nonzero")
    texts = [original(item["raw"]).decode("ascii", "replace") for item in result["channels"] if item["version"] == c.receiver_version]
    if result["retained_tail"]:
        tail = json.loads(original(result["retained_tail"]))
        values = {key: original(item) for key, item in tail["files"].items()}
        pending, descriptor = ring_tail(values["header"], values["descriptor"], values["ring"])
        require(pending == values["pending"] and descriptor == tail["descriptor"] and tail["consumed"] is False,
                "retained Boot ring evidence differs")
        texts.append((values["partial"] + pending).decode("ascii", "replace"))
    samples = [json.loads(line) for line in original(result["samples"]).decode().splitlines()]
    value = dict(result="N03_FULL_RECEIVE_PROFILE_VERIFIED", original=c.record(out / "result.json"), profile=profile)
    # Preserve a useful full receive result if a coarse install marker was missed.
    for key, derive in (("activation", lambda: apply_timing(texts, c.target_version)),
                        ("boot_residency", lambda: boot_interval(samples, c.receiver_version, c.target_version,
                                                                require_confirmation=False)),
                        ("boot", lambda: boot_interval(samples, c.receiver_version, c.target_version))):
        try:
            value[key] = derive()
        except RuntimeError as error:
            value[key] = dict(result="EVIDENCE_GAP", detail=str(error))
    if getattr(c, "install_restore_expected", False):
        try:
            require(profile["clock_ok"] == 1 and "candidate_apply_ticks_ms" in value["activation"],
                    "N04 clock/target-bound activation evidence missing")
            value["install_restore"] = install_restore_timing(
                texts, profile["clock_hz"], package_kind=getattr(c, "package_kind", "full"))
        except RuntimeError as error:
            value["install_restore"] = dict(result="EVIDENCE_GAP", detail=str(error))
    return value
