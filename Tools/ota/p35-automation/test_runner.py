"""Offline tests only. Synthetic events are NEVER physical acceptance evidence."""
import json
import hashlib
from pathlib import Path
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parent))
import runner as r


def plan():
    pin = dict(path='not-used-by-unit-tests', bytes=1048576, sha256='a'*64)
    return dict(schema=1, run_id='p35-unit', allow_bluetooth_toggle=True,
        phone=dict(serial='UNIT', model='UNIT', adb_port=5093, adb=pin.copy(), adb_key=pin.copy()),
        app=dict(id='com.example.p35', sha256='b'*64, version_code=92, release=True),
        firmware=dict(device_address='AA:BB', protocol=1, package=pin.copy(),
            current=dict(version=30293, sha256='c'*64), target=dict(version=30294, sha256='d'*64),
            release_id='fixture-only', latest_url='https://fixture.invalid/api/public/firmware/latest'),
        ui=dict(arm={'resource-id':'p35-arm'}, stop={'resource-id':'p35-stop'},
                check={'text':'check'}, download={'text':'download'}, start={'text':'start'},
                resume={'text':'resume'}, navigate=[], reconnect=[]),
        limits=dict(total_seconds=1800, stage_seconds=120, event_seconds=5, disconnect_seconds=5),
        cases=[dict(id='R%02d' % (i+1), durable_min=offset, durable_max=offset+4095,
                    bitmap='partial' if i == 4 else 'any')
               for i, offset in enumerate([0,4096,131072,262144,393216,524288,655360,786432,917504,983040])])


def state(seq=1, **changes):
    s = dict(schema=1, captureId='e'*32, protocol=1, seq=seq, monoUs=seq*1000, deviceAddress='AA:BB', phase='idle', event='heartbeat',
        currentVersionCode=30293, currentImageSha256='c'*64, targetVersionCode=30294,
        targetImageSha256='d'*64, packageSha256='a'*64, packageBytes=1048576, packageVerified=True,
        releaseId='fixture-only', latestUrl='https://fixture.invalid/api/public/firmware/latest',
        durable=0, bitmap=0, linkConnected=True, freshConnection=True, session=1, sendOffset=None,
        healthy=True, lost=0, error=None)
    s.update(changes)
    return s


def line(s):
    return ('1700000000.000 100 100 I flutter: ' + r.PREFIX + json.dumps(s) + '\n').encode()


def xml(nodes):
    return ('<?xml version="1.0"?><hierarchy>' + nodes + '</hierarchy>\nUI hierchary dumped to: /dev/tty').encode()


def node(text='start', package='com.example.p35', **attrs):
    props = dict(text=text, package=package, clickable='true', enabled='true', bounds='[10,20][110,80]')
    props.update(attrs)
    return '<node ' + ' '.join('%s="%s"' % pair for pair in props.items()) + '/>'


def trace(p=None):
    p = p or plan()
    rows = [state(), state(phase='checkingUpdate'), state(phase='downloading'), state(phase='readyToInstall'),
            state(phase='transferring', event='beginAck')]
    for i,c in enumerate(p['cases']):
        off = c['durable_min']
        bitmap = 3 if c['bitmap'] == 'partial' else 0
        rows.extend([
            state(phase='transferring', durable=off, bitmap=bitmap),
            state(phase='failed', durable=off, bitmap=bitmap, linkConnected=False),
            state(phase='failed', durable=off, bitmap=bitmap),
            state(phase='transferring', event='beginAck', durable=off, bitmap=bitmap, session=i+2),
            state(phase='transferring', event='data', durable=off, bitmap=bitmap, session=i+2,
                  sendOffset=off+(256 if bitmap else 0)),
            state(phase='transferring', durable=off+4096, bitmap=0, session=i+2)])
    rows.append(state(phase='completed', event='identity', currentVersionCode=30294,
                      currentImageSha256='d'*64, durable=1048576))
    for n,s in enumerate(rows):
        s.update(seq=n+1, monoUs=(n+1)*1000)
    return rows


class Fake:
    def __init__(self, rows):
        self.rows = iter(rows)
        self.actions, self.records = [], []
        self.now = 0
        self.fail_disable = False
        self.radio_touched = False

    def clock(self):
        return self.now

    def next_state(self, seconds):
        self.now += .1
        try:
            return next(self.rows)
        except StopIteration:
            raise r.Stop('CAPABILITY_MISSING', 'synthetic input ended')

    def tap(self, selector):
        self.actions.append(('tap', selector))

    def radio(self, enabled, *, case=None):
        self.radio_touched = not enabled
        self.actions.append(('radio', enabled))
        if not enabled and self.fail_disable:
            raise r.Stop('ENV_BLOCKED', 'uncertain disable')

    def record(self, event, **fields):
        self.records.append((event, fields))


