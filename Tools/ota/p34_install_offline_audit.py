"""Streaming post-close transport/archive audit, not a device entry point.

Runtime health/context interpretation still needs independent review. A PASS
here proves the exact wire/native transcript and archived bytes, not OTA speed.
"""
import argparse
import hashlib
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT/'Tools/ota'))
import p34_install_recovery as host
from recovery_confirm import install as body, nor_capture as nor, gpio_page as gpio
from recovery_confirm import eeprom_sequence as eeprom, flash_port as flash, r2_health as health
from recovery_confirm.mutation_audit import SealedGate, flash_stores, target_events
from recovery_confirm.confirm_io import draft, observe
SELF=Path(__file__).resolve()


def record(path):
    path = Path(path)
    digest = hashlib.sha256()
    size = 0
    with path.open('rb') as stream:
        for raw in iter(lambda:stream.read(1024*1024),b''):
            size += len(raw);digest.update(raw)
    return dict(path=str(path),bytes=size,sha256=digest.hexdigest())


def partitions(stream):
    """Only a returned log switch moves subsequent events to the next file."""
    rows = []
    index = 0
    for line in stream:
        row = json.loads(line)
        if row['event']=='online-log-switch-returned':
            if (row['old'],row['new'])!=(index,index+1): raise ValueError('event segment order')
            yield rows
            rows = []
            index += 1
        rows.append(row)
    if rows: yield rows


def chunks(rows,address,size):
    data = bytearray()
    for row in rows:
        if row['event']=='recovery-chunk-read-returned' and address<=row['address']<address+size:
            if row['address']!=address+len(data): raise ValueError('archive chunk gap/repetition')
            data.extend(bytes.fromhex(row['data_hex']))
    if len(data)!=size: raise ValueError('archive chunk coverage differs')
    return bytes(data)


def bind_records(frozen,current,required):
    if frozen!=current or len({r['path'] for r in frozen})!=len(frozen):
        raise ValueError('current input differs from frozen execution dependency')
    if not set(map(str,required)).issubset({r['path'] for r in frozen}):
        raise ValueError('consumed asset/oracle/helper not bound by execution plan')
    return current


def source_bindings(store,plan,oracle):
    required=[*host.ASSETS.values(),Path(oracle['path']),ROOT/'.cache/p34-confirm-page2/result.json']
    # Bind helpers actually used by this auditor, not every module imported by
    # historical preparation tools (including an unused legacy NOR writer).
    helpers=(host,host.cli,host.setup,host.confirm,body,nor,gpio,eeprom,flash,health,
             sys.modules[SealedGate.__module__],sys.modules[draft.__module__])
    required.extend(Path(module.__file__).resolve() for module in helpers)
    return bind_records(plan['inputs'],[record(store.checked(r['path'])) for r in plan['inputs']],required)


