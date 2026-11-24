import io
import json
from pathlib import Path
import sys
import unittest
from unittest import mock

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT/'Tools/ota'))
import p34_nor_reconcile as r


class ReconcileTests(unittest.TestCase):
    def setUp(self):
        self.source = (ROOT/'.cache/p34-recovery-sources1/r2-a.bin').read_bytes()

    def rows(self): return r.audit.events(r.AREA/'events.jsonl')

    def changed(self, name, change):
        applied = False
        for e in self.rows():
            if not applied and e['event'] == name:
                applied = True
                e = change(dict(e))
                if e is None: continue
            yield e
        self.assertTrue(applied)

    def test_complete_actual_host_journal(self):
        result = r.journal(self.rows(), self.source)
        self.assertEqual(result['mutation_commands'], 2576)
        self.assertEqual(result['settled_mutations'], 2576)
        self.assertEqual(result['tx_payload_bytes'], 619612)

    def test_missing_write_return_rejected(self):
        with self.assertRaises(RuntimeError):
            r.journal(self.changed('debug-write-returned', lambda e: None), self.source)

    def test_tx_word_corruption_rejected(self):
        with self.assertRaises(RuntimeError):
            r.journal(self.changed('nor-tx-word', lambda e: dict(e, value=e['value']^1)), self.source)

    def test_missing_settlement_rejected(self):
        with self.assertRaises(RuntimeError):
            r.journal(self.changed('nor-mutation-settled', lambda e: None), self.source)

    def test_out_of_bound_settlement_time_rejected(self):
        with self.assertRaises(RuntimeError):
            r.journal(self.changed('nor-mutation-settled', lambda e: dict(e, elapsed_seconds=3)), self.source)

    def test_actual_archives_and_bcb_reconstruction(self):
        worker = json.loads((r.AREA/'worker.json').read_text())
        result = r.audit.physical_files(r.AREA, worker)
        self.assertEqual(result['nor_archives'], 8)
        self.assertEqual(len(result['bcb_traces']), 2)

    def test_archive_drift_rejected(self):
        worker = json.loads((r.AREA/'worker.json').read_text())
        record = r.cli.record
        def changed(path):
            value = record(path)
            return dict(value, sha256='0'*64) if Path(path).name == 'before-candidate-backup.bin' else value
        with mock.patch.object(r.cli, 'record', side_effect=changed):
            with self.assertRaises(RuntimeError): r.audit.physical_files(r.AREA, worker)

    def test_truncated_fresh_sdk_remains_rejected(self):
        area = ROOT/'.cache/p34-host-nor-status1'
        worker = json.loads((area/'worker.json').read_text())
        original = Path.open
        text = (area/'sdk.log').read_text()
        with mock.patch.object(Path, 'open', lambda p, *a, **kw:
                               io.StringIO(text[:len(text)//2]) if p == area/'sdk.log' else original(p, *a, **kw)):
            with self.assertRaises(RuntimeError): r.audit.trace(area, worker)


if __name__ == '__main__': unittest.main()
