const io = require('./io.cjs');
const { assert } = io;
const [label] = process.argv.slice(2);
assert.match(label || '', /^[a-z0-9-]+$/);
const destination = io.reserve(label + '.json');
const report = { startedAt: new Date().toISOString(), kind: 'CONFIGURATION_PREPARATION_READ_ONLY',
  formalAcceptance: 'NOT_RUN', businessMutations: 'NONE', requests: [] };
const env = io.environment();
const cloud = io.cloudInputs();
const ghToken = io.githubToken(env);
async function cf(route, token) {
  const response = await io.http('https://api.cloudflare.com/client/v4/' + route,
    { headers: { authorization: 'Bearer ' + token } }, report.requests);
  if (response.status !== 200) return { available: false, status: response.status, codes: response.json?.errors?.map(e => e.code) };
  return { available: true, result: response.json?.result, resultInfo: response.json?.result_info };
}
async function gh(route) {
  const response = await io.http('https://api.github.com/repos/Eitan-S-23/E-Track/' + route,
    { headers: { authorization: 'Bearer ' + ghToken, accept: 'application/vnd.github+json', 'user-agent': 'E-Track-P44-acceptance',
      'x-github-api-version': '2022-11-28' } }, report.requests);
  assert.equal(response.status, 200, 'GitHub read failed: ' + route);
  return response.json;
}
async function main() {
  report.credentials = {};
  for (const [name, token] of [['provisioning', cloud.provisioning], ['existingCi', cloud.ci]]) {
    const verification = await cf('user/tokens/verify', token);
    report.credentials[name] = { active: verification.result?.status === 'active', verifyStatus: verification.available ? 200 : verification.status };
    const groups = await cf('user/tokens/permission_groups', token);
    report.credentials[name].permissionGroups = groups.available ? {
      available: true, selected: groups.result.filter(x => /Workers R2 Storage Bucket Item|API Tokens/.test(x.name)),
    } : groups;
    // An account-owned token may authorize the account catalog but not the user catalog.
    const accountGroups = await cf('accounts/' + cloud.account + '/tokens/permission_groups', token);
    report.credentials[name].accountPermissionGroups = accountGroups.available ? {
      available: true, selected: accountGroups.result.filter(x => /Workers R2 Storage Bucket Item|API Tokens/.test(x.name)),
    } : accountGroups;
  }
  const safeVars = new Set(['ENVIRONMENT', 'APP_ID', 'GITHUB_OWNER', 'GITHUB_REPO', 'DOWNLOAD_TOKEN_KEY_VERSION',
    'DOWNLOAD_TOKEN_TTL_SECONDS', 'FIRMWARE_V2_CUTOVER_EPOCH']);
  report.workers = [];
  for (const name of ['e-track-firmware-production', 'e-track-firmware-p41-test']) {
    const settings = await cf('accounts/' + cloud.account + '/workers/scripts/' + name + '/settings', cloud.ci);
    const deployments = await cf('accounts/' + cloud.account + '/workers/scripts/' + name + '/deployments', cloud.ci);
    report.workers.push({ name, settings: settings.available ? {
      bindings: settings.result.bindings.map(x => ({ name: x.name, type: x.type,
        ...(x.type === 'plain_text' && safeVars.has(x.name) ? { value: x.text } : {}),
        ...(x.type === 'r2_bucket' ? { bucketName: x.bucket_name } : {}),
        ...(x.type === 'd1' ? { databaseId: x.id } : {}) })),
      observability: settings.result.observability,
    } : settings, deployments });
  }
  report.github = {};
  for (const name of ['firmware-production', 'firmware-rehearsal']) {
    const base = 'environments/' + name;
    const config = await gh(base);
    const secrets = await gh(base + '/secrets');
    const variables = await gh(base + '/variables');
    const branches = await gh(base + '/deployment-branch-policies');
    report.github[name] = { id: config.id, updatedAt: config.updated_at, canAdminsBypass: config.can_admins_bypass,
      protectionRules: config.protection_rules.map(x => ({ type: x.type, preventSelfReview: x.prevent_self_review,
        reviewers: x.reviewers?.map(y => ({ type: y.type, login: y.reviewer.login, id: y.reviewer.id })) })),
      branchPolicy: config.deployment_branch_policy, branchRules: branches.branch_policies,
      secrets: secrets.secrets.map(x => ({ name: x.name, updatedAt: x.updated_at })),
      variables: variables.variables.map(x => ({ name: x.name, updatedAt: x.updated_at,
        ...(x.name === 'OTA_BOOT_CHAIN_READY' || x.name === 'TRACE_R2_BUCKET' || x.name.startsWith('FIRMWARE_REHEARSAL_BINDINGS_CHECK_')
          ? { value: x.value } : { valueSha256: io.sha256(x.value) }) })) };
    assert.equal(variables.variables.find(x => x.name === 'OTA_BOOT_CHAIN_READY')?.value, 'false', 'Unexpected environment gate');
  }
  const gate = await gh('actions/variables/OTA_BOOT_CHAIN_READY');
  report.github.repositoryGate = { name: gate.name, value: gate.value, updatedAt: gate.updated_at };
  assert.equal(gate.value, 'false', 'Unexpected repository gate');
  report.github.main = await gh('git/ref/heads/main');
  report.complete = true;
}
main().catch(error => { report.error = io.redact(error.message); process.exitCode = 1; }).finally(() => {
  report.endedAt = new Date().toISOString(); io.writeJson(destination, report);
  process.stdout.write(JSON.stringify({ output: destination, complete: report.complete || false,
    error: report.error, requests: report.requests.map(x => ({ method: x.method, path: io.redact(x.path), status: x.status, errorClass: x.errorClass })) }) + '\n');
});
