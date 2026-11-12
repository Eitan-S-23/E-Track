import { CliError } from "../../app/bluetooth_flutter_Trace/cloudflare/update-service/scripts/firmware-cli.mjs";
import { versionCodeFor } from "../../app/bluetooth_flutter_Trace/cloudflare/update-service/scripts/firmware-schema.mjs";
import { automaticCandidateAdmission } from "./original-admin-candidate.mjs";

export const ADMIN_CANDIDATE_ORIGIN = "https://trace-update-service-staging.tangjichentudou.workers.dev";
export const ADMIN_CANDIDATE_BUCKET = "trace-update-staging-releases";

export function adminCandidateAdmission(env) {
  const automatic = env.FIRMWARE_RELEASE_MODE === "original-admin-candidate";
  if (automatic) automaticCandidateAdmission(env);
  if (env.GITHUB_ACTIONS !== "true" || (!automatic && env.GITHUB_EVENT_NAME !== "workflow_dispatch")
      || env.GITHUB_REPOSITORY !== "Eitan-S-23/E-Track" || env.INPUT_PREPARE_ADMIN_CANDIDATE !== "true"
      || env.OTA_BOOT_CHAIN_READY !== "false" || env.INPUT_FIRMWARE_BUILD_PROFILE !== "p34-v2-candidate"
      || !/^[0-9a-f]{40}$/.test(env.GITHUB_SHA ?? "") || env.INPUT_CANDIDATE_REVIEWED_COMMIT !== env.GITHUB_SHA
      || !/^[1-9][0-9]*$/.test(env.GITHUB_RUN_ID ?? "") || env.GITHUB_RUN_ATTEMPT !== "1"
      || ["INPUT_PUBLISH", "INPUT_REHEARSAL", "INPUT_CHECK_BINDINGS", "INPUT_PACKAGE_CANDIDATE", "INPUT_STAGE_CANDIDATE"]
        .some(name => env[name] !== "false")
      || env.INPUT_CANDIDATE_FULL_BASE_VERSION || env.INPUT_APPROVED_REHEARSAL_RUN_ID) {
    throw new CliError("Normal Admin candidates require an explicit locked-production-gate dispatch; no mixed mode or automatic rerun");
  }
  const versionCode = versionCodeFor(env.INPUT_VERSION_NAME);
  if (automatic && (versionCode <= 30324 || env.INPUT_CANDIDATE_BASE_VERSION)) {
    throw new CliError("Automatic candidates require a fresh version above 3.3.24 and never generate a delta");
  }
  if (versionCode !== 30321 && versionCode <= 30322) throw new CliError("Select the actual installed V2 baseline or a fresh normal version above 3.3.22");
  if (!env.INPUT_RELEASE_NOTES?.trim() || env.INPUT_RELEASE_NOTES.length > 8000) throw new CliError("Candidate release notes are required");
  const baseVersionName = env.INPUT_CANDIDATE_BASE_VERSION || null;
  const baseVersionCode = baseVersionName ? versionCodeFor(baseVersionName) : null;
  if (baseVersionCode !== null && baseVersionCode >= versionCode) throw new CliError("Delta base must precede the target version");
  return { workflowCommit: env.GITHUB_SHA, runId: env.GITHUB_RUN_ID,
    versionName: env.INPUT_VERSION_NAME, versionCode, baseVersionName, baseVersionCode };
}
