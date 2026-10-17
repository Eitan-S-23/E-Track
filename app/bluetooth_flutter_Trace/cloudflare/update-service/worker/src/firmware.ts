import { ApiError, backendUnavailable, invalidParameter } from "./errors";
import { sha256Hex, verifyBearerToken } from "./crypto";
import { clientIpFrom, json } from "./http";
import { enforceRateLimit } from "./rate_limiter";
import { signFirmwareDownload, streamFirmwareObject, verifyFirmwareDownload, verifyFirmwareObject } from "./firmware_download";
import { APP_VERSION_MAX, FIRMWARE_MODEL, FirmwareSchemaError, U32_MAX, canonicalJson,
  parseFirmwareRegistration } from "../../scripts/firmware-schema.mjs";
import type { FirmwareRegistration } from "../../scripts/firmware-schema.mjs";
import type { FirmwareAssetRow, FirmwareChannelRow, FirmwareReleaseRow, WorkerEnv } from "./types";

const QUERY = ["appId", "deviceModel", "channel", "currentVersionCode", "currentImageSha",
  "hardwareRevision", "layoutId", "bootVersion", "protocolVersion", "appVersionCode"];

export async function firmwareOperation(action: () => Promise<Response>): Promise<Response> {
  try { return await action(); } catch (error) {
    if (error instanceof ApiError) throw error;
    if (error instanceof FirmwareSchemaError) {
      throw new ApiError(error.code, error.message, error.code === "FORMAL_RELEASE_REQUIRED" ? 403 : 400);
    }
    // D1 errors can contain SQL/values. Do not log a recovery capability or key.
    throw backendUnavailable();
  }
}

export function requireFirmwareJsonHeaders(request: Request): void {
  const acceptsJson = request.headers.get("Accept")?.split(",").some((entry) => {
    const [mediaType, ...parameters] = entry.split(";").map((value) => value.trim());
    if (mediaType.toLowerCase() !== "application/json") return false;
    const quality = parameters.filter((value) => /^q\s*=/i.test(value));
    if (quality.length === 0) return true;
    if (quality.length !== 1) return false;
    const match = /^q\s*=\s*(0(?:\.\d{0,3})?|1(?:\.0{0,3})?)$/i.exec(quality[0]);
    return !!match && Number(match[1]) > 0;
  });
  if (new URL(request.url).protocol !== "https:"
    || request.headers.get("Content-Type")?.split(";")[0].trim().toLowerCase() !== "application/json"
    || !acceptsJson) {
    throw invalidParameter("HTTPS, Content-Type and Accept application/json are required");
  }
}

export async function readFirmwareJson(request: Request): Promise<unknown> {
  const reader = request.body?.getReader();
  if (!reader) throw invalidParameter("JSON body is required");
  const chunks: Uint8Array[] = [];
  let length = 0;
  try {
    for (;;) {
      const item = await reader.read();
      if (item.done) break;
      length += item.value.byteLength;
      if (length > 1024 * 1024) throw invalidParameter("Firmware metadata exceeds 1 MiB");
      chunks.push(item.value);
    }
  } finally { await reader.cancel(); }
  const bytes = new Uint8Array(length);
  let offset = 0;
  for (const chunk of chunks) { bytes.set(chunk, offset); offset += chunk.byteLength; }
  try { return JSON.parse(new TextDecoder("utf-8", { fatal: true }).decode(bytes)); }
  catch { throw invalidParameter("Invalid JSON body"); }
}

