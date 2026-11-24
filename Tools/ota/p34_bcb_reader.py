"""Host verification of read-only BCB wire sequence and snapshot arbitration."""
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
    out = store.checked(ROOT/".cache/p34-bcb-reader1")
    cli.require(not out.exists(), "preserve evidence")
    snapshot = ROOT/".cache/p34-bc-target/f"
    core = ROOT/"Tools/ota/ram_recovery"
    sources = [ROOT/"tests/boot/p34_bcb_reader_host.c", core/"bcb_reader.c",
               snapshot/"Libraries/EEPROM/eeprom_bcb.c"]
    for key in ("HOME", "USERPROFILE", "APPDATA", "LOCALAPPDATA", "TEMP", "TMP", "TMPDIR",
                "XDG_CACHE_HOME", "XDG_CONFIG_HOME", "XDG_DATA_HOME", "PYTHONUSERBASE",
                "PYTHONPYCACHEPREFIX", "CCACHE_DIR", "SCCACHE_DIR"):
        store.checked(out/"host"/key.lower())
    for name in ("reader.exe", "compile.json", "compile.log", "tests.json", "tests.log", "result.json"):
        store.checked(out/name)
    env = host.environment(store, out)
    cc = Path("D:/install/mingw64/bin/gcc.exe")
    host.command(store, out, "compile", [cc,"-std=c99","-O2","-Wall","-Wextra","-Werror",
                 "-I"+str(core),"-I"+str(snapshot/"Libraries"),*sources,"-o",out/"reader.exe"], env,90)
    log = host.command(store,out,"tests",[out/"reader.exe"],env,90)
    cli.require(b"BCB_READER_HOST_PASS" in log, "checks missing")
    store.write(out/"result.json",dict(result="BCB_READER_HOST_PASS",
        inputs=[cli.record(p) for p in sources+[core/"bcb_reader.h",Path(__file__),cc,
                snapshot/"Libraries/EEPROM/eeprom_bcb.h"]],
        executable=cli.record(out/"reader.exe"),hardware=False,
        scope="mock GPIO protocol and real arbiter; no actual EEPROM observation"))
    print(log.decode())


if __name__ == "__main__":
    main()
