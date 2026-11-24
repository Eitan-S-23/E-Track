import copy
import io
from pathlib import Path
import sys
import unittest
from types import SimpleNamespace
from unittest import mock

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT/'Tools/ota'))
sys.path.insert(0, str(ROOT/'tests/boot'))
import p34_r2_backup_device as run
import test_p34_r2_state_device as fixture


def session(fault=None):
    image = run.owner.ASSETS['image'].read_bytes()
    archive = run.component.ARCHIVE.read_bytes()
    clock = fixture.Clock()
    paths = [fixture.BinaryBuffer(n, '') for n in run.LOGS]
    native = fixture.Native(paths, clock, image, fault)
    native.memory.update({a: 0 for a in (*run.mapped.DMA.values(), *run.mapped.ENDPOINTS.values())})
    header, payload = run.mapped.expected(archive)
    for base, raw in ((run.mapped.BASE, header), (run.mapped.PAYLOAD, payload)):
        native.memory.update({base+i: int.from_bytes(raw[i:i+4], 'little') for i in range(0, len(raw), 4)})
    if fault == 'header': native.memory[run.mapped.BASE] ^= 1
    if fault == 'block-deadline':
        function = native.JLINKARM_CORESIGHT_ReadAPDPReg
        callback = function.callback
        def expire(index, ap, pointer):
            address = native.tar
            result = callback(index, ap, pointer)
            if (index, ap, address) == (3, 1, run.mapped.PAYLOAD): clock.value += 31
            return result
        function.callback = expire
    rows, initial, saved = [], [], {}
    def persist(event, **fields): rows.append(dict(event=event, **fields))
    def collect(event, **fields):
        persist(event, **fields)
        initial.append(dict(event=event, **fields))
    def save(name, raw):
        if fault == 'archive': raise OSError('archive failure')
        if name in saved: raise AssertionError('repeated backup archive')
        saved[name] = raw
        if fault == 'archive-expiry': clock.value += 800
    original_probe = run.owner.Probe
    with mock.patch('recovery_entry.native_probe.guarded', side_effect=lambda f, *a, **k: f(*a)):
        dap = run.base.Dap(native, paths[0], ROOT/'.cache/model-only.jlink', io.BytesIO())
        dap.sdk = run.owner.JournalSDK(native, collect, clock=clock)
        observation = run.base.Observation(dap, collect, seconds=600, clock=clock)
        result = run.execute(dap, observation, persist, initial, paths, fixture.record, lambda: 900-clock.value,
            image, fixture.MAP, archive, save, clock=clock, sleep=clock.sleep, guard=lambda f, *a, **k: f(*a))
    assert run.owner.Probe is original_probe
    return result, rows, paths, native, saved


