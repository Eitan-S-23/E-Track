"""Read the existing ZIP packet without extracting or executing archived scripts."""
import fnmatch
import hashlib
import io
import json
from pathlib import Path, PurePosixPath
import re
import zipfile


def sha(data):
    return hashlib.sha256(data).hexdigest()


def relative(value):
    value = str(value).replace('\\', '/')
    p = PurePosixPath(value)
    if not value or p.is_absolute() or '..' in p.parts or ':' in value:
        raise ValueError('nonportable original reference')
    return p.as_posix()


class Store:
    def __init__(self, payload, root):
        self.root = root
        self.zip = zipfile.ZipFile(io.BytesIO(payload))
        names = self.zip.namelist()
        if len(names) != len(set(names)):
            raise ValueError('duplicate archive member')
        index = json.loads(self.zip.read('index.json'))
        if index['schema'] != 'p35-local-evidence-packet-v1':
            raise ValueError('wrong original packet')
        self.files = {}
        for name, row in index['files'].items():
            key = relative(name)
            if key in self.files and self.files[key] != row:
                raise ValueError('conflicting original aliases')
            if not re.fullmatch('[0-9a-f]{64}', row['sha256']) or type(row['bytes']) is not int or row['bytes'] < 0:
                raise ValueError('invalid original fingerprint')
            self.files[key] = row
        self.objects = {v['sha256'] for v in self.files.values()}
        if set(names) != {'index.json'} | {'objects/' + d for d in self.objects}:
            raise ValueError('unindexed or missing original object')
        self.reads = set()

    def key(self, value):
        value = str(value).replace('\\', '/')
        prefix = self.root.as_posix().rstrip('/') + '/'
        if value.startswith(prefix):
            value = value[len(prefix):]
        return relative(value)

    def read(self, value):
        key = self.key(value)
        row = self.files[key]
        data = self.zip.read('objects/' + row['sha256'])
        if len(data) != row['bytes'] or sha(data) != row['sha256']:
            raise ValueError('original bytes changed: ' + key)
        self.reads.add(key)
        return data

    def verify(self):
        seen = set()
        for name, row in self.files.items():
            if row['sha256'] not in seen:
                self.read(name)
                seen.add(row['sha256'])
            if self.zip.getinfo('objects/' + row['sha256']).file_size != row['bytes']:
                raise ValueError('inconsistent alias size')
        return dict(files=len(self.files), objects=len(seen), exactBytes=True)

    def exists(self, value):
        key = self.key(value)
        return key in self.files or any(n.startswith(key + '/') for n in self.files)

    def glob(self, folder, pattern, recursive=False):
        prefix = self.key(folder).rstrip('/') + '/'
        return sorted(self.root / n for n in self.files if n.startswith(prefix)
                      and (recursive or '/' not in n[len(prefix):])
                      and fnmatch.fnmatchcase(n.rsplit('/', 1)[-1], pattern))

    def children(self, folder):
        prefix = self.key(folder).rstrip('/') + '/'
        return sorted({self.root / (prefix + n[len(prefix):].split('/')[0])
                       for n in self.files if n.startswith(prefix)})


def load(source, root, guard):
    manifest = json.loads(source.read_bytes())
    chunks = []
    for row in manifest['parts']:
        p = guard(root, source.parent / relative(row['path']))
        data = p.read_bytes()
        if len(data) != row['bytes'] or sha(data) != row['sha256']:
            raise ValueError('packet part fingerprint mismatch')
        chunks.append(data)
    payload = b''.join(chunks)
    if len(payload) != manifest['bytes'] or sha(payload) != manifest['sha256']:
        raise ValueError('whole packet fingerprint mismatch')
    return Store(payload, root)
