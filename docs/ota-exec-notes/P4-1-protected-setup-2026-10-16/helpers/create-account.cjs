const fs = require('node:fs');
const path = require('node:path');
const assert = require('node:assert/strict');
const crypto = require('node:crypto');
const root = fs.realpathSync.native(path.resolve(__dirname, '../..'));
assert.equal(fs.realpathSync.native(process.cwd()), root);
const receiptPath = path.join(__dirname, 'create-account.json');
const targetPath = path.join(root, '.cache/cf-auth-input/p41-test-account.json');
assert(!fs.existsSync(receiptPath));
assert(!fs.existsSync(targetPath));
const plan = JSON.parse(fs.readFileSync(path.join(__dirname, 'create-account-plan.json'), 'utf8'));
assert.equal(plan.name, 'e-track-firmware-p41-validation');
assert.equal(plan.type, 'standard');
assert.equal(plan.standalone, true);
assert.equal(plan.idempotencyKey, 'e-track-p41-standalone-20261016-fefcb3f-v1');
const token = fs.readFileSync(path.join(root, '.cache/cf-auth-input/token.txt'), 'utf8').trim();
const receipt = { startedAt: new Date().toISOString(), scope: 'ONE_STANDALONE_FREE_TEST_ACCOUNT', requests: [], created: false };
const sha = value => crypto.createHash('sha256').update(value).digest('hex');
const sanitize = value => String(value).replaceAll(token, '[REDACTED_TOKEN]')
  .replace(/[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}/ig, '[REDACTED_EMAIL]');
async function request(method, route, body) {
  const response = await fetch('https://api.cloudflare.com/client/v4/' + route, {
    method, redirect: 'error', signal: AbortSignal.timeout(45000),
    headers: { Authorization: 'Bearer ' + token, Accept: 'application/json',
      'Content-Type': 'application/json', ...(method === 'POST' ? { 'Idempotency-Key': plan.idempotencyKey } : {}) },
    body: body ? JSON.stringify(body) : undefined });
  const data = await response.json();
  receipt.requests.push({ method, route, status: response.status, success: data.success,
    errors: data.errors?.map(error => ({ code: error.code, message: sanitize(error.message) })) });
  return { status: response.status, data };
}
async function main() {
  const user = await request('GET', 'user');
  if (user.status !== 200 || !user.data.success) {
    receipt.blocker = 'USER_DETAILS_READ_UNAVAILABLE_NO_ACCOUNT_CREATE_ATTEMPT';
    return;
  }
  receipt.userDetailsRead = true;
  receipt.userIdentitySha256 = sha(String(user.data.result.id));
  receipt.userSuspended = user.data.result.suspended;
  assert.notEqual(user.data.result.suspended, true);
  const accounts = await request('GET', 'accounts?per_page=50');
  assert.equal(accounts.status, 200);
  assert.equal(accounts.data.success, true);
  assert(!accounts.data.result.some(account => account.name === plan.name), 'Named account already exists; inspect rather than create another');
  const created = await request('POST', 'accounts', { name: plan.name, type: plan.type, standalone: true });
  if (created.status < 200 || created.status >= 300 || !created.data.success) {
    receipt.blocker = 'ACCOUNT_CREATION_REJECTED_NO_PERMISSION_EXPANSION_OR_RETRY';
    return;
  }
  const account = created.data.result;
  assert.match(account.id, /^[0-9a-f]{32}$/);
  assert.equal(account.name, plan.name);
  assert.equal(account.type, 'standard');
  assert.notEqual(account.id, 'af6dd848e6a21f1cd26d44b1b656af7b');
  fs.writeFileSync(targetPath, JSON.stringify({ accountId: account.id, name: account.name, type: account.type,
    createdOn: account.created_on, idempotencyKey: plan.idempotencyKey,
    purpose: 'P4-1 test resources only; no production resources or paid-plan activation' }, null, 2) + '\n', { flag: 'wx', mode: 0o600 });
  receipt.created = true;
  receipt.accountName = account.name;
  receipt.accountIdSha256 = sha(account.id);
  receipt.privateTargetFile = '.cache/cf-auth-input/p41-test-account.json';
  receipt.ok = true;
}
main().catch(error => { receipt.ok = false; receipt.error = { name: error.name, code: error.cause?.code,
    message: sanitize(error.message) }; process.exitCode = 1; })
  .finally(() => { receipt.endedAt = new Date().toISOString(); receipt.closed = true;
    fs.writeFileSync(receiptPath, JSON.stringify(receipt, null, 2) + '\n', { flag: 'wx' });
    console.log(JSON.stringify(receipt)); });
