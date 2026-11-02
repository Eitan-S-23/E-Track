"""Test-only adapter for the existing Access/CSRF/channel CAS API."""
import copy
import hashlib
import http.client
import json
import os
import ssl
import time
from urllib.parse import urlencode, urlsplit

from runner import require, strict_json

ADMIN = 'https://e-track-firmware-p43-admin-test.pages.dev'
PUBLIC = 'https://e-track-firmware-p41-public.pages.dev'
CHANNELS = '/api/admin/firmware/channels?appId=trace&deviceModel=e-track-at32f435'
RELEASES = '/api/admin/firmware/releases?appId=trace&deviceModel=e-track-at32f435'


class Cloud:
    def __init__(self, config, out, host):
        self.config, self.out, self.h = config, out, host
        self.auth, self.csrf = {}, None
        self.number = 0

    def request(self, origin, route, body=None):
        require(origin in (ADMIN, PUBLIC) and route.startswith('/api/'), 'test API only')
        require(body is None or origin == ADMIN, 'no public mutation')
        self.number += 1
        label = 'http-%04d' % self.number
        self.h.save(self.out / (label + '-intent.json'), dict(origin=origin,
            route=route, method='GET' if body is None else 'POST', body=body))
        headers = {'Accept': 'application/json', 'User-Agent': 'E-Track-P35/1.0'}
        if origin == ADMIN:
            headers.update(self.auth)
        payload = None
        if body is not None:
            headers.update(Origin=ADMIN, **{'X-CSRF-Token': self.csrf,
                                          'Content-Type': 'application/json'})
            payload = json.dumps(body).encode()
        # No redirects, proxy discovery, cookies on the public endpoint, or retries.
        context = ssl.SSLContext(ssl.PROTOCOL_TLS_CLIENT)
        context.load_default_certs()  # Unlike create_default_context, ignores SSLKEYLOGFILE.
        connection = http.client.HTTPSConnection(urlsplit(origin).hostname, timeout=25, context=context)
        deadline = time.monotonic() + 30
        try:
            connection.request('GET' if body is None else 'POST', route, payload, headers)
            response = connection.getresponse()
            chunks, size = [], 0
            while True:
                require(time.monotonic() < deadline, 'API response deadline')
                chunk = response.read1(65536)
                if not chunk:
                    break
                size += len(chunk)
                require(size <= 4 * 1024 * 1024, 'oversized API response')
                chunks.append(chunk)
            raw = b''.join(chunks)
            self.h.save(self.out / (label + '-received.json'), dict(status=response.status,
                bytes=len(raw), sha256=hashlib.sha256(raw).hexdigest()))
            require(response.status == 200, 'test API HTTP %s; no automatic retry' % response.status)
            value = strict_json(raw)
            safe = copy.deepcopy(value)
            if route == '/api/admin/session':
                safe = {k: value.get(k) for k in ('ok', 'role', 'appId', 'environment')}
            if isinstance(safe.get('asset'), dict):
                safe['asset'].pop('downloadUrl', None)
            self.h.save(self.out / (label + '-response.json'), dict(status=response.status,
                bytes=len(raw), sha256=hashlib.sha256(raw).hexdigest(), data=safe))
            return value, response.getheaders()
        finally:
            connection.close()

    def login(self):
        token = os.environ.get('P35_ACCESS_TOKEN', '')
        require(token and not any(c.isspace() or c == ';' for c in token), 'P35_ACCESS_TOKEN required')
        self.auth = {'Cookie': 'CF_Authorization=' + token}
        session, headers = self.request(ADMIN, '/api/admin/session')
        require(session.get('ok') is True and session.get('environment') == 'staging'
                and session.get('appId') == 'trace' and session.get('role') == 'owner', 'test owner session required')
        require(hashlib.sha256(session['actor'].lower().encode()).hexdigest() == self.config['actor_sha256'],
                'unexpected test actor')
        csrf = session.get('csrfToken', '')
        require(isinstance(csrf, str) and len(csrf) == 36 and
                all(c in '0123456789abcdef-' for c in csrf), 'invalid CSRF token')
        require(any(k.lower() == 'set-cookie' and 'trace_admin_csrf=' + csrf in v for k, v in headers),
                'CSRF cookie missing')
        self.csrf = csrf
        self.auth['Cookie'] += '; trace_admin_csrf=' + csrf

    def channels(self):
        value, _ = self.request(ADMIN, CHANNELS)
        rows = value['firmwareChannels']
        require(len(rows) == 2 and {x['channel'] for x in rows} == {'stable', 'beta'}, 'unexpected channel set')
        return {x['channel']: x for x in rows}

    def releases(self):
        value, _ = self.request(ADMIN, RELEASES)
        require(isinstance(value.get('firmwareReleases'), list), 'release list missing')
        return value['firmwareReleases']

    def preflight(self, version):
        self.login()
        original = self.channels()
        require(original['stable']['disableLatest'] is False and
                original['stable']['disableDownloads'] is False, 'test channel disabled')
        require(all(x['versionCode'] < version for x in self.releases()), 'version already registered or not forward')
        return original

    def activate(self, original, target, query):
        self.login()
        require(self.channels() == original, 'test channels changed before activation')
        matches = [x for x in self.releases() if x['releaseId'] == target['releaseId']]
        require(len(matches) == 1, 'registered candidate missing')
        actual = matches[0]
        require(actual['state'] == 'ready' and actual['archived'] is False and
                actual['versionCode'] == target['versionCode'] and
                actual['targetImageSha256'] == target['targetImageSha256'], 'candidate not ready/mismatched')
        for asset in target['assets']:
            rows = [x for x in actual['assets'] if x['kind'] == asset['kind']]
            require(len(rows) == 1 and rows[0]['r2State'] == 'available' and
                    all(rows[0][k] == asset[k] for k in ('sha256', 'sizeBytes', 'fileName')), 'registered asset mismatch')
        self.mutate(original, target['releaseId'], 'publish')
        latest, _ = self.request(PUBLIC, '/api/public/firmware/latest?' + urlencode(query))
        full = next(x for x in target['assets'] if x['kind'] == 'full')
        require(latest.get('schemaVersion') == 2 and latest.get('updateAvailable') is True and
                all(latest[k] == target[k] for k in ('releaseId', 'versionCode', 'targetImageSha256')),
                'public latest did not select candidate')
        require(latest['asset']['kind'] == 'full' and
                all(latest['asset'][k] == full[k] for k in ('sha256', 'sizeBytes', 'fileName')) and
                urlsplit(latest['asset']['downloadUrl']).scheme == 'https' and
                urlsplit(latest['asset']['downloadUrl']).netloc == urlsplit(PUBLIC).netloc,
                'public package mismatch')

    def mutate(self, before, release_id, action):
        row = before['stable']
        value, _ = self.request(ADMIN, '/api/admin/firmware/channels/stable/' + action,
            dict(appId='trace', deviceModel='e-track-at32f435', releaseId=release_id,
                 expectedRevision=row['revision'], reason='P3-5 test pipeline ' + action))
        require(value.get('ok') is True and value['currentReleaseId'] == release_id and
                value['revision'] == row['revision'] + 1, 'channel mutation not confirmed')
        expected = published(before, release_id)
        require(self.channels() == expected, 'channel readback mismatch')
        return expected

    def restore(self, original, target):
        self.login()
        current = self.channels()
        if current == original:
            return current  # Includes activation rejected before any mutation.
        expected = published(original, target['releaseId'])
        restored = published(expected, original['stable']['currentReleaseId'])
        if current == restored:
            return current  # A previous restoration's response may have been lost.
        require(current == expected, 'channel ownership changed; do not overwrite another operator')
        return self.mutate(current, original['stable']['currentReleaseId'], 'retract')


def published(rows, release_id):
    value = copy.deepcopy(rows)
    value['stable'].update(currentReleaseId=release_id, revision=rows['stable']['revision'] + 1)
    return value
