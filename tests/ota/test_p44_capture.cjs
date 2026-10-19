// Offline transport mocks: no credentials, HTTP, cloud mutation or filesystem output.
const assert = require('node:assert/strict');
const crypto = require('node:crypto');
const s = require('../../Tools/acceptance/p44/run.cjs');
const c = require('../../Tools/acceptance/p44/capture.cjs');
const prefix = '/repos/Eitan-S-23/E-Track';
const envRoute = prefix + '/environments/firmware-rehearsal';
let checks = 0;
const check = (name, run) => { run(); checks++; };
const route = (origin, method, path, allowed) => check(method + path, () => assert.equal(c.routeAllowed(origin, method, path), allowed));

check('canonical', () => assert.equal(c.canonical({ z: [{ b: 1, a: 2 }], a: true }), '{"a":true,"z":[{"a":2,"b":1}]}'));
for (const method of ['PUT', 'DELETE', 'PATCH']) route('https://api.github.com', method, prefix + '/releases', false);
route('https://api.github.com', 'GET', prefix + '/releases?per_page=100&page=1', true);
route('https://api.github.com', 'GET', '/repos/other/repository/releases', false);
route('https://api.github.com', 'POST', prefix + '/actions/workflows/firmware-build.yml/dispatches', true);
route('https://api.github.com', 'POST', prefix + '/actions/workflows/build.yml/dispatches', false);
route('https://api.github.com', 'POST', prefix + '/actions/runs/123/pending_deployments', false);
route('https://api.github.com', 'POST', prefix + '/actions/runs/123/approve', false);
route('https://api.github.com', 'POST', envRoute + '/deployment-branch-policies', true);
route('https://api.github.com', 'POST', prefix + '/environments/firmware-production/deployment-branch-policies', false);
for (const name of ['OTA_PREVIOUS_RELEASE_JSON', 'OTA_APPROVED_BOOTSTRAP_BASELINE_SHA256']) route('https://api.github.com', 'PATCH', envRoute + '/variables/' + name, true);
for (const name of ['OTA_BOOT_CHAIN_READY', 'OTHER']) route('https://api.github.com', 'PATCH', envRoute + '/variables/' + name, false);
for (const value of Object.values(c.resources)) {
  route('https://api.cloudflare.com', 'POST', '/accounts/[ACCOUNT]/d1/database/' + value.db + '/query', true);
  const list = '/' + value.bucket + '/?list-type=2&max-keys=1000';
  route('s3', 'GET', list, true); route('s3', 'PUT', list, false); route('s3', 'DELETE', list, false);
  route('s3', 'GET', list + '&prefix=other', false);
  route('s3', 'GET', '/' + value.bucket + '/../foreign/', false);
  if (value.worker) { route(value.worker, 'POST', '/api/ci/firmware/preflight', true);
    route(value.worker, 'POST', '/api/ci/firmware/releases', false); }
}
route('https://api.cloudflare.com', 'POST', '/accounts/[ACCOUNT]/tokens', false);
route('https://api.cloudflare.com', 'POST', '/accounts/[ACCOUNT]/d1/database/other/query', false);
for (const sql of ['SELECT name,type,sql FROM sqlite_master ORDER BY type,name',
  'SELECT COUNT(*) AS count FROM "firmware_releases"', 'SELECT * FROM "audit_logs" ORDER BY rowid LIMIT 500 OFFSET 0',
  'SELECT * FROM "audit_logs" ORDER BY rowid LIMIT 500 OFFSET 500']) check(sql, () => assert(c.sqlAllowed(sql)));
for (const sql of ['SELECT 1; DELETE FROM firmware_releases', 'DROP TABLE audit_logs', 'PRAGMA table_info(audit_logs)',
  'SELECT * FROM "audit_logs" ORDER BY rowid LIMIT 501 OFFSET 0', 'SELECT * FROM "audit_logs" ORDER BY rowid LIMIT 500 OFFSET -1',
  'SELECT COUNT(*) AS count FROM "bad;name"']) check(sql, () => assert(!c.sqlAllowed(sql)));
