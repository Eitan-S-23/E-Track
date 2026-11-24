"""One schema5 FULL batch screen with original capture and complete raw readback."""
import json
from pathlib import Path
import re
import sys
import types

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'Tools/ota'))
import p34_radio_trial as radio
import p34_radio_followup as followup
import p34_batch_install as install
import p34_batch_archive as archive
import p34_capture_capacity as capacity

cli = radio.cli
AREA = install.AREA
TRIALS = AREA / 'trials'
ASSETS = AREA / 'assets/result.json'
READER = AREA / 'src/Tools/ota/p3-4-link-stats/batch_timing.py'
TEST = ROOT / 'tests/ota/test_p34_batch_trial.py'
HOST_TESTS = AREA / 'host-tests-001'


def clone(fn, **changes):
    return types.FunctionType(fn.__code__, dict(fn.__globals__, **changes), fn.__name__, fn.__defaults__, fn.__closure__)


def assets(s):
    value = s.read(ASSETS)
    cli.require(value['result'] == 'BATCH_ASSETS_VERIFIED' and value['hardware'] is False,
                'verified host assets required')
    for item in [*value['inputs'], value['receiver'], value['target'], value['package'],
                 *[x['package'] for x in value['negatives']]]:
        cli.require(cli.record(s.checked(item['path'])) == item, 'batch asset changed')
    cli.require(value['specification']['receiver'] == 30249 and value['specification']['target_version'] == 30250 and
                value['decoded']['byte_identical'] and value['decoded']['boot_ok'], 'wrong batch successor')
    return value


def archive_ready(s):
    value = s.read(archive.OUT / 'result.json')
    cli.require(value['result'] == 'INACTIVE_CAPTURE_ARCHIVED_VERIFIED' and value['usb_closed'] and
                value['app_stopped'] and value['protected_snapshot_unchanged'] and value['configuration_unchanged'] and
                len(value['remaining']) == 7 and value['no_delete'] and value['no_ota'], 'archive unresolved')
    for name in ('archive-001', 'install-001'):
        owner = s.read(AREA / 'runtime' / name / 'closed.json')
        cli.require(owner['worker_exit'] == 0 and not owner['forced_termination'], 'prior owner not closed')
    return value


def apk(s):
    report, _ = install.inputs(s)
    value = s.read(install.OUT / 'result.json')
    cli.require(value['result'] == 'FIXED_SIGNER_BATCH_UPDATE_VERIFIED' and value['usb_closed'] and
                value['installed']['sha256'] == report['apk']['sha256'] and value['snapshot_preserved'] and
                value['configuration_preserved'] and value['permissions_preserved'], 'installed batch APK unresolved')
    return report


def predecessor(s, group):
    return clone(radio.confirmed_predecessor, ORDER=('combined', 'batch'),
                 TRIALS=install.prior.PRIOR.parent)(s, 'batch', group)


def validate_config(value, group):
    cli.require(type(value.get('schema')) is int and value['schema'] == 5 and
                type(value.get('dataBatchFrames')) is int and value['dataBatchFrames'] == 3,
                'schema5 three-frame batch required')
    radio.validate_config(dict(value, schema=4), group)


def verify_batch(capture, messages, expected, sha):
    cli.require(type(expected.get('schema')) is int and expected['schema'] == 5 and
                type(expected.get('dataBatchFrames')) is int and expected['dataBatchFrames'] == 3 and
                expected.get('transferMode') == 'full' and expected.get('prefixBytes') == 0,
                'batch configuration contract mismatch')
    item = radio.original_verify(capture, messages, expected, sha)
    fields = set(expected) - {'target', 'firmwareLatestUrl'} | {'deviceAddress', 'endpointHost', 'configSha256'}
    cli.require(set(item) == fields and all(type(item.get(k)) is type(expected[k]) and item[k] == expected[k]
        for k in (*radio.EXTRA, 'pauseScanDuringOta', 'androidHighPriority', 'dataBatchFrames')),
        'batch observation differs from configuration')
    return item


radio.backend.verify_experiment = verify_batch


