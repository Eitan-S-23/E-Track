const io = require('./io.cjs');
const { spawnSync } = require('node:child_process');
const role = process.argv[2];
io.assert.ok(['production', 'staging'].includes(role), 'Exact environment required');
const label = 'create-s3-' + role + '-01';
const destination = io.reserve(label + '.json');
const reservation = io.reserve(label + '-reservation.json');
const privateDirectory = io.output('private');
const privatePath = io.reserve('private/' + role + '-s3-20261019.json');
const prior = io.readJson(io.output('platform-preparation-02.json'));
io.assert.equal(prior.complete, true);
const environmentName = role === 'production' ? 'firmware-production' : 'firmware-rehearsal';
const expectedSecrets = role === 'production' ? ['TRACE_R2_ACCESS_KEY_ID', 'TRACE_R2_SECRET_ACCESS_KEY']
  : ['FIRMWARE_REHEARSAL_TRACE_R2_ACCESS_KEY_ID', 'FIRMWARE_REHEARSAL_TRACE_R2_SECRET_ACCESS_KEY'];
io.assert.ok(prior.github[environmentName].secrets.every(x => !expectedSecrets.includes(x.name)), 'Do not replace an existing pair');
const group = { id: '2efd5506f9c8494dacb1fa10a3e7d5b6', name: 'Workers R2 Storage Bucket Item Write' };
const bucket = role === 'production' ? 'e-track-firmware-production-releases' : 'e-track-firmware-p41-test-releases';
const name = role === 'production' ? 'e-track-firmware-production-s3-ci-20261019' : 'e-track-firmware-p41-test-s3-ci-20261019';
const report = { startedAt: new Date().toISOString(), purpose: 'Owner-delegated strict bucket S3 credential provisioning',
  role, environmentName, bucket, name, permissionGroup: group, requests: [], attempts: [], configuredToGitHub: false,
  policyEvidence: 'Two public Cloudflare-provider issue examples corroborate ID; service response must independently resolve the name.',
  policySources: ['https://github.com/cloudflare/terraform-provider-cloudflare/issues/5967',
    'https://github.com/cloudflare/terraform-provider-cloudflare/issues/3227',
    'https://developers.cloudflare.com/r2/api/tokens/',
    'https://developers.cloudflare.com/fundamentals/api/how-to/create-via-api/'],
  scopeLimit: 'One exact bucket, Object Read and Write; platform granularity includes object deletion. No account/Worker/D1/token-management grants.',
  automaticRetry: false, formalAcceptance: 'NOT_RUN' };
