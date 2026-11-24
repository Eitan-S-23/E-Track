import copy
from contextlib import contextmanager
import hashlib
import json
from pathlib import Path
import sys
from types import SimpleNamespace
import unittest
from urllib.parse import urlsplit
from unittest import mock

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT/'Tools/ota'))
sys.path.insert(0, str(ROOT/'tests/boot'))
import p34_r2_postcheck as run
import test_p34_r2_backup_device as mapped_fixture
import test_p34_r2_checkpoint_device as identity_fixture


def encoded(value):
    return (json.dumps(value, separators=(',', ':'))+'\n').encode()


def observations(config, sentinel, config_sha):
    capture = '1789990000000000-0123456789abcdef01234567'
    header = dict(kind='open', schema=1, captureId=capture, sentinel=sentinel,
        target=config['target'], pid=123, platform='android', openedAt='2026-10-06T00:00:00Z',
        limits=dict(captureBytes=67108864, pendingBytes=1048576))
    experiment = {k: v for k, v in config.items() if k not in ('target', 'firmwareLatestUrl')}
    experiment.update(deviceAddress=config['target'], endpointHost=urlsplit(config['firmwareLatestUrl']).hostname,
                      configSha256=config_sha)
    messages = ['OTA_EXPERIMENT '+json.dumps(experiment), 'OTA_RADIO {}', 'OTA_PHY {}',
        'OTA_PHY_CANCEL nativeAcknowledged=false', 'OTA_LINK_STATS '+json.dumps(dict(label='query',
            device=config['target'], getInfo=dict(calls=1, failures=0), bind=dict(found=True, subscribeOk=True)))]
    items = [header, *(dict(kind='line', message=line) for line in messages)]
    query = b''.join(encoded(dict(row, seq=i)) for i, row in enumerate(items, 1))
    health = dict(schema=1, captureId=capture, healthy=True, lost=0, error=None,
        upgradeStarts=0, upgradeEnds=0, outcome=None, records=len(items), bytes=len(query), producerLines=len(messages))
    identity = {k: config[k] for k in ('packageSha256', 'packageBytes', 'currentVersionCode',
        'targetVersionCode', 'currentImageSha256', 'targetImageSha256')}
    identity.update(deviceAddress=config['target'], appLifecycle='resumed')
    items.append(dict(kind='upgrade-start', input=identity))
    items.extend(dict(kind='line', message='OTA_MONO '+event+' monoUs=10 wallUs=100')
                 for event in ('MONO_BUDGET_START', 'MONO_END_ACK_OK', 'MONO_REBOOT_VERIFIED'))
    for phase, prefix in (('pre-transfer', 'current'), ('post-reboot', 'target')):
        items.append(dict(kind='line', message='OTA_IDENTITY '+json.dumps(dict(phase=phase,
            versionCode=config[prefix+'VersionCode'], imageSha256=config[prefix+'ImageSha256'],
            deviceAddress=config['target']))))
    items.append(dict(kind='upgrade-end', outcome='completed'))
    raw = b''.join(encoded(dict(row, seq=i)) for i, row in enumerate(items, 1))
    footer = dict(health, kind='snapshot', records=len(items), bytes=len(raw), producerLines=len(messages)+5,
        upgradeStarts=1, upgradeEnds=1, outcome='completed', sha256=hashlib.sha256(raw).hexdigest(),
        exportedAt='2026-10-06T00:01:00Z')
    # Health contains schema/counters too, but the snapshot footer has an exact field set.
    finished = raw+encoded(footer)
    return query, encoded(health), finished, encoded({k: v for k, v in footer.items()
        if k not in ('kind', 'sha256', 'exportedAt')})


