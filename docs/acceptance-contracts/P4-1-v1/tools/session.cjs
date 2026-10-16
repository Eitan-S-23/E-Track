// P4-1 acceptance transport/containment adapter, not a release implementation.
const fs = require('node:fs');
const path = require('node:path');
const cp = require('node:child_process');
const assert = require('node:assert/strict');
const crypto = require('node:crypto');

const root = fs.realpathSync.native(path.resolve(__dirname, '../../../..'));
assert.equal(fs.realpathSync.native(process.cwd()), root, 'Run from the authorized worktree root');
const repository = 'Eitan-S-23/E-Track';
const branch = 'dev/p4-1/unattended-20261015';
const outputRoot = '.cache/p41-acceptance-20261016';
const initialEnvironment = { ...process.env };
const hash = bytes => crypto.createHash('sha256').update(bytes).digest('hex');

function guard(value) {
  const target = path.resolve(root, value);
  let ancestor = target;
  while (!fs.existsSync(ancestor)) ancestor = path.dirname(ancestor);
  const actual = path.resolve(fs.realpathSync.native(ancestor), path.relative(ancestor, target));
  const relative = path.relative(root, actual);
  assert(!path.isAbsolute(relative) && relative !== '..' && !relative.startsWith('..' + path.sep), 'Outside authorized worktree');
  for (let p = ancestor; ; p = path.dirname(p)) {
    assert(!fs.lstatSync(p).isSymbolicLink(), 'Reparse point: ' + p);
    assert.equal(fs.realpathSync.native(p).toLowerCase(), p.toLowerCase(), 'Unresolved path: ' + p);
    if (p === path.dirname(p)) break;
  }
  return actual;
}

function write(value, bytes) {
  const destination = guard(value);
  assert(!fs.existsSync(destination), 'Preserve existing evidence: ' + destination);
  fs.mkdirSync(guard(path.dirname(destination)), { recursive: true });
  fs.writeFileSync(guard(destination), bytes, { flag: 'wx' });
  return { path: path.relative(root, destination).replaceAll('\\', '/'),
    size_bytes: Buffer.byteLength(bytes), sha256: hash(bytes) };
}
const writeJson = (value, data) => write(value, JSON.stringify(data, null, 2) + '\n');

function environment() {
  const env = { ...initialEnvironment };
  for (const name of Object.keys(env)) {
    if (/^(GH_|GITHUB_TOKEN|CLOUDFLARE_|CF_|TRACE_|OTA_|GIT_|NODE_OPTIONS|NODE_COMPILE_CACHE|OPENAI_|ANTHROPIC_|CC_CONNECT)/i.test(name)) delete env[name];
  }
  delete env.WECHAT_WEBHOOK_KEY;
  const directories = { TEMP: 'tmp', TMP: 'tmp', TMPDIR: 'tmp', HOME: 'home', USERPROFILE: 'home',
    APPDATA: 'appdata', LOCALAPPDATA: 'localappdata', XDG_CONFIG_HOME: 'config', XDG_CACHE_HOME: 'cache',
    XDG_DATA_HOME: 'data', GH_CONFIG_DIR: 'config/gh', npm_config_cache: 'npm-cache',
    PIP_CACHE_DIR: 'pip-cache', WRANGLER_LOG_PATH: 'wrangler-logs' };
  for (const [key, relative] of Object.entries(directories)) {
    env[key] = guard(outputRoot + '/runtime/' + relative);
  }
  // All destinations are checked before the first mkdir or child invocation.
  for (const key of Object.keys(directories)) fs.mkdirSync(guard(env[key]), { recursive: true });
  return Object.assign(env, { PYTHONDONTWRITEBYTECODE: '1', PYTHONUTF8: '1',
    WRANGLER_SEND_METRICS: 'false', WRANGLER_LOG: 'none', GH_NO_UPDATE_NOTIFIER: '1', GH_PROMPT_DISABLED: '1',
    GIT_OPTIONAL_LOCKS: '0', GIT_TERMINAL_PROMPT: '0', npm_config_update_notifier: 'false' });
}

function git(args) {
  return cp.execFileSync('git', ['--no-optional-locks', '-c', 'core.fsmonitor=false',
    '-c', 'gc.auto=0', '-c', 'maintenance.auto=false', ...args],
  { cwd: root, env: environment(), windowsHide: true, encoding: 'utf8', timeout: 30000 }).trim();
}

