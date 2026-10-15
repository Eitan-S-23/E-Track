"""Retain existing P4-1 readiness originals; no builds or remote operations.

Adapted from the prior archive-p41-bootstrap.py fixed-input archive helper.
Run from the original exclusive worktree. Default mode checks a write plan only.
"""
import argparse
import hashlib
import io
import json
import re
import stat
import subprocess
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DEST = ROOT / 'docs/ota-exec-notes/P4-1-readiness-2026-10-16'
COMMIT = '18c4da4d28c1f2bcf7175f4b461e2a6bf462a23e'
CHECKOUT = '5b1c50f526f0edf90884b58c1c321593b7db0d1f'
MAIN = 'b42d3e25db85d6aba397cb4d0fb34bb5b653904f'
RUNS = {'fw': 38788072495, 'cf': 38788072597, 'gov': 38788072424, 'app': 38788072457}
ARTIFACTS = {11999665013, 11999610067, 11999325159, 11998528211,
             11998428426, 11998169541, 11998473287, 11997994989}


def guard(value):
    value = Path(value)
    actual = value.resolve(strict=False)
    actual.relative_to(ROOT)
    for parent in (value, *value.parents):
        if parent.exists() and getattr(parent.lstat(), 'st_file_attributes', 0) & stat.FILE_ATTRIBUTE_REPARSE_POINT:
            raise RuntimeError('Reparse point: ' + str(parent))
    return actual


def read(value):
    return guard(ROOT / value).read_bytes()


def obj(value):
    return json.loads(read(value))


def sha(data):
    return hashlib.sha256(data).hexdigest()


def encoded(value):
    return (json.dumps(value, ensure_ascii=True, indent=2) + '\n').encode()


def decoded(data):
    return re.sub(r'\x1b\[[0-9;]*[A-Za-z]', '', data.decode('utf-8-sig'))


assert Path.cwd().resolve() == ROOT
assert str(ROOT).replace('\\', '/').lower() == 'd:/github/my/e-track/.cache/p41-dev-20261015'
parser = argparse.ArgumentParser()
parser.add_argument('--apply', action='store_true')
parser.add_argument('--expected-plan-sha')
args = parser.parse_args()
payloads, origins = {}, {}


def add(name, data, source):
    assert name not in payloads
    payloads[name], origins[name] = data, source


github_names = ['main.json', 'environments.json', 'pr-before.json', 'push.json', 'runs-1.json',
                'pr.json', 'source-commit.json', 'main-after-code.json', 'merge-commit.json',
                'runs-2.json', 'fw-artifacts.json', 'gov-artifacts.json']
github_names += [label + '-' + kind for label in RUNS for kind in ['jobs.json', 'logs.zip']]
github_names += ['artifact-' + str(artifact_id) + '.zip' for artifact_id in sorted(ARTIFACTS)]
for name in github_names:
    source = '.cache/github/p41-ready-' + name
    add('github/' + Path(source).name, read(source), source)

labels = ['p41-ready-host', 'p41-ready-workflow', 'p41-ready-governance', 'p41-ready-types',
          'p41-ready-scripts', 'p41-ready-key-host', 'p41-ready-key-workflow', 'p41-ready-key-types',
          'p41-ready-lifecycle-host', 'p41-ready-lifecycle-workflow', 'p41-ready-final-bytes',
          'p41-ready-final-governance', 'p41-ready-final-types', 'p41-ready-stage', 'p41-ready-commit']
local_rows = []
for label in labels:
    receipt = obj('.cache/logs/' + label + '.json')
    assert receipt['closed'] and receipt['exitCode'] == 0
    for suffix in ['.json', '.stdout.txt', '.stderr.txt']:
        source = '.cache/logs/' + label + suffix
        add('commands/' + label + suffix, read(source), source)
    stdout = decoded(read('.cache/logs/' + label + '.stdout.txt'))
    stderr = decoded(read('.cache/logs/' + label + '.stderr.txt'))
    local_rows.append({'label': label, 'exitCode': receipt['exitCode'], 'closed': receipt['closed'],
                       'vitest': [int(n) for n in re.findall(r'\bTests\s+(\d+) passed', stdout)],
                       'node': [int(n) for n in re.findall(r'\u2139 tests (\d+)', stdout)],
                       'python': [int(n) for n in re.findall(r'Ran (\d+) tests', stdout + stderr)]})