def full_metrics(messages, total, device):
    module = cli.load_module('batch_timing_screen', READER)
    observed = module.analyze(messages.splitlines(), total)
    values = [json.loads(line[len('OTA_LINK_STATS '):]) for line in messages.splitlines()
              if line.startswith('OTA_LINK_STATS ')]
    value = next(x for x in values if x.get('label') == 'upgrade')
    transfer, binding = value['transfer'], value['bind']
    cli.require(value['device'].lower() == device.lower() and transfer['durable']['finalOff'] == total and
                binding['writeMode'] == 'without' and binding['mtuChunkBytes'] == 244 and
                binding['mtuSource'] == 'negotiated', 'batch link or final durable mismatch')
    end = re.findall(r'^OTA_MONO MONO_END_ACK_OK monoUs=(\d+) wallUs=\d+ durable=(\d+)\r?$', messages, re.M)
    reboot = re.findall(r'^OTA_MONO MONO_REBOOT_VERIFIED monoUs=(\d+) wallUs=\d+\r?$', messages, re.M)
    cli.require(len(end) == len(reboot) == 1 and int(end[0][1]) == total and int(reboot[0]) > int(end[0][0]),
                'original END/reboot markers required')
    return dict(observed, installation_reconnect_seconds=(int(reboot[0]) - int(end[0][0])) / 1e6,
        transfer=transfer, binding=binding, gatt_writes=value['gattWrites'], discoveries=value['discovers'],
        platform_writes=value['platformWrites'],
        ack_threshold_eligible=transfer['ackSamples'] == 'complete' and transfer['ackEarlyInvalid'] == 0 and
            transfer['ackEarlyUnsent'] == 0 and transfer['ackLatency']['count'] == (total + 127) // 128,
        formal_reference_admitted=False,
        sample_scope='one batch screening transfer; partial ACK latency remains partial; no threshold acceptance')


class Batch(radio.Radio):
    def __init__(self, s, arm):
        cli.require(arm == 'batch', 'only the new unspent batch cell is admitted')
        self.arm, self.assets = arm, assets(s)
        self.proof, self.report = predecessor(s, self.assets), apk(s)
        path = Path(self.proof['plan']['profile']['path'])
        radio.backend.Backend.__init__(self, s, path, s.read(path), cli.RECONNECT_GROUP)
        self.receiver_version, self.target_version = 30249, 30250
        self.served_name = self.assets['specification']['served_name']

    def context(self, out):
        c = clone(radio.Radio.context, ORDER=(*radio.ORDER, 'batch'))(self, out)
        c.envelope = followup.fixed_envelope()
        old_load, original_sources = c.load, c.sources
        def load(name, path):
            module = old_load(name, path)
            if Path(path) == ROOT / 'Tools/ota/p34_full_trace.py':
                module.full_metrics = full_metrics
            return module
        c.load = load
        extras = [cli.record(p) for p in (__file__, TEST, ASSETS, READER, install.__file__,
            install.OUT / 'result.json', archive.__file__, archive.OUT / 'result.json',
            capacity.__file__, followup.__file__, AREA / 'apk-g1/apk.json')]
        c.sources = lambda: sorted({x['path']: x for x in [*original_sources(), *extras]}.values(), key=lambda x: x['path'])
        return c

    def phone(self, c, name, *, producer=False):
        phone = super().phone(c, name, producer=producer)
        original_config, original_provision = phone.config, phone.provision
        def config(*args):
            value = dict(original_config(*args), schema=5, dataBatchFrames=3)
            validate_config(value, self.assets)
            return value
        def provision(c, p, out, value):
            capacity.ensure_capacity(self.store, p, out / 'capacity', package=c.PKG,
                sentinel=c.apk['metadata']['device_observation']['sentinel'], target=c.TARGET,
                known_configs=self.known_configs(c))
            return original_provision(c, p, out, value)
        phone.config, phone.provision = config, provision
        return phone


def tests(s):
    path = HOST_TESTS / 'result.json'
    value = s.read(path)
    cli.require(value['result'] == 'PASS' and value['source'] == cli.record(__file__) and
                value['test'] == cli.record(TEST) and value['reader'] == cli.record(READER), 'source-bound host tests required')
    return cli.record(path)


if __name__ == '__main__':
    cli.require(Path.cwd() == ROOT and sys.flags.isolated and sys.flags.no_site and sys.dont_write_bytecode,
                'explicit root and isolated Python required')
    clone(radio.main, __file__=__file__, Radio=Batch, TRIALS=TRIALS, ORDER=('batch',),
          validate_config=validate_config, tests=tests, verify_pre_cell_failure=archive_ready)()
