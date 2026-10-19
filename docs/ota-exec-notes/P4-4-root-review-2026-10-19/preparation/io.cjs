const fs = require('node:fs');
const path = require('node:path');
const crypto = require('node:crypto');
const assert = require('node:assert/strict');
const { spawnSync } = require('node:child_process');
const project = 'D:/github/my/E-Track';
const worktree = project + '/.cache/p4-4-integration-20261018';
const base = path.resolve(__dirname);
const { guard: originalGuard } = require(worktree + '/.cache/p44-run.cjs');
const { ProxyAgent, request } = require(project + '/.cache/p4-3-implementation-20261017/app/bluetooth_flutter_Trace/cloudflare/update-service/admin/node_modules/undici');
const sensitive = new Set();
const sha256 = data => crypto.createHash('sha256').update(data).digest('hex');
const readJson = file => JSON.parse(fs.readFileSync(file, 'utf8'));
function guard(file) { return originalGuard(path.resolve(file), project); }
function output(name) {
  const full = path.resolve(base, name);
  const relative = path.relative(base, full);
  assert.ok(relative !== '..' && !relative.startsWith('..' + path.sep) && !path.isAbsolute(relative));
  return guard(full);
}
function reserve(name) {
  const full = output(name);
  assert.ok(!fs.existsSync(full), 'Preserve the original: ' + name);
  return full;
}
function redact(value) {
  let text = typeof value === 'string' ? value : JSON.stringify(value, null, 2);
  for (const item of sensitive) if (item) text = text.split(item).join('[REDACTED]');
  return text.replace(/(https:\/\/[^\s"<>?]+)\?[^\s"<>]+/g, '$1?[REDACTED_QUERY]');
}
function writeJson(file, value) {
  guard(file); guard(path.dirname(file));
  fs.mkdirSync(path.dirname(file), { recursive: true });
  guard(file);
  fs.writeFileSync(file, redact(value) + '\n', { flag: 'wx' });
}
function environment() {
  const names = ['tmp', 'home', 'appdata', 'localappdata', 'npm', 'gh', 'logs', 'xdg-config', 'xdg-cache', 'xdg-data'];
  const dirs = Object.fromEntries(names.map(name => [name, output(name)]));
  for (const dir of Object.values(dirs)) fs.mkdirSync(dir, { recursive: true });
  return { ...process.env, TEMP: dirs.tmp, TMP: dirs.tmp, TMPDIR: dirs.tmp,
    HOME: dirs.home, USERPROFILE: dirs.home, APPDATA: dirs.appdata, LOCALAPPDATA: dirs.localappdata,
    XDG_CONFIG_HOME: dirs['xdg-config'], XDG_CACHE_HOME: dirs['xdg-cache'], XDG_DATA_HOME: dirs['xdg-data'],
    GH_CONFIG_DIR: dirs.gh, GH_PROMPT_DISABLED: '1', GH_NO_UPDATE_NOTIFIER: '1', GH_NO_EXTENSION_UPDATE_NOTIFIER: '1',
    npm_config_cache: dirs.npm, npm_config_update_notifier: 'false', PYTHONDONTWRITEBYTECODE: '1', PYTHONUTF8: '1',
    WRANGLER_SEND_METRICS: 'false', CLOUDFLARE_SEND_METRICS: 'false',
    WECHAT_WEBHOOK_KEY: '', ANTHROPIC_API_KEY: '', GIT_TERMINAL_PROMPT: '0' };
}
function githubToken(env) {
  const authEnv = { ...env, GH_CONFIG_DIR: 'C:/Users/SU/AppData/Roaming/GitHub CLI' };
  delete authEnv.GH_TOKEN; delete authEnv.GITHUB_TOKEN;
  const result = spawnSync('gh', ['auth', 'token', '--hostname', 'github.com', '--user', 'Eitan-S-23'], {
    cwd: project, env: authEnv, encoding: 'utf8', timeout: 30000, windowsHide: true,
  });
  assert.equal(result.status, 0, 'Existing GitHub authentication unavailable');
  const value = result.stdout.trim(); assert.ok(value); sensitive.add(value);
  return value;
}
function cloudInputs() {
  const p41 = project + '/.cache/p41-dev-20261015';
  const account = readJson(p41 + '/.cache/cf-firmware-setup-20261015/d1-edit-r2/wrangler.json').account_id;
  assert.equal(sha256(account), '01910e669500c221e2154f608e9f4e856b0a08297026e1ea98f1d18dd8cf9742');
  const provisioning = fs.readFileSync(p41 + '/.cache/cf-auth-input/token.txt', 'utf8').trim();
  const ci = fs.readFileSync(p41 + '/.cache/cf-auth-input/p41-ci-token.txt', 'utf8').trim();
  for (const value of [account, provisioning, ci]) sensitive.add(value);
  return { account, provisioning, ci };
}
async function http(url, options, receipts) {
  const parsed = new URL(url);
  assert.ok(['https://api.cloudflare.com', 'https://api.github.com', 'https://developers.cloudflare.com'].includes(parsed.origin));
  assert.ok(!parsed.username && !parsed.password);
  const method = options.method || 'GET';
  const receipt = { method, origin: parsed.origin, path: parsed.pathname, startedAt: new Date().toISOString() };
  receipts.push(receipt);
  const dispatcher = new ProxyAgent({ uri: 'http://127.0.0.1:7897', allowH2: false, requestTls: { rejectUnauthorized: true } });
  try {
    const response = await request(url, { ...options, method, dispatcher, maxRedirections: 0,
      headersTimeout: 30000, bodyTimeout: 30000, signal: AbortSignal.timeout(60000) });
    const chunks = []; let size = 0;
    for await (const chunk of response.body) {
      size += chunk.length; assert.ok(size <= (options.maxBytes || 4 * 1024 * 1024), 'Bounded response exceeded'); chunks.push(chunk);
    }
    const bytes = Buffer.concat(chunks);
    Object.assign(receipt, { status: response.statusCode, bytes: size, sha256: sha256(bytes),
      requestId: response.headers['x-github-request-id'] || response.headers['cf-ray'], endedAt: new Date().toISOString() });
    let json; try { json = JSON.parse(bytes); } catch { /* Public docs and empty responses are not JSON. */ }
    return { status: response.statusCode, bytes, json, headers: response.headers };
  } catch (error) {
    Object.assign(receipt, { errorClass: error.code || error.name, endedAt: new Date().toISOString() });
    throw Error('Bounded HTTP operation failed; see the sanitized receipt');
  } finally { await dispatcher.destroy(); }
}
module.exports = { fs, path, assert, project, worktree, base, guard, output, reserve, redact,
  sha256, readJson, writeJson, environment, githubToken, cloudInputs, http, sensitive };
