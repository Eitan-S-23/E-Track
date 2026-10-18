import assert from "node:assert/strict";
import { createHash } from "node:crypto";
import { createServer } from "node:http";
import { readFile } from "node:fs/promises";
import { createRequire } from "node:module";
import { test } from "node:test";
import { createFirmwareS3Bucket, s3Credentials } from "../../app/bluetooth_flutter_Trace/cloudflare/update-service/scripts/firmware-s3.mjs";
import { uploadFirmwareAsset } from "../../app/bluetooth_flutter_Trace/cloudflare/update-service/scripts/upload-firmware-r2-asset.mjs";

const require = createRequire(new URL("../../app/bluetooth_flutter_Trace/cloudflare/update-service/worker/package.json", import.meta.url));
const { S3Client } = require("@aws-sdk/client-s3");
const metadata = JSON.parse(await readFile(new URL("../../app/bluetooth_flutter_Trace/cloudflare/update-service/worker/test/fixtures/firmware-release-v2.json", import.meta.url)));
const credentials = { accessKeyId: "a".repeat(32), secretAccessKey: "b".repeat(64) };
const bytesFor = kind => Buffer.from(`P4-2-${kind}-fixture\n`);

async function fixture(t) {
  const objects = new Map(), requests = [];
  const state = { corrupt: "", deny: false, race: false, failPut: 0, putCount: 0, heldHeads: [] };
  const server = createServer(async (req, res) => {
    const chunks = []; for await (const chunk of req) chunks.push(chunk);
    const body = Buffer.concat(chunks), key = decodeURIComponent(new URL(req.url, "http://localhost").pathname);
    requests.push({ method: req.method, key, headers: req.headers });
    if (state.deny) { res.writeHead(403); res.end("<Error><Code>AccessDenied</Code></Error>"); return; }
    const object = objects.get(key);
    if (req.method === "HEAD") {
      const reply = () => { res.writeHead(object ? 200 : 404, object ? object.headers : {}); res.end(); };
      if (state.race && !object) { state.heldHeads.push(reply); if (state.heldHeads.length === 2) state.heldHeads.splice(0).forEach(f => f()); }
      else reply();
    } else if (req.method === "PUT") {
      state.putCount++;
      if (req.headers["if-none-match"] !== "*") { res.writeHead(400); res.end(); return; }
      if (state.failPut) { res.writeHead(state.failPut); res.end("<Error><Code>ConditionalRequestConflict</Code></Error>"); return; }
      if (objects.has(key)) { res.writeHead(412); res.end("<Error><Code>PreconditionFailed</Code></Error>"); return; }
      const etag = `"${createHash("md5").update(body).digest("hex")}"`;
      const headers = { "content-length": String(body.length), etag,
        ...Object.fromEntries(Object.entries(req.headers).filter(([k]) => k.startsWith("x-amz-meta-") || ["content-type", "content-disposition", "cache-control"].includes(k))) };
      objects.set(key, { body, headers }); res.writeHead(200, { etag }); res.end();
    } else if (req.method === "GET") {
      if (!object) { res.writeHead(404); res.end(); return; }
      if (req.headers["if-match"] !== object.headers.etag) { res.writeHead(412); res.end(); return; }
      let bytes = object.body;
      if (state.corrupt === "digest") { bytes = Buffer.from(bytes); bytes[0] ^= 1; }
      if (state.corrupt === "short") bytes = bytes.subarray(0, -1);
      if (state.corrupt === "long") bytes = Buffer.concat([bytes, Buffer.from([0])]);
      const headers = { ...object.headers, "content-length": String(bytes.length) };
      if (state.corrupt === "etag") headers.etag = '"different"';
      res.writeHead(200, headers); res.end(bytes);
    } else { res.writeHead(405); res.end(); }
  });
  await new Promise(resolve => server.listen(0, "127.0.0.1", resolve));
  const client = new S3Client({ endpoint: `http://127.0.0.1:${server.address().port}`, region: "auto", forcePathStyle: true,
    credentials, maxAttempts: 1, requestChecksumCalculation: "WHEN_REQUIRED", responseChecksumValidation: "WHEN_REQUIRED" });
  const { bucket } = createFirmwareS3Bucket({ accountId: "c".repeat(32), bucketName: "e-track-firmware-production-releases", credentials, client });
  t.after(async () => { client.destroy(); server.closeAllConnections(); await new Promise(resolve => server.close(resolve)); });
  return { objects, requests, state, bucket };
}

