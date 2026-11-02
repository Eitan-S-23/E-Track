"""Invoke the existing protected rehearsal workflow; never implement a publisher."""
import hashlib
import io
import json
import os
from pathlib import PurePosixPath
import re
import time
from urllib.parse import quote
import zipfile

from runner import require, strict_json

REPOSITORY = 'Eitan-S-23/E-Track'
WORKFLOW = 'firmware-build.yml'
ENVIRONMENT = 'firmware-rehearsal'
VARIABLES = {'OTA_PREVIOUS_RELEASE_JSON', 'OTA_APPROVED_BOOTSTRAP_BASELINE_SHA256'}


def sha(raw):
    return hashlib.sha256(raw).hexdigest()


class Build:
    def __init__(self, config, out, host, env, marker):
        self.c, self.out, self.h, self.env, self.marker = config, out, host, env, marker
        self.number, self.run_id, self.terminal = 0, None, False
        self.dispatch_attempted = False
        self.changed = []

    def api(self, route, body=None, method=None, binary=False):
        self.number += 1
        argv = ['gh', 'api', '--hostname', 'github.com', 'repos/' + REPOSITORY + route,
                '--method', method or ('POST' if body is not None else 'GET')]
        if body is not None:
            argv += ['--input', '-']
        raw = self.h.command(self.out, 'gh-%04d' % self.number, argv, self.env,
            seconds=180 if binary else 40, stdin=None if body is None else json.dumps(body).encode())
        return raw if binary else strict_json(raw) if raw.strip() else None

    def variable(self, name):
        return self.api('/environments/' + ENVIRONMENT + '/variables/' + name)['value']

    def set_variable(self, name, value):
        self.api('/environments/' + ENVIRONMENT + '/variables/' + name,
                 dict(name=name, value=value), method='PATCH')
        require(self.variable(name) == value, 'rehearsal variable readback mismatch')

    def preflight(self):
        require(os.environ.get('GH_TOKEN'), 'GH_TOKEN required; no implicit host credential discovery')
        commit = self.api('/commits/' + quote(self.c['ref'], safe=''))
        require(commit['sha'] == self.c['sha'], 'source ref moved')
        workflow = self.api('/contents/.github/workflows/' + WORKFLOW + '?ref=' + self.c['sha'])
        require(workflow['sha'] == self.c['workflow_blob'], 'unreviewed workflow revision')
        variables = self.api('/environments/' + ENVIRONMENT + '/variables?per_page=100')
        require(variables['total_count'] <= 100, 'environment variable inventory truncated')
        current = {x['name']: x['value'] for x in variables['variables']}
        gate = current.get('OTA_BOOT_CHAIN_READY')
        if gate is None:
            gate = self.api('/actions/variables/OTA_BOOT_CHAIN_READY')['value']
        require(gate == 'false', 'boot-chain gate must stay locked')
        require(current.get('FIRMWARE_REHEARSAL_TRACE_R2_BUCKET') == 'e-track-firmware-p41-test-releases',
                'unexpected test bucket')
        self.before_runs = self.runs()
        for status in ('queued', 'in_progress', 'waiting', 'pending', 'requested'):
            active = self.api('/actions/workflows/' + WORKFLOW + '/runs?status=' + status + '&per_page=1')
            require(active['total_count'] == 0, 'another firmware workflow is active')
        desired = dict(current)
        for name, change in self.c['variables'].items():
            require(current.get(name) == change['before'], 'rehearsal variable changed before start')
            desired[name] = change['during']
        base = strict_json(desired['OTA_PREVIOUS_RELEASE_JSON'].encode())
        if base.get('provenanceKind') == 'inaugural-bootstrap-v1':
            require(base['targetCommitSha'] == self.c['sha'] and base['targetVersionName'] == self.c['version'],
                    'bootstrap descriptor must already be approved for the requested source/version')
            encoded = json.dumps(base, sort_keys=True, separators=(',', ':'), ensure_ascii=False).encode()
            require(sha(encoded) == desired['OTA_APPROVED_BOOTSTRAP_BASELINE_SHA256'],
                    'approved bootstrap descriptor hash mismatch')
        self.h.save(self.out / 'variables-before.json', {k: current[k] for k in VARIABLES})

    def runs(self):
        value = self.api('/actions/workflows/' + WORKFLOW + '/runs?per_page=100')
        require(len(value['workflow_runs']) <= 100, 'invalid workflow inventory')
        return value['workflow_runs']

    def start(self):
        require(self.api('/commits/' + quote(self.c['ref'], safe=''))['sha'] == self.c['sha'],
                'source ref moved before dispatch')
        for name, change in self.c['variables'].items():
            require(self.variable(name) == change['before'], 'rehearsal variable ownership changed')
            self.changed.append(name)  # Record before request: a lost reply is not a failed mutation.
            self.h.save(self.out / ('variable-' + name + '-intent.json'), change)
            self.set_variable(name, change['during'])
        self.h.save(self.out / 'dispatch-intent.json', dict(source=self.c['sha'],
            beforeIds=[x['id'] for x in self.before_runs], marker=self.marker))
        self.dispatch_attempted = True
        # Exactly one request. Any uncertain outcome retains the pipeline lock.
        self.api('/actions/workflows/' + WORKFLOW + '/dispatches', dict(ref=self.c['ref'], inputs={
            'version_name': self.c['version'], 'firmware_build_profile': 'p34-v2-candidate',
            'rehearsal': 'true', 'publish': 'false', 'check_bindings': 'false',
            'approved_rehearsal_run_id': '', 'release_notes': self.marker}))
        return self.wait()

    def wait(self):
        deadline = time.monotonic() + self.c['seconds']
        prior = {x['id'] for x in self.before_runs}
        while time.monotonic() < deadline:
            if self.run_id is None:
                new = [x for x in self.runs() if x['id'] not in prior and
                       x['head_sha'] == self.c['sha'] and x['event'] == 'workflow_dispatch' and
                       x['head_branch'] == self.c['ref']]
                require(len(new) <= 1, 'ambiguous dispatch; no redispatch')
                if new:
                    self.run_id = new[0]['id']
                    self.h.save(self.out / 'run-bound.json', dict(id=self.run_id, sha=self.c['sha']))
            if self.run_id is not None:
                run = self.api('/actions/runs/' + str(self.run_id))
                require(run['head_sha'] == self.c['sha'] and run['run_attempt'] == 1 and
                        run['event'] == 'workflow_dispatch' and run['head_branch'] == self.c['ref'] and
                        run['path'] == '.github/workflows/' + WORKFLOW, 'CI run identity changed')
                if run['status'] == 'completed':
                    self.terminal = True
                    self.h.save(self.out / 'run-completed.json', run)
                    require(run['conclusion'] == 'success', 'CI build/upload/registration failed')
                    return self.archive()
            time.sleep(min(10, max(0, deadline - time.monotonic())))
        require(False, 'CI still pending/unknown; approve protected environment normally, never redispatch')

    def archive(self):
        inventory = self.api('/actions/runs/' + str(self.run_id) + '/artifacts?per_page=100')
        require(inventory['total_count'] <= 100, 'artifact inventory truncated')
        matches = [a for a in inventory['artifacts'] if a['name'] == 'p41-rehearsal-%s-1' % self.run_id]
        require(len(matches) == 1, 'unique rehearsal artifact required')
        artifact = matches[0]
        require(not artifact['expired'] and 0 < artifact['size_in_bytes'] <= 64 * 1024 * 1024 and
                artifact['workflow_run']['head_sha'] == self.c['sha'] and
                artifact['workflow_run']['id'] == self.run_id, 'invalid rehearsal artifact')
        raw = self.api('/actions/artifacts/%s/zip' % artifact['id'], binary=True)
        require(len(raw) == artifact['size_in_bytes'] and artifact['digest'] == 'sha256:' + sha(raw),
                'artifact digest/size mismatch')
        self.h.save(self.out / 'artifact.json', artifact)
        folder = self.h.fresh(self.out / 'originals')
        files = unpack(raw, folder, self.h)
        target = verify_release(files, self.c, self.run_id, self.marker)
        target['package'] = self.h.record(folder / 'prepared' / target['full']['fileName'])
        self.h.save(self.out / 'verified.json', target)
        return target

    def restore(self):
        require(not self.dispatch_attempted or self.terminal,
                'CI may still consume temporary variables; preserve them and the lock for reconciliation')
        errors = []
        for name in reversed(self.changed):
            change = self.c['variables'][name]
            try:
                current = self.variable(name)
                if current == change['before']:
                    continue
                require(current == change['during'], 'variable changed by another operator; not overwritten')
                self.set_variable(name, change['before'])
            except Exception:
                errors.append(name)
        require(not errors, 'unrestored rehearsal variables: ' + ', '.join(errors))
        self.h.save(self.out / 'variables-restored.json', dict(restored=True, names=self.changed))


