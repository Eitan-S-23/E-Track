import assert from "node:assert/strict";
import { execFileSync } from "node:child_process";
import { readFile, mkdir, mkdtemp } from "node:fs/promises";
import { existsSync } from "node:fs";
import { fileURLToPath } from "node:url";
import path from "node:path";
import { test } from "node:test";
import { executeStaging, loadStagingInputs, stagingAdmission, stagingInputs, verifyStagingCheckout, verifyStagingMetadata, STAGING_PROTOCOL } from "../../.github/scripts/firmware-candidate-staging.mjs";
import { candidateAdmission } from "../../.github/scripts/firmware-candidate-context.mjs";
import { outputPath, writeOutput } from "../../app/bluetooth_flutter_Trace/cloudflare/update-service/scripts/firmware-cli.mjs";
import { canonicalJson, parseFirmwareRegistration, r2KeyFor } from "../../app/bluetooth_flutter_Trace/cloudflare/update-service/scripts/firmware-schema.mjs";
import { digest, metadataBytes } from "../../app/bluetooth_flutter_Trace/cloudflare/update-service/scripts/prepare-firmware-release.mjs";
import { releaseConfig, verifyPromotion } from "../../app/bluetooth_flutter_Trace/cloudflare/update-service/scripts/firmware-release-pipeline.mjs";

const root = fileURLToPath(new URL("../../", import.meta.url));
const area = outputPath(root, path.resolve(root, process.env.P51_TEST_AREA || ".cache/p51-staging/selftests"));
await mkdir(area, { recursive: true });
const admitted = outputPath(root, path.join(await mkdtemp(path.join(area, "real-archive-")), "admitted"));
const python = process.env.PYTHON || (process.platform === "win32" ? "python" : "python3");
// This is the real isolated archive parser, not a prepared-output double.
const admissionOutput = execFileSync(python, ["-I", "-S", "-B", "-X", "utf8", "Tools/ota/p51-staging-inputs.py", "--root-out", admitted],
  { cwd: root, env: process.env, encoding: "utf8", windowsHide: true, timeout: 90000 });
await writeOutput(root, path.join(admitted, "SELFTEST-ADMISSION.txt"), admissionOutput);
const inputNames = ["app-final.bin", "candidate-metadata.json", "gcc-build-inputs.json", "keyed-build-evidence.json", "native-verification.json", "source-proof.json"];
const baseEnv = () => ({ GITHUB_ACTIONS: "true", GITHUB_EVENT_NAME: "workflow_dispatch", GITHUB_REPOSITORY: "Eitan-S-23/E-Track",
  GITHUB_SHA: "a".repeat(40), GITHUB_RUN_ID: "456", GITHUB_RUN_ATTEMPT: "2", GITHUB_REF: "refs/heads/fixture-only",
  GITHUB_WORKFLOW_SHA: "a".repeat(40), GITHUB_WORKFLOW_REF: "Eitan-S-23/E-Track/.github/workflows/firmware-build.yml@refs/heads/fixture-only",
  INPUT_STAGE_CANDIDATE: "true", INPUT_PACKAGE_CANDIDATE: "false", INPUT_PUBLISH: "false", INPUT_REHEARSAL: "false", INPUT_CHECK_BINDINGS: "false",
  INPUT_CANDIDATE_MODE: "archived-original", INPUT_VERSION_NAME: "3.3.19", INPUT_FIRMWARE_BUILD_PROFILE: "p34-v2-candidate",
  INPUT_CANDIDATE_REVIEWED_COMMIT: "a".repeat(40), OTA_BOOT_CHAIN_READY: "false", FIRMWARE_RELEASE_MODE: "immutable-candidate-staging",
  FIRMWARE_CANDIDATE_CONTEXT: "firmware-rehearsal/immutable-candidate-staging-v1" });
