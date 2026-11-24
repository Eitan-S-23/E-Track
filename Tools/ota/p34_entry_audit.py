"""Offline entry/EEPROM trace, source binding and selected-output boundary audit."""
import ast
import hashlib
import json
from pathlib import Path
import re
import struct
import sys
import zlib

ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT/"Tools/ota"))
import p34_session as cli
import p34_probe_audit as old_audit
from recovery_entry.control_probe import READ_WORDS,DCRSR,PAUSE,COMP,EXTRA
from recovery_entry.owner_probe import QSPI_REGS,PAGE_NAME,MANAGER
from recovery_entry.rendezvous import WFI,WFI_COMPARATOR

AREAS=("p34-native-probe-test9","p34-native-probe-test10","p34-native-probe-test11",
       "p34-native-settings8","p34-native-settings9","p34-native-entry-facts1","p34-native-entry-facts2",
       "p34-entry-option-manual1","p34-entry-rendezvous-test1","p34-entry-control-reference1",
       "p34-entry-control-test1","p34-entry-control-test2","p34-entry-control-test3",
       "p34-entry-wfi1","p34-entry-wfi-retained1","p34-entry-qspi-manual1",
       "p34-entry-owner-test1","p34-entry-owner-test2","p34-entry-owner1",
       "p34-host-bcb-test1","p34-host-bcb-test2","p34-host-bcb1")


def trace_writes(text,worker,events,kind):
    allowed=set(READ_WORDS)|{DCRSR,WFI,worker["dap"]["original_tar"]}
    if kind=="owners":
        data=worker["owner_samples"][0]["updater"]
        allowed.update(QSPI_REGS.values())
        allowed.update(range(MANAGER+4,MANAGER+16,4))
        allowed.update(range(data["page_pool"][0],data["page_pool"][1],4))
        allowed.update(range(PAGE_NAME&~3,(PAGE_NAME&~3)+24,4))
        for item in data["headers"]: allowed.update(range(item["address"],item["address"]+16,4))
        pointer=data["updater"]
        allowed.update(pointer+i for i in (0x44,0x1284,0x1470,0x34e8,0x34ec))
        allowed.update(range(pointer+0x13b4,pointer+0x13f4,4))
    if kind=="bcb": allowed.update((0x40020418,0x40020428))
    writes=[]; tar=None
    for line in text.splitlines():
        if "CPU_WriteMem" in line: raise ValueError("unexpected high-level CPU write")
        if not re.search(r"JLINK\w*_(?:Write|CORESIGHT_Write)",line): continue
        m=re.fullmatch(r".*JLINK_CORESIGHT_WriteAPDPReg\((AP|DP) reg 0x([0-9A-Fa-f]+), 0x([0-9A-Fa-f]+)\)",line)
        if not m: raise ValueError("unknown SDK write")
        port,register,value=m[1],int(m[2],16),int(m[3],16)
        if port=="DP":
            valid=(register==2 and value in (0,0xf0)) or (register==1 and value in (0x50000040,0x10000040,0x40))
        elif register==0:
            csw=worker["dap"]["ap_csw"]
            valid=value in (csw,(csw&~0x37)|0x12)
        elif register==1:
            tar=value; valid=tar in allowed
        elif register==3:
            valid=(tar==DCRSR and value in (15,16,17,20)) or (
                kind=="wfi" and ((tar==PAUSE and value==0x1000) or (tar==COMP and value in (0,WFI_COMPARATOR)))) or (
                kind=="bcb" and tar in (0x40020418,0x40020428) and value in (0x40,0x80))
            if valid: writes.append((tar,value))
        else: valid=False
        if not valid: raise ValueError("write outside exact entry capability")
    expected=[(e["address"],e["value"]) for e in events if e["event"] in ("debug-write-attempt","i2c-edge-attempt")]
    if writes!=expected: raise ValueError("SDK and action journal disagree")
    if tar!=worker["dap"]["original_tar"]: raise ValueError("TAR not restored")
    return writes


