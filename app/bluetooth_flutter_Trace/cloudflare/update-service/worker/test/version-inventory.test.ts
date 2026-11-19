import { env } from "cloudflare:workers";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { cleanupInventory, inventoryControl, inventorySummary, inventoryDetails, refreshInventory, reportInventory, sha256Text } from "../src/version_inventory";

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

function detail(kind: "app" | "firmware" = "app", patch: Record<string, string> = {}) {
  return new URL(`https://example.com/api/admin/version-inventory/detail?${new URLSearchParams({kind,
    versionCode: kind === "app" ? "100" : "30321", imageSha256: (kind === "app" ? "b" : "d").repeat(64),
    ...(kind === "app" ? {platform:"android",versionName:"1.0.74"} : {deviceModel:"e-track-at32f435",hardwareRevision:"1",layoutId:"1"}),
    windowDays:"30", ...patch})}`);
}

describe("read-only inventory details", () => {
  it("preserves the legacy retry fingerprint and leaves absent metadata unknown", async () => {
    const p = payload();
    const identity = p.devices.map(({ageSeconds: _age, ...device}) => device);
    const fingerprint = await sha256Text(JSON.stringify([p.versionCode,p.versionName,p.imageSha256,identity]));
    await reportInventory(req(p), enabled, now);
    expect((await env.DB.prepare("SELECT state_hash FROM version_inventory_installations").first<{state_hash:string}>())?.state_hash).toBe(fingerprint);
    expect(await (await inventoryDetails(enabled, detail(), now)).json()).toMatchObject({
      sampleCount:1,unknownModels:1,unknownIps:1,models:[],reports:[{brand:null,model:null,osVersion:null,ip:null}]});
  });
  it("stores bounded phone fields and derives IP only from the trusted edge header", async () => {
    const p = {...payload(),phone:{brand:"Example",model:"Model A",osVersion:"16 (SDK 36)"},
      quality:{scope:"companion-day",day:"2027-01-15",connectionAttempts:4,connectionSucceeded:3,connectionFailed:1}};
    const request = req(p);
    request.headers.set("CF-Connecting-IP", "198.51.100.23");
    request.headers.set("X-Forwarded-For", "203.0.113.7");
    await reportInventory(request, enabled, now);
    const result = await (await inventoryDetails(enabled, detail(), now)).json<Record<string, unknown>>();
    expect(result).toMatchObject({sampleCount:1,models:[{brand:"Example",model:"Model A",count:1,share:1}],
      ips:[{ip:"198.51.100.23",count:1}],reports:[{ip:"198.51.100.23",osVersion:"16 (SDK 36)"}],
      quality:{samples:1,connectionAttempts:4,connectionSucceeded:3,connectionFailed:1}});
    expect(JSON.stringify(result)).not.toContain(token);
    expect(JSON.stringify(result)).not.toContain("203.0.113.7");
    await expect(reportInventory(req({...p,sequence:2,ip:"203.0.113.7"}),enabled,now+1)).rejects.toMatchObject({status:400});
    await expect(reportInventory(req({...p,sequence:2,phone:{model:"A",serialNumber:"secret"}}),enabled,now+1)).rejects.toMatchObject({status:400});
  });
  it.each([
    ["198.51.100.23", "198.51.100.23"], ["2001:0DB8::1", "2001:db8::1"],
    ["::ffff:192.0.2.1", "::ffff:c000:201"], ["192.0.2", null], ["256.0.2.1", null],
    ["192.000.2.1", null], ["2001:db8::invalid", null], ["[2001:db8::1]", null],
    ["2001:db8::1%zone", null], ["user@192.0.2.1", null],
  ])("validates and normalizes edge report address %s", async (ip, expected) => {
    const request = req(payload()); request.headers.set("CF-Connecting-IP", ip!);
    await reportInventory(request, enabled, now);
    const result = await (await inventoryDetails(enabled, detail(), now)).json<{reports:Array<{ip:string|null}>}>();
    expect(result.reports[0].ip).toBe(expected);
  });
  it("shows top five models against the full sample and keeps unknown/other coverage", async () => {
    const models = ["A","A","A","A","B","B","C","D","E","F",null];
    for (const [index,model] of models.entries()) {
      await reportInventory(req({...payload(),...(model ? {phone:{brand:"Example",model}} : {})},
        (index+1).toString(16).padStart(64,"0")), enabled, now-index);
    }
    const result = await (await inventoryDetails(enabled,detail(),now)).json<{
      sampleCount:number;models:Array<{model:string;count:number;share:number}>;unknownModels:number;otherModels:number;
    }>();
    expect(result.sampleCount).toBe(11); expect(result.models).toHaveLength(5);
    expect(result.models[0]).toMatchObject({model:"A",count:4,share:4/11});
    expect(result.unknownModels).toBe(1); expect(result.otherModels).toBe(1);
  });
  it("binds the complete App scope and pages equal-time reports without duplicates", async () => {
    for (let index=1;index<=5;index++) await reportInventory(req(payload(),index.toString(16).padStart(64,"0")),enabled,now);
    await reportInventory(req({...payload(),imageSha256:"e".repeat(64)},"f".repeat(64)),enabled,now);
    const first = await (await inventoryDetails(enabled,detail("app",{limit:"2"}),now)).json<{
      sampleCount:number;reports:Array<{installationTag:string}>;nextCursor:string;
    }>();
    const second = await (await inventoryDetails(enabled,detail("app",{limit:"2",cursor:first.nextCursor}),now)).json<typeof first>();
    const third = await (await inventoryDetails(enabled,detail("app",{limit:"2",cursor:second.nextCursor}),now)).json<typeof first>();
    expect(first.sampleCount).toBe(5);
    expect(new Set([...first.reports,...second.reports,...third.reports].map(row=>row.installationTag)).size).toBe(5);
    expect(third.nextCursor).toBeNull();
    expect((await (await inventoryDetails(enabled,detail("app",{imageSha256:"e".repeat(64)}),now)).json<{sampleCount:number}>()).sampleCount).toBe(1);
  });
  it("links exact firmware observations to their reporting installations' current App versions", async () => {
    const p = payload();
    await reportInventory(req(p),enabled,now);
    await reportInventory(req({...p,versionCode:101,versionName:"1.0.75",imageSha256:"e".repeat(64)},"f".repeat(64)),enabled,now);
    await reportInventory(req({...p,sequence:2,versionCode:102,versionName:"1.0.76",imageSha256:"9".repeat(64)}),enabled,now+1);
    const result = await (await inventoryDetails(enabled,detail("firmware"),now+1)).json<{
      sampleCount:number;associatedApps:Array<{platform:string;versionCode:number;imageSha256:string;count:number}>;
    }>();
    expect(result.sampleCount).toBe(2);
    expect(result.associatedApps).toMatchObject([{platform:"android",versionCode:102,imageSha256:"9".repeat(64),count:1},
      {platform:"android",versionCode:101,imageSha256:"e".repeat(64),count:1}]);
    expect((await (await inventoryDetails(enabled,detail("firmware",{hardwareRevision:"2"}),now)).json<{sampleCount:number}>()).sampleCount).toBe(0);
  });
  it("applies the selected observation window without refreshing old cached MCU observations", async () => {
    const p = payload(); p.devices[0].ageSeconds=20*day;
    await reportInventory(req(p),enabled,now);
    expect((await (await inventoryDetails(enabled,detail("app",{windowDays:"7"}),now)).json<{sampleCount:number}>()).sampleCount).toBe(1);
    expect((await (await inventoryDetails(enabled,detail("firmware",{windowDays:"7"}),now)).json<{sampleCount:number}>()).sampleCount).toBe(0);
    expect((await (await inventoryDetails(enabled,detail("firmware",{windowDays:"30"}),now)).json<{sampleCount:number}>()).sampleCount).toBe(1);
  });
  it("rejects missing, duplicate, cross-platform and malformed scopes before reading details", async () => {
    const urls = [detail("app",{platform:"windows"}),detail("app",{windowDays:"1"}),detail("app",{limit:"51"}),
      detail("app",{cursor:"invalid"}),detail("firmware",{deviceModel:"other"}),detail("firmware",{hardwareRevision:"-1"})];
    const missing=detail("firmware"); missing.searchParams.delete("layoutId"); urls.push(missing);
    const duplicate=detail();duplicate.searchParams.append("versionCode","100");urls.push(duplicate);
    const unknown=detail();unknown.searchParams.set("ip","198.51.100.1");urls.push(unknown);
    for (const url of urls) await expect(inventoryDetails(enabled,url,now)).rejects.toMatchObject({status:400});
    await expect(inventoryDetails({...enabled,VERSION_INVENTORY_ENABLED:"false"},detail(),now)).rejects.toMatchObject({status:503});
  });
  it("rejects oversized, control-character and unbounded diagnostic metadata", async () => {
    for (const phone of [{model:"x".repeat(81)},{brand:"a\nprivate"}]) {
      await expect(reportInventory(req({...payload(),phone}),enabled,now)).rejects.toMatchObject({status:400});
    }
    for (const quality of [{scope:"all-actions",day:"2027-01-15"}, {scope:"companion-day",day:"2027-02-30"},
      {scope:"companion-day",day:"2027-01-15",connectionAttempts:100001}, {scope:"companion-day",day:"2027-01-15",log:"secret"}]) {
      await expect(reportInventory(req({...payload(),quality}),enabled,now)).rejects.toMatchObject({status:400});
    }
    expect((await summary()).app).toEqual([]);
  });
});

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
  it("acknowledges only an already stored matching snapshot and preserves its receipt time", async () => {
    const p = payload();
    expect(await (await reportInventory(req(p), enabled, now)).json()).toMatchObject({
      accepted: true, acknowledged: true, reportedAt: now, sequence: 1 });
    expect(await (await reportInventory(req({ ...p, sequence: 2 }), enabled, now + 10)).json()).toMatchObject({
      accepted: false, acknowledged: true, reportedAt: now, sequence: 1 });
    await reportInventory(req({ ...p, sequence: 4, versionCode: 102 }), enabled, now + 20);
    expect(await (await reportInventory(req({ ...p, sequence: 3 }), enabled, now + 30)).json()).toMatchObject({
      accepted: false, acknowledged: false, reportedAt: null, sequence: 4 });
  });
  it("does not claim a delayed duplicate answered a newer refresh request", async () => {
    const p = payload();
    await reportInventory(req(p), enabled, now);
    const requestId = crypto.randomUUID();
    await refreshInventory(enabled, "owner@example.com", { requestId }, now + 1);
    expect(await (await reportInventory(req(p), enabled, now + 2)).json()).toMatchObject({
      accepted: false, acknowledged: true, refreshId: "initial", reportedAt: now });
    expect(await (await reportInventory(req({ ...p, sequence: 2 }), enabled, now + 3)).json()).toMatchObject({
      accepted: true, acknowledged: true, refreshId: requestId, reportedAt: now + 3 });
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
