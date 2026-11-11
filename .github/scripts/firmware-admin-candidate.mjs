import { readFile } from "node:fs/promises";
import path from "node:path";
import { pathToFileURL } from "node:url";
import { args, CliError, failure, outputPath, projectRoot, required, writeOutput } from "../../app/bluetooth_flutter_Trace/cloudflare/update-service/scripts/firmware-cli.mjs";
import { canonicalJson, parseFirmwareRegistration, versionCodeFor } from "../../app/bluetooth_flutter_Trace/cloudflare/update-service/scripts/firmware-schema.mjs";
import { digest, metadataBytes, prepareFirmwareRelease, readyProjection } from "../../app/bluetooth_flutter_Trace/cloudflare/update-service/scripts/prepare-firmware-release.mjs";
import { verifyBuildKeyBinding } from "../../app/bluetooth_flutter_Trace/cloudflare/update-service/scripts/firmware-release-key.mjs";
import { verifyBuildConfiguration } from "../../app/bluetooth_flutter_Trace/cloudflare/update-service/scripts/firmware-build-profile.mjs";
import { createFirmwareS3Bucket } from "../../app/bluetooth_flutter_Trace/cloudflare/update-service/scripts/firmware-s3.mjs";
import { uploadFirmwareAsset } from "../../app/bluetooth_flutter_Trace/cloudflare/update-service/scripts/upload-firmware-r2-asset.mjs";
import { preflightFirmware } from "../../app/bluetooth_flutter_Trace/cloudflare/update-service/scripts/firmware-preflight-client.mjs";
import { registerFirmware } from "../../app/bluetooth_flutter_Trace/cloudflare/update-service/scripts/register-firmware-release.mjs";
import { verifyWorkerEnvironment } from "../../app/bluetooth_flutter_Trace/cloudflare/update-service/scripts/firmware-release-pipeline.mjs";

export const ADMIN_CANDIDATE_ORIGIN = "https://trace-update-service-staging.tangjichentudou.workers.dev";
export const ADMIN_CANDIDATE_BUCKET = "trace-update-staging-releases";

export function adminCandidateAdmission(env) {
  if (env.GITHUB_ACTIONS !== "true" || env.GITHUB_EVENT_NAME !== "workflow_dispatch"
      || env.GITHUB_REPOSITORY !== "Eitan-S-23/E-Track" || env.INPUT_PREPARE_ADMIN_CANDIDATE !== "true"
      || env.OTA_BOOT_CHAIN_READY !== "false" || env.INPUT_FIRMWARE_BUILD_PROFILE !== "p34-v2-candidate"
      || !/^[0-9a-f]{40}$/.test(env.GITHUB_SHA ?? "") || env.INPUT_CANDIDATE_REVIEWED_COMMIT !== env.GITHUB_SHA
      || !/^[1-9][0-9]*$/.test(env.GITHUB_RUN_ID ?? "") || env.GITHUB_RUN_ATTEMPT !== "1"
      || ["INPUT_PUBLISH", "INPUT_REHEARSAL", "INPUT_CHECK_BINDINGS", "INPUT_PACKAGE_CANDIDATE", "INPUT_STAGE_CANDIDATE"]
        .some(name => env[name] !== "false")
      || env.INPUT_CANDIDATE_BASE_VERSION || env.INPUT_CANDIDATE_FULL_BASE_VERSION || env.INPUT_APPROVED_REHEARSAL_RUN_ID) {
    throw new CliError("Normal Admin candidates require an explicit locked-production-gate dispatch; no mixed mode or automatic rerun");
  }
  const versionCode = versionCodeFor(env.INPUT_VERSION_NAME);
  if (versionCode !== 30321 && versionCode <= 30322) throw new CliError("Select the actual installed V2 baseline or a fresh normal version above 3.3.22");
  if (!env.INPUT_RELEASE_NOTES?.trim() || env.INPUT_RELEASE_NOTES.length > 8000) throw new CliError("Candidate release notes are required");
  return { workflowCommit: env.GITHUB_SHA, runId: env.GITHUB_RUN_ID, versionName: env.INPUT_VERSION_NAME, versionCode };
}

