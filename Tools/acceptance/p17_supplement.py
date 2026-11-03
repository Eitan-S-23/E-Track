"""Offline P1-7 successor: original startup, physical key and user battery report."""
import argparse
import hashlib
import json
from pathlib import Path
import re
import sys

sys.path.insert(0, str(Path(__file__).resolve().parent))
import p17_review as prior

h = prior.p.h
DEFINITIONS = 'eff2a5e9d6fc3ea2cf2efda28ae365764105a2027a2aac3033666945d453defb'
ENTRY = '8ce39d3e202717e73f107b08a73361a3ebda6a30831274cce44737b65ce583d3'
OPERATOR = '15b5e99dedaf8a38aa0dfe97914f65268d2648a50adcb9fb51df52a2b3d516c7'
BATTERY_QUOTE = '\u6d4b\u8bd5\u4e86\uff0c\u4e00\u5207\u90fd\u6b63\u5e38'


def digest(data):
    return hashlib.sha256(data).hexdigest()


def key_gate(stdout, native):
    long = re.findall(r'P17_RESULT long result=(\d+) ticks=(\d+) gpio=([0-9a-f]+)', stdout)
    short = re.findall(r'P17_RESULT short result=(\d+) ticks=(\d+) gpio=([0-9a-f]+)', stdout)
    h.require(len(long) == len(short) == 1 and 'P17_ERROR' not in stdout, 'missing/duplicate key results')
    h.require(long[0][0] == '1' and int(long[0][1]) >= 3000 and not int(long[0][2], 16) & 0x8000,
              'long physical hold not demonstrated')
    h.require(short[0][0] == '0' and 0 < int(short[0][1]) < 3000, 'short sample not rejected')
    ticks = [int(v, 16) for v in re.findall(
        r'Read 4 bytes @ address 0x20001030 \(Data = 0x([0-9A-F]{8})\)', native)]
    h.require(len(ticks) == 4 and ticks[1]-ticks[0] == int(long[0][1]) and
              ticks[3]-ticks[2] == int(short[0][1]), 'native tick/result mismatch')
    pcs = list(re.finditer(r"^03-\d+-\d+-(\d+)-[0-9A-F]+: Writing register 'pc' = 0x([0-9A-F]{8})",
                          native, re.M))
    h.require([p[2] for p in pcs] == ['08001E6D', '080019AA', '08001E6D', '080019AA'],
              'wrong predicate/caller PC sequence')
    spans = [int(pcs[i+1][1])-int(pcs[i][1]) for i in (0, 2)]
    h.require(spans[0] >= 3000 and 0 < spans[1] < 3000, 'native host interval contradicts key timing')
    for i, expected in ((0, 1), (2, 0)):
        chunk = native[pcs[i].end():pcs[i+1].start()]
        words = re.findall(r"Read register 'r0' \(4 bytes\) from hardware: 0x([0-9A-F]{8})", chunk)
        h.require(words and int.from_bytes(bytes.fromhex(words[-1]), 'little') == expected,
                  'native return register mismatch')
    h.require('Resetting target' not in native and 'Flash breakpoints disabled' in native,
              'unexpected reset/Flash breakpoint mode')
    return dict(longTicks=int(long[0][1]), shortTicks=int(short[0][1]), nativeTicks=ticks,
                hostCallToCallerRestoreMs=spans, callerRestored=True,
                limitation='Short rejection observed after 10 ticks, not a measured one-second stable press. '
                           'Host intervals include debugger overhead; no end-to-end recovery receiver entry.')


def battery_gate(report, context):
    h.require(report.get('quote') == BATTERY_QUOTE and report.get('source') == 'current-conversation-user',
              'missing firsthand battery report')
    h.require(report.get('procedure') == dict(usbDisconnected=True, jlinkDisconnected=True,
              batteryOnly=True, powerButtonStartup=True, enteredApp=True), 'wrong battery observation scope')
    h.require(BATTERY_QUOTE in context and 'P17-BATTERY-01' in context, 'battery report context missing')
    h.require(report.get('instrumented') is False, 'human report must not be relabeled as telemetry')
    return dict(result='PASS', source='User-reported physical observation', instrumented=False,
                limitation='No video, rail/current measurement, timestamped duration or endurance claim.')


