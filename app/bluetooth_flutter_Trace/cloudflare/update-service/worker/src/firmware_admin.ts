import { canonicalJson, exactObject, FIRMWARE_MODEL, integer, text } from "../../scripts/firmware-schema.mjs";
import { sha256Hex } from "./crypto";
import { ApiError, backendUnavailable, invalidParameter } from "./errors";
import { firmwareAssets, firmwareOperation, readFirmwareJson, requireFirmwareFull, requireFirmwareJsonHeaders,
  usableFirmwareAsset } from "./firmware";
import { signFirmwareDownload, verifyFirmwareObject } from "./firmware_download";
import { json } from "./http";
import type { FirmwareChannelRow, FirmwareReleaseRow, FirmwareSigningEnv, FirmwareStorageEnv } from "./types";

export type FirmwareAdminEnv = FirmwareStorageEnv & FirmwareSigningEnv & { FIRMWARE_DOWNLOAD_ORIGIN?: string };
export interface FirmwareAdminActor { email: string; requestId: string }
type Action = "disable" | "recovery-download";
interface IdempotencyRow {
  actor_canonical: string; idempotency_key: string; fingerprint: string; action: Action; release_id: string;
  state: "pending" | "completed"; status_code: number; response_body_json: string; request_id: string;
  retained_until: number; original_expires_at: number | null;
}
interface Tombstone { fingerprint: string; action: Action; release_id: string; expired_at: number }

function scope(body: Record<string, unknown>): void {
  if (body.appId !== "trace" || body.deviceModel !== FIRMWARE_MODEL) throw invalidParameter("Invalid firmware appId/deviceModel");
}
function releaseIdentity(value: string): string {
  if (!/^[A-Za-z0-9._-]+$/.test(value) || value.includes("..")) throw invalidParameter("Invalid releaseId");
  return value;
}
function ready(release: FirmwareReleaseRow | null): asserts release is FirmwareReleaseRow {
  if (!release || release.app_id !== "trace" || release.device_model !== FIRMWARE_MODEL) throw new ApiError("RELEASE_NOT_FOUND", "Firmware release not found", 404);
  if (release.archived) throw new ApiError("RELEASE_ARCHIVED", "Firmware release archived", 410);
  if (release.state === "disabled") throw new ApiError("RELEASE_DISABLED", "Firmware release disabled", 410);
  if (release.state !== "ready") throw new ApiError("RELEASE_NOT_READY", "Firmware release not ready", 409);
}

export function listFirmware(env: FirmwareStorageEnv, url: URL, requestId: string, channels: boolean): Promise<Response> {
  return firmwareOperation(async () => {
    for (const key of url.searchParams.keys()) if (!["appId", "deviceModel"].includes(key)) throw invalidParameter("Unknown firmware list parameter");
    for (const key of ["appId", "deviceModel"]) if (url.searchParams.getAll(key).length !== 1) throw invalidParameter("Required firmware scope missing/duplicated");
    scope(Object.fromEntries(url.searchParams));
    const channelRows = (await env.DB.prepare("SELECT * FROM firmware_channels WHERE app_id=? AND device_model=? ORDER BY name")
      .bind("trace", FIRMWARE_MODEL).all<FirmwareChannelRow>()).results;
    if (channels) return json({ ok: true, requestId, firmwareChannels: channelRows.map((c) => ({
      appId: c.app_id, deviceModel: c.device_model, channel: c.name, ...channelSnapshot(c),
      ...(c.legacy_current_release_id ? { legacyPending: true } : {}) })) });
    const releases = (await env.DB.prepare("SELECT * FROM firmware_releases WHERE app_id=? AND device_model=? ORDER BY version_code DESC")
      .bind("trace", FIRMWARE_MODEL).all<FirmwareReleaseRow>()).results;
    const result = [];
    for (const r of releases) result.push({ releaseId: r.id, appId: r.app_id, deviceModel: r.device_model,
      versionName: r.version_name, versionCode: r.version_code, releaseTag: r.release_tag, state: r.state,
      archived: r.archived === 1, releaseNotes: r.release_notes, targetImageSha256: r.target_image_sha256,
      publishedChannels: channelRows.filter((c) => c.current_release_id === r.id).map((c) => c.name),
      assets: (await firmwareAssets(env.DB, r.id)).map((a) => ({ assetId: a.id, kind: a.kind, fileName: a.file_name,
        sha256: a.sha256, sizeBytes: a.size_bytes, r2State: a.r2_state, baseVersionCode: a.base_vcode,
        baseImageSha256: a.kind === "patch" ? a.base_image_sha256 : null })) });
    return json({ ok: true, requestId, firmwareReleases: result });
  });
}

