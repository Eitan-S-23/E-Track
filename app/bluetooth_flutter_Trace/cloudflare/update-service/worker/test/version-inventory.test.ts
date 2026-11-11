import { env } from "cloudflare:workers";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { cleanupInventory, inventoryControl, inventorySummary, refreshInventory, reportInventory, sha256Text } from "../src/version_inventory";

const enabled = { ...env, VERSION_INVENTORY_ENABLED: "true" };
const now = 1800000000;
const day = 86400;
const token = "a".repeat(64);
function payload() {
  return { appId: "trace", platform: "android", sequence: 1, versionCode: 100, versionName: "1.0.74", imageSha256: "b".repeat(64),
    devices: [{ deviceKey: "c".repeat(64), identityScope: "installation", deviceModel: "e-track-at32f435", versionCode: 30321,
      imageSha256: "d".repeat(64), hardwareRevision: 1, layoutId: 1, observationId: crypto.randomUUID(), ageSeconds: 0 }] };
}
function req(body: unknown, credential = token) {
  return new Request("https://example.com/api/public/version-inventory", { method: "POST",
    headers: { "Content-Type": "application/json", Authorization: `Bearer ${credential}`, "CF-Connecting-IP": crypto.randomUUID() }, body: JSON.stringify(body) });
}
async function summary(at = now) { return (await inventorySummary(enabled, at)).json<{
  app: Array<{ active7: number; active30: number; active90: number; versionCode: number }>;
  firmware: Array<{ active7: number; active30: number; active90: number; lastSeen: number }>;
  uniqueDeviceCount: null; refreshResponses: number;
}>(); }

beforeEach(async () => {
  await env.DB.batch([env.DB.prepare("DELETE FROM version_inventory_installations"),
    env.DB.prepare("DELETE FROM version_inventory_budget"),
    env.DB.prepare("UPDATE version_inventory_control SET refresh_id='initial',requested_at=0,daily_limit=5000 WHERE id=1")]);
});
afterEach(() => vi.restoreAllMocks());

