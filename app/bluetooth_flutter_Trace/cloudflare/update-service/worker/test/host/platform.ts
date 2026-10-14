import { createHash } from "node:crypto";
import { readdirSync, readFileSync } from "node:fs";
import { fileURLToPath } from "node:url";
import { SqliteD1 } from "./sqlite-d1";
import type { WorkerEnv } from "../../src/types";

// Only the external platform surface is substituted. Business handlers and SQL
// are the production modules. These memory R2/KV/DO doubles are explicitly not
// remote R2, Access or workerd evidence.
export class DurableObject {
  constructor(protected ctx: DurableObjectState, protected env: WorkerEnv) {}
}

class HostDigestStream extends WritableStream<ArrayBuffer | ArrayBufferView> {
  readonly digest: Promise<ArrayBuffer>;
  constructor(algorithm: string) {
    const hash = createHash(algorithm.replace("-", "").toLowerCase());
    let complete!: (value: ArrayBuffer) => void;
    let fail!: (error: unknown) => void;
    const digest = new Promise<ArrayBuffer>((resolve, reject) => { complete = resolve; fail = reject; });
    super({
      write(value) { hash.update(value instanceof ArrayBuffer ? new Uint8Array(value)
        : new Uint8Array(value.buffer, value.byteOffset, value.byteLength)); },
      close() { complete(Uint8Array.from(hash.digest()).buffer); }, abort(error) { fail(error); }
    });
    this.digest = digest;
  }
}
Object.defineProperty(crypto, "DigestStream", { value: HostDigestStream, configurable: true });

class MemoryBucket {
  objects = new Map<string, { bytes: Uint8Array; options: R2PutOptions; etag: string }>();
  async put(key: string, value: BodyInit, options: R2PutOptions = {}) {
    const bytes = new Uint8Array(await new Response(value).arrayBuffer());
    const onlyIf = options.onlyIf as R2Conditional | undefined;
    if (onlyIf?.etagDoesNotMatch === "*" && this.objects.has(key)) return null;
    this.objects.set(key, { bytes, options, etag: createHash("md5").update(bytes).digest("hex") });
    return this.head(key);
  }
  async head(key: string) {
    const entry = this.objects.get(key);
    if (!entry) return null;
    const { bytes, options, etag } = entry;
    return { key, version: etag, size: bytes.byteLength, etag, httpEtag: `"${etag}"`, uploaded: new Date(), checksums: {},
      customMetadata: options.customMetadata ?? {}, httpMetadata: options.httpMetadata ?? {}, storageClass: "Standard",
      writeHttpMetadata(headers: Headers) {
        const metadata = options.httpMetadata as R2HTTPMetadata | undefined;
        if (metadata?.contentType) headers.set("Content-Type", metadata.contentType);
        if (metadata?.cacheControl) headers.set("Cache-Control", metadata.cacheControl);
      } };
  }
  async get(key: string, options: R2GetOptions = {}) {
    const condition = options.onlyIf as R2Conditional | undefined;
    if (condition?.etagMatches?.startsWith('"') && condition.etagMatches.endsWith('"')) {
      throw new TypeError("Conditional ETag should not be wrapped in quotes");
    }
    const head = await this.head(key);
    if (!head) return null;
    if (condition?.etagMatches !== undefined && condition.etagMatches !== head.etag) return head;
    const bytes = this.objects.get(key)!.bytes;
    const range = options.range as { offset?: number; length?: number } | undefined;
    const start = range?.offset ?? 0;
    const sliced = bytes.slice(start, range?.length === undefined ? undefined : start + range.length);
    return { ...head, body: new Response(sliced).body!, bodyUsed: false,
      range: range ? { offset: start, length: sliced.length } : undefined,
      async arrayBuffer() { return sliced.buffer; }, async text() { return new TextDecoder().decode(sliced); },
      async json() { return JSON.parse(new TextDecoder().decode(sliced)); } };
  }
  async delete(key: string | string[]) { for (const k of typeof key === "string" ? [key] : key) this.objects.delete(k); }
  async list(options: R2ListOptions = {}) {
    const objects = [];
    for (const key of this.objects.keys()) if (key.startsWith(options.prefix ?? "")) objects.push(await this.head(key));
    return { objects, truncated: false, delimitedPrefixes: [] };
  }
}
class MemoryKv {
  values = new Map<string, string>();
  async put(key: string, value: string) { this.values.set(key, value); }
  async get(key: string, type?: string | { type: string }) {
    const value = this.values.get(key);
    if (value === undefined) return null;
    return type === "json" || (typeof type === "object" && type.type === "json") ? JSON.parse(value) : value;
  }
  async delete(key: string) { this.values.delete(key); }
}
const hits = new Map<string, number[]>();
export const hostDb = new SqliteD1();
const migrationDir = fileURLToPath(new URL("../../../migrations/", import.meta.url));
export const env = {
  DB: hostDb, RELEASES_BUCKET: new MemoryBucket(), MANIFEST_CACHE: new MemoryKv(),
  RATE_LIMITER: { getByName() { return { check(key: string, limit: number, window: number) {
    const now = Date.now();
    const times = (hits.get(key) ?? []).filter((time) => time >= now - window * 1000);
    if (times.length >= limit) return { allowed: false, retryAfter: window };
    times.push(now); hits.set(key, times); return { allowed: true, retryAfter: 0 };
  } }; } },
  APP_ID: "trace", ENVIRONMENT: "dev", GITHUB_OWNER: "Eitan-S-23", GITHUB_REPO: "Trace",
  DOWNLOAD_TOKEN_KEY_VERSION: "dev", DOWNLOAD_TOKEN_TTL_SECONDS: "300", MANIFEST_CACHE_TTL_SECONDS: "60",
  RATE_LIMIT_WINDOW_SECONDS: "60", RATE_LIMIT_MAX_REQUESTS: "10000", ENABLE_DIRECT_ADMIN_API: "false",
  DOWNLOAD_HMAC_KEY_CURRENT: "test-download-hmac-key", DOWNLOAD_TOKEN_PREVIOUS_KEY_VERSION: "previous",
  DOWNLOAD_HMAC_KEY_PREVIOUS: "test-previous-download-hmac-key", FIRMWARE_V2_CUTOVER_EPOCH: "1780000000",
  DEPLOY_TOKEN_SHA256: "c23a45cfa237db77c09def37bfb4bfc7e263fd92bdbc6663021240f5f788f9b5",
  TEST_MIGRATIONS: readdirSync(migrationDir).filter((name) => name.endsWith(".sql")).sort()
    .map((name) => ({ name, sql: readFileSync(`${migrationDir}/${name}`, "utf8") }))
} as unknown as WorkerEnv & { TEST_MIGRATIONS: Array<{ name: string; sql: string }> };

export async function applyD1Migrations(_db: D1Database, migrations: Array<{ name: string; sql: string }>) {
  for (const migration of migrations) hostDb.migrate(migration.sql);
}
export function createExecutionContext(): ExecutionContext {
  return { waitUntil(promise: Promise<unknown>) { void promise; }, passThroughOnException() {}, props: {} } as ExecutionContext;
}
export const SELF = { async fetch(input: RequestInfo | URL, init?: RequestInit) {
  const { default: worker } = await import("../../src/index");
  return worker.fetch(new Request(input, init), env, createExecutionContext());
} };
