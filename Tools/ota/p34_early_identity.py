"""Authorized finite read-only identity pass; no reset/halt/flash commands."""
import hashlib
from pathlib import Path
import struct
import sys
import zlib

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "Tools/ota"))
import p34_session as cli
import p34_install_cost as host
import p34_boot_device as device
import baud_uncached as native

AREA = ROOT / ".cache/p34-early-identity1"


def image_identity(raw):
    cli.require(len(raw) >= 0x460, "short image")
    header = raw[0x400:0x460]
    cli.require(header[:4] == b"ETFW", "no ETFW header")
    word = lambda offset: struct.unpack_from("<I", header, offset)[0]
    cli.require(zlib.crc32(header[:92]) == word(92), "header CRC mismatch")
    size = word(36)
    cli.require(0x460 <= size <= 0xf0000 and size <= len(raw), "image length invalid")
    masked = bytearray(raw[:size])
    masked[0x428:0x448] = bytes(32)
    masked[0x45c:0x460] = bytes(4)
    cli.require(hashlib.sha256(masked).digest() == header[40:72], "image SHA mismatch")
    return dict(version=word(8), bytes=size, sha256=hashlib.sha256(raw[:size]).hexdigest(),
                stored_sha256=header[40:72].hex(), header_version=word(4), hardware_rev=word(32),
                layout=header[72], min_boot=header[73], vector_msp=struct.unpack_from("<I", raw)[0],
                vector_reset=struct.unpack_from("<I", raw, 4)[0],
                scope="header CRC/image hash identity, not full firmware admission")


def regions(mode):
    value = dict(core_before=(0xe000edf0, 4), vtor_before=(0xe000ed08, 4), qspi_before=(0xa0001010, 4))
    if mode == "initial":
        value.update(boot=(0x08000000, 65536), app_slot=(0x08010000, 0xf0000))
    else:
        value.update(candidate=(0x90000000, 0x100000), backup=(0x90100000, 0x100000),
                     recovery=(0x90200000, 0x100000))
    value.update(vtor_after=(0xe000ed08, 4), qspi_after=(0xa0001010, 4), core_after=(0xe000edf0, 4))
    return value


