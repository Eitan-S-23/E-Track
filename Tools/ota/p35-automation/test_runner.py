"""Offline tests only. Synthetic events are NEVER physical acceptance evidence."""
import json
import hashlib
from pathlib import Path
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parent))
import runner as r


def window_dump(focus, *, history=b'', policy=b''):
    sections = [('policy', 'POLICY STATE', policy), ('animator', 'ANIMATOR STATE', b''),
        ('sessions', 'SESSIONS', b''), ('displays', 'DISPLAY CONTENTS', focus),
        ('tokens', 'TOKENS', b''), ('windows', 'WINDOWS', b''), ('trace', 'TRACE', b'')]
    return history + b''.join(('WINDOW MANAGER ' + title + ' (dumpsys window ' + name + ')\n').encode()
                             + body + b'\n' for name, title, body in sections)


class ForegroundTests(unittest.TestCase):
    def test_current_sections_exclude_nested_historical_display(self):
        pkg = 'com.example.p35'
        focus = ('mCurrentFocus=Window{abc u0 ' + pkg + '/MainActivity}\n').encode()
        history = b'WINDOW MANAGER LAST ANR (dumpsys window lastanr)\n'
        history += b'WINDOW MANAGER DISPLAY CONTENTS (dumpsys window displays)\n'
        history += b'mCurrentFocus=Window{def u0 foreign.app/MainActivity}\nmShowingLockscreen=true\n'
        self.assertTrue(r.foreground_ok(window_dump(b'mCurrentFocus=null\n' + focus, history=history), pkg))
        for raw in (history, focus, window_dump(focus).split(b'WINDOW MANAGER TOKENS')[0],
                    window_dump(focus).rstrip(b'\n'), window_dump(focus, policy=b'mKeyguardShowing=true\n'),
                    window_dump(focus+focus), window_dump(focus+b'mCurrentFocus=Window{aaa u0 overlay.app/Dialog}\n'),
                    window_dump(focus.replace(pkg.encode(), b'other.app'), history=history.replace(b'foreign.app', pkg.encode()))):
            with self.subTest(raw=raw):
                self.assertFalse(r.foreground_ok(raw, pkg))


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
    def test_bootstrap_cannot_be_replaced_by_an_upgrade_tap(self):
        p = plan(); p['ui']['arm'] = p['ui']['start']
        with self.assertRaises(r.Stop): r.validate_plan(p)
        android = object.__new__(r.Android)
        with self.assertRaises(r.Stop): android.tap(p['ui']['start'], bootstrap=True)

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
    def test_flutter_identifier_container_resolves_one_button_descendant(self):
        parent = '<node resource-id="p35-start" package="com.example.p35" clickable="false" enabled="true" bounds="[0,0][120,100]">'
        self.assertEqual(r.find_control(xml(parent + node() + '</node>'),
            {'resource-id': 'p35-start'}, 'com.example.p35'), (60, 50))
        for children in [node() + node(), node(enabled='false'), node(package='other.app')]:
            with self.assertRaises(r.Stop):
                r.find_control(xml(parent + children + '</node>'), {'resource-id': 'p35-start'}, 'com.example.p35')

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
    def test_case_results_require_whole_run_success_and_preserve_unrun_cases(self):
        c, io = self.run_rows(trace())
        c.run()
        self.assertEqual([row['outcome'] for row in c.case_results(complete=True)], ['PASS'] * 10)
        self.assertEqual([row['outcome'] for row in c.case_results()], ['RECOVERY_OBSERVED'] * 10)
        self.assertIsNone(c.active_case)
        rows = trace()
        second = next(s for s in rows if s['event'] == 'data' and s['durable'] == 4096)
        second['sendOffset'] = 999
        c, io = self.run_rows(rows)
        with self.assertRaises(r.Stop) as error:
            c.run()
        report = c.case_results(error_code=error.exception.code)
        self.assertEqual([row['id'] for row in report], [case['id'] for case in plan()['cases']])
        self.assertEqual([row['outcome'] for row in report], ['RECOVERY_OBSERVED', 'FAIL'] + ['NOT_RUN'] * 8)
        self.assertEqual(report[1]['stage'], 'R02-first-resumed-DATA')
        self.assertEqual(report[1]['code'], 'PRODUCT_OR_ENV_FAILURE')
        self.assertEqual(len(c.cases), 1)

    def test_case_results_never_promote_recoveries_after_failed_final_identity(self):
        rows = trace()
        rows[-1]['freshConnection'] = False
        c, io = self.run_rows(rows)
        with self.assertRaises(r.Stop):
            c.run()
        self.assertEqual(len(c.cases), 10)
        self.assertEqual([row['outcome'] for row in c.case_results()], ['RECOVERY_OBSERVED'] * 10)
        self.assertEqual(c.stage, 'post-reboot-identity')

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

    def test_historical_identity_is_not_sufficient_to_start(self):
        rows = trace(); rows[3]['freshConnection'] = False
        c, io = self.run_rows(rows)
        with self.assertRaises(r.Stop): c.run()
        self.assertNotIn(('tap', {'text': 'start'}), io.actions)

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


