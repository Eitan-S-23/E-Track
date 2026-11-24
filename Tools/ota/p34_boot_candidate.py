"""Contained Boot candidate builds and host checks; never operates hardware."""
import hashlib
import json
import os
from pathlib import Path
import re
import runpy
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / ".cache/p34-boot/preparation"
IO = runpy.run_path(str(ROOT / ".agents/skills/e-track-flutter-debug/scripts/host_io.py"))
OLD = ROOT / ".cache/p34q/irqscreen/triage/boot-fix/run-002"
BACKUP = ROOT / ".cache/p34-rolling28/session-w28/mcu/final-boot.bin"
BOOT_SHA = "55200bb8b9399b5b2fa3e9b9d02d0504bec066f7624d0f293d82cb4244505f62"
ARM = Path(r"D:\singlechip\gcc+gdb+openocd\tools\arm-gnu-toolchain-13.3.rel1-ming")
CMAKE = r"C:\Program Files\CMake\bin\cmake.exe"
NINJA = r"D:\singlechip\gcc+gdb+openocd\tools\ninja-win\ninja.exe"


def checked(path):
    return IO["checked_output"](ROOT, path)


def record(path):
    data = Path(path).read_bytes()
    return dict(path=str(path), bytes=len(data), sha256=hashlib.sha256(data).hexdigest())


def main():
    if Path.cwd() != ROOT or not (sys.flags.isolated and sys.flags.no_site and sys.dont_write_bytecode):
        raise RuntimeError("isolated project-root execution required")
    checked(OUT)
    if OUT.exists():
        raise RuntimeError("preserve previous preparation")
    whole = BACKUP.read_bytes()
    if len(whole) != 65536 or hashlib.sha256(whole).hexdigest() != BOOT_SHA:
        raise RuntimeError("original whole Boot backup mismatch")
    env = dict(os.environ)
    leaves = dict(HOME="home", USERPROFILE="home", APPDATA="roaming", LOCALAPPDATA="local",
        TEMP="tmp", TMP="tmp", TMPDIR="tmp", XDG_CACHE_HOME="cache", XDG_CONFIG_HOME="config",
        CCACHE_DIR="ccache", SCCACHE_DIR="sccache")
    for key, leaf in leaves.items():
        path = checked(OUT / "host" / leaf)
        path.mkdir(parents=True, exist_ok=True)
        env[key] = str(path)
    env.update(SOURCE_DATE_EPOCH="1786320000", PYTHONDONTWRITEBYTECODE="1", CCACHE_DISABLE="1",
               SCCACHE_DISABLE="1", GIT_OPTIONAL_LOCKS="0")
    env["PATH"] = str(ARM / "bin") + os.pathsep + r"D:\install\mingw64\bin" + os.pathsep + env["PATH"]
    for key in ("GCC_EXEC_PREFIX", "COMPILER_PATH", "LIBRARY_PATH", "CPATH", "C_INCLUDE_PATH", "CPLUS_INCLUDE_PATH"):
        env.pop(key, None)
    recovery = checked(OUT / "original-whole-boot.bin")
    with recovery.open("xb") as stream:
        stream.write(whole)
    result = dict(boot_only=True, hardware=False, backup=record(recovery), actions=[], passed=False)

    def run(name, command, expected=0):
        log = checked(OUT / (name + ".log"))
        p = subprocess.run(command, cwd=ROOT, env=env, capture_output=True, timeout=240,
                           creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
        data = p.stdout + b"\nSTDERR\n" + p.stderr
        with log.open("xb") as stream:
            stream.write(data)
        text = data.decode("utf-8", "replace")
        result["actions"].append(dict(name=name, command=command, exit=p.returncode,
            warnings=len(re.findall(r"\bwarning:", text)), errors=len(re.findall(r"\berror:", text)), log=record(log)))
        print(name, p.returncode, text[-1000:], flush=True)
        if p.returncode != expected:
            raise RuntimeError("failed step: " + name)

    try:
        sources = [ROOT / p for p in ("tests/boot/test_boot_state_machine.c", "boot/src/boot_state_machine.c",
            "boot/src/boot_fw_header.c", "boot/src/boot_slot.c", "boot/src/boot_crc32.c",
            "boot/src/boot_sha256.c", "Libraries/EEPROM/eeprom_bcb.c")]
        for mode in ("default", "candidate"):
            exe = checked(OUT / ("host-state-" + mode + ".exe"))
            defines = ["-DP34_BOOT_SKIP_IDENTICAL_BLOCKS=1"] if mode == "candidate" else []
            run("compile-state-" + mode, [r"D:\install\mingw64\bin\gcc.exe", "-std=c99", "-O2",
                "-Wall", "-Wextra", "-Werror", *defines, "-I" + str(ROOT / "boot/include"),
                "-I" + str(ROOT / "Libraries"), *map(str, sources), "-o", str(exe)])
            run("state-" + mode, [str(exe)])
        for name, script in (("qspi", "test_boot_qspi_clock.py"), ("protocols", "test_boot_protocols.py")):
            exe = checked(OUT / ("host-" + name + ".exe"))
            checked(exe.with_suffix(".c"))
            code = "import runpy;from pathlib import Path;runpy.run_path(" + repr(str(ROOT / "tests/boot" / script)) + ")[\"compile_test\"](Path(" + repr(str(exe)) + "))"
            run("compile-" + name, [sys.executable, "-I", "-S", "-B", "-X", "utf8", "-c", code])
            run(name, [str(exe)])
        for mode in ("default", "candidate"):
            build = checked(OUT / mode)
            install = checked(OUT / ("install-" + mode))
            run("configure-" + mode, [CMAKE, "-S", str(ROOT / "MDK-ARM_F435/cmake-generated"),
                "-B", str(build), "-G", "Ninja", "-DCMAKE_BUILD_TYPE=Release", "-DCMAKE_OBJECT_PATH_MAX=1024",
                "-DCMAKE_MAKE_PROGRAM=" + NINJA, "-DARM_TOOLCHAIN_ROOT=" + str(ARM),
                "-DKEIL_GCC_COMPILER_CACHE=OFF", "-DCMAKE_INSTALL_PREFIX=" + str(install),
                "-DP34_BOOT_SKIP_IDENTICAL_BLOCKS=" + ("ON" if mode == "candidate" else "OFF")])
            run("build-" + mode, [CMAKE, "--build", str(build), "--target", "X_Track_Boot", "--parallel", "4"])
            run("artifact-" + mode, [sys.executable, "-I", "-S", "-B", "-X", "utf8",
                str(ROOT / "tests/boot/validate_boot_artifact.py"), "--build-dir", str(build)])
            result[mode] = [record(build / "boot" / ("X-Track-Boot." + ext)) for ext in ("bin", "hex", "elf", "map")]
        old = OLD / "build/boot/X-Track-Boot.bin"
        current = OUT / "default/boot/X-Track-Boot.bin"
        result["default_byte_identical"] = old.read_bytes() == current.read_bytes()
        if not result["default_byte_identical"]:
            raise RuntimeError("default Boot binary differs from installed baseline")
        result["sources"] = [record(p) for p in sources] + [record(Path(__file__)),
            record(ROOT / "MDK-ARM_F435/cmake-generated/CMakeLists.txt")]
        result["passed"] = True
    except Exception as error:
        result["error"] = type(error).__name__ + ": " + str(error)
    IO["write_json"](ROOT, checked(OUT / "result.json"), result)
    return 0 if result["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
