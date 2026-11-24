"""Build a terminal-only RAM entry scaffold and retained observer, never load it."""
from pathlib import Path
import json
import sys
ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "Tools/ota"))
import p34_install_cost as host

def main():
    cli = host.cli
    cli.require(Path.cwd() == ROOT and sys.flags.isolated and sys.flags.no_site
                and sys.dont_write_bytecode, "isolated root required")
    store = cli.Store(ROOT)
    out = store.checked(ROOT / ".cache/p34-entry-bootstrap3")
    cli.require(not out.exists(), "preserve evidence")
    db = ROOT / ".cache/p34-bc-target/b16/compile_commands.json"
    rows = [r for r in json.loads(db.read_text()) if "boot_fw_header.c" in r["file"]
            and "X_Track_Boot.dir" in r["command"]]
    cli.require(len(rows) == 1 and '"' not in rows[0]["command"], "command shape")
    template = rows[0]["command"].split()
    cc = Path(template[0])
    src = ROOT / "Tools/ota/recovery_entry"
    for key in ("HOME", "USERPROFILE", "APPDATA", "LOCALAPPDATA", "TEMP", "TMP", "TMPDIR",
                "XDG_CACHE_HOME", "XDG_CONFIG_HOME", "XDG_DATA_HOME", "PYTHONUSERBASE",
                "PYTHONPYCACHEPREFIX", "CCACHE_DIR", "SCCACHE_DIR"):
        store.checked(out / "host" / key.lower())
    for tag in ("bootstrap", "runtime", "link", "disassembly", "symbols", "sections", "size", "undefined"):
        for ext in (".log", ".json", ".o", ".su"):
            store.checked(out / (tag + ext))
    for name in ("entry.elf", "entry.map", "result.json"):
        store.checked(out / name)
    for name in ("bootstrap.S", "bootstrap.ld", "runtime.c", "runtime.h"):
        store.checked(out / "source" / name)
    for name in ("bootstrap.S", "bootstrap.ld", "runtime.c", "runtime.h"):
        store.raw(out / "source" / name, (src / name).read_bytes())
    src = out / "source"
    env = host.environment(store, out)
    for name in ("bootstrap.S", "runtime.c"):
        args = list(template)
        args[args.index("-o") + 1] = str(out / (Path(name).stem + ".o"))
        args[args.index("-c") + 1] = str(src / name)
        args += ["-ffreestanding", "-fno-builtin", "-Wa,--noexecstack", "-I" + str(src)]
        host.command(store, out, Path(name).stem, args, env, 60)
    args = [cc, *[a for a in template if a.startswith("-m")], "-nostdlib", "-Wl,--gc-sections",
            "-Wl,--fatal-warnings", "-Wl,-u,re_observe", "-T", src / "bootstrap.ld",
            "-Wl,-Map=" + str(out / "entry.map"), out / "bootstrap.o", out / "runtime.o",
            "-o", out / "entry.elf"]
    host.command(store, out, "link", args, env, 60)
    for tag, name, flags in (("disassembly", "objdump", ["-dr"]), ("symbols", "nm", ["-n", "-S"]),
                            ("sections", "readelf", ["-l", "-S"]), ("size", "size", []),
                            ("undefined", "nm", ["-u"])):
        log = host.command(store, out, tag, [cc.parent / ("arm-none-eabi-" + name + ".exe"),
                                           *flags, out / "entry.elf"], env, 60)
        if tag == "undefined":
            cli.require(not log.strip(), "unresolved symbol")
    store.write(out / "result.json", dict(result="TERMINAL_ONLY_RAM_SCAFFOLD_LINKED",
        inputs=[cli.record(p) for p in (Path(__file__), db, cc, src / "bootstrap.S", src / "bootstrap.ld",
                                       src / "runtime.c", src / "runtime.h")],
        artifacts=[cli.record(out / n) for n in ("entry.elf", "entry.map", "disassembly.log", "symbols.log")],
        device_execute_ready=False, hardware=False, media_dispatch=False,
        scope="entry terminates after isolated BSS initialization; observer retained but not dispatched"))
    print("TERMINAL_ONLY_RAM_SCAFFOLD_LINKED; device_execute_ready=false")

if __name__ == "__main__":
    main()
