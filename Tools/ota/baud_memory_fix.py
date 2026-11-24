"""Isolated memory-budget repair, reusing the admitted single-App baud tooling."""
from __future__ import annotations

import argparse
import importlib.util
import io
import json
import os
from pathlib import Path
import re
import struct
import sys
import time
import types
import unittest

ROOT = Path(__file__).resolve().parents[2]
SELF = Path(__file__).resolve()
OUT = ROOT / ".cache/p34m"
PREVIOUS = ROOT / ".cache/p34b"
CHANGES = ("USER/HAL/HAL_SD_CARD.cpp", "USER/main.cpp", "Simulator/LVGL.Simulator/lv_conf.h",
           "cmake/linker/x-track-app-gcc.ld.S", "MDK-ARM_F435/cmake-generated/CMakeLists.txt")


def load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


def map_section(text, section, size=None, owner=None):
    matches = re.findall(r"^\s*" + re.escape(section) +
                         r"\s+(0x[0-9a-fA-F]+)\s+(0x[0-9a-fA-F]+)([^\n]*)$", text, re.M)
    found = [(int(a, 16), int(n, 16)) for a, n, file in matches
             if int(a, 16) >= 0x20000000 and (owner is None or owner in file)]
    if len(found) != 1 or (size is not None and found[0][1] != size):
        raise RuntimeError("ambiguous/missing map allocation: " + section)
    return found[0]


def heap_evidence(raw):
    samples, base, limit = raw["samples"], raw["heap_base"], raw["heap_limit"]
    if not (raw["reader_closed"] and len(samples) == 12 and base < limit and
            all(0 <= x["lvgl_used"] <= x["lvgl_peak"] <= 128*1024 and
                base <= x["system_break"] <= limit for x in samples)):
        raise RuntimeError("invalid original heap samples")
    return dict(result="BASELINE_HEAPS_PROFILED", max_lvgl_peak=max(x["lvgl_peak"] for x in samples),
                system_used=max(x["system_break"]-base for x in samples), capacity=limit-base,
                counter_caveat="LVGL requested-size counters may clamp to zero; not actual TLSF live/free usage",
                requires_new_firmware_tlsf_monitor=True, reader_closed=True)


def memory_report(line):
    match = re.fullmatch(r"P34MEM: sysCapacity=(\d+) sysUsed=(\d+) lvPool=(\d+) lvFree=(\d+) lvLargest=(\d+)", line.strip())
    if match is None:
        raise RuntimeError("missing or malformed actual startup memory report")
    capacity, used, pool, free, largest = map(int, match.groups())
    if not (capacity >= 4096 and 0 <= used <= capacity-512 and pool == 124*1024 and
            16384 <= free <= pool and 4096 <= largest <= free):
        raise RuntimeError("startup memory report lacks diagnostic runtime headroom")
    return dict(system_capacity=capacity, system_used=used, lvgl_pool=pool, lvgl_free=free, lvgl_largest=largest)


def configure():
    r = load("memory_fix_runtime", SELF.with_name("baud_runtime.py"))
    b, a = r.b, r.a
    for common in (b, a.b):
        common.OUT = OUT
        common.host.OUT = OUT
    a.FW, a.OUT, a.RAW = OUT / "fw", OUT / "assets", OUT / "build/app-gcc/X-Track-App-GCC.bin"
    r.RUNTIME = OUT / "runtime"
    r.PHONE, r.NETWORK = r.RUNTIME / "phone-r1", r.RUNTIME / "network-r1"
    original_load, original_sources = r.load, r.sources

    def load_bound(name, path):
        module = original_load(name, path)
        filename = Path(path).name
        if filename in ("baud_tune.py", "baud_restore.py"):
            module.m, module.b = r.m, b
            if filename == "baud_restore.py":
                module.a, module.OUT = a, OUT / "recovery"
        return module

    r.load = load_bound
    r.sources = lambda: sorted(original_sources() + [b.record(SELF), b.record(SELF.with_name("test_baud_memory_fix.py")),
                               b.record(SELF.with_name("test_baud_heap_guard.py")), b.record(SELF.with_name("heap_guard_fixture.c"))] +
                               [b.record(a.FW / path) for path in CHANGES], key=lambda x: x["path"])

    original_reader = r.m.ImageReader

    class ResetAwareReader(original_reader):
        def select(self, prefix):
            known = any(bytes.fromhex(p["prefix"]) == prefix for p in self.profiles.values())
            if not known and not self.in_app():
                raise r.m.passive.Transition("reset during executable-header read")
            return super().select(prefix)

    r.m.ImageReader = ResetAwareReader
    original_advance = r.advance

    def advance(previous):
        reports = []
        for path in sorted((r.cell(previous) / "mcu").glob("app-epoch-*.raw")):
            for line in path.read_text(encoding="ascii", errors="replace").splitlines():
                if line.startswith("P34MEM:"):
                    reports.append(memory_report(line))
        b.require(reports, "actual startup memory qualification is missing; no next baud cell")
        return original_advance(previous)

    r.advance = advance

    def launch(name, mode, seconds, run=None):
        return r.supervisor.owned.launch(r.RUNTIME / name, SELF,
                                        [mode] + (["--run", run] if run else []), seconds)

    r.launch_worker = launch
    return r


