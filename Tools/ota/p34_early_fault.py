"""Reviewed early-exception isolated App OFF/ON preparation and GCC build."""
import argparse
import json
from pathlib import Path
import re
import shutil
import struct
import sys

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "Tools/ota"))
import p34_boot_checkpoint_model as model
import p34_boot_candidate as tc

BASE = ROOT / ".cache/p34-sha-candidate"
AREA = ROOT / ".cache/p34-early-fault"
CM = Path("MDK-ARM_F435/cmake-generated/CMakeLists.txt")
START = CM.parent / "cmake/sources/startup_at32f435_437_gcc.S"
LINK = Path("cmake/linker/x-track-app-gcc.ld.S")
FAULT = CM.parent / "cmake/sources/HAL_FaultHandle_20e7c83ac691.cpp"
SLOTS = (2, 3, 4, 5, 6, 11, 12, 14)
APPEND = '''
# Reviewed isolated App experiment; OFF is production-equivalent.
option(P34_EARLY_FAULT_VECTORS "Use reviewed early exception Flash vectors" OFF)
if(P34_EARLY_FAULT_VECTORS)
    target_compile_definitions(X_Track_App_GCC PRIVATE P34_EARLY_FAULT_VECTORS=1)
    target_sources(X_Track_App_GCC PRIVATE
        "${CMAKE_CURRENT_LIST_DIR}/../../USER/HAL/p34_early_fault.cpp")
    add_custom_command(OUTPUT "${APP_LINKER_SCRIPT}" APPEND
        DEPENDS "${CMAKE_CURRENT_LIST_DIR}/../../USER/HAL/p34_early_fault_policy.h")
endif()
'''
# Linker is preprocessed independently of the target, so the flag must also
# precede creation of APP_LINKER_SCRIPT's existing command.
LINK_FLAG = '''
option(P34_EARLY_FAULT_VECTORS "Use reviewed early exception Flash vectors" OFF)
set(P34_EARLY_LINKER_DEFINE)
if(P34_EARLY_FAULT_VECTORS)
    set(P34_EARLY_LINKER_DEFINE "-DP34_EARLY_FAULT_VECTORS=1")
endif()
'''
LINK_SECTION = '''
#if defined(P34_EARLY_FAULT_VECTORS)
  .p34_runtime_vectors ALIGN(1024) :
  {
    KEEP(*(.p34_runtime_vectors))
  } > FLASH
  ASSERT((ADDR(.p34_runtime_vectors) % 1024) == 0, "Runtime VTOR alignment")
  ASSERT(SIZEOF(.p34_runtime_vectors) == SIZEOF(.isr_vector), "Vector size mismatch")
  ASSERT(ADDR(.p34_runtime_vectors) >= ADDR(.fw_header) + SIZEOF(.fw_header), "Header overlap")
  ASSERT(ADDR(.p34_runtime_vectors) + SIZEOF(.p34_runtime_vectors) <= ORIGIN(FLASH) + LENGTH(FLASH), "Vector overflow")
#endif
'''
DIAG = '''
#if defined(P34_EARLY_FAULT_VECTORS)
#if !CONFIG_DEBUG_SERIAL_ENABLE || !CONFIG_DEBUG_RTT_ENABLE || CONFIG_HARDFAULT_AUTO_REBOOT || CONFIG_HARDFAULT_DUMP_DISPLAY
#error Unreviewed diagnostic configuration for early-vector experiment
#endif
extern "C" int p34_backtrace_ready(void);
extern "C" int p34_runtime_diagnostics_ready(void)
{
    return s_faultHandleReady && p34_backtrace_ready() &&
        (&CONFIG_DEBUG_SERIAL == &Serial5) && UART5->ctrl1_bit.uen &&
        UART5->ctrl1_bit.ten && _SEGGER_RTT.MaxNumUpBuffers > 0 &&
        _SEGGER_RTT.aUp[0].pBuffer != 0 && _SEGGER_RTT.aUp[0].SizeOfBuffer > 0 &&
        _SEGGER_RTT.aUp[0].Flags == SEGGER_RTT_MODE_NO_BLOCK_TRIM;
}
#endif
'''
BACKTRACE = '''
#if defined(P34_EARLY_FAULT_VECTORS)
#ifdef CMB_USING_OS_PLATFORM
#error OS-dependent backtrace is outside the reviewed experiment
#endif
int p34_backtrace_ready(void)
{
    return init_ok && main_stack_size != 0 && code_size != 0;
}
#endif
'''


