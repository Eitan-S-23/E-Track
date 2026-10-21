const io = require('./io.cjs');
const destination = io.reserve('d1-preparation-01.json');
const cloud = io.cloudInputs();
const report = { startedAt: new Date().toISOString(), kind: 'CONFIGURATION_PREPARATION_FIXED_D1_READS',
  formalAcceptance: 'NOT_RUN', businessMutations: 'NONE_REQUESTED', requests: [], databases: [] };
const queries = [
  { id: 'unresolved', sql: 'SELECT COUNT(*) AS count FROM firmware_channels WHERE app_id=? AND device_model=? AND legacy_current_release_id IS NOT NULL' },
  { id: 'legacy', sql: 'SELECT MAX(version_code) AS version_code FROM firmware_releases_legacy WHERE app_id=? AND device_model=?' },
  { id: 'latest', sql: 'SELECT version_code,registration_json FROM firmware_releases WHERE app_id=? AND device_model=? ORDER BY version_code DESC LIMIT 1' },
];
async function main() {
  for (const [name, id] of [['e-track-firmware-production', '1cd5db26-6bbd-4595-abef-72ff51ecdaf3'],
    ['e-track-firmware-p41-test', '2617e1e1-956f-42ce-a465-da56d84abf06']]) {
    const state = { name, id, observations: [] }; report.databases.push(state);
    for (const query of queries) {
      const response = await io.http('https://api.cloudflare.com/client/v4/accounts/' + cloud.account + '/d1/database/' + id + '/query', {
        method: 'POST', headers: { authorization: 'Bearer ' + cloud.ci, 'content-type': 'application/json' },
        body: JSON.stringify({ sql: query.sql, params: ['trace', 'e-track-at32f435'] }),
      }, report.requests);
      io.assert.equal(response.status, 200, 'Fixed D1 read failed');
      io.assert.equal(response.json?.success, true);
      io.assert.ok(response.json.result?.every(x => x.success === true));
      state.observations.push({ id: query.id, sql: query.sql, params: ['trace', 'e-track-at32f435'], result: response.json.result });
      for (const item of response.json.result) {
        if (item.meta?.rows_written !== undefined) io.assert.equal(item.meta.rows_written, 0, 'Read query unexpectedly reports writes');
      }
    }
  }
  report.complete = true;
}
main().catch(error => { report.error = io.redact(error.message); process.exitCode = 1; }).finally(() => {
  report.endedAt = new Date().toISOString(); io.writeJson(destination, report);
  process.stdout.write(JSON.stringify({ output: destination, complete: report.complete || false, error: report.error,
    databases: report.databases.map(x => ({ name: x.name, queriesCompleted: x.observations.length,
      latestVersionCode: x.observations.find(y => y.id === 'latest')?.result[0]?.results[0]?.version_code ?? null })) }) + '\n');
});
