"""Source-bound successor for the closed third-sector finish, not a replay CLI."""
import argparse
import ctypes
import json
import os
from pathlib import Path
import re
import shutil
import sys
import time

ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT/'Tools/ota'))
import p34_flash_finish_sector as finished
import p34_install_recovery as prior
from recovery_confirm.install_continue import Install

base,cli,host=prior.base,prior.cli,prior.host
SELF=Path(__file__).resolve()
FINISH=ROOT/'.cache/p34-flash-finish1'
LOGS,FILES,ASSETS=prior.LOGS,prior.FILES,prior.ASSETS
ADDITIONS=('Tools/ota/recovery_confirm/flash_continue.py','Tools/ota/recovery_confirm/install_continue.py',
           'Tools/ota/p34_install_continue.py','Tools/ota/p34_install_strict_audit.py',
           'tests/boot/test_p34_install_continue.py','tests/boot/test_p34_install_strict_audit.py')
SCOPE=dict(prior.SCOPE,entry='finish1 halted context; R2 first3 sectors; original remaining envelope',
           flash_first_sector=3,flash_last_sector=302,completed_prefix_replay=False)


def sources(store):
    inputs=finished.sources(store)
    worker,parent,plan=(store.read(FINISH/(n+'.json')) for n in ('worker','parent','plan'))
    cli.require(worker['result']=='THIRD_SECTOR_FINISHED_HALTED_CLOSED' and worker['close_returned'] and
                worker['sources_unchanged_after_close'] and parent['exit']==0 and not parent['timeout'] and
                not parent['presence_after']['debugger_processes'] and parent['after_history']==plan['before_history'],
                'actual closed third-sector finish required')
    cli.require(worker['finish']['trace']['target_writes']==750 and
                worker['finish']['sector']['complete'] and worker['finish']['sector']['erase_commands']==0 and
                worker['final_trace']['native_close']==1 and not worker['reset_performed'],'finish scope differs')
    for item in plan['inputs']+worker['logs']:
        cli.require(finished.prior.audit.record(store.checked(item['path']))==item,'finish dependency drift')
    return list(dict.fromkeys([*inputs,*(ROOT/n for n in ADDITIONS),
        *(FINISH/n for n in ('worker.json','parent.json','plan.json','events.jsonl','affected.bin',*finished.LOGS))]))


def execute(dap,observation,persist,initial_rows,paths,record,remaining,archives,assets,function,
            *,retained_entry,clock=time.monotonic,guard=base.guarded,body_factory=Install):
    result=dict(result='FAILED',close_returned=False,historical_sdk_audit_passed=False)
    logs=body=None
    normal=False
    restore=None
    original_close=observation.close
    def close():
        if normal or observation.closed:return original_close()
        dap.power_changed=False
        dap.metadata['dp_restore_deferred_for_halt']=True
        try:
            if dap.ready:dap.metadata['retained_dp_ctrlstat']=dap._power_ready()
        finally:original_close()
    observation.close=close
    try:
        observation.connect()
        cli.require(dap.original_csw==dap.word_csw==0x23000052,'native word profile differs')
        acquisition,restore=prior.setup.dp_plan(dap.metadata)
        logs=prior.OnlineLog(dap,prior.SealedGate(paths,dap.metadata,record),persist,remaining,
                             initial_rows=initial_rows,clock=clock)
        logs.switch(read_allowed=lambda _:False,expected_stores=[],expected_dp_writes=acquisition)
        body=body_factory(dap,observation,logs,remaining,archives.write,assets,function,
                          retained_entry=retained_entry,clock=clock,guard=guard)
        result['body']=body.run()
        cli.require(result['body']['result']=='READY_FOR_FINAL_NATIVE_CLOSE','incomplete continuation')
        result['archives']=guard(archives.finish,seconds=min(60,remaining()-90))
        logs.prepare_close()
        normal=True
    except BaseException as error:result['error']=type(error).__name__+': '+str(error)
    finally:
        try:observation.close()
        except BaseException as error:normal=False;result['close_error']=type(error).__name__+': '+str(error)
        try:archives.close()
        except BaseException as error:normal=False;result['archive_close_error']=type(error).__name__+': '+str(error)
        result.update(close_returned=dap.close_returned,dap=dict(dap.metadata),native_ap_error=dap.sdk.error)
        if body:
            result.update(phase=body.phase,app_may_have_changed=True,
                flash_sectors_audited=len(body.flash_sequence.completed) if body.flash_sequence else 0,
                eeprom_pages_attempted=body.eeprom_wire.page_index if body.eeprom_wire else 0,
                reset_attempted=bool(body.exit_port and body.exit_port.reset_attempted),
                release_attempted=bool(body.exit_port and body.exit_port.release_attempted),
                release_returned=body.released,component_results=body.results)
        if normal:
            try:
                trace=guard(lambda:logs.finish(read_allowed=lambda _:False,expected_stores=[],
                    expected_dp_writes=restore),seconds=min(60,remaining()))
                preserved_dp=not dap.power_changed and dap.metadata['original_dp']&0xf0000000==0xf0000000
                cli.require(dap.close_returned and dap.metadata['tar_restored'] and dap.metadata['csw_restored'] and
                            (dap.metadata['dp_restored'] or preserved_dp),'final AP/native restoration missing')
                result.update(result='R2_INSTALLED_ORIGINAL_BOOT_CLOSED',final_trace=trace,
                    logs=list(logs.gate.records),runtime_health_observed=True,
                    original_dp_preserved_without_write=preserved_dp)
            except BaseException as error:result['final_audit_error']=type(error).__name__+': '+str(error)
        if logs:result.update(log_mode=logs.mode,log_error=logs.error,sealed=list(logs.gate.records))
    return result