const cloudEnv = () => ({ ...baseEnv(), CLOUDFLARE_ACCOUNT_ID: "a".repeat(32), TRACE_R2_ACCESS_KEY_ID: "a".repeat(32),
  TRACE_R2_SECRET_ACCESS_KEY: "b".repeat(64), TRACE_DEPLOY_TOKEN: "public-noncredential-double",
  TRACE_UPDATE_SERVICE_URL: stagingInputs.serviceUrl, TRACE_R2_BUCKET: stagingInputs.bucketName });
const gitDouble = argv => argv[0] === "rev-parse" ? "a".repeat(40) : "";
async function fixture() {
  const out = outputPath(root, await mkdtemp(path.join(area, "delivery-")));
  for (const name of inputNames) await writeOutput(root, path.join(out, "inputs", name), await readFile(path.join(admitted, "inputs", name)));
  for (const asset of stagingInputs.assets) await writeOutput(root, path.join(out, "assets", asset.fileName), await readFile(path.join(admitted, "assets", asset.fileName)));
  return out;
}

// Only network/storage ports and checkout identity are doubles. Parsers,
// hashes, complete stream readback, conditional upload and registration are real.
function ports(mode = "ok", controller) {
  const objects = new Map(), calls = [], uploads = [], registrations = [];
  let disposed = false;
  const bucket = {
    async head(key) { calls.push("head");
      if (mode === "r2-uncertain") throw new Error("simulated transport uncertainty");
      if (mode === "abort") { setTimeout(() => controller.abort(), 5); return new Promise(() => {}); }
      const value = objects.get(key);
      return value ? { size: value.bytes.length, etag: "fixture-etag", customMetadata: value.metadata } : null;
    },
    async put(key, bytes, options) { calls.push("put"); assert.equal(options.onlyIf.etagDoesNotMatch, "*");
      objects.set(key, { bytes: Buffer.from(bytes), metadata: options.customMetadata }); uploads.push(key);
      return { etag: "fixture-etag" };
    },
    async get(key, options) { calls.push("get"); assert.equal(options.onlyIf.etagMatches, "fixture-etag");
      const bytes = Buffer.from(objects.get(key).bytes);
      if (mode === "corrupt-readback") bytes[bytes.length - 1] ^= 1;
      return { body: new ReadableStream({ start(stream) { if (mode === "interrupted-readback") { stream.error(new Error("interrupted")); return; }
        for (let off = 0; off < bytes.length; off += 65536) stream.enqueue(bytes.subarray(off, off + 65536)); stream.close(); } }) };
    }
  };
  const fetcher = async (url, request = {}) => {
    const endpoint = new URL(url).pathname; calls.push(endpoint);
    if (endpoint === "/healthz") return Response.json({ ok: true, environment: mode === "wrong-health" ? "prod" : "staging" });
    const id = request.headers["X-Request-Id"], headers = { "X-Request-Id": id };
    const body = JSON.parse(request.body);
    if (endpoint.endsWith("/preflight")) {
      assert.equal(body.environment, "staging"); parseFirmwareRegistration(body.metadata);
      if (mode === "preflight-conflict") return Response.json({}, { status: 409 });
      return Response.json({ ok: true, schemaVersion: 1, environment: "staging", requestId: id,
        metadataSha256: digest(Buffer.from(canonicalJson(body.metadata) + "\n")), unresolvedLegacyChannels: 0,
        maxVersionCode: 30319, legacyMaxVersionCode: null }, { headers });
    }
    assert.equal(endpoint, "/api/ci/firmware/releases"); registrations.push(body);
    parseFirmwareRegistration(body);
    assert.equal(objects.size, 3); assert.equal(calls.filter(c => c === "get").length, 3);
    if (mode === "register-conflict") return Response.json({ errorCode: "RELEASE_CONFLICT" }, { status: 409 });
    if (mode === "register-uncertain") throw new Error("simulated uncertain result");
    return Response.json({ ok: true, releaseId: "fixture-staging-release", state: "ready", assetsRegistered: 3,
      requestId: id, idempotent: mode === "already-ready" }, { status: mode === "already-ready" ? 200 : 201, headers });
  };
  const bucketFactory = async (config, operation) => { calls.push("bucket-factory");
    assert.equal(config.bucketName, stagingInputs.bucketName);
    try { return await operation(bucket); } finally { disposed = true; }
  };
  return { bucketFactory, fetcher, calls, objects, registrations, uploads, disposed: () => disposed };
}

