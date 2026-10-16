const fs = require('node:fs');
const path = require('node:path');
const cp = require('node:child_process');
const root = fs.realpathSync.native(path.resolve(__dirname, '..'));
const [label, directory, executable, ...args] = process.argv.slice(2);
if (!/^[a-z0-9-]+$/.test(label || '') || !executable) throw Error('label, cwd and command required');
function contained(value) {
  const target = path.resolve(root, value);
  let parent = target;
  const rest = [];
  while (!fs.existsSync(parent)) { rest.unshift(path.basename(parent)); parent = path.dirname(parent); }
  const actual = path.resolve(fs.realpathSync.native(parent), ...rest);
  const rel = path.relative(root, actual);
  if (rel === '..' || rel.startsWith('..' + path.sep) || path.isAbsolute(rel)) throw Error('outside worktree');
  for (let p = parent; p !== path.dirname(p); p = path.dirname(p)) {
    if (fs.lstatSync(p).isSymbolicLink()) throw Error('reparse point: ' + p);
  }
  return target;
}
const cwd = contained(directory);
const env = { ...process.env };
for (const key of Object.keys(env)) {
  if (/^(CLOUDFLARE_|CF_|TRACE_|GH_|GITHUB_TOKEN|OTA_AES_KEY|ANTHROPIC_|OPENAI_|WECHAT_|CC_CONNECT|NODE_OPTIONS|NODE_COMPILE_CACHE|GIT_CONFIG|GIT_INDEX_FILE)/i.test(key)) delete env[key];
}
const dirs = {
  TEMP: 'tmp', TMP: 'tmp', TMPDIR: 'tmp', HOME: 'home', USERPROFILE: 'home',
  APPDATA: 'appdata', LOCALAPPDATA: 'localappdata', XDG_CONFIG_HOME: 'config',
  XDG_CACHE_HOME: 'cache', XDG_DATA_HOME: 'data', npm_config_cache: 'npm-cache',
  PIP_CACHE_DIR: 'pip-cache', WRANGLER_LOG_PATH: 'wrangler-logs'
};
const outputs = Object.fromEntries(Object.entries(dirs).map(([key, dir]) => [key, contained('.cache/runtime/' + dir)]));
const logs = contained('.cache/logs');
const stdoutPath = contained('.cache/logs/' + label + '.stdout.txt');
const stderrPath = contained('.cache/logs/' + label + '.stderr.txt');
const receiptPath = contained('.cache/logs/' + label + '.json');
for (const value of [...Object.values(outputs), logs]) fs.mkdirSync(value, { recursive: true });
Object.assign(env, outputs, { PYTHONDONTWRITEBYTECODE: '1', PYTHONUTF8: '1',
  WRANGLER_SEND_METRICS: 'false', WRANGLER_LOG: 'none', GIT_OPTIONAL_LOCKS: '0',
  GIT_TERMINAL_PROMPT: '0', NPM_CONFIG_UPDATE_NOTIFIER: 'false', npm_config_update_notifier: 'false' });
const stdout = fs.openSync(stdoutPath, 'wx');
const stderr = fs.openSync(stderrPath, 'wx');
const started = new Date().toISOString();
const child = cp.spawn(executable, args, { cwd, env, windowsHide: true, stdio: ['ignore', 'pipe', 'pipe'] });
const deadline = setTimeout(() => child.kill(), 900000);
child.stdout.on('data', bytes => { fs.writeSync(stdout, bytes); process.stdout.write(bytes); });
child.stderr.on('data', bytes => { fs.writeSync(stderr, bytes); process.stderr.write(bytes); });
let error;
child.on('error', value => { error = value.message; });
child.on('close', (code, signal) => {
  clearTimeout(deadline);
  fs.closeSync(stdout); fs.closeSync(stderr);
  const receipt = { cwd, executable, args, pid: child.pid, started, ended: new Date().toISOString(),
    exitCode: code, signal, error, outputs, stdoutPath, stderrPath, closed: true };
  fs.writeFileSync(receiptPath, JSON.stringify(receipt, null, 2) + '\n', { flag: 'wx' });
  process.stdout.write('\nRECEIPT=' + receiptPath + ' EXIT=' + code + '\n');
  process.exitCode = code ?? 1;
});
