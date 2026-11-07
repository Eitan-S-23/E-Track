import assert from "node:assert/strict";
import { execFileSync } from "node:child_process";
import { cp, mkdir, mkdtemp, readFile } from "node:fs/promises";
import path from "node:path";
import { fileURLToPath } from "node:url";
import { test } from "node:test";
import { executeStaging, loadStagingInputs, normalStagingInputs as inputs, stagingAdmission, verifyStagingMetadata } from "../../.github/scripts/firmware-candidate-staging.mjs";
import { outputPath, writeOutput } from "../../app/bluetooth_flutter_Trace/cloudflare/update-service/scripts/firmware-cli.mjs";
import { canonicalJson, parseFirmwareRegistration } from "../../app/bluetooth_flutter_Trace/cloudflare/update-service/scripts/firmware-schema.mjs";
import { digest } from "../../app/bluetooth_flutter_Trace/cloudflare/update-service/scripts/prepare-firmware-release.mjs";

const root = fileURLToPath(new URL("../../", import.meta.url));
const area = outputPath(root, path.resolve(root, process.env.P51_TEST_AREA || ".cache/p51-staging/selftests"));
await mkdir(area, { recursive: true });
const admitted = outputPath(root, path.join(await mkdtemp(path.join(area, "normal-originals-")), "admitted"));
const python = process.env.PYTHON || (process.platform === "win32" ? "python" : "python3");
const stdout = execFileSync(python, ["-I", "-S", "-B", "-X", "utf8", "Tools/ota/p51-normal-staging-inputs.py", "--root-out", admitted],
  { cwd: root, env: process.env, encoding: "utf8", windowsHide: true, timeout: 90000 });
await writeOutput(root, path.join(admitted, "SELFTEST-ADMISSION.txt"), stdout);
const sha = "a".repeat(40), git = argv => argv[0] === "rev-parse" ? sha : "";
const env = () => ({ GITHUB_ACTIONS: "true", GITHUB_EVENT_NAME: "workflow_dispatch", GITHUB_REPOSITORY: "Eitan-S-23/E-Track",
  GITHUB_SHA: sha, GITHUB_WORKFLOW_SHA: sha, GITHUB_REF: "refs/heads/fixture-only", GITHUB_RUN_ID: "789", GITHUB_RUN_ATTEMPT: "1",
  GITHUB_WORKFLOW_REF: "Eitan-S-23/E-Track/.github/workflows/firmware-build.yml@refs/heads/fixture-only",
  INPUT_STAGE_CANDIDATE: "true", INPUT_PACKAGE_CANDIDATE: "false", INPUT_PUBLISH: "false", INPUT_REHEARSAL: "false", INPUT_CHECK_BINDINGS: "false",
  INPUT_CANDIDATE_MODE: "normal-delta", INPUT_CANDIDATE_REVIEWED_COMMIT: sha, INPUT_CANDIDATE_BASE_VERSION: "3.3.20",
  INPUT_VERSION_NAME: "3.3.21", INPUT_FIRMWARE_BUILD_PROFILE: "p34-v2-candidate", OTA_BOOT_CHAIN_READY: "false",
  FIRMWARE_RELEASE_MODE: "immutable-candidate-staging", FIRMWARE_CANDIDATE_CONTEXT: "firmware-rehearsal/immutable-candidate-staging-v1",
  CLOUDFLARE_ACCOUNT_ID: "a".repeat(32), TRACE_R2_ACCESS_KEY_ID: "a".repeat(32), TRACE_R2_SECRET_ACCESS_KEY: "b".repeat(64),
  TRACE_DEPLOY_TOKEN: "public-noncredential-double", TRACE_UPDATE_SERVICE_URL: inputs.serviceUrl, TRACE_R2_BUCKET: inputs.bucketName });
