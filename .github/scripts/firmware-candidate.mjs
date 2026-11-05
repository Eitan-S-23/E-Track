import { execFileSync, spawnSync } from "node:child_process";
import { existsSync, lstatSync, realpathSync } from "node:fs";
import { mkdir, readFile, readdir, rm } from "node:fs/promises";
import path from "node:path";
import { pathToFileURL } from "node:url";
import { args, CliError, failure, outputPath, projectRoot, writeOutput } from "../../app/bluetooth_flutter_Trace/cloudflare/update-service/scripts/firmware-cli.mjs";
import { digest } from "../../app/bluetooth_flutter_Trace/cloudflare/update-service/scripts/prepare-firmware-release.mjs";
import { firmwareKeyHeader, verifyBuildKeyBinding } from "../../app/bluetooth_flutter_Trace/cloudflare/update-service/scripts/firmware-release-key.mjs";
import { verifyBuildConfiguration, readBuildConfiguration } from "../../app/bluetooth_flutter_Trace/cloudflare/update-service/scripts/firmware-build-profile.mjs";
import { buildKeyedFirmware, cleanupPrivateBuildKey } from "./firmware-gcc-keyed-build.mjs";
import { candidateAdmission, candidateMode, UI_BASELINE } from "./firmware-candidate-context.mjs";
export { candidateAdmission } from "./firmware-candidate-context.mjs";

export function verifyCandidateCheckout(root, env, config, git = argv =>
  execFileSync("git", ["--no-optional-locks", ...argv], { cwd: root, encoding: "utf8", windowsHide: true }).trim()) {
  const owner = candidateAdmission(env);
  if (git(["rev-parse", "HEAD"]) !== owner.commitSha) throw new CliError("Candidate checkout differs from reviewed source");
  if (candidateMode(env) === "archived-original") return owner;
  if (candidateMode(env) === "start-state-supplement") {
    if (config?.schema !== "p51-start-state-inputs-v1" || config.mode !== "start-state-supplement"
        || config.repository !== env.GITHUB_REPOSITORY || config.task !== "P51-START-STATE-01"
        || config.purpose !== "preparation-only/normal-OTA-start-state"
        || git(["diff", "--name-only", "HEAD"])) throw new CliError("Supplement contract/checkout drift");
    return owner;
  }
  const expectedPaths = ["USER", "ArduinoAPI", "Libraries", "MDK-ARM_F435", "boot", "cmake",
    "vendor", "Simulator", "bsdiff_lzma_AES128-main", "segger_rtt"];
  if (config?.schema !== "p51-new-source-inputs-v2" || config.mode !== "new-source"
      || config.repository !== env.GITHUB_REPOSITORY || config.reviewedProductBaseline !== UI_BASELINE
      || config.profile !== "p34-v2-candidate"
      || JSON.stringify(config.productPaths) !== JSON.stringify(expectedPaths)
      || config.derivation !== "one-keyed-source-build/two-fw-header-finalizations"
      || config.timestampPolicy !== "actual-checkout-commit-time-for-both-headers") {
    throw new CliError("New-source reviewed product/input contract mismatch");
  }
  git(["merge-base", "--is-ancestor", UI_BASELINE, owner.commitSha]);
  if (git(["diff", "--name-only", UI_BASELINE, owner.commitSha, "--", ...expectedPaths])
      || git(["diff", "--name-only", "HEAD"])
      || git(["status", "--porcelain", "--untracked-files=all", "--", ...expectedPaths])) {
    throw new CliError("Candidate product differs from the reviewed UI baseline or checkout is dirty");
  }
  return owner;
}

