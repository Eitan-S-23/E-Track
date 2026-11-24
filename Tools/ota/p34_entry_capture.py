"""Test the original read-only BCB reader on the owned, non-resetting clock."""
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "Tools/ota"))
import p34_install_cost as host


def main():
    cli = host.cli
    cli.require(Path.cwd() == ROOT and sys.flags.isolated and sys.flags.no_site and
                sys.dont_write_bytecode, "isolated root required")
    store = cli.Store(ROOT)
    out = store.checked(ROOT / ".cache/p34-entry-capture1")
    cli.require(not out.exists(), "preserve evidence")
    db = ROOT / ".cache/p34-bc-target/b16/compile_commands.json"
    rows = [r for r in json.loads(db.read_text()) if "boot_fw_header.c" in r["file"]
            and "X_Track_Boot.dir" in r["command"]]
    cli.require(len(rows) == 1 and '"' not in rows[0]["command"], "template shape")
    template = rows[0]["command"].split()
    originals = [ROOT / "Tools/ota/recovery_entry" / n for n in
                 ("capture.c", "capture.h", "runtime.c", "runtime.h", "supervisor.h")]
    originals += [ROOT / "Tools/ota/ram_recovery" / n for n in ("bcb_reader.c", "bcb_reader.h")]
    originals += [ROOT / "tests/boot" / n for n in ("p34_entry_capture_host.c", "p34_bcb_reader_host.c")]
    library = ROOT / ".cache/p34-bc-target/f/Libraries"
    for p in originals:
        store.checked(out / "source" / p.name)
    for tag in ("compile", "run", "capture", "runtime"):
        for ext in (".json", ".log", ".o", ".su"):
            store.checked(out / (tag + ext))
    for n in ("capture.exe", "result.json"):
        store.checked(out / n)
    for p in originals:
        store.raw(out / "source" / p.name, p.read_bytes())
    src = out / "source"
    env = host.environment(store, out)
    cc = Path("D:/install/mingw64/bin/gcc.exe")
    host.command(store, out, "compile", [cc, "-std=c99", "-O2", "-Wall", "-Wextra", "-Werror",
        "-I" + str(src), "-I" + str(library), *[src / n for n in
        ("capture.c", "runtime.c", "bcb_reader.c", "p34_entry_capture_host.c")],
        library / "EEPROM/eeprom_bcb.c", "-o", out / "capture.exe"], env, 60)
    log = host.command(store, out, "run", [out / "capture.exe"], env, 60)
    cli.require(b"ENTRY_CAPTURE_HOST_PASS scenarios=8" in log, "capture integration result")
    for name in ("capture", "runtime"):
        args = list(template)
        args[args.index("-c")+1] = str(src / (name + ".c"))
        args[args.index("-o")+1] = str(out / (name + ".o"))
        args += ["-ffreestanding", "-fno-builtin", "-I" + str(src)]
        host.command(store, out, name, args, env, 60)
    inputs = [cli.record(p) for p in sorted(src.iterdir())]
    inputs += [cli.record(p) for p in (Path(__file__), db, cc, Path(template[0]),
               library / "EEPROM/eeprom_bcb.c", library / "EEPROM/eeprom_bcb.h")]
    store.write(out / "result.json", dict(result="ENTRY_CAPTURE_CLOCK_INTEGRATION_PASS", inputs=inputs,
        artifacts=[cli.record(p) for p in sorted(out.iterdir()) if p.is_file()],
        scenarios=8, hardware=False, target_linked=False, device_execute_ready=False,
        scope="new timing/ownership wrapper; unchanged reader; no fixed-pin physical adapter"))
    print(log.decode())


if __name__ == "__main__":
    main()
