// Bounded read-only qualification of the supplied CI credential and fixed targets.
const fs = require('node:fs');
const path = require('node:path');
const cp = require('node:child_process');
const assert = require('node:assert/strict');
const root = fs.realpathSync.native(path.resolve(__dirname, '../..'));
assert.equal(fs.realpathSync.native(process.cwd()), root);
const output = path.join(__dirname, 'probe.json');
assert(!fs.existsSync(output));
const token = fs.readFileSync(path.join(root, '.cache/cf-auth-input/p41-ci-token.txt'), 'utf8').trim();
const provisioning = fs.readFileSync(path.join(root, '.cache/cf-auth-input/token.txt'), 'utf8').trim();
assert(/^[A-Za-z0-9_.-]{20,4096}$/.test(token), 'Input must be one bare API token');
assert(token !== provisioning, 'Do not export the local provisioning credential');
const original = JSON.parse(fs.readFileSync(path.join(root, '.cache/p41-setup-20261016/read-only.json')));
assert.equal(original.cloudflareAccounts.accounts.length, 1);
const account = original.cloudflareAccounts.accounts[0].id;
assert(/^[0-9a-f]{32}$/.test(account));
const expected = { worker: 'e-track-firmware-p41-test', bucket: 'e-track-firmware-p41-test-releases',
  database: 'e-track-firmware-p41-test', databaseId: '2617e1e1-956f-42ce-a465-da56d84abf06',
  serviceUrl: 'https://e-track-firmware-p41-test.tangjichentudou.workers.dev' };
const result = { startedAt: new Date().toISOString(), scope: 'CURRENT_ACCOUNT_CI_CREDENTIAL_READS',
  requests: [], tokenDistinctFromProvisioning: true, tokenFormat: token.startsWith('cfat_') ? 'cfat' : 'unprefixed',
  tokenPolicyVerified: false, hardProductionPermissionIsolation: false,
  resourceWritesRequested: 0, previewSessionsCreated: 0, nativeQualification: 'NOT_RUN' };
const redact = value => [token, provisioning, account].reduce((text, secret) =>
  text.replaceAll(secret, '[REDACTED]'), String(value));
async function get(route) {
  const response = await fetch('https://api.cloudflare.com/client/v4' + route, { method: 'GET',
    headers: { Authorization: 'Bearer ' + token, Accept: 'application/json' },
    redirect: 'error', signal: AbortSignal.timeout(30000) });
  const body = await response.json();
  result.requests.push({ method: 'GET', route: redact(route), status: response.status,
    success: body.success, errors: body.errors?.map(error => ({ code: error.code, message: redact(error.message) })) });
  return { status: response.status, body };
}
async function main() {
  const verified = await get(token.startsWith('cfat_') ? `/accounts/${account}/tokens/verify` : '/user/tokens/verify');
  result.tokenVerification = { status: verified.status, active: verified.body.result?.status === 'active' };
  assert.equal(verified.status, 200, 'CI token verification failed');
  assert.equal(result.tokenVerification.active, true, 'CI token is not active');
  const selectedAccount = await get(`/accounts/${account}`);
  result.account = { status: selectedAccount.status, matchesSelectedAccount: selectedAccount.body.result?.id === account };
  const worker = await get(`/accounts/${account}/workers/scripts/${expected.worker}/settings`);
  const bindings = worker.body.result?.bindings ?? [];
  const pick = name => bindings.filter(binding => binding.name === name);
  result.worker = { status: worker.status, worker: expected.worker,
    bucketMatches: pick('RELEASES_BUCKET').length === 1 && pick('RELEASES_BUCKET')[0].bucket_name === expected.bucket,
    databaseMatches: pick('DB').length === 1 && pick('DB')[0].id === expected.databaseId,
    environmentMatches: pick('ENVIRONMENT').length === 1 && pick('ENVIRONMENT')[0].text === 'staging' };
  const bucket = await get(`/accounts/${account}/r2/buckets/${expected.bucket}`);
  result.bucket = { status: bucket.status, nameMatches: bucket.body.result?.name === expected.bucket };
  const database = await get(`/accounts/${account}/d1/database/${expected.databaseId}`);
  result.database = { status: database.status, nameMatches: database.body.result?.name === expected.database,
    idMatches: database.body.result?.uuid === expected.databaseId };
  const health = cp.spawnSync('curl.exe', ['-q', '--silent', '--show-error', '--fail', '--proto', '=https',
    '--connect-timeout', '15', '--max-time', '30', expected.serviceUrl + '/healthz'],
    { cwd: root, windowsHide: true, encoding: 'utf8', timeout: 35000, maxBuffer: 1024 * 1024 });
  result.health = { exitCode: health.status, closed: true, error: redact(health.stderr ?? '') };
  if (health.status === 0) {
    const body = JSON.parse(health.stdout);
    result.health.observation = body;
  }
  assert.equal(selectedAccount.status, 200, 'Account read failed');
  assert.equal(result.account.matchesSelectedAccount, true, 'Wrong account');
  for (const value of [result.worker.bucketMatches, result.worker.databaseMatches, result.worker.environmentMatches]) {
    assert.equal(value, true, 'Unexpected existing Worker binding');
  }
  assert.equal(worker.status, 200, 'Worker settings read failed');
  assert.equal(bucket.status, 200, 'R2 bucket read failed');
  assert.equal(result.bucket.nameMatches, true, 'Wrong bucket');
  assert.equal(database.status, 200, 'D1 metadata read failed');
  assert.equal(result.database.nameMatches, true, 'Wrong D1 name');
  assert.equal(result.database.idMatches, true, 'Wrong D1 identity');
  assert.equal(health.status, 0, 'Worker health transport failed');
  result.ok = true;
}
main().catch(error => { result.ok = false; result.error = { name: error.name, message: redact(error.message),
  causeCode: error.cause?.code }; process.exitCode = 1; }).finally(() => {
  result.endedAt = new Date().toISOString(); result.closed = true;
  const safe = redact(JSON.stringify(result, null, 2)) + '\n';
  fs.writeFileSync(output, safe, { flag: 'wx' });
  console.log(safe);
});
