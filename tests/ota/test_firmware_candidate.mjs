import assert from "node:assert/strict";
import { mkdir, mkdtemp, readFile, access } from "node:fs/promises";
import path from "node:path";
import { fileURLToPath } from "node:url";
import { spawnSync } from "node:child_process";
import { test } from "node:test";
import { candidateAdmission, cleanupCandidate, redactCandidate } from "../../.github/scripts/firmware-candidate.mjs";
import { outputPath, writeOutput } from "../../app/bluetooth_flutter_Trace/cloudflare/update-service/scripts/firmware-cli.mjs";
import { firmwareKeyBinding, verifyBuildKeyBinding } from "../../app/bluetooth_flutter_Trace/cloudflare/update-service/scripts/firmware-release-key.mjs";

const root = fileURLToPath(new URL("../../", import.meta.url));
const fixtures = outputPath(root, path.join(root, ".cache/p51-packaging-impl-20261104-01/node-tests"));
const env = () => ({ GITHUB_ACTIONS: "true", GITHUB_EVENT_NAME: "workflow_dispatch", GITHUB_REPOSITORY: "Eitan-S-23/E-Track",
  GITHUB_SHA: "a".repeat(40), INPUT_CANDIDATE_REVIEWED_COMMIT: "a".repeat(40),
  GITHUB_RUN_ID: "123", GITHUB_RUN_ATTEMPT: "1", INPUT_PACKAGE_CANDIDATE: "true", INPUT_PUBLISH: "false",
  INPUT_REHEARSAL: "false", INPUT_CHECK_BINDINGS: "false", OTA_BOOT_CHAIN_READY: "false",
  INPUT_VERSION_NAME: "3.3.16", INPUT_FIRMWARE_BUILD_PROFILE: "p34-v2-candidate" });

test("pure admission accepts only the explicit artifact-only context (host fixture, no CI execution)", () => {
  assert.equal(candidateAdmission(env()).runId, "123");
});

test("actual CLI rejects a non-dispatch host before any candidate inputs or private key use", () => {
  const result = spawnSync(process.execPath, [path.join(root, ".github/scripts/firmware-candidate.mjs"), "gate"],
    { cwd: root, env: { ...process.env, GITHUB_EVENT_NAME: "push" }, encoding: "utf8", windowsHide: true, timeout: 15000 });
  assert.equal(result.status, 2, result.stderr);
  assert.match(JSON.parse(result.stderr).message, /artifact-only dispatch/);
});
for (const [name, value] of [["GITHUB_ACTIONS", "false"], ["GITHUB_EVENT_NAME", "push"], ["GITHUB_REPOSITORY", "other/repo"],
  ["GITHUB_SHA", "b".repeat(40)], ["INPUT_CANDIDATE_REVIEWED_COMMIT", ""], ["INPUT_PACKAGE_CANDIDATE", "false"],
  ["INPUT_PUBLISH", "true"], ["INPUT_REHEARSAL", "true"], ["INPUT_CHECK_BINDINGS", "true"],
  ["OTA_BOOT_CHAIN_READY", "true"], ["INPUT_VERSION_NAME", "3.3.15"], ["INPUT_FIRMWARE_BUILD_PROFILE", "baseline"],
  ["GITHUB_RUN_ID", "0"], ["GITHUB_RUN_ATTEMPT", ""], ["TRACE_DEPLOY_TOKEN", "fixture-no-credential"],
  ["GITHUB_TOKEN", "fixture-no-credential"]]) test(`admission rejects ${name}`, () => {
    assert.throws(() => candidateAdmission({ ...env(), [name]: value }));
  });

test("exact key binding rejects development, absent and different keys without disclosure", () => {
  const key = "bc".repeat(16), different = "de".repeat(16);
  const build = { keyBinding: firmwareKeyBinding(key, "approved-ci-key-v1") };
  verifyBuildKeyBinding(build, { OTA_AES_KEY: key });
  for (const value of [undefined, "01".repeat(16), "00".repeat(16), different]) {
    assert.throws(() => verifyBuildKeyBinding(build, { OTA_AES_KEY: value }), error => {
      if (value) assert.ok(!error.message.includes(value));
      return true;
    });
  }
  assert.throws(() => verifyBuildKeyBinding({ keyBinding: { ...build.keyBinding, source: "development-ci-key-v1" } }, { OTA_AES_KEY: key }));
});

