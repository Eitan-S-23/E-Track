"""Thin no-OTA route for runner.py. Only native semantics and original App logs."""
from __future__ import annotations

import argparse
import csv
import hashlib
import io
import json
import math
import os
from pathlib import Path
import re
import shlex
import sys
import time

import runner as r

ROOT = r.ROOT
MAC = re.compile(r'[0-9a-f]{2}(?::[0-9a-f]{2}){5}')
MAX_CAPTURE = 128 * 1024 * 1024 + 8192
ARM, STOP, QUERY = ({'resource-id': 'p35-' + s} for s in ('arm', 'stop', 'reconnect'))
# Exact semantic labels of the installed speedometer route, not screen positions.
HOME = {'content-desc': '\u7801\u8868', 'class': 'android.widget.Button'}
DEVICES = {'content-desc': '\u8bbe\u5907'}
CONNECT = {'content-desc': '\u8fde\u63a5\u8bbe\u5907'}
CONNECTED = '\u5df2\u8fde\u63a5'
FIRMWARE = '\u7801\u8868\u56fa\u4ef6'
DEVICE_ID = '\u8bbe\u5907ID'
OPEN_FIRMWARE = '\u68c0\u67e5\u5355\u7247\u673a\u56fa\u4ef6\u66f4\u65b0'
CLOSED_RECORDER = '\u5f00\u59cb\u81ea\u52a8\u5316\u8bb0\u5f55\uff08\u5305\u542b\u8bbe\u5907\u6807\u8bc6\uff0c\u6700\u957f\u4e00\u5c0f\u65f6\uff09: closed'
UNREADY_HINT = '\u8bbe\u5907\u8eab\u4efd\u672a\u786e\u8ba4\uff08\u672a\u8bc6\u522b\u5230 OTA \u670d\u52a1\u6216\u8eab\u4efd\u8bfb\u53d6\u5931\u8d25\uff09\uff0c\u6682\u4e0d\u80fd\u68c0\u67e5\u66f4\u65b0'


def validate(p):
    r.require(isinstance(p, dict) and set(p) - {'lifecycle'} == {'schema', 'run_id', 'phone', 'app',
        'device', 'scenario', 'limits'}, 'no-OTA configuration fields')
    if 'lifecycle' in p:
        r.require(isinstance(p['lifecycle'], dict) and set(p['lifecycle']) == {'restart_closed_recorder'} and
            type(p['lifecycle']['restart_closed_recorder']) is bool, 'explicit test-App-only lifecycle permission')
    r.require(type(p['schema']) is int and p['schema'] == 2, 'smoke schema must be 2')
    r.require(isinstance(p['run_id'], str) and re.fullmatch(r'p35-[a-z0-9-]{1,40}', p['run_id']), 'run_id')
    for section in ('phone', 'app', 'device', 'scenario', 'limits'):
        r.require(isinstance(p[section], dict), 'configuration section: ' + section)
    phone, app, device, scenario, limits = (p[k] for k in ('phone', 'app', 'device', 'scenario', 'limits'))
    r.require(set(phone) == {'serial', 'model', 'adb_port', 'adb', 'adb_key'}, 'phone fields')
    r.require(isinstance(phone['serial'], str) and r.IDENT.fullmatch(phone['serial']), 'phone serial')
    r.require(isinstance(phone['model'], str) and 0 < len(phone['model']) <= 80, 'phone model')
    r.require(type(phone['adb_port']) is int and 1024 <= phone['adb_port'] <= 65535
              and phone['adb_port'] != 5037, 'private ADB port required')
    for pin in (phone['adb'], phone['adb_key']):
        r.require(isinstance(pin, dict) and set(pin) == {'path', 'bytes', 'sha256'} and
            isinstance(pin['path'], str) and pin['path'] and r.uint(pin['bytes']) and
            pin['bytes'] > 0 and r.digest(pin['sha256']), 'pinned executable/key input required')
    r.require(set(app) == {'id', 'sha256', 'version_code', 'release'} and
        isinstance(app['id'], str) and re.fullmatch(r'[a-z][a-z0-9_]*(?:\.[a-z][a-z0-9_]*)+\.p35acceptance', app['id'])
        and r.digest(app['sha256']) and r.uint(app['version_code']) and app['release'] is True,
        'pinned side-by-side Release test APP required; no installation fallback')
    r.require(set(device) == {'address', 'display_name', 'expected_version', 'expected_sha256'} and
        isinstance(device['address'], str) and MAC.fullmatch(device['address']) and
        isinstance(device['display_name'], str) and len(device['display_name']) <= 128,
        'explicit lowercase target MAC and optional exact advertised name required')
    r.require(device['expected_version'] is None or r.uint(device['expected_version']) and device['expected_version'] > 0,
              'optional version pin')
    r.require(device['expected_sha256'] is None or r.digest(device['expected_sha256']), 'optional image pin')
    r.require(set(scenario) == {'kind', 'capture_seconds', 'min_heartbeats'} and scenario['kind'] == 'no-ota-smoke',
              'this entry cannot authorize or execute OTA/fault injection')
    r.require(type(scenario['capture_seconds']) in (int, float) and math.isfinite(scenario['capture_seconds']) and
        5 <= scenario['capture_seconds'] <= 60 and type(scenario['min_heartbeats']) is int and
        3 <= scenario['min_heartbeats'] <= scenario['capture_seconds'], 'finite capture coverage')
    r.require(set(limits) == {'total_seconds', 'stage_seconds', 'command_seconds', 'event_seconds', 'cleanup_seconds'},
              'limit fields')
    for key, lo, hi in [('total_seconds', 120, 900), ('stage_seconds', 10, 120),
        ('command_seconds', 5, 60), ('event_seconds', 2, 10), ('cleanup_seconds', 20, 90)]:
        r.require(type(limits[key]) in (int, float) and math.isfinite(limits[key]) and lo <= limits[key] <= hi,
                  'finite limit: ' + key)
    r.require(limits['stage_seconds'] < limits['total_seconds'] and
        scenario['capture_seconds'] + limits['event_seconds'] < limits['stage_seconds'], 'coverage must fit stage')
    return p


def nodes(xml, package):
    tree = r.hierarchy(xml)
    r.require(all(n.get('package') == package for n in tree.iter('node')),
              'foreign UI nodes/overlay; no action', 'UI_UNAVAILABLE')
    return tree


def labels(xml, package):
    return [n.get(k, '') for n in nodes(xml, package).iter('node') for k in ('text', 'content-desc')]


def has_label(xml, package, value):
    return any(value in v.splitlines() for v in labels(xml, package))


def scroll_viewport(xml, package):
    tree = nodes(xml, package)
    views = [n for n in tree.iter('node') if n.get('scrollable') == 'true' and
             n.get('enabled') == 'true' and n.get('visible-to-user') != 'false']
    views = [n for n in views if not any(c in views for c in n.iter('node') if c is not n)]
    if has_label(xml, package, FIRMWARE):
        main = [n for n in views if n.get('class') == 'android.widget.ScrollView']
        if len(main) == 1:
            # Flutter's passive success snackbar can expose its own scroll action.
            views = [n for n in views if n is main[0] or not (
                n.get('class') == 'android.view.View' and n.get('clickable') == 'false' and
                not n.get('resource-id') and len(list(n)) == 0 and
                n.get('content-desc', '').startswith('\u6210\u529f:'))]
    anchored = [n for n in views if any('\u53ef\u7528\u8bbe\u5907' in v.splitlines() or
        any(MAC.fullmatch(line.lower()) for line in v.splitlines())
        for child in n.iter('node') for v in (child.get('text', ''), child.get('content-desc', '')))]
    if anchored:
        views = anchored
    elif has_label(xml, package, '\u6b63\u5728\u626b\u63cf\u8bbe\u5907...') or has_label(xml, package, '\u626b\u63cf\u5df2\u505c\u6b62'):
        return None  # A transient snackbar is not the device-list viewport.
    r.require(len(views) <= 1, 'ambiguous native scroll viewport', 'UI_UNAVAILABLE')
    if not views:
        return None
    bounds = re.fullmatch(r'\[(\d+),(\d+)\]\[(\d+),(\d+)\]', views[0].get('bounds', ''))
    r.require(bounds is not None, 'invalid scroll viewport', 'UI_UNAVAILABLE')
    x1, y1, x2, y2 = map(int, bounds.groups())
    r.require(0 <= x1 < x2 <= 20000 and 0 <= y1 < y2 <= 20000 and y2-y1 >= 8,
              'scroll bounds', 'UI_UNAVAILABLE')
    return x1, y1, x2, y2


def scan_page(xml, package):
    tree = nodes(xml, package)
    r.require((has_label(xml, package, '\u6b63\u5728\u626b\u63cf\u8bbe\u5907...') or
               has_label(xml, package, '\u626b\u63cf\u5df2\u505c\u6b62')) and
        not has_label(xml, package, FIRMWARE) and not has_label(xml, package, DEVICE_ID) and
        not any(n.get('resource-id', '').startswith('p35-') for n in tree.iter('node')),
        'not a known pre-capture scan page', 'UNRESOLVED_STATE')
    return scroll_viewport(xml, package)


def scan_fingerprint(xml, package):
    # Row positions matter for scrolling, unlike business-state idle comparison.
    rows = []
    for n in nodes(xml, package).iter('node'):
        text = '\n'.join((n.get('text', ''), n.get('content-desc', '')))
        addresses = re.findall(r'(?i)(?:[0-9a-f]{2}:){5}[0-9a-f]{2}', text)
        if addresses:
            rows.append((sorted(set(x.lower() for x in addresses)), n.get('bounds', '')))
    return hashlib.sha256(json.dumps(rows).encode()).hexdigest()


def prearm_page(xml, package):
    tree = nodes(xml, package)
    r.require(not any(n.get('resource-id', '').startswith('p35-') for n in tree.iter('node')) and
              not has_label(xml, package, DEVICE_ID) and not has_label(xml, package, FIRMWARE),
              'not a known pre-ARM page', 'UNRESOLVED_STATE')
    if has_label(xml, package, '\u6b63\u5728\u626b\u63cf\u8bbe\u5907...') or has_label(xml, package, '\u626b\u63cf\u5df2\u505c\u6b62'):
        scan_page(xml, package)
        return 'scan'
    r.require(has_label(xml, package, '\u8bbe\u5907\u4e2d\u5fc3'), 'unknown pre-ARM page', 'UNRESOLVED_STATE')
    r.find_control(xml, HOME, package)
    return 'home'


def launch_return(response, component):
    text = response.decode('utf-8', 'strict')
    r.require(not re.search(r'Error:|Exception', text) and
        re.findall(r'(?m)^Status: (\S+)\r?$', text) == ['ok'] and
        re.findall(r'(?m)^Activity: (\S+)\r?$', text) == [component] and
        re.findall(r'(?m)^(Complete)\r?$', text) == ['Complete'],
        'APP launch result unavailable/ambiguous', 'ENV_BLOCKED')


def failed_launch_receipts(p, prior, h):
    """Attribute a pre-UI launch using originals, without adding old journal events."""
    pkg = p['app']['id']
    remote = '/sdcard/Android/data/' + pkg + '/files/p35-observations'
    records = []
    pins = []
    base = [str(Path(p['phone']['adb']['path']).resolve()), '-H', '127.0.0.1', '-P',
            str(p['phone']['adb_port']), '-s', p['phone']['serial']]
    for path in sorted((prior / 'usb').glob('adb-[0-9]*.started.json')):
        start = h.read_json(path)
        stem = path.name[:-len('.started.json')]
        closed_path = path.with_name(stem + '.closed.json')
        r.require(closed_path.is_file(), 'original command outcome unavailable', 'UNRESOLVED_STATE')
        closed = h.read_json(closed_path)
        argv = start['argv']
        r.require(argv[:7] == base and closed.get('argv') == argv and
            Path(start['cwd']).resolve() == ROOT and closed.get('cleanup_complete') is True and
            closed.get('reason') == 'completed' and closed.get('stopped_while_running') is False and
            closed.get('exit_code') in (0, 1) and
            closed.get('started_monotonic_ns') == start['monotonic_ns'],
            'original command closure/identity unbound', 'UNRESOLVED_STATE')
        streams = []
        for suffix in ('stdout', 'stderr'):
            file = path.with_name(stem + '.' + suffix)
            r.require(h.record(file) == closed[suffix], 'original command stream changed', 'EVIDENCE_GAP')
            streams.append(file.read_bytes())
            pins.append(h.record(file))
        pins.extend((h.record(path), h.record(closed_path)))
        tail = argv[7:]
        command = shlex.split(tail[1]) if len(tail) == 2 and tail[0] in ('shell', 'exec-out') else tail[1:]
        r.require(closed['exit_code'] == 0 or command == ['pidof', pkg] and not streams[0].strip(),
                  'original command did not succeed', 'UNRESOLVED_STATE')
        records.append((tail[0], command, streams[0], streams[1], start['monotonic_ns'], closed['ended_monotonic_ns']))
    r.require(records and all(a[5] <= b[4] for a, b in zip(records, records[1:])),
              'original commands missing/overlapping', 'UNRESOLVED_STATE')
    launches = [i for i, row in enumerate(records) if row[1][:2] == ['am', 'start']]
    r.require(len(launches) == 1, 'one original launch required', 'UNRESOLVED_STATE')
    index = launches[0]
    command, response = records[index][1:3]
    r.require(command[:4] == ['am', 'start', '-W', '-n'] and len(command) == 5 and
        re.fullmatch(re.escape(pkg) + r'/[A-Za-z0-9_.$]+', command[-1]),
        'original launcher unbound', 'UNRESOLVED_STATE')
    component = command[-1]
    launch_return(response, component)
    r.require(index >= 2 and records[index-2][1] == ['cmd', 'package', 'resolve-activity', '--brief', pkg] and
        records[index-2][2].decode().strip().splitlines()[-1] == component and
        records[index-1][1] == ['pidof', pkg], 'pre-launch process binding missing', 'UNRESOLVED_STATE')
    previous = records[index-1][2].decode().strip()
    after = records[index+1:]
    r.require(len(after) >= 2 and after[0][1] == ['pidof', pkg] and
        all(row[1] in (['pidof', pkg], ['dumpsys', 'window']) for row in after),
        'post-launch actions not query-only', 'UNRESOLVED_STATE')
    pid = after[0][2].decode().strip()
    r.require(pid.isdigit() and (not previous or previous == pid) and
        all(row[2].decode().strip() == pid for row in after if row[1] == ['pidof', pkg]),
        'original process changed/ambiguous', 'UNRESOLVED_STATE')
    probe = 'if [ -d "$1" ]; then echo directory; elif [ ! -e "$1" ]; then echo missing; else echo unknown; fi'
    baseline = {x.name: x for x in (prior / 'previous-captures').glob('*.jsonl')}
    probes = [row[2].strip() for row in records[:index] if row[1] == ['sh', '-c', probe, 'sh', remote]]
    listings = [row[2].decode().splitlines() for row in records[:index] if row[1] == ['ls', '-1', remote]]
    r.require(probes == [b'missing'] and not baseline and not listings or
        probes == [b'directory'] and len(listings) == 1 and len(listings[0]) == len(set(listings[0])) and
        set(listings[0]) == set(baseline), 'original capture baseline unbound', 'UNRESOLVED_STATE')
    for name, file in baseline.items():
        originals = [row[2] for row in records[:index] if row[1] == ['cat', remote + '/' + name]]
        r.require(len(originals) == 1 and originals[0] == file.read_bytes(),
                  'original baseline differs from retrieval receipt', 'EVIDENCE_GAP')
    for kind, cmd, stdout, stderr, _, _ in records[:index-2]:
        safe = cmd in (['-l'], [], ['getprop', 'ro.product.model'], ['pm', 'list', 'packages', pkg],
            ['pm', 'path', pkg], ['dumpsys', 'package', pkg], ['dumpsys', 'activity', 'services', pkg],
            ['sh', '-c', probe, 'sh', remote], ['ls', '-1', remote])
        safe = safe or len(cmd) == 2 and cmd[0] in ('cat', 'sha256sum') and (
            re.fullmatch(re.escape(remote) + r'/[0-9a-f]{32}\.jsonl', cmd[1]) or
            cmd[0] == 'sha256sum' and cmd[1].startswith('/data/app/') and cmd[1].endswith('/base.apk'))
        safe = safe or len(cmd) == 3 and cmd[:2] == ['wc', '-c'] and re.fullmatch(
            re.escape(remote) + r'/[0-9a-f]{32}\.jsonl', cmd[2])
        r.require(safe, 'original pre-launch actions not query-only', 'UNRESOLVED_STATE')
    return dict(pid=pid, owned=not previous, component=component, receipts=pins,
                basis='closed original launch result + pre/post process receipts')


