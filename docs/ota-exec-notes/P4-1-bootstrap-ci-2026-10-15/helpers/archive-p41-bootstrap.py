"""Inspect and retain existing P4-1 originals; no builds or remote operations."""
import argparse
import base64
import hashlib
import io
import json
import re
import stat
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DEST = ROOT / 'docs/ota-exec-notes/P4-1-bootstrap-ci-2026-10-15'
COMMIT = 'c860b3be7a0b1a3ca1b3a53cf79cc9ef21cc9124'
CHECKOUT = '76e8c8a924fe4dba642c9972fa6f9d698ff00436'
RUNS = {'fw': 38759988453, 'cf': 38759987935, 'gov': 38759987663, 'app': 38759988139}
ARTIFACTS = {11985646589, 11985631395, 11985436767, 11985177807, 11984993121, 11985271812, 11985027937}


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


assert Path.cwd().resolve() == ROOT
parser = argparse.ArgumentParser()
parser.add_argument('--apply', action='store_true')
parser.add_argument('--expected-plan-sha')
args = parser.parse_args()
payloads, origins = {}, {}


def add(name, data, source):
    assert name not in payloads
    payloads[name], origins[name] = data, source


github_names = ['app-jobs.json', 'app-logs.zip', 'cf-jobs.json', 'cf-logs.zip',
                'fw-artifacts.json', 'fw-jobs.json', 'fw-logs.zip', 'gov-artifacts-r2.json',
                'gov-jobs.json', 'gov-logs.zip', 'merge-commit.json', 'pr.json', 'push.json',
                'runs.json', 'runs-2.json', 'source-commit.json']
github_names += ['artifact-' + str(artifact_id) + '.zip' for artifact_id in sorted(ARTIFACTS)]
for name in github_names:
    source = '.cache/github/p41-resume-' + name
    add('github/' + Path(source).name, read(source), source)
for name in ['identity.json', 'releases.json', 'target-tag.json', 'archive-commit.json',
             'archive-tree.json', 'provenance-contents.json', 'app-contents.json',
             'descriptor-development-only.json', 'qualification.json']:
    source = '.cache/p41-bootstrap-readonly/' + name
    add('remote/' + name, read(source), source)
for label in ['p41-resume-stage', 'p41-resume-commit', 'p41-resume-remote-header']:
    for suffix in ['.json', '.stdout.txt', '.stderr.txt']:
        source = '.cache/logs/' + label + suffix
        add('commands/' + label + suffix, read(source), source)
for name in ['p41-bootstrap-readonly.mjs', 'archive-p41-bootstrap.py']:
    add('helpers/' + name, read('.cache/' + name), '.cache/' + name)

prior = obj('docs/ota-exec-notes/P4-1-bootstrap-followup-2026-10-15/local-inventory.json')
assert sha(read('docs/ota-exec-notes/P4-1-bootstrap-followup-2026-10-15/local-inventory.json')) == '80644f18a3ebd40f7ac62e4b2a3f208e8fd7d24594c46b6963b95c9037df755f'
assert not {entry['source'] for entry in prior['files']} & set(origins.values())
source_commit = obj('.cache/github/p41-resume-source-commit.json')
merge_commit = obj('.cache/github/p41-resume-merge-commit.json')
assert source_commit['sha'] == COMMIT and merge_commit['sha'] == CHECKOUT
assert source_commit['tree']['sha'] == merge_commit['tree']['sha']
assert {p['sha'] for p in merge_commit['parents']} == {COMMIT, 'b42d3e25db85d6aba397cb4d0fb34bb5b653904f'}
runs = obj('.cache/github/p41-resume-runs-2.json')['workflow_runs']
assert {r['id'] for r in runs} == set(RUNS.values())
assert all(r['head_sha'] == COMMIT and r['event'] == 'pull_request' and r['run_attempt'] == 1
           and r['status'] == 'completed' and r['conclusion'] == 'success' for r in runs)
jobs = {}
for name, run_id in RUNS.items():
    listing = obj('.cache/github/p41-resume-' + name + '-jobs.json')
    assert listing['total_count'] == len(listing['jobs'])
    assert all(j['run_id'] == run_id and j['head_sha'] == COMMIT and j['status'] == 'completed'
               and j['conclusion'] in ('success', 'skipped') for j in listing['jobs'])
    jobs[name] = listing['jobs']
