// P4-1 acceptance control plane. Product construction remains in the shared workflow.
const fs = require('node:fs');
const assert = require('node:assert/strict');
const cp = require('node:child_process');
const s = require('./session.cjs');
const directory = s.outputRoot + '/formal';
const prefix = '/repos/' + s.repository;
const environmentRoute = prefix + '/environments/firmware-rehearsal';
const contractPath = 'docs/acceptance-contracts/P4-1-v1.contract.json';
const read = file => JSON.parse(fs.readFileSync(s.guard(file), 'utf8'));
const canonical = value => JSON.stringify(sort(value));
function sort(value) {
  if (Array.isArray(value)) return value.map(sort);
  if (value && typeof value === 'object') return Object.fromEntries(Object.keys(value).sort().map(k => [k, sort(value[k])]));
  return value;
}
function destination(label) {
  assert(/^[a-z0-9/.-]+$/.test(label) && label.split('/').every(part => part && part !== '.' && part !== '..'));
  return s.guard(directory + '/' + label);
}
function save(label, value) { return s.writeJson(destination(label + '.json'), value); }

async function api(label, route, { method = 'GET', body, expected = [200] } = {}) {
  assert(route === '/user' || route.startsWith(prefix + '/'));
  const output = destination(label + '.json'), receipt = destination(label + '-receipt.json');
  assert(!fs.existsSync(output) && !fs.existsSync(receipt), 'Preserve previous API observation');
  if (method !== 'GET') {
    const allowed = (method === 'POST' && route === environmentRoute + '/variables')
      || (method === 'POST' && route === prefix + '/actions/workflows/firmware-build.yml/dispatches')
      || (method === 'POST' && new RegExp('^' + prefix + '/actions/runs/[1-9][0-9]*/pending_deployments$').test(route));
    assert(allowed, 'Unapproved GitHub mutation');
  }
  const started = new Date().toISOString();
  const response = await fetch('https://api.github.com' + route, { method, redirect: 'error',
    headers: { Authorization: 'Bearer ' + s.githubToken(), Accept: 'application/vnd.github+json',
      'Content-Type': 'application/json', 'X-GitHub-Api-Version': '2022-11-28' },
    body: body === undefined ? undefined : JSON.stringify(body), signal: AbortSignal.timeout(60000) });
  const bytes = Buffer.from(await response.arrayBuffer());
  const artifact = s.write(output, bytes);
  s.writeJson(receipt, { started, ended: new Date().toISOString(), method, route, request: body,
    status: response.status, requestId: response.headers.get('x-github-request-id'), artifact });
  assert(expected.includes(response.status), 'GitHub HTTP ' + response.status + ': ' + route);
  return bytes.length ? JSON.parse(bytes) : null;
}

async function list(label, route, field) {
  const items = [];
  for (let page = 1; page <= 30; page++) {
    const data = await api(label + '-page-' + page, route + (route.includes('?') ? '&' : '?') + 'per_page=100&page=' + page);
    const batch = field ? data[field] : data;
    assert(Array.isArray(batch)); items.push(...batch);
    if (batch.length < 100) {
      assert.equal(new Set(items.map(item => item.id ?? item.name)).size, items.length, 'Duplicate listing identity');
      return items;
    }
  }
  throw Error('Incomplete bounded GitHub inventory');
}

function target() {
  const value = read(directory + '/target.json');
  assert.equal(value.repository, s.repository);
  assert.equal(value.branch, s.branch);
  assert.equal(value.versionName, '3.2.8');
  assert(/^[0-9a-f]{40}$/.test(value.commitSha));
  assert.equal(value.descriptor.targetCommitSha, value.commitSha);
  assert.equal(value.descriptor.targetVersionName, value.versionName);
  assert.equal(s.hash(canonical(value.descriptor)), value.descriptorSha256);
  return value;
}

function frozen() {
  const value = target(), contract = read(contractPath);
  assert.equal(contract.status, 'FROZEN');
  assert.equal(contract.freeze_commit, value.commitSha);
  assert.equal(s.git(['rev-parse', 'HEAD']), value.commitSha);
  assert.equal(s.git(['branch', '--show-current']), s.branch);
  return { target: value, contractSha256: s.hash(fs.readFileSync(s.guard(contractPath))) };
}

