import { contentDigest } from "../../scripts/firmware-schema.mjs";
import { signHmacSha256, timingSafeEqual } from "./crypto";
import { ApiError, backendUnavailable, invalidParameter } from "./errors";
import type { FirmwareAssetRow, FirmwareSigningEnv } from "./types";

type Purpose = "public-ota" | "admin-recovery";
type AssetIdentity = Pick<FirmwareAssetRow, "id" | "release_id" | "kind">;
const V2_KEYS = ["tokenVersion", "assetId", "releaseId", "kind", "purpose", "expiresAt", "keyVersion", "signature"];
const V1_KEYS = ["assetId", "releaseId", "expiresAt", "keyVersion", "signature"];

function keyFor(env: FirmwareSigningEnv, version: string): string {
  if (version === env.DOWNLOAD_TOKEN_KEY_VERSION) {
    if (env.DOWNLOAD_HMAC_KEY_CURRENT) return env.DOWNLOAD_HMAC_KEY_CURRENT;
    throw backendUnavailable("Firmware signing key is not configured");
  }
  if (version === env.DOWNLOAD_TOKEN_PREVIOUS_KEY_VERSION && env.DOWNLOAD_HMAC_KEY_PREVIOUS) {
    return env.DOWNLOAD_HMAC_KEY_PREVIOUS;
  }
  throw new ApiError("TOKEN_INVALID", "Unknown signing key version", 401);
}

function cutover(env: FirmwareSigningEnv): number {
  const value = env.FIRMWARE_V2_CUTOVER_EPOCH;
  if (!value || !/^(0|[1-9][0-9]*)$/.test(value) || !Number.isSafeInteger(Number(value))) {
    throw backendUnavailable("Auditable firmware v2 cutover epoch is not configured");
  }
  return Number(value);
}

export function firmwareTokenMessage(asset: AssetIdentity, purpose: Purpose, expiresAt: number, keyVersion: string): string {
  return ["2", "GET", asset.id, asset.release_id, asset.kind, purpose, String(expiresAt), keyVersion].join("\n");
}

export async function signFirmwareDownload(
  env: FirmwareSigningEnv, origin: string, asset: AssetIdentity, purpose: Purpose,
  now = Math.floor(Date.now() / 1000)
): Promise<{ downloadUrl: string; expiresAt: number }> {
  cutover(env);
  if ((purpose === "admin-recovery") !== (asset.kind === "recovery")) {
    throw new ApiError("TOKEN_INVALID", "Asset purpose mismatch", 401);
  }
  const url = new URL(origin);
  if (url.protocol !== "https:" || url.username || url.password) throw backendUnavailable("Firmware download origin must use HTTPS");
  const expiresAt = now + 300;
  const keyVersion = env.DOWNLOAD_TOKEN_KEY_VERSION;
  if (!/^[A-Za-z0-9._-]+$/.test(keyVersion)) throw backendUnavailable("Invalid signing key version");
  const signature = await signHmacSha256(firmwareTokenMessage(asset, purpose, expiresAt, keyVersion), keyFor(env, keyVersion));
  const query = new URLSearchParams({ tokenVersion: "2", assetId: asset.id, releaseId: asset.release_id,
    kind: asset.kind, purpose, expiresAt: String(expiresAt), keyVersion, signature });
  return { downloadUrl: `${url.origin}/api/public/firmware/download?${query}`, expiresAt };
}

export async function verifyFirmwareDownload(request: Request, env: FirmwareSigningEnv): Promise<{
  assetId: string; releaseId: string; kind?: FirmwareAssetRow["kind"]; purpose: Purpose;
}> {
  const url = new URL(request.url);
  const v2 = url.searchParams.has("tokenVersion");
  const keys = v2 ? V2_KEYS : V1_KEYS;
  const invalid = () => new ApiError("TOKEN_INVALID", "Invalid firmware download token", 401);
  if (request.method !== "GET" || url.protocol !== "https:") throw invalid();
  for (const key of url.searchParams.keys()) if (!keys.includes(key)) throw invalid();
  for (const key of keys) if (url.searchParams.getAll(key).length !== 1 || !url.searchParams.get(key)) throw invalid();
  const get = (key: string) => url.searchParams.get(key)!;
  if (!/^(0|[1-9][0-9]*)$/.test(get("expiresAt"))) throw invalid();
  const expiresAt = Number(get("expiresAt"));
  const now = Math.floor(Date.now() / 1000);
  if (!Number.isSafeInteger(expiresAt) || !/^[A-Za-z0-9_-]{43}$/.test(get("signature"))) throw invalid();
  for (const key of ["assetId", "releaseId", "keyVersion"]) {
    if (!/^[A-Za-z0-9._-]+$/.test(get(key))) throw invalid();
  }
  let message: string;
  let kind: FirmwareAssetRow["kind"] | undefined;
  let purpose: Purpose = "public-ota";
  if (v2) {
    if (get("tokenVersion") !== "2" || !["full", "patch", "recovery"].includes(get("kind"))
      || !["public-ota", "admin-recovery"].includes(get("purpose"))) throw invalid();
    kind = get("kind") as FirmwareAssetRow["kind"];
    purpose = get("purpose") as Purpose;
    if ((kind === "recovery") !== (purpose === "admin-recovery")) throw invalid();
    message = firmwareTokenMessage({ id: get("assetId"), release_id: get("releaseId"), kind }, purpose, expiresAt, get("keyVersion"));
  } else {
    const end = cutover(env) + 300;
    if (expiresAt > end) throw invalid();
    message = ["GET", get("assetId"), get("releaseId"), String(expiresAt), get("keyVersion")].join("\n");
  }
  const signature = await signHmacSha256(message, keyFor(env, get("keyVersion")));
  if (!timingSafeEqual(signature, get("signature"))) throw invalid();
  if (now >= expiresAt) throw new ApiError("TOKEN_EXPIRED", "Firmware download token expired", 401);
  if (v2 && expiresAt > now + 300) throw invalid();
  return { assetId: get("assetId"), releaseId: get("releaseId"), kind, purpose };
}