const env = io.environment();
const cloud = io.cloudInputs();
async function main() {
  // Establish the private output ACL before any secret can be returned.
  const identity = spawnSync('whoami.exe', ['/user', '/fo', 'csv', '/nh'], { cwd: io.project, env, encoding: 'utf8', windowsHide: true });
  io.assert.equal(identity.status, 0, 'Cannot establish private-file owner');
  const sid = identity.stdout.match(/S-1-5-(?:[0-9]+-)*[0-9]+/g);
  io.assert.equal(sid?.length, 1, 'Ambiguous private-file owner');
  io.guard(privateDirectory); io.fs.mkdirSync(privateDirectory, { recursive: true });
  const acl = spawnSync('icacls.exe', [privateDirectory, '/inheritance:r', '/grant:r', '*' + sid[0] + ':(OI)(CI)F'],
    { cwd: io.project, env, windowsHide: true, encoding: 'utf8', timeout: 30000 });
  io.assert.equal(acl.status, 0, 'Private output ACL was not established');
  report.privateOutput = { path: privatePath, currentUserOnly: true, aclExitCode: acl.status };
  const expiresOn = new Date(Date.now() + 90 * 24 * 60 * 60 * 1000).toISOString();
  const resource = 'com.cloudflare.edge.r2.bucket.' + cloud.account + '_default_' + bucket;
  const policy = { effect: 'allow', resources: { [resource]: '*' }, permission_groups: [{ id: group.id }] };
  const body = { name, expires_on: expiresOn, policies: [policy] };
  report.expiresOnRequested = expiresOn;
  io.writeJson(reservation, { ...report, status: 'RESERVED_BEFORE_POST',
    permittedRoutes: ['account-owned', 'user-owned-only-after-definite-account-403'], credentialSource: 'Existing local provisioning token; never exported' });
  for (const route of ['accounts/' + cloud.account + '/tokens', 'user/tokens']) {
    const response = await io.http('https://api.cloudflare.com/client/v4/' + route, {
      method: 'POST', headers: { authorization: 'Bearer ' + cloud.provisioning, 'content-type': 'application/json' },
      body: JSON.stringify(body),
    }, report.requests);
    const result = response.json?.result;
    if (result?.value) io.sensitive.add(result.value);
    if (result?.id) io.sensitive.add(result.id);
    const attempt = { endpoint: route.startsWith('accounts/') ? 'account-owned' : 'user-owned', status: response.status,
      success: response.json?.success === true, errorCodes: response.json?.errors?.map(x => x.code) };
    report.attempts.push(attempt);
    if (response.status === 403 && response.json?.success === false && !result?.id && !result?.value) continue;
    io.assert.ok(response.status >= 200 && response.status < 300 && response.json?.success === true, 'Unexpected creation response; reconcile without retry');
    io.assert.match(result?.id || '', /^[0-9a-f]{32}$/);
    io.assert.ok(typeof result.value === 'string' && result.value.length >= 32, 'Creation returned no usable token value');
    const key = io.sha256(result.value); io.sensitive.add(key);
    const privateValue = { accessKeyId: result.id, secretAccessKey: key, tokenName: name, bucket,
      accountSha256: io.sha256(cloud.account), tokenEndpoint: attempt.endpoint, createdAt: new Date().toISOString(),
      expiresOn: result.expires_on, environmentName, verifiedPolicy: false };
    io.guard(privatePath);
    io.fs.writeFileSync(privatePath, JSON.stringify(privateValue, null, 2) + '\n', { flag: 'wx', mode: 0o600 });
    report.created = true; report.tokenIdSha256 = io.sha256(result.id);
    const policies = result.policies;
    report.resolvedPolicies = policies;
    io.assert.equal(policies?.length, 1, 'Unexpected policy count; do not consume credential');
    io.assert.equal(policies[0].effect, 'allow', 'Unexpected policy effect');
    io.assert.deepEqual(policies[0].resources, { [resource]: '*' }, 'Unexpected resource scope; do not consume credential');
    io.assert.equal(policies[0].permission_groups?.length, 1, 'Unexpected permission count');
    io.assert.equal(policies[0].permission_groups[0].id, group.id, 'Unexpected resolved permission ID');
    // The request intentionally omitted the cosmetic name, so it cannot be our own echo.
    io.assert.equal(policies[0].permission_groups[0].name, group.name, 'Permission name was not independently resolved');
    io.assert.equal(result.name, name, 'Unexpected token name');
    io.assert.equal(new Date(result.expires_on).getTime(), new Date(expiresOn).getTime(), 'Unexpected token lifetime');
    report.verifiedPolicy = true;
    return;
  }
  report.created = false;
  report.disposition = 'ENV_BLOCKED: both documented strict creation routes returned an explicit 403. No pair or GitHub secret was created.';
  process.exitCode = 2;
}
main().catch(error => { report.error = io.redact(error.message); report.disposition = 'STOP_AND_RECONCILE_NO_RETRY'; process.exitCode = 1; }).finally(() => {
  report.endedAt = new Date().toISOString(); io.writeJson(destination, report);
  process.stdout.write(JSON.stringify({ output: destination, role, created: report.created, verifiedPolicy: report.verifiedPolicy || false,
    attempts: report.attempts, disposition: report.disposition, error: report.error, configuredToGitHub: false }) + '\n');
});
