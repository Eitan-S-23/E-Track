"""Correlate original HCI frames with an already completed OTA, offline only."""
import argparse
import collections
import hashlib
import json
from pathlib import Path
import runpy
import struct
import sys

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'Tools/ota'))
import p34_hci_att as att
import p34_hci_compare as compare

require = compare.require


def frames(rows):
    """Reassemble one characteristic/direction without losing HCI boundaries."""
    require(len({(r['generation'], r['direction'], r['value_handle']) for r in rows}) <= 1,
            'mixed characteristic streams')
    pending = bytearray()
    origins = collections.deque()
    result = []
    for row in rows:
        raw = bytes.fromhex(row['value_hex'])
        require(raw, 'empty characteristic fragment')
        pending.extend(raw)
        origins.append([len(raw), row])
        while len(pending) >= 8:
            require(pending[:2] == b'\xa5\x5a', 'invalid stream prefix; never skip bytes')
            length = 10 + int.from_bytes(pending[6:8], 'little')
            require(length <= 4106, 'protocol frame bound')
            if len(pending) < length:
                break
            data = bytes(pending[:length])
            compare.valid_frame(data)
            first, left, last = origins[0][1], length, None
            while left:
                size, last = origins[0]
                consumed = min(left, size)
                left -= consumed
                if consumed == size:
                    origins.popleft()
                else:
                    origins[0][0] -= consumed
            result.append(dict(command=data[2], session=data[3],
                sequence=int.from_bytes(data[4:6], 'little'), payload=data[8:-2],
                start_record=first['start_record'], end_record=last['end_record'],
                start_timestamp=first['start_timestamp'], end_timestamp=last['end_timestamp']))
            del pending[:length]
    require(not pending, 'incomplete protocol frame')
    return result


def declarations(rows):
    found = {}
    for row in rows:
        raw = bytes.fromhex(row['att_hex'])
        if row['direction'] != 'rx' or raw[:2] != b'\x09\x07':
            continue
        require((len(raw)-2) % 7 == 0, 'bad characteristic declaration')
        for offset in range(2, len(raw), 7):
            _, props, handle, uuid = struct.unpack_from('<HBHH', raw, offset)
            if uuid in (0xfff1, 0xfff2):
                require(uuid not in found or found[uuid] == (handle, props),
                        'conflicting characteristic declarations')
                found[uuid] = (handle, props)
    require(0xfff1 in found and 0xfff2 in found and
            found[0xfff1][1] & 0x10 and found[0xfff2][1] & 4,
            'FFF1 notify and FFF2 write capabilities required')
    return found[0xfff2][0], found[0xfff1][0]


def verify_data(data_frames, package):
    require(data_frames, 'no DATA frames')
    offset = 0
    for sequence, frame in enumerate(data_frames, 1):
        payload = frame['payload']
        require(frame['sequence'] == sequence and len(payload) > 4 and
                int.from_bytes(payload[:4], 'little') == offset,
                'DATA sequence/offset differs or contains retries')
        value = payload[4:]
        require(value == package[offset:offset+len(value)], 'DATA bytes differ from package')
        offset += len(value)
    require(offset == len(package), 'incomplete package')


def completions(data, connection):
    """FIFO ACL buffer completion reports, not exact radio transmission times."""
    pending, completed = collections.deque(), {}
    at, index = 16, 0
    while at < len(data):
        _, size, flags, _, stamp = struct.unpack_from('>IIIIQ', data, at)
        packet = data[at+24:at+24+size]
        at += 24+size
        index += 1
        if not connection['start_record'] <= index <= connection['end_record']:
            continue
        if packet[0] == 2 and not flags & 1 and \
                int.from_bytes(packet[1:3], 'little') & 0xfff == connection['handle']:
            pending.append(index)
        if packet[:2] != b'\x04\x13':
            continue
        require(len(packet) >= 4 and len(packet) == 4+packet[3]*4, 'bad completion event')
        for offset in range(4, len(packet), 4):
            handle, count = struct.unpack_from('<HH', packet, offset)
            if handle != connection['handle']:
                continue
            require(count <= len(pending), 'completion count exceeds owned ACL packets')
            for _ in range(count):
                completed[pending.popleft()] = dict(record=index, timestamp=stamp)
    return completed