export async function verifyFirmwareObject(bucket: R2Bucket, asset: {
  r2Key: string; sha256: string; sizeBytes: number; kind: FirmwareAssetRow["kind"];
}): Promise<string> {
  const head = await bucket.head(asset.r2Key);
  if (!head || head.size !== asset.sizeBytes || head.customMetadata?.sha256 !== asset.sha256
    || head.customMetadata?.kind !== asset.kind) throw new Error("R2 metadata mismatch");
  const object = await bucket.get(asset.r2Key, { onlyIf: { etagMatches: head.etag } });
  if (!object || !("body" in object) || object.size !== asset.sizeBytes) throw new Error("R2 object changed or missing");
  // lib.webworker's Crypto omits Cloudflare's documented DigestStream extension.
  const hash = new (crypto as Crypto & { DigestStream: typeof DigestStream }).DigestStream("SHA-256");
  let bytes = 0;
  const counter = new TransformStream<Uint8Array, Uint8Array>({
    transform(chunk, controller) {
      bytes += chunk.byteLength;
      if (bytes > asset.sizeBytes) throw new Error("R2 body exceeds registered size");
      controller.enqueue(chunk);
    }
  });
  const [, rawDigest] = await Promise.all([object.body.pipeThrough(counter).pipeTo(hash), hash.digest]);
  const digest = Array.from(new Uint8Array(rawDigest), (byte) => byte.toString(16).padStart(2, "0")).join("");
  if (bytes !== asset.sizeBytes || digest !== asset.sha256) throw new Error("R2 readback mismatch");
  return object.httpEtag;
}

export async function streamFirmwareObject(request: Request, bucket: R2Bucket, asset: FirmwareAssetRow, requestId: string): Promise<Response> {
  // R2 conditions use raw entity tags; stored identity and HTTP headers stay quoted.
  const etag = asset.r2_etag?.match(/^"([\x21\x23-\x7e\x80-\xff]+)"$/)?.[1];
  if (!asset.r2_key || !etag) throw backendUnavailable("Firmware asset lacks verified R2 identity");
  const rawRange = request.headers.get("Range");
  let offset: number | undefined;
  if (rawRange !== null) {
    if (!/^bytes=[0-9]+-$/.test(rawRange)) throw invalidParameter("Only Range: bytes=N- is supported");
    offset = Number(rawRange.slice(6, -1));
    if (!Number.isSafeInteger(offset)) throw invalidParameter("Invalid Range boundary");
    if (offset >= asset.size_bytes) return new Response(null, { status: 416, headers: {
      "Content-Range": `bytes */${asset.size_bytes}`, "X-Request-Id": requestId, "Cache-Control": "no-store" } });
    if (request.headers.has("If-Range") && request.headers.get("If-Range") !== asset.r2_etag) offset = undefined;
  }
  const object = await bucket.get(asset.r2_key, { onlyIf: { etagMatches: etag },
    ...(offset === undefined ? {} : { range: { offset } }) });
  if (!object || !("body" in object) || object.size !== asset.size_bytes || object.httpEtag !== asset.r2_etag
    || (object.customMetadata?.sha256 && object.customMetadata.sha256 !== asset.sha256)
    || (object.customMetadata?.kind && object.customMetadata.kind !== asset.kind)) {
    throw backendUnavailable("Firmware R2 identity changed or unavailable");
  }
  const headers = new Headers({
    "Content-Type": asset.kind === "recovery" ? "application/octet-stream" : "application/vnd.e-track.etu",
    "Content-Length": String(asset.size_bytes - (offset ?? 0)), "Accept-Ranges": "bytes", "ETag": object.httpEtag,
    "Content-Disposition": `attachment; filename="${asset.file_name.replace(/["\\\x00-\x1f\x7f]/g, "_")}"`,
    "Cache-Control": "public, max-age=31536000, immutable", "X-Request-Id": requestId,
    "X-Trace-Asset-Type": "firmware", "X-Trace-Asset-Source": "r2"
  });
  if (offset === undefined) headers.set("Content-Digest", contentDigest(asset.sha256));
  else headers.set("Content-Range", `bytes ${offset}-${asset.size_bytes - 1}/${asset.size_bytes}`);
  return new Response(object.body, { status: offset === undefined ? 200 : 206, headers });
}
