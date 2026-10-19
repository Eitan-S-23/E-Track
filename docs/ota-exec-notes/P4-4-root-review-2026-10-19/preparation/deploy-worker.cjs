const io = require('./io.cjs');
const { spawnSync } = require('node:child_process');
const [mode, role, suffix = ''] = process.argv.slice(2);
io.assert.ok(['plan', 'deploy'].includes(mode)); io.assert.ok(['production', 'staging'].includes(role));
io.assert.ok(suffix === '' || suffix === '02' || suffix === '03' || suffix === '04');
const step = mode + (suffix ? '-' + suffix : '');
const http = ['03', '04'].includes(suffix)
  ? require('./curl-io.cjs').createHttp('curl-' + mode + '-' + role + '-' + suffix) : io.http;
const targets = {
  production: { name: 'e-track-firmware-production', bucket: 'e-track-firmware-production-releases',
    d1: '1cd5db26-6bbd-4595-abef-72ff51ecdaf3', environment: 'prod',
    originalConfig: io.worktree + '/.cache/p44/production/wrangler.json', version: 'd4ecbdc7-f097-4ced-b55c-b2f6dfe4c451' },
  staging: { name: 'e-track-firmware-p41-test', bucket: 'e-track-firmware-p41-test-releases',
    d1: '2617e1e1-956f-42ce-a465-da56d84abf06', environment: 'staging',
    originalConfig: io.project + '/.cache/p41-dev-20261015/.cache/cf-firmware-setup-20261015/d1-edit-r2/wrangler.json',
    version: 'db7d28f6-453d-439b-b37e-ef98361e56d9' },
};
const target = targets[role];
const folder = 'deploy/' + role + '/';
const resultPath = io.reserve(folder + step + '.json');
const consolePath = io.reserve(folder + step + '-console.log');
const logPath = io.reserve(folder + step + '-wrangler.log');
const ndjsonPath = io.reserve(folder + step + '-wrangler.ndjson');
const dryRun = io.output(folder + 'dry-run');
const configPath = mode === 'plan' ? io.reserve('private/deploy-' + role + '.json') : io.output('private/deploy-' + role + '.json');
const reservationPath = mode === 'deploy' ? io.reserve(folder + 'deployment-reservation' + (suffix === '04' ? '-04' : '') + '.json') : null;
const contentPath = mode === 'deploy' ? io.reserve(folder + 'deployed-content.bin') : null;
const input = io.readJson(io.output('worker-input-02.json'));
io.assert.equal(input.complete, true);
io.assert.equal(input.commit, 'b56534d7b6c993c0795010d0404fb8a81f7eeb9d');
const runtime = io.fs.readFileSync(io.guard(input.runtime.path));
io.assert.equal(io.sha256(runtime), input.runtime.sha256);
const report = { startedAt: new Date().toISOString(), mode, role, target, sourceCommit: input.commit,
  runtimeSha256: input.runtime.sha256, artifactId: input.artifact.id, requests: [], businessDataWrites: 'NONE_REQUESTED',
  formalAcceptance: 'NOT_RUN', purpose: 'Owner-authorized Worker configuration preparation; no release or device operation' };
const cloud = io.cloudInputs(); const env = io.environment();
const prefix = 'https://api.cloudflare.com/client/v4/accounts/' + cloud.account + '/workers/scripts/' + target.name;
const canonical = value => JSON.stringify(sort(value));
function sort(value) { return Array.isArray(value) ? value.map(sort) : value && typeof value === 'object'
  ? Object.fromEntries(Object.keys(value).sort().map(key => [key, sort(value[key])])) : value; }