class RadioStateTests(unittest.TestCase):
    ENVELOPE = (b'SERVICE com.android.bluetooth/.btservice.AdapterService 854462b pid=22045 user=0\r\n'
                b'  Client:\r\n')
    # Sanitized shape of the observed --print output; no phone identifiers.
    # OFF/turning variants below are synthetic, not actual phone observations.
    ADAPTER_ON = (b'SERVICE com.android.bluetooth/.btservice.AdapterService\n'
                  b'    AdapterProperties\n'
                  b'      ConnectionState: STATE_DISCONNECTED\n'
                  b'      State: ON\n'
                  b'    Profile: HeadsetService\n'
                  b'      State: OFF\n')

    def device(self, outputs):
        android = object.__new__(r.Android)
        android.p = plan()
        android.calls = []
        android.record = lambda *args, **kwargs: None
        def cmd(args, seconds=15):
            android.calls.append((args, seconds))
            value = outputs.pop(0)
            if isinstance(value, BaseException):
                raise value
            return value
        android.cmd = cmd
        return android

    def test_empty_manager_uses_scoped_adapter_state(self):
        android = self.device([b'', self.ADAPTER_ON])
        self.assertIs(android.radio_state(), True)
        self.assertEqual([args for args, _ in android.calls], [
            ['shell', 'dumpsys', 'bluetooth_manager'],
            ['shell', 'dumpsys', 'activity', 'service',
             'com.android.bluetooth/.btservice.AdapterService', '--print']])

    def test_exact_service_envelope_is_unknown_not_off_or_a_format_failure(self):
        path = r.ROOT / '.cache/p35-native-log-20261101/pipeline4-01/device/usb/adb-00198.stdout'
        raw = path.read_bytes() if path.exists() else self.ENVELOPE
        self.assertEqual(raw, self.ENVELOPE)
        self.assertIsNone(r.parse_radio_state(raw, 'adapter'))
        for bad in (raw + b'  State: OFF\n', raw.replace(b'AdapterService', b'OtherService'),
                    raw.replace(b'pid=22045', b'pid=unknown')):
            with self.subTest(raw=bad), self.assertRaises(r.Stop):
                r.parse_radio_state(bad, 'adapter')

    def test_selected_reader_is_reused_without_manager_reprobe(self):
        android = self.device([b'', self.ADAPTER_ON, self.ADAPTER_ON.replace(b'State: ON', b'State: OFF')])
        self.assertIs(android.radio_state(), True)
        self.assertIs(android.radio_state(), False)
        self.assertEqual([args for args, _ in android.calls],
                         [list(r.RADIO_MANAGER), list(r.RADIO_ADAPTER), list(r.RADIO_ADAPTER)])

    def test_supported_manager_formats_and_scoped_profiles(self):
        for value, expected in [('ON', True), ('OFF', False)]:
            for raw in [('state: ' + value + '\n').encode(),
                        ('Bluetooth Status\n  enabled: true\n  state: ' + value +
                         '\nProfile\n  state: ON\n').encode()]:
                with self.subTest(raw=raw):
                    android = self.device([raw, raw])
                    self.assertIs(android.radio_state(), expected)
                    self.assertIs(android.radio_state(), expected)
                    self.assertEqual([args for args, _ in android.calls], [list(r.RADIO_MANAGER)] * 2)
        android = self.device([b'', self.ADAPTER_ON + b'Unrelated profile log\n\tstate: OFF\n'])
        self.assertIs(android.radio_state(), True)

    def test_turning_and_ble_only_states_never_confirm_on_or_off(self):
        for value in ['TURNING_ON', 'TURNING_OFF', 'BLE_ON', 'BLE_TURNING_ON', 'BLE_TURNING_OFF']:
            with self.subTest(value=value):
                manager = self.device([('state: ' + value).encode()])
                self.assertIsNone(manager.radio_state())
                self.assertEqual(len(manager.calls), 1)
                adapter = self.device([b'', self.ADAPTER_ON.replace(b'State: ON', ('State: ' + value).encode())])
                self.assertIsNone(adapter.radio_state())

    def test_malformed_ambiguous_absent_and_profile_states_fail_closed(self):
        bad = [b'', b'bluetooth_on=0', b"Can't find service: com.android.bluetooth/.btservice.AdapterService",
               b'Profile\n  State: OFF\n', b'    AdapterProperties\n      mState: OFF\n',
               b'    AdapterProperties\n      Profile\n        State: OFF\n',
               self.ADAPTER_ON.replace(b'State: ON', b'state: ON'),
               self.ADAPTER_ON.replace(b'State: ON', b'State: ON\n      State: OFF'),
               self.ADAPTER_ON + b'    AdapterProperties\n      State: OFF\n',
               self.ADAPTER_ON.replace(b'State: ON', b'State: ON trailing'),
               self.ADAPTER_ON.replace(b'State: ON', b'State: 10'), b'\xff', b'\x00',
               self.ADAPTER_ON.replace(b'      State:', b'\tState:'), b'x' * (1024 * 1024 + 1)]
        for raw in bad:
            with self.subTest(sample=raw[:100]):
                android = self.device([b'', raw])
                with self.assertRaises(r.Stop) as error:
                    android.radio_state()
                self.assertEqual(error.exception.code, 'CAPABILITY_MISSING')
                self.assertEqual(len(android.calls), 2)

    def test_nonempty_invalid_manager_never_hides_failure_with_fallback(self):
        for raw in [b'bluetooth_on=1', b'Profile\n  state: ON\n', b'state: ON\nstate: OFF\n',
                    b'Bluetooth Status\n  enabled: true\n', b'state: NOT_ON', b'\xff']:
            android = self.device([raw])
            with self.assertRaises(r.Stop):
                android.radio_state()
            self.assertEqual(len(android.calls), 1)

    def test_nonzero_command_and_timeout_errors_propagate_without_retry(self):
        for prefix in [[], [b'']]:
            for error in [RuntimeError('standard tool nonzero exit'), TimeoutError('read timed out')]:
                android = self.device(prefix + [error])
                with self.assertRaises(type(error)) as caught:
                    android.radio_state()
                self.assertIs(caught.exception, error)
                self.assertEqual(len(android.calls), len(prefix) + 1)

    def test_fallback_shares_the_initial_read_deadline(self):
        from unittest.mock import patch
        for elapsed, expected_calls in [(2, 2), (6, 1)]:
            now = [0.0]
            android = self.device([b'', self.ADAPTER_ON])
            cmd = android.cmd
            def read(args, seconds=15):
                value = cmd(args, seconds)
                if args == list(r.RADIO_MANAGER):
                    now[0] += elapsed
                return value
            android.cmd = read
            with patch.object(r.time, 'monotonic', lambda: now[0]):
                if elapsed == 2:
                    self.assertIs(android.radio_state(), True)
                    self.assertEqual([seconds for _, seconds in android.calls], [5, 3])
                else:
                    with self.assertRaisesRegex(r.Stop, 'state-read deadline'):
                        android.radio_state()
            self.assertEqual(len(android.calls), expected_calls)
        android = self.device([b'state: ON'])
        now = [0.0]
        cmd = android.cmd
        def late_on(args, seconds=15):
            value = cmd(args, seconds)
            now[0] += 6
            return value
        android.cmd = late_on
        with patch.object(r.time, 'monotonic', lambda: now[0]):
            with self.assertRaisesRegex(r.Stop, 'state-read deadline'):
                android.radio_state()
        self.assertEqual(len(android.calls), 1)

    def test_invalid_read_allowance_starts_no_command(self):
        for seconds in [0, -1, 6, float('inf'), float('nan'), True]:
            android = self.device([])
            with self.assertRaises(r.Stop):
                android.radio_state(seconds=seconds)
            self.assertEqual(android.calls, [])

    def radio_device(self, outputs):
        android = self.device(outputs)
        android.p = plan()
        android.p['limits']['disconnect_seconds'] = .15
        android.radio_state_source = 'adapter'
        android.radio_touched = True
        android.restore_attempted = False
        android.record = lambda *args, **kwargs: None
        read = android.cmd
        def cmd(args, seconds=15):
            if args[:3] == ['shell', 'cmd', 'bluetooth_manager']:
                android.calls.append((args, seconds))
                return b''
            return read(args, seconds)
        android.cmd = cmd
        return android

    def test_restoration_waits_for_explicit_on_with_bounded_reads(self):
        from unittest.mock import patch
        now = [0.0]
        android = self.radio_device([self.ADAPTER_ON.replace(b'State: ON', b'State: TURNING_ON'),
                                     self.ADAPTER_ON])
        with patch.object(r.time, 'monotonic', lambda: now[0]), \
             patch.object(r.time, 'sleep', lambda seconds: now.__setitem__(0, now[0] + seconds)):
            android.radio(True)
        self.assertFalse(android.radio_touched)
        self.assertTrue(android.restore_attempted)
        self.assertAlmostEqual(android.calls[-1][1], .1)
        self.assertEqual(sum(args[-1] == 'enable' for args, _ in android.calls), 1)

    def test_permanent_transition_times_out_without_second_restore(self):
        from unittest.mock import patch
        now = [0.0]
        android = self.radio_device([self.ADAPTER_ON.replace(b'State: ON', b'State: TURNING_ON')] * 10)
        with patch.object(r.time, 'monotonic', lambda: now[0]), \
             patch.object(r.time, 'sleep', lambda seconds: now.__setitem__(0, now[0] + seconds)):
            with self.assertRaisesRegex(r.Stop, 'did not reach requested state'):
                android.radio(True)
            count = len(android.calls)
            with self.assertRaisesRegex(r.Stop, 'already attempted'):
                android.radio(True)
        self.assertEqual(len(android.calls), count)
        self.assertTrue(android.radio_touched)
        self.assertAlmostEqual(now[0], .15)
        self.assertEqual(sum(args[-1] == 'enable' for args, _ in android.calls), 1)

    def test_disable_waits_for_explicit_synthetic_off(self):
        from unittest.mock import patch
        now = [0.0]
        android = self.radio_device([self.ADAPTER_ON.replace(b'State: ON', b'State: TURNING_OFF'),
                                     self.ENVELOPE,
                                     self.ADAPTER_ON.replace(b'State: ON', b'State: OFF')])
        android.pump = lambda: None
        android.decoder = r.Decoder()
        android.decoder.previous = state(phase='transferring', durable=0)
        android.last_state_at = 0
        with patch.object(r.time, 'monotonic', lambda: now[0]), \
             patch.object(r.time, 'sleep', lambda seconds: now.__setitem__(0, now[0] + seconds)):
            android.radio(False, case=android.p['cases'][0])
        self.assertTrue(android.radio_touched)
        self.assertFalse(android.restore_attempted)
        self.assertAlmostEqual(now[0], .1)
        self.assertEqual(sum(args[-1] == 'disable' for args, _ in android.calls), 1)

    def test_absent_adapter_after_restore_is_not_off_or_success(self):
        from unittest.mock import patch
        now = [0.0]
        android = self.radio_device([b'No services match'])
        with patch.object(r.time, 'monotonic', lambda: now[0]):
            with self.assertRaises(r.Stop):
                android.radio(True)
        self.assertTrue(android.radio_touched)
        self.assertTrue(android.restore_attempted)
        self.assertEqual(sum(args[-1] == 'enable' for args, _ in android.calls), 1)


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


