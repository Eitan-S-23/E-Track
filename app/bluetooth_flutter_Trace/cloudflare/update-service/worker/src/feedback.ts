import { ApiError, invalidParameter } from "./errors";
import { json } from "./http";
import { boundedJson, sha256Text } from "./version_inventory";
import type { WorkerEnv } from "./types";

type FeedbackEnv = Pick<WorkerEnv, "DB" | "APP_ID">;
type PublicFeedbackEnv = FeedbackEnv & Pick<WorkerEnv, "RATE_LIMITER">;
interface BatchRow { install_key: string; payload_hash: string; report_day: number; received_at: number }
interface Message { id: string; body: string; createdAt: number; platform: string; versionName: string; versionCode: number }
const UUID = /^[0-9a-f]{8}-[0-9a-f]{4}-4[0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$/;
const DAY = 86400;
const OFFSET = 8 * 3600;
const STATUSES = ["pending", "processing", "resolved", "declined"];
const MESSAGE_COLUMNS = "id,client_id AS clientId,body,client_created_at AS clientCreatedAt,received_at AS receivedAt,platform,version_name AS versionName,version_code AS versionCode,status,note,revision,updated_at AS updatedAt,updated_by AS updatedBy";

function noCache(body: unknown, status = 200, headers: Record<string, string> = {}) {
  return json(body, status, { "Cache-Control": "no-store", ...headers });
}
function dayOf(now: number) { return Math.floor((now + OFFSET) / DAY); }
function nextDay(day: number) { return (day + 1) * DAY - OFFSET; }
function limited(now: number, retryAt: number, scope: string) {
  return noCache({ ok: false, errorCode: "RATE_LIMITED", scope, retryAt, serverTime: now }, 429,
    { "Retry-After": String(Math.max(1, retryAt - now)) });
}
function ipOf(request: Request): string {
  const ip = request.headers.get("CF-Connecting-IP") ?? "";
  if (/^(0|[1-9][0-9]{0,2})(\.(0|[1-9][0-9]{0,2})){3}$/.test(ip) && ip.split(".").every(part => Number(part) <= 255)) return ip;
  if (ip.includes(":") && /^[0-9a-fA-F:.]+$/.test(ip)) {
    try { return new URL(`http://[${ip}]/`).hostname.toLowerCase(); } catch { /* Reject malformed IPv6. */ }
  }
  throw invalidParameter("Trusted client IP required");
}
function message(value: unknown): Message {
  if (!value || typeof value !== "object" || Array.isArray(value)) throw invalidParameter("Invalid feedback");
  const item = value as Record<string, unknown>;
  if (typeof item.id !== "string" || !UUID.test(item.id)) throw invalidParameter("Message UUID required");
  if (typeof item.body !== "string" || !item.body.trim() || item.body.length > 2000 || item.body.includes("\0")) {
    throw invalidParameter("Feedback must contain 1-2000 characters");
  }
  if (typeof item.createdAt !== "number" || !Number.isSafeInteger(item.createdAt) || item.createdAt < 0 || item.createdAt > 4102444800) {
    throw invalidParameter("Invalid client time");
  }
  if (typeof item.platform !== "string" || !["android", "windows", "ios"].includes(item.platform) ||
      typeof item.versionName !== "string" || !/^[\w.+-]{1,64}$/.test(item.versionName) ||
      typeof item.versionCode !== "number" || !Number.isSafeInteger(item.versionCode) || item.versionCode < 0 || item.versionCode > 2100000000) {
    throw invalidParameter("Invalid App identity");
  }
  return { id: item.id, body: item.body.trim(), createdAt: item.createdAt, platform: item.platform,
    versionName: item.versionName, versionCode: item.versionCode };
}

export async function submitFeedback(request: Request, env: PublicFeedbackEnv,
  now = Math.floor(Date.now() / 1000)): Promise<Response> {
  const ip = ipOf(request);
  const ingress = await sha256Text(`feedback-ingress:${ip}`);
  const rate = await env.RATE_LIMITER.getByName(`feedback:${ingress.slice(0, 2)}`).check(ingress, 20, 60);
  if (!rate.allowed) return limited(now, now + Math.max(1, rate.retryAfter), "requests");
  const token = request.headers.get('X-Install-Token') ?? request.headers.get("Authorization")?.match(/^Bearer ([0-9a-f]{64})$/)?.[1];
  if (!token) throw new ApiError("TOKEN_INVALID", "Installation feedback token required", 401);
  const body = await boundedJson(request, 96 * 1024);
  if (body.appId !== env.APP_ID || typeof body.batchId !== "string" || !UUID.test(body.batchId) ||
      !Array.isArray(body.messages) || !body.messages.length || body.messages.length > 10) {
    throw invalidParameter("A batch UUID and 1-10 messages are required");
  }
  const messages = body.messages.map(message);
  if (new Set(messages.map(item => item.id)).size !== messages.length) throw invalidParameter("Duplicate message IDs");
  const installKey = await sha256Text(token);
  const hash = await sha256Text(JSON.stringify(messages));
  const batchId = body.batchId;
  const readBatch = () => env.DB.prepare("SELECT install_key,payload_hash,report_day,received_at FROM feedback_batches WHERE id=?")
    .bind(batchId).first<BatchRow>();
  const acknowledge = (batch: BatchRow, replayed: boolean) => {
    if (batch.install_key !== installKey || batch.payload_hash !== hash) {
      throw new ApiError("IDEMPOTENCY_CONFLICT", "Batch identity or payload changed", 409);
    }
    return noCache({ ok: true, batchId, acceptedIds: messages.map(item => item.id), replayed,
      receivedAt: batch.received_at, nextAllowedAt: nextDay(batch.report_day), serverTime: now }, replayed ? 200 : 201);
  };
  const previous = await readBatch();
  if (previous) return acknowledge(previous, true);
  const day = dayOf(now);
  const salt = await env.DB.prepare("SELECT ip_salt FROM feedback_settings WHERE id=1").first<string>("ip_salt");
  if (!salt) throw new ApiError("BACKEND_UNAVAILABLE", "Feedback storage unavailable", 503);
  const signingKey = await crypto.subtle.importKey("raw", new TextEncoder().encode(salt),
    { name: "HMAC", hash: "SHA-256" }, false, ["sign"]);
  const signature = await crypto.subtle.sign("HMAC", signingKey, new TextEncoder().encode(`${day}:${ip}`));
  const ipKey = Array.from(new Uint8Array(signature), x => x.toString(16).padStart(2, "0")).join("");
  const statements = [env.DB.prepare("INSERT INTO feedback_batches(id,install_key,payload_hash,report_day,ip_key,received_at) VALUES(?,?,?,?,?,?)")
    .bind(batchId, installKey, hash, day, ipKey, now)];
  for (const item of messages) statements.push(env.DB.prepare(`INSERT INTO feedback_messages
    (client_id,install_key,batch_id,body,client_created_at,received_at,platform,version_name,version_code,updated_at)
    VALUES(?,?,?,?,?,?,?,?,?,?)`).bind(item.id, installKey, batchId, item.body, item.createdAt, now,
      item.platform, item.versionName, item.versionCode, now));
  try {
    await env.DB.batch(statements);
  } catch (error) {
    // A concurrent replay can lose the insert race; it must not spend another day.
    const stored = await readBatch();
    if (stored) return acknowledge(stored, true);
    const detail = String(error);
    if (detail.includes("feedback IP daily budget")) return limited(now, nextDay(day), "ip");
    if (detail.includes("feedback_batches.install_key") || detail.includes("feedback_batches.report_day")) {
      return limited(now, nextDay(day), "installation");
    }
    if (detail.includes("feedback_messages.install_key") || detail.includes("feedback_messages.client_id")) {
      throw new ApiError("IDEMPOTENCY_CONFLICT", "A message was already submitted in another batch", 409);
    }
    throw error;
  }
  return acknowledge({ install_key: installKey, payload_hash: hash, report_day: day, received_at: now }, false);
}

export async function listFeedback(env: FeedbackEnv, url: URL): Promise<Response> {
  const status = url.searchParams.get("status") ?? "all";
  const before = url.searchParams.get("before");
  const q = (url.searchParams.get("q") ?? "").trim();
  if (!["all", ...STATUSES].includes(status) || q.length > 120 ||
      (before !== null && (!/^[1-9][0-9]{0,14}$/.test(before) || !Number.isSafeInteger(Number(before))))) {
    throw invalidParameter("Invalid feedback filter or cursor");
  }
  const result = await env.DB.prepare(`SELECT ${MESSAGE_COLUMNS} FROM feedback_messages
    WHERE (?='all' OR status=?) AND (? IS NULL OR id<?) AND (?='' OR instr(lower(body),lower(?))>0)
    ORDER BY id DESC LIMIT 21`).bind(status, status, before, before, q, q).all<Record<string, unknown>>();
  const rows = result.results.slice(0, 20);
  return noCache({ ok: true, feedback: rows, nextCursor: result.results.length > 20 ? rows.at(-1)!.id : null });
}

export async function feedbackDetail(env: FeedbackEnv, id: number): Promise<Response> {
  const item = await env.DB.prepare(`SELECT ${MESSAGE_COLUMNS} FROM feedback_messages WHERE id=?`).bind(id).first();
  if (!item) throw new ApiError("RELEASE_NOT_FOUND", "Feedback not found", 404);
  const history = await env.DB.prepare("SELECT revision,status,note,actor,created_at AS createdAt FROM feedback_events WHERE feedback_id=? ORDER BY revision DESC LIMIT 30")
    .bind(id).all();
  return noCache({ ok: true, feedback: item, history: history.results });
}

export async function updateFeedback(env: FeedbackEnv, id: number, actor: string, body: Record<string, unknown>,
  now = Math.floor(Date.now() / 1000)): Promise<Response> {
  if (typeof body.status !== "string" || !STATUSES.includes(body.status) || typeof body.note !== "string" ||
      body.note.length > 2000 || body.note.includes("\0") || typeof body.revision !== "number" ||
      !Number.isSafeInteger(body.revision) || body.revision < 1) throw invalidParameter("Invalid feedback update");
  const result = await env.DB.prepare(`UPDATE feedback_messages SET status=?,note=?,revision=revision+1,updated_at=?,updated_by=?
    WHERE id=? AND revision=?`).bind(body.status, body.note.trim(), now, actor, id, body.revision).run();
  if (!result.meta.changes) throw new ApiError("CAS_CONFLICT", "Feedback changed; reload before saving", 409);
  return feedbackDetail(env, id);
}

export async function cleanupFeedback(env: FeedbackEnv, now = Math.floor(Date.now() / 1000)): Promise<void> {
  // Keep small idempotency receipts after expiring message content, so retries stay harmless.
  await env.DB.prepare("DELETE FROM feedback_messages WHERE id IN (SELECT id FROM feedback_messages WHERE received_at<? LIMIT 100)")
    .bind(now - 90 * DAY).run();
}