function area(root) { return outputPath(root, path.join(root, ".cache/p51-candidate")); }
export function redactCandidate(value, key) {
  let text = value ?? "";
  if (/^[0-9a-fA-F]{32}$/.test(key ?? "")) {
    for (const secret of [key, ...key.match(/.{8}/g)]) {
      text = text.replace(new RegExp(secret, "gi"), "[REDACTED_KEY]");
    }
  }
  return text;
}
function ownership(env) {
  const { GITHUB_SHA: commitSha, GITHUB_RUN_ID: runId, GITHUB_RUN_ATTEMPT: runAttempt } = env;
  if (!/^[0-9a-f]{40}$/.test(commitSha ?? "") || !/^[1-9][0-9]*$/.test(runId ?? "")
      || !/^[1-9][0-9]*$/.test(runAttempt ?? "")) throw new CliError("Missing cleanup owner");
  return { commitSha, runId, runAttempt };
}

export async function cleanupCandidate(root, env) {
  if (existsSync(path.join(root, ".cache/p51cg"))) {
    await cleanupPrivateBuildKey({ root, buildDir: ".cache/p51cg", env });
  }
  const parent = area(root), privateDir = outputPath(root, path.join(parent, "private"));
  if (existsSync(privateDir)) {
    if (existsSync(path.join(privateDir, "native-active.json"))) {
      throw new CliError("Native tree closure is unconfirmed; preserve private state and do not upload");
    }
    const expected = ownership(env);
    const owner = JSON.parse(await readFile(outputPath(root, path.join(privateDir, "owner.json")), "utf8"));
    if (JSON.stringify(owner) !== JSON.stringify(expected)) throw new CliError("Refusing a different private candidate owner");
    // Revalidate every descendant before a recursive delete; never follow links.
    async function check(dir) {
      for (const entry of await readdir(dir, { withFileTypes: true })) {
        const child = outputPath(root, path.join(dir, entry.name));
        if (lstatSync(child).isSymbolicLink()) throw new CliError("Private candidate contains a link");
        if (entry.isDirectory()) await check(child);
      }
    }
    await check(privateDir);
    await rm(privateDir, { recursive: true });
  }
  if (existsSync(privateDir)) throw new CliError("Private candidate cleanup incomplete");
  return { privateAbsent: true };
}

export async function buildSourceCandidate({ root, env, config, execute, build = buildKeyedFirmware,
  git = argv => execFileSync("git", ["--no-optional-locks", ...argv],
    { cwd: root, encoding: "utf8", windowsHide: true }).trim() }) {
  verifyCandidateCheckout(root, env, config, git);
  if (candidateMode(env) !== "new-source") throw new CliError("Only new-source invokes GCC");
  const buildTimestamp = Number(git(["show", "-s", "--format=%ct", "HEAD"]));
  const result = await build({ root, buildDir: ".cache/p51cg", evidenceDir: ".cache/p51-candidate/keyed-build",
    versionName: env.INPUT_VERSION_NAME, commitSha: env.GITHUB_SHA, buildTimestamp, env,
    profile: config.profile, execute });
  verifyBuildKeyBinding(result, env);
  verifyBuildConfiguration(result, config.profile);
  verifyCandidateCheckout(root, env, config, git);
  return result;
}

