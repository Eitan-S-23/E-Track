"""Compile the actual serial IRQ and OTA parser against an AT32 register model."""
from __future__ import annotations

import argparse
import os
from pathlib import Path
import runpy
import shutil
import subprocess

ROOT = Path(__file__).resolve().parents[2]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--source-root", type=Path, default=ROOT)
    parser.add_argument("--metrics", action="store_true")
    args = parser.parse_args()
    guard = runpy.run_path(str(ROOT / ".agents/skills/e-track-flutter-debug/scripts/host_io.py"))["checked_output"]
    if Path.cwd().resolve() != ROOT:
        raise RuntimeError("explicit project-root cwd required")
    out = guard(ROOT, args.out)
    if out.exists():
        raise RuntimeError("fresh output directory required")
    for name in ("tmp", "home", "appdata", "localappdata", "compile.log", "run.log", "test.exe"):
        guard(ROOT, out / name)
    source = args.source_root.resolve(strict=True)
    compiler = shutil.which("g++") or shutil.which("clang++")
    if not compiler and os.name == "nt":
        compiler = str(Path("D:/install/mingw64/bin/g++.exe"))
    if not compiler or not Path(compiler).is_file():
        raise RuntimeError("host C++ compiler required")
    out.mkdir(parents=True)
    env = dict(os.environ)
    for key, leaf in dict(TEMP="tmp", TMP="tmp", TMPDIR="tmp", HOME="home", USERPROFILE="home",
                          APPDATA="appdata", LOCALAPPDATA="localappdata").items():
        path = guard(ROOT, out / leaf)
        path.mkdir(exist_ok=True)
        env[key] = str(path)
    env.update(CCACHE_DISABLE="1", SCCACHE_DISABLE="1", PYTHONDONTWRITEBYTECODE="1")
    env["PATH"] = str(Path(compiler).parent) + os.pathsep + env.get("PATH", "")
    binary = guard(ROOT, out / "test.exe")
    command = [compiler, "-std=c++11", "-Wall", "-Wextra", "-Werror", "-O2",
        *(["-DCONFIG_OTA_LINK_METRICS=1"] if args.metrics else []),
        "-I" + str(ROOT / "tests/ota/serial_stubs"),
        "-I" + str(source / "MDK-ARM_F435/Platform/Core"), "-I" + str(source / "Libraries"),
        str(ROOT / "tests/ota/test_hardware_serial.cpp"),
        str(source / "MDK-ARM_F435/Platform/Core/HardwareSerial.cpp"),
        str(source / "Libraries/OTA/ota_ble_frame.c"), "-o", str(binary)]
    options = dict(cwd=ROOT, env=env, capture_output=True, timeout=90)
    if os.name == "nt":
        options["creationflags"] = subprocess.CREATE_NO_WINDOW
    built = subprocess.run(command, **options)
    with (out / "compile.log").open("xb") as stream:
        stream.write(built.stdout + built.stderr)
    print((built.stdout + built.stderr).decode("utf-8", "replace"), end="")
    if built.returncode:
        return built.returncode
    ran = subprocess.run([str(binary)], **options)
    with (out / "run.log").open("xb") as stream:
        stream.write(ran.stdout + ran.stderr)
    print((ran.stdout + ran.stderr).decode("utf-8", "replace"), end="")
    return ran.returncode


if __name__ == "__main__":
    raise SystemExit(main())
