import fs from 'node:fs';
import path from 'node:path';
import assert from 'node:assert/strict';
import { createHash } from 'node:crypto';
import { spawnSync } from 'node:child_process';
import { fileURLToPath, pathToFileURL } from 'node:url';

const directory = path.dirname(fileURLToPath(import.meta.url));
const root = path.resolve(directory, '../..');
const destination = path.join(root, 'docs/ota-exec-notes/P4-1-r2-registration-qualification-2026-10-15');
const { outputPath } = await import(pathToFileURL(path.join(root,
  'app/bluetooth_flutter_Trace/cloudflare/update-service/scripts/firmware-cli.mjs')));
const guard = value => outputPath(root, value);
const hash = value => createHash('sha256').update(value).digest('hex');
const encode = value => Buffer.from(JSON.stringify(value, null, 2) + '\n');
assert.equal(fs.realpathSync.native(process.cwd()), fs.realpathSync.native(root));
const action = process.argv[2];
assert.ok(['ci', 'plan', 'apply', 'verify'].includes(action));
const zip = guard(path.join(root, '.cache/github/p41-75ee-firmware-logs.zip'));
function command(executable, args) {
  const result = spawnSync(executable, args, { cwd: root, windowsHide: true, maxBuffer: 32 * 1024 * 1024, timeout: 120000 });
  assert.equal(result.status, 0, executable + ' failed');
  return result.stdout;
}
const entries = command('tar', ['-tf', zip]).toString('utf8').trim().split(/\r?\n/);
const selected = new Map();
for (const [name, prefix, step] of [
  ['host', 'Release tooling', 6], ['pipeline', 'Release tooling', 7], ['native-workerd', 'Release tooling', 8],
  ['types', 'Release tooling', 9], ['worker-bundle', 'Release tooling', 10], ['vendor-build', 'Release tooling', 12],
  ['byte-tests', 'Release tooling', 13], ['workflow-tests', 'Release tooling', 14], ['byte-fixture', 'Release tooling', 15],
  ['checkout-development', 'Release tooling', 2], ['checkout-gcc', 'Build firmware', 2],
  ['gcc-build', 'Build firmware', 11], ['gcc-byte-preparation', 'Build firmware', 17]
]) {
  const matches = entries.filter(entry => entry.startsWith(prefix + ' ') && entry.includes('/' + step + '_'));
  assert.equal(matches.length, 1, 'Unique CI step: ' + name);
  selected.set(name, { entry: matches[0], bytes: command('tar', ['-xOf', zip, matches[0]]) });
}
const plain = name => selected.get(name).bytes.toString('utf8').replace(/\x1b\[[0-9;]*m/g, '');
if (action === 'ci') {
  const output = guard(path.join(directory, 'ci-summary.json'));
  assert.equal(fs.existsSync(output), false);
  const runs = JSON.parse(fs.readFileSync(path.join(root, '.cache/github/p41-continue-75ee-ci.json'))).workflow_runs;
  const run = runs.find(value => value.id === 38689324267);
  assert.equal(run.head_sha, '75eea2c7380cfe3dadf147af4514a1e443d6e5d8');
  assert.equal(run.conclusion, 'success'); assert.equal(run.event, 'pull_request');
  const jobs = JSON.parse(fs.readFileSync(path.join(root, '.cache/github/p41-75ee-firmware-jobs.json'))).jobs;
  assert.deepEqual(jobs.filter(value => /rehearsal|production/.test(value.name)).map(value => value.conclusion), ['skipped', 'skipped']);
  const counts = {
    hostScriptsAndMigration: Number(plain('host').match(/Tests\s+(\d+) passed/)[1]),
    pipelineHost: Number(plain('pipeline').match(/Tests\s+(\d+) passed/)[1]),
    nativeWorkerd: Number(plain('native-workerd').match(/Tests\s+(\d+) passed/)[1]),
    bytePreparation: Number(plain('byte-fixture').match(/\u2139 tests (\d+)/)[1]),
    packageAndVectors: [...plain('byte-tests').matchAll(/Ran (\d+) tests?/g)].map(match => Number(match[1])),
    workflow: Number(plain('workflow-tests').match(/\u2139 tests (\d+)/)[1])
  };
  for (const name of ['host', 'pipeline', 'native-workerd']) {
    const totals = plain(name).match(/Tests\s+(\d+) passed\s+\((\d+)\)/);
    assert.ok(totals, 'Vitest passed and total counts required: ' + name);
    assert.equal(Number(totals[1]), Number(totals[2]));
  }
  for (const name of ['workflow-tests', 'byte-fixture']) {
    const tests = Number(plain(name).match(/\u2139 tests (\d+)/)[1]);
    assert.equal(Number(plain(name).match(/\u2139 pass (\d+)/)[1]), tests);
    for (const field of ['fail', 'cancelled', 'skipped', 'todo']) {
      assert.equal(Number(plain(name).match(new RegExp('\\u2139 ' + field + ' (\\d+)'))[1]), 0);
    }
  }
  assert.equal(plain('byte-tests').split(/\r?\n/).filter(line => line.endsWith(' OK')).length, 2);
  assert.deepEqual(counts, { hostScriptsAndMigration: 34, pipelineHost: 33, nativeWorkerd: 156,
    bytePreparation: 19, packageAndVectors: [8, 9], workflow: 41 });
  const sourcePaths = ['.github/workflows/firmware-build.yml', 'Tools/etu_pack.py', 'Tools/etu_unpack.py',
    'app/bluetooth_flutter_Trace/cloudflare/update-service/scripts',
    'app/bluetooth_flutter_Trace/cloudflare/update-service/worker', 'tests/ota'];
  command('git', ['--no-optional-locks', 'diff', '--exit-code', 'cd4f2e4d651fb7eafe8253ce854b90242cede4d9', run.head_sha, '--', ...sourcePaths]);
  const summary = { runId: run.id, event: run.event, headSha: run.head_sha, url: run.html_url,
    productCommit: 'cd4f2e4d651fb7eafe8253ce854b90242cede4d9', reviewedSourcePaths: sourcePaths, productDiffExitCode: 0,
    counts, gccWarnings: (plain('gcc-build').match(/\bwarning:/g) ?? []).length,
    gccErrors: (plain('gcc-build').match(/\berror:/g) ?? []).length,
    vendorWarnings: (plain('vendor-build').match(/\bwarning:/g) ?? []).length,
    jobs: jobs.map(value => ({ id: value.id, name: value.name, conclusion: value.conclusion })),
    selected: [...selected].map(([name, value]) => ({ name, zipEntry: value.entry,
      sizeBytes: value.bytes.length, sha256: hash(value.bytes),
      commandLines: value.bytes.toString('utf8').split(/\r?\n/).filter(line => line.includes('##[group]Run ')),
      resultLines: plain(name).split(/\r?\n/).filter(line => /Tests\s+\d+ passed|\u2139 (tests|pass|fail|cancelled|skipped|todo) |Ran \d+ tests?|^.*\bOK$/.test(line)) })) };
  assert.equal(summary.gccErrors, 0);
  fs.writeFileSync(output, encode(summary), { flag: 'wx' });
  console.log(JSON.stringify({ output, counts, gccWarnings: summary.gccWarnings, gccErrors: summary.gccErrors,
    vendorWarnings: summary.vendorWarnings }));
} else if (action === 'verify') {
  const inventoryPath = guard(path.join(destination, 'inventory.json'));
  const inventory = JSON.parse(fs.readFileSync(inventoryPath, 'utf8'));
  for (const entry of inventory.files) {
    const bytes = fs.readFileSync(guard(path.join(destination, entry.path)));
    assert.equal(bytes.length, entry.sizeBytes, entry.path);
    assert.equal(hash(bytes), entry.sha256, entry.path);
  }
  console.log(JSON.stringify({ exactFilesVerified: inventory.files.length, inventorySha256: hash(fs.readFileSync(inventoryPath)) }));
} else {
  const token = fs.readFileSync(path.join(root, '.cache/cf-auth-input/token.txt'), 'utf8').trim();
  const secrets = JSON.parse(fs.readFileSync(path.join(root, '.cache/cf-auth-input/firmware-test-secrets.json'), 'utf8'));
  const sensitive = [token, ...Object.values(secrets)].filter(value => typeof value === 'string' && value.length > 10);
  const payloads = new Map();
  function add(name, source, bytes = fs.readFileSync(guard(source))) {
    assert.equal(payloads.has(name), false);
    const target = guard(path.join(destination, name));
    if (name !== '.gitattributes') assert.equal(fs.existsSync(target), false, name);
    for (const value of sensitive) assert.equal(bytes.includes(Buffer.from(value)), false, 'Credential in ' + name);
    payloads.set(name, { source, target, bytes });
  }
  function walk(dir, prefix) {
    for (const entry of fs.readdirSync(guard(dir), { withFileTypes: true })) {
      const target = guard(path.join(dir, entry.name));
      assert.equal(entry.isSymbolicLink(), false);
      if (entry.isDirectory()) { if (entry.name !== 'runtime') walk(target, prefix + entry.name + '/'); }
      else add(prefix + entry.name, target);
    }
  }
  walk(directory, 'operations/');
  for (const [name, value] of selected) add('ci/steps/' + name + '.txt', zip + '!' + value.entry, value.bytes);
  for (const name of ['p41-continue-75ee-ci.json', 'p41-75ee-firmware-jobs.json', 'p41-75ee-firmware-logs.zip',
    'p41-s3-main-before-record.json', 'p41-s3-releases-after.json', 'p41-s3-environments-after.json']) {
    add('github/' + name, path.join(root, '.cache/github', name));
  }
  for (const label of ['p41-s3-first-upload', 'p41-s3-first-upload-r2', 'p41-s3-assets-register',
    'p41-s3-protected-after', 'p41-s3-ci-inspection', 'p41-s3-ci-inspection-r2', 'p41-s3-ci-inspection-r3', 'p41-s3-closeout-audit']) {
    for (const suffix of ['json', 'stdout.txt', 'stderr.txt']) add('commands/' + label + '.' + suffix,
      path.join(root, '.cache/logs', label + '.' + suffix));
  }
  add('commands/run.cjs', path.join(root, '.cache/run.cjs'));
  add('commands/gh.cjs', path.join(root, '.cache/gh.cjs'));
  const fixture = path.join(root, '.cache/cf-firmware-setup-20261015/qualification-fixture/firmware-release-tests/case-R5kVz9/prepared');
  for (const name of ['app-final.bin', 'e-track-at32f435-v2.8.1-full.etu',
    'e-track-at32f435-v2.8.0-to-v2.8.1-patch.etu', 'recovery-v2.8.1.bin', 'verification.json']) add('fixture/' + name, path.join(fixture, name));
  add('fixture/qualification-metadata-unverified.json', path.join(root, '.cache/cf-firmware-setup-20261015/d1-edit-r2/qualification-metadata.json'));
  add('.gitattributes', path.join(destination, '.gitattributes'));
  const inventory = [...payloads].map(([name, value]) => ({ path: name, source: path.relative(root, value.source).replaceAll('\\', '/'),
    sizeBytes: value.bytes.length, sha256: hash(value.bytes) }));
  const planSha256 = hash(encode(inventory));
  const inventoryPath = guard(path.join(destination, 'inventory.json'));
  assert.equal(fs.existsSync(inventoryPath), false);
  if (action === 'apply') {
    assert.equal(process.argv[3], planSha256);
    for (const [name, value] of payloads) {
      if (name === '.gitattributes') continue;
      fs.mkdirSync(guard(path.dirname(value.target)), { recursive: true });
      fs.writeFileSync(guard(value.target), value.bytes, { flag: 'wx' });
      assert.equal(hash(fs.readFileSync(value.target)), hash(value.bytes));
    }
    fs.writeFileSync(inventoryPath, encode({ purpose: 'Synthetic R2/registration qualification; not formal rehearsal or independent whole-card acceptance',
      productCommit: 'cd4f2e4d651fb7eafe8253ce854b90242cede4d9', originalHead: '75eea2c7380cfe3dadf147af4514a1e443d6e5d8', files: inventory }), { flag: 'wx' });
    console.log(JSON.stringify({ archivedFiles: inventory.length + 1, inventorySha256: hash(fs.readFileSync(inventoryPath)) }));
  } else console.log(JSON.stringify({ files: inventory.length + 1, bytes: inventory.reduce((sum, value) => sum + value.sizeBytes, 0),
    planSha256, destination, allTargetsNormalizedAndChecked: true }));
}
