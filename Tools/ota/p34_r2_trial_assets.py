"""Offline sender descriptors for the existing R2 package, not an OTA entry."""
import argparse
import hashlib
from pathlib import Path
import re
import struct
import sys

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'Tools/ota'))
import p34_install_cost as host
import p34_patch_assets as shared
import p34_finalized_vtor_capture as capture
import p34_info_retry_trial as policy
from recovery_confirm import r2_health

cli = host.cli
PACKAGE = ROOT / '.cache/p34-r2-ota-package2/result.json'
PRIOR = ROOT / '.cache/p34-sha-candidate/assets/result.json'
ABI = ROOT / '.cache/p34-r2-live-layout1/result.json'
R2_SOURCE = ROOT / '.cache/p34-recovery-sources1/result.json'
BUILD = ROOT / '.cache/p34-early-usb-r2/on/b/app-gcc'
SELF = Path(__file__).resolve()


def identity(raw):
    capture.policy.sources.verify(raw)
    header = raw[0x400:0x460]
    return dict(version_code=struct.unpack_from('<I', header, 8)[0],
        version_name=header[12:28].split(b'\0', 1)[0].decode('ascii'), image_len=len(raw),
        raw_image_sha256=hashlib.sha256(raw).hexdigest(),
        build_timestamp=struct.unpack_from('<I', header, 28)[0],
        hardware_rev=struct.unpack_from('<I', header, 32)[0], layout_id=header[72],
        min_boot=header[73], integrity_sha256=header[40:72].hex())


def validate_abi(original, derived):
    aliases = dict(durable_off='progress.durable_off', segment_bitmap='progress.segment_bitmap',
        resumed='progress.resumed', complete='progress.complete', parser_bad_frames='demux.parser.bad_frames')
    cli.require(original['size'] == derived['size'] == 576 and len(original['members']) == len(derived['members']) == 21,
                'full R2 ABI shape differs')
    for name, item in original['members'].items():
        actual = derived['members'][aliases.get(name, name)]
        cli.require(item == dict(offset=actual['offset'], size=actual['bytes']), 'R2 member ABI differs: ' + name)


def derive(store):
    package, old, layout = store.read(PACKAGE), store.read(PRIOR)['groups']['measure'], store.read(ABI)
    cli.require(package['result'] == 'R2_TRANSITION_PACKAGE_HOST_VERIFIED' and package['header_only'] is True and
        package['hardware'] is False and layout['result'] == 'R2_SESSION_ABI_DERIVED', 'qualified offline inputs required')
    for item in package['inputs'] + package['outputs'] + layout['inputs'] + layout['dependencies'] + layout['outputs']:
        cli.require(cli.record(item['path']) == item, 'package/ABI source or output changed')
    validate_abi(old['target_bindings']['layout']['members'], layout)
    assets = {suffix: cli.record(BUILD / ('X-Track-App-GCC' + suffix)) for suffix in ('.map', '.elf')}
    original = {r['path']: r for r in store.read(R2_SOURCE)['inputs']}
    cli.require(original.get(assets['.elf']['path']) == assets['.elf'], 'R2 original ELF binding differs')
    r2_health.verify_map(Path(assets['.map']['path']).read_bytes())
    constants = store.read(ROOT / '.cache/p34ab/assets/session-assets.json')['constants']
    a, b = (Path(package[name]['path']).read_bytes() for name in ('current', 'target'))
    first, second = identity(a), identity(b)
    cli.require((first['version_code'], second['version_code']) == (30276, 30277) and
                a[:0x400] + a[0x460:] == b[:0x400] + b[0x460:], 'fixed R2 header-only transition differs')
    receiver = shared.bindings(old, package['current'], first, assets, constants)
    target = shared.bindings(old, package['target'], second, assets, constants)
    boot = cli.record(ROOT / '.cache/p34-native-acquire1/boot-readback.bin')
    cli.require(all((bound['whole_boot']['bytes'], bound['whole_boot']['sha256']) == (boot['bytes'], boot['sha256'])
                    for bound in (receiver, target)), 'original full Boot binding differs')
    receiver['whole_boot'] = target['whole_boot'] = boot
    specification = dict(old['specification'], receiver=30276, target_version=30277,
        version_name=second['version_name'], served_name='p34-r2-transition-full.etu', release_key='p34-r2-transition')
    checks = package['checks']
    cli.require(all(checks['positive'][key] is True for key in
        ('passed', 'byte_identical', 'boot_ok', 'guards_ok', 'workspace_lifecycle_ok')), 'native positive missing')
    negatives = []
    for label in ('payload-crc', 'truncated', 'same-version', 'wrong-flags'):
        cli.require(checks[label]['passed'] is True and checks[label]['prepares'] == 0, 'native negative did not reject')
        negatives.append(dict(package=cli.record(PACKAGE.parent / (label + '.etu')), native=checks[label]))
    group = dict(specification=specification, receiver=package['current'], receiver_identity=first,
        receiver_bindings=receiver, target=package['target'], target_identity=second, target_bindings=target,
        package=package['package'], package_kind='full', decoded=checks['positive'], negatives=negatives)
    # These are asset bindings, never evidence that a transfer or live admission ran.
    return group