export async function apiTokenS3Credentials(token, fetcher = fetch) {
  if (!token || /\s/.test(token)) throw new CliError("Existing R2-capable API credential is required");
  const response = await fetcher("https://api.cloudflare.com/client/v4/user/tokens/verify", {
    headers: { Authorization: `Bearer ${token}` }, redirect: "error", signal: AbortSignal.timeout(30000) });
  if (!response.ok) throw new CliError("Existing R2 token verification failed");
  const value = await response.json();
  if (value.success !== true || value.result?.status !== "active" || !/^[0-9a-f]{32}$/.test(value.result?.id ?? "")) {
    throw new CliError("Existing R2 token is not active");
  }
  // Documented R2 derivation, not a new token, scope expansion or rotation.
  return { accessKeyId: value.result.id, secretAccessKey: digest(Buffer.from(token)) };
}

async function packageCandidate(root, out, env) {
  const owner = adminCandidateAdmission(env);
  if (Object.entries(env).some(([name, value]) => value && /^(CLOUDFLARE_|CF_|TRACE_|GH_|GITHUB_TOKEN)/.test(name))) {
    throw new CliError("Packaging must not receive cloud or publishing credentials");
  }
  const source = path.join(out, "source");
  const proof = JSON.parse(await readFile(path.join(source, "source-proof.json")));
  const original = JSON.parse(await readFile(path.join(source, "gcc-build-inputs.json")));
  if (proof.schema !== "original-admin-normal-source-proof-v1" || proof.verifiedAgainst !== owner.workflowCommit
      || proof.sourceMatches !== true || proof.importedBenchmarkPackages !== 0 || proof.sourceCommit !== original.commitSha) {
    throw new CliError("Normal candidate GCC provenance mismatch");
  }
  for (const pin of proof.files) {
    const bytes = await readFile(outputPath(root, pin.path));
    if (bytes.length !== pin.bytes || digest(bytes) !== pin.sha256) throw new CliError("Admitted GCC input changed");
  }
  verifyBuildKeyBinding(original, env);
  verifyBuildConfiguration(original, "p34-v2-candidate");
  const build = { ...original, versionName: owner.versionName, versionCode: owner.versionCode };
  const release = { releaseTag: `mcu-e-track-at32f435-v${owner.versionName}`, runId: owner.runId,
    commitSha: original.commitSha, versionName: owner.versionName, releaseNotes: env.INPUT_RELEASE_NOTES,
    hardwareRevision: 1, layoutId: 1, minBootVersion: 1, minProtocolVersion: 1,
    targetHardware: "AT32F435RGT7", minAppVersionCode: 100 };
  const result = await prepareFirmwareRelease({ root, app: path.join(source, "app/X-Track-App-GCC.bin"),
    boot: path.join(source, "boot/X-Track-Boot.bin"), build, release, repository: env.GITHUB_REPOSITORY,
    buildEvidenceDir: source, outputDir: path.join(out, "prepared"), aesKey: env.OTA_AES_KEY });
  if (owner.versionCode === 30321 && !(await readFile(path.join(result.outputDir, "app-final.bin")))
    .equals(await readFile(path.join(source, "installed-baseline.bin")))) throw new CliError("Installed baseline identity changed");
  await writeOutput(root, path.join(out, "package-result.json"), JSON.stringify({ ...owner,
    sourceCommit: original.commitSha, metadataSha256: digest(metadataBytes(result.metadata)),
    verificationSha256: digest(await readFile(path.join(result.outputDir, "verification.json"))),
    sourceProofSha256: digest(await readFile(path.join(source, "source-proof.json"))),
    normalPackages: true, sourceCompilations: 0, importedBenchmarkPackages: 0, githubReleaseCreated: false,
    productionApproved: false, channelPublished: false }, null, 2) + "\n");
  return { ok: true, versionName: owner.versionName, assetsPrepared: result.metadata.assets.length };
}

