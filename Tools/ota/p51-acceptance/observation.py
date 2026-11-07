"""Manual P5 recording, reusing the installed recorder and acknowledged receiver."""
import os
import re
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'p35-automation'))
import smoke as s
import runner as r
import state_chain
h = state_chain.h


def start_notice(out, label, message, cli):
    path = h.checked(out / 'notifications' / label)
    h.require(re.fullmatch(r'[a-z0-9-]+', label), 'unsafe notice label')
    h.fresh(path)
    env = h.environment(path)
    session = env.get('CC_SESSION_KEY', '')
    h.require(re.fullmatch(r'feishu:[^:]+:ou_[a-zA-Z0-9]+', session) and env.get('CC_PROJECT'),
              'current-session notification route unavailable')
    body = '<at user_id="' + session.rsplit(':', 1)[1] + '">requester</at>\n' + message
    process = h.Process(path, 'send', [h.pinned(cli), 'send', '--project', env['CC_PROJECT'],
        '--session', session, '--stdin'], env, stdin=body.encode('utf8'))
    return path, process


def finish_notice(notice):
    path, process = notice
    raw = process.wait(max(.01, 30 - (time.monotonic_ns()-process.started)/1e9))
    h.require(raw.strip() == b'Message sent successfully.', 'user action notification not acknowledged')
    h.save(path / 'result.json', dict(delivered=True, currentSession=True, chatReplyRequested=False))
    print('USER_ACTION_DELIVERED ' + path.name, flush=True)


def notify(out, label, message, cli):
    notice = start_notice(out, label, message, cli)
    try:
        finish_notice(notice)
    finally:
        notice[1].close('notification-ended')


def identity(states, version, digest, address, after=0):
    found = s.latest_identity(states, after)
    if found is None:
        return None
    h.require(found['deviceAddress'].lower() == address and found['linkConnected'] and found['freshConnection'],
              'identity is not from the live selected device')
    if found['currentVersionCode'] != version or found['currentImageSha256'] != digest:
        return None
    return found


