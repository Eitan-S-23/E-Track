"""Read-only original-evidence and tampering controls for P1-7."""
from pathlib import Path
import subprocess
import sys
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'Tools/acceptance'))
import p17_review as r


def read(name):
    if name == 'contract.json':
        return (ROOT / 'docs/acceptance-contracts/P1-7-v1.contract.json').read_bytes()
    return (ROOT / 'docs/acceptance-contracts/P1-7-v1' / name).read_bytes()


class Tests(unittest.TestCase):
    def test_isolated_cli_entry(self):
        result = subprocess.run([sys.executable, '-I', '-S', '-B', '-X', 'utf8',
            str(ROOT/'Tools/acceptance/p17_review.py'), '--help'], cwd=ROOT,
            capture_output=True, timeout=15, check=False)
        self.assertEqual(result.returncode, 0, result.stderr.decode())
        self.assertIn(b'--bundle', result.stdout)

    def test_actual_originals_without_device_access(self):
        with patch.object(r.p.live_mcu, 'MCU', side_effect=AssertionError('device forbidden')):
            result = r.evaluate(read)
        self.assertEqual(result['overallResult'], 'EVIDENCE_GAP')
        self.assertEqual(list(result['criteria'].values()).count('PASS'), 3)
        self.assertEqual(result['criteria']['C_RECOVERY_KEY'], 'NOT_OBSERVED')
        self.assertEqual(result['criteria']['C_BATTERY'], 'NOT_OBSERVED')
        self.assertLessEqual(result['observed']['startup']['upper_ms'], 1500)
        self.assertGreater(result['observed']['startup']['reset_inclusive_upper_ms'], 1500)
        self.assertEqual(result['originalOutcome'], 'HARNESS_FAIL')
        self.assertEqual(result['bootExecutableBytes'], 14800)

    def test_modified_originals_rejected(self):
        names = ('contract.json', 'final-matrix.json', 'inputs/plan.json', 'inputs/boot-executable.bin',
                 'observation/native/0003-startup-samples/sdk.log',
                 'observation/native/0005-after/app.bin',
                 'observation/native/0005-after/commander.closed.json')
        for target in names:
            with self.subTest(target=target), self.assertRaisesRegex(RuntimeError, 'hash mismatch'):
                r.evaluate(lambda name: read(name) + (b' ' if name == target else b''))

    def test_missing_original_rejected(self):
        def missing(name):
            if name.endswith('0005-after/app.bin'):
                raise FileNotFoundError(name)
            return read(name)
        with self.assertRaises(FileNotFoundError):
            r.evaluate(missing)

    def test_path_escape_rejected(self):
        for name in ('../outside', '/absolute', 'D:/outside', 'a/../b', 'a\\b', 'a//b'):
            with self.subTest(name=name), self.assertRaises(RuntimeError):
                r.safe_relative(name)


if __name__ == '__main__':
    unittest.main()
