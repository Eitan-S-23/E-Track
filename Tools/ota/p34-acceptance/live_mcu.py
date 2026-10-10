"""P3-4 standard Commander/RTTLogger adapter, exact images and no Flash algorithm."""
import csv
import hashlib
import io
import os
import re
import struct
import time
import zlib

import live_host as h
import metrics

START = ["exec DisableAutoUpdateFW", "exec SetRestartOnClose = 0",
         "exec InhibitConnectRetries = 1", "exec SetEnableMemCache = 0", "connect",
         "exec ExcludeFlashCacheRange 0x08000000-0x080FFFFF"]
REGISTERS = dict(vtor=0xe000ed08, cfsr=0xe000ed28, hfsr=0xe000ed2c,
                 dhcsr=0xe000edf0, sdio=0x4002c434, freeze=0xe0042008)
SYMBOLS = dict(health="_ZL12g_ota_health", confirmed="_ZL18g_ota_confirm_done",
    state="_ZL20g_ota_state_snapshot", snapped="_ZL19g_ota_state_snapped",
    sd="_ZL10SD_IsReady", owner="_ZL19g_ota_overlay_owner", session="_ZL13s_ble_session",
    rtt="_SEGGER_RTT", main_loop="_ZN3HAL10HAL_UpdateEv",
    disabled="_ZL19g_qspi_ota_disabled", jedec="_ZL15g_qspi_jedec_id")
INSTALL_PAIRS = {("initial", "base"), ("base", "maintenance"),
                 ("maintenance", "base"), ("target", "restore")}


def symbols(text):
    found = {}
    for line in text.splitlines():
        match = re.fullmatch(r"([0-9a-fA-F]{8}) (?:([0-9a-fA-F]+) )?([A-Za-z]) (\S+)", line)
        if match:
            name = match[4]
            if name in found:
                found[name] = None
            else:
                found[name] = (int(match[1], 16), int(match[2], 16) if match[2] else None)
    return found


def byte_member(disassembly, name, size):
    # Release ELF has no type DWARF. These two actual accessor functions each
    # contain one byte load; use its operand, never a remembered struct offset.
    h.require("<" + name + ">:" in disassembly, "wrong accessor disassembly")
    offsets = re.findall(r"\bldrb(?:\.w)?\s+r0,\s*\[r0,\s*#(\d+)\]", disassembly)
    h.require(len(offsets) == 1 and "bx\tlr" in disassembly and 0 <= int(offsets[0]) < size,
              "unrecognized session accessor; do not guess offsets")
    return int(offsets[0])


def health_gate(samples):
    a, b = (struct.unpack("<9I", samples[k]) for k in ("health0", "health1"))
    scalar = lambda k: int.from_bytes(samples[k], "little")
    h.require(samples["state"] == b"\x04" and samples["snapped"] == samples["confirmed"] == b"\x01",
              "current boot is not confirmed")
    h.require(samples["sd"] == b"\x01" and samples["owner"] == samples["active"] == samples["isr"] == b"\x00",
              "SD unavailable or OTA/storage owner active")
    h.require(scalar("vtor") == 0x08010800 and scalar("cfsr") == scalar("hfsr") == 0 and
              not scalar("dhcsr") & 0xa0000 and not scalar("sdio") & 0x3800, "fault/halt/storage/pending state")
    h.require(a[3] == b[3] and a[7:] == b[7:] == (1, 1) and b[4] > a[4] and b[5] > a[5],
              "boot changed or main loop/watchdog did not advance")
    return dict(health=[a, b], registers={k: scalar(k) for k in REGISTERS}, confirmed_state=4,
                confirmation_source="current initialized App BCB snapshot; not an EEPROM dump")


def stack_observation(guard, stack):
    h.require(len(guard) == 32 and len(stack) == 8192, "unexpected bound stack layout")
    h.require(guard == b"\x5a" * 32, "stack guard changed")
    free = 0
    for offset in range(0, len(stack), 4):
        if stack[offset:offset + 4] != b"\xa5" * 4:
            break
        free += 4
    h.require(free > 0, "stack paint exhausted; high-water unknown")
    return dict(guard_intact=True, free_painted_bytes=free, high_water_bytes=len(stack)-free,
                scope="Paint observed at this read, not a whole-program worst-case proof")


