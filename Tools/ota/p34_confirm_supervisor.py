"""Build and execute the independent HOST-ONLY recovery-confirmation model."""
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT/"Tools/ota"))
import p34_install_cost as host


def main():
    cli=host.cli
    cli.require(Path.cwd()==ROOT and sys.flags.isolated and sys.flags.no_site and
                sys.dont_write_bytecode,"isolated root required")
    store=cli.Store(ROOT)
    out=store.checked(ROOT/".cache/p34-confirm-supervisor1")
    cli.require(not out.exists(),"preserve previous results")
    boot=ROOT/".cache/p34-bc-target/f"
    app=ROOT/".cache/p34-early-usb-r2/f"
    component=ROOT/"Tools/ota/recovery_confirm"
    sources=[ROOT/"tests/boot/p34_confirm_supervisor_host.c",component/"confirm.c"]
    sources += [boot/"boot/src"/n for n in
                ("boot_state_machine.c","boot_fw_header.c","boot_crc32.c","boot_sha256.c","boot_slot.c")]
    sources += [boot/"Libraries/EEPROM/eeprom_bcb.c",app/"Libraries/OTA/ota_backup.c",
                app/"Libraries/OTA/ota_slot_header.c"]
    for key in ("HOME","USERPROFILE","APPDATA","LOCALAPPDATA","TEMP","TMP","TMPDIR",
                "XDG_CACHE_HOME","XDG_CONFIG_HOME","XDG_DATA_HOME","PYTHONUSERBASE",
                "PYTHONPYCACHEPREFIX","CCACHE_DIR","SCCACHE_DIR"):
        store.checked(out/"host"/key.lower())
    for n in ("test.exe","compile.log","compile.json","tests.log","tests.json","result.json"):
        store.checked(out/n)
    env=host.environment(store,out)
    cc=Path("D:/install/mingw64/bin/gcc.exe")
    args=[cc,"-std=c99","-O2","-Wall","-Wextra","-Werror","-DRR_CONFIRM_HOST_ONLY",
          "-I"+str(component),"-I"+str(boot/"boot/include"),"-I"+str(app/"Libraries"),
          *sources,"-o",out/"test.exe"]
    host.command(store,out,"compile",args,env,90)
    images=[ROOT/".cache/p34-boot/activation/after/boot.bin",
            ROOT/".cache/p34-recovery-sources1/r2-a.bin",ROOT/".cache/p34-recovery-sources1/r2-b.bin"]
    log=host.command(store,out,"tests",[out/"test.exe",*images],env,180)
    cli.require(b"CONFIRM_SUPERVISOR_HOST_PASS" in log and b"NORMAL_STAGING_PASS" in log,"missing checks")
    inputs=sources+images+[component/"confirm.h",Path(__file__),cc]
    inputs+=list((boot/"boot/include").glob("*.h"))+list((app/"Libraries/OTA").glob("*.h"))
    inputs += [app/"Libraries/EEPROM/eeprom_bcb.h"]
    store.write(out/"result.json",dict(result="HOST_ONLY_CONFIRM_SUPERVISOR_PASS",
        inputs=[cli.record(p) for p in inputs],executable=cli.record(out/"test.exe"),
        hardware=False,device_entry=False,scope="constructed states, mock EEPROM and NOR only"))
    print(log.decode())


if __name__=="__main__":
    main()
