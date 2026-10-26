import { createHash } from "node:crypto";
import { spawnSync } from "node:child_process";
import { existsSync } from "node:fs";
import { mkdir, readFile } from "node:fs/promises";
import path from "node:path";
import { pathToFileURL } from "node:url";
import { buildFirmwareMetadata } from "./build-firmware-release-metadata.mjs";
import { args, CliError, failure, outputPath, projectRoot, required, writeOutput } from "./firmware-cli.mjs";
import { assetFileName, canonicalJson, FIRMWARE_MODEL, parseFirmwareRegistration, sha256, versionCodeFor } from "./firmware-schema.mjs";
import { validateKeyBinding } from "./firmware-release-key.mjs";
import { readBuildConfiguration, validateBuildConfiguration } from "./firmware-build-profile.mjs";

export const digest = bytes => createHash("sha256").update(bytes).digest("hex");
export const BOOTSTRAP_PROVENANCE = "inaugural-bootstrap-v1";
const badInput = message => new CliError(message, "INVALID_PARAMETER", 1);
export const readyProjection = value => parseFirmwareRegistration({ ...value,
  assets: value.assets.map(asset => ({ ...asset, r2Verified: true })) });
export const metadataBytes = value => Buffer.from(canonicalJson(value) + "\n");

export async function fileIdentity(file) {
  const bytes = await readFile(file);
  if (!bytes.length) throw badInput("Empty input file");
  return { fileName: path.basename(file), sizeBytes: bytes.length, sha256: digest(bytes) };
}

export async function captureBuildInputs({ app, boot, commitSha, versionName, buildTimestamp, keyBinding, buildConfiguration }) {
  if (path.basename(app) !== "X-Track-App-GCC.bin" || path.basename(boot) !== "X-Track-Boot.bin") {
    throw badInput("Release requires the GCC App and matching Boot, not AC5/legacy images");
  }
  if (!/^[0-9a-f]{40}$/.test(commitSha) || !Number.isSafeInteger(buildTimestamp)
    || buildTimestamp < 0 || buildTimestamp > 0xffffffff) throw new CliError("Invalid build identity");
  return { commitSha, versionName, versionCode: versionCodeFor(versionName), buildTimestamp,
    app: await fileIdentity(app), boot: await fileIdentity(boot),
    ...(keyBinding === undefined ? {} : { keyBinding: validateKeyBinding(keyBinding) }),
    ...(buildConfiguration === undefined ? {} : { buildConfiguration: validateBuildConfiguration(buildConfiguration) }) };
}

export function verifyReferenceBuild(build, referencePreparation, canonicalRunId) {
  const previous = JSON.parse(referencePreparation);
  if (canonicalJson(previous.build) !== canonicalJson(build) || previous.runId !== canonicalRunId) {
    throw badInput("Rehearsal reference GCC App/Boot/provenance differs from the current build");
  }
}