def unpack(raw, out, host):
    files, names, total = {}, set(), 0
    with zipfile.ZipFile(io.BytesIO(raw)) as archive:
        require(len(archive.infolist()) <= 2000, 'too many archive members')
        entries = []
        for entry in archive.infolist():
            # ZipInfo normalizes backslashes on Windows; inspect the original spelling.
            name = entry.orig_filename
            p = PurePosixPath(name)
            require(not p.is_absolute() and p.parts and all(x not in ('..', '.') for x in p.parts)
                    and '\\' not in name and ':' not in name and
                    all(re.fullmatch(r'[A-Za-z0-9_.-]+', x) and not x.endswith('.') and
                        not re.fullmatch(r'(?i:con|prn|aux|nul|com[0-9]|lpt[0-9])', x.split('.')[0])
                        for x in p.parts), 'unsafe artifact path')
            normalized = p.as_posix().casefold()
            require(normalized not in names and (entry.external_attr >> 16) & 0o170000 != 0o120000,
                    'duplicate/symlink artifact member')
            names.add(normalized)
            total += entry.file_size
            require(total <= 128 * 1024 * 1024 and entry.file_size <= 32 * 1024 * 1024, 'oversized expanded artifact')
            host.checked(out.joinpath(*p.parts))
            if not entry.is_dir():
                entries.append(entry)
        for entry in entries:
            data = archive.read(entry)
            host.raw(out / entry.filename, data)
            files[entry.filename] = data
    return files


