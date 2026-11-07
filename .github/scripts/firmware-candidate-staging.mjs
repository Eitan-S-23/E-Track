import { existsSync } from "node:fs";
import { readFile } from "node:fs/promises";
import { execFile, execFileSync } from "node:child_process";
import { promisify } from "node:util";
import { fileURLToPath, pathToFileURL } from "node:url";
import path from "node:path";
import { args, CliError, failure, outputPath, projectRoot, writeOutput } from "../../app/bluetooth_flutter_Trace/cloudflare/update-service/scripts/firmware-cli.mjs";
import { assetFileName, canonicalJson, parseFirmwareRegistration } from "../../app/bluetooth_flutter_Trace/cloudflare/update-service/scripts/firmware-schema.mjs";
import { buildFirmwareMetadata } from "../../app/bluetooth_flutter_Trace/cloudflare/update-service/scripts/build-firmware-release-metadata.mjs";
import { digest, metadataBytes, readyProjection } from "../../app/bluetooth_flutter_Trace/cloudflare/update-service/scripts/prepare-firmware-release.mjs";
import { verifyBuildConfiguration } from "../../app/bluetooth_flutter_Trace/cloudflare/update-service/scripts/firmware-build-profile.mjs";
import { bounded, verifyWorkerEnvironment } from "../../app/bluetooth_flutter_Trace/cloudflare/update-service/scripts/firmware-release-pipeline.mjs";
import { preflightFirmware } from "../../app/bluetooth_flutter_Trace/cloudflare/update-service/scripts/firmware-preflight-client.mjs";
import { uploadFirmwareAsset, withFirmwareBucket } from "../../app/bluetooth_flutter_Trace/cloudflare/update-service/scripts/upload-firmware-r2-asset.mjs";
import { s3Credentials } from "../../app/bluetooth_flutter_Trace/cloudflare/update-service/scripts/firmware-s3.mjs";
import { registerFirmware } from "../../app/bluetooth_flutter_Trace/cloudflare/update-service/scripts/register-firmware-release.mjs";

export const STAGING_PROTOCOL = "p51-immutable-candidate-staging-v1";
const inputFile = fileURLToPath(new URL("../../Tools/ota/p51-staging-inputs.json", import.meta.url));
export const stagingInputs = JSON.parse(await readFile(inputFile));
export const normalStagingInputs = JSON.parse(await readFile(new URL("../../Tools/ota/p51-normal-staging-inputs.json", import.meta.url)));
const inputsFor = env => env.INPUT_CANDIDATE_MODE === "normal-delta" ? normalStagingInputs : stagingInputs;
const cloudKeys = ["CLOUDFLARE_ACCOUNT_ID", "TRACE_R2_ACCESS_KEY_ID", "TRACE_R2_SECRET_ACCESS_KEY",
  "TRACE_UPDATE_SERVICE_URL", "TRACE_R2_BUCKET", "TRACE_DEPLOY_TOKEN"];
const fail = message => new CliError(message, "INVALID_PARAMETER", 2);

