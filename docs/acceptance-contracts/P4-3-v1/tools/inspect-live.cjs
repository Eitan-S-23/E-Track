const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const { createHash } = require('node:crypto');

const { root, store } = require('./io.cjs');
const originals = store('live');
assert.equal(fs.realpathSync(process.cwd()), fs.realpathSync(root));
const sha = bytes => createHash('sha256').update(bytes).digest('hex');
const read = originals.read;
const json = file => JSON.parse(read(file));
const pub = '.cache/p43/live-drill/';
const priv = '.cache/p43/private/live-drill/';
const batches = ['probe-01', 'probe-02', 'probe-03', 'drill-01', 'drill-02', 'drill-03', 'drill-04', 'drill-05', 'drill-06'];
const http = [];
const publicReads = [];
const summary = [];
const counts = { d1Originals: 0, snapshotProjections: 0, httpOriginals: 0, publicBodies: 0, screenshots: 0 };

function scrub(value) {
  if (Array.isArray(value)) return value.map(scrub);
  if (value && typeof value === 'object') return Object.fromEntries(Object.entries(value).map(([key, item]) => {
    if (['actor', 'actor_canonical', 'last_actor'].includes(key) && typeof item === 'string') {
      return [`${key}_sha256`, sha(item.trim().toLowerCase())];
    }
    if (['downloadUrl', 'idempotencyKey', 'csrfToken'].includes(key)) return [`${key}Sha256`, typeof item === 'string' ? sha(item) : null];
    if (['ip', 'user_agent'].includes(key)) return [key, '[PRIVATE_ORIGINAL]'];
    return [key, scrub(item)];
  }));
  return typeof value === 'string' ? value.replace(/https?:\/\/[^\s"<>]*\?[^\s"<>]*/g, '[URL_QUERY_PRIVATE]')
    .replace(/\beyJ[A-Za-z0-9_-]+\.[A-Za-z0-9_-]+\.[A-Za-z0-9_-]+\b/g, '[JWT_PRIVATE]') : value;
}
function same(actual, expected, label) {
  // Do not print private source values on a mismatch.
  try { assert.deepEqual(actual, expected); } catch { throw new Error(`Original/projection mismatch: ${label}`); }
}
function canonical(value) {
  if (!value || typeof value !== 'object') return JSON.stringify(value);
  return Array.isArray(value) ? `[${value.map(canonical).join(',')}]`
    : `{${Object.keys(value).sort().map(key => `${JSON.stringify(key)}:${canonical(value[key])}`).join(',')}}`;
}
function snapshot(label, name) { return json(`${pub}${label}/${name}-snapshot.json`); }
function receipt(label, name) { return json(`${pub}${label}/${name}-http.json`); }

