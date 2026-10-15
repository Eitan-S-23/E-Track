export interface FirmwareKeyBinding {
  schemaVersion: 1; keyId: 1; source: "approved-ci-key-v1" | "development-ci-key-v1";
  keySha256: string; headerSha256: string; keySourceSha256: string;
}
export const DEVELOPMENT_PACKAGING_KEY: string;
export function firmwareKeyHeader(key: string): string;
export function firmwareKeyBinding(key: string, source: string): FirmwareKeyBinding;
export function validateKeyBinding(value: unknown): FirmwareKeyBinding;
export function approvedFirmwareKey(env: Record<string, string | undefined>): FirmwareKeyBinding;
export function verifyBuildKeyBinding(build: { keyBinding?: unknown }, env: Record<string, string | undefined>): FirmwareKeyBinding;
