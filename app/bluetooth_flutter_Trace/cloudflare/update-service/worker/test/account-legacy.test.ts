import { env } from 'cloudflare:workers';
import { beforeAll, describe, expect, it, vi, afterEach } from 'vitest';
import worker from '../src/index';
import { accountBudget } from '../src/account_quota';
import { accountCloudAccess, accountRoute, requireAccount } from '../src/accounts';
import { legacySource, preparedLegacy, legacyResponse, isFormalLegacyRelease } from '../src/account_legacy';
import { signFirmwareDownload } from '../src/firmware_download';
import { publishFirmware, mutateFirmwareChannel } from '../src/firmware_admin';
import type { FirmwareAssetRow, FirmwareChannelRow, FirmwareReleaseRow } from '../src/types';
import { metadata, register, uploadFixture, bytesFor } from './firmware-fixture';
import { signedInRequest } from './account-fixture';
import { assetFileName, r2KeyFor } from '../../scripts/firmware-schema.mjs';
import { onRequest as publicRequest } from '../../public/functions/[[path]]';

const sourceSha = 'a'.repeat(64);
const targetSha = '6e763fb66958d4a4db3b9cbf7b02351184c189165d5499faf26986421273762a';
const limits = { automatic_daily_limit: 5, manual_daily_limit: 5 };
let sourceId: string, targetId: string;
let clientSequence = 0;

async function firmware(version: number, sha: string, commit: string) {
  const input = metadata();
  input.versionCode = version; input.versionName = `3.3.${version % 100}`;
  input.releaseTag = `mcu-e-track-at32f435-v${input.versionName}`;
  input.commitSha = commit; input.targetImageSha256 = sha;
  if (version === 30348) input.assets = input.assets.filter(a => a.kind !== 'patch');
  for (const asset of input.assets) {
    if (asset.kind === 'patch') { asset.baseVersionCode = 30348; asset.baseImageSha256 = sourceSha; }
    asset.fileName = assetFileName(asset.kind, input.versionName, asset.baseVersionCode);
    asset.r2Key = r2KeyFor(input, asset);
    asset.githubUrl = `https://github.com/Eitan-S-23/Trace/releases/download/${input.releaseTag}/${asset.fileName}`;
  }
  await uploadFixture(input);
  const response = await register(input), body = await response.json() as { releaseId: string };
  expect(response.status, JSON.stringify(body)).toBe(201);
  return body.releaseId;
}
async function publish(id: string) {
  const channel = await env.DB.prepare(`SELECT * FROM firmware_channels
    WHERE app_id='trace' AND device_model='e-track-at32f435' AND name='stable'`).first<FirmwareChannelRow>();
  const input = {
    appId: 'trace', deviceModel: 'e-track-at32f435', releaseId: id,
    expectedRevision: channel!.revision, reason: 'synthetic compatibility self-test',
  };
  const actor = { email: 'owner@example.test', requestId: crypto.randomUUID() };
  if (id === sourceId) await mutateFirmwareChannel(env, actor, 'stable', 'retract', input);
  else await publishFirmware(env, actor, 'stable', input);
}
function latest(headers: Headers, extra: Record<string, string> = {}) {
  const query = new URLSearchParams({ appId: 'trace', deviceModel: 'e-track-at32f435', channel: 'stable',
    currentVersionCode: '30348', currentImageSha: sourceSha, hardwareRevision: '1', layoutId: '1',
    bootVersion: '1', protocolVersion: '1', appVersionCode: '119', ...extra });
  return new Request('https://example.com/api/public/firmware/latest?' + query, { headers });
}
async function client() {
  const base = await signedInRequest('https://example.com/api/public/firmware/latest');
  const account = await requireAccount(base, env), headers = new Headers(base.headers);
  headers.set('CF-Connecting-IP', '192.0.2.' + (++clientSequence));
  // A real login fixture, but deliberately no device binding or fabricated UID.
  await env.DB.prepare('DELETE FROM account_devices WHERE account_id=?').bind(account.id).run();
  headers.delete('X-Device-Uid'); headers.set('X-Legacy-Migration', 'uid-v1');
  return { headers, account, request: latest(headers) };
}
interface PreparedBody {
  versionCode: number; targetImageSha256: string;
  asset: { kind: string; assetId: string; downloadUrl: string };
  legacyMigration: Record<string, unknown> & { accountId: string; checkId: string; expiresAt: number };
}
async function prepare() {
  const value = await client(), response = await worker.fetch(value.request, env);
  const body = await response.json() as PreparedBody;
  expect(response.status, JSON.stringify(body)).toBe(200);
  expect(body.asset.kind).toBe('full'); expect(body.versionCode).toBe(30350);
  expect(body.targetImageSha256).toBe(targetSha);
  return { ...value, body };
}
function authorization(value: Awaited<ReturnType<typeof prepare>>, patch: Record<string, unknown> = {}) {
  const headers = new Headers(value.headers); headers.delete('X-Legacy-Migration');
  headers.set('Content-Type', 'application/json');
  return new Request('https://example.com/api/account/ota/authorize', { method: 'POST', headers,
    body: JSON.stringify({ ...value.body.legacyMigration, legacyCheckId: value.body.legacyMigration.checkId, ...patch }) });
}
function download(value: Awaited<ReturnType<typeof prepare>>, url = value.body.asset.downloadUrl) {
  const headers = new Headers(value.headers); headers.delete('X-Legacy-Migration');
  headers.set('X-Legacy-Migration-Check-Id', value.body.legacyMigration.checkId);
  return new Request(url, { headers });
}