async function verifyEnvironment(label, value) {
  const user = await api(label + '/user', '/user');
  assert.equal(user.login, 'Eitan-S-23');
  const remote = await api(label + '/branch', prefix + '/git/ref/heads/' + s.branch);
  assert.equal(remote.object.sha, value.commitSha, 'Remote branch is not the approved target');
  const environment = await api(label + '/environment', environmentRoute);
  assert.equal(environment.id, 24458272742);
  assert.deepEqual(environment.deployment_branch_policy, { protected_branches: false, custom_branch_policies: true });
  const reviewers = environment.protection_rules.find(rule => rule.type === 'required_reviewers');
  assert(reviewers?.reviewers.some(item => item.type === 'User' && item.reviewer.login === user.login));
  assert.equal(reviewers.prevent_self_review, false, 'Delegation cannot bypass self-review protection');
  const policies = await list(label + '/policies', environmentRoute + '/deployment-branch-policies', 'branch_policies');
  assert.equal(policies.length, 1);
  assert.equal(policies[0].name, s.branch); assert.equal(policies[0].type, 'branch');
  const variables = await list(label + '/variables', environmentRoute + '/variables', 'variables');
  const values = Object.fromEntries(variables.map(item => [item.name, item.value]));
  assert.equal(values.OTA_BOOT_CHAIN_READY, 'false');
  assert.equal(values.FIRMWARE_REHEARSAL_TRACE_R2_BUCKET, 'e-track-firmware-p41-test-releases');
  assert.equal(values.FIRMWARE_REHEARSAL_TRACE_D1_DATABASE_NAME, 'e-track-firmware-p41-test');
  assert.equal(values.FIRMWARE_REHEARSAL_TRACE_D1_DATABASE_ID, '2617e1e1-956f-42ce-a465-da56d84abf06');
  const secrets = await list(label + '/secret-names', environmentRoute + '/secrets', 'secrets');
  assert.deepEqual(secrets.map(item => item.name).sort(), ['CLOUDFLARE_ACCOUNT_ID', 'CLOUDFLARE_API_TOKEN',
    'OTA_AES_KEY', 'TRACE_DEPLOY_TOKEN', 'TRACE_UPDATE_SERVICE_URL'].map(name => 'FIRMWARE_REHEARSAL_' + name).sort());
  return { values, environmentId: environment.id, reviewer: user.login };
}

function desiredVariables(value) {
  return { OTA_PREVIOUS_RELEASE_JSON: canonical(value.descriptor),
    OTA_APPROVED_BOOTSTRAP_BASELINE_SHA256: value.descriptorSha256,
    TRACE_FIRMWARE_MIN_APP_VERSION_CODE: '0', TRACE_FIRMWARE_MIN_PROTOCOL_VERSION: '1' };
}

async function prepareTarget() {
  const proofPath = 'docs/ota-exec-notes/P4-1-bootstrap-baseline-2026-10-15/provenance.json';
  const proof = read(proofPath), verify = proof.verification;
  const commit = s.git(['rev-parse', 'HEAD']);
  assert.equal(s.git(['branch', '--show-current']), s.branch);
  const descriptor = { provenanceKind: 'inaugural-bootstrap-v1', isFormalRelease: false, kind: 'app',
    versionName: '3.2.7', versionCode: 30207, commitSha: proof.run.head_sha, buildTimestamp: verify.build.buildTimestamp,
    imageSha256: verify.finalImage.sha256, sourceSha256: verify.finalImage.sha256, sourceSizeBytes: verify.finalImage.sizeBytes,
    archiveCommit: 'c860b3be7a0b1a3ca1b3a53cf79cc9ef21cc9124', archivePath: proofPath.replace('/provenance.json', ''),
    sourceRunId: String(proof.run.id), sourceRunAttempt: String(proof.run.run_attempt), sourceArtifactId: String(proof.artifact.id),
    sourceArtifactSha256: proof.artifact.digest.replace('sha256:', ''), provenanceSha256: s.hash(fs.readFileSync(proofPath)),
    targetVersionName: '3.2.8', targetCommitSha: commit };
  descriptor.sourceUrl = `https://raw.githubusercontent.com/${s.repository}/${descriptor.archiveCommit}/${descriptor.archivePath}/app-final.bin`;
  const value = { repository: s.repository, branch: s.branch, commitSha: commit, versionName: '3.2.8',
    descriptor, descriptorSha256: s.hash(canonical(descriptor)), minAppVersionCode: 0, minProtocolVersion: 1,
    keySha256: 'a94ae0f006b3d6be51279b861dc19b8a0892833939d0a4db5a81ee7af511fe9e' };
  const schema = await import('../../../../app/bluetooth_flutter_Trace/cloudflare/update-service/scripts/firmware-schema.mjs');
  const prepare = await import('../../../../app/bluetooth_flutter_Trace/cloudflare/update-service/scripts/prepare-firmware-release.mjs');
  assert.equal(canonical(descriptor), schema.canonicalJson(descriptor));
  prepare.validateBaseDescriptor(descriptor, value.versionName, s.repository, commit);
  prepare.validateBootstrapProvenance(descriptor, proof, s.repository);
  save('target', value);
  console.log(JSON.stringify({ target: value.versionName, commit, descriptorSha256: value.descriptorSha256 }));
}

