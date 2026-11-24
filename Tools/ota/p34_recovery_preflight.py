"""Finite nonmutating Flash envelope/protection capture on original running 30275."""
import argparse
import ctypes
import hashlib
import json
import os
from pathlib import Path
import re
import sys
import time

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT/'Tools/ota'))
import p34_probe_acquire as base
from recovery_confirm.native_io import Words
from recovery_confirm import flash_port as flash
from recovery_confirm.boot_exit import BOOT_SHA

cli,host = base.cli,base.host
SELF = Path(__file__).resolve()
START,END,OLD_SIZE = 0x08010000,0x080a7800,617588
VTOR,STATE,ISR = 0xe000ed08,0x20052a54,0x20052b34
META = (flash.IDCODE,flash.FSIZE,*flash.CLOCK,*flash.CONFIG,*flash.PROTECTION,
        *(a for _,s,c,_ in flash.BANKS for a in (s,c)))
READS = frozenset((flash.DHCSR,VTOR,STATE,ISR,*META,*range(0x08000000,END,4)))
SOURCES = list(dict.fromkeys([*base.SOURCES,SELF,*(ROOT/name for name in (
    'Tools/ota/recovery_confirm/native_io.py','Tools/ota/recovery_confirm/flash_port.py',
    'Tools/ota/recovery_confirm/flash_plan.py','Tools/ota/recovery_confirm/boot_exit.py',
    'Tools/ota/p34_nor_audit.py',
    'tests/boot/test_p34_control_probe.py','tests/boot/test_p34_native_probe.py',
    'tests/boot/test_p34_entry_policy.py',
    'tests/boot/test_p34_recovery_preflight.py','.cache/p34-native-image1/app-readback.bin',
    '.cache/p34-native-acquire1/boot-readback.bin','.cache/p34-reconciled-resume1/parent.json',
    '.cache/p34-recovery-ports3/result.json'))]))
FILES = ('plan.json','parent.json','worker.json','worker.log','events.jsonl','sdk.log','callbacks.log',
         'project.jlink','boot.bin','envelope.bin','collateral.bin','tests.json','tests.log','result.json','audit.json')


def acquire(port,boot,original,save=lambda name,offset,raw:None):
    if hashlib.sha256(boot).hexdigest()!=BOOT_SHA or hashlib.sha256(original).hexdigest()!=base.APP_SHA:
        raise ValueError('exact original images required')
    reset_seen = False
    def owner():
        nonlocal reset_seen
        status = port.read32(flash.DHCSR)
        reset_seen |= bool(status & 0x02000000)
        if reset_seen or status & 0xa0000 or port.read32(VTOR)!=START:
            raise ValueError('old App halted/reset/phase changed')
        if port.read32(STATE)&255 or port.read32(ISR)&255:
            raise ValueError('old OTA owner active')
    def region(name,address,size):
        result = bytearray()
        while len(result)<size:
            owner()
            take = min(1024,size-len(result),1024-(address+len(result))%1024)
            raw = port.read_bytes(address+len(result),take)
            if type(raw) is not bytes or len(raw)!=take:
                raise ValueError('short Flash preflight chunk')
            save(name,len(result),raw)
            result.extend(raw)
            owner()
        return bytes(result)
    owner()
    before = {str(a):port.read32(a) for a in META}
    if region('header',START+0x400,96)!=original[0x400:0x460]:
        raise ValueError('old header changed')
    boot_actual = region('boot',0x08000000,65536)
    if boot_actual!=boot: raise ValueError('original whole Boot changed')
    envelope = region('envelope',START,END-START)
    if envelope[:OLD_SIZE]!=original: raise ValueError('original App prefix changed')
    if region('header',START+0x400,96)!=original[0x400:0x460]:
        raise ValueError('terminal old header changed')
    after = {str(a):port.read32(a) for a in META}
    owner()
    if before!=after: raise ValueError('Flash identity/protection/clock changed during capture')
    return dict(boot=boot_actual,envelope=envelope,collateral=envelope[619580:],before=before,after=after,
                reset_seen=reset_seen,write_admitted=False)


def preflight(store,out):
    cli.require(not out.exists(),'preserve read cell')
    for n in FILES: store.checked(out/n)
    for p in SOURCES: store.checked(out/'source'/p.relative_to(ROOT))
    for key in ('HOME','USERPROFILE','APPDATA','LOCALAPPDATA','TEMP','TMP','TMPDIR','XDG_CACHE_HOME',
                'XDG_CONFIG_HOME','XDG_DATA_HOME','PYTHONUSERBASE','PYTHONPYCACHEPREFIX','CCACHE_DIR','SCCACHE_DIR'):
        store.checked(out/'host'/key.lower())


