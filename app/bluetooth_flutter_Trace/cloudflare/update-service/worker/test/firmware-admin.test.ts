import { env } from "cloudflare:workers";
import { SELF } from "cloudflare:test";
import { afterEach, beforeAll, describe, expect, it, vi } from "vitest";
import { onRequest } from "../../admin/functions/api/admin/[[path]]";
import { cleanupFirmwareIdempotency, firmwareReleaseAction, listFirmware, mutateFirmwareChannel, publishFirmware,
  type FirmwareChannelAction } from "../src/firmware_admin";
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

const firmwareScope = { appId: "trace", deviceModel: "e-track-at32f435" };
const channelRow = (name: string) => env.DB.prepare("SELECT * FROM firmware_channels WHERE app_id='trace' AND device_model=? AND name=?")
  .bind(firmwareScope.deviceModel, name).first<FirmwareChannelRow>();
async function changeChannel(name: string, action: FirmwareChannelAction, fields: Record<string, unknown> = {}, requestId = crypto.randomUUID()) {
  const channel = (await channelRow(name))!;
  return mutateFirmwareChannel(env, { email: owner, requestId }, name, action,
    { ...firmwareScope, expectedRevision: channel.revision, reason: "P4-3 operator reason", ...fields });
}
async function freshChannel(name = "stable") {
  const current = await registered();
  if (name === "beta") await changeChannel(name, "publish", { releaseId: current.releaseId });
  if ((await channelRow(name))!.disable_latest) await changeChannel(name, "resume_latest");
  if ((await channelRow(name))!.disable_downloads) await changeChannel(name, "resume_downloads");
  return current;
}

