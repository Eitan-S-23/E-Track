const io = require('./io.cjs');
const { execFileSync } = require('node:child_process');
const commit = '15be25e593405396d8db8fb0011fc62e42d6d27d';
const product = 'b56534d7b6c993c0795010d0404fb8a81f7eeb9d';
const directory = 'docs/ota-exec-notes/P4-4-s3-remediation-2026-10-19';
const destination = io.reserve('delivery-review.json');
const report = { startedAt: new Date().toISOString(), commit, product, files: [], formalAcceptance: 'NOT_RUN' };
const git = args => execFileSync('git', ['--no-optional-locks', ...args], { cwd: io.worktree, windowsHide: true, maxBuffer: 8 * 1024 * 1024 });
try {
  const inventory = io.readJson(io.path.join(io.worktree, directory, 'raw-output-inventory.json'));
  for (const entry of inventory.files) {
    io.assert.ok(!entry.path.includes('..') && !io.path.isAbsolute(entry.path));
    const relative = directory + '/' + entry.path;
    const bytes = io.fs.readFileSync(io.path.join(io.worktree, relative));
    const blob = git(['show', commit + ':' + relative]);
    io.assert.equal(bytes.length, entry.sizeBytes); io.assert.equal(io.sha256(bytes), entry.sha256);
    io.assert.equal(blob.length, entry.sizeBytes); io.assert.equal(io.sha256(blob), entry.sha256);
    report.files.push({ path: relative, bytes: bytes.length, sha256: entry.sha256 });
  }
  io.assert.equal(report.files.length, 38);
  report.totalBytes = report.files.reduce((sum, file) => sum + file.bytes, 0);
  io.assert.equal(report.totalBytes, 2990737);
  const scopedPaths = ['.github/scripts', '.github/workflows/firmware-build.yml',
    'app/bluetooth_flutter_Trace/cloudflare/update-service', 'tests/ota',
    'docs/ota-cross-system-contracts.md', 'docs/ota-prompts'];
  io.assert.equal(git(['diff', '--name-only', product, commit, '--', ...scopedPaths]).toString().trim(), '');
  report.productAndValidationUnchanged = true;
  const ci = JSON.parse(io.fs.readFileSync(io.path.join(io.worktree, directory, 'remediation-ci-state-02.log'), 'utf8'));
  const governance = JSON.parse(io.fs.readFileSync(io.path.join(io.worktree, directory, 'remediation-governance-state-01.log'), 'utf8'));
  for (const state of [ci, governance]) {
    io.assert.equal(state.headSha, product); io.assert.equal(state.status, 'completed'); io.assert.equal(state.conclusion, 'success');
    io.assert.ok(state.jobs.every(job => job.status === 'completed' && ['success', 'skipped'].includes(job.conclusion)));
  }
  io.assert.equal(ci.jobs.filter(job => job.conclusion === 'success').length, 2);
  io.assert.equal(ci.jobs.filter(job => job.conclusion === 'skipped').length, 3);
  io.assert.equal(governance.jobs.filter(job => job.conclusion === 'success').length, 3);
  report.ci = { firmware: ci, governance };
  const audit = JSON.parse(io.fs.readFileSync(io.path.join(io.worktree, directory, 'remediation-npm-audit-01.log'), 'utf8'));
  report.advisories = { counts: audit.metadata.vulnerabilities, nodes: Object.keys(audit.vulnerabilities).sort() };
  io.assert.equal(report.advisories.counts.total, 11); io.assert.equal(report.advisories.counts.critical, 0);
  report.pass = true;
} catch (error) { report.error = error.message; process.exitCode = 1; }
report.endedAt = new Date().toISOString(); io.writeJson(destination, report);
process.stdout.write(JSON.stringify({ output: destination, pass: report.pass || false, files: report.files.length,
  totalBytes: report.totalBytes, error: report.error }) + '\n');
