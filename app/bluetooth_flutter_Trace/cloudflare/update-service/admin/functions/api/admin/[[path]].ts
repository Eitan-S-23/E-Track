type Platform = "android" | "windows";
type ChannelName = "stable" | "beta";
type ActorRole = "viewer" | "publisher" | "owner";

interface AdminEnv {
  DB: D1Database;
  RELEASES_BUCKET: R2Bucket;
  ENVIRONMENT: string;
  APP_ID: string;
  ACCESS_JWT_ISSUER?: string;
  ACCESS_JWT_AUD?: string;
  ADMIN_VIEWER_EMAILS?: string;
  ADMIN_PUBLISHER_EMAILS?: string;
  ADMIN_OWNER_EMAILS?: string;
  ADMIN_ALLOWED_ORIGINS?: string;
}

interface Actor {
  email: string;
  role: ActorRole;
  requestId: string;
}

interface ChannelRow {
  id: string;
  app_id: string;
  platform: Platform;
  name: ChannelName;
  current_release_id: string | null;
  revision: number;
  disable_latest: number;
  disable_downloads: number;
  maintenance_admin_only: number;
  maintenance_message: string | null;
}

interface ReleaseRow {
  id: string;
  app_id: string;
  platform: Platform;
  version_name: string;
  version_code: number;
  release_tag: string;
  state: "candidate" | "disabled";
  release_notes: string;
  archived: number;
  fallback_only: number;
}

interface ReleaseAssetRow {
  id: string;
  asset_type: "apk" | "windows_zip" | "windows_exe" | "manifest" | "patch";
  file_name: string;
  size_bytes: number;
  r2_key: string | null;
  r2_state: "not_uploaded" | "available" | "r2_deleted" | "archived";
}

interface FirmwareReleaseRow {
  id: string;
  app_id: string;
  device_model: string;
  version_name: string;
  version_code: number;
  release_tag: string;
  state: "candidate" | "disabled";
  release_notes: string;
  file_name: string;
  sha256: string;
  size_bytes: number;
  r2_key: string | null;
  r2_state: "not_uploaded" | "available" | "r2_deleted" | "archived";
  github_url: string;
  target_hardware: string | null;
  transport: string;
  archived: number;
}

interface FirmwareChannelRow {
  id: string;
  app_id: string;
  device_model: string;
  name: ChannelName;
  current_release_id: string | null;
  revision: number;
  disable_latest: number;
  disable_downloads: number;
  maintenance_message: string | null;
}

interface AnnouncementRow {
  id: string;
  app_id: string;
  title: string;
  body: string;
  pinned: number;
  published: number;
  published_at: string | null;
  created_at: string;
  updated_at: string;
}

interface StorageTypeSummary {
  type: string;
  objectCount: number;
  totalSizeBytes: number;
}

interface DeleteR2Result {
  objectCount: number;
  totalSizeBytes: number;
}

interface AccessJwk {
  kid: string;
  kty: string;
  alg?: string;
  use?: string;
  n?: string;
  e?: string;
}

interface AccessJwks {
  keys: AccessJwk[];
}

class AdminError extends Error {
  constructor(
    public readonly code: string,
    message: string,
    public readonly status: number
  ) {
    super(message);
    this.name = "AdminError";
  }
}

let cachedJwks: { issuer: string; expiresAt: number; jwks: AccessJwks } | null = null;

export const onRequest: PagesFunction<AdminEnv> = async (context) => {
  const requestId = requestIdFrom(context.request);
  try {
    const actor = await requireAccessActor(context.request, context.env, requestId);
    const response = await routeAdminRequest(context, actor);
    response.headers.set("X-Request-Id", requestId);
    return response;
  } catch (error) {
    const response = errorJson(error, requestId);
    response.headers.set("X-Request-Id", requestId);
    return response;
  }
};

async function routeAdminRequest(
  context: EventContext<AdminEnv, string, unknown>,
  actor: Actor
): Promise<Response> {
  const url = new URL(context.request.url);
  const method = context.request.method.toUpperCase();
  const route = routeSegments(context.params.path);

  if (method === "OPTIONS") {
    return new Response(null, { status: 204 });
  }

  if (method !== "GET") {
    requireSameOriginMutation(context.request, context.env);
    requireCsrf(context.request);
  }

  if (method === "GET" && route.length === 1 && route[0] === "session") {
    const csrfToken = crypto.randomUUID();
    return json(
      {
        ok: true,
        environment: context.env.ENVIRONMENT,
        appId: context.env.APP_ID,
        actor: actor.email,
        role: actor.role,
        csrfToken
      },
      200,
      {
        "Set-Cookie": csrfCookie(csrfToken)
      }
    );
  }

  if (method === "GET" && route.length === 1 && route[0] === "channels") {
    requireRole(actor, "viewer");
    return listChannels(context.env, url);
  }

  if (method === "GET" && route.length === 1 && route[0] === "releases") {
    requireRole(actor, "viewer");
    return listReleases(context.env, url);
  }

  if (method === "GET" && route.length === 1 && route[0] === "storage") {
    requireRole(actor, "viewer");
    return storageSummary(context.env, url);
  }

  if (method === "GET" && route.length === 1 && route[0] === "announcements") {
    requireRole(actor, "viewer");
    return listAnnouncements(context.env, url);
  }

  if (method === "POST" && route.length === 1 && route[0] === "announcements") {
    requireRole(actor, "publisher");
    const body = await requestJson(context.request);
    return saveAnnouncement(context.env, actor, null, body);
  }

  if (method === "POST" && route.length === 2 && route[0] === "announcements") {
    requireRole(actor, "publisher");
    const body = await requestJson(context.request);
    return saveAnnouncement(context.env, actor, route[1], body);
  }

  if (
    method === "POST" &&
    route.length === 3 &&
    route[0] === "announcements" &&
    route[2] === "delete"
  ) {
    requireRole(actor, "publisher");
    return deleteAnnouncement(context.env, actor, route[1]);
  }

  if (method === "GET" && route.length === 2 && route[0] === "firmware" && route[1] === "releases") {
    requireRole(actor, "viewer");
    return listFirmwareReleases(context.env, url);
  }

  if (method === "GET" && route.length === 2 && route[0] === "firmware" && route[1] === "channels") {
    requireRole(actor, "viewer");
    return listFirmwareChannels(context.env, url);
  }

  if (
    method === "POST" &&
    route.length === 3 &&
    route[0] === "channels" &&
    route[2] === "publish"
  ) {
    const channel = parseChannel(route[1]);
    requireRole(actor, channel === "stable" ? "owner" : "publisher");
    const body = await requestJson(context.request);
    return publishRelease(context.env, actor, channel, body);
  }

  if (
    method === "POST" &&
    route.length === 3 &&
    route[0] === "releases" &&
    route[2] === "notes"
  ) {
    requireRole(actor, "publisher");
    const body = await requestJson(context.request);
    return editReleaseNotes(context.env, actor, route[1], body);
  }

  if (
    method === "POST" &&
    route.length === 3 &&
    route[0] === "releases" &&
    route[2] === "disable"
  ) {
    requireRole(actor, "owner");
    return disableRelease(context.env, actor, route[1]);
  }

  if (
    method === "POST" &&
    route.length === 3 &&
    route[0] === "releases" &&
    route[2] === "delete"
  ) {
    requireRole(actor, "owner");
    return deleteRelease(context.env, actor, route[1]);
  }

  if (
    method === "POST" &&
    route.length === 4 &&
    route[0] === "firmware" &&
    route[1] === "channels" &&
    route[3] === "publish"
  ) {
    const channel = parseChannel(route[2]);
    requireRole(actor, channel === "stable" ? "owner" : "publisher");
    const body = await requestJson(context.request);
    return publishFirmwareRelease(context.env, actor, channel, body);
  }

  if (
    method === "POST" &&
    route.length === 4 &&
    route[0] === "firmware" &&
    route[1] === "releases" &&
    route[3] === "disable"
  ) {
    requireRole(actor, "owner");
    return disableFirmwareRelease(context.env, actor, route[2]);
  }

  throw new AdminError("NOT_FOUND", "Admin route not found", 404);
}

