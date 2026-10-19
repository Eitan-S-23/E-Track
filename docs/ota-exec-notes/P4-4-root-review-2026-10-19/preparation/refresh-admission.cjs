const io = require('./io.cjs');
const { createHttp } = require('./curl-io.cjs');
const label = process.argv[2];
io.assert.match(label || '', /^refresh-admission-[0-9]+$/);
const destination = io.reserve(label + '.json');
const http = createHttp('curl-' + label);
const env = io.environment();
const token = io.githubToken(env);
const report = { startedAt: new Date().toISOString(), kind: 'READ_ONLY_ADMISSION_REFRESH',
  formalAcceptance: 'NOT_RUN', requests: [], environments: {} };

async function get(route) {
  const response = await http('https://api.github.com/repos/Eitan-S-23/E-Track/' + route, {
    headers: { authorization: 'Bearer ' + token, accept: 'application/vnd.github+json',
      'user-agent': 'E-Track-P44-root-review', 'x-github-api-version': '2022-11-28' },
  }, report.requests);
  io.assert.equal(response.status, 200, 'GitHub read denied: ' + route);
  return response.json;
}

async function main() {
  for (const name of ['firmware-production', 'firmware-rehearsal']) {
    const route = 'environments/' + name;
    const config = await get(route);
    const secrets = await get(route + '/secrets?per_page=100');
    const variables = await get(route + '/variables?per_page=100');
    const branches = await get(route + '/deployment-branch-policies?per_page=100');
    io.assert.equal(secrets.total_count, secrets.secrets.length, 'Secret pagination incomplete');
    io.assert.equal(variables.total_count, variables.variables.length, 'Variable pagination incomplete');
    io.assert.equal(branches.total_count, branches.branch_policies.length, 'Branch pagination incomplete');
    const prefix = name === 'firmware-rehearsal' ? 'FIRMWARE_REHEARSAL_' : '';
    const requiredSecrets = ['TRACE_R2_ACCESS_KEY_ID', 'TRACE_R2_SECRET_ACCESS_KEY'].map(x => prefix + x);
    const gate = variables.variables.find(x => x.name === 'OTA_BOOT_CHAIN_READY');
    report.environments[name] = {
      id: config.id, updatedAt: config.updated_at, canAdminsBypass: config.can_admins_bypass,
      protectionRules: config.protection_rules.map(x => ({ type: x.type, preventSelfReview: x.prevent_self_review,
        reviewers: x.reviewers?.map(y => ({ type: y.type, login: y.reviewer.login, id: y.reviewer.id })) })),
      branchPolicy: config.deployment_branch_policy, branchRules: branches.branch_policies,
      secrets: secrets.secrets.map(x => ({ name: x.name, updatedAt: x.updated_at })),
      variables: variables.variables.map(x => ({ name: x.name, updatedAt: x.updated_at,
        ...(['OTA_BOOT_CHAIN_READY', prefix + 'TRACE_R2_BUCKET'].includes(x.name) ? { value: x.value } : {}) })),
      requiredS3Secrets: requiredSecrets,
      missingS3Secrets: requiredSecrets.filter(x => !secrets.secrets.some(y => y.name === x)),
    };
    io.assert.equal(gate?.value, 'false', 'Unexpected environment gate');
  }
  const gate = await get('actions/variables/OTA_BOOT_CHAIN_READY');
  report.repositoryGate = { name: gate.name, value: gate.value, updatedAt: gate.updated_at };
  io.assert.equal(gate.value, 'false', 'Unexpected repository gate');
  const mainRef = await get('git/ref/heads/main');
  report.remoteMain = mainRef.object.sha;
  report.missingS3SecretCount = Object.values(report.environments).reduce((sum, x) => sum + x.missingS3Secrets.length, 0);
  report.complete = true;
}

main().catch(error => { report.error = io.redact(error.message); process.exitCode = 1; }).finally(() => {
  report.endedAt = new Date().toISOString();
  io.writeJson(destination, report);
  process.stdout.write(JSON.stringify({ output: destination, complete: report.complete || false,
    missingS3SecretCount: report.missingS3SecretCount, remoteMain: report.remoteMain,
    error: report.error, requests: report.requests.length }) + '\n');
});
