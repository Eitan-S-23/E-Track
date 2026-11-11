import { env } from "cloudflare:workers";
import { afterEach, describe, expect, it, vi } from "vitest";
import { firmwareAssets } from "../src/firmware";
import { firmwareReleaseAction } from "../src/firmware_admin";
import { deleteFirmwareFiles } from "../src/firmware_delete";
import { draft, registered } from "./firmware-fixture";

afterEach(() => vi.restoreAllMocks());
const actor = () => ({ email: "owner@example.com", requestId: crypto.randomUUID() });
function request(id: string, action: string, extra: object = {}) {
  return new Request(`https://admin.example.com/api/admin/firmware/releases/${id}/${action}`, {
    method: "POST", headers: { "Content-Type": "application/json", Accept: "application/json", "Idempotency-Key": crypto.randomUUID() },
    body: JSON.stringify({ appId: "trace", deviceModel: "e-track-at32f435", reason: "delete disposable test files", ...extra }) });
}
const remove = (id: string, extra?: object) => deleteFirmwareFiles(request(id, "delete", extra), env, actor(), id);
const disable = (id: string) => firmwareReleaseAction(request(id, "disable"), env, actor(), id, "disable");
const row = (id: string) => env.DB.prepare("SELECT * FROM firmware_releases WHERE id=?").bind(id).first();
const audits = (id: string) => env.DB.prepare("SELECT action FROM audit_logs WHERE target_id=? ORDER BY rowid").bind(id).all();

