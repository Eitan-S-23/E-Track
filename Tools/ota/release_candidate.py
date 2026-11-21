"""Version-only main push and unpublished candidate delivery; never a device test."""
import argparse
import base64
import datetime
import hashlib
import json
import os
from pathlib import Path
import re
import runpy
import shutil
import subprocess
import sys
import time
from urllib.request import getproxies
import uuid

ROOT = Path(__file__).resolve().parents[2]
IO = runpy.run_path(str(ROOT / '.agents/skills/e-track-flutter-debug/scripts/host_io.py'))
checked = IO['checked_output']
FIRMWARE = 'Tools/ota/original-admin-release.json'
APP = 'app/bluetooth_flutter_Trace/pubspec.yaml'
REPO = 'Eitan-S-23/E-Track'
WORKFLOW = '.github/workflows/original-admin-candidate.yml'


def require(value, message):
    if not value:
        raise RuntimeError(message)


def next_version(version, mcu=False):
    require(re.fullmatch(r'(0|[1-9]\d*)\.(0|[1-9]\d*)\.(0|[1-9]\d*)', version), 'Invalid version')
    major, minor, patch = map(int, version.split('.'))
    if mcu:
        require(minor < 100 and patch < 100, 'Invalid MCU version encoding')
        code = major * 10000 + minor * 100 + patch + 1
        require(code <= 0xffffffff, 'MCU version overflow')
        return f'{code // 10000}.{code // 100 % 100}.{code % 100}'
    return f'{major}.{minor}.{patch + 1}'


def version_edit(component, raw, notes=None):
    text = raw.decode('utf-8')
    if component == 'mcu':
        value = json.loads(text)
        require(value.get('schema') == 'original-admin-automatic-candidates-v1', 'Unknown firmware configuration')
        old = value['firmware']['versionName']
        new = next_version(old, mcu=True)
        note = notes or (f'Version-only {old} to {new} candidate for owner-controlled OTA testing. '
            'Product functionality unchanged. Full/recovery candidate only; no automatic channel '
            'publication, delta generation or device operation. App version unchanged.')
        require(0 < len(note.strip()) <= 8000, 'Invalid release notes')
        value['firmware'].update(versionName=new, releaseNotes=note)
        ending = '\r\n' if '\r\n' in text else '\n'
        data = (json.dumps(value, ensure_ascii=True, indent=2) + '\n').replace('\n', ending).encode('utf-8')
        code = sum(int(p) * n for p, n in zip(new.split('.'), (10000, 100, 1)))
        return dict(file=FIRMWARE, beforeVersion=old, version=new, code=code), data
    require(component == 'app' and notes is None, 'App only changes pubspec version name/code')
    matches = list(re.finditer(r'(?m)^version:[ \t]*(\d+\.\d+\.\d+)\+([1-9]\d*)[ \t]*(?=\r?$)', text))
    require(len(matches) == 1, 'Expected one App version name+code')
    match = matches[0]
    old, previous = match.group(1), int(match.group(2))
    new, code = next_version(old), previous + 1
    require(102 <= previous and code <= 2100000000, 'App versionCode overflow or unsupported baseline')
    data = (text[:match.start(1)] + new + '+' + str(code) + text[match.end(2):]).encode('utf-8')
    return dict(file=APP, beforeVersion=old, beforeCode=previous, version=new, code=code), data


def check_reservations(component, version, releases, refs):
    tag = 'mcu-e-track-at32f435-v' + version if component == 'mcu' else 'v' + version
    require(not any(r.get('tag_name') == tag for r in releases), 'Version reserved by Release/draft: ' + tag)
    require(not any(r.get('ref') == 'refs/tags/' + tag for r in refs), 'Version reserved by tag: ' + tag)


def matching_run(runs, source):
    matches = [r for r in runs if r.get('head_sha') == source and r.get('event') == 'push'
               and r.get('path') == WORKFLOW and r.get('head_branch') == 'main']
    require(len(matches) <= 1, 'Ambiguous candidate runs; do not dispatch or retry')
    if matches:
        require(matches[0].get('run_attempt') == 1, 'Unexpected candidate rerun')
    return matches[0] if matches else None


