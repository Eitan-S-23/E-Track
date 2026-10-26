import { readFile } from "node:fs/promises";
import path from "node:path";
import { CliError, outputPath, writeOutput } from "./firmware-cli.mjs";
import { canonicalJson, parseFirmwareRegistration } from "./firmware-schema.mjs";
import { digest, metadataBytes, readyProjection } from "./prepare-firmware-release.mjs";
import { uploadFirmwareAsset } from "./upload-firmware-r2-asset.mjs";
import { registerFirmware } from "./register-firmware-release.mjs";
import { approvedFirmwareKey } from "./firmware-release-key.mjs";
import { s3Credentials } from "./firmware-s3.mjs";
import { preflightFirmware } from "./firmware-preflight-client.mjs";
import { firmwareBuildProfile, verifyBuildConfiguration } from "./firmware-build-profile.mjs";
export { verifyMonotonic } from "./firmware-monotonic.mjs";

const fail = message => new CliError(message, "RELEASE_CONFLICT", 1);
const cancelled = () => new CliError("Release execution cancelled", "BACKEND_UNAVAILABLE", 1);
const active = signal => { if (signal?.aborted) throw cancelled(); };
export const PUBLICATION_PROTOCOL = "s3-worker-preflight-v1";

export function releaseConfig(env) {
  const buildProfile = firmwareBuildProfile(env.INPUT_FIRMWARE_BUILD_PROFILE);
  const mode = env.FIRMWARE_RELEASE_MODE;
  if (env.GITHUB_EVENT_NAME !== "workflow_dispatch" || env.INPUT_CHECK_BINDINGS === "true" || !["rehearsal", "production"].includes(mode)
    || (mode === "production" ? env.INPUT_PUBLISH !== "true" || env.INPUT_REHEARSAL === "true"
      : env.INPUT_REHEARSAL !== "true" || env.INPUT_PUBLISH === "true")) throw new CliError("Only an explicit, unambiguous release dispatch can use cloud bindings");
  if (env.OTA_BOOT_CHAIN_READY !== (mode === "production" ? "true" : "false")) throw fail("Boot-chain gate is not in the required state");
  const keys = ["CLOUDFLARE_ACCOUNT_ID", "TRACE_R2_ACCESS_KEY_ID", "TRACE_R2_SECRET_ACCESS_KEY", "TRACE_UPDATE_SERVICE_URL", "TRACE_DEPLOY_TOKEN",
    "TRACE_R2_BUCKET", "OTA_AES_KEY", "GITHUB_TOKEN",
    "GITHUB_REPOSITORY", "GITHUB_SHA", "GITHUB_RUN_ID", "GITHUB_RUN_ATTEMPT", "OTA_PREVIOUS_RELEASE_JSON",
    "TRACE_FIRMWARE_MIN_APP_VERSION_CODE", "TRACE_FIRMWARE_MIN_PROTOCOL_VERSION"];
  for (const key of keys) if (!env[key]) throw new CliError(`Missing release configuration: ${key}`);
  s3Credentials(env);
  if (env.TRACE_D1_DATABASE_ID || env.TRACE_D1_DATABASE_NAME) throw new CliError("Client-selected D1 bindings are not accepted by the release chain");
  approvedFirmwareKey(env);
  for (const key of ["TRACE_DEPLOY_TOKEN", "GITHUB_TOKEN"]) {
    if (/\s/.test(env[key])) throw new CliError("Release credentials must not contain whitespace");
  }
  for (const [key, max] of [["TRACE_FIRMWARE_MIN_APP_VERSION_CODE", 2100000000], ["TRACE_FIRMWARE_MIN_PROTOCOL_VERSION", 255]]) {
    if (!/^(0|[1-9][0-9]*)$/.test(env[key]) || !Number.isSafeInteger(Number(env[key])) || Number(env[key]) > max) {
      throw new CliError(`Invalid numeric release configuration: ${key}`);
    }
  }
  if (!/^[0-9a-f]{32}$/.test(env.CLOUDFLARE_ACCOUNT_ID) || !/^[0-9a-fA-F]{32}$/.test(env.OTA_AES_KEY)
    || !/^[a-z0-9][a-z0-9-]{1,61}[a-z0-9]$/.test(env.TRACE_R2_BUCKET)
    || !/^[0-9a-f]{40}$/.test(env.GITHUB_SHA) || !/^[1-9][0-9]*$/.test(env.GITHUB_RUN_ID)
    || !/^[1-9][0-9]*$/.test(env.GITHUB_RUN_ATTEMPT)) throw new CliError("Invalid explicit release binding or identity");
  let url;
  try { url = new URL(env.TRACE_UPDATE_SERVICE_URL); } catch { throw new CliError("Invalid Worker origin configuration"); }
  if (url.protocol !== "https:" || url.username || url.password || url.search || url.hash || url.pathname !== "/") throw new CliError("Worker binding must be a credential-free HTTPS origin");
  // Renaming the rehearsal bucket must not admit the protected old Trace bucket
  // to production. Neither non-production bucket is a production destination.
  const rehearsalBucket = "e-track-firmware-p41-test-releases";
  if (mode === "rehearsal" ? env.TRACE_R2_BUCKET !== rehearsalBucket
    : env.TRACE_R2_BUCKET !== "e-track-firmware-production-releases") {
    throw new CliError("Staging and production bucket bindings must remain isolated");
  }
  let canonicalRunId = env.GITHUB_RUN_ID;
  if (mode === "production") {
    canonicalRunId = env.INPUT_APPROVED_REHEARSAL_RUN_ID;
    if (!/^[1-9][0-9]*$/.test(canonicalRunId ?? "") || canonicalRunId !== env.OTA_APPROVED_REHEARSAL_RUN_ID
      || !/^[1-9][0-9]*$/.test(env.OTA_APPROVED_REHEARSAL_ATTEMPT ?? "")
      || !/^[0-9a-f]{64}$/.test(env.OTA_APPROVED_REHEARSAL_METADATA_SHA256 ?? "")
      || !/^[0-9a-f]{64}$/.test(env.OTA_APPROVED_REHEARSAL_EVIDENCE_SHA256 ?? "")
      || canonicalRunId === env.GITHUB_RUN_ID) throw new CliError("Explicit approved rehearsal provenance and hashes are required");
  }
  return { mode, canonicalRunId, executionRunId: env.GITHUB_RUN_ID, executionAttempt: env.GITHUB_RUN_ATTEMPT,
    buildProfile, serviceUrl: url.origin, bucketName: env.TRACE_R2_BUCKET, accountId: env.CLOUDFLARE_ACCOUNT_ID };
}