@contextmanager
def trigger_fixture():
    s = run.cli.Store(ROOT)
    assets = s.read(run.ASSET_RECEIPT)['groups']['transition']
    old = s.read(ROOT/'.cache/p34-sha-candidate/trials/measure/cells/s04/runtime-config.json')
    config = dict(old, currentVersionCode=30276, targetVersionCode=30277,
        currentImageSha256=assets['receiver']['sha256'], targetImageSha256=assets['target']['sha256'],
        packageBytes=assets['package']['bytes'], packageSha256=assets['package']['sha256'])
    apk = s.read(run.asset_api.policy.APK)
    cell = ROOT/'.cache/model-post-cell'
    def record_bytes(path, raw): return dict(path=str(path), bytes=len(raw), sha256=hashlib.sha256(raw).hexdigest())
    conf = encoded(config)
    conf_record = record_bytes(cell/'runtime-config.json', conf)
    query, pre, snapshot, done = observations(config, apk['metadata']['device_observation']['sentinel'], conf_record['sha256'])
    files = {'runtime-config.json': conf, 'launch.json': encoded(dict(pid=123, apk=apk['apk'])),
        'queries/result.json': encoded(dict(start_inputs_verified_before=True, pid=123, config=conf_record)),
        'queries/package.etu': Path(assets['package']['path']).read_bytes(), 'queries/events.jsonl': query,
        'queries/health-before.json': pre, 'queries/health-after.json': pre, 'queries/health-ready.json': pre,
        'finished/snapshot.jsonl': snapshot, 'finished/health-before.json': done, 'finished/health-after.json': done}
    original_read, original_bytes, original_record = s.read, Path.read_bytes, run.cli.record
    def key(path): return Path(path).relative_to(cell).as_posix() if Path(path).is_relative_to(cell) else None
    def raw(path):
        name = key(path)
        if name is not None:
            if name not in files: raise FileNotFoundError(name)
            return files[name]
        return original_bytes(path)
    def read(path): return json.loads(raw(Path(path))) if key(path) is not None else original_read(path)
    def record(path): return record_bytes(path, raw(Path(path))) if key(path) is not None else original_record(path)
    with mock.patch.object(s, 'read', side_effect=read), mock.patch.object(Path, 'read_bytes', new=raw), \
         mock.patch.object(run.cli, 'record', side_effect=record), \
         mock.patch.object(run.asset_api.policy, 'installed', return_value=apk):
        yield s, cell/'finished/snapshot.jsonl', files