async function listChannels(env: AdminEnv, url: URL): Promise<Response> {
  const appId = queryString(url, "appId") ?? env.APP_ID;
  const platform = parsePlatform(queryString(url, "platform") ?? "android");
  const result = await env.DB.prepare(
    `
      SELECT
        c.*,
        r.release_tag,
        r.version_name,
        r.version_code,
        r.state AS release_state
      FROM channels c
      LEFT JOIN releases r ON r.id = c.current_release_id
      WHERE c.app_id = ? AND c.platform = ?
      ORDER BY c.name
    `
  )
    .bind(appId, platform)
    .all();
  return json({ ok: true, channels: result.results });
}

async function listReleases(env: AdminEnv, url: URL): Promise<Response> {
  const appId = queryString(url, "appId") ?? env.APP_ID;
  const platform = parsePlatform(queryString(url, "platform") ?? "android");
  const result = await env.DB.prepare(
    `
      SELECT
        r.*,
        group_concat(c.name) AS published_channels,
        (
          SELECT count(*)
          FROM release_assets a
          WHERE a.release_id = r.id AND a.disabled = 0
        ) AS asset_count,
        (
          SELECT count(*)
          FROM release_assets a
          WHERE a.release_id = r.id AND a.disabled = 0 AND a.r2_state = 'available'
        ) AS r2_available_count,
        (
          SELECT COALESCE(max(a.size_bytes), 0)
          FROM release_assets a
          WHERE a.release_id = r.id
            AND a.disabled = 0
            AND a.platform = r.platform
            AND a.asset_type IN ('apk', 'windows_zip', 'windows_exe')
        ) AS installer_size_bytes,
        (
          SELECT count(*)
          FROM release_assets a
          WHERE a.release_id = r.id AND a.disabled = 0 AND a.r2_state <> 'available'
        ) AS github_fallback_only_count,
        (
          SELECT count(*)
          FROM patches p
          WHERE p.to_release_id = r.id AND p.disabled = 0
        ) AS patch_count
      FROM releases r
      LEFT JOIN channels c ON c.current_release_id = r.id
      WHERE r.app_id = ? AND r.platform = ?
        AND r.archived = 0
        AND EXISTS (
          SELECT 1
          FROM release_assets a
          WHERE a.release_id = r.id
            AND a.disabled = 0
            AND a.r2_state = 'available'
        )
        AND NOT EXISTS (
          SELECT 1
          FROM release_assets a
          WHERE a.release_id = r.id
            AND a.disabled = 0
            AND a.r2_state <> 'available'
        )
      GROUP BY r.id
      ORDER BY r.version_code DESC, r.created_at DESC
      LIMIT 50
    `
  )
    .bind(appId, platform)
    .all();
  return json({ ok: true, releases: result.results });
}

async function storageSummary(env: AdminEnv, url: URL): Promise<Response> {
  const appId = queryString(url, "appId") ?? env.APP_ID;
  const platform = parsePlatform(queryString(url, "platform") ?? "android");
  const prefix = `${appId}/`;
  const [r2, trackedRows, trackedTotal, fullyR2Releases] = await Promise.all([
    listR2Usage(env, prefix),
    env.DB.prepare(
      `
        SELECT type, count(*) AS objectCount, COALESCE(sum(size_bytes), 0) AS totalSizeBytes
        FROM (
          SELECT asset_type AS type, size_bytes
          FROM release_assets
          WHERE app_id = ?
            AND platform = ?
            AND disabled = 0
            AND r2_state = 'available'
          UNION ALL
          SELECT 'firmware' AS type, size_bytes
          FROM firmware_releases
          WHERE app_id = ?
            AND archived = 0
            AND state <> 'disabled'
            AND r2_state = 'available'
        )
        GROUP BY type
        ORDER BY type
      `
    )
      .bind(appId, platform, appId)
      .all<StorageTypeSummary>(),
    env.DB.prepare(
      `
        SELECT
          count(*) AS objectCount,
          COALESCE(sum(size_bytes), 0) AS totalSizeBytes
        FROM (
          SELECT size_bytes
          FROM release_assets
          WHERE app_id = ?
            AND platform = ?
            AND disabled = 0
            AND r2_state = 'available'
          UNION ALL
          SELECT size_bytes
          FROM firmware_releases
          WHERE app_id = ?
            AND archived = 0
            AND state <> 'disabled'
            AND r2_state = 'available'
        )
      `
    )
      .bind(appId, platform, appId)
      .first<{ objectCount: number; totalSizeBytes: number }>(),
    env.DB.prepare(
      `
        SELECT count(*) AS releaseCount
        FROM releases r
        WHERE r.app_id = ?
          AND r.platform = ?
          AND r.archived = 0
          AND EXISTS (
            SELECT 1
            FROM release_assets a
            WHERE a.release_id = r.id
              AND a.disabled = 0
              AND a.r2_state = 'available'
          )
          AND NOT EXISTS (
            SELECT 1
            FROM release_assets a
            WHERE a.release_id = r.id
              AND a.disabled = 0
              AND a.r2_state <> 'available'
          )
      `
    )
      .bind(appId, platform)
      .first<{ releaseCount: number }>()
  ]);

  return json({
    ok: true,
    storage: {
      prefix,
      r2,
      tracked: {
        objectCount: trackedTotal?.objectCount ?? 0,
        totalSizeBytes: trackedTotal?.totalSizeBytes ?? 0,
        releaseCount: fullyR2Releases?.releaseCount ?? 0,
        byType: trackedRows.results
      }
    }
  });
}

