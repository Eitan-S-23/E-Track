// Complete the already-authorized test environment; never dispatch or approve.
const fs = require('node:fs');
const path = require('node:path');
const cp = require('node:child_process');
const assert = require('node:assert/strict');
const root = fs.realpathSync.native(path.resolve(__dirname, '../..'));
assert.equal(fs.realpathSync.native(process.cwd()), root);
assert.equal(root.toLowerCase(), 'd:\\github\\my\\e-track\\.cache\\p41-dev-20261015');
const gh = 'C:/Program Files/GitHub CLI/gh.exe';
const repo = 'Eitan-S-23/E-Track';
const environment = 'firmware-rehearsal';
const branch = 'dev/p4-1/unattended-20261015';
const base = `/repos/${repo}/environments/${environment}`;
const secretName = 'FIRMWARE_REHEARSAL_TRACE_DEPLOY_TOKEN';
function guard(value) {
  const target = path.resolve(root, value);
  let parent = target;
  while (!fs.existsSync(parent)) parent = path.dirname(parent);
  const actual = path.resolve(fs.realpathSync.native(parent), path.relative(parent, target));
  const relative = path.relative(root, actual);
  assert(!path.isAbsolute(relative) && relative !== '..' && !relative.startsWith('..' + path.sep));
  for (let current = parent; current !== path.dirname(current); current = path.dirname(current)) {
    assert(!fs.lstatSync(current).isSymbolicLink());
    assert.equal(fs.realpathSync.native(current).toLowerCase(), current.toLowerCase());
  }
  return actual;
}
const retry = process.argv[2] === '--retry-public-key-eof';
assert(process.argv.length === (retry ? 3 : 2));
if (retry) {
  const prior = JSON.parse(fs.readFileSync(guard('.cache/p41-approved-20261016/github-register.json')));
  assert(prior.closed && !prior.ok && prior.secretUploads.length === 1);
  assert.equal(prior.secretUploads[0].exitCode, 1);
  assert.match(prior.secretUploads[0].stderr, /^failed to fetch public key:.*: EOF\n$/);
}
const output = guard('.cache/p41-approved-20261016/' + (retry ? 'github-register-retry.json' : 'github-register.json'));
assert(!fs.existsSync(output), 'Do not replay completed configuration');
const local = JSON.parse(fs.readFileSync(guard('.cache/cf-auth-input/firmware-test-secrets.json')));
const deployToken = local.TRACE_DEPLOY_TOKEN;
assert(typeof deployToken === 'string' && deployToken.length >= 32 && !/\s/.test(deployToken));
const result = { startedAt: new Date().toISOString(), environment, branch, requests: [],
  secretUploads: [], approvalsPerformed: 0, dispatches: 0, cloudflareWrites: 0,
  productionModified: false, descriptorApprovalConfigured: false,
  retryOf: retry ? 'github-register.json: public-key GET EOF, before upload' : undefined };
let token;
const redact = value => [token, deployToken, local.DOWNLOAD_HMAC_KEY_CURRENT].filter(Boolean)
  .reduce((text, secret) => text.replaceAll(secret, '[REDACTED]'), String(value));
