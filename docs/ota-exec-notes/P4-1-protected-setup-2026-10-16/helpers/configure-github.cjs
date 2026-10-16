const fs = require('node:fs');
const path = require('node:path');
const cp = require('node:child_process');
const crypto = require('node:crypto');
const assert = require('node:assert/strict');
const { pathToFileURL } = require('node:url');
const root = fs.realpathSync.native(path.resolve(__dirname, '../..'));
assert.equal(fs.realpathSync.native(process.cwd()), root);
const gh = 'C:/Program Files/GitHub CLI/gh.exe';
const owner = { login: 'Eitan-S-23', id: 204050265 };
const repository = 'Eitan-S-23/E-Track';
const environment = 'firmware-rehearsal';
const branch = 'dev/p4-1/unattended-20261015';
const scope = '/repos/' + repository + '/environments/' + environment;
const keyName = 'FIRMWARE_REHEARSAL_OTA_AES_KEY';
const keyPath = path.join(root, '.cache/cf-auth-input/p41-rehearsal-ota-key.json');
const receiptPath = path.join(__dirname, 'github-configuration.json');
assert(!fs.existsSync(receiptPath));
assert(!fs.existsSync(keyPath));
const result = { startedAt: new Date().toISOString(), scope, requests: [],
  approvalsPerformed: 0, dispatches: 0, productionModified: false, cloudCredentialExported: false };