export function verifyPromotion(metadata, { approvedMetadata, approvedEvidence, approvedPreparation, approvedRun, currentBuild, config, env }) {
  const parsed = parseFirmwareRegistration(JSON.parse(approvedMetadata));
  const evidence = JSON.parse(approvedEvidence);
  if (digest(approvedMetadata) !== env.OTA_APPROVED_REHEARSAL_METADATA_SHA256
    || digest(approvedEvidence) !== env.OTA_APPROVED_REHEARSAL_EVIDENCE_SHA256
    || !approvedPreparation || digest(approvedPreparation) !== evidence.preparationSha256
    || !metadataBytes(parsed).equals(approvedMetadata) || !metadataBytes(readyProjection(metadata)).equals(approvedMetadata)) {
    throw fail("Rebuilt assets/canonical metadata differ from approved rehearsal bytes");
  }
  const previousBuild = JSON.parse(approvedPreparation).build;
  verifyBuildConfiguration(previousBuild, config.buildProfile);
  verifyBuildConfiguration(currentBuild, config.buildProfile);
  if (canonicalJson(previousBuild) !== canonicalJson(currentBuild)) throw fail("Approved rehearsal GCC build configuration/provenance differs");
  if (metadata.runId !== config.canonicalRunId || parsed.commitSha !== env.GITHUB_SHA
    || String(approvedRun.id) !== config.canonicalRunId || approvedRun.head_sha !== env.GITHUB_SHA
    || approvedRun.path !== ".github/workflows/firmware-build.yml" || approvedRun.event !== "workflow_dispatch"
    || approvedRun.conclusion !== "success" || String(approvedRun.run_attempt) !== env.OTA_APPROVED_REHEARSAL_ATTEMPT
    || evidence.publicationProtocol !== PUBLICATION_PROTOCOL
    || evidence.preflight?.metadataSha256 !== evidence.metadataSha256 || evidence.preflight?.environment !== "staging"
    || evidence.preflight?.ok !== true || evidence.preflight?.unresolvedLegacyChannels !== 0
    || evidence.mode !== "rehearsal" || evidence.executionRunId !== config.canonicalRunId
    || evidence.executionAttempt !== env.OTA_APPROVED_REHEARSAL_ATTEMPT
    || evidence.commitSha !== metadata.commitSha || evidence.metadataSha256 !== digest(approvedMetadata)
    || evidence.registration?.state !== "ready" || evidence.replay?.idempotent !== true
    || evidence.registration.releaseId !== evidence.replay.releaseId
    || evidence.uploads?.length !== metadata.assets.length) throw fail("Approved rehearsal run/evidence binding mismatch");
  for (const asset of metadata.assets) {
    const result = evidence.uploads.find(r => r.fileName === asset.fileName);
    if (!result || result.ok !== true || !["UPLOADED", "ALREADY_PRESENT"].includes(result.status)
      || result.sha256 !== asset.sha256 || result.sizeBytes !== asset.sizeBytes || result.r2Key !== asset.r2Key) throw fail("Approved R2 readback evidence mismatch");
  }
}

