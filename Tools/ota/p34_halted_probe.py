"""Bounded owner/config observation of the unchanged, retained WFI halt."""
import argparse
import ctypes
import json
import os
from pathlib import Path
import re
import sys

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT/"Tools/ota"))
import p34_rendezvous as predecessor
from recovery_entry.owner_probe import Reader, collect
from recovery_entry.control_probe import Control

base, cli, host = predecessor.base, predecessor.cli, predecessor.host
SELF = Path(__file__).resolve()
SOURCES = list(dict.fromkeys([*predecessor.SOURCES, SELF, *(ROOT/n for n in (
    "Tools/ota/recovery_entry/owner_probe.py", "tests/boot/test_p34_owner_probe.py",
    ".cache/p34-entry-control-test3/result.json", ".cache/p34-entry-wfi1/worker.json",
    ".cache/p34-entry-wfi1/plan.json", ".cache/p34-entry-wfi1/parent.json",
    ".cache/p34-entry-wfi-retained1/worker.json", ".cache/p34-entry-wfi-retained1/parent.json",
    ".cache/p34-sha-candidate/f/USER/App/Pages/FirmwareUpdate/FirmwareUpdate.cpp",
    ".cache/p34-sha-candidate/f/USER/App/Pages/FirmwareUpdate/FirmwareUpdate.h",
    ".cache/p34-sha-candidate/f/USER/App/Utils/PageManager/PageBase.h",
    ".cache/p34-sha-candidate/f/USER/App/Utils/StorageService/StorageService.cpp",
    ".cache/p34-sha-candidate/f/MDK-ARM_F435/Platform/middlewares/usb_drivers/inc/usb_std.h"))]))


def preflight(store,out):
    cli.require(not out.exists(),"preserve halted observation")
    for name in predecessor.FILES: store.checked(out/name)
    for p in SOURCES: store.checked(out/"source"/p.relative_to(ROOT))


def snapshot(store,out):
    inputs=[cli.record(p) for p in SOURCES]
    env=host.environment(store,out)
    for p in SOURCES: store.raw(out/"source"/p.relative_to(ROOT),p.read_bytes())
    return inputs,env


def worker(store,out):
    cli.require(base.in_job(),"owned job required")
    plan=store.read(out/"plan.json")
    cli.require(plan["inputs"]==[cli.record(p) for p in SOURCES] and plan["out"]==str(out),"input drift")
    cli.require(plan["native_history_approved"]==str(base.HISTORY),"history authority mismatch")
    cli.require(cli.record(base.JLINK/"JLink_x64.dll")["sha256"]==base.DLL_SHA,"DLL drift")
    result=dict(result="FAILED",close_returned=False,device_execute_ready=False,
                reset_performed=False,peripheral_writes=False)
    control,dap=None,None
    with (out/"events.jsonl").open("x",encoding="utf-8") as events, (out/"callbacks.log").open("xb") as callbacks:
        def emit(event,**fields):
            events.write(json.dumps(dict(time=cli.now(),event=event,**fields))+"\n"); events.flush()
        try:
            presence=base.native_presence(); emit("presence",**presence)
            cli.require(not presence["debugger_processes"],"another debugger present")
            with os.add_dll_directory(str(base.JLINK)):
                sdk=base.guarded(ctypes.CDLL,str(base.JLINK/"JLink_x64.dll"))
                dap=base.Dap(sdk,out/"sdk.log",out/"project.jlink",callbacks)
                observation=base.Observation(dap,emit,seconds=35)
                image=(ROOT/".cache/p34-native-image1/app-readback.bin").read_bytes()
                control=Control(dap,observation,emit,image[0x400:0x460],retained=True)
                observation.connect()
                previous=store.read(ROOT/".cache/p34-entry-wfi1/worker.json")
                retained=control.observe_retained(previous)
                result["retained"]=retained
                owners=[]
                for _ in range(2):
                    observation._check()
                    reader=Reader(dap,emit)
                    owners.append(dict(updater=collect(reader),qspi=reader.qspi()))
                cli.require(owners[0]==owners[1],"owner/config changed while halted")
                cli.require(control.context()==previous["context"],"retained context changed")
                observation._check()
                result.update(result="HALTED_OWNER_CONFIG_OBSERVED",owner_samples=owners)
        except Exception as error:
            result["error"]=type(error).__name__+": "+str(error)
        finally:
            try:
                if control: control.close()
            except Exception as error:
                result.update(result="FAILED",close_error=type(error).__name__+": "+str(error))
            result["close_returned"]=bool(dap and dap.close_returned)
            if dap: result["dap"]=dap.metadata
            store.write(out/"worker.json",result)
    print(json.dumps(result))
    return 0 if result["result"]=="HALTED_OWNER_CONFIG_OBSERVED" and result["close_returned"] else 1


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action",choices=("selftest","owners","worker"))
    parser.add_argument("--output-dir",type=Path,required=True)
    parser.add_argument("--tests",type=Path)
    parser.add_argument("--native-history-approved",type=Path)
    args=parser.parse_args()
    cli.require(Path.cwd()==ROOT and sys.flags.isolated and sys.flags.no_site and sys.dont_write_bytecode,"isolated explicit root required")
    store=cli.Store(ROOT); out=store.checked(args.output_dir)
    if args.action=="worker": return worker(store,out)
    preflight(store,out)
    inputs=[cli.record(p) for p in SOURCES]
    if args.action=="selftest":
        inputs,env=snapshot(store,out)
        env["P34_TEST_OUT"]=str(out)
        data=host.command(store,out,"tests",[sys.executable,"-I","-S","-B","-X","utf8",ROOT/"tests/boot/test_p34_owner_probe.py","-v"],env,60)
        match=re.search(rb"Ran (\d+) tests? in .*\r?\n\r?\nOK\b",data)
        cli.require(match and inputs==[cli.record(p) for p in SOURCES],"test/input drift")
        store.write(out/"result.json",dict(result="HALTED_OWNER_HOST_PASS",tests=int(match[1]),inputs=inputs,hardware=False))
        print("HALTED_OWNER_HOST_PASS",int(match[1]),"tests"); return 0
    cli.require(args.native_history_approved==base.HISTORY,"exact current history approval required")
    tests=store.read(args.tests)
    cli.require(tests["result"]=="HALTED_OWNER_HOST_PASS" and tests["inputs"]==inputs,"bound tests required")
    old=store.read(ROOT/".cache/p34-entry-wfi1/plan.json")
    cli.require(old["inputs"]==[cli.record(p) for p in predecessor.SOURCES],"retained adapter source drift")
    for name in ("p34-entry-wfi1","p34-entry-wfi-retained1"):
        parent=store.read(ROOT/".cache"/name/"parent.json")
        cli.require(parent["exit"]==0 and not parent["timeout"],"uncertain predecessor")
    before=base.history(store); inputs,env=snapshot(store,out)
    store.write(out/"plan.json",dict(action="owners",out=str(out),inputs=inputs,tests=cli.record(args.tests),
        native_history_approved=str(base.HISTORY),before_history=before,worker_seconds=45,native_call_seconds=5,
        scope="Retained WFI; fixed pointer-chain and non-consuming QSPI reads; only core-read selector writes"))
    result=base.owned_run(store,out,[SELF,"worker","--output-dir",out],env,timeout=45)
    result["after_history"]=base.history(store); result["presence_after"]=base.native_presence()
    store.write(out/"parent.json",result); print(json.dumps(result))
    return 0 if result["exit"]==0 and not result["timeout"] else 1


if __name__=="__main__": raise SystemExit(main())