def heap_probe(r):
    b, m, c = r.b, r.m, r.m.c
    b.require(r.supervisor.owned.in_job(), "owned bounded heap probe required")
    previous = r.read(PREVIOUS / "runs/bootstrap-trace/failure/readback/result.json")
    closed = r.read(PREVIOUS / "runtime/readback-bootstrap-trace-r1/closed.json")
    b.require(previous["result"] == "BASELINE_RETAINED_BOOT_AND_SLOTS_VERIFIED" and previous["reader_closed"] and
              closed["worker_exit"] == 0 and not closed["forced_termination"], "prior reader not reconciled")
    m.native_authority()
    profile = r.read(PREVIOUS / "mcu-bindings.json")["profiles"]["30207"]
    b.require(b.record(profile["map"]["path"]) == profile["map"], "baseline map changed")
    text = Path(profile["map"]["path"]).read_text(encoding="utf-8")
    addresses = dict(lvgl_peak=map_section(text, ".bss.max_used", 4)[0],
                     lvgl_used=map_section(text, ".bss.cur_used", 4)[0],
                     system_break=map_section(text, ".data.current.0", 4, "gcc_runtime_compat")[0])
    heap_base = map_section(text, "._user_heap_stack")[0]
    heap_limit = map_section(text, ".ota_stack_guard", 32)[0]
    out = b.checked(OUT / "heap-probe")
    e = c.Evidence(out)
    link = m.BoundLink(e, writable=False)
    result = dict(started=b.now(), source=b.record(SELF), result="NOT_PROFILED", writes=0, reset=0,
                  heap_base=heap_base, heap_limit=heap_limit, capacity=heap_limit-heap_base,
                  native_history_before=c.record(c.MRU), samples=[])
    try:
        link.connect()
        for _ in range(12):
            link.running()
            b.require(link.read(c.APP, 0x460) == bytes.fromhex(profile["prefix"]), "baseline changed")
            sample = dict(time=b.now())
            for name, address in addresses.items():
                link.ram_reads.append((address, address+4))
                sample[name] = m.u32(link.read(address, 4))
            link.running()
            result["samples"].append(sample)
            time.sleep(.5)
        b.require(all(0 <= x["lvgl_used"] <= x["lvgl_peak"] <= 128*1024 and
                      heap_base <= x["system_break"] <= heap_limit for x in result["samples"]), "invalid allocator snapshot")
        result.update(result="BASELINE_HEAPS_PROFILED", max_lvgl_peak=max(x["lvgl_peak"] for x in result["samples"]))
    except Exception as error:
        result["error"] = type(error).__name__ + ": " + str(error)
    finally:
        link.close()
        result.update(ended=b.now(), reader_closed=not link.opened, native_history_after=c.record(c.MRU))
        e.save("result.json", result)
        e.events.close()
        e.ledger.close()
    print(json.dumps(result), flush=True)
    return 0 if result["result"] == "BASELINE_HEAPS_PROFILED" else 1