async function configure() {
  const value = target();
  const context = await verifyEnvironment('configure-before', value);
  for (const [name, desired] of Object.entries(desiredVariables(value))) {
    assert(context.values[name] === undefined || context.values[name] === desired, 'Existing target configuration conflicts: ' + name);
    if (context.values[name] === desired) continue;
    await api('configure-' + name.toLowerCase().replaceAll('_', '-'), environmentRoute + '/variables',
      { method: 'POST', body: { name, value: desired }, expected: [201] });
  }
  const after = await verifyEnvironment('configure-after', value);
  for (const [name, expected] of Object.entries(desiredVariables(value))) assert.equal(after.values[name], expected);
  save('configured', { ok: true, targetSha256: s.hash(fs.readFileSync(destination('target.json'))),
    environmentId: after.environmentId, delegate: after.reviewer, authority: 'P41-STAGING-DELEGATION-20261016' });
}

async function githubSnapshot(label) {
  assert(['github-before', 'github-after'].includes(label));
  const releases = await list(label + '/releases', prefix + '/releases');
  for (const release of releases) release.assets = await list(label + '/assets-' + release.id, prefix + '/releases/' + release.id + '/assets');
  const stable = releases.map(release => ({ id: release.id, tag: release.tag_name, target: release.target_commitish,
    name: release.name, body: release.body, draft: release.draft, prerelease: release.prerelease,
    created: release.created_at, updated: release.updated_at, published: release.published_at,
    assets: release.assets.map(a => ({ id: a.id, name: a.name, label: a.label, size: a.size, digest: a.digest,
      state: a.state, content_type: a.content_type, created_at: a.created_at, updated_at: a.updated_at })).sort((a,b) => a.id-b.id)
  })).sort((a,b) => a.id-b.id);
  const environments = await verifyEnvironment(label + '/protected-config', target());
  for (const [name, expected] of Object.entries(desiredVariables(target()))) assert.equal(environments.values[name], expected);
  save(label + '/snapshot', { ok: true, complete: true, releases: stable, environment: environments,
    comparisonExclusions: ['asset download_count: unrelated readers may increment it'], timestamp: new Date().toISOString() });
}

async function dispatch() {
  const context = frozen(), value = context.target;
  assert.equal(read(s.outputRoot + '/commands/formal-precheck.json').exitCode, 0);
  assert.equal(read(s.outputRoot + '/cloud/before/receipt.json').ok, true);
  assert.equal(read(directory + '/github-before/snapshot.json').ok, true);
  assert.equal(read(directory + '/configured.json').ok, true);
  const request = { ref: s.branch, inputs: { version_name: value.versionName, publish: 'false', rehearsal: 'true',
    check_bindings: 'false', release_notes: 'P4-1 canonical staging qualification; not a production release.' } };
  // Reserve before POST. A lost response must be reconciled, never redispatched.
  save('dispatch-reservation', { created: new Date().toISOString(), commitSha: value.commitSha,
    contractSha256: context.contractSha256, request });
  await api('dispatch', prefix + '/actions/workflows/firmware-build.yml/dispatches', { method: 'POST', body: request, expected: [204] });
}

async function discover(label) {
  assert(/^[a-z0-9-]+$/.test(label));
  const reservation = read(directory + '/dispatch-reservation.json');
  const runs = await list(label + '/runs', prefix + '/actions/workflows/firmware-build.yml/runs?branch=' + encodeURIComponent(s.branch) + '&event=workflow_dispatch', 'workflow_runs');
  const matches = runs.filter(run => run.head_sha === reservation.commitSha && Date.parse(run.created_at) >= Date.parse(reservation.created) - 5000);
  assert.equal(matches.length, 1, 'Dispatch must resolve to exactly one source-bound run');
  assert.equal(matches[0].run_attempt, 1);
  save('run', { id: matches[0].id, head_sha: matches[0].head_sha, run_attempt: 1, html_url: matches[0].html_url });
  console.log(JSON.stringify({ runId: matches[0].id, status: matches[0].status, url: matches[0].html_url }));
}