assert next(row for row in local_rows if row['label'] == 'p41-ready-lifecycle-host')['vitest'] == [134]
assert next(row for row in local_rows if row['label'] == 'p41-ready-lifecycle-workflow')['node'] == [57]
assert next(row for row in local_rows if row['label'] == 'p41-ready-final-bytes')['node'] == [22]
assert next(row for row in local_rows if row['label'] == 'p41-ready-final-governance')['python'] == [23]
assert next(row for row in local_rows if row['label'] == 'p41-ready-scripts')['vitest'] == [34]
assert not (ROOT / '.cache/logs/p41-ready-gov-r2.json').exists()

for name in ['read-only.json', 'independent-development-review.json']:
    source = '.cache/p41-ready-20261016/' + name
    add('observations/' + name, read(source), source)
for name in ['run.cjs', 'gh.cjs', 'archive-p41-ready.py', 'inspect-p41-ready.py']:
    add('helpers/' + name, read('.cache/' + name), '.cache/' + name)
add('helpers/read-only.cjs', read('.cache/p41-ready-20261016/read-only.cjs'),
    '.cache/p41-ready-20261016/read-only.cjs')

source_commit = obj('.cache/github/p41-ready-source-commit.json')
merge_commit = obj('.cache/github/p41-ready-merge-commit.json')
assert source_commit['sha'] == COMMIT and merge_commit['sha'] == CHECKOUT
assert source_commit['tree']['sha'] == merge_commit['tree']['sha']
assert {p['sha'] for p in merge_commit['parents']} == {COMMIT, MAIN}
pr = obj('.cache/github/p41-ready-pr.json')
assert pr['draft'] and pr['state'] == 'open' and not pr['merged']
assert pr['head']['sha'] == COMMIT and pr['base']['sha'] == MAIN
runs = obj('.cache/github/p41-ready-runs-2.json')['workflow_runs']
assert {run['id'] for run in runs} == set(RUNS.values())
assert all(run['head_sha'] == COMMIT and run['event'] == 'pull_request' and run['run_attempt'] == 1
           and run['status'] == 'completed' and run['conclusion'] == 'success' for run in runs)
jobs = {}
for name, run_id in RUNS.items():
    listing = obj('.cache/github/p41-ready-' + name + '-jobs.json')
    assert listing['total_count'] == len(listing['jobs'])
    assert all(job['run_id'] == run_id and job['head_sha'] == COMMIT and job['status'] == 'completed'
               and job['conclusion'] in ('success', 'skipped') for job in listing['jobs'])
    jobs[name] = listing['jobs']
assert {job['name'] for job in jobs['fw'] if job['conclusion'] == 'skipped'} == {
    'Isolated firmware binding qualification (not rehearsal)',
    'Firmware rehearsal (shared release implementation)', 'Firmware production (shared release implementation)'}
assert {job['name'] for job in jobs['app'] if job['conclusion'] == 'skipped'} == {
    'Build Android APK', 'Build Windows EXE', 'Deploy GitHub Pages', 'Create GitHub Release'}


def log(label, fragment, aggregate=False):
    with zipfile.ZipFile(ROOT / '.cache/github' / f'p41-ready-{label}-logs.zip') as archive:
        names = [name for name in archive.namelist() if fragment in name and ('/' not in name) == aggregate]
        assert len(names) == 1, names
        return decoded(archive.read(names[0]))


