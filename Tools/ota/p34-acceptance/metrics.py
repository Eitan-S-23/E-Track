"""Read-only decoder for the production 420-byte MCU metrics, not schema-2 probes."""
import argparse
import hashlib
import json
from pathlib import Path
import re
import struct
import zlib

SIZE = 420
MAGIC = 0x50334d31
FIELDS = ("magic schema size ready active run clock_hz clock_ok overflow uart_baud_actual "
          "retained_baud total_len terminal protocol session epoch initial_durable final_durable "
          "start_ms end_ms rx_bytes rx_ring_peak overlay_dropped hw_dropped uart_errors "
          "uart_error_flags parser_bad_frames package_crc32").split()
PHASES = ("payload_read payload_program payload_erase payload_verify journal_read journal_program "
          "journal_erase journal_verify uart_rx_irq ack_tx").split()


def require(value, message):
    if not value:
        raise ValueError(message)


def decode(raw):
    require(len(raw) == SIZE, "production MCU metrics size; old probes are not compatible")
    words = struct.unpack("<105I", raw)
    m = dict(zip(FIELDS, words))
    require((m["magic"], m["schema"], m["size"], m["ready"], m["active"]) ==
            (MAGIC, 1, SIZE, 1, 0), "production MCU metrics publication/schema")
    require(zlib.crc32(raw[:-4]) == words[-1], "MCU metrics CRC/torn read")
    require(m["clock_ok"] == 1 and m["clock_hz"] == 288000000 and m["overflow"] == 0,
            "invalid/overflowed MCU clock or counters")
    require(m["run"] > 0 and m["terminal"] in (0, 1), "MCU metrics session boundary")
    require(0 < m["uart_baud_actual"] <= 1000000 and
            m["retained_baud"] in (0, 115200, 230400, 460800, 921600), "MCU UART parameter domain")
    m["package_sha256"] = raw[112:144].hex()
    error = words[36:44]
    m["first_error"] = dict(zip(("operation", "phase", "address", "length", "result",
                                  "mismatch_address", "expected", "observed"), error)) if error[1] else None
    if m["first_error"] is not None and error[4] >= 1 << 31:
        m["first_error"]["result"] -= 1 << 32
    m["phase"] = {}
    for i, name in enumerate(PHASES):
        calls, errors, count, lo, hi, maximum = words[44 + i * 6:50 + i * 6]
        cycles = lo + (hi << 32)
        require(errors <= calls and maximum <= cycles and
                (calls != 0 or not any((errors, count, cycles, maximum))), "MCU phase count mismatch")
        m["phase"][name] = dict(calls=calls, errors=errors, bytes_requested=count,
            cycles=cycles, max_cycles=maximum,
            elapsed_us=cycles * 1000000 / m["clock_hz"] if calls else None,
            max_us=maximum * 1000000 / m["clock_hz"] if calls else None)
    require(m["phase"]["uart_rx_irq"]["bytes_requested"] == m["rx_bytes"], "MCU RX accounting")
    if m["terminal"] == 0:
        require(m["protocol"] in (1, 2) and 1 <= m["session"] <= 255 and
                (m["protocol"] == 1 or m["epoch"] > 0) and
                64 <= m["total_len"] <= 1048576 and m["final_durable"] == m["total_len"] and
                m["initial_durable"] <= m["total_len"], "MCU final staging state")
        if m["initial_durable"] == 0:
            required = ("payload_read", "payload_program", "payload_erase", "payload_verify",
                        "journal_read", "journal_program", "uart_rx_irq", "ack_tx")
            require(all(m["phase"][p]["calls"] > 0 and m["phase"][p]["cycles"] > 0 for p in required),
                    "missing required MCU stage measurements")
    m["elapsed_ms"] = (m["end_ms"] - m["start_ms"]) & 0xffffffff
    m["clean"] = (m["terminal"] == 0 and m["first_error"] is None and
        not any(m[k] for k in ("overlay_dropped", "hw_dropped", "uart_errors", "uart_error_flags", "parser_bad_frames")) and
        all(p["errors"] == 0 for p in m["phase"].values()))
    m["scope"] = ("MCU DWT intervals only. Staging callbacks include XIP restore, IRQs and WAIT_RX/ACK; "
                  "do not sum nested stages or subtract App clocks. UART includes IRQ body/hardware capture/hook, not exception entry/exit. "
                  "Erase bytes are logical 4 KiB requests, not physical erase-ahead bytes. "
                  "terminal=0 is validated staging/END, not installation or independent acceptance.")
    return m


def from_rtt(data):
    lines = [line for line in data.splitlines() if line.startswith(b"P34_METRICS ")]
    require(len(lines) == 1, "one complete original MCU metrics record required")
    require(re.fullmatch(rb"P34_METRICS [0-9a-f]{840}", lines[0]), "truncated/invalid MCU metrics record")
    return decode(bytes.fromhex(lines[0][12:].decode("ascii")))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", type=Path, required=True)
    parser.add_argument("--binary", action="store_true")
    parser.add_argument("--elf", type=Path, required=True)
    parser.add_argument("--map", type=Path, required=True)
    parser.add_argument("--expect-elf-sha256", required=True)
    parser.add_argument("--expect-map-sha256", required=True)
    parser.add_argument("--package", type=Path, required=True)
    parser.add_argument("--expect-epoch", type=int, required=True)
    parser.add_argument("--expect-baud", type=int, choices=(115200, 230400, 460800, 921600), required=True)
    args = parser.parse_args()
    bindings = {}
    for name, path, expected in (("elf", args.elf, args.expect_elf_sha256),
                                 ("map", args.map, args.expect_map_sha256)):
        require(path.stat().st_size <= 32 * 1024 * 1024, "oversized ELF/map")
        digest = hashlib.sha256(path.read_bytes()).hexdigest()
        require(re.fullmatch(r"[0-9a-f]{64}", expected) and digest == expected, "wrong matching " + name)
        bindings[name] = dict(path=str(path.resolve()), sha256=digest)
    mapping = args.map.read_text(encoding="utf-8")
    bindings["addresses"] = {}
    for symbol in ("g_ota_link_metrics", "g_ota_metrics_publish_bytes", "_SEGGER_RTT"):
        hits = re.findall(r"(?m)^\s*(0x[0-9a-fA-F]+)\s+" + symbol + r"\s*$", mapping)
        require(len(hits) == 1, "matching map symbol missing/ambiguous: " + symbol)
        bindings["addresses"][symbol] = hits[0]
    require(args.input.stat().st_size <= 64 * 1024 * 1024, "oversized MCU capture")
    require(64 <= args.package.stat().st_size <= 1048576, "bounded package required")
    source = args.input.read_bytes()
    m = decode(source) if args.binary else from_rtt(source)
    package = args.package.read_bytes()
    require(m["total_len"] == len(package) and m["package_sha256"] == hashlib.sha256(package).hexdigest() and
            m["epoch"] == args.expect_epoch, "wrong MCU session/package binding")
    if m["terminal"] == 0:
        require(m["package_crc32"] == zlib.crc32(package), "MCU staging CRC does not match package")
    require(abs(m["uart_baud_actual"] - args.expect_baud) <= args.expect_baud // 33,
            "MCU measured baud mismatch")
    print(json.dumps(dict(metrics=m, binding=bindings, raw_sha256=hashlib.sha256(source).hexdigest(),
                         independent_acceptance=False), indent=2))


if __name__ == "__main__":
    try:
        main()
    except (ValueError, OSError) as error:
        raise SystemExit("MCU_METRICS_REJECTED: " + str(error))