def wire(rows,kind,address,payload,size,original):
    """Decode physical SDA, with exact master stores checked by the SDK cursor."""
    if original&0xc0!=0xc0: raise ValueError('released GPIO latch required')
    output = original
    driven,sampled,starts,stops = [],[],[],[]
    current = None
    fresh_input=post_expected=None
    started=False
    for operation,at,value in target_events(rows):
        if operation=='write':
            if at not in (gpio.SET,gpio.CLEAR) or value not in (0x40,0x80): raise ValueError('non-GPIO wire store')
            if post_expected is not None: raise ValueError('missing physical START/STOP post-level')
            if not started:
                if fresh_input!=(original,0xc0): raise ValueError('missing initial physical idle')
                started=True
            previous = output
            output = output|value if at==gpio.SET else output&~value
            if value==0x40:
                if not previous&0x40 and output&0x40:
                    driven.append(int(bool(output&0x80)));sampled.append(None);current=len(driven)-1
                if not output&0x40: current=None
            elif previous&0x40 and bool(previous&0x80)!=bool(output&0x80):
                if fresh_input!=(previous,previous&0xc0): raise ValueError('missing physical START/STOP pre-level')
                post_expected=output&0xc0
                (stops if output&0x80 else starts).append(len(driven))
                # START/STOP are boundaries, not stable data bit samples.
                current=None
            fresh_input=None
        elif at==gpio.OUTPUT and value!=output: raise ValueError('wire latch mismatch')
        elif at==gpio.INPUT:
            if bool(value&0x40)!=bool(output&0x40): raise ValueError('physical SCL mismatch')
            if post_expected is not None:
                if value&0xc0!=post_expected: raise ValueError('physical START/STOP post-level mismatch')
                post_expected=None
            fresh_input=(output,value&0xc0)
            if current is not None:
                bit=int(bool(value&0x80))
                if sampled[current] is not None and sampled[current]!=bit: raise ValueError('unstable physical SDA')
                sampled[current]=bit
    expected_bits = 29+size*9 if kind=='read' else (len(payload)+2)*9+1 if kind=='page' else 10
    if (not started or post_expected is not None or output!=original or starts!=([0,19] if kind=='read' else [0]) or
            stops!=[expected_bits] or len(driven)!=expected_bits): raise ValueError('wire boundary/count mismatch')
    def byte(bits):
        if len(bits)!=8 or any(bit not in (0,1) for bit in bits): raise ValueError('missing physical bit')
        return sum(bit<<(7-i) for i,bit in enumerate(bits))
    sent = [(0,0xa0)]
    if kind!='ack': sent.append((9,address))
    if kind=='read': sent.append((19,0xa1))
    if kind=='page': sent.extend((18+9*i,b) for i,b in enumerate(payload))
    for start,wanted in sent:
        if (byte(driven[start:start+8])!=wanted or byte(sampled[start:start+8])!=wanted or
                driven[start+8]!=1 or sampled[start+8]!=0): raise ValueError('master byte/slave ACK mismatch')
    raw = b''
    if kind=='read':
        raw = bytes(byte(sampled[28+9*i:36+9*i]) for i in range(size))
        for i in range(size):
            if (driven[28+9*i:36+9*i]!=[1]*8 or driven[36+9*i]!=int(i==size-1) or
                    sampled[36+9*i]!=int(i==size-1)): raise ValueError('master release/ACK/NACK mismatch')
    return raw


