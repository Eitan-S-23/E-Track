// Offline C4-original integration and native request/wrapper checks. No cloud operations.
const r = require('../../Tools/ota/p44-after-recovery.cjs');
const s = require('../../Tools/acceptance/p44/run.cjs');
const c = require('../../Tools/acceptance/p44/capture.cjs');
const { fs, path, assert } = s;
const { gzipSync } = require('node:zlib');
const originalRoot = path.join(s.root, 'docs/acceptance-contracts/P4-4-v4/evidence');
const base = new Map();
const bytes = value => Buffer.isBuffer(value) ? value : Buffer.from(JSON.stringify(value));
const ref = (name, value) => ({ path: name, size_bytes: value.length, sha256: s.sha256(value) });
function walk(directory, prefix = '') {
  for (const entry of fs.readdirSync(directory, { withFileTypes: true })) {
    assert(!entry.isSymbolicLink()); const name = prefix + entry.name;
    if (entry.isDirectory()) walk(path.join(directory, entry.name), name + '/');
    else base.set(name, fs.readFileSync(path.join(directory, entry.name)));
  }
}
walk(originalRoot);
const originalFiles = [...base].map(([name, value]) => ref(name, value));
base.set('recovery/c4.contract.json', fs.readFileSync(path.join(s.root, 'docs/acceptance-contracts/P4-4-v4.contract.json')));
base.set('recovery/c4.final-evidence-matrix.json', fs.readFileSync(path.join(s.root, 'docs/acceptance-contracts/P4-4-v4/final-evidence-matrix.json')));
const input = { schema: 'p44-after-recovery-v1', source_commit: r.C4, source_bundle_commit: r.B4, source_index_commit: r.I4,
  source_contract: ref('recovery/c4.contract.json', base.get('recovery/c4.contract.json')),
  source_matrix: ref('recovery/c4.final-evidence-matrix.json', base.get('recovery/c4.final-evidence-matrix.json')), files: originalFiles };
for (const [key, name] of Object.entries({ target: 'target.json', before: 'snapshots/before.json', negatives: 'negatives.json',
  run_a: 'run-a/final.json', run_b: 'run-b/final.json', reviewer_attestation: 'reviewer-attestation.json' })) input[key] = ref(name, base.get(name));
