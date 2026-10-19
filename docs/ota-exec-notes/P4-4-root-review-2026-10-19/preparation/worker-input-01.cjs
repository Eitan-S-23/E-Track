const io = require('./io.cjs');
const { spawnSync, execFileSync } = require('node:child_process');
const commit = 'b56534d7b6c993c0795010d0404fb8a81f7eeb9d';
const runId = 39175549010;
const resultPath = io.reserve('worker-input-01.json');
const archivePath = io.reserve('worker-input-01.zip');
const listingPath = io.reserve('worker-input-01-members.txt');
const runtimePath = io.reserve('worker-runtime/index.js');
const mapPath = io.reserve('worker-runtime-source-map/index.js.map');
const report = { startedAt: new Date().toISOString(), kind: 'TESTED_WORKER_INPUT_PREPARATION', commit, runId,
  requests: [], operations: [], deployed: false, formalAcceptance: 'NOT_RUN' };
const env = io.environment(); env.GH_TOKEN = io.githubToken(env);
delete env.GITHUB_TOKEN; env.GH_DEBUG = ''; env.GH_HTTP_DEBUG = '';
async function get(route) {
  const response = await io.http('https://api.github.com/repos/Eitan-S-23/E-Track/' + route, { headers: {
    authorization: 'Bearer ' + env.GH_TOKEN, accept: 'application/vnd.github+json',
    'user-agent': 'E-Track-P44-acceptance', 'x-github-api-version': '2022-11-28',
  } }, report.requests);
  io.assert.equal(response.status, 200, 'GitHub read failed'); return response.json;
}
function command(executable, args, maxBuffer) {
  const startedAt = new Date().toISOString();
  const result = spawnSync(executable, args, { cwd: io.project, env, windowsHide: true, timeout: 180000, maxBuffer });
  report.operations.push({ executable, args, startedAt, endedAt: new Date().toISOString(), exitCode: result.status,
    error: result.error?.code, signal: result.signal, stderr: io.redact((result.stderr || Buffer.alloc(0)).toString()) });
  io.assert.ok(!result.error && result.status === 0, 'Input retrieval command failed; preserve the receipt');
  return result.stdout;
}
function save(file, bytes) {
  io.guard(file); io.fs.mkdirSync(io.path.dirname(file), { recursive: true }); io.guard(file);
  io.fs.writeFileSync(file, bytes, { flag: 'wx' });
}
async function main() {
  const run = await get('actions/runs/' + runId);
  io.assert.equal(run.head_sha, commit); io.assert.equal(run.run_attempt, 1);
  io.assert.equal(run.event, 'workflow_dispatch'); io.assert.equal(run.path, '.github/workflows/firmware-build.yml');
  report.run = { id: run.id, headSha: run.head_sha, attempt: run.run_attempt, status: run.status, conclusion: run.conclusion };
  const jobs = await get('actions/runs/' + runId + '/attempts/1/jobs?per_page=100');
  io.assert.equal(jobs.jobs.length, jobs.total_count, 'Incomplete job list');
  const tooling = jobs.jobs.find(x => x.name === 'Release tooling development checks (no cloud credentials)');
  io.assert.equal(tooling?.conclusion, 'success', 'The source-bound Worker test/build job has not passed');
  io.assert.equal(tooling.steps.find(x => x.name === 'Preserve tested Worker deployment input')?.conclusion, 'success');
  report.toolingJob = tooling;
  const artifacts = await get('actions/runs/' + runId + '/artifacts?per_page=100');
  io.assert.equal(artifacts.artifacts.length, artifacts.total_count, 'Incomplete artifact list');
  const selected = artifacts.artifacts.filter(x => x.name === 'p41-worker-bundle-' + commit);
  io.assert.equal(selected.length, 1); const artifact = selected[0];
  io.assert.equal(artifact.expired, false); io.assert.equal(artifact.workflow_run.head_sha, commit);
  io.assert.match(artifact.digest, /^sha256:[0-9a-f]{64}$/);
  report.artifact = artifact;
  const bytes = command('gh', ['api', 'repos/Eitan-S-23/E-Track/actions/artifacts/' + artifact.id + '/zip'], 8 * 1024 * 1024);
  save(archivePath, bytes);
  io.assert.equal(bytes.length, artifact.size_in_bytes, 'Artifact length mismatch');
  io.assert.equal('sha256:' + io.sha256(bytes), artifact.digest, 'Artifact digest mismatch');
  const listing = command('C:/Windows/System32/tar.exe', ['-tf', archivePath], 1024 * 1024);
  save(listingPath, listing);
  const members = listing.toString().trim().split(/\r?\n/).filter(Boolean);
  io.assert.equal(new Set(members).size, members.length, 'Duplicate archive member');
  io.assert.deepEqual([...members].sort(), ['README.md', 'index.js', 'index.js.map', 'purpose.txt', 'source-commit.txt'].sort(), 'Unexpected bundle members');
  const member = name => command('C:/Windows/System32/tar.exe', ['-xOf', archivePath, name], 8 * 1024 * 1024);
  io.assert.equal(member('source-commit.txt').toString().trim(), commit);
  const runtime = member('index.js'), mapBytes = member('index.js.map');
  const map = JSON.parse(mapBytes); io.assert.equal(map.sources.length, map.sourcesContent.length);
  const checked = [];
  for (let i = 0; i < map.sources.length; i++) {
    const file = io.path.posix.normalize('.cache/p41-worker-bundle/' + map.sources[i]);
    io.assert.ok(!io.path.posix.isAbsolute(file) && !file.startsWith('../'), 'Unexpected source-map path');
    if (file.includes('/node_modules/')) continue;
    io.assert.ok(file.startsWith('app/bluetooth_flutter_Trace/cloudflare/update-service/'), 'Unreviewed bundled source');
    const original = execFileSync('git', ['--no-optional-locks', 'show', commit + ':' + file],
      { cwd: io.worktree, windowsHide: true, maxBuffer: 4 * 1024 * 1024 });
    io.assert.equal(map.sourcesContent[i].replace(/\r\n/g, '\n'), original.toString().replace(/\r\n/g, '\n'), 'Bundled source differs from Git: ' + file);
    checked.push({ path: file, gitBytesSha256: io.sha256(original) });
  }
  for (const suffix of ['/worker/src/index.ts', '/worker/src/firmware-preflight.ts', '/scripts/firmware-monotonic.mjs']) {
    io.assert.ok(checked.some(x => x.path.endsWith(suffix)), 'Required preflight source absent from bundle');
  }
  io.assert.ok(runtime.includes(Buffer.from('/api/ci/firmware/preflight')));
  save(runtimePath, runtime); save(mapPath, mapBytes);
  report.sourceChecks = checked; report.runtime = { path: runtimePath, bytes: runtime.length, sha256: io.sha256(runtime) };
  report.archive = { path: archivePath, bytes: bytes.length, sha256: io.sha256(bytes) };
  report.complete = true;
}
main().catch(error => { report.error = io.redact(error.message); process.exitCode = 1; }).finally(() => {
  report.endedAt = new Date().toISOString(); io.writeJson(resultPath, report);
  process.stdout.write(JSON.stringify({ output: resultPath, complete: report.complete || false,
    artifactId: report.artifact?.id, sourceFilesVerified: report.sourceChecks?.length, runtime: report.runtime, error: report.error }) + '\n');
});
