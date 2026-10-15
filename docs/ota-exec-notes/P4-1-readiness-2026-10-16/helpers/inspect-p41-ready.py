"""Read original P4-1 Actions ZIPs without extracting or running their contents."""
import hashlib
import json
import re
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
assert Path.cwd().resolve() == ROOT


def decode(data):
    return re.sub(r'\x1b\[[0-9;]*[A-Za-z]', '', data.decode('utf-8-sig'))


def show(value):
    print(json.dumps(value, ensure_ascii=True))


for label in ['fw', 'cf', 'gov', 'app']:
    with zipfile.ZipFile(ROOT / f'.cache/github/p41-ready-{label}-logs.zip') as archive:
        for name in archive.namelist():
            if '/' not in name:
                content = decode(archive.read(name))
                show({'run': label, 'member': name,
                      'vitest': re.findall(r'\bTests\s+(\d+) passed', content),
                      'node': re.findall(r'\u2139 tests (\d+)', content),
                      'python': re.findall(r'Ran (\d+) tests', content)})
            if label == 'fw' and any(piece in name for piece in [
                    '/11_Build firmware.txt', '/19_Exercise the shared key-bound',
                    '/20_Check development key cleanup', '/15_Report firmware artifacts',
                    '/15_Execute production byte', '/17_Exercise production preparation']):
                content = decode(archive.read(name))
                show({'member': name, 'warnings': len(re.findall(r'warning:', content)),
                      'errors': len(re.findall(r'error:', content)), 'tail': content.splitlines()[-14:]})

for listing_name in ['fw', 'gov']:
    listing = json.loads((ROOT / f'.cache/github/p41-ready-{listing_name}-artifacts.json').read_bytes())
    for item in listing['artifacts']:
        path = ROOT / f'.cache/github/p41-ready-artifact-{item["id"]}.zip'
        if not path.exists():
            show({'artifact': item['id'], 'downloaded': False})
            continue
        data = path.read_bytes()
        assert len(data) == item['size_in_bytes']
        assert 'sha256:' + hashlib.sha256(data).hexdigest() == item['digest']
        with zipfile.ZipFile(path) as archive:
            members = archive.namelist()
            show({'artifact': item['id'], 'verified': True, 'members': members})
            for name in members:
                if name.endswith(('gcc-build-inputs.json', 'keyed-build-evidence.json', 'DEVELOPMENT-ONLY.json')):
                    show({'artifact': item['id'], 'member': name, 'content': json.loads(archive.read(name))})