let githubToken, otaKey;
const sanitize = text => [githubToken, otaKey].filter(Boolean).reduce((value, secret) => value.replaceAll(secret, '[REDACTED]'), String(text));
async function request(method, route, body) {
  if (method !== 'GET') assert(route === scope || route.startsWith(scope + '/'));
  const response = await fetch('https://api.github.com' + route, { method, redirect: 'error',
    headers: { Authorization: 'Bearer ' + githubToken, Accept: 'application/vnd.github+json',
      'X-GitHub-Api-Version': '2022-11-28', 'Content-Type': 'application/json' },
    body: body === undefined ? undefined : JSON.stringify(body), signal: AbortSignal.timeout(30000) });
  const text = await response.text();
  const data = text ? JSON.parse(text) : null;
  result.requests.push({ method, route, status: response.status,
    errorMessage: response.ok ? undefined : sanitize(data?.message ?? 'Request failed') });
  return { status: response.status, data };
}
function verifyEnvironment(value) {
  assert.equal(value.name, environment);
  assert.deepEqual(value.deployment_branch_policy, { protected_branches: false, custom_branch_policies: true });
  const required = value.protection_rules.find(rule => rule.type === 'required_reviewers');
  assert(required);
  assert.equal(required.prevent_self_review, false);
  assert.equal(required.reviewers.length, 1);
  assert.equal(required.reviewers[0].type, 'User');
  assert.equal(required.reviewers[0].reviewer.id, owner.id);
  assert.equal(required.reviewers[0].reviewer.login, owner.login);
}
async function main() {
  const tokenRead = cp.spawnSync(gh, ['auth', 'token', '--hostname', 'github.com', '--user', owner.login],
    { cwd: root, encoding: 'utf8', windowsHide: true, timeout: 15000,
      env: { ...process.env, GH_NO_UPDATE_NOTIFIER: '1', GH_PROMPT_DISABLED: '1',
        TEMP: path.join(root, '.cache/runtime/tmp'), TMP: path.join(root, '.cache/runtime/tmp') } });
  assert.equal(tokenRead.status, 0);
  githubToken = tokenRead.stdout.trim();
  const who = await request('GET', '/user');
  assert.equal(who.status, 200);
  assert.equal(who.data.login, owner.login);
  assert.equal(who.data.id, owner.id);
  const repo = await request('GET', '/repos/' + repository);
  assert.equal(repo.status, 200);
  assert.equal(repo.data.permissions.admin, true);
  assert.equal(repo.data.visibility, 'public');
  const before = await request('GET', scope);
  assert.equal(before.status, 404, 'Environment already exists; inspect rather than overwrite its protections');
  const created = await request('PUT', scope, { wait_timer: 0, prevent_self_review: false,
    reviewers: [{ type: 'User', id: owner.id }],
    deployment_branch_policy: { protected_branches: false, custom_branch_policies: true } });
  assert.equal(created.status, 200);
  verifyEnvironment(created.data);
  result.createdEnvironmentId = created.data.id;
  const policy = await request('POST', scope + '/deployment-branch-policies', { name: branch, type: 'branch' });
  assert.equal(policy.status, 200);
  const policies = await request('GET', scope + '/deployment-branch-policies?per_page=100');
  assert.equal(policies.status, 200);
  assert.equal(policies.data.total_count, 1);
  assert.equal(policies.data.branch_policies[0].name, branch);
  assert.equal(policies.data.branch_policies[0].type, 'branch');
  const variables = { OTA_BOOT_CHAIN_READY: 'false',
    FIRMWARE_REHEARSAL_TRACE_R2_BUCKET: 'e-track-firmware-p41-test-releases',
    FIRMWARE_REHEARSAL_TRACE_D1_DATABASE_NAME: 'e-track-firmware-p41-test' };
  for (const [name, value] of Object.entries(variables)) {
    const saved = await request('POST', scope + '/variables', { name, value });
    assert.equal(saved.status, 201);
  }
  const observedVariables = await request('GET', scope + '/variables?per_page=100');
  assert.equal(observedVariables.status, 200);
  assert.equal(observedVariables.data.total_count, Object.keys(variables).length);
  assert.deepEqual(Object.fromEntries(observedVariables.data.variables.map(item => [item.name, item.value])), variables);
  const beforeSecrets = await request('GET', scope + '/secrets?per_page=100');
  assert.equal(beforeSecrets.status, 200);
  assert.equal(beforeSecrets.data.total_count, 0);
  const { approvedFirmwareKey } = await import(pathToFileURL(path.join(root,
    'app/bluetooth_flutter_Trace/cloudflare/update-service/scripts/firmware-release-key.mjs')));
  otaKey = crypto.randomBytes(16).toString('hex');
  const binding = approvedFirmwareKey({ OTA_AES_KEY: otaKey });
  fs.writeFileSync(keyPath, JSON.stringify({ schemaVersion: 1, keyName, keyHex: otaKey,
    keySha256: binding.keySha256, createdAt: new Date().toISOString(),
    scope: 'P4-1 rehearsal. Retain for authorized later key provisioning; do not rotate or publish automatically.' }, null, 2) + '\n',
    { flag: 'wx', mode: 0o600 });
  const env = { ...process.env };
  for (const name of Object.keys(env)) if (/^(GH_|GITHUB_TOKEN|CLOUDFLARE_|CF_|TRACE_|OTA_|GIT_TRACE|NODE_OPTIONS|NODE_COMPILE_CACHE)/.test(name)) delete env[name];
  Object.assign(env, { GH_TOKEN: githubToken, GH_HOST: 'github.com', GH_NO_UPDATE_NOTIFIER: '1', GH_PROMPT_DISABLED: '1' });
  for (const [name, directory] of Object.entries({ TEMP: 'tmp', TMP: 'tmp', TMPDIR: 'tmp', HOME: 'home',
    USERPROFILE: 'home', APPDATA: 'appdata', LOCALAPPDATA: 'localappdata', GH_CONFIG_DIR: 'config/gh' })) {
    env[name] = path.join(root, '.cache/runtime', directory);
    fs.mkdirSync(env[name], { recursive: true });
  }
  const uploaded = cp.spawnSync(gh, ['secret', 'set', keyName, '--app', 'actions', '--repo', repository, '--env', environment],
    { cwd: root, env, input: otaKey, encoding: 'utf8', windowsHide: true, timeout: 120000 });
  result.secretUpload = { secretName: keyName, exitCode: uploaded.status, pid: uploaded.pid, closed: true,
    stdout: sanitize(uploaded.stdout ?? ''), stderr: sanitize(uploaded.stderr ?? '') };
  assert.equal(uploaded.status, 0, 'Environment secret upload failed; retain the same private key for recovery');
  const secrets = await request('GET', scope + '/secrets?per_page=100');
  assert.equal(secrets.status, 200);
  assert.equal(secrets.data.total_count, 1);
  assert.equal(secrets.data.secrets[0].name, keyName);
  const after = await request('GET', scope);
  assert.equal(after.status, 200);
  verifyEnvironment(after.data);
  result.environment = { name: environment, requiredReviewer: owner.login,
    preventSelfReview: false, allowedBranches: [{ name: branch, type: 'branch' }],
    gate: 'false', variables, secretNames: secrets.data.secrets.map(secret => secret.name) };
  result.reviewPolicy = 'The human repository owner must approve any future run. The local agent uses the same GitHub identity for dispatch, so prevent_self_review=true would block that sole owner; no approval API is called and this is not independent production approval.';
  result.key = { secretName: keyName, nonDevelopment: true, keySha256: binding.keySha256,
    privateOwnerCopy: '.cache/cf-auth-input/p41-rehearsal-ota-key.json', runtimeValueVerified: false };
  result.missing = ['Production-free Cloudflare test account and its dedicated token',
    'Actual target Worker/D1/R2 fixture preparation and binding variables',
    'Reviewed bindings-check commit and later manual environment approval'];
  result.ok = true;
}
main().catch(error => { result.ok = false; result.error = { name: error.name, code: error.cause?.code,
    message: sanitize(error.message) }; process.exitCode = 1; })
  .finally(() => { result.endedAt = new Date().toISOString(); result.closed = true;
    fs.writeFileSync(receiptPath, JSON.stringify(result, null, 2) + '\n', { flag: 'wx' });
    console.log(JSON.stringify(result)); });