let token;
function githubToken() {
  if (token) return token;
  const candidates = [initialEnvironment.GH_CONFIG_DIR,
    initialEnvironment.APPDATA && path.join(initialEnvironment.APPDATA, 'GitHub CLI'),
    initialEnvironment.APPDATA && path.join(initialEnvironment.APPDATA, 'gh'),
    initialEnvironment.USERPROFILE && path.join(initialEnvironment.USERPROFILE, '.config/gh')]
    .filter(Boolean).filter(p => fs.existsSync(path.join(p, 'hosts.yml')));
  assert(candidates.length > 0, 'Existing GitHub credential configuration unavailable');
  // auth token is read-only. Its original config is an input; update checks and
  // all controllable runtime/cache destinations remain disabled or contained.
  const env = { ...environment(), GH_CONFIG_DIR: candidates[0] };
  const result = cp.spawnSync('C:/Program Files/GitHub CLI/gh.exe',
    ['auth', 'token', '--hostname', 'github.com', '--user', 'Eitan-S-23'],
    { cwd: root, env, windowsHide: true, encoding: 'utf8', timeout: 15000 });
  assert.equal(result.status, 0, 'Existing GitHub identity unavailable');
  token = result.stdout.trim();
  assert(token && !/\s/.test(token));
  return token;
}

async function githubGet(route) {
  assert(route === '/user' || route === '/repos/' + repository || route.startsWith('/repos/' + repository + '/'));
  const response = await fetch('https://api.github.com' + route, { redirect: 'error',
    headers: { Authorization: 'Bearer ' + githubToken(), Accept: 'application/vnd.github+json',
      'X-GitHub-Api-Version': '2022-11-28' }, signal: AbortSignal.timeout(60000) });
  const bytes = Buffer.from(await response.arrayBuffer());
  return { status: response.status, bytes, data: bytes.length ? JSON.parse(bytes) : null,
    requestId: response.headers.get('x-github-request-id'), date: response.headers.get('date') };
}

async function get(label, route) {
  assert(/^[a-z0-9-]+$/.test(label));
  const destination = guard(outputRoot + '/github/' + label + '.json');
  const receiptPath = guard(outputRoot + '/github/' + label + '.receipt.json');
  assert(!fs.existsSync(destination) && !fs.existsSync(receiptPath));
  const started = new Date().toISOString();
  const result = await githubGet(route);
  const artifact = write(destination, result.bytes);
  writeJson(receiptPath, { started, ended: new Date().toISOString(), method: 'GET', route,
    status: result.status, requestId: result.requestId, date: result.date, artifact });
  console.log(JSON.stringify({ status: result.status, route, artifact }));
  if (result.status !== 200) process.exitCode = 1;
  return result;
}

async function run(label, directory, executable, args) {
  assert(/^[a-z0-9-]+$/.test(label));
  const cwd = guard(directory);
  const stem = outputRoot + '/commands/' + label;
  const paths = ['.stdout.txt', '.stderr.txt', '.json'].map(extension => guard(stem + extension));
  paths.forEach(p => assert(!fs.existsSync(p), 'Command label already used'));
  fs.mkdirSync(guard(path.dirname(paths[0])), { recursive: true });
  const env = environment();
  const stdout = fs.openSync(guard(paths[0]), 'wx');
  const stderr = fs.openSync(guard(paths[1]), 'wx');
  const started = new Date().toISOString();
  const child = cp.spawn(executable, args, { cwd, env, windowsHide: true, stdio: ['ignore', 'pipe', 'pipe'] });
  const deadline = setTimeout(() => child.kill(), 900000);
  child.stdout.on('data', bytes => { fs.writeSync(stdout, bytes); process.stdout.write(bytes); });
  child.stderr.on('data', bytes => { fs.writeSync(stderr, bytes); process.stderr.write(bytes); });
  let error;
  child.on('error', value => { error = value.message; });
  await new Promise(resolve => child.on('close', (exitCode, signal) => {
    clearTimeout(deadline); fs.closeSync(stdout); fs.closeSync(stderr);
    const streams = paths.slice(0, 2).map(p => ({ path: path.relative(root, p).replaceAll('\\', '/'),
      size_bytes: fs.statSync(p).size, sha256: hash(fs.readFileSync(p)) }));
    writeJson(paths[2], { cwd, executable, args, pid: child.pid, started, ended: new Date().toISOString(),
      exitCode, signal, error, streams, closed: true });
    console.log(JSON.stringify({ receipt: paths[2], exitCode, closed: true }));
    process.exitCode = exitCode ?? 1;
    resolve();
  }));
}

module.exports = { root, repository, branch, outputRoot, guard, write, writeJson, environment,
  hash, git, githubToken, githubGet, get, run };
if (require.main === module) {
  const [operation, ...args] = process.argv.slice(2);
  Promise.resolve().then(() => {
    if (operation === 'get' && args.length === 2) return get(...args);
    if (operation === 'run' && args.length >= 3) return run(args[0], args[1], args[2], args.slice(3));
    throw Error('Expected get LABEL ROUTE or run LABEL CWD EXECUTABLE ARGS');
  }).catch(error => { console.error(JSON.stringify({ error: error.message, causeCode: error.cause?.code })); process.exitCode = 1; });
}