async function listAnnouncements(env: AdminEnv, url: URL): Promise<Response> {
  const appId = queryString(url, "appId") ?? env.APP_ID;
  const result = await env.DB.prepare(
    `
      SELECT id, app_id, title, body, pinned, published, published_at, created_at, updated_at
      FROM announcements
      WHERE app_id = ?
      ORDER BY pinned DESC, COALESCE(published_at, updated_at, created_at) DESC, created_at DESC
      LIMIT 50
    `
  )
    .bind(appId)
    .all<AnnouncementRow>();
  return json({ ok: true, announcements: result.results });
}

async function saveAnnouncement(
  env: AdminEnv,
  actor: Actor,
  announcementId: string | null,
  body: Record<string, unknown>
): Promise<Response> {
  const appId = requireString(body.appId ?? env.APP_ID, "appId");
  const title = boundedString(body.title, "title", 120);
  const content = boundedString(body.body, "body", 8000);
  const pinned = boolFlag(body.pinned);
  const published = boolFlag(body.published);
  const existing = announcementId
    ? await env.DB.prepare("SELECT * FROM announcements WHERE id = ? AND app_id = ? LIMIT 1")
        .bind(announcementId, appId)
        .first<AnnouncementRow>()
    : null;

  if (announcementId && !existing) {
    throw new AdminError("NOT_FOUND", "Announcement not found", 404);
  }

  const id = announcementId ?? `ann_${crypto.randomUUID().replaceAll("-", "")}`;
  await env.DB.batch([
    env.DB.prepare("INSERT OR IGNORE INTO apps (id, name) VALUES (?, ?)").bind(appId, appId),
    existing
      ? env.DB.prepare(
          `
            UPDATE announcements
            SET
              title = ?,
              body = ?,
              pinned = ?,
              published = ?,
              published_at = CASE
                WHEN ? = 1 AND published_at IS NULL THEN datetime('now')
                ELSE published_at
              END,
              updated_at = datetime('now')
            WHERE id = ?
          `
        ).bind(title, content, pinned, published, published, id)
      : env.DB.prepare(
          `
            INSERT INTO announcements (
              id,
              app_id,
              title,
              body,
              pinned,
              published,
              published_at
            )
            VALUES (?, ?, ?, ?, ?, ?, CASE WHEN ? = 1 THEN datetime('now') ELSE NULL END)
          `
        ).bind(id, appId, title, content, pinned, published, published),
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
        VALUES (?, ?, ?, 'access', ?, 'announcement', ?, ?, ?, ?)
      `
    ).bind(
      crypto.randomUUID(),
      appId,
      actor.email,
      existing ? "edit_announcement" : "create_announcement",
      id,
      actor.requestId,
      existing ? canonicalJson(announcementSnapshot(existing)) : null,
      canonicalJson({ title, body: content, pinned: pinned === 1, published: published === 1 })
    )
  ]);

  return json({ ok: true, announcementId: id });
}

async function deleteAnnouncement(env: AdminEnv, actor: Actor, announcementId: string): Promise<Response> {
  const announcement = await env.DB.prepare("SELECT * FROM announcements WHERE id = ? LIMIT 1")
    .bind(announcementId)
    .first<AnnouncementRow>();
  if (!announcement) {
    throw new AdminError("NOT_FOUND", "Announcement not found", 404);
  }

  await env.DB.batch([
    env.DB.prepare("DELETE FROM announcements WHERE id = ?").bind(announcementId),
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
        VALUES (?, ?, ?, 'access', 'delete_announcement', 'announcement', ?, ?, ?, '{"deleted":true}')
      `
    ).bind(
      crypto.randomUUID(),
      announcement.app_id,
      actor.email,
      announcementId,
      actor.requestId,
      canonicalJson(announcementSnapshot(announcement))
    )
  ]);

  return json({ ok: true });
}

async function listFirmwareReleases(env: AdminEnv, url: URL): Promise<Response> {
  const appId = queryString(url, "appId") ?? env.APP_ID;
  const deviceModel = optionalDeviceModel(queryString(url, "deviceModel"));
  const baseSql = `
      SELECT
        f.*,
        group_concat(c.name) AS published_channels
      FROM firmware_releases f
      LEFT JOIN firmware_channels c ON c.current_release_id = f.id
      WHERE f.app_id = ?
        AND f.archived = 0
        AND f.r2_state = 'available'
        ${deviceModel ? "AND f.device_model = ?" : ""}
      GROUP BY f.id
      ORDER BY f.device_model ASC, f.version_code DESC, f.created_at DESC
      LIMIT 100
    `;
  const statement = env.DB.prepare(baseSql);
  const result = deviceModel
    ? await statement.bind(appId, deviceModel).all()
    : await statement.bind(appId).all();
  return json({ ok: true, firmwareReleases: result.results });
}

