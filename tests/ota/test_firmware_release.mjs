import assert from "node:assert/strict";
import { spawnSync } from "node:child_process";
import { existsSync, readFileSync, writeFileSync } from "node:fs";
import { crc32 } from "node:zlib";
import { mkdir, mkdtemp, readFile } from "node:fs/promises";
import path from "node:path";
import { fileURLToPath } from "node:url";
import { test } from "node:test";
import { buildFirmwareMetadata } from "../../app/bluetooth_flutter_Trace/cloudflare/update-service/scripts/build-firmware-release-metadata.mjs";
import { captureBuildInputs, digest, metadataBytes, prepareFirmwareRelease, readyProjection,
  validateBaseDescriptor } from "../../app/bluetooth_flutter_Trace/cloudflare/update-service/scripts/prepare-firmware-release.mjs";
import { outputPath, writeOutput } from "../../app/bluetooth_flutter_Trace/cloudflare/update-service/scripts/firmware-cli.mjs";
import { parseFirmwareRegistration } from "../../app/bluetooth_flutter_Trace/cloudflare/update-service/scripts/firmware-schema.mjs";

const root = path.resolve(fileURLToPath(new URL("../../", import.meta.url)));
const python = process.env.PYTHON ?? (process.platform === "win32" ? "python" : "python3");
const bsdiff = process.env.BSDIFF_EXE ?? path.join(root, "bsdiff_lzma_AES128-main/bsdiff/build/bin/bsdiff.exe");
const aesKey = "01".repeat(16); // Isolated non-production fixture, never a release configuration.
const repository = "Eitan-S-23/Trace";
const fixture = JSON.parse(await readFile(path.join(root,
  "app/bluetooth_flutter_Trace/cloudflare/update-service/worker/test/fixtures/firmware-release-v2.json"), "utf8"));

async function input() {
  const parent = outputPath(root, path.join(root, ".cache/firmware-release-tests"));
  await mkdir(parent, { recursive: true });
  const dir = await mkdtemp(path.join(parent, "case-"));
  const app = path.join(dir, "X-Track-App-GCC.bin");
  const boot = path.join(dir, "X-Track-Boot.bin");
  const raw = Buffer.alloc(8192, 0x35);
  raw.writeUInt32LE(0x20057ff0, 0); raw.writeUInt32LE(0x08010501, 4);
  raw.fill(0xff, 0x400, 0x460);
  await writeOutput(root, app, raw);
  await writeOutput(root, boot, Buffer.from("synthetic Boot input, not installable"));
  const old = path.join(dir, "old-placeholder.bin");
  const baseFile = path.join(dir, "base.bin");
  const oldBytes = Buffer.from(raw); oldBytes[0x500] ^= 0x19;
  await writeOutput(root, old, oldBytes);
  const setup = spawnSync(python, ["-B", path.join(root, "Tools/etu_pack.py"), "finalize", "--app", old,
    "--out", baseFile, "--ver-name", "2.8.0", "--build-ts", "1786320000"],
    { cwd: dir, encoding: "utf8", windowsHide: true, env: { ...process.env, PYTHONDONTWRITEBYTECODE: "1", PYTHONUTF8: "1" } });
  await writeOutput(root, path.join(dir, "base-finalize.stdout.txt"), setup.stdout);
  assert.equal(setup.status, 0, setup.stderr);
  const baseBytes = await readFile(baseFile);
  const release = structuredClone(fixture);
  delete release.assets;
  const build = await captureBuildInputs({ app, boot, commitSha: release.commitSha,
    versionName: release.versionName, buildTimestamp: 1786320000 });
  const base = { isFormalRelease: true, kind: "app", versionName: "2.8.0", versionCode: 20800,
    releaseTag: "mcu-e-track-at32f435-v2.8.0", commitSha: "2".repeat(40), imageSha256: digest(baseBytes),
    sourceSha256: digest(baseBytes), sourceSizeBytes: baseBytes.length,
    sourceUrl: `https://github.com/${repository}/releases/download/mcu-e-track-at32f435-v2.8.0/X-Track-App-GCC.bin` };
  return { root, dir, app, boot, build, release, repository, base, baseFile,
    outputDir: path.join(dir, "prepared"), aesKey, bsdiff, python };
}