check('private headers excluded', () => assert.deepEqual(c.publicHeaders({ link: 'pages', 'set-cookie': 'private', location: 'signed', date: 'now' }), { link: 'pages', date: 'now' }));
check('next link', () => assert.equal(c.nextLink({ link: '<https://api.github.com/next>; rel="next", <last>; rel="last"' }), 'https://api.github.com/next'));
check('terminal link', () => assert.equal(c.nextLink({}), undefined));
const identity = { head_sha: 'a'.repeat(40), head_branch: 'dev/p4-4/config-integration-20261018', run_attempt: 1,
  event: 'workflow_dispatch', path: '.github/workflows/firmware-build.yml', repository: { full_name: 'Eitan-S-23/E-Track' } };
check('run identity', () => c.runIdentity(identity, { commitSha: identity.head_sha }));
for (const [key, value] of [['run_attempt', 2], ['head_sha', 'b'.repeat(40)], ['head_branch', 'main'], ['event', 'push'], ['path', 'other.yml']]) {
  check('reject run drift ' + key, () => assert.throws(() => c.runIdentity({ ...identity, [key]: value }, { commitSha: identity.head_sha })));
}
const currentBytes = s.fs.readFileSync(s.path.join(s.root,
  'docs/ota-exec-notes/P4-4-root-review-2026-10-19/preparation/verification-inputs/current.json'));
const current = JSON.parse(currentBytes);
const currentTables = {
  firmware_releases: [{ app_id: current.appId, device_model: current.deviceModel, version_code: current.versionCode,
    registration_json: currentBytes.toString('utf8').trimEnd() }],
  firmware_channels: [{ app_id: current.appId, device_model: current.deviceModel, legacy_current_release_id: null }],
  firmware_releases_legacy: [],
};
check('current staging fixture identity', () => assert.equal(s.sha256(currentBytes),
  'fe435e1a0bc6afea344566846b1a63e8de39ee9335a98a874e97fbcc82b543a4'));
check('admit exact existing staging registration', () => c.stagingAdmission(currentTables));
for (const [name, change] of [
  ['missing schema', value => delete value.firmware_channels],
  ['unexpected current version', value => { value.firmware_releases[0].version_code = 30209; }],
  ['ambiguous baseline', value => { value.firmware_releases.push({ ...value.firmware_releases[0] }); }],
  ['changed registration', value => { value.firmware_releases[0].registration_json += ' '; }],
  ['unresolved legacy channel', value => { value.firmware_channels[0].legacy_current_release_id = 1; }],
  ['legacy version collision', value => { value.firmware_releases_legacy.push({ ...value.firmware_releases[0], version_code: 30209 }); }],
  ['invalid legacy version', value => { value.firmware_releases_legacy.push({ ...value.firmware_releases[0], version_code: '30208' }); }],
]) {
  const value = structuredClone(currentTables); change(value);
  check('reject staging admission ' + name, () => assert.throws(() => c.stagingAdmission(value)));
}
const outputs = new Map(), saved = { ...s };
const exists = s.fs.existsSync, spawnSync = s.cp.spawnSync;
s.destination = name => s.path.join(s.root, '.cache/p44-capture-offline-unused', name);
s.fs.existsSync = file => String(file).startsWith(s.destination(''))
  ? outputs.has(s.path.relative(s.destination(''), file).replaceAll('\\', '/')) : exists(file);
