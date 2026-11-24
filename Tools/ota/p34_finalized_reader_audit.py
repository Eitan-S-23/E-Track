"""Offline closed SDK-to-frame-to-file audit for the nonmutating reader cell."""
import argparse
import json
from pathlib import Path
import re
import sys

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT/'Tools/ota'))
import p34_nor_audit as shared
from recovery_entry.finalized_reader import ORIGIN, LENGTH, DHCSR, VTOR

cli = shared.cli
SOURCES = (Path(__file__).resolve(), Path(shared.__file__).resolve(), Path(cli.__file__).resolve(),
           ROOT/'Tools/ota/recovery_entry/finalized_reader.py', ROOT/'tests/boot/test_p34_finalized_reader_audit.py')


def frames(rows):
    pending = None
    for e in rows:
        if e['event'] == 'finalized-read-attempt':
            cli.require(pending is None,'overlapping target read frames'); pending=e
        elif e['event'] == 'finalized-read-returned':
            cli.require(pending is not None and e['address']==pending['address'] and
                        len(bytes.fromhex(e['data_hex']))==pending['bytes'],'unpaired target read frame')
            pending=None
            yield e
    cli.require(pending is None,'unfinished target read frame')


def trace(lines, rows, metadata, raw):
    original=metadata['ap_csw']; csw=original; tar=None; bank=0; pending=None; closed=False
    expected=iter(frames(rows)); frame=next(expected,None); offset=0
    frame_count=words=ble_words=0; covered=bytearray(len(raw)//4)
    for line in lines:
        cli.require('CPU_WriteMem' not in line,'high-level target write')
        if re.search(r'JLINK(?:ARM)?_Close\(',line): closed=True
        wr,rd=shared.WREG.search(line),shared.RREG.search(line)
        if wr:
            cli.require(pending is None,'overlapping SDK calls')
            port,index,value=wr[1],int(wr[2],16),int(wr[3],16)
            pending=('write',port,index)
            if port=='DP':
                cli.require((index==2 and value in (0,0xf0)) or
                            (index==1 and value in (0,0x40,0x10000000,0x10000040,0x50000000,0x50000040)),
                            'unlisted DP setup')
                if index==2: bank=value
            elif index==0:
                cli.require(value in (original,(original&~0x37)|0x12),'unknown CSW setup');csw=value
            elif index==1:
                cli.require(value in (DHCSR,VTOR,0x20052a54,0x20052b34,metadata['original_tar']) or
                            value%4==0 and ORIGIN<=value<ORIGIN+LENGTH,'TAR outside named read scope')
                tar=value
            else: raise RuntimeError('AP data/unknown write forbidden')
        elif rd:
            cli.require(pending is None,'overlapping SDK read'); pending=('read',rd[1],int(rd[2],16))
        elif shared.VALUE.search(line) and pending and pending[0]=='read':
            value=int(shared.VALUE.search(line)[1],16)
            if pending[1:]==('AP',3) and bank==0:
                cli.require(tar is not None and csw&0x37==0x12,'unknown target read format')
                if tar in (0x20052a54,0x20052b34):
                    cli.require(value&255==0,'observed OTA owner not idle');ble_words+=1
                else:
                    cli.require(frame is not None and tar==frame['address']+offset,'SDK/frame address mismatch')
                    data=bytes.fromhex(frame['data_hex'])
                    cli.require(data[offset:offset+4]==value.to_bytes(4,'little'),'SDK/frame bytes mismatch')
                    if ORIGIN<=tar<ORIGIN+len(raw):
                        ix=tar-ORIGIN
                        cli.require(raw[ix:ix+4]==data[offset:offset+4],'SDK/file bytes mismatch');covered[ix//4]=1
                    else:
                        cli.require((tar==DHCSR and value&0x020a0000==0) or (tar==VTOR and value==ORIGIN),
                                    'unexpected current core/vector observation')
                    words+=1;offset+=4
                    if offset==len(data): frame_count+=1;offset=0;frame=next(expected,None)
                tar=(tar&~1023)|((tar+4)&1023)
        elif shared.RETURN.search(line) and pending:
            cli.require(int(shared.RETURN.search(line)[1])>=0,'failed SDK call');pending=None
        elif re.search(r'JLINK\w*_(?:Write|CORESIGHT_Write)',line): raise RuntimeError('unrecognized SDK write')
    cli.require(pending is None and frame is None and closed,'incomplete SDK/frame/close')
    cli.require(csw==original and tar==metadata['original_tar'],'AP configuration not restored')
    cli.require(all(covered),'image file lacks complete native read coverage')
    return dict(target_memory_data_writes=0,matched_frames=frame_count,matched_words=words,
                matched_image_bytes=len(raw),idle_word_reads=ble_words,native_close_seen=closed)


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output-dir',type=Path,required=True)
    args=parser.parse_args()
    cli.require(Path.cwd()==ROOT and sys.flags.isolated and sys.flags.no_site and sys.dont_write_bytecode,'isolated root required')
    store=cli.Store(ROOT);out=store.checked(args.output_dir);cli.require(not out.exists(),'preserve audit')
    store.checked(out/'result.json')
    area=store.checked('.cache/p34-finalized-reader-device1')
    worker,parent,plan=(store.read(area/(n+'.json')) for n in ('worker','parent','plan'))
    cli.require(parent['exit']==0 and not parent['timeout'] and worker['close_returned'] and
                worker['result']=='EXTENDED_OLD_APP_READ_FINALIZED_REJECTED' and
                not worker['reader']['reset_seen'] and worker['reader']['error'] is None and
                parent['after_history']==plan['before_history'],'qualified closed read required')
    evidence=[cli.record(area/n) for n in ('worker.json','parent.json','plan.json','sdk.log','events.jsonl')]
    evidence.extend((worker['capture'],worker['tail'],*(cli.record(p) for p in SOURCES)))
    for item in plan['inputs']:
        path=store.checked(item['path']);cli.require(cli.record(path)==item,'current qualification source drift')
        snap=cli.record(store.checked(area/'source'/path.relative_to(ROOT)))
        cli.require((snap['bytes'],snap['sha256'])==(item['bytes'],item['sha256']),'qualification snapshot drift')
        evidence.extend((item,snap))
    raw=(area/'readback.bin').read_bytes()
    cli.require(len(raw)==LENGTH and raw[:617588]==(ROOT/'.cache/p34-native-image1/app-readback.bin').read_bytes() and
                raw[617588:]==(area/'tail-unclassified.bin').read_bytes(),'original prefix/tail identity mismatch')
    with (area/'sdk.log').open(encoding='utf-8') as stream:
        result=trace(stream,shared.events(area/'events.jsonl'),worker['dap'],raw)
    cli.require(result['idle_word_reads']==8 and result['matched_frames']==worker['reader']['target_chunks'] and
                result['matched_words']==worker['reader']['target_words'],'exact frame/owner counts mismatch')
    for item in evidence:cli.require(cli.record(store.checked(item['path']))==item,'audit input drift')
    store.write(out/'result.json',dict(result='EXTENDED_READ_SDK_AUDIT_PASS',trace=result,evidence=evidence,
                hardware_operations=0,finalized_r2_admission=False,historical_nor_sdk_gap_preserved=True))
    print('EXTENDED_READ_SDK_AUDIT_PASS',json.dumps(result))


if __name__=='__main__':main()
