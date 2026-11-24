"""Contained host-driven EEPROM read using the existing fixed C BCB reader."""
import argparse
import ctypes
import json
import os
from pathlib import Path
import re
import sys
import time

ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT/"Tools/ota"))
import p34_halted_probe as previous
from recovery_entry.control_probe import Control
from recovery_entry import host_bcb as hb

base,cli,host=previous.base,previous.cli,previous.host
SELF=Path(__file__).resolve()
CC=Path("D:/install/mingw64/bin/gcc.exe")
CORE=ROOT/"Tools/ota/ram_recovery"
LIB=ROOT/".cache/p34-bc-target/f/Libraries"
SOURCES=list(dict.fromkeys([*previous.SOURCES,SELF,*(ROOT/n for n in (
    "Tools/ota/recovery_entry/host_bcb.py","tests/boot/test_p34_host_bcb.py",
    "Tools/ota/ram_recovery/bcb_reader.c","Tools/ota/ram_recovery/bcb_reader.h",
    "Tools/ota/recovery_entry/report.py",
    ".cache/p34-bc-target/f/Libraries/EEPROM/eeprom_bcb.c",
    ".cache/p34-bc-target/f/Libraries/EEPROM/eeprom_bcb.h",
    ".cache/p34-bcb-reader1/result.json",
    ".cache/p34-entry-owner1/worker.json",".cache/p34-entry-owner1/parent.json",
    ".cache/p34-entry-owner1/plan.json",
    ".cache/p34-eeprom-reference1/result.json",
    ".cache/p34-eeprom-reference1/page-05.txt",".cache/p34-eeprom-reference1/page-06.txt",
    ".cache/p34-eeprom-reference1/page-11.txt",".cache/p34-eeprom-reference1/page-12.txt"))]))
FILES=(*previous.predecessor.FILES,"compile.log","compile.json","bcb-reader.dll","capture-raw.bin")


def preflight(store,out):
    cli.require(not out.exists(),"preserve BCB evidence")
    for name in FILES: store.checked(out/name)
    for p in SOURCES: store.checked(out/"source"/p.relative_to(ROOT))


def snapshot(store,out):
    inputs=[cli.record(p) for p in SOURCES]
    env=host.environment(store,out)
    for p in SOURCES: store.raw(out/"source"/p.relative_to(ROOT),p.read_bytes())
    return inputs,env


