"""Contained standard CMake builds and the P3-4 UART configuration regression."""
import argparse
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
import time

ROOT = Path(__file__).resolve().parents[3]


def load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


io = load("p34_host_io", ROOT / ".agents/skills/e-track-flutter-debug/scripts/host_io.py")
owned = load("p34_owned_commands", ROOT / "Tools/flutter/dev_checks.py")


def checked(path):
    return io.checked_output(ROOT, path)


def record(path):
    path = Path(path)
    return dict(path=str(path.relative_to(ROOT)), bytes=path.stat().st_size,
                sha256=hashlib.sha256(path.read_bytes()).hexdigest())


def environment(out):
    env = {key: value for key, value in os.environ.items()
           if not key.startswith(("GIT_", "PYTHON", "CCACHE_", "SCCACHE_"))}
    names = ("HOME", "USERPROFILE", "APPDATA", "LOCALAPPDATA", "TEMP", "TMP", "TMPDIR",
             "XDG_CACHE_HOME", "XDG_CONFIG_HOME", "XDG_DATA_HOME", "PYTHONUSERBASE",
             "CCACHE_DIR", "SCCACHE_DIR")
    paths = {name: checked(out / "host" / name.lower()) for name in names}
    for name, path in paths.items():
        path.mkdir(parents=True, exist_ok=True)
        env[name] = str(path)
    env.update(PYTHONDONTWRITEBYTECODE="1", PYTHONUTF8="1", PYTHONNOUSERSITE="1",
               SOURCE_DATE_EPOCH="1786320000", CCACHE_DISABLE="1", SCCACHE_DISABLE="1",
               GIT_OPTIONAL_LOCKS="0", GIT_CONFIG_NOSYSTEM="1", GIT_TERMINAL_PROMPT="0",
               GIT_CONFIG_GLOBAL=str(checked(out / "host/gitconfig")))
    return env


