"""One benchmark envelope over an admitted protected finalized pair; no MCU build."""
import argparse
import importlib.util
import json
import os
from pathlib import Path
import signal
import sys

ROOT = Path(__file__).resolve().parents[2]
spec = importlib.util.spec_from_file_location('p51_benchmark_originals', ROOT / 'Tools/ota/p51-normal-staging-inputs.py')
s = importlib.util.module_from_spec(spec)
spec.loader.exec_module(s)
m = s.m
MANIFEST = 'Tools/ota/p51-benchmark-inputs.json'


def validate_config(config):
    m.require(config['schema'] == 'p51-benchmark-inputs-v1' and config['task'] == 'P5-1'
        and config['mode'] == 'archived-benchmark' and config['repository'] == 'Eitan-S-23/E-Track'
        and config['profile'] == 'p34-v2-candidate' and config['purpose'] == 'fixed-load-benchmark'
        and config['derivation'] == 'protected-finalized-pair/reference-envelope-only'
        and config['productionPublishable'] is False and config['representativeFunctionalSample'] is False
        and (config['baseVersion'], config['targetVersion']) == ('3.3.20', '3.3.21')
        and config['normalInputs']['path'] == 'Tools/ota/p51-normal-staging-inputs.json'
        and config['reference'] == dict(totalBytes=1048576, seed=7, budget=256), 'Benchmark input contract')


def resolve(config):
    validate_config(config)
    original_config = json.loads(m.read(config['normalInputs']))
    original = s.resolve(original_config)
    candidate = json.loads(original['candidate'])
    files = original['files']
    base = m.verified(files[original_config['baseImage']['member']], config['base'])
    target = m.verified(original['image'], config['target'])
    m.require(m.recovery.validate_app(base)['version_name'] == config['baseVersion']
        and m.recovery.validate_app(target)['version_name'] == config['targetVersion'], 'Benchmark finalized pair')
    builds = candidate['originalBuilds']
    m.require(builds['base']['keyBinding'] == builds['target']['keyBinding']
        and builds['base']['keyBinding']['source'] == 'approved-ci-key-v1', 'Benchmark original key lineage')
    boot = files['inputs/retained-group16-boot.bin']
    m.require(m.sha(boot) == candidate['retainedBoot']['sha256'] and len(boot) == candidate['retainedBoot']['bytes'],
        'Benchmark retained Boot identity')
    proof = dict(schema='p51-benchmark-source-v1', config=config, original=original['proof'],
        originalBuilds=builds, base=config['base'], target=config['target'], boot=candidate['retainedBoot'],
        sourceCompilations=0, finalizations=0, normalPackageGenerations=0,
        originalNormalAssets=original_config['assets'], packagePurpose='fixed-load-benchmark',
        productionPublishable=False, representativeFunctionalSample=False)
    return dict(base=base, target=target, boot=boot, proof=proof)


def materialize(config_bytes, out):
    m.require(not os.environ.get('OTA_AES_KEY'), 'Benchmark inputs must not receive the key')
    out = m.checked(out)
    m.require(not (out / 'inputs').exists(), 'Preserve previous benchmark inputs')
    data = resolve(json.loads(config_bytes))
    for name in ('manifest.json', 'benchmark-source.json', 'base.bin', 'target.bin', 'boot.bin'):
        m.checked(out / 'inputs' / name)
    m.save(out / 'inputs/manifest.json', config_bytes)
    m.save_json(out / 'inputs/benchmark-source.json', data['proof'])
    for name in ('base', 'target', 'boot'):
        m.save(out / 'inputs' / (name + '.bin'), data[name])
    return data


def check_materialized(config_bytes, out):
    out = m.checked(out)
    data = resolve(json.loads(config_bytes))
    m.require((out / 'inputs/manifest.json').read_bytes() == config_bytes
        and json.loads((out / 'inputs/benchmark-source.json').read_bytes()) == data['proof'],
        'Benchmark materialized proof drift')
    for name in ('base', 'target', 'boot'):
        m.require((out / 'inputs' / (name + '.bin')).read_bytes() == data[name], 'Benchmark materialized image drift')
    return data


def protected_owner(env, config_bytes, out):
    expected = dict(INPUT_CANDIDATE_MODE='archived-benchmark', INPUT_VERSION_NAME='3.3.21',
        INPUT_CANDIDATE_BASE_VERSION='3.3.20', INPUT_PUBLISH='false', INPUT_REHEARSAL='false',
        INPUT_CHECK_BINDINGS='false', INPUT_PACKAGE_CANDIDATE='true', OTA_BOOT_CHAIN_READY='false',
        FIRMWARE_RELEASE_MODE='artifact-candidate-benchmark',
        FIRMWARE_CANDIDATE_CONTEXT='firmware-rehearsal/artifact-only-archived-benchmark-v1',
        GITHUB_ACTIONS='true', GITHUB_EVENT_NAME='workflow_dispatch', GITHUB_REPOSITORY='Eitan-S-23/E-Track')
    m.require(all(env.get(key) == value for key, value in expected.items())
        and env.get('INPUT_STAGE_CANDIDATE', 'false') == 'false'
        and not any(env.get(key) for key in ('INPUT_CANDIDATE_FULL_BASE_VERSION',
            'INPUT_APPROVED_REHEARSAL_RUN_ID', 'INPUT_RELEASE_NOTES'))
        and not any(value for key, value in env.items() if key.startswith(('GH_', 'GITHUB_TOKEN', 'TRACE_', 'CF_', 'CLOUDFLARE_'))),
        'Benchmark protected artifact-only context')
    owner = dict(commitSha=env['GITHUB_SHA'], runId=env['GITHUB_RUN_ID'], runAttempt=env['GITHUB_RUN_ATTEMPT'])
    m.require(m.re.fullmatch(r'[0-9a-f]{40}', owner['commitSha'])
        and all(m.re.fullmatch(r'[1-9][0-9]*', owner[key]) for key in ('runId', 'runAttempt'))
        and env.get('GITHUB_WORKFLOW_SHA') == env.get('INPUT_CANDIDATE_REVIEWED_COMMIT') == owner['commitSha']
        and m.re.fullmatch(r'refs/heads/[A-Za-z0-9_./-]+', env.get('GITHUB_REF', ''))
        and env.get('GITHUB_WORKFLOW_REF') == 'Eitan-S-23/E-Track/.github/workflows/firmware-build.yml@' + env['GITHUB_REF']
        and json.loads((out / 'evidence/input-binding.json').read_bytes()) == dict(manifestSha256=m.sha(config_bytes), owner=owner)
        and json.loads((out / 'private/owner.json').read_bytes()) == owner, 'Benchmark runner/input owner')
    return owner