assert {j['name'] for j in jobs['fw'] if j['conclusion'] == 'skipped'} == {
    'Firmware rehearsal (shared release implementation)', 'Firmware production (shared release implementation)'}
assert {j['name'] for j in jobs['app'] if j['conclusion'] == 'skipped'} == {
    'Build Android APK', 'Build Windows EXE', 'Deploy GitHub Pages', 'Create GitHub Release'}


def log(archive, member):
    with zipfile.ZipFile(ROOT / '.cache/github' / archive) as z:
        return re.sub(r'\x1b\[[0-9;]*[A-Za-z]', '', z.read(member).decode('utf-8-sig'))


def aggregate(archive, fragment):
    with zipfile.ZipFile(ROOT / '.cache/github' / archive) as z:
        name = next(n for n in z.namelist() if '/' not in n and fragment in n)
    return name, log(archive, name)


_, tooling = aggregate('p41-resume-fw-logs.zip', 'Release tooling')
_, governance = aggregate('p41-resume-gov-logs.zip', 'Validate acceptance')
_, backend = aggregate('p41-resume-cf-logs.zip', 'Worker Typecheck')
build_log = log('p41-resume-fw-logs.zip', 'Build firmware (arm-none-eabi-gcc)/11_Build firmware.txt')
host_log = log('p41-resume-fw-logs.zip', 'Build firmware (arm-none-eabi-gcc)/12_Run host tests (boot vectors, OTA host tests, P3-1 product regressions).txt')
vitest_counts = [int(n) for n in re.findall(r'\bTests\s+(\d+) passed', tooling)]
node_counts = [int(n) for n in re.findall(r'\u2139 tests (\d+)', tooling)]
python_counts = [int(n) for n in re.findall(r'Ran (\d+) tests', tooling)]
governance_counts = [int(n) for n in re.findall(r'Ran (\d+) tests', governance)]
assert vitest_counts == [34, 90, 156] and node_counts == [42, 22] and python_counts == [8, 9]
assert governance_counts == [127, 36, 3, 14, 11, 62, 39, 29]
assert [int(n) for n in re.findall(r'\bTests\s+(\d+) passed', backend)] == [156]
warning_lines = [line for line in build_log.splitlines() if 'warning:' in line]
error_lines = [line for line in build_log.splitlines() if 'error:' in line]
vendor_warnings = [line for line in tooling.splitlines() if 'warning:' in line]
assert len(warning_lines) == 640 and not error_lines and len(vendor_warnings) == 6
fixture = json.loads(next(line.split('BYTE_FIXTURE ', 1)[1] for line in tooling.splitlines() if 'BYTE_FIXTURE {' in line))
cli = json.loads(next(line.split('PREPARATION_CLI ', 1)[1] for line in tooling.splitlines() if 'PREPARATION_CLI {' in line))
assert cli['exitCode'] == 0 and cli['missingKeyExit'] == 2

artifact_rows, member_rows = [], []
for name, expected_run in [('fw-artifacts.json', RUNS['fw']), ('gov-artifacts-r2.json', RUNS['gov'])]:
    listing = obj('.cache/github/p41-resume-' + name)
    assert listing['total_count'] == len(listing['artifacts'])
    for item in listing['artifacts']:
        assert item['id'] in ARTIFACTS
        archive_name = 'p41-resume-artifact-' + str(item['id']) + '.zip'
        data = read('.cache/github/' + archive_name)
        assert len(data) == item['size_in_bytes'] and 'sha256:' + sha(data) == item['digest']
        assert item['workflow_run']['head_sha'] == COMMIT and item['workflow_run']['id'] == expected_run
        artifact_rows.append({**item, 'archivedAs': 'github/' + archive_name})
        with zipfile.ZipFile(io.BytesIO(data)) as z:
            for member in z.infolist():
                content = z.read(member)
                member_rows.append({'archive': 'github/' + archive_name, 'member': member.filename,
                                    'sizeBytes': len(content), 'sha256': sha(content), 'zipTimestamp': list(member.date_time)})
assert {a['id'] for a in artifact_rows} == ARTIFACTS


