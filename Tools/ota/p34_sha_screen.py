"""Host correctness and ARM object-size screen; no firmware/device writes."""
import argparse
import hashlib
import json
from pathlib import Path
import shlex
import sys

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "Tools/ota"))
import p34_install_cost as host

cli = host.cli
BASE = ROOT / ".cache/p34-timed-ack"
SOURCE = BASE / "f/boot/src/boot_sha256.c"
HEADER = BASE / "f/boot/include/boot_crypto.h"
TEST = ROOT / "tests/ota/p34_sha_vectors.c"
LENGTHS = (0, 1, 55, 56, 63, 64, 65, 255, 256, 257, 4095, 4096, 617492)
CHUNKS = (1, 7, 63, 64, 65, 256, 4096, 617492)


def verify_vectors(data):
    expected = {(n, chunk, align) for n in LENGTHS for chunk in CHUNKS for align in (0, 1)}
    pattern = bytes((i * 17 + 3) % 256 for i in range(max(LENGTHS) + 2))
    digests = {(n, align): hashlib.sha256(pattern[align:align+n]).hexdigest()
               for n in LENGTHS for align in (0, 1)}
    seen = set()
    for line in data.decode("ascii").splitlines():
        parts = line.split()
        cli.require(len(parts) == 4, "malformed SHA vector")
        n, chunk, align = map(int, parts[:3])
        key = n, chunk, align
        cli.require(key in expected and key not in seen, "unexpected or duplicate SHA vector")
        cli.require(parts[3] == digests[n, align], "SHA differs from independent hashlib oracle")
        seen.add(key)
    cli.require(seen == expected, "missing SHA vectors")
    return len(seen)


def run(out):
    store = cli.Store(ROOT)
    out = store.checked(out)
    cli.require(not out.exists(), "preserve prior SHA screen")
    manifest = store.read(BASE / "build/source.json")
    for path in (SOURCE, HEADER):
        cli.require(cli.record(path) in manifest["files"], "source differs from measured firmware")
    inputs = [cli.record(p) for p in (SOURCE, HEADER, TEST, Path(__file__),
                                    BASE / "b/build.ninja", BASE / "build/configure.json")]
    lines = (BASE / "b/build.ninja").read_text().splitlines()
    entries = [i for i, line in enumerate(lines) if
               line.startswith("build CMakeFiles/X_Track_App_GCC.dir/") and "/boot_sha256.c.obj:" in line]
    cli.require(len(entries) == 1, "unique measured App SHA command required")
    entry = lines[entries[0]:entries[0]+8]
    flags = next(line.split(" = ", 1)[1] for line in entry if line.startswith("  FLAGS = "))
    includes = next(line.split(" = ", 1)[1] for line in entry if line.startswith("  INCLUDES = "))
    defines = next(line.split(" = ", 1)[1] for line in entry if line.startswith("  DEFINES = "))
    original_flags = shlex.split(defines + " " + flags + " " + includes)
    cli.require(original_flags.count("-Oz") == 1 and "-DOTA_TARGET_APP" in original_flags,
                "measured SHA optimization flags differ")
    configure = store.read(BASE / "build/configure.json")["command"]
    compiler = Path(next(x.split("=", 1)[1] for x in configure if x.startswith("-DCMAKE_C_COMPILER=")))
    size = compiler.with_name("arm-none-eabi-size.exe")
    # All compiler products, stack reports, receipts, temp/home/cache paths are
    # enumerated before the first build. Source and measured firmware are read-only.
    for optimization in ("Oz", "O2"):
        for suffix in (".exe", ".o", ".su"):
            store.checked(out / (optimization + suffix))
        for tag in ("native-compile", "vectors", "arm-compile", "size"):
            for suffix in (".log", ".json"):
                store.checked(out / (optimization + "-" + tag + suffix))
    store.checked(out / "result.json")
    for key in ("HOME", "USERPROFILE", "APPDATA", "LOCALAPPDATA", "TEMP", "TMP", "TMPDIR",
                "XDG_CACHE_HOME", "XDG_CONFIG_HOME", "XDG_DATA_HOME", "PYTHONUSERBASE",
                "PYTHONPYCACHEPREFIX", "CCACHE_DIR", "SCCACHE_DIR"):
        store.checked(out / "host" / key.lower())
    env = host.environment(store, out)
    results = {}
    for optimization in ("Oz", "O2"):
        exe, obj = out / (optimization + ".exe"), out / (optimization + ".o")
        host.command(store, out, optimization + "-native-compile",
            ["D:/install/mingw64/bin/gcc.exe", "-std=c99", "-" + optimization,
             "-Wall", "-Wextra", "-Werror", "-I" + str(HEADER.parent), SOURCE, TEST, "-o", exe], env, 90)
        data = host.command(store, out, optimization + "-vectors", [exe], env, 90)
        count = verify_vectors(data)
        arm_flags = ["-" + optimization if x == "-Oz" else x for x in original_flags]
        output = host.command(store, out, optimization + "-arm-compile",
                              [compiler, *arm_flags, "-c", SOURCE, "-o", obj], env, 90)
        cli.require(b"warning:" not in output and b"error:" not in output, "ARM diagnostics")
        sizes = host.command(store, out, optimization + "-size", [size, obj], env, 30)
        fields = sizes.decode().splitlines()[-1].split()
        results[optimization] = dict(vectors=count, text=int(fields[0]), data=int(fields[1]),
            bss=int(fields[2]), object=cli.record(obj), stack=cli.record(out / (optimization + ".su")))
    cli.require(inputs == [cli.record(x["path"]) for x in inputs], "screen inputs changed")
    value = dict(result="SHA_OPTIMIZATION_HOST_SCREEN_PASS", inputs=inputs, variants=results,
        device_operations=0, firmware_built=False, measured_speedup=False,
        scope="Unchanged SHA source, independent host digest oracle and target ARM compile only. "
              "No target latency measurement; object size and x86 correctness do not establish MCU speed.")
    store.write(out / "result.json", value)
    print(json.dumps(value))


if __name__ == "__main__":
    cli.require(Path.cwd() == ROOT and sys.flags.isolated and sys.flags.no_site and
                sys.dont_write_bytecode, "explicit isolated project root required")
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", type=Path, required=True)
    run(parser.parse_args().out)
