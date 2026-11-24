"""Bounded P3-4 settings/observation workers, no target write or reset interface."""
import argparse
import ctypes
from ctypes import wintypes
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import time
import re

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "Tools/ota"))
import p34_session as cli
import p34_install_cost as host
from baud_uncached import native_presence
from recovery_entry.loader import BOOT_SHA
from recovery_entry.native_probe import DLL_SHA, Native, guarded
from recovery_entry.dap_probe import Dap, APP_LENGTH, APP_SHA
from recovery_entry.state_probe import sample as sample_state
from recovery_entry.probe import BEFORE_OPEN, BEFORE_CONNECT, Observation, scan_sdk_writes

JLINK = Path("C:/Users/SU/SEGGER/JLink_V818")
HISTORY = Path("C:/Users/SU/AppData/Roaming/SEGGER")
SELF = Path(__file__).resolve()
SOURCES = [SELF, *(ROOT / n for n in (
    "Tools/ota/recovery_entry/native_probe.py", "Tools/ota/recovery_entry/probe.py",
    "Tools/ota/recovery_entry/dap_probe.py",
    "Tools/ota/recovery_entry/state_probe.py",
    "Tools/ota/recovery_entry/loader.py", "Tools/ota/recovery_entry/load_contract.py",
    "Tools/ota/baud_uncached.py", "Tools/ota/p34_session.py", "Tools/ota/p34_install_cost.py",
    "Tools/flutter/dev_checks.py", "tests/boot/test_p34_native_probe.py",
    ".cache/p34-native-settings2/worker.json", ".cache/p34-native-settings2/plan.json",
    ".cache/p34-native-reference2/pylink-jlink.py", ".cache/p34-native-reference2/pyocd-jlink-probe.py",
    ".cache/p34-native-reference2/pyocd-dap.py",
    ".cache/p34-native-acquire1/boot-readback.bin",
    "tests/boot/test_p34_entry_probe.py", ".agents/skills/e-track-flutter-debug/scripts/host_io.py"))]
SOURCES += [ROOT / "vendor/AT32F435_437_DFP/Device/Include/at32f435_437.h"]
SOURCES += [ROOT / f"vendor/AT32F435_437_DFP/Peripherals/inc/at32f435_437_{name}.h"
            for name in ("debug", "wdt", "crm", "gpio", "dma", "edma", "qspi", "sdio", "flash")]
SOURCES += [ROOT / n for n in (
    ".cache/p34-sha-candidate/b/app-gcc/X-Track-App-GCC.map",
    ".cache/p34-app-handoff/disassembly.log", ".cache/p34-native-image1/worker.json",
    ".cache/p34-native-image1/app-readback.bin",
    ".cache/p34-sha-candidate/f/MDK-ARM_F435/Platform/Core/at32_sdio.h",
    ".cache/p34-sha-candidate/f/MDK-ARM_F435/Platform/Core/at32_sdio.c",
    ".cache/p34-entry-option-manual1/page-0089.txt",
    ".cache/p34-entry-option-manual1/page-0062.txt",
    ".cache/p34-entry-option-manual1/page-0103.txt",
    "MDK-ARM_F435/RTE/Device/-AT32F435RGT7/at32f435_437_flash.c")]
SOURCES += [ROOT / ".cache/p34-sha-candidate/f" / n for n in (
    "USER/App/Common/DataProc/DP_Recorder.cpp",
    "USER/HAL/HAL_SD_CARD.cpp")]
FILES = ("plan.json", "parent.json", "worker.log", "worker.json", "events.jsonl",
    "sdk.log", "callbacks.log", "project.jlink", "boot-readback.bin", "app-readback.bin")
BOOTSTRAP = "import json,runpy,sys; sys.argv=json.loads(sys.stdin.readline()); runpy.run_path(sys.argv[0],run_name='__main__')"