def package(artifact_id, prefix, label, expect_patch):
    archive_name = 'p41-resume-artifact-' + str(artifact_id) + '.zip'
    with zipfile.ZipFile(ROOT / '.cache/github' / archive_name) as z:
        def selected(name):
            return z.read(prefix + name)
        metadata_data, summary_data = selected('cloudflare-firmware-release-metadata.json'), selected('verification.json')
        metadata, summary = json.loads(metadata_data), json.loads(summary_data)
        final = selected('app-final.bin')
        assert summary['ok'] is True and summary['preparedMetadataSha256'] == sha(metadata_data)
        assert summary['finalImage']['sha256'] == sha(final) == metadata['targetImageSha256']
        assert summary['fullByteEqual'] is True and summary['recoveryVerified'] is True
        assert summary['patchByteEqual'] is expect_patch and summary['r2Verified'] is False
        assert selected('work/full-candidate.bin') == final == selected('work/recovery-app.bin')
        if expect_patch:
            assert selected('work/patch-candidate.bin') == final
        for asset in metadata['assets']:
            content = selected(asset['fileName'])
            assert len(content) == asset['sizeBytes'] and sha(content) == asset['sha256'] and asset['r2Verified'] is False
        for step in summary['steps']:
            assert step['exitCode'] == 0
            assert sha(selected('steps/' + step['label'] + '.stdout.txt')) == step['stdoutSha256']
            assert sha(selected('steps/' + step['label'] + '.stderr.txt')) == step['stderrSha256']
        for name, data in [('cloudflare-firmware-release-metadata.json', metadata_data), ('verification.json', summary_data)]:
            add('selected/' + label + '/' + name, data, 'github/' + archive_name + '!' + prefix + name)
        return summary


prefix = 'firmware-release-tests/' + fixture['path'].split('/.cache/firmware-release-tests/', 1)[1] + '/'
synthetic = package(11985631395, prefix, 'synthetic-three-assets', True)
gcc = package(11985646589, '', 'gcc-development', None)
assert gcc['commitSha'] == CHECKOUT and gcc['runId'] == str(RUNS['fw']) and gcc['versionName'] == '2.7.0'
with zipfile.ZipFile(ROOT / '.cache/github/p41-resume-artifact-11985646589.zip') as z:
    label = z.read('DEVELOPMENT-ONLY.json')
    assert json.loads(label)['installable'] is False
    add('selected/gcc-development/DEVELOPMENT-ONLY.json', label, 'github/p41-resume-artifact-11985646589.zip!DEVELOPMENT-ONLY.json')
with zipfile.ZipFile(ROOT / '.cache/github/p41-resume-artifact-11985177807.zip') as z:
    inputs = z.read('gcc-build-inputs.json')
    build = json.loads(inputs)
    assert build['commitSha'] == CHECKOUT and sha(z.read(build['app']['fileName'])) == build['app']['sha256']
    with zipfile.ZipFile(ROOT / '.cache/github/p41-resume-artifact-11985436767.zip') as boot_zip:
        assert sha(boot_zip.read(build['boot']['fileName'])) == build['boot']['sha256']
    add('selected/gcc-build-inputs.json', inputs, 'github/p41-resume-artifact-11985177807.zip!gcc-build-inputs.json')
with zipfile.ZipFile(ROOT / '.cache/github/p41-resume-artifact-11984993121.zip') as z:
    assert z.read('source-commit.txt').decode().strip() == CHECKOUT

remote = obj('.cache/p41-bootstrap-readonly/qualification.json')
assert remote['ok'] and remote['closed'] and remote['remoteDownload'] == 'PASS'
assert remote['testedCommit'] == COMMIT and remote['remoteWrites'] == 0
assert remote['approvalOrigin'] == 'LOCAL_TEST_EXPECTATION_NOT_PROTECTED_APPROVAL'
assert remote['rehearsal'] == 'NOT_RUN' and remote['production'] == 'NOT_RUN'
assert len(remote['requests']) == 7 and remote['missingApprovalRejectedBeforeNetwork'] is True
for request in remote['requests']:
    assert request['method'] == 'GET'
    if not request['identitySanitized']:
        data = read('.cache/p41-bootstrap-readonly/' + request['file'])
        assert len(data) == request['sizeBytes'] and sha(data) == request['sha256']
