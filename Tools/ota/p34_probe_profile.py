"""Strict schema6 admission for the fixed-radio, same-link INFO comparison."""
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'Tools/ota'))
import p34_batch_trial as batch
import p34_probe_assets as assets_api

cli = batch.cli
FLAGS = ('pauseScanDuringOta', 'androidHighPriority', 'dataBatchFrames', 'reuseRebootInfoLink')


def assets(s, arm):
    cli.require(arm in ('control', 'reuse'), 'unlisted probe arm')
    value = s.read(assets_api.OUT / 'result.json')
    cli.require(value['result'] == 'PROBE_ASSETS_VERIFIED' and value['hardware'] is False, 'verified assets required')
    group = value['groups'][arm]
    for item in [*value['inputs'], group['receiver'], group['target'], group['package'],
                 *[x['package'] for x in group['negatives']]]:
        cli.require(cli.record(s.checked(item['path'])) == item, 'probe asset changed')
    spec = group['specification']
    cli.require(spec['target_version'] == (30255 if arm == 'control' else 30256) and
                spec['receiver'] == spec['target_version'] - 1 and
                spec['reuseRebootInfoLink'] is (arm == 'reuse') and
                group['receiver_bindings']['whole_boot'] == group['target_bindings']['whole_boot'] and
                all(group['decoded'][k] for k in ('passed', 'byte_identical', 'boot_ok', 'guards_ok', 'workspace_lifecycle_ok')),
                'wrong probe asset identity')
    return dict(group, specification=dict(spec, pauseScanDuringOta=True, androidHighPriority=True, dataBatchFrames=3))


def validate_config(value, group):
    cli.require(type(value.get('schema')) is int and value['schema'] == 6 and
                type(value.get('reuseRebootInfoLink')) is bool and
                value['reuseRebootInfoLink'] is group['specification']['reuseRebootInfoLink'], 'wrong probe policy')
    batch.validate_config(dict(value, schema=5), group)
    expected_keys = {'schema', 'runId', 'target', 'requestedBaud', 'reuseGatt', 'withoutResponse',
        'firmwareLatestUrl', 'packageBytes', 'packageSha256', 'currentVersionCode', 'currentImageSha256',
        'targetVersionCode', 'targetImageSha256', 'senderWindowSegments', 'transferMode', 'prefixBytes',
        *batch.radio.EXTRA, *FLAGS}
    cli.require(set(value) == expected_keys, 'unknown or missing probe config field')


def verify(capture, messages, expected, sha):
    cli.require(type(expected.get('schema')) is int and expected['schema'] == 6 and
                type(expected.get('reuseRebootInfoLink')) is bool and expected.get('transferMode') == 'full',
                'schema6 FULL observation required')
    item = batch.radio.original_verify(capture, messages, expected, sha)
    fields = set(expected) - {'target', 'firmwareLatestUrl'} | {'deviceAddress', 'endpointHost', 'configSha256'}
    cli.require(set(item) == fields and all(type(item.get(k)) is type(expected[k]) and item[k] == expected[k]
        for k in (*batch.radio.EXTRA, *FLAGS)), 'probe observation policy differs')
    return item
