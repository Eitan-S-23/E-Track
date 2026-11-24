"""Fresh-WFI / single EEPROM read / unchanged-App exit qualification candidate."""
import argparse
import ctypes
import hashlib
import json
import os
from pathlib import Path
import re
import sys
import time

ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT/'Tools/ota'))
import p34_probe_acquire as base
import p34_gpio_read_probe as host_read
import p34_ap_journal_tests as host_ap
from recovery_entry.control_probe import Control,READ_WORDS,PAUSE,COMP,DCRSR
from recovery_entry import rendezvous,owner_probe,app_resume
from recovery_confirm import gpio_page as gpio,gpio_read,ap_journal
from recovery_confirm.native_io import Words,Budget

cli,host=base.cli,base.host
SELF=Path(__file__).resolve()
FILES=('plan.json','worker.json','parent.json','worker.log','sdk.log','events.jsonl','callbacks.log',
       'project.jlink','read.bin','tests.json','tests.log','result.json','audit.json','reuse.json')
SOURCES=[*base.SOURCES,*host_ap.SOURCES,SELF,*(ROOT/name for name in (
    'Tools/ota/p34_gpio_read_probe.py','Tools/ota/recovery_entry/control_probe.py',
    'Tools/ota/recovery_entry/rendezvous.py','Tools/ota/recovery_entry/owner_probe.py',
    'Tools/ota/recovery_entry/app_resume.py','tests/boot/test_p34_gpio_read_device.py',
    'tests/boot/p34_gpio_session_model.py','tests/boot/test_p34_app_resume.py',
    'tests/boot/test_p34_owner_probe.py','.cache/p34-entry-owner1/worker.json',
    '.cache/p34-recovery-log-probe1/audit.json','.cache/p34-gpio-read-tests3/result.json',
    '.cache/p34-ap-journal-tests2/result.json'))]
REUSED=(('p34-entry-control-test3','WFI_CONTROL_HOST_PASS',22),
        ('p34-entry-owner-test2','HALTED_OWNER_HOST_PASS',9),
        ('p34-app-resume-test3','APP_RESUME_HOST_PASS',16))


def reused_components(store):
    paths=[];manifest=[]
    excluded=ROOT/'Tools/ota/p34_app_resume.py'
    for name,label,count in REUSED:
        area=ROOT/'.cache'/name
        receipt=area/'result.json';value=store.read(receipt)
        cli.require(value['result']==label and value['tests']==count,'original component oracle mismatch')
        paths.append(receipt)
        reused=[];excluded_current=[]
        for item in value['inputs']:
            source=Path(item['path']);snapshot=area/'source'/source.relative_to(ROOT)
            record=cli.record(snapshot)
            cli.require((record['bytes'],record['sha256'])==(item['bytes'],item['sha256']),'reused source snapshot drift')
            paths.append(snapshot)
            if source==excluded:
                excluded_current.append(dict(path=str(source),snapshot=record,reason='Old wrapper not imported or executed'))
            else:
                cli.require(cli.record(source)==item,'reused component dependency changed')
                paths.append(source);reused.append(item)
        manifest.append(dict(receipt=cli.record(receipt),tests=count,reused_current=reused,excluded_current=excluded_current,
                             scope='Unchanged component oracles only; no retained context or old hardware replay'))
    return list(dict.fromkeys(paths)),manifest


def sources(store):
    for path,label in ((ROOT/'.cache/p34-gpio-read-tests3/result.json','GPIO_READ_HOST_PASS'),
                       (ROOT/'.cache/p34-ap-journal-tests2/result.json','AP_JOURNAL_HOST_PASS')):
        result=store.read(path)
        cli.require(result['result']==label and all(cli.record(item['path'])==item for item in result['inputs']),
                    'GPIO/AP component evidence drift')
    paths,_=reused_components(store)
    return list(dict.fromkeys([*SOURCES,*host_read.sources(store),*paths]))


def owners(dap,emit):
    reader=owner_probe.Reader(dap,emit)
    result=dict(updater=owner_probe.collect(reader),qspi=reader.qspi())
    cli.require(result['updater']['no_scheduled_sd_ota_owner'],'scheduled SD OTA owner')
    return result


