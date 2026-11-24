"""ARM compile only of BCB reader and fixed-pin port, no device execution."""
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
    out = store.checked(ROOT/".cache/p34-bcb-reader-arm1")
    cli.require(not out.exists(), "preserve outputs")
    db = ROOT/".cache/p34-bc-target/b16/compile_commands.json"
    entries = [e for e in json.loads(db.read_text()) if
               "boot_fw_header.c" in e["file"] and "X_Track_Boot.dir" in e["command"]]
    cli.require(len(entries) == 1 and '"' not in entries[0]["command"], "command shape")
    template = entries[0]["command"].split()
    core = ROOT/"Tools/ota/ram_recovery"
    inputs = [core/"bcb_reader.c", core/"at32_bcb_port.c"]
    for key in ("HOME", "USERPROFILE", "APPDATA", "LOCALAPPDATA", "TEMP", "TMP", "TMPDIR",
                "XDG_CACHE_HOME", "XDG_CONFIG_HOME", "XDG_DATA_HOME", "PYTHONUSERBASE",
                "PYTHONPYCACHEPREFIX", "CCACHE_DIR", "SCCACHE_DIR"):
        store.checked(out/"host"/key.lower())
    for source in inputs:
        for ext in (".o", ".su", ".log", ".json"): store.checked(out/(source.stem+ext))
    store.checked(out/"result.json")
    env = host.environment(store, out)
    for source in inputs:
        args = list(template)
        args[args.index("-o")+1] = str(out/(source.stem+".o"))
        args[args.index("-c")+1] = str(source)
        args += ["-ffreestanding", "-fno-builtin", "-I"+str(core)]
        host.command(store, out, source.stem, args, env, 60)
    inputs += [core/"bcb_reader.h",core/"at32_bcb_port.h",db,Path(__file__)]
    store.write(out/"result.json",dict(result="BCB_FIXED_PIN_PORT_COMPILED",
        inputs=[cli.record(p) for p in inputs], artifacts=[cli.record(p) for p in sorted(out.glob("*.o"))],
        hardware=False, linked=False, timing_validated=False, takeover_proved=False))
    print("BCB_FIXED_PIN_PORT_COMPILED; no EEPROM read or target run")


if __name__ == "__main__":
    main()
