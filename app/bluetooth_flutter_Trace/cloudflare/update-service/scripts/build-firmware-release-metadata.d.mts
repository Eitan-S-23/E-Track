import type { FirmwareRegistration } from "./firmware-schema.mjs";
export function buildFirmwareMetadata(options: {
  release: Omit<FirmwareRegistration, "schemaVersion" | "appId" | "deviceModel" | "versionCode" | "targetImageSha256" | "transport" | "isFormalRelease" | "assets">;
  assetsDir: string; finalImage: string;
  patchBases?: Array<{ baseImageSha256: string; baseVersionCode: number }>;
  repository?: string;
}): Promise<FirmwareRegistration>;
