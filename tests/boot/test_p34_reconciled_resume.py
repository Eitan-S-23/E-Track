import copy
from pathlib import Path
import sys
import unittest
from unittest import mock

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT/'Tools/ota'))
import p34_reconciled_resume as r


class SuccessorTests(unittest.TestCase):
    def setUp(self): self.store = r.cli.Store(ROOT)

    def test_actual_reconciliation_keeps_historical_gap(self):
        records = r.reconciliation_gate(self.store)
        self.assertTrue(any(x['path'].endswith('failure.json') for x in records))

    def test_historical_gap_cannot_be_renamed_pass(self):
        value = self.store.read(r.RECONCILIATION)
        value['historical_sdk_audit_passed'] = True
        with mock.patch.object(self.store, 'read', return_value=value):
            with self.assertRaises(RuntimeError): r.reconciliation_gate(self.store)

    def test_missing_sequence_rejected(self):
        value = self.store.read(r.RECONCILIATION)
        value['journal']['settled_mutations'] -= 1
        with mock.patch.object(self.store, 'read', return_value=value):
            with self.assertRaises(RuntimeError): r.reconciliation_gate(self.store)

    def test_missing_original_sdk_binding_rejected(self):
        value = self.store.read(r.RECONCILIATION)
        value['evidence'] = [x for x in value['evidence'] if not x['path'].endswith('sdk.log')]
        with mock.patch.object(self.store, 'read', return_value=value):
            with self.assertRaises(RuntimeError): r.reconciliation_gate(self.store)

    def test_record_drift_rejected(self):
        record = r.cli.record(r.SELF); record['sha256'] = '0'*64
        with self.assertRaises(RuntimeError): r.verify_records(self.store, [record])

    def test_old_complete_sdk_gate_does_not_accept_reconciliation(self):
        with self.assertRaises((RuntimeError, KeyError)):
            r.prior.recovery_inputs(self.store, r.RECONCILIATION)

    def test_native_entry_unreachable_on_eligibility_failure(self):
        out = ROOT/'.cache/mock-reconciled-resume'
        plan = dict(inputs=[r.cli.record(p) for p in r.SOURCES], out=str(out), route='RESUME-23-RECONCILED',
                    historical_sdk_audit_passed=False, evidence=[])
        with mock.patch.object(r.base, 'in_job', return_value=True), \
             mock.patch.object(self.store, 'read', return_value=plan), \
             mock.patch.object(r, 'eligibility', side_effect=RuntimeError('evidence gap')), \
             mock.patch.object(r.prior, 'native_worker') as native:
            with self.assertRaises(RuntimeError): r.worker(self.store, out)
            native.assert_not_called()

    def test_changed_status_context_rejected_before_sdk_gate(self):
        directory = ROOT/'.cache/p34-host-nor-status1'
        values = {n: self.store.read(directory/(n+'.json')) for n in ('worker', 'parent', 'plan')}
        values['plan']['out'] = str(r.STATUS)
        values['parent']['started'] = '2026-10-05T23:00:00+00:00'
        values['worker']['before']['context']['pc'] ^= 2
        original = self.store.read
        def read(path):
            path = Path(path)
            return copy.deepcopy(values[path.stem]) if path.parent == r.STATUS else original(path)
        with mock.patch.object(self.store, 'read', side_effect=read):
            with self.assertRaisesRegex(RuntimeError, 'context drift'): r.status_gate(self.store)

    def test_actual_fresh_status_identity(self):
        worker, records = r.status_gate(self.store)
        self.assertEqual(worker['status']['samples'], [dict(sr1=0, sr2=2, jedec='ef4018')]*2)
        self.assertTrue(any(x['path'].endswith('sdk.log') for x in records))

    def test_changed_current_status_rejected(self):
        original = self.store.read
        def read(path):
            value = original(path)
            if Path(path) == r.STATUS/'worker.json': value['status']['samples'][0]['sr1'] = 4
            return value
        with mock.patch.object(self.store, 'read', side_effect=read):
            with self.assertRaisesRegex(RuntimeError, 'status changed'): r.status_gate(self.store)

    def test_hashing_budget_exhaustion_never_opens_native_probe(self):
        out = ROOT/'.cache/mock-reconciled-resume'
        plan = dict(inputs=[r.cli.record(p) for p in r.SOURCES], out=str(out), route='RESUME-23-RECONCILED',
                    historical_sdk_audit_passed=False, evidence=[])
        with mock.patch.object(r.base, 'in_job', return_value=True), \
             mock.patch.object(self.store, 'read', return_value=plan), \
             mock.patch.object(r, 'eligibility', return_value=[]), \
             mock.patch.object(r.time, 'monotonic', side_effect=[0, 46]), \
             mock.patch.object(r.prior, 'native_worker') as native:
            with self.assertRaisesRegex(RuntimeError, 'headroom'): r.worker(self.store, out)
            native.assert_not_called()


if __name__ == '__main__': unittest.main()
