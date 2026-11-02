"""Host tests only: no CI, cloud, ADB or OTA requests."""
import copy
import io
import json
from pathlib import Path
import sys
import unittest
from unittest.mock import patch
import uuid
import zipfile

sys.path.insert(0, str(Path(__file__).resolve().parent))
import runner as r
import pipeline as p
import pipeline_build as b
import pipeline_cloud as c


def fixture():
    config = dict(schema=1, run_id='p35-pipeline-test',
        build=dict(ref='dev/firmware/test', sha='a' * 40, workflow_blob='b' * 40,
                   version='3.2.95', seconds=60, variables={}),
        cloud=dict(actor_sha256='d' * 64, query=dict(appId='trace', deviceModel='e-track-at32f435',
                   channel='stable', currentVersionCode=30293, currentImageSha='c' * 64, appVersionCode=92,
                   hardwareRevision=1, layoutId=1, bootVersion=1, protocolVersion=1)),
        plan=dict(path='template.json', bytes=100, sha256='e' * 64),
        authority=dict(test_ci=True, test_channel=True, device_campaign=True,
                       exclusive_rehearsal_environment=True, reference='host test only'))
    template = json.loads((r.ROOT / 'Tools/ota/p35-automation/plan.example.json').read_bytes())
    template['allow_bluetooth_toggle'] = True
    template['app'].update(sha256='b' * 64, version_code=92)
    for name in ('adb', 'adb_key'):
        template['phone'][name].update(bytes=3, sha256='a' * 64)
    template['firmware'].update(protocol=2, current=dict(version=30293, sha256='c' * 64))
    template['firmware']['target']['sha256'] = 'd' * 64
    template['firmware']['package']['sha256'] = 'e' * 64
    target = dict(releaseId='fw_test', versionCode=30295, targetImageSha256='f' * 64,
                  package=dict(path='package.etu', bytes=291113, sha256='a' * 64), assets=[])
    rows = dict(stable=dict(channel='stable', currentReleaseId='old', revision=22,
                           disableLatest=False, disableDownloads=False),
                beta=dict(channel='beta', currentReleaseId=None, revision=11,
                          disableLatest=True, disableDownloads=True))
    return config, template, target, rows


def release_files():
    config, _, _, _ = fixture()
    cfg = dict(config['build'], version_code=30295)
    assets = [dict(kind=kind, fileName=kind + '.bin', sizeBytes=3, sha256=b.sha(b'abc'),
                   r2Verified=True, r2Key='test/' + kind) for kind in ('full', 'patch', 'recovery')]
    m = dict(schemaVersion=2, appId='trace', deviceModel='e-track-at32f435', commitSha=cfg['sha'],
        versionName=cfg['version'], versionCode=30295, runId='123', releaseNotes='test-marker',
        targetImageSha256=b.sha(b'abc'), assets=assets)
    metadata = json.dumps(m).encode()
    evidence = dict(mode='rehearsal', github=None, commitSha=cfg['sha'], executionRunId='123',
        canonicalRunId='123', executionAttempt='1', metadataSha256=b.sha(metadata),
        preflight=dict(ok=True, environment='staging'),
        registration=dict(ok=True, state='ready', releaseId='fw_test'),
        uploads=[dict(a, ok=True) for a in assets])
    build = dict(commitSha=cfg['sha'], versionName=cfg['version'], versionCode=30295,
        keyBinding=dict(source='approved-ci-key-v1'), buildConfiguration=dict(actualProfile='p34-v2-candidate'),
        app=dict(fileName='app.bin', sha256=b.sha(b'abc')), boot=dict(fileName='boot.bin', sha256=b.sha(b'abc')))
    files = {'prepared/cloudflare-firmware-release-metadata.json': metadata,
             'prepared/release-evidence.json': json.dumps(evidence).encode(),
             'keyed-build/gcc-build-inputs.json': json.dumps(build).encode(),
             'prepared/app-final.bin': b'abc', 'keyed-build/app/app.bin': b'abc',
             'keyed-build/boot/boot.bin': b'abc', 'keyed-build/steps/build.stdout.txt': b'warning: retained\n',
             'keyed-build/steps/build.stderr.txt': b''}
    files.update({'prepared/' + a['fileName']: b'abc' for a in assets})
    return cfg, files


