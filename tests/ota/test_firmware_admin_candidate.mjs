import test from "node:test";
import assert from "node:assert/strict";
import { readFile } from "node:fs/promises";
import { createHash } from "node:crypto";
import { adminCandidateAdmission, apiTokenS3Credentials, ADMIN_CANDIDATE_BUCKET,
  ADMIN_CANDIDATE_ORIGIN, verifyAdminCandidateAssets } from "../../.github/scripts/firmware-admin-candidate.mjs";

const valid = () => ({ GITHUB_ACTIONS: "true", GITHUB_EVENT_NAME: "workflow_dispatch",
  GITHUB_REPOSITORY: "Eitan-S-23/E-Track", GITHUB_SHA: "a".repeat(40), GITHUB_RUN_ID: "123456", GITHUB_RUN_ATTEMPT: "1",
  INPUT_PREPARE_ADMIN_CANDIDATE: "true", OTA_BOOT_CHAIN_READY: "false", INPUT_FIRMWARE_BUILD_PROFILE: "p34-v2-candidate",
  INPUT_CANDIDATE_REVIEWED_COMMIT: "a".repeat(40), INPUT_PUBLISH: "false", INPUT_REHEARSAL: "false",
  INPUT_CHECK_BINDINGS: "false", INPUT_PACKAGE_CANDIDATE: "false", INPUT_STAGE_CANDIDATE: "false",
  INPUT_VERSION_NAME: "3.3.23", INPUT_RELEASE_NOTES: "Normal V2 candidate; not hardware acceptance" });

test("normal original-Admin candidate is explicit and does not open production", () => {
  assert.equal(adminCandidateAdmission(valid()).versionCode, 30323);
  assert.equal(adminCandidateAdmission({ ...valid(), INPUT_VERSION_NAME: "3.3.21" }).versionCode, 30321);
  assert.equal(ADMIN_CANDIDATE_BUCKET, "trace-update-staging-releases");
  assert.equal(new URL(ADMIN_CANDIDATE_ORIGIN).hostname, "trace-update-service-staging.tangjichentudou.workers.dev");
});
for (const key of ["INPUT_PUBLISH", "INPUT_REHEARSAL", "INPUT_CHECK_BINDINGS", "INPUT_PACKAGE_CANDIDATE", "INPUT_STAGE_CANDIDATE", "OTA_BOOT_CHAIN_READY"]) {
  test(`mixed or production mode is rejected: ${key}`, () => assert.throws(() => adminCandidateAdmission({ ...valid(), [key]: "true" })));
}
for (const [key, value] of [["GITHUB_EVENT_NAME", "push"], ["GITHUB_REPOSITORY", "other/repo"],
  ["GITHUB_RUN_ATTEMPT", "2"], ["INPUT_CANDIDATE_REVIEWED_COMMIT", "b".repeat(40)],
  ["INPUT_FIRMWARE_BUILD_PROFILE", "baseline"], ["INPUT_CANDIDATE_BASE_VERSION", "3.3.23"],
  ["INPUT_CANDIDATE_BASE_VERSION", "3.3.24"], ["INPUT_CANDIDATE_BASE_VERSION", "invalid"],
  ["INPUT_VERSION_NAME", "3.3.22"], ["INPUT_VERSION_NAME", "3.3.20"], ["INPUT_RELEASE_NOTES", " "]]) {
  test(`invalid candidate identity is rejected: ${key}=${value}`, () => assert.throws(() => adminCandidateAdmission({ ...valid(), [key]: value })));
}
test("R2 uses the documented existing-token derivation without creating credentials", async () => {
  const token = "not-a-real-token", id = "b".repeat(32);
  const result = await apiTokenS3Credentials(token, async (url, init) => {
    assert.equal(url, "https://api.cloudflare.com/client/v4/user/tokens/verify");
    assert.equal(init.redirect, "error");
    assert.equal(init.headers.Authorization, `Bearer ${token}`);
    assert.equal(init.method, undefined);
    return Response.json({ success: true, result: { id, status: "active" } });
  });
  assert.deepEqual(result, { accessKeyId: id, secretAccessKey: createHash("sha256").update(token).digest("hex") });
});
for (const value of [{ success: false }, { success: true, result: { id: "a".repeat(32), status: "expired" } },
  { success: true, result: { id: "bad", status: "active" } }]) {
  test(`R2 token verification fails closed: ${JSON.stringify(value)}`, async () => {
    await assert.rejects(apiTokenS3Credentials("token", async () => Response.json(value)));
  });
}
test("normal source pins contain no fixed-load reference or imported ETU asset", async () => {
  const config = JSON.parse(await readFile(new URL("../../Tools/ota/admin-candidate-inputs.json", import.meta.url)));
  assert.equal(config.schema, "original-admin-normal-source-v1");
  assert.equal(config.profile, "p34-v2-candidate");
  assert.ok(!JSON.stringify(config).includes("reference.lzma"));
  assert.ok(!JSON.stringify(config).includes(".etu"));
});

test("explicit original-Admin delta selects a lower base without enabling another release mode", () => {
  const owner = adminCandidateAdmission({ ...valid(), INPUT_CANDIDATE_BASE_VERSION: "3.3.21" });
  assert.equal(owner.baseVersionName, "3.3.21");
  assert.equal(owner.baseVersionCode, 30321);
  assert.equal(adminCandidateAdmission(valid()).baseVersionName, null);
  assert.throws(() => adminCandidateAdmission({ ...valid(), INPUT_CANDIDATE_BASE_VERSION: "3.3.21",
    INPUT_CANDIDATE_FULL_BASE_VERSION: "3.3.20" }));
});

test("registration requires a byte-verified patch with the exact requested base", () => {
  const owner = adminCandidateAdmission({ ...valid(), INPUT_CANDIDATE_BASE_VERSION: "3.3.21" });
  const metadata = { targetImageSha256: "a".repeat(64), assets: [{ kind: "patch", baseVersionCode: 30321, baseImageSha256: "b".repeat(64) }] };
  const preparation = { patchByteEqual: true, base: { provenanceKind: "original-admin-pinned-base-v1",
    versionName: "3.3.21", versionCode: 30321, imageSha256: "b".repeat(64) },
    patchComparison: { baseImageSha256: "b".repeat(64), targetImageSha256: "a".repeat(64) } };
  verifyAdminCandidateAssets(metadata, preparation, owner);
  for (const change of [{ patchByteEqual: false }, { base: { ...preparation.base, versionCode: 30320 } },
    { patchComparison: { ...preparation.patchComparison, targetImageSha256: "c".repeat(64) } }]) {
    assert.throws(() => verifyAdminCandidateAssets(metadata, { ...preparation, ...change }, owner));
  }
  assert.throws(() => verifyAdminCandidateAssets({ ...metadata, assets: [] }, preparation, owner));
  assert.throws(() => verifyAdminCandidateAssets({ ...metadata, assets: [...metadata.assets, ...metadata.assets] }, preparation, owner));
  assert.throws(() => verifyAdminCandidateAssets({ ...metadata, assets: [{ ...metadata.assets[0], baseImageSha256: "c".repeat(64) }] }, preparation, owner));
  assert.throws(() => verifyAdminCandidateAssets(metadata, preparation, adminCandidateAdmission(valid())));
  verifyAdminCandidateAssets({ assets: [] }, { base: null, patchByteEqual: null }, adminCandidateAdmission(valid()));
});
