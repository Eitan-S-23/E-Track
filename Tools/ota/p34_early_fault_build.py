"""Bounded corrected build route: normalize __FILE__ only, retain old receipts."""
import argparse
from pathlib import Path
import re
import sys

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "Tools/ota"))
import p34_early_fault as e


def main(mode):
    cli, host = e.model.cli, e.model.host
    s = cli.Store(ROOT)
    p = s.read(e.AREA / "prepared.json")
    for r in p["sources"] + p["implementation"]:
        cli.require(cli.record(r["path"]) == r, "prepared drift")
    host_tests = s.read(e.AREA / "tests/result.json")
    cli.require(host_tests["result"] == "EARLY_HOST_PASS", "host checks required")
    for r in host_tests["inputs"]: cli.require(cli.record(r["path"]) == r, "host test drift")
    if mode == "on":
        cli.require(s.read(e.AREA / "off2/result.json")["baseline_identical"], "OFF reproduction required")
    out = s.checked(e.AREA / ("off2" if mode == "off" else "on"))
    cli.require(not out.exists(), "preserve outputs")
    for name in ("result.json", "inputs.json", "elf.bin", "b", "install"): s.checked(out / name)
    for tag in ("configure", "build", "symbols", "disassembly", "extract", "attributes"):
        for suffix in (".log", ".json"): s.checked(out / (tag + suffix))
    bound = [cli.record(Path(__file__)), cli.record(e.AREA / "prepared.json"), cli.record(e.AREA / "tests/result.json")]
    env = host.environment(s, out)
    args = s.read(e.BASE / "build/configure.json")["command"]
    args = [x.replace(str(e.BASE / "f"), str(e.AREA / "f")).replace(str(e.BASE / "b"), str(out / "b"))
            .replace(str(e.BASE / "install"), str(out / "install")) for x in args]
    mapping = "-fmacro-prefix-map=" + (e.AREA / "f").as_posix() + "=" + (e.BASE / "f").as_posix()
    args = [x + " " + mapping if x.startswith(("-DCMAKE_C_FLAGS:STRING=", "-DCMAKE_CXX_FLAGS:STRING=")) else x for x in args]
    args.append("-DP34_EARLY_FAULT_VECTORS=" + mode.upper())
    s.write(out / "inputs.json", dict(inputs=bound, macro_path_mapping=mapping,
            reason="Four LVGL __FILE__ strings in prior OFF changed binary layout; actual source/output paths unchanged"))
    host.command(s, out, "configure", args, env, 180)
    raw = host.command(s, out, "build", [args[0], "--build", out / "b", "--target", "X_Track_App_GCC", "--parallel", "6"], env, 900)
    elf = out / "b/app-gcc/X-Track-App-GCC.elf"; arm = e.tc.ARM / "bin"
    for tag, tool, flags in [("symbols", "nm", ["-n", "-S"]), ("disassembly", "objdump", ["-d"]),
                             ("attributes", "readelf", ["-h", "-S", "-A"])]:
        host.command(s, out, tag, [arm / ("arm-none-eabi-" + tool + ".exe"), *flags, elf], env, 60)
    host.command(s, out, "extract", [arm / "arm-none-eabi-objcopy.exe", "-O", "binary", elf, out / "elf.bin"], env, 60)
    binary = out / "b/app-gcc/X-Track-App-GCC.bin"
    cli.require(binary.read_bytes() == (out / "elf.bin").read_bytes(), "ELF binding")
    equal = binary.read_bytes() == (e.BASE / "b/app-gcc/X-Track-App-GCC.bin").read_bytes()
    if mode == "off":
        cli.require(equal, "OFF still differs")
        for marker in (b"p34_early_exception", b"p34_runtime_vectors", b"p34_enable_runtime_vectors"):
            cli.require(marker not in (out / "symbols.log").read_bytes(), "OFF leaked symbols")
    for r in p["sources"] + p["implementation"] + bound:
        cli.require(cli.record(r["path"]) == r, "source changed")
    s.write(out / "result.json", dict(result="EARLY_APP_BUILT", mode=mode, baseline_identical=equal,
        artifacts=[cli.record(out / "b/app-gcc" / ("X-Track-App-GCC." + ext)) for ext in ("bin", "elf", "map", "hex")],
        inputs=bound, warnings=len(re.findall(rb"warning:", raw)), errors=len(re.findall(rb"error:", raw)),
        hardware=False, measured_speedup=False, independent_acceptance=False))
    print("EARLY_APP_BUILT", mode, binary.stat().st_size, "baseline_identical", equal)


if __name__ == "__main__":
    e.model.cli.require(Path.cwd() == ROOT and sys.flags.isolated and sys.flags.no_site and sys.dont_write_bytecode,
                        "isolated root required")
    p = argparse.ArgumentParser(); p.add_argument("mode", choices=("off", "on"))
    main(p.parse_args().mode)
