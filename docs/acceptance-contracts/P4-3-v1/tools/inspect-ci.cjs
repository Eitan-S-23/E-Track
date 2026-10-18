const assert = require('node:assert/strict');
const { root, bundle, sha, run, git, readLocal, jsonLocal, verify, archiveFile, store } = require('./io.cjs');

const oldSource = '972e74c43cd36b7a308e457296aaf7bb06120e78';
const source = '0067b6c3caa9ee263c53ae372fdc63cc7f74250f';
const service = 'app/bluetooth_flutter_Trace/cloudflare/update-service/';
if (process.argv[2] === 'governance') {
  const metadata = jsonLocal(`${bundle}/inputs/governance.json`);
  assert.equal(metadata.status, 'completed'); assert.equal(metadata.conclusion, 'success');
  assert.equal(metadata.head_branch, 'dev/p4-3/admin-controls-20261017');
  assert.equal(metadata.path, '.github/workflows/acceptance-governance.yml');
  assert.equal(metadata.event, 'workflow_dispatch'); assert.equal(metadata.run_attempt, 1);
  const jobs = jsonLocal(`${bundle}/inputs/governance-jobs.json`).jobs;
  assert.equal(jobs.length, 3); assert.ok(jobs.every(job => job.conclusion === 'success'));
  git(['merge-base', '--is-ancestor', metadata.head_sha, 'HEAD']);
  git(['diff', '--exit-code', metadata.head_sha, 'HEAD', '--', 'Tools/acceptance', 'Tools/provenance',
    '.github/workflows/acceptance-governance.yml', `${bundle}/tools`]);
  const zip = readLocal(`${bundle}/inputs/governance-logs.zip`);
  const zipPath = `${bundle}/inputs/governance-logs.zip`;
  const names = run('tar', ['-tf', zipPath]).toString('utf8').trim().split(/\r?\n/);
  const checks = names.filter(name => /\/\d+_Run governance regression tests\.txt$/.test(name));
  assert.equal(checks.length, 1, 'Expected exact original regression step log');
  const logs = run('tar', ['-xOf', zipPath, checks[0]]).toString('utf8');
  assert.match(logs, /test_acceptance_bundle\.py/); assert.match(logs, /test_acceptance_efficiency\.py/);
  assert.doesNotMatch(logs, /FAILED \(|Traceback \(most recent call last\)/);
  assert.ok((logs.match(/\bOK\b/g) || []).length >= 8, 'Each required Python suite must complete');
  process.stdout.write(JSON.stringify({ nature: 'Independent original governance CI evaluation',
    runId: String(metadata.id), source: metadata.head_sha, successfulJobs: jobs.length,
    regressionSuites: (logs.match(/\bOK\b/g) || []).length, originalLogsSha256: sha(zip), verified: true }, null, 2) + '\n');
  process.exit(0);
}
const old = store('live');
const current = store('repair');
const clean = text => text.replace(/\u001b\[[0-9;]*m/g, '');
const earlySource = '933b790e69e04ee551ad255398e08f12a1b2a107';
const adminPath = service + 'admin/functions/api/admin/[[path]].ts';
assert.deepEqual(git(['diff', '--name-only', earlySource, oldSource, '--', service]).trim().split(/\r?\n/).sort(),
  [adminPath, service + 'worker/test/firmware-admin.test.ts'].sort());
const beforeCookieRepair = git(['show', `${earlySource}:${adminPath}`]);
const afterCookieRepair = git(['show', `${oldSource}:${adminPath}`]);
const repairedCookieBlock = [
  '    const existingCsrf = cookieValue(context.request.headers.get("Cookie"), "trace_admin_csrf");',
  "    // Another tab's session read must not invalidate an already-confirmed request.",
  '    const csrfToken = existingCsrf && /^[0-9a-f]{8}-[0-9a-f]{4}-4[0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$/.test(existingCsrf)',
  '      ? existingCsrf : crypto.randomUUID();'
].join('\n');
assert.ok(afterCookieRepair.includes(repairedCookieBlock));
assert.equal(afterCookieRepair.replace(repairedCookieBlock, '    const csrfToken = crypto.randomUUID();'), beforeCookieRepair);
function metadataChecks(metadata, expectedSource, expectedRun) {
  assert.equal(metadata.status, 'completed');
  assert.equal(metadata.conclusion, 'success');
  assert.equal(metadata.headSha, expectedSource);
  assert.equal(metadata.event, 'workflow_dispatch');
  assert.equal(metadata.jobs.length, 4);
  assert.ok(metadata.jobs.every(job => job.conclusion === 'success'));
  if (metadata.databaseId) assert.equal(String(metadata.databaseId), expectedRun);
}
function inspect(originals, candidate, runId, uiCount, metadataPath) {
  const metadata = originals.json(metadataPath);
  metadataChecks(metadata, candidate, runId);
  const input = `.cache/p43/ci/artifacts-${runId}/admin-deployment-input-${candidate}`;
  assert.equal(originals.text(`${input}/source-commit.txt`).trim(), candidate);
  assert.equal(originals.text(`${input}/source-run.txt`).trim(), `${runId}/1`);
  const files = originals.text(`${input}/SHA256SUMS`).trim().split(/\r?\n/).map(line => {
    const match = /^([a-f0-9]{64})  (public\/(?:_routes\.json|_worker\.js\/index\.js|index\.html))$/.exec(line);
    assert.ok(match, 'Unexpected serving manifest entry');
    const bytes = originals.read(`${input}/${match[2]}`);
    assert.equal(sha(bytes), match[1]);
    return { path: match[2], sizeBytes: bytes.length, sha256: match[1] };
  });
  assert.deepEqual(files.map(file => file.path).sort(), ['public/_routes.json', 'public/_worker.js/index.js', 'public/index.html']);
  assert.equal(originals.text(`${input}/public/index.html`), git(['show', `${candidate}:${service}admin/public/index.html`]));
  assert.match(originals.text(`${input}/public/_worker.js/index.js`), /existingCsrf/);
  const zip = originals.read(`.cache/p43/ci/logs-${runId}.zip`);
  const zipPath = archiveFile(zip);
  const log = name => clean(run('tar', ['-xOf', zipPath, name]).toString('utf8'));
  const worker = log('Worker Typecheck and Invariants/7_Run invariant tests.txt');
  const native = worker.match(/\bTests\s+(\d+) passed\s+\((\d+)\)/);
  assert.ok(native); assert.equal(Number(native[1]), 270); assert.equal(native[1], native[2]);
  const ui = originals.text(`.cache/p43/ci/artifacts-${runId}/admin-mock-ui-${runId}-1/playwright.log`);
  assert.match(ui, new RegExp(`\\b${uiCount} passed \\(`));
  assert.doesNotMatch(ui, /\b\d+ (failed|skipped|interrupted|flaky)\b/);
  if (uiCount === 36) assert.equal(originals.text(`.cache/p43/ci/artifacts-${runId}/admin-mock-ui-${runId}-1/checkout-sha.txt`).trim(), candidate);
  const smoke = originals.text(`.cache/p43/ci/artifacts-${runId}/admin-bundle-diagnostics-${runId}-1/native-smoke.log`);
  const smokeCounts = Object.fromEntries(['tests', 'pass', 'fail', 'skipped', 'cancelled'].map(name =>
    [name, Number(smoke.match(new RegExp(`\\b${name} (\\d+)`))?.[1])]));
  assert.deepEqual(smokeCounts, { tests: 3, pass: 3, fail: 0, skipped: 0, cancelled: 0 });
  const diagnostics = run('tar', ['-tf', zipPath]).toString('utf8').trim().split(/\r?\n/)
    .filter(name => /^[0-9]_/.test(name)).map(name => {
      const text = log(name);
      return { name, npmWarnings: (text.match(/npm warn/g) || []).length,
        warningAnnotations: (text.match(/##\[warning\]/g) || []).length,
        expectedNativeExceptions: (text.match(/uncaught exception;/g) || []).length,
        auditSummaries: text.split('\n').filter(line => /\b\d+ (?:high severity )?vulnerabilities\b/.test(line)) };
    });
  const bad = structuredClone(metadata); bad.conclusion = 'failure';
  assert.throws(() => metadataChecks(bad, candidate, runId));
  assert.throws(() => metadataChecks(metadata, '0'.repeat(40), runId));
  return { source: candidate, runId, worker: 270, ui: uiCount, router: smokeCounts, files, diagnostics, input };
}
const previous = inspect(old, oldSource, '39084376785', 12, '.cache/p43/logs/csrf-ci-inspect-01.log');
const repaired = inspect(current, source, '39098302062', 36, '.cache/p43/logs/accept02-ci-status-01.log');
const unchanged = ['worker', 'admin/functions', 'public', 'migrations', 'scripts', 'admin/package.json',
  'admin/package-lock.json', 'admin/playwright.config.ts', 'admin/test-bundle.mjs'].map(file => service + file);
git(['diff', '--exit-code', oldSource, source, '--', ...unchanged, '.github/workflows/cloudflare-update-service.yml']);
git(['diff', '--exit-code', source, 'HEAD', '--', service, '.github/workflows/cloudflare-update-service.yml', '.github/workflows/deploy-cloudflare-admin.yml']);
const stripComment = text => {
  const lines = text.split('\n');
  const kept = lines.filter(line => !line.startsWith('// ../.wrangler/tmp/pages-'));
  assert.equal(lines.length - kept.length, 1);
  return kept.join('\n');
};
assert.equal(stripComment(old.text(`${previous.input}/public/_worker.js/index.js`)), stripComment(current.text(`${repaired.input}/public/_worker.js/index.js`)));
assert.equal(sha(old.read(`${previous.input}/public/_routes.json`)), sha(current.read(`${repaired.input}/public/_routes.json`)));
function strip(text, start, end) {
  const a = text.indexOf(start); const b = text.indexOf(end, a + start.length);
  assert.ok(a >= 0 && b > a); return text.slice(0, a) + text.slice(b);
}
const outsideRepair = text => strip(strip(text, 'async function runFirmwareReleaseAction(', 'async function saveNotes('),
  'async function api(', 'function render()');
assert.equal(outsideRepair(old.text(`${previous.input}/public/index.html`)), outsideRepair(current.text(`${repaired.input}/public/index.html`)));
assert.equal(readLocal(service + 'admin/public/index.html').toString('utf8').replaceAll('\r\n', '\n'), current.text(`${repaired.input}/public/index.html`));
const archiveEntries = { live: old.verifyAll(), repair: current.verifyAll() };
assert.deepEqual(archiveEntries, { live: 585, repair: 158 });
assert.throws(() => verify(Buffer.from('altered'), { path: 'negative', sizeBytes: 7, sha256: '0'.repeat(64) }));
assert.throws(() => current.read('.cache/p43/private/unregistered'));

const result = { nature: 'Independent offline evaluation, not a new product CI or deployment',
  previous, repaired, archiveEntries, serverInputsUnchanged: true, routerBytesUnchanged: true,
  executableFacadeUnchanged: true, uiOutsideRepairUnchanged: true, headProductScopeMatchesRepair: true,
  negativeOraclesRejected: 6, newCloudBusinessRequests: 0, productVerdict: true };
result.earlyDrillApplicability = { source: earlySource, onlyServerDelta: 'Reviewed session GET cookie preservation; all business handlers and public inputs unchanged' };
process.stdout.write(JSON.stringify(result, null, 2) + '\n');
