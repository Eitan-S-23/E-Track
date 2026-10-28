"""P3-5 event-driven Release UI automation. No screenshots, Debug VM or PC sender.

The Release telemetry contract in README.md is a prerequisite, not a claim that
Release92 implements it. The new recorder requires a rebuilt Release APK.
"""
from __future__ import annotations

import argparse
from collections import deque
import hashlib
import json
import math
import os
from pathlib import Path
import re
import sys
import time
import xml.etree.ElementTree as ET

ROOT = Path(__file__).resolve().parents[3]
PREFIX = 'OTA_P35_STATE '
PHASES = {'idle', 'checkingUpdate', 'downloading', 'verifyingDownload',
          'readyToInstall', 'transferring', 'applying', 'waitingReboot',
          'reconnectVerify', 'completed', 'failed', 'cancelled'}
HASH = re.compile(r'[0-9a-f]{64}')
IDENT = re.compile(r'[A-Za-z0-9_.:-]{1,128}')
MAX_LINE = 16384


class Stop(RuntimeError):
    def __init__(self, code, detail):
        super().__init__(detail)
        self.code = code


def require(ok, detail, code='PRECONDITION_FAILED'):
    if not ok:
        raise Stop(code, detail)


def strict_json(raw):
    def pairs(items):
        result = {}
        for key, value in items:
            require(key not in result, 'duplicate JSON key', 'EVIDENCE_GAP')
            result[key] = value
        return result
    try:
        return json.loads(raw, object_pairs_hook=pairs,
            parse_constant=lambda _: require(False, 'non-finite JSON', 'EVIDENCE_GAP'))
    except (ValueError, UnicodeError) as error:
        raise Stop('EVIDENCE_GAP', 'invalid UTF-8/JSON') from error


def uint(value, maximum=0xffffffff):
    return type(value) is int and 0 <= value <= maximum


def digest(value):
    return isinstance(value, str) and HASH.fullmatch(value) is not None


def load_host():
    # Reuse project containment, Windows Job ownership and split-stream receipts.
    folder = ROOT / 'Tools/ota/p34-acceptance'
    sys.path.insert(0, str(folder))
    import live_host
    require(live_host.ROOT == ROOT, 'helper loaded from another worktree')
    return live_host


def selector(value):
    require(isinstance(value, dict) and set(value) <= {'resource-id', 'text', 'content-desc'}
            and bool(value), 'selector must use native accessibility fields')
    require(all(isinstance(v, str) and 0 < len(v) <= 160 for v in value.values()), 'invalid selector value')
    return value


def validate_plan(p):
    require(isinstance(p, dict) and type(p.get('schema')) is int and p['schema'] == 1, 'plan schema must be 1')
    require(isinstance(p.get('run_id'), str) and re.fullmatch(r'p35-[a-z0-9-]{1,40}', p['run_id']), 'run_id')
    for section in ['phone', 'app', 'firmware', 'ui', 'limits']:
        require(isinstance(p.get(section), dict), 'missing plan section: ' + section)
    phone, app, fw, ui, limits = (p[k] for k in ['phone', 'app', 'firmware', 'ui', 'limits'])
    require(isinstance(phone.get('serial'), str) and IDENT.fullmatch(phone['serial']), 'phone serial')
    require(isinstance(phone.get('model'), str) and 0 < len(phone['model']) <= 80, 'phone model')
    require(type(phone.get('adb_port')) is int and 1024 <= phone['adb_port'] <= 65535
            and phone['adb_port'] != 5037, 'dedicated ADB port required')
    require(isinstance(app.get('id'), str) and re.fullmatch(r'[a-z][a-z0-9_]*(?:\.[a-z][a-z0-9_]*)+', app['id']), 'application ID')
    require(digest(app.get('sha256')) and uint(app.get('version_code')) and app.get('release') is True, 'pinned Release APK identity')
    require(isinstance(fw.get('device_address'), str) and IDENT.fullmatch(fw['device_address']), 'BLE identity')
    for key in ['current', 'target']:
        require(isinstance(fw.get(key), dict) and uint(fw[key].get('version')) and digest(fw[key].get('sha256')), 'firmware ' + key)
    require(fw['target']['version'] > fw['current']['version'], 'forward target required; never reuse stale downgrade plans')
    for asset in [phone.get('adb'), phone.get('adb_key'), fw.get('package')]:
        require(isinstance(asset, dict) and set(asset) == {'path', 'bytes', 'sha256'} and
                isinstance(asset['path'], str) and asset['path'] and uint(asset['bytes']) and
                asset['bytes'] > 0 and digest(asset['sha256']), 'pinned input file required')
    size = fw['package']['bytes']
    require(type(fw.get('protocol')) is int and fw['protocol'] in (1, 2), 'reviewed wire protocol required')
    require(64 <= size <= 0x180000, 'ETU package bounds')
    require(isinstance(fw.get('release_id'), str) and 0 < len(fw['release_id']) <= 160, 'real backend release binding')
    require(isinstance(fw.get('latest_url'), str) and re.fullmatch(r'https://[a-z0-9.-]+/api/public/firmware/latest', fw['latest_url']), 'real latest URL without credentials/query')
    for key in ['arm', 'stop', 'check', 'download', 'start', 'resume']:
        selector(ui.get(key))
    require(ui['arm'] == {'resource-id': 'p35-arm'} and ui['stop'] == {'resource-id': 'p35-stop'},
            'capture controls must be the dedicated native identifiers, never business-button substitutes')
    for key in ['navigate', 'reconnect']:
        require(isinstance(ui.get(key), list) and len(ui[key]) <= 12, 'bounded UI route')
        for step in ui[key]:
            selector(step)
    for key, minimum, maximum in [('total_seconds', 60, 18000), ('stage_seconds', 5, 600),
                                   ('event_seconds', 1, 10), ('disconnect_seconds', 1, 30)]:
        require(type(limits.get(key)) in (int, float) and math.isfinite(limits[key]) and
                minimum <= limits[key] <= maximum, 'invalid limit: ' + key)
    require(limits['stage_seconds'] < limits['total_seconds'], 'stage deadline must fit total deadline')
    cases = p.get('cases')
    require(isinstance(cases, list) and len(cases) == 10, 'exactly ten planned independent disconnect events required')
    previous, ids = -1, set()
    for case in cases:
        require(isinstance(case, dict) and set(case) == {'id', 'durable_min', 'durable_max', 'bitmap'}, 'case fields')
        require(isinstance(case['id'], str) and re.fullmatch(r'R\d{2}', case['id']) and case['id'] not in ids, 'unique case ID')
        ids.add(case['id'])
        lo, hi = case['durable_min'], case['durable_max']
        require(uint(lo) and uint(hi) and previous < lo <= hi < size and lo % 4096 == 0,
                'ordered, nonoverlapping durable windows before END')
        require(case['bitmap'] in {'zero', 'partial', 'any'}, 'bitmap predicate')
        require(fw['protocol'] == 1 or case['bitmap'] == 'any', 'v2 has no bitmap; do not invent partial bits')
        previous = hi
    require(any(c['durable_min'] == 0 for c in cases) and
            (fw['protocol'] == 2 or any(c['bitmap'] == 'partial' for c in cases))
            and cases[-1]['durable_min'] >= size * .8, 'early/partial/tail coverage required')
    return p


