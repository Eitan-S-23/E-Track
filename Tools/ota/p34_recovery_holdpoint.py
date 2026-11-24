"""Bind a candidate holdpoint to saved artifacts; never connect to hardware."""
from pathlib import Path
import hashlib
import struct
import sys

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "Tools/ota"))
import p34_install_cost as host


def main():
    cli = host.cli
    cli.require(Path.cwd() == ROOT and sys.flags.isolated and sys.flags.no_site
                and sys.dont_write_bytecode, "isolated root required")
    store = cli.Store(ROOT)
    out = store.checked(ROOT / ".cache/p34-recovery-holdpoint1")
    store.checked(out / "result.json")
    cli.require(not out.exists(), "preserve evidence")
    base = ROOT / ".cache/p34-bc-target"
    elf_path = base / "b1/boot/X-Track-Boot.elf"
    bin_path = base / "b1/boot/X-Track-Boot.bin"
    full_path = ROOT / ".cache/p34-boot/activation/after/boot.bin"
    elf, compact, full = (p.read_bytes() for p in (elf_path, bin_path, full_path))
    cli.require(len(full) == 65536 and hashlib.sha256(full).hexdigest() ==
                "a63346db0dc673dc42adf6064892c466af5c4571df53cb55fe5b6ea154c1fdf4",
                "complete original Boot mismatch")
    cli.require(len(compact) == 14780 and full[:len(compact)] == compact,
                "compact baseline mismatch")
    cli.require(elf[:7] == b"\x7fELF\x01\x01\x01", "ELF32 little-endian required")
    header = struct.unpack_from("<HHIIIIIHHHHHH", elf, 16)
    cli.require(header[1] == 40, "ARM required")
    phoff, phsize, phnum = header[4], header[8], header[9]
    cli.require(phsize == 32 and phoff + phsize * phnum <= len(elf), "program headers")
    address, expected = 0x0800199C, bytes.fromhex("1c22002101a801f07ffd")
    matches = []
    for index in range(phnum):
        kind, offset, virtual, physical, filesz, memsz, flags, align = struct.unpack_from(
            "<IIIIIIII", elf, phoff + index * phsize)
        cli.require(offset + filesz <= len(elf), "segment bounds")
        if kind == 1 and virtual <= address and address + len(expected) <= virtual + filesz:
            cli.require(flags & 1 and physical == virtual, "executable Flash segment required")
            start = offset + address - virtual
            matches.append(elf[start:start + len(expected)])
    cli.require(matches == [expected], "holdpoint ELF bytes mismatch or ambiguous mapping")
    cli.require(full[address - 0x08000000:address - 0x08000000 + len(expected)] == expected,
                "holdpoint complete-backup bytes mismatch")
    inputs = [Path(__file__), elf_path, bin_path, full_path,
              base / "g1-disassembly.log", base / "f/boot/src/boot_main.c",
              base / "f/boot/platform/at32/boot_platform_at32.c"]
    store.write(out / "result.json", dict(
        result="SAVED_HOLDPOINT_BYTES_BOUND", address=hex(address), bytes=expected.hex(),
        compact_bytes=len(compact), full_bytes=len(full), inputs=[cli.record(p) for p in inputs],
        device_execute_ready=False, hardware=False,
        scope="artifact/address identity only; no safe-entry or breakpoint execution proof",
        unresolved=["pre-entry media settlement", "reset and board power behavior",
                    "watchdog and retained debug state", "breakpoint mechanism",
                    "exception and DMA ownership", "safe exit"] ))
    print("SAVED_HOLDPOINT_BYTES_BOUND; device_execute_ready=false")


if __name__ == "__main__":
    main()