def worker(store,out):
    deadline=time.monotonic()+330
    cli.require(base.in_job(),'owned preflight worker required')
    plan = store.read(out/'plan.json')
    cli.require(plan['out']==str(out) and plan['inputs']==[cli.record(p) for p in SOURCES],'preflight input drift')
    cli.require(plan['native_history_approved']==str(base.HISTORY) and
                cli.record(base.JLINK/'JLink_x64.dll')['sha256']==base.DLL_SHA,'native scope/DLL drift')
    result = dict(result='FAILED',target_data_writes=0,reset_performed=False,write_admitted=False)
    dap,observer = None,None
    streams = {}
    with (out/'events.jsonl').open('x',encoding='utf-8') as events,(out/'callbacks.log').open('xb') as callbacks:
        def emit(event,**fields):
            events.write(json.dumps(dict(time=cli.now(),event=event,**fields))+'\n'); events.flush()
        def save(name,offset,raw):
            if name=='header': return
            if name not in streams: streams[name]=(out/(name+'.bin')).open('xb')
            stream = streams[name]
            cli.require(stream.tell()==offset,'archive offset changed')
            stream.write(raw); stream.flush()
        try:
            cli.require(not base.native_presence()['debugger_processes'],'another debugger active')
            with os.add_dll_directory(str(base.JLINK)):
                sdk = base.guarded(ctypes.CDLL,str(base.JLINK/'JLink_x64.dll'))
                dap = base.Dap(sdk,out/'sdk.log',out/'project.jlink',callbacks)
                observer = base.Observation(dap,emit,seconds=deadline-time.monotonic())
                observer.connect()
                port = Words(dap,emit,reads=READS,write_allowed=lambda a,v:False,seconds=reader_seconds(deadline))
                port.budget.end=min(port.budget.end,deadline)
                data = acquire(port,(ROOT/'.cache/p34-native-acquire1/boot-readback.bin').read_bytes(),
                               (ROOT/'.cache/p34-native-image1/app-readback.bin').read_bytes(),save)
                cli.require(port.writes==0,'read capability emitted data writes')
                for stream in streams.values(): stream.flush(); os.fsync(stream.fileno())
                result.update(result='FLASH_PREFLIGHT_CAPTURED_NOT_WRITE_ADMITTED',
                              boot=cli.record(out/'boot.bin'),envelope=cli.record(out/'envelope.bin'),
                              collateral=store.raw(out/'collateral.bin',data.pop('collateral')),
                              before=data['before'],after=data['after'],reset_seen=data['reset_seen'])
        except BaseException as error:
            result['error'] = type(error).__name__+': '+str(error)
        finally:
            for name,stream in streams.items():
                try: stream.close()
                except BaseException as error:
                    result['result']='FAILED'
                    result.setdefault('archive_close_errors',[]).append(dict(name=name,error=type(error).__name__+': '+str(error)))
            try:
                if observer: observer.close()
                elif dap: dap.close()
            except BaseException as error:
                result.update(result='FAILED',close_error=type(error).__name__+': '+str(error))
            result['close_returned'] = bool(dap and dap.close_returned)
            if dap: result['dap'] = dap.metadata
            store.write(out/'worker.json',result)
    print(json.dumps(result))
    return 0 if result['result']=='FLASH_PREFLIGHT_CAPTURED_NOT_WRITE_ADMITTED' and result['close_returned'] else 1


def reader_seconds(deadline,clock=time.monotonic):
    left=min(300,deadline-clock())
    cli.require(left>=240,'insufficient prequalified capture budget after connection')
    return left