def execute(dap,observation,emit,save,app,expected_a,*,seconds=420,clock=time.monotonic,sleep=time.sleep):
    """All device actions are on this connection and the newly captured context."""
    cli.require(hashlib.sha256(app).hexdigest()==base.APP_SHA and len(expected_a)==64,'exact original input images required')
    budget=Budget(seconds,clock)
    control=Control(dap,observation,emit,app[0x400:0x460])
    result=dict(result='FAILED',reset_performed=False,physical_waveform_timing_qualified=False)
    resumed=False
    port=None
    try:
        observation.connect()
        budget.now()
        stop=rendezvous.acquire(control,emit,seconds=15,clock=clock,sleep=sleep)
        result['entry']=stop
        cli.require(stop['result']=='APP_WFI_HALTED_RETAINED_NOT_RESET' and
                    not stop['media']['observed_blockers'],'fresh WFI/media admission failed')
        before=[owners(dap,emit),owners(dap,emit)]
        cli.require(before[0]==before[1] and control.context()==stop['context'],'fresh held owner/context changed')
        result['owners_before']=before
        raw=stop['state_samples'][-1]['raw']
        original={address:raw['gpiob_'+name] for address,name in ((gpio.MODE,'mode'),(gpio.TYPE,'type'),
            (gpio.DRIVE,'drive'),(gpio.PULL,'pull'),(gpio.OUTPUT,'output'))}
        io=Words(dap,emit,reads=gpio.READS,write_allowed=gpio.allowed_write,
                 seconds=min(330,budget.left()),clock=clock)
        pins=gpio.Pins(io,original,lambda:not control.reset_seen and dap.ready)
        pins.verify_idle()
        start=clock();sleep(.006)
        cli.require(clock()-start>=.005 and budget.left()>=330,'EEPROM settlement or read/exit allowance missing')
        measurement=[]
        def measured(event,**fields):
            measurement.append(dict(event=event,**fields));emit(event,**fields)
        # The SDK proxy still journals all native calls into the outer event stream.
        io.emit=measured
        probe=gpio_read.Read64(pins,measured,clock=clock,sleep=sleep)
        read=probe.run()
        data=bytes.fromhex(read['raw_hex'])
        result['read']=read
        result['raw']=save(data)
        cli.require(data==expected_a,'current inactive A differs from retained original pair')
        result['wire']=gpio_read.wire_trace(measurement,data,original[gpio.OUTPUT])
        io.emit=emit
        pins.verify_idle()
        cli.require(control.context()==stop['context'],'post-read context differs from this entry')
        after=[control.media(),control.media()]
        cli.require(not rendezvous.stopped_media_observation(after)['observed_blockers'],'post-read media changed')
        owner_after=owners(dap,emit)
        cli.require(owner_after==before[-1],'post-read owners changed')
        result['owners_after']=owner_after
        result['media_after']=after
        vectors=dap.read_flash(0x08010000,524)
        cli.require(vectors==app[:524] and control.context()==stop['context'],'current vector/context changed')
        cli.require(budget.left()>=40,'insufficient verified original-App exit/observation time')
        port=app_resume.Port(dap,emit,app[0x400:0x460])
        result['exit']=app_resume.execute(port,vectors,clock=clock,sleep=sleep)
        budget.now()
        resumed=result['exit']['result']=='ORIGINAL_APP_RESUMED_STABLE'
        cli.require(resumed,'uncertain original-App release; retain observation evidence')
        result['result']='GPIO_READ_ORIGINAL_APP_RESUMED'
    except BaseException as error:
        result['error']=type(error).__name__+': '+str(error)
    finally:
        try:
            if resumed: observation.close()
            else: control.close()
        except BaseException as error:
            result.update(result='FAILED',close_error=type(error).__name__+': '+str(error))
        result['close_returned']=dap.close_returned
        result['dap']=dap.metadata
        result['transport_mutation_attempted']=control.mutation_attempted
        result['release_attempted']=bool(port and port.attempted)
        result['release_returned']=bool(port and port.returned)
        result['running_state']='ORIGINAL_APP_HEALTH_VERIFIED' if resumed else (
            'UNKNOWN_AFTER_RELEASE_ATTEMPT' if result['release_attempted'] else 'NOT_RELEASED_BY_THIS_CELL')
        result['native_ap_error']=getattr(dap.sdk,'error',None)
    return result