class Tests(unittest.TestCase):
    def test_actual_native_owner_backup_archives_log_replay_restore_close(self):
        value, rows, paths, native, saved = session()
        self.assertEqual(value['result'], 'R2_BACKUP_MAPPED_NATIVE_CLOSED', value)
        self.assertEqual(value['state']['payload_sha256'], run.mapped.PAYLOAD_SHA)
        self.assertEqual(len(saved['backup-payload']), 617588)
        self.assertEqual(saved['backup-header'], run.mapped.EXPECTED_HEADER)
        self.assertEqual((native.dp, native.tar, native.csw), (0x40, 0xe000ef38, 0x23000052))
        fixture.Tests().assert_close_only(native)
        trace = run.audit_trace(paths, rows, value['dap'], fixture.record, True)
        self.assertEqual(trace['logs'], value['logs'])
        self.assertEqual((trace['target_writes'], trace['native_close']), (0, 1))
        self.assertFalse(value['ota_ready'])
        changed = copy.deepcopy(rows)
        next(r for r in changed if r['event'] == 'online-log-head-verified')['record']['sha256'] = '0'*64
        with self.assertRaisesRegex(RuntimeError, 'head changed'):
            run.audit_trace(paths, changed, value['dap'], fixture.record, True)
        with self.assertRaises((RuntimeError, ValueError)):
            run.audit_trace(paths, rows, value['dap'], fixture.record, False)

    def test_state_header_archive_or_close_failures_preserve_single_close(self):
        for fault in ('reset', 'bad-ui', 'header', 'archive', 'close'):
            value, _, _, native, _ = session(fault)
            self.assertEqual(value['result'], 'FAILED', value)
            fixture.Tests().assert_close_only(native)
            self.assertFalse(value.get('native_close_audited', False))
            self.assertEqual(value['close_returned'], fault != 'close')

    def test_original_checkpoint_and_state_proofs_not_historical_ota(self):
        store = run.cli.Store(ROOT)
        proof = run.predecessor(store)
        self.assertFalse(proof['historical_ota_predecessor'])
        self.assertEqual(proof['state_review']['sha256'], run.REVIEW_SHA)
        original = run.cli.record
        def changed(path):
            value = original(path)
            return dict(value, sha256='0'*64) if Path(path) == run.STATE/'worker.json' else value
        with mock.patch.object(run.cli, 'record', side_effect=changed):
            with self.assertRaisesRegex(RuntimeError, 'state evidence changed'): run.predecessor(store)

    def test_deadline_and_archive_expiry_use_one_close_without_next_operation(self):
        for fault in ('block-deadline', 'archive-expiry'):
            value, rows, _, native, saved = session(fault)
            self.assertEqual(value['result'], 'FAILED', value)
            fixture.Tests().assert_close_only(native)
            self.assertTrue(value['close_returned'])
            if fault == 'block-deadline':
                reads = [r for r in rows if r['event'] == 'recovery-chunk-read-attempt' and
                         r['address'] >= run.mapped.PAYLOAD]
                self.assertEqual(len(reads), 1)
                self.assertFalse(saved)
            else:
                self.assertEqual(set(saved), {'backup-header'})

    def make_plan(self):
        out = ROOT/'.cache/unused-backup-model'
        test = out/'tests/result.json'
        item = dict(path=str(test), bytes=1, sha256='a'*64)
        proof = {'model': True}
        plan = dict(out=str(out), scope=run.SCOPE, inputs=[], tests=item, predecessor=proof,
            worker_seconds=900, parent_seconds=1020, connection_generation='r2-backup-'+out.name,
            before_history=[], native_history_approved=str(run.base.HISTORY))
        return out, test, item, proof, plan

    def test_bad_job_plan_tests_or_proof_reject_before_dll_or_output(self):
        store = run.cli.Store(ROOT)
        out, test, item, proof, original = self.make_plan()
        plan = original
        tests = dict(result='R2_BACKUP_DEVICE_HOST_PASS', inputs=[], hardware=False)
        def read(path): return tests if Path(path) == test else plan
        with mock.patch.object(run.base, 'in_job', return_value=False), mock.patch.object(store, 'read') as reader:
            with self.assertRaisesRegex(RuntimeError, 'owned backup'): run.worker(store, out)
            reader.assert_not_called()
        with mock.patch.object(run.base, 'in_job', return_value=True), \
             mock.patch.object(run.base, 'history', return_value=[]), \
             mock.patch.object(store, 'read', side_effect=read), \
             mock.patch.object(run, 'sources', return_value=[]), \
             mock.patch.object(run, 'predecessor', return_value=proof), \
             mock.patch.object(run.cli, 'record', return_value=item), \
             mock.patch.object(run.ctypes, 'CDLL') as load:
            run.validate_worker_plan(store, original, out, [])
            for key, value in (('scope', 'other'), ('inputs', [1]), ('tests', {}), ('predecessor', {}),
                ('worker_seconds', 180), ('parent_seconds', 240), ('connection_generation', 'other'),
                ('before_history', [1]), ('native_history_approved', 'other')):
                plan = dict(original, **{key: value})
                with self.subTest(key=key), self.assertRaises((RuntimeError, KeyError)): run.worker(store, out)
            plan = original
            tests['inputs'] = [1]
            with self.assertRaisesRegex(RuntimeError, 'current backup selftests'): run.worker(store, out)
            load.assert_not_called()

    def test_late_outer_failure_never_masks_failure_or_recloses_native(self):
        store = run.cli.Store(ROOT)
        out, _, _, _, plan = self.make_plan()
        dap = SimpleNamespace(_opened=True, close_returned=True)
        class Observation:
            closed = False
            native_closes = 0
            def close(self):
                if not self.closed:
                    self.closed = True
                    self.native_closes += 1
        obs = Observation()
        class Directory:
            def __enter__(self): return self
            def __exit__(self, *args): raise OSError('late directory close failure')
        def execute(*args, **kwargs):
            obs.close()
            return dict(result='R2_BACKUP_MAPPED_NATIVE_CLOSED', close_returned=True, state={'observed': True})
        def opened(path, mode='r', **kwargs):
            self.assertEqual(path.parent, out)
            return io.BytesIO() if 'b' in mode else io.StringIO()
        with mock.patch.object(run.base, 'in_job', return_value=True), \
             mock.patch.object(store, 'read', return_value=plan), \
             mock.patch.object(run, 'sources', return_value=[]), \
             mock.patch.object(run, 'validate_worker_plan'), \
             mock.patch.object(run.cli, 'record', return_value={'sha256': run.base.DLL_SHA}), \
             mock.patch.object(run.base, 'native_presence', return_value={'debugger_processes': []}), \
             mock.patch.object(run.os, 'add_dll_directory', return_value=Directory()), \
             mock.patch.object(run.ctypes, 'CDLL', return_value=object()), \
             mock.patch.object(run.base, 'Dap', return_value=dap), \
             mock.patch.object(run.base, 'Observation', return_value=obs), \
             mock.patch.object(run.owner, 'JournalSDK', return_value=object()), \
             mock.patch.object(run, 'execute', side_effect=execute), \
             mock.patch.object(run.mapped, 'expected', return_value=(b'h', b'p')), \
             mock.patch.object(Path, 'open', new=opened), \
             mock.patch.object(Path, 'read_bytes', return_value=b'model'), \
             mock.patch.object(store, 'write') as save:
            self.assertEqual(run.worker(store, out), 1)
        result = save.call_args.args[1]
        self.assertEqual(result['result'], 'FAILED')
        self.assertTrue(result['state']['observed'])
        self.assertEqual(obs.native_closes, 1)


if __name__ == '__main__': unittest.main()
