"""Prepare/build one N04 App from the immutable, measured N03 source lineage.

Host-only. This does not finalize packages, reserve versions, or touch devices.
Existing source/build evidence is never replaced by a second invocation.
"""
from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import json
import os
from pathlib import Path
import re
import runpy
import shutil
import subprocess
import sys
import time

ROOT = Path(__file__).resolve().parents[2]
BASE = ROOT / ".cache/p34-next/n03/fw"
AREA = ROOT / ".cache/p34-session/n04/firmware"
FW = ROOT / ".cache/p34-session/n04/fw"
BUILD = ROOT / ".cache/p34-session/n04/b"
OVERLAY = ("Libraries/W25Q128/qspi_cmd_en25qh128a.cpp",
           "Libraries/W25Q128/qspi_cmd_en25qh128a.h", "USER/HAL/HAL_OTA_Package.cpp")
IO = runpy.run_path(str(ROOT / ".agents/skills/e-track-flutter-debug/scripts/host_io.py"))
CMAKE = Path("C:/Program Files/CMake/bin/cmake.exe")
ARM = Path("D:/singlechip/gcc+gdb+openocd/tools/arm-gnu-toolchain-13.3.rel1-ming")
NINJA = Path("D:/singlechip/gcc+gdb+openocd/tools/ninja-win/ninja.exe")


def require(value, message):
    if not value:
        raise RuntimeError(message)


def checked(path):
    return IO["checked_output"](ROOT, path)


def record(path):
    path = Path(path)
    data = path.read_bytes()
    return dict(path=str(path), bytes=len(data), sha256=hashlib.sha256(data).hexdigest())


def read(path):
    return json.loads(Path(path).read_text(encoding="utf-8"))


def save(path, value):
    return IO["write_json"](ROOT, checked(path), value)


def unchanged(items):
    for item in items:
        require(record(checked(item["path"])) == item, "bound input changed: " + item["path"])


def environment():
    paths = {name: checked(AREA / "host" / folder) for name, folder in {
        "HOME": "home", "USERPROFILE": "home", "APPDATA": "appdata", "LOCALAPPDATA": "localappdata",
        "TEMP": "tmp", "TMP": "tmp", "TMPDIR": "tmp", "XDG_CONFIG_HOME": "config",
        "XDG_CACHE_HOME": "cache", "XDG_DATA_HOME": "data", "XDG_STATE_HOME": "state",
        "PYTHONUSERBASE": "python", "PYTHONPYCACHEPREFIX": "pycache",
        "CCACHE_DIR": "ccache", "SCCACHE_DIR": "sccache"}.items()}
    env = dict(os.environ)
    for name, path in paths.items():
        path.mkdir(parents=True, exist_ok=True)
        env[name] = str(path)
    env.update(SOURCE_DATE_EPOCH="1786320000", CCACHE_DISABLE="1", SCCACHE_DISABLE="1",
               PYTHONDONTWRITEBYTECODE="1", GIT_OPTIONAL_LOCKS="0")
    return env, {name: str(path) for name, path in paths.items()}


def run(tag, args, cwd, env, timeout):
    paths = [checked(AREA / "logs" / (tag + suffix)) for suffix in (".stdout", ".stderr", ".json")]
    require(not any(path.exists() for path in paths), "preserve original command: " + tag)
    paths[0].parent.mkdir(parents=True, exist_ok=True)
    started = time.monotonic()
    timed_out = False
    try:
        result = subprocess.run(list(map(str, args)), cwd=checked(cwd), env=env,
            stdin=subprocess.DEVNULL, capture_output=True, timeout=timeout,
            creationflags=subprocess.CREATE_NO_WINDOW)
        stdout, stderr, code = result.stdout, result.stderr, result.returncode
    except subprocess.TimeoutExpired as error:
        stdout, stderr, code = error.stdout or b"", error.stderr or b"", None
        timed_out = True
    for path, data in zip(paths, (stdout, stderr)):
        with path.open("xb") as stream:
            stream.write(data)
    save(paths[2], dict(args=list(map(str, args)), cwd=str(cwd), exit=code, timeout=timed_out,
                       seconds=time.monotonic() - started, stdout=record(paths[0]), stderr=record(paths[1])))
    print("N04_HOST_STEP", tag, "exit", code, flush=True)
    require(code == 0 and not timed_out, "host command failed: " + tag)
    return stdout + stderr


