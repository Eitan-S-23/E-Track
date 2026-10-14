import { env } from "cloudflare:workers";
import { SELF } from "cloudflare:test";
import { mkdir, mkdtemp, readFile } from "node:fs/promises";
import path from "node:path";
import { describe, expect, it, vi } from "vitest";
import { bytesFor, metadata as fixtureMetadata } from "../../app/bluetooth_flutter_Trace/cloudflare/update-service/worker/test/firmware-fixture";
import { outputPath, projectRoot, writeOutput } from "../../app/bluetooth_flutter_Trace/cloudflare/update-service/scripts/firmware-cli.mjs";
import { digest, metadataBytes, readyProjection } from "../../app/bluetooth_flutter_Trace/cloudflare/update-service/scripts/prepare-firmware-release.mjs";
import { firmwareGitHub } from "../../app/bluetooth_flutter_Trace/cloudflare/update-service/scripts/firmware-github-release.mjs";
import { publishPreparedRelease, releaseConfig, verifyPromotion, verifyMonotonic } from "../../app/bluetooth_flutter_Trace/cloudflare/update-service/scripts/firmware-release-pipeline.mjs";
import { registerFirmware } from "../../app/bluetooth_flutter_Trace/cloudflare/update-service/scripts/register-firmware-release.mjs";

const root = projectRoot();
let run = 9001;
async function setup(omitKind?: string) {
  const metadata = fixtureMetadata(); metadata.runId = String(++run);
  for (const a of metadata.assets) a.r2Verified = false;
  const parent = outputPath(root, path.join(root, ".cache/firmware-pipeline-tests"));
  await mkdir(parent, { recursive: true });
  const assetsDir = await mkdtemp(path.join(parent, "case-"));
  for (const a of metadata.assets) if (a.kind !== omitKind) await writeOutput(root, path.join(assetsDir, a.fileName), bytesFor(a.kind));
  await writeOutput(root, path.join(assetsDir, "cloudflare-firmware-release-metadata.json"), metadataBytes(metadata));
  await writeOutput(root, path.join(assetsDir, "verification.json"), JSON.stringify({ fixtureOnly: true,
    layer: "script-handler-host", bytePreparationTestedSeparately: true }));
  const environment = { FIRMWARE_RELEASE_MODE: "rehearsal", GITHUB_EVENT_NAME: "workflow_dispatch",
    INPUT_PUBLISH: "false", INPUT_REHEARSAL: "true", OTA_BOOT_CHAIN_READY: "false",
    CLOUDFLARE_ACCOUNT_ID: "1".repeat(32), CLOUDFLARE_API_TOKEN: "isolated-fixture-token",
    TRACE_UPDATE_SERVICE_URL: "https://example.com", TRACE_DEPLOY_TOKEN: "test-deploy-token",
    TRACE_R2_BUCKET: "trace-update-staging-releases", TRACE_D1_DATABASE_ID: "11111111-1111-1111-1111-111111111111",
    TRACE_D1_DATABASE_NAME: "fixture-d1", OTA_AES_KEY: "01".repeat(16), GITHUB_TOKEN: "fixture-github-token",
    GITHUB_REPOSITORY: "Eitan-S-23/Trace", GITHUB_SHA: metadata.commitSha, GITHUB_RUN_ID: metadata.runId,
    GITHUB_RUN_ATTEMPT: "1", OTA_PREVIOUS_RELEASE_JSON: "fixture-only", TRACE_FIRMWARE_MIN_APP_VERSION_CODE: "0",
    TRACE_FIRMWARE_MIN_PROTOCOL_VERSION: "1" };
  const calls: string[] = [];
  const fetcher: typeof fetch = async (input, init) => {
    const url = String(input);
    calls.push(`${init?.method ?? "GET"} ${new URL(url).pathname}`);
    if (url === "https://example.com/healthz") return Response.json({ ok: true,
      environment: environment.FIRMWARE_RELEASE_MODE === "production" ? "prod" : "staging" });
    if (url === "https://example.com/api/ci/firmware/releases") return SELF.fetch(url, init);
    throw new Error("Unexpected test network request");
  };
  return { root, assetsDir, metadata, config: releaseConfig(environment), env: environment,
    bucket: env.RELEASES_BUCKET, db: env.DB, deployToken: "test-deploy-token", fetcher, calls,
    github: { publish: vi.fn(() => { throw new Error("Rehearsal must never publish GitHub"); }) } };
}