async function listFirmwareChannels(env: AdminEnv, url: URL): Promise<Response> {
  const appId = queryString(url, "appId") ?? env.APP_ID;
  const deviceModel = optionalDeviceModel(queryString(url, "deviceModel"));
  const baseSql = `
      SELECT
        c.*,
        f.release_tag,
        f.version_name,
        f.version_code,
        f.state AS release_state
      FROM firmware_channels c
      LEFT JOIN firmware_releases f ON f.id = c.current_release_id
      WHERE c.app_id = ?
        ${deviceModel ? "AND c.device_model = ?" : ""}
      ORDER BY c.device_model ASC, c.name ASC
    `;
  const statement = env.DB.prepare(baseSql);
  const result = deviceModel
    ? await statement.bind(appId, deviceModel).all()
    : await statement.bind(appId).all();
  return json({ ok: true, firmwareChannels: result.results });
}

async function publishRelease(
  env: AdminEnv,
  actor: Actor,
  channelName: ChannelName,
  body: Record<string, unknown>
): Promise<Response> {
  const appId = requireString(body.appId ?? env.APP_ID, "appId");
  const platform = parsePlatform(body.platform ?? "android");
  const releaseId = requireString(body.releaseId, "releaseId");
  const expectedRevision = requireInt(body.expectedRevision, "expectedRevision");
  const rollback = body.rollback === true;

  const channel = await env.DB.prepare(
    "SELECT * FROM channels WHERE app_id = ? AND platform = ? AND name = ? LIMIT 1"
  )
    .bind(appId, platform, channelName)
    .first<ChannelRow>();
  if (!channel) throw new AdminError("RELEASE_NOT_FOUND", "Channel not found", 404);

  const target = await env.DB.prepare("SELECT * FROM releases WHERE id = ? LIMIT 1")
    .bind(releaseId)
    .first<ReleaseRow>();
  if (!target || target.app_id !== appId || target.platform !== platform) {
    throw new AdminError("RELEASE_NOT_FOUND", "Release not found", 404);
  }
  if (target.state === "disabled") {
    throw new AdminError("RELEASE_DISABLED", "Disabled release cannot be published", 410);
  }
  if (target.archived === 1) {
    throw new AdminError("ASSET_ARCHIVED", "Archived release cannot be published", 409);
  }
  if (target.release_notes.trim() === "") {
    throw new AdminError("RELEASE_NOTES_REQUIRED", "Release notes are required before publish", 409);
  }

  if (channel.current_release_id && !rollback) {
    const current = await env.DB.prepare("SELECT version_code FROM releases WHERE id = ? LIMIT 1")
      .bind(channel.current_release_id)
      .first<{ version_code: number }>();
    if (current && target.version_code <= current.version_code) {
      throw new AdminError(
        "VERSION_REGRESSION",
        "Publishing a non-rollback versionCode regression is blocked",
        409
      );
    }
  }

  if (platform === "android") {
    await ensureAndroidCompleteness(env, releaseId);
  }

  const beforeJson = canonicalJson(channelSnapshot(channel));
  const afterJson = canonicalJson(channelSnapshot(channel, releaseId));
  const updatedChannel = await env.DB.prepare(
    `
      UPDATE channels
      SET
        current_release_id = ?,
        revision = revision + 1,
        last_action = ?,
        last_actor = ?,
        last_actor_type = 'access',
        last_request_id = ?,
        last_before_json = ?,
        last_after_json = ?,
        updated_at = datetime('now')
      WHERE id = ? AND revision = ? AND disable_latest = 0
      RETURNING revision
    `
  )
    .bind(
      releaseId,
      rollback ? "rollback" : "publish",
      actor.email,
      actor.requestId,
      beforeJson,
      afterJson,
      channel.id,
      expectedRevision
    )
    .first<{ revision: number }>();

  if (!updatedChannel) {
    throw new AdminError("CAS_CONFLICT", "Channel revision changed or latest is disabled", 409);
  }
  return json({ ok: true, revision: updatedChannel.revision });
}