class PlanTests(unittest.TestCase):
    def test_valid(self):
        self.assertEqual(len(r.validate_plan(plan())['cases']), 10)

    def test_unsafe_plans(self):
        mutations = [lambda p:p.update(schema=True), lambda p:p['app'].update(release=False),
            lambda p:p['phone'].update(adb_port=5037), lambda p:p['phone'].update(serial='x;reboot'),
            lambda p:p['firmware']['target'].update(version=30292),
            lambda p:p['limits'].update(stage_seconds=float('nan')),
            lambda p:p['limits'].update(total_seconds=float('inf')),
            lambda p:p['cases'].pop(), lambda p:p['cases'][1].update(id='R01'),
            lambda p:p['cases'][1].update(durable_min=0), lambda p:p['cases'][-1].update(durable_max=1048576),
            lambda p:p['cases'][4].update(bitmap='any'), lambda p:p['ui'].update(start={'x':'1'})]
        for mutate in mutations:
            with self.subTest(mutate=mutate):
                p=plan();mutate(p)
                with self.assertRaises(r.Stop):r.validate_plan(p)

    def test_template_is_not_live_ready(self):
        with self.assertRaises(r.Stop):
            r.validate_plan(r.strict_json((Path(__file__).parent/'plan.example.json').read_bytes()))


class UITests(unittest.TestCase):
    def test_text_and_resource_id(self):
        self.assertEqual(r.find_control(xml(node(**{'resource-id':'ota-start'})),
            {'resource-id':'ota-start'}, 'com.example.p35'), (60,50))

    def test_clickable_ancestor(self):
        tree = '<node package="com.example.p35" clickable="true" enabled="true" bounds="[0,0][100,80]">'
        tree += node(clickable='false') + '</node>'
        self.assertEqual(r.find_control(xml(tree), {'text':'start'}, 'com.example.p35'), (50,40))

    def test_foreign_missing_ambiguous_disabled_invalid(self):
        for tree in [xml(node(package='other.app')), xml(node('else')), xml(node()+node()),
                     xml(node(enabled='false')), xml(node(bounds='[1,1][1,2]')),
                     b'ERROR: null root', b'<!DOCTYPE foo><hierarchy/>', xml('<broken>')]:
            with self.subTest(tree=tree):
                with self.assertRaises(r.Stop):r.find_control(tree, {'text':'start'}, 'com.example.p35')

    def test_value_key_is_not_native_identifier(self):
        with self.assertRaises(r.Stop):r.selector({'ValueKey':'ota-start'})

    def test_disabled_child_cannot_borrow_enabled_parent(self):
        parent='<node package="com.example.p35" clickable="true" enabled="true" bounds="[0,0][100,80]">'
        with self.assertRaises(r.Stop):
            r.find_control(xml(parent+node(clickable='false',enabled='false')+'</node>'),
                {'text':'start'},'com.example.p35')

    def test_hidden_control_rejected(self):
        with self.assertRaises(r.Stop):
            r.find_control(xml(node(**{'visible-to-user':'false'})),{'text':'start'},'com.example.p35')


