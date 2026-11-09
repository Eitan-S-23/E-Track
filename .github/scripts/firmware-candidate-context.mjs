import { CliError } from "../../app/bluetooth_flutter_Trace/cloudflare/update-service/scripts/firmware-cli.mjs";
import { versionCodeFor } from "../../app/bluetooth_flutter_Trace/cloudflare/update-service/scripts/firmware-schema.mjs";

// User-directed V2-only source, development checked; not an acceptance verdict.
export const UI_BASELINE = "bd751e4431755261d2978e994e24b5009961fca4";
export function candidateMode(env) {
  const mode = env.INPUT_CANDIDATE_MODE || "archived-original";
  if (!["archived-original", "new-source", "start-state-supplement", "normal-delta", "archived-benchmark"].includes(mode)) throw new CliError("Unknown candidate input mode");
  return mode;
}

export function candidateAdmission(env) {
  const mode = candidateMode(env);
  if (env.GITHUB_ACTIONS !== "true" || env.GITHUB_EVENT_NAME !== "workflow_dispatch"
      || env.GITHUB_REPOSITORY !== "Eitan-S-23/E-Track" || env.INPUT_PACKAGE_CANDIDATE !== "true"
      || env.INPUT_PUBLISH !== "false" || env.INPUT_REHEARSAL !== "false" || env.INPUT_CHECK_BINDINGS !== "false"
      || (env.INPUT_STAGE_CANDIDATE && env.INPUT_STAGE_CANDIDATE !== "false")
      || env.OTA_BOOT_CHAIN_READY !== "false"
      || env.INPUT_FIRMWARE_BUILD_PROFILE !== "p34-v2-candidate"
      || !/^[0-9a-f]{40}$/.test(env.GITHUB_SHA ?? "")
      || env.GITHUB_SHA !== env.INPUT_CANDIDATE_REVIEWED_COMMIT
      || !/^[1-9][0-9]*$/.test(env.GITHUB_RUN_ID ?? "") || !/^[1-9][0-9]*$/.test(env.GITHUB_RUN_ATTEMPT ?? "")) {
    throw new CliError("Candidate requires the exact reviewed source, protected locked-gate artifact-only dispatch");
  }
  if (Object.entries(env).some(([name, value]) => value &&
      /^(CLOUDFLARE_|CF_|TRACE_|GH_|GITHUB_TOKEN)/.test(name))) {
    throw new CliError("Candidate packaging must not receive cloud or publishing credentials");
  }
  if (mode === "archived-original") {
    if (env.INPUT_VERSION_NAME !== "3.3.16" || env.INPUT_CANDIDATE_BASE_VERSION || env.INPUT_CANDIDATE_FULL_BASE_VERSION
        || env.FIRMWARE_RELEASE_MODE || env.FIRMWARE_CANDIDATE_CONTEXT) {
      throw new CliError("Archived-original candidate requires its unchanged header-only inputs");
    }
  } else if (mode === "archived-benchmark") {
    if (env.FIRMWARE_RELEASE_MODE !== "artifact-candidate-benchmark"
        || env.FIRMWARE_CANDIDATE_CONTEXT !== "firmware-rehearsal/artifact-only-archived-benchmark-v1"
        || env.GITHUB_WORKFLOW_SHA !== env.GITHUB_SHA
        || !/^refs\/heads\/[A-Za-z0-9_./-]+$/.test(env.GITHUB_REF ?? "")
        || env.GITHUB_WORKFLOW_REF !== `Eitan-S-23/E-Track/.github/workflows/firmware-build.yml@${env.GITHUB_REF}`
        || env.INPUT_VERSION_NAME !== "3.3.21" || env.INPUT_CANDIDATE_BASE_VERSION !== "3.3.20"
        || env.INPUT_CANDIDATE_FULL_BASE_VERSION || env.INPUT_APPROVED_REHEARSAL_RUN_ID || env.INPUT_RELEASE_NOTES) {
      throw new CliError("Archived benchmark requires its exact finalized pair and protected artifact-only context");
    }
  } else if (mode === "normal-delta") {
    if (env.FIRMWARE_RELEASE_MODE !== "artifact-candidate-normal"
        || env.FIRMWARE_CANDIDATE_CONTEXT !== "firmware-rehearsal/artifact-only-normal-delta-v1"
        || env.GITHUB_WORKFLOW_SHA !== env.GITHUB_SHA
        || !/^refs\/heads\/[A-Za-z0-9_./-]+$/.test(env.GITHUB_REF ?? "")
        || env.GITHUB_WORKFLOW_REF !== `Eitan-S-23/E-Track/.github/workflows/firmware-build.yml@${env.GITHUB_REF}`
        || env.INPUT_CANDIDATE_FULL_BASE_VERSION || env.INPUT_APPROVED_REHEARSAL_RUN_ID || env.INPUT_RELEASE_NOTES
        || versionCodeFor(env.INPUT_CANDIDATE_BASE_VERSION) <= 30319
        || versionCodeFor(env.INPUT_VERSION_NAME) <= versionCodeFor(env.INPUT_CANDIDATE_BASE_VERSION)
        || env.INPUT_CANDIDATE_BASE_VERSION.length > 16 || env.INPUT_VERSION_NAME.length > 16) {
      throw new CliError("Normal delta requires the protected artifact-only context and a fresh forward pair above 30319");
    }
  } else if (mode === "start-state-supplement") {
    if (env.INPUT_VERSION_NAME !== "3.3.19" || env.INPUT_CANDIDATE_BASE_VERSION || env.INPUT_CANDIDATE_FULL_BASE_VERSION
        || env.FIRMWARE_RELEASE_MODE !== "artifact-candidate-supplement"
        || env.FIRMWARE_CANDIDATE_CONTEXT !== "firmware-rehearsal/artifact-only-start-state-v1"
        || env.GITHUB_WORKFLOW_SHA !== env.GITHUB_SHA
        || env.GITHUB_WORKFLOW_REF !== `Eitan-S-23/E-Track/.github/workflows/firmware-build.yml@${env.GITHUB_REF}`
        || !/^refs\/(heads|tags)\/[A-Za-z0-9_./-]+$/.test(env.GITHUB_REF ?? "")) {
      throw new CliError("Supplement requires its exact protected artifact-only workflow and immutable original target, no version overrides");
    }
  } else {
    if (env.FIRMWARE_RELEASE_MODE !== "artifact-candidate"
        || env.FIRMWARE_CANDIDATE_CONTEXT !== "firmware-rehearsal/artifact-only-new-source-v1"
        || env.GITHUB_WORKFLOW_SHA !== env.GITHUB_SHA
        || env.GITHUB_WORKFLOW_REF !== `Eitan-S-23/E-Track/.github/workflows/firmware-build.yml@${env.GITHUB_REF}`
        || !/^refs\/(heads|tags)\/[A-Za-z0-9_./-]+$/.test(env.GITHUB_REF ?? "")) {
      throw new CliError("New-source candidate requires the exact protected artifact-only workflow context");
    }
    const base = versionCodeFor(env.INPUT_CANDIDATE_BASE_VERSION), target = versionCodeFor(env.INPUT_VERSION_NAME);
    if (base <= 30316 || target <= base || env.INPUT_CANDIDATE_BASE_VERSION.length > 16
        || env.INPUT_VERSION_NAME.length > 16) {
      throw new CliError("New-source requires a fresh canonical forward version pair above the retained 30316");
    }
    if (env.INPUT_CANDIDATE_FULL_BASE_VERSION) {
      const fullBase = versionCodeFor(env.INPUT_CANDIDATE_FULL_BASE_VERSION);
      if (fullBase <= 30316 || fullBase >= target || fullBase === base || env.INPUT_CANDIDATE_FULL_BASE_VERSION.length > 16) {
        throw new CliError("Full-cell start must be a fresh lower version distinct from the patch base");
      }
    }
  }
  return { commitSha: env.GITHUB_SHA, runId: env.GITHUB_RUN_ID, runAttempt: env.GITHUB_RUN_ATTEMPT };
}
