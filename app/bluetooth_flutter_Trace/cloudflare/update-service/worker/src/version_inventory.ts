import { ApiError, invalidParameter } from "./errors";
import { json } from "./http";
import type { WorkerEnv } from "./types";

type InventoryEnv = Pick<WorkerEnv, "DB" | "APP_ID" | "VERSION_INVENTORY_ENABLED">;
type PublicInventoryEnv = InventoryEnv & Pick<WorkerEnv, "RATE_LIMITER">;
interface Control { refresh_id: string; requested_at: number; daily_limit: number }
interface Installation {
  sequence: number; state_hash: string; last_seen: number; report_day: string;
  day_count: number; refresh_id: string;
}
interface DeviceReport {
  deviceKey: string; identityScope: "installation"; deviceModel: string;
  versionCode: number; imageSha256: string; hardwareRevision: number; layoutId: number;
  observationId: string; ageSeconds: number;
}
const DAY = 86400;
const RETENTION = 90 * DAY;
const HEX = /^[0-9a-f]{64}$/;
const UUID = /^[0-9a-f]{8}-[0-9a-f]{4}-4[0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$/;

export async function sha256Text(value: string): Promise<string> {
  const bytes = await crypto.subtle.digest("SHA-256", new TextEncoder().encode(value));
  return Array.from(new Uint8Array(bytes), n => n.toString(16).padStart(2, "0")).join("");
}

export async function boundedJson(request: Pick<Request, "headers" | "body">, maximum = 8192): Promise<Record<string, unknown>> {
  if (!/^application\/json(?:\s*;|$)/i.test(request.headers.get("Content-Type") ?? "")) {
    throw invalidParameter("application/json required");
  }
  if (request.headers.has("Content-Encoding")) throw invalidParameter("Encoded request bodies are unsupported");
  const length = request.headers.get("Content-Length");
  if (length !== null && (!/^\d+$/.test(length) || Number(length) > maximum)) throw invalidParameter("Request too large");
  const reader = request.body?.getReader();
  if (!reader) throw invalidParameter("JSON body required");
  const chunks: Uint8Array[] = [];
  let total = 0;
  try {
    while (true) {
      const part = await reader.read();
      if (part.done) break;
      total += part.value.byteLength;
      if (total > maximum) { await reader.cancel(); throw invalidParameter("Request too large"); }
      chunks.push(part.value);
    }
  } finally { reader.releaseLock(); }
  const bytes = new Uint8Array(total);
  let offset = 0;
  for (const chunk of chunks) { bytes.set(chunk, offset); offset += chunk.length; }
  try {
    const value: unknown = JSON.parse(new TextDecoder("utf-8", { fatal: true }).decode(bytes));
    if (!value || typeof value !== "object" || Array.isArray(value)) throw new Error();
    return value as Record<string, unknown>;
  } catch { throw invalidParameter("Invalid JSON object"); }
}

function enabled(env: InventoryEnv) {
  if (env.VERSION_INVENTORY_ENABLED !== "true") throw new ApiError("BACKEND_UNAVAILABLE", "Version reporting is disabled", 503);
}
function integer(value: unknown, name: string, maximum = 4294967295): number {
  if (typeof value !== "number" || !Number.isSafeInteger(value) || value < 0 || value > maximum) throw invalidParameter(`Invalid ${name}`);
  return value;
}
function digest(value: unknown, name: string): string {
  if (typeof value !== "string" || !HEX.test(value)) throw invalidParameter(`Invalid ${name}`);
  return value;
}
async function control(env: InventoryEnv): Promise<Control> {
  const row = await env.DB.prepare("SELECT refresh_id, requested_at, daily_limit FROM version_inventory_control WHERE id=1").first<Control>();
  if (!row) throw new ApiError("BACKEND_UNAVAILABLE", "Inventory storage is not ready", 503);
  return row;
}
async function rate(request: Request, env: PublicInventoryEnv) {
  const ip = request.headers.get("CF-Connecting-IP");
  // Never derive inventory identities from IP addresses; this key only rate-limits ingress.
  const key = await sha256Text(`inventory:${ip ?? "unknown"}`);
  const result = await env.RATE_LIMITER.getByName(`inventory:${key.slice(0, 2)}`).check(key, 120, 3600);
  if (!result.allowed) throw new ApiError("RATE_LIMITED", "Version reporting rate limited", 429);
}

export async function inventoryControl(request: Request, env: PublicInventoryEnv): Promise<Response> {
  enabled(env);
  await rate(request, env);
  const current = await control(env);
  return json({ ok: true, refreshId: current.refresh_id, requestedAt: current.requested_at,
    reportIntervalSeconds: DAY, controlIntervalSeconds: 14400 }, 200, { "Cache-Control": "private, max-age=300" });
}

export async function reportInventory(request: Request, env: PublicInventoryEnv, now = Math.floor(Date.now() / 1000)): Promise<Response> {
  enabled(env);
  await rate(request, env);
  const token = request.headers.get("Authorization")?.match(/^Bearer ([0-9a-f]{64})$/)?.[1];
  if (!token) throw new ApiError("TOKEN_INVALID", "Installation reporting token required", 401);
  const key = await sha256Text(token);
  const body = await boundedJson(request);
  if (body.appId !== env.APP_ID || body.platform !== "android") throw invalidParameter("Unsupported reporting scope");
  const sequence = integer(body.sequence, "sequence", Number.MAX_SAFE_INTEGER);
  if (!sequence) throw invalidParameter("Positive sequence required");
  const versionCode = integer(body.versionCode, "versionCode", 2100000000);
  const versionName = body.versionName;
  if (typeof versionName !== "string" || !/^[\w.+-]{1,64}$/.test(versionName)) throw invalidParameter("Invalid versionName");
  const imageSha = digest(body.imageSha256, "imageSha256");
  if (!Array.isArray(body.devices) || body.devices.length > 4) throw invalidParameter("At most four device observations required");
  const devices: DeviceReport[] = body.devices.map((value: unknown) => {
    if (!value || typeof value !== "object" || Array.isArray(value)) throw invalidParameter("Invalid device observation");
    const d = value as Record<string, unknown>;
    if (d.identityScope !== "installation" || d.deviceModel !== "e-track-at32f435") throw invalidParameter("Unqualified device identity");
    if (typeof d.observationId !== "string" || !UUID.test(d.observationId)) throw invalidParameter("Invalid observationId");
    return { deviceKey: digest(d.deviceKey, "deviceKey"), identityScope: "installation", deviceModel: d.deviceModel,
      versionCode: integer(d.versionCode, "device versionCode"), imageSha256: digest(d.imageSha256, "device imageSha256"),
      hardwareRevision: integer(d.hardwareRevision, "hardwareRevision", 65535), layoutId: integer(d.layoutId, "layoutId", 65535),
      observationId: d.observationId, ageSeconds: integer(d.ageSeconds, "ageSeconds", RETENTION) };
  });
  if (new Set(devices.map(d => d.deviceKey)).size !== devices.length) throw invalidParameter("Duplicate device observation");
  // Exclude the increasing age of a cached observation from retry identity.
  const stateHash = await sha256Text(JSON.stringify([versionCode, versionName, imageSha,
    devices.map(({ ageSeconds: _age, ...identity }) => identity).sort((a, b) => a.deviceKey.localeCompare(b.deviceKey))]));
  const current = await control(env);
  const previous = await env.DB.prepare("SELECT sequence,state_hash,last_seen,report_day,day_count,refresh_id FROM version_inventory_installations WHERE install_key=?")
    .bind(key).first<Installation>();
  const response = (accepted: boolean, next = DAY) => json({ ok: true, accepted, refreshId: current.refresh_id, nextReportSeconds: next });
  if (previous && sequence <= previous.sequence) {
    if (sequence === previous.sequence && stateHash !== previous.state_hash) throw new ApiError("IDEMPOTENCY_CONFLICT", "Sequence payload changed", 409);
    return response(false);
  }
  const day = new Date(now * 1000).toISOString().slice(0, 10);
  if (previous?.report_day === day && previous.day_count >= 8) throw new ApiError("RATE_LIMITED", "Installation daily reporting limit", 429);
  if (previous && previous.state_hash === stateHash && previous.refresh_id === current.refresh_id && now - previous.last_seen < DAY) return response(false);
  const statements = [env.DB.prepare(`INSERT INTO version_inventory_installations
    (install_key,platform,version_code,version_name,image_sha256,sequence,state_hash,first_seen,last_seen,refresh_id,report_day,day_count)
    VALUES (?,'android',?,?,?,?,?,?,?,?,?,1) ON CONFLICT(install_key) DO UPDATE SET
    version_code=excluded.version_code,version_name=excluded.version_name,image_sha256=excluded.image_sha256,
    sequence=excluded.sequence,state_hash=excluded.state_hash,last_seen=excluded.last_seen,refresh_id=excluded.refresh_id,
    report_day=excluded.report_day,day_count=CASE WHEN report_day=excluded.report_day THEN day_count+1 ELSE 1 END
    WHERE version_inventory_installations.sequence < excluded.sequence`)
    .bind(key, versionCode, versionName, imageSha, sequence, stateHash, now, now, current.refresh_id, day)];
  for (const d of devices) statements.push(env.DB.prepare(`INSERT INTO version_inventory_devices
    (install_key,device_key,identity_scope,device_model,version_code,image_sha256,hardware_revision,layout_id,observation_id,observed_at)
    SELECT ?,?,'installation',?,?,?,?,?,?,? WHERE EXISTS
    (SELECT 1 FROM version_inventory_installations WHERE install_key=? AND sequence=? AND state_hash=?)
    ON CONFLICT(install_key,device_key) DO UPDATE SET version_code=excluded.version_code,image_sha256=excluded.image_sha256,
    hardware_revision=excluded.hardware_revision,layout_id=excluded.layout_id,
    observed_at=CASE WHEN observation_id=excluded.observation_id THEN observed_at ELSE excluded.observed_at END,
    observation_id=excluded.observation_id`)
    .bind(key, d.deviceKey, d.deviceModel, d.versionCode, d.imageSha256, d.hardwareRevision, d.layoutId,
      d.observationId, now - d.ageSeconds, key, sequence, stateHash));
  // The current report is a bounded snapshot, not an ever-growing per-installation log.
  statements.push(env.DB.prepare(`DELETE FROM version_inventory_devices WHERE install_key=?
    ${devices.length ? `AND device_key NOT IN (${devices.map(() => "?").join(",")})` : ""}
    AND EXISTS (SELECT 1 FROM version_inventory_installations WHERE install_key=? AND sequence=? AND state_hash=?)`)
    .bind(key, ...devices.map(d => d.deviceKey), key, sequence, stateHash));
  try {
    const written = await env.DB.batch(statements);
    return response(written[0].meta.changes > 0);
  } catch (error) {
    if (String(error).includes("inventory daily budget") || String(error).includes("day_count")) {
      throw new ApiError("RATE_LIMITED", "Inventory budget exhausted; upgrades remain independent", 429);
    }
    throw error;
  }
}

export async function inventorySummary(env: InventoryEnv, now = Math.floor(Date.now() / 1000)): Promise<Response> {
  enabled(env);
  const current = await control(env);
  const app = await env.DB.prepare(`SELECT version_code AS versionCode,version_name AS versionName,image_sha256 AS imageSha256,
    SUM(last_seen>=?) AS active7,SUM(last_seen>=?) AS active30,COUNT(*) AS active90,MAX(last_seen) AS lastSeen
    FROM version_inventory_installations WHERE last_seen>=? GROUP BY version_code,version_name,image_sha256
    ORDER BY active30 DESC,version_code DESC LIMIT 500`).bind(now-7*DAY, now-30*DAY, now-RETENTION).all();
  const firmware = await env.DB.prepare(`SELECT device_model AS deviceModel,version_code AS versionCode,image_sha256 AS imageSha256,
    hardware_revision AS hardwareRevision,layout_id AS layoutId,SUM(observed_at>=?) AS active7,SUM(observed_at>=?) AS active30,
    COUNT(*) AS active90,MAX(observed_at) AS lastSeen FROM version_inventory_devices WHERE observed_at>=?
    GROUP BY device_model,version_code,image_sha256,hardware_revision,layout_id ORDER BY active30 DESC,version_code DESC LIMIT 500`)
    .bind(now-7*DAY, now-30*DAY, now-RETENTION).all();
  const responses = await env.DB.prepare("SELECT COUNT(*) AS n FROM version_inventory_installations WHERE refresh_id=? AND last_seen>=?")
    .bind(current.refresh_id, current.requested_at).first<{ n: number }>();
  return json({ ok: true, generatedAt: now, app: app.results, firmware: firmware.results,
    refreshId: current.refresh_id, refreshRequestedAt: current.requested_at, refreshResponses: current.requested_at ? responses?.n ?? 0 : 0,
    coverage: "reporting-installations-only", firmwareIdentityScope: "installation", uniqueDeviceCount: null,
    dailyReportLimit: current.daily_limit, retentionDays: 90 });
}

export async function refreshInventory(env: InventoryEnv, actor: string, body: Record<string, unknown>, now = Math.floor(Date.now() / 1000)): Promise<Response> {
  enabled(env);
  const id = body.requestId;
  if (typeof id !== "string" || !UUID.test(id)) throw invalidParameter("A UUID requestId is required");
  const current = await control(env);
  if (current.refresh_id === id) return json({ ok: true, refreshId: id, requestedAt: current.requested_at, idempotent: true });
  if (current.requested_at && now - current.requested_at < 900) throw new ApiError("RATE_LIMITED", "A refresh was requested within 15 minutes", 429);
  const result = await env.DB.prepare("UPDATE version_inventory_control SET refresh_id=?,requested_at=?,requested_by=? WHERE id=1 AND refresh_id=?")
    .bind(id, now, actor, current.refresh_id).run();
  if (!result.meta.changes) throw new ApiError("CAS_CONFLICT", "Inventory refresh changed; reload", 409);
  return json({ ok: true, refreshId: id, requestedAt: now, idempotent: false });
}

export async function cleanupInventory(env: InventoryEnv, now = Math.floor(Date.now() / 1000)): Promise<void> {
  if (env.VERSION_INVENTORY_ENABLED !== "true") return;
  await env.DB.batch([
    env.DB.prepare("DELETE FROM version_inventory_devices WHERE (install_key,device_key) IN (SELECT install_key,device_key FROM version_inventory_devices WHERE observed_at<? LIMIT 400)").bind(now-RETENTION),
    env.DB.prepare("DELETE FROM version_inventory_installations WHERE install_key IN (SELECT install_key FROM version_inventory_installations WHERE last_seen<? LIMIT 100)").bind(now-RETENTION),
    env.DB.prepare("DELETE FROM version_inventory_budget WHERE day < ?").bind(new Date((now-7*DAY)*1000).toISOString().slice(0,10))
  ]);
}
