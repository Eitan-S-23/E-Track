"""Admit a pinned protected normal preparation without keys or transformations."""
import argparse
import importlib.util
import io
import json
import os
from pathlib import Path
import stat
import sys
from types import SimpleNamespace
import zipfile

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / '.cache/p51-staging/python'))


def load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


n = load('p51_normal_staging_sources', ROOT / 'Tools/ota/p51-normal-inputs.py')
m = n.m
functional = load('p51_normal_staging_functional', ROOT / 'Tools/ota/p51-acceptance/functional_sample.py')


def canonical(value):
    return (json.dumps(value, sort_keys=True, separators=(',', ':'), ensure_ascii=False) + '\n').encode()


def record(path):
    path = m.checked(path)
    raw = path.read_bytes()
    return dict(path=path.relative_to(ROOT).as_posix(), bytes=len(raw), sha256=m.sha(raw))


def resolve(config):
    m.require(config['schema'] == 'p51-normal-staging-inputs-v1' and config['task'] == 'P51-DELTA-01'
        and config['profile'] == 'p34-v2-candidate' and config['versionCode'] == 30321
        and config['baseVersionCode'] == 30320 and config['versionName'] == '3.3.21'
        and config['baseVersionName'] == '3.3.20', 'Normal staging contract mismatch')
    source_config = json.loads(m.read(config['sourceInputs']))
    expected_source, original_blobs = n.resolve(source_config)
    archive_bytes = m.read(config['archive'])
    artifact = json.loads(m.read(config['artifact']))
    run = json.loads(m.read(config['run']))
    owner = config['originalOwner']
    m.require(artifact['id'] == owner['artifactId'] and artifact['name'] == 'p51-normal-' + owner['runId'] + '-' + owner['runAttempt']
        and artifact['digest'] == 'sha256:' + m.sha(archive_bytes) and artifact['size_in_bytes'] == len(archive_bytes)
        and artifact['workflow_run']['head_sha'] == owner['commitSha']
        and artifact['workflow_run']['id'] == int(owner['runId'])
        and run['id'] == int(owner['runId']) and run['run_attempt'] == int(owner['runAttempt'])
        and run['head_sha'] == owner['commitSha'] and run['conclusion'] == 'success'
        and run['event'] == 'workflow_dispatch' and run['path'] == '.github/workflows/firmware-build.yml'
        and run['repository']['full_name'] == source_config['repository'], 'Normal staging protected-run lineage')
    files = {}
    with zipfile.ZipFile(io.BytesIO(archive_bytes)) as archive:
        m.require(len(archive.namelist()) == len(set(archive.namelist()))
            and sum(item.file_size for item in archive.infolist()) < 200 * 1024 * 1024
            and archive.testzip() is None, 'Invalid normal staging archive')
        for item in archive.infolist():
            name = item.filename
            parts = name.rstrip('/').split('/')
            m.require(name and ':' not in name and '\\' not in name and not name.startswith('/')
                and all(part not in ('', '.', '..', 'private') for part in parts)
                and parts[0] in ('normal', 'inputs', 'evidence') and not stat.S_ISLNK(item.external_attr >> 16)
                and not name.endswith(('key.h', '.exe', 'native-active.json', 'key-build-active.json')),
                'Unsafe normal staging archive member')
            if not item.is_dir():
                files[name] = archive.read(item)
    inventory = [dict(member=name, bytes=len(raw), sha256=m.sha(raw)) for name, raw in sorted(files.items())]
    m.require(m.sha(canonical(inventory)) == config['archiveMembersSha256'], 'Normal staging archive inventory drift')

    def member(pin):
        return m.verified(files[pin['member']], pin)

    candidate_bytes = member(config['candidateMetadata'])
    candidate = json.loads(candidate_bytes)
    native_bytes = member(config['verification'])
    metadata_bytes = member(config['registration'])
    metadata = json.loads(metadata_bytes)
    image, base = member(config['finalImage']), member(config['baseImage'])
    m.require(json.loads(files['inputs/normal-source-proof.json']) == expected_source
        and json.loads(files['inputs/manifest.json']) == source_config, 'Normal staging original source proof drift')
    for name, expected in original_blobs.items():
        m.require(files['inputs/' + name] == expected, 'Normal staging original source bytes drift')
    producer = {key: owner[key] for key in ('commitSha', 'runId', 'runAttempt')}
    m.require(candidate['schema'] == 'p51-normal-candidate-v1' and candidate['runner'] == producer
        and candidate['isFormalRelease'] is False and candidate['productionPublishable'] is False
        and candidate['readyRegistered'] is False and candidate['sourceCompilations'] == candidate['referenceSearches'] == 0
        and candidate['finalizations'] == 2 and candidate['packagePurpose'] == 'normal-upgrade'
        and candidate['bootInstallation'] == 'FORBIDDEN'
        and candidate['nativeVerificationSha256'] == m.sha(native_bytes)
        and candidate['sourceProofSha256'] == m.sha(files['inputs/normal-source-proof.json'])
        and candidate['retainedBoot'] == expected_source['retainedBoot'], 'Normal staging candidate lineage drift')
    m.require((candidate['baseVersionCode'], candidate['versionCode'], candidate['baseImageSha256'], candidate['targetImageSha256'])
        == (30320, 30321, m.sha(base), m.sha(image)) and config['baseImageSha256'] == m.sha(base), 'Normal staging image identity')
    for role, raw, version in (('base', base, 30320), ('target', image, 30321)):
        original = expected_source['roles'][role]['originalBuild']
        m.require(candidate['originalBuilds'][role] == original, 'Normal staging build identity')
        fields = m.recovery.validate_app(raw)
        gcc = original_blobs[expected_source['roles'][role]['files']['app/X-Track-App-GCC.bin']['path']]
        m.require(fields['version_code'] == version and fields['build_ts'] == original['buildTimestamp']
            and raw[:0x400] == gcc[:0x400] and raw[0x460:] == gcc[0x460:], 'Normal staging finalized executable drift')
        preparation = candidate['preparations'][role]
        m.require(preparation['path'] == 'normal/' + role + '/verification.json'
            and m.sha(files[preparation['path']]) == preparation['sha256'], 'Normal staging preparation drift')
    m.require(metadata['versionCode'] == 30321 and metadata['targetImageSha256'] == m.sha(image)
        and metadata['runId'] == owner['runId'] and metadata['commitSha'] == source_config['targetSourceCommit']
        and [a['kind'] for a in config['assets']] == ['full', 'patch', 'recovery'], 'Normal staging registration lineage')
    blobs = [member(pin) for pin in config['assets']]
    for pin, raw in zip(config['assets'], blobs):
        rows = [a for a in metadata['assets'] if a['kind'] == pin['kind']]
        m.require(len(rows) == 1 and rows[0]['fileName'] == pin['fileName']
            and rows[0]['sizeBytes'] == len(raw) and rows[0]['sha256'] == m.sha(raw), 'Normal staging original asset drift')
    proof = dict(schema='p51-normal-staging-source-proof-v1', originalOwner=owner, archive=config['archive'],
        artifactReceipt=config['artifact'], configSha256=m.sha(canonical(config)), files=inventory,
        sourceCompilations=0, finalizations=0, packageGenerations=0, referenceSearches=0,
        originalSourceProofSha256=candidate['sourceProofSha256'], preparations=candidate['preparations'],
        targetSourceCommit=source_config['targetSourceCommit'], assets=config['assets'], finalImage=config['finalImage'])
    return dict(files=files, proof=proof, image=image, blobs=blobs, candidate=candidate_bytes,
        registration=metadata_bytes, native=native_bytes, build=files['inputs/originals/target/keyed-build/gcc-build-inputs.json'])