describe('explicit account-owned pre-UID migration', () => {
  beforeAll(async () => {
    sourceId = await firmware(30348, sourceSha, '5d81e6b9be2e666a90723a9997fd3a482f583801');
    targetId = await firmware(30350, targetSha, '91916e11469fce94282a9e1a0254048f4e4a9d7f');
    await publish(targetId);
  });
  afterEach(() => vi.restoreAllMocks());

  it('requires login before any compatibility query', async () => {
    const value = await client(), headers = new Headers(value.headers); headers.delete('Authorization');
    const response = await worker.fetch(latest(headers), env);
    expect(response.status).toBe(401);
    expect(await response.json()).toMatchObject({ errorCode: 'LOGIN_REQUIRED' });
  });
  it('keeps ordinary firmware checks and BEGIN gated by a hardware binding', async () => {
    const value = await client(), headers = new Headers(value.headers); headers.delete('X-Legacy-Migration');
    const response = await worker.fetch(latest(headers), env);
    expect(response.status).toBe(403);
    expect(await response.json()).toMatchObject({ errorCode: 'DEVICE_NOT_BOUND' });
    const authorize = new Request('https://example.com/api/account/ota/authorize', { method: 'POST',
      headers: { Authorization: headers.get('Authorization')!, 'Content-Type': 'application/json' }, body: '{}' });
    await expect(accountRoute(authorize, env)).rejects.toMatchObject({ code: 'DEVICE_NOT_BOUND' });
    expect((await accountBudget(env.DB, value.account.id, limits)).manual.used).toBe(0);
  });
  it.each(['automatic', 'unknown'])('never offers the bypass to a %s check', async kind => {
    const value = await client(); value.headers.set('X-Update-Check-Kind', kind);
    await expect(accountCloudAccess(latest(value.headers), env, async () => Response.json({})))
      .rejects.toMatchObject({ code: 'LEGACY_MIGRATION_INVALID' });
  });
  it.each([
    ['currentVersionCode', '30347'], ['currentVersionCode', '30350'], ['currentImageSha', 'b'.repeat(64)],
    ['hardwareRevision', '2'], ['layoutId', '2'], ['bootVersion', '0'], ['protocolVersion', '2'],
    ['deviceModel', 'other-device'],
  ])('rejects an unregistered/mismatched source %s=%s', async (key, val) => {
    const value = await client();
    await expect(legacySource(latest(value.headers, { [key]: val }), env)).rejects.toMatchObject({
      code: key === 'currentImageSha' ? 'LEGACY_MIGRATION_UNAVAILABLE' : 'LEGACY_MIGRATION_INVALID',
    });
  });
  it('rejects an ambiguous identity and a supplied UID', async () => {
    const value = await client(), url = new URL(value.request.url); url.searchParams.append('currentVersionCode', '30348');
    await expect(legacySource(new Request(url, { headers: value.headers }), env))
      .rejects.toMatchObject({ code: 'LEGACY_MIGRATION_INVALID' });
    value.headers.set('X-Device-Uid', '1'.repeat(24));
    await expect(legacySource(latest(value.headers), env)).rejects.toMatchObject({ code: 'LEGACY_MIGRATION_INVALID' });
  });
  it('charges one manual check, forces full, preserves signed download and never binds automatically', async () => {
    const value = await prepare();
    expect(value.body.legacyMigration).toMatchObject({ mode: 'uid-v1', accountId: value.account.id,
      checkId: value.headers.get('X-Update-Check-Id'), sourceVersionCode: 30348, targetVersionCode: 30350 });
    expect((await accountBudget(env.DB, value.account.id, limits)).manual.used).toBe(1);
    expect((await accountBudget(env.DB, value.account.id, limits)).automatic.used).toBe(0);
    const response = await worker.fetch(download(value), env);
    expect(response.status).toBe(200); expect(new Uint8Array(await response.arrayBuffer())).toEqual(bytesFor('full'));
    const ack = await accountRoute(authorization(value), env);
    expect(await ack.json()).toMatchObject({ ok: true, accountId: value.account.id, legacyMigration: true });
    expect((await env.DB.prepare('SELECT COUNT(*) AS n FROM account_devices WHERE account_id=?')
      .bind(value.account.id).first<{ n: number }>())!.n).toBe(0);
    expect((await env.DB.prepare("SELECT COUNT(*) AS n FROM account_audit WHERE account_id=? AND action='legacy_ota_authorize'")
      .bind(value.account.id).first<{ n: number }>())!.n).toBe(1);
  });
  it('refreshes URLs without another charge or extending the preparation expiry', async () => {
    const value = await prepare(); value.headers.set('X-Update-Refresh', '1');
    const response = await worker.fetch(latest(value.headers), env), body = await response.json() as PreparedBody;
    expect(response.status).toBe(200);
    expect(body.legacyMigration).toEqual(value.body.legacyMigration);
    expect((await accountBudget(env.DB, value.account.id, limits)).manual.used).toBe(1);
  });
  it('applies the same full-only admission and allowance at Public Pages', async () => {
    const value = await client();
    const response = await publicRequest({ request: value.request,
      env: { ...env, ASSETS: { fetch: async () => new Response('asset') } }, params: {}, data: {},
      functionPath: '/', waitUntil() {}, passThroughOnException() {}, next: async () => new Response('asset'),
    } as Parameters<typeof publicRequest>[0]);
    expect(response.status).toBe(200);
    expect(await response.json()).toMatchObject({ versionCode: 30350, asset: { kind: 'full' },
      legacyMigration: { accountId: value.account.id, sourceVersionCode: 30348 } });
    expect((await accountBudget(env.DB, value.account.id, limits)).manual.used).toBe(1);
  });
  it('rejects cross-account authorization and download proof', async () => {
    const owner = await prepare(), other = await client();
    owner.headers.set('Authorization', other.headers.get('Authorization')!);
    await expect(accountRoute(authorization(owner), env)).rejects.toMatchObject({ code: 'LEGACY_MIGRATION_INVALID' });
    const response = await worker.fetch(download(owner), env);
    expect(response.status).toBe(403); expect(await response.json()).toMatchObject({ errorCode: 'LEGACY_MIGRATION_INVALID' });
  });
  it.each(['sourceVersionCode','sourceImageSha256','hardwareRevision','layoutId','bootVersion',
    'protocolVersion','targetVersionCode','targetImageSha256','targetReleaseId','assetId','assetSha256'])
    ('refuses a changed %s before BEGIN', async key => {
      const value = await prepare();
      await expect(accountRoute(authorization(value, { [key]: 'changed' }), env))
        .rejects.toMatchObject({ code: 'LEGACY_MIGRATION_INVALID' });
    });
  it('refuses expired or incomplete grants and a missing download proof', async () => {
    const value = await prepare();
    const headers = new Headers(download(value).headers); headers.delete('X-Legacy-Migration-Check-Id');
    expect((await worker.fetch(new Request(value.body.asset.downloadUrl, { headers }), env)).status).toBe(403);
    await env.DB.prepare("UPDATE account_update_checks SET state='failed' WHERE account_id=? AND check_id=?")
      .bind(value.account.id, value.body.legacyMigration.checkId).run();
    await expect(preparedLegacy(env, value.account.id, value.body.legacyMigration.checkId))
      .rejects.toMatchObject({ code: 'LEGACY_MIGRATION_INVALID' });
    await env.DB.prepare("UPDATE account_update_checks SET state='complete' WHERE account_id=? AND check_id=?")
      .bind(value.account.id, value.body.legacyMigration.checkId).run();
    vi.spyOn(Date, 'now').mockReturnValue(value.body.legacyMigration.expiresAt);
    await expect(preparedLegacy(env, value.account.id, value.body.legacyMigration.checkId))
      .rejects.toMatchObject({ code: 'LEGACY_MIGRATION_INVALID' });
  });
  it('refuses signed PATCH tokens and unsigned full URLs under a full grant', async () => {
    const value = await prepare();
    const patch = await env.DB.prepare("SELECT * FROM firmware_release_assets WHERE release_id=? AND kind='patch'")
      .bind(targetId).first<FirmwareAssetRow>();
    const signed = await signFirmwareDownload(env, 'https://example.com', patch!, 'public-ota');
    const wrongKind = await worker.fetch(download(value, signed.downloadUrl), env);
    expect(wrongKind.status).toBe(403);
    const url = new URL(value.body.asset.downloadUrl); url.searchParams.delete('signature');
    expect((await worker.fetch(download(value, url.toString()), env)).status).toBeGreaterThanOrEqual(400);
  });
  it('will not issue a migration against another channel target', async () => {
    await publish(sourceId);
    try {
      const value = await client(), response = await worker.fetch(value.request, env);
      expect(response.status).toBe(409); expect(await response.json()).toMatchObject({ errorCode: 'LEGACY_MIGRATION_UNAVAILABLE' });
      expect((await accountBudget(env.DB, value.account.id, limits)).manual.used).toBe(0);
    } finally { await publish(targetId); }
  });
  it('formal-source guard and missing-object download remain fail closed without changing immutable identity', async () => {
    const source = await env.DB.prepare('SELECT * FROM firmware_releases WHERE id=?')
      .bind(sourceId).first<FirmwareReleaseRow>();
    expect(isFormalLegacyRelease(source!)).toBe(true);
    for (const patch of [{ archived: 1 }, { state: 'draft' as const }, { registration_json: null },
      { registration_json: JSON.stringify({ ...JSON.parse(source!.registration_json!), isFormalRelease: false }) }]) {
      expect(isFormalLegacyRelease({ ...source!, ...patch })).toBe(false);
    }
    const ready = await prepare();
    const asset = await env.DB.prepare('SELECT * FROM firmware_release_assets WHERE id=?')
      .bind(ready.body.asset.assetId).first<FirmwareAssetRow>();
    await env.RELEASES_BUCKET.delete(asset!.r2_key!);
    try { expect((await worker.fetch(download(ready), env)).status).toBeGreaterThanOrEqual(400); }
    finally { await env.RELEASES_BUCKET.put(asset!.r2_key!, bytesFor('full'), {
      customMetadata: { sha256: asset!.sha256, kind: 'full' },
      httpMetadata: { contentType: 'application/vnd.e-track.etu' },
    }); }
  });
  it('rejects recovery-shaped or altered target responses even with a valid source', async () => {
    const value = await prepare();
    for (const change of [{ asset: { ...value.body.asset, kind: 'recovery' } },
      { targetImageSha256: 'c'.repeat(64) }, { versionCode: 30351 }]) {
      await expect(legacyResponse(value.request, env, value.account.id, {
        sourceVersionCode: 30348, sourceImageSha256: sourceSha, hardwareRevision: 1, layoutId: 1,
        bootVersion: 1, protocolVersion: 1,
      }, Response.json({ ...value.body, updateAvailable: true, ...change })))
        .rejects.toMatchObject({ code: 'LEGACY_MIGRATION_UNAVAILABLE' });
    }
  });
});