async function fixture() {
  const out = outputPath(root, path.join(await mkdtemp(path.join(area, "normal-delivery-")), "out"));
  await cp(admitted, out, { recursive: true, errorOnExist: true, force: false });
  return out;
}
function ports(mode = "ok", onHealth = () => {}) {
  const objects = new Map(), calls = [], registrations = [];
  let closed = false;
  const bucket = {
    async head(key) { calls.push("head"); const value = objects.get(key);
      return value ? { size: value.bytes.length, etag: "fixture-etag", customMetadata: value.metadata } : null; },
    async put(key, bytes, options) { calls.push("put"); assert.equal(options.onlyIf.etagDoesNotMatch, "*");
      objects.set(key, { bytes: Buffer.from(bytes), metadata: options.customMetadata }); return { etag: "fixture-etag" }; },
    async get(key, options) { calls.push("get"); assert.equal(options.onlyIf.etagMatches, "fixture-etag");
      const raw = Buffer.from(objects.get(key).bytes); if (mode === "corrupt") raw[raw.length - 1] ^= 1;
      return { body: new ReadableStream({ start(stream) { stream.enqueue(raw); stream.close(); } }) }; }
  };
  const fetcher = async (url, request = {}) => {
    const endpoint = new URL(url).pathname; calls.push(endpoint);
    if (endpoint === "/healthz") { onHealth(); return Response.json({ ok: true, environment: "staging" }); }
    const id = request.headers["X-Request-Id"], headers = { "X-Request-Id": id }, body = JSON.parse(request.body);
    if (endpoint.endsWith("/preflight")) {
      parseFirmwareRegistration(body.metadata); assert.equal(body.environment, "staging");
      return Response.json({ ok: true, schemaVersion: 1, environment: "staging", requestId: id,
        metadataSha256: digest(Buffer.from(canonicalJson(body.metadata) + "\n")), unresolvedLegacyChannels: 0,
        maxVersionCode: 30319, legacyMaxVersionCode: null }, { headers });
    }
    assert.equal(endpoint, "/api/ci/firmware/releases"); parseFirmwareRegistration(body);
    assert.equal(objects.size, 3); assert.equal(calls.filter(c => c === "get").length, 3);
    registrations.push(body);
    if (mode === "uncertain") throw new Error("simulated transport failure");
    return Response.json({ ok: true, releaseId: "fixture-normal-release", state: "ready", assetsRegistered: 3,
      requestId: id, idempotent: false }, { status: 201, headers });
  };
  const bucketFactory = async (config, operation) => {
    assert.equal(config.bucketName, inputs.bucketName);
    try { return await operation(bucket); } finally { closed = true; }
  };
  return { fetcher, bucketFactory, calls, registrations, objects, closed: () => closed };
}

test("normal protected originals are delivered unchanged with truthful separate source and runner identities", async () => {
  const out = await fixture(), io = ports();
  const result = await executeStaging({ root, out, env: env(), git, ...io });
  assert.equal(result.candidateInputMode, "normal-delta");
  assert.equal(result.originalOwner.commitSha, inputs.originalOwner.commitSha);
  assert.equal(result.originalOwner.runId, "42362540910");
  assert.equal(result.delivery.commitSha, sha);
  assert.equal(io.registrations.length, 1); assert.ok(io.closed());
  const metadata = io.registrations[0];
  assert.equal(metadata.commitSha, "1430c8ff7f3bcd9a35bfe158ba697b99021f75f2");
  assert.equal(metadata.runId, result.originalOwner.runId);
  assert.equal(verifyStagingMetadata(metadata, inputs).versionCode, 30321);
  assert.equal(metadata.assets.find(a => a.kind === "patch").sizeBytes, 12439);
  for (const pin of inputs.assets) assert.equal(metadata.assets.find(a => a.kind === pin.kind).sha256, pin.sha256);
  assert.equal(result.packageGenerations, 0); assert.equal(result.finalizations, 0);
  assert.equal(result.productionPublishable, false); assert.equal(result.approvalEligible, false);
  const second = ports();
  await assert.rejects(executeStaging({ root, out, env: env(), git, ...second }), /Preserve previous/);
  assert.deepEqual(second.calls, []);
});

