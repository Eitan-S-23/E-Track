import assert from "node:assert/strict";
import test from "node:test";
import { execFileSync, spawnSync } from "node:child_process";
import { existsSync } from "node:fs";
import { mkdir, mkdtemp, readFile } from "node:fs/promises";
import path from "node:path";
import { fileURLToPath } from "node:url";
import { candidateAdmission } from "../../.github/scripts/firmware-candidate-context.mjs";
import { verifyNormalCheckout, packageNormalCandidate } from "../../.github/scripts/firmware-normal-candidate.mjs";
import { validateBaseDescriptor, captureBuildInputs, digest, prepareFirmwareRelease } from "../../app/bluetooth_flutter_Trace/cloudflare/update-service/scripts/prepare-firmware-release.mjs";
import { firmwareKeyBinding } from "../../app/bluetooth_flutter_Trace/cloudflare/update-service/scripts/firmware-release-key.mjs";
import { captureBuildConfiguration, firmwareCMakeOptions } from "../../app/bluetooth_flutter_Trace/cloudflare/update-service/scripts/firmware-build-profile.mjs";
import { outputPath, writeOutput } from "../../app/bluetooth_flutter_Trace/cloudflare/update-service/scripts/firmware-cli.mjs";

const root = path.resolve(fileURLToPath(new URL("../../", import.meta.url)));
const fixtures = outputPath(root, path.resolve(root, process.env.P51_TEST_AREA || ".cache/p51-normal-tests"));
const config = JSON.parse(await readFile(path.join(root, "Tools/ota/p51-normal-inputs.json")));
const python = process.env.PYTHON ?? (process.platform === "win32" ? "python" : "python3");
const bsdiff = process.env.BSDIFF_EXE ?? path.join(root, "bsdiff_lzma_AES128-main/bsdiff/build/bin/bsdiff.exe");
const fixtureKey = "ab".repeat(16); // Public synthetic fixture, never installable or a protected candidate.

const sha = "a".repeat(40);
export const normalEnvironment = () => ({ GITHUB_ACTIONS: "true", GITHUB_EVENT_NAME: "workflow_dispatch",
  GITHUB_REPOSITORY: "Eitan-S-23/E-Track", INPUT_PACKAGE_CANDIDATE: "true", INPUT_STAGE_CANDIDATE: "false",
  INPUT_PUBLISH: "false", INPUT_REHEARSAL: "false", INPUT_CHECK_BINDINGS: "false", OTA_BOOT_CHAIN_READY: "false",
  INPUT_FIRMWARE_BUILD_PROFILE: "p34-v2-candidate", GITHUB_SHA: sha, GITHUB_WORKFLOW_SHA: sha,
  INPUT_CANDIDATE_REVIEWED_COMMIT: sha, GITHUB_REF: "refs/heads/dev/firmware/p51-packaging-20261104",
  GITHUB_WORKFLOW_REF: "Eitan-S-23/E-Track/.github/workflows/firmware-build.yml@refs/heads/dev/firmware/p51-packaging-20261104",
  GITHUB_RUN_ID: "42", GITHUB_RUN_ATTEMPT: "1", INPUT_CANDIDATE_MODE: "normal-delta",
  INPUT_VERSION_NAME: "3.3.21", INPUT_CANDIDATE_BASE_VERSION: "3.3.20", INPUT_CANDIDATE_FULL_BASE_VERSION: "",
  FIRMWARE_RELEASE_MODE: "artifact-candidate-normal",
  FIRMWARE_CANDIDATE_CONTEXT: "firmware-rehearsal/artifact-only-normal-delta-v1" });

test("normal delta admits only its exact protected artifact-only dispatch", () => {
  assert.deepEqual(candidateAdmission(normalEnvironment()), { commitSha: sha, runId: "42", runAttempt: "1" });
});

test("normal candidate provenance never becomes an ordinary formal release base", () => {
  assert.throws(() => validateBaseDescriptor({ provenanceKind: "p51-normal-candidate-v1", isFormalRelease: false,
    kind: "app", versionCode: 30320, versionName: "3.3.20", commitSha: sha, imageSha256: "b".repeat(64),
    sourceSha256: "b".repeat(64), sourceSizeBytes: 4096 }, "3.3.21", "Eitan-S-23/E-Track", sha), /formal/);
});

for (const [field, value] of [["INPUT_PUBLISH", "true"], ["INPUT_REHEARSAL", "true"], ["INPUT_STAGE_CANDIDATE", "true"],
  ["OTA_BOOT_CHAIN_READY", "true"], ["GITHUB_WORKFLOW_SHA", "b".repeat(40)], ["GITHUB_EVENT_NAME", "push"],
  ["GITHUB_TOKEN", "must-not-receive"], ["TRACE_DEPLOY_TOKEN", "must-not-receive"], ["INPUT_CANDIDATE_BASE_VERSION", "3.3.19"],
  ["INPUT_VERSION_NAME", "3.3.20"], ["INPUT_CANDIDATE_FULL_BASE_VERSION", "3.3.19"], ["INPUT_RELEASE_NOTES", "not permitted"],
  ["FIRMWARE_CANDIDATE_CONTEXT", "firmware-rehearsal/artifact-only-new-source-v1"], ["GITHUB_REF", "refs/tags/not-a-branch"]]) {
  test(`normal admission rejects ${field} drift`, () => assert.throws(() => candidateAdmission({ ...normalEnvironment(), [field]: value })));
}

