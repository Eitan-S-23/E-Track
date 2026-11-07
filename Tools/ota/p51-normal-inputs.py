"""Admit existing protected GCC originals; never search or generate a reference."""
import argparse
import io
import json
import os
from pathlib import Path
import re
import shutil
import signal
import sys
import zipfile

ROOT = Path(__file__).resolve().parents[2]
sys.path[:0] = [str(ROOT / 'Tools/ota'), str(ROOT / '.cache/p51-staging/python')]
import importlib.util
spec = importlib.util.spec_from_file_location('p51_normal_package', ROOT / 'Tools/ota/p51-package.py')
m = importlib.util.module_from_spec(spec)
spec.loader.exec_module(m)

MEMBERS = ('app/X-Track-App-GCC.bin', 'app/X-Track-App-GCC.elf', 'app/X-Track-App-GCC.map',
           'boot/X-Track-Boot.bin', 'CMakeCache.txt', 'compile_commands.json',
           'gcc-build-inputs.json', 'keyed-build-evidence.json')


def validate_config(config):
    m.require(config['schema'] == 'p51-normal-inputs-v1' and config['mode'] == 'normal-delta'
        and config['task'] == 'P51-DELTA-01' and config['repository'] == 'Eitan-S-23/E-Track'
        and config['profile'] == 'p34-v2-candidate' and config['purpose'] == 'normal-upgrade'
        and config['basePurpose'] == 'preparation-only/forward-baseline-initialization'
        and config['derivation'] == 'two-archived-GCC-executables/normal-preparer'
        and config['timestampPolicy'] == 'preserve-each-original-build-timestamp'
        and config['productionPublishable'] is False, 'Normal candidate input contract')
    m.require(30319 < m.pack.parse_version_name(config['baseVersion'])
        < m.pack.parse_version_name(config['targetVersion']), 'Normal candidate fresh forward versions')
    m.require(config['baseSource']['path'] == 'Tools/ota/p51-candidate-inputs.json'
        and config['targetSource']['path'] == 'Tools/ota/p51-start-state-inputs.json', 'Normal original source paths')


def archived_build(archive, expected, role):
    with zipfile.ZipFile(io.BytesIO(archive)) as z:
        m.require(len(z.namelist()) == len(set(z.namelist())), 'Duplicate original archive member')
        files = {name: z.read('keyed-build/' + name) for name in MEMBERS}
    build = json.loads(files['gcc-build-inputs.json'])
    evidence = json.loads(files['keyed-build-evidence.json'])
    m.require(build == expected and evidence['commitSha'] == build['commitSha']
        and evidence['keyBinding'] == build['keyBinding']
        and evidence['buildConfiguration'] == build['buildConfiguration'], 'Normal original GCC evidence mismatch')
    for name in MEMBERS[:4]:
        rows = [r for r in evidence['artifacts'] if r['path'] == name]
        m.require(len(rows) == 1 and rows[0]['sizeBytes'] == len(files[name])
            and rows[0]['sha256'] == m.sha(files[name]), 'Normal original GCC artifact mismatch')
    for name, record in [('app/X-Track-App-GCC.bin', build['app']), ('boot/X-Track-Boot.bin', build['boot'])]:
        m.require(len(files[name]) == record['sizeBytes'] and m.sha(files[name]) == record['sha256'], 'Normal raw build mismatch')
    m.require(files['app/X-Track-App-GCC.bin'][0x400:0x460] == b'\xff' * 96, 'Normal input must be unfinalized GCC')
    prefix = 'originals/' + role + '/keyed-build/'
    return {prefix + name: data for name, data in files.items()}, {
        'originalBuild': build,
        'files': {name: dict(path=prefix + name, bytes=len(data), sha256=m.sha(data)) for name, data in files.items()}}


def resolve(config):
    validate_config(config)
    base_config = json.loads(m.read(config['baseSource']))
    target_config = json.loads(m.read(config['targetSource']))
    base = m.archived_inputs(base_config)
    target = m.resolve_supplement(target_config)
    m.require(base['build']['commitSha'] == config['baseSourceCommit']
        and target['build']['commitSha'] == config['targetSourceCommit']
        and base['build']['keyBinding'] == target['build']['keyBinding']
        and base['build']['keyBinding']['source'] == 'approved-ci-key-v1', 'Normal source/key lineage mismatch')
    blobs, roles = {}, {}
    for role, archive, build in [('base', base['archive'], base['build']),
                                 ('target', m.read(target_config['archive']), target['build'])]:
        files, proof = archived_build(archive, build, role)
        blobs.update(files)
        roles[role] = proof
    old = blobs[roles['base']['files']['app/X-Track-App-GCC.bin']['path']]
    new = blobs[roles['target']['files']['app/X-Track-App-GCC.bin']['path']]
    m.require(old[:0x400] != new[:0x400] or old[0x460:] != new[0x460:], 'Normal sample cannot be header-only')
    blobs['retained-group16-boot.bin'] = m.resolve_boot(base_config)
    blobs['original-base.bin'] = base['base']
    with zipfile.ZipFile(io.BytesIO(m.read(target_config['archive']))) as z:
        image = z.read('prepared/app-final.bin')
    final = target['originalMetadata']['finalization']['target']
    m.require(m.sha(image) == final['sha256'] and len(image) == final['sizeBytes']
        and m.recovery.validate_app(image)['version_code'] == 30319, 'Normal archived target image mismatch')
    blobs['original-target.bin'] = image
    proof = dict(schema='p51-normal-source-proof-v1', config=config, roles=roles,
        baseArchive=base_config['packet']['objects']['archive'], targetArchive=target_config['archive'],
        baseArtifact=base['artifact'], targetOriginalOwner=target['originalOwner'],
        retainedBoot=base_config['boot'], sourceCompilations=0, referenceSearches=0,
        sourceChangesOutsideFwHeader=True, bootInstallation='FORBIDDEN', isFormalRelease=False)
    return proof, blobs


