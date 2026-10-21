const io = require('./io.cjs');
const { execFileSync } = require('node:child_process');
const { pathToFileURL } = require('node:url');
const { DatabaseSync } = require('node:sqlite');
const expectedCommit = process.argv[2];
io.assert.match(expectedCommit || '', /^[0-9a-f]{40}$/);
const resultPath = io.reserve('verify-remediation-01.json');
const fixturePath = 'docs/ota-exec-notes/P4-1-r2-registration-qualification-2026-10-15/operations/verified-metadata.json';
const fixtureDir = 'docs/ota-exec-notes/P4-1-r2-registration-qualification-2026-10-15/fixture';
const scratch = io.output('verification-inputs');
const source = file => io.path.join(io.worktree, file);
const storageBytes = io.fs.readFileSync(source(fixturePath));
const storage = JSON.parse(storageBytes);
const d1 = io.readJson(io.output('d1-preparation-01.json'));
const current = d1.databases.find(x => x.name === 'e-track-firmware-p41-test')
  .observations.find(x => x.id === 'latest').result[0].results[0];
const canonicalBytes = Buffer.from(current.registration_json + '\n');
io.assert.equal(io.sha256(canonicalBytes), 'fe435e1a0bc6afea344566846b1a63e8de39ee9335a98a874e97fbcc82b543a4');
const currentMetadata = JSON.parse(current.registration_json);
const inputs = new Map([[fixturePath, storageBytes], ['current.json', canonicalBytes], ['stale.json', storageBytes],
  ['conflicting.json', Buffer.from(JSON.stringify({ ...currentMetadata, releaseNotes: 'Independent conflict control' }) + '\n')]]);
for (const asset of storage.assets) inputs.set(fixtureDir + '/' + asset.fileName, io.fs.readFileSync(source(fixtureDir + '/' + asset.fileName)));
const destinations = [...inputs].map(([file, bytes]) => ({ file, bytes, path: io.reserve('verification-inputs/' + file) }));
const report = { startedAt: new Date().toISOString(), kind: 'INDEPENDENT_OFFLINE_REMEDIATION_REVIEW',
  sourceCommit: expectedCommit, node: process.version, realNetwork: false, formalAcceptance: 'NOT_RUN',
  dataSource: 'Fixed read-only staging D1 preparation snapshot and unchanged historical storage fixture',
  sqlite: 'Independent in-memory three-table predicate harness, not a remote Worker or full migration campaign', qualification: [], streams: [] };
