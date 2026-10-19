const io = require('./io.cjs');
const { spawnSync } = require('node:child_process');
const { fs, path, assert, sha256 } = io;
const mode = process.argv[2];
assert.ok(['plan', 'publish', 'verify'].includes(mode));
const destination = io.guard(io.worktree + '/docs/ota-exec-notes/P4-4-root-review-2026-10-19');
const planPath = io.output('publication-plan-01.json');
const inventoryPath = io.guard(path.join(destination, 'raw-output-inventory.json'));
const env = io.environment();
const cloud = io.cloudInputs();
const ghToken = io.githubToken(env);
const secrets = new Set([cloud.provisioning, cloud.ci, ghToken,
  Buffer.from('Eitan-S-23:' + ghToken).toString('base64')]);
const protectedRoot = io.project + '/.cache/p41-dev-20261015/.cache/cf-auth-input/';
for (const file of [protectedRoot + 'firmware-test-secrets.json', protectedRoot + 'p41-rehearsal-ota-key.json',
  io.worktree + '/.cache/p44/private/production-secrets.json']) {
  for (const [key, value] of Object.entries(io.readJson(file))) {
    if (typeof value === 'string' && /key|token|hmac/i.test(key) &&
        !/path|source|name|version/i.test(key) && value.length >= 16) secrets.add(value);
  }
}
function scan(bytes) {
  for (const value of secrets) assert.ok(!bytes.includes(Buffer.from(value)), 'Known credential in selected evidence');
  assert.ok(!/gh[pousr]_[A-Za-z0-9]{30,}|github_pat_[A-Za-z0-9_]{30,}/.test(bytes.toString('utf8')),
    'Credential-shaped value in selected evidence');
}
function sanitize(source, bytes) {
  scan(bytes);
  const transformations = [];
  if (/\.(?:cjs|mjs|js|zip)$/i.test(source)) {
    assert.ok(!bytes.includes(Buffer.from(cloud.account)), 'Account literal in immutable code/archive');
    return { bytes, transformations };
  }
  let text = bytes.toString('utf8');
  assert.ok(Buffer.from(text).equals(bytes), 'Unexpected binary evidence format');
  const rules = [
    ['account-identifier', new RegExp(cloud.account, 'g'), '[REDACTED_ACCOUNT]'],
    ['set-cookie-header', /^set-cookie:[^\r\n]*/gim, 'set-cookie: [REDACTED_COOKIE]'],
    ['email-address', /[A-Za-z0-9.!#$%&'*+/=?^_`{|}~-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}/g, '[REDACTED_EMAIL]'],
    ['url-query', /(https?:\/\/[^\s"'<>?\\]+)\?[^\s"'<>\\]+/g, '$1?[REDACTED_QUERY]'],
  ];
  for (const [kind, pattern, replacement] of rules) {
    const count = [...text.matchAll(pattern)].length;
    if (count) { text = text.replace(pattern, replacement); transformations.push({ kind, count }); }
  }
  const output = Buffer.from(text); scan(output);
  return { bytes: output, transformations };
}
function selected() {
  const pairs = [];
  function add(source, relative) {
    const full = io.guard(source); assert.ok(fs.lstatSync(full).isFile());
    const target = io.guard(path.join(destination, relative));
    pairs.push({ source: full, target, path: relative.replaceAll('\\', '/') });
  }
  const review = io.project + '/.cache/p44-root-review-546d8b3-20261019';
  for (const name of fs.readdirSync(review).sort()) add(path.join(review, name), 'review/' + name);
  for (const name of fs.readdirSync(io.base).sort()) {
    if (name === path.basename(planPath) || name.startsWith('delivery-') && name !== 'delivery-review.json') continue;
    if (!/\.(?:cjs|json|zip|txt)$/.test(name)) continue;
    add(path.join(io.base, name), 'preparation/' + name);
  }
  const directories = ['deploy/staging', 'deploy/production', 'checks', 'verification-inputs',
    ...fs.readdirSync(io.base).filter(name => /^curl-/.test(name) && fs.lstatSync(path.join(io.base, name)).isDirectory())];
  for (const relative of directories) {
    const directory = io.guard(path.join(io.base, relative));
    if (!fs.existsSync(directory)) continue;
    for (const name of fs.readdirSync(directory).sort()) {
      const source = path.join(directory, name);
      if (fs.lstatSync(source).isDirectory()) continue;
      add(source, 'preparation/' + relative + '/' + name);
    }
  }
  add(io.worktree + '/.cache/p44-run.cjs', 'helpers/p44-run.cjs');
  for (const label of ['root-record-check-01', 'root-record-diff-01']) {
    for (const extension of ['log', 'json']) {
      const name = label + '.' + extension;
      add(io.worktree + '/.cache/p44/logs/' + name, 'preparation/checks/' + name);
    }
  }
  assert.equal(new Set(pairs.map(x => x.path)).size, pairs.length);
  return pairs.sort((a, b) => a.path.localeCompare(b.path, 'en'));
}
function content(entry) {
  const original = fs.readFileSync(entry.source);
  const projected = sanitize(entry.source, original);
  if (/\.zip$/i.test(entry.source)) {
    const listing = spawnSync('tar', ['-tf', entry.source], { cwd: io.project, env, encoding: 'utf8', windowsHide: true });
    assert.equal(listing.status, 0);
    for (const member of listing.stdout.trim().split(/\r?\n/).filter(x => x && !x.endsWith('/'))) {
      const result = spawnSync('tar', ['-xOf', entry.source, member], { cwd: io.project, env,
        windowsHide: true, maxBuffer: 8 * 1024 * 1024 });
      assert.equal(result.status, 0); scan(result.stdout);
      assert.ok(!result.stdout.includes(Buffer.from(cloud.account)), 'Account identifier inside archive');
    }
  }
  return { original, ...projected };
}
function summarize(entry, data) {
  return { path: entry.path, source: path.relative(io.project, entry.source).replaceAll('\\', '/'),
    originalSizeBytes: data.original.length, originalSha256: sha256(data.original),
    sizeBytes: data.bytes.length, sha256: sha256(data.bytes), transformations: data.transformations,
    byteExact: data.original.equals(data.bytes) };
}
if (mode === 'plan') {
  assert.ok(!fs.existsSync(planPath) && !fs.existsSync(inventoryPath), 'Preserve prior plan/inventory');
  const entries = selected().map(entry => {
    assert.ok(!fs.existsSync(entry.target), 'Never overwrite published evidence');
    return summarize(entry, content(entry));
  });
  io.writeJson(planPath, { createdAt: new Date().toISOString(), destination, entries,
    excludes: ['private inputs/configs', 'cache/home/tmp directories', 'redundant dry-run trees', 'source-map extraction tree'],
    note: 'Pre-acceptance originals/projections, not a frozen formal bundle. No original is modified.' });
  process.stdout.write(JSON.stringify({ plan: planPath, files: entries.length,
    projected: entries.filter(x => !x.byteExact).length, bytes: entries.reduce((sum, x) => sum + x.sizeBytes, 0) }) + '\n');
} else if (mode === 'publish') {
  assert.ok(!fs.existsSync(inventoryPath), 'Never overwrite published inventory');
  const plan = io.readJson(planPath);
  const prepared = plan.entries.map(entry => {
    const source = io.guard(path.join(io.project, entry.source));
    const target = io.guard(path.join(destination, entry.path));
    assert.ok(!fs.existsSync(target), 'Never overwrite evidence');
    const data = content({ source });
    assert.deepEqual(summarize({ path: entry.path, source }, data), entry, 'Source changed after publication preflight');
    return { target, bytes: data.bytes };
  });
  for (const item of prepared) {
    io.guard(path.dirname(item.target)); fs.mkdirSync(path.dirname(item.target), { recursive: true });
    io.guard(item.target); fs.writeFileSync(item.target, item.bytes, { flag: 'wx' });
    assert.ok(fs.readFileSync(item.target).equals(item.bytes));
  }
  io.writeJson(inventoryPath, { ...plan, publishedAt: new Date().toISOString(),
    sourceCommit: 'b56534d7b6c993c0795010d0404fb8a81f7eeb9d',
    implementationEvidenceCommit: '15be25e593405396d8db8fb0011fc62e42d6d27d',
    secretScan: 'Known protected values and GitHub credential patterns, including uncompressed ZIP members',
    formalAcceptance: 'NOT_RUN', scope: 'Independent offline review and authorized configuration preparation' });
  process.stdout.write(JSON.stringify({ inventory: inventoryPath, files: prepared.length }) + '\n');
} else {
  const inventory = io.readJson(inventoryPath);
  for (const entry of inventory.entries) {
    const original = fs.readFileSync(io.guard(path.join(io.project, entry.source)));
    const published = fs.readFileSync(io.guard(path.join(destination, entry.path)));
    assert.equal(original.length, entry.originalSizeBytes); assert.equal(sha256(original), entry.originalSha256);
    assert.equal(published.length, entry.sizeBytes); assert.equal(sha256(published), entry.sha256); scan(published);
  }
  process.stdout.write(JSON.stringify({ verifiedFiles: inventory.entries.length,
    originalHashesVerified: true, publishedHashesVerified: true, knownSecretScanPassed: true }) + '\n');
}
