"""Bounded read-only SDK rotation qualification; no Flash/EEPROM writer."""
import argparse
import contextlib
import ctypes
import json
import os
from pathlib import Path
import re
import sys
import time

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT/'Tools/ota'))
import p34_recovery_preflight as prior
from recovery_confirm.log_segments import Segments, rotation_events, checked_records, checked_lines

cli,host,base = prior.cli,prior.host,prior.base
SELF = Path(__file__).resolve()
SOURCES = list(dict.fromkeys([*prior.SOURCES,SELF,ROOT/'Tools/ota/recovery_confirm/log_segments.py',
    ROOT/'tests/boot/test_p34_recovery_log_probe.py',ROOT/'tests/boot/test_p34_recovery_preflight.py',
    ROOT/'.cache/p34-recovery-preflight1/audit.json',ROOT/'.cache/p34-recovery-preflight1/envelope.bin']))
LOGS = tuple('sdk-%03d.log'%i for i in range(6))
KEYS = ('HOME','USERPROFILE','APPDATA','LOCALAPPDATA','TEMP','TMP','TMPDIR','XDG_CACHE_HOME',
        'XDG_CONFIG_HOME','XDG_DATA_HOME','PYTHONUSERBASE','PYTHONPYCACHEPREFIX','CCACHE_DIR','SCCACHE_DIR')


def preflight(store,out):
    cli.require(not out.exists(),'preserve log qualification evidence')
    for name in (*prior.FILES,*LOGS): store.checked(out/name)
    for path in SOURCES: store.checked(out/'source'/path.relative_to(ROOT))
    for key in KEYS: store.checked(out/'host'/key.lower())


def rotate_dap(dap,path,emit,budget,clock=time.monotonic):
    started=clock()
    def state():
        values=[]
        for index,ap in ((1,0),(0,1),(1,1)):
            cli.require(budget()>=5,'no log-boundary native-call allowance')
            values.append(dap._read_reg(index,ap))
        cli.require(values[0]&0xf0000000==0xf0000000 and values[0]&0xb2==0 and
                    values[1]==dap.word_csw,'unqualified DP/AP at log boundary')
        return values
    before=state()
    cli.require(budget()>=5,'no log-switch native-call allowance')
    dap._call('JLINKARM_SetLogFile',str(path).encode('ascii'))
    after=state()
    ended=clock()
    cli.require(before==after and ended>=started,'DP/AP state or clock changed across log switch')
    emit('sdk-log-state',before=before,after=after,started=started,ended=ended)


