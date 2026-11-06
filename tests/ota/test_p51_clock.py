"""Existing soak clock retains real time and seals the final observed action."""
import json
import os
from pathlib import Path
import sys
import tempfile
import threading
import time
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'Tools/ota/p34-acceptance'))
import live
h = live.h
sys.path.insert(0, str(ROOT / 'Tools/ota/p51-acceptance'))
import run as p5


class SoakClockTests(unittest.TestCase):
    def setUp(self):
        parent = h.checked(Path(os.environ['P51_CLOCK_TEST_OUT']))
        parent.mkdir(parents=True, exist_ok=True)
        self.temp = tempfile.TemporaryDirectory(dir=parent)
        self.addCleanup(self.temp.cleanup)
        self.root = h.checked(Path(self.temp.name))
        self.out = h.fresh(self.root / 'clock')

    def test_legacy_fixed_duration_is_preserved(self):
        live.soak_clock(self.out, self.root, 1)
        result = h.read_json(self.out / 'clock-result.json')
        self.assertGreaterEqual(result['elapsed_seconds'], 1)
        self.assertFalse(result['independent_acceptance'])

    def test_owned_stop_preserves_last_result_and_actual_duration(self):
        stop, errors = threading.Event(), []
        def run():
            try:
                live.soak_clock(self.out, self.root, 30, stop_event=stop)
            except BaseException as error:
                errors.append(error)
        thread = threading.Thread(target=run)
        thread.start()
        try:
            h.wait_for(lambda: (self.out / 'monotonic.jsonl').exists(), 5)
            result_path = self.root / 'block-01/result.json'
            h.save(result_path, dict(observed=True))
        finally:
            stop.set()
            thread.join(timeout=5)
        self.assertFalse(thread.is_alive())
        self.assertEqual(errors, [])
        result = h.read_json(self.out / 'clock-result.json')
        self.assertEqual(result['observed_actions'], 1)
        rows = [json.loads(line) for line in (self.out / 'monotonic.jsonl').read_text().splitlines()]
        self.assertEqual(rows[-1]['kind'], 'stop')
        self.assertEqual(next(row['original'] for row in rows if row['kind'] == 'action_observed'), h.record(result_path))

    def test_campaign_has_finite_blocks_and_does_not_replay_failure(self):
        campaign = h.fresh(self.root / 'campaign')
        plan = dict(phone=dict(limits=dict(total_seconds=5400)), mcu=dict(package={}))
        def failed(*args):
            raise RuntimeError('synthetic transfer failure')
        with patch.object(p5, 'ble_block', side_effect=failed) as block, self.assertRaisesRegex(RuntimeError, 'synthetic'):
            p5.long_campaign(plan, campaign)
        self.assertEqual(block.call_count, 1)
        rows = [json.loads(line) for line in (campaign / 'clock/monotonic.jsonl').read_text().splitlines()]
        self.assertEqual(rows[-1]['kind'], 'stop')

    def test_campaign_stops_when_declared_count_and_span_are_both_met(self):
        campaign = h.fresh(self.root / 'campaign')
        plan = dict(phone=dict(limits=dict(total_seconds=5400)), mcu=dict(package={}))
        def observed(p, folder, count):
            self.assertEqual(count, 8)
            h.save(folder / 'cell-08/intent.json', dict(hostMonoNs=14401_000_000_000))
            value = dict(cells=[dict(beginObservedMonoNs=1_000_000_000)]*8)
            h.save(folder / 'result.json', value)
            return value
        with patch.object(p5, 'ble_block', side_effect=observed) as block:
            p5.long_campaign(plan, campaign)
        self.assertEqual(block.call_count, 4)
        self.assertEqual(h.read_json(campaign / 'result.json')['attempts'], 32)


if __name__ == '__main__':
    unittest.main()
