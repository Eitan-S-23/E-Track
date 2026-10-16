const fs = require('node:fs');
const path = require('node:path');
const cp = require('node:child_process');
const crypto = require('node:crypto');

const root = path.resolve(__dirname, '../../..');
const configPath = path.join(__dirname, 'wrangler.json');
const operation = process.argv[2];
const commands = {
  help: ['d1', 'migrations', 'apply', '--help'],
  'import-help': ['d1', 'execute', '--help'],
  'inspect-before': ['d1', 'execute', 'e-track-firmware-p41-test', '--remote', '--config', configPath,
    '--command', "SELECT type,name,tbl_name,sql FROM sqlite_master ORDER BY type,name; SELECT id,name,applied_at FROM d1_migrations ORDER BY id;", '--json'],
  'inspect-before-r2': ['d1', 'execute', 'e-track-firmware-p41-test', '--remote', '--config', configPath,
    '--command', "SELECT type,name,tbl_name,sql FROM sqlite_master ORDER BY type,name; SELECT id,name,applied_at FROM d1_migrations ORDER BY id;", '--json'],
  'import-accepted': ['d1', 'execute', 'e-track-firmware-p41-test', '--remote', '--config', configPath,
    '--file', path.join(__dirname, 'accepted-migrations.sql'), '--yes', '--json'],
  'inspect-after': ['d1', 'execute', 'e-track-firmware-p41-test', '--remote', '--config', configPath,
    '--command', "SELECT type,name,tbl_name,sql FROM sqlite_master ORDER BY type,name; SELECT id,name,applied_at FROM d1_migrations ORDER BY id; PRAGMA foreign_key_check;", '--json'],
  migrate: ['d1', 'migrations', 'apply', 'e-track-firmware-p41-test', '--remote', '--config', configPath],
  deploy: ['deploy', '--no-bundle', '--config', configPath],
  secrets: ['secret', 'bulk', '--config', configPath]
};
if (!Object.hasOwn(commands, operation)) throw Error('Unknown bounded operation');
const config = JSON.parse(fs.readFileSync(configPath, 'utf8'));
const owned = JSON.parse(fs.readFileSync(path.join(__dirname, 'resources-created.json'), 'utf8'));
if (config.name !== owned.workerName || config.name !== 'e-track-firmware-p41-test'
    || config.account_id !== owned.accountId
    || config.d1_databases[0].database_id !== owned.d1.id
    || config.kv_namespaces[0].id !== owned.kv.id
    || config.r2_buckets[0].bucket_name !== owned.r2.name) throw Error('Target identity mismatch');
const bundle = fs.readFileSync(path.resolve(__dirname, config.main));
if (crypto.createHash('sha256').update(bundle).digest('hex') !==
    '9ff814b0fd1731418a2250a3ae941ff1f6ce0db99233f6f1db42a1ba2c161082') throw Error('CI bundle mismatch');

function contained(value) {
  const target = path.resolve(value);
  let existing = target;
  while (!fs.existsSync(existing)) existing = path.dirname(existing);
  const real = path.resolve(fs.realpathSync.native(existing), path.relative(existing, target));
  const relative = path.relative(root, real);
  if (relative === '..' || relative.startsWith('..' + path.sep) || path.isAbsolute(relative)) {
    throw Error('Output outside worktree');
  }
  for (let p = existing; p !== path.dirname(p); p = path.dirname(p)) {
    if (fs.lstatSync(p).isSymbolicLink()) throw Error('Linked output');
  }
  return target;
}

