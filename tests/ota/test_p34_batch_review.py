"""Reconnect duration accounting must not merge independent clock origins."""
import io
import json
from pathlib import Path
import sys
import unittest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'Tools/ota'))
import p34_batch_review as f


def fixture():
    attempts = [dict(n=1,outcome='no_verdict'), dict(n=2,outcome='completed')]
    rows = [dict(label='probe', attempt=i+1, phases={'probe_attempt':[100,100+duration]},
        attempts=[attempts[i]], bind={}, getInfo={}) for i,duration in enumerate((2000000,3000000))]
    rows.append(dict(label='probe',attempt=None,phases={'reconnect':[7,6000007]},attempts=attempts))
    return rows


class Tests(unittest.TestCase):
    def parse(self, rows):
        return f.probes('\n'.join('OTA_LINK_STATS '+json.dumps(x) for x in rows))

    def test_duration_sum_not_absolute_origins(self):
        value = self.parse(fixture())
        self.assertEqual(value['seconds'], 6)
        self.assertEqual(value['outside_attempts_seconds'], 1)

    def test_missing_or_duplicate_attempt(self):
        rows = fixture()
        for bad in (rows[1:], rows[:1]+rows):
            with self.assertRaises(RuntimeError): self.parse(bad)

    def test_negative_residual(self):
        rows = fixture()
        rows[-1]['phases']['reconnect'][1] = 4000007
        with self.assertRaises(RuntimeError): self.parse(rows)

    def test_unfinished_or_mismatched_outcome(self):
        rows = fixture()
        rows[-1]['attempts'] = []
        with self.assertRaises(RuntimeError): self.parse(rows)


if __name__ == '__main__':
    s = f.cli.Store(ROOT)
    out = f.trial.AREA / 'review-tests-001'
    f.cli.require(not out.exists(), 'preserve tests')
    stream = io.StringIO()
    result = unittest.TextTestRunner(stream=stream,verbosity=2).run(unittest.defaultTestLoader.loadTestsFromTestCase(Tests))
    s.raw(out / 'tests.log',stream.getvalue().encode())
    s.write(out / 'result.json',dict(result='PASS' if result.wasSuccessful() else 'FAIL',tests=result.testsRun,
        source=f.cli.record(f.__file__),test=f.cli.record(__file__),hardware=False))
    print(stream.getvalue())
    sys.exit(not result.wasSuccessful())
