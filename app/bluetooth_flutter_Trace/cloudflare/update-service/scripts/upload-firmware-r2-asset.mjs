import { createHash } from "node:crypto";
import { readFile } from "node:fs/promises";
import path from "node:path";
import { pathToFileURL } from "node:url";
import { createFirmwareS3Bucket, s3Credentials } from "./firmware-s3.mjs";
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
  } catch { throw mismatch(); }
  finally { await reader.cancel().catch(() => {}); }
  if (size !== asset.sizeBytes || hash.digest("hex") !== asset.sha256) throw mismatch();
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
    // Plain R2 metadata crosses Wrangler's proxy without Node/SDK Headers identity.
    const httpMetadata = {
      contentType: asset.kind === "recovery" ? "application/octet-stream" : "application/vnd.e-track.etu",
      contentDisposition: `attachment; filename="${asset.fileName}"`,
      cacheControl: "public, max-age=31536000, immutable"
    };
    const created = await bucket.put(asset.r2Key, bytes, { onlyIf: { etagDoesNotMatch: "*" },
      httpMetadata, customMetadata: { sha256: asset.sha256, kind: asset.kind,
        "content-digest": contentDigest(asset.sha256) }, sha256: asset.sha256 });
    status = created ? "UPLOADED" : "ALREADY_PRESENT";
    head = await bucket.head(asset.r2Key);
  }
  await readback(bucket, asset, head, status === "UPLOADED");
  return { ok: true, status, requestId, kind: asset.kind, fileName: asset.fileName, r2Key: asset.r2Key,
    sha256: asset.sha256, sizeBytes: asset.sizeBytes, contentDigest: contentDigest(asset.sha256) };
}

export async function withFirmwareBucket({ bucketName, accountId, env = process.env, signal }, operation) {
  const platform = createFirmwareS3Bucket({ bucketName, accountId, credentials: s3Credentials(env), signal });
  try { return await operation(platform.bucket); }
  finally { platform.dispose(); }
}

async function main() {
  const options = args(process.argv.slice(2), ["metadata", "assets-dir", "asset", "bucket", "account-id",
    "output", "remote", "dry-run"], ["remote", "dry-run"]);
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
    accountId: required(options, "account-id", "CLOUDFLARE_ACCOUNT_ID") }, async bucket => {
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
