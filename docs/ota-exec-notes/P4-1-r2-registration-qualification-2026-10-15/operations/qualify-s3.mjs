import fs from 'node:fs';
import path from 'node:path';
import assert from 'node:assert/strict';
import { createHash } from 'node:crypto';
import { fileURLToPath, pathToFileURL } from 'node:url';
import { qualificationBucket } from './curl-r2-bucket.mjs';

const directory = path.dirname(fileURLToPath(import.meta.url));
const root = path.resolve(directory, '../..');
assert.equal(fs.realpathSync.native(process.cwd()), fs.realpathSync.native(root));
const scripts = path.join(root, 'app/bluetooth_flutter_Trace/cloudflare/update-service/scripts');
const { outputPath } = await import(pathToFileURL(path.join(scripts, 'firmware-cli.mjs')));
const { uploadFirmwareAsset } = await import(pathToFileURL(path.join(scripts, 'upload-firmware-r2-asset.mjs')));
const { registerFirmware } = await import(pathToFileURL(path.join(scripts, 'register-firmware-release.mjs')));
const { canonicalJson, contentDigest } = await import(pathToFileURL(path.join(scripts, 'firmware-schema.mjs')));
const phase = process.argv[2];
assert.ok(['first-upload', 'first-upload-r2', 'assets-register'].includes(phase));
const guard = value => outputPath(root, value);
const output = guard(path.join(directory, phase));
const receiptPath = guard(path.join(directory, phase + '.json'));
assert.equal(fs.existsSync(receiptPath), false);
assert.equal(fs.existsSync(output), false);
const verifiedMetadataPath = guard(path.join(directory, 'verified-metadata.json'));
if (phase === 'assets-register') assert.equal(fs.existsSync(verifiedMetadataPath), false);
const token = fs.readFileSync(path.join(root, '.cache/cf-auth-input/token.txt'), 'utf8').trim();
const owned = JSON.parse(fs.readFileSync(path.join(root, '.cache/cf-firmware-setup-20261015/d1-edit-r2/resources-created.json'), 'utf8'));
assert.equal(owned.accountId, 'af6dd848e6a21f1cd26d44b1b656af7b');
assert.equal(owned.r2.name, 'e-track-firmware-p41-test-releases');
assert.equal(owned.d1.id, '2617e1e1-956f-42ce-a465-da56d84abf06');
const metadataPath = path.join(root, '.cache/cf-firmware-setup-20261015/d1-edit-r2/qualification-metadata.json');
const metadata = JSON.parse(fs.readFileSync(metadataPath, 'utf8'));
const fixture = path.join(root, '.cache/cf-firmware-setup-20261015/qualification-fixture/firmware-release-tests/case-R5kVz9/prepared');
const hash = bytes => createHash('sha256').update(bytes).digest('hex');
assert.equal(hash(fs.readFileSync(metadataPath)), 'fbbd9b4756e8858e45a3ea5bf8c93d7c26b23a50740035a4f18ff5d0c5427ed7');
assert.equal(metadata.assets.length, 3);
assert.deepEqual(metadata.assets.map(asset => asset.kind), ['full', 'patch', 'recovery']);
const objects = metadata.assets.map(asset => asset.r2Key);
const bytesByName = new Map();
for (const asset of metadata.assets) {
  assert.equal(asset.r2Verified, false);
  assert.ok(asset.r2Key.startsWith('trace/firmware/e-track-at32f435/20801-'));
  const bytes = fs.readFileSync(path.join(fixture, asset.fileName));
  assert.equal(bytes.length, asset.sizeBytes);
  assert.equal(hash(bytes), asset.sha256);
  bytesByName.set(asset.fileName, bytes);
}
const sensitive = [token];
const redact = value => sensitive.reduce((text, secret) => text.split(secret).join('[REDACTED]'), String(value ?? ''));
const receipt = { purpose: 'ISOLATED_SYNTHETIC_S3_QUALIFICATION_NOT_REHEARSAL', phase,
  started: new Date().toISOString(), bucket: owned.r2.name, databaseId: owned.d1.id,
  productionModule: 'upload-firmware-r2-asset.mjs:uploadFirmwareAsset',
  transport: 'Test-side curl S3 adapter; not withFirmwareBucket or a workflow run',
  inputMetadataSha256: hash(fs.readFileSync(metadataPath)), objects, observations: [], cases: [], ok: false,
  sourceHashes: Object.fromEntries(['upload-firmware-r2-asset.mjs', 'register-firmware-release.mjs',
    'firmware-schema.mjs'].map(name => [name, hash(fs.readFileSync(path.join(scripts, name)))])) };