tooling = log('fw', 'Release tooling', True)
governance = log('gov', 'Validate acceptance', True)
backend = log('cf', 'Worker Typecheck', True)
ordinary_log = log('fw', '/11_Build firmware.txt')
keyed_log = log('fw', '/19_Exercise the shared key-bound')
host_log = log('fw', '/12_Run host tests')
vendor_log = log('fw', '/12_Build the existing vendor')
cleanup_log = log('fw', '/20_Check development key cleanup')
assert [int(n) for n in re.findall(r'\bTests\s+(\d+) passed', tooling)] == [34, 134, 156]
assert [int(n) for n in re.findall(r'\u2139 tests (\d+)', tooling)] == [57, 22]
assert [int(n) for n in re.findall(r'Ran (\d+) tests', tooling)] == [8, 9]
governance_counts = [int(n) for n in re.findall(r'Ran (\d+) tests', governance)]
assert governance_counts == [127, 36, 3, 14, 11, 62, 39, 29]
assert [int(n) for n in re.findall(r'\bTests\s+(\d+) passed', backend)] == [156]
for content in [ordinary_log, keyed_log]:
    assert len(re.findall(r'warning:', content)) == 640
    assert not re.search(r'error:', content)
assert len(re.findall(r'warning:', vendor_log)) == 6
assert '{"privateBuildKeyAbsent":true}' in cleanup_log
fixture = json.loads(next(line.split('BYTE_FIXTURE ', 1)[1] for line in tooling.splitlines() if 'BYTE_FIXTURE {' in line))
cli = json.loads(next(line.split('PREPARATION_CLI ', 1)[1] for line in tooling.splitlines() if 'PREPARATION_CLI {' in line))
assert cli['exitCode'] == 0 and cli['missingKeyExit'] == 2

artifact_rows, member_rows = [], []
for name, run_id in [('fw', RUNS['fw']), ('gov', RUNS['gov'])]:
    listing = obj('.cache/github/p41-ready-' + name + '-artifacts.json')
    assert listing['total_count'] == len(listing['artifacts'])
    for item in listing['artifacts']:
        assert item['id'] in ARTIFACTS
        archive_name = 'p41-ready-artifact-' + str(item['id']) + '.zip'
        data = read('.cache/github/' + archive_name)
        assert len(data) == item['size_in_bytes'] and 'sha256:' + sha(data) == item['digest']
        assert item['workflow_run']['head_sha'] == COMMIT and item['workflow_run']['id'] == run_id
        artifact_rows.append({**item, 'archivedAs': 'github/' + archive_name})
        with zipfile.ZipFile(io.BytesIO(data)) as archive:
            assert len(archive.namelist()) == len(set(archive.namelist()))
            for member in archive.infolist():
                assert Path(member.filename).name.lower() != 'private-key.h'
                content = archive.read(member)
                member_rows.append({'archive': 'github/' + archive_name, 'member': member.filename,
                                    'sizeBytes': len(content), 'sha256': sha(content), 'zipTimestamp': list(member.date_time)})
assert {item['id'] for item in artifact_rows} == ARTIFACTS


def selected(artifact_id, name, target=None):
    archive_name = f'p41-ready-artifact-{artifact_id}.zip'
    with zipfile.ZipFile(ROOT / '.cache/github' / archive_name) as archive:
        data = archive.read(name)
    if target:
        add('selected/' + target, data, 'github/' + archive_name + '!' + name)
    return data


