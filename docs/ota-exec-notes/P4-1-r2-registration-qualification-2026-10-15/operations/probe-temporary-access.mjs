import fs from 'node:fs';
import path from 'node:path';
import assert from 'node:assert/strict';
import { spawnSync } from 'node:child_process';
import { fileURLToPath, pathToFileURL } from 'node:url';

const directory = path.dirname(fileURLToPath(import.meta.url));
const root = path.resolve(directory, '../..');
const { outputPath } = await import(pathToFileURL(path.join(root,
  'app/bluetooth_flutter_Trace/cloudflare/update-service/scripts/firmware-cli.mjs')));
const guard = value => outputPath(root, value);
const privateRoot = guard(path.join(root, '.cache/cf-auth-input/r2-qualification'));
const receiptPath = guard(path.join(directory, 'readonly-probe.json'));
assert.equal(fs.existsSync(receiptPath), false);
const token = fs.readFileSync(path.join(root, '.cache/cf-auth-input/token.txt'), 'utf8').trim();
const config = JSON.parse(fs.readFileSync(path.join(root, '.cache/cf-firmware-setup-20261015/d1-edit-r2/resources-created.json'), 'utf8'));
assert.equal(config.accountId, 'af6dd848e6a21f1cd26d44b1b656af7b');
assert.equal(config.r2.name, 'e-track-firmware-p41-test-releases');
const metadata = JSON.parse(fs.readFileSync(path.join(root,
  '.cache/cf-firmware-setup-20261015/d1-edit-r2/qualification-metadata.json'), 'utf8'));
const objects = metadata.assets.map(asset => asset.r2Key);
assert.equal(objects.length, 3);
assert.ok(objects.every(key => key.startsWith('trace/firmware/e-track-at32f435/20801-')));
const credentialPath = guard(path.join(privateRoot, 'readonly-credentials.json'));
assert.equal(fs.existsSync(credentialPath), false);
const outputs = { TEMP: 'tmp', TMP: 'tmp', TMPDIR: 'tmp', HOME: 'home', USERPROFILE: 'home',
  APPDATA: 'appdata', LOCALAPPDATA: 'localappdata', XDG_CONFIG_HOME: 'config', XDG_CACHE_HOME: 'cache' };
const env = { ...process.env };
for (const key of Object.keys(env)) if (/^(CF_|CLOUDFLARE_|GH_|GITHUB_TOKEN|TRACE_|NODE_OPTIONS|NODE_COMPILE_CACHE)/.test(key)) delete env[key];
for (const [key, relative] of Object.entries(outputs)) {
  env[key] = guard(path.join(privateRoot, relative));
  fs.mkdirSync(env[key], { recursive: true });
}
const sensitive = [token];
const redact = value => sensitive.reduce((text, secret) => text.split(secret).join('[REDACTED]'), String(value ?? ''));
const receipt = { started: new Date().toISOString(), purpose: 'Scoped read-only R2 access qualification, not rehearsal',
  bucket: config.r2.name, objects, ttlSeconds: 900, permission: 'object-read-only', observations: [], ok: false };
try {
  const verified = await fetch('https://api.cloudflare.com/client/v4/user/tokens/verify', {
    headers: { Authorization: `Bearer ${token}` }, redirect: 'error', signal: AbortSignal.timeout(30000) });
  const verification = await verified.json();
  receipt.observations.push({ operation: 'verify-parent', status: verified.status, active: verification.result?.status === 'active' });
  assert.equal(verified.status, 200);
  assert.equal(verification.result.status, 'active');
  assert.match(verification.result.id, /^[0-9a-f]{32}$/);
  const response = await fetch(`https://api.cloudflare.com/client/v4/accounts/${config.accountId}/r2/temp-access-credentials`, {
    method: 'POST', redirect: 'error', headers: { Authorization: `Bearer ${token}`, 'Content-Type': 'application/json' },
    body: JSON.stringify({ bucket: config.r2.name, parentAccessKeyId: verification.result.id,
      permission: 'object-read-only', ttlSeconds: 900, objects }), signal: AbortSignal.timeout(30000) });
  const body = await response.json();
  receipt.observations.push({ operation: 'mint-scoped-readonly', status: response.status,
    cfRay: response.headers.get('cf-ray'), success: body.success, errors: body.errors });
  assert.equal(response.status, 200);
  assert.equal(body.success, true);
  const credentials = body.result;
  for (const key of ['accessKeyId', 'secretAccessKey', 'sessionToken']) {
    assert.match(credentials[key], /^[A-Za-z0-9._~+/=-]+$/);
    sensitive.push(credentials[key]);
  }
  fs.writeFileSync(credentialPath, JSON.stringify(credentials), { flag: 'wx' });
  const curlInput = ['aws-sigv4 = "aws:amz:auto:s3"',
    'user = ' + JSON.stringify(credentials.accessKeyId + ':' + credentials.secretAccessKey),
    'header = ' + JSON.stringify('X-Amz-Security-Token: ' + credentials.sessionToken)].join('\n') + '\n';
  for (const [label, key, expected] of [['allowed-missing-object', objects[0], 404],
    ['denied-outside-object-scope', 'trace/firmware/e-track-at32f435/outside-qualification-scope.bin', 403]]) {
    const headers = guard(path.join(privateRoot, label + '.headers'));
    const output = guard(path.join(privateRoot, label + '.body'));
    assert.equal(fs.existsSync(headers), false); assert.equal(fs.existsSync(output), false);
    const url = `https://${config.accountId}.r2.cloudflarestorage.com/${config.r2.name}/${key.split('/').map(encodeURIComponent).join('/')}`;
    const result = spawnSync('curl', ['--config', '-', '--head', '--silent', '--show-error', '--proto', '=https',
      '--connect-timeout', '15', '--max-time', '30', '--dump-header', headers, '--output', output,
      '--write-out', '%{http_code}', url], { cwd: root, env, input: curlInput, encoding: 'utf8',
      windowsHide: true, timeout: 35000, maxBuffer: 1024 * 1024 });
    const status = Number(result.stdout.trim());
    receipt.observations.push({ operation: label, key, curlExitCode: result.status, status,
      stderr: redact(result.stderr), responseHeaders: redact(fs.readFileSync(headers, 'utf8')) });
    assert.equal(result.status, 0);
    assert.equal(status, expected);
  }
  receipt.ok = true;
} catch (error) {
  receipt.error = { name: error.name, message: redact(error.message) };
  process.exitCode = 1;
} finally {
  receipt.finished = new Date().toISOString();
  fs.writeFileSync(receiptPath, redact(JSON.stringify(receipt, null, 2)) + '\n', { flag: 'wx' });
  console.log(JSON.stringify({ ok: receipt.ok, observations: receipt.observations.map(x =>
    ({ operation: x.operation, status: x.status, success: x.success })), error: receipt.error, receiptPath }));
}
