import { env } from "cloudflare:workers";
import { applyD1Migrations, createExecutionContext } from "cloudflare:test";
import { describe, expect, it, vi } from "vitest";
import worker from "../src/index";
import { firmwareReleaseInsert } from "../src/firmware";
import { canonicalJson } from "../../scripts/firmware-schema.mjs";
import { metadata } from "./firmware-fixture";

function call(value: unknown, headers: Record<string, string> = {}, db = env.DB) {
  return worker.fetch(new Request("https://example.com/api/ci/firmware/preflight", { method: "POST",
    headers: { Authorization: "Bearer test-deploy-token", Accept: "application/json", "Content-Type": "application/json", ...headers },
    body: JSON.stringify(value) }), { ...env, ENVIRONMENT: "staging", DB: db }, createExecutionContext());
}
const envelope = (input = metadata()) => ({ schemaVersion: 1, environment: "staging", metadata: input });
async function snapshot(db = env.DB) {
  const result: Record<string, unknown> = {};
  for (const table of ["firmware_releases", "firmware_release_assets", "firmware_channels", "firmware_releases_legacy", "audit_logs"]) {
    result[table] = (await db.prepare(`SELECT * FROM ${table} ORDER BY id`).all()).results;
  }
  return result;
}

describe("authenticated fixed-query firmware preflight", () => {
  it.each(["", "Bearer wrong-token", "Basic invalid", "Bearer test-deploy-token,other"])("rejects %s before parsing or querying", async Authorization => {
    const prepare = vi.spyOn(env.DB, "prepare");
    try {
      const response = await call({ sql: "SELECT secret FROM anything" }, { Authorization });
      expect(response.status).toBe(401); expect(prepare).not.toHaveBeenCalled();
    } finally { prepare.mockRestore(); }
  });
  it.each(["sql", "databaseId", "bucketName", "accountId"])("rejects client-controlled %s before DB access", async field => {
    const prepare = vi.spyOn(env.DB, "prepare");
    try {
      expect((await call({ ...envelope(), [field]: "injected" })).status).toBe(400);
      expect(prepare).not.toHaveBeenCalled();
    } finally { prepare.mockRestore(); }
  });
  it("rejects mixed environment before querying and returns no authorization data", async () => {
    const prepare = vi.spyOn(env.DB, "prepare");
    try {
      const response = await call({ ...envelope(), environment: "prod" });
      expect(response.status).toBe(409); expect(prepare).not.toHaveBeenCalled();
      expect(await response.text()).not.toContain("test-deploy-token");
    } finally { prepare.mockRestore(); }
  });
  it("executes the three SELECTs, binds the response identity and has no business writes", async () => {
    const before = await snapshot(); const prepare = vi.spyOn(env.DB, "prepare");
    let response: Response;
    try {
      response = await call(envelope(), { "X-Request-Id": "p44-preflight-original" });
      expect(response.status).toBe(200);
      expect(prepare.mock.calls).toHaveLength(3);
      expect(prepare.mock.calls.every(([sql]) => sql.startsWith("SELECT "))).toBe(true);
    } finally { prepare.mockRestore(); }
    expect(await response!.json()).toMatchObject({ ok: true, schemaVersion: 1, environment: "staging", requestId: "p44-preflight-original", unresolvedLegacyChannels: 0 });
    expect(response!.headers.get("X-Request-Id")).toBe("p44-preflight-original");
    expect(await snapshot()).toEqual(before);
  });
  it("preserves same-version canonical replay and blocks lower/different identities", async () => {
    const input = metadata();
    await env.DB.prepare("INSERT OR IGNORE INTO apps(id,name) VALUES ('trace','trace')").run();
    await firmwareReleaseInsert(env.DB, input, crypto.randomUUID(), canonicalJson(input)).run();
    const before = await snapshot();
    expect((await call(envelope(input))).status).toBe(200);
    expect((await call(envelope({ ...input, releaseNotes: "different identity" }))).status).toBe(409);
    // A schema-valid older candidate is lower than the inserted current release.
    const older = metadata();
    const newer = metadata();
    await firmwareReleaseInsert(env.DB, newer, crypto.randomUUID(), canonicalJson(newer)).run();
    expect((await call(envelope(older))).status).toBe(409);
    const after = await snapshot();
    expect(after.audit_logs).toEqual(before.audit_logs);
    expect(after.firmware_channels).toEqual(before.firmware_channels);
  });
  it("blocks migrated unresolved pointers and legacy maximum on a native isolated D1 fixture", async () => {
    const db = env.PREFLIGHT_LEGACY_DB;
    await applyD1Migrations(db, env.TEST_MIGRATIONS.slice(0, 4));
    const input = metadata(); const asset = input.assets[0];
    await db.prepare("INSERT INTO apps(id,name) VALUES ('trace','trace')").run();
    await db.prepare(`INSERT INTO firmware_releases (id,app_id,device_model,version_name,version_code,release_tag,commit_sha,run_id,file_name,sha256,size_bytes,github_url)
      VALUES ('legacy','trace',?,?,?,?,?,?,?,?,?,?)`).bind(input.deviceModel, input.versionName, input.versionCode,
      input.releaseTag, input.commitSha, input.runId, asset.fileName, asset.sha256, asset.sizeBytes, asset.githubUrl).run();
    await db.prepare("INSERT INTO firmware_channels(id,app_id,device_model,name,current_release_id) VALUES ('legacy-channel','trace',?,'stable','legacy')").bind(input.deviceModel).run();
    await applyD1Migrations(db, env.TEST_MIGRATIONS.slice(4));
    const before = await snapshot(db);
    expect((await call(envelope(metadata()), {}, db)).status).toBe(409);
    expect(await snapshot(db)).toEqual(before);
    // Fixture setup removes the pointer; the handler must still reject the legacy maximum.
    await db.prepare("DELETE FROM firmware_channels WHERE id='legacy-channel'").run();
    const withoutPointer = await snapshot(db);
    expect((await call(envelope(input), {}, db)).status).toBe(409);
    expect(await snapshot(db)).toEqual(withoutPointer);
  });
  it("sanitizes a backend exception instead of returning SQL or values", async () => {
    const prepare = vi.spyOn(env.DB, "prepare").mockImplementation(() => { throw new Error("private SQL credential value"); });
    try {
      const response = await call(envelope()); expect(response.status).toBe(503);
      expect(await response.text()).not.toContain("private SQL");
    } finally { prepare.mockRestore(); }
  });
});