def worker(store,out):
    deadline=time.monotonic()+prior.WORKER_SECONDS
    cli.require(base.in_job(),'owned continuation worker required')
    plan=store.read(out/'plan.json')
    cli.require(plan['out']==str(out) and plan['inputs']==[finished.prior.audit.record(p) for p in sources(store)],
                'continuation source drift')
    cli.require(plan['native_history_approved']==str(base.HISTORY) and plan['scope']==SCOPE,'exact scope required')
    cli.require(cli.record(base.JLINK/'JLink_x64.dll')['sha256']==base.DLL_SHA,'native DLL drift')
    assets={name:path.read_bytes() for name,path in ASSETS.items()}
    retained=prior.failed_entry.predecessor(store)
    page=store.read(ROOT/'.cache/p34-confirm-page2/result.json')
    cli.require(cli.record(page['dll']['path'])==page['dll'],'original C oracle drift')
    dll,function=prior.confirm.bind(Path(page['dll']['path']))
    archives=prior.Archives(store,out)
    dap=observation=None
    result=dict(result='FAILED',close_returned=False)
    with (out/'events.jsonl').open('x',encoding='utf-8') as events,(out/'callbacks.log').open('xb') as callbacks:
        initial=[]
        def persist(event,**fields):
            events.write(json.dumps(dict(time=cli.now(),event=event,**fields))+'\n');events.flush()
            if event in ('online-log-sealed','recovery-install-phase'):os.fsync(events.fileno())
            if event in ('flash-sequence-sector-audited','recovery-install-phase',
                         'nor-region-captured-audited','eeprom-operation-audited'):
                print(json.dumps(dict(time=cli.now(),event=event,**fields)),flush=True)
        def collect(event,**fields):persist(event,**fields);initial.append(dict(event=event,**fields))
        try:
            cli.require(not base.native_presence()['debugger_processes'],'competing debugger')
            cli.require(deadline-time.monotonic()>prior.WORKER_SECONDS-60,'initial setup allowance exhausted')
            with os.add_dll_directory(str(base.JLINK)):
                sdk=base.guarded(ctypes.CDLL,str(base.JLINK/'JLink_x64.dll'))
                dap=base.Dap(sdk,out/LOGS[0],out/'project.jlink',callbacks)
                dap.sdk=prior.JournalSDK(sdk,collect)
                observation=base.Observation(dap,collect,seconds=600)
                result=execute(dap,observation,persist,initial,[out/n for n in LOGS],cli.record,
                    lambda:deadline-time.monotonic(),archives,assets,function,retained_entry=retained)
        except BaseException as error:
            result['outer_error']=type(error).__name__+': '+str(error)
            if observation is None and dap is not None and dap._opened:
                try:dap.close()
                except BaseException as close:result['outer_close_error']=str(close)
            try:archives.close()
            except BaseException as close:result['outer_archive_close_error']=str(close)
        if dap:result.update(close_returned=dap.close_returned,dap=dict(dap.metadata))
        try:result['sources_unchanged_after_close']=plan['inputs']==[finished.prior.audit.record(p) for p in sources(store)]
        except BaseException as error:result.update(sources_unchanged_after_close=False,source_check_error=str(error))
        if not result['sources_unchanged_after_close']:result['result']='FAILED'
        store.write(out/'worker.json',prior.json_result(result))
    print(json.dumps(dict(result=result['result'],phase=result.get('phase'),close_returned=result['close_returned'])),flush=True)
    return 0 if result['result']=='R2_INSTALLED_ORIGINAL_BOOT_CLOSED' else 1


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action',choices=('selftest','execute','worker'))
    parser.add_argument('--output-dir',type=Path,required=True)
    parser.add_argument('--tests',type=Path)
    parser.add_argument('--native-history-approved',type=Path)
    args=parser.parse_args()
    cli.require(Path.cwd()==ROOT and sys.flags.isolated and sys.flags.no_site and sys.dont_write_bytecode,'isolated root required')
    store=cli.Store(ROOT);out=store.checked(args.output_dir)
    if args.action=='worker':return worker(store,out)
    inputs=sources(store);prior.preflight(store,out,inputs)
    records=[finished.prior.audit.record(p) for p in inputs]
    if args.action=='execute':
        tests=store.read(args.tests)
        cli.require(tests['result']=='INSTALL_CONTINUATION_HOST_PASS' and tests['inputs']==records,'current tests required')
        cli.require(args.native_history_approved==base.HISTORY,'exact native history authority')
        cli.require(shutil.disk_usage(ROOT).free>=20*1024**3,'20GiB evidence margin required')
        before=base.history(store)
    env=host.environment(store,out)
    for source in inputs:store.raw(out/'source'/source.relative_to(ROOT),source.read_bytes())
    if args.action=='selftest':
        env['P34_TEST_OUT']=str(out)
        env['P34_CONFIRM_DLL']=store.read(ROOT/'.cache/p34-confirm-page2/result.json')['dll']['path']
        log=host.command(store,out,'tests',[sys.executable,'-I','-S','-B','-X','utf8',
            ROOT/'tests/boot/test_p34_install_continue.py','-v'],env,180)
        count=re.search(rb'Ran (\d+) tests? in .*\r?\n\r?\nOK\b',log)
        cli.require(count and records==[finished.prior.audit.record(p) for p in inputs],'test/source drift')
        store.write(out/'result.json',dict(result='INSTALL_CONTINUATION_HOST_PASS',tests=int(count[1]),
                                         inputs=records,hardware=False))
        print('INSTALL_CONTINUATION_HOST_PASS',int(count[1]));return 0
    store.write(out/'plan.json',dict(out=str(out),inputs=records,tests=cli.record(args.tests),scope=SCOPE,
        before_history=before,native_history_approved=str(base.HISTORY),worker_seconds=prior.WORKER_SECONDS,
        parent_seconds=prior.PARENT_SECONDS,physical_timing_bound_qualified=False,historical_sdk_audit_passed=False))
    result=base.owned_run(store,out,[SELF,'worker','--output-dir',out],env,timeout=prior.PARENT_SECONDS)
    result.update(after_history=base.history(store),presence_after=base.native_presence())
    store.write(out/'parent.json',result);print(json.dumps(result))
    return 0 if result['exit']==0 and not result['timeout'] else 1


if __name__=='__main__':raise SystemExit(main())
