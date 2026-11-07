import { constants } from "node:fs";
import { copyFile, mkdir, readFile } from "node:fs/promises";
import path from "node:path";
import { CliError, outputPath } from "../../app/bluetooth_flutter_Trace/cloudflare/update-service/scripts/firmware-cli.mjs";
import { canonicalJson, versionCodeFor } from "../../app/bluetooth_flutter_Trace/cloudflare/update-service/scripts/firmware-schema.mjs";
import { digest, prepareFirmwareCandidate } from "../../app/bluetooth_flutter_Trace/cloudflare/update-service/scripts/prepare-firmware-release.mjs";
import { verifyBuildKeyBinding } from "../../app/bluetooth_flutter_Trace/cloudflare/update-service/scripts/firmware-release-key.mjs";
import { verifyBuildConfiguration } from "../../app/bluetooth_flutter_Trace/cloudflare/update-service/scripts/firmware-build-profile.mjs";
import { candidateAdmission, candidateMode } from "./firmware-candidate-context.mjs";

const fail = message => new CliError(message, "INVALID_PARAMETER", 1);
const file = (root, out, name) => outputPath(root, path.join(out, name));

export function verifyNormalCheckout(root, env, config, git) {
  candidateAdmission(env);
  const products = ["USER", "ArduinoAPI", "Libraries", "MDK-ARM_F435", "boot", "cmake", "vendor", "Simulator", "bsdiff_lzma_AES128-main", "segger_rtt"];
  const changed = ["USER/App/Pages/FirmwareUpdate/FirmwareUpdate.cpp", "USER/App/Pages/FirmwareUpdate/FirmwareUpdate.h",
    "USER/App/Pages/RouteSelect/RouteSelect.cpp", "USER/App/Utils/lv_ext/lv_file_browser_label.h"];
  if (candidateMode(env) !== "normal-delta" || config.schema !== "p51-normal-inputs-v1"
      || config.mode !== "normal-delta" || config.task !== "P51-DELTA-01" || config.repository !== env.GITHUB_REPOSITORY
      || config.profile !== "p34-v2-candidate" || config.baseVersion !== env.INPUT_CANDIDATE_BASE_VERSION
      || config.targetVersion !== env.INPUT_VERSION_NAME || config.productionPublishable !== false
      || config.purpose !== "normal-upgrade" || config.basePurpose !== "preparation-only/forward-baseline-initialization"
      || config.derivation !== "two-archived-GCC-executables/normal-preparer"
      || config.timestampPolicy !== "preserve-each-original-build-timestamp"
      || config.baseSourceCommit !== "18f6b3d3af0c24b1ce81573700cd61005b7c530e"
      || config.targetSourceCommit !== "1430c8ff7f3bcd9a35bfe158ba697b99021f75f2"
      || canonicalJson(config.productPaths) !== canonicalJson(products)
      || canonicalJson(config.sourceChangePaths) !== canonicalJson(changed)) throw fail("Normal reviewed input contract mismatch");
  git(["merge-base", "--is-ancestor", config.targetSourceCommit, env.GITHUB_SHA]);
  if (git(["diff", "--name-only", config.targetSourceCommit, env.GITHUB_SHA, "--", ...products])
      || git(["diff", "--name-only", "HEAD"])
      || git(["status", "--porcelain", "--untracked-files=all", "--", ...products])
      || git(["diff", "--name-only", config.baseSourceCommit, config.targetSourceCommit, "--", ...products]).split(/\r?\n/).sort().join("\n") !== changed.join("\n")) {
    throw fail("Normal candidate product/source delta or checkout drift");
  }
}