def preflight(store,out,inputs):
    cli.require(not out.exists(),'preserve GPIO session evidence')
    for name in FILES: store.checked(out/name)
    for path in inputs: store.checked(out/'source'/path.relative_to(ROOT))
    for key in ('HOME','USERPROFILE','APPDATA','LOCALAPPDATA','TEMP','TMP','TMPDIR','XDG_CACHE_HOME',
                'XDG_CONFIG_HOME','XDG_DATA_HOME','PYTHONUSERBASE','PYTHONPYCACHEPREFIX','CCACHE_DIR','SCCACHE_DIR'):
        store.checked(out/'host'/key.lower())


def worker(store,out):
    deadline=time.monotonic()+420
    cli.require(base.in_job(),'owned GPIO worker required')
    plan=store.read(out/'plan.json');inputs=sources(store)
    cli.require(plan['out']==str(out) and plan['inputs']==[cli.record(path) for path in inputs],'GPIO session source drift')
    cli.require(cli.record(out/'reuse.json')==plan['reuse'] and store.read(out/'reuse.json')==reused_components(store)[1],
                'component reuse manifest drift')
    cli.require(plan['native_history_approved']==str(base.HISTORY) and
                cli.record(base.JLINK/'JLink_x64.dll')['sha256']==base.DLL_SHA,'native authority/identity drift')
    result=dict(result='FAILED',close_returned=False)
    dap=None
    with (out/'events.jsonl').open('x',encoding='utf-8') as stream,(out/'callbacks.log').open('xb') as callbacks:
        def emit(event,**fields):
            stream.write(json.dumps(dict(time=cli.now(),event=event,**fields))+'\n');stream.flush()
        try:
            cli.require(not base.native_presence()['debugger_processes'],'competing debugger')
            with os.add_dll_directory(str(base.JLINK)):
                sdk=base.guarded(ctypes.CDLL,str(base.JLINK/'JLink_x64.dll'))
                dap=base.Dap(sdk,out/'sdk.log',out/'project.jlink',callbacks)
                dap.sdk=ap_journal.JournalSDK(sdk,emit)
                observation=base.Observation(dap,emit,seconds=deadline-time.monotonic())
                app=(ROOT/'.cache/p34-native-image1/app-readback.bin').read_bytes()
                before=(ROOT/'.cache/p34-host-nor-rebuild1/bcb-before.bin').read_bytes()[:64]
                cli.require(deadline-time.monotonic()>=380,'GPIO worker setup consumed read/exit allowance')
                result=execute(dap,observation,emit,lambda raw:store.raw(out/'read.bin',raw),app,before,
                               seconds=deadline-time.monotonic())
        except BaseException as error:
            result['error']=type(error).__name__+': '+str(error)
            if dap and not dap.close_returned:
                try: dap.close()
                except BaseException as close: result['outer_close_error']=type(close).__name__+': '+str(close)
            if dap: result.update(close_returned=dap.close_returned,dap=dap.metadata)
        store.write(out/'worker.json',result)
    print(json.dumps(result))
    return 0 if result['result']=='GPIO_READ_ORIGINAL_APP_RESUMED' and result['close_returned'] else 1