def firmware_receipt(log, source, run_id, version):
    rows = [json.loads(line.split('ORIGINAL_ADMIN_RECEIPT ', 1)[1]) for line in log.splitlines()
            if 'ORIGINAL_ADMIN_RECEIPT {' in line]
    receipts = {r['name']: r['value'] for r in rows}
    ready, result = receipts.get('ready-metadata.json', {}), receipts.get('register-receipt.json', {})
    require(ready.get('commitSha') == source and str(ready.get('runId')) == str(run_id)
            and ready.get('versionName') == version, 'Missing/mismatched source-bound candidate metadata')
    registration = result.get('registration', {})
    require(result.get('ok') is True and result.get('channelPublished') is False
            and result.get('productionApproved') is False and registration.get('state') == 'ready'
            and registration.get('assetsRegistered') == 2, 'Candidate registration not ready/unpublished')
    assets = ready.get('assets', [])
    require(len(assets) == 2 and {a['kind'] for a in assets} == {'full', 'recovery'}
            and all(a.get('r2Verified') is True for a in assets), 'Missing verified full/recovery assets')
    return dict(registration=result, metadata=ready,
                warnings=len(re.findall(r'\bwarning:', log, re.I)), errors=len(re.findall(r'\berror:', log, re.I)))


class Host:
    def __init__(self, root, out):
        self.root, self.out = root, out
        self.sequence, self.token = 0, ''
        env = dict(os.environ)
        for key in list(env):
            if key.startswith(('GIT_', 'GH_', 'GITHUB_')) or key in (
                    'NODE_OPTIONS', 'NODE_COMPILE_CACHE', 'SSLKEYLOGFILE', 'NODE_REDIRECT_WARNINGS'):
                env.pop(key, None)
        for key in ('HOME', 'USERPROFILE', 'APPDATA', 'LOCALAPPDATA', 'TEMP', 'TMP', 'TMPDIR',
                    'XDG_CACHE_HOME', 'XDG_CONFIG_HOME', 'XDG_DATA_HOME', 'GH_CONFIG_DIR'):
            env[key] = str(checked(root, out / 'host'))
        env.update(GIT_CONFIG_GLOBAL='NUL' if os.name == 'nt' else '/dev/null', GIT_CONFIG_NOSYSTEM='1',
                   GIT_TERMINAL_PROMPT='0', GCM_INTERACTIVE='never', GH_PROMPT_DISABLED='1',
                   GH_HOST='github.com', GH_PAGER='', GH_NO_UPDATE_NOTIFIER='1',
                   GH_NO_EXTENSION_UPDATE_NOTIFIER='1', PYTHONDONTWRITEBYTECODE='1')
        # gh does not read Windows Internet Settings; reuse that existing proxy in memory.
        proxies = getproxies()
        for scheme in ('http', 'https'):
            if not (env.get(scheme + '_proxy') or env.get(scheme.upper() + '_PROXY')) and proxies.get(scheme):
                env[scheme.upper() + '_PROXY'] = proxies[scheme]
        self.env = env
        checked(root, out / 'host').mkdir(parents=True)
        self.gh = shutil.which('gh')
        require(self.gh and shutil.which('git'), 'Existing Git and GitHub CLI are required; no auto install/login')

    def authenticate(self):
        # Only the existing GitHub credential is read; nothing is logged or persisted.
        self.token = os.environ.get('GH_TOKEN') or os.environ.get('GITHUB_TOKEN') or ''
        if not self.token:
            auth_env = dict(os.environ, GH_NO_UPDATE_NOTIFIER='1', GH_NO_EXTENSION_UPDATE_NOTIFIER='1',
                            GH_PROMPT_DISABLED='1')
            for key in ('TEMP', 'TMP', 'TMPDIR', 'XDG_CACHE_HOME'):
                auth_env[key] = self.env[key]
            result = subprocess.run([self.gh, 'auth', 'token', '--hostname', 'github.com'], cwd=self.root,
                env=auth_env, capture_output=True, timeout=30, creationflags=0x08000000 if os.name == 'nt' else 0)
            require(result.returncode == 0, 'Existing gh credential unavailable; no login or new token attempted')
            self.token = result.stdout.decode('utf-8').strip()
        require(bool(self.token) and not re.search(r'\s', self.token), 'Invalid existing credential')
        self.env['GH_TOKEN'] = self.token
        self.basic = base64.b64encode(('x-access-token:' + self.token).encode()).decode()
        self.env.update(GIT_CONFIG_COUNT='1', GIT_CONFIG_KEY_0='http.https://github.com/.extraheader',
                        GIT_CONFIG_VALUE_0='AUTHORIZATION: basic ' + self.basic)

    def clean(self, value):
        for secret in (self.token, getattr(self, 'basic', '')):
            if secret:
                value = value.replace(secret, '[REDACTED]')
        return re.sub(r'(?:gh[opusr]_|github_pat_)[A-Za-z0-9_]+', '[REDACTED]', value)

    def run(self, argv, timeout=120):
        self.sequence += 1
        result = subprocess.run(list(map(str, argv)), cwd=self.root, env=self.env, capture_output=True,
            timeout=timeout, creationflags=0x08000000 if os.name == 'nt' else 0)
        stdout, stderr = result.stdout.decode('utf-8', 'replace'), result.stderr.decode('utf-8', 'replace')
        checked(self.root, self.out / f'command-{self.sequence:03d}.log').write_text(
            self.clean(stdout + stderr), encoding='utf-8')
        require(result.returncode == 0, f'Command {self.sequence} failed; inspect contained log, do not repeat release')
        return stdout.strip()

    def git(self, *args):
        return self.run(['git', '-c', 'safe.directory=' + self.root.as_posix(), '-c', 'core.fsmonitor=false',
            '-c', 'core.autocrlf=true',
            '-c', 'core.hooksPath=' + str(checked(self.root, self.out / 'empty-hooks')), '-c', 'gc.auto=0',
            '-c', 'maintenance.auto=false', '-c', 'commit.gpgsign=false', '-c', 'credential.helper=',
            '-c', 'core.askPass=', '-c', 'http.sslBackend=openssl', '--no-optional-locks', *args])

    def api(self, route):
        require(route == 'user' or route.startswith(('repos/' + REPO + '/', 'repos/Eitan-S-23/Trace/')),
                'Only existing GitHub repository reads are allowed')
        return json.loads(self.run([self.gh, 'api', '--hostname', 'github.com', '--method', 'GET', route]))

    def releases(self, repo):
        rows = []
        for page in range(1, 101):
            part = self.api(f'repos/{repo}/releases?per_page=100&page={page}')
            require(isinstance(part, list), 'Invalid Release list')
            rows.extend(part)
            if len(part) < 100:
                return rows
        raise RuntimeError('Release pagination incomplete; no version reservation decision')


