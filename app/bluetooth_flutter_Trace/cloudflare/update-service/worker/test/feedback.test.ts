import { env } from "cloudflare:workers";
import { beforeEach, expect, it } from "vitest";
import { cleanupFeedback, feedbackDetail, listFeedback, submitFeedback, updateFeedback } from "../src/feedback";
import { sha256Text } from "../src/version_inventory";

const now = 1794996000;
let sequence = 0, ip: string;
const token = () => crypto.randomUUID().replaceAll("-", "") + crypto.randomUUID().replaceAll("-", "");
const data = () => ({ appId: "trace", batchId: crypto.randomUUID(), messages: [{ id: crypto.randomUUID(),
  body: "Feedback <script>must remain text</script>", createdAt: now, platform: "android", versionName: "1.0.82", versionCode: 108 }] });
type Payload = ReturnType<typeof data>;
function request(body: unknown, key: string, address = ip) {
  return new Request("https://example.test/api/public/feedback", { method: "POST", headers: {
    "Content-Type": "application/json", Authorization: "Bearer " + key, "CF-Connecting-IP": address,
  }, body: JSON.stringify(body) });
}
async function count(table: string) { return env.DB.prepare(`SELECT COUNT(*) AS n FROM ${table}`).first<number>("n"); }
beforeEach(async () => {
  ip = `203.0.113.${++sequence}`;
  await env.DB.batch(["feedback_events", "feedback_messages", "feedback_batches"].map(table => env.DB.prepare(`DELETE FROM ${table}`)));
});

it("accepts one batch and returns a no-store receipt without token or IP", async () => {
  const payload = data(), key = token();
  const response = await submitFeedback(request(payload, key), env, now);
  expect(response.status).toBe(201);
  expect(response.headers.get("Cache-Control")).toBe("no-store");
  const text = await response.text();
  expect(text).not.toContain(key); expect(text).not.toContain(ip);
  expect(JSON.parse(text)).toMatchObject({ ok: true, batchId: payload.batchId, acceptedIds: [payload.messages[0].id] });
  const row = await env.DB.prepare("SELECT * FROM feedback_batches").first();
  expect(row?.install_key).toBe(await sha256Text(key)); expect(row?.ip_key).not.toBe(ip);
  expect(await count("feedback_messages")).toBe(1);
});

it("shares the daily installation allowance across versions and IP changes", async () => {
  const key = token();
  expect((await submitFeedback(request(data(), key), env, now)).status).toBe(201);
  const changed = data(); changed.messages[0].versionCode++;
  const response = await submitFeedback(request(changed, key, "198.51.100.2"), env, now + 60);
  expect(response.status).toBe(429); expect(await response.json()).toMatchObject({ scope: "installation" });
  expect(await count("feedback_batches")).toBe(1);
  expect((await submitFeedback(request(changed, key), env, now + 86400)).status).toBe(201);
});

it("uses the Beijing midnight boundary, not device time or a rolling day", async () => {
  const key = token(), midnight = Date.parse("2026-11-19T00:00:00+08:00") / 1000;
  const first = await submitFeedback(request(data(), key), env, midnight - 1);
  expect(await first.json()).toMatchObject({ nextAllowedAt: midnight });
  expect((await submitFeedback(request(data(), key), env, midnight)).status).toBe(201);
});

it("normalizes IPv6 spellings into the same shared pool and rejects invalid IPs", async () => {
  await submitFeedback(request(data(), token(), "2001:0db8:0:0:0:0:0:123"), env, now);
  await submitFeedback(request(data(), token(), "2001:db8::123"), env, now);
  expect(await env.DB.prepare("SELECT COUNT(DISTINCT ip_key) AS n FROM feedback_batches").first("n")).toBe(1);
  for (const invalid of ["999.1.2.3", "1.2.3.4:80", "2001:db8::xyz", "012.1.2.3"]) {
    await expect(submitFeedback(request(data(), token(), invalid), env, now)).rejects.toMatchObject({ code: "INVALID_PARAMETER" });
  }
});

it("acknowledges a lost-response replay without spending another day or duplicating messages", async () => {
  const key = token(), payload = data();
  await submitFeedback(request(payload, key), env, now);
  const replay = await submitFeedback(request(payload, key, "198.51.100.3"), env, now + 86400);
  expect(await replay.json()).toMatchObject({ replayed: true, receivedAt: now });
  expect(await count("feedback_batches")).toBe(1); expect(await count("feedback_messages")).toBe(1);
  expect((await submitFeedback(request(data(), key), env, now + 86400)).status).toBe(201);
});

it("rejects changed replay content and another installation claiming the same batch", async () => {
  const payload = data(), key = token(); await submitFeedback(request(payload, key), env, now);
  const changed = structuredClone(payload); changed.messages[0].body = "changed";
  await expect(submitFeedback(request(changed, key), env, now)).rejects.toMatchObject({ code: "IDEMPOTENCY_CONFLICT" });
  await expect(submitFeedback(request(payload, token()), env, now)).rejects.toMatchObject({ code: "IDEMPOTENCY_CONFLICT" });
  expect(await count("feedback_batches")).toBe(1);
});