async function get(route) {
  assert(route === '/user' || route.startsWith(`/repos/${repo}/`));
  const response = await fetch('https://api.github.com' + route, { redirect: 'error',
    headers: { Authorization: 'Bearer ' + token, Accept: 'application/vnd.github+json',
      'X-GitHub-Api-Version': '2022-11-28' }, signal: AbortSignal.timeout(30000) });
  result.requests.push({ method: 'GET', route, status: response.status });
  assert(response.ok, 'GitHub read failed: ' + response.status);
  return response.json();
}
function verifyEnvironment(value) {
  assert.equal(value.name, environment);
  assert.deepEqual(value.deployment_branch_policy, { protected_branches: false, custom_branch_policies: true });
  const rule = value.protection_rules.find(item => item.type === 'required_reviewers');
  assert(rule && rule.prevent_self_review === false && rule.reviewers.length === 1);
  assert.equal(rule.reviewers[0].reviewer.login, 'Eitan-S-23');
  assert.equal(rule.reviewers[0].reviewer.id, 204050265);
}
async function main() {
  const approved = JSON.parse(fs.readFileSync(guard('.cache/github/p41-approved-run-1.json')));
  assert.equal(approved.id, 38859822756);
  assert.equal(approved.conclusion, 'success');
  const tokenRead = cp.spawnSync(gh, ['auth', 'token', '--hostname', 'github.com', '--user', 'Eitan-S-23'],
    { cwd: root, windowsHide: true, encoding: 'utf8', timeout: 15000,
      env: { ...process.env, GH_NO_UPDATE_NOTIFIER: '1', GH_PROMPT_DISABLED: '1',
        TEMP: guard('.cache/runtime/tmp'), TMP: guard('.cache/runtime/tmp') } });
  assert.equal(tokenRead.status, 0); token = tokenRead.stdout.trim();
  assert.equal((await get('/user')).login, 'Eitan-S-23');
  verifyEnvironment(await get(base));
  const policies = await get(base + '/deployment-branch-policies?per_page=100');
  assert.equal(policies.total_count, 1);
  assert.equal(policies.branch_policies[0].name, branch);
  assert.equal(policies.branch_policies[0].type, 'branch');
  const variables = (await get(base + '/variables?per_page=100')).variables;
  assert.equal(variables.find(item => item.name === 'OTA_BOOT_CHAIN_READY')?.value, 'false');
  assert(!variables.some(item => ['OTA_PREVIOUS_RELEASE_JSON', 'OTA_APPROVED_BOOTSTRAP_BASELINE_SHA256'].includes(item.name)));
  const before = (await get(base + '/secrets?per_page=100')).secrets;
  assert.deepEqual(before.map(item => item.name).sort(), [
    'FIRMWARE_REHEARSAL_CLOUDFLARE_ACCOUNT_ID', 'FIRMWARE_REHEARSAL_CLOUDFLARE_API_TOKEN',
    'FIRMWARE_REHEARSAL_OTA_AES_KEY', 'FIRMWARE_REHEARSAL_TRACE_UPDATE_SERVICE_URL'
  ]);
  const env = { ...process.env };
  for (const name of Object.keys(env)) {
    if (/^(GH_|GITHUB_TOKEN|CLOUDFLARE_|CF_|TRACE_|OTA_|GIT_TRACE|NODE_OPTIONS|NODE_COMPILE_CACHE|OPENAI_|ANTHROPIC_|CC_CONNECT)/.test(name)) delete env[name];
  }
  Object.assign(env, { GH_TOKEN: token, GH_HOST: 'github.com', GH_NO_UPDATE_NOTIFIER: '1', GH_PROMPT_DISABLED: '1' });
  for (const [name, directory] of Object.entries({ TEMP: 'tmp', TMP: 'tmp', TMPDIR: 'tmp', HOME: 'home',
    USERPROFILE: 'home', APPDATA: 'appdata', LOCALAPPDATA: 'localappdata', GH_CONFIG_DIR: 'config/gh' })) {
    env[name] = guard('.cache/runtime/' + directory);
    fs.mkdirSync(env[name], { recursive: true });
  }
  const saved = cp.spawnSync(gh, ['secret', 'set', secretName, '--app', 'actions', '--repo', repo, '--env', environment],
    { cwd: root, env, input: deployToken, windowsHide: true, encoding: 'utf8', timeout: 120000 });
  result.secretUploads.push({ name: secretName, pid: saved.pid, exitCode: saved.status, closed: true,
    stdout: redact(saved.stdout ?? ''), stderr: redact(saved.stderr ?? '') });
  assert.equal(saved.status, 0, 'Secret upload failed; preserve the receipt before recovery');
  const after = (await get(base + '/secrets?per_page=100')).secrets;
  assert.deepEqual(after.map(item => item.name).sort(), [...before.map(item => item.name), secretName].sort());
  verifyEnvironment(await get(base));
  assert.deepEqual((await get(base + '/variables?per_page=100')).variables, variables);
  result.secretNames = after.map(item => item.name);
  result.variables = variables;
  result.source = 'Existing test-only credential; not the old Trace service credential';
  result.runtimeSecretReadback = 'NOT_AVAILABLE: GitHub returns secret metadata only';
  result.ok = true;
}
main().catch(error => {
  result.ok = false; result.error = { name: error.name, message: redact(error.message), causeCode: error.cause?.code };
  process.exitCode = 1;
}).finally(() => {
  result.endedAt = new Date().toISOString(); result.closed = true;
  const safe = redact(JSON.stringify(result, null, 2)) + '\n';
  fs.writeFileSync(output, safe, { flag: 'wx' });
  console.log(safe);
});
