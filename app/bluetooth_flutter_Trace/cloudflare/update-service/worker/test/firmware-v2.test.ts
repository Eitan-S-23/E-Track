import { env } from "cloudflare:workers";
import { SELF } from "cloudflare:test";
import { afterEach, describe, expect, it, vi } from "vitest";
import { signHmacSha256 } from "../src/crypto";
import { firmwareAssets, requireFirmwareFull } from "../src/firmware";
import { firmwareTokenMessage, signFirmwareDownload, streamFirmwareObject } from "../src/firmware_download";
import { contentDigest } from "../../scripts/firmware-schema.mjs";
import { canonicalJson } from "../../scripts/firmware-schema.mjs";
import { channelSnapshot } from "../src/firmware_admin";
import { BASE_SHA, bytesFor, draft, latest, metadata, register, registered, uploadFixture, type LatestBody } from "./firmware-fixture";
import type { FirmwareChannelRow, FirmwareReleaseRow } from "../src/types";

afterEach(() => vi.restoreAllMocks());

describe("P4-2 register/schema v2", () => {
  it("registers all three assets atomically and replays canonical reordered metadata without another audit", async () => {
    const { input, releaseId } = await registered(false);
    const replay = await register({ ...input, assets: [...input.assets].reverse() });
    expect(replay.status).toBe(200);
    expect(await replay.json()).toMatchObject({ releaseId, state: "ready", assetsRegistered: 3, idempotent: true });
    expect((await env.DB.prepare("SELECT count(*) AS n FROM audit_logs WHERE target_id=?").bind(releaseId).first<{ n: number }>())!.n).toBe(1);
    expect((await firmwareAssets(env.DB, releaseId)).length).toBe(3);
  });
  it.each(["releaseNotes", "commitSha", "runId", "targetImageSha256"])("conflicts on changed %s", async (field) => {
    const { input } = await registered(false);
    const changed = { ...input, [field]: field.endsWith("Sha") ? "2".repeat(40)
      : field.endsWith("Sha256") ? "2".repeat(64) : "different" };
    const response = await register(changed);
    expect(response.status).toBe(409);
    expect(await response.json()).toMatchObject({ errorCode: "RELEASE_CONFLICT" });
  });
  it.each([
    ["unknown root", (v: any) => { v.typ0 = 1; }],
    ["unknown asset", (v: any) => { v.assets[0].typ0 = 1; }],
    ["unknown kind", (v: any) => { v.assets[0].kind = "delta"; }],
    ["duplicate full", (v: any) => { v.assets.push(v.assets[0]); }],
    ["missing recovery", (v: any) => { v.assets = v.assets.slice(0, 2); }],
    ["null full base", (v: any) => { v.assets[0].baseImageSha256 = null; }],
    ["bad version", (v: any) => { v.versionName = "02.8.1"; }],
    ["wrong formula", (v: any) => { v.versionCode++; }],
    ["u32 overflow", (v: any) => { v.versionCode = 4294967296; }],
    ["App overflow", (v: any) => { v.minAppVersionCode = 2100000001; }],
    ["unverified", (v: any) => { v.assets[0].r2Verified = false; }],
    ["asset path", (v: any) => { v.assets[0].fileName = "../firmware.etu"; }],
    ["mutable URL", (v: any) => { v.assets[0].githubUrl = "https://github.com/a/b/releases/latest/download/x"; }],
    ["wrong URL file", (v: any) => { v.assets[0].githubUrl += "x"; }],
    ["wrong R2 key", (v: any) => { v.assets[0].r2Key += "x"; }]
  ])("rejects %s before SQL side effects", async (_name, mutate) => {
    const input = metadata(); mutate(input);
    const response = await register(input);
    expect(response.status).toBe(400);
    expect(await response.json()).toMatchObject({ errorCode: "INVALID_PARAMETER" });
    expect(await env.DB.prepare("SELECT id FROM firmware_releases WHERE release_tag=?").bind(input.releaseTag).first()).toBeNull();
  });
  it("rejects non-formal releases and invalid/multiple bearer credentials", async () => {
    expect((await register({ ...metadata(), isFormalRelease: false })).status).toBe(403);
    expect((await register(metadata(), { Authorization: "Bearer a, Bearer b" })).status).toBe(401);
    expect((await register(metadata(), { Authorization: "", "X-Deploy-Token": "test-deploy-token" })).status).toBe(401);
  });
  it.each(["Content-Type", "Accept"])("requires %s", async (header) => {
    expect((await register(metadata(), { [header]: "text/plain" })).status).toBe(400);
  });
  it.each(["missing", "size", "metadata digest", "bytes"])("rejects R2 %s mismatch without partial registration", async (kind) => {
    const input = metadata();
    await uploadFixture(input);
    const asset = input.assets[0];
    if (kind === "missing") await env.RELEASES_BUCKET.delete(asset.r2Key);
    else await env.RELEASES_BUCKET.put(asset.r2Key, kind === "size" ? new Uint8Array(3)
      : kind === "bytes" ? new Uint8Array(asset.sizeBytes) : bytesFor("full"),
    { customMetadata: { kind: "full", sha256: kind === "metadata digest" ? "f".repeat(64) : asset.sha256 } });
    expect((await register(input)).status).toBe(503);
    expect(await env.DB.prepare("SELECT id FROM firmware_releases WHERE release_tag=?").bind(input.releaseTag).first()).toBeNull();
  });
  it("rolls back release/assets/channels when audit insertion fails", async () => {
    const input = metadata(); await uploadFixture(input);
    await env.DB.prepare("CREATE TRIGGER p42_fail_register BEFORE INSERT ON audit_logs WHEN NEW.action='register_firmware_release' BEGIN SELECT RAISE(ABORT,'injected audit failure'); END").run();
    try {
      expect((await register(input)).status).toBe(503);
      expect(await env.DB.prepare("SELECT id FROM firmware_releases WHERE release_tag=?").bind(input.releaseTag).first()).toBeNull();
    } finally { await env.DB.prepare("DROP TRIGGER p42_fail_register").run(); }
  });
  it("serializes 20 identical concurrent registrations to one release and audit", async () => {
    const input = metadata(); await uploadFixture(input);
    const responses = await Promise.all(Array.from({ length: 20 }, () => register(input)));
    expect(responses.filter((r) => r.status === 201)).toHaveLength(1);
    expect(responses.filter((r) => r.status === 200)).toHaveLength(19);
    const ids = await Promise.all(responses.map(async (r) => (await r.json<{ releaseId: string }>()).releaseId));
    expect(new Set(ids).size).toBe(1);
  });
});

