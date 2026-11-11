"""Admit the current normal GCC executable, without any benchmark package."""
import argparse
import hashlib
import io
import json
import os
from pathlib import Path
import subprocess
import sys
import zipfile

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'Tools/ota/p34-acceptance'))
import live_host as h


def read_pin(pin):
    path = (ROOT / pin['path']).resolve(strict=True)
    path.relative_to(ROOT)
    raw = path.read_bytes()
    assert len(raw) == pin['bytes'] and hashlib.sha256(raw).hexdigest() == pin['sha256'], 'Source pin mismatch'
    return raw


def materialize(out):
    assert not os.environ.get('OTA_AES_KEY'), 'Source admission must not receive the packaging key'
    config = h.read_json(ROOT / 'Tools/ota/admin-candidate-inputs.json')
    assert config['schema'] == 'original-admin-normal-source-v1'
    requested_base = os.environ.get('INPUT_CANDIDATE_BASE_VERSION', '')
    assert not requested_base or requested_base == config['installedBaseline']['versionName'], 'Requested delta base is not the pinned original-Admin baseline'
    delivery = json.loads(read_pin(config['sourceDelivery']))
    archive = read_pin(config['sourceArchive'])
    artifact = delivery['artifact']
    assert delivery['source'] == artifact['workflow_run']['head_sha'] == config['sourceCommit']
    assert delivery['run'] == artifact['workflow_run']['id']
    assert artifact['digest'] == 'sha256:' + hashlib.sha256(archive).hexdigest()
    assert artifact['size_in_bytes'] == len(archive)
    # A cached build is reusable only while every firmware input is unchanged.
    comparison = subprocess.run(['git', 'diff', '--exit-code', config['sourceCommit'], 'HEAD', '--',
        *config['productPaths']], cwd=ROOT, capture_output=True, timeout=30, check=False)
    assert comparison.returncode == 0, 'Firmware source changed: obtain a fresh verified GCC source archive'
    head = subprocess.run(['git', 'rev-parse', 'HEAD'], cwd=ROOT, capture_output=True, timeout=15, check=True).stdout.decode().strip()
    assert head == os.environ['GITHUB_SHA']
    with zipfile.ZipFile(io.BytesIO(archive)) as bundle:
        rows = bundle.infolist()
        assert len(rows) == len({row.filename for row in rows}) <= 10000
        assert sum(row.file_size for row in rows) < 300 * 1024 * 1024
        names = ('gcc-build-inputs.json', 'keyed-build-evidence.json', 'steps.json', 'CMakeCache.txt',
                 'compile_commands.json', 'compiler-launchers.ninja', 'app/X-Track-App-GCC.bin',
                 'app/X-Track-App-GCC.elf', 'app/X-Track-App-GCC.map', 'boot/X-Track-Boot.bin')
        files = {name: bundle.read('keyed-build/' + name) for name in names}
        assert json.loads(bundle.read('evidence/cleanup.json')) == {'privateAbsent': True}
        build = json.loads(files['gcc-build-inputs.json'])
        evidence = json.loads(files['keyed-build-evidence.json'])
        assert build['commitSha'] == evidence['commitSha'] == config['sourceCommit']
        assert build['keyBinding'] == evidence['keyBinding'] and build['keyBinding']['source'] == 'approved-ci-key-v1'
        assert build['buildConfiguration'] == evidence['buildConfiguration']
        assert build['buildConfiguration']['actualProfile'] == config['profile']
        assert evidence['steps'] == json.loads(files['steps.json'])
        assert [row['label'] for row in evidence['steps']] == ['configure', 'build', 'size']
        assert all(row['exitCode'] == row['errorLines'] == 0 for row in evidence['steps'])
        for pin in evidence['artifacts']:
            raw = bundle.read('keyed-build/' + pin['path'])
            assert len(raw) == pin['sizeBytes'] and hashlib.sha256(raw).hexdigest() == pin['sha256']
    out = h.checked(out)
    for name in (*files, 'source-proof.json', 'installed-baseline.bin'):
        h.checked(out / name)
    h.fresh(out)
    for name, raw in files.items():
        h.raw(out / name, raw)
    h.raw(out / 'installed-baseline.bin', read_pin(config['installedBaseline']))
    h.save(out / 'source-proof.json', dict(schema='original-admin-normal-source-proof-v1',
        config=config, sourceCommit=config['sourceCommit'], verifiedAgainst=head, sourceMatches=True,
        keyedBuildStage='PASS', originalWholeRun='FAIL_AFTER_SUCCESSFUL_BUILD_NOT_RECLASSIFIED',
        priorBuildWarnings=sum(row['warningLines'] for row in evidence['steps']),
        importedBenchmarkPackages=0, sourceCompilations=0,
        files=[h.record(out / name) for name in (*names, 'installed-baseline.bin')]))
    print('NORMAL_GCC_SOURCE_MATCHES_CURRENT_CHECKOUT; no benchmark package imported', flush=True)


if __name__ == '__main__':
    assert Path.cwd() == ROOT and sys.flags.isolated and sys.flags.no_site and sys.dont_write_bytecode
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--out', type=Path, required=True)
    materialize(parser.parse_args().out)
