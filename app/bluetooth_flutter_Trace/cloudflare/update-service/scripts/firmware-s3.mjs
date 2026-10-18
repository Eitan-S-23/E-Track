import { createRequire } from "node:module";
import { CliError } from "./firmware-cli.mjs";

const require = createRequire(new URL("../worker/package.json", import.meta.url));

export function s3Credentials(env) {
  for (const key of ["TRACE_R2_ACCESS_KEY_ID", "TRACE_R2_SECRET_ACCESS_KEY"]) {
    if (!env[key]) throw new CliError(`Missing release configuration: ${key}`);
  }
  if (!/^[0-9a-f]{32}$/.test(env.TRACE_R2_ACCESS_KEY_ID) || !/^[0-9a-f]{64}$/.test(env.TRACE_R2_SECRET_ACCESS_KEY)) {
    throw new CliError("Invalid R2 S3 credential format");
  }
  if (env.CLOUDFLARE_API_TOKEN) throw new CliError("Control-plane credentials cannot be mixed with the S3 release chain");
  return { accessKeyId: env.TRACE_R2_ACCESS_KEY_ID, secretAccessKey: env.TRACE_R2_SECRET_ACCESS_KEY };
}

// Keep the existing immutable-upload algorithm; adapt only its storage port.
export function createFirmwareS3Bucket({ accountId, bucketName, credentials, signal, client }) {
  if (!/^[0-9a-f]{32}$/.test(accountId) || !/^[a-z0-9][a-z0-9-]{1,61}[a-z0-9]$/.test(bucketName)
    || !credentials?.accessKeyId || !credentials?.secretAccessKey) throw new CliError("Invalid explicit S3 binding");
  const { S3Client, HeadObjectCommand, PutObjectCommand, GetObjectCommand } = require("@aws-sdk/client-s3");
  const owned = !client;
  client ??= new S3Client({ endpoint: `https://${accountId}.r2.cloudflarestorage.com`, region: "auto",
    credentials, maxAttempts: 1, requestChecksumCalculation: "WHEN_REQUIRED", responseChecksumValidation: "WHEN_REQUIRED" });
  const send = (command) => client.send(command, { abortSignal: signal
    ? AbortSignal.any([signal, AbortSignal.timeout(300000)]) : AbortSignal.timeout(300000) });
  const failure = error => new CliError(`R2 S3 request failed${Number.isInteger(error?.$metadata?.httpStatusCode)
    ? `: HTTP ${error.$metadata.httpStatusCode}` : ""}`, "R2_VERIFY_FAILED", 1);
  const bucket = {
    async head(key) {
      try {
        const result = await send(new HeadObjectCommand({ Bucket: bucketName, Key: key }));
        if (!Number.isSafeInteger(result.ContentLength) || !result.ETag) throw new Error();
        return { size: result.ContentLength, etag: result.ETag, customMetadata: result.Metadata ?? {} };
      } catch (error) { if (error?.$metadata?.httpStatusCode === 404) return null; throw failure(error); }
    },
    async put(key, bytes, options) {
      if (options?.onlyIf?.etagDoesNotMatch !== "*") throw new CliError("S3 writes require atomic conditional creation");
      try {
        const result = await send(new PutObjectCommand({ Bucket: bucketName, Key: key, Body: bytes,
          ContentLength: bytes.byteLength, IfNoneMatch: "*", Metadata: options.customMetadata,
          ContentType: options.httpMetadata.contentType, ContentDisposition: options.httpMetadata.contentDisposition,
          CacheControl: options.httpMetadata.cacheControl }));
        return { etag: result.ETag };
      } catch (error) {
        if (error?.$metadata?.httpStatusCode === 412) return null;
        // A 409/network error is not permission to retry without the condition.
        throw failure(error);
      }
    },
    async get(key, options) {
      if (!options?.onlyIf?.etagMatches) throw new CliError("S3 readback requires the observed ETag");
      try {
        const result = await send(new GetObjectCommand({ Bucket: bucketName, Key: key, IfMatch: options.onlyIf.etagMatches }));
        if (result.ETag !== options.onlyIf.etagMatches || !result.Body) {
          result.Body?.destroy?.(); throw new Error();
        }
        return { body: result.Body.transformToWebStream() };
      } catch (error) { throw failure(error); }
    }
  };
  return { bucket, dispose() { if (owned) client.destroy(); } };
}