export function handleFirmwareLatest(request: Request, env: WorkerEnv, requestId: string): Promise<Response> {
  return firmwareOperation(async () => {
    const url = new URL(request.url);
    const get = (name: string) => url.searchParams.get(name)!;
    if (get("deviceModel") !== FIRMWARE_MODEL) throw new ApiError("UNKNOWN_DEVICE_MODEL", "Unknown firmware deviceModel", 400);
    for (const name of url.searchParams.keys()) if (!QUERY.includes(name)) throw invalidParameter("Unsupported latest query parameter");
    for (const name of QUERY) {
      if (url.searchParams.getAll(name).length !== 1 || !get(name)) throw invalidParameter(`${name} must occur exactly once`);
    }
    if (url.protocol !== "https:" || get("appId") !== "trace" || !["stable", "beta"].includes(get("channel"))) {
      throw invalidParameter("Invalid firmware appId/channel or non-HTTPS request");
    }
    const number = (name: string, max: number) => {
      const value = get(name);
      if (!/^[0-9]+$/.test(value) || !Number.isSafeInteger(Number(value)) || Number(value) > max) {
        throw invalidParameter(`${name} is not a valid decimal integer`);
      }
      return Number(value);
    };
    const current = number("currentVersionCode", U32_MAX);
    const appVersion = number("appVersionCode", APP_VERSION_MAX);
    const hardware = number("hardwareRevision", 65535);
    const layout = number("layoutId", 255);
    const boot = number("bootVersion", 255);
    const protocol = number("protocolVersion", 255);
    if (!/^[0-9a-f]{64}$/.test(get("currentImageSha"))) throw invalidParameter("currentImageSha must be a complete lowercase raw SHA-256");
    const rate = await enforceRateLimit(env, `firmware-latest:${clientIpFrom(request)}:trace:${FIRMWARE_MODEL}:${get("channel")}`);
    if (!rate.allowed) return json({ errorCode: "RATE_LIMITED", message: "Too many firmware checks", requestId,
      retryAfter: rate.retryAfter }, 429, { "Retry-After": String(rate.retryAfter) });
    const channel = await env.DB.prepare("SELECT * FROM firmware_channels WHERE app_id=? AND device_model=? AND name=?")
      .bind("trace", FIRMWARE_MODEL, get("channel")).first<FirmwareChannelRow>();
    const noUpdate = (errorCode = "NO_UPDATE") => json({ schemaVersion: 2, requestId, updateAvailable: false, errorCode,
      ...(errorCode === "CHANNEL_STOPPED" ? { maintenanceMessage: channel?.maintenance_message ?? null } : {}) });
    if (channel?.legacy_current_release_id) throw backendUnavailable("Channel references unverified legacy firmware");
    if (channel?.disable_latest === 1) return noUpdate("CHANNEL_STOPPED");
    if (!channel?.current_release_id) return noUpdate();
    const release = await env.DB.prepare("SELECT * FROM firmware_releases WHERE id=?")
      .bind(channel.current_release_id).first<FirmwareReleaseRow>();
    if (!release || release.app_id !== channel.app_id || release.device_model !== channel.device_model
      || release.state !== "ready" || release.archived !== 0) throw backendUnavailable("Invalid firmware channel target");
    if (release.version_code <= current) return noUpdate();
    if (appVersion < release.min_app_version_code) {
      throw new ApiError("CLIENT_TOO_OLD", "App update required", 426, { minAppVersionCode: release.min_app_version_code });
    }
    const compatibility = { releaseId: release.id };
    if (hardware !== release.hardware_rev) throw new ApiError("HARDWARE_INCOMPATIBLE", "Hardware revision mismatch", 409,
      { ...compatibility, requiredHardwareRevision: release.hardware_rev, hardwareRevision: hardware });
    if (layout !== release.layout_id) throw new ApiError("LAYOUT_INCOMPATIBLE", "Layout mismatch", 409,
      { ...compatibility, requiredLayoutId: release.layout_id, layoutId: layout });
    if (boot < release.min_boot_version) throw new ApiError("BOOT_TOO_OLD", "Boot update required", 409,
      { ...compatibility, minBootVersion: release.min_boot_version, bootVersion: boot });
    if (protocol < release.min_protocol_version || protocol !== 1) throw new ApiError("PROTOCOL_UNSUPPORTED", "Unsupported BLE protocol", 409,
      { ...compatibility, minProtocolVersion: release.min_protocol_version, protocolVersion: protocol });
    const assets = await firmwareAssets(env.DB, release.id);
    const full = requireFirmwareFull(release, assets);
    const patches = assets.filter((a) => a.kind === "patch" && a.base_image_sha256 === get("currentImageSha"));
    if (patches.length > 1) throw backendUnavailable("Ambiguous patch base");
    const asset = patches.length === 1 && usableFirmwareAsset(patches[0]) ? patches[0] : full;
    const signed = await signFirmwareDownload(env, url.origin, asset, "public-ota");
    return json({ schemaVersion: 2, requestId, updateAvailable: true, appId: release.app_id,
      deviceModel: release.device_model, channel: channel.name, releaseId: release.id,
      versionName: release.version_name, versionCode: release.version_code, releaseTag: release.release_tag,
      releaseNotes: release.release_notes, targetImageSha256: release.target_image_sha256,
      targetHardware: release.target_hardware, transport: release.transport, minAppVersionCode: release.min_app_version_code,
      asset: { assetId: asset.id, kind: asset.kind, fileName: asset.file_name, sha256: asset.sha256,
        sizeBytes: asset.size_bytes, baseVersionCode: asset.base_vcode,
        baseImageSha256: asset.kind === "patch" ? asset.base_image_sha256 : null, ...signed } });
  });
}

export async function firmwareAssets(db: D1Database, releaseId: string): Promise<FirmwareAssetRow[]> {
  return (await db.prepare("SELECT * FROM firmware_release_assets WHERE release_id=? ORDER BY kind,base_vcode,file_name")
    .bind(releaseId).all<FirmwareAssetRow>()).results;
}

