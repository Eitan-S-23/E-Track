// Failure triage only: exercise the pinned SDK codec, never a runtime or R2 binding.
const fs = require('node:fs');
const path = require('node:path');
const assert = require('node:assert/strict');
const cp = require('node:child_process');
const crypto = require('node:crypto');
const { createRequire } = require('node:module');
let spawnAttempts = 0;
for (const name of ['spawn', 'spawnSync', 'exec', 'execSync', 'execFile', 'execFileSync', 'fork']) {
  cp[name] = () => { spawnAttempts++; throw Error('Native processes are forbidden in this codec probe'); };
}
const root = process.cwd();
const worker = path.join(root, 'app/bluetooth_flutter_Trace/cloudflare/update-service/worker');
const requireWorker = createRequire(path.join(worker, 'package.json'));
const mfPath = requireWorker.resolve('miniflare');
const mf = requireWorker('miniflare');
const lock = JSON.parse(fs.readFileSync(path.join(worker, 'package-lock.json')));
const installed = requireWorker('miniflare/package.json');
assert.equal(installed.version, lock.packages['node_modules/miniflare'].version);
const impl = { Blob, File, Headers: mf.Headers, Request: mf.Request, Response: mf.Response,
  isReadableStream: value => value instanceof ReadableStream };
const reducers = { ...mf.structuredSerializableReducers, ...mf.createHTTPReducers(impl) };
const body = Buffer.from('fixture');
const headers = { 'Content-Type': 'application/vnd.e-track.etu', 'Content-Length': String(body.length),
  'Content-Digest': 'sha-256=:' + crypto.createHash('sha256').update(body).digest('base64') + ':',
  'Content-Disposition': 'attachment; filename="fixture.etu"', 'Cache-Control': 'public, max-age=31536000, immutable' };
const cases = [
  ['node-global-headers', new Headers(headers), false],
  ['miniflare-headers', new mf.Headers(headers), true],
  ['plain-r2-metadata', { contentType: headers['Content-Type'], contentDisposition: headers['Content-Disposition'],
    cacheControl: headers['Cache-Control'] }, true]
];
const results = [];
for (const [name, httpMetadata, expected] of cases) {
  const args = ['fixture-key', body, { onlyIf: { etagDoesNotMatch: '*' }, httpMetadata,
    customMetadata: { sha256: crypto.createHash('sha256').update(body).digest('hex'), kind: 'full' } }];
  let accepted = false, error;
  try {
    const encoded = mf.stringifyWithStreams(impl, args, reducers, true);
    assert(!(encoded instanceof Promise));
    accepted = typeof encoded.value === 'string';
  } catch (caught) { error = { name: caught.name, message: caught.message, path: caught.path }; }
  results.push({ name, accepted, expected, error });
  assert.equal(accepted, expected, name);
}
assert.equal(spawnAttempts, 0);
console.log(JSON.stringify({ ok: true, scope: 'OFFLINE_SDK_CODEC_TRIAGE_NOT_FORMAL_REHEARSAL', node: process.version,
  miniflare: installed.version, sdkSha256: crypto.createHash('sha256').update(fs.readFileSync(mfPath)).digest('hex'),
  globalHeadersMatchSDK: Headers === mf.Headers, results, spawnAttempts, remoteRequests: 0 }, null, 2));
