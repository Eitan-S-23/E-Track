"""Offline release-entry regressions. No GitHub, backend or device mutations."""
import contextlib
import copy
import importlib.util
import io
import json
import os
from pathlib import Path
import subprocess
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[2]
SPEC = importlib.util.spec_from_file_location('release_candidate', ROOT / 'Tools/ota/release_candidate.py')
R = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(R)
A, B = 'a' * 40, 'b' * 40
CONFIG = dict(schema='original-admin-automatic-candidates-v1', firmware=dict(versionName='3.3.45', releaseNotes='old'))


def raw_config():
    return (json.dumps(CONFIG, indent=2) + '\n').encode()


def sample_log(source=A, version='3.3.46'):
    values = {'ready-metadata.json': dict(commitSha=source, runId='123', versionName=version,
        assets=[dict(kind='full', r2Verified=True), dict(kind='recovery', r2Verified=True)]),
        'register-receipt.json': dict(ok=True, channelPublished=False, productionApproved=False,
            registration=dict(state='ready', assetsRegistered=2))}
    return '\n'.join('job step 2026-11-21 ORIGINAL_ADMIN_RECEIPT ' + json.dumps(dict(name=k, value=v))
                     for k, v in values.items())


class VersionTests(unittest.TestCase):
    def test_mcu_only_version_and_notes_change(self):
        plan, raw = R.version_edit('mcu', raw_config())
        self.assertEqual((plan['version'], plan['code'], plan['file']), ('3.3.46', 30346, R.FIRMWARE))
        value = json.loads(raw)
        value['firmware'] = CONFIG['firmware']
        self.assertEqual(value, CONFIG)

    def test_app_increments_both_fields_preserving_other_bytes(self):
        before = b'# comment\r\nversion: 1.0.88+114\r\nname: trace\r\n'
        plan, raw = R.version_edit('app', before)
        self.assertEqual(raw, before.replace(b'1.0.88+114', b'1.0.89+115'))
        self.assertEqual((plan['version'], plan['code']), ('1.0.89', 115))

    def test_mcu_decimal_rollover(self):
        self.assertEqual(R.next_version('3.3.99', True), '3.4.0')
        self.assertEqual(R.next_version('3.99.99', True), '4.0.0')

    def test_invalid_versions_and_overflow(self):
        for version in ('01.2.3', '3.100.0', '3.0.100', '3.3.-1', '429496.72.95'):
            with self.subTest(version=version), self.assertRaises(RuntimeError):
                R.next_version(version, True)

    def test_app_rejects_duplicate_missing_overflow(self):
        for raw in (b'name: app', b'version: 1.0.88+114\nversion: 1.0.89+115\n',
                    b'version: 1.0.88+2100000000\n', b'version: 01.0.88+114\n'):
            with self.subTest(raw=raw), self.assertRaises(RuntimeError):
                R.version_edit('app', raw)

    def test_notes_do_not_change_app(self):
        with self.assertRaises(RuntimeError):
            R.version_edit('app', b'version: 1.0.88+114\n', 'not allowed')
        for notes in (' ', 'x' * 8001):
            with self.assertRaises(RuntimeError):
                R.version_edit('mcu', raw_config(), notes)

    def test_drafts_are_reservations(self):
        with self.assertRaises(RuntimeError):
            R.check_reservations('app', '1.0.89', [dict(tag_name='v1.0.89', draft=True)], [])
        with self.assertRaises(RuntimeError):
            R.check_reservations('mcu', '3.3.46', [], [dict(ref='refs/tags/mcu-e-track-at32f435-v3.3.46')])
        R.check_reservations('mcu', '3.3.46', [dict(tag_name='mcu-e-track-at32f435-v3.3.45')], [])

    def test_run_selection_is_exact_first_push(self):
        run = dict(head_sha=A, event='push', path=R.WORKFLOW, head_branch='main', run_attempt=1)
        self.assertEqual(R.matching_run([run], A), run)
        self.assertIsNone(R.matching_run([dict(run, event='workflow_dispatch')], A))
        self.assertIsNone(R.matching_run([dict(run, head_sha=B)], A))
        for rows in ([run, run], [dict(run, run_attempt=2)]):
            with self.assertRaises(RuntimeError):
                R.matching_run(rows, A)

    def test_receipt_requires_ready_verified_source_bound_assets(self):
        log = sample_log()
        self.assertEqual(R.firmware_receipt(log, A, 123, '3.3.46')['errors'], 0)
        for text in (log.replace(A, B), log.replace('"ready"', '"pending"'),
                     log.replace('"r2Verified": true', '"r2Verified": false'),
                     log.replace('"channelPublished": false', '"channelPublished": true'),
                     log.replace('"productionApproved": false', '"productionApproved": true')):
            with self.assertRaises(RuntimeError):
                R.firmware_receipt(text, A, 123, '3.3.46')


