// Fixed-input snapshot adapter, reusing the prior readiness archive conventions.
const fs = require('node:fs');
const path = require('node:path');
const crypto = require('node:crypto');
const assert = require('node:assert/strict');
const root = fs.realpathSync.native(path.resolve(__dirname, '../..'));
assert.equal(fs.realpathSync.native(process.cwd()), root);
assert.equal(root.toLowerCase(), 'd:\\github\\my\\e-track\\.cache\\p41-dev-20261015');
const dest = 'docs/ota-exec-notes/P4-1-protected-setup-2026-10-16';
const sha = data => crypto.createHash('sha256').update(data).digest('hex');
const encode = value => Buffer.from(JSON.stringify(value, null, 2) + '\n');
function guard(value) {
  const target = path.resolve(root, value);
  let parent = target;
  const rest = [];
  while (!fs.existsSync(parent)) { rest.unshift(path.basename(parent)); parent = path.dirname(parent); }
  const actual = path.resolve(fs.realpathSync.native(parent), ...rest);
  const relative = path.relative(root, actual);
  assert(!path.isAbsolute(relative) && relative !== '..' && !relative.startsWith('..' + path.sep));
  for (let current = parent; current !== path.dirname(current); current = path.dirname(current)) {
    assert(!fs.lstatSync(current).isSymbolicLink());
    assert.equal(fs.realpathSync.native(current).toLowerCase(), current.toLowerCase());
  }
  return actual;
}
const read = name => fs.readFileSync(guard(name));
const payloads = new Map();
function add(name, bytes, source, kind = 'BYTE_IDENTICAL_COPY') {
  assert(!payloads.has(name));
  payloads.set(name, { bytes, source, kind });
}
const prefix = '.cache/p41-setup-20261016/';
for (const name of ['create-account-plan.json', 'create-account.json', 'github-configuration.json']) {
  add('operations/' + name, read(prefix + name), prefix + name);
}
const raw = read(prefix + 'read-only.json');
const safe = JSON.parse(raw);
safe.cloudflareAccounts.accounts = safe.cloudflareAccounts.accounts.map(account => ({
  ...account, id: '[REDACTED_EXISTING_ACCOUNT_ID]', name: '[REDACTED_EXISTING_ACCOUNT_NAME]'
}));
add('operations/read-only.sanitized.json', encode({
  evidenceKind: 'SANITIZED_DERIVATIVE',
  source: { path: prefix + 'read-only.json', sizeBytes: raw.length, sha256: sha(raw), archived: false },
  redactedFields: ['cloudflareAccounts.accounts[*].id', 'cloudflareAccounts.accounts[*].name'],
  observation: safe
}), prefix + 'read-only.json', 'SANITIZED_DERIVATIVE');
for (const name of ['cloudflare-account-setup.md', 'cloudflare-account-owned-tokens.md',
  'cloudflare-permissions.md', 'cloudflare-r2-start.md', 'github-environments.md',
  'github-branch-policies.md', 'github-secrets.md']) {
  add('references/' + name, read(prefix + name), prefix + name);
}
for (const name of ['probe-setup.cjs', 'create-account.cjs', 'configure-github.cjs', 'archive-setup.cjs']) {
  add('helpers/' + name, read(prefix + name), prefix + name);
}
add('helpers/run.cjs', read('.cache/run.cjs'), '.cache/run.cjs');
const label = 'p41-setup-governance';
const receipt = JSON.parse(read('.cache/logs/' + label + '.json'));
assert.equal(receipt.closed, true);
assert.equal(receipt.exitCode, 0);
const stdout = read('.cache/logs/' + label + '.stdout.txt');
const stderr = read('.cache/logs/' + label + '.stderr.txt');
assert.match(Buffer.concat([stdout, stderr]).toString(), /Ran 23 tests/);
for (const suffix of ['.json', '.stdout.txt', '.stderr.txt']) {
  add('commands/' + label + suffix, read('.cache/logs/' + label + suffix), '.cache/logs/' + label + suffix);
}
const existingSecrets = JSON.parse(read('.cache/cf-auth-input/firmware-test-secrets.json'));
const key = JSON.parse(read('.cache/cf-auth-input/p41-rehearsal-ota-key.json'));
const secrets = [read('.cache/cf-auth-input/token.txt').toString().trim(),
  existingSecrets.TRACE_DEPLOY_TOKEN, existingSecrets.DOWNLOAD_HMAC_KEY_CURRENT,
  key.keyHex, key.keyHex.toUpperCase(), Buffer.from(key.keyHex, 'hex').toString('base64')];
const sensitive = secrets.map(value => Buffer.from(value));
sensitive.push(Buffer.from(key.keyHex, 'hex'));
const input = JSON.parse(read('.cache/cf-auth-input/p41-isolated-account-input.json'));
if (input.api_token) sensitive.push(Buffer.from(input.api_token));
const credentialPattern = /\b(?:gh[pousr]_[A-Za-z0-9]{20,}|github_pat_[A-Za-z0-9_]{30,}|cfat_[A-Za-z0-9_-]{20,})\b/;
const inventory = [];
for (const name of ['.gitattributes', 'README.md']) {
  const bytes = read(dest + '/' + name);
  inventory.push({ path: name, sizeBytes: bytes.length, sha256: sha(bytes), kind: 'AUTHORED_RECORD' });
}
for (const [name, { bytes, source, kind }] of payloads) {
  assert(!credentialPattern.test(bytes.toString()), 'Credential pattern in public output: ' + name);
  for (const value of sensitive) assert(!bytes.includes(value), 'Sensitive value in public output: ' + name);
  inventory.push({ path: name, sizeBytes: bytes.length, sha256: sha(bytes), source, kind });
}
add('inventory.json', encode({ schemaVersion: 1, scope: 'AUTHORIZED_SETUP_NOT_ACCEPTANCE',
  startingCommit: 'fefcb3f2b493527e14affa236207a8d5f4deb682', files: inventory }), 'Generated inventory');
const targets = [...payloads.keys()].map(name => guard(dest + '/' + name));
assert(targets.every(target => !fs.existsSync(target)), 'Refusing to overwrite retained observations');
const planSha256 = sha(encode(targets));
console.log(JSON.stringify({ preflight: 'PASS', targets, planSha256, totalFiles: targets.length + 2 }));
if (process.argv.includes('--apply')) {
  const index = process.argv.indexOf('--expected-plan-sha');
  assert(index !== -1);
  assert.equal(process.argv[index + 1], planSha256);
  for (const [name, { bytes }] of payloads) {
    const target = guard(dest + '/' + name);
    fs.mkdirSync(path.dirname(target), { recursive: true });
    fs.writeFileSync(target, bytes, { flag: 'wx' });
    assert.deepEqual(read(target), bytes);
  }
  console.log(JSON.stringify({ archivedFiles: targets.length + 2,
    inventorySha256: sha(payloads.get('inventory.json').bytes), privateCredentialMatches: 0 }));
}
