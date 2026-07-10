import { ApiError, backendUnavailable, invalidParameter } from "./errors";
import { canonicalJson } from "./crypto";
import { clientIpFrom, json } from "./http";
import { writeLog } from "./logger";
import { enforceRateLimit } from "./rate_limiter";
import { signedDownloadUrls } from "./downloads";
import {
  parseCapabilities,
  parseChannel,
  parseJsonArray,
  parseJsonObject,
  parsePlatform
} from "./validation";
import type {
  AppConfigRow,
  AssetRow,
  ChannelName,
  ChannelRow,
  PatchRow,
  Platform,
  ReleaseRow,
  SecurityPayload,
  WorkerEnv
} from "./types";

const LATEST_QUERY_PARAMS = new Set([
  "appId",
  "platform",
  "channel",
  "versionCode",
  "schemaVersion",
  "capabilities"
]);

interface ManifestEnvelope {
  v1: Record<string, unknown>;
  v2: Record<string, unknown>;
}

interface RenderableLatestState {
  config: AppConfigRow;
  channel: ChannelRow;
  release: ReleaseRow;
  assets: AssetRow[];
  patches: PatchRow[];
}

export async function handleLatest(
  request: Request,
  env: WorkerEnv,
  requestId: string
): Promise<Response> {
  const url = new URL(request.url);
  for (const key of url.searchParams.keys()) {
    if (!LATEST_QUERY_PARAMS.has(key)) {
      throw invalidParameter(`Unsupported query parameter: ${key}`);
    }
  }

  const appId = url.searchParams.get("appId") ?? env.APP_ID;
  const platform = parsePlatform(url.searchParams.get("platform") ?? "android");
  const channel = parseChannel(url.searchParams.get("channel") ?? "stable");
  const versionCode = parseVersionCode(url.searchParams.get("versionCode"));
  const schemaVersion = parseSchemaVersion(url.searchParams.get("schemaVersion"));
  const capabilities = parseCapabilities(url.searchParams.get("capabilities"));
  const wantsV2 = schemaVersion >= 2 && capabilities.length > 0;

  const rate = await enforceRateLimit(
    env,
    `latest:${clientIpFrom(request)}:${appId}:${platform}:${channel}`
  );
  if (!rate.allowed) {
    return json(
      { errorCode: "RATE_LIMITED", message: "Too many update checks", retryAfter: rate.retryAfter },
      429,
      { "Retry-After": String(rate.retryAfter) }
    );
  }

  try {
    const state = await loadLatestState(env, appId, platform, channel);
    if (!state.channel || !state.release) {
      return noUpdate();
    }
    if (state.config.disable_all_latest === 1 || state.channel.disable_latest === 1) {
      return json({
        errorCode: "CHANNEL_STOPPED",
        updateAvailable: false,
        maintenanceMessage: state.channel.maintenance_message ?? state.config.maintenance_message
      });
    }
    if (state.release.state === "disabled") {
      return noUpdate();
    }
    if (versionCode >= state.release.version_code) {
      return noUpdate();
    }
    if (state.release.min_client_version_code > versionCode) {
      return json(
        {
          errorCode: "CLIENT_TOO_OLD",
          message: "Client must install a compatible version first",
          minClientVersionCode: state.release.min_client_version_code
        },
        426
      );
    }

    const renderableState: RenderableLatestState = {
      config: state.config,
      channel: state.channel,
      release: state.release,
      assets: state.assets,
      patches: state.patches
    };
    const origin = new URL(request.url).origin;
    const cacheKey = [
      "manifest",
      encodeURIComponent(origin),
      env.DOWNLOAD_TOKEN_KEY_VERSION,
      appId,
      platform,
      channel,
      String(renderableState.channel.revision)
    ].join(":");
    const cached = await env.MANIFEST_CACHE.get(cacheKey, "json");
    const envelope =
      cached && isManifestEnvelope(cached)
        ? cached
        : await renderAndCacheEnvelope(env, origin, renderableState, cacheKey);
    return json(wantsV2 ? envelope.v2 : envelope.v1);
  } catch (error) {
    if (error instanceof ApiError) throw error;
    const message = error instanceof Error ? error.message : String(error);
    writeLog("error", "latest_failed", { requestId, message });
    throw backendUnavailable();
  }
}

async function renderAndCacheEnvelope(
  env: WorkerEnv,
  origin: string,
  state: RenderableLatestState,
  cacheKey: string
): Promise<ManifestEnvelope> {
  const envelope = await renderManifestEnvelope(env, origin, state);
  const ttl = Number(env.MANIFEST_CACHE_TTL_SECONDS || "60");
  await env.MANIFEST_CACHE.put(cacheKey, JSON.stringify(envelope), { expirationTtl: ttl });
  return envelope;
}

