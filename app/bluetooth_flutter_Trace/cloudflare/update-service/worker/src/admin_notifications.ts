import { ApiError, invalidParameter } from "./errors";
import { json } from "./http";
import { sha256Text } from "./version_inventory";
import { deltaJobViews, type DeltaJob } from "./delta_jobs";
import type { WorkerEnv } from "./types";

type NotificationEnv = Pick<WorkerEnv, "DB" | "ADMIN_PUSH_PUBLIC_KEY" | "ADMIN_PUSH_PRIVATE_JWK" | "ADMIN_PUSH_SUBJECT" | "DELTA_GITHUB_TOKEN"> & { APP_ID?: string };
const nowSeconds = () => Math.floor(Date.now() / 1000);
const publicKeyPattern = /^[A-Za-z0-9_-]{87}$/;

export function pushEndpoint(value: unknown): string {
  if (typeof value !== "string" || value.length > 2048) throw invalidParameter("Invalid push endpoint");
  let url: URL;
  try { url = new URL(value); } catch { throw invalidParameter("Invalid push endpoint"); }
  const allowed = (url.hostname === "fcm.googleapis.com" && url.pathname.startsWith("/fcm/send/")) ||
    (url.hostname === "updates.push.services.mozilla.com" && url.pathname.startsWith("/wpush/")) ||
    (/^[a-z0-9-]+\.notify\.windows\.com$/.test(url.hostname) && url.pathname === "/w/") ||
    (url.hostname === "web.push.apple.com" && url.pathname.startsWith("/"));
  if (!allowed || url.protocol !== "https:" || url.port || url.username || url.password || url.hash || url.pathname === "/") {
    throw invalidParameter("Unsupported push service; in-app notifications remain available");
  }
  return url.href;
}

export async function deltaActivity(env: NotificationEnv, actor: string): Promise<Response> {
  // Non-subscribers also retain arrivals while away. Materialization is bounded;
  // only Access-authorized readers reach this function, and no old releases seed it.
  if (env.APP_ID) await env.DB.prepare(`INSERT OR IGNORE INTO admin_notifications(candidate_id,actor,status,created_at)
    SELECT e.id,?,'ready',e.created_at FROM admin_candidate_events e WHERE e.app_id=?
    AND NOT EXISTS(SELECT 1 FROM admin_notifications n WHERE n.actor=? AND n.candidate_id=e.id)
    ORDER BY e.id LIMIT 100`).bind(actor,env.APP_ID,actor).run();
  const [jobs, notifications, unread, subscriptions] = await env.DB.batch<DeltaJob | Record<string, unknown>>([
    env.DB.prepare("SELECT * FROM delta_jobs WHERE actor=? ORDER BY CASE WHEN status IN ('ready','failed') THEN 1 ELSE 0 END,updated_at DESC,id LIMIT 100").bind(actor),
    env.DB.prepare(`SELECT n.id,n.job_id AS jobId,n.attempt,n.status,n.error_code AS errorCode,n.created_at AS createdAt,
      CASE WHEN n.candidate_id IS NULL THEN 'delta' ELSE 'candidate' END AS type,
      COALESCE(e.kind,j.kind) AS kind,COALESCE(e.release_id,j.target_release_id) AS targetReleaseId,
      j.base_version_code AS baseVersionCode,COALESCE(e.version_code,j.target_version_code) AS targetVersionCode,
      e.version_name AS versionName,e.device_model AS deviceModel,
      CASE WHEN n.id>COALESCE(r.through_id,0) AND n.read_at IS NULL THEN 1 ELSE 0 END AS unread
      FROM admin_notifications n LEFT JOIN delta_jobs j ON j.id=n.job_id
      LEFT JOIN admin_candidate_events e ON e.id=n.candidate_id
      LEFT JOIN admin_notification_reads r ON r.actor=n.actor WHERE n.actor=? ORDER BY n.id DESC LIMIT 30`).bind(actor),
    env.DB.prepare(`SELECT COUNT(*) AS count FROM admin_notifications WHERE actor=? AND read_at IS NULL AND id>
      COALESCE((SELECT through_id FROM admin_notification_reads WHERE actor=?),0)`).bind(actor,actor),
    env.DB.prepare("SELECT id,expires_at AS expiresAt FROM admin_push_subscriptions WHERE actor=? AND expires_at>?").bind(actor,nowSeconds())
  ]);
  return json({ ok: true, actor, jobs: await deltaJobViews(env, jobs.results as DeltaJob[]), notifications: notifications.results,
    unreadCount: (unread.results[0] as { count: number }).count,
    pushSubscriptions: subscriptions.results,
    pushPublicKey: publicKeyPattern.test(env.ADMIN_PUSH_PUBLIC_KEY ?? "") ? env.ADMIN_PUSH_PUBLIC_KEY : null,
    generatedAt: nowSeconds(), scope: "own-jobs", jobsLimit: 100 });
}