export function validateBaseDescriptor(base, targetVersion, repository, targetCommit) {
  if (!base || !["app", "recovery"].includes(base.kind)
    || base.versionCode !== versionCodeFor(base.versionName) || base.versionCode >= versionCodeFor(targetVersion)
    || !/^[0-9a-f]{40}$/.test(base.commitSha)) {
    throw badInput("Base must identify a lower-version finalized App");
  }
  for (const key of ["imageSha256", "sourceSha256"]) sha256(base[key], key);
  if (!Number.isSafeInteger(base.sourceSizeBytes) || base.sourceSizeBytes <= 0) throw badInput("Invalid base length");
  if (base.provenanceKind === BOOTSTRAP_PROVENANCE) {
    const keys = ["provenanceKind", "isFormalRelease", "kind", "versionName", "versionCode", "commitSha", "buildTimestamp",
      "imageSha256", "sourceSha256", "sourceSizeBytes", "sourceUrl", "archiveCommit", "archivePath", "sourceRunId",
      "sourceRunAttempt", "sourceArtifactId", "sourceArtifactSha256", "provenanceSha256", "targetVersionName", "targetCommitSha"];
    if (canonicalJson(Object.keys(base).sort()) !== canonicalJson(keys.sort()) || base.isFormalRelease !== false
      || base.kind !== "app" || base.imageSha256 !== base.sourceSha256 || base.sourceSizeBytes < 0x460
      || base.sourceSizeBytes > 0xf0000 || !/^[0-9a-f]{40}$/.test(base.archiveCommit)
      || !/^docs\/ota-exec-notes\/P4-1-bootstrap-baseline-[a-z0-9-]{1,64}$/.test(base.archivePath)
      || base.targetVersionName !== targetVersion || !/^[0-9a-f]{40}$/.test(base.targetCommitSha)
      || base.targetCommitSha !== targetCommit
      || !Number.isSafeInteger(base.buildTimestamp) || base.buildTimestamp < 0 || base.buildTimestamp > 0xffffffff) {
      throw badInput("Invalid explicit inaugural bootstrap provenance or target identity");
    }
    for (const key of ["sourceRunId", "sourceRunAttempt", "sourceArtifactId"]) {
      if (typeof base[key] !== "string" || !/^[1-9][0-9]*$/.test(base[key]) || !Number.isSafeInteger(Number(base[key]))) {
        throw badInput("Invalid bootstrap CI identity");
      }
    }
    for (const key of ["sourceArtifactSha256", "provenanceSha256"]) sha256(base[key], key);
    if (base.sourceUrl !== `https://raw.githubusercontent.com/${repository}/${base.archiveCommit}/${base.archivePath}/app-final.bin`) {
      throw badInput("Bootstrap source must be an immutable same-repository archive");
    }
    return base;
  }
  if (base.provenanceKind !== undefined || base.isFormalRelease !== true
    || base.releaseTag !== `mcu-${FIRMWARE_MODEL}-v${base.versionName}`) {
    throw badInput("Base must identify the preceding formal finalized App");
  }
  const name = base.kind === "recovery" ? assetFileName("recovery", base.versionName) : "X-Track-App-GCC.bin";
  if (base.sourceUrl !== `https://github.com/${repository}/releases/download/${base.releaseTag}/${name}`) {
    throw badInput("Base source must be a pinned formal Release App or recovery, never nightly or ETU");
  }
  return base;
}

export function validateBootstrapProvenance(base, proof, repository) {
  const run = proof?.run, artifact = proof?.artifact, verified = proof?.verification;
  const build = verified?.build, development = proof?.developmentOnly;
  if (proof?.schemaVersion !== 1 || proof.provenanceKind !== BOOTSTRAP_PROVENANCE || proof.repository !== repository
    || String(run?.id) !== base.sourceRunId || String(run.run_attempt) !== base.sourceRunAttempt
    || run.path !== ".github/workflows/firmware-build.yml" || run.event !== "workflow_dispatch"
    || run.status !== "completed" || run.conclusion !== "success" || run.head_sha !== base.commitSha
    || run.repository?.full_name !== repository || run.head_repository?.full_name !== repository
    || !Number.isSafeInteger(run.repository?.id) || run.repository.id <= 0 || run.head_repository.id !== run.repository.id
    || String(artifact?.id) !== base.sourceArtifactId || artifact.name !== `p41-gcc-development-${base.commitSha}`
    || artifact.digest !== `sha256:${base.sourceArtifactSha256}` || artifact.workflow_run?.id !== run.id
    || artifact.workflow_run.repository_id !== run.repository.id || artifact.workflow_run.head_repository_id !== run.repository.id
    || artifact.workflow_run.head_sha !== base.commitSha || artifact.workflow_run.head_branch !== run.head_branch
    || verified?.ok !== true || verified.commitSha !== base.commitSha || verified.runId !== base.sourceRunId
    || verified.versionName !== base.versionName || verified.base !== null || verified.fullByteEqual !== true
    || verified.patchByteEqual !== null || verified.recoveryVerified !== true || verified.r2Verified !== false
    || verified.finalImage?.fileName !== "app-final.bin" || verified.finalImage.sha256 !== base.imageSha256
    || verified.finalImage.sizeBytes !== base.sourceSizeBytes || build?.commitSha !== base.commitSha
    || build.versionName !== base.versionName || build.versionCode !== base.versionCode || build.buildTimestamp !== base.buildTimestamp
    || build.app?.fileName !== "X-Track-App-GCC.bin" || build.app.sizeBytes !== base.sourceSizeBytes
    || build.boot?.fileName !== "X-Track-Boot.bin" || !Number.isSafeInteger(build.boot.sizeBytes)
    || build.boot.sizeBytes <= 0 || build.boot.sizeBytes > 0x10000
    || development?.installable !== false || development.formalBase !== "NOT_USED"
    || development.rehearsal !== "NOT_RUN" || development.remoteEffects !== "NOT_RUN") {
    throw badInput("Archived bootstrap CI/build/development provenance mismatch");
  }
  sha256(build.app.sha256, "bootstrap GCC App SHA");
  sha256(build.boot.sha256, "bootstrap Boot SHA");
  return proof;
}