class ConfigurationTests(unittest.TestCase):
    def test_valid_configuration(self):
        self.assertEqual(p.validate(fixture()[0]), 30295)

    def test_rejects_production_and_unknown_controls(self):
        for change in ('ref', 'publish', 'variables', 'version', 'seconds', 'sha'):
            with self.subTest(change=change):
                cfg = fixture()[0]
                cfg['build'][change] = {'ref': 'main', 'publish': True, 'variables': {'OTA_BOOT_CHAIN_READY': {}},
                                        'version': '3.2.095', 'seconds': float('inf'), 'sha': '0' * 40}[change]
                with self.assertRaises(r.Stop):
                    p.validate(cfg)

    def test_query_rejects_credentials_and_foreign_channel(self):
        for key, value in [('token', 'secret'), ('channel', 'beta'), ('appId', 'foreign')]:
            cfg = fixture()[0]
            cfg['cloud']['query'][key] = value
            with self.assertRaises(r.Stop):
                p.validate(cfg)

    def test_windows_use_real_size_and_preserve_template(self):
        cfg, template, target, _ = fixture()
        before = copy.deepcopy(template)
        plan = p.make_plan(template, cfg, target)
        self.assertEqual(template, before)
        self.assertEqual(len(plan['cases']), 10)
        self.assertEqual(plan['cases'][-1]['durable_max'], target['package']['bytes'] - 1)
        self.assertTrue(all(x['durable_min'] % 4096 == 0 for x in plan['cases']))
        self.assertGreaterEqual(plan['cases'][-1]['durable_min'], target['package']['bytes'] * .8)

    def test_small_package_and_v1_are_not_faked(self):
        cfg, template, target, _ = fixture()
        with self.assertRaises(r.Stop):
            p.windows(40959)
        template['firmware']['protocol'] = 1
        with self.assertRaises(r.Stop):
            p.make_plan(template, cfg, target)

    def test_many_package_sizes_validate(self):
        cfg, template, target, _ = fixture()
        for size in (40960, 45001, 291113, 0x180000):
            target['package']['bytes'] = size
            r.validate_plan(p.make_plan(template, cfg, target))

    def test_archive_binding_positive(self):
        cfg, files = release_files()
        actual = b.verify_release(files, cfg, 123, 'test-marker')
        self.assertEqual(actual['warnings'], 1)
        self.assertEqual(actual['errors'], 0)

    def test_archive_rejects_wrong_run_marker_and_corrupt_asset(self):
        for change in ('run', 'marker', 'asset', 'final', 'key', 'source', 'production', 'upload'):
            with self.subTest(change=change):
                cfg, files = release_files()
                run, marker = 123, 'test-marker'
                if change == 'run': run = 124
                if change == 'marker': marker = 'different dispatch'
                if change == 'asset': files['prepared/full.bin'] = b'bad'
                if change == 'final': files['prepared/app-final.bin'] = b'bad'
                if change == 'source': cfg['sha'] = 'b' * 40
                if change == 'key':
                    value = json.loads(files['keyed-build/gcc-build-inputs.json'])
                    value['keyBinding']['source'] = 'development-key'
                    files['keyed-build/gcc-build-inputs.json'] = json.dumps(value).encode()
                if change in ('production', 'upload'):
                    value = json.loads(files['prepared/release-evidence.json'])
                    if change == 'production': value['mode'] = 'production'
                    else: value['uploads'][0]['sha256'] = 'a' * 64
                    files['prepared/release-evidence.json'] = json.dumps(value).encode()
                with self.assertRaises(r.Stop):
                    b.verify_release(files, cfg, run, marker)


