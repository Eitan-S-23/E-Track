import { createHash } from "node:crypto";
import { canonicalJson, exactObject, FIRMWARE_MODEL, integer, sha256, text, versionCodeFor } from "./firmware-schema.mjs";

const digest = (bytes) => createHash("sha256").update(bytes).digest("hex");
const conflict = (id) => new Error(`BACKFILL_CONFLICT: ${id}`);
const fields = ["releaseId", "appId", "deviceModel", "releaseTag", "runId", "commitSha", "versionName", "versionCode",
  "targetImageSha256", "hardwareRevision", "layoutId", "minBootVersion", "minProtocolVersion", "targetHardware",
  "artifact", "image", "verification"];

function immutableLocator(value, label) {
  text(value, label);
  const url = new URL(value);
  if (url.protocol !== "https:" || url.username || url.password || url.search || url.hash
    || !/^\/[^/]+\/[^/]+\/releases\/download\/[^/]+\/[^/]+$/.test(url.pathname)
    || url.hostname !== "github.com" || url.pathname.includes("/latest/download/")) throw new Error(`Invalid immutable ${label}`);
}

async function verifiedRecord(record, old, readArtifact, bucket) {
  exactObject(record, fields, "backfill record");
  const pairs = { releaseId: "id", appId: "app_id", deviceModel: "device_model", releaseTag: "release_tag",
    runId: "run_id", commitSha: "commit_sha", versionName: "version_name", versionCode: "version_code" };
  for (const [key, column] of Object.entries(pairs)) if (record[key] !== old[column]) throw new Error(`Legacy ${key} mismatch`);
  if (record.appId !== "trace" || record.deviceModel !== FIRMWARE_MODEL) throw new Error("Unknown legacy model");
  if (typeof record.commitSha !== "string" || !/^[0-9a-f]{40}$/.test(record.commitSha)) throw new Error("Invalid commitSha");
  if (versionCodeFor(record.versionName) !== record.versionCode) throw new Error("Legacy version formula mismatch");
  text(record.runId, "runId");
  sha256(record.targetImageSha256, "targetImageSha256");
  integer(record.hardwareRevision, "hardwareRevision", 65535);
  for (const key of ["layoutId", "minBootVersion", "minProtocolVersion"]) integer(record[key], key, 255);
  text(record.targetHardware, "targetHardware");
  if (old.target_hardware && old.target_hardware !== record.targetHardware) throw new Error("Legacy target hardware mismatch");
  if (old.transport !== "ble") throw new Error("Unsupported legacy transport");
  integer(old.min_app_version_code, "minAppVersionCode", 2100000000);
  const artifact = exactObject(record.artifact, ["locator", "sha256", "sizeBytes"], "artifact");
  const image = exactObject(record.image, ["locator", "sha256", "imageLength"], "image");
  const verification = exactObject(record.verification,
    ["toolVersion", "evidenceLocator", "evidenceSha256", "verifiedBy", "verifiedAt"], "verification");
  immutableLocator(artifact.locator, "artifact locator");
  immutableLocator(image.locator, "image locator");
  immutableLocator(verification.evidenceLocator, "verification evidence locator");
  for (const key of ["toolVersion", "verifiedBy", "verifiedAt"]) text(verification[key], key);
  if (!/^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(?:\.\d+)?Z$/.test(verification.verifiedAt)
    || !Number.isFinite(Date.parse(verification.verifiedAt))) throw new Error("Invalid verification time");
  sha256(verification.evidenceSha256, "evidenceSha256");
  sha256(image.sha256, "image.sha256");
  if (artifact.locator !== old.github_url || artifact.sha256 !== old.sha256 || artifact.sizeBytes !== old.size_bytes
    || image.sha256 !== record.targetImageSha256) throw new Error("Legacy asset/image binding mismatch");
  integer(image.imageLength, "imageLength", 4294967295, 1);
  const bytes = await readArtifact(artifact.locator);
  const rawImage = await readArtifact(image.locator);
  const evidence = await readArtifact(verification.evidenceLocator);
  if (bytes.byteLength !== old.size_bytes || digest(bytes) !== old.sha256
    || rawImage.byteLength !== image.imageLength || digest(rawImage) !== image.sha256
    || digest(evidence) !== verification.evidenceSha256) throw new Error("Artifact/raw image/evidence byte verification failed");
  let etag = null;
  if (old.r2_state === "available") {
    if (!old.r2_key) throw new Error("Missing legacy R2 key");
    const head = await bucket.head(old.r2_key);
    if (!head || head.size !== old.size_bytes || (head.customMetadata?.sha256 && head.customMetadata.sha256 !== old.sha256)) {
      throw new Error("Legacy R2 HEAD mismatch");
    }
    const object = await bucket.get(old.r2_key, { onlyIf: { etagMatches: head.etag } });
    if (!object || !("body" in object)) throw new Error("Legacy R2 changed or missing");
    const hash = createHash("sha256");
    let size = 0;
    const reader = object.body.getReader();
    try {
      for (;;) {
        const chunk = await reader.read();
        if (chunk.done) break;
        size += chunk.value.byteLength;
        if (size > old.size_bytes) throw new Error("Legacy R2 length exceeded");
        hash.update(chunk.value);
      }
    } finally { await reader.cancel(); }
    if (size !== old.size_bytes || hash.digest("hex") !== old.sha256) throw new Error("Legacy R2 readback mismatch");
    etag = object.httpEtag;
  }
  return etag;
}