def build(r):
    b, fw, directory = r.b, r.a.FW, OUT / "build"
    b.require(not (OUT / "firmware-build-001.json").exists(), "preserve first repair build")
    heap = r.read(OUT / "heap-profile.json")
    b.require(heap["result"] == "BASELINE_HEAPS_PROFILED" and heap["reader_closed"] and
              heap["max_lvgl_peak"] < 120*1024, "no measured margin for diagnostic-only LVGL pool rebalance")
    cmake = r"C:\Program Files\CMake\bin\cmake.exe"
    toolchain = Path(r"D:\singlechip\gcc+gdb+openocd\tools\arm-gnu-toolchain-13.3.rel1-ming")
    for p in (directory, OUT / "firmware-build-001.json", OUT / "firmware-build-001.configure.log", OUT / "firmware-build-001.build.log"):
        b.checked(p)
    args = [cmake, "-S", str(fw / "MDK-ARM_F435/cmake-generated"), "-B", str(directory), "-G", "Ninja",
            "-DCMAKE_BUILD_TYPE=Release", "-DCMAKE_OBJECT_PATH_MAX=1024", "-DP3_4_LINK_PROFILE=ON",
            "-DKEIL_GCC_COMPILER_CACHE:FILEPATH=", "-DARM_TOOLCHAIN_ROOT=" + str(toolchain),
            "-DCMAKE_MAKE_PROGRAM=D:/singlechip/gcc+gdb+openocd/tools/ninja-win/ninja.exe"]
    for language, compiler in (("C", "gcc"), ("CXX", "g++"), ("ASM", "gcc")):
        args.append("-DCMAKE_" + language + "_COMPILER=" + str(toolchain / "bin" / ("arm-none-eabi-" + compiler + ".exe")))
    env = dict(SOURCE_DATE_EPOCH="1786320000", CCACHE_DISABLE="1", SCCACHE_DISABLE="1")
    configured = b.command(args, cwd=fw, extra_env=env, timeout=180, check=False)
    config = r.raw(OUT / "firmware-build-001.configure.log", configured.stdout + configured.stderr)
    b.require(configured.returncode == 0, "repair configure failed")
    built = b.command([cmake, "--build", str(directory), "--target", "X_Track_App_GCC", "X_Track_Boot", "--parallel", "8"],
                      cwd=fw, extra_env=env, timeout=1200, check=False)
    raw = built.stdout + built.stderr
    log = r.raw(OUT / "firmware-build-001.build.log", raw)
    text = raw.decode("utf-8", "replace")
    paths = list(CHANGES) + ["USER/HAL/HAL_Bluetooth.cpp", "USER/HAL/BtBaudExperiment/p34_link_profile.h",
                            "MDK-ARM_F435/Platform/Core/HardwareSerial.cpp", "MDK-ARM_F435/Platform/Core/HardwareSerial.h"]
    r.save(OUT / "firmware-build-001.json", dict(time=b.now(), passed=built.returncode == 0, exit=built.returncode,
           configure=config, log=log, warnings=len(re.findall(r"\bwarning:", text)), errors=len(re.findall(r"\berror:", text)),
           scope="GCC App and Boot rebuild after shared header change; no Boot flash or release",
           modified_sources=[b.record(fw / path) for path in paths],
           artifacts=[b.record(p) for folder in ("app-gcc", "boot") for p in sorted((directory / folder).glob("X-Track-*.*")) if p.is_file()],
           hardware_contacted=False))
    print(text[-5000:], flush=True)
    b.require(built.returncode == 0, "repair build failed; retain original log")