def verify_release(files, config, run_id, marker):
    metadata_raw = files['prepared/cloudflare-firmware-release-metadata.json']
    m = strict_json(metadata_raw)
    e = strict_json(files['prepared/release-evidence.json'])
    build = strict_json(files['keyed-build/gcc-build-inputs.json'])
    require(m['schemaVersion'] == 2 and m['appId'] == 'trace' and m['deviceModel'] == 'e-track-at32f435'
            and m['commitSha'] == config['sha'] and m['versionName'] == config['version'] and
            m['versionCode'] == config['version_code'] and str(m['runId']) == str(run_id) and
            m['releaseNotes'] == marker, 'firmware metadata identity mismatch')
    require(build['commitSha'] == config['sha'] and build['versionName'] == config['version'] and
            build['versionCode'] == config['version_code'] and
            build['keyBinding']['source'] == 'approved-ci-key-v1' and
            build['buildConfiguration']['actualProfile'] == 'p34-v2-candidate', 'keyed build identity mismatch')
    require(e['mode'] == 'rehearsal' and e['github'] is None and e['commitSha'] == config['sha'] and
            str(e['executionRunId']) == str(run_id) and str(e['canonicalRunId']) == str(run_id) and
            str(e['executionAttempt']) == '1' and e['metadataSha256'] == sha(metadata_raw) and
            e['preflight']['ok'] is True and e['preflight']['environment'] == 'staging' and
            e['registration']['ok'] is True and e['registration']['state'] == 'ready', 'test publication evidence mismatch')
    require(len(m['assets']) == 3 and {a['kind'] for a in m['assets']} == {'full', 'patch', 'recovery'}, 'asset set')
    require(len(e['uploads']) == 3, 'upload evidence missing')
    for a in m['assets']:
        data = files['prepared/' + a['fileName']]
        require(len(data) == a['sizeBytes'] and sha(data) == a['sha256'] and a['r2Verified'] is True,
                'local package integrity mismatch')
        upload = [x for x in e['uploads'] if x['kind'] == a['kind']]
        require(len(upload) == 1 and upload[0]['ok'] is True and
                all(upload[0][k] == a[k] for k in ('fileName', 'sha256', 'sizeBytes', 'r2Key')), 'upload binding mismatch')
    require(sha(files['prepared/app-final.bin']) == m['targetImageSha256'], 'final firmware hash mismatch')
    for kind in ('app', 'boot'):
        require(sha(files['keyed-build/' + kind + '/' + build[kind]['fileName']]) == build[kind]['sha256'],
                'keyed input hash mismatch')
    logs = files['keyed-build/steps/build.stdout.txt'] + files['keyed-build/steps/build.stderr.txt']
    require(not re.search(rb'\berror:', logs), 'compiler errors in successful CI evidence')
    return dict(releaseId=e['registration']['releaseId'], versionCode=m['versionCode'],
        targetImageSha256=m['targetImageSha256'], assets=m['assets'],
        full=next(a for a in m['assets'] if a['kind'] == 'full'),
        warnings=len(re.findall(rb'\bwarning:', logs)), errors=len(re.findall(rb'\berror:', logs)))