def package(artifact_id, prefix, label, expect_patch):
    metadata_data = selected(artifact_id, prefix + 'cloudflare-firmware-release-metadata.json', label + '/metadata.json')
    summary_data = selected(artifact_id, prefix + 'verification.json', label + '/verification.json')
    metadata, summary = json.loads(metadata_data), json.loads(summary_data)
    final = selected(artifact_id, prefix + 'app-final.bin')
    assert summary['ok'] is True and summary['preparedMetadataSha256'] == sha(metadata_data)
    assert summary['finalImage']['sha256'] == sha(final) == metadata['targetImageSha256']
    assert summary['fullByteEqual'] is True and summary['recoveryVerified'] is True
    assert summary['patchByteEqual'] is expect_patch and summary['r2Verified'] is False
    assert selected(artifact_id, prefix + 'work/full-candidate.bin') == final
    assert selected(artifact_id, prefix + 'work/recovery-app.bin') == final
    if expect_patch:
        assert selected(artifact_id, prefix + 'work/patch-candidate.bin') == final
    for asset in metadata['assets']:
        content = selected(artifact_id, prefix + asset['fileName'])
        assert len(content) == asset['sizeBytes'] and sha(content) == asset['sha256'] and asset['r2Verified'] is False
    for step in summary['steps']:
        assert step['exitCode'] == 0
        assert sha(selected(artifact_id, prefix + 'steps/' + step['label'] + '.stdout.txt')) == step['stdoutSha256']
        assert sha(selected(artifact_id, prefix + 'steps/' + step['label'] + '.stderr.txt')) == step['stderrSha256']
    return summary


prefix = 'firmware-release-tests/' + fixture['path'].split('/.cache/firmware-release-tests/', 1)[1] + '/'
synthetic = package(11998428426, prefix, 'synthetic-three-assets', True)
ordinary = package(11998169541, '', 'ordinary-gcc-development', None)
keyed = package(11999325159, 'prepared/', 'keyed-gcc-development', None)
for artifact_id, prefix, label in [(11998169541, '', 'ordinary-gcc-development'),
                                    (11999325159, 'prepared/', 'keyed-gcc-development'),
                                    (11999325159, 'build/', 'keyed-build')]:
    marker = selected(artifact_id, prefix + 'DEVELOPMENT-ONLY.json', label + '/DEVELOPMENT-ONLY.json')
    assert json.loads(marker)['installable'] is False

ordinary_inputs = json.loads(selected(11999610067, 'gcc-build-inputs.json', 'ordinary-gcc-build-inputs.json'))
assert ordinary_inputs['commitSha'] == CHECKOUT and ordinary['build'] == ordinary_inputs
for kind, artifact_id in [('app', 11999610067), ('boot', 11999665013)]:
    content = selected(artifact_id, ordinary_inputs[kind]['fileName'])
    assert sha(content) == ordinary_inputs[kind]['sha256'] and len(content) == ordinary_inputs[kind]['sizeBytes']
assert selected(11998528211, 'source-commit.txt').decode().strip() == CHECKOUT
key_inputs = json.loads(selected(11999325159, 'build/gcc-build-inputs.json', 'keyed-build/gcc-build-inputs.json'))
key_evidence = json.loads(selected(11999325159, 'build/keyed-build-evidence.json', 'keyed-build/keyed-build-evidence.json'))
key_source = subprocess.check_output(['git', '--no-optional-locks', 'show', COMMIT + ':Libraries/OTA/ota_keys.c'], cwd=ROOT)
header = ''.join(f'#define OTA_AES_KEY_1_WORD{index} 0x01010101u\n' for index in range(4)).encode()
expected_key = {'schemaVersion': 1, 'keyId': 1, 'source': 'development-ci-key-v1',
                'keySha256': sha(bytes([1]) * 16), 'headerSha256': sha(header), 'keySourceSha256': sha(key_source)}
assert key_evidence['keyBinding'] == key_inputs['keyBinding'] == expected_key
assert key_inputs == keyed['build'] and key_inputs['commitSha'] == CHECKOUT
assert key_evidence['bootKeyConsumer'] is False and key_evidence['compilerCache'] == 'DISABLED'
assert key_evidence['sourceDateEpoch'] == '1786320000'
cache = selected(11999325159, 'build/CMakeCache.txt', 'keyed-build/CMakeCache.txt')
rules = selected(11999325159, 'build/compiler-launchers.ninja', 'keyed-build/compiler-launchers.ninja')
assert sha(cache) == key_evidence['compilerCacheConfigSha256']
assert sha(rules) == key_evidence['compilerLaunchersSha256']
assert re.search(rb'^KEIL_GCC_COMPILER_CACHE:STRING=OFF\r?$', cache, re.M)
assert not re.search(rb'(?:^|[\\/\s])(?:sccache|ccache)(?:\.exe)?(?:\s|$)', rules, re.M | re.I)
key_command = key_evidence['keyCompileCommand']
assert key_command['file'].endswith('/Libraries/OTA/ota_keys.c')
assert 'CMakeFiles/X_Track_App_GCC.dir/' in key_command['command']
assert '-include "/home/runner/work/E-Track/E-Track/.cache/keyed-development-build/private-key.h"' in key_command['command']
assert 'OTA_AES_KEY_1_WORD' not in key_command['command']
for artifact in key_evidence['artifacts']:
    content = selected(11999325159, 'build/' + artifact['path'])
    assert sha(content) == artifact['sha256'] and len(content) == artifact['sizeBytes']
    assert re.fullmatch(r'2026-10-15T18:45:[0-9]{2}\.[0-9]{3}Z', artifact['modifiedAt'])
