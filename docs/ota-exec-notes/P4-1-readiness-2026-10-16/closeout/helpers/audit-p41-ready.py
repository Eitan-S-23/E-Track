"""Read-only path, original-byte, credential-leak and process receipt audit."""
import argparse
import csv
import hashlib
import io
import json
import re
import stat
import subprocess
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
assert Path.cwd().resolve() == ROOT
assert str(ROOT).replace('\\', '/').lower() == 'd:/github/my/e-track/.cache/p41-dev-20261015'


def guard(value):
    value = ROOT / value
    actual = value.resolve(strict=False)
    actual.relative_to(ROOT)
    for parent in (value, *value.parents):
        if parent.exists() and getattr(parent.lstat(), 'st_file_attributes', 0) & stat.FILE_ATTRIBUTE_REPARSE_POINT:
            raise RuntimeError('Reparse point: ' + str(parent))
    return actual


def sha(data):
    return hashlib.sha256(data).hexdigest()


parser = argparse.ArgumentParser()
parser.add_argument('selection')
parser.add_argument('--current-label', required=True)
args = parser.parse_args()
selection_path = guard(args.selection)
selection_bytes = selection_path.read_bytes()
selection = json.loads(selection_bytes)
assert Path(selection['root']).resolve() == ROOT
seen, missing = set(), set()


def walk(value):
    target = guard(value)
    if target in seen:
        return
    if not target.exists():
        missing.add(str(target))
        return
    seen.add(target)
    if target.is_dir():
        for child in target.iterdir():
            walk(child)


for value in selection['files'] + selection['dirs']:
    walk(value)
assert not [value for value in seen if value.name.lower() == 'private-key.h']
for value in selection.get('deleted', []):
    assert not guard(value).exists()

archive = guard('docs/ota-exec-notes/P4-1-readiness-2026-10-16')
inventory_bytes = (archive / 'inventory.json').read_bytes()
assert sha(inventory_bytes) == '61c2710ad57e32bce8445de6bccbf36113f32e61616a6245c55dae176e2a7068'
inventory = json.loads(inventory_bytes)
assert len(inventory['files']) == 97
for item in inventory['files']:
    data = guard(archive / item['path']).read_bytes()
    assert len(data) == item['sizeBytes'] and sha(data) == item['sha256']

private = [guard('.cache/cf-auth-input/token.txt').read_text(encoding='utf-8').strip()]
private_config = json.loads(guard('.cache/cf-auth-input/firmware-test-secrets.json').read_bytes())
private += [private_config[key] for key in ['TRACE_DEPLOY_TOKEN', 'DOWNLOAD_HMAC_KEY_CURRENT']]
private = [value.encode() for value in private if isinstance(value, str) and len(value) > 20]
assert len(private) == 3
pattern = re.compile(rb'\b(?:gh[pousr]_[A-Za-z0-9]{20,}|github_pat_[A-Za-z0-9_]{30,})\b')
scanned_files, scanned_members = 0, 0


def secret_check(data):
    assert not pattern.search(data), 'GitHub credential pattern in selected evidence'
    assert all(value not in data for value in private), 'Private credential value in selected evidence'


for target in sorted(archive.rglob('*')):
    target = guard(target)
    if not target.is_file():
        continue
    data = target.read_bytes()
    secret_check(data)
    scanned_files += 1
    if target.suffix == '.zip':
        with zipfile.ZipFile(io.BytesIO(data)) as stream:
            for member in stream.infolist():
                assert Path(member.filename).name.lower() != 'private-key.h'
                secret_check(stream.read(member))
                scanned_members += 1

commands, planned_only = [], []
for label in dict.fromkeys(selection['logs']):
    if label == args.current_label:
        continue
    receipt = guard('.cache/logs/' + label + '.json')
    if not receipt.exists():
        planned_only.append(label)
        continue
    record = json.loads(receipt.read_bytes())
    assert record['closed'] and record.get('ended')
    for value in record['outputs'].values():
        guard(value)
    commands.append({'label': label, 'pid': record.get('pid'), 'exitCode': record['exitCode'], 'closed': record['closed']})
query = subprocess.run(['wmic', 'process', 'get', 'Name,ProcessId', '/format:csv'], cwd=ROOT,
                       capture_output=True, encoding='utf-8', errors='replace', timeout=20, check=True)
pids = {str(record['pid']) for record in commands}
matching = [row for row in csv.DictReader(io.StringIO(query.stdout.strip()))
            if row.get('ProcessId') in pids and row.get('Name') in ['node.exe', 'python.exe', 'git.exe']]
assert not matching, 'A receipt PID is present; inspect creation time before attributing or stopping it'
shared_index = Path('D:/github/my/E-Track/.git/index').read_bytes()
assert sha(shared_index) == '2907ee569cb8415877c8c688b3e09b5948a789d6430796eab99ae3ad43f3a3dd'
print(json.dumps({'ok': True, 'selectionFile': str(selection_path), 'selectionSha256': sha(selection_bytes),
                  'resolvedEntryCount': len(seen), 'missingSelectedPaths': sorted(missing),
                  'verifiedInventoryEntries': len(inventory['files']), 'scannedArchiveFiles': scanned_files,
                  'scannedZipMembers': scanned_members, 'privateCredentialMatches': 0,
                  'privateHeaderFiles': 0, 'closedCommands': commands, 'plannedOnlyNotRun': planned_only,
                  'matchingReceiptPids': matching, 'sharedRootIndexSha256': sha(shared_index),
                  'currentAuditReceipt': 'Outer runner writes this receipt after this check exits',
                  'externalWrites': selection['externalWrites'], 'authorizedGitMetadata': selection['gitMetadata'],
                  'historicalExternalCacheIncident': 'P41-AUDIT-01 remains ATTRIBUTION_UNRESOLVED; no cleanup performed'}))
