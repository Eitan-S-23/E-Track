"""Run existing acceptance regressions plus the supplemental oracles."""
from pathlib import Path
import sys
import unittest

ROOT = Path(__file__).resolve().parents[2]
assert Path.cwd() == ROOT and sys.flags.isolated and sys.flags.no_site and sys.dont_write_bytecode
sys.path.insert(0, str(ROOT/'tests/ota'))
suite = unittest.defaultTestLoader.loadTestsFromNames([
    'test_acceptance_bundle', 'test_acceptance_efficiency', 'test_p17_observe',
    'test_p17_review', 'test_p17_supplement'])
result = unittest.TextTestRunner(verbosity=2).run(suite)
raise SystemExit(0 if result.wasSuccessful() else 1)
