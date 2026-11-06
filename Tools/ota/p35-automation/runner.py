"""P3-5 deterministic Release automation: no AI, screenshots or PC BLE sender."""
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
DIAGNOSTIC_PREFIX = 'OTA_P35_DIAGNOSTIC '
LINK_PREFIXES = ('OTA_LINK_SAMPLE ', 'OTA_LINK_STATS ', 'OTA_LINK_RETIRE ', 'OTA_LINK_LATE ',
                 'OTA_LINK_ACK_IGNORED ', 'OTA_LINK_ACK_ERROR ')
PRIVATE_DIAGNOSTIC = re.compile(r'https?://|[?&][^\s=]+='
    r'|(?:token|authorization|secret|password|api[_-]?key)[\"\s]*[:=]', re.I)
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
        if isinstance(raw, bytes):
            raw = raw.decode('utf-8')
        return json.loads(raw, object_pairs_hook=pairs,
            parse_constant=lambda _: require(False, 'non-finite JSON', 'EVIDENCE_GAP'))
    except (ValueError, UnicodeError) as error:
        raise Stop('EVIDENCE_GAP', 'invalid UTF-8/JSON') from error


def audit_logcat_status(raw, capture_id, archive):
    value = strict_json(raw)
    common = {'schema', 'captureId', 'source', 'status'}
    require(isinstance(value, dict) and type(value.get('schema')) is int and value['schema'] == 1 and
            value.get('captureId') == capture_id and value.get('source') == 'diagnostic-only',
            'unbound native mirror status', 'EVIDENCE_GAP')
    if value.get('status') == 'NO_NATIVE_ERROR_OBSERVED':
        require(set(value) == common, 'invalid native mirror summary', 'EVIDENCE_GAP')
    else:
        require(value.get('status') == 'FAILED_DISABLED' and set(value) == common | {
            'errorType', 'nativeResult', 'expectedBytes', 'record', 'recordSha256'} and
            isinstance(value['errorType'], str) and bool(value['errorType']) and
            isinstance(value['record'], str), 'invalid native mirror failure', 'EVIDENCE_GAP')
        require((type(value['nativeResult']) is int and type(value['expectedBytes']) is int and value['expectedBytes'] > 0)
                or value['nativeResult'] is None and value['expectedBytes'] is None,
                'invalid native mirror return', 'EVIDENCE_GAP')
        line = value['record'].encode('utf-8')
        if value['nativeResult'] is not None:
            require(value['expectedBytes'] == len(line) + 9 and value['nativeResult'] != value['expectedBytes'],
                    'native mirror return does not describe this failed write', 'EVIDENCE_GAP')
        require(line in archive.splitlines() and hashlib.sha256(line).hexdigest() == value['recordSha256'],
                'native mirror rejection is not bound to the original', 'EVIDENCE_GAP')
    return value


def audit_logcat_mirror(raw, capture_id, states, status, *, original=None):
    """Audit optional text rendering without treating it as the primary stream.

    Android's events text renderer can truncate a successfully stored binary
    string. Preserve every malformed line's location/hash; never reconstruct it
    from the complete, independently validated App/ACK-stream original.
    """
    reference = states
    if original is not None:
        decoder = Decoder()
        require(decoder.feed(original) == states, 'mirror reference states differ from original', 'EVIDENCE_GAP')
        reference = sorted(states + decoder.diagnostics, key=lambda x: x['seq'])
    by_seq = {x['seq']: x for x in reference}
    observed, errors = [], []
    reference_complete = True
    for number, line in enumerate(raw.splitlines(), 1):
        diagnostic = line.find(DIAGNOSTIC_PREFIX.encode()) >= 0
        prefix = DIAGNOSTIC_PREFIX if diagnostic else PREFIX
        marker = line.find(prefix.encode())
        if original is None and (diagnostic or b'OTA_P35_CAPTURE ' in line and b'ota-link-v1' in line):
            reference_complete = False
        if marker < 0:
            continue
        try:
            row = (validate_diagnostic if diagnostic else validate_state)(strict_json(line[marker + len(prefix):]))
        except Stop as error:
            errors.append(dict(line=number, bytes=len(line), sha256=hashlib.sha256(line).hexdigest(),
                               code=error.code, detail=str(error)))
            continue
        if row['captureId'] == capture_id:
            observed.append(row)
    reference_complete = reference_complete and [x['seq'] for x in reference] == list(range(1, len(reference) + 1))
    return dict(source='diagnostic-only', captureId=capture_id, records=len(observed), originalRecords=len(reference),
        rawBytes=len(raw), rawSha256=hashlib.sha256(raw).hexdigest(), parseErrors=errors,
        missingSequences=sorted(set(by_seq)-{x['seq'] for x in observed}), referenceComplete=reference_complete,
        retainedMatch=reference_complete and all(by_seq.get(x['seq']) == x for x in observed),
        exactEquality=reference_complete and not errors and observed == reference, nativeMirror=status, usedForInjection=False)


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


def load_smoke():
    sys.path.insert(0, str(Path(__file__).resolve().parent))
    sys.modules.setdefault('runner', sys.modules[__name__])
    import smoke
    require(smoke.ROOT == ROOT, 'preparation loaded from another worktree')
    return smoke


def selector(value):
    require(isinstance(value, dict) and set(value) <= {'resource-id', 'text', 'content-desc', 'class'}
            and bool(value), 'selector must use native accessibility fields')
    require(all(isinstance(v, str) and 0 < len(v) <= 160 for v in value.values()), 'invalid selector value')
    return value


