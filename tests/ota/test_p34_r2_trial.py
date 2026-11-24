from contextlib import ExitStack, nullcontext
import copy
import json
from pathlib import Path
import sys
from types import SimpleNamespace
import unittest
from unittest import mock

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT/'Tools/ota'))
import p34_r2_trial as run


class Tests(unittest.TestCase):
    def test_real_context_config_separates_current_recovery_from_old_phone_history(self):
        s = run.cli.Store(ROOT)
        api = run.Trial(s)
        out = ROOT/'.cache/model-r2-trial'
        registries = {name: getattr(run.cli, name) for name in
            ('MEASURED_FULL_GROUPS', 'NEW_BOOT_GROUPS', 'ALL_PATCH_GROUPS', 'RECONNECT_GROUP')}
        with ExitStack() as guards:
            for name in ('full_api', 'window_api', 'successor_api', 'install_api', 'patch_api'):
                module = getattr(api, name)
                for method in ('load', 'load_for_context'):
                    if hasattr(module, method):
                        guards.enter_context(mock.patch.object(module, method,
                            side_effect=AssertionError('historical asset loader called')))
            c = api.context(out)
            installed = api.installed_context(out)
        api.preflight(c, out)
        value = api.phone(c, 'r2_host_test').config(c, 's04', 921600, 28, 'https://offline.trycloudflare.com')
        run.post.asset_api.policy.validate(value, api.assets)
        self.assertEqual((value['currentVersionCode'], value['targetVersionCode'], value['packageBytes']),
                         (30276, 30277, 294052))
        self.assertEqual(value['schema'], 9)
        self.assertEqual(value['dataBatchFrames'], 12)
        self.assertEqual(installed.receiver_image_sha, api.assets['target']['sha256'])
        self.assertEqual(c.group, api.group)
        self.assertEqual(c.package_kind, 'full')
        for name, original in registries.items(): self.assertIs(getattr(run.cli, name), original)
        self.assertIs(c.p.query.m, c.envelope)
        source_records = c.sources()
        for path in (*run.post.reader_sources(s), run.ROOT/'Tools/ota/p34_capture_capacity.py'):
            self.assertIn(run.cli.record(path), source_records)
        self.assertEqual(api.predecessor(c)['descriptor']['kind'], 'CLOSED_R2A_RECOVERY_AND_READ_ONLY_BASELINE')
        self.assertFalse(api.proof['historical_ota_predecessor'])
        self.assertEqual(api.historical_capture['report']['summary']['input']['targetVersionCode'], 30275)
        self.assertEqual(c.native_authority()['mode'], 'NO_NATIVE_IN_PHONE_CELL')
        self.assertIs(run.Trial.observe_install, run.prior.Trial.observe_install)
        self.assertIs(run.Trial.downloaded_package, run.prior.Trial.downloaded_package)
        self.assertIs(run.Trial.finish_install_snapshot, run.prior.Trial.finish_install_snapshot)
        with self.assertRaisesRegex(RuntimeError, 'prohibited'): api.install_checkpoint(c, out)
        history = api.historical_capture['report']
        phone = dict(capture_directories=7, stable_completed=True, snapshots=['snapshot-1.jsonl'],
            snapshot_records={'snapshot-1.jsonl': {'sha256': history['summary']['rawSha256']}},
            config=history['inputs']['config'], pid=history['summary']['pid'],
            health={'captureId': history['summary']['captureId']})
        saved = {}
        original_record = run.cli.record
        def record(path):
            if path == out/'prestart-phone/result.json': return {'path': str(path), 'sha256': 'f'*64, 'bytes': 1}
            return original_record(path)
        def save(path, value): saved[path.name] = json.loads(json.dumps(value))
        with mock.patch.object(c, 'save', side_effect=save), mock.patch.object(c, 'root_state', return_value={}), \
             mock.patch.object(c, 'sources', return_value=source_records), \
             mock.patch.object(run.cli, 'record', side_effect=record), \
             mock.patch.object(api, 'installed_context', return_value=installed), \
             mock.patch.object(c, 'read', side_effect=lambda path: saved[path.name]):
            api.prepare(c, out, phone, {})
            api.validate(c, out)
            plan = copy.deepcopy(saved['plan.json'])
            for key, bad in (('group', 'wrong'), ('package_kind', 'patch'), ('bindings', {}),
                ('target_bindings', {}), ('cells', {}), ('native_authority', {})):
                with self.subTest(plan_key=key):
                    saved['plan.json'] = dict(plan, **{key: bad})
                    with self.assertRaises(RuntimeError): api.validate(c, out)
            saved['plan.json'] = plan
        # Exercise both live-reader paths on real encoded schema9/radio/PHY records.
        sys.path.insert(0, str(ROOT/'tests/boot'))
        import test_p34_r2_postcheck as fixture
        with fixture.trigger_fixture() as (store, snapshot, files):
            expected = store.read(snapshot.parent.parent/'runtime-config.json')
            summary, _, _ = run.backend.verify_full_snapshot(c.envelope, files['finished/snapshot.jsonl'], expected,
                run.cli.record(snapshot.parent.parent/'runtime-config.json')['sha256'], 123,
                c.apk['metadata']['device_observation']['sentinel'])
            query, _, _ = c.p.query.validate(files['queries/events.jsonl'], files['queries/health-before.json'],
                files['queries/health-after.json'], pid=123, sentinel=c.apk['metadata']['device_observation']['sentinel'],
                target=expected['target'])
            self.assertEqual(query['captureId'], summary['captureId'])
            for raw in (files['finished/snapshot.jsonl'].replace(b'OTA_RADIO {}', b'OTA_RADIO token=x'),
                        files['finished/snapshot.jsonl'].replace(b'"lost":0', b'"lost":1'),
                        files['finished/snapshot.jsonl'][:-1]):
                with self.assertRaises(ValueError):
                    c.envelope.verify(raw, sentinel=c.apk['metadata']['device_observation']['sentinel'], target=expected['target'])

    def test_phone_lifecycle_preserves_original_observer_and_does_not_claim_final_success(self):
        for fail in (False, True):
            events, saved = [], {}
            api = object.__new__(run.Trial)
            api.store, api.proof = run.cli.Store(ROOT), {'descriptor': {'kind': 'model-recovery'}}
            c = SimpleNamespace(load=lambda *a: SimpleNamespace(device_lock=lambda: nullcontext()),
                save=lambda path, value, **kw: saved.__setitem__(path.name, value), now=lambda: 'model-time')
            phone = SimpleNamespace(usb=lambda *a: nullcontext(object()), network=lambda *a: nullcontext('https://model'),
                release_old=lambda *a: events.append('retain-old-capture'),
                config=lambda *a: events.append('config') or {'model': True},
                provision=lambda *a: events.append('provision') or 123)
            api.phone = lambda *a: phone
            def observe(*args):
                events.append('original-observe-install')
                if fail: raise RuntimeError('original observer rejected')
                return {'outcome': 'completed'}
            api.observe_install = observe
            with mock.patch.object(run.post, 'verify_trigger', side_effect=lambda *a: events.append('verify-original-trigger') or {}) as trigger:
                code = api.install_worker(c, ROOT/'.cache/model-r2-trial', 's04')
            self.assertEqual(code, int(fail))
            self.assertFalse(saved['result.json']['final_device_verified'])
            self.assertFalse(saved['result.json']['native_trace_used'])
            self.assertEqual(events[:4], ['retain-old-capture', 'config', 'provision', 'original-observe-install'])
            self.assertEqual(trigger.call_count, int(not fail))
            self.assertEqual(saved['result.json']['result'], 'R2_OTA_INCOMPLETE' if fail else 'R2_OTA_SNAPSHOT_CAPTURED')

    def test_changed_current_baseline_rejects_without_relabeling_old_ota(self):
        s = run.cli.Store(ROOT)
        with mock.patch.object(run.cli, 'record', return_value={'sha256': '0'*64}):
            with self.assertRaisesRegex(RuntimeError, 'closed R2 baseline'): run.current(s)


if __name__ == '__main__': unittest.main()
