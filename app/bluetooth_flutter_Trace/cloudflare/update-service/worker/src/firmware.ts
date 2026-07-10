import { ApiError, backendUnavailable, invalidParameter } from "./errors";
import { verifyBearerToken } from "./crypto";
import { clientIpFrom, json } from "./http";
import { writeLog } from "./logger";
import { enforceRateLimit } from "./rate_limiter";
import { signDownloadToken, verifyDownloadToken } from "./downloads";
import { optionalString, parseChannel, requireInt, requireSha256, requireString } from "./validation";
import type { ChannelName, FirmwareChannelRow, FirmwareReleaseRow, WorkerEnv } from "./types";

const FIRMWARE_LATEST_QUERY_PARAMS = new Set([
  "appId",
  "deviceModel",
  "channel",
  "currentVersion",
  "currentVersionCode"
]);

interface RegisterFirmwareReleaseRequest {
  appId: string;
  deviceModel: string;
  releaseTag: string;
  runId: string;
  commitSha: string;
  versionName: string;
  versionCode: number;
  releaseNotes: string;
  fileName: string;
  sha256: string;
  sizeBytes: number;
  githubUrl: string;
  r2Key?: string;
  r2Verified: boolean;
  targetHardware?: string;
  transport: string;
  minAppVersionCode: number;
  isFormalRelease: boolean;
  r2Backfill: boolean;
}

interface FirmwareDownloadStateRow extends FirmwareReleaseRow {
  channel_id: string | null;
  channel_disable_downloads: number | null;
  app_disable_downloads: number | null;
}

export async function handleFirmwareLatest(
  request: Request,
  env: WorkerEnv,
  requestId: string
): Promise<Response> {
  const url = new URL(request.url);
  for (const key of url.searchParams.keys()) {
    if (!FIRMWARE_LATEST_QUERY_PARAMS.has(key)) {
      throw invalidParameter(`Unsupported query parameter: ${key}`);
    }
  }

  const appId = url.searchParams.get("appId") ?? env.APP_ID;
  const deviceModel = normalizeDeviceModel(requireString(url.searchParams.get("deviceModel"), "deviceModel"));
  const channel = parseChannel(url.searchParams.get("channel") ?? "stable");
  const currentVersion = optionalString(url.searchParams.get("currentVersion"));
  const currentVersionCode = parseOptionalVersionCode(url.searchParams.get("currentVersionCode"));

  const rate = await enforceRateLimit(
    env,
    `firmware-latest:${clientIpFrom(request)}:${appId}:${deviceModel}:${channel}`
  );
  if (!rate.allowed) {
    return json(
      { errorCode: "RATE_LIMITED", message: "Too many firmware update checks", retryAfter: rate.retryAfter },
      429,
      { "Retry-After": String(rate.retryAfter) }
    );
  }

  try {
    const state = await loadFirmwareLatestState(env, appId, deviceModel, channel);
    if (!state.channel?.current_release_id || !state.release) {
      return noFirmwareUpdate();
    }
    if (state.channel.disable_latest === 1) {
      return json({
        errorCode: "CHANNEL_STOPPED",
        updateAvailable: false,
        maintenanceMessage: state.channel.maintenance_message
      });
    }
    if (state.release.state === "disabled" || state.release.archived === 1) {
      return noFirmwareUpdate();
    }
    if (!isFirmwareNewer(state.release, currentVersionCode, currentVersion)) {
      return noFirmwareUpdate();
    }
    if (state.release.r2_state !== "available" || !state.release.r2_key) {
      throw backendUnavailable("Firmware R2 asset is not available");
    }

    const origin = new URL(request.url).origin;
    const urls = await signedFirmwareDownloadUrls(env, origin, state.release);
    return json({
      schemaVersion: 1,
      updateAvailable: true,
      appId: state.release.app_id,
      deviceModel: state.release.device_model,
      channel: state.channel.name,
      releaseId: state.release.id,
      versionName: state.release.version_name,
      versionCode: state.release.version_code,
      releaseTag: state.release.release_tag,
      releaseNotes: state.release.release_notes,
      fileName: state.release.file_name,
      sha256: state.release.sha256,
      sizeBytes: state.release.size_bytes,
      targetHardware: state.release.target_hardware,
      transport: state.release.transport,
      downloadUrl: urls.downloadUrl,
      expiresAt: urls.expiresAt
    });
  } catch (error) {
    if (error instanceof ApiError) throw error;
    const message = error instanceof Error ? error.message : String(error);
    writeLog("error", "firmware_latest_failed", { requestId, message });
    throw backendUnavailable();
  }
}

