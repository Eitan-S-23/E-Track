const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');
const { createHash } = require('node:crypto');

const { root } = require('./io.cjs');
assert.equal(fs.realpathSync(process.cwd()), fs.realpathSync(root));
const sourcePath = 'app/bluetooth_flutter_Trace/cloudflare/update-service/admin/public/index.html';
const html = fs.readFileSync(path.join(root, sourcePath), 'utf8');
function section(start, end) {
  const a = html.indexOf(start);
  const b = html.indexOf(end, a + start.length);
  assert.ok(a >= 0 && b > a, `Missing source section: ${start}`);
  assert.equal(html.indexOf(start, a + start.length), -1);
  return html.slice(a, b);
}
const originalFunctions = [
  section('      function setFirmwareData(', '      async function runFirmwareChannelAction('),
  section('      async function runFirmwareReleaseAction(', '      async function saveNotes('),
  section('      async function mutate(', '      function render()')
].join('\n');

async function observe(status, code, terminal) {
  const scope = { appId: 'trace', deviceModel: 'e-track-at32f435' };
  const release = { ...scope, releaseId: 'acceptance-synthetic-release', versionCode: 20801,
    versionName: '2.8.1', releaseTag: 'acceptance-synthetic-tag', releaseNotes: 'Offline fixture',
    targetImageSha256: 'a'.repeat(64), state: 'ready', archived: false, publishedChannels: [],
    assets: [{ assetId: 'acceptance-synthetic-recovery', kind: 'recovery', fileName: 'fixture.bin',
      sha256: 'b'.repeat(64), sizeBytes: 32, r2State: 'available' }] };
  const state = { busy: false, session: { actor: 'owner@example.test', role: 'owner', csrfToken: 'synthetic' },
    firmwareReleases: [release], firmwareChannels: [], firmwarePendingAction: null,
    firmwareReconcileRequired: false, selectedFirmwareId: release.releaseId };
  const writes = [];
  const durable = new Map();
  const confirmations = [];
  let serial = 0;
  let reads = 0;
  const reply = (body, httpStatus = 200) => new Response(JSON.stringify(body), {
    status: httpStatus, headers: { 'Content-Type': 'application/json', 'X-Request-Id': body.requestId || 'fixture-read' }
  });
  const context = vm.createContext({ state, activeConfirmDialog: null, URL, Response,
    crypto: { randomUUID: () => `00000000-0000-4000-8000-${String(++serial).padStart(12, '0')}` },
    t: key => key, canRole: role => state.session.role === role,
    firmwareReady: item => item?.state === 'ready' && !item.archived,
    firmwarePublishedChannels: item => item.publishedChannels,
    renderFirmware() {}, renderSessions() {}, setStatus() {},
    setBusy(value) { state.busy = value; },
    openConfirmDialog(options) { confirmations.push(options.title); return Promise.resolve({ reason: 'same operator intent' }); },
    openResultDialog() { return Promise.resolve(true); },
    async fetch(url, options) {
      if (options.method !== 'POST') {
        reads++;
        if (url === '/api/admin/session') return reply({ ok: true, ...state.session });
        return reply({ ok: true, requestId: 'fixture-read',
          ...(url.includes('/releases?') ? { firmwareReleases: [release] } : { firmwareChannels: [] }) });
      }
      const key = options.headers['Idempotency-Key'];
      writes.push({ path: url, key, body: options.body });
      if (writes.length === 2) return reply({ errorCode: code, message: 'Injected reconciliation rejection', requestId: 'fixture-rejected' }, status);
      if (!durable.has(key)) {
        const expiresAt = Math.floor(Date.now() / 1000) + 300;
        const query = new URLSearchParams({ tokenVersion: '2', purpose: 'admin-recovery',
          releaseId: release.releaseId, assetId: release.assets[0].assetId });
        durable.set(key, { ok: true, requestId: `fixture-effect-${durable.size + 1}`,
          action: 'issue_recovery_download', releaseId: release.releaseId, assetId: release.assets[0].assetId,
          kind: 'recovery', fileName: 'fixture.bin', expiresAt, idempotent: false,
          downloadUrl: `https://offline.example.test/api/public/firmware/download?${query}` });
      }
      if (writes.length === 1) throw new Error('Injected lost response after a durable commit');
      return reply(durable.get(key));
    }
  });
  vm.runInContext(originalFunctions, context, { filename: sourcePath, timeout: 1000 });
  await context.runFirmwareReleaseAction(release.releaseId, 'recovery-download');
  assert.equal(durable.size, 1);
  assert.ok(state.firmwarePendingAction);
  const pending = state.firmwarePendingAction;
  const readsBeforeRetry = reads;
  await context.runFirmwareReleaseAction(null, null, true);
  assert.equal(writes.length, 2);
  assert.deepEqual(writes[1], writes[0]);
  assert.ok(reads > readsBeforeRetry);
  const pendingRetained = state.firmwarePendingAction === pending;
  const writeLockRetained = Boolean(state.firmwarePendingAction || state.firmwareReconcileRequired);
  await context.runFirmwareReleaseAction(release.releaseId, 'recovery-download');
  const expectedRetained = !terminal;
  return { status, code, terminal, originalResponseLostAfterCommit: true,
    retryUsedSameRequest: true, readsBeforeAndAfterRetry: reads,
    pendingRetained, writeLockRetained, postCount: writes.length, durableEffects: durable.size,
    acceptedNewKey: writes.length === 3 && writes[2].key !== writes[0].key,
    expectedRetained, conforms: pendingRetained === expectedRetained
      && durable.size === (terminal ? 2 : 1), explicitConfirmations: confirmations.length };
}

(async () => {
  const results = [];
  for (const [status, code, terminal] of [
    [401, 'TOKEN_EXPIRED', false], [403, 'CSRF_INVALID', false],
    [403, 'ROLE_FORBIDDEN', false], [429, 'RATE_LIMITED', false],
    [503, 'BACKEND_UNAVAILABLE', false], [409, 'IDEMPOTENCY_RESULT_EXPIRED', true]
  ]) results.push(await observe(status, code, terminal));
  const failed = results.filter(result => !result.conforms);
  process.stdout.write(JSON.stringify({ nature: 'Independent frozen source probe; original UI functions, mocked transport only',
    sourcePath, sourceSha256: createHash('sha256').update(html).digest('hex'),
    actualCloudRequests: 0, originalProductFilesModified: false, results,
    passed: results.length - failed.length, failed: failed.length }, null, 2) + '\n');
  process.exitCode = failed.length ? 1 : 0;
})().catch(error => { process.stderr.write(String(error.stack || error) + '\n'); process.exitCode = 2; });
