import { ApiError, backendUnavailable } from "./errors";
import { downloadHmacKey, signHmacSha256, timingSafeEqual } from "./crypto";
import { json } from "./http";
import { writeLog } from "./logger";
import type { AssetRow, ChannelRow, ReleaseRow, WorkerEnv } from "./types";

interface DownloadStateRow extends AssetRow {
  release_state: ReleaseRow["state"];
  release_archived: number;
  channel_id: string | null;
  channel_disable_downloads: number | null;
  app_disable_downloads: number | null;
}

export interface SignedDownloadUrls {
  downloadUrl: string;
  fallbackUrl: string;
  expiresAt: number;
}

export async function signedDownloadUrls(
  env: WorkerEnv,
  origin: string,
  method: string,
  assetId: string,
  releaseId: string
): Promise<SignedDownloadUrls> {
  const ttlSeconds = Number(env.DOWNLOAD_TOKEN_TTL_SECONDS || "300");
  const expiresAt = Math.floor(Date.now() / 1000) + ttlSeconds;
  const keyVersion = env.DOWNLOAD_TOKEN_KEY_VERSION;
  const signature = await signDownloadToken(env, method, assetId, releaseId, expiresAt, keyVersion);
  const query = new URLSearchParams({
    assetId,
    releaseId,
    expiresAt: String(expiresAt),
    keyVersion,
    signature
  });

  return {
    downloadUrl: `${origin}/api/public/download?${query.toString()}`,
    fallbackUrl: `${origin}/api/public/github-fallback?${query.toString()}`,
    expiresAt
  };
}

export async function signDownloadToken(
  env: WorkerEnv,
  method: string,
  assetId: string,
  releaseId: string,
  expiresAt: number,
  keyVersion: string
): Promise<string> {
  const key = downloadHmacKey(env, keyVersion);
  return signHmacSha256(downloadTokenMessage(method, assetId, releaseId, expiresAt, keyVersion), key);
}

export async function handleDownload(
  request: Request,
  env: WorkerEnv,
  requestId: string,
  mode: "primary" | "github-fallback"
): Promise<Response> {
  const url = new URL(request.url);
  const assetId = requiredQuery(url, "assetId");
  const releaseId = requiredQuery(url, "releaseId");
  const expiresAt = Number(requiredQuery(url, "expiresAt"));
  const keyVersion = requiredQuery(url, "keyVersion");
  const signature = requiredQuery(url, "signature");

  await verifyDownloadToken(env, request.method, assetId, releaseId, expiresAt, keyVersion, signature);
  const state = await loadDownloadState(env, assetId, releaseId);
  ensureDownloadAllowed(state, mode);

  if (mode === "primary") {
    return streamR2Asset(env, state, requestId);
  }

  writeLog("info", "download_redirect", {
    requestId,
    releaseId,
    assetId,
    channel: state.channel_id,
    status: "redirect",
    mode
  });

  return new Response(null, {
    status: 302,
    headers: {
      Location: state.github_url,
      "Cache-Control": "no-store",
      "X-Request-Id": requestId
    }
  });
}

async function streamR2Asset(
  env: WorkerEnv,
  state: DownloadStateRow,
  requestId: string
): Promise<Response> {
  if (state.r2_state !== "available" || !state.r2_key) {
    throw backendUnavailable("R2 primary asset is not available");
  }

  let object: R2ObjectBody | null;
  try {
    object = await env.RELEASES_BUCKET.get(state.r2_key);
  } catch (error) {
    const message = error instanceof Error ? error.message : String(error);
    writeLog("error", "r2_download_failed", {
      requestId,
      releaseId: state.release_id,
      assetId: state.id,
      r2Key: state.r2_key,
      message
    });
    throw backendUnavailable("R2 primary asset could not be read");
  }

  if (!object) {
    throw backendUnavailable("R2 primary asset is missing");
  }
  if (object.size !== state.size_bytes) {
    throw backendUnavailable("R2 primary asset size mismatch");
  }

  const headers = new Headers();
  object.writeHttpMetadata(headers);
  headers.set("Content-Type", headers.get("Content-Type") ?? contentTypeForAsset(state));
  headers.set("Content-Length", String(object.size));
  headers.set("ETag", object.httpEtag);
  headers.set("Cache-Control", "public, max-age=31536000, immutable");
  headers.set("Content-Disposition", `attachment; filename="${contentDispositionFileName(state.file_name)}"`);
  headers.set("X-Request-Id", requestId);
  headers.set("X-Trace-Asset-Source", "r2");

  writeLog("info", "download_stream", {
    requestId,
    releaseId: state.release_id,
    assetId: state.id,
    channel: state.channel_id,
    assetType: state.asset_type,
    bytes: object.size,
    status: "ok",
    mode: "primary"
  });

  return new Response(object.body, { headers });
}