export async function packageNormalCandidate({ root, out, env, config, execute, python = "python3", bsdiff = env.BSDIFF_EXE }) {
  const owner = candidateAdmission(env);
  if (candidateMode(env) !== "normal-delta") throw fail("Normal candidate mode required");
  const proof = JSON.parse(await readFile(file(root, out, "inputs/normal-source-proof.json")));
  if (proof.schema !== "p51-normal-source-proof-v1" || canonicalJson(proof.config) !== canonicalJson(config)
      || proof.sourceCompilations !== 0 || proof.referenceSearches !== 0 || proof.sourceChangesOutsideFwHeader !== true
      || proof.isFormalRelease !== false || proof.bootInstallation !== "FORBIDDEN") throw fail("Normal source proof mismatch");
  for (const role of ["base", "target"]) verifyBuildKeyBinding(proof.roles[role].originalBuild, env);
  const toolFile = file(root, out, "inputs/tools/" + path.basename(bsdiff));
  await mkdir(path.dirname(toolFile), { recursive: true });
  await copyFile(path.resolve(bsdiff), toolFile, constants.COPYFILE_EXCL);
  const toolBytes = await readFile(toolFile);
  if (!toolBytes.equals(await readFile(path.resolve(bsdiff)))) throw fail("Copied bsdiff tool differs from producer input");
  const results = {};
  for (const role of ["base", "target"]) {
    const source = proof.roles[role], original = source.originalBuild;
    if (original.commitSha !== config[role === "base" ? "baseSourceCommit" : "targetSourceCommit"]) {
      throw fail("Normal original source commit mismatch");
    }
    verifyBuildKeyBinding(original, env);
    verifyBuildConfiguration(original, config.profile);
    for (const record of Object.values(source.files)) {
      const bytes = await readFile(file(root, out, "inputs/" + record.path));
      if (bytes.length !== record.bytes || digest(bytes) !== record.sha256) throw fail("Normal original file changed");
    }
    const versionName = config[role === "base" ? "baseVersion" : "targetVersion"];
    const build = { ...original, versionName, versionCode: versionCodeFor(versionName) };
    const release = { releaseTag: `mcu-e-track-at32f435-v${versionName}`, runId: owner.runId, commitSha: original.commitSha,
      versionName, releaseNotes: role === "base" ? "P51 forward baseline initialization only; not a formal release"
        : "P51 normal delta candidate; original UI source change, not production approval",
      targetHardware: "AT32F435RGT7", hardwareRevision: 1, layoutId: 1, minBootVersion: 1,
      minProtocolVersion: 1, minAppVersionCode: 0 };
    const sourceDir = file(root, out, `inputs/originals/${role}/keyed-build`);
    let base, baseFile, basePreparation;
    if (role === "target") {
      baseFile = file(root, out, "normal/base/app-final.bin");
      basePreparation = file(root, out, "normal/base/verification.json");
      const initial = results.base.summary, bytes = await readFile(basePreparation);
      base = { provenanceKind: "p51-normal-candidate-v1", isFormalRelease: false, kind: "app",
        versionName: config.baseVersion, versionCode: versionCodeFor(config.baseVersion),
        commitSha: initial.commitSha, buildTimestamp: initial.build.buildTimestamp,
        imageSha256: initial.finalImage.sha256, sourceSha256: initial.finalImage.sha256,
        sourceSizeBytes: initial.finalImage.sizeBytes, sourcePreparationSha256: digest(bytes), producer: owner };
    }
    results[role] = await prepareFirmwareCandidate({ root, candidateEnv: env, app: path.join(sourceDir, "app/X-Track-App-GCC.bin"),
      boot: path.join(sourceDir, "boot/X-Track-Boot.bin"), build, release, repository: env.GITHUB_REPOSITORY,
      buildEvidenceDir: sourceDir, base, baseFile, basePreparation, outputDir: file(root, out, "normal/" + role),
      aesKey: env.OTA_AES_KEY, python, bsdiff: toolFile, execute });
    verifyBuildKeyBinding(original, env);
  }
  const comparison = results.target.summary.patchComparison;
  if (comparison.changesOutsideFwHeader !== true || comparison.preferredKindForMatchingBase !== "patch"
      || comparison.patchPackageBytes >= comparison.fullPackageBytes) throw fail("Normal candidate is not a beneficial real-source PATCH");
  const metadata = { schema: "p51-normal-candidate-v1", runner: owner, isFormalRelease: false, productionPublishable: false,
    readyRegistered: false, sourceCompilations: 0, referenceSearches: 0, finalizations: 2,
    derivation: config.derivation, originalBuilds: Object.fromEntries(Object.entries(proof.roles).map(([role, value]) => [role, value.originalBuild])),
    basePurpose: config.basePurpose, packagePurpose: "normal-upgrade", sourceProofSha256: digest(await readFile(file(root, out, "inputs/normal-source-proof.json"))),
    preparations: Object.fromEntries(await Promise.all(["base", "target"].map(async role => [role, {
      path: `normal/${role}/verification.json`, sha256: digest(await readFile(file(root, out, `normal/${role}/verification.json`)))}]))),
    baseVersionCode: versionCodeFor(config.baseVersion), versionCode: versionCodeFor(config.targetVersion),
    baseImageSha256: results.base.summary.finalImage.sha256, targetImageSha256: results.target.summary.finalImage.sha256,
    patchComparison: comparison, retainedBoot: proof.retainedBoot, bootInstallation: "FORBIDDEN",
    toolDependency: { path: "inputs/tools/" + path.basename(toolFile), bytes: toolBytes.length, sha256: digest(toolBytes) } };
  return metadata;
}