def block_timings(data_frames, acks, completed):
    require(len(data_frames) == len(acks), 'complete block ACK map required')
    by_sequence = {f['sequence']: f for f in acks}
    blocks = []
    for offset in range(0, len(data_frames), 32):
        group = data_frames[offset:offset+32]
        first, last = group[0], group[-1]
        ack = by_sequence[last['sequence']]
        durable = int.from_bytes(ack['payload'][1:5], 'little')
        require(durable == int.from_bytes(last['payload'][:4], 'little') + len(last['payload'])-4,
                'block ACK does not confirm its complete durable payload')
        require(last['end_record'] in completed, 'last DATA controller completion missing')
        done = completed[last['end_record']]
        following = data_frames[offset+32] if offset+32 < len(data_frames) else None
        blocks.append(dict(block=offset//32, durable=durable,
            send_ms=(last['end_timestamp']-first['start_timestamp'])/1000,
            tail_ms=(ack['end_timestamp']-last['end_timestamp'])/1000,
            controller_report_ms=(done['timestamp']-last['end_timestamp'])/1000,
            after_controller_report_ms=(ack['end_timestamp']-done['timestamp'])/1000,
            next_send_ms=(following['start_timestamp']-ack['end_timestamp'])/1000 if following else None,
            last_data_record=last['end_record'], completion_record=done['record'],
            durable_ack_record=ack['end_record']))
    keys = ('send_ms', 'tail_ms', 'controller_report_ms', 'after_controller_report_ms', 'next_send_ms')
    totals = {key: sum(b[key] for b in blocks if b[key] is not None) for key in keys}
    return dict(blocks=blocks, totals=totals,
        negative_samples={key: sum(b[key] < 0 for b in blocks if b[key] is not None) for key in keys},
        scope='Same HCI clock, 32-frame durable blocks. Completion notification latency is included; '
              'after-controller time is not isolated MCU Flash time. Tail equals the two controller subspans.')