def session_writes(rows,start,end,wire):
    tar=None;bank=0;actual=[];gpio_count=0
    native_read=None;gpio_reads=[]
    pause=[];comparators=[];release=[]
    positions=[];pause_positions=[];comparator_positions=[];release_positions=[]
    expected=[(row['address'],row['value']) for row in rows if row['event'] in
              ('debug-write-attempt','recovery-word-write-attempt','resume-write-attempt')]
    for i,row in enumerate(rows):
        if row['event']=='ap-call-returned' and native_read is not None:
            if start<i<end: gpio_reads.append((native_read,row['read_value']))
            native_read=None
        if row['event']!='ap-call-attempt': continue
        if row['operation']=='write' and row['ap']==0 and row['index']==2: bank=row['value']
        if bank!=0 or row['ap']!=1: continue
        if row['operation']=='write' and row['index']==1: tar=row['value']
        if row['index']==3:
            if row['operation']=='write':
                address,value=tar,row['value'];actual.append((address,value));positions.append(i)
                if address in (gpio.SET,gpio.CLEAR):
                    cli.require(start<i<end,'GPIO store outside the audited read interval');gpio_count+=1
                elif address==PAUSE:
                    cli.require(i<start,'late watchdog pause change');pause.append(value);pause_positions.append(i)
                elif address==COMP:
                    cli.require(i<start,'late comparator change');comparators.append(value);comparator_positions.append(i)
                elif address==app_resume.DHCSR:
                    cli.require(i>end,'resume before complete GPIO read');release.append(value);release_positions.append(i)
                elif address==DCRSR:
                    cli.require(not start<i<end,'core selector inside GPIO read')
                else: raise ValueError('unlisted session target write')
            else: native_read=tar
            if tar is not None: tar=ap_journal.next_tar(tar)
    expected_reads=[(row['address'],row['value']) for row in rows[start+1:end] if row['event']=='recovery-word-read']
    cli.require(gpio_reads==expected_reads,'physical GPIO interval reads differ from AP/native journal')
    cli.require(actual==expected and len(pause)==1 and comparators==[rendezvous.WFI_COMPARATOR,0] and
                release==[0xa05f0001] and gpio_count==wire['gpio_stores'],'session write manifest/order mismatch')
    cli.require(pause_positions[0]<comparator_positions[0]<comparator_positions[1]<start and
                release_positions[0]==positions[-1],'entry ordering or post-release target write violation')
    return dict(target_writes=len(actual),gpio_stores=gpio_count,gpio_target_reads=len(gpio_reads),
                watchdog_pause_stores=1,comparator_stores=2,resume_stores=1)