def worker(store,out):
    cli.require(base.in_job(),"owned worker required")
    plan=store.read(out/"plan.json")
    cli.require(plan["inputs"]==[cli.record(p) for p in SOURCES] and plan["out"]==str(out),"source/plan drift")
    cli.require(plan["native_history_approved"]==str(base.HISTORY),"history authority mismatch")
    cli.require(cli.record(base.JLINK/"JLink_x64.dll")["sha256"]==base.DLL_SHA,"J-Link DLL drift")
    reader_path=store.checked(plan["reader_dll"]["path"])
    cli.require(cli.record(reader_path)==plan["reader_dll"],"tested C reader drift")
    result=dict(result="FAILED",close_returned=False,reset_performed=False,device_execute_ready=False,
                gpio_configuration_changed=False,nor_accessed=False,ram_code_executed=False)
    control,dap=None,None
    with (out/"events.jsonl").open("x",encoding="utf-8") as events, (out/"callbacks.log").open("xb") as callbacks:
        def emit(event,**fields):
            events.write(json.dumps(dict(time=cli.now(),event=event,**fields))+"\n"); events.flush()
        try:
            presence=base.native_presence(); emit("presence",**presence)
            cli.require(not presence["debugger_processes"],"another debugger present")
            reader=ctypes.CDLL(str(reader_path))
            function=hb.bind(reader)
            with os.add_dll_directory(str(base.JLINK)):
                sdk=base.guarded(ctypes.CDLL,str(base.JLINK/"JLink_x64.dll"))
                dap=base.Dap(sdk,out/"sdk.log",out/"project.jlink",callbacks)
                observation=base.Observation(dap,emit,seconds=350)
                image=(ROOT/".cache/p34-native-image1/app-readback.bin").read_bytes()
                control=Control(dap,observation,emit,image[0x400:0x460],retained=True)
                observation.connect()
                original=store.read(ROOT/".cache/p34-entry-wfi1/worker.json")
                retained=control.observe_retained(original)
                result["before"]=retained
                pins=hb.Pins(control,retained["state_samples"][-1]["raw"],emit)
                pins.verify(idle=True)
                stop_bound=time.monotonic()
                time.sleep(.006)
                cli.require(time.monotonic()-stop_bound>=.005,"EEPROM settlement wait too short")
                result["pre_bus_settlement_seconds"]=time.monotonic()-stop_bound
                emit("i2c-capture-start",sequence="A/B/A/B",last_possible_stop_wait_seconds=result["pre_bus_settlement_seconds"])
                captured=hb.capture(function,pins,seconds=300)
                result["capture"]=captured
                result["raw"]=store.raw(out/"capture-raw.bin",bytes.fromhex(captured["raw_hex"]))
                result["edge_attempts"],result["sda_samples"]=pins.edges,pins.samples
                cli.require(captured["result"]=="HOST_BCB_CAPTURED","BCB capture failed; retain without bus cleanup")
                pins.verify(idle=True)
                cli.require(control.context()==original["context"],"post-read context changed")
                observation._check()
                result.update(result="HOST_BCB_READ_VERIFIED_RETAINED",bus_released_high=True,
                              eeprom_payload_bytes_written=0,internal_eeprom_pointer_changed=True)
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
    return 0 if result["result"]=="HOST_BCB_READ_VERIFIED_RETAINED" and result["close_returned"] else 1


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action",choices=("selftest","capture","worker"))
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
        dll=store.checked(out/"bcb-reader.dll")
        compile_log=host.command(store,out,"compile",[CC,"-std=c99","-O2","-Wall","-Wextra","-Werror","-shared",
            "-static-libgcc","-I"+str(CORE),"-I"+str(LIB),CORE/"bcb_reader.c",LIB/"EEPROM/eeprom_bcb.c","-o",dll],env,90)
        env["P34_BCB_DLL"]=str(dll); env["P34_TEST_OUT"]=str(out)
        data=host.command(store,out,"tests",[sys.executable,"-I","-S","-B","-X","utf8",ROOT/"tests/boot/test_p34_host_bcb.py","-v"],env,90)
        match=re.search(rb"Ran (\d+) tests? in .*\r?\n\r?\nOK\b",data)
        cli.require(match and inputs==[cli.record(p) for p in SOURCES],"test/input drift")
        store.write(out/"result.json",dict(result="HOST_BCB_CALLBACKS_PASS",tests=int(match[1]),inputs=inputs,
            reader_dll=cli.record(dll),compiler=cli.record(CC),hardware=False,
            warnings=len(re.findall(rb"\bwarning:",compile_log)),errors=len(re.findall(rb"\berror:",compile_log))))
        print("HOST_BCB_CALLBACKS_PASS",int(match[1]),"tests"); return 0
    cli.require(args.native_history_approved==base.HISTORY,"exact history authority required")
    tests=store.read(args.tests)
    cli.require(tests["result"]=="HOST_BCB_CALLBACKS_PASS" and tests["inputs"]==inputs and
                tests["compiler"]==cli.record(CC) and tests["errors"]==tests["warnings"]==0,"bound host tests required")
    old=store.read(ROOT/".cache/p34-entry-owner1/plan.json")
    cli.require(old["inputs"]==[cli.record(p) for p in previous.SOURCES],"predecessor source drift")
    cli.require(cli.record(store.checked(tests["reader_dll"]["path"]))==tests["reader_dll"],"reader DLL changed")
    parent=store.read(ROOT/".cache/p34-entry-owner1/parent.json")
    cli.require(parent["exit"]==0 and not parent["timeout"],"uncertain predecessor")
    before=base.history(store); inputs,env=snapshot(store,out)
    store.write(out/"plan.json",dict(action="capture",out=str(out),inputs=inputs,tests=cli.record(args.tests),
        reader_dll=tests["reader_dll"],native_history_approved=str(base.HISTORY),before_history=before,
        worker_seconds=360,capture_seconds=300,native_call_seconds=5,
        scope="Existing C random-read A/B/A/B; only PB6/PB7 set/clear; no config/EEPROM payload/NOR/reset/RAM writes"))
    result=base.owned_run(store,out,[SELF,"worker","--output-dir",out],env,timeout=360)
    result["after_history"]=base.history(store); result["presence_after"]=base.native_presence()
    store.write(out/"parent.json",result); print(json.dumps(result))
    return 0 if result["exit"]==0 and not result["timeout"] else 1


if __name__=="__main__": raise SystemExit(main())
