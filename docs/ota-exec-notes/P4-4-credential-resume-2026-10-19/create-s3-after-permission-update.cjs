const io = require('./io.cjs');
const { createHttp } = require('./curl-io.cjs');
const { spawnSync } = require('node:child_process');
const [role, sequence] = process.argv.slice(2);
io.assert.ok(['production', 'staging'].includes(role));
io.assert.match(sequence || '', /^[0-9]{2}$/);
const label = 'create-s3-' + role + '-' + sequence;
const destination = io.reserve(label + '.json');
const reservation = io.reserve(label + '-reservation.json');
const privateDirectory = io.output('private');
const rawResponse = io.reserve('private/' + label + '-response.json');
const privatePair = io.reserve('private/' + label + '-pair.json');
const readHttp = createHttp('curl-' + label + '-precheck');
const env = io.environment();
const cloud = io.cloudInputs();
const admission = io.readJson(io.output('refresh-admission-04.json'));
const localCheck = io.readJson(io.output('verify-permissions-03.json'));
const environmentName = role === 'production' ? 'firmware-production' : 'firmware-rehearsal';
const bucket = role === 'production' ? 'e-track-firmware-production-releases' : 'e-track-firmware-p41-test-releases';
const tokenName = role === 'production' ? 'e-track-firmware-production-s3-ci-20261019' : 'e-track-firmware-p41-test-s3-ci-20261019';
const prefix = role === 'production' ? '' : 'FIRMWARE_REHEARSAL_';
const expectedSecrets = ['TRACE_R2_ACCESS_KEY_ID', 'TRACE_R2_SECRET_ACCESS_KEY'].map(x => prefix + x);
const group = { id: '2efd5506f9c8494dacb1fa10a3e7d5b6', name: 'Workers R2 Storage Bucket Item Write' };
const report = {
  startedAt: new Date().toISOString(), role, environmentName, bucket, tokenName,
  ownerStateChange: 'Owner reports local Account API Tokens Edit updated; verify actual account POST, not catalog inference',
  formalAcceptance: 'NOT_RUN', configuredToGitHub: false, created: 'NOT_ATTEMPTED', requests: [],
  permissionGroup: group, credentialSource: 'Existing local provisioning credential, not e-track-ci',
  scope: 'One exact bucket, Object Read and Write; includes DELETE capability at platform granularity, never used by this application',
  policyBasis: 'Public documented single-bucket syntax and corroborated group ID; require service-resolved exact group and independent GET before consumption',
  automaticWriteRetry: false, route: 'account-owned-only',
};
async function get(route, credential) {
  return readHttp('https://api.cloudflare.com/client/v4/' + route, {
    headers: { authorization: 'Bearer ' + credential },
  }, report.requests);
}
function verifyPolicy(result, resource, expiresOn) {
  io.assert.equal(result.name, tokenName);
  io.assert.equal(result.status, 'active');
  io.assert.equal(result.policies?.length, 1);
  const policy = result.policies[0];
  io.assert.equal(policy.effect, 'allow');
  io.assert.deepEqual(policy.resources, { [resource]: '*' });
  io.assert.deepEqual(policy.permission_groups, [group]);
  io.assert.equal(new Date(result.expires_on).getTime(), Date.parse(expiresOn));
  io.assert.ok(!result.condition || Object.keys(result.condition).length === 0);
}
async function main() {
  io.assert.notEqual(cloud.provisioning, cloud.ci);
  io.assert.equal(localCheck.credentials.provisioning.verify.active, true);
  io.assert.ok(Date.now() - Date.parse(localCheck.endedAt) < 30 * 60 * 1000, 'Refresh stale credential evidence');
  io.assert.ok(Date.now() - Date.parse(admission.endedAt) < 30 * 60 * 1000, 'Refresh stale environment inventory');
  // The tenth main-ref GET failed at TLS; the preceding nine successful reads remain valid originals.
  io.assert.equal(admission.requests.slice(0, 9).every(x => x.status === 200), true);
  io.assert.equal(admission.repositoryGate.value, 'false');
  for (const item of Object.values(admission.environments)) {
    io.assert.equal(item.variables.find(x => x.name === 'OTA_BOOT_CHAIN_READY').value, 'false');
  }
  io.assert.deepEqual(admission.environments[environmentName].missingS3Secrets, expectedSecrets);
  const identity = spawnSync('whoami.exe', [], { cwd: io.project, env, encoding: 'utf8', windowsHide: true });
  io.assert.equal(identity.status, 0);
  const acl = spawnSync('icacls.exe', [privateDirectory], { cwd: io.project, env, encoding: 'utf8', windowsHide: true });
  io.assert.equal(acl.status, 0);
  const entries = acl.stdout.split(/\r?\n/).filter(x => /:\(/.test(x));
  io.assert.equal(entries.length, 1, 'Unexpected private-directory ACL');
  io.assert.ok(entries[0].toLowerCase().includes(identity.stdout.trim().toLowerCase() + ':(oi)(ci)(f)'), 'Private output must remain current-user-only');
  report.privateOutput = { directory: privateDirectory, currentUserOnly: true, rawResponse, privatePair };
  const ci = await get('accounts/' + cloud.account + '/tokens/permission_groups', cloud.ci);
  report.existingCiManagementCatalog = { status: ci.status, success: ci.json?.success, errors: ci.json?.errors };
  io.assert.equal(ci.status, 403, 'Existing CI management access changed; reconcile scope before proceeding');
  io.assert.equal(ci.json?.success, false);
  const directory = await get('accounts/' + cloud.account + '/tokens?page=1&per_page=100', cloud.provisioning);
  report.directoryCheck = { status: directory.status, success: directory.json?.success, errors: directory.json?.errors };
  if (directory.status === 200) {
    const rows = directory.json.result;
    const info = directory.json.result_info;
    io.assert.ok(Array.isArray(rows));
    io.assert.ok(!info || ((info.total_pages ?? 1) <= 1 && (info.total_count ?? rows.length) === rows.length));
    io.assert.equal(rows.some(x => x.name === tokenName), false, 'Matching credential already exists; do not duplicate');
  } else {
    io.assert.equal(directory.status, 403);
    io.assert.equal(directory.json?.success, false);
    const old = io.readJson(io.output('create-s3-production-01.json'));
    io.assert.equal(old.created, false);
    io.assert.ok(old.attempts.every(x => x.status === 403 && x.success === false));
    report.directoryLimit = 'Read denied; no earlier ambiguous or successful create. One exact account POST follows reported permission change.';
  }
  const expiresOn = new Date(Math.floor(Date.now() / 1000) * 1000 + 90 * 86400000).toISOString().replace('.000Z', 'Z');
  const resource = 'com.cloudflare.edge.r2.bucket.' + cloud.account + '_default_' + bucket;
  const body = { name: tokenName, expires_on: expiresOn,
    policies: [{ effect: 'allow', resources: { [resource]: '*' }, permission_groups: [{ id: group.id }] }] };
  report.expiresOnRequested = expiresOn;
  io.writeJson(reservation, { ...report, status: 'RESERVED_BEFORE_POST', permittedPosts: 1 });
  report.created = 'UNKNOWN_PENDING_RESULT';
  const response = await io.http('https://api.cloudflare.com/client/v4/accounts/' + cloud.account + '/tokens', {
    method: 'POST', headers: { authorization: 'Bearer ' + cloud.provisioning, 'content-type': 'application/json' },
    body: JSON.stringify(body),
  }, report.requests);
  const result = response.json?.result;
  if (result?.value) io.sensitive.add(result.value);
  if (result?.id) io.sensitive.add(result.id);
  // Preserve the one-time credential response before any semantic assertion can fail.
  io.guard(rawResponse);
  io.fs.writeFileSync(rawResponse, response.bytes, { flag: 'wx', mode: 0o600 });
  report.createResponse = { status: response.status, success: response.json?.success, errors: response.json?.errors };
  if (response.status === 403 && response.json?.success === false && !result?.id && !result?.value) {
    report.created = false;
    report.disposition = 'ACTUAL_ACCOUNT_CREATE_DENIED_AFTER_OWNER_PERMISSION_UPDATE';
    process.exitCode = 2;
    return;
  }
  io.assert.ok(response.status >= 200 && response.status < 300 && response.json?.success === true, 'Unexpected create response; reconcile, never retry');
  report.created = true;
  io.assert.match(result?.id || '', /^[0-9a-f]{32}$/);
  io.assert.ok(typeof result.value === 'string' && result.value.length >= 32);
  const secretAccessKey = io.sha256(result.value);
  io.sensitive.add(secretAccessKey);
  verifyPolicy(result, resource, expiresOn);
  const check = await io.http('https://api.cloudflare.com/client/v4/accounts/' + cloud.account + '/tokens/' + result.id, {
    headers: { authorization: 'Bearer ' + cloud.provisioning },
  }, report.requests);
  io.assert.equal(check.status, 200, 'Created credential retained privately; policy GET required before use');
  io.assert.equal(check.json.success, true);
  verifyPolicy(check.json.result, resource, expiresOn);
  io.guard(privatePair);
  io.fs.writeFileSync(privatePair, JSON.stringify({ accessKeyId: result.id, secretAccessKey, tokenName, bucket,
    accountSha256: io.sha256(cloud.account), environmentName, expiresOn, verifiedPolicy: true,
    policyResponseSha256: io.sha256(check.bytes), sourceResponse: rawResponse }, null, 2) + '\n', { flag: 'wx', mode: 0o600 });
  report.verifiedPolicy = true;
  report.tokenIdSha256 = io.sha256(result.id);
  report.resolvedPolicies = check.json.result.policies;
  report.disposition = 'CREATED_AND_POLICY_READBACK_VERIFIED_NOT_YET_CONFIGURED';
}
main().catch(error => {
  report.error = io.redact(error.message);
  report.disposition = 'STOP_AND_RECONCILE_NO_WRITE_RETRY';
  process.exitCode = 1;
}).finally(() => {
  report.endedAt = new Date().toISOString();
  io.writeJson(destination, report);
  process.stdout.write(io.redact({ output: destination, role, created: report.created,
    existingCiManagementCatalog: report.existingCiManagementCatalog, directoryCheck: report.directoryCheck,
    createResponse: report.createResponse, verifiedPolicy: report.verifiedPolicy || false,
    configuredToGitHub: false, disposition: report.disposition, error: report.error }) + '\n');
});