class Tests(unittest.TestCase):
    def test_real_native_B_identity_and_A_backup_are_distinct(self):
        identity, _, _, native, archives = identity_fixture.session('r2-b.bin')
        self.assertEqual(identity['result'], 'R2_CHECKPOINT_NATIVE_CLOSED')
        self.assertEqual(archives['app'], run.IMAGE_B.read_bytes())
        api = SimpleNamespace(base=run.base, owner=run.mapped_owner, mapped=run.mapped,
            component=run.mapped_component, LOGS=run.baseline.LOGS, execute=run.execute_backup)
        session = run.bind(mapped_fixture.session, run=api)
        value, rows, paths, native, saved = session()
        self.assertEqual(value['result'], 'R2_BACKUP_MAPPED_NATIVE_CLOSED', value)
        self.assertEqual(value['state']['version'], 30276)
        self.assertEqual(saved['backup-payload'], run.IMAGE_A.read_bytes())
        self.assertNotEqual(saved['backup-payload'], run.IMAGE_B.read_bytes())
        self.assertEqual(value['state']['payload_bytes'], 619580)
        mapped_fixture.fixture.Tests().assert_close_only(native)
        trace = run.audit_trace('backup', paths, rows, value['dap'], mapped_fixture.fixture.record, True)
        self.assertEqual(trace['logs'], value['logs'])
        with self.assertRaises(ValueError): run.backup.expected(run.IMAGE_B.read_bytes())
        with self.assertRaises(ValueError): run.backup.Capture(None, None, run.IMAGE_A.read_bytes())

    def test_original_snapshot_and_byte_admission_are_both_required(self):
        with trigger_fixture() as (s, snapshot, files):
            proof = run.verify_trigger(s, snapshot)
            self.assertFalse(proof['final_device_verified'])
            self.assertEqual(len(proof['inputs']), 11)
            original = dict(files)
            for name in list(files):
                with self.subTest(missing=name):
                    files.pop(name)
                    with self.assertRaises((RuntimeError, ValueError, FileNotFoundError)):
                        run.verify_trigger(s, snapshot)
                    files.update(original)
            for name, change in (
                ('queries/result.json', dict(start_inputs_verified_before=False)),
                ('queries/result.json', dict(pid=124)),
                ('queries/health-before.json', dict(lost=1)),
                ('queries/health-after.json', dict(captureId='different')),
                ('queries/health-ready.json', dict(captureId='different')),
                ('queries/health-ready.json', dict(upgradeStarts=1)),
                ('finished/health-after.json', dict(lost=1))):
                with self.subTest(name=name, change=change):
                    files[name] = encoded(dict(json.loads(original[name]), **change))
                    with self.assertRaises((RuntimeError, ValueError)): run.verify_trigger(s, snapshot)
                    files.update(original)
            for change in ('credentials', 'pid', 'target', 'config', 'policy', 'unsuccessful'):
                with self.subTest(corrupt=change):
                    rows = [json.loads(line) for line in original['queries/events.jsonl'].splitlines()]
                    if change in ('pid', 'target'):
                        rows[0][change] = 124 if change == 'pid' else 'different'
                    elif change == 'credentials': rows[2]['message'] = 'OTA_RADIO token=x'
                    elif change == 'unsuccessful':
                        rows[-1]['message'] = rows[-1]['message'].replace('"calls": 1', '"calls": 0')
                    else:
                        experiment = json.loads(rows[1]['message'][len('OTA_EXPERIMENT '):])
                        experiment['configSha256' if change == 'config' else 'dataBatchFrames'] = '0'*64 if change == 'config' else 11
                        rows[1]['message'] = 'OTA_EXPERIMENT '+json.dumps(experiment)
                    data = b''.join(encoded(row) for row in rows)
                    files['queries/events.jsonl'] = data
                    for name in ('queries/health-before.json', 'queries/health-after.json'):
                        files[name] = encoded(dict(json.loads(original[name]), bytes=len(data)))
                    with self.assertRaises((RuntimeError, ValueError)): run.verify_trigger(s, snapshot)
                    files.update(original)

    def test_worker_rejects_kind_job_and_stale_plan_before_any_driver(self):
        s = run.cli.Store(ROOT)
        out = ROOT/'.cache/model-post-cell'
        item = dict(path=str(out/'tests.json'), bytes=1, sha256='a'*64)
        proof = dict(snapshot={'path': str(out/'finished/snapshot.jsonl')})
        plan = dict(out=str(out), scope=run.SCOPE, kind='identity', inputs=[], tests=item, trigger=proof,
            worker_seconds=900, parent_seconds=1020, connection_generation='r2-post-identity-'+out.name,
            before_history=[], native_history_approved=str(run.base.HISTORY))
        tested = dict(result='R2_POST_OTA_HOST_PASS', hardware=False, inputs=[])
        with mock.patch.object(run.base, 'in_job', return_value=False), mock.patch.object(s, 'read') as read:
            with self.assertRaisesRegex(RuntimeError, 'owned post'): run.worker(s, out, 'identity')
            read.assert_not_called()
        with mock.patch.object(run.base, 'in_job', return_value=True), \
             mock.patch.object(s, 'read', return_value=plan):
            with self.assertRaisesRegex(RuntimeError, 'kind'): run.worker(s, out, 'backup')
        with mock.patch.object(s, 'read', return_value=tested), \
             mock.patch.object(run.cli, 'record', return_value=item), \
             mock.patch.object(run, 'verify_trigger', return_value=proof), \
             mock.patch.object(run.base, 'history', return_value=[]):
            run.validate_plan(s, plan, out, [])
            for key, wrong in (('inputs', [1]), ('scope', 'other'), ('kind', 'write'),
                ('trigger', {'snapshot': {'path': 'changed'}}), ('worker_seconds', 901),
                ('parent_seconds', 1021), ('before_history', [1]), ('connection_generation', 'other')):
                with self.subTest(key=key), self.assertRaises((RuntimeError, KeyError)):
                    run.validate_plan(s, dict(plan, **{key: wrong}), out, [])


if __name__ == '__main__': unittest.main()
