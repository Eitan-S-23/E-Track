import { ApiError } from "./errors";
import { canonicalJson } from "./crypto";
import type { Actor, ChannelName, ChannelRow, Platform, ReleaseRow, WorkerEnv } from "./types";

export interface PublishInput extends Actor {
  appId: string;
  platform: Platform;
  channel: ChannelName;
  releaseId: string;
  expectedRevision: number;
  rollback: boolean;
}

export interface ActionResult {
  ok: boolean;
  errorCode?: string;
  status?: number;
}

export async function publishRelease(env: WorkerEnv, input: PublishInput): Promise<ActionResult> {
  const channel = await env.DB.prepare(
    "SELECT * FROM channels WHERE app_id = ? AND platform = ? AND name = ? LIMIT 1"
  )
    .bind(input.appId, input.platform, input.channel)
    .first<ChannelRow>();
  if (!channel) throw new ApiError("RELEASE_NOT_FOUND", "Channel not found", 404);

  const target = await env.DB.prepare("SELECT * FROM releases WHERE id = ? LIMIT 1")
    .bind(input.releaseId)
    .first<ReleaseRow>();
  if (!target || target.app_id !== input.appId || target.platform !== input.platform) {
    throw new ApiError("RELEASE_NOT_FOUND", "Release not found", 404);
  }
  if (target.state === "disabled") {
    throw new ApiError("RELEASE_DISABLED", "Disabled release cannot be published", 410);
  }
  if (target.archived === 1) {
    return { ok: false, errorCode: "ASSET_ARCHIVED", status: 409 };
  }
  if (target.release_notes.trim() === "") {
    throw new ApiError("RELEASE_NOTES_REQUIRED", "Release notes are required before publish", 409);
  }

  if (channel.current_release_id && !input.rollback) {
    const current = await env.DB.prepare("SELECT version_code FROM releases WHERE id = ? LIMIT 1")
      .bind(channel.current_release_id)
      .first<{ version_code: number }>();
    if (current && target.version_code <= current.version_code) {
      return { ok: false, errorCode: "VERSION_REGRESSION", status: 409 };
    }
  }

  await ensureAndroidCompleteness(env, target);

  const beforeJson = canonicalJson(channelSnapshot(channel));
  const afterJson = canonicalJson(channelSnapshot(channel, target.id));
  const updatedChannel = await env.DB.prepare(
    `
      UPDATE channels
      SET
        current_release_id = ?,
        revision = revision + 1,
        last_action = ?,
        last_actor = ?,
        last_actor_type = ?,
        last_request_id = ?,
        last_before_json = ?,
        last_after_json = ?,
        updated_at = datetime('now')
      WHERE id = ? AND revision = ? AND disable_latest = 0
      RETURNING revision
    `
  )
    .bind(
      target.id,
      input.rollback ? "rollback" : "publish",
      input.actor,
      input.actorType,
      input.requestId,
      beforeJson,
      afterJson,
      channel.id,
      input.expectedRevision
    )
    .first<{ revision: number }>();

  if (!updatedChannel) {
    return { ok: false, errorCode: "CAS_CONFLICT", status: 409 };
  }
  return { ok: true };
}

export async function editReleaseNotes(
  env: WorkerEnv,
  input: Actor & { releaseId: string; releaseNotes: string }
): Promise<ActionResult> {
  const release = await env.DB.prepare("SELECT * FROM releases WHERE id = ? LIMIT 1")
    .bind(input.releaseId)
    .first<ReleaseRow>();
  if (!release) throw new ApiError("RELEASE_NOT_FOUND", "Release not found", 404);

  const beforeJson = canonicalJson({ releaseNotes: release.release_notes });
  const afterJson = canonicalJson({ releaseNotes: input.releaseNotes });
  await env.DB.batch([
    env.DB.prepare(
      "UPDATE releases SET release_notes = ?, updated_at = datetime('now') WHERE id = ?"
    ).bind(input.releaseNotes, input.releaseId),
    env.DB.prepare(
      `
        INSERT INTO audit_logs (
          id,
          app_id,
          actor,
          actor_type,
          action,
          target_type,
          target_id,
          request_id,
          before_json,
          after_json
        )
        VALUES (?, ?, ?, ?, 'edit_notes', 'release', ?, ?, ?, ?)
      `
    ).bind(
      crypto.randomUUID(),
      release.app_id,
      input.actor,
      input.actorType,
      input.releaseId,
      input.requestId,
      beforeJson,
      afterJson
    ),
    env.DB.prepare(
      `
        UPDATE channels
        SET
          revision = revision + 1,
          last_action = 'edit_notes',
          last_actor = ?,
          last_actor_type = ?,
          last_request_id = ?,
          last_before_json = ?,
          last_after_json = ?,
          updated_at = datetime('now')
        WHERE current_release_id = ?
      `
    ).bind(
      input.actor,
      input.actorType,
      input.requestId,
      beforeJson,
      afterJson,
      input.releaseId
    )
  ]);

  return { ok: true };
}

export async function disableRelease(
  env: WorkerEnv,
  input: Actor & { releaseId: string }
): Promise<ActionResult> {
  const referenced = await env.DB.prepare(
    "SELECT id FROM channels WHERE current_release_id = ? LIMIT 1"
  )
    .bind(input.releaseId)
    .first<{ id: string }>();
  if (referenced) {
    return { ok: false, errorCode: "RELEASE_DISABLED", status: 409 };
  }

  const result = await env.DB.prepare(
    "UPDATE releases SET state = 'disabled', updated_at = datetime('now') WHERE id = ?"
  )
    .bind(input.releaseId)
    .run();
  if (result.meta.changes !== 1) {
    throw new ApiError("RELEASE_NOT_FOUND", "Release not found", 404);
  }
  await env.DB.prepare(
    `
      INSERT INTO audit_logs (
        id,
        actor,
        actor_type,
        action,
        target_type,
        target_id,
        request_id,
        before_json,
        after_json
      )
      VALUES (?, ?, ?, 'disable_release', 'release', ?, ?, '{}', '{"state":"disabled"}')
    `
  )
    .bind(crypto.randomUUID(), input.actor, input.actorType, input.releaseId, input.requestId)
    .run();
  return { ok: true };
}

async function ensureAndroidCompleteness(env: WorkerEnv, release: ReleaseRow): Promise<void> {
  if (release.platform !== "android") return;
  const apk = await env.DB.prepare(
    "SELECT id FROM release_assets WHERE release_id = ? AND platform = 'android' AND asset_type = 'apk' AND disabled = 0 LIMIT 1"
  )
    .bind(release.id)
    .first<{ id: string }>();
  if (!apk) {
    throw new ApiError("BACKEND_UNAVAILABLE", "Android release is missing an APK asset", 503);
  }
}

function channelSnapshot(
  channel: ChannelRow,
  currentReleaseId = channel.current_release_id
): Record<string, unknown> {
  return {
    id: channel.id,
    app_id: channel.app_id,
    platform: channel.platform,
    name: channel.name,
    current_release_id: currentReleaseId,
    revision: channel.revision,
    disable_latest: channel.disable_latest,
    disable_downloads: channel.disable_downloads,
    maintenance_admin_only: channel.maintenance_admin_only,
    maintenance_message: channel.maintenance_message
  };
}
