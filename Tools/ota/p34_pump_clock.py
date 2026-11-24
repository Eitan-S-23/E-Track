"""Bounded read-only clock/scheduler sampling on retained30252; no RTT/reset."""
import argparse
import json
import os
from pathlib import Path
import struct
import sys
import time

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'Tools/ota'))
import p34_install_cost as host
import p34_hci_status as status
import baud_mcu as mcu

cli = host.cli
OUT = ROOT / '.cache/p34-hci/pump-clock-001'


def inputs(s):
    prior, _ = status.inputs(s)
    assets = s.read(ROOT / '.cache/p34-crc-screen/assets/result.json')
    target = assets['groups']['measure']['target']
    cli.require(cli.record(target['path']) == target and target['sha256'] ==
        '4733c5b3b2bb0da34b509821fa75bd2c642d0b27b641a3f7ee647062d4d800c6', 'retained target drift')
    build = s.read(ROOT / '.cache/p34-crc-screen/build/result.json')
    paths = {Path(x['path']).suffix: x for x in build['artifacts']}
    for item in paths.values():
        cli.require(cli.record(item['path']) == item, 'CRC build artifact drift')
    image, original = Path(target['path']).read_bytes(), Path(paths['.bin']['path']).read_bytes()
    cli.require(image[:0x400]+image[0x460:] == original[:0x400]+original[0x460:], 'map executable mismatch')
    text = Path(paths['.map']['path']).read_text(encoding='utf-8')
    symbols = mcu.bind_map(text, image, False)
    symbols['scheduler'] = mcu.map_bss(text, '_ZL11taskManager', 12)
    symbols['pump'] = mcu.map_symbol(text, 'HAL::BT_OtaPump()')
    for name in ('_ZL16disp_refr_px_sum', '_ZL13disp_refr_cnt', '_ZL18disp_refr_time_sum'):
        symbols[name] = mcu.map_bss(text, name, 4)
    return prior, image, symbols


def worker(s):
    prior, image, symbols = inputs(s)
    authority = mcu.native_authority()
    os.environ.update(host.environment(s, OUT))
    e = mcu.c.Evidence(s.checked(OUT / 'native'))
    link = mcu.c.Link(e, writable=False)
    result = dict(result='CLOCK_SAMPLE_INCOMPLETE', prior=prior, symbols=symbols,
        native_authority=authority, mru_before=mcu.c.record(mcu.c.MRU),
        reset=False, flash=False, rtt=False, ota=False, samples=[])
    try:
        link.connect()
        result['identity'] = link.image(image)
        def read(address, count=4):
            cli.require(0x20000000 <= address < address+count <= 0x20058000 or
                        (count == 4 and address in (0xE000E014,0xE0001004)), 'sample address bound')
            link.ram_reads.append((address,address+count))
            return link.read(address,count)
        def word(address):
            return struct.unpack('<I',read(address))[0]
        def tasks():
            head, tail, priority = struct.unpack('<III', read(symbols['scheduler'],12))
            rows, visited = [], set()
            while head:
                cli.require(head not in visited and len(rows) < 16, 'invalid task chain')
                visited.add(head)
                raw = read(head,28)
                _, function, period, previous, cost, error, following = struct.unpack('<7I',raw)
                cli.require(0x08010000 <= (function & ~1) < 0x08100000 and period < 1000000,
                            'invalid task record')
                rows.append(dict(address=head, function=function & ~1, period=period,
                                 previous=previous, cost=cost, error=error))
                head = following
            cli.require(rows and rows[-1]['address'] == tail, 'task tail mismatch')
            pump = [x for x in rows if x['function'] == symbols['pump']]
            cli.require(len(pump) == 1 and pump[0]['period'] == 20, 'unexpected pump task')
            return dict(priority=priority, pump=pump[0])
        for _ in range(11):
            link.running()
            start = time.monotonic_ns()
            result['samples'].append(dict(start_ns=start, tick=word(symbols['tick']),
                cycles=word(0xE0001004), clock=word(symbols['core_clock']),
                reload=word(0xE000E014), scheduler=tasks(),
                display={name:word(symbols[name]) for name in
                         ('_ZL16disp_refr_px_sum','_ZL13disp_refr_cnt','_ZL18disp_refr_time_sum')},
                end_ns=time.monotonic_ns()))
            time.sleep(.5)
        link.running()
        cli.require(link.read(mcu.c.APP,0x460) == image[:0x460], 'App changed during sampling')
        result['result'] = 'RETAINED_IDLE_CLOCK_SAMPLED'
    except Exception as error:
        result.update(error=type(error).__name__, detail=str(error))
    finally:
        link.close()
        result.update(reader_closed=not link.opened, mru_after=mcu.c.record(mcu.c.MRU))
        s.write(OUT / 'result.json',result)
        e.events.close()
        e.ledger.close()
    print(json.dumps(result),flush=True)
    cli.require('error' not in result,'read-only observation needs reconciliation')


def main():
    global OUT
    cli.require(Path.cwd() == ROOT and sys.flags.isolated and sys.flags.no_site and
                sys.dont_write_bytecode, 'explicit root and isolated Python required')
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('mode',choices=('check','launch','worker'))
    parser.add_argument('--phase',choices=('clock','display'),default='clock')
    args=parser.parse_args()
    mode=args.mode
    if args.phase=='display':
        OUT=ROOT/'.cache/p34-hci/pump-display-001'
    s=cli.Store(ROOT)
    prior, _, symbols=inputs(s)
    if mode=='check':
        print(json.dumps(symbols)); return
    owner=cli.load_module('pump_clock_owner',ROOT/'.cache/p3-4-screening-20260922/supervisor.py')
    if mode=='launch':
        cli.require(not OUT.exists(),'preserve clock observation')
        for name in ('intent.json','result.json','host','native'): s.checked(OUT/name)
        s.write(OUT/'intent.json',dict(source=cli.record(__file__),prior=prior,symbols=symbols,
            seconds=180, reset=False,flash=False,rtt=False,ota=False,
            scope='retained image readback then 11 idle clock/scheduler samples; not an OTA measurement'))
        print(owner.owned.launch(s.checked(ROOT/'.cache/p34-hci/runtime'/OUT.name),
                                 Path(__file__),['worker','--phase',args.phase],180))
    else:
        cli.require(owner.owned.in_job(),'finite owned reader required')
        lock=cli.load_module('pump_clock_lock',ROOT/'Tools/ota/repeat_cycle.py')
        s.checked(lock.RUNS/'device.lock')
        with lock.device_lock():
            worker(s)


if __name__=='__main__':
    main()