STATE_KEYS = {'schema', 'captureId', 'protocol', 'seq', 'monoUs', 'deviceAddress', 'phase', 'event',
    'currentVersionCode', 'currentImageSha256', 'targetVersionCode', 'targetImageSha256',
    'packageSha256', 'packageBytes', 'packageVerified', 'releaseId', 'latestUrl',
    'durable', 'bitmap', 'linkConnected', 'freshConnection', 'session', 'sendOffset',
    'healthy', 'lost', 'error'}


def validate_state(s):
    require(isinstance(s, dict) and set(s) == STATE_KEYS and type(s['schema']) is int and s['schema'] == 1,
            'missing/unknown Release telemetry fields', 'EVIDENCE_GAP')
    require(uint(s['seq'], 2**63-1) and uint(s['monoUs'], 2**63-1) and isinstance(s['phase'], str)
            and s['phase'] in PHASES and isinstance(s['event'], str)
            and s['event'] in {'state', 'heartbeat', 'beginAck', 'data', 'identity'}, 'telemetry domain', 'EVIDENCE_GAP')
    require(isinstance(s['captureId'], str) and re.fullmatch('[0-9a-f]{32}', s['captureId']), 'capture identity', 'EVIDENCE_GAP')
    require(s['protocol'] is None or type(s['protocol']) is int and s['protocol'] in (1, 2), 'wire protocol', 'EVIDENCE_GAP')
    require((uint(s['bitmap']) if s['protocol'] == 1 else s['bitmap'] is None), 'actual bitmap domain', 'EVIDENCE_GAP')
    for key in ['packageVerified', 'linkConnected', 'freshConnection', 'healthy']:
        require(type(s[key]) is bool, 'telemetry boolean: ' + key, 'EVIDENCE_GAP')
    for key in ['currentVersionCode', 'targetVersionCode', 'packageBytes', 'durable', 'session']:
        require(uint(s[key]), 'telemetry integer: ' + key, 'EVIDENCE_GAP')
    require(s['sendOffset'] is None or uint(s['sendOffset']), 'send offset', 'EVIDENCE_GAP')
    for key in ['currentImageSha256', 'targetImageSha256', 'packageSha256']:
        require(s[key] is None or digest(s[key]), 'telemetry digest: ' + key, 'EVIDENCE_GAP')
    require(s['healthy'] and type(s['lost']) is int and s['lost'] == 0 and s['error'] is None,
            'producer reports lost/error/unhealthy capture', 'EVIDENCE_GAP')
    require(s['durable'] <= s['packageBytes'] and
            (s['protocol'] != 1 or s['session'] <= 255) and
            (s['durable'] % 4096 == 0 or s['durable'] == s['packageBytes']), 'durable domain', 'EVIDENCE_GAP')
    require(isinstance(s['deviceAddress'], str) and IDENT.fullmatch(s['deviceAddress']) and
            (s['releaseId'] is None or isinstance(s['releaseId'], str) and len(s['releaseId']) <= 160) and
            (s['latestUrl'] is None or isinstance(s['latestUrl'], str) and len(s['latestUrl']) <= 300),
            'telemetry string domains', 'EVIDENCE_GAP')
    return s