def vector_body(text):
    pattern = r"(?ms)(^g_pfnVectors:\n)(.*?)(^__Vectors_End:)"
    matches = list(re.finditer(pattern, text))
    model.cli.require(len(matches) == 1, "unique vector list required")
    body = matches[0][2]
    entries = re.findall(r"(?m)^\s*\.word (\S+)\s*$", body)
    model.cli.require(len(entries) == 131 and entries[:2] == ["_estack", "Reset_Handler"], "vector geometry")
    model.cli.require(entries[3] == "HardFault_Handler" and all(entries[i] != "0" for i in SLOTS), "exception slots")
    model.cli.require(all(entries[i] == "0" for i in (7, 8, 9, 10, 13)), "reserved vectors")
    return matches[0], entries


def prepare(s):
    s.checked(AREA); model.cli.require(not AREA.exists(), "preserve experiment")
    old = s.read(BASE / "build/source.json")
    copies = []
    for r in old["files"]:
        p = Path(r["path"]); model.cli.require(model.cli.record(p) == r, "baseline drift")
        copies.append((p, s.checked(AREA / "f" / p.relative_to(BASE / "f"))))
    additions = ["USER/HAL/p34_early_fault.cpp", "USER/HAL/p34_early_fault_policy.h",
                 "MDK-ARM_F435/cmake-generated/cmake/sources/p34_vector_entries.inc"]
    for n in additions: s.checked(AREA / "f" / n)
    s.checked(AREA / "prepared.json")
    for p, dst in copies:
        dst.parent.mkdir(parents=True, exist_ok=True); shutil.copyfile(p, dst)
    f = AREA / "f"
    start = (f / START).read_text(encoding="utf-8")
    match, entries = vector_body(start)
    # Per-entry condition keeps one canonical list for both tables.
    inc = "".join(("#if defined(P34_PRIMARY_TABLE) && defined(P34_EARLY_FAULT_VECTORS)\n"
        "    .word p34_early_exception\n#else\n    .word " + e + "\n#endif\n")
        if i in SLOTS else "    .word " + e + "\n" for i, e in enumerate(entries))
    replacement = '#define P34_PRIMARY_TABLE 1\n#include "p34_vector_entries.inc"\n#undef P34_PRIMARY_TABLE\n'
    start = start[:match.start(2)] + replacement + start[match.end(2):]
    start += '''
#if defined(P34_EARLY_FAULT_VECTORS)
.section .p34_runtime_vectors,"a",%progbits
.balign 1024
.global p34_runtime_vectors
.type p34_runtime_vectors, %object
p34_runtime_vectors:
#include "p34_vector_entries.inc"
.size p34_runtime_vectors, .-p34_runtime_vectors
.section .text.p34_early_exception,"ax",%progbits
.global p34_early_exception
.type p34_early_exception, %function
.thumb_func
p34_early_exception:
    cpsid i
1:  b 1b
.size p34_early_exception, .-p34_early_exception
#endif
'''
    (f / START).write_text(start, encoding="utf-8", newline="\n")
    (f / START.parent / "p34_vector_entries.inc").write_text(inc, encoding="ascii")
    link = (f / LINK).read_text(encoding="utf-8")
    model.cli.require(link.count("  .text :") == 1, "linker anchor")
    (f / LINK).write_text(link.replace("  .text :", LINK_SECTION + "\n  .text :"), encoding="utf-8", newline="\n")
    cm = (f / CM).read_text(encoding="utf-8")
    anchor = 'add_custom_command(\n    OUTPUT "${APP_LINKER_SCRIPT}"'
    model.cli.require(cm.count(anchor) == 1, "App linker command anchor")
    cm = cm.replace(anchor, LINK_FLAG + "\n" + anchor)
    marker = '        "${APP_LINKER_SOURCE}"'
    model.cli.require(cm.count(marker) == 1, "App linker input anchor")
    cm = cm.replace(marker, '        ${P34_EARLY_LINKER_DEFINE}\n' + marker)
    (f / CM).write_text(cm + APPEND, encoding="utf-8", newline="\n")
    hal = f / "USER/HAL/HAL.cpp"; text = hal.read_text(encoding="utf-8")
    end = "    Timer_SetEnable(CONFIG_HAL_UPDATE_TIM, true);\n}"
    model.cli.require(text.count(end) == 1, "HAL final anchor")
    text = '#if defined(P34_EARLY_FAULT_VECTORS)\nextern "C" void p34_enable_runtime_vectors(void);\n#endif\n' + text
    text = text.replace(end, "    Timer_SetEnable(CONFIG_HAL_UPDATE_TIM, true);\n#if defined(P34_EARLY_FAULT_VECTORS)\n    p34_enable_runtime_vectors();\n#endif\n}")
    hal.write_text(text, encoding="utf-8", newline="\n")
    for relative, extra in [(FAULT, DIAG), (Path("Libraries/cm_backtrace/cm_backtrace.c"), BACKTRACE)]:
        p = f / relative; p.write_text(p.read_text(encoding="utf-8") + extra, encoding="utf-8", newline="\n")
    for name in ("p34_early_fault.cpp", "p34_early_fault_policy.h"):
        shutil.copyfile(ROOT / "Tools/ota" / name, f / "USER/HAL" / name)
    s.write(AREA / "prepared.json", dict(base=model.cli.record(BASE / "build/source.json"), entries=entries,
        sources=[model.cli.record(p) for p in sorted(f.rglob("*")) if p.is_file()],
        implementation=[model.cli.record(ROOT / "Tools/ota" / n) for n in
                        ("p34_early_fault.py", "p34_early_fault.cpp", "p34_early_fault_policy.h")], hardware=False))
    print("EARLY_SNAPSHOT_PREPARED", len(copies), "vector_entries", len(entries))


