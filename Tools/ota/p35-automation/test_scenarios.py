"""Synthetic coverage only; no phone, CI or network operations."""
from collections import deque
import copy
import hashlib
import json
from pathlib import Path
import sys
from types import SimpleNamespace
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parent))
import runner as r
import scenarios as s
import pipeline
import test_runner as u
import test_pipeline as pu


def plan(profile='background-lock'):
    p = u.plan()
    p.update(test_profile=profile, cases=[], allow_bluetooth_toggle=profile == 'resume-once',
             allow_display_control=profile == 'background-lock')
    p['app']['id'] = 'com.example.p35acceptance'
    p['ui']['arm'] = {'resource-id': 'p35-arm-stream'}
    p['preparation'] = dict(live_stream_port=5193, log_buffer='events')
    if profile == 'resume-once':
        p['cases'] = [dict(id='R01', durable_min=4096, durable_max=65535, bitmap='any')]
    return p


def state(**changes):
    row = u.state(schema=2, phase='transferring', runtime=dict(backgrounded=False, acquired=True,
        reason=None, active=True, paused=False, ownerEpoch=3, revision=1, task=dict(taskId='task_3', generation=3,
        deviceToken=hashlib.sha256(b'AA:BB').hexdigest(), packageSha256='a'*64)))
    row.update(changes)
    return row


def power(awake=True):
    return ('  mWakefulness=' + ('Awake' if awake else 'Asleep') + '\n  mHalInteractiveModeEnabled=' +
            ('true' if awake else 'false') + '\n').encode()


def policy(locked=False):
    return ('    KeyguardServiceDelegate\n      showing=' + ('true' if locked else 'false') +
            '\n      secure=true\n      deviceHasKeyguard=true\n      KeyguardStateMonitor\n').encode()


class DisplayTests(unittest.TestCase):
    def test_scoped_strict_states(self):
        self.assertFalse(s.display(power(), policy())['showing'])
        self.assertTrue(s.display(power(False), policy(True))['showing'])
        for p, k in [(b'', policy()), (power()*2, policy()), (power(), policy()*2),
                     (power().replace(b'Awake', b'UNKNOWN'), policy()),
                     (power(), policy().replace(b'      showing=false', b'  showing=false')),
                     (power(), policy().replace(b'false', b'unknown')), (b'\xff', policy())]:
            with self.subTest(p=p, k=k), self.assertRaises(r.Stop):
                s.display(p, k)

    def test_current_phone_originals(self):
        area = r.ROOT / '.cache/p35-scenarios-20261101/display-preflight-01'
        if not area.exists():
            self.skipTest('local phone originals not a portable fixture')
        actual = s.display((area/'power.raw').read_bytes(), (area/'policy.raw').read_bytes())
        self.assertTrue(actual['awake'] and actual['secure'] and not actual['showing'])