export function channelSnapshot(c: FirmwareChannelRow) {
  return { currentReleaseId: c.current_release_id, revision: c.revision,
    disableLatest: c.disable_latest === 1, disableDownloads: c.disable_downloads === 1,
    maintenanceMessage: c.maintenance_message };
}

export function publishFirmware(env: FirmwareStorageEnv, actor: FirmwareAdminActor, name: string, body: unknown): Promise<Response> {
  return firmwareOperation(async () => {
    const input = exactObject(body, ["appId", "deviceModel", "releaseId", "expectedRevision", "reason"]);
    scope(input);
    const releaseId = releaseIdentity(text(input.releaseId, "releaseId"));
    const revision = integer(input.expectedRevision, "expectedRevision");
    const reason = text(input.reason, "reason");
    const channel = await env.DB.prepare("SELECT * FROM firmware_channels WHERE app_id=? AND device_model=? AND name=?")
      .bind("trace", FIRMWARE_MODEL, name).first<FirmwareChannelRow>();
    if (!channel) throw new ApiError("RELEASE_NOT_FOUND", "Firmware channel not found", 404);
    if (channel.revision !== revision) throw new ApiError("CAS_CONFLICT", "Firmware channel changed", 409);
    const target = await env.DB.prepare("SELECT * FROM firmware_releases WHERE id=?").bind(releaseId).first<FirmwareReleaseRow>();
    ready(target);
    const assets = await firmwareAssets(env.DB, target.id);
    if (assets.some((a) => a.r2_state === "archived" || a.r2_state === "r2_deleted")) throw new ApiError("ASSET_ARCHIVED", "Firmware asset archived", 409);
    requireFirmwareFull(target, assets);
    if (assets.some((a) => !usableFirmwareAsset(a))) throw new ApiError("RELEASE_INCOMPLETE", "Firmware asset unavailable", 409);
    const current = channel.current_release_id
      ? await env.DB.prepare("SELECT version_code FROM firmware_releases WHERE id=?").bind(channel.current_release_id).first<{ version_code: number }>()
      : channel.legacy_current_release_id
        ? await env.DB.prepare("SELECT version_code FROM firmware_releases_legacy WHERE id=?").bind(channel.legacy_current_release_id).first<{ version_code: number }>()
        : null;
    if (current && target.version_code <= current.version_code) throw new ApiError("VERSION_REGRESSION", "Publish must advance firmware version", 409);
    const after = { ...channelSnapshot(channel), currentReleaseId: releaseId, revision: revision + 1 };
    // The schema trigger inserts the audit in this same statement/transaction.
    const result = await env.DB.batch<FirmwareChannelRow>([env.DB.prepare(`UPDATE firmware_channels SET current_release_id=?,
      legacy_current_release_id=NULL,revision=revision+1,last_action='publish',last_actor=?,last_actor_type='access',
      last_request_id=?,last_reason=?,last_before_json=?,last_after_json=?,updated_at=datetime('now')
      WHERE id=? AND revision=? RETURNING *`).bind(releaseId, actor.email, actor.requestId, reason,
      canonicalJson(channelSnapshot(channel)), canonicalJson(after), channel.id, revision)]);
    const updated = result[0].results[0];
    if (!updated) throw new ApiError("CAS_CONFLICT", "Firmware channel changed", 409);
    return json({ ok: true, requestId: actor.requestId, action: "publish", channel: updated.name,
      ...channelSnapshot(updated), idempotent: false });
  });
}