def package(config_bytes, out, cc):
    out = m.checked(out)
    owner = protected_owner(os.environ, config_bytes, out)
    data = check_materialized(config_bytes, out)
    key = bytes.fromhex(os.environ['OTA_AES_KEY'])
    for build in data['proof']['originalBuilds'].values():
        m.require_supplement_key(build, key)
    header = ''.join('#define OTA_AES_KEY_1_WORD%d 0x%su\n' % (i, key.hex()[i*8:i*8+8]) for i in range(4)).encode()
    m.require((out / 'private/key.h').read_bytes() == header, 'Benchmark private header drift')
    m.require(not (out / 'prepared').exists() and not (out / 'evidence/reference').exists(), 'Preserve previous benchmark package')
    config = json.loads(config_bytes)
    data['row'], data['compressed'] = m.source_reference(data['base'], data['target'], config, out / 'evidence/reference')
    result = m.package(data, key, out / 'prepared')
    m.save(out / 'prepared/app-start.bin', data['base'])
    result['native'] = m.native_verify(data, out / 'prepared', out / 'private', cc, all_assets=True)
    m.require(len(result['native']['checks']) == 11, 'Benchmark native case inventory')
    check_materialized(config_bytes, out)
    assets = []
    kinds = {'app-start.bin': 'start-app', 'app-final.bin': 'target-app', 'X-Track-Boot.bin': 'external-boot',
        'full.etu': 'auxiliary-full', 'patch.etu': 'patch', 'reference-1MiB.etu': 'reference', 'recovery.bin': 'recovery'}
    for name, kind in kinds.items():
        raw = (out / 'prepared' / name).read_bytes()
        assets.append(dict(fileName=name, kind=kind, sizeBytes=len(raw), sha256=m.sha(raw)))
    result['assets'] = assets
    m.save_json(out / 'evidence/benchmark-verification.json', result)
    metadata = dict(schema='p51-archived-benchmark-v1', mode='archived-benchmark', task='P5-1', runner=owner,
        packagePurpose='fixed-load-benchmark', representativeFunctionalSample=False, isFormalRelease=False,
        productionPublishable=False, readyRegistered=False, sourceCompilations=0, finalizations=0,
        originalSourceProof=data['proof'], sourceProofSha256=m.sha((out / 'inputs/benchmark-source.json').read_bytes()),
        verificationSha256=m.sha((out / 'evidence/benchmark-verification.json').read_bytes()),
        versionName=config['targetVersion'], versionCode=30321, targetImageSha256=m.sha(data['target']),
        baseVersionName=config['baseVersion'], baseVersionCode=30320, baseImageSha256=m.sha(data['base']),
        assets=assets, reference=dict(aliasOf='patch.etu', totalLength=1048576, fullConsumption=True),
        noCloudMutation=True, noDeviceOperation=True, normalAssetsUnchanged=True, hardwareAcceptance='NOT_RUN')
    m.save_json(out / 'prepared/benchmark-metadata.json', metadata)
    return metadata


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('mode', choices=('inputs', 'check', 'package'))
    parser.add_argument('--root-out', type=Path, required=True)
    parser.add_argument('--cc', default='gcc')
    args = parser.parse_args()
    m.require(Path.cwd() == ROOT and sys.flags.isolated and sys.flags.no_site and sys.dont_write_bytecode,
        'Use explicit worktree cwd and Python -I -S -B')
    config = (ROOT / MANIFEST).read_bytes()
    if args.mode == 'inputs':
        materialize(config, args.root_out)
    elif args.mode == 'check':
        m.require(not os.environ.get('OTA_AES_KEY'), 'Benchmark check must not receive the key')
        check_materialized(config, args.root_out)
    else:
        package(config, args.root_out, args.cc)
    print('P51_BENCHMARK_' + args.mode.upper() + '_COMPLETE; physical acceptance NOT_RUN')


if __name__ == '__main__':
    def cancelled(signum, frame):
        raise InterruptedError('benchmark adapter cancelled')
    signal.signal(signal.SIGTERM, cancelled)
    try:
        main()
    except Exception as error:
        print(json.dumps(m.failure_diagnostic(error)), file=sys.stderr)
        raise SystemExit(1)