def host_tests(r):
    b = r.b
    for name, dirname in (("test_baud_mcu", "host-tests-mcu-002"), ("test_baud_runtime", "host-tests-runtime-002")):
        module = load("memory_fix_" + name, SELF.with_name(name + ".py"))
        module.OUT = b.checked(OUT / dirname)
        b.require(not module.OUT.exists(), "preserve host tests")
        b.checked(module.OUT / "result.json")
        module.OUT.mkdir(parents=True)
        for key, value in list(vars(module).items()):
            if not isinstance(value, types.ModuleType):
                continue
            filename = Path(getattr(value, "__file__", "")).name
            if filename == "baud_runtime.py":
                setattr(module, key, r)
            elif filename == "baud_mcu.py":
                setattr(module, key, r.m)
            elif filename in ("baud_tune.py", "baud_restore.py"):
                setattr(module, key, r.load("memory_fix_" + key, SELF.with_name(filename)))
        stream = io.StringIO()
        result = unittest.TextTestRunner(stream=stream, verbosity=2).run(unittest.defaultTestLoader.loadTestsFromModule(module))
        r.save(module.OUT / "result.json", dict(passed=result.wasSuccessful(), tests=result.testsRun,
               failures=len(result.failures), errors=len(result.errors), output=stream.getvalue(),
               tested_source=b.record(Path(r.m.__file__)), sources=r.sources(), test_source=b.record(module.__file__), hardware=False))
        print(stream.getvalue(), flush=True)
        b.require(result.wasSuccessful(), "repair host tests failed")
    r.hostcheck()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("mode", choices=("launch-heap", "heap-worker", "heap-analysis", "build", "assets", "maps", "recovery", "host-tests",
                                        "plan", "open", "start", "network-worker", "phone-worker", "capture-worker",
                                        "coordinate", "advance", "advance-worker", "status", "close"))
    parser.add_argument("--run", default="bootstrap")
    args = parser.parse_args()
    r = configure()
    b = r.b
    b.require(Path.cwd().resolve() == ROOT and sys.flags.isolated and sys.flags.no_site and sys.dont_write_bytecode,
              "isolated explicit project root required")
    os.environ.update(r.environment())
    if args.mode == "launch-heap":
        print(r.supervisor.owned.launch(r.RUNTIME / "heap-probe", SELF, ["heap-worker"], 90), flush=True)
    elif args.mode == "heap-worker":
        cycle = r.load("heap_device_lock", SELF.with_name("repeat_cycle.py"))
        with cycle.device_lock():
            raise SystemExit(heap_probe(r))
    elif args.mode == "heap-analysis":
        raw = r.read(OUT / "heap-probe/result.json")
        b.require(b.record(OUT / "heap-probe/driver-v1.py")["sha256"] == raw["source"]["sha256"], "original probe source missing")
        value = heap_evidence(raw)
        value.update(original=b.record(OUT / "heap-probe/result.json"), validator=b.record(SELF),
                     explanation="Preserve original host rejection; zero is valid in lv_mem.c's clamped cur_used counter. No device rerun.")
        r.save(OUT / "heap-profile.json", value)
        print(json.dumps(value), flush=True)
    elif args.mode == "build":
        build(r)
    elif args.mode == "assets":
        r.a.main()
    elif args.mode == "maps":
        r.m.prepare()
    elif args.mode == "recovery":
        r.load("memory_restore", SELF.with_name("baud_restore.py")).prepare()
    elif args.mode == "host-tests":
        host_tests(r)
    elif args.mode == "plan":
        guard = r.read(OUT / "heap-guard-tests/result.json")
        b.require(guard["passed"] and guard["linker_script"] == b.record(OUT / "build/app-gcc/x-track-app-gcc.ld") and
                  guard["source"] == b.record(SELF.with_name("test_baud_heap_guard.py")) and
                  guard["fixture"] == b.record(SELF.with_name("heap_guard_fixture.c")), "real linker guard tests missing/stale")
        r.prepare()
    else:
        r.authority()
        if args.mode == "open":
            r.open_runtime()
        elif args.mode == "start":
            r.start(args.run, 115200, "bootstrap")
        elif args.mode == "network-worker":
            r.network_worker()
        elif args.mode == "phone-worker":
            r.phone().server()
        elif args.mode == "capture-worker":
            cycle = r.load("memory_device_lock", SELF.with_name("repeat_cycle.py"))
            with cycle.device_lock():
                raise SystemExit(r.m.capture(args.run))
        elif args.mode == "coordinate":
            r.coordinate(args.run)
        elif args.mode == "advance":
            r.launch_worker("advance-" + args.run, "advance-worker", 1800, args.run)
        elif args.mode == "advance-worker":
            r.advance(args.run)
        elif args.mode == "status":
            for path in (r.cell(args.run) / "status.json", r.cell(args.run) / "mcu/state.json"):
                if path.exists():
                    print(path, json.dumps(r.read(path)), flush=True)
        else:
            for path in (r.PHONE, r.NETWORK):
                if path.exists() and not (path / "closed.json").exists():
                    r.save(path / "stop.json", dict(time=b.now(), reason="close owned repair runtime"))


if __name__ == "__main__":
    main()
