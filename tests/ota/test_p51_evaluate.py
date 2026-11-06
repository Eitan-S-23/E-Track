"""P5 statistics reject incomplete transfers and report true source timing."""
import copy
from pathlib import Path
import sys
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'Tools/ota/p51-acceptance'))
import evaluate as e


class TimingTests(unittest.TestCase):
    def test_single_original_cell_mode_never_runs_other_cells_or_long_group(self):
        argv = ['evaluate.py', '--cell', '.cache/prior-cell', '--inputs', '.cache/inputs.json', '--out', '.cache/not-created']
        for failure in (False, True):
            observed = dict(states=[4, 1, 3, 4], rawImageVerified=True)
            with patch.object(sys, 'argv', argv), patch.object(e.h, 'read_json', return_value={}), \
                    patch.object(e.run, 'validate', return_value={'bound': True}), \
                    patch.object(e.h, 'fresh', return_value=ROOT / '.cache/not-created'), patch.object(e.h, 'save') as save, \
                    patch.object(e, 'four_cell', return_value=observed,
                        side_effect=RuntimeError('missing original') if failure else None) as cell, \
                    patch.object(e, 'long_group') as long_group:
                if failure:
                    with self.assertRaisesRegex(RuntimeError, 'missing original'):
                        e.main()
                    self.assertEqual(save.call_args.args[0].name, 'failed.json')
                else:
                    e.main()
                    self.assertEqual(save.call_args.args[1], dict(outcome='CELL_ORIGINALS_VERIFIED', cell=observed, deviceOperations=0))
                cell.assert_called_once_with(ROOT / '.cache/prior-cell', {'bound': True})
                long_group.assert_not_called()

    def group(self):
        return dict(label='upgrade', clockId='original:1', ackLatencyUs=[100, 200], summary=dict(
            bind=dict(writeMode='withoutResponse', mtuChunkBytes=244), transfer=dict(outcome='ok',
                elapsedUs=100000000, startUs=100, endAckUs=100000100,
                begin=dict(count=1, first=dict(off=0, bitmap=0, protocol=2, ackTimeoutMs=500,
                    maxRetries=5, windowSegments=32)), durable=dict(finalOff=1048576),
                ackSamples='complete', ackEarlyInvalid=0, segmentsUnique=2, retransmitFrames=0)))

    def test_uses_reference_bytes_and_same_source_clock(self):
        value = e.transfer(self.group(), 1048576)
        self.assertEqual(value['throughputKiBps'], 10.24)
        self.assertEqual(value['elapsedUs'], 100000000)
        self.assertEqual(value['sourceClock'], 'original:1')

    def test_no_credit_for_partial_timing_or_nonzero_start(self):
        for field, value in (('elapsedUs', 0), ('outcome', 'fail'), ('ackSamples', 'partial:missing=1'),
                             ('ackEarlyInvalid', 1), ('segmentsUnique', 3)):
            group = self.group()
            group['summary']['transfer'][field] = value
            with self.subTest(field=field), self.assertRaises(RuntimeError):
                e.transfer(group, 1048576)
        group = self.group()
        group['summary']['transfer']['begin']['first']['off'] = 4096
        with self.assertRaises(RuntimeError):
            e.transfer(group, 1048576)

    def test_package_must_be_really_committed(self):
        fw = dict(package=dict(bytes=1048576), target=dict(version=30319))
        journal = dict(matches_reference=True, durable=1048576, committed_target=30319)
        e.run.final_storage(dict(storage=dict(journal=journal)), fw)
        for field, value in (('matches_reference', False), ('durable', 4096), ('committed_target', 30318)):
            with self.subTest(field=field), self.assertRaises(RuntimeError):
                e.run.final_storage(dict(storage=dict(journal=dict(journal, **{field: value}))), fw)

    def test_soak_excludes_outer_setup_and_observation_delay(self):
        self.assertEqual(e.conservative_span([(1, 1000000001, 2000000001),
            (11000000001, 12000000001, 13000000001)]), 10)
        self.assertEqual(e.conservative_span([(1, 100, 200)]), 0)
        for intervals in ([], [(3, 2, 4)], [(1, 2, 9), (8, 10, 11)]):
            with self.assertRaises(RuntimeError):
                e.conservative_span(intervals)


if __name__ == '__main__':
    unittest.main()
