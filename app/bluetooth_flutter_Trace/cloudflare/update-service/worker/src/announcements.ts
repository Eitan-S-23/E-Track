import { ApiError, backendUnavailable, invalidParameter } from "./errors";
import { clientIpFrom, json } from "./http";
import { writeLog } from "./logger";
import { enforceRateLimit } from "./rate_limiter";
import { parseChannel, parsePlatform } from "./validation";
import type { ChannelName, Platform, WorkerEnv } from "./types";

const ANNOUNCEMENTS_QUERY_PARAMS = new Set(["appId", "platform", "channel", "limit"]);
const DEFAULT_LIMIT = 8;
const MAX_LIMIT = 20;

interface ManualAnnouncementRow {
  id: string;
  title: string;
  body: string;
  pinned: number;
  published_at: string | null;
  created_at: string;
  updated_at: string;
}

interface ReleaseAnnouncementRow {
  id: string;
  version_name: string;
  version_code: number;
  release_tag: string;
  release_notes: string;
  created_at: string;
  updated_at: string;
}

export async function handleAnnouncements(
  request: Request,
  env: WorkerEnv,
  requestId: string
): Promise<Response> {
  const url = new URL(request.url);
  for (const key of url.searchParams.keys()) {
    if (!ANNOUNCEMENTS_QUERY_PARAMS.has(key)) {
      throw invalidParameter(`Unsupported query parameter: ${key}`);
    }
  }

  const appId = url.searchParams.get("appId") ?? env.APP_ID;
  const platform = parsePlatform(url.searchParams.get("platform") ?? "android");
  const channel = parseChannel(url.searchParams.get("channel") ?? "stable");
  const limit = parseLimit(url.searchParams.get("limit"));

  const rate = await enforceRateLimit(
    env,
    `announcements:${clientIpFrom(request)}:${appId}:${platform}:${channel}`
  );
  if (!rate.allowed) {
    return json(
      { errorCode: "RATE_LIMITED", message: "Too many announcement requests", retryAfter: rate.retryAfter },
      429,
      { "Retry-After": String(rate.retryAfter) }
    );
  }

  try {
    const [manual, release] = await Promise.all([
      loadManualAnnouncements(env, appId, limit),
      loadReleaseAnnouncement(env, appId, platform, channel)
    ]);

    const announcements = [
      ...manual.results.map((row) => ({
        id: row.id,
        type: "manual",
        title: row.title,
        body: row.body,
        pinned: row.pinned === 1,
        publishedAt: row.published_at ?? row.updated_at ?? row.created_at,
        updatedAt: row.updated_at
      })),
      ...(release ? [releaseAnnouncement(release)] : [])
    ];

    return json({
      ok: true,
      appId,
      platform,
      channel,
      announcements
    });
  } catch (error) {
    if (error instanceof ApiError) throw error;
    const message = error instanceof Error ? error.message : String(error);
    writeLog("error", "announcements_failed", { requestId, message });
    throw backendUnavailable();
  }
}

function loadManualAnnouncements(
  env: WorkerEnv,
  appId: string,
  limit: number
): Promise<D1Result<ManualAnnouncementRow>> {
  return env.DB.prepare(
    `
      SELECT id, title, body, pinned, published_at, created_at, updated_at
      FROM announcements
      WHERE app_id = ? AND published = 1
      ORDER BY pinned DESC, COALESCE(published_at, updated_at, created_at) DESC, id DESC
      LIMIT ?
    `
  )
    .bind(appId, limit)
    .all<ManualAnnouncementRow>();
}

async function loadReleaseAnnouncement(
  env: WorkerEnv,
  appId: string,
  platform: Platform,
  channel: ChannelName
): Promise<ReleaseAnnouncementRow | null> {
  return (
    (await env.DB.prepare(
      `
        SELECT r.id, r.version_name, r.version_code, r.release_tag, r.release_notes, r.created_at, r.updated_at
        FROM channels c
        JOIN releases r ON r.id = c.current_release_id
        WHERE c.app_id = ?
          AND c.platform = ?
          AND c.name = ?
          AND c.disable_latest = 0
          AND r.state <> 'disabled'
          AND r.archived = 0
        LIMIT 1
      `
    )
      .bind(appId, platform, channel)
      .first<ReleaseAnnouncementRow>()) ?? null
  );
}

function releaseAnnouncement(row: ReleaseAnnouncementRow): Record<string, unknown> {
  const notes = row.release_notes.trim();
  return {
    id: `release:${row.id}`,
    type: "release",
    title: `Trace ${row.version_name} 更新公告`,
    body: notes || `Trace ${row.version_name} 已发布，暂无发布说明。`,
    versionName: row.version_name,
    versionCode: row.version_code,
    releaseTag: row.release_tag,
    publishedAt: row.updated_at ?? row.created_at,
    updatedAt: row.updated_at
  };
}

function parseLimit(value: string | null): number {
  if (!value) return DEFAULT_LIMIT;
  const parsed = Number(value);
  if (!Number.isInteger(parsed) || parsed < 1 || parsed > MAX_LIMIT) {
    throw invalidParameter(`limit must be an integer from 1 to ${MAX_LIMIT}`);
  }
  return parsed;
}
