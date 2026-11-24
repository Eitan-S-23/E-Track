"""Link isolated RAM core and peripheral ports; no takeover/device execution."""
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
    out = store.checked(ROOT/".cache/p34-ram-ports-link1")
    cli.require(not out.exists(), "preserve evidence")
    snap = ROOT/".cache/p34-bc-target/f"
    core = ROOT/"Tools/ota/ram_recovery"
    db = ROOT/".cache/p34-bc-target/b16/compile_commands.json"
    rows = [r for r in json.loads(db.read_text()) if
            "boot_fw_header.c" in r["file"] and "X_Track_Boot.dir" in r["command"]]
    cli.require(len(rows) == 1 and '"' not in rows[0]["command"], "command shape")
    template = rows[0]["command"].split()
    cc = Path(template[0]); tools = cc.parent
    sources = [core/n for n in ("writer.c","memory.c","bcb_reader.c","at32_bcb_port.c","at32_qspi_port.c")]
    sources += [snap/"boot/src"/n for n in ("boot_fw_header.c","boot_crc32.c","boot_sha256.c")]
    sources += [snap/"Libraries/EEPROM/eeprom_bcb.c"]
    sources += [snap/"MDK-ARM_F435/RTE/Device/-AT32F435RGT7"/n for n in
                ("at32f435_437_gpio.c","at32f435_437_crm.c","at32f435_437_qspi.c")]
    for key in ("HOME", "USERPROFILE", "APPDATA", "LOCALAPPDATA", "TEMP", "TMP", "TMPDIR",
                "XDG_CACHE_HOME", "XDG_CONFIG_HOME", "XDG_DATA_HOME", "PYTHONUSERBASE",
                "PYTHONPYCACHEPREFIX", "CCACHE_DIR", "SCCACHE_DIR"):
        store.checked(out/"host"/key.lower())
    for p in sources:
        for ext in (".o", ".su", ".log", ".json"): store.checked(out/(p.stem+ext))
    for n in ("ports.elf","ports.map","result.json"):
        store.checked(out/n)
    for n in ("link","undefined","symbols","sections","size","disassembly"):
        for ext in (".log",".json"): store.checked(out/(n+ext))
    env = host.environment(store,out)
    for source in sources:
        args = list(template)
        args[args.index("-o")+1] = str(out/(source.stem+".o"))
        args[args.index("-c")+1] = str(source)
        args += ["-ffreestanding","-fno-builtin","-I"+str(core)]
        host.command(store,out,source.stem,args,env,60)
    roots = ("rr_at32_bcb_capture","rr_qspi_prepare","rr_qspi_read","rr_qspi_erase","rr_qspi_program")
    args = [cc,*[a for a in template if a.startswith("-m")],"-nostdlib","-Wl,--gc-sections",
            "-Wl,--fatal-warnings","-Wl,-Map="+str(out/"ports.map"),"-T",core/"core.ld"]
    args += ["-Wl,-u,"+n for n in roots]
    args += [out/(p.stem+".o") for p in sources]+["-o",out/"ports.elf"]
    host.command(store,out,"link",args,env,60)
    undefined = host.command(store,out,"undefined",[tools/"arm-none-eabi-nm.exe","-u",out/"ports.elf"],env,30)
    cli.require(not undefined.strip(),"unresolved direct symbols")
    symbols = host.command(store,out,"symbols",[tools/"arm-none-eabi-nm.exe","-n","-S",out/"ports.elf"],env,30)
    for forbidden in (b"bcb_commit",b"boot_platform_eeprom_write",b"qspi_xip_enable"):
        cli.require(forbidden not in symbols,"forbidden/unbounded entry retained")
    for tag, tool, flags in (("sections","readelf",["-l"]),("size","size",[]),("disassembly","objdump",["-dr"])):
        log = host.command(store,out,tag,[tools/("arm-none-eabi-"+tool+".exe"),*flags,out/"ports.elf"],env,30)
        if tag == "size": print(log.decode())
    inputs = sources+list(core.glob("*.h"))+[core/"core.ld",db,Path(__file__),cc]
    # Bind the exact project SDK headers rather than only a compiler command.
    inputs += sorted((snap/"vendor").rglob("*.h"))
    inputs += sorted((snap/"boot/include").glob("*.h"))
    inputs += [snap/"Libraries/EEPROM/eeprom_bcb.h",snap/"Libraries/OTA/ota_layout.h",
               snap/"MDK-ARM_F435/cmake-generated/cmake/gcc_compat.h"]
    store.write(out/"result.json",dict(result="RAM_CORE_AND_PORTS_LINKED",
        inputs=[cli.record(p) for p in inputs],artifacts=[cli.record(out/n) for n in
        ("ports.elf","ports.map","symbols.log","sections.log","disassembly.log")],
        hardware=False,device_loader=False,takeover_proved=False,
        scope="callable ports; conditional 288MHz DWT, no source mailbox or watchdog/exit plan"))
    print("RAM_CORE_AND_PORTS_LINKED; no device entry")


if __name__ == "__main__":
    main()
