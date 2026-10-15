const fs = require('node:fs');
const path = require('node:path');
const cp = require('node:child_process');
const assert = require('node:assert/strict');
const root = fs.realpathSync.native(path.resolve(__dirname, '../..'));
assert.equal(fs.realpathSync.native(process.cwd()), root);
const receiptPath = path.join(__dirname, 'read-only.json');
assert(!fs.existsSync(receiptPath));
const receipt = { startedAt: new Date().toISOString(), mode: 'READ_ONLY', requests: [] };
const account = 'af6dd848e6a21f1cd26d44b1b656af7b';
async function get(url, token) {
  const response = await fetch(url, { headers: { Authorization: 'Bearer ' + token,
    Accept: 'application/json', 'X-GitHub-Api-Version': '2022-11-28' },
    redirect: 'error', signal: AbortSignal.timeout(30000) });
  receipt.requests.push({ method: 'GET', host: new URL(url).host, path: new URL(url).pathname,
    status: response.status });
  return { status: response.status, data: await response.json() };
}
async function main() {
  const token = fs.readFileSync(path.join(root, '.cache/cf-auth-input/token.txt'), 'utf8').trim();
  const verified = await get('https://api.cloudflare.com/client/v4/user/tokens/verify', token);
  receipt.cloudflareTokenActive = verified.status === 200 && verified.data.result?.status === 'active';
  if (receipt.cloudflareTokenActive) {
    const detail = await get('https://api.cloudflare.com/client/v4/user/tokens/' + verified.data.result.id, token);
    receipt.cloudflarePolicy = { status: detail.status, readable: detail.status === 200,
      policies: detail.data.result?.policies?.map(policy => ({ effect: policy.effect,
        permissions: policy.permission_groups?.map(group => ({ id: group.id, name: group.name })),
        resources: policy.resources })) };
    const settings = await get(`https://api.cloudflare.com/client/v4/accounts/${account}/workers/scripts/e-track-firmware-p41-test/settings`, token);
    receipt.testWorker = { status: settings.status, bindings: settings.data.result?.bindings?.map(binding => ({
      name: binding.name, type: binding.type,
      r2TargetMatches: binding.type === 'r2_bucket' ? binding.bucket_name === 'e-track-firmware-p41-test-releases' : undefined,
      d1TargetMatches: binding.type === 'd1' ? binding.id === '2617e1e1-956f-42ce-a465-da56d84abf06' : undefined })) };
  }
  const gh = cp.spawnSync('C:/Program Files/GitHub CLI/gh.exe',
    ['auth', 'token', '--hostname', 'github.com', '--user', 'Eitan-S-23'],
    { cwd: root, windowsHide: true, encoding: 'utf8', timeout: 15000,
      env: { ...process.env, GH_NO_UPDATE_NOTIFIER: '1', GH_PROMPT_DISABLED: '1' } });
  assert.equal(gh.status, 0);
  const githubToken = gh.stdout.trim();
  const identity = await get('https://api.github.com/user', githubToken);
  assert.equal(identity.data.login, 'Eitan-S-23');
  receipt.githubIdentity = identity.data.login;
  const base = 'https://api.github.com/repos/Eitan-S-23/E-Track';
  const secrets = await get(base + '/actions/secrets?per_page=100', githubToken);
  receipt.repositorySecrets = { status: secrets.status, total: secrets.data.total_count,
    names: secrets.data.secrets?.map(secret => secret.name) };
  const vars = await get(base + '/actions/variables?per_page=100', githubToken);
  receipt.repositoryVariables = { status: vars.status, total: vars.data.total_count,
    names: vars.data.variables?.map(variable => variable.name),
    productionGateUnlocked: vars.data.variables?.some(variable => variable.name === 'OTA_BOOT_CHAIN_READY' && variable.value === 'true') };
  const local = JSON.parse(fs.readFileSync(path.join(root, '.cache/cf-auth-input/firmware-test-secrets.json'), 'utf8'));
  receipt.privateInputFieldNames = Object.keys(local);
  receipt.ok = true;
}
main().catch(error => { receipt.ok = false; receipt.errorClass = error.name; process.exitCode = 1; })
  .finally(() => {
    receipt.endedAt = new Date().toISOString();
    fs.writeFileSync(receiptPath, JSON.stringify(receipt, null, 2) + '\n', { flag: 'wx' });
    console.log(JSON.stringify(receipt));
  });