export function stagingAdmission(env, credentials = false) {
  const inputs = inputsFor(env), normal = env.INPUT_CANDIDATE_MODE === "normal-delta";
  if (env.GITHUB_ACTIONS !== "true" || env.GITHUB_EVENT_NAME !== "workflow_dispatch"
    || env.GITHUB_REPOSITORY !== "Eitan-S-23/E-Track" || env.INPUT_STAGE_CANDIDATE !== "true"
    || ["INPUT_PACKAGE_CANDIDATE", "INPUT_PUBLISH", "INPUT_REHEARSAL", "INPUT_CHECK_BINDINGS"].some(k => env[k] !== "false")
    || env.OTA_BOOT_CHAIN_READY !== "false" || env.INPUT_FIRMWARE_BUILD_PROFILE !== "p34-v2-candidate"
    || env.INPUT_VERSION_NAME !== inputs.versionName || !["archived-original", "normal-delta"].includes(env.INPUT_CANDIDATE_MODE)
    || (normal ? env.INPUT_CANDIDATE_BASE_VERSION !== inputs.baseVersionName : env.INPUT_CANDIDATE_BASE_VERSION)
    || env.INPUT_CANDIDATE_FULL_BASE_VERSION || env.INPUT_APPROVED_REHEARSAL_RUN_ID
    || env.INPUT_RELEASE_NOTES || env.FIRMWARE_RELEASE_MODE !== "immutable-candidate-staging"
    || env.FIRMWARE_CANDIDATE_CONTEXT !== "firmware-rehearsal/immutable-candidate-staging-v1"
    || !/^[0-9a-f]{40}$/.test(env.GITHUB_SHA ?? "") || env.GITHUB_SHA !== env.INPUT_CANDIDATE_REVIEWED_COMMIT
    || env.GITHUB_WORKFLOW_SHA !== env.GITHUB_SHA
    || !/^refs\/heads\/[A-Za-z0-9_./-]+$/.test(env.GITHUB_REF ?? "")
    || env.GITHUB_WORKFLOW_REF !== `Eitan-S-23/E-Track/.github/workflows/firmware-build.yml@${env.GITHUB_REF}`
    || !/^[1-9][0-9]*$/.test(env.GITHUB_RUN_ID ?? "") || !/^[1-9][0-9]*$/.test(env.GITHUB_RUN_ATTEMPT ?? "")) {
    throw fail("Staging requires the exact reviewed, exclusive locked-gate protected workflow");
  }
  for (const [name, value] of Object.entries(env)) {
    if (value && /^(TRACE_|CLOUDFLARE_|CF_|GH_|GITHUB_TOKEN|OTA_)/.test(name)
      && name !== "OTA_BOOT_CHAIN_READY" && !(credentials && cloudKeys.includes(name))) {
      throw fail("Unexpected key/cloud/production input in immutable staging context");
    }
  }
  const delivery = { commitSha: env.GITHUB_SHA, runId: env.GITHUB_RUN_ID, runAttempt: env.GITHUB_RUN_ATTEMPT,
    workflowCommit: env.GITHUB_WORKFLOW_SHA, workflowRef: env.GITHUB_WORKFLOW_REF };
  const inputIdentity = { mode: env.INPUT_CANDIDATE_MODE, versionCode: inputs.versionCode,
    baseVersionCode: inputs.baseVersionCode, schema: inputs.schema };
  if (!credentials) return { delivery, inputIdentity };
  for (const key of cloudKeys) if (!env[key]) throw fail(`Missing staging binding: ${key}`);
  s3Credentials(env);
  if (!/^[0-9a-f]{32}$/.test(env.CLOUDFLARE_ACCOUNT_ID) || /\s/.test(env.TRACE_DEPLOY_TOKEN)
    || env.TRACE_UPDATE_SERVICE_URL !== inputs.serviceUrl || env.TRACE_R2_BUCKET !== inputs.bucketName) {
    throw fail("Immutable staging requires the exact isolated Worker and test bucket");
  }
  return { delivery, inputIdentity, serviceUrl: inputs.serviceUrl, bucketName: inputs.bucketName,
    accountId: env.CLOUDFLARE_ACCOUNT_ID };
}

export function verifyStagingCheckout(root, env, credentials = false, git = argv =>
  execFileSync("git", ["--no-optional-locks", ...argv], { cwd: root, encoding: "utf8", windowsHide: true }).trim()) {
  const result = stagingAdmission(env, credentials);
  if (git(["rev-parse", "HEAD"]) !== result.delivery.commitSha || git(["diff", "--name-only", "HEAD"])) {
    throw fail("Immutable staging checkout differs from the reviewed delivery source");
  }
  return result;
}

async function pinned(root, record) {
  const bytes = await readFile(outputPath(root, path.join(root, record.path)));
  if (bytes.length !== record.bytes || digest(bytes) !== record.sha256) throw fail("Pinned original staging input changed");
  return bytes;
}

