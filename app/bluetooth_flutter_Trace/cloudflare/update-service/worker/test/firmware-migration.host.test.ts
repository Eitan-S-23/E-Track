import { createHash } from "node:crypto";
import { readFileSync } from "node:fs";
import { env } from "cloudflare:workers";
import { afterEach, describe, expect, it } from "vitest";
import { SqliteD1 } from "./host/sqlite-d1";
import { backfillFirmwareV2 } from "../../scripts/backfill-firmware-v2.mjs";
import { canonicalJson } from "../../scripts/firmware-schema.mjs";
import { handleFirmwareLatest } from "../src/firmware";
import { firmwareReleaseAction } from "../src/firmware_admin";
import { bytesFor } from "./firmware-fixture";

const hash = (value: string | Uint8Array) => createHash("sha256").update(value).digest("hex");
const files = ["0001_init.sql", "0002_patch_formats.sql", "0003_firmware_releases.sql", "0004_announcements.sql", "0005_firmware_multi_asset.sql"];
const sql = files.map((name) => readFileSync(new URL(`../../migrations/${name}`, import.meta.url), "utf8"));
const open: SqliteD1[] = [];
afterEach(() => { for (const db of open.splice(0)) db.sqlite.close(); });

async function setup(states = ["published"]) {
  const db = new SqliteD1(); open.push(db);
  for (const migration of sql.slice(0, 4)) db.migrate(migration);
  db.sqlite.exec("INSERT INTO apps(id,name) VALUES ('trace','trace')");
  const records: any[] = [];
  const artifacts = new Map<string, Uint8Array>();
  for (const [i, state] of states.entries()) {
    const id = `legacy-${i}`;
    const version = `2.8.${i + 1}`;
    const tag = `mcu-e-track-at32f435-v${version}`;
    const file = `e-track-at32f435-v${version}-full.etu`;
    const locator = `https://github.com/Eitan-S-23/Trace/releases/download/${tag}/${file}`;
    const imageLocator = `https://github.com/Eitan-S-23/Trace/releases/download/${tag}/app.bin`;
    const evidenceLocator = `https://github.com/Eitan-S-23/Trace/releases/download/${tag}/verification.json`;
    const key = `trace/firmware/e-track-at32f435/${20801 + i}-${tag}/${file}`;
    const body = bytesFor("full");
    await env.RELEASES_BUCKET.put(key, body, { customMetadata: { sha256: hash(body), kind: "full" } });
    await db.prepare(`INSERT INTO firmware_releases (id,app_id,device_model,version_name,version_code,release_tag,
      commit_sha,run_id,state,release_notes,file_name,sha256,size_bytes,r2_key,r2_state,github_url,target_hardware,created_at)
      VALUES (?,'trace','e-track-at32f435',?,?,?,?,?,?,'legacy notes',?,?,?,?,'available',?,'AT32F435RGT7','2025-01-01 00:00:00')`)
      .bind(id, version, 20801 + i, tag, "1".repeat(40), `legacy-run-${i}`, state === "disabled" ? "disabled" : "candidate",
        file, hash(body), body.length, key, locator).run();
    if (state === "published") await db.prepare(`INSERT INTO firmware_channels
      (id,app_id,device_model,name,current_release_id,revision,last_action)
      VALUES ('old-stable','trace','e-track-at32f435','stable',?,9,'rollback')`).bind(id).run();
    const record = { releaseId: id, appId: "trace", deviceModel: "e-track-at32f435", releaseTag: tag,
      runId: `legacy-run-${i}`, commitSha: "1".repeat(40), versionName: version, versionCode: 20801 + i,
      targetImageSha256: hash(bytesFor("final-image")), hardwareRevision: 1, layoutId: 1, minBootVersion: 1,
      minProtocolVersion: 1, targetHardware: "AT32F435RGT7", artifact: { locator, sha256: hash(body), sizeBytes: body.length },
      image: { locator: imageLocator, sha256: hash(bytesFor("final-image")), imageLength: bytesFor("final-image").length },
      verification: { toolVersion: "p42-synthetic-verifier-v1", evidenceLocator, evidenceSha256: hash(bytesFor("evidence")),
        verifiedBy: "fixture-reviewer", verifiedAt: "2026-10-14T00:00:00Z" } };
    records.push(record);
    artifacts.set(locator, body); artifacts.set(imageLocator, bytesFor("final-image")); artifacts.set(evidenceLocator, bytesFor("evidence"));
  }
  const before = db.sqlite.prepare("SELECT * FROM firmware_releases ORDER BY id").all();
  const manifest = { manifestSchemaVersion: 1, approvedBy: { migrationOwner: "fixture-migration-owner", otaReleaseReviewer: "fixture-release-reviewer" }, records };
  function options() {
    return { db: db as unknown as D1Database, bucket: env.RELEASES_BUCKET, manifest,
      approvedManifestSha256: hash(canonicalJson(manifest)), readArtifact: async (locator: string) => {
        const bytes = artifacts.get(locator); if (!bytes) throw new Error("Artifact unavailable"); return bytes;
      } };
  }
  return { db, manifest, before, artifacts, options };
}