def wire(events,worker):
    output=worker["before"]["state_samples"][-1]["raw"]["gpiob_output"]
    original=output; pending=None; started=False; drive=[]; sampled=[]; current=None
    attempts=verified=starts=stops=0
    for e in events:
        if e["event"]=="i2c-capture-start": started=True
        if not started: continue
        if e["event"]=="control-word" and e["address"]==0x40020410 and output&0x40 and e["value"]&0x40 and current is not None:
            sampled[current]=int(bool(e["value"]&0x80))
        if e["event"]=="i2c-edge-attempt":
            cli.require(pending is None,"overlapping edge attempt")
            attempts+=1; pending=e
        if e["event"]=="i2c-edge-verified":
            cli.require(pending and all(e[k]==pending[k] for k in ("edge","pin","high")),"edge verification mismatch")
            verified+=1; pin,high=e["pin"],e["high"]; before=output
            if high: output|=1<<pin
            else: output&=~(1<<pin)
            if pin==6 and not before&0x40 and output&0x40:
                drive.append(int(bool(output&0x80))); sampled.append(None); current=len(drive)-1
            if pin==6 and not output&0x40: current=None
            if pin==7 and before&0x40 and bool(before&0x80)!=bool(output&0x80):
                if high: stops+=1
                else: starts+=1
            pending=None
    cli.require(pending is None and attempts==verified==5748 and len(drive)==2420 and starts==8 and stops==4 and output==original,
                "incomplete fixed read-only wire trace")
    raw=bytearray()
    byte=lambda bits: sum(bit<<(7-i) for i,bit in enumerate(bits))
    for record in range(4):
        start=record*605
        cli.require([byte(drive[start+i:start+i+8]) for i in (0,9,19)]==[0xa0,0x40 if record%2 else 0,0xa1],"wire address/pointer mismatch")
        cli.require(all(sampled[start+i]==0 for i in (8,17,27)),"wire slave ACK mismatch")
        for index in range(64):
            offset=start+28+index*9
            bits=sampled[offset:offset+8]
            cli.require(all(bit in (0,1) for bit in bits),"missing physical SDA sample")
            raw.append(byte(bits))
            cli.require(drive[offset+8]==int(index==63),"master ACK/NACK mismatch")
    cli.require(raw==bytes.fromhex(worker["capture"]["raw_hex"]),"physical SDA trace disagrees with BCB bytes")
    return dict(edge_writes=attempts,rising_clocks=len(drive),starts=starts,stops=stops,bytes_reconstructed=len(raw))


