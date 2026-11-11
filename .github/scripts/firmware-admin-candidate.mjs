import { readFile } from "node:fs/promises";
import path from "node:path";
import { pathToFileURL } from "node:url";
import { args, CliError, failure, outputPath, projectRoot, required, writeOutput } from "../../app/bluetooth_flutter_Trace/cloudflare/update-service/scripts/firmware-cli.mjs";
import { canonicalJson, parseFirmwareRegistration } from "../../app/bluetooth_flutter_Trace/cloudflare/update-service/scripts/firmware-schema.mjs";
import { digest, metadataBytes, prepareOriginalAdminCandidate, readyProjection } from "../../app/bluetooth_flutter_Trace/cloudflare/update-service/scripts/prepare-firmware-release.mjs";
import { verifyBuildKeyBinding } from "../../app/bluetooth_flutter_Trace/cloudflare/update-service/scripts/firmware-release-key.mjs";
import { verifyBuildConfiguration } from "../../app/bluetooth_flutter_Trace/cloudflare/update-service/scripts/firmware-build-profile.mjs";
import { createFirmwareS3Bucket } from "../../app/bluetooth_flutter_Trace/cloudflare/update-service/scripts/firmware-s3.mjs";
import { uploadFirmwareAsset } from "../../app/bluetooth_flutter_Trace/cloudflare/update-service/scripts/upload-firmware-r2-asset.mjs";
import { preflightFirmware } from "../../app/bluetooth_flutter_Trace/cloudflare/update-service/scripts/firmware-preflight-client.mjs";
import { registerFirmware } from "../../app/bluetooth_flutter_Trace/cloudflare/update-service/scripts/register-firmware-release.mjs";
import { verifyWorkerEnvironment } from "../../app/bluetooth_flutter_Trace/cloudflare/update-service/scripts/firmware-release-pipeline.mjs";
import { adminCandidateAdmission, ADMIN_CANDIDATE_ORIGIN, ADMIN_CANDIDATE_BUCKET } from "./firmware-admin-context.mjs";

export { adminCandidateAdmission, ADMIN_CANDIDATE_ORIGIN, ADMIN_CANDIDATE_BUCKET };

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

export async function packageCandidate(root, out, env) {
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
  const result = await prepareOriginalAdminCandidate({ root, app: path.join(source, "app/X-Track-App-GCC.bin"),
    boot: path.join(source, "boot/X-Track-Boot.bin"), build, release, repository: env.GITHUB_REPOSITORY,
    buildEvidenceDir: source, outputDir: path.join(out, "prepared"), aesKey: env.OTA_AES_KEY,
    candidateEnv: env, sourceProof: path.join(source, "source-proof.json"),
    bsdiff: env.BSDIFF_EXE ?? process.env.BSDIFF_EXE });
  verifyAdminCandidateAssets(result.metadata, result.summary, owner);
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

export function verifyAdminCandidateAssets(metadata, preparation, owner) {
  const patches = metadata.assets.filter(asset => asset.kind === "patch");
  if (owner.baseVersionName === null) {
    if (patches.length || preparation.base !== null || preparation.patchByteEqual !== null) {
      throw new CliError("Unexpected delta in a full-only Admin candidate");
    }
  } else if (patches.length !== 1 || preparation.patchByteEqual !== true
      || preparation.base?.provenanceKind !== "original-admin-pinned-base-v1"
      || preparation.base.versionName !== owner.baseVersionName
      || preparation.base.versionCode !== owner.baseVersionCode
      || patches[0].baseVersionCode !== owner.baseVersionCode
      || patches[0].baseImageSha256 !== preparation.base.imageSha256
      || preparation.patchComparison?.baseImageSha256 !== preparation.base.imageSha256
      || preparation.patchComparison?.targetImageSha256 !== metadata.targetImageSha256) {
    throw new CliError("Admin delta metadata must match the verified base and reconstruction");
  }
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
  const preparation = JSON.parse(await readFile(path.join(prepared, "verification.json")));
  if (result.workflowCommit !== owner.workflowCommit || result.runId !== owner.runId || metadata.runId !== owner.runId
      || metadata.versionCode !== owner.versionCode || metadata.commitSha !== result.sourceCommit
      || result.baseVersionName !== owner.baseVersionName || result.baseVersionCode !== owner.baseVersionCode
      || result.metadataSha256 !== digest(metadataBytes(metadata)) || result.normalPackages !== true
      || result.verificationSha256 !== digest(await readFile(path.join(prepared, "verification.json")))
      || result.sourceProofSha256 !== digest(await readFile(path.join(out, "source/source-proof.json")))) {
    throw new CliError("Normal package evidence does not belong to this dispatch");
  }
  verifyAdminCandidateAssets(metadata, preparation, owner);
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
