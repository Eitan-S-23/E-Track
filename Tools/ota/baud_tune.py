"""Bounded, image-bound UART admission through the existing firmware controller."""
from __future__ import annotations

import importlib.util
import json
from pathlib import Path
import re
import struct
import sys
import time

spec = importlib.util.spec_from_file_location("baud_tune_mcu", Path(__file__).with_name("baud_mcu.py"))
m = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = m
spec.loader.exec_module(m)
b, c = m.b, m.c


def known(status, baud):
    return all(status.get(key) == value for key, value in dict(state=1, known=baud, baud=baud, busy=0, probe=0).items())


def command_for(kind, baud, status):
    b.require(status["busy"] == 0 and status["probe"] == 0, "AT control cannot run during OTA or another probe")
    epoch = status["epoch"]
    b.require(type(epoch) is int and 0 <= epoch <= 0xFFFFFFFF, "control epoch")
    if kind == "rearm":
        return "rate rearm %d" % epoch
    b.require(baud in (115200, 460800, 921600), "candidate rate scope")
    if kind == "probe":
        return "probe %d %d" % (epoch, baud)
    if kind == "set":
        b.require(known(status, status["baud"]) and status["known"] != baud, "setter requires aligned known old baud")
        return "rate set %d %d" % (epoch, baud)
    if kind == "align":
        b.require(status["state"] == 1 and status["known"] == baud, "only align to an observed known module rate")
        return "uart %d %d" % (epoch, baud)
    raise RuntimeError("unlisted controller operation")


class ControlLink(c.Link):
    running = m.passive.Link.running

    def write(self, address, data):
        self.running()
        super().write(address, data)


class ControlChannel(m.UpChannel):
    def __init__(self, link, index, profile):
        super().__init__(link, index, profile)
        self.blocked = False
        down = self.descriptor(True)
        link.ram_reads.append((down["buffer"], down["buffer"] + down["size"]))
        link.ram_writes += [(down["buffer"], down["buffer"] + 16), (self.address + 108, self.address + 112)]
        self.writer = c.RingWriter(self)

    send = c.Rtt.send


