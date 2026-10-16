// Bounded development-log retention only; no acceptance runner or remote calls.
const fs = require('node:fs');
const path = require('node:path');
const cp = require('node:child_process');
const assert = require('node:assert/strict');
const crypto = require('node:crypto');
const { guard } = require('../../docs/acceptance-contracts/P4-1-v1/tools/session.cjs');

const root = fs.realpathSync.native(process.cwd());
const destination = 'docs/ota-exec-notes/P4-1-native-01-remediation-2026-10-16';
const sourceCommit = '5d4d07571451905ac156a1a721fa8b8ce764ed7c';
const runs = { fw: 38929267144, cf: 38929267218, gov: 38929267147, app: 38929267169 };
const read = value => fs.readFileSync(guard(value));
const json = value => JSON.parse(read(value));
const hash = bytes => crypto.createHash('sha256').update(bytes).digest('hex');
const encode = value => Buffer.from(JSON.stringify(value, null, 2) + '\n');
const git = args => cp.execFileSync('git', ['--no-optional-locks', '-c', 'core.fsmonitor=false', ...args],
  { cwd: root, encoding: 'utf8', windowsHide: true }).trim();
const payloads = new Map();
function retain(name, bytes, source) {
  assert(!payloads.has(name));
  payloads.set(name, { bytes, source });
}
function copy(source, name) { retain(name, read(source), source); }

const local = [];
const labels = ['red-inputs', 'red', 'green', 'pipeline', 'types', 'types-fixed',
  'host-final', 'final-inputs', 'diff-check', 'add', 'implementation-commit'];
for (const label of labels) {
  const stem = '.cache/logs/p41-native-01-' + label;
  const receipt = json(stem + '.json');
  assert.equal(receipt.closed, true);
  assert.equal(receipt.exitCode, label === 'red' ? 1 : label === 'types' ? 2 : 0);
  for (const suffix of ['.json', '.stdout.txt', '.stderr.txt']) copy(stem + suffix, 'commands/' + path.basename(stem + suffix));
  const stdout = read(stem + '.stdout.txt').toString('utf8');
  local.push({ label, exitCode: receipt.exitCode, started: receipt.started, ended: receipt.ended,
    testSummaries: stdout.split(/\r?\n/).filter(line => /^\s+Tests\s/.test(line)).map(line => line.trim()) });
}
assert.deepEqual(local.find(row => row.label === 'red').testSummaries, ['Tests  3 failed | 38 passed (41)']);
for (const label of ['green', 'host-final']) {
  assert.deepEqual(local.find(row => row.label === label).testSummaries, ['Tests  41 passed (41)']);
}
assert.deepEqual(local.find(row => row.label === 'pipeline').testSummaries, ['Tests  136 passed (136)']);

for (const name of fs.readdirSync(guard('.cache/github')).filter(name => name.startsWith('p41-native-01-')).sort()) {
  copy('.cache/github/' + name, 'github/' + name);
}
const source = json('.cache/github/p41-native-01-source-commit.json');
const checkout = json('.cache/github/p41-native-01-checkout-commit.json');
const pr = json('.cache/github/p41-native-01-pr-current.json');
assert.equal(source.sha, sourceCommit);
assert.equal(pr.head.sha, sourceCommit);
assert.equal(pr.merge_commit_sha, checkout.sha);
assert.equal(source.tree.sha, checkout.tree.sha);
assert.equal(git(['show', '-s', '--format=%T', sourceCommit]), source.tree.sha);
assert.equal(pr.merged, false);
assert.equal(pr.draft, true);
const runList = json('.cache/github/p41-native-01-ci-final.json').workflow_runs;
assert.deepEqual(runList.map(run => run.id).sort(), Object.values(runs).sort());
for (const run of runList) {
  assert.equal(run.head_sha, sourceCommit);
  assert.equal(run.event, 'pull_request');
  assert.equal(run.run_attempt, 1);
  assert.equal(run.status, 'completed');
  assert.equal(run.conclusion, 'success');
}