export async function sourceMetadata(root, env, config, build) {
  const parent = area(root), prepared = path.join(parent, "prepared");
  const proof = JSON.parse(await readFile(path.join(parent, "evidence/source-images.json")));
  const verification = JSON.parse(await readFile(path.join(parent, "evidence/verification.json")));
  const assets = [];
  for (const name of ["app-start.bin", "app-final.bin", "X-Track-Boot.bin", "full.etu", "patch.etu",
    "reference-1MiB.etu", "recovery.bin", ...(env.INPUT_CANDIDATE_FULL_BASE_VERSION ? ["app-start-full.bin"] : [])]) {
    const bytes = await readFile(outputPath(root, path.join(prepared, name)));
    assets.push({ fileName: name, sizeBytes: bytes.length, sha256: digest(bytes) });
  }
  const identity = name => assets.find(a => a.fileName === name);
  if (identity("app-start.bin").sha256 !== proof.base.sha256 || identity("app-final.bin").sha256 !== proof.target.sha256
      || identity("X-Track-Boot.bin").sha256 !== proof.boot.sha256
      || identity("patch.etu").sizeBytes !== 1048576
      || identity("patch.etu").sha256 !== identity("reference-1MiB.etu").sha256
      || !verification.fullByteEqual || !verification.patchByteEqual || !verification.recoveryByteEqual
      || verification.native.checks.length !== (env.INPUT_CANDIDATE_FULL_BASE_VERSION ? 12 : 11)
      || verification.native.checks.some(c => !c.observation.passed)
      || JSON.stringify(assets) !== JSON.stringify(verification.assets)
      || proof.base.versionName !== env.INPUT_CANDIDATE_BASE_VERSION || proof.target.versionName !== env.INPUT_VERSION_NAME
      || JSON.stringify(proof.raw) !== JSON.stringify(build.app)) {
    throw new CliError("New-source byte verification/asset identity mismatch");
  }
  if (env.INPUT_CANDIDATE_FULL_BASE_VERSION && (proof.fullBase?.versionName !== env.INPUT_CANDIDATE_FULL_BASE_VERSION
      || identity("app-start-full.bin").sha256 !== proof.fullBase.sha256)) {
    throw new CliError("Full-cell start identity mismatch");
  }
  const keyed = path.join(parent, "keyed-build");
  if (JSON.stringify(await readBuildConfiguration(keyed, config.profile)) !== JSON.stringify(build.buildConfiguration)) {
    throw new CliError("New-source compiler configuration drift");
  }
  const evidence = JSON.parse(await readFile(path.join(keyed, "keyed-build-evidence.json")));
  for (const record of evidence.artifacts) {
    const bytes = await readFile(outputPath(root, path.join(keyed, record.path)));
    if (bytes.length !== record.sizeBytes || digest(bytes) !== record.sha256) throw new CliError("Compiled artifact drift");
  }
  return { schema: "p51-artifact-candidate-v2", mode: "new-source", task: "P5-1",
    isFormalRelease: false, productionPublishable: false, readyRegistered: false,
    versionName: proof.target.versionName, versionCode: proof.target.versionCode,
    buildTimestamp: proof.target.buildTimestamp, targetImageSha256: proof.target.sha256,
    baseVersionName: proof.base.versionName, baseVersionCode: proof.base.versionCode,
    baseImageSha256: proof.base.sha256,
    hardwareAcceptance: "NOT_RUN", runner: ownership(env),
    source: { reviewedProductBaseline: config.reviewedProductBaseline, actualCheckout: env.GITHUB_SHA,
      workflowCommit: env.GITHUB_WORKFLOW_SHA, workflowRef: env.GITHUB_WORKFLOW_REF,
      productUnchangedFromReviewedBaseline: true },
    derivation: env.INPUT_CANDIDATE_FULL_BASE_VERSION
      ? "one-keyed-source-build/three-fw-header-finalizations" : config.derivation,
    sourceCompilations: 1, build, finalization: proof,
    elfMapRelationship: { directory: "keyed-build/app", headerOffset: 1024, headerBytes: 96,
      description: "ELF/MAP exactly match raw GCC App; start/target differ only in the documented finalized fw_header",
      artifacts: evidence.artifacts.filter(a => a.path.startsWith("app/")) },
    ordinaryBuiltBoot: { ...build.boot, candidateBoot: false, purpose: "compile-only, not approved group16" },
    boot: { ...proof.boot, kind: "external-approved-group16", firmwareRebuilt: false },
    key: { ...build.keyBinding, compiledAndPackagingBindingMatched: true },
    assets: assets.map(asset => ({ ...asset,
      kind: ({ "full.etu": "full", "patch.etu": "patch", "reference-1MiB.etu": "reference",
        "recovery.bin": "recovery", "app-start.bin": "start-app", "app-final.bin": "target-app",
        "X-Track-Boot.bin": "external-boot", "app-start-full.bin": "full-cell-start-app" })[asset.fileName],
      ...(asset.fileName === "patch.etu" || asset.fileName === "reference-1MiB.etu"
        ? { baseVersionCode: proof.base.versionCode, baseImageSha256: proof.base.sha256 }
        : {}) })),
    reference: { aliasOf: "patch.etu", totalLength: 1048576, fullConsumption: true },
    bleFullCell: { actualDeviceBinding: "NOT_RUN", instruction: config.bleFullCell,
      patchBase: proof.base, suppliedFullStart: proof.fullBase ?? null,
      noFabricatedDeviceIdentity: true },
    noCloudMutation: true, noDeviceOperation: true };
}