function tombstoneInsert(db: D1Database, now: number, actor?: string, key?: string): D1PreparedStatement {
  const sql = `INSERT INTO firmware_admin_idempotency_tombstones
    (actor_canonical,idempotency_key,fingerprint,action,release_id,expired_at,tombstoned_at)
    SELECT actor_canonical,idempotency_key,fingerprint,action,release_id,retained_until,?
    FROM firmware_admin_idempotency WHERE state='completed' AND retained_until<=?
    ${actor === undefined ? "" : "AND actor_canonical=? AND idempotency_key=?"}
    ON CONFLICT(actor_canonical,idempotency_key) DO NOTHING`;
  return actor === undefined ? db.prepare(sql).bind(now, now) : db.prepare(sql).bind(now, now, actor, key!);
}

export async function cleanupFirmwareIdempotency(db: D1Database, now = Math.floor(Date.now() / 1000)): Promise<number> {
  const results = await db.batch([tombstoneInsert(db, now), db.prepare(
    "DELETE FROM firmware_admin_idempotency WHERE state='completed' AND retained_until<=?").bind(now)]);
  return results[1].meta.changes;
}

async function replayResult(db: D1Database, actor: string, key: string, fingerprint: string, now: number): Promise<Response | null> {
  const records = await db.batch<Tombstone | IdempotencyRow>([
    db.prepare("SELECT * FROM firmware_admin_idempotency_tombstones WHERE actor_canonical=? AND idempotency_key=?").bind(actor, key),
    db.prepare("SELECT * FROM firmware_admin_idempotency WHERE actor_canonical=? AND idempotency_key=?").bind(actor, key)
  ]);
  const t = records[0].results[0];
  const r = records[1].results[0];
  if ((t && !("expired_at" in t)) || (r && !("state" in r))) throw backendUnavailable("Idempotency row shape mismatch");
  const tombstone = t && "expired_at" in t ? t : undefined;
  const row = r && "state" in r ? r : undefined;
  if (row && row.state !== "completed") throw backendUnavailable("Incomplete idempotency result");
  if (tombstone && row && (tombstone.fingerprint !== row.fingerprint || tombstone.action !== row.action
    || tombstone.release_id !== row.release_id || tombstone.expired_at !== row.retained_until)) throw backendUnavailable("Idempotency integrity failure");
  if (row && now >= row.retained_until) await db.batch([tombstoneInsert(db, now, actor, key)]);
  const original = tombstone ?? row;
  if (!original) return null;
  if (original.fingerprint !== fingerprint) throw new ApiError("IDEMPOTENCY_CONFLICT", "Idempotency request changed", 409);
  if (tombstone || !row || now >= row.retained_until || (row.original_expires_at !== null && now >= row.original_expires_at)) {
    throw new ApiError("IDEMPOTENCY_RESULT_EXPIRED", "Original idempotency result expired; use a new key", 409);
  }
  const body = JSON.parse(row.response_body_json) as Record<string, unknown>;
  if (row.status_code !== 200 || body.ok !== true || body.requestId !== row.request_id
    || body.releaseId !== row.release_id || body.idempotent !== false
    || body.action !== (row.action === "disable" ? "disable_release" : "issue_recovery_download")
    || (row.action === "recovery-download" && body.expiresAt !== row.original_expires_at)) {
    throw backendUnavailable("Idempotency result integrity failure");
  }
  return json({ ...body, idempotent: true }, 200, { "X-Request-Id": row.request_id });
}

