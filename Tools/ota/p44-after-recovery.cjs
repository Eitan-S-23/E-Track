// After-only recovery. The C4 collector and every original remain unchanged.
const s = require('../acceptance/p44/run.cjs');
const capture = require('../acceptance/p44/capture.cjs');
const leaf = capture._test;
const { fs, path, assert, cp } = s;
const { gunzipSync } = require('node:zlib');
let DATA = path.join(s.root, 'docs/acceptance-contracts/P4-4-v6/evidence');
let CONTRACT = path.join(s.root, 'docs/acceptance-contracts/P4-4-v6.contract.json');
const SELF = 'Tools/ota/p44-after-recovery.cjs';
const C4 = '2756ca95e26ec636216313271708b3304d61a5cc';
const B4 = 'da37711799a21c4eb2c5d082dab1a7b81d028511';
const I4 = '7168568489ab0eb67a9e7a05106f245e7243421e';
const C5 = '9bfc48573a5eed190583411ac465bd847424a286';
const B5 = '21fa17f7da91a0d336ae1f1a7f1a93910beb2ab7';
const I5 = '7ae9112dcb8a910a541005df3421ed75fe8be3cb';
const C6_TOOL = '6fffaa25442bdcd863f3a3f4e93e20ebe180a2c1';
const C5_CONTRACT_SHA = 'ac95899a5dfdc8010dfc26ff350a2ffd94a72328412dd7a56705f72a99d83687';
const C5_MATRIX_SHA = '0c79b01bbb97d276aa2fce322c0ab7f4aa5be65bc183a1457c75ca69f4c1f5dc';
const LEGACY_PREDECESSOR = Object.freeze({ predecessor_commit: C5, predecessor_bundle_commit: B5, predecessor_index_commit: I5 });
let PREDECESSOR = LEGACY_PREDECESSOR;
const BRANCH = 'dev/p4-4/config-integration-20261018';
const REPO = '/repos/Eitan-S-23/E-Track';
let FIXTURE = 'inputs/after-recovery-v6.json';
let RECOVERY = 'recovery-v6/';
let COMMANDS = 'recovery-commands-v6/';
const OLD = 'snapshots/after/';
const TAIL = 'snapshots/after-tail-v6/';
let PRIVATE_WIRE = '.cache/p44/private/capture-failures/P4-4-v6/';
let PACKAGE_SPEC = null, PACKAGE_SPEC_PATH = null;
const LEGACY_RESERVATION = RECOVERY + 'after-reservation.json';
const RESUME_SCHEMA = 'p44-after-resume-reservation-v1';
const ATTEMPT_RESULT_SCHEMA = 'p44-after-attempt-result-v1';
const SCHEMA_SQL = 'SELECT name,type,sql FROM sqlite_master ORDER BY type,name';
const TOKEN_ID_SHA = '0c22488a9bee1355603d8d61faca06fcacbdafccfed8a4ba7dc490af7cacdedc';
const OFFLINE_IDENTITY = Object.freeze({
  source_path: '.cache/p41-dev-20261015/.cache/cf-readonly-20261015-r1/token-status.json',
  size_bytes: 483, sha256: '693ac971c7473e03f2fe526d117efe8b295cd403d24f8f66961ecb31ca563afa',
  id_pointer: '/body/result/id', id_sha256: TOKEN_ID_SHA, mode: 'offline-no-fallback',
});
const LEGACY_KEYS = ['first_missing', 'old_complete', 'old_failed', 'predecessor_bundle_commit', 'predecessor_commit',
  'predecessor_index_commit', 'product_commit', 'source_bundle_commit', 'started', 'tool_commit'];
const RESUME_KEYS = ['attempt', 'first_missing', 'head', 'predecessor_bundle_commit', 'predecessor_commit',
  'predecessor_index_commit', 'previous_attempts', 'product_commit', 'reused_complete', 'reused_failures', 'reused_records',
  'schema', 'source_bundle_commit', 'started', 'tool_commit', 'tool_sha256'];
const RESULT_KEYS = ['attempt', 'complete_labels', 'ended', 'error_code', 'failure_labels', 'failures', 'new_reads', 'ok',
  'reservation', 'reservation_sha256', 'schema', 'started'];
const RESULT_OPTIONAL = ['error_code'];
const RESULT_REQUIRED = RESULT_KEYS.filter(key => !RESULT_OPTIONAL.includes(key));
const roles = Object.keys(capture.resources);
const moduleRoot = path.join(s.root, 'app/bluetooth_flutter_Trace/cloudflare/update-service/worker/node_modules');
const canonical = capture.canonical;
const MISSING = new Error('RECOVERY_MISSING');
MISSING.code = 'RECOVERY_MISSING';