test("reviewed source gate binds exactly the UI delta, not an arbitrary new checkout", () => {
  const git = argv => argv[0] === "diff" && argv[2] === config.baseSourceCommit ? config.sourceChangePaths.join("\n") : "";
  verifyNormalCheckout(root, normalEnvironment(), config, git);
  for (const change of [{ baseVersion: "3.3.22" }, { productionPublishable: true }, { sourceChangePaths: [] },
    { baseSourceCommit: "b".repeat(40) }, { purpose: "benchmark" }]) {
    assert.throws(() => verifyNormalCheckout(root, normalEnvironment(), { ...config, ...change }, git));
  }
  assert.throws(() => verifyNormalCheckout(root, normalEnvironment(), config,
    argv => argv[0] === "status" ? "?? USER/new.cpp" : git(argv)), /drift/);
});

test("actual original product diff matches the normal source contract", () => {
  const observed = execFileSync("git", ["--no-optional-locks", "diff", "--name-only", config.baseSourceCommit,
    config.targetSourceCommit, "--", ...config.productPaths], { cwd: root, encoding: "utf8", windowsHide: true }).trim();
  assert.deepEqual(observed.split(/\r?\n/).sort(), config.sourceChangePaths);
});

async function syntheticInputs(headerOnly = false) {
  await mkdir(fixtures, { recursive: true });
  const out = await mkdtemp(path.join(fixtures, "normal-"));
  const raw = Buffer.alloc(8192);
  let state = 0x12345678;
  for (let i = 0; i < raw.length; i++) {
    state ^= state << 13; state ^= state >>> 17; state ^= state << 5;
    raw[i] = state & 0xff;
  }
  raw.writeUInt32LE(0x20057ff0, 0); raw.writeUInt32LE(0x08010501, 4);
  raw.fill(0xff, 0x400, 0x460);
  const cmake = await readFile(path.join(root, "MDK-ARM_F435/cmake-generated/CMakeLists.txt"), "utf8");
  const block = cmake.match(/if\(P34_OTA_CANDIDATE\)([\s\S]*?)\nendif\(\)/)[1];
  const defs = ["OTA_TARGET_APP", "P34_EARLY_FAULT_VECTORS=1", ...block.match(/target_compile_definitions\(X_Track_App_GCC PRIVATE([\s\S]*?)\n\s*\)/)[1]
    .trim().split(/\s+/).map(value => value.replace("${P34_OTA_UART_BAUD}", "921600"))];
  const cache = "CMAKE_BUILD_TYPE:STRING=Release\nKEIL_GCC_COMPILER_CACHE:STRING=OFF\n" + Object.entries(firmwareCMakeOptions(config.profile)).map(([key, value]) => `${key}:STRING=${value}\n`).join("");
  const commands = [{ file: "synthetic-ota_keys.c", command: "fixture-only-gcc " + defs.map(d => "-D" + d).join(" ") + " -o CMakeFiles/X_Track_App_GCC.dir/synthetic.o" }];
  const proof = { schema: "p51-normal-source-proof-v1", config, sourceCompilations: 0, referenceSearches: 0,
    sourceChangesOutsideFwHeader: true, isFormalRelease: false, bootInstallation: "FORBIDDEN", roles: {}, retainedBoot: { fixture: true } };
  for (const role of ["base", "target"]) {
    const prefix = `originals/${role}/keyed-build/`, folder = path.join(out, "inputs", prefix);
    const bytes = Buffer.from(raw);
    if (role === "base" && !headerOnly) bytes[0x600] ^= 0x51;
    const originals = { "app/X-Track-App-GCC.bin": bytes, "boot/X-Track-Boot.bin": Buffer.from("synthetic boot, not installable"),
      "CMakeCache.txt": Buffer.from(cache), "compile_commands.json": Buffer.from(JSON.stringify(commands)) };
    for (const [name, value] of Object.entries(originals)) await writeOutput(root, path.join(folder, name), value);
    const originalBuild = await captureBuildInputs({ app: path.join(folder, "app/X-Track-App-GCC.bin"), boot: path.join(folder, "boot/X-Track-Boot.bin"),
      commitSha: config[role === "base" ? "baseSourceCommit" : "targetSourceCommit"], versionName: role === "base" ? "3.3.13" : "3.3.19",
      buildTimestamp: 1786320000, keyBinding: firmwareKeyBinding(fixtureKey, "approved-ci-key-v1"),
      buildConfiguration: captureBuildConfiguration({ profile: config.profile, cache, commands }) });
    proof.roles[role] = { originalBuild, files: Object.fromEntries(Object.entries(originals).map(([name, value]) =>
      [name, { path: prefix + name, bytes: value.length, sha256: digest(value) }])) };
  }
  await writeOutput(root, path.join(out, "inputs/normal-source-proof.json"), JSON.stringify(proof));
  await writeOutput(root, path.join(out, "DEVELOPMENT-ONLY.json"), JSON.stringify({ installable: false, provenance: "synthetic host fixture" }));
  return { root, out, config, env: { ...normalEnvironment(), OTA_AES_KEY: fixtureKey }, python, bsdiff };
}