export async function candidateMetadata(root, env, manifest) {
  const parent = area(root), prepared = path.join(parent, "prepared");
  const assets = [];
  for (const [kind, name] of [["full", "full.etu"], ["patch", "patch.etu"], ["recovery", "recovery.bin"]]) {
    const bytes = await readFile(outputPath(root, path.join(prepared, name)));
    assets.push({ kind, fileName: name, sizeBytes: bytes.length, sha256: digest(bytes),
      baseVersionCode: kind === "patch" ? 30313 : 0,
      baseImageSha256: kind === "patch" ? manifest.packet.members.base.sha256 : "" });
  }
  const image = await readFile(path.join(prepared, "app-final.bin"));
  const boot = await readFile(path.join(prepared, "X-Track-Boot.bin"));
  if (digest(image) !== manifest.targetSha256 || digest(boot) !== manifest.boot.sha256
      || !(await readFile(path.join(prepared, "patch.etu"))).equals(await readFile(path.join(prepared, "reference-1MiB.etu")))
      || assets[1].sizeBytes !== 1048576) throw new CliError("Prepared candidate identity mismatch");
  return { schema: "p51-artifact-candidate-v1", task: "P5-1", purpose: "independent acceptance inputs only",
    isFormalRelease: false, productionPublishable: false, hardwareAcceptance: "NOT_RUN", readyRegistered: false,
    runner: ownership(env), appSourceCommit: manifest.sourceCommit, originalCiRun: manifest.originalRun,
    originalCiArtifact: manifest.originalArtifact, sourceEvidenceCommit: manifest.sourceEvidenceCommit,
    versionName: manifest.targetVersion, versionCode: 30316, buildTimestamp: manifest.targetTimestamp,
    targetImageSha256: digest(image), targetBytes: image.length,
    derivation: "Original GCC executable unchanged; fw_header-only forward finalization",
    boot: { kind: "external-approved-group16", sha256: digest(boot), bytes: boot.length,
      source: manifest.boot.source, evidenceCommit: manifest.bootEvidenceCommit, firmwareRebuilt: false },
    key: { source: "approved-ci-key-v1", exactOriginalBuildBindingMatched: true }, assets,
    reference: { aliasOf: "patch.etu", fileName: "reference-1MiB.etu", totalLength: 1048576, sha256: assets[1].sha256 },
    noCloudMutation: true, noDeviceOperation: true };
}

