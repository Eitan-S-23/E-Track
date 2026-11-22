import { ApiError, backendUnavailable } from './errors';
import { verifyFirmwareDownload } from './firmware_download';
import { json } from './http';
import type { FirmwareAssetRow, FirmwareReleaseRow, WorkerEnv } from './types';

export const LEGACY_SOURCE_VERSION = 30348;
export const LEGACY_TARGET_VERSION = 30350;
const targetSource = '91916e11469fce94282a9e1a0254048f4e4a9d7f';
const targetImage = '6e763fb66958d4a4db3b9cbf7b02351184c189165d5499faf26986421273762a';
const lifetimeMs = 24 * 3600000;
const model = 'e-track-at32f435';

export interface LegacyMigration {
  mode: 'uid-v1'; accountId: string; checkId: string;
  sourceVersionCode: number; sourceImageSha256: string;
  hardwareRevision: number; layoutId: number; bootVersion: number; protocolVersion: number;
  targetVersionCode: number; targetImageSha256: string; targetReleaseId: string;
  assetId: string; assetSha256: string; expiresAt: number;
}

const unavailable = () => new ApiError('LEGACY_MIGRATION_UNAVAILABLE',
  'The registered 3.3.48 device requires the published 3.3.50 full migration', 409);
const invalid = () => new ApiError('LEGACY_MIGRATION_INVALID', 'Legacy migration identity or preparation is not valid', 403);

export function isFormalLegacyRelease(release: FirmwareReleaseRow): boolean {
  try {
    const registration = JSON.parse(release.registration_json ?? 'null');
    return release.state === 'ready' && release.archived === 0 && registration?.isFormalRelease === true &&
      registration.commitSha === release.commit_sha && registration.targetImageSha256 === release.target_image_sha256;
  } catch { return false; }
}

export async function legacySource(request: Request, env: WorkerEnv) {
  const url = new URL(request.url), get = (key: string) => url.searchParams.get(key);
  if (request.method !== 'GET' || request.headers.get('X-Legacy-Migration') !== 'uid-v1' ||
      request.headers.get('X-Update-Check-Kind') !== 'manual' || request.headers.has('X-Device-Uid') ||
      get('appId') !== env.APP_ID || get('deviceModel') !== model ||
      get('currentVersionCode') !== String(LEGACY_SOURCE_VERSION) || !/^[0-9a-f]{64}$/.test(get('currentImageSha') ?? '')) {
    throw invalid();
  }
  for (const key of ['currentVersionCode','currentImageSha','hardwareRevision','layoutId','bootVersion','protocolVersion']) {
    if (url.searchParams.getAll(key).length !== 1) throw invalid();
  }
  const release = await env.DB.prepare(`SELECT * FROM firmware_releases
    WHERE app_id=? AND device_model=? AND version_code=? AND target_image_sha256=?`)
    .bind(env.APP_ID, model, LEGACY_SOURCE_VERSION, get('currentImageSha')).first<FirmwareReleaseRow>();
  if (!release || !isFormalLegacyRelease(release)) throw unavailable();
  if (get('hardwareRevision') !== String(release.hardware_rev) || get('layoutId') !== String(release.layout_id) ||
      !/^[0-9]+$/.test(get('bootVersion') ?? '') || Number(get('bootVersion')) < release.min_boot_version ||
      get('protocolVersion') !== '1') throw invalid();
  return { sourceVersionCode: LEGACY_SOURCE_VERSION, sourceImageSha256: release.target_image_sha256,
    hardwareRevision: release.hardware_rev, layoutId: release.layout_id,
    bootVersion: Number(get('bootVersion')), protocolVersion: 1 };
}

async function target(env: WorkerEnv, releaseId: string, assetId: string, assetSha: string) {
  const release = await env.DB.prepare('SELECT * FROM firmware_releases WHERE id=?').bind(releaseId).first<FirmwareReleaseRow>();
  const asset = await env.DB.prepare('SELECT * FROM firmware_release_assets WHERE id=? AND release_id=?')
    .bind(assetId, releaseId).first<FirmwareAssetRow>();
  if (!release || !isFormalLegacyRelease(release) || release.app_id !== env.APP_ID || release.device_model !== model ||
      release.version_code !== LEGACY_TARGET_VERSION || release.commit_sha !== targetSource ||
      release.target_image_sha256 !== targetImage || !asset || asset.kind !== 'full' ||
      asset.r2_state !== 'available' || !asset.r2_key || !asset.r2_etag || asset.sha256 !== assetSha ||
      asset.base_vcode !== 0 || asset.base_image_sha256 !== '') throw unavailable();
  return { release, asset };
}