export async function handleFirmwareDownload(
  request: Request,
  env: WorkerEnv,
  requestId: string
): Promise<Response> {
  const url = new URL(request.url);
  const assetId = requiredQuery(url, "assetId");
  const releaseId = requiredQuery(url, "releaseId");
  const expiresAt = Number(requiredQuery(url, "expiresAt"));
  const keyVersion = requiredQuery(url, "keyVersion");
  const signature = requiredQuery(url, "signature");

  await verifyDownloadToken(env, request.method, assetId, releaseId, expiresAt, keyVersion, signature);
  const state = await loadFirmwareDownloadState(env, assetId, releaseId);
  ensureFirmwareDownloadAllowed(state);
  return streamFirmwareR2Asset(env, state, requestId);
}

export async function handleRegisterFirmwareRelease(
  request: Request,
  env: WorkerEnv,
  requestId: string
): Promise<Response> {
  const token = bearerToken(request);
  const authorized = await verifyBearerToken(token, env.DEPLOY_TOKEN_SHA256);
  if (!authorized) {
    throw new ApiError("TOKEN_INVALID", "CI deploy token is invalid", 401);
  }

  const input = parseRegisterFirmwareReleaseRequest(await request.json());
  if (!input.isFormalRelease) {
    throw new ApiError("FORMAL_RELEASE_REQUIRED", "Firmware candidates require a formal release", 403);
  }
  await validateFirmwareAsset(input, env);

  const releaseId = firmwareReleaseIdFor(input.appId, input.deviceModel, input.releaseTag);
  const existing = await env.DB.prepare(
    "SELECT id, run_id, commit_sha FROM firmware_releases WHERE app_id = ? AND device_model = ? AND release_tag = ? LIMIT 1"
  )
    .bind(input.appId, input.deviceModel, input.releaseTag)
    .first<{ id: string; run_id: string; commit_sha: string }>();
  if (existing) {
    if (existing.run_id === input.runId && existing.commit_sha === input.commitSha) {
      const r2AssetsUpdated = await updateFirmwareR2AssetState(env, input, existing.id, requestId);
      return json({ ok: true, releaseId: existing.id, idempotent: true, r2AssetsUpdated });
    }
    if (input.r2Backfill) {
      if (existing.commit_sha !== input.commitSha) {
        throw invalidParameter("r2Backfill commitSha must match the existing firmware release");
      }
      const r2AssetsUpdated = await updateFirmwareR2AssetState(env, input, existing.id, requestId);
      return json({
        ok: true,
        releaseId: existing.id,
        idempotent: false,
        r2Backfill: true,
        r2AssetsUpdated
      });
    }
    throw invalidParameter("firmware releaseTag already exists with different runId or commitSha");
  }
  if (input.r2Backfill) {
    throw invalidParameter("r2Backfill can only update an existing firmware release");
  }

  const statements: D1PreparedStatement[] = [
    env.DB.prepare("INSERT OR IGNORE INTO apps (id, name) VALUES (?, ?)").bind(
      input.appId,
      input.appId
    ),
    env.DB.prepare("INSERT OR IGNORE INTO app_config (app_id) VALUES (?)").bind(input.appId),
    env.DB.prepare(
      "INSERT OR IGNORE INTO firmware_channels (id, app_id, device_model, name) VALUES (?, ?, ?, 'stable')"
    ).bind(firmwareChannelIdFor(input.appId, input.deviceModel, "stable"), input.appId, input.deviceModel),
    env.DB.prepare(
      "INSERT OR IGNORE INTO firmware_channels (id, app_id, device_model, name) VALUES (?, ?, ?, 'beta')"
    ).bind(firmwareChannelIdFor(input.appId, input.deviceModel, "beta"), input.appId, input.deviceModel),
    env.DB.prepare(
      `
        INSERT INTO firmware_releases (
          id,
          app_id,
          device_model,
          version_name,
          version_code,
          release_tag,
          commit_sha,
          run_id,
          state,
          release_notes,
          file_name,
          sha256,
          size_bytes,
          r2_key,
          r2_state,
          github_url,
          target_hardware,
          transport,
          min_app_version_code
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, 'candidate', ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
      `
    ).bind(
      releaseId,
      input.appId,
      input.deviceModel,
      input.versionName,
      input.versionCode,
      input.releaseTag,
      input.commitSha,
      input.runId,
      input.releaseNotes,
      input.fileName,
      input.sha256,
      input.sizeBytes,
      input.r2Key ?? null,
      input.r2Key ? "available" : "not_uploaded",
      input.githubUrl,
      input.targetHardware ?? null,
      input.transport,
      input.minAppVersionCode
    ),
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
          after_json
        )
        VALUES (?, ?, 'github-actions', 'ci', 'register_firmware_candidate', 'firmware_release', ?, ?, ?)
      `
    ).bind(
      crypto.randomUUID(),
      input.appId,
      releaseId,
      requestId,
      JSON.stringify({
        deviceModel: input.deviceModel,
        releaseTag: input.releaseTag,
        versionCode: input.versionCode,
        fileName: input.fileName,
        sha256: input.sha256,
        sizeBytes: input.sizeBytes,
        r2Key: input.r2Key ?? null
      })
    )
  ];

  await env.DB.batch(statements);
  return json({ ok: true, releaseId, idempotent: false }, 201);
}

async function signedFirmwareDownloadUrls(
  env: WorkerEnv,
  origin: string,
  release: FirmwareReleaseRow
): Promise<{ downloadUrl: string; expiresAt: number }> {
  const ttlSeconds = Number(env.DOWNLOAD_TOKEN_TTL_SECONDS || "300");
  const expiresAt = Math.floor(Date.now() / 1000) + ttlSeconds;
  const keyVersion = env.DOWNLOAD_TOKEN_KEY_VERSION;
  const assetId = firmwareAssetIdFor(release.id, release.file_name);
  const signature = await signDownloadToken(env, "GET", assetId, release.id, expiresAt, keyVersion);
  const query = new URLSearchParams({
    assetId,
    releaseId: release.id,
    expiresAt: String(expiresAt),
    keyVersion,
    signature
  });
  return {
    downloadUrl: `${origin}/api/public/firmware/download?${query.toString()}`,
    expiresAt
  };
}

async function loadFirmwareLatestState(
  env: WorkerEnv,
  appId: string,
  deviceModel: string,
  channelName: ChannelName
): Promise<{ channel: FirmwareChannelRow | null; release: FirmwareReleaseRow | null }> {
  const channel = await env.DB.prepare(
    "SELECT * FROM firmware_channels WHERE app_id = ? AND device_model = ? AND name = ? LIMIT 1"
  )
    .bind(appId, deviceModel, channelName)
    .first<FirmwareChannelRow>();
  if (!channel?.current_release_id) {
    return { channel: channel ?? null, release: null };
  }

  const release = await env.DB.prepare("SELECT * FROM firmware_releases WHERE id = ? LIMIT 1")
    .bind(channel.current_release_id)
    .first<FirmwareReleaseRow>();
  return { channel, release: release ?? null };
}

async function loadFirmwareDownloadState(
  env: WorkerEnv,
  assetId: string,
  releaseId: string
): Promise<FirmwareDownloadStateRow> {
  const row = await env.DB.prepare(
    `
      SELECT
        f.*,
        c.id AS channel_id,
        c.disable_downloads AS channel_disable_downloads,
        ac.disable_all_downloads AS app_disable_downloads
      FROM firmware_releases f
      LEFT JOIN firmware_channels c ON c.current_release_id = f.id
      LEFT JOIN app_config ac ON ac.app_id = f.app_id
      WHERE f.id = ?
      LIMIT 1
    `
  )
    .bind(releaseId)
    .first<FirmwareDownloadStateRow>();

  if (!row || firmwareAssetIdFor(row.id, row.file_name) !== assetId) {
    throw new ApiError("ASSET_DISABLED", "Firmware asset is not available", 410);
  }
  return row;
}

function ensureFirmwareDownloadAllowed(row: FirmwareDownloadStateRow): void {
  if (row.state === "disabled") {
    throw new ApiError("ASSET_DISABLED", "Firmware release is disabled", 410);
  }
  if (row.archived === 1 || row.r2_state === "archived" || row.r2_state === "r2_deleted") {
    throw new ApiError("ASSET_ARCHIVED", "Firmware asset is archived", 409);
  }
  if (row.app_disable_downloads === 1 || row.channel_disable_downloads === 1) {
    throw new ApiError("CHANNEL_STOPPED", "Firmware downloads are temporarily disabled", 503);
  }
  if (!row.channel_id) {
    throw new ApiError("ASSET_DISABLED", "Firmware release is not currently published to a channel", 410);
  }
  if (row.r2_state !== "available" || !row.r2_key) {
    throw backendUnavailable("Firmware R2 asset is not available");
  }
}

async function streamFirmwareR2Asset(
  env: WorkerEnv,
  state: FirmwareDownloadStateRow,
  requestId: string
): Promise<Response> {
  if (!state.r2_key) throw backendUnavailable("Firmware R2 asset is not available");
  let object: R2ObjectBody | null;
  try {
    object = await env.RELEASES_BUCKET.get(state.r2_key);
  } catch (error) {
    const message = error instanceof Error ? error.message : String(error);
    writeLog("error", "firmware_r2_download_failed", {
      requestId,
      releaseId: state.id,
      r2Key: state.r2_key,
      message
    });
    throw backendUnavailable("Firmware R2 asset could not be read");
  }

  if (!object) throw backendUnavailable("Firmware R2 asset is missing");
  if (object.size !== state.size_bytes) throw backendUnavailable("Firmware R2 asset size mismatch");

  const headers = new Headers();
  object.writeHttpMetadata(headers);
  headers.set("Content-Type", headers.get("Content-Type") ?? "application/octet-stream");
  headers.set("Content-Length", String(object.size));
  headers.set("ETag", object.httpEtag);
  headers.set("Cache-Control", "public, max-age=31536000, immutable");
  headers.set("Content-Disposition", `attachment; filename="${contentDispositionFileName(state.file_name)}"`);
  headers.set("X-Request-Id", requestId);
  headers.set("X-Trace-Asset-Source", "r2");
  headers.set("X-Trace-Asset-Type", "firmware");

  writeLog("info", "firmware_download_stream", {
    requestId,
    releaseId: state.id,
    channel: state.channel_id,
    bytes: object.size,
    status: "ok"
  });

  return new Response(object.body, { headers });
}

function parseRegisterFirmwareReleaseRequest(value: unknown): RegisterFirmwareReleaseRequest {
  if (!value || typeof value !== "object") {
    throw invalidParameter("request body must be an object");
  }
  const body = value as Record<string, unknown>;
  return {
    appId: requireString(body.appId, "appId"),
    deviceModel: normalizeDeviceModel(requireString(body.deviceModel, "deviceModel")),
    releaseTag: requireString(body.releaseTag, "releaseTag"),
    runId: requireString(body.runId, "runId"),
    commitSha: requireString(body.commitSha, "commitSha"),
    versionName: normalizeVersionName(requireString(body.versionName, "versionName")),
    versionCode: requireInt(body.versionCode, "versionCode"),
    releaseNotes: String(body.releaseNotes ?? ""),
    fileName: requireString(body.fileName, "fileName"),
    sha256: requireSha256(body.sha256, "sha256"),
    sizeBytes: requireInt(body.sizeBytes, "sizeBytes"),
    githubUrl: requireString(body.githubUrl, "githubUrl"),
    r2Key: typeof body.r2Key === "string" ? body.r2Key : undefined,
    r2Verified: body.r2Verified === true,
    targetHardware: optionalString(body.targetHardware),
    transport: optionalString(body.transport) ?? "ble",
    minAppVersionCode: body.minAppVersionCode ? requireInt(body.minAppVersionCode, "minAppVersionCode") : 0,
    isFormalRelease: body.isFormalRelease === true,
    r2Backfill: body.r2Backfill === true
  };
}

async function validateFirmwareAsset(
  input: RegisterFirmwareReleaseRequest,
  env: WorkerEnv
): Promise<void> {
  assertSafeFileName(input.fileName);
  assertImmutableGitHubAssetUrl(input.githubUrl, env, input.releaseTag);
  if (!input.r2Key) return;
  assertExpectedFirmwareR2Key(input);
  if (!input.r2Verified) {
    throw invalidParameter("r2Verified must be true when r2Key is provided");
  }
  const object = await env.RELEASES_BUCKET.head(input.r2Key);
  if (!object) {
    throw invalidParameter(`R2 object is missing: ${input.fileName}`);
  }
  if (object.size !== input.sizeBytes) {
    throw invalidParameter(`R2 object size mismatch: ${input.fileName}`);
  }
  const metadataSha256 = object.customMetadata?.sha256?.toLowerCase();
  if (metadataSha256 && metadataSha256 !== input.sha256) {
    throw invalidParameter(`R2 object sha256 metadata mismatch: ${input.fileName}`);
  }
}

async function updateFirmwareR2AssetState(
  env: WorkerEnv,
  input: RegisterFirmwareReleaseRequest,
  releaseId: string,
  requestId: string
): Promise<number> {
  if (!input.r2Key) return 0;
  const result = await env.DB.prepare(
    `
      UPDATE firmware_releases
      SET r2_key = ?, r2_state = 'available', updated_at = datetime('now')
      WHERE id = ?
        AND sha256 = ?
        AND size_bytes = ?
        AND file_name = ?
        AND state <> 'disabled'
    `
  )
    .bind(input.r2Key, releaseId, input.sha256, input.sizeBytes, input.fileName)
    .run();
  if (result.meta.changes !== 1) {
    throw invalidParameter(`registered firmware does not match R2 metadata: ${input.fileName}`);
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
        after_json
      )
      VALUES (?, ?, 'github-actions', 'ci', 'update_firmware_r2_asset', 'firmware_release', ?, ?, ?)
    `
  )
    .bind(
      crypto.randomUUID(),
      input.appId,
      releaseId,
      requestId,
      JSON.stringify({ r2AssetsUpdated: 1, r2Key: input.r2Key })
    )
    .run();
  return 1;
}

