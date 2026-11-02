"""P1-7 bounded startup observation using the existing SEGGER adapter."""
import argparse
import json
from pathlib import Path
import re
import sys

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'Tools/ota/p34-acceptance'))
import live_host as h
import live_mcu


def sdk_events(text):
    events, pending = [], None
    previous = -1.0
    for line in text.splitlines():
        match = re.match(r'T\d+ (\d+):(\d+\.\d+) (.*)', line)
        if not match:
            continue
        stamp = int(match[1]) * 1000 + float(match[2])
        h.require(stamp >= previous, 'nonmonotonic SDK clock')
        previous = stamp
        body = match[3].strip()
        call = re.match(r'JLINK_(ReadMemEx(?:_64)?|Go|Reset(?:Ex)?)\((.*)', body)
        if call:
            h.require(pending is None, 'incomplete SDK operation')
            pending = dict(kind=call[1], start_ms=stamp)
            if call[1].startswith('ReadMem'):
                args = re.match(r'0x([\dA-Fa-f]+), 0x([\dA-Fa-f]+) Bytes', call[2])
                h.require(args is not None, 'unrecognized native read')
                pending.update(address=int(args[1], 16), size=int(args[2], 16))
        elif pending and body.startswith('Data:'):
            pending['data'] = bytes.fromhex(body[5:].split('...')[0].strip())
        elif pending and body.startswith('- '):
            pending['end_ms'] = stamp
            if pending['kind'].startswith('ReadMem'):
                count = re.search(r'returns (\d+) \(0x', body)
                h.require(count and int(count[1]) == pending['size'], 'failed/short native read')
                if pending['size'] <= 16:
                    h.require(len(pending.get('data', b'')) == pending['size'], 'missing native bytes')
                    events.append(pending)
            else:
                events.append(pending)
            pending = None
    h.require(pending is None, 'truncated final native operation')
    return events


def summarize(events, addresses, count):
    gos = [e for e in events if e['kind'] == 'Go']
    resets = [e for e in events if e['kind'].startswith('Reset')]
    h.require(len(gos) == len(resets) == 1, 'not one reset/start observation')
    go, reset = gos[0], resets[0]
    h.require(reset['end_ms'] <= go['start_ms'], 'reset/start order')
    reads = {k: [e for e in events if e.get('address') == addr and e['start_ms'] > go['end_ms']]
             for k, addr in addresses.items()}
    h.require(all(len(items) == count for items in reads.values()), 'missing/extra samples')
    word = lambda e: int.from_bytes(e['data'][:4], 'little')
    signatures = [e for e in reads['rtt'] if e['data'][:10] == b'SEGGER RTT']
    h.require(signatures and reads['rtt'][0]['data'][:10] != b'SEGGER RTT', 'missing fresh signature edge')
    first = signatures[0]
    prior = [e for e in reads['rtt'] if e['end_ms'] < first['start_ms']][-1]
    timing = dict(lower_ms=prior['start_ms']-go['end_ms'], upper_ms=first['end_ms']-go['start_ms'],
                  reset_inclusive_upper_ms=first['end_ms']-reset['start_ms'])
    # Only a conservative upper bound can establish the <=1500 ms gate.
    startup = 'PASS' if timing['upper_ms'] <= 1500 else 'PRODUCT_FAIL' if timing['lower_ms'] > 1500 else 'EVIDENCE_GAP'
    pd = reads['pd2']
    highs = [i for i, e in enumerate(pd) if word(e) & 4]
    h.require(highs and highs[0] > 0, 'missing power-hold low/high transition')
    edge = highs[0]
    drops = [i for i in range(edge, len(pd)) if not word(pd[i]) & 4]
    h.require(pd[-1]['end_ms']-first['end_ms'] >= 3000, 'insufficient post-start sampling')
    boot = [i for i in range(count) if reads['boot_clock'][i]['end_ms'] < prior['start_ms']
            and word(reads['vtor'][i]) in (0, 0x08000000)
            and word(reads['boot_clock'][i]) == 288000000]
    h.require(len(boot) >= 2, 'no clock-bound Boot window')
    a, b = reads['boot_millis'][boot[0]], reads['boot_millis'][boot[-1]]
    elapsed = (b['start_ms']+b['end_ms']-a['start_ms']-a['end_ms'])/2
    delta = (word(b)-word(a)) & 0xffffffff
    clocks = [decode_clock(reads['crm'][i]['data']) for i in boot]
    clock_ok = all(value == 288000000 for value in clocks)
    tick_rate = delta/elapsed if elapsed > 0 else 0
    return dict(startup=dict(result=startup, **timing),
        powerHold=dict(result='PRODUCT_FAIL' if drops else 'PASS', samples=len(pd), drops=drops,
            first_high_lower_ms=pd[edge-1]['start_ms']-go['end_ms'],
            first_high_upper_ms=pd[edge]['end_ms']-go['start_ms'],
            observed_after_signature_ms=pd[-1]['end_ms']-first['end_ms'],
            max_sample_gap_ms=max(y['start_ms']-x['end_ms'] for x,y in zip(pd,pd[1:])),
            scope='No sampled drop, not an oscilloscope proof of arbitrarily short glitches'),
        clock=dict(result='PASS' if clock_ok else 'PRODUCT_FAIL', register_decoded_hz=sorted(set(clocks)),
            reported_hz=288000000, boot_samples=len(boot),
            scope='PLL source/multiplier/dividers decoded against bound 8MHz reference, not oscillator metrology'),
        tickCalibration=dict(result='PASS' if elapsed >= 500 and .98 <= tick_rate <= 1.02 else 'EVIDENCE_GAP',
            elapsed_ms=elapsed, tick_delta=delta, ticks_per_host_ms=tick_rate),
        recoveryKey='NOT_OBSERVED', batteryStartup='NOT_OBSERVED')