function relative(name) {
  assert(typeof name === 'string' && /^[a-zA-Z0-9_./-]+$/.test(name)
    && name.split('/').every(p => p && p !== '.' && p !== '..'), 'RECOVERY_PATH');
  return name;
}
function configurePackage(name) {
  assert(!PACKAGE_SPEC, 'RECOVERY_PACKAGE_ALREADY_SELECTED');
  relative(name);
  const value = JSON.parse(fs.readFileSync(s.guard(path.join(s.root, name))));
  assert.deepEqual(Object.keys(value).sort(), ['max_after_invocations', 'package', 'predecessor', 'round_id', 'schema', 'version']);
  assert.equal(value.schema, 'p44-after-package-v1');
  assert(Number.isSafeInteger(value.version) && value.version >= 7, 'RECOVERY_PACKAGE_VERSION');
  assert.equal(value.package, 'docs/acceptance-contracts/P4-4-v' + value.version);
  assert.equal(value.max_after_invocations, 2, 'RECOVERY_INVOCATION_LIMIT');
  assert.match(value.round_id, /^P44-[a-zA-Z0-9-]+$/);
  const previous = value.predecessor;
  assert.deepEqual(Object.keys(previous).sort(), ['bundle_commit', 'commit', 'contract_sha256', 'index_commit', 'matrix_sha256']);
  for (const key of ['commit', 'bundle_commit', 'index_commit']) assert.match(previous[key], /^[0-9a-f]{40}$/);
  for (const key of ['contract_sha256', 'matrix_sha256']) assert.match(previous[key], /^[0-9a-f]{64}$/);
  PACKAGE_SPEC = value; PACKAGE_SPEC_PATH = name;
  DATA = s.guard(path.join(s.root, value.package, 'evidence'));
  CONTRACT = s.guard(path.join(s.root, value.package + '.contract.json'));
  FIXTURE = 'inputs/after-recovery-v' + value.version + '.json';
  RECOVERY = 'recovery-v' + value.version + '/'; COMMANDS = 'recovery-commands-v' + value.version + '/';
  PRIVATE_WIRE = '.cache/p44/private/capture-failures/P4-4-v' + value.version + '/';
  PREDECESSOR = { predecessor_commit: previous.commit, predecessor_bundle_commit: previous.bundle_commit, predecessor_index_commit: previous.index_commit };
  return value;
}
function packageArgs() { return PACKAGE_SPEC ? ['--package-spec', PACKAGE_SPEC_PATH] : []; }
function contractId() { return 'P4-4-v' + (PACKAGE_SPEC?.version || 6); }
function attemptDir(number) { return TAIL + 'attempt-' + number + '/'; }
function makeIO(base = DATA) {
  base = s.guard(base);
  const sensitive = [], created = [];
  const safe = target => s.guard(target, base);
  const destination = name => safe(path.join(base, relative(name)));
  const readBytes = name => fs.readFileSync(destination(name));
  const fileRef = name => { const bytes = readBytes(name); return { path: name, size_bytes: bytes.length, sha256: s.sha256(bytes) }; };
  return { base, destination, readBytes, fileRef, created,
    readPrivateBytes: name => fs.readFileSync(s.guard(path.join(s.root, relative(name)))),
    exists: name => fs.existsSync(destination(name)),
    list(name) {
      const clean = typeof name === 'string' ? name.replace(/\/+$/, '') : name;
      const directory = destination(clean);
      assert(clean.length > 0, 'RECOVERY_DIRECTORY');
      if (!fs.existsSync(directory)) return [];
      const info = fs.lstatSync(directory);
      assert(info.isDirectory() && !info.isSymbolicLink(), 'RECOVERY_DIRECTORY');
      return fs.readdirSync(directory, { withFileTypes: true })
        .map(entry => {
          assert(!entry.isSymbolicLink(), 'RECOVERY_SYMLINK');
          return { name: entry.name, directory: entry.isDirectory() };
        }).sort((a, b) => a.name.localeCompare(b.name));
    },
    read: name => JSON.parse(readBytes(name)),
    addSensitive(value) { sensitive.push(value, Buffer.from(value).toString('base64')); },
    write(name, value) {
      const file = destination(name);
      assert(!fs.existsSync(file), 'RECOVERY_ORIGINAL_EXISTS');
      const bytes = Buffer.isBuffer(value) ? value : Buffer.from(typeof value === 'string' ? value : JSON.stringify(value, null, 2) + '\n');
      const decoded = bytes[0] === 0x1f && bytes[1] === 0x8b ? gunzipSync(bytes, { maxOutputLength: leaf.httpMaxBytes }) : bytes;
      for (const value of sensitive) assert(!bytes.includes(Buffer.from(value)) && !decoded.includes(Buffer.from(value)), 'RECOVERY_SENSITIVE_OUTPUT');
      fs.mkdirSync(safe(path.dirname(file)), { recursive: true }); destination(name);
      fs.writeFileSync(file, bytes, { flag: 'wx' }); created.push(name);
      return { path: name, size_bytes: bytes.length, sha256: s.sha256(bytes) };
    } };
}
function reference(io, ref, maximum = 256 * 1024 * 1024) {
  assert(ref && typeof ref === 'object' && !Array.isArray(ref), 'RECOVERY_REFERENCE');
  assert.deepEqual(Object.keys(ref).sort(), ['path', 'sha256', 'size_bytes'], 'RECOVERY_REFERENCE');
  relative(ref.path); assert.match(ref.sha256, /^[0-9a-f]{64}$/, 'RECOVERY_DIGEST');
  assert(Number.isSafeInteger(ref.size_bytes) && ref.size_bytes >= 0 && ref.size_bytes <= maximum, 'RECOVERY_SIZE');
  const bytes = io.readBytes(ref.path);
  assert.equal(bytes.length, ref.size_bytes, 'RECOVERY_SIZE'); assert.equal(s.sha256(bytes), ref.sha256, 'RECOVERY_DIGEST');
  return bytes;
}
function readDocument(io, ref, maximum) { return JSON.parse(reference(io, ref, maximum)); }
function configureHttp(http = require(path.join(moduleRoot, 'undici'))) {
  return { request: http.request, ProxyAgent: class extends http.ProxyAgent {
    constructor(options) {
      super({ ...options, proxyTls: { ...options.proxyTls, timeout: 30000 },
        requestTls: { ...options.requestTls, rejectUnauthorized: true, timeout: 30000 } });
    }
  } };
}
async function withLeaves(io, operation, options = {}) {
  const old = Object.fromEntries(['destination', 'readBytes', 'read', 'write', 'fileRef'].map(key => [key, s[key]]));
  for (const key of Object.keys(old)) s[key] = io[key];
  leaf.setHttp(configureHttp(options.http));
  leaf.setPrivateCapture((label, bytes) => {
    const directory = options.privateRoot || path.join(s.root, PRIVATE_WIRE);
    const file = s.guard(path.join(directory, relative(label) + '.wire.body'));
    assert(!fs.existsSync(file), 'PRIVATE_ORIGINAL_EXISTS');
    if (bytes === undefined) return;
    assert(Buffer.isBuffer(bytes) && bytes.length <= leaf.httpMaxBytes, 'PRIVATE_WIRE_BOUND');
    fs.mkdirSync(s.guard(path.dirname(file)), { recursive: true }); s.guard(file);
    fs.writeFileSync(file, bytes, { flag: 'wx' });
    return { path: path.relative(s.root, file).replaceAll('\\', '/'), size_bytes: bytes.length, sha256: s.sha256(bytes) };
  });
  try { return await operation(); }
  finally { Object.assign(s, old); leaf.setHttp(undefined); leaf.setPrivateCapture(undefined); }
}
function loadRecovery(io) {
  const input = io.read(FIXTURE);
  assert.equal(input.schema, 'p44-after-recovery-v2', 'RECOVERY_SCHEMA');
  if (PACKAGE_SPEC) assert.deepEqual(input.package_spec, PACKAGE_SPEC, 'RECOVERY_PACKAGE_BINDING');
  assert.equal(input.source_commit, C4); assert.equal(input.source_bundle_commit, B4); assert.equal(input.source_index_commit, I4);
  for (const [key, value] of Object.entries(PREDECESSOR)) assert.equal(input[key], value, 'RECOVERY_PREDECESSOR');
  assert.deepEqual(input.offline_identity, OFFLINE_IDENTITY, 'RECOVERY_OFFLINE_SOURCE');
  assert.equal(input.source_contract.path, 'recovery/c4.contract.json');
  assert.equal(input.source_matrix.path, 'recovery/c4.final-evidence-matrix.json');
  const contract = JSON.parse(reference(io, input.source_contract));
  const matrix = JSON.parse(reference(io, input.source_matrix));
  assert.equal(contract.contract_id, 'P4-4-v4'); assert.equal(contract.freeze_commit, C4); assert.equal(contract.status, 'FROZEN');
  assert.equal(matrix.contract_id, contract.contract_id); assert.equal(matrix.contract_sha256.toLowerCase(), s.sha256(reference(io, input.source_contract)));
  assert.equal(matrix.overall_result, 'EVIDENCE_GAP');
  const previousVersion = PACKAGE_SPEC ? PACKAGE_SPEC.version - 1 : 5;
  assert.equal(input.predecessor_contract.path, RECOVERY + 'c' + previousVersion + '.contract.json');
  assert.equal(input.predecessor_matrix.path, RECOVERY + 'c' + previousVersion + '.final-evidence-matrix.json');
  const previousContractBytes = reference(io, input.predecessor_contract), previousMatrixBytes = reference(io, input.predecessor_matrix);
  const previousHash = PACKAGE_SPEC?.predecessor.contract_sha256 || C5_CONTRACT_SHA;
  assert.equal(s.sha256(previousContractBytes), previousHash, 'RECOVERY_PREDECESSOR_CONTRACT');
  assert.equal(s.sha256(previousMatrixBytes), PACKAGE_SPEC?.predecessor.matrix_sha256 || C5_MATRIX_SHA, 'RECOVERY_PREDECESSOR_MATRIX');
  const previousContract = JSON.parse(previousContractBytes), previousMatrix = JSON.parse(previousMatrixBytes);
  assert.equal(previousContract.contract_id, 'P4-4-v' + previousVersion); assert.equal(previousContract.freeze_commit, PREDECESSOR.predecessor_commit);
  assert.equal(previousMatrix.contract_id, previousContract.contract_id); assert.equal(previousMatrix.contract_sha256.toLowerCase(), previousHash);
  assert.equal(previousMatrix.overall_result, 'EVIDENCE_GAP');
  for (const id of ['P44-CONFIGURATION', 'P44-RAW-RUNS', 'P44-REHEARSAL', 'P44-RAW-READBACK']) {
    const rows = matrix.criteria.filter(item => item.id === id);
    assert.equal(rows.length, 1); assert.equal(rows[0].result, 'PASS'); assert.equal(rows[0].execution, 'EXECUTED');
    const prior = previousMatrix.criteria.filter(item => item.id === id);
    assert.equal(prior.length, 1); assert.equal(prior[0].result, 'PASS'); assert.equal(prior[0].execution, 'REUSED');
    assert.equal(prior[0].origin_contract_sha256.toLowerCase(), s.sha256(reference(io, input.source_contract)));
    assert.equal(prior[0].origin_matrix_sha256.toLowerCase(), s.sha256(reference(io, input.source_matrix)));
  }
  assert(Array.isArray(input.files));
  const files = new Map();
  for (const ref of input.files) { relative(ref.path); assert(!files.has(ref.path), 'RECOVERY_DUPLICATE_FILE'); files.set(ref.path, ref); }
  const original = ref => { assert.deepEqual(files.get(ref.path), ref, 'RECOVERY_SOURCE_REFERENCE'); return reference(io, ref); };
  const document = ref => JSON.parse(original(ref));
  assert.equal(input.private_verify_failure.path, 'recovery/private-verify-failure.json');
  const privateFailure = document(input.private_verify_failure);
  assert.equal(privateFailure.error_code, 'ECONNRESET'); assert.equal(privateFailure.attempts, 1);
  assert(!Object.hasOwn(privateFailure, 'status') && !Object.hasOwn(privateFailure, 'body'), 'RECOVERY_PRIVATE_PHASE_UNKNOWN');
  for (const [key, name] of Object.entries({ target: 'target.json', before: 'snapshots/before.json', negatives: 'negatives.json',
    run_a: 'run-a/final.json', run_b: 'run-b/final.json', reviewer_attestation: 'reviewer-attestation.json' })) {
    assert.equal(input[key].path, name); original(input[key]);
  }
  const target = document(input.target), before = document(input.before), a = document(input.run_a), b = document(input.run_b);
  assert.equal(target.repository, 'Eitan-S-23/E-Track'); assert.equal(target.branch, BRANCH); assert.equal(target.commitSha, C4);
  assert.equal(target.versionName, '3.2.9'); assert.equal(target.descriptor.targetCommitSha, C4);
  assert.equal(target.descriptor.targetVersionName, '3.2.9'); assert.equal(target.descriptorSha256, s.sha256(canonical(target.descriptor)));
  const run = JSON.parse(original(b.final_run.body));
  capture.runIdentity(run, target); assert.equal(run.id, 39351100037); assert.equal(run.status, 'completed'); assert.equal(run.conclusion, 'success');
  const first = JSON.parse(original(a.final_run.body));
  capture.runIdentity(first, target); assert.equal(first.id, 39313672925); assert.equal(first.status, 'completed'); assert.equal(first.conclusion, 'failure');
  assert(Date.parse(first.updated_at) <= Date.parse(run.created_at), 'RECOVERY_RUN_ORDER');
  const finished = Date.parse(run.updated_at); assert(Number.isFinite(finished), 'RECOVERY_RUN_TIME');
  return { io, input, files, original, document, target, before, finished, run,
    old: new Map(), oldFailures: new Map(), complete: new Map(), failures: new Map(), attempts: [],
    used: new Set(), visited: new Set(), order: [], fresh: [], freshEntries: [],
    firstMissing: undefined, prefixFirstMissing: undefined, prefixOrder: [], fetching: false, attempt: null, nextAttempt: 2,
    initialComplete: null, initialFailures: null, toolCommit: null, reusedComplete: 0 };
}
function timing(ctx, record) {
  const start = Date.parse(record.started), end = Date.parse(record.ended);
  assert(Number.isFinite(start) && Number.isFinite(end) && end >= start && start >= ctx.finished, 'RECOVERY_AFTER_TIME');
}
function originFor(route) {
  assert(typeof route === 'string' && route.startsWith('/') && !/[\r\n\0]/.test(route), 'RECOVERY_ROUTE');
  if (route.startsWith('/accounts/')) return 'https://api.cloudflare.com';
  if (route.startsWith('/repos/')) return 'https://api.github.com';
  return 's3';
}
function encoding(record) {
  const headers = record.response_headers || {};
  const value = headers['content-encoding']; if (value === undefined) return 'identity';
  return value === 'gzip' ? 'gzip' : 'unsupported';
}
function bodyBytes(ctx, record) {
  assert(record.body, 'RECOVERY_BODY');
  const wire = reference(ctx.io, record.body, leaf.httpMaxBytes);
  const headers = record.response_headers || {};
  if (headers['content-length'] !== undefined) assert.equal(String(wire.length), String(headers['content-length']), 'RECOVERY_CONTENT_LENGTH');
  const type = encoding(record);
  assert.notEqual(type, 'unsupported', 'RECOVERY_ENCODING');
  if (type === 'gzip') {
    assert(record.decoded_body && record.decoded_body.size_bytes <= leaf.httpMaxBytes, 'RECOVERY_DECODED_REFERENCE');
    const decoded = reference(ctx.io, record.decoded_body, leaf.httpMaxBytes);
    assert(gunzipSync(wire, { maxOutputLength: leaf.httpMaxBytes }).equals(decoded), 'RECOVERY_DECODED_MISMATCH');
    return decoded;
  }
  assert.equal(record.decoded_body, undefined, 'RECOVERY_UNEXPECTED_DECODED');
  return wire;
}
function d1Payload(ctx, record) {
  const data = JSON.parse(bodyBytes(ctx, record).toString('utf8'));
  assert(data && data.success === true && Array.isArray(data.result) && data.result.length === 1
    && data.result[0].success === true, 'RECOVERY_D1');
  assert(data.result[0].meta.rows_written === 0 && data.result[0].meta.changed_db === false, 'RECOVERY_D1_WRITE');
  assert(Array.isArray(data.result[0].results), 'RECOVERY_ROWS');
  return data.result[0].results;
}
function response(ctx, record, method, route, expected = 200, sql) {
  assert.equal(record.completed, true, 'RECOVERY_INCOMPLETE'); assert.equal(record.method, method, 'RECOVERY_METHOD');
  assert.equal(record.path, route, 'RECOVERY_ROUTE'); assert((Array.isArray(expected) ? expected : [expected]).includes(record.status), 'RECOVERY_STATUS');
  timing(ctx, record);
  if (sql !== undefined) {
    assert(capture.sqlAllowed(sql)); assert.deepEqual(JSON.parse(reference(ctx.io, record.request)), { sql }, 'RECOVERY_SQL');
    return d1Payload(ctx, record);
  }
  assert.equal(record.decoded_body, undefined, 'RECOVERY_UNEXPECTED_DECODED');
  return bodyBytes(ctx, record);
}
const d1Route = role => '/accounts/[ACCOUNT]/d1/database/' + capture.resources[role].db + '/query';
const countSql = table => 'SELECT COUNT(*) AS count FROM "' + table + '"';
const rowSql = (table, offset) => 'SELECT * FROM "' + table + '" ORDER BY rowid LIMIT 8 OFFSET ' + offset;
function tables(schema) {
  assert(Array.isArray(schema));
  const names = new Set(), selected = [];
  for (const row of schema) {
    assert(row && typeof row === 'object' && !Array.isArray(row), 'RECOVERY_SCHEMA_ROW');
    assert.deepEqual(Object.keys(row).sort(), ['name', 'sql', 'type'], 'RECOVERY_SCHEMA_FIELDS');
    assert(typeof row.name === 'string' && /^[a-z_][a-z0-9_]*$/i.test(row.name), 'RECOVERY_SCHEMA_NAME');
    assert(['table', 'index', 'view', 'trigger'].includes(row.type), 'RECOVERY_SCHEMA_TYPE');
    assert(typeof row.sql === 'string' ? row.sql.trim().length > 0 : row.type === 'index' && row.sql === null, 'RECOVERY_SCHEMA_SQL');
    const key = row.type + '/' + row.name;
    assert(!names.has(key), 'RECOVERY_DUPLICATE_TABLE'); names.add(key);
    if (row.type !== 'table' || row.name.startsWith('sqlite_') || row.name.startsWith('_cf_')) continue;
    assert(!/WITHOUT\s+ROWID/i.test(row.sql), 'RECOVERY_TABLE'); selected.push(row.name);
  }
  return selected;
}
function totalCount(rows) {
  assert.equal(rows.length, 1); const total = rows[0].count;
  assert(Number.isSafeInteger(total) && total >= 0 && total <= 20000, 'RECOVERY_COUNT'); return total;
}
function xmlField(xml, name) {
  const all = [...xml.matchAll(new RegExp('<' + name + '>([^<]*)</' + name + '>', 'g'))];
  assert.equal(all.length, 1, 'RECOVERY_XML');
  return all[0][1].replace(/&(?:amp|lt|gt|quot|apos);/g, x => ({ '&amp;': '&', '&lt;': '<', '&gt;': '>', '&quot;': '"', '&apos;': "'" })[x]);
}
function beforeSchema(ctx, role) {
  const record = ctx.before.databases[role].schema;
  assert.equal(record.completed, true); assert.equal(record.method, 'POST');
  assert.equal(record.path, d1Route(role), 'RECOVERY_BEFORE_ROUTE');
  assert(capture.sqlAllowed(SCHEMA_SQL));
  assert.deepEqual(JSON.parse(reference(ctx.io, record.request)), { sql: SCHEMA_SQL }, 'RECOVERY_BEFORE_SQL');
  return d1Payload(ctx, record);
}
function failureName(label, attempt) { return label + '-request-failure-' + attempt + '.json'; }
function validateHeaderMap(headers) {
  assert(headers && typeof headers === 'object' && !Array.isArray(headers), 'RECOVERY_HEADERS');
  const seen = new Set();
  for (const [key, value] of Object.entries(headers)) {
    assert(/^[a-z0-9-]+$/.test(key) && !seen.has(key), 'RECOVERY_HEADER_NAME'); seen.add(key);
    assert(typeof value === 'string', 'RECOVERY_HEADER_VALUE');
    assert(!['authorization', 'cookie', 'set-cookie', 'proxy-authorization', 'x-api-key'].includes(key), 'RECOVERY_SENSITIVE_HEADER');
  }
}
function expectedReservation(record) {
  const value = { method: record.method, origin: originFor(record.path), path: record.path, started: record.started };
  if (record.request) value.request = record.request;
  if (record.request_headers) value.request_headers = record.request_headers;
  value.note = 'Reserved before request; a lost response is not permission to replay a mutation.';
  return value;
}
function validateFailureDocument(ctx, source, label, ref, index, record) {
  assert.equal(ref.path, source.dir + failureName(label, index), 'RECOVERY_FAILURE_PATH');
  const doc = readDocument(ctx.io, ref);
  const keys = ['attempt', 'ended', 'error_code', 'final_response_received', 'first_information', 'informational_count',
    'informational_seen', 'method', 'path', 'received_body_bytes', 'schema', 'started'];
  if (record.request) keys.push('request');
  assert.deepEqual(Object.keys(doc).sort(), keys.sort(), 'RECOVERY_FAILURE_FIELDS');
  assert.equal(doc.schema, 'p44-request-failure-v1'); assert.equal(doc.attempt, index);
  assert.equal(doc.method, record.method); assert.equal(doc.path, record.path);
  if (record.request) assert.deepEqual(doc.request, record.request, 'RECOVERY_FAILURE_REQUEST');
  assert.match(doc.error_code, /^[A-Z][A-Z0-9_]+$/, 'RECOVERY_FAILURE_CODE');
  assert.equal(doc.final_response_received, false); assert(Number.isSafeInteger(doc.received_body_bytes) && doc.received_body_bytes >= 0);
  assert(typeof doc.informational_seen === 'boolean'); assert(Number.isSafeInteger(doc.informational_count) && doc.informational_count >= 0);
  assert.equal(doc.informational_seen, doc.informational_count > 0, 'RECOVERY_INFORMATIONAL');
  if (doc.informational_seen) assert(doc.first_information && Number.isSafeInteger(doc.first_information.status));
  else assert.equal(doc.first_information, null);
  timing(ctx, doc);
  return doc;
}
const PARTIAL_FIELDS = ['partial_body_sha256', 'partial_body_size_bytes', 'partial_projection', 'private_wire', 'wire_received_size_bytes'];
function validatePartial(ctx, source, label, record) {
  assert(Number.isSafeInteger(record.status) && record.status >= 100 && record.status < 600, 'RECOVERY_STATUS');
  assert.equal(record.decoded_body, undefined, 'RECOVERY_PARTIAL_DECODED');
  assert.match(record.partial_body_sha256, /^[0-9a-f]{64}$/, 'RECOVERY_PARTIAL_DIGEST');
  assert(Number.isSafeInteger(record.partial_body_size_bytes) && record.partial_body_size_bytes >= 0
    && record.partial_body_size_bytes <= leaf.httpMaxBytes, 'RECOVERY_PARTIAL_SIZE');
  if (record.response_headers !== undefined) validateHeaderMap(record.response_headers);
  let raw;
  if (record.body !== undefined) {
    assert.equal(record.body.path, source.dir + label + '.partial.body', 'RECOVERY_PARTIAL_PATH');
    assert(record.response_headers, 'RECOVERY_PARTIAL_HEADERS');
    if (record.method === 'POST') {
      const encoding = record.response_headers['content-encoding'];
      assert(encoding === undefined || encoding.trim().toLowerCase() === 'identity', 'RECOVERY_PRIVATE_ENCODING');
    }
    assert.equal(record.private_wire, undefined, 'RECOVERY_PARTIAL_STORAGE');
    assert.equal(record.partial_projection, undefined, 'RECOVERY_PARTIAL_STORAGE');
    raw = reference(ctx.io, record.body, leaf.httpMaxBytes);
  } else if (record.private_wire !== undefined) {
    assert.equal(record.method, 'POST', 'RECOVERY_PRIVATE_METHOD');
    assert.equal(record.request_headers?.['accept-encoding'], 'gzip', 'RECOVERY_PRIVATE_ENCODING');
    if (record.response_headers !== undefined) {
      const encoding = record.response_headers['content-encoding'];
      assert(typeof encoding === 'string' && encoding.trim() && encoding.trim().toLowerCase() !== 'identity', 'RECOVERY_PRIVATE_ENCODING');
    }
    assert.equal(record.partial_projection, 'Encoded failure retained privately; public hash/length/location only', 'RECOVERY_PARTIAL_PROJECTION');
    let privateRoot = PRIVATE_WIRE;
    const originalName = source.dir + label + '.http.json';
    if (PACKAGE_SPEC && ctx.files.has(originalName)) {
      assert.deepEqual(ctx.document(ctx.files.get(originalName)), record, 'RECOVERY_PRIVATE_ORIGINAL');
      const match = record.private_wire.path.match(/^(\.cache\/p44\/private\/capture-failures\/P4-4-v[0-9]+\/)/);
      assert(match, 'RECOVERY_PRIVATE_PATH'); privateRoot = match[1];
    }
    assert.equal(record.private_wire.path, privateRoot + source.dir + label + '.wire.body', 'RECOVERY_PRIVATE_PATH');
    raw = reference({ readBytes: name => ctx.io.readPrivateBytes(name) }, record.private_wire, leaf.httpMaxBytes);
  } else {
    assert.equal(record.partial_projection, 'Known sensitive value: original hash/length only, no public plaintext copy', 'RECOVERY_PARTIAL_PROJECTION');
  }
  if (raw !== undefined) {
    assert.equal(raw.length, record.partial_body_size_bytes, 'RECOVERY_PARTIAL_SIZE');
    assert.equal(s.sha256(raw), record.partial_body_sha256, 'RECOVERY_PARTIAL_DIGEST');
  }
  if (record.wire_received_size_bytes !== undefined) assert(Number.isSafeInteger(record.wire_received_size_bytes)
    && record.wire_received_size_bytes >= record.partial_body_size_bytes, 'RECOVERY_PARTIAL_RECEIVED_SIZE');
}
function validateRecord(ctx, source, label, record, recordRef) {
  assert(record && typeof record === 'object' && !Array.isArray(record), 'RECOVERY_RECORD');
  assert(['POST', 'GET'].includes(record.method), 'RECOVERY_METHOD');
  assert(typeof record.path === 'string'); assert.equal(originFor(record.path), originFor(record.path));
  assert.equal(typeof record.completed, 'boolean');
  assert(Number.isSafeInteger(record.request_attempts) && [1, 2].includes(record.request_attempts), 'RECOVERY_ATTEMPTS');
  assert(Array.isArray(record.request_failures), 'RECOVERY_FAILURES');
  timing(ctx, record);
  const reservationRef = ctx.io.fileRef(source.dir + label + '-reservation.json');
  const reservation = readDocument(ctx.io, reservationRef);
  assert.deepEqual(reservation, expectedReservation(record), 'RECOVERY_RESERVATION');
  assert.equal(reservation.origin, originFor(record.path), 'RECOVERY_ORIGIN');
  if (record.request) {
    assert.equal(record.request.path, source.dir + label + '.request.json', 'RECOVERY_REQUEST_PATH');
    reference(ctx.io, record.request);
  }
  if (record.request_headers !== undefined) { validateHeaderMap(record.request_headers); assert.deepEqual(record.request_headers, { 'accept-encoding': 'gzip' }); }
  const failures = [];
  record.request_failures.forEach((ref, index) => {
    const doc = validateFailureDocument(ctx, source, label, ref, index + 1, record);
    if (index === 0 && record.request_attempts === 2) {
      assert.equal(doc.error_code, 'ECONNRESET', 'RECOVERY_RETRY_CODE');
      assert.equal(doc.final_response_received, false); assert.equal(doc.informational_seen, false);
      assert.equal(doc.received_body_bytes, 0);
    }
    failures.push({ doc, ref, index: index + 1 });
  });
  if (record.completed) {
    assert(PARTIAL_FIELDS.every(key => record[key] === undefined), 'RECOVERY_PARTIAL_AS_COMPLETE');
    assert.equal(record.request_failures.length, record.request_attempts - 1, 'RECOVERY_ATTEMPTS');
    assert.equal(record.error_code, undefined, 'RECOVERY_FAILED_RESPONSE');
    assert(Number.isSafeInteger(record.status) && record.status >= 100 && record.status < 600, 'RECOVERY_STATUS');
    assert(record.response_headers, 'RECOVERY_HEADERS'); validateHeaderMap(record.response_headers);
    assert(record.body, 'RECOVERY_BODY');
    assert.equal(record.body.path, source.dir + label + '.body', 'RECOVERY_BODY_PATH');
    if (record.request_attempts === 1) assert.equal(reservation.started, record.started, 'RECOVERY_RESERVATION_TIME');
    else {
      assert.equal(record.retry_reservation?.path, source.dir + label + '-retry-2-reservation.json', 'RECOVERY_RETRY_PATH');
      const retry = readDocument(ctx.io, record.retry_reservation);
      assert.equal(retry.schema, 'p44-request-retry-reservation-v1'); assert.equal(retry.attempt, 2);
      assert(Date.parse(retry.started) >= Date.parse(failures[0].doc.ended)
        && Date.parse(retry.started) <= Date.parse(record.ended), 'RECOVERY_RETRY_TIME');
      assert.equal(retry.delay_ms, 500);
      assert.deepEqual(retry.first_failure, record.request_failures[0], 'RECOVERY_RETRY_FIRST');
      assert(Date.parse(retry.started) >= Date.parse(failures[0].doc.started), 'RECOVERY_RETRY_ORDER');
      assert.deepEqual(Object.keys(retry).sort(), ['attempt', 'delay_ms', 'first_failure', 'method', 'path', 'request', 'schema', 'started']
        .filter(key => key !== 'request' || record.request).sort(), 'RECOVERY_RETRY_FIELDS');
      assert.equal(retry.method, record.method); assert.equal(retry.path, record.path);
      if (record.request) assert.deepEqual(retry.request, record.request);
    }
    if (record.method === 'POST') {
      assert(record.request, 'RECOVERY_REQUEST'); assert(record.request_headers, 'RECOVERY_REQUEST_HEADERS');
      assert.deepEqual(JSON.parse(reference(ctx.io, record.request)), JSON.parse(reference(ctx.io, record.request)));
      assert.equal(typeof JSON.parse(reference(ctx.io, record.request)).sql, 'string', 'RECOVERY_SQL_SHAPE');
    } else assert.equal(record.request, undefined, 'RECOVERY_REQUEST');
    if (record.method === 'POST' || record.decoded_body !== undefined) bodyBytes(ctx, record);
    if (record.method === 'POST') assert(record.decoded_body !== undefined || encoding(record) === 'identity');
    return { completed: true, failures };
  }
  const received = Object.hasOwn(record, 'status');
  assert.equal(record.request_failures.length, record.request_attempts - (received ? 1 : 0), 'RECOVERY_ATTEMPTS');
  assert.equal(typeof record.error_code, 'string'); assert.match(record.error_code, /^[A-Z][A-Z0-9_]+$/, 'RECOVERY_FAILURE_CODE');
  if (received) validatePartial(ctx, source, label, record);
  else {
    assert.equal(record.error_code, failures[failures.length - 1].doc.error_code, 'RECOVERY_FAILURE_CODE');
    assert(PARTIAL_FIELDS.every(key => record[key] === undefined)
      && record.body === undefined && record.decoded_body === undefined && record.response_headers === undefined, 'RECOVERY_PRE_RESPONSE_BODY');
  }
  assert.equal(record.retry_reservation === undefined, record.request_attempts === 1, 'RECOVERY_RETRY_UNEXPECTED');
  if (record.request_attempts === 2) {
    const retry = readDocument(ctx.io, record.retry_reservation);
    assert.equal(retry.schema, 'p44-request-retry-reservation-v1'); assert.equal(retry.attempt, 2);
    assert(Date.parse(retry.started) >= Date.parse(failures[0].doc.ended)
      && Date.parse(retry.started) <= Date.parse(record.ended), 'RECOVERY_RETRY_TIME'); assert.equal(retry.delay_ms, 500);
    assert.deepEqual(retry.first_failure, record.request_failures[0], 'RECOVERY_RETRY_FIRST');
    assert.deepEqual(Object.keys(retry).sort(), ['attempt', 'delay_ms', 'first_failure', 'method', 'path', 'request', 'schema', 'started']
      .filter(key => key !== 'request' || record.request).sort(), 'RECOVERY_RETRY_FIELDS');
    assert.equal(retry.method, record.method); assert.equal(retry.path, record.path);
    if (record.request) assert.deepEqual(retry.request, record.request);
  } else assert.equal(reservation.started, record.started, 'RECOVERY_RESERVATION_TIME');
  return { completed: false, failures };
}
function scanSource(ctx, source) {
  const entries = ctx.io.list(source.dir);
  const files = [], dirs = [];
  for (const entry of entries) (entry.directory ? dirs : files).push(entry.name);
  if (source.number !== 1) assert.equal(dirs.length, 0, 'RECOVERY_UNKNOWN_DIRECTORY');
  else assert(dirs.every(name => /^attempt-(?:[2-9]|[1-9][0-9]+)$/.test(name)), 'RECOVERY_UNKNOWN_DIRECTORY');
  const names = new Set(files), expected = new Set(), complete = new Map(), failures = new Map(), recordEnds = [];
  const recordRefs = new Set();
  if (source.number > 1) expected.add('attempt-reservation.json');
  const resultRef = source.number > 1 && ctx.io.exists(source.dir + 'attempt-result.json')
    ? ctx.io.fileRef(source.dir + 'attempt-result.json') : null;
  if (resultRef) expected.add('attempt-result.json');
  const httpNames = files.filter(name => name.endsWith('.http.json')).sort();
  for (const name of httpNames) {
    const label = name.slice(0, -'.http.json'.length);
    relative(source.dir + label);
    const recordRef = ctx.io.fileRef(source.dir + name);
    recordRefs.add(recordRef.path); expected.add(name);
    if (source.fixture) assert.deepEqual(ctx.files.get(recordRef.path), recordRef, 'RECOVERY_SOURCE_REFERENCE');
    const record = readDocument(ctx.io, recordRef);
    const checked = validateRecord(ctx, source, label, record, recordRef);
    assert(!complete.has(label) && !failures.has(label), 'RECOVERY_DUPLICATE_PREFIX');
    const reservationRef = ctx.io.fileRef(source.dir + label + '-reservation.json');
    const entry = { label, record, recordRef, source: source.number === 0 ? 'c4' : 'attempt-' + source.number,
      attempt: source.number, reservation: readDocument(ctx.io, reservationRef), reservationRef };
    expected.add(label + '-reservation.json');
    if (record.request) expected.add(label + '.request.json');
    if (record.body) expected.add(label + (record.completed ? '.body' : '.partial.body'));
    if (record.decoded_body) expected.add(label + '.decoded.body');
    if (record.retry_reservation) expected.add(label + '-retry-2-reservation.json');
    for (const failure of checked.failures) expected.add(failureName(label, failure.index));
    if (checked.completed) {
      complete.set(label, entry);
      if (source.number === 0) ctx.old.set(label, entry);
    } else {
      const list = [{ label, kind: 'record', ref: recordRef, record, source: entry.source, attempt: source.number }];
      failures.set(label, list);
      if (source.number === 0) ctx.oldFailures.set(label, list);
    }
    if (checked.completed && record.request_failures.length) {
      failures.set(label, record.request_failures.map((ref, index) => ({ label, kind: 'retry-prior', ref,
        doc: readDocument(ctx.io, ref), source: entry.source, attempt: source.number, index: index + 1 })));
    }
    recordEnds.push(record.ended);
    if (checked.completed) {
      assert(!ctx.complete.has(label), 'RECOVERY_DUPLICATE_COMPLETE');
      ctx.complete.set(label, entry); ctx.used.add(label);
    }
    ctx.visited.add(label); ctx.order.push(label);
  }
  const orphans = [...names].filter(name => !expected.has(name)), missingFiles = [...expected].filter(name => !names.has(name));
  if (orphans.length) assert.fail('RECOVERY_ORPHAN_FILE:' + orphans.sort().join(','));
  if (missingFiles.length) assert.fail('RECOVERY_MISSING_FILE:' + missingFiles.sort().join(','));
  if (source.fixture) {
    const fixtureFiles = [...ctx.files.keys()].filter(name => name.startsWith(source.dir));
    assert.deepEqual([...names].map(name => source.dir + name).sort(), fixtureFiles.sort(), 'RECOVERY_SOURCE_FILES');
  }
  const attemptReservationRef = source.attemptReservation ? ctx.io.fileRef(source.attemptReservation) : null;
  if (attemptReservationRef && attemptReservationRef.path.startsWith(source.dir)) {
    expected.add(attemptReservationRef.path.slice(source.dir.length));
  }
  const attempt = { number: source.number, dir: source.dir, reservationRef: attemptReservationRef,
    reservation: attemptReservationRef ? readDocument(ctx.io, attemptReservationRef) : null,
    complete, failures, records: httpNames, recordRefs, recordEnds, resultRef, result: null, ended: null };
  if (resultRef) {
    attempt.result = readDocument(ctx.io, resultRef);
    const value = attempt.result;
    assert.deepEqual(Object.keys(value).filter(key => !RESULT_OPTIONAL.includes(key)).sort(), RESULT_REQUIRED.slice().sort(), 'RECOVERY_ATTEMPT_RESULT_FIELDS');
    assert.equal(value.schema, ATTEMPT_RESULT_SCHEMA); assert.equal(value.attempt, attempt.number);
    assert.equal(value.started, attempt.reservation.started); assert.equal(typeof value.ok, 'boolean');
    assert.deepEqual(value.reservation, attempt.reservationRef); assert.equal(value.reservation_sha256, attempt.reservationRef.sha256);
    assert.deepEqual(value.complete_labels, [...complete.keys()].sort(), 'RECOVERY_ATTEMPT_RESULT_COMPLETE');
    assert.deepEqual(value.failure_labels, [...failures.keys()].sort(), 'RECOVERY_ATTEMPT_RESULT_FAILURES');
    assert.deepEqual(value.new_reads.slice().sort((a, b) => a.path.localeCompare(b.path)),
      [...recordRefs].map(path => ctx.io.fileRef(path)).sort((a, b) => a.path.localeCompare(b.path)), 'RECOVERY_ATTEMPT_RESULT_READS');
    assert.deepEqual(value.failures.slice().sort((a, b) => a.path.localeCompare(b.path)), failureRefsFor(attempt), 'RECOVERY_ATTEMPT_RESULT_FAILURE_REFS');
    assert.equal(value.ok, !Object.hasOwn(value, 'error_code'), 'RECOVERY_ATTEMPT_RESULT_OK');
    const terminal = [...failures.values()].flat().filter(entry => entry.kind === 'record');
    assert(!value.ok || terminal.length === 0, 'RECOVERY_ATTEMPT_RESULT_OK');
    if (!value.ok) {
      assert.match(value.error_code, /^[A-Z][A-Z0-9_]*$/);
      if (terminal.length) assert.equal(value.error_code, terminal[0].record.error_code, 'RECOVERY_ATTEMPT_RESULT_CODE');
    }
    const end = Date.parse(value.ended);
    assert(Number.isFinite(end) && end >= Date.parse(value.started), 'RECOVERY_ATTEMPT_RESULT_TIME');
    assert(recordEnds.every(time => end >= Date.parse(time)), 'RECOVERY_ATTEMPT_RESULT_TIME');
  }
  for (const [label, list] of failures) {
    const target = ctx.failures.get(label) || []; ctx.failures.set(label, target.concat(list));
  }
  attempt.ended = [attempt.reservation?.started, ...recordEnds, ...(resultRef ? [attempt.result.ended] : [])]
    .filter(Boolean).sort().at(-1);
  return attempt;
}
function failureRefsFor(attempt) {
  const refs = [];
  for (const list of attempt.failures.values()) for (const entry of list) {
    if (entry.kind === 'retry-prior') refs.push(entry.ref);
    else {
      refs.push(...entry.record.request_failures);
      if (Object.hasOwn(entry.record, 'status')) refs.push(entry.ref);
    }
  }
  return refs.sort((a, b) => a.path.localeCompare(b.path));
}
function scanAttempts(ctx) {
  const entries = ctx.io.list(TAIL);
  const dirs = entries.filter(entry => entry.directory).map(entry => entry.name);
  const files = entries.filter(entry => !entry.directory).map(entry => entry.name);
  assert(files.length > 0, 'RECOVERY_C6_MISSING');
  assert(dirs.every(name => /^attempt-(?:[2-9]|[1-9][0-9]+)$/.test(name)), 'RECOVERY_UNKNOWN_DIRECTORY');
  const numbers = dirs.map(name => Number(name.slice('attempt-'.length))).sort((a, b) => a - b);
  numbers.forEach((number, index) => assert.equal(number, index + 2, 'RECOVERY_ATTEMPT_GAP'));
  assert(ctx.io.exists(LEGACY_RESERVATION), 'RECOVERY_C6_MISSING');
  const sources = [{ dir: OLD, number: 0, fixture: true, attemptReservation: null },
    { dir: TAIL, number: 1, fixture: false, attemptReservation: LEGACY_RESERVATION }];
  for (const number of numbers) sources.push({ dir: attemptDir(number), number, fixture: false, attemptReservation: attemptDir(number) + 'attempt-reservation.json' });
  for (const source of sources) {
    const attempt = scanSource(ctx, source);
    if (source.number > 0) {
      assert.equal(source.attemptReservation, source.number === 1 ? LEGACY_RESERVATION : attemptDir(source.number) + 'attempt-reservation.json', 'RECOVERY_ATTEMPT_RESERVATION');
      ctx.attempts.push(attempt);
    }
  }
  ctx.nextAttempt = 2 + numbers.length;
}
function failureList(ctx) {
  const list = [];
  for (const [label, entries] of ctx.failures) for (const entry of entries)
    list.push({ label, source: entry.source, attempt: entry.attempt, kind: entry.kind, record: entry.ref });
  return list.sort((a, b) => a.attempt - b.attempt || a.label.localeCompare(b.label) || a.kind.localeCompare(b.kind));
}
function recordList(complete) {
  return [...complete.entries()].map(([label, entry]) => ({ label, record: entry.recordRef, reservation: entry.reservationRef }))
    .sort((a, b) => a.label.localeCompare(b.label) || a.record.path.localeCompare(b.record.path));
}
function attemptSummary(attempt) {
  const value = { attempt: attempt.number, reservation: attempt.reservationRef, reservation_sha256: attempt.reservationRef.sha256,
    complete: attempt.complete.size, failures: [...attempt.failures.values()].reduce((total, list) => total + list.length, 0),
    complete_labels: [...attempt.complete.keys()].sort(), failure_labels: [...attempt.failures.keys()].sort(), ended: attempt.ended || null };
  if (attempt.resultRef) { value.result = attempt.resultRef; value.result_sha256 = attempt.resultRef.sha256; }
  return value;
}
function validateAttemptHistory(ctx, order, oldFirst) {
  const priorComplete = new Map(ctx.old), priorFailures = new Map(ctx.oldFailures);
  const prior = [];
  let previousEnd = ctx.finished;
  for (const attempt of ctx.attempts) {
    const reservation = attempt.reservation;
    assert(reservation && typeof reservation === 'object', 'RECOVERY_ATTEMPT_RESERVATION');
    const start = Date.parse(reservation.started);
    assert(Number.isFinite(start) && start >= previousEnd, 'RECOVERY_ATTEMPT_TIME');
    if (attempt.number === 1) {
      assert.deepEqual(Object.keys(reservation).sort(), LEGACY_KEYS.slice().sort(), 'RECOVERY_ATTEMPT_FIELDS');
      assert.equal(reservation.product_commit, C4); assert.equal(reservation.source_bundle_commit, B4);
      for (const [key, value] of Object.entries(LEGACY_PREDECESSOR)) assert.equal(reservation[key], value, 'RECOVERY_ATTEMPT_PREDECESSOR');
      assert.equal(reservation.tool_commit, C6_TOOL, 'RECOVERY_ATTEMPT_TOOL');
      assert.equal(reservation.old_complete, ctx.old.size, 'RECOVERY_ATTEMPT_OLD_COMPLETE');
      assert.equal(reservation.old_failed, [...ctx.oldFailures.values()].reduce((n, list) => n + list.length, 0), 'RECOVERY_ATTEMPT_OLD_FAILED');
      assert.equal(reservation.first_missing, oldFirst, 'RECOVERY_ATTEMPT_FIRST');
    } else {
      assert.deepEqual(Object.keys(reservation).sort(), RESUME_KEYS.slice().sort(), 'RECOVERY_ATTEMPT_FIELDS');
      assert.equal(reservation.schema, RESUME_SCHEMA); assert.equal(reservation.attempt, attempt.number);
      assert.equal(reservation.product_commit, C4); assert.equal(reservation.source_bundle_commit, B4);
      if (PACKAGE_SPEC && ctx.files.has(attempt.reservationRef.path)) ctx.original(attempt.reservationRef);
      else for (const [key, value] of Object.entries(PREDECESSOR)) assert.equal(reservation[key], value, 'RECOVERY_ATTEMPT_PREDECESSOR');
      assert.match(reservation.tool_commit, /^[0-9a-f]{40}$/, 'RECOVERY_ATTEMPT_TOOL');
      assert.match(reservation.tool_sha256, /^[0-9a-f]{64}$/); assert.match(reservation.head, /^[0-9a-f]{40}$/);
      assert.equal(reservation.reused_complete, priorComplete.size, 'RECOVERY_ATTEMPT_REUSED');
      assert.deepEqual(reservation.reused_failures, listFailures(priorFailures), 'RECOVERY_ATTEMPT_FAILURES');
      assert.deepEqual(reservation.reused_records, recordList(priorComplete), 'RECOVERY_ATTEMPT_RECORDS');
      assert.deepEqual(reservation.previous_attempts, prior.map(attemptSummary), 'RECOVERY_ATTEMPT_PREVIOUS');
      const expectedFirst = order.find(label => !priorComplete.has(label)) || null;
      assert.equal(reservation.first_missing, expectedFirst, 'RECOVERY_ATTEMPT_FIRST');
    }
    const expectedFirst = attempt.number === 1 ? oldFirst : (order.find(label => !priorComplete.has(label)) || null);
    const startIndex = expectedFirst === null ? -1 : order.indexOf(expectedFirst);
    assert(startIndex >= 0, 'RECOVERY_ATTEMPT_FRONTIER');
    const segment = order.slice(startIndex, startIndex + attempt.complete.size);
    assert.equal(segment.length, attempt.complete.size, 'RECOVERY_ATTEMPT_BEYOND_FRONTIER');
    assert.deepEqual([...attempt.complete.keys()].sort(), segment.slice().sort(), 'RECOVERY_ATTEMPT_SEQUENCE');
    const terminal = [...attempt.failures.entries()].filter(([, list]) => list.some(entry => entry.kind === 'record'));
    assert(terminal.length <= 1, 'RECOVERY_MULTIPLE_TERMINAL_FAILURES');
    if (terminal.length) assert.equal(terminal[0][0], order[startIndex + attempt.complete.size], 'RECOVERY_FAILURE_POSITION');
    for (const [label, list] of attempt.failures) for (const entry of list)
      if (entry.kind === 'retry-prior') assert(attempt.complete.has(label), 'RECOVERY_RETRY_POSITION');
    for (const [label, entry] of attempt.complete) {
      const record = entry.record;
      assert(Date.parse(record.started) >= start, 'RECOVERY_ATTEMPT_TIME');
      priorComplete.set(label, entry);
    }
    for (const [label, list] of attempt.failures) priorFailures.set(label, (priorFailures.get(label) || []).concat(list));
    prior.push(attempt);
    previousEnd = Date.parse(attempt.ended);
  }
  ctx.priorFailures = priorFailures;
}
function listFailures(map) {
  const list = [];
  for (const [label, entries] of map) for (const entry of entries)
    list.push({ label, source: entry.source, attempt: entry.attempt, kind: entry.kind, record: entry.ref });
  return list.sort((a, b) => a.attempt - b.attempt || a.label.localeCompare(b.label) || a.kind.localeCompare(b.kind));
}
async function walkAll(ctx, ensure) {
  const result = { databases: {}, buckets: {}, github: {} };
  for (const role of roles) {
    const schema = await ensure.d1(role + '-schema', role, SCHEMA_SQL);
    assert.deepEqual(schema.rows, beforeSchema(ctx, role), 'RECOVERY_SCHEMA_DRIFT');
    const records = {};
    for (const name of tables(schema.rows)) {
      const count = await ensure.d1(role + '-' + name + '-count', role, countSql(name));
      const total = totalCount(count.rows), pages = [], ids = new Set();
      for (let offset = 0; offset < total; offset += 8) {
        const page = await ensure.d1(role + '-' + name + '-rows8-' + offset, role, rowSql(name, offset));
        assert.equal(page.rows.length, Math.min(8, total - offset), 'RECOVERY_PAGE_COUNT');
        for (const row of page.rows) if (Object.hasOwn(row, 'id')) {
          const id = canonical(row.id); assert(!ids.has(id), 'RECOVERY_DUPLICATE_ROW'); ids.add(id);
        }
        pages.push(page.envelope);
      }
      records[name] = { count: count.envelope, pages };
    }
    result.databases[role] = { schema: schema.envelope, tables: records };
    result.buckets[role] = await walkBucket(ctx, ensure, role);
  }
  const github = await walkGitHub(ctx, ensure);
  result.target_tag = github.target_tag; result.github.releases = github.releases; result.github.assets = github.assets;
  result.protected_configuration = await walkConfiguration(ctx, ensure);
  return result;
}
async function walkBucket(ctx, ensure, role) {
  const resource = capture.resources[role];
  if (role === 'production') {
    const route = '/' + resource.bucket + '/?list-type=2&max-keys=1000';
    const got = await ensure.s3(role + '-r2-1', role, route);
    const xml = got.bytes.toString('utf8');
    assert.equal(xmlField(xml, 'Name'), resource.bucket); assert.equal(xmlField(xml, 'IsTruncated'), 'false');
    return [got.envelope];
  }
  const pages = [], tokens = new Set(); let continuation;
  for (let number = 1; number <= 20; number++) {
    const query = new URLSearchParams({ 'list-type': '2', 'max-keys': '1000' }); if (continuation) query.set('continuation-token', continuation);
    const route = '/' + resource.bucket + '/?' + query;
    const got = await ensure.s3(role + '-r2-' + number, role, route);
    const xml = got.bytes.toString('utf8'); assert.equal(xmlField(xml, 'Name'), resource.bucket); pages.push(got.envelope);
    const truncated = xmlField(xml, 'IsTruncated'); assert(['true', 'false'].includes(truncated));
    if (truncated === 'false') return pages;
    assert(number < 20); const next = xmlField(xml, 'NextContinuationToken');
    assert(next && !tokens.has(next), 'RECOVERY_R2_CURSOR'); tokens.add(next); continuation = next;
  }
  throw new Error('RECOVERY_R2_LIMIT');
}
function nextLink(headers) {
  const value = headers?.link; if (!value) return null;
  for (const part of value.split(',')) {
    const match = part.match(/<([^>]+)>\s*;\s*rel="next"/); if (match) return match[1];
  }
  return null;
}
async function walkGitHub(ctx, ensure) {
  const releases = await ensure.pages('releases', REPO + '/releases');
  assert(!releases.items.some(value => value.tag_name?.startsWith('mcu-e-track-at32f435-v')), 'FORMAL_LINEAGE_PRESENT');
  const tag = await ensure.capture('target-tag', 'https://api.github.com', REPO + '/git/ref/tags/mcu-e-track-at32f435-v' + ctx.target.versionName, [200, 404]);
  const peeled = [];
  if (tag.envelope.status === 200) {
    let object = tag.json().object;
    for (let depth = 0; object?.type === 'tag' && depth < 7; depth++) {
      assert.match(object.sha, /^[0-9a-f]{40}$/);
      const next = await ensure.capture('target-tag-' + depth, 'https://api.github.com', REPO + '/git/tags/' + object.sha);
      peeled.push(next.envelope); object = next.json().object;
    }
    assert(object?.type === 'commit' && object.sha === C4, 'RECOVERY_PRODUCT_TAG');
  }
  const assets = {};
  for (const release of releases.items) {
    assert(Number.isSafeInteger(release.id) && release.id > 0, 'RECOVERY_RELEASE_ID');
    assets[release.id] = (await ensure.pages('assets-' + release.id, REPO + '/releases/' + release.id + '/assets')).records;
  }
  return { target_tag: { ref: tag.envelope, peeled }, releases: releases.records, assets };
}
async function walkConfiguration(ctx, ensure) {
  const result = {};
  for (const role of ['production', 'rehearsal']) {
    const route = REPO + '/environments/firmware-' + role, stem = 'config-' + role;
    const config = await ensure.capture(stem + '-environment', 'https://api.github.com', route);
    const vars = await ensure.pages(stem + '-variables', route + '/variables', 'variables');
    const names = await ensure.pages(stem + '-secrets', route + '/secrets', 'secrets');
    const rules = await ensure.pages(stem + '-branches', route + '/deployment-branch-policies', 'branch_policies');
    const previous = ctx.before.protected_configuration[role];
    const original = JSON.parse(reference(ctx.io, previous.configuration.body)), value = config.json();
    for (const key of ['id', 'name', 'protection_rules', 'deployment_branch_policy', 'can_admins_bypass']) assert.deepEqual(value[key], original[key], 'RECOVERY_ENV_DRIFT');
    assert.deepEqual(value.deployment_branch_policy, { protected_branches: false, custom_branch_policies: true });
    const reviewer = value.protection_rules.find(rule => rule.type === 'required_reviewers');
    assert.equal(reviewer.prevent_self_review, role === 'production'); assert.equal(reviewer.reviewers.length, 1);
    assert.equal(reviewer.reviewers[0].reviewer.login, 'Eitan-S-23'); assert.equal(reviewer.reviewers[0].reviewer.id, 204050265);
    const values = Object.fromEntries(vars.items.map(item => [item.name, item.value]));
    assert.equal(Object.keys(values).length, vars.items.length, 'RECOVERY_DUPLICATE_VARIABLE');
    assert.deepEqual(values, previous.values, 'RECOVERY_VARIABLE_DRIFT'); assert.equal(values.OTA_BOOT_CHAIN_READY, 'false');
    assert.equal(values.TRACE_FIRMWARE_MIN_APP_VERSION_CODE, String(ctx.target.minAppVersionCode));
    assert.equal(values.TRACE_FIRMWARE_MIN_PROTOCOL_VERSION, String(ctx.target.minProtocolVersion));
    const keyPrefix = role === 'production' ? '' : 'FIRMWARE_REHEARSAL_';
    assert.equal(values[keyPrefix + 'TRACE_R2_BUCKET'], capture.resources[role === 'production' ? role : 'staging'].bucket);
    for (const name of ['CLOUDFLARE_ACCOUNT_ID', 'OTA_AES_KEY', 'TRACE_DEPLOY_TOKEN', 'TRACE_UPDATE_SERVICE_URL', 'TRACE_R2_ACCESS_KEY_ID', 'TRACE_R2_SECRET_ACCESS_KEY']) {
      assert(names.items.some(item => item.name === keyPrefix + name), 'RECOVERY_MISSING_SECRET');
    }
    if (role === 'rehearsal') {
      assert.equal(values.OTA_PREVIOUS_RELEASE_JSON, canonical(ctx.target.descriptor));
      assert.equal(values.OTA_APPROVED_BOOTSTRAP_BASELINE_SHA256, ctx.target.descriptorSha256);
    }
    const secretIdentity = values => values.map(item => {
      for (const name of ['name', 'created_at', 'updated_at']) assert(typeof item[name] === 'string', 'RECOVERY_SECRET_METADATA');
      return { name: item.name, created_at: item.created_at, updated_at: item.updated_at };
    }).sort((a, b) => a.name.localeCompare(b.name));
    const oldNames = secretIdentity(previous.secrets.flatMap(record => JSON.parse(reference(ctx.io, record.body)).secrets));
    assert.deepEqual(secretIdentity(names.items), oldNames, 'RECOVERY_SECRET_DRIFT');
    assert.deepEqual(rules.items, previous.rules, 'RECOVERY_BRANCH_RULE_DRIFT');
    if (role === 'production') assert.deepEqual(rules.items.map(rule => [rule.name, rule.type]), [['main', 'branch']]);
    else {
      assert(rules.items.every(rule => rule.type === 'branch' && ['dev/p4-1/unattended-20261015', BRANCH].includes(rule.name)));
      assert(rules.items.some(rule => rule.name === BRANCH));
    }
    result[role] = { configuration: config.envelope, variables: vars.records, secrets: names.records, branches: rules.records, values, rules: rules.items };
  }
  const gate = await ensure.capture('config-repository-gate', 'https://api.github.com', REPO + '/actions/variables/OTA_BOOT_CHAIN_READY');
  assert.equal(gate.json().value, 'false');
  const remote = await ensure.capture('config-tool-ref', 'https://api.github.com', REPO + '/git/ref/heads/' + BRANCH);
  assert.equal(remote.json().object.sha, ctx.toolCommit, 'RECOVERY_REMOTE_TOOL_DRIFT');
  result.repository_gate = gate.envelope; result.tool_ref = remote.envelope;
  result.product_commit = C4; result.tool_commit = ctx.toolCommit; return result;
}
function makeEnsure(ctx, api, fetch, pairFor, stagingFor) {
  function reused(label) {
    const entry = ctx.complete.get(label); if (!entry) return null;
    assert(!ctx.visited.has(label), 'RECOVERY_PREFIX_REPLAY');
    ctx.visited.add(label); ctx.used.add(label); ctx.order.push(label); return entry;
  }
  function prepare(label, role) {
    if (ctx.visited.has(label)) throw Object.assign(new Error('RECOVERY_PREFIX_REPLAY'), { code: 'RECOVERY_PREFIX_REPLAY' });
    ctx.visited.add(label); ctx.order.push(label);
    if (!fetch) { if (ctx.firstMissing === undefined) ctx.firstMissing = label; throw MISSING; }
    if (!ctx.fetching) throw Object.assign(new Error('RECOVERY_NOT_FETCHING'), { code: 'RECOVERY_NOT_FETCHING' });
    if (!ctx.fetchedOnce) {
      assert.equal(label, ctx.prefixFirstMissing, 'RECOVERY_FIRST_REQUEST'); ctx.fetchedOnce = true;
    }
    if (role) assert.notEqual(role, 'production', 'RECOVERY_PRODUCTION_REPLAY');
    if (!ctx.attempt) startAttempt(ctx);
  }
  async function d1(label, role, sql) {
    allowedRead(role, sql);
    const entry = reused(label);
    if (entry) return { envelope: entry.record, rows: response(ctx, entry.record, 'POST', d1Route(role), 200, sql) };
    prepare(label, role);
    const stem = ctx.attemptDir + label;
    const result = await api.d1(stem, role, sql);
    const fresh = registerFresh(ctx, label, 'd1', role, result.envelope, stem);
    return { envelope: fresh.record, rows: response(ctx, fresh.record, 'POST', d1Route(role), 200, sql) };
  }
  async function s3(label, role, route) {
    const entry = reused(label);
    if (entry) return { envelope: entry.record, bytes: response(ctx, entry.record, 'GET', route) };
    prepare(label, role);
    const pair = role === 'protected' ? await pairFor() : stagingFor();
    const result = await api.s3(ctx.attemptDir + label, role, route, pair);
    const fresh = registerFresh(ctx, label, 's3', role, result.envelope, ctx.attemptDir + label);
    return { envelope: fresh.record, bytes: response(ctx, fresh.record, 'GET', route) };
  }
  async function gh(label, origin, route, expected) {
    const entry = reused(label);
    if (entry) {
      const body = response(ctx, entry.record, 'GET', route, expected);
      return { envelope: entry.record, json: () => JSON.parse(body) };
    }
    prepare(label);
    const result = await api.capture(ctx.attemptDir + label, origin, route, { expected });
    const fresh = registerFresh(ctx, label, 'github', undefined, result.envelope, ctx.attemptDir + label);
    return { envelope: fresh.record, json: () => JSON.parse(response(ctx, fresh.record, 'GET', route, expected)) };
  }
  async function pages(label, route, field) {
    const items = [], records = [];
    for (let page = 1; page <= 30; page++) {
      const current = route + (route.includes('?') ? '&' : '?') + 'per_page=100&page=' + page;
      const got = await gh(label + '-' + page, 'https://api.github.com', current);
      const body = got.json(), batch = field ? body[field] : body;
      assert(Array.isArray(batch), 'RECOVERY_PAGE_SHAPE'); records.push(got.envelope); items.push(...batch);
      const next = nextLink(got.envelope.response_headers);
      if (!next) { if (field) assert.equal(body.total_count, items.length, 'RECOVERY_PAGE_COUNT'); return { items, records }; }
      const gotUrl = new URL(next), wanted = new URL('https://api.github.com' + route + (route.includes('?') ? '&' : '?') + 'per_page=100&page=' + (page + 1));
      assert.equal(gotUrl.origin + gotUrl.pathname, wanted.origin + wanted.pathname, 'RECOVERY_PAGE_LINK_ORIGIN');
      assert.deepEqual([...gotUrl.searchParams].sort(), [...wanted.searchParams].sort(), 'RECOVERY_PAGE_LINK_QUERY');
    }
    throw new Error('RECOVERY_PAGE_LIMIT');
  }
  return { d1, s3, capture: gh, pages };
}
function registerFresh(ctx, label, kind, role, envelope, stem) {
  const recordPath = stem + '.http.json';
  assert(ctx.io.exists(recordPath), 'RECOVERY_FRESH_RECORD');
  const recordRef = ctx.io.fileRef(recordPath);
  const reservationRef = ctx.io.fileRef(stem + '-reservation.json');
  const reservation = readDocument(ctx.io, reservationRef);
  const source = { dir: ctx.attemptDir, number: ctx.attempt, fixture: false };
  const checked = validateRecord(ctx, source, label, envelope, recordRef);
  const entry = { label, record: envelope, recordRef, reservation, reservationRef,
    source: 'attempt-' + ctx.attempt, attempt: ctx.attempt };
  const attempt = ctx.attempts.find(item => item.number === ctx.attempt);
  if (checked.completed) {
    ctx.complete.set(label, entry);
    attempt.complete.set(label, entry);
  } else {
    const list = checked.failures.map(failure => ({ label, kind: 'record', ref: recordRef, record: envelope,
      source: entry.source, attempt: ctx.attempt, failure: failure.doc }));
    attempt.failures.set(label, list); ctx.failures.set(label, (ctx.failures.get(label) || []).concat(list));
  }
  if (checked.completed && envelope.request_failures.length) {
    const list = envelope.request_failures.map((ref, index) => ({ label, kind: 'retry-prior', ref,
      doc: readDocument(ctx.io, ref), source: entry.source, attempt: ctx.attempt, index: index + 1 }));
    attempt.failures.set(label, list); ctx.failures.set(label, (ctx.failures.get(label) || []).concat(list));
  }
  ctx.fresh.push(label); ctx.freshEntries.push({ label, kind, role: role || null, record: recordRef });
  return entry;
}
function startAttempt(ctx) {
  assert(!ctx.attempt && !ctx.io.exists('snapshots/after.json') && !ctx.io.exists(RECOVERY + 'after-result.json'), 'RECOVERY_ALREADY_EXECUTED');
  const number = ctx.nextAttempt;
  assert(number >= 2 && !ctx.io.exists(attemptDir(number)), 'RECOVERY_ATTEMPT_EXISTS');
  const started = new Date().toISOString();
  const reservation = { schema: RESUME_SCHEMA, attempt: number, tool_commit: ctx.toolCommit,
    tool_sha256: s.sha256(fs.readFileSync(s.guard(path.join(s.root, SELF)))), head: s.git(['rev-parse', 'HEAD']),
    product_commit: C4, source_bundle_commit: B4, ...PREDECESSOR, started,
    first_missing: ctx.prefixFirstMissing, reused_complete: ctx.initialComplete.size,
    reused_failures: listFailures(ctx.failures), reused_records: recordList(ctx.initialComplete),
    previous_attempts: ctx.attempts.map(attemptSummary) };
  const reservationRef = ctx.io.write(attemptDir(number) + 'attempt-reservation.json', reservation);
  ctx.attempt = number; ctx.attemptDir = attemptDir(number);
  ctx.attempts.push({ number, dir: ctx.attemptDir, reservationRef, reservation, complete: new Map(), failures: new Map(),
    records: [], result: null, resultRef: null, ended: null });
}
function attemptResult(ctx, ok, error) {
  const attempt = ctx.attempts.find(item => item.number === ctx.attempt);
  assert(attempt && !ctx.io.exists(attempt.dir + 'attempt-result.json'), 'RECOVERY_ATTEMPT_RESULT_EXISTS');
  // The HTTP leaf persists failures before throwing, so its files, not the
  // success-return path's in-memory maps, own the attempt's final inventory.
  const scanned = scanSource({ ...ctx, complete: new Map(), failures: new Map(), old: new Map(), oldFailures: new Map(),
    used: new Set(), visited: new Set(), order: [] },
  { dir: attempt.dir, number: attempt.number, fixture: false, attemptReservation: attempt.dir + 'attempt-reservation.json' });
  Object.assign(attempt, scanned);
  const reads = ctx.io.list(attempt.dir).filter(entry => !entry.directory && entry.name.endsWith('.http.json'))
    .map(entry => ctx.io.fileRef(attempt.dir + entry.name)).sort((a, b) => a.path.localeCompare(b.path));
  const value = { schema: ATTEMPT_RESULT_SCHEMA, attempt: attempt.number, ok,
    reservation: attempt.reservationRef, reservation_sha256: attempt.reservationRef.sha256,
    started: attempt.reservation.started, ended: new Date().toISOString(),
    complete_labels: [...attempt.complete.keys()].sort(), failure_labels: [...attempt.failures.keys()].sort(),
    failures: failureRefsFor(attempt), new_reads: reads,
    ...(ok ? {} : { error_code: /^[A-Z][A-Z0-9_]*$/.test(error?.code || '') ? error.code : 'RECOVERY_FAILED' }) };
  const ref = ctx.io.write(attempt.dir + 'attempt-result.json', value);
  attempt.resultRef = ref; attempt.result = value; attempt.ended = value.ended;
  return ref;
}
async function validatePrefix(ctx) {
  scanAttempts(ctx);
  assert.deepEqual(Object.keys(ctx.before.databases).sort(), roles.slice().sort(), 'RECOVERY_BEFORE_ROLES');
  for (const role of roles) tables(beforeSchema(ctx, role));
  const c4Failed = listFailures(ctx.oldFailures).filter(item => item.kind === 'record');
  assert.deepEqual(ctx.input.after_complete.slice().sort((a, b) => a.path.localeCompare(b.path)),
    [...ctx.old.values()].map(entry => entry.recordRef).sort((a, b) => a.path.localeCompare(b.path)), 'RECOVERY_PREFIX_SET');
  assert.deepEqual(ctx.input.after_failed.slice().sort((a, b) => a.path.localeCompare(b.path)),
    c4Failed.map(item => item.record).sort((a, b) => a.path.localeCompare(b.path)), 'RECOVERY_FAILED_SET');
  ctx.initialComplete = new Map(ctx.complete); ctx.initialFailures = new Map();
  for (const [label, list] of ctx.failures) ctx.initialFailures.set(label, list.slice());
  ctx.visited = new Set(); ctx.used = new Set(); ctx.order = []; ctx.firstMissing = undefined;
  const ensure = makeEnsure(ctx, null, false, null, null);
  try { await walkAll(ctx, ensure); } catch (error) { if (error !== MISSING && error.code !== 'RECOVERY_MISSING') throw error; }
  const order = [...ctx.order];
  assert.equal(ctx.firstMissing === undefined, order.length === ctx.complete.size, 'RECOVERY_FRONTIER');
  const oldFirst = order.find(label => !ctx.old.has(label));
  if (oldFirst === undefined) {
    // A complete C4 plan cannot have a later missing-tail attempt.
    assert(ctx.old.size === order.length, 'RECOVERY_C4_FRONTIER');
  } else assert.equal(ctx.old.size, order.indexOf(oldFirst), 'RECOVERY_C4_PREFIX');
  assert.equal(ctx.used.size, ctx.initialComplete.size, 'RECOVERY_UNUSED_PREFIX');
  for (const label of ctx.failures.keys()) assert(ctx.visited.has(label), 'RECOVERY_UNKNOWN_FAILURE');
  assert(ctx.attempts.length > 0, 'RECOVERY_C6_MISSING');
  validateAttemptHistory(ctx, order, oldFirst);
  ctx.prefixOrder = order; ctx.prefixFirstMissing = ctx.firstMissing;
  ctx.visited = new Set(); ctx.used = new Set(); ctx.order = []; ctx.firstMissing = undefined;
  return ctx;
}
function admit(ctx, contract, head, report, contractHash) {
  assert.equal(contract.contract_id, contractId()); assert.equal(contract.status, 'FROZEN');
  assert.match(contract.freeze_commit, /^[0-9a-f]{40}$/); assert.notEqual(contract.freeze_commit, C4);
  assert.equal(head, contract.freeze_commit, 'RECOVERY_TOOL_HEAD');
  assert.equal(report?.schema, 'p44-after-admission-v1', 'RECOVERY_ADMISSION'); assert.equal(report.ok, true);
  assert.equal(report.freeze_commit, contract.freeze_commit); assert.equal(report.source_commit, C4); assert.equal(report.source_bundle_commit, B4);
  for (const [key, value] of Object.entries(PREDECESSOR)) assert.equal(report[key], value, 'RECOVERY_ADMISSION_PREDECESSOR');
  assert.match(contractHash, /^[0-9a-f]{64}$/);
  assert.equal(report.contract_sha256.toLowerCase(), contractHash, 'RECOVERY_ADMISSION_CONTRACT');
  const external = contract.external_inputs.filter(item => item.evidence_path === 'evidence/' + FIXTURE);
  assert.equal(external.length, 1); assert.equal(external[0].evidence_sha256.toLowerCase(), s.sha256(ctx.io.readBytes(FIXTURE)));
  assert.equal(ctx.io.read(COMMANDS + 'formal-precheck.json').exitCode, 0, 'RECOVERY_PRECHECK');
  for (const kind of ['before', 'negatives']) {
    const result = ctx.io.read(RECOVERY + kind + '-result.json');
    assert.equal(result.schema, 'p44-after-existing-v1'); assert.equal(result.ok, true); assert.equal(result.kind, kind);
    assert.deepEqual(result.source, ctx.input[kind]); assert.equal(result.source_commit, C4); assert.equal(result.source_bundle_commit, B4); assert.equal(result.platform_operations, 0);
    for (const [key, value] of Object.entries(PREDECESSOR)) assert.equal(result[key], value, 'RECOVERY_EXISTING_PREDECESSOR');
  }
  ctx.toolCommit = contract.freeze_commit; return ctx;
}
function pythonAdmission(spawn = cp.spawnSync) {
  const result = spawn('python', ['-I', '-S', '-B', 'Tools/ota/p44-after-bundle.py', ...packageArgs(), 'admit'], {
    cwd: s.root, env: process.env, windowsHide: true, timeout: 120000, maxBuffer: 32 * 1024 * 1024, encoding: 'utf8',
  });
  assert.equal(result.status, 0, 'RECOVERY_PYTHON_ADMISSION');
  return JSON.parse(result.stdout);
}
function allowedRead(role, sql) {
  assert(roles.includes(role), 'RECOVERY_ROLE'); assert(capture.sqlAllowed(sql), 'RECOVERY_SQL');
  assert(sql === SCHEMA_SQL || /^SELECT COUNT\(\*\) AS count FROM "[a-z_][a-z0-9_]*"$/i.test(sql)
    || /^SELECT \* FROM "[a-z_][a-z0-9_]*" ORDER BY rowid LIMIT 8 OFFSET (0|[1-9][0-9]*)$/i.test(sql), 'RECOVERY_SQL');
}
async function d1Read(ctx, label, role, sql, api = leaf) {
  const ensure = makeEnsure(ctx, api, true, offlinePair, stagingPair);
  const result = await ensure.d1(label, role, sql); return result;
}
function identityFromOriginal(raw, expected) {
  assert(Buffer.isBuffer(raw) && raw.length === expected.size_bytes, 'RECOVERY_OFFLINE_SIZE');
  assert.equal(s.sha256(raw), expected.sha256, 'RECOVERY_OFFLINE_DIGEST');
  assert.equal(expected.id_pointer, '/body/result/id', 'RECOVERY_OFFLINE_POINTER');
  const value = JSON.parse(raw), id = value?.body?.result?.id;
  assert.equal(value.status, 200); assert.equal(value.body.success, true); assert.equal(value.body.result.status, 'active');
  assert(typeof id === 'string' && /^[0-9a-f]{32}$/.test(id), 'RECOVERY_OFFLINE_ID');
  assert.equal(s.sha256(id), expected.id_sha256, 'RECOVERY_OFFLINE_ID_DIGEST');
  return id;
}
function offlinePair(ctx, readPrivate = fs.readFileSync) {
  assert.deepEqual(ctx.input.offline_identity, OFFLINE_IDENTITY, 'RECOVERY_OFFLINE_SOURCE');
  const existing = ctx.io.exists(RECOVERY + 'offline-identity.json') ? readDocument(ctx.io, ctx.io.fileRef(RECOVERY + 'offline-identity.json')) : null;
  const project = path.resolve(s.root, '../..');
  const source = s.guard(path.join(project, OFFLINE_IDENTITY.source_path), project);
  assert.equal(fs.statSync(source).size, OFFLINE_IDENTITY.size_bytes, 'RECOVERY_OFFLINE_SIZE');
  const raw = readPrivate(source), id = identityFromOriginal(raw, OFFLINE_IDENTITY);
  const token = readPrivate(s.guard(path.join(project, '.cache/p41-dev-20261015/.cache/cf-auth-input/token.txt'), project)).toString('utf8').trim();
  assert(token, 'RECOVERY_LOCAL_TOKEN');
  const pair = { accessKeyId: id, secretAccessKey: s.sha256(token) }, historical = JSON.parse(raw);
  for (const value of [token, pair.accessKeyId, pair.secretAccessKey]) ctx.io.addSensitive(value);
  if (existing) {
    assert.equal(existing.schema, 'p44-offline-token-identity-v1'); assert.equal(existing.ok, true);
    assert.equal(existing.sha256, OFFLINE_IDENTITY.sha256); assert.equal(existing.id_sha256, OFFLINE_IDENTITY.id_sha256);
    assert.equal(existing.source_path, OFFLINE_IDENTITY.source_path); assert.equal(existing.mode, OFFLINE_IDENTITY.mode);
    assert.equal(existing.verify_requests, 0); assert.equal(existing.current_active_observed, false);
    assert.equal(existing.historical.started, historical.started); assert.equal(existing.historical.finished, historical.finished);
    assert.equal(existing.historical.status, historical.status);
  } else {
    ctx.io.write(RECOVERY + 'offline-identity.json', { schema: 'p44-offline-token-identity-v1', ok: true,
      ...OFFLINE_IDENTITY, verify_requests: 0, current_active_observed: false, evaluated_at: new Date().toISOString(),
      historical: { started: historical.started, finished: historical.finished, status: historical.status },
      interpretation: 'Fixed historical identity read offline; not a fresh active-status check. No network fallback.' });
  }
  return pair;
}
function stagingPair() {
  const project = path.resolve(s.root, '../..');
  const pairs = JSON.parse(fs.readFileSync(s.guard(path.join(project, '.cache/p44-cred-20261019/private/p44-s3-credentials-20261019.json'), project), 'utf8'));
  const pair = pairs.credentials.rehearsal;
  assert.equal(pair.bucket, capture.resources.staging.bucket); assert.equal(pair.secret_access_key_sha256, s.sha256(pair.token_value));
  assert.equal(s.sha256(pair.token_id_access_key_id), 'e96e395a2e6866581f0c4aa1b46579026683ea9f4fbfab48b9b2f8b45a22a508');
  return { accessKeyId: pair.token_id_access_key_id, secretAccessKey: pair.secret_access_key_sha256 };
}
async function after(ctx, api = leaf, getPair = offlinePair, getStagingPair = stagingPair) {
  assert(ctx.toolCommit && ctx.initialComplete.size > 0, 'RECOVERY_NOT_ADMITTED');
  for (const name of ['snapshots/after.json', RECOVERY + 'after-result.json']) assert(!ctx.io.exists(name), 'RECOVERY_ALREADY_EXECUTED');
  ctx.fetching = true; ctx.used = new Set(); ctx.visited = new Set(); ctx.order = []; ctx.firstMissing = undefined; ctx.fetchedOnce = false;
  const pairs = { protected: undefined, staging: undefined };
  const pairFor = async () => { if (!pairs.protected) pairs.protected = await getPair(ctx); return pairs.protected; };
  const stagingFor = () => { if (!pairs.staging) pairs.staging = getStagingPair(); return pairs.staging; };
  let result;
  try {
    const ensure = makeEnsure(ctx, api, true, pairFor, stagingFor);
    result = await walkAll(ctx, ensure);
  } catch (error) {
    if (ctx.attempt && !ctx.io.exists(ctx.attemptDir + 'attempt-result.json')) {
      try { attemptResult(ctx, false, error); } catch { /* Preserve the original failure; the orphan is still fail-closed on rescan. */ }
    }
    throw error;
  }
  if (ctx.attempt) attemptResult(ctx, true);
  assert.equal(ctx.used.size, ctx.initialComplete.size, 'RECOVERY_PREFIX_NOT_CONSUMED');
  for (const label of ctx.initialComplete.keys()) assert(ctx.visited.has(label), 'RECOVERY_UNUSED_PREFIX');
  for (const label of ctx.failures.keys()) assert(ctx.visited.has(label), 'RECOVERY_UNKNOWN_FAILURE');
  result.recovery = { source_commit: C4, source_bundle_commit: B4, tool_commit: ctx.toolCommit, ...PREDECESSOR,
    input: ctx.io.fileRef(FIXTURE), complete_originals: ctx.input.after_complete, failed_originals: ctx.input.after_failed,
    private_verify_failure: ctx.input.private_verify_failure, attempts: ctx.attempts.map(attemptSummary),
    reused_complete: ctx.initialComplete.size, reused_failures: listFailures(ctx.initialFailures),
    reused_records: recordList(ctx.initialComplete), new_reads: ctx.freshEntries,
    first_missing: ctx.prefixFirstMissing ?? null,
    interpretation: 'Original C4 and verified C6 after responses retain their original times; only missing tail reads were executed.' };
  const snapshot = ctx.io.write('snapshots/after.json', result);
  ctx.io.write(RECOVERY + 'after-result.json', { schema: 'p44-after-recovery-result-v2', ok: true, snapshot,
    reused_complete: ctx.initialComplete.size, new_reads: ctx.freshEntries.length, first_new: ctx.fresh[0] ?? null,
    first_missing: null, attempts: ctx.attempts.map(attemptSummary),
    product_commit: C4, tool_commit: ctx.toolCommit, source_commit: C4, source_bundle_commit: B4, freeze_commit: ctx.toolCommit, ...PREDECESSOR });
  return result;
}
function assemble(ctx) {
  const afterResult = ctx.io.read(RECOVERY + 'after-result.json'); assert.equal(afterResult.ok, true);
  const manifest = ctx.document(ctx.files.get('rehearsal-manifest.json'));
  assert.equal(manifest.schema, 'p44-observations-v1'); assert.deepEqual(manifest.target, ctx.input.target);
  assert(manifest.run_a && manifest.run_b && manifest.artifact && manifest.artifact_listing, 'RECOVERY_MANIFEST_INCOMPLETE');
  manifest.snapshots = { before: ctx.before, after: JSON.parse(reference(ctx.io, afterResult.snapshot)) };
  manifest.readbacks = ctx.document(ctx.files.get('readbacks.json'));
  assert.equal(Object.keys(manifest.readbacks).length, 3); for (const record of Object.values(manifest.readbacks)) ctx.original(record.body);
  manifest.reviewer_attestation = ctx.input.reviewer_attestation;
  const output = ctx.io.write('manifest.json', manifest);
  ctx.io.write(RECOVERY + 'assemble-result.json', { ok: true, manifest: output, source_commit: C4,
    source_bundle_commit: B4, freeze_commit: ctx.toolCommit, ...PREDECESSOR, platform_operations: 0 });
}
function containedEnvironment(directory) {
  for (const key of ['NODE_OPTIONS', 'NODE_V8_COVERAGE', 'NODE_COMPILE_CACHE', 'SSLKEYLOGFILE', 'GIT_TRACE', 'GIT_TRACE2',
    'GIT_TRACE2_EVENT', 'GIT_TRACE2_PERF', 'GIT_INDEX_FILE', 'GIT_OBJECT_DIRECTORY', 'BASH_ENV', 'ENV']) assert(!process.env[key], 'RECOVERY_OUTPUT_OVERRIDE');
  const env = { ...process.env };
  for (const key of ['TEMP', 'TMP', 'TMPDIR', 'HOME', 'USERPROFILE', 'APPDATA', 'LOCALAPPDATA', 'XDG_CONFIG_HOME', 'XDG_CACHE_HOME', 'XDG_DATA_HOME', 'GH_CONFIG_DIR', 'npm_config_cache']) {
    env[key] = s.guard(path.join(directory, key.toLowerCase()));
  }
  for (const key of ['TEMP', 'TMP', 'TMPDIR', 'HOME', 'USERPROFILE', 'APPDATA', 'LOCALAPPDATA', 'XDG_CONFIG_HOME', 'XDG_CACHE_HOME', 'XDG_DATA_HOME', 'GH_CONFIG_DIR', 'npm_config_cache']) fs.mkdirSync(env[key], { recursive: true });
  return { ...env, GH_PROMPT_DISABLED: '1', GH_NO_UPDATE_NOTIFIER: '1', GH_NO_EXTENSION_UPDATE_NOTIFIER: '1', npm_config_update_notifier: 'false',
    PYTHONDONTWRITEBYTECODE: '1', PYTHONUTF8: '1', GIT_TERMINAL_PROMPT: '0', GIT_OPTIONAL_LOCKS: '0', WRANGLER_SEND_METRICS: 'false',
    WECHAT_WEBHOOK_KEY: '', ANTHROPIC_API_KEY: '' };
}
function commandAllowed(command, args) {
  assert(['node', 'python'].includes(command) && Array.isArray(args), 'RECOVERY_COMMAND');
  assert(args.every(value => typeof value === 'string' && !/[\0\r\n]/.test(value)), 'RECOVERY_COMMAND_ARGUMENT');
  let index = 0;
  if (command === 'python') {
    while (args[index]?.startsWith('-')) { assert(['-I', '-S', '-B'].includes(args[index]), 'RECOVERY_PYTHON_OPTION'); index++; }
  }
  const script = args[index];
  const allowed = command === 'node' ? [SELF] : ['Tools/ota/p44-after-bundle.py', 'Tools/acceptance/validate_bundle.py', 'Tools/acceptance/p44/inspect.py', 'Tools/acceptance/p44/origins.py'];
  assert(allowed.includes(script), 'RECOVERY_SCRIPT');
}
function reuseSourcePairs() {
  const version = PACKAGE_SPEC ? PACKAGE_SPEC.version : 6;
  const pairs = [];
  for (let number = 4; number <= version - 2; number += 1) {
    const base = 'docs/acceptance-contracts/P4-4-v' + number;
    pairs.push([base + '.contract.json', base + '/final-evidence-matrix.json']);
  }
  return pairs;
}
function validatorArgs(label) {
  assert(['formal-precheck', 'formal-rerun-plan'].includes(label), 'RECOVERY_VALIDATOR_LABEL');
  const version = PACKAGE_SPEC ? PACKAGE_SPEC.version : 6;
  const current = PACKAGE_SPEC ? PACKAGE_SPEC.package : 'docs/acceptance-contracts/P4-4-v6';
  const previous = 'docs/acceptance-contracts/P4-4-v' + (version - 1);
  const args = ['-I', '-S', '-B', 'Tools/acceptance/validate_bundle.py', '--contract', current + '.contract.json',
    '--repo-root', s.root.replaceAll('\\', '/'), '--previous-contract', previous + '.contract.json',
    '--previous-matrix', previous + '/final-evidence-matrix.json'];
  for (const pair of reuseSourcePairs()) args.push('--reuse-source', ...pair);
  args.push('--matrix', current + '/evidence-matrix.json');
  if (label === 'formal-rerun-plan') args.push('--write-rerun-plan', 'rerun-plan.json');
  return args;
}
function afterSlot(io, child = false) {
  assert(PACKAGE_SPEC, 'RECOVERY_PACKAGE_REQUIRED');
  for (let slot = 1; slot <= PACKAGE_SPEC.max_after_invocations; slot++) {
    const stem = COMMANDS + 'formal-after-invocation-' + slot;
    if (!io.exists(stem + '.json')) {
      assert.equal(io.exists(stem + '-reservation.json'), child, 'RECOVERY_INVOCATION_OPEN');
      return { slot, stem };
    }
    const receipt = io.read(stem + '.json');
    assert(receipt.closed === true && receipt.process_closed === true && receipt.signal === null, 'RECOVERY_INVOCATION_UNCLOSED');
    assert(receipt.exitCode !== 0 && Number.isInteger(receipt.exitCode), 'RECOVERY_ALREADY_EXECUTED');
    reference(io, receipt.output);
  }
  assert.fail('RECOVERY_INVOCATION_LIMIT');
}
function admitSlot(ctx, slot) {
  assert.equal(ctx.toolCommit, s.git(['rev-parse', 'HEAD']), 'RECOVERY_TOOL_HEAD');
  if (slot.slot === 1) return;
  const priorStem = COMMANDS + 'formal-after-invocation-' + (slot.slot - 1);
  const approval = ctx.io.read(RECOVERY + 'continuation-' + slot.slot + '.json');
  assert.deepEqual(Object.keys(approval).sort(), ['approved_at', 'approved_by', 'basis', 'decision', 'first_missing', 'prior_attempt_result', 'prior_receipt', 'schema', 'slot', 'tool_commit', 'tool_sha256']);
  assert.equal(approval.schema, 'p44-after-continuation-v1'); assert.equal(approval.slot, slot.slot);
  assert.equal(approval.decision, 'CONTINUE_MISSING_ONLY');
  for (const field of ['approved_by', 'basis']) assert(typeof approval[field] === 'string' && approval[field].trim().length > 0, 'RECOVERY_CONTINUATION_BASIS');
  assert.equal(approval.tool_commit, ctx.toolCommit);
  assert.equal(approval.tool_sha256, s.sha256(fs.readFileSync(s.guard(path.join(s.root, SELF)))));
  assert.equal(approval.first_missing, ctx.prefixFirstMissing, 'RECOVERY_CONTINUATION_FRONTIER');
  assert.deepEqual(approval.prior_receipt, ctx.io.fileRef(priorStem + '.json'));
  const receipt = readDocument(ctx.io, approval.prior_receipt);
  const approvedAt = Date.parse(approval.approved_at);
  assert(approvedAt >= Date.parse(receipt.ended) && approvedAt <= Date.now(), 'RECOVERY_CONTINUATION_TIME');
  const currentReservation = COMMANDS + 'formal-after-invocation-' + slot.slot + '-reservation.json';
  if (ctx.io.exists(currentReservation)) {
    assert(approvedAt <= Date.parse(ctx.io.read(currentReservation).started), 'RECOVERY_CONTINUATION_TIME');
  }
  const prior = ctx.attempts.at(-1);
  assert(prior.result && !prior.result.ok, 'RECOVERY_CONTINUATION_FAILURE');
  assert.deepEqual(approval.prior_attempt_result, prior.resultRef);
  assert.equal(prior.reservation.tool_commit, ctx.toolCommit, 'RECOVERY_CONTINUATION_SOURCE');
  assert.equal(prior.reservation.tool_sha256, approval.tool_sha256, 'RECOVERY_CONTINUATION_SOURCE');
}
async function runCommand(io, label, command, args, environment, stemOverride) {
  assert(/^[a-z0-9-]+$/.test(label), 'RECOVERY_COMMAND_LABEL'); commandAllowed(command, args);
  const stem = stemOverride || COMMANDS + label;
  for (const suffix of ['.log', '.json', '-reservation.json']) assert(!io.exists(stem + suffix), 'RECOVERY_COMMAND_EXISTS');
  const started = new Date().toISOString();
  io.write(stem + '-reservation.json', { label, command, args, cwd: s.root, started });
  const log = io.destination(stem + '.log'); fs.mkdirSync(s.guard(path.dirname(log)), { recursive: true }); io.destination(stem + '.log');
  const fd = fs.openSync(log, 'wx');
  return new Promise(resolve => {
    const child = cp.spawn(command, args, { cwd: s.root, env: environment, windowsHide: true, stdio: ['ignore', 'pipe', 'pipe'] });
    let spawnFailed = false;
    const timer = setTimeout(() => {
      if (process.platform === 'win32') cp.spawnSync('taskkill.exe', ['/PID', String(child.pid), '/T', '/F'], { cwd: s.root, windowsHide: true, timeout: 15000 });
      else child.kill();
    }, 60 * 60 * 1000);
    for (const stream of [child.stdout, child.stderr]) stream.on('data', bytes => { fs.writeSync(fd, bytes); process.stdout.write(bytes); });
    child.on('error', () => { spawnFailed = true; fs.writeSync(fd, 'RECOVERY_COMMAND_START_FAILED\n'); });
    child.on('close', (exitCode, signal) => {
      clearTimeout(timer); fs.closeSync(fd);
      io.write(stem + '.json', { label, command, args, cwd: s.root, started, ended: new Date().toISOString(),
        exitCode, signal, process_closed: true, closed: true, spawn_failed: spawnFailed, output: io.fileRef(stem + '.log') });
      resolve(exitCode === 0 && !spawnFailed ? 0 : 1);
    });
  });
}
async function main(args, runtime = {}) {
  if (args[0] === '--package-spec') { configurePackage(args[1]); args = args.slice(2); }
  const io = runtime.io || makeIO();
  if (args[0] === 'run') {
    const [, label, command, ...rest] = args;
    const contract = JSON.parse(fs.readFileSync(s.guard(CONTRACT)));
    assert.equal(contract.status, 'FROZEN'); assert.equal(contract.contract_id, contractId());
    const actual = ['node', SELF, ...packageArgs(), ...args].join(' ');
    if (!['formal-precheck', 'formal-rerun-plan'].includes(label)) assert(contract.commands.some(item => item.id === label && item.command === actual), 'RECOVERY_FROZEN_COMMAND');
    else { assert.equal(command, 'python'); assert.deepEqual(rest, validatorArgs(label), 'RECOVERY_VALIDATOR_COMMAND'); }
    let slot;
    if (PACKAGE_SPEC && label === 'formal-after') {
      slot = afterSlot(io);
      const ctx = loadRecovery(io);
      admit(ctx, contract, s.git(['rev-parse', 'HEAD']), pythonAdmission(), s.sha256(fs.readFileSync(CONTRACT)));
      await validatePrefix(ctx); admitSlot(ctx, slot);
    }
    return runCommand(io, label, command, rest, containedEnvironment(path.join(s.root, '.cache/p44-v' + (PACKAGE_SPEC?.version || 6) + '-host')), slot?.stem);
  }
  assert(args.length === 1 && ['after', 'assemble'].includes(args[0]), 'RECOVERY_MODE');
  return withLeaves(io, async () => {
    const ctx = loadRecovery(io);
    const contractBytes = runtime.contractBytes || fs.readFileSync(s.guard(CONTRACT)), contract = JSON.parse(contractBytes);
    admit(ctx, contract, s.git(['rev-parse', 'HEAD']), runtime.admission || pythonAdmission(), s.sha256(contractBytes));
    await validatePrefix(ctx);
    if (PACKAGE_SPEC && args[0] === 'after') admitSlot(ctx, afterSlot(io, true));
    assert.equal(s.git(['branch', '--show-current']), BRANCH);
    assert.equal(s.git(['diff', '--name-only', C4, ctx.toolCommit, '--', 'Tools/acceptance/', 'Tools/provenance/manifest_profiles.json']), '', 'RECOVERY_FROZEN_LEAVES_CHANGED');
    if (args[0] === 'after') await after(ctx, runtime.api || leaf, runtime.getPair || offlinePair, runtime.getStagingPair || stagingPair); else assemble(ctx);
    console.log(JSON.stringify({ ok: true, mode: args[0], product_commit: C4, tool_commit: ctx.toolCommit })); return 0;
  });
}
module.exports = { DATA, CONTRACT, C4, B4, I4, C5, B5, I5, C6_TOOL, PREDECESSOR, BRANCH, REPO, FIXTURE, RECOVERY, COMMANDS, OLD, TAIL,
  LEGACY_RESERVATION, RESUME_SCHEMA, ATTEMPT_RESULT_SCHEMA, SCHEMA_SQL, TOKEN_ID_SHA, OFFLINE_IDENTITY, attemptDir,
  makeIO, reference, readDocument, configureHttp, withLeaves, loadRecovery, validatePrefix, admit, pythonAdmission, tables, allowedRead,
  d1Read, identityFromOriginal, offlinePair, stagingPair, after, assemble, containedEnvironment, commandAllowed, validatorArgs, runCommand, main,
  scanAttempts, scanSource, validateRecord, attemptSummary, failureList, listFailures, recordList, walkAll, makeEnsure,
  configurePackage, packageArgs, afterSlot, admitSlot };
if (require.main === module) main(process.argv.slice(2)).then(code => { process.exitCode = code; }).catch(error => {
  console.error(JSON.stringify({ ok: false, error_code: /^[A-Z0-9_]+$/.test(error.code || '') ? error.code : 'RECOVERY_FAILED' })); process.exitCode = 1;
});