async function counts() {
  return {
    releases: (await env.DB.prepare("SELECT COUNT(*) AS n FROM firmware_releases").first<{ n: number }>())!.n,
    assets: (await env.DB.prepare("SELECT COUNT(*) AS n FROM firmware_release_assets").first<{ n: number }>())!.n,
    audit: (await env.DB.prepare("SELECT COUNT(*) AS n FROM audit_logs").first<{ n: number }>())!.n,
    channels: (await env.DB.prepare("SELECT * FROM firmware_channels ORDER BY id").all()).results
  };
}

// Only the GitHub HTTP/storage surface is doubled. Publication ordering and
// full-byte verification execute the actual production client, not a fake flow.
class GitHubHttp {
  release: any = null;
  assets = new Map<string, any>();
  bytes = new Map<number, Uint8Array>();
  calls: string[] = [];
  corrupt = false;
  redirect = false;
  constructor(readonly metadata: any) {}
  fetch: typeof fetch = async (input, init = {}) => {
    const url = new URL(String(input)); const method = init.method ?? "GET";
    this.calls.push(`${method} ${url.hostname}${url.pathname}`);
    if (url.hostname === "release-assets.githubusercontent.com") {
      expect(init.headers).toBeUndefined();
      return new Response(this.bytes.get(Number(url.pathname.slice(1))));
    }
    if (url.pathname.includes("/git/ref/tags/")) return Response.json({ object: { type: "commit", sha: this.metadata.commitSha } });
    if (url.pathname.includes("/releases/tags/")) return this.release ? Response.json(this.release) : new Response(null, { status: 404 });
    if (url.hostname === "uploads.github.com") {
      expect(method).toBe("POST");
      const name = url.searchParams.get("name")!;
      if (this.assets.has(name)) return new Response(null, { status: 409 });
      const body = new Uint8Array(await new Response(init.body).arrayBuffer());
      const asset = { id: 10 + this.assets.size, name, size: body.length, state: "uploaded", digest: `sha256:${digest(body)}` };
      this.assets.set(name, asset); this.bytes.set(asset.id, body);
      return Response.json(asset, { status: 201 });
    }
    const match = url.pathname.match(/\/releases\/assets\/(\d+)$/);
    if (match) {
      if (this.redirect) return new Response(null, { status: 302, headers: { Location: `https://release-assets.githubusercontent.com/${match[1]}` } });
      const bytes = this.bytes.get(Number(match[1]))!;
      return new Response(this.corrupt ? new Uint8Array(bytes.length) : bytes);
    }
    if (url.pathname.endsWith("/releases/7/assets")) return Response.json([...this.assets.values()]);
    if (url.pathname.endsWith("/releases/7")) {
      if (method === "PATCH") {
        expect(JSON.parse(String(init.body))).toEqual({ draft: false }); this.release.draft = false;
      }
      return Response.json(this.release);
    }
    if (url.pathname.endsWith("/releases") && method === "POST") {
      this.release = { id: 7, ...JSON.parse(String(init.body)) };
      return Response.json(this.release, { status: 201 });
    }
    throw new Error(`Unexpected GitHub fixture request: ${method} ${url.pathname}`);
  };
  client() { return firmwareGitHub({ repository: "Eitan-S-23/Trace", token: "fixture-only", fetcher: this.fetch }); }
}