async function publishFirmwareRelease(
  env: AdminEnv,
  actor: Actor,
  channelName: ChannelName,
  body: Record<string, unknown>
): Promise<Response> {
  const appId = requireString(body.appId ?? env.APP_ID, "appId");
  const deviceModel = parseDeviceModel(body.deviceModel);
  const releaseId = requireString(body.releaseId, "releaseId");
  const expectedRevision = requireInt(body.expectedRevision, "expectedRevision");
  const rollback = body.rollback === true;

  const channel = await env.DB.prepare(
    "SELECT * FROM firmware_channels WHERE app_id = ? AND device_model = ? AND name = ? LIMIT 1"
  )
    .bind(appId, deviceModel, channelName)
    .first<FirmwareChannelRow>();
  if (!channel) throw new AdminError("RELEASE_NOT_FOUND", "Firmware channel not found", 404);

  const target = await env.DB.prepare("SELECT * FROM firmware_releases WHERE id = ? LIMIT 1")
    .bind(releaseId)
    .first<FirmwareReleaseRow>();
  if (!target || target.app_id !== appId || target.device_model !== deviceModel) {
    throw new AdminError("RELEASE_NOT_FOUND", "Firmware release not found", 404);
  }
  if (target.state === "disabled") {
    throw new AdminError("RELEASE_DISABLED", "Disabled firmware release cannot be published", 410);
  }
  if (target.archived === 1 || target.r2_state !== "available" || !target.r2_key) {
    throw new AdminError("ASSET_ARCHIVED", "Firmware R2 asset is not available", 409);
  }

  if (channel.current_release_id && !rollback) {
    const current = await env.DB.prepare("SELECT version_code FROM firmware_releases WHERE id = ? LIMIT 1")
      .bind(channel.current_release_id)
      .first<{ version_code: number }>();
    if (current && target.version_code <= current.version_code) {
      throw new AdminError(
        "VERSION_REGRESSION",
        "Publishing a non-rollback firmware versionCode regression is blocked",
        409
      );
    }
  }

  const beforeJson = canonicalJson(firmwareChannelSnapshot(channel));
  const afterJson = canonicalJson(firmwareChannelSnapshot(channel, releaseId));
  const updatedChannel = await env.DB.prepare(
    `
      UPDATE firmware_channels
      SET
        current_release_id = ?,
        revision = revision + 1,
        last_action = ?,
        last_actor = ?,
        last_actor_type = 'access',
        last_request_id = ?,
        last_before_json = ?,
        last_after_json = ?,
        updated_at = datetime('now')
      WHERE id = ? AND revision = ? AND disable_latest = 0
      RETURNING revision
    `
  )
    .bind(
      releaseId,
      rollback ? "rollback" : "publish",
      actor.email,
      actor.requestId,
      beforeJson,
      afterJson,
      channel.id,
      expectedRevision
    )
    .first<{ revision: number }>();

  if (!updatedChannel) {
    throw new AdminError("CAS_CONFLICT", "Firmware channel revision changed or latest is disabled", 409);
  }

  await env.DB.prepare(
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
      VALUES (?, ?, ?, 'access', 'publish_firmware', 'firmware_channel', ?, ?, ?, ?)
    `
  )
    .bind(
      crypto.randomUUID(),
      appId,
      actor.email,
      channel.id,
      actor.requestId,
      beforeJson,
      afterJson
    )
    .run();

  return json({ ok: true, revision: updatedChannel.revision });
}

async function editReleaseNotes(
  env: AdminEnv,
  actor: Actor,
  releaseId: string,
  body: Record<string, unknown>
): Promise<Response> {
  const releaseNotes = requireString(body.releaseNotes, "releaseNotes");
  if (releaseNotes.length > 8000) {
    throw new AdminError("INVALID_PARAMETER", "releaseNotes is too long", 400);
  }

  const release = await env.DB.prepare("SELECT * FROM releases WHERE id = ? LIMIT 1")
    .bind(releaseId)
    .first<ReleaseRow>();
  if (!release) throw new AdminError("RELEASE_NOT_FOUND", "Release not found", 404);

  const beforeJson = canonicalJson({ releaseNotes: release.release_notes });
  const afterJson = canonicalJson({ releaseNotes });
  await env.DB.batch([
    env.DB.prepare("UPDATE releases SET release_notes = ?, updated_at = datetime('now') WHERE id = ?")
      .bind(releaseNotes, releaseId),
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
        VALUES (?, ?, ?, 'access', 'edit_notes', 'release', ?, ?, ?, ?)
      `
    ).bind(
      crypto.randomUUID(),
      release.app_id,
      actor.email,
      releaseId,
      actor.requestId,
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
          last_actor_type = 'access',
          last_request_id = ?,
          last_before_json = ?,
          last_after_json = ?,
          updated_at = datetime('now')
        WHERE current_release_id = ?
      `
    ).bind(actor.email, actor.requestId, beforeJson, afterJson, releaseId)
  ]);

  return json({ ok: true });
}

async function disableFirmwareRelease(
  env: AdminEnv,
  actor: Actor,
  releaseId: string
): Promise<Response> {
  const referenced = await env.DB.prepare(
    "SELECT id FROM firmware_channels WHERE current_release_id = ? LIMIT 1"
  )
    .bind(releaseId)
    .first<{ id: string }>();
  if (referenced) {
    throw new AdminError(
      "RELEASE_DISABLED",
      "Published firmware cannot be disabled before moving the channel",
      409
    );
  }

  const release = await env.DB.prepare("SELECT app_id, state FROM firmware_releases WHERE id = ? LIMIT 1")
    .bind(releaseId)
    .first<{ app_id: string; state: string }>();
  if (!release) throw new AdminError("RELEASE_NOT_FOUND", "Firmware release not found", 404);

  const result = await env.DB.prepare(
    "UPDATE firmware_releases SET state = 'disabled', updated_at = datetime('now') WHERE id = ?"
  )
    .bind(releaseId)
    .run();
  if (result.meta.changes !== 1) {
    throw new AdminError("RELEASE_NOT_FOUND", "Firmware release not found", 404);
  }

  await env.DB.prepare(
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
      VALUES (?, ?, ?, 'access', 'disable_firmware', 'firmware_release', ?, ?, ?, '{"state":"disabled"}')
    `
  )
    .bind(
      crypto.randomUUID(),
      release.app_id,
      actor.email,
      releaseId,
      actor.requestId,
      canonicalJson({ state: release.state })
    )
    .run();

  return json({ ok: true });
}

