"""Deterministic host regression. No physical ADB, install, OTA or AI calls.

All generated test evidence stays in the authorized worktree's .cache. Synthetic
Phone/Process endpoints exercise the real route, parser, archive and cleanup.
"""
from contextlib import contextmanager
import copy
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
import test_runner as fixtures


def plan():
    pin = dict(path='synthetic-read-only', bytes=1, sha256='a'*64)
    return dict(schema=2, run_id='p35-synthetic',
        phone=dict(serial='SYNTHETIC', model='UNIT', adb_port=5093, adb=pin.copy(), adb_key=pin.copy()),
        app=dict(id='com.example.p35acceptance', sha256='b'*64, version_code=92, release=True),
        device=dict(address='aa:bb:cc:dd:ee:ff', display_name='SYNTHETIC-TARGET', expected_version=None, expected_sha256=None),
        scenario=dict(kind='no-ota-smoke', capture_seconds=5, min_heartbeats=3),
        limits=dict(total_seconds=120, stage_seconds=15, command_seconds=5, event_seconds=5, cleanup_seconds=20))


def state(seq=1, **changes):
    return fixtures.state(seq, protocol=None, bitmap=None, session=0,
        deviceAddress=plan()['device']['address'], **changes)


def archive(states):
    body = b''.join((r.PREFIX + json.dumps(row) + '\n').encode() for row in states)
    capture_id=states[0]['captureId'] if states else 'e'*32
    header = dict(schema=1, kind='open', captureId=capture_id)
    footer = dict(schema=1, kind='close', captureId=capture_id, records=len(states),
        sha256=hashlib.sha256(body).hexdigest(), healthy=True, lost=0, error=None)
    return b'OTA_P35_CAPTURE ' + json.dumps(header).encode() + b'\n' + body + b'OTA_P35_CAPTURE ' + json.dumps(footer).encode() + b'\n'


def unhealthy_archive(raw):
    rows = raw.splitlines(keepends=True)
    footer = json.loads(rows[-1][len(b'OTA_P35_CAPTURE '):])
    footer.update(healthy=False, lost=1, error='duration-limit')
    return b''.join(rows[:-1]) + b'OTA_P35_CAPTURE ' + json.dumps(footer).encode() + b'\n'


def node(label='', *, identifier=None, clickable=True, bounds='[10,20][110,80]', cls='android.view.View', scrollable=False):
    attrs = {'content-desc':label, 'package':plan()['app']['id'], 'class':cls,
        'enabled':'true', 'clickable':str(clickable).lower(), 'bounds':bounds, 'scrollable':str(scrollable).lower()}
    if identifier:
        attrs['resource-id'] = identifier
    import xml.etree.ElementTree as ET
    return ET.tostring(ET.Element('node', attrs)).decode()


def xml(*items):
    return fixtures.xml(''.join(items))


def scroll_container(*items, bounds='[20,100][320,500]'):
    import xml.etree.ElementTree as ET
    root=ET.fromstring(node(scrollable=True,clickable=False,bounds=bounds,cls='android.widget.ScrollView'))
    for item in items:root.append(ET.fromstring(item))
    return ET.tostring(root).decode()