test("real archive resolves with immutable metadata and distinct compilation/delivery identities", async () => {
  const out = await fixture(), io = ports();
  const evidence = await executeStaging({ root, out, env: cloudEnv(), git: gitDouble, ...io });
  assert.equal(evidence.originalOwner.commitSha, "1430c8ff7f3bcd9a35bfe158ba697b99021f75f2");
  assert.equal(evidence.originalOwner.runId, "41900439548"); assert.equal(evidence.originalOwner.runAttempt, "1");
  assert.equal(evidence.originalOwner.artifactId, 13359301400); assert.equal(evidence.originalOwner.buildTimestamp, 1793820855);
  assert.equal(evidence.delivery.commitSha, "a".repeat(40)); assert.equal(evidence.delivery.runId, "456"); assert.equal(evidence.delivery.runAttempt, "2");
  assert.equal(io.registrations.length, 1); assert.equal(io.uploads.length, 3); assert.ok(io.disposed());
  const metadata = io.registrations[0];
  assert.equal(metadata.commitSha, evidence.originalOwner.commitSha); assert.equal(metadata.runId, evidence.originalOwner.runId);
  assert.equal(metadata.assets.find(a => a.kind === "patch").baseImageSha256, stagingInputs.baseImageSha256);
  for (const asset of metadata.assets) assert.equal(asset.sha256, stagingInputs.assets.find(a => a.kind === asset.kind).sha256);
  assert.equal(digest(await readFile(path.join(out,"inputs/candidate-metadata.json"))), "d0ac413335eb8bd77838e4ec8ca305c411a4f517b6d03b1f06746c1e1e73ce96");
  assert.equal(evidence.productionPublishable, false); assert.equal(evidence.publicationProtocol, STAGING_PROTOCOL);
  assert.equal(evidence.sourceProofSha256, digest(await readFile(path.join(out,"inputs/source-proof.json"))));
  assert.equal(verifyStagingMetadata(metadata).versionCode, 30319);
  for (const mutate of [value => { value.targetImageSha256 = "0".repeat(64); },
    value => { value.assets[0].sha256 = "0".repeat(64); },
    value => { value.assets.find(a => a.kind === "patch").baseImageSha256 = "0".repeat(64); }]) {
    const wrong = structuredClone(metadata); mutate(wrong);
    assert.throws(() => verifyStagingMetadata(wrong), /Staging generated metadata/);
  }
  for (const key of ["sourceCompilations", "finalizations", "packageGenerations", "referenceSearches"]) assert.equal(evidence[key], 0);
  const approvedMetadata = metadataBytes(metadata), prepared = Buffer.from(JSON.stringify({ build: (await loadStagingInputs(root, out)).build }));
  const augmented = { ...evidence, preparationSha256: digest(prepared) }, approvedEvidence = Buffer.from(JSON.stringify(augmented));
  assert.throws(() => verifyPromotion(metadata, { approvedMetadata, approvedEvidence, approvedPreparation: prepared,
    currentBuild: JSON.parse(prepared).build, config: { canonicalRunId: metadata.runId, buildProfile: "p34-v2-candidate" },
    approvedRun: { id: Number(metadata.runId), head_sha: metadata.commitSha, run_attempt: 1, path: ".github/workflows/firmware-build.yml", event: "workflow_dispatch", conclusion: "success" },
    env: { GITHUB_SHA: metadata.commitSha, OTA_APPROVED_REHEARSAL_ATTEMPT: "1", OTA_APPROVED_REHEARSAL_METADATA_SHA256: digest(approvedMetadata),
      OTA_APPROVED_REHEARSAL_EVIDENCE_SHA256: digest(approvedEvidence) } }), /Approved rehearsal run\/evidence binding mismatch/);
  await assert.rejects(executeStaging({ root, out, env: cloudEnv(), git: gitDouble, ...ports() }), /Preserve previous/);
});

