const io = require('./io.cjs');
const { fs, path, assert, sha256 } = io;
const { spawnSync } = require('node:child_process');
const mode = process.argv[2];
assert.ok(['record', 'final'].includes(mode));
const destination = io.output('write-audit-01.json');
if (mode === 'record') assert.ok(!fs.existsSync(destination), 'Preserve prior audit');
const scopes = [io.project + '/.cache/p44-root-review-546d8b3-20261019', io.base,
  io.project + '/docs/ota-exec-notes/P4-4-s3-preacceptance-2026-10-19.md',
  io.worktree + '/docs/ota-exec-notes/P4-4-root-review-2026-10-19',
  io.worktree + '/docs/ota-exec-notes/P4-4-s3-preacceptance-2026-10-19.md',
  io.worktree + '/docs/ota-exec-notes/P4-4-configuration-2026-10-18.md',
  io.worktree + '/PLAN-OTA-EXEC.md',
  ...fs.readdirSync(io.worktree + '/.cache/p44/logs').filter(name => name.startsWith('root-'))
    .map(name => io.worktree + '/.cache/p44/logs/' + name)];
const inspected = [];
const counts = { files: 0, directories: 0, bytes: 0 };
function visit(target) {
  io.guard(target);
  const stat = fs.lstatSync(target);
  assert.ok(!stat.isSymbolicLink(), 'Linked controlled output');
  const relative = path.relative(io.project, fs.realpathSync(target));
  assert.ok(relative !== '..' && !relative.startsWith('..' + path.sep) && !path.isAbsolute(relative));
  if (stat.isDirectory()) {
    counts.directories++;
    for (const name of fs.readdirSync(target)) visit(path.join(target, name));
  } else {
    counts.files++; counts.bytes += stat.size;
    inspected.push({ path: relative.replaceAll('\\', '/'), sizeBytes: stat.size });
  }
}
for (const scope of scopes) if (fs.existsSync(io.guard(scope))) visit(scope);
const git = (cwd, args) => {
  const result = spawnSync('git', ['--no-optional-locks', ...args], { cwd, encoding: 'utf8', windowsHide: true });
  assert.equal(result.status, 0, 'Read-only Git check failed'); return result.stdout.trim();
};
const rootIndex = io.guard(io.project + '/.git/index');
const rootIndexSha256 = sha256(fs.readFileSync(rootIndex));
if (mode === 'final') assert.equal(rootIndexSha256, io.readJson(destination).rootSharedIndexSha256,
  'Root shared index changed; reconcile without reverting');
assert.equal(git(io.worktree, ['diff', '15be25e593405396d8db8fb0011fc62e42d6d27d', '--name-only', '--',
  'app', '.github', 'Libraries', 'USER', 'boot', 'MDK-ARM_F435', 'tests', 'Tools',
  'docs/acceptance-contracts', 'docs/ota-cross-system-contracts.md', 'docs/ota-prompts']), '');
const external = [
  'C:/Users/SU/AppData/LocalLow/Microsoft/CryptnetUrlCache/Content/ABD721CDC3648033BA8C827AF15A4543',
  'C:/Users/SU/AppData/LocalLow/Microsoft/CryptnetUrlCache/MetaData/ABD721CDC3648033BA8C827AF15A4543',
  'C:/Users/SU/AppData/LocalLow/Microsoft/CryptnetUrlCache/Content/B6E4D06BF128A1673A8DAFB4E25B990D',
  'C:/Users/SU/AppData/LocalLow/Microsoft/CryptnetUrlCache/MetaData/B6E4D06BF128A1673A8DAFB4E25B990D',
  'C:/Users/SU/AppData/Local/Microsoft/PowerShell/StartupProfileData-NonInteractive',
  'C:/Users/SU/AppData/Local/Microsoft/Windows/PowerShell/StartupProfileData-NonInteractive',
].map(file => {
  if (!fs.existsSync(file)) return { path: file, exists: false };
  const stat = fs.statSync(file);
  return { path: file, exists: true, sizeBytes: stat.size, mtime: stat.mtime.toISOString() };
});
const record = { observedAt: new Date().toISOString(), mode, activeProjectRoot: io.project,
  additionalAuthorizedWorktree: io.worktree, scopes, inspected, counts,
  head: git(io.worktree, ['rev-parse', 'HEAD']), branch: git(io.worktree, ['branch', '--show-current']),
  rootSharedIndexSha256: rootIndexSha256, productAndFrozenInputsUnchangedSinceImplementationDelivery: true,
  selectedOutputPathsInsideAuthorizedRoot: true, externalOutputPathsSelected: [],
  externalReadOnlyObservations: external, externalCleanup: false,
  delegation: 'Implementation child controlled-output audit was independently reconciled in delivery-review.json; two review children were read-only.',
  gitWrites: 'Only task-worktree index/HEAD/COMMIT_EDITMSG/reflog, task branch and remote-tracking refs/reflogs, shared objects; no root index/main write.',
  containment: 'cmd/Node; temp, home, XDG, npm, gh and Wrangler outputs project-local; TLS checks enabled.',
  limits: 'Selected-output and inspected-command audit, not machine-wide tracing. External PowerShell-cache timestamp attribution remains unknown.' };
if (mode === 'record') io.writeJson(destination, record);
process.stdout.write(JSON.stringify({ output: mode === 'record' ? destination : null, observedAt: record.observedAt,
  counts, selectedOutputPathsInsideAuthorizedRoot: true, rootIndexPreserved: mode === 'final',
  externalReadOnlyObservations: external, limits: record.limits }) + '\n');
