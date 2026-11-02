"""Actual campaign input persistence and recovery attribution, without devices."""
import hashlib
import json
import os
from pathlib import Path
import sys
import unittest
from unittest.mock import patch
import uuid

sys.path.insert(0, str(Path(__file__).resolve().parent))
import runner as r
import smoke as s
from test_campaign import plan
from test_smoke import plan as smoke_plan


class BindingTests(unittest.TestCase):
    def test_input_bytes_survive_actual_save_and_recovery_rejects_tampering(self):
        h = r.load_host()
        area = h.fresh(r.ROOT / '.cache/p35-remediation-20261101/binding' / uuid.uuid4().hex)
        p = plan()
        native = smoke_plan()
        native['device'].update(expected_version=p['firmware']['current']['version'],
                                expected_sha256=p['firmware']['current']['sha256'])
        variants = {
            'lf': (json.dumps(p, indent=2) + '\n').encode(),
            'crlf': (json.dumps(p, indent=2) + '\n').replace('\n', '\r\n').encode(),
            'compact': json.dumps(p, separators=(',', ':')).encode(),
            'indent4': (json.dumps(p, indent=4) + '\n').encode(),
        }
        for name, raw in variants.items():
            with self.subTest(format=name):
                root = h.fresh(area / name)
                config, prior = root / 'input.json', root / 'prior'
                h.raw(config, raw)
                reads = []
                original_read = Path.read_bytes

                def read(path):
                    if path == config:
                        reads.append(path)
                    return original_read(path)

                class Driver:
                    campaign = None
                    cleanup_result = dict(captureState='NOT_ARMED', armAttempts=0,
                        stopAttempts=0, ownedAppStopAttempts=0, appRestartAttempts=0)

                    def __init__(self, *args):
                        pass

                    def startup(self, **kwargs):
                        h.save(prior / 'journal/00001.json', dict(event='launch-intent'))
                        raise r.Stop('UI_UNAVAILABLE', 'synthetic pre-ARM launch failure')

                    def close(self):
                        h.save(prior / 'usb/closed.json', dict(cleanup_complete=True,
                            server_closed=True, listening=False))
                        raise r.Stop('UNRESOLVED_STATE', 'synthetic retained owner')

                cwd = Path.cwd()
                try:
                    os.chdir(root)
                    with patch.object(r, 'ROOT', root), patch.object(s, 'ROOT', root), \
                         patch.object(h, 'ROOT', root), patch.object(r, 'load_host', lambda: h), \
                         patch.object(h, 'pinned', lambda pin: config), patch.object(r, 'Android', Driver):
                        with patch.object(Path, 'read_bytes', read):
                            self.assertEqual(r.main(['run', '--plan', str(config), '--out', str(prior), '--execute']), 2)
                        self.assertEqual(reads, [config])
                        saved = prior / 'plan.json'
                        self.assertEqual(saved.read_bytes(), raw)
                        self.assertEqual(h.read_json(prior / 'inputs.json')['planSha256'], hashlib.sha256(raw).hexdigest())
                        # Only downstream device admission is substituted, not byte binding.
                        with patch.object(s, 'failed_launch_receipts') as receipts, \
                             patch.object(s, 'reconcile_file_source', return_value=73) as device:
                            self.assertEqual(s.reconcile(native, b'unused-smoke-input', prior, root / 'recovery', h), 73)
                            receipts.assert_called_once()
                            device.assert_called_once()
                            receipts.reset_mock()
                            device.reset_mock()
                            h.checked(saved).write_bytes(raw + b'\n')
                            with self.assertRaisesRegex(r.Stop, 'not a bound pre-ARM'):
                                s.reconcile(native, b'unused-smoke-input', prior, root / 'tampered', h)
                            receipts.assert_not_called()
                            device.assert_not_called()
                finally:
                    os.chdir(cwd)


if __name__ == '__main__':
    unittest.main()
