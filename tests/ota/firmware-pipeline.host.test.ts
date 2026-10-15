import { env } from "cloudflare:workers";
import { SELF } from "cloudflare:test";
import { createHash } from "node:crypto";
import { mkdir, mkdtemp, readFile } from "node:fs/promises";
import path from "node:path";
import { describe, expect, it, vi } from "vitest";
import { bytesFor, metadata as fixtureMetadata } from "../../app/bluetooth_flutter_Trace/cloudflare/update-service/worker/test/firmware-fixture";
import { outputPath, projectRoot, writeOutput } from "../../app/bluetooth_flutter_Trace/cloudflare/update-service/scripts/firmware-cli.mjs";
import { digest, metadataBytes, readyProjection } from "../../app/bluetooth_flutter_Trace/cloudflare/update-service/scripts/prepare-firmware-release.mjs";
import { firmwareGitHub } from "../../app/bluetooth_flutter_Trace/cloudflare/update-service/scripts/firmware-github-release.mjs";
import { publishPreparedRelease, releaseConfig, verifyPromotion, verifyMonotonic } from "../../app/bluetooth_flutter_Trace/cloudflare/update-service/scripts/firmware-release-pipeline.mjs";
import { registerFirmware } from "../../app/bluetooth_flutter_Trace/cloudflare/update-service/scripts/register-firmware-release.mjs";
import { canonicalJson } from "../../app/bluetooth_flutter_Trace/cloudflare/update-service/scripts/firmware-schema.mjs";

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
    TRACE_R2_BUCKET: "e-track-firmware-p41-test-releases", TRACE_D1_DATABASE_ID: "11111111-1111-1111-1111-111111111111",
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
  otherReleases: any[] = [];
  tag: string | null = null;
  assets = new Map<string, any>();
  bytes = new Map<number, Uint8Array>();
  calls: string[] = [];
  corrupt = false;
  redirect = false;
  stopAfterUploads: number | null = null;
  createdTarget: string | null = null;
  tagAfterUploads: string | null = null;
  constructor(readonly metadata: any) {}
  seedDraft() {
    this.release = { id: 7, tag_name: this.metadata.releaseTag, target_commitish: this.metadata.commitSha,
      name: this.metadata.releaseTag, body: this.metadata.releaseNotes, draft: true, prerelease: false };
  }
  store(name: string, bytes: Uint8Array) {
    const asset = { id: 10 + this.assets.size, name, size: bytes.length, state: "uploaded", digest: `sha256:${digest(bytes)}` };
    this.assets.set(name, asset); this.bytes.set(asset.id, bytes);
    return asset;
  }
  interrupt() {
    if (this.stopAfterUploads !== null && this.assets.size >= this.stopAfterUploads) throw new Error("injected GitHub interruption");
  }
  fetch: typeof fetch = async (input, init = {}) => {
    const url = new URL(String(input)); const method = init.method ?? "GET";
    this.calls.push(`${method} ${url.hostname}${url.pathname}`);
    if (url.hostname === "release-assets.githubusercontent.com") {
      expect(init.headers).toBeUndefined();
      return new Response(this.bytes.get(Number(url.pathname.slice(1))));
    }
    if (url.pathname.includes("/git/ref/tags/")) return this.tag
      ? Response.json({ object: { type: "commit", sha: this.tag } }) : new Response(null, { status: 404 });
    // GitHub's by-tag endpoint returns published releases, not drafts. A new
    // draft can legitimately have no Git ref until it is published.
    if (url.pathname.includes("/releases/tags/")) return this.release && !this.release.draft
      ? Response.json(this.release) : new Response(null, { status: 404 });
    if (url.hostname === "uploads.github.com") {
      expect(method).toBe("POST");
      this.interrupt();
      const name = url.searchParams.get("name")!;
      if (this.assets.has(name)) return new Response(null, { status: 409 });
      const body = new Uint8Array(await new Response(init.body).arrayBuffer());
      const asset = this.store(name, body);
      if (this.tagAfterUploads && this.assets.size === this.metadata.assets.length) this.tag = this.tagAfterUploads;
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
        this.interrupt();
        expect(JSON.parse(String(init.body))).toEqual({ draft: false }); this.release.draft = false;
        this.tag ??= this.release.target_commitish;
      }
      return Response.json(this.release);
    }
    if (url.pathname.endsWith("/releases")) {
      if (method === "GET") return Response.json([...(this.release ? [this.release] : []), ...this.otherReleases]);
      if (method === "POST") {
        if (this.release) return new Response(null, { status: 422 });
        this.release = { id: 7, ...JSON.parse(String(init.body)) };
        if (this.createdTarget) this.release.target_commitish = this.createdTarget;
        return Response.json(this.release, { status: 201 });
      }
    }
    throw new Error(`Unexpected GitHub fixture request: ${method} ${url.pathname}`);
  };
  client() { return firmwareGitHub({ repository: "Eitan-S-23/Trace", token: "fixture-only", fetcher: this.fetch }); }
}