export async function readNotifications(env: NotificationEnv, actor: string, body: Record<string, unknown>): Promise<Response> {
  if ("ids" in body) {
    const ids = body.ids;
    if ("throughId" in body || !Array.isArray(ids) || !ids.length || ids.length > 30 ||
      ids.some(id => !Number.isSafeInteger(id) || id <= 0) || new Set(ids).size !== ids.length) {
      throw invalidParameter("Expected 1 to 30 distinct notification IDs");
    }
    // Viewing one result must not consume older, unseen results from this actor.
    const read = await env.DB.prepare(`UPDATE admin_notifications SET read_at=COALESCE(read_at,?)
      WHERE actor=? AND id IN (${ids.map(()=>"?").join(",")}) RETURNING id`)
      .bind(nowSeconds(),actor,...ids).all<{id:number}>();
    return json({ok:true,readIds:read.results.map(row=>row.id)});
  }
  const through = body.throughId;
  if (!Number.isSafeInteger(through) || Number(through) < 0) throw invalidParameter("Invalid notification cursor");
  await env.DB.prepare(`INSERT INTO admin_notification_reads(actor,through_id)
    VALUES (?,MIN(?,COALESCE((SELECT MAX(id) FROM admin_notifications WHERE actor=?),0)))
    ON CONFLICT(actor) DO UPDATE SET through_id=MAX(through_id,excluded.through_id)`)
    .bind(actor,through,actor).run();
  const cursor = await env.DB.prepare("SELECT through_id FROM admin_notification_reads WHERE actor=?")
    .bind(actor).first<{through_id:number}>();
  return json({ ok: true, throughId: cursor?.through_id ?? 0 });
}

export async function subscribeNotifications(env: NotificationEnv, actor: string, body: Record<string, unknown>): Promise<Response> {
  if (!publicKeyPattern.test(env.ADMIN_PUSH_PUBLIC_KEY ?? "")) throw new ApiError("BACKEND_UNAVAILABLE", "Push is not configured", 503);
  const endpoint = pushEndpoint(body.endpoint);
  if (body.applicationServerKey !== env.ADMIN_PUSH_PUBLIC_KEY) throw invalidParameter("Push key changed; resubscribe");
  const id = await sha256Text(endpoint), now = nowSeconds();
  const current = await env.DB.prepare("SELECT actor FROM admin_push_subscriptions WHERE id=?").bind(id).first<{ actor: string }>();
  if (current && current.actor !== actor) throw new ApiError("RELEASE_CONFLICT", "This browser subscription belongs to a different account", 409);
  try {
    const result = await env.DB.prepare(`INSERT INTO admin_push_subscriptions(id,actor,endpoint,created_at,expires_at) VALUES (?,?,?,?,?)
      ON CONFLICT(id) DO UPDATE SET expires_at=excluded.expires_at WHERE actor=excluded.actor`)
      .bind(id,actor,endpoint,now,now + 30 * 86400).run();
    if (!result.meta.changes) throw new ApiError("RELEASE_CONFLICT", "Browser subscription ownership changed", 409);
  } catch (error) {
    if (String(error).includes("push subscription limit")) throw new ApiError("RATE_LIMITED", "At most five active browsers per account", 429);
    throw error;
  }
  return json({ ok: true, id, expiresAt: now + 30 * 86400 });
}

export async function unsubscribeNotifications(env: NotificationEnv, actor: string, body: Record<string, unknown>): Promise<Response> {
  if (typeof body.id !== "string" || !/^[a-f0-9]{64}$/.test(body.id)) throw invalidParameter("Invalid subscription ID");
  await env.DB.prepare("DELETE FROM admin_push_subscriptions WHERE id=? AND actor=?").bind(body.id,actor).run();
  return json({ ok: true });
}