def evaluate(read):
    startup = prior.evaluate(lambda n: read('predecessor/predecessor/predecessor/' + n))
    index = json.loads(read('supplement/index.json'))
    originals = {}
    for name, pin in index['files'].items():
        prior.safe_relative(name)
        data = read('supplement/' + name)
        h.require(len(data) == pin['bytes'] and digest(data) == pin['sha256'], 'supplement hash mismatch: ' + name)
        originals[name] = data

    def raw(name):
        h.require(name in originals, 'unindexed original: ' + name)
        return originals[name]

    def js(name):
        return json.loads(raw(name))

    for name, expected in (('gdb-definitions-05.gdb', DEFINITIONS), ('gdb-key-05.gdb', ENTRY),
                            ('execute-03.py', OPERATOR)):
        h.require(digest(raw('key/' + name)) == expected, 'different physical collector')
    key = key_gate(raw('key/gdb-key-03/gdb.stdout').decode('utf8'),
                   raw('key/gdb-key-03/server.log').decode('utf8'))
    for label in ('gdb', 'server', 'notify-hold', 'notify-release', 'notify-short'):
        prefix = 'key/gdb-key-03/' + label
        receipt = js(prefix + '.closed.json')
        h.require(receipt['cleanup_complete'] and receipt['exit_code'] == 0, 'unsuccessful key command')
        for stream in ('stdout', 'stderr'):
            h.require(digest(raw(prefix + '.' + stream)) == receipt[stream]['sha256'], 'receipt stream mismatch')
    h.require(raw('key/gdb-key-03/stage-finished.log').strip() == b'P17_STAGE finished', 'unfinished key batch')
    notices = js('key/gdb-key-03/notifications.json')
    h.require([n['stage'] for n in notices] == ['hold', 'release', 'short'] and all(n['delivered'] for n in notices),
              'missing physical-action reminders')
    original_root = 'predecessor/predecessor/predecessor/inputs/'
    app, boot = read(original_root + 'app-final.bin'), read(original_root + 'boot-full.bin')
    states = {}
    for label, prefix in (('before', 'key/reconcile-01/0001-current-identity/'),
                          ('after', 'post/inspect-01/0001-current-identity/')):
        samples = {Path(n).stem:data for n, data in originals.items() if n.startswith(prefix) and n.endswith('.bin')}
        h.require(samples['app'] == app and samples['boot'] == boot, 'retained binary changed')
        health = prior.p.live_mcu.health_gate(samples)
        h.require(health['registers']['freeze'] == 0, 'debug freeze not restored')
        prior.p.live_mcu.stack_observation(samples['guard'], samples['stack'])
        states[label] = samples
    for name in ('candidate_slot', 'backup_slot', 'recovery_slot', 'staging'):
        h.require(states['before'][name] == states['after'][name], 'storage original changed')
    failed = js('key/gdb-key-01/failed.json')
    h.require(failed['notifications'] == [], 'first host failure lineage changed')
    failed_stdout = raw('key/gdb-key-02/gdb.stdout').decode('utf8')
    h.require('Breakpoint 2, 0x080019aa' in failed_stdout and 'P17_RESULT' not in failed_stdout,
              'failed pre-call attempt hidden')
    h.require(raw('key/gdb-key-02/server.stdout').count(b'Resetting target') == 1, 'reset count changed')
    state = js('key/reconcile-02/result.json')
    h.require(state['pc'] == 0x080019aa and state['values']['dhcsr'] & 0x20000 and
              state['values']['hold'] & 4, 'missing same-checkpoint reconciliation')
    battery = battery_gate(js('battery.json'), raw('battery-context.md').decode('utf8'))
    timing = startup['observed']
    h.require(timing['tickCalibration']['result'] == 'PASS' and
              timing['powerHold']['first_high_lower_ms'] <= 1000 <= timing['powerHold']['first_high_upper_ms'],
              'original one-second Boot delay not supported')
    criteria = dict(startup['criteria'], C_RECOVERY_KEY='PASS', C_BATTERY='PASS')
    h.require(set(criteria.values()) == {'PASS'}, 'unresolved original requirement')
    return dict(outcome='P17_ORIGINALS_ACCEPTED', overallResult='PASS', criteria=criteria,
        originalStartup=startup, key=key, battery=battery, retainedAppSha256=digest(app),
        retainedBootSha256=digest(boot), supplementalInputCount=len(originals),
        supplementalIndexSha256=digest(read('supplement/index.json')), deviceOperations=0,
        originalPhysicalKeyResets=1, originalPhysicalKeyCalls=2,
        originalKeyDate='2026-11-03 UTC / 2026-11-04 Asia/Shanghai',
        originalOperator='Original independent acceptance session with user physical key actions',
        limitations=['Isolated predicate, not forced end-to-end recovery receiver.', key['limitation'],
                     battery['limitation'], 'Original startup/PD2/clock observation bounds remain unchanged.'])


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--bundle', type=Path, required=True)
    parser.add_argument('--out', type=Path, required=True)
    args = parser.parse_args()
    h.require(Path.cwd() == prior.p.ROOT and sys.flags.isolated and sys.flags.no_site and sys.dont_write_bytecode,
              'isolated active-root execution required')
    bundle, out = h.checked(args.bundle), h.checked(args.out)
    h.require(not out.exists(), 'preserve prior evaluation')
    result = evaluate(lambda name: h.checked(bundle / str(prior.safe_relative(name))).read_bytes())
    h.save(out, result)
    print(json.dumps({k:result[k] for k in ('outcome', 'overallResult', 'criteria', 'deviceOperations')}), flush=True)


if __name__ == '__main__':
    main()
