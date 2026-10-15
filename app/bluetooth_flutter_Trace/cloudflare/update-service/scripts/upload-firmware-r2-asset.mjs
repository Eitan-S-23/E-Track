import { createHash } from "node:crypto";
import { readFile, mkdir } from "node:fs/promises";
import { createRequire } from "node:module";
import { release as osRelease } from "node:os";
import path from "node:path";
import { fileURLToPath, pathToFileURL } from "node:url";
import { canonicalJson, contentDigest, parseFirmwareRegistration } from "./firmware-schema.mjs";
import { args, CliError, failure, outputPath, projectRoot, required, writeOutput } from "./firmware-cli.mjs";

const sha = (bytes) => createHash("sha256").update(bytes).digest("hex");
function conflict() { return new CliError("Existing R2 object has different byte identity", "R2_OBJECT_CONFLICT", 1); }
async function readback(bucket, asset, head, uploaded) {
  const mismatch = () => uploaded ? new CliError("R2 put readback mismatch", "R2_VERIFY_FAILED", 1) : conflict();
  if (!head || head.size !== asset.sizeBytes || head.customMetadata?.sha256 !== asset.sha256
    || head.customMetadata?.kind !== asset.kind) throw mismatch();
  const object = await bucket.get(asset.r2Key, { onlyIf: { etagMatches: head.etag } });
  if (!object || !("body" in object)) throw new CliError("R2 readback unavailable", "R2_VERIFY_FAILED", 1);
  const hash = createHash("sha256");
  let size = 0;
  const reader = object.body.getReader();
  try {
    for (;;) {
      const part = await reader.read();
      if (part.done) break;
      size += part.value.byteLength;
      if (size > asset.sizeBytes) throw mismatch();
      hash.update(part.value);
    }
  } finally { await reader.cancel(); }
  if (size !== asset.sizeBytes || hash.digest("hex") !== asset.sha256) throw mismatch();
}

export function assertFirmwareRuntime(platform = process.platform, release = osRelease()) {
  if (platform !== "win32") return;
  const version = /^(\d+)\.(\d+)\.(\d+)(?:\.\d+)?$/.exec(release);
  // Windows 11 still reports kernel major 10. Wrangler requires build 22000+.
  if (!version || Number(version[1]) < 10 || (Number(version[1]) === 10 && Number(version[3]) < 22000)) {
    throw new CliError("Wrangler firmware bindings require Windows 11 or a supported Linux CI host; use the protected check_bindings dispatch instead of retrying this host");
  }
}

export async function verifyStoredFirmwareAsset(metadata, fileName, bucket) {
  const parsed = parseFirmwareRegistration(metadata, undefined, false);
  const asset = parsed.assets.find(a => a.fileName === fileName);
  if (!asset) throw new CliError("Readback must select one metadata asset");
  const head = await bucket.head(asset.r2Key);
  if (!head) throw new CliError("Required existing R2 object is absent; read-only checks never upload it", "R2_VERIFY_FAILED", 1);
  await readback(bucket, asset, head, false);
  return { ok: true, kind: asset.kind, fileName: asset.fileName, r2Key: asset.r2Key,
    sha256: asset.sha256, sizeBytes: asset.sizeBytes, contentDigest: contentDigest(asset.sha256) };
}

export async function uploadFirmwareAsset(metadata, fileName, bytes, bucket, requestId = crypto.randomUUID()) {
  const parsed = parseFirmwareRegistration(metadata, undefined, false);
  const asset = parsed.assets.find((a) => a.fileName === fileName);
  if (!asset || bytes.byteLength !== asset.sizeBytes || sha(bytes) !== asset.sha256) {
    throw new CliError("Local asset does not match metadata", "INVALID_PARAMETER", 1);
  }
  let head = await bucket.head(asset.r2Key);
  let status = "ALREADY_PRESENT";
  if (!head) {
    const headers = new Headers({
      "Content-Type": asset.kind === "recovery" ? "application/octet-stream" : "application/vnd.e-track.etu",
      "Content-Length": String(asset.sizeBytes), "Content-Digest": contentDigest(asset.sha256),
      "Content-Disposition": `attachment; filename="${asset.fileName}"`,
      "Cache-Control": "public, max-age=31536000, immutable"
    });
    const created = await bucket.put(asset.r2Key, bytes, { onlyIf: { etagDoesNotMatch: "*" },
      httpMetadata: headers, customMetadata: { sha256: asset.sha256, kind: asset.kind,
        "content-digest": contentDigest(asset.sha256) }, sha256: asset.sha256 });
    status = created ? "UPLOADED" : "ALREADY_PRESENT";
    head = await bucket.head(asset.r2Key);
  }
  await readback(bucket, asset, head, status === "UPLOADED");
  return { ok: true, status, requestId, kind: asset.kind, fileName: asset.fileName, r2Key: asset.r2Key,
    sha256: asset.sha256, sizeBytes: asset.sizeBytes, contentDigest: contentDigest(asset.sha256) };
}