def segments(assets,plan,demcr,aircr):
    def item(name,reads,stores=(),**extra): return dict(name=name,reads=reads,stores=stores,**extra)
    selectors = tuple((body.DCRSR,v) for v in (15,16,17,20))
    reads = {*body.control_probe.READ_WORDS,*body.STATE_WORDS,*body.owner_probe.QSPI_REGS.values(),
             *range(0x20000000,0x20058000,4),*range(0x08010000,0x08010000+617588,4)}
    yield item('retained-entry',reads,selectors*3,bind_words=False)
    def internal(label):
        envelope = assets['envelope'] if label=='before' else assets['image']+assets['envelope'][len(assets['image']):]
        for name,origin,data in (('boot',0x08000000,assets['boot']),('envelope',0x08010000,envelope)):
            for offset in range(0,len(data),nor.BLOCK):
                raw=data[offset:offset+nor.BLOCK]
                yield item(label+'-'+name,body.INTERNAL_READS,archive=(label+'-'+name,offset,origin+offset,raw))
    def pair(label):
        expected = assets['bcb'] if label=='before' else plan.target*2
        for index,address in enumerate((0,64,0,64)):
            yield item(label+'-bcb',gpio.READS,eeprom.stores('read',address,size=64),
                       wire=('read',address,b'',64),eeprom_archive=(label+'-bcb',index*64,expected[index*64:(index+1)*64]))
    def regions(label):
        for name,(start,end,_) in nor.REGIONS.items():
            reads={nor.DHCSR,nor.PAUSE,*nor.QSPI_REGS.values(),*range(nor.MAPPED+start,nor.MAPPED+end,4)}
            for offset in range(0,end-start,nor.BLOCK):
                raw=assets[name][offset:offset+nor.BLOCK]
                yield item(label+'-'+name,reads,nor.OPEN if offset==0 else (),
                           archive=(label+'-'+name,offset,nor.MAPPED+start+offset,raw))
            yield item(label+'-'+name+'-close',reads,nor.CLOSE)
    yield from internal('before')
    yield from pair('before')
    yield from regions('before')
    yield item('state-before',{*body.STATE_WORDS,*body.STATE_EXTRA},bind_words=False)
    for index,(address,_) in enumerate(body.geometry(assets['image']).sectors):
        reads={flash.DHCSR,flash.PAUSE,flash.IDCODE,flash.FSIZE,*flash.CLOCK,*flash.CONFIG,*flash.PROTECTION,
               *range(address,address+2048,4),*(a for _,s,c,_ in flash.BANKS for a in (s,c))}
        yield item('flash-'+str(index),reads,flash_stores(assets['image'],assets['envelope'],index))
    operations=[('read',0,b'',64),('read',64,b'',64)]
    for offset in range(0,64,8):
        operations += [('page',offset,plan.record[offset:offset+8],0),('ack',0,b'',0),('read',offset,b'',8)]
    operations += [('read',a,b'',64) for a in (0,64,0,64)]
    for index,(kind,address,payload,size) in enumerate(operations):
        extra = {}
        if kind=='read':
            expected=(plan.before if index<2 else plan.target)[address:address+size]
            extra['eeprom_archive']=('confirm-read-'+str(index),0,expected)
        yield item('eeprom-'+str(index),gpio.READS,eeprom.stores(kind,address,payload,size),
                   wire=(kind,address,payload,size),**extra)
    yield from internal('after')
    yield from regions('after')
    yield item('state-after',{*body.STATE_WORDS,*body.STATE_EXTRA},bind_words=False)
    yield from pair('after')
    yield item('reset',body.EXIT_READS,((body.DFSR,8),(body.DEMCR,demcr|1),(body.AIRCR,aircr))+selectors)
    yield item('release',body.EXIT_READS,selectors+((body.DEMCR,demcr),(body.DHCSR,0xa05f0001)))
    yield item('health',health.READS)


