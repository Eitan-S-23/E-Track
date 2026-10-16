// Read-only Cloudflare/S3 evidence. curl owns SigV4; no upload or custom runtime.
const fs = require('node:fs');
const path = require('node:path');
const cp = require('node:child_process');
const assert = require('node:assert/strict');
const s = require('./session.cjs');

const workerNames = ['trace-update-service-staging', 'e-track-firmware-p41-test'];
const databases = [
  { role: 'protected', name: 'trace-update-staging', id: '0133ad9e-d4a2-4fef-a659-4f2bf3d3a645' },
  { role: 'test', name: 'e-track-firmware-p41-test', id: '2617e1e1-956f-42ce-a465-da56d84abf06' }
];
const buckets = [
  { role: 'protected', name: 'trace-update-staging-releases' },
  { role: 'test', name: 'e-track-firmware-p41-test-releases' }
];
const mode = process.argv[2], label = process.argv[3];
assert(['preflight', 'snapshot', 'assets'].includes(mode) && /^[a-z0-9-]+$/.test(label || ''));
const directory = s.guard(s.outputRoot + '/cloud/' + label);
const receiptPath = s.guard(directory + '/receipt.json');
assert(!fs.existsSync(directory), 'Preserve previous observation');
const owned = JSON.parse(fs.readFileSync(s.guard('.cache/cf-firmware-setup-20261015/d1-edit-r2/resources-created.json')));
const account = owned.accountId;
assert(/^[0-9a-f]{32}$/.test(account));
assert.equal(owned.r2.name, buckets[1].name);
assert.equal(owned.d1.id, databases[1].id);
const token = fs.readFileSync(s.guard('.cache/cf-auth-input/token.txt'), 'utf8').trim();
assert(token && !/\s/.test(token));
const sensitive = [token, account];
const redact = text => sensitive.reduce((value, secret) => value.replaceAll(secret, '[REDACTED]'), String(text));
const report = { mode, label, started: new Date().toISOString(), accountSha256: s.hash(account),
  purpose: 'P4-1 protected-resource and test-resource read-only evidence',
  credentialSource: 'Existing local provisioning credential; never exported or persisted',
  requests: [], files: [], ok: false, mutationsRequested: 0 };
let sequence = 0;

function save(name, value) {
  const bytes = Buffer.isBuffer(value) ? value : Buffer.from(JSON.stringify(value, null, 2) + '\n');
  const result = s.write(path.join(directory, name), bytes);
  report.files.push(result);
  return result;
}

async function api(route, sql) {
  assert(++sequence <= 120, 'Read-only request budget exceeded');
  const prefix = 'accounts/' + account + '/';
  const allowed = ['user/tokens/verify', prefix + 'workers/scripts', prefix + 'r2/buckets',
    prefix + 'd1/database?per_page=100', ...workerNames.map(name => prefix + 'workers/scripts/' + name + '/settings'),
    ...databases.map(db => prefix + 'd1/database/' + db.id + '/query')];
  assert(allowed.includes(route), 'Unreviewed Cloudflare route');
  if (sql !== undefined) {
    assert(databases.some(db => route === prefix + 'd1/database/' + db.id + '/query'));
    assert(/^SELECT\s/i.test(sql) && !/;|\b(?:INSERT|UPDATE|DELETE|CREATE|DROP|ALTER|REPLACE|PRAGMA|ATTACH)\b/i.test(sql), 'Only one SELECT is allowed');
  }
  const method = sql === undefined ? 'GET' : 'POST';
  const started = new Date().toISOString();
  const response = await fetch('https://api.cloudflare.com/client/v4/' + route, { method, redirect: 'error',
    headers: { Authorization: 'Bearer ' + token, 'Content-Type': 'application/json' },
    body: sql === undefined ? undefined : JSON.stringify({ sql }), signal: AbortSignal.timeout(60000) });
  const bytes = Buffer.from(await response.arrayBuffer());
  const data = JSON.parse(bytes);
  const entry = { sequence, method, route: route.replace(account, '[ACCOUNT]'), sql,
    started, ended: new Date().toISOString(), status: response.status, cfRay: response.headers.get('cf-ray'),
    responseSha256: s.hash(bytes), success: data.success };
  report.requests.push(entry);
  if (route === 'user/tokens/verify') {
    entry.tokenActive = data.result?.status === 'active';
  } else {
    entry.response = save(String(sequence).padStart(3, '0') + '-api.json', Buffer.from(redact(bytes)));
    entry.responseSanitized = bytes.toString() !== redact(bytes);
  }
  assert.equal(response.status, 200, 'Cloudflare read failed: HTTP ' + response.status);
  assert.equal(data.success, true, 'Cloudflare read did not succeed');
  if (sql !== undefined) {
    assert.equal(data.result.length, 1);
    for (const result of data.result) {
      assert(result.success && result.meta.rows_written === 0 && result.meta.changed_db === false,
        'D1 read returned unexpected write/state evidence');
    }
  }
  return data;
}

