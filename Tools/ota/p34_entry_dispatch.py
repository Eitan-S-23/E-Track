"""One-shot offline dispatch build, with an unqualified compiled-in profile."""
import argparse
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "Tools/ota"))
import p34_install_cost as host
from recovery_entry.load_contract import inspect
from recovery_entry.stack_audit import analyze, load_bytes


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--output-dir", default=".cache/p34-entry-dispatch4")
    parser.add_argument("--capability", choices=("nor", "bcb"), default="nor")
    args = parser.parse_args()
    cli = host.cli
    cli.require(Path.cwd() == ROOT and sys.flags.isolated and sys.flags.no_site
                and sys.dont_write_bytecode, "isolated root required")
    store = cli.Store(ROOT)
    out = store.checked(ROOT / args.output_dir)
    cli.require(not out.exists(), "preserve evidence")
    src = ROOT / "Tools/ota/recovery_entry"
    names = ("runtime.c", "runtime.h", "supervisor.c", "supervisor.h", "platform_at32.c",
             "bootstrap.S", "bootstrap.ld", "dispatch.c", "dispatch.h", "profile.c", "qualification.c")
    source_files = {n: src / n for n in names}
    if args.capability == "bcb":
        source_files.update({n: src / n for n in ("capture.c", "capture.h", "bcb_target.c", "bcb_target.h",
                             "bcb_platform_at32.c", "bcb_dispatch.c")})
        source_files.update({n: ROOT / "Tools/ota/ram_recovery" / n for n in
                             ("bcb_reader.c", "bcb_reader.h", "memory.c", "writer.h")})
        source_files["eeprom_bcb.c"] = ROOT / ".cache/p34-bc-target/f/Libraries/EEPROM/eeprom_bcb.c"
        source_files["EEPROM/eeprom_bcb.h"] = ROOT / ".cache/p34-bc-target/f/Libraries/EEPROM/eeprom_bcb.h"
    names = tuple(source_files)
    db = ROOT / ".cache/p34-bc-target/b16/compile_commands.json"
    rows = [r for r in json.loads(db.read_text()) if "boot_fw_header.c" in r["file"]
            and "X_Track_Boot.dir" in r["command"]]
    cli.require(len(rows) == 1 and '"' not in rows[0]["command"], "compile template")
    template = rows[0]["command"].split()
    arm, cc = Path(template[0]), Path("D:/install/mingw64/bin/gcc.exe")
    sources = [n for n in names if n.endswith((".c", ".S"))]
    if args.capability == "bcb":
        sources = [n for n in sources if n not in ("supervisor.c", "dispatch.c")]
    tags = [Path(n).stem for n in sources] + ["host_compile", "supervisor_compile", "supervisor_run",
        "link", "disassembly", "symbols", "sections", "undefined", "size", "contract_tests",
        "timing_compile", "timing_run", "runtime_compile", "runtime_run"]
    if args.capability == "bcb":
        tags += ["gpio_compile", "gpio_run", "bcb_compile", "report_tests"] + ["bcb_" + str(i) for i in range(12)]
    tags += ["dispatch_" + str(i) for i in range(8)]
    for tag in tags:
        for ext in (".log", ".json", ".o", ".su"):
            store.checked(out / (tag + ext))
    for n in names:
        store.checked(out / "source" / n)
    tests = [ROOT / "tests/boot" / n for n in ("p34_entry_dispatch_host.c", "p34_entry_supervisor_host.c",
                                               "test_p34_dispatch_contract.py", "p34_entry_timing_host.c",
                                               "p34_entry_runtime_host.c")]
    helpers = [Path(__file__), ROOT / "Tools/ota/recovery_entry/load_contract.py",
               ROOT / "Tools/ota/recovery_entry/stack_audit.py", ROOT / "Tools/ota/p34_boot_stack.py"]
    if args.capability == "bcb":
        tests += [ROOT / "tests/boot" / n for n in
                  ("p34_entry_bcb_target_host.c", "p34_bcb_reader_host.c", "p34_entry_gpio_host.c",
                   "test_p34_entry_report.py")]
        helpers += [ROOT / "Tools/ota/recovery_entry/report.py"]
        store.checked(out / "source/gpio-mock/at32f435_437.h")
        store.checked(out / "gpio.exe")
        store.checked(out / "bcb.exe")
    for p in tests + helpers:
        store.checked(out / "source" / p.name)
    for n in ("dispatch.exe", "supervisor.exe", "timing.exe", "runtime.exe", "entry.elf", "entry.map",
              "result.json", "analysis.json"):
        store.checked(out / n)
    # Capture exact source bytes before compiler or test execution.
    for name, p in source_files.items():
        store.raw(out / "source" / name, p.read_bytes())
    for p in tests + helpers:
        store.raw(out / "source" / p.name, p.read_bytes())
    if args.capability == "bcb":
        store.raw(out / "source/gpio-mock/at32f435_437.h",
                  (ROOT / "tests/boot/p34_entry_gpio_mock/at32f435_437.h").read_bytes())
    src = out / "source"
    env = host.environment(store, out)
    base = [cc, "-std=c99", "-O2", "-Wall", "-Wextra", "-Werror", "-I" + str(src)]
    if args.capability == "bcb": base += ["-I" + str(src / "EEPROM")]
    for name, count in (("timing", 12), ("runtime", 15)):
        host.command(store, out, name + "_compile", base + [src / "runtime.c",
            src / ("p34_entry_" + name + "_host.c"), "-o", out / (name + ".exe")], env, 60)
        log = host.command(store, out, name + "_run", [out / (name + ".exe")], env, 60)
        cli.require(("HOST_PASS scenarios=" + str(count)).encode() in log, "timing/runtime result")
    host.command(store, out, "host_compile", base + [src / n for n in
        ("runtime.c", "qualification.c", "supervisor.c", "dispatch.c", "p34_entry_dispatch_host.c")] +
        ["-o", out / "dispatch.exe"], env, 60)
    for i in range(8):
        log = host.command(store, out, "dispatch_" + str(i), [out / "dispatch.exe", str(i)], env, 60)
        cli.require(b"ENTRY_DISPATCH_HOST_PASS" in log, "dispatch result")
    host.command(store, out, "supervisor_compile", base + [src / n for n in
        ("runtime.c", "qualification.c", "supervisor.c", "p34_entry_supervisor_host.c")] +
        ["-o", out / "supervisor.exe"], env, 60)
    log = host.command(store, out, "supervisor_run", [out / "supervisor.exe"], env, 60)
    cli.require(b"ENTRY_SUPERVISOR_HOST_PASS scenarios=55" in log, "supervisor result")
    if args.capability == "bcb":
        host.command(store, out, "gpio_compile", base + ["-I" + str(src / "gpio-mock"),
            src / "bcb_platform_at32.c", src / "p34_entry_gpio_host.c", "-o", out / "gpio.exe"], env, 60)
        log = host.command(store, out, "gpio_run", [out / "gpio.exe"], env, 60)
        cli.require(b"ENTRY_GPIO_HOST_PASS scenarios=12" in log, "GPIO result")
        host.command(store, out, "bcb_compile", base + [src / n for n in ("runtime.c", "qualification.c",
            "capture.c", "bcb_target.c", "bcb_dispatch.c", "bcb_reader.c", "eeprom_bcb.c",
            "p34_entry_bcb_target_host.c")] + ["-o", out / "bcb.exe"], env, 60)
        for i in range(12):
            log = host.command(store, out, "bcb_" + str(i), [out / "bcb.exe", str(i)], env, 60)
            cli.require(b"ENTRY_BCB_TARGET_HOST_PASS" in log, "BCB target result")
    for name in sources:
        cmd = list(template)
        cmd[cmd.index("-o")+1] = str(out / (Path(name).stem + ".o"))
        cmd[cmd.index("-c")+1] = str(src / name)
        define = "RE_ENTRY_BCB_CAPTURE" if args.capability == "bcb" else "RE_ENTRY_DISPATCH"
        cmd += ["-ffreestanding", "-fno-builtin", "-Wa,--noexecstack", "-D" + define + "=1", "-I" + str(src)]
        if args.capability == "bcb": cmd += ["-I" + str(src / "EEPROM")]
        host.command(store, out, Path(name).stem, cmd, env, 60)
    host.command(store, out, "link", [arm, *[a for a in template if a.startswith("-m")],
        "-nostdlib", "-Wl,--gc-sections", "-Wl,--fatal-warnings", "-T", src / "bootstrap.ld",
        "-Wl,-Map=" + str(out / "entry.map"), *[out / (Path(n).stem + ".o") for n in sources],
        "-o", out / "entry.elf"], env, 60)
    for tag, tool, flags in (("disassembly", "objdump", ["-dr"]), ("symbols", "nm", ["-n", "-S"]),
                             ("sections", "readelf", ["-l", "-S"]), ("undefined", "nm", ["-u"]), ("size", "size", [])):
        log = host.command(store, out, tag, [arm.parent / ("arm-none-eabi-" + tool + ".exe"),
                                           *flags, out / "entry.elf"], env, 60)
        if tag == "undefined": cli.require(not log.strip(), "unresolved symbols")
    elf = (out / "entry.elf").read_bytes()
    symbols, dis = (out / "symbols.log").read_text(), (out / "disassembly.log").read_text()
    layout = inspect(elf, dispatched=args.capability == "nor", bcb_capture=args.capability == "bcb")
    analysis = analyze(elf, symbols, dis, [p.read_text() for p in sorted(out.glob("*.su"))], capability=args.capability)
    import re
    profile = re.findall(r"(?m)^([0-9a-f]+) ([0-9a-f]+) [rRtT] re_compiled_profile$", symbols)
    cli.require(len(profile) == 1, "immutable profile symbol")
    address, size = (int(v, 16) for v in profile[0])
    cli.require(size == 80 and load_bytes(elf, address, size) == bytes(80), "unqualified profile required")
    entry = "re_bcb_entry_dispatch" if args.capability == "bcb" else "re_entry_dispatch"
    cli.require(entry in analysis["graph"]["re_bootstrap_entry"], "missing bootstrap dispatch")
    if args.capability == "bcb":
        for forbidden in ("bcb_commit", "re_observe", "re_supervise_once", "re_platform_write32",
                          "rr_workspace_storage", "rr_at32_bcb_capture"):
            cli.require(not re.search(r"\b" + forbidden + r"$", symbols, re.M), "forbidden symbol: " + forbidden)
    store.write(out / "analysis.json", dict(layout=layout, stack=analysis, profile_qualified=False))
    env["RE_ENTRY_TEST_BUILD"] = str(out)
    env["RE_ENTRY_TEST_CAPABILITY"] = args.capability
    host.command(store, out, "contract_tests", [sys.executable, "-I", "-S", "-B", "-X", "utf8",
        tests[2], "-v"], env, 60)
    if args.capability == "bcb":
        host.command(store, out, "report_tests", [sys.executable, "-I", "-S", "-B", "-X", "utf8",
            ROOT / "tests/boot/test_p34_entry_report.py", "-v"], env, 60)
    compile_tags = [Path(n).stem for n in sources] + ["host_compile", "supervisor_compile", "link",
                                                       "timing_compile", "runtime_compile"]
    if args.capability == "bcb": compile_tags += ["gpio_compile", "bcb_compile"]
    diagnostics = b"\n".join((out / (tag + ".log")).read_bytes() for tag in compile_tags)
    warnings = len(re.findall(rb"\bwarning:", diagnostics, re.I))
    errors = len(re.findall(rb"\berror:", diagnostics, re.I))
    cli.require(warnings == errors == 0, "unexpected compile/link diagnostics")
    inputs = [cli.record(p) for p in sorted(src.rglob("*")) if p.is_file()] + [cli.record(db), cli.record(arm), cli.record(cc)]
    inputs += [cli.record(p) for p in sorted((ROOT / ".cache/p34-bc-target/f/vendor").rglob("*.h"))]
    inputs += [cli.record(ROOT / p) for p in ("Tools/ota/p34_install_cost.py", "Tools/ota/p34_session.py",
               ".agents/skills/e-track-flutter-debug/scripts/host_io.py")]
    outputs = [cli.record(p) for p in sorted(out.iterdir()) if p.is_file()]
    store.write(out / "result.json", dict(result="ENTRY_ONE_SHOT_DISPATCH_SELFTEST_PASS", inputs=inputs,
        artifacts=outputs, host_dispatch_scenarios=8, host_supervisor_scenarios=55,
        host_timing_scenarios=12, host_runtime_scenarios=15,
        capability=args.capability, host_bcb_scenarios=12 if args.capability == "bcb" else 0,
        host_gpio_scenarios=12 if args.capability == "bcb" else 0,
        warnings=warnings, errors=errors, hardware=False, device_execute_ready=False,
        profile_qualified=False, independent_acceptance=False))
    print(json.dumps(dict(result="ENTRY_ONE_SHOT_DISPATCH_SELFTEST_PASS", stack=analysis["entries"],
                          warnings=warnings, errors=errors, device_execute_ready=False), indent=2))


if __name__ == "__main__":
    main()
