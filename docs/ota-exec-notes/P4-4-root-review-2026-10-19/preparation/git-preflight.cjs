const io = require('./io.cjs');
const { fs, path, assert } = io;
const base = io.project + '/.git';
const task = 'worktrees/p4-4-integration-20261018/';
const branch = 'dev/p4-4/config-integration-20261018';
for (const name of ['GIT_INDEX_FILE', 'GIT_OBJECT_DIRECTORY', 'GIT_ALTERNATE_OBJECT_DIRECTORIES',
  'GIT_TRACE', 'GIT_TRACE2', 'GIT_TRACE2_EVENT', 'GIT_TRACE2_PERF', 'BASH_ENV', 'ENV']) {
  assert.ok(!process.env[name], 'Unexpected Git/shell output override: ' + name);
}
const targets = [task + 'index', task + 'index.lock', task + 'HEAD', task + 'HEAD.lock',
  task + 'COMMIT_EDITMSG', task + 'logs/HEAD', 'objects',
  'refs/heads/' + branch, 'refs/heads/' + branch + '.lock', 'logs/refs/heads/' + branch,
  'refs/remotes/origin/' + branch, 'refs/remotes/origin/' + branch + '.lock',
  'logs/refs/remotes/origin/' + branch];
for (const relative of targets) io.guard(path.join(base, relative));
let objectDirectories = 0;
for (const entry of fs.readdirSync(path.join(base, 'objects'), { withFileTypes: true })) {
  assert.ok(!entry.isSymbolicLink());
  if (entry.isDirectory()) { io.guard(path.join(base, 'objects', entry.name)); objectDirectories++; }
}
const outputs = [];
for (const label of ['root-stage-01', 'root-commit-01', 'root-push-01']) {
  for (const suffix of ['.log', '.json', '-wrangler.log']) {
    const target = io.guard(io.worktree + '/.cache/p44/logs/' + label + suffix);
    assert.ok(!fs.existsSync(target), 'Existing Git operation receipt; do not repeat blindly');
    outputs.push(target);
  }
}
process.stdout.write(JSON.stringify({ targets, objectDirectories, outputs,
  rootIndex: 'read-only and not staged', mainRef: 'not modified',
  hooks: 'Existing hooks inspected; explicit commit message avoids AI generation and contained runner disables webhook notification.' }) + '\n');
