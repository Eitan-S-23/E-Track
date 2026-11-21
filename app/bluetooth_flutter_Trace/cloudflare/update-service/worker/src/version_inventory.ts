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
const QUALITY_COUNTERS = ["connectionAttempts", "connectionSucceeded", "connectionFailed", "checksSucceeded", "checksFailed", "updatesSucceeded", "updatesFailed"] as const;

function reportAddress(value: string | null): string | null {
  if (!value || value.length > 45) return null;
  if (value.includes(":")) {
    if (!/^[0-9a-f:.]+$/i.test(value)) return null;
    try { return new URL(`http://[${value}]/`).hostname.slice(1, -1); }
    catch { return null; }
  }
  const octets = value.split(".");
  return octets.length === 4 && octets.every(part => /^(0|[1-9]\d{0,2})$/.test(part) && Number(part) <= 255) ? value : null;
}

function textMetadata(value: unknown, name: string, maximum: number): string | null {
  if (value === undefined || value === null) return null;
  if (typeof value !== "string" || !value.trim() || value.length > maximum || /[\u0000-\u001f\u007f]/.test(value)) throw invalidParameter(`Invalid ${name}`);
  return value.trim();
}
function phoneMetadata(value: unknown): { brand: string | null; model: string | null; osVersion: string | null } {
  if (value === undefined || value === null) return { brand: null, model: null, osVersion: null };
  if (!value || typeof value !== "object" || Array.isArray(value)) throw invalidParameter("Invalid phone metadata");
  const phone = value as Record<string, unknown>;
  if (Object.keys(phone).some(key => !["brand", "model", "osVersion"].includes(key))) throw invalidParameter("Unknown phone metadata field");
  return { brand: textMetadata(phone.brand, "phone brand", 80), model: textMetadata(phone.model, "phone model", 80),
    osVersion: textMetadata(phone.osVersion, "OS version", 64) };
}
function qualityMetadata(value: unknown): Record<string, string | number> | null {
  if (value === undefined || value === null) return null;
  if (!value || typeof value !== "object" || Array.isArray(value)) throw invalidParameter("Invalid quality summary");
  const quality = value as Record<string, unknown>;
  const date = typeof quality.day === "string" ? new Date(`${quality.day}T00:00:00Z`) : new Date(NaN);
  if (quality.scope !== "companion-day" || typeof quality.day !== "string" || !/^\d{4}-\d{2}-\d{2}$/.test(quality.day) ||
      !Number.isFinite(date.getTime()) || date.toISOString().slice(0, 10) !== quality.day ||
      Object.keys(quality).some(key => !["scope", "day", ...QUALITY_COUNTERS].includes(key))) throw invalidParameter("Invalid quality scope");
  const result: Record<string, string | number> = { scope: "companion-day", day: quality.day };
  for (const key of QUALITY_COUNTERS) result[key] = integer(quality[key] ?? 0, key, 100000);
  return result;
}

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
  const token = request.headers.get('X-Install-Token') ?? request.headers.get("Authorization")?.match(/^Bearer ([0-9a-f]{64})$/)?.[1];
  if (!token) throw new ApiError("TOKEN_INVALID", "Installation reporting token required", 401);
  const key = await sha256Text(token);
  const body = await boundedJson(request);
  if (Object.keys(body).some(key => !["appId", "platform", "sequence", "versionCode", "versionName", "imageSha256", "devices", "phone", "quality"].includes(key))) {
    throw invalidParameter("Unknown inventory field");
  }
  if (body.appId !== env.APP_ID || body.platform !== "android") throw invalidParameter("Unsupported reporting scope");
  const sequence = integer(body.sequence, "sequence", Number.MAX_SAFE_INTEGER);
  if (!sequence) throw invalidParameter("Positive sequence required");
  const versionCode = integer(body.versionCode, "versionCode", 2100000000);
  const versionName = body.versionName;
  if (typeof versionName !== "string" || !/^[\w.+-]{1,64}$/.test(versionName)) throw invalidParameter("Invalid versionName");
  const imageSha = digest(body.imageSha256, "imageSha256");
  const phone = phoneMetadata(body.phone), quality = qualityMetadata(body.quality);
  const reportIp = reportAddress(request.headers.get("CF-Connecting-IP"));
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
  const identity: unknown[] = [versionCode, versionName, imageSha,
    devices.map(({ ageSeconds: _age, ...deviceIdentity }) => deviceIdentity).sort((a, b) => a.deviceKey.localeCompare(b.deviceKey))];
  // Preserve the pre-migration retry fingerprint for legacy reports.
  if (body.phone !== undefined || body.quality !== undefined) identity.push(phone, quality);
  const stateHash = await sha256Text(JSON.stringify(identity));
  const current = await control(env);
  const readInstallation = () => env.DB.prepare("SELECT sequence,state_hash,last_seen,report_day,day_count,refresh_id FROM version_inventory_installations WHERE install_key=?")
    .bind(key).first<Installation>();
  let previous = await readInstallation();
  const response = (accepted: boolean, next = DAY) => {
    const acknowledged = accepted || previous?.state_hash === stateHash;
    return json({ ok: true, accepted, acknowledged,
      reportedAt: accepted ? now : acknowledged ? previous!.last_seen : null,
      sequence: accepted ? sequence : previous?.sequence ?? sequence,
      refreshId: !accepted && acknowledged ? previous!.refresh_id : current.refresh_id,
      nextReportSeconds: next });
  };
  if (previous && sequence <= previous.sequence) {
    if (sequence === previous.sequence && stateHash !== previous.state_hash) throw new ApiError("IDEMPOTENCY_CONFLICT", "Sequence payload changed", 409);
    return response(false);
  }
  const day = new Date(now * 1000).toISOString().slice(0, 10);
  if (previous?.report_day === day && previous.day_count >= 8) throw new ApiError("RATE_LIMITED", "Installation daily reporting limit", 429);
  if (previous && previous.state_hash === stateHash && previous.refresh_id === current.refresh_id && now - previous.last_seen < DAY) return response(false);
  const statements = [env.DB.prepare(`INSERT INTO version_inventory_installations
    (install_key,platform,version_code,version_name,image_sha256,sequence,state_hash,first_seen,last_seen,refresh_id,report_day,day_count,
      phone_brand,phone_model,os_version,report_ip,quality_json)
    VALUES (?,'android',?,?,?,?,?,?,?,?,?,1,?,?,?,?,?) ON CONFLICT(install_key) DO UPDATE SET
    version_code=excluded.version_code,version_name=excluded.version_name,image_sha256=excluded.image_sha256,
    sequence=excluded.sequence,state_hash=excluded.state_hash,last_seen=excluded.last_seen,refresh_id=excluded.refresh_id,
    phone_brand=excluded.phone_brand,phone_model=excluded.phone_model,os_version=excluded.os_version,
    report_ip=excluded.report_ip,quality_json=excluded.quality_json,
    report_day=excluded.report_day,day_count=CASE WHEN report_day=excluded.report_day THEN day_count+1 ELSE 1 END
    WHERE version_inventory_installations.sequence < excluded.sequence`)
    .bind(key, versionCode, versionName, imageSha, sequence, stateHash, now, now, current.refresh_id, day,
      phone.brand, phone.model, phone.osVersion, reportIp, quality ? JSON.stringify(quality) : null)];
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
    // A newer sequence may win after the initial read. Acknowledge only stored state.
    if (!written[0].meta.changes) previous = await readInstallation();
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

