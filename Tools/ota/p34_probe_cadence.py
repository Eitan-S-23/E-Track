"""One same-APK successor with100ms probe interval; unchanged2s INFO timeout."""
import copy
import json
import os
from pathlib import Path
import sys
from types import SimpleNamespace

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'Tools/ota'))
import p34_probe_trial as previous

cli, batch, ui = previous.cli, previous.batch, previous.ui
AREA = ROOT / '.cache/p34-probe-cadence'
OUT = AREA / 'trial'
ASSETS = AREA / 'assets'
PRIOR = previous.TRIALS / 'reuse'
TEST = ROOT / 'tests/ota/test_p34_probe_cadence.py'
HOST = AREA / 'tests-001'


def make_assets(s):
    cli.require(not ASSETS.exists() and not os.environ.get('OTA_AES_KEY'), 'preserve assets/no key override')
    report = ui.archival.proof(s, PRIOR)
    old = previous.profile.assets(s, 'reuse')
    cli.require(report['summary']['input']['targetImageSha256'] == old['target']['sha256'], 'retained receiver differs')
    host = ui.screen.host
    env = host.environment(s, ASSETS)
    os.environ.update(env)
    sys.path.insert(0, str(Path(sys.base_prefix) / 'Lib/site-packages'))
    pack = cli.load_module('cadence_pack', ui.AREA / 'f/Tools/etu_pack.py')
    unpack = cli.load_module('cadence_unpack', ui.AREA / 'f/Tools/etu_unpack.py')
    tools = cli.load_module('cadence_negatives', ROOT / 'Tools/ota/prepare_baud_assets.py')
    shared = previous.profile.assets_api.ui.shared
    decoder = s.read(ROOT / '.cache/p34-next/n03/assets/result.json')['decoder']
    cli.require(cli.record(s.checked(decoder['path'])) == decoder, 'decoder changed')
    receiver = old['target']
    before = Path(receiver['path']).read_bytes()
    raw = bytearray(before)
    raw[0x400:0x460] = pack.build_fw_header(bytes(raw), '3.2.57-p34p', 1786320000)
    cli.require(before[:0x400] + before[0x460:] == raw[:0x400] + raw[0x460:], 'executable changed')
    target = s.raw(ASSETS / 'target.bin', bytes(raw))
    identity = shared.identity(bytes(raw), unpack)
    cli.require(identity['version_code'] == 30257, 'target version differs')
    blob = shared.wrap_payload(pack, pack.lzma_alone_encode(bytes(raw)), before, bytes(raw), kind='full')
    package = s.raw(ASSETS / 'p34-probe-fast-full.etu', blob)
    def native(label, item, expected):
        return json.loads(host.command(s, ASSETS, label,
            [decoder['path'], item['path'], receiver['path'], target['path'], expected], env, 180))
    decoded = native('positive', package, 'ok')
    cli.require(all(decoded[k] for k in ('passed', 'byte_identical', 'boot_ok', 'guards_ok', 'workspace_lifecycle_ok')),
                'native positive failed')
    negatives = []
    for label, broken, expected in tools.negatives(blob, 30256):
        item = s.raw(ASSETS / (label + '.etu'), broken)
        result = native(label, item, expected)
        cli.require(result['passed'] and result['prepares'] == 0, 'negative reached preparation')
        negatives.append(dict(name=label, package=item, native=result))
    bindings = copy.deepcopy(old['target_bindings'])
    bindings['profile'].update(image=target, identity=identity, prefix=bytes(raw[:0x460]).hex())
    group = dict(specification=dict(old['specification'], receiver=30256, target_version=30257,
        version_name='3.2.57-p34p', served_name='p34-probe-fast-full.etu', release_key='p34-probe-fast',
        rebootProbeIntervalMs=100), receiver=receiver, receiver_bindings=old['target_bindings'], target=target,
        target_identity=identity, target_bindings=bindings, package=package, package_kind='full',
        decoded=decoded, negatives=negatives)
    s.write(ASSETS / 'result.json', dict(result='CADENCE_ASSETS_VERIFIED', hardware=False, group=group,
        inputs=[cli.record(__file__), decoder, cli.record(PRIOR / 'analysis/latest.json'), report['after'],
                cli.record(previous.profile.assets_api.OUT / 'result.json')]))
    print('CADENCE_ASSETS_VERIFIED', package['bytes'], package['sha256'], flush=True)