async function registerCandidate(root, out, env) {
  const owner = adminCandidateAdmission(env);
  if (env.OTA_AES_KEY || env.TRACE_UPDATE_SERVICE_URL !== ADMIN_CANDIDATE_ORIGIN || env.TRACE_R2_BUCKET !== ADMIN_CANDIDATE_BUCKET
      || !/^[0-9a-f]{32}$/.test(env.CLOUDFLARE_ACCOUNT_ID ?? "") || !env.TRACE_DEPLOY_TOKEN) {
    throw new CliError("Registration requires the exact original staging service/bucket and no packaging key");
  }
  const prepared = path.join(out, "prepared");
  const metadata = parseFirmwareRegistration(JSON.parse(await readFile(path.join(prepared, "cloudflare-firmware-release-metadata.json"))), env.GITHUB_REPOSITORY, false);
  const result = JSON.parse(await readFile(path.join(out, "package-result.json")));
  if (result.workflowCommit !== owner.workflowCommit || result.runId !== owner.runId || metadata.runId !== owner.runId
      || metadata.versionCode !== owner.versionCode || metadata.commitSha !== result.sourceCommit
      || result.metadataSha256 !== digest(metadataBytes(metadata)) || result.normalPackages !== true
      || result.verificationSha256 !== digest(await readFile(path.join(prepared, "verification.json")))
      || result.sourceProofSha256 !== digest(await readFile(path.join(out, "source/source-proof.json")))) {
    throw new CliError("Normal package evidence does not belong to this dispatch");
  }
  await verifyWorkerEnvironment(ADMIN_CANDIDATE_ORIGIN, "rehearsal");
  const preflight = await preflightFirmware(metadata, { serviceUrl: ADMIN_CANDIDATE_ORIGIN, mode: "rehearsal", deployToken: env.TRACE_DEPLOY_TOKEN });
  await writeOutput(root, path.join(out, "preflight.json"), JSON.stringify(preflight, null, 2) + "\n");
  const credentials = await apiTokenS3Credentials(env.CLOUDFLARE_API_TOKEN);
  const platform = createFirmwareS3Bucket({ accountId: env.CLOUDFLARE_ACCOUNT_ID, bucketName: ADMIN_CANDIDATE_BUCKET, credentials });
  const uploads = [];
  try {
    for (const asset of metadata.assets) {
      uploads.push(await uploadFirmwareAsset(metadata, asset.fileName, await readFile(path.join(prepared, asset.fileName)), platform.bucket));
      await writeOutput(root, path.join(out, "uploads.json"), JSON.stringify(uploads, null, 2) + "\n");
    }
  } finally { platform.dispose(); }
  const ready = readyProjection(metadata);
  await writeOutput(root, path.join(out, "ready-metadata.json"), metadataBytes(ready));
  const registration = await registerFirmware(ready, { serviceUrl: ADMIN_CANDIDATE_ORIGIN, deployToken: env.TRACE_DEPLOY_TOKEN });
  await writeOutput(root, path.join(out, "registration.json"), JSON.stringify(registration, null, 2) + "\n");
  return { ok: true, versionName: owner.versionName, registration, uploads,
    originalAdmin: true, productionApproved: false, channelPublished: false, deviceOperations: 0 };
}

async function main() {
  const [action, ...argv] = process.argv.slice(2);
  const options = args(argv, ["out"]);
  const root = projectRoot(), out = outputPath(root, required(options, "out"));
  adminCandidateAdmission(process.env);
  if (action === "gate") return;
  if (!["package", "register"].includes(action)) throw new CliError("Expected gate, package or register");
  const result = await (action === "package" ? packageCandidate : registerCandidate)(root, out, process.env);
  await writeOutput(root, path.join(out, action + "-receipt.json"), canonicalJson(result) + "\n");
  process.stdout.write(JSON.stringify(result) + "\n");
}
if (process.argv[1] && import.meta.url === pathToFileURL(path.resolve(process.argv[1])).href) main().catch(failure);