async function loadNormalStagingInputs(root, out, inputs) {
  for (const pin of [inputs.sourceInputs, inputs.archive, inputs.artifact, inputs.run]) await pinned(root, pin);
  const proofBytes = await readFile(outputPath(root, path.join(out, "inputs/source-proof.json")));
  const proof = JSON.parse(proofBytes);
  if (proof.schema !== "p51-normal-staging-source-proof-v1"
    || canonicalJson(proof.originalOwner) !== canonicalJson(inputs.originalOwner)
    || canonicalJson(proof.archive) !== canonicalJson(inputs.archive)
    || canonicalJson(proof.artifactReceipt) !== canonicalJson(inputs.artifact)
    || proof.configSha256 !== digest(Buffer.from(canonicalJson(inputs) + "\n"))
    || digest(Buffer.from(canonicalJson(proof.files) + "\n")) !== inputs.archiveMembersSha256
    || ["sourceCompilations", "finalizations", "packageGenerations", "referenceSearches"].some(k => proof[k] !== 0)) {
    throw fail("Normal staging original proof/inventory changed");
  }
  const originals = new Map();
  for (const pin of proof.files) {
    if (!/^[A-Za-z0-9_./-]+$/.test(pin.member) || pin.member.startsWith("/")
      || pin.member.split("/").some(p => ["", ".", "..", "private"].includes(p))) throw fail("Unsafe normal staging member");
    const bytes = await readFile(outputPath(root, path.join(out, "originals", pin.member)));
    if (bytes.length !== pin.bytes || digest(bytes) !== pin.sha256) throw fail("Normal staging original bytes changed");
    originals.set(pin.member, bytes);
  }
  const selected = async (name, pin) => {
    const bytes = await readFile(outputPath(root, path.join(out, "inputs", name)));
    if (bytes.length !== pin.bytes || digest(bytes) !== pin.sha256 || !bytes.equals(originals.get(pin.member))) {
      throw fail("Normal staging selected evidence changed");
    }
    return bytes;
  };
  const candidate = JSON.parse(await selected("candidate-metadata.json", inputs.candidateMetadata));
  const registration = JSON.parse(await selected("registration.json", inputs.registration));
  await selected("app-final.bin", inputs.finalImage);
  await selected("native-verification.json", inputs.verification);
  const buildBytes = await readFile(outputPath(root, path.join(out, "inputs/gcc-build-inputs.json")));
  if (!buildBytes.equals(originals.get("inputs/originals/target/keyed-build/gcc-build-inputs.json"))) throw fail("Normal staging build changed");
  const build = JSON.parse(buildBytes);
  verifyBuildConfiguration(build, inputs.profile);
  if (candidate.schema !== "p51-normal-candidate-v1" || candidate.isFormalRelease !== false || candidate.productionPublishable !== false
    || candidate.readyRegistered !== false || registration.runId !== inputs.originalOwner.runId
    || registration.commitSha !== build.commitSha || proof.targetSourceCommit !== build.commitSha
    || candidate.patchComparison.preferredKindForMatchingBase !== "patch"
    || candidate.patchComparison.changesOutsideFwHeader !== true) throw fail("Normal staging candidate lineage changed");
  const bytesByName = new Map();
  for (const pin of inputs.assets) {
    if (pin.fileName !== assetFileName(pin.kind, inputs.versionName, pin.kind === "patch" ? inputs.baseVersionCode : 0)) {
      throw fail("Normal staging asset name changed");
    }
    const bytes = await readFile(outputPath(root, path.join(out, "assets", pin.fileName)));
    if (bytes.length !== pin.bytes || digest(bytes) !== pin.sha256 || !bytes.equals(originals.get(pin.member))) throw fail("Normal staging asset bytes changed");
    bytesByName.set(pin.fileName, bytes);
  }
  verifyStagingMetadata(registration, inputs);
  return { proof, sourceProofSha256: digest(proofBytes), owner: inputs.originalOwner, build, bytesByName, registration };
}