class CloudTests(unittest.TestCase):
    def client(self):
        cfg, _, target, rows = fixture()
        client = c.Cloud(cfg['cloud'], None, None)
        client.login = lambda: None
        return client, target, rows

    def test_restore_no_change_and_lost_response_are_idempotent(self):
        for state in ('original', 'restored'):
            client, target, original = self.client()
            value = original if state == 'original' else c.published(c.published(original, target['releaseId']), 'old')
            client.channels = lambda: value
            client.mutate = lambda *args: self.fail('no mutation expected')
            self.assertEqual(client.restore(original, target), value)

    def test_restore_after_lost_activation_response(self):
        client, target, original = self.client()
        current = c.published(original, target['releaseId'])
        client.channels = lambda: current
        calls = []
        client.mutate = lambda before, release, action: calls.append((before, release, action))
        client.restore(original, target)
        self.assertEqual(calls, [(current, 'old', 'retract')])

    def test_restore_does_not_overwrite_concurrent_operator(self):
        for changed in ('revision', 'release', 'beta', 'flags'):
            client, target, original = self.client()
            current = c.published(original, target['releaseId'])
            if changed == 'revision': current['stable']['revision'] += 1
            if changed == 'release': current['stable']['currentReleaseId'] = 'foreign'
            if changed == 'beta': current['beta']['revision'] += 1
            if changed == 'flags': current['stable']['disableLatest'] = True
            client.channels = lambda: current
            client.mutate = lambda *args: self.fail('foreign state must not be overwritten')
            with self.assertRaises(r.Stop):
                client.restore(original, target)

    def test_activation_rejects_changed_channel_before_publish(self):
        client, target, original = self.client()
        client.channels = lambda: c.published(original, 'foreign')
        client.releases = lambda: self.fail('changed channel must stop first')
        with self.assertRaises(r.Stop):
            client.activate(original, target, {})

    def test_mutation_uses_revision_and_checks_readback(self):
        client, _, original = self.client()
        calls = []
        client.request = lambda origin, route, body: (calls.append(body) or
            dict(ok=True, currentReleaseId='new', revision=23), [])
        client.channels = lambda: c.published(original, 'new')
        client.mutate(original, 'new', 'publish')
        self.assertEqual(calls[0]['expectedRevision'], 22)
        client.channels = lambda: original
        with self.assertRaises(r.Stop):
            client.mutate(original, 'new', 'publish')

    def test_activate_checks_live_registration_and_public_selection(self):
        for failure in ('none', 'hash', 'state', 'public', 'download'):
            client, target, original = self.client()
            full = dict(kind='full', sha256='a' * 64, sizeBytes=291113, fileName='full.etu')
            target['assets'] = [full]
            actual = dict(target, state='ready', archived=False, assets=[dict(full, r2State='available')])
            latest = dict(schemaVersion=2, updateAvailable=True, **target)
            latest['asset'] = dict(full, downloadUrl=c.PUBLIC + '/download')
            if failure == 'hash': actual['assets'][0]['sha256'] = 'b' * 64
            if failure == 'state': actual['state'] = 'pending'
            if failure == 'public': latest['versionCode'] = 1
            if failure == 'download': latest['asset']['downloadUrl'] = 'https://foreign.invalid/package'
            client.channels = lambda: original
            client.releases = lambda: [actual]
            mutations = []
            client.mutate = lambda *args: mutations.append(args)
            client.request = lambda *args: (latest, [])
            if failure == 'none': client.activate(original, target, {})
            else:
                with self.assertRaises(r.Stop): client.activate(original, target, {})
            self.assertEqual(len(mutations), 0 if failure in ('hash', 'state') else 1)

    def test_http_adapter_hides_tokens_and_does_not_follow_redirects(self):
        class Response:
            def __init__(self, value, status=200):
                self.raw, self.status = json.dumps(value).encode(), status
            def read1(self, limit):
                value, self.raw = self.raw[:limit], self.raw[limit:]
                return value
            def getheaders(self): return []
        cfg = fixture()[0]
        host = MemoryHost()
        client = c.Cloud(cfg['cloud'], Path('cloud'), host)
        client.auth = {'Cookie': 'secret-access'}
        calls = []
        response = Response(dict(ok=True, role='owner', appId='trace', environment='staging',
                                 actor='private-actor', csrfToken='private-csrf'))
        class Connection:
            def __init__(self, hostname, **options):
                self.hostname = hostname
                assert options['context'].keylog_filename is None
            def request(self, method, route, body, headers): calls.append((self.hostname, headers))
            def getresponse(self): return response
            def close(self): pass
        with patch.object(c.http.client, 'HTTPSConnection', Connection):
            client.request(c.ADMIN, '/api/admin/session')
            self.assertNotIn('private-actor', json.dumps(host.saved))
            self.assertNotIn('private-csrf', json.dumps(host.saved))
            self.assertNotIn('secret-access', json.dumps(host.saved))
            response = Response(dict(asset=dict(downloadUrl='signed-secret')))
            client.request(c.PUBLIC, '/api/public/firmware/latest')
            self.assertNotIn('Cookie', calls[-1][1])
            self.assertNotIn('signed-secret', json.dumps(host.saved))
            response = Response({}, 302)
            with self.assertRaises(r.Stop): client.request(c.PUBLIC, '/api/public/firmware/latest')
            self.assertEqual(len(calls), 3)


class MemoryHost:
    def __init__(self): self.saved = {}
    def save(self, path, value): self.saved[str(path)] = copy.deepcopy(value)