def verify_tests(path):
    path = checked(path)
    value = read(path)
    require(value["result"] == "HOST_MODEL_PASS" and value["tests"] == 10 and
            value["failures"] == value["errors"] == value["skipped"] == 0 and
            value["inputs_unchanged"] and value["hardware"] is False, "current N04 host tests required")
    unchanged(value["inputs"])
    required = {(0, 0), (0, 1), (1, 0), (1, 1)}
    require({(item["optimize"], item["profile"]) for item in value["native"]} == required,
            "all optimization/profile combinations must have run")
    require(any(item["status_pairs"] == 65536 for item in value["native"]), "exhaustive status test missing")
    unchanged([item[key] for item in value["native"] for key in ("fixture", "executable")])
    unchanged(value["commands"] + [value["log"]])
    return record(path)


def verify_source():
    source = read(AREA / "source.json")
    require(source["overlay_names"] == list(OVERLAY) and source["base"] == str(BASE) and
            source["fw"] == str(FW) and source["build"] == str(BUILD), "candidate source scope differs")
    unchanged(source["inputs"] + source["base_files"] + source["candidate_files"])
    return source


def frozen_lineage(files):
    anchor = read(ROOT / ".cache/p34-next/n03/source-preparation.json")
    parent = Path(anchor["delta"]["base"])
    expected = {Path(item["path"]).relative_to(parent).as_posix(): item for item in anchor["originals"]}
    overlays = {item["relative"]: item["candidate"] for item in anchor["overlay"]}
    require(set(expected) == {path.relative_to(BASE).as_posix() for path in files},
            "N03 lineage file set differs from its original preparation")
    for path in files:
        name = path.relative_to(BASE).as_posix()
        data = path.read_bytes()
        if name in overlays:
            require(hashlib.sha256(data.replace(b"\r\n", b"\n")).hexdigest() == overlays[name],
                    "N03 original overlay changed: " + name)
        else:
            require((len(data), hashlib.sha256(data).hexdigest()) ==
                    (expected[name]["bytes"], expected[name]["sha256"]),
                    "N03 original inherited file changed: " + name)


def prepare(tests):
    for path in (AREA, FW, BUILD):
        checked(path)
        require(not path.exists(), "preserve existing N04 preparation/build: " + str(path))
    test = verify_tests(tests)
    base_files = sorted(path for path in BASE.rglob("*") if path.is_file())
    require(base_files and all((BASE / name).is_file() for name in OVERLAY), "N03 source lineage incomplete")
    frozen_lineage(base_files)
    for path in base_files:
        checked(path)
        checked(FW / path.relative_to(BASE))
    for name in ("intent.json", "source.json", "failed-prepare.json", "sources/p34_install_candidate.py"):
        checked(AREA / name)
    inputs = [test, record(ROOT / ".cache/p34-next/n03/source-preparation.json"),
              record(ROOT / ".cache/p34-next/n03/build-result.json"),
              record(ROOT / ".cache/p34-session/n03-window8-repeat/assets/result.json"),
              record(ROOT / ".agents/skills/e-track-flutter-debug/scripts/host_io.py")]
    inputs += [record(ROOT / name) for name in OVERLAY]
    originals = [record(path) for path in base_files]
    # The three old root files must really be the measured lineage's versions.
    # Other dirty root sources are not candidates for implicit integration.
    baseline = []
    for name in OVERLAY:
        original = subprocess.run(["git", "--no-optional-locks", "-c", "core.fsmonitor=false",
                                   "show", "HEAD:" + name], cwd=ROOT, capture_output=True,
                                  timeout=20, creationflags=subprocess.CREATE_NO_WINDOW)
        require(original.returncode == 0 and original.stdout.replace(b"\r\n", b"\n") ==
                (BASE / name).read_bytes().replace(b"\r\n", b"\n"), "root/base ancestry mismatch: " + name)
        baseline.append(dict(name=name, head_sha256=hashlib.sha256(original.stdout).hexdigest()))
    env, paths = environment()
    snapshot = checked(AREA / "sources/p34_install_candidate.py")
    snapshot.parent.mkdir(parents=True, exist_ok=True)
    with snapshot.open("xb") as stream:
        stream.write(Path(__file__).read_bytes())
    inputs.append(record(snapshot))
    save(AREA / "intent.json", dict(inputs=inputs, base=str(BASE), fw=str(FW), build=str(BUILD),
        environment=paths, overlay_names=OVERLAY, ancestry=baseline, device_operations=0,
        source=record(Path(__file__)), generator_snapshot=record(snapshot)))
    try:
        for path in base_files:
            target = checked(FW / path.relative_to(BASE))
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(path, target)
        for name in OVERLAY:
            shutil.copyfile(ROOT / name, checked(FW / name))
        candidates = [record(FW / path.relative_to(BASE)) for path in base_files]
        differing = [str(path.relative_to(BASE)).replace("\\", "/")
                     for path, before, after in zip(base_files, originals, candidates)
                     if before["sha256"] != after["sha256"]]
        require(set(differing) == set(OVERLAY), "undeclared source delta")
        unchanged(originals + inputs)
        save(AREA / "source.json", dict(result="N04_SOURCE_READY", inputs=inputs, base=str(BASE),
            fw=str(FW), build=str(BUILD), base_files=originals, candidate_files=candidates,
            overlay_names=OVERLAY, source=record(Path(__file__)), device_operations=0))
        print("N04_SOURCE_READY", len(candidates), "files; overlay", len(OVERLAY), flush=True)
    except Exception as error:
        save(AREA / "failed-prepare.json", dict(error=type(error).__name__, detail=str(error),
                                               preserve_partial_outputs=True, device_operations=0))
        raise


