"""Build isolated observer/timebase host tests; no physical MMIO adapter."""
from pathlib import Path
import sys
ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "Tools/ota"))
import p34_install_cost as host

def main():
    cli = host.cli
    cli.require(Path.cwd() == ROOT and sys.flags.isolated and sys.flags.no_site
                and sys.dont_write_bytecode, "isolated root required")
    store = cli.Store(ROOT)
    out = store.checked(ROOT / ".cache/p34-entry-runtime1")
    cli.require(not out.exists(), "preserve evidence")
    for key in ("HOME", "USERPROFILE", "APPDATA", "LOCALAPPDATA", "TEMP", "TMP", "TMPDIR",
                "XDG_CACHE_HOME", "XDG_CONFIG_HOME", "XDG_DATA_HOME", "PYTHONUSERBASE",
                "PYTHONPYCACHEPREFIX", "CCACHE_DIR", "SCCACHE_DIR"):
        store.checked(out / "host" / key.lower())
    for n in ("runtime.exe", "compile.log", "compile.json", "run.log", "run.json", "result.json"):
        store.checked(out / n)
    env = host.environment(store, out)
    cc = Path("D:/install/mingw64/bin/gcc.exe")
    source = ROOT / "Tools/ota/recovery_entry"
    test = ROOT / "tests/boot/p34_entry_runtime_host.c"
    host.command(store, out, "compile", [cc, "-std=c99", "-O2", "-Wall", "-Wextra", "-Werror",
                 "-I" + str(source), source / "runtime.c", test, "-o", out / "runtime.exe"], env, 60)
    log = host.command(store, out, "run", [out / "runtime.exe"], env, 60)
    cli.require(b"ENTRY_RUNTIME_HOST_PASS scenarios=15" in log, "missing checks")
    store.write(out / "result.json", dict(result="ENTRY_RUNTIME_HOST_PASS", scenarios=15,
        inputs=[cli.record(p) for p in (Path(__file__), cc, source / "runtime.c", source / "runtime.h", test)],
        hardware=False, target_adapter=False, device_execute_ready=False))
    print(log.decode())

if __name__ == "__main__":
    main()