describe("P4-2 latest and public download", () => {
  it("distinguishes raw R2 conditions from quoted HTTP entity tags", async () => {
    const input = metadata();
    await uploadFixture(input);
    const key = input.assets.find((asset) => asset.kind === "full")!.r2Key;
    const head = (await env.RELEASES_BUCKET.head(key))!;
    expect(head.httpEtag).toBe(`"${head.etag}"`);
    const matched = await env.RELEASES_BUCKET.get(key, { onlyIf: { etagMatches: head.etag } });
    expect(matched && "body" in matched).toBe(true);
    if (matched && "body" in matched) await matched.body.cancel();
    await expect(async () => {
      await env.RELEASES_BUCKET.get(key, { onlyIf: { etagMatches: head.httpEtag } });
    }).rejects.toThrow(/Conditional ETag.*quotes/);
    const mismatched = await env.RELEASES_BUCKET.get(key, { onlyIf: { etagMatches: "not-the-etag" } });
    expect(mismatched).not.toBeNull();
    expect(mismatched && "body" in mismatched).toBe(false);
  });
  it.each(["opaque", 'W/"opaque"', '""', '"bad"quote"', '"bad\netag"'])(
    "rejects a noncanonical stored HTTP entity tag %j", async (etag) => {
      const { releaseId } = await registered(false);
      const asset = (await firmwareAssets(env.DB, releaseId)).find((row) => row.kind === "full")!;
      await expect(streamFirmwareObject(new Request("https://example.com/asset"), env.RELEASES_BUCKET,
        { ...asset, r2_etag: etag }, "etag-negative")).rejects.toThrow("lacks verified R2 identity");
    });
  async function flags(disableLatest: number, disableDownloads: number, message: string | null) {
    const c = (await env.DB.prepare("SELECT * FROM firmware_channels WHERE app_id='trace' AND device_model='e-track-at32f435' AND name='stable'")
      .first<FirmwareChannelRow>())!;
    const after = { ...c, revision: c.revision + 1, disable_latest: disableLatest, disable_downloads: disableDownloads, maintenance_message: message };
    await env.DB.prepare(`UPDATE firmware_channels SET disable_latest=?,disable_downloads=?,maintenance_message=?,revision=revision+1,
      last_action='stop_downloads',last_actor='fixture',last_actor_type='test',last_request_id=?,last_reason='self-test flag fixture',
      last_before_json=?,last_after_json=? WHERE id=? AND revision=?`)
      .bind(disableLatest, disableDownloads, message, crypto.randomUUID(), canonicalJson(channelSnapshot(c)),
        canonicalJson(channelSnapshot(after)), c.id, c.revision).run();
  }
  it("honors independent latest/download stop flags with already-issued URLs", async () => {
    await registered();
    const body = await (await latest()).json<LatestBody>();
    try {
      await flags(1, 0, "maintenance");
      expect(await (await latest()).json()).toMatchObject({ schemaVersion: 2, updateAvailable: false, errorCode: "CHANNEL_STOPPED", maintenanceMessage: "maintenance" });
      expect((await SELF.fetch(body.asset.downloadUrl)).status).toBe(200);
      await flags(0, 1, null);
      expect((await latest()).status).toBe(200);
      const stopped = await SELF.fetch(body.asset.downloadUrl);
      expect(stopped.status).toBe(503); expect(await stopped.json()).toMatchObject({ errorCode: "CHANNEL_STOPPED" });
    } finally { await flags(0, 0, null); }
  });
  it.each(["draft", "missing full"])("fails closed on a deliberately corrupted %s channel read model", async (caseName) => {
    await registered();
    const channel = (await env.DB.prepare("SELECT * FROM firmware_channels WHERE name='stable' AND app_id='trace'").first<FirmwareChannelRow>())!;
    const bad = await draft();
    const names = ["firmware_pointer_update", "firmware_channel_mutation_guard", "firmware_ready_update"];
    const definitions = [];
    for (const name of names) definitions.push((await env.DB.prepare("SELECT sql FROM sqlite_master WHERE name=?").bind(name).first<{ sql: string }>())!.sql);
    for (const name of names) await env.DB.prepare(`DROP TRIGGER ${name}`).run();
    try {
      if (caseName === "missing full") await env.DB.prepare("UPDATE firmware_releases SET state='ready' WHERE id=?").bind(bad.releaseId).run();
      await env.DB.prepare("UPDATE firmware_channels SET current_release_id=? WHERE id=?").bind(bad.releaseId, channel.id).run();
      expect((await latest()).status).toBe(503);
    } finally {
      await env.DB.prepare("UPDATE firmware_channels SET current_release_id=? WHERE id=?").bind(channel.current_release_id, channel.id).run();
      for (const definition of definitions) await env.DB.prepare(definition).run();
    }
  });
  it("selects exact raw-SHA patch, falls back to full, hides recovery and returns no update", async () => {
    const { input } = await registered();
    const patch = await (await latest()).json<LatestBody>();
    expect(patch.asset.kind).toBe("patch");
    expect(patch.asset.baseImageSha256).toBe(BASE_SHA);
    const full = await (await latest({ currentImageSha: "22".repeat(32) })).json<LatestBody>();
    expect(full.asset.kind).toBe("full");
    expect(full.asset.baseImageSha256).toBeNull();
    expect(full.targetImageSha256).not.toBe(full.asset.sha256);
    for (const current of [input.versionCode, input.versionCode + 1]) {
      const noUpdate = await (await latest({ currentVersionCode: String(current), appVersionCode: "0", hardwareRevision: "9" })).json();
      expect(noUpdate).toMatchObject({ schemaVersion: 2, updateAvailable: false, errorCode: "NO_UPDATE" });
      expect(noUpdate).not.toHaveProperty("asset");
    }
  });
  it("falls back when matching patch is archived but rejects an archived full even when patch matches", async () => {
    const { releaseId } = await registered();
    await env.DB.prepare("UPDATE firmware_release_assets SET r2_state='archived' WHERE release_id=? AND kind='patch'").bind(releaseId).run();
    expect((await (await latest()).json<LatestBody>()).asset.kind).toBe("full");
    await env.DB.prepare("UPDATE firmware_release_assets SET r2_state='archived' WHERE release_id=? AND kind='full'").bind(releaseId).run();
    expect((await latest()).status).toBe(503);
  });
  it.each([
    ["appVersionCode", "", "INVALID_PARAMETER", 400], ["appVersionCode", "1e2", "INVALID_PARAMETER", 400],
    ["appVersionCode", "-1", "INVALID_PARAMETER", 400], ["appVersionCode", "2100000001", "INVALID_PARAMETER", 400],
    ["currentImageSha", "11", "INVALID_PARAMETER", 400], ["currentImageSha", "A".repeat(64), "INVALID_PARAMETER", 400],
    ["deviceModel", "igpsport-bsc300", "UNKNOWN_DEVICE_MODEL", 400], ["unknown", "x", "INVALID_PARAMETER", 400],
    ["hardwareRevision", "2", "HARDWARE_INCOMPATIBLE", 409], ["layoutId", "2", "LAYOUT_INCOMPATIBLE", 409],
    ["bootVersion", "0", "BOOT_TOO_OLD", 409], ["protocolVersion", "2", "PROTOCOL_UNSUPPORTED", 409]
  ])("rejects latest %s=%s without download information", async (field, value, code, status) => {
    await registered();
    const response = await latest({ [field]: String(value) });
    expect(response.status).toBe(status);
    const result = await response.json();
    expect(result).toMatchObject({ errorCode: code });
    expect(result).not.toHaveProperty("asset");
    expect(result).not.toHaveProperty("downloadUrl");
  });
  it("applies App gate before the ordered hardware/layout/Boot/protocol checks", async () => {
    await registered(true, { minAppVersionCode: 150 });
    const response = await latest({ hardwareRevision: "2", layoutId: "2", bootVersion: "0", protocolVersion: "0" });
    expect(response.status).toBe(426);
    expect(await response.json()).toMatchObject({ errorCode: "CLIENT_TOO_OLD", minAppVersionCode: 150 });
  });
  it("rejects missing or duplicate query parameters", async () => {
    const query = "appId=trace&deviceModel=e-track-at32f435&channel=stable";
    expect((await SELF.fetch(`https://example.com/api/public/firmware/latest?${query}`)).status).toBe(400);
    expect((await SELF.fetch(`https://example.com/api/public/firmware/latest?${query}&channel=beta`)).status).toBe(400);
  });
  it("defensively rejects missing and duplicate full read models", async () => {
    const { releaseId } = await registered(false);
    const release = (await env.DB.prepare("SELECT * FROM firmware_releases WHERE id=?").bind(releaseId).first<FirmwareReleaseRow>())!;
    const assets = await firmwareAssets(env.DB, releaseId);
    expect(() => requireFirmwareFull(release, assets.filter((a) => a.kind !== "full"))).toThrow();
    expect(() => requireFirmwareFull(release, [...assets, assets.find((a) => a.kind === "full")!])).toThrow();
  });
  it("enforces headers, byte identity and correct full/partial digest semantics", async () => {
    await registered();
    const body = await (await latest()).json<LatestBody>();
    const full = await SELF.fetch(body.asset.downloadUrl);
    expect(full.status).toBe(200);
    expect(full.headers.get("Content-Type")).toBe("application/vnd.e-track.etu");
    expect(full.headers.get("Content-Digest")).toBe(contentDigest(body.asset.sha256));
    expect(full.headers.get("Content-Length")).toBe(String(body.asset.sizeBytes));
    expect(full.headers.get("ETag")).toMatch(/^"[^\"]+"$/);
    expect(full.headers.get("X-Request-Id")).toBeTruthy();
    expect(new Uint8Array(await full.arrayBuffer())).toEqual(bytesFor("patch"));
    const partial = await SELF.fetch(body.asset.downloadUrl, { headers: { Range: "bytes=3-", "If-Range": full.headers.get("ETag")! } });
    expect(partial.status).toBe(206);
    expect(partial.headers.get("Content-Range")).toBe(`bytes 3-${body.asset.sizeBytes - 1}/${body.asset.sizeBytes}`);
    expect(partial.headers.has("Content-Digest")).toBe(false);
    expect(new Uint8Array(await partial.arrayBuffer())).toEqual(bytesFor("patch").slice(3));
    const changed = await SELF.fetch(body.asset.downloadUrl, { headers: { Range: "bytes=3-", "If-Range": '"other"' } });
    expect(changed.status).toBe(200);
    expect((await changed.arrayBuffer()).byteLength).toBe(body.asset.sizeBytes);
  });
  it.each(["bytes=-3", "bytes=1-2", "bytes=1-,3-", "bytes=1e2-", "items=1-"])("rejects Range %s", async (range) => {
    await registered();
    const body = await (await latest()).json<LatestBody>();
    expect((await SELF.fetch(body.asset.downloadUrl, { headers: { Range: range } })).status).toBe(400);
  });
  it("returns 416 at/past EOF and rejects a mutated immutable R2 object", async () => {
    const { input } = await registered();
    const body = await (await latest()).json<LatestBody>();
    expect((await SELF.fetch(body.asset.downloadUrl, { headers: { Range: `bytes=${body.asset.sizeBytes}-` } })).status).toBe(416);
    const patch = input.assets.find((a) => a.kind === "patch")!;
    await env.RELEASES_BUCKET.put(patch.r2Key, new Uint8Array(patch.sizeBytes), { customMetadata: { sha256: patch.sha256, kind: patch.kind } });
    expect((await SELF.fetch(body.asset.downloadUrl)).status).toBe(503);
  });
  it("revokes public URLs when the release is no longer published", async () => {
    await registered();
    const old = await (await latest()).json<LatestBody>();
    await registered();
    expect((await SELF.fetch(old.asset.downloadUrl)).status).toBe(410);
  });
});