export async function verifyDownloadToken(
  env: WorkerEnv,
  method: string,
  assetId: string,
  releaseId: string,
  expiresAt: number,
  keyVersion: string,
  signature: string
): Promise<void> {
  if (!Number.isInteger(expiresAt) || expiresAt <= 0) {
    throw new ApiError("TOKEN_INVALID", "Download token expiry is invalid", 401);
  }
  if (expiresAt < Math.floor(Date.now() / 1000)) {
    throw new ApiError("TOKEN_EXPIRED", "Download token expired", 401);
  }

  const expected = await signDownloadToken(env, method, assetId, releaseId, expiresAt, keyVersion);
  if (!timingSafeEqual(expected, signature)) {
    throw new ApiError("TOKEN_INVALID", "Download token signature is invalid", 401);
  }
}

export async function loadDownloadState(
  env: WorkerEnv,
  assetId: string,
  releaseId: string
): Promise<DownloadStateRow> {
  const row = await env.DB.prepare(
    `
      SELECT
        a.*,
        r.state AS release_state,
        r.archived AS release_archived,
        c.id AS channel_id,
        c.disable_downloads AS channel_disable_downloads,
        ac.disable_all_downloads AS app_disable_downloads
      FROM release_assets a
      JOIN releases r ON r.id = a.release_id
      LEFT JOIN channels c ON c.current_release_id = r.id
      LEFT JOIN app_config ac ON ac.app_id = r.app_id
      WHERE a.id = ? AND a.release_id = ?
      LIMIT 1
    `
  )
    .bind(assetId, releaseId)
    .first<DownloadStateRow>();

  if (!row) {
    throw new ApiError("ASSET_DISABLED", "Asset is not available", 410);
  }
  return row;
}

export function ensureDownloadAllowed(
  row: DownloadStateRow,
  mode: "primary" | "github-fallback"
): void {
  if (row.release_state === "disabled" || row.disabled === 1) {
    throw new ApiError("ASSET_DISABLED", "Asset or release is disabled", 410);
  }
  if (row.release_archived === 1 || row.r2_state === "archived" || row.r2_state === "r2_deleted") {
    throw new ApiError("ASSET_ARCHIVED", "Asset is archived and must be restored before download", 409);
  }
  if (row.app_disable_downloads === 1 || row.channel_disable_downloads === 1) {
    throw new ApiError("CHANNEL_STOPPED", "Downloads are temporarily disabled", 503);
  }
  if (!row.channel_id) {
    throw new ApiError("ASSET_DISABLED", "Release is not currently published to a channel", 410);
  }
  if (mode === "github-fallback" && row.github_url.includes("/latest/download/")) {
    throw new ApiError("FALLBACK_UNAVAILABLE", "GitHub fallback URL is not immutable", 502);
  }
}

export function tokenFailureResponse(error: ApiError): Response {
  return json({ errorCode: error.code, message: error.message }, error.status);
}

function requiredQuery(url: URL, key: string): string {
  const value = url.searchParams.get(key);
  if (!value) throw new ApiError("TOKEN_INVALID", `${key} is required`, 401);
  return value;
}

function contentTypeForAsset(asset: AssetRow): string {
  if (asset.asset_type === "apk") return "application/vnd.android.package-archive";
  if (asset.asset_type === "manifest") return "application/json; charset=utf-8";
  if (asset.asset_type === "windows_zip") return "application/zip";
  if (asset.file_name.endsWith(".tpatch")) return "application/octet-stream";
  return "application/octet-stream";
}

function contentDispositionFileName(fileName: string): string {
  return fileName.replace(/["\\\r\n]/g, "_");
}

function downloadTokenMessage(
  method: string,
  assetId: string,
  releaseId: string,
  expiresAt: number,
  keyVersion: string
): string {
  return [method.toUpperCase(), assetId, releaseId, String(expiresAt), keyVersion].join("\n");
}
