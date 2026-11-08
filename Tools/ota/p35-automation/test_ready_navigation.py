"""Offline replay of the original success-snackbar/ready cleanup failure."""
from collections import deque
import copy
from pathlib import Path
from types import SimpleNamespace
import time
import unittest

import runner as r
import smoke as s
from test_runner import plan, state, xml, node
from test_smoke import archive, unhealthy_archive

PKG = 'com.wen.gaia.gaia.p35acceptance'
ORIGINAL = r.ROOT / '.cache/p35-native-log-20261101/pipeline-live-01/device/usb/adb-00182.stdout'
SEALED_READY = r.ROOT / '.cache/p35-native-log-20261101/reconcile-ready-01/app-capture.jsonl'


def original_or_fixture():
    if ORIGINAL.is_file():
        return ORIGINAL.read_bytes()
    return xml(node(package=PKG, **{'content-desc': s.FIRMWARE}) +
        node(package=PKG, **{'class': 'android.widget.ScrollView', 'scrollable': 'true',
            'clickable': 'false', 'bounds': '[0,264][1080,2298]'}) +
        node(package=PKG, **{'class': 'android.view.View', 'scrollable': 'true',
            'clickable': 'false', 'content-desc': '\u6210\u529f: fixture', 'bounds': '[0,2154][1080,2298]'}) +
        node(package=PKG, **{'resource-id': 'p35-reconnect'}))


