"""Freestanding RAM core link proof, without device ports or takeover entry."""
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT/"Tools/ota"))
import p34_install_cost as host


def main():
    cli = host.cli
    cli.require(Path.cwd() == ROOT and sys.flags.isolated and sys.flags.no_site and
                sys.dont_write_bytecode, "isolated root required")
    store = cli.Store(ROOT)
    out = store.checked(ROOT/".cache/p34-ram-core-link2")
    cli.require(not out.exists(), "preserve previous link")
    db = ROOT/".cache/p34-bc-target/b16/compile_commands.json"
    entries = [r for r in json.loads(db.read_text()) if
               "boot_fw_header.c" in r["file"] and "X_Track_Boot.dir" in r["command"]]
    cli.require(len(entries) == 1 and '"' not in entries[0]["command"], "command shape")
    template = entries[0]["command"].split()
    cc = Path(template[0]); tools = cc.parent
    snapshot = ROOT/".cache/p34-bc-target/f"
    core = ROOT/"Tools/ota/ram_recovery"
    inputs = [core/"writer.c", core/"memory.c"] + [snapshot/"boot/src"/n for n in
              ("boot_fw_header.c", "boot_crc32.c", "boot_sha256.c")]
    names = [p.stem for p in inputs]
    for key in ("HOME", "USERPROFILE", "APPDATA", "LOCALAPPDATA", "TEMP", "TMP", "TMPDIR",
                "XDG_CACHE_HOME", "XDG_CONFIG_HOME", "XDG_DATA_HOME", "PYTHONUSERBASE",
                "PYTHONPYCACHEPREFIX", "CCACHE_DIR", "SCCACHE_DIR"):
        store.checked(out/"host"/key.lower())
    for n in names:
        for ext in (".o", ".su", ".log", ".json"): store.checked(out/(n+ext))
    for n in ("core.elf", "core.map", "result.json"):
        store.checked(out/n)
    for n in ("link", "symbols", "undefined", "sections", "size", "disassembly"):
        for ext in (".json", ".log"): store.checked(out/(n+ext))
    env = host.environment(store, out)
    for source in inputs:
        args = list(template)
        args[args.index("-o")+1] = str(out/(source.stem+".o"))
        args[args.index("-c")+1] = str(source)
        args += ["-ffreestanding", "-fno-builtin", "-I"+str(core)]
        host.command(store, out, source.stem, args, env, 60)
    # Inherit ABI flags rather than guessing a different CPU or float ABI.
    machine = [a for a in template if a.startswith("-m")]
    host.command(store, out, "link", [cc, *machine, "-nostdlib", "-Wl,--gc-sections",
                 "-Wl,--fatal-warnings", "-Wl,-Map="+str(out/"core.map"),
                 "-T", core/"core.ld", *[out/(n+".o") for n in names],
                 "-o", out/"core.elf"], env, 60)
    unknown = host.command(store, out, "undefined", [tools/"arm-none-eabi-nm.exe", "-u", out/"core.elf"], env, 30)
    cli.require(not unknown.strip(), "unresolved direct symbols")
    for tag, tool, args in (
        ("symbols", "nm", ["-n", "-S"]), ("sections", "objdump", ["-h"]),
        ("size", "size", []), ("disassembly", "objdump", ["-dr"])):
        data = host.command(store, out, tag, [tools/("arm-none-eabi-"+tool+".exe"), *args, out/"core.elf"], env, 30)
        if tag == "size": print(data.decode())
    inputs += [core/"writer.h", core/"core.ld", db, Path(__file__), cc,
               snapshot/"Libraries/OTA/ota_layout.h"]
    inputs += sorted((snapshot/"boot/include").glob("*.h"))
    inputs.append(snapshot/"MDK-ARM_F435/cmake-generated/cmake/gcc_compat.h")
    store.write(out/"result.json", dict(result="FREESTANDING_RAM_CORE_LINKED",
        inputs=[cli.record(p) for p in inputs], artifacts=[cli.record(out/n) for n in
        ("core.elf", "core.map", "undefined.log", "sections.log", "disassembly.log")],
        hardware=False, executable_device_loader=False, indirect_ports_bound=False,
        scope="linked core fits candidate overlay; ownership and full stack NOT proved"))
    print("FREESTANDING_RAM_CORE_LINKED; no device entry/ports")


if __name__ == "__main__":
    main()