async function disableRelease(env: AdminEnv, actor: Actor, releaseId: string): Promise<Response> {
  const referenced = await env.DB.prepare(
    "SELECT id FROM channels WHERE current_release_id = ? LIMIT 1"
  )
    .bind(releaseId)
    .first<{ id: string }>();
  if (referenced) {
    throw new AdminError(
      "RELEASE_DISABLED",
      "Published release cannot be disabled before moving the channel",
      409
    );
  }

  const release = await env.DB.prepare("SELECT app_id, state FROM releases WHERE id = ? LIMIT 1")
    .bind(releaseId)
    .first<{ app_id: string; state: string }>();
  if (!release) throw new AdminError("RELEASE_NOT_FOUND", "Release not found", 404);

  const result = await env.DB.prepare(
    "UPDATE releases SET state = 'disabled', updated_at = datetime('now') WHERE id = ?"
  )
    .bind(releaseId)
    .run();
  if (result.meta.changes !== 1) {
    throw new AdminError("RELEASE_NOT_FOUND", "Release not found", 404);
  }

  await env.DB.prepare(
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
      VALUES (?, ?, ?, 'access', 'disable_release', 'release', ?, ?, ?, '{"state":"disabled"}')
    `
  )
    .bind(
      crypto.randomUUID(),
      release.app_id,
      actor.email,
      releaseId,
      actor.requestId,
      canonicalJson({ state: release.state })
    )
    .run();

  return json({ ok: true });
}

async function deleteRelease(env: AdminEnv, actor: Actor, releaseId: string): Promise<Response> {
  const referenced = await env.DB.prepare(
    "SELECT name FROM channels WHERE current_release_id = ? LIMIT 1"
  )
    .bind(releaseId)
    .first<{ name: string }>();
  if (referenced) {
    throw new AdminError(
      "RELEASE_IN_USE",
      "Published release cannot be deleted before moving the channel",
      409
    );
  }

  const release = await env.DB.prepare("SELECT * FROM releases WHERE id = ? LIMIT 1")
    .bind(releaseId)
    .first<ReleaseRow>();
  if (!release) throw new AdminError("RELEASE_NOT_FOUND", "Release not found", 404);

  const assets = await env.DB.prepare(
    "SELECT id, asset_type, file_name, size_bytes, r2_key, r2_state FROM release_assets WHERE release_id = ?"
  )
    .bind(releaseId)
    .all<ReleaseAssetRow>();
  const [patchRows, historyRows] = await Promise.all([
    env.DB.prepare("SELECT count(*) AS count FROM patches WHERE to_release_id = ?")
      .bind(releaseId)
      .first<{ count: number }>(),
    env.DB.prepare("SELECT count(*) AS count FROM channel_history WHERE release_id = ?")
      .bind(releaseId)
      .first<{ count: number }>()
  ]);
  const deletedR2 = await deleteR2ObjectsForRelease(env, release, assets.results);
  const assetRowCount = assets.results.length;
  const patchRowCount = patchRows?.count ?? 0;
  const historyRowCount = historyRows?.count ?? 0;
  const hardDeleteRelease = historyRowCount === 0;

  const beforeJson = canonicalJson({
    release,
    assets: assets.results.map((asset) => ({
      assetType: asset.asset_type,
      fileName: asset.file_name,
      sizeBytes: asset.size_bytes,
      r2Key: asset.r2_key,
      r2State: asset.r2_state
    }))
  });

  const statements = [
    env.DB.prepare("DELETE FROM patches WHERE to_release_id = ?").bind(releaseId),
    env.DB.prepare("DELETE FROM release_assets WHERE release_id = ?").bind(releaseId),
    hardDeleteRelease
      ? env.DB.prepare("DELETE FROM releases WHERE id = ?").bind(releaseId)
      : env.DB.prepare(
          `
            UPDATE releases
            SET
              archived = 1,
              state = 'disabled',
              payload_signature_json = NULL,
              security_payload_json = '{}',
              release_notes = '',
              capabilities_json = '[]',
              fallback_only = 0,
              updated_at = datetime('now')
            WHERE id = ?
          `
        ).bind(releaseId),
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
        VALUES (?, ?, ?, 'access', 'delete_release', 'release', ?, ?, ?, ?)
      `
    ).bind(
      crypto.randomUUID(),
      release.app_id,
      actor.email,
      releaseId,
      actor.requestId,
      beforeJson,
      canonicalJson({
        deleted: true,
        hardDeletedRelease: hardDeleteRelease,
        retainedReleaseTombstone: !hardDeleteRelease,
        retainedD1HistoryRows: historyRowCount,
        deletedR2Objects: deletedR2.objectCount,
        deletedR2Bytes: deletedR2.totalSizeBytes,
        deletedD1Rows: patchRowCount + assetRowCount + (hardDeleteRelease ? 1 : 0)
      })
    )
  ];

  await env.DB.batch(statements);

  return json({
    ok: true,
    hardDeletedRelease: hardDeleteRelease,
    retainedReleaseTombstone: !hardDeleteRelease,
    retainedD1HistoryRows: historyRowCount,
    deletedR2Objects: deletedR2.objectCount,
    deletedR2Bytes: deletedR2.totalSizeBytes,
    deletedD1Rows: patchRowCount + assetRowCount + (hardDeleteRelease ? 1 : 0)
  });
}

async function ensureAndroidCompleteness(env: AdminEnv, releaseId: string): Promise<void> {
  const apk = await env.DB.prepare(
    "SELECT id FROM release_assets WHERE release_id = ? AND platform = 'android' AND asset_type = 'apk' AND disabled = 0 LIMIT 1"
  )
    .bind(releaseId)
    .first<{ id: string }>();
  if (!apk) {
    throw new AdminError("BACKEND_UNAVAILABLE", "Android release is missing an APK asset", 503);
  }
}

async function requireAccessActor(
  request: Request,
  env: AdminEnv,
  requestId: string
): Promise<Actor> {
  if (!env.ACCESS_JWT_ISSUER || !env.ACCESS_JWT_AUD) {
    throw new AdminError("BACKEND_UNAVAILABLE", "Cloudflare Access is not configured", 503);
  }

  const token = request.headers.get("CF-Access-Jwt-Assertion") ?? bearerToken(request);
  if (!token) {
    throw new AdminError("TOKEN_INVALID", "Cloudflare Access JWT is required", 401);
  }

  const { header, payload, signedData, signature } = parseJwt(token);
  if (header.alg !== "RS256" || typeof header.kid !== "string") {
    throw new AdminError("TOKEN_INVALID", "Cloudflare Access JWT algorithm is invalid", 401);
  }

  const nowSeconds = Math.floor(Date.now() / 1000);
  if (typeof payload.exp !== "number" || payload.exp <= nowSeconds) {
    throw new AdminError("TOKEN_EXPIRED", "Cloudflare Access JWT expired", 401);
  }
  if (typeof payload.nbf === "number" && payload.nbf > nowSeconds) {
    throw new AdminError("TOKEN_INVALID", "Cloudflare Access JWT is not valid yet", 401);
  }
  if (payload.iss !== env.ACCESS_JWT_ISSUER) {
    throw new AdminError("TOKEN_INVALID", "Cloudflare Access JWT issuer is invalid", 401);
  }
  if (!audienceMatches(payload.aud, env.ACCESS_JWT_AUD)) {
    throw new AdminError("TOKEN_INVALID", "Cloudflare Access JWT audience is invalid", 401);
  }

  const jwk = await jwkForKid(env.ACCESS_JWT_ISSUER, header.kid);
  const key = await crypto.subtle.importKey(
    "jwk",
    jwk,
    { name: "RSASSA-PKCS1-v1_5", hash: "SHA-256" },
    false,
    ["verify"]
  );
  const valid = await crypto.subtle.verify(
    "RSASSA-PKCS1-v1_5",
    key,
    arrayBufferFromBytes(signature),
    new TextEncoder().encode(signedData)
  );
  if (!valid) {
    throw new AdminError("TOKEN_INVALID", "Cloudflare Access JWT signature is invalid", 401);
  }

  const email = typeof payload.email === "string" ? payload.email.toLowerCase() : "";
  if (!email) {
    throw new AdminError("TOKEN_INVALID", "Cloudflare Access JWT email is missing", 401);
  }

  return {
    email,
    role: roleForEmail(env, email),
    requestId
  };
}

