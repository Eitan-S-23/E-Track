from pathlib import Path
import sys
from types import SimpleNamespace
import unittest
from unittest import mock

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT/'Tools/ota'))
sys.path.insert(0, str(ROOT/'tests/boot'))
import p34_r2_backup_byte_device as run
import test_p34_r2_backup_device as old_tests
import test_p34_r2_mapped_backup as component_tests


class DisplayNative(old_tests.fixture.Native):
    def __getattr__(self, name):
        if name == 'JLINKARM_OpenEx':
            m = run.mapped
            self.memory.update({m.DMA['dma1_3']: 0x1093, m.DMA['dma2_4']: 0x2a81,
                m.ENDPOINTS['display_peripheral']: 0x4001300c, m.ENDPOINTS['display_memory']: 0x200145df,
                m.ENDPOINTS['sd_peripheral']: 0x50061080, m.ENDPOINTS['sd_memory']: 0x20052e10})
        return super().__getattr__(name)


session = run.byte.bind(old_tests.session, run=run,
    fixture=SimpleNamespace(**dict(vars(old_tests.fixture), Native=DisplayNative)))


class Tests(unittest.TestCase):
    make_plan = old_tests.Tests.make_plan
    test_worker_admission_before_native = run.byte.bind(
        old_tests.Tests.test_bad_job_plan_tests_or_proof_reject_before_dll_or_output, run=run)
    test_late_outer_failure_single_close = run.byte.bind(
        old_tests.Tests.test_late_outer_failure_never_masks_failure_or_recloses_native, run=run)

    def test_actual_odd_display_full_capture_and_unchanged_frozen_globals(self):
        snapshot = run.prior.mapped.Capture.snapshot
        execute = run.prior.execute
        value, rows, paths, native, saved = session()
        self.assertEqual(value['result'], 'R2_BACKUP_MAPPED_NATIVE_CLOSED', value)
        self.assertEqual(len(saved['backup-payload']), 617588)
        old_tests.fixture.Tests().assert_close_only(native)
        trace = run.audit_trace(paths, rows, value['dap'], old_tests.fixture.record, True)
        self.assertEqual(trace['logs'], value['logs'])
        guards = [r for r in rows if r['event'] == 'r2-mapped-backup-guard']
        self.assertTrue(guards)
        self.assertTrue(all(r['endpoints']['display_memory'] == 0x200145df for r in guards))
        self.assertIs(run.prior.mapped.Capture.snapshot, snapshot)
        self.assertIs(run.prior.execute, execute)

    def test_display_byte_only_word_sd_qspi_and_master_guards_retained(self):
        probe, _, _, _, _ = component_tests.Tests().make()
        probe.active = True
        row = run.mapped.passive.Probe.sample(probe)
        view = probe.view.locate()
        dma = {k: 0 for k in run.mapped.DMA}
        dma.update(dma1_3=0x1093, dma2_4=0x2a81)
        ends = dict(display_peripheral=0x4001300c, display_memory=0x200145df,
                    sd_peripheral=0x50061080, sd_memory=0x20052e10)
        for address in (0x20000000, 0x200145df, 0x20057fff):
            self.assertEqual(run.byte.qualify(row, view, dma, dict(ends, display_memory=address)), 0)
        for key, value in (('display_memory', 0x1fffffff), ('display_memory', 0x20058000),
                           ('display_memory', 0x90100000), ('sd_memory', 0x20052e11),
                           ('display_peripheral', 0xa0001100)):
            with self.assertRaises(ValueError): run.byte.qualify(row, view, dma, dict(ends, **{key: value}))
        for key, value in (('dma1_3', 0x1091), ('dma2_4', 0x1093), ('edma_1', 1)):
            with self.assertRaises(ValueError): run.byte.qualify(row, view, dict(dma, **{key: value}), ends)
        changed = dict(row, qspi=dict(row['qspi'], qspi_xip3=8))
        with self.assertRaises(ValueError): run.byte.qualify(changed, view, dma, ends)
        with self.assertRaises(ValueError): run.prior.mapped.qualify(row, view, dma, ends)

    def test_only_reconciled_failed_prefix_is_successor_predecessor(self):
        s = run.cli.Store(ROOT)
        proof = run.predecessor(s)
        self.assertFalse(proof['repeat_successful_nor_capture'])
        self.assertEqual(proof['failed_prefix_review']['sha256'], run.REVIEW_SHA)
        original = run.cli.record
        def corrupt(path):
            value = original(path)
            return dict(value, sha256='0'*64) if Path(path) == run.FAILED/'worker.json' else value
        with mock.patch.object(run.cli, 'record', side_effect=corrupt):
            with self.assertRaisesRegex(RuntimeError, 'failed-prefix evidence'): run.predecessor(s)


if __name__ == '__main__': unittest.main()