async function renderManifestEnvelope(
  env: WorkerEnv,
  origin: string,
  state: RenderableLatestState
): Promise<ManifestEnvelope> {
  const apk = state.assets.find((asset) => asset.asset_type === "apk");
  if (state.release.platform === "android" && !apk) {
    throw new ApiError("BACKEND_UNAVAILABLE", "Android APK asset is missing", 503);
  }

  const fullUrls = apk
    ? await signedDownloadUrls(env, origin, "GET", apk.id, state.release.id)
    : undefined;
  const securityPayload = parseSecurityPayload(state.release.security_payload_json);
  const payloadSignature = parseJsonObject(state.release.payload_signature_json);
  const capabilities = parseJsonArray(state.release.capabilities_json);

  const renderedPatches = [];
  for (const patch of state.patches) {
    const patchUrls = await signedDownloadUrls(env, origin, "GET", patch.asset_id, state.release.id);
    renderedPatches.push({
      fromVersionCode: patch.from_version_code,
      toVersionCode: state.release.version_code,
      assetName: patch.file_name,
      algorithm: patch.patch_format,
      sha256: patch.patch_sha256,
      size: patch.patch_size_bytes,
      oldSha256: patch.old_sha256,
      newSha256: patch.output_sha256,
      downloadUrl: patchUrls.downloadUrl,
      fallbackUrl: patchUrls.fallbackUrl
    });
  }

  const base = {
    updateAvailable: true,
    platform: state.release.platform,
    versionName: state.release.version_name,
    versionCode: state.release.version_code,
    releaseTag: state.release.release_tag,
    apkAssetName: securityPayload.apkAssetName,
    apkSha256: securityPayload.apkSha256,
    apkSize: securityPayload.apkSize,
    fullDownloadUrl: fullUrls?.downloadUrl,
    fullFallbackUrl: fullUrls?.fallbackUrl,
    patches: renderedPatches
  };

  return {
    v1: {
      schemaVersion: 1,
      ...base
    },
    v2: {
      schemaVersion: 2,
      appId: state.release.app_id,
      channel: state.channel.name,
      releaseId: state.release.id,
      releaseNotes: state.release.release_notes,
      minClientVersionCode: state.release.min_client_version_code,
      capabilities,
      payloadSignature,
      assets: securityPayload.assetHashes,
      ...base
    }
  };
}

interface LatestState {
  config: AppConfigRow;
  channel: ChannelRow | null;
  release: ReleaseRow | null;
  assets: AssetRow[];
  patches: PatchRow[];
}

async function loadLatestState(
  env: WorkerEnv,
  appId: string,
  platform: Platform,
  channelName: ChannelName
): Promise<LatestState> {
  const config =
    (await env.DB.prepare("SELECT * FROM app_config WHERE app_id = ?")
      .bind(appId)
      .first<AppConfigRow>()) ?? defaultConfig(appId);

  const channel = await env.DB.prepare(
    "SELECT * FROM channels WHERE app_id = ? AND platform = ? AND name = ? LIMIT 1"
  )
    .bind(appId, platform, channelName)
    .first<ChannelRow>();

  if (!channel?.current_release_id) {
    return { config, channel, release: null, assets: [], patches: [] };
  }

  const release = await env.DB.prepare("SELECT * FROM releases WHERE id = ? LIMIT 1")
    .bind(channel.current_release_id)
    .first<ReleaseRow>();
  if (!release) {
    return { config, channel, release: null, assets: [], patches: [] };
  }

  const assets = await env.DB.prepare(
    "SELECT * FROM release_assets WHERE release_id = ? AND disabled = 0 ORDER BY asset_type, file_name"
  )
    .bind(release.id)
    .all<AssetRow>();
  const patches = await env.DB.prepare(
    `
      SELECT p.*, a.file_name
      FROM patches p
      JOIN release_assets a ON a.id = p.asset_id
      WHERE p.to_release_id = ? AND p.disabled = 0 AND a.disabled = 0
      ORDER BY
        p.from_version_code DESC,
        p.old_sha256 ASC,
        CASE p.patch_format WHEN 'tracepatch' THEN 0 ELSE 1 END,
        a.file_name ASC
    `
  )
    .bind(release.id)
    .all<PatchRow>();

  return {
    config,
    channel,
    release,
    assets: assets.results,
    patches: patches.results
  };
}

function defaultConfig(appId: string): AppConfigRow {
  return {
    app_id: appId,
    default_channel: "stable",
    min_supported_client_version_code: 0,
    emergency_manifest_url: null,
    disable_all_latest: 0,
    disable_all_downloads: 0,
    maintenance_message: null
  };
}

function parseSecurityPayload(value: string): SecurityPayload {
  const parsed = JSON.parse(value) as SecurityPayload;
  if (!parsed || typeof parsed !== "object") {
    throw new ApiError("BACKEND_UNAVAILABLE", "Security payload is invalid", 503);
  }
  return parsed;
}

function parseVersionCode(value: string | null): number {
  if (!value) return 0;
  const parsed = Number(value);
  if (!Number.isInteger(parsed) || parsed < 0) {
    throw invalidParameter("versionCode must be a non-negative integer");
  }
  return parsed;
}

function parseSchemaVersion(value: string | null): number {
  if (!value) return 1;
  const parsed = Number(value);
  if (!Number.isInteger(parsed) || parsed < 1) {
    throw invalidParameter("schemaVersion must be a positive integer");
  }
  return parsed;
}

function noUpdate(): Response {
  return json({ errorCode: "NO_UPDATE", updateAvailable: false });
}

function isManifestEnvelope(value: unknown): value is ManifestEnvelope {
  if (!value || typeof value !== "object") return false;
  const candidate = value as Record<string, unknown>;
  return typeof candidate.v1 === "object" && typeof candidate.v2 === "object";
}

export function securityPayloadCanonicalJson(payload: SecurityPayload): string {
  return canonicalJson(payload);
}