class Decoder:
    """Incremental parser; no partial line, old PID, dropped sequence or invented state."""
    def __init__(self):
        self.pending = b''
        self.previous = None
        self.closed = None

    def feed(self, data):
        self.pending += data
        rows = self.pending.split(b'\n')
        self.pending = rows.pop()
        require(len(self.pending) <= MAX_LINE, 'oversize/truncated producer line', 'EVIDENCE_GAP')
        result = []
        for row in rows:
            require(len(row) <= MAX_LINE, 'oversize producer line', 'EVIDENCE_GAP')
            if b'chatty' in row or b'dropped' in row.lower():
                raise Stop('EVIDENCE_GAP', 'logcat reports potential loss')
            require(b'OTA_P35_ERROR ' not in row, 'App recorder failure', 'EVIDENCE_GAP')
            marker = row.find(b'OTA_P35_CAPTURE ')
            if marker >= 0:
                capture = strict_json(row[marker + len(b'OTA_P35_CAPTURE '):])
                if capture.get('kind') == 'close':
                    self.closed = capture
            start = row.find(PREFIX.encode())
            if start < 0:
                continue
            s = validate_state(strict_json(row[start + len(PREFIX):]))
            if self.previous is not None:
                require(s['captureId'] == self.previous['captureId'] and
                        s['seq'] == self.previous['seq'] + 1 and s['monoUs'] >= self.previous['monoUs'],
                        'lost/replayed/reordered producer records', 'EVIDENCE_GAP')
            self.previous = s
            result.append(s)
        return result


def audit_capture(raw, capture_id):
    """Check unchanged App originals; never manufacture a footer for a lost run."""
    require(len(raw) <= 128 * 1024 * 1024 + 8192 and raw.endswith(b'\n'), 'incomplete/oversized App capture', 'EVIDENCE_GAP')
    rows = raw.splitlines(keepends=True)
    marker = b'OTA_P35_CAPTURE '
    require(len(rows) >= 3 and rows[0].startswith(marker) and rows[-1].startswith(marker),
            'App capture missing header/footer; preserve partial file', 'EVIDENCE_GAP')
    header, footer = (strict_json(row[len(marker):]) for row in (rows[0], rows[-1]))
    require(header == dict(schema=1, kind='open', captureId=capture_id), 'wrong App capture header', 'EVIDENCE_GAP')
    require(set(footer) == {'schema', 'kind', 'captureId', 'records', 'sha256', 'healthy', 'lost', 'error'} and
            footer['schema'] == 1 and footer['kind'] == 'close' and footer['captureId'] == capture_id and
            footer['healthy'] is True and type(footer['lost']) is int and footer['lost'] == 0 and footer['error'] is None,
            'unhealthy App capture footer', 'EVIDENCE_GAP')
    states_raw = b''.join(rows[1:-1])
    require(all(row.startswith(PREFIX.encode()) for row in rows[1:-1]), 'unexpected persisted record', 'EVIDENCE_GAP')
    decoder = Decoder()
    states = decoder.feed(states_raw)
    require(states and states[0]['seq'] == 1 and all(s['captureId'] == capture_id for s in states) and
            type(footer['records']) is int and len(states) == footer['records'] and
            footer['sha256'] == hashlib.sha256(states_raw).hexdigest(), 'App capture count/hash/sequence mismatch', 'EVIDENCE_GAP')
    return dict(captureId=capture_id, records=len(states), sha256=hashlib.sha256(raw).hexdigest(),
                final=states[-1], integrity='VERIFIED', formalAcceptance='NOT_ADJUDICATED')