def scan_trace(lines,rows,metadata,boot_raw,envelope_raw):
    import p34_nor_audit as parser
    archives={'boot':bytearray(),'envelope':bytearray()}
    counts={'chunk':0,'word':0,'close_attempt':0,'close_returned':0}
    word_counts={a:0 for a in (flash.DHCSR,VTOR,STATE,ISR,*META)}
    meta_samples={str(a):[] for a in META}
    def expected():
        pending=None
        for event in rows:
            kind=event['event']
            if kind=='attempt' and event.get('operation')=='close': counts['close_attempt']+=1
            if kind=='returned' and event.get('operation')=='close': counts['close_returned']+=1
            if kind=='recovery-chunk-read-attempt':
                cli.require(pending is None,'overlapping chunk attempts');pending=event
            elif kind=='recovery-word-read':
                address,value=event['address'],event['value']
                cli.require(pending is None and address in word_counts,'unexpected/interleaved word read')
                if address==flash.DHCSR: cli.require(value&0x020a0000==0,'halt/reset/lockup observed')
                if address==VTOR: cli.require(value==START,'old VTOR changed')
                if address in (STATE,ISR): cli.require(value&255==0,'OTA owner not idle')
                if str(address) in meta_samples: meta_samples[str(address)].append(value)
                counts['word']+=1;word_counts[address]+=1
                yield address,value
            elif event['event']=='recovery-chunk-read-returned':
                raw = bytes.fromhex(event['data_hex'])
                address=event['address']
                cli.require(pending is not None and pending['address']==address and pending['bytes']==len(raw),
                            'missing/mismatched chunk attempt/return')
                pending=None;counts['chunk']+=1
                if len(raw)==96:
                    cli.require(address==START+0x400 and raw==envelope_raw[0x400:0x460],'header mismatch')
                else:
                    cli.require(len(raw)==1024,'unexpected archive chunk length')
                    name='boot' if address<START else 'envelope'
                    origin=0x08000000 if name=='boot' else START
                    cli.require(address==origin+len(archives[name]),'archive chunk order')
                    archives[name].extend(raw)
                for i in range(0,len(raw),4): yield event['address']+i,int.from_bytes(raw[i:i+4],'little')
        cli.require(pending is None,'unfinished chunk attempt')
    wanted = iter(expected())
    bank,tar,csw,pending,count = 0,None,metadata['ap_csw'],None,0
    closed=False
    elapsed = []
    for line in lines:
            cli.require('CPU_WriteMem' not in line and not re.search(r'JLINK(?:ARM)?_(?:Connect|Halt|Reset|Go|Step|SetRESET|ClrRESET|SetPower)\(',line),
                        'unexpected high-level device operation')
            if re.search(r'JLINK(?:ARM)?_Close\(',line):
                cli.require(not closed,'duplicate SDK close');closed=True
            wr,rd = parser.WREG.search(line),parser.RREG.search(line)
            if wr:
                cli.require(pending is None and not closed,'overlapping/post-close native calls')
                port,reg,value = wr[1],int(wr[2],16),int(wr[3],16)
                pending = ('write',port,reg)
                if port=='DP':
                    cli.require((reg==2 and value in (0,0xf0)) or
                                (reg==1 and value in (0x50000040,0x10000040,0x40,0x50000000,0x10000000,0)),
                                'unexpected DP write')
                    if reg==2: bank=value
                elif reg==0:
                    cli.require(value in (metadata['ap_csw'],(metadata['ap_csw']&~0x37)|0x12),'unexpected CSW')
                    csw=value
                elif reg==1:
                    cli.require(value in READS or value==metadata['original_tar'],'TAR outside read/restore scope')
                    tar=value
                else: raise ValueError('target data write in read-only cell')
            elif rd:
                cli.require(pending is None and not closed,'overlapping/post-close native calls')
                pending=('read',rd[1],int(rd[2],16))
            elif parser.VALUE.search(line) and pending and pending[0]=='read':
                if pending[1:]==('AP',3) and bank==0:
                    value=int(parser.VALUE.search(line)[1],16)
                    cli.require(csw&0x37==0x12 and next(wanted,None)==(tar,value),'SDK/read journal mismatch')
                    tar=(tar&~1023)|((tar+4)&1023);count+=1
            elif parser.RETURN.search(line) and pending:
                cli.require(int(parser.RETURN.search(line)[1])>=0,'failed native AP call')
                match=re.search(r'-\s+([0-9.]+)ms returns',line)
                cli.require(match is not None,'missing native call duration')
                elapsed.append(float(match[1]));pending=None
            elif re.search(r'JLINK\w*_(?:Write|CORESIGHT_Write)',line):
                raise ValueError('unrecognized native write')
    cli.require(pending is None and next(wanted,None) is None and closed,'unfinished SDK/journal/native close')
    cli.require(csw==metadata['ap_csw'] and tar==metadata['original_tar'],'AP configuration not restored')
    cli.require(counts==dict(chunk=672,word=5420,close_attempt=1,close_returned=1) and count==176988,'read/close count changed')
    cli.require(all(n==(1346 if a in (flash.DHCSR,VTOR,STATE,ISR) else 2) for a,n in word_counts.items()),'owner/meta count changed')
    cli.require(bytes(archives['boot'])==boot_raw and bytes(archives['envelope'])==envelope_raw,'archive differs from native bytes')
    cli.require(len(boot_raw)==65536 and len(envelope_raw)==END-START,'archive extent mismatch')
    elapsed.sort()
    return dict(memory_words=count,register_calls=len(elapsed),mean_native_ms=sum(elapsed)/len(elapsed),
                p99_native_ms=elapsed[int((len(elapsed)-1)*.99)],max_native_ms=max(elapsed),
                counts=counts,meta_samples=meta_samples,native_close_seen=closed)


