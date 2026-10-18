import { createHash } from "node:crypto";
import { canonicalJson, parseFirmwareRegistration } from "./firmware-schema.mjs";
import { CliError } from "./firmware-cli.mjs";

export async function preflightFirmware(metadata, { serviceUrl, deployToken, mode, fetcher = fetch, signal }) {
  const input = parseFirmwareRegistration(metadata, undefined, false);
  let origin;
  try { origin = new URL(serviceUrl); } catch { throw new CliError("Invalid preflight origin"); }
  if (origin.protocol !== "https:" || origin.username || origin.password || origin.search || origin.hash || origin.pathname !== "/"
    || !deployToken || /\s/.test(deployToken) || !["production", "rehearsal"].includes(mode)) throw new CliError("Invalid preflight configuration");
  const environment = mode === "production" ? "prod" : "staging";
  const projected = { ...input, assets: input.assets.map(asset => ({ ...asset, r2Verified: true })) };
  const metadataSha256 = createHash("sha256").update(canonicalJson(projected) + "\n").digest("hex");
  const requestId = crypto.randomUUID();
  let response;
  try {
    response = await fetcher(new URL("/api/ci/firmware/preflight", origin), { method: "POST", redirect: "error",
      headers: { Authorization: `Bearer ${deployToken}`, Accept: "application/json", "Content-Type": "application/json", "X-Request-Id": requestId },
      signal: signal ? AbortSignal.any([signal, AbortSignal.timeout(20000)]) : AbortSignal.timeout(20000),
      body: canonicalJson({ schemaVersion: 1, environment, metadata: projected }) });
  } catch { throw new CliError("Preflight network request failed", "BACKEND_UNAVAILABLE", 1); }
  // Never echo an upstream error body or trust unbounded diagnostics.
  if (!response.ok) {
    await response.body?.cancel();
    throw new CliError(`Preflight rejected: HTTP ${response.status}`, response.status === 409 ? "RELEASE_CONFLICT"
      : response.status === 401 ? "TOKEN_INVALID" : "BACKEND_UNAVAILABLE", 1, requestId);
  }
  let result;
  try {
    if (!response.body) throw new Error();
    const reader = response.body.getReader(); const chunks = []; let size = 0;
    try {
      for (;;) { const item = await reader.read(); if (item.done) break;
        size += item.value.length; if (size > 32768) throw new Error(); chunks.push(item.value); }
    } finally { await reader.cancel(); }
    result = JSON.parse(Buffer.concat(chunks));
  } catch { throw new CliError("Invalid preflight response", "BACKEND_UNAVAILABLE", 1, requestId); }
  if (response.status !== 200 || result.ok !== true || result.schemaVersion !== 1 || result.environment !== environment
    || result.requestId !== requestId || response.headers.get("X-Request-Id") !== requestId || result.metadataSha256 !== metadataSha256
    || result.unresolvedLegacyChannels !== 0
    || ![result.maxVersionCode, result.legacyMaxVersionCode].every(value => value === null || (Number.isSafeInteger(value) && value >= 0))
    || (result.maxVersionCode !== null && result.maxVersionCode > input.versionCode)
    || (result.legacyMaxVersionCode !== null && result.legacyMaxVersionCode >= input.versionCode)) {
    throw new CliError("Invalid preflight identity or version result", "RELEASE_CONFLICT", 1, requestId);
  }
  return result;
}