function bootstrapBase(options) {
  const { releaseTag: _, ...base } = options.base;
  const archiveCommit = "3".repeat(40), archivePath = "docs/ota-exec-notes/P4-1-bootstrap-baseline-fixture";
  return { ...base, provenanceKind: "inaugural-bootstrap-v1", isFormalRelease: false,
    buildTimestamp: 1786320000, archiveCommit, archivePath,
    sourceUrl: `https://raw.githubusercontent.com/${repository}/${archiveCommit}/${archivePath}/app-final.bin`,
    sourceRunId: "12345", sourceRunAttempt: "1", sourceArtifactId: "67890", sourceArtifactSha256: "a".repeat(64),
    provenanceSha256: "b".repeat(64), targetVersionName: options.release.versionName,
    targetCommitSha: options.release.commitSha };
}

test("real finalize/full/patch/recovery bytes and canonical P4-2 metadata roundtrip", async () => {
  const options = await input();
  const result = await prepareFirmwareRelease(options);
  assert.deepEqual(result.metadata.assets.map(a => a.kind), ["full", "patch", "recovery"]);
  assert.equal(result.summary.patchByteEqual, true);
  assert.equal(result.summary.r2Verified, false);
  assert.equal(result.metadata.targetImageSha256, result.summary.finalImage.sha256);
  assert.equal(result.metadata.assets[1].baseImageSha256, options.base.imageSha256);
  assert.throws(() => parseFirmwareRegistration(result.metadata), /readback/);
  assert.equal(parseFirmwareRegistration(readyProjection(result.metadata)).assets.length, 3);
  for (const asset of result.metadata.assets) {
    const bytes = await readFile(path.join(options.outputDir, asset.fileName));
    assert.equal(bytes.length, asset.sizeBytes); assert.equal(digest(bytes), asset.sha256);
  }
  assert.equal(digest(await readFile(options.app)), options.build.app.sha256);
  assert.equal(digest(metadataBytes(readyProjection(result.metadata))), result.summary.expectedReadyMetadataSha256);
  process.stdout.write(`BYTE_FIXTURE ${JSON.stringify({ path: options.outputDir, assets: result.metadata.assets,
    finalImage: result.summary.finalImage, metadataSha256: result.summary.preparedMetadataSha256 })}\n`);
});

test("explicit bootstrap provenance still generates and byte-applies a real patch", async () => {
  const options = await input(); options.base = bootstrapBase(options);
  const result = await prepareFirmwareRelease(options);
  assert.deepEqual(result.metadata.assets.map(a => a.kind), ["full", "patch", "recovery"]);
  assert.equal(result.summary.patchByteEqual, true);
  assert.equal(result.summary.base.isFormalRelease, false);
  assert.equal(result.summary.base.provenanceKind, "inaugural-bootstrap-v1");
  assert.equal(result.metadata.assets[1].baseImageSha256, options.base.imageSha256);
  assert.equal(result.metadata.runId, options.release.runId);
  assert.notEqual(result.metadata.runId, options.base.sourceRunId);
  assert.deepEqual(await readFile(path.join(options.outputDir, "work/patch-candidate.bin")),
    await readFile(path.join(options.outputDir, "app-final.bin")));
});

test("bootstrap base timestamp and placeholder sources fail before target preparation", async () => {
  const options = await input(); options.base = bootstrapBase(options);
  options.base.buildTimestamp++;
  await assert.rejects(prepareFirmwareRelease(options), /base build timestamp/);
  assert.equal(existsSync(path.join(options.outputDir, "app-final.bin")), false);
  const other = await input(); other.base = bootstrapBase(other);
  other.baseFile = path.join(other.dir, "old-placeholder.bin");
  other.base.imageSha256 = other.base.sourceSha256 = digest(await readFile(other.baseFile));
  await assert.rejects(prepareFirmwareRelease(other), /base-verify/);
  assert.equal(existsSync(path.join(other.outputDir, "app-final.bin")), false);
});

test("bootstrap target binding and version monotonicity fail before output creation", async () => {
  const options = await input(); options.base = bootstrapBase(options);
  for (const change of [{ targetCommitSha: "f".repeat(40) }, { targetVersionName: "2.8.2" },
    { versionCode: 20801 }, { versionName: "2.8.1", versionCode: 20801 }]) {
    await assert.rejects(prepareFirmwareRelease({ ...options, base: { ...options.base, ...change } }));
    assert.equal(existsSync(options.outputDir), false);
  }
});

