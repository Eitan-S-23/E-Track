import { readFile } from "node:fs/promises";
import path from "node:path";
import { pathToFileURL } from "node:url";
import { canonicalJson, parseFirmwareRegistration } from "./firmware-schema.mjs";
import { CliError, failure } from "./firmware-cli.mjs";

export async function registerFirmware(metadata, { serviceUrl, deployToken, fetcher = fetch, retries = 3, timeoutMs = 30000, signal }) {
  if (!serviceUrl || !deployToken) throw new CliError("Service URL and deploy token are required");
  if (/\s/.test(deployToken)) throw new CliError("Deploy token must be one credential without whitespace");
  let url;
  try { url = new URL(serviceUrl); } catch { throw new CliError("Invalid registration origin"); }
  if (url.protocol !== "https:" || url.username || url.password || url.search || url.hash || url.pathname !== "/") throw new CliError("Registration requires a credential-free HTTPS origin");
  if (!Number.isInteger(retries) || retries < 1 || retries > 3 || !Number.isInteger(timeoutMs) || timeoutMs < 1 || timeoutMs > 30000) {
    throw new CliError("Invalid registration retry/timeout bounds");
  }
  const input = parseFirmwareRegistration(metadata);
  const requestId = crypto.randomUUID();
  for (let attempt = 0; attempt < retries; attempt++) {
    if (signal?.aborted) throw new CliError("Registration cancelled", "BACKEND_UNAVAILABLE", 1);
    let response;
    try {
      response = await fetcher(new URL("/api/ci/firmware/releases", url), { method: "POST", redirect: "error",
        signal: signal ? AbortSignal.any([signal, AbortSignal.timeout(timeoutMs)]) : AbortSignal.timeout(timeoutMs), headers: { Authorization: `Bearer ${deployToken}`,
          "Content-Type": "application/json", Accept: "application/json", "X-Request-Id": requestId },
        body: canonicalJson(input) });
    } catch {
      if (signal?.aborted) throw new CliError("Registration cancelled", "BACKEND_UNAVAILABLE", 1);
      if (attempt + 1 < retries) continue;
      throw new CliError("Registration network request failed", "BACKEND_UNAVAILABLE", 1);
    }
    // An HTTP response (including 503/409) is definitive: never blindly retry it.
    if (![200, 201].includes(response.status)) {
      const error = await response.json().catch(() => null);
      const allowed = ["INVALID_PARAMETER", "FORMAL_RELEASE_REQUIRED", "RELEASE_CONFLICT", "RELEASE_INCOMPLETE",
        "TOKEN_INVALID", "TOKEN_EXPIRED", "RATE_LIMITED", "BACKEND_UNAVAILABLE"];
      const code = allowed.includes(error?.errorCode) ? error.errorCode : "BACKEND_UNAVAILABLE";
      throw new CliError(`Registration rejected: HTTP ${response.status}`, code, 1, requestId);
    }
    const result = await response.json();
    if (result.ok !== true || result.state !== "ready" || typeof result.releaseId !== "string" || !result.releaseId
      || result.assetsRegistered !== input.assets.length || typeof result.requestId !== "string"
      || result.requestId !== requestId
      || result.requestId !== response.headers.get("X-Request-Id")
      || result.idempotent !== (response.status === 200)) throw new CliError("Invalid registration result", "BACKEND_UNAVAILABLE", 1);
    return result;
  }
}

async function main() {
  const input = process.argv[2] ?? process.env.TRACE_FIRMWARE_METADATA_JSON;
  if (!input || process.argv.length > 3) throw new CliError("Provide one firmware metadata path");
  const result = await registerFirmware(JSON.parse(await readFile(input, "utf8")), {
    serviceUrl: process.env.TRACE_UPDATE_SERVICE_URL, deployToken: process.env.TRACE_DEPLOY_TOKEN,
    retries: Number(process.env.TRACE_REGISTER_RETRIES ?? "3"), timeoutMs: Number(process.env.TRACE_REGISTER_TIMEOUT_MS ?? "30000")
  });
  process.stdout.write(JSON.stringify(result) + "\n");
}
if (process.argv[1] && import.meta.url === pathToFileURL(path.resolve(process.argv[1])).href) main().catch(failure);
