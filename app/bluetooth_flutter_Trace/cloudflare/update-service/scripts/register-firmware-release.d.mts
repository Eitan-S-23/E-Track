export function registerFirmware(metadata: unknown, options: {
  serviceUrl: string; deployToken: string; fetcher?: typeof fetch; retries?: number; timeoutMs?: number; signal?: AbortSignal;
}): Promise<{ ok: true; state: "ready"; releaseId: string; requestId: string; idempotent: boolean; assetsRegistered: number }>;