export function usableFirmwareAsset(asset: FirmwareAssetRow): boolean {
  return asset.r2_state === "available" && !!asset.r2_key && !!asset.r2_etag
    && /^[0-9a-f]{64}$/.test(asset.sha256) && Number.isSafeInteger(asset.size_bytes) && asset.size_bytes > 0;
}

export function requireFirmwareFull(release: FirmwareReleaseRow, assets: FirmwareAssetRow[]): FirmwareAssetRow {
  const full = assets.filter((a) => a.kind === "full");
  if (!/^[0-9a-f]{64}$/.test(release.target_image_sha256) || full.length !== 1 || !usableFirmwareAsset(full[0])
    || full[0].base_vcode !== 0 || full[0].base_image_sha256 !== ""
    || assets.some((a) => !["full", "patch", "recovery"].includes(a.kind)
      || (a.kind === "patch" && (!/^[0-9a-f]{64}$/.test(a.base_image_sha256) || a.base_vcode <= 0 || a.base_vcode >= release.version_code)))) {
    throw backendUnavailable("Firmware release lacks a complete verified full fallback");
  }
  return full[0];
}

export function handleFirmwareDownload(request: Request, env: WorkerEnv, requestId: string): Promise<Response> {
  return firmwareOperation(async () => {
    const token = await verifyFirmwareDownload(request, env);
    const asset = await env.DB.prepare("SELECT * FROM firmware_release_assets WHERE id=? AND release_id=?")
      .bind(token.assetId, token.releaseId).first<FirmwareAssetRow>();
    if (!asset) throw new ApiError("ASSET_DISABLED", "Firmware asset unavailable", 410);
    if ((token.kind && token.kind !== asset.kind) || (token.purpose === "admin-recovery") !== (asset.kind === "recovery")) {
      throw new ApiError("TOKEN_INVALID", "Firmware token asset/purpose mismatch", 401);
    }
    const release = await env.DB.prepare("SELECT * FROM firmware_releases WHERE id=?").bind(asset.release_id).first<FirmwareReleaseRow>();
    if (!release || release.state !== "ready") throw new ApiError("ASSET_DISABLED", "Firmware release unavailable", 410);
    if (release.archived || ["archived", "r2_deleted"].includes(asset.r2_state)) throw new ApiError("ASSET_ARCHIVED", "Firmware asset archived", 409);
    const visibility = await env.DB.prepare(`SELECT
      (SELECT disable_all_downloads FROM app_config WHERE app_id=?) AS stopped,
      (SELECT count(*) FROM firmware_channels WHERE current_release_id=?) AS published,
      (SELECT count(*) FROM firmware_channels WHERE current_release_id=? AND disable_downloads=1) AS channel_stopped`)
      .bind(release.app_id, release.id, release.id).first<{ stopped: number; published: number; channel_stopped: number }>();
    if (visibility?.stopped || (token.purpose === "public-ota" && visibility?.channel_stopped)) {
      throw new ApiError("CHANNEL_STOPPED", "Firmware downloads are stopped", 503);
    }
    if (token.purpose === "public-ota" && !visibility?.published) throw new ApiError("ASSET_DISABLED", "Firmware release withdrawn", 410);
    if (!usableFirmwareAsset(asset)) throw backendUnavailable("Firmware R2 asset unavailable");
    return streamFirmwareObject(request, env.RELEASES_BUCKET, asset, requestId);
  });
}

