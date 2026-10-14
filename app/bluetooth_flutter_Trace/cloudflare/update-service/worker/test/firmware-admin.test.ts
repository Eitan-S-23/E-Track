import { env } from "cloudflare:workers";
import { SELF } from "cloudflare:test";
import { afterEach, beforeAll, describe, expect, it, vi } from "vitest";
import { onRequest } from "../../admin/functions/api/admin/[[path]]";
import { cleanupFirmwareIdempotency, firmwareReleaseAction, listFirmware, publishFirmware } from "../src/firmware_admin";
import { firmwareAssets } from "../src/firmware";
import { bytesFor, draft, latest, registered, type LatestBody } from "./firmware-fixture";
import type { FirmwareChannelRow } from "../src/types";

const adminEnv = { ...env, FIRMWARE_DOWNLOAD_ORIGIN: "https://example.com" };
const owner = " Owner@Example.com ";
afterEach(() => { vi.restoreAllMocks(); vi.unstubAllGlobals(); });

function request(id: string, action = "recovery-download", key: string = crypto.randomUUID(), reason = "owner recovery self-test") {
  return new Request(`https://admin.example.com/api/admin/firmware/releases/${id}/${action}`, {
    method: "POST", headers: { "Content-Type": "application/json", Accept: "application/json", "Idempotency-Key": key },
    body: JSON.stringify({ appId: "trace", deviceModel: "e-track-at32f435", reason }) });
}
function act(id: string, key: string = crypto.randomUUID(), action: "disable" | "recovery-download" = "recovery-download", reason?: string) {
  return firmwareReleaseAction(request(id, action, key, reason), adminEnv, { email: owner, requestId: crypto.randomUUID() }, id, action);
}
async function count(sql: string, id: string) { return (await env.DB.prepare(sql).bind(id).first<{ n: number }>())!.n; }