def repository_ready(host):
    require(Path(host.git('rev-parse', '--show-toplevel')).resolve() == host.root, 'Wrong project root')
    require(Path(host.git('rev-parse', '--path-format=absolute', '--git-common-dir')).resolve() == host.root / '.git',
            'Use the primary main checkout, not another worktree')
    require(host.git('branch', '--show-current') == 'main', 'Use main')
    require(host.git('remote', 'get-url', 'origin') == 'https://github.com/' + REPO + '.git', 'Unexpected origin')
    require(not host.git('status', '--porcelain=v1', '--untracked-files=no'), 'Tracked/index changes exist; nothing staged')
    local = host.git('rev-parse', 'HEAD')
    require(host.api('repos/' + REPO + '/git/ref/heads/main')['object']['sha'] == local,
            'Local main differs from remote; no automatic merge/reset/push')
    return local


def wait_for_delivery(host, state, save, minutes):
    source, component = state['source'], state['component']
    deadline = time.monotonic() + minutes * 60
    while time.monotonic() < deadline:
        route = f'repos/{REPO}/actions/workflows/original-admin-candidate.yml/runs?branch=main&event=push&head_sha={source}&per_page=100'
        run = matching_run(host.api(route)['workflow_runs'], source)
        if run:
            state.update(run=run['id'], url=run['html_url'])
            save('CI_RUNNING' if run['status'] != 'completed' else 'CI_COMPLETED')
            print(f"CI {run['id']}: {run['status']} {run.get('conclusion') or ''}", flush=True)
            if run['status'] == 'completed':
                require(run['conclusion'] == 'success', 'Formal CI failed; preserve reserved version and inspect original run')
                jobs = host.api(f"repos/{REPO}/actions/runs/{run['id']}/jobs?per_page=100")['jobs']
                selected = 'firmware' if component == 'mcu' else 'app'
                other = 'app' if component == 'mcu' else 'firmware'
                require(next(j for j in jobs if j['name'] == selected)['conclusion'] == 'success'
                        and next(j for j in jobs if j['name'] == other)['conclusion'] == 'skipped',
                        'Unexpected component selection')
                job = next(j for j in jobs if j['name'] == selected)
                log = host.run([host.gh, 'run', 'view', str(run['id']), '--repo', REPO,
                                '--job', str(job['id']), '--log'], timeout=180)
                if component == 'mcu':
                    state['receipt'] = firmware_receipt(log, source, run['id'], state['version'])
                else:
                    rows = []
                    for line in log.splitlines():
                        start = line.find('{"source":')
                        if start >= 0:
                            try:
                                rows.append(json.loads(line[start:]))
                            except json.JSONDecodeError:
                                pass
                    receipt = next((r for r in rows if r.get('source') == source and r.get('completed') is True
                                    and r.get('channelPublished') is False), None)
                    require(receipt is not None, 'Missing completed original-signer delivery receipt')
                    state['receipt'] = receipt
                save('DELIVERED')
                print(f"READY {component} {state['version']} (unpublished): {run['html_url']}", flush=True)
                return
        else:
            print('Waiting for the exact main-push candidate run...', flush=True)
        time.sleep(min(30, max(0, deadline - time.monotonic())))
    raise RuntimeError('Observation deadline reached; use --resume, never repeat the version bump')


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('component', nargs='?', choices=('mcu', 'app'))
    parser.add_argument('--dry-run', action='store_true', help='Check next version without editing, committing or pushing')
    parser.add_argument('--resume', type=Path, help='Only observe an existing source-bound result.json')
    parser.add_argument('--notes', help='MCU release notes; App keeps all content except its version line')
    parser.add_argument('--timeout-minutes', type=int, default=120)
    args = parser.parse_args(argv)
    if not args.component and not args.resume:
        parser.print_help()
        return 0
    require(not args.resume or not (args.component or args.dry_run or args.notes), 'Resume is read-only and takes no component')
    require(1 <= args.timeout_minutes <= 180, 'Invalid finite observation timeout')
    require(Path.cwd() == ROOT and sys.dont_write_bytecode, 'Run from project root with python -B or the batch launcher')
    for name in (FIRMWARE, APP, '.git', '.git/index', '.git/index.lock', '.git/COMMIT_EDITMSG',
                 '.git/refs/heads/main', '.git/refs/remotes/origin/main', '.git/logs/HEAD',
                 '.git/logs/refs/heads/main', '.git/logs/refs/remotes/origin/main', '.cache/candidate-release'):
        checked(ROOT, name)
    objects = checked(ROOT, '.git/objects')
    for directory, children, _ in os.walk(objects):
        checked(ROOT, directory)
        for child in children:
            checked(ROOT, Path(directory) / child)
    base = checked(ROOT, '.cache/candidate-release')
    stamp = datetime.datetime.now(datetime.timezone.utc).strftime('%Y%m%dT%H%M%SZ') + '-' + uuid.uuid4().hex[:8]
    out = checked(ROOT, base / stamp)
    out.mkdir(parents=True)
    state = dict(component=args.component, phase='PREFLIGHT', createdAt=stamp, deviceOperations=0, manualBackendOperations=0)
    def save(phase):
        state['phase'] = phase
        IO['write_json'](ROOT, out / 'result.json', state, replace=(out / 'result.json').exists())
    lock = checked(ROOT, base / 'active.lock')
    owned = False
    host = None
    try:
        host = Host(ROOT, out)
        host.authenticate()
        if args.resume:
            prior = checked(ROOT, args.resume)
            require(prior.parent.parent == base and prior.name == 'result.json', 'Expected a contained prior result.json')
            state.update(json.loads(prior.read_text(encoding='utf-8')))
            require(re.fullmatch(r'[0-9a-f]{40}', state.get('source', '')), 'No committed source to observe; inspect local Git state')
            save('RESUMING')
            wait_for_delivery(host, state, save, args.timeout_minutes)
            return 0
        if not args.dry_run:
            with lock.open('x', encoding='ascii') as stream:
                stream.write(str(out))
            owned = True
            for receipt in base.glob('*/result.json'):
                previous = json.loads(checked(ROOT, receipt).read_text(encoding='utf-8'))
                source = previous.get('source')
                if source and previous.get('phase') != 'DELIVERED':
                    require(any(json.loads(p.read_text(encoding='utf-8')).get('source') == source
                                and json.loads(p.read_text(encoding='utf-8')).get('phase') == 'DELIVERED'
                                for p in base.glob('*/result.json')), 'Unresolved prior source; use --resume ' + str(receipt))
        before = repository_ready(host)
        file = checked(ROOT, FIRMWARE if args.component == 'mcu' else APP)
        raw = file.read_bytes()
        edit, data = version_edit(args.component, raw, args.notes)
        state.update(edit, before=before)
        repo = REPO if args.component == 'mcu' else 'Eitan-S-23/Trace'
        releases = host.releases(repo)
        refs = host.api(f'repos/{repo}/git/matching-refs/tags/')
        check_reservations(args.component, edit['version'], releases, refs)
        save('DRY_RUN' if args.dry_run else 'PREPARED')
        print(f"{args.component}: {edit['beforeVersion']} -> {edit['version']} ({edit['code']})", flush=True)
        if args.dry_run:
            return 0
        require(repository_ready(host) == before and file.read_bytes() == raw, 'Source changed during preflight')
        checked(ROOT, out / 'before-version.bin').write_bytes(raw)
        checked(ROOT, file).write_bytes(data)
        save('EDITED')
        require(host.git('diff', '--name-only') == edit['file'], 'Unexpected changed files; nothing committed')
        require(host.git('rev-parse', 'HEAD') == before and not host.git('diff', '--cached', '--name-only'), 'Concurrent Git change')
        host.git('diff', '--check')
        host.git('add', '--', edit['file'])
        require(host.git('diff', '--cached', '--name-only') == edit['file'], 'Unexpected index scope; not committed')
        actor = host.api('user')
        expected = data.decode('utf-8').replace('\r\n', '\n').strip()
        require(host.git('rev-parse', 'HEAD') == before and
                host.git('show', ':' + edit['file']).replace('\r\n', '\n') == expected,
                'Source/index changed before commit')
        host.git('diff', '--cached', '--check')
        host.git('-c', 'user.name=' + actor['login'], '-c', f"user.email={actor['id']}+{actor['login']}@users.noreply.github.com",
                 'commit', '-m', f"release: {args.component} {edit['version']} version-only OTA candidate")
        source = host.git('rev-parse', 'HEAD')
        state.update(source=source, versionFileSha256=hashlib.sha256(data).hexdigest())
        save('COMMITTED')
        require(host.git('show', '--format=', '--name-only', source) == edit['file'], 'Commit scope mismatch')
        require(host.git('rev-parse', source + '^') == before and
                host.git('show', source + ':' + edit['file']).replace('\r\n', '\n') == expected,
                'Committed bytes/parent changed; no push')
        require(host.api('repos/' + REPO + '/git/ref/heads/main')['object']['sha'] == before, 'Remote moved; no automatic push')
        save('PUSH_STARTED')
        host.git('push', 'origin', source + ':refs/heads/main')
        require(host.api('repos/' + REPO + '/git/ref/heads/main')['object']['sha'] == source, 'Push result unresolved; use --resume')
        save('PUSHED')
        print('PUSHED ' + source + '; waiting for formal CI and candidate receipt', flush=True)
        wait_for_delivery(host, state, save, args.timeout_minutes)
        return 0
    except (Exception, KeyboardInterrupt) as error:
        state['error'] = host.clean(str(error)) if host else type(error).__name__
        save(state['phase'])
        print('STOP: ' + state['error'], file=sys.stderr, flush=True)
        return 1
    finally:
        if owned:
            require(lock.read_text(encoding='ascii') == str(out), 'Release ownership changed; preserve lock')
            lock.unlink()
        print('Receipt: ' + str(out / 'result.json'), flush=True)


if __name__ == '__main__':
    raise SystemExit(main())