const runtime = contained(path.join(__dirname, 'runtime'));
const output = contained(path.join(__dirname, operation + '.json'));
if (fs.existsSync(output)) throw Error('Preserve the existing operation receipt');
const token = operation === 'help' ? '' : fs.readFileSync(path.join(root, '.cache/cf-auth-input/token.txt'), 'utf8').trim();
if (operation !== 'help' && !token) throw Error('Missing explicit setup credential');
const secretPath = path.join(root, '.cache/cf-auth-input/firmware-test-secrets.json');
const secrets = fs.existsSync(secretPath) ? JSON.parse(fs.readFileSync(secretPath, 'utf8')) : {};
const redactions = [token, ...Object.values(secrets)].filter(x => typeof x === 'string' && x.length > 10);
const redact = value => redactions.reduce((s, secret) => s.split(secret).join('[REDACTED]'), String(value ?? ''));
let migrationInputs;
if (operation === 'import-accepted') {
  const inspection = JSON.parse(fs.readFileSync(path.join(__dirname, 'inspect-before-r2.json'), 'utf8'));
  const state = JSON.parse(inspection.stdout);
  if (inspection.exitCode !== 0 || !state.every(x => x.success && x.meta.rows_written === 0)
      || state[1].results.length || state[0].results.some(x =>
        !['sqlite_autoindex_d1_migrations_1', '_cf_KV', 'd1_migrations', 'sqlite_sequence'].includes(x.name))) {
    throw Error('Expected the verified new empty database');
  }
  const names = ['0001_init.sql', '0002_patch_formats.sql', '0003_firmware_releases.sql',
    '0004_announcements.sql', '0005_firmware_multi_asset.sql'];
  migrationInputs = [];
  const chunks = [];
  for (const name of names) {
    const source = path.join(root, 'app/bluetooth_flutter_Trace/cloudflare/update-service/migrations', name);
    const bytes = fs.readFileSync(source);
    migrationInputs.push({ name, sizeBytes: bytes.length,
      sha256: crypto.createHash('sha256').update(bytes).digest('hex') });
    // Keep accepted SQL intact and append the same tracking insert as Wrangler.
    chunks.push(bytes, Buffer.from(`\nINSERT INTO "d1_migrations" (name) VALUES ('${name}');\n`));
  }
  const bytes = Buffer.concat(chunks);
  const target = contained(path.join(__dirname, 'accepted-migrations.sql'));
  fs.writeFileSync(target, bytes, { flag: 'wx' });
  migrationInputs.push({ name: 'accepted-migrations.sql', sizeBytes: bytes.length,
    sha256: crypto.createHash('sha256').update(bytes).digest('hex') });
}
const env = { ...process.env };
for (const key of Object.keys(env)) {
  if (/^(CLOUDFLARE_|CF_|TRACE_|OTA_AES_KEY|GH_|GITHUB_TOKEN|NODE_OPTIONS|NODE_COMPILE_CACHE|GIT_CONFIG|GIT_INDEX_FILE)/i.test(key)) delete env[key];
}
for (const [key, relative] of Object.entries({
  TEMP: 'tmp', TMP: 'tmp', TMPDIR: 'tmp', HOME: 'home', USERPROFILE: 'home',
  APPDATA: 'appdata', LOCALAPPDATA: 'localappdata', XDG_CONFIG_HOME: 'config',
  XDG_CACHE_HOME: 'cache', XDG_DATA_HOME: 'data', npm_config_cache: 'npm', WRANGLER_LOG_PATH: 'logs'
})) {
  env[key] = contained(path.join(runtime, relative));
  fs.mkdirSync(env[key], { recursive: true });
}
Object.assign(env, { CI: '1', NODE_USE_ENV_PROXY: '1', WRANGLER_SEND_METRICS: 'false',
  WRANGLER_LOG: 'log', GIT_OPTIONAL_LOCKS: '0', GIT_TERMINAL_PROMPT: '0',
  NPM_CONFIG_UPDATE_NOTIFIER: 'false', CLOUDFLARE_API_TOKEN: token,
  CLOUDFLARE_ACCOUNT_ID: config.account_id });
let input;
if (operation === 'secrets') {
  if (!secrets.DEPLOY_TOKEN_SHA256 || !secrets.DOWNLOAD_HMAC_KEY_CURRENT) throw Error('Runtime secrets not prepared');
  input = JSON.stringify({ DEPLOY_TOKEN_SHA256: secrets.DEPLOY_TOKEN_SHA256,
    DOWNLOAD_HMAC_KEY_CURRENT: secrets.DOWNLOAD_HMAC_KEY_CURRENT });
}
const executable = path.join(root, 'app/bluetooth_flutter_Trace/cloudflare/update-service/worker/node_modules/wrangler/bin/wrangler.js');
const started = new Date().toISOString();
const result = cp.spawnSync(process.execPath, [executable, ...commands[operation]], {
  cwd: root, env, input, encoding: 'utf8', windowsHide: true, timeout: 120000,
  maxBuffer: 8 * 1024 * 1024
});
const receipt = { operation, started, finished: new Date().toISOString(), cwd: root,
  args: [executable, ...commands[operation]], exitCode: result.status, signal: result.signal,
  migrationInputs,
  error: result.error ? redact(result.error.message) : null,
  stdout: redact(result.stdout), stderr: redact(result.stderr), closed: true };
fs.writeFileSync(output, JSON.stringify(receipt, null, 2) + '\n', { flag: 'wx' });
process.stdout.write(receipt.stdout);
process.stderr.write(receipt.stderr);
process.stdout.write('\nRECEIPT=' + output + ' EXIT=' + result.status + '\n');
process.exitCode = result.status ?? 1;
