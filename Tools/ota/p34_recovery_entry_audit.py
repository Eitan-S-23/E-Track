"""Offline inventory of saved entry dependencies, not a device loader."""
from pathlib import Path
import hashlib
import re
import struct
import sys

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "Tools/ota"))
import p34_install_cost as host


def load_segments(data):
    if data[:7] != b"\x7fELF\x01\x01\x01":
        raise ValueError("ELF32 little-endian required")
    header = struct.unpack_from("<HHIIIIIHHHHHH", data, 16)
    if header[1] != 40 or header[8] != 32:
        raise ValueError("ARM program-header format required")
    offset, count = header[4], header[9]
    if offset + count * 32 > len(data):
        raise ValueError("truncated program headers")
    result = []
    for index in range(count):
        kind, start, virtual, physical, size, memory, flags, _ = struct.unpack_from(
            "<IIIIIIII", data, offset + index * 32)
        if kind != 1:
            continue
        if size > memory or start + size > len(data) or virtual + memory > 2**32:
            raise ValueError("invalid load segment")
        result.append(dict(start=virtual, end=virtual + memory, file_bytes=size,
                           memory_bytes=memory, physical=physical, flags=flags))
    if not result:
        raise ValueError("no load segments")
    return result


def main():
    cli = host.cli
    cli.require(Path.cwd() == ROOT and sys.flags.isolated and sys.flags.no_site
                and sys.dont_write_bytecode, "isolated project root required")
    store = cli.Store(ROOT)
    out = store.checked(ROOT / ".cache/p34-recovery-entry-audit1")
    store.checked(out / "result.json")
    cli.require(not out.exists(), "preserve evidence")
    paths = {
        "boot": ".cache/p34-boot/activation/after/boot.bin",
        "boot_elf": ".cache/p34-bc-target/b1/boot/X-Track-Boot.elf",
        "ram_elf": ".cache/p34-ram-ports-link1/ports.elf",
        "platform": ".cache/p34-bc-target/f/boot/platform/at32/boot_platform_at32.c",
        "main": ".cache/p34-bc-target/f/boot/src/boot_main.c",
        "app_disassembly": ".cache/p34-early-usb-r2/on/disassembly.log",
        "app_elf": ".cache/p34-early-usb-r2/on/b/app-gcc/X-Track-App-GCC.elf",
        "bcb": "Tools/ota/ram_recovery/at32_bcb_port.c",
        "qspi": "Tools/ota/ram_recovery/at32_qspi_port.c",
        "linker": "Tools/ota/ram_recovery/core.ld",
    }
    raw = {key: (ROOT / path).read_bytes() for key, path in paths.items()}
    cli.require(hashlib.sha256(raw["boot"]).hexdigest() ==
                "a63346db0dc673dc42adf6064892c466af5c4571df53cb55fe5b6ea154c1fdf4",
                "original Boot identity")
    cli.require(hashlib.sha256(raw["ram_elf"]).hexdigest() ==
                "f5f1ce093bd6b62dbdcc07c2f094c53150c105d4909d460567df622e17481c22",
                "saved RAM ports identity")
    facts = []

    def anchor(key, fragment, interpretation):
        lines = raw[key].decode("utf-8").splitlines()
        found = [(i + 1, line) for i, line in enumerate(lines) if fragment in line]
        cli.require(len(found) == 1, "ambiguous/missing anchor: " + fragment)
        facts.append(dict(path=paths[key], line=found[0][0], text=found[0][1],
                          interpretation=interpretation))

    anchor("platform", "configure_eeprom_gpio();",
           "Boot platform init changes I2C GPIO before candidate holdpoint")
    anchor("platform", "gpio_bits_set(GPIOB, GPIO_PINS_6 | GPIO_PINS_7);",
           "Line release needs a prior bus-state bound; not a passive acquisition")
    anchor("platform", "qspi_send(0x66u)",
           "Original QSPI init sends reset opcodes; not a harmless cold-port shortcut")
    anchor("qspi", "memset(s,0,sizeof(*s));",
           "prepare clears sticky failure; must not be reused as post-timeout observation")
    anchor("qspi", "return s && s->initialized && !s->failed;",
           "Existing public read path rejects failed state; no separate settled observer")
    anchor("bcb", "DWT->CYCCNT = 0u;",
           "BCB capture creates a new counter epoch, invalidating a prior raw DWT timestamp")
    anchor("linker", "ENTRY(rr_run)",
           "Callable core entry is not a reset/vector/bootstrap implementation")
    anchor("app_disassembly", "bl\t8018d04 <WDG_Init>",
           "Selected R2 HAL_Init actually calls WDG_Init; live App halt must account for WDT")
    app_lines = raw["app_disassembly"].decode("utf-8").splitlines()
    owner = None
    for line in app_lines:
        match = re.match(r"[0-9a-f]+ <([^>]+)>:", line)
        if match:
            owner = match.group(1)
        if "bl\t8018d04 <WDG_Init>" in line:
            cli.require(owner == "_ZN3HAL8HAL_InitEv", "unexpected watchdog caller")
            break
    boot_segments = load_segments(raw["boot_elf"])
    ram_segments = load_segments(raw["ram_elf"])
    initial_msp = struct.unpack_from("<I", raw["boot"])[0]
    for segment in ram_segments:
        cli.require(0x20058000 <= segment["start"] <= segment["end"] <= 0x20080000,
                    "RAM core outside declared overlay")
    overlaps = []
    for ram in ram_segments:
        for boot in boot_segments:
            if max(ram["start"], boot["start"]) < min(ram["end"], boot["end"]):
                overlaps.append(dict(ram=ram, boot=boot))
    store.write(out / "result.json", dict(
        result="OFFLINE_ENTRY_DEPENDENCIES_INVENTORIED", facts=facts,
        initial_boot_msp=initial_msp, boot_load_segments=boot_segments,
        ram_load_segments=ram_segments, load_segment_overlaps=overlaps,
        caveat="Load-segment comparison does not bound the active descending Boot stack, DMA or future bootstrap",
        device_execute_ready=False, hardware=False,
        inputs=[cli.record(Path(__file__))] + [cli.record(ROOT / p) for p in paths.values()]))
    print("OFFLINE_ENTRY_DEPENDENCIES_INVENTORIED facts=" + str(len(facts)))
    print("Boot initial MSP=" + hex(initial_msp) + "; RAM load-segment overlaps=" + str(len(overlaps)))
    for segment in ram_segments:
        print("RAM " + hex(segment["start"]) + ".." + hex(segment["end"]))


if __name__ == "__main__":
    main()