def slot_header(raw, kind):
    h.require(len(raw) == 32, "slot header read length")
    if raw == b"\xff" * 32:
        return dict(erased=True)
    h.require(raw[:4] == b"ETSL" and raw[4:8] == bytes([kind, 255, 255, 255]) and
        raw[28:] == struct.pack("<I", 0x434f4d54), "uncommitted/invalid slot header; reconcile")
    size, crc, version = struct.unpack_from("<3I", raw, 8)
    h.require(0 < size <= (0x180000 if kind == 3 else 0xf0000), "slot outside capacity")
    return dict(erased=False, bytes=size, crc32=crc, version=version, sha8=raw[20:28].hex())


def journal_observation(raw, package):
    h.require(len(raw) == 4096, "staging journal size")
    if raw == b"\xff" * 4096:
        return dict(erased=True, expected_begin_durable=0, committed_target=None)
    journal = raw[0x40:0x6c]
    h.require(journal[:4] == b"ETRJ" and zlib.crc32(journal[:40]) == struct.unpack_from("<I", journal, 40)[0],
              "invalid staging journal; preserve and reconcile")
    total = struct.unpack_from("<I", journal, 36)[0]
    h.require(0 < total <= 0x180000, "invalid journal length")
    blocks = (total + 4095) // 4096
    bits = [(raw[0x70 + i // 8] >> (i % 8)) & 1 for i in range(512)]
    first = next((i for i, bit in enumerate(bits) if bit), 512)
    h.require(first <= blocks and all(bits[first:]), "noncontiguous staging bitmap")
    durable = min(total, first * 4096)
    matches = journal[4:36].hex() == package["sha256"] and total == package["bytes"]
    committed = slot_header(raw[:32], 3)["version"] if raw[28:32] == struct.pack("<I", 0x434f4d54) else None
    return dict(erased=False, package_sha256=journal[4:36].hex(), bytes=total, durable=durable,
        matches_reference=matches, expected_begin_durable=durable if matches else 0, committed_target=committed)


def storage_observation(samples, package=None):
    h.require(samples["disabled"] == b"\x00", "OTA storage disabled")
    jedec = int.from_bytes(samples["jedec"], "little")
    h.require(jedec in (0xef4018, 0x1c4018, 0x1c4017, 0xef4017), "unqualified QSPI identity/capacity")
    return dict(jedec=jedec, capacity_bytes=1 << (jedec & 255),
        slots={name: slot_header(samples[name], kind) for name, kind in
               (("candidate_slot", 1), ("backup_slot", 2), ("recovery_slot", 4))},
        staging_header_hex=samples["staging"][:32].hex(),
        staging_journal_sha256=hashlib.sha256(samples["staging"]).hexdigest(),
        staging_erased=samples["staging"] == b"\xff" * 4096,
        journal=journal_observation(samples["staging"], package) if package is not None else None)


def restore_gate(raw, base, boot, phase):
    h.require(len(raw) == 640, "restore mailbox size")
    w = struct.unpack_from("<16I", raw)
    h.require(w[:4] == (0x41343352, 1, phase, 0) and w[8:12] ==
              (30287, 30286, len(base), __import__("zlib").crc32(base)), "restore phase/identity/error")
    h.require(raw[576:608].hex() == boot and raw[608:640].hex() == __import__("hashlib").sha256(base).hexdigest(),
              "restore did not verify the bound Boot/backup")
    h.require(raw[319] == 0x55, "missing EEPROM initialization marker")
    if phase == 1:
        h.require(w[5] == w[6] == w[12] == 0 and w[7] in (1, 2), "restore already armed/mutated")
    else:
        h.require(w[12:15] == (1, 0, 1) and raw[192:320] == raw[448:576],
                  "rollback commit/journal/config preservation failed")
    return dict(phase=phase, tick=w[4], mutation_started=w[12])


class MCU:
    def __init__(self, plan, out):
        self.plan, self.out = plan, h.checked(out)
        self.env, self.count, self.logger = h.environment(out), 0, None
        self.bound = {}

    def tool(self, name):
        return h.pinned(self.plan["tools"][name])

    def bind(self, role):
        if role in self.bound:
            return self.bound[role]
        image = self.plan["images"][role]
        binary, elf, mapping = (h.pinned(image[k]) for k in ("image", "elf", "map"))
        out = h.fresh(self.out / ("symbols-" + role))
        raw = h.checked(out / "elf.bin")
        h.command(out, "objcopy", [self.tool("objcopy"), "-O", "binary", elf, raw], self.env, seconds=30)
        original, finalized = raw.read_bytes(), binary.read_bytes()
        h.require(len(original) == len(finalized) and original[:0x400] == finalized[:0x400] and
            original[0x460:] == finalized[0x460:], "ELF is not this finalized executable")
        nm = h.command(out, "nm", [self.tool("nm"), "-n", "-S", elf], self.env, seconds=30).decode("utf-8")
        table = symbols(nm)
        names = ["_SEGGER_RTT", "g_restore_control"] if role == "restore" else list(SYMBOLS.values())
        if role == "maintenance":
            names += ["g_p34_retained_word", "g_p34_retention_error"]
        for name in names:
            h.require(table.get(name) is not None, "missing/ambiguous ELF symbol: " + name)
        rtt = table["_SEGGER_RTT"][0]
        matches = re.findall(r"(?m)^\s*(0x[0-9a-fA-F]+)\s+_SEGGER_RTT\s*$", mapping.read_text(encoding="utf-8"))
        h.require(len(matches) == 1 and int(matches[0], 16) == rtt, "map/ELF RTT mismatch")
        offsets = {}
        if role != "restore":
            for name in ("__StackGuardStart", "__StackGuardEnd", "__StackLimit", "__StackTop"):
                h.require(table.get(name) is not None, "missing stack symbol " + name)
            h.require(table["__StackGuardEnd"][0] - table["__StackGuardStart"][0] == 32 and
                table["__StackTop"][0] - table["__StackLimit"][0] == 8192, "wrong stack reservation")
            size = table[SYMBOLS["session"]][1]
            for key, name in (("active", "ota_ble_session_active"), ("isr", "ota_ble_session_isr_active")):
                text = h.command(out, key, [self.tool("objdump"), "-d", "--disassemble=" + name, elf],
                                 self.env, seconds=30).decode("utf-8")
                offsets[key] = byte_member(text, name, size)
        if role in ("base", "target"):
            for name, size in (("g_ota_link_metrics", 420), ("g_ota_metrics_publish_bytes", 4), ("system_core_clock", 4)):
                h.require(table.get(name) is not None and table[name][1] == size, "wrong production metric/clock ABI")
                hits = re.findall(r"(?m)^\s*(0x[0-9a-fA-F]+)\s+" + name + r"\s*$", mapping.read_text(encoding="utf-8"))
                h.require(len(hits) == 1 and int(hits[0], 16) == table[name][0], "metric map/ELF mismatch")
            h.require(table.get("SystemTickCount") is not None and table["SystemTickCount"][1] == 4, "missing live tick symbol")
        result = dict(image=binary, table=table, offsets=offsets, rtt=rtt)
        h.save(out / "result.json", dict(image=image, rtt=rtt, offsets=offsets,
            symbols={name: table[name] for name in names}))
        self.bound[role] = result
        return result

    def execute(self, commands, reads, label, *, seconds=180):
        h.require(self.logger is None, "Commander must not race the RTT reader")
        self.count += 1
        out = h.fresh(self.out / ("%04d-" % self.count + label))
        self.foreign_debuggers(out)
        paths = {name: h.checked(out / (name + ".bin")) for name in reads}
        lines = list(START)
        for command in commands:
            if isinstance(command, tuple):
                name, address, size = command
                h.require(name in paths and 0 < size <= 0x180000, "unbound memory read")
                lines.append('savebin "%s", 0x%08X, 0x%X' % (paths[name], address, size))
            else:
                lines.append(command)
        lines.append("qc")
        for leaf in ("commands.jlink", "settings.jlink", "sdk.log"):
            h.checked(out / leaf)
        h.raw(out / "commands.jlink", ("\n".join(lines) + "\n").encode("ascii"))
        console = h.command(out, "commander", [self.tool("commander"), "-Device", "AT32F435RGT7",
            "-If", "SWD", "-Speed", "1000", "-USB", str(self.plan["probe_serial"]),
            "-AutoConnect", "0", "-ExitOnError", "1", "-NoGui", "1",
            "-SettingsFile", out / "settings.jlink", "-Log", out / "sdk.log",
            "-CommandFile", out / "commands.jlink"], self.env, seconds=seconds)
        data = {}
        for name, size in reads.items():
            h.require(paths[name].is_file() and paths[name].stat().st_size == size, "missing/short original readback")
            data[name] = paths[name].read_bytes()
        return data, console.decode("utf-8", "replace"), out

    def foreign_debuggers(self, out):
        h.require(os.name == "nt", "this physical device route requires the authorized Windows host")
        raw = h.command(out, "processes", ["tasklist", "/FO", "CSV", "/NH"], self.env, seconds=15)
        names = {row[0].lower() for row in csv.reader(io.StringIO(raw.decode("utf-8", "replace"))) if row}
        excluded = {"jlink.exe", "jlinkrttlogger.exe", "jlinkrttviewer.exe", "jlinkrttclient.exe",
                    "jlinkgdbserver.exe", "jlinkgdbservercl.exe"}
        h.require(not names & excluded, "another debugger/RTT reader exists; do not kill or compete")

    def read(self, address, size, label):
        return self.execute([("value", address, size)], dict(value=size), label)[0]["value"]

    def inspect(self, role, label="inspect"):
        bound = self.bind(role)
        image = bound["image"].read_bytes()
        h.require(0x460 <= len(image) <= 0xf0000, "App write/read bounds")
        fields = {key: (bound["table"][name][0], 36 if key == "health" else 4 if key == "jedec" else 1)
                  for key, name in SYMBOLS.items() if key not in ("session", "rtt", "main_loop")}
        session = bound["table"][SYMBOLS["session"]][0]
        fields.update({key: (session + offset, 1) for key, offset in bound["offsets"].items()})
        fields.update({key: (address, 4) for key, address in REGISTERS.items()})
        reads = dict(boot=65536, app=len(image), header_after=96, health0=36, health1=36)
        commands = [("boot", 0x08000000, 65536), ("app", 0x08010000, len(image)),
                    ("health0", fields.pop("health")[0], 36), "sleep 1000",
                    ("health1", bound["table"][SYMBOLS["health"]][0], 36)]
        for name, (address, size) in fields.items():
            commands.append((name, address, size))
            reads[name] = size
        commands.append(("header_after", 0x08010400, 96))
        for name, address, size in (("guard", bound["table"]["__StackGuardStart"][0], 32),
                ("stack", bound["table"]["__StackLimit"][0], 8192),
                ("candidate_slot", 0x90000000, 32), ("backup_slot", 0x90100000, 32),
                ("recovery_slot", 0x90200000, 32), ("staging", 0x90300000, 4096)):
            commands.append((name, address, size))
            reads[name] = size
        data, _, out = self.execute(commands, reads, label, seconds=300)
        h.require(data["boot"] == h.pinned(self.plan["boot"]).read_bytes(), "Boot identity changed")
        h.require(data["app"] == image and data["header_after"] == image[0x400:0x460], "wrong/currently changing App")
        result = health_gate(data)
        result.update(stack=stack_observation(data["guard"], data["stack"]), storage=storage_observation(data, self.plan["package"]))
        result.update(role=role, image=self.plan["images"][role]["image"], boot=h.record(out / "boot.bin"))
        h.save(out / "result.json", result)
        return result

    def install(self, current, target):
        h.require((current, target) in INSTALL_PAIRS, "unsafe direct install; target-to-base requires ordinary Boot rollback")
        before = self.inspect(current, "pre-install")
        staged = before["storage"]["journal"]["committed_target"]
        h.require(staged is None or staged <= (30287 if current == "target" else 30286),
                  "newer committed staging/pending apply; do not replace the App")
        bound, destination = self.bind(current), self.bind(target)
        address = bound["table"][SYMBOLS["main_loop"]][0]
        freeze = before["registers"]["freeze"]
        data, console, _ = self.execute(["w4 0xE0042008, 0x%08X" % (freeze | 0x1000),
            "SetBP 0x%08X, T, H" % address, "g", "sleep 500", "regs",
            ("sdio", REGISTERS["sdio"], 4), ("dhcsr", REGISTERS["dhcsr"], 4)],
            dict(sdio=4, dhcsr=4), "storage-idle-halt")
        pcs = re.findall(r"\bPC\s*=\s*([0-9a-fA-F]{8})", console)
        h.require(pcs and int(pcs[-1], 16) == address and
            int.from_bytes(data["dhcsr"], "little") & 0x20000 and
            not int.from_bytes(data["sdio"], "little") & 0x3800, "halt not proved safe; do not program")
        self.execute(["h", "ClrBP 0", 'loadbin "%s", 0x08010000' % destination["image"], "r",
            "w4 0xE0042008, 0x%08X" % freeze, "g", "sleep 3000"], {}, "install-" + target)
        if target == "restore":
            reads, _, _ = self.execute([("app", 0x08010000, destination["image"].stat().st_size),
                ("boot", 0x08000000, 65536)], dict(app=destination["image"].stat().st_size, boot=65536),
                "restore-image-readback", seconds=300)
            h.require(reads["app"] == destination["image"].read_bytes() and
                reads["boot"] == h.pinned(self.plan["boot"]).read_bytes(), "restore image/Boot readback mismatch")
            return self.restore_state(1)
        self.wait_boot(target)
        return self.inspect(target, "post-install")

    def signature(self, role):
        bound = self.bind(role)
        h.require(self.read(bound["rtt"], 16, "rtt-signature")[:10] == b"SEGGER RTT", "wrong/live RTT signature")
        return bound["rtt"]

    def start_logger(self, role, label):
        address = self.signature(role)
        self.foreign_debuggers(h.fresh(self.out / (label + "-owner")))
        output = h.checked(self.out / (label + ".rtt"))
        h.require(not output.exists() and self.logger is None, "duplicate RTT reader/output")
        self.logger = h.Process(self.out, label, [self.tool("rttlogger"), "-Device", "CORTEX-M4",
            "-If", "SWD", "-Speed", "1000", "-USB", str(self.plan["probe_serial"]), "-RTTAddress", "0x%08X" % address,
            "-RTTChannel", "0", output], self.env)
        h.wait_for(lambda: self.logger.alive() and output.exists(), 10)
        return output

    def stop_logger(self):
        if self.logger:
            self.logger.close("planned_capture_stop_not_a_success_verdict")
            self.logger = None

    def transfer_snapshot(self, raw_metrics):
        """After END/terminal publication, before reboot: read, never halt/apply a write."""
        bound = self.bind("base")
        table = bound["table"]
        requested = [("header_before", 0x08010400, 96),
            ("metrics", table["g_ota_link_metrics"][0], 420),
            ("published", table["g_ota_metrics_publish_bytes"][0], 4),
            ("guard", table["__StackGuardStart"][0], 32),
            ("stack", table["__StackLimit"][0], 8192),
            ("clock", table["system_core_clock"][0], 4), ("systick", 0xe000e010, 12),
            ("vtor", REGISTERS["vtor"], 4), ("wdt", 0x40003004, 8),
            ("tick0", table["SystemTickCount"][0], 4), "sleep 100",
            ("tick1", table["SystemTickCount"][0], 4), ("header_after", 0x08010400, 96)]
        data, _, out = self.execute(requested, {row[0]: row[2] for row in requested if isinstance(row, tuple)}, "terminal-before-reboot")
        header = bound["image"].read_bytes()[0x400:0x460]
        h.require(data["header_before"] == data["header_after"] == header and data["metrics"] == raw_metrics,
                  "terminal stack/clock window missed or MCU reset; preserve OTA, do not replay")
        h.require(int.from_bytes(data["published"], "little") == 853, "incomplete original RTT publication")
        h.require(int.from_bytes(data["vtor"], "little") == 0x08010800, "already in Boot; no old-App stack claim")
        h.require(int.from_bytes(data["clock"], "little") == 288000000, "unexpected live MCU clock")
        ctrl, reload, current = struct.unpack("<3I", data["systick"])
        h.require(ctrl & 7 == 7 and reload == 287999 and current <= reload, "unqualified steady-state SysTick")
        ticks = [int.from_bytes(data[key], "little") for key in ("tick0", "tick1")]
        h.require(ticks[1] > ticks[0], "terminal clock stopped/reset")
        value = dict(stack=stack_observation(data["guard"], data["stack"]), clock_hz=288000000,
            systick=[ctrl, reload, current], ticks=ticks, watchdog_registers=list(struct.unpack("<2I", data["wdt"])),
            originals={name: h.record(out / (name + ".bin")) for name in data},
            scope="Old App terminal session before reboot; includes any subsequent apply stack use. Read-only, no WDT feed/write.")
        h.save(out / "result.json", value)
        return value

    def down(self, text):
        h.require(re.fullmatch(r"(?:status|probe \d+ (?:115200|230400|460800|921600)|rate set \d+ (?:115200|230400|460800|921600)|rate rearm \d+|at \d+ AT\+REBOOT=1)", text), "non-whitelisted maintenance command")
        address = self.signature("maintenance")
        data, offset = (text + "\n").encode("ascii"), 0
        deadline = time.monotonic() + 10
        while offset < len(data):
            h.require(time.monotonic() < deadline, "RTT down timeout")
            descriptor = self.read(address + 0x60, 24, "down-descriptor")
            _, buffer, size, wr, rd, _ = struct.unpack("<6I", descriptor)
            h.require(size == 16 and 0x20000000 <= buffer < 0x20058000 - size and wr < size and rd < size,
                      "unexpected live RTT down descriptor")
            free = (rd - wr - 1) % size
            if not free:
                time.sleep(.05)
                continue
            chunk = data[offset:offset + free]
            commands = ["w1 0x%08X, 0x%02X" % (buffer + (wr + n) % size, value) for n, value in enumerate(chunk)]
            commands += ["w4 0x%08X, 0x%08X" % (address + 0x6c, (wr + len(chunk)) % size), "sleep 50"]
            self.execute(commands, {}, "maintenance-down")
            offset += len(chunk)

    def console(self, text):
        self.down(text)
        if text != "status":
            time.sleep(7)
            self.down("status")
        label = "console-%04d" % self.count
        path = self.start_logger("maintenance", label)
        try:
            time.sleep(2)
            h.require(self.logger.alive(), "RTT logger exited during maintenance capture")
        finally:
            self.stop_logger()
        raw = path.read_bytes()
        status = re.findall(rb"(?m)^BXST: ([^\r\n]+)", raw)
        h.require(status, "missing actual maintenance status")
        values = dict((k.decode(), int(v)) for k, v in re.findall(rb"(\w+)=(\d+)", status[-1]))
        h.require(all(values.get(k) == 0 for k in ("busy", "probe", "drop", "rej", "logdrop", "cmdr", "disc")),
                  "maintenance busy/error/missing records")
        return values, raw

    def baud(self, target):
        self.inspect("maintenance")
        self.start_logger("maintenance", "startup-drain")
        try:
            time.sleep(2)
            h.require(self.logger.alive(), "startup RTT reader exited")
        finally:
            self.stop_logger()
        status, _ = self.console("status")
        epoch, old = status["epoch"], status["baud"]
        status, _ = self.console("probe %d %d" % (epoch, old))
        h.require(status["state"] == 1 and status["known"] == old, "module/UART rate unknown; no set")
        if target != old:
            status, _ = self.console("rate set %d %d" % (epoch, target))
            h.require(status["state"] == 2, "rate set result unknown")
            status, raw = self.console("probe %d %d" % (epoch, target))
            if status["state"] != 1:
                status, raw = self.console("probe %d %d" % (epoch, old))
                h.require(b"deferred=1" in raw and status["state"] == 2, "set not effective or ambiguous; no restart")
                status, _ = self.console("at %d AT+REBOOT=1" % epoch)
                status, _ = self.console("rate rearm %d" % epoch)
                status, _ = self.console("probe %d %d" % (epoch, target))
        h.require(status["epoch"] == epoch and status["state"] == 1 and status["known"] == status["baud"] == target,
                  "module/UART handshake not proved")
        table = self.bind("maintenance")["table"]
        word = int.from_bytes(self.read(table["g_p34_retained_word"][0], 4, "retained-baud"), "little")
        error = int.from_bytes(self.read(table["g_p34_retention_error"][0], 4, "retention-error"), "little")
        slot = {115200: 5, 230400: 6, 460800: 7, 921600: 8}[target]
        h.require(error == 0 and word == (0x50340000 | ((slot ^ 255) << 8) | slot), "retained baud mismatch")
        h.save(self.out / "baud-result.json", dict(baud=target, word=word, status=status, retained_by_firmware=True))

    def restore_state(self, phase):
        address = self.bind("restore")["table"]["g_restore_control"][0]
        a = self.read(address, 640, "restore-mailbox-a")
        time.sleep(.2)
        b = self.read(address, 640, "restore-mailbox-b")
        base = h.pinned(self.plan["images"]["base"]["image"]).read_bytes()
        first = restore_gate(a, base, self.plan["boot"]["sha256"], phase)
        second = restore_gate(b, base, self.plan["boot"]["sha256"], phase)
        h.require(second["tick"] > first["tick"], "restore stopped or reset")
        return second

    def restore(self):
        self.install("target", "restore")
        self.restore_state(1)
        address = self.bind("restore")["table"]["g_restore_control"][0]
        self.execute(["w4 0x%08X, 0x%08X" % (address + 24, (~0x52333441) & 0xffffffff),
            "w4 0x%08X, 0x52333441" % (address + 20), "sleep 3000"], {}, "restore-arm")
        committed = self.restore_state(3)
        self.execute(["r", "g"], {}, "ordinary-boot-rollback")
        self.wait_boot("base")
        result = self.inspect("base", "rollback-full-readback")
        journal = self.read(0x90300000, 4096, "rollback-staging-zero")
        h.require(journal == b"\xff" * 4096, "same-package zero durable journal not established")
        h.save(self.out / "restore-result.json", dict(mailbox=committed, restored=result,
            journal_erased=True, ordinary_boot=True, boot_programmed=False))

    def wait_boot(self, role, seconds=300):
        bound = self.bind(role)
        header = bound["image"].read_bytes()[0x400:0x460]
        state = bound["table"][SYMBOLS["state"]][0]
        confirmed = bound["table"][SYMBOLS["confirmed"]][0]
        deadline = time.monotonic() + seconds
        while time.monotonic() < deadline:
            data, _, _ = self.execute([("header", 0x08010400, 96), ("vtor", REGISTERS["vtor"], 4),
                ("state", state, 1), ("confirmed", confirmed, 1)],
                dict(header=96, vtor=4, state=1, confirmed=1), "wait-ordinary-boot", seconds=min(180, max(1, deadline-time.monotonic())))
            if data["header"] == header and data["vtor"] == struct.pack("<I", 0x08010800) and \
                    data["state"] == b"\x04" and data["confirmed"] == b"\x01":
                return
            time.sleep(2)
        raise RuntimeError("ordinary Boot/app confirmation deadline; no repeated reset")