function save(file, bytes) { io.guard(file); io.fs.mkdirSync(io.path.dirname(file), { recursive: true }); io.guard(file); io.fs.writeFileSync(file, bytes, { flag: 'wx' }); }
async function get(suffix) {
  io.assert.ok(['/settings', '/deployments', '/schedules'].includes(suffix) || /^\/content\/v2\?version=[0-9a-f-]{36}$/.test(suffix));
  const response = await http(prefix + suffix, { headers: { authorization: 'Bearer ' + cloud.provisioning } }, report.requests);
  io.assert.equal(response.status, 200, 'Required Worker read failed'); return response;
}
async function state() {
  const settings = (await get('/settings')).json.result;
  const deployments = (await get('/deployments')).json.result.deployments;
  const cronResult = (await get('/schedules')).json.result;
  const schedules = Array.isArray(cronResult) ? cronResult : cronResult.schedules;
  io.assert.ok(Array.isArray(schedules));
  const latest = deployments[0];
  io.assert.equal(latest.versions.length, 1); io.assert.equal(latest.versions[0].percentage, 100);
  const bindings = settings.bindings;
  io.assert.equal(bindings.find(x => x.name === 'DB')?.id, target.d1);
  io.assert.equal(bindings.find(x => x.name === 'RELEASES_BUCKET')?.bucket_name, target.bucket);
  io.assert.equal(bindings.find(x => x.name === 'ENVIRONMENT')?.text, target.environment);
  io.assert.equal(settings.observability.redact_query_string, true, 'Preserve query redaction atomically');
  return { settings, version: latest.versions[0].version_id, deploymentId: latest.id,
    crons: schedules.map(x => x.cron).sort() };
}
function runWrangler(args, credential) {
  const executionEnv = { ...env, CLOUDFLARE_API_TOKEN: credential, CLOUDFLARE_ACCOUNT_ID: cloud.account,
    CI: '1', NODE_USE_ENV_PROXY: '1', WRANGLER_LOG: 'log', WRANGLER_LOG_SANITIZE: 'true',
    WRANGLER_LOG_PATH: logPath, WRANGLER_OUTPUT_FILE_DIRECTORY: io.output(folder), WRANGLER_OUTPUT_FILE_PATH: ndjsonPath };
  delete executionEnv.GH_TOKEN; delete executionEnv.GITHUB_TOKEN;
  const cli = io.worktree + '/app/bluetooth_flutter_Trace/cloudflare/update-service/worker/node_modules/wrangler/bin/wrangler.js';
  const fullArgs = [cli, 'deploy', '--no-bundle', '--keep-vars', '--config', configPath, ...args];
  const startedAt = new Date().toISOString();
  const execution = spawnSync(process.execPath, fullArgs, { cwd: io.base, env: executionEnv, windowsHide: true,
    encoding: 'utf8', timeout: 240000, maxBuffer: 8 * 1024 * 1024 });
  const consoleText = io.redact((execution.stdout || '') + (execution.stderr || ''));
  save(consolePath, consoleText);
  report.command = { executable: process.execPath, args: fullArgs, cwd: io.base, startedAt,
    endedAt: new Date().toISOString(), exitCode: execution.status, signal: execution.signal, error: execution.error?.code,
    consolePath, warningLines: consoleText.split(/\r?\n/).filter(x => /warning/i.test(x)).length };
  io.assert.ok(!execution.error && execution.status === 0, 'Wrangler did not report success; reconcile, never blindly retry');
}
async function main() {
  if (suffix === '04') {
    io.assert.equal(mode, 'deploy'); io.assert.equal(role, 'production');
    const previous = io.readJson(io.output(folder + 'deploy-03.json'));
    io.assert.equal(previous.command.exitCode, 1);
    const log = io.fs.readFileSync(io.output(folder + 'deploy-03-wrangler.log'), 'utf8');
    const calls = [...log.matchAll(/START CF API REQUEST: ([A-Z]+) ([^\r\n]+)/g)];
    io.assert.equal(calls.length, 1); io.assert.equal(calls[0][1], 'GET');
    io.assert.ok(calls[0][2].endsWith('/workers/services/' + target.name));
    const service = await http('https://api.cloudflare.com/client/v4/accounts/' + cloud.account + '/workers/services/' + target.name,
      { headers: { authorization: 'Bearer ' + cloud.provisioning } }, report.requests);
    io.assert.equal(service.status, 200, 'Service metadata is still unavailable');
    report.resumeReason = 'Previous CLI stopped at its first read-only service GET; fresh service and old-version checks precede the unperformed upload.';
  }
  if (mode === 'deploy') {
    const token = io.githubToken(env); report.gates = [];
    for (const route of ['actions/variables/OTA_BOOT_CHAIN_READY',
      'environments/firmware-rehearsal/variables/OTA_BOOT_CHAIN_READY',
      'environments/firmware-production/variables/OTA_BOOT_CHAIN_READY']) {
      const response = await http('https://api.github.com/repos/Eitan-S-23/E-Track/' + route,
        { headers: { authorization: 'Bearer ' + token, accept: 'application/vnd.github+json', 'user-agent': 'E-Track-P44-acceptance' } }, report.requests);
      io.assert.equal(response.status, 200, 'Gate readback unavailable');
      io.assert.equal(response.json.value, 'false', 'Gate changed; stop before deployment');
      report.gates.push({ route, value: response.json.value });
    }
  }
  const before = await state(); report.before = before;
  io.assert.equal(before.version, target.version, 'Current Worker changed; stop before replacement');
  if (mode === 'plan') {
    const config = io.readJson(target.originalConfig);
    io.assert.equal(config.name, target.name); io.assert.equal(config.account_id, cloud.account);
    io.assert.equal(config.compatibility_date, before.settings.compatibility_date);
    io.assert.equal(canonical(config.compatibility_flags), canonical(before.settings.compatibility_flags));
    io.assert.equal(config.d1_databases.length, 1); io.assert.equal(config.d1_databases[0].database_id, target.d1);
    io.assert.equal(config.r2_buckets.length, 1); io.assert.equal(config.r2_buckets[0].bucket_name, target.bucket);
    for (const binding of before.settings.bindings) {
      io.assert.ok(['plain_text', 'secret_text', 'd1', 'r2_bucket', 'kv_namespace', 'durable_object_namespace'].includes(binding.type), 'Unreviewed binding type');
      if (binding.type === 'kv_namespace') io.assert.equal(config.kv_namespaces?.find(x => x.binding === binding.name)?.id, binding.namespace_id);
      if (binding.type === 'durable_object_namespace') io.assert.equal(config.durable_objects?.bindings.find(x => x.name === binding.name)?.class_name, binding.class_name);
    }
    config.main = input.runtime.path; config.keep_vars = true;
    delete config.vars; delete config.migrations;
    config.triggers = { crons: before.crons };
    // The post-deployment non-versioned PATCH reads this object, not unsafe
    // upload metadata. The pinned JSON config parser retains unknown fields.
    config.observability = before.settings.observability;
    // Wrangler 4.105.0 supports this passthrough; its typed observability schema
    // does not yet expose redact_query_string. Preserve the live API value.
    config.unsafe = { metadata: { observability: before.settings.observability,
      annotations: { 'workers/message': 'P4-4 configuration; tested CI source ' + input.commit,
        'workers/tag': 'p44-' + input.commit.slice(0, 12) } } };
    const configBytes = Buffer.from(JSON.stringify(config, null, 2) + '\n'); save(configPath, configBytes);
    report.config = { path: configPath, sha256: io.sha256(configBytes) };
    runWrangler(['--dry-run', '--outdir', dryRun], '');
    report.complete = true; return;
  }
  const planSuffix = suffix === '04' ? '03' : suffix;
  const plan = io.readJson(io.output(folder + 'plan' + (planSuffix ? '-' + planSuffix : '') + '.json'));
  io.assert.equal(plan.complete, true); io.assert.equal(plan.runtimeSha256, input.runtime.sha256);
  io.assert.equal(io.sha256(io.fs.readFileSync(configPath)), plan.config.sha256);
  io.assert.equal(canonical(before.settings), canonical(plan.before.settings), 'Settings drifted since plan');
  io.assert.equal(canonical(before.crons), canonical(plan.before.crons), 'Cron state drifted since plan');
  io.writeJson(reservationPath, { role, target, sourceCommit: input.commit, runtimeSha256: input.runtime.sha256,
    priorVersion: before.version, reservedAt: new Date().toISOString(), mutationsAllowed: 'One Worker deploy only; preserve all bindings, secrets, crons and query redaction' });
  runWrangler([], cloud.provisioning);
  const after = await state(); report.after = after;
  io.assert.notEqual(after.version, before.version, 'No successor version was observed');
  const bindingOrder = bindings => [...bindings].sort((a, b) => a.name.localeCompare(b.name));
  io.assert.equal(canonical(bindingOrder(after.settings.bindings)), canonical(bindingOrder(before.settings.bindings)), 'Binding changed during code-only deployment');
  io.assert.equal(after.settings.compatibility_date, before.settings.compatibility_date, 'Compatibility date changed');
  io.assert.equal(canonical(after.settings.compatibility_flags), canonical(before.settings.compatibility_flags), 'Compatibility flags changed');
  io.assert.equal(canonical(after.settings.observability), canonical(before.settings.observability), 'Observability changed');
  io.assert.equal(canonical(after.crons), canonical(before.crons), 'Cron changed');
  const response = await get('/content/v2?version=' + after.version);
  save(contentPath, response.bytes);
  const contentType = response.headers['content-type'];
  io.assert.ok(contentType.startsWith('multipart/form-data'), 'Expected module Worker content');
  const form = await new Response(response.bytes, { headers: { 'content-type': contentType } }).formData();
  const entrypoint = response.headers['cf-entrypoint'];
  io.assert.equal(entrypoint, 'index.js');
  const part = form.get(entrypoint); io.assert.ok(part && typeof part.arrayBuffer === 'function');
  const downloaded = Buffer.from(await part.arrayBuffer());
  io.assert.equal(io.sha256(downloaded), input.runtime.sha256, 'Deployed module differs from tested input');
  const codeParts = [...form.entries()].filter(([, value]) => value.type !== 'application/source-map').map(([name]) => name);
  io.assert.deepEqual(codeParts, ['index.js'], 'Unexpected additional deployed module');
  report.content = { path: contentPath, sha256: io.sha256(response.bytes), contentType, entrypoint,
    moduleSha256: io.sha256(downloaded), moduleBytes: downloaded.length, codeParts };
  report.complete = true;
}
main().catch(error => { report.error = io.redact(error.message); process.exitCode = 1; }).finally(() => {
  report.endedAt = new Date().toISOString(); io.writeJson(resultPath, report);
  process.stdout.write(JSON.stringify({ output: resultPath, mode, role, complete: report.complete || false,
    version: report.after?.version, deploymentId: report.after?.deploymentId, error: report.error }) + '\n');
});
