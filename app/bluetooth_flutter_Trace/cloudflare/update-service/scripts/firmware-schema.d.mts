export type FirmwareKind = "full" | "patch" | "recovery";
export interface FirmwareAssetMetadata {
  kind: FirmwareKind;
  fileName: string;
  sha256: string;
  sizeBytes: number;
  baseImageSha256: string;
  baseVersionCode: number;
  githubUrl: string;
  r2Key: string;
  r2Verified: boolean;
}
export interface FirmwareRegistration {
  schemaVersion: 2;
  appId: string;
  deviceModel: string;
  releaseTag: string;
  runId: string;
  commitSha: string;
  versionName: string;
  versionCode: number;
  releaseNotes: string;
  targetImageSha256: string;
  hardwareRevision: number;
  layoutId: number;
  minBootVersion: number;
  minProtocolVersion: number;
  targetHardware: string;
  transport: "ble";
  minAppVersionCode: number;
  isFormalRelease: true;
  assets: FirmwareAssetMetadata[];
}
export const FIRMWARE_MODEL: string;
export const U32_MAX: number;
export const APP_VERSION_MAX: number;
export class FirmwareSchemaError extends Error { code: "INVALID_PARAMETER" | "FORMAL_RELEASE_REQUIRED"; }
export function exactObject(value: unknown, keys: string[], label?: string): Record<string, unknown>;
export function text(value: unknown, label: string, allowEmpty?: boolean): string;
export function integer(value: unknown, label: string, max?: number, min?: number): number;
export function sha256(value: unknown, label: string): string;
export function versionCodeFor(version: unknown): number;
export function versionNameFor(code: number): string;
export function assetFileName(kind: FirmwareKind, targetVersion: string, baseVersionCode?: number): string;
export function r2KeyFor(release: Pick<FirmwareRegistration, "appId" | "deviceModel" | "versionCode" | "releaseTag">, asset: Pick<FirmwareAssetMetadata, "fileName">): string;
export function canonicalJson(value: unknown): string;
export function contentDigest(hex: string): string;
export function parseFirmwareRegistration(value: unknown, repository?: string, requireVerified?: boolean): FirmwareRegistration;
