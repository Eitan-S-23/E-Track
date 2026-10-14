import { createHash } from "node:crypto";
import { spawnSync } from "node:child_process";
import { existsSync } from "node:fs";
import { mkdir, readFile } from "node:fs/promises";
import path from "node:path";
import { pathToFileURL } from "node:url";
import { buildFirmwareMetadata } from "./build-firmware-release-metadata.mjs";
import { args, CliError, failure, outputPath, projectRoot, required, writeOutput } from "./firmware-cli.mjs";
import { assetFileName, canonicalJson, FIRMWARE_MODEL, parseFirmwareRegistration, sha256, versionCodeFor } from "./firmware-schema.mjs";

export const digest = bytes => createHash("sha256").update(bytes).digest("hex");
const badInput = message => new CliError(message, "INVALID_PARAMETER", 1);
export const readyProjection = value => parseFirmwareRegistration({ ...value,
  assets: value.assets.map(asset => ({ ...asset, r2Verified: true })) });
export const metadataBytes = value => Buffer.from(canonicalJson(value) + "\n");

export async function fileIdentity(file) {
  const bytes = await readFile(file);
  if (!bytes.length) throw badInput("Empty input file");
  return { fileName: path.basename(file), sizeBytes: bytes.length, sha256: digest(bytes) };
}

export async function captureBuildInputs({ app, boot, commitSha, versionName, buildTimestamp }) {
  if (path.basename(app) !== "X-Track-App-GCC.bin" || path.basename(boot) !== "X-Track-Boot.bin") {
    throw badInput("Release requires the GCC App and matching Boot, not AC5/legacy images");
  }
  if (!/^[0-9a-f]{40}$/.test(commitSha) || !Number.isSafeInteger(buildTimestamp)
    || buildTimestamp < 0 || buildTimestamp > 0xffffffff) throw new CliError("Invalid build identity");
  return { commitSha, versionName, versionCode: versionCodeFor(versionName), buildTimestamp,
    app: await fileIdentity(app), boot: await fileIdentity(boot) };
}

export function validateBaseDescriptor(base, targetVersion, repository) {
  if (!base || base.isFormalRelease !== true || !["app", "recovery"].includes(base.kind)
    || base.versionCode !== versionCodeFor(base.versionName) || base.versionCode >= versionCodeFor(targetVersion)
    || base.releaseTag !== `mcu-${FIRMWARE_MODEL}-v${base.versionName}` || !/^[0-9a-f]{40}$/.test(base.commitSha)) {
    throw badInput("Base must identify the preceding formal finalized App");
  }
  for (const key of ["imageSha256", "sourceSha256"]) sha256(base[key], key);
  if (!Number.isSafeInteger(base.sourceSizeBytes) || base.sourceSizeBytes <= 0) throw badInput("Invalid base length");
  const name = base.kind === "recovery" ? assetFileName("recovery", base.versionName) : "X-Track-App-GCC.bin";
  if (base.sourceUrl !== `https://github.com/${repository}/releases/download/${base.releaseTag}/${name}`) {
    throw badInput("Base source must be a pinned formal Release App or recovery, never nightly or ETU");
  }
  return base;
}

export async function prepareFirmwareRelease({ root, app, boot, build, release, repository,
  base, baseFile, outputDir, referenceDir, aesKey = process.env.OTA_AES_KEY,
  bsdiff = process.env.BSDIFF_EXE, python = process.env.PYTHON ?? "python3", execute = spawnSync }) {
  if (!/^[0-9a-fA-F]{32}$/.test(aesKey ?? "")) throw new CliError("OTA_AES_KEY must be configured as 32 hex characters");
  if (!/^[A-Za-z0-9_.-]+\/[A-Za-z0-9_.-]+$/.test(repository ?? "")) throw new CliError("Explicit GitHub repository required");
  if (release.releaseTag !== `mcu-${FIRMWARE_MODEL}-v${release.versionName}`
    || !/^[1-9][0-9]*$/.test(release.runId ?? "")) throw new CliError("Invalid release tag or canonical provenance run id");
  // Current production GCC target and the existing recovery verifier support this
  // hardware/layout. Do not emit metadata claiming a different compiled target.
  if (release.hardwareRevision !== 1 || release.layoutId !== 1 || release.minBootVersion !== 1
    || release.targetHardware !== "AT32F435RGT7") throw new CliError("Unsupported GCC hardware/layout identity");
  const observedBuild = await captureBuildInputs({ app, boot, commitSha: release.commitSha,
    versionName: release.versionName, buildTimestamp: build.buildTimestamp });
  if (canonicalJson(observedBuild) !== canonicalJson(build)) throw badInput("Cross-stage GCC input identity mismatch");
  if (base) {
    validateBaseDescriptor(base, release.versionName, repository);
    const source = await fileIdentity(baseFile);
    if (source.sha256 !== base.sourceSha256 || source.sizeBytes !== base.sourceSizeBytes) throw badInput("Base source byte identity mismatch");
    if (!bsdiff || !existsSync(bsdiff)) throw new CliError("A validated bsdiff executable is required for patch generation");
  } else if (baseFile) throw new CliError("Base file requires its formal provenance descriptor");
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
    if (result.error || result.status !== 0 || (marker && !(result.stdout ?? "").includes(marker))) {
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
    await verify(baseFile, base.kind, base.versionName, base.imageSha256, "base-verify");
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
  const reproduce = file => referenceDir ? ["--reproduce-from", path.join(referenceDir, path.basename(file))] : [];
  await run("full-pack", "Tools/etu_pack.py", ["pack-full", "--app", finalImage, "--out", full,
    "--ver-name", release.versionName, ...reproduce(full)], "pack-full OK:");
  const fullCandidate = path.join(out, "work", "full-candidate.bin");
  await run("full-apply", "Tools/etu_unpack.py", [full, "--out", fullCandidate, "--verify-fw-header"], "unpack(full) OK:");
  if (!(await readFile(fullCandidate)).equals(finalized)) throw badInput("Full roundtrip byte mismatch");
  if (base) {
    const patch = path.join(out, names[1]);
    await run("patch-pack", "Tools/etu_pack.py", ["pack-patch", "--old", baseApp, "--new", finalImage, "--out", patch,
      "--ver-name", release.versionName, "--base-ver-name", base.versionName, "--bsdiff-exe", path.resolve(bsdiff),
      ...reproduce(patch)], "pack-patch OK:");
    const candidate = path.join(out, "work", "patch-candidate.bin");
    await run("patch-apply", "Tools/etu_unpack.py", [patch, "--old", baseApp, "--out", candidate,
      "--verify-fw-header"], "unpack(patch) OK:");
    if (!(await readFile(candidate)).equals(finalized)) throw badInput("Patch application byte mismatch");
  }
  const recovery = path.join(out, names.at(-1));
  await run("recovery-create", "Tools/jlink/prepare-bootstrap-app.py", ["prepare", "--input", finalImage,
    "--input-kind", "app", "--output", path.join(out, "work", "recovery-app.bin"),
    "--recovery-output", recovery], "P1_5_APP_PREPARE=PASS");
  await verify(recovery, "recovery", release.versionName, targetSha, "recovery-verify");
  const metadata = await buildFirmwareMetadata({ release, assetsDir: out, finalImage, repository,
    patchBases: base ? [{ baseImageSha256: base.imageSha256, baseVersionCode: base.versionCode }] : [] });
  if (canonicalJson(await captureBuildInputs({ app, boot, commitSha: build.commitSha,
    versionName: build.versionName, buildTimestamp: build.buildTimestamp })) !== canonicalJson(build)) throw badInput("GCC source changed during preparation");
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
