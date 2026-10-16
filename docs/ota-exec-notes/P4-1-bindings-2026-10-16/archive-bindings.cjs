// Fixed-input archive, reusing the prior archive-setup guard and native tar.
const fs = require('node:fs');
const path = require('node:path');
const cp = require('node:child_process');
const crypto = require('node:crypto');
const assert = require('node:assert/strict');
const root = fs.realpathSync.native(path.resolve(__dirname, '../..'));
assert.equal(fs.realpathSync.native(process.cwd()), root);
assert.equal(root.toLowerCase(), 'd:\\github\\my\\e-track\\.cache\\p41-dev-20261015');
const destination = 'docs/ota-exec-notes/P4-1-bindings-2026-10-16';
const commit = 'c715ec6b00f8d9b06a820213da72421694b1e44c';
const runId = 38859822756;
const sha = bytes => crypto.createHash('sha256').update(bytes).digest('hex');
const encode = value => Buffer.from(JSON.stringify(value, null, 2) + '\n');
function guard(value) {
  const target = path.resolve(root, value);
  let parent = target;
  while (!fs.existsSync(parent)) parent = path.dirname(parent);
  const actual = path.resolve(fs.realpathSync.native(parent), path.relative(parent, target));
  const relative = path.relative(root, actual);
  assert(!path.isAbsolute(relative) && relative !== '..' && !relative.startsWith('..' + path.sep));
  for (let current = parent; current !== path.dirname(current); current = path.dirname(current)) {
    assert(!fs.lstatSync(current).isSymbolicLink());
    assert.equal(fs.realpathSync.native(current).toLowerCase(), current.toLowerCase());
  }
  return actual;
}
const read = name => fs.readFileSync(guard(name));
const json = name => JSON.parse(read(name));
const payloads = new Map();
function add(name, bytes, source, kind = 'BYTE_IDENTICAL_COPY') {
  assert(!payloads.has(name));
  payloads.set(name, { bytes, source, kind });
}
const privateConfig = json('.cache/cf-auth-input/firmware-test-secrets.json');
const key = json('.cache/cf-auth-input/p41-rehearsal-ota-key.json');
const sensitive = [read('.cache/cf-auth-input/token.txt').toString().trim(),
  read('.cache/cf-auth-input/p41-ci-token.txt').toString().trim(),
  privateConfig.TRACE_DEPLOY_TOKEN, privateConfig.DOWNLOAD_HMAC_KEY_CURRENT,
  key.keyHex, key.keyHex.toUpperCase(), Buffer.from(key.keyHex, 'hex').toString('base64')].map(value => Buffer.from(value));
sensitive.push(Buffer.from(key.keyHex, 'hex'));
function secretCheck(bytes, name) {
  assert(!/\b(?:gh[pousr]_[A-Za-z0-9]{20,}|github_pat_[A-Za-z0-9_]{30,}|cfat_[A-Za-z0-9_-]{20,})\b/.test(bytes.toString()), name);
  for (const value of sensitive) assert(!bytes.includes(value), 'Private credential in ' + name);
}
const github = '.cache/github/p41-approved-';
for (const name of ['run-1.json', 'jobs-1.json', 'pending-1.json', 'artifacts-1.json', 'reviews-1.json', 'logs-1.zip', 'bindings-1.zip']) {
  add('github/' + name, read(github + name), github + name);
}
const run = json(github + 'run-1.json');
assert.equal(run.id, runId); assert.equal(run.run_attempt, 1);
assert.equal(run.head_sha, commit); assert.equal(run.event, 'workflow_dispatch');
assert.equal(run.status, 'completed'); assert.equal(run.conclusion, 'success');
assert.equal(run.head_branch, 'dev/p4-1/unattended-20261015');
const jobs = json(github + 'jobs-1.json');
assert.equal(jobs.total_count, 5); assert.equal(jobs.jobs.length, 5);
for (const job of jobs.jobs) {
  assert.equal(job.run_id, runId); assert.equal(job.run_attempt, 1); assert.equal(job.head_sha, commit);
  assert.equal(job.status, 'completed');
  assert.equal(job.conclusion, [116839829129, 116839829282].includes(job.id) ? 'skipped' : 'success');
}
assert.deepEqual(json(github + 'pending-1.json'), []);
const approvals = json(github + 'reviews-1.json');
assert.equal(approvals.length, 1);
assert.equal(approvals[0].state, 'approved'); assert.equal(approvals[0].user.login, 'Eitan-S-23');
assert.equal(approvals[0].environments.length, 1);
assert.equal(approvals[0].environments[0].name, 'firmware-rehearsal');
const artifact = json(github + 'artifacts-1.json').artifacts.find(item => item.id === 12029386620);
assert.equal(artifact.name, 'p41-bindings-38859822756-1');
assert.equal(artifact.workflow_run.id, runId); assert.equal(artifact.workflow_run.head_sha, commit);
assert.equal(artifact.size_in_bytes, read(github + 'bindings-1.zip').length);
assert.equal(artifact.digest, 'sha256:' + sha(read(github + 'bindings-1.zip')));
const tar = args => cp.execFileSync('tar.exe', args, { cwd: root, windowsHide: true,
  timeout: 30000, maxBuffer: 32 * 1024 * 1024 });