for (const batch of batches) {
  const result = json(`${pub}${batch}/result.json`);
  assert.equal(sha(read(`${pub}${batch}/collector-source.mjs`)), result.collectorSha256);
  for (const shot of result.screenshots) {
    assert.equal(sha(read(`${pub}${batch}/${shot.file}`)), shot.sha256);
    counts.screenshots++;
  }
  for (const name of originals.names(`${pub}${batch}`)) {
    if (name.endsWith('-d1-receipt.json')) {
      const r = json(`${pub}${batch}/${name}`);
      const bytes = read(`${priv}${batch}/${name.replace('-d1-receipt.json', '-d1-original.json')}`);
      assert.equal(sha(bytes), r.bodySha256, name);
      assert.equal(bytes.length, r.bodyBytes, name);
      const original = JSON.parse(bytes);
      same(original.success, r.success, name);
      assert.match(r.query, /^SELECT\b/);
      if (r.success) for (const item of original.result) {
        assert.equal(item.success, true);
        assert.equal(item.meta.rows_written, 0);
        assert.equal(item.meta.changed_db, false);
      }
      const projectionPath = `${pub}${batch}/${name.replace('-d1-receipt.json', '-snapshot.json')}`;
      if (originals.exists(projectionPath)) {
        const data = JSON.parse(original.result[0].results[0].snapshot_json);
        for (const list of Object.values(data)) list.sort((a, b) => String(a.id ?? a.request_id ?? a.app_id ?? '')
          .localeCompare(String(b.id ?? b.request_id ?? b.app_id ?? '')));
        same(scrub(data), json(projectionPath), `${batch}/${name}`);
        counts.snapshotProjections++;
      }
      counts.d1Originals++;
    }
    if (name.endsWith('-http.json')) {
      const r = json(`${pub}${batch}/${name}`);
      const bytes = read(`${priv}${batch}/${name.replace('-http.json', '-response-original.json')}`);
      const request = json(`${priv}${batch}/${name.replace('-http.json', '-request.json')}`);
      assert.equal(sha(bytes), r.originalResponseSha256, name);
      assert.equal(bytes.length, r.originalResponseBytes, name);
      const original = JSON.parse(bytes);
      same(scrub(original), r.result, `${batch}/${name}`);
      assert.equal(original.requestId, r.requestId);
      same(scrub(request.body), r.body, name);
      assert.equal(request.pathname, r.pathname);
      assert.equal(request.method, 'POST');
      assert.equal(request.origin, 'https://e-track-firmware-p43-admin-test.pages.dev');
      assert.equal(request.idempotencyKey ? sha(request.idempotencyKey) : null, r.idempotencyKeySha256);
      http.push({ ...r, batch });
      counts.httpOriginals++;
    }
    if (name.endsWith('-public.json')) {
      const r = json(`${pub}${batch}/${name}`);
      const bytes = read(`${priv}${batch}/${name.replace('-public.json', '-body.bin')}`);
      assert.equal(sha(bytes), r.bodySha256, name);
      assert.equal(bytes.length, r.bodyBytes, name);
      if (r.body) same(scrub(JSON.parse(bytes)), r.body, `${batch}/${name}`);
      publicReads.push({ ...r, batch, file: name });
      counts.publicBodies++;
    }
  }
  summary.push({ batch, originalResult: result.result, originalCounts: result.counts,
    productSource: result.productSource, failedChecks: result.checks.filter(check => check.result === 'FAIL').map(check => check.id) });
}

const start = snapshot('probe-03', '001-before');
const last = snapshot('drill-06', '024-final');
const before06 = snapshot('drill-06', '001-before');
const high = 'fw_12367eee317a0774a7271cf982ee7f933c6b089336645f9e607501105e72bf0c';
const low = 'fw_e1abd9e066161562fb72322b81ee7c06bf4719df7d6f89e769811a7460373648';
same(last.assets, start.assets, 'all original asset rows');
same(last.appConfig, start.appConfig, 'app config');
same(last.releases.find(row => row.id === high), start.releases.find(row => row.id === high), 'high release');
const finalLow = last.releases.find(row => row.id === low);
const originalLow = start.releases.find(row => row.id === low);
same({ ...finalLow, state: originalLow.state, updated_at: originalLow.updated_at }, originalLow, 'low immutable identity');
assert.equal(finalLow.state, 'disabled');
assert.equal(last.assets.length, 6);
assert.ok(last.assets.every(asset => asset.base_image_sha256 !== finalLow.target_image_sha256));

