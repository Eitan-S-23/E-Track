const io = require('./io.cjs');
const resultPath = io.reserve('deploy/staging/redaction-recovery.json');
const reservationPath = io.reserve('deploy/staging/redaction-recovery-reservation.json');
const contentPath = io.reserve('deploy/staging/recovered-content.bin');
const prior = io.readJson(io.output('deploy/staging/deploy.json'));
const input = io.readJson(io.output('worker-input-02.json'));
io.assert.equal(prior.command.exitCode, 0);
io.assert.equal(prior.before.settings.observability.redact_query_string, true);
const cloud = io.cloudInputs();
const prefix = 'https://api.cloudflare.com/client/v4/accounts/' + cloud.account + '/workers/scripts/e-track-firmware-p41-test';
const report = { startedAt: new Date().toISOString(), purpose: 'Restore the pre-deployment query-redaction invariant only',
  requests: [], noWorkerBusinessRequests: true, formalAcceptance: 'NOT_RUN' };
const headers = { authorization: 'Bearer ' + cloud.provisioning, 'content-type': 'application/json' };
async function get(suffix) {
  const response = await io.http(prefix + suffix, { headers }, report.requests);
  io.assert.equal(response.status, 200); return response;
}
async function main() {
  const before = (await get('/settings')).json.result;
  const deployment = (await get('/deployments')).json.result.deployments[0];
  const version = deployment.versions[0].version_id;
  io.assert.equal(version, 'bb3d44fd-4a84-489e-9e04-6adfc54a458e', 'Unexpected staging successor; stop before settings write');
  report.before = before; report.version = version; report.deploymentId = deployment.id;
  if (before.observability.redact_query_string !== true) {
    io.writeJson(reservationPath, { scope: 'staging script-settings.observability only', version,
      observedAt: new Date().toISOString(), expected: prior.before.settings.observability, automaticRetry: false });
    const response = await io.http(prefix + '/script-settings', { method: 'PATCH', headers,
      body: JSON.stringify({ observability: prior.before.settings.observability }) }, report.requests);
    io.assert.equal(response.status, 200, 'Redaction restore did not return success; reconcile without retry');
    io.assert.equal(response.json?.success, true); report.settingsWrite = true;
  }
  const after = (await get('/settings')).json.result; report.after = after;
  io.assert.equal(after.observability.redact_query_string, true, 'Query redaction not restored');
  io.assert.deepEqual(after.bindings, prior.before.settings.bindings, 'Bindings changed during deployment');
  io.assert.deepEqual(after.observability, prior.before.settings.observability, 'Unexpected observability settings after restore');
  io.assert.equal(after.compatibility_date, prior.before.settings.compatibility_date);
  io.assert.deepEqual(after.compatibility_flags, prior.before.settings.compatibility_flags);
  const scheduleResult = (await get('/schedules')).json.result;
  const schedules = Array.isArray(scheduleResult) ? scheduleResult : scheduleResult.schedules;
  report.crons = schedules.map(x => x.cron).sort();
  io.assert.deepEqual(report.crons, prior.before.crons);
  const content = await get('/content/v2?version=' + version);
  io.guard(contentPath); io.fs.writeFileSync(contentPath, content.bytes, { flag: 'wx' });
  const contentType = content.headers['content-type'];
  const form = await new Response(content.bytes, { headers: { 'content-type': contentType } }).formData();
  const entrypoint = content.headers['cf-entrypoint']; io.assert.equal(entrypoint, 'index.js');
  const bytes = Buffer.from(await form.get(entrypoint).arrayBuffer());
  io.assert.equal(io.sha256(bytes), input.runtime.sha256);
  io.assert.deepEqual([...form.entries()].filter(([, file]) => file.type !== 'application/source-map').map(([name]) => name), ['index.js']);
  report.content = { path: contentPath, contentType, entrypoint, sha256: io.sha256(content.bytes),
    moduleSha256: io.sha256(bytes), moduleBytes: bytes.length };
  report.complete = true;
}
main().catch(error => { report.error = io.redact(error.message); process.exitCode = 1; }).finally(() => {
  report.endedAt = new Date().toISOString(); io.writeJson(resultPath, report);
  process.stdout.write(JSON.stringify({ output: resultPath, complete: report.complete || false,
    version: report.version, redactionRestored: report.after?.observability?.redact_query_string === true, error: report.error }) + '\n');
});