def semantic_control(xml, package, label, *, token=False):
    tree = nodes(xml, package)
    matches = [n for n in tree.iter('node') if any(
        label.lower() in v.lower().splitlines() if token else v == label
        for v in (n.get('text', ''), n.get('content-desc', '')))]
    # Select the smallest semantic node; parent labels can repeat child text.
    matches = [n for n in matches if not any(c in matches for c in n.iter('node') if c is not n)]
    r.require(len(matches) <= 1, 'ambiguous target semantic control', 'UI_UNAVAILABLE')
    r.require(matches, 'target semantic control missing', 'UI_WAIT')
    n = matches[0]
    wanted = {k: n.get(k) for k in ('text', 'content-desc') if n.get(k)}
    return r.find_control(xml, wanted, package)


def idle_phase(s, p):
    r.validate_state(s)
    r.require(s['deviceAddress'].lower() == p['device']['address'], 'wrong target', 'IDENTITY_MISMATCH')
    r.require(s['phase'] == 'idle' and s['protocol'] is None and s['bitmap'] is None and
        s['session'] == s['durable'] == 0 and s['sendOffset'] is None,
        'busy/unknown OTA state; no further UI action', 'DEVICE_BUSY')
    return s


def idle_state(s, p):
    idle_phase(s, p)
    r.require(s['linkConnected'] and s['freshConnection'] and
        s['currentVersionCode'] > 0 and r.digest(s['currentImageSha256']),
        'target disconnected, historical or wrong identity', 'IDENTITY_MISMATCH')
    for field, actual in [('expected_version', s['currentVersionCode']), ('expected_sha256', s['currentImageSha256'])]:
        r.require(p['device'][field] is None or p['device'][field] == actual, 'fresh firmware pin mismatch', 'IDENTITY_MISMATCH')
    return s


def product_failures(states, p):
    """Known idle product defects are verdicts, not permission to abort sealing."""
    checks = [
        ('LINK_NOT_CONNECTED', lambda s: s['linkConnected']),
        ('IDENTITY_NOT_FRESH', lambda s: s['freshConnection']),
        ('IDENTITY_UNAVAILABLE', lambda s: s['currentVersionCode'] > 0 and r.digest(s['currentImageSha256'])),
        ('VERSION_PIN_MISMATCH', lambda s: p['device']['expected_version'] is None or
            s['currentVersionCode'] == p['device']['expected_version']),
        ('IMAGE_PIN_MISMATCH', lambda s: p['device']['expected_sha256'] is None or
            s['currentImageSha256'] == p['device']['expected_sha256']),
    ]
    failures = []
    for code, check in checks:
        bad = [s['seq'] for s in states if not check(s)]
        if bad:
            failures.append(dict(code=code, stage='fresh-identity' if states[0]['seq'] in bad else
                'capture-observe', firstSeq=bad[0], lastSeq=bad[-1], records=len(bad)))
    return failures


def latest_identity(states, after_seq):
    # One reconnect action can emit connector and page-read identities in one batch.
    return next((s for s in reversed(states) if s['seq'] > after_seq and s['event'] == 'identity'), None)


def audit_smoke(raw, capture_id, p, live, identity_seq=None, *, observation_source='logcat', samples=None):
    report = r.audit_capture(raw, capture_id)
    states = r.Decoder().feed(b''.join(raw.splitlines(keepends=True)[1:-1]))
    r.require(states == live, 'live/persisted sequence mismatch', 'EVIDENCE_GAP')
    r.require(observation_source in {'logcat', 'app-file'}, 'unknown observation source', 'EVIDENCE_GAP')
    if observation_source == 'app-file':
        r.require(type(identity_seq) is int and identity_seq > 0, 'file observation needs query-bound identity sequence', 'EVIDENCE_GAP')
        r.require(samples and samples[-1]['lastConsumedSeq'] == len(states),
                  'missing execution-time file observations', 'EVIDENCE_GAP')
        consumed, previous_time = 0, -1
        for sample in samples:
            size = sample['bytes']
            r.require(0 <= size <= len(raw) and sample['sha256'] == hashlib.sha256(raw[:size]).hexdigest() and
                sample['previousConsumedSeq'] == consumed and sample['hostMonoNs'] >= previous_time,
                'file sample/final prefix mismatch', 'EVIDENCE_GAP')
            cursor = FileCursor(capture_id)
            cursor.feed(raw[:size])
            consumed = cursor.decoder.previous['seq'] if cursor.decoder.previous else 0
            r.require(consumed == sample['lastConsumedSeq'], 'invented file observation sequence', 'EVIDENCE_GAP')
            previous_time = sample['hostMonoNs']
        r.require(any(x['stage'] == 'capture-start' and x['lastConsumedSeq'] > 0 for x in samples) and
            any(x['stage'] == 'fresh-identity' and x['lastConsumedSeq'] >= identity_seq for x in samples) and
            any(x['stage'] == 'capture-observe' and x['lastConsumedSeq'] > identity_seq for x in samples),
            'missing staged observations; final retrieval is not live evidence', 'EVIDENCE_GAP')
    for s in states:
        idle_phase(s, p)
    identity = (states[0]['currentVersionCode'], states[0]['currentImageSha256'])
    r.require(all((s['currentVersionCode'], s['currentImageSha256']) == identity for s in states),
              'firmware identity changed during no-OTA capture', 'IDENTITY_MISMATCH')
    identities = [s for s in states if s['event'] == 'identity' and
                  (identity_seq is None or s['seq'] == identity_seq)]
    r.require(identities, 'no post-arm GET_INFO identity event', 'EVIDENCE_GAP')
    observed = [s for s in states if s['seq'] >= identities[0]['seq']]
    failures = product_failures(observed, p)
    heartbeats = [s for s in states if s['event'] == 'heartbeat' and s['seq'] > identities[0]['seq']]
    r.require(len(heartbeats) >= p['scenario']['min_heartbeats'] and
        states[-1]['monoUs'] - identities[0]['monoUs'] >= p['scenario']['capture_seconds'] * 1_000_000,
        'insufficient producer heartbeat/time coverage', 'EVIDENCE_GAP')
    r.require(all(0 <= b['monoUs'] - a['monoUs'] <= p['limits']['event_seconds'] * 1_000_000
        for a, b in zip(states, states[1:])), 'producer heartbeat gap', 'EVIDENCE_GAP')
    return dict(records=report['records'], sha256=report['sha256'], integrity=report['integrity'],
        heartbeats=len(heartbeats), identityEvents=len(identities), firmwareVersion=identity[0],
        firmwareSha256=identity[1], targetBound=True, identityBound=not failures,
        freshIdentityVerified=not failures, testOutcome='FAIL' if failures else 'PASS',
        failures=failures, bootstrapRecords=identities[0]['seq']-1, observationSource=observation_source,
        fileSamples=samples or [])


class FileCursor:
    """Append-only App bytes; only complete lines are consumed, exactly once."""
    def __init__(self, capture_id):
        self.capture_id, self.raw, self.consumed = capture_id, b'', 0
        self.decoder = r.Decoder()

    def feed(self, raw):
        r.require(len(raw) <= MAX_CAPTURE and raw.startswith(self.raw),
                  'App file truncated or previously sampled prefix changed', 'EVIDENCE_GAP')
        end = raw.rfind(b'\n') + 1
        r.require(len(raw) - end <= r.MAX_LINE, 'oversize incomplete App line', 'EVIDENCE_GAP')
        lines = raw[self.consumed:end].splitlines(keepends=True)
        states = []
        previous_seq = self.decoder.previous['seq'] if self.decoder.previous else 0
        for line in lines:
            r.require(line.startswith((b'OTA_P35_CAPTURE ', r.PREFIX.encode())),
                      'unexpected complete App file line', 'EVIDENCE_GAP')
            r.require(self.decoder.closed is None, 'App bytes after footer', 'EVIDENCE_GAP')
            if line.startswith(r.PREFIX.encode()):
                r.require(self.decoder.opened is not None, 'App state before header', 'EVIDENCE_GAP')
            else:
                receipt = r.strict_json(line[len(b'OTA_P35_CAPTURE '):])
                r.require(receipt.get('kind') in {'open', 'close'}, 'unknown complete App receipt', 'EVIDENCE_GAP')
            states.extend(self.decoder.feed(line))
            r.require(self.decoder.opened == dict(schema=1, kind='open', captureId=self.capture_id) and
                type(self.decoder.opened['schema']) is int,
                'App file/header capture identity mismatch', 'EVIDENCE_GAP')
        r.require(not states or states[0]['seq'] == previous_seq + 1 and
            all(x['captureId'] == self.capture_id for x in states), 'file capture identity', 'EVIDENCE_GAP')
        self.raw, self.consumed = raw, end
        return states


def sealed_file(raw, capture_id):
    """Structural seal is separate from health/test PASS, for safe recovery."""
    cursor = FileCursor(capture_id)
    states = cursor.feed(raw)
    footer = cursor.decoder.closed
    r.require(raw.endswith(b'\n') and footer is not None and states and states[0]['seq'] == 1,
              'unsealed/incomplete App file', 'EVIDENCE_GAP')
    body = b''.join(raw.splitlines(keepends=True)[1:-1])
    r.require(set(footer) == {'schema', 'kind', 'captureId', 'records', 'sha256', 'healthy', 'lost', 'error'} and
        type(footer['schema']) is int and footer['schema'] == 1 and footer['kind'] == 'close' and
        footer['captureId'] == capture_id and type(footer['records']) is int and footer['records'] == len(states) and
        footer['sha256'] == hashlib.sha256(body).hexdigest() and type(footer['healthy']) is bool and
        r.uint(footer['lost']) and (footer['error'] is None or isinstance(footer['error'], str) and footer['error']) and
        (not footer['healthy'] or footer['lost'] == 0 and footer['error'] is None),
        'App seal count/hash/domain mismatch', 'EVIDENCE_GAP')
    return dict(integrity='VERIFIED', healthy=footer['healthy'] and footer['lost'] == 0 and footer['error'] is None,
                footer=footer, final=states[-1], sha256=hashlib.sha256(raw).hexdigest(), records=len(states))


def sealed_unready_ui(tree, pkg):
    """The installed page's hint excludes upgrading; identity action excludes busy query."""
    controls = nodes(tree, pkg)
    r.require(has_label(tree, pkg, CLOSED_RECORDER) and has_label(tree, pkg, UNREADY_HINT) and
        not any(n.get('resource-id') in {'p35-stop', 'p35-start', 'p35-download', 'p35-resume'}
                for n in controls.iter('node')), 'unknown/busy closed-recorder UI', 'UNRESOLVED_STATE')
    r.find_control(tree, {'resource-id': 'p35-identity'}, pkg)


def capture_prefix(raw, capture_id, p):
    r.require(0 < len(raw) <= MAX_CAPTURE, 'capture prefix bounds', 'EVIDENCE_GAP')
    decoder = r.Decoder()
    states = decoder.feed(raw)
    r.require(decoder.opened is not None and type(decoder.opened.get('schema')) is int and
        decoder.opened == dict(schema=1, kind='open', captureId=capture_id) and
        states and states[0]['seq'] == 1 and all(s['captureId'] == capture_id for s in states),
        'unowned/incomplete capture prefix', 'EVIDENCE_GAP')
    for state in states:
        idle_phase(state, p)
    if decoder.closed is not None:
        r.audit_capture(raw, capture_id)
    return decoder