const members = [];
const zipMembers = new Map();
for (const archive of ['logs-1.zip', 'bindings-1.zip']) {
  const source = guard(github + archive);
  const names = tar(['-tf', source]).toString().trim().split(/\r?\n/);
  assert.equal(new Set(names).size, names.length);
  const contents = new Map();
  for (const name of names) {
    assert(!name.split('/').includes('..') && !path.isAbsolute(name));
    assert.notEqual(path.basename(name).toLowerCase(), 'private-key.h');
    const bytes = tar(['-xOf', source, name]);
    secretCheck(bytes, archive + '!' + name);
    contents.set(name, bytes);
    members.push({ archive: 'github/' + archive, member: name, sizeBytes: bytes.length, sha256: sha(bytes) });
  }
  zipMembers.set(archive, contents);
}
assert.deepEqual([...zipMembers.get('bindings-1.zip').keys()], ['result.json']);
const resultBytes = zipMembers.get('bindings-1.zip').get('result.json');
const result = JSON.parse(resultBytes);
assert.equal(result.ok, true); assert.equal(result.scope, 'RUNTIME_BINDING_QUALIFICATION');
assert.equal(result.commitSha, commit); assert.equal(result.runId, String(runId)); assert.equal(result.runAttempt, '1');
assert.equal(result.workerBindingsMatched, true);
assert.equal(result.canonicalRehearsal, 'NOT_RUN'); assert.equal(result.independentAcceptance, 'NOT_RUN');
assert.equal(result.businessMutations, 'NONE_REQUESTED');
assert.equal(result.controlPlane, 'WRANGLER_REMOTE_PREVIEW_SESSION');
const fixture = read(result.fixturePath);
assert.equal(result.fixtureSha256, sha(fixture));
const expectedAssets = JSON.parse(fixture).assets;
assert.equal(result.assets.length, 3);
for (const [index, asset] of result.assets.entries()) {
  assert.equal(asset.ok, true);
  for (const field of ['kind', 'fileName', 'r2Key', 'sha256', 'sizeBytes']) assert.equal(asset[field], expectedAssets[index][field]);
}
assert.deepEqual(result.database.before, result.database.after);
assert.deepEqual(result.database.before.counts, {
  firmware_releases: 1, firmware_releases_legacy: 0, firmware_release_assets: 3, firmware_channels: 2, audit_logs: 1
});
assert.equal(result.database.before.channels.length, 2);
assert(result.database.before.channels.every(channel => channel.current_release_id === null
  && channel.legacy_current_release_id === null && channel.revision === 0));