def find_control(xml, wanted, package):
    selector(wanted)
    require(len(xml) <= 2 * 1024 * 1024 and b'<!DOCTYPE' not in xml and b'<!ENTITY' not in xml,
            'unsafe/oversize UI hierarchy', 'UI_UNAVAILABLE')
    begin, end = xml.find(b'<hierarchy'), xml.rfind(b'</hierarchy>')
    require(begin >= 0 and end >= begin, 'native accessibility tree unavailable; no screenshot fallback', 'UI_UNAVAILABLE')
    try:
        root = ET.fromstring(xml[begin:end + len(b'</hierarchy>')])
    except ET.ParseError as error:
        raise Stop('UI_UNAVAILABLE', 'malformed native hierarchy') from error
    parents = {child: parent for parent in root.iter() for child in parent}
    matches = []
    for node in root.iter('node'):
        if not all(node.get(k) == v for k, v in wanted.items()):
            continue
        require(node.get('package') == package, 'selector matched foreign app/overlay', 'UI_UNAVAILABLE')
        require(node.get('enabled') == 'true' and node.get('visible-to-user') != 'false',
                'target control disabled/hidden', 'UI_UNAVAILABLE')
        if node.get('clickable') != 'true':
            # Flutter may put identifier on a semantic container and the actual
            # button action on its child. Never pick among multiple actions.
            children = [child for child in node.iter('node') if child is not node and child.get('clickable') == 'true']
            require(len(children) <= 1, 'identifier contains ambiguous actions', 'UI_UNAVAILABLE')
            if children:
                node = children[0]
                require(node.get('package') == package and node.get('enabled') == 'true' and
                        node.get('visible-to-user') != 'false', 'descendant disabled/foreign/hidden', 'UI_UNAVAILABLE')
        while node.get('clickable') != 'true' and node in parents:
            node = parents[node]
        require(node.get('package') == package and node.get('clickable') == 'true'
                and node.get('enabled') == 'true', 'control disabled/not clickable', 'UI_UNAVAILABLE')
        matches.append(node)
    unique = {id(n): n for n in matches}
    require(unique, 'control missing; no blind coordinates', 'UI_UNAVAILABLE')
    require(len(unique) == 1, 'control ambiguous; no blind coordinates', 'UI_UNAVAILABLE')
    node = next(iter(unique.values()))
    bounds = re.fullmatch(r'\[(\d+),(\d+)\]\[(\d+),(\d+)\]', node.get('bounds', ''))
    require(bounds is not None, 'invalid control bounds', 'UI_UNAVAILABLE')
    x1, y1, x2, y2 = map(int, bounds.groups())
    require(0 <= x1 < x2 <= 20000 and 0 <= y1 < y2 <= 20000, 'empty/outside control', 'UI_UNAVAILABLE')
    return ((x1+x2)//2, (y1+y2)//2)


def bound(s, p, *, package=False, final=False):
    fw = p['firmware']
    require(s['protocol'] is None or s['protocol'] == fw['protocol'], 'negotiated protocol differs from reviewed plan', 'IDENTITY_MISMATCH')
    identity = fw['target' if final else 'current']
    require(s['deviceAddress'] == fw['device_address'] and
            s['currentVersionCode'] == identity['version'] and s['currentImageSha256'] == identity['sha256'],
            'fresh device identity differs from plan', 'IDENTITY_MISMATCH')
    if package:
        require(s['targetVersionCode'] == fw['target']['version'] and s['targetImageSha256'] == fw['target']['sha256']
                and s['packageSha256'] == fw['package']['sha256'] and s['packageBytes'] == fw['package']['bytes']
                and s['packageVerified'] and s['releaseId'] == fw['release_id'] and s['latestUrl'] == fw['latest_url'],
                'App verified package/backend binding differs from plan', 'IDENTITY_MISMATCH')


def case_matches(s, case):
    bitmap = s['bitmap']
    return case['durable_min'] <= s['durable'] <= case['durable_max'] and (
        case['bitmap'] == 'any' or case['bitmap'] == 'zero' and bitmap == 0
        or case['bitmap'] == 'partial' and 0 < bitmap < 0xffffffff)


def resume_offset(s):
    if s['protocol'] == 2:
        return s['durable']
    return s['durable'] + next((n for n in range(32) if not s['bitmap'] & (1 << n)), 32) * 128


class Campaign:
    def __init__(self, plan, driver, clock=time.monotonic):
        self.p, self.io, self.clock = validate_plan(plan), driver, clock
        self.deadline = clock() + plan['limits']['total_seconds']
        self.state, self.cases = None, []
        self.progress, self.progress_at = None, clock()

    def wait(self, predicate, stage, seconds=None, *, allow_failure=False):
        deadline = min(self.deadline, self.clock() + (seconds or self.p['limits']['stage_seconds']))
        while self.clock() < deadline:
            state = self.io.next_state(min(self.p['limits']['event_seconds'], deadline - self.clock()))
            validate_state(state)
            require(state['deviceAddress'] == self.p['firmware']['device_address'],
                    'event from a different BLE device', 'IDENTITY_MISMATCH')
            self.state = state
            if state['phase'] == 'transferring':
                if self.progress is None or state['durable'] > self.progress:
                    self.progress, self.progress_at = state['durable'], self.clock()
                require(self.clock() - self.progress_at < 30, '30 seconds without MCU durable progress', 'NO_DURABLE_PROGRESS')
            else:
                self.progress, self.progress_at = None, self.clock()
            if not allow_failure:
                require(state['phase'] not in {'failed', 'cancelled'}, 'App terminal during ' + stage, 'PRODUCT_OR_ENV_FAILURE')
            if predicate(state):
                self.io.record('observed', stage=stage, state=state)
                return state
        raise Stop('EVIDENCE_GAP', 'stage deadline: ' + stage)

    def run(self):
        # The driver has already started durable raw capture before any UI action.
        initial = self.wait(lambda s: s['phase'] == 'idle', 'initial-idle')
        bound(initial, self.p)
        require(initial['linkConnected'], 'connect/identify the target before executing the campaign')
        for step in self.p['ui']['navigate']:
            self.io.tap(step)
        self.io.tap(self.p['ui']['check'])
        self.wait(lambda s: s['phase'] == 'checkingUpdate', 'fresh-query-start')
        queried = self.wait(lambda s: s['phase'] in {'idle', 'downloading', 'readyToInstall'}, 'latest-result')
        require(queried['targetVersionCode'] == self.p['firmware']['target']['version'],
                'latest did not select the admitted target; do not publish or manufacture a release')
        if queried['phase'] == 'idle':
            self.io.tap(self.p['ui']['download'])
        ready = self.wait(lambda s: s['phase'] == 'readyToInstall', 'download-and-verify')
        bound(ready, self.p, package=True)
        require(ready['linkConnected'] and ready['freshConnection'], 'fresh package-owner identity required before start', 'IDENTITY_MISMATCH')
        self.io.tap(self.p['ui']['start'])
        self.wait(lambda s: s['event'] == 'beginAck', 'initial-BEGIN')
        require(self.state['durable'] == 0 and self.state['bitmap'] in (None, 0), 'unknown initial staging; no reset/erase workaround')
        for case in self.p['cases']:
            def at_boundary(s):
                bound(s, self.p, package=True)
                require(s['phase'] == 'transferring' and s['durable'] <= case['durable_max'],
                        'missed planned disconnect boundary: ' + case['id'], 'EVIDENCE_GAP')
                return s['linkConnected'] and case_matches(s, case)
            before = self.wait(at_boundary, case['id'] + '-boundary')
            self.io.record('disconnect-intent', case=case['id'], state=before)
            try:
                self.io.radio(False, case=case)
                cut = self.wait(lambda s: not s['linkConnected'], case['id'] + '-actual-disconnect',
                    self.p['limits']['disconnect_seconds'], allow_failure=True)
                require(case_matches(cut, case), 'actual disconnect outside frozen window', 'EVIDENCE_GAP')
                require(cut['durable'] >= before['durable'], 'durable regressed at disconnect', 'EVIDENCE_GAP')
            finally:
                # Restore the adapter, not the firmware or an uncertain UI operation.
                if self.io.radio_touched:
                    self.io.radio(True)
            for step in self.p['ui']['reconnect']:
                self.io.tap(step)
            connected = self.wait(lambda s: s['linkConnected'] and s['freshConnection'],
                case['id'] + '-reconnected', allow_failure=True)
            bound(connected, self.p, package=True)
            self.io.tap(self.p['ui']['resume'])
            resumed = self.wait(lambda s: s['event'] == 'beginAck', case['id'] + '-resume-BEGIN', allow_failure=True)
            bound(resumed, self.p, package=True)
            require(cut['durable'] <= resumed['durable'] <= case['durable_max'],
                    'MCU resume prefix regressed or escaped planned window', 'EVIDENCE_GAP')
            expected = resume_offset(resumed)
            require(expected < self.p['firmware']['package']['bytes'], 'no missing DATA left to prove recovery')
            first = self.wait(lambda s: s['event'] == 'data', case['id'] + '-first-resumed-DATA')
            bound(first, self.p, package=True)
            require(first['session'] == resumed['session'] and first['sendOffset'] == expected,
                    'sender did not follow MCU durable/bitmap', 'PRODUCT_OR_ENV_FAILURE')
            self.wait(lambda s: s['durable'] > resumed['durable'], case['id'] + '-durable-progress')
            value = dict(id=case['id'], before=before, disconnected=cut, resume=resumed, firstData=first)
            self.cases.append(value)
            self.io.record('recovery-observed', **value)
        final = self.wait(lambda s: s['phase'] == 'completed' and s['event'] == 'identity', 'post-reboot-identity')
        bound(final, self.p, package=True, final=True)
        require(final['freshConnection'] and final['linkConnected'] and final['durable'] == self.p['firmware']['package']['bytes'],
                'END/UI completion is not fresh final identity', 'EVIDENCE_GAP')
        return dict(outcome='AUTOMATION_COMPLETED', recovered=len(self.cases), final=final,
                    formalAcceptance='NOT_ADJUDICATED', cases=self.cases)


class Android:
    """Thin standard adb/uiautomator adapter; logcat writes independently of polling."""
    def __init__(self, p, out, h):
        self.p, self.out, self.h = p, out, h
        self.env = h.environment(out, p['phone']['adb_key'])
        self.base = [str(h.pinned(p['phone']['adb'])), '-H', '127.0.0.1', '-P',
                     str(p['phone']['adb_port']), '-s', p['phone']['serial']]
        self.server = self.capture = None
        self.pid = self.initial_radio = None
        self.radio_touched = False
        self.restore_attempted = False
        self.sequence, self.offset, self.journal_seq = 0, 0, 0
        self.decoder, self.queue = Decoder(), deque()
        self.total_deadline = time.monotonic() + p['limits']['total_seconds'] + 30
        self.last_ui = None
        self.last_state_at = None
        self.campaign = None

    def record(self, event, **fields):
        self.journal_seq += 1
        self.h.save(self.out / 'journal' / ('%05d.json' % self.journal_seq),
                    dict(event=event, hostMonoNs=time.monotonic_ns(), **fields))

    def cmd(self, args, seconds=15):
        import shlex
        require(self.server and self.server.alive() and self.h.listening(self.p['phone']['adb_port']),
                'private ADB owner unavailable', 'COLLECTOR_FAILED')
        require(time.monotonic() + seconds < self.total_deadline, 'command exceeds campaign deadline')
        self.sequence += 1
        if args[0] in ('shell', 'exec-out'):
            args = [args[0], ' '.join(shlex.quote(str(x)) for x in args[1:])]
        return self.h.command(self.out / 'commands', 'adb-%05d' % self.sequence,
                              self.base + args, self.env, seconds=seconds)

    def startup(self, *, retrieval_only=False):
        port = self.p['phone']['adb_port']
        require(not self.h.listening(port), 'private ADB port already owned')
        self.server = self.h.Process(self.out, 'adb-server',
            [self.base[0], '-P', str(port), 'nodaemon', 'server'], self.env)
        self.h.wait_for(lambda: self.server.alive() and self.h.listening(port), 10)
        require(self.cmd(['get-serialno']).strip().decode() == self.p['phone']['serial'], 'wrong phone')
        require(self.cmd(['shell', 'getprop', 'ro.product.model']).strip().decode() == self.p['phone']['model'], 'wrong phone model')
        app = self.p['app']
        location = self.cmd(['shell', 'pm', 'path', app['id']]).decode().strip()
        require(re.fullmatch(r'package:/data/app/[A-Za-z0-9/_.=+~-]+/base\.apk', location), 'ambiguous/split APK; not installing another')
        actual = self.cmd(['shell', 'sha256sum', location[8:]]).decode().split()[0]
        require(actual == app['sha256'], 'installed APK hash mismatch')
        package = self.cmd(['shell', 'dumpsys', 'package', app['id']]).decode()
        require('DEBUGGABLE' not in package and re.search(r'\bversionCode=' + str(app['version_code']) + r'\b', package), 'not the pinned non-debuggable version')
        if retrieval_only:
            return
        pid = self.cmd(['shell', 'pidof', app['id']]).strip().decode()
        require(pid.isdigit(), 'one running Release process required; no force-stop/automatic relaunch')
        self.pid = pid
        self.initial_radio = self.radio_state()
        require(self.initial_radio is True, 'Bluetooth must initially be on')
        self.capture = self.h.Process(self.out, 'logcat', self.base +
            ['logcat', '-v', 'epoch', '--pid=' + pid, '-T', '1', '*:V'], self.env)
        # Discard pre-readiness buffered lines. A fresh producer heartbeat must follow.
        time.sleep(.2)
        require(self.capture.alive(), 'logcat did not start', 'COLLECTOR_FAILED')
        self.offset = self.capture.paths['stdout'].stat().st_size
        self.record('capture-started', pid=pid, apkSha256=actual, screenshots=False)

    def pump(self):
        require(self.capture and self.capture.alive() and self.server.alive(), 'collector/ADB stopped; no action replay', 'COLLECTOR_FAILED')
        path = self.capture.paths['stdout']
        size = path.stat().st_size
        require(self.offset <= size <= 256 * 1024 * 1024 and size - self.offset <= 1024 * 1024,
                'capture truncated, oversized or control consumer fell behind', 'EVIDENCE_GAP')
        with path.open('rb') as stream:
            stream.seek(self.offset)
            data = stream.read()
        self.offset += len(data)
        states = self.decoder.feed(data)
        require(all(s['deviceAddress'] == self.p['firmware']['device_address'] for s in states),
                'App switched target during capture; no further UI/radio actions', 'IDENTITY_MISMATCH')
        if states:
            self.last_state_at = time.monotonic()
        self.queue.extend(states)
        require(len(self.queue) <= 1000, 'event backlog; refusing late injection', 'EVIDENCE_GAP')

    def next_state(self, seconds):
        deadline = min(time.monotonic() + seconds, self.total_deadline)
        while time.monotonic() < deadline:
            self.pump()
            if self.queue:
                return self.queue.popleft()
            time.sleep(.02)
        raise Stop('CAPABILITY_MISSING', 'no fresh persisted Release telemetry; Release92 predates the recorder')

    def ui(self):
        require(self.cmd(['shell', 'pidof', self.p['app']['id']]).strip().decode() == self.pid,
                'App process changed', 'EVIDENCE_GAP')
        focus = self.cmd(['shell', 'dumpsys', 'window', 'windows']).decode(errors='replace')
        focus_lines = [line for line in focus.splitlines() if 'mCurrentFocus=' in line]
        require(len(focus_lines) == 1 and re.search(r'\b' + re.escape(self.p['app']['id']) + r'/', focus_lines[0]),
                'target App not unobscured foreground; no permission-dialog auto-approval', 'UI_UNAVAILABLE')
        self.last_ui = self.cmd(['exec-out', 'uiautomator', 'dump', '--compressed', '/dev/tty'])
        return self.last_ui

    def tap(self, wanted, *, bootstrap=False):
        require(not bootstrap or wanted == {'resource-id': 'p35-arm'},
                'only the dedicated record control may precede telemetry readiness')
        self.pump()
        point = None
        # Scroll only within a native, package-owned viewport. No screenshots or
        # absolute screen assumptions, and never retry an uncertain business tap.
        for attempt in range(13):
            xml = self.ui()
            try:
                point = find_control(xml, wanted, self.p['app']['id'])
                break
            except Stop as error:
                if error.code != 'UI_UNAVAILABLE' or attempt == 12:
                    raise
                if 'disabled' in str(error):
                    time.sleep(.25)
                    continue
                require('control missing' in str(error), str(error), error.code)
                require(b'<!' not in xml, 'unsafe scroll hierarchy', 'UI_UNAVAILABLE')
                begin, end = xml.find(b'<hierarchy'), xml.rfind(b'</hierarchy>')
                tree = ET.fromstring(xml[begin:end + len(b'</hierarchy>')])
                views = [n for n in tree.iter('node') if n.get('package') == self.p['app']['id'] and
                         n.get('scrollable') == 'true' and n.get('enabled') == 'true']
                require(len(views) == 1, 'no unique native scroll viewport', 'UI_UNAVAILABLE')
                bounds = re.fullmatch(r'\[(\d+),(\d+)\]\[(\d+),(\d+)\]', views[0].get('bounds', ''))
                require(bounds is not None, 'invalid scroll viewport', 'UI_UNAVAILABLE')
                x1, y1, x2, y2 = map(int, bounds.groups())
                require(0 <= x1 < x2 <= 20000 and 0 <= y1 < y2 <= 20000, 'invalid viewport bounds', 'UI_UNAVAILABLE')
                x, top, bottom = (x1+x2)//2, y1+(y2-y1)//4, y1+3*(y2-y1)//4
                a, b = (bottom, top) if attempt < 6 else (top, bottom)
                self.cmd(['shell', 'input', 'swipe', str(x), str(a), str(x), str(b), '250'], seconds=5)
                self.pump()
        require(point is not None, 'control not found', 'UI_UNAVAILABLE')
        self.pump()
        require(bootstrap or self.last_state_at is not None and time.monotonic() - self.last_state_at < self.p['limits']['event_seconds'],
                'producer heartbeat expired before UI action', 'COLLECTOR_FAILED')
        require(not self.queue or self.queue[-1]['healthy'], 'capture unhealthy before UI action')
        self.record('tap-intent', selector=wanted, point=list(point))
        self.cmd(['shell', 'input', 'tap', str(point[0]), str(point[1])], seconds=5)
        self.record('tap-command-returned', selector=wanted)

    def retrieve(self, capture_id):
        require(isinstance(capture_id, str) and re.fullmatch('[0-9a-f]{32}', capture_id), 'explicit capture ID required')
        remote = '/sdcard/Android/data/' + self.p['app']['id'] + '/files/p35-observations/' + capture_id + '.jsonl'
        size = self.cmd(['shell', 'wc', '-c', remote]).split()[0]
        require(size.isdigit() and int(size) <= 128 * 1024 * 1024 + 8192, 'oversized App original', 'EVIDENCE_GAP')
        raw = self.cmd(['exec-out', 'cat', remote], seconds=60)
        self.h.raw(self.out / 'app-capture.jsonl', raw)
        report = audit_capture(raw, capture_id)
        self.h.save(self.out / 'app-capture-integrity.json', report)
        return report

    def finish_capture(self):
        capture_id = self.decoder.previous['captureId']
        self.tap(self.p['ui']['stop'])
        until = time.monotonic() + self.p['limits']['stage_seconds']
        while self.decoder.closed is None and time.monotonic() < until:
            self.pump()
            time.sleep(.05)
        require(self.decoder.closed is not None, 'no App close receipt; retrieve originals later, never replay OTA', 'EVIDENCE_GAP')
        report = self.retrieve(capture_id)
        require(report['final'] == self.decoder.previous, 'live/stored final records differ', 'EVIDENCE_GAP')
        return report

    def radio_state(self):
        text = self.cmd(['shell', 'dumpsys', 'bluetooth_manager']).decode(errors='replace')
        values = re.findall(r'(?m)^\s*state:\s*(ON|OFF)\s*$', text)
        require(len(values) == 1, 'unqualified Android Bluetooth state format', 'CAPABILITY_MISSING')
        return values[0] == 'ON'

    def radio(self, enabled, *, case=None):
        require(self.p.get('allow_bluetooth_toggle') is True, 'adapter toggle affects other phone Bluetooth connections; explicit plan opt-in required')
        if not enabled:
            self.pump()
            latest = self.decoder.previous
            require(latest is not None and self.last_state_at is not None and
                    time.monotonic() - self.last_state_at < self.p['limits']['event_seconds'],
                    'stale capture before radio injection', 'COLLECTOR_FAILED')
            require(case is not None and latest['phase'] == 'transferring' and latest['linkConnected'] and
                    case_matches(latest, case), 'live state escaped disconnect window before command', 'EVIDENCE_GAP')
        if enabled:
            require(not self.restore_attempted, 'radio restoration already attempted; reconcile actual state', 'CLEANUP_FAILED')
            self.restore_attempted = True
        else:
            self.restore_attempted = False
        self.radio_touched = True  # An uncertain disable still needs one safe restore attempt.
        self.record('radio-intent', enabled=enabled)
        self.cmd(['shell', 'cmd', 'bluetooth_manager', 'enable' if enabled else 'disable'], seconds=5)
        deadline = time.monotonic() + self.p['limits']['disconnect_seconds']
        while time.monotonic() < deadline:
            if self.radio_state() == enabled:
                self.record('radio-state-observed', enabled=enabled)
                if enabled:
                    self.radio_touched = False
                return
            time.sleep(.05)
        raise Stop('ENV_BLOCKED', 'Bluetooth command did not reach requested state')

    def close(self):
        errors = []
        if self.radio_touched:
            if self.restore_attempted:
                errors.append('radio restoration unresolved after its bounded attempt')
            else:
                try:
                    self.radio(True)
                except Exception as error:
                    errors.append('radio restoration: ' + str(error))
        for process in [self.capture, self.server]:
            if process:
                try:
                    process.close('p35-owner-finished')
                except Exception as error:
                    errors.append('owned process: ' + str(error))
        require(not self.h.listening(self.p['phone']['adb_port']), 'private ADB still listening', 'CLEANUP_FAILED')
        require(not errors, '; '.join(errors), 'CLEANUP_FAILED')


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('mode', choices=['check', 'probe', 'run', 'retrieve', 'audit'])
    parser.add_argument('--plan', type=Path)
    parser.add_argument('--archive', type=Path, help='offline audit of an unchanged App JSONL file')
    parser.add_argument('--out', type=Path)
    parser.add_argument('--execute', action='store_true', help='required for UI/radio mutations; not formal acceptance authorization')
    parser.add_argument('--capture-id', help='retrieve unchanged App originals after USB recovery; no UI or OTA replay')
    args = parser.parse_args(argv)
    require(Path.cwd() == ROOT and sys.flags.isolated and sys.flags.no_site and sys.dont_write_bytecode,
            'run from active root with python -I -S -B -X utf8')
    if args.mode == 'audit':
        require(args.archive is not None and args.capture_id is not None and args.plan is None and
                args.out is None and not args.execute, 'audit is read-only and requires archive and capture ID')
        require(args.archive.stat().st_size <= 128 * 1024 * 1024 + 8192, 'oversized App original', 'EVIDENCE_GAP')
        print(json.dumps(audit_capture(args.archive.read_bytes(), args.capture_id)))
        return 0
    require(args.plan is not None and args.archive is None, 'plan required; archive only for offline audit')
    p = validate_plan(strict_json(args.plan.read_bytes()))
    if args.mode == 'check':
        require(not args.execute and args.out is None, 'check is offline/no outputs')
        print(json.dumps(dict(plan='VALID', cases=10, deviceOperations=0, liveQualification='NOT_RUN')))
        return 0
    require(args.out is not None and (args.mode != 'run' or args.execute), 'explicit output and --execute required')
    require(args.mode == 'run' or not args.execute, 'read-only mode never accepts --execute')
    require((args.mode == 'retrieve') == (args.capture_id is not None), 'capture ID only for retrieval')
    if args.capture_id is not None:
        require(re.fullmatch('[0-9a-f]{32}', args.capture_id), 'invalid capture ID')
    h = load_host()
    out = h.checked(args.out)
    require(not out.exists(), 'existing/uncertain run directory; do not replay')
    for name in ['plan.json', 'inputs.json', 'result.json', 'journal', 'commands', 'adb-server.stdout', 'adb-server.stderr',
                 'adb-server.started.json', 'adb-server.closed.json', 'logcat.stdout', 'logcat.stderr',
                 'logcat.started.json', 'logcat.closed.json', 'host', 'app-capture.jsonl', 'app-capture-integrity.json',
                 'previous-owner.stdout', 'previous-owner.stderr', 'previous-owner.started.json',
                 'previous-owner.closed.json', 'unresolved-owner.json']:
        h.checked(out / name)
    for pin in [p['phone']['adb'], p['phone']['adb_key'], p['firmware']['package']]:
        h.pinned(pin)
    h.save(out / 'plan.json', p)
    h.save(out / 'inputs.json', dict(mode=args.mode,
        planSha256=hashlib.sha256(args.plan.read_bytes()).hexdigest(),
        runner=h.record(Path(__file__)), hostHelper=h.record(Path(h.__file__)),
        formalAcceptance=False))
    result = dict(outcome='NOT_RUN', formalAcceptance='NOT_ADJUDICATED', recovered=0)
    driver = None
    try:
        with h.device_owner(out, read_only=args.mode in {'probe', 'retrieve'}):
            driver = Android(p, out, h)
            try:
                driver.startup(retrieval_only=args.mode == 'retrieve')
                if args.mode == 'retrieve':
                    result.update(outcome='ORIGINALS_RETRIEVED', archive=driver.retrieve(args.capture_id))
                else:
                    result.update(execute_ui(args.mode, p, driver))
            except Exception as error:
                result['executionError'] = dict(code=getattr(error, 'code', 'HOST_FAILED'), detail=str(error))
                raise
            finally:
                driver.close()
    except Exception as error:
        result.update(outcome=getattr(error, 'code', 'HOST_FAILED'), detail=str(error),
                      recovered=len(driver.campaign.cases) if driver and driver.campaign else 0,
                      preserveOriginals=True, replay=False)
    h.save(out / 'result.json', result)
    print(json.dumps({k: v for k, v in result.items() if k not in {'cases', 'final'}}))
    return 0 if result['outcome'] in {'PROBE_READY', 'AUTOMATION_COMPLETED', 'ORIGINALS_RETRIEVED'} else 2


def execute_ui(mode, p, driver):
    if mode == 'run':
        require(p.get('allow_bluetooth_toggle') is True, 'explicit adapter-toggle scope required')
        driver.tap(p['ui']['arm'], bootstrap=True)
    else:
        find_control(driver.ui(), p['ui']['check'], p['app']['id'])
    state = driver.next_state(p['limits']['event_seconds'])
    bound(state, p)
    require(state['phase'] == 'idle' and state['linkConnected'] and state['freshConnection'], 'unknown/busy starting state')
    driver.queue.appendleft(state)
    if mode == 'probe':
        return dict(outcome='PROBE_READY', telemetry=True, checkControl=True, deviceMutations=0,
                    radioInjection='NOT_TESTED', fullCampaign='NOT_RUN')
    driver.campaign = Campaign(p, driver)
    result = driver.campaign.run()
    result['archive'] = driver.finish_capture()
    return result


if __name__ == '__main__':
    try:
        raise SystemExit(main())
    except (Stop, OSError) as error:
        print(json.dumps(dict(outcome=getattr(error, 'code', 'INPUT_ERROR'), detail=str(error))), file=sys.stderr)
        raise SystemExit(2)