export async function loadStagingInputs(root, out, configuration = stagingInputs) {
  if (configuration.schema === "p51-normal-staging-inputs-v1") return loadNormalStagingInputs(root, out, configuration);
  const original = JSON.parse(await pinned(root, stagingInputs.sourceInputs));
  await pinned(root, original.archive);
  await pinned(root, original.artifact);
  const inputs = path.join(out, "inputs");
  const proofBytes = await readFile(outputPath(root, path.join(inputs, "source-proof.json")));
  const proof = JSON.parse(proofBytes);
  const owner = { commitSha: original.sourceCommit, runId: String(original.originalRun),
    runAttempt: String(original.originalAttempt), artifactId: original.originalArtifact, buildTimestamp: original.buildTimestamp };
  const expected = { schema: "p51-staging-source-proof-v1", originalOwner: owner, archive: original.archive,
    artifactReceipt: original.artifact, originalMetadata: original.members.metadata, build: original.members.build,
    keyedEvidence: original.members.keyedEvidence, verification: stagingInputs.verification,
    sourceCompilations: 0, finalizations: 0, packageGenerations: 0, referenceSearches: 0,
    assets: stagingInputs.assets, finalImage: stagingInputs.finalImage };
  if (canonicalJson(proof) !== canonicalJson(expected)) throw fail("Staging materialized source/asset proof changed");
  const contents = {};
  for (const [name, record] of [["candidate-metadata.json", original.members.metadata], ["gcc-build-inputs.json", original.members.build],
    ["keyed-build-evidence.json", original.members.keyedEvidence], ["native-verification.json", stagingInputs.verification],
    ["app-final.bin", stagingInputs.finalImage]]) {
    const bytes = await readFile(outputPath(root, path.join(inputs, name)));
    if (bytes.length !== record.bytes || digest(bytes) !== record.sha256) throw fail("Staging original evidence/image changed");
    contents[name] = bytes;
  }
  const candidate = JSON.parse(contents["candidate-metadata.json"]), build = JSON.parse(contents["gcc-build-inputs.json"]);
  verifyBuildConfiguration(build, stagingInputs.profile);
  if (candidate.schema !== "p51-artifact-candidate-v2" || candidate.isFormalRelease !== false
    || candidate.productionPublishable !== false || candidate.readyRegistered !== false
    || candidate.versionCode !== stagingInputs.versionCode || candidate.baseVersionCode !== stagingInputs.baseVersionCode
    || candidate.baseImageSha256 !== stagingInputs.baseImageSha256 || candidate.targetImageSha256 !== digest(contents["app-final.bin"])
    || candidate.runner.commitSha !== owner.commitSha || candidate.runner.runId !== owner.runId || candidate.runner.runAttempt !== owner.runAttempt
    || canonicalJson(candidate.build) !== canonicalJson(build)) throw fail("Staging original candidate identity mismatch");
  const bytesByName = new Map();
  for (const asset of stagingInputs.assets) {
    if (asset.fileName !== assetFileName(asset.kind, stagingInputs.versionName, asset.kind === "patch" ? stagingInputs.baseVersionCode : 0)) {
      throw fail("Staging canonical asset naming mismatch");
    }
    const bytes = await readFile(outputPath(root, path.join(out, "assets", asset.fileName)));
    if (bytes.length !== asset.bytes || digest(bytes) !== asset.sha256) throw fail("Staging selected asset byte identity mismatch");
    bytesByName.set(asset.fileName, bytes);
  }
  return { proof, sourceProofSha256: digest(proofBytes), owner, build, bytesByName };
}