describe("P4-2 owner recovery and permanent idempotency", () => {
  it("issues a recovery-only URL for unpublished ready firmware and a sanitized atomic audit", async () => {
    const { releaseId } = await registered(false);
    const response = await act(releaseId);
    const body = await response.json<any>();
    expect(body).toMatchObject({ action: "issue_recovery_download", kind: "recovery", releaseId, idempotent: false });
    const url = new URL(body.downloadUrl);
    expect(url.searchParams.get("purpose")).toBe("admin-recovery");
    const downloaded = await SELF.fetch(url.toString());
    expect(downloaded.status).toBe(200);
    expect(downloaded.headers.get("Content-Type")).toBe("application/octet-stream");
    expect(new Uint8Array(await downloaded.arrayBuffer())).toEqual(bytesFor("recovery"));
    const audit = await env.DB.prepare("SELECT * FROM audit_logs WHERE request_id=?").bind(body.requestId).first<any>();
    expect(audit.actor).toBe("owner@example.com");
    expect(audit.action).toBe("issue_recovery_download");
    expect(audit.reason).toBe("owner recovery self-test");
    expect(JSON.parse(audit.before_json)).toEqual({ assetId: body.assetId, kind: "recovery", releaseId,
      r2State: "available", sha256: body.sha256, sizeBytes: body.sizeBytes });
    expect(JSON.stringify(audit)).not.toMatch(/downloadUrl|signature|Idempotency-Key/);
  });
  it("returns the identical URL and original requestId on replay without another audit", async () => {
    const { releaseId } = await registered(false); const key = crypto.randomUUID();
    const first = await (await act(releaseId, key)).json<any>();
    const replay = await act(releaseId, key);
    expect(await replay.json()).toEqual({ ...first, idempotent: true });
    expect(replay.headers.get("X-Request-Id")).toBe(first.requestId);
    expect(await count("SELECT count(*) AS n FROM audit_logs WHERE request_id=?", first.requestId)).toBe(1);
  });
  it("rejects changed reason/action fingerprints across both endpoints", async () => {
    const { releaseId } = await registered(false); const key = crypto.randomUUID();
    await act(releaseId, key);
    await expect(act(releaseId, key, "recovery-download", "different reason")).rejects.toMatchObject({ code: "IDEMPOTENCY_CONFLICT" });
    await expect(act(releaseId, key, "disable")).rejects.toMatchObject({ code: "IDEMPOTENCY_CONFLICT" });
  });
  it("handles 20 concurrent same-key requests with one completed result and one audit", async () => {
    const { releaseId } = await registered(false); const key = crypto.randomUUID();
    const results = await Promise.all(Array.from({ length: 20 }, async () => (await act(releaseId, key)).json<any>()));
    expect(results.filter((r) => !r.idempotent)).toHaveLength(1);
    expect(new Set(results.map((r) => r.requestId)).size).toBe(1);
    expect(new Set(results.map((r) => r.downloadUrl)).size).toBe(1);
    expect(await count("SELECT count(*) AS n FROM firmware_admin_idempotency WHERE idempotency_key=?", key)).toBe(1);
    expect(await count("SELECT count(*) AS n FROM audit_logs WHERE request_id=?", results[0].requestId)).toBe(1);
  });
  it("expires the original URL at exactly 300 seconds; a new key is required", async () => {
    vi.spyOn(Date, "now").mockReturnValue(1800000000000);
    const { releaseId } = await registered(false); const key = crypto.randomUUID();
    await act(releaseId, key);
    vi.mocked(Date.now).mockReturnValue(1800000299000);
    expect((await act(releaseId, key)).status).toBe(200);
    vi.mocked(Date.now).mockReturnValue(1800000300000);
    await expect(act(releaseId, key)).rejects.toMatchObject({ code: "IDEMPOTENCY_RESULT_EXPIRED" });
    expect((await act(releaseId)).status).toBe(200);
  });
  it("starts issuance time after R2 verification, not before a slow readback", async () => {
    vi.spyOn(Date, "now").mockReturnValue(1800000000000);
    const { releaseId } = await registered(false);
    const head = env.RELEASES_BUCKET.head.bind(env.RELEASES_BUCKET);
    vi.spyOn(env.RELEASES_BUCKET, "head").mockImplementation(async (key) => {
      vi.mocked(Date.now).mockReturnValue(1800000100000);
      return head(key);
    });
    const result = await (await act(releaseId)).json<any>();
    expect(result.expiresAt).toBe(1800000400);
  });
  it("different canonical owners can reuse a key but reason bytes are exact", async () => {
    const { releaseId } = await registered(false); const key = crypto.randomUUID();
    const first = await (await act(releaseId, key)).json<any>();
    const other = await firmwareReleaseAction(request(releaseId, "recovery-download", key), adminEnv,
      { email: "other-owner@example.com", requestId: crypto.randomUUID() }, releaseId, "recovery-download");
    expect((await other.json<any>()).requestId).not.toBe(first.requestId);
    await expect(act(releaseId, key, "recovery-download", " owner recovery self-test ")).rejects.toMatchObject({ code: "IDEMPOTENCY_CONFLICT" });
  });
  it("records a tombstone on an expired conflicting request before result cleanup", async () => {
    vi.spyOn(Date, "now").mockReturnValue(1800000000000);
    const { releaseId } = await registered(false); const key = crypto.randomUUID(); await act(releaseId, key);
    vi.mocked(Date.now).mockReturnValue(1800086400000);
    await expect(act(releaseId, key, "recovery-download", "changed")).rejects.toMatchObject({ code: "IDEMPOTENCY_CONFLICT" });
    expect(await count("SELECT count(*) AS n FROM firmware_admin_idempotency WHERE idempotency_key=?", key)).toBe(1);
    expect(await count("SELECT count(*) AS n FROM firmware_admin_idempotency_tombstones WHERE idempotency_key=?", key)).toBe(1);
    await expect(env.DB.prepare(`INSERT INTO firmware_admin_idempotency_tombstones
      SELECT * FROM firmware_admin_idempotency_tombstones WHERE idempotency_key=?`).bind(key).run()).rejects.toThrow(/UNIQUE/);
    await expect(env.DB.prepare(`INSERT OR IGNORE INTO firmware_admin_idempotency_tombstones
      SELECT actor_canonical,idempotency_key,? AS fingerprint,action,release_id,expired_at,tombstoned_at
      FROM firmware_admin_idempotency_tombstones WHERE idempotency_key=?`).bind("0".repeat(64), key).run()).rejects.toThrow(/integrity/);
  });
  it("revokes recovery URLs immediately when the asset becomes archived", async () => {
    const { releaseId } = await registered(false);
    const result = await (await act(releaseId)).json<any>();
    await env.DB.prepare("UPDATE firmware_release_assets SET r2_state='archived' WHERE id=?").bind(result.assetId).run();
    expect((await SELF.fetch(result.downloadUrl)).status).toBe(409);
  });
  it.each(["request-first", "cleanup-first", "concurrent"])("keeps the 24h key guard under %s scheduling", async (schedule) => {
    vi.spyOn(Date, "now").mockReturnValue(1800000000000);
    const { releaseId } = await registered(false); const key = crypto.randomUUID();
    await act(releaseId, key);
    vi.mocked(Date.now).mockReturnValue(1800086400000);
    const expired = () => expect(act(releaseId, key)).rejects.toMatchObject({ code: "IDEMPOTENCY_RESULT_EXPIRED" });
    if (schedule === "request-first") { await expired(); await cleanupFirmwareIdempotency(env.DB); }
    if (schedule === "cleanup-first") { await cleanupFirmwareIdempotency(env.DB); await expired(); }
    if (schedule === "concurrent") await Promise.all([expired(), cleanupFirmwareIdempotency(env.DB)]);
    expect(await count("SELECT count(*) AS n FROM firmware_admin_idempotency_tombstones WHERE idempotency_key=?", key)).toBe(1);
    expect(await count("SELECT count(*) AS n FROM firmware_admin_idempotency WHERE idempotency_key=?", key)).toBe(0);
    await expect(act(releaseId, key, "recovery-download", "changed")).rejects.toMatchObject({ code: "IDEMPOTENCY_CONFLICT" });
    await expired();
  });
  it("keeps disable replay valid until the exclusive 24h boundary and never re-enables disabled firmware", async () => {
    vi.spyOn(Date, "now").mockReturnValue(1800000000000);
    const { releaseId } = await registered(false); const key = crypto.randomUUID();
    const first = await (await act(releaseId, key, "disable")).json<any>();
    for (const now of [1800000000, 1800086399]) {
      vi.mocked(Date.now).mockReturnValue(now * 1000);
      expect(await (await act(releaseId, key, "disable")).json()).toEqual({ ...first, idempotent: true });
    }
    vi.mocked(Date.now).mockReturnValue(1800086400000);
    await expect(act(releaseId, key, "disable")).rejects.toMatchObject({ code: "IDEMPOTENCY_RESULT_EXPIRED" });
    await expect(act(releaseId, crypto.randomUUID(), "disable")).rejects.toMatchObject({ code: "RELEASE_DISABLED" });
    await expect(env.DB.prepare("UPDATE firmware_releases SET state='ready' WHERE id=?").bind(releaseId).run()).rejects.toThrow();
  });
  it("uses real SQL to prevent pending commits, body deletion without tombstone, and tombstone deletion", async () => {
    vi.spyOn(Date, "now").mockReturnValue(1800000000000);
    const { releaseId } = await registered(false); const pendingKey = crypto.randomUUID();
    await expect(env.DB.prepare(`INSERT INTO firmware_admin_idempotency
      (actor_canonical,idempotency_key,fingerprint,method,canonical_path,action,release_id,state,created_epoch_seconds,retained_until)
      VALUES ('owner@example.com',?,'${"a".repeat(64)}','POST',?,'disable',?,'pending',1800000000,1800086400)`)
      .bind(pendingKey, `/api/admin/firmware/releases/${releaseId}/disable`, releaseId).run()).rejects.toThrow(/FOREIGN KEY/i);
    expect(await count("SELECT count(*) AS n FROM firmware_admin_idempotency WHERE idempotency_key=?", pendingKey)).toBe(0);
    const key = crypto.randomUUID(); await act(releaseId, key);
    await expect(env.DB.prepare("DELETE FROM firmware_admin_idempotency WHERE idempotency_key=?").bind(key).run()).rejects.toThrow(/tombstone/i);
    vi.mocked(Date.now).mockReturnValue(1800086400000);
    await cleanupFirmwareIdempotency(env.DB);
    await expect(env.DB.prepare("DELETE FROM firmware_admin_idempotency_tombstones WHERE idempotency_key=?").bind(key).run()).rejects.toThrow(/permanent/i);
  });
  it("rolls back result cleanup if a tombstone cannot be written", async () => {
    vi.spyOn(Date, "now").mockReturnValue(1800000000000);
    const { releaseId } = await registered(false); const key = crypto.randomUUID(); await act(releaseId, key);
    await env.DB.prepare("CREATE TRIGGER p42_tombstone_fail BEFORE INSERT ON firmware_admin_idempotency_tombstones BEGIN SELECT RAISE(ABORT,'injected failure'); END").run();
    try {
      await expect(cleanupFirmwareIdempotency(env.DB, 1800086400)).rejects.toThrow();
      expect(await count("SELECT count(*) AS n FROM firmware_admin_idempotency WHERE idempotency_key=?", key)).toBe(1);
    } finally { await env.DB.prepare("DROP TRIGGER p42_tombstone_fail").run(); }
  });
  it("rolls back pending/result/audit and disable mutation on an audit failure", async () => {
    const { releaseId } = await registered(false);
    await env.DB.prepare("CREATE TRIGGER p42_action_fail BEFORE INSERT ON audit_logs WHEN NEW.actor_type='access' BEGIN SELECT RAISE(ABORT,'injected audit failure'); END").run();
    try {
      await expect(act(releaseId)).rejects.toMatchObject({ code: "BACKEND_UNAVAILABLE" });
      await expect(act(releaseId, crypto.randomUUID(), "disable")).rejects.toMatchObject({ code: "BACKEND_UNAVAILABLE" });
      expect(await env.DB.prepare("SELECT state FROM firmware_releases WHERE id=?").bind(releaseId).first()).toMatchObject({ state: "ready" });
      expect(await count("SELECT count(*) AS n FROM firmware_admin_idempotency WHERE release_id=?", releaseId)).toBe(0);
    } finally { await env.DB.prepare("DROP TRIGGER p42_action_fail").run(); }
  });
  it.each(["draft", "disabled", "archived", "asset archived", "not uploaded", "R2 missing"])("rejects recovery for %s", async (state) => {
    const { releaseId } = state === "draft" ? await draft() : await registered(false);
    if (state === "disabled") await act(releaseId, crypto.randomUUID(), "disable");
    if (state === "archived") await env.DB.prepare("UPDATE firmware_releases SET archived=1 WHERE id=?").bind(releaseId).run();
    if (state === "asset archived" || state === "not uploaded") await env.DB.prepare("UPDATE firmware_release_assets SET r2_state=? WHERE release_id=? AND kind='recovery'")
      .bind(state === "asset archived" ? "archived" : "not_uploaded", releaseId).run();
    if (state === "R2 missing") {
      const asset = (await firmwareAssets(env.DB, releaseId)).find((a) => a.kind === "recovery")!;
      await env.RELEASES_BUCKET.delete(asset.r2_key!);
    }
    const codes: Record<string, string> = { draft: "RELEASE_NOT_READY", disabled: "RELEASE_DISABLED", archived: "RELEASE_ARCHIVED",
      "asset archived": "ASSET_ARCHIVED", "not uploaded": "RECOVERY_ASSET_UNAVAILABLE", "R2 missing": "R2_VERIFY_FAILED" };
    await expect(act(releaseId)).rejects.toMatchObject({ code: codes[state] });
  });
  it("cannot disable a channel-referenced release or publish a draft/stale revision/regression", async () => {
    const { releaseId } = await registered();
    await expect(act(releaseId, crypto.randomUUID(), "disable")).rejects.toMatchObject({ code: "RELEASE_IN_USE" });
    const channel = (await env.DB.prepare("SELECT * FROM firmware_channels WHERE name='stable'").first<FirmwareChannelRow>())!;
    const d = await draft();
    const input = { appId: "trace", deviceModel: "e-track-at32f435", releaseId: d.releaseId, expectedRevision: channel.revision, reason: "test" };
    const actor = { email: "owner@example.com", requestId: crypto.randomUUID() };
    await expect(publishFirmware(env, actor, "stable", input)).rejects.toMatchObject({ code: "RELEASE_NOT_READY" });
    await expect(publishFirmware(env, actor, "stable", { ...input, expectedRevision: channel.revision - 1 })).rejects.toMatchObject({ code: "CAS_CONFLICT" });
    await expect(publishFirmware(env, actor, "stable", { ...input, releaseId })).rejects.toMatchObject({ code: "VERSION_REGRESSION" });
  });
  it("publishes and audits atomically; rejects SQL disable and identity changes on a referenced release", async () => {
    const current = await registered();
    const next = await registered(false);
    const channel = (await env.DB.prepare("SELECT * FROM firmware_channels WHERE name='stable'").first<FirmwareChannelRow>())!;
    await env.DB.prepare("CREATE TRIGGER p42_publish_fail BEFORE INSERT ON audit_logs WHEN NEW.target_type='firmware_channel' BEGIN SELECT RAISE(ABORT,'injected failure'); END").run();
    try {
      await expect(publishFirmware(env, { email: owner, requestId: crypto.randomUUID() }, "stable", { appId: "trace", deviceModel: "e-track-at32f435",
        releaseId: next.releaseId, expectedRevision: channel.revision, reason: "test" })).rejects.toThrow();
      expect(await env.DB.prepare("SELECT current_release_id,revision FROM firmware_channels WHERE id=?").bind(channel.id).first())
        .toMatchObject({ current_release_id: current.releaseId, revision: channel.revision });
    } finally { await env.DB.prepare("DROP TRIGGER p42_publish_fail").run(); }
    await expect(env.DB.prepare("UPDATE firmware_releases SET state='disabled' WHERE id=?").bind(current.releaseId).run()).rejects.toThrow(/in use/);
    await expect(env.DB.prepare("UPDATE firmware_releases SET target_image_sha256=? WHERE id=?").bind("0".repeat(64), current.releaseId).run()).rejects.toThrow(/immutable/);
  });
  it("returns the versioned multi-asset admin read model", async () => {
    const { releaseId } = await registered();
    const url = new URL("https://admin.example.com/api/admin/firmware/releases?appId=trace&deviceModel=e-track-at32f435");
    const body = await (await listFirmware(env, url, "read-model", false)).json<any>();
    expect(body.firmwareReleases.find((r: any) => r.releaseId === releaseId)).toMatchObject({ state: "ready", publishedChannels: ["stable"], assets: expect.any(Array) });
    expect(body.requestId).toBe("read-model");
  });
});