for (const [key, value] of [["INPUT_CANDIDATE_MODE", "archived-original"], ["INPUT_CANDIDATE_BASE_VERSION", "3.3.18"],
  ["INPUT_VERSION_NAME", "3.3.19"], ["INPUT_PACKAGE_CANDIDATE", "true"], ["INPUT_PUBLISH", "true"],
  ["INPUT_RELEASE_NOTES", "mutable"], ["INPUT_APPROVED_REHEARSAL_RUN_ID", "123"], ["OTA_AES_KEY", "01".repeat(16)],
  ["TRACE_UPDATE_SERVICE_URL", "https://production.invalid"], ["TRACE_R2_BUCKET", "production"], ["OTA_BOOT_CHAIN_READY", "true"]]) {
  test(`normal delivery rejects ${key} before cloud calls`, async () => {
    const io = ports();
    await assert.rejects(executeStaging({ root, out: admitted, env: { ...env(), [key]: value }, git, ...io }));
    assert.deepEqual(io.calls, []);
  });
}
for (const name of ["inputs/registration.json", "inputs/source-proof.json", "originals/normal/target/steps/patch-apply.stdout.txt",
  "originals/inputs/tools/bsdiff", "assets/e-track-at32f435-v3.3.20-to-v3.3.21-patch.etu"]) {
  test(`normal delivery rejects changed ${name} before cloud calls`, async () => {
    const out = await fixture(), io = ports(), file = path.join(out, name), raw = await readFile(file);
    raw[raw.length - 1] ^= 1; await writeOutput(root, file, raw);
    await assert.rejects(executeStaging({ root, out, env: env(), git, ...io }));
    assert.deepEqual(io.calls, []);
  });
}
test("rewritten inventory cannot hide omitted preparation originals", async () => {
  const out = await fixture(), io = ports(), file = path.join(out, "inputs/source-proof.json");
  const proof = JSON.parse(await readFile(file)); proof.files.pop();
  await writeOutput(root, file, JSON.stringify(proof));
  await assert.rejects(executeStaging({ root, out, env: env(), git, ...io }), /inventory/);
  assert.deepEqual(io.calls, []);
});
for (const mode of ["corrupt", "uncertain"]) test(`normal delivery preserves ${mode} failure without blind retry`, async () => {
  const out = await fixture(), io = ports(mode);
  await assert.rejects(executeStaging({ root, out, env: env(), git, ...io }));
  assert.equal(io.registrations.length, mode === "uncertain" ? 1 : 0); assert.ok(io.closed());
  const steps = JSON.parse(await readFile(path.join(out, "evidence/staging-delivery-steps.json")));
  assert.equal(steps.at(-1).automaticRetry, false);
});
test("normal input loading and credential-free gate do not imply formal-release approval", async () => {
  const values = env();
  for (const key of Object.keys(values)) if (key.startsWith("TRACE_") || key.startsWith("CLOUDFLARE_")) delete values[key];
  assert.equal(stagingAdmission(values).delivery.runId, "789");
  assert.throws(() => stagingAdmission(env()), /Unexpected/);
  const loaded = await loadStagingInputs(root, admitted, inputs);
  assert.equal(loaded.registration.versionCode, 30321);
  assert.equal(loaded.proof.finalizations, 0);
});
test("switching between otherwise admitted input modes during delivery is rejected before uploads", async () => {
  const current = env(), out = await fixture();
  const io = ports("ok", () => Object.assign(current, { INPUT_CANDIDATE_MODE: "archived-original",
    INPUT_VERSION_NAME: "3.3.19", INPUT_CANDIDATE_BASE_VERSION: "" }));
  await assert.rejects(executeStaging({ root, out, env: current, git, ...io }), /environment changed/);
  assert.deepEqual(io.calls, ["/healthz"]); assert.equal(io.registrations.length, 0); assert.equal(io.objects.size, 0);
});
