import { existsSync } from "node:fs";
import { readFile } from "node:fs/promises";
import path from "node:path";
import { args, CliError, failure, outputPath, projectRoot, required, writeOutput } from "../../app/bluetooth_flutter_Trace/cloudflare/update-service/scripts/firmware-cli.mjs";
import { canonicalJson, versionCodeFor } from "../../app/bluetooth_flutter_Trace/cloudflare/update-service/scripts/firmware-schema.mjs";
import { captureBuildInputs, digest, metadataBytes, prepareFirmwareRelease, readyProjection } from "../../app/bluetooth_flutter_Trace/cloudflare/update-service/scripts/prepare-firmware-release.mjs";
import { firmwareGitHub } from "../../app/bluetooth_flutter_Trace/cloudflare/update-service/scripts/firmware-github-release.mjs";
import { publishPreparedRelease, releaseConfig, verifyPromotion } from "../../app/bluetooth_flutter_Trace/cloudflare/update-service/scripts/firmware-release-pipeline.mjs";
import { withFirmwareBucket } from "../../app/bluetooth_flutter_Trace/cloudflare/update-service/scripts/upload-firmware-r2-asset.mjs";

async function main() {
  const [command, ...argv] = process.argv.slice(2);
  if (!["capture", "execute", "development"].includes(command)) throw new CliError("Expected capture, development or execute");
  const options = args(argv, ["app", "boot", "build-inputs", "output", "output-dir", "reference-dir",
    "version", "commit", "build-timestamp", "bsdiff", "python"]);
  const root = projectRoot();
  const app = path.resolve(required(options, "app"));
  const boot = path.resolve(required(options, "boot"));
  if (command === "capture") {
    const manifest = await captureBuildInputs({ app, boot, commitSha: required(options, "commit"),
      versionName: required(options, "version"), buildTimestamp: Number(required(options, "build-timestamp")) });
    await writeOutput(root, required(options, "output"), JSON.stringify(manifest, null, 2) + "\n");
    process.stdout.write(JSON.stringify({ ok: true, ...manifest }) + "\n");
    return;
  }
  const build = JSON.parse(await readFile(required(options, "build-inputs"), "utf8"));
  const outputDir = outputPath(root, required(options, "output-dir"));
  if (existsSync(outputDir)) throw new CliError("Output directory already exists; preserve the previous attempt");
  const controller = new AbortController();
  const cancel = () => controller.abort();
  process.once("SIGTERM", cancel); process.once("SIGINT", cancel);
  try {
    if (command === "development") {
      if (process.env.OTA_AES_KEY || process.env.CLOUDFLARE_API_TOKEN || process.env.TRACE_DEPLOY_TOKEN) {
        throw new CliError("Development validation must not receive release credentials");
      }
      const release = { releaseTag: `mcu-e-track-at32f435-v${build.versionName}`, runId: process.env.GITHUB_RUN_ID ?? "1",
        commitSha: build.commitSha, versionName: build.versionName, releaseNotes: "DEVELOPMENT ONLY; not a release or rehearsal",
        hardwareRevision: 1, layoutId: 1, minBootVersion: 1, minProtocolVersion: 1, targetHardware: "AT32F435RGT7", minAppVersionCode: 0 };
      const result = await prepareFirmwareRelease({ root, app, boot, build, release, outputDir,
        repository: process.env.GITHUB_REPOSITORY ?? "Eitan-S-23/E-Track", aesKey: "01".repeat(16),
        python: options.python ?? "python3" });
      await writeOutput(root, path.join(outputDir, "DEVELOPMENT-ONLY.json"), JSON.stringify({ installable: false,
        formalBase: "NOT_USED", rehearsal: "NOT_RUN", remoteEffects: "NOT_RUN", testKey: "isolated fixture key" }) + "\n");
      process.stdout.write(JSON.stringify({ ok: true, developmentOnly: true, ...result.summary }) + "\n");
      return;
    }
    const env = process.env;
    const config = releaseConfig(env);
    if (build.commitSha !== env.GITHUB_SHA || build.versionName !== env.RELEASE_VERSION
      || build.versionCode !== versionCodeFor(env.RELEASE_VERSION)) throw new CliError("Build artifact does not belong to this release run");
    const release = { releaseTag: `mcu-e-track-at32f435-v${build.versionName}`, runId: config.canonicalRunId,
      commitSha: env.GITHUB_SHA, versionName: build.versionName, releaseNotes: env.INPUT_RELEASE_NOTES ?? "",
      hardwareRevision: 1, layoutId: 1, minBootVersion: 1,
      minProtocolVersion: Number(env.TRACE_FIRMWARE_MIN_PROTOCOL_VERSION), targetHardware: "AT32F435RGT7",
      minAppVersionCode: Number(env.TRACE_FIRMWARE_MIN_APP_VERSION_CODE) };
    const referenceRoot = options["reference-dir"] && path.resolve(options["reference-dir"]);
    if ((config.mode === "production" || Number(config.executionAttempt) > 1) && !referenceRoot) {
      throw new CliError("Production and rehearsal retries require the original immutable reference artifact");
    }
    let referencePreparation, referenceMetadata;
    if (referenceRoot) {
      referencePreparation = await readFile(path.join(referenceRoot, "prepared/verification.json"));
      referenceMetadata = await readFile(path.join(referenceRoot, "prepared/cloudflare-firmware-release-metadata.json"));
      const previous = JSON.parse(referencePreparation);
      if (canonicalJson(previous.build) !== canonicalJson(build) || previous.runId !== config.canonicalRunId) {
        throw new CliError("Rehearsal reference GCC App/Boot/provenance differs from the current build");
      }
    }
    const github = firmwareGitHub({ repository: env.GITHUB_REPOSITORY, token: env.GITHUB_TOKEN, signal: controller.signal });
    const base = JSON.parse(env.OTA_PREVIOUS_RELEASE_JSON);
    if (referencePreparation && canonicalJson(JSON.parse(referencePreparation).base) !== canonicalJson(base)) {
      throw new CliError("Patch base provenance changed since rehearsal");
    }
    const source = await github.releaseBase(base, release, env.OTA_APPROVED_BOOTSTRAP_BASELINE_SHA256, config.mode);
    const inputs = outputPath(root, path.join(path.dirname(outputDir), "inputs"));
    const baseFile = outputPath(root, path.join(inputs, "base-source.bin"));
    await writeOutput(root, baseFile, source.bytes);
    await writeOutput(root, path.join(inputs, "base-provenance.json"), JSON.stringify(source.evidence, null, 2) + "\n");
    const prepared = await prepareFirmwareRelease({ root, app, boot, build, release, repository: env.GITHUB_REPOSITORY,
      base, baseFile, outputDir, bsdiff: options.bsdiff, python: options.python ?? "python3",
      referenceDir: referenceRoot && path.join(referenceRoot, "prepared") });
    if (referenceMetadata && !metadataBytes(readyProjection(JSON.parse(referenceMetadata))).equals(metadataBytes(readyProjection(prepared.metadata)))) {
      throw new CliError("Reproduced metadata differs from the reference attempt");
    }
    let approval;
    if (config.mode === "production") {
      const approvedRun = await github.json(`/actions/runs/${config.canonicalRunId}/attempts/${env.OTA_APPROVED_REHEARSAL_ATTEMPT}`);
      approval = { approvedMetadata: referenceMetadata, approvedPreparation: referencePreparation, approvedRun,
        approvedEvidence: await readFile(path.join(referenceRoot, "prepared/release-evidence.json")) };
      verifyPromotion(prepared.metadata, { ...approval, config, env });
    }
    controller.signal.throwIfAborted();
    const evidence = await withFirmwareBucket({ root, bucketName: config.bucketName, accountId: config.accountId,
      databaseId: config.databaseId, databaseName: config.databaseName }, (bucket, db) => publishPreparedRelease({
        root, assetsDir: outputDir, metadata: prepared.metadata, config, env, bucket, db, github, approval,
        deployToken: env.TRACE_DEPLOY_TOKEN, signal: controller.signal }));
    process.stdout.write(JSON.stringify({ ok: true, mode: config.mode, metadataSha256: evidence.metadataSha256,
      evidenceSha256: digest(await readFile(path.join(outputDir, "release-evidence.json"))),
      releaseId: evidence.registration.releaseId, state: evidence.registration.state }) + "\n");
  } finally {
    process.removeListener("SIGTERM", cancel); process.removeListener("SIGINT", cancel);
  }
}
main().catch(failure);