describe("P4-3 atomic channel controls", () => {
  it("retracts only the pointer/revision/audit and gives upgraded devices NO_UPDATE", async () => {
    const old = await registered(false);
    const current = await freshChannel();
    const before = (await channelRow("stable"))!;
    const releases = await env.DB.prepare("SELECT * FROM firmware_releases WHERE id IN (?,?) ORDER BY id")
      .bind(old.releaseId, current.releaseId).all();
    const assets = await env.DB.prepare("SELECT * FROM firmware_release_assets WHERE release_id IN (?,?) ORDER BY id")
      .bind(old.releaseId, current.releaseId).all();
    const requestId = crypto.randomUUID();
    const result = await (await changeChannel("stable", "retract", { releaseId: old.releaseId }, requestId)).json<any>();
    expect(result).toEqual({ ok: true, requestId, action: "retract", channel: "stable", revision: before.revision + 1,
      currentReleaseId: old.releaseId, disableLatest: false, disableDownloads: false, maintenanceMessage: null, idempotent: false });
    expect((await env.DB.prepare("SELECT * FROM firmware_releases WHERE id IN (?,?) ORDER BY id")
      .bind(old.releaseId, current.releaseId).all()).results).toEqual(releases.results);
    expect((await env.DB.prepare("SELECT * FROM firmware_release_assets WHERE release_id IN (?,?) ORDER BY id")
      .bind(old.releaseId, current.releaseId).all()).results).toEqual(assets.results);
    const audit = await env.DB.prepare("SELECT * FROM audit_logs WHERE request_id=?").bind(requestId).first<any>();
    expect(audit).toMatchObject({ action: "retract", actor: "owner@example.com", reason: "P4-3 operator reason", target_id: before.id });
    expect(JSON.parse(audit.before_json)).toMatchObject({ currentReleaseId: current.releaseId, revision: before.revision });
    expect(JSON.parse(audit.after_json)).toMatchObject({ currentReleaseId: old.releaseId, revision: result.revision });
    expect((await latest({ currentVersionCode: "1" })).status).toBe(200);
    expect(await (await latest({ currentVersionCode: "1" })).json()).toMatchObject({ updateAvailable: true, releaseId: old.releaseId });
    expect(await (await latest({ currentVersionCode: String(current.input.versionCode) })).json())
      .toMatchObject({ updateAvailable: false, errorCode: "NO_UPDATE" });
    expect(await (await latest({ currentVersionCode: String(old.input.versionCode) })).json())
      .toMatchObject({ updateAvailable: false, errorCode: "NO_UPDATE" });
  });
  it.each(["publish", "retract"] as const)("%s never clears an independent stop flag", async (action) => {
    const old = await registered(false); await freshChannel();
    const next = await registered(false);
    await changeChannel("stable", "stop_latest", { maintenanceMessage: "investigation" });
    await changeChannel("stable", "stop_downloads");
    const body = await (await changeChannel("stable", action, { releaseId: action === "publish" ? next.releaseId : old.releaseId })).json<any>();
    expect(body).toMatchObject({ disableLatest: true, disableDownloads: true, maintenanceMessage: "investigation", idempotent: false });
  });
  it("stops old signed URLs independently of latest and preserves the other switch on resume", async () => {
    await freshChannel();
    const metadata = await (await latest()).json<LatestBody>();
    await changeChannel("stable", "stop_downloads", { maintenanceMessage: "download incident" });
    expect(await (await latest()).json()).toMatchObject({ updateAvailable: true });
    const stopped = await SELF.fetch(metadata.asset.downloadUrl);
    expect(stopped.status).toBe(503);
    expect(await stopped.json()).toMatchObject({ errorCode: "CHANNEL_STOPPED" });
    await changeChannel("stable", "stop_latest");
    expect(await (await latest()).json()).toMatchObject({ updateAvailable: false, errorCode: "CHANNEL_STOPPED" });
    const resumedDownload = await (await changeChannel("stable", "resume_downloads")).json<any>();
    expect(resumedDownload).toMatchObject({ disableLatest: true, disableDownloads: false, maintenanceMessage: "download incident" });
    const permitted = await SELF.fetch(metadata.asset.downloadUrl);
    expect(permitted.status).toBe(200); await permitted.arrayBuffer();
    expect(await (await latest()).json()).toMatchObject({ errorCode: "CHANNEL_STOPPED" });
    expect(await (await changeChannel("stable", "resume_latest")).json()).toMatchObject({ disableLatest: false,
      disableDownloads: false, maintenanceMessage: null });
    await changeChannel("stable", "stop_downloads");
    await changeChannel("stable", "stop_latest");
    expect(await (await changeChannel("stable", "resume_latest")).json()).toMatchObject({ disableLatest: false, disableDownloads: true });
    expect((await SELF.fetch(metadata.asset.downloadUrl)).status).toBe(503);
  });
  it("conservatively blocks a release shared by stable and a stopped beta without changing token v2", async () => {
    const current = await freshChannel();
    await changeChannel("beta", "publish", { releaseId: current.releaseId });
    const metadata = await (await latest()).json<LatestBody>();
    await changeChannel("beta", "stop_downloads");
    expect((await SELF.fetch(metadata.asset.downloadUrl)).status).toBe(503);
    await changeChannel("beta", "resume_downloads");
    const permitted = await SELF.fetch(metadata.asset.downloadUrl);
    expect(permitted.status).toBe(200); await permitted.arrayBuffer();
  });
  it.each(["stop_latest", "resume_latest", "stop_downloads", "resume_downloads"] as const)(
    "same-value %s checks CAS but adds no revision or success audit", async (action) => {
      await freshChannel();
      if (action.startsWith("stop")) await changeChannel("stable", action);
      const before = (await channelRow("stable"))!;
      const requestId = crypto.randomUUID();
      const result = await (await changeChannel("stable", action, {}, requestId)).json<any>();
      expect(result).toMatchObject({ idempotent: true, revision: before.revision, requestId });
      expect(await count("SELECT count(*) AS n FROM audit_logs WHERE request_id=?", requestId)).toBe(0);
      expect(await channelRow("stable")).toEqual(before);
      await expect(changeChannel("stable", action, { expectedRevision: before.revision - 1 }))
        .rejects.toMatchObject({ code: "CAS_CONFLICT" });
    });
  it("audits a real maintenance-message change without pretending it is a no-op", async () => {
    await freshChannel(); await changeChannel("stable", "stop_latest", { maintenanceMessage: "first" });
    const before = (await channelRow("stable"))!;
    const result = await (await changeChannel("stable", "stop_latest", { maintenanceMessage: "second" })).json<any>();
    expect(result).toMatchObject({ revision: before.revision + 1, maintenanceMessage: "second", idempotent: false });
    expect(await count("SELECT count(*) AS n FROM audit_logs WHERE request_id=?", result.requestId)).toBe(1);
  });
  it.each(["publish", "retract", "stop_latest", "resume_latest", "stop_downloads", "resume_downloads"] as const)(
    "rolls back %s and its revision when the shared audit rejects insertion", async (action) => {
      await freshChannel(); const target = await registered(false);
      if (action === "resume_latest") await changeChannel("stable", "stop_latest");
      if (action === "resume_downloads") await changeChannel("stable", "stop_downloads");
      const before = await channelRow("stable"); const requestId = crypto.randomUUID();
      await env.DB.prepare("CREATE TRIGGER p43_channel_audit_failure BEFORE INSERT ON audit_logs WHEN NEW.target_type='firmware_channel' BEGIN SELECT RAISE(ABORT,'injected channel audit failure'); END").run();
      try {
        await expect(changeChannel("stable", action, action === "publish" || action === "retract" ? { releaseId: target.releaseId } : {}, requestId))
          .rejects.toMatchObject({ code: "BACKEND_UNAVAILABLE" });
        expect(await channelRow("stable")).toEqual(before);
        expect(await count("SELECT count(*) AS n FROM audit_logs WHERE request_id=?", requestId)).toBe(0);
      } finally { await env.DB.prepare("DROP TRIGGER p43_channel_audit_failure").run(); }
    });
  it("allows only one winner among concurrent same-revision writes", async () => {
    await freshChannel(); const before = (await channelRow("stable"))!;
    const ids = Array.from({ length: 12 }, () => crypto.randomUUID());
    const outcomes = await Promise.allSettled(ids.map(id => changeChannel("stable", "stop_latest", { expectedRevision: before.revision }, id)));
    expect(outcomes.filter(r => r.status === "fulfilled")).toHaveLength(1);
    for (const outcome of outcomes) if (outcome.status === "rejected") expect(outcome.reason).toMatchObject({ code: "CAS_CONFLICT" });
    expect((await channelRow("stable"))!.revision).toBe(before.revision + 1);
    let audits = 0;
    for (const id of ids) audits += await count("SELECT count(*) AS n FROM audit_logs WHERE request_id=?", id);
    expect(audits).toBe(1);
  });
  it.each(["publish", "retract", "resume_latest", "resume_downloads"] as const)(
    "%s fails closed if asset state changes after readback but before the CAS batch", async (action) => {
      const current = await freshChannel(); const target = await registered(false);
      if (action === "resume_latest") await changeChannel("stable", "stop_latest");
      if (action === "resume_downloads") await changeChannel("stable", "stop_downloads");
      const releaseId = action === "publish" || action === "retract" ? target.releaseId : current.releaseId;
      const before = await channelRow("stable"); const requestId = crypto.randomUUID();
      const batch = env.DB.batch.bind(env.DB);
      const spy = vi.spyOn(env.DB, "batch").mockImplementationOnce(async statements => {
        spy.mockRestore();
        await env.DB.prepare("UPDATE firmware_release_assets SET r2_state='archived' WHERE release_id=? AND kind='full'").bind(releaseId).run();
        return batch(statements);
      });
      try {
        await expect(changeChannel("stable", action, action === "publish" || action === "retract" ? { releaseId } : {}, requestId))
          .rejects.toMatchObject({ code: "CAS_CONFLICT" });
        expect(await channelRow("stable")).toEqual(before);
        expect(await count("SELECT count(*) AS n FROM audit_logs WHERE request_id=?", requestId)).toBe(0);
      } finally {
        spy.mockRestore();
        await env.DB.prepare("UPDATE firmware_release_assets SET r2_state='available' WHERE release_id=? AND kind='full'").bind(releaseId).run();
      }
    });
  it.each(["resume_latest", "resume_downloads"] as const)("%s cannot reopen an unavailable asset", async action => {
    const { releaseId } = await freshChannel();
    await changeChannel("stable", action === "resume_latest" ? "stop_latest" : "stop_downloads");
    const before = await channelRow("stable");
    await env.DB.prepare("UPDATE firmware_release_assets SET r2_state='archived' WHERE release_id=? AND kind='full'").bind(releaseId).run();
    try {
      await expect(changeChannel("stable", action)).rejects.toMatchObject({ code: "ASSET_ARCHIVED" });
      expect(await channelRow("stable")).toEqual(before);
    } finally { await env.DB.prepare("UPDATE firmware_release_assets SET r2_state='available' WHERE release_id=? AND kind='full'").bind(releaseId).run(); }
  });
  it.each(["publish", "retract"] as const)("%s rejects missing R2 bytes before any mutation", async action => {
    await freshChannel(); const target = await registered(false); const before = await channelRow("stable");
    const asset = (await firmwareAssets(env.DB, target.releaseId))[0];
    await env.RELEASES_BUCKET.delete(asset.r2_key!);
    await expect(changeChannel("stable", action, { releaseId: target.releaseId })).rejects.toMatchObject({ code: "R2_VERIFY_FAILED" });
    expect(await channelRow("stable")).toEqual(before);
  });
});