describe("P4-1 production pipeline with existing handler and SQLite host ports", () => {
  it("uploads and fully reads three assets, then atomically registers ready and replays with no extra rows/audit/channel effects", async () => {
    const s = await setup(); const before = await counts();
    const first = await publishPreparedRelease(s);
    expect(first.registration).toMatchObject({ state: "ready", idempotent: false, assetsRegistered: 3 });
    expect(first.replay).toMatchObject({ releaseId: first.registration.releaseId, idempotent: true });
    expect(first.uploads.map(v => v.status)).toEqual(["UPLOADED", "UPLOADED", "UPLOADED"]);
    expect(s.github.publish).not.toHaveBeenCalled();
    const after = await counts();
    expect({ ...after, channels: undefined }).toEqual({ ...before, channels: undefined,
      releases: before.releases + 1, assets: before.assets + 3, audit: before.audit + 1 });
    expect(after.channels).toHaveLength(2);
    for (const channel of after.channels) expect(channel).toMatchObject({ current_release_id: null, revision: 0, last_action: "init" });
    if (before.channels.length) expect(after.channels).toEqual(before.channels);
    const put = vi.spyOn(s.bucket, "put");
    try {
      expect((await publishPreparedRelease(s)).uploads.every(v => v.status === "ALREADY_PRESENT")).toBe(true);
      expect(put).not.toHaveBeenCalled(); expect(await counts()).toEqual(after);
    } finally { put.mockRestore(); }
    console.info("P41_HOST_READY", { uploads: first.uploads, registration: first.registration, replay: first.replay,
      before, after, metadataSha256: first.metadataSha256, calls: s.calls });
  });

  it.each(["missing asset", "bad digest"])("%s rejects before health, GitHub, R2 or registration", async reason => {
    const s = await setup(reason === "missing asset" ? "recovery" : undefined);
    if (reason === "bad digest") s.metadata.assets[0].sha256 = "0".repeat(64);
    const head = vi.spyOn(s.bucket, "head");
    try {
      await expect(publishPreparedRelease(s)).rejects.toThrow();
      expect(head).not.toHaveBeenCalled(); expect(s.calls).toEqual([]); expect(s.github.publish).not.toHaveBeenCalled();
    } finally { head.mockRestore(); }
  });

  it("same-key different bytes rejects without overwrite or register", async () => {
    const s = await setup(); const a = s.metadata.assets[0]; const before = await counts();
    await s.bucket.put(a.r2Key, new Uint8Array(a.sizeBytes), { customMetadata: { kind: a.kind, sha256: a.sha256 } });
    const put = vi.spyOn(s.bucket, "put");
    try {
      await expect(publishPreparedRelease(s)).rejects.toMatchObject({ code: "R2_OBJECT_CONFLICT" });
      expect(put).not.toHaveBeenCalled(); expect(await counts()).toEqual(before);
      expect(s.calls.some(v => v.startsWith("POST"))).toBe(false);
    } finally { put.mockRestore(); }
  });

  it("false-positive R2 put with missing readback never persists verified metadata or touches D1", async () => {
    const s = await setup(); const before = await counts();
    const get = vi.spyOn(s.bucket, "get").mockResolvedValue(null);
    try {
      await expect(publishPreparedRelease(s)).rejects.toMatchObject({ code: "R2_VERIFY_FAILED" });
      expect(await counts()).toEqual(before);
      const stored = JSON.parse(await readFile(path.join(s.assetsDir, "cloudflare-firmware-release-metadata.json"), "utf8"));
      expect(stored.assets.every((a: any) => a.r2Verified === false)).toBe(true);
      expect(s.calls.some(v => v.startsWith("POST"))).toBe(false);
    } finally { get.mockRestore(); }
  });

  it("a real registration audit failure rolls back ready/assets and stops without retry", async () => {
    const s = await setup(); const before = await counts();
    await env.DB.exec("CREATE TRIGGER p41_fail_audit BEFORE INSERT ON audit_logs BEGIN SELECT RAISE(ABORT,'p41 injected audit failure'); END;");
    try {
      await expect(publishPreparedRelease(s)).rejects.toMatchObject({ exitCode: 1 });
      expect(await counts()).toEqual(before);
      expect(s.calls.filter(v => v.startsWith("POST"))).toHaveLength(1);
    } finally { await env.DB.exec("DROP TRIGGER p41_fail_audit"); }
  });

  it("cancellation after the first upload stops subsequent uploads and registration", async () => {
    const s = await setup(); const controller = new AbortController();
    const original = s.bucket.get.bind(s.bucket); let reads = 0;
    const get = vi.spyOn(s.bucket, "get").mockImplementation(async (...argv: any[]) => {
      const result = await (original as any)(...argv); reads++; controller.abort(); return result;
    });
    try {
      await expect(publishPreparedRelease({ ...s, signal: controller.signal })).rejects.toThrow(/cancelled/);
      expect(reads).toBe(1); expect(s.calls.some(v => v.startsWith("POST"))).toBe(false);
    } finally { get.mockRestore(); }
  });

  it("monotonicity rejects lower versions and same-version changed metadata before upload", async () => {
    const s = await setup(); await publishPreparedRelease(s);
    const changed = { ...s.metadata, releaseNotes: "different notes" };
    await expect(verifyMonotonic(s.db, changed)).rejects.toThrow(/increase D1/);
    await expect(verifyMonotonic(s.db, { ...s.metadata, versionCode: s.metadata.versionCode - 1 })).rejects.toThrow(/increase D1/);
  });

  it("checks/PR/nightly, ambiguous modes, missing config and crossed buckets fail closed", async () => {
    const s = await setup();
    for (const change of [{ GITHUB_EVENT_NAME: "push" }, { GITHUB_EVENT_NAME: "pull_request" },
      { FIRMWARE_RELEASE_MODE: "checks" }, { INPUT_PUBLISH: "true" }, { TRACE_R2_BUCKET: "production-bucket" },
      { OTA_AES_KEY: "" }, { CLOUDFLARE_API_TOKEN: "" }, { TRACE_D1_DATABASE_ID: "" }, { OTA_BOOT_CHAIN_READY: "true" }]) {
      expect(() => releaseConfig({ ...s.env, ...change })).toThrow();
    }
    expect(s.calls).toEqual([]);
  });

  it("production reuses approved canonical runId, checks rebuild bytes, then verifies immutable GitHub assets before R2/register", async () => {
    const s = await setup(); const stage = await publishPreparedRelease(s);
    const approvedMetadata = await readFile(path.join(s.assetsDir, "cloudflare-firmware-release-metadata.json"));
    const approvedEvidence = await readFile(path.join(s.assetsDir, "release-evidence.json"));
    const approvedPreparation = await readFile(path.join(s.assetsDir, "verification.json"));
    const envProduction = { ...s.env, FIRMWARE_RELEASE_MODE: "production", INPUT_PUBLISH: "true", INPUT_REHEARSAL: "false",
      OTA_BOOT_CHAIN_READY: "true", TRACE_R2_BUCKET: "production-fixture-bucket", GITHUB_RUN_ID: "999999",
      INPUT_APPROVED_REHEARSAL_RUN_ID: s.metadata.runId, OTA_APPROVED_REHEARSAL_RUN_ID: s.metadata.runId,
      OTA_APPROVED_REHEARSAL_ATTEMPT: "1", OTA_APPROVED_REHEARSAL_METADATA_SHA256: digest(approvedMetadata),
      OTA_APPROVED_REHEARSAL_EVIDENCE_SHA256: digest(approvedEvidence) };
    const config = releaseConfig(envProduction);
    const approvedRun = { id: Number(s.metadata.runId), head_sha: s.metadata.commitSha, path: ".github/workflows/firmware-build.yml",
      event: "workflow_dispatch", conclusion: "success", run_attempt: 1 };
    const approval = { approvedMetadata, approvedEvidence, approvedPreparation, approvedRun };
    const http = new GitHubHttp(s.metadata);
    const fetcher: typeof fetch = async (input, init) => String(input).endsWith("/healthz")
      ? Response.json({ ok: true, environment: "prod" }) : s.fetcher(input, init);
    const result = await publishPreparedRelease({ ...s, config, env: envProduction, github: http.client(), approval, fetcher });
    expect(result.canonicalRunId).toBe(stage.executionRunId); expect(result.executionRunId).toBe("999999");
    expect(result.metadataSha256).toBe(stage.metadataSha256); expect(result.github?.assetCount).toBe(3);
    expect(http.assets.size).toBe(3); expect(http.release.draft).toBe(false);
    expect(http.calls.some(v => v.startsWith("DELETE"))).toBe(false);
    const events = JSON.parse(await readFile(path.join(s.assetsDir, "release-steps.json"), "utf8"));
    expect(events.map((v: any) => v.step)).toEqual(["preflight", "github-release-readback", "r2-readback", "r2-readback", "r2-readback", "register", "idempotent-replay"]);
    for (const changed of [{ ...s.metadata, runId: config.executionRunId }, { ...s.metadata, releaseNotes: "changed" }]) {
      expect(() => verifyPromotion(changed, { ...approval, config, env: envProduction })).toThrow();
    }
    expect(() => verifyPromotion(s.metadata, { ...approval, config, env: envProduction,
      approvedRun: { ...approvedRun, head_sha: "f".repeat(40) } })).toThrow();
    const again = await http.client().publish(s.metadata, new Map(s.metadata.assets.map(a => [a.fileName, bytesFor(a.kind)])));
    expect(again.assetCount).toBe(3);
    expect(http.calls.filter(v => v.startsWith("POST uploads.github.com"))).toHaveLength(3);
    console.info("P41_HOST_PRODUCTION_ORDER", events.map((v: any) => v.step));
  });

  it("GitHub full-byte readback catches false metadata and never publishes a corrupted draft", async () => {
    const s = await setup(); const http = new GitHubHttp(s.metadata); http.corrupt = true;
    await expect(http.client().publish(s.metadata, new Map(s.metadata.assets.map(a => [a.fileName, bytesFor(a.kind)]))))
      .rejects.toThrow(/readback digest/);
    expect(http.release.draft).toBe(true);
    expect(http.calls.some(v => v.startsWith("PATCH"))).toBe(false);
  });

  it("GitHub signed redirect receives no repository credential", async () => {
    const s = await setup(); const http = new GitHubHttp(s.metadata); http.redirect = true;
    await expect(http.client().publish(s.metadata, new Map(s.metadata.assets.map(a => [a.fileName, bytesFor(a.kind)]))))
      .resolves.toMatchObject({ fullReadbackVerified: true });
  });

  it("register cancellation does not retry and service paths cannot hide a wrong origin", async () => {
    const s = await setup(); const controller = new AbortController(); controller.abort();
    const fetcher = vi.fn(async () => new Response());
    await expect(registerFirmware(readyProjection(s.metadata), { serviceUrl: "https://example.com", deployToken: "test", fetcher,
      signal: controller.signal })).rejects.toThrow(/cancelled/);
    await expect(registerFirmware(readyProjection(s.metadata), { serviceUrl: "https://example.com/path", deployToken: "test", fetcher }))
      .rejects.toMatchObject({ exitCode: 2 });
    expect(fetcher).not.toHaveBeenCalled();
  });

  it.each(["valid", "wrong commit", "wrong digest", "not previous", "draft", "missing asset"])
    ("formal base transport checks actual source/version/full SHA: %s", async reason => {
      const bytes = bytesFor("final-image");
      const descriptor = { isFormalRelease: true, kind: "app", versionName: "2.8.0", versionCode: 20800,
        releaseTag: "mcu-e-track-at32f435-v2.8.0", commitSha: "1".repeat(40), imageSha256: digest(bytes),
        sourceSha256: digest(bytes), sourceSizeBytes: bytes.length,
        sourceUrl: "https://github.com/Eitan-S-23/Trace/releases/download/mcu-e-track-at32f435-v2.8.0/X-Track-App-GCC.bin" };
      const fetcher = vi.fn<typeof fetch>(async (input, init) => {
        expect(init?.method ?? "GET").toBe("GET");
        const url = new URL(String(input));
        if (url.pathname.endsWith("/releases")) return Response.json([
          { id: 8, tag_name: descriptor.releaseTag, draft: reason === "draft", prerelease: false },
          ...(reason === "not previous" ? [{ id: 9, tag_name: "mcu-e-track-at32f435-v2.8.1", draft: false, prerelease: false }] : [])
        ]);
        if (url.pathname.includes("/git/ref/tags/")) return Response.json({ object: { type: "commit",
          sha: reason === "wrong commit" ? "2".repeat(40) : descriptor.commitSha } });
        if (url.pathname.endsWith("/releases/8/assets")) return Response.json(reason === "missing asset" ? [] : [
          { id: 80, name: "X-Track-App-GCC.bin", size: bytes.length, state: "uploaded", digest: `sha256:${digest(bytes)}` }]);
        if (url.pathname.endsWith("/releases/assets/80")) return new Response(reason === "wrong digest" ? new Uint8Array(bytes.length) : bytes);
        throw new Error("Unexpected formal base fixture request");
      });
      const client = firmwareGitHub({ repository: "Eitan-S-23/Trace", token: "fixture-only", fetcher });
      if (reason === "valid") expect((await client.formalBase(descriptor, "2.8.2")).bytes).toEqual(Buffer.from(bytes));
      else await expect(client.formalBase(descriptor, "2.8.2")).rejects.toThrow();
    });
});