def selected_symbols(text):
    selected = {}
    for line in text.splitlines():
        match = re.fullmatch(r"([a-fA-F0-9]+) ([a-fA-F0-9]+) (\w) (\S+)", line)
        if match is None:
            continue
        address, length, kind, name = match.groups()
        if name in ("g_p34_ble_profile", "_SEGGER_RTT", "qspi_xip_restore_checked") or "ota_install_restore" in name:
            require(name not in selected, "duplicate selected ELF symbol: " + name)
            selected[name] = dict(address=int(address, 16), bytes=int(length, 16), kind=kind)
    return selected


def original_command(tag):
    value = read(AREA / "logs" / (tag + ".json"))
    require(value["exit"] == 0 and value["timeout"] is False, "original build command did not succeed: " + tag)
    unchanged([value["stdout"], value["stderr"]])
    return b"".join(Path(value[key]["path"]).read_bytes() for key in ("stdout", "stderr"))


def build(*, reconcile=False):
    source = verify_source()
    require(not (AREA / "build.json").exists(), "preserve completed candidate build")
    if reconcile:
        require(BUILD.is_dir() and read(AREA / "failed-build.json")["detail"] == "N03 profile ABI changed",
                "reconciliation is limited to the recorded symbol-parser failure")
    else:
        require(not BUILD.exists(), "preserve attempted candidate build")
    failure = AREA / ("failed-reconcile.json" if reconcile else "failed-build.json")
    for path in (BUILD, AREA / "install", AREA / "build.json", failure):
        checked(path)
    for tool in (CMAKE, NINJA, ARM / "bin/arm-none-eabi-gcc.exe", ARM / "bin/arm-none-eabi-g++.exe"):
        require(tool.is_file(), "tool missing: " + str(tool))
    env, paths = environment()
    args = [CMAKE, "-S", FW / "MDK-ARM_F435/cmake-generated", "-B", BUILD, "-G", "Ninja",
        "-DCMAKE_BUILD_TYPE=Release", "-DCMAKE_OBJECT_PATH_MAX=1024", "-DP3_4_LINK_PROFILE=ON",
        "-DKEIL_GCC_COMPILER_CACHE:FILEPATH=", "-DARM_TOOLCHAIN_ROOT=" + str(ARM),
        "-DCMAKE_INSTALL_PREFIX=" + str(AREA / "install"), "-DCMAKE_MAKE_PROGRAM=" + str(NINJA),
        "-DCMAKE_CXX_FLAGS:STRING=-DCONFIG_OTA_INSTALL_QE_REUSE=1 -DCONFIG_OTA_INSTALL_PROFILE=1"]
    for language, compiler in (("C", "gcc"), ("CXX", "g++"), ("ASM", "gcc")):
        args.append("-DCMAKE_" + language + "_COMPILER=" +
                    str(ARM / "bin" / ("arm-none-eabi-" + compiler + ".exe")))
    try:
        if reconcile:
            log = original_command("configure") + original_command("build")
            size = original_command("size")
            symbols = original_command("symbols").decode("utf-8")
        else:
            log = run("configure", args, FW, env, 300)
            log += run("build", [CMAKE, "--build", BUILD, "--target", "X_Track_App_GCC", "--parallel", "8"],
                       FW, env, 1800)
            elf = BUILD / "app-gcc/X-Track-App-GCC.elf"
            size = run("size", [ARM / "bin/arm-none-eabi-size.exe", "--format=berkeley", elf], FW, env, 30)
            symbols = run("symbols", [ARM / "bin/arm-none-eabi-nm.exe", "-S", elf], FW, env, 30).decode("utf-8")
        selected = selected_symbols(symbols)
        require(selected.get("g_p34_ble_profile", {}).get("bytes") == 336, "N03 profile ABI changed")
        require("qspi_xip_restore_checked" in selected and "_SEGGER_RTT" in selected,
                "candidate restore/RTT symbols missing")
        raw = (BUILD / "app-gcc/X-Track-App-GCC.bin").read_bytes()
        require(0 < len(raw) <= 0xf0000 and b"P34INSTALL:" in raw, "candidate size/diagnostic marker invalid")
        commands = read(BUILD / "compile_commands.json")
        hal = [item for item in commands if item["file"].replace("\\", "/").endswith("/USER/HAL/HAL_OTA_Package.cpp")
               and "X_Track_App_GCC.dir" in item["command"]]
        require(len(hal) == 1 and all(flag in hal[0]["command"] for flag in
            ("-DCONFIG_OTA_INSTALL_QE_REUSE=1", "-DCONFIG_OTA_INSTALL_PROFILE=1")),
            "actual App compile command does not enable N04")
        require(not (BUILD / "boot/X-Track-Boot.bin").exists(), "App-only build unexpectedly generated Boot")
        verify_source()
        artifacts = [dict(record(path), mtime_ns=path.stat().st_mtime_ns)
                     for path in sorted((BUILD / "app-gcc").glob("X-Track-App-GCC.*"))]
        value = dict(result="N04_APP_BUILD_PASS", source_manifest=record(AREA / "source.json"),
            generator=source["source"], environment=paths, artifacts=artifacts, symbols=selected,
            warnings=len(re.findall(rb"\bwarning:", log)), errors=len(re.findall(rb"\berror:", log)),
            size_output=size.decode("utf-8"), app_bytes=len(raw), slot_bytes=0xf0000,
            n03_profile_bytes=336, n04_enabled=True, boot_built=False, finalized=False,
            device_operations=0, independent_acceptance=False, reused_original_build=reconcile,
            original_failure=record(AREA / "failed-build.json") if reconcile else None,
            verifier=record(Path(__file__)),
            commands=[record(AREA / "logs" / (name + ".json")) for name in ("configure", "build", "size", "symbols")])
        save(AREA / "build.json", value)
        print(json.dumps({key: value[key] for key in ("result", "warnings", "errors", "app_bytes", "boot_built")}),
              flush=True)
        print(value["size_output"], flush=True)
    except Exception as error:
        save(failure, dict(error=type(error).__name__, detail=str(error),
                           preserve_partial_outputs=True, device_operations=0))
        raise


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=("prepare", "build", "reconcile", "verify"))
    parser.add_argument("--root", required=True)
    parser.add_argument("--tests")
    args = parser.parse_args()
    require(Path(args.root) == ROOT and Path.cwd() == ROOT and sys.flags.isolated and
            sys.flags.no_site and sys.dont_write_bytecode, "explicit isolated project cwd required")
    if args.action == "prepare":
        require(args.tests is not None, "--tests required for source preparation")
        prepare(args.tests)
    elif args.action in ("build", "reconcile"):
        build(reconcile=args.action == "reconcile")
    else:
        source = verify_source()
        print("N04_SOURCE_UNCHANGED", len(source["candidate_files"]))


if __name__ == "__main__":
    main()
