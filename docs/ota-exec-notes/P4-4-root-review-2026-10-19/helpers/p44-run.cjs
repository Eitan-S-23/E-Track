const fs = require('node:fs');
const path = require('node:path');
const { spawn, spawnSync } = require('node:child_process');
const root = path.resolve(__dirname, '..');
const commonGit = 'D:/github/my/E-Track/.git';

// Thin adaptation of the P4-3 contained command adapter; no platform protocol.
function guard(target, boundary = root) {
  const full = path.resolve(target);
  const relative = path.relative(path.resolve(boundary), full);
  if (relative === '..' || relative.startsWith(`..${path.sep}`) || path.isAbsolute(relative)) throw Error('Outside authorized boundary: ' + full);
  let current = path.parse(full).root;
  for (const part of full.slice(current.length).split(path.sep).filter(Boolean)) {
    current = path.join(current, part);
    if (!fs.existsSync(current)) continue;
    const check = spawnSync('fsutil.exe', ['reparsepoint', 'query', current], { cwd: root, windowsHide: true });
    const message = new TextDecoder('gbk').decode(Buffer.concat([check.stdout || Buffer.alloc(0), check.stderr || Buffer.alloc(0)]));
    if (check.status !== 1 || !/not a reparse point|\u4e0d\u662f\u4e00\u4e2a\u91cd\u5206\u6790\u70b9/.test(message)) throw Error('Unverified path: ' + current);
  }
  return full;
}

if (require.main !== module) module.exports = { root, guard };
else {
  const [label, command, ...args] = process.argv.slice(2);
  if (!/^[a-z0-9-]+$/.test(label || '') || !command) throw Error('Expected unique label and command');
  if (command === 'preflight') {
    for (const name of args) process.stdout.write(guard(path.resolve(root, name)) + '\n');
    process.exit(0);
  }
  const dirs = Object.fromEntries(['tmp', 'home', 'appdata', 'localappdata', 'npm', 'gh', 'logs', 'xdg-config', 'xdg-cache', 'xdg-data'].map(name => [name, guard(path.join(root, '.cache/p44', name))]));
  const logPath = guard(path.join(dirs.logs, label + '.log'));
  const receiptPath = guard(path.join(dirs.logs, label + '.json'));
  if (fs.existsSync(logPath) || fs.existsSync(receiptPath)) throw Error('Never overwrite an observation');
  for (const dir of Object.values(dirs)) fs.mkdirSync(dir, { recursive: true });
  const env = { ...process.env, TEMP: dirs.tmp, TMP: dirs.tmp, TMPDIR: dirs.tmp,
    HOME: dirs.home, USERPROFILE: dirs.home, APPDATA: dirs.appdata, LOCALAPPDATA: dirs.localappdata,
    XDG_CONFIG_HOME: dirs['xdg-config'], XDG_CACHE_HOME: dirs['xdg-cache'], XDG_DATA_HOME: dirs['xdg-data'],
    npm_config_cache: dirs.npm, npm_config_update_notifier: 'false',
    GH_CONFIG_DIR: dirs.gh, GH_PROMPT_DISABLED: '1', GH_NO_UPDATE_NOTIFIER: '1', GH_NO_EXTENSION_UPDATE_NOTIFIER: '1',
    WRANGLER_SEND_METRICS: 'false', CLOUDFLARE_SEND_METRICS: 'false',
    WRANGLER_LOG_PATH: guard(path.join(dirs.logs, label + '-wrangler.log')),
    PYTHONDONTWRITEBYTECODE: '1', PYTHONUTF8: '1', GIT_TERMINAL_PROMPT: '0',
    GIT_CONFIG_GLOBAL: 'C:/Users/SU/.gitconfig', WECHAT_WEBHOOK_KEY: '', ANTHROPIC_API_KEY: '' };
  let executable = command, actualArgs = args;
  if (command === 'git' || command === 'github-git') {
    guard(commonGit, commonGit);
    executable = 'git'; actualArgs = ['-c', 'gc.auto=0', '-c', 'maintenance.auto=false', ...args];
  }
  if (['gh', 'github-git'].includes(command)) {
    const authEnv = { ...process.env, TEMP: dirs.tmp, TMP: dirs.tmp, TMPDIR: dirs.tmp, GH_NO_UPDATE_NOTIFIER: '1', GH_PROMPT_DISABLED: '1' };
    delete authEnv.GH_TOKEN; delete authEnv.GITHUB_TOKEN;
    const auth = spawnSync('gh', ['auth', 'token', '--hostname', 'github.com', '--user', 'Eitan-S-23'], { cwd: root, env: authEnv, encoding: 'utf8', timeout: 30000, windowsHide: true });
    if (auth.status !== 0 || !auth.stdout.trim()) throw Error('Existing owner credential unavailable');
    env.GH_TOKEN = auth.stdout.trim(); delete env.GITHUB_TOKEN;
    if (command === 'github-git') {
      env.GIT_CONFIG_COUNT = '3';
      env.GIT_CONFIG_KEY_0 = 'credential.helper'; env.GIT_CONFIG_VALUE_0 = '';
      env.GIT_CONFIG_KEY_1 = 'http.https://github.com/.extraheader';
      env.GIT_CONFIG_VALUE_1 = 'AUTHORIZATION: basic ' + Buffer.from('Eitan-S-23:' + env.GH_TOKEN).toString('base64');
      env.GIT_CONFIG_KEY_2 = 'http.sslBackend'; env.GIT_CONFIG_VALUE_2 = 'openssl';
    }
  }
  const startedAt = new Date().toISOString();
  const log = fs.createWriteStream(logPath, { flags: 'wx' });
  const child = spawn(executable, actualArgs, { cwd: root, env, windowsHide: true, stdio: ['ignore', 'pipe', 'pipe'] });
  const timer = setTimeout(() => child.kill(), 20 * 60 * 1000);
  for (const stream of [child.stdout, child.stderr]) {
    const lines = require('node:readline').createInterface({ input: stream });
    lines.on('line', line => {
      const safe = line.replace(/(https?:\/\/[^?\s"<>]+)\?[^\s"<>]+/g, '$1?[REDACTED_QUERY]') + '\n';
      log.write(safe); process.stdout.write(safe);
    });
  }
  child.on('error', error => { log.write(error.message); process.stderr.write(error.message); });
  child.on('close', (exitCode, signal) => {
    clearTimeout(timer);
    log.end(() => {
      fs.writeFileSync(receiptPath, JSON.stringify({ label, command, args, cwd: root, startedAt, endedAt: new Date().toISOString(), exitCode, signal, logPath }, null, 2) + '\n', { flag: 'wx' });
      process.exitCode = exitCode === 0 ? 0 : 1;
    });
  });
}