export function handleRegisterFirmwareRelease(request: Request, env: WorkerEnv, requestId: string): Promise<Response> {
  return firmwareOperation(async () => {
    const authorization = request.headers.get("Authorization");
    const token = authorization && /^Bearer [^\s,]+$/.test(authorization) ? authorization.slice(7) : null;
    if (!await verifyBearerToken(token, env.DEPLOY_TOKEN_SHA256)) throw new ApiError("TOKEN_INVALID", "Invalid CI token", 401);
    requireFirmwareJsonHeaders(request);
    const input = parseFirmwareRegistration(await readFirmwareJson(request), `${env.GITHUB_OWNER}/${env.GITHUB_REPO}`);
    const canonical = canonicalJson(input);
    const existing = () => env.DB.prepare("SELECT * FROM firmware_releases WHERE app_id=? AND device_model=? AND release_tag=?")
      .bind(input.appId, input.deviceModel, input.releaseTag).first<FirmwareReleaseRow>();
    const replay = async (row: FirmwareReleaseRow) => {
      if (row.registration_json !== canonical) throw new ApiError("RELEASE_CONFLICT", "Firmware metadata conflicts with registered identity", 409);
      const assets = await firmwareAssets(env.DB, row.id);
      if (row.state !== "ready" || row.archived || assets.length !== input.assets.length || assets.some((a) => !usableFirmwareAsset(a))) {
        throw new ApiError("RELEASE_INCOMPLETE", "Registered firmware is no longer ready/available", 409);
      }
      return json({ ok: true, requestId, releaseId: row.id, state: "ready", idempotent: true, assetsRegistered: assets.length });
    };
    const previous = await existing();
    if (previous && previous.registration_json !== canonical) return replay(previous);
    const verifiedEtags: string[] = [];
    for (const asset of input.assets) verifiedEtags.push(await verifyFirmwareObject(env.RELEASES_BUCKET, asset));
    if (previous) return replay(previous);
    // Do not shadow an unverified legacy tag/version/run with a fresh registration.
    const legacy = await env.DB.prepare(`SELECT id FROM firmware_releases_legacy
      WHERE app_id=? AND device_model=? AND (release_tag=? OR version_code=? OR run_id=?)`)
      .bind(input.appId, input.deviceModel, input.releaseTag, input.versionCode, input.runId).first();
    if (legacy) throw new ApiError("RELEASE_CONFLICT", "Legacy firmware requires approved backfill", 409);
    const releaseId = `fw_${await sha256Hex(`${input.appId}\n${input.deviceModel}\n${input.releaseTag}`)}`;
    const statements: D1PreparedStatement[] = [
      env.DB.prepare("INSERT OR IGNORE INTO apps(id,name) VALUES (?,?)").bind(input.appId, input.appId),
      env.DB.prepare("INSERT OR IGNORE INTO app_config(app_id) VALUES (?)").bind(input.appId),
      firmwareReleaseInsert(env.DB, input, releaseId, canonical)
    ];
    for (let index = 0; index < input.assets.length; index++) {
      const asset = input.assets[index];
      const id = `fw_asset_${await sha256Hex(`${releaseId}\n${asset.kind}\n${asset.baseImageSha256}`)}`;
      statements.push(env.DB.prepare(`INSERT INTO firmware_release_assets
        (id,release_id,kind,file_name,sha256,size_bytes,r2_key,r2_etag,r2_state,github_url,base_image_sha256,base_vcode)
        VALUES (?,?,?,?,?,?,?,?,'available',?,?,?)`).bind(id, releaseId, asset.kind, asset.fileName,
        asset.sha256, asset.sizeBytes, asset.r2Key, verifiedEtags[index], asset.githubUrl, asset.baseImageSha256, asset.baseVersionCode));
    }
    statements.push(env.DB.prepare("UPDATE firmware_releases SET state='ready',updated_at=datetime('now') WHERE id=? AND state='draft'").bind(releaseId));
    for (const channel of ["stable", "beta"]) statements.push(env.DB.prepare(`INSERT OR IGNORE INTO firmware_channels
      (id,app_id,device_model,name) VALUES (?,?,?,?)`).bind(`fw_ch_${input.appId}_${input.deviceModel}_${channel}`, input.appId, input.deviceModel, channel));
    statements.push(env.DB.prepare(`INSERT INTO audit_logs(id,app_id,actor,actor_type,action,target_type,target_id,request_id,after_json)
      VALUES (?,?,'github-actions','ci','register_firmware_release','firmware_release',?,?,?)`)
      .bind(crypto.randomUUID(), input.appId, releaseId, requestId, canonicalJson({ releaseId, state: "ready", assetsRegistered: input.assets.length })));
    try { await env.DB.batch(statements); } catch (error) {
      const concurrent = await existing();
      if (concurrent) return replay(concurrent);
      const conflict = await env.DB.prepare("SELECT id FROM firmware_releases WHERE app_id=? AND device_model=? AND (version_code=? OR run_id=?)")
        .bind(input.appId, input.deviceModel, input.versionCode, input.runId).first();
      if (conflict) throw new ApiError("RELEASE_CONFLICT", "Firmware version/run already registered", 409);
      throw error;
    }
    return json({ ok: true, requestId, releaseId, state: "ready", idempotent: false, assetsRegistered: input.assets.length }, 201);
  });
}

export function firmwareReleaseInsert(db: D1Database, input: FirmwareRegistration, id: string, canonical: string): D1PreparedStatement {
  return db.prepare(`INSERT INTO firmware_releases (id,app_id,device_model,version_name,version_code,release_tag,
    commit_sha,run_id,release_notes,target_image_sha256,hardware_rev,layout_id,min_boot_version,min_protocol_version,
    target_hardware,transport,min_app_version_code,registration_json) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)`)
    .bind(id, input.appId, input.deviceModel, input.versionName, input.versionCode, input.releaseTag, input.commitSha,
      input.runId, input.releaseNotes, input.targetImageSha256, input.hardwareRevision, input.layoutId,
      input.minBootVersion, input.minProtocolVersion, input.targetHardware, input.transport, input.minAppVersionCode, canonical);
}
