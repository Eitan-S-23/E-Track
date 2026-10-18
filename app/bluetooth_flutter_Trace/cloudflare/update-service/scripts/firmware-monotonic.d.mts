import type { FirmwareRegistration } from "./firmware-schema.mjs";
export class FirmwareMonotonicError extends Error { readonly code: "RELEASE_CONFLICT"; }
export function verifyMonotonic(db: D1Database, metadata: FirmwareRegistration): Promise<{
  maxVersionCode: number | null; legacyMaxVersionCode: number | null; unresolvedLegacyChannels: number;
}>;
