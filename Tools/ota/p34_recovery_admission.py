"""Execute exact snapshot recovery admission on provisional images, offline."""
import hashlib
import json
from pathlib import Path
import re
import struct
import sys
import zlib

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "Tools/ota"))
import p34_install_cost as host


def slot(image):
    hdr = image[0x400:0x460]
    metadata = (b"ETSL\x04\xff\xff\xff" +
                struct.pack("<III", len(image), zlib.crc32(image),
                            struct.unpack_from("<I", hdr, 8)[0]) + hdr[40:48] + b"TMOC")
    return metadata + b"\xff"*(4096-32) + image + b"\xff"*(0x100000-4096-len(image))


def reseal(image, offset, value):
    changed = bytearray(image)
    changed[offset:offset+len(value)] = value
    changed[0x428:0x448] = bytes(32)
    changed[0x45c:0x460] = bytes(4)
    changed[0x428:0x448] = hashlib.sha256(changed).digest()
    struct.pack_into("<I", changed, 0x45c, zlib.crc32(changed[0x400:0x45c]))
    return bytes(changed)


def main():
    cli = host.cli
    cli.require(Path.cwd() == ROOT and sys.flags.isolated and sys.flags.no_site and
                sys.dont_write_bytecode, "isolated root required")
    store = cli.Store(ROOT)
    out = store.checked(ROOT / ".cache/p34-recovery-admission2")
    cli.require(not out.exists(), "preserve previous run")
    snapshot = ROOT / ".cache/p34-bc-target/f"
    sources = [ROOT / "tests/boot/p34_recovery_admission_host.c"] + [
        snapshot / "boot/src" / name for name in
        ("boot_fw_header.c", "boot_crc32.c", "boot_sha256.c", "boot_slot.c")]
    sources.append(snapshot / "Libraries/EEPROM/eeprom_bcb.c")
    cases = []
    manifest = ROOT / ".cache/p34-recovery-sources1/result.json"
    inventory = store.read(manifest)
    for binding in inventory["inputs"] + inventory["outputs"]:
        cli.require(cli.record(binding["path"]) == binding, "source preparation drift")
    for item in inventory["images"]:
        image = (manifest.parent / item["file"]).read_bytes()
        cases.append((item["file"], slot(image), 0, 0))
    image = (manifest.parent / "r2-a.bin").read_bytes()
    good = slot(image)
    # SOURCE_INVALID=1 and SOURCE_IO_ERROR=2 in the bound source.
    for name, offset in (("magic", 0), ("type", 4), ("padding", 5),
                         ("length", 8), ("crc", 12), ("version", 16),
                         ("sha8", 20), ("marker", 28), ("payload", 0x1500)):
        bad = bytearray(good)
        bad[offset] ^= 1
        cases.append((name, bytes(bad), 1, 0))
    for name, offset, value in (
            ("hardware", 0x420, struct.pack("<I", 2)),
            ("layout", 0x448, b"\x02"), ("minboot", 0x449, b"\xff"),
            ("msp", 0, bytes(4)), ("reset", 4, bytes(4)),
            ("header_version", 0x404, struct.pack("<I", 2)),
            ("name", 0x40c, b"X"*16), ("header_pad", 0x44a, b"\x00")):
        cases.append((name, slot(reseal(image, offset, value)), 1, 0))
    cases += [("read_header", good, 2, 1), ("read_payload", good, 2, 2),
              ("short_slot", good[:32], 2, 0)]
    for key in ("HOME", "USERPROFILE", "APPDATA", "LOCALAPPDATA", "TEMP", "TMP", "TMPDIR",
                "XDG_CACHE_HOME", "XDG_CONFIG_HOME", "XDG_DATA_HOME", "PYTHONUSERBASE",
                "PYTHONPYCACHEPREFIX", "CCACHE_DIR", "SCCACHE_DIR"):
        store.checked(out / "host" / key.lower())
    for name in ["validator.exe", "compile.log", "compile.json", "result.json"] + [
            n+suffix for n, _, _, _ in cases for suffix in (".bin", ".log", ".json")]:
        store.checked(out / name)
    # All controllable outputs were checked before environment() creates dirs.
    env = host.environment(store, out)
    exe = out / "validator.exe"
    cc = Path("D:/install/mingw64/bin/gcc.exe")
    command = [cc, "-std=c99", "-O2", "-Wall", "-Wextra", "-Werror",
               "-ffunction-sections", "-fdata-sections", "-Wl,--gc-sections",
               "-I"+str(snapshot/"boot/include"), "-I"+str(snapshot/"Libraries"),
               "-I"+str(snapshot/"boot/src"), *sources, "-o", exe]
    host.command(store, out, "compile", command, env, 90)
    records = []
    for name, data, expected, failure in cases:
        path = out / (name+".bin")
        store.raw(path, data)
        text = host.command(store, out, name, [exe, path, expected, failure], env, 30)
        match = re.search(rb"result=(\d+) reads=(\d+) version=(\d+)", text)
        cli.require(match is not None, "missing result")
        records.append(dict(name=name, expected=expected, reads=int(match[2])))
    inputs = sources + [snapshot/"boot/src/boot_state_machine.c", manifest, Path(__file__), cc]
    inputs += sorted((snapshot/"boot/include").glob("*.h"))
    inputs += [snapshot/"Libraries/OTA/ota_layout.h", snapshot/"Libraries/EEPROM/eeprom_bcb.h"]
    store.write(out/"result.json", dict(result="SNAPSHOT_RECOVERY_ADMISSION_PASS",
        cases=records, inputs=[cli.record(p) for p in inputs], executable=cli.record(exe),
        hardware=False, scope="exact recovery validator only; no BCB transitions or device writer"))
    print("SNAPSHOT_RECOVERY_ADMISSION_PASS cases="+str(len(records)))


if __name__ == "__main__":
    main()
