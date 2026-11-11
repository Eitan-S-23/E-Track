import { canonicalJson, exactObject, FIRMWARE_MODEL, text } from "../../scripts/firmware-schema.mjs";
import { ApiError, backendUnavailable, invalidParameter } from "./errors";
import { firmwareOperation } from "./firmware";
import type { FirmwareAdminActor } from "./firmware_admin";
import { json } from "./http";
import type { FirmwareReleaseRow, FirmwareStorageEnv } from "./types";

function scoped(input: Record<string, unknown>): void {
  if (input.appId !== "trace" || input.deviceModel !== FIRMWARE_MODEL) {
    throw invalidParameter("Invalid firmware appId/deviceModel");
  }
}

export function editFirmwareNotes(env: FirmwareStorageEnv, actor: FirmwareAdminActor,
  releaseId: string, body: unknown): Promise<Response> {
  return firmwareOperation(async () => {
    const input = exactObject(body, ["appId", "deviceModel", "releaseNotes", "expectedNotes", "reason"]);
    scoped(input);
    const notes = text(input.releaseNotes, "releaseNotes", true);
    const expected = text(input.expectedNotes, "expectedNotes", true);
    const reason = text(input.reason, "reason");
    if (notes.length > 8000 || reason.length > 2000) throw invalidParameter("Firmware notes/reason is too long");
    const current = () => env.DB.prepare("SELECT * FROM firmware_releases WHERE id=? AND app_id=? AND device_model=?")
      .bind(releaseId, "trace", FIRMWARE_MODEL).first<FirmwareReleaseRow>();
    const release = await current();
    if (!release) throw new ApiError("RELEASE_NOT_FOUND", "Firmware release not found", 404);
    if (release.archived) throw new ApiError("RELEASE_ARCHIVED", "Firmware release archived", 410);
    if (release.state === "disabled") throw new ApiError("RELEASE_DISABLED", "Firmware release disabled", 410);
    if (release.release_notes !== expected) throw new ApiError("CAS_CONFLICT", "Firmware notes changed; reload before saving", 409);
    if (notes === expected) return json({ ok: true, requestId: actor.requestId, action: "edit_notes",
      releaseId, releaseNotes: notes, idempotent: true });
    const results = await env.DB.batch([
      env.DB.prepare(`UPDATE firmware_releases SET release_notes=?,updated_at=datetime('now')
        WHERE id=? AND app_id=? AND device_model=? AND release_notes=? AND archived=0 AND state IN ('draft','ready')
        RETURNING id`).bind(notes, releaseId, "trace", FIRMWARE_MODEL, expected),
      env.DB.prepare(`INSERT INTO audit_logs(id,app_id,actor,actor_type,action,target_type,target_id,
        request_id,reason,before_json,after_json)
        SELECT ?,?,?,'access','edit_notes','firmware_release',?,?,?,?,? WHERE changes()=1`)
        .bind(crypto.randomUUID(), "trace", actor.email.trim().toLowerCase(), releaseId, actor.requestId,
          reason, canonicalJson({ releaseNotes: expected }), canonicalJson({ releaseNotes: notes }))
    ]);
    if (results[0].results.length !== 1) {
      const latest = await current();
      if (latest?.archived) throw new ApiError("RELEASE_ARCHIVED", "Firmware release archived", 410);
      if (latest?.state === "disabled") throw new ApiError("RELEASE_DISABLED", "Firmware release disabled", 410);
      throw new ApiError("CAS_CONFLICT", "Firmware notes changed; reload before saving", 409);
    }
    return json({ ok: true, requestId: actor.requestId, action: "edit_notes", releaseId, releaseNotes: notes, idempotent: false });
  });
}

interface HistoryRow {
  id: string; action: string; actor: string; created_at: string; reason: string | null;
  target_type: string; target_id: string; request_id: string | null;
  before_json: string | null; after_json: string | null;
  release_id: string | null; release_tag: string | null; channel: string | null;
}