def history(store):
    root = store.io.checked_output(HISTORY, HISTORY)
    return [cli.record(store.io.checked_output(root, p)) for p in sorted(root.rglob('*')) if p.is_file()]


def in_job():
    kernel = ctypes.WinDLL("kernel32", use_last_error=True)
    kernel.GetCurrentProcess.restype = wintypes.HANDLE
    kernel.IsProcessInJob.argtypes = [wintypes.HANDLE, wintypes.HANDLE, ctypes.POINTER(wintypes.BOOL)]
    kernel.IsProcessInJob.restype = wintypes.BOOL
    value = wintypes.BOOL()
    cli.require(kernel.IsProcessInJob(kernel.GetCurrentProcess(), None, ctypes.byref(value)), "job query failed")
    return bool(value.value)


def owned_run(store, out, argv, env, timeout=45):
    runner = cli.load_module("probe_job", ROOT / "Tools/flutter/dev_checks.py")
    job, child = runner.WindowsJob(), None
    started = time.monotonic()
    result = dict(timeout=False, started=cli.now(), worker_released=False)
    log = store.checked(out / "worker.log")
    try:
        with log.open("xb") as stream:
            child = subprocess.Popen([sys.executable, "-I", "-S", "-B", "-X", "utf8", "-c", BOOTSTRAP],
                cwd=ROOT, env=env, stdin=subprocess.PIPE, stdout=stream, stderr=subprocess.STDOUT,
                creationflags=subprocess.CREATE_NO_WINDOW)
            result["pid"] = child.pid
            job.assign(child)
            child.stdin.write((json.dumps(list(map(str, argv))) + "\n").encode("ascii"))
            child.stdin.close()
            result["worker_released"] = True
            try:
                result["exit"] = child.wait(timeout=timeout)
            except subprocess.TimeoutExpired:
                result["timeout"] = True
    finally:
        job.terminate()
        job.close()
        if child:
            result["exit"] = child.wait(timeout=5)
        result.update(elapsed_seconds=time.monotonic()-started, ended=cli.now())
    return result


