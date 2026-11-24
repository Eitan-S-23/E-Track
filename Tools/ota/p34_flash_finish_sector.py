"""One exact no-erase completion of settled sector2, retaining the halted CPU."""
import argparse
import ctypes
import json
import os
from pathlib import Path
import re
import sys
import time

ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT/'Tools/ota'))
import p34_flash_settlement as prior
from recovery_confirm.flash_remainder import PartialSector

base,cli,host=prior.base,prior.cli,prior.host
SELF=Path(__file__).resolve()
SETTLED=ROOT/'.cache/p34-flash-settlement1'
LOGS=tuple('sdk-%03d.log'%i for i in range(6))
FILES=tuple(dict.fromkeys([*prior.FILES,*LOGS]))


def complete_sector(dap,logs,envelope,image,remaining,*,clock=time.monotonic,sleep=time.sleep,guard=base.guarded):
    if logs.dap is not dap or logs.gate.index!=4 or len(logs.gate.paths)!=6:
        raise ValueError('fresh sealed settlement and exact finish log positions required')
    active=True;port=None;last=None
    def check(index=4):
        nonlocal last
        left=remaining()
        if (not active or not 60<left<=180 or last is not None and left>last or
                logs.gate.index!=index or not logs.target_allowed()):
            raise ValueError('partial writer owner/close reserve lost')
        last=left
        return left-60
    def owner():check();return True
    def native(function,*args,seconds):
        value=guard(function,*args,seconds=min(seconds,check(),port.words.budget.left()))
        check();port.words.check()
        return value
    try:
        check()
        port=PartialSector(dap,image,envelope,owner,logs.emit,seconds=min(90,check()),
                           clock=clock,sleep=sleep,guard=native)
        result=port.run()
        check()
        if (not result['complete'] or result['erase_commands'] or result['preserved_words']!=138 or
                result['programmed_words']!=512 or port.position!=750):
            raise ValueError('incomplete third-sector remainder')
        trace=guard(lambda:logs.switch(read_allowed=lambda a:a in port.words.reads,expected_stores=port.plan),
                    seconds=min(30,check(),port.words.budget.left()))
        check(5)
        if trace['target_writes']!=750 or trace['native_close'] or trace['log_file_closed']!=1:
            raise ValueError('third-sector audit mismatch')
        return dict(result='THIRD_SECTOR_FINISHED_AUDITED',sector=result,trace=trace,reset_allowed=False)
    finally:
        active=False


def sources(store):
    inputs=prior.sources(store)
    worker,parent,plan=(store.read(SETTLED/(n+'.json')) for n in ('worker','parent','plan'))
    cli.require(worker['result']=='PARTIAL_FLASH_SETTLED_CLOSED_NOT_WRITE_ADMITTED' and worker['close_returned'] and
                worker['sources_unchanged_after_close'] and parent['exit']==0 and not parent['timeout'] and
                parent['after_history']==plan['before_history'],'closed actual settlement required')
    cli.require((SETTLED/'affected.bin').read_bytes()==prior.EXPECTED.read_bytes()[:6144],
                'physical affected region no longer matches partial proof')
    for record in [worker['affected'],*worker['logs'],*plan['inputs']]:
        cli.require(prior.audit.record(store.checked(record['path']))==record,'settlement evidence/source drift')
    return list(dict.fromkeys([*inputs,SELF,ROOT/'Tools/ota/recovery_confirm/flash_remainder.py',
        ROOT/'tests/boot/test_p34_flash_finish_sector.py',ROOT/'tests/boot/test_p34_flash_remainder.py',
        ROOT/'.cache/p34-flash-remainder-tests1/result.json',
        *(SETTLED/n for n in ('worker.json','parent.json','plan.json','affected.bin',*prior.LOGS))]))