async function jwkForKid(issuer: string, kid: string): Promise<JsonWebKey> {
  const now = Date.now();
  if (!cachedJwks || cachedJwks.issuer !== issuer || cachedJwks.expiresAt <= now) {
    const response = await fetch(`${issuer.replace(/\/$/, "")}/cdn-cgi/access/certs`, {
      headers: { Accept: "application/json" }
    });
    if (!response.ok) {
      throw new AdminError("BACKEND_UNAVAILABLE", "Could not fetch Cloudflare Access certs", 503);
    }
    cachedJwks = {
      issuer,
      expiresAt: now + 5 * 60 * 1000,
      jwks: (await response.json()) as AccessJwks
    };
  }

  const key = cachedJwks.jwks.keys.find((candidate) => candidate.kid === kid);
  if (!key || key.kty !== "RSA") {
    throw new AdminError("TOKEN_INVALID", "Cloudflare Access JWT key is unknown", 401);
  }
  return key as JsonWebKey;
}

function parseJwt(token: string): {
  header: Record<string, unknown>;
  payload: Record<string, unknown>;
  signedData: string;
  signature: Uint8Array;
} {
  const parts = token.split(".");
  if (parts.length !== 3) {
    throw new AdminError("TOKEN_INVALID", "Cloudflare Access JWT is malformed", 401);
  }
  return {
    header: jsonFromBase64Url(parts[0]),
    payload: jsonFromBase64Url(parts[1]),
    signedData: `${parts[0]}.${parts[1]}`,
    signature: bytesFromBase64Url(parts[2])
  };
}

function roleForEmail(env: AdminEnv, email: string): ActorRole {
  const owners = emailSet(env.ADMIN_OWNER_EMAILS);
  const publishers = emailSet(env.ADMIN_PUBLISHER_EMAILS);
  const viewers = emailSet(env.ADMIN_VIEWER_EMAILS);
  if (owners.has(email)) return "owner";
  if (publishers.has(email)) return "publisher";
  if (viewers.has(email)) return "viewer";
  throw new AdminError("TOKEN_INVALID", "Cloudflare Access user is not allowed", 403);
}

function requireRole(actor: Actor, required: ActorRole): void {
  const rank = { viewer: 1, publisher: 2, owner: 3 } satisfies Record<ActorRole, number>;
  if (rank[actor.role] < rank[required]) {
    throw new AdminError("TOKEN_INVALID", "Admin role is not allowed for this action", 403);
  }
}

function requireSameOriginMutation(request: Request, env: AdminEnv): void {
  const origin = request.headers.get("Origin");
  const allowed = new Set([
    new URL(request.url).origin,
    ...csv(env.ADMIN_ALLOWED_ORIGINS)
  ]);
  if (!origin || !allowed.has(origin)) {
    throw new AdminError("TOKEN_INVALID", "Admin mutation origin is not allowed", 403);
  }
}

function requireCsrf(request: Request): void {
  const header = request.headers.get("X-CSRF-Token");
  const cookie = cookieValue(request.headers.get("Cookie"), "trace_admin_csrf");
  if (!header || !cookie || header !== cookie) {
    throw new AdminError("TOKEN_INVALID", "CSRF token is invalid", 403);
  }
}

async function requestJson(request: Request): Promise<Record<string, unknown>> {
  const body = await request.json().catch(() => null);
  if (!body || typeof body !== "object" || Array.isArray(body)) {
    throw new AdminError("INVALID_PARAMETER", "Request body must be a JSON object", 400);
  }
  return body as Record<string, unknown>;
}

function json(data: unknown, status = 200, headers?: HeadersInit): Response {
  return Response.json(data, {
    status,
    headers: {
      "Cache-Control": "no-store",
      ...headers
    }
  });
}

function errorJson(error: unknown, requestId: string): Response {
  if (error instanceof AdminError) {
    return json({ errorCode: error.code, message: error.message, requestId }, error.status);
  }
  const message = error instanceof Error ? error.message : String(error);
  return json(
    { errorCode: "BACKEND_UNAVAILABLE", message: "Admin backend unavailable", requestId, detail: message },
    503
  );
}

function routeSegments(value: string | string[] | undefined): string[] {
  if (!value) return [];
  return Array.isArray(value) ? value : [value];
}

function requestIdFrom(request: Request): string {
  return request.headers.get("X-Request-Id") ?? crypto.randomUUID();
}

function queryString(url: URL, key: string): string | null {
  const value = url.searchParams.get(key);
  return value === "" ? null : value;
}

function requireString(value: unknown, field: string): string {
  if (typeof value !== "string" || value.trim() === "") {
    throw new AdminError("INVALID_PARAMETER", `${field} is required`, 400);
  }
  return value.trim();
}

function boundedString(value: unknown, field: string, maxLength: number): string {
  const text = requireString(value, field);
  if (text.length > maxLength) {
    throw new AdminError("INVALID_PARAMETER", `${field} is too long`, 400);
  }
  return text;
}

function boolFlag(value: unknown): 0 | 1 {
  return value === true || value === 1 || value === "1" ? 1 : 0;
}

function requireInt(value: unknown, field: string): number {
  const parsed =
    typeof value === "number" ? value : typeof value === "string" ? Number(value) : NaN;
  if (!Number.isInteger(parsed) || parsed < 0) {
    throw new AdminError("INVALID_PARAMETER", `${field} must be a non-negative integer`, 400);
  }
  return parsed;
}

function parsePlatform(value: unknown): Platform {
  if (value === "android" || value === "windows") return value;
  throw new AdminError("INVALID_PARAMETER", "platform must be android or windows", 400);
}

function parseChannel(value: unknown): ChannelName {
  if (value === "stable" || value === "beta") return value;
  throw new AdminError("INVALID_PARAMETER", "channel must be stable or beta", 400);
}

function parseDeviceModel(value: unknown): string {
  return requireString(value, "deviceModel").toLowerCase().replace(/\s+/g, "-");
}