export async function prepareFirmwareRelease({ root, app, boot, build, release, repository,
  base, baseFile, outputDir, referenceDir, buildEvidenceDir, aesKey = process.env.OTA_AES_KEY,
  bsdiff = process.env.BSDIFF_EXE, python = process.env.PYTHON ?? "python3", execute = spawnSync }) {
  if (!/^[0-9a-fA-F]{32}$/.test(aesKey ?? "")) throw new CliError("OTA_AES_KEY must be configured as 32 hex characters");
  if (!/^[A-Za-z0-9_.-]+\/[A-Za-z0-9_.-]+$/.test(repository ?? "")) throw new CliError("Explicit GitHub repository required");
  if (release.releaseTag !== `mcu-${FIRMWARE_MODEL}-v${release.versionName}`
    || !/^[1-9][0-9]*$/.test(release.runId ?? "")) throw new CliError("Invalid release tag or canonical provenance run id");
  // Current production GCC target and the existing recovery verifier support this
  // hardware/layout. Do not emit metadata claiming a different compiled target.
  if (release.hardwareRevision !== 1 || release.layoutId !== 1 || release.minBootVersion !== 1
    || release.targetHardware !== "AT32F435RGT7") throw new CliError("Unsupported GCC hardware/layout identity");
  const observedConfiguration = build.buildConfiguration === undefined ? undefined
    : await readBuildConfiguration(buildEvidenceDir ?? path.resolve(path.dirname(app), ".."), build.buildConfiguration.requestedProfile);
  const observedBuild = await captureBuildInputs({ app, boot, commitSha: release.commitSha,
    versionName: release.versionName, buildTimestamp: build.buildTimestamp, keyBinding: build.keyBinding,
    buildConfiguration: observedConfiguration });
  if (canonicalJson(observedBuild) !== canonicalJson(build)) throw badInput("Cross-stage GCC input identity mismatch");
  if (referenceDir) verifyReferenceBuild(build, await readFile(path.join(referenceDir, "verification.json")), release.runId);
  if (base) {
    validateBaseDescriptor(base, release.versionName, repository, release.commitSha);
    const source = await fileIdentity(baseFile);
    if (source.sha256 !== base.sourceSha256 || source.sizeBytes !== base.sourceSizeBytes) throw badInput("Base source byte identity mismatch");
    if (!bsdiff || !existsSync(bsdiff)) throw new CliError("A validated bsdiff executable is required for patch generation");
  } else if (baseFile) throw new CliError("Base file requires its provenance descriptor");
  const out = outputPath(root, outputDir);
  if (existsSync(out)) throw new CliError("Use a fresh output directory; do not overwrite a prior attempt");
  const names = [assetFileName("full", release.versionName),
    ...(base ? [assetFileName("patch", release.versionName, base.versionCode)] : []),
    assetFileName("recovery", release.versionName)];
  const paths = [out, ...["work", "tmp", "steps"].map(name => path.join(out, name)),
    ...names.map(name => path.join(out, name)), path.join(out, "app-final.bin"),
    path.join(out, "cloudflare-firmware-release-metadata.json"), path.join(out, "verification.json")];
  paths.forEach(value => outputPath(root, value));
  for (const dir of paths.slice(0, 4)) await mkdir(dir, { recursive: true });
  const env = { ...process.env, OTA_AES_KEY: aesKey, PYTHONDONTWRITEBYTECODE: "1", PYTHONUTF8: "1",
    TEMP: path.join(out, "tmp"), TMP: path.join(out, "tmp"), TMPDIR: path.join(out, "tmp") };
  const steps = [];
  async function run(label, script, argv, marker) {
    const result = execute(python, ["-B", path.join(root, script), ...argv],
      { cwd: path.join(out, "work"), env, encoding: "utf8", windowsHide: true, timeout: 330000, maxBuffer: 8 * 1024 * 1024 });
    await writeOutput(root, path.join(out, "steps", `${label}.stdout.txt`), result.stdout ?? "");
    await writeOutput(root, path.join(out, "steps", `${label}.stderr.txt`), result.stderr ?? "");
    steps.push({ label, executable: python, argv: ["-B", script, ...argv], exitCode: result.status,
      stdoutSha256: digest(Buffer.from(result.stdout ?? "")), stderrSha256: digest(Buffer.from(result.stderr ?? "")) });
    await writeOutput(root, path.join(out, "steps.json"), JSON.stringify(steps, null, 2) + "\n");
    if (result.error || result.status !== 0 || (marker && !(result.stdout ?? "").includes(marker))
      || /^\s*(?:\[err\]|error\b|fatal\b|\S+=FAIL\b)/im.test((result.stdout ?? "") + "\n" + (result.stderr ?? ""))) {
      throw badInput(`${label} failed exit/stdout verification; see preserved step output`);
    }
    return result.stdout;
  }
  async function verify(file, kind, version, imageSha, label, extra = []) {
    const result = JSON.parse(await run(label, ".github/scripts/firmware-byte-check.py",
      ["--input", file, "--kind", kind, "--version", version, "--sha256", imageSha, ...extra]));
    if (result.ok !== true || result.sha256 !== imageSha || result.version_name !== version
      || result.version_code !== versionCodeFor(version)) throw badInput(`${label} returned an invalid verification result`);
    return result;
  }
  let baseApp;
  if (base) {
    const fields = await verify(baseFile, base.kind, base.versionName, base.imageSha256, "base-verify");
    if (base.provenanceKind === BOOTSTRAP_PROVENANCE && fields.build_ts !== base.buildTimestamp) {
      throw badInput("Bootstrap base build timestamp differs from its CI provenance");
    }
    baseApp = path.join(out, "work", "base-final.bin");
    await run("base-extract", "Tools/jlink/prepare-bootstrap-app.py", ["prepare", "--input", baseFile,
      "--input-kind", base.kind, "--output", baseApp], "P1_5_APP_PREPARE=PASS");
    if ((await fileIdentity(baseApp)).sha256 !== base.imageSha256) throw badInput("Extracted base SHA mismatch");
  }
  const finalImage = path.join(out, "app-final.bin");
  await run("finalize", "Tools/etu_pack.py", ["finalize", "--app", app, "--out", finalImage,
    "--ver-name", release.versionName, "--build-ts", String(build.buildTimestamp)], "finalize OK:");
  const finalized = await readFile(finalImage);
  const targetSha = digest(finalized);
  const fields = await verify(finalImage, "app", release.versionName, targetSha, "finalized-verify",
    ["--placeholder", app, "--placeholder-sha256", build.app.sha256]);
  if (fields.build_ts !== build.buildTimestamp) throw badInput("Finalized build timestamp mismatch");
  const full = path.join(out, names[0]);
  const verifiedAssets = [];
  const reproduce = file => referenceDir ? ["--reproduce-from", path.join(referenceDir, path.basename(file))] : [];
  await run("full-pack", "Tools/etu_pack.py", ["pack-full", "--app", finalImage, "--out", full,
    "--ver-name", release.versionName, ...reproduce(full)], "pack-full OK:");
  verifiedAssets.push(await fileIdentity(full));
  const fullCandidate = path.join(out, "work", "full-candidate.bin");
  await run("full-apply", "Tools/etu_unpack.py", [full, "--out", fullCandidate, "--verify-fw-header"], "unpack(full) OK:");
  if (!(await readFile(fullCandidate)).equals(finalized)) throw badInput("Full roundtrip byte mismatch");
  await verify(finalImage, "app", release.versionName, targetSha, "full-outer-verify", ["--package", full]);
  if (base) {
    const patch = path.join(out, names[1]);
    await run("patch-pack", "Tools/etu_pack.py", ["pack-patch", "--old", baseApp, "--new", finalImage, "--out", patch,
      "--ver-name", release.versionName, "--base-ver-name", base.versionName, "--bsdiff-exe", path.resolve(bsdiff),
      ...reproduce(patch)], "pack-patch OK:");
    verifiedAssets.push(await fileIdentity(patch));
    const candidate = path.join(out, "work", "patch-candidate.bin");
    await run("patch-apply", "Tools/etu_unpack.py", [patch, "--old", baseApp, "--out", candidate,
      "--verify-fw-header"], "unpack(patch) OK:");
    if (!(await readFile(candidate)).equals(finalized)) throw badInput("Patch application byte mismatch");
    await verify(finalImage, "app", release.versionName, targetSha, "patch-outer-verify", ["--package", patch, "--base-image", baseApp]);
  }
  const recovery = path.join(out, names.at(-1));
  await run("recovery-create", "Tools/jlink/prepare-bootstrap-app.py", ["prepare", "--input", finalImage,
    "--input-kind", "app", "--output", path.join(out, "work", "recovery-app.bin"),
    "--recovery-output", recovery], "P1_5_APP_PREPARE=PASS");
  verifiedAssets.push(await fileIdentity(recovery));
  await verify(recovery, "recovery", release.versionName, targetSha, "recovery-verify");
  const metadata = await buildFirmwareMetadata({ release, assetsDir: out, finalImage, repository,
    patchBases: base ? [{ baseImageSha256: base.imageSha256, baseVersionCode: base.versionCode }] : [] });
  for (const asset of metadata.assets) {
    const verified = verifiedAssets.find(a => a.fileName === asset.fileName);
    if (!verified || verified.sha256 !== asset.sha256 || verified.sizeBytes !== asset.sizeBytes) throw badInput("Asset changed after byte verification");
  }
  if (canonicalJson(await captureBuildInputs({ app, boot, commitSha: build.commitSha,
    versionName: build.versionName, buildTimestamp: build.buildTimestamp, keyBinding: build.keyBinding,
    buildConfiguration: observedConfiguration === undefined ? undefined
      : await readBuildConfiguration(buildEvidenceDir ?? path.resolve(path.dirname(app), ".."), build.buildConfiguration.requestedProfile) })) !== canonicalJson(build)) throw badInput("GCC source changed during preparation");
  const prepared = metadataBytes(metadata);
  await writeOutput(root, path.join(out, "cloudflare-firmware-release-metadata.json"), prepared);
  const summary = { ok: true, commitSha: release.commitSha, runId: release.runId, versionName: release.versionName,
    build, base: base ?? null, finalImage: await fileIdentity(finalImage), assets: metadata.assets,
    fullByteEqual: true, patchByteEqual: base ? true : null, recoveryVerified: true,
    preparedMetadataSha256: digest(prepared), expectedReadyMetadataSha256: digest(metadataBytes(readyProjection(metadata))),
    r2Verified: false, steps };
  await writeOutput(root, path.join(out, "verification.json"), JSON.stringify(summary, null, 2) + "\n");
  return { metadata, summary, outputDir: out };
}