function isFirmwareNewer(
  release: FirmwareReleaseRow,
  currentVersionCode: number | null,
  currentVersion: string | undefined
): boolean {
  if (currentVersionCode !== null) {
    return currentVersionCode < release.version_code;
  }
  if (!currentVersion) return true;
  const compared = compareVersionNames(currentVersion, release.version_name);
  return compared < 0;
}

function compareVersionNames(left: string, right: string): number {
  const leftParts = versionParts(left);
  const rightParts = versionParts(right);
  if (!leftParts || !rightParts) return normalizeVersionName(left) === normalizeVersionName(right) ? 0 : -1;
  const length = Math.max(leftParts.length, rightParts.length);
  for (let index = 0; index < length; index += 1) {
    const diff = (leftParts[index] ?? 0) - (rightParts[index] ?? 0);
    if (diff !== 0) return diff < 0 ? -1 : 1;
  }
  return 0;
}

function versionParts(value: string): number[] | null {
  const normalized = normalizeVersionName(value);
  if (!/^\d+(?:\.\d+)*$/.test(normalized)) return null;
  return normalized.split(".").map((part) => Number(part));
}

function normalizeVersionName(value: string): string {
  return value.trim().replace(/^v/i, "");
}

function parseOptionalVersionCode(value: string | null): number | null {
  if (!value) return null;
  const parsed = Number(value);
  if (!Number.isInteger(parsed) || parsed < 0) {
    throw invalidParameter("currentVersionCode must be a non-negative integer");
  }
  return parsed;
}

