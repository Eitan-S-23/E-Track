"""P5 statistics reject incomplete transfers and report true source timing."""
import copy
from pathlib import Path
import sys
import unittest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'Tools/ota/p51-acceptance'))
import evaluate as e


class TimingTests(unittest.TestCase):
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


if __name__ == '__main__':
    unittest.main()