def verify_preparation(out, candidate):
    source = out / 'originals'
    prepared = source / 'normal/target'
    proof = json.loads((prepared / 'verification.json').read_bytes())
    asset = lambda kind: record(prepared / next(a['fileName'] for a in proof['assets'] if a['kind'] == kind))
    plan = dict(kind='patch', functional_sample=dict(purpose='normal-upgrade', preparation=record(prepared / 'verification.json'),
        full_package=asset('full')), mcu=dict(package=asset('patch'), images=dict(base=dict(image=record(source / 'normal/base/app-final.bin')),
        target=dict(image=record(prepared / 'app-final.bin')))), tool_dependencies=[record(source / candidate['toolDependency']['path'])])

    def pinned(pin):
        m.read(pin)
        return m.checked(ROOT / pin['path'])

    host = SimpleNamespace(ROOT=ROOT, require=m.require, checked=m.checked, pinned=pinned,
        read_json=lambda path: json.loads(path.read_bytes()), host=SimpleNamespace(load=load))
    functional.validate(plan, host)


def materialize(config, out):
    m.require(not any(v for k, v in os.environ.items() if k.startswith(('TRACE_', 'CLOUDFLARE_', 'CF_', 'GH_', 'OTA_AES_KEY', 'GITHUB_TOKEN'))),
        'Normal staging admission must not receive credentials')
    out = m.checked(out)
    m.require(not out.exists(), 'Preserve previous normal staging attempt')
    data = resolve(config)
    for name in data['files']:
        m.checked(out / 'originals' / name)
    for pin in config['assets']:
        m.checked(out / 'assets' / pin['fileName'])
    for name in ('source-proof.json', 'app-final.bin', 'candidate-metadata.json', 'registration.json', 'native-verification.json', 'gcc-build-inputs.json'):
        m.checked(out / 'inputs' / name)
    for name, raw in data['files'].items():
        m.save(out / 'originals' / name, raw)
    verify_preparation(out, json.loads(data['candidate']))
    for pin, raw in zip(config['assets'], data['blobs']):
        m.save(out / 'assets' / pin['fileName'], raw)
    for name, key in (('app-final.bin', 'image'), ('candidate-metadata.json', 'candidate'),
        ('registration.json', 'registration'), ('native-verification.json', 'native'), ('gcc-build-inputs.json', 'build')):
        m.save(out / 'inputs' / name, data[key])
    m.save_json(out / 'inputs/source-proof.json', data['proof'])


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--root-out', type=Path, required=True)
    args = parser.parse_args()
    m.require(Path.cwd() == ROOT and sys.flags.isolated and sys.flags.no_site and sys.dont_write_bytecode,
        'Use explicit worktree cwd and Python -I -S -B')
    materialize(json.loads((ROOT / 'Tools/ota/p51-normal-staging-inputs.json').read_bytes()), args.root_out)
    print('P51_NORMAL_IMMUTABLE_STAGING_INPUTS_VERIFIED')
