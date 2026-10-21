const io = require('./io.cjs');
const output = io.reserve('verify-permissions-02.json');
const env = io.environment();
const cloud = io.cloudInputs();
const report = {
  startedAt: new Date().toISOString(), kind: 'READ_ONLY_PERMISSION_REFRESH_AFTER_OWNER_UPDATE',
  formalAcceptance: 'NOT_RUN', requests: [], checks: {}, writesRequested: 0,
};
const expectedNames = [
  'e-track-firmware-production-s3-ci-20261019',
  'e-track-firmware-p41-test-s3-ci-20261019',
];
async function get(name, credential, route) {
  const result = await io.http('https://api.cloudflare.com/client/v4/' + route, {
    headers: { authorization: 'Bearer ' + credential },
  }, report.requests);
  const value = result.json?.result;
  if (value?.id) io.sensitive.add(value.id);
  if (Array.isArray(value)) for (const item of value) if (item.id && item.policies) io.sensitive.add(item.id);
  report.checks[name] = {
    status: result.status, success: result.json?.success === true,
    errorCodes: result.json?.errors?.map(x => x.code),
    resultInfo: result.json?.result_info,
  };
  return result;
}
async function main() {
  io.assert.notEqual(cloud.provisioning, cloud.ci, 'Provisioning and CI credentials must remain distinct');
  const verified = await get('localTokenActive', cloud.provisioning, 'user/tokens/verify');
  io.assert.equal(verified.status, 200, 'Local provisioning credential could not be verified');
  io.assert.equal(verified.json.result.status, 'active', 'Local provisioning credential is not active');
  report.checks.localTokenActive.tokenIdSha256 = io.sha256(verified.json.result.id);
  const catalog = await get('localAccountPermissionCatalog', cloud.provisioning,
    'accounts/' + cloud.account + '/tokens/permission_groups');
  io.assert.equal(catalog.status, 200, 'Updated local account-token permission is not effective');
  io.assert.equal(catalog.json.success, true);
  io.assert.ok(Array.isArray(catalog.json.result), 'Unexpected permission catalog');
  const wanted = catalog.json.result.filter(x =>
    ['Workers R2 Storage Bucket Item Write', 'Account API Tokens Write', 'Account API Tokens Read'].includes(x.name));
  report.permissionGroups = wanted;
  const bucket = wanted.filter(x => x.name === 'Workers R2 Storage Bucket Item Write');
  io.assert.equal(bucket.length, 1, 'Exactly one live bucket Object RW group is required');
  io.assert.equal(bucket[0].id, '2efd5506f9c8494dacb1fa10a3e7d5b6', 'Live group differs from prior public reference');
  const ciCatalog = await get('existingCiAccountPermissionCatalog', cloud.ci,
    'accounts/' + cloud.account + '/tokens/permission_groups');
  io.assert.equal(ciCatalog.status, 403, 'CI management access changed; do not provision until reconciled');
  io.assert.equal(ciCatalog.json?.success, false);
  const listed = await get('accountTokenDirectory', cloud.provisioning,
    'accounts/' + cloud.account + '/tokens?page=1&per_page=100');
  io.assert.equal(listed.status, 200, 'Cannot reconcile existing account tokens before creation');
  io.assert.equal(listed.json.success, true);
  io.assert.ok(Array.isArray(listed.json.result));
  const info = listed.json.result_info;
  io.assert.ok(!info || ((info.total_pages ?? 1) <= 1 &&
    (info.total_count ?? listed.json.result.length) === listed.json.result.length), 'Directory pagination is incomplete');
  report.existingTokenCount = listed.json.result.length;
  report.nameCollisions = listed.json.result.filter(x => expectedNames.includes(x.name)).map(x => ({
    name: x.name, idSha256: io.sha256(x.id), status: x.status, expiresOn: x.expires_on,
  }));
  io.assert.equal(report.nameCollisions.length, 0, 'Existing matching token requires reconciliation, not replacement');
  report.complete = true;
  report.disposition = 'READS_PASSED_CREATE_STILL_UNTESTED';
}
main().catch(error => {
  report.error = io.redact(error.message);
  report.disposition = 'READ_CHECK_STOPPED_NO_MUTATION';
  process.exitCode = 1;
}).finally(() => {
  report.endedAt = new Date().toISOString();
  io.writeJson(output, report);
  process.stdout.write(JSON.stringify({ output, complete: report.complete || false, checks: report.checks,
    permissionGroups: report.permissionGroups, nameCollisions: report.nameCollisions,
    disposition: report.disposition, error: report.error }) + '\n');
});
