"""Exercise the actual generated GCC linker script, without touching hardware."""
import importlib.util
from pathlib import Path
import sys

SELF = Path(__file__).resolve()
spec = importlib.util.spec_from_file_location("heap_guard_setup", SELF.with_name("baud_memory_fix.py"))
m = importlib.util.module_from_spec(spec)
spec.loader.exec_module(m)


def main():
    r = m.configure()
    b = r.b
    b.require(Path.cwd().resolve() == b.ROOT and sys.flags.isolated and sys.flags.no_site and sys.dont_write_bytecode,
              "isolated explicit root required")
    out = b.checked(m.OUT / "heap-guard-tests")
    script = m.OUT / "build/app-gcc/x-track-app-gcc.ld"
    fixture = SELF.with_name("heap_guard_fixture.c")
    compiler = Path(r"D:\singlechip\gcc+gdb+openocd\tools\arm-gnu-toolchain-13.3.rel1-ming\bin\arm-none-eabi-gcc.exe")
    cases = (("enough", 0x53000, 4096, 0), ("too-small", 0x55800, 4096, 1), ("default-off", 0x55800, None, 0))
    b.require(script.is_file() and not out.exists(), "generated script and fresh test output required")
    for name, _, _, _ in cases:
        for suffix in (".elf", ".map", ".log"):
            b.checked(out / (name + suffix))
    b.checked(out / "result.json")
    out.mkdir(parents=True)
    results = []
    for name, size, minimum, expected in cases:
        args = [str(compiler), "-std=c99", "-Wall", "-Wextra", "-Werror", "-Os", "-mthumb", "-mcpu=cortex-m4",
                "-ffreestanding", "-nostdlib", "-Wl,--gc-sections", "-DTEST_RAM_BYTES=" + str(size),
                "-I" + str(m.OUT / "fw/Libraries/OTA"), "-T" + str(script), str(fixture),
                "-Wl,-Map=" + str(out / (name + ".map")), "-o", str(out / (name + ".elf"))]
        if minimum is not None:
            args.append("-Wl,--defsym=__p34_heap_min=" + str(minimum))
        result = b.command(args, cwd=out, timeout=60, check=False)
        raw = result.stdout + result.stderr
        log = r.raw(out / (name + ".log"), raw)
        passed = result.returncode == expected and (expected == 0 or
                 b"P34: insufficient system heap for diagnostic runtime" in raw)
        results.append(dict(name=name, passed=passed, exit=result.returncode, expected_exit=expected, log=log))
        print(name, result.returncode, raw.decode("utf-8", "replace"), flush=True)
    r.save(out / "result.json", dict(passed=all(x["passed"] for x in results), cases=results,
           linker_script=b.record(script), fixture=b.record(fixture), source=b.record(SELF), hardware_contacted=False))
    b.require(all(x["passed"] for x in results), "real linker regression failed")


if __name__ == "__main__":
    main()