describe("P4-2 existing Access Pages facade", () => {
  let keys: CryptoKeyPair;
  let jwk: JsonWebKey;
  const issuer = "https://p42-test.cloudflareaccess.com";
  const b64 = (value: Uint8Array) => btoa(String.fromCharCode(...value)).replace(/\+/g, "-").replace(/\//g, "_").replace(/=+$/, "");
  const encodeText = (value: string) => b64(new TextEncoder().encode(value));
  beforeAll(async () => {
    keys = await crypto.subtle.generateKey({ name: "RSASSA-PKCS1-v1_5", modulusLength: 2048,
      publicExponent: new Uint8Array([1, 0, 1]), hash: "SHA-256" }, true, ["sign", "verify"]);
    jwk = await crypto.subtle.exportKey("jwk", keys.publicKey);
  });
  async function jwt(email: string, exp = Math.floor(Date.now() / 1000) + 3600) {
    const encode = (v: unknown) => b64(new TextEncoder().encode(JSON.stringify(v)));
    const message = `${encode({ alg: "RS256", kid: "p42" })}.${encode({ iss: issuer, aud: ["p42"], email, exp })}`;
    return `${message}.${b64(new Uint8Array(await crypto.subtle.sign("RSASSA-PKCS1-v1_5", keys.privateKey, new TextEncoder().encode(message))))}`;
  }
  async function page(id: string, options: { email?: string; header?: Record<string, string>; reason?: string; extra?: object; key?: string;
    token?: string | null; jwksResponse?: () => Promise<Response> } = {}) {
    vi.stubGlobal("fetch", vi.fn(options.jwksResponse ?? (async () => Response.json({ keys: [{ ...jwk, kid: "p42" }] }))));
    const route = ["firmware", "releases", id, "recovery-download"];
    const req = new Request(`https://admin.example.com/api/admin/${route.join("/")}`, { method: "POST", headers: {
      ...(options.token === null ? {} : { "CF-Access-Jwt-Assertion": options.token ?? await jwt(options.email ?? "owner@example.com") }),
      "Content-Type": "application/json", Accept: "application/json", Origin: "https://admin.example.com",
      "X-CSRF-Token": "csrf-fixture", Cookie: "trace_admin_csrf=csrf-fixture", "Idempotency-Key": options.key ?? crypto.randomUUID(), ...options.header
    }, body: JSON.stringify({ appId: "trace", deviceModel: "e-track-at32f435", reason: options.reason ?? "approved self-test", ...options.extra }) });
    return onRequest({ request: req, params: { path: route }, env: { ...adminEnv, APP_ID: "trace", ENVIRONMENT: "dev",
      ACCESS_JWT_ISSUER: issuer, ACCESS_JWT_AUD: "p42", ADMIN_OWNER_EMAILS: "owner@example.com", ADMIN_PUBLISHER_EMAILS: "publisher@example.com",
      ASSETS: { fetch: async () => new Response() } },
      data: {}, functionPath: "/api/admin", next: async () => new Response(), waitUntil() {}, passThroughOnException() {} } as Parameters<typeof onRequest>[0]);
  }
  it("validates a real test JWT and preserves original requestId in replay JSON and header", async () => {
    const { releaseId } = await registered(false); const key = crypto.randomUUID();
    const first = await page(releaseId, { key });
    const body = await first.json<any>(); expect(first.status).toBe(200);
    const replay = await page(releaseId, { key });
    expect(await replay.json()).toEqual({ ...body, idempotent: true });
    expect(replay.headers.get("X-Request-Id")).toBe(body.requestId);
  });
  it("rejects an expired valid JWT and malformed response-correlation headers", async () => {
    const { releaseId } = await registered(false);
    const expired = await page(releaseId, { token: await jwt("owner@example.com", Math.floor(Date.now() / 1000) - 1) });
    expect(await expired.json()).toMatchObject({ errorCode: "TOKEN_EXPIRED" });
    const valid = await page(releaseId, { header: { "X-Request-Id": "invalid request id" } });
    const body = await valid.json<any>();
    expect(valid.status).toBe(200);
    expect(body.requestId).not.toBe("invalid request id");
    expect(body.requestId).toBe(valid.headers.get("X-Request-Id"));
  });
  it.each([
    ["missing assertion", null],
    ["wrong segment count", "invalid"],
    ["unsupported algorithm", `${encodeText('{"alg":"none"}')}.e30.AA`],
    ["invalid Base64URL", "!.e30.AA"],
    ["invalid header JSON", `${encodeText('{"alg":')}.e30.AA`],
    ["null header", "bnVsbA.e30.AA"],
    ["null payload", `${encodeText('{"alg":"RS256","kid":"p42"}')}.bnVsbA.AA`]
  ] as const)("returns TOKEN_INVALID/401 for %s before network or database access", async (_name, token) => {
    const prepare = vi.spyOn(env.DB, "prepare");
    const response = await page("unqueried-release", { token });
    const body = await response.json<any>();
    expect(response.status).toBe(401);
    expect(body).toEqual({ errorCode: "TOKEN_INVALID", message: expect.any(String), requestId: expect.any(String) });
    expect(response.headers.get("X-Request-Id")).toBe(body.requestId);
    expect(fetch).not.toHaveBeenCalled();
    expect(prepare).not.toHaveBeenCalled();
    if (token) expect(JSON.stringify(body)).not.toContain(token);
  });
  it("keeps invalid signatures as TOKEN_INVALID/401 without a database access", async () => {
    const token = `${(await jwt("owner@example.com")).split(".").slice(0, 2).join(".")}.AA`;
    const prepare = vi.spyOn(env.DB, "prepare");
    const response = await page("unqueried-release", { token });
    expect(response.status).toBe(401);
    expect(await response.json()).toMatchObject({ errorCode: "TOKEN_INVALID" });
    expect(prepare).not.toHaveBeenCalled();
  });
  it.each(["HTTP failure", "invalid JSON", "network failure"])("keeps JWKS %s as BACKEND_UNAVAILABLE/503", async (failure) => {
    vi.spyOn(Date, "now").mockReturnValue(1900000000000);
    const prepare = vi.spyOn(env.DB, "prepare");
    const response = await page("unqueried-release", { jwksResponse: async () => {
      if (failure === "network failure") throw new Error("JWKS transport unavailable");
      return failure === "invalid JSON" ? new Response("{") : new Response(null, { status: 503 });
    } });
    expect(response.status).toBe(503);
    expect(await response.json()).toMatchObject({ errorCode: "BACKEND_UNAVAILABLE" });
    expect(fetch).toHaveBeenCalledTimes(1);
    expect(prepare).not.toHaveBeenCalled();
  });
  it("does not classify an unexpected decoder failure as invalid credentials", async () => {
    vi.stubGlobal("atob", () => { throw new Error("decoder unavailable"); });
    const prepare = vi.spyOn(env.DB, "prepare");
    const response = await page("unqueried-release");
    expect(response.status).toBe(503);
    expect(await response.json()).toMatchObject({ errorCode: "BACKEND_UNAVAILABLE" });
    expect(fetch).not.toHaveBeenCalled();
    expect(prepare).not.toHaveBeenCalled();
  });
  it.each([
    ["publisher", { email: "publisher@example.com" }, 403, "ROLE_FORBIDDEN"],
    ["unknown actor", { email: "nobody@example.com" }, 403, "ACCESS_FORBIDDEN"],
    ["origin", { header: { Origin: "https://other.example.com" } }, 403, "ORIGIN_FORBIDDEN"],
    ["csrf", { header: { "X-CSRF-Token": "bad" } }, 403, "CSRF_INVALID"],
    ["bad key", { key: "not-a-uuid" }, 400, "INVALID_PARAMETER"],
    ["empty reason", { reason: "  " }, 400, "INVALID_PARAMETER"],
    ["unknown field", { extra: { releaseId: "forbidden" } }, 400, "INVALID_PARAMETER"],
    ["invalid JWT", { token: "invalid" }, 401, "TOKEN_INVALID"]
  ] as const)("rejects %s without a success audit", async (_name, options, status, code) => {
    const { releaseId } = await registered(false);
    const response = await page(releaseId, options);
    expect(response.status).toBe(status);
    const body = await response.json<any>();
    expect(body.errorCode).toBe(code);
    expect(body).not.toHaveProperty("downloadUrl");
    expect(await count("SELECT count(*) AS n FROM firmware_admin_idempotency WHERE release_id=?", releaseId)).toBe(0);
  });
});