async function main() {
  const options = args(process.argv.slice(2), ["app", "boot", "build-inputs", "release-inputs", "repository",
    "base-descriptor", "base-file", "output-dir", "reference-dir", "bsdiff", "python"]);
  const result = await prepareFirmwareRelease({ root: projectRoot(), app: path.resolve(required(options, "app")),
    boot: path.resolve(required(options, "boot")), build: JSON.parse(await readFile(required(options, "build-inputs"), "utf8")),
    release: JSON.parse(await readFile(required(options, "release-inputs"), "utf8")), repository: required(options, "repository"),
    base: options["base-descriptor"] ? JSON.parse(await readFile(options["base-descriptor"], "utf8")) : undefined,
    baseFile: options["base-file"] && path.resolve(options["base-file"]), outputDir: path.resolve(required(options, "output-dir")),
    referenceDir: options["reference-dir"] && path.resolve(options["reference-dir"]), bsdiff: options.bsdiff,
    python: options.python ?? process.env.PYTHON ?? "python3" });
  process.stdout.write(JSON.stringify({ ok: true, outputDir: result.outputDir, assetsPrepared: result.metadata.assets.length,
    r2Verified: false, metadataSha256: result.summary.preparedMetadataSha256 }) + "\n");
}
if (process.argv[1] && import.meta.url === pathToFileURL(path.resolve(process.argv[1])).href) main().catch(failure);
