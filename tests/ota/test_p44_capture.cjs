// Offline transport mocks: no credentials, HTTP, cloud mutation or filesystem output.
const assert = require('node:assert/strict');
const crypto = require('node:crypto');
const { Readable } = require('node:stream');
const { gzipSync } = require('node:zlib');
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
  'SELECT * FROM "audit_logs" ORDER BY rowid LIMIT 500 OFFSET 500',
  'SELECT * FROM "audit_logs" ORDER BY rowid LIMIT 8 OFFSET 0', 'SELECT * FROM "audit_logs" ORDER BY rowid LIMIT 8 OFFSET 8']) check(sql, () => assert(c.sqlAllowed(sql)));
for (const sql of ['SELECT 1; DELETE FROM firmware_releases', 'DROP TABLE audit_logs', 'PRAGMA table_info(audit_logs)',
  'SELECT * FROM "audit_logs" ORDER BY rowid LIMIT 501 OFFSET 0', 'SELECT * FROM "audit_logs" ORDER BY rowid LIMIT 16 OFFSET 0',
  'SELECT * FROM "audit_logs" ORDER BY rowid LIMIT 500 OFFSET -1',
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
const approvedPrevious = c._test.approvedPredecessorTarget();
const approvedV1 = JSON.parse(s.fs.readFileSync(s.path.join(s.root, 'docs/acceptance-contracts/P4-4-v1/evidence/target.json')));
const approvedV2 = JSON.parse(s.fs.readFileSync(s.path.join(s.root, 'docs/acceptance-contracts/P4-4-v2/evidence/target.json')));
const approvedP41 = JSON.parse(s.fs.readFileSync(s.path.join(s.root, 'docs/acceptance-contracts/P4-1-v2/evidence/formal/target.json')));
check('approved v3 target is hash-bound to C3', () => assert.equal(approvedPrevious.commitSha, 'ba952497948a03c40cbd8baebbfc9228621fb44b'));
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
s.fileRef = name => {
  const bytes = outputs.get(name); assert(Buffer.isBuffer(bytes));
  return { path: name, size_bytes: bytes.length, sha256: s.sha256(bytes) };
};
const fixtureValue = 'OFFLINE_FIXTURE_NOT_A_REAL_CREDENTIAL';
c._test.setContext({ account: '1'.repeat(32), local: fixtureValue, gh: fixtureValue, sensitive: [fixtureValue] });
const privateOutputs = new Map();
c._test.setPrivateCapture((label, bytes) => {
  assert(!privateOutputs.has(label), 'PRIVATE_ORIGINAL_EXISTS');
  if (bytes === undefined) return;
  privateOutputs.set(label, Buffer.from(bytes));
  return { path: '.cache/p44/private/capture-failures/P4-4-v4/' + label + '.wire.body',
    size_bytes: bytes.length, sha256: s.sha256(bytes) };
});
const response = (body, headers = {}, status = 200) => ({ status, headers, bytes: Buffer.from(typeof body === 'string' ? body : JSON.stringify(body)) });
const predecessorName = 'inputs/predecessor-before.json', predecessorRoot = 'p';
const inheritedRootName = 'inputs/predecessor-before', inheritedRoot = predecessorRoot + '/' + inheritedRootName;
const ancestorRoot = inheritedRoot + '/' + inheritedRootName;
function predecessorFixture(records, transform = () => {}, recent = [], latest = []) {
  for (const name of [...outputs.keys()]) if (name.startsWith('inputs/predecessor-before')
    || name.startsWith(predecessorRoot + '/')
    || name.startsWith('snapshots/before/') || name.startsWith('snapshots/after/')) outputs.delete(name);
  const files = [], middleFiles = [], inheritedFiles = [];
  const layers = [{ root: predecessorRoot, files }, { root: inheritedRoot, files: middleFiles }];
  const original = (root, list, name, value, include = true) => {
    const reference = { ...s.write(root + '/' + name, value), path: name };
    for (const parent of layers) if (root.startsWith(parent.root + '/')) {
      parent.files.push({ ...reference, path: root.slice(parent.root.length + 1) + '/' + name });
    }
    if (include) list.push(reference);
    return reference;
  };
  const recordOriginals = (root, list, items) => { for (const record of items) {
    const label = record.label, method = record.method || 'POST', origin = record.origin || 'https://api.cloudflare.com';
    const path = record.path || '/accounts/[ACCOUNT]/d1/database/' + c.resources.protected.db + '/query';
    const request = method === 'POST' ? original(root, list, label + '.request.json', Buffer.from(JSON.stringify({ sql: record.sql }))) : undefined;
    const started = '2026-10-19T11:00:00Z', ended = '2026-10-19T11:00:01Z';
    original(root, list, label + '-reservation.json', { method, origin, path, started, ...(request ? { request } : {}) });
    const completed = record.completed !== false;
    const payload = record.body || {
      success: true, result: [{ success: true, meta: { rows_written: 0, changed_db: false }, results: record.rows || [] }],
    };
    const decoded = Buffer.isBuffer(payload) ? payload : Buffer.from(JSON.stringify(payload));
    const wire = record.gzip ? gzipSync(decoded) : payload;
    const body = record.noResponse ? undefined : original(root, list, label + (completed ? '.body' : '.partial.body'), wire);
    const sidecar = record.gzip && completed ? original(root, list, label + '.decoded.body', record.decodedBody || decoded) : undefined;
    const envelope = { method, path, started, ended, completed,
      ...(!record.noResponse ? { status: record.status || 200, body,
        response_headers: { 'content-type': 'application/json', ...(record.gzip ? { 'content-encoding': 'gzip', 'content-length': String(wire.length) } : {}) } } : {}),
      ...(sidecar ? { decoded_body: sidecar } : {}),
      ...(request ? { request } : {}), ...(!completed ? { error_code: record.noResponse ? 'ECONNRESET' : 23 } : {}), ...record.envelope };
    original(root, list, label + '.http.json', envelope);
  } };
  recordOriginals(ancestorRoot, inheritedFiles, records);
  recordOriginals(inheritedRoot, middleFiles, recent);
  recordOriginals(predecessorRoot, files, latest);
  const ancestor = { status: 'FROZEN', contract_id: 'P4-4-v1', freeze_commit: '08afb97ddae316b3b305354f1582afdb836d7633' };
  const ancestorContract = original(ancestorRoot, inheritedFiles, 'predecessor.contract.json', ancestor, false);
  const ancestorMatrix = original(ancestorRoot, inheritedFiles, 'predecessor.final-evidence-matrix.json', {
    contract_id: ancestor.contract_id, contract_sha256: ancestorContract.sha256, overall_result: 'EVIDENCE_GAP' }, false);
  const ancestorManifest = original(inheritedRoot, middleFiles, predecessorName, { schema: 'p44-predecessor-before-v1',
    source_evidence_root: inheritedRootName, source_commit: ancestor.freeze_commit,
    source_bundle_commit: 'e5994fb28466e46c99a1f247494473e6cba9cc03', predecessor_contract_id: ancestor.contract_id,
    predecessor_contract_sha256: ancestorContract.sha256, predecessor_contract: ancestorContract,
    predecessor_final_matrix: ancestorMatrix, files: inheritedFiles });
  const middle = { status: 'FROZEN', contract_id: 'P4-4-v2', freeze_commit: '70193ce7fb7cc4e426029d07cf7b50c1fcbfef1c',
    external_inputs: [{ id: 'predecessor-before', evidence_path: 'evidence/' + predecessorName,
      evidence_sha256: ancestorManifest.sha256, fingerprint: 'sha256:' + ancestorManifest.sha256 }] };
  const middleContract = original(inheritedRoot, middleFiles, 'predecessor.contract.json', middle, false);
  const middleMatrix = original(inheritedRoot, middleFiles, 'predecessor.final-evidence-matrix.json', { contract_id: middle.contract_id,
    contract_sha256: middleContract.sha256, overall_result: 'EVIDENCE_GAP' }, false);
  const inherited = original(predecessorRoot, files, predecessorName, { schema: 'p44-predecessor-before-v1',
    source_evidence_root: inheritedRootName, source_commit: middle.freeze_commit,
    source_bundle_commit: '84268ac2ad34727b76250ff944211b7efba1cfb3', predecessor_contract_id: middle.contract_id,
    predecessor_contract_sha256: middleContract.sha256, predecessor_contract: middleContract,
    predecessor_final_matrix: middleMatrix, inherited_predecessor: ancestorManifest, files: middleFiles });
  const previous = { status: 'FROZEN', contract_id: 'P4-4-v3', freeze_commit: 'ba952497948a03c40cbd8baebbfc9228621fb44b',
    external_inputs: [{ id: 'predecessor-before', evidence_path: 'evidence/' + predecessorName,
      evidence_sha256: inherited.sha256, fingerprint: 'sha256:' + inherited.sha256 }] };
  const contractRef = original(predecessorRoot, files, 'predecessor.contract.json', previous, false);
  const matrixRef = original(predecessorRoot, files, 'predecessor.final-evidence-matrix.json', { contract_id: previous.contract_id,
    contract_sha256: contractRef.sha256, overall_result: 'EVIDENCE_GAP' }, false);
  const manifest = { schema: 'p44-predecessor-before-v1', source_evidence_root: predecessorRoot,
    source_commit: previous.freeze_commit, source_bundle_commit: '20febda2ac2e05e5f4b761a9f365091b177516b6',
    predecessor_contract_id: previous.contract_id, predecessor_contract_sha256: contractRef.sha256,
    predecessor_contract: contractRef, predecessor_final_matrix: matrixRef, inherited_predecessor: inherited, files };
  transform(manifest);
  const manifestRef = s.write(predecessorName, manifest);
  return { status: 'FROZEN', contract_id: 'P4-4-v4', external_inputs: [{ id: 'predecessor-before',
    evidence_path: 'evidence/' + predecessorName, evidence_sha256: manifestRef.sha256, fingerprint: 'sha256:' + manifestRef.sha256 }] };
}
function streamed(wire, headers, width = 113) {
  const chunks = [];
  for (let offset = 0; offset < wire.length; offset += width) chunks.push(wire.subarray(offset, offset + width));
  return { statusCode: 200, headers, body: Readable.from(chunks) };
}
const decodedResponse = (wire, headers, decodeD1 = true, limit = c._test.httpMaxBytes, width) =>
  c._test.responseBytes(streamed(wire, headers, width), decodeD1, limit, new AbortController().signal);
async function strictTransport() {
  const original = s.fs.readFileSync(s.path.join(s.root,
    'docs/acceptance-contracts/P4-4-v2/evidence/snapshots/before/protected-channel_history-rows8-24.body'));
  for (const bytes of [original, Buffer.from(JSON.stringify({ before_json: 'x'.repeat(2 * 1024 * 1024 + 17),
    after_json: '\u4e2d\u6587-\u00e9-\ud83d\ude80' }))]) {
    const wire = gzipSync(bytes), headers = { 'content-encoding': 'gzip', 'content-length': String(wire.length) };
    const compressed = await decodedResponse(wire, headers, true, c._test.httpMaxBytes, 3);
    const identity = await decodedResponse(bytes, { 'content-length': String(bytes.length) }, true, c._test.httpMaxBytes, 65536);
    check('large streamed gzip preserves distinct wire and decoded bytes', () => {
      assert(compressed.wireBytes.equals(wire)); assert(compressed.bytes.equals(bytes));
      assert(identity.bytes.equals(bytes)); assert.deepEqual(compressed.headers, headers);
      assert(compressed.decodedVerified); assert.notEqual(s.sha256(compressed.wireBytes), s.sha256(compressed.bytes));
    });
  }
  const bytes = Buffer.from('{"ok":true}'), wire = gzipSync(bytes);
  const crc = Buffer.from(wire); crc[crc.length - 8] ^= 1;
  const isize = Buffer.from(wire); isize[isize.length - 4] ^= 1;
  for (const [name, input, encoding] of [
    ['truncated-header', wire.subarray(0, 5), 'gzip'], ['truncated-trailer', wire.subarray(0, -1), 'gzip'],
    ['bad-crc', crc, 'gzip'], ['bad-size', isize, 'gzip'], ['not-gzip', bytes, 'gzip'],
    ['unsupported', wire, 'br'], ['compound', wire, 'gzip, deflate'], ['empty-encoding', wire, ''],
  ]) {
    const source = streamed(input, { 'content-encoding': encoding }, 3);
    await assert.rejects(c._test.responseBytes(source, true, 1024, new AbortController().signal), error => {
      assert(error.partial.bytes.equals(input)); assert.equal(error.partial.decodedVerified, false); return true;
    }); checks++;
    check(name + ' destroys source after failure', () => assert(source.body.destroyed));
  }
  await assert.rejects(decodedResponse(wire, { 'content-encoding': 'gzip', 'content-length': String(bytes.length) }),
    { code: 'HTTP_WIRE_LENGTH' }); checks++;
  await assert.rejects(decodedResponse(wire, { 'content-encoding': 'gzip', 'Content-Encoding': 'gzip' }),
    { code: 'HTTP_ENCODING_UNSUPPORTED' }); checks++;
  const trailerSource = streamed(wire.subarray(0, -1), { 'content-encoding': 'gzip' });
  await assert.rejects(c._test.responseBytes(trailerSource, true, 1024, new AbortController().signal), error => {
    assert.deepEqual(JSON.parse(error.partial.decodedBytes), { ok: true });
    assert.equal(error.partial.decodedVerified, false); return true;
  }); checks++;
  await assert.rejects(decodedResponse(Buffer.alloc(1025, 1), {}, true, 1024), error => {
    assert.equal(error.code, 'HTTP_WIRE_SIZE_LIMIT'); assert.equal(error.partial.bytes.length, 1024); return true;
  }); checks++;
  await assert.rejects(decodedResponse(gzipSync(Buffer.alloc(4096, 1)), { 'content-encoding': 'gzip' }, true, 1024), error => {
    assert.equal(error.code, 'HTTP_DECODED_SIZE_LIMIT'); assert.equal(error.partial.decodedBytes.length, 1024); return true;
  }); checks++;
  await assert.rejects(decodedResponse(wire, {}, true, c._test.httpMaxBytes + 1)); checks++;
  const s3 = await decodedResponse(wire, { 'content-encoding': 'gzip' }, false);
  check('S3 stored content encoding does not transform object bytes', () => assert(s3.bytes.equals(wire)));

  const originalTimeout = AbortSignal.timeout, requestedDeadlines = [];
  const controller = new AbortController(); let timer, requests = 0, closes = 0, source, requestSignal;
  AbortSignal.timeout = milliseconds => {
    requestedDeadlines.push(milliseconds); timer = setTimeout(() => controller.abort(), 30); return controller.signal;
  };
  c._test.setTransport(undefined);
  c._test.setHttp({ ProxyAgent: class {
    constructor(options) { assert.equal(options.requestTls.rejectUnauthorized, true); assert.equal(options.allowH2, false); }
    async destroy() { closes++; }
  }, request: async (_url, options) => {
    requests++; requestSignal = options.signal;
    assert.equal(options.maxRedirections, 0); assert.equal(options.headersTimeout, 30000); assert.equal(options.bodyTimeout, 30000);
    source = new Readable({ read() {} }); source.push(wire.subarray(0, 5));
    return { statusCode: 200, headers: { 'content-encoding': 'gzip' }, body: source };
  } });
  try {
    await assert.rejects(c._test.transport('https://offline.invalid/query', 'POST', { 'accept-encoding': 'gzip' }, bytes),
      { code: 'ABORT_ERR' }); checks++;
    check('one absolute deadline covers request and stalled decoding without retry', () => {
      assert.deepEqual(requestedDeadlines, [60000]); assert.equal(requestSignal, controller.signal);
      assert.equal(requests, 1); assert.equal(closes, 1); assert(source.destroyed);
    });
  } finally { clearTimeout(timer); AbortSignal.timeout = originalTimeout; c._test.setHttp(undefined); }

  const d1Route = '/accounts/[ACCOUNT]/d1/database/' + c.resources.staging.db + '/query';
  const secretBytes = Buffer.from(JSON.stringify({ accidentally_leaked: fixtureValue })), secretWire = gzipSync(secretBytes);
  check('sensitive fixture is visible only after decompression', () => assert(!secretWire.includes(Buffer.from(fixtureValue))));
  c._test.setTransport(async () => decodedResponse(secretWire, { 'content-encoding': 'gzip' }));
  await assert.rejects(c._test.capture('gzip-secret', 'https://api.cloudflare.com', d1Route,
    { method: 'POST', body: { sql: 'SELECT COUNT(*) AS count FROM "apps"' } })); checks++;
  check('decoded-only secret retains wire privately, never publicly', () => {
    assert(privateOutputs.get('gzip-secret').equals(secretWire));
    assert(!outputs.has('gzip-secret.body')); assert(!outputs.has('gzip-secret.decoded.body'));
    assert(!outputs.has('gzip-secret.partial.body')); assert.equal(s.read('gzip-secret.http.json').completed, false);
    assert(!outputs.get('gzip-secret.http.json').includes(Buffer.from(fixtureValue)));
  });
  c._test.setTransport(async () => decodedResponse(wire.subarray(0, -1), { 'content-encoding': 'gzip' }));
  await assert.rejects(c._test.capture('gzip-truncated', 'https://api.cloudflare.com', d1Route,
    { method: 'POST', body: { sql: 'SELECT COUNT(*) AS count FROM "apps"' } })); checks++;
  check('truncated gzip is private despite complete decoded JSON prefix', () => {
    assert(privateOutputs.get('gzip-truncated').equals(wire.subarray(0, -1)));
    assert(!outputs.has('gzip-truncated.partial.body')); assert(!s.read('gzip-truncated.http.json').body);
  });

  const tables = {};
  for (const [name, rows] of Object.entries(currentTables)) {
    c._test.setTransport(async (_url, method, headers) => {
      assert.equal(method, 'POST'); assert.equal(headers['accept-encoding'], 'gzip');
      const payload = Buffer.from(JSON.stringify({ success: true, result: [{ success: true,
        meta: { rows_written: 0, changed_db: false }, results: rows }] }));
      const compressed = gzipSync(payload);
      return decodedResponse(compressed, { 'content-encoding': 'gzip', 'content-length': String(compressed.length) });
    });
    tables[name] = { pages: await c._test.tablePages('snapshots/before', 'staging', name, rows.length) };
  }
  check('actual gzip tablePages output reaches staging admission', () => c._test.stagingSnapshotAdmission(tables));
  const page = tables.firmware_releases.pages[0], originalDecoded = page.decoded_body;
  check('D1 request negotiation and separate original representations are bound', () => {
    assert.equal(page.request_headers['accept-encoding'], 'gzip'); assert(page.body.path.endsWith('.body'));
    assert(page.decoded_body.path.endsWith('.decoded.body')); assert.notEqual(page.body.sha256, page.decoded_body.sha256);
  });
  page.decoded_body = s.write('wrong-decoded-fixture.body', Buffer.from('{}'));
  check('staging admission rejects valid-hash decoded substitution', () =>
    assert.throws(() => c._test.stagingSnapshotAdmission(tables), /HTTP_DECODED_MISMATCH/));
  page.decoded_body = originalDecoded;
}
async function requestRetries() {
  const undici = require(s.path.join(s.root, 'app/bluetooth_flutter_Trace/cloudflare/update-service/worker/node_modules/undici'));
  const reset = () => Object.assign(new Error(fixtureValue), { code: 'ECONNRESET' });
  const d1Route = '/accounts/[ACCOUNT]/d1/database/' + c.resources.protected.db + '/query';
  const sql = 'SELECT COUNT(*) AS count FROM "apps"';
  c._test.setTransport(undefined);
  for (const [label, origin, route, method, body] of [
    ['retry-native-get', 'https://api.github.com', prefix + '/releases', 'GET', undefined],
    ['retry-native-d1', 'https://api.cloudflare.com', d1Route, 'POST', { sql }],
  ]) {
    const agent = new undici.MockAgent(); agent.disableNetConnect();
    const pool = agent.get(origin);
    const endpoint = origin === 'https://api.cloudflare.com' ? '/client/v4' + route.replace('[ACCOUNT]', '1'.repeat(32)) : route;
    const requestBytes = body ? Buffer.from(JSON.stringify(body)) : undefined;
    const matcher = { path: endpoint, method, ...(body ? {
      body: bytes => bytes instanceof Uint8Array && Buffer.from(bytes).equals(requestBytes),
    } : {}) };
    pool.intercept(matcher).replyWithError(reset());
    const decoded = Buffer.from(JSON.stringify(body ? { success: true, result: [{ success: true,
      meta: { rows_written: 0, changed_db: false }, results: [{ count: 1 }] }] } : []));
    const wire = body ? gzipSync(decoded) : decoded;
    pool.intercept(matcher).reply(200, wire, { headers: body
      ? { 'content-encoding': 'gzip', 'content-length': String(wire.length) } : {} });
    c._test.setHttp({ request: undici.request, ProxyAgent: class extends undici.Dispatcher {
      dispatch(options, handler) { return agent.dispatch(options, handler); }
      async destroy() { await agent.close(); }
    } });
    const got = await c._test.capture(label, origin, route, { method, ...(body ? { body } : {}) });
    agent.assertNoPendingInterceptors();
    check('real installed Undici MockAgent retries exact read once ' + method, () => {
      assert.equal(got.envelope.request_attempts, 2); assert.equal(got.envelope.request_failures.length, 1);
      assert(got.bytes.equals(decoded));
      const first = got.envelope.request_failures[0], failure = s.read(first.path);
      assert.equal(s.sha256(s.readBytes(first.path)), first.sha256); assert.equal(failure.error_code, 'ECONNRESET');
      assert.equal(failure.attempt, 1); assert.equal(failure.final_response_received, false);
      assert.equal(failure.informational_seen, false); assert.equal(failure.received_body_bytes, 0);
      assert.deepEqual(s.read(got.envelope.retry_reservation.path).first_failure, first);
      if (body) assert.deepEqual(failure.request, got.envelope.request);
      assert(!s.readBytes(first.path).includes(Buffer.from(fixtureValue)));
      assert(!outputs.has(label + '-request-failure-2.json'));
    });
  }

  let calls = 0, closes = 0, handler;
  const install = fn => {
    calls = 0; closes = 0; handler = fn;
    c._test.setHttp({ request: async (...args) => { calls++; return handler(...args); },
      ProxyAgent: class { async destroy() { closes++; } } });
  };
  install(async () => { throw reset(); });
  await assert.rejects(c._test.capture('retry-twice-failed', 'https://api.github.com', prefix + '/releases')); checks++;
  check('second pre-response failure stops and preserves both originals', () => {
    const envelope = s.read('retry-twice-failed.http.json');
    assert.equal(calls, 2); assert.equal(closes, 1); assert.equal(envelope.request_attempts, 2);
    assert.equal(envelope.request_failures.length, 2); assert(envelope.retry_reservation);
    assert.equal(envelope.completed, false);
    for (const reference of envelope.request_failures) assert.equal(s.sha256(s.readBytes(reference.path)), reference.sha256);
  });
  for (const [label, origin, route, method, body] of [
    ['retry-no-dispatch', 'https://api.github.com', prefix + '/actions/workflows/firmware-build.yml/dispatches', 'POST', { ref: 'test' }],
    ['retry-no-patch', 'https://api.github.com', envRoute + '/variables/OTA_PREVIOUS_RELEASE_JSON', 'PATCH', { name: 'test', value: 'test' }],
    ['retry-no-business-post', c.resources.staging.worker, '/api/ci/firmware/preflight', 'POST', {}],
  ]) {
    install(async () => { throw reset(); });
    await assert.rejects(c._test.capture(label, origin, route, { method, body })); checks++;
    check('write or business request has no extra attempt ' + label, () => {
      assert.equal(calls, 1); assert.equal(s.read(label + '.http.json').request_attempts, 1);
      assert(!outputs.has(label + '-retry-2-reservation.json'));
    });
  }
  check('arbitrary SQL and GET payload are not retry-authorized', () => {
    assert(!c._test.retryableCapture('https://api.cloudflare.com', 'POST', d1Route, { sql: 'DELETE FROM apps' }));
    assert(!c._test.retryableCapture('https://api.github.com', 'GET', prefix + '/releases', {}));
    assert(c._test.retryableCapture('s3', 'GET', '/' + c.resources.staging.bucket + '/?list-type=2&max-keys=1000'));
  });
  install(async () => { throw reset(); });
  await assert.rejects(c._test.transport('https://offline.invalid/private-verify', 'GET', {})); checks++;
  check('direct private verify transport retains one-attempt behavior', () => assert.equal(calls, 1));
  for (const code of ['ECONNREFUSED', 'ENOTFOUND', 'UND_ERR_SOCKET', 'ABORT_ERR']) {
    install(async () => { throw Object.assign(new Error(fixtureValue), { code }); });
    const label = 'retry-no-code-' + code.toLowerCase();
    await assert.rejects(c._test.capture(label, 'https://api.github.com', prefix + '/releases')); checks++;
    check('unapproved error is not retried ' + code, () => assert.equal(calls, 1));
  }
  for (const status of [401, 403, 500]) {
    install(async () => ({ ...streamed(Buffer.from('{"observed":true}'), {}), statusCode: status }));
    const label = 'retry-no-http-' + status;
    await assert.rejects(c._test.capture(label, 'https://api.github.com', prefix + '/releases')); checks++;
    check('HTTP response is retained without retry ' + status, () => {
      assert.equal(calls, 1); assert.equal(s.read(label + '.http.json').status, status);
      assert.equal(s.read(label + '.http.json').request_failures.length, 0); assert(outputs.has(label + '.body'));
    });
  }
  install(async (_url, options) => {
    options.onInfo({ statusCode: 103, headers: { private_header: fixtureValue } }); throw reset();
  });
  await assert.rejects(c._test.capture('retry-no-informational', 'https://api.github.com', prefix + '/releases')); checks++;
  check('1xx blocks retry and is not recorded as no response at all', () => {
    const first = s.read('retry-no-informational-request-failure-1.json');
    assert.equal(calls, 1); assert.equal(first.informational_seen, true); assert.equal(first.first_information.status, 103);
    assert.equal(first.informational_count, 1); assert(!outputs.get('retry-no-informational-request-failure-1.json').includes(Buffer.from(fixtureValue)));
  });
  install(async () => {
    const body = new Readable({ read() { this.push(Buffer.from('{"ok":true}')); this.destroy(reset()); } });
    return { statusCode: 200, headers: {}, body };
  });
  await assert.rejects(c._test.capture('retry-no-body-reset', 'https://api.github.com', prefix + '/releases')); checks++;
  check('ECONNRESET after final headers does not enter request retry boundary', () => {
    assert.equal(calls, 1); assert.equal(s.read('retry-no-body-reset.http.json').status, 200);
    assert.equal(s.read('retry-no-body-reset.http.json').request_failures.length, 0);
  });
  const brokenGzip = gzipSync(Buffer.from('{"ok":true}')).subarray(0, -1);
  install(async () => streamed(brokenGzip, { 'content-encoding': 'gzip' }));
  await assert.rejects(c._test.capture('retry-no-gzip', 'https://api.cloudflare.com', d1Route, { method: 'POST', body: { sql } })); checks++;
  check('gzip failure remains private and does not retry a fulfilled request', () => {
    assert.equal(calls, 1); assert(privateOutputs.get('retry-no-gzip').equals(brokenGzip));
    assert.equal(s.read('retry-no-gzip.http.json').request_failures.length, 0);
  });

  const originalWrite = s.write;
  for (const suffix of ['-request-failure-1.json', '-retry-2-reservation.json']) {
    const label = suffix.includes('failure') ? 'retry-audit-failed' : 'retry-reservation-failed';
    s.write = (name, value) => { if (name === label + suffix) throw Error('OFFLINE_AUDIT_FAILURE'); return originalWrite(name, value); };
    install(async () => { throw reset(); });
    try { await assert.rejects(c._test.capture(label, 'https://api.github.com', prefix + '/releases')); checks++; }
    finally { s.write = originalWrite; }
    check('audit failure prevents an unrecorded extra request ' + suffix, () => assert.equal(calls, 1));
  }
  const originalTimeout = AbortSignal.timeout;
  const controller = new AbortController(), durations = []; let timer;
  AbortSignal.timeout = value => { durations.push(value); return controller.signal; };
  install(async () => { timer = setTimeout(() => controller.abort(), 25); throw reset(); });
  try {
    await assert.rejects(c._test.capture('retry-aborted-backoff', 'https://api.github.com', prefix + '/releases')); checks++;
    check('same 60s signal aborts backoff before a second request', () => {
      assert.deepEqual(durations, [60000]); assert.equal(calls, 1);
      assert(!outputs.has('retry-aborted-backoff-retry-2-reservation.json'));
      assert.equal(s.read('retry-aborted-backoff.http.json').request_failures.length, 1);
    });
  } finally { clearTimeout(timer); AbortSignal.timeout = originalTimeout; }
  let now = 0;
  c._test.setMonotonic(() => now);
  s.write = (name, value) => {
    const reference = originalWrite(name, value);
    if (name === 'retry-sync-deadline-retry-2-reservation.json') now = 60001;
    return reference;
  };
  install(async () => { throw reset(); });
  try {
    await assert.rejects(c._test.capture('retry-sync-deadline', 'https://api.github.com', prefix + '/releases'),
      { code: 'REQUEST_DEADLINE_EXCEEDED' }); checks++;
    check('synchronous reservation crossing deadline cannot send second request', () => {
      const record = s.read('retry-sync-deadline.http.json');
      assert.equal(calls, 1); assert.equal(record.request_attempts, 1); assert(record.retry_reservation);
      assert.equal(record.request_failures.length, 1);
    });
  } finally { s.write = originalWrite; c._test.setMonotonic(undefined); }
  c._test.setHttp(undefined);
}
async function main() {
  await strictTransport();
  await requestRetries();
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

  const oldLabel = 'snapshots/before/protected-channel_history-0';
  const oldSql = 'SELECT * FROM "channel_history" ORDER BY rowid LIMIT 500 OFFSET 0';
  const rows = count => Array.from({ length: count }, (_, id) => ({ id }));
  let network = 0;
  const noNetwork = async () => { network++; throw Error('UNEXPECTED_NETWORK'); };
  c._test.setTransport(noNetwork);
  let fixture = predecessorFixture([{ label: oldLabel, sql: oldSql, rows: rows(500) }]);
  const savedEnvelope = Buffer.from(outputs.get(ancestorRoot + '/' + oldLabel + '.http.json'));
  const priorPages = await c._test.withBeforePredecessor(predecessorName, fixture,
    () => c._test.tablePages('snapshots/before', 'protected', 'channel_history', 500));
  check('complete old 500 page uses zero network requests', () => assert.equal(network, 0));
  check('old page reference relocated without changing original envelope', () => {
    assert.equal(priorPages[0].body.path, ancestorRoot + '/' + oldLabel + '.body');
    assert(outputs.get(ancestorRoot + '/' + oldLabel + '.http.json').equals(savedEnvelope));
    assert.equal(priorPages[0].started, '2026-10-19T11:00:00Z');
    assert.equal(priorPages[0].predecessor_origin.source_bundle_commit, 'e5994fb28466e46c99a1f247494473e6cba9cc03');
  });
  fixture = predecessorFixture([{ label: oldLabel, sql: oldSql, rows: rows(17), completed: false }]);
  const failed = Buffer.from(outputs.get(ancestorRoot + '/' + oldLabel + '.http.json'));
  const offsets = [];
  c._test.setTransport(async (_url, method, _headers, body) => {
    network++; assert.equal(method, 'POST');
    const sql = JSON.parse(body).sql, match = sql.match(/^SELECT \* FROM "channel_history" ORDER BY rowid LIMIT 8 OFFSET ([0-9]+)$/);
    assert(match, 'NEW_PAGE_MUST_BE_EIGHT'); const offset = Number(match[1]); offsets.push(offset);
    return response({ success: true, result: [{ success: true, meta: { rows_written: 0, changed_db: false }, results: rows(17).slice(offset, offset + 8) }] });
  });
  const small = await c._test.withBeforePredecessor(predecessorName, fixture,
    () => c._test.tablePages('snapshots/before', 'protected', 'channel_history', 17));
  check('incomplete large page replaced by exactly three small requests', () => assert.deepEqual(offsets, [0, 8, 16]));
  check('failed large original stays incomplete byte-for-byte', () => assert(outputs.get(ancestorRoot + '/' + oldLabel + '.http.json').equals(failed)));
  check('fresh small labels cannot alias failed large label', () => {
    assert.deepEqual(small.map(page => page.body.path), [0, 8, 16].map(offset => 'snapshots/before/protected-channel_history-rows8-' + offset + '.body'));
    assert(!outputs.has(oldLabel + '.http.json'));
  });
  await assert.rejects(c._test.tablePages('snapshots/before', 'protected', 'channel_history', 17)); checks++;
  check('repeat small-page entry refused before network', () => assert.equal(network, 3));
  network = 0; offsets.length = 0;
  fixture = predecessorFixture([{ label: oldLabel, sql: oldSql, rows: rows(500) }]);
  c._test.setTransport(async (_url, _method, _headers, body) => {
    network++; const match = JSON.parse(body).sql.match(/LIMIT 8 OFFSET ([0-9]+)$/); assert(match);
    const offset = Number(match[1]); offsets.push(offset);
    return response({ success: true, result: [{ success: true, meta: { rows_written: 0, changed_db: false }, results: rows(510).slice(offset, offset + 8) }] });
  });
  const mixed = await c._test.withBeforePredecessor(predecessorName, fixture,
    () => c._test.tablePages('snapshots/before', 'protected', 'channel_history', 510));
  check('mixed width restoration fetches only missing rows', () => assert.deepEqual(offsets, [500, 508]));
  check('mixed width restoration preserves exact row order', () => assert.deepEqual(mixed.flatMap(page => JSON.parse(s.readBytes(page.body.path)).result[0].results), rows(510)));
  network = 0; c._test.setTransport(noNetwork);
  for (const mutation of [
    { sql: oldSql.replace('LIMIT 500', 'LIMIT 8') },
    { envelope: { method: 'GET' } },
    { envelope: { path: '/accounts/[ACCOUNT]/d1/database/wrong/query' } },
    { envelope: { completed: undefined } },
  ]) {
    fixture = predecessorFixture([{ label: oldLabel, sql: oldSql, rows: rows(500), ...mutation }]);
    await assert.rejects(c._test.withBeforePredecessor(predecessorName, fixture,
      () => c._test.tablePages('snapshots/before', 'protected', 'channel_history', 500))); checks++;
  }
  check('binding errors never fall back to a network request', () => assert.equal(network, 0));
  fixture = predecessorFixture([{ label: oldLabel, sql: oldSql, rows: rows(500) }]);
  outputs.set(ancestorRoot + '/' + oldLabel + '.body', Buffer.from('{}'));
  check('tampered predecessor bytes rejected', () => assert.throws(() => c._test.loadBeforePredecessor(predecessorName, fixture)));
  fixture = predecessorFixture([{ label: oldLabel, sql: oldSql, rows: rows(500) }], value => { value.source_bundle_commit = 'b'.repeat(40); });
  check('wrong predecessor bundle identity rejected', () => assert.throws(() => c._test.loadBeforePredecessor(predecessorName, fixture)));
  fixture = predecessorFixture([{ label: oldLabel, sql: oldSql, rows: rows(500) }]);
  fixture.external_inputs[0].evidence_sha256 = '0'.repeat(64);
  check('current frozen anchor mismatch rejected', () => assert.throws(() => c._test.loadBeforePredecessor(predecessorName, fixture)));
  fixture = predecessorFixture([{ label: oldLabel, sql: oldSql, rows: rows(500) }]);
  for (const [origin, method, path, body] of [
    ['https://api.github.com', 'POST', prefix + '/actions/workflows/firmware-build.yml/dispatches', { ref: target.branch }],
    ['https://api.github.com', 'PATCH', envRoute + '/variables/OTA_PREVIOUS_RELEASE_JSON', { value: 'unreviewed' }],
    [c.resources.staging.worker, 'POST', '/api/ci/firmware/preflight', {}],
  ]) {
    await assert.rejects(c._test.withBeforePredecessor(predecessorName, fixture,
      () => c._test.capture('snapshots/before/forbidden-mutation', origin, path, { method, body }))); checks++;
  }
  check('predecessor context cannot authorize mutations', () => assert.equal(network, 0));
  offsets.length = 0;
  c._test.setTransport(async (_url, _method, _headers, body) => {
    network++; const match = JSON.parse(body).sql.match(/LIMIT 8 OFFSET ([0-9]+)$/); assert(match);
    const offset = Number(match[1]); offsets.push(offset);
    return response({ success: true, result: [{ success: true, meta: { rows_written: 0, changed_db: false }, results: rows(17).slice(offset, offset + 8) }] });
  });
  await c._test.tablePages('snapshots/after', 'protected', 'channel_history', 17);
  check('after uses fresh eight-row pages despite available predecessor', () => assert.deepEqual(offsets, [0, 8, 16]));
  await assert.rejects(c._test.snapshot('after', predecessorName)); checks++;
  check('after cannot activate predecessor fixture', () => assert.equal(network, 3));
  network = 0;
  fixture = predecessorFixture([{ label: oldLabel, sql: oldSql, rows: rows(17), completed: false }]);
  c._test.setTransport(async () => { network++; throw Object.assign(new Error('interrupted'), {
    code: 'MOCK_SMALL_PAGE_TIMEOUT', partial: response({ complete_json_not_complete_transport: true }) }); });
  await assert.rejects(c._test.withBeforePredecessor(predecessorName, fixture,
    () => c._test.tablePages('snapshots/before', 'protected', 'channel_history', 17))); checks++;
  check('new small-page failure is not retried or skipped', () => {
    assert.equal(network, 1);
    assert.equal(s.read('snapshots/before/protected-channel_history-rows8-0.http.json').completed, false);
    assert(!outputs.has('snapshots/before/protected-channel_history-rows8-8-reservation.json'));
  });

  const recentPages = [0, 8, 16, 24, 32].map(offset => ({
    label: 'snapshots/before/protected-channel_history-rows8-' + offset,
    sql: 'SELECT * FROM "channel_history" ORDER BY rowid LIMIT 8 OFFSET ' + offset,
    rows: rows(65).slice(offset, offset + 8), completed: offset !== 32,
  }));
  fixture = predecessorFixture([{ label: oldLabel, sql: oldSql, rows: rows(65), completed: false }], () => {}, recentPages);
  const retained = new Map([...outputs].filter(([name]) => name.startsWith(predecessorRoot + '/'))
    .map(([name, bytes]) => [name, Buffer.from(bytes)]));
  offsets.length = 0; network = 0;
  c._test.setTransport(async (_url, method, headers, body) => {
    network++; assert.equal(method, 'POST'); assert.equal(headers['accept-encoding'], 'gzip');
    const match = JSON.parse(body).sql.match(/LIMIT 8 OFFSET ([0-9]+)$/); assert(match);
    const offset = Number(match[1]); offsets.push(offset);
    const payload = Buffer.from(JSON.stringify({ success: true, result: [{ success: true,
      meta: { rows_written: 0, changed_db: false }, results: rows(65).slice(offset, offset + 8) }] }));
    return decodedResponse(gzipSync(payload), { 'content-encoding': 'gzip' });
  });
  const recovered = await c._test.withBeforePredecessor(predecessorName, fixture,
    () => c._test.tablePages('snapshots/before', 'protected', 'channel_history', 65));
  check('V3 resumes first missing V2 page, never replays four complete pages', () => assert.deepEqual(offsets, [32, 40, 48, 56, 64]));
  check('two-layer originals and both failures remain unchanged', () => {
    for (const [name, bytes] of retained) assert(outputs.get(name).equals(bytes));
    assert.equal(recovered[0].predecessor_origin.contract_id, 'P4-4-v2');
    assert.deepEqual(recovered.flatMap(page => c._test.d1Document(page).result[0].results), rows(65));
  });
  for (const transform of [value => { delete value.inherited_predecessor; },
    value => { value.inherited_predecessor.sha256 = '0'.repeat(64); },
    value => { value.predecessor_contract_id = 'P4-4-v1'; },
    value => { value.source_commit = approvedV1.commitSha; }]) {
    fixture = predecessorFixture([{ label: oldLabel, sql: oldSql, rows: rows(1) }], transform);
    check('missing or skipped V2/V1 lineage is rejected', () => assert.throws(() => c._test.loadBeforePredecessor(predecessorName, fixture)));
  }
  const completedV3 = [32, 40, 48, 56, 64].map(offset => ({
    label: 'snapshots/before/protected-channel_history-rows8-' + offset,
    sql: 'SELECT * FROM "channel_history" ORDER BY rowid LIMIT 8 OFFSET ' + offset,
    rows: rows(65).slice(offset, offset + 8), gzip: true,
  }));
  const failedV3 = { label: 'snapshots/before/protected-patches-rows8-0',
    sql: 'SELECT * FROM "patches" ORDER BY rowid LIMIT 8 OFFSET 0', completed: false, noResponse: true };
  fixture = predecessorFixture([{ label: oldLabel, sql: oldSql, rows: rows(65), completed: false }], () => {},
    recentPages, [...completedV3, failedV3]);
  network = 0; c._test.setTransport(noNetwork);
  const allHistory = await c._test.withBeforePredecessor(predecessorName, fixture,
    () => c._test.tablePages('snapshots/before', 'protected', 'channel_history', 65));
  check('V4 reuses complete gzip pages across three generations without requests', () => {
    assert.equal(network, 0); assert.deepEqual(allHistory.flatMap(page => c._test.d1Document(page).result[0].results), rows(65));
    assert.equal(allHistory[4].predecessor_origin.contract_id, 'P4-4-v3');
    assert(allHistory[4].decoded_body.path.startsWith('p/snapshots/before/'));
    assert(allHistory[0].body.path.startsWith('p/inputs/predecessor-before/snapshots/before/'));
  });
  c._test.setTransport(async (_url, _method, headers, body) => {
    network++; assert.equal(JSON.parse(body).sql, failedV3.sql); assert.equal(headers['accept-encoding'], 'gzip');
    return decodedResponse(gzipSync(Buffer.from(JSON.stringify({ success: true, result: [{ success: true,
      meta: { rows_written: 0, changed_db: false }, results: rows(3) }] }))), { 'content-encoding': 'gzip' });
  });
  await c._test.withBeforePredecessor(predecessorName, fixture,
    () => c._test.tablePages('snapshots/before', 'protected', 'patches', 3));
  check('V4 resumes missing patches read, not earlier successful gzip pages', () => {
    assert.equal(network, 1); assert.equal(s.read('p/' + failedV3.label + '.http.json').completed, false);
  });
  fixture = predecessorFixture([{ label: oldLabel, sql: oldSql, rows: rows(65), completed: false }], () => {}, recentPages,
    [{ ...completedV3[0], decodedBody: Buffer.from('{}') }]);
  c._test.setTransport(noNetwork);
  await assert.rejects(c._test.withBeforePredecessor(predecessorName, fixture,
    () => c._test.d1(completedV3[0].label, 'protected', completedV3[0].sql, true)), /HTTP_DECODED_MISMATCH/); checks++;
  check('self-consistent inherited sidecar hashes cannot replace wire truth', () => assert.equal(network, 1));

  // V4 recognizes only the approved C3 descriptor, not older accepted pairs.
  s.cp.spawnSync = spawnSync;
  for (const name of [...outputs.keys()]) if (name.startsWith('configure') || name === 'configured.json') outputs.delete(name);
  const stagingValues = { OTA_PREVIOUS_RELEASE_JSON: c.canonical(approvedPrevious.descriptor),
    OTA_APPROVED_BOOTSTRAP_BASELINE_SHA256: approvedPrevious.descriptorSha256 };
  const patches = []; let branchPosts = 0;
  c._test.setTransport(async (url, method, _headers, body) => {
    const endpoint = new URL(url).pathname, production = endpoint.includes('firmware-production');
    const keyPrefix = production ? '' : 'FIRMWARE_REHEARSAL_';
    if (method === 'PATCH') { const value = JSON.parse(body); patches.push(value.name); stagingValues[value.name] = value.value; return response('', {}, 204); }
    if (method === 'POST') { branchPosts++; throw Error('BRANCH_RECREATION_FORBIDDEN'); }
    if (endpoint.includes('/git/ref/heads/')) return response({ object: { sha: target.commitSha } });
    if (endpoint.endsWith('/actions/variables/OTA_BOOT_CHAIN_READY')) return response({ value: 'false' });
    if (endpoint.endsWith('/secrets')) return response({ total_count: names.length, secrets: names.map(name => ({ name: keyPrefix + name })) });
    if (endpoint.endsWith('/variables')) {
      const values = { OTA_BOOT_CHAIN_READY: 'false', TRACE_FIRMWARE_MIN_APP_VERSION_CODE: '0', TRACE_FIRMWARE_MIN_PROTOCOL_VERSION: '1',
        [keyPrefix + 'TRACE_R2_BUCKET']: c.resources[production ? 'production' : 'staging'].bucket, ...stagingValues };
      return response({ total_count: Object.keys(values).length, variables: Object.entries(values).map(([name, value]) => ({ name, value })) });
    }
    if (endpoint.endsWith('/deployment-branch-policies')) return response({ total_count: 1, branch_policies: [{ name: production ? 'main' : target.branch, type: 'branch' }] });
    if (endpoint.endsWith('/environments/firmware-' + (production ? 'production' : 'rehearsal'))) return response({
      deployment_branch_policy: { protected_branches: false, custom_branch_policies: true }, protection_rules: [{ type: 'required_reviewers',
        prevent_self_review: production, reviewers: [{ type: 'User', reviewer: { login: 'Eitan-S-23', id: 204050265 } }] }] });
    throw Error('UNKNOWN_V4_CONFIGURATION_ROUTE');
  });
  await c._test.configure(); checks++;
  check('C3 to C4 changes only descriptor and hash', () => assert.deepEqual(patches.sort(), ['OTA_APPROVED_BOOTSTRAP_BASELINE_SHA256', 'OTA_PREVIOUS_RELEASE_JSON']));
  check('C3 to C4 never recreates existing branch rule', () => assert.equal(branchPosts, 0));
  const resetConfiguration = () => {
    for (const name of [...outputs.keys()]) if (name.startsWith('configure') || name === 'configured.json') outputs.delete(name);
    patches.length = 0; branchPosts = 0;
  };
  resetConfiguration();
  await c._test.configure(); checks++;
  check('complete C4 pair is zero mutation no-op', () => assert.equal(patches.length + branchPosts, 0));
  for (const pair of [
    { OTA_PREVIOUS_RELEASE_JSON: c.canonical(approvedPrevious.descriptor), OTA_APPROVED_BOOTSTRAP_BASELINE_SHA256: target.descriptorSha256 },
    { OTA_PREVIOUS_RELEASE_JSON: c.canonical(target.descriptor), OTA_APPROVED_BOOTSTRAP_BASELINE_SHA256: approvedPrevious.descriptorSha256 },
    { OTA_PREVIOUS_RELEASE_JSON: c.canonical(approvedV1.descriptor), OTA_APPROVED_BOOTSTRAP_BASELINE_SHA256: approvedV1.descriptorSha256 },
    { OTA_PREVIOUS_RELEASE_JSON: c.canonical(approvedV2.descriptor), OTA_APPROVED_BOOTSTRAP_BASELINE_SHA256: approvedV2.descriptorSha256 },
    { OTA_PREVIOUS_RELEASE_JSON: c.canonical(approvedP41.descriptor), OTA_APPROVED_BOOTSTRAP_BASELINE_SHA256: approvedP41.descriptorSha256 },
  ]) {
    resetConfiguration(); Object.assign(stagingValues, pair);
    await assert.rejects(c._test.configure(), /UNEXPECTED_BASELINE_PAIR/); checks++;
    check('mixed or old pair rejected before mutations', () => assert.equal(patches.length + branchPosts, 0));
  }
  console.log(JSON.stringify({ ok: true, assertions: checks, cloud_operations: 0, filesystem_writes: 0,
    standard_signer: '@smithy/signature-v4', capture_bodies: [...outputs.keys()].filter(k => k.endsWith('.body')).length }));
}
async function realPredecessor() {
  const packet = JSON.parse(s.fs.readFileSync(0, 'utf8'));
  assert.equal(packet.scope, 'bundle.predecessor_plan');
  for (const item of packet.originals) {
    assert(item.path.startsWith(predecessorRoot + '/') && !item.path.split('/').includes('..'));
    const source = s.path.resolve(item.source), relative = s.path.relative(s.root, source);
    assert(relative && relative !== '..' && !relative.startsWith('..' + s.path.sep) && !s.path.isAbsolute(relative));
    outputs.set(item.path, s.fs.readFileSync(source));
  }
  const makeAnchor = value => {
    const bytes = Buffer.from(JSON.stringify(value)); outputs.set(predecessorName, bytes);
    return { status: 'FROZEN', contract_id: 'P4-4-v4', external_inputs: [{ id: 'predecessor-before',
      evidence_path: 'evidence/' + predecessorName, evidence_sha256: s.sha256(bytes), fingerprint: 'sha256:' + s.sha256(bytes) }] };
  };
  const previousMatrix = JSON.parse(outputs.get(predecessorRoot + '/' + packet.manifest.predecessor_final_matrix.path));
  const middleManifest = JSON.parse(outputs.get(predecessorRoot + '/' + packet.manifest.inherited_predecessor.path));
  const inheritedManifest = JSON.parse(outputs.get(inheritedRoot + '/' + middleManifest.inherited_predecessor.path));
  const inheritedMatrix = JSON.parse(outputs.get(ancestorRoot + '/' + inheritedManifest.predecessor_final_matrix.path));
  assert(/[A-F]/.test(inheritedManifest.predecessor_contract_sha256));
  assert(/[A-F]/.test(inheritedMatrix.contract_sha256));
  const inventory = c._test.loadBeforePredecessor(predecessorName, makeAnchor(packet.manifest));
  assert.equal(inventory.layers.length, 3); assert.equal(inventory.incomplete.size, 3);
  let requests = 0, complete = 0, incomplete = 0, gzipComplete = 0;
  c._test.setTransport(async () => { requests++; throw Error('REAL_FIXTURE_MUST_BE_OFFLINE'); });
  await c._test.withBeforePredecessor(predecessorName, makeAnchor(packet.manifest), async () => {
    for (const [root, manifest] of [[predecessorRoot, packet.manifest], [inheritedRoot, middleManifest], [ancestorRoot, inheritedManifest]]) {
      for (const file of manifest.files.filter(item => item.path.startsWith('snapshots/before/') && item.path.endsWith('.http.json'))) {
        const label = file.path.slice(0, -'.http.json'.length), envelope = JSON.parse(outputs.get(root + '/' + file.path));
        const reservation = JSON.parse(outputs.get(root + '/' + label + '-reservation.json'));
        const body = envelope.request ? JSON.parse(outputs.get(root + '/' + envelope.request.path)) : undefined;
        if (envelope.completed) {
          const restored = c._test.predecessorCapture(label, reservation.origin, envelope.path, { method: envelope.method, body });
          assert(restored && restored.wireBytes.equals(outputs.get(root + '/' + envelope.body.path)));
          assert(restored.bytes.equals(outputs.get(root + '/' + (envelope.decoded_body || envelope.body).path)));
          if (envelope.decoded_body) {
            gzipComplete++;
            assert.deepEqual(restored.json(), JSON.parse(outputs.get(root + '/' + envelope.decoded_body.path)));
            assert.equal(restored.envelope.decoded_body.path, root + '/' + envelope.decoded_body.path);
          }
          assert.equal(restored.envelope.started, envelope.started); assert.equal(restored.envelope.ended, envelope.ended);
          assert.equal(restored.envelope.predecessor_origin.contract_id, manifest.predecessor_contract_id); complete++;
        } else {
          assert.throws(() => c._test.d1Document(envelope), /D1_DOCUMENT_BINDING/); incomplete++;
        }
      }
    }
  });
  assert.equal(complete, 47); assert.equal(incomplete, 3); assert.equal(gzipComplete, 12); assert.equal(requests, 0);
  const wrong = structuredClone(packet.manifest); wrong.predecessor_contract_sha256 = 'F'.repeat(64);
  assert.throws(() => c._test.loadBeforePredecessor(predecessorName, makeAnchor(wrong)), /PREDECESSOR_CONTRACT_HASH/);
  wrong.predecessor_contract_sha256 = 'G'.repeat(64);
  assert.throws(() => c._test.loadBeforePredecessor(predecessorName, makeAnchor(wrong)));
  const matrixPath = predecessorRoot + '/' + packet.manifest.predecessor_final_matrix.path;
  const originalMatrixBytes = outputs.get(matrixPath);
  const changedMatrix = Buffer.from(JSON.stringify({ ...previousMatrix, contract_sha256: '0'.repeat(64) }));
  const changedManifest = structuredClone(packet.manifest);
  changedManifest.predecessor_final_matrix = { ...changedManifest.predecessor_final_matrix,
    size_bytes: changedMatrix.length, sha256: s.sha256(changedMatrix) };
  outputs.set(matrixPath, changedMatrix);
  assert.throws(() => c._test.loadBeforePredecessor(predecessorName, makeAnchor(changedManifest)), /PREDECESSOR_MATRIX_BINDING/);
  outputs.set(matrixPath, originalMatrixBytes);
  const gzipFile = packet.manifest.files.find(item => item.path.startsWith('snapshots/before/') && item.path.endsWith('.http.json')
    && JSON.parse(outputs.get(predecessorRoot + '/' + item.path)).decoded_body);
  const gzipEnvelope = JSON.parse(outputs.get(predecessorRoot + '/' + gzipFile.path));
  const decodedPath = predecessorRoot + '/' + gzipEnvelope.decoded_body.path, originalDecoded = outputs.get(decodedPath);
  outputs.set(decodedPath, Buffer.from('{}'));
  assert.throws(() => c._test.loadBeforePredecessor(predecessorName, makeAnchor(packet.manifest)), /PREDECESSOR_BYTES/);
  outputs.set(decodedPath, originalDecoded);
  console.log(JSON.stringify({ ok: true, source: packet.scope, complete_old_reads: complete, incomplete_old_reads: incomplete,
    gzip_old_reads: gzipComplete, inherited_sidecar_tamper_rejected: true,
    failed_original_inventory: inventory.incomplete.size,
    uppercase_originals_accepted: true, wrong_digest_rejected: true, wrong_matrix_digest_rejected: true,
    malformed_digest_rejected: true, network_requests: requests,
    filesystem_writes: 0 }));
}
(process.argv[2] === '--predecessor-stdin' ? realPredecessor()
  : process.argv[2] === '--retry-only' ? requestRetries() : main()).catch(error => {
    console.error(JSON.stringify({ ok: false, assertions: checks, error_code: error.code || 'OFFLINE_TEST_FAILED',
      error_name: error.name, source_location: error.stack?.match(/(?:test_p44_capture\.cjs|capture\.cjs):[0-9]+:[0-9]+/)?.[0] }));
    process.exitCode = 1;
  })
  .finally(() => { Object.assign(s, saved); c._test.setContext(undefined); c._test.setTransport(undefined);
    s.fs.existsSync = exists; s.cp.spawnSync = spawnSync;
    c._test.setHttp(undefined); c._test.setPrivateCapture(undefined); c._test.setMonotonic(undefined);
    c._test.setFrozen(undefined); c._test.setSleep(undefined); });