def audit(store,area):
    auditor=record(SELF)
    worker,parent,plan = (store.read(area/(n+'.json')) for n in ('worker','parent','plan'))
    host.cli.require(parent['exit']==0 and not parent['timeout'] and worker['result']=='R2_INSTALLED_ORIGINAL_BOOT_CLOSED' and
                     worker['close_returned'] and worker['sources_unchanged_after_close'] and
                     parent['after_history']==plan['before_history'],'normal closed installation required')
    for original in plan['inputs']:
        saved=record(store.checked(area/'source'/Path(original['path']).relative_to(ROOT)))
        host.cli.require((saved['bytes'],saved['sha256'])==(original['bytes'],original['sha256']),'frozen snapshot drift')
    oracle=store.read(ROOT/'.cache/p34-confirm-page2/result.json')['dll']
    sources=source_bindings(store,plan,oracle)
    assets={name:path.read_bytes() for name,path in host.ASSETS.items()}
    host.cli.require(record(oracle['path'])==oracle,'C oracle changed')
    dll,function=host.confirm.bind(Path(oracle['path']))
    draft_plan=draft(function,(area/'before-bcb.bin').read_bytes(),assets['boot'],assets['image'])
    host.cli.require(draft_plan.address==0 and (area/'draft-a.bin').read_bytes()==draft_plan.record and
                     observe(function,draft_plan,(area/'after-bcb.bin').read_bytes()),'original C draft/final pair failed')
    archives={name:record(store.checked(area/(name+'.bin'))) for name in host.ARCHIVES}
    host.cli.require(archives==worker['archives'] and all(archives[n]['bytes']==size for n,size in host.ARCHIVES.items()),
                     'exact final archive set differs')
    paths=[store.checked(area/name) for name in host.LOGS]
    gate=SealedGate(paths,worker['dap'],record)
    inputs=[record(area/name) for name in ('events.jsonl','plan.json','parent.json','worker.json')]
    setup,restore=host.setup.dp_plan(worker['dap'])
    with (area/'events.jsonl').open(encoding='utf-8') as stream:
        groups=iter(partitions(stream))
        gate.begin(0)
        gate.seal(0,next(groups),read_allowed=lambda _:False,expected_stores=(),expected_dp_writes=setup)
        planned=list(segments(assets,draft_plan,0,0))
        demcr=None
        if len(planned)!=719: raise ValueError('complete segment plan differs')
        original=worker['component_results']['entry']['state_samples'][-1]['raw']['gpiob_output']
        for index,spec in enumerate(planned,1):
            rows=next(groups)
            selectors=tuple((body.DCRSR,v) for v in (15,16,17,20))
            if spec['name']=='reset':
                def first_read(address):
                    return next(row['value'] for row in rows if row['event']=='recovery-word-read' and row['address']==address)
                demcr=first_read(body.DEMCR)
                if demcr&1: raise ValueError('preexisting vector catch')
                aircr=0x05fa0004|(first_read(body.AIRCR)&0x700)
                spec['stores']=((body.DFSR,8),(body.DEMCR,demcr|1),(body.AIRCR,aircr))+selectors
            elif spec['name']=='release':
                if demcr is None: raise ValueError('release without reset plan')
                spec['stores']=selectors+((body.DEMCR,demcr),(body.DHCSR,0xa05f0001))
            gate.begin(index)
            gate.seal(index,rows,read_allowed=lambda a,reads=spec['reads']:a in reads,
                      expected_stores=spec['stores'],bind_words=spec.get('bind_words',True))
            if 'archive' in spec:
                name,offset,address,wanted=spec['archive']
                with (area/(name+'.bin')).open('rb') as archive:
                    archive.seek(offset);stored=archive.read(len(wanted))
                if chunks(rows,address,len(wanted))!=wanted or stored!=wanted: raise ValueError('native/archive/asset bytes differ')
            if 'wire' in spec:
                raw=wire(rows,*spec['wire'],original)
                if 'eeprom_archive' in spec:
                    name,offset,wanted=spec['eeprom_archive']
                    stored=(area/(name+'.bin')).read_bytes()[offset:offset+len(wanted)]
                    if raw!=wanted or stored!=wanted: raise ValueError('physical SDA/archive/C bytes differ')
            print('AUDITED',index,spec['name'],flush=True)
        gate.begin(720)
        gate.seal(720,next(groups),read_allowed=lambda _:False,expected_stores=(),expected_dp_writes=restore,
                  final=True,native_closed=True)
        if next(groups,None) is not None: raise ValueError('extra event segments')
    if (gate.records!=worker['logs'] or inputs!=[record(r['path']) for r in inputs] or
            sources!=source_bindings(store,plan,oracle) or auditor!=record(SELF)): raise ValueError('original evidence/auditor/input changed')
    return dict(result='INSTALL_TRANSPORT_ARCHIVES_AUDIT_PASS',logs=gate.records,archives=archives,inputs=inputs+sources,
                auditor=auditor,
                native_calls=gate.cursor.native_calls,target_reads=gate.cursor.target_reads,
                target_writes=gate.cursor.target_writes,historical_sdk_audit_passed=False,
                runtime_health_independently_reconciled=False,hardware_operations=0)


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--area',type=Path,required=True)
    parser.add_argument('--output-dir',type=Path,required=True)
    args=parser.parse_args()
    host.cli.require(Path.cwd()==ROOT and sys.flags.isolated and sys.flags.no_site and sys.dont_write_bytecode,'isolated root required')
    store=host.cli.Store(ROOT);out=store.checked(args.output_dir)
    store.checked(out/'result.json')
    host.cli.require(not out.exists(),'preserve audit output')
    result=audit(store,store.checked(args.area))
    if result['auditor']!=record(SELF): raise ValueError('auditor changed before result publication')
    store.write(out/'result.json',result)
    print(result['result'])


if __name__=='__main__': main()