async function status(label, approve = false) {
  assert(/^[a-z0-9-]+$/.test(label));
  const run = read(directory + '/run.json'), value = target();
  const observed = await api(label + '/run', prefix + '/actions/runs/' + run.id);
  assert.equal(observed.head_sha, value.commitSha); assert.equal(observed.run_attempt, 1);
  assert.equal(observed.path, '.github/workflows/firmware-build.yml');
  const jobs = await list(label + '/jobs', prefix + '/actions/runs/' + run.id + '/attempts/1/jobs', 'jobs');
  const pending = await api(label + '/pending', prefix + '/actions/runs/' + run.id + '/pending_deployments');
  console.log(JSON.stringify({ runId: run.id, status: observed.status, conclusion: observed.conclusion,
    jobs: jobs.map(j => ({ name: j.name, status: j.status, conclusion: j.conclusion })), pending: pending.map(p => p.environment.name) }));
  if (approve) {
    const context = frozen();
    assert.equal(pending.length, 1); assert.equal(pending[0].environment.id, 24458272742);
    assert.equal(pending[0].environment.name, 'firmware-rehearsal'); assert.equal(pending[0].current_user_can_approve, true);
    assert(!fs.existsSync(destination('approval-reservation.json')), 'Approval already attempted; inspect its audit record');
    const request = { environment_ids: [pending[0].environment.id], state: 'approved',
      comment: 'User-delegated agent approval, P41-STAGING-DELEGATION-20261016; staging only; contract SHA256 '
        + context.contractSha256 + '; commit ' + value.commitSha };
    save('approval-reservation', { runId: run.id, attempt: 1, contractSha256: context.contractSha256,
      actor: 'Eitan-S-23', execution: 'USER_DELEGATED_AGENT_APPROVAL', request });
    await api('approval', prefix + '/actions/runs/' + run.id + '/pending_deployments', { method: 'POST', body: request });
  }
  return observed;
}

async function download(label, route, expectedSize, expectedDigest) {
  const output = destination(label + '.zip'), receipt = destination(label + '-receipt.json');
  assert(!fs.existsSync(output) && !fs.existsSync(receipt));
  let response = await fetch('https://api.github.com' + route, { redirect: 'manual',
    headers: { Authorization: 'Bearer ' + s.githubToken(), Accept: 'application/vnd.github+json' }, signal: AbortSignal.timeout(60000) });
  if (response.status === 302) {
    const url = new URL(response.headers.get('location'));
    assert.equal(url.protocol, 'https:'); assert(!url.username && !url.password);
    assert(['.blob.core.windows.net', '.actions.githubusercontent.com', '.githubusercontent.com'].some(suffix => url.hostname.endsWith(suffix)));
    response = await fetch(url, { redirect: 'error', signal: AbortSignal.timeout(180000) });
  }
  assert.equal(response.status, 200);
  const chunks = []; let length = 0;
  for await (const part of response.body) {
    length += part.length; assert(length <= (expectedSize ?? 256 * 1024 * 1024), 'Download bound exceeded'); chunks.push(part);
  }
  const bytes = Buffer.concat(chunks);
  const artifact = s.write(output, bytes);
  s.writeJson(receipt, { route, status: response.status, artifact, expectedSize, expectedDigest });
  if (expectedSize !== undefined) assert.equal(length, expectedSize);
  if (expectedDigest !== undefined) assert.equal('sha256:' + s.hash(bytes), expectedDigest);
  return artifact;
}