def materialize(config, out):
    proof, blobs = resolve(config)
    out = m.checked(out)
    m.require(not (out / 'inputs').exists(), 'Preserve prior normal inputs')
    for name in [*blobs, 'normal-source-proof.json', 'manifest.json']:
        m.checked(out / 'inputs' / name)
    for name, data in blobs.items():
        m.save(out / 'inputs' / name, data)
    m.save_json(out / 'inputs/manifest.json', config)
    m.save_json(out / 'inputs/normal-source-proof.json', proof)
    return proof


def check_materialized(config, out):
    proof, blobs = resolve(config)
    out = m.checked(out)
    m.require(json.loads((out / 'inputs/manifest.json').read_bytes()) == config
        and json.loads((out / 'inputs/normal-source-proof.json').read_bytes()) == proof,
        'Normal materialized source proof drift')
    for name, expected in blobs.items():
        m.require(m.checked(out / 'inputs' / name).read_bytes() == expected, 'Normal materialized original byte drift')


def native(out, cc):
    out = m.checked(out)
    prepared = out / 'normal/target'
    proof = json.loads((prepared / 'verification.json').read_bytes())
    data = dict(base=(prepared / 'work/base-final.bin').read_bytes(), target=(prepared / 'app-final.bin').read_bytes())
    private = out / 'private'
    m.save(out / 'inputs/base.bin', data['base'])
    aliases = private / 'normal-assets'
    for kind, name in [('full', 'full.etu'), ('patch', 'patch.etu'), ('recovery', 'recovery.bin')]:
        asset = next(a for a in proof['assets'] if a['kind'] == kind)
        m.save(aliases / name, (prepared / asset['fileName']).read_bytes())
    m.save(aliases / 'app-final.bin', data['target'])
    result = m.native_verify(data, aliases, private, cc, all_assets=True)
    initialization = out / 'normal/base'
    initial_proof = json.loads((initialization / 'verification.json').read_bytes())
    full = next(a for a in initial_proof['assets'] if a['kind'] == 'full')
    result['initialization'] = m.native_verify(dict(base=(out / 'inputs/original-target.bin').read_bytes(),
        target=(initialization / 'app-final.bin').read_bytes()), initialization, private, cc, all_assets=True,
        full_only=dict(fileName=full['fileName'], expected=initialization / 'app-final.bin',
                       prefix='initialization-', base=out / 'inputs/original-target.bin'))
    m.save_json(out / 'evidence/normal-native.json', result)


def command(out, request_path):
    out = m.checked(out)
    request_path = m.checked(request_path)
    request_path.relative_to(out / 'private')
    request = json.loads(request_path.read_bytes())
    argv = request['argv']
    scripts = ('Tools/etu_pack.py', 'Tools/etu_unpack.py', 'Tools/jlink/prepare-bootstrap-app.py',
               '.github/scripts/firmware-byte-check.py')
    m.require(re.fullmatch(r'normal-step-[1-9][0-9]*', request['label']) and request['timeout'] == 330
        and len(argv) > 3 and Path(shutil.which(argv[0]) or argv[0]).resolve() == Path(sys.executable).resolve()
        and argv[1] == '-B' and Path(argv[2]) in [ROOT / name for name in scripts]
        and Path(request['cwd']) in [out / 'normal' / role / 'work' for role in ('base', 'target')],
        'Bounded normal-preparer command request')
    env = {key: value for key, value in os.environ.items()
           if not key.startswith(('GH_', 'GITHUB_TOKEN', 'TRACE_', 'CF_', 'CLOUDFLARE_'))}
    m.native_command(request['label'], argv, env, out / 'evidence/native', timeout=330, cwd=request['cwd'])


if __name__ == '__main__':
    def cancelled(signum, frame):
        raise InterruptedError('normal candidate command interrupted')
    signal.signal(signal.SIGINT, cancelled)
    signal.signal(signal.SIGTERM, cancelled)
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('mode', choices=('inputs', 'check', 'native', 'command'))
    parser.add_argument('--root-out', type=Path, required=True)
    parser.add_argument('--cc', default='gcc')
    parser.add_argument('--command-json', type=Path)
    args = parser.parse_args()
    m.require(Path.cwd() == ROOT and sys.flags.isolated and sys.flags.no_site and sys.dont_write_bytecode,
              'Use explicit worktree cwd and Python -I -S -B')
    if args.mode in ('inputs', 'check'):
        m.require(not os.environ.get('OTA_AES_KEY'), 'Input admission must not receive the key')
        action = materialize if args.mode == 'inputs' else check_materialized
        action(json.loads((ROOT / 'Tools/ota/p51-normal-inputs.json').read_bytes()), args.root_out)
    elif args.mode == 'native':
        native(args.root_out, args.cc)
    else:
        command(args.root_out, args.command_json)
    print('P51_NORMAL_' + args.mode.upper() + '_COMPLETE')