// Synthetic HTTP bytes qualify only provenance transport. Actual firmware/header
// and patch application are exercised separately by test_firmware_release.mjs.
function bootstrapHttp() {
  const repository = "Eitan-S-23/Trace";
  const bytes = Buffer.alloc(8192, 0x5a);
  const target = { versionName: "2.8.2", commitSha: "4".repeat(40), releaseTag: "mcu-e-track-at32f435-v2.8.2" };
  const descriptor: any = { provenanceKind: "inaugural-bootstrap-v1", isFormalRelease: false, kind: "app",
    versionName: "2.8.0", versionCode: 20800, commitSha: "1".repeat(40), buildTimestamp: 1786320000,
    imageSha256: digest(bytes), sourceSha256: digest(bytes), sourceSizeBytes: bytes.length,
    archiveCommit: "3".repeat(40), archivePath: "docs/ota-exec-notes/P4-1-bootstrap-baseline-fixture",
    sourceRunId: "12345", sourceRunAttempt: "1", sourceArtifactId: "67890", sourceArtifactSha256: "a".repeat(64),
    targetVersionName: target.versionName, targetCommitSha: target.commitSha, provenanceSha256: "",
    sourceUrl: "" };
  descriptor.sourceUrl = `https://raw.githubusercontent.com/${repository}/${descriptor.archiveCommit}/${descriptor.archivePath}/app-final.bin`;
  const provenance = { schemaVersion: 1, provenanceKind: descriptor.provenanceKind, repository,
    run: { id: 12345, run_attempt: 1, path: ".github/workflows/firmware-build.yml", status: "completed",
      conclusion: "success", event: "workflow_dispatch", head_sha: descriptor.commitSha, head_branch: "dev/fixture",
      repository: { id: 7, full_name: repository }, head_repository: { id: 7, full_name: repository } },
    artifact: { id: 67890, name: `p41-gcc-development-${descriptor.commitSha}`,
      digest: `sha256:${descriptor.sourceArtifactSha256}`, workflow_run: { id: 12345, repository_id: 7,
        head_repository_id: 7, head_sha: descriptor.commitSha, head_branch: "dev/fixture" } },
    verification: { ok: true, commitSha: descriptor.commitSha, runId: descriptor.sourceRunId,
      versionName: descriptor.versionName, build: { commitSha: descriptor.commitSha,
        versionName: descriptor.versionName, versionCode: descriptor.versionCode, buildTimestamp: descriptor.buildTimestamp,
        app: { fileName: "X-Track-App-GCC.bin", sizeBytes: bytes.length, sha256: "b".repeat(64) },
        boot: { fileName: "X-Track-Boot.bin", sizeBytes: 16384, sha256: "c".repeat(64) } },
      finalImage: { fileName: "app-final.bin", sizeBytes: bytes.length, sha256: descriptor.imageSha256 },
      base: null, fullByteEqual: true, patchByteEqual: null, recoveryVerified: true, r2Verified: false },
    developmentOnly: { installable: false, formalBase: "NOT_USED", rehearsal: "NOT_RUN", remoteEffects: "NOT_RUN" } };
  const state = { descriptor, provenance, target, bytes, provenanceBytes: Buffer.alloc(0), approval: "",
    releases: [] as any[], tag: null as string | null, corrupt: false, wrongPath: false,
    archiveType: "file", encoding: "base64", missing: false, redirected: false, calls: [] as string[],
    mode: "rehearsal", treeMode: "100644", treeType: "blob", truncatedTree: false,
    wrongCommit: false, wrongTree: false, wrongBlob: false, invalidBase64: false,
    oversizedFile: false, oversizedResponse: false, invalidListing: false, failPageTwo: false, laterReleases: [] as any[] };
  const blob = (data: Buffer) => createHash("sha1").update(Buffer.from(`blob ${data.length}\0`)).update(data).digest("hex");
  const seal = () => {
    state.provenanceBytes = Buffer.from(JSON.stringify(provenance));
    descriptor.provenanceSha256 = digest(state.provenanceBytes);
    state.approval = digest(Buffer.from(canonicalJson(descriptor)));
  };
  seal();
  const fetcher: typeof fetch = async (input, init = {}) => {
    const url = new URL(String(input));
    state.calls.push(`${init.method ?? "GET"} ${url.hostname}${url.pathname}`);
    expect(init.method ?? "GET").toBe("GET");
    expect(url.origin).toBe("https://api.github.com");
    expect(init.redirect).toBe("error");
    if (url.pathname.endsWith("/releases")) {
      if (state.invalidListing) return Response.json({ incomplete: true });
      if (url.searchParams.get("page") === "2") return state.failPageTwo
        ? new Response(null, { status: 503 }) : Response.json(state.laterReleases);
      return Response.json(state.releases);
    }
    if (url.pathname.includes("/git/ref/tags/")) return state.tag
      ? Response.json({ object: { type: "commit", sha: state.tag } }) : new Response(null, { status: 404 });
    if (url.pathname.includes("/git/commits/")) return Response.json({ sha: state.wrongCommit ? "f".repeat(40) : descriptor.archiveCommit,
      tree: { sha: "5".repeat(40) } });
    if (url.pathname.includes("/git/trees/")) return Response.json({ sha: (state.wrongTree ? "f" : "5").repeat(40), truncated: state.truncatedTree,
      tree: [["provenance.json", state.provenanceBytes], ["app-final.bin", bytes]].map(([name, data]) => ({
        path: `${descriptor.archivePath}/${name}`, type: state.treeType, mode: state.treeMode,
        sha: state.wrongBlob ? "f".repeat(40) : blob(data as Buffer) })) });
    const prefix = `/repos/${repository}/contents/`;
    if (url.pathname.startsWith(prefix)) {
      expect(url.searchParams.get("ref")).toBe(descriptor.archiveCommit);
      if (state.missing) return new Response(null, { status: 404 });
      if (state.redirected) return new Response(null, { status: 302, headers: { Location: "https://untrusted.invalid/archive" } });
      if (state.oversizedResponse) return new Response(" ".repeat(131072 * 2 + 8193));
      const requested = decodeURIComponent(url.pathname.slice(prefix.length));
      const data = requested.endsWith("/provenance.json") ? state.provenanceBytes
        : state.corrupt ? Buffer.alloc(bytes.length) : bytes;
      return Response.json({ type: state.archiveType, path: state.wrongPath ? "wrong-path" : requested,
        encoding: state.encoding, size: state.oversizedFile ? 983041 : data.length, sha: blob(data),
        content: data.toString("base64") + (state.invalidBase64 ? "!" : "") });
    }
    throw new Error(`Unexpected bootstrap fixture request: ${url.pathname}`);
  };
  return { state, seal, client: () => firmwareGitHub({ repository, token: "fixture-only", fetcher }) };
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
    for (const change of [{ TRACE_FIRMWARE_MIN_APP_VERSION_CODE: "2100000001" }, { TRACE_FIRMWARE_MIN_PROTOCOL_VERSION: "256" },
      { TRACE_FIRMWARE_MIN_PROTOCOL_VERSION: "not-a-number" }, { TRACE_DEPLOY_TOKEN: "two credentials" }]) {
      expect(() => releaseConfig({ ...s.env, ...change })).toThrow();
    }
  });

  it.each([
    ["rehearsal", "e-track-firmware-p41-test-releases", true],
    ["rehearsal", "trace-update-staging-releases", false],
    ["rehearsal", "production-fixture-bucket", false],
    ["production", "e-track-firmware-p41-test-releases", false],
    ["production", "trace-update-staging-releases", false],
    ["production", "production-fixture-bucket", true]
  ])("P41_BUCKET_ROLES %s bucket %s admitted=%s", async (mode, bucket, admitted) => {
    const s = await setup();
    const production = mode === "production";
    const selected = { ...s.env, FIRMWARE_RELEASE_MODE: mode, TRACE_R2_BUCKET: bucket,
      INPUT_PUBLISH: String(production), INPUT_REHEARSAL: String(!production),
      OTA_BOOT_CHAIN_READY: String(production), GITHUB_RUN_ID: production ? "999999" : s.env.GITHUB_RUN_ID,
      INPUT_APPROVED_REHEARSAL_RUN_ID: s.env.GITHUB_RUN_ID,
      OTA_APPROVED_REHEARSAL_RUN_ID: s.env.GITHUB_RUN_ID, OTA_APPROVED_REHEARSAL_ATTEMPT: "1",
      OTA_APPROVED_REHEARSAL_METADATA_SHA256: "1".repeat(64),
      OTA_APPROVED_REHEARSAL_EVIDENCE_SHA256: "2".repeat(64) };
    if (admitted) expect(releaseConfig(selected)).toMatchObject({ mode, bucketName: bucket });
    else expect(() => releaseConfig(selected)).toThrow(/bucket bindings/);
    expect(s.calls).toEqual([]);
    expect(s.github.publish).not.toHaveBeenCalled();
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

  it.each([0, 1, 3])("GitHub resumes the same untagged draft after interruption with %i uploaded assets", async completed => {
    const s = await setup(); const http = new GitHubHttp(s.metadata);
    const bytes = new Map(s.metadata.assets.map(a => [a.fileName, bytesFor(a.kind)]));
    http.stopAfterUploads = completed;
    await expect(http.client().publish(s.metadata, bytes)).rejects.toThrow(/injected GitHub interruption/);
    expect(http.release).toMatchObject({ id: 7, draft: true, target_commitish: s.metadata.commitSha });
    expect(http.tag).toBeNull(); expect(http.assets.size).toBe(completed);
    const firstCalls = [...http.calls];
    const existing = [...http.bytes].map(([id, value]) => ({ id, sha256: digest(value) }));
    http.stopAfterUploads = null;
    const result = await http.client().publish(s.metadata, bytes);
    expect(result).toEqual({ releaseId: 7, assetCount: 3, fullReadbackVerified: true });
    expect(http.release.draft).toBe(false); expect(http.tag).toBe(s.metadata.commitSha);
    const retryCalls = http.calls.slice(firstCalls.length);
    expect(retryCalls).toContain("GET api.github.com/repos/Eitan-S-23/Trace/releases");
    expect(retryCalls.filter(v => v.startsWith("POST uploads.github.com"))).toHaveLength(3 - completed);
    expect(http.calls.filter(v => v === "POST api.github.com/repos/Eitan-S-23/Trace/releases")).toHaveLength(1);
    for (const item of existing) expect(digest(http.bytes.get(item.id)!)).toBe(item.sha256);
    await writeOutput(root, path.join(s.assetsDir, "github-draft-retry.json"), JSON.stringify({ completed,
      firstCalls, retryCalls, existing, result, tag: http.tag }, null, 2) + "\n");
    console.info("P41_HOST_DRAFT_RETRY", { completed, releaseId: result.releaseId,
      newUploads: 3 - completed, existingBytesUnchanged: true, fullReadbackVerified: true });
  });

  it.each(["wrong target", "mutable target", "conflicting tag", "ambiguous drafts", "changed notes", "prerelease"])
    ("GitHub rejects %s in an existing draft before any mutation", async reason => {
      const s = await setup(); const http = new GitHubHttp(s.metadata); http.seedDraft();
      if (reason === "wrong target") http.release.target_commitish = "f".repeat(40);
      if (reason === "mutable target") http.release.target_commitish = "main";
      if (reason === "conflicting tag") http.tag = "f".repeat(40);
      if (reason === "ambiguous drafts") http.otherReleases.push({ ...http.release, id: 8 });
      if (reason === "changed notes") http.release.body = "different notes";
      if (reason === "prerelease") http.release.prerelease = true;
      await expect(http.client().publish(s.metadata, new Map(s.metadata.assets.map(a => [a.fileName, bytesFor(a.kind)]))))
        .rejects.toMatchObject({ code: "RELEASE_CONFLICT" });
      expect(http.calls.filter(v => !v.startsWith("GET"))).toEqual([]);
      expect(http.assets.size).toBe(0); expect(http.release.draft).toBe(true);
    });

  it("GitHub still requires a tag for a published release", async () => {
    const s = await setup(); const http = new GitHubHttp(s.metadata); http.seedDraft(); http.release.draft = false;
    await expect(http.client().publish(s.metadata, new Map(s.metadata.assets.map(a => [a.fileName, bytesFor(a.kind)]))))
      .rejects.toThrow();
    expect(http.calls.filter(v => !v.startsWith("GET"))).toEqual([]);
  });

  it("GitHub validates a newly returned draft target before any asset upload", async () => {
    const s = await setup(); const http = new GitHubHttp(s.metadata); http.createdTarget = "f".repeat(40);
    await expect(http.client().publish(s.metadata, new Map(s.metadata.assets.map(a => [a.fileName, bytesFor(a.kind)]))))
      .rejects.toMatchObject({ code: "RELEASE_CONFLICT" });
    expect(http.assets.size).toBe(0); expect(http.calls.some(v => v.startsWith("PATCH"))).toBe(false);
  });

  it("GitHub rechecks a conflicting tag created during upload before publishing", async () => {
    const s = await setup(); const http = new GitHubHttp(s.metadata); http.tagAfterUploads = "f".repeat(40);
    await expect(http.client().publish(s.metadata, new Map(s.metadata.assets.map(a => [a.fileName, bytesFor(a.kind)]))))
      .rejects.toMatchObject({ code: "RELEASE_CONFLICT" });
    expect(http.assets.size).toBe(3); expect(http.release.draft).toBe(true);
    expect(http.calls.some(v => v.startsWith("PATCH"))).toBe(false);
  });

  it("GitHub reads every existing draft asset before adding missing assets", async () => {
    const s = await setup(); const http = new GitHubHttp(s.metadata); http.seedDraft();
    const asset = s.metadata.assets[0]; http.store(asset.fileName, bytesFor(asset.kind)); http.corrupt = true;
    await expect(http.client().publish(s.metadata, new Map(s.metadata.assets.map(a => [a.fileName, bytesFor(a.kind)]))))
      .rejects.toThrow(/readback digest/);
    expect(http.calls.filter(v => !v.startsWith("GET"))).toEqual([]);
    expect(http.assets.size).toBe(1); expect(http.release.draft).toBe(true); expect(http.tag).toBeNull();
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

  it("rejects a stale register response even if body and response header agree", async () => {
    const s = await setup();
    const fetcher = vi.fn(async () => Response.json({ ok: true, state: "ready", releaseId: "stale", requestId: "stale-request",
      assetsRegistered: 3, idempotent: false }, { status: 201, headers: { "X-Request-Id": "stale-request" } }));
    await expect(registerFirmware(readyProjection(s.metadata), { serviceUrl: "https://example.com", deployToken: "test", fetcher }))
      .rejects.toThrow(/Invalid registration result/);
    expect(fetcher).toHaveBeenCalledTimes(1);
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
      const target = { versionName: "2.8.2", commitSha: "4".repeat(40) };
      if (reason === "valid") {
        expect((await client.formalBase(descriptor, "2.8.2")).bytes).toEqual(Buffer.from(bytes));
        expect((await client.releaseBase(descriptor, target)).bytes).toEqual(Buffer.from(bytes));
      } else {
        await expect(client.formalBase(descriptor, "2.8.2")).rejects.toThrow();
        await expect(client.releaseBase(descriptor, target)).rejects.toThrow();
      }
      expect(fetcher.mock.calls.some(([url]) => String(url).includes("/contents/"))).toBe(false);
    });

  it.each(["first attempt", "exact published retry", "exact untagged draft retry"])
    ("P41_BOOTSTRAP_VALID %s preserves non-formal provenance without cloud writes", async reason => {
      const h = bootstrapHttp(); const s = h.state;
      if (reason !== "first attempt") {
        s.mode = "production";
        s.releases.push({ id: 99, tag_name: s.target.releaseTag, prerelease: false,
          draft: reason.includes("draft"), target_commitish: s.target.commitSha });
        if (!reason.includes("draft")) s.tag = s.target.commitSha;
      }
      const source = await h.client().releaseBase(s.descriptor, s.target, s.approval, s.mode);
      expect(source.bytes).toEqual(s.bytes);
      expect(source.evidence).toMatchObject({ provenanceKind: "inaugural-bootstrap-v1", isFormalRelease: false,
        sourceSha256: s.descriptor.sourceSha256, sourceRunId: "12345", sourceArtifactId: "67890" });
      expect(s.calls.every(call => call.startsWith("GET api.github.com/"))).toBe(true);
    });

  it.each(["missing approval", "missing mode", "missing target commit", "wrong approval", "wrong target", "unapproved descriptor", "mutable archive",
    "path traversal", "formal disguise", "unknown field"])("P41_BOOTSTRAP_REJECT %s before network", async reason => {
      const h = bootstrapHttp(); const s = h.state;
      if (reason === "missing approval") s.approval = "";
      if (reason === "missing mode") s.mode = "";
      if (reason === "missing target commit") s.target.commitSha = undefined as any;
      if (reason === "wrong approval") s.approval = "0".repeat(64);
      if (reason === "wrong target") s.target.commitSha = "f".repeat(40);
      if (reason === "unapproved descriptor") s.descriptor.sourceRunId = "23456";
      if (reason === "mutable archive") s.descriptor.archiveCommit = "main";
      if (reason === "path traversal") s.descriptor.archivePath += "/../other";
      if (reason === "formal disguise") s.descriptor.isFormalRelease = true;
      if (reason === "unknown field") s.descriptor.approved = true;
      await expect(h.client().releaseBase(s.descriptor, s.target, s.approval, s.mode)).rejects.toThrow();
      expect(s.calls).toEqual([]);
    });

  it.each(["previous release", "newer release", "other draft", "prerelease target", "ambiguous target", "blank tag", "control tag",
    "wrong published tag", "missing published tag", "wrong draft target", "malformed MCU version", "existing target during rehearsal"])
    ("P41_BOOTSTRAP_REJECT %s without archive reads", async reason => {
      const h = bootstrapHttp(); const s = h.state;
      s.mode = reason === "existing target during rehearsal" ? "rehearsal" : "production";
      const target = { id: 99, tag_name: s.target.releaseTag, prerelease: false, draft: false,
        target_commitish: s.target.commitSha };
      if (reason === "previous release") target.tag_name = "mcu-e-track-at32f435-v2.8.0";
      if (reason === "newer release") target.tag_name = "mcu-e-track-at32f435-v2.8.3";
      if (reason === "other draft") { target.tag_name = "mcu-e-track-at32f435-v2.8.1"; target.draft = true; }
      if (reason === "prerelease target") target.prerelease = true;
      if (reason === "blank tag") target.tag_name = "";
      if (reason === "control tag") target.tag_name = "mcu-e-track-at32f435-v2.8.2\n";
      if (reason === "wrong published tag") s.tag = "f".repeat(40);
      if (reason === "wrong draft target") { target.draft = true; target.target_commitish = "main"; }
      if (reason === "malformed MCU version") target.tag_name = "mcu-e-track-at32f435-v2.8.2-rc.1";
      if (reason === "existing target during rehearsal") s.tag = s.target.commitSha;
      s.releases.push(target);
      if (reason === "ambiguous target") s.releases.push({ ...target, id: 100 });
      await expect(h.client().releaseBase(s.descriptor, s.target, s.approval, s.mode)).rejects.toThrow();
      expect(s.calls.some(call => call.includes("/contents/"))).toBe(false);
    });

  it.each(["bad source bytes", "bad provenance digest", "symlink", "Git symlink", "Git submodule", "truncated Git tree",
    "wrong Git commit", "wrong Git tree", "wrong Git blob", "invalid base64", "oversized file", "oversized response",
    "wrong path", "wrong encoding", "missing archive",
    "redirected archive", "failed CI", "fork CI", "wrong source commit", "wrong run attempt", "wrong artifact",
    "wrong verification", "rewritten development label"])("P41_BOOTSTRAP_REJECT %s after read-only archive access", async reason => {
      const h = bootstrapHttp(); const s = h.state;
      if (reason === "bad source bytes") s.corrupt = true;
      if (reason === "symlink") s.archiveType = "symlink";
      if (reason === "Git symlink") s.treeMode = "120000";
      if (reason === "Git submodule") { s.treeMode = "160000"; s.treeType = "commit"; }
      if (reason === "truncated Git tree") s.truncatedTree = true;
      if (reason === "wrong Git commit") s.wrongCommit = true;
      if (reason === "wrong Git tree") s.wrongTree = true;
      if (reason === "wrong Git blob") s.wrongBlob = true;
      if (reason === "invalid base64") s.invalidBase64 = true;
      if (reason === "oversized file") s.oversizedFile = true;
      if (reason === "oversized response") s.oversizedResponse = true;
      if (reason === "wrong path") s.wrongPath = true;
      if (reason === "wrong encoding") s.encoding = "none";
      if (reason === "missing archive") s.missing = true;
      if (reason === "redirected archive") s.redirected = true;
      if (reason === "failed CI") s.provenance.run.conclusion = "failure";
      if (reason === "fork CI") s.provenance.run.head_repository.full_name = "somebody/Trace";
      if (reason === "wrong source commit") s.provenance.run.head_sha = "f".repeat(40);
      if (reason === "wrong run attempt") s.provenance.run.run_attempt = 2;
      if (reason === "wrong artifact") s.provenance.artifact.workflow_run.id = 23456;
      if (reason === "wrong verification") s.provenance.verification.finalImage.sha256 = "f".repeat(64);
      if (reason === "rewritten development label") s.provenance.developmentOnly.installable = true;
      h.seal();
      if (reason === "bad provenance digest") s.provenanceBytes = Buffer.from("{}");
      await expect(h.client().releaseBase(s.descriptor, s.target, s.approval, s.mode)).rejects.toThrow();
      expect(s.calls.every(call => call.startsWith("GET api.github.com/"))).toBe(true);
    });

  it.each(["predecessor on page two", "failed page two", "malformed listing"])
    ("P41_BOOTSTRAP_REJECT %s never treats an incomplete inventory as empty", async reason => {
      const h = bootstrapHttp(); const s = h.state;
      s.releases = Array.from({ length: 100 }, (_, n) => ({ id: n + 1, tag_name: `app-v${n}`, draft: false, prerelease: false }));
      if (reason === "predecessor on page two") s.laterReleases = [
        { id: 101, tag_name: "mcu-e-track-at32f435-v2.8.0", draft: false, prerelease: false }];
      if (reason === "failed page two") s.failPageTwo = true;
      if (reason === "malformed listing") s.invalidListing = true;
      await expect(h.client().releaseBase(s.descriptor, s.target, s.approval, s.mode)).rejects.toThrow();
      expect(s.calls.filter(call => call.endsWith("/releases"))).toHaveLength(reason === "malformed listing" ? 1 : 2);
      expect(s.calls.some(call => call.includes("/contents/"))).toBe(false);
    });
});
