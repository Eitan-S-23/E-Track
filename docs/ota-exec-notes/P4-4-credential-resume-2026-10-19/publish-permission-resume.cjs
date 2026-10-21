const io = require('./io.cjs');
const { fs, path, assert, sha256 } = io;
const destination = io.guard(io.worktree + '/docs/ota-exec-notes/P4-4-credential-resume-2026-10-19');
const inventoryPath = io.guard(path.join(destination, 'inventory.json'));
const env = io.environment();
const cloud = io.cloudInputs();
const githubToken = io.githubToken(env);
const secrets = new Set([cloud.provisioning, cloud.ci, githubToken,
  Buffer.from('Eitan-S-23:' + githubToken).toString('base64')]);
const protectedRoot = io.project + '/.cache/p41-dev-20261015/.cache/cf-auth-input/';
for (const file of [protectedRoot + 'firmware-test-secrets.json', protectedRoot + 'p41-rehearsal-ota-key.json',
  io.worktree + '/.cache/p44/private/production-secrets.json']) {
  for (const [key, value] of Object.entries(io.readJson(file))) {
    if (typeof value === 'string' && /key|token|hmac/i.test(key) && !/path|source|name|version/i.test(key) && value.length >= 16) secrets.add(value);
  }
}
const sources = [
  'verify-permissions-02.cjs', 'verify-permissions-02.json',
  'verify-permissions-03.cjs', 'verify-permissions-03.json',
  'refresh-admission.cjs', 'refresh-admission-04.json',
  'create-s3-after-permission-update.cjs', 'create-s3-production-02.json',
  'create-s3-production-02-reservation.json', 'io.cjs', 'curl-io.cjs',
  'publish-permission-resume.cjs',
];
for (const dir of ['curl-refresh-admission-04', 'curl-create-s3-production-02-precheck']) {
  for (const file of fs.readdirSync(io.output(dir)).sort()) sources.push(dir + '/' + file);
}
sources.push('private/create-s3-production-02-response.json');
assert.equal(io.readJson(io.output('create-s3-production-02.json')).created, false);
const denied = io.readJson(io.output('private/create-s3-production-02-response.json'));
assert.equal(denied.success, false);
assert.ok(!denied.result?.id && !denied.result?.value, 'Only the confirmed credential-free denial may be copied');
function scan(bytes) {
  for (const value of secrets) assert.ok(!bytes.includes(Buffer.from(value)), 'Known credential in publication');
  assert.ok(!/gh[pousr]_[A-Za-z0-9]{30,}|github_pat_[A-Za-z0-9_]{30,}/.test(bytes.toString('utf8')));
}
assert.ok(!fs.existsSync(inventoryPath), 'Preserve existing inventory');
const prepared = sources.map(name => {
  const source = io.output(name);
  const relative = name.startsWith('private/') ? 'account-create-denial.json' : name;
  const target = io.guard(path.join(destination, relative));
  assert.ok(!fs.existsSync(target), 'Preserve prior evidence');
  const original = fs.readFileSync(source);
  scan(original);
  let text = original.toString('utf8');
  assert.ok(Buffer.from(text).equals(original));
  const changes = [];
  for (const [kind, regex, replacement] of [
    ['account-identifier', new RegExp(cloud.account, 'g'), '[REDACTED_ACCOUNT]'],
    ['cookie-header', /^set-cookie:[^\r\n]*/gim, 'set-cookie: [REDACTED_COOKIE]'],
    ['email-address', /[A-Za-z0-9.!#$%&'*+/=?^_`{|}~-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}/g, '[REDACTED_EMAIL]'],
    ['url-query', /(https?:\/\/[^\s"'<>?\\]+)\?[^\s"'<>\\]+/g, '$1?[REDACTED_QUERY]'],
  ]) {
    const count = [...text.matchAll(regex)].length;
    if (count) { text = text.replace(regex, replacement); changes.push({ kind, count }); }
  }
  const bytes = Buffer.from(text); scan(bytes);
  return { target, bytes, entry: { path: relative, source: path.relative(io.project, source).replaceAll('\\', '/'),
    originalSizeBytes: original.length, originalSha256: sha256(original), sizeBytes: bytes.length,
    sha256: sha256(bytes), byteExact: original.equals(bytes), transformations: changes } };
});
for (const item of prepared) {
  io.guard(path.dirname(item.target)); fs.mkdirSync(path.dirname(item.target), { recursive: true });
  io.guard(item.target); fs.writeFileSync(item.target, item.bytes, { flag: 'wx' });
  assert.ok(fs.readFileSync(item.target).equals(item.bytes));
}
io.writeJson(inventoryPath, { createdAt: new Date().toISOString(), formalAcceptance: 'NOT_RUN',
  baselineCommit: '231932fdd554af1504c1465117d1470cf4a0dc22',
  scope: 'Permission-update continuation: bounded reads and one explicitly denied account-token POST; no pair/secret write',
  secretScan: 'Known protected values and GitHub credential patterns', entries: prepared.map(x => x.entry),
  limits: 'Preparation originals/projections, not a formal bundle; original bytes and prior failures remain unchanged' });
process.stdout.write(JSON.stringify({ inventory: inventoryPath, files: prepared.length,
  byteExact: prepared.filter(x => x.entry.byteExact).length,
  bytes: prepared.reduce((sum, x) => sum + x.bytes.length, 0), knownSecretScanPassed: true }) + '\n');
