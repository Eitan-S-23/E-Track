// Thin platform capture: standard HTTP/SigV4, two explicit dispatches, no reviewer API.
const s = require('./run.cjs');
const { fs, path, assert } = s;
const repository = 'Eitan-S-23/E-Track';
const branch = 'dev/p4-4/config-integration-20261018';
const prefix = '/repos/' + repository;
const envRoute = prefix + '/environments/firmware-rehearsal';
const contractPath = 'docs/acceptance-contracts/P4-4-v1.contract.json';
const project = path.resolve(s.root, '../..');
const modules = path.join(s.root, 'app/bluetooth_flutter_Trace/cloudflare/update-service/worker/node_modules');
const resources = {
  production: { db: '1cd5db26-6bbd-4595-abef-72ff51ecdaf3', bucket: 'e-track-firmware-production-releases',
    worker: 'https://e-track-firmware-production.tangjichentudou.workers.dev' },
  protected: { db: '0133ad9e-d4a2-4fef-a659-4f2bf3d3a645', bucket: 'trace-update-staging-releases' },
  staging: { db: '2617e1e1-956f-42ce-a465-da56d84abf06', bucket: 'e-track-firmware-p41-test-releases',
    worker: 'https://e-track-firmware-p41-test.tangjichentudou.workers.dev' },
};
const sort = value => Array.isArray(value) ? value.map(sort) : value && typeof value === 'object'
  ? Object.fromEntries(Object.keys(value).sort().map(key => [key, sort(value[key])])) : value;