async function collect() {
  const run = read(directory + '/run.json');
  const observed = await status('completed');
  assert.equal(observed.status, 'completed');
  const reviews = await api('completed/reviews', prefix + '/actions/runs/' + run.id + '/approvals');
  await download('completed/logs', prefix + '/actions/runs/' + run.id + '/attempts/1/logs');
  const artifacts = await list('completed/artifacts', prefix + '/actions/runs/' + run.id + '/artifacts', 'artifacts');
  const selected = artifacts.filter(a => a.name === 'p41-rehearsal-' + run.id + '-1');
  assert.equal(selected.length, 1, 'Required rehearsal artifact is missing');
  assert.equal(selected[0].expired, false); assert.equal(selected[0].workflow_run.head_sha, target().commitSha);
  assert(/^sha256:[0-9a-f]{64}$/.test(selected[0].digest));
  const artifact = await download('completed/rehearsal', prefix + '/actions/artifacts/' + selected[0].id + '/zip', selected[0].size_in_bytes, selected[0].digest);
  save('collected', { ok: observed.conclusion === 'success', runId: run.id, conclusion: observed.conclusion,
    artifact, artifactId: selected[0].id, approvals: reviews.length });
}

async function ci() {
  const value = target();
  const runs = await list('ci/runs', prefix + '/actions/runs?event=pull_request&head_sha=' + value.commitSha, 'workflow_runs');
  const paths = ['firmware-build.yml', 'acceptance-governance.yml', 'cloudflare-update-service.yml', 'build.yml'];
  const checked = [];
  for (const name of paths) {
    const selected = runs.filter(run => run.path === '.github/workflows/' + name && run.head_sha === value.commitSha)
      .sort((a,b) => b.id-a.id)[0];
    assert(selected, 'Missing current PR workflow: ' + name);
    assert.equal(selected.status, 'completed'); assert.equal(selected.conclusion, 'success');
    const jobs = await list('ci/' + selected.id + '-jobs', prefix + '/actions/runs/' + selected.id + '/attempts/' + selected.run_attempt + '/jobs', 'jobs');
    assert(jobs.length && jobs.every(job => job.status === 'completed' && ['success', 'skipped'].includes(job.conclusion)));
    checked.push({ name, runId: selected.id, attempt: selected.run_attempt, headSha: selected.head_sha,
      jobs: jobs.map(job => ({ name: job.name, conclusion: job.conclusion, steps: job.steps })) });
  }
  save('ci', { ok: true, sourceCommit: value.commitSha, workflows: checked });
  console.log(JSON.stringify({ ok: true, runs: checked.map(run => run.runId) }));
}

function push() {
  assert.equal(s.git(['branch', '--show-current']), s.branch);
  const env = s.environment();
  env.GIT_CONFIG_COUNT = '1'; env.GIT_CONFIG_KEY_0 = 'http.https://github.com/.extraheader';
  env.GIT_CONFIG_VALUE_0 = 'AUTHORIZATION: basic ' + Buffer.from('x-access-token:' + s.githubToken()).toString('base64');
  const result = cp.spawnSync('git', ['-c', 'credential.helper=', '-c', 'gc.auto=0',
    '-c', 'maintenance.auto=false', 'push', 'origin', 'HEAD:refs/heads/' + s.branch],
  { cwd: s.root, env, encoding: 'utf8', windowsHide: true, timeout: 180000 });
  process.stdout.write(result.stdout ?? ''); process.stderr.write(result.stderr ?? '');
  assert.equal(result.status, 0, 'Scoped branch push failed');
}

function selftest() {
  assert.equal(canonical({ b: [2, { z: 0, a: 1 }], a: 1 }), '{"a":1,"b":[2,{"a":1,"z":0}]}');
  assert.throws(() => destination('../outside'));
  assert.throws(() => s.guard('../outside'));
  assert.equal(Object.keys(desiredVariables({ descriptor: {}, descriptorSha256: 'test' })).length, 4);
  assert.equal(desiredVariables({ descriptor: {}, descriptorSha256: 'test' }).TRACE_FIRMWARE_MIN_PROTOCOL_VERSION, '1');
  console.log(JSON.stringify({ ok: true, checks: 5, remoteActions: 0 }));
}

if (require.main === module) {
  const [mode, label] = process.argv.slice(2);
  Promise.resolve().then(() => {
    if (mode === 'selftest') return selftest();
    if (mode === 'target') return prepareTarget();
    if (mode === 'configure') return configure();
    if (mode === 'github-snapshot') return githubSnapshot(label);
    if (mode === 'dispatch') return dispatch();
    if (mode === 'discover') return discover(label);
    if (mode === 'status') return status(label);
    if (mode === 'approve') return status(label, true);
    if (mode === 'collect') return collect();
    if (mode === 'ci') return ci();
    if (mode === 'push') return push();
    throw Error('Unknown acceptance operation');
  }).catch(error => { console.error(JSON.stringify({ error: error.message, causeCode: error.cause?.code })); process.exitCode = 1; });
}