def worker(store, out):
    cli.require(in_job(), "owned Windows job required before SDK load")
    plan = store.read(out / "plan.json")
    cli.require(plan["inputs"] == [cli.record(p) for p in SOURCES] and plan["out"] == str(out), "source/plan drift")
    cli.require(plan["native_history_approved"] == str(HISTORY), "exact native history authority required")
    cli.require(cli.record(JLINK / "JLink_x64.dll")["sha256"] == DLL_SHA, "SDK digest drift")
    for name in FILES:
        store.checked(out / name)
    result = dict(result="FAILED", settings_only=plan["action"] in ("settings", "inspect-settings"), device_execute_ready=False,
        sdk_write_audit_passed=False, transient_debug_state_proven_unchanged=False,
        native_dll_loaded=False, probe_open_attempted=False, close_returned=False)
    observation, backend, data = None, None, bytearray()
    with (out / "events.jsonl").open("x", encoding="utf-8") as events, (out / "callbacks.log").open("xb") as callbacks:
        def emit(event, **fields):
            events.write(json.dumps(dict(time=cli.now(), event=event, **fields)) + "\n")
            events.flush()
        try:
            emit("presence", **native_presence())
            with os.add_dll_directory(str(JLINK)):
                sdk = guarded(ctypes.CDLL, str(JLINK / "JLink_x64.dll"))
                result["native_dll_loaded"] = True
                adapter = Dap if plan["action"] in ("dap", "state", "image") else Native
                backend = adapter(sdk, out / "sdk.log", out / "project.jlink", callbacks)
                observation = Observation(backend, emit, seconds=540 if plan["action"] == "image" else 30)
                if plan["action"] == "inspect-settings":
                    result["responses"] = []
                    for command in dict.fromkeys((*BEFORE_OPEN, *BEFORE_CONNECT,
                                                  "SetEnableMemCache = 0", "InvalidateCache")):
                        for repeat in (1, 2):
                            rc, message = backend.command(command)
                            item = dict(command=command, repeat=repeat, result=rc, message=message)
                            result["responses"].append(item)
                            emit("setting-response-observed", **item)
                            cli.require(type(rc) is int and rc >= 0 and message == "", "settings response error")
                    result["result"] = "SETTINGS_RESPONSES_OBSERVED_NO_PROBE_OPEN"
                elif plan["action"] == "settings":
                    observation.started = time.monotonic()
                    for command in (*BEFORE_OPEN, *BEFORE_CONNECT):
                        observation._setting(command)
                    observation._setting("SetEnableMemCache = 0")
                    observation._command("InvalidateCache")
                    result["result"] = "NATIVE_SETTINGS_PASS_NO_PROBE_OPEN"
                else:
                    observation.connect()
                    result["before"] = observation.sample()
                    emit("before", sample=result["before"])
                    cli.require(int.from_bytes(bytes.fromhex(result["before"]["raw"]["cpuid"]), "little") == 0x410fc241,
                                "unexpected CPU identity")
                    if plan["action"] == "image":
                        for offset in range(0, APP_LENGTH, 1024):
                            size = min(1024, APP_LENGTH - offset)
                            chunk = observation._call("read_flash", 0x08010000 + offset, size)
                            cli.require(isinstance(chunk, bytes) and len(chunk) == size, "short App chunk")
                            data.extend(chunk)
                            emit("app-progress", bytes=len(data), total=APP_LENGTH)
                    elif plan["action"] in ("dap", "state"):
                        data.extend(observation.read(0x08000000, 16))
                        if plan["action"] == "state":
                            result["state_samples"] = [sample_state(observation), sample_state(observation)]
                    else:
                        for offset in range(0, 65536, 4096):
                            data.extend(observation.read(0x08000000 + offset, 4096))
                    result["after"] = observation.sample()
                    emit("after", sample=result["after"])
                    digest = hashlib.sha256(data).hexdigest()
                    if plan["action"] == "image":
                        result["app_sha256"] = digest
                        cli.require(digest == APP_SHA, "full current App mismatch")
                        result["result"] = "DAP_FULL_APP_MATCH"
                    elif plan["action"] in ("dap", "state"):
                        cli.require(data == (ROOT / ".cache/p34-native-acquire1/boot-readback.bin").read_bytes()[:16],
                                    "Boot vector prefix mismatch")
                        result["result"] = "DAP_CORE_AND_VECTOR_PREFIX_OBSERVED"
                    else:
                        result["boot_sha256"] = digest
                        cli.require(digest == BOOT_SHA, "complete Boot identity mismatch")
                        result["result"] = "OBSERVED_BOOT_MATCH_REQUIRES_WRITE_RECONCILIATION"
        except BaseException as error:
            result["error"] = type(error).__name__ + ": " + str(error)
        finally:
            if observation:
                result["probe_open_attempted"] = observation.open_attempted
                try:
                    observation.close()
                except BaseException as error:
                    result["close_error"] = type(error).__name__ + ": " + str(error)
                    result["result"] = "FAILED"
            result["close_returned"] = backend is not None and backend.close_returned
            if isinstance(backend, Dap): result["dap"] = backend.metadata
            if data:
                is_app = plan["action"] == "image"
                result["readback"] = store.raw(out / ("app-readback.bin" if is_app else "boot-readback.bin"), data)
                result["app_bytes" if is_app else "boot_bytes"] = len(data)
            if (out / "sdk.log").exists():
                result["write_inventory"] = scan_sdk_writes((out / "sdk.log").read_text(errors="replace"))
            store.write(out / "worker.json", result)
    print(json.dumps(result))
    return 0 if result["result"] != "FAILED" else 1


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=("selftest", "inspect-settings", "settings", "acquire", "dap", "state", "image", "worker", "fixture-hang", "fixture-ok"))
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--native-history-approved", type=Path)
    parser.add_argument("--tests", type=Path)
    parser.add_argument("--settings", type=Path)
    args = parser.parse_args()
    cli.require(Path.cwd() == ROOT and sys.flags.isolated and sys.flags.no_site and sys.dont_write_bytecode,
                "isolated explicit project root required")
    store = cli.Store(ROOT)
    out = store.checked(args.output_dir)
    if args.action.startswith("fixture-"):
        cli.require(in_job(), "fixture must be owned")
        if args.action == "fixture-hang": guarded(time.sleep, 2, seconds=.05)
        print("OWNED_FIXTURE_PASS")
        return 0
    if args.action == "worker": return worker(store, out)
    if args.action == "selftest":
        cli.require(not out.exists(), "preserve self-test evidence")
        for name in ("tests.log", "tests.json", "result.json", "case-ok", "case-hang"):
            store.checked(out / name)
        inputs = [cli.record(p) for p in SOURCES]
        for p in SOURCES:
            store.checked(out / "source" / p.relative_to(ROOT))
        env = host.environment(store, out)
        env["P34_TEST_OUT"] = str(out)
        for p in SOURCES:
            store.raw(out / "source" / p.relative_to(ROOT), p.read_bytes())
        data = host.command(store, out, "tests", [sys.executable, "-I", "-S", "-B", "-X", "utf8",
            ROOT / "tests/boot/test_p34_native_probe.py", "-v"], env, 90)
        match = re.search(rb"Ran (\d+) tests? in .*\r?\n\r?\nOK\b", data)
        cli.require(match is not None and inputs == [cli.record(p) for p in SOURCES], "test result/input drift")
        store.write(out / "result.json", dict(result="NATIVE_PROBE_HOST_PASS", tests=int(match[1]), inputs=inputs,
            hardware=False, native_dll_loaded=False))
        print("NATIVE_PROBE_HOST_PASS", int(match[1]), "tests")
        return 0
    cli.require(args.native_history_approved is not None and args.native_history_approved == HISTORY,
                "current exact history approval required")
    cli.require(not out.exists(), "preserve existing acquisition")
    inputs = [cli.record(p) for p in SOURCES]
    tests = store.read(args.tests)
    cli.require(tests["result"] == "NATIVE_PROBE_HOST_PASS" and tests["inputs"] == inputs, "bound host tests required")
    if args.action in ("acquire", "dap", "state", "image"):
        settings = store.read(args.settings)
        cli.require(settings["result"] == "NATIVE_SETTINGS_PASS_NO_PROBE_OPEN" and
                    store.read(args.settings.parent / "plan.json")["inputs"] == inputs and
                    store.read(args.settings.parent / "parent.json")["exit"] == 0, "native settings must pass first")
    for name in FILES:
        store.checked(out / name)
    for path in SOURCES:
        store.checked(out / "source" / path.relative_to(ROOT))
    before = history(store)
    cli.require(cli.record(JLINK / "JLink_x64.dll")["sha256"] == DLL_SHA, "SDK digest drift")
    env = host.environment(store, out)
    for p in SOURCES:
        store.raw(out / "source" / p.relative_to(ROOT), p.read_bytes())
    store.write(out / "plan.json", dict(action=args.action, out=str(out), inputs=inputs,
        native_history_approved=str(HISTORY), user_approval="Current user reply: allowed; native history/config only, no cleanup",
        before_history=before, dll=cli.record(JLINK / "JLink_x64.dll"),
        power="User-confirmed J-Link 3.3V/GND direct supply; no power commands",
        worker_seconds=600 if args.action == "image" else 45, native_call_seconds=5, target_writes_requested=0))
    result = owned_run(store, out, [SELF, "worker", "--output-dir", out], env,
                       timeout=600 if args.action == "image" else 45)
    result["after_history"] = history(store)
    result["presence_after"] = native_presence()
    store.write(out / "parent.json", result)
    print(json.dumps(result))
    return 0 if result["exit"] == 0 and not result["timeout"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