const old = originalFiles.filter(item => item.path.startsWith(r.OLD) && item.path.endsWith('.http.json'));
input.after_complete = old.filter(item => JSON.parse(base.get(item.path)).completed);
input.after_failed = old.filter(item => !JSON.parse(base.get(item.path)).completed);
base.set(r.FIXTURE, bytes(input));
let assertions = 0;
function check(action) { action(); assertions++; }
async function rejects(action, pattern) { await assert.rejects(action, pattern); assertions++; }
function memoryIO() {
  const data = new Map(base), root = path.join(s.root, '.cache/p44-v5-development/memory-unused'), created = [];
  return { data, created, base: root, destination: name => path.join(root, name), exists: name => data.has(name),
    readBytes: name => { assert(data.has(name), 'MISSING_MEMORY_ORIGINAL'); return data.get(name); },
    read: name => JSON.parse(data.get(name)), fileRef: name => ref(name, data.get(name)), addSensitive() {},
    write(name, value) { assert(!data.has(name), 'MEMORY_ORIGINAL_EXISTS'); const raw = bytes(value); data.set(name, raw); created.push(name); return ref(name, raw); } };
}
async function bound(io, operation, http) {
  const exists = fs.existsSync;
  fs.existsSync = name => { const relative = path.relative(io.base, String(name)); return relative && !relative.startsWith('..') && !path.isAbsolute(relative) ? io.data.has(relative.replaceAll('\\', '/')) : exists(name); };
  try { return await r.withLeaves(io, operation, { http, privateRoot: path.join(s.root, '.cache/p44-v5-development/private-unused') }); }
  finally { fs.existsSync = exists; }
}
function change(io, name, value) {
  const raw = bytes(value); io.data.set(name, raw);
  const packet = io.read(r.FIXTURE), next = ref(name, raw);
  packet.files = packet.files.map(item => item.path === name ? next : item);
  for (const key of ['after_complete', 'after_failed']) packet[key] = packet[key].map(item => item.path === name ? next : item);
  for (const key of ['target', 'before', 'negatives', 'run_a', 'run_b']) if (packet[key].path === name) packet[key] = next;
  io.data.set(r.FIXTURE, bytes(packet));
}
const fixtureTime = '2026-10-20T04:00:00.000Z';
function mockAPI(ctx, alter = () => {}) {
  const calls = [], schemas = {}, data = {};
  for (const [role, database] of Object.entries(ctx.before.databases)) {
    schemas[role] = c._test.d1Document(database.schema).result[0].results;
    data[role] = Object.fromEntries(Object.entries(database.tables).map(([name, table]) =>
      [name, table.pages.flatMap(record => c._test.d1Document(record).result[0].results)]));
  }
  function http(label, method, route, payload, request, status = 200, gzip = false) {
    const decoded = bytes(payload), wire = gzip ? gzipSync(decoded) : decoded;
    const envelope = { method, path: route, status, completed: true, started: fixtureTime, ended: fixtureTime,
      response_headers: { ...(gzip ? { 'content-encoding': 'gzip' } : {}), 'content-length': String(wire.length) },
      body: ctx.io.write(label + '.body', wire) };
    if (request) envelope.request = ctx.io.write(label + '.request.json', request);
    if (gzip) envelope.decoded_body = ctx.io.write(label + '.decoded.body', decoded);
    ctx.io.write(label + '.http.json', envelope);
    return { envelope, bytes: decoded, json: () => JSON.parse(decoded) };
  }
  const api = {
    async d1(label, role, sql) {
      assert(label.startsWith(r.TAIL)); assert.notEqual(role, 'production', 'OLD_PRODUCTION_REPLAY'); calls.push({ label, role, sql });
      let rows;
      if (sql === r.SCHEMA_SQL) rows = schemas[role];
      else if (sql.startsWith('SELECT COUNT')) rows = [{ count: data[role][sql.match(/FROM "([^"]+)"/)[1]].length }];
      else { const match = sql.match(/^SELECT \* FROM "([^"]+)" ORDER BY rowid LIMIT 8 OFFSET ([0-9]+)$/); assert(match); rows = data[role][match[1]].slice(Number(match[2]), Number(match[2]) + 8); }
      rows = structuredClone(rows); alter({ kind: 'd1', label, rows, sql });
      const got = http(label, 'POST', '/accounts/[ACCOUNT]/d1/database/' + c.resources[role].db + '/query',
        { success: true, result: [{ success: true, meta: { rows_written: 0, changed_db: false }, results: rows }] }, { sql }, 200, true);
      return { envelope: got.envelope, rows };
    },
    async s3(label, role, route) {
      assert.notEqual(role, 'production'); calls.push({ label, role, method: 'GET' });
      const record = ctx.before.buckets[role][0];
      return http(label, 'GET', route, ctx.io.readBytes(record.body.path));
    },
    async pages(label, route, field) {
      calls.push({ label, route }); let records;
      const environment = route.includes('/environments/firmware-production') ? 'production' : 'rehearsal';
      if (field) records = ctx.before.protected_configuration[environment][{ variables: 'variables', secrets: 'secrets', branch_policies: 'branches' }[field]];
      else if (route.includes('/releases/') && route.endsWith('/assets')) records = ctx.before.github.assets[route.match(/releases\/(\d+)/)[1]];
      else records = ctx.before.github.releases;
      const items = records.flatMap(record => { const value = JSON.parse(ctx.io.readBytes(record.body.path)); return field ? value[field] : value; });
      const cloned = structuredClone(items); alter({ kind: 'pages', field, items: cloned, environment });
      const got = http(label + '-1', 'GET', route + '?per_page=100&page=1', field ? { [field]: cloned, total_count: cloned.length } : cloned);
      return { items: cloned, records: [got.envelope] };
    },
    async capture(label, origin, route) {
      assert.equal(origin, 'https://api.github.com'); calls.push({ label, route }); let value, status = 200;
      if (route.includes('/git/ref/tags/')) { value = { message: 'Not Found' }; status = 404; }
      else if (route.includes('/git/ref/heads/')) value = { object: { sha: ctx.toolCommit } };
      else if (route.endsWith('/actions/variables/OTA_BOOT_CHAIN_READY')) value = { value: 'false' };
      else { const role = route.endsWith('firmware-production') ? 'production' : 'rehearsal'; value = JSON.parse(ctx.io.readBytes(ctx.before.protected_configuration[role].configuration.body.path)); }
      value = structuredClone(value); alter({ kind: 'capture', label, route, value });
      return http(label, 'GET', route, value, undefined, status);
    }
  };
  return { api, calls };
}
async function originalsAndTail() {
  const io = memoryIO();
  await bound(io, async () => {
    const ctx = r.validatePrefix(r.loadRecovery(io)); ctx.toolCommit = 'a'.repeat(40);
    check(() => { assert.equal(ctx.old.size, 31); assert.equal(ctx.input.after_failed.length, 1); });
    const { api, calls } = mockAPI(ctx);
    const snapshot = await r.after(ctx, api, async () => ({ accessKeyId: 'not-a-real-id', secretAccessKey: 'not-a-real-secret' }), () => ({}));
    check(() => {
      assert.equal(calls[0].label, r.TAIL + r.GAP); assert.equal(calls[0].sql, 'SELECT * FROM "audit_logs" ORDER BY rowid LIMIT 8 OFFSET 16');
      assert.equal(ctx.used.size, 31); assert.equal(ctx.fresh.filter(label => label.startsWith('protected-audit_logs-rows8-')).length, 20);
      assert(calls.every(call => call.role !== 'production'));
      assert.equal(snapshot.recovery.source_commit, r.C4); assert.equal(snapshot.protected_configuration.tool_commit, ctx.toolCommit);
      assert.equal(JSON.parse(snapshot.protected_configuration.rehearsal.values.OTA_PREVIOUS_RELEASE_JSON).targetCommitSha, r.C4);
      for (const [name, value] of base) assert(io.data.get(name).equals(value), 'ORIGINAL_BYTES_CHANGED');
      assert(!io.created.some(name => name.startsWith(r.OLD))); assert.equal(io.read('recovery/after-result.json').old_failed, 1);
    });
    r.assemble(ctx);
    check(() => { assert.equal(io.read('manifest.json').target.sha256, input.target.sha256); assert.equal(io.read('recovery/assemble-result.json').platform_operations, 0); });
    await rejects(() => r.after(ctx, api), /RECOVERY_ALREADY_EXECUTED/);
    check(() => assert.throws(() => r.assemble(ctx), /MEMORY_ORIGINAL_EXISTS/));
  });
  for (const mutate of [
    (io, name, record) => { record.completed = false; change(io, name, record); },
    (io, name, record) => { record.started = '2026-10-19T01:00:00Z'; change(io, name, record); },
    (io, name, record) => { record.path = record.path.replace(c.resources.production.db, c.resources.staging.db); change(io, name, record); },
    (io, name, record) => { io.data.set(record.body.path, Buffer.from('tampered')); },
    (io, name, record) => { io.data.set(record.request.path, bytes({ sql: 'DELETE FROM apps' })); },
  ]) {
    const next = memoryIO(), name = input.after_complete[0].path, record = next.read(name); mutate(next, name, record);
    await bound(next, async () => { check(() => assert.throws(() => r.validatePrefix(r.loadRecovery(next)))); assert.equal(next.created.length, 0); });
  }
  for (const mutation of ['decoded', 'failed-washed', 'failed-code', 'bad-row-count', 'duplicate-prefix', 'bad-target', 'schema-tail']) {
    const next = memoryIO(), packet = next.read(r.FIXTURE);
    if (mutation === 'decoded') {
      const name = packet.after_complete.find(item => next.read(item.path).decoded_body).path, record = next.read(name);
      change(next, record.decoded_body.path, Buffer.from('{}')); record.decoded_body = next.read(r.FIXTURE).files.find(item => item.path === record.decoded_body.path); change(next, name, record);
    } else if (mutation.startsWith('failed-')) {
      const name = packet.after_failed[0].path, value = next.read(name);
      if (mutation === 'failed-washed') value.completed = true; else value.error_code = 'ECONNRESET'; change(next, name, value);
    } else if (mutation === 'bad-row-count') {
      const name = r.OLD + 'protected-audit_logs-rows8-8.http.json', record = next.read(name);
      const value = JSON.parse(require('node:zlib').gunzipSync(next.data.get(record.body.path))); value.result[0].results.pop();
      const decoded = bytes(value), wire = gzipSync(decoded);
      change(next, record.body.path, wire); change(next, record.decoded_body.path, decoded);
      const updated = next.read(r.FIXTURE).files; record.body = updated.find(item => item.path === record.body.path);
      record.decoded_body = updated.find(item => item.path === record.decoded_body.path); record.response_headers['content-length'] = String(wire.length); change(next, name, record);
    } else if (mutation === 'duplicate-prefix') { packet.after_complete[30] = packet.after_complete[0]; next.data.set(r.FIXTURE, bytes(packet)); }
    else if (mutation === 'bad-target') { const value = next.read('target.json'); value.commitSha = 'f'.repeat(40); change(next, 'target.json', value); }
    else {
      const before = next.read('snapshots/before.json'), record = before.databases.staging.schema;
      const decoded = JSON.parse(require('node:zlib').gunzipSync(next.data.get(record.body.path))); decoded.result[0].results.push({ name: 'invalid_tail', type: 'table', sql: 5 });
      const raw = bytes(decoded), wire = gzipSync(raw); change(next, record.body.path, wire); change(next, record.decoded_body.path, raw);
      record.body = ref(record.body.path, wire); record.decoded_body = ref(record.decoded_body.path, raw); record.response_headers['content-length'] = String(wire.length);
      change(next, 'snapshots/before.json', before);
    }
    await bound(next, async () => { check(() => assert.throws(() => r.validatePrefix(r.loadRecovery(next)), undefined, mutation)); assert.equal(next.created.length, 0); });
  }
}
async function regressions() {
  for (const schema of [[{ name: 'bad', type: 'other', sql: 'x' }], [{ name: 'bad', type: 'table', sql: null }],
    [{ name: 'bad', type: 'table', sql: 'CREATE TABLE bad(id)', extra: true }], [{ name: 'bad', type: 'table', sql: 'CREATE TABLE bad(id) WITHOUT ROWID' }]]) check(() => assert.throws(() => r.tables(schema)));
  check(() => assert.deepEqual(r.tables([{ name: '_cf_KV', type: 'table', sql: 'CREATE TABLE _cf_KV(id) WITHOUT ROWID' }]), []));
  for (const sql of ['DELETE FROM apps', 'SELECT * FROM "apps" ORDER BY rowid LIMIT 500 OFFSET 0', 'SELECT 1; DROP TABLE apps']) check(() => assert.throws(() => r.allowedRead('staging', sql)));
  check(() => assert.throws(() => r.allowedRead('other', r.SCHEMA_SQL)));
  for (const value of [['node', ['-e', 'process.exit(0)']], ['python', ['-c', 'pass']], ['node', ['unreviewed.cjs']]]) check(() => assert.throws(() => r.commandAllowed(...value)));
  for (const option of ['-eprocess.exit(0)', '--eval=process.exit(0)', '-p', '-r', '--require=unreviewed.cjs', '--import=unreviewed.cjs']) {
    check(() => assert.throws(() => r.commandAllowed('node', [option, 'Tools/ota/p44-after-recovery.cjs'])));
  }
  for (const option of ['-cpass', '-mhttp.server', '-X', '--help']) {
    check(() => assert.throws(() => r.commandAllowed('python', [option, 'Tools/acceptance/validate_bundle.py'])));
  }
  check(() => {
    assert.deepEqual(r.validatorArgs('formal-rerun-plan'), [...r.validatorArgs('formal-precheck'), '--write-rerun-plan', 'rerun-plan.json']);
    assert.throws(() => r.validatorArgs('formal-final-check'));
    assert(r.validatorArgs('formal-precheck').includes('docs/acceptance-contracts/P4-4-v4/final-evidence-matrix.json'));
    assert.throws(() => r.validatorArgs('unreviewed'));
  });
  check(() => assert.throws(() => r.pythonAdmission(() => ({ status: 1, stdout: '{}' })), /RECOVERY_PYTHON_ADMISSION/));
  for (const [name, alter] of [
    ['secret-rotation', x => { if (x.kind === 'pages' && x.field === 'secrets') x.items[0].updated_at = '2026-10-21T00:00:00Z'; }],
    ['wrong-remote', x => { if (x.kind === 'capture' && x.route.includes('/git/ref/heads/')) x.value.object.sha = r.C4; }],
    ['gate', x => { if (x.kind === 'capture' && x.route.endsWith('/actions/variables/OTA_BOOT_CHAIN_READY')) x.value.value = 'true'; }],
    ['descriptor', x => { if (x.kind === 'pages' && x.field === 'variables') { const value = x.items.find(v => v.name === 'OTA_PREVIOUS_RELEASE_JSON'); if (value) value.value = '{}'; } }],
  ]) {
    const io = memoryIO(); await bound(io, async () => {
      const ctx = r.validatePrefix(r.loadRecovery(io)); ctx.toolCommit = 'a'.repeat(40);
      await rejects(() => r.afterConfiguration(ctx, mockAPI(ctx, alter).api)); check(() => assert(!io.exists('recovery/after-result.json'), name));
    });
  }
  const io = memoryIO(); await bound(io, async () => {
    const ctx = r.validatePrefix(r.loadRecovery(io)); let calls = 0;
    await rejects(() => r.d1Read(ctx, 'production-unplanned-count', 'production', 'SELECT COUNT(*) AS count FROM "apps"', { d1() { calls++; } }), /RECOVERY_PRODUCTION_REPLAY/);
    await rejects(() => r.d1Read(ctx, 'staging-schema', 'staging', r.SCHEMA_SQL, { d1() { calls++; } }), /RECOVERY_FIRST_REQUEST/);
    check(() => assert.equal(calls, 0));
  });
  const duplicate = memoryIO(); await bound(duplicate, async () => {
    const ctx = r.validatePrefix(r.loadRecovery(duplicate)); ctx.toolCommit = 'a'.repeat(40);
    const { api } = mockAPI(ctx, value => { if (value.kind === 'd1' && value.label === r.TAIL + r.GAP) value.rows[1].id = value.rows[0].id; });
    await rejects(() => r.after(ctx, api, async () => ({})), /RECOVERY_DUPLICATE_ROW/);
    check(() => assert(!duplicate.exists('snapshots/after.json')));
  });
  const admitted = memoryIO(); await bound(admitted, async () => {
    const ctx = r.validatePrefix(r.loadRecovery(admitted)), head = 'a'.repeat(40);
    const contract = { contract_id: 'P4-4-v5', status: 'FROZEN', freeze_commit: head,
      external_inputs: [{ evidence_path: 'evidence/' + r.FIXTURE, evidence_sha256: s.sha256(admitted.readBytes(r.FIXTURE)) }] };
    const hash = s.sha256(bytes(contract)), report = { schema: 'p44-after-admission-v1', ok: true, freeze_commit: head,
      source_commit: r.C4, source_bundle_commit: r.B4, contract_sha256: hash };
    admitted.write('recovery-commands/formal-precheck.json', { exitCode: 0 });
    for (const kind of ['before', 'negatives']) admitted.write('recovery/' + kind + '-result.json', {
      schema: 'p44-after-existing-v1', ok: true, kind, source: ctx.input[kind], source_bundle_commit: r.B4, platform_operations: 0 });
    check(() => assert.equal(r.admit(ctx, contract, head, report, hash).target.commitSha, r.C4));
    for (const altered of [{ ...report, freeze_commit: r.C4 }, { ...report, ok: false }, { ...report, schema: 'stale' },
      { ...report, contract_sha256: '0'.repeat(64) }, { ...report, source_bundle_commit: '0'.repeat(40) }]) {
      check(() => assert.throws(() => r.admit(ctx, contract, head, altered, hash)));
    }
    check(() => assert.throws(() => r.admit(ctx, contract, r.C4, report, hash)));
  });
}
async function nativeTransport() {
  const undici = require(path.join(s.root, 'app/bluetooth_flutter_Trace/cloudflare/update-service/worker/node_modules/undici'));
  const agent = new undici.MockAgent(); agent.disableNetConnect();
  agent.get('https://api.github.com').intercept({ path: r.REPO + '/releases', method: 'GET' }).replyWithError(Object.assign(new Error('offline'), { code: 'UND_ERR_CONNECT_TIMEOUT' }));
  let options;
  const http = { request: undici.request, ProxyAgent: class extends undici.Dispatcher {
    constructor(value) { super(); options = value; }
    dispatch(value, handler) { return agent.dispatch(value, handler); }
    async destroy() { await agent.close(); }
  } };
  const io = memoryIO(), timeout = AbortSignal.timeout, limits = [];
  AbortSignal.timeout = ms => { limits.push(ms); return timeout(ms); };
  c._test.setContext({ account: '1'.repeat(32), local: 'OFFLINE_VALUE', gh: 'OFFLINE_VALUE', sensitive: ['OFFLINE_VALUE'] });
  try {
    await bound(io, async () => {
      await rejects(() => c._test.capture(r.TAIL + 'native-timeout', 'https://api.github.com', r.REPO + '/releases'), { code: 'UND_ERR_CONNECT_TIMEOUT' });
      agent.assertNoPendingInterceptors();
      const record = io.read(r.TAIL + 'native-timeout.http.json');
      check(() => {
        assert.equal(record.error_code, 'UND_ERR_CONNECT_TIMEOUT'); assert.equal(record.request_attempts, 1); assert.equal(record.request_failures.length, 1);
        assert(!record.retry_reservation); assert.deepEqual(limits, [60000]);
        assert.equal(options.proxyTls.timeout, 30000); assert.equal(options.requestTls.timeout, 30000);
        assert.equal(options.requestTls.rejectUnauthorized, true); assert.equal(options.allowH2, false);
        assert(!io.created.some(name => name.includes('retry-2')));
      });
    }, http);
  } finally { AbortSignal.timeout = timeout; c._test.setContext(undefined); }
}
async function physicalWrapper(output) {
  const io = r.makeIO(path.join(output, 'wrapper'));
  const env = r.containedEnvironment(path.join(output, 'host'));
  const code = await r.runCommand(io, 'help', 'python', ['-I', '-S', '-B', 'Tools/acceptance/p44/inspect.py', '--help'], env);
  check(() => {
    assert.equal(code, 0); const receipt = io.read('recovery-commands/help.json');
    assert.equal(receipt.exitCode, 0); assert.equal(receipt.process_closed, true); assert(receipt.started && receipt.ended);
    assert.equal(s.sha256(io.readBytes(receipt.output.path)), receipt.output.sha256);
    assert(!fs.existsSync(path.join(output, 'wrapper/commands')));
  });
  await rejects(() => r.runCommand(io, 'help', 'python', ['-I', '-S', '-B', 'Tools/acceptance/p44/inspect.py', '--help'], env), /RECOVERY_COMMAND_EXISTS/);
  check(() => assert.throws(() => io.write('../escape.json', {}), /RECOVERY_PATH/));
  check(() => assert.throws(() => io.write('recovery-commands/help.json', {}), /RECOVERY_ORIGINAL_EXISTS/));
  io.addSensitive('OFFLINE_PROTECTED_DERIVED_KEY');
  check(() => assert.throws(() => io.write('secret.body', gzipSync(Buffer.from('OFFLINE_PROTECTED_DERIVED_KEY'))), /RECOVERY_SENSITIVE_OUTPUT/));
  check(() => assert(!io.exists('secret.body')));
}
async function main() {
  assert.equal(process.argv[2], '--output-dir');
  const output = s.guard(path.resolve(process.argv[3]));
  const relative = path.relative(path.join(s.root, '.cache/p44-v5-development'), output);
  assert(relative && !relative.startsWith('..') && !path.isAbsolute(relative)); assert(!fs.existsSync(output), 'SELFTEST_EXISTS');
  fs.mkdirSync(output, { recursive: true });
  const io = r.makeIO(output), started = new Date().toISOString();
  const source = ['Tools/ota/p44-after-recovery.cjs', 'tests/ota/test_p44_after_recovery.cjs'].map(name => ref(name, fs.readFileSync(path.join(s.root, name))));
  let failure;
  try { await originalsAndTail(); await regressions(); await nativeTransport(); await physicalWrapper(output); }
  catch (error) { failure = error; }
  const result = { scope: 'OFFLINE_DEVELOPMENT_SELFTEST_ONLY', ok: !failure, started, ended: new Date().toISOString(), assertions,
    source, cloud_operations: 0, retained_complete_originals: input.after_complete.length, retained_failed_originals: input.after_failed.length,
    error_code: failure?.code || (failure ? 'SELFTEST_FAILED' : undefined),
    source_location: failure?.stack?.match(/(?:test_p44_after_recovery\.cjs|p44-after-recovery\.cjs):[0-9]+:[0-9]+/)?.[0] };
  io.write('result.json', result); console.log(JSON.stringify(result)); process.exitCode = failure ? 1 : 0;
}
main().catch(error => { console.error(JSON.stringify({ ok: false, error_code: error.code || 'SELFTEST_ENTRY_FAILED' })); process.exitCode = 1; });
