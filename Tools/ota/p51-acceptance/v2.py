"""Prospective V2-only automation guards; historical bundles stay immutable."""
import hashlib
import json
from pathlib import Path
import re
import struct
import sys
import zlib

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'p34-acceptance'))
import live_host as h

PROFILE = dict(protocol=2, windowSegments=24, dataBatchFrames=12)


def same_file(left, right):
    h.pinned(left)
    h.pinned(right)
    h.require((left['bytes'], left['sha256']) == (right['bytes'], right['sha256']),
              'V2 artifact identity differs')


def live_plan(plan):
    fw, config = plan.get('firmware', {}), plan.get('benchmark', {})
    h.require(type(fw.get('protocol')) is int and fw['protocol'] == 2 and
              config.get('wire') == 'v2-only' and config.get('link') == PROFILE,
              'V2-only execution inputs required; historical plans cannot run devices')
    proof = h.read_json(h.pinned(config['receiver_proof']))
    h.require(proof['outcome'] == 'V2_ONLY_KEYED_RECEIVER_VERIFIED' and proof['keyBindingMatches'],
              'verified keyed V2 receiver required')
    keyed = h.read_json(h.pinned(proof['keyedBuild']))
    h.require(keyed['commitSha'] == proof['source'] and
              keyed['buildConfiguration']['actualProfile'] == 'p34-v2-candidate' and
              all(row['exitCode'] == row['errorLines'] == 0 for row in keyed['steps']) and
              [row['label'] for row in keyed['steps']] == ['configure', 'build', 'size'],
              'V2 keyed build did not succeed')
    build = h.read_json(h.pinned(config['app_build']))
    h.require(build['source'] == proof['productSource'], 'APK and V2 receiver product source differ')
    for role, field in (('base', 'receiver'), ('target', 'unpackagedTarget')):
        for kind in ('image', 'elf', 'map'):
            same_file(plan['mcu']['images'][role][kind], proof[field][kind])
    same_file(plan['mcu']['boot'], proof['boot'])
    restore_binding(plan)
    return config


def restore_binding(plan):
    config, mcu = plan['benchmark'], plan['mcu']
    binding = h.read_json(h.pinned(config['restore_binding']))
    h.require(binding.get('schema') == 'p51-v2-restore-binding-v1', 'V2 restore binding required')
    for field, role in (('base', 'base'), ('target', 'target')):
        same_file(binding[field], mcu['images'][role]['image'])
    same_file(binding['boot'], mcu['boot'])
    for kind in ('image', 'elf', 'map'):
        same_file(binding['restore'][kind], mcu['images']['restore'][kind])
    base = h.pinned(binding['base']).read_bytes()
    target = h.pinned(binding['target']).read_bytes()
    raw = h.pinned(binding['restore']['image']).read_bytes()
    before, after = (struct.unpack_from('<I', data, 0x408)[0] for data in (target, base))
    h.require(before > after > 0 and struct.unpack_from('<I', raw, 0x408)[0] == before,
              'restore image version is not the actual V2 target')
    expected = struct.pack('<4I', before, after, len(base), zlib.crc32(base))
    h.require(expected in raw and bytes.fromhex(binding['base']['sha256']) in raw and
              bytes.fromhex(binding['boot']['sha256']) in raw,
              'restore executable embeds another version, backup or Boot; no device action')
    build = h.read_json(h.pinned(binding['build']))
    h.require(build['result'] == 'APP_BUILT' and build['variant'] == 'restore' and not build['boot_built'],
              'not a successful App-only restore build')
    same_file(build['restore_bindings'], binding['bindings_header'])
    artifacts = {Path(row['path']).suffix: row for row in build['artifacts']}
    for kind in ('elf', 'map'):
        same_file(artifacts['.' + kind], binding['restore'][kind])
    compiled = h.pinned(artifacts['.bin']).read_bytes()
    h.require(len(compiled) == len(raw) and compiled[:0x400] == raw[:0x400] and
              compiled[0x460:] == raw[0x460:], 'restore differs beyond finalized header')
    return binding


def states(rows):
    for row in rows:
        protocol = row['protocol']
        h.require(protocol is None or type(protocol) is int and protocol == 2,
                  'V1 or unknown transfer observed; stop the V2 campaign')
        h.require(row['bitmap'] is None, 'V2 state cannot carry a V1 bitmap')
        if row['event'] in ('beginAck', 'data'):
            h.require(protocol == 2 and type(row['session']) is int and 0 < row['session'] <= 255,
                      'transfer event has no accepted V2 session')
    return rows


def summary(value, *, expected=None):
    transfer = value['transfer']
    first = transfer['begin']['first']
    h.require(type(first.get('protocol')) is int and first['protocol'] == 2 and
              type(first.get('epoch')) is int and 0 < first['epoch'] <= 0xffffffff and
              type(first.get('session')) is int and 0 < first['session'] <= 255 and
              type(first.get('seq')) is int and 0 <= first['seq'] <= 0xffff,
              'timing summary has no accepted V2 BEGIN/epoch/session')
    window = first['windowSegments']
    batch = transfer.get('dataBatch', {}).get('maxFrames', 1)
    h.require(type(window) is int and 1 <= window <= PROFILE['windowSegments'] and
              type(batch) is int and batch in (1, 3, 12), 'unsupported V2 window/batch geometry')
    actual = dict(protocol=2, windowSegments=window, dataBatchFrames=batch)
    h.require(expected is None or actual == expected, 'actual V2 link differs from the declared test profile')
    return actual


def diagnostics(groups, *, expected=None):
    for group in groups:
        h.require(group['label'] != 'prefix-probe', 'retired prefix probe in V2 recording')
        for line in group['lines']:
            match = re.match(r'OTA_LINK_SAMPLE label=\S+ kind=control_(?:start|end) us=\d+ cmd=(\d+)\b', line)
            h.require(match is None or int(match[1]) not in (1, 2, 3, 4),
                      'retired V1 command in V2 recording')
        if group['label'] == 'upgrade' and group['summary']['transfer'].get('begin'):
            summary(group['summary'], expected=expected)


def recording(raw, capture_id, *, expected=None):
    # Use exactly the parser used after a physical block, not a test-only decoder.
    sys.path.insert(0, str(h.ROOT / 'Tools/ota/p35-automation'))
    import runner
    report = runner.audit_link_diagnostics(raw, capture_id)
    rows = states(runner.Decoder().feed(raw))
    diagnostics(report['groups'], expected=expected)
    return report, rows


def cli():
    import argparse
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--capture', type=Path, required=True)
    parser.add_argument('--capture-id', required=True)
    parser.add_argument('--expected-profile', action='store_true')
    args = parser.parse_args()
    report, rows = recording(args.capture.read_bytes(), args.capture_id,
                             expected=PROFILE if args.expected_profile else None)
    upgrades = [group for group in report['groups'] if group['label'] == 'upgrade']
    h.require(upgrades, 'no actual upgrade diagnostic group')
    print(json.dumps(dict(outcome='V2_RECORDING_PARSED', records=len(rows), upgrades=len(upgrades),
                         sha256=hashlib.sha256(args.capture.read_bytes()).hexdigest(), deviceOperations=0)))


if __name__ == '__main__':
    cli()