def audit(store,out):
    import p34_nor_audit as parser
    plan,worker,parent=(store.read(out/(name+'.json')) for name in ('plan','worker','parent'))
    cli.require(plan['inputs']==[cli.record(path) for path in sources(store)],'GPIO audit source drift')
    cli.require(cli.record(out/'reuse.json')==plan['reuse'] and store.read(out/'reuse.json')==reused_components(store)[1],
                'GPIO audit component reuse drift')
    cli.require(parent['exit']==0 and not parent['timeout'] and parent['after_history']==plan['before_history'] and
        worker['result']=='GPIO_READ_ORIGINAL_APP_RESUMED' and worker['close_returned'] and
        worker['exit']['result']=='ORIGINAL_APP_RESUMED_STABLE','normal current-App closure required')
    cli.require(worker['release_attempted'] is True and worker['release_returned'] is True and
        worker['running_state']=='ORIGINAL_APP_HEALTH_VERIFIED' and worker['native_ap_error'] is None and
        worker['exit']['resume_attempts']==1 and worker['exit']['resume_returned'] is True,'verified single release required')
    bound=[cli.record(out/name) for name in ('plan.json','worker.json','parent.json','events.jsonl','sdk.log','read.bin','reuse.json')]
    for item in plan['inputs']:
        snapshot=cli.record(out/'source'/Path(item['path']).relative_to(ROOT))
        cli.require((snapshot['bytes'],snapshot['sha256'])==(item['bytes'],item['sha256']),'GPIO snapshot drift')
    reads=set(READ_WORDS)|set(gpio.READS)|set(app_resume.REGISTERS.values())|set(owner_probe.QSPI_REGS.values())
    def read_allowed(address):
        return address in reads or address%4==0 and (0x08000000<=address<0x08010000+617588 or 0x20000000<=address<0x20058000)
    values={PAUSE:{worker['entry']['before']['debug_apb1_frz']|0x1000},COMP:{0,rendezvous.WFI_COMPARATOR},
            DCRSR:{15,16,17,20},app_resume.DHCSR:{0xa05f0001},gpio.SET:{0x40,0x80},gpio.CLEAR:{0x40,0x80}}
    with (out/'sdk.log').open(encoding='utf-8') as stream:
        trace=ap_journal.audit(stream,parser.events(out/'events.jsonl'),worker['dap'],read_allowed=read_allowed,
            write_allowed=lambda a,v:a in values and (v is None or v in values[a]))
    rows=list(parser.events(out/'events.jsonl'))
    start=[i for i,row in enumerate(rows) if row['event']=='gpio-read-start']
    end=[i for i,row in enumerate(rows) if row['event']=='gpio-read-returned']
    cli.require(len(start)==len(end)==1 and start[0]<end[0],'one GPIO interval required')
    data=(out/'read.bin').read_bytes()
    cli.require(data==(ROOT/'.cache/p34-host-nor-rebuild1/bcb-before.bin').read_bytes()[:64],'physical read archive mismatch')
    wire=gpio_read.wire_trace(rows[start[0]:end[0]+1],data,worker['entry']['state_samples'][-1]['raw']['gpiob_output'])
    manifest=session_writes(rows,start[0],end[0],wire)
    cli.require(manifest['gpio_target_reads']==worker['read']['target_reads'] and
                manifest['gpio_stores']==worker['read']['gpio_stores'],'GPIO measurement count differs from native evidence')
    cli.require(manifest['target_writes']==trace['target_writes'] and worker['dap']['tar_restored'] and
                worker['dap']['csw_restored'] and worker['dap']['dp_restored'],'whole-session writes/restore mismatch')
    started,ended=rows[start[0]]['started'],rows[end[0]]['ended']
    cli.require(ap_journal.valid_time(started) and ap_journal.valid_time(ended) and
                0<ended-started<300 and worker['read']['elapsed_seconds']==ended-started,'GPIO elapsed-time binding mismatch')
    for row in rows[start[0]+1:end[0]]:
        if row['event']=='ap-call-returned':
            cli.require(started<=row['started']<=row['ended']<=ended,'native call outside measured GPIO clock interval')
    cli.require(wire==worker['wire'] and bound==[cli.record(item['path']) for item in bound],'GPIO wire/evidence drift')
    store.write(out/'audit.json',dict(result='GPIO_SESSION_SDK_AUDIT_PASS',trace=trace,wire=wire,manifest=manifest,inputs=bound,
        eeprom_payload_writes=0,original_app_resumed=True,physical_waveform_timing_qualified=False))


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
    if args.action=='audit': audit(store,out);print('GPIO_SESSION_SDK_AUDIT_PASS');return 0
    inputs=sources(store);preflight(store,out,inputs);records=[cli.record(path) for path in inputs]
    if args.action=='capture':
        tests=store.read(args.tests)
        cli.require(tests['result']=='GPIO_SESSION_HOST_PASS' and tests['inputs']==records,'source-bound GPIO session tests required')
        cli.require(args.native_history_approved==base.HISTORY,'exact native history permission required')
        before=base.history(store)
    env=host.environment(store,out)
    for path in inputs: store.raw(out/'source'/path.relative_to(ROOT),path.read_bytes())
    _,reuse=reused_components(store)
    store.write(out/'reuse.json',reuse)
    if args.action=='selftest':
        env['P34_TEST_OUT']=str(out)
        log=host.command(store,out,'tests',[sys.executable,'-I','-S','-B','-X','utf8',ROOT/'tests/boot/test_p34_gpio_read_device.py','-v'],env,180)
        match=re.search(rb'Ran (\d+) tests? in .*\r?\n\r?\nOK\b',log)
        cli.require(match and records==[cli.record(path) for path in inputs],'GPIO session test/source drift')
        store.write(out/'result.json',dict(result='GPIO_SESSION_HOST_PASS',tests=int(match[1]),inputs=records,
                                         reuse=cli.record(out/'reuse.json'),hardware=False))
        print('GPIO_SESSION_HOST_PASS tests='+str(int(match[1])));return 0
    store.write(out/'plan.json',dict(out=str(out),inputs=records,tests=cli.record(args.tests),
        reuse=cli.record(out/'reuse.json'),
        native_history_approved=str(base.HISTORY),before_history=before,parent_seconds=450,
        scope='Fresh original-App WFI; one 64B EEPROM read via PB6/PB7; same-context no-reset verified original-App resume'))
    result=base.owned_run(store,out,[SELF,'worker','--output-dir',out],env,timeout=450)
    result['after_history']=base.history(store);result['presence_after']=base.native_presence()
    store.write(out/'parent.json',result);print(json.dumps(result))
    return 0 if result['exit']==0 and not result['timeout'] else 1


if __name__=='__main__': raise SystemExit(main())
