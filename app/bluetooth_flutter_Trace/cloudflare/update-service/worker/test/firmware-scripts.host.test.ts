import { env } from "cloudflare:workers";
import { SELF } from "cloudflare:test";
import { mkdir, mkdtemp, readFile, writeFile } from "node:fs/promises";
import { spawnSync } from "node:child_process";
import { fileURLToPath } from "node:url";
import path from "node:path";
import { describe, expect, it, vi } from "vitest";
import { buildFirmwareMetadata } from "../../scripts/build-firmware-release-metadata.mjs";
import { uploadFirmwareAsset } from "../../scripts/upload-firmware-r2-asset.mjs";
import { registerFirmware } from "../../scripts/register-firmware-release.mjs";
import { outputPath, projectRoot } from "../../scripts/firmware-cli.mjs";
import { canonicalJson, contentDigest, parseFirmwareRegistration } from "../../scripts/firmware-schema.mjs";
import { bytesFor, metadata, SCHEMA_FIXTURE, uploadFixture } from "./firmware-fixture";

const root = projectRoot();
const scripts = fileURLToPath(new URL("../../scripts/", import.meta.url));
const worker = fileURLToPath(new URL("../", import.meta.url));
async function files() {
  const base = outputPath(root, path.join(root, ".cache", "p4-2-script-fixtures"));
  await mkdir(base, { recursive: true });
  const dir = await mkdtemp(path.join(base, "case-"));
  for (const asset of SCHEMA_FIXTURE.assets) await writeFile(outputPath(root, path.join(dir, asset.fileName)), bytesFor(asset.kind));
  await writeFile(outputPath(root, path.join(dir, "app.bin")), bytesFor("final-image"));
  await writeFile(outputPath(root, path.join(dir, "patch-bases.json")), JSON.stringify([{ baseImageSha256: "11".repeat(32), baseVersionCode: 20800 }]));
  return dir;
}

