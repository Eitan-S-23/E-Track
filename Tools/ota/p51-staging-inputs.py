"""Read-only archive admission; copy exact selected bytes, never prepare firmware."""
import argparse
import importlib.util
import io
import json
import os
from pathlib import Path
import sys
import zipfile

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / '.cache/p51-staging/python'))
spec = importlib.util.spec_from_file_location('p51_archive', ROOT / 'Tools/ota/p51-package.py')
m = importlib.util.module_from_spec(spec)
spec.loader.exec_module(m)


def resolve_staging(config):
    m.require(config['schema'] == 'p51-candidate-staging-inputs-v1'
              and config['task'] == 'P51-CANDIDATE-STAGING-01' and config['profile'] == 'p34-v2-candidate',
              'Staging input contract/profile mismatch')
    original = json.loads(m.read(config['sourceInputs']))
    data = m.resolve_supplement(original)
    meta = data['originalMetadata']
    m.require((meta['versionName'], meta['versionCode'], meta['baseVersionCode'], meta['baseImageSha256']) ==
              (config['versionName'], config['versionCode'], config['baseVersionCode'], config['baseImageSha256']),
              'Staging target/base identity mismatch')
    m.require([a['kind'] for a in config['assets']] == ['full', 'patch', 'recovery'], 'Staging three-asset inventory')
    with zipfile.ZipFile(io.BytesIO(m.read(original['archive']))) as archive:
        image = m.verified(archive.read(config['finalImage']['member']), config['finalImage'])
        blobs = [m.verified(archive.read(a['member']), a) for a in config['assets']]
        verification_bytes = m.verified(archive.read(config['verification']['member']), config['verification'])
        metadata_bytes = m.verified(archive.read(original['members']['metadata']['member']), original['members']['metadata'])
        build_bytes = m.verified(archive.read(original['members']['build']['member']), original['members']['build'])
        keyed_bytes = m.verified(archive.read(original['members']['keyedEvidence']['member']), original['members']['keyedEvidence'])
    fields = m.recovery.validate_app(image)
    m.require(fields['version_code'] == config['versionCode'] and fields['version_name'] == config['versionName']
              and fields['build_ts'] == original['buildTimestamp'] and meta['targetImageSha256'] == m.sha(image)
              and meta['finalization']['target']['sha256'] == m.sha(image), 'Staging finalized image lineage')
    for rec, blob in zip(config['assets'], blobs):
        asset = next(a for a in meta['assets'] if a['fileName'] == rec['member'].split('/')[-1])
        m.require(asset['kind'] == rec['kind'] and asset['sha256'] == m.sha(blob) and asset['sizeBytes'] == len(blob),
                  'Staging archived asset lineage')
        if rec['kind'] == 'patch':
            m.require(asset['baseVersionCode'] == config['baseVersionCode']
                      and asset['baseImageSha256'] == config['baseImageSha256'], 'Staging patch base lineage')
        if rec['kind'] == 'recovery':
            raw, kind = m.recovery.split_asset(blob, 'recovery')
            m.require(kind == 'recovery' and raw == image, 'Staging recovery image mismatch')
    verification = json.loads(verification_bytes)
    m.require(all(verification[k] is True for k in ('fullByteEqual', 'patchByteEqual', 'recoveryByteEqual', 'referenceAliasesPatch'))
              and verification['referenceBytes'] == 1048576 and verification['native']['warnings'] == 0
              and verification['native']['errors'] == 0 and len(verification['native']['checks']) == 12
              and all(c['observation']['passed'] for c in verification['native']['checks']), 'Staging original native verification')
    proof = dict(schema='p51-staging-source-proof-v1', originalOwner=dict(data['originalOwner'],
        artifactId=original['originalArtifact'], buildTimestamp=original['buildTimestamp']),
        archive=original['archive'], artifactReceipt=original['artifact'], originalMetadata=original['members']['metadata'],
        build=original['members']['build'], keyedEvidence=original['members']['keyedEvidence'],
        verification=config['verification'], sourceCompilations=0, finalizations=0, packageGenerations=0,
        referenceSearches=0, assets=config['assets'], finalImage=config['finalImage'])
    return dict(proof=proof, image=image, blobs=blobs, metadata=metadata_bytes, build=build_bytes,
                keyed=keyed_bytes, verification=verification_bytes)


def materialize(config, out):
    m.require(not any(v for k, v in os.environ.items() if k.startswith(('TRACE_', 'CLOUDFLARE_', 'CF_', 'GH_', 'OTA_AES_KEY', 'GITHUB_TOKEN'))),
              'Staging archive admission must not receive cloud/key credentials')
    out = m.checked(out)
    m.require(not out.exists(), 'Preserve previous staging attempt')
    data = resolve_staging(config)
    # All admission succeeds before the first file is created.
    for rec, blob in zip(config['assets'], data['blobs']):
        m.save(out / 'assets' / rec['fileName'], blob)
    for name, key in [('candidate-metadata.json', 'metadata'), ('gcc-build-inputs.json', 'build'),
                      ('keyed-build-evidence.json', 'keyed'), ('native-verification.json', 'verification'), ('app-final.bin', 'image')]:
        m.save(out / 'inputs' / name, data[key])
    m.save_json(out / 'inputs/source-proof.json', data['proof'])


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--root-out', type=Path, required=True)
    args = parser.parse_args()
    m.require(Path.cwd() == ROOT and sys.flags.isolated and sys.flags.no_site and sys.dont_write_bytecode,
              'Explicit worktree and isolated Python required')
    config = json.loads((ROOT / 'Tools/ota/p51-staging-inputs.json').read_bytes())
    materialize(config, args.root_out)
    print('P51_IMMUTABLE_STAGING_INPUTS_VERIFIED')