def main():
    cli.require(Path.cwd()==ROOT and sys.flags.isolated and sys.flags.no_site and sys.dont_write_bytecode,"isolated root required")
    store=cli.Store(ROOT); out=store.checked(ROOT/".cache/p34-entry-audit2/result.json")
    cli.require(not out.exists(),"preserve audit")
    files=[]; manifests=[]
    for name in AREAS:
        area=store.checked(ROOT/".cache"/name)
        cli.require(area.is_dir(),"missing selected evidence: "+name)
        for p in area.rglob("*"):
            store.checked(p)
            if p.is_file(): files.append(cli.record(p))
        manifest=area/("plan.json" if (area/"plan.json").exists() else "result.json")
        value=store.read(manifest)
        for item in value.get("inputs",[]):
            p=Path(item["path"]); snap=area/"source"/p.relative_to(ROOT)
            check=snap if snap.exists() else p
            data=check.read_bytes()
            cli.require(len(data)==item["bytes"] and hashlib.sha256(data).hexdigest()==item["sha256"],"snapshot/input drift")
        manifests.append(cli.record(manifest))
        if (area/"parent.json").exists():
            parent=store.read(area/"parent.json")
            cli.require(parent["exit"]==0 and not parent["timeout"],"worker did not close successfully")
            cli.require(parent["after_history"]==value["before_history"],"external native history changed")
    traces=[]
    for name,kind in (("p34-entry-wfi1","wfi"),("p34-entry-wfi-retained1","retained"),
                      ("p34-entry-owner1","owners"),("p34-host-bcb1","bcb")):
        area=ROOT/".cache"/name; worker=store.read(area/"worker.json")
        events=[json.loads(line) for line in (area/"events.jsonl").read_text().splitlines()]
        cli.require(worker["close_returned"] and worker["dap"]["tar_restored"] and worker["dap"]["csw_restored"],"close/restore missing")
        rows=trace_writes((area/"sdk.log").read_text(),worker,events,kind)
        item=dict(area=name,logged_data_writes=len(rows),cpu_write_calls=0)
        if kind=="bcb": item["wire"]=wire(events,worker)
        traces.append(item)
    area=ROOT/".cache/p34-host-bcb1"; worker=store.read(area/"worker.json")
    events=[json.loads(line) for line in (area/"events.jsonl").read_text().splitlines()]
    log=(area/"sdk.log").read_text()
    for mutation in ("CPU_WriteMem(4 bytes @ 0x20060000)",
                     "JLINK_CORESIGHT_WriteAPDPReg(AP reg 0x01, 0xE000ED0C)\nJLINK_CORESIGHT_WriteAPDPReg(AP reg 0x03, 0x05FA0004)",
                     "JLINK_CORESIGHT_WriteAPDPReg(AP reg 0x01, 0x40020418)\nJLINK_CORESIGHT_WriteAPDPReg(AP reg 0x03, 0x00000100)"):
        try: trace_writes(log+"\n"+mutation,worker,events,"bcb")
        except ValueError: pass
        else: raise ValueError("unsafe trace mutation accepted")
    passive=ROOT/".cache/p34-native-entry-facts2"
    old_audit.writes_in_scope((passive/"sdk.log").read_text(),"state",store.read(passive/"worker.json")["dap"])
    app=(ROOT/".cache/p34-native-image1/app-readback.bin").read_bytes()
    selected=worker["capture"]["selected"]
    cli.require(selected["state"]==4 and selected["copy_phase"]==selected["resume_block"]==0 and
                selected["cur_vcode"]==struct.unpack_from("<I",app,0x408)[0] and
                selected["cand_len"]==len(app) and selected["cand_crc32"]==zlib.crc32(app),"BCB/current App mismatch")
    selected_tests=[]
    for name in ("p34-native-probe-test11","p34-entry-control-test3","p34-entry-owner-test2","p34-host-bcb-test2"):
        value=store.read(ROOT/".cache"/name/"result.json")
        for item in value["inputs"]: cli.require(cli.record(Path(item["path"]))==item,"current tested source drift")
        selected_tests.append(dict(area=name,tests=value["tests"]))
    source_files=[]
    for pattern in ("p34_entry_audit.py","p34_halted_probe.py","p34_host_bcb.py","p34_rendezvous.py"):
        p=ROOT/"Tools/ota"/pattern; text=p.read_text(); ast.parse(text)
        cli.require(text.isascii(),"non-ASCII Python source")
        source_files.append(cli.record(p))
    store.write(out,dict(result="ENTRY_AND_BCB_AUDIT_PASS",files=files,manifests=manifests,traces=traces,
        selected_tests=selected_tests,negative_write_checks=3,current_app_bcb_consistent=True,
        native_history_changed=False,external_write_authority="C:/Users/SU/AppData/Roaming/SEGGER history/config only; no cleanup",
        logical_dp_retention_across_close_proven=False,proof_scope="logged calls, readback, source bindings; not all electrical transients",
        source_files=source_files,device_execute_ready=False))
    print("ENTRY_AND_BCB_AUDIT_PASS",len(files),"files; physical SDA bytes reconstructed; BCB/App consistent")


if __name__=="__main__": raise SystemExit(main())
