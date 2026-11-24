"""Owned, source-bound WFI rendezvous worker. No reset/resume/Flash/RAM-write action."""
import argparse
import ctypes
import json
import os
from pathlib import Path
import re
import sys

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "Tools/ota"))
import p34_probe_acquire as base
from recovery_entry.control_probe import Control
from recovery_entry.rendezvous import acquire

cli, host = base.cli, base.host
SELF = Path(__file__).resolve()
SOURCES = list(dict.fromkeys([*base.SOURCES, SELF, *(ROOT / n for n in (
    "Tools/ota/recovery_entry/rendezvous.py", "Tools/ota/recovery_entry/control_probe.py",
    "tests/boot/test_p34_rendezvous.py", "tests/boot/test_p34_control_probe.py",
    ".cache/p34-native-probe-test11/result.json", ".cache/p34-native-settings9/worker.json",
    ".cache/p34-native-settings9/plan.json", ".cache/p34-native-settings9/parent.json",
    ".cache/p34-native-entry-facts2/worker.json", ".cache/p34-entry-control-reference1/cortex_m.py",
    ".cache/p34-entry-control-reference1/fpb.py", ".cache/p34-entry-control-reference1/result.json",
    "vendor/AT32F435_437_DFP/Peripherals/inc/at32f435_437_wwdt.h",
    ".cache/p34-sha-candidate/f/Libraries/SdFat/src/FatLib/FatVolume.h",
    ".cache/p34-sha-candidate/f/MDK-ARM_F435/Platform/middlewares/usb_drivers/src/usbd_core.c"))]))
FILES = ("plan.json", "worker.json", "parent.json", "worker.log", "sdk.log", "project.jlink",
         "callbacks.log", "events.jsonl", "tests.log", "tests.json", "result.json")


def preflight(store, out):
    cli.require(not out.exists(), "preserve rendezvous evidence")
    for name in FILES:
        store.checked(out / name)
    for p in SOURCES:
        store.checked(out / "source" / p.relative_to(ROOT))


def snapshot(store, out):
    inputs = [cli.record(p) for p in SOURCES]
    env = host.environment(store, out)
    for p in SOURCES:
        store.raw(out / "source" / p.relative_to(ROOT), p.read_bytes())
    return inputs, env