async function main() {
  const head = execFileSync('git', ['--no-optional-locks', 'rev-parse', 'HEAD'], { cwd: io.worktree, encoding: 'utf8', windowsHide: true }).trim();
  io.assert.equal(head, expectedCommit);
  const paths = ['.github/scripts/firmware-bindings-check.mjs',
    'app/bluetooth_flutter_Trace/cloudflare/update-service/scripts'];
  io.assert.equal(execFileSync('git', ['--no-optional-locks', 'diff', 'HEAD', '--name-only', '--', ...paths],
    { cwd: io.worktree, encoding: 'utf8', windowsHide: true }).trim(), '', 'Review committed product bytes only');
  for (const item of destinations) {
    io.guard(item.path); io.fs.mkdirSync(io.path.dirname(item.path), { recursive: true });
    io.guard(item.path); io.fs.writeFileSync(item.path, item.bytes, { flag: 'wx' });
  }
  report.inputs = destinations.map(x => ({ file: x.file, sha256: io.sha256(x.bytes), bytes: x.bytes.length }));
  const load = file => import(pathToFileURL(source(file)).href);
  const prefix = 'app/bluetooth_flutter_Trace/cloudflare/update-service/scripts/';
  const { checkFirmwareBindings } = await load('.github/scripts/firmware-bindings-check.mjs');
  const { verifyMonotonic } = await load(prefix + 'firmware-monotonic.mjs');
  const { canonicalJson } = await load(prefix + 'firmware-schema.mjs');
  const { verifyStoredFirmwareAsset } = await load(prefix + 'upload-firmware-r2-asset.mjs');
  const env = { GITHUB_EVENT_NAME: 'workflow_dispatch', INPUT_CHECK_BINDINGS: 'true', INPUT_PUBLISH: 'false',
    INPUT_REHEARSAL: 'false', OTA_BOOT_CHAIN_READY: 'false', GITHUB_REPOSITORY: 'Eitan-S-23/E-Track',
    GITHUB_SHA: expectedCommit, FIRMWARE_REHEARSAL_BINDINGS_CHECK_COMMIT: expectedCommit,
    GITHUB_RUN_ID: '1', GITHUB_RUN_ATTEMPT: '1', CLOUDFLARE_ACCOUNT_ID: 'a'.repeat(32),
    TRACE_R2_ACCESS_KEY_ID: 'b'.repeat(32), TRACE_R2_SECRET_ACCESS_KEY: 'c'.repeat(64), TRACE_DEPLOY_TOKEN: 'synthetic-only',
    TRACE_UPDATE_SERVICE_URL: 'https://e-track-firmware-p41-test.tangjichentudou.workers.dev', TRACE_R2_BUCKET: 'e-track-firmware-p41-test-releases' };
  async function qualify(name, history, file, wrongHash = false) {
    const observed = { name, history, file, requests: 0, selects: 0, connects: 0, reads: 0, puts: 0 };
    report.qualification.push(observed);
    const sqlite = new DatabaseSync(':memory:');
    sqlite.exec('CREATE TABLE firmware_channels(app_id TEXT,device_model TEXT,legacy_current_release_id TEXT);'
      + 'CREATE TABLE firmware_releases_legacy(app_id TEXT,device_model TEXT,version_code INTEGER);'
      + 'CREATE TABLE firmware_releases(app_id TEXT,device_model TEXT,version_code INTEGER,registration_json TEXT)');
    if (history) sqlite.prepare('INSERT INTO firmware_releases VALUES(?,?,?,?)')
      .run(currentMetadata.appId, currentMetadata.deviceModel, current.version_code, current.registration_json);
    const db = { prepare(sql) { observed.selects++; io.assert.match(sql, /^SELECT /);
      const statement = sqlite.prepare(sql); return { bind(...values) { return { async first() { return statement.get(...values) ?? null; } }; } }; } };
    const fetcher = async (url, init) => {
      observed.requests++; io.assert.equal(new URL(url).pathname, '/api/ci/firmware/preflight');
      const body = JSON.parse(init.body);
      try {
        const state = await verifyMonotonic(db, body.metadata);
        return Response.json({ ok: true, schemaVersion: 1, environment: 'staging', requestId: init.headers['X-Request-Id'],
          metadataSha256: io.sha256(canonicalJson(body.metadata) + '\n'), ...state }, { headers: { 'X-Request-Id': init.headers['X-Request-Id'] } });
      } catch (error) { io.assert.equal(error.code, 'RELEASE_CONFLICT'); return Response.json({ errorCode: error.code }, { status: 409 }); }
    };
    const connect = async (_config, operation) => { observed.connects++; return operation({
      async head(key) { const asset = storage.assets.find(x => x.r2Key === key);
        return { size: asset.sizeBytes, etag: 'stable', customMetadata: { sha256: asset.sha256, kind: asset.kind } }; },
      async get(key) { observed.reads++; const asset = storage.assets.find(x => x.r2Key === key);
        return { body: new ReadableStream({ start(c) { c.enqueue(inputs.get(fixtureDir + '/' + asset.fileName)); c.close(); } }) }; },
      async put() { observed.puts++; throw Error('Forbidden write in read-only review'); },
    }); };
    try {
      const result = await checkFirmwareBindings({ root: scratch, env: { ...env,
        FIRMWARE_REHEARSAL_BINDINGS_CHECK_METADATA_PATH: file,
        FIRMWARE_REHEARSAL_BINDINGS_CHECK_METADATA_SHA256: wrongHash ? '0'.repeat(64) : io.sha256(inputs.get(file)) }, connect, fetcher });
      observed.ok = result.ok; observed.preflightInput = result.preflightInput;
      io.assert.equal(result.fixtureSha256, io.sha256(storageBytes));
      io.assert.equal(result.preflightInput.commitSha, currentMetadata.commitSha);
      io.assert.notEqual(result.preflightInput.commitSha, expectedCommit);
    } catch (error) { observed.errorCode = error.code; observed.message = error.message; }
    finally { sqlite.close(); }
    io.assert.equal(observed.puts, 0);
    return observed;
  }
  for (const history of [false, true]) {
    const value = await qualify(history ? 'registered-30208' : 'empty-control', history, 'current.json');
    io.assert.equal(value.ok, true); io.assert.equal(value.errorCode, undefined);
    io.assert.equal(value.requests, 2); io.assert.equal(value.selects, 6);
    io.assert.equal(value.connects, 1); io.assert.equal(value.reads, 3);
  }
  for (const file of ['stale.json', 'conflicting.json']) {
    const value = await qualify(file, true, file);
    io.assert.equal(value.errorCode, 'RELEASE_CONFLICT'); io.assert.equal(value.selects, 3); io.assert.equal(value.connects, 0);
  }
  const wrong = await qualify('raw-hash-mismatch', true, 'current.json', true);
  io.assert.equal(wrong.errorCode, 'INVALID_PARAMETER'); io.assert.equal(wrong.requests, 0); io.assert.equal(wrong.connects, 0);
  const asset = storage.assets[0];
  for (const mode of ['valid', 'empty-failure', 'partial-failure', 'abort', 'different-bytes']) {
    let pulls = 0; const expected = mode === 'different-bytes' ? 'R2_OBJECT_CONFLICT' : mode === 'valid' ? null : 'R2_VERIFY_FAILED';
    const data = Buffer.from(inputs.get(fixtureDir + '/' + asset.fileName)); if (mode === 'different-bytes') data[0] ^= 1;
    const observation = { mode }; report.streams.push(observation);
    const bucket = { async head() { return { size: asset.sizeBytes, etag: 'stable', customMetadata: { sha256: asset.sha256, kind: asset.kind } }; },
      async get() { return { body: new ReadableStream({ pull(c) { pulls++;
        if (mode === 'valid' || mode === 'different-bytes') { c.enqueue(data); c.close(); }
        else if (mode === 'partial-failure' && pulls === 1) c.enqueue(data.subarray(0, 4));
        else c.error(mode === 'abort' ? new DOMException('private-sentinel', 'AbortError') : new Error('private-sentinel'));
      } }) }; } };
    try { observation.ok = (await verifyStoredFirmwareAsset(storage, asset.fileName, bucket)).ok; }
    catch (error) { observation.errorCode = error.code; observation.message = error.message; }
    if (expected) io.assert.equal(observation.errorCode, expected); else io.assert.equal(observation.ok, true);
    io.assert.ok(!JSON.stringify(observation).includes('private-sentinel'));
  }
  report.pass = true;
}
main().catch(error => { report.error = error.message; process.exitCode = 1; }).finally(() => {
  report.endedAt = new Date().toISOString(); io.writeJson(resultPath, report);
  process.stdout.write(JSON.stringify({ output: resultPath, pass: report.pass || false,
    qualificationCases: report.qualification.length, streamCases: report.streams.length, error: report.error }) + '\n');
});