fs.mkdirSync(output, { recursive: true });
async function cf(route, body) {
  const response = await fetch('https://api.cloudflare.com/client/v4/' + route, {
    method: body ? 'POST' : 'GET', redirect: 'error',
    headers: { Authorization: `Bearer ${token}`, 'Content-Type': 'application/json' },
    ...(body ? { body: JSON.stringify(body) } : {}), signal: AbortSignal.timeout(30000) });
  const result = await response.json();
  receipt.observations.push({ action: route, status: response.status, cfRay: response.headers.get('cf-ray'),
    success: result.success, errors: result.errors });
  assert.equal(response.status, 200);
  assert.equal(result.success, true);
  return result;
}
async function counts(label) {
  const sql = "SELECT (SELECT count(*) FROM firmware_releases) AS releases, (SELECT count(*) FROM firmware_release_assets) AS assets, (SELECT count(*) FROM firmware_channels) AS channels, (SELECT count(*) FROM audit_logs WHERE action='register_firmware_release') AS register_audits, (SELECT count(*) FROM firmware_releases WHERE state='ready') AS ready";
  const body = await cf(`accounts/${owned.accountId}/d1/database/${owned.d1.id}/query`, { sql });
  receipt.observations.push({ action: label, sql, body });
  assert.ok(body.result.every(value => value.success && value.meta.rows_written === 0 && !value.meta.changed_db));
  return body.result[0].results;
}
async function snapshot(label) {
  const sql = 'SELECT * FROM firmware_releases ORDER BY id; SELECT * FROM firmware_release_assets ORDER BY id; SELECT * FROM firmware_channels ORDER BY id; SELECT * FROM audit_logs ORDER BY id;';
  const body = await cf(`accounts/${owned.accountId}/d1/database/${owned.d1.id}/query`, { sql });
  receipt.observations.push({ action: label, sql, body });
  assert.equal(body.result.length, 4);
  assert.ok(body.result.every(value => value.success && value.meta.rows_written === 0 && !value.meta.changed_db));
  return body.result.map(value => value.results);
}
try {
  const before = await counts('D1_BEFORE_FIRST_UPLOAD');
  assert.deepEqual(before, [{ releases: 0, assets: 0, channels: 0, register_audits: 0, ready: 0 }]);
  const verified = await cf('user/tokens/verify');
  assert.equal(verified.result.status, 'active');
  assert.match(verified.result.id, /^[0-9a-f]{32}$/);
  const temporary = await cf(`accounts/${owned.accountId}/r2/temp-access-credentials`, {
    bucket: owned.r2.name, parentAccessKeyId: verified.result.id,
    permission: 'object-read-write', ttlSeconds: 900, objects });
  for (const name of ['accessKeyId', 'secretAccessKey', 'sessionToken']) {
    assert.equal(typeof temporary.result[name], 'string');
    sensitive.push(temporary.result[name]);
  }
  receipt.credentialScope = { permission: 'object-read-write', ttlSeconds: 900, objects,
    persisted: false, passedToCurl: 'stdin only' };
  const bucket = qualificationBucket({ root, guard, directory: output, accountId: owned.accountId,
    bucketName: owned.r2.name, objects, credentials: temporary.result, observations: receipt.observations, redact });
  if (phase === 'assets-register') {
    const first = JSON.parse(fs.readFileSync(path.join(directory, 'first-upload-r2.json'), 'utf8'));
    assert.equal(first.ok, true);
    const secrets = JSON.parse(fs.readFileSync(path.join(root, '.cache/cf-auth-input/firmware-test-secrets.json'), 'utf8'));
    assert.ok(secrets.TRACE_DEPLOY_TOKEN);
    sensitive.push(...Object.values(secrets));
    const serviceUrl = 'https://e-track-firmware-p41-test.tangjichentudou.workers.dev';
    const settings = await cf(`accounts/${owned.accountId}/workers/scripts/e-track-firmware-p41-test/settings`);
    const bindings = settings.result.bindings;
    assert.equal(bindings.find(value => value.name === 'DB').id, owned.d1.id);
    assert.equal(bindings.find(value => value.name === 'RELEASES_BUCKET').bucket_name, owned.r2.name);
    receipt.verifiedBindings = bindings.filter(value => ['DB', 'RELEASES_BUCKET', 'GITHUB_OWNER', 'GITHUB_REPO', 'ENVIRONMENT'].includes(value.name));
    const fetcher = async (url, options) => {
      assert.equal(new URL(url).origin, serviceUrl);
      assert.equal(new URL(url).pathname, '/api/ci/firmware/releases');
      assert.equal(options.method, 'POST');
      const response = await fetch(url, options);
      receipt.observations.push({ action: 'REAL_REGISTER_HTTP', status: response.status,
        requestId: response.headers.get('x-request-id'), cfRay: response.headers.get('cf-ray'),
        requestBodySha256: hash(Buffer.from(options.body)), body: await response.clone().json() });
      return response;
    };
    const register = input => registerFirmware(input, { serviceUrl, deployToken: secrets.TRACE_DEPLOY_TOKEN, fetcher });
    const rejectRegister = async (label, input, status, code) => {
      const start = receipt.observations.length;
      await assert.rejects(register(input), error => {
        assert.equal(error.code, code); assert.equal(error.exitCode, 1); return true;
      });
      const responses = receipt.observations.slice(start).filter(value => value.action === 'REAL_REGISTER_HTTP');
      assert.equal(responses.length, 1);
      assert.equal(responses[0].status, status);
      receipt.cases.push({ label, status: 'PASS', httpStatus: status, errorCode: code, requests: 1,
        sharedClientExitCodeProperty: 1 });
    };
    const absentBefore = await snapshot('D1_BEFORE_PARTIAL_ASSETS_NEGATIVE');
    assert.deepEqual(absentBefore, [[], [], [], []]);
    const falseClaims = structuredClone(metadata);
    falseClaims.assets.forEach(asset => { asset.r2Verified = true; });
    await rejectRegister('PARTIAL_R2_ASSETS_REJECTED', falseClaims, 503, 'BACKEND_UNAVAILABLE');
    assert.deepEqual(await snapshot('D1_AFTER_PARTIAL_ASSETS_NEGATIVE'), absentBefore);

    const patch = metadata.assets[1];
    const corrupted = Buffer.from(bytesByName.get(patch.fileName));
    corrupted[corrupted.length - 1] ^= 1;
    const beforeBad = receipt.observations.length;
    await assert.rejects(uploadFirmwareAsset(metadata, patch.fileName, corrupted, bucket), error => {
      assert.equal(error.code, 'INVALID_PARAMETER'); assert.equal(error.exitCode, 1); return true;
    });
    assert.equal(receipt.observations.length, beforeBad);
    receipt.cases.push({ label: 'BAD_LOCAL_DIGEST_NO_REMOTE_CALL', status: 'PASS',
      sharedClientExitCodeProperty: 1, remoteRequests: 0 });

    receipt.uploads = [];
    for (const asset of metadata.assets) {
      const start = receipt.observations.length;
      const result = await uploadFirmwareAsset(metadata, asset.fileName, bytesByName.get(asset.fileName), bucket);
      receipt.uploads.push(result);
      const calls = receipt.observations.slice(start).filter(value => value.method);
      assert.equal(calls.at(-1).method, 'GET');
      assert.equal(calls.at(-1).status, 200);
      assert.equal(calls.at(-1).responseBodyLength, asset.sizeBytes);
      assert.equal(calls.at(-1).responseBodySha256, asset.sha256);
      if (asset.kind === 'full') {
        assert.equal(result.status, 'ALREADY_PRESENT');
        assert.equal(calls.some(value => value.method === 'PUT'), false);
      } else {
        assert.equal(calls[0].status, 404);
        assert.ok(calls.some(value => value.method === 'PUT' && value.requestHeaders['If-None-Match'] === '*'));
      }
      asset.r2Verified = true;
    }
    receipt.cases.push({ label: 'THREE_ASSETS_FULL_READBACK', status: 'PASS', assets: 3 });
    const heads = [];
    for (const asset of metadata.assets) {
      const head = await bucket.head(asset.r2Key);
      assert.equal(head.size, asset.sizeBytes);
      assert.deepEqual(head.customMetadata, { 'content-digest': contentDigest(asset.sha256), kind: asset.kind, sha256: asset.sha256 });
      assert.deepEqual(head.httpMetadata, { contentType: asset.kind === 'recovery' ? 'application/octet-stream' : 'application/vnd.e-track.etu',
        contentDisposition: `attachment; filename="${asset.fileName}"`, cacheControl: 'public, max-age=31536000, immutable' });
      heads.push(head);
    }
    const replayStart = receipt.observations.length;
    for (const asset of metadata.assets) {
      assert.equal((await uploadFirmwareAsset(metadata, asset.fileName, bytesByName.get(asset.fileName), bucket)).status, 'ALREADY_PRESENT');
    }
    assert.equal(receipt.observations.slice(replayStart).some(value => value.method === 'PUT'), false);
    receipt.cases.push({ label: 'IDENTICAL_UPLOAD_REPLAY_NO_PUT', status: 'PASS', assets: 3 });

    const changed = structuredClone(metadata);
    const full = metadata.assets[0];
    const different = Buffer.from(bytesByName.get(full.fileName));
    different[different.length - 1] ^= 1;
    changed.assets[0].sha256 = hash(different);
    const collisionStart = receipt.observations.length;
    await assert.rejects(uploadFirmwareAsset(changed, full.fileName, different, bucket), error => {
      assert.equal(error.code, 'R2_OBJECT_CONFLICT'); assert.equal(error.exitCode, 1); return true;
    });
    assert.equal(receipt.observations.slice(collisionStart).some(value => ['PUT', 'GET'].includes(value.method)), false);
    receipt.cases.push({ label: 'DIFFERENT_BYTES_SAME_KEY_REJECTED', status: 'PASS', sharedClientExitCodeProperty: 1 });

    const conditional = await bucket.put(full.r2Key, bytesByName.get(full.fileName), {
      onlyIf: { etagDoesNotMatch: '*' }, sha256: full.sha256,
      httpMetadata: new Headers({ 'Content-Length': String(full.sizeBytes), 'Content-Type': 'application/vnd.e-track.etu' }),
      customMetadata: heads[0].customMetadata });
    assert.equal(conditional, null);
    assert.equal(receipt.observations.at(-1).status, 412);
    const stale = await bucket.get(full.r2Key, { onlyIf: { etagMatches: '0'.repeat(32) } });
    assert.equal('body' in stale, false);
    assert.equal(receipt.observations.at(-1).status, 412);
    receipt.cases.push({ label: 'S3_CONDITIONAL_PUT_AND_GET_REJECTED', status: 'PASS', httpStatuses: [412, 412], transportOnly: true });
    for (let index = 0; index < metadata.assets.length; index++) {
      assert.deepEqual(await bucket.head(metadata.assets[index].r2Key), heads[index]);
    }
    receipt.r2HeadsUnchangedAfterReplaysAndNegatives = heads;
    assert.deepEqual(await counts('D1_BEFORE_READY_REGISTER'), before);
    fs.writeFileSync(verifiedMetadataPath, canonicalJson(metadata) + '\n', { flag: 'wx' });
    receipt.verifiedMetadata = { path: verifiedMetadataPath, sizeBytes: fs.statSync(verifiedMetadataPath).size,
      sha256: hash(fs.readFileSync(verifiedMetadataPath)) };

    const registered = await register(metadata);
    assert.equal(registered.idempotent, false);
    const ready = await snapshot('D1_READY_AFTER_201');
    assert.deepEqual(ready.map(rows => rows.length), [1, 3, 2, 1]);
    assert.equal(ready[0][0].state, 'ready');
    assert.equal(ready[0][0].registration_json, canonicalJson(metadata));
    assert.equal(ready[0][0].id, registered.releaseId);
    for (const asset of metadata.assets) {
      const row = ready[1].find(value => value.file_name === asset.fileName);
      assert.equal(row.r2_state, 'available'); assert.equal(row.r2_key, asset.r2Key);
      assert.equal(row.sha256, asset.sha256); assert.equal(row.size_bytes, asset.sizeBytes);
      assert.equal(row.r2_etag, heads[metadata.assets.indexOf(asset)].httpEtag);
    }
    assert.ok(ready[2].every(row => row.current_release_id === null && row.legacy_current_release_id === null
      && row.revision === 0 && row.last_action === 'init'));
    assert.equal(ready[3][0].action, 'register_firmware_release');
    receipt.cases.push({ label: 'REAL_REGISTER_201_READY', status: 'PASS', releaseId: registered.releaseId });

    const replay = await register(metadata);
    assert.equal(replay.idempotent, true); assert.equal(replay.releaseId, registered.releaseId);
    assert.deepEqual(await snapshot('D1_AFTER_200_REPLAY'), ready);
    receipt.cases.push({ label: 'REAL_REGISTER_200_REPLAY_UNCHANGED_D1', status: 'PASS' });
    const conflicting = { ...metadata, releaseNotes: metadata.releaseNotes + ' Deliberate conflict negative.' };
    await rejectRegister('REAL_REGISTER_409_CONFLICT', conflicting, 409, 'RELEASE_CONFLICT');
    assert.deepEqual(await snapshot('D1_AFTER_409_CONFLICT'), ready);
    receipt.finalCounts = await counts('D1_QUALIFICATION_FINAL_COUNTS');
    assert.deepEqual(receipt.finalCounts, [{ releases: 1, assets: 3, channels: 2, register_audits: 1, ready: 1 }]);
    receipt.noPublishedChannel = true;
    receipt.registered = registered;
  } else {
  const asset = metadata.assets[0];
  const result = await uploadFirmwareAsset(metadata, asset.fileName, bytesByName.get(asset.fileName), bucket);
  receipt.uploadResult = result;
  assert.equal(result.status, 'UPLOADED');
  assert.deepEqual(receipt.observations.filter(value => value.method).map(value => [value.method, value.status]),
    [['HEAD', 404], ['PUT', 200], ['HEAD', 200], ['GET', 200]]);
  assert.deepEqual(await counts('D1_AFTER_FIRST_UPLOAD'), before);
  }
  assert.equal(hash(fs.readFileSync(metadataPath)), receipt.inputMetadataSha256);
  receipt.ok = true;
} catch (error) {
  receipt.error = { name: error.name, code: error.code, message: redact(error.message) };
  process.exitCode = 1;
} finally {
  receipt.finished = new Date().toISOString();
  fs.writeFileSync(receiptPath, redact(JSON.stringify(receipt, null, 2)) + '\n', { flag: 'wx' });
  console.log(JSON.stringify({ phase, ok: receipt.ok, upload: receipt.uploadResult?.status,
    passedCases: receipt.cases.length, ready: receipt.registered?.state, error: receipt.error, receiptPath }));
}