def worker(store, out):
    cli.require(base.in_job(), "owned job required before native DLL load")
    plan = store.read(out / "plan.json")
    cli.require(plan["action"] in ("wfi", "observe-retained"), "unknown control action")
    cli.require(plan["inputs"] == [cli.record(p) for p in SOURCES] and plan["out"] == str(out), "source/plan drift")
    cli.require(plan["native_history_approved"] == str(base.HISTORY), "exact native history approval")
    cli.require(cli.record(base.JLINK / "JLink_x64.dll")["sha256"] == base.DLL_SHA, "DLL drift")
    for name in FILES:
        store.checked(out/name)
    result = dict(result="FAILED", close_returned=False, device_execute_ready=False,
                  native_dll_loaded=False, reset_performed=False, supply_commands=False)
    control, observation, dap = None, None, None
    with (out / "events.jsonl").open("x", encoding="utf-8") as events, (out / "callbacks.log").open("xb") as callbacks:
        def emit(event, **fields):
            events.write(json.dumps(dict(time=cli.now(), event=event, **fields)) + "\n")
            events.flush()
        try:
            presence = base.native_presence()
            emit("presence", **presence)
            cli.require(not presence["debugger_processes"], "another debugger owns the board")
            with os.add_dll_directory(str(base.JLINK)):
                sdk = base.guarded(ctypes.CDLL, str(base.JLINK / "JLink_x64.dll"))
                result["native_dll_loaded"] = True
                dap = base.Dap(sdk, out / "sdk.log", out / "project.jlink", callbacks)
                observation = base.Observation(dap, emit, seconds=35)
                image = (ROOT / ".cache/p34-native-image1/app-readback.bin").read_bytes()
                control = Control(dap, observation, emit, image[0x400:0x460], retained=plan["action"] == "observe-retained")
                observation.connect()
                if plan["action"] == "wfi":
                    result.update(acquire(control, emit, seconds=15))
                else:
                    previous = plan["previous"]
                    cli.require(cli.record(Path(previous["path"])) == previous, "retained receipt changed")
                    result.update(control.observe_retained(store.read(previous["path"])))
        except Exception as error:
            result["error"] = type(error).__name__ + ": " + str(error)
        finally:
            try:
                if control:
                    control.close()
                elif observation:
                    observation.close()
            except Exception as error:
                result.update(result="FAILED", close_error=type(error).__name__ + ": " + str(error))
            result["close_returned"] = bool(dap and dap.close_returned)
            if dap: result["dap"] = dap.metadata
            if control: result["transport_mutation_attempted"] = control.mutation_attempted
            store.write(out / "worker.json", result)
    print(json.dumps(result))
    return 0 if result["result"] in ("APP_WFI_HALTED_RETAINED_NOT_RESET", "APP_WFI_RETAINED_AFTER_RECONNECT") and result["close_returned"] else 1


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=("selftest", "wfi", "observe-retained", "worker"))
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--tests", type=Path)
    parser.add_argument("--previous", type=Path)
    parser.add_argument("--native-history-approved", type=Path)
    args = parser.parse_args()
    cli.require(Path.cwd() == ROOT and sys.flags.isolated and sys.flags.no_site and sys.dont_write_bytecode,
                "isolated explicit project root required")
    store = cli.Store(ROOT)
    out = store.checked(args.output_dir)
    if args.action == "worker": return worker(store, out)
    preflight(store, out)
    inputs = [cli.record(p) for p in SOURCES]
    if args.action == "selftest":
        inputs, env = snapshot(store, out)
        data = host.command(store, out, "tests", [sys.executable, "-I", "-S", "-B", "-X", "utf8",
                            ROOT/"tests/boot/test_p34_control_probe.py", "-v"], env, 90)
        match = re.search(rb"Ran (\d+) tests? in .*\r?\n\r?\nOK\b", data)
        cli.require(match and inputs == [cli.record(p) for p in SOURCES], "test/input drift")
        store.write(out / "result.json", dict(result="WFI_CONTROL_HOST_PASS", tests=int(match[1]), inputs=inputs,
                                               hardware=False, native_dll_loaded=False))
        print("WFI_CONTROL_HOST_PASS", int(match[1]), "tests")
        return 0
    cli.require(args.native_history_approved == base.HISTORY, "current exact history authority required")
    tests = store.read(args.tests)
    cli.require(tests["result"] == "WFI_CONTROL_HOST_PASS" and tests["inputs"] == inputs, "bound host tests required")
    original_tests = store.read(ROOT/".cache/p34-native-probe-test11/result.json")
    cli.require(original_tests["inputs"] == [cli.record(p) for p in base.SOURCES], "base read adapter test drift")
    settings = store.read(ROOT/".cache/p34-native-settings9/worker.json")
    cli.require(settings["result"] == "NATIVE_SETTINGS_PASS_NO_PROBE_OPEN" and
                store.read(ROOT/".cache/p34-native-settings9/plan.json")["inputs"] == original_tests["inputs"] and
                store.read(ROOT/".cache/p34-native-settings9/parent.json")["exit"] == 0, "native settings drift")
    cli.require(cli.record(base.JLINK/"JLink_x64.dll")["sha256"] == base.DLL_SHA, "DLL drift")
    previous = None
    if args.action == "observe-retained":
        previous = cli.record(store.checked(args.previous))
        old = store.read(args.previous)
        old_plan, old_parent = (store.read(args.previous.parent/n) for n in ("plan.json", "parent.json"))
        cli.require(old["result"] == "APP_WFI_HALTED_RETAINED_NOT_RESET" and old["close_returned"] and
                    old_plan["inputs"] == inputs and old_parent["exit"] == 0 and not old_parent["timeout"],
                    "same-source normally closed retained predecessor required")
    before = base.history(store)
    inputs, env = snapshot(store, out)
    store.write(out/"plan.json", dict(action=args.action, out=str(out), inputs=inputs, previous=previous,
        tests=cli.record(args.tests), native_history_approved=str(base.HISTORY), before_history=before,
        user_authority="P3-4 autonomous continuation; verified WFI stop only; no reset/Flash/RAM writes",
        power="J-Link direct 3.3V/GND remains connected; no physical supply commands",
        retention="Keep WDT halt-pause and logical DP system/debug requests; no automatic resume",
        worker_seconds=45, native_call_seconds=5, rendezvous_seconds=15))
    result = base.owned_run(store, out, [SELF, "worker", "--output-dir", out], env, timeout=45)
    result["after_history"] = base.history(store)
    result["presence_after"] = base.native_presence()
    store.write(out/"parent.json", result)
    print(json.dumps(result))
    return 0 if result["exit"] == 0 and not result["timeout"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