class ReadyNavigationTests(unittest.TestCase):
    def old_ready(self, raw, *, pid=b'', home=False, busy=False, changed=False):
        d = object.__new__(s.Smoke)
        d.p = {'app': {'id': PKG}}
        d.out = Path('unused-offline-output')
        d.previous_captures = {}
        d.pid = None
        d.ui = lambda: xml(node(package=PKG, **{'content-desc': '\u8bbe\u5907\u4e2d\u5fc3'}) +
            node(package=PKG, **s.HOME)) if home else xml(node(package=PKG, **{'resource-id': 'p35-start'}))
        def idle():
            r.require(not busy, 'active OTA service', 'DEVICE_BUSY')
        d.idle_services = idle
        d.foreground_existing = lambda current: self.assertEqual(current, pid.decode())
        d.record = lambda *args, **kwargs: None
        cid = r.Decoder().feed(raw)[0]['captureId']
        d.capture_names = lambda: {cid}
        d.original = lambda capture, destination: raw
        commands = []
        def cmd(args, **kwargs):
            commands.append(args)
            self.assertEqual(args, ['shell', 'pidof', PKG])
            return b'5678' if changed and len(commands) > 1 else pid
        d.cmd = cmd
        d.old_captures()
        return d.previous_captures[cid], commands

    @unittest.skipUnless(SEALED_READY.is_file(), 'preserved reconciled original is local')
    def test_exact_sealed_ready_original_admitted_only_with_absent_app(self):
        raw = SEALED_READY.read_bytes()
        report, commands = self.old_ready(raw)
        self.assertEqual(report['sha256'], '3804a30b1294d7c16e05e7af933394ad2a2670c79d548cadb7917dbda7a24793')
        self.assertEqual(report['final']['phase'], 'readyToInstall')
        self.assertEqual(len(commands), 1)

    def test_old_ready_requires_healthy_entire_prebegin_history_and_absent_app(self):
        ready = state(phase='readyToInstall', protocol=None, session=0, bitmap=None, sendOffset=None)
        raw = archive([ready])
        report, commands = self.old_ready(raw)
        self.assertTrue(report['healthy'])
        self.assertEqual(len(commands), 1)
        with self.assertRaises(r.Stop):
            self.old_ready(raw, pid=b'1234')
        for bad in (dict(ready, protocol='v2'), dict(ready, session=1),
                    dict(ready, durable=4096), dict(ready, sendOffset=0),
                    dict(ready, event='beginAck'), dict(ready, phase='transferring'),
                    dict(ready, phase='applying')):
            with self.subTest(bad=bad), self.assertRaises(r.Stop):
                self.old_ready(archive([bad, dict(ready, seq=2, monoUs=2000)]))
        for invalid in (unhealthy_archive(raw), b'\n'.join(raw.splitlines()[:-1]) + b'\n',
                        raw.replace(b'"records": 1', b'"records": 2'),
                        archive([dict(ready, packageVerified=False)])):
            with self.subTest(invalid=invalid[-120:]), self.assertRaises(r.Stop):
                self.old_ready(invalid)

    def test_old_ready_existing_stable_home_does_not_restart_or_stop_app(self):
        ready = state(phase='readyToInstall', protocol=None, session=0, bitmap=None, sendOffset=None)
        raw = archive([ready])
        report, commands = self.old_ready(raw, pid=b'1234', home=True)
        self.assertTrue(report['healthy'])
        self.assertEqual(commands, [['shell', 'pidof', PKG]] * 2)
        for opts in ({'busy': True}, {'changed': True}, {'pid': b'1234 5678'}, {'home': False}):
            args = dict(pid=b'1234', home=True)
            args.update(opts)
            with self.subTest(opts=opts), self.assertRaises(r.Stop):
                self.old_ready(raw, **args)

    @unittest.skipUnless(ORIGINAL.is_file(), 'original device hierarchy is a local preserved replay input')
    def test_exact_original_selects_main_scrollview_not_passive_snackbar(self):
        raw = ORIGINAL.read_bytes()
        self.assertEqual(s.scroll_viewport(raw, PKG), (0, 264, 1080, 2298))
        self.assertIn(b'scrollable="true"', raw)

    def test_real_tap_reuses_qualified_viewport_before_start(self):
        d = object.__new__(r.Android)
        d.p = plan()
        d.p['app']['id'] = PKG
        d.p['ui']['start'] = {'resource-id': 'p35-start'}
        d.preparation = None
        d.queue = deque()
        d.last_state_at = time.monotonic()
        d.pump = lambda: None
        screens = iter([original_or_fixture(), xml(node(package=PKG, **{'resource-id': 'p35-start'}))])
        d.ui = lambda: next(screens)
        calls = []
        d.cmd = lambda args, **kwargs: calls.append(args)
        d.record = lambda *args, **kwargs: None
        d.tap({'resource-id': 'p35-start'})
        self.assertEqual(calls[0], ['shell', 'input', 'swipe', '540', '1789', '540', '772', '250'])
        self.assertEqual(calls[1], ['shell', 'input', 'tap', '60', '50'])
        self.assertTrue(d.transfer_start_attempted)

    def test_actionable_or_unknown_overlays_remain_ambiguous(self):
        raw = original_or_fixture()
        marker = '\u6210\u529f:'.encode()
        with self.assertRaises(r.Stop):
            s.scroll_viewport(raw.replace(marker, b'Unrecognized:'), PKG)
        # Only the exact passive leaf qualifies; keep real competing scroll panes.
        tree = s.nodes(raw, PKG)
        snack = next(n for n in tree.iter('node') if n.get('content-desc', '').startswith('\u6210\u529f:'))
        snack.set('clickable', 'true')
        with self.assertRaises(r.Stop):
            s.scroll_viewport(r.ET.tostring(tree), PKG)

    def test_ready_cleanup_requires_no_start_intent_and_full_pretransfer_history(self):
        d = object.__new__(r.Android)
        d.p = plan()
        d.transfer_start_attempted = False
        ready = state(phase='readyToInstall', protocol=None, session=0, bitmap=None, sendOffset=None)
        d.preparation = SimpleNamespace(live=[ready])
        d.check_cleanup_state(ready)
        d.transfer_start_attempted = True
        with self.assertRaises(r.Stop):
            d.check_cleanup_state(ready)
        d.transfer_start_attempted = False
        for bad in (state(event='beginAck'), state(phase='applying'),
                    dict(ready, durable=4096), dict(ready, session=1), dict(ready, phase='unknown')):
            d.preparation.live = [bad, ready]
            with self.subTest(bad=bad), self.assertRaises(r.Stop):
                d.check_cleanup_state(ready)

    def test_closed_ready_ui_uses_bound_owner_oracle_not_default_smoke(self):
        # This unit fixture tests owner-oracle delegation, not a native stop.
        # Renaming an active toolbar's resource ID does not close its recorder.
        raw = xml(node(package=PKG, **{'content-desc': s.FIRMWARE}) +
            node(package=PKG, **{'resource-id': 'p35-reconnect'}))
        d = object.__new__(s.Smoke)
        d.p = {'app': {'id': PKG}}
        d.capture_resolved = True
        d.capture_seal = {'final': {'phase': 'readyToInstall'}}
        d.idle_services = lambda: None
        d.ui = lambda: raw
        calls = []
        d.check_cleanup_state = lambda state: calls.append(state)
        d.idle_recorder_ui()
        self.assertEqual(calls, [d.capture_seal['final']])
        def reject(state):
            raise r.Stop('DEVICE_BUSY', 'default smoke must not admit ready')
        d.check_cleanup_state = reject
        with self.assertRaises(r.Stop):
            d.idle_recorder_ui()

    def test_active_labels_still_block_cleanup_after_only_id_changes(self):
        samples = [xml(node(package=PKG, **{'content-desc': s.FIRMWARE}) +
            node(package=PKG, **{'resource-id': 'p35-arm', 'content-desc': s.RECORDER_STOP}) +
            node(package=PKG, **{'resource-id': 'p35-arm-stream', 'content-desc': s.RECORDER_RECONNECT}))]
        if ORIGINAL.is_file():
            samples.append(ORIGINAL.read_bytes().replace(b'p35-stop', b'p35-arm'))
        for raw in samples:
            d = object.__new__(s.Smoke)
            d.p = {'app': {'id': PKG}}
            d.capture_resolved = True
            d.capture_seal = {'final': {'phase': 'readyToInstall'}}
            d.idle_services = lambda: None
            d.ui = lambda: raw
            calls = []
            d.check_cleanup_state = lambda state: calls.append(state)
            with self.subTest(native=len(raw)), self.assertRaisesRegex(r.Stop, 'recorder active'):
                d.idle_recorder_ui()
            self.assertEqual(calls, [])


if __name__ == '__main__':
    unittest.main()