def assets(s):
    value = s.read(ASSETS / 'result.json')
    cli.require(value['result'] == 'CADENCE_ASSETS_VERIFIED' and value['hardware'] is False, 'verified assets required')
    group = value['group']
    for item in [*value['inputs'], group['receiver'], group['target'], group['package'],
                 *[x['package'] for x in group['negatives']]]:
        cli.require(cli.record(s.checked(item['path'])) == item, 'asset input changed')
    cli.require(group['specification']['receiver'] == 30256 and group['specification']['target_version'] == 30257 and
                group['receiver_bindings']['whole_boot'] == group['target_bindings']['whole_boot'], 'wrong cadence identity')
    return group


def validate(value, group):
    cli.require(type(value.get('rebootProbeIntervalMs')) is int and value['rebootProbeIntervalMs'] == 100 and
                value.get('rebootInfoTimeoutMs') == 2000 and value.get('reuseRebootInfoLink') is True,
                'only the declared interval may change')
    previous.profile.validate_config(dict(value, rebootProbeIntervalMs=500), group)


class Cadence(previous.Probe):
    def __init__(self, s, preinstall=False):
        self.probe_arm, self.ui_arm, self.arm, self.preinstall = 'reuse', 'measure', 'batch', preinstall
        self.assets = assets(s)
        self.proof = batch.clone(batch.radio.confirmed_predecessor, ORDER=('reuse', 'cadence'),
                                TRIALS=previous.TRIALS)(s, 'cadence', self.assets)
        self.report = previous.install.inputs(s)[0] if preinstall else previous.install.apk(s)
        path = Path(self.proof['plan']['profile']['path'])
        batch.radio.backend.Backend.__init__(self, s, path, s.read(path), cli.RECONNECT_GROUP)
        self.receiver_version, self.target_version = 30256, 30257
        self.served_name = self.assets['specification']['served_name']

    def context(self, out):
        c = super().context(out)
        c.n04_prior_assets.append(previous.profile.assets(self.store, 'reuse'))
        c.previous_assets = c.n04_prior_assets[-1]
        old = c.sources
        paths = [Path(__file__), TEST, ASSETS / 'result.json', HOST / 'result.json']
        if not self.preinstall:
            paths.append(AREA / 'archive/result.json')
        records = [cli.record(p) for p in paths]
        c.sources = lambda: sorted({x['path']: x for x in [*old(), *records]}.values(), key=lambda x: x['path'])
        return c

    def phone(self, c, name, *, producer=False):
        phone = super().phone(c, name, producer=producer)
        old = phone.config
        def config(*args):
            value = dict(old(*args), rebootProbeIntervalMs=100)
            validate(value, self.assets)
            return value
        phone.config = config
        return phone


def tests(s):
    value = s.read(HOST / 'result.json')
    cli.require(value['result'] == 'PASS' and value['source'] == cli.record(__file__) and
                value['test'] == cli.record(TEST), 'source-bound tests required')
    return cli.record(HOST / 'result.json')