class UnitTests(unittest.TestCase):
    def test_latest_identity_uses_last_of_received_batch_not_future_records(self):
        rows=[state(),state(2,event='identity'),state(3,freshConnection=False),state(4,event='identity')]
        self.assertEqual(s.latest_identity(rows,1)['seq'],4)
        self.assertEqual(s.latest_identity(rows[:2],1)['seq'],2)
        self.assertIsNone(s.latest_identity(rows,4))
        path=r.ROOT/'.cache/p35-smoke/p35-smoke-scroll-20b21557-02/observations/00003.jsonl'
        if path.exists():
            rows=s.FileCursor('6f37f98e5eb51493e3b954545475095f').feed(path.read_bytes())
            self.assertEqual(s.latest_identity(rows,6)['seq'],19)

    def test_device_list_viewport_ignores_native_scan_snackbar(self):
        path=r.ROOT/'.cache/p35-smoke/p35-smoke-scroll-20b21557-01/usb/adb-00048.stdout'
        if path.exists():
            self.assertEqual(s.scan_page(path.read_bytes(),'com.wen.gaia.gaia.p35acceptance'),(0,1122,1080,2151))
        tree=xml(node('\u6b63\u5728\u626b\u63cf\u8bbe\u5907...'),
                 scroll_container(node('\u53ef\u7528\u8bbe\u5907')),node('scan snackbar',scrollable=True))
        self.assertEqual(s.scan_page(tree,plan()['app']['id']),(20,100,320,500))
        with self.assertRaises(r.Stop):
            s.scan_page(xml(node('\u626b\u63cf\u5df2\u505c\u6b62'),
                scroll_container(node('\u53ef\u7528\u8bbe\u5907')),scroll_container(node('11:22:33:44:55:66'))),plan()['app']['id'])
        self.assertIsNone(s.scan_page(xml(node('\u626b\u63cf\u5df2\u505c\u6b62'),node('snackbar',scrollable=True)),plan()['app']['id']))

    def test_prearm_home_requires_real_native_home_control_and_no_recorder(self):
        pkg=plan()['app']['id']
        tree=xml(node('\u8bbe\u5907\u4e2d\u5fc3'),node(s.HOME['content-desc'],cls='android.widget.Button'))
        self.assertEqual(s.prearm_page(tree,pkg),'home')
        path=r.ROOT/'.cache/p35-navigation-fix-20261030/reconcile-02/usb/adb-00033.stdout'
        if path.exists():self.assertEqual(s.prearm_page(path.read_bytes(),'com.wen.gaia.gaia.p35acceptance'),'home')
        for bad in [tree.replace(b'android.widget.Button',b'android.view.View'),
                    tree.replace(b'com.example',b'foreign.app'),
                    xml(node('\u8bbe\u5907\u4e2d\u5fc3'),node(identifier='p35-stop')),
                    xml(node(s.HOME['content-desc'],cls='android.widget.Button'))]:
            with self.assertRaises(r.Stop):s.prearm_page(bad,pkg)

    def test_scroll_viewport_original_scan_and_negative_bounds(self):
        path=r.ROOT/'.cache/p35-smoke/p35-smoke-file-20b21557-02/usb/adb-00069.stdout'
        if path.exists():
            self.assertIsNotNone(s.scan_page(path.read_bytes(),'com.wen.gaia.gaia.p35acceptance'))
        tree=xml(node('\u626b\u63cf\u5df2\u505c\u6b62',clickable=False),
                 scroll_container(node('\u53ef\u7528\u8bbe\u5907'),bounds='[10,20][110,80]'))
        self.assertEqual(s.scan_page(tree,plan()['app']['id']),(10,20,110,80))
        for bad in [tree.replace(b'[10,20][110,80]',b'[10,20][110,21]'),
                    tree.replace(b'[10,20][110,80]',b'invalid'),
                    tree.replace(b'com.example',b'foreign.app'),
                    xml(node(scrollable=True),node(scrollable=True))]:
            with self.assertRaises(r.Stop):s.scroll_viewport(bad,plan()['app']['id'])

    def test_scroll_fingerprint_tracks_row_motion_but_ignores_scan_rssi(self):
        tree=xml(node('target\naa:bb:cc:dd:ee:ff\n-60 dBm'))
        self.assertEqual(s.scan_fingerprint(tree,plan()['app']['id']),
                         s.scan_fingerprint(tree.replace(b'-60',b'-80'),plan()['app']['id']))
        self.assertNotEqual(s.scan_fingerprint(tree,plan()['app']['id']),
            s.scan_fingerprint(tree.replace(b'[10,20][110,80]',b'[10,30][110,90]'),plan()['app']['id']))

    def test_file_sealed_unready_ui_original_and_busy_negative_guards(self):
        path=r.ROOT/'.cache/p35-file-fix-20261030/recover-01/usb/adb-00036.stdout'
        if path.exists():
            pkg='com.wen.gaia.gaia.p35acceptance'
            s.sealed_unready_ui(path.read_bytes(),pkg)
        tree=xml(node(s.FIRMWARE),node(s.CLOSED_RECORDER,identifier='p35-arm',clickable=False),
                 node(s.UNREADY_HINT),node(identifier='p35-check',clickable=False),node(identifier='p35-identity'))
        s.sealed_unready_ui(tree,plan()['app']['id'])
        for bad in [tree.replace(b'p35-arm',b'p35-stop'),tree.replace(b'p35-identity',b'unknown-control'),
                    tree.replace(b': closed',b': unknown'),tree.replace(b'com.example',b'foreign.app')]:
            with self.assertRaises(r.Stop):s.sealed_unready_ui(bad,plan()['app']['id'])
    def test_file_cursor_partial_tail_and_repeat_sample_consumes_once(self):
        rows = [state(), state(2, event='identity', monoUs=1000000)]
        raw = archive(rows)
        boundary = raw.find(b'\n', raw.find(b'\n') + 1) + 1
        cursor = s.FileCursor('e'*32)
        self.assertEqual(cursor.feed(raw[:boundary]), rows[:1])
        self.assertEqual(cursor.feed(raw[:boundary+10]), [])
        self.assertEqual(cursor.feed(raw[:boundary+10]), [])
        self.assertEqual(cursor.feed(raw), rows[1:])
        self.assertEqual(cursor.feed(raw), [])
        self.assertIsNotNone(cursor.decoder.closed)

    def test_file_cursor_truncation_prefix_change_sequence_and_complete_corruption(self):
        raw = archive([state(), state(2, monoUs=1000000)])
        boundary = raw.find(b'\n', raw.find(b'\n') + 1) + 1
        for change in [raw[:boundary-1], raw.replace(b'"seq": 1', b'"seq": 9')]:
            cursor = s.FileCursor('e'*32); cursor.feed(raw[:boundary])
            with self.assertRaises(r.Stop): cursor.feed(change)
        for bad in [raw.replace(b'"seq": 2', b'"seq": 3'), raw.replace(b'"seq": 1', b'"seq": 2'),
                    raw.replace(b'OTA_P35_STATE ', b'UNKNOWN '), raw.replace(b'"seq": 1', b'"seq": ?'),
                    raw.replace(b'e'*32, b'f'*32)]:
            with self.subTest(bad=bad), self.assertRaises(r.Stop): s.FileCursor('e'*32).feed(bad)

    def test_file_unhealthy_seal_resolves_structure_not_test_health(self):
        raw = unhealthy_archive(archive([state()]))
        seal = s.sealed_file(raw, 'e'*32)
        self.assertEqual(seal['integrity'], 'VERIFIED'); self.assertFalse(seal['healthy'])
        with self.assertRaises(r.Stop): r.audit_capture(raw, 'e'*32)
        with self.assertRaises(r.Stop): s.sealed_file(raw.replace(b'"records": 1', b'"records": 2'), 'e'*32)

    def test_mixed_file_cursor_and_seal_preserve_global_sequence_and_tail(self):
        raw = fixtures.mixed_archive(interleaved=True)
        lines = raw.splitlines(keepends=True)
        cursor = s.FileCursor('a' * 32)
        observed = []
        for length in range(1, len(lines) + 1):
            prefix = b''.join(lines[:length])
            observed.extend(cursor.feed(prefix))
            self.assertEqual(cursor.feed(prefix), [])
        self.assertEqual([row['seq'] for row in observed], [1, 3])
        self.assertEqual(cursor.decoder.previous['seq'], 3)
        self.assertEqual(cursor.decoder.previous_record['seq'], 5)
        seal = s.sealed_file(raw, 'a' * 32)
        self.assertEqual(seal['records'], 5)
        self.assertEqual(seal['final'], observed[-1])
        self.assertTrue(seal['healthy'])
        self.assertFalse(s.sealed_file(unhealthy_archive(raw), 'a' * 32)['healthy'])
        for index in (2, 4, 5):
            with self.subTest(index=index), self.assertRaises(r.Stop):
                s.sealed_file(b''.join(lines[:index] + lines[index+1:]), 'a' * 32)
        for changed in (raw.replace(b'"records": 5', b'"records": 2'),
                        raw.replace(b'"ownerEpoch": 7', b'"ownerEpoch": 8', 1),
                        raw.replace(b'"schema": 2, "kind": "close"', b'"schema": 1, "kind": "close"'),
                        raw.replace(b'us=40 off=0', b'us=41 off=0')):
            with self.assertRaises(r.Stop): s.sealed_file(changed, 'a' * 32)

    def test_mixed_sealed_stop_recovery_checks_observed_diagnostics_not_list_index(self):
        from types import SimpleNamespace
        raw = fixtures.mixed_archive(interleaved=True)
        lines = raw.splitlines(keepends=True)
        for corrupt in (False, True):
            driver = object.__new__(s.Smoke)
            driver.arm_attempted = driver.arm_baseline_confirmed = driver.stop_attempted = True
            driver.stream_failed = driver.original_verified = True
            driver.stop_seal_recovered = False
            driver.capture_id = 'a' * 32
            driver.previous_captures = {}
            driver.decoder = r.Decoder()
            driver.live = driver.decoder.feed(b''.join(lines[:4]))
            driver.out = r.ROOT / '.cache/unused-mixed-seal-test'
            driver.original = lambda cid, destination: raw
            driver.h = SimpleNamespace(save=lambda path, value: None)
            if corrupt:
                driver.decoder.diagnostics[0]['line'] += ' changed=1'
                with self.assertRaises(r.Stop): driver.recover_sealed_stop()
            else:
                driver.recover_sealed_stop()
                self.assertTrue(driver.capture_resolved)
                self.assertEqual(driver.capture_seal['records'], 5)
                self.assertEqual(driver.capture_state, 'SEALED_WITH_LIVE_GAP')

    def test_mixed_optional_diagnostic_compare_checks_tail_identity(self):
        driver = object.__new__(s.Smoke)
        driver.decoder = r.Decoder()
        driver.live = driver.decoder.feed(fixtures.mixed_archive(interleaved=True))
        driver.capture_id = 'a' * 32
        driver.diagnostic_header = driver.decoder.opened
        driver.diagnostic_footer = driver.decoder.closed
        driver.diagnostic_error = None
        originals = driver.live + driver.decoder.diagnostics
        driver.diagnostic_states = {x['seq']: copy.deepcopy(x) for x in originals}
        driver.compare_diagnostics()
        driver.diagnostic_states[5]['ownerEpoch'] += 1
        with self.assertRaises(r.Stop): driver.compare_diagnostics()

    def test_file_old_unhealthy_but_sealed_original_is_preserved_not_a_permanent_block(self):
        raw=unhealthy_archive(archive([state()]))
        driver=object.__new__(s.Smoke)
        driver.p=plan();driver.previous_captures={};driver.out=r.ROOT/'.cache/p35-file-fix-20261030/unused-offline-path'
        driver.capture_names=lambda:{'e'*32}
        driver.original=lambda cid,destination:raw
        driver.old_captures()
        self.assertEqual(driver.previous_captures['e'*32]['sha256'],hashlib.sha256(raw).hexdigest())
        self.assertFalse(driver.previous_captures['e'*32]['healthy'])

    def test_file_audit_requires_real_staged_prefix_observations(self):
        rows = [state(), state(2,event='identity',monoUs=1000000)] + [state(n+3,monoUs=(n+2)*1000000) for n in range(5)]
        raw=archive(rows); lines=raw.splitlines(keepends=True)
        samples=[]; consumed=0
        for count,stage in [(1,'capture-start'),(2,'fresh-identity'),(7,'capture-observe'),(7,'capture-stop')]:
            prefix=b''.join(lines[:count+1])
            samples.append(dict(bytes=len(prefix),sha256=hashlib.sha256(prefix).hexdigest(),hostMonoNs=len(samples),
                previousConsumedSeq=consumed,lastConsumedSeq=count,stage=stage));consumed=count
        self.assertEqual(s.audit_smoke(raw,'e'*32,plan(),rows,2,observation_source='app-file',samples=samples)['observationSource'],'app-file')
        for bad in [[],[dict(samples[-1],previousConsumedSeq=0)],
                    [dict(x,sha256='f'*64) for x in samples]]:
            with self.assertRaises(r.Stop):s.audit_smoke(raw,'e'*32,plan(),rows,2,observation_source='app-file',samples=bad)

    def test_valid_no_firmware_package_or_fake_ota_parameters(self):
        self.assertEqual(s.validate(plan())['scenario']['kind'], 'no-ota-smoke')

    def test_lifecycle_is_optional_but_requires_explicit_boolean_scope(self):
        for value in [True,False]:
            p=plan();p['lifecycle']=dict(restart_closed_recorder=value)
            self.assertEqual(s.validate(p)['lifecycle']['restart_closed_recorder'],value)
        for value in [dict(restart_closed_recorder='true'),dict(restart_closed_recorder=1),
                      dict(restart_closed_recorder=True,clear_data=True),True]:
            p=plan();p['lifecycle']=value
            with self.assertRaises(r.Stop):s.validate(p)

    def test_original_installed_closed_toolbar_mapping_is_the_restart_guard(self):
        path=r.ROOT/'.cache/p35-smoke-owner-release-20261029-01/usb/adb-00025.stdout'
        if not path.exists():self.skipTest('optional original phone hierarchy not present')
        tree=r.hierarchy(path.read_bytes())
        arms=[n for n in tree.iter('node') if n.get('resource-id')=='p35-arm']
        self.assertEqual(len(arms),1)
        self.assertTrue(any(c.get('content-desc')==s.CLOSED_RECORDER for c in arms[0].iter('node')))

    def test_rejects_scope_expansion_unpinned_assets_bad_deadlines(self):
        mutations = [lambda p:p.update(allow_bluetooth_toggle=True),
            lambda p:p['scenario'].update(kind='ota'), lambda p:p['scenario'].update(capture_seconds=float('nan')),
            lambda p:p['phone'].update(adb_port=5037), lambda p:p['phone']['adb'].update(bytes=0),
            lambda p:p['app'].update(id='com.example.production'), lambda p:p['app'].update(release=False),
            lambda p:p['device'].update(address='unknown'), lambda p:p['limits'].update(total_seconds=float('inf'))]
        for mutate in mutations:
            p = plan(); mutate(p)
            with self.subTest(p=p), self.assertRaises(r.Stop): s.validate(p)

    def test_placeholder_template_rejected(self):
        with self.assertRaises(r.Stop): s.validate(r.strict_json((Path(__file__).parent/'smoke.example.json').read_bytes()))

    def test_multidisplay_null_focus_and_real_conflicts(self):
        pkg = plan()['app']['id']
        focus = ('mCurrentFocus=Window{123 u0 ' + pkg + '/MainActivity}\n').encode()
        self.assertTrue(r.foreground_ok(fixtures.window_dump(b'mCurrentFocus=null\n' + focus), pkg))
        for raw in [b'mCurrentFocus=null\n', focus+focus, focus.replace(pkg.encode(), b'foreign.app'),
                    focus+b'mCurrentFocus=Window{456 u0 system.dialog/Permission}\n', focus+b'mShowingLockscreen=true\n']:
            with self.subTest(raw=raw): self.assertFalse(r.foreground_ok(fixtures.window_dump(raw), pkg))

    def test_layout_motion_is_not_business_transition(self):
        left = xml(node(identifier='p35-arm'))
        right = left.replace(b'[10,20][110,80]', b'[30,40][130,100]')
        self.assertTrue(r.idle_equivalent(left, right))
        for change in [right.replace(b'enabled="true"', b'enabled="false"'),
            right.replace(b'p35-arm', b'p35-stop'), right.replace(b'com.example', b'com.foreign')]:
            self.assertFalse(r.idle_equivalent(left, change))

    def test_home_duplicate_label_disambiguated_by_native_class(self):
        tree = xml(node(s.HOME['content-desc'], cls='android.widget.Button'), node(s.HOME['content-desc']))
        self.assertEqual(r.find_control(tree, s.HOME, plan()['app']['id']), (60,50))

    def test_address_binding_and_ambiguous_name_rejection(self):
        pkg = plan()['app']['id']; address = plan()['device']['address']
        self.assertEqual(s.semantic_control(xml(node('SYNTHETIC\n' + address.upper())), pkg, address, token=True), (60,50))
        with self.assertRaises(r.Stop): s.semantic_control(xml(node('duplicate'),node('duplicate')),pkg,'duplicate')

    def test_integrity_and_fresh_identity_not_ui_success(self):
        rows = [state(event='state'), state(2,event='identity',monoUs=1000000)]
        rows += [state(n+3,monoUs=(n+2)*1000000) for n in range(5)]
        self.assertEqual(s.audit_smoke(archive(rows), 'e'*32, plan(), rows)['heartbeats'],5)
        for mutate in [lambda xs:xs[1].update(event='heartbeat'), lambda xs:xs[-1].update(currentImageSha256='f'*64),
            lambda xs:xs[-1].update(deviceAddress='11:22:33:44:55:66'),
            lambda xs:xs[-1].update(phase='applying'), lambda xs:xs[-1].update(healthy=False)]:
            bad=copy.deepcopy(rows); mutate(bad)
            with self.subTest(bad=bad), self.assertRaises(r.Stop):s.audit_smoke(archive(bad),'e'*32,plan(),bad)
        with self.assertRaises(r.Stop):s.audit_smoke(archive(rows),'e'*32,plan(),rows[:-1])
        with self.assertRaises(r.Stop):s.audit_smoke(archive(rows)[:-1],'e'*32,plan(),rows)

    def test_capture_replayed_receipts_and_after_footer(self):
        header=b'OTA_P35_CAPTURE {"schema":1,"kind":"open","captureId":"' + b'e'*32 + b'"}\n'
        d=r.Decoder();d.feed(header)
        with self.assertRaises(r.Stop):d.feed(header)
        d=r.Decoder();d.feed(archive([state()]))
        with self.assertRaises(r.Stop):d.feed(fixtures.line(state(2)))

    def test_redaction(self):
        text=json.dumps(s.redacted_plan(plan()))
        self.assertNotIn('aa:bb',text);self.assertNotIn('SYNTHETIC',text)

    def test_bootstrap_can_be_disconnected_but_post_query_identity_must_be_fresh(self):
        rows=[state(event='state',linkConnected=False,freshConnection=False),state(2,event='identity',monoUs=1000000)]
        rows += [state(n+3,monoUs=(n+2)*1000000) for n in range(5)]
        self.assertEqual(s.audit_smoke(archive(rows),'e'*32,plan(),rows,2)['bootstrapRecords'],1)
        for index in [1,4]:
            bad=copy.deepcopy(rows);bad[index].update(linkConnected=False,freshConnection=False)
            report=s.audit_smoke(archive(bad),'e'*32,plan(),bad,2)
            self.assertEqual(report['testOutcome'],'FAIL')
            self.assertFalse(report['identityBound']);self.assertFalse(report['freshIdentityVerified'])
            self.assertEqual({item['code'] for item in report['failures']}, {'LINK_NOT_CONNECTED','IDENTITY_NOT_FRESH'})

    def test_known_idle_product_defects_return_fail_without_weakening_originals(self):
        for changes,codes in [
            (dict(linkConnected=False),{'LINK_NOT_CONNECTED'}),
            (dict(freshConnection=False),{'IDENTITY_NOT_FRESH'}),
            (dict(currentVersionCode=0,currentImageSha256=None),{'IDENTITY_UNAVAILABLE'})]:
            with self.subTest(changes=changes):
                rows=[state(event='state',**changes),state(2,event='identity',monoUs=1000000,**changes)]
                rows += [state(n+3,monoUs=(n+2)*1000000,**changes) for n in range(5)]
                raw=archive(rows)
                report=s.audit_smoke(raw,'e'*32,plan(),rows,2)
                self.assertEqual(report['testOutcome'],'FAIL');self.assertEqual(report['integrity'],'VERIFIED')
                self.assertEqual({item['code'] for item in report['failures']},codes)
                self.assertTrue(report['targetBound']);self.assertFalse(report['identityBound'])
                self.assertEqual(r.audit_capture(raw,'e'*32)['records'],len(rows))

    def test_firmware_pins_are_product_verdicts_not_substituted_observations(self):
        rows=[state(event='identity',monoUs=0)]+[state(n+2,monoUs=(n+1)*1000000) for n in range(5)]
        p=plan();p['device'].update(expected_version=123,expected_sha256='f'*64)
        report=s.audit_smoke(archive(rows),'e'*32,p,rows)
        self.assertEqual(report['testOutcome'],'FAIL')
        self.assertEqual({item['code'] for item in report['failures']},{'VERSION_PIN_MISMATCH','IMAGE_PIN_MISMATCH'})
        self.assertEqual(report['firmwareVersion'],rows[0]['currentVersionCode'])
        self.assertEqual(report['firmwareSha256'],rows[0]['currentImageSha256'])

    def test_disconnected_idle_capture_is_safe_to_stop_not_fresh_identity(self):
        disconnected=state(linkConnected=False,freshConnection=False)
        s.idle_phase(disconnected,plan())
        with self.assertRaises(r.Stop):s.idle_state(disconnected,plan())
        for bad in [dict(disconnected,phase='applying'),dict(disconnected,lost=1),
                    dict(disconnected,deviceAddress='11:22:33:44:55:66')]:
            with self.assertRaises(r.Stop):s.idle_phase(bad,plan())

    def test_owned_prefix_is_not_an_immutable_finished_archive(self):
        raw=archive([state(linkConnected=False,freshConnection=False)])
        prefix=raw[:raw.rfind(b'OTA_P35_CAPTURE ')]
        self.assertIsNone(s.capture_prefix(prefix,'e'*32,plan()).closed)
        self.assertIsNotNone(s.capture_prefix(raw,'e'*32,plan()).closed)
        for bad in [prefix.replace(b'"seq": 1',b'"seq": 2'),prefix.replace(b'"phase": "idle"',b'"phase": "applying"'),
                    prefix.replace(b'"lost": 0',b'"lost": 1'),prefix.replace(b'e'*32,b'f'*32),
                    prefix.replace(b'"schema": 1',b'"schema": true',1)]:
            with self.assertRaises(r.Stop):s.capture_prefix(bad,'e'*32,plan())