class ResultTests(unittest.TestCase):
    def test_cli_preserves_ten_statuses_on_failure_and_redacts_archive(self):
        import contextlib
        import io
        from types import SimpleNamespace
        from unittest.mock import patch
        for mode in ('success', 'case-failure', 'cleanup-failure'):
            with self.subTest(mode=mode):
                rows = trace()
                if mode == 'case-failure':
                    next(s for s in rows if s['event'] == 'data' and s['durable'] == 4096)['sendOffset'] = 999
                device = Fake(rows)
                campaign = r.Campaign(plan(), device, device.clock)
                saved = {}
                def close():
                    if mode == 'cleanup-failure':
                        raise r.Stop('CLEANUP_FAILED', 'owned process not closed')
                driver = SimpleNamespace(campaign=campaign, startup=lambda **_: None, close=close)
                helper = SimpleNamespace(checked=lambda path: Path(str(path) + '.synthetic-absent')
                    if Path(path).name in {'p34-live-device.lock', 'p35-reconcile-device.lock'} else Path(path), pinned=lambda pin: Path('fixture'),
                    save=lambda path, value: saved.update({Path(path).name: value}),
                    raw=lambda path, value: saved.update({Path(path).name: value}),
                    record=lambda path: {}, device_owner=lambda *args, **kwargs: contextlib.nullcontext(),
                    __file__=__file__)
                def execute(*args):
                    result = campaign.run()
                    result['archive'] = {'privateDeviceIdentity': 'MUST_NOT_APPEAR_IN_CONSOLE'}
                    return result
                console = io.StringIO()
                out = r.ROOT / '.cache/p35-ten-prepare-20261030/never-created-cli-unit'
                self.assertFalse(out.exists())
                with patch.object(r, 'strict_json', lambda raw: plan()), patch.object(r, 'load_host', lambda: helper), \
                     patch.object(r, 'Android', lambda *args: driver), patch.object(r, 'execute_ui', execute), \
                     contextlib.redirect_stdout(console):
                    code = r.main(['run', '--plan', __file__, '--out', str(out), '--execute'])
                result = saved['result.json']
                self.assertEqual(len(result['caseResults']), 10)
                self.assertNotIn('MUST_NOT_APPEAR_IN_CONSOLE', console.getvalue())
                self.assertFalse(out.exists())
                if mode == 'case-failure':
                    self.assertEqual(code, 2)
                    self.assertEqual(len(result['cases']), 1)
                    self.assertEqual([x['outcome'] for x in result['caseResults']],
                        ['RECOVERY_OBSERVED', 'FAIL'] + ['NOT_RUN'] * 8)
                else:
                    self.assertEqual(code, 0 if mode == 'success' else 2)
                    self.assertEqual([x['outcome'] for x in result['caseResults']],
                        ['PASS' if mode == 'success' else 'RECOVERY_OBSERVED'] * 10)


if __name__ == '__main__':
    unittest.main()