class Observer(s.Smoke):
    """Only reuse Smoke's USB, launch, archive and closed-recorder primitives.

    Its no-OTA scenario runner/validator and automatic UI methods are not used.
    P5 admission and changing firmware identities belong to run.py instead.
    """
    def __init__(self, p, out, cli):
        super().__init__(p, out, h)
        self.cli, self.env, self.preparation = cli, h.environment(out), self
        self.stream_port, self.stream_capture, self.stream_forwarded = 5193, None, False
        self.cursor = None
        self.notice_index = 0
        self.recording_deadline = None
        self.pending_notice = None
        self.stop_notice_sent = False

    def launch(self, **kwargs):
        try:
            super().launch(**kwargs)
        except r.Stop as error:
            if self.arm_attempted or not self.pid or error.code != 'UI_UNAVAILABLE' or str(error) not in (
                'test APP not foreground/unlocked; no hierarchy collected',
                'pre-ARM focus changed; sample discarded'):
                raise
            # The existing launcher already verified the returned PID. Navigation
            # owns the later foreground check, not a second launch or UI action.
            self.mutation_unknown = False
            self.owned_launch_confirmed = self.owned_app_pid == self.pid
            self.record('launch-ui-deferred', pid=self.pid)

    prepare_live_stream = r.Android.prepare_live_stream

    def start_live_stream(self):
        # Manual preparation can briefly pause the producer; phase and whole
        # recording deadlines still bound the owner, and EOF/footer checks stay strict.
        return r.Android.start_live_stream(self, idle_seconds=60)

    def tap(self, *args, **kwargs):
        raise RuntimeError('user owns UI; no automatic tap')

    def scroll(self, *args, **kwargs):
        raise RuntimeError('user owns UI; no automatic swipe')

    def phase(self, name, seconds):
        self.enter(name)
        self.stage_deadline = min(self.total, time.monotonic() + seconds)
        self.phone.operation_deadline = self.stage_deadline

    def ask(self, label, message, *, asynchronous=False):
        self.notice_index += 1
        label = '%03d-%s' % (self.notice_index, label)
        if asynchronous:
            h.require(self.pending_notice is None, 'notification already pending')
            self.pending_notice = start_notice(self.out, label, message, self.cli)
        else:
            notify(self.out, label, message, self.cli)

    def ui(self):
        package = self.p['app']['id']
        for attempt in range(3):
            h.require(self.cmd(['shell', 'pidof', package]).strip().decode() == self.pid, 'App PID changed')
            before = self.cmd(['shell', 'dumpsys', 'window'])
            if not r.foreground_ok(before, package):
                raise r.Stop('UI_UNAVAILABLE', 'test APP not foreground/unlocked; no hierarchy collected')
            raw = self.cmd(['exec-out', 'uiautomator', 'dump', '--compressed', '/dev/tty'])
            after = self.cmd(['shell', 'dumpsys', 'window'])
            h.require(self.cmd(['shell', 'pidof', package]).strip().decode() == self.pid, 'App PID changed')
            if not r.foreground_ok(after, package):
                raise r.Stop('UI_UNAVAILABLE', 'pre-ARM focus changed; sample discarded')
            if raw.strip() == b'ERROR: null root node returned by UiTestAutomationBridge.':
                self.record('native-ui-null-root', attempt=attempt+1)
                if attempt < 2:
                    continue  # cmd retains the same phase deadline and every original.
            s.nodes(raw, package)
            return raw

    def navigate(self):
        self.phase('manual-firmware-page', 300)
        requested = False
        def page():
            nonlocal requested
            try:
                raw = self.ui()
                if s.has_label(raw, self.p['app']['id'], s.FIRMWARE):
                    return raw
            except r.Stop as error:
                if error.code != 'UI_UNAVAILABLE' or str(error) not in (
                    'test APP not foreground/unlocked; no hierarchy collected',
                    'pre-ARM focus changed; sample discarded'):
                    raise
            if not requested:
                requested = True
                self.ask('firmware-page', '\u8bf7\u6253\u5f00\u6d4b\u8bd5 App\uff0c\u8fde\u63a5 E-Track \u5e76\u505c\u7559\u5728\u201c\u7801\u8868\u56fa\u4ef6\u201d\u9875\u3002\u5148\u4e0d\u5f00\u59cb\u5347\u7ea7\uff0c\u65e0\u9700\u56de\u590d\u804a\u5929\u3002')
            return None
        return self.wait(page)

    def start_recording(self):
        self.start_phone()
        self.phase('preserve-originals', 240)
        self.old_captures()
        self.phase('attach-test-app', 180)
        pid = self.cmd(['shell', 'pidof', self.p['app']['id']], success_codes=(0, 1)).strip().decode()
        if pid:
            h.require(pid.isdigit(), 'ambiguous App PID')
            self.pid = pid
        else:
            self.launch()
        self.navigate()
        self.prepare_recorder()
        self.phase('prepare-recording', 120)
        r.find_control(self.ui(), {'resource-id': 'p51-arm-timing'}, self.p['app']['id'])
        self.idle_services()
        self.prepare_live_stream()
        self.phase('manual-recording-arm', 300)
        self.ask('recording-arm', '\u70b9 App \u53f3\u4e0a\u89d2\u6298\u7ebf\u56fe\u6807\u5f00\u59cb\u8ba1\u65f6\u3002\u4fdd\u6301\u672c\u9875\uff0c\u7b49\u4e0b\u4e00\u6761\u63d0\u793a\uff0c\u4e0d\u7528\u56de\u804a\u5929\u3002', asynchronous=True)
        def armed():
            names = self.capture_names()
            old = set(self.previous_captures)
            h.require(old <= names and len(names-old) <= 1, 'capture store changed unexpectedly')
            if not names-old:
                return False
            self.capture_id, = names-old
            self.arm_attempted = True
            self.cursor = s.FileCursor(self.capture_id)
            if self.stream_capture is None:
                self.start_live_stream()
            self.recording_deadline = min(self.total-180, time.monotonic()+3000)
            return True
        self.wait(armed)
        if self.pending_notice is not None:
            finish_notice(self.pending_notice)
            self.pending_notice = None
        self.phase('first-record', 30)
        self.wait(lambda: (self.pump_stream(), bool(self.live))[1])
        h.save(self.out / 'recording-ready.json', dict(captureId=self.capture_id, pid=self.pid,
            deadlineMonotonic=self.recording_deadline, originalStoreCount=len(self.previous_captures)))

    def pump_stream(self):
        raw = self.stream_capture.paths['stdout'].read_bytes()
        h.require(len(raw) <= s.MAX_CAPTURE, 'recording size exceeded')
        self.live.extend(self.cursor.feed(raw))
        self.decoder = self.cursor.decoder
        if raw:
            h.require(self.decoder.opened == dict(schema=2, kind='open', captureId=self.capture_id,
                diagnostics='ota-link-v1'), 'wrong recording mode')
        if not self.stream_capture.alive():
            h.require(self.decoder.closed is not None and self.stream_capture.process.returncode == 0,
                      'acknowledged stream ended unexpectedly')
        return self.decoder.closed is not None

    def fresh_identity(self, image, after=0, *, request=False):
        self.phase('fresh-device-identity', 180)
        self.pump_stream()
        if request and identity(self.live, image['version'], image['sha256'], self.p['device']['address'], after) is None:
            self.ask('fresh-identity', '\u70b9 App \u53f3\u4e0a\u89d2\u84dd\u7259\u56fe\u6807\u201c\u91cd\u8fde\u53d6\u8bc1\u76ee\u6807\u201d\u3002\u4e0d\u505c\u8bb0\u5f55\uff0c\u4e0d\u7528\u56de\u804a\u5929\u3002')
        def found():
            self.pump_stream()
            return identity(self.live, image['version'], image['sha256'], self.p['device']['address'], after)
        row = self.wait(found)
        self.record('identity-verified', state=row)
        return row

    def ready_package(self, firmware):
        self.phase('manual-package-download', 300)
        code = firmware['target']['version']
        version = '%d.%d.%d' % (code // 10000, code // 100 % 100, code % 100)
        self.ask('check-download', '\u8bf7\u5728\u539f\u9875\u9762\u68c0\u67e5\u5e76\u4e0b\u8f7d ' + version + ' \u56fa\u4ef6\uff0c\u5148\u4e0d\u70b9\u5f00\u59cb\u5347\u7ea7\u3002\u6211\u4f1a\u6838\u5bf9\u5b9e\u9645\u4e0b\u8f7d\u5305\u7684\u6458\u8981\uff0c\u65e0\u9700\u56de\u590d\u3002')
        def ready():
            self.pump_stream()
            if not self.live or self.live[-1]['phase'] != 'readyToInstall':
                return None
            row = self.live[-1]
            r.bound(row, dict(firmware=firmware), package=True)
            h.require(row['freshConnection'] and row['linkConnected'] and row['session'] == row['durable'] == 0,
                      'package owner is not a fresh zero-durable start')
            return row
        return self.wait(ready)

    def finish(self, *, diagnostics):
        self.phase('manual-recording-stop', 180)
        self.stop_notice_sent = True
        self.ask('recording-stop', '\u672c\u8f6e\u7248\u672c\u548c\u677f\u7aef\u72b6\u6001\u5df2\u53d6\u5230\u3002\u8bf7\u53ea\u70b9\u505c\u6b62\u65b9\u6846\uff0c\u7ed3\u675f\u5e76\u4fdd\u7559\u8bb0\u5f55\uff1b\u4e0d\u8981\u518d\u5f00\u59cb\u5347\u7ea7\uff0c\u65e0\u9700\u56de\u590d\u3002')
        self.wait(self.pump_stream)
        self.stream_capture.wait(10)
        self.phase('seal-originals', 180)
        raw = self.original(self.capture_id, self.out / 'app-capture.jsonl')
        self.capture_seal = s.sealed_file(raw, self.capture_id)
        self.capture_resolved = True
        h.require(raw == self.cursor.raw == self.stream_capture.paths['stdout'].read_bytes(),
                  'App/ACK stream original mismatch')
        report = r.audit_link_diagnostics(raw, self.capture_id) if diagnostics else r.audit_capture(raw, self.capture_id)
        remote = '/sdcard/Android/data/' + self.p['app']['id'] + '/files/p35-logcat-diagnostics/' + self.capture_id + '.json'
        mirror = self.cmd(['exec-out', 'cat', remote])
        h.raw(self.out / 'native-mirror.json', mirror)
        r.audit_logcat_status(mirror, self.capture_id, raw)
        for cid, prior in self.previous_captures.items():
            remote = '/sdcard/Android/data/' + self.p['app']['id'] + '/files/p35-observations/' + cid + '.jsonl'
            h.require(self.cmd(['shell', 'sha256sum', remote]).split()[0].decode() == prior['sha256'], 'old original changed')
        self.idle_services()
        h.save(self.out / 'observation.json', report)
        return report

    def preserve_failure(self):
        if self.capture_id is None or self.capture_resolved:
            return
        self.total = min(self.phone.deadline-15, time.monotonic()+150)
        self.phase('preserve-failed-recording', 150)
        try:
            try:
                self.pump_stream()
            except Exception:
                pass
            terminal = self.live and self.live[-1]['phase'] in (
                'idle', 'completed', 'failed', 'cancelled', 'readyToInstall')
            if terminal and not self.stop_notice_sent and not self.decoder.closed:
                self.stop_notice_sent = True
                self.ask('stop-existing-recording', '\u8bf7\u53ea\u70b9\u505c\u6b62\u65b9\u6846\u4fdd\u7559\u73b0\u6709\u8bb0\u5f55\uff0c\u4e0d\u8981\u91cd\u8bd5\u6216\u518d\u6b21\u5347\u7ea7\u3002\u6211\u4f1a\u53d6\u56de\u539f\u4ef6\u6838\u5bf9\u5b9e\u9645\u7ed3\u679c\uff0c\u65e0\u9700\u56de\u590d\u3002')
            remote = '/sdcard/Android/data/' + self.p['app']['id'] + '/files/p35-observations/' + self.capture_id + '.jsonl'
            def sealed():
                raw = self.cmd(['exec-out', 'cat', remote])
                try:
                    return s.sealed_file(raw, self.capture_id)
                except r.Stop:
                    return None
            self.wait(sealed)
            raw = self.original(self.capture_id, self.out / 'failure-original.jsonl')
            self.capture_seal = s.sealed_file(raw, self.capture_id)
            self.capture_resolved = True
            h.save(self.out / 'failure-capture.json', dict(original=h.record(self.out / 'failure-original.jsonl'),
                seal=self.capture_seal, preservesFailure=True, noOtaReplay=True))
        except Exception as error:
            h.save(self.out / 'failure-capture.json', dict(type=type(error).__name__, message=str(error),
                captureId=self.capture_id, noOtaReplay=True, laterReadbackRequired=True))

    def close(self):
        try:
            if self.pending_notice:
                self.pending_notice[1].close('notification-owner-close')
            if self.stream_capture:
                self.stream_capture.close('bounded-P5-recording-close')
        finally:
            self.phone.close()
        h.save(self.out / 'closed.json', dict(privateAdbClosed=self.phone.closed,
            streamClosed=not h.listening(self.stream_port), captureResolved=self.capture_resolved,
            captureId=self.capture_id, pid=self.pid))