export function firmwareReleaseAction(request: Request, env: FirmwareAdminEnv, actor: FirmwareAdminActor, id: string, action: Action): Promise<Response> {
  return firmwareOperation(async () => {
    const lookupEpoch = Math.floor(Date.now() / 1000);
    requireFirmwareJsonHeaders(request);
    const releaseId = releaseIdentity(id);
    const body = exactObject(await readFirmwareJson(request), ["appId", "deviceModel", "reason"]);
    scope(body);
    const reason = text(body.reason, "reason");
    const key = request.headers.get("Idempotency-Key");
    if (!key || !/^[0-9a-f]{8}-[0-9a-f]{4}-4[0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$/.test(key)) {
      throw invalidParameter("Idempotency-Key must be a lowercase UUIDv4");
    }
    const actorCanonical = actor.email.trim().toLowerCase();
    const path = `/api/admin/firmware/releases/${releaseId}/${action}`;
    const fingerprint = await sha256Hex(canonicalJson({ method: "POST", path, body }));
    const existing = await replayResult(env.DB, actorCanonical, key, fingerprint, lookupEpoch);
    if (existing) return existing;
    const release = await env.DB.prepare("SELECT * FROM firmware_releases WHERE id=?").bind(releaseId).first<FirmwareReleaseRow>();
    if (!release || release.app_id !== body.appId || release.device_model !== body.deviceModel) throw new ApiError("RELEASE_NOT_FOUND", "Firmware release not found", 404);
    if (release.archived) throw new ApiError("RELEASE_ARCHIVED", "Firmware release archived", 410);
    if (release.state === "disabled") throw new ApiError("RELEASE_DISABLED", "Firmware release disabled", 410);
    const auditId = crypto.randomUUID();
    const statements: D1PreparedStatement[] = [];
    let now: number;
    let result: Record<string, unknown>;
    let expiresAt: number | null = null;
    if (action === "disable") {
      if (await env.DB.prepare("SELECT id FROM firmware_channels WHERE current_release_id=?").bind(releaseId).first()) {
        throw new ApiError("RELEASE_IN_USE", "Firmware release is still referenced", 409);
      }
      now = Math.floor(Date.now() / 1000);
      statements.push(env.DB.prepare("UPDATE firmware_releases SET state='disabled',updated_at=datetime('now') WHERE id=? AND state=? AND archived=0")
        .bind(releaseId, release.state));
      statements.push(env.DB.prepare(`INSERT INTO audit_logs(id,app_id,actor,actor_type,action,target_type,target_id,request_id,reason,before_json,after_json)
        SELECT ?,?,?,'access','disable_release','firmware_release',?,?,?,?,? WHERE changes()=1`)
        .bind(auditId, release.app_id, actorCanonical, releaseId, actor.requestId, reason,
          canonicalJson({ state: release.state, archived: release.archived }), canonicalJson({ state: "disabled", archived: release.archived })));
      result = { ok: true, requestId: actor.requestId, action: "disable_release", releaseId, state: "disabled", idempotent: false };
    } else {
      ready(release);
      const recovery = (await firmwareAssets(env.DB, releaseId)).filter((a) => a.kind === "recovery");
      if (recovery.length !== 1) throw new ApiError("RECOVERY_ASSET_UNAVAILABLE", "Exactly one recovery asset is required", 409);
      const asset = recovery[0];
      if (["archived", "r2_deleted"].includes(asset.r2_state)) throw new ApiError("ASSET_ARCHIVED", "Recovery asset archived", 409);
      if (!usableFirmwareAsset(asset)) throw new ApiError("RECOVERY_ASSET_UNAVAILABLE", "Recovery asset is incomplete", 409);
      try {
        const etag = await verifyFirmwareObject(env.RELEASES_BUCKET, { r2Key: asset.r2_key!, kind: "recovery", sha256: asset.sha256, sizeBytes: asset.size_bytes });
        if (etag !== asset.r2_etag) throw new Error("R2 identity changed");
      } catch { throw new ApiError("R2_VERIFY_FAILED", "Recovery R2 readback could not be confirmed", 503); }
      if (!env.FIRMWARE_DOWNLOAD_ORIGIN) throw backendUnavailable("Firmware download origin is not configured");
      now = Math.floor(Date.now() / 1000);
      // HMAC calculation is pure. The capability is issued only if this batch commits.
      const signed = await signFirmwareDownload(env, env.FIRMWARE_DOWNLOAD_ORIGIN, asset, "admin-recovery", now);
      expiresAt = signed.expiresAt;
      const identity = { releaseId, assetId: asset.id, kind: "recovery", r2State: asset.r2_state, sha256: asset.sha256, sizeBytes: asset.size_bytes };
      statements.push(env.DB.prepare(`INSERT INTO audit_logs(id,app_id,actor,actor_type,action,target_type,target_id,request_id,reason,before_json,after_json)
        SELECT ?,?,?,'access','issue_recovery_download','firmware_asset',?,?,?,?,?
        FROM firmware_release_assets a JOIN firmware_releases r ON r.id=a.release_id
        WHERE a.id=? AND r.id=? AND r.state='ready' AND r.archived=0 AND a.kind='recovery'
          AND a.r2_state='available' AND a.r2_key=? AND a.r2_etag=? AND a.sha256=? AND a.size_bytes=?`)
        .bind(auditId, release.app_id, actorCanonical, asset.id, actor.requestId, reason, canonicalJson(identity),
          canonicalJson({ ...identity, purpose: "admin-recovery", expiresAt }), asset.id, releaseId,
          asset.r2_key, asset.r2_etag, asset.sha256, asset.size_bytes));
      result = { ok: true, requestId: actor.requestId, action: "issue_recovery_download", releaseId, assetId: asset.id,
        kind: "recovery", fileName: asset.file_name, sha256: asset.sha256, sizeBytes: asset.size_bytes, ...signed, idempotent: false };
    }
    statements.unshift(
      env.DB.prepare("SELECT fingerprint FROM firmware_admin_idempotency_tombstones WHERE actor_canonical=? AND idempotency_key=?").bind(actorCanonical, key),
      env.DB.prepare("SELECT state FROM firmware_admin_idempotency WHERE actor_canonical=? AND idempotency_key=?").bind(actorCanonical, key),
      env.DB.prepare(`INSERT INTO firmware_admin_idempotency
        (actor_canonical,idempotency_key,fingerprint,method,canonical_path,action,release_id,state,created_epoch_seconds,retained_until)
        VALUES (?,?,?,'POST',?,?,?,'pending',?,?)`).bind(actorCanonical, key, fingerprint, path, action, releaseId, now, now + 86400)
    );
    statements.push(env.DB.prepare(`UPDATE firmware_admin_idempotency SET state='completed',status_code=200,
      response_body_json=?,request_id=?,original_expires_at=? WHERE actor_canonical=? AND idempotency_key=?
      AND state='pending' AND EXISTS (SELECT 1 FROM audit_logs WHERE id=?)`)
      .bind(canonicalJson(result), actor.requestId, expiresAt, actorCanonical, key, auditId));
    try { await env.DB.batch(statements); } catch {
      const concurrent = await replayResult(env.DB, actorCanonical, key, fingerprint, Math.floor(Date.now() / 1000));
      if (concurrent) return concurrent;
      const current = await env.DB.prepare("SELECT * FROM firmware_releases WHERE id=?").bind(releaseId).first<FirmwareReleaseRow>();
      if (current?.archived) throw new ApiError("RELEASE_ARCHIVED", "Firmware release archived", 410);
      if (current?.state === "disabled") throw new ApiError("RELEASE_DISABLED", "Firmware release disabled", 410);
      if (action === "disable" && await env.DB.prepare("SELECT id FROM firmware_channels WHERE current_release_id=?").bind(releaseId).first()) {
        throw new ApiError("RELEASE_IN_USE", "Firmware release is still referenced", 409);
      }
      throw backendUnavailable("Firmware action did not commit");
    }
    return json(result, 200, { "X-Request-Id": actor.requestId });
  });
}