describe("P4-2 owner recovery and permanent idempotency", () => {
  it("reconciles a same-key disable committed after lookup but before the follower's state check", async () => {
    const { releaseId } = await registered(false); const key = crypto.randomUUID();
    const batch = env.DB.batch.bind(env.DB); let inject = true; let winner: any;
    const spy = vi.spyOn(env.DB, "batch").mockImplementation(async statements => {
      const records = await batch(statements);
      if (inject && statements.length === 2) {
        inject = false;
        winner = await (await act(releaseId, key, "disable")).json();
      }
      return records;
    });
    try {
      const replay = await (await act(releaseId, key, "disable")).json<any>();
      expect(replay).toEqual({ ...winner, idempotent: true });
      expect(await count("SELECT count(*) AS n FROM audit_logs WHERE request_id=?", winner.requestId)).toBe(1);
    } finally { spy.mockRestore(); }
  });
  it("rejects key reuse across release identities even when action and reason match", async () => {
    const first = await registered(false); const second = await registered(false); const key = crypto.randomUUID();
    const result = await (await act(first.releaseId, key)).json<any>();
    await expect(act(second.releaseId, key)).rejects.toMatchObject({ code: "IDEMPOTENCY_CONFLICT" });
    expect(await count("SELECT count(*) AS n FROM firmware_admin_idempotency WHERE release_id=?", second.releaseId)).toBe(0);
    expect(await count("SELECT count(*) AS n FROM audit_logs WHERE request_id=?", result.requestId)).toBe(1);
  });
  it.each(["disable", "recovery-download"] as const)("preserves %s fingerprint conflicts when disable wins after lookup", async action => {
    const { releaseId } = await registered(false); const key = crypto.randomUUID();
    const batch = env.DB.batch.bind(env.DB); let inject = true;
    const spy = vi.spyOn(env.DB, "batch").mockImplementation(async statements => {
      const records = await batch(statements);
      if (inject && statements.length === 2) {
        inject = false;
        await act(releaseId, key, "disable", "winning intent");
      }
      return records;
    });
    try {
      await expect(act(releaseId, key, action, "different intent")).rejects.toMatchObject({ code: "IDEMPOTENCY_CONFLICT" });
      expect(await count("SELECT count(*) AS n FROM firmware_admin_idempotency WHERE idempotency_key=? AND state='completed'", key)).toBe(1);
      expect(await count("SELECT count(*) AS n FROM firmware_admin_idempotency WHERE idempotency_key=? AND state='pending'", key)).toBe(0);
    } finally { spy.mockRestore(); }
  });
  it("reconciles a committed recovery result even if the follower's R2 readback then fails", async () => {
    const { releaseId } = await registered(false); const key = crypto.randomUUID();
    const batch = env.DB.batch.bind(env.DB); let inject = true; let winner: any;
    const spy = vi.spyOn(env.DB, "batch").mockImplementation(async statements => {
      const records = await batch(statements);
      if (inject && statements.length === 2) {
        inject = false;
        winner = await (await act(releaseId, key)).json();
        const recovery = (await firmwareAssets(env.DB, releaseId)).find(asset => asset.kind === "recovery")!;
        await env.RELEASES_BUCKET.delete(recovery.r2_key!);
      }
      return records;
    });
    try {
      const replay = await act(releaseId, key);
      expect(await replay.json()).toEqual({ ...winner, idempotent: true });
      expect(replay.headers.get("X-Request-Id")).toBe(winner.requestId);
      expect(await count("SELECT count(*) AS n FROM audit_logs WHERE request_id=?", winner.requestId)).toBe(1);
    } finally { spy.mockRestore(); }
  });
  it("binds exact Unicode reason bytes and reordered JSON to the RFC 8785 fingerprint", async () => {
    const { releaseId } = await registered(false); const key = crypto.randomUUID(); const reason = " reason \u20ac \ud83d\ude80 ";
    const first = await (await act(releaseId, key, "recovery-download", reason)).json<any>();
    const body = { reason, deviceModel: firmwareScope.deviceModel, appId: "trace" };
    const reordered = new Request(`https://admin.example.com/api/admin/firmware/releases/${releaseId}/recovery-download`, {
      method: "POST", headers: { "Content-Type": "application/json", Accept: "application/json", "Idempotency-Key": key }, body: JSON.stringify(body) });
    const response = await firmwareReleaseAction(reordered, adminEnv, { email: "owner@example.com", requestId: crypto.randomUUID() }, releaseId, "recovery-download");
    expect(await response.json()).toEqual({ ...first, idempotent: true });
    const canonical = JSON.stringify({ body: { appId: "trace", deviceModel: firmwareScope.deviceModel, reason },
      method: "POST", path: `/api/admin/firmware/releases/${releaseId}/recovery-download` });
    const digest = new Uint8Array(await crypto.subtle.digest("SHA-256", new TextEncoder().encode(canonical)));
    const row = await env.DB.prepare("SELECT fingerprint,actor_canonical FROM firmware_admin_idempotency WHERE idempotency_key=?").bind(key).first<any>();
    expect(row).toEqual({ actor_canonical: "owner@example.com", fingerprint: Array.from(digest, byte => byte.toString(16).padStart(2, "0")).join("") });
    const audit = await env.DB.prepare("SELECT * FROM audit_logs WHERE request_id=?").bind(first.requestId).first();
    expect(JSON.stringify(audit)).not.toContain(key);
    expect(JSON.stringify(audit)).not.toContain(first.downloadUrl);
  });
  it("serializes mixed concurrent fingerprints and actions into one completed business effect", async () => {
    const { releaseId } = await registered(false); const key = crypto.randomUUID();
    const results = await Promise.allSettled(Array.from({ length: 12 }, (_, i) => act(releaseId, key,
      i % 2 ? "disable" : "recovery-download", `competing intent ${i}`)));
    expect(results.filter(r => r.status === "fulfilled")).toHaveLength(1);
    for (const result of results) if (result.status === "rejected") expect(result.reason).toMatchObject({ code: "IDEMPOTENCY_CONFLICT" });
    const row = await env.DB.prepare("SELECT request_id,state FROM firmware_admin_idempotency WHERE idempotency_key=?").bind(key).first<any>();
    expect(row.state).toBe("completed");
    expect(await count("SELECT count(*) AS n FROM audit_logs WHERE request_id=?", row.request_id)).toBe(1);
  });
  it.each(["disable", "recovery-download"].flatMap(action => ["request-first", "cleanup-first", "concurrent"].map(schedule => ({ action, schedule }))))(
    "preserves $action fingerprint outcomes and audit under $schedule expiry cleanup", async ({ action, schedule }) => {
      vi.spyOn(Date, "now").mockReturnValue(1800000000000);
      const { releaseId } = await registered(false); const key = crypto.randomUUID();
      const result = await (await act(releaseId, key, action as "disable" | "recovery-download")).json<any>();
      await cleanupFirmwareIdempotency(env.DB, 1800086399);
      expect(await count("SELECT count(*) AS n FROM firmware_admin_idempotency WHERE idempotency_key=?", key)).toBe(1);
      vi.mocked(Date.now).mockReturnValue(1800086400000);
      const requests = async () => {
        await expect(act(releaseId, key, action as "disable" | "recovery-download"))
          .rejects.toMatchObject({ code: "IDEMPOTENCY_RESULT_EXPIRED" });
        await expect(act(releaseId, key, action as "disable" | "recovery-download", "changed expired intent"))
          .rejects.toMatchObject({ code: "IDEMPOTENCY_CONFLICT" });
      };
      if (schedule === "request-first") { await requests(); await cleanupFirmwareIdempotency(env.DB); }
      if (schedule === "cleanup-first") { await cleanupFirmwareIdempotency(env.DB); await requests(); }
      if (schedule === "concurrent") await Promise.all([requests(), cleanupFirmwareIdempotency(env.DB)]);
      expect(await count("SELECT count(*) AS n FROM firmware_admin_idempotency WHERE idempotency_key=?", key)).toBe(0);
      expect(await count("SELECT count(*) AS n FROM firmware_admin_idempotency_tombstones WHERE idempotency_key=?", key)).toBe(1);
      expect(await count("SELECT count(*) AS n FROM audit_logs WHERE request_id=?", result.requestId)).toBe(1);
      expect(await count("SELECT count(*) AS n FROM firmware_admin_idempotency WHERE release_id=? AND state='pending'", releaseId)).toBe(0);
    });
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
  async function jwt(email: string, exp = Math.floor(Date.now() / 1000) + 3600, claims: Record<string, unknown> = {}) {
    const encode = (v: unknown) => b64(new TextEncoder().encode(JSON.stringify(v)));
    const message = `${encode({ alg: "RS256", kid: "p42" })}.${encode({ iss: issuer, aud: ["p42"], email, exp, ...claims })}`;
    return `${message}.${b64(new Uint8Array(await crypto.subtle.sign("RSASSA-PKCS1-v1_5", keys.privateKey, new TextEncoder().encode(message))))}`;
  }
  async function page(id: string, options: { email?: string; header?: Record<string, string>; reason?: string; extra?: object; key?: string;
    token?: string | null; jwksResponse?: () => Promise<Response>; route?: string[]; method?: string; query?: string; body?: unknown } = {}) {
    vi.stubGlobal("fetch", vi.fn(options.jwksResponse ?? (async () => Response.json({ keys: [{ ...jwk, kid: "p42" }] }))));
    const route = options.route ?? ["firmware", "releases", id, "recovery-download"];
    const method = options.method ?? "POST";
    const req = new Request(`https://admin.example.com/api/admin/${route.join("/")}${options.query ?? ""}`, { method, headers: {
      ...(options.token === null ? {} : { "CF-Access-Jwt-Assertion": options.token ?? await jwt(options.email ?? "owner@example.com") }),
      "Content-Type": "application/json", Accept: "application/json", Origin: "https://admin.example.com",
      "X-CSRF-Token": "csrf-fixture", Cookie: "trace_admin_csrf=csrf-fixture", "Idempotency-Key": options.key ?? crypto.randomUUID(), ...options.header
    }, body: ["GET", "HEAD"].includes(method) ? undefined : JSON.stringify(Object.hasOwn(options, "body") ? options.body : {
      appId: "trace", deviceModel: "e-track-at32f435", reason: options.reason ?? "approved self-test", ...options.extra }) });
    return onRequest({ request: req, params: { path: route }, env: { ...adminEnv, APP_ID: "trace", ENVIRONMENT: "dev",
      ACCESS_JWT_ISSUER: issuer, ACCESS_JWT_AUD: "p42", ADMIN_OWNER_EMAILS: "owner@example.com", ADMIN_PUBLISHER_EMAILS: "publisher@example.com",
      ADMIN_VIEWER_EMAILS: "viewer@example.com",
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
  it.each(["stable", "beta"].flatMap(channel => ["publish", "retract", "stop-latest", "resume-latest", "stop-downloads", "resume-downloads"]
    .map(action => ({ channel, action }))))("uses the fixed $channel/$action endpoint and exact result envelope", async ({ channel, action }) => {
    await freshChannel(channel); const target = await registered(false);
    if (action === "resume-latest") await changeChannel(channel, "stop_latest");
    if (action === "resume-downloads") await changeChannel(channel, "stop_downloads");
    const before = (await channelRow(channel))!; const requestId = crypto.randomUUID();
    const pointer = ["publish", "retract"].includes(action);
    const response = await page("unused", { route: ["firmware", "channels", channel, action], header: { "X-Request-Id": requestId },
      body: { ...firmwareScope, expectedRevision: before.revision, reason: "exact channel reason", ...(pointer ? { releaseId: target.releaseId } : {}) } });
    const body = await response.json<any>();
    expect(response.status, JSON.stringify(body)).toBe(200);
    expect(response.headers.get("X-Request-Id")).toBe(requestId);
    expect(body).toEqual({ ok: true, requestId, action: action.replaceAll("-", "_"), channel,
      revision: before.revision + 1, currentReleaseId: pointer ? target.releaseId : before.current_release_id,
      disableLatest: action === "stop-latest", disableDownloads: action === "stop-downloads", maintenanceMessage: null, idempotent: false });
    const audit = await env.DB.prepare("SELECT * FROM audit_logs WHERE request_id=?").bind(requestId).first<any>();
    expect(audit).toMatchObject({ reason: "exact channel reason", actor: "owner@example.com", action: body.action });
    expect(JSON.parse(audit.after_json).revision).toBe(body.revision);
  });
  it.each([
    ["stable", "owner", 200], ["stable", "publisher", 403], ["stable", "viewer", 403],
    ["beta", "owner", 200], ["beta", "publisher", 200], ["beta", "viewer", 403]
  ] as const)("enforces %s stop permissions for %s", async (channel, role, status) => {
    await freshChannel(channel); const before = (await channelRow(channel))!; const requestId = crypto.randomUUID();
    const response = await page("unused", { email: `${role}@example.com`, route: ["firmware", "channels", channel, "stop-downloads"],
      header: { "X-Request-Id": requestId }, body: { ...firmwareScope, expectedRevision: before.revision, reason: "role test" } });
    expect(response.status).toBe(status);
    if (status === 403) {
      expect(await response.json()).toMatchObject({ errorCode: "ROLE_FORBIDDEN", requestId });
      expect(await channelRow(channel)).toEqual(before);
      expect(await count("SELECT count(*) AS n FROM audit_logs WHERE request_id=?", requestId)).toBe(0);
    }
  });
  it.each(["releases", "channels"])("requires the exact scope and exposes the %s DTO to a viewer", async endpoint => {
    const current = await freshChannel();
    const response = await page("unused", { email: "viewer@example.com", route: ["firmware", endpoint], method: "GET",
      query: "?appId=trace&deviceModel=e-track-at32f435", header: { "X-Request-Id": "p43-viewer-read" } });
    expect(response.status).toBe(200);
    const body = await response.json<any>();
    expect(body.requestId).toBe(response.headers.get("X-Request-Id"));
    if (endpoint === "releases") expect(body.firmwareReleases.find((r: any) => r.releaseId === current.releaseId))
      .toMatchObject({ ...firmwareScope, versionCode: current.input.versionCode, state: "ready", archived: false, publishedChannels: ["stable"] });
    else expect(body.firmwareChannels.find((c: any) => c.channel === "stable"))
      .toMatchObject({ ...firmwareScope, currentReleaseId: current.releaseId, disableLatest: false, disableDownloads: false });
    const missing = await page("unused", { route: ["firmware", endpoint], method: "GET", query: "?appId=trace" });
    expect(missing.status).toBe(400);
    const extra = await page("unused", { route: ["firmware", endpoint], method: "GET",
      query: "?appId=trace&deviceModel=e-track-at32f435&deviceModel=e-track-at32f435" });
    expect(extra.status).toBe(400);
  });
  it.each([
    ["unknown field", { rollback: false }], ["reason missing", { reason: undefined }], ["reason blank", { reason: " \t\n" }],
    ["reason wrong type", { reason: 7 }], ["reason malformed Unicode", { reason: "\ud800" }],
    ["revision missing", { expectedRevision: undefined }], ["revision negative", { expectedRevision: -1 }],
    ["revision string", { expectedRevision: "1" }], ["revision fraction", { expectedRevision: 1.5 }],
    ["revision unsafe", { expectedRevision: Number.MAX_SAFE_INTEGER + 1 }], ["scope wrong type", { appId: 12 }],
    ["release path", { releaseId: "../other" }], ["release missing", { releaseId: undefined }],
    ["maintenance on retract", { maintenanceMessage: "not allowed" }]
  ] as const)("rejects channel %s without a channel or audit effect", async (_label, fields) => {
    const current = await freshChannel(); const before = (await channelRow("stable"))!; const requestId = crypto.randomUUID();
    const response = await page("unused", { route: ["firmware", "channels", "stable", "retract"], header: { "X-Request-Id": requestId },
      body: { ...firmwareScope, releaseId: current.releaseId, expectedRevision: before.revision, reason: "validation", ...fields } });
    expect(response.status).toBe(400);
    expect(await response.json()).toMatchObject({ errorCode: "INVALID_PARAMETER", requestId });
    expect(await channelRow("stable")).toEqual(before);
    expect(await count("SELECT count(*) AS n FROM audit_logs WHERE request_id=?", requestId)).toBe(0);
  });
  it.each([
    ["GET", "retract"], ["PUT", "publish"], ["DELETE", "stop-latest"], ["OPTIONS", "resume-downloads"],
    ["POST", "rollback"], ["POST", "stop_latest"], ["POST", "resume"]
  ])("rejects unsupported method/endpoint %s %s instead of exposing an alias", async (method, action) => {
    const response = await page("unused", { route: ["firmware", "channels", "stable", action], method });
    expect(response.status).toBe(400);
    expect(await response.json()).toMatchObject({ errorCode: "INVALID_PARAMETER" });
  });
  it.each(["Stable", "nightly", " stable "])("rejects noncanonical channel %s", async channel => {
    const response = await page("unused", { route: ["firmware", "channels", channel, "publish"] });
    expect(response.status).toBe(400);
  });
  it.each([
    ["Content-Type", "text/plain"], ["Content-Type", ""], ["Accept", "*/*"], ["Accept", "application/json;q=0"],
    ["Accept", "application/json;q=0.000"], ["Accept", ""]
  ])("rejects unacceptable %s=%s before mutation", async (header, value) => {
    const current = await freshChannel(); const before = (await channelRow("stable"))!;
    const response = await page("unused", { route: ["firmware", "channels", "stable", "retract"], header: { [header]: value },
      body: { ...firmwareScope, releaseId: current.releaseId, expectedRevision: before.revision, reason: "header test" } });
    expect(response.status).toBe(400);
    expect(await channelRow("stable")).toEqual(before);
  });
  it.each(["draft", "disabled", "archived", "not found"] as const)("maps the retract target %s state without partial effects", async state => {
    await freshChannel(); const target = state === "draft" ? await draft() : await registered(false);
    if (state === "disabled") await act(target.releaseId, crypto.randomUUID(), "disable");
    if (state === "archived") await env.DB.prepare("UPDATE firmware_releases SET archived=1 WHERE id=?").bind(target.releaseId).run();
    const before = (await channelRow("stable"))!; const requestId = crypto.randomUUID();
    const response = await page("unused", { route: ["firmware", "channels", "stable", "retract"], header: { "X-Request-Id": requestId },
      body: { ...firmwareScope, releaseId: state === "not found" ? "no-such-release" : target.releaseId, expectedRevision: before.revision, reason: "state gate" } });
    const expected = { draft: [409, "RELEASE_NOT_READY"], disabled: [410, "RELEASE_DISABLED"],
      archived: [410, "RELEASE_ARCHIVED"], "not found": [404, "RELEASE_NOT_FOUND"] }[state];
    expect(response.status).toBe(expected[0]);
    expect(await response.json()).toMatchObject({ errorCode: expected[1], requestId });
    expect(await channelRow("stable")).toEqual(before);
    expect(await count("SELECT count(*) AS n FROM audit_logs WHERE request_id=?", requestId)).toBe(0);
  });
  it("uses the fixed disable endpoint with reference protection and key-based replay", async () => {
    const current = await freshChannel();
    const inUse = await page(current.releaseId, { route: ["firmware", "releases", current.releaseId, "disable"] });
    expect(inUse.status).toBe(409); expect(await inUse.json()).toMatchObject({ errorCode: "RELEASE_IN_USE" });
    const target = await registered(false); const key = crypto.randomUUID();
    const route = ["firmware", "releases", target.releaseId, "disable"];
    const first = await page(target.releaseId, { route, key }); const body = await first.json<any>();
    expect(first.status).toBe(200);
    expect(body).toEqual({ ok: true, requestId: expect.any(String), action: "disable_release", releaseId: target.releaseId, state: "disabled", idempotent: false });
    const replay = await page(target.releaseId, { route, key });
    expect(await replay.json()).toEqual({ ...body, idempotent: true });
    expect(replay.headers.get("X-Request-Id")).toBe(body.requestId);
    expect(await count("SELECT count(*) AS n FROM audit_logs WHERE request_id=?", body.requestId)).toBe(1);
  });
  it.each([
    { iss: "https://wrong.cloudflareaccess.com" }, { aud: ["wrong-audience"] }, { nbf: 4000000000 }, { iat: 4000000000 },
    { nbf: "0" }, { iat: "0" }, { iat: null }, { exp: "4000000000" }, { exp: null }
  ])("rejects a correctly signed but invalid Access claim %j", async claims => {
    const response = await page("unqueried-release", { token: await jwt("owner@example.com", Math.floor(Date.now() / 1000) + 3600, claims) });
    expect(response.status).toBe(401);
    expect(await response.json()).toMatchObject({ errorCode: "TOKEN_INVALID" });
  });
  it("never promotes a publisher from a spoofed email header or JWT role claim", async () => {
    const response = await page("unused", { route: ["firmware", "channels", "stable", "stop-latest"],
      token: await jwt("publisher@example.com", Math.floor(Date.now() / 1000) + 3600, { role: "owner" }),
      header: { "Cf-Access-Authenticated-User-Email": "owner@example.com" } });
    expect(response.status).toBe(403); expect(await response.json()).toMatchObject({ errorCode: "ROLE_FORBIDDEN" });
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