def worker(store,out):
    deadline = time.monotonic()+330
    cli.require(base.in_job(),'owned worker required')
    plan = store.read(out/'plan.json')
    cli.require(plan['out']==str(out) and plan['inputs']==[cli.record(p) for p in SOURCES],'log probe source drift')
    cli.require(plan['native_history_approved']==str(base.HISTORY) and
                cli.record(base.JLINK/'JLink_x64.dll')['sha256']==base.DLL_SHA,'native identity/scope drift')
    result = dict(result='FAILED',target_data_writes=0,write_admitted=False,reset_performed=False)
    dap = observer = logs = None
    streams = {}
    count = 0
    with (out/'events.jsonl').open('x',encoding='utf-8') as events,(out/'callbacks.log').open('xb') as callbacks:
        def emit(event,**fields):
            events.write(json.dumps(dict(time=cli.now(),event=event,**fields))+'\n');events.flush()
        def save(name,offset,raw):
            nonlocal count
            if name=='header': return
            if name not in streams: streams[name]=(out/(name+'.bin')).open('xb')
            stream=streams[name]
            cli.require(stream.tell()==offset,'archive offset drift')
            stream.write(raw);stream.flush()
            count += 1
            if count % 128 == 0: logs.rotate()
        try:
            cli.require(not base.native_presence()['debugger_processes'],'competing debugger')
            with os.add_dll_directory(str(base.JLINK)):
                sdk=base.guarded(ctypes.CDLL,str(base.JLINK/'JLink_x64.dll'))
                dap=base.Dap(sdk,out/LOGS[0],out/'project.jlink',callbacks)
                observer=base.Observation(dap,emit,seconds=deadline-time.monotonic())
                observer.connect()
                port=prior.Words(dap,emit,reads=prior.READS,write_allowed=lambda a,v:False,
                                 seconds=prior.reader_seconds(deadline))
                port.budget.end=min(port.budget.end,deadline)
                logs=Segments([out/name for name in LOGS],
                    lambda path:rotate_dap(dap,path,emit,port.check),cli.record,emit)
                data=prior.acquire(port,(ROOT/'.cache/p34-native-acquire1/boot-readback.bin').read_bytes(),
                                   (ROOT/'.cache/p34-native-image1/app-readback.bin').read_bytes(),save)
                cli.require(port.writes==0 and count==670,'read extent/write mismatch')
                cli.require(data['envelope']==(ROOT/'.cache/p34-recovery-preflight1/envelope.bin').read_bytes(),
                            'envelope differs from preceding read-only capture')
                for stream in streams.values(): stream.flush();os.fsync(stream.fileno())
                result.update(result='SEGMENTED_READ_CAPTURED_NOT_WRITE_ADMITTED',
                    boot=cli.record(out/'boot.bin'),envelope=cli.record(out/'envelope.bin'),
                    collateral=store.raw(out/'collateral.bin',data['collateral']),before=data['before'],
                    after=data['after'],reset_seen=data['reset_seen'])
        except BaseException as error:
            result['error']=type(error).__name__+': '+str(error)
        finally:
            for name,stream in streams.items():
                try: stream.close()
                except BaseException as error:
                    result['result']='FAILED'
                    result.setdefault('archive_close_errors',[]).append(dict(name=name,error=str(error)))
            try:
                if observer: observer.close()
                elif dap: dap.close()
            except BaseException as error:
                result.update(result='FAILED',close_error=type(error).__name__+': '+str(error))
            result['close_returned']=bool(dap and dap.close_returned)
            if dap: result['dap']=dap.metadata
            if logs:
                result['rotation_index']=logs.index
                result['sealed_before_close']=list(logs.sealed)
                try: result['logs']=logs.finish(result['close_returned'])
                except BaseException as error:
                    result.update(result='FAILED',log_error=type(error).__name__+': '+str(error))
            store.write(out/'worker.json',result)
    print(json.dumps(result))
    return 0 if result['result']=='SEGMENTED_READ_CAPTURED_NOT_WRITE_ADMITTED' and result['close_returned'] else 1