describe("Unified Admin firmware file deletion", () => {
  it("requires an explicitly disabled, unreferenced release and a nonblank reason", async () => {
    const published = await registered();
    const unreferenced = await registered(false);
    const erase = vi.spyOn(env.RELEASES_BUCKET, "delete");
    await expect(remove(published.releaseId)).rejects.toMatchObject({ code: "RELEASE_IN_USE" });
    await expect(remove(unreferenced.releaseId)).rejects.toMatchObject({ code: "RELEASE_CONFLICT" });
    await disable(unreferenced.releaseId);
    await expect(remove(unreferenced.releaseId, { reason: " " })).rejects.toMatchObject({ code: "INVALID_PARAMETER" });
    await expect(remove(unreferenced.releaseId, { deviceModel: "wrong-model" })).rejects.toMatchObject({ code: "INVALID_PARAMETER" });
    expect(erase).not.toHaveBeenCalled();
  });

  it("deletes only the selected files, retains identities/history and makes repeat reads deterministic", async () => {
    const selected = await registered(false);
    const other = await registered(false);
    await disable(selected.releaseId);
    const before = await row(selected.releaseId);
    const assets = await firmwareAssets(env.DB, selected.releaseId);
    const channels = (await env.DB.prepare("SELECT * FROM channels ORDER BY id").all()).results;
    const response = await remove(selected.releaseId);
    expect(await response.json()).toMatchObject({ action: "delete_files", archived: true, retainedHistory: true, idempotent: false });
    expect(await row(selected.releaseId)).toMatchObject({ ...before, archived: 1, updated_at: expect.any(String) });
    const after = await firmwareAssets(env.DB, selected.releaseId);
    expect(after).toEqual(assets.map(a => ({ ...a, r2_state: "r2_deleted", updated_at: expect.any(String) })));
    for (const asset of assets) expect(await env.RELEASES_BUCKET.head(asset.r2_key!)).toBeNull();
    for (const asset of other.input.assets) expect(await env.RELEASES_BUCKET.head(asset.r2Key)).not.toBeNull();
    expect((await env.DB.prepare("SELECT * FROM channels ORDER BY id").all()).results).toEqual(channels);
    const history = await audits(selected.releaseId);
    expect(history.results.filter(a => a.action === "archive_for_file_deletion")).toHaveLength(1);
    expect(history.results.filter(a => a.action === "delete_firmware_files")).toHaveLength(1);
    expect(await (await remove(selected.releaseId)).json()).toMatchObject({ idempotent: true });
    expect((await audits(selected.releaseId)).results).toEqual(history.results);
    await expect(env.DB.prepare("DELETE FROM firmware_releases WHERE id=?").bind(selected.releaseId).run()).rejects.toThrow();
    await expect(env.DB.prepare("UPDATE firmware_releases SET archived=0 WHERE id=?").bind(selected.releaseId).run()).rejects.toThrow();
    await expect(env.DB.prepare("UPDATE firmware_release_assets SET r2_state='available' WHERE release_id=?")
      .bind(selected.releaseId).run()).rejects.toThrow();
  });

  it("archives before R2 deletion and resumes after a partial failure without repeating archive audit", async () => {
    const selected = await registered(false);
    await disable(selected.releaseId);
    const assets = await firmwareAssets(env.DB, selected.releaseId);
    const erase = env.RELEASES_BUCKET.delete.bind(env.RELEASES_BUCKET);
    let attempts = 0;
    const spy = vi.spyOn(env.RELEASES_BUCKET, "delete").mockImplementation(async key => {
      expect(await row(selected.releaseId)).toMatchObject({ archived: 1, state: "disabled" });
      if (++attempts === 2) throw new Error("injected R2 failure");
      return erase(key);
    });
    await expect(remove(selected.releaseId)).rejects.toMatchObject({ code: "BACKEND_UNAVAILABLE" });
    expect(await env.RELEASES_BUCKET.head(assets[0].r2_key!)).toBeNull();
    expect(await env.RELEASES_BUCKET.head(assets[1].r2_key!)).not.toBeNull();
    expect((await firmwareAssets(env.DB, selected.releaseId)).every(a => a.r2_state !== "r2_deleted")).toBe(true);
    spy.mockRestore();
    expect((await remove(selected.releaseId)).status).toBe(200);
    expect((await audits(selected.releaseId)).results.filter(a => a.action === "archive_for_file_deletion")).toHaveLength(1);
    expect((await firmwareAssets(env.DB, selected.releaseId)).every(a => a.r2_state === "r2_deleted")).toBe(true);
  });

  it("does not delete anything when R2 identity changed", async () => {
    const selected = await registered(false);
    await disable(selected.releaseId);
    await env.RELEASES_BUCKET.put(selected.input.assets[1].r2Key, "unexpected replacement");
    const erase = vi.spyOn(env.RELEASES_BUCKET, "delete");
    await expect(remove(selected.releaseId)).rejects.toMatchObject({ code: "R2_OBJECT_CONFLICT" });
    expect(erase).not.toHaveBeenCalled();
    expect(await row(selected.releaseId)).toMatchObject({ archived: 0 });
  });

  it("rolls back a rejected archive audit before deleting files", async () => {
    const selected = await registered(false);
    await disable(selected.releaseId);
    const erase = vi.spyOn(env.RELEASES_BUCKET, "delete");
    await env.DB.prepare(`CREATE TRIGGER test_delete_audit_failure BEFORE INSERT ON audit_logs
      WHEN NEW.action='archive_for_file_deletion' BEGIN SELECT RAISE(ABORT,'injected audit failure'); END`).run();
    try {
      await expect(remove(selected.releaseId)).rejects.toMatchObject({ code: "BACKEND_UNAVAILABLE" });
      expect(await row(selected.releaseId)).toMatchObject({ archived: 0 });
      expect(erase).not.toHaveBeenCalled();
    } finally { await env.DB.prepare("DROP TRIGGER test_delete_audit_failure").run(); }
  });

  it("can archive an empty disabled draft but cannot attach files afterward", async () => {
    const selected = await draft();
    await disable(selected.releaseId);
    expect((await remove(selected.releaseId)).status).toBe(200);
    await expect(env.DB.prepare(`INSERT INTO firmware_release_assets
      (id,release_id,kind,file_name,sha256,size_bytes,base_image_sha256,base_vcode,github_url)
      VALUES (?,?,'full','unexpected.etu',?,10,?,0,?)`)
      .bind(crypto.randomUUID(), selected.releaseId, "a".repeat(64), "", selected.input.assets[0].githubUrl)
      .run()).rejects.toThrow("disabled firmware asset set is sealed");
  });

  it("refuses an App object key even when it is present on a disabled firmware draft", async () => {
    const selected = await draft();
    const key = "trace/android/retained-app.apk";
    await env.RELEASES_BUCKET.put(key, "retained App");
    await env.DB.prepare(`INSERT INTO firmware_release_assets
      (id,release_id,kind,file_name,sha256,size_bytes,base_image_sha256,base_vcode,r2_key,github_url)
      VALUES (?,?,'full','unexpected.etu',?,12,'',0,?,?)`)
      .bind(crypto.randomUUID(), selected.releaseId, "a".repeat(64), key, selected.input.assets[0].githubUrl).run();
    await disable(selected.releaseId);
    const erase = vi.spyOn(env.RELEASES_BUCKET, "delete");
    await expect(remove(selected.releaseId)).rejects.toMatchObject({ code: "R2_OBJECT_CONFLICT" });
    expect(erase).not.toHaveBeenCalled();
    expect(await env.RELEASES_BUCKET.head(key)).not.toBeNull();
  });
});