const invalid = [
  ["INPUT_STAGE_CANDIDATE", "false"], ["INPUT_STAGE_CANDIDATE", "TRUE"], ["INPUT_PUBLISH", "true"], ["INPUT_REHEARSAL", "true"],
  ["INPUT_PACKAGE_CANDIDATE", "true"], ["INPUT_CHECK_BINDINGS", "true"], ["OTA_BOOT_CHAIN_READY", "true"],
  ["INPUT_CANDIDATE_MODE", "new-source"], ["INPUT_CANDIDATE_MODE", "start-state-supplement"],
  ["INPUT_CANDIDATE_BASE_VERSION", "3.3.18"], ["INPUT_CANDIDATE_FULL_BASE_VERSION", "3.3.17"],
  ["INPUT_VERSION_NAME", "3.3.20"], ["INPUT_FIRMWARE_BUILD_PROFILE", "baseline"], ["INPUT_APPROVED_REHEARSAL_RUN_ID", "123"],
  ["GITHUB_SHA", "b".repeat(40)], ["GITHUB_WORKFLOW_SHA", "b".repeat(40)], ["GITHUB_RUN_ID", "0"], ["GITHUB_RUN_ATTEMPT", "0"],
  ["GITHUB_WORKFLOW_REF", "another-workflow"], ["GITHUB_EVENT_NAME", "push"], ["GITHUB_REPOSITORY", "Eitan-S-23/Trace"],
  ["TRACE_UPDATE_SERVICE_URL", "https://e-track-firmware-production.tangjichentudou.workers.dev"],
  ["TRACE_UPDATE_SERVICE_URL", stagingInputs.serviceUrl + "/"], ["TRACE_R2_BUCKET", "e-track-firmware-production-releases"],
  ["TRACE_D1_DATABASE_ID", "public-double"], ["CLOUDFLARE_API_TOKEN", "public-double"], ["GITHUB_TOKEN", "public-double"],
  ["OTA_AES_KEY", "01".repeat(16)], ["OTA_PREVIOUS_RELEASE_JSON", "{}"], ["OTA_APPROVED_REHEARSAL_RUN_ID", "123"],
  ["TRACE_REGISTER_RETRIES", "3"], ["INPUT_RELEASE_NOTES", "mutable metadata"], ["FIRMWARE_RELEASE_MODE", "rehearsal"],
  ["FIRMWARE_CANDIDATE_CONTEXT", "firmware-rehearsal/artifact-only-new-source-v1"], ["TRACE_R2_ACCESS_KEY_ID", "not-an-id"]
];
for (const [name, value] of invalid) test(`admission rejects ${name}/${value.length} with zero cloud calls`, async () => {
  const io = ports();
  await assert.rejects(executeStaging({ root, out: admitted, env: { ...cloudEnv(), [name]: value }, git: gitDouble, ...io }));
  assert.deepEqual(io.calls, []);
});