def audit(store,out):
    import p34_nor_audit as parser
    plan,worker,parent=(store.read(out/(name+'.json')) for name in ('plan','worker','parent'))
    cli.require(plan['inputs']==[cli.record(p) for p in SOURCES],'audit source drift')
    cli.require(parent['exit']==0 and not parent['timeout'] and parent['after_history']==plan['before_history'] and
        worker['result']=='SEGMENTED_READ_CAPTURED_NOT_WRITE_ADMITTED' and worker['close_returned'] and
        not worker.get('archive_close_errors') and worker['reset_seen'] is False,'normal closure required')
    for item in plan['inputs']:
        snapshot=cli.record(out/'source'/Path(item['path']).relative_to(ROOT))
        cli.require((snapshot['bytes'],snapshot['sha256'])==(item['bytes'],item['sha256']),'snapshot drift')
    paths=[out/name for name in LOGS]
    checked_records(paths,worker['logs'],cli.record)
    rotation_events(parser.events(out/'events.jsonl'))
    states=[row for row in parser.events(out/'events.jsonl') if row['event']=='sdk-log-state']
    cli.require(len(states)==5 and all(row['before']==row['after'] and row['ended']>=row['started']
        and row['before'][0]&0xf0000000==0xf0000000 and row['before'][0]&0xb2==0 and
        row['before'][1]==(worker['dap']['ap_csw']&~0x37)|0x12 for row in states),'rotation state mismatch')
    names=(*LOGS,'events.jsonl','plan.json','worker.json','parent.json','boot.bin','envelope.bin','collateral.bin')
    bound=[cli.record(out/name) for name in names]
    boot=(out/'boot.bin').read_bytes();envelope=(out/'envelope.bin').read_bytes()
    cli.require(boot==(ROOT/'.cache/p34-native-acquire1/boot-readback.bin').read_bytes() and
        envelope==(ROOT/'.cache/p34-recovery-preflight1/envelope.bin').read_bytes() and
        envelope[619580:]==(out/'collateral.bin').read_bytes(),'original/collateral image drift')
    with contextlib.ExitStack() as stack:
        streams=[stack.enter_context(path.open(encoding='utf-8')) for path in paths]
        trace=prior.scan_trace(checked_lines(streams,parser.events(out/'events.jsonl')),parser.events(out/'events.jsonl'),
                               worker['dap'],boot,envelope)
    cli.require(all(v==[worker['before'][a],worker['after'][a]] for a,v in trace['meta_samples'].items()),'metadata mismatch')
    cli.require(bound==[cli.record(item['path']) for item in bound],'audit input drift')
    store.write(out/'audit.json',dict(result='SEGMENTED_SDK_READ_AUDIT_PASS',trace=trace,inputs=bound,
        source=cli.record(SELF),target_data_writes=0,mutation_logging_qualified=False,
        physical_gpio_timing_qualified=False,historical_nor_sdk_gap_repaired=False))


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action',choices=('selftest','capture','worker','audit'))
    parser.add_argument('--output-dir',type=Path,required=True)
    parser.add_argument('--tests',type=Path)
    parser.add_argument('--native-history-approved',type=Path)
    args=parser.parse_args()
    cli.require(Path.cwd()==ROOT and sys.flags.isolated and sys.flags.no_site and sys.dont_write_bytecode,'isolated root required')
    store=cli.Store(ROOT);out=store.checked(args.output_dir)
    if args.action=='worker': return worker(store,out)
    if args.action=='audit': audit(store,out);print('SEGMENTED_SDK_READ_AUDIT_PASS');return 0
    preflight(store,out)
    inputs=[cli.record(p) for p in SOURCES]
    if args.action=='capture':
        tests=store.read(args.tests)
        cli.require(tests['result']=='SEGMENTED_LOG_HOST_PASS' and tests['inputs']==inputs,'source-bound tests required')
        cli.require(args.native_history_approved==base.HISTORY,'exact native history permission required')
        before=base.history(store)
    env=host.environment(store,out)
    for p in SOURCES: store.raw(out/'source'/p.relative_to(ROOT),p.read_bytes())
    if args.action=='selftest':
        env['P34_TEST_OUT']=str(out)
        log=host.command(store,out,'tests',[sys.executable,'-I','-S','-B','-X','utf8',
            ROOT/'tests/boot/test_p34_recovery_log_probe.py','-v'],env,120)
        count=re.search(rb'Ran (\d+) tests? in .*\r?\n\r?\nOK\b',log)
        cli.require(count and inputs==[cli.record(p) for p in SOURCES],'test/source drift')
        store.write(out/'result.json',dict(result='SEGMENTED_LOG_HOST_PASS',tests=int(count[1]),inputs=inputs,hardware=False))
        print('SEGMENTED_LOG_HOST_PASS tests='+str(int(count[1])));return 0
    store.write(out/'plan.json',dict(out=str(out),inputs=inputs,tests=cli.record(args.tests),
        native_history_approved=str(base.HISTORY),before_history=before,parent_seconds=360,worker_seconds=330,
        scope='Read-only log rotation discriminator, 6 raw logs, 5 switches; no halt/reset/target data writes'))
    result=base.owned_run(store,out,[SELF,'worker','--output-dir',out],env,timeout=360)
    result['after_history']=base.history(store);result['presence_after']=base.native_presence()
    store.write(out/'parent.json',result);print(json.dumps(result))
    return 0 if result['exit']==0 and not result['timeout'] else 1


if __name__=='__main__': raise SystemExit(main())
