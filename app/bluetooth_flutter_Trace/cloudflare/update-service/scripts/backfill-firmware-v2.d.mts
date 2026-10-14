export function backfillFirmwareV2(options: { db: D1Database; bucket: R2Bucket; manifest: unknown;
  approvedManifestSha256: string; readArtifact(locator: string): Promise<Uint8Array> }): Promise<{
  migrated: string[]; reused: string[]; quarantined: { releaseId: string; reason: string }[]; approvedManifestSha256: string;
}>;