function normalizeDeviceModel(value: string): string {
  return value.trim().toLowerCase().replace(/\s+/g, "-");
}

function assertImmutableGitHubAssetUrl(value: string, env: WorkerEnv, releaseTag: string): void {
  if (value.includes("/latest/download/")) {
    throw invalidParameter("GitHub latest download URLs are not allowed");
  }
  const url = new URL(value);
  if (url.hostname !== "github.com") {
    throw invalidParameter("Firmware assets must use github.com immutable release URLs");
  }
  const expectedPrefix = `/${env.GITHUB_OWNER}/${env.GITHUB_REPO}/releases/download/`;
  if (!url.pathname.startsWith(expectedPrefix) || !url.pathname.includes(`/${releaseTag}/`)) {
    throw invalidParameter("GitHub firmware asset URL must match releaseTag");
  }
}

function assertExpectedFirmwareR2Key(input: RegisterFirmwareReleaseRequest): void {
  const expected = firmwareR2KeyForRelease(input);
  if (input.r2Key !== expected) {
    throw invalidParameter(`R2 key does not match the firmware object key policy: ${input.fileName}`);
  }
}

function firmwareR2KeyForRelease(input: RegisterFirmwareReleaseRequest): string {
  assertSafeFileName(input.fileName);
  assertSafePathPart(input.appId, "appId");
  assertSafePathPart(input.deviceModel, "deviceModel");
  assertSafePathPart(input.releaseTag, "releaseTag");
  return `${input.appId}/firmware/${input.deviceModel}/${input.versionCode}-${input.releaseTag}/${input.fileName}`;
}

