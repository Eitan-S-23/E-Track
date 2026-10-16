import fs from 'node:fs';
import path from 'node:path';
import assert from 'node:assert/strict';
import { createHash } from 'node:crypto';
import { spawnSync } from 'node:child_process';
import { fileURLToPath, pathToFileURL } from 'node:url';

const directory = path.dirname(fileURLToPath(import.meta.url));
const root = path.resolve(directory, '../../..');
const parent = path.dirname(directory);
const destination = path.join(root, 'docs/ota-exec-notes/P4-1-cloud-qualification-2026-10-15');
const { outputPath } = await import(pathToFileURL(path.join(root,
  'app/bluetooth_flutter_Trace/cloudflare/update-service/scripts/firmware-cli.mjs')));
const guard = value => outputPath(root, value);
assert.equal(fs.realpathSync.native(process.cwd()).toLowerCase(), root.toLowerCase());
const sha = value => createHash('sha256').update(value).digest('hex');
const encode = value => Buffer.from(JSON.stringify(value, null, 2) + '\n');
const credentialDirectory = path.join(root, '.cache/cf-auth-input');
const token = fs.readFileSync(path.join(credentialDirectory, 'token.txt'), 'utf8').trim();
const secrets = JSON.parse(fs.readFileSync(path.join(credentialDirectory, 'firmware-test-secrets.json'), 'utf8'));
const sensitive = [token, ...Object.values(secrets)].filter(x => typeof x === 'string' && x.length > 10);
function walk(directory) {
  guard(directory);
  return fs.readdirSync(directory, { withFileTypes: true }).flatMap(entry => {
    const target = guard(path.join(directory, entry.name));
    assert.equal(entry.isSymbolicLink(), false);
    return entry.isDirectory() ? walk(target) : [target];
  });
}
function checkedBytes(source) {
  const bytes = fs.readFileSync(guard(source));
  for (const value of sensitive) assert.equal(bytes.includes(Buffer.from(value)), false,
    'Credential value outside the private input: ' + path.relative(root, source));
  return bytes;
}
if (process.argv[2] === '--audit') {
  const output = guard(path.join(directory, 'wrapup-audit.json'));
  assert.equal(fs.existsSync(output), false);
  const temp = guard(path.join(root, '.wrangler'));
  const files = walk(temp);
  const expected = ['cache/cf.json', 'tmp/bundle-EVCykP/middleware-insertion-facade.js',
    'tmp/bundle-EVCykP/middleware-loader.entry.ts', 'tmp/dev-TLkcNY/ProxyServerWorker.js',
    'tmp/dev-TLkcNY/ProxyServerWorker.js.map'].sort();
  assert.deepEqual(files.map(p => path.relative(temp, p).replaceAll('\\', '/')).sort(), expected);
  const inventory = files.map(p => { const bytes = checkedBytes(p); return {
    path: p, sizeBytes: bytes.length, sha256: sha(bytes) }; });
  const processQuery = spawnSync('wmic', ['process', 'get', 'CommandLine,ParentProcessId,ProcessId', '/format:csv'],
    { cwd: root, encoding: 'utf8', windowsHide: true, timeout: 20000 });
  assert.equal(processQuery.status, 0);
  const ownedPids = [24672, 24220, 5092, 5596, 25324];
  const stillPresent = processQuery.stdout.split(/\r?\n/).filter(line => ownedPids.includes(Number(line.split(',').at(-1))));
  assert.deepEqual(stillPresent, []);
  const sharedIndexSha256 = sha(fs.readFileSync('D:/github/my/E-Track/.git/index'));
  assert.equal(sharedIndexSha256, '2907ee569cb8415877c8c688b3e09b5948a789d6430796eab99ae3ad43f3a3dd');
  const scanned = walk(parent);
  for (const file of scanned) checkedBytes(file);
  const acl = spawnSync('icacls', [credentialDirectory], { cwd: root, encoding: 'utf8', windowsHide: true });
  assert.equal(acl.status, 0);
  const crashDirectory = 'C:/Users/SU/AppData/Local/CrashDumps';
  const crashFiles = fs.readdirSync(crashDirectory).map(name => ({ name,
    modified: fs.statSync(path.join(crashDirectory, name)).mtime.toISOString() }));
  assert.ok(crashFiles.every(x => x.modified < '2026-10-15T00:00:00.000Z'));
  // These five files belong only to the failed, now-closed remote-proxy attempt.
  guard(temp);
  fs.rmSync(temp, { recursive: true });
  assert.equal(fs.existsSync(temp), false);
  const audit = { checkedAt: new Date().toISOString(), activeRoot: root, sharedIndexSha256,
    closedOwnedPids: ownedPids, processQueryExitCode: processQuery.status, removedDisposableFiles: inventory,
    priorShellQuotingAccident: { path: path.join(root, '[k'), bytes: 0, removed: !fs.existsSync(path.join(root, '[k')),
      cause: 'cmd interpreted an inline JavaScript arrow as redirection; the empty file was removed with apply_patch' },
    outputs: [directory, path.join(parent, 'qualification-fixture'), path.join(root, '.cache/logs'), destination],
    credentialScan: { files: scanned.length, suppliedOrGeneratedCredentialValuesOutsidePrivateInput: 0 },
    retainedCredentialInputs: { directory: credentialDirectory,
      reason: 'Authorized qualification is still open; retain the user-corrected input to avoid another copy/paste request.',
      exportedToCi: false, acl: acl.stdout.trim() },
    externalReadOnlyCrashCheck: { directory: crashDirectory, files: crashFiles, newCrashDumpObserved: false },
    externalWriteAssessment: 'No new outside-project write observed in the controlled paths and crash checks; no PowerShell or system installation was invoked. Historical P41-AUDIT-01 is unchanged.' };
  fs.writeFileSync(output, encode(audit), { flag: 'wx' });
  console.log(JSON.stringify({ audit: output, removedFiles: inventory.length, credentialScanFiles: scanned.length,
    ownedProcessesClosed: true, sharedIndexUnchanged: true }));
} else {
  const sources = new Map();
  const add = (name, source) => { assert.equal(sources.has(name), false); sources.set(name, guard(source)); };
  for (const name of ['resources-created.json', 'd1-create-request.json', 'd1-create-response.json',
    'kv-create-request.json', 'kv-create-response.json', 'r2-create-request.json', 'r2-create-response.json',
    'migrate.json', 'inspect-before.json', 'inspect-before-r2.json', 'accepted-migrations.sql', 'import-accepted.json',
    'inspect-after.json', 'schema-comparison.json', 'deploy.json', 'secrets.json', 'remote-preflight.json',
    'remote-api-negative.json', 'remote-protected-after.json', 'qualification-metadata.json', 'wrapup-audit.json',
    'wrangler.json', 'wrangler-operation.cjs', 'verify-schema.cjs', 'qualify-remote.mjs', 'archive-current.mjs']) {
    add('operations/' + name, path.join(directory, name));
  }
  for (const name of ['resource-d1-request.json', 'resource-d1-created.json']) add('earlier-failure/' + name, path.join(parent, name));
  for (const name of ['d1-inventory.json', 'bindings.json']) add('protected-before/' + name,
    path.join(root, '.cache/cf-readonly-20261015-r1', name));
  for (const name of ['run.json', 'jobs.json', 'artifacts.json', 'logs.zip', 'worker-bundle.zip',
    'development-fixtures.zip', 'selected-step-logs.json', 'verification-summary.json', 'source-tree-binding.json',
    'independent-review.json']) add('ci/' + name, path.join(parent, 'ci', name));
  for (const label of ['p41-qualification-extract', 'p41-cf-qualification-preflight',
    'p41-cf-qualification-api-negative', 'p41-cf-protected-after']) {
    for (const suffix of ['json', 'stdout.txt', 'stderr.txt']) add('commands/' + label + '.' + suffix,
      path.join(root, '.cache/logs', label + '.' + suffix));
  }
  add('commands/run.cjs', path.join(root, '.cache/run.cjs'));
  add('.gitattributes', path.join(destination, '.gitattributes'));
  const payloads = [...sources].map(([name, source]) => ({ name, source, bytes: checkedBytes(source),
    target: guard(path.join(destination, name)) }));
  for (const item of payloads) if (item.name !== '.gitattributes') assert.equal(fs.existsSync(item.target), false);
  const inventory = payloads.map(x => ({ path: x.name, source: path.relative(root, x.source).replaceAll('\\', '/'),
    sizeBytes: x.bytes.length, sha256: sha(x.bytes) }));
  const planSha256 = sha(encode(inventory));
  const inventoryPath = guard(path.join(destination, 'inventory.json'));
  assert.equal(fs.existsSync(inventoryPath), false);
  if (process.argv[2] === '--apply') {
    assert.equal(process.argv[3], planSha256);
    for (const item of payloads) {
      if (item.name === '.gitattributes') continue;
      fs.mkdirSync(path.dirname(item.target), { recursive: true });
      guard(item.target);
      fs.writeFileSync(item.target, item.bytes, { flag: 'wx' });
      assert.equal(sha(fs.readFileSync(item.target)), sha(item.bytes));
    }
    fs.writeFileSync(inventoryPath, encode({ purpose: 'Isolated synthetic qualification, not formal rehearsal or independent acceptance',
      testedCodeCommit: 'cd4f2e4d651fb7eafe8253ce854b90242cede4d9', files: inventory }), { flag: 'wx' });
    console.log(JSON.stringify({ archivedFiles: payloads.length + 1, inventorySha256: sha(fs.readFileSync(inventoryPath)), planSha256 }));
  } else {
    assert.equal(process.argv[2], '--plan');
    console.log(JSON.stringify({ root, files: payloads.length + 1, bytes: payloads.reduce((sum, x) => sum + x.bytes.length, 0),
      planSha256, targets: [...payloads.map(x => x.target), inventoryPath] }, null, 2));
  }
}
