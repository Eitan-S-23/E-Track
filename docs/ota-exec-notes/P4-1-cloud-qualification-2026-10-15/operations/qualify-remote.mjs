import fs from 'node:fs';
import path from 'node:path';
import assert from 'node:assert/strict';
import { createHash } from 'node:crypto';
import { fileURLToPath, pathToFileURL } from 'node:url';

const directory = path.dirname(fileURLToPath(import.meta.url));
const root = path.resolve(directory, '../../..');
const scripts = path.join(root, 'app/bluetooth_flutter_Trace/cloudflare/update-service/scripts');
const { outputPath } = await import(pathToFileURL(path.join(scripts, 'firmware-cli.mjs')));
const config = JSON.parse(fs.readFileSync(path.join(directory, 'wrangler.json'), 'utf8'));
const owned = JSON.parse(fs.readFileSync(path.join(directory, 'resources-created.json'), 'utf8'));
assert.equal(config.name, 'e-track-firmware-p41-test');
assert.equal(config.account_id, owned.accountId);
assert.equal(config.d1_databases[0].database_id, owned.d1.id);
assert.equal(config.r2_buckets[0].bucket_name, 'e-track-firmware-p41-test-releases');
assert.equal(config.r2_buckets[0].bucket_name, owned.r2.name);
assert.equal(config.kv_namespaces[0].id, owned.kv.id);
const phase = process.argv[2];
assert.ok(['preflight', 'api-negative', 'protected-after'].includes(phase));
const resultFile = outputPath(root, path.join(directory, `remote-${phase}.json`));
assert.equal(fs.existsSync(resultFile), false);
const token = fs.readFileSync(path.join(root, '.cache/cf-auth-input/token.txt'), 'utf8').trim();
const secrets = JSON.parse(fs.readFileSync(path.join(root, '.cache/cf-auth-input/firmware-test-secrets.json'), 'utf8'));
assert.ok(token && secrets.TRACE_DEPLOY_TOKEN);
const sensitive = [token, ...Object.values(secrets)].filter(x => typeof x === 'string' && x.length > 10);
const redact = value => sensitive.reduce((text, secret) => text.split(secret).join('[REDACTED]'), String(value));
for (const name of Object.keys(process.env)) {
  if (/^(CLOUDFLARE_|CF_|TRACE_|GH_|GITHUB_TOKEN|OTA_AES_KEY|NODE_OPTIONS|NODE_COMPILE_CACHE|GIT_CONFIG|GIT_INDEX_FILE)/i.test(name)) delete process.env[name];
}
const runtime = outputPath(root, path.join(directory, 'runtime/qualification'));
const outputs = { TEMP: 'tmp', TMP: 'tmp', TMPDIR: 'tmp', HOME: 'home', USERPROFILE: 'home',
  APPDATA: 'appdata', LOCALAPPDATA: 'localappdata', XDG_CACHE_HOME: 'cache', XDG_CONFIG_HOME: 'config',
  XDG_DATA_HOME: 'data', npm_config_cache: 'npm', WRANGLER_LOG_PATH: 'logs' };
for (const [key, relative] of Object.entries(outputs)) {
  const target = outputPath(root, path.join(runtime, relative));
  fs.mkdirSync(target, { recursive: true });
  process.env[key] = target;
}
Object.assign(process.env, { CLOUDFLARE_API_TOKEN: token, CLOUDFLARE_ACCOUNT_ID: config.account_id,
  CI: '1', NODE_USE_ENV_PROXY: '1', WRANGLER_SEND_METRICS: 'false', WRANGLER_LOG: 'none',
  GIT_OPTIONAL_LOCKS: '0', GIT_TERMINAL_PROMPT: '0', npm_config_update_notifier: 'false' });
const result = { purpose: 'ISOLATED_SYNTHETIC_QUALIFICATION_NOT_REHEARSAL', phase,
  started: new Date().toISOString(), worker: config.name, databaseId: owned.d1.id,
  bucket: owned.r2.name, observations: [], ok: false };