class BuildTests(unittest.TestCase):
    def make(self):
        client = b.Build(fixture()[0]['build'], Path('test'), MemoryHost(), {}, 'test-marker')
        client.before_runs = []
        return client

    def test_dispatch_is_test_only(self):
        client = self.make()
        requests = []
        client.api = lambda route, body=None: (dict(sha=client.c['sha']) if route.startswith('/commits/')
                                               else requests.append((route, body)))
        client.wait = lambda: 'built'
        self.assertEqual(client.start(), 'built')
        payload = requests[0][1]['inputs']
        self.assertEqual(payload['publish'], 'false')
        self.assertEqual(payload['rehearsal'], 'true')
        self.assertEqual(payload['release_notes'], 'test-marker')
        self.assertEqual(len(requests), 1)

    def test_dispatch_lost_reply_does_not_retry_or_restore_variables(self):
        client = self.make()
        calls = []
        def fail(*args):
            if args[0].startswith('/commits/'):
                return dict(sha=client.c['sha'])
            calls.append(args)
            raise OSError('reply lost')
        client.api = fail
        with self.assertRaises(OSError): client.start()
        with self.assertRaises(r.Stop): client.restore()
        self.assertTrue(client.dispatch_attempted)
        self.assertEqual(len(calls), 1)

    def test_variable_restore_only_owned_values(self):
        for current in ('old', 'temporary', 'foreign'):
            client = self.make()
            name = 'OTA_PREVIOUS_RELEASE_JSON'
            client.c['variables'] = {name: dict(before='old', during='temporary')}
            client.changed = [name]
            client.variable = lambda name: current
            calls = []
            client.set_variable = lambda name, value: calls.append((name, value))
            if current == 'foreign':
                with self.assertRaises(r.Stop): client.restore()
            else:
                client.restore()
            self.assertEqual(calls, [(name, 'old')] if current == 'temporary' else [])

    def test_failed_ci_marks_terminal_before_failure(self):
        client = self.make()
        client.run_id = 123
        client.api = lambda route: dict(head_sha=client.c['sha'], run_attempt=1,
            event='workflow_dispatch', head_branch=client.c['ref'], path='.github/workflows/firmware-build.yml',
            status='completed', conclusion='failure')
        with self.assertRaises(r.Stop): client.wait()
        self.assertTrue(client.terminal)

    def test_ambiguous_dispatch_stops_without_selecting(self):
        client = self.make()
        client.runs = lambda: [dict(id=i, head_sha=client.c['sha'], event='workflow_dispatch',
                                    head_branch=client.c['ref']) for i in (1, 2)]
        with self.assertRaises(r.Stop): client.wait()
        self.assertIsNone(client.run_id)

    def test_preflight_checks_workflow_and_bootstrap_without_mutation(self):
        for failure in ('none', 'source', 'workflow', 'gate', 'bucket', 'active', 'descriptor'):
            client = self.make()
            descriptor = dict(provenanceKind='inaugural-bootstrap-v1', targetCommitSha=client.c['sha'],
                              targetVersionName=client.c['version'])
            values = dict(OTA_BOOT_CHAIN_READY='false',
                FIRMWARE_REHEARSAL_TRACE_R2_BUCKET='e-track-firmware-p41-test-releases',
                OTA_PREVIOUS_RELEASE_JSON=json.dumps(descriptor),
                OTA_APPROVED_BOOTSTRAP_BASELINE_SHA256=b.sha(json.dumps(descriptor, sort_keys=True, separators=(',', ':')).encode()))
            if failure == 'gate': values['OTA_BOOT_CHAIN_READY'] = 'true'
            if failure == 'bucket': values['FIRMWARE_REHEARSAL_TRACE_R2_BUCKET'] = 'production'
            if failure == 'descriptor': values['OTA_APPROVED_BOOTSTRAP_BASELINE_SHA256'] = 'b' * 64
            def api(route, body=None, **kwargs):
                self.assertIsNone(body)
                if route.startswith('/commits/'):
                    return dict(sha='f' * 40 if failure == 'source' else client.c['sha'])
                if route.startswith('/contents/'):
                    return dict(sha='f' * 40 if failure == 'workflow' else client.c['workflow_blob'])
                if '/variables?' in route:
                    return dict(total_count=len(values), variables=[dict(name=k, value=v) for k, v in values.items()])
                if '?status=' in route: return dict(total_count=1 if failure == 'active' else 0)
                return dict(workflow_runs=[])
            client.api = api
            with patch.dict(b.os.environ, GH_TOKEN='fake-test-token'):
                if failure == 'none': client.preflight()
                else:
                    with self.assertRaises(r.Stop): client.preflight()
            self.assertFalse(client.dispatch_attempted)

    def test_pending_ci_cannot_restore_variables(self):
        client = self.make()
        client.dispatch_attempted = True
        client.variable = lambda name: self.fail('pending CI must not restore anything')
        with self.assertRaises(r.Stop): client.restore()

    def test_successful_ci_archives_only_bound_run(self):
        client = self.make()
        client.run_id = 123
        client.api = lambda route: dict(head_sha=client.c['sha'], run_attempt=1,
            event='workflow_dispatch', head_branch=client.c['ref'], path='.github/workflows/firmware-build.yml',
            status='completed', conclusion='success')
        client.archive = lambda: 'verified-package'
        self.assertEqual(client.wait(), 'verified-package')
        self.assertTrue(client.terminal)


class FilesystemTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.h = r.load_host()
        cls.area = cls.h.fresh(r.ROOT / '.cache/p35-pipeline-tests-20261101' / ('suite-' + uuid.uuid4().hex))

    def folder(self):
        return self.h.fresh(self.area / uuid.uuid4().hex)

    def test_unpack_rejects_unsafe_duplicate_and_symlink_paths(self):
        for name in ('../escape', '/escape', 'C:/escape', 'a/b', 'link', 'NUL.bin', 'trailing.'):
            raw = io.BytesIO()
            with zipfile.ZipFile(raw, 'w') as archive:
                info = zipfile.ZipInfo(name)
                if name == 'link': info.external_attr = 0o120777 << 16
                archive.writestr(info, b'bad')
            data = raw.getvalue().replace(b'a/b', b'a\\b') if name == 'a/b' else raw.getvalue()
            with self.subTest(name=name), self.assertRaises(r.Stop): b.unpack(data, self.folder(), self.h)

    def test_unpack_real_bytes(self):
        raw = io.BytesIO()
        with zipfile.ZipFile(raw, 'w') as archive: archive.writestr('prepared/test.bin', b'abc')
        out = self.folder()
        self.assertEqual(b.unpack(raw.getvalue(), out, self.h), {'prepared/test.bin': b'abc'})
        self.assertEqual((out / 'prepared/test.bin').read_bytes(), b'abc')

    def test_pipeline_sequence_and_all_failure_cleanup(self):
        for failure in ('none', 'preflight', 'build', 'build-restore', 'activate', 'runner', 'runner-result', 'restore'):
            with self.subTest(failure=failure):
                root = self.folder()
                cfg, template, target, rows = fixture()
                order = []
                def event(name):
                    order.append(name)
                    if name == failure: raise r.Stop('TEST_FAILURE', name)
                class Builder:
                    def __init__(self, *args): pass
                    def preflight(self): event('preflight')
                    def start(self): event('build'); return target
                    def restore(self): event('build-restore')
                class Cloud:
                    def __init__(self, *args): pass
                    def preflight(self, version): event('cloud-preflight'); return rows
                    def activate(self, *args): event('activate')
                    def restore(self, *args): event('restore'); return rows
                def run(*args):
                    event('runner')
                    return dict(outcome='CAPABILITY_MISSING' if failure == 'runner-result' else 'AUTOMATION_COMPLETED')
                lock = root / '.cache/p35-pipeline.lock'
                with patch.object(p, 'ROOT', root), patch.object(p, 'LOCK', lock), patch.object(p, 'environment', return_value={}):
                    result = p.execute(cfg, template, dict(cfg['build'], version_code=30295),
                                       root / 'run', self.h, Builder, Cloud, run)
                if failure == 'none':
                    self.assertEqual(result['outcome'], 'PASS')
                    self.assertEqual(order, ['preflight', 'cloud-preflight', 'build', 'build-restore', 'activate', 'runner', 'restore'])
                else:
                    self.assertNotEqual(result['outcome'], 'PASS')
                self.assertEqual(lock.exists(), failure in ('restore', 'build-restore'))
                if 'activate' in order: self.assertIn('restore', order)
                if failure in ('preflight', 'build', 'build-restore', 'activate'): self.assertNotIn('runner', order)
                self.assertEqual(order.count('build-restore'), 1)
                self.assertEqual(result['formalAcceptance'], 'NOT_ADJUDICATED')

    def test_existing_lock_prevents_any_new_output_or_dispatch(self):
        root = self.folder()
        lock = root / '.cache/p35-pipeline.lock'
        self.h.save(lock, dict(existing=True))
        cfg, template, _, _ = fixture()
        with patch.object(p, 'ROOT', root), patch.object(p, 'LOCK', lock):
            with self.assertRaises(r.Stop): p.execute(cfg, template, cfg['build'], root / 'run', self.h)
        self.assertFalse((root / 'run').exists())

    def test_real_cli_offline_check_and_missing_execute(self):
        root = self.folder()
        cfg, template, _, _ = fixture()
        pin = self.h.raw(root / 'pinned-test-input', b'abc')
        template['phone'].update(adb=pin, adb_key=pin)
        self.h.save(root / 'template.json', template)
        cfg['plan'] = self.h.record(root / 'template.json')
        self.h.save(root / 'config.json', cfg)
        env = p.environment(self.h, root)
        command = [sys.executable, '-I', '-S', '-B', '-X', 'utf8', 'Tools/ota/p35-automation/runner.py']
        raw = self.h.command(root, 'check', command + ['pipeline-check', '--config', str(root / 'config.json')], env, seconds=20)
        self.assertEqual(json.loads(raw)['outcome'], 'CONFIGURATION_VALID')
        self.h.command(root, 'no-execute', command + ['pipeline', '--config', str(root / 'config.json'),
            '--out', str(root / 'must-not-exist')], env, seconds=20, success_codes=(2,))
        self.assertFalse((root / 'must-not-exist').exists())
        self.h.command(root, 'example-rejected', command + ['pipeline-check', '--config',
            'Tools/ota/p35-automation/pipeline.example.json'], env, seconds=20, success_codes=(2,))

    def test_recovery_never_rebuilds_or_replays_device(self):
        for failure in ('none', 'live-owner', 'pending-ci', 'unbound-dispatch', 'foreign-cloud'):
            with self.subTest(failure=failure):
                root = self.folder()
                prior = self.h.fresh(root / 'prior')
                cfg, _, target, rows = fixture()
                self.h.save(prior / 'configuration.json', cfg)
                owner = dict(pid=99999999, out=str(prior),
                    configurationSha256=b.sha((prior / 'configuration.json').read_bytes()))
                self.h.save(prior / 'owner.json', owner)
                lock = root / '.cache/p35-pipeline.lock'
                self.h.save(lock, owner)
                self.h.save(prior / 'build/dispatch-intent.json', dict(issued=True))
                if failure != 'unbound-dispatch': self.h.save(prior / 'build/run-bound.json', dict(id=123))
                self.h.save(prior / 'channels-before.json', rows)
                self.h.save(prior / 'target.json', target)
                self.h.save(prior / 'activation-intent.json', dict(
                    original=self.h.record(prior / 'channels-before.json'), target=self.h.record(prior / 'target.json')))
                originals = {x: x.read_bytes() for x in prior.rglob('*') if x.is_file()}
                actions = []
                class Builder:
                    def __init__(self, *args): pass
                    def api(self, route):
                        actions.append('read-ci')
                        return dict(head_sha=cfg['build']['sha'], run_attempt=1,
                            status='in_progress' if failure == 'pending-ci' else 'completed')
                    def restore(self): actions.append('restore-build')
                class Cloud:
                    def __init__(self, *args): pass
                    def restore(self, *args):
                        actions.append('restore-cloud')
                        r.require(failure != 'foreign-cloud', 'foreign cloud state')
                        return rows
                def command(*args, **kwargs):
                    return b'"python.exe","99999999"\n' if failure == 'live-owner' else b'INFO: No tasks\n'
                with patch.object(p, 'ROOT', root), patch.object(p, 'LOCK', lock), \
                     patch.object(p, 'Build', Builder), patch.object(p, 'Cloud', Cloud), \
                     patch.object(p, 'environment', return_value={}), patch.object(self.h, 'command', command):
                    if failure == 'none':
                        result = p.recover(prior, root / 'recovery', self.h)
                        self.assertEqual(result['outcome'], 'REMOTE_STATE_RESTORED')
                        self.assertEqual(actions, ['read-ci', 'restore-build', 'restore-cloud'])
                    else:
                        with self.assertRaises(r.Stop): p.recover(prior, root / 'recovery', self.h)
                self.assertEqual(lock.exists(), failure != 'none')
                if failure in ('live-owner', 'pending-ci', 'unbound-dispatch'):
                    self.assertNotIn('restore-build', actions)
                    self.assertNotIn('restore-cloud', actions)
                for path, raw in originals.items(): self.assertEqual(path.read_bytes(), raw)


if __name__ == '__main__':
    unittest.main()