describe("P4-2 canonical metadata / upload / register scripts", () => {
  it("builds the same canonical v2 fixture from actual files and keeps R2 unverified", async () => {
    const dir = await files();
    const { assets, schemaVersion, appId, deviceModel, versionCode, targetImageSha256, transport, isFormalRelease, ...release } = SCHEMA_FIXTURE;
    const result = await buildFirmwareMetadata({ release, assetsDir: dir, finalImage: path.join(dir, "app.bin"),
      patchBases: [{ baseImageSha256: "11".repeat(32), baseVersionCode: 20800 }] });
    expect(canonicalJson(result)).toBe(canonicalJson({ ...SCHEMA_FIXTURE, assets: assets.map((a) => ({ ...a, r2Verified: false })) }));
    expect(result.targetImageSha256).not.toBe(result.assets[0].sha256);
    await writeFile(outputPath(root, path.join(dir, "metadata-built.json")), canonicalJson(result));
  });
  it("executes the builder CLI, preserves source files and returns a real exit code", async () => {
    const dir = await files(); const output = path.join(dir, "metadata-cli.json");
    const args = [path.join(scripts, "build-firmware-release-metadata.mjs"), "--assets-dir", dir,
      "--release-tag", SCHEMA_FIXTURE.releaseTag, "--run-id", "9001", "--commit-sha", "1".repeat(40),
      "--version-name", "2.8.1", "--release-notes", SCHEMA_FIXTURE.releaseNotes, "--target-hardware", "AT32F435RGT7",
      "--hardware-revision", "1", "--layout-id", "1", "--min-boot-version", "1", "--min-protocol-version", "1",
      "--min-app-version-code", "0", "--final-image", path.join(dir, "app.bin"),
      "--patch-bases", path.join(dir, "patch-bases.json"), "--output", output];
    const run = spawnSync(process.execPath, args, { cwd: worker, env: process.env, encoding: "utf8", windowsHide: true, timeout: 15000 });
    console.info("BUILDER_CLI", { exitCode: run.status, stdout: run.stdout, stderr: run.stderr });
    expect(run.status).toBe(0);
    expect(JSON.parse(await readFile(output, "utf8")).assets).toHaveLength(3);
    expect(new Uint8Array(await readFile(path.join(dir, "app.bin")))).toEqual(bytesFor("final-image"));
  });
  it("uploads with conditional create, canonical HTTP metadata and full readback; same bytes never rewrite", async () => {
    const value = metadata(); const asset = value.assets[0];
    const put = vi.spyOn(env.RELEASES_BUCKET, "put");
    try {
      const result = await uploadFirmwareAsset(value, asset.fileName, bytesFor("full"), env.RELEASES_BUCKET);
      expect(result).toMatchObject({ ok: true, status: "UPLOADED", contentDigest: contentDigest(asset.sha256) });
      const options = put.mock.calls[0][2]!;
      expect(options.onlyIf).toEqual({ etagDoesNotMatch: "*" });
      expect(options.customMetadata).toMatchObject({ sha256: asset.sha256, kind: "full" });
      expect(new Headers(options.httpMetadata as Headers).get("Content-Digest")).toBe(contentDigest(asset.sha256));
      expect(new Headers(options.httpMetadata as Headers).get("Content-Length")).toBe(String(asset.sizeBytes));
      expect(await uploadFirmwareAsset(value, asset.fileName, bytesFor("full"), env.RELEASES_BUCKET)).toMatchObject({ status: "ALREADY_PRESENT" });
      expect(put).toHaveBeenCalledTimes(1);
    } finally { put.mockRestore(); }
  });
  it.each(["metadata", "bytes", "size"])("rejects existing R2 %s collision without overwrite", async (kind) => {
    const value = metadata(); const asset = value.assets[0];
    await env.RELEASES_BUCKET.put(asset.r2Key, kind === "size" ? new Uint8Array(2) : kind === "bytes" ? new Uint8Array(asset.sizeBytes) : bytesFor("full"),
      { customMetadata: { kind: "full", sha256: kind === "metadata" ? "0".repeat(64) : asset.sha256 } });
    const put = vi.spyOn(env.RELEASES_BUCKET, "put");
    try {
      await expect(uploadFirmwareAsset(value, asset.fileName, bytesFor("full"), env.RELEASES_BUCKET)).rejects.toMatchObject({ code: "R2_OBJECT_CONFLICT" });
      expect(put).not.toHaveBeenCalled();
    } finally { put.mockRestore(); }
  });
  it("closes the HEAD/PUT race with onlyIf and verifies the winning object", async () => {
    const value = metadata(); const asset = value.assets[0]; await uploadFixture(value);
    const head = vi.spyOn(env.RELEASES_BUCKET, "head").mockResolvedValueOnce(null);
    try {
      expect(await uploadFirmwareAsset(value, asset.fileName, bytesFor("full"), env.RELEASES_BUCKET)).toMatchObject({ status: "ALREADY_PRESENT" });
    } finally { head.mockRestore(); }
  });
  it("rejects false-positive put success when readback is missing", async () => {
    const value = metadata(); const asset = value.assets[0];
    const get = vi.spyOn(env.RELEASES_BUCKET, "get").mockResolvedValue(null);
    try { await expect(uploadFirmwareAsset(value, asset.fileName, bytesFor("full"), env.RELEASES_BUCKET)).rejects.toMatchObject({ code: "R2_VERIFY_FAILED" }); }
    finally { get.mockRestore(); }
  });
  it("rejects local byte mismatches before any R2 call", async () => {
    const value = metadata(); const head = vi.spyOn(env.RELEASES_BUCKET, "head");
    try {
      await expect(uploadFirmwareAsset(value, value.assets[0].fileName, new Uint8Array(3), env.RELEASES_BUCKET)).rejects.toMatchObject({ code: "INVALID_PARAMETER" });
      expect(head).not.toHaveBeenCalled();
    } finally { head.mockRestore(); }
  });
  it("keeps dry-run metadata unverified and rejects the old skip-readback option", async () => {
    const dir = await files();
    const input = { ...SCHEMA_FIXTURE, assets: SCHEMA_FIXTURE.assets.map((a) => ({ ...a, r2Verified: false })) };
    const file = path.join(dir, "metadata-dry-run.json"); await writeFile(outputPath(root, file), canonicalJson(input));
    const argv = [path.join(scripts, "upload-firmware-r2-asset.mjs"), "--metadata", file, "--assets-dir", dir, "--asset", input.assets[0].fileName];
    const dry = spawnSync(process.execPath, [...argv, "--dry-run"], { cwd: worker, env: process.env, encoding: "utf8", windowsHide: true, timeout: 15000 });
    expect(dry.status).toBe(0); expect(JSON.parse(dry.stdout).verified).toBe(false);
    expect(await readFile(file, "utf8")).toBe(canonicalJson(input));
    const skip = spawnSync(process.execPath, [...argv, "--skip-readback"], { cwd: worker, env: process.env, encoding: "utf8", windowsHide: true, timeout: 15000 });
    expect(skip.status).toBe(2); expect(JSON.parse(skip.stderr).errorCode).toBe("INVALID_PARAMETER");
    console.info("UPLOADER_CLI", { dryRunExit: dry.status, refusedSkipExit: skip.status });
  });
  it("register client consumes the same real handler/SQLite chain and replays idempotently", async () => {
    const value = metadata(); await uploadFixture(value);
    const fetcher: typeof fetch = async (url, init) => SELF.fetch(String(url), init);
    const first = await registerFirmware(value, { serviceUrl: "https://example.com", deployToken: "test-deploy-token", fetcher });
    expect(first).toMatchObject({ state: "ready", assetsRegistered: 3, idempotent: false });
    expect(await registerFirmware(value, { serviceUrl: "https://example.com", deployToken: "test-deploy-token", fetcher })).toMatchObject({ releaseId: first.releaseId, idempotent: true });
  });
  it.each([400, 409, 503])("does not retry a definitive HTTP %s", async (status) => {
    const fetcher = vi.fn(async () => Response.json({ errorCode: status === 409 ? "RELEASE_CONFLICT" : "BACKEND_UNAVAILABLE" }, { status }));
    await expect(registerFirmware(metadata(), { serviceUrl: "https://example.com", deployToken: "test", fetcher })).rejects.toMatchObject({ exitCode: 1 });
    expect(fetcher).toHaveBeenCalledTimes(1);
  });
  it("bounds network-only retries and requires the registration result contract", async () => {
    const fetcher = vi.fn(async () => { throw new Error("no response"); });
    await expect(registerFirmware(metadata(), { serviceUrl: "https://example.com", deployToken: "test", fetcher })).rejects.toThrow();
    expect(fetcher).toHaveBeenCalledTimes(3);
    await expect(registerFirmware(metadata(), { serviceUrl: "https://example.com", deployToken: "test",
      fetcher: async () => Response.json({ ok: true }, { status: 201 }) })).rejects.toThrow(/result/);
  });
  it("rejects insecure origins, invalid config and unknown schema before fetch", async () => {
    const fetcher = vi.fn(async () => new Response());
    await expect(registerFirmware(metadata(), { serviceUrl: "http://example.com", deployToken: "test", fetcher })).rejects.toMatchObject({ exitCode: 2 });
    await expect(registerFirmware(metadata(), { serviceUrl: "https://example.com", deployToken: "test", retries: 4, fetcher })).rejects.toMatchObject({ exitCode: 2 });
    expect(() => parseFirmwareRegistration({ ...metadata(), schemaVersion: 1 })).toThrow();
    expect(fetcher).not.toHaveBeenCalled();
  });
  it("prevents script outputs escaping the active worktree", () => {
    expect(() => outputPath(root, path.join(root, "..", "p4-2-outside"))).toThrow(/escapes/);
    expect(() => outputPath(root, path.join(root + "-other", "result.json"))).toThrow(/escapes/);
  });
});