for step in key_evidence['steps']:
    assert step['exitCode'] == 0 and step['errorLines'] == 0
    stdout = selected(11999325159, 'build/steps/' + step['label'] + '.stdout.txt')
    stderr = selected(11999325159, 'build/steps/' + step['label'] + '.stderr.txt')
    assert sha(stdout) == step['stdoutSha256'] and sha(stderr) == step['stderrSha256']
    assert len(re.findall(rb'warning:', stdout + stderr)) == step['warningLines']
assert next(step for step in key_evidence['steps'] if step['label'] == 'build')['warningLines'] == 640
assert key_inputs['app']['sha256'] != ordinary_inputs['app']['sha256']
assert key_inputs['boot'] == ordinary_inputs['boot']
for summary in [ordinary, keyed]:
    assert summary['commitSha'] == CHECKOUT and summary['runId'] == str(RUNS['fw']) and summary['versionName'] == '2.7.0'

read_only = obj('.cache/p41-ready-20261016/read-only.json')
assert read_only['ok'] and read_only['mode'] == 'READ_ONLY'
assert all(request['method'] == 'GET' for request in read_only['requests'])
assert read_only['cloudflareTokenActive'] and read_only['cloudflarePolicy']['status'] == 403
assert read_only['repositorySecrets']['names'] == ['ETRACK_DEV_SIGNING_KEYSTORE']
assert read_only['repositoryVariables']['total'] == 0
assert obj('.cache/github/p41-ready-environments.json')['total_count'] == 0

inspection = {'scope': 'Development implementation/readiness evidence; not formal acceptance or rehearsal',
              'branch': 'dev/p4-1/unattended-20261015', 'testedCommit': COMMIT, 'actualPrCheckout': CHECKOUT,
              'sourceAndCheckoutTree': source_commit['tree']['sha'], 'remoteMain': MAIN,
              'runs': RUNS, 'wholeCard': 'IN_PROGRESS', 'runtimeBindingQualification': 'NOT_RUN',
              'canonicalRehearsal': 'NOT_RUN', 'production': 'NOT_RUN', 'independentAcceptance': 'NOT_RUN',
              'counts': {'hostScriptsAndMigration': 34, 'pipelineHost': 134, 'nativeWorkerd': 156,
                         'workflow': 57, 'bytes': 22, 'package': 8, 'goldenVectors': 9},
              'governanceSuiteCounts': governance_counts, 'backendNativeRepeatedCount': 156,
              'countPolicy': 'Separate suites; repeated native runs and aggregate/step logs are not added together',
              'diagnostics': {'ordinaryGccWarnings': 640, 'ordinaryGccErrors': 0,
                              'keyedGccWarnings': 640, 'keyedGccErrors': 0, 'vendorWarnings': 6,
                              'ordinarySizeOutput': log('fw', '/15_Report firmware artifacts').splitlines()[-4:],
                              'keyedSizeOutput': selected(11999325159, 'build/steps/size.stdout.txt').decode(),
                              'policy': 'Only actual compiler/linker steps counted; expected host negative diagnostics retained separately'},
              'firmwareHostMarkers': re.findall(r'\b[A-Z][A-Z0-9_]+=(?:PASS|FAIL)[^\r\n]*', host_log),
              'cliPositiveAndNegative': cli, 'syntheticFixture': fixture, 'syntheticThreeAssets': synthetic,
              'ordinaryGccDevelopment': ordinary, 'keyedGccDevelopment': keyed,
              'ordinaryBuildInputs': ordinary_inputs, 'keyedBuildEvidence': key_evidence,
              'localCommands': local_rows, 'plannedOnlyNotRun': ['p41-ready-gov-r2'],
              'privateHeaderInArtifact': False, 'cleanupOriginal': 'github/p41-ready-fw-logs.zip!Build firmware (arm-none-eabi-gcc)/20_Check development key cleanup before archiving.txt',
              'artifacts': artifact_rows,
              'jobs': {key: [{'id': job['id'], 'name': job['name'], 'conclusion': job['conclusion']} for job in value]
                       for key, value in jobs.items()},
              'ownerPrerequisites': ['Authorized production-free Cloudflare account and constrained runtime credential',
                                    'Reviewed target/fixture rebinding and protected environment configuration',
                                    'Owner-approved non-development OTA key in the existing protected secret interface',
                                    'Exact final target/descriptor approval and admitted one canonical rehearsal'],
              'preservedBoundaries': ['No main-before-acceptance prerequisite', 'No provisioning-token export',
                                     'No additional key-hash approval variable', 'No bootstrap archive rewrite',
                                     'No new device operation or other task start', 'Historical P41-AUDIT-01 remains attribution-unresolved']}