const jobs = {};
const zipMembers = [];
const logs = {};
const credentialPattern = /\b(?:gh[pousr]_[A-Za-z0-9]{20,}|github_pat_[A-Za-z0-9_]{30,})\b/;
for (const [group, runId] of Object.entries(runs)) {
  const listing = json('.cache/github/p41-native-01-' + group + '-jobs.json');
  assert.equal(listing.total_count, listing.jobs.length);
  jobs[group] = listing.jobs.map(job => {
    assert.equal(job.run_id, runId);
    assert.equal(job.head_sha, sourceCommit);
    assert.equal(job.status, 'completed');
    assert(['success', 'skipped'].includes(job.conclusion));
    return { id: job.id, name: job.name, conclusion: job.conclusion,
      steps: job.steps.map(step => ({ number: step.number, name: step.name, conclusion: step.conclusion })) };
  });
  const zip = guard('.cache/github/p41-native-01-' + group + '-logs.zip');
  const names = cp.execFileSync('tar.exe', ['-tf', zip], { cwd: root, encoding: 'utf8', windowsHide: true }).trim().split(/\r?\n/);
  assert.equal(new Set(names).size, names.length);
  logs[group] = new Map();
  for (const member of names) {
    assert(!member.includes('..') && !path.isAbsolute(member));
    const bytes = cp.execFileSync('tar.exe', ['-xOf', zip, member], { cwd: root, windowsHide: true, maxBuffer: 16 * 1024 * 1024 });
    assert(!credentialPattern.test(bytes.toString('utf8')), 'Credential pattern in ' + member);
    logs[group].set(member, bytes.toString('utf8').replace(/\x1b\[[0-9;]*[A-Za-z]/g, ''));
    zipMembers.push({ archive: 'github/' + path.basename(zip), member, sizeBytes: bytes.length, sha256: hash(bytes) });
  }
}
function log(group, fragment, aggregate = false) {
  const entries = [...logs[group]].filter(([name]) => name.includes(fragment) && !name.includes('/') === aggregate);
  assert.equal(entries.length, 1, fragment);
  return entries[0][1];
}
const tooling = log('fw', 'Release tooling', true);
const native = log('cf', 'Worker Typecheck', true);
const governance = log('gov', 'Validate acceptance', true);
assert.deepEqual(jobs.fw.filter(job => job.conclusion === 'skipped').map(job => job.name).sort(), [
  'Isolated firmware binding qualification (not rehearsal)',
  'Firmware rehearsal (shared release implementation)', 'Firmware production (shared release implementation)'
].sort());
assert.deepEqual(jobs.app.filter(job => job.conclusion === 'skipped').map(job => job.name).sort(), [
  'Build Android APK', 'Build Windows EXE', 'Deploy GitHub Pages', 'Create GitHub Release'
].sort());
const counts = content => [...content.matchAll(/\bTests\s+(\d+) passed/g)].map(match => Number(match[1]));
assert.deepEqual(counts(tooling), [41, 136, 156]);
assert.deepEqual(counts(native), [156]);
assert(log('fw', 'Release tooling development checks (no cloud credentials)/2_Checkout').includes(checkout.sha));
assert(log('cf', 'Worker Typecheck and Invariants/2_Checkout').includes(checkout.sha));
const diagnostics = {};
for (const [label, fragment] of [['gcc', '/11_Build firmware.txt'], ['keyedDevelopmentGcc', '/19_Exercise the shared key-bound'],
  ['vendorBsdiff', '/12_Build the existing vendor']]) {
  const content = log('fw', fragment);
  diagnostics[label] = { warnings: [...content.matchAll(/\bwarning:/g)].length, errors: [...content.matchAll(/\berror:/g)].length };
  assert.equal(diagnostics[label].errors, 0);
}
const frozenPaths = ['docs/acceptance-contracts/P4-1-v1', 'docs/acceptance-contracts/P4-1-v1.contract.json',
  'docs/acceptance-contracts/FREEZE-INDEX.md'];
assert.equal(git(['diff', '--name-status', '53b78608cac6bb5c2e9253362471b6383f5c31ff', '--', ...frozenPaths]), '');
const redInputs = json('.cache/logs/p41-native-01-red-inputs.stdout.txt');
assert.equal(hash(fs.readFileSync('D:/github/my/E-Track/.git/index')), redInputs.sharedIndexSha256);
const summary = { scope: 'P41-NATIVE-01 development self-tests, not independent acceptance',
  sourceCommit, branch: pr.head.ref, actualPrCheckout: checkout.sha, sourceAndCheckoutTree: source.tree.sha,
  runs, local, ciCounts: { firmwareToolingSuites: counts(tooling), backendNative: counts(native),
    nodeSuites: [...tooling.matchAll(/(?:\u2139|#) tests (\d+)/g)].map(match => Number(match[1])),
    pythonToolingSuites: [...tooling.matchAll(/Ran (\d+) tests/g)].map(match => Number(match[1])),
    governanceSuites: [...governance.matchAll(/Ran (\d+) tests/g)].map(match => Number(match[1])) },
  countPolicy: 'Distinct suites; repeated native runs and duplicated aggregate/step logs are not summed.',
  diagnostics, jobs, oldV1Result: 'PRODUCT_FAIL', frozenPathsUnchanged: true, sharedIndexUnchanged: true,
  cloudUploadReadbackReady: 'NOT_VERIFIED_BY_THIS_REPAIR', r2WritePermission: 'NOT_VERIFIED',
  stagingDispatches: 0, newQualificationUploads: 0, independentAcceptance: 'PENDING_ORIGINAL_REVIEWER' };
retain('ci-inspection.json', encode(summary), 'Derived from original closed receipts, GitHub API and complete job log ZIPs');
retain('zip-members.json', encode(zipMembers), 'SHA-256 of original CI ZIP members read without extraction');
copy('.cache/run.cjs', 'helpers/run.cjs');
copy('.cache/gh.cjs', 'helpers/gh.cjs');
copy('.cache/p41-native-01-remediation/retain.cjs', 'helpers/retain.cjs');
const inventory = [{ path: '.gitattributes', sizeBytes: read(destination + '/.gitattributes').length,
  sha256: hash(read(destination + '/.gitattributes')), source: 'Byte-preserving Git attributes for this new development archive' }];
for (const [name, value] of payloads) {
  assert(!credentialPattern.test(value.bytes.toString('utf8')), 'Credential pattern: ' + name);
  const target = guard(destination + '/' + name);
  assert(!fs.existsSync(target), 'Refuse to overwrite: ' + target);
  inventory.push({ path: name, source: value.source, sizeBytes: value.bytes.length, sha256: hash(value.bytes) });
}
retain('inventory.json', encode({ sourceCommit, scope: summary.scope, files: inventory }), 'Inventory excluding itself');
assert(!fs.existsSync(guard(destination + '/inventory.json')));
console.log(JSON.stringify({ preflight: 'PASS', destination: guard(destination), files: payloads.size + 1, summary }, null, 2));
if (process.argv.includes('--apply')) {
  for (const [name, value] of payloads) {
    const target = guard(destination + '/' + name);
    fs.mkdirSync(guard(path.dirname(target)), { recursive: true });
    fs.writeFileSync(guard(target), value.bytes, { flag: 'wx' });
    assert.equal(hash(read(target)), hash(value.bytes));
  }
  console.log(JSON.stringify({ retained: payloads.size + 1, inventorySha256: hash(read(destination + '/inventory.json')) }));
}