export function verifyStagingMetadata(metadata, inputs = stagingInputs) {
  metadata = parseFirmwareRegistration(metadata, "Eitan-S-23/E-Track", false);
  if (metadata.versionCode !== inputs.versionCode || metadata.targetImageSha256 !== inputs.finalImage.sha256
    || metadata.assets.length !== inputs.assets.length) throw fail("Staging generated metadata target/inventory mismatch");
  for (const asset of metadata.assets) {
    const pinnedAsset = inputs.assets.find(a => a.kind === asset.kind);
    if (!pinnedAsset || asset.fileName !== pinnedAsset.fileName || asset.sha256 !== pinnedAsset.sha256 || asset.sizeBytes !== pinnedAsset.bytes
      || (asset.kind === "patch" && (asset.baseVersionCode !== inputs.baseVersionCode
        || asset.baseImageSha256 !== inputs.baseImageSha256))) throw fail("Staging generated metadata asset/base mismatch");
  }
  return metadata;
}

export async function executeStaging({ root, out, env, fetcher = fetch, bucketFactory = withFirmwareBucket, signal, git }) {
  const config = verifyStagingCheckout(root, env, true, git);
  out = outputPath(root, out);
  const inputs = inputsFor(env);
  const data = await loadStagingInputs(root, out, inputs);
  const metadata = data.registration ?? await buildFirmwareMetadata({ repository: env.GITHUB_REPOSITORY,
    assetsDir: path.join(out, "assets"), finalImage: path.join(out, "inputs/app-final.bin"),
    patchBases: [{ baseVersionCode: stagingInputs.baseVersionCode, baseImageSha256: stagingInputs.baseImageSha256 }],
    release: { releaseTag: "mcu-e-track-at32f435-v3.3.19", runId: data.owner.runId, commitSha: data.owner.commitSha,
      versionName: stagingInputs.versionName, releaseNotes: "P51 isolated staging only; immutable candidate, not production approval",
      targetHardware: "AT32F435RGT7", hardwareRevision: 1, layoutId: 1, minBootVersion: 1, minProtocolVersion: 1, minAppVersionCode: 0 } });
  verifyStagingMetadata(metadata, inputs);
  const evidenceDir = outputPath(root, path.join(out, "evidence"));
  const stepsPath = path.join(evidenceDir, "staging-delivery-steps.json");
  if (existsSync(stepsPath)) throw fail("Preserve previous staging delivery; reconcile uncertainty before another attempt");
  const events = [], uploads = [];
  const record = async value => { events.push(value); await writeOutput(root, stepsPath, JSON.stringify(events, null, 2) + "\n"); };
  const active = () => { signal?.throwIfAborted();
    if (canonicalJson(stagingAdmission(env, true)) !== canonicalJson(config)) throw fail("Staging environment changed during delivery"); };
  await writeOutput(root, path.join(evidenceDir, "staging-registration-input.json"), metadataBytes(metadata));
  await record({ step: "admitted", originalOwner: data.owner, delivery: config.delivery });
  try {
    active();
    await verifyWorkerEnvironment(config.serviceUrl, "rehearsal", fetcher, signal);
    active();
    const preflight = await preflightFirmware(metadata, { serviceUrl: config.serviceUrl, mode: "rehearsal",
      deployToken: env.TRACE_DEPLOY_TOKEN, fetcher, signal });
    await record({ step: "preflight", ...preflight });
    active();
    return await bucketFactory({ bucketName: config.bucketName, accountId: config.accountId, env, signal }, async bucket => {
      for (const asset of metadata.assets) {
        active();
        const result = await bounded(() => uploadFirmwareAsset(metadata, asset.fileName, data.bytesByName.get(asset.fileName), bucket), signal);
        uploads.push(result);
        await record({ step: "r2-full-readback", ...result });
      }
      active();
      const ready = readyProjection(metadata);
      await record({ step: "registration-request", retries: 1, metadataSha256: digest(metadataBytes(ready)) });
      const registration = await registerFirmware(ready, { serviceUrl: config.serviceUrl, deployToken: env.TRACE_DEPLOY_TOKEN,
        fetcher, retries: 1, signal });
      await record({ step: "registration-ready", ...registration });
      const evidence = { schema: STAGING_PROTOCOL, publicationProtocol: STAGING_PROTOCOL, mode: "immutable-candidate-staging",
        candidateInputMode: config.inputIdentity.mode,
        productionPublishable: false, approvalEligible: false, environment: "staging", originalOwner: data.owner,
        delivery: config.delivery, sourceProofSha256: data.sourceProofSha256,
        metadataSha256: digest(metadataBytes(ready)), originalArchive: data.proof.archive,
        preflight, uploads, registration, sourceCompilations: 0, finalizations: 0, packageGenerations: 0, referenceSearches: 0,
        githubRelease: "NOT_RUN", channels: "UNCHANGED", deviceOperations: "NOT_RUN" };
      await writeOutput(root, path.join(evidenceDir, "staging-registration-ready.json"), metadataBytes(ready));
      await writeOutput(root, path.join(evidenceDir, "staging-delivery-evidence.json"), JSON.stringify(evidence, null, 2) + "\n");
      return evidence;
    });
  } catch (error) {
    await record({ step: "failed-or-uncertain", code: error?.code ?? "BACKEND_UNAVAILABLE", automaticRetry: false });
    throw error;
  }
}

