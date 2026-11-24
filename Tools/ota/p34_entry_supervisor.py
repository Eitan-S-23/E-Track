"""Contained host checks and target link for fixed supervisor callbacks."""
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
    out = store.checked(ROOT / ".cache/p34-entry-supervisor2")
    cli.require(not out.exists(), "preserve evidence")
    src = ROOT / "Tools/ota/recovery_entry"
    names = ("runtime.c", "runtime.h", "supervisor.c", "supervisor.h", "platform_at32.c", "bootstrap.S", "bootstrap.ld")
    db = ROOT / ".cache/p34-bc-target/b16/compile_commands.json"
    rows = [r for r in json.loads(db.read_text()) if "boot_fw_header.c" in r["file"] and "X_Track_Boot.dir" in r["command"]]
    cli.require(len(rows) == 1 and '"' not in rows[0]["command"], "template shape")
    template = rows[0]["command"].split()
    arm = Path(template[0]); cc = Path("D:/install/mingw64/bin/gcc.exe")
    tags = ("host_compile", "host_run", "runtime", "supervisor", "platform_at32", "bootstrap",
            "link", "disassembly", "symbols", "sections", "undefined", "size")
    for key in ("HOME", "USERPROFILE", "APPDATA", "LOCALAPPDATA", "TEMP", "TMP", "TMPDIR",
                "XDG_CACHE_HOME", "XDG_CONFIG_HOME", "XDG_DATA_HOME", "PYTHONUSERBASE",
                "PYTHONPYCACHEPREFIX", "CCACHE_DIR", "SCCACHE_DIR"):
        store.checked(out / "host" / key.lower())
    for tag in tags:
        for ext in (".log", ".json", ".o", ".su"):
            store.checked(out / (tag + ext))
    for n in names:
        store.checked(out / "source" / n)
    for n in ("supervisor.exe", "entry.elf", "entry.map", "result.json"):
        store.checked(out / n)
    for n in names:
        store.raw(out / "source" / n, (src / n).read_bytes())
    src = out / "source"
    env = host.environment(store, out)
    test = ROOT / "tests/boot/p34_entry_supervisor_host.c"
    host.command(store, out, "host_compile", [cc, "-std=c99", "-O2", "-Wall", "-Wextra", "-Werror",
        "-I" + str(src), src / "runtime.c", src / "supervisor.c", test, "-o", out / "supervisor.exe"], env, 60)
    log = host.command(store, out, "host_run", [out / "supervisor.exe"], env, 60)
    cli.require(b"ENTRY_SUPERVISOR_HOST_PASS" in log, "missing host pass")
    print(log.decode())
    sources = ("runtime.c", "supervisor.c", "platform_at32.c", "bootstrap.S")
    for name in sources:
        args = list(template)
        args[args.index("-o") + 1] = str(out / (Path(name).stem + ".o"))
        args[args.index("-c") + 1] = str(src / name)
        args += ["-ffreestanding", "-fno-builtin", "-Wa,--noexecstack", "-I" + str(src)]
        host.command(store, out, Path(name).stem, args, env, 60)
    host.command(store, out, "link", [arm, *[a for a in template if a.startswith("-m")],
        "-nostdlib", "-Wl,--gc-sections", "-Wl,--fatal-warnings", "-Wl,-u,re_supervise_once",
        "-T", src / "bootstrap.ld", "-Wl,-Map=" + str(out / "entry.map"),
        *[out / (Path(n).stem + ".o") for n in sources], "-o", out / "entry.elf"], env, 60)
    for tag, tool, flags in (("disassembly", "objdump", ["-dr"]), ("symbols", "nm", ["-n", "-S"]),
                             ("sections", "readelf", ["-l", "-S"]), ("undefined", "nm", ["-u"]), ("size", "size", [])):
        output = host.command(store, out, tag, [arm.parent / ("arm-none-eabi-" + tool + ".exe"),
                                               *flags, out / "entry.elf"], env, 60)
        if tag == "undefined": cli.require(not output.strip(), "unresolved symbol")
    inputs = [Path(__file__), db, cc, arm, test] + [src / n for n in names]
    inputs += sorted((ROOT / ".cache/p34-bc-target/f/vendor").rglob("*.h"))
    store.write(out / "result.json", dict(result="SUPERVISOR_HOST_AND_TARGET_LINK_PASS",
        inputs=[cli.record(p) for p in inputs], artifacts=[cli.record(out / n) for n in
        ("entry.elf", "entry.map", "disassembly.log", "symbols.log")],
        hardware=False, device_execute_ready=False, bootstrap_dispatch=False))
    print("SUPERVISOR_HOST_AND_TARGET_LINK_PASS; no device execution")

if __name__ == "__main__":
    main()