const added = last.audit.filter(row => !start.audit.some(old => old.id === row.id));
const successful = new Map(http.filter(r => r.status === 200 && r.result.idempotent === false).map(r => [r.requestId, r]));
function checkAudits(state) {
  for (const old of start.audit) same(state.audit.find(row => row.id === old.id), old, 'append-only history');
  const newRows = state.audit.filter(row => !start.audit.some(old => old.id === row.id));
  assert.equal(newRows.length, successful.size);
  for (const row of newRows) {
    const request = successful.get(row.request_id);
    assert.ok(request, 'Every added audit must have an original successful HTTP response');
    assert.equal(row.action, request.result.action);
    assert.equal(row.reason, request.body.reason);
    assert.equal(row.actor_type, 'access');
    assert.equal(row.actor_sha256, json(`${pub}drill-06/result.json`).owner.actorSha256);
    if (row.target_type === 'firmware_channel') {
      const before = JSON.parse(row.before_json);
      const after = JSON.parse(row.after_json);
      assert.equal(after.revision, before.revision + 1);
      assert.equal(before.revision, request.body.expectedRevision);
      for (const key of ['revision', 'currentReleaseId', 'disableLatest', 'disableDownloads', 'maintenanceMessage']) {
        same(after[key], request.result[key], `audit response ${key}`);
      }
    } else {
      const stored = state.idempotency.find(item => item.request_id === row.request_id);
      assert.ok(stored);
      assert.equal(stored.fingerprint, sha(canonical({ method: 'POST', path: request.pathname, body: request.body })));
      assert.equal(stored.retained_until, stored.created_epoch_seconds + 86400);
      assert.equal(stored.state, 'completed');
      assert.equal(stored.status_code, 200);
      if (stored.action === 'recovery-download') {
        assert.equal(stored.original_expires_at, stored.created_epoch_seconds + 300);
        assert.equal(stored.original_expires_at, request.result.expiresAt);
      }
    }
  }
}
function checkFinal(state) {
  assert.equal(state.channels.length, 2);
  for (const channel of state.channels) {
    assert.equal(channel.current_release_id, high);
    assert.equal(channel.disable_latest, 1);
    assert.equal(channel.disable_downloads, 1);
    assert.equal(channel.revision, channel.name === 'stable' ? 13 : 11);
    const chain = added.filter(row => row.target_id === channel.id)
      .sort((a, b) => JSON.parse(a.after_json).revision - JSON.parse(b.after_json).revision);
    const initial = start.channels.find(row => row.id === channel.id);
    let previous = { currentReleaseId: initial.current_release_id, revision: initial.revision,
      disableLatest: Boolean(initial.disable_latest), disableDownloads: Boolean(initial.disable_downloads),
      maintenanceMessage: initial.maintenance_message };
    for (const row of chain) { same(JSON.parse(row.before_json), previous, 'continuous channel audit'); previous = JSON.parse(row.after_json); }
    assert.equal(previous.revision, channel.revision);
  }
}
checkAudits(last);
checkFinal(last);

for (const [name, beforeName, winnerName, conflictName] of [
  ['stable', '001-before', '003-after-cas-winner-stable', '005-after-cas-conflict-stable'],
  ['beta', '007-after-cas-restored-stable', '009-after-cas-winner-beta', '011-after-cas-conflict-beta']
]) {
  const before = snapshot('drill-06', beforeName);
  const winner = snapshot('drill-06', winnerName);
  const conflict = snapshot('drill-06', conflictName);
  assert.equal(winner.audit.length, before.audit.length + 1);
  same(conflict, winner, `${name} loser has no mutation`);
  const response = http.find(r => r.batch === 'drill-06' && r.id.includes(`cas-loser-${name}`));
  assert.equal(response.status, 409);
  assert.equal(response.result.errorCode, 'CAS_CONFLICT');
}
same(snapshot('drill-06', '013-after-cas-restored-beta'), snapshot('drill-06', '016-after-expiry'), 'expired request has no mutation');
same(snapshot('drill-06', '020-after-final-disable'), snapshot('drill-06', '023-after-disable-replays'), 'disable replays have no mutation');
assert.equal(last.audit.length, before06.audit.length + 5);