describe("P4-2 token v2 and bounded v1 verifier", () => {
  it("matches the frozen 67-byte token golden vector", async () => {
    const message = firmwareTokenMessage({ id: "asset-patch-20801", release_id: "release-20801", kind: "patch" }, "public-ota", 1800000300, "7");
    expect(new TextEncoder().encode(message).length).toBe(67);
    expect(await signHmacSha256(message, String.fromCharCode(...Array.from({ length: 32 }, (_, i) => i))))
      .toBe("DmjZ33S6hz_9jrbUtdv_BqGNvOY4GCjNJqIcBpvZuzU");
    expect(contentDigest("00".repeat(32))).toBe("sha-256=:AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA=:");
  });
  it.each(["missing", "empty", "duplicate", "unknown", "purpose", "kind", "asset", "signature"])("rejects %s token mutation", async (kind) => {
    await registered();
    const body = await (await latest()).json<LatestBody>();
    const url = new URL(body.asset.downloadUrl);
    if (kind === "missing") url.searchParams.delete("kind");
    if (kind === "empty") url.searchParams.set("kind", "");
    if (kind === "duplicate") url.searchParams.append("kind", "patch");
    if (kind === "unknown") url.searchParams.set("foo", "bar");
    if (kind === "purpose") url.searchParams.set("purpose", "admin-recovery");
    if (kind === "kind") url.searchParams.set("kind", "full");
    if (kind === "asset") url.searchParams.set("assetId", "other");
    if (kind === "signature") url.searchParams.set("signature", "x".repeat(43));
    expect((await SELF.fetch(url.toString())).status).toBe(401);
  });
  it("expires v2 at the exact deadline and never signs v1", async () => {
    await registered();
    const body = await (await latest()).json<LatestBody>();
    expect(new URL(body.asset.downloadUrl).searchParams.get("tokenVersion")).toBe("2");
    vi.spyOn(Date, "now").mockReturnValue(body.asset.expiresAt * 1000);
    expect(await (await SELF.fetch(body.asset.downloadUrl)).json()).toMatchObject({ errorCode: "TOKEN_EXPIRED" });
  });
  it("accepts a rotated previous v2 key and binds actual asset kind, not just the signature", async () => {
    const { releaseId } = await registered();
    const asset = (await firmwareAssets(env.DB, releaseId)).find((a) => a.kind === "full")!;
    const rotated = await signFirmwareDownload({ ...env, DOWNLOAD_TOKEN_KEY_VERSION: "previous", DOWNLOAD_HMAC_KEY_CURRENT: env.DOWNLOAD_HMAC_KEY_PREVIOUS },
      "https://example.com", asset, "public-ota");
    expect((await SELF.fetch(rotated.downloadUrl)).status).toBe(200);
    const wrongKind = await signFirmwareDownload(env, "https://example.com", { ...asset, kind: "patch" }, "public-ota");
    expect((await SELF.fetch(wrongKind.downloadUrl)).status).toBe(401);
  });
  it("accepts only public v1 inside the fixed cutover window and rejects at cutoff", async () => {
    const { releaseId } = await registered();
    const assets = await firmwareAssets(env.DB, releaseId);
    const now = Number(env.FIRMWARE_V2_CUTOVER_EPOCH);
    vi.spyOn(Date, "now").mockReturnValue((now + 10) * 1000);
    async function legacy(kind: string, expires = now + 300) {
      const asset = assets.find((a) => a.kind === kind)!;
      const message = ["GET", asset.id, releaseId, String(expires), env.DOWNLOAD_TOKEN_KEY_VERSION].join("\n");
      const signature = await signHmacSha256(message, env.DOWNLOAD_HMAC_KEY_CURRENT!);
      return `https://example.com/api/public/firmware/download?${new URLSearchParams({ assetId: asset.id, releaseId,
        expiresAt: String(expires), keyVersion: env.DOWNLOAD_TOKEN_KEY_VERSION, signature })}`;
    }
    expect((await SELF.fetch(await legacy("full"))).status).toBe(200);
    expect((await SELF.fetch(await legacy("recovery"))).status).toBe(401);
    expect((await SELF.fetch(await legacy("full", now + 301))).status).toBe(401);
    vi.mocked(Date.now).mockReturnValue((now + 300) * 1000);
    expect((await SELF.fetch(await legacy("full"))).status).toBe(401);
  });
  it("fails signing closed without an auditable cutover", async () => {
    await expect(signFirmwareDownload({ ...env, FIRMWARE_V2_CUTOVER_EPOCH: undefined }, "https://example.com",
      { id: "asset", release_id: "release", kind: "full" }, "public-ota")).rejects.toThrow("cutover");
  });
});