const logs = zipMembers.get('logs-1.zip');
function log(fragment) {
  const found = [...logs].filter(([name]) => name.includes(fragment));
  assert.equal(found.length, 1, 'Ambiguous log fragment: ' + fragment);
  return found[0][1].toString().replace(/\x1b\[[0-9;]*[A-Za-z]/g, '');
}
const tooling = log('4_Release tooling');
const counts = {
  hostAndNative: [...tooling.matchAll(/\bTests\s+(\d+) passed/g)].map(match => Number(match[1])),
  workflowAndBytes: [...tooling.matchAll(/\u2139 tests (\d+)/g)].map(match => Number(match[1])),
  packageAndGolden: [...tooling.matchAll(/Ran (\d+) tests/g)].map(match => Number(match[1]))
};
assert.deepEqual(counts, { hostAndNative: [34, 134, 156], workflowAndBytes: [57, 22], packageAndGolden: [8, 9] });
const diagnostics = {};
for (const [name, fragment] of [['ordinaryGcc', '/11_Build firmware.txt'], ['developmentKeyGcc', '/19_Exercise the shared'],
  ['vendor', '/12_Build the existing vendor']]) {
  const content = log(fragment);
  diagnostics[name] = { warnings: [...content.matchAll(/warning:/g)].length, errors: [...content.matchAll(/error:/g)].length };
  assert.equal(diagnostics[name].errors, 0);
  assert.equal(diagnostics[name].warnings, name === 'vendor' ? 6 : 640);
}
assert(log('/20_Check development key cleanup').includes('{"privateBuildKeyAbsent":true}'));
assert(log('/6_Read existing objects').includes('"scope":"RUNTIME_BINDING_QUALIFICATION"'));
const successfulConfiguration = json('.cache/p41-approved-20261016/github-register-retry.json');
assert(successfulConfiguration.closed && successfulConfiguration.ok);
assert.equal(successfulConfiguration.secretUploads.length, 1);
assert.equal(successfulConfiguration.secretUploads[0].exitCode, 0);
for (const name of ['github-register.json', 'github-register-retry.json', 'configure-register.cjs']) {
  add('configuration/' + name, read('.cache/p41-approved-20261016/' + name), '.cache/p41-approved-20261016/' + name);
}
add('configuration/github-bindings.json', read('.cache/p41-existing-account-20261016/github-bindings.json'),
  '.cache/p41-existing-account-20261016/github-bindings.json');
add('archive-bindings.cjs', read('.cache/p41-approved-20261016/archive-bindings.cjs'), '.cache/p41-approved-20261016/archive-bindings.cjs');
add('result.json', resultBytes, 'github/bindings-1.zip!result.json');
add('artifact-members.json', encode(members), 'Derived native tar ZIP inventory', 'DERIVED');
add('inspection.json', encode({ scope: 'DEVELOPMENT_QUALIFICATION_NOT_ACCEPTANCE', commit, runId, runAttempt: 1,
  ok: true, runtimeBindingQualification: 'PASS', canonicalRehearsal: 'NOT_RUN', realKeyBuild: 'NOT_RUN',
  productionZeroEffectCampaign: 'NOT_RUN', independentAcceptance: 'NOT_RUN', counts, diagnostics,
  countPolicy: 'Separate suites; aggregate and step duplicates are not added together',
  resultSha256: sha(resultBytes), artifactDigestMatched: true, allThreeExistingAssetsMatched: true,
  d1CountsAndChannelsUnchanged: true, protectedApprovalObserved: true, pendingApprovals: 0,
  lifecycle: 'Callback completed, shared adapter returned, job post-steps completed; remote preview state not inventoried',
  businessMutations: result.businessMutations, controlPlane: result.controlPlane,
  registrationSecretMetadataPresent: true, configurationRetry: 'One public-key GET EOF before upload; original retained',
  productionAndRehearsalSkipped: true, privateCredentialMatches: 0 }), 'Derived original-byte and log checks', 'DERIVED');
const inventory = [];
for (const name of ['.gitattributes', 'README.md']) {
  const bytes = read(destination + '/' + name); secretCheck(bytes, name);
  inventory.push({ path: name, sizeBytes: bytes.length, sha256: sha(bytes), kind: 'AUTHORED_RECORD' });
}
for (const [name, { bytes, source, kind }] of payloads) {
  secretCheck(bytes, name);
  inventory.push({ path: name, sizeBytes: bytes.length, sha256: sha(bytes), source, kind });
}
add('inventory.json', encode({ schemaVersion: 1, testedCommit: commit, files: inventory }), 'Generated inventory');
const targets = [...payloads.keys()].map(name => guard(destination + '/' + name));
assert(targets.every(target => !fs.existsSync(target)), 'Refusing to overwrite prior evidence');
const planSha256 = sha(encode(targets));
console.log(JSON.stringify({ preflight: 'PASS', targets, planSha256, counts, diagnostics, totalFiles: targets.length + 2 }));
if (process.argv.includes('--apply')) {
  const position = process.argv.indexOf('--expected-plan-sha');
  assert(position !== -1); assert.equal(process.argv[position + 1], planSha256);
  for (const [name, { bytes }] of payloads) {
    const target = guard(destination + '/' + name);
    fs.mkdirSync(path.dirname(target), { recursive: true }); fs.writeFileSync(target, bytes, { flag: 'wx' });
    assert.deepEqual(read(target), bytes);
  }
  console.log(JSON.stringify({ archivedFiles: targets.length + 2, inventorySha256: sha(payloads.get('inventory.json').bytes) }));
}