for (const name of ["source-proof.json", "candidate-metadata.json", "gcc-build-inputs.json", "app-final.bin", ...stagingInputs.assets.map(a => a.fileName)]) {
  test(`tampered ${name} fails before any cloud call`, async () => {
    const out = await fixture(), io = ports();
    const dir = stagingInputs.assets.some(a => a.fileName === name) ? "assets" : "inputs";
    const file = path.join(out, dir, name), bytes = await readFile(file); bytes[bytes.length - 1] ^= 1;
    await writeOutput(root, file, bytes);
    await assert.rejects(executeStaging({ root, out, env: cloudEnv(), git: gitDouble, ...io }));
    assert.deepEqual(io.calls, []);
  });
}
for (const mode of ["wrong-health", "preflight-conflict", "corrupt-readback", "interrupted-readback", "r2-uncertain", "register-conflict", "register-uncertain"]) {
  test(`${mode} stops without registration or blind retry`, async () => {
    const out = await fixture(), io = ports(mode);
    await assert.rejects(executeStaging({ root, out, env: cloudEnv(), git: gitDouble, ...io }));
    assert.equal(io.registrations.length, mode.startsWith("register-") ? 1 : 0);
    assert.ok(!existsSync(path.join(out, "evidence/staging-registration-ready.json")));
    assert.ok(!existsSync(path.join(out, "evidence/staging-delivery-evidence.json")));
    if (!mode.startsWith("wrong-") && !mode.startsWith("preflight-")) assert.ok(io.disposed());
    assert.equal(io.calls.filter(c => c === "/api/ci/firmware/releases").length, io.registrations.length);
    assert.equal(JSON.parse(await readFile(path.join(out,"evidence/staging-delivery-steps.json"))).at(-1).automaticRetry, false);
  });
}
test("bounded cancellation closes the owned storage port and never registers", async () => {
  const controller = new AbortController(), out = await fixture(), io = ports("abort", controller);
  await assert.rejects(executeStaging({ root, out, env: cloudEnv(), git: gitDouble, signal: controller.signal, ...io }));
  assert.ok(io.disposed()); assert.equal(io.registrations.length, 0);
});
test("matching existing objects are read back without upload and one idempotent registration suffices", async () => {
  const out = await fixture(), io = ports("already-ready");
  for (const asset of stagingInputs.assets) {
    const key = r2KeyFor({ appId:"trace", deviceModel:"e-track-at32f435", versionCode:30319,
      releaseTag:"mcu-e-track-at32f435-v3.3.19" }, asset);
    io.objects.set(key, { bytes:await readFile(path.join(out,"assets",asset.fileName)), metadata:{ sha256:asset.sha256, kind:asset.kind } });
  }
  const evidence = await executeStaging({ root, out, env:cloudEnv(), git:gitDouble, ...io });
  assert.equal(io.uploads.length, 0); assert.equal(io.registrations.length, 1);
  assert.equal(evidence.registration.idempotent, true);
  assert.ok(evidence.uploads.every(value => value.status === "ALREADY_PRESENT"));
  assert.ok(io.disposed());
});
test("conflicting existing object is never overwritten or registered", async () => {
  const out = await fixture(), io = ports(), asset = stagingInputs.assets[0];
  const key = r2KeyFor({ appId:"trace", deviceModel:"e-track-at32f435", versionCode:30319,
    releaseTag:"mcu-e-track-at32f435-v3.3.19" }, asset);
  io.objects.set(key, { bytes:await readFile(path.join(out,"assets",asset.fileName)), metadata:{ sha256:"0".repeat(64), kind:asset.kind } });
  await assert.rejects(executeStaging({ root, out, env:cloudEnv(), git:gitDouble, ...io }), error => error.code === "R2_OBJECT_CONFLICT");
  assert.equal(io.uploads.length, 0); assert.equal(io.registrations.length, 0); assert.ok(io.disposed());
});
test("gate is credential-free and checkout mismatch is rejected", () => {
  assert.equal(stagingAdmission(baseEnv()).delivery.runId, "456");
  assert.throws(() => stagingAdmission(cloudEnv()), /Unexpected/);
  assert.throws(() => verifyStagingCheckout(root, baseEnv(), false, () => "different"), /checkout/);
  assert.throws(() => releaseConfig({ ...cloudEnv(), INPUT_STAGE_CANDIDATE: "true" }), /Immutable staging/);
});
test("legacy artifact-only modes remain admitted independently and reject staging/cloud pollution", () => {
  const original = { ...baseEnv(), INPUT_STAGE_CANDIDATE: "false", INPUT_PACKAGE_CANDIDATE: "true", INPUT_VERSION_NAME: "3.3.16",
    FIRMWARE_RELEASE_MODE: "", FIRMWARE_CANDIDATE_CONTEXT: "" };
  for (const mode of ["archived-original", "new-source", "start-state-supplement"]) {
    const env = { ...original, INPUT_CANDIDATE_MODE: mode };
    if (mode === "new-source") Object.assign(env, { INPUT_VERSION_NAME:"3.3.19", INPUT_CANDIDATE_BASE_VERSION:"3.3.18",
      FIRMWARE_RELEASE_MODE:"artifact-candidate", FIRMWARE_CANDIDATE_CONTEXT:"firmware-rehearsal/artifact-only-new-source-v1" });
    if (mode === "start-state-supplement") Object.assign(env, { INPUT_VERSION_NAME:"3.3.19", FIRMWARE_RELEASE_MODE:"artifact-candidate-supplement",
      FIRMWARE_CANDIDATE_CONTEXT:"firmware-rehearsal/artifact-only-start-state-v1" });
    assert.equal(candidateAdmission(env).runId, "456");
    for (const override of [{ INPUT_STAGE_CANDIDATE:"true" }, { TRACE_DEPLOY_TOKEN:"public-double" }, { CLOUDFLARE_ACCOUNT_ID:"a".repeat(32) }]) {
      assert.throws(() => candidateAdmission({ ...env, ...override }));
    }
  }
});
test("workflow is opt-in protected, mutually exclusive, and has no firmware/production action", async () => {
  const text = await readFile(path.join(root, ".github/workflows/firmware-build.yml"), "utf8");
  const workflow = JSON.parse(execFileSync(python, ["-B", "-c", "import json,sys,yaml;print(json.dumps(yaml.load(sys.stdin,Loader=yaml.BaseLoader)))"],
    { cwd: root, input: text, encoding: "utf8", windowsHide: true }));
  const job = workflow.jobs["stage-candidate"];
  assert.equal(workflow.on.workflow_dispatch.inputs.stage_candidate.default, "false");
  assert.equal(job.environment, "firmware-rehearsal"); assert.deepEqual(job.permissions, { contents:"read" });
  assert.equal(job["timeout-minutes"], "20"); assert.equal(job.needs, undefined);
  assert.equal(job.env.PYTHONPATH, "${{ github.workspace }}/.cache/p51-staging/python");
  assert.match(job.if, /stage_candidate == 'true'/);
  for (const name of ["build", "release-development-checks", "register-cloudflare", "rehearse-cloudflare", "check-firmware-bindings"]) {
    assert.match(workflow.jobs[name].if, /stage_candidate != 'true'/);
  }
  assert.equal(job.steps.filter(step => JSON.stringify(step.env ?? {}).includes("secrets.")).length, 1);
  const delivery = job.steps.find(step => step.id === "delivery");
  for (const value of Object.values(delivery.env)) if (value.includes("secrets.")) assert.match(value, /secrets\.FIRMWARE_REHEARSAL_/);
  assert.doesNotMatch(JSON.stringify(job), /OTA_AES_KEY|GITHUB_TOKEN|cmake|arm-none-eabi|firmware-release\.mjs|wrangler|release create|D1_DATABASE/);
  assert.ok(job.steps.findIndex(step => step.run?.endsWith("staging.mjs gate")) < job.steps.indexOf(delivery));
  const output = job.steps.find(step => step.uses === "actions/upload-artifact@v4").with.path;
  assert.equal(output.split("\n").filter(v => /\.(etu|bin)$/.test(v)).length, 3);
  assert.doesNotMatch(output, /initialize|Boot|key\.h|private|keyed-build/);
});