class SyntheticDevice:
    """Scripted native UI/producer. All unexpected device commands fail closed."""
    def __init__(self, out, h, *, fault=None, initial='home'):
        self.out, self.h, self.fault = out, h, fault
        self.now, self.page, self.calls = 100., initial, []
        self.server = self.logger = None
        self.active, self.rows, self.raw, self.seq, self.next_beat = False, [], b'', 0, None
        self.started, self.closed = 0., False
        self.last_tree = None
        self.cold = bool(fault and fault.startswith(('closed-','restart-','owned-stop-')))
        self.pid, self.restarted, self.stopped = '1234', False, False
        self.cleaning = False
        self.foregrounded = False
        self.list_index = 2 if fault=='list-scroll-up' else 0
        self.swipes = 0
        self.cid='e'*32
        self.old_raw=archive([state(linkConnected=False,freshConnection=False)]) if self.cold else None
        if fault=='restart-old-partial':self.old_raw=self.old_raw[:self.old_raw.rfind(b'OTA_P35_CAPTURE ')]

    def mono(self):
        return self.now

    def sleep(self, seconds):
        self.now += seconds
        if self.active and self.next_beat is not None and self.now >= self.next_beat:
            self.emit('heartbeat');self.next_beat += 1

    def append(self, data):
        self.raw += data
        if not self.fault or not self.fault.startswith('file-') or self.fault=='file-logcat-conflict':
            if self.fault=='file-logcat-conflict':data=data.replace(b'"currentVersionCode": 30293',b'"currentVersionCode": 30287')
            with self.logger.paths['stdout'].open('ab') as stream: stream.write(data)

    def emit(self, event):
        self.seq += 1
        if self.fault=='file-sequence-gap' and self.seq==3:self.seq+=1
        row=state(self.seq,event=event,monoUs=int((self.now-self.started)*1000000),captureId=self.cid)
        if self.fault == 'wrong-target':row['deviceAddress']='11:22:33:44:55:66'
        if self.fault=='bootstrap-disconnected' and event!='identity' and not any(r['event']=='identity' for r in self.rows):
            row.update(linkConnected=False,freshConnection=False)
        if self.fault in {'false-link','false-fresh','false-both','false-both-cleanup'}:
            if self.fault!='false-fresh':row['linkConnected']=False
            if self.fault!='false-link':row['freshConnection']=False
        if self.fault=='drop-after-identity' and self.seq>=4:row.update(linkConnected=False,freshConnection=False)
        if self.fault=='changed-after-identity' and self.seq>=4:row['currentImageSha256']='f'*64
        if self.fault=='closed-false-flags':row.update(linkConnected=False,freshConnection=False)
        if self.fault=='query-double-identity' and event=='heartbeat' and sum(x['event']=='identity' for x in self.rows)==1:
            row['freshConnection']=False
        self.rows.append(row)
        self.append((r.PREFIX+json.dumps(row)+'\n').encode())
        if self.seq>=3 and self.fault=='file-truncate':self.raw=self.raw[-100:]
        if self.seq>=3 and self.fault=='file-prefix-change':self.raw=self.raw.replace(b'"kind": "open"',b'"kind": "oops"')

    def tree(self):
        choices={
            'home':[node(s.HOME['content-desc'],cls='android.widget.Button'),node(s.HOME['content-desc']),node('\u8bbe\u5907\u4e2d\u5fc3',clickable=False)],
            'dashboard':[node('\u4eea\u8868\u76d8'),node(s.DEVICES['content-desc'])],
            'list':[node('\u6b63\u5728\u626b\u63cf\u8bbe\u5907...',clickable=False),node('SYNTHETIC\n'+plan()['device']['address'].upper())],
            'detail':[node(s.DEVICE_ID,clickable=False),node(plan()['device']['address'].upper(),clickable=False),node(s.CONNECT['content-desc'])],
            'connected':[node(s.DEVICE_ID,clickable=False),node(plan()['device']['address'].upper(),clickable=False),node(s.CONNECTED,clickable=False),node(s.OPEN_FIRMWARE)],
            'firmware':[node(s.FIRMWARE,clickable=False),node('record: off' if not self.active else 'recording',identifier='p35-stop' if self.active else 'p35-arm'),
                node(identifier='p35-reconnect',bounds='[130,20][230,80]'),node(identifier='p35-check')],
        }
        if self.fault=='recorder-unavailable' and self.page=='firmware':
            choices['firmware']=[node(s.FIRMWARE,clickable=False),node(identifier='p35-arm',clickable=False),
                node(identifier='p35-reconnect',bounds='[130,20][230,80]')]
        if self.fault and self.fault.startswith('list-'):
            found = self.list_index >= 2 if self.fault!='list-scroll-up' else self.list_index == 0
            if self.fault in {'list-missing','list-scroll-timeout','list-foreign','list-pid-change',
                              'list-no-viewport','list-ambiguous-viewport','list-wrong-name-mac'}:
                found=False
            row=node('SYNTHETIC\n'+plan()['device']['address'].upper()) if found else node(
                ('SYNTHETIC-TARGET' if self.fault=='list-wrong-name-mac' else 'other')+'\n11:22:33:44:55:%02x'%self.list_index)
            choices['list']=[node('\u6b63\u5728\u626b\u63cf\u8bbe\u5907...',clickable=False),row]
            if self.fault!='list-no-viewport':
                choices['list']=[choices['list'][0],scroll_container(node('\u53ef\u7528\u8bbe\u5907'),row)]
            if self.fault=='list-ambiguous-viewport':choices['list'].append(scroll_container(node('11:22:33:44:55:ff')))
            if self.fault=='list-snackbar':choices['list'].append(node('scan snackbar',scrollable=True))
            if self.fault=='list-hidden-footer':
                choices['list'].append(node('\u672a\u627e\u5230\u6211\u7684\u8bbe\u5907',bounds='[0,0][0,0]'))
        if self.cold and not self.restarted and self.page=='firmware':
            status='failed:unknown' if self.fault=='restart-unknown-status' else 'closed'
            choices['firmware']=[node(s.FIRMWARE,clickable=False),
                node(s.CLOSED_RECORDER.rsplit(': ',1)[0]+': '+status,identifier='p35-arm',clickable=False),
                node(identifier='p35-check',clickable=self.fault!='restart-busy-ui')]
        if self.fault=='file-sealed-unready' and self.seq and not self.active and self.page=='firmware':
            choices['firmware']=[node(s.FIRMWARE),node(s.CLOSED_RECORDER,identifier='p35-arm',clickable=False),
                node(s.UNREADY_HINT),node(identifier='p35-check',clickable=False),node(identifier='p35-identity')]
        self.last_tree=xml(*choices[self.page]);return self.last_tree

    def command(self, args):
        self.calls.append(list(args));self.sleep(.025)
        pkg=plan()['app']['id']
        if args==['devices','-l']:
            return b'List of devices attached\n' if self.fault=='no-usb' else b'SYNTHETIC device model:UNIT\n'
        if args==['get-serialno']:return b'SYNTHETIC\n'
        if args==['shell','getprop','ro.product.model']:return b'UNIT\n'
        if args[:3]==['shell','pm','list']:return ('package:'+pkg+'\n').encode()
        if args[:3]==['shell','pm','path']:return b'package:/data/app/unit/base.apk\n'
        if args[:3]==['shell','dumpsys','package']:return b'versionCode=92\n'
        if args[:4]==['shell','dumpsys','activity','services']:
            return b'DeviceOtaService' if self.fault=='busy' else b'No OTA service\n'
        if args[:3]==['shell','sh','-c']:return b'directory\n' if self.cold or self.fault=='old-partial' or self.raw else b'missing\n'
        if args[:3]==['shell','ls','-1']:
            if self.restarted and self.fault=='restart-store-changed':return ('f'*32+'.jsonl\n').encode()
            names=['e'*32] if self.cold else ['f'*32] if self.fault=='old-partial' else []
            if self.raw:names.append(self.cid)
            if self.raw and self.fault=='file-many':names.append('f'*32)
            return ''.join(n+'.jsonl\n' for n in names).encode()
        if args[:4]==['shell','cmd','package','resolve-activity']:return (pkg+'/MainActivity\n').encode()
        if args[:3]==['shell','am','force-stop']:
            if args[-1]!=pkg:raise AssertionError('foreign package process stop')
            if self.fault in {'restart-timeout','owned-stop-timeout' if self.restarted else ''}:
                raise r.Stop('TIMEOUT','synthetic uncertain process stop')
            if self.fault!='restart-pid-survives':self.pid=None;self.stopped=True
            return b''
        if args[:3]==['shell','am','start']:
            self.foregrounded=True
            if self.fault=='launch-existing-pid-changed':self.pid='9876'
            if self.stopped or self.pid is None:
                self.pid='1234' if self.fault=='restart-same-pid' else '2345'
                self.restarted=True;self.stopped=False;self.page='home';self.cid='d'*32
                if self.fault=='restart-old-changed':self.old_raw=archive([state(linkConnected=False,freshConnection=False,monoUs=2000000)])
            if self.fault=='launch-timeout':raise r.Stop('TIMEOUT','synthetic uncertain launch')
            if self.fault=='launch-error':return b'Error: synthetic launch result\n'
            if self.fault=='launch-unknown':return b''
            return ('Status: ok\nActivity: '+args[-1]+'\nComplete\n').encode()
        if args[:2]==['shell','pidof']:
            if self.fault=='list-pid-change' and self.swipes:self.pid='9876'
            if self.active and self.fault=='file-pid-change':self.pid='9876'
            if self.fault=='launch-pre-pid-ambiguous':return b'1234 9876\n'
            if self.restarted and self.fault=='launch-post-pid-missing':return b''
            if self.restarted and self.fault=='launch-post-pid-ambiguous':return b'2345 9876\n'
            if self.fault=='owned-cleanup-pid-changed' and self.cleaning:self.pid='9876'
            return ((self.pid or '')+'\n').encode()
        if args[:3]==['shell','dumpsys','window']:
            owner='foreign.app' if self.fault=='foreign' or self.fault=='restart-foreign' and self.restarted else pkg
            if self.fault=='file-background-sealed' and not self.foregrounded:owner='foreign.app'
            if self.fault=='list-foreign' and self.swipes:owner='foreign.app'
            focus = ('mCurrentFocus=null\nmCurrentFocus=Window{123 u0 '+owner+'/MainActivity}\n').encode()
            if self.fault=='window-history-only':return b'WINDOW MANAGER LAST ANR (dumpsys window lastanr)\n'+focus
            raw = fixtures.window_dump(focus, policy=b'mKeyguardShowing=true\n' if self.fault=='window-locked' else b'')
            if self.fault=='window-truncated':return raw.split(b'WINDOW MANAGER TOKENS')[0]
            if self.fault=='window-conflict':return fixtures.window_dump(focus+focus)
            if self.fault=='window-history':return b'WINDOW MANAGER LAST ANR (dumpsys window lastanr)\nWINDOW MANAGER DISPLAY CONTENTS (dumpsys window displays)\nmCurrentFocus=Window{456 u0 old.app/MainActivity}\n'+raw
            return raw
        if args[:2]==['exec-out','uiautomator']:
            if self.fault=='foreign':raise AssertionError('foreign hierarchy must never be read')
            return self.tree()
        if args[:3]==['shell','input','swipe']:
            self.swipes+=1
            if self.fault=='list-scroll-timeout':raise r.Stop('TIMEOUT','uncertain synthetic swipe')
            self.list_index=max(0,min(3,self.list_index+(1 if int(args[4])>int(args[6]) else -1)))
            return b''
        if args[:3]==['shell','input','tap']:
            if self.fault=='tap-timeout':raise r.Stop('TIMEOUT','synthetic uncertain tap')
            transitions={'home':'dashboard','dashboard':'list','list':'detail','detail':'connected','connected':'firmware'}
            if self.page in transitions:self.page=transitions[self.page];return b''
            if not self.active and not self.seq:
                if self.fault=='file-no-start':return b''
                self.active=True;self.started=self.now
                if self.fault!='missing-producer':
                    self.append(b'OTA_P35_CAPTURE '+json.dumps(dict(schema=1,kind='open',captureId=self.cid)).encode()+b'\n')
                    if self.fault=='file-partial-tail':self.append(b'OTA_P35_STATE {"seq":')
                    elif self.fault!='file-header-only':self.emit('state');self.next_beat=self.now+1
            elif args[-2:]==['180','50']:
                if self.fault!='query-timeout':
                    self.emit('identity')
                    if self.fault=='query-double-identity':self.emit('heartbeat');self.emit('identity')
                else:raise r.Stop('TIMEOUT','synthetic query timeout')
            else:
                self.active=False
                complete=archive(self.rows)
                if self.fault=='file-unhealthy-footer':complete=unhealthy_archive(complete)
                if self.fault!='missing-footer':self.append(complete[len(self.raw):])
                if self.fault=='file-stop-timeout':raise r.Stop('TIMEOUT','STOP returned late after file sealed')
            return b''
        if args[:3]==['shell','wc','-c']:
            raw=self.old_raw if self.cold and args[-1].endswith('e'*32+'.jsonl') else self.raw
            return str(len(b'partial\n') if self.fault=='old-partial' else len(raw)).encode()+b' capture\n'
        if args[:2]==['exec-out','cat']:
            if self.cold and args[-1].endswith('e'*32+'.jsonl'):return self.old_raw
            return b'partial\n' if self.fault=='old-partial' else self.raw
        if args[:2]==['exec-out','head']:return self.raw[:int(args[3])]
        if args[:2]==['shell','sha256sum']:
            if args[2].endswith('base.apk'):return (plan()['app']['sha256']+' base.apk\n').encode()
            raw=b'partial\n' if self.fault=='old-partial' else self.raw
            if self.cold and args[-1].endswith('e'*32+'.jsonl'):raw=self.old_raw
            digest='0'*64 if self.fault=='remote-hash' else hashlib.sha256(raw).hexdigest()
            return (digest+' capture\n').encode()
        raise AssertionError('unexpected or unauthorized synthetic command: '+repr(args))

    def process(self, out, label, argv, env):
        device=self
        class Process:
            def __init__(self):
                self.paths={k:device.h.checked(out/(label+'.'+k)) for k in ('stdout','stderr')}
                for path in self.paths.values():device.h.raw(path,b'')
                self.running=True
            def alive(self):return self.running
            def close(self, reason):self.running=False
        process=Process()
        if label=='adb-server':self.server=process
        elif label=='logcat':self.logger=process
        else:raise AssertionError('unexpected worker')
        return process