function base64url(bytes: Uint8Array): string {
  return btoa(String.fromCharCode(...bytes)).replace(/\+/g,"-").replace(/\//g,"_").replace(/=+$/,"");
}

export async function vapidAuthorization(env: NotificationEnv, endpoint: string): Promise<string> {
  const publicKey = env.ADMIN_PUSH_PUBLIC_KEY ?? "";
  const subject = env.ADMIN_PUSH_SUBJECT ?? "";
  if (!publicKeyPattern.test(publicKey) || !/^(https:\/\/|mailto:)/.test(subject)) throw new Error("Push configuration unavailable");
  const jwk = JSON.parse(env.ADMIN_PUSH_PRIVATE_JWK ?? "null") as JsonWebKey | null;
  if (!jwk || jwk.kty !== "EC" || jwk.crv !== "P-256" || !jwk.d || !jwk.x || !jwk.y ||
    base64url(Uint8Array.from(atob(publicKey.replace(/-/g,"+").replace(/_/g,"/") + "="),c=>c.charCodeAt(0))) !== publicKey) {
    throw new Error("Invalid push signing configuration");
  }
  const decode = (value: string) => Uint8Array.from(atob(value.replace(/-/g,"+").replace(/_/g,"/") + "="), c=>c.charCodeAt(0));
  if (base64url(new Uint8Array([4,...decode(jwk.x),...decode(jwk.y)])) !== publicKey) throw new Error("Push key mismatch");
  const key = await crypto.subtle.importKey("jwk",jwk,{name:"ECDSA",namedCurve:"P-256"},false,["sign"]);
  const encode = (value: unknown) => base64url(new TextEncoder().encode(JSON.stringify(value)));
  const unsigned = `${encode({typ:"JWT",alg:"ES256"})}.${encode({aud:new URL(pushEndpoint(endpoint)).origin,exp:nowSeconds()+3600,sub:subject})}`;
  const signature = await crypto.subtle.sign({name:"ECDSA",hash:"SHA-256"},key,new TextEncoder().encode(unsigned));
  return `vapid t=${unsigned}.${base64url(new Uint8Array(signature))}, k=${publicKey}`;
}

// Payloadless RFC 8030/8292 pushes only wake the service worker. Protected data is
// fetched with its Access session, never sent to a browser-vendor push service.
export async function deliverNotifications(env: NotificationEnv, fetcher = fetch): Promise<void> {
  if (!env.ADMIN_PUSH_PRIVATE_JWK || !env.ADMIN_PUSH_PUBLIC_KEY) return;
  const now = nowSeconds();
  await env.DB.prepare("UPDATE admin_notification_deliveries SET status='failed' WHERE status='pending' AND attempts>=5 AND next_at<=?").bind(now).run();
  const due = await env.DB.prepare(`SELECT d.event_id,d.subscription_id,s.endpoint FROM admin_notification_deliveries d
    JOIN admin_push_subscriptions s ON s.id=d.subscription_id
    WHERE d.status='pending' AND d.next_at<=? AND d.attempts<5 AND s.expires_at>? ORDER BY d.next_at LIMIT 3`)
    .bind(now,now).all<{event_id:number;subscription_id:string;endpoint:string}>();
  for (const row of due.results) {
    const lease = crypto.randomUUID();
    const claimed = await env.DB.prepare(`UPDATE admin_notification_deliveries SET lease=?,next_at=?,attempts=attempts+1
      WHERE event_id=? AND subscription_id=? AND status='pending' AND next_at<=? AND attempts<5`)
      .bind(lease,now+300,row.event_id,row.subscription_id,now).run();
    if (!claimed.meta.changes) continue;
    try {
      const response = await fetcher(pushEndpoint(row.endpoint), { method: "POST", redirect: "manual",
        headers: { Authorization: await vapidAuthorization(env,row.endpoint), TTL: "86400", Urgency: "normal", "Content-Length": "0" },
        signal: AbortSignal.timeout(6000) });
      await response.body?.cancel();
      if (response.status === 404 || response.status === 410) {
        await env.DB.prepare("DELETE FROM admin_push_subscriptions WHERE id=?").bind(row.subscription_id).run();
      } else {
        const status = response.ok ? "sent" : response.status === 429 || response.status >= 500 ? "pending" : "failed";
        await env.DB.prepare("UPDATE admin_notification_deliveries SET status=CASE WHEN ?='pending' AND attempts>=5 THEN 'failed' ELSE ? END WHERE event_id=? AND subscription_id=? AND lease=?")
          .bind(status,status,row.event_id,row.subscription_id,lease).run();
      }
    } catch {
      await env.DB.prepare("UPDATE admin_notification_deliveries SET status=CASE WHEN attempts>=5 THEN 'failed' ELSE 'pending' END WHERE event_id=? AND subscription_id=? AND lease=?")
        .bind(row.event_id,row.subscription_id,lease).run();
    }
  }
  await env.DB.prepare("DELETE FROM admin_push_subscriptions WHERE expires_at<=?").bind(now).run();
}

export function candidateArrival(env: Pick<WorkerEnv, "DB" | "APP_ID">, input: {
  appId: string; kind: "android" | "windows" | "firmware"; releaseId: string;
  versionName: string; versionCode: number; deviceModel?: string; commitSha: string; runId: string;
}): D1PreparedStatement {
  // Must be part of the registration batch, after asset verification. A failed
  // asset insert or audit write rolls the event and its outbox back as well.
  return env.DB.prepare(`INSERT OR IGNORE INTO admin_candidate_events
    (app_id,kind,release_id,version_name,version_code,device_model,commit_sha,run_id,created_at)
    SELECT ?,?,?,?,?,?,?,?,? WHERE ?=?`).bind(input.appId,input.kind,input.releaseId,input.versionName,
      input.versionCode,input.deviceModel ?? null,input.commitSha,input.runId,nowSeconds(),input.appId,env.APP_ID);
}
