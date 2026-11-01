"""Bounded development background/lock observations, not ten-window acceptance."""
import hashlib
import re
import time

import runner as r

HOLD_SECONDS = 2
UNLOCK_SECONDS = 120


def display(power, policy):
    try:
        power, policy = power.decode('utf-8'), policy.decode('utf-8')
    except UnicodeError as error:
        raise r.Stop('CAPABILITY_MISSING', 'invalid display observation') from error
    wake = re.findall(r'^  mWakefulness=(\w+)\s*$', power, re.M)
    interactive = re.findall(r'^  mHalInteractiveModeEnabled=(true|false)\s*$', power, re.M)
    sections = re.findall(r'^    KeyguardServiceDelegate\s*\n((?:^      .*\n)+)', policy, re.M)
    r.require(len(wake) == len(interactive) == len(sections) == 1 and
              wake[0] in {'Awake', 'Asleep', 'Dozing', 'Dreaming'}, 'ambiguous display state', 'CAPABILITY_MISSING')
    values = {}
    for key in ('showing', 'secure', 'deviceHasKeyguard'):
        found = re.findall(r'^      ' + key + r'=(true|false)\s*$', sections[0], re.M)
        r.require(len(found) == 1, 'missing/ambiguous keyguard ' + key, 'CAPABILITY_MISSING')
        values[key] = found[0] == 'true'
    values.update(awake=wake[0] == 'Awake', interactive=interactive[0] == 'true', wakefulness=wake[0])
    return values


def read_display(io):
    return display(io.cmd(['shell', 'dumpsys', 'power'], seconds=5),
                   io.cmd(['shell', 'dumpsys', 'window', 'policy'], seconds=5))


def preflight(io):
    state = read_display(io)
    r.require(state['awake'] and state['interactive'] and not state['showing'] and state['deviceHasKeyguard'],
              'background-lock must start awake and unlocked with a real keyguard', 'UI_UNAVAILABLE')
    io.record('display-preflight', state=state, unlock='USER_REQUIRED' if state['secure'] else 'USER_IF_REQUIRED')
    component = io.cmd(['shell', 'cmd', 'package', 'resolve-activity', '--brief', io.p['app']['id']], seconds=5).decode().strip().splitlines()
    r.require(component and re.fullmatch(re.escape(io.p['app']['id']) + r'/[A-Za-z0-9_.$]+', component[-1]),
              'background return activity unresolved', 'UI_UNAVAILABLE')
    io.scenario_component = component[-1]


