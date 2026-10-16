import { env } from "cloudflare:workers";
import { SELF } from "cloudflare:test";
import { createHash } from "node:crypto";
import { mkdir, mkdtemp, readFile, writeFile } from "node:fs/promises";
import { createRequire } from "node:module";
import { spawnSync } from "node:child_process";
import { fileURLToPath } from "node:url";
import path from "node:path";
import { describe, expect, it, vi } from "vitest";
import { createHTTPReducers, Headers as MiniflareHeaders, Request as MiniflareRequest,
  Response as MiniflareResponse, stringifyWithStreams, structuredSerializableReducers,
  type PlatformImpl } from "miniflare";
import { buildFirmwareMetadata } from "../../scripts/build-firmware-release-metadata.mjs";
import { uploadFirmwareAsset } from "../../scripts/upload-firmware-r2-asset.mjs";
import { registerFirmware } from "../../scripts/register-firmware-release.mjs";
import { outputPath, projectRoot } from "../../scripts/firmware-cli.mjs";
import { canonicalJson, contentDigest, parseFirmwareRegistration } from "../../scripts/firmware-schema.mjs";
import { bytesFor, metadata, SCHEMA_FIXTURE, uploadFixture } from "./firmware-fixture";

const root = projectRoot();
const scripts = fileURLToPath(new URL("../../scripts/", import.meta.url));
const worker = fileURLToPath(new URL("../", import.meta.url));
// Use the SDK's actual constructors/reducers, without creating a native runtime.
const codecPlatform = {
  Blob, File, Headers: MiniflareHeaders, Request: MiniflareRequest, Response: MiniflareResponse,
  isReadableStream: (value: unknown) => value instanceof ReadableStream,
  bufferReadableStream: (stream: ReadableStream) => new Response(stream).arrayBuffer(),
  unbufferReadableStream: (buffer: ArrayBuffer) => new Response(buffer).body!
} as unknown as PlatformImpl<ReadableStream>;
const codecReducers = { ...structuredSerializableReducers, ...createHTTPReducers(codecPlatform) };
const encodePut = (argv: unknown[]) => stringifyWithStreams(codecPlatform, argv, codecReducers, true);

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
  it("P41-NATIVE-01 retains the pinned codec's Node Headers rejection and SDK Headers control", async () => {
    const requireWorker = createRequire(path.join(worker, "package.json"));
    const lock = JSON.parse(await readFile(path.join(worker, "package-lock.json"), "utf8"));
    const miniflareVersion = requireWorker("miniflare/package.json").version;
    const wranglerVersion = requireWorker("wrangler/package.json").version;
    expect(miniflareVersion).toBe(lock.packages["node_modules/miniflare"].version);
    expect(wranglerVersion).toBe(lock.packages["node_modules/wrangler"].version);
    expect(Headers).not.toBe(MiniflareHeaders);
    const asset = metadata().assets[0];
    const headers = { "Content-Type": "application/vnd.e-track.etu", "Content-Length": String(asset.sizeBytes),
      "Content-Digest": contentDigest(asset.sha256), "Content-Disposition": `attachment; filename="${asset.fileName}"`,
      "Cache-Control": "public, max-age=31536000, immutable" };
    const options = { onlyIf: { etagDoesNotMatch: "*" }, sha256: asset.sha256,
      customMetadata: { sha256: asset.sha256, kind: asset.kind, "content-digest": contentDigest(asset.sha256) } };
    let rejection;
    try { encodePut([asset.r2Key, bytesFor("full"), { ...options, httpMetadata: new Headers(headers) }]); }
    catch (error) { rejection = error; }
    expect(rejection).toMatchObject({ name: "DevalueError", message: "Cannot stringify arbitrary non-POJOs", path: "[2].httpMetadata" });
    const encoded = await encodePut([asset.r2Key, bytesFor("full"), { ...options, httpMetadata: new MiniflareHeaders(headers) }]);
    expect(encoded.value.length).toBeGreaterThan(0);
    console.info("P41_NATIVE_CODEC_CONTROL", { node: process.version, wranglerVersion, miniflareVersion,
      sdkSha256: createHash("sha256").update(await readFile(requireWorker.resolve("miniflare"))).digest("hex"),
      rejected: { name: (rejection as Error).name, path: "[2].httpMetadata" }, sdkHeadersAccepted: true });
  });
  it.each(["full", "patch", "recovery"])("P41-NATIVE-01 uploads %s through the real SDK codec with immutable metadata and full readback", async (kind) => {
    const value = metadata(); const asset = value.assets.find(a => a.kind === kind)!; const bytes = bytesFor(kind);
    const originalPut = env.RELEASES_BUCKET.put.bind(env.RELEASES_BUCKET);
    const put = vi.spyOn(env.RELEASES_BUCKET, "put").mockImplementation(async (...argv) => {
      // Serialize the unmodified production arguments before the memory adapter.
      const encoded = await encodePut(argv);
      expect(encoded.value.length).toBeGreaterThan(0);
      return originalPut(...argv);
    });
    const get = vi.spyOn(env.RELEASES_BUCKET, "get");
    try {
      const result = await uploadFirmwareAsset(value, asset.fileName, bytes, env.RELEASES_BUCKET);
      expect(result).toMatchObject({ ok: true, status: "UPLOADED", kind, sizeBytes: bytes.byteLength,
        sha256: asset.sha256, contentDigest: contentDigest(asset.sha256) });
      expect(put.mock.calls[0][0]).toBe(asset.r2Key);
      expect(put.mock.calls[0][1]).toBe(bytes);
      const options = put.mock.calls[0][2]!;
      expect(options.onlyIf).toEqual({ etagDoesNotMatch: "*" });
      expect(options.sha256).toBe(asset.sha256);
      expect(options.customMetadata).toEqual({ sha256: asset.sha256, kind, "content-digest": contentDigest(asset.sha256) });
      expect(Object.getPrototypeOf(options.httpMetadata)).toBe(Object.prototype);
      expect(options.httpMetadata).toEqual({
        contentType: kind === "recovery" ? "application/octet-stream" : "application/vnd.e-track.etu",
        contentDisposition: `attachment; filename="${asset.fileName}"`, cacheControl: "public, max-age=31536000, immutable"
      });
      const head = await env.RELEASES_BUCKET.head(asset.r2Key);
      expect(get.mock.calls).toEqual([[asset.r2Key, { onlyIf: { etagMatches: head!.etag } }]]);
      expect(await uploadFirmwareAsset(value, asset.fileName, bytes, env.RELEASES_BUCKET)).toMatchObject({ status: "ALREADY_PRESENT" });
      expect(put).toHaveBeenCalledTimes(1);
      expect(get.mock.calls).toEqual(Array.from({ length: 2 }, () => [asset.r2Key, { onlyIf: { etagMatches: head!.etag } }]));
      console.info("P41_NATIVE_CODEC_UPLOAD", { kind, status: result.status, options, fullReadbacks: get.mock.calls.length });
    } finally { put.mockRestore(); get.mockRestore(); }
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
  it.each(["short", "long", "digest"])("rejects a %s multi-chunk readback despite matching HEAD metadata", async (failure) => {
    const value = metadata(); const asset = value.assets[0]; const bytes = bytesFor("full");
    const changed = failure === "short" ? bytes.slice(0, -1)
      : failure === "long" ? new Uint8Array([...bytes, 0]) : bytes.slice();
    if (failure === "digest") changed[changed.length - 1] ^= 1;
    const originalGet = env.RELEASES_BUCKET.get.bind(env.RELEASES_BUCKET);
    const get = vi.spyOn(env.RELEASES_BUCKET, "get").mockImplementation(async (key, options) => {
      const object = await originalGet(key, options);
      if (!object || !("body" in object)) throw new Error("Expected stored fixture");
      return { ...object, writeHttpMetadata: object.writeHttpMetadata.bind(object), body: new ReadableStream<Uint8Array>({ start(controller) {
        controller.enqueue(changed.slice(0, 4)); controller.enqueue(changed.slice(4)); controller.close();
      } }) };
    });
    try {
      await expect(uploadFirmwareAsset(value, asset.fileName, bytes, env.RELEASES_BUCKET)).rejects.toMatchObject({ code: "R2_VERIFY_FAILED" });
      expect(get).toHaveBeenCalledTimes(1);
    } finally { get.mockRestore(); }
  });
  it.each(["length", "digest"])("rejects local %s mismatches before any R2 call", async (failure) => {
    const value = metadata(); const head = vi.spyOn(env.RELEASES_BUCKET, "head");
    const put = vi.spyOn(env.RELEASES_BUCKET, "put"); const get = vi.spyOn(env.RELEASES_BUCKET, "get");
    try {
      const bytes = new Uint8Array(failure === "length" ? 3 : value.assets[0].sizeBytes);
      await expect(uploadFirmwareAsset(value, value.assets[0].fileName, bytes, env.RELEASES_BUCKET)).rejects.toMatchObject({ code: "INVALID_PARAMETER" });
      expect(head).not.toHaveBeenCalled(); expect(put).not.toHaveBeenCalled(); expect(get).not.toHaveBeenCalled();
    } finally { head.mockRestore(); put.mockRestore(); get.mockRestore(); }
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