def main():
    cli.require(Path.cwd() == ROOT and sys.flags.isolated and sys.flags.no_site and
                sys.dont_write_bytecode, "isolated explicit project root required")
    cli.require(len(sys.argv) == 2 and sys.argv[1] in ("initial", "nor"), "initial/nor mode required")
    mode = sys.argv[1]
    store = cli.Store(ROOT)
    out = store.checked(AREA / mode)
    cli.require(not out.exists(), "preserve prior identity attempt")
    for name in ("result.json", "commands.jlink", "settings.jlink", "sdk.log", "command.json", "command.log"):
        store.checked(out / name)
    for name in regions(mode):
        store.checked(out / (name + ".bin"))
    for name in ("home", "userprofile", "appdata", "localappdata", "temp", "tmp", "tmpdir", "xdg_cache_home",
                 "xdg_config_home", "xdg_data_home", "pythonuserbase", "pythonpycacheprefix", "ccache_dir", "sccache_dir"):
        store.checked(out / "host" / name)
    device.IO["checked_output"](device.MRU.parent, device.MRU)
    old = store.read(ROOT / ".cache/p34-app-handoff/result.json")
    known = old["groups"]["measure"]["image"]
    cli.require(cli.record(known["path"]) == known, "expected historical App drift")
    sample = Path(known["path"]).read_bytes()
    cli.require(image_identity(sample)["version"] == 30275, "header parser positive")
    for offset in (0x408, 0x500):
        bad = bytearray(sample); bad[offset] ^= 1
        try:
            image_identity(bad)
        except RuntimeError:
            pass
        else:
            raise RuntimeError("header parser negative failed")
    if mode == "nor":
        previous = store.read(AREA / "initial/result.json")
        cli.require(previous["result"] == "INITIAL_IDENTITY_MATCHED" and previous["nor_mapping_ready"],
                    "NOR prerequisite not established")
        for record in previous["files"]:
            cli.require(cli.record(record["path"]) == record, "initial observation drift")
    result = dict(result="IDENTITY_FAILED", mode=mode, source=cli.record(Path(__file__)),
        hardware=False, flash=0, reset=0, halt=0, mru_before=cli.record(device.MRU), parser_checks=3)
    env = host.environment(store, out)
    lines = ["exec DisableAutoUpdateFW", "exec SetEnableMemCache = 0", "exec InvalidateCache",
             "exec ExcludeFlashCacheRange 0x08000000-0x080FFFFF",
             "exec ExcludeFlashCacheRange 0x90000000-0x902FFFFF"]
    for name, (address, size) in regions(mode).items():
        lines.append("savebin " + device.quote(out / (name + ".bin")) + ", 0x%08X, 0x%X" % (address, size))
    lines.append("qc")
    cli.require(all(line.startswith(("exec ", "savebin ")) or line == "qc" for line in lines), "forbidden device command")
    store.raw(out / "commands.jlink", ("\n".join(lines)+"\n").encode("ascii"))
    try:
        result["presence"] = native.native_presence()
        args = [device.JLINK, "-Device", "AT32F435RGT7", "-If", "SWD", "-Speed", "1000", "-USB", "123456",
                "-AutoConnect", "1", "-ExitOnError", "1", "-NoGui", "1", "-SettingsFile", out / "settings.jlink",
                "-Log", out / "sdk.log", "-CommandFile", out / "commands.jlink"]
        result["hardware"] = True
        data = host.command(store, out, "command", args, env, 180)
        cli.require(b"Not all bytes" not in data, "partial Commander read")
        raw = {n: (out / (n+".bin")).read_bytes() for n in regions(mode)}
        cli.require(all(len(raw[n]) == size for n, (_, size) in regions(mode).items()), "short readback")
        values = {n: struct.unpack("<I", raw[n])[0] for n in raw if n.endswith(("before", "after"))}
        result["observed_registers"] = values
        cli.require(not (values["core_before"] | values["core_after"]) & (1 << 17), "halted target; no automatic resume")
        cli.require(values["vtor_before"] == values["vtor_after"] == 0x08010000, "unexpected/changing initial VTOR")
        result["nor_mapping_ready"] = all(values[n] & (1 << 20) and not values[n] & (7 << 16)
                                         for n in ("qspi_before", "qspi_after"))
        if mode == "initial":
            result["app"] = image_identity(raw["app_slot"])
            cli.require(result["app"]["sha256"] == known["sha256"], "current App differs from expected 30275")
            result["boot_sha256"] = hashlib.sha256(raw["boot"]).hexdigest()
            cli.require(result["boot_sha256"] == "a63346db0dc673dc42adf6064892c466af5c4571df53cb55fe5b6ea154c1fdf4",
                        "full Boot differs from preserved backup")
            result["result"] = "INITIAL_IDENTITY_MATCHED"
        else:
            cli.require(result["nor_mapping_ready"], "NOR mapping state changed")
            result["slots"] = {}
            for name in ("candidate", "backup", "recovery"):
                try:
                    result["slots"][name] = image_identity(raw[name])
                except RuntimeError as error:
                    result["slots"][name] = dict(status="NO_VALID_IMAGE_IDENTITY", reason=str(error))
            result["result"] = "NOR_IDENTITIES_OBSERVED"
    except Exception as error:
        result["error"] = type(error).__name__ + ": " + str(error)
    finally:
        result["mru_after"] = cli.record(device.MRU)
        result["files"] = [cli.record(p) for p in sorted(out.glob("*.bin"))]
        result["command_files"] = [cli.record(p) for p in sorted(out.glob("command*"))]
        store.write(out / "result.json", result)
    print(result)
    return 0 if result["result"] != "IDENTITY_FAILED" else 1


if __name__ == "__main__":
    raise SystemExit(main())