def tune(run, baud, version, *, cold_start=True):
    b.require(re.fullmatch(r"[a-z0-9-]{1,48}", run) and baud in (115200, 460800, 921600) and version in (30208, 30209),
              "bounded diagnostic admission identity")
    m.native_authority()
    bindings = m.load_bindings()
    profile = bindings["profiles"][str(version)]
    expected = Path(profile["image"]["path"]).read_bytes()
    out = b.checked(b.OUT / "rates" / run)
    receipt = b.checked(b.OUT / "rates" / (run + ".json"))
    b.require(not out.exists() and not receipt.exists(), "prior tuning attempt must be reconciled, never replayed")
    e, reader = m.Evidence(out), None
    link = ControlLink(e, writable=True)
    started = time.monotonic()
    result = dict(run=run, baud=baud, version=version, result="NOT_ADMITTED", source=b.record(Path(__file__)),
                  native_history_before=c.record(c.MRU), commands=[], ota=0, flash=0, mcu_reset=0)

    def action(kind, rate=None, deferred=False):
        b.require(time.monotonic() - started < 450, "finite UART admission deadline")
        channel = reader.channel
        before = channel.status()
        b.require(before["busy"] == before["probe"] == 0, "UART controller not idle")
        if kind == "reboot":
            b.require(deferred and before["state"] == 2 and before["old"] != 0 and before["baud"] == before["old"],
                      "module reboot requires this transaction's explicit deferred evidence")
            command = "at %d AT+REBOOT=1" % before["epoch"]
        else:
            command = command_for(kind, rate, before)
        e.emit("quota-reserved", command=command, before=before, meaning="planned bounded action, no replay/refund")
        first = channel.send(command)
        if kind == "probe":
            line = channel.wait(first, lambda value: c.probe_terminal(value, rate), 10)
            b.require(line.startswith("BXPB: done "), "probe rejected/aborted; no retry")
        else:
            prefix = {"set": "BXRATE: ", "rearm": "BXRATE: ", "align": "BXUART: ", "reboot": "BXAT: "}[kind]
            line = channel.wait(first, lambda value: value.startswith(prefix), 4)
            b.require("rejected" not in line and "bad " not in line, "controller rejected action")
        after = channel.status()
        b.require(after["probe"] == 0 and after["epoch"] == before["epoch"] and
                  after["drop"] == before["drop"] and after["logdrop"] == before["logdrop"], "control evidence lost or epoch changed")
        value = dict(command=command, before=before, after=after, terminal=line, lines=channel.lines[first:])
        result["commands"].append(value)
        return value

    def fresh_probe(rate):
        value = action("probe", rate)
        b.require(" comm=1 " in value["terminal"] and re.search(r" idx=%d " % {115200: 5, 460800: 7, 921600: 8}[rate], value["terminal"]) and
                  known(value["after"], rate), "fresh module communication at selected baud not confirmed")
        return value["after"]

    def wait_reader():
        deadline = time.monotonic() + 60
        while time.monotonic() < deadline:
            observed = reader.poll()
            if observed is not None:
                return observed
            time.sleep(.1)
        raise RuntimeError("diagnostic App initialization deadline")

    try:
        link.connect()
        b.require(m.base.read_image(link, len(expected)) == expected, "tune image mismatch")
        boot = m.read_region(link, 0x08000000, 65536)
        b.require(m.a.sha(boot) == bindings["whole_boot"]["sha256"], "whole Boot mismatch before AT")
        reader = m.ImageReader(link, {str(version): profile}, channel_factory=ControlChannel)
        wait_reader()
        reader.check_dwt()
        initial = reader.channel.status()
        b.require(initial["baud"] in (115200, 460800, 921600) and initial["state"] in (0, 1), "unknown/pending old tuning transaction")
        action("rearm")
        before = fresh_probe(initial["baud"])
        if before["baud"] != baud:
            old = before["baud"]
            action("set", baud)
            at_target = action("probe", baud)
            if not known(at_target["after"], baud):
                at_old = action("probe", old)
                deferred = any(line.startswith("BXRATE: deferred ") and " deferred=1 " in line for line in at_old["lines"])
                if deferred:
                    action("reboot", deferred=True)
                    time.sleep(1)
                    action("rearm")
                    fresh_probe(baud)
                else:
                    result["safe_retained_old"] = known(at_old["after"], old)
                    raise RuntimeError("rate change not confirmed; do not repeat the setter")
            elif " comm=1 " not in at_target["terminal"]:
                raise RuntimeError("KNOWN without this probe's actual communication")
        symbols = profile["symbols"]
        b.require(reader.read32(symbols["retained_word"]) == m.baud_word(baud) and
                  reader.read32(symbols["retention_error"]) == 0 and reader.read32(m.ERTC_DT20) == m.baud_word(baud),
                  "selected rate retention not read back")
        if cold_start:
            reader.close()
            reader.gate.invalidate("planned matched MCU restart")
            e.emit("quota-reserved", command="Reset+Go", purpose="verify selected UART survives MCU startup")
            reset, go = link.sdk.JLINKARM_Reset, link.sdk.JLINKARM_Go
            reset.argtypes, reset.restype, go.argtypes, go.restype = [], None, [], None
            reset()
            go()
            result["mcu_reset"] = 1
            observed = wait_reader()
            deadline = time.monotonic() + 30
            lines = list(observed["lines"])
            while not any(m.passive.confirmation(line, version) for line in lines) and time.monotonic() < deadline:
                observed = reader.poll()
                if observed:
                    lines.extend(observed["lines"])
                time.sleep(.1)
            b.require(any(m.passive.confirmation(line, version) for line in lines), "fresh BCB confirmation missing after matched restart")
            b.require(reader.read32(symbols["boot_baud"]) == baud and reader.read32(symbols["retained_word"]) == m.baud_word(baud) and
                      reader.read32(symbols["retention_error"]) == 0, "startup did not retain selected UART")
            result["dwt_after_restart"] = reader.check_dwt()
            result["post_restart_status"] = fresh_probe(baud)
        result.update(result="BAUD_COLD_START_VERIFIED" if cold_start else "BAUD_COMMUNICATION_VERIFIED",
                      final_status=reader.channel.status(), identity=profile["identity"], seconds=time.monotonic() - started)
    except Exception as error:
        result["error"] = type(error).__name__ + ": " + str(error)
        e.emit("error", error=result["error"])
    finally:
        if reader:
            reader.close()
        link.close()
        result.update(native_history_after=c.record(c.MRU), reader_closed=not link.opened)
        e.save("result.json", result)
        e.events.close()
        e.ledger.close()
        b.io.write_json(b.ROOT, receipt, result)
    b.require(result["result"] in ("BAUD_COLD_START_VERIFIED", "BAUD_COMMUNICATION_VERIFIED"), result.get("error", "baud not admitted"))
    return result