describe("P4-2 actual SQL constraints", () => {
  async function insert(releaseId: string, fields: Record<string, unknown> = {}) {
    const row = { kind: "full", base: "", vcode: 0, name: crypto.randomUUID(), id: crypto.randomUUID(), ...fields };
    return env.DB.prepare(`INSERT INTO firmware_release_assets
      (id,release_id,kind,file_name,sha256,size_bytes,r2_key,r2_etag,r2_state,github_url,base_image_sha256,base_vcode)
      VALUES (?,?,?,?,'${"a".repeat(64)}',1,?,'"verified"','available','https://github.com/a/b/releases/download/v/f',?,?)`)
      .bind(row.id, releaseId, row.kind, row.name, row.id, row.base, row.vcode).run();
  }
  async function rejects(label: string, action: Promise<unknown>) {
    let message = "";
    try { await action; } catch (error) { message = String(error); }
    expect(message).toMatch(/constraint|firmware|NOT NULL|UNIQUE/i);
    console.info(`SQL_REJECT ${label}: ${message}`);
  }
  it("database rejects the second full, not an application precheck", async () => {
    const { releaseId } = await draft(); await insert(releaseId);
    await rejects("XC-D1-DUP-FULL", insert(releaseId));
  });
  it("database rejects the second patch for the same raw base", async () => {
    const { releaseId } = await draft(); await insert(releaseId, { kind: "patch", base: BASE_SHA, vcode: 20800 });
    await rejects("XC-D1-DUP-PATCH", insert(releaseId, { kind: "patch", base: BASE_SHA, vcode: 20800 }));
  });
  it("database rejects the second recovery asset", async () => {
    const { releaseId } = await draft(); await insert(releaseId, { kind: "recovery" });
    await rejects("duplicate-recovery", insert(releaseId, { kind: "recovery" }));
  });
  it.each([
    ["NULL full", { base: null }], ["full with SHA", { base: BASE_SHA }], ["full with version", { vcode: 1 }],
    ["empty patch", { kind: "patch", vcode: 1 }], ["zero patch version", { kind: "patch", base: BASE_SHA }],
    ["uppercase SHA", { kind: "patch", base: "A".repeat(64), vcode: 1 }],
    ["unknown kind", { kind: "other" }], ["recovery base", { kind: "recovery", vcode: 1 }],
    ["patch ahead of target", { kind: "patch", base: BASE_SHA, vcode: 4294967295 }]
  ])("SQL rejects illegal kind/base: %s", async (name, fields) => {
    const { releaseId } = await draft(); await rejects(String(name), insert(releaseId, fields));
  });
  it("database rejects ready without full, and retains draft", async () => {
    const { releaseId } = await draft();
    await insert(releaseId, { kind: "patch", base: BASE_SHA, vcode: 20800 });
    await rejects("XC-D1-NO-FULL-READY", env.DB.prepare("UPDATE firmware_releases SET state='ready' WHERE id=?").bind(releaseId).run());
    expect(await env.DB.prepare("SELECT state FROM firmware_releases WHERE id=?").bind(releaseId).first()).toMatchObject({ state: "draft" });
  });
  it("database rejects unpublished asset readiness and draft/cross-scope channel pointers", async () => {
    const { releaseId } = await draft(); await insert(releaseId);
    await env.DB.prepare("UPDATE firmware_release_assets SET r2_state='not_uploaded' WHERE release_id=?").bind(releaseId).run();
    await rejects("unverified-ready", env.DB.prepare("UPDATE firmware_releases SET state='ready' WHERE id=?").bind(releaseId).run());
    await rejects("draft-pointer", env.DB.prepare("INSERT INTO firmware_channels(id,app_id,device_model,name,current_release_id) VALUES (?,'trace','other','beta',?)")
      .bind(crypto.randomUUID(), releaseId).run());
  });
  it("rejects direct channel changes without CAS and admin audit without a reason", async () => {
    await registered();
    await rejects("channel-CAS", env.DB.prepare("UPDATE firmware_channels SET disable_downloads=1 WHERE app_id='trace' AND name='stable'").run());
    await rejects("admin-reason", env.DB.prepare(`INSERT INTO audit_logs(id,app_id,actor,actor_type,action,target_type,request_id,after_json)
      VALUES (?,'trace','owner','access','publish','firmware_channel','test','{}')`).bind(crypto.randomUUID()).run());
  });
});