class Smoke:
    def __init__(self, p, out, h):
        sys.path.insert(0, str(ROOT / 'Tools/ota/p34-acceptance'))
        from live_phone import Phone
        self.p, self.out, self.h = p, out, h
        self.total = time.monotonic() + p['limits']['total_seconds']
        self.stage, self.stage_deadline = 'preflight', self.total
        self.phone = Phone(dict(app_id=p['app']['id'], phone_serial=p['phone']['serial'],
            phone_model=p['phone']['model'], adb_port=p['phone']['adb_port'],
            tools=dict(adb=p['phone']['adb']), adb_key=p['phone']['adb_key'], apk=p['app']),
            out / 'usb', p['limits']['total_seconds'] + p['limits']['cleanup_seconds'] + 15)
        self.logcat = None
        self.decoder, self.live = r.Decoder(), []
        self.file_cursor = None
        self.observation_source, self.file_samples = 'app-file', []
        self.arm_baseline_confirmed = False
        self.diagnostic_pending, self.diagnostic_states = b'', {}
        self.diagnostic_header = self.diagnostic_footer = None
        self.diagnostic_error = None
        self.offset, self.pid, self.journal_seq = 0, None, 0
        self.capture_id = None
        self.arm_attempted = self.stop_attempted = self.mutation_unknown = False
        self.arm_action_count = 0
        self.capture_resolved = False
        self.capture_seal = None
        self.capture_recovery_states = None
        self.stop_seal_recovered = False
        self.capture_state = 'NOT_ARMED'
        self.stream_failed = False
        self.original_verified = False
        self.identity_seq = None
        self.previous_captures = {}
        self.restart_attempted = self.restart_confirmed = self.owned_stop_attempted = False
        self.owned_app_pid = None
        self.owned_launch_confirmed = False
        self.owned_app_closed = False
        self.prearm_navigation = False

    def enter(self, stage):
        self.stage = stage
        self.stage_deadline = min(self.total, time.monotonic() + self.p['limits']['stage_seconds'])
        self.phone.operation_deadline = self.stage_deadline
        self.record('stage', stage=stage)
        print('P35_STAGE ' + stage, flush=True)

    def record(self, event, **fields):
        self.journal_seq += 1
        self.h.save(self.out / 'journal' / ('%05d.json' % self.journal_seq),
                    dict(event=event, hostMonoNs=time.monotonic_ns(), **fields))

    def cmd(self, args, *, success_codes=(0,)):
        r.require(time.monotonic() < self.stage_deadline, 'stage deadline expired', 'TIMEOUT')
        return self.phone.cmd(args, seconds=min(self.p['limits']['command_seconds'],
            self.stage_deadline - time.monotonic()), success_codes=success_codes)

    def idle_services(self):
        raw = self.cmd(['shell', 'dumpsys', 'activity', 'services', self.p['app']['id']])
        r.require(b'DeviceOtaService' not in raw, 'active/unknown OTA service', 'DEVICE_BUSY')

    def ui(self):
        if self.pid is not None:
            r.require(self.cmd(['shell', 'pidof', self.p['app']['id']]).strip().decode() == self.pid,
                      'APP process changed; preserve recording', 'IDENTITY_MISMATCH')
        focus = self.cmd(['shell', 'dumpsys', 'window'])
        r.require(r.foreground_ok(focus, self.p['app']['id']),
                  'test APP not foreground/unlocked; no hierarchy collected', 'UI_UNAVAILABLE')
        raw = self.cmd(['exec-out', 'uiautomator', 'dump', '--compressed', '/dev/tty'])
        nodes(raw, self.p['app']['id'])
        return raw

    def wait(self, check):
        while time.monotonic() < self.stage_deadline:
            value = check()
            if value:
                return value
            time.sleep(min(.2, max(0, self.stage_deadline - time.monotonic())))
        raise r.Stop('TIMEOUT', 'stage progress deadline; no action replay')

    def control(self, wanted=None, *, label=None, token=False):
        scrolls = 0
        previous = None
        def ready():
            nonlocal scrolls, previous
            xml = self.ui()
            try:
                return r.find_control(xml, wanted, self.p['app']['id']) if wanted else semantic_control(
                    xml, self.p['app']['id'], label, token=token)
            except r.Stop as error:
                if error.code == 'UI_WAIT' or error.code == 'UI_UNAVAILABLE' and (
                    'control missing' in str(error) or 'disabled/hidden' in str(error)):
                    if label and scrolls < 4:
                        if previous is not None and r.idle_equivalent(previous, xml):
                            return None
                        if scroll_viewport(xml, self.p['app']['id']) is not None:
                            previous, scrolls = xml, scrolls + 1
                            self.scroll(xml, 'down', scrolls)
                            self.mutation_unknown = False
                    return None
                raise
        return self.wait(ready)

    def scroll(self, tree, direction, attempt):
        viewport = scroll_viewport(tree, self.p['app']['id'])
        r.require(viewport is not None and direction in {'down', 'up'},
                  'native scroll route unavailable', 'UI_UNAVAILABLE')
        self.idle_services()
        x1, y1, x2, y2 = viewport
        near, far = y1+(y2-y1)//4, y1+3*(y2-y1)//4
        start, end = (far, near) if direction == 'down' else (near, far)
        self.record('scroll-intent', attempt=attempt, direction=direction, viewport=viewport)
        self.mutation_unknown = True
        self.cmd(['shell', 'input', 'swipe', str((x1+x2)//2), str(start), str((x1+x2)//2), str(end), '250'])
        self.record('scroll-returned', attempt=attempt, direction=direction)

    def find_target(self):
        pkg, address = self.p['app']['id'], self.p['device']['address']
        self.enter('discover-target')
        direction, attempts, previous, stable = 'down', 0, None, 0
        while time.monotonic() < self.stage_deadline:
            try:
                tree = self.ui()
            except (r.Stop, RuntimeError) as error:
                if time.monotonic() >= self.stage_deadline:
                    raise r.Stop('TARGET_SEARCH_INCOMPLETE',
                                 'target search time bound; visible UI is not the full scan result') from error
                raise
            viewport = scan_page(tree, pkg)
            self.prearm_navigation = True
            self.mutation_unknown = False  # The preceding navigation/scroll reached this known page.
            values = labels(tree, pkg)
            wanted = address if any(address in v.lower().splitlines() for v in values) else None
            name = self.p['device']['display_name']
            if wanted is None and name:
                matching = [v for v in values if name in v.splitlines()]
                # A configured name cannot override a different explicit MAC.
                if matching and not any(re.search(r'(?i)(?:[0-9a-f]{2}:){5}[0-9a-f]{2}', v) for v in matching):
                    wanted = name
            if wanted is not None:
                try:
                    semantic_control(tree, pkg, wanted, token=True)
                except r.Stop as error:
                    if error.code != 'UI_WAIT' and not (error.code == 'UI_UNAVAILABLE' and
                            ('hidden' in str(error) or 'bounds' in str(error))):
                        raise
                else:
                    self.record('target-found', source='native-list', scrolls=attempts, matchedBy='mac' if wanted == address else 'name')
                    return wanted
            fingerprint = scan_fingerprint(tree, pkg)
            self.record('target-search-observation', source='native-list', fingerprint=fingerprint,
                        scrolls=attempts, direction=direction, targetVisible=False,
                        fullScanDataAvailable=False)
            stable = stable+1 if fingerprint == previous else 0
            previous = fingerprint
            if attempts >= 24 or viewport is None:
                break
            if stable >= 2 or attempts == 12:
                if direction == 'up':
                    break
                direction, stable, previous = 'up', 0, None
            attempts += 1
            self.scroll(tree, direction, attempts)
        raise r.Stop('TARGET_SEARCH_INCOMPLETE',
                     'bounded visible-list traversal exhausted; target absence/power state is not established')

    def tap(self, wanted=None, *, label=None, token=False):
        self.idle_services()
        point = self.control(wanted, label=label, token=token)
        # No uncertain tap is repeated. Coordinates belong to this native node.
        self.record('tap-intent', control=wanted or 'target-bound-semantic', point=point)
        self.mutation_unknown = True
        self.cmd(['shell', 'input', 'tap', *map(str, point)])
        self.record('tap-returned')

    def original(self, capture_id, destination):
        r.require(re.fullmatch(r'[0-9a-f]{32}', capture_id), 'invalid capture path', 'EVIDENCE_GAP')
        remote = '/sdcard/Android/data/' + self.p['app']['id'] + '/files/p35-observations/' + capture_id + '.jsonl'
        size = self.cmd(['shell', 'wc', '-c', remote]).split()
        r.require(size and size[0].isdigit() and 0 < int(size[0]) <= MAX_CAPTURE, 'original size bound', 'EVIDENCE_GAP')
        raw = self.cmd(['exec-out', 'cat', remote])
        self.h.raw(destination, raw)  # Preserve even a partial or unhealthy original.
        digest = self.cmd(['shell', 'sha256sum', remote]).split()
        r.require(digest and len(raw) == int(size[0]) and hashlib.sha256(raw).hexdigest().encode() == digest[0],
                  'original changed during retrieval', 'EVIDENCE_GAP')
        if capture_id == self.capture_id:
            self.original_verified = True
        return raw

    def prefix(self, capture_id, destination):
        r.require(re.fullmatch(r'[0-9a-f]{32}', capture_id), 'invalid capture path', 'EVIDENCE_GAP')
        remote = '/sdcard/Android/data/' + self.p['app']['id'] + '/files/p35-observations/' + capture_id + '.jsonl'
        size = self.cmd(['shell', 'wc', '-c', remote]).split()
        r.require(size and size[0].isdigit() and 0 <= int(size[0]) <= MAX_CAPTURE, 'prefix size bound', 'EVIDENCE_GAP')
        raw = self.cmd(['exec-out', 'head', '-c', size[0].decode(), remote])
        self.h.raw(destination, raw)
        r.require(len(raw) == int(size[0]), 'prefix read truncated', 'EVIDENCE_GAP')
        return raw

    def capture_names(self):
        remote = '/sdcard/Android/data/' + self.p['app']['id'] + '/files/p35-observations'
        probe = 'if [ -d "$1" ]; then echo directory; elif [ ! -e "$1" ]; then echo missing; else echo unknown; fi'
        present = self.cmd(['shell', 'sh', '-c', probe, 'sh', remote]).strip()
        r.require(present in {b'directory', b'missing'}, 'unknown old capture directory', 'UNRESOLVED_STATE')
        if present == b'missing':
            r.require(not self.previous_captures, 'previous capture directory disappeared', 'UNRESOLVED_STATE')
            return set()
        names = self.cmd(['shell', 'ls', '-1', remote]).decode().splitlines()
        r.require(len(names) <= 32 and len(names) == len(set(names)) and
                  all(re.fullmatch(r'[0-9a-f]{32}\.jsonl', n) for n in names),
                  'unknown/full previous capture store', 'UNRESOLVED_STATE')
        return {name[:-6] for name in names}

    def old_captures(self):
        names = self.capture_names()
        r.require(len(names) < 32, 'previous capture store full', 'UNRESOLVED_STATE')
        for name in names:
            cid = name
            raw = self.original(cid, self.out / 'previous-captures' / (cid + '.jsonl'))
            try:
                report = sealed_file(raw, cid)
            except r.Stop as error:
                raise r.Stop('UNRESOLVED_STATE', 'previous capture unsealed/corrupt; original preserved') from error
            if report['final']['phase'] == 'readyToInstall':
                # A sealed download is not a transfer. A later idle home instance
                # is not the old download owner merely because a PID exists.
                states = FileCursor(cid).feed(raw)
                r.require(report['healthy'] and report['final']['packageVerified'] and
                    all(row['phase'] in {'idle', 'checkingUpdate', 'downloading', 'verifyingDownload', 'readyToInstall'} and
                        row['protocol'] is None and row['bitmap'] is None and row['session'] == row['durable'] == 0 and
                        row['sendOffset'] is None and row['event'] not in {'beginAck', 'data', 'endAck'}
                        for row in states), 'old ready capture has unproved transfer history', 'UNRESOLVED_STATE')
                pid = self.cmd(['shell', 'pidof', self.p['app']['id']], success_codes=(0, 1)).strip().decode()
                if pid:
                    r.require(pid.isdigit(), 'ambiguous existing APP process', 'UNRESOLVED_STATE')
                    previous_pid = self.pid
                    self.pid = pid
                    try:
                        self.idle_services()
                        self.foreground_existing(pid)
                        tree = self.ui()
                        r.require(prearm_page(tree, self.p['app']['id']) == 'home' and
                                  r.idle_equivalent(tree, self.ui()),
                                  'existing APP is not stable pre-ARM home', 'UNRESOLVED_STATE')
                        self.idle_services()
                        r.require(self.cmd(['shell', 'pidof', self.p['app']['id']]).strip().decode() == pid,
                                  'existing APP changed during admission', 'UNRESOLVED_STATE')
                        self.record('old-ready-idle-home', captureId=cid, pid=pid, sha256=report['sha256'])
                    finally:
                        self.pid = previous_pid
            else:
                r.require(report['final']['phase'] in {'idle', 'completed', 'failed', 'cancelled'},
                          'old capture has unresolved OTA phase', 'UNRESOLVED_STATE')
            self.previous_captures[cid] = dict(bytes=len(raw), sha256=report['sha256'], final=report['final'], healthy=report['healthy'])

    def start_phone(self):
        self.enter('preflight')
        r.require(not self.h.listening(self.phone.port), 'private ADB port already owned', 'ENV_BLOCKED')
        self.phone.server = self.h.Process(self.phone.out, 'adb-server',
            [self.phone.base[0], '-P', str(self.phone.port), 'nodaemon', 'server'], self.phone.env)
        self.wait(lambda: self.phone.server.alive() and self.h.listening(self.phone.port))
        devices = self.cmd(['devices', '-l']).decode(errors='replace')
        r.require(re.search(r'(?m)^' + re.escape(self.phone.serial) + r'\s+device\b', devices),
                  'target USB missing/offline/unauthorized; prepare phone then start a new run', 'ENV_BLOCKED')
        r.require(self.cmd(['get-serialno']).strip().decode() == self.phone.serial and
            self.cmd(['shell', 'getprop', 'ro.product.model']).strip().decode() == self.p['phone']['model'],
            'wrong phone identity', 'IDENTITY_MISMATCH')
        self.phone.installed()
        text = self.cmd(['shell', 'dumpsys', 'package', self.p['app']['id']]).decode()
        codes = re.findall(r'\bversionCode=(\d+)\b', text)
        r.require(codes == [str(self.p['app']['version_code'])] and 'DEBUGGABLE' not in text,
                  'test APP version/Release mismatch', 'IDENTITY_MISMATCH')
        self.idle_services()

    def start(self):
        self.start_phone()
        self.old_captures()
        self.launch()

    def launch(self, *, required_pid=None, forbidden_pid=None):
        self.enter('launch')
        component = self.cmd(['shell', 'cmd', 'package', 'resolve-activity', '--brief', self.p['app']['id']]).decode().strip().splitlines()
        r.require(component and re.fullmatch(re.escape(self.p['app']['id']) + r'/[A-Za-z0-9_.$]+', component[-1]),
                  'test APP launcher unavailable', 'ENV_BLOCKED')
        previous_pid = self.cmd(['shell', 'pidof', self.p['app']['id']], success_codes=(0, 1)).strip().decode()
        r.require(not previous_pid or previous_pid.isdigit(), 'ambiguous pre-launch APP process', 'ENV_BLOCKED')
        r.require(required_pid is None or previous_pid == required_pid,
                  'old APP process changed before launch', 'IDENTITY_MISMATCH')
        r.require(forbidden_pid is None or not previous_pid,
                  'APP process appeared after stop; no launch', 'UNRESOLVED_STATE')
        self.record('launch-intent', component=component[-1], previousPid=previous_pid)
        self.mutation_unknown = True
        response = self.cmd(['shell', 'am', 'start', '-W', '-n', component[-1]])
        launch_return(response, component[-1])
        self.pid = self.cmd(['shell', 'pidof', self.p['app']['id']]).strip().decode()
        r.require(self.pid.isdigit(), 'one APP process required', 'ENV_BLOCKED')
        r.require(required_pid is None or self.pid == required_pid,
                  'old APP process changed; no hierarchy or capture replay', 'IDENTITY_MISMATCH')
        r.require(forbidden_pid is None or self.pid != forbidden_pid,
                  'old APP PID survived restart; no action replay', 'UNRESOLVED_STATE')
        r.require(not previous_pid or self.pid == previous_pid,
                  'existing APP process changed during launch', 'IDENTITY_MISMATCH')
        if not previous_pid:
            self.owned_app_pid = self.pid
        self.record('launch-returned', pid=self.pid, previousPid=previous_pid, component=component[-1],
                    responseSha256=hashlib.sha256(response).hexdigest())
        self.ui()
        self.mutation_unknown = False
        self.record('launch-confirmed', pid=self.pid)
        if self.owned_app_pid == self.pid:
            self.owned_launch_confirmed = True

    def foreground_existing(self, pid):
        self.pid = str(pid)
        r.require(self.cmd(['shell', 'pidof', self.p['app']['id']]).strip().decode() == self.pid,
                  'old APP process changed', 'IDENTITY_MISMATCH')
        window = self.cmd(['shell', 'dumpsys', 'window'])
        if not r.foreground_ok(window, self.p['app']['id']):
            self.launch(required_pid=self.pid)
        else:
            self.ui()

    def navigate(self):
        pkg = self.p['app']['id']
        self.enter('navigate-connect')
        xml = self.ui()
        if has_label(xml, pkg, FIRMWARE):
            # Never restart the App just to obtain a fresh identity. The native
            # reconnect/GET_INFO action after arm supplies the fresh oracle.
            return
        if any(n.get('content-desc') == HOME['content-desc'] and n.get('class') == HOME['class']
               for n in nodes(xml, pkg).iter('node')):
            self.tap(HOME)
            self.wait(lambda: has_label(self.ui(), pkg, '\u4eea\u8868\u76d8'))
            self.mutation_unknown = False
        xml = self.ui()
        address = self.p['device']['address']
        if not has_label(xml, pkg, DEVICE_ID):
            if not has_label(xml, pkg, '\u6b63\u5728\u626b\u63cf\u8bbe\u5907...') and not has_label(xml, pkg, '\u626b\u63cf\u5df2\u505c\u6b62'):
                self.tap(DEVICES)
            label = self.find_target()
            self.enter('navigate-connect')
            self.tap(label=label, token=True)
            self.wait(lambda: has_label(self.ui(), pkg, DEVICE_ID))
            self.mutation_unknown = False
            self.prearm_navigation = False
        xml = self.ui()
        r.require(any(address in s.lower().splitlines() for s in labels(xml, pkg)),
                  'device detail does not bind target address; no connection', 'IDENTITY_MISMATCH')
        if not has_label(xml, pkg, CONNECTED):
            self.tap(CONNECT)
            self.wait(lambda: has_label(self.ui(), pkg, CONNECTED))
            self.mutation_unknown = False
        self.tap(label=OPEN_FIRMWARE, token=True)
        self.wait(lambda: has_label(self.ui(), pkg, FIRMWARE))
        self.mutation_unknown = False

    def idle_recorder_ui(self):
        self.idle_services()
        tree = self.ui()
        pkg = self.p['app']['id']
        r.require(has_label(tree, pkg, FIRMWARE) and
            not any(n.get('resource-id') == 'p35-stop' for n in nodes(tree, pkg).iter('node')),
            'APP not at idle firmware page or recorder active; no process stop', 'UNRESOLVED_STATE')
        try:
            r.find_control(tree, {'resource-id': 'p35-check'}, pkg)
        except r.Stop as error:
            r.require(error.code == 'UI_UNAVAILABLE' and
                self.capture_resolved and self.capture_seal is not None,
                'idle state not proved by check control or owned seal', 'UNRESOLVED_STATE')
            self.check_cleanup_state(self.capture_seal['final'])
            if self.capture_seal['final']['phase'] == 'readyToInstall':
                r.require('control missing' in str(error) or 'disabled' in str(error),
                          'ambiguous pre-transfer cleanup UI', 'UNRESOLVED_STATE')
                r.find_control(tree, QUERY, pkg)
            else:
                r.require('disabled' in str(error), 'missing idle check control', 'UNRESOLVED_STATE')
                sealed_unready_ui(tree, pkg)
        r.require(r.idle_equivalent(tree, self.ui()), 'APP business state changed; no process stop', 'UNRESOLVED_STATE')
        return tree

    def idle_prearm_ui(self):
        r.require(self.prearm_navigation and not self.arm_attempted and not self.restart_attempted,
                  'not an evidenced pre-ARM navigation', 'UNRESOLVED_STATE')
        self.idle_services()
        before = prearm_page(self.ui(), self.p['app']['id'])
        r.require(prearm_page(self.ui(), self.p['app']['id']) == before,
                  'pre-ARM page changed during cleanup', 'UNRESOLVED_STATE')
        r.require(self.capture_names() == set(self.previous_captures),
                  'capture store changed during pre-ARM navigation', 'UNRESOLVED_STATE')
        for cid, old in self.previous_captures.items():
            raw = self.original(cid, self.out / 'prearm-cleanup-captures' / (cid+'.jsonl'))
            r.require(hashlib.sha256(raw).hexdigest() == old['sha256'],
                      'original changed during pre-ARM cleanup', 'UNRESOLVED_STATE')
        self.mutation_unknown = False
        self.capture_resolved = True

    def stop_app_process(self, pid, action):
        # Only the pinned test package and checked current PID. Never replay this mutation.
        r.require(self.cmd(['shell', 'pidof', self.p['app']['id']]).strip().decode() == pid,
                  'test APP owner changed before process stop', 'UNRESOLVED_STATE')
        self.record(action + '-intent', pid=pid)
        self.mutation_unknown = True
        self.cmd(['shell', 'am', 'force-stop', self.p['app']['id']])
        self.wait(lambda: self.cmd(['shell', 'pidof', self.p['app']['id']], success_codes=(0, 1)).strip() == b'')
        self.record(action + '-confirmed', pid=pid)
        self.mutation_unknown = False

    def prepare_recorder(self):
        if not self.p.get('lifecycle', {}).get('restart_closed_recorder', False):
            return
        self.enter('prepare-recorder')
        tree = self.ui()
        pkg = self.p['app']['id']
        arms = [n for n in nodes(tree, pkg).iter('node') if n.get('resource-id') == 'p35-arm']
        if len(arms) != 1 or not any(c.get('content-desc') == CLOSED_RECORDER for c in arms[0].iter('node')):
            return  # Fresh recorder uses normal bounded arm admission; unknown states are not restarted.
        r.require(not self.restart_attempted and self.previous_captures,
                  'closed recorder without verified old originals', 'UNRESOLVED_STATE')
        r.require(any(item['final']['deviceAddress'].lower() == self.p['device']['address'] and
            item['final']['phase'] == 'idle' and item['final']['protocol'] is None and
            item['final']['session'] == item['final']['durable'] == 0 for item in self.previous_captures.values()),
            'no sealed idle target capture for lifecycle preparation', 'UNRESOLVED_STATE')
        self.idle_recorder_ui()
        old_pid = self.pid
        self.restart_attempted = True
        self.stop_app_process(old_pid, 'restart-stop')
        self.pid = None
        self.launch(forbidden_pid=old_pid)
        self.navigate()
        self.enter('verify-restarted-originals')
        remote = '/sdcard/Android/data/' + pkg + '/files/p35-observations'
        names = self.cmd(['shell', 'ls', '-1', remote]).decode().splitlines()
        r.require(set(names) == {cid + '.jsonl' for cid in self.previous_captures} and
            len(names) == len(self.previous_captures), 'old capture store changed across restart', 'UNRESOLVED_STATE')
        for cid, item in self.previous_captures.items():
            raw = self.original(cid, self.out / 'after-restart-captures' / (cid + '.jsonl'))
            r.require(len(raw) == item['bytes'] and hashlib.sha256(raw).hexdigest() == item['sha256'],
                      'old original changed across test APP restart', 'UNRESOLVED_STATE')
        self.restart_confirmed = True
        self.record('restart-complete', oldPid=old_pid, newPid=self.pid, preservedCaptures=len(names))

    def check_cleanup_state(self, state):
        idle_phase(state, self.p)

    def pump(self):
        try:
            return self._pump()
        except r.Stop as error:
            self.stream_failed = self.stream_failed or error.code in {
                'EVIDENCE_GAP', 'COLLECTOR_FAILED', 'IDENTITY_MISMATCH', 'DEVICE_BUSY'}
            raise
        except BaseException:
            self.stream_failed = True
            raise

    def diagnostic_pump(self):
        if not self.logcat:
            return
        if not self.logcat.alive():
            self.diagnostic_error = 'logcat stopped; App file remains the observation source'
        path = self.logcat.paths['stdout']
        size = path.stat().st_size
        r.require(self.offset <= size <= 256 * 1024 * 1024 and size - self.offset <= 1024 * 1024,
                  'collector loss/overrun', 'EVIDENCE_GAP')
        with path.open('rb') as stream:
            stream.seek(self.offset)
            data = stream.read()
        self.offset += len(data)
        self.diagnostic_pending += data
        lines = self.diagnostic_pending.split(b'\n')
        self.diagnostic_pending = lines.pop()
        r.require(len(self.diagnostic_pending) <= r.MAX_LINE, 'oversize diagnostic tail', 'EVIDENCE_GAP')
        for line in lines:
            for marker in (b'OTA_P35_CAPTURE ', r.PREFIX.encode(), b'OTA_P35_ERROR '):
                start = line.find(marker)
                if start < 0:
                    continue
                value = r.strict_json(line[start + len(marker):])
                if marker == r.PREFIX.encode():
                    r.validate_state(value)
                    old = self.diagnostic_states.get(value['seq'])
                    r.require(old is None or old == value, 'conflicting diagnostic sequence', 'EVIDENCE_GAP')
                    self.diagnostic_states[value['seq']] = value
                elif marker == b'OTA_P35_ERROR ':
                    self.diagnostic_error = value
                elif value.get('kind') == 'open':
                    r.require(self.diagnostic_header is None, 'replayed diagnostic header', 'EVIDENCE_GAP')
                    self.diagnostic_header = value
                elif value.get('kind') == 'close':
                    r.require(self.diagnostic_footer is None, 'replayed diagnostic footer', 'EVIDENCE_GAP')
                    self.diagnostic_footer = value

    def _pump(self):
        r.require(self.phone.server and self.phone.server.alive(), 'ADB stopped', 'COLLECTOR_FAILED')
        r.require(self.cmd(['shell', 'pidof', self.p['app']['id']], success_codes=(0, 1)).strip().decode() == self.pid,
                  'APP process changed during file observation', 'IDENTITY_MISMATCH')
        names = self.capture_names()
        r.require(set(self.previous_captures) <= names, 'old capture removed during observation', 'EVIDENCE_GAP')
        added = names - set(self.previous_captures)
        r.require(len(added) <= 1, 'multiple new capture files; ownership ambiguous', 'UNRESOLVED_STATE')
        self.diagnostic_pump()
        if not added:
            r.require(self.capture_id is None, 'owned capture disappeared', 'EVIDENCE_GAP')
            return []
        cid = next(iter(added))
        r.require(self.arm_attempted and self.arm_baseline_confirmed and
                  (self.capture_id is None or self.capture_id == cid), 'unbound file observation', 'UNRESOLVED_STATE')
        if self.file_cursor is None:
            self.file_cursor = FileCursor(cid)
            self.decoder = self.file_cursor.decoder
        destination = self.out / 'observations' / ('%05d.jsonl' % (len(self.file_samples) + 1))
        raw = self.prefix(cid, destination)
        before = self.live[-1]['seq'] if self.live else 0
        states = self.file_cursor.feed(raw)
        if self.decoder.opened:
            self.capture_id = cid
            self.capture_state = 'HEADER_ONLY'
        for s in states:
            idle_phase(s, self.p)
            r.require(self.capture_id == s['captureId'] and (self.live or s['seq'] == 1),
                      'unowned/replayed recording', 'EVIDENCE_GAP')
            if self.live:
                r.require((s['currentVersionCode'], s['currentImageSha256']) == (
                    self.live[0]['currentVersionCode'], self.live[0]['currentImageSha256']),
                    'firmware changed during smoke', 'IDENTITY_MISMATCH')
            self.live.append(s)
        if self.live:
            self.capture_state = 'ACTIVE'
        sample = dict(**self.h.record(destination), stage=self.stage, hostMonoNs=time.monotonic_ns(),
                      previousConsumedSeq=before, lastConsumedSeq=self.live[-1]['seq'] if self.live else 0)
        self.file_samples.append(sample)
        self.record('file-observed', sample=sample)
        r.require(self.cmd(['shell', 'pidof', self.p['app']['id']], success_codes=(0, 1)).strip().decode() == self.pid,
                  'APP changed during file read', 'IDENTITY_MISMATCH')
        self.compare_diagnostics()
        if self.decoder.closed:
            sealed_file(raw, cid)
            self.capture_state = 'SEALED'
        return states

    def compare_diagnostics(self):
        if self.diagnostic_header and self.decoder.opened:
            r.require(self.diagnostic_header == self.decoder.opened, 'logcat/file header conflict', 'EVIDENCE_GAP')
        if self.diagnostic_footer and self.decoder.closed:
            r.require(self.diagnostic_footer == self.decoder.closed, 'logcat/file footer conflict', 'EVIDENCE_GAP')
        for state in self.live:
            if state['seq'] in self.diagnostic_states:
                r.require(self.diagnostic_states[state['seq']] == state, 'logcat/file state conflict', 'EVIDENCE_GAP')
        if self.decoder.closed:
            r.require(all(value['captureId'] == self.capture_id and 1 <= seq <= len(self.live)
                for seq, value in self.diagnostic_states.items()), 'diagnostic state missing from sealed App file', 'EVIDENCE_GAP')
            if isinstance(self.diagnostic_error, dict):
                r.require(self.diagnostic_error.get('captureId') == self.capture_id and not self.decoder.closed.get('healthy'),
                          'diagnostic recorder error conflicts with healthy seal', 'EVIDENCE_GAP')

    def inspect_failed(self, prior):
        """Read-only attribution. Never launch a changed/absent original process."""
        journal = [self.h.read_json(x) for x in sorted((prior / 'journal').glob('*.json'))]
        launches = [x for x in journal if x.get('event') == 'launch-confirmed']
        arms = [i for i, x in enumerate(journal) if x.get('event') == 'tap-intent' and x.get('control') == ARM]
        binding = None
        if not launches and not arms:
            binding = failed_launch_receipts(self.p, prior, self.h)
            self.h.save(self.out / 'launch-association.json', binding)
            launches = [binding]
        r.require(len(launches) == 1 and len(arms) <= 1, 'old action binding unavailable', 'UNRESOLVED_STATE')
        prearm = not arms
        if prearm:
            intents = [i for i, x in enumerate(journal) if x.get('event') == 'tap-intent']
            r.require((intents or binding is not None) and all(journal[i].get('control') in (HOME, DEVICES) and
                i+1 < len(journal) and journal[i+1].get('event') == 'tap-returned' for i in intents) and
                all(x.get('event') in {'stage', 'launch-intent', 'launch-returned', 'launch-confirmed', 'tap-intent', 'tap-returned'}
                    for x in journal), 'pre-ARM actions are not positively bound', 'UNRESOLVED_STATE')
        else:
            r.require(any(x.get('event') == 'tap-returned' for x in journal[arms[0]+1:]),
                      'old ARM return binding unavailable', 'UNRESOLVED_STATE')
        old_pid = str(launches[0]['pid'])
        r.require(old_pid.isdigit(), 'old PID invalid', 'UNRESOLVED_STATE')
        for path in sorted((prior / 'previous-captures').glob('*.jsonl')):
            r.require(re.fullmatch(r'[0-9a-f]{32}\.jsonl', path.name) and path.stat().st_size <= MAX_CAPTURE,
                      'invalid original baseline', 'EVIDENCE_GAP')
            cid, raw = path.stem, path.read_bytes()
            audit = sealed_file(raw, cid)
            self.previous_captures[cid] = dict(bytes=len(raw), sha256=audit['sha256'], final=audit['final'])
        pid = self.cmd(['shell', 'pidof', self.p['app']['id']], success_codes=(0, 1)).strip().decode()
        report = dict(classification='D', originalPid=old_pid, currentPid=pid, sameProcess=pid == old_pid,
                      candidates=[], baselineUnchanged=True, deviceAndApkVerified=True, recordStarts=0,
                      preArmActionsVerified=prearm)
        if binding is not None:
            report['launchAssociation'] = binding
        names = self.capture_names()
        report['directoryReadable'] = True
        r.require(set(self.previous_captures) <= names, 'baseline file missing', 'UNRESOLVED_STATE')
        for cid, old in self.previous_captures.items():
            raw = self.original(cid, self.out / 'arm-baseline' / (cid + '.jsonl'))
            if hashlib.sha256(raw).hexdigest() != old['sha256']:
                report['baselineUnchanged'] = False
        added = names - set(self.previous_captures)
        report['candidateCount'] = len(added)
        candidate_cursor = None
        for cid in sorted(added):
            raw = self.prefix(cid, self.out / 'candidates' / (cid + '.jsonl'))
            item = dict(original=self.h.record(self.out / 'candidates' / (cid + '.jsonl')))
            cursor = FileCursor(cid)
            try:
                states = cursor.feed(raw)
                item.update(header=cursor.decoder.opened, records=len(states),
                    partialTailBytes=len(raw)-cursor.consumed, footer=cursor.decoder.closed,
                    targetBound=bool(states) and all(x['deviceAddress'].lower() == self.p['device']['address'] for x in states))
                if cursor.decoder.closed:
                    item['seal'] = sealed_file(raw, cid)
                if len(added) == 1:
                    candidate_cursor = cursor
            except r.Stop as error:
                item['parseError'] = str(error)
            report['candidates'].append(item)
        focus = self.cmd(['shell', 'dumpsys', 'window'])
        report['foreground'] = r.foreground_ok(focus, self.p['app']['id'])
        tree = None
        if report['foreground'] and pid == old_pid:
            self.pid = pid
            tree = self.ui()
            self.h.raw(self.out / 'current-ui.xml', tree)
        if (binding is not None and binding['owned'] and prearm and not pid and
            not report['foreground'] and report['baselineUnchanged'] and not added):
            # A returned pre-ARM launch can already have exited. Never relaunch
            # it to establish continuity or stop a replacement process.
            services = self.cmd(['shell', 'dumpsys', 'activity', 'services', self.p['app']['id']])
            r.require(services.startswith(b'ACTIVITY MANAGER SERVICES (dumpsys activity services)') and
                b'DeviceOtaService' not in services, 'exited owner service state unavailable/busy', 'UNRESOLVED_STATE')
            r.require(self.capture_names() == set(self.previous_captures),
                      'capture store changed after original process absence', 'UNRESOLVED_STATE')
            for cid, old in self.previous_captures.items():
                raw = self.original(cid, self.out / 'exited-prearm-baseline' / (cid + '.jsonl'))
                r.require(hashlib.sha256(raw).hexdigest() == old['sha256'],
                          'exited original capture baseline changed', 'UNRESOLVED_STATE')
            r.require(not self.cmd(['shell', 'pidof', self.p['app']['id']], success_codes=(0, 1)).strip(),
                      'App appeared during original process absence checks', 'UNRESOLVED_STATE')
            self.capture_resolved = True
            self.mutation_unknown = False
            report.update(classification='C', captureState='PRE_ARM_PROCESS_EXITED_VERIFIED',
                originalProcessAbsentVerified=True, processAbsenceObservations=2,
                originalLaunchResolved=True, uiReadinessClaimed=False, freshUpgradeStateClaimed=False)
        elif pid != old_pid or not report['baselineUnchanged'] or len(added) > 1 or prearm and added:
            report['missingEvidence'] = 'original process continuity/unchanged baseline/unique candidate not established'
        elif prearm and not added and tree is not None:
            report['preArmPage'] = prearm_page(tree, self.p['app']['id'])
            self.prearm_navigation = True
            self.mutation_unknown = False
            self.capture_resolved = True
            report.update(classification='C', captureState='PRE_ARM_NAVIGATION_VERIFIED')
            if binding is not None and binding['owned']:
                self.owned_app_pid = old_pid
                self.owned_launch_confirmed = True
        elif prearm and not added:
            report.update(classification='C', captureState='PRE_ARM_FOREGROUND_RESTORE_REQUIRED')
        elif not added:
            report['classification'] = 'C'
            report['captureState'] = 'NOT_CONFIRMED'
            if tree is not None and self.not_started_ui(tree):
                self.arm_attempted = self.arm_baseline_confirmed = self.capture_resolved = True
                self.mutation_unknown = False
                report['captureState'] = 'NOT_STARTED_VERIFIED'
        else:
            item = report['candidates'][0]
            report['classification'] = 'A' if item.get('targetBound') and not item.get('parseError') else 'B'
            report['captureState'] = 'UNRESOLVED_PARTIAL'
            if report['classification'] == 'A':
                self.pid = pid
                self.arm_attempted = self.arm_baseline_confirmed = True
                self.capture_id = next(iter(added))
                self.file_cursor, self.decoder = candidate_cursor, candidate_cursor.decoder
                self.live = r.Decoder().feed(candidate_cursor.raw)  # Recovery only; never a smoke observation claim.
                for state in self.live:
                    idle_phase(state, self.p)
                report['captureState'] = 'SEALED' if self.decoder.closed else 'ACTIVE'
                self.capture_state = report['captureState']
        report['associationBasis'] = [('closed launch receipts; no ARM/business actions' if binding is not None else
            'returned HOME/DEVICES only') if prearm else 'original ARM intent/return',
            'original launch PID + repeated current process absence' if report.get('originalProcessAbsentVerified') else
            'original PID/current PID comparison (see sameProcess)', 'verified phone/APK', 'unchanged original baseline',
            'no new capture plus known pre-ARM page verification' if prearm else 'real header and target states']
        if tree is not None:
            report['associationBasis'].append('foreground test APP hierarchy')
        self.h.save(self.out / 'inspection.json', report)
        return report

    def not_started_ui(self, tree):
        pkg = self.p['app']['id']
        arms = [n for n in nodes(tree, pkg).iter('node') if n.get('resource-id') == 'p35-arm']
        if len(arms) != 1 or not any(n.get('content-desc', '').endswith(': off') for n in arms[0].iter('node')):
            return False
        self.idle_recorder_ui()
        r.find_control(tree, ARM, pkg)
        r.require(r.idle_equivalent(tree, self.ui()) and self.capture_names() == set(self.previous_captures),
                  'unstarted recorder evidence changed', 'UNRESOLVED_STATE')
        return True

    def record_smoke(self):
        self.prepare_recorder()
        self.enter('capture-start')
        xml = self.ui()
        r.require(not any(n.get('resource-id') == 'p35-stop' for n in nodes(xml, self.p['app']['id']).iter('node')),
                  'existing recording active; preserve and reconcile', 'UNRESOLVED_STATE')
        try:
            self.control(ARM)
        except r.Stop as error:
            if error.code == 'TIMEOUT' or error.code == 'UI_UNAVAILABLE' and str(error) == 'control disabled/not clickable':
                raise r.Stop('PRECONDITION_FAILED',
                    'recorder arm unavailable; check identity/permissions or one-use recorder fresh-process prerequisite; '
                    'no automatic restart, reinstall or data clearing') from error
            raise
        r.require(self.capture_names() == set(self.previous_captures), 'capture store changed before ARM', 'UNRESOLVED_STATE')
        for cid, old in self.previous_captures.items():
            raw = self.original(cid, self.out / 'arm-baseline' / (cid + '.jsonl'))
            r.require(hashlib.sha256(raw).hexdigest() == old['sha256'], 'old original changed before ARM', 'EVIDENCE_GAP')
        self.ui()
        self.arm_baseline_confirmed = True
        self.record('arm-baseline', pid=self.pid, captures=self.previous_captures)
        self.logcat = self.h.Process(self.out, 'logcat', self.phone.base +
            ['logcat', '-v', 'epoch', '--pid=' + self.pid, '-T', '1', '*:V'], self.phone.env)
        time.sleep(.2)
        r.require(self.logcat.alive(), 'logcat not ready', 'COLLECTOR_FAILED')
        self.offset = 0
        self.arm_attempted = True
        self.arm_action_count = 1
        self.capture_state = 'ARM_UNCONFIRMED'
        self.tap(ARM)
        self.wait(lambda: (self.pump(), bool(self.live))[1])
        r.require(self.decoder.closed is None, 'capture closed before query', 'EVIDENCE_GAP')
        self.mutation_unknown = False

        self.enter('fresh-identity')
        self.pump()
        previous = self.live[-1]['seq']
        self.tap(QUERY)  # Normal connector plus GET_INFO, never disconnect/transfer.
        def identity():
            self.pump()
            return latest_identity(self.live, previous)
        fresh = self.wait(identity)
        idle_phase(fresh, self.p)
        self.identity_seq = fresh['seq']
        self.mutation_unknown = False
        self.record('identity-query-observed', seq=fresh['seq'],
            freshIdentityVerified=not product_failures([fresh], self.p))

        self.enter('capture-observe')
        def covered():
            self.pump()
            beats = [s for s in self.live if s['event'] == 'heartbeat' and s['seq'] > fresh['seq']]
            return len(beats) >= self.p['scenario']['min_heartbeats'] and self.live[-1]['monoUs'] - fresh['monoUs'] >= (
                self.p['scenario']['capture_seconds'] * 1_000_000)
        self.wait(covered)
        self.enter('capture-stop')
        self.pump()
        r.require(self.decoder.closed is None, 'capture already closed before configured STOP', 'EVIDENCE_GAP')
        self.stop_attempted = True
        self.tap(STOP)
        self.wait(lambda: (self.pump(), self.decoder.closed)[1])

        self.enter('retrieve-audit')
        raw = self.original(self.capture_id, self.out / 'app-capture.jsonl')
        # Closing integrity resolves ownership even if the smoke assertions fail.
        r.require(raw == self.file_cursor.raw, 'sealed original differs from observed file prefix', 'EVIDENCE_GAP')
        self.capture_seal = sealed_file(raw, self.capture_id)
        self.capture_resolved = True
        self.mutation_unknown = False
        footer = r.strict_json(raw.splitlines()[-1][len(b'OTA_P35_CAPTURE '):])
        r.require(self.decoder.closed == footer, 'live/stored close receipt mismatch', 'EVIDENCE_GAP')
        self.diagnostic_pump()
        self.compare_diagnostics()
        report = audit_smoke(raw, self.capture_id, self.p, self.live, self.identity_seq,
                            observation_source=self.observation_source, samples=self.file_samples)
        report['logcatOverlapRecords'] = len(set(self.diagnostic_states) & {x['seq'] for x in self.live})
        report['logcatDiagnosticError'] = self.diagnostic_error
        self.h.save(self.out / 'app-capture-integrity.json', report)
        for cid, old in self.previous_captures.items():
            old_raw = self.original(cid, self.out / 'after-capture-baseline' / (cid + '.jsonl'))
            r.require(hashlib.sha256(old_raw).hexdigest() == old['sha256'], 'old original changed during smoke', 'EVIDENCE_GAP')
        report['previousCapturesUnchanged'] = True
        self.idle_services()
        self.ui()
        return report

    def recover_sealed_stop(self):
        """Resolve only an already-stopped recorder, never repair live evidence."""
        r.require(self.arm_attempted and self.arm_baseline_confirmed and self.stop_attempted and
            self.stream_failed and not self.stop_seal_recovered and self.capture_id and self.live and
            self.live[0]['seq'] == 1 and self.capture_id not in self.previous_captures and
            self.decoder.opened == dict(schema=1, kind='open', captureId=self.capture_id),
            'no bound STOP/failed stream for sealed recovery', 'UNRESOLVED_STATE')
        raw = self.original(self.capture_id, self.out / 'sealed-stop-original.jsonl')
        report = r.audit_capture(raw, self.capture_id)
        rows = FileCursor(self.capture_id).feed(raw)
        r.require(self.original_verified and all(0 < row['seq'] <= len(rows) and rows[row['seq'] - 1] == row
                  for row in self.live), 'sealed recovery conflicts with observed rows', 'EVIDENCE_GAP')
        r.require(rows[-1]['phase'] in {'idle', 'failed', 'cancelled'} and
            all(row['phase'] not in {'applying', 'waitingReboot', 'reconnectVerify', 'completed'} and
                (row['packageBytes'] == 0 or row['durable'] < row['packageBytes']) for row in rows),
            'sealed recovery has unknown/post-transfer outcome', 'UNRESOLVED_STATE')
        self.h.save(self.out / 'sealed-stop-recovery.json', dict(archive=report,
            observedRecords=len(self.live), liveEvidence='FAILED_UNCHANGED', noNewStop=True))
        self.capture_seal = sealed_file(raw, self.capture_id)
        self.capture_recovery_states = rows
        self.capture_resolved = self.stop_seal_recovered = True
        self.capture_state = 'SEALED_WITH_LIVE_GAP'
        self.mutation_unknown = False

    def cleanup(self):
        errors = []
        self.stage_deadline = time.monotonic() + self.p['limits']['cleanup_seconds']
        self.phone.operation_deadline = self.stage_deadline
        if self.arm_attempted and not self.capture_resolved:
            try:
                if self.arm_baseline_confirmed and not self.stream_failed:
                    self.pump()
                if self.capture_id:
                    # Only our confirmed, idle capture may be stopped, once.
                    if self.decoder.closed is None and not self.stop_attempted and not self.stream_failed and self.live:
                        self.pump()
                        self.check_cleanup_state(self.decoder.previous)
                        self.stop_attempted = True
                        self.tap(STOP)
                        self.wait(lambda: (self.pump(), self.decoder.closed)[1])
                    destination = self.out / 'app-capture.jsonl'
                    if self.decoder.closed is None:
                        self.prefix(self.capture_id, self.out / 'unsealed-prefix.jsonl')
                        raise r.Stop('UNRESOLVED_STATE', 'active prefix preserved; not a sealed original')
                    if not destination.exists():
                        raw = self.original(self.capture_id, destination)
                    else:
                        raw = destination.read_bytes()
                    r.require(self.original_verified, 'original remote readback not verified', 'EVIDENCE_GAP')
                    r.require(self.file_cursor is None or raw == self.file_cursor.raw,
                              'salvage original differs from observed prefix', 'EVIDENCE_GAP')
                    self.capture_seal = sealed_file(raw, self.capture_id)
                    self.capture_resolved = True
                    self.mutation_unknown = False
                elif self.arm_baseline_confirmed and not self.stream_failed and self.not_started_ui(self.ui()):
                    self.capture_resolved = True
                    self.capture_state = 'NOT_STARTED_VERIFIED'
                    self.mutation_unknown = False
                    self.record('arm-not-started-verified')
            except BaseException as error:
                errors.append(dict(step='capture-salvage', code=getattr(error, 'code', 'HOST_FAILED'), detail=str(error)))
                if self.stop_attempted and self.stream_failed:
                    try:
                        self.recover_sealed_stop()
                    except BaseException as recovery_error:
                        errors.append(dict(step='sealed-stop-recovery',
                            code=getattr(recovery_error, 'code', 'HOST_FAILED'), detail=str(recovery_error)))
        if self.owned_app_pid and not self.owned_app_closed:
            try:
                r.require(not self.owned_stop_attempted and not self.mutation_unknown and
                    (not self.stream_failed or self.stop_seal_recovered) and
                    self.owned_launch_confirmed and (not self.restart_attempted or self.restart_confirmed) and
                    (not self.arm_attempted or self.capture_resolved),
                    'owned APP action/capture unresolved; no process stop', 'UNRESOLVED_STATE')
                if self.arm_attempted and self.decoder.previous is not None:
                    self.check_cleanup_state(self.capture_seal['final'] if self.stop_seal_recovered else self.decoder.previous)
                if self.prearm_navigation and not self.arm_attempted:
                    self.idle_prearm_ui()
                else:
                    self.idle_recorder_ui()
                self.owned_stop_attempted = True
                self.stop_app_process(self.owned_app_pid, 'owned-app-stop')
                self.owned_app_closed = True
            except BaseException as error:
                errors.append(dict(step='owned-app', code=getattr(error, 'code', 'CLEANUP_FAILED'), detail=str(error)))
        for name, close in [('logcat', lambda: self.logcat.close('smoke-finished') if self.logcat else None),
                            ('usb', lambda: self.phone.close() if self.phone.server else None)]:
            try:
                close()
            except BaseException as error:
                errors.append(dict(step=name, code='CLEANUP_FAILED', detail=str(error)))
        try:
            self.h.pinned(self.p['phone']['adb_key'])
            r.require(not self.phone.server or not self.h.listening(self.phone.port),
                      'private ADB still listening', 'CLEANUP_FAILED')
        except BaseException as error:
            errors.append(dict(step='post-close', code='CLEANUP_FAILED', detail=str(error)))
        return dict(complete=not errors, errors=errors, captureResolved=self.capture_resolved,
            appRestartAttempts=int(self.restart_attempted), appRestartConfirmed=self.restart_confirmed,
            ownedAppLaunchConfirmed=self.owned_launch_confirmed,
            ownedAppStopAttempts=int(self.owned_stop_attempted), ownedAppClosed=self.owned_app_closed,
            observationSource=self.observation_source, armAttempts=self.arm_action_count,
            stopAttempts=int(self.stop_attempted), logcatDiagnosticError=self.diagnostic_error,
            captureSeal=self.capture_seal,
            sealedStopRecovered=self.stop_seal_recovered,
            captureState=self.capture_state,
            unresolved=self.mutation_unknown or self.arm_attempted and not self.capture_resolved or
                self.restart_attempted and not self.restart_confirmed or
                bool(self.owned_app_pid and not self.owned_app_closed))


def failure(error, stage):
    code = getattr(error, 'code', 'HOST_FAILED')
    blocked = {'ENV_BLOCKED', 'DEVICE_BUSY', 'UNRESOLVED_STATE', 'UI_UNAVAILABLE', 'UI_WAIT',
               'PRECONDITION_FAILED', 'IDENTITY_MISMATCH', 'TARGET_SEARCH_INCOMPLETE'}
    return dict(outcome='BLOCKED' if code in blocked else 'FAIL', stage=stage, code=code, reason=str(error))


def redacted_plan(p):
    value = json.loads(json.dumps(p))
    for section, fields in [('phone', ['serial', 'adb_key']), ('device', ['address', 'display_name'])]:
        for key in fields:
            value[section][key] = '<redacted; bound by configuration SHA256>'
    return value


def preflight_outputs(h, out):
    out = h.checked(out)
    r.require(not out.exists(), 'existing output; preserve prior result, no replay')
    for name in ('plan.json', 'inputs.json', 'result.json', 'report.txt', 'audit.json', 'usb', 'host',
        'journal', 'previous-captures', 'after-restart-captures', 'previous-owner-results', 'prior-lock.json', 'app-capture.jsonl',
        'app-capture-integrity.json', 'unresolved-owner.json', 'observations', 'arm-baseline', 'inspection.json',
        'candidates', 'current-ui.xml', 'after-capture-baseline', 'prearm-cleanup-captures', 'previous-recovery-lease.json',
        'previous-recovery-result.json', 'previous-recovery-usb-closed.json', 'launch-association.json',
        'exited-prearm-baseline'):
        h.checked(out / name)
    for suffix in ('stdout', 'stderr', 'started.json', 'closed.json'):
        h.checked(out / ('logcat.' + suffix))
    h.checked(ROOT / '.cache/p34-live-device.lock')
    h.checked(ROOT / '.cache/p35-reconcile-device.lock')
    return out


def reclaim_query_only_lease(h, lease, out, original_lock_bytes):
    """Reclaim closed reads, or a sealed capture with confirmed same-PID foreground restore."""
    previous = h.read_json(lease)
    previous_out = h.checked(previous['out'])
    previous_result = h.read_json(previous_out / 'result.json')
    previous_usb = h.read_json(previous_out / 'usb/closed.json')
    cleanup = previous_result.get('cleanup', {})
    sealed_restore = (previous_result.get('captureResolved') is True and cleanup.get('captureResolved') is True and
        cleanup.get('ownedAppStopAttempts') == 0 and cleanup.get('errors') and
        all(x.get('step') == 'owned-app' and x.get('code') == 'UI_UNAVAILABLE' for x in cleanup['errors']))
    previous_inspection = previous_result.get('inspection', {})
    prearm_restore = (cleanup.get('complete') is True and cleanup.get('ownedAppStopAttempts') == 0 and
        previous_inspection.get('preArmActionsVerified') is True and previous_inspection.get('sameProcess') is True and
        previous_inspection.get('baselineUnchanged') is True and previous_inspection.get('candidateCount') == 0 and
        str(previous_inspection.get('originalPid')) == str(previous_inspection.get('currentPid')) and
        (previous_out / 'owner-lock.json').read_bytes() == original_lock_bytes)
    restored = sealed_restore or prearm_restore
    r.require(previous.get('originalOwnerSha256') == hashlib.sha256(original_lock_bytes).hexdigest() and
        previous_result.get('outcome') == 'BLOCKED' and previous_result.get('stopAttempts') == 0 and
        previous_result.get('recordStarts') == 0 and (cleanup.get('complete') is True or sealed_restore) and
        previous_usb.get('cleanup_complete') is True and previous_usb.get('server_closed') is True and
        previous_usb.get('listening') is False, 'old recovery actions/closure unresolved', 'UNRESOLVED_STATE')
    journals = [h.read_json(path) for path in (previous_out / 'journal').glob('*.json')]
    if prearm_restore:
        r.require(all(x.get('event') in {'stage', 'launch-intent', 'launch-confirmed'} for x in journals),
                  'old pre-ARM recovery had non-foreground actions', 'UNRESOLVED_STATE')
    if sealed_restore:
        raw = (previous_out / 'app-capture.jsonl').read_bytes()
        header = r.strict_json(raw.splitlines()[0][len(b'OTA_P35_CAPTURE '):])
        seal = sealed_file(raw, header['captureId'])
        r.require(seal['sha256'] == previous_result['integrity']['sha256'] and
            (previous_out / 'owner-lock.json').read_bytes() == original_lock_bytes,
            'old sealed capture/owner receipt changed', 'UNRESOLVED_STATE')
    if restored:
        intents = [x for x in journals if x.get('event') == 'launch-intent']
        confirmations = [x for x in journals if x.get('event') == 'launch-confirmed']
        pid = previous_result['inspection']['originalPid']
        r.require(str(pid).isdigit() and int(pid) > 0 and len(intents) == len(confirmations) == 1 and str(confirmations[0]['pid']) == str(pid) and
            str(previous_result['inspection']['currentPid']) == str(pid),
            'old foreground restoration outcome unconfirmed', 'UNRESOLVED_STATE')
    r.require(not any(item.get('event') in {'tap-intent', 'scroll-intent', 'owned-app-stop-intent', 'restart-stop-intent'} or
        item.get('event') == 'launch-intent' and not restored for item in journals),
              'previous recovery had a mutation intent; no lease bypass', 'UNRESOLVED_STATE')
    r.require(type(previous.get('pid')) is int and previous['pid'] > 0, 'invalid recovery owner', 'UNRESOLVED_STATE')
    data = h.command(out, 'previous-recovery-owner', ['tasklist', '/FO', 'CSV', '/NH', '/FI',
        'PID eq ' + str(previous['pid'])], h.environment(out), seconds=15)
    rows = list(csv.reader(io.StringIO(data.decode('utf-8', 'replace'))))
    r.require(rows and not any(len(row) > 1 and row[1] == str(previous['pid']) for row in rows),
              'old recovery owner live/unconfirmed', 'UNRESOLVED_STATE')
    old_bytes = lease.read_bytes()
    h.raw(out / 'previous-recovery-lease.json', old_bytes)
    h.raw(out / 'previous-recovery-result.json', (previous_out / 'result.json').read_bytes())
    h.raw(out / 'previous-recovery-usb-closed.json', (previous_out / 'usb/closed.json').read_bytes())
    r.require(h.read_json(lease) == previous, 'recovery owner changed', 'UNRESOLVED_STATE')
    lease.unlink()  # Proven query-only, dead owner; originals preserved above.


def reconcile_file_source(p, prior, out, h, lock_bytes, original_result, *, inspect_only=False):
    lock = h.checked(ROOT / '.cache/p34-live-device.lock')
    lease = h.checked(ROOT / '.cache/p35-reconcile-device.lock')
    lease_value = dict(pid=os.getpid(), out=str(out), originalOwnerSha256=hashlib.sha256(lock_bytes).hexdigest())
    for name in ('owner-lock.json', 'original-result.json', 'lease.json'):
        h.checked(out / name)
    h.raw(out / 'owner-lock.json', lock_bytes)
    h.raw(out / 'original-result.json', (prior / 'result.json').read_bytes())
    report = dict(outcome='BLOCKED', stage='inspect-original', classification='D', observationSource='app-file',
        originalSmokeOutcome=original_result['outcome'], freshIdentityClaimed=False, smokeReplayed=False,
        recordStarts=0, stopAttempts=0, ownerReleased=False, captureResolved=False, inspectOnly=inspect_only)
    driver, lease_owned = None, False
    with h.device_owner(out, read_only=True):
        try:
            r.require(lock.read_bytes() == lock_bytes, 'old owner changed', 'UNRESOLVED_STATE')
            driver = Smoke(p, out, h)
            driver.start_phone()
            driver.enter('inspect-original')
            inspection = driver.inspect_failed(prior)
            report.update(inspection=inspection, classification=inspection['classification'])
            if inspect_only:
                report['stage'] = 'inspection-complete'
            else:
                exited_after_seal = False
                if (inspection.get('currentPid') == '' and inspection.get('baselineUnchanged') and
                    inspection.get('candidateCount') == 1 and lease.exists()):
                    previous_out = h.checked(h.read_json(lease)['out'])
                    previous_result = h.read_json(previous_out / 'result.json')
                    previous_inspection = previous_result.get('inspection', {})
                    if (previous_result.get('captureResolved') is True and previous_inspection.get('classification') == 'A' and
                        previous_inspection.get('sameProcess') is True and
                        previous_inspection.get('originalPid') == inspection['originalPid'] and
                        (previous_out / 'owner-lock.json').read_bytes() == lock_bytes):
                        candidate = inspection['candidates'][0]['original']
                        previous_file = h.checked(previous_out / 'app-capture.jsonl')
                        r.require(0 < previous_file.stat().st_size <= MAX_CAPTURE,
                                  'prior recovered original size bound', 'EVIDENCE_GAP')
                        raw = previous_file.read_bytes()
                        seal = previous_result['integrity']
                        r.require(hashlib.sha256(raw).hexdigest() == candidate['sha256'] == seal['sha256'],
                                  'previously attributed sealed file changed', 'EVIDENCE_GAP')
                        cid = seal['footer']['captureId']
                        driver.file_cursor = FileCursor(cid)
                        driver.file_cursor.feed(raw)
                        driver.decoder = driver.file_cursor.decoder
                        driver.capture_id = cid
                        driver.capture_seal = sealed_file(raw, cid)
                        idle_phase(driver.capture_seal['final'], p)
                        driver.capture_resolved = True
                        driver.capture_state = 'SEALED'
                        exited_after_seal = True
                        inspection.update(captureState='PREVIOUSLY_SEALED_APP_EXITED',
                            originalProcessAbsentVerified=True, priorAssociation=h.record(previous_out / 'result.json'))
                r.require(inspection.get('captureState') in {'SEALED', 'ACTIVE', 'NOT_STARTED_VERIFIED',
                    'PREVIOUSLY_SEALED_APP_EXITED', 'PRE_ARM_NAVIGATION_VERIFIED', 'PRE_ARM_FOREGROUND_RESTORE_REQUIRED',
                    'PRE_ARM_PROCESS_EXITED_VERIFIED'},
                          'capture attribution unresolved; see inspection originals', 'UNRESOLVED_STATE')
                r.require(lock.read_bytes() == lock_bytes, 'owner changed after inspection', 'UNRESOLVED_STATE')
                if lease.exists():
                    reclaim_query_only_lease(h, lease, out, lock_bytes)
                h.save(lease, lease_value)
                h.save(out / 'lease.json', lease_value)
                lease_owned = True
                if inspection['captureState'] == 'PRE_ARM_FOREGROUND_RESTORE_REQUIRED':
                    r.require(inspection['sameProcess'] and inspection['preArmActionsVerified'] and
                        inspection['baselineUnchanged'] and inspection['candidateCount'] == 0,
                        'foreground restore is not bound to a pre-ARM owner', 'UNRESOLVED_STATE')
                    driver.pid = inspection['originalPid']
                    driver.prearm_navigation = True
                    driver.foreground_existing(driver.pid)
                    driver.mutation_unknown = True
                    inspection['preArmPage'] = prearm_page(driver.ui(), p['app']['id'])
                    driver.idle_services()
                    driver.mutation_unknown = False
                    driver.capture_resolved = True
                    inspection.update(captureState='PRE_ARM_NAVIGATION_VERIFIED', foregroundRestored=True)
                if original_result.get('cleanup', {}).get('ownedAppLaunchConfirmed') and not exited_after_seal:
                    driver.owned_app_pid = driver.pid
                    driver.owned_launch_confirmed = True
                if (inspection['captureState'] == 'PRE_ARM_NAVIGATION_VERIFIED' and
                    inspection.get('launchAssociation', {}).get('owned')):
                    driver.owned_app_pid = inspection['originalPid']
                    driver.owned_launch_confirmed = True
                if inspection['captureState'] == 'ACTIVE':
                    driver.foreground_existing(driver.pid)
                    driver.enter('reconcile-capture')
                    driver.pump()
                    if driver.decoder.closed is None:
                        idle_phase(driver.decoder.previous, p)
                        report['stopAttempts'] = 1
                        driver.stop_attempted = True
                        driver.tap(STOP)
                        driver.wait(lambda: (driver.pump(), driver.decoder.closed)[1])
                if driver.capture_id:
                    raw = driver.original(driver.capture_id, out / 'app-capture.jsonl')
                    seal = sealed_file(raw, driver.capture_id)
                    driver.capture_seal = seal
                    idle_phase(seal['final'], p)
                    driver.capture_resolved = True
                    driver.mutation_unknown = False
                    report.update(integrity=seal, recoveredCaptureHealthy=seal['healthy'],
                                  testOutcome='NOT_RECONSTRUCTED' if seal['healthy'] else 'FAIL')
                report.update(outcome='ORIGINALS_RECOVERED' if driver.capture_id else 'ORIGINAL_NOT_STARTED_VERIFIED',
                              stage='original-actions-resolved', captureResolved=driver.capture_resolved)
                if driver.owned_app_pid and inspection['captureState'] != 'PRE_ARM_NAVIGATION_VERIFIED':
                    # Restore this already-confirmed process, never cold-launch
                    # an absent/changed owner merely to manufacture UI evidence.
                    driver.foreground_existing(driver.pid)
                if exited_after_seal:
                    driver.mutation_unknown = True
                    r.require(not driver.cmd(['shell', 'pidof', p['app']['id']], success_codes=(0, 1)).strip(),
                              'App appeared after sealed-owner absence check', 'UNRESOLVED_STATE')
                    driver.mutation_unknown = False
        except BaseException as error:
            report.update(failure(error, driver.stage if driver else 'inspect-original'))
        finally:
            if driver:
                if inspect_only:
                    try:
                        driver.phone.close()
                        report['cleanup'] = dict(complete=True, errors=[], deviceActions=0)
                    except BaseException as error:
                        report['cleanup'] = dict(complete=False, errors=[str(error)])
                else:
                    report['cleanup'] = driver.cleanup()
                    report['captureResolved'] = driver.capture_resolved
                cleanup = report['cleanup']
                if not cleanup['complete']:
                    report.update(outcome='BLOCKED', stage='cleanup', code='UNRESOLVED_STATE')
                if (not inspect_only and lease_owned and cleanup['complete'] and driver.capture_resolved and
                    not cleanup.get('unresolved')):
                    r.require(lock.read_bytes() == lock_bytes and h.read_json(lease) == lease_value,
                              'ownership changed before release', 'UNRESOLVED_STATE')
                    lock.unlink()
                    lease.unlink()
                    report.update(ownerReleased=True, outcome='ORIGINAL_OWNER_RESOLVED')
                    if driver.capture_seal is not None:
                        report.update(integrity=driver.capture_seal, recoveredCaptureHealthy=driver.capture_seal['healthy'],
                                      testOutcome='NOT_RECONSTRUCTED' if driver.capture_seal['healthy'] else 'FAIL')
            h.save(out / 'result.json', report)
    h.save(out / 'audit.json', dict(root=str(ROOT), outputs=[h.record(h.checked(x)) for x in sorted(out.rglob('*'))
        if x.is_file()], selectedExternalWrites=[], originalFailureUnchanged=
        (out / 'original-result.json').read_bytes() == (prior / 'result.json').read_bytes(),
        originalLockPreserved=lock.exists() and lock.read_bytes() == lock_bytes,
        privateAdbListening=h.listening(p['phone']['adb_port'])))
    print(json.dumps(dict(outcome=report['outcome'], classification=report['classification'],
        ownerReleased=report['ownerReleased'], recordStarts=0, stopAttempts=report['stopAttempts'],
        evidence=str(out.relative_to(ROOT)))), flush=True)
    return 0 if report['ownerReleased'] else 1 if report['outcome'] == 'FAIL' else 2


def reconcile(p, configuration, prior, out, h, *, sealed_original=None, inspect_only=False):
    """Complete an evidenced owner's capture stop, never rerun the smoke.

    The original failed result and device lock stay unchanged. A disconnected
    idle recorder can be stopped safely; it is not fresh identity evidence.
    """
    prior = h.checked(prior)
    out = preflight_outputs(h, out)
    lock = h.checked(ROOT / '.cache/p34-live-device.lock')
    lease = h.checked(ROOT / '.cache/p35-reconcile-device.lock')
    for name in ('before-prefix.jsonl', 'prefixes', 'owner-lock.json', 'lease.json', 'original-result.json',
        'previous-recovery-lease.json', 'previous-recovery-result.json', 'previous-recovery-usb-closed.json',
        'previous-sealed-original.jsonl'):
        h.checked(out / name)
    r.require(lock.is_file(), 'outstanding owner required', 'UNRESOLVED_STATE')
    lock_bytes = lock.read_bytes()
    sealed_bytes = None
    if sealed_original is not None:
        sealed_original = h.checked(sealed_original)
        r.require(sealed_original.is_file() and 0 < sealed_original.stat().st_size <= MAX_CAPTURE,
                  'bounded previously recovered original required', 'UNRESOLVED_STATE')
        sealed_bytes = sealed_original.read_bytes()
    owner = h.read_json(lock)
    r.require(h.checked(owner['out']) == prior, 'recovery owner/output mismatch', 'UNRESOLVED_STATE')
    result = h.read_json(prior / 'result.json')
    closed = h.read_json(prior / 'usb/closed.json')
    inputs = h.read_json(prior / 'inputs.json')
    smoke_bound = (result.get('otaOperations') == 0 and result.get('radioToggles') == 0 and
        result.get('installOperations') == 0 and
        inputs.get('configurationSha256') == hashlib.sha256(configuration).hexdigest())
    campaign_bound = False
    if inputs.get('mode') == 'run':
        original_plan = (prior / 'plan.json').read_bytes()
        single = inputs.get('singleUpgrade', False)
        r.require(type(single) is bool, 'invalid original campaign profile', 'UNRESOLVED_STATE')
        plan = r.validate_plan(r.strict_json(original_plan), single=single)
        journal = [h.read_json(x) for x in sorted((prior / 'journal').glob('*.json'))]
        cleanup = result.get('cleanup', {})
        r.require(inputs.get('planSha256') == hashlib.sha256(original_plan).hexdigest() and
            plan['phone'] == p['phone'] and plan['app'] == p['app'] and
            plan['firmware']['device_address'] == p['device']['address'] and
            plan['firmware']['current'] == dict(version=p['device']['expected_version'], sha256=p['device']['expected_sha256']) and
            result.get('outcome') == 'UNRESOLVED_STATE' and result.get('cases') == [] and
            result.get('recovered') == 0 and
            result.get('caseResults') == [dict(id=x['id'], outcome='NOT_RUN') for x in plan['cases']] and
            result.get('executionError', {}).get('code') == 'UI_UNAVAILABLE' and
            cleanup.get('captureState') == 'NOT_ARMED' and cleanup.get('armAttempts') == 0 and
            cleanup.get('stopAttempts') == 0 and cleanup.get('ownedAppStopAttempts') == 0 and
            cleanup.get('appRestartAttempts') == 0 and
            sum(x.get('event') == 'launch-intent' for x in journal) == 1 and
            all(x.get('event') in {'stage', 'launch-intent', 'launch-returned'} for x in journal) and
            all(x.get('stage') in {'preflight', 'launch'} for x in journal if x.get('event') == 'stage'),
            'campaign is not a bound pre-ARM launch failure', 'UNRESOLVED_STATE')
        failed_launch_receipts(p, prior, h)
        campaign_bound = True
    r.require(result.get('lockRetained') is True and (smoke_bound or campaign_bound) and
        closed.get('cleanup_complete') is True and closed.get('server_closed') is True and closed.get('listening') is False,
        'original operation/configuration/closure unbound', 'UNRESOLVED_STATE')
    old_decoder = r.Decoder()
    logcat = prior / 'logcat.stdout'
    if logcat.exists():
        old_decoder.feed(logcat.read_bytes())
    if inspect_only or not old_decoder.opened or not old_decoder.previous:
        r.require(sealed_original is None, 'zero-log recovery discovers actual originals, not supplied capture IDs', 'UNRESOLVED_STATE')
        return reconcile_file_source(p, prior, out, h, lock_bytes, result, inspect_only=inspect_only)
    r.require(old_decoder.opened and old_decoder.previous, 'old capture ID unavailable', 'UNRESOLVED_STATE')
    capture_id = old_decoder.opened['captureId']
    idle_phase(old_decoder.previous, p)
    if sealed_bytes is not None:
        capture_prefix(sealed_bytes, capture_id, p)
        r.audit_capture(sealed_bytes, capture_id)
    launched = [h.read_json(path) for path in sorted((prior / 'journal').glob('*.json'))]
    pids = [item['pid'] for item in launched if item.get('event') == 'launch-confirmed']
    r.require(len(pids) == 1 and str(pids[0]).isdigit(), 'old App PID unavailable', 'UNRESOLVED_STATE')
    for pin in (p['phone']['adb'], p['phone']['adb_key']):
        h.pinned(pin)
    h.raw(out / 'owner-lock.json', lock_bytes)
    h.raw(out / 'original-result.json', (prior / 'result.json').read_bytes())
    if sealed_bytes is not None:
        h.raw(out / 'previous-sealed-original.jsonl', sealed_bytes)
    lease_value = dict(pid=os.getpid(), out=str(out), originalOwnerSha256=hashlib.sha256(lock_bytes).hexdigest())
    driver = None
    report = dict(outcome='BLOCKED', stage='reconcile-owner', formalAcceptance='NOT_ADJUDICATED',
        originalSmokeOutcome=result['outcome'], smokeReplayed=False, recordStarts=0, stopAttempts=0,
        ownerReleaseRequested=sealed_bytes is not None, ownerReleased=False)
    with h.device_owner(out, read_only=True):
        if lease.exists():
            reclaim_query_only_lease(h, lease, out, lock_bytes)
        h.save(lease, lease_value)
        h.save(out / 'lease.json', lease_value)
        try:
            r.require(lock.read_bytes() == lock_bytes, 'old ownership changed', 'UNRESOLVED_STATE')
            driver = Smoke(p, out, h)
            driver.start_phone()
            driver.foreground_existing(str(pids[0]))
            driver.enter('reconcile-capture')
            raw = driver.prefix(capture_id, out / 'before-prefix.jsonl')
            decoded = capture_prefix(raw, capture_id, p)
            r.require(decoded.previous['seq'] >= old_decoder.previous['seq'] and
                decoded.previous['monoUs'] >= old_decoder.previous['monoUs'], 'capture replayed/truncated', 'EVIDENCE_GAP')
            if sealed_bytes is not None:
                r.require(decoded.closed is not None and raw == sealed_bytes,
                          'previously resolved capture changed/reopened; no release or stop', 'UNRESOLVED_STATE')
                driver.idle_services()
                tree = driver.ui()
                r.require(not any(n.get('resource-id') == 'p35-stop' for n in nodes(tree, p['app']['id']).iter('node')),
                          'current APP has an active recorder', 'UNRESOLVED_STATE')
                r.find_control(tree, {'resource-id': 'p35-check'}, p['app']['id'])
                r.require(r.idle_equivalent(tree, driver.ui()), 'APP state changed before owner release', 'UNRESOLVED_STATE')
            if decoded.closed is None:
                report['stopAttempts'] = 1
                driver.tap(STOP)
                reads = 0
                def sealed():
                    nonlocal reads
                    reads += 1
                    raw = driver.prefix(capture_id, out / 'prefixes' / ('%05d.jsonl' % reads))
                    return capture_prefix(raw, capture_id, p).closed
                driver.wait(sealed)
            raw = driver.original(capture_id, out / 'app-capture.jsonl')
            integrity = r.audit_capture(raw, capture_id)
            driver.capture_id = capture_id
            driver.capture_resolved = True
            driver.mutation_unknown = False
            h.save(out / 'app-capture-integrity.json', integrity)
            report.update(outcome='ORIGINALS_RECOVERED', stage='complete', integrity=integrity,
                recordStopVerified=True, freshIdentityClaimed=False)
        except BaseException as error:
            report.update(failure(error, driver.stage if driver else 'reconcile-owner'))
        finally:
            if driver:
                cleanup = driver.cleanup()
                report['cleanup'] = cleanup
                if not cleanup['complete']:
                    report.update(outcome='FAIL', stage='cleanup', code='CLEANUP_FAILED')
                elif cleanup['unresolved']:
                    report.update(outcome='BLOCKED', stage='cleanup', code='UNRESOLVED_STATE')
            if report['outcome'] == 'ORIGINALS_RECOVERED' and lock.read_bytes() == lock_bytes and h.read_json(lease) == lease_value:
                if sealed_bytes is not None:
                    # Exact old lock/result/original bytes are archived above.
                    # This is resolution of proved actions, not a failed-lock bypass.
                    h.checked(lock).unlink()
                    report.update(outcome='ORIGINAL_OWNER_RESOLVED', ownerReleased=True)
                lease.unlink()  # This invocation's verified lease; old owner only on explicit proved release.
            h.save(out / 'result.json', report)
    h.save(out / 'audit.json', dict(root=str(ROOT), outputs=[h.record(h.checked(path)) for path in sorted(out.rglob('*'))
        if path.is_file()], selectedExternalWrites=[], originalLockPreserved=lock.exists() and lock.read_bytes() == lock_bytes,
        originalOwnerBytesArchived=(out / 'owner-lock.json').read_bytes() == lock_bytes,
        recoveryLeaseRetained=lease.exists(), privateAdb5093Listening=h.listening(p['phone']['adb_port'])))
    print(json.dumps(dict(outcome=report['outcome'], stage=report['stage'], stopAttempts=report['stopAttempts'],
        originalSmokeOutcome=result['outcome'], smokeReplayed=False, evidence=str(out.relative_to(ROOT)),
        formalAcceptance='NOT_ADJUDICATED')), flush=True)
    return 0 if report['outcome'] in {'ORIGINALS_RECOVERED', 'ORIGINAL_OWNER_RESOLVED'} else 1 if report['outcome'] == 'FAIL' else 2


def main(argv):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('mode', choices=('smoke', 'smoke-check', 'smoke-reconcile'))
    parser.add_argument('--plan', required=True, type=Path)
    parser.add_argument('--out', type=Path, help='fresh project-local evidence directory')
    parser.add_argument('--execute', action='store_true', help='authorized no-OTA UI/recording only')
    parser.add_argument('--prior', type=Path, help='exact failed owner output; reconciliation only')
    parser.add_argument('--sealed-original', type=Path,
        help='previously recovered sealed original; query-only reconciliation may archive/release proved old owner')
    parser.add_argument('--inspect-only', action='store_true', help='reconcile reads only; no ARM/STOP/launch/owner release')
    args = parser.parse_args(argv)
    r.require(Path.cwd() == ROOT and sys.flags.isolated and sys.flags.no_site and sys.dont_write_bytecode,
              'run from explicit worktree root with python -I -S -B -X utf8')
    r.require(args.plan.is_file() and args.plan.stat().st_size <= 65536, 'bounded configuration required')
    raw = args.plan.read_bytes()
    p = validate(r.strict_json(raw))
    r.require((args.mode == 'smoke-reconcile') == (args.prior is not None), 'prior output only for reconciliation')
    r.require(args.sealed_original is None or args.mode == 'smoke-reconcile', 'owner release only for reconciliation')
    r.require(not args.inspect_only or args.mode == 'smoke-reconcile', 'inspection only for reconciliation')
    if args.mode == 'smoke-check':
        r.require(not args.execute and args.out is None, 'smoke-check is offline/no outputs')
        print(json.dumps(dict(configuration='VALID', scenario='no-ota-smoke', deviceOperations=0)))
        return 0
    r.require(args.execute, 'smoke requires --execute for authorized launch/connect/record only')
    h = r.load_host()
    if args.mode == 'smoke-reconcile':
        r.require(args.out is not None, 'fresh reconciliation output required')
        return reconcile(p, raw, args.prior, args.out, h, sealed_original=args.sealed_original, inspect_only=args.inspect_only)
    out = preflight_outputs(h, args.out or ROOT / '.cache/p35-smoke' / p['run_id'])
    result = dict(outcome='NOT_RUN', automationOutcome='STOPPED', testOutcome='NOT_RUN',
        stage='inputs', formalAcceptance='NOT_ADJUDICATED',
        aiCalls=0, otaOperations=0, radioToggles=0, installOperations=0)
    driver = None
    h.save(out / 'plan.json', redacted_plan(p))
    h.save(out / 'inputs.json', dict(configurationSha256=hashlib.sha256(raw).hexdigest(),
        sources=[h.record(Path(__file__)), h.record(r.ROOT / 'Tools/ota/p35-automation/runner.py'),
                 h.record(Path(h.__file__)), h.record(r.ROOT / 'Tools/ota/p34-acceptance/live_phone.py')],
        evidencePrivacy='local private originals; do not publish raw USB/UI/JSONL receipts'))
    try:
        for pin in (p['phone']['adb'], p['phone']['adb_key']):
            h.pinned(pin)
        lock = h.checked(ROOT / '.cache/p34-live-device.lock')
        r.require(not h.checked(ROOT / '.cache/p35-reconcile-device.lock').exists(),
                  'outstanding recovery lease; reconcile before any new action', 'UNRESOLVED_STATE')
        if lock.exists():
            result['stage'] = 'reconcile-owner'
            # Reuse the existing owner liveness check and preserve its receipt.
            # Even a dead owner is not permission to discard its actual actions.
            previous = h.read_json(lock)
            h.save(out / 'prior-lock.json', previous)
            try:
                with h.device_owner(out, read_only=True):
                    prior_out = h.checked(previous['out'])
                    for name in ('result.json', 'usb/closed.json'):
                        path = h.checked(prior_out / name)
                        if path.is_file():
                            h.raw(out / 'previous-owner-results' / Path(name).name, path.read_bytes())
            except RuntimeError as error:
                raise r.Stop('UNRESOLVED_STATE', 'previous owner still running or liveness unconfirmed; no device command') from error
            raise r.Stop('UNRESOLVED_STATE', 'previous owner/action outcome requires reconciliation; lock unchanged')
        with h.device_owner(out):
            try:
                driver = Smoke(p, out, h)
                driver.start()
                driver.navigate()
                report = driver.record_smoke()
                r.require(report.get('integrity') == 'VERIFIED' and report.get('testOutcome') in {'PASS', 'FAIL'},
                          'missing original integrity/product verdict', 'EVIDENCE_GAP')
                defects = report.get('failures', [])
                result.update(outcome=report['testOutcome'], stage=defects[0]['stage'] if defects else 'complete',
                    code=defects[0]['code'] if defects else None,
                    reason='product assertions failed; see capture.failures' if defects else None, capture=report)
            except BaseException as error:
                result.update(failure(error, driver.stage if driver else 'startup'))
                result['executionError'] = dict(stage=result['stage'], code=result['code'], reason=result['reason'])
            finally:
                if driver:
                    cleanup = driver.cleanup()
                    result['cleanup'] = cleanup
                    if not cleanup['complete']:
                        result['executionOutcome'] = result['outcome']
                        result.update(outcome='FAIL', stage='cleanup', code='CLEANUP_FAILED', reason='see private cleanup receipts')
                        if cleanup['unresolved']:
                            result.update(outcome='BLOCKED', code='UNRESOLVED_STATE',
                                          reason='owned action/capture needs reconciliation; see private cleanup receipts')
                    elif cleanup['unresolved']:
                        result['executionOutcome'] = result['outcome']
                        result.update(outcome='BLOCKED', code='UNRESOLVED_STATE',
                                      reason='owned action/capture needs reconciliation; see private executionError')
                    if cleanup['unresolved'] or not cleanup['complete']:
                        raise r.Stop('UNRESOLVED_STATE', 'owned action/cleanup unresolved; device lock retained')
                    if 'capture' in result and cleanup.get('captureResolved') is True:
                        result['automationOutcome'] = 'COMPLETED'
    except BaseException as error:
        # A cleanup exception must override even an already-known product FAIL.
        if result['outcome'] in {'NOT_RUN', 'PASS'} or 'capture' in result and 'cleanup' not in result:
            result.update(failure(error, 'cleanup' if 'capture' in result else result['stage']))
        result['automationOutcome'] = 'STOPPED'
    result['lockRetained'] = (ROOT / '.cache/p34-live-device.lock').exists()
    if result['lockRetained']:
        result['automationOutcome'] = 'STOPPED'
    result['testOutcome'] = result['outcome']
    if not (out / 'result.json').exists():
        h.save(out / 'result.json', result)
    code = {'PASS': 0, 'FAIL': 1, 'BLOCKED': 2}[result['outcome']]
    # Console and shareable report contain no phone/MAC/key paths or raw errors.
    summary = dict(outcome=result['outcome'], automationOutcome=result['automationOutcome'],
        testOutcome=result['testOutcome'], stage=result['stage'], code=result.get('code'),
        exitCode=code, evidence=str(out.relative_to(ROOT)), formalAcceptance='NOT_ADJUDICATED')
    h.raw(out / 'report.txt', (json.dumps(summary, indent=2) + '\n').encode())
    h.save(out / 'audit.json', dict(root=str(ROOT), outputs=[h.record(h.checked(path)) for path in sorted(out.rglob('*'))
        if path.is_file()], selectedExternalWrites=[], externalKey='read-only, pinned',
        deviceWrites='test APP ordinary state/JSONL; explicitly configured idle test-App lifecycle only',
        lockPath='.cache/p34-live-device.lock', lockRetained=(ROOT / '.cache/p34-live-device.lock').exists()))
    print(json.dumps(summary), flush=True)
    return code
