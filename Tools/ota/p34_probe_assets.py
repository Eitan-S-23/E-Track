"""Prepare two header-only successors for the same-APK INFO retry screen."""
import copy
import json
import os
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'Tools/ota'))
import p34_ui_assets as ui
import p34_radio_archive as archive

cli, host = ui.cli, ui.host
AREA = ROOT / '.cache/p34-probe-fix'
OUT = AREA / 'assets'
PRIOR = ui.screen.AREA / 'trials-dns/measure'


def prepare(s):
    cli.require(not OUT.exists() and not os.environ.get('OTA_AES_KEY'), 'preserve assets/no key override')
    report = archive.proof(s, PRIOR)
    group = s.read(ui.OUT / 'result.json')['groups']['measure']
    cli.require(report['summary']['input']['targetVersionCode'] == 30254 and
                report['summary']['input']['targetImageSha256'] == group['target']['sha256'], 'wrong predecessor')
    inputs = [cli.record(PRIOR / 'analysis/latest.json'), report['after'], cli.record(ui.OUT / 'result.json'),
              cli.record(__file__), cli.record(ui.shared.__file__)]
    decoder = s.read(ROOT / '.cache/p34-next/n03/assets/result.json')['decoder']
    inputs += [decoder, group['target'], group['target_bindings']['whole_boot']]
    for item in inputs:
        cli.require(cli.record(s.checked(item['path'])) == item, 'input changed')
    env = host.environment(s, OUT)
    os.environ.update(env)
    sys.path.insert(0, str(Path(sys.base_prefix) / 'Lib/site-packages'))
    pack = cli.load_module('probe_pack', ui.screen.AREA / 'f/Tools/etu_pack.py')
    unpack = cli.load_module('probe_unpack', ui.screen.AREA / 'f/Tools/etu_unpack.py')
    tools = cli.load_module('probe_negatives', ROOT / 'Tools/ota/prepare_baud_assets.py')
    receiver, bindings, groups = group['target'], group['target_bindings'], {}
    for name, version, reuse in (('control', 30255, False), ('reuse', 30256, True)):
        before = Path(receiver['path']).read_bytes()
        raw = bytearray(before)
        raw[0x400:0x460] = pack.build_fw_header(bytes(raw), f'3.2.{version-30200}-p34p', 1786320000)
        cli.require(before[:0x400] + before[0x460:] == raw[:0x400] + raw[0x460:], 'executable changed')
        target = s.raw(OUT / (name + '.bin'), bytes(raw))
        identity = ui.shared.identity(bytes(raw), unpack)
        cli.require(identity['version_code'] == version, 'wrong target version')
        blob = ui.shared.wrap_payload(pack, pack.lzma_alone_encode(bytes(raw)), before, bytes(raw), kind='full')
        package = s.raw(OUT / ('p34-probe-' + name + '-full.etu'), blob)
        def native(label, item, expected):
            return json.loads(host.command(s, OUT, name + '-' + label,
                [decoder['path'], item['path'], receiver['path'], target['path'], expected], env, 180))
        decoded = native('positive', package, 'ok')
        cli.require(all(decoded[k] for k in ('passed', 'byte_identical', 'boot_ok', 'guards_ok', 'workspace_lifecycle_ok')),
                    'native positive failed')
        negatives = []
        for label, broken, expected in tools.negatives(blob, version - 1):
            item = s.raw(OUT / (name + '-' + label + '.etu'), broken)
            result = native(label, item, expected)
            cli.require(result['passed'] and result['prepares'] == 0, 'negative reached preparation')
            negatives.append(dict(name=label, package=item, native=result))
        target_bindings = copy.deepcopy(bindings)
        target_bindings['profile'].update(image=target, identity=identity, prefix=bytes(raw[:0x460]).hex())
        groups[name] = dict(specification=dict(receiver=version-1, target_version=version,
            version_name=f'3.2.{version-30200}-p34p', served_name='p34-probe-' + name + '-full.etu',
            release_key='p34-probe-' + name, kind='full', reuseRebootInfoLink=reuse),
            receiver=receiver, receiver_bindings=bindings, target=target, target_identity=identity,
            target_bindings=target_bindings, package=package, package_kind='full', decoded=decoded, negatives=negatives)
        receiver, bindings = target, target_bindings
    s.write(OUT / 'result.json', dict(result='PROBE_ASSETS_VERIFIED', hardware=False, groups=groups, inputs=inputs,
        scope='two sequential header-only FULL cells, same APK and receiver code; not identical-package A/B'))
    print('PROBE_ASSETS_VERIFIED', {k: v['package']['bytes'] for k, v in groups.items()}, flush=True)


if __name__ == '__main__':
    cli.require(Path.cwd() == ROOT and sys.flags.isolated and sys.flags.no_site and sys.dont_write_bytecode,
                'isolated explicit root required')
    cli.require(sys.argv[1:] in (['launch'], ['worker']), 'exact mode required')
    s = cli.Store(ROOT)
    owner = cli.load_module('probe_assets_owner', ROOT / '.cache/p3-4-screening-20260922/supervisor.py')
    if sys.argv[1] == 'launch':
        s.checked(OUT)
        print(owner.owned.launch(s.checked(AREA / 'runtime/assets-001'), Path(__file__), ['worker'], 900))
    else:
        cli.require(owner.owned.in_job(), 'finite asset owner required')
        prepare(s)
