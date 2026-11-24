"""Retrieve exact-branch original CI diagnostics without rerunning CI."""
import argparse
import io
import json
from pathlib import Path
import runpy
import sys
import time
import urllib.error
import urllib.request
import zipfile

ROOT = Path(__file__).resolve().parents[2]


class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, *args, **kwargs):
        return None


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--run", type=int, required=True)
    args = parser.parse_args()
    b = runpy.run_path(str(ROOT / "Tools/ota/p34_batch_validation.py"))["runtime"]()
    token = b.credential()
    run = b.api('/repos/' + b.REPO + '/actions/runs/' + str(args.run), token)[1]
    b.require(run['head_branch'] == b.BRANCH and run['path'] == '.github/workflows/flutter-dev-checks.yml',
              'wrong development run')
    artifacts = b.api('/repos/' + b.REPO + '/actions/runs/' + str(args.run) + '/artifacts', token)[1]['artifacts']
    out = b.checked(b.OUT / 'ci' / str(args.run))
    output = []
    for item in artifacts:
        if not item['name'].startswith(('flutter-dev-ubuntu-latest-', 'flutter-dev-windows-2022-')):
            continue
        b.require(not item['expired'] and item['size_in_bytes'] < 20 * 1024 * 1024, 'artifact bound')
        path = b.checked(out / (str(item['id']) + '.zip'))
        if not path.exists():
            url = 'https://api.github.com/repos/' + b.REPO + '/actions/artifacts/' + str(item['id']) + '/zip?fresh=' + str(time.time_ns())
            request = urllib.request.Request(url, headers={'Authorization': 'Bearer ' + token})
            try:
                with urllib.request.build_opener(NoRedirect()).open(request, timeout=30) as response:
                    raw = response.read(20 * 1024 * 1024 + 1)
            except urllib.error.HTTPError as error:
                b.require(error.code == 302, 'artifact API HTTP ' + str(error.code))
                # Do not forward GitHub credentials to the signed storage URL.
                with urllib.request.urlopen(error.headers['Location'], timeout=30) as response:
                    raw = response.read(20 * 1024 * 1024 + 1)
            b.require(len(raw) <= 20 * 1024 * 1024, 'download bound')
            path.parent.mkdir(parents=True, exist_ok=True)
            with path.open('xb') as stream:
                stream.write(raw)
        archive = zipfile.ZipFile(io.BytesIO(path.read_bytes()))
        logs = [info for info in archive.infolist() if info.filename.endswith('/tests.log')]
        b.require(len(logs) == 1 and logs[0].file_size <= 20 * 1024 * 1024, 'test log bound')
        raw = archive.read(logs[0])
        log = b.checked(out / (str(item['id']) + '-tests.log'))
        if log.exists():
            b.require(log.read_bytes() == raw, 'original log changed')
        else:
            with log.open('xb') as stream:
                stream.write(raw)
        lines = raw.decode('utf-8', 'replace').splitlines()
        errors = []
        for index, line in enumerate(lines):
            if '[E]' in line:
                errors.append('\n'.join(lines[index:index + 20]))
        output.append(dict(artifact=item['id'], name=item['name'], errors=errors, log=b.record(log)))
    b.require(len(output) == 2, 'both-host diagnostic artifacts required')
    result = b.checked(out / 'diagnosis.json')
    value = dict(run=args.run, sha=run['head_sha'], conclusion=run['conclusion'], hosts=output)
    if not result.exists():
        b.save(str(result), value)
    print(json.dumps(value))


if __name__ == '__main__':
    if not (Path.cwd() == ROOT and sys.flags.isolated and sys.flags.no_site and sys.dont_write_bytecode):
        raise RuntimeError('isolated explicit root required')
    main()
