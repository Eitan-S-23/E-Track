// After-only recovery. The C4 collector and every original remain unchanged.
const s = require('../acceptance/p44/run.cjs');
const capture = require('../acceptance/p44/capture.cjs');
const leaf = capture._test;
const { fs, path, assert, cp } = s;
const { gunzipSync } = require('node:zlib');
const DATA = path.join(s.root, 'docs/acceptance-contracts/P4-4-v5/evidence');
const CONTRACT = path.join(s.root, 'docs/acceptance-contracts/P4-4-v5.contract.json');
const SELF = 'Tools/ota/p44-after-recovery.cjs';
const C4 = '2756ca95e26ec636216313271708b3304d61a5cc';
const B4 = 'da37711799a21c4eb2c5d082dab1a7b81d028511';
const I4 = '7168568489ab0eb67a9e7a05106f245e7243421e';
const BRANCH = 'dev/p4-4/config-integration-20261018';
const REPO = '/repos/Eitan-S-23/E-Track';
const FIXTURE = 'inputs/after-recovery.json';
const OLD = 'snapshots/after/';
const TAIL = 'snapshots/after-tail/';
const GAP = 'protected-audit_logs-rows8-16';
const SCHEMA_SQL = 'SELECT name,type,sql FROM sqlite_master ORDER BY type,name';
const TOKEN_ID_SHA = '0c22488a9bee1355603d8d61faca06fcacbdafccfed8a4ba7dc490af7cacdedc';
const roles = Object.keys(capture.resources);
const moduleRoot = path.join(s.root, 'app/bluetooth_flutter_Trace/cloudflare/update-service/worker/node_modules');
const canonical = capture.canonical;