def validate_plan(p, *, single=False, scenarios=False):
    require(isinstance(p, dict) and type(p.get('schema')) is int and p['schema'] == 1, 'plan schema must be 1')
    require(not (single and scenarios) and (p.get('test_profile') in {'resume-once', 'background-lock'}
            if scenarios else p.get('test_profile') == ('single-upgrade' if single else None)),
            'test profile requires its explicit development entry')
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
    stream_port = p['preparation'].get('live_stream_port') if isinstance(p.get('preparation'), dict) else None
    arm_id = 'p35-arm-stream' if stream_port is not None else 'p35-arm'
    if stream_port is not None and ui['arm'] == {'resource-id': 'p51-arm-timing'}:
        arm_id = 'p51-arm-timing'
    require(ui['arm'] == {'resource-id': arm_id} and ui['stop'] == {'resource-id': 'p35-stop'},
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
    prep = p.get('preparation', {})
    require(isinstance(prep, dict) and set(prep) <= {'display_name', 'command_seconds',
        'cleanup_seconds', 'restart_closed_recorder', 'startup_log_tag', 'radio_state_reader',
        'capture_failure_buffer', 'log_buffer', 'live_stream_port', 'logcat_binary'}, 'preparation fields')
    require(type(prep.get('logcat_binary', False)) is bool and (not prep.get('logcat_binary') or
            stream_port is not None and prep.get('log_buffer') == 'events'),
            'binary diagnostic requires the acknowledged primary and events buffer')
    if stream_port is not None:
        require(type(stream_port) is int and 1024 <= stream_port <= 65535 and
                stream_port not in (5037, phone['adb_port']) and app['id'].endswith('.p35acceptance') and
                prep.get('log_buffer') == 'events', 'explicit test-only live stream binding required')
    require(type(prep.get('capture_failure_buffer', False)) is bool, 'capture failure buffer opt-in must be boolean')
    require(prep.get('log_buffer', 'main') in ('main', 'events'), 'unsupported telemetry log buffer')
    require(prep.get('log_buffer') != 'events' or 'startup_log_tag' not in prep,
            'structured events must not change text logging policy')
    require(prep.get('radio_state_reader') in (None, 'vivo-pd2312-sdk33-getState-v1'),
            'unqualified radio-state reader profile')
    require(isinstance(prep.get('display_name', ''), str) and len(prep.get('display_name', '')) <= 128,
            'optional exact advertised name')
    require(type(prep.get('restart_closed_recorder', False)) is bool, 'explicit recorder lifecycle permission')
    if 'startup_log_tag' in prep:
        logging = prep['startup_log_tag']
        require(isinstance(logging, dict) and {'before', 'during', 'seconds'} <= set(logging) <=
                {'before', 'during', 'seconds', 'allow_info_baseline'} and
                logging['before'] == 'M' and logging['during'] == 'V' and
                type(logging.get('allow_info_baseline', False)) is bool and
                type(logging['seconds']) is int and 60 <= logging['seconds'] <= 300,
                'only the explicitly qualified bounded M-to-V startup logging policy is supported')
    for key, default, lo, hi in [('command_seconds', 30, 5, 60), ('cleanup_seconds', 60, 20, 90)]:
        value = prep.get(key, default)
        require(type(value) in (int, float) and math.isfinite(value) and lo <= value <= hi,
                'preparation limit: ' + key)
    cases = p.get('cases')
    if scenarios:
        require(stream_port is not None, 'scenario coverage requires the acknowledged live stream')
        if p['test_profile'] == 'background-lock':
            require(cases == [] and p.get('allow_bluetooth_toggle') is False and
                    p.get('allow_display_control') is True,
                    'background-lock requires explicit display scope and forbids radio cuts')
            return p
        require(p.get('allow_bluetooth_toggle') is True and p.get('allow_display_control', False) is False,
                'resume-once requires adapter scope, not display mutations')
    if single:
        require(cases == [] and p.get('allow_bluetooth_toggle') is False,
                'single upgrade forbids disconnect cases and adapter mutation')
        return p
    require(isinstance(cases, list) and len(cases) == (1 if scenarios else 10),
            'exactly one development cut or ten formal disconnect events required')
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
    if scenarios:
        require(cases[0]['durable_min'] >= 4096 and cases[0]['durable_max'] < size // 2,
                'resume-once requires a positive durable prefix before the package midpoint')
        return p
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
    require(isinstance(s, dict) and type(s.get('schema')) is int and s['schema'] in (1, 2) and
            set(s) == STATE_KEYS | ({'runtime'} if s['schema'] == 2 else set()),
            'missing/unknown Release telemetry fields', 'EVIDENCE_GAP')
    if s['schema'] == 2:
        runtime = s['runtime']
        require(isinstance(runtime, dict) and set(runtime) == {'backgrounded', 'acquired', 'reason',
                'active', 'paused', 'ownerEpoch', 'revision', 'task'}, 'runtime fields', 'EVIDENCE_GAP')
        require(all(type(runtime[k]) is bool for k in ('backgrounded', 'acquired', 'active', 'paused')) and
                all(uint(runtime[k], 2**63-1) for k in ('ownerEpoch', 'revision')) and
                (runtime['reason'] is None or isinstance(runtime['reason'], str) and len(runtime['reason']) <= 256),
                'runtime domains', 'EVIDENCE_GAP')
        task = runtime['task']
        require(task is None or isinstance(task, dict) and set(task) == {
                'taskId', 'generation', 'deviceToken', 'packageSha256'} and
                isinstance(task['taskId'], str) and 0 < len(task['taskId']) <= 128 and
                uint(task['generation'], 2**63-1) and digest(task['deviceToken']) and digest(task['packageSha256']),
                'runtime task binding', 'EVIDENCE_GAP')
        require(not runtime['acquired'] or runtime['active'] and task is not None and
                task['generation'] == runtime['ownerEpoch'], 'acquired runtime has no current owner', 'EVIDENCE_GAP')
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


def validate_diagnostic(s):
    keys = {'schema', 'captureId', 'seq', 'monoUs', 'statsId', 'clockId', 'ownerEpoch',
            'ownerStateSeq', 'label', 'attempt', 'line'}
    require(isinstance(s, dict) and set(s) == keys and type(s['schema']) is int and s['schema'] == 1,
            'diagnostic fields', 'EVIDENCE_GAP')
    require(isinstance(s['captureId'], str) and re.fullmatch('[0-9a-f]{32}', s['captureId']) and
            all(uint(s[k], 2**63-1) for k in ('seq', 'monoUs', 'statsId', 'ownerEpoch', 'ownerStateSeq')) and
            s['statsId'] > 0 and 0 < s['ownerStateSeq'] < s['seq'] and
            s['clockId'] == '%s:%s' % (s['captureId'], s['statsId']), 'diagnostic clock/owner', 'EVIDENCE_GAP')
    require(s['label'] in ('upgrade', 'probe', 'query', 'prefix-probe') and
            (s['attempt'] is None or uint(s['attempt']) and s['attempt'] > 0), 'diagnostic instance', 'EVIDENCE_GAP')
    line = s['line']
    require(isinstance(line, str) and line.startswith(LINK_PREFIXES) and '\n' not in line and '\r' not in line
            and not PRIVATE_DIAGNOSTIC.search(line), 'unsafe/unknown diagnostic line', 'EVIDENCE_GAP')
    if line.startswith(('OTA_LINK_STATS ', 'OTA_LINK_ACK_IGNORED ')):
        value = strict_json(line.split(' ', 1)[1])
        require(value.get('label') == s['label'] and value.get('attempt') == s['attempt'],
                'diagnostic source instance differs', 'EVIDENCE_GAP')
        if line.startswith('OTA_LINK_STATS '):
            require(value.get('clock') == 'stopwatch-mono-us', 'diagnostic source clock differs', 'EVIDENCE_GAP')
    else:
        require(line.split(' ', 2)[1] == 'label=' + s['label'], 'diagnostic source label differs', 'EVIDENCE_GAP')
    return s


def valid_capture_header(value, capture_id):
    return isinstance(value, dict) and type(value.get('schema')) is int and (
        value == dict(schema=1, kind='open', captureId=capture_id) or
        value == dict(schema=2, kind='open', captureId=capture_id, diagnostics='ota-link-v1'))


class Decoder:
    """Incremental parser; no partial line, old PID, dropped sequence or invented state."""
    def __init__(self):
        self.pending = b''
        self.previous = None
        self.opened = None
        self.closed = None
        self.previous_record = None
        self.diagnostics = []
        self.state_owners = {}
        self.instances = {}

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
                require(isinstance(capture, dict), 'invalid capture receipt', 'EVIDENCE_GAP')
                if capture.get('kind') == 'open':
                    require(self.opened is None and self.previous is None and self.closed is None,
                            'replayed capture header', 'EVIDENCE_GAP')
                    require(valid_capture_header(capture, capture.get('captureId')), 'unknown capture schema', 'EVIDENCE_GAP')
                    self.opened = capture
                if capture.get('kind') == 'close':
                    require(self.closed is None, 'replayed capture footer', 'EVIDENCE_GAP')
                    self.closed = capture
            diagnostic_start = row.find(DIAGNOSTIC_PREFIX.encode())
            start = diagnostic_start if diagnostic_start >= 0 else row.find(PREFIX.encode())
            if start < 0:
                continue
            require(self.closed is None, 'state after capture footer', 'EVIDENCE_GAP')
            is_diagnostic = diagnostic_start >= 0
            prefix = DIAGNOSTIC_PREFIX if is_diagnostic else PREFIX
            s = (validate_diagnostic if is_diagnostic else validate_state)(strict_json(row[start + len(prefix):]))
            if self.previous_record is not None:
                require(s['captureId'] == self.previous_record['captureId'] and
                        s['seq'] == self.previous_record['seq'] + 1 and s['monoUs'] >= self.previous_record['monoUs'],
                        'lost/replayed/reordered producer records: expected seq %s, received %s' %
                        (self.previous_record['seq'] + 1, s['seq']), 'EVIDENCE_GAP')
            if self.opened is not None:
                require(s['captureId'] == self.opened['captureId'] and
                        (self.previous_record is not None or s['seq'] == 1), 'capture header binding', 'EVIDENCE_GAP')
            self.previous_record = s
            if is_diagnostic:
                require(self.opened is not None and self.opened['schema'] == 2, 'unannounced diagnostic', 'EVIDENCE_GAP')
                require(self.state_owners.get(s['ownerStateSeq']) == s['ownerEpoch'], 'diagnostic owner anchor differs', 'EVIDENCE_GAP')
                identity = tuple(s[k] for k in ('clockId', 'ownerEpoch', 'ownerStateSeq', 'label', 'attempt'))
                require(self.instances.setdefault(s['statsId'], identity) == identity, 'diagnostic instance drift', 'EVIDENCE_GAP')
                self.diagnostics.append(s)
                continue
            require(self.previous is None or s['schema'] == self.previous['schema'], 'state schema changed', 'EVIDENCE_GAP')
            if s['schema'] == 2:
                self.state_owners[s['seq']] = s['runtime']['ownerEpoch']
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
    require(valid_capture_header(header, capture_id),
            'wrong App capture header', 'EVIDENCE_GAP')
    require(set(footer) == {'schema', 'kind', 'captureId', 'records', 'sha256', 'healthy', 'lost', 'error'} and
            type(footer['schema']) is int and footer['schema'] == header['schema'] and footer['kind'] == 'close' and footer['captureId'] == capture_id and
            footer['healthy'] is True and type(footer['lost']) is int and footer['lost'] == 0 and footer['error'] is None,
            'unhealthy App capture footer', 'EVIDENCE_GAP')
    states_raw = b''.join(rows[1:-1])
    prefixes = (PREFIX.encode(), DIAGNOSTIC_PREFIX.encode()) if header['schema'] == 2 else (PREFIX.encode(),)
    require(all(row.startswith(prefixes) for row in rows[1:-1]), 'unexpected persisted record', 'EVIDENCE_GAP')
    decoder = Decoder()
    states = decoder.feed(raw)
    count = len(states) + len(decoder.diagnostics)
    require(states and states[0]['seq'] == 1 and all(s['captureId'] == capture_id for s in states) and
            type(footer['records']) is int and count == footer['records'] and
            footer['sha256'] == hashlib.sha256(states_raw).hexdigest(), 'App capture count/hash/sequence mismatch', 'EVIDENCE_GAP')
    result = dict(captureId=capture_id, records=count, sha256=hashlib.sha256(raw).hexdigest(),
                  final=states[-1], integrity='VERIFIED', formalAcceptance='NOT_ADJUDICATED')
    if header['schema'] == 2:
        result.update(stateRecords=len(states), diagnosticRecords=len(decoder.diagnostics))
    return result


def audit_link_diagnostics(raw, capture_id):
    """Return real raw lines grouped by their source clock, never a P34 snapshot."""
    archive = audit_capture(raw, capture_id)
    decoder = Decoder()
    decoder.feed(raw)
    require(decoder.diagnostics, 'no acknowledged link diagnostics', 'EVIDENCE_GAP')
    sys.path.insert(0, str(ROOT / 'Tools/ota/p3-4-link-stats'))
    from acceptance_stats import rank
    groups = {}
    for row in decoder.diagnostics:
        group = groups.setdefault(row['statsId'], dict(clockId=row['clockId'], ownerEpoch=row['ownerEpoch'],
            label=row['label'], attempt=row['attempt'], lines=[]))
        group['lines'].append(row['line'])
    for group in groups.values():
        summaries = [strict_json(line[len('OTA_LINK_STATS '):]) for line in group['lines'] if line.startswith('OTA_LINK_STATS ')]
        require(len(summaries) == 1, 'missing/duplicate source summary', 'EVIDENCE_GAP')
        summary = summaries[0]
        sends, repeats, acks = [], [], []
        for line in group['lines']:
            match = re.fullmatch(r'OTA_LINK_SAMPLE label=\S+ kind=(segment_first_send|segment_retransmit|ack_latency) us=(-?\d+) off=(\d+)(?: len=(\d+))?', line)
            if match:
                (sends if match[1] == 'segment_first_send' else repeats if match[1] == 'segment_retransmit' else acks).append((int(match[3]), int(match[2])))
        transfer = summary.get('transfer')
        require(isinstance(transfer, dict) and {'segmentsUnique', 'segmentSendTotal', 'retransmitFrames',
                'outcome', 'ackSamples', 'ackEarlyInvalid', 'ackLatency'} <= transfer.keys() and
                all(uint(transfer[k], 2**63-1) for k in ('segmentsUnique', 'segmentSendTotal', 'retransmitFrames', 'ackEarlyInvalid')) and
                isinstance(transfer['ackLatency'], dict) and uint(transfer['ackLatency'].get('count'), 2**63-1),
                'missing/invalid source transfer summary', 'EVIDENCE_GAP')
        require(len(sends) == len({off for off, _ in sends}) == transfer['segmentsUnique'] and
                len(sends) + len(repeats) == transfer['segmentSendTotal'] and
                len(repeats) == transfer['retransmitFrames'] and len(acks) == transfer['ackLatency']['count'] and
                len(acks) == len({off for off, _ in acks}) and all(us >= 0 for _, us in sends + repeats + acks),
                'diagnostic samples disagree with source summary', 'EVIDENCE_GAP')
        require({off for off, _ in acks + repeats} <= {off for off, _ in sends},
                'ACK/retry belongs to another source clock', 'EVIDENCE_GAP')
        latencies = [us for _, us in acks]
        expected = dict(count=len(latencies), minUs=min(latencies) if latencies else None,
            p50Us=rank(latencies, 50), p95Us=rank(latencies, 95), p99Us=rank(latencies, 99),
            maxUs=max(latencies) if latencies else None)
        require(transfer['ackLatency'] == expected and all(v is None or uint(v, 2**63-1)
                for v in transfer['ackLatency'].values()), 'raw ACK distribution differs from source summary', 'EVIDENCE_GAP')
        if transfer['outcome'] == 'ok':
            require(transfer['ackSamples'] == 'complete' and transfer['ackEarlyInvalid'] == 0 and
                    len(acks) == len(sends), 'completed source has missing/invalid ACK samples', 'EVIDENCE_GAP')
        group.update(summary=summary, ackLatencyUs=latencies)
    return dict(archive=archive, groups=list(groups.values()), format='p35-original-link-lines-v1',
                physicalAcceptance='NOT_ADJUDICATED')


def foreground_ok(raw, package):
    """Use the live full-dump sections, never the nested LAST ANR snapshot."""
    try:
        text = raw.decode('utf-8')
    except UnicodeError:
        return False
    if not text.endswith('\n'):
        return False
    headings = list(re.finditer(r'(?m)^WINDOW MANAGER [^\r\n]*\(dumpsys window ([a-z]+)\):?\r?$', text))
    policies = [i for i, m in enumerate(headings) if m[1] == 'policy']
    if len(policies) != 1:
        return False
    live = headings[policies[0]:]
    # These root sections bound the current policy and every current display.
    # A historical DISPLAY heading alone is not an observation boundary.
    if [m[1] for m in live[:7]] != ['policy', 'animator', 'sessions', 'displays', 'tokens', 'windows', 'trace']:
        return False
    if len({m[1] for m in live}) != len(live):
        return False
    current = text[live[0].start():]
    if re.search(r'\b(?:mShowingLockscreen|mDreamingLockscreen|mKeyguardShowing|isStatusBarKeyguard|isKeyguardShowing)=true\b', current):
        return False
    displays = text[live[3].end():live[4].start()]
    values = re.findall(r'(?m)^\s*mCurrentFocus=([^\r\n]+)', displays)
    values = [v.strip() for v in values if v.strip() != 'null']
    return len(values) == 1 and re.fullmatch(r'Window\{[0-9a-f]+ u0 ' +
        re.escape(package) + r'/[A-Za-z0-9_.$]+\}', values[0]) is not None


def hierarchy(xml):
    require(len(xml) <= 2 * 1024 * 1024 and b'<!' not in xml,
            'unsafe/oversize UI hierarchy', 'UI_UNAVAILABLE')
    begin, end = xml.find(b'<hierarchy'), xml.rfind(b'</hierarchy>')
    require(begin >= 0 and end >= begin, 'native hierarchy unavailable', 'UI_UNAVAILABLE')
    try:
        return ET.fromstring(xml[begin:end + len(b'</hierarchy>')])
    except ET.ParseError as error:
        raise Stop('UI_UNAVAILABLE', 'malformed native hierarchy') from error


def idle_equivalent(left, right):
    # Same origin as foreground_ok. Layout bounds are not business state.
    def normalized(raw):
        tree = hierarchy(raw)
        for node in tree.iter('node'):
            node.attrib.pop('bounds', None)
        return ET.tostring(tree)
    return normalized(left) == normalized(right)


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
    def __init__(self, plan, driver, clock=time.monotonic, *, single=False, scenarios=False):
        self.p, self.io, self.clock = validate_plan(plan, single=single, scenarios=scenarios), driver, clock
        self.deadline = clock() + plan['limits']['total_seconds']
        self.state, self.cases = None, []
        self.active_case, self.stage = None, 'initial-idle'
        self.progress, self.progress_at = None, clock()

    def case_results(self, *, complete=False, error_code=None):
        observed = {case['id'] for case in self.cases}
        result = []
        for case in self.p['cases']:
            row = dict(id=case['id'], outcome='NOT_RUN')
            if case['id'] in observed:
                row['outcome'] = 'PASS' if complete else 'RECOVERY_OBSERVED'
            elif case['id'] == self.active_case:
                row.update(outcome='FAIL', stage=self.stage, code=error_code)
            result.append(row)
        return result

    def wait(self, predicate, stage, seconds=None, *, allow_failure=False):
        self.stage = stage
        if hasattr(self.io, 'enter_stage'):
            self.io.enter_stage(stage, seconds or self.p['limits']['stage_seconds'])
        deadline = min(self.deadline, self.clock() + (seconds or self.p['limits']['stage_seconds']))
        while self.clock() < deadline:
            state = self.io.next_state(min(self.p['limits']['event_seconds'], deadline - self.clock()))
            validate_state(state)
            scenario = getattr(self.io, 'scenario', None)
            if scenario is not None:
                scenario.observe(state)
                scenario.healthy()
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
                if hasattr(self.io, 'confirm_action'):
                    self.io.confirm_action()
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
            self.active_case = case['id']
            def at_boundary(s):
                bound(s, self.p, package=True)
                require(s['phase'] == 'transferring' and s['durable'] <= case['durable_max'],
                        'missed planned disconnect boundary: ' + case['id'], 'EVIDENCE_GAP')
                return s['linkConnected'] and case_matches(s, case)
            before = self.wait(at_boundary, case['id'] + '-boundary')
            self.io.record('disconnect-intent', case=case['id'], state=before)
            try:
                self.stage = case['id'] + '-radio-off'
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
            self.active_case = None
        coverage = None
        final = None
        if self.p.get('test_profile') == 'background-lock':
            import scenarios
            self.io.scenario = scenarios.Background(self)
            coverage = self.io.scenario.run()
            final = self.io.scenario.final
        if final is None:
            final = self.wait(lambda s: s['phase'] == 'completed' and s['event'] == 'identity', 'post-reboot-identity')
        bound(final, self.p, package=True, final=True)
        require(final['freshConnection'] and final['linkConnected'] and final['durable'] == self.p['firmware']['package']['bytes'],
                'END/UI completion is not fresh final identity', 'EVIDENCE_GAP')
        return dict(outcome='AUTOMATION_COMPLETED', recovered=len(self.cases), final=final,
                    formalAcceptance='NOT_ADJUDICATED', cases=self.cases, scenarioCoverage=coverage)


RADIO_MANAGER = ('shell', 'dumpsys', 'bluetooth_manager')
RADIO_ADAPTER = ('shell', 'dumpsys', 'activity', 'service',
                 'com.android.bluetooth/.btservice.AdapterService', '--print')
RADIO_BINDER = ('shell', 'service', 'call', 'bluetooth_manager', '8')
RADIO_FRAMEWORK = '/system/framework/framework.jar'
RADIO_FRAMEWORK_SHA256 = '3614bbb0ff5717fe1946ebe95d569ae06c9d8c07b0f9ad49b65e716ebc87a4ab'
RADIO_FINGERPRINT = 'vivo/PD2312/PD2312:13/TP1A.220624.014/compiler06251531:user/release-keys'


def parse_radio_parcel(raw):
    # The pinned ROM's getState() has no arguments and returns exception=0, int.
    # Never infer OFF from a missing service, exception, boolean or command exit.
    require(isinstance(raw, bytes) and len(raw) <= 256, 'invalid radio-state parcel', 'CAPABILITY_MISSING')
    match = re.fullmatch(rb"Result: Parcel\(00000000 (0000000[a-f]|00000010) +'\.{8}'\)\r?\n?", raw)
    require(match is not None, 'unqualified radio-state parcel', 'CAPABILITY_MISSING')
    value = int(match[1], 16)
    return {10: False, 12: True}.get(value)


def parse_radio_state(raw, source):
    require(isinstance(raw, bytes) and len(raw) <= 1024 * 1024,
            'missing/oversized Bluetooth state dump', 'CAPABILITY_MISSING')
    try:
        text = raw.decode('utf-8')
    except UnicodeError:
        raise Stop('CAPABILITY_MISSING', 'invalid Bluetooth state encoding') from None
    require('\x00' not in text, 'malformed Bluetooth state dump', 'CAPABILITY_MISSING')
    require(source in {'manager', 'adapter'}, 'unknown Bluetooth state reader', 'CAPABILITY_MISSING')
    header, field = ('Bluetooth Status', 'state') if source == 'manager' else ('AdapterProperties', 'State')
    lines = text.splitlines()
    sections = [(index, len(line) - len(line.lstrip(' '))) for index, line in enumerate(lines)
                if line.strip() == header]
    if source == 'adapter' and not sections and re.fullmatch(
            r'SERVICE com\.android\.bluetooth/\.btservice\.AdapterService [0-9a-f]+ '
            r'pid=[1-9][0-9]* user=0\r?\n  Client:\r?\n(?:\r?\n)*', text):
        # Android can keep the service envelope while its client is changing.
        # This is unavailable state, not OFF; the existing transition bound applies.
        return None
    if source == 'manager' and not sections:
        # Retain the original standalone manager format, never a profile-only dump.
        block = [line for line in lines if line.strip()]
        require(len(block) == 1, 'unqualified Bluetooth manager dump', 'CAPABILITY_MISSING')
    else:
        require(len(sections) == 1, 'missing/ambiguous Bluetooth state section', 'CAPABILITY_MISSING')
        index, indent = sections[0]
        block = []
        for line in lines[index + 1:]:
            if not line.strip():
                continue
            depth = len(line) - len(line.lstrip(' '))
            if depth <= indent:
                break
            if depth == indent + 2:
                block.append(line)
    values = [match for line in block
              if (match := re.fullmatch(r' *' + field + r': *(.*)', line))]
    require(len(values) == 1, 'missing/ambiguous Bluetooth state field', 'CAPABILITY_MISSING')
    require('\t' not in values[0].group(0), 'malformed Bluetooth state field', 'CAPABILITY_MISSING')
    value = values[0].group(1).strip()
    require(value in {'ON', 'OFF', 'TURNING_ON', 'TURNING_OFF', 'BLE_ON',
                      'BLE_TURNING_ON', 'BLE_TURNING_OFF'},
            'unknown Bluetooth adapter state', 'CAPABILITY_MISSING')
    # Turning and BLE-only states do not confirm either requested full-radio state.
    return {'ON': True, 'OFF': False}.get(value)


class Android:
    """Thin standard adb/uiautomator adapter; logcat writes independently of polling."""
    def __init__(self, p, out, h, automatic=False):
        self.p, self.out, self.h = p, out, h
        self.preparation = None
        self.cleanup_result = None
        self.final_verified = False
        if automatic:
            smoke = load_smoke()
            require(smoke.MAC.fullmatch(p['firmware']['device_address']) and p['app']['id'].endswith('.p35acceptance'),
                    'automatic campaign requires exact lowercase MAC and side-by-side test package')
            options = p.get('preparation', {})
            prep_plan = dict(run_id=p['run_id'], phone=p['phone'], app=p['app'],
                device=dict(address=p['firmware']['device_address'], display_name=options.get('display_name', ''),
                    expected_version=p['firmware']['current']['version'], expected_sha256=p['firmware']['current']['sha256']),
                lifecycle=dict(restart_closed_recorder=options.get('restart_closed_recorder', False)),
                limits=dict(total_seconds=p['limits']['total_seconds'], stage_seconds=p['limits']['stage_seconds'],
                    command_seconds=options.get('command_seconds', 30), event_seconds=p['limits']['event_seconds'],
                    cleanup_seconds=options.get('cleanup_seconds', 60)))
            self.preparation = smoke.Smoke(prep_plan, out, h)
            self.preparation.observation_source = 'logcat'
            self.env, self.base = self.preparation.phone.env, self.preparation.phone.base
        else:
            self.env = h.environment(out, p['phone']['adb_key'])
            self.base = [str(h.pinned(p['phone']['adb'])), '-H', '127.0.0.1', '-P',
                         str(p['phone']['adb_port']), '-s', p['phone']['serial']]
        self.server = self.capture = None
        self.stream_capture = None
        self.stream_port = p.get('preparation', {}).get('live_stream_port')
        self.stream_forwarded = False
        self.pid = self.initial_radio = None
        self.radio_touched = False
        self.restore_attempted = False
        self.radio_state_source = None
        self.sequence, self.offset, self.journal_seq = 0, 0, 0
        self.decoder, self.queue = Decoder(), deque()
        self.total_deadline = time.monotonic() + p['limits']['total_seconds'] + p.get('preparation', {}).get('cleanup_seconds', 60)
        self.last_ui = None
        self.last_state_at = None
        self.campaign = None
        self.product_result = None
        self.state_sink = None
        self.scenario = None
        self.transfer_start_attempted = False
        self.log_tag_touched = False
        self.log_tag_restore_attempted = False
        self.log_tag_started = self.log_tag_saved_deadlines = None
        if self.preparation:
            self.preparation.decoder = self.decoder
            self.preparation.pump = self.pump
            self.preparation.check_cleanup_state = self.check_cleanup_state

    def enter_stage(self, stage, seconds):
        if self.preparation:
            self.preparation.enter(stage)
            self.preparation.stage_deadline = min(self.preparation.total, time.monotonic() + seconds)
            self.preparation.phone.operation_deadline = self.preparation.stage_deadline

    def confirm_action(self):
        if self.preparation:
            self.preparation.mutation_unknown = False

    def check_cleanup_state(self, state):
        history = getattr(self.preparation, 'capture_recovery_states', None) or self.preparation.live
        if state['phase'] == 'readyToInstall':
            require(not getattr(self, 'transfer_start_attempted', True) and self.preparation.live and
                    all(s['phase'] in {'idle', 'checkingUpdate', 'downloading', 'verifyingDownload', 'readyToInstall'} and
                        s['protocol'] is None and s['bitmap'] is None and s['session'] == s['durable'] == 0 and
                        s['sendOffset'] is None and s['event'] not in {'beginAck', 'data', 'endAck'}
                        for s in history),
                    'transfer intent/history prevents pre-BEGIN cleanup', 'UNRESOLVED_STATE')
            bound(state, self.p, package=True)
            return
        require(state['phase'] in {'idle', 'completed', 'failed'},
                'transfer/apply/reboot outcome unresolved; preserve owner', 'UNRESOLVED_STATE')
        if not self.final_verified:
            require(not any(row['phase'] in {'applying', 'waitingReboot', 'reconnectVerify', 'completed'}
                    or row['packageBytes'] > 0 and row['durable'] == row['packageBytes']
                    for row in history),
                    'post-transfer device outcome unknown; no App stop or replay', 'UNRESOLVED_STATE')
        bound(state, self.p, final=self.final_verified)

    def arm_baseline(self):
        prep = self.preparation
        prep.enter('capture-start')
        prep.idle_recorder_ui()
        require(prep.capture_names() == set(prep.previous_captures), 'capture store changed before ARM', 'UNRESOLVED_STATE')
        for cid, pin in prep.previous_captures.items():
            raw = prep.original(cid, self.out / 'arm-baseline' / (cid + '.jsonl'))
            require(hashlib.sha256(raw).hexdigest() == pin['sha256'], 'old original changed before ARM', 'EVIDENCE_GAP')
        prep.arm_baseline_confirmed = True
        prep.record('arm-baseline', pid=prep.pid, captures=prep.previous_captures)

    def prepare_startup_logging(self):
        policy = self.p.get('preparation', {}).get('startup_log_tag')
        if policy is None:
            return
        prep = self.preparation
        require(prep is not None and not self.log_tag_touched and self.log_tag_started is None,
                'startup logging owner is single-use')
        require(not prep.cmd(['shell', 'pidof', self.p['app']['id']], success_codes=(0, 1)).strip(),
                'startup logging requires an absent test process', 'UNRESOLVED_STATE')
        before = self.cmd(['shell', 'getprop', 'log.tag'], seconds=5).decode('utf-8', 'strict').strip()
        if before == 'I' and policy.get('allow_info_baseline', False):
            # INFO already passed real reader/original qualification. No write
            # means no property restoration ownership; live readiness still gates OTA.
            self.record('startup-log-tag-not-needed', observed=before, propertyWrites=0)
            return
        require(before == policy['before'], 'global log.tag baseline changed; not overwritten', 'UNRESOLVED_STATE')
        self.record('startup-log-tag-intent', property='log.tag', before=before, during=policy['during'],
                    maxSeconds=policy['seconds'])
        self.log_tag_started = time.monotonic()
        self.log_tag_saved_deadlines = (prep.total, self.total_deadline)
        # Reserve restoration commands plus their bounded owned-process closure.
        work_end = self.log_tag_started + policy['seconds'] - 45
        prep.total, self.total_deadline = min(prep.total, work_end), min(self.total_deadline, work_end)
        prep.stage_deadline = min(prep.stage_deadline, work_end)
        prep.phone.operation_deadline = prep.stage_deadline
        self.log_tag_touched = True
        self.cmd(['shell', 'setprop', 'log.tag', policy['during']], seconds=5)
        require(self.cmd(['shell', 'getprop', 'log.tag'], seconds=5).decode('utf-8', 'strict').strip() == policy['during'],
                'global log.tag configuration readback failed', 'UNRESOLVED_STATE')
        self.record('startup-log-tag-configured', beforeLaunch=True)

    def restore_startup_logging(self):
        if not getattr(self, 'log_tag_touched', False):
            return
        require(not self.log_tag_restore_attempted, 'startup logging restoration unresolved; no replay', 'UNRESOLVED_STATE')
        self.log_tag_restore_attempted = True
        policy, prep = self.p['preparation']['startup_log_tag'], self.preparation
        old_operation_deadline = prep.phone.operation_deadline
        prep.phone.operation_deadline = None
        try:
            current = self.cmd(['shell', 'getprop', 'log.tag'], seconds=5).decode('utf-8', 'strict').strip()
            require(current in (policy['before'], policy['during']), 'foreign global log.tag change; not overwritten', 'UNRESOLVED_STATE')
            if current == policy['during']:
                self.cmd(['shell', 'setprop', 'log.tag', policy['before']], seconds=5)
            require(self.cmd(['shell', 'getprop', 'log.tag'], seconds=5).decode('utf-8', 'strict').strip() == policy['before'],
                    'global log.tag restoration unconfirmed', 'UNRESOLVED_STATE')
            self.log_tag_touched = False
            elapsed = time.monotonic() - self.log_tag_started
            self.record('startup-log-tag-restored', value=policy['before'], elapsedSeconds=elapsed)
            require(elapsed <= policy['seconds'], 'startup logging duration exceeded its bound', 'TIMEOUT')
        finally:
            prep.total, self.total_deadline = self.log_tag_saved_deadlines
            prep.phone.operation_deadline = old_operation_deadline

    def finish_startup_logging(self):
        if not getattr(self, 'log_tag_touched', False):
            return
        self.restore_startup_logging()
        self.enter_stage('startup-log-tag-restored-readiness', self.p['limits']['stage_seconds'])
        self.pump()
        boundary = self.decoder.previous['seq']
        self.queue.clear()
        end = min(self.total_deadline, time.monotonic() + self.p['limits']['event_seconds'])
        fresh = []
        while len(fresh) < 2:
            remaining = end - time.monotonic()
            require(remaining > 0, 'no continuing telemetry after startup logging restoration', 'CAPABILITY_MISSING')
            state = self.next_state(remaining)
            bound(state, self.p)
            require(state['phase'] == 'idle' and state['seq'] > boundary and state['packageBytes'] == 0,
                    'unexpected state after logging restoration', 'UNRESOLVED_STATE')
            fresh.append(state['seq'])
        self.queue.appendleft(state)
        self.record('startup-log-tag-restored-readiness', boundarySeq=boundary, freshSeqs=fresh)

    def fresh_identity(self):
        self.enter_stage('fresh-identity', self.p['limits']['stage_seconds'])
        self.pump()
        previous = self.decoder.previous['seq']
        self.tap({'resource-id': 'p35-reconnect'})
        deadline = min(self.total_deadline, time.monotonic() + self.p['limits']['stage_seconds'])
        while time.monotonic() < deadline:
            self.pump()
            fresh = load_smoke().latest_identity(self.preparation.live, previous)
            if fresh and self.decoder.previous['freshConnection']:
                bound(fresh, self.p)
                bound(self.decoder.previous, self.p)
                require(fresh['phase'] == 'idle' and fresh['freshConnection'] and fresh['linkConnected'],
                        'fresh starting identity unavailable', 'IDENTITY_MISMATCH')
                self.confirm_action()
                self.queue.clear()
                self.queue.append(fresh)
                self.record('identity-query-observed', seq=fresh['seq'])
                self.finish_startup_logging()
                return
            time.sleep(.02)
        raise Stop('IDENTITY_MISMATCH', 'no query-bound current identity; no OTA start')

    def no_update(self):
        self.final_verified = True
        self.tap(self.p['ui']['check'])
        queried = self.campaign.wait(lambda s: s['phase'] == 'checkingUpdate', 'post-upgrade-latest-start')
        bound(queried, self.p, final=True)
        empty = self.campaign.wait(lambda s: s['phase'] == 'idle' and s['targetVersionCode'] == 0,
                                   'post-upgrade-no-update')
        bound(empty, self.p, final=True)
        require(empty['freshConnection'] and empty['linkConnected'] and empty['targetImageSha256'] is None
                and empty['releaseId'] is None and empty['packageSha256'] is None
                and empty['packageBytes'] == 0 and not empty['packageVerified']
                and empty['latestUrl'] == self.p['firmware']['latest_url'], 'latest did not prove no update', 'EVIDENCE_GAP')
        # The installed service clears these fields only after a parsed NO_UPDATE.
        require(load_smoke().has_label(self.ui(), self.p['app']['id'], '\u6682\u65e0\u53ef\u7528\u66f4\u65b0'),
                'no-update service result missing from native page', 'EVIDENCE_GAP')
        return dict(outcome='NO_UPDATE', seq=empty['seq'], currentVersionCode=empty['currentVersionCode'])

    def record(self, event, **fields):
        if self.preparation:
            return self.preparation.record(event, **fields)
        self.journal_seq += 1
        self.h.save(self.out / 'journal' / ('%05d.json' % self.journal_seq),
                    dict(event=event, hostMonoNs=time.monotonic_ns(), **fields))

    def cmd(self, args, seconds=15):
        if self.preparation:
            return self.preparation.phone.cmd(args, seconds=seconds)
        import shlex
        require(self.server and self.server.alive() and self.h.listening(self.p['phone']['adb_port']),
                'private ADB owner unavailable', 'COLLECTOR_FAILED')
        require(time.monotonic() + seconds < self.total_deadline, 'command exceeds campaign deadline')
        self.sequence += 1
        if args[0] in ('shell', 'exec-out'):
            args = [args[0], ' '.join(shlex.quote(str(x)) for x in args[1:])]
        return self.h.command(self.out / 'commands', 'adb-%05d' % self.sequence,
                              self.base + args, self.env, seconds=seconds)

    def logcat_command(self):
        if self.p.get('preparation', {}).get('logcat_binary'):
            # The old adb logcat shortcut applies shell CR conversion to binary.
            return self.base + ['exec-out', 'logcat', '-B', '-b', 'events', '--pid=' + self.pid, '-T', '1']
        buffer = ['-b', 'events'] if self.p.get('preparation', {}).get('log_buffer') == 'events' else []
        return self.base + ['logcat', *buffer, '-v', 'epoch', '--pid=' + self.pid, '-T', '1', '*:V']

    def prepare_live_stream(self):
        if self.stream_port is None:
            return
        require(self.preparation is not None and not self.h.listening(self.stream_port),
                'stream requires automatic owned test App and an unused local port', 'ENV_BLOCKED')
        import live_stream
        self.record('stream-forward-intent', localPort=self.stream_port, remotePort=live_stream.REMOTE_PORT)
        self.cmd(['forward', '--no-rebind', 'tcp:' + str(self.stream_port), 'tcp:' + str(live_stream.REMOTE_PORT)])
        self.stream_forwarded = True
        expected = '%s tcp:%d tcp:%d' % (self.p['phone']['serial'], self.stream_port, live_stream.REMOTE_PORT)
        require(expected in self.cmd(['forward', '--list']).decode().splitlines(), 'forward binding mismatch', 'ENV_BLOCKED')
        self.preparation.observation_source = 'acknowledged-stream-v1'

    def start_live_stream(self, *, idle_seconds=5):
        require(self.stream_forwarded and self.stream_capture is None, 'stream is single use', 'ENV_BLOCKED')
        require(type(idle_seconds) is int and 1 <= idle_seconds <= 180, 'invalid stream idle timeout', 'ENV_BLOCKED')
        self.stream_capture = self.h.Process(self.out, 'live-stream',
            [sys.executable, '-I', '-S', '-B', '-u', '-X', 'utf8',
             str(ROOT / 'Tools/ota/p35-automation/live_stream.py'), '--port', str(self.stream_port),
             '--wire-out', str(self.h.checked(self.out / 'live-stream.wire')),
             '--idle-seconds', str(idle_seconds)], self.env)
        self.offset = 0
        require(self.stream_capture.alive(), 'live stream receiver failed to start', 'COLLECTOR_FAILED')

    def startup(self, *, retrieval_only=False):
        if self.preparation:
            if self.p.get('preparation', {}).get('startup_log_tag') is not None:
                self.preparation.start_phone()
                self.preparation.old_captures()
                self.prepare_startup_logging()
                self.preparation.launch()
            else:
                self.preparation.start()
            self.preparation.navigate()
            self.preparation.prepare_recorder()
            self.pid, self.server = self.preparation.pid, self.preparation.phone.server
            self.initial_radio = self.radio_state()
            require(self.initial_radio is True, 'Bluetooth must initially be on')
            self.capture = self.h.Process(self.out, 'logcat', self.logcat_command(), self.env)
            self.preparation.logcat = self.capture
            time.sleep(.2)
            require(self.capture.alive(), 'logcat did not start', 'COLLECTOR_FAILED')
            self.offset = self.capture.paths['stdout'].stat().st_size
            self.record('capture-started', pid=self.pid, screenshots=False, source='shared-phone-logcat')
            self.prepare_live_stream()
            return
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
        self.capture = self.h.Process(self.out, 'logcat', self.logcat_command(), self.env)
        # Discard pre-readiness buffered lines. A fresh producer heartbeat must follow.
        time.sleep(.2)
        require(self.capture.alive(), 'logcat did not start', 'COLLECTOR_FAILED')
        self.offset = self.capture.paths['stdout'].stat().st_size
        self.record('capture-started', pid=pid, apkSha256=actual, screenshots=False)

    def pump(self):
        try:
            return self._pump_logcat()
        except (Stop, OSError):
            if getattr(self, 'preparation', None):
                self.preparation.stream_failed = True
            raise

    def _pump_logcat(self):
        require(self.capture and self.capture.alive() and self.server.alive(), 'collector/ADB stopped; no action replay', 'COLLECTOR_FAILED')
        selected = self.capture
        if getattr(self, 'stream_port', None) is not None:
            if self.stream_capture is None:
                return  # No producer/ARM yet, never use diagnostic logcat as fallback.
            selected = self.stream_capture
        path = selected.paths['stdout']
        size = path.stat().st_size
        require(self.offset <= size <= 256 * 1024 * 1024 and size - self.offset <= 1024 * 1024,
                'capture truncated, oversized or control consumer fell behind', 'EVIDENCE_GAP')
        with path.open('rb') as stream:
            stream.seek(self.offset)
            data = stream.read()
        self.offset += len(data)
        states = self.decoder.feed(data)
        require(selected.alive() or self.decoder.closed is not None and selected.process.poll() == 0,
                'live stream ended without a verified close frame', 'COLLECTOR_FAILED')
        require(all(s['deviceAddress'] == self.p['firmware']['device_address'] for s in states),
                'App switched target during capture; no further UI/radio actions', 'IDENTITY_MISMATCH')
        if states:
            self.last_state_at = time.monotonic()
            if self.preparation:
                prep = self.preparation
                expected = dict(schema=1, kind='open', captureId=states[0]['captureId'])
                if self.p['ui']['arm'] == {'resource-id': 'p51-arm-timing'}:
                    expected.update(schema=2, diagnostics='ota-link-v1')
                require(prep.arm_attempted and self.decoder.opened == expected
                        and (prep.live or states[0]['seq'] == 1), 'unowned campaign recording', 'EVIDENCE_GAP')
                require(states[0]['captureId'] not in prep.previous_captures, 'replayed old capture', 'EVIDENCE_GAP')
                prep.capture_id = states[0]['captureId']
                prep.capture_state = 'ACTIVE'
                prep.live.extend(states)
        if getattr(self, 'state_sink', None):
            for state in states:
                self.state_sink(state)
        else:
            self.queue.extend(states)
        require(len(self.queue) <= 1000, 'event backlog; refusing late injection', 'EVIDENCE_GAP')

    def next_state(self, seconds):
        deadline = min(time.monotonic() + seconds, self.total_deadline)
        while time.monotonic() < deadline:
            self.pump()
            if self.queue:
                return self.queue.popleft()
            time.sleep(.02)
        raise Stop('CAPABILITY_MISSING', 'no fresh Release logcat telemetry; preserve App original; no file-polling injection fallback')

    def ui(self):
        if self.preparation:
            return self.preparation.ui()
        require(self.cmd(['shell', 'pidof', self.p['app']['id']]).strip().decode() == self.pid,
                'App process changed', 'EVIDENCE_GAP')
        focus = self.cmd(['shell', 'dumpsys', 'window'])
        require(foreground_ok(focus, self.p['app']['id']),
                'target App not unobscured foreground; no permission-dialog auto-approval', 'UI_UNAVAILABLE')
        self.last_ui = self.cmd(['exec-out', 'uiautomator', 'dump', '--compressed', '/dev/tty'])
        return self.last_ui

    def tap(self, wanted, *, bootstrap=False):
        arm_id = 'p35-arm-stream' if getattr(self, 'stream_port', None) is not None else 'p35-arm'
        if getattr(self, 'stream_port', None) is not None and getattr(self, 'p', {}).get('ui', {}).get('arm') == {'resource-id': 'p51-arm-timing'}:
            arm_id = 'p51-arm-timing'
        require(not bootstrap or wanted == {'resource-id': arm_id},
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
                viewport = load_smoke().scroll_viewport(xml, self.p['app']['id'])
                require(viewport is not None, 'no unique native scroll viewport', 'UI_UNAVAILABLE')
                x1, y1, x2, y2 = viewport
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
        if wanted in (self.p['ui']['start'], self.p['ui']['resume']):
            self.transfer_start_attempted = True
        if self.preparation:
            self.preparation.mutation_unknown = True
            if bootstrap:
                self.preparation.arm_attempted = True
                self.preparation.arm_action_count = 1
            if wanted == self.p['ui']['stop']:
                self.preparation.stop_attempted = True
        if bootstrap and getattr(self, 'stream_port', None) is not None:
            self.start_live_stream()
        self.cmd(['shell', 'input', 'tap', str(point[0]), str(point[1])], seconds=5)
        self.record('tap-command-returned', selector=wanted)

    def retrieve(self, capture_id):
        require(isinstance(capture_id, str) and re.fullmatch('[0-9a-f]{32}', capture_id), 'explicit capture ID required')
        if self.preparation:
            raw = self.preparation.original(capture_id, self.out / 'app-capture.jsonl')
            report = audit_capture(raw, capture_id)
            original_decoder = Decoder()
            states = original_decoder.feed(raw)
            require(states == self.preparation.live, 'live/App original sequence differs', 'EVIDENCE_GAP')
            if original_decoder.opened['schema'] == 2:
                require(original_decoder.diagnostics == self.decoder.diagnostics,
                        'live/App original diagnostics differ', 'EVIDENCE_GAP')
            self.preparation.capture_seal = load_smoke().sealed_file(raw, capture_id)
            self.preparation.capture_resolved = True
            self.preparation.capture_state = 'SEALED'
            self.confirm_action()
            self.h.save(self.out / 'app-capture-integrity.json', report)
            if self.stream_port is not None:
                remote = '/sdcard/Android/data/' + self.p['app']['id'] + '/files/p35-logcat-diagnostics/' + capture_id + '.json'
                diagnostic = self.cmd(['exec-out', 'cat', remote], seconds=5)
                self.h.raw(self.out / 'logcat-native-status.json', diagnostic)
                status = audit_logcat_status(diagnostic, capture_id, raw)
                wire = self.capture.paths['stdout'].read_bytes()
                rendered = wire
                binary = self.p.get('preparation', {}).get('logcat_binary', False)
                if binary:
                    import logcat_binary
                    self.h.raw(self.out / 'logcat-live-snapshot.bin', wire)
                    terminal = self.cmd(['exec-out', 'logcat', '-B', '-d', '-b', 'events', '--pid=' + self.pid], seconds=10)
                    self.h.raw(self.out / 'logcat-terminal.bin', terminal)
                    mirror, rendered, end = logcat_binary.audit_pair(wire, terminal, int(self.pid), capture_id, raw, states, status)
                    self.h.raw(self.out / 'logcat-decoded.jsonl', rendered)
                    self.h.raw(self.out / 'logcat-terminal-decoded.jsonl', end)
                else:
                    mirror = audit_logcat_mirror(rendered, capture_id, states, status, original=raw)
                    mirror.update(wireFormat='text', wireBytes=len(wire), wireSha256=hashlib.sha256(wire).hexdigest())
                self.h.save(self.out / 'logcat-diagnostic-integrity.json', mirror)
            return report
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

    def radio_state(self, seconds=5):
        require(type(seconds) in (int, float) and math.isfinite(seconds) and 0 < seconds <= 5,
                'finite Bluetooth state-read timeout required', 'ENV_BLOCKED')
        deadline = time.monotonic() + seconds

        def read(command):
            remaining = deadline - time.monotonic()
            require(remaining > 0, 'Bluetooth state-read deadline', 'ENV_BLOCKED')
            raw = self.cmd(list(command), seconds=remaining)
            require(time.monotonic() < deadline, 'Bluetooth state-read deadline', 'ENV_BLOCKED')
            return raw

        profile = self.p.get('preparation', {}).get('radio_state_reader')
        if profile == 'vivo-pd2312-sdk33-getState-v1':
            if not getattr(self, 'radio_getter_verified', False):
                fingerprint = read(('shell', 'getprop', 'ro.build.fingerprint')).strip()
                require(fingerprint == RADIO_FINGERPRINT.encode(), 'radio reader ROM changed', 'CAPABILITY_MISSING')
                checksum = read(('shell', 'sha256sum', RADIO_FRAMEWORK)).split()
                require(checksum == [RADIO_FRAMEWORK_SHA256.encode(), RADIO_FRAMEWORK.encode()],
                        'radio reader framework changed; no Binder call', 'CAPABILITY_MISSING')
                self.radio_getter_verified = True
                self.record('radio-reader-verified', profile=profile, frameworkSha256=RADIO_FRAMEWORK_SHA256,
                            method='IBluetoothManager.getState', transaction=8)
            return parse_radio_parcel(read(RADIO_BINDER))

        source = getattr(self, 'radio_state_source', None)
        if source is None:
            raw = read(RADIO_MANAGER)
            source = 'adapter' if not raw.strip() else 'manager'
            self.radio_state_source = source
            if source == 'adapter':
                raw = read(RADIO_ADAPTER)
        else:
            raw = read(RADIO_MANAGER if source == 'manager' else RADIO_ADAPTER)
        return parse_radio_state(raw, source)

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
            if self.radio_state(seconds=min(5, deadline - time.monotonic())) is enabled:
                self.record('radio-state-observed', enabled=enabled)
                if enabled:
                    self.radio_touched = False
                return
            time.sleep(min(.05, max(0, deadline - time.monotonic())))
        raise Stop('ENV_BLOCKED', 'Bluetooth command did not reach requested state: ' + ('ON' if enabled else 'OFF'))

    def capture_failure_buffer(self):
        """One diagnostic snapshot after radio restoration; never a live fallback."""
        prep = self.preparation
        if (not self.p.get('preparation', {}).get('capture_failure_buffer', False) or not prep or
                not prep.capture_id or getattr(self, 'failure_buffer_attempted', False)):
            return
        self.failure_buffer_attempted = True
        deadline = time.monotonic() + 15
        buffer = self.p.get('preparation', {}).get('log_buffer', 'main')
        result = dict(captureId=prep.capture_id, pid=self.pid, buffer=buffer, usedForReadiness=False, files={})
        commands = [
            ('buffer', ['logcat', '-d', '-b', buffer, '-v', 'epoch', '--pid=' + self.pid, '*:V']),
            ('log-tag', ['shell', 'getprop', 'log.tag']),
            ('rate-limit', ['shell', 'getprop', 'persist.log.ratelimit']),
        ]
        try:
            require(self.cmd(['shell', 'pidof', self.p['app']['id']], seconds=5).strip().decode() == self.pid,
                    'failure snapshot PID changed', 'IDENTITY_MISMATCH')
            for name, command in commands:
                remaining = deadline - time.monotonic()
                require(remaining > 0, 'failure snapshot deadline', 'TIMEOUT')
                raw = self.cmd(command, seconds=min(5, remaining))
                result['files'][name] = self.h.raw(self.out / 'failure-buffer' / (name + '.raw'), raw)
            result['outcome'] = 'DIAGNOSTIC_ONLY'
        except Exception as error:
            result.update(outcome='DIAGNOSTIC_FAILED', code=getattr(error, 'code', 'HOST_FAILED'), detail=str(error))
        self.h.save(self.out / 'failure-buffer' / 'result.json', result)

    def close(self):
        errors = []
        logging_errors = []
        if getattr(self, 'scenario', None):
            try:
                self.scenario.restore()
            except Exception as error:
                errors.append('display restoration: ' + str(error))
        try:
            self.restore_startup_logging()
        except Exception as error:
            logging_errors.append(str(error))
        if self.preparation:
            self.preparation.stage_deadline = time.monotonic() + self.preparation.p['limits']['cleanup_seconds']
            self.preparation.phone.operation_deadline = self.preparation.stage_deadline
        if self.radio_touched:
            if self.restore_attempted:
                errors.append('radio restoration unresolved after its bounded attempt')
            else:
                try:
                    self.radio(True)
                except Exception as error:
                    errors.append('radio restoration: ' + str(error))
        if self.preparation:
            prefix_error = None
            buffer_error = None
            prep = self.preparation
            if not self.final_verified or prep.stream_failed:
                try:
                    self.capture_failure_buffer()
                except Exception as error:
                    buffer_error = str(error)
            unsafe = prep.stream_failed or prep.mutation_unknown
            if prep.capture_id and self.decoder.previous:
                try:
                    self.check_cleanup_state(self.decoder.previous)
                except Stop:
                    unsafe = True
            if unsafe and prep.capture_id and self.decoder.closed is None:
                try:
                    prep.prefix(prep.capture_id, self.out / 'failed-original-prefix.jsonl')
                except Exception as error:
                    prefix_error = str(error)
            try:
                self.cleanup_result = self.preparation.cleanup()
            finally:
                if getattr(self, 'stream_capture', None) is not None:
                    try:
                        self.stream_capture.close('p35-stream-finished')
                    except Exception as error:
                        errors.append('owned stream close: ' + str(error))
                if getattr(self, 'stream_forwarded', False) and self.h.listening(self.stream_port):
                    errors.append('owned stream forward still listening')
            self.cleanup_result['radioErrors'] = errors
            self.cleanup_result['startupLoggingErrors'] = logging_errors
            self.cleanup_result['prefixPreservationError'] = prefix_error
            self.cleanup_result['bufferPreservationError'] = buffer_error
            require(self.cleanup_result['complete'] and not self.cleanup_result['unresolved'] and not errors and not logging_errors,
                    'shared campaign action/cleanup unresolved; retain device lock', 'UNRESOLVED_STATE')
            return
        for process in [self.capture, self.server]:
            if process:
                try:
                    process.close('p35-owner-finished')
                except Exception as error:
                    errors.append('owned process: ' + str(error))
        require(not self.h.listening(self.p['phone']['adb_port']), 'private ADB still listening', 'CLEANUP_FAILED')
        require(not errors, '; '.join(errors), 'CLEANUP_FAILED')


def main(argv=None):
    argv = sys.argv[1:] if argv is None else argv
    if argv and argv[0] in {'pipeline', 'pipeline-check', 'pipeline-recover'}:
        sys.path.insert(0, str(Path(__file__).resolve().parent))
        sys.modules['runner'] = sys.modules[__name__]
        import pipeline
        return pipeline.main(argv)
    if argv and argv[0] in {'smoke', 'smoke-check', 'smoke-reconcile'}:
        sys.path.insert(0, str(Path(__file__).resolve().parent))
        # The terminal entry is __main__; share its Stop/decoder types rather
        # than importing a second copy when the thin adapter imports runner.
        sys.modules['runner'] = sys.modules[__name__]
        import smoke
        try:
            return smoke.main(argv)
        except (Stop, OSError, ValueError) as error:
            print(json.dumps(dict(outcome='BLOCKED', stage='configuration',
                code=getattr(error, 'code', 'INPUT_ERROR'), reason='invalid input/output boundary; no device action',
                formalAcceptance='NOT_ADJUDICATED')), file=sys.stderr)
            return 2
    parser = argparse.ArgumentParser(description=__doc__,
        epilog='No-OTA entry: runner.py smoke --plan CONFIG --execute; offline: smoke-check --plan CONFIG')
    parser.add_argument('mode', choices=['check', 'probe', 'run', 'retrieve', 'audit', 'audit-timing'])
    parser.add_argument('--plan', type=Path)
    parser.add_argument('--archive', type=Path, help='offline audit of an unchanged App JSONL file')
    parser.add_argument('--out', type=Path)
    parser.add_argument('--execute', action='store_true', help='required for UI/radio mutations; not formal acceptance authorization')
    profiles = parser.add_mutually_exclusive_group()
    profiles.add_argument('--single-upgrade', action='store_true', help='development-only single upgrade, no injected disconnects')
    profiles.add_argument('--scenario-coverage', action='store_true', help='explicit resume-once or background-lock development scenario')
    parser.add_argument('--capture-id', help='retrieve unchanged App originals after USB recovery; no UI or OTA replay')
    args = parser.parse_args(argv)
    require(Path.cwd() == ROOT and sys.flags.isolated and sys.flags.no_site and sys.dont_write_bytecode,
            'run from active root with python -I -S -B -X utf8')
    if args.mode in ('audit', 'audit-timing'):
        require(args.archive is not None and args.capture_id is not None and args.plan is None and
                args.out is None and not args.execute and not args.single_upgrade and not args.scenario_coverage,
                'audit is read-only and requires archive and capture ID')
        require(args.archive.stat().st_size <= 128 * 1024 * 1024 + 8192, 'oversized App original', 'EVIDENCE_GAP')
        check = audit_link_diagnostics if args.mode == 'audit-timing' else audit_capture
        print(json.dumps(check(args.archive.read_bytes(), args.capture_id)))
        return 0
    require(args.plan is not None and args.archive is None, 'plan required; archive only for offline audit')
    configuration = args.plan.read_bytes()
    p = validate_plan(strict_json(configuration), single=args.single_upgrade, scenarios=args.scenario_coverage)
    if args.mode == 'check':
        require(not args.execute and args.out is None, 'check is offline/no outputs')
        print(json.dumps(dict(plan='VALID', cases=len(p['cases']), deviceOperations=0, liveQualification='NOT_RUN')))
        return 0
    require(args.out is not None and (args.mode != 'run' or args.execute), 'explicit output and --execute required')
    if args.mode == 'run' and p['cases']:
        require(p.get('allow_bluetooth_toggle') is True, 'explicit device/adapter injection authorization required before startup')
    require(args.mode == 'run' or not args.execute, 'read-only mode never accepts --execute')
    require(args.mode != 'probe' or p.get('preparation', {}).get('live_stream_port') is None,
            'acknowledged stream requires explicit owned recording, not the legacy read-only probe')
    require((args.mode == 'retrieve') == (args.capture_id is not None), 'capture ID only for retrieval')
    if args.capture_id is not None:
        require(re.fullmatch('[0-9a-f]{32}', args.capture_id), 'invalid capture ID')
    h = load_host()
    out = h.checked(args.out)
    require(not out.exists(), 'existing/uncertain run directory; do not replay')
    if args.mode == 'run':
        load_smoke().preflight_outputs(h, out)
        h.checked(out / 'failed-original-prefix.jsonl')
    for name in ['plan.json', 'inputs.json', 'result.json', 'journal', 'commands', 'adb-server.stdout', 'adb-server.stderr',
                 'adb-server.started.json', 'adb-server.closed.json', 'logcat.stdout', 'logcat.stderr',
                 'logcat.started.json', 'logcat.closed.json', 'host', 'app-capture.jsonl', 'app-capture-integrity.json',
                 'previous-owner.stdout', 'previous-owner.stderr', 'previous-owner.started.json',
                 'previous-owner.closed.json', 'unresolved-owner.json', 'failure-buffer',
                 'live-stream.stdout', 'live-stream.stderr', 'live-stream.started.json', 'live-stream.closed.json',
                 'live-stream.wire', 'logcat-diagnostic-integrity.json', 'logcat-native-status.json', 'logcat-decoded.jsonl',
                 'logcat-terminal.bin', 'logcat-terminal-decoded.jsonl', 'logcat-live-snapshot.bin']:
        h.checked(out / name)
    for pin in [p['phone']['adb'], p['phone']['adb_key'], p['firmware']['package']]:
        h.pinned(pin)
    h.raw(out / 'plan.json', configuration)
    h.save(out / 'inputs.json', dict(mode=args.mode,
        singleUpgrade=args.single_upgrade,
        scenarioCoverage=args.scenario_coverage,
        planSha256=hashlib.sha256(configuration).hexdigest(),
        runner=h.record(Path(__file__)), hostHelper=h.record(Path(h.__file__)),
        liveStreamHelper=h.record(ROOT / 'Tools/ota/p35-automation/live_stream.py') if p.get('preparation', {}).get('live_stream_port') else None,
        binaryLogcatHelper=h.record(ROOT / 'Tools/ota/p35-automation/logcat_binary.py') if p.get('preparation', {}).get('logcat_binary') else None,
        formalAcceptance=False))
    result = dict(outcome='NOT_RUN', formalAcceptance='NOT_ADJUDICATED', recovered=0)
    driver = None
    try:
        lock = h.checked(ROOT / '.cache/p34-live-device.lock')
        if args.mode == 'run' and lock.exists():
            h.raw(out / 'prior-lock.json', lock.read_bytes())
            raise Stop('UNRESOLVED_STATE', 'existing device owner/action requires reconciliation; no replay')
        with h.device_owner(out, read_only=args.mode in {'probe', 'retrieve'}):
            require(not h.checked(ROOT / '.cache/p35-reconcile-device.lock').exists(),
                    'unresolved recovery lease; no device action', 'UNRESOLVED_STATE')
            driver = Android(p, out, h, args.mode == 'run')
            try:
                driver.startup(retrieval_only=args.mode == 'retrieve')
                if args.mode == 'retrieve':
                    result.update(outcome='ORIGINALS_RETRIEVED', archive=driver.retrieve(args.capture_id))
                else:
                    result.update(execute_ui(args.mode, p, driver))
            except Exception as error:
                result['executionError'] = dict(code=getattr(error, 'code', 'HOST_FAILED'), detail=str(error))
                result['verifiedStages'] = getattr(driver, 'product_result', None)
                result.update(outcome=getattr(error, 'code', 'HOST_FAILED'), detail=str(error),
                    recovered=len(driver.campaign.cases) if driver.campaign else 0, preserveOriginals=True, replay=False)
            finally:
                driver.close()
    except Exception as error:
        result.update(outcome=getattr(error, 'code', 'HOST_FAILED'), detail=str(error),
                      recovered=len(driver.campaign.cases) if driver and driver.campaign else 0,
                      preserveOriginals=True, replay=False)
    if args.mode == 'run':
        campaign = driver.campaign if driver else None
        background = p.get('test_profile') == 'background-lock'
        result.update(planned=len(p['cases']), semantics=p['test_profile'] if args.scenario_coverage else
            'single-upgrade-no-injection' if args.single_upgrade else 'one-upgrade-ten-disconnect-events',
            plannedCoverage=dict(foregroundUpgrade=True, adapterDisconnectResume=bool(p['cases']),
                disconnectWindows=len(p['cases']), background=background, screenLock=background,
                processDeathRecovery=False, rfImpairment=False, physicalPowerLoss=False),
            telemetrySource='acknowledged-stream-v1' if p.get('preparation', {}).get('live_stream_port') else 'logcat',
            cases=campaign.cases if campaign else [],
            caseResults=campaign.case_results(complete=result['outcome'] == 'AUTOMATION_COMPLETED',
                error_code=result.get('executionError', {}).get('code', result['outcome'])) if campaign else
                [dict(id=case['id'], outcome='NOT_RUN') for case in p['cases']])
        result['cleanup'] = getattr(driver, 'cleanup_result', None) if driver else None
        result['lockRetained'] = (ROOT / '.cache/p34-live-device.lock').exists()
    h.save(out / 'result.json', result)
    print(json.dumps({k: result[k] for k in ('outcome', 'recovered', 'planned', 'caseResults', 'lockRetained', 'formalAcceptance')
                      if k in result}))
    return 0 if result['outcome'] in {'PROBE_READY', 'AUTOMATION_COMPLETED', 'ORIGINALS_RETRIEVED'} else 2


def execute_ui(mode, p, driver):
    if mode == 'run':
        single = p.get('test_profile') == 'single-upgrade'
        validate_plan(p, single=single, scenarios=p.get('test_profile') in {'resume-once', 'background-lock'})
        require(not p['cases'] or p.get('allow_bluetooth_toggle') is True, 'explicit adapter-toggle scope required')
        if getattr(driver, 'preparation', None):
            driver.arm_baseline()
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
    if getattr(driver, 'preparation', None):
        driver.fresh_identity()
    if p.get('test_profile') in {'resume-once', 'background-lock'}:
        require(state['schema'] == 2, 'scenario profile requires actual runtime telemetry schema 2', 'CAPABILITY_MISSING')
    if p.get('test_profile') == 'background-lock':
        import scenarios
        scenarios.preflight(driver)
    driver.campaign = Campaign(p, driver, single=p.get('test_profile') == 'single-upgrade',
        scenarios=p.get('test_profile') in {'resume-once', 'background-lock'})
    result = driver.campaign.run()
    driver.product_result = result
    if getattr(driver, 'preparation', None):
        result['noUpdate'] = driver.no_update()
    result['archive'] = driver.finish_capture()
    return result


if __name__ == '__main__':
    try:
        raise SystemExit(main())
    except (Stop, OSError) as error:
        print(json.dumps(dict(outcome=getattr(error, 'code', 'INPUT_ERROR'), detail=str(error))), file=sys.stderr)
        raise SystemExit(2)