class FakeHost:
    dirty = False
    remote_moved = False
    reserved = False
    push_error = False
    calls = []

    def __init__(self, root, out):
        self.root, self.out, self.head, self.remote = root, out, A, A
        self.staged = ''
        self.gh = 'gh'

    def authenticate(self):
        pass

    def clean(self, text):
        return text

    def releases(self, repo):
        return [dict(tag_name='mcu-e-track-at32f435-v3.3.46', draft=True)] if self.reserved else []

    def api(self, route):
        self.calls.append(('GET', route))
        if route == 'user':
            return dict(login='tester', id=1)
        if route.endswith('/git/ref/heads/main'):
            return dict(object=dict(sha=B if self.remote_moved else self.remote))
        if route.endswith('/git/matching-refs/tags/'):
            return []
        raise AssertionError(route)

    def git(self, *args):
        self.calls.append(args)
        if args == ('rev-parse', '--show-toplevel'):
            return str(self.root)
        if args == ('rev-parse', '--path-format=absolute', '--git-common-dir'):
            return str(self.root / '.git')
        if args == ('branch', '--show-current'):
            return 'main'
        if args == ('remote', 'get-url', 'origin'):
            return 'https://github.com/' + R.REPO + '.git'
        if args == ('status', '--porcelain=v1', '--untracked-files=no'):
            return ' M unrelated.cpp' if self.dirty else ''
        if args == ('rev-parse', 'HEAD'):
            return self.head
        if args == ('rev-parse', B + '^'):
            return A
        if args == ('diff', '--name-only'):
            return R.FIRMWARE if (self.root / R.FIRMWARE).read_bytes() != raw_config() else R.APP
        if args == ('diff', '--cached', '--name-only'):
            return self.staged
        if args == ('diff', '--check'):
            return ''
        if args == ('diff', '--cached', '--check'):
            return ''
        if args[0] == 'add':
            self.staged = args[-1]
            return ''
        if 'commit' in args:
            self.head = B
            return B
        if args[0] == 'show':
            if ':' in args[-1]:
                return (self.root / args[-1].split(':', 1)[1]).read_text().strip()
            return self.staged
        if args[0] == 'push':
            if self.push_error:
                raise RuntimeError('network lost after push request')
            self.remote = B
            return ''
        raise AssertionError(args)


