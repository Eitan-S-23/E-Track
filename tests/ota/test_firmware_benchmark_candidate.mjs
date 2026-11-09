import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import test from "node:test";
import { candidateAdmission, candidateMode, UI_BASELINE } from "../../.github/scripts/firmware-candidate-context.mjs";
import { verifyCandidateCheckout } from "../../.github/scripts/firmware-candidate.mjs";

const config = JSON.parse(readFileSync(new URL("../../Tools/ota/p51-benchmark-inputs.json", import.meta.url)));
const source = "a".repeat(40);
const env = {
  GITHUB_ACTIONS: "true", GITHUB_EVENT_NAME: "workflow_dispatch", GITHUB_REPOSITORY: "Eitan-S-23/E-Track",
  GITHUB_SHA: source, GITHUB_WORKFLOW_SHA: source, INPUT_CANDIDATE_REVIEWED_COMMIT: source,
  GITHUB_RUN_ID: "123", GITHUB_RUN_ATTEMPT: "1", GITHUB_REF: "refs/heads/benchmark",
  GITHUB_WORKFLOW_REF: "Eitan-S-23/E-Track/.github/workflows/firmware-build.yml@refs/heads/benchmark",
  INPUT_PACKAGE_CANDIDATE: "true", INPUT_PUBLISH: "false", INPUT_REHEARSAL: "false",
  INPUT_CHECK_BINDINGS: "false", INPUT_STAGE_CANDIDATE: "false", OTA_BOOT_CHAIN_READY: "false",
  INPUT_FIRMWARE_BUILD_PROFILE: "p34-v2-candidate", INPUT_CANDIDATE_MODE: "archived-benchmark",
  INPUT_CANDIDATE_BASE_VERSION: config.baseVersion, INPUT_VERSION_NAME: config.targetVersion,
  FIRMWARE_RELEASE_MODE: "artifact-candidate-benchmark",
  FIRMWARE_CANDIDATE_CONTEXT: "firmware-rehearsal/artifact-only-archived-benchmark-v1",
};

test("benchmark has explicit nonpublishing context and finalized pair", () => {
  assert.equal(candidateMode(env), "archived-benchmark");
  assert.deepEqual(candidateAdmission(env), { commitSha: source, runId: "123", runAttempt: "1" });
  const calls = [];
  verifyCandidateCheckout(process.cwd(), env, config, args => {
    calls.push(args);
    return args[0] === "rev-parse" ? source : "";
  });
  assert.equal(config.productSource, UI_BASELINE);
  assert.ok(calls.some(args => args[0] === "merge-base" && args.includes(config.sourceCommit)));
  assert.ok(calls.some(args => args[0] === "status"));
});

for (const [key, value] of Object.entries({ INPUT_PUBLISH: "true", INPUT_REHEARSAL: "true",
  INPUT_STAGE_CANDIDATE: "true", INPUT_CHECK_BINDINGS: "true", OTA_BOOT_CHAIN_READY: "true",
  INPUT_VERSION_NAME: config.baseVersion, INPUT_CANDIDATE_BASE_VERSION: "3.3.18", INPUT_CANDIDATE_FULL_BASE_VERSION: "3.3.17",
  GITHUB_WORKFLOW_SHA: "b".repeat(40), INPUT_CANDIDATE_REVIEWED_COMMIT: "b".repeat(40),
  GITHUB_WORKFLOW_REF: "Eitan-S-23/E-Track/.github/workflows/other.yml@refs/heads/benchmark",
  GITHUB_REF: "refs/tags/benchmark", INPUT_APPROVED_REHEARSAL_RUN_ID: "1", INPUT_RELEASE_NOTES: "release",
  FIRMWARE_RELEASE_MODE: "production", TRACE_DEPLOY_TOKEN: "public-test-double", GH_TOKEN: "public-test-double" })) {
  test(`benchmark rejects ${key} drift`, () => assert.throws(() => candidateAdmission({ ...env, [key]: value })));
}

test("benchmark refuses normal-purpose, changed product and dirty checkout", () => {
  const clean = args => args[0] === "rev-parse" ? source : "";
  for (const delta of [{ purpose: "normal-upgrade" }, { representativeFunctionalSample: true },
    { productionPublishable: true }, { baseVersion: "3.3.18" }, { targetVersion: "3.3.19" },
    { productSource: "b".repeat(40) }, { sourceCommit: "unbound" }]) {
    assert.throws(() => verifyCandidateCheckout(process.cwd(), env, { ...config, ...delta }, clean));
  }
  for (const when of [args => args[0] === "diff" && args.length === 3,
    args => args[0] === "diff" && args.includes("USER"), args => args[0] === "status"]) {
    assert.throws(() => verifyCandidateCheckout(process.cwd(), env, config, args => when(args) ? "changed.cpp" : clean(args)));
  }
});

test("forward version drift still fails exact manifest binding", () => {
  const changed = { ...env, INPUT_VERSION_NAME: "3.3.23" };
  assert.deepEqual(candidateAdmission(changed), { commitSha: source, runId: "123", runAttempt: "1" });
  assert.throws(() => verifyCandidateCheckout(process.cwd(), changed, config,
    args => args[0] === "rev-parse" ? source : ""));
});

test("workflow archives truthful benchmark metadata and excludes private material", () => {
  const workflow = readFileSync(new URL("../../.github/workflows/firmware-build.yml", import.meta.url), "utf8");
  const step = workflow.split("- name: Preserve benchmark-only finalized pair and native receipts")[1].split("- name:")[0];
  assert.match(step, /candidate_mode == 'archived-benchmark'/);
  assert.match(step, /steps\.cleanup\.outcome == 'success'/);
  assert.match(step, /prepared\/benchmark-metadata\.json/);
  assert.match(step, /inputs\//);
  assert.doesNotMatch(step, /private\/|key\.h/);
});
