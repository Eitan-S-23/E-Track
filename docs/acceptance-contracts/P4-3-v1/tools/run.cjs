const fs = require('node:fs');
const path = require('node:path');
const assert = require('node:assert/strict');
const { spawnSync } = require('node:child_process');
const { root, bundle, guard, sha, jsonLocal } = require('./io.cjs');

const [label, command, ...args] = process.argv.slice(2);
assert.match(label || '', /^[a-z0-9-]+$/);
assert.ok(['node', 'python'].includes(command), 'Offline interpreters only');
assert.equal(fs.realpathSync(process.cwd()), fs.realpathSync(root));
const host = jsonLocal(`${bundle}/inputs/host.json`);
assert.equal(process.version, host.node.version);
assert.equal(sha(fs.readFileSync(process.execPath)), host.node.sha256);
assert.equal(sha(fs.readFileSync(host.tar.executable)), host.tar.sha256);
const dirs = Object.fromEntries(['tmp', 'home', 'appdata', 'localappdata', 'npm', 'xdg-config', 'xdg-cache', 'xdg-data']
  .map(name => [name, guard(`.cache/p43-formal/${name}`)]));
const outputBase = label.startsWith('formal-') ? `${bundle}/evidence` : '.cache/p43-formal/development';
const logPath = guard(`${outputBase}/${label}.log`);
const receiptPath = guard(`${outputBase}/${label}.json`);
assert.ok(!fs.existsSync(logPath) && !fs.existsSync(receiptPath), 'Preserve original command records');
for (const dir of [...Object.values(dirs), path.dirname(logPath)]) fs.mkdirSync(dir, { recursive: true });
guard(logPath); guard(receiptPath);
const env = { ...process.env, TEMP: dirs.tmp, TMP: dirs.tmp, TMPDIR: dirs.tmp,
  HOME: dirs.home, USERPROFILE: dirs.home, APPDATA: dirs.appdata, LOCALAPPDATA: dirs.localappdata,
  XDG_CONFIG_HOME: dirs['xdg-config'], XDG_CACHE_HOME: dirs['xdg-cache'], XDG_DATA_HOME: dirs['xdg-data'],
  npm_config_cache: dirs.npm, npm_config_update_notifier: 'false',
  PYTHONDONTWRITEBYTECODE: '1', PYTHONUTF8: '1', GIT_OPTIONAL_LOCKS: '0', GIT_TERMINAL_PROMPT: '0',
  GCM_INTERACTIVE: 'never', GIT_CONFIG_GLOBAL: 'C:\\Users\\SU\\.gitconfig' };
for (const key of ['GH_TOKEN', 'GITHUB_TOKEN', 'CLOUDFLARE_API_TOKEN', 'CLOUDFLARE_API_KEY', 'ANTHROPIC_API_KEY', 'WECHAT_WEBHOOK_KEY']) delete env[key];
const started = new Date().toISOString();
const result = spawnSync(command === 'node' ? process.execPath : command, args,
  { cwd: root, env, windowsHide: true, timeout: 900000, maxBuffer: 128 * 1024 * 1024 });
const output = Buffer.concat([result.stdout || Buffer.alloc(0), result.stderr || Buffer.alloc(0)]);
fs.writeFileSync(logPath, output, { flag: 'wx' });
fs.writeFileSync(receiptPath, JSON.stringify({ label, command, args, cwd: root, started,
  ended: new Date().toISOString(), exitCode: result.status, signal: result.signal,
  error: result.error?.message || null, node: process.version, logPath }, null, 2) + '\n', { flag: 'wx' });
process.stdout.write(output);
if (result.error) process.stderr.write(result.error.message + '\n');
process.exitCode = result.status === 0 ? 0 : (result.status || 2);
