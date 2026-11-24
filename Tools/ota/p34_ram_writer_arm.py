"""Compile the isolated core with inherited Boot ABI; no target link/execution."""
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
    out = store.checked(ROOT/".cache/p34-ram-writer-arm1")
    cli.require(not out.exists(), "preserve evidence")
    prior = ROOT/".cache/p34-ram-writer1/result.json"
    tests = store.read(prior)
    for item in tests["inputs"]:
        cli.require(cli.record(item["path"]) == item, "tested core drift")
    database = ROOT/".cache/p34-bc-target/b16/compile_commands.json"
    entries = [r for r in json.loads(database.read_text()) if
               "boot_fw_header.c" in r["file"] and "X_Track_Boot.dir" in r["command"]]
    cli.require(len(entries) == 1, "ambiguous ABI template")
    template = entries[0]["command"]
    cli.require('"' not in template and "'" not in template, "quoted template needs explicit parser")
    args = template.split()
    cli.require(args.count("-o") == args.count("-c") == 1, "unknown command shape")
    args[args.index("-o")+1] = str(store.checked(out/"writer.o"))
    args[args.index("-c")+1] = str(ROOT/"Tools/ota/ram_recovery/writer.c")
    for key in ("HOME", "USERPROFILE", "APPDATA", "LOCALAPPDATA", "TEMP", "TMP", "TMPDIR",
                "XDG_CACHE_HOME", "XDG_CONFIG_HOME", "XDG_DATA_HOME", "PYTHONUSERBASE",
                "PYTHONPYCACHEPREFIX", "CCACHE_DIR", "SCCACHE_DIR"):
        store.checked(out/"host"/key.lower())
    for n in ("writer.su", "compile.json", "compile.log", "symbols.log", "symbols.json",
              "disassembly.json", "disassembly.log", "result.json"):
        store.checked(out/n)
    env = host.environment(store, out)
    host.command(store, out, "compile", args, env, 90)
    bin_dir = Path(args[0]).parent
    host.command(store, out, "symbols", [bin_dir/"arm-none-eabi-nm.exe", "-u", out/"writer.o"], env, 30)
    host.command(store, out, "disassembly", [bin_dir/"arm-none-eabi-objdump.exe", "-dr", out/"writer.o"], env, 30)
    paths = [Path(__file__), database, prior, ROOT/"Tools/ota/ram_recovery/writer.c",
             ROOT/"Tools/ota/ram_recovery/writer.h", Path(args[0])]
    store.write(out/"result.json", dict(result="ARM_TRANSACTION_CORE_COMPILED",
        inputs=[cli.record(p) for p in paths], object=cli.record(out/"writer.o"),
        stack=cli.record(out/"writer.su"), symbols=cli.record(out/"symbols.log"),
        hardware=False, linked=False, ram_layout_proved=False,
        scope="inherited ABI compile only; unresolved calls retained, no target stack bound"))
    print("ARM_TRANSACTION_CORE_COMPILED; not linked or executable")
    print((out/"writer.su").read_text())
    print((out/"symbols.log").read_text())


if __name__ == "__main__":
    main()