for (const channel of ['stable', 'beta']) {
  const find = name => {
    const result = publicReads.find(row => row.batch === 'drill-05' && row.name === `${name}-${channel}`);
    assert.ok(result, `${name}-${channel}`); return result;
  };
  const latest = find('latest-low-client');
  assert.equal(latest.status, 200); assert.equal(latest.body.versionCode, 20801); assert.equal(latest.body.releaseId, low);
  for (const version of [20801, 30208]) {
    const response = publicReads.find(row => row.batch === 'drill-05' && row.name === `latest-upgraded-${channel}-${version}`);
    assert.ok(response); assert.equal(response.status, 200); assert.equal(response.body.errorCode, 'NO_UPDATE');
    assert.equal(response.body.updateAvailable, false); assert.equal(response.body.asset, undefined);
  }
  const stopped = find('download-stopped');
  const open = find('old-url-open');
  const stoppedLatest = find('latest-stopped');
  const openOld = find('old-url-latest-stopped');
  const blockedOld = find('old-url-blocked');
  assert.equal(stopped.status, 503); assert.equal(stopped.body.errorCode, 'CHANNEL_STOPPED');
  assert.equal(stoppedLatest.status, 200); assert.equal(stoppedLatest.body.errorCode, 'CHANNEL_STOPPED');
  assert.equal(stoppedLatest.body.updateAvailable, false); assert.equal(stoppedLatest.body.asset, undefined);
  assert.equal(open.status, 200); assert.equal(openOld.status, 200);
  assert.equal(blockedOld.status, 503); assert.equal(blockedOld.body.errorCode, 'CHANNEL_STOPPED');
  for (const r of [stopped, openOld, blockedOld]) assert.equal(r.urlSha256, open.urlSha256);
  const asset = last.assets.find(row => row.id === latest.body.asset.assetId);
  assert.ok(asset);
  for (const r of [open, openOld]) {
    assert.equal(r.bodySha256, asset.sha256); assert.equal(r.bodyBytes, asset.size_bytes);
    assert.equal(r.contentDigest, `sha-256=:${Buffer.from(asset.sha256, 'hex').toString('base64')}:`);
    assert.equal(r.assetType, 'firmware');
  }
}

const recoveryRead = publicReads.find(row => row.batch === 'drill-05' && row.name === 'renewed-recovery-download');
const recoveryAsset = last.assets.find(row => row.release_id === low && row.kind === 'recovery');
assert.ok(recoveryRead); assert.equal(recoveryRead.status, 200);
assert.equal(recoveryRead.bodySha256, recoveryAsset.sha256); assert.equal(recoveryRead.bodyBytes, recoveryAsset.size_bytes);
const expiredRead = publicReads.find(row => row.batch === 'drill-06' && row.name === 'expired-recovery-url');
assert.ok(expiredRead); assert.equal(expiredRead.status, 401); assert.equal(expiredRead.body.errorCode, 'TOKEN_EXPIRED');
assert.equal(expiredRead.urlSha256, recoveryRead.urlSha256);
const expiredReplay = receipt('drill-06', '014-expired-recovery-replay');
assert.equal(expiredReplay.status, 409); assert.equal(expiredReplay.result.errorCode, 'IDEMPOTENCY_RESULT_EXPIRED');
assert.equal(expiredReplay.result.downloadUrlSha256, undefined);
const firstDisable = receipt('drill-06', '019-final-low-disable');
const repeatDisable = receipt('drill-06', '021-disable-exact-replay');
assert.equal(firstDisable.status, 200); assert.equal(repeatDisable.status, 200);
assert.equal(repeatDisable.requestId, firstDisable.requestId);
assert.equal(repeatDisable.idempotencyKeySha256, firstDisable.idempotencyKeySha256);
assert.equal(repeatDisable.result.idempotent, true);
const freshDisable = receipt('drill-06', '022-disable-fresh-key-reject');
assert.equal(freshDisable.status, 410); assert.equal(freshDisable.result.errorCode, 'RELEASE_DISABLED');
same(snapshot('probe-03', '001-before'), snapshot('probe-03', '002-after-cancel'), 'real cancellation');
const dependency = json(`${priv}drill-06/018-low-backfill-dependencies-d1-original.json`);
assert.equal(dependency.success, true);
assert.ok(dependency.result[0].results.every(row => Object.values(row).every(value => value === 0)));