function relative(name) {
  assert(typeof name === 'string' && /^[a-zA-Z0-9_./-]+$/.test(name)
    && name.split('/').every(p => p && p !== '.' && p !== '..'), 'RECOVERY_PATH');
  return name;
}
function makeIO(base = DATA) {
  base = s.guard(base);
  const sensitive = [], created = [];
  const destination = name => s.guard(path.join(base, relative(name)), base);
  const readBytes = name => fs.readFileSync(destination(name));
  const fileRef = name => { const bytes = readBytes(name); return { path: name, size_bytes: bytes.length, sha256: s.sha256(bytes) }; };
  return { base, destination, readBytes, fileRef, created,
    exists: name => fs.existsSync(destination(name)),
    read: name => JSON.parse(readBytes(name)),
    addSensitive(value) { sensitive.push(value, Buffer.from(value).toString('base64')); },
    write(name, value) {
      const file = destination(name);
      assert(!fs.existsSync(file), 'RECOVERY_ORIGINAL_EXISTS');
      const bytes = Buffer.isBuffer(value) ? value : Buffer.from(typeof value === 'string' ? value : JSON.stringify(value, null, 2) + '\n');
      const decoded = bytes[0] === 0x1f && bytes[1] === 0x8b ? gunzipSync(bytes, { maxOutputLength: leaf.httpMaxBytes }) : bytes;
      for (const value of sensitive) assert(!bytes.includes(Buffer.from(value)) && !decoded.includes(Buffer.from(value)), 'RECOVERY_SENSITIVE_OUTPUT');
      fs.mkdirSync(s.guard(path.dirname(file), base), { recursive: true }); destination(name);
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
    const directory = options.privateRoot || path.join(s.root, '.cache/p44/private/capture-failures/P4-4-v5');
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
  assert.equal(input.schema, 'p44-after-recovery-v1', 'RECOVERY_SCHEMA');
  assert.equal(input.source_commit, C4); assert.equal(input.source_bundle_commit, B4); assert.equal(input.source_index_commit, I4);
  const contract = JSON.parse(reference(io, input.source_contract));
  const matrix = JSON.parse(reference(io, input.source_matrix));
  assert.equal(contract.contract_id, 'P4-4-v4'); assert.equal(contract.freeze_commit, C4); assert.equal(contract.status, 'FROZEN');
  assert.equal(matrix.contract_id, contract.contract_id); assert.equal(matrix.contract_sha256.toLowerCase(), s.sha256(reference(io, input.source_contract)));
  assert.equal(matrix.overall_result, 'EVIDENCE_GAP');
  for (const id of ['P44-RAW-RUNS', 'P44-REHEARSAL', 'P44-RAW-READBACK']) {
    const rows = matrix.criteria.filter(item => item.id === id);
    assert.equal(rows.length, 1); assert.equal(rows[0].result, 'PASS'); assert.equal(rows[0].execution, 'EXECUTED');
  }
  assert(Array.isArray(input.files));
  const files = new Map();
  for (const ref of input.files) { relative(ref.path); assert(!files.has(ref.path), 'RECOVERY_DUPLICATE_FILE'); files.set(ref.path, ref); }
  const original = ref => { assert.deepEqual(files.get(ref.path), ref, 'RECOVERY_SOURCE_REFERENCE'); return reference(io, ref); };
  const document = ref => JSON.parse(original(ref));
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
  return { io, input, files, original, document, target, before, finished, run, old: new Map(), used: new Set(), fresh: [] };
}
function timing(ctx, record) {
  const start = Date.parse(record.started), end = Date.parse(record.ended);
  assert(Number.isFinite(start) && Number.isFinite(end) && end >= start && start >= ctx.finished, 'RECOVERY_AFTER_TIME');
}
function response(ctx, record, method, route, expected = 200, sql) {
  assert.equal(record.completed, true, 'RECOVERY_INCOMPLETE'); assert.equal(record.method, method, 'RECOVERY_METHOD');
  assert.equal(record.path, route, 'RECOVERY_ROUTE'); assert((Array.isArray(expected) ? expected : [expected]).includes(record.status), 'RECOVERY_STATUS');
  timing(ctx, record);
  if (sql !== undefined) {
    assert(capture.sqlAllowed(sql)); assert.deepEqual(JSON.parse(reference(ctx.io, record.request)), { sql }, 'RECOVERY_SQL');
    const data = leaf.d1Document(record);
    assert(data.success === true && data.result.length === 1 && data.result[0].success === true, 'RECOVERY_D1');
    assert(data.result[0].meta.rows_written === 0 && data.result[0].meta.changed_db === false, 'RECOVERY_D1_WRITE');
    assert(Array.isArray(data.result[0].results), 'RECOVERY_ROWS'); return data.result[0].results;
  }
  assert(record.decoded_body === undefined, 'RECOVERY_UNEXPECTED_DECODED');
  return reference(ctx.io, record.body, leaf.httpMaxBytes);
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
function validatePrefix(ctx) {
  assert.deepEqual(Object.keys(ctx.before.databases).sort(), [...roles].sort(), 'RECOVERY_BEFORE_ROLES');
  for (const role of roles) tables(leaf.d1Document(ctx.before.databases[role].schema).result[0].results);
  assert.equal(ctx.input.after_complete.length, 31); assert.equal(ctx.input.after_failed.length, 1);
  for (const ref of ctx.input.after_complete) {
    assert(ref.path.startsWith(OLD) && ref.path.endsWith('.http.json'), 'RECOVERY_PREFIX_PATH');
    const label = ref.path.slice(OLD.length, -'.http.json'.length), record = ctx.document(ref);
    assert(!ctx.old.has(label), 'RECOVERY_DUPLICATE_PREFIX');
    assert(record.completed === true, 'RECOVERY_INCOMPLETE'); timing(ctx, record);
    for (const key of ['request', 'body', 'decoded_body']) if (record[key]) ctx.original(record[key]);
    const reservation = ctx.document(ctx.files.get(OLD + label + '-reservation.json'));
    assert.equal(reservation.method, record.method); assert.equal(reservation.path, record.path);
    assert.deepEqual(reservation.request, record.request); assert.equal(reservation.started, record.started);
    ctx.old.set(label, { record, reservation });
  }
  const failedRef = ctx.input.after_failed[0]; assert.equal(failedRef.path, OLD + GAP + '.http.json');
  const failed = ctx.document(failedRef); assert.equal(failed.completed, false); assert.equal(failed.error_code, 'UND_ERR_CONNECT_TIMEOUT');
  assert.equal(failed.method, 'POST'); assert.equal(failed.path, d1Route('protected')); assert.equal(failed.request_attempts, 1);
  assert(!Object.hasOwn(failed, 'status') && !Object.hasOwn(failed, 'body') && !failed.retry_reservation, 'RECOVERY_FAILED_RESPONSE');
  assert.deepEqual(JSON.parse(ctx.original(failed.request)), { sql: rowSql('audit_logs', 16) });
  assert.equal(failed.request_failures.length, 1);
  const failure = ctx.document(failed.request_failures[0]);
  assert.equal(failure.error_code, failed.error_code); assert.equal(failure.attempt, 1); assert.equal(failure.final_response_received, false);
  assert.equal(failure.received_body_bytes, 0); assert.equal(failure.informational_seen, false); assert.equal(failure.informational_count, 0);
  assert.equal(failure.first_information, null); assert.deepEqual(failure.request, failed.request); timing(ctx, failed); timing(ctx, failure);
  const visited = new Set(); let missing;
  const take = (label, role, sql) => {
    const entry = ctx.old.get(label); if (!entry) { missing = label; return null; }
    assert.equal(entry.reservation.origin, 'https://api.cloudflare.com'); visited.add(label);
    return response(ctx, entry.record, 'POST', d1Route(role), 200, sql);
  };
  outer: for (const role of roles) {
    const schema = take(role + '-schema', role, SCHEMA_SQL); if (!schema) break;
    for (const name of tables(schema)) {
      const count = take(role + '-' + name + '-count', role, countSql(name)); if (!count) break outer;
      const total = totalCount(count);
      for (let offset = 0; offset < total; offset += 8) {
        const rows = take(role + '-' + name + '-rows8-' + offset, role, rowSql(name, offset)); if (!rows) break outer;
        assert.equal(rows.length, Math.min(8, total - offset), 'RECOVERY_PAGE_COUNT');
      }
    }
    const label = role + '-r2-1', entry = ctx.old.get(label); assert(entry, 'RECOVERY_PREFIX_R2');
    assert.equal(role, 'production'); assert.equal(entry.reservation.origin, 's3');
    const xml = response(ctx, entry.record, 'GET', '/' + capture.resources[role].bucket + '/?list-type=2&max-keys=1000').toString('utf8');
    assert.equal(xmlField(xml, 'Name'), capture.resources[role].bucket); assert.equal(xmlField(xml, 'IsTruncated'), 'false'); visited.add(label);
  }
  assert.equal(missing, GAP, 'RECOVERY_FIRST_MISSING'); assert.equal(visited.size, 31, 'RECOVERY_UNUSED_PREFIX');
  assert.equal(ctx.old.size, visited.size); return ctx;
}
function admit(ctx, contract, head, report, contractHash) {
  assert.equal(contract.contract_id, 'P4-4-v5'); assert.equal(contract.status, 'FROZEN');
  assert.match(contract.freeze_commit, /^[0-9a-f]{40}$/); assert.notEqual(contract.freeze_commit, C4);
  assert.equal(head, contract.freeze_commit, 'RECOVERY_TOOL_HEAD');
  assert.equal(report?.schema, 'p44-after-admission-v1', 'RECOVERY_ADMISSION'); assert.equal(report.ok, true);
  assert.equal(report.freeze_commit, contract.freeze_commit); assert.equal(report.source_commit, C4); assert.equal(report.source_bundle_commit, B4);
  assert.match(contractHash, /^[0-9a-f]{64}$/);
  assert.equal(report.contract_sha256.toLowerCase(), contractHash, 'RECOVERY_ADMISSION_CONTRACT');
  const external = contract.external_inputs.filter(item => item.evidence_path === 'evidence/' + FIXTURE);
  assert.equal(external.length, 1); assert.equal(external[0].evidence_sha256.toLowerCase(), s.sha256(ctx.io.readBytes(FIXTURE)));
  assert.equal(ctx.io.read('recovery-commands/formal-precheck.json').exitCode, 0, 'RECOVERY_PRECHECK');
  for (const kind of ['before', 'negatives']) {
    const result = ctx.io.read('recovery/' + kind + '-result.json');
    assert.equal(result.schema, 'p44-after-existing-v1'); assert.equal(result.ok, true); assert.equal(result.kind, kind);
    assert.deepEqual(result.source, ctx.input[kind]); assert.equal(result.source_bundle_commit, B4); assert.equal(result.platform_operations, 0);
  }
  ctx.toolCommit = contract.freeze_commit; return ctx;
}
function pythonAdmission(spawn = cp.spawnSync) {
  const result = spawn('python', ['-I', '-S', '-B', 'Tools/ota/p44-after-bundle.py', 'admit'], {
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
  allowedRead(role, sql);
  const old = ctx.old.get(label);
  if (old) {
    assert(!ctx.used.has(label), 'RECOVERY_PREFIX_REPLAY'); ctx.used.add(label);
    return { envelope: old.record, rows: response(ctx, old.record, 'POST', d1Route(role), 200, sql) };
  }
  assert.notEqual(role, 'production', 'RECOVERY_PRODUCTION_REPLAY');
  if (!ctx.fresh.length) assert.equal(label, GAP, 'RECOVERY_FIRST_REQUEST');
  assert(!label.includes('/') && label.startsWith(role + '-'), 'RECOVERY_LABEL');
  ctx.fresh.push(label);
  const result = await api.d1(TAIL + label, role, sql);
  response(ctx, result.envelope, 'POST', d1Route(role), 200, sql); return result;
}
async function protectedPair(ctx) {
  const project = path.resolve(s.root, '../..');
  const token = fs.readFileSync(s.guard(path.join(project, '.cache/p41-dev-20261015/.cache/cf-auth-input/token.txt'), project), 'utf8').trim();
  assert(token, 'RECOVERY_LOCAL_TOKEN');
  const label = 'recovery/private-verify';
  const started = new Date().toISOString();
  ctx.io.write(label + '-reservation.json', { method: 'GET', path: '/user/tokens/verify', started, attempts_allowed: 1 });
  let raw;
  try {
    raw = await leaf.transport('https://api.cloudflare.com/client/v4/user/tokens/verify', 'GET', { authorization: 'Bearer ' + token });
    const data = JSON.parse(raw.bytes);
    assert.equal(raw.status, 200); assert.equal(data.success, true); assert.equal(data.result.status, 'active');
    assert.match(data.result.id, /^[0-9a-f]{32}$/); assert.equal(s.sha256(data.result.id), TOKEN_ID_SHA, 'RECOVERY_TOKEN_ID');
    const pair = { accessKeyId: data.result.id, secretAccessKey: s.sha256(token) };
    ctx.io.addSensitive(pair.accessKeyId); ctx.io.addSensitive(pair.secretAccessKey);
    ctx.io.write(label + '.json', { ok: true, method: 'GET', path: '/user/tokens/verify', status: raw.status, started,
      ended: new Date().toISOString(), attempts: 1, original_sha256: s.sha256(raw.bytes), original_size_bytes: raw.bytes.length,
      response_projection: { success: true, status: 'active', id_sha256: TOKEN_ID_SHA },
      omitted_original: 'Private authentication input; token ID stays in memory. Not a business snapshot response.' });
    return pair;
  } catch (error) {
    ctx.io.write(label + '-failure.json', { ok: false, started, ended: new Date().toISOString(), attempts: 1,
      error_code: /^[A-Z0-9_]+$/.test(error.code || '') ? error.code : 'PRIVATE_VERIFY_FAILED',
      ...(raw ? { status: raw.status, original_sha256: s.sha256(raw.bytes), original_size_bytes: raw.bytes.length } : {}) });
    throw error;
  }
}
function stagingPair() {
  const project = path.resolve(s.root, '../..');
  const pairs = JSON.parse(fs.readFileSync(s.guard(path.join(project, '.cache/p44-cred-20261019/private/p44-s3-credentials-20261019.json'), project), 'utf8'));
  const pair = pairs.credentials.rehearsal;
  assert.equal(pair.bucket, capture.resources.staging.bucket); assert.equal(pair.secret_access_key_sha256, s.sha256(pair.token_value));
  assert.equal(s.sha256(pair.token_id_access_key_id), 'e96e395a2e6866581f0c4aa1b46579026683ea9f4fbfab48b9b2f8b45a22a508');
  return { accessKeyId: pair.token_id_access_key_id, secretAccessKey: pair.secret_access_key_sha256 };
}
async function afterConfiguration(ctx, api = leaf) {
  const result = {};
  for (const role of ['production', 'rehearsal']) {
    const route = REPO + '/environments/firmware-' + role, label = TAIL + 'config/' + role;
    const config = await api.capture(label + '-environment', 'https://api.github.com', route);
    const vars = await api.pages(label + '-variables', route + '/variables', 'variables');
    const names = await api.pages(label + '-secrets', route + '/secrets', 'secrets');
    const rules = await api.pages(label + '-branches', route + '/deployment-branch-policies', 'branch_policies');
    const previous = ctx.before.protected_configuration[role];
    const original = JSON.parse(reference(ctx.io, previous.configuration.body)), value = config.json();
    for (const key of ['id', 'name', 'protection_rules', 'deployment_branch_policy', 'can_admins_bypass']) assert.deepEqual(value[key], original[key], 'RECOVERY_ENV_DRIFT');
    assert.deepEqual(value.deployment_branch_policy, { protected_branches: false, custom_branch_policies: true });
    const reviewer = value.protection_rules.find(rule => rule.type === 'required_reviewers');
    assert.equal(reviewer.prevent_self_review, role === 'production'); assert.equal(reviewer.reviewers.length, 1);
    assert.equal(reviewer.reviewers[0].reviewer.login, 'Eitan-S-23'); assert.equal(reviewer.reviewers[0].reviewer.id, 204050265);
    const values = Object.fromEntries(vars.items.map(value => [value.name, value.value]));
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
    const secretIdentity = values => values.map(value => {
      for (const name of ['name', 'created_at', 'updated_at']) assert(typeof value[name] === 'string', 'RECOVERY_SECRET_METADATA');
      return { name: value.name, created_at: value.created_at, updated_at: value.updated_at };
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
  const gate = await api.capture(TAIL + 'config/repository-gate', 'https://api.github.com', REPO + '/actions/variables/OTA_BOOT_CHAIN_READY');
  assert.equal(gate.json().value, 'false');
  const remote = await api.capture(TAIL + 'config/tool-ref', 'https://api.github.com', REPO + '/git/ref/heads/' + BRANCH);
  assert.equal(remote.json().object.sha, ctx.toolCommit, 'RECOVERY_REMOTE_TOOL_DRIFT');
  result.repository_gate = gate.envelope; result.tool_ref = remote.envelope;
  result.product_commit = C4; result.tool_commit = ctx.toolCommit; return result;
}
async function after(ctx, api = leaf, getPair = protectedPair, getStagingPair = stagingPair) {
  assert(ctx.toolCommit && ctx.old.size === 31, 'RECOVERY_NOT_ADMITTED');
  for (const name of ['recovery/after-reservation.json', 'snapshots/after.json', 'recovery/after-result.json']) assert(!ctx.io.exists(name), 'RECOVERY_ALREADY_EXECUTED');
  ctx.io.write('recovery/after-reservation.json', { product_commit: C4, tool_commit: ctx.toolCommit, source_bundle_commit: B4,
    started: new Date().toISOString(), old_complete: 31, old_failed: 1, first_missing: GAP });
  const pair = await getPair(ctx), result = { databases: {}, buckets: {}, github: {} };
  for (const role of roles) {
    const schema = await d1Read(ctx, role + '-schema', role, SCHEMA_SQL, api);
    assert.deepEqual(schema.rows, leaf.d1Document(ctx.before.databases[role].schema).result[0].results, 'RECOVERY_SCHEMA_DRIFT');
    const records = {};
    for (const name of tables(schema.rows)) {
      const count = await d1Read(ctx, role + '-' + name + '-count', role, countSql(name), api);
      const total = totalCount(count.rows), pages = [], ids = new Set();
      for (let offset = 0; offset < total; offset += 8) {
        const page = await d1Read(ctx, role + '-' + name + '-rows8-' + offset, role, rowSql(name, offset), api);
        assert.equal(page.rows.length, Math.min(8, total - offset), 'RECOVERY_PAGE_COUNT');
        for (const row of page.rows) if (Object.hasOwn(row, 'id')) {
          const id = canonical(row.id); assert(!ids.has(id), 'RECOVERY_DUPLICATE_ROW'); ids.add(id);
        }
        pages.push(page.envelope);
      }
      records[name] = { count: count.envelope, pages };
    }
    result.databases[role] = { schema: schema.envelope, tables: records };
    if (role === 'production') {
      const label = role + '-r2-1'; assert(!ctx.used.has(label)); ctx.used.add(label); result.buckets[role] = [ctx.old.get(label).record]; continue;
    }
    const pages = [], tokens = new Set(); let continuation;
    for (let number = 1; number <= 20; number++) {
      const query = new URLSearchParams({ 'list-type': '2', 'max-keys': '1000' }); if (continuation) query.set('continuation-token', continuation);
      const route = '/' + capture.resources[role].bucket + '/?' + query;
      const got = await api.s3(TAIL + role + '-r2-' + number, role, route, role === 'protected' ? pair : getStagingPair());
      const xml = response(ctx, got.envelope, 'GET', route).toString('utf8');
      assert.equal(xmlField(xml, 'Name'), capture.resources[role].bucket); pages.push(got.envelope);
      const truncated = xmlField(xml, 'IsTruncated'); assert(['true', 'false'].includes(truncated)); if (truncated === 'false') break;
      assert(number < 20); continuation = xmlField(xml, 'NextContinuationToken');
      assert(continuation && !tokens.has(continuation), 'RECOVERY_R2_CURSOR'); tokens.add(continuation);
    }
    result.buckets[role] = pages;
  }
  const releases = await api.pages(TAIL + 'releases', REPO + '/releases');
  assert(!releases.items.some(value => value.tag_name.startsWith('mcu-e-track-at32f435-v')), 'FORMAL_LINEAGE_PRESENT');
  const tag = await api.capture(TAIL + 'target-tag', 'https://api.github.com', REPO + '/git/ref/tags/mcu-e-track-at32f435-v3.2.9', { expected: [200, 404] });
  const peeled = [];
  if (tag.envelope.status === 200) {
    let object = tag.json().object;
    for (let depth = 0; object?.type === 'tag' && depth < 7; depth++) {
      assert.match(object.sha, /^[0-9a-f]{40}$/);
      const next = await api.capture(TAIL + 'target-tag-' + depth, 'https://api.github.com', REPO + '/git/tags/' + object.sha);
      peeled.push(next.envelope); object = next.json().object;
    }
    assert(object?.type === 'commit' && object.sha === C4, 'RECOVERY_PRODUCT_TAG');
  }
  result.target_tag = { ref: tag.envelope, peeled }; result.github.releases = releases.records; result.github.assets = {};
  for (const release of releases.items) {
    assert(Number.isSafeInteger(release.id) && release.id > 0, 'RECOVERY_RELEASE_ID');
    result.github.assets[release.id] = (await api.pages(TAIL + 'assets-' + release.id, REPO + '/releases/' + release.id + '/assets')).records;
  }
  result.protected_configuration = await afterConfiguration(ctx, api);
  assert.equal(ctx.used.size, 31, 'RECOVERY_PREFIX_NOT_CONSUMED');
  result.recovery = { source_commit: C4, source_bundle_commit: B4, tool_commit: ctx.toolCommit,
    input: ctx.io.fileRef(FIXTURE), complete_originals: ctx.input.after_complete, failed_originals: ctx.input.after_failed,
    interpretation: 'Original C4 after responses retain their original times; only missing tail reads were executed.' };
  const snapshot = ctx.io.write('snapshots/after.json', result);
  ctx.io.write('recovery/after-result.json', { ok: true, snapshot, old_complete: 31, old_failed: 1,
    new_d1_reads: ctx.fresh.length, first_new_d1: ctx.fresh[0], product_commit: C4, tool_commit: ctx.toolCommit,
    source_commit: C4, source_bundle_commit: B4, freeze_commit: ctx.toolCommit });
  return result;
}
function assemble(ctx) {
  const afterResult = ctx.io.read('recovery/after-result.json'); assert.equal(afterResult.ok, true);
  const manifest = ctx.document(ctx.files.get('rehearsal-manifest.json'));
  assert.equal(manifest.schema, 'p44-observations-v1'); assert.deepEqual(manifest.target, ctx.input.target);
  assert(manifest.run_a && manifest.run_b && manifest.artifact && manifest.artifact_listing, 'RECOVERY_MANIFEST_INCOMPLETE');
  manifest.snapshots = { before: ctx.before, after: JSON.parse(reference(ctx.io, afterResult.snapshot)) };
  manifest.readbacks = ctx.document(ctx.files.get('readbacks.json'));
  assert.equal(Object.keys(manifest.readbacks).length, 3); for (const record of Object.values(manifest.readbacks)) ctx.original(record.body);
  manifest.reviewer_attestation = ctx.input.reviewer_attestation;
  const output = ctx.io.write('manifest.json', manifest);
  ctx.io.write('recovery/assemble-result.json', { ok: true, manifest: output, source_commit: C4,
    source_bundle_commit: B4, freeze_commit: ctx.toolCommit, platform_operations: 0 });
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
function validatorArgs(label) {
  assert(['formal-precheck', 'formal-rerun-plan'].includes(label), 'RECOVERY_VALIDATOR_LABEL');
  const args = ['-I', '-S', '-B', 'Tools/acceptance/validate_bundle.py', '--contract', 'docs/acceptance-contracts/P4-4-v5.contract.json',
    '--repo-root', s.root.replaceAll('\\', '/'), '--previous-contract', 'docs/acceptance-contracts/P4-4-v4.contract.json',
    '--previous-matrix', 'docs/acceptance-contracts/P4-4-v4/final-evidence-matrix.json', '--matrix',
    'docs/acceptance-contracts/P4-4-v5/evidence-matrix.json'];
  if (label === 'formal-rerun-plan') args.push('--write-rerun-plan', 'rerun-plan.json');
  return args;
}
async function runCommand(io, label, command, args, environment) {
  assert(/^[a-z0-9-]+$/.test(label), 'RECOVERY_COMMAND_LABEL'); commandAllowed(command, args);
  const stem = 'recovery-commands/' + label;
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
async function main(args) {
  const io = makeIO();
  if (args[0] === 'run') {
    const [, label, command, ...rest] = args;
    const contract = JSON.parse(fs.readFileSync(s.guard(CONTRACT)));
    assert.equal(contract.status, 'FROZEN'); assert.equal(contract.contract_id, 'P4-4-v5');
    const actual = ['node', SELF, ...args].join(' ');
    if (!['formal-precheck', 'formal-rerun-plan'].includes(label)) assert(contract.commands.some(item => item.id === label && item.command === actual), 'RECOVERY_FROZEN_COMMAND');
    else { assert.equal(command, 'python'); assert.deepEqual(rest, validatorArgs(label), 'RECOVERY_VALIDATOR_COMMAND'); }
    return runCommand(io, label, command, rest, containedEnvironment(path.join(s.root, '.cache/p44-v5-host')));
  }
  assert(args.length === 1 && ['after', 'assemble'].includes(args[0]), 'RECOVERY_MODE');
  return withLeaves(io, async () => {
    const ctx = validatePrefix(loadRecovery(io));
    const contractBytes = fs.readFileSync(s.guard(CONTRACT)), contract = JSON.parse(contractBytes);
    admit(ctx, contract, s.git(['rev-parse', 'HEAD']), pythonAdmission(), s.sha256(contractBytes));
    assert.equal(s.git(['branch', '--show-current']), BRANCH);
    assert.equal(s.git(['diff', '--name-only', C4, ctx.toolCommit, '--', 'Tools/acceptance/', 'Tools/provenance/manifest_profiles.json']), '', 'RECOVERY_FROZEN_LEAVES_CHANGED');
    if (args[0] === 'after') await after(ctx); else assemble(ctx);
    console.log(JSON.stringify({ ok: true, mode: args[0], product_commit: C4, tool_commit: ctx.toolCommit })); return 0;
  });
}
module.exports = { DATA, CONTRACT, C4, B4, I4, BRANCH, REPO, FIXTURE, OLD, TAIL, GAP, SCHEMA_SQL, TOKEN_ID_SHA,
  makeIO, reference, configureHttp, withLeaves, loadRecovery, validatePrefix, admit, pythonAdmission, tables, allowedRead, d1Read, afterConfiguration,
  after, assemble, containedEnvironment, commandAllowed, validatorArgs, runCommand, main };
if (require.main === module) main(process.argv.slice(2)).then(code => { process.exitCode = code; }).catch(error => {
  console.error(JSON.stringify({ ok: false, error_code: /^[A-Z0-9_]+$/.test(error.code || '') ? error.code : 'RECOVERY_FAILED' })); process.exitCode = 1;
});