class EntryTests(unittest.TestCase):
    def setUp(self):
        cache = R.checked(ROOT, '.cache/release-candidate-tests')
        cache.mkdir(parents=True, exist_ok=True)
        self.tmp = tempfile.TemporaryDirectory(dir=cache)
        self.root = Path(self.tmp.name).resolve()
        self.oldcwd = Path.cwd()
        self.addCleanup(self.tmp.cleanup)
        self.addCleanup(os.chdir, self.oldcwd)
        os.chdir(self.root)
        (self.root / '.git/objects').mkdir(parents=True)
        for name, raw in ((R.FIRMWARE, raw_config()), (R.APP, b'version: 1.0.88+114\n')):
            path = self.root / name
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(raw)
        FakeHost.calls = []
        FakeHost.dirty = FakeHost.remote_moved = FakeHost.reserved = FakeHost.push_error = False

    def execute(self, *args, delivered=True):
        def wait(host, state, save, minutes):
            if delivered:
                save('DELIVERED')
            else:
                raise RuntimeError('observation interrupted')
        with patch.object(R, 'ROOT', self.root), patch.object(R, 'Host', FakeHost), \
                patch.object(R, 'wait_for_delivery', side_effect=wait), \
                contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
            return R.main(list(args))

    def test_dry_run_preserves_both_files_and_never_commits(self):
        self.assertEqual(self.execute('mcu', '--dry-run'), 0)
        self.assertEqual((self.root / R.FIRMWARE).read_bytes(), raw_config())
        self.assertFalse(any(c[0] in ('add', 'push') or 'commit' in c for c in FakeHost.calls))

    def test_real_entry_stages_only_selected_mcu_file(self):
        self.assertEqual(self.execute('mcu'), 0)
        self.assertIn(('add', '--', R.FIRMWARE), FakeHost.calls)
        self.assertIn(('push', 'origin', B + ':refs/heads/main'), FakeHost.calls)
        self.assertEqual((self.root / R.APP).read_bytes(), b'version: 1.0.88+114\n')
        self.assertFalse((self.root / '.cache/candidate-release/active.lock').exists())

    def test_app_entry_only_changes_pubspec(self):
        self.assertEqual(self.execute('app'), 0)
        self.assertIn(('add', '--', R.APP), FakeHost.calls)
        self.assertEqual((self.root / R.FIRMWARE).read_bytes(), raw_config())
        self.assertEqual((self.root / R.APP).read_bytes(), b'version: 1.0.89+115\n')

    def test_dirty_diverged_and_reserved_stop_before_edits(self):
        for name in ('dirty', 'remote_moved', 'reserved'):
            with self.subTest(name=name):
                setattr(FakeHost, name, True)
                self.assertEqual(self.execute('mcu'), 1)
                self.assertEqual((self.root / R.FIRMWARE).read_bytes(), raw_config())
                setattr(FakeHost, name, False)

    def test_interruption_blocks_next_bump_and_resume_is_read_only(self):
        self.assertEqual(self.execute('mcu', delivered=False), 1)
        receipt = next((self.root / '.cache/candidate-release').glob('*/result.json'))
        modified = (self.root / R.FIRMWARE).read_bytes()
        self.assertEqual(self.execute('mcu'), 1)
        self.assertEqual((self.root / R.FIRMWARE).read_bytes(), modified)
        FakeHost.calls = []
        self.assertEqual(self.execute('--resume', str(receipt)), 0)
        self.assertFalse(any(c[0] in ('add', 'push') or 'commit' in c for c in FakeHost.calls))

    def test_push_failure_never_repeats_push(self):
        FakeHost.push_error = True
        self.assertEqual(self.execute('mcu'), 1)
        self.assertEqual(sum(c[0] == 'push' for c in FakeHost.calls), 1)
        receipt = json.loads(next((self.root / '.cache/candidate-release').glob('*/result.json')).read_text())
        self.assertEqual((receipt['source'], receipt['phase']), (B, 'PUSH_STARTED'))

    def test_existing_lock_is_preserved(self):
        lock = self.root / '.cache/candidate-release/active.lock'
        lock.parent.mkdir(parents=True)
        lock.write_text('another owner')
        self.assertEqual(self.execute('mcu'), 1)
        self.assertEqual(lock.read_text(), 'another owner')

    def test_git_and_gh_outputs_are_contained_and_redacted(self):
        out = self.root / '.cache/host-test'
        out.mkdir(parents=True)
        with patch.object(R.shutil, 'which', return_value='tool'):
            host = R.Host(self.root, out)
        host.token = 'private-test-secret'
        with patch.object(R.subprocess, 'run', return_value=subprocess.CompletedProcess([], 0, b'private-test-secret', b'')) as call:
            host.run(['tool', 'read'])
        self.assertEqual(call.call_args.kwargs['cwd'], self.root)
        self.assertEqual(Path(host.env['TEMP']), out / 'host')
        self.assertNotIn('private-test-secret', (out / 'command-001.log').read_text())

    def test_existing_system_proxy_is_used_without_changing_configuration(self):
        out = self.root / '.cache/proxy-test'
        out.mkdir(parents=True)
        with patch.object(R.shutil, 'which', return_value='tool'), patch.dict(os.environ, {}, clear=True), \
                patch.object(R, 'getproxies', return_value={'https': 'http://127.0.0.1:7897'}):
            host = R.Host(self.root, out)
        self.assertEqual(host.env['HTTPS_PROXY'], 'http://127.0.0.1:7897')

    def test_explicit_proxy_is_not_overwritten(self):
        out = self.root / '.cache/explicit-proxy-test'
        out.mkdir(parents=True)
        with patch.object(R.shutil, 'which', return_value='tool'), \
                patch.dict(os.environ, {'HTTPS_PROXY': 'http://127.0.0.1:9999'}), \
                patch.object(R, 'getproxies', return_value={'https': 'http://127.0.0.1:7897'}):
            host = R.Host(self.root, out)
        self.assertEqual(host.env['HTTPS_PROXY'], 'http://127.0.0.1:9999')

    def test_real_git_accepts_preserved_crlf_version_edits(self):
        executable = R.shutil.which('git')
        if not executable:
            self.skipTest('Git is not installed')
        out = self.root / '.cache/real-git-test'
        out.mkdir(parents=True)
        with patch.object(R.shutil, 'which', return_value=executable):
            host = R.Host(self.root, out)
        host.git('init')
        original = raw_config().replace(b'\n', b'\r\n')
        target = self.root / R.FIRMWARE
        target.write_bytes(original)
        host.git('add', '--', R.FIRMWARE)
        host.git('-c', 'user.name=Fixture', '-c', 'user.email=fixture@example.invalid', 'commit', '-m', 'fixture')
        _, edited = R.version_edit('mcu', original)
        target.write_bytes(edited)
        host.git('diff', '--check')
        host.git('add', '--', R.FIRMWARE)
        host.git('diff', '--cached', '--check')
        self.assertEqual(json.loads(host.git('show', ':' + R.FIRMWARE))['firmware']['versionName'], '3.3.46')


