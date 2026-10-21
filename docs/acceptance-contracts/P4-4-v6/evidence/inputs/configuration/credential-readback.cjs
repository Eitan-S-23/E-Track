const io = require('./io.cjs');
const label = process.argv[2];
io.assert.match(label || '', /^credential-readback-[0-9]{2}$/);
const destination = io.reserve(label + '.json');
const rawDirectory = io.reserve('private/' + label);
const slots = Array.from({ length: 20 }, (_, n) => io.reserve('private/' + label + '/' + String(n + 1).padStart(2, '0') + '.json'));
const env = io.environment();
const old = io.cloudInputs();
const cfg = io.readJson(io.project + '/app/bluetooth_flutter_Trace/cloudflare/update-service/.github-actions-secrets.staging.local.json');
const cloud = { account: cfg.secrets.CLOUDFLARE_ACCOUNT_ID, token: cfg.secrets.CLOUDFLARE_API_TOKEN };
io.assert.equal(cloud.account, old.account, 'The handed-off credentials target another account');
for (const value of Object.values(cfg.secrets)) if (typeof value === 'string') io.sensitive.add(value);
const privateData = io.readJson(io.project + '/.cache/p44-cred-20261019/private/p44-s3-credentials-20261019.json');
io.assert.equal(privateData.account_id, cloud.account);
const pairs = privateData.credentials;
for (const entry of Object.values(pairs)) {
  for (const key of ['token_id_access_key_id', 'token_value', 'secret_access_key_sha256']) io.sensitive.add(entry[key]);
  io.assert.equal(entry.secret_access_key_sha256, io.sha256(entry.token_value));
}
const githubToken = io.githubToken(env);
const report = { startedAt: new Date().toISOString(), kind: 'INDEPENDENT_CURRENT_CONFIGURATION_READBACK',
  formalAcceptance: 'NOT_RUN', requests: [], observations: {}, checks: [], mutations: 0,
  source: { path: 'app/bluetooth_flutter_Trace/cloudflare/update-service/.github-actions-secrets.staging.local.json',
    sameValueAsOldLocal: cloud.token === old.provisioning, sameValueAsExistingCi: cloud.token === old.ci,
    accountMatchesApproved: true, privateDerivationMatches: true } };