def decode_clock(data):
    h.require(len(data) == 12, 'CRM register read size')
    pll, cfg = (int.from_bytes(data[i:i+4], 'little') for i in (4,8))
    h.require((cfg >> 2) & 3 == 2, 'Boot not running from PLL')
    ms, ns, fr = pll & 15, (pll >> 6) & 511, (pll >> 16) & 7
    h.require(ms > 0 and ns > 0 and fr <= 5, 'invalid PLL divider')
    ahb = (0,0,0,0,0,0,0,0,1,2,3,4,6,7,8,9)[(cfg >> 4) & 15]
    return (8000000*ns // (ms*(1 << fr))) >> ahb


def commands(addresses, count):
    h.require(160 <= count <= 240, 'unbounded sample count')
    result = []
    for _ in range(count):
        for key, address in addresses.items():
            words = 4 if key == 'rtt' else 3 if key == 'crm' else 1
            result.append('mem32 0x%08X, %d' % (address, words))
        result.append('sleep 20')
    return result


def startup(plan_file, out, contract_file, matrix_file):
    plan = h.read_json(plan_file)
    h.require(plan['scope'] == 'P1-7-current-image-startup', 'wrong observation plan')
    contract, matrix = h.read_json(contract_file), h.read_json(matrix_file)
    h.require(contract['task_id'] == 'P1-7' and contract['status'] == 'FROZEN'
              and matrix['overall_result'] == 'NOT_RUN', 'frozen unexecuted P1-7 admission required')
    for pin in plan['pins']:
        h.pinned(pin)
    for name in ('p34-live-device.lock', 'p35-reconcile-device.lock', 'p35-pipeline.lock'):
        h.require(not (ROOT/'.cache'/name).exists(), 'device/pipeline already owned')
    out = h.fresh(out)
    h.save(out/'plan.json', plan)
    h.command(out, 'frozen-precheck', [sys.executable, '-I', '-S', '-B', '-X', 'utf8',
        ROOT/'Tools/acceptance/validate_bundle.py', '--contract', contract_file,
        '--matrix', matrix_file, '--repo-root', ROOT], h.environment(out), seconds=120)
    with h.device_owner(out):
        mcu = live_mcu.MCU(plan['mcu'], out)
        before = mcu.inspect('target', 'before')
        bound = mcu.bind('target')
        h.require(bound['rtt'] == plan['addresses']['rtt'], 'RTT symbol drift')
        freeze = before['registers']['freeze']
        idle = bound['table'][live_mcu.SYMBOLS['main_loop']][0]
        print('IDENTITY_AND_HEALTH_OK; stopping at storage-idle boundary', flush=True)
        data, console, _ = mcu.execute(['w4 0xE0042008, 0x%08X' % (freeze|0x1000),
            'SetBP 0x%08X, T, H' % idle, 'g', 'sleep 500', 'regs',
            ('sdio', live_mcu.REGISTERS['sdio'], 4), ('dhcsr', live_mcu.REGISTERS['dhcsr'], 4)],
            dict(sdio=4, dhcsr=4), 'idle-halt', seconds=30)
        pcs = re.findall(r'\bPC\s*=\s*([0-9a-fA-F]{8})', console)
        h.require(pcs and int(pcs[-1],16) == idle and int.from_bytes(data['dhcsr'],'little') & 0x20000
                  and not int.from_bytes(data['sdio'],'little') & 0x3800,
                  'idle halt unconfirmed; preserve state and reconcile before any reset')
        print('IDLE_BOUNDARY_OK; one reset/start with native timestamped sampling', flush=True)
        native = ['ClrBP 0', 'w4 0x%08X, 0' % bound['rtt'], 'r',
                  'w4 0xE0042008, 0x%08X' % freeze, 'g']
        native += commands(plan['addresses'], plan['samples'])
        _, _, sample_out = mcu.execute(native, {}, 'startup-samples', seconds=60)
        print('SAMPLING_COMPLETE; waiting for normal boot confirmation', flush=True)
        mcu.execute(['sleep 35000'], {}, 'settle', seconds=50)
        after = mcu.inspect('target', 'after')
        h.require(after['registers']['freeze'] == freeze, 'debug freeze was not restored')
        measured = summarize(sdk_events((sample_out/'sdk.log').read_text(encoding='utf8',errors='strict')),
                             plan['addresses'], plan['samples'])
        measured.update(bootBytes=plan['bootExecutable']['bytes'], retainedImage=plan['mcu']['images']['target']['image'],
            nativeLog=h.record(sample_out/'sdk.log'), resetCount=1, flashCount=0, eepromWrites=0,
            before=before, after=after, formalAcceptance='PARTIAL_P1_7_OBSERVATION')
        h.save(out/'result.json', measured)
        print(json.dumps({k:v for k,v in measured.items() if k not in ('before','after')}), flush=True)
    return 0


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--plan', required=True, type=Path)
    parser.add_argument('--out', required=True, type=Path)
    parser.add_argument('--contract', required=True, type=Path)
    parser.add_argument('--matrix', required=True, type=Path)
    args = parser.parse_args()
    h.require(Path.cwd() == ROOT and sys.flags.isolated and sys.flags.no_site and sys.dont_write_bytecode,
              'isolated project-root execution required')
    return startup(args.plan, h.checked(args.out), args.contract, args.matrix)


if __name__ == '__main__':
    raise SystemExit(main())