function optionalDeviceModel(value: string | null): string | null {
  return value ? value.toLowerCase().replace(/\s+/g, "-") : null;
}

async function listR2Usage(
  env: AdminEnv,
  prefix: string
): Promise<{ prefix: string; objectCount: number; totalSizeBytes: number; byType: StorageTypeSummary[] }> {
  let cursor: string | undefined;
  let objectCount = 0;
  let totalSizeBytes = 0;
  const byType = new Map<string, StorageTypeSummary>();

  do {
    const page = await env.RELEASES_BUCKET.list({ prefix, cursor });
    for (const object of page.objects) {
      const type = assetTypeForR2Key(object.key);
      objectCount += 1;
      totalSizeBytes += object.size;
      const current = byType.get(type) ?? { type, objectCount: 0, totalSizeBytes: 0 };
      current.objectCount += 1;
      current.totalSizeBytes += object.size;
      byType.set(type, current);
    }
    cursor = page.truncated ? page.cursor : undefined;
  } while (cursor);

  return {
    prefix,
    objectCount,
    totalSizeBytes,
    byType: [...byType.values()].sort((left, right) => left.type.localeCompare(right.type))
  };
}

async function deleteR2ObjectsForRelease(
  env: AdminEnv,
  release: ReleaseRow,
  assets: ReleaseAssetRow[]
): Promise<DeleteR2Result> {
  const objects = new Map<string, number>();
  let cursor: string | undefined;
  const prefix = `${release.app_id}/releases/${release.version_code}-${release.release_tag}/`;

  do {
    const page = await env.RELEASES_BUCKET.list({ prefix, cursor });
    for (const object of page.objects) {
      objects.set(object.key, object.size);
    }
    cursor = page.truncated ? page.cursor : undefined;
  } while (cursor);

  for (const asset of assets) {
    if (!asset.r2_key || objects.has(asset.r2_key)) continue;
    const object = await env.RELEASES_BUCKET.head(asset.r2_key);
    if (object) objects.set(asset.r2_key, object.size);
  }

  let totalSizeBytes = 0;
  for (const [key, size] of objects) {
    await env.RELEASES_BUCKET.delete(key);
    totalSizeBytes += size;
  }

  return {
    objectCount: objects.size,
    totalSizeBytes
  };
}

function assetTypeForR2Key(key: string): string {
  if (key.includes("/firmware/")) return "firmware";
  if (key.includes("/android/patches/")) return "patch";
  if (key.includes("/manifest/")) return "manifest";
  if (key.includes("/android/")) return "apk";
  if (key.includes("/windows/")) return "windows";
  return "other";
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

function firmwareChannelSnapshot(
  channel: FirmwareChannelRow,
  currentReleaseId = channel.current_release_id
): Record<string, unknown> {
  return {
    id: channel.id,
    app_id: channel.app_id,
    device_model: channel.device_model,
    name: channel.name,
    current_release_id: currentReleaseId,
    revision: channel.revision,
    disable_latest: channel.disable_latest,
    disable_downloads: channel.disable_downloads,
    maintenance_message: channel.maintenance_message
  };
}

function announcementSnapshot(announcement: AnnouncementRow): Record<string, unknown> {
  return {
    id: announcement.id,
    app_id: announcement.app_id,
    title: announcement.title,
    body: announcement.body,
    pinned: announcement.pinned === 1,
    published: announcement.published === 1,
    published_at: announcement.published_at
  };
}

function canonicalJson(value: unknown): string {
  if (Array.isArray(value)) {
    return `[${value.map((entry) => canonicalJson(entry)).join(",")}]`;
  }
  if (value && typeof value === "object") {
    return `{${Object.entries(value)
      .filter(([, entryValue]) => entryValue !== undefined)
      .sort(([left], [right]) => left.localeCompare(right))
      .map(([key, entryValue]) => `${JSON.stringify(key)}:${canonicalJson(entryValue)}`)
      .join(",")}}`;
  }
  return JSON.stringify(value);
}

function audienceMatches(aud: unknown, expected: string): boolean {
  return Array.isArray(aud) ? aud.includes(expected) : aud === expected;
}

function emailSet(value: string | undefined): Set<string> {
  return new Set(csv(value).map((entry) => entry.toLowerCase()));
}

function csv(value: string | undefined): string[] {
  return (value ?? "")
    .split(",")
    .map((entry) => entry.trim())
    .filter(Boolean);
}

function bearerToken(request: Request): string | null {
  const authorization = request.headers.get("Authorization");
  return authorization?.startsWith("Bearer ") ? authorization.slice("Bearer ".length) : null;
}

function jsonFromBase64Url(value: string): Record<string, unknown> {
  const text = new TextDecoder().decode(bytesFromBase64Url(value));
  const parsed = JSON.parse(text) as unknown;
  if (!parsed || typeof parsed !== "object" || Array.isArray(parsed)) {
    throw new AdminError("TOKEN_INVALID", "Cloudflare Access JWT payload is invalid", 401);
  }
  return parsed as Record<string, unknown>;
}

function bytesFromBase64Url(value: string): Uint8Array {
  const normalized = value.replace(/-/g, "+").replace(/_/g, "/");
  const padded = normalized.padEnd(Math.ceil(normalized.length / 4) * 4, "=");
  const binary = atob(padded);
  const bytes = new Uint8Array(binary.length);
  for (let index = 0; index < binary.length; index += 1) {
    bytes[index] = binary.charCodeAt(index);
  }
  return bytes;
}

function arrayBufferFromBytes(bytes: Uint8Array): ArrayBuffer {
  return bytes.buffer.slice(bytes.byteOffset, bytes.byteOffset + bytes.byteLength) as ArrayBuffer;
}

function cookieValue(cookieHeader: string | null, name: string): string | null {
  if (!cookieHeader) return null;
  for (const part of cookieHeader.split(";")) {
    const [key, ...rest] = part.trim().split("=");
    if (key === name) return rest.join("=");
  }
  return null;
}

function csrfCookie(value: string): string {
  return `trace_admin_csrf=${value}; Path=/api/admin; HttpOnly; Secure; SameSite=Strict; Max-Age=3600`;
}
