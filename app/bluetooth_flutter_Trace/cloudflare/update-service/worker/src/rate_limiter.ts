import { DurableObject } from "cloudflare:workers";
import type { WorkerEnv } from "./types";

interface CountRow {
  [key: string]: SqlStorageValue;
  count: number;
}

export class RateLimiter extends DurableObject<WorkerEnv> {
  constructor(ctx: DurableObjectState, env: WorkerEnv) {
    super(ctx, env);
    ctx.blockConcurrencyWhile(async () => {
      this.ctx.storage.sql.exec(`
        CREATE TABLE IF NOT EXISTS hits (
          key TEXT NOT NULL,
          timestamp_ms INTEGER NOT NULL
        );
        CREATE INDEX IF NOT EXISTS idx_hits_key_timestamp ON hits(key, timestamp_ms);
      `);
    });
  }

  check(key: string, limit: number, windowSeconds: number): { allowed: boolean; retryAfter: number } {
    const now = Date.now();
    const windowMs = windowSeconds * 1000;
    const cutoff = now - windowMs;

    this.ctx.storage.sql.exec("DELETE FROM hits WHERE timestamp_ms < ?", cutoff);
    const row = this.ctx.storage.sql
      .exec<CountRow>("SELECT COUNT(*) AS count FROM hits WHERE key = ? AND timestamp_ms >= ?", key, cutoff)
      .one();

    if (row.count >= limit) {
      return { allowed: false, retryAfter: windowSeconds };
    }

    this.ctx.storage.sql.exec("INSERT INTO hits (key, timestamp_ms) VALUES (?, ?)", key, now);
    return { allowed: true, retryAfter: 0 };
  }
}

export async function enforceRateLimit(
  env: WorkerEnv,
  key: string
): Promise<{ allowed: boolean; retryAfter: number }> {
  const windowSeconds = Number(env.RATE_LIMIT_WINDOW_SECONDS || "60");
  const limit = Number(env.RATE_LIMIT_MAX_REQUESTS || "60");
  const shard = rateLimitShard(key);
  const stub = env.RATE_LIMITER.getByName(`public:${shard}`);
  return stub.check(key, limit, windowSeconds);
}

function rateLimitShard(key: string): string {
  let hash = 0;
  for (let i = 0; i < key.length; i += 1) {
    hash = (hash * 31 + key.charCodeAt(i)) >>> 0;
  }
  return String(hash % 128);
}