describe("P4-2 real SQLite forward migration and controlled backfill", () => {
  it("applies the full migration chain to an empty database and emits the actual schema", async () => {
    const db = new SqliteD1(); open.push(db);
    for (const migration of sql) db.migrate(migration);
    expect(db.sqlite.prepare("PRAGMA foreign_key_check").all()).toHaveLength(0);
    console.info("SQLITE_VERSION", db.sqlite.prepare("SELECT sqlite_version() AS version").get());
    console.info("P42_SCHEMA_DUMP", db.sqlite.prepare("SELECT type,name,sql FROM sqlite_master WHERE name LIKE 'firmware_%' OR name LIKE 'idx_firmware_%' ORDER BY type,name").all());
  });
  it("preserves all legacy bytes and isolates the unresolved channel without changing revision", async () => {
    const s = await setup(); s.db.migrate(sql[4]);
    expect(s.db.sqlite.prepare("SELECT * FROM firmware_releases_legacy ORDER BY id").all()).toEqual(s.before);
    expect(s.db.sqlite.prepare("SELECT * FROM firmware_channels").get()).toMatchObject({ current_release_id: null,
      legacy_current_release_id: "legacy-0", revision: 9, last_action: "retract" });
    const query = "appId=trace&deviceModel=e-track-at32f435&channel=stable&currentVersionCode=1&currentImageSha=" + "1".repeat(64)
      + "&hardwareRevision=1&layoutId=1&bootVersion=1&protocolVersion=1&appVersionCode=100";
    await expect(handleFirmwareLatest(new Request(`https://example.com/api/public/firmware/latest?${query}`),
      { ...env, DB: s.db as unknown as D1Database }, "legacy-test")).rejects.toMatchObject({ code: "BACKEND_UNAVAILABLE" });
  });
  it("verifies artifacts/raw image/R2, safely maps published ready, preserves disabled/draft and replays without extra rows", async () => {
    const s = await setup(["published", "disabled", "unpublished"]); s.db.migrate(sql[4]);
    expect(await backfillFirmwareV2(s.options())).toMatchObject({ migrated: ["legacy-0", "legacy-1", "legacy-2"], quarantined: [] });
    const rows = s.db.sqlite.prepare("SELECT id,state,target_image_sha256,created_at FROM firmware_releases ORDER BY id").all();
    expect(rows.map((r) => r.state)).toEqual(["ready", "disabled", "draft"]);
    expect(rows.every((r) => r.target_image_sha256 === hash(bytesFor("final-image")))).toBe(true);
    expect(rows.every((r) => r.created_at === "2025-01-01 00:00:00")).toBe(true);
    expect(s.db.sqlite.prepare("SELECT current_release_id,legacy_current_release_id,revision,last_action FROM firmware_channels").get())
      .toEqual({ current_release_id: "legacy-0", legacy_current_release_id: null, revision: 9, last_action: "retract" });
    expect(await backfillFirmwareV2(s.options())).toMatchObject({ migrated: [], reused: ["legacy-0", "legacy-1", "legacy-2"] });
    expect(s.db.sqlite.prepare("SELECT count(*) AS n FROM firmware_release_assets").get()!.n).toBe(3);
    expect(s.db.sqlite.prepare("SELECT count(*) AS n FROM audit_logs").get()!.n).toBe(3);
    console.info("BACKFILL_BEFORE", s.before);
    console.info("BACKFILL_AFTER", rows, s.db.sqlite.prepare("SELECT kind,base_image_sha256,base_vcode FROM firmware_release_assets").all());
  });
  it.each(["missing record", "missing identity", "bad schema", "missing approval", "legacy mismatch", "raw mismatch", "artifact missing", "evidence mismatch"])
    ("stops before every write on published %s", async (caseName) => {
      const s = await setup(["unpublished", "published"]); s.db.migrate(sql[4]);
      const r = s.manifest.records[1];
      if (caseName === "missing record") s.manifest.records.pop();
      if (caseName === "missing identity") delete r.hardwareRevision;
      if (caseName === "bad schema") s.manifest.manifestSchemaVersion = 2;
      if (caseName === "missing approval") s.manifest.approvedBy.otaReleaseReviewer = "";
      if (caseName === "legacy mismatch") r.commitSha = "2".repeat(40);
      if (caseName === "raw mismatch") s.artifacts.set(r.image.locator, bytesFor("full"));
      if (caseName === "artifact missing") s.artifacts.delete(r.artifact.locator);
      if (caseName === "evidence mismatch") s.artifacts.set(r.verification.evidenceLocator, bytesFor("full"));
      await expect(backfillFirmwareV2(s.options())).rejects.toThrow();
      expect(s.db.sqlite.prepare("SELECT count(*) AS n FROM firmware_releases").get()!.n).toBe(0);
      expect(s.db.sqlite.prepare("SELECT count(*) AS n FROM firmware_backfill_manifests").get()!.n).toBe(0);
      expect(s.db.sqlite.prepare("SELECT * FROM firmware_releases_legacy ORDER BY id").all()).toEqual(s.before);
    });
  it("isolates unverifiable unpublished rows without inventing zero/default identity", async () => {
    const s = await setup(["unpublished"]); s.db.migrate(sql[4]);
    delete s.manifest.records[0].targetImageSha256;
    const result = await backfillFirmwareV2(s.options());
    expect(result.quarantined).toHaveLength(1);
    expect(result.migrated).toHaveLength(0);
    expect(s.db.sqlite.prepare("SELECT count(*) AS n FROM firmware_releases").get()!.n).toBe(0);
  });
  it("rejects a changed manifest and an unapproved digest without overwriting identity", async () => {
    const s = await setup(); s.db.migrate(sql[4]);
    await expect(backfillFirmwareV2({ ...s.options(), approvedManifestSha256: "0".repeat(64) })).rejects.toThrow(/digest/);
    await backfillFirmwareV2(s.options());
    s.manifest.records[0].hardwareRevision = 2;
    await expect(backfillFirmwareV2(s.options())).rejects.toThrow(/BACKFILL_CONFLICT/);
    expect(s.db.sqlite.prepare("SELECT hardware_rev FROM firmware_releases").get()!.hardware_rev).toBe(1);
  });
  it("rejects missing recovery on a legitimate full-only backfilled release", async () => {
    const s = await setup(); s.db.migrate(sql[4]); await backfillFirmwareV2(s.options());
    const request = new Request("https://admin.example.com/api/admin/firmware/releases/legacy-0/recovery-download", {
      method: "POST", headers: { "Content-Type": "application/json", Accept: "application/json", "Idempotency-Key": crypto.randomUUID() },
      body: JSON.stringify({ appId: "trace", deviceModel: "e-track-at32f435", reason: "self-test" }) });
    await expect(firmwareReleaseAction(request, { ...env, DB: s.db as unknown as D1Database, FIRMWARE_DOWNLOAD_ORIGIN: "https://example.com" },
      { email: "owner@example.com", requestId: "missing-recovery" }, "legacy-0", "recovery-download"))
      .rejects.toMatchObject({ code: "RECOVERY_ASSET_UNAVAILABLE" });
  });
  it("cannot map a published legacy row ready when its R2 object is gone", async () => {
    const s = await setup(); s.db.migrate(sql[4]);
    await env.RELEASES_BUCKET.delete(String(s.before[0].r2_key));
    await expect(backfillFirmwareV2(s.options())).rejects.toThrow(/LEGACY_UNVERIFIED/);
    expect(s.db.sqlite.prepare("SELECT count(*) AS n FROM firmware_releases").get()!.n).toBe(0);
  });
  it("rolls back all schema/data changes when the forward migration fails", async () => {
    const s = await setup();
    expect(() => s.db.migrate(sql[4] + "\nSELECT * FROM missing_table_to_inject_failure;")).toThrow();
    expect(s.db.sqlite.prepare("SELECT * FROM firmware_releases ORDER BY id").all()).toEqual(s.before);
    expect(s.db.sqlite.prepare("SELECT name FROM sqlite_master WHERE name='firmware_releases_legacy'").get()).toBeUndefined();
    expect(s.db.sqlite.prepare("PRAGMA table_info(audit_logs)").all().some((r) => r.name === "reason")).toBe(false);
  });
  it("rolls back the complete backfill when its audit fails", async () => {
    const s = await setup(); s.db.migrate(sql[4]);
    s.db.sqlite.exec("CREATE TRIGGER fail_backfill BEFORE INSERT ON audit_logs BEGIN SELECT RAISE(ABORT,'injected audit failure'); END;");
    await expect(backfillFirmwareV2(s.options())).rejects.toThrow();
    expect(s.db.sqlite.prepare("SELECT count(*) AS n FROM firmware_release_assets").get()!.n).toBe(0);
    expect(s.db.sqlite.prepare("SELECT legacy_current_release_id FROM firmware_channels").get()!.legacy_current_release_id).toBe("legacy-0");
  });
});
