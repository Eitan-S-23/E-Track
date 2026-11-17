import { assetFileName, versionNameFor } from "../../scripts/firmware-schema.mjs";
import { storedAppDeltaFormat } from "./app_patch_format";

export function deltaFileName(job: {
  kind: "android" | "firmware"; base_version_code: number; target_version_code: number; base_sha256: string;
  input_json?: string;
}): string {
  return job.kind === "firmware"
    ? assetFileName("patch", versionNameFor(job.target_version_code), job.base_version_code)
    : `delta-${job.base_version_code}-${job.target_version_code}-${job.base_sha256.slice(0, 12)}.${storedAppDeltaFormat(job)}`;
}
