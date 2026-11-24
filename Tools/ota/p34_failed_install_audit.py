"""Offline exact failed-entry reconciliation; no device operation or repair."""
import argparse
import hashlib
from pathlib import Path
import re
import sys

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT/'Tools/ota'))
import p34_session as cli
import p34_nor_audit as parser
from recovery_confirm.mutation_audit import Cursor
from recovery_entry import control_probe, owner_probe
from recovery_entry.state_probe import STATE_WORDS

AREA = ROOT/'.cache/p34-recovery-install1'
RECEIPT = ROOT/'.cache/p34-failed-install-audit1/result.json'
HASHES = dict(zip(('sdk-000.log','sdk-001.log','events.jsonl','worker.json','parent.json','plan.json'), (
    '40c4a35d810beb3d03b5af67bcba3985f3939eedc0b3bd9791035f0d80f73d7a',
    '6ae4d0af3569801b44e93403ed135367a81f4e47d1cf5eaa08b9bb8255daa594',
    'ee75885f5a9c96d4c7746fba7d155b29fcfa3c7ed321f0651c0bb59bcc4dbc14',
    '185e546495160ed52eb53c8fbdd12c2647919703f25f38339e91253346e4bf31',
    '847b472afe8bcb49a67388a61e62b30fe8581d7291490988a3aa4f3cf3e8135b',
    '14cbb568fd77bb9c1c53ada84e0c7dfa4c67f1dfe92e0ebbdd813afd2705cf3f')))
BUILD = ROOT/'.cache/p34-sha-candidate'
INPUTS = [Path(__file__),ROOT/'Tools/ota/recovery_confirm/mutation_audit.py',
          ROOT/'Tools/ota/recovery_confirm/ap_journal.py',ROOT/'Tools/ota/p34_nor_audit.py',
          *(AREA/name for name in HASHES),BUILD/'build/result.json',BUILD/'build/source.json',
          *(BUILD/'b/app-gcc'/('X-Track-App-GCC'+ext) for ext in ('.bin','.elf','.map')),
          BUILD/'f/MDK-ARM_F435/Platform/lv_port/lv_port_disp.cpp',
          BUILD/'f/MDK-ARM_F435/Platform/HAL/HAL_Display.cpp',
          ROOT/'.cache/p34-app-handoff/result.json',ROOT/'.cache/p34-app-handoff/elf.bin',
          ROOT/'.cache/p34-app-handoff/symbols.log',ROOT/'.cache/p34-app-handoff/symbols.json',
          ROOT/'.cache/p34-native-image1/app-readback.bin']


def trace(paths, rows, metadata, closed):
    indexes = [i for i,row in enumerate(rows) if row['event']=='online-log-switch-returned']
    cli.require(len(indexes)==1,'exact single setup switch required')
    split = indexes[0]
    cursor = Cursor(metadata)
    with paths[0].open(encoding='utf-8') as stream:
        first = cursor.verify(stream,rows[:split],read_allowed=lambda _:False,expected_stores=(),
                              expected_dp_writes=(0x50000040,),switched_away=True)
    selectors = tuple((control_probe.DCRSR,value) for value in (15,16,17,20))
    stores = ((control_probe.PAUSE,0x1000),(control_probe.COMP,0x48045a79))+selectors+((control_probe.COMP,0),)+selectors*2
    reads = {*control_probe.READ_WORDS,*STATE_WORDS,*owner_probe.QSPI_REGS.values(),
             *range(0x20000000,0x20058000,4),*range(0x08010000,0x08010000+617588,4)}
    # The failed cell intentionally retained debug requests. Change only this
    # local final-readback oracle; never claim the actual original DP restored.
    cli.require(metadata['original_dp']==0x40 and metadata['retained_dp_ctrlstat']==0xf0000040 and
                metadata['dp_restore_deferred_for_halt'] and not metadata['dp_restored'],
                'explicit retained DP disposition required')
    cursor.metadata = dict(metadata,original_dp=0xf0000040)
    with paths[1].open(encoding='utf-8') as stream:
        last = cursor.verify(stream,rows[split:],read_allowed=lambda a:a in reads,expected_stores=stores,
                             final=True,bind_words=False,native_closed=closed)
    cli.require(first['tail']==last['first'],'setup/entry boundary differs')
    cli.require((cursor.native_calls,cursor.target_reads,cursor.target_writes)==(1584,513,15),
                'failed-entry exact native counts differ')
    return dict(native_calls=cursor.native_calls,target_reads=cursor.target_reads,target_stores=list(stores),
                target_writes=cursor.target_writes,native_close=last['native_close_completed'],
                actual_original_dp=metadata['original_dp'],retained_dp=0xf0000040,dp_restored=False,
                nvm_payload_writes=0,reset_writes=0,resume_writes=0)


