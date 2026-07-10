import { ApiError } from "./errors";
import type { WorkerEnv } from "./types";

const encoder = new TextEncoder();

export function canonicalJson(value: unknown): string {
  if (Array.isArray(value)) {
    return `[${value.map((item) => canonicalJson(item)).join(",")}]`;
  }
  if (value && typeof value === "object") {
    const entries = Object.entries(value as Record<string, unknown>).sort(([a], [b]) =>
      a.localeCompare(b)
    );
    return `{${entries
      .map(([key, entryValue]) => `${JSON.stringify(key)}:${canonicalJson(entryValue)}`)
      .join(",")}}`;
  }
  return JSON.stringify(value);
}

export async function sha256Hex(input: string): Promise<string> {
  const digest = await crypto.subtle.digest("SHA-256", encoder.encode(input));
  return hex(new Uint8Array(digest));
}

export async function verifyBearerToken(
  providedToken: string | null,
  expectedSha256: string | undefined
): Promise<boolean> {
  if (!providedToken || !expectedSha256) return false;
  const providedHash = await sha256Hex(providedToken);
  return timingSafeEqual(providedHash.toLowerCase(), expectedSha256.toLowerCase());
}

export async function signHmacSha256(message: string, key: string): Promise<string> {
  const cryptoKey = await crypto.subtle.importKey(
    "raw",
    encoder.encode(key),
    { name: "HMAC", hash: "SHA-256" },
    false,
    ["sign"]
  );
  const signature = await crypto.subtle.sign("HMAC", cryptoKey, encoder.encode(message));
  return base64Url(new Uint8Array(signature));
}

export function downloadHmacKey(env: WorkerEnv, keyVersion: string): string {
  if (keyVersion === env.DOWNLOAD_TOKEN_KEY_VERSION) {
    if (env.DOWNLOAD_HMAC_KEY_CURRENT) return env.DOWNLOAD_HMAC_KEY_CURRENT;
    throw new ApiError("BACKEND_UNAVAILABLE", "Current download signing key is not configured", 503);
  }
  if (
    keyVersion === env.DOWNLOAD_TOKEN_PREVIOUS_KEY_VERSION &&
    env.DOWNLOAD_HMAC_KEY_PREVIOUS
  ) {
    return env.DOWNLOAD_HMAC_KEY_PREVIOUS;
  }
  throw new ApiError("TOKEN_INVALID", "Download token key version is invalid", 401);
}

export function timingSafeEqual(a: string, b: string): boolean {
  if (a.length !== b.length) return false;
  let diff = 0;
  for (let i = 0; i < a.length; i += 1) {
    diff |= a.charCodeAt(i) ^ b.charCodeAt(i);
  }
  return diff === 0;
}

function base64Url(bytes: Uint8Array): string {
  let binary = "";
  for (const byte of bytes) {
    binary += String.fromCharCode(byte);
  }
  return btoa(binary).replace(/\+/g, "-").replace(/\//g, "_").replace(/=+$/g, "");
}

function hex(bytes: Uint8Array): string {
  return Array.from(bytes)
    .map((byte) => byte.toString(16).padStart(2, "0"))
    .join("");
}
