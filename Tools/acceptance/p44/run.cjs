// Contained command capture. This module never grants platform authority.
const fs = require('node:fs');
const path = require('node:path');
const crypto = require('node:crypto');
const cp = require('node:child_process');
const assert = require('node:assert/strict');
const root = path.resolve(__dirname, '../../..');
const base = path.join(root, 'docs/acceptance-contracts/P4-4-v3/evidence');
const sha256 = bytes => crypto.createHash('sha256').update(bytes).digest('hex');

function guard(target, boundary = root) {
  const full = path.resolve(target), relative = path.relative(path.resolve(boundary), full);
  assert(relative !== '..' && !relative.startsWith('..' + path.sep) && !path.isAbsolute(relative), 'PATH_OUTSIDE_ROOT');
  let current = path.parse(full).root;
  for (const part of full.slice(current.length).split(path.sep).filter(Boolean)) {
    current = path.join(current, part);
    let stat;
    try { stat = fs.lstatSync(current); } catch (error) { if (error.code === 'ENOENT') continue; throw error; }
    assert(!stat.isSymbolicLink(), 'REPARSE_PATH');
    if (process.platform === 'win32') {
      const checked = cp.spawnSync('fsutil.exe', ['reparsepoint', 'query', current], {
        cwd: root, windowsHide: true, timeout: 10000,
      });
      const message = new TextDecoder('gbk').decode(Buffer.concat([checked.stdout || Buffer.alloc(0), checked.stderr || Buffer.alloc(0)]));
      assert(checked.status === 1 && /not a reparse point|\u4e0d\u662f\u4e00\u4e2a\u91cd\u5206\u6790\u70b9/.test(message), 'UNVERIFIED_PATH');
    }
  }
  return full;
}
function destination(name) {
  assert(/^[a-zA-Z0-9_./-]+$/.test(name) && name.split('/').every(p => p && p !== '.' && p !== '..'), 'OUTPUT_NAME');
  return guard(path.join(base, name));
}
function write(name, value) {
  const file = destination(name);
  assert(!fs.existsSync(file), 'ORIGINAL_EXISTS');
  const bytes = Buffer.isBuffer(value) ? value : Buffer.from(typeof value === 'string' ? value : JSON.stringify(value, null, 2) + '\n');
  guard(path.dirname(file)); fs.mkdirSync(path.dirname(file), { recursive: true }); guard(file);
  fs.writeFileSync(file, bytes, { flag: 'wx' });
  return { path: name, size_bytes: bytes.length, sha256: sha256(bytes) };
}
const read = name => JSON.parse(fs.readFileSync(destination(name), 'utf8'));
const readBytes = name => fs.readFileSync(destination(name));
function fileRef(name) {
  const bytes = fs.readFileSync(destination(name));
  return { path: name, size_bytes: bytes.length, sha256: sha256(bytes) };
}
function environment() {
  for (const key of ['NODE_OPTIONS', 'NODE_V8_COVERAGE', 'NODE_COMPILE_CACHE', 'SSLKEYLOGFILE', 'GIT_TRACE', 'GIT_TRACE2',
    'GIT_TRACE2_EVENT', 'GIT_TRACE2_PERF', 'GIT_INDEX_FILE', 'GIT_OBJECT_DIRECTORY', 'BASH_ENV', 'ENV']) {
    assert(!process.env[key], 'UNREVIEWED_OUTPUT_OVERRIDE');
  }
  const names = ['tmp', 'home', 'appdata', 'localappdata', 'xdg-config', 'xdg-cache', 'xdg-data', 'gh', 'npm'];
  const dirs = Object.fromEntries(names.map(name => [name, guard(path.join(root, '.cache/p44-formal-host', name))]));
  for (const dir of Object.values(dirs)) fs.mkdirSync(dir, { recursive: true });
  return { ...process.env, TEMP: dirs.tmp, TMP: dirs.tmp, TMPDIR: dirs.tmp, HOME: dirs.home, USERPROFILE: dirs.home,
    APPDATA: dirs.appdata, LOCALAPPDATA: dirs.localappdata, XDG_CONFIG_HOME: dirs['xdg-config'],
    XDG_CACHE_HOME: dirs['xdg-cache'], XDG_DATA_HOME: dirs['xdg-data'], GH_CONFIG_DIR: dirs.gh,
    GH_PROMPT_DISABLED: '1', GH_NO_UPDATE_NOTIFIER: '1', GH_NO_EXTENSION_UPDATE_NOTIFIER: '1',
    npm_config_cache: dirs.npm, npm_config_update_notifier: 'false', PYTHONDONTWRITEBYTECODE: '1',
    PYTHONUTF8: '1', GIT_TERMINAL_PROMPT: '0', GIT_OPTIONAL_LOCKS: '0',
    WECHAT_WEBHOOK_KEY: '', ANTHROPIC_API_KEY: '', WRANGLER_SEND_METRICS: 'false' };
}
function git(args) {
  const result = cp.spawnSync('git', ['--no-optional-locks', '-c', 'core.fsmonitor=false', ...args], {
    cwd: root, windowsHide: true, encoding: 'utf8', timeout: 30000,
  });
  assert.equal(result.status, 0, 'GIT_READ_FAILED');
  return result.stdout.trim();
}
module.exports = { fs, path, cp, assert, root, base, sha256, guard, destination, write, read, readBytes, fileRef, environment, git };

if (require.main === module) {
  const [label, command, ...args] = process.argv.slice(2);
  assert(/^[a-z0-9-]+$/.test(label || '') && ['node', 'python'].includes(command), 'COMMAND_NOT_ALLOWED');
  const stem = 'commands/' + label;
  for (const suffix of ['.log', '.json']) assert(!fs.existsSync(destination(stem + suffix)), 'COMMAND_ALREADY_CAPTURED');
  const env = environment();
  const logPath = destination(stem + '.log');
  fs.mkdirSync(guard(path.dirname(logPath)), { recursive: true }); guard(logPath);
  const fd = fs.openSync(logPath, 'wx');
  const started = new Date().toISOString();
  const child = cp.spawn(command, args, { cwd: root, env, windowsHide: true, stdio: ['ignore', 'pipe', 'pipe'] });
  const timer = setTimeout(() => {
    if (process.platform === 'win32') cp.spawnSync('taskkill.exe', ['/PID', String(child.pid), '/T', '/F'], { cwd: root, windowsHide: true, timeout: 15000 });
    else child.kill();
  }, 60 * 60 * 1000);
  for (const stream of [child.stdout, child.stderr]) stream.on('data', bytes => { fs.writeSync(fd, bytes); process.stdout.write(bytes); });
  child.on('error', () => fs.writeSync(fd, 'COMMAND_START_FAILED\n'));
  child.on('close', (exitCode, signal) => {
    clearTimeout(timer); fs.closeSync(fd);
    write(stem + '.json', { label, command, args, cwd: root, started, ended: new Date().toISOString(),
      exitCode, signal, process_closed: true, output: fileRef(stem + '.log') });
    process.exitCode = exitCode === 0 ? 0 : 1;
  });
}