test("approved-envelope reproduction is byte-identical, including canonical provenance", async () => {
  const options = await input();
  const first = await prepareFirmwareRelease(options);
  const replay = await prepareFirmwareRelease({ ...options, outputDir: path.join(options.dir, "replay"), referenceDir: options.outputDir });
  assert.deepEqual(metadataBytes(first.metadata), metadataBytes(replay.metadata));
  assert.equal(first.summary.expectedReadyMetadataSha256, replay.summary.expectedReadyMetadataSha256);
  for (const a of first.metadata.assets) assert.deepEqual(await readFile(path.join(first.outputDir, a.fileName)),
    await readFile(path.join(replay.outputDir, a.fileName)));
});

test("a fresh generation still uses independent random package nonces", async () => {
  const options = await input();
  const one = await prepareFirmwareRelease({ ...options, base: undefined, baseFile: undefined });
  const two = await prepareFirmwareRelease({ ...options, base: undefined, baseFile: undefined, outputDir: path.join(options.dir, "random") });
  assert.notEqual(one.metadata.assets[0].sha256, two.metadata.assets[0].sha256);
  assert.equal(one.metadata.targetImageSha256, two.metadata.targetImageSha256);
});

for (const aesKey of ["", "invalid"]) test(`missing/invalid key fails configuration before outputs (${aesKey || "missing"})`, async () => {
  const options = await input();
  await assert.rejects(prepareFirmwareRelease({ ...options, aesKey }), { exitCode: 2 });
  assert.equal(existsSync(options.outputDir), false);
});

test("wrong cross-stage GCC digest fails before preparation", async () => {
  const options = await input(); options.build.app.sha256 = "0".repeat(64);
  await assert.rejects(prepareFirmwareRelease(options), /Cross-stage/);
  assert.equal(existsSync(options.outputDir), false);
});

test("wrong base image SHA rejects before full/patch/recovery output", async () => {
  const options = await input(); options.base.imageSha256 = "0".repeat(64);
  await assert.rejects(prepareFirmwareRelease(options), /base-verify/);
  assert.equal(existsSync(path.join(options.outputDir, "app-final.bin")), false);
  assert.equal(existsSync(path.join(options.outputDir, "cloudflare-firmware-release-metadata.json")), false);
});

test("base source drift, wrong version, nightly and ETU sources are rejected", async () => {
  const options = await input();
  for (const change of [{ versionCode: 20801 }, { isFormalRelease: false },
    { sourceUrl: options.base.sourceUrl.replace("/releases/download/", "/actions/artifacts/") },
    { sourceUrl: options.base.sourceUrl.replace("X-Track-App-GCC.bin", "full.etu") }]) {
    assert.throws(() => validateBaseDescriptor({ ...options.base, ...change }, "2.8.1", repository));
  }
  options.base.sourceSha256 = "0".repeat(64);
  await assert.rejects(prepareFirmwareRelease(options), /Base source byte/);
});

test("exit zero with a patch stdout failure does not advance to recovery or metadata", async () => {
  const options = await input();
  const execute = (exe, argv, config) => {
    const result = spawnSync(exe, argv, config);
    if (argv.includes("--old") && argv[1].endsWith("etu_unpack.py")) result.stdout = "injected stdout failure despite exit zero\n";
    return result;
  };
  await assert.rejects(prepareFirmwareRelease({ ...options, execute }), /patch-apply failed exit\/stdout/);
  assert.equal(existsSync(path.join(options.outputDir, "recovery-v2.8.1.bin")), false);
});

test("a successful patch tool with wrong candidate bytes is rejected", async () => {
  const options = await input();
  const execute = (exe, argv, config) => {
    const result = spawnSync(exe, argv, config);
    if (argv.includes("--old") && argv[1].endsWith("etu_unpack.py")) {
      writeFileSync(outputPath(root, argv[argv.indexOf("--out") + 1]), Buffer.from("injected corrupt candidate"));
    }
    return result;
  };
  await assert.rejects(prepareFirmwareRelease({ ...options, execute }), /Patch application byte mismatch/);
  assert.equal(existsSync(path.join(options.outputDir, "cloudflare-firmware-release-metadata.json")), false);
});

test("damaged recovery trailer fails actual verification before metadata", async () => {
  const options = await input();
  const execute = (exe, argv, config) => {
    const result = spawnSync(exe, argv, config);
    if (argv.includes("--recovery-output")) writeFileSync(outputPath(root, argv[argv.indexOf("--recovery-output") + 1]), Buffer.from("bad-tail"));
    return result;
  };
  await assert.rejects(prepareFirmwareRelease({ ...options, execute }), /recovery-verify/);
  assert.equal(existsSync(path.join(options.outputDir, "cloudflare-firmware-release-metadata.json")), false);
});