const deploy = json('.cache/p43/live/pages-csrf-02-summary.json');
const originalAttempt = json('.cache/p43/live/pages-csrf-01-summary.json');
assert.equal(deploy.status, 200); assert.equal(deploy.operation, 'GET_ONLY');
assert.equal(deploy.deployment.id, json(`${pub}drill-06/result.json`).deploymentId);
assert.equal(deploy.deployment.sourceCommit, '972e74c43cd36b7a308e457296aaf7bb06120e78');
assert.equal(deploy.deployment.actualStage.status, 'success');
assert.equal(deploy.originalAttempt.cliExitCode, null); assert.equal(deploy.originalAttempt.signal, 'SIGTERM');
assert.ok(originalAttempt.failure); assert.equal(originalAttempt.deploymentCommandAttempted, true);
assert.equal(deploy.cloudWritesAttempted, 0);

const privateBase = '.cache/p43/private/pages/';
const rawDeployment = read(privateBase + 'pages-csrf-02-readback.json');
assert.equal(sha(rawDeployment), deploy.originalSha256);
const deployed = JSON.parse(rawDeployment);
assert.equal(deployed.success, true);
const beforeDeployment = json(privateBase + 'pages-csrf-01-project-before-deploy.json').result;
const afterDeployment = json(privateBase + 'pages-csrf-01-project-after-deploy.json').result;
for (const item of [afterDeployment, deployed.result]) same(item.deployment_configs, beforeDeployment.deployment_configs, 'unchanged deployment bindings');
assert.equal(deployed.result.canonical_deployment.id, deploy.deployment.id);
assert.equal(deployed.result.canonical_deployment.deployment_trigger.metadata.commit_hash, deploy.deployment.sourceCommit);
assert.equal(deployed.result.canonical_deployment.latest_stage.status, 'success');
assert.equal(deployed.result.deployment_configs.production.d1_databases.DB.id, '2617e1e1-956f-42ce-a465-da56d84abf06');
assert.equal(deployed.result.deployment_configs.production.r2_buckets.RELEASES_BUCKET.name, 'e-track-firmware-p41-test-releases');
const session = json(priv + 'drill-06/session-original.json');
const lastResult = json(pub + 'drill-06/result.json');
assert.equal(session.status, 200);
assert.equal(session.body.role, 'owner');
assert.equal(sha(session.body.actor.trim().toLowerCase()), lastResult.owner.actorSha256);
assert.equal(session.headers['x-request-id'], lastResult.owner.requestId);
assert.equal(session.body.csrfToken.length, 36);
assert.equal(sha(read(priv + 'drill-06/served-index.html')), lastResult.servedHtml.sha256);

const badFinal = structuredClone(last); badFinal.channels[0].disable_downloads = 0;
assert.throws(() => checkFinal(badFinal));
const badAudit = structuredClone(last); badAudit.audit.find(row => row.id === added[0].id).request_id = 'unbound-response';
assert.throws(() => checkAudits(badAudit));
process.stdout.write(JSON.stringify({ nature: 'Independent offline review of historical implementation originals; no new cloud execution',
  counts, privateOriginalsRead: originals.privateReadCount(), identityAndBindingsVerified: true, originalBatches: summary, additionalCloudWrites: 0,
  effectsCorrelated: { channel: added.filter(row => row.target_type === 'firmware_channel').length,
    recovery: added.filter(row => row.action === 'issue_recovery_download').length,
    disable: added.filter(row => row.action === 'disable_release').length },
  finalChannels: last.channels.map(row => ({ name: row.name, revision: row.revision,
    currentReleaseId: row.current_release_id, disableLatest: row.disable_latest, disableDownloads: row.disable_downloads })),
  preservedAssets: last.assets.length, lowState: finalLow.state,
  privateOriginalsVerifiedWithoutPublication: true, semanticTamperControlsRejected: 2,
  limits: ['Real publisher/viewer sessions absent', 'Historical observations, not a fresh cloud state claim',
    'Repaired UI is evaluated separately; the historical deployment was not changed'] }, null, 2) + '\n');
