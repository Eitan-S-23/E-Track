const fs = require('node:fs');
const path = require('node:path');
const cp = require('node:child_process');
const crypto = require('node:crypto');
const assert = require('node:assert/strict');
const root = fs.realpathSync.native(path.resolve(__dirname, '../..'));
assert.equal(fs.realpathSync.native(process.cwd()), root);
const out = name => path.join(__dirname, name);
const result = { startedAt: new Date().toISOString(), mode: 'READ_ONLY_SETUP_CAPABILITY', requests: [], references: [] };
const planned = ['read-only.json', 'cloudflare-create-account.md', 'cloudflare-account-setup.md', 'github-environments.md'];
for (const name of planned) assert(!fs.existsSync(out(name)));
async function get(url, token) {
  const response = await fetch(url, { headers: { Authorization: 'Bearer ' + token,
    Accept: 'application/json', 'X-GitHub-Api-Version': '2022-11-28' },
    redirect: 'error', signal: AbortSignal.timeout(30000) });
  result.requests.push({ method: 'GET', host: new URL(url).host, path: new URL(url).pathname, status: response.status });
  return { status: response.status, data: await response.json() };
}
async function reference(url, file) {
  const response = await fetch(url, { headers: { Accept: 'text/markdown' }, signal: AbortSignal.timeout(45000) });
  const bytes = Buffer.from(await response.arrayBuffer());
  assert(bytes.length < 8000000);
  fs.writeFileSync(out(file), bytes, { flag: 'wx' });
  result.references.push({ url, resolvedUrl: response.url, file, status: response.status,
    contentType: response.headers.get('content-type'), bytes: bytes.length,
    sha256: crypto.createHash('sha256').update(bytes).digest('hex') });
}
async function main() {
  await reference('https://developers.cloudflare.com/api/resources/accounts/methods/create/', 'cloudflare-create-account.md');
  await reference('https://developers.cloudflare.com/fundamentals/setup/account/create-account/', 'cloudflare-account-setup.md');
  await reference('https://docs.github.com/en/rest/deployments/environments?apiVersion=2022-11-28', 'github-environments.md');
  const token = fs.readFileSync(path.join(root, '.cache/cf-auth-input/token.txt'), 'utf8').trim();
  const accounts = await get('https://api.cloudflare.com/client/v4/accounts?per_page=50', token);
  result.cloudflareAccounts = { status: accounts.status, success: accounts.data.success,
    totalVisible: accounts.data.result_info?.total_count,
    accounts: accounts.data.result?.map(account => ({ id: account.id, name: account.name, type: account.type })),
    errors: accounts.data.errors?.map(error => ({ code: error.code, message: error.message })) };
  const gh = cp.spawnSync('C:/Program Files/GitHub CLI/gh.exe',
    ['auth', 'token', '--hostname', 'github.com', '--user', 'Eitan-S-23'],
    { cwd: root, windowsHide: true, encoding: 'utf8', timeout: 15000,
      env: { ...process.env, GH_NO_UPDATE_NOTIFIER: '1', GH_PROMPT_DISABLED: '1',
        TEMP: path.join(root, '.cache/runtime/tmp'), TMP: path.join(root, '.cache/runtime/tmp') } });
  assert.equal(gh.status, 0);
  const githubToken = gh.stdout.trim();
  const identity = await get('https://api.github.com/user', githubToken);
  assert.equal(identity.data.login, 'Eitan-S-23');
  result.githubIdentity = { login: identity.data.login, id: identity.data.id, type: identity.data.type };
  const base = 'https://api.github.com/repos/Eitan-S-23/E-Track';
  const repo = await get(base, githubToken);
  assert.equal(repo.status, 200);
  result.repository = { id: repo.data.id, visibility: repo.data.visibility, owner: repo.data.owner.login,
    permissions: repo.data.permissions, defaultBranch: repo.data.default_branch };
  const envs = await get(base + '/environments?per_page=100', githubToken);
  result.environments = { status: envs.status, total: envs.data.total_count,
    entries: envs.data.environments?.map(environment => ({ id: environment.id, name: environment.name,
      protectionRules: environment.protection_rules, deploymentBranchPolicy: environment.deployment_branch_policy })) };
  result.ok = true;
}
main().catch(error => { result.ok = false; result.error = { name: error.name, code: error.cause?.code, message: error.message }; process.exitCode = 1; })
  .finally(() => { result.endedAt = new Date().toISOString(); result.closed = true;
    fs.writeFileSync(out('read-only.json'), JSON.stringify(result, null, 2) + '\n', { flag: 'wx' });
    const safe = { ...result, cloudflareAccounts: result.cloudflareAccounts ? {
      ...result.cloudflareAccounts, accounts: result.cloudflareAccounts.accounts?.map(account => ({ ...account,
        name: account.name.replace(/[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}/ig, '[REDACTED_EMAIL]') })) } : undefined };
    console.log(JSON.stringify(safe)); });
