"""Build/test isolated C recovery core; never connects to a target."""
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
    out = store.checked(ROOT/".cache/p34-ram-writer1")
    cli.require(not out.exists(), "preserve earlier evidence")
    snapshot = ROOT/".cache/p34-bc-target/f"
    inputs = [ROOT/"tests/boot/p34_ram_writer_host.c"] + [snapshot/"boot/src"/name for name in
              ("boot_fw_header.c", "boot_crc32.c", "boot_sha256.c")]
    for key in ("HOME", "USERPROFILE", "APPDATA", "LOCALAPPDATA", "TEMP", "TMP", "TMPDIR",
                "XDG_CACHE_HOME", "XDG_CONFIG_HOME", "XDG_DATA_HOME", "PYTHONUSERBASE",
                "PYTHONPYCACHEPREFIX", "CCACHE_DIR", "SCCACHE_DIR"):
        store.checked(out/"host"/key.lower())
    for n in ("writer.exe", "compile.log", "compile.json", "a.log", "a.json", "b.log", "b.json", "result.json"):
        store.checked(out/n)
    env = host.environment(store, out)
    cc = Path("D:/install/mingw64/bin/gcc.exe")
    exe = out/"writer.exe"
    args = [cc, "-std=c99", "-O2", "-Wall", "-Wextra", "-Werror",
            "-I"+str(ROOT/"Tools/ota/ram_recovery"), "-I"+str(snapshot/"boot/include"),
            "-I"+str(snapshot/"Libraries"), *inputs, "-o", exe]
    host.command(store, out, "compile", args, env, 90)
    for name in ("a", "b"):
        image = ROOT/(".cache/p34-recovery-sources1/r2-"+name+".bin")
        output = host.command(store, out, name, [exe, image], env, 90)
        cli.require(b"RAM_WRITER_HOST_PASS cases=23" in output, "native checks missing")
        inputs.append(image)
    inputs += [Path(__file__), cc, ROOT/"Tools/ota/ram_recovery/writer.c",
               ROOT/"Tools/ota/ram_recovery/writer.h", snapshot/"Libraries/OTA/ota_layout.h"]
    inputs += sorted((snapshot/"boot/include").glob("*.h"))
    store.write(out/"result.json", dict(result="RAM_WRITER_C_HOST_PASS", checks=46,
        inputs=[cli.record(p) for p in inputs], executable=cli.record(exe), hardware=False,
        scope="C transaction core with mock I/O; not target-linked RAM loader"))
    print("RAM_WRITER_C_HOST_PASS checks=46")


if __name__ == "__main__":
    main()