class ObserveTests(unittest.TestCase):
    def test_ready_mcu_and_completed_original_app_are_distinct_receipts(self):
        for component in ('mcu', 'app'):
            with self.subTest(component=component):
                run = dict(id=123, html_url='https://github.com/test', head_sha=A, event='push', path=R.WORKFLOW,
                           head_branch='main', run_attempt=1, status='completed', conclusion='success')
                class Host:
                    gh = 'gh'
                    def api(self, route):
                        if '/runs?' in route:
                            return dict(workflow_runs=[run])
                        selected = 'firmware' if component == 'mcu' else 'app'
                        other = 'app' if component == 'mcu' else 'firmware'
                        return dict(jobs=[dict(name=selected, conclusion='success', id=1), dict(name=other, conclusion='skipped')])
                    def run(self, *args, **kwargs):
                        return sample_log() if component == 'mcu' else json.dumps(dict(source=A, completed=True,
                            channelPublished=False, runId=456))
                state, phases = dict(source=A, component=component, version='3.3.46'), []
                with contextlib.redirect_stdout(io.StringIO()):
                    R.wait_for_delivery(Host(), state, phases.append, 1)
                self.assertEqual(phases[-1], 'DELIVERED')
                self.assertIn('receipt', state)

    def test_release_pagination_includes_old_drafts(self):
        host = object.__new__(R.Host)
        page1 = [dict(tag_name='old-' + str(i)) for i in range(100)]
        draft = dict(tag_name='v1.0.89', draft=True)
        with patch.object(host, 'api', side_effect=[page1, [draft]]) as api:
            rows = host.releases('Eitan-S-23/Trace')
        self.assertEqual(api.call_count, 2)
        with self.assertRaises(RuntimeError):
            R.check_reservations('app', '1.0.89', rows, [])

    def test_completed_workflow_is_not_sufficient_without_registration(self):
        run = dict(id=123, html_url='https://github.com/test', head_sha=A, event='push', path=R.WORKFLOW,
                   head_branch='main', run_attempt=1, status='completed', conclusion='success')
        class Host:
            gh = 'gh'
            def api(self, route):
                if '/runs?' in route:
                    return dict(workflow_runs=[run])
                return dict(jobs=[dict(name='firmware', conclusion='success', id=1), dict(name='app', conclusion='skipped')])
            def run(self, *args, **kwargs):
                return 'Upload accepted only'
        with contextlib.redirect_stdout(io.StringIO()), self.assertRaises(RuntimeError):
            R.wait_for_delivery(Host(), dict(source=A, component='mcu', version='3.3.46'), lambda p: None, 1)

    def test_github_api_remains_get_only_and_allowlisted(self):
        host = object.__new__(R.Host)
        host.gh = 'gh'
        with patch.object(host, 'run', return_value='{}') as run:
            host.api('repos/' + R.REPO + '/releases')
            self.assertIn('GET', run.call_args.args[0])
            with self.assertRaises(RuntimeError):
                host.api('https://admin.example/api/publish')


if __name__ == '__main__':
    unittest.main()