const serviceUrl = 'https://e-track-firmware-p41-test.tangjichentudou.workers.dev';
const sha = bytes => createHash('sha256').update(bytes).digest('hex');
try {
  if (phase === 'protected-after') {
    const oldDirectory = path.join(root, '.cache/cf-readonly-20261015-r1');
    const original = JSON.parse(fs.readFileSync(path.join(oldDirectory, 'd1-inventory.json'), 'utf8'));
    assert.equal(original.route, `accounts/${config.account_id}/d1/database/0133ad9e-d4a2-4fef-a659-4f2bf3d3a645/query`);
    const response = await fetch(`https://api.cloudflare.com/client/v4/${original.route}`, {
      method: 'POST', redirect: 'error', headers: { Authorization: `Bearer ${token}`, 'Content-Type': 'application/json' },
      body: JSON.stringify({ sql: original.sql }), signal: AbortSignal.timeout(30000) });
    const body = await response.json();
    result.observations.push({ action: 'PROTECTED_D1_SELECT_ONLY', sql: original.sql,
      status: response.status, cfRay: response.headers.get('cf-ray'), body });
    assert.equal(response.status, 200);
    assert.equal(body.success, true);
    assert.ok(body.result.every(x => x.success && x.meta.rows_written === 0 && !x.meta.changed_db));
    assert.deepEqual(body.result.map(x => x.results), original.body.result.map(x => x.results));
    const before = JSON.parse(fs.readFileSync(path.join(oldDirectory, 'bindings.json'), 'utf8'))[0];
    assert.equal(before.route, `accounts/${config.account_id}/workers/scripts/trace-update-service-staging/settings`);
    const settingsResponse = await fetch(`https://api.cloudflare.com/client/v4/${before.route}`, {
      headers: { Authorization: `Bearer ${token}` }, redirect: 'error', signal: AbortSignal.timeout(30000) });
    const settings = await settingsResponse.json();
    assert.equal(settingsResponse.status, 200);
    assert.equal(settings.success, true);
    assert.equal(settings.result.compatibility_date, before.result.compatibility_date);
    assert.deepEqual(settings.result.compatibility_flags, before.result.compatibility_flags);
    assert.equal(settings.result.bindings.length, before.result.bindings.length);
    const observedBindings = before.result.bindings.map(old => {
      const current = settings.result.bindings.find(x => x.name === old.name);
      assert.ok(current);
      const comparable = Object.fromEntries(Object.keys(old).map(key => [key, current[key]]));
      assert.deepEqual(comparable, old);
      return comparable;
    });
    result.observations.push({ action: 'PROTECTED_WORKER_OBSERVABLE_BINDINGS_UNCHANGED', status: settingsResponse.status,
      cfRay: settingsResponse.headers.get('cf-ray'), bindings: observedBindings });
    result.limitations = 'Count and observable binding comparison only; not complete production R2/Release/channel identity acceptance.';
    result.ok = true;
  } else if (phase === 'api-negative') {
    const prior = JSON.parse(fs.readFileSync(path.join(directory, 'remote-preflight.json'), 'utf8'));
    assert.equal(prior.observations[0].status, 200);
    assert.equal(prior.observations[1].status, 200);
    const fixtureDir = path.resolve(directory, '../qualification-fixture/firmware-release-tests/case-R5kVz9/prepared');
    const original = JSON.parse(fs.readFileSync(path.join(fixtureDir, 'cloudflare-firmware-release-metadata.json'), 'utf8'));
    const verification = JSON.parse(fs.readFileSync(path.join(fixtureDir, 'verification.json'), 'utf8'));
    for (const asset of original.assets) {
      const bytes = fs.readFileSync(path.join(fixtureDir, asset.fileName));
      assert.equal(bytes.length, asset.sizeBytes);
      assert.equal(sha(bytes), asset.sha256);
    }
    const { buildFirmwareMetadata } = await import(pathToFileURL(path.join(scripts, 'build-firmware-release-metadata.mjs')));
    const { canonicalJson } = await import(pathToFileURL(path.join(scripts, 'firmware-schema.mjs')));
    const { registerFirmware } = await import(pathToFileURL(path.join(scripts, 'register-firmware-release.mjs')));
    const release = { ...original, releaseNotes: 'P4-1 isolated synthetic qualification; not installable firmware, not a formal rehearsal.' };
    delete release.assets;
    const metadata = await buildFirmwareMetadata({ release, assetsDir: fixtureDir,
      finalImage: path.join(fixtureDir, 'app-final.bin'), repository: 'Eitan-S-23/E-Track',
      patchBases: [{ baseImageSha256: verification.base.imageSha256, baseVersionCode: verification.base.versionCode }] });
    const metadataFile = outputPath(root, path.join(directory, 'qualification-metadata.json'));
    fs.writeFileSync(metadataFile, canonicalJson(metadata) + '\n', { flag: 'wx' });
    result.fixtureMetadataSha256 = sha(fs.readFileSync(metadataFile));
    result.fixtureProvenance = { ciRun: '38677391835', archiveSha256: '44fe3d9f8923f8d9f570be3835c8893d458b0572e842cf1b19aea3f7ca9abb90',
      case: 'firmware-release-tests/case-R5kVz9/prepared', syntheticCommit: metadata.commitSha, syntheticRunId: metadata.runId };
    const query = async label => {
      const sql = "SELECT (SELECT count(*) FROM firmware_releases) AS releases, (SELECT count(*) FROM firmware_release_assets) AS assets, (SELECT count(*) FROM firmware_channels) AS channels, (SELECT count(*) FROM audit_logs WHERE action='register_firmware_release') AS register_audits, (SELECT count(*) FROM firmware_releases WHERE state='ready') AS ready";
      const response = await fetch(`https://api.cloudflare.com/client/v4/accounts/${config.account_id}/d1/database/${owned.d1.id}/query`,
        { method: 'POST', redirect: 'error', headers: { Authorization: `Bearer ${token}`, 'Content-Type': 'application/json' },
          body: JSON.stringify({ sql }), signal: AbortSignal.timeout(30000) });
      const body = await response.json();
      result.observations.push({ action: label, sql, status: response.status, cfRay: response.headers.get('cf-ray'), body });
      assert.equal(response.status, 200);
      assert.equal(body.success, true);
      assert.ok(body.result.every(x => x.success && x.meta.rows_written === 0 && !x.meta.changed_db));
      return body.result[0].results;
    };
    const before = await query('D1_NEGATIVES_BEFORE');
    assert.deepEqual(before, [{ releases: 0, assets: 0, channels: 0, register_audits: 0, ready: 0 }]);
    const expectedCodes = [];
    const fetcher = async (url, options) => {
      assert.equal(new URL(url).origin, serviceUrl);
      const response = await fetch(url, options);
      result.observations.push({ action: 'REAL_REGISTER_HTTP', status: response.status,
        requestId: response.headers.get('x-request-id'), body: await response.clone().json() });
      return response;
    };
    // Deliberately false readback claims are negative inputs, never saved as verified metadata.
    const falseClaims = structuredClone(metadata);
    falseClaims.assets.forEach(asset => { asset.r2Verified = true; });
    const rejected = async (label, input, deployToken, code, status) => {
      const start = result.observations.length;
      await assert.rejects(registerFirmware(input, { serviceUrl, deployToken, fetcher }), error => {
        assert.equal(error.code, code); assert.equal(error.exitCode, 1); return true;
      });
      const responses = result.observations.slice(start).filter(x => x.action === 'REAL_REGISTER_HTTP');
      assert.equal(responses.length, 1);
      assert.equal(responses[0].status, status);
      expectedCodes.push({ label, errorCode: code, httpStatus: status, requests: responses.length, expectedExitCode: 1 });
    };
    try {
      await rejected('MISSING_R2_ASSETS', falseClaims, secrets.TRACE_DEPLOY_TOKEN, 'BACKEND_UNAVAILABLE', 503);
      await rejected('INVALID_BEARER', falseClaims, 'p41-intentionally-invalid', 'TOKEN_INVALID', 401);
      for (const [label, change, status, code] of [
        ['UNKNOWN_SCHEMA_FIELD', { unexpectedQualificationField: true }, 400, 'INVALID_PARAMETER'],
        ['NONFORMAL_INPUT', { isFormalRelease: false }, 403, 'FORMAL_RELEASE_REQUIRED']
      ]) {
        const requestId = crypto.randomUUID();
        const response = await fetcher(`${serviceUrl}/api/ci/firmware/releases`, { method: 'POST', redirect: 'error',
          headers: { Authorization: `Bearer ${secrets.TRACE_DEPLOY_TOKEN}`, 'Content-Type': 'application/json',
            Accept: 'application/json', 'X-Request-Id': requestId }, body: JSON.stringify({ ...falseClaims, ...change }),
          signal: AbortSignal.timeout(30000) });
        assert.equal(response.status, status);
        assert.equal((await response.json()).errorCode, code);
        assert.equal(response.headers.get('x-request-id'), requestId);
        expectedCodes.push({ label, errorCode: code, httpStatus: status, requests: 1 });
      }
    } finally {
      const after = await query('D1_NEGATIVES_AFTER');
      assert.deepEqual(after, before);
      result.noD1BusinessEffects = true;
      result.cases = expectedCodes;
    }
    result.ok = true;
  } else {
  const endpoint = `https://api.cloudflare.com/client/v4/accounts/${config.account_id}/workers/scripts/${config.name}/settings`;
  const response = await fetch(endpoint, { headers: { Authorization: `Bearer ${token}` },
    redirect: 'error', signal: AbortSignal.timeout(30000) });
  const settings = await response.json();
  result.observations.push({ action: 'GET_NEW_WORKER_SETTINGS', status: response.status,
    cfRay: response.headers.get('cf-ray'), body: settings });
  assert.equal(response.status, 200);
  assert.equal(settings.success, true);
  const bindings = settings.result.bindings;
  assert.equal(bindings.find(x => x.name === 'DB').id, owned.d1.id);
  assert.equal(bindings.find(x => x.name === 'RELEASES_BUCKET').bucket_name, owned.r2.name);
  assert.equal(bindings.find(x => x.name === 'MANIFEST_CACHE').namespace_id, owned.kv.id);
  assert.equal(bindings.find(x => x.name === 'GITHUB_REPO').text, 'E-Track');
  assert.equal(bindings.find(x => x.name === 'FIRMWARE_V2_CUTOVER_EPOCH').text, '1792039926');
  for (const name of ['DEPLOY_TOKEN_SHA256', 'DOWNLOAD_HMAC_KEY_CURRENT']) {
    assert.equal(bindings.find(x => x.name === name).type, 'secret_text');
  }
  const health = await fetch(`${serviceUrl}/healthz`, { redirect: 'error', signal: AbortSignal.timeout(20000) });
  const body = await health.json();
  result.observations.push({ action: 'GET_NEW_WORKER_HEALTH', status: health.status, body });
  assert.equal(health.status, 200);
  assert.equal(body.ok, true);
  assert.equal(body.environment, 'staging');
  const { withFirmwareBucket } = await import(pathToFileURL(path.join(scripts, 'upload-firmware-r2-asset.mjs')));
  await withFirmwareBucket({ bucketName: owned.r2.name, accountId: config.account_id, root: runtime,
    wranglerCwd: path.join(scripts, '../worker'), databaseId: owned.d1.id,
    databaseName: owned.d1.name }, async (bucket, db) => {
    const listing = await bucket.list({ limit: 10 });
    const rows = await db.prepare('SELECT (SELECT count(*) FROM firmware_releases) AS releases, (SELECT count(*) FROM firmware_release_assets) AS assets, (SELECT count(*) FROM firmware_channels) AS channels, (SELECT count(*) FROM audit_logs) AS audits').all();
    result.observations.push({ action: 'REAL_PRODUCTION_STORAGE_PROXY_READ', listing, rows });
    assert.equal(listing.objects.length, 0);
    assert.equal(listing.truncated, false);
    assert.equal(rows.success, true);
    assert.deepEqual(rows.results, [{ releases: 0, assets: 0, channels: 0, audits: 0 }]);
  });
  result.platformDisposed = true;
  result.bundleSha256 = sha(fs.readFileSync(path.resolve(directory, config.main)));
  result.ok = true;
  }
} catch (error) {
  result.error = { name: error.name, code: error.code, message: redact(error.message) };
  process.exitCode = 1;
} finally {
  result.finished = new Date().toISOString();
  fs.writeFileSync(resultFile, redact(JSON.stringify(result, null, 2)) + '\n', { flag: 'wx' });
  console.log(JSON.stringify({ phase, ok: result.ok, error: result.error, resultFile }));
  delete process.env.CLOUDFLARE_API_TOKEN;
}