def analyze(data, package, expected):
    require(hashlib.sha256(package).hexdigest() == expected['packageSha256'] and
            len(package) == expected['packageBytes'], 'original package binding differs')
    decoded = att.analyze(data, expected['deviceAddress'])
    results, identities = [], []
    for connection in decoded['connections']:
        rows = [r for r in decoded['att'] if r['generation'] == connection['generation']]
        tx_handle, rx_handle = declarations(rows)
        tx_rows = [r for r in rows if r['direction'] == 'tx' and r.get('value_handle') == tx_handle]
        rx_rows = [r for r in rows if r['direction'] == 'rx' and r.get('value_handle') == rx_handle]
        tx, rx = frames(tx_rows), frames(rx_rows)
        info = [f for f in rx if f['command'] == 0x80]
        for frame in info:
            payload = frame['payload']
            require(len(payload) == 50, 'INFO length differs')
            identities.append(dict(generation=connection['generation'],
                version=int.from_bytes(payload[12:16], 'little'), sha256=payload[16:48].hex(),
                record=frame['end_record'], timestamp=frame['end_timestamp']))
        begins = [f for f in tx if f['command'] == 1]
        if not begins:
            continue
        require(len(begins) == 1, 'multiple BEGIN frames; explicit trial selection required')
        begin = begins[0]
        require(len(begin['payload']) == 101 and begin['payload'][5:37].hex() == expected['packageSha256'],
                'BEGIN package binding differs')
        data_frames = [f for f in tx if f['command'] == 2]
        verify_data(data_frames, package)
        ends = [f for f in tx if f['command'] == 3]
        require(len(ends) == 1 and ends[0]['payload'].hex() == expected['packageSha256'], 'END differs')
        end = ends[0]
        require(len({f['session'] for f in [*data_frames, end]}) == 1, 'mixed OTA sessions')
        session = end['session']
        acks = [f for f in rx if f['session'] == session and f['command'] == 0x82]
        require([f['sequence'] for f in acks] == [f['sequence'] for f in data_frames] and
                all(len(f['payload']) == 9 and f['payload'][0] == 0 for f in acks),
                'ACK set differs or contains errors')
        final = [f for f in rx if f['command'] == 0x83 and f['session'] == session]
        require(len(final) == 1 and final[0]['sequence'] == end['sequence'] and
                len(final[0]['payload']) == 9 and final[0]['payload'][0] == 0 and
                int.from_bytes(final[0]['payload'][1:5], 'little') == len(package), 'END ACK differs')
        bound = dict(connection, end_record=connection.get('end_record', decoded['capture']['packets']))
        parameters = compare.link_parameters(data, bound)
        first, last = data_frames[0], data_frames[-1]
        active = [e for e in parameters if e['record'] <= first['start_record']]
        changes = [e for e in parameters if first['start_record'] < e['record'] <= last['end_record']]
        duration = (final[0]['end_timestamp'] - begin['start_timestamp']) / 1e6
        writes = [r for r in tx_rows if first['start_record'] <= r['start_record'] <= last['end_record']]
        stamps = [r['start_timestamp'] for r in writes]
        gaps = sorted((b-a)/1000 for a,b in zip(stamps, stamps[1:]))
        results.append(dict(generation=connection['generation'], data_frames=len(data_frames),
            ack_frames=len(acks), data_att_chunks=len(writes), parameters_before_data=active,
            parameters_during_data=changes, begin_record=begin['start_record'],
            end_ack_record=final[0]['end_record'], end_ack_timestamp=final[0]['end_timestamp'],
            hci_begin_to_end_ack_seconds=duration, hci_package_kb_s=len(package)/1000/duration,
            data_write_gap_ms=dict(p50=gaps[len(gaps)//2], p95=gaps[int(len(gaps)*.95)],
                                   maximum=max(gaps)),
            tx_handle=tx_handle, rx_handle=rx_handle,
            block_timing=block_timings(data_frames, acks, completions(data, bound))))
    require(len(results) == 1, 'one full package-matched OTA required')
    result = results[0]
    old = [i for i in identities if i['generation'] == result['generation'] and
           i['version'] == expected['currentVersionCode'] and i['sha256'] == expected['currentImageSha256']]
    target = [i for i in identities if i['record'] > result['end_ack_record'] and
              i['version'] == expected['targetVersionCode'] and i['sha256'] == expected['targetImageSha256']]
    require(old and len(target) == 1, 'old and post-END target identity bindings required')
    result.update(result='ORIGINAL_OTA_HCI_CORRELATED', identities=identities,
        hci_end_ack_to_target_seconds=(target[0]['timestamp']-result['end_ack_timestamp'])/1e6,
        absolute_clock='UNVERIFIED_VENDOR_WALL_CLOCK; only same-HCI-clock differences used',
        air_time='NOT_MEASURED; host-controller capture is not over-air capture',
        phy='UNKNOWN unless an explicit PHY observation exists')
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--hci', type=Path, required=True)
    parser.add_argument('--report', type=Path, required=True)
    parser.add_argument('--out', type=Path, required=True)
    args = parser.parse_args()
    require(Path.cwd() == ROOT and sys.flags.isolated and sys.flags.no_site and sys.dont_write_bytecode,
            'explicit root and isolated Python required')
    guard = runpy.run_path(str(ROOT / '.agents/skills/e-track-flutter-debug/scripts/host_io.py'))
    out = guard['checked_output'](ROOT, args.out)
    require(not out.exists(), 'preserve prior correlation')
    report = json.loads(args.report.read_bytes())
    require(report['result'] == 'FULL_INSTALL_VERIFIED', 'completed original report required')
    result = analyze(args.hci.read_bytes(), Path(report['inputs']['download']['path']).read_bytes(),
                     report['summary']['input'])
    result['sources'] = [dict(path=str(p), sha256=hashlib.sha256(p.read_bytes()).hexdigest())
        for p in (Path(__file__), Path(att.__file__), Path(compare.__file__), args.hci, args.report)]
    guard['write_json'](ROOT, out, result)
    print(json.dumps(result, indent=2))


if __name__ == '__main__':
    main()