def archive(s, owner, worker):
    ui.archival.proof(s, PRIOR)
    ui.archival.proof(s, previous.TRIALS / 'control')
    out = s.checked(AREA / 'archive')
    if worker:
        radio = SimpleNamespace(ORDER=('reuse',), TRIALS=previous.TRIALS,
            old=SimpleNamespace(TRIAL=previous.TRIALS / 'control'),
            APK=previous.AREA / 'apk-g1/apk.json', backend=batch.radio.backend)
        batch.clone(ui.archival.worker, radio=radio)(s, 'reuse', out)
    else:
        tests(s)
        previous.install.apk(s)
        cli.require(not out.exists(), 'preserve archive attempt')
        for name in ('intent.json', 'result.json', 'capture', 'host', 'usb', 'stop-intent.json', 'mkdir-intent.json', 'move-intent.json'):
            s.checked(out / name)
        s.write(out / 'intent.json', dict(source=cli.record(__file__), protected=str(PRIOR),
            selected=str(previous.TRIALS / 'control'), no_delete=True, no_ota=True))
        print(owner.owned.launch(s.checked(AREA / 'runtime/archive-001'), Path(__file__), ['archive-worker'], 600))


if __name__ == '__main__':
    cli.require(Path.cwd() == ROOT and sys.flags.isolated and sys.flags.no_site and sys.dont_write_bytecode,
                'isolated explicit root required')
    modes = ('assets', 'check', 'archive', 'archive-worker', 'launch', 'coordinator', 'network', 'cell')
    cli.require(len(sys.argv) in (2, 4) and sys.argv[1] in modes and
                (len(sys.argv) == 2 or sys.argv[2:] == ['--arm', 'cadence']), 'exact cadence invocation required')
    mode = sys.argv[1]
    s = cli.Store(ROOT)
    owner = cli.load_module('probe_cadence_owner', ROOT / '.cache/p3-4-screening-20260922/supervisor.py')
    if mode not in ('check', 'archive', 'launch'):
        cli.require(owner.owned.in_job(), 'finite owner required')
    if mode == 'assets':
        make_assets(s)
    elif mode.startswith('archive'):
        archive(s, owner, mode == 'archive-worker')
    else:
        tests(s)
        if mode == 'launch':
            cli.require(not OUT.exists(), 'preserve cadence attempt')
            a = s.read(AREA / 'archive/result.json')
            close = s.read(AREA / 'runtime/archive-001/closed.json')
            cli.require(a['result'] == 'INACTIVE_CAPTURE_ARCHIVED_VERIFIED' and a['usb_closed'] and
                        a['protected_snapshot_unchanged'] and a['configuration_unchanged'] and len(a['remaining']) == 7 and
                        close['worker_exit'] == 0 and not close['forced_termination'], 'archive unresolved')
        api = Cadence(s, preinstall=mode == 'check')
        c = api.context(OUT)
        api.preflight(c, OUT)
        if mode == 'check':
            value = api.phone(c, 'cadence_offline').config(c, 's04', 921600, 28, 'https://offline.trycloudflare.com')
            validate(value, api.assets)
            cli.require(api.installed_context(OUT).receiver_image_sha == api.assets['target']['sha256'], 'wrong target binding')
            print('CADENCE_OFFLINE_VERIFIED', len(c.sources()))
        elif mode == 'launch':
            s.write(OUT / 'intent.json', dict(time=cli.now(), sources=c.sources(), tests=tests(s), arm='cadence',
                scope='one legal FULL successor, only100ms interval; unchanged2s INFO timeout and same APK', independent_acceptance=False))
            print(owner.owned.launch(s.checked(OUT / 'runtime/coordinator'), Path(__file__), ['coordinator'], 6000))
        else:
            cli.require(c.sources() == s.read(OUT / 'intent.json')['sources'], 'running inputs changed')
            os.environ.update(c.environment())
            if mode == 'coordinator':
                batch.clone(ui.coordinate, __file__=__file__, tests=tests)(s, api, c, owner, OUT, 'cadence')
            else:
                api.validate(c, OUT)
                code = api.network_worker(c, OUT) if mode == 'network' else api.cell_worker(c, OUT, 's04')
                cli.require(code == 0, 'cadence trial needs reconciliation')