class TelemetryTests(unittest.TestCase):
    def test_v2_never_fabricates_a_bitmap(self):
        s = state(protocol=2, bitmap=None, durable=4096)
        r.validate_state(s)
        self.assertEqual(r.resume_offset(s), 4096)
        with self.assertRaises(r.Stop): r.validate_state(dict(s, bitmap=0))

    def test_capture_change_or_explicit_writer_error_fails(self):
        d = r.Decoder(); d.feed(line(state()))
        with self.assertRaises(r.Stop): d.feed(line(state(2, captureId='f'*32)))
        with self.assertRaises(r.Stop): r.Decoder().feed(b'OTA_P35_ERROR {"error":"write-failed"}\n')

    def test_split_utf8_and_multiple_lines(self):
        d=r.Decoder();payload=line(state())+line(state(2))
        self.assertEqual(d.feed(payload[:23]), [])
        self.assertEqual([s['seq'] for s in d.feed(payload[23:])], [1,2])

    def test_no_telemetry_is_not_success(self):
        self.assertEqual(r.Decoder().feed(b'normal log\n'), [])

    def test_sequence_gap_duplicate_backwards_clock(self):
        for second in [state(3), state(1), state(2,monoUs=0)]:
            d=r.Decoder();d.feed(line(state()))
            with self.assertRaises(r.Stop):d.feed(line(second))

    def test_bad_domains(self):
        for changes in [dict(schema=True),dict(healthy=False),dict(lost=1),dict(lost=False),dict(error='disk-full'),
                        dict(durable=1),dict(durable=1048577),dict(session=256,durable=1048576),
                        dict(currentImageSha256='partial'),dict(packageVerified=1),dict(seq=-1)]:
            with self.subTest(changes=changes):
                with self.assertRaises(r.Stop):r.validate_state(state(**changes))

    def test_unknown_and_missing_fields(self):
        for s in [dict(state(),unknown=True), {k:v for k,v in state().items() if k!='bitmap'}]:
            with self.assertRaises(r.Stop):r.validate_state(s)

    def test_duplicate_json_field(self):
        with self.assertRaises(r.Stop):r.strict_json('{"schema":1,"schema":1}')

    def test_truncation_limit_and_logcat_loss(self):
        for data in [b'x'*(r.MAX_LINE+1), b'chatty dropped 4 lines\n']:
            with self.assertRaises(r.Stop):r.Decoder().feed(data)

    def test_wrong_binding(self):
        for change in [dict(currentVersionCode=30292),dict(deviceAddress='OTHER'),
            dict(packageSha256='f'*64),dict(packageVerified=False),dict(releaseId='other'),
            dict(latestUrl='https://wrong.invalid/api/public/firmware/latest')]:
            with self.subTest(change=change):
                with self.assertRaises(r.Stop):r.bound(state(**change),plan(),package=True)

    def test_bitmap_first_missing(self):
        self.assertEqual(r.resume_offset(state(durable=4096,bitmap=0b1011)),4352)
        self.assertEqual(r.resume_offset(state(durable=4096,bitmap=0xffffffff)),8192)


class CampaignTests(unittest.TestCase):
    def test_v2_campaign_uses_real_durable_resume_not_v1_bits(self):
        p = plan(); p['firmware']['protocol'] = 2
        for case in p['cases']: case['bitmap'] = 'any'
        rows = trace(p)
        for s in rows: s.update(protocol=2, bitmap=None)
        c, io = self.run_rows(rows, p)
        self.assertEqual(c.run()['recovered'], 10)
        p['cases'][4]['bitmap'] = 'partial'
        with self.assertRaises(r.Stop): r.validate_plan(p)

    def run_rows(self, rows, p=None):
        io=Fake(rows);c=r.Campaign(p or plan(),io,io.clock)
        return c,io

    def test_complete_ten_without_screenshots_or_model_steps(self):
        c,io=self.run_rows(trace());result=c.run()
        self.assertEqual(result['recovered'],10)
        self.assertEqual(result['formalAcceptance'],'NOT_ADJUDICATED')
        self.assertEqual([v for k,v in io.actions if k=='radio'], [False,True]*10)
        self.assertEqual(sum(k=='tap' for k,_ in io.actions),12)

    def test_manual_download_path(self):
        rows=trace();rows[2]['phase']='idle'
        c,io=self.run_rows(rows);c.run()
        self.assertIn(('tap',{'text':'download'}),io.actions)

    def test_no_action_on_missing_telemetry_or_wrong_initial_identity(self):
        for rows in [[], [state(currentVersionCode=30292)]]:
            c,io=self.run_rows(rows)
            with self.assertRaises(r.Stop):c.run()
            self.assertEqual(io.actions,[])

    def test_wrong_package_before_start(self):
        rows=trace();rows[3]['packageSha256']='f'*64
        c,io=self.run_rows(rows)
        with self.assertRaises(r.Stop):c.run()
        self.assertNotIn(('tap',{'text':'start'}),io.actions)

    def test_missed_boundary_never_injects(self):
        rows=trace();rows[5]['durable']=4096
        c,io=self.run_rows(rows)
        with self.assertRaises(r.Stop):c.run()
        self.assertFalse(any(k=='radio' for k,_ in io.actions))

    def test_actual_disconnect_outside_window_restores_radio(self):
        rows=trace();rows[6]['durable']=4096
        c,io=self.run_rows(rows)
        with self.assertRaises(r.Stop):c.run()
        self.assertEqual([v for k,v in io.actions if k=='radio'],[False,True])

    def test_uncertain_disable_restores_without_ui_retry(self):
        c,io=self.run_rows(trace());io.fail_disable=True
        with self.assertRaises(r.Stop):c.run()
        self.assertEqual([v for k,v in io.actions if k=='radio'],[False,True])
        self.assertNotIn(('tap',{'text':'resume'}),io.actions)

    def test_wrong_resume_send_or_session(self):
        for change in [dict(sendOffset=128),dict(session=99)]:
            rows=trace();rows[9].update(change)
            c,io=self.run_rows(rows)
            with self.assertRaises(r.Stop):c.run()
            self.assertEqual(len(c.cases),0)

    def test_final_identity_not_ui_success(self):
        for changes in [dict(currentImageSha256='f'*64),dict(freshConnection=False),dict(durable=1044480)]:
            rows=trace();rows[-1].update(changes)
            c,io=self.run_rows(rows)
            with self.assertRaises(r.Stop):c.run()

    def test_foreign_device_during_progress_rejected(self):
        rows=trace();rows[10]['deviceAddress']='OTHER'
        c,io=self.run_rows(rows)
        with self.assertRaises(r.Stop):c.run()
        self.assertEqual(len(c.cases),0)

    def test_no_durable_progress_watchdog(self):
        io=Fake([state(phase='transferring') for _ in range(5)])
        original=io.next_state
        def slow(seconds):
            s=original(seconds);io.now+=10;return s
        io.next_state=slow;c=r.Campaign(plan(),io,io.clock)
        with self.assertRaisesRegex(r.Stop,'without MCU durable'):
            c.wait(lambda _:False,'stalled')

    def test_stale_idle_cannot_trigger_download_or_start(self):
        c,io=self.run_rows([state(),state(),state()])
        with self.assertRaises(r.Stop):c.run()
        self.assertEqual(io.actions,[('tap',{'text':'check'})])

    def test_capture_loss_after_start_does_not_restart_upgrade(self):
        rows=trace()[:5]
        c,io=self.run_rows(rows)
        with self.assertRaises(r.Stop):c.run()
        self.assertEqual(io.actions.count(('tap',{'text':'start'})),1)
        self.assertFalse(any(k=='radio' for k,_ in io.actions))