class RouteTests(unittest.TestCase):
    def test_double_get_info_batch_starts_coverage_at_latest_identity(self):
        driver,device,out,report,error,cleanup=self.run_route('query-double-identity')
        self.assertIsNone(error);self.assertEqual(report['testOutcome'],'PASS');self.assertTrue(cleanup['complete'])
        identities=[row for row in device.rows if row['event']=='identity']
        self.assertEqual(len(identities),2);self.assertEqual(driver.identity_seq,identities[-1]['seq'])
        self.assertTrue(any(not row['freshConnection'] for row in device.rows if row['seq']<driver.identity_seq))
        self.assertEqual(sum(c[:3]==['shell','input','tap'] and c[-2:]==['180','50'] for c in device.calls),1)

    def test_target_below_fold_and_above_current_position_complete_real_route(self):
        for fault in ['list-scroll-target','list-scroll-up','list-hidden-footer','list-snackbar']:
            with self.subTest(fault=fault):
                driver,device,out,report,error,cleanup=self.run_route(fault)
                self.assertIsNone(error);self.assertEqual(report['testOutcome'],'PASS')
                self.assertTrue(cleanup['complete']);self.assertGreaterEqual(device.swipes,2)
                for call in device.calls:
                    if call[:3]==['shell','input','swipe']:
                        self.assertEqual(call[3],str((20+320)//2));self.assertEqual(call[5],call[3])
                        self.assertEqual({int(call[4]),int(call[6])},{200,400})
                events=[self.h.read_json(p) for p in sorted((out/'journal').glob('*.json'))]
                self.assertTrue(any(x['event']=='target-found' and x['matchedBy']=='mac' for x in events))
                self.assertEqual(sum(x['event']=='scroll-intent' for x in events),device.swipes)
                self.assertFalse(driver.prearm_navigation)

    def test_missing_target_is_bounded_coverage_not_device_absence(self):
        for fault in ['list-missing','list-no-viewport','list-wrong-name-mac']:
            with self.subTest(fault=fault):
                _,device,_,report,error,cleanup=self.run_route(fault,terminal=True,cold_start=True)
                self.assertIsNone(error);self.assertIsNone(report);self.assertEqual(device.exit_code,2)
                self.assertEqual(device.result['code'],'TARGET_SEARCH_INCOMPLETE')
                self.assertLessEqual(device.swipes,24);self.assertEqual(cleanup['armAttempts'],0)
                self.assertTrue(cleanup['complete']);self.assertFalse(device.result['lockRetained'])
                self.assertTrue(cleanup['ownedAppClosed']);self.assertEqual(device.page,'list')

    def test_scroll_unknown_foreground_pid_and_ambiguous_route_never_tap_target(self):
        for fault in ['list-scroll-timeout','list-foreign','list-pid-change','list-ambiguous-viewport']:
            with self.subTest(fault=fault):
                _,device,out,report,error,cleanup=self.run_route(fault,terminal=True,cold_start=True)
                self.assertIsNone(error);self.assertIsNone(report);self.assertEqual(device.exit_code,2)
                self.assertEqual(cleanup['armAttempts'],0);self.assertFalse(cleanup['ownedAppClosed'])
                self.assertTrue(device.result['lockRetained']);self.assertEqual(device.page,'list')
                events=[self.h.read_json(p) for p in sorted((out/'journal').glob('*.json'))]
                self.assertFalse(any(x['event']=='target-found' for x in events))
                if fault=='list-scroll-timeout':self.assertEqual(device.swipes,1)
                if fault=='list-ambiguous-viewport':self.assertEqual(device.swipes,0)

    def test_file_empty_logcat_full_terminal_route_and_stop_ack_from_footer(self):
        driver,device,out,report,error,cleanup=self.run_route('file-empty-logcat',terminal=True,cold_start=True)
        self.assertIsNone(error);self.assertEqual(device.exit_code,0)
        self.assertEqual(report['observationSource'],'app-file');self.assertEqual(report['logcatOverlapRecords'],0)
        self.assertEqual((out/'logcat.stdout').read_bytes(),b'')
        self.assertEqual((out/'app-capture.jsonl').read_bytes(),device.raw)
        self.assertEqual((cleanup['armAttempts'],cleanup['stopAttempts']),(1,1))
        self.assertTrue(cleanup['ownedAppClosed']);self.assertFalse(device.result['lockRetained'])

    def test_file_no_start_header_partial_many_or_changed_pid_never_rearms(self):
        for fault in ['file-no-start','file-header-only','file-partial-tail','file-many','file-pid-change']:
            with self.subTest(fault=fault):
                driver,device,out,report,error,cleanup=self.run_route(fault,initial='firmware')
                self.assertIsNotNone(error);self.assertIsNone(report)
                self.assertEqual(sum(c[:3]==['shell','input','tap'] and c[-2:]==['60','50'] for c in device.calls),1)
                self.assertEqual(cleanup['stopAttempts'],0)
                self.assertEqual(cleanup['captureResolved'],fault=='file-no-start')

    def test_file_corruption_and_source_conflict_fail_without_stop(self):
        for fault in ['file-truncate','file-prefix-change','file-sequence-gap','file-logcat-conflict']:
            with self.subTest(fault=fault):
                _,_,_,report,error,cleanup=self.run_route(fault,initial='firmware')
                self.assertIsNone(report);self.assertIsNotNone(error)
                self.assertTrue(cleanup['unresolved']);self.assertEqual(cleanup['stopAttempts'],0)

    def test_file_final_remote_digest_mismatch_keeps_original_and_unresolved_owner(self):
        _,_,out,report,error,cleanup=self.run_route('remote-hash')
        self.assertIsNone(report);self.assertIsNotNone(error)
        self.assertTrue((out/'app-capture.jsonl').is_file());self.assertTrue(cleanup['unresolved'])

    def test_file_unhealthy_or_late_stop_is_failure_but_resolves_owned_actions(self):
        for fault in ['file-unhealthy-footer','file-stop-timeout']:
            with self.subTest(fault=fault):
                _,device,out,_,_,cleanup=self.run_route(fault,terminal=True,cold_start=True)
                self.assertEqual(device.exit_code,1);self.assertTrue(cleanup['captureResolved'])
                self.assertTrue(cleanup['complete']);self.assertFalse(device.result['lockRetained'])
                self.assertEqual((cleanup['armAttempts'],cleanup['stopAttempts']),(1,1))
                self.assertEqual((out/'app-capture.jsonl').read_bytes(),device.raw)

    @classmethod
    def setUpClass(cls):
        cls.h=r.load_host()
        cls.area=cls.h.fresh(Path(os.environ.get('P35_SMOKE_TEST_OUT', r.ROOT/'.cache/p35-standalone-selftest-20261029'))/('suite-'+uuid.uuid4().hex))
        sys.path.insert(0,str(r.ROOT/'Tools/ota/p34-acceptance'))
        import live_phone
        cls.live_phone=live_phone

    def run_route(self, fault=None, initial='home', terminal=False, restart=False, cold_start=False):
        h=self.h
        case=h.fresh(self.area/('case-'+uuid.uuid4().hex))
        out=case/'evidence' if terminal else case
        device=SyntheticDevice(out,h,fault=fault,initial=initial)
        if cold_start:device.pid=None
        configuration=plan()
        if restart:configuration['lifecycle']=dict(restart_closed_recorder=True)
        real_phone=self.live_phone.Phone
        class Phone:
            def __init__(self,p,usb,seconds):
                self.out=h.fresh(usb);self.env=h.environment(usb)
                self.port=5093;self.serial='SYNTHETIC';self.pkg=plan()['app']['id']
                self.plan=dict(p,apk=dict(sha256=plan()['app']['sha256']))
                self.base=['SYNTHETIC_ADB','-H','127.0.0.1','-P','5093','-s','SYNTHETIC']
                self.server=None
            def cmd(self,args,**kwargs):return device.command(args)
            def installed(self):return real_phone.installed(self)
            def close(self):
                if device.fault in {'cleanup','false-both-cleanup'}:raise RuntimeError('synthetic cleanup failure')
                if self.server:self.server.close('synthetic closed')
        # Only the standard-tool endpoints are synthetic; the route is real.
        with patch.object(self.live_phone,'Phone',Phone),patch.object(h,'Process',device.process),\
             patch.object(h,'listening',lambda port:bool(device.server and device.server.alive())),\
             patch.object(h,'pinned',lambda item:Path('synthetic-read-only')),\
             patch.object(s.time,'monotonic',device.mono),patch.object(s.time,'sleep',device.sleep):
            error=None;report=None
            if terminal:
                drivers=[]
                real_driver=s.Smoke
                class Driver(real_driver):
                    def __init__(self,*args):
                        super().__init__(*args);drivers.append(self)
                    def cleanup(self):
                        device.cleaning=True
                        return super().cleanup()
                config=case/'configuration.json';h.save(config,configuration)
                cwd=Path.cwd()
                try:
                    os.chdir(case)
                    with patch.object(s,'ROOT',case),patch.object(h,'ROOT',case),patch.object(s,'Smoke',Driver),\
                         patch.object(r,'load_host',lambda:h):
                        device.exit_code=s.main(['smoke','--plan',str(config),'--out',str(out),'--execute'])
                finally:os.chdir(cwd)
                driver=drivers[0];device.result=h.read_json(out/'result.json')
                report=device.result.get('capture');cleanup=device.result['cleanup']
            else:
                driver=s.Smoke(configuration,out,h)
                try:
                    driver.start();driver.navigate();report=driver.record_smoke()
                except BaseException as caught:error=caught
                device.cleaning=True
                cleanup=driver.cleanup()
        self.assertFalse(device.logger and device.logger.alive())
        if fault not in {'cleanup','false-both-cleanup'}:self.assertFalse(device.server and device.server.alive())
        self.assertFalse(any(c[0] in {'install','uninstall'} or 'bluetooth_manager' in c or 'clear' in c for c in device.calls))
        if not restart and not cold_start:self.assertFalse(any('force-stop' in c for c in device.calls))
        return driver,device,out,report,error,cleanup

    def test_full_home_connect_fresh_identity_capture_retrieve_cleanup(self):
        driver,device,out,report,error,cleanup=self.run_route()
        self.assertIsNone(error)
        self.assertEqual(report['integrity'],'VERIFIED')
        self.assertTrue(cleanup['complete']);self.assertFalse(cleanup['unresolved'])
        self.assertEqual((out/'app-capture.jsonl').read_bytes(),device.raw)
        self.assertEqual(sum(c[:3]==['shell','input','tap'] for c in device.calls),8)

    def test_cold_launch_owns_and_closes_only_new_test_app_after_full_terminal_route(self):
        _,device,out,report,error,cleanup=self.run_route(terminal=True,cold_start=True)
        self.assertIsNone(error);self.assertEqual(device.exit_code,0)
        self.assertEqual(device.result['automationOutcome'],'COMPLETED')
        self.assertTrue(cleanup['ownedAppLaunchConfirmed']);self.assertTrue(cleanup['ownedAppClosed'])
        self.assertEqual(cleanup['appRestartAttempts'],0);self.assertEqual(cleanup['ownedAppStopAttempts'],1)
        self.assertIsNone(device.pid);self.assertFalse(device.result['lockRetained'])
        self.assertEqual((out/'app-capture.jsonl').read_bytes(),device.raw)
        self.assertEqual(sum('force-stop' in c for c in device.calls),1)

    def test_existing_test_app_is_not_owned_or_stopped_by_launch(self):
        _,device,_,_,error,cleanup=self.run_route(terminal=True)
        self.assertIsNone(error);self.assertEqual(device.exit_code,0)
        self.assertFalse(cleanup['ownedAppLaunchConfirmed']);self.assertFalse(cleanup['ownedAppClosed'])
        self.assertEqual(device.pid,'1234');self.assertFalse(any('force-stop' in c for c in device.calls))

    def test_unconfirmed_cold_foreground_keeps_process_and_lock_without_hierarchy(self):
        _,device,out,_,error,cleanup=self.run_route('foreign',terminal=True,cold_start=True)
        self.assertIsNone(error);self.assertEqual(device.exit_code,2)
        self.assertTrue(cleanup['unresolved']);self.assertFalse(cleanup['ownedAppLaunchConfirmed'])
        self.assertTrue(device.result['lockRetained']);self.assertIsNotNone(device.pid)
        self.assertEqual(device.result['code'],'UNRESOLVED_STATE')
        self.assertEqual(device.result['executionError']['code'],'UI_UNAVAILABLE')
        self.assertFalse(any(c[:2]==['exec-out','uiautomator'] or 'force-stop' in c for c in device.calls))
        events=[self.h.read_json(p) for p in sorted((out/'journal').glob('*.json'))]
        self.assertEqual(sum(x['event']=='launch-returned' for x in events),1)
        self.assertFalse(any(x['event']=='launch-confirmed' for x in events))

    def test_current_window_negative_shapes_block_full_launch_chain(self):
        for fault in ('window-history-only','window-truncated','window-locked','window-conflict'):
            with self.subTest(fault=fault):
                _,device,out,_,_,cleanup=self.run_route(fault,terminal=True,cold_start=True)
                self.assertEqual(device.exit_code,2)
                self.assertTrue(device.result['lockRetained'])
                self.assertEqual(cleanup['armAttempts'],0)
                self.assertFalse(any(c[:2]==['exec-out','uiautomator'] or 'force-stop' in c for c in device.calls))

    def test_cold_owned_stop_timeout_preserves_capture_and_never_replays_stop(self):
        _,device,out,report,error,cleanup=self.run_route('owned-stop-timeout',terminal=True,cold_start=True)
        self.assertIsNone(error);self.assertIsNotNone(report);self.assertEqual(device.exit_code,2)
        self.assertFalse(cleanup['complete']);self.assertTrue(device.result['lockRetained'])
        self.assertEqual(device.result['code'],'UNRESOLVED_STATE')
        self.assertEqual(device.result['executionOutcome'],'PASS')
        self.assertEqual(device.result['automationOutcome'],'STOPPED')
        self.assertEqual(cleanup['errors'][0]['code'],'TIMEOUT')
        self.assertEqual((out/'app-capture.jsonl').read_bytes(),device.raw)
        self.assertEqual(sum('force-stop' in c for c in device.calls),1)

    def test_ambiguous_prelaunch_pid_blocks_before_any_launch_or_hierarchy(self):
        _,device,_,report,error,cleanup=self.run_route('launch-pre-pid-ambiguous',terminal=True)
        self.assertIsNone(error);self.assertIsNone(report);self.assertEqual(device.exit_code,2)
        self.assertEqual(device.result['code'],'ENV_BLOCKED')
        self.assertTrue(cleanup['complete']);self.assertFalse(cleanup['unresolved'])
        self.assertFalse(device.result['lockRetained']);self.assertIsNone(device.logger)
        self.assertFalse(any(c[:3]==['shell','am','start'] or c[:2]==['exec-out','uiautomator'] or
                             'force-stop' in c for c in device.calls))

    def test_unconfirmed_launch_keeps_lock_and_never_replays_or_reads_hierarchy(self):
        for fault,cold,code in [('launch-error',True,'ENV_BLOCKED'),('launch-unknown',True,'ENV_BLOCKED'),('launch-timeout',True,'TIMEOUT'),
                              ('launch-post-pid-missing',True,'ENV_BLOCKED'),
                              ('launch-post-pid-ambiguous',True,'ENV_BLOCKED'),
                              ('launch-existing-pid-changed',False,'IDENTITY_MISMATCH')]:
            with self.subTest(fault=fault):
                _,device,out,report,error,cleanup=self.run_route(fault,terminal=True,cold_start=cold)
                self.assertIsNone(error);self.assertIsNone(report);self.assertEqual(device.exit_code,2)
                self.assertEqual(device.result['code'],'UNRESOLVED_STATE')
                self.assertEqual(device.result['executionError']['code'],code)
                self.assertEqual(device.result['automationOutcome'],'STOPPED')
                self.assertTrue(cleanup['unresolved']);self.assertFalse(cleanup['ownedAppLaunchConfirmed'])
                self.assertTrue(device.result['lockRetained']);self.assertIsNone(device.logger)
                self.assertIsNotNone(device.pid)
                self.assertEqual(sum(c[:3]==['shell','am','start'] for c in device.calls),1)
                self.assertFalse(any(c[:2]==['exec-out','uiautomator'] or 'force-stop' in c for c in device.calls))
                self.assertFalse((out/'app-capture.jsonl').exists())

    def test_changed_owned_pid_at_cleanup_preserves_original_and_never_stops_replacement(self):
        _,device,out,report,error,cleanup=self.run_route('owned-cleanup-pid-changed',terminal=True,cold_start=True)
        self.assertIsNone(error);self.assertIsNotNone(report);self.assertEqual(device.exit_code,2)
        self.assertEqual(device.result['code'],'UNRESOLVED_STATE')
        self.assertEqual(device.result['executionOutcome'],'PASS')
        self.assertEqual(device.result['automationOutcome'],'STOPPED')
        self.assertTrue(cleanup['ownedAppLaunchConfirmed']);self.assertFalse(cleanup['ownedAppClosed'])
        self.assertTrue(cleanup['captureResolved']);self.assertTrue(cleanup['unresolved'])
        self.assertTrue(device.result['lockRetained']);self.assertEqual(device.pid,'9876')
        self.assertEqual((out/'app-capture.jsonl').read_bytes(),device.raw)
        self.assertFalse(any('force-stop' in c for c in device.calls))

    def test_already_connected_list_and_firmware_entry(self):
        for initial in ['list','connected','firmware']:
            with self.subTest(initial=initial):
                _,_,_,report,error,cleanup=self.run_route(initial=initial)
                self.assertIsNone(error);self.assertTrue(cleanup['complete']);self.assertTrue(report['identityBound'])

    def test_foreign_foreground_is_blocked_before_any_hierarchy(self):
        _,device,_,_,error,cleanup=self.run_route('foreign')
        self.assertEqual(s.failure(error,'launch')['outcome'],'BLOCKED')
        self.assertFalse(any(c[:2]==['exec-out','uiautomator'] for c in device.calls))
        self.assertTrue(cleanup['complete'])

    def test_missing_usb_busy_service_and_old_partial_have_no_ui_actions(self):
        for fault in ['no-usb','busy','old-partial']:
            with self.subTest(fault=fault):
                _,device,out,_,error,cleanup=self.run_route(fault)
                self.assertIsNotNone(error);self.assertTrue(cleanup['complete'])
                self.assertFalse(any(c[:2]==['shell','input'] or c[:3]==['shell','am','start'] for c in device.calls))
                if fault=='old-partial':self.assertEqual(next((out/'previous-captures').iterdir()).read_bytes(),b'partial\n')

    def test_no_telemetry_or_wrong_target_not_automatic_success(self):
        for fault in ['missing-producer','wrong-target']:
            with self.subTest(fault=fault):
                _,_,_,report,error,cleanup=self.run_route(fault)
                self.assertIsNone(report);self.assertIsNotNone(error);self.assertTrue(cleanup['unresolved'])

    def test_uncertain_tap_is_not_replayed(self):
        _,device,_,_,error,cleanup=self.run_route('tap-timeout')
        self.assertEqual(sum(c[:3]==['shell','input','tap'] for c in device.calls),1)
        self.assertIsNotNone(error);self.assertTrue(cleanup['unresolved'])

    def test_partial_footer_and_remote_hash_preserve_original(self):
        for fault in ['missing-footer','remote-hash']:
            with self.subTest(fault=fault):
                _,device,out,report,error,cleanup=self.run_route(fault)
                self.assertIsNotNone(error);self.assertIsNone(report)
                preserved=out/('unsealed-prefix.jsonl' if fault=='missing-footer' else 'app-capture.jsonl')
                self.assertTrue(preserved.is_file())
                self.assertTrue(device.raw.startswith(preserved.read_bytes()))
                self.assertTrue(cleanup['unresolved'])

    def test_disconnected_bootstrap_reaches_query_without_extra_record_start(self):
        _,device,_,report,error,cleanup=self.run_route('bootstrap-disconnected')
        self.assertIsNone(error);self.assertTrue(cleanup['complete']);self.assertIsNotNone(report)
        self.assertFalse(device.rows[0]['freshConnection'])
        self.assertTrue(any(row['event']=='identity' and row['freshConnection'] for row in device.rows))

    def test_query_timeout_stops_owned_idle_capture_once_without_replaying_query(self):
        _,device,out,report,error,cleanup=self.run_route('query-timeout')
        self.assertIsNotNone(error);self.assertIsNone(report)
        self.assertEqual(sum(c[:3]==['shell','input','tap'] and c[-2:]==['180','50'] for c in device.calls),1)
        self.assertTrue(cleanup['complete']);self.assertFalse(cleanup['unresolved'])
        self.assertEqual((out/'app-capture.jsonl').read_bytes(),device.raw)

    def test_cleanup_failure_remains_explicit(self):
        _,_,_,report,error,cleanup=self.run_route('cleanup')
        self.assertIsNone(error);self.assertIsNotNone(report)
        self.assertFalse(cleanup['complete'])

    def test_product_failures_finish_capture_original_retrieval_and_cleanup(self):
        for fault in ['false-link','false-fresh','false-both','drop-after-identity']:
            with self.subTest(fault=fault):
                driver,device,out,report,error,cleanup=self.run_route(fault)
                self.assertIsNone(error);self.assertEqual(report['testOutcome'],'FAIL')
                self.assertEqual(report['integrity'],'VERIFIED');self.assertFalse(report['identityBound'])
                self.assertTrue(cleanup['complete']);self.assertFalse(cleanup['unresolved'])
                self.assertTrue(driver.original_verified);self.assertTrue(driver.capture_resolved)
                self.assertFalse(device.active)
                self.assertEqual((out/'app-capture.jsonl').read_bytes(),device.raw)
                self.assertEqual(sum(c[:3]==['shell','input','tap'] for c in device.calls),8)
                self.assertEqual(len([row for row in device.rows if row['event']=='identity']),1)
                self.assertGreaterEqual(report['heartbeats'],3)

    def test_changed_identity_is_still_fatal_not_completed_product_failure(self):
        _,device,_,report,error,cleanup=self.run_route('changed-after-identity')
        self.assertIsNone(report);self.assertEqual(error.code,'IDENTITY_MISMATCH')
        self.assertTrue(cleanup['unresolved']);self.assertTrue(device.active)

    def test_product_failure_does_not_mask_host_cleanup_failure(self):
        _,_,_,report,error,cleanup=self.run_route('false-both-cleanup')
        self.assertIsNone(error);self.assertEqual(report['testOutcome'],'FAIL')
        self.assertFalse(cleanup['complete'])

    def test_terminal_entry_drives_entire_real_route_and_reports_product_verdict(self):
        for fault in [None,'false-both','drop-after-identity','false-both-cleanup']:
            with self.subTest(fault=fault):
                _,device,out,report,error,cleanup=self.run_route(fault,terminal=True)
                self.assertIsNone(error);self.assertIsNotNone(report)
                self.assertEqual(device.exit_code,0 if fault is None else 1)
                result=device.result
                self.assertEqual(result['automationOutcome'],'STOPPED' if fault=='false-both-cleanup' else 'COMPLETED')
                self.assertEqual(result['testOutcome'],'PASS' if fault is None else 'FAIL')
                self.assertEqual(result['aiCalls'],0);self.assertEqual(result['otaOperations'],0)
                self.assertEqual((out/'app-capture.jsonl').read_bytes(),device.raw)
                self.assertEqual(result['lockRetained'],fault=='false-both-cleanup')
                self.assertEqual(sum(c[:3]==['shell','input','tap'] for c in device.calls),8)
                self.assertEqual(json.loads((out/'report.txt').read_text())['automationOutcome'],result['automationOutcome'])

    def test_unavailable_recorder_blocks_without_start_or_restart(self):
        _,device,_,report,error,cleanup=self.run_route('recorder-unavailable')
        self.assertIsNone(report);self.assertEqual(error.code,'PRECONDITION_FAILED')
        self.assertEqual(s.failure(error,'capture-start')['outcome'],'BLOCKED')
        self.assertIsNone(device.logger);self.assertFalse(device.active)
        self.assertTrue(cleanup['complete']);self.assertFalse(cleanup['unresolved'])

    def test_authorized_closed_recorder_restart_preserves_old_logs_and_finishes_single_entry(self):
        for fault in ['closed-good','closed-false-flags']:
            with self.subTest(fault=fault):
                driver,device,out,report,error,cleanup=self.run_route(fault,initial='firmware',terminal=True,restart=True)
                self.assertIsNone(error);self.assertEqual(device.exit_code,0 if fault=='closed-good' else 1)
                self.assertEqual(device.result['automationOutcome'],'COMPLETED')
                self.assertTrue(cleanup['appRestartConfirmed']);self.assertTrue(cleanup['ownedAppClosed'])
                self.assertEqual((cleanup['appRestartAttempts'],cleanup['ownedAppStopAttempts']),(1,1))
                self.assertFalse(device.result['lockRetained']);self.assertIsNone(device.pid)
                old=out/'previous-captures'/('e'*32+'.jsonl')
                self.assertEqual(old.read_bytes(),device.old_raw)
                self.assertEqual((out/'after-restart-captures'/old.name).read_bytes(),device.old_raw)
                self.assertEqual((out/'app-capture.jsonl').read_bytes(),device.raw)
                self.assertEqual(driver.capture_id,'d'*32)
                self.assertEqual(sum('force-stop' in c for c in device.calls),2)
                self.assertEqual(sum(row['event']=='identity' for row in device.rows),1)

    def test_permission_never_restarts_a_fresh_recorder(self):
        _,device,_,report,error,cleanup=self.run_route(terminal=True,restart=True)
        self.assertIsNone(error);self.assertEqual(device.exit_code,0)
        self.assertEqual(cleanup['appRestartAttempts'],0)
        self.assertFalse(any('force-stop' in c for c in device.calls))

    def test_closed_recorder_without_permission_busy_or_bad_old_log_has_no_process_stop(self):
        for fault,restart in [('closed-good',False),('restart-busy-ui',True),
                              ('restart-old-partial',True),('restart-unknown-status',True)]:
            with self.subTest(fault=fault,restart=restart):
                _,device,_,report,error,cleanup=self.run_route(fault,initial='firmware',restart=restart)
                self.assertIsNone(report);self.assertIsNotNone(error)
                self.assertFalse(any('force-stop' in c for c in device.calls));self.assertIsNone(device.logger)

    def test_uncertain_restart_pid_or_foreground_never_replays_restart_or_starts_capture(self):
        for fault in ['restart-timeout','restart-pid-survives','restart-same-pid','restart-foreign',
                      'restart-old-changed','restart-store-changed']:
            with self.subTest(fault=fault):
                _,device,out,report,error,cleanup=self.run_route(fault,initial='firmware',restart=True)
                self.assertIsNone(report);self.assertIsNotNone(error);self.assertIsNone(device.logger)
                self.assertTrue(cleanup['unresolved'])
                self.assertEqual(sum('force-stop' in c for c in device.calls),1)
                self.assertTrue((out/'previous-captures'/('e'*32+'.jsonl')).is_file())
                if fault in {'restart-old-changed','restart-store-changed'}:
                    self.assertTrue(cleanup['ownedAppLaunchConfirmed'])
                    self.assertFalse(cleanup['appRestartConfirmed'])
                    self.assertEqual(cleanup['ownedAppStopAttempts'],0)
                    self.assertFalse(cleanup['ownedAppClosed'])

    def test_owned_test_app_stop_timeout_cannot_claim_automation_completed(self):
        _,device,out,report,error,cleanup=self.run_route('owned-stop-timeout',initial='firmware',terminal=True,restart=True)
        self.assertIsNone(error);self.assertIsNotNone(report)
        self.assertEqual(device.exit_code,2);self.assertEqual(device.result['automationOutcome'],'STOPPED')
        self.assertTrue(device.result['lockRetained']);self.assertFalse(cleanup['complete'])
        self.assertEqual(sum('force-stop' in c for c in device.calls),2)
        self.assertEqual((out/'app-capture.jsonl').read_bytes(),device.raw)


class EntryTests(unittest.TestCase):
    def test_launch_return_without_ui_confirmation_reconciles_only_bound_safe_owner(self):
        for kind in ('safe','campaign','inspect','foreign','pid-change','new-file','busy','stop-timeout',
                     'exited','exited-replacement','exited-busy','exited-empty-services','exited-new-file',
                     'unknown-return','missing-closure','stream-change','extra-mutation','historical-only'):
            with self.subTest(kind=kind), self.root() as (root,config):
                h=self.h;prior=h.fresh(root/'prior');out=root/'recovered';p=plan();pkg=p['app']['id']
                original=dict(outcome='BLOCKED',lockRetained=True,otaOperations=0,radioToggles=0,installOperations=0,
                    cleanup=dict(ownedAppLaunchConfirmed=False))
                if kind=='campaign':
                    p['device'].update(expected_version=30293,expected_sha256='c'*64)
                    config=root/'bound-configuration.json'
                    h.save(config,p)
                    cp=fixtures.plan();cp.update(phone=p['phone'],app=p['app'])
                    cp['firmware'].update(device_address=p['device']['address'],
                        current=dict(version=p['device']['expected_version'],sha256=p['device']['expected_sha256']))
                    h.save(prior/'plan.json',cp)
                    h.save(prior/'inputs.json',dict(mode='run',planSha256=hashlib.sha256((prior/'plan.json').read_bytes()).hexdigest()))
                    original=dict(outcome='UNRESOLVED_STATE',lockRetained=True,cases=[],recovered=0,
                        caseResults=[dict(id=c['id'],outcome='NOT_RUN') for c in cp['cases']],
                        executionError=dict(code='UI_UNAVAILABLE'),cleanup=dict(captureState='NOT_ARMED',armAttempts=0,
                            stopAttempts=0,ownedAppStopAttempts=0,appRestartAttempts=0,ownedAppLaunchConfirmed=False))
                else:
                    h.save(prior/'inputs.json',dict(configurationSha256=hashlib.sha256(config.read_bytes()).hexdigest()))
                h.save(prior/'result.json',original)
                h.save(prior/'usb/closed.json',dict(cleanup_complete=True,server_closed=True,listening=False))
                h.save(prior/'journal/00001.json',dict(event='launch-intent'))
                probe='if [ -d "$1" ]; then echo directory; elif [ ! -e "$1" ]; then echo missing; else echo unknown; fi'
                remote='/sdcard/Android/data/'+pkg+'/files/p35-observations'
                component=pkg+'/MainActivity'
                commands=[(['sh','-c',probe,'sh',remote],b'missing\n'),
                    (['cmd','package','resolve-activity','--brief',pkg],(component+'\n').encode()),
                    (['pidof',pkg],b''),(['am','start','-W','-n',component],
                        b'' if kind=='unknown-return' else ('Status: ok\nActivity: '+component+'\nComplete\n').encode()),
                    (['pidof',pkg],b'1234\n'),(['pidof',pkg],b'1234\n'),
                    (['dumpsys','window'],fixtures.window_dump(('mCurrentFocus=Window{aaa u0 '+pkg+'/MainActivity}\n').encode()))]
                if kind=='extra-mutation':commands.append((['input','tap','1','1'],b''))
                base=[str(Path(p['phone']['adb']['path']).resolve()),'-H','127.0.0.1','-P','5093','-s',p['phone']['serial']]
                for i,(cmd,data) in enumerate(commands,1):
                    label='adb-%05d'%i;argv=base+['shell',s.shlex.join(cmd)]
                    h.save(prior/'usb'/(label+'.started.json'),dict(argv=argv,cwd=str(root),monotonic_ns=i*10))
                    stdout=h.raw(prior/'usb'/(label+'.stdout'),data);stderr=h.raw(prior/'usb'/(label+'.stderr'),b'')
                    if kind=='missing-closure' and i==4:continue
                    if kind=='stream-change' and i==4:stdout=dict(stdout,sha256='0'*64)
                    h.save(prior/'usb'/(label+'.closed.json'),dict(argv=argv,cleanup_complete=True,reason='completed',
                        stopped_while_running=False,exit_code=0,started_monotonic_ns=i*10,ended_monotonic_ns=i*10+1,
                        stdout=stdout,stderr=stderr))
                lock=root/'.cache/p34-live-device.lock';h.save(lock,dict(pid=123,out=str(prior)))
                old_lock=lock.read_bytes();old_result=(prior/'result.json').read_bytes()
                device=SyntheticDevice(out,h,fault={'foreign':'foreign','busy':'busy','historical-only':'window-history-only',
                    'stop-timeout':'owned-stop-timeout'}.get(kind),initial='home')
                if kind=='pid-change':device.pid='9876'
                if kind=='new-file':device.raw=archive([state()])
                if kind=='stop-timeout':device.restarted=True;device.cold=False
                if kind.startswith('exited'):
                    device.pid=None;device.fault='foreign'
                    if kind=='exited-new-file':device.raw=archive([state()])
                class Driver(s.Smoke):
                    def start_phone(self):
                        self.phone.server=device.process(self.phone.out,'adb-server',[],{})
                        self.phone.close=lambda:self.phone.server.close('synthetic finished')
                    def cmd(self,args,**kwargs):
                        if kind.startswith('exited') and args[:4]==['shell','dumpsys','activity','services']:
                            device.calls.append(args)
                            if kind=='exited-empty-services':return b''
                            return b'ACTIVITY MANAGER SERVICES (dumpsys activity services)\n'+(b'DeviceOtaService' if kind=='exited-busy' else b'')
                        if kind=='exited-replacement' and args==['shell','pidof',pkg] and any(c==args for c in device.calls):
                            device.pid='9876'
                        return device.command(args)
                with patch.object(h,'command',lambda *a,**k:b'INFO: No tasks match\n'),\
                     patch.object(h,'listening',lambda port:bool(device.server and device.server.alive())),\
                     patch.object(s,'Smoke',Driver),patch.object(s.time,'monotonic',device.mono),patch.object(s.time,'sleep',device.sleep):
                    try:code=s.reconcile(p,config.read_bytes(),prior,out,h,inspect_only=kind=='inspect')
                    except (r.Stop,RuntimeError):code=2
                self.assertEqual((prior/'result.json').read_bytes(),old_result)
                self.assertEqual(len(list((prior/'journal').glob('*.json'))),1)
                self.assertFalse(any(c[:3]==['shell','input','tap'] for c in device.calls))
                if kind in ('safe','campaign','exited'):
                    self.assertEqual(code,0);self.assertFalse(lock.exists())
                    self.assertEqual(sum('force-stop' in c for c in device.calls),0 if kind=='exited' else 1)
                    if kind=='exited':
                        self.assertTrue(h.read_json(out/'result.json')['inspection']['originalProcessAbsentVerified'])
                        self.assertFalse(any(c[:3]==['shell','am','start'] or c[:2]==['exec-out','uiautomator'] for c in device.calls))
                    else:self.assertTrue(h.read_json(out/'result.json')['cleanup']['ownedAppClosed'])
                else:
                    self.assertIn(code,(1,2));self.assertEqual(lock.read_bytes(),old_lock)
                    self.assertEqual(sum('force-stop' in c for c in device.calls),1 if kind=='stop-timeout' else 0)

    def test_file_zero_log_recovery_closed_active_partial_ambiguous_and_changed_process(self):
        for kind in ['sealed','background-sealed','unready-sealed','active','unhealthy','header','partial','many','pid-changed',
                     'app-exited','previously-sealed-app-exited','no-start','inspect-only',
                     'prearm','prearm-home','prearm-background','prearm-background-inspect','prearm-inspect','prearm-no-return','prearm-new-file',
                     'prearm-pid-change','prearm-foreign','prearm-busy']:
            with self.subTest(kind=kind),self.root() as (root,config):
                h=self.h;prior=h.fresh(root/'prior');out=root/'recovered'
                original=dict(outcome='BLOCKED',lockRetained=True,otaOperations=0,radioToggles=0,installOperations=0,
                    executionError=dict(stage='capture-start',code='TIMEOUT'),cleanup=dict(ownedAppLaunchConfirmed=True))
                h.save(prior/'result.json',original)
                h.save(prior/'usb/closed.json',dict(cleanup_complete=True,server_closed=True,listening=False))
                h.save(prior/'inputs.json',dict(configurationSha256=hashlib.sha256(config.read_bytes()).hexdigest()))
                h.save(prior/'journal/00001.json',dict(event='launch-confirmed',pid='1234'))
                prearm=kind.startswith('prearm')
                h.save(prior/'journal/00002.json',dict(event='tap-intent',control=s.DEVICES if prearm else s.ARM))
                if kind!='prearm-no-return':h.save(prior/'journal/00003.json',dict(event='tap-returned'))
                if not prearm:h.raw(prior/'logcat.stdout',b'')
                lock=root/'.cache/p34-live-device.lock';h.save(lock,dict(pid=123,out=str(prior)))
                original_lock=lock.read_bytes();original_result=(prior/'result.json').read_bytes()
                if kind=='previously-sealed-app-exited':
                    recovered=h.fresh(root/'previous-recovery')
                    recovered_raw=archive([state()]);seal=s.sealed_file(recovered_raw,'e'*32)
                    h.raw(recovered/'app-capture.jsonl',recovered_raw);h.raw(recovered/'owner-lock.json',original_lock)
                    h.save(recovered/'result.json',dict(outcome='BLOCKED',recordStarts=0,stopAttempts=0,captureResolved=True,
                        integrity=seal,inspection=dict(classification='A',sameProcess=True,originalPid='1234',currentPid='1234'),
                        cleanup=dict(complete=False,captureResolved=True,ownedAppStopAttempts=0,
                            errors=[dict(step='owned-app',code='UI_UNAVAILABLE')])))
                    h.save(recovered/'usb/closed.json',dict(cleanup_complete=True,server_closed=True,listening=False))
                    h.save(recovered/'journal/00001.json',dict(event='launch-intent'))
                    h.save(recovered/'journal/00002.json',dict(event='launch-confirmed',pid='1234'))
                    h.save(root/'.cache/p35-reconcile-device.lock',dict(pid=123,out=str(recovered),
                        originalOwnerSha256=hashlib.sha256(original_lock).hexdigest()))
                fault='file-many' if kind=='many' else 'file-background-sealed' if kind in {'background-sealed','prearm-background','prearm-background-inspect'} else 'file-sealed-unready' if kind=='unready-sealed' else 'file-empty-logcat'
                if kind=='prearm-foreign':fault='foreign'
                if kind=='prearm-busy':fault='busy'
                device=SyntheticDevice(out,h,fault=fault,initial='list' if prearm else 'firmware')
                if kind=='prearm-home':device.page='home'
                device.rows=[state()];device.seq=1
                full=archive(device.rows)
                if kind=='unhealthy':full=unhealthy_archive(full)
                device.raw=full
                if kind in {'active','inspect-only'}:device.raw=full[:full.rfind(b'OTA_P35_CAPTURE ')];device.active=True
                if kind in {'header','partial'}:
                    device.raw=full.splitlines(keepends=True)[0]+(b'OTA_P35_STATE {"seq":' if kind=='partial' else b'')
                    device.active=True
                if kind=='no-start':device.raw=b''
                if prearm and kind!='prearm-new-file':device.raw=b'';device.rows=[];device.seq=0
                if kind=='pid-changed':device.pid='9876'
                if kind=='prearm-pid-change':device.pid='9876'
                if kind in {'app-exited','previously-sealed-app-exited'}:device.pid=None
                class Driver(s.Smoke):
                    def start_phone(self):
                        self.phone.server=device.process(self.phone.out,'adb-server',[],{})
                        self.phone.close=lambda:self.phone.server.close('synthetic finished')
                    def cmd(self,args,**kwargs):return device.command(args)
                with patch.object(h,'command',lambda *a,**k:b'INFO: No tasks match\n'),\
                     patch.object(h,'pinned',lambda item:Path('synthetic')),\
                     patch.object(h,'listening',lambda port:bool(device.server and device.server.alive())),\
                     patch.object(s,'Smoke',Driver),patch.object(s.time,'monotonic',device.mono),patch.object(s.time,'sleep',device.sleep):
                    code=s.reconcile(plan(),config.read_bytes(),prior,out,h,inspect_only=kind in {'inspect-only','prearm-inspect','prearm-background-inspect'})
                report=h.read_json(out/'result.json')
                self.assertEqual((prior/'result.json').read_bytes(),original_result)
                self.assertFalse(any(c[0] in {'install','uninstall'} for c in device.calls))
                launches=[c for c in device.calls if c[:3]==['shell','am','start']]
                self.assertEqual(len(launches),1 if kind in {'background-sealed','prearm-background','prearm-foreign'} else 0)
                self.assertEqual(report['recordStarts'],0)
                if report.get('cleanup') and 'armAttempts' in report['cleanup']:self.assertEqual(report['cleanup']['armAttempts'],0)
                self.assertFalse(report['freshIdentityClaimed']);self.assertFalse(report['smokeReplayed'])
                self.assertFalse(device.server.alive())
                if kind in {'sealed','background-sealed','unready-sealed','active','unhealthy','no-start',
                            'previously-sealed-app-exited','prearm','prearm-home','prearm-background'}:
                    self.assertEqual(code,0);self.assertTrue(report['ownerReleased']);self.assertFalse(lock.exists())
                    self.assertEqual(report['stopAttempts'],1 if kind=='active' else 0)
                    if kind=='unhealthy':self.assertEqual(report['testOutcome'],'FAIL');self.assertFalse(report['recoveredCaptureHealthy'])
                    if kind in {'prearm','prearm-home','prearm-background'}:
                        self.assertEqual(report['inspection']['captureState'],'PRE_ARM_NAVIGATION_VERIFIED')
                        self.assertEqual(sum('force-stop' in c for c in device.calls),1)
                else:
                    self.assertEqual(code,2);self.assertEqual(lock.read_bytes(),original_lock)
                    self.assertEqual(report['stopAttempts'],0)
                    self.assertFalse(any('force-stop' in c for c in device.calls))

    def test_file_recovery_lease_sealed_confirmed_restore_is_not_an_unresolved_stop(self):
        for kind in ['confirmed','confirmed-prearm','unconfirmed','stop-attempted','changed-original','live-owner']:
            with self.subTest(kind=kind),self.root() as (root,config):
                h=self.h;old=h.fresh(root/'old-recovery');out=h.fresh(root/'next')
                lock_bytes=b'exact original owner'
                raw=archive([state()]);seal=s.sealed_file(raw,'e'*32)
                result=dict(outcome='BLOCKED',recordStarts=0,stopAttempts=0,captureResolved=True,integrity=seal,
                    inspection=dict(originalPid='1234',currentPid='1234'),
                    cleanup=dict(complete=False,captureResolved=True,ownedAppStopAttempts=1 if kind=='stop-attempted' else 0,
                        errors=[dict(step='owned-app',code='UI_UNAVAILABLE')]))
                if kind=='confirmed-prearm':
                    result.update(captureResolved=False,integrity=None,
                        inspection=dict(originalPid='1234',currentPid='1234',preArmActionsVerified=True,
                                        sameProcess=True,baselineUnchanged=True,candidateCount=0),
                        cleanup=dict(complete=True,captureResolved=False,ownedAppStopAttempts=0,errors=[]))
                h.save(old/'result.json',result)
                h.raw(old/'owner-lock.json',lock_bytes)
                if kind!='confirmed-prearm':h.raw(old/'app-capture.jsonl',raw+b'changed' if kind=='changed-original' else raw)
                h.save(old/'usb/closed.json',dict(cleanup_complete=True,server_closed=True,listening=False))
                h.save(old/'journal/00001.json',dict(event='launch-intent'))
                if kind!='unconfirmed':h.save(old/'journal/00002.json',dict(event='launch-confirmed',pid='1234'))
                lease=root/'.cache/p35-reconcile-device.lock'
                h.save(lease,dict(pid=123,out=str(old),originalOwnerSha256=hashlib.sha256(lock_bytes).hexdigest()))
                original=lease.read_bytes()
                data=b'"python.exe","123","Console"\n' if kind=='live-owner' else b'INFO: No tasks match\n'
                with patch.object(h,'command',lambda *a,**k:data):
                    if kind in {'confirmed','confirmed-prearm'}:
                        s.reclaim_query_only_lease(h,lease,out,lock_bytes)
                        self.assertFalse(lease.exists());self.assertEqual((out/'previous-recovery-lease.json').read_bytes(),original)
                    else:
                        with self.assertRaises(r.Stop):s.reclaim_query_only_lease(h,lease,out,lock_bytes)
                        self.assertEqual(lease.read_bytes(),original)

    @classmethod
    def setUpClass(cls):
        cls.h=r.load_host()
        sys.path.insert(0,str(r.ROOT/'Tools/ota/p34-acceptance'))
        import live_phone
        cls.area=cls.h.fresh(Path(os.environ.get('P35_SMOKE_TEST_OUT', r.ROOT/'.cache/p35-standalone-selftest-20261029'))/('entry-'+uuid.uuid4().hex))

    @contextmanager
    def root(self):
        root=self.h.fresh(self.area/('case-'+uuid.uuid4().hex))
        config=root/'configuration.json'
        self.h.save(config,plan())
        cwd=Path.cwd()
        try:
            os.chdir(root)
            with patch.object(s,'ROOT',root),patch.object(self.h,'ROOT',root),\
                 patch.object(r,'load_host',lambda:self.h),patch.object(self.h,'pinned',lambda item:Path('synthetic')):
                yield root,config
        finally:
            os.chdir(cwd)

    def driver(self, *, error=None, cleanup_error=False, unresolved=False, throw_cleanup=False, product_fail=False):
        class Driver:
            def __init__(self,*args):self.stage='capture-observe'
            def start(self):pass
            def navigate(self):pass
            def record_smoke(self):
                if error:raise error
                return dict(integrity='VERIFIED',synthetic=True,testOutcome='FAIL' if product_fail else 'PASS',
                    failures=[dict(stage='fresh-identity',code='IDENTITY_NOT_FRESH')] if product_fail else [])
            def cleanup(self):
                if throw_cleanup:raise RuntimeError('unexpected synthetic cleanup exception')
                return dict(complete=not cleanup_error,errors=[],unresolved=unresolved,captureResolved=not unresolved)
        return Driver

    def test_real_report_exit_codes_and_lock_closure(self):
        for error,cleanup_error,unresolved,expected in [
            (None,False,False,0),(r.Stop('ENV_BLOCKED','synthetic phone missing'),False,False,2),
            (r.Stop('EVIDENCE_GAP','synthetic missing evidence'),False,False,1),
            (r.Stop('EVIDENCE_GAP','synthetic unknown capture'),False,True,2), (None,True,False,1)]:
            with self.subTest(expected=expected),self.root() as (root,config),\
                 patch.object(s,'Smoke',self.driver(error=error,cleanup_error=cleanup_error,unresolved=unresolved)):
                out=root/'evidence'
                self.assertEqual(s.main(['smoke','--plan',str(config),'--out',str(out),'--execute']),expected)
                result=self.h.read_json(out/'result.json')
                self.assertEqual(result['outcome'],{0:'PASS',1:'FAIL',2:'BLOCKED'}[expected])
                self.assertEqual(result['testOutcome'],result['outcome'])
                self.assertEqual(result['automationOutcome'],'COMPLETED' if expected==0 else 'STOPPED')
                self.assertEqual((root/'.cache/p34-live-device.lock').exists(),cleanup_error or unresolved)
                self.assertTrue((out/'report.txt').is_file());self.assertTrue((out/'audit.json').is_file())
                summary=json.loads((out/'report.txt').read_text())
                self.assertEqual(summary['formalAcceptance'],'NOT_ADJUDICATED')
                self.assertEqual(summary['automationOutcome'],result['automationOutcome'])
                self.assertNotIn('SYNTHETIC',(out/'plan.json').read_text())

    def test_unexpected_cleanup_exception_cannot_leave_pass(self):
        with self.root() as (root,config),patch.object(s,'Smoke',self.driver(throw_cleanup=True)):
            out=root/'evidence'
            self.assertEqual(s.main(['smoke','--plan',str(config),'--out',str(out),'--execute']),1)
            self.assertEqual(self.h.read_json(out/'result.json')['stage'],'cleanup')
            self.assertTrue((root/'.cache/p34-live-device.lock').exists())

    def test_completed_product_fail_is_exit_one_and_releases_resolved_lock(self):
        with self.root() as (root,config),patch.object(s,'Smoke',self.driver(product_fail=True)):
            out=root/'evidence'
            self.assertEqual(s.main(['smoke','--plan',str(config),'--out',str(out),'--execute']),1)
            result=self.h.read_json(out/'result.json')
            self.assertEqual((result['automationOutcome'],result['testOutcome']),('COMPLETED','FAIL'))
            self.assertEqual(result['stage'],'fresh-identity');self.assertEqual(result['code'],'IDENTITY_NOT_FRESH')
            self.assertTrue(result['cleanup']['complete']);self.assertFalse(result['lockRetained'])
            self.assertFalse((root/'.cache/p34-live-device.lock').exists())
            summary=json.loads((out/'report.txt').read_text())
            self.assertEqual(summary['automationOutcome'],'COMPLETED');self.assertEqual(summary['exitCode'],1)

    def test_failed_product_with_cleanup_error_cannot_claim_completion(self):
        for throw in [False,True]:
            with self.subTest(throw=throw),self.root() as (root,config),\
                 patch.object(s,'Smoke',self.driver(product_fail=True,cleanup_error=True,throw_cleanup=throw)):
                out=root/'evidence'
                self.assertEqual(s.main(['smoke','--plan',str(config),'--out',str(out),'--execute']),1)
                result=self.h.read_json(out/'result.json')
                self.assertEqual(result['automationOutcome'],'STOPPED');self.assertEqual(result['stage'],'cleanup')
                self.assertTrue(result['lockRetained'])

    def test_previous_live_dead_or_unknown_owner_never_authorizes_replay(self):
        for owner_result in [b'"python.exe","123","Console"\n',b'INFO: No tasks match\n',None]:
            with self.subTest(owner_result=owner_result),self.root() as (root,config):
                prior=self.h.fresh(root/'prior')
                self.h.save(prior/'result.json',dict(outcome='UNKNOWN',action='record-start'))
                lock=root/'.cache/p34-live-device.lock'
                self.h.save(lock,dict(pid=123,out=str(prior)))
                original=lock.read_bytes()
                def owner_check(*args,**kwargs):
                    if owner_result is None:raise RuntimeError('owner liveness unknown')
                    return owner_result
                out=root/'evidence'
                with patch.object(self.h,'command',owner_check),patch.object(s,'Smoke') as constructor:
                    self.assertEqual(s.main(['smoke','--plan',str(config),'--out',str(out),'--execute']),2)
                    constructor.assert_not_called()
                self.assertEqual(lock.read_bytes(),original)
                if owner_result and owner_result.startswith(b'INFO'):
                    self.assertEqual((out/'previous-owner-results/result.json').read_bytes(),(prior/'result.json').read_bytes())

    def test_existing_output_and_missing_execute_have_no_side_effects(self):
        with self.root() as (root,config),patch.object(s,'Smoke') as constructor:
            out=self.h.fresh(root/'evidence')
            with self.assertRaises(r.Stop):s.main(['smoke','--plan',str(config),'--out',str(out),'--execute'])
            with self.assertRaises(r.Stop):s.main(['smoke','--plan',str(config),'--out',str(root/'not-created')])
            self.assertFalse((root/'not-created').exists());constructor.assert_not_called()

    def test_actual_isolated_cli_checks_no_adb_or_ai(self):
        h=self.h
        out=h.fresh(self.area/('cli-'+uuid.uuid4().hex))
        config=out/'configuration.json';h.save(config,plan())
        env=h.environment(out)
        base=[sys.executable,'-I','-S','-B','-X','utf8',r.ROOT/'Tools/ota/p35-automation/runner.py']
        for label,args,expected in [
            ('help',['--help'],0),('check',['smoke-check','--plan',str(config)],0),
            ('template',['smoke-check','--plan',str(r.ROOT/'Tools/ota/p35-automation/smoke.example.json')],2),
            ('scope',['smoke','--plan',str(config),'--out',str(out/'not-created')],2)]:
            h.command(out,label,base+args,env,seconds=20,success_codes=(expected,))
        self.assertFalse((out/'not-created').exists())

    def test_reconcile_closes_only_owned_idle_capture_preserves_failure_and_old_lock(self):
        for kind in ['open','closed','stop-timeout','wrong-target','release','release-open','release-changed',
                     'release-busy','release-cleanup']:
            with self.subTest(kind=kind),self.root() as (root,config):
                h=self.h
                prior=h.fresh(root/'prior')
                raw_config=config.read_bytes()
                original=dict(outcome='FAIL',lockRetained=True,otaOperations=0,radioToggles=0,installOperations=0)
                h.save(prior/'result.json',original)
                h.save(prior/'usb/closed.json',dict(cleanup_complete=True,server_closed=True,listening=False))
                h.save(prior/'inputs.json',dict(configurationSha256=hashlib.sha256(raw_config).hexdigest()))
                h.save(prior/'journal/00001.json',dict(event='launch-confirmed',pid='1234'))
                full=archive([state(linkConnected=False,freshConnection=False)])
                prefix=full[:full.rfind(b'OTA_P35_CAPTURE ')]
                h.raw(prior/'logcat.stdout',prefix)
                sealed=prior/'sealed.jsonl';h.raw(sealed,full)
                lock=root/'.cache/p34-live-device.lock';h.save(lock,dict(pid=123,out=str(prior)))
                original_lock=lock.read_bytes();original_result=(prior/'result.json').read_bytes()
                actions=[]
                class Driver:
                    def __init__(self,p,out,h):self.stage='reconcile-owner';self.out=out
                    def start_phone(self):self.stage='preflight'
                    def ui(self):
                        if kind.startswith('release'):
                            return xml(node(identifier='p35-check',clickable=kind!='release-busy'))
                        return b'owned native UI'
                    def idle_services(self):pass
                    def foreground_existing(self,pid):self.pid=pid
                    def enter(self,name):self.stage=name
                    def prefix(self,cid,path):
                        data=full if kind in {'closed','release','release-busy','release-cleanup'} or actions else prefix
                        if kind=='release-changed':
                            data=archive([state(linkConnected=False,freshConnection=False,monoUs=2000000)])
                        if kind=='wrong-target':data=data.replace(b'aa:bb:cc:dd:ee:ff',b'11:22:33:44:55:66')
                        h.raw(path,data);return data
                    def tap(self,wanted):
                        self.assert_stop=wanted==s.STOP
                        if not self.assert_stop:raise AssertionError('non-stop recovery action')
                        actions.append(wanted)
                        self.mutation_unknown=True
                        if kind=='stop-timeout':raise r.Stop('TIMEOUT','stop outcome unknown')
                    def wait(self,check):return check()
                    def original(self,cid,path):h.raw(path,full);return full
                    def cleanup(self):return dict(complete=kind!='release-cleanup',errors=[],unresolved=getattr(self,'mutation_unknown',False),
                        captureResolved=getattr(self,'capture_resolved',False))
                out=root/'recovered'
                with patch.object(h,'command',lambda *a,**k:b'INFO: No tasks match\n'),\
                     patch.object(h,'listening',lambda port:False),patch.object(s,'Smoke',Driver):
                    code=s.reconcile(plan(),raw_config,prior,out,h,
                        sealed_original=sealed if kind.startswith('release') else None)
                if kind=='release':
                    self.assertFalse(lock.exists())
                    self.assertEqual((out/'owner-lock.json').read_bytes(),original_lock)
                    self.assertEqual((out/'previous-sealed-original.jsonl').read_bytes(),full)
                    self.assertEqual(h.read_json(out/'result.json')['outcome'],'ORIGINAL_OWNER_RESOLVED')
                    self.assertTrue(h.read_json(out/'result.json')['ownerReleased'])
                    self.assertFalse((root/'.cache/p35-reconcile-device.lock').exists())
                    self.assertEqual(code,0);self.assertEqual(actions,[])
                    self.assertEqual((prior/'result.json').read_bytes(),original_result)
                    continue
                self.assertEqual(lock.read_bytes(),original_lock)
                self.assertEqual((prior/'result.json').read_bytes(),original_result)
                self.assertLessEqual(len(actions),1)
                if kind in {'open','closed'}:
                    self.assertEqual(code,0)
                    self.assertEqual(len(actions),0 if kind=='closed' else 1)
                    self.assertFalse((root/'.cache/p35-reconcile-device.lock').exists())
                    report=h.read_json(out/'result.json')
                    self.assertEqual(report['outcome'],'ORIGINALS_RECOVERED')
                    self.assertFalse(report['smokeReplayed']);self.assertFalse(report['freshIdentityClaimed'])
                    self.assertTrue(report['cleanup']['captureResolved']);self.assertFalse(report['cleanup']['unresolved'])
                else:
                    self.assertNotEqual(code,0)
                    self.assertTrue((root/'.cache/p35-reconcile-device.lock').exists())
                    if kind.startswith('release'):self.assertEqual(actions,[])

    def test_recovery_lease_without_device_lock_still_blocks_new_execution(self):
        with self.root() as (root,config),patch.object(s,'Smoke') as driver:
            self.h.save(root/'.cache/p35-reconcile-device.lock',dict(pid=123,out='unresolved'))
            out=root/'evidence'
            self.assertEqual(s.main(['smoke','--plan',str(config),'--out',str(out),'--execute']),2)
            driver.assert_not_called()
            self.assertEqual(self.h.read_json(out/'result.json')['automationOutcome'],'STOPPED')

    def test_query_only_lease_reclaim_checks_owner_action_result_and_preserves_bytes(self):
        for kind in ['closed-query','live-owner','stop-intent','launch-intent','cleanup-unknown']:
            with self.subTest(kind=kind),self.root() as (root,config):
                h=self.h;prior=h.fresh(root/'old-recovery');out=h.fresh(root/'next-recovery')
                lock_bytes=b'original failed owner'
                lease=root/'.cache/p35-reconcile-device.lock'
                h.save(lease,dict(pid=123,out=str(prior),originalOwnerSha256=hashlib.sha256(lock_bytes).hexdigest()))
                raw=lease.read_bytes()
                h.save(prior/'result.json',dict(outcome='BLOCKED',stopAttempts=1 if kind=='stop-intent' else 0,
                    recordStarts=0,cleanup=dict(complete=kind!='cleanup-unknown')))
                h.save(prior/'usb/closed.json',dict(cleanup_complete=True,server_closed=True,listening=False))
                if kind=='launch-intent':h.save(prior/'journal/00001.json',dict(event='launch-intent'))
                data=b'"python.exe","123","Console"\n' if kind=='live-owner' else b'INFO: No tasks match\n'
                with patch.object(h,'command',lambda *a,**k:data):
                    if kind=='closed-query':
                        s.reclaim_query_only_lease(h,lease,out,lock_bytes)
                        self.assertFalse(lease.exists())
                        self.assertEqual((out/'previous-recovery-lease.json').read_bytes(),raw)
                    else:
                        with self.assertRaises(r.Stop):s.reclaim_query_only_lease(h,lease,out,lock_bytes)
                        self.assertEqual(lease.read_bytes(),raw)


if __name__=='__main__':
    unittest.main()