contents = obj('.cache/p41-bootstrap-readonly/app-contents.json')
downloaded = base64.b64decode(contents['content'].replace('\n', ''), validate=True)
assert downloaded == read('.cache/p41-bootstrap-readonly/app-final.bin')
assert downloaded == read('docs/ota-exec-notes/P4-1-bootstrap-baseline-2026-10-15/app-final.bin')
header = obj('.cache/logs/p41-resume-remote-header.json')
assert header['closed'] and header['exitCode'] == 0

inspection = {'scope': 'Development feedback and read-only source qualification; not formal acceptance or rehearsal',
              'branch': 'dev/p4-1/unattended-20261015', 'testedCommit': COMMIT, 'actualPrCheckout': CHECKOUT,
              'sourceAndCheckoutTree': source_commit['tree']['sha'], 'runs': RUNS,
              'counts': {'hostScriptsAndMigration': 34, 'pipelineHost': 90, 'nativeWorkerd': 156,
                         'workflow': 42, 'bytes': 22, 'package': 8, 'goldenVectors': 9},
              'governanceSuiteCounts': governance_counts, 'backendNativeRepeatedCount': 156,
              'countPolicy': 'Separate suites; repeated native runs and aggregate/step logs are not added together',
              'diagnostics': {'gccCompilerLinkerWarnings': len(warning_lines), 'gccCompilerLinkerErrors': len(error_lines),
                              'vendorWarnings': len(vendor_warnings),
                              'gccSizeOutput': build_log.splitlines()[-8:],
                              'nativeDiagnosticPolicy': 'Expected negative-test diagnostics remain in original logs'},
              'firmwareHostMarkers': re.findall(r'\b[A-Z][A-Z0-9_]+=(?:PASS|FAIL)[^\r\n]*', host_log),
              'cliPositiveAndNegative': cli, 'syntheticFixture': fixture,
              'syntheticThreeAssets': synthetic, 'actualGccDevelopment': gcc, 'buildInputs': build,
              'artifacts': artifact_rows,
              'jobs': {key: [{'id': j['id'], 'name': j['name'], 'conclusion': j['conclusion']} for j in value]
                       for key, value in jobs.items()},
              'readOnlySource': remote,
              'retrievalIncident': {'label': 'p41-resume-gov-artifacts', 'toolExitCode': 1,
                                    'stderr': 'fetch failed', 'outputCreated': False,
                                    'recovery': 'One bounded GET retry, p41-resume-gov-artifacts-r2; no CI rerun'},
              'remaining': ['Authorized main integration and candidate activation', 'Protected environment approval/configuration',
                            'Canonical real rehearsal and independent production-zero-side-effect evidence', 'Formal acceptance']}
add('ci-inspection.json', encoded(inspection), 'Derived from retained original logs, API responses and artifact bytes')
add('artifact-members.json', encoded(member_rows), 'Derived from the seven original artifact ZIPs')

token_pattern = re.compile(rb'\b(?:gh[pousr]_[A-Za-z0-9]{20,}|github_pat_[A-Za-z0-9_]{30,})\b')
for name, data in payloads.items():
    assert not token_pattern.search(data), 'Credential pattern: ' + name
    if name.endswith('.zip'):
        with zipfile.ZipFile(io.BytesIO(data)) as z:
            for member in z.infolist():
                assert not token_pattern.search(z.read(member)), 'Credential pattern in ZIP member'
attributes = guard(DEST / '.gitattributes').read_bytes()
assert attributes == b'* -text\n'
inventory = [{'path': '.gitattributes', 'sizeBytes': len(attributes), 'sha256': sha(attributes), 'source': 'Evidence byte-preservation rule'}]
inventory += [{'path': name, 'sizeBytes': len(data), 'sha256': sha(data), 'source': origins[name]}
              for name, data in sorted(payloads.items())]
add('inventory.json', encoded({'testedCommit': COMMIT, 'files': inventory}), 'Inventory excluding itself')
targets = [guard(DEST / name) for name in sorted(payloads)]
assert all(not target.exists() for target in targets), 'Refusing to replace prior evidence'
plan_sha = sha(encoded([str(target) for target in targets]))
print(json.dumps({'preflight': 'PASS', 'root': str(ROOT), 'targets': [str(t) for t in targets], 'planSha256': plan_sha}))
print(json.dumps({'inspection': 'PASS', 'counts': inspection['counts'], 'governance': governance_counts,
                  'warnings': inspection['diagnostics'], 'archiveFiles': len(payloads) + 1,
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