describe("optional version inventory", () => {
  it("is disabled until explicitly configured and never changes release state", async () => {
    await expect(reportInventory(req(payload()), { ...enabled, VERSION_INVENTORY_ENABLED: "false" }, now)).rejects.toMatchObject({ status: 503 });
    expect((await summary()).app).toEqual([]);
  });
  it("counts installations once and updates their current version instead of cumulative request counts", async () => {
    const p = payload();
    await reportInventory(req(p), enabled, now);
    await reportInventory(req({ ...p, sequence: 2 }), enabled, now + 10);
    expect((await summary()).app).toMatchObject([{ active7: 1, versionCode: 100 }]);
    await reportInventory(req({ ...p, sequence: 3, versionCode: 101, imageSha256: "e".repeat(64) }), enabled, now + 20);
    expect((await summary()).app).toMatchObject([{ active7: 1, versionCode: 101 }]);
  });
  it("does not pretend installation-scoped MCU observations are globally unique devices", async () => {
    const p = payload();
    await reportInventory(req(p), enabled, now);
    await reportInventory(req(p, "f".repeat(64)), enabled, now);
    const s = await summary();
    expect(s.firmware[0].active7).toBe(2);
    expect(s.uniqueDeviceCount).toBeNull();
  });
  it("keeps a cached MCU observation old when its phone reports again", async () => {
    const p = payload(); p.devices[0].ageSeconds = 20 * day;
    await reportInventory(req(p), enabled, now);
    await reportInventory(req({ ...p, sequence: 2 }), enabled, now + day);
    const s = await summary(now + day);
    expect(s.app[0].active7).toBe(1);
    expect(s.firmware[0]).toMatchObject({ active7: 0, active30: 1, lastSeen: now - 20 * day });
  });
  it("refreshes only a new observation, not repeated delivery of the old nonce", async () => {
    const p = payload(); p.devices[0].ageSeconds = 20 * day;
    await reportInventory(req(p), enabled, now);
    p.devices[0] = { ...p.devices[0], observationId: crypto.randomUUID(), ageSeconds: 0 };
    await reportInventory(req({ ...p, sequence: 2 }), enabled, now + 1);
    expect((await summary(now + 1)).firmware[0]).toMatchObject({ active7: 1, lastSeen: now + 1 });
  });
  it("rejects reused sequence with changed bytes and ignores an older delayed report", async () => {
    const p = payload(); await reportInventory(req(p), enabled, now);
    await expect(reportInventory(req({ ...p, versionCode: 101 }), enabled, now)).rejects.toMatchObject({ code: "IDEMPOTENCY_CONFLICT" });
    await reportInventory(req({ ...p, sequence: 4, versionCode: 102 }), enabled, now);
    await reportInventory(req({ ...p, sequence: 3, versionCode: 101 }), enabled, now);
    expect((await summary()).app[0].versionCode).toBe(102);
  });
  it("bounds devices and removes absent observations from the installation snapshot", async () => {
    const p = payload(); await reportInventory(req(p), enabled, now);
    await reportInventory(req({ ...p, sequence: 2, devices: [] }), enabled, now + 1);
    expect((await summary()).firmware).toEqual([]);
    await expect(reportInventory(req({ ...p, sequence: 3, devices: Array(5).fill(p.devices[0]) }), enabled, now)).rejects.toMatchObject({ status: 400 });
  });
  it.each(["imageSha256", "sequence", "versionCode"])("rejects invalid %s without adding a record", async (field) => {
    await expect(reportInventory(req({ ...payload(), [field]: -1 }), enabled, now)).rejects.toMatchObject({ status: 400 });
    expect((await summary()).app).toEqual([]);
  });
  it("rejects arbitrary global identities, future ages, duplicated devices and absent credentials", async () => {
    const p = payload();
    for (const patch of [{ identityScope: "global" }, { ageSeconds: -1 }]) {
      await expect(reportInventory(req({ ...p, devices: [{ ...p.devices[0], ...patch }] }), enabled, now)).rejects.toMatchObject({ status: 400 });
    }
    await expect(reportInventory(req({ ...p, devices: [p.devices[0], p.devices[0]] }), enabled, now)).rejects.toMatchObject({ status: 400 });
    await expect(reportInventory(req(p, ""), enabled, now)).rejects.toMatchObject({ status: 401 });
  });
  it("limits body bytes before parsing even without Content-Length", async () => {
    await expect(reportInventory(req({ ...payload(), padding: "x".repeat(9000) }), enabled, now)).rejects.toMatchObject({ status: 400 });
  });
  it("makes refresh idempotent, keeps existing counts and records later responses", async () => {
    const p = payload(); await reportInventory(req(p), enabled, now);
    const requestId = crypto.randomUUID();
    await refreshInventory(enabled, "owner@example.com", { requestId }, now + 1);
    await refreshInventory(enabled, "owner@example.com", { requestId }, now + 2);
    expect((await summary()).refreshResponses).toBe(0);
    expect((await summary()).app[0].active30).toBe(1);
    await reportInventory(req({ ...p, sequence: 2 }), enabled, now + 3);
    expect((await summary(now + 3)).refreshResponses).toBe(1);
    await expect(refreshInventory(enabled, "owner@example.com", { requestId: crypto.randomUUID() }, now + 4)).rejects.toMatchObject({ status: 429 });
  });
  it("enforces the installation day cap without overwriting the previous state", async () => {
    const p = payload();
    for (let n = 1; n <= 8; n++) await reportInventory(req({ ...p, sequence: n, versionCode: 100 + n }), enabled, now + n);
    await expect(reportInventory(req({ ...p, sequence: 9, versionCode: 109 }), enabled, now + 9)).rejects.toMatchObject({ status: 429 });
    expect((await summary()).app[0].versionCode).toBe(108);
  });
  it("enforces the global budget transactionally and permits reports the following day", async () => {
    await env.DB.prepare("UPDATE version_inventory_control SET daily_limit=1 WHERE id=1").run();
    const p = payload(); await reportInventory(req(p), enabled, now);
    await expect(reportInventory(req(p, "f".repeat(64)), enabled, now)).rejects.toMatchObject({ status: 429 });
    expect((await summary()).app[0].active7).toBe(1);
    await reportInventory(req({ ...p, sequence: 2 }), enabled, now + day);
    expect((await summary(now + day)).app[0].active7).toBe(1);
  });
  it("hashes the private installation token and never returns identifiers in aggregates", async () => {
    await reportInventory(req(payload()), enabled, now);
    expect((await env.DB.prepare("SELECT install_key FROM version_inventory_installations").first<{ install_key: string }>())?.install_key).toBe(await sha256Text(token));
    const body = JSON.stringify(await summary());
    expect(body).not.toContain(token);
    expect(body).not.toContain(await sha256Text(token));
    expect(await (await inventoryControl(req({}), enabled)).json()).toMatchObject({ refreshId: "initial", reportIntervalSeconds: day });
  });
  it("expires old MCU observations even while the installation is still active", async () => {
    const p = payload(); p.devices[0].ageSeconds = 89 * day;
    await reportInventory(req(p), enabled, now);
    await cleanupInventory(enabled, now + 2 * day);
    expect((await summary(now + 2 * day)).app).toHaveLength(1);
    expect((await env.DB.prepare("SELECT * FROM version_inventory_devices").all()).results).toEqual([]);
    await cleanupInventory(enabled, now + 91 * day);
    expect((await env.DB.prepare("SELECT * FROM version_inventory_installations").all()).results).toEqual([]);
  });
});