def audit(store,out):
    import p34_nor_audit as parser
    plan,worker,parent=(store.read(out/(n+'.json')) for n in ('plan','worker','parent'))
    cli.require(plan['inputs']==[cli.record(p) for p in SOURCES],'audit source drift')
    cli.require(parent['exit']==0 and not parent['timeout'] and parent['after_history']==plan['before_history'] and
                worker['result']=='FLASH_PREFLIGHT_CAPTURED_NOT_WRITE_ADMITTED' and worker['close_returned'] and
                not worker.get('archive_close_errors') and worker['reset_seen'] is False,'qualified normal closure required')
    for record in plan['inputs']:
        relative=Path(record['path']).relative_to(ROOT)
        snapshot=cli.record(out/'source'/relative)
        cli.require(snapshot['bytes']==record['bytes'] and snapshot['sha256']==record['sha256'],'snapshot drift')
    bound=[cli.record(out/name) for name in ('sdk.log','events.jsonl','plan.json','worker.json','parent.json',
                                           'boot.bin','envelope.bin','collateral.bin')]
    boot_raw=(out/'boot.bin').read_bytes();envelope=(out/'envelope.bin').read_bytes()
    cli.require(boot_raw==(ROOT/'.cache/p34-native-acquire1/boot-readback.bin').read_bytes() and
                envelope[:OLD_SIZE]==(ROOT/'.cache/p34-native-image1/app-readback.bin').read_bytes() and
                envelope[619580:]==(out/'collateral.bin').read_bytes(),'original image/collateral identity mismatch')
    with (out/'sdk.log').open(encoding='utf-8') as stream:
        result=scan_trace(stream,parser.events(out/'events.jsonl'),worker['dap'],boot_raw,envelope)
    cli.require(all(values==[worker['before'][address],worker['after'][address]] for address,values in result['meta_samples'].items()),
                'worker metadata differs from SDK observations')
    cli.require(bound==[cli.record(item['path']) for item in bound],'audit input drift')
    store.write(out/'audit.json',dict(result='FLASH_PREFLIGHT_SDK_READ_AUDIT_PASS',target_data_writes=0,
        trace=result,
        physical_gpio_timing_qualified=False,inputs=bound,parser=cli.record(Path(parser.__file__)),
        source=cli.record(SELF)))


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
    if args.action=='audit':
        parent=store.read(out/'parent.json')
        cli.require(parent['exit']==0 and not parent['timeout'],'normal closure required')
        audit(store,out);print('FLASH_PREFLIGHT_SDK_READ_AUDIT_PASS');return 0
    preflight(store,out)
    inputs=[cli.record(p) for p in SOURCES]
    if args.action=='capture':
        tests=store.read(args.tests)
        cli.require(tests['result']=='FLASH_PREFLIGHT_HOST_PASS' and tests['inputs']==inputs,'bound preflight tests required')
        cli.require(args.native_history_approved==base.HISTORY,'exact native history permission required')
        old=store.read(ROOT/'.cache/p34-reconciled-resume1/parent.json')
        cli.require(old['exit']==0 and not old['timeout'],'original resume not closed')
        before=base.history(store)
    env=host.environment(store,out)
    for p in SOURCES: store.raw(out/'source'/p.relative_to(ROOT),p.read_bytes())
    if args.action=='selftest':
        env['P34_TEST_OUT']=str(out)
        log=host.command(store,out,'tests',[sys.executable,'-I','-S','-B','-X','utf8',
                         ROOT/'tests/boot/test_p34_recovery_preflight.py','-v'],env,120)
        count=re.search(rb'Ran (\d+) tests? in .*\r?\n\r?\nOK\b',log)
        cli.require(count and inputs==[cli.record(p) for p in SOURCES],'test/input drift')
        store.write(out/'result.json',dict(result='FLASH_PREFLIGHT_HOST_PASS',tests=int(count[1]),inputs=inputs,hardware=False))
        print('FLASH_PREFLIGHT_HOST_PASS tests='+str(int(count[1])));return 0
    store.write(out/'plan.json',dict(out=str(out),inputs=inputs,tests=cli.record(args.tests),before_history=before,
        native_history_approved=str(base.HISTORY),parent_seconds=360,observation_seconds=330,read_seconds=300,
        scope='No halt/reset/data-write: original Boot65536B, App envelope620544B, collateral964B, read-only Flash metadata'))
    result=base.owned_run(store,out,[SELF,'worker','--output-dir',out],env,timeout=360)
    result['after_history']=base.history(store);result['presence_after']=base.native_presence()
    store.write(out/'parent.json',result);print(json.dumps(result))
    return 0 if result['exit']==0 and not result['timeout'] else 1


if __name__=='__main__': raise SystemExit(main())
