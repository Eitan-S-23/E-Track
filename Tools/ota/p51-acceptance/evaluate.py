"""Offline P5 evaluation of original BCB, images, App captures and link clocks."""
import argparse
import hashlib
import json
from pathlib import Path
import re
import sys

sys.path.insert(0, str(Path(__file__).resolve().parent))
import run
import state_chain as sc
from observation import r
h, m = sc.h, sc.m
sys.path.insert(0, str(h.ROOT / 'Tools/ota/p3-4-link-stats'))
from acceptance_stats import rank


def final_native(folder, p):
    matches = list(folder.glob('*-final-full-readback'))
    h.require(len(matches) == 1, 'missing/ambiguous complete target readback')
    data = {path.stem: path.read_bytes() for path in matches[0].glob('*.bin')}
    h.require(data['app'] == h.pinned(p['mcu']['images']['target']['image']).read_bytes() and
              data['boot'] == h.pinned(p['mcu']['boot']).read_bytes() and
              data['header_after'] == data['app'][0x400:0x460], 'target/Boot raw bytes differ')
    value = m.health_gate(data)
    value['storage'] = m.storage_observation(data, p['mcu']['package'])
    run.final_storage(value, p['firmware'])
    return value


def points_from_originals(folder, p):
    images, tables, text = {}, {}, {}
    for role in ('base', 'target'):
        images[role] = h.pinned(p['mcu']['images'][role]['image']).read_bytes()
        tables[role] = m.symbols((folder / ('symbols-' + role) / 'nm.stdout').read_text())
        text[role] = {symbol: (folder / 'state-bindings' / (role + '-%d.stdout' % i)).read_text()
                      for i, symbol in enumerate(sc.SYMBOLS)}
    return sc.bind_points(images, tables, text)


def four_cell(folder, p):
    value = h.read_json(folder / 'result.json')
    h.require(value['outcome'] == 'CELL_OBSERVED' and value['inputs'] == p['firmware'] and
              value['package'] == p['mcu']['package'] and not (folder / 'failed.json').exists(), 'cell failed/unbound')
    raw = h.pinned(value['phone']).read_bytes()
    cid = value['initialInfo']['captureId']
    archive = r.audit_capture(raw, cid)
    states = r.Decoder().feed(raw)
    h.require(value['initialInfo'] in states and value['finalInfo'] in states and
              value['initialInfo']['event'] == value['finalInfo']['event'] == 'identity' and
              value['finalInfo']['seq'] > value['initialInfo']['seq'], 'INFO is not an original post-boundary identity')
    for row, final in ((value['initialInfo'], False), (value['finalInfo'], True)):
        r.bound(row, dict(firmware=p['firmware']), final=final)
        h.require(row['freshConnection'] and row['linkConnected'], 'stale/disconnected INFO')
    native = h.pinned(value['native']).parent
    points = points_from_originals(native, p)
    samples = []
    for phase in sc.PHASES:
        matches = list(native.glob('*-capture-' + phase))
        h.require(len(matches) == 1, 'missing original BCB phase')
        source = matches[0]
        data = {path.stem: path.read_bytes() for path in source.glob('*.bin')}
        pair, observed = sc.extract(data, (source / 'commander.stdout').read_text(), points, phase)
        h.require(pair == data['pair'], 'derived pair differs from original stack')
        samples.append(observed)
    h.require([row['state'] for row in samples] == [4, 1, 3, 4], 'incomplete state chain')
    final = final_native(native, p)
    return dict(channel=value['channel'], kind=value['kind'], states=[row['state'] for row in samples],
        package=value['package'], finalInfo=value['finalInfo'], rawImageVerified=True,
        original=h.record(folder / 'result.json'), rawCapture=h.record(h.pinned(value['phone'])),
        archive=archive, finalNative=final)