def build_binding(store):
    build = store.read(BUILD/'build/result.json')
    for record in build['artifacts']+[build['source']]:
        cli.require(cli.record(store.checked(record['path']))==record,'original build binding changed')
    source = store.read(BUILD/'build/source.json')
    for name in ('lv_port/lv_port_disp.cpp','HAL/HAL_Display.cpp'):
        path = BUILD/'f/MDK-ARM_F435/Platform'/name
        record = next(r for r in source['files'] if r['path']==str(path))
        cli.require(cli.record(path)==record,'display source changed')
    handoff = store.read(ROOT/'.cache/p34-app-handoff/result.json')
    cli.require(cli.record(ROOT/'.cache/p34-app-handoff/elf.bin')==handoff['extracted_binary'],
                'ELF-extracted binary changed')
    raw = (BUILD/'b/app-gcc/X-Track-App-GCC.bin').read_bytes()
    old = (ROOT/'.cache/p34-native-image1/app-readback.bin').read_bytes()
    cli.require(hashlib.sha256(old).hexdigest()=='4d248fd7e3f6db9d08afdc3712f383064779a3b732ae3b7d550a4f2c393114f6' and
                len(raw)==len(old)==617588 and raw==(ROOT/'.cache/p34-app-handoff/elf.bin').read_bytes() and
                old[:0x400]+old[0x460:]==raw[:0x400]+raw[0x460:],'original executable/build mismatch')
    mapped = (BUILD/'b/app-gcc/X-Track-App-GCC.map').read_text(encoding='utf-8')
    symbols = (ROOT/'.cache/p34-app-handoff/symbols.log').read_text(encoding='utf-8')
    for number,address in ((2,0x200045e0),(1,0x200171e0)):
        name = '_ZZ17lv_port_disp_initvE12lv_disp_buf'+str(number)
        cli.require(re.search(r'(?m)^ .bss\.'+name+r'\s+0x%08x\s+0x12c00\b'%address,mapped) and
                    re.search(r'(?m)^%08x 00012c00 b '%address+name+r'\s*$',symbols),'display symbol mismatch')
    return dict(display_buffers=[0x200045e0,0x200171e0],each_bytes=76800,executable_equal_except_header=True)


def audit(store):
    records = [cli.record(store.checked(path)) for path in INPUTS]
    for name,digest in HASHES.items():
        cli.require(cli.record(AREA/name)['sha256']==digest,'failed original evidence changed')
    worker,parent,plan = (store.read(AREA/(name+'.json')) for name in ('worker','parent','plan'))
    cli.require(worker['result']=='FAILED' and worker['error']=='ValueError: DMA endpoint/count changed' and
                worker['phase']=='FRESH_ENTRY' and worker['close_returned'] and worker['native_ap_error'] is None and
                worker['sources_unchanged_after_close'] and parent['exit']==1 and not parent['timeout'] and
                parent['after_history']==plan['before_history'] and not parent['presence_after']['debugger_processes'],
                'exact closed failed entry required')
    for name in ('app_may_have_changed','flash_sectors_audited','eeprom_pages_attempted',
                 'reset_attempted','release_attempted','release_returned'):
        cli.require(not worker[name],'failed cell reached a payload/exit stage')
    for original in plan['inputs']:
        path = store.checked(AREA/'source'/Path(original['path']).relative_to(ROOT))
        saved = cli.record(path)
        cli.require((saved['sha256'],saved['bytes'])==(original['sha256'],original['bytes']),
                    'frozen failed-cell source snapshot drift')
        records.append(saved)
    rows = list(parser.events(AREA/'events.jsonl'))
    result = trace([AREA/'sdk-000.log',AREA/'sdk-001.log'],rows,worker['dap'],worker['close_returned'])
    binding = build_binding(store)
    cli.require(records==[cli.record(r['path']) for r in records],'audit input drift')
    return dict(result='FAILED_ENTRY_RECONCILED_NO_PAYLOAD',trace=result,build=binding,inputs=records,
                historical_sdk_audit_passed=False,hardware_operations=0)


def predecessor(store):
    receipt = store.read(RECEIPT)
    cli.require(receipt['result']=='FAILED_ENTRY_RECONCILED_NO_PAYLOAD' and receipt['trace']['nvm_payload_writes']==0 and
                receipt['trace']['dp_restored'] is False and receipt['trace']['native_close']==1,
                'closed failure reconciliation required')
    cli.require({str(p) for p in INPUTS}.issubset({r['path'] for r in receipt['inputs']}),'missing audit bindings')
    for record in receipt['inputs']:
        cli.require(cli.record(store.checked(record['path']))==record,'failure audit input drift')
    worker = store.read(AREA/'worker.json')
    return dict(worker['component_results']['entry'],close_returned=worker['close_returned'])


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output-dir',type=Path,required=True)
    args = parser.parse_args()
    cli.require(Path.cwd()==ROOT and sys.flags.isolated and sys.flags.no_site and sys.dont_write_bytecode,'isolated root required')
    store = cli.Store(ROOT)
    out = store.checked(args.output_dir)
    store.checked(out/'result.json')
    cli.require(not out.exists(),'preserve audit evidence')
    result = audit(store)
    store.write(out/'result.json',result)
    print(result['result'],result['trace'])


if __name__=='__main__': main()