it("atomically admits only one of concurrent batches from an installation", async () => {
  const key = token();
  const responses = await Promise.all(Array.from({ length: 5 }, () => submitFeedback(request(data(), key), env, now)));
  expect(responses.filter(response => response.status === 201)).toHaveLength(1);
  expect(responses.filter(response => response.status === 429)).toHaveLength(4);
  expect(await count("feedback_batches")).toBe(1); expect(await count("feedback_messages")).toBe(1);
});

it("atomically enforces the 50-batch shared IP pool and keeps other IPs independent", async () => {
  await submitFeedback(request(data(), token()), env, now);
  const row = (await env.DB.prepare("SELECT ip_key,report_day FROM feedback_batches LIMIT 1").first<{ ip_key: string; report_day: number }>())!;
  await env.DB.batch(Array.from({ length: 48 }, (_, i) => env.DB.prepare(
    "INSERT INTO feedback_batches(id,install_key,payload_hash,report_day,ip_key,received_at) VALUES(?,?,?,?,?,?)")
    .bind(crypto.randomUUID(), `fixture-${i}`, "fixture", row.report_day, row.ip_key, now)));
  const results = await Promise.all(Array.from({ length: 5 }, () => submitFeedback(request(data(), token()), env, now)));
  expect(results.filter(response => response.status === 201)).toHaveLength(1);
  for (const response of results.filter(response => response.status === 429)) expect(await response.json()).toMatchObject({ scope: "ip" });
  expect(await count("feedback_batches")).toBe(50);
  expect((await submitFeedback(request(data(), token(), "198.51.100.4"), env, now)).status).toBe(201);
  expect((await submitFeedback(request(data(), token()), env, now + 86400)).status).toBe(201);
});

it("concurrent exact replays return consistent acknowledgements", async () => {
  const key = token(), payload = data();
  const responses = await Promise.all(Array.from({ length: 5 }, () => submitFeedback(request(payload, key), env, now)));
  expect(responses.every(response => [200, 201].includes(response.status))).toBe(true);
  expect(await count("feedback_messages")).toBe(1); expect(await count("feedback_batches")).toBe(1);
});

it("rolls back the daily budget when a reused message ID aborts the batch", async () => {
  const payload = data(), key = token(); await submitFeedback(request(payload, key), env, now);
  payload.batchId = crypto.randomUUID();
  await expect(submitFeedback(request(payload, key), env, now + 86400)).rejects.toMatchObject({ code: "IDEMPOTENCY_CONFLICT" });
  expect(await count("feedback_batches")).toBe(1);
  expect((await submitFeedback(request(data(), key), env, now + 86400)).status).toBe(201);
});

for (const [label, mutate] of [
  ["empty", (body: Payload) => { body.messages[0].body = "  "; }],
  ["oversized", (body: Payload) => { body.messages[0].body = "x".repeat(2001); }],
  ["too many", (body: Payload) => { body.messages = Array.from({ length: 11 }, () => data().messages[0]); }],
  ["duplicate", (body: Payload) => { body.messages.push(body.messages[0]); }],
  ["wrong app", (body: Payload) => { body.appId = "foreign"; }],
] as const) it(`rejects ${label} feedback without consuming quota`, async () => {
  const payload = data(); mutate(payload);
  await expect(submitFeedback(request(payload, token()), env, now)).rejects.toMatchObject({ code: "INVALID_PARAMETER" });
  expect(await count("feedback_batches")).toBe(0);
});

it("requires the trusted IP and token and applies a short-window request cap", async () => {
  await expect(submitFeedback(request(data(), token(), ""), env, now)).rejects.toThrow();
  const key = token(), payload = data();
  await expect(submitFeedback(request(payload, "bad"), env, now)).rejects.toMatchObject({ code: "TOKEN_INVALID" });
  for (let i = 0; i < 19; i++) await submitFeedback(request(payload, key), env, now);
  const last = await submitFeedback(request(payload, key), env, now);
  expect(last.status).toBe(429); expect(await last.json()).toMatchObject({ scope: "requests" });
});

it("lists and updates feedback with optimistic concurrency and original history", async () => {
  await submitFeedback(request(data(), token()), env, now);
  const listing = await (await listFeedback(env, new URL("https://example.test/?status=pending")))
    .json<{ feedback: Array<{ id: number; body: string; revision: number }> }>();
  const item = listing.feedback[0];
  expect(item.body).toContain("<script>");
  await updateFeedback(env, item.id, "owner@example.com", { status: "processing", note: "Investigating", revision: 1 }, now + 1);
  await expect(updateFeedback(env, item.id, "other", { status: "resolved", note: "stale", revision: 1 }, now + 2))
    .rejects.toMatchObject({ code: "CAS_CONFLICT" });
  expect(await (await feedbackDetail(env, item.id)).json()).toMatchObject({
    feedback: { status: "processing", revision: 2, note: "Investigating" },
    history: [{ revision: 2, actor: "owner@example.com", note: "Investigating" }],
  });
  expect(await (await listFeedback(env, new URL("https://example.test/?status=pending"))).json()).toMatchObject({ feedback: [] });
  await cleanupFeedback(env, now + 91 * 86400);
  expect(await count("feedback_messages")).toBe(0); expect(await count("feedback_events")).toBe(0);
  expect(await count("feedback_batches")).toBe(1);
});