for (const kind of ["full", "patch", "recovery"]) test(`actual S3 SDK serializes/signs immutable ${kind} creation and full replay`, async t => {
  const f = await fixture(t), asset = metadata.assets.find(a => a.kind === kind);
  assert.equal((await uploadFirmwareAsset(metadata, asset.fileName, bytesFor(kind), f.bucket)).status, "UPLOADED");
  assert.equal((await uploadFirmwareAsset(metadata, asset.fileName, bytesFor(kind), f.bucket)).status, "ALREADY_PRESENT");
  assert.equal(f.state.putCount, 1);
  const put = f.requests.find(r => r.method === "PUT");
  assert.match(put.headers.authorization, /^AWS4-HMAC-SHA256 /);
  assert.match(put.headers.authorization, /SignedHeaders=[^,]*if-none-match/);
  assert.equal(put.headers["if-none-match"], "*");
  assert.equal(put.headers["x-amz-meta-sha256"], asset.sha256);
  assert.equal(put.headers["x-amz-meta-kind"], kind);
  assert.equal(put.headers["content-length"], String(asset.sizeBytes));
  assert.equal(put.headers["cache-control"], "public, max-age=31536000, immutable");
  assert.equal(put.headers["content-disposition"], `attachment; filename="${asset.fileName}"`);
  assert.equal(f.requests.filter(r => r.method === "GET").length, 2);
});

test("two simultaneous SDK writers create once and validate the winner", async t => {
  const f = await fixture(t); f.state.race = true;
  const asset = metadata.assets[0];
  const results = await Promise.all([1, 2].map(() => uploadFirmwareAsset(metadata, asset.fileName, bytesFor(asset.kind), f.bucket)));
  assert.deepEqual(results.map(r => r.status).sort(), ["ALREADY_PRESENT", "UPLOADED"]);
  assert.equal(f.objects.size, 1); assert.equal(f.state.putCount, 2);
});

test("different bytes at one key never overwrite through the SDK", async t => {
  const f = await fixture(t), asset = metadata.assets[0];
  await uploadFirmwareAsset(metadata, asset.fileName, bytesFor(asset.kind), f.bucket);
  const other = structuredClone(metadata), bytes = Buffer.from(bytesFor(asset.kind)); bytes[0] ^= 1;
  other.assets[0].sha256 = createHash("sha256").update(bytes).digest("hex");
  await assert.rejects(uploadFirmwareAsset(other, asset.fileName, bytes, f.bucket), { code: "R2_OBJECT_CONFLICT" });
  assert.equal(f.state.putCount, 1);
});

for (const corrupt of ["digest", "short", "long", "etag"]) test(`SDK ${corrupt} readback fails closed`, async t => {
  const f = await fixture(t); f.state.corrupt = corrupt;
  const asset = metadata.assets[0];
  await assert.rejects(uploadFirmwareAsset(metadata, asset.fileName, bytesFor(asset.kind), f.bucket), { code: "R2_VERIFY_FAILED" });
});

test("SDK access rejection leaks neither credentials nor upstream response", async t => {
  const f = await fixture(t); f.state.deny = true;
  const asset = metadata.assets[0];
  await assert.rejects(uploadFirmwareAsset(metadata, asset.fileName, bytesFor(asset.kind), f.bucket), error => {
    assert.match(error.message, /HTTP 403/);
    assert.ok(!error.message.includes(credentials.secretAccessKey) && !error.message.includes("AccessDenied")); return true;
  });
  assert.equal(f.state.putCount, 0);
});

test("SDK 409 does not downgrade to unconditional creation or blind retry", async t => {
  const f = await fixture(t); f.state.failPut = 409;
  const asset = metadata.assets[0];
  await assert.rejects(uploadFirmwareAsset(metadata, asset.fileName, bytesFor(asset.kind), f.bucket), { code: "R2_VERIFY_FAILED" });
  assert.equal(f.state.putCount, 1); assert.equal(f.objects.size, 0);
});

test("no credential fallback or mixed control-plane credentials", () => {
  assert.throws(() => s3Credentials({}), /Missing release configuration: TRACE_R2_ACCESS_KEY_ID/);
  assert.throws(() => s3Credentials({ TRACE_R2_ACCESS_KEY_ID: credentials.accessKeyId }), /TRACE_R2_SECRET_ACCESS_KEY/);
  assert.throws(() => s3Credentials({ TRACE_R2_ACCESS_KEY_ID: credentials.accessKeyId,
    TRACE_R2_SECRET_ACCESS_KEY: credentials.secretAccessKey, CLOUDFLARE_API_TOKEN: "unused-control-plane" }), /cannot be mixed/);
});