export async function verifyWorkerEnvironment(serviceUrl, mode, fetcher = fetch, signal) {
  const response = await fetcher(`${serviceUrl}/healthz`, { redirect: "error", signal: signal
    ? AbortSignal.any([signal, AbortSignal.timeout(20000)]) : AbortSignal.timeout(20000) });
  if (!response.ok) throw new CliError("Worker health check failed", "BACKEND_UNAVAILABLE", 1);
  const health = await response.json();
  if (health.ok !== true || health.environment !== (mode === "rehearsal" ? "staging" : "prod")) throw fail("Worker is not the selected release environment");
}

async function bounded(operation, signal) {
  active(signal);
  let timer, abort;
  const stop = new Promise((_, reject) => {
    timer = setTimeout(() => reject(new CliError("R2 operation exceeded 300 seconds", "R2_VERIFY_FAILED", 1)), 300000);
    abort = () => reject(cancelled()); signal?.addEventListener("abort", abort, { once: true });
  });
  try { return await Promise.race([operation(), stop]); }
  finally { clearTimeout(timer); signal?.removeEventListener("abort", abort); }
}

export async function publishPreparedRelease({ root, assetsDir, metadata, config, bucket, github,
  deployToken, fetcher = fetch, signal, approval, env }) {
  if (canonicalJson(releaseConfig(env)) !== canonicalJson(config)) throw new CliError("Release binding changed after preflight");
  if (!["rehearsal", "production"].includes(config.mode)) throw new CliError("Checks/nightly may not publish or register");
  active(signal);
  metadata = parseFirmwareRegistration(metadata, env.GITHUB_REPOSITORY, false);
  if (metadata.runId !== config.canonicalRunId || metadata.commitSha !== env.GITHUB_SHA) throw fail("Release provenance does not match execution");
  const preparationBytes = await readFile(path.join(assetsDir, "verification.json"));
  const preparation = JSON.parse(preparationBytes);
  verifyBuildConfiguration(preparation.build, config.buildProfile);
  if (config.mode === "production") verifyPromotion(metadata, { ...approval, currentBuild: preparation.build, config, env });
  const bytesByName = new Map();
  for (const asset of metadata.assets) {
    const bytes = await readFile(path.join(assetsDir, asset.fileName));
    if (bytes.length !== asset.sizeBytes || digest(bytes) !== asset.sha256) throw fail("Local release asset differs from metadata");
    bytesByName.set(asset.fileName, bytes);
  }
  const preparationSha256 = digest(preparationBytes);
  const metadataPath = outputPath(root, path.join(assetsDir, "cloudflare-firmware-release-metadata.json"));
  const evidencePath = outputPath(root, path.join(assetsDir, "release-evidence.json"));
  const attemptsPath = outputPath(root, path.join(assetsDir, "release-steps.json"));
  const events = [];
  const record = async value => { events.push(value); await writeOutput(root, attemptsPath, JSON.stringify(events, null, 2) + "\n"); };
  await verifyWorkerEnvironment(config.serviceUrl, config.mode, fetcher, signal);
  const before = await preflightFirmware(metadata, { serviceUrl: config.serviceUrl, mode: config.mode, deployToken, fetcher, signal });
  await record({ step: "preflight", ...before });
  active(signal);
  let githubResult = null;
  if (config.mode === "production") {
    githubResult = await github.publish(metadata, bytesByName);
    await record({ step: "github-release-readback", ...githubResult });
  }
  const uploads = [];
  for (const asset of metadata.assets) {
    active(signal);
    const result = await bounded(() => uploadFirmwareAsset(metadata, asset.fileName, bytesByName.get(asset.fileName), bucket), signal);
    uploads.push(result);
    await record({ step: "r2-readback", ...result });
  }
  active(signal);
  const ready = readyProjection(metadata);
  // No projected ready flags are persisted until every real R2 readback passed.
  await writeOutput(root, metadataPath, metadataBytes(ready));
  const registration = await registerFirmware(ready, { serviceUrl: config.serviceUrl, deployToken, fetcher, signal });
  await record({ step: "register", ...registration });
  active(signal);
  const replay = await registerFirmware(ready, { serviceUrl: config.serviceUrl, deployToken, fetcher, signal });
  if (!replay.idempotent || replay.releaseId !== registration.releaseId) throw fail("Registration replay changed release identity");
  await record({ step: "idempotent-replay", ...replay });
  const evidence = { publicationProtocol: PUBLICATION_PROTOCOL, preflight: before,
    mode: config.mode, commitSha: metadata.commitSha, canonicalRunId: metadata.runId,
    executionRunId: config.executionRunId, executionAttempt: config.executionAttempt,
    metadataSha256: digest(metadataBytes(ready)), preparationSha256,
    github: githubResult, uploads, registration, replay };
  await writeOutput(root, evidencePath, JSON.stringify(evidence, null, 2) + "\n");
  return evidence;
}