class Background:
    def __init__(self, campaign):
        self.c, self.io, self.p = campaign, campaign.io, campaign.p
        self.clock = campaign.clock
        self.last = self.final = self.task = self.session = None
        self.error = None
        self.home_touched = self.sleep_touched = self.restore_attempted = False
        self.receipts = {}
        self.bound_seq = campaign.state['seq']
        self.last_at = self.clock()
        self.last_durable = campaign.state['durable']
        self.progress_at = self.clock()
        self.expect_background = False
        self.revision = None

    def observe(self, state):
        # Keep draining even after a failed oracle so the sealed original and any
        # real post-reboot identity are not lost while waiting for user unlock.
        self.last, self.last_at = state, self.clock()
        self.c.state = state
        try:
            r.validate_state(state)
            r.require(state['schema'] == 2, 'runtime telemetry missing', 'CAPABILITY_MISSING')
            r.require(state['deviceAddress'] == self.p['firmware']['device_address'], 'scenario device changed', 'IDENTITY_MISMATCH')
            r.require(state['event'] != 'beginAck' or state['seq'] <= self.bound_seq,
                      'duplicate BEGIN during background/return', 'PRODUCT_OR_ENV_FAILURE')
            r.require(state['phase'] not in {'failed', 'cancelled'}, 'App terminal during background scenario', 'PRODUCT_OR_ENV_FAILURE')
            runtime = state['runtime']
            r.require(self.revision is None or runtime['revision'] >= self.revision, 'runtime revision regressed', 'EVIDENCE_GAP')
            self.revision = runtime['revision']
            if state['phase'] == 'completed' and state['event'] == 'identity':
                # Keep the first strict upgrade proof. A later NO_UPDATE query
                # legitimately clears its asset; it must still identify the same
                # target image, but is not a second completion of that transfer.
                r.bound(state, self.p, package=self.final is None, final=True)
                r.require(state['freshConnection'] and state['linkConnected'], 'unverified terminal identity', 'EVIDENCE_GAP')
                if self.final is None:
                    r.require(state['durable'] == self.p['firmware']['package']['bytes'], 'incomplete terminal durable', 'EVIDENCE_GAP')
                    self.final = state
                    self.io.final_verified = True
            if state['phase'] == 'transferring':
                r.bound(state, self.p, package=True)
                r.require(not self.expect_background or runtime['backgrounded'], 'unexpected foreground return', 'EVIDENCE_GAP')
                if self.task is not None:
                    r.require(runtime['task'] == self.task and runtime['ownerEpoch'] == self.task['generation'] and
                              runtime['acquired'] and runtime['active'] and not runtime['paused'] and
                              state['session'] == self.session and state['linkConnected'],
                              'background execution owner/session lost', 'PRODUCT_OR_ENV_FAILURE')
                r.require(state['durable'] >= self.last_durable, 'durable regressed', 'EVIDENCE_GAP')
                if state['durable'] > self.last_durable:
                    self.last_durable, self.progress_at = state['durable'], self.clock()
                r.require(self.clock() - self.progress_at < 30, 'background durable stalled', 'NO_DURABLE_PROGRESS')
        except r.Stop as error:
            self.error = self.error or error

    def pump(self):
        self.io.pump()
        return False  # This is not cancellation/replay of the current ADB command.

    def healthy(self):
        if self.error:
            raise self.error
        r.require(self.clock() < self.c.deadline and self.clock() - self.last_at < self.p['limits']['event_seconds'],
                  'background live event deadline', 'EVIDENCE_GAP')

    def wait(self, predicate, stage, seconds=10):
        self.c.stage = stage
        self.io.enter_stage(stage, seconds + 10)
        deadline = min(self.c.deadline, self.clock() + seconds)
        while self.clock() < deadline:
            self.pump()
            self.healthy()
            if self.last is not None and predicate(self.last):
                self.io.record('scenario-observed', stage=stage, state=self.last)
                return self.last
            time.sleep(.02)
        raise r.Stop('EVIDENCE_GAP', 'scenario deadline: ' + stage)

    def hold(self, stage):
        start = self.wait(lambda s: s['phase'] == 'transferring' and s['runtime']['backgrounded'], stage + '-start')
        self.expect_background = True
        stamp = self.clock()
        end = self.wait(lambda s: s['phase'] == 'transferring' and s['runtime']['backgrounded'] and
                        self.clock() - stamp >= HOLD_SECONDS and s['durable'] > start['durable'], stage + '-progress')
        self.receipts[stage] = dict(start=start, end=end, seconds=self.clock() - stamp)

    def run(self):
        phone = self.io.preparation.phone
        r.require(phone.read_ready is None and self.io.state_sink is None, 'existing stream consumer', 'ENV_BLOCKED')
        self.io.state_sink, phone.read_ready = self.observe, self.pump
        while self.io.queue:
            self.observe(self.io.queue.popleft())
        try:
            owned = self.wait(lambda s: s['phase'] == 'transferring' and s['runtime']['acquired'] and
                              s['runtime']['active'] and not s['runtime']['paused'], 'background-owner')
            self.task, self.session = owned['runtime']['task'], owned['session']
            r.require(self.task is not None and self.task['packageSha256'] == self.p['firmware']['package']['sha256'] and
                      self.task['deviceToken'] == hashlib.sha256(self.p['firmware']['device_address'].encode()).hexdigest(),
                      'background task asset/device mismatch', 'IDENTITY_MISMATCH')
            self.io.record('background-home-intent', state=owned)
            self.home_touched = True
            self.io.cmd(['shell', 'input', 'keyevent', 'KEYCODE_HOME'], seconds=5)
            self.hold('home')
            self.io.record('screen-sleep-intent', state=self.last)
            self.sleep_touched = True
            self.io.cmd(['shell', 'input', 'keyevent', 'KEYCODE_SLEEP'], seconds=5)
            deadline = min(self.c.deadline, self.clock() + 5)
            while self.clock() < deadline:
                screen = read_display(self.io)
                self.healthy()
                if not screen['awake'] and not screen['interactive'] and screen['showing']:
                    break
                time.sleep(.1)
            r.require(not screen['awake'] and not screen['interactive'] and screen['showing'],
                      'real screen lock not confirmed', 'CAPABILITY_MISSING')
            self.io.record('screen-locked', state=screen)
            self.hold('locked')
            self.restore()
            self.healthy()
            self.receipts['return'] = dict(state=self.last, duplicateBegin=False, task=self.task, session=self.session)
            return dict(outcome='PASS', home=self.receipts['home'], locked=self.receipts['locked'],
                        foregroundReturn=self.receipts['return'], formalAcceptance='NOT_ADJUDICATED')
        finally:
            # On failure keep the consumer active through the one restoration
            # attempt; close() calls restore before disposing the phone owner.
            if not self.home_touched and not self.sleep_touched:
                self.io.state_sink, phone.read_ready = None, None

    def restore(self):
        if not self.home_touched and not self.sleep_touched:
            self.io.state_sink = None
            self.io.preparation.phone.read_ready = None
            return
        r.require(not self.restore_attempted, 'display restoration unresolved; do not replay', 'UNRESOLVED_STATE')
        self.restore_attempted = True
        self.io.enter_stage('display-restore', UNLOCK_SECONDS + 30)
        if self.sleep_touched:
            self.io.record('screen-wake-intent')
            self.io.cmd(['shell', 'input', 'keyevent', 'KEYCODE_WAKEUP'], seconds=5)
            print('P35_USER_ACTION: Unlock the test phone now; do not stop the App or BLE. Capture continues.', flush=True)
            self.io.record('user-unlock-needed', seconds=UNLOCK_SECONDS, credentialBypass=False)
        deadline = min(self.c.deadline, self.clock() + UNLOCK_SECONDS)
        while self.clock() < deadline:
            self.pump()
            screen = read_display(self.io)
            if screen['awake'] and screen['interactive'] and not screen['showing']:
                self.sleep_touched = False
                break
            time.sleep(.3)
        r.require(not self.sleep_touched and screen['awake'] and screen['interactive'] and not screen['showing'],
                  'user unlock not observed', 'UNRESOLVED_STATE')
        # Bring the existing singleTask activity back; no new sender or connection.
        self.io.record('foreground-restore-intent')
        self.expect_background = False
        self.io.cmd(['shell', 'am', 'start', '-W', '-n', self.io.scenario_component], seconds=10)
        focus = self.io.cmd(['shell', 'dumpsys', 'window'], seconds=5)
        r.require(r.foreground_ok(focus, self.p['app']['id']), 'foreground restoration not confirmed', 'UI_UNAVAILABLE')
        deadline = min(self.c.deadline, self.clock() + 10)
        while self.clock() < deadline:
            self.pump()
            if self.last is not None and not self.last['runtime']['backgrounded']:
                break
            time.sleep(.02)
        r.require(self.last is not None and not self.last['runtime']['backgrounded'], 'foreground lifecycle missing', 'EVIDENCE_GAP')
        r.require(self.io.cmd(['shell', 'pidof', self.p['app']['id']], seconds=5).decode().strip() == self.io.pid,
                  'App process changed during background test', 'EVIDENCE_GAP')
        self.home_touched = False
        self.io.record('display-restored', state=screen, lifecycle=self.last, samePid=self.io.pid)
        self.io.state_sink = None
        self.io.preparation.phone.read_ready = None