export async function supplementMetadata(root, env, config) {
  candidateAdmission(env);
  const parent = area(root);
  const proofBytes = await readFile(outputPath(root, path.join(parent, "inputs/supplement-source.json")));
  const proof = JSON.parse(proofBytes);
  const verification = JSON.parse(await readFile(outputPath(root, path.join(parent, "evidence/supplement-verification.json"))));
  const build = JSON.parse(await readFile(outputPath(root, path.join(parent, "inputs/supplement-build.json"))));
  const admitted = await readFile(outputPath(root, path.join(parent, "inputs/manifest.json")));
  const originalOwner = { commitSha: config.sourceCommit, runId: String(config.originalRun), runAttempt: String(config.originalAttempt) };
  const nativeCases = config.images.flatMap(rec => ["positive", "payload-crc", "truncated", "wrong-target-version"]
    .map(name => `init-${rec.versionCode}-${name}`));
  if (JSON.stringify(proof.originalOwner) !== JSON.stringify(originalOwner)
      || proof.configSha256 !== digest(admitted) || JSON.stringify(JSON.parse(admitted)) !== JSON.stringify(config)
      || JSON.stringify(proof.build) !== JSON.stringify(build) || build.commitSha !== originalOwner.commitSha
      || verification.sourceProofSha256 !== digest(proofBytes)
      || JSON.stringify(proof.images) !== JSON.stringify(config.images)
      || !verification.fullByteEqual || !verification.strictFullConsumption
      || JSON.stringify(proof.build.keyBinding) !== JSON.stringify(verification.keyBinding)
      || verification.assets.length !== 2 || verification.native.checks.length !== 8
      || verification.native.warnings !== 0 || verification.native.errors !== 0
      || JSON.stringify(verification.native.checks.map(c => c.case)) !== JSON.stringify(nativeCases)
      || verification.native.checks.some(c => !c.observation.passed
        || (c.case.endsWith("-positive") ? !c.observation.byte_identical : c.observation.prepares !== 0))) {
    throw new CliError("Supplement verification/source drift");
  }
  for (const [i, rec] of config.images.entries()) {
    const bytes = await readFile(outputPath(root, path.join(parent, "prepared", rec.fileName)));
    const asset = verification.assets[i];
    if (asset.fileName !== rec.fileName || asset.sizeBytes !== bytes.length || asset.sha256 !== digest(bytes)
        || asset.targetVersionCode !== rec.versionCode || asset.targetVersionName !== rec.versionName
        || asset.targetImageSha256 !== rec.sha256 || asset.targetBytes !== rec.bytes
        || asset.purpose !== config.purpose || asset.kind !== "full-initialization") throw new CliError("Supplement asset identity drift");
  }
  return { schema: "p51-start-state-supplement-v1", mode: "start-state-supplement", task: config.task,
    purpose: config.purpose, isFormalRelease: false, productionPublishable: false, readyRegistered: false,
    runner: ownership(env), workflow: { commitSha: env.GITHUB_WORKFLOW_SHA, ref: env.GITHUB_WORKFLOW_REF },
    originalBuild: { ...originalOwner, artifactId: config.originalArtifact, archive: config.archive,
      artifactReceipt: config.artifact, buildTimestamp: config.buildTimestamp, build: proof.build,
      elfMapRelationship: proof.elfMapRelationship },
    derivation: "immutable-finalized-start-images/FULL-envelope-only", sourceCompilations: 0,
    originalImages: config.images, boot: { ...proof.boot, firmwareRebuilt: false, includedInSupplement: false },
    key: { ...proof.build.keyBinding, exactOriginalBuildBindingMatched: true }, assets: verification.assets,
    noReferenceSearch: true, target30319Regenerated: false, hardwareAcceptance: "NOT_RUN",
    noCloudMutation: true, noDeviceOperation: true, setupExcludedFromP5Statistics: true };
}