def transfer(group, package_bytes):
    summary, samples = group['summary'], group['ackLatencyUs']
    t = summary['transfer']
    first = t['begin']['first']
    elapsed = t['elapsedUs']
    h.require(group['label'] == 'upgrade' and t['outcome'] == 'ok' and
              type(elapsed) is int and elapsed > 0 and elapsed == t['endAckUs']-t['startUs'] and
              t['begin']['count'] == 1 and first['off'] == first['bitmap'] == 0 and
              t['durable']['finalOff'] == package_bytes, 'not a complete zero-start reference transfer')
    h.require(t['ackSamples'] == 'complete' and t['ackEarlyInvalid'] == 0 and
              t['segmentsUnique'] == len(samples) and t['segmentsUnique'] > 0, 'incomplete ACK population')
    parameters = {key: first[key] for key in ('protocol', 'ackTimeoutMs', 'maxRetries', 'windowSegments')}
    parameters.update({key: summary['bind'][key] for key in ('writeMode', 'mtuChunkBytes')})
    return dict(elapsedUs=elapsed, throughputKiBps=package_bytes*1e6/1024/elapsed,
        retransmissionRate=t['retransmitFrames']/t['segmentsUnique'], ackSamplesUs=samples,
        parameters=parameters, sourceClock=group['clockId'])