export async function legacyResponse(request: Request, env: WorkerEnv, accountId: string,
  source: Awaited<ReturnType<typeof legacySource>>, response: Response): Promise<Response> {
  if (!response.ok) return response;
  const body = await response.clone().json() as Record<string, unknown>;
  if (body.updateAvailable === false && body.errorCode === 'CHANNEL_STOPPED') return response;
  const asset = body.asset as Record<string, unknown> | undefined;
  if (body.updateAvailable !== true || body.versionCode !== LEGACY_TARGET_VERSION ||
      body.targetImageSha256 !== targetImage || !asset || asset.kind !== 'full' ||
      typeof body.releaseId !== 'string' || typeof asset.assetId !== 'string' || typeof asset.sha256 !== 'string') throw unavailable();
  await target(env, body.releaseId, asset.assetId, asset.sha256);
  const checkId = request.headers.get('X-Update-Check-Id')!;
  const check = await env.DB.prepare('SELECT created_at FROM account_update_checks WHERE account_id=? AND check_id=?')
    .bind(accountId, checkId).first<{ created_at: number }>();
  if (!check) throw backendUnavailable();
  const migration: LegacyMigration = { mode: 'uid-v1', accountId, checkId, ...source,
    targetVersionCode: LEGACY_TARGET_VERSION, targetImageSha256: targetImage, targetReleaseId: body.releaseId,
    assetId: asset.assetId, assetSha256: asset.sha256, expiresAt: check.created_at + lifetimeMs };
  return json({ ...body, legacyMigration: migration }, response.status, response.headers);
}

export async function preparedLegacy(env: WorkerEnv, accountId: string, checkId: unknown): Promise<LegacyMigration> {
  if (typeof checkId !== 'string' || !/^[a-zA-Z0-9_-]{16,80}$/.test(checkId)) throw invalid();
  const row = await env.DB.prepare(`SELECT state,kind,created_at,response_json FROM account_update_checks
    WHERE account_id=? AND check_id=?`).bind(accountId, checkId)
    .first<{ state: string; kind: string; created_at: number; response_json: string | null }>();
  const now = Date.now();
  if (!row || row.state !== 'complete' || row.kind !== 'manual' || !row.response_json ||
      now < row.created_at || now >= row.created_at + lifetimeMs) throw invalid();
  let body: Record<string, unknown>;
  try { body = JSON.parse(row.response_json); } catch { throw invalid(); }
  const grant = body.legacyMigration as LegacyMigration | undefined;
  const asset = body.asset as Record<string, unknown> | undefined;
  if (!grant || grant.mode !== 'uid-v1' || grant.accountId !== accountId || grant.checkId !== checkId ||
      grant.sourceVersionCode !== LEGACY_SOURCE_VERSION || grant.targetVersionCode !== LEGACY_TARGET_VERSION ||
      grant.targetImageSha256 !== targetImage || !/^[0-9a-f]{64}$/.test(grant.sourceImageSha256) ||
      grant.expiresAt !== row.created_at + lifetimeMs || body.versionCode !== grant.targetVersionCode ||
      body.targetImageSha256 !== grant.targetImageSha256 || body.releaseId !== grant.targetReleaseId ||
      asset?.kind !== 'full' || asset.assetId !== grant.assetId || asset.sha256 !== grant.assetSha256) throw invalid();
  await target(env, grant.targetReleaseId, grant.assetId, grant.assetSha256);
  return grant;
}

export async function legacyDownload(request: Request, env: WorkerEnv, accountId: string): Promise<void> {
  const grant = await preparedLegacy(env, accountId, request.headers.get('X-Legacy-Migration-Check-Id'));
  // The existing signed URL remains mandatory; no new token or purpose is introduced.
  const token = await verifyFirmwareDownload(request, env);
  if (token.purpose !== 'public-ota' || token.kind !== 'full' ||
      token.assetId !== grant.assetId || token.releaseId !== grant.targetReleaseId) throw invalid();
}

export async function authorizeLegacy(env: WorkerEnv, accountId: string, body: Record<string, unknown>) {
  const grant = await preparedLegacy(env, accountId, body.legacyCheckId);
  for (const key of ['sourceVersionCode','sourceImageSha256','hardwareRevision','layoutId','bootVersion',
    'protocolVersion','targetVersionCode','targetImageSha256','targetReleaseId','assetId','assetSha256'] as const) {
    if (body[key] !== grant[key]) throw invalid();
  }
  await env.DB.prepare('INSERT INTO account_audit(id,actor,action,account_id,occurred_at) VALUES(?,?,?,?,?)')
    .bind(crypto.randomUUID(), accountId, 'legacy_ota_authorize', accountId, Date.now()).run();
  return json({ ok: true, accountId, authorizedAt: Date.now(), legacyMigration: true });
}