async function main() {
  const mode = process.argv[2];
  if (!["gate", "inputs", "package", "cleanup"].includes(mode)) throw new CliError("Unknown candidate mode");
  const options = args(process.argv.slice(3), ["python", "cc"]);
  const root = projectRoot(), env = process.env, out = area(root);
  if (realpathSync.native(process.cwd()) !== root) throw new CliError("Explicit active worktree required");
  if (mode === "cleanup") {
    const receipt = await cleanupCandidate(root, env);
    await writeOutput(root, path.join(out, "evidence/cleanup.json"), JSON.stringify(receipt) + "\n");
    process.stdout.write("P51_PRIVATE_CLEANUP_VERIFIED\n");
    return;
  }
  const inputMode = candidateMode(env);
  const manifestFile = path.join(root, inputMode === "start-state-supplement" ? "Tools/ota/p51-start-state-inputs.json"
    : inputMode === "new-source" ? "Tools/ota/p51-new-source-inputs.json" : "Tools/ota/p51-candidate-inputs.json");
  const manifestBytes = await readFile(manifestFile), manifest = JSON.parse(manifestBytes);
  const owner = verifyCandidateCheckout(root, env, manifest);
  if (mode === "gate") { process.stdout.write("P51_ARTIFACT_ONLY_ADMITTED\n"); return; }
  const privateDir = outputPath(root, path.join(out, "private"));
  const evidence = outputPath(root, path.join(out, "evidence"));
  await mkdir(evidence, { recursive: true });
  const run = async (mode, extra = [], childEnv = env) => {
    const label = mode === "command" ? path.basename(extra[1], ".json") : mode;
    const argv = ["-I", "-S", "-B", "-X", "utf8", path.join(root, "Tools/ota/p51-package.py"), mode,
      "--root-out", out, "--cc", options.cc ?? "gcc", ...extra];
    const result = spawnSync(options.python ?? "python3", argv,
      { cwd: root, env: childEnv, encoding: "utf8", windowsHide: true, timeout: 660000, maxBuffer: 16 * 1024 * 1024 });
    const ok = !result.error && result.status === 0;
    await writeOutput(root, path.join(evidence, `${label}.stdout.txt`), redactCandidate(result.stdout, env.OTA_AES_KEY));
    await writeOutput(root, path.join(evidence, `${label}.stderr.txt`), redactCandidate(result.stderr, env.OTA_AES_KEY));
    await writeOutput(root, path.join(evidence, `${label}-process.json`), JSON.stringify({ stage: mode, argv,
      exitCode: result.status, signal: result.signal, timeout: result.error?.code === "ETIMEDOUT", ok }) + "\n");
    if (!ok) throw new CliError("Candidate adapter failed; bounded process receipt retained", "INVALID_PARAMETER", 1);
    return result;
  };
  if (mode === "inputs") {
    if (env.OTA_AES_KEY) throw new CliError("Input admission must run without the packaging secret");
    await run(inputMode === "start-state-supplement" ? "supplement-inputs" : inputMode === "new-source" ? "source-inputs" : "inputs");
    await writeOutput(root, path.join(evidence, "input-binding.json"), JSON.stringify({ manifestSha256: digest(manifestBytes), owner }) + "\n");
    return;
  }
  if (inputMode === "start-state-supplement") {
    const binding = JSON.parse(await readFile(path.join(evidence, "input-binding.json")));
    if (binding.manifestSha256 !== digest(manifestBytes) || JSON.stringify(binding.owner) !== JSON.stringify(owner)) {
      throw new CliError("Supplement input/runner owner changed");
    }
    const build = JSON.parse(await readFile(path.join(out, "inputs/supplement-build.json")));
    verifyBuildKeyBinding(build, env);
    verifyBuildConfiguration(build, "p34-v2-candidate");
    if (existsSync(privateDir)) throw new CliError("Preserve earlier candidate private state");
    await mkdir(privateDir);
    await writeOutput(root, path.join(privateDir, "owner.json"), JSON.stringify(owner));
    try {
      await writeOutput(root, path.join(privateDir, "key.h"), firmwareKeyHeader(env.OTA_AES_KEY));
      await run("supplement-package");
      verifyCandidateCheckout(root, env, manifest);
      verifyBuildKeyBinding(build, env);
      const metadata = await supplementMetadata(root, env, manifest);
      await writeOutput(root, path.join(out, "prepared/supplement-metadata.json"), JSON.stringify(metadata, null, 2) + "\n");
      process.stdout.write("P51_START_STATE_SUPPLEMENT_PACKAGED; preparation-only, hardware NOT_RUN\n");
    } finally { await cleanupCandidate(root, env); }
    return;
  }
  if (inputMode === "new-source") {
    const binding = JSON.parse(await readFile(path.join(evidence, "input-binding.json")));
    if (binding.manifestSha256 !== digest(manifestBytes) || JSON.stringify(binding.owner) !== JSON.stringify(owner)) {
      throw new CliError("Candidate new-source input owner changed");
    }
    if (existsSync(privateDir)) throw new CliError("Preserve earlier candidate private state");
    await mkdir(privateDir);
    await writeOutput(root, path.join(privateDir, "owner.json"), JSON.stringify(owner));
    try {
      let counter = 0;
      const execute = async (tool, argv, options) => {
        const label = `compiler-${++counter}`;
        const request = outputPath(root, path.join(privateDir, label + ".json"));
        await writeOutput(root, request, JSON.stringify({ label, argv: [tool, ...argv], timeout: 600 }));
        // The adapter alone receives the key for redaction; its compiler tree does not.
        let result;
        try { result = await run("command", ["--command-json", request], { ...options.env, OTA_AES_KEY: env.OTA_AES_KEY }); }
        catch { result = { status: 1 }; }
        const receipt = JSON.parse(await readFile(path.join(evidence, "native", label + ".process.json")));
        return { status: result.status === 0 ? receipt.exitCode : 1,
          stdout: await readFile(path.join(evidence, "native", label + ".stdout.txt"), "utf8"),
          stderr: await readFile(path.join(evidence, "native", label + ".stderr.txt"), "utf8"),
          treeCleanupComplete: receipt.treeCleanupComplete };
      };
      const build = await buildSourceCandidate({ root, env, config: manifest, execute });
      await writeOutput(root, path.join(privateDir, "key.h"), firmwareKeyHeader(env.OTA_AES_KEY));
      await writeOutput(root, path.join(out, "inputs/source-build.json"), JSON.stringify({ build, owner,
        configSha256: digest(manifestBytes), reviewedProductBaseline: manifest.reviewedProductBaseline,
        workflowCommit: env.GITHUB_WORKFLOW_SHA, baseVersion: env.INPUT_CANDIDATE_BASE_VERSION,
        targetVersion: env.INPUT_VERSION_NAME, fullBaseVersion: env.INPUT_CANDIDATE_FULL_BASE_VERSION || "" }) + "\n");
      await run("source-package");
      verifyCandidateCheckout(root, env, manifest);
      verifyBuildKeyBinding(build, env);
      const metadata = await sourceMetadata(root, env, manifest, build);
      await writeOutput(root, path.join(out, "prepared/candidate-metadata.json"), JSON.stringify(metadata, null, 2) + "\n");
      await writeOutput(root, path.join(evidence, "inputs.json"), manifestBytes);
      process.stdout.write("P51_NEW_SOURCE_PACKAGED; formal candidate binding and hardware NOT_RUN\n");
    } finally { await cleanupCandidate(root, env); }
    return;
  }
  const buildBytes = await readFile(path.join(out, "inputs/build.json"));
  if (digest(buildBytes) !== manifest.packet.members.build.sha256) throw new CliError("Original CI key/build input changed");
  const build = JSON.parse(buildBytes);
  if (digest(await readFile(path.join(out, "inputs/manifest.json"))) !== digest(Buffer.from(JSON.stringify(manifest, null, 2) + "\n"))) {
    throw new CliError("Candidate admitted manifest changed");
  }
  const binding = JSON.parse(await readFile(path.join(evidence, "input-binding.json")));
  if (binding.manifestSha256 !== digest(manifestBytes) || JSON.stringify(binding.owner) !== JSON.stringify(owner)) {
    throw new CliError("Candidate input owner changed");
  }
  verifyBuildKeyBinding(build, env);
  verifyBuildConfiguration(build, "p34-v2-candidate");
  if (existsSync(privateDir)) throw new CliError("Preserve earlier candidate private state");
  await mkdir(privateDir);
  await writeOutput(root, path.join(privateDir, "owner.json"), JSON.stringify(owner));
  try {
    await writeOutput(root, path.join(privateDir, "key.h"), firmwareKeyHeader(env.OTA_AES_KEY));
    await run("package");
    const metadata = await candidateMetadata(root, env, manifest);
    await writeOutput(root, path.join(out, "prepared/candidate-metadata.json"), JSON.stringify(metadata, null, 2) + "\n");
    await writeOutput(root, path.join(evidence, "inputs.json"), manifestBytes);
    process.stdout.write("P51_PROTECTED_CANDIDATE_PACKAGED; release and physical acceptance NOT_RUN\n");
  } finally { await cleanupCandidate(root, env); }
}

if (process.argv[1] && import.meta.url === pathToFileURL(path.resolve(process.argv[1])).href) main().catch(failure);
