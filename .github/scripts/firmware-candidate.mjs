import { execFileSync, spawnSync } from "node:child_process";
import { existsSync, lstatSync, realpathSync } from "node:fs";
import { mkdir, readFile, readdir, rm } from "node:fs/promises";
import path from "node:path";
import { pathToFileURL } from "node:url";
import { args, CliError, failure, outputPath, projectRoot, writeOutput } from "../../app/bluetooth_flutter_Trace/cloudflare/update-service/scripts/firmware-cli.mjs";
import { digest } from "../../app/bluetooth_flutter_Trace/cloudflare/update-service/scripts/prepare-firmware-release.mjs";
import { firmwareKeyHeader, verifyBuildKeyBinding } from "../../app/bluetooth_flutter_Trace/cloudflare/update-service/scripts/firmware-release-key.mjs";
import { verifyBuildConfiguration } from "../../app/bluetooth_flutter_Trace/cloudflare/update-service/scripts/firmware-build-profile.mjs";

export function candidateAdmission(env) {
  if (env.GITHUB_ACTIONS !== "true" || env.GITHUB_EVENT_NAME !== "workflow_dispatch"
      || env.GITHUB_REPOSITORY !== "Eitan-S-23/E-Track" || env.INPUT_PACKAGE_CANDIDATE !== "true"
      || env.INPUT_PUBLISH !== "false" || env.INPUT_REHEARSAL !== "false" || env.INPUT_CHECK_BINDINGS !== "false"
      || env.OTA_BOOT_CHAIN_READY !== "false" || env.INPUT_VERSION_NAME !== "3.3.16"
      || env.INPUT_FIRMWARE_BUILD_PROFILE !== "p34-v2-candidate"
      || !/^[0-9a-f]{40}$/.test(env.GITHUB_SHA ?? "")
      || env.GITHUB_SHA !== env.INPUT_CANDIDATE_REVIEWED_COMMIT
      || !/^[1-9][0-9]*$/.test(env.GITHUB_RUN_ID ?? "") || !/^[1-9][0-9]*$/.test(env.GITHUB_RUN_ATTEMPT ?? "")) {
    throw new CliError("Candidate requires the exact reviewed source, protected locked-gate artifact-only dispatch");
  }
  if (Object.entries(env).some(([name, value]) => value &&
      /^(CLOUDFLARE_|CF_API|TRACE_|GH_TOKEN|GITHUB_TOKEN)/.test(name))) {
    throw new CliError("Candidate packaging must not receive cloud or publishing credentials");
  }
  return { commitSha: env.GITHUB_SHA, runId: env.GITHUB_RUN_ID, runAttempt: env.GITHUB_RUN_ATTEMPT };
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
  const owner = candidateAdmission(env);
  const head = execFileSync("git", ["--no-optional-locks", "rev-parse", "HEAD"], { cwd: root, encoding: "utf8", windowsHide: true }).trim();
  if (head !== owner.commitSha) throw new CliError("Candidate checkout differs from reviewed source");
  if (mode === "gate") { process.stdout.write("P51_ARTIFACT_ONLY_ADMITTED\n"); return; }
  const manifestFile = path.join(root, "Tools/ota/p51-candidate-inputs.json");
  const manifestBytes = await readFile(manifestFile), manifest = JSON.parse(manifestBytes);
  const privateDir = outputPath(root, path.join(out, "private"));
  const evidence = outputPath(root, path.join(out, "evidence"));
  await mkdir(evidence, { recursive: true });
  const run = async mode => {
    const argv = ["-I", "-S", "-B", "-X", "utf8", path.join(root, "Tools/ota/p51-package.py"), mode,
      "--root-out", out, "--cc", options.cc ?? "gcc"];
    const result = spawnSync(options.python ?? "python3", argv,
      { cwd: root, env, encoding: "utf8", windowsHide: true, timeout: 600000, maxBuffer: 1024 * 1024 });
    const ok = !result.error && result.status === 0;
    await writeOutput(root, path.join(evidence, `${mode}.stdout.txt`), redactCandidate(result.stdout, env.OTA_AES_KEY));
    await writeOutput(root, path.join(evidence, `${mode}.stderr.txt`), redactCandidate(result.stderr, env.OTA_AES_KEY));
    await writeOutput(root, path.join(evidence, `${mode}-process.json`), JSON.stringify({ stage: mode, argv,
      exitCode: result.status, signal: result.signal, timeout: result.error?.code === "ETIMEDOUT", ok }) + "\n");
    if (!ok) throw new CliError("Candidate adapter failed; bounded process receipt retained", "INVALID_PARAMETER", 1);
  };
  if (mode === "inputs") {
    if (env.OTA_AES_KEY) throw new CliError("Input admission must run without the packaging secret");
    await run("inputs");
    await writeOutput(root, path.join(evidence, "input-binding.json"), JSON.stringify({ manifestSha256: digest(manifestBytes), owner }) + "\n");
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