/** Access-authenticated, read-only detail. Its window and complete version scope
 * match the aggregate row; IP is a network observation, never a person count. */
export async function inventoryDetails(env: InventoryEnv, url: URL, now = Math.floor(Date.now() / 1000)): Promise<Response> {
  enabled(env);
  const query = url.searchParams, kind = query.get("kind");
  const common = ["kind", "versionCode", "imageSha256", "windowDays", "limit", "cursor"];
  const fields = kind === "app" ? ["platform", "versionName"] : kind === "firmware" ? ["deviceModel", "hardwareRevision", "layoutId"] : [];
  if (!fields.length || [...query.keys()].some(key => ![...common, ...fields].includes(key) || query.getAll(key).length !== 1)) throw invalidParameter("Invalid inventory detail scope");
  function number(key: string, maximum: number, fallback?: number) {
    const value = query.get(key);
    if (value === null && fallback !== undefined) return fallback;
    if (value === null || !/^(0|[1-9][0-9]*)$/.test(value)) throw invalidParameter(`Invalid ${key}`);
    return integer(Number(value), key, maximum);
  }
  const versionCode = number("versionCode", kind === "app" ? 2100000000 : 4294967295);
  const imageSha256 = digest(query.get("imageSha256"), "imageSha256");
  const windowDays = number("windowDays", 90, 30), limit = number("limit", 50, 20);
  if (![7, 30, 90].includes(windowDays) || limit < 1) throw invalidParameter("Invalid detail window or limit");
  const scope: Record<string, string | number> = { kind: kind!, versionCode, imageSha256 };
  let from: string, where: string, seen: string, device: string;
  const bindings: Array<string | number> = [versionCode, imageSha256];
  if (kind === "app") {
    if (query.get("platform") !== "android" || !/^[\w.+-]{1,64}$/.test(query.get("versionName") ?? "")) throw invalidParameter("Unsupported App detail scope");
    scope.platform = "android"; scope.versionName = query.get("versionName")!;
    from = "version_inventory_installations i";
    where = "i.version_code=? AND i.image_sha256=? AND i.platform='android' AND i.version_name=? AND i.last_seen>=?";
    bindings.push(scope.versionName, now - windowDays * DAY);
    seen = "i.last_seen"; device = "''";
  } else {
    if (query.get("deviceModel") !== "e-track-at32f435") throw invalidParameter("Unsupported firmware detail scope");
    scope.deviceModel = "e-track-at32f435";
    scope.hardwareRevision = number("hardwareRevision", 65535); scope.layoutId = number("layoutId", 65535);
    from = "version_inventory_devices d JOIN version_inventory_installations i ON i.install_key=d.install_key";
    where = "d.version_code=? AND d.image_sha256=? AND d.device_model='e-track-at32f435' AND d.hardware_revision=? AND d.layout_id=? AND d.observed_at>=? AND i.last_seen>=?";
    bindings.push(scope.hardwareRevision, scope.layoutId, now - windowDays * DAY, now - RETENTION);
    seen = "d.observed_at"; device = "d.device_key";
  }
  let cursorWhere = "";
  const cursorValues: Array<string | number> = [];
  const cursor = query.get("cursor");
  if (cursor !== null) {
    const parts = cursor.split("|");
    if (parts.length !== 3 || !/^[0-9]{1,12}$/.test(parts[0]) || !HEX.test(parts[1]) ||
        (kind === "firmware" ? !HEX.test(parts[2]) : parts[2] !== "")) throw invalidParameter("Invalid detail cursor");
    const timestamp = Number(parts[0]);
    cursorWhere = ` AND (${seen},i.install_key,${device}) < (?,?,?)`;
    cursorValues.push(timestamp, parts[1], parts[2]);
  }
  const select = (sql: string) => env.DB.prepare(sql).bind(...bindings);
  const qualitySelect = `SELECT DISTINCT i.install_key,i.quality_json FROM ${from} WHERE ${where}`;
  const statements = [
    select(`SELECT COUNT(*) AS n,SUM(i.phone_model IS NULL) AS unknownModels,SUM(i.report_ip IS NULL) AS unknownIps FROM ${from} WHERE ${where}`),
    select(`SELECT i.phone_brand AS brand,i.phone_model AS model,COUNT(*) AS count FROM ${from} WHERE ${where} AND i.phone_model IS NOT NULL
      GROUP BY i.phone_brand,i.phone_model ORDER BY count DESC,model,brand LIMIT 5`),
    select(`SELECT i.report_ip AS ip,COUNT(*) AS count FROM ${from} WHERE ${where} AND i.report_ip IS NOT NULL GROUP BY i.report_ip ORDER BY count DESC,ip LIMIT 10`),
    select(`SELECT i.platform,i.version_code AS versionCode,i.version_name AS versionName,i.image_sha256 AS imageSha256,COUNT(*) AS count FROM ${from} WHERE ${where}
      GROUP BY i.platform,i.version_code,i.version_name,i.image_sha256 ORDER BY count DESC,versionCode DESC,imageSha256 LIMIT 50`),
    env.DB.prepare(`SELECT i.install_key AS installationKey,${device} AS deviceKey,${seen} AS observedAt,i.last_seen AS reportedAt,
      i.phone_brand AS brand,i.phone_model AS model,i.os_version AS osVersion,i.report_ip AS ip,i.quality_json AS quality,
      i.platform,i.version_code AS appVersionCode,i.version_name AS appVersionName,i.image_sha256 AS appImageSha256
      FROM ${from} WHERE ${where}${cursorWhere} ORDER BY ${seen} DESC,i.install_key DESC,${device} DESC LIMIT ?`).bind(...bindings, ...cursorValues, limit + 1),
    select(`SELECT COUNT(quality_json) AS samples,${QUALITY_COUNTERS.map(key => `COALESCE(SUM(json_extract(quality_json,'$.${key}')),0) AS ${key}`).join(",")}
      FROM (${qualitySelect})`)
  ];
  const result = await env.DB.batch<Record<string, unknown>>(statements);
  const totals = result[0].results[0] as { n: number; unknownModels: number | null; unknownIps: number | null };
  const total = totals.n;
  const withShare = (row: Record<string, unknown>) => ({ ...row, count: Number(row.count), share: total ? Number(row.count) / total : 0 });
  const models = result[1].results.map(withShare), ips = result[2].results.map(withShare), associatedApps = result[3].results.map(withShare);
  const records = result[4].results;
  const visible = records.slice(0, limit), last = visible.at(-1);
  const reports = visible.map(({ installationKey, deviceKey, quality, ...row }) => ({ ...row,
    installationTag: String(installationKey).slice(0, 12), deviceTag: deviceKey ? String(deviceKey).slice(0, 12) : null,
    quality: typeof quality === "string" ? JSON.parse(quality) : null }));
  return json({ ok: true, generatedAt: now, scope, windowDays, sampleCount: total,
    coverage: "reporting-installations-only", firmwareIdentityScope: "installation", uniqueDeviceCount: null,
    models, unknownModels: totals.unknownModels ?? 0,
    otherModels: total - (totals.unknownModels ?? 0) - models.reduce((sum, row) => sum + Number(row.count), 0),
    ips, unknownIps: totals.unknownIps ?? 0,
    otherIps: total - (totals.unknownIps ?? 0) - ips.reduce((sum, row) => sum + Number(row.count), 0),
    associatedApps: kind === "firmware" ? associatedApps : [],
    otherAssociatedApps: kind === "firmware" ? total - associatedApps.reduce((sum, row) => sum + Number(row.count), 0) : 0,
    quality: { ...result[5].results[0], scope: "latest-reported-companion-days" }, reports,
    nextCursor: records.length > limit && last ? `${last.observedAt}|${last.installationKey}|${last.deviceKey}` : null });
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
