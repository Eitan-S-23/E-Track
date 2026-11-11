import { canonicalJson, exactObject, FIRMWARE_MODEL, r2KeyFor, text } from "../../scripts/firmware-schema.mjs";
import { ApiError, backendUnavailable, invalidParameter } from "./errors";
import { firmwareAssets, firmwareOperation, readFirmwareJson, requireFirmwareJsonHeaders } from "./firmware";
import type { FirmwareAdminActor } from "./firmware_admin";
import { json } from "./http";
import type { FirmwareReleaseRow, FirmwareStorageEnv } from "./types";

export function deleteFirmwareFiles(request: Request, env: FirmwareStorageEnv,
  actor: FirmwareAdminActor, releaseId: string): Promise<Response> {
  return firmwareOperation(async () => {
    requireFirmwareJsonHeaders(request);
    const body = exactObject(await readFirmwareJson(request), ["appId", "deviceModel", "reason"]);
    const reason = text(body.reason, "reason");
    if (body.appId !== "trace" || body.deviceModel !== FIRMWARE_MODEL
      || !/^[A-Za-z0-9._-]+$/.test(releaseId) || releaseId.includes("..")) throw invalidParameter("Invalid firmware scope or releaseId");
    const release = await env.DB.prepare("SELECT * FROM firmware_releases WHERE id=?")
      .bind(releaseId).first<FirmwareReleaseRow>();
    if (!release || release.app_id !== body.appId || release.device_model !== body.deviceModel) {
      throw new ApiError("RELEASE_NOT_FOUND", "Firmware release not found", 404);
    }
    if (await env.DB.prepare("SELECT id FROM firmware_channels WHERE current_release_id=?").bind(releaseId).first()) {
      throw new ApiError("RELEASE_IN_USE", "Move every channel away from this release before deletion", 409);
    }
    if (release.state !== "disabled") throw new ApiError("RELEASE_CONFLICT", "Disable this release before deleting its files", 409);
    const guards = await env.DB.prepare(`SELECT name FROM sqlite_master WHERE type='trigger' AND name IN
      ('firmware_disabled_assets_sealed','firmware_archive_no_reopen','firmware_deleted_asset_no_restore')`).all();
    if (guards.results.length !== 3) throw backendUnavailable("Firmware deletion migration is required");
    const assets = await firmwareAssets(env.DB, releaseId);
    const remaining = assets.filter(a => a.r2_state !== "r2_deleted");
    if (assets.length > 64) throw backendUnavailable("Unexpected firmware asset count");
    const identity = { appId: release.app_id, deviceModel: release.device_model,
      versionCode: release.version_code, releaseTag: release.release_tag };
    for (const asset of remaining) {
      if (!asset.r2_key) {
        if (asset.r2_state === "available") throw backendUnavailable("Firmware file has no R2 identity");
        continue;
      }
      if (asset.r2_key !== r2KeyFor(identity, { fileName: asset.file_name })) {
        throw new ApiError("R2_OBJECT_CONFLICT", "Firmware file is outside its release namespace", 409);
      }
      const shared = await env.DB.prepare(`SELECT id FROM firmware_release_assets WHERE r2_key=? AND release_id<>?
        UNION ALL SELECT id FROM firmware_releases_legacy WHERE r2_key=? LIMIT 1`)
        .bind(asset.r2_key, releaseId, asset.r2_key).first();
      if (shared) throw new ApiError("RELEASE_IN_USE", "Firmware file has another retained release reference", 409);
      const object = await env.RELEASES_BUCKET.head(asset.r2_key);
      if (object && (object.size !== asset.size_bytes || !asset.r2_etag || object.httpEtag !== asset.r2_etag
        || object.customMetadata?.sha256 !== asset.sha256 || object.customMetadata?.kind !== asset.kind)) {
        throw new ApiError("R2_OBJECT_CONFLICT", "Firmware R2 identity changed; deletion stopped", 409);
      }
    }

    const actorEmail = actor.email.trim().toLowerCase();
    // Archive and audit atomically before touching R2. A partial deletion stays
    // unavailable; an explicit new confirmation resumes only the remaining files.
    const archived = await env.DB.batch<FirmwareReleaseRow>([
      env.DB.prepare(`UPDATE firmware_releases SET archived=1,updated_at=datetime('now')
        WHERE id=? AND state='disabled' AND archived=0`).bind(releaseId),
      env.DB.prepare(`INSERT INTO audit_logs(id,app_id,actor,actor_type,action,target_type,target_id,request_id,reason,before_json,after_json)
        SELECT ?,?,?,'access','archive_for_file_deletion','firmware_release',?,?,?,?,? WHERE changes()=1`)
        .bind(crypto.randomUUID(), release.app_id, actorEmail, releaseId, actor.requestId, reason,
          canonicalJson({ state: "disabled", archived: false }), canonicalJson({ state: "disabled", archived: true })),
      env.DB.prepare("SELECT * FROM firmware_releases WHERE id=? AND state='disabled' AND archived=1").bind(releaseId)
    ]);
    if (!archived[2].results[0]) throw backendUnavailable("Firmware archive was not confirmed");
    for (const asset of remaining) {
      if (!asset.r2_key) continue;
      await env.RELEASES_BUCKET.delete(asset.r2_key);
      if (await env.RELEASES_BUCKET.head(asset.r2_key)) throw backendUnavailable("Firmware file deletion was not confirmed");
    }
    const result = { ok: true, requestId: actor.requestId, action: "delete_files", releaseId,
      state: "disabled", archived: true, retainedHistory: true, assetCount: assets.length,
      idempotent: release.archived === 1 && remaining.length === 0 };
    await env.DB.batch([
      env.DB.prepare(`INSERT INTO audit_logs(id,app_id,actor,actor_type,action,target_type,target_id,request_id,reason,before_json,after_json)
        SELECT ?,?,?,'access','delete_firmware_files','firmware_release',?,?,?,NULL,?
        WHERE EXISTS (SELECT 1 FROM firmware_release_assets WHERE release_id=? AND r2_state<>'r2_deleted')`)
        .bind(crypto.randomUUID(), release.app_id, actorEmail, releaseId, actor.requestId, reason, canonicalJson(result), releaseId),
      env.DB.prepare(`UPDATE firmware_release_assets SET r2_state='r2_deleted',updated_at=datetime('now')
        WHERE release_id=? AND r2_state<>'r2_deleted'`).bind(releaseId)
    ]);
    return json(result, 200, { "X-Request-Id": actor.requestId });
  });
}