class AdapterTests(unittest.TestCase):
    def test_late_boundary_is_rejected_before_any_radio_command(self):
        android = object.__new__(r.Android)
        android.p = plan(); android.pump = lambda: None
        android.decoder = r.Decoder()
        android.decoder.previous = state(phase='applying', durable=1048576)
        android.last_state_at = r.time.monotonic()
        android.radio_touched = False
        with self.assertRaisesRegex(r.Stop, 'escaped disconnect window'):
            android.radio(False, case=plan()['cases'][0])
        self.assertFalse(android.radio_touched)

    def test_radio_toggle_requires_explicit_opt_in(self):
        android=object.__new__(r.Android)
        android.p=plan();android.p['allow_bluetooth_toggle']=False
        with self.assertRaises(r.Stop):android.radio(False)

    def test_missing_capture_fails_before_ui(self):
        android=object.__new__(r.Android)
        android.capture=None
        with self.assertRaises(r.Stop):android.tap({'text':'start'})

    def test_no_second_radio_restore_command(self):
        android=object.__new__(r.Android)
        android.p=plan();android.restore_attempted=True
        with self.assertRaises(r.Stop):android.radio(True)


class ArchiveTests(unittest.TestCase):
    def archive(self):
        states = (r.PREFIX + json.dumps(state()) + '\n').encode()
        header = dict(schema=1, kind='open', captureId='e'*32)
        footer = dict(schema=1, kind='close', captureId='e'*32, records=1,
                      sha256=hashlib.sha256(states).hexdigest(), healthy=True, lost=0, error=None)
        return b'OTA_P35_CAPTURE ' + json.dumps(header).encode() + b'\n' + states + b'OTA_P35_CAPTURE ' + json.dumps(footer).encode() + b'\n'

    def test_complete_originals(self):
        self.assertEqual(r.audit_capture(self.archive(), 'e'*32)['integrity'], 'VERIFIED')

    def test_partial_tampered_or_wrong_capture_never_accepted(self):
        raw = self.archive()
        for value in [raw[:-1], raw.split(b'OTA_P35_CAPTURE ')[1],
                      raw.replace(b'"records": 1', b'"records": 2'),
                      raw.replace(b'"healthy": true', b'"healthy": false'),
                      raw.replace(b'"seq": 1', b'"seq": 2')]:
            with self.assertRaises(r.Stop): r.audit_capture(value, 'e'*32)
        with self.assertRaises(r.Stop): r.audit_capture(raw, 'f'*32)


if __name__ == '__main__':
    unittest.main()