add('ci-inspection.json', encoded(inspection), 'Derived from retained original logs, API responses and artifact bytes')
add('artifact-members.json', encoded(member_rows), 'Derived from the eight original artifact ZIPs; ZIP timestamps explicitly labelled')

token_pattern = re.compile(rb'\b(?:gh[pousr]_[A-Za-z0-9]{20,}|github_pat_[A-Za-z0-9_]{30,})\b')
for name, data in payloads.items():
    assert not token_pattern.search(data), 'Credential pattern: ' + name
    if name.endswith('.zip'):
        with zipfile.ZipFile(io.BytesIO(data)) as archive:
            for member in archive.infolist():
                assert not token_pattern.search(archive.read(member)), 'Credential pattern in ZIP member'
attributes = guard(DEST / '.gitattributes').read_bytes()
assert attributes == b'* -text\n'
inventory = [{'path': '.gitattributes', 'sizeBytes': len(attributes), 'sha256': sha(attributes), 'source': 'Evidence byte-preservation rule'}]
inventory += [{'path': name, 'sizeBytes': len(data), 'sha256': sha(data), 'source': origins[name]}
              for name, data in sorted(payloads.items())]
add('inventory.json', encoded({'testedCommit': COMMIT, 'files': inventory}), 'Inventory excluding itself')
targets = [guard(DEST / name) for name in sorted(payloads)]
assert all(not target.exists() for target in targets), 'Refusing to replace prior evidence'
plan_sha = sha(encoded([str(target) for target in targets]))
print(json.dumps({'preflight': 'PASS', 'root': str(ROOT), 'targets': [str(target) for target in targets], 'planSha256': plan_sha}))
print(json.dumps({'inspection': 'PASS', 'counts': inspection['counts'], 'governance': governance_counts,
                  'diagnostics': inspection['diagnostics'], 'archiveFiles': len(payloads) + 1,
                  'archiveBytes': len(attributes) + sum(map(len, payloads.values()))}))
if args.apply:
    assert args.expected_plan_sha == plan_sha, 'Output plan changed'
    for name, data in payloads.items():
        target = guard(DEST / name)
        target.parent.mkdir(parents=True, exist_ok=True)
        with guard(target).open('xb') as stream:
            stream.write(data)
        assert target.read_bytes() == data
    print(json.dumps({'archivedFiles': len(payloads) + 1, 'inventorySha256': sha(payloads['inventory.json'])}))
