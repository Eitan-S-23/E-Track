"""Reconcile install2 through its failed third sector; never operate a device."""
import argparse
from pathlib import Path
import sys

ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT/'Tools/ota'))
import p34_install_offline_audit as prior
from recovery_confirm.mutation_audit import SealedGate,target_events

SELF=Path(__file__).resolve()
AREA=ROOT/'.cache/p34-recovery-install2'


def audit(store,out):
    record=prior.record
    worker,parent,plan=(store.read(AREA/(n+'.json')) for n in ('worker','parent','plan'))
    require=prior.host.cli.require
    require(worker['result']=='FAILED' and worker['phase']=='FLASH' and
            worker['error']=='ValueError: Flash completion unknown at operational deadline' and
            worker['close_returned'] and worker['sources_unchanged_after_close'] and worker['native_ap_error'] is None and
            worker['app_may_have_changed'] and worker['flash_sectors_audited']==2 and
            not worker['eeprom_pages_attempted'] and not worker['reset_attempted'] and not worker['release_attempted'] and
            parent['exit']==1 and not parent['timeout'] and parent['after_history']==plan['before_history'],
            'exact closed partial third-sector failure required')
    require(worker['dap']['original_dp']==0x40 and worker['dap']['retained_dp_ctrlstat']==0xf0000040 and
            not worker['dap']['dp_restored'],'explicit retained DP disposition required')
    paths=[store.checked(AREA/('sdk-%03d.log'%i)) for i in range(196)]
    originals=[record(AREA/n) for n in ('events.jsonl','plan.json','worker.json','parent.json')]
    originals += [record(SELF),record(Path(prior.__file__))]
    oracle=store.read(ROOT/'.cache/p34-confirm-page2/result.json')['dll']
    sources=prior.source_bindings(store,plan,oracle)
    assets={name:path.read_bytes() for name,path in prior.host.ASSETS.items()}
    dll,function=prior.host.confirm.bind(Path(oracle['path']))
    draft=prior.draft(function,(AREA/'before-bcb.bin').read_bytes(),assets['boot'],assets['image'])
    require(draft.address==0 and (AREA/'draft-a.bin').read_bytes()==draft.record,'fixed inactive A draft mismatch')
    specs=list(prior.segments(assets,draft,0,0))
    gate=SealedGate(paths,worker['dap'],record)
    envelope=bytearray(assets['envelope'])
    envelope[:4096]=assets['image'][:4096]
    envelope[4096:6144]=b'\xff'*2048
    original=worker['component_results']['entry']['state_samples'][-1]['raw']['gpiob_output']
    archives={}
    with (AREA/'events.jsonl').open(encoding='utf-8') as stream:
        groups=iter(prior.partitions(stream))
        gate.begin(0)
        gate.seal(0,next(groups),read_allowed=lambda _:False,expected_stores=(),expected_dp_writes=(0x50000040,))
        for index in range(1,196):
            rows=next(groups)
            spec=specs[index-1]
            stores=spec['stores']
            if index==195:
                actual=[(address,value) for op,address,value in target_events(rows) if op=='write']
                require(actual and len(actual)<len(stores) and tuple(actual)==stores[:len(actual)] and
                        actual[-1]==(0x08011224,0x8965ff72),'not the exact observed third-sector prefix')
                stores=actual
                require(spec['name']=='flash-2','failed stage plan mismatch')
                last_reads=[(a,v) for op,a,v in target_events(rows) if op=='read']
                require(last_reads[-1]==(0x40023c0c,0x20) and (0x08011224,0x8965ff72) not in last_reads,
                        'terminal EOP/no-readback discriminator differs')
                for address,value in actual:
                    if 0x08011000<=address<0x08011800:
                        envelope[address-0x08010000:address-0x08010000+4]=value.to_bytes(4,'little')
                # Only this local final oracle targets retained DP, not original40.
                gate.cursor.metadata=dict(worker['dap'],original_dp=0xf0000040)
            gate.begin(index)
            trace=gate.seal(index,rows,read_allowed=lambda a,reads=spec['reads']:a in reads,
                      expected_stores=stores,bind_words=spec.get('bind_words',True),
                      final=index==195,native_closed=index==195)
            if index>=193:
                sector=index-193
                address=0x08010000+sector*2048
                captured=[row for row in rows if row['event']=='recovery-chunk-read-returned' and
                          address<=row['address']<address+2048]
                require([row['address'] for row in captured]==[address,address+1024]*(2 if index==195 else 3),
                        'sector full readback order/coverage differs')
                values=[bytes.fromhex(row['data_hex']) for row in captured]
                offset=sector*2048
                require(values[0]+values[1]==assets['envelope'][offset:offset+2048] and
                        values[2]+values[3]==b'\xff'*2048,'sector preimage/erased readback differs')
                if index<195:
                    require(values[4]+values[5]==assets['image'][offset:offset+2048],'complete sector readback differs')
                else:
                    require((trace['native_calls'],trace['target_reads'],trace['target_writes'])==(9752,2478,287),
                            'exact failed segment counts differ')
            if 'archive' in spec:
                name,offset,address,wanted=spec['archive']
                path=AREA/(name+'.bin')
                with path.open('rb') as archive:
                    archive.seek(offset);stored=archive.read(len(wanted))
                require(prior.chunks(rows,address,len(wanted))==wanted and stored==wanted,'fresh archive/native bytes mismatch')
                archives[name]=record(path)
            if 'wire' in spec:
                raw=prior.wire(rows,*spec['wire'],original)
                name,offset,wanted=spec['eeprom_archive']
                path=AREA/(name+'.bin')
                require(raw==wanted and path.read_bytes()[offset:offset+len(wanted)]==wanted,'physical BCB bytes mismatch')
                archives[name]=record(path)
            if index%20==0 or index>=193: print('FAILED_CELL_SEGMENT_AUDITED',index,spec['name'],flush=True)
        require(next(groups,None) is None,'events after actual native Close segment')
    require(gate.records[:195]==worker['sealed'] and originals==[record(r['path']) for r in originals] and
            sources==prior.source_bindings(store,plan,oracle),'failed-cell input/source drift')
    expected=store.raw(out/'expected-envelope.bin',bytes(envelope))
    return dict(result='PARTIAL_FLASH_PREFIX_RECONCILED_NOT_RESUME_ADMITTED',logs=gate.records,
                native_calls=gate.cursor.native_calls,target_reads=gate.cursor.target_reads,
                target_writes=gate.cursor.target_writes,archives=archives,inputs=originals+sources,
                expected_envelope=expected,last_program_address=0x08011224,last_program_value=0x8965ff72,
                last_status=0x20,last_word_read_back=False,relocked=False,
                dp_restored=False,actual_original_dp=0x40,preclose_retained_dp=0xf0000040,
                historical_sdk_audit_passed=False,hardware_operations=0,physical_envelope_observed=False)


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output-dir',type=Path,required=True)
    args=parser.parse_args()
    prior.host.cli.require(Path.cwd()==ROOT and sys.flags.isolated and sys.flags.no_site and sys.dont_write_bytecode,'isolated root required')
    store=prior.host.cli.Store(ROOT);out=store.checked(args.output_dir)
    for name in ('result.json','expected-envelope.bin'):store.checked(out/name)
    prior.host.cli.require(not out.exists(),'preserve failed-prefix evidence')
    result=audit(store,out);store.write(out/'result.json',result);print(result['result'])


if __name__=='__main__':main()