/**
 * Controlled, binding-based backfill. The caller supplies an approved immutable
 * manifest digest, an artifact reader, and the explicitly selected D1/R2 bindings.
 * This module performs no credential discovery, deployment or network fallback.
 * Validation of ALL unresolved published records precedes the first D1 write.
 */
export async function backfillFirmwareV2({ db, bucket, manifest, approvedManifestSha256, readArtifact }) {
  exactObject(manifest, ["manifestSchemaVersion", "approvedBy", "records"], "manifest");
  if (manifest.manifestSchemaVersion !== 1 || !Array.isArray(manifest.records)) throw new Error("Invalid manifestSchemaVersion/records");
  const approvals = exactObject(manifest.approvedBy, ["migrationOwner", "otaReleaseReviewer"], "approvals");
  text(approvals.migrationOwner, "migrationOwner");
  text(approvals.otaReleaseReviewer, "otaReleaseReviewer");
  sha256(approvedManifestSha256, "approvedManifestSha256");
  if (digest(canonicalJson(manifest)) !== approvedManifestSha256) throw new Error("Approved manifest digest mismatch");
  const originals = (await db.prepare("SELECT * FROM firmware_releases_legacy ORDER BY id").all()).results;
  const pending = (await db.prepare("SELECT * FROM firmware_channels WHERE legacy_current_release_id IS NOT NULL").all()).results;
  const published = new Set(pending.map((c) => c.legacy_current_release_id));
  const seen = new Set();
  for (const record of manifest.records) {
    if (!record || seen.has(record.releaseId)) throw new Error("Duplicate/invalid backfill releaseId");
    seen.add(record.releaseId);
  }
  const missing = [...published].filter((id) => !seen.has(id));
  if (missing.length) throw new Error(`LEGACY_UNVERIFIED: missing published manifests: ${missing.join(",")}`);
  const plans = [];
  const quarantined = [];
  const reused = [];
  for (const record of manifest.records) {
    const old = originals.find((r) => r.id === record.releaseId);
    const entry = canonicalJson({ manifestSchemaVersion: 1, approvedBy: approvals, record });
    const fingerprint = digest(entry);
    const existing = await db.prepare("SELECT manifest_sha256 FROM firmware_backfill_manifests WHERE release_id=?").bind(record.releaseId).first();
    if (existing && existing.manifest_sha256 !== fingerprint) throw conflict(record.releaseId);
    if (existing) { reused.push(record.releaseId); continue; }
    try {
      if (!old) throw new Error("Legacy release not found");
      const etag = await verifiedRecord(record, old, readArtifact, bucket);
      if (published.has(old.id) && (old.state === "disabled" || old.archived || old.r2_state !== "available" || !etag)) {
        throw new Error("Published legacy is not safely mappable to ready");
      }
      plans.push({ old, record, etag, fingerprint, entry });
    } catch (error) {
      const reason = error instanceof Error ? error.message : "Verification failed";
      if (published.has(record.releaseId)) throw new Error(`LEGACY_UNVERIFIED: ${record.releaseId}: ${reason}`);
      quarantined.push({ releaseId: record.releaseId, reason });
    }
  }
  const statements = [];
  for (const { old, record: r, etag, fingerprint, entry } of plans) {
    const state = old.state === "disabled" ? "disabled" : "draft";
    statements.push(db.prepare(`INSERT INTO firmware_releases (id,app_id,device_model,version_name,version_code,
      release_tag,commit_sha,run_id,state,release_notes,target_image_sha256,hardware_rev,layout_id,min_boot_version,
      min_protocol_version,target_hardware,transport,min_app_version_code,archived,created_at,updated_at)
      VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)`).bind(old.id, old.app_id, old.device_model, old.version_name,
      old.version_code, old.release_tag, old.commit_sha, old.run_id, state, old.release_notes, r.targetImageSha256,
      r.hardwareRevision, r.layoutId, r.minBootVersion, r.minProtocolVersion, r.targetHardware, old.transport,
      old.min_app_version_code, old.archived, old.created_at, old.updated_at));
    const slug = (v) => v.toLowerCase().replace(/[^a-z0-9]+/g, "_").replace(/^_+|_+$/g, "");
    // Keep the old asset identifier so existing v1 URLs can survive only their
    // fixed remaining compatibility window, without reintroducing v1 signing.
    const assetId = `fw_asset_${old.id}_${slug(old.file_name)}`;
    statements.push(db.prepare(`INSERT INTO firmware_release_assets
      (id,release_id,kind,file_name,sha256,size_bytes,r2_key,r2_etag,r2_state,github_url,base_image_sha256,base_vcode,created_at,updated_at)
      VALUES (?,?,'full',?,?,?,?,?,?,?,'',0,?,?)`).bind(assetId, old.id, old.file_name, old.sha256, old.size_bytes,
      old.r2_key, etag, old.r2_state, old.github_url, old.created_at, old.updated_at));
    statements.push(db.prepare("INSERT INTO firmware_backfill_manifests(release_id,manifest_sha256,manifest_json) VALUES (?,?,?)")
      .bind(old.id, fingerprint, entry));
    if (published.has(old.id)) {
      statements.push(db.prepare(`UPDATE firmware_releases SET state='ready',updated_at=datetime('now') WHERE id=?
        AND EXISTS(SELECT 1 FROM firmware_channels WHERE legacy_current_release_id=?)`).bind(old.id, old.id));
      statements.push(db.prepare(`UPDATE firmware_channels SET current_release_id=?,legacy_current_release_id=NULL
        WHERE legacy_current_release_id=?`).bind(old.id, old.id));
    }
    statements.push(db.prepare(`INSERT INTO audit_logs(id,app_id,actor,actor_type,action,target_type,target_id,request_id,reason,after_json)
      VALUES (?,?,?,'system','backfill_firmware_v2','firmware_release',?,?,'approved immutable manifest',?)`)
      .bind(`backfill_${digest(old.id)}`, old.app_id, approvals.migrationOwner, old.id, `backfill_${fingerprint}`,
        canonicalJson({ releaseId: old.id, manifestSha256: fingerprint, approvedManifestSha256 })));
  }
  if (statements.length) await db.batch(statements);
  return { migrated: plans.map((p) => p.old.id), reused, quarantined, approvedManifestSha256 };
}
