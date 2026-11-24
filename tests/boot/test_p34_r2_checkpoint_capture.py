import copy
import io
from pathlib import Path
import sys
import unittest
from types import SimpleNamespace
from unittest import mock

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'Tools/ota'))
import p34_r2_checkpoint_capture as run


class Tests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.store = run.cli.Store(ROOT)
        cls.records = [cls.store.read(run.REVIEW), cls.store.read(run.AUDIT),
            *(cls.store.read(run.RECOVERY / (n + '.json')) for n in ('worker', 'parent', 'plan'))]

    def test_original_independent_receipts_admit_recovery_not_an_ota(self):
        run.validate_predecessor(*self.records)
        review = self.records[0]
        self.assertFalse(review['recovery_establishes_r2_backup'])
        self.assertFalse(review['eeprom']['after_boot_physical_pair_observed'])
        self.assertEqual(review['eeprom']['final_a']['backup_version'], 30274)

    def test_incomplete_uncertain_wrong_identity_and_relabeled_evidence_reject(self):
        changes = (
            (0, ('runtime_health_independently_reconciled',), False),
            (0, ('runtime_health', 'original_sdk_bound'), False),
            (0, ('continuation', 'image_version'), 30277),
            (0, ('continuation', 'image_sha256'), '0' * 64),
            (0, ('historical_sdk_audit_passed',), True),
            (0, ('recovery_establishes_r2_backup',), True),
            (0, ('original_logs',), []),
            (0, ('reviewed_source_inputs',), []),
            (1, ('terminal_idle_checked',), False),
            (2, ('result',), 'FAILED'),
            (2, ('close_returned',), False),
            (2, ('sources_unchanged_after_close',), False),
            (2, ('dap', 'dp_restored'), False),
            (2, ('final_trace', 'native_close_completed'), 0),
            (3, ('timeout',), True),
            (3, ('presence_after', 'debugger_processes'), ['competing']),
        )
        for index, keys, value in changes:
            with self.subTest(keys=keys):
                changed = copy.deepcopy(self.records)
                target = changed[index]
                for key in keys[:-1]: target = target[key]
                target[keys[-1]] = value
                with self.assertRaises(RuntimeError): run.validate_predecessor(*changed)

    def test_predecessor_checks_original_bytes_before_returning_a_proof(self):
        records = copy.deepcopy(self.records)
        review = records[0]
        review['root_receipt_crosscheck'] = run.cli.record(run.AUDIT)
        paths = (run.REVIEW, run.AUDIT,
                 *(run.RECOVERY / (n + '.json') for n in ('worker', 'parent', 'plan')))
        values = dict(zip(paths, records))
        first = records[1]['inputs'][0]
        with mock.patch.object(self.store, 'read', side_effect=lambda p: values[Path(p)]), \
             mock.patch.object(run.evidence, 'record', return_value=dict(first, sha256='0' * 64)) as read:
            with self.assertRaisesRegex(RuntimeError, 'original recovery evidence changed'):
                run.predecessor(self.store)
        self.assertEqual(read.call_count, 1)

    def test_worker_requires_owned_job_before_plan_or_native_access(self):
        with mock.patch.object(run.base, 'in_job', return_value=False), \
             mock.patch.object(self.store, 'read', side_effect=AssertionError('read before admission')), \
             mock.patch.object(run.ctypes, 'CDLL', side_effect=AssertionError('native load before admission')):
            with self.assertRaisesRegex(RuntimeError, 'owned read-only checkpoint worker'):
                run.worker(self.store, ROOT / '.cache/unused-checkpoint-model')

    def worker_plan_fixture(self):
        out = ROOT / '.cache/unused-checkpoint-model'
        current = [dict(path='model-input', bytes=1, sha256='a' * 64)]
        test_path = ROOT / '.cache/model-tests/result.json'
        test_record = dict(path=str(test_path), bytes=1, sha256='b' * 64)
        review = self.records[0]
        proof = dict(kind='CLOSED_RECOVERY_R2A', review=run.cli.record(run.REVIEW),
            audit=run.cli.record(run.AUDIT), worker=run.cli.record(run.RECOVERY / 'worker.json'),
            parent=run.cli.record(run.RECOVERY / 'parent.json'), version=30276,
            image_sha256=review['continuation']['image_sha256'], historical_ota_predecessor=False)
        plan = dict(out=str(out), scope=run.SCOPE, inputs=current, tests=test_record, predecessor=proof,
            worker_seconds=900, parent_seconds=1020, connection_generation='r2-checkpoint-' + out.name,
            before_history=[], native_history_approved=str(run.base.HISTORY))
        tested = dict(result='R2_CHECKPOINT_CAPTURE_HOST_PASS', inputs=current, hardware=False)
        return out, current, test_path, test_record, plan, tested

    def test_worker_rejects_missing_stale_tests_predecessor_and_deadlines_before_native_load(self):
        out, current, test_path, test_record, original, tested = self.worker_plan_fixture()
        saved_record, saved_read = run.cli.record, self.store.read
        def record(path): return test_record if Path(path) == test_path else saved_record(path)
        plan = original
        def read(path):
            if Path(path) == out / 'plan.json': return plan
            if Path(path) == test_path: return tested
            return saved_read(path)
        with mock.patch.object(run.base, 'history', return_value=[]), \
             mock.patch.object(run.cli, 'record', side_effect=record), \
             mock.patch.object(self.store, 'read', side_effect=read), \
             mock.patch.object(run.base, 'in_job', return_value=True), \
             mock.patch.object(run, 'sources', return_value=[]), \
             mock.patch.object(run.ctypes, 'CDLL') as load:
            run.validate_worker_plan(self.store, original, out, current)
            # Drive the actual worker for every rejection, before output opens.
            plan = dict(original, inputs=[])
            tested['inputs'] = []
            for path, wrong in ((('tests',), None), (('tests', 'sha256'), '0' * 64),
                (('predecessor', 'kind'), None), (('predecessor', 'version'), 30277),
                (('predecessor', 'image_sha256'), '0' * 64), (('predecessor', 'worker'), {}),
                (('predecessor', 'parent'), {}), (('connection_generation',), None),
                (('worker_seconds',), 901), (('parent_seconds',), 999), (('before_history',), ['changed'])):
                plan = copy.deepcopy(dict(original, inputs=[]))
                target = plan
                for key in path[:-1]: target = target[key]
                if wrong is None: target.pop(path[-1])
                else: target[path[-1]] = wrong
                with self.subTest(path=path), self.assertRaises((RuntimeError, KeyError)):
                    run.worker(self.store, out)
            plan = dict(original, inputs=[])
            tested['inputs'] = current
            with self.assertRaisesRegex(RuntimeError, 'current capture selftests'):
                run.worker(self.store, out)
            load.assert_not_called()

    def test_late_outer_failure_preserves_close_but_returns_failure_without_native_reclose(self):
        out, _, _, _, plan, _ = self.worker_plan_fixture()
        plan['inputs'] = []
        dap = SimpleNamespace(_opened=True, close_returned=True)
        class Observation:
            closed = False
            native_closes = 0
            def close(self):
                if not self.closed:
                    self.closed = True
                    self.native_closes += 1
        observation = Observation()
        class Directory:
            def __enter__(self): return self
            def __exit__(self, *args): raise OSError('late directory close failure')
        def execute(*args, **kwargs):
            observation.close()
            return dict(result='R2_CHECKPOINT_NATIVE_CLOSED', close_returned=True, checkpoint={'observed': True})
        def opened(path, mode='r', **kwargs):
            self.assertEqual(path.parent, out)
            return io.BytesIO() if 'b' in mode else io.StringIO()
        with mock.patch.object(run.base, 'in_job', return_value=True), \
             mock.patch.object(self.store, 'read', return_value=plan), \
             mock.patch.object(run, 'sources', return_value=[]), \
             mock.patch.object(run, 'validate_worker_plan'), \
             mock.patch.object(run.cli, 'record', return_value={'sha256': run.base.DLL_SHA}), \
             mock.patch.object(run.base, 'native_presence', return_value={'debugger_processes': []}), \
             mock.patch.object(run.os, 'add_dll_directory', return_value=Directory()), \
             mock.patch.object(run.ctypes, 'CDLL', return_value=object()), \
             mock.patch.object(run.base, 'Dap', return_value=dap), \
             mock.patch.object(run.base, 'Observation', return_value=observation), \
             mock.patch.object(run.owner, 'JournalSDK', return_value=object()), \
             mock.patch.object(run.owner, 'execute', side_effect=execute), \
             mock.patch.object(Path, 'open', new=opened), \
             mock.patch.object(Path, 'read_bytes', return_value=b'model'), \
             mock.patch.object(self.store, 'write') as save:
            self.assertEqual(run.worker(self.store, out), 1)
        result = save.call_args.args[1]
        self.assertEqual(result['result'], 'FAILED')
        self.assertTrue(result['close_returned'])
        self.assertTrue(result['checkpoint']['observed'])
        self.assertIn('late directory close failure', result['outer_error'])
        self.assertEqual(observation.native_closes, 1)

    def test_selftest_inputs_are_current_and_output_preflight_rejects_existing_area(self):
        self.assertIn(run.REVIEW, run.sources(self.store))
        self.assertIn(run.SELF, run.sources(self.store))
        with self.assertRaisesRegex(RuntimeError, 'preserve'):
            run.owner.preflight(self.store, run.RECOVERY, run.sources(self.store))


if __name__ == '__main__':
    unittest.main()
