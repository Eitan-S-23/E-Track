"""Original replay and synthetic negative tests; no physical operations."""
from pathlib import Path
from types import SimpleNamespace
import unittest

import runner as r
import smoke as s
from test_smoke import archive, state, unhealthy_archive

AREA = r.ROOT / '.cache/p35-native-log-20261101'


class FaultCleanupTests(unittest.TestCase):
    def driver(self, raw, live):
        d = object.__new__(s.Smoke)
        d.capture_id = live[0]['captureId']
        d.arm_attempted = d.arm_baseline_confirmed = d.stop_attempted = d.stream_failed = True
        d.capture_resolved = d.original_verified = False
        d.stop_seal_recovered = False
        d.capture_recovery_states = None
        d.previous_captures = {}
        d.live = live
        d.decoder = r.Decoder()
        d.decoder.opened = dict(schema=1, kind='open', captureId=d.capture_id)
        d.decoder.previous = live[-1]
        d.out = Path('unused-offline-output')
        d.reads, d.receipts = [], []
        def original(cid, path):
            self.assertEqual(cid, d.capture_id)
            d.reads.append(path)
            d.original_verified = True
            return raw
        d.original = original
        d.h = SimpleNamespace(save=lambda path, value: d.receipts.append((path, value)))
        return d

    def test_sealed_stop_recovery_preserves_live_failure_and_never_fills_missing_rows(self):
        rows = [state(n, monoUs=n*1000, phase='failed') for n in range(1, 5)]
        d = self.driver(archive(rows), [rows[0], rows[-1]])
        observed = list(d.live)
        d.recover_sealed_stop()
        self.assertTrue(d.capture_resolved)
        self.assertTrue(d.stop_seal_recovered)
        self.assertTrue(d.stream_failed)
        self.assertEqual(d.live, observed)
        self.assertEqual(d.capture_recovery_states, rows)
        self.assertEqual(d.capture_seal['records'], 4)
        self.assertEqual(len(d.reads), 1)

    @unittest.skipUnless((AREA / 'radio-reconcile-01/app-capture.jsonl').exists(), 'local preserved replay')
    def test_exact_original_seal_recovery_does_not_relabel_old_run_or_its_log(self):
        raw = (AREA / 'radio-reconcile-01/app-capture.jsonl').read_bytes()
        rows = s.FileCursor('958d2ab3c691edd598325c35b76ae74e').feed(raw)
        d = self.driver(raw, rows[:699])
        d.recover_sealed_stop()
        self.assertEqual(d.capture_seal['sha256'], '57215beec5240d1a543069716151ed51b49e0cab8d5d0b440c2ce27170196567')
        self.assertEqual(d.capture_seal['records'], 709)
        self.assertEqual(len(d.live), 699)
        self.assertTrue(d.stream_failed)

    def test_unknown_owner_unsealed_changed_or_apply_history_never_qualifies(self):
        row = state(phase='failed')
        raw = archive([row])
        for field in ('stop_attempted', 'arm_baseline_confirmed', 'stream_failed'):
            d = self.driver(raw, [row])
            setattr(d, field, False)
            with self.subTest(field=field), self.assertRaises(r.Stop):
                d.recover_sealed_stop()
            self.assertEqual(d.reads, [])
        for bad in (unhealthy_archive(raw), raw[:raw.rfind(b'OTA_P35_CAPTURE ')],
                    archive([dict(row, currentVersionCode=30287)]),
                    archive([dict(row, phase='applying'), dict(row, seq=2, monoUs=2000)]),
                    archive([dict(row, durable=row['packageBytes']), dict(row, seq=2, monoUs=2000)])):
            d = self.driver(bad, [row])
            with self.subTest(raw=bad[-80:]), self.assertRaises(r.Stop):
                d.recover_sealed_stop()
            self.assertFalse(d.stop_seal_recovered)


if __name__ == '__main__':
    unittest.main()