let rawIndex = 0;
async function get(name, origin, route, token) {
  const response = await io.http(origin + route, { headers: { authorization: 'Bearer ' + token,
    accept: 'application/json', 'user-agent': 'E-Track-P44-independent-readback',
    ...(origin.includes('github') ? { 'x-github-api-version': '2022-11-28' } : {}) } }, report.requests);
  const file = slots[rawIndex++]; io.assert.ok(file);
  io.guard(rawDirectory); io.fs.mkdirSync(rawDirectory, { recursive: true }); io.guard(file);
  io.fs.writeFileSync(file, response.bytes, { flag: 'wx', mode: 0o600 });
  report.observations[name] = { status: response.status, original: file,
    originalSha256: io.sha256(response.bytes), originalBytes: response.bytes.length, response: response.json };
  if (response.json?.result?.value) io.sensitive.add(response.json.result.value);
  io.assert.equal(response.status, 200, 'Current GET failed: ' + name);
  return response.json;
}
const cf = (name, route) => get(name, 'https://api.cloudflare.com/client/v4/', route, cloud.token);
const gh = (name, route) => get(name, 'https://api.github.com/repos/Eitan-S-23/E-Track/', route, githubToken);
function check(name, condition) {
  report.checks.push({ name, passed: Boolean(condition) });
  io.assert.ok(condition, name);
}
async function main() {
  const verify = await cf('sourceVerification', 'user/tokens/verify');
  check('source credential active', verify.success === true && verify.result.status === 'active');
  io.sensitive.add(verify.result.id);
  report.source.managementIdSha256 = io.sha256(verify.result.id);
  report.source.sameManagementIdAsOldLocal = report.source.managementIdSha256 ===
    '0c22488a9bee1355603d8d61faca06fcacbdafccfed8a4ba7dc490af7cacdedc';
  const catalog = await cf('permissionCatalog', 'accounts/' + cloud.account + '/tokens/permission_groups');
  check('permission catalog shape', catalog.success === true && Array.isArray(catalog.result));
  const expectedGroups = new Map([
    ['6a018a9f2fc74eb6b293b0c548f38b39', 'Workers R2 Storage Bucket Item Read'],
    ['2efd5506f9c8494dacb1fa10a3e7d5b6', 'Workers R2 Storage Bucket Item Write'],
  ]);
  for (const [id, name] of expectedGroups) check('catalog group ' + name, catalog.result.some(x => x.id === id && x.name === name));
  const directory = await cf('tokenDirectory', 'accounts/' + cloud.account + '/tokens');
  check('token directory shape', directory.success === true && Array.isArray(directory.result));
  const info = directory.result_info;
  check('token directory complete', !info || ((info.total_pages ?? 1) <= 1 && (info.total_count ?? directory.result.length) === directory.result.length));
  report.directoryCount = directory.result.length;
  report.extraDirectoryEntries = directory.result.filter(entry => entry.name !== 'Track' &&
    !Object.values(pairs).some(pair => pair.token_id_access_key_id === entry.id)).map(entry => ({
      name: entry.name, idSha256: io.sha256(entry.id), status: entry.status,
    }));
  check('no unexpected newly listed credential', report.extraDirectoryEntries.length === 0 && directory.result.length === 3);
  report.tokens = {};
  for (const role of ['production', 'rehearsal']) {
    const pair = pairs[role];
    const name = role === 'production' ? 'e-track-firmware-production-s3-ci-20261019' : 'e-track-firmware-rehearsal-s3-ci-20261019';
    const bucket = role === 'production' ? 'e-track-firmware-production-releases' : 'e-track-firmware-p41-test-releases';
    const resource = 'com.cloudflare.edge.r2.bucket.' + cloud.account + '_default_' + bucket;
    const response = await cf(role + 'Policy', 'accounts/' + cloud.account + '/tokens/' + pair.token_id_access_key_id);
    const token = response.result;
    check(role + ' returned identity', response.success === true && token.id === pair.token_id_access_key_id && token.name === name && token.status === 'active');
    check(role + ' exact one allow policy', token.policies?.length === 1 && token.policies[0].effect === 'allow');
    const policy = token.policies[0];
    io.assert.deepEqual(policy.resources, { [resource]: '*' }, role + ' resource scope');
    check(role + ' exact two groups', policy.permission_groups?.length === 2 &&
      new Set(policy.permission_groups.map(x => x.id)).size === 2 &&
      policy.permission_groups.every(x => expectedGroups.get(x.id) === x.name));
    check(role + ' no undocumented conditions', !token.condition || Object.keys(token.condition).length === 0);
    check(role + ' binding matches private input', pair.bucket === bucket && pair.resource_scope === resource &&
      pair.gh_env === (role === 'production' ? 'firmware-production' : 'firmware-rehearsal'));
    report.tokens[role] = { name, bucket, idSha256: io.sha256(token.id), issuedOn: token.issued_on,
      createdOn: token.created_on, expiresOn: token.expires_on ?? null, notBefore: token.not_before ?? null,
      policies: token.policies, condition: token.condition ?? null, verified: true };
  }
  report.github = {};
  for (const role of ['production', 'rehearsal']) {
    const name = 'firmware-' + role;
    const route = 'environments/' + name;
    const config = await gh(role + 'Environment', route);
    const secrets = await gh(role + 'Secrets', route + '/secrets?per_page=100');
    const variables = await gh(role + 'Variables', route + '/variables?per_page=100');
    const branches = await gh(role + 'Branches', route + '/deployment-branch-policies?per_page=100');
    check(name + ' metadata pages complete', secrets.total_count === secrets.secrets.length &&
      variables.total_count === variables.variables.length && branches.total_count === branches.branch_policies.length);
    const prefix = role === 'production' ? '' : 'FIRMWARE_REHEARSAL_';
    check(name + ' S3 secret names exist', ['TRACE_R2_ACCESS_KEY_ID', 'TRACE_R2_SECRET_ACCESS_KEY']
      .every(key => secrets.secrets.some(entry => entry.name === prefix + key)));
    check(name + ' gate false', variables.variables.find(entry => entry.name === 'OTA_BOOT_CHAIN_READY')?.value === 'false');
    const reviewer = config.protection_rules.find(entry => entry.type === 'required_reviewers');
    check(name + ' existing reviewer retained', reviewer?.reviewers?.length === 1 && reviewer.reviewers[0].reviewer.login === 'Eitan-S-23');
    check(name + ' prevent self review unchanged', reviewer.prevent_self_review === (role === 'production'));
    report.github[name] = { id: config.id, protectionRules: config.protection_rules,
      canAdminsBypass: config.can_admins_bypass, secrets: secrets.secrets, variables: variables.variables,
      branchPolicy: config.deployment_branch_policy, branches: branches.branch_policies };
  }
  const gate = await gh('repositoryGate', 'actions/variables/OTA_BOOT_CHAIN_READY');
  check('repository gate false', gate.value === 'false');
  const main = await gh('mainRef', 'git/ref/heads/main');
  report.remoteMain = main.object.sha;
  report.complete = true;
}
main().catch(error => { report.error = io.redact(error.message); process.exitCode = 1; }).finally(() => {
  report.endedAt = new Date().toISOString();
  io.writeJson(destination, report);
  process.stdout.write(io.redact({ output: destination, complete: report.complete || false,
    source: report.source, directoryCount: report.directoryCount, extraDirectoryEntries: report.extraDirectoryEntries,
    tokens: report.tokens, passedChecks: report.checks.filter(x => x.passed).length,
    remoteMain: report.remoteMain, error: report.error, requests: report.requests.length }) + '\n');
});
