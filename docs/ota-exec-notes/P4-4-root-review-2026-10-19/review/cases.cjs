(async () => {
  const fs = require("node:fs");
  const path = require("node:path");
  const crypto = require("node:crypto");
  const assert = require("node:assert/strict");
  const { pathToFileURL } = require("node:url");
  const { execFileSync } = require("node:child_process");
  const root = "D:/github/my/E-Track/.cache/p4-4-integration-20261018";
  const sha = "546d8b39a5697ba1b018720b120608de52a511d2";
  const scripts = "app/bluetooth_flutter_Trace/cloudflare/update-service/scripts/";
  const load = p => import(pathToFileURL(path.join(root, p)).href);
  const { checkFirmwareBindings } = await load(".github/scripts/firmware-bindings-check.mjs");
  const { verifyMonotonic } = await load(scripts + "firmware-monotonic.mjs");
  const { canonicalJson } = await load(scripts + "firmware-schema.mjs");
  const { verifyStoredFirmwareAsset } = await load(scripts + "upload-firmware-r2-asset.mjs");
  const fixtureDir = "docs/ota-exec-notes/P4-1-r2-registration-qualification-2026-10-15";
  const metadata = JSON.parse(fs.readFileSync(path.join(root, fixtureDir, "operations/verified-metadata.json"), "utf8"));
  const bytes = a => fs.readFileSync(path.join(root, fixtureDir, "fixture", a.fileName));
  const env = {
    GITHUB_EVENT_NAME: "workflow_dispatch", INPUT_CHECK_BINDINGS: "true", INPUT_PUBLISH: "false",
    INPUT_REHEARSAL: "false", OTA_BOOT_CHAIN_READY: "false", GITHUB_REPOSITORY: "Eitan-S-23/E-Track",
    GITHUB_SHA: sha, FIRMWARE_REHEARSAL_BINDINGS_CHECK_COMMIT: sha, GITHUB_RUN_ID: "1", GITHUB_RUN_ATTEMPT: "1",
    CLOUDFLARE_ACCOUNT_ID: "a".repeat(32), TRACE_R2_ACCESS_KEY_ID: "b".repeat(32),
    TRACE_R2_SECRET_ACCESS_KEY: "c".repeat(64), TRACE_DEPLOY_TOKEN: "synthetic-not-a-credential",
    TRACE_UPDATE_SERVICE_URL: "https://e-track-firmware-p41-test.tangjichentudou.workers.dev",
    TRACE_R2_BUCKET: "e-track-firmware-p41-test-releases"
  };
  async function qualification(currentVersion) {
    const observed = { currentVersion, posts: 0, queries: 0, connects: 0, reads: 0 };
    const db = { prepare(sql) {
      observed.queries++;
      assert.match(sql, /^SELECT /);
      let row;
      if (sql.startsWith("SELECT COUNT")) row = { count: 0 };
      else if (sql.startsWith("SELECT MAX")) row = { version_code: null };
      else row = currentVersion === null ? null : { version_code: currentVersion, registration_json: "{}" };
      return { bind() { return { async first() { return row; } }; } };
    } };
    const fetcher = async (url, init) => {
      observed.posts++;
      assert.equal(new URL(url).pathname, "/api/ci/firmware/preflight");
      const body = JSON.parse(init.body);
      try {
        const result = await verifyMonotonic(db, body.metadata);
        const digest = crypto.createHash("sha256").update(canonicalJson(body.metadata) + "\n").digest("hex");
        return Response.json({ ok: true, schemaVersion: 1, environment: "staging",
          requestId: init.headers["X-Request-Id"], metadataSha256: digest, ...result },
          { headers: { "X-Request-Id": init.headers["X-Request-Id"] } });
      } catch (e) {
        assert.equal(e.code, "RELEASE_CONFLICT");
        return Response.json({ errorCode: e.code }, { status: 409 });
      }
    };
    const connect = async (config, operation) => {
      observed.connects++;
      return operation({
        async head(key) { const a = metadata.assets.find(v => v.r2Key === key);
          return { size: a.sizeBytes, etag: '"stable-fixture"', customMetadata: { sha256: a.sha256, kind: a.kind } }; },
        async get(key) { observed.reads++; const a = metadata.assets.find(v => v.r2Key === key);
          return { body: new ReadableStream({ start(c) { c.enqueue(bytes(a)); c.close(); } }) }; },
        async put() { throw new Error("unexpected write"); }
      });
    };
    try { observed.result = (await checkFirmwareBindings({ root, env, fetcher, connect })).ok; }
    catch (e) { observed.errorCode = e.code; observed.message = e.message; }
    return observed;
  }
  const empty = await qualification(null);
  const existing = await qualification(30208);
  assert.equal(empty.result, true);
  assert.equal(empty.reads, 3);
  assert.equal(existing.errorCode, "RELEASE_CONFLICT");
  assert.equal(existing.connects, 0);
  const asset = metadata.assets[0];
  const streamResults = [];
  for (const mode of ["valid", "transport-error", "different-bytes"]) {
    let data = bytes(asset);
    if (mode === "different-bytes") { data = Buffer.from(data); data[0] ^= 1; }
    const bucket = {
      async head() { return { size: asset.sizeBytes, etag: '"stable-fixture"', customMetadata: { sha256: asset.sha256, kind: asset.kind } }; },
      async get() { return { body: new ReadableStream({ start(c) {
        if (mode === "transport-error") c.error(new Error("synthetic transport failure"));
        else { c.enqueue(data); c.close(); }
      } }) }; }
    };
    try { streamResults.push({ mode, ok: (await verifyStoredFirmwareAsset(metadata, asset.fileName, bucket)).ok }); }
    catch (e) { streamResults.push({ mode, errorCode: e.code, message: e.message }); }
  }
  assert.equal(streamResults[0].ok, true);
  assert.equal(streamResults[1].errorCode, "R2_OBJECT_CONFLICT");
  assert.equal(streamResults[2].errorCode, "R2_OBJECT_CONFLICT");
  process.stdout.write(JSON.stringify({nature:"Independent offline reproduction; injected DB and stream ports; no network or file writes",delivery:sha,fixtureVersion:metadata.versionCode,qualification:[empty,existing],streamResults},null,2)+"\n");
})().catch(e=>{process.stderr.write(e.stack+"\n");process.exitCode=1;});