test("builder refuses missing full/recovery assets instead of emitting metadata", async () => {
  const options = await input();
  await assert.rejects(buildFirmwareMetadata({ release: options.release, assetsDir: options.dir,
    finalImage: options.baseFile, repository }), /ENOENT/);
});

test("output path and unsupported compiled identity fail closed", async () => {
  const options = await input();
  await assert.rejects(prepareFirmwareRelease({ ...options, outputDir: path.join(root, "..", "not-authorized") }), /escapes/);
  await assert.rejects(prepareFirmwareRelease({ ...options, release: { ...options.release, layoutId: 2 } }), { exitCode: 2 });
});

test("actual preparation CLI returns one JSON result and configuration exit 2", async () => {
  const options = await input();
  for (const [name, value] of [["build", options.build], ["release", options.release], ["base", options.base]]) {
    await writeOutput(root, path.join(options.dir, `${name}.json`), JSON.stringify(value));
  }
  const script = path.join(root, "app/bluetooth_flutter_Trace/cloudflare/update-service/scripts/prepare-firmware-release.mjs");
  const argv = [script, "--app", options.app, "--boot", options.boot, "--build-inputs", path.join(options.dir, "build.json"),
    "--release-inputs", path.join(options.dir, "release.json"), "--repository", repository, "--base-descriptor", path.join(options.dir, "base.json"),
    "--base-file", options.baseFile, "--output-dir", options.outputDir, "--python", python, "--bsdiff", bsdiff];
  const run = spawnSync(process.execPath, argv, { cwd: root, env: { ...process.env, OTA_AES_KEY: aesKey },
    encoding: "utf8", windowsHide: true, timeout: 30000 });
  assert.equal(run.status, 0, run.stderr);
  assert.equal(JSON.parse(run.stdout).assetsPrepared, 3);
  const missing = spawnSync(process.execPath, argv, { cwd: root, env: { ...process.env, OTA_AES_KEY: "" },
    encoding: "utf8", windowsHide: true, timeout: 30000 });
  assert.equal(missing.status, 2); assert.equal(JSON.parse(missing.stderr).errorCode, "INVALID_PARAMETER");
  process.stdout.write(`PREPARATION_CLI ${JSON.stringify({ exitCode: run.status, stdout: run.stdout,
    missingKeyExit: missing.status, missingKeyStderr: missing.stderr })}\n`);
});

for (const mutation of ["target", "base", "trailer"]) test(`rejects ETU outer ${mutation} drift despite a byte-equal unpack result`, async () => {
  const options = await input();
  const execute = (exe, argv, config) => {
    const result = spawnSync(exe, argv, config);
    const stage = mutation === "base" ? "pack-patch" : "pack-full";
    if (argv.includes(stage)) {
      const out = outputPath(root, argv[argv.indexOf("--out") + 1]);
      let bytes = readFileSync(out);
      if (mutation === "trailer") bytes = Buffer.concat([bytes, Buffer.from("illegal trailing bytes")]);
      else {
        if (mutation === "target") bytes.writeUInt32LE(20802, 40);
        else bytes[52] ^= 1;
        bytes.writeUInt32LE(crc32(bytes.subarray(0, 60)), 60);
      }
      writeFileSync(out, bytes);
    }
    return result;
  };
  await assert.rejects(prepareFirmwareRelease({ ...options, execute }), /outer-verify/);
  assert.equal(existsSync(path.join(options.outputDir, "cloudflare-firmware-release-metadata.json")), false);
});

test("late asset replacement cannot change the verified metadata identity", async () => {
  const options = await input();
  const execute = (exe, argv, config) => {
    const result = spawnSync(exe, argv, config);
    if (argv.includes("--recovery-output")) writeFileSync(outputPath(root, path.join(options.outputDir,
      "e-track-at32f435-v2.8.1-full.etu")), Buffer.from("late altered package"));
    return result;
  };
  await assert.rejects(prepareFirmwareRelease({ ...options, execute }), /changed after byte verification/);
});

test("an explicit error overrides a simultaneous success stdout marker", async () => {
  const options = await input();
  const execute = (exe, argv, config) => {
    const result = spawnSync(exe, argv, config);
    if (argv.includes("pack-full")) result.stdout += "\n[err] injected error after success marker\n";
    return result;
  };
  await assert.rejects(prepareFirmwareRelease({ ...options, execute }), /full-pack failed exit\/stdout/);
});