async function main() {
  const [command, ...argv] = process.argv.slice(2);
  if (!["gate", "inputs", "execute"].includes(command)) throw fail("Expected staging gate, inputs or execute");
  const options = args(argv, ["output-dir", "python"]), root = projectRoot(), env = process.env;
  const config = verifyStagingCheckout(root, env, command === "execute");
  const out = outputPath(root, path.resolve(root, options["output-dir"] ?? `.cache/p51-staging/run-${config.delivery.runId}-${config.delivery.runAttempt}`));
  if (command === "gate") { process.stdout.write("P51_STAGING_ONLY_ADMITTED\n"); return; }
  if (command === "inputs") {
    if (existsSync(out)) throw fail("Preserve previous staging inputs");
    const childEnv = { ...env };
    for (const name of Object.keys(childEnv)) if (/^(TRACE_|CLOUDFLARE_|CF_|GH_|GITHUB_TOKEN|OTA_)/.test(name)) delete childEnv[name];
    try {
      const result = await promisify(execFile)(options.python ?? "python3", ["-I", "-S", "-B", "-X", "utf8",
        path.join(root, env.INPUT_CANDIDATE_MODE === "normal-delta" ? "Tools/ota/p51-normal-staging-inputs.py" : "Tools/ota/p51-staging-inputs.py"), "--root-out", out],
      { cwd: root, env: childEnv, timeout: 90000, maxBuffer: 16 * 1024 * 1024, windowsHide: true });
      await writeOutput(root, path.join(out, "evidence/inputs-process.json"), JSON.stringify({ exitCode: 0, stdout: result.stdout, stderr: result.stderr }) + "\n");
    } catch (error) {
      await writeOutput(root, path.join(out, "evidence/inputs-process.json"), JSON.stringify({ exitCode: error.code,
        signal: error.signal, stdout: error.stdout, stderr: error.stderr }) + "\n");
      throw fail("Immutable staging input admission failed; original diagnostic retained");
    }
    await loadStagingInputs(root, out, inputsFor(env));
    process.stdout.write("P51_STAGING_ORIGINAL_BYTES_ADMITTED\n");
    return;
  }
  const controller = new AbortController(), cancel = () => controller.abort();
  process.once("SIGINT", cancel); process.once("SIGTERM", cancel);
  try {
    const evidence = await executeStaging({ root, out, env, signal: controller.signal });
    process.stdout.write(JSON.stringify({ ok: true, mode: evidence.mode, metadataSha256: evidence.metadataSha256,
      releaseId: evidence.registration.releaseId, state: evidence.registration.state }) + "\n");
  } finally { process.removeListener("SIGINT", cancel); process.removeListener("SIGTERM", cancel); }
}
if (process.argv[1] && import.meta.url === pathToFileURL(path.resolve(process.argv[1])).href) main().catch(failure);