test("failure diagnostics redact full key and emitted word fragments, retaining other evidence", () => {
  const key = "0123456789abcdef0123456789abcdef";
  const result = redactCandidate(`compile error: ${key} 0x01234567u 0x89ABCDEFu`, key);
  assert.equal(result, "compile error: [REDACTED_KEY] 0x[REDACTED_KEY]u 0x[REDACTED_KEY]u");
  assert.equal(redactCandidate("0123456789AbCdEf0123456789abcdef 0x89AbCdEfu", "0123456789AbCdEf0123456789abcdef"),
    "[REDACTED_KEY] 0x[REDACTED_KEY]u");
});

test("private cleanup is owner-bound, removes native key products and is idempotent", async () => {
  await mkdir(fixtures, { recursive: true });
  const fixtureRoot = await mkdtemp(path.join(fixtures, "cleanup-"));
  const privateDir = path.join(fixtureRoot, ".cache/p51-candidate/private");
  const owner = candidateAdmission(env());
  await writeOutput(fixtureRoot, path.join(privateDir, "owner.json"), JSON.stringify(owner));
  await writeOutput(fixtureRoot, path.join(privateDir, "key.h"), "nonsecret fixture");
  await writeOutput(fixtureRoot, path.join(privateDir, "tmp/compiler.s"), "nonsecret fixture");
  await assert.rejects(cleanupCandidate(fixtureRoot, { ...env(), GITHUB_RUN_ID: "124" }), /different/);
  await access(path.join(privateDir, "key.h"));
  await writeOutput(fixtureRoot, path.join(privateDir, "native-active.json"), "{}");
  await assert.rejects(cleanupCandidate(fixtureRoot, env()), /unconfirmed/);
  const { unlink } = await import("node:fs/promises");
  await unlink(outputPath(fixtureRoot, path.join(privateDir, "native-active.json")));
  assert.deepEqual(await cleanupCandidate(fixtureRoot, env()), { privateAbsent: true });
  await assert.rejects(access(privateDir));
  assert.deepEqual(await cleanupCandidate(fixtureRoot, env()), { privateAbsent: true });
});

test("workflow candidate path has exactly one protected secret and an explicit upload allowlist", async () => {
  const text = await readFile(path.join(root, ".github/workflows/firmware-build.yml"), "utf8");
  const job = text.split("  package-candidate:\n")[1].split("  release-development-checks:\n")[0];
  assert.match(job, /environment: firmware-rehearsal/);
  assert.match(job, /contents: read/);
  assert.equal((job.match(/secrets\./g) ?? []).length, 1);
  assert.match(job, /secrets\.FIRMWARE_REHEARSAL_OTA_AES_KEY/);
  assert.ok(job.indexOf("firmware-candidate.mjs gate") < job.indexOf("secrets."));
  assert.ok(job.indexOf("firmware-candidate.mjs inputs") < job.indexOf("secrets."));
  assert.doesNotMatch(job, /firmware-release.mjs|wrangler|TRACE_|CLOUDFLARE_|arm-none-eabi|needs:/);
  const upload = job.split("name: p51-candidate-")[1];
  assert.match(upload, /candidate-metadata.json/);
  assert.doesNotMatch(upload, /private|key\.h|decoder|path: \.cache\/p51-candidate\/\s*$/m);
  assert.match(job, /always\(\) && steps.cleanup.outcome == 'success'/);
});

test("candidate-only excludes all original jobs, while mixed modes still reach the failing candidate gate", async () => {
  const text = (await readFile(path.join(root, ".github/workflows/firmware-build.yml"), "utf8")).replaceAll("\r\n", "\n");
  for (const name of ["build", "release-development-checks", "register-cloudflare", "rehearse-cloudflare", "check-firmware-bindings"]) {
    const block = text.split(`\n  ${name}:\n`)[1].split(/\n  [a-z][a-z-]+:\n/)[0];
    assert.match(block, /if:[\s\S]*?github.event.inputs.package_candidate != 'true'/);
  }
  const candidate = text.split("\n  package-candidate:\n")[1].split("\n  release-development-checks:\n")[0];
  assert.match(candidate, /if: github.event_name == 'workflow_dispatch' && github.event.inputs.package_candidate == 'true'\n/);
  assert.doesNotMatch(candidate, /FIRMWARE_REHEARSAL_P51_PACKAGING_COMMIT/);
});