function s3(credentials, bucket, { head = false, continuation, object } = {}) {
  assert(buckets.some(item => item.name === bucket));
  assert(++sequence <= 120, 'Read-only request budget exceeded');
  const query = new URLSearchParams({ 'list-type': '2', 'max-keys': '1000' });
  if (continuation !== undefined) query.set('continuation-token', continuation);
  const stem = path.join(directory, String(sequence).padStart(3, '0') + '-s3');
  const headerPath = s.guard(stem + '.headers'), bodyPath = s.guard(stem + '.body');
  assert(!fs.existsSync(headerPath) && !fs.existsSync(bodyPath));
  fs.mkdirSync(s.guard(directory), { recursive: true });
  const config = 'aws-sigv4 = "aws:amz:auto:s3"\nuser = ' + JSON.stringify(credentials.id + ':' + credentials.key) + '\n';
  const env = s.environment();
  env.CURL_HOME = env.HOME;
  const args = ['--disable', '--config', '-', '--silent', '--show-error', '--proto', '=https',
    '--connect-timeout', '15', '--max-time', '60', '--max-filesize', '16777216',
    '--dump-header', headerPath, '--output', bodyPath, '--write-out', '%{http_code}'];
  if (head) args.push('--head');
  if (object !== undefined) assert(/^trace\/firmware\/e-track-at32f435\/[a-zA-Z0-9.-]+\/[a-zA-Z0-9.-]+$/.test(object));
  const suffix = object === undefined ? (head ? '' : '?' + query.toString()) : object.split('/').map(encodeURIComponent).join('/');
  args.push(`https://${account}.r2.cloudflarestorage.com/${bucket}/${suffix}`);
  const started = new Date().toISOString();
  const result = cp.spawnSync('curl.exe', args, { cwd: s.root, env, input: config, encoding: 'utf8',
    windowsHide: true, timeout: 70000, maxBuffer: 1024 * 1024 });
  const responseFiles = [headerPath, bodyPath].filter(p => fs.existsSync(p)).map(p => ({
    path: path.relative(s.root, p).replaceAll('\\', '/'), size_bytes: fs.statSync(p).size,
    sha256: s.hash(fs.readFileSync(p)) }));
  report.files.push(...responseFiles);
  report.requests.push({ sequence, method: head ? 'HEAD' : 'GET', operation: object === undefined ? (head ? 'HeadBucket' : 'ListObjectsV2') : 'GetObject', object,
    bucket, started, ended: new Date().toISOString(), status: Number(result.stdout?.trim()),
    exitCode: result.status, pid: result.pid, processClosed: true, stderr: redact(result.stderr || ''),
    files: responseFiles });
  assert(!result.error && result.status === 0, 'S3 read transport failed; preserve receipt without retry');
  assert.equal(Number(result.stdout.trim()), 200, 'S3 read was not admitted');
  return head ? null : fs.readFileSync(bodyPath, object === undefined ? 'utf8' : undefined);
}

function xmlText(text, name) {
  const values = [...text.matchAll(new RegExp('<' + name + '>([^<]*)</' + name + '>', 'g'))];
  assert.equal(values.length, 1, 'Missing/ambiguous S3 pagination field: ' + name);
  return values[0][1].replace(/&(?:amp|lt|gt|quot|apos);/g,
    token => ({ '&amp;': '&', '&lt;': '<', '&gt;': '>', '&quot;': '"', '&apos;': "'" })[token]);
}