function snapshot(raw: string | null): Record<string, unknown> {
  if (!raw) return {};
  let value: unknown;
  try { value = JSON.parse(raw); } catch { throw backendUnavailable("Invalid firmware audit snapshot"); }
  if (!value || typeof value !== "object" || Array.isArray(value)) throw backendUnavailable("Invalid firmware audit snapshot");
  const safe: Record<string, unknown> = {};
  // Capabilities, signatures and storage keys are never returned by the history API.
  for (const key of ["currentReleaseId", "revision", "disableLatest", "disableDownloads", "maintenanceMessage",
    "state", "archived", "releaseNotes", "r2State", "deletedObjects", "assetCount", "retainedHistory"]) {
    const field = (value as Record<string, unknown>)[key];
    if (field === null || ["string", "number", "boolean"].includes(typeof field)) safe[key] = field;
  }
  return safe;
}

export function firmwareHistory(env: FirmwareStorageEnv, url: URL, requestId: string): Promise<Response> {
  return firmwareOperation(async () => {
    const allowed = ["appId", "deviceModel", "releaseId", "limit", "cursor"];
    for (const key of url.searchParams.keys()) {
      if (!allowed.includes(key) || url.searchParams.getAll(key).length !== 1) throw invalidParameter("Invalid history query");
    }
    scoped(Object.fromEntries(url.searchParams));
    const limitText = url.searchParams.get("limit") ?? "25";
    if (!/^[1-9][0-9]?$/.test(limitText) || Number(limitText) > 50) throw invalidParameter("History limit must be 1..50");
    const limit = Number(limitText);
    const releaseId = url.searchParams.get("releaseId");
    if (releaseId !== null && (!/^[A-Za-z0-9._-]{1,200}$/.test(releaseId) || releaseId.includes(".."))) {
      throw invalidParameter("Invalid history releaseId");
    }
    const cursor = url.searchParams.get("cursor");
    let beforeTime = "", beforeId = "";
    if (cursor !== null) {
      const match = /^(\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2})\|([A-Za-z0-9._:-]{1,128})$/.exec(cursor);
      if (!match) throw invalidParameter("Invalid history cursor");
      [, beforeTime, beforeId] = match;
    }
    const conditions = ["l.app_id=?", "(c.id IS NOT NULL OR r.id IS NOT NULL)"];
    const values: (string | number)[] = ["trace", FIRMWARE_MODEL, "trace", FIRMWARE_MODEL, "trace"];
    if (releaseId !== null) {
      conditions.push(`(r.id=? OR (c.id IS NOT NULL AND
        (CASE WHEN json_valid(l.before_json) THEN json_extract(l.before_json,'$.currentReleaseId') END=?
         OR CASE WHEN json_valid(l.after_json) THEN json_extract(l.after_json,'$.currentReleaseId') END=?)))`);
      values.push(releaseId, releaseId, releaseId);
    }
    if (cursor !== null) {
      conditions.push("(l.created_at<? OR (l.created_at=? AND l.id<?))");
      values.push(beforeTime, beforeTime, beforeId);
    }
    const rows = (await env.DB.prepare(`SELECT l.id,l.action,l.actor,l.created_at,l.reason,l.target_type,
        l.target_id,l.request_id,l.before_json,l.after_json,r.id AS release_id,r.release_tag,c.name AS channel
      FROM audit_logs l
      LEFT JOIN firmware_channels c ON l.target_type='firmware_channel' AND l.target_id=c.id
        AND c.app_id=? AND c.device_model=?
      LEFT JOIN firmware_release_assets a ON l.target_type='firmware_asset' AND l.target_id=a.id
      LEFT JOIN firmware_releases r ON r.id=CASE WHEN l.target_type='firmware_release' THEN l.target_id ELSE a.release_id END
        AND r.app_id=? AND r.device_model=?
      WHERE ${conditions.join(" AND ")} ORDER BY l.created_at DESC,l.id DESC LIMIT ?`)
      .bind(...values, limit + 1).all<HistoryRow>()).results;
    const page = rows.slice(0, limit);
    const last = page.at(-1);
    return json({ ok: true, requestId, history: page.map(row => ({ id: row.id, action: row.action,
      actor: row.actor, createdAt: row.created_at, reason: row.reason, targetType: row.target_type,
      targetId: row.target_id, requestId: row.request_id, releaseId: row.release_id, releaseTag: row.release_tag,
      channel: row.channel, before: snapshot(row.before_json), after: snapshot(row.after_json) })),
      nextCursor: rows.length > limit && last ? `${last.created_at}|${last.id}` : null });
  });
}