const canonical = value => JSON.stringify(sort(value));
const privateRead = relative => fs.readFileSync(s.guard(path.join(project, relative), project), 'utf8').trim();
let context, transportOverride, frozenOverride, sleepOverride;
const sleep = ms => sleepOverride ? sleepOverride(ms) : new Promise(resolve => setTimeout(resolve, ms));
function secrets() {
  if (context) return context;
  assert.equal(s.root.replaceAll('\\', '/'), project.replaceAll('\\', '/') + '/.cache/p4-4-integration-20261018', 'TASK_ROOT');
  const config = JSON.parse(privateRead('app/bluetooth_flutter_Trace/cloudflare/update-service/.github-actions-secrets.staging.local.json'));
  const pairs = JSON.parse(privateRead('.cache/p44-cred-20261019/private/p44-s3-credentials-20261019.json'));
  const account = config.secrets.CLOUDFLARE_ACCOUNT_ID;
  assert.equal(s.sha256(account), '01910e669500c221e2154f608e9f4e856b0a08297026e1ea98f1d18dd8cf9742', 'ACCOUNT_IDENTITY');
  const local = privateRead('.cache/p41-dev-20261015/.cache/cf-auth-input/token.txt');
  const env = s.environment();
  const auth = s.cp.spawnSync('gh', ['auth', 'token', '--hostname', 'github.com', '--user', 'Eitan-S-23'], {
    cwd: s.root, env: { ...env, GH_CONFIG_DIR: 'C:/Users/SU/AppData/Roaming/GitHub CLI', GH_TOKEN: '', GITHUB_TOKEN: '' },
    windowsHide: true, encoding: 'utf8', timeout: 30000,
  });
  assert(auth.status === 0 && auth.stdout.trim(), 'GITHUB_AUTH_UNAVAILABLE');
  const gh = auth.stdout.trim();
  const sensitive = [account, local, gh, ...Object.values(config.secrets).filter(v => typeof v === 'string' && v)];
  const deploy = {
    production: JSON.parse(privateRead('.cache/p4-4-integration-20261018/.cache/p44/private/production-secrets.json')),
    staging: JSON.parse(privateRead('.cache/p41-dev-20261015/.cache/cf-auth-input/firmware-test-secrets.json')),
  };
  for (const value of Object.values(deploy)) {
    assert.equal(s.sha256(value.TRACE_DEPLOY_TOKEN), value.DEPLOY_TOKEN_SHA256, 'DEPLOY_PAIR');
    sensitive.push(value.TRACE_DEPLOY_TOKEN, value.DOWNLOAD_HMAC_KEY_CURRENT);
  }
  assert.notEqual(deploy.production.TRACE_DEPLOY_TOKEN, deploy.staging.TRACE_DEPLOY_TOKEN, 'DEPLOY_ISOLATION');
  const ota = JSON.parse(privateRead('.cache/p41-dev-20261015/.cache/cf-auth-input/p41-rehearsal-ota-key.json'));
  assert.match(ota.keyHex, /^[0-9a-fA-F]{32}$/);
  assert.equal(s.sha256(Buffer.from(ota.keyHex, 'hex')), 'a94ae0f006b3d6be51279b861dc19b8a0892833939d0a4db5a81ee7af511fe9e', 'APPROVED_AES');
  sensitive.push(ota.keyHex.toLowerCase(), ota.keyHex.toUpperCase());
  for (const [role, pair] of Object.entries(pairs.credentials)) {
    assert(['production', 'rehearsal'].includes(role), 'PAIR_ROLE');
    assert.equal(pair.bucket, resources[role === 'rehearsal' ? 'staging' : role].bucket, 'PAIR_BUCKET');
    assert.equal(pair.secret_access_key_sha256, s.sha256(pair.token_value), 'PAIR_DERIVATION');
    assert.equal(s.sha256(pair.token_id_access_key_id), role === 'production'
      ? 'eb673c4ae5e4fe5a023669fb1a945c1f366dc7b0c04aaa5638abb11238e7fd49'
      : 'e96e395a2e6866581f0c4aa1b46579026683ea9f4fbfab48b9b2f8b45a22a508', 'PAIR_IDENTITY');
    sensitive.push(pair.token_id_access_key_id, pair.token_value, pair.secret_access_key_sha256);
  }
  context = { account, local, gh, pairs: pairs.credentials, deploy, env,
    sensitive: sensitive.filter(Boolean).flatMap(value => [value, Buffer.from(value).toString('base64')]) };
  return context;
}
function publicHeaders(headers) {
  return Object.fromEntries(Object.entries(headers).filter(([name]) =>
    !['set-cookie', 'location', 'authorization', 'proxy-authorization', 'cookie'].includes(name.toLowerCase())));
}
function routeAllowed(origin, method, route) {
  if (typeof route !== 'string' || /[\r\n#\\]/.test(route) || route.split(/[/?]/).some(part => part === '.' || part === '..')) return false;
  if (origin === 'https://api.github.com') {
    if (method === 'GET') return route === '/user' || route.startsWith(prefix + '/');
    if (method === 'POST') return route === prefix + '/actions/workflows/firmware-build.yml/dispatches'
      || route === envRoute + '/deployment-branch-policies';
    return method === 'PATCH' && ['OTA_PREVIOUS_RELEASE_JSON', 'OTA_APPROVED_BOOTSTRAP_BASELINE_SHA256']
      .some(name => route === envRoute + '/variables/' + name);
  }
  if (origin === 'https://api.cloudflare.com') return (method === 'GET' && route === '/user/tokens/verify')
    || (method === 'POST' && Object.values(resources).some(r => route === '/accounts/[ACCOUNT]/d1/database/' + r.db + '/query'));
  if (origin === 's3') {
    if (method !== 'GET') return false;
    return Object.values(resources).some(r => route.startsWith('/' + r.bucket + '/?list-type=2&max-keys=1000')
      && /^\/?[^?]+\?list-type=2&max-keys=1000(?:&continuation-token=[^&#]+)?$/.test(route)
      || new RegExp('^/' + r.bucket + '/trace/firmware/e-track-at32f435/[a-zA-Z0-9.-]+/[a-zA-Z0-9.-]+$').test(route));
  }
  return Object.values(resources).some(r => r.worker === origin) && method === 'POST' && route === '/api/ci/firmware/preflight';
}
async function transport(url, method, headers, body, maxBytes = 16 * 1024 * 1024) {
  if (transportOverride) return transportOverride(url, method, headers, body, maxBytes);
  const { request, ProxyAgent } = require(path.join(modules, 'undici'));
  const proxy = new ProxyAgent({ uri: 'http://127.0.0.1:7897', allowH2: false, requestTls: { rejectUnauthorized: true } });
  let response;
  const chunks = [];
  try {
    response = await request(url, { method, headers, body, dispatcher: proxy, maxRedirections: 0,
      headersTimeout: 30000, bodyTimeout: 30000, signal: AbortSignal.timeout(60000) });
    let size = 0;
    for await (const chunk of response.body) { size += chunk.length; assert(size <= maxBytes, 'HTTP_SIZE_LIMIT'); chunks.push(chunk); }
    return { status: response.statusCode, headers: publicHeaders(response.headers), bytes: Buffer.concat(chunks) };
  } catch (error) {
    if (response) error.partial = { status: response.statusCode, headers: publicHeaders(response.headers), bytes: Buffer.concat(chunks) };
    throw error;
  } finally { await proxy.destroy(); }
}
async function capture(label, origin, route, { method = 'GET', body, headers = {}, expected = 200 } = {}) {
  assert(routeAllowed(origin, method, route), 'UNAPPROVED_ROUTE');
  const c = secrets(), stem = label;
  for (const suffix of ['-reservation.json', '.body', '.http.json', ...(body === undefined ? [] : ['.request.json'])]) {
    assert(!fs.existsSync(s.destination(stem + suffix)), 'REQUEST_ALREADY_CAPTURED');
  }
  let requestBody;
  if (body !== undefined) requestBody = Buffer.from(JSON.stringify(body));
  if (requestBody) for (const value of c.sensitive) assert(!requestBody.includes(Buffer.from(value)), 'SENSITIVE_REQUEST_BODY');
  const requestRef = requestBody ? s.write(stem + '.request.json', requestBody) : undefined;
  const started = new Date().toISOString();
  s.write(stem + '-reservation.json', { method, origin, path: route, started, request: requestRef,
    note: 'Reserved before request; a lost response is not permission to replay a mutation.' });
  const envelope = { method, path: route, started, ...(requestRef ? { request: requestRef } : {}) };
  let url;
  if (origin === 'https://api.github.com') {
    url = origin + route;
    headers = { authorization: 'Bearer ' + c.gh, accept: 'application/vnd.github+json',
      'x-github-api-version': '2022-11-28', 'user-agent': 'E-Track-P44', ...headers };
  } else if (origin === 'https://api.cloudflare.com') {
    url = origin + '/client/v4' + route.replace('[ACCOUNT]', c.account);
    headers = { authorization: 'Bearer ' + c.local, ...headers };
  } else if (origin === 's3') url = 'https://' + c.account + '.r2.cloudflarestorage.com' + route;
  else { url = origin + route; headers = { accept: 'application/json', ...headers }; }
  if (requestBody) headers['content-type'] = 'application/json';
  try {
    const response = await transport(url, method, headers, requestBody);
    // Decisive bodies are byte-exact. A credential-bearing response stops capture.
    const headerBytes = Buffer.from(JSON.stringify(response.headers));
    for (const value of c.sensitive) assert(!response.bytes.includes(Buffer.from(value)) && !headerBytes.includes(Buffer.from(value)), 'SENSITIVE_RESPONSE');
    envelope.status = response.status;
    envelope.response_headers = response.headers;
    envelope.body = s.write(stem + '.body', response.bytes);
    envelope.completed = true;
    envelope.ended = new Date().toISOString();
    s.write(stem + '.http.json', envelope);
    assert((Array.isArray(expected) ? expected : [expected]).includes(response.status), 'HTTP_UNEXPECTED_STATUS');
    return { envelope, bytes: response.bytes, json: () => JSON.parse(response.bytes) };
  } catch (error) {
    if (!fs.existsSync(s.destination(stem + '.http.json'))) {
      const partial = error.partial;
      if (partial) {
        envelope.status = partial.status;
        envelope.partial_body_sha256 = s.sha256(partial.bytes);
        envelope.partial_body_size_bytes = partial.bytes.length;
        const safe = c.sensitive.every(value => !partial.bytes.includes(Buffer.from(value))
          && !JSON.stringify(partial.headers).includes(value));
        if (safe) { envelope.response_headers = partial.headers; envelope.body = s.write(stem + '.partial.body', partial.bytes); }
        else envelope.partial_projection = 'Known sensitive value: original hash/length only, no public plaintext copy';
      }
      s.write(stem + '.http.json', { ...envelope, ended: new Date().toISOString(),
        error_code: error.code || 'CAPTURE_FAILED', completed: false });
    }
    throw error;
  }
}
const gh = (label, route, options) => capture(label, 'https://api.github.com', route, options);
function nextLink(headers) {
  const value = headers.link || headers.Link;
  if (!value) return undefined;
  return String(value).split(',').map(item => item.trim()).find(item => /;\s*rel="next"/.test(item))?.match(/^<([^>]+)>/)?.[1];
}
async function pages(label, route, field) {
  const records = [], items = [];
  for (let page = 1; page <= 30; page++) {
    const current = route + (route.includes('?') ? '&' : '?') + 'per_page=100&page=' + page;
    const result = await gh(label + '-' + page, current), body = result.json();
    const batch = field ? body[field] : body;
    assert(Array.isArray(batch), 'PAGE_SHAPE'); records.push(result.envelope); items.push(...batch);
    const next = nextLink(result.envelope.response_headers);
    if (!next) {
      if (field) assert.equal(body.total_count, items.length, 'PAGE_COUNT');
      return { records, items };
    }
    const got = new URL(next), wanted = new URL('https://api.github.com' + route + (route.includes('?') ? '&' : '?') + 'per_page=100&page=' + (page + 1));
    assert.equal(got.origin + got.pathname, wanted.origin + wanted.pathname, 'PAGE_LINK_ORIGIN');
    assert.deepEqual([...got.searchParams].sort(), [...wanted.searchParams].sort(), 'PAGE_LINK_QUERY');
  }
  throw Error('PAGE_LIMIT');
}
function target() {
  const t = s.read('target.json');
  assert.equal(t.repository, repository); assert.equal(t.branch, branch); assert.equal(t.versionName, '3.2.9');
  assert.match(t.commitSha, /^[0-9a-f]{40}$/); assert.equal(t.descriptor.targetCommitSha, t.commitSha);
  assert.equal(t.descriptor.targetVersionName, t.versionName);
  assert.equal(s.sha256(canonical(t.descriptor)), t.descriptorSha256);
  return t;
}
function frozen() {
  if (frozenOverride) return frozenOverride();
  const t = target(), contract = JSON.parse(fs.readFileSync(s.guard(path.join(s.root, contractPath))));
  assert.equal(contract.status, 'FROZEN'); assert.equal(contract.contract_id, 'P4-4-v1');
  assert.equal(contract.freeze_commit, t.commitSha); assert.equal(s.git(['rev-parse', 'HEAD']), t.commitSha);
  assert.equal(s.git(['branch', '--show-current']), branch);
  assert.equal(s.read('commands/formal-precheck.json').exitCode, 0);
  return t;
}
async function prepareTarget() {
  assert.equal(s.git(['branch', '--show-current']), branch);
  const old = JSON.parse(fs.readFileSync(s.guard(path.join(s.root, 'docs/acceptance-contracts/P4-1-v2/evidence/formal/target.json'))));
  const t = { ...old, branch, commitSha: s.git(['rev-parse', 'HEAD']), versionName: '3.2.9' };
  t.descriptor = { ...old.descriptor, targetCommitSha: t.commitSha, targetVersionName: t.versionName };
  t.descriptorSha256 = s.sha256(canonical(t.descriptor));
  const { pathToFileURL } = require('node:url');
  const scripts = path.join(s.root, 'app/bluetooth_flutter_Trace/cloudflare/update-service/scripts');
  const schema = await import(pathToFileURL(path.join(scripts, 'firmware-schema.mjs')));
  const prepare = await import(pathToFileURL(path.join(scripts, 'prepare-firmware-release.mjs')));
  assert.equal(canonical(t.descriptor), schema.canonicalJson(t.descriptor));
  const proof = JSON.parse(fs.readFileSync(s.guard(path.join(s.root, t.descriptor.archivePath, 'provenance.json'))));
  prepare.validateBaseDescriptor(t.descriptor, t.versionName, repository, t.commitSha);
  prepare.validateBootstrapProvenance(t.descriptor, proof, repository);
  s.write('target.json', t);
  console.log(JSON.stringify({ target: t.versionName, commit: t.commitSha, descriptor_sha256: t.descriptorSha256 }));
}
async function configuration(label, checkTarget) {
  const result = {};
  for (const role of ['production', 'rehearsal']) {
    const route = prefix + '/environments/firmware-' + role;
    const config = await gh(label + '/' + role + '-environment', route);
    const vars = await pages(label + '/' + role + '-variables', route + '/variables', 'variables');
    const names = await pages(label + '/' + role + '-secrets', route + '/secrets', 'secrets');
    const rules = await pages(label + '/' + role + '-branches', route + '/deployment-branch-policies', 'branch_policies');
    const value = config.json(), reviewer = value.protection_rules.find(r => r.type === 'required_reviewers');
    assert.deepEqual(value.deployment_branch_policy, { protected_branches: false, custom_branch_policies: true });
    assert.equal(reviewer.prevent_self_review, role === 'production');
    assert.equal(reviewer.reviewers.length, 1); assert.equal(reviewer.reviewers[0].reviewer.login, 'Eitan-S-23');
    assert.equal(reviewer.reviewers[0].reviewer.id, 204050265);
    const values = Object.fromEntries(vars.items.map(v => [v.name, v.value]));
    assert.equal(values.OTA_BOOT_CHAIN_READY, 'false');
    assert.equal(values.TRACE_FIRMWARE_MIN_APP_VERSION_CODE, String(target().minAppVersionCode), 'MIN_APP_CONFIG_DRIFT');
    assert.equal(values.TRACE_FIRMWARE_MIN_PROTOCOL_VERSION, String(target().minProtocolVersion), 'MIN_PROTOCOL_CONFIG_DRIFT');
    const keyPrefix = role === 'production' ? '' : 'FIRMWARE_REHEARSAL_';
    for (const name of ['CLOUDFLARE_ACCOUNT_ID', 'OTA_AES_KEY', 'TRACE_DEPLOY_TOKEN', 'TRACE_UPDATE_SERVICE_URL',
      'TRACE_R2_ACCESS_KEY_ID', 'TRACE_R2_SECRET_ACCESS_KEY']) assert(names.items.some(n => n.name === keyPrefix + name), 'MISSING_SECRET');
    assert.equal(values[keyPrefix + 'TRACE_R2_BUCKET'], resources[role === 'production' ? role : 'staging'].bucket);
    if (role === 'production') assert.deepEqual(rules.items.map(r => [r.name, r.type]), [['main', 'branch']]);
    else {
      assert(rules.items.every(r => r.type === 'branch' && ['dev/p4-1/unattended-20261015', branch].includes(r.name)));
      if (checkTarget) {
        assert(rules.items.some(r => r.name === branch));
        assert.equal(values.OTA_PREVIOUS_RELEASE_JSON, canonical(target().descriptor));
        assert.equal(values.OTA_APPROVED_BOOTSTRAP_BASELINE_SHA256, target().descriptorSha256);
      }
    }
    result[role] = { configuration: config.envelope, variables: vars.records, secrets: names.records, branches: rules.records, values, rules: rules.items };
  }
  const gate = await gh(label + '/repository-gate', prefix + '/actions/variables/OTA_BOOT_CHAIN_READY');
  assert.equal(gate.json().value, 'false');
  const remote = await gh(label + '/candidate-ref', prefix + '/git/ref/heads/' + branch);
  assert.equal(remote.json().object.sha, target().commitSha, 'REMOTE_CANDIDATE_DRIFT');
  result.repository_gate = gate.envelope; result.candidate_ref = remote.envelope;
  return result;
}
async function configure() {
  const t = target(), before = await configuration('configure-before', false);
  const prior = JSON.parse(fs.readFileSync(s.guard(path.join(s.root, 'docs/acceptance-contracts/P4-1-v2/evidence/formal/target.json'))));
  const changes = { OTA_PREVIOUS_RELEASE_JSON: canonical(t.descriptor), OTA_APPROVED_BOOTSTRAP_BASELINE_SHA256: t.descriptorSha256 };
  const oldValues = { OTA_PREVIOUS_RELEASE_JSON: canonical(prior.descriptor), OTA_APPROVED_BOOTSTRAP_BASELINE_SHA256: prior.descriptorSha256 };
  for (const [name, value] of Object.entries(changes)) assert([oldValues[name], value].includes(before.rehearsal.values[name]), 'UNEXPECTED_BASELINE');
  s.write('configure-plan.json', { target: s.fileRef('target.json'), branch, changes, gate_changes: 0, reviewer_changes: 0 });
  if (!before.rehearsal.rules.some(r => r.name === branch)) await gh('configure-branch', envRoute + '/deployment-branch-policies', {
    method: 'POST', body: { name: branch, type: 'branch' } });
  for (const [name, value] of Object.entries(changes)) if (before.rehearsal.values[name] !== value) {
    await gh('configure-' + name.toLowerCase(), envRoute + '/variables/' + name, { method: 'PATCH', body: { name, value }, expected: 204 });
  }
  s.write('configured.json', { before, after: await configuration('configure-after', true) });
}
function sqlAllowed(sql) {
  return sql === 'SELECT name,type,sql FROM sqlite_master ORDER BY type,name'
    || /^SELECT COUNT\(\*\) AS count FROM "[a-z_][a-z0-9_]*"$/i.test(sql)
    || /^SELECT \* FROM "[a-z_][a-z0-9_]*" ORDER BY rowid LIMIT 500 OFFSET (0|[1-9][0-9]*)$/i.test(sql);
}
async function d1(label, role, sql) {
  assert(sqlAllowed(sql), 'UNAPPROVED_SQL');
  const result = await capture(label, 'https://api.cloudflare.com', '/accounts/[ACCOUNT]/d1/database/' + resources[role].db + '/query', {
    method: 'POST', body: { sql } });
  const data = result.json();
  assert(data.success && data.result.length === 1, 'D1_RESPONSE');
  assert(data.result[0].success && data.result[0].meta.rows_written === 0 && data.result[0].meta.changed_db === false, 'D1_READ_ONLY');
  return { envelope: result.envelope, rows: data.result[0].results };
}
async function protectedPair(label) {
  const c = secrets(), started = new Date().toISOString();
  s.write(label + '-local-verify-reservation.json', { method: 'GET', path: '/user/tokens/verify', started });
  const response = await transport('https://api.cloudflare.com/client/v4/user/tokens/verify', 'GET', { authorization: 'Bearer ' + c.local });
  const data = JSON.parse(response.bytes);
  if (!(response.status === 200 && data.success && data.result.status === 'active')) {
    s.write(label + '-local-verify-failure.json', { status: response.status, started, ended: new Date().toISOString(),
      original_sha256: s.sha256(response.bytes), errors: data.errors?.map(error => ({ code: error.code })) });
    throw Error('LOCAL_READ_CREDENTIAL');
  }
  const id = data.result.id; assert.match(id, /^[0-9a-f]{32}$/);
  assert.equal(s.sha256(id), '0c22488a9bee1355603d8d61faca06fcacbdafccfed8a4ba7dc490af7cacdedc', 'LOCAL_CREDENTIAL_IDENTITY');
  // The verification identity becomes an S3 Access Key ID and is not published.
  s.write(label + '-local-verify.json', { method: 'GET', path: '/user/tokens/verify', status: response.status,
    started, ended: new Date().toISOString(), original_sha256: s.sha256(response.bytes), original_size_bytes: response.bytes.length,
    response_projection: { success: true, status: data.result.status, id_sha256: s.sha256(id) },
    omitted_original: 'Access Key identifier used only in memory; this is an auxiliary projection, not a raw response body.' });
  const key = s.sha256(c.local); c.sensitive.push(id, key);
  return { accessKeyId: id, secretAccessKey: key };
}
async function s3(label, role, route, pair, expected = 200) {
  assert(route.startsWith('/' + resources[role].bucket + '/'), 'R2_RESOURCE');
  const { SignatureV4 } = require(path.join(modules, '@smithy/signature-v4'));
  const { Sha256Node } = require(path.join(modules, '@smithy/core/checksum'));
  const { HttpRequest } = require(path.join(modules, '@smithy/core/protocols'));
  const c = secrets(), url = new URL('https://' + c.account + '.r2.cloudflarestorage.com' + route);
  const signer = new SignatureV4({ credentials: pair, region: 'auto', service: 's3', sha256: Sha256Node, uriEscapePath: false });
  const request = await signer.sign(new HttpRequest({ protocol: url.protocol, hostname: url.hostname,
    method: 'GET', path: url.pathname, query: Object.fromEntries(url.searchParams), headers: { host: url.hostname } }));
  return capture(label, 's3', route, { headers: request.headers, expected });
}
function pair(role) {
  const value = secrets().pairs[role === 'staging' ? 'rehearsal' : role];
  assert(value, 'PAIR_MISSING'); return { accessKeyId: value.token_id_access_key_id, secretAccessKey: value.secret_access_key_sha256 };
}
function xmlText(text, name) {
  const matches = [...text.matchAll(new RegExp('<' + name + '>([^<]*)</' + name + '>', 'g'))];
  assert.equal(matches.length, 1, 'XML_FIELD');
  return matches[0][1].replace(/&(?:amp|lt|gt|quot|apos);/g, token => ({ '&amp;': '&', '&lt;': '<', '&gt;': '>', '&quot;': '"', '&apos;': "'" })[token]);
}
function stagingAdmission(tables) {
  const relevant = row => row.app_id === 'trace' && row.device_model === 'e-track-at32f435';
  assert(Array.isArray(tables.firmware_releases) && Array.isArray(tables.firmware_channels)
    && Array.isArray(tables.firmware_releases_legacy), 'STAGING_SCHEMA_INCOMPLETE');
  const releases = tables.firmware_releases.filter(relevant), latest = releases.filter(row => row.version_code === 30208);
  assert.equal(Math.max(...releases.map(row => row.version_code)), 30208, 'STAGING_CURRENT_VERSION_DRIFT');
  assert.equal(latest.length, 1, 'STAGING_BASELINE_AMBIGUOUS');
  assert.equal(s.sha256(latest[0].registration_json + '\n'), 'fe435e1a0bc6afea344566846b1a63e8de39ee9335a98a874e97fbcc82b543a4', 'STAGING_BASELINE_DRIFT');
  assert(!tables.firmware_channels.filter(relevant).some(row => row.legacy_current_release_id != null), 'UNRESOLVED_LEGACY_CHANNEL');
  assert(tables.firmware_releases_legacy.filter(relevant).every(row => Number.isSafeInteger(row.version_code) && row.version_code < 30209), 'STAGING_LEGACY_VERSION_DRIFT');
}
async function snapshot(phase) {
  frozen(); assert(['before', 'after'].includes(phase));
  const result = { databases: {}, buckets: {}, github: {} }, stem = 'snapshots/' + phase;
  const localPair = await protectedPair(stem);
  for (const [role, resource] of Object.entries(resources)) {
    const schema = await d1(stem + '/' + role + '-schema', role, 'SELECT name,type,sql FROM sqlite_master ORDER BY type,name');
    const tables = {};
    for (const table of schema.rows.filter(row => row.type === 'table' && !row.name.startsWith('sqlite_') && !row.name.startsWith('_cf_'))) {
      assert(!/WITHOUT\s+ROWID/i.test(table.sql), 'UNSUPPORTED_TABLE_LAYOUT');
      const count = await d1(stem + '/' + role + '-' + table.name + '-count', role, 'SELECT COUNT(*) AS count FROM "' + table.name + '"');
      const total = count.rows[0].count;
      assert(Number.isSafeInteger(total) && total >= 0 && total <= 20000, 'D1_SIZE_LIMIT');
      const records = []; let rows = 0;
      for (let offset = 0; offset < total; offset += 500) {
        const data = await d1(stem + '/' + role + '-' + table.name + '-' + offset, role,
          'SELECT * FROM "' + table.name + '" ORDER BY rowid LIMIT 500 OFFSET ' + offset);
        records.push(data.envelope); rows += data.rows.length;
      }
      assert.equal(rows, total, 'D1_PAGE_COUNT'); tables[table.name] = { count: count.envelope, pages: records };
    }
    result.databases[role] = { schema: schema.envelope, tables };
    const records = []; let continuation;
    for (let page = 1; page <= 20; page++) {
      const query = new URLSearchParams({ 'list-type': '2', 'max-keys': '1000' });
      if (continuation) query.set('continuation-token', continuation);
      const data = await s3(stem + '/' + role + '-r2-' + page, role, '/' + resource.bucket + '/?' + query,
        role === 'protected' ? localPair : pair(role));
      const xml = data.bytes.toString('utf8'); records.push(data.envelope);
      assert.equal(xmlText(xml, 'Name'), resource.bucket);
      const truncated = xmlText(xml, 'IsTruncated'); assert(['true', 'false'].includes(truncated));
      if (truncated === 'false') break;
      assert(page < 20); const next = xmlText(xml, 'NextContinuationToken'); assert(next && next !== continuation); continuation = next;
    }
    result.buckets[role] = records;
  }
  const releases = await pages(stem + '/releases', prefix + '/releases');
  assert(!releases.items.some(r => r.tag_name.startsWith('mcu-e-track-at32f435-v')), 'FORMAL_LINEAGE_PRESENT');
  const tag = await gh(stem + '/target-tag', prefix + '/git/ref/tags/mcu-e-track-at32f435-v' + target().versionName, { expected: [200, 404] });
  const peeled = [];
  if (tag.envelope.status === 200) {
    let object = tag.json().object;
    for (let depth = 0; object?.type === 'tag' && depth < 7; depth++) {
      assert.match(object.sha, /^[0-9a-f]{40}$/);
      const next = await gh(stem + '/target-tag-' + depth, prefix + '/git/tags/' + object.sha);
      peeled.push(next.envelope); object = next.json().object;
    }
    assert(object?.type === 'commit' && object.sha === target().commitSha, 'TARGET_TAG_CONFLICT');
  }
  result.target_tag = { ref: tag.envelope, peeled };
  result.github.releases = releases.records; result.github.assets = {};
  for (const release of releases.items) result.github.assets[release.id] = (await pages(stem + '/assets-' + release.id,
    prefix + '/releases/' + release.id + '/assets')).records;
  result.protected_configuration = await configuration(stem + '/config', true);
  if (phase === 'before') {
    const tables = Object.fromEntries(Object.entries(result.databases.staging.tables)
      .map(([name, value]) => [name, value.pages.flatMap(page => document(page.body).result[0].results)]));
    stagingAdmission(tables);
  }
  s.write(stem + '.json', result);
  console.log(JSON.stringify({ snapshot: phase, complete: true, roles: 3, releases: releases.items.length }));
}
function dispatchBody() {
  return { ref: branch, inputs: { publish: 'false', rehearsal: 'true', check_bindings: 'false',
    approved_rehearsal_run_id: '', version_name: target().versionName,
    release_notes: 'P4-4 new S3/preflight configuration qualification; staging only; gate=false; no production release.' } };
}
function runIdentity(run, t) {
  assert.equal(run.head_sha, t.commitSha); assert.equal(run.head_branch, branch); assert.equal(run.run_attempt, 1);
  assert.equal(run.event, 'workflow_dispatch'); assert.equal(run.path, '.github/workflows/firmware-build.yml');
  assert.equal(run.repository.full_name, repository);
}
function document(reference) {
  const bytes = s.readBytes(reference.path);
  assert.equal(bytes.length, reference.size_bytes); assert.equal(s.sha256(bytes), reference.sha256);
  return JSON.parse(bytes);
}
function rejectedAdmission() {
  const ended = s.read('run-a/final.json'), t = target();
  const run = document(ended.final_run.body); runIdentity(run, t);
  assert.equal(run.conclusion, 'failure'); assert.equal(run.status, 'completed');
  const reviews = document(ended.reviews_http.body);
  assert.equal(reviews.length, 1);
  const review = reviews[0];
  assert(review.state === 'rejected' && review.user?.login === 'Eitan-S-23' && review.user?.id === 204050265 && review.user?.type === 'User');
  assert.equal(review.environments.length, 1);
  assert(review.environments[0].id === 24458272742 && review.environments[0].name === 'firmware-rehearsal');
  const jobs = ended.jobs_pages.flatMap(page => document(page.body).jobs);
  assert(ended.jobs_pages.every(page => document(page.body).total_count === jobs.length));
  assert.equal(jobs.length, 5); assert.equal(new Set(jobs.map(job => job.name)).size, 5);
  for (const job of jobs) {
    assert.equal(job.run_id, run.id); assert.equal(job.run_attempt, 1); assert.equal(job.head_sha, t.commitSha);
    assert.equal(job.head_branch, branch); assert.equal(job.status, 'completed');
    if (['Build firmware (arm-none-eabi-gcc)', 'Release tooling development checks (no cloud credentials)'].includes(job.name)) {
      assert.equal(job.conclusion, 'success');
    } else {
      assert(['Firmware rehearsal (shared release implementation)', 'Firmware production (shared release implementation)',
        'Isolated firmware binding qualification (not rehearsal)'].includes(job.name));
      assert(Array.isArray(job.steps) && job.steps.every(step => step.conclusion === 'skipped'));
      assert(job.conclusion === 'skipped' || (job.name.startsWith('Firmware rehearsal') && job.conclusion === 'failure'));
    }
  }
  const witness = s.read('reviewer-action-a.json');
  assert(witness.reviewer === 'Eitan-S-23' && witness.reviewer_id === 204050265 && witness.run_id === run.id
    && witness.run_attempt === 1 && witness.state === 'rejected' && ['owner_response', 'root_witness'].includes(witness.basis));
  const original = s.readBytes(witness.evidence.path);
  assert(original.length && original.length === witness.evidence.size_bytes && s.sha256(original) === witness.evidence.sha256);
}
async function dispatch(letter) {
  const t = frozen(); assert(['a', 'b'].includes(letter)); s.read('configured.json'); s.read('snapshots/before.json');
  if (letter === 'b') {
    rejectedAdmission();
  }
  const stem = 'run-' + letter;
  assert(!fs.existsSync(s.destination(stem + '/dispatch-intent.json')), 'DISPATCH_ALREADY_RESERVED');
  await configuration(stem + '/admission', true);
  for (const status of ['queued', 'in_progress', 'waiting', 'pending', 'requested']) {
    const active = await pages(stem + '/active-' + status, prefix + '/actions/workflows/firmware-build.yml/runs?event=workflow_dispatch&status=' + status, 'workflow_runs');
    assert.equal(active.items.length, 0, 'RELEASE_RUN_ALREADY_ACTIVE');
  }
  s.write(stem + '/dispatch-intent.json', { created_at: new Date().toISOString(), commitSha: t.commitSha, body: dispatchBody() });
  await gh(stem + '/dispatch', prefix + '/actions/workflows/firmware-build.yml/dispatches', { method: 'POST', body: dispatchBody(), expected: 204 });
  const started = Date.parse(s.read(stem + '/dispatch-intent.json').created_at);
  for (let attempt = 1; attempt <= 30; attempt++) {
    const listing = await pages(stem + '/discovery-' + attempt, prefix + '/actions/workflows/firmware-build.yml/runs?branch=' + encodeURIComponent(branch) + '&event=workflow_dispatch', 'workflow_runs');
    const matches = listing.items.filter(r => r.head_sha === t.commitSha && Date.parse(r.created_at) >= started - 5000
      && Date.parse(r.created_at) <= started + 120000 && (letter !== 'b' || r.id !== s.read('run-a/identity.json').run_id));
    assert(matches.length <= 1, 'AMBIGUOUS_DISPATCH');
    if (matches.length) {
      runIdentity(matches[0], t); s.write(stem + '/identity.json', { run_id: matches[0].id, url: matches[0].html_url });
      console.log(JSON.stringify({ run: letter, run_id: matches[0].id, url: matches[0].html_url, reviewer_action: letter === 'a' ? 'Reject' : 'Approve' }));
      return waitForPending(letter);
    }
    await sleep(10000);
  }
  throw Error('DISPATCH_DISCOVERY_TIMEOUT');
}
async function waitForPending(letter, label = '') {
  const stem = 'run-' + letter, id = s.read(stem + '/identity.json').run_id, t = frozen();
  for (let attempt = 1; attempt <= 90; attempt++) {
    const run = await gh(stem + '/' + label + 'waiting-' + attempt, prefix + '/actions/runs/' + id); runIdentity(run.json(), t);
    const pending = await gh(stem + '/' + label + 'pending-' + attempt, prefix + '/actions/runs/' + id + '/pending_deployments');
    if (pending.json().length && ['waiting', 'pending'].includes(run.json().status)) {
      assert.equal(pending.json().length, 1); assert.equal(pending.json()[0].environment.name, 'firmware-rehearsal');
      assert.equal(pending.json()[0].environment.id, 24458272742);
      s.write(stem + '/waiting.json', { waiting_run: run.envelope, pending_deployments: pending.envelope });
      console.log(JSON.stringify({ run: letter, run_id: id, status: 'waiting', required_human_action: letter === 'a' ? 'Reject' : 'Approve',
        url: 'https://github.com/' + repository + '/actions/runs/' + id })); return;
    }
    assert.notEqual(run.json().status, 'completed', 'RUN_ENDED_BEFORE_REVIEW');
    await sleep(10000);
  }
  throw Error('REVIEW_WAIT_TIMEOUT');
}
async function recover(letter, label) {
  assert(['a', 'b'].includes(letter) && /^[a-z0-9-]+$/.test(label || ''), 'RECOVERY_LABEL');
  const t = frozen(), stem = 'run-' + letter, intent = s.read(stem + '/dispatch-intent.json');
  assert.equal(intent.commitSha, t.commitSha); assert.deepEqual(intent.body, dispatchBody());
  const listing = await pages(stem + '/recover-' + label, prefix + '/actions/workflows/firmware-build.yml/runs?branch=' + encodeURIComponent(branch) + '&event=workflow_dispatch', 'workflow_runs');
  const matches = listing.items.filter(run => run.head_sha === t.commitSha && Date.parse(run.created_at) >= Date.parse(intent.created_at) - 5000
    && Date.parse(run.created_at) <= Date.parse(intent.created_at) + 120000 && (letter !== 'b' || run.id !== s.read('run-a/identity.json').run_id));
  assert.equal(matches.length, 1, 'RECOVERY_RUN_AMBIGUOUS'); runIdentity(matches[0], t);
  const identityFile = stem + '/identity.json';
  if (fs.existsSync(s.destination(identityFile))) assert.equal(s.read(identityFile).run_id, matches[0].id);
  else s.write(identityFile, { run_id: matches[0].id, url: matches[0].html_url });
  s.write(stem + '/recover-' + label + '-result.json', { status: matches[0].status, run_id: matches[0].id,
    platform_mutations: 0, note: 'Read-only reconciliation of the original intent, never redispatch' });
  if (!fs.existsSync(s.destination(stem + '/waiting.json')) && matches[0].status !== 'completed') return waitForPending(letter, 'recover-' + label + '-');
}
async function finish(letter, label = '') {
  const t = frozen(), stem = 'run-' + letter; assert(['a', 'b'].includes(letter));
  assert(!fs.existsSync(s.destination(stem + '/final.json')), 'RUN_FINAL_ALREADY_CAPTURED_USE_MISSING_DATA_COLLECTOR');
  const id = s.read(stem + '/identity.json').run_id; s.read(stem + '/waiting.json');
  let final;
  for (let attempt = 1; attempt <= 180; attempt++) {
    const run = await gh(stem + '/' + label + 'terminal-' + attempt, prefix + '/actions/runs/' + id + '/attempts/1'); runIdentity(run.json(), t);
    if (run.json().status === 'completed') { final = run; break; }
    await sleep(10000);
  }
  assert(final, 'RUN_TERMINAL_TIMEOUT');
  const reviews = await gh(stem + '/' + label + 'reviews', prefix + '/actions/runs/' + id + '/approvals');
  const jobs = await pages(stem + '/' + label + 'jobs', prefix + '/actions/runs/' + id + '/attempts/1/jobs', 'jobs');
  s.write(stem + '/final.json', { final_run: final.envelope, reviews_http: reviews.envelope,
    jobs_pages: jobs.records, run: final.json(), reviews: reviews.json() });
  assert.equal(final.json().conclusion, letter === 'a' ? 'failure' : 'success', 'RUN_CONCLUSION');
  console.log(JSON.stringify({ run: letter, run_id: id, conclusion: final.json().conclusion, reviews: reviews.json().length }));
  await collectLogs(letter, label);
  if (letter === 'b') await collectArtifact(label);
}
function download(label, route) {
  const c = secrets();
  s.write(label + '-reservation.json', { method: 'GITHUB_CLI_GET', path: route, started: new Date().toISOString() });
  const result = s.cp.spawnSync('gh', ['api', route, '--hostname', 'github.com'], { cwd: s.root,
    env: { ...c.env, GH_TOKEN: c.gh }, windowsHide: true, timeout: 180000, maxBuffer: 256 * 1024 * 1024 });
  const bytes = result.stdout || Buffer.alloc(0), stderr = result.stderr || Buffer.alloc(0);
  let text = stderr.toString('utf8');
  for (const value of c.sensitive) text = text.split(value).join('[REDACTED]');
  text = text.replace(/(https?:\/\/[^?\s"<>]+)\?[^\s"<>]+/g, '$1?[REDACTED_QUERY]');
  const artifact = s.write(label + '.zip', bytes);
  s.write(label + '-receipt.json', { method: 'GITHUB_CLI_GET', path: route, exit_code: result.status, signal: result.signal,
    process_closed: true, ended: new Date().toISOString(), artifact, stderr_sha256: s.sha256(stderr), stderr_size_bytes: stderr.length,
    stderr_projection: text });
  assert.equal(result.status, 0, 'ARCHIVE_DOWNLOAD_FAILED');
  assert(bytes.length >= 4 && bytes.subarray(0, 2).toString() === 'PK', 'ARCHIVE_NOT_ZIP');
  return artifact;
}
async function collectLogs(letter, label = '') {
  assert(['a', 'b'].includes(letter));
  assert(!fs.existsSync(s.destination('run-' + letter + '/logs.json')), 'RUN_LOGS_ALREADY_CAPTURED');
  const id = s.read('run-' + letter + '/identity.json').run_id;
  const artifact = download('run-' + letter + '/' + label + 'logs', prefix + '/actions/runs/' + id + '/attempts/1/logs');
  s.write('run-' + letter + '/logs.json', { run_id: id, attempt: 1, artifact });
}
async function collectArtifact(label = '') {
  assert(!fs.existsSync(s.destination('artifact.json')), 'ARTIFACT_ALREADY_CAPTURED');
  const id = s.read('run-b/identity.json').run_id, t = frozen();
  assert.equal(s.read('run-b/final.json').run.conclusion, 'success');
  {
    const artifacts = await pages('run-b/' + label + 'artifacts', prefix + '/actions/runs/' + id + '/artifacts', 'artifacts');
    const matches = artifacts.items.filter(a => a.name === 'p41-rehearsal-' + id + '-1'); assert.equal(matches.length, 1);
    const item = matches[0]; assert.equal(item.expired, false); assert.equal(item.workflow_run.head_sha, t.commitSha);
    const route = prefix + '/actions/artifacts/' + item.id + '/zip';
    const ref = download('run-b/' + label + 'rehearsal', route);
    assert.equal(ref.size_bytes, item.size_in_bytes); assert.equal('sha256:' + ref.sha256, item.digest, 'ARTIFACT_DIGEST');
    s.write('artifact.json', { artifact: ref, artifact_listing: artifacts.records });
  }
}
function assemble() {
  const manifest = { schema: 'p44-observations-v1', target: s.fileRef('target.json') };
  for (const letter of ['a', 'b']) {
    const stem = 'run-' + letter;
    if (!fs.existsSync(s.destination(stem + '/final.json'))) continue;
    const final = s.read(stem + '/final.json');
    manifest['run_' + letter] = { ...s.read(stem + '/identity.json'), dispatch: s.read(stem + '/dispatch.http.json'),
      ...s.read(stem + '/waiting.json'), final_run: final.final_run, reviews: final.reviews_http, jobs_pages: final.jobs_pages };
  }
  if (fs.existsSync(s.destination('artifact.json'))) Object.assign(manifest, s.read('artifact.json'));
  manifest.snapshots = {};
  for (const phase of ['before', 'after']) if (fs.existsSync(s.destination('snapshots/' + phase + '.json'))) manifest.snapshots[phase] = s.read('snapshots/' + phase + '.json');
  if (fs.existsSync(s.destination('readbacks.json'))) manifest.readbacks = s.read('readbacks.json');
  if (!fs.existsSync(s.destination('reviewer-attestation.json')) && ['a', 'b'].every(letter => fs.existsSync(s.destination('reviewer-action-' + letter + '.json')))) {
    const actions = ['a', 'b'].map(letter => s.read('reviewer-action-' + letter + '.json'));
    s.write('reviewer-attestation.json', { schema: 'p44-reviewer-attestation-v1', reviewer: 'Eitan-S-23', reviewer_id: 204050265, actions });
  }
  if (fs.existsSync(s.destination('reviewer-attestation.json'))) manifest.reviewer_attestation = s.fileRef('reviewer-attestation.json');
  const complete = Boolean(manifest.readbacks && manifest.reviewer_attestation && manifest.snapshots.after);
  s.write(complete ? 'manifest.json' : 'rehearsal-manifest.json', manifest);
}
async function readbacks() {
  frozen(); const result = s.read('rehearsal-result.json'); assert.equal(result.ok, true);
  assert.equal(result.observed.metadata.commitSha, target().commitSha); const captures = {};
  for (const asset of result.observed.metadata.assets) {
    assert(/^trace\/firmware\/e-track-at32f435\/[a-zA-Z0-9.-]+\/[a-zA-Z0-9.-]+$/.test(asset.r2Key));
    const response = await s3('readbacks/' + asset.kind, 'staging', '/' + resources.staging.bucket + '/' + asset.r2Key, pair('staging'));
    assert.equal(response.bytes.length, asset.sizeBytes); assert.equal(s.sha256(response.bytes), asset.sha256);
    captures[asset.r2Key] = response.envelope;
  }
  assert.equal(Object.keys(captures).length, 3); s.write('readbacks.json', captures);
}
async function negatives() {
  frozen(); s.read('snapshots/before.json'); const c = secrets(), results = [];
  const probes = [['missing-staging', 'staging', undefined],
    ['production-token-to-staging', 'staging', c.deploy.production.TRACE_DEPLOY_TOKEN],
    ['staging-token-to-production', 'production', c.deploy.staging.TRACE_DEPLOY_TOKEN]];
  for (const [name, role, token] of probes) {
    const data = await capture('negatives/' + name, resources[role].worker, '/api/ci/firmware/preflight', {
      method: 'POST', body: {}, headers: token ? { authorization: 'Bearer ' + token } : {}, expected: 401 });
    assert.equal(data.json().errorCode, 'TOKEN_INVALID', 'AUTH_DENIAL_CODE'); results.push(data.envelope);
  }
  for (const [from, to] of [['production', 'staging'], ['staging', 'production']]) {
    const data = await s3('negatives/' + from + '-s3-to-' + to, to,
      '/' + resources[to].bucket + '/?list-type=2&max-keys=1000', pair(from), 403);
    assert.equal(xmlText(data.bytes.toString('utf8'), 'Code'), 'AccessDenied'); results.push(data.envelope);
  }
  s.write('negatives.json', { ok: true, requests: results, worker_denials: 3, outside_bucket_denials: 2,
    body_note: 'Empty body deliberately tests authentication before body parsing; no accepted register call.' });
}
async function productionPreflight() {
  frozen(); const result = s.read('rehearsal-result.json'); assert.equal(result.ok, true);
  const metadata = result.observed.metadata; assert.equal(metadata.commitSha, target().commitSha);
  const id = require('node:crypto').randomUUID();
  const response = await capture('production-preflight', resources.production.worker, '/api/ci/firmware/preflight', {
    method: 'POST', body: { schemaVersion: 1, environment: 'prod', metadata },
    headers: { authorization: 'Bearer ' + secrets().deploy.production.TRACE_DEPLOY_TOKEN, 'x-request-id': id } });
  const data = response.json();
  assert(data.ok && data.schemaVersion === 1 && data.environment === 'prod' && data.requestId === id);
  assert.equal(response.envelope.response_headers['x-request-id'], id);
  assert.equal(data.metadataSha256, s.sha256(canonical(metadata) + '\n'));
  assert.equal(data.unresolvedLegacyChannels, 0);
  assert(data.maxVersionCode === null || data.maxVersionCode <= metadata.versionCode);
  assert(data.legacyMaxVersionCode === null || data.legacyMaxVersionCode < metadata.versionCode);
  s.write('production-preflight-result.json', { ok: true, http: response.envelope, requested_request_id: id,
    effect: 'Authenticated fixed SELECT-only endpoint; not production workflow consumption, registration or publication.' });
}
module.exports = { canonical, routeAllowed, sqlAllowed, nextLink, publicHeaders, resources, runIdentity, stagingAdmission,
  _test: { capture, pages, d1, s3, configuration, dispatch, waitForPending, recover, rejectedAdmission, finish, collectArtifact, collectLogs,
    setContext(value) { assert(require.main !== module); context = value; },
    setFrozen(value) { assert(require.main !== module); frozenOverride = value; },
    setSleep(value) { assert(require.main !== module); sleepOverride = value; },
    setTransport(value) { assert(require.main !== module); transportOverride = value; } } };
if (require.main === module) {
  const [mode, label] = process.argv.slice(2);
  Promise.resolve().then(async () => {
    if (mode === 'target') return prepareTarget();
    if (mode === 'configure') return configure();
    if (['before', 'after'].includes(mode)) return snapshot(mode);
    if (mode === 'dispatch-a' || mode === 'dispatch-b') return dispatch(mode.slice(-1));
    if (mode === 'finish-a' || mode === 'finish-b') return finish(mode.slice(-1));
    if (mode === 'recover-a' || mode === 'recover-b') return recover(mode.slice(-1), label);
    if (['finish-a-recovery', 'finish-b-recovery', 'collect-b', 'logs-a', 'logs-b'].includes(mode)) {
      frozen(); assert(/^[a-z0-9-]+$/.test(label || ''), 'RECOVERY_LABEL');
      if (mode === 'collect-b') return collectArtifact('recover-' + label + '-');
      if (mode.startsWith('logs-')) return collectLogs(mode.slice(-1), 'recover-' + label + '-');
      return finish(mode === 'finish-a-recovery' ? 'a' : 'b', 'recover-' + label + '-');
    }
    if (mode === 'assemble') return assemble();
    if (mode === 'readbacks') return readbacks();
    if (mode === 'negatives') return negatives();
    if (mode === 'production-preflight') return productionPreflight();
    throw Error('UNKNOWN_CAPTURE_MODE');
  }).catch(error => { console.error(JSON.stringify({ ok: false, error_code: error.code || 'CAPTURE_FAILED', mode })); process.exitCode = 1; });
}
