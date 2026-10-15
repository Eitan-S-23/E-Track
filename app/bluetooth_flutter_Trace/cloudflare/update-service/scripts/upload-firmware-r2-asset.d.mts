export function assertFirmwareRuntime(platform?: string, release?: string): void;
export function verifyStoredFirmwareAsset(metadata: unknown, fileName: string, bucket: R2Bucket): Promise<{
  ok: true; kind: string; fileName: string; r2Key: string; sha256: string; sizeBytes: number; contentDigest: string;
}>;
export function uploadFirmwareAsset(metadata: unknown, fileName: string, bytes: Uint8Array, bucket: R2Bucket, requestId?: string): Promise<{
  ok: true; status: "UPLOADED" | "ALREADY_PRESENT"; requestId: string; kind: string; fileName: string; r2Key: string;
  sha256: string; sizeBytes: number; contentDigest: string;
}>;
export function withFirmwareBucket<T>(options: {
  bucketName: string; accountId: string; root?: string; wranglerCwd?: string; databaseId?: string; databaseName?: string;
}, operation: (bucket: R2Bucket, db?: D1Database) => Promise<T>): Promise<T>;
