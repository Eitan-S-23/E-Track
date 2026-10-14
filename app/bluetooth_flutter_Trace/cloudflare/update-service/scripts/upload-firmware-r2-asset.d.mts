export function uploadFirmwareAsset(metadata: unknown, fileName: string, bytes: Uint8Array, bucket: R2Bucket, requestId?: string): Promise<{
  ok: true; status: "UPLOADED" | "ALREADY_PRESENT"; requestId: string; kind: string; fileName: string; r2Key: string;
  sha256: string; sizeBytes: number; contentDigest: string;
}>;