def build(s, mode):
    p = s.read(AREA / "prepared.json")
    for r in p["sources"] + p["implementation"]:
        model.cli.require(model.cli.record(r["path"]) == r, "prepared source drift")
    out = s.checked(AREA / mode); model.cli.require(not out.exists(), "preserve build")
    for n in ("result.json", "source.json") : s.checked(out / n)
    s.checked(out / "b"); s.checked(out / "install")
    for tag in ("configure", "build", "symbols", "disassembly", "extract", "attributes"):
        for suffix in (".log", ".json"): s.checked(out / (tag + suffix))
    s.checked(out / "elf.bin")
    env = model.host.environment(s, out)
    args = s.read(BASE / "build/configure.json")["command"]
    args = [x.replace(str(BASE / "f"), str(AREA / "f")).replace(str(BASE / "b"), str(out / "b"))
            .replace(str(BASE / "install"), str(out / "install")) for x in args]
    args.append("-DP34_EARLY_FAULT_VECTORS=" + ("ON" if mode == "on" else "OFF"))
    s.write(out / "source.json", dict(prepared=model.cli.record(AREA / "prepared.json")))
    model.host.command(s, out, "configure", args, env, 180)
    raw = model.host.command(s, out, "build", [args[0], "--build", out / "b", "--target", "X_Track_App_GCC", "--parallel", "6"], env, 900)
    elf = out / "b/app-gcc/X-Track-App-GCC.elf"; arm = tc.ARM / "bin"
    for tag, tool, flags in [("symbols", "nm", ["-n", "-S"]), ("disassembly", "objdump", ["-d"]),
                             ("attributes", "readelf", ["-h", "-S", "-A"])]:
        model.host.command(s, out, tag, [arm / ("arm-none-eabi-" + tool + ".exe"), *flags, elf], env, 60)
    model.host.command(s, out, "extract", [arm / "arm-none-eabi-objcopy.exe", "-O", "binary", elf, out / "elf.bin"], env, 60)
    binary = out / "b/app-gcc/X-Track-App-GCC.bin"
    model.cli.require(binary.read_bytes() == (out / "elf.bin").read_bytes(), "ELF binding")
    if mode == "off":
        model.cli.require(binary.read_bytes() == (BASE / "b/app-gcc/X-Track-App-GCC.bin").read_bytes(), "OFF binary changed")
        model.cli.require(b"p34_early_exception" not in (out / "symbols.log").read_bytes() and
                          b"p34_runtime_vectors" not in (out / "symbols.log").read_bytes(), "OFF leaked symbols")
    for r in p["sources"] + p["implementation"]:
        model.cli.require(model.cli.record(r["path"]) == r, "source changed during build")
    s.write(out / "result.json", dict(result="EARLY_APP_BUILT", mode=mode,
        artifacts=[model.cli.record(out / "b/app-gcc" / ("X-Track-App-GCC." + ext)) for ext in ("bin", "elf", "map", "hex")],
        warnings=len(re.findall(rb"warning:", raw)), errors=len(re.findall(rb"error:", raw)),
        hardware=False, measured_speedup=False, independent_acceptance=False))
    print("EARLY_APP_BUILT", mode, binary.stat().st_size)


if __name__ == "__main__":
    model.cli.require(Path.cwd() == ROOT and sys.flags.isolated and sys.flags.no_site and sys.dont_write_bytecode,
                      "isolated project root required")
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("mode", choices=("prepare", "off", "on"))
    mode = parser.parse_args().mode; store = model.cli.Store(ROOT)
    prepare(store) if mode == "prepare" else build(store, mode)
