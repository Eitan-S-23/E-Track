const io = require('./io.cjs');
const destination = io.reserve('verify-permissions-03.json');
const cloud = io.cloudInputs();
const report = { startedAt: new Date().toISOString(),
  purpose: 'Discriminate updated credential scopes without treating catalog denial as create failure',
  formalAcceptance: 'NOT_RUN', requests: [], credentials: {}, mutations: 0 };
async function read(route, token) {
  const response = await io.http('https://api.cloudflare.com/client/v4/' + route, {
    headers: { authorization: 'Bearer ' + token },
  }, report.requests);
  const result = response.json?.result;
  if (result?.id) io.sensitive.add(result.id);
  if (Array.isArray(result)) for (const entry of result) if (entry.id && entry.policies) io.sensitive.add(entry.id);
  return { response, projection: { status: response.status, success: response.json?.success === true,
    errors: response.json?.errors, resultInfo: response.json?.result_info } };
}
async function main() {
  for (const [name, token] of [['provisioning', cloud.provisioning], ['existingCi', cloud.ci]]) {
    const checks = report.credentials[name] = {};
    const verify = await read('user/tokens/verify', token);
    checks.verify = { ...verify.projection, active: verify.response.json?.result?.status === 'active' };
    io.assert.equal(checks.verify.active, true, 'Credential is not active: ' + name);
    const id = verify.response.json.result.id;
    checks.verify.idSha256 = io.sha256(id);
    for (const [kind, route] of [
      ['userPermissionCatalog', 'user/tokens/permission_groups'],
      ['accountPermissionCatalog', 'accounts/' + cloud.account + '/tokens/permission_groups'],
      ['selfMetadata', 'user/tokens/' + id],
    ]) {
      const result = await read(route, token);
      checks[kind] = result.projection;
      if (result.response.status === 200) {
        const data = result.response.json.result;
        checks[kind].selected = Array.isArray(data)
          ? data.filter(x => /Workers R2 Storage Bucket Item|API Tokens/.test(x.name))
          : { name: data.name, status: data.status, policies: data.policies, expiresOn: data.expires_on };
      }
    }
  }
  const directory = await read('accounts/' + cloud.account + '/tokens?page=1&per_page=100', cloud.provisioning);
  report.accountTokenDirectory = directory.projection;
  if (directory.response.status === 200) {
    const rows = directory.response.json.result;
    const info = directory.response.json.result_info;
    io.assert.ok(Array.isArray(rows));
    io.assert.ok(!info || ((info.total_pages ?? 1) <= 1 && (info.total_count ?? rows.length) === rows.length));
    report.accountTokenDirectory.count = rows.length;
    report.accountTokenDirectory.matches = rows.filter(x => /e-track-firmware-(production|p41-test)-s3-ci-20261019/.test(x.name))
      .map(x => ({ name: x.name, idSha256: io.sha256(x.id), status: x.status, expiresOn: x.expires_on }));
  }
  report.complete = true;
}
main().catch(error => { report.error = io.redact(error.message); process.exitCode = 1; }).finally(() => {
  report.endedAt = new Date().toISOString();
  io.writeJson(destination, report);
  process.stdout.write(io.redact({ output: destination, complete: report.complete || false,
    credentials: report.credentials, directory: report.accountTokenDirectory, error: report.error }) + '\n');
});