def sources(store):
    return list(dict.fromkeys([SELF, ROOT / 'tests/ota/test_p34_r2_trial_assets.py', PACKAGE, PRIOR, ABI, R2_SOURCE,
        ROOT / '.cache/p34ab/assets/session-assets.json', ROOT / '.cache/p34-next/n03_bindings.py',
        ROOT / 'Tools/ota/baud_mcu.py', Path(shared.__file__), Path(capture.__file__),
        Path(capture.policy.__file__), Path(capture.policy.sources.__file__), Path(policy.__file__),
        Path(r2_health.__file__),
        *(Path(sys.modules[c.__module__].__file__) for c in policy.Trial.__mro__ if c is not object),
        *(ROOT / n for n in ('Tools/ota/p34_session.py', 'Tools/ota/p34_install_cost.py',
            'Tools/ota/p34_patch_preparation.py', 'Tools/ota/p34_install_candidate.py',
            '.agents/skills/e-track-flutter-debug/scripts/host_io.py',
            '.cache/p34-sha-candidate/trials/measure/cells/s04/runtime-config.json'))]))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output-dir', type=Path, required=True)
    parser.add_argument('--check-only', action='store_true')
    args = parser.parse_args()
    cli.require(Path.cwd() == ROOT and sys.flags.isolated and sys.flags.no_site and sys.dont_write_bytecode,
                'isolated explicit root required')
    store = cli.Store(ROOT)
    out = store.checked(args.output_dir)
    import p34_mutation_audit_tests as preflight
    inputs = sources(store)
    preflight.preflight(store, out, inputs)
    if args.check_only:
        print('R2_TRIAL_ASSETS_PREFLIGHT_PASS'); return
    records = [cli.record(p) for p in inputs]
    env = host.environment(store, out)
    for path in inputs: store.raw(out / 'source' / path.relative_to(ROOT), path.read_bytes())
    log = host.command(store, out, 'tests', [sys.executable, '-I', '-S', '-B', '-X', 'utf8',
        ROOT / 'tests/ota/test_p34_r2_trial_assets.py', '-v'], env, 120)
    count = re.search(rb'Ran (\d+) tests? in .*\r?\n\r?\nOK\b', log)
    cli.require(count, 'R2 trial assets tests failed')
    group = derive(store)
    cli.require(records == [cli.record(p) for p in inputs], 'trial descriptor inputs changed')
    store.write(out / 'result.json', dict(result='R2_TRIAL_ASSETS_HOST_VERIFIED', tests=int(count[1]),
        inputs=records, groups={'transition': group}, hardware=False, new_package_generated=False,
        historical_ota_predecessor=False, sender_implemented=False, ota_ready=False))
    print('R2_TRIAL_ASSETS_HOST_VERIFIED', group['package']['bytes'])


if __name__ == '__main__': main()