def long_group(blocks, p, clock):
    rows, captures, intervals = [], set(), []
    for folder in blocks:
        value = h.read_json(folder / 'result.json')
        h.require(value['outcome'] == 'BLE_BLOCK_OBSERVED' and value['inputs'] == p['firmware'] and
                  not (folder / 'failed.json').exists(), 'failed block cannot be dropped from the group')
        raw = h.pinned(value['original']).read_bytes()
        header = r.strict_json(raw.splitlines()[0][len('OTA_P35_CAPTURE '):])
        h.require(header['captureId'] not in captures, 'duplicate original capture')
        captures.add(header['captureId'])
        report = r.audit_link_diagnostics(raw, header['captureId'])
        groups = [group for group in report['groups'] if group['label'] == 'upgrade']
        h.require(len(groups) == len(value['cells']), 'missing/extra actual attempt')
        states = r.Decoder().feed(raw)
        for index, (cell, group) in enumerate(zip(value['cells'], groups), 1):
            h.require(cell['index'] == index and cell['initial'] in states and cell['finalInfo'] in states,
                      'result is not backed by original device events')
            r.bound(cell['finalInfo'], dict(firmware=p['firmware']), package=True, final=True)
            h.require(cell['finalInfo']['freshConnection'] and cell['finalInfo']['linkConnected'], 'no fresh completion')
            final_native(folder / ('cell-%02d' % index) / 'mcu', p)
            timing = transfer(group, p['mcu']['package']['bytes'])
            timing.update(captureId=header['captureId'], cell=index)
            rows.append(timing)
            intent = h.read_json(folder / ('cell-%02d' % index) / 'intent.json')
            intervals.append((intent['hostMonoNs'], cell['beginObservedMonoNs'], cell['hostFinishedMonoNs']))
    h.require(len(rows) >= 30, 'fewer than the predeclared first 30 attempts')
    parameters = rows[0]['parameters']
    h.require(all(row['parameters'] == parameters for row in rows), 'mixed candidate parameter groups')
    first30 = rows[:30]
    p95 = rank([row['elapsedUs'] for row in first30], 95)
    all_ack = [sample for row in rows for sample in row['ackSamplesUs']]
    p99 = rank(all_ack, 99)
    expected_timeout = min(2000, max(500, (3*p99+999)//1000))
    stable = parameters['maxRetries'] == 5 and parameters['ackTimeoutMs'] == expected_timeout and p95 <= 120000000 and all(
        row['elapsedUs'] <= 150000000 and row['throughputKiBps'] >= 9 and row['retransmissionRate'] <= .01 for row in rows)
    log = [json.loads(line) for line in (clock / 'monotonic.jsonl').read_text().splitlines()]
    h.require(log[0]['kind'] == 'start' and log[-1]['kind'] == 'stop' and
              len({row['clock_id'] for row in log}) == 1 and
              all(a['elapsed_ns'] <= b['elapsed_ns'] for a, b in zip(log, log[1:])), 'incomplete observer clock')
    clock_result = h.read_json(clock / 'clock-result.json')
    h.pinned(clock_result['log'])
    h.require(clock_result['elapsed_seconds'] == log[-1]['elapsed_ns']/1e9 and
              clock_result['observed_actions'] > 0, 'clock did not observe the campaign')
    observed_files = {row['original']['path']: row['original'] for row in log if row['kind'] == 'action_observed'}
    for source in (blocks[0] / 'intent.json', blocks[-1] / 'result.json'):
        pin = h.record(source)
        h.require(observed_files.get(pin['path']) == pin, 'observer clock did not bracket the actual campaign')
    span = conservative_span(intervals)
    return dict(attempts=len(rows), first30Successes=30, stability30=stable, parameters=parameters,
        p95Us=p95, p99Us=p99, requiredAckTimeoutMs=expected_timeout, observedSpanSeconds=span,
        observerSeconds=clock_result['elapsed_seconds'], transferSeconds=sum(row['elapsedUs'] for row in rows)/1e6,
        soakObserved=span >= 14400 and clock_result['elapsed_seconds'] >= span,
        note='Wall span includes explicit install/restore/UI intervals; it is not continuous payload-transfer time.',
        rows=rows)


def conservative_span(intervals):
    h.require(intervals and all(0 < start <= begin <= end for start, begin, end in intervals) and
              all(a[2] <= b[0] for a, b in zip(intervals, intervals[1:])), 'invalid campaign time ordering')
    # First ACK observation is after the first BEGIN. Last invitation is before
    # the last transfer. Their difference cannot add initial/final setup time.
    return max(0, intervals[-1][0]-intervals[0][1])/1e9


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--inputs', type=Path, required=True)
    parser.add_argument('--out', type=Path, required=True)
    args = parser.parse_args()
    h.require(Path.cwd() == h.ROOT and sys.flags.isolated and sys.flags.no_site and sys.dont_write_bytecode,
              'explicit worktree and isolated Python required')
    spec = h.read_json(args.inputs)
    out = h.fresh(args.out)
    try:
        results = [four_cell(h.checked(h.ROOT / item['out']), run.validate(h.read_json(h.pinned(item['inputs']))))
                   for item in spec['cells']]
        h.require(len(results) == 4 and {(row['channel'], row['kind']) for row in results} ==
                  {('sd', 'full'), ('ble', 'full'), ('sd', 'patch'), ('ble', 'patch')}, 'not exactly four combinations')
        h.save(out / 'four.json', dict(combinations=len(results), cells=results))
        p = run.validate(h.read_json(h.pinned(spec['long_inputs'])))
        blocks = []
        absent = False
        for path in spec['blocks']:
            folder = h.checked(h.ROOT / path)
            if folder.exists():
                h.require(not absent, 'a declared earlier block was omitted')
                h.require((folder / 'result.json').is_file() and not (folder / 'failed.json').exists(), 'unfinished/failed block')
                blocks.append(folder)
            else:
                absent = True
        result = long_group(blocks, p, h.checked(h.ROOT / spec['clock']))
        h.save(out / 'long.json', result)
        h.require(result['stability30'] and result['soakObserved'], 'required long-test gates not met')
        h.save(out / 'result.json', dict(outcome='OBSERVATIONS_MEET_P5_GATES', combinations=4, group=result))
        print('OBSERVATIONS_MEET_P5_GATES', flush=True)
    except BaseException as error:
        h.save(out / 'failed.json', dict(type=type(error).__name__, message=str(error), noDeviceOperations=True))
        raise


if __name__ == '__main__':
    main()