def worker(store,out):
    deadline=time.monotonic()+180
    cli.require(base.in_job(),'owned finish worker required')
    plan=store.read(out/'plan.json')
    cli.require(plan['inputs']==[cli.record(p) for p in sources(store)] and plan['out']==str(out),'finish source drift')
    cli.require(plan['native_history_approved']==str(base.HISTORY) and
                cli.record(base.JLINK/'JLink_x64.dll')['sha256']==base.DLL_SHA,'native identity/scope mismatch')
    envelope=prior.EXPECTED.read_bytes()
    image=prior.prior.ASSETS['image'].read_bytes()
    context=store.read(prior.AREA/'worker.json')['component_results']['entry']['context']
    result=dict(result='FAILED',close_returned=False,programming_attempted=False,reset_performed=False)
    observer=dap=logs=None;normal=False
    with (out/'events.jsonl').open('x',encoding='utf-8') as events,(out/'callbacks.log').open('xb') as callbacks:
        initial=[]
        def persist(event,**fields):
            events.write(json.dumps(dict(time=cli.now(),event=event,**fields))+'\n');events.flush()
        def collect(event,**fields):persist(event,**fields);initial.append(dict(event=event,**fields))
        try:
            cli.require(deadline-time.monotonic()>150 and not base.native_presence()['debugger_processes'],'finish setup allowance/owner')
            with os.add_dll_directory(str(base.JLINK)):
                sdk=base.guarded(ctypes.CDLL,str(base.JLINK/'JLink_x64.dll'))
                dap=base.Dap(sdk,out/LOGS[0],out/'project.jlink',callbacks)
                dap.sdk=prior.JournalSDK(sdk,collect)
                observer=prior.RetainedObservation(dap,collect,seconds=120)
                observer.connect()
                logs=prior.OnlineLog(dap,prior.SealedGate([out/n for n in LOGS],dap.metadata,cli.record),persist,
                                    lambda:deadline-time.monotonic(),initial_rows=initial)
                logs.switch(read_allowed=lambda _:False,expected_stores=(),
                            expected_dp_writes=prior.prior.setup.dp_plan(dap.metadata)[0])
                observer.emit=logs.emit
                port=prior.Words(dap,logs.emit,reads=prior.READS,write_allowed=lambda a,v:False,
                                 seconds=min(90,deadline-time.monotonic()-60))
                control=prior.Control(dap,observer,logs.emit,envelope[0x400:0x460],retained=True)
                def seal(reads,stores,bind):
                    return logs.switch(read_allowed=lambda a:a in reads,expected_stores=stores,bind_words=bind)
                result['settlement']=prior.capture(port,control,envelope[:6144],context,seal,
                    lambda raw:store.raw(out/'affected.bin',raw),bounded=prior.Boundary(port,lambda:deadline-time.monotonic()))
                result['programming_attempted']=True
                result['finish']=complete_sector(dap,logs,envelope,image,lambda:deadline-time.monotonic())
                observer._check();logs.prepare_close();normal=True
        except BaseException as error:result['error']=type(error).__name__+': '+str(error)
        finally:
            try:
                if observer:observer.close()
                elif dap:dap.close()
            except BaseException as error:normal=False;result['close_error']=type(error).__name__+': '+str(error)
            result['close_returned']=bool(dap and dap.close_returned)
            if dap:result['dap']=dict(dap.metadata)
            if normal:
                try:
                    logs.gate.cursor.metadata=dict(dap.metadata,original_dp=0xf0000040)
                    result['final_trace']=logs.finish(read_allowed=lambda _:False,expected_stores=())
                    result.update(result='THIRD_SECTOR_FINISHED_HALTED_CLOSED',logs=logs.gate.records)
                except BaseException as error:result['audit_error']=type(error).__name__+': '+str(error)
            if logs:result['sealed']=list(logs.gate.records)
            try:result['sources_unchanged_after_close']=plan['inputs']==[cli.record(p) for p in sources(store)]
            except BaseException as error:result['sources_unchanged_after_close']=False;result['source_error']=str(error)
            if not result['sources_unchanged_after_close']:result['result']='FAILED'
            store.write(out/'worker.json',result)
    print(json.dumps(result));return 0 if result['result']=='THIRD_SECTOR_FINISHED_HALTED_CLOSED' else 1


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action',choices=('selftest','finish','worker'))
    parser.add_argument('--output-dir',type=Path,required=True)
    parser.add_argument('--tests',type=Path)
    parser.add_argument('--native-history-approved',type=Path)
    args=parser.parse_args()
    cli.require(Path.cwd()==ROOT and sys.flags.isolated and sys.flags.no_site and sys.dont_write_bytecode,'isolated root required')
    store=cli.Store(ROOT);out=store.checked(args.output_dir)
    if args.action=='worker':return worker(store,out)
    inputs=sources(store);prior.preflight(store,out,inputs)
    for n in FILES:store.checked(out/n)
    records=[cli.record(p) for p in inputs]
    if args.action=='finish':
        tests=store.read(args.tests)
        cli.require(tests['result']=='FLASH_FINISH_HOST_PASS' and tests['inputs']==records,'bound finish tests required')
        cli.require(args.native_history_approved==base.HISTORY,'exact native history permission')
        before=base.history(store)
    env=host.environment(store,out)
    for p in inputs:store.raw(out/'source'/p.relative_to(ROOT),p.read_bytes())
    if args.action=='selftest':
        env['P34_TEST_OUT']=str(out)
        log=host.command(store,out,'tests',[sys.executable,'-I','-S','-B','-X','utf8',ROOT/'tests/boot/test_p34_flash_finish_sector.py','-v'],env,120)
        count=re.search(rb'Ran (\d+) tests',log)
        cli.require(count and records==[cli.record(p) for p in inputs],'finish test/source drift')
        store.write(out/'result.json',dict(result='FLASH_FINISH_HOST_PASS',tests=int(count[1]),inputs=records,hardware=False))
        print('FLASH_FINISH_HOST_PASS',int(count[1]));return 0
    store.write(out/'plan.json',dict(out=str(out),inputs=records,tests=cli.record(args.tests),before_history=before,
        native_history_approved=str(base.HISTORY),scope='fresh settled6KiB then750 exact stores;374 new words08011228..08011800;no erase/prefix replay/EEPROM/NOR/reset/resume',
        worker_seconds=180,parent_seconds=240))
    result=base.owned_run(store,out,[SELF,'worker','--output-dir',out],env,timeout=240)
    result.update(after_history=base.history(store),presence_after=base.native_presence())
    store.write(out/'parent.json',result);print(json.dumps(result));return 0 if result['exit']==0 and not result['timeout'] else 1


if __name__=='__main__':raise SystemExit(main())