test("real normal candidate uses shared finalize/vendor/apply and preserves both preparations", async () => {
  const options = await syntheticInputs();
  const observed = [];
  const metadata = await packageNormalCandidate({ ...options, execute: async (tool, argv, settings) => {
    observed.push({ argv, cwd: settings.cwd });
    assert.ok(settings.cwd === path.join(options.out, "normal/base/work") || settings.cwd === path.join(options.out, "normal/target/work"));
    return spawnSync(tool, argv, settings);
  } });
  assert.equal(metadata.baseVersionCode, 30320); assert.equal(metadata.versionCode, 30321);
  assert.equal(metadata.isFormalRelease, false); assert.equal(metadata.referenceSearches, 0);
  assert.equal(metadata.patchComparison.preferredKindForMatchingBase, "patch");
  assert.equal(metadata.patchComparison.changesOutsideFwHeader, true);
  const target = path.join(options.out, "normal/target");
  const proof = JSON.parse(await readFile(path.join(target, "verification.json")));
  assert.equal(proof.steps.length, 12);
  assert.equal(proof.base.provenanceKind, "p51-normal-candidate-v1");
  assert.equal(proof.base.isFormalRelease, false);
  assert.equal(proof.commitSha, config.targetSourceCommit);
  assert.equal(proof.base.producer.commitSha, sha);
  assert.deepEqual(await readFile(path.join(target, "work/patch-candidate.bin")), await readFile(path.join(target, "app-final.bin")));
  assert.deepEqual(await readFile(path.join(target, "work/base-final.bin")), await readFile(path.join(options.out, "normal/base/app-final.bin")));
  assert.ok(observed.some(value => value.argv.includes("pack-patch") && value.argv.includes(path.join(options.out, metadata.toolDependency.path))));
  assert.equal(digest(await readFile(path.join(options.out, metadata.toolDependency.path))), metadata.patchComparison.tool.sha256);
  assert.equal(existsSync(path.join(options.out, "normal/candidate-metadata.json")), false); // Native verification still owns final publication.
  process.stdout.write(`NORMAL_CANDIDATE_FIXTURE ${JSON.stringify({ out: options.out, metadata, installable: false })}\n`);
});

test("known development key and changed original bytes fail before normal output creation", async () => {
  const options = await syntheticInputs();
  await assert.rejects(packageNormalCandidate({ ...options, env: { ...options.env, OTA_AES_KEY: "01".repeat(16) } }), /development/);
  assert.equal(existsSync(path.join(options.out, "normal")), false);
  await writeOutput(root, path.join(options.out, "inputs/originals/base/keyed-build/app/X-Track-App-GCC.bin"), Buffer.from("not the admitted image"));
  await assert.rejects(packageNormalCandidate(options), /file changed/);
  assert.equal(existsSync(path.join(options.out, "normal")), false);
});

test("a header-only pair cannot become a representative normal candidate", async () => {
  const options = await syntheticInputs(true);
  await assert.rejects(packageNormalCandidate(options), /real-source PATCH/);
  assert.equal(existsSync(path.join(options.out, "normal/candidate-metadata.json")), false);
});

test("ordinary release preparation refuses the new non-formal base before output", async () => {
  const options = await syntheticInputs();
  await packageNormalCandidate(options);
  const target = path.join(options.out, "normal/target");
  const proof = JSON.parse(await readFile(path.join(target, "verification.json")));
  const outputDir = path.join(options.out, "must-not-create");
  const sourceDir = path.join(options.out, "inputs/originals/target/keyed-build");
  const release = JSON.parse(await readFile(path.join(target, "cloudflare-firmware-release-metadata.json")));
  await assert.rejects(prepareFirmwareRelease({ root, app: path.join(sourceDir, "app/X-Track-App-GCC.bin"),
    boot: path.join(sourceDir, "boot/X-Track-Boot.bin"), build: proof.build, buildEvidenceDir: sourceDir,
    release, repository: options.env.GITHUB_REPOSITORY, base: proof.base, baseFile: path.join(target, "work/base-final.bin"),
    outputDir, aesKey: fixtureKey, bsdiff, python }), /formal/);
  assert.equal(existsSync(outputDir), false);
});