class ContractTests(unittest.TestCase):
    def test_schema_two_strict_and_no_mixed_capture(self):
        row = state()
        self.assertEqual(r.validate_state(row), row)
        for change in ({'schema': True}, {'schema': 1}, {'runtime': None}, {'schema': 3}):
            with self.subTest(change=change), self.assertRaises(r.Stop):
                r.validate_state(dict(row, **change))
        for change in ({'active': 1}, {'task': None}, {'ownerEpoch': 4}, {'revision': -1}, {'extra': False}):
            bad = copy.deepcopy(row)
            bad['runtime'].update(change)
            with self.subTest(change=change), self.assertRaises(r.Stop):
                r.validate_state(bad)
        with self.assertRaises(r.Stop):
            r.Decoder().feed(u.line(u.state()) + u.line(state(seq=2, monoUs=2000)))

    def test_profiles_are_explicit_not_formal_or_single(self):
        for kind in ('resume-once', 'background-lock'):
            p = plan(kind)
            self.assertEqual(r.validate_plan(p, scenarios=True), p)
            for flags in ({}, {'single': True}, {'single': True, 'scenarios': True}):
                with self.assertRaises(r.Stop): r.validate_plan(p, **flags)
            bad = copy.deepcopy(p)
            bad['allow_bluetooth_toggle'] = not bad['allow_bluetooth_toggle']
            with self.assertRaises(r.Stop): r.validate_plan(bad, scenarios=True)
        for cases in ([], u.plan()['cases'], [dict(id='R01', durable_min=0, durable_max=65535, bitmap='any')]):
            bad = plan('resume-once'); bad['cases'] = cases
            with self.assertRaises(r.Stop): r.validate_plan(bad, scenarios=True)

    def test_resume_reuses_durable_oracle_and_one_cut(self):
        p = plan('resume-once')
        for fault in (None, 'offset', 'hash', 'prefix'):
            rows = u.trace(p)
            if fault == 'offset': rows[9]['sendOffset'] = 0
            if fault == 'hash': rows[-1]['currentImageSha256'] = 'f'*64
            if fault == 'prefix': rows[8]['durable'] = 0
            io = u.Fake(rows)
            campaign = r.Campaign(p, io, io.clock, scenarios=True)
            if fault:
                with self.subTest(fault=fault), self.assertRaises(r.Stop): campaign.run()
            else:
                self.assertEqual(campaign.run()['recovered'], 1)
                self.assertEqual([a for a in io.actions if a[0]=='radio'], [('radio', False), ('radio', True)])

    def test_pipeline_derives_only_requested_windows(self):
        c, _, target, _ = pu.fixture()
        for kind in ('resume-once', 'background-lock'):
            c['test_profile'] = kind
            p = plan(kind); p['firmware']['protocol'] = 2
            self.assertEqual(pipeline.validate(c), 30295)
            actual = pipeline.make_plan(p, c, target)
            self.assertEqual(len(actual['cases']), int(kind=='resume-once'))
            self.assertEqual(actual['test_profile'], kind)
            if actual['cases']:
                self.assertEqual(actual['cases'][0]['durable_min'], 4096)


class BackgroundIO:
    def __init__(self, fault=None):
        self.p, self.fault = plan(), fault
        self.now, self.seq, self.durable = 0., 1, 0
        self.bg, self.awake, self.locked, self.woken = False, True, False, False
        self.state_sink, self.queue = None, deque()
        self.preparation = SimpleNamespace(phone=SimpleNamespace(read_ready=None))
        self.calls, self.records = [], []
        self.pid = '123'
        self.scenario_component = self.p['app']['id'] + '/MainActivity'
    def clock(self): return self.now
    def sleep(self, seconds): self.now += seconds
    def enter_stage(self, *args): pass
    def record(self, event, **fields): self.records.append((event, fields))
    def pump(self):
        self.now += .02
        self.seq += 1
        if self.fault != 'stalled': self.durable = min(self.durable + 4096, 1044480)
        row = state(seq=self.seq, monoUs=int(self.now*1e6), durable=self.durable)
        row['runtime']['backgrounded'] = self.bg
        if self.fault == 'owner' and self.bg: row['runtime']['task']['taskId'] = 'foreign'
        if self.fault == 'begin' and self.bg: row['event'] = 'beginAck'
        if self.fault == 'paused' and self.bg: row['runtime']['paused'] = True
        if self.fault == 'no-runtime': row.pop('runtime'); row['schema'] = 1
        if self.woken and self.fault != 'transfer-on-return':
            row.update(phase='completed', event='identity', currentVersionCode=30294,
                       currentImageSha256='d'*64, durable=1048576)
            if self.fault == 'final-hash': row['currentImageSha256'] = 'f'*64
            row['runtime'].update(active=False, acquired=False, task=None)
        if self.state_sink: self.state_sink(row)
    def cmd(self, args, **kwargs):
        self.calls.append(args)
        self.pump()
        if args[-1] == 'KEYCODE_HOME': self.bg = True
        if args[-1] == 'KEYCODE_SLEEP': self.awake, self.locked = False, True
        if args[-1] == 'KEYCODE_WAKEUP':
            self.awake, self.woken = True, True
            if self.fault != 'unlock': self.locked = False
        if args[:3] == ['shell', 'am', 'start']:
            if self.fault == 'restore': raise r.Stop('UNRESOLVED_STATE', 'synthetic return failed')
            self.bg = False
        if args == ['shell', 'dumpsys', 'power']: return power(self.awake)
        if args == ['shell', 'dumpsys', 'window', 'policy']: return policy(self.locked)
        if args == ['shell', 'dumpsys', 'window']:
            return u.window_dump(('mCurrentFocus=Window{abc u0 '+self.p['app']['id']+'/MainActivity}\n').encode())
        if args[:2] == ['shell', 'pidof']: return self.pid.encode()
        return b''