async function main() {
  const verified = await api('user/tokens/verify');
  assert.equal(verified.result.status, 'active');
  assert(/^[0-9a-f]{32}$/.test(verified.result.id));
  const credentials = { id: verified.result.id, key: s.hash(token) };
  sensitive.push(credentials.id, credentials.key);
  if (mode === 'assets') {
    const evidence = JSON.parse(fs.readFileSync(s.guard(process.argv[4]), 'utf8'));
    const target = JSON.parse(fs.readFileSync(s.guard(s.outputRoot + '/formal/target.json'), 'utf8'));
    assert.equal(evidence.ok, true);
    assert.equal(evidence.metadata.commitSha, target.commitSha);
    assert.equal(evidence.metadata.versionName, target.versionName);
    assert.deepEqual(evidence.metadata.assets.map(asset => asset.kind), ['full', 'patch', 'recovery']);
    report.assets = [];
    for (const asset of evidence.metadata.assets) {
      assert(asset.r2Key.endsWith('/' + asset.fileName));
      const bytes = s3(credentials, buckets[1].name, { object: asset.r2Key });
      assert.equal(bytes.length, asset.sizeBytes);
      assert.equal(s.hash(bytes), asset.sha256);
      report.assets.push({ kind: asset.kind, r2Key: asset.r2Key, fileName: asset.fileName,
        sizeBytes: bytes.length, sha256: s.hash(bytes), requestSequence: sequence });
    }
    report.ok = true;
    return;
  }
  const prefix = 'accounts/' + account + '/';
  const workers = await api(prefix + 'workers/scripts');
  const r2 = await api(prefix + 'r2/buckets');
  const d1 = await api(prefix + 'd1/database?per_page=100');
  assert(Array.isArray(workers.result));
  const listedBuckets = r2.result.buckets ?? r2.result;
  assert(Array.isArray(listedBuckets));
  assert(Array.isArray(d1.result) && d1.result_info?.total_count === d1.result.length);
  const relevantWorkers = workers.result.filter(w => /^(?:trace-update-service|e-track-firmware)/.test(w.id));
  assert.deepEqual(relevantWorkers.map(w => w.id).sort(), workerNames.slice().sort(), 'Review changed release-service scope before execution');
  assert.deepEqual(listedBuckets.map(b => b.name).sort(), buckets.map(b => b.name).sort(), 'Review additional bucket scope before execution');
  for (const database of databases) assert(d1.result.some(db => db.uuid === database.id && db.name === database.name));
  report.inventory = { workers: workers.result.map(w => ({ id: w.id, etag: w.etag, modified_on: w.modified_on })),
    databases: d1.result.map(db => ({ name: db.name, id: db.uuid })), buckets: listedBuckets.map(b => b.name) };
  report.bindings = [];
  for (const name of workerNames) {
    const settings = await api(prefix + 'workers/scripts/' + name + '/settings');
    const index = workerNames.indexOf(name), bindings = settings.result.bindings;
    assert.equal(bindings.find(b => b.name === 'DB')?.id, databases[index].id);
    assert.equal(bindings.find(b => b.name === 'RELEASES_BUCKET')?.bucket_name, buckets[index].name);
    report.bindings.push({ name, bindings });
  }
  if (mode === 'preflight') {
    for (const bucket of buckets) s3(credentials, bucket.name, { head: true });
    for (const db of databases) await api(prefix + 'd1/database/' + db.id + '/query',
      "SELECT name,type,sql FROM sqlite_master WHERE type IN ('table','index','trigger') ORDER BY type,name");
    report.scope = { protected: { worker: workerNames[0], database: databases[0], bucket: buckets[0] },
      test: { worker: workerNames[1], database: databases[1], bucket: buckets[1] },
      note: 'Old Trace is protected despite its staging label. No separate firmware-production resource is assumed.' };
  } else {
    report.databases = [];
    for (const db of databases) {
      const route = prefix + 'd1/database/' + db.id + '/query';
      const schema = await api(route, "SELECT name,type,sql FROM sqlite_master WHERE type IN ('table','index','trigger') ORDER BY type,name");
      const tables = schema.result[0].results.filter(row => row.type === 'table' && !row.name.startsWith('sqlite_')
        && !row.name.startsWith('_cf_')).map(row => row.name);
      const contents = {};
      for (const table of tables) {
        assert(/^[a-z_][a-z0-9_]*$/i.test(table), 'Unexpected D1 table name');
        const counted = await api(route, 'SELECT COUNT(*) AS count FROM "' + table + '"');
        const count = counted.result[0].results[0].count;
        assert(Number.isSafeInteger(count) && count >= 0 && count <= 20000, 'Unbounded snapshot table');
        const rows = [];
        for (let offset = 0; offset < count; offset += 500) {
          const page = await api(route, 'SELECT * FROM "' + table + '" ORDER BY rowid LIMIT 500 OFFSET ' + offset);
          rows.push(...page.result[0].results);
        }
        assert.equal(rows.length, count);
        contents[table] = rows;
      }
      const artifact = save(db.role + '-d1.json', { database: db, schema: schema.result[0].results, tables: contents });
      report.databases.push({ ...db, artifact });
    }
    report.r2 = [];
    for (const bucket of buckets) {
      let continuation;
      const pages = [];
      for (let page = 1; page <= 20; page++) {
        const body = s3(credentials, bucket.name, { continuation });
        assert.equal(xmlText(body, 'Name'), bucket.name);
        const truncated = xmlText(body, 'IsTruncated');
        assert(['true', 'false'].includes(truncated));
        pages.push(report.requests.at(-1));
        if (truncated === 'false') break;
        assert(page < 20, 'Incomplete bounded S3 inventory');
        const next = xmlText(body, 'NextContinuationToken');
        assert(next && next !== continuation, 'Invalid S3 continuation');
        continuation = next;
      }
      report.r2.push({ ...bucket, complete: true, pages });
    }
  }
  report.ok = true;
}

main().catch(error => { report.error = { name: error.name, message: redact(error.message), causeCode: error.cause?.code };
  process.exitCode = 1; }).finally(() => {
  report.ended = new Date().toISOString(); report.closed = true;
  s.write(receiptPath, redact(JSON.stringify(report, null, 2)) + '\n');
  console.log(JSON.stringify({ mode, label, ok: report.ok, requests: report.requests.length,
    mutationsRequested: report.mutationsRequested, receipt: path.relative(s.root, receiptPath), error: report.error }));
});