export async function withFirmwareBucket({ bucketName, accountId, root = projectRoot(), wranglerCwd, databaseId, databaseName }, operation) {
  // Never fall back to an interactive or cached developer OAuth identity.
  required({}, "api-token", "CLOUDFLARE_API_TOKEN");
  if (!/^[0-9a-f]{32}$/.test(accountId) || !/^[a-z0-9][a-z0-9-]{1,61}[a-z0-9]$/.test(bucketName)) throw new CliError("Invalid account/bucket configuration");
  if ((databaseId || databaseName) && (!/^[0-9a-f]{8}(-[0-9a-f]{4}){3}-[0-9a-f]{12}$/.test(databaseId ?? "")
    || !/^[a-zA-Z0-9_-]+$/.test(databaseName ?? ""))) throw new CliError("Invalid explicit D1 binding");
  assertFirmwareRuntime();
  const temp = outputPath(root, path.join(root, ".cache", "firmware-uploader", crypto.randomUUID()));
  const configPath = outputPath(root, path.join(temp, "wrangler.json"));
  const controls = { TEMP: "tmp", TMP: "tmp", TMPDIR: "tmp", HOME: "home", USERPROFILE: "home",
    APPDATA: "appdata", LOCALAPPDATA: "localappdata", XDG_CACHE_HOME: "cache", XDG_CONFIG_HOME: "config", WRANGLER_LOG_PATH: "logs" };
  for (const dir of Object.values(controls)) outputPath(root, path.join(temp, dir));
  for (const [key, dir] of Object.entries(controls)) {
    await mkdir(path.join(temp, dir), { recursive: true });
    process.env[key] = path.join(temp, dir);
  }
  process.env.WRANGLER_SEND_METRICS = "false";
  process.env.WRANGLER_LOG = "none";
  await writeOutput(root, configPath, JSON.stringify({ name: "trace-firmware-uploader", account_id: accountId,
    compatibility_date: "2026-06-28", compatibility_flags: ["nodejs_compat"],
    r2_buckets: [{ binding: "ASSET_BUCKET", bucket_name: bucketName, remote: true }],
    ...(databaseId ? { d1_databases: [{ binding: "RELEASE_DB", database_id: databaseId, database_name: databaseName, remote: true }] } : {}) }));
  const cwd = path.resolve(wranglerCwd ?? fileURLToPath(new URL("../worker/", import.meta.url)));
  const require = createRequire(path.join(cwd, "package.json"));
  const { getPlatformProxy } = await import(pathToFileURL(require.resolve("wrangler")).href);
  const platform = await getPlatformProxy({ configPath, envFiles: [], persist: false, remoteBindings: true });
  try { return await operation(platform.env.ASSET_BUCKET, platform.env.RELEASE_DB); }
  finally { await platform.dispose(); }
}

async function main() {
  const options = args(process.argv.slice(2), ["metadata", "assets-dir", "asset", "bucket", "account-id",
    "wrangler-cwd", "output", "remote", "dry-run"], ["remote", "dry-run"]);
  const metadataPath = path.resolve(required(options, "metadata", "TRACE_FIRMWARE_METADATA_JSON"));
  const assetsDir = path.resolve(required(options, "assets-dir", "TRACE_FIRMWARE_ASSETS_DIR"));
  const fileName = required(options, "asset");
  const metadata = parseFirmwareRegistration(JSON.parse(await readFile(metadataPath, "utf8")), undefined, false);
  if (!metadata.assets.some((a) => a.fileName === fileName)) throw new CliError("--asset must select one metadata array item");
  const bytesByName = new Map();
  for (const asset of metadata.assets) {
    const bytes = await readFile(path.join(assetsDir, asset.fileName));
    if (bytes.length !== asset.sizeBytes || sha(bytes) !== asset.sha256) throw new CliError("Local asset mismatch", "INVALID_PARAMETER", 1);
    bytesByName.set(asset.fileName, bytes);
  }
  if (options["dry-run"]) {
    process.stdout.write(JSON.stringify({ ok: true, dryRun: true, verified: false, fileName }) + "\n");
    return;
  }
  if (!options.remote) throw new CliError("Explicit --remote and separately authorized target are required");
  const root = projectRoot();
  const output = outputPath(root, options.output ?? metadataPath);
  await withFirmwareBucket({ root, bucketName: required(options, "bucket", "TRACE_R2_BUCKET"),
    accountId: required(options, "account-id", "CLOUDFLARE_ACCOUNT_ID"), wranglerCwd: options["wrangler-cwd"] }, async bucket => {
    let timeout;
    const result = await Promise.race([
      uploadFirmwareAsset(metadata, fileName, bytesByName.get(fileName), bucket),
      new Promise((_, reject) => { timeout = setTimeout(() => reject(new CliError("R2 verification timed out", "R2_VERIFY_FAILED", 1)), 300000); })
    ]).finally(() => clearTimeout(timeout));
    metadata.assets.find((a) => a.fileName === fileName).r2Verified = true;
    await writeOutput(root, output, canonicalJson(metadata) + "\n");
    process.stdout.write(JSON.stringify(result) + "\n");
  });
}
if (process.argv[1] && import.meta.url === pathToFileURL(path.resolve(process.argv[1])).href) main().catch(failure);