function assertSafeFileName(fileName: string): void {
  if (
    fileName.includes("/") ||
    fileName.includes("\\") ||
    fileName === "." ||
    fileName === ".." ||
    fileName.trim() === ""
  ) {
    throw invalidParameter("firmware fileName must be a plain file name");
  }
}

function assertSafePathPart(value: string, fieldName: string): void {
  if (
    value.includes("/") ||
    value.includes("\\") ||
    value.includes("..") ||
    value.trim() === ""
  ) {
    throw invalidParameter(`${fieldName} contains invalid R2 path characters`);
  }
}

function firmwareReleaseIdFor(appId: string, deviceModel: string, releaseTag: string): string {
  return `fw_${slug(appId)}_${slug(deviceModel)}_${slug(releaseTag)}`;
}

function firmwareChannelIdFor(appId: string, deviceModel: string, channel: string): string {
  return `fw_ch_${slug(appId)}_${slug(deviceModel)}_${channel}`;
}

function firmwareAssetIdFor(releaseId: string, fileName: string): string {
  return `fw_asset_${releaseId}_${slug(fileName)}`;
}

function slug(value: string): string {
  return value.toLowerCase().replace(/[^a-z0-9]+/g, "_").replace(/^_+|_+$/g, "");
}

function requiredQuery(url: URL, key: string): string {
  const value = url.searchParams.get(key);
  if (!value) throw new ApiError("TOKEN_INVALID", `${key} is required`, 401);
  return value;
}

function contentDispositionFileName(fileName: string): string {
  return fileName.replace(/["\\\r\n]/g, "_");
}

function bearerToken(request: Request): string | null {
  const authorization = request.headers.get("Authorization");
  if (authorization?.startsWith("Bearer ")) return authorization.slice("Bearer ".length);
  return request.headers.get("X-Deploy-Token");
}

function noFirmwareUpdate(): Response {
  return json({ errorCode: "NO_UPDATE", updateAvailable: false });
}