s.write = (name, value) => {
  assert(!outputs.has(name), 'ORIGINAL_EXISTS');
  const bytes = Buffer.isBuffer(value) ? value : Buffer.from(typeof value === 'string' ? value : JSON.stringify(value));
  outputs.set(name, bytes); return { path: name, size_bytes: bytes.length, sha256: crypto.createHash('sha256').update(bytes).digest('hex') };
};
s.read = name => JSON.parse(outputs.get(name));
s.readBytes = name => outputs.get(name);
const fixtureValue = 'OFFLINE_FIXTURE_NOT_A_REAL_CREDENTIAL';
c._test.setContext({ account: '1'.repeat(32), local: fixtureValue, gh: fixtureValue, sensitive: [fixtureValue] });
const response = (body, headers = {}, status = 200) => ({ status, headers, bytes: Buffer.from(typeof body === 'string' ? body : JSON.stringify(body)) });
async function main() {
  let requests = 0;
  c._test.setTransport(async (url, method, headers, body) => {
    requests++; assert.equal(method, 'POST'); assert(outputs.has('dispatch-reservation.json'));
    assert.equal(JSON.parse(body).ref, 'test'); return response('', { 'x-github-request-id': 'fixture' }, 204);
  });
  const posted = await c._test.capture('dispatch', 'https://api.github.com', prefix + '/actions/workflows/firmware-build.yml/dispatches', {
    method: 'POST', body: { ref: 'test' }, expected: 204 });
  check('zero byte HTTP 204 retained', () => assert.equal(posted.envelope.body.size_bytes, 0));
  check('original request saved', () => assert.equal(s.read('dispatch.request.json').ref, 'test'));
  await assert.rejects(c._test.capture('dispatch', 'https://api.github.com', prefix + '/actions/workflows/firmware-build.yml/dispatches', {
    method: 'POST', body: { ref: 'test' }, expected: 204 })); checks++;
  check('no repeat dispatch', () => assert.equal(requests, 1));
  c._test.setTransport(async () => response({ errors: [{ code: 9109 }] }, {}, 403));
  await assert.rejects(c._test.capture('denied', 'https://api.github.com', prefix + '/releases')); checks++;
  check('failed response retained', () => assert.equal(s.read('denied.http.json').status, 403));
  c._test.setTransport(async () => { throw Object.assign(new Error(fixtureValue), { code: 'MOCK_TLS_ERROR' }); });
  await assert.rejects(c._test.capture('transport', 'https://api.github.com', prefix + '/releases')); checks++;
  check('transport class only', () => assert.equal(s.read('transport.http.json').error_code, 'MOCK_TLS_ERROR'));
  check('no exception secret stored', () => assert(!outputs.get('transport.http.json').includes(Buffer.from(fixtureValue))));
  c._test.setTransport(async () => { throw Object.assign(new Error('interrupted'), { code: 'MOCK_TRUNCATED',
    partial: response({ valid_json_but_incomplete_stream: true }, { 'content-type': 'application/json' }, 200) }); });
  await assert.rejects(c._test.capture('partial', 'https://api.github.com', prefix + '/releases')); checks++;
  check('partial HTTP status preserved', () => assert.equal(s.read('partial.http.json').status, 200));
  check('partial HTTP marked incomplete', () => assert.equal(s.read('partial.http.json').completed, false));
  check('safe partial bytes retained', () => assert(outputs.has('partial.partial.body')));
  c._test.setTransport(async () => response({ accidentally_leaked: fixtureValue }));
  await assert.rejects(c._test.capture('sensitive', 'https://api.github.com', prefix + '/releases')); checks++;
  check('sensitive body not public', () => assert(!outputs.has('sensitive.body')));
  c._test.setTransport(async () => response({}, { 'x-debug': fixtureValue }));
  await assert.rejects(c._test.capture('sensitive-header', 'https://api.github.com', prefix + '/releases')); checks++;
  check('sensitive header not public', () => assert(!outputs.get('sensitive-header.http.json').includes(Buffer.from(fixtureValue))));
  await assert.rejects(c._test.capture('sensitive-request', 'https://api.github.com', prefix + '/actions/workflows/firmware-build.yml/dispatches', {
    method: 'POST', body: { leaked: fixtureValue } })); checks++;
  check('sensitive request not public', () => assert(!outputs.has('sensitive-request.request.json')));
  c._test.setTransport(async url => url.endsWith('page=1') ? response([{ id: 1 }], {
    link: '<https://api.github.com' + prefix + '/releases?page=2&per_page=100>; rel="next"',
  }) : response([{ id: 2 }]));
  const listed = await c._test.pages('pages', prefix + '/releases');
  check('pagination original headers retained', () => assert(listed.records[0].response_headers.link));
  check('pagination covers both pages', () => assert.deepEqual(listed.items.map(x => x.id), [1, 2]));
  c._test.setTransport(async () => response([], { link: '<https://foreign.invalid/p?per_page=100&page=2>; rel="next"' }));
  await assert.rejects(c._test.pages('bad-pages', prefix + '/releases')); checks++;
  c._test.setTransport(async () => response({ total_count: 2, jobs: [{ id: 1 }] }));
  await assert.rejects(c._test.pages('incomplete', prefix + '/actions/runs/1/attempts/1/jobs', 'jobs')); checks++;
  c._test.setTransport(async () => response({ success: true, result: [{ success: true,
    meta: { rows_written: 0, changed_db: false }, results: [{ count: 0 }] }] }));
  const read = await c._test.d1('d1', 'production', 'SELECT COUNT(*) AS count FROM "firmware_releases"');
  check('read-only D1 full body retained', () => assert.equal(read.rows[0].count, 0));
  c._test.setTransport(async () => response({ success: true, result: [{ success: true,
    meta: { rows_written: 1, changed_db: true }, results: [] }] }));
  await assert.rejects(c._test.d1('d1-write', 'production', 'SELECT COUNT(*) AS count FROM "firmware_releases"')); checks++;
  c._test.setTransport(async (url, method, headers) => {
    assert.equal(method, 'GET'); assert.match(headers.authorization, /^AWS4-HMAC-SHA256 Credential=OFFLINEID\//);
    assert(headers.authorization.includes('/auto/s3/aws4_request')); assert(headers['x-amz-content-sha256']);
    return response('<ListBucketResult/>');
  });
  await c._test.s3('s3', 'staging', '/' + c.resources.staging.bucket + '/?list-type=2&max-keys=1000', {
    accessKeyId: 'OFFLINEID', secretAccessKey: 'OFFLINEKEY' }); checks++;
  check('SigV4 credential never archived', () => assert(![...outputs.values()].some(bytes => bytes.includes(Buffer.from('OFFLINEID')))));
  const target = { repository: 'Eitan-S-23/E-Track', branch: identity.head_branch, commitSha: identity.head_sha,
    versionName: '3.2.9', minAppVersionCode: 0, minProtocolVersion: 1,
    descriptor: { targetCommitSha: identity.head_sha, targetVersionName: '3.2.9' } };
  target.descriptorSha256 = s.sha256(c.canonical(target.descriptor));
  s.write('target.json', target); s.write('configured.json', {}); s.write('snapshots/before.json', {});
  c._test.setFrozen(() => target); c._test.setSleep(async () => {});
  let dispatches = 0, waitReads = 0;
  const names = ['CLOUDFLARE_ACCOUNT_ID', 'OTA_AES_KEY', 'TRACE_DEPLOY_TOKEN', 'TRACE_UPDATE_SERVICE_URL', 'TRACE_R2_ACCESS_KEY_ID', 'TRACE_R2_SECRET_ACCESS_KEY'];
  c._test.setTransport(async (url, method) => {
    const u = new URL(url), endpoint = u.pathname, production = endpoint.includes('firmware-production');
    const keyPrefix = production ? '' : 'FIRMWARE_REHEARSAL_';
    if (endpoint.endsWith('/dispatches')) { assert.equal(method, 'POST'); dispatches++; return response('', {}, 204); }
    if (endpoint.endsWith('/pending_deployments')) return response([{ environment: { name: 'firmware-rehearsal', id: 24458272742 } }]);
    if (endpoint.endsWith('/actions/runs/123')) { waitReads++; return response({ ...identity, id: 123,
      status: waitReads === 1 ? 'in_progress' : 'waiting', conclusion: null, created_at: new Date().toISOString(), updated_at: new Date().toISOString() }); }
    if (endpoint.endsWith('/runs')) return response({ total_count: u.searchParams.has('branch') ? 1 : 0,
      workflow_runs: u.searchParams.has('branch') ? [{ ...identity, id: 123, created_at: new Date().toISOString(), html_url: 'offline-fixture-run-123' }] : [] });
    if (endpoint.includes('/git/ref/heads/')) return response({ object: { sha: target.commitSha } });
    if (endpoint.endsWith('/actions/variables/OTA_BOOT_CHAIN_READY')) return response({ value: 'false' });
    if (endpoint.endsWith('/secrets')) return response({ total_count: names.length, secrets: names.map(name => ({ name: keyPrefix + name })) });
    if (endpoint.endsWith('/variables')) {
      const values = { OTA_BOOT_CHAIN_READY: 'false', TRACE_FIRMWARE_MIN_APP_VERSION_CODE: '0', TRACE_FIRMWARE_MIN_PROTOCOL_VERSION: '1',
        [keyPrefix + 'TRACE_R2_BUCKET']: c.resources[production ? 'production' : 'staging'].bucket,
        OTA_PREVIOUS_RELEASE_JSON: c.canonical(target.descriptor), OTA_APPROVED_BOOTSTRAP_BASELINE_SHA256: target.descriptorSha256 };
      return response({ total_count: Object.keys(values).length, variables: Object.entries(values).map(([name, value]) => ({ name, value })) });
    }
    if (endpoint.endsWith('/deployment-branch-policies')) return response({ total_count: 1, branch_policies: [{ name: production ? 'main' : target.branch, type: 'branch' }] });
    if (endpoint.endsWith('/environments/firmware-' + (production ? 'production' : 'rehearsal'))) return response({
      deployment_branch_policy: { protected_branches: false, custom_branch_policies: true }, protection_rules: [{ type: 'required_reviewers',
        prevent_self_review: production, reviewers: [{ type: 'User', reviewer: { login: 'Eitan-S-23', id: 204050265 } }] }] });
    throw Error('UNKNOWN_MOCK_ROUTE');
  });
  const log = console.log; console.log = () => {};
  try { await c._test.dispatch('a'); } finally { console.log = log; }
  check('real orchestration dispatches once', () => assert.equal(dispatches, 1));
  check('intent and HTTP reservations distinct', () => assert(outputs.has('run-a/dispatch-intent.json') && outputs.has('run-a/dispatch-reservation.json')));
  check('stale in-progress status not selected as waiting', () => assert.equal(waitReads, 2));
  check('waiting record bound to second observation', () => assert.equal(s.read('run-a/waiting.json').waiting_run.body.path, 'run-a/waiting-2.body'));
  await assert.rejects(c._test.dispatch('a')); checks++;
  check('repeated orchestration cannot redispatch', () => assert.equal(dispatches, 1));
  const broken = { ...target, minProtocolVersion: 2 }; outputs.set('target.json', Buffer.from(JSON.stringify(broken)));
  await assert.rejects(c._test.configuration('min-protocol-drift', true)); checks++;
  outputs.set('target.json', Buffer.from(JSON.stringify(target)));
  const orchestrationTransport = async (url, method) => {
    const u = new URL(url), endpoint = u.pathname;
    if (endpoint.endsWith('/actions/runs/123/attempts/1')) return response({ ...identity, id: 123,
      status: 'completed', conclusion: 'failure', created_at: new Date().toISOString(), updated_at: new Date().toISOString() });
    if (endpoint.endsWith('/approvals')) return response([{ state: 'rejected', user: { login: 'Eitan-S-23', id: 204050265, type: 'User' },
      environments: [{ name: 'firmware-rehearsal', id: 24458272742 }] }]);
    if (endpoint.endsWith('/jobs')) {
      const jobNames = ['Build firmware (arm-none-eabi-gcc)', 'Release tooling development checks (no cloud credentials)',
        'Firmware rehearsal (shared release implementation)', 'Firmware production (shared release implementation)',
        'Isolated firmware binding qualification (not rehearsal)'];
      return response({ total_count: 5, jobs: jobNames.map((name, i) => ({ id: i + 1, name, run_id: 123, run_attempt: 1,
        head_sha: target.commitSha, head_branch: target.branch, status: 'completed', conclusion: i < 2 ? 'success' : 'skipped', steps: [] })) });
    }
    throw Error('UNKNOWN_FINAL_MOCK_ROUTE');
  };
  c._test.setTransport(orchestrationTransport);
  s.cp.spawnSync = () => ({ status: 0, stdout: Buffer.from('PK_OFFLINE_ZIP_FIXTURE'), stderr: Buffer.alloc(0) });
  console.log = () => {};
  try { await c._test.finish('a'); } finally { console.log = log; }
  check('finish captures complete logs without approval API', () => assert(outputs.has('run-a/logs.zip') && outputs.has('run-a/logs.json')));
  let repeatedRequests = 0;
  c._test.setTransport(async () => { repeatedRequests++; throw Error('UNEXPECTED_REPEAT_GET'); });
  s.cp.spawnSync = () => { repeatedRequests++; throw Error('UNEXPECTED_REPEAT_DOWNLOAD'); };
  await assert.rejects(c._test.finish('a', 'recover-offline-')); checks++;
  await assert.rejects(c._test.collectLogs('a', 'recover-offline-')); checks++;
  check('completed final and logs refused before network', () => assert.equal(repeatedRequests, 0));
  const witness = s.write('owner-rejection-fixture.txt', Buffer.from('OFFLINE owner action fixture, not a real reviewer action'));
  s.write('reviewer-action-a.json', { reviewer: 'Eitan-S-23', reviewer_id: 204050265, run_id: 123, run_attempt: 1,
    state: 'rejected', basis: 'owner_response', evidence: witness });
  check('strict rejection admission', () => c._test.rejectedAdmission());
  const final = s.read('run-a/final.json'), reviewFile = final.reviews_http.body.path;
  const oldReview = outputs.get(reviewFile);
  outputs.set(reviewFile, Buffer.from('[]'));
  check('rejection receipt tampering blocks B', () => assert.throws(() => c._test.rejectedAdmission()));
  outputs.set(reviewFile, oldReview);
  const artifactBytes = Buffer.from('PK_OFFLINE_ARTIFACT_FIXTURE');
  s.write('run-b/identity.json', { run_id: 124 }); s.write('run-b/final.json', { run: { conclusion: 'success' } });
  c._test.setTransport(async () => response({ total_count: 1, artifacts: [{ id: 125, name: 'p41-rehearsal-124-1',
    expired: false, workflow_run: { head_sha: target.commitSha }, size_in_bytes: artifactBytes.length,
    digest: 'sha256:' + s.sha256(artifactBytes) }] }));
  s.cp.spawnSync = () => ({ status: 0, stdout: artifactBytes, stderr: Buffer.alloc(0) });
  await c._test.collectArtifact(); checks++;
  check('separate readonly collector binds actual archive bytes', () => assert.equal(s.read('artifact.json').artifact.sha256, s.sha256(artifactBytes)));
  c._test.setTransport(async () => { repeatedRequests++; throw Error('UNEXPECTED_REPEAT_GET'); });
  s.cp.spawnSync = () => { repeatedRequests++; throw Error('UNEXPECTED_REPEAT_DOWNLOAD'); };
  await assert.rejects(c._test.collectArtifact('recover-offline-')); checks++;
  check('completed artifact refused before network', () => assert.equal(repeatedRequests, 0));
  // Simulate a successful POST followed by a failed discovery, retaining both originals.
  for (const key of [...outputs.keys()].filter(name => name.startsWith('run-a/'))) outputs.delete(key);
  s.write('run-a/dispatch-intent.json', { created_at: new Date().toISOString(), commitSha: target.commitSha,
    body: { ref: target.branch, inputs: { publish: 'false', rehearsal: 'true', check_bindings: 'false', approved_rehearsal_run_id: '',
      version_name: '3.2.9', release_notes: 'P4-4 new S3/preflight configuration qualification; staging only; gate=false; no production release.' } } });
  s.write('run-a/dispatch.http.json', { status: 204, completed: true });
  s.write('run-a/discovery-1-1.http.json', { completed: false, error_code: 'MOCK_TLS_ERROR' });
  let recoveryPosts = 0;
  c._test.setTransport(async (url, method) => {
    if (method !== 'GET') recoveryPosts++;
    const endpoint = new URL(url).pathname;
    if (endpoint.endsWith('/runs')) return response({ total_count: 1, workflow_runs: [{ ...identity, id: 123,
      status: 'waiting', created_at: new Date().toISOString(), html_url: 'offline-fixture-run-123' }] });
    if (endpoint.endsWith('/pending_deployments')) return response([{ environment: { id: 24458272742, name: 'firmware-rehearsal' } }]);
    return response({ ...identity, id: 123, status: 'waiting' });
  });
  console.log = () => {};
  try { await c._test.recover('a', 'offline-1'); } finally { console.log = log; }
  check('lost discovery recovery is GET-only', () => assert.equal(recoveryPosts, 0));
  check('failed discovery preserved', () => assert.equal(s.read('run-a/discovery-1-1.http.json').completed, false));
  check('recovery binds same intent source', () => assert.equal(s.read('run-a/identity.json').run_id, 123));
  console.log(JSON.stringify({ ok: true, assertions: checks, cloud_operations: 0, filesystem_writes: 0,
    standard_signer: '@smithy/signature-v4', capture_bodies: [...outputs.keys()].filter(k => k.endsWith('.body')).length }));
}
main().catch(error => { console.error(JSON.stringify({ ok: false, assertions: checks, error_code: error.code || 'OFFLINE_TEST_FAILED' })); process.exitCode = 1; })
  .finally(() => { Object.assign(s, saved); c._test.setContext(undefined); c._test.setTransport(undefined);
    s.fs.existsSync = exists; s.cp.spawnSync = spawnSync;
    c._test.setFrozen(undefined); c._test.setSleep(undefined); });