def run(out, env, label, argv, timeout):
    argv = list(map(str, argv))
    log = checked(out / (label + ".log"))
    receipt = checked(out / (label + ".json"))
    if log.exists() or receipt.exists():
        raise RuntimeError("preserve prior command outcome: " + label)
    print("P34_COMMAND " + label, flush=True)
    started = time.monotonic()
    value = dict(command=argv, cwd=str(ROOT), timeout_seconds=timeout,
                 exit=None, timed_out=False)
    if os.name != "nt":
        status = owned.run_command(ROOT, argv, ROOT, env, log, timeout)
        value.update(exit=status["exit_code"], timed_out=status["timed_out"], owner=status)
    else:
        job, process = owned.WindowsJob(), None
        try:
            with log.open("xb") as stream:
                process = subprocess.Popen([sys.executable, "-I", "-S", "-B", "-X", "utf8",
                    "-c", owned.WINDOWS_LAUNCHER], cwd=ROOT, env=env, stdin=subprocess.PIPE,
                    stdout=stream, stderr=subprocess.STDOUT, creationflags=subprocess.CREATE_NO_WINDOW)
                try:
                    job.assign(process)
                except Exception:
                    process.kill()
                    raise
                process.stdin.write((json.dumps(argv) + "\n").encode("ascii"))
                process.stdin.close()
                value["exit"] = process.wait(timeout=timeout)
        except subprocess.TimeoutExpired:
            value["timed_out"] = True
        finally:
            job.terminate()
            job.close()
            if process is not None:
                if process.stdin is not None and not process.stdin.closed:
                    process.stdin.close()
                process.wait(timeout=10)
                value["exit"] = process.returncode
    value.update(elapsed_seconds=round(time.monotonic() - started, 3), log=record(log))
    io.write_json(ROOT, receipt, value)
    if value["exit"] != 0 or value["timed_out"]:
        raise RuntimeError("command failed: " + label)
    return log.read_bytes()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("variant", choices=("candidate", "maintenance", "restore", "baud-test"))
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--toolchain", type=Path)
    parser.add_argument("--cmake", default="cmake")
    parser.add_argument("--ninja", default="ninja")
    parser.add_argument("--cc", default="gcc")
    parser.add_argument("--default-baud", type=int, choices=(115200, 230400, 460800, 921600), default=921600)
    args = parser.parse_args()
    if Path.cwd() != ROOT or not (sys.flags.isolated and sys.flags.no_site and sys.dont_write_bytecode):
        raise RuntimeError("run from the explicit worktree with Python -I -S -B")
    out = checked(args.out)
    if out.exists():
        raise RuntimeError("fresh project-local output required")
    for name in ("intent.json", "result.json", "failed.json", "b", "install", "baud-test.exe", "baud-test"):
        checked(out / name)
    for name in ("configure", "build", "size", "compile-baud", "test-baud"):
        checked(out / (name + ".log"))
        checked(out / (name + ".json"))
    env = environment(out)
    io.write_json(ROOT, out / "intent.json", dict(variant=args.variant,
        default_baud=args.default_baud, source=str(ROOT), device_operations=0, independent_acceptance=False))
    try:
        if args.variant == "baud-test":
            cc = shutil.which(args.cc, path=env.get("PATH"))
            if cc is None:
                raise RuntimeError("native C compiler unavailable")
            exe = out / ("baud-test.exe" if os.name == "nt" else "baud-test")
            run(out, env, "compile-baud", [cc, "-std=c99", "-O2", "-Wall", "-Wextra", "-Werror",
                "-I" + str(ROOT / "USER/HAL"), ROOT / "tests/ota/test_ota_uart_baud.c", "-o", exe], 90)
            log = run(out, env, "test-baud", [exe], 30)
            match = re.search(rb"UART_BAUD_CHECKS=(\d+) failures=0", log)
            if match is None or int(match[1]) != 405:
                raise RuntimeError("complete UART configuration regression missing")
            result = dict(result="UART_CONFIGURATION_REGRESSION_PASS", checks=int(match[1]))
        else:
            if args.toolchain is None or not args.toolchain.is_dir():
                raise RuntimeError("explicit installed ARM toolchain root required")
            suffix = ".exe" if os.name == "nt" else ""
            cmake = shutil.which(args.cmake, path=env.get("PATH"))
            ninja = shutil.which(args.ninja, path=env.get("PATH"))
            if cmake is None or ninja is None:
                raise RuntimeError("CMake and Ninja must already be installed")
            args.toolchain = args.toolchain.resolve(strict=True)
            flags = "-fmacro-prefix-map=" + ROOT.as_posix() + "=."
            command = [cmake, "-S", ROOT / "MDK-ARM_F435/cmake-generated", "-B", out / "b", "-G", "Ninja",
                "-DCMAKE_BUILD_TYPE=Release", "-DCMAKE_OBJECT_PATH_MAX=1024",
                "-DKEIL_GCC_COMPILER_CACHE:FILEPATH=", "-DARM_TOOLCHAIN_ROOT=" + str(args.toolchain),
                "-DCMAKE_MAKE_PROGRAM=" + ninja, "-DCMAKE_INSTALL_PREFIX=" + str(out / "install"),
                "-DCMAKE_C_FLAGS:STRING=" + flags, "-DCMAKE_CXX_FLAGS:STRING=" + flags,
                "-DP34_EARLY_FAULT_VECTORS=ON", "-DP34_OTA_UART_BAUD=" + str(args.default_baud),
                "-DP34_OTA_CANDIDATE=" + ("OFF" if args.variant == "maintenance" else "ON"),
                "-DP3_4_LINK_PROFILE=" + ("ON" if args.variant == "maintenance" else "OFF")]
            for language, compiler in (("C", "gcc"), ("CXX", "g++"), ("ASM", "gcc")):
                command.append("-DCMAKE_" + language + "_COMPILER=" +
                               str(args.toolchain / "bin" / ("arm-none-eabi-" + compiler + suffix)))
            if args.variant == "restore":
                command.append("-DCMAKE_PROJECT_INCLUDE=" + str(Path(__file__).parent / "restore/inject.cmake"))
            run(out, env, "configure", command, 180)
            log = run(out, env, "build", [cmake, "--build", out / "b", "--target", "X_Track_App_GCC", "--parallel", "8"], 900)
            run(out, env, "size", [args.toolchain / "bin" / ("arm-none-eabi-size" + suffix),
                                  out / "b/app-gcc/X-Track-App-GCC.elf"], 30)
            result = dict(result="APP_BUILT", variant=args.variant, default_baud=args.default_baud,
                artifacts=[record(out / "b/app-gcc" / ("X-Track-App-GCC." + ext)) for ext in ("elf", "hex", "bin", "map")],
                warnings=len(re.findall(rb"\bwarning:", log)), errors=len(re.findall(rb"\berror:", log)),
                boot_built=False, source_date_epoch=1786320000)
        result.update(installed=False, formal_freeze=False, independent_acceptance=False)
        io.write_json(ROOT, out / "result.json", result)
        print(json.dumps(result), flush=True)
    except Exception as error:
        io.write_json(ROOT, out / "failed.json", dict(error=str(error), preserve_outputs=True, device_operations=0))
        raise


if __name__ == "__main__":
    main()