class BackgroundTests(unittest.TestCase):
    def run_case(self, fault=None):
        io = BackgroundIO(fault)
        c = r.Campaign(io.p, io, io.clock, scenarios=True)
        c.state = state(event='beginAck')
        return io, s.Background(c)

    def test_home_lock_return_and_terminal_retained_during_unlock(self):
        io, bg = self.run_case()
        with patch.object(s.time, 'sleep', io.sleep): result = bg.run()
        self.assertEqual(result['outcome'], 'PASS')
        self.assertEqual(bg.final['currentVersionCode'], 30294)
        self.assertGreater(result['home']['end']['durable'], result['home']['start']['durable'])
        self.assertGreater(result['locked']['end']['durable'], result['locked']['start']['durable'])
        self.assertFalse(bg.home_touched or bg.sleep_touched)
        self.assertIsNone(io.state_sink)
        self.assertIsNone(io.preparation.phone.read_ready)
        bg.restore()
        self.assertEqual(sum(a[-1]=='KEYCODE_WAKEUP' for a in io.calls), 1)

    def test_failed_oracles_cannot_pass_and_restore_is_not_replayed(self):
        for fault in ('owner', 'begin', 'paused', 'stalled', 'no-runtime', 'final-hash', 'unlock', 'restore'):
            io, bg = self.run_case(fault)
            with self.subTest(fault=fault), patch.object(s.time, 'sleep', io.sleep):
                with self.assertRaises(r.Stop): bg.run()
                if bg.home_touched or bg.sleep_touched:
                    try: bg.restore()
                    except r.Stop: pass
                if bg.home_touched or bg.sleep_touched:
                    before = list(io.calls)
                    with self.assertRaises(r.Stop): bg.restore()
                    self.assertEqual(io.calls, before)
                self.assertLessEqual(sum(a[-1]=='KEYCODE_WAKEUP' for a in io.calls), 1)

    def test_return_before_completion_keeps_later_begin_guard(self):
        io, bg = self.run_case('transfer-on-return')
        io.scenario = bg
        with patch.object(s.time, 'sleep', io.sleep):
            self.assertEqual(bg.run()['outcome'], 'PASS')
        self.assertIsNone(bg.final)
        row = state(seq=io.seq+1, event='beginAck', durable=io.durable)
        io.next_state = lambda seconds: row
        with self.assertRaisesRegex(r.Stop, 'duplicate BEGIN'):
            bg.c.wait(lambda value: True, 'post-return')

    def test_post_verified_query_may_clear_asset_but_not_change_identity(self):
        io,bg=self.run_case()
        final=state(seq=2,phase='completed',event='identity',currentVersionCode=30294,
                    currentImageSha256='d'*64,durable=1048576)
        bg.observe(final)
        self.assertIsNone(bg.error)
        cleared=dict(final,seq=3,targetVersionCode=0,targetImageSha256=None,packageSha256=None,
                     packageBytes=0,durable=0,packageVerified=False,releaseId=None,protocol=None,bitmap=None)
        bg.observe(cleared)
        self.assertIsNone(bg.error)
        self.assertEqual(bg.final,final)
        bg.observe(dict(cleared,seq=4,currentImageSha256='f'*64))
        self.assertEqual(bg.error.code,'IDENTITY_MISMATCH')
        other_io,other=self.run_case()
        other.observe(cleared)
        self.assertIsNotNone(other.error)
        self.assertIsNone(other.final)


if __name__ == '__main__': unittest.main()
