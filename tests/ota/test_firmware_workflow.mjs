import assert from "node:assert/strict";
import { execFileSync, spawnSync } from "node:child_process";
import { mkdir, mkdtemp, readFile } from "node:fs/promises";
import path from "node:path";
import { fileURLToPath } from "node:url";
import { test } from "node:test";
import { outputPath, writeOutput } from "../../app/bluetooth_flutter_Trace/cloudflare/update-service/scripts/firmware-cli.mjs";
import { releaseConfig } from "../../app/bluetooth_flutter_Trace/cloudflare/update-service/scripts/firmware-release-pipeline.mjs";

const root = fileURLToPath(new URL("../../", import.meta.url));
const python = process.env.PYTHON ?? (process.platform === "win32" ? "python" : "python3");
const text = await readFile(path.join(root, ".github/workflows/firmware-build.yml"), "utf8");
// BaseLoader preserves YAML's "on" key rather than YAML 1.1's boolean alias.
const workflow = JSON.parse(execFileSync(python, ["-B", "-c",
  "import json,sys,yaml; print(json.dumps(yaml.load(sys.stdin, Loader=yaml.BaseLoader)))"],
  { cwd: root, input: text, encoding: "utf8", windowsHide: true }));
const production = workflow.jobs["register-cloudflare"];
const rehearsal = workflow.jobs["rehearse-cloudflare"];
const bindings = workflow.jobs["check-firmware-bindings"];
const normalize = value => value.trim().replace(/\s+/g, " ");

// P4-4 checks the actual configuration parser without a build or cloud call.
const p44Fixture = () => ({
  FIRMWARE_RELEASE_MODE: "rehearsal", GITHUB_EVENT_NAME: "workflow_dispatch",
  INPUT_REHEARSAL: "true", INPUT_PUBLISH: "false", INPUT_CHECK_BINDINGS: "false",
  OTA_BOOT_CHAIN_READY: "false", CLOUDFLARE_ACCOUNT_ID: "a".repeat(32),
  TRACE_R2_ACCESS_KEY_ID: "a".repeat(32), TRACE_R2_SECRET_ACCESS_KEY: "b".repeat(64), TRACE_DEPLOY_TOKEN: "p44-noncredential-deploy",
  TRACE_UPDATE_SERVICE_URL: "https://p44-fixture.invalid", TRACE_R2_BUCKET: "e-track-firmware-p41-test-releases",
  OTA_AES_KEY: "bc".repeat(16), GITHUB_TOKEN: "p44-noncredential-github", GITHUB_REPOSITORY: "Eitan-S-23/E-Track",
  GITHUB_SHA: "a".repeat(40), GITHUB_RUN_ID: "123", GITHUB_RUN_ATTEMPT: "1",
  OTA_PREVIOUS_RELEASE_JSON: "{}", TRACE_FIRMWARE_MIN_APP_VERSION_CODE: "0", TRACE_FIRMWARE_MIN_PROTOCOL_VERSION: "1",
});

test("P4-4 actual configuration parser admits its isolated host-only control", () => {
  assert.equal(releaseConfig(p44Fixture()).mode, "rehearsal");
  assert.equal(releaseConfig(p44Fixture()).buildProfile, "baseline");
});

test("P35 explicit protected profile is a baseline-default allowlist passed identically to compiler and release", () => {
  const input = workflow.on.workflow_dispatch.inputs.firmware_build_profile;
  assert.equal(input.type, "choice"); assert.equal(input.default, "baseline");
  assert.deepEqual(input.options, ["baseline", "p34-v2-candidate"]);
  for (const job of [production, rehearsal]) {
    const build = job.steps.find(step => step.id === "keyed_build");
    const release = job.steps.find(step => step.id === "release_execute");
    assert.equal(build.env.INPUT_FIRMWARE_BUILD_PROFILE, "${{ github.event.inputs.firmware_build_profile }}");
    assert.equal(release.env.INPUT_FIRMWARE_BUILD_PROFILE, build.env.INPUT_FIRMWARE_BUILD_PROFILE);
    assert.match(build.run, /--profile "\$INPUT_FIRMWARE_BUILD_PROFILE"/);
    assert.doesNotMatch(build.run, /\$\{\{[^}]*inputs\./);
  }
  assert.equal(releaseConfig({ ...p44Fixture(), INPUT_FIRMWARE_BUILD_PROFILE: "p34-v2-candidate" }).buildProfile, "p34-v2-candidate");
  const development = workflow.jobs.build.steps.find(step => step.id === "keyed_development");
  assert.equal(development.env.INPUT_FIRMWARE_BUILD_PROFILE, "${{ github.event.inputs.firmware_build_profile || 'baseline' }}");
  assert.match(development.run, /--development/);
  assert.match(development.run, /--profile "\$INPUT_FIRMWARE_BUILD_PROFILE"/);
  assert.doesNotMatch(JSON.stringify(development.env), /secrets\./);
  for (const value of ["", "unknown", "baseline;exit 0", "P34_OTA_CANDIDATE=ON"]) {
    assert.throws(() => releaseConfig({ ...p44Fixture(), INPUT_FIRMWARE_BUILD_PROFILE: value }), /Unknown firmware/);
  }
});

for (const name of ["CLOUDFLARE_ACCOUNT_ID", "TRACE_R2_ACCESS_KEY_ID", "TRACE_R2_SECRET_ACCESS_KEY", "TRACE_UPDATE_SERVICE_URL", "TRACE_DEPLOY_TOKEN",
  "TRACE_R2_BUCKET", "OTA_AES_KEY", "GITHUB_TOKEN",
  "GITHUB_REPOSITORY", "GITHUB_SHA", "GITHUB_RUN_ID", "GITHUB_RUN_ATTEMPT", "OTA_PREVIOUS_RELEASE_JSON",
  "TRACE_FIRMWARE_MIN_APP_VERSION_CODE", "TRACE_FIRMWARE_MIN_PROTOCOL_VERSION"]) {
  test(`P4-4 missing ${name} fails by name without credential disclosure`, () => {
    const env = p44Fixture(); delete env[name];
    assert.throws(() => releaseConfig(env), error => {
      assert.equal(error.exitCode, 2);
      assert.equal(error.message, `Missing release configuration: ${name}`);
      for (const field of ["TRACE_R2_ACCESS_KEY_ID", "TRACE_R2_SECRET_ACCESS_KEY", "TRACE_DEPLOY_TOKEN", "GITHUB_TOKEN", "OTA_AES_KEY"]) {
        assert.ok(!error.message.includes(p44Fixture()[field]));
      }
      return true;
    });
  });
}

for (const [name, value] of [
  ["TRACE_UPDATE_SERVICE_URL", "http://p44-fixture.invalid"],
  ["TRACE_UPDATE_SERVICE_URL", "https://p44-fixture.invalid/path"],
  ["TRACE_UPDATE_SERVICE_URL", "https://p44-fixture.invalid/?token=p44-query-fixture"],
  ["TRACE_UPDATE_SERVICE_URL", "https://p44-user:p44-password@p44-fixture.invalid"],
  ["CLOUDFLARE_API_TOKEN", "control-plane-not-accepted"], ["TRACE_R2_ACCESS_KEY_ID", "p44 invalid fixture"],
  ["TRACE_R2_SECRET_ACCESS_KEY", "bad-s3-secret"], ["TRACE_DEPLOY_TOKEN", "p44 invalid fixture"],
  ["TRACE_R2_BUCKET", "trace-update-staging-releases"], ["TRACE_D1_DATABASE_ID", "p44-invalid-id"],
  ["GITHUB_SHA", "p44-invalid-source"], ["INPUT_CHECK_BINDINGS", "true"], ["INPUT_PUBLISH", "true"],
]) {
  test(`P4-4 rejects unsafe ${name} configuration (${value.length}) without echoing its value`, () => {
    assert.throws(() => releaseConfig({ ...p44Fixture(), [name]: value }), error => {
      assert.ok(!error.message.includes(value));
      return true;
    });
  });
}

test("production remains explicit dispatch/publish with a first-step hard gate and protected environment", () => {
  assert.equal(normalize(production.if), "github.event_name == 'workflow_dispatch' && github.event.inputs.publish == 'true'");
  assert.equal(production.environment, "firmware-production");
  assert.equal(production.steps[0].id, "gate");
  assert.match(production.steps[0].run, /OTA_BOOT_CHAIN_READY/);
  assert.doesNotMatch(production.if, /OTA_BOOT_CHAIN_READY/);
  assert.deepEqual(production.needs, ["build", "release-development-checks"]);
});

test("rehearsal has only separately named staging secrets and read-only GitHub permissions", () => {
  assert.equal(rehearsal.environment, "firmware-rehearsal");
  assert.equal(rehearsal.permissions.contents, "read");
  assert.match(rehearsal.if, /rehearsal == 'true'/);
  for (const step of rehearsal.steps) for (const value of Object.values(step.env ?? {})) {
    if (String(value).includes("secrets.")) assert.match(value, /secrets\.FIRMWARE_REHEARSAL_/);
  }
});

test("nightly/checks jobs cannot acquire release secrets or execute the cloud pipeline", () => {
  assert.equal(workflow.permissions.contents, "read");
  for (const id of ["build", "release-development-checks"]) {
    const job = workflow.jobs[id];
    assert.equal(job.environment, undefined);
    assert.doesNotMatch(JSON.stringify(job), /secrets\.|firmware-release\.mjs execute|release create|wrangler deploy/);
  }
  assert.equal(workflow.on.workflow_dispatch.inputs.publish.default, "false");
  assert.equal(workflow.on.workflow_dispatch.inputs.rehearsal.default, "false");
  assert.equal(workflow.on.workflow_dispatch.inputs.check_bindings.default, "false");
});

test("binding qualification is a protected explicit check-only Linux job with bounded execution", () => {
  assert.equal(normalize(bindings.if), "github.event_name == 'workflow_dispatch' && github.event.inputs.check_bindings == 'true' && github.event.inputs.publish != 'true' && github.event.inputs.rehearsal != 'true'");
  assert.equal(bindings.environment, "firmware-rehearsal");
  assert.equal(bindings["runs-on"], "ubuntu-latest");
  assert.equal(bindings["timeout-minutes"], "10");
  assert.deepEqual(bindings.permissions, { contents: "read" });
  assert.deepEqual(bindings.needs, ["release-development-checks"]);
  assert.equal(bindings.steps[0].id, "gate");
  const checkout = bindings.steps.find(step => step.uses === "actions/checkout@v4");
  assert.equal(checkout.with.ref, "${{ github.sha }}");
  assert.equal(checkout.with["persist-credentials"], "false");
  assert.match(workflow.concurrency.group, /inputs\.check_bindings/);
  assert.match(workflow.concurrency["cancel-in-progress"], /!inputs\.check_bindings/);
});

test("binding check credentials are confined to readback after dependency installation", () => {
  const run = bindings.steps.find(step => step.id === "bindings_check");
  assert.equal(run["timeout-minutes"], "5");
  assert.equal(run.run, "node .github/scripts/firmware-bindings-check.mjs --output .cache/bindings-check/result.json");
  assert.equal(run.env.FIRMWARE_REHEARSAL_BINDINGS_CHECK_COMMIT, "${{ vars.FIRMWARE_REHEARSAL_BINDINGS_CHECK_COMMIT }}");
  for (const name of ["FIRMWARE_REHEARSAL_BINDINGS_CHECK_METADATA_PATH", "FIRMWARE_REHEARSAL_BINDINGS_CHECK_METADATA_SHA256"]) {
    assert.equal(run.env[name], "${{ vars." + name + " }}");
    assert.equal(bindings.steps[0].env[name], run.env[name]);
  }
  assert.equal(bindings.steps.filter(step => JSON.stringify(step.env ?? {}).includes("secrets.")).length, 1);
  for (const value of Object.values(run.env)) if (value.includes("secrets.")) assert.match(value, /secrets\.FIRMWARE_REHEARSAL_/);
  assert.doesNotMatch(JSON.stringify(bindings), /OTA_AES_KEY|CLOUDFLARE_API_TOKEN|TRACE_D1_DATABASE|OTA_PREVIOUS_RELEASE_JSON|OTA_APPROVED_BOOTSTRAP|firmware-release\.mjs execute|contents.*write/);
  assert.equal(run.env.TRACE_DEPLOY_TOKEN, "${{ secrets.FIRMWARE_REHEARSAL_TRACE_DEPLOY_TOKEN }}");
  const artifact = bindings.steps.find(step => step.uses === "actions/upload-artifact@v4");
  assert.equal(artifact.with["if-no-files-found"], "error");
  assert.equal(artifact.with["retention-days"], "14");
});

test("both release environments use the identical production implementation and same-run App/Boot inputs", () => {
  const run = job => job.steps.find(step => step.id === "release_execute");
  assert.equal(run(production).run, run(rehearsal).run);
  assert.match(run(production).run, /firmware-release\.mjs execute/);
  for (const job of [production, rehearsal]) {
    assert.match(run(job).run, /X-Track-App-GCC.bin/);
    assert.match(run(job).run, /X-Track-Boot.bin/);
    assert.match(run(job).run, /gcc-build-inputs.json/);
    assert.doesNotMatch(run(job).run, /\$\{\{.*(release_notes|version_name)/);
    assert.deepEqual(job.steps.filter(step => JSON.stringify(step.env ?? {}).includes("secrets.")).map(step => step.id),
      ["keyed_build", "release_execute"]);
    assert.ok(job.steps.some(step => step.uses === "actions/download-artifact@v4" && step.with["run-id"]));
  }
  assert.doesNotMatch(text, /--clobber|release edit|delete-asset|wrangler deploy|\/tmp\/etfw/);
  assert.match(workflow.concurrency.group, /'release'/);
  assert.notEqual(workflow.concurrency["cancel-in-progress"], true);
});

test("development wiring explicitly executes host, native, byte and production-GCC paths", () => {
  const checks = workflow.jobs["release-development-checks"].steps.map(step => step.run ?? "").join("\n");
  assert.match(checks, /firmware-scripts.host.test.ts test\/firmware-migration.host.test.ts/);
  assert.match(checks, /p41-host.config.mjs/);
  assert.match(checks, /npm test -- --reporter=verbose/);
  assert.match(checks, /test_firmware_pack.py/);
  assert.match(checks, /PYTHONPATH="\$GITHUB_WORKSPACE\/Tools" python3 -B tests\/ota-vectors\/test_vectors.py/);
  assert.match(checks, /node --test tests\/ota\/test_firmware_release.mjs/);
  const build = workflow.jobs.build.steps.map(step => step.run ?? "").join("\n");
  assert.match(build, /--target X_Track_App_GCC X_Track_Boot/);
  assert.match(build, /firmware-release.mjs capture/);
  assert.match(build, /firmware-release.mjs development/);
  assert.match(build, /firmware-gcc-keyed-build.mjs --development/);
});

test("protected builds and packaging bind the same approved key without exposing cloud credentials to compilation", () => {
  const keyed = job => job.steps.find(step => step.id === "keyed_build");
  assert.equal(keyed(production).run, keyed(rehearsal).run);
  for (const job of [production, rehearsal]) {
    const build = keyed(job), release = job.steps.find(step => step.id === "release_execute");
    assert.equal(build.env.OTA_AES_KEY, release.env.OTA_AES_KEY);
    assert.equal(build["timeout-minutes"], "15");
    assert.match(build.run, /firmware-gcc-keyed-build.mjs/);
    assert.doesNotMatch(build.run, /--development/);
    assert.match(build.run, /trap cleanup_key EXIT/);
    assert.match(build.run, /trap 'exit 130' INT/);
    assert.match(build.run, /trap 'exit 143' TERM/);
    assert.match(build.run, /firmware-gcc-keyed-build.mjs cleanup --build-dir \.cache\/release-gcc/);
    assert.match(release.run, /\.cache\/release\/keyed-build\/gcc-build-inputs.json/);
    assert.doesNotMatch(JSON.stringify(build.env), /CLOUDFLARE_|TRACE_DEPLOY_TOKEN|GITHUB_TOKEN/);
    assert.equal(job.steps.filter(step => step.uses === "carlosperate/arm-none-eabi-gcc-action@v1")[0].with.release, "13.3.Rel1");
    assert.ok(job.steps.indexOf(build) < job.steps.indexOf(release));
    const cleanup = job.steps.find(step => step.id === "key_cleanup");
    const archive = job.steps.find(step => step.uses === "actions/upload-artifact@v4");
    assert.match(cleanup.if, /always\(\)/);
    assert.equal(cleanup.run, "node .github/scripts/firmware-gcc-keyed-build.mjs cleanup --build-dir .cache/release-gcc");
    assert.equal(archive.if, "always() && steps.key_cleanup.outcome == 'success'");
    assert.ok(job.steps.indexOf(cleanup) < job.steps.indexOf(archive));
  }
  assert.doesNotMatch(text, /OTA_APPROVED_AES_KEY_SHA256/);
});

test("bootstrap approval is explicit environment configuration, never a development default", () => {
  for (const job of [production, rehearsal]) {
    const step = job.steps.find(value => value.id === "release_execute");
    assert.equal(step.env.OTA_APPROVED_BOOTSTRAP_BASELINE_SHA256, "${{ vars.OTA_APPROVED_BOOTSTRAP_BASELINE_SHA256 }}");
  }
  for (const id of ["build", "release-development-checks"]) {
    assert.doesNotMatch(JSON.stringify(workflow.jobs[id]), /OTA_APPROVED_BOOTSTRAP_BASELINE_SHA256/);
  }
});

const workerBundle = workflow.jobs["release-development-checks"].steps.find(step => step.id === "worker_bundle");
function assertBuildOnlyWorkerBundle(step) {
  assert.deepEqual(step.run.trim().split("\n"), [
    "set -euo pipefail",
    'node node_modules/wrangler/bin/wrangler.js deploy --dry-run --outdir "$GITHUB_WORKSPACE/.cache/p41-worker-bundle"',
    'printf \'%s\\n\' "$GITHUB_SHA" > "$GITHUB_WORKSPACE/.cache/p41-worker-bundle/source-commit.txt"',
    'printf \'%s\\n\' \'Build-only input; no deployment or rehearsal performed.\' > "$GITHUB_WORKSPACE/.cache/p41-worker-bundle/purpose.txt"'
  ]);
  assert.equal(step.env.CLOUDFLARE_API_TOKEN, "");
  assert.equal(step.env.CLOUDFLARE_ACCOUNT_ID, "");
  for (const key of ["HOME", "XDG_CONFIG_HOME", "XDG_CACHE_HOME"]) {
    assert.match(step.env[key], /^\$\{\{ github.workspace \}\}\/\.cache\/p41\/worker-/);
  }
}

test("Worker bundle is a credential-free CI build input, not a deployment", () => {
  assertBuildOnlyWorkerBundle(workerBundle);
  const artifact = workflow.jobs["release-development-checks"].steps.find(step =>
    step.uses === "actions/upload-artifact@v4" && step.with.name.startsWith("p41-worker-bundle-"));
  assert.equal(artifact.if, "success() && steps.worker_bundle.outcome == 'success'");
  assert.equal(artifact.with.path, ".cache/p41-worker-bundle/");
  assert.equal(artifact.with["if-no-files-found"], "error");
  assert.equal(artifact.with["retention-days"], "14");
});

test("Worker bundle guard rejects an actual deployment or an injected extra command", () => {
  assert.throws(() => assertBuildOnlyWorkerBundle({ ...workerBundle,
    run: workerBundle.run.replace(" --dry-run", "") }));
  assert.throws(() => assertBuildOnlyWorkerBundle({ ...workerBundle,
    run: workerBundle.run + "\necho unexpected\n" }));
  assert.throws(() => assertBuildOnlyWorkerBundle({ ...workerBundle,
    env: { ...workerBundle.env, CLOUDFLARE_API_TOKEN: "must-not-reach-build" } }));
});

const bash = process.platform === "win32"
  ? path.join(path.dirname(path.dirname(execFileSync("where", ["git"], { encoding: "utf8", windowsHide: true }).trim().split(/\r?\n/)[0])), "bin/bash.exe")
  : "bash";

const version = workflow.jobs.build.steps.find(step => step.id === "version");
test("version inputs use environment mappings rather than shell interpolation", () => {
  for (const [name, input] of [["INPUT_VERSION_NAME", "version_name"], ["INPUT_PUBLISH", "publish"], ["INPUT_REHEARSAL", "rehearsal"]]) {
    assert.equal(version.env[name], `\${{ github.event.inputs.${input} }}`);
  }
  assert.doesNotMatch(version.run, /\$\{\{[^}]*inputs\./);
});

const versionCases = [
  ["legacy source PR", { event: "pull_request" }, "2.7.0-nightly", 20700],
  ["legacy source push", { event: "push" }, "2.7.0-nightly", 20700],
  ["legacy source checks dispatch", {}, "2.7.0", 20700],
  ["explicit formal version", { input: "3.2.7", publish: "true" }, "3.2.7", 30207],
  ["explicit rehearsal version", { input: "3.2.7", rehearsal: "true" }, "3.2.7", 30207],
  ["canonical source formal version", { source: "v3.2.7", publish: "true" }, "3.2.7", 30207],
  ["canonical source rehearsal version", { source: "v3.2.7", rehearsal: "true" }, "3.2.7", 30207],
  ["legacy source cannot choose formal version", { publish: "true" }, null],
  ["legacy source cannot choose rehearsal version", { rehearsal: "true" }, null],
  ["explicit short version", { input: "2.7" }, null],
  ["explicit prefixed version", { input: "v2.7.0" }, null],
  ["leading zero major", { input: "02.7.0" }, null],
  ["leading zero minor", { input: "2.07.0" }, null],
  ["leading zero patch", { input: "2.7.00" }, null],
  ["explicit prerelease suffix", { input: "2.7.0-rc.1", publish: "true" }, null],
  ["explicit nightly suffix", { input: "2.7.0-nightly.1" }, null],
  ["u32 maximum", { input: "429496.72.95", publish: "true" }, "429496.72.95", 4294967295],
  ["u32 overflow", { input: "429496.72.96", publish: "true" }, null],
  ["major overflow", { input: "429497.0.0" }, null],
  ["huge major must not wrap Bash arithmetic", { input: "18446744073709551616.0.0" }, null],
  ["malformed legacy source", { source: "v2.bad" }, null],
  ["leading zero legacy source", { source: "v02.7" }, null],
  ["source prerelease suffix", { source: "v2.7.0-rc.1", rehearsal: "true" }, null]
];
for (const [label, values, expectedName, expectedCode] of versionCases) test(`actual version shell: ${label}`, async () => {
  const parent = outputPath(root, path.join(root, ".cache/firmware-workflow-tests"));
  await mkdir(parent, { recursive: true });
  const dir = await mkdtemp(path.join(parent, "version-"));
  const source = values.source ?? "v2.7";
  const event = values.event ?? "workflow_dispatch";
  await writeOutput(root, path.join(dir, "USER/App/Version.h"), `#define VERSION_SOFTWARE "${source}"\n`);
  const output = outputPath(root, path.join(dir, "github-output.txt"));
  await writeOutput(root, output, "");
  const environment = { ...process.env, GITHUB_EVENT_NAME: event, INPUT_VERSION_NAME: values.input ?? "",
    INPUT_PUBLISH: values.publish ?? "false", INPUT_REHEARSAL: values.rehearsal ?? "false",
    GITHUB_OUTPUT: output.replaceAll("\\", "/") };
  // Render the legacy event expression just as Actions does, so a regression
  // fails for the version decision rather than Bash's "bad substitution".
  const script = version.run.replaceAll("${{ github.event_name }}", event);
  const result = spawnSync(bash, ["--noprofile", "--norc", "-c", script],
    { cwd: dir, env: environment, encoding: "utf8", windowsHide: true, timeout: 15000 });
  const contents = await readFile(output, "utf8");
  await writeOutput(root, path.join(dir, "result.json"), JSON.stringify({ label, source, event, values,
    exitCode: result.status, stdout: result.stdout, stderr: result.stderr, output: contents }, null, 2) + "\n");
  assert.doesNotMatch(result.stderr ?? "", /bad substitution/);
  assert.equal(result.status, expectedName === null ? 1 : 0, result.stdout + result.stderr);
  if (expectedName === null) {
    assert.equal(contents, "");
    assert.match(result.stdout, /::error title=Invalid version::/);
  } else {
    const fields = Object.fromEntries(contents.trim().split(/\r?\n/).map(line => line.split("=")));
    assert.match(fields.build_number, /^[1-9][0-9]*$/);
    assert.equal(fields.version_name, expectedName.endsWith("-nightly") ? `${expectedName}.${fields.build_number}` : expectedName);
    assert.equal(fields.version_code, String(expectedCode));
  }
  process.stdout.write(`VERSION_CASE ${JSON.stringify({ label, exitCode: result.status, output: contents })}\n`);
});

const cases = [
  ["production locked", production, { OTA_BOOT_CHAIN_READY: "false" }, 1],
  ["production missing approval", production, { OTA_BOOT_CHAIN_READY: "true", INPUT_APPROVED_REHEARSAL_RUN_ID: "" }, 2],
  ["production ambiguous mode", production, { OTA_BOOT_CHAIN_READY: "true", INPUT_REHEARSAL: "true" }, 2],
  ["production rejects binding-check mode", production, { OTA_BOOT_CHAIN_READY: "true", INPUT_CHECK_BINDINGS: "true" }, 2],
  ["production wrong approval", production, { OTA_BOOT_CHAIN_READY: "true", INPUT_APPROVED_REHEARSAL_RUN_ID: "9002" }, 2],
  ["production approved shell gate only", production, { OTA_BOOT_CHAIN_READY: "true" }, 0],
  ["rehearsal locked", rehearsal, { OTA_BOOT_CHAIN_READY: "false" }, 0],
  ["rehearsal unlocked", rehearsal, { OTA_BOOT_CHAIN_READY: "true" }, 1],
  ["rehearsal cannot publish", rehearsal, { OTA_BOOT_CHAIN_READY: "false", INPUT_PUBLISH: "true" }, 1],
  ["rehearsal rejects binding-check mode", rehearsal, { INPUT_CHECK_BINDINGS: "true" }, 1],
  ["rehearsal retry binds original attempt", rehearsal, { OTA_BOOT_CHAIN_READY: "false", GITHUB_RUN_ATTEMPT: "2" }, 0],
  ["binding-check locked reviewed source", bindings, { INPUT_CHECK_BINDINGS: "true" }, 0],
  ["binding-check rejects ordinary dispatch", bindings, {}, 2],
  ["binding-check rejects push", bindings, { INPUT_CHECK_BINDINGS: "true", GITHUB_EVENT_NAME: "push" }, 2],
  ["binding-check rejects missing gate", bindings, { INPUT_CHECK_BINDINGS: "true", OTA_BOOT_CHAIN_READY: "" }, 2],
  ["binding-check rejects unlocked gate", bindings, { INPUT_CHECK_BINDINGS: "true", OTA_BOOT_CHAIN_READY: "true" }, 2],
  ["binding-check rejects publication", bindings, { INPUT_CHECK_BINDINGS: "true", INPUT_PUBLISH: "true" }, 2],
  ["binding-check rejects rehearsal", bindings, { INPUT_CHECK_BINDINGS: "true", INPUT_REHEARSAL: "true" }, 2],
  ["binding-check rejects absent reviewed source", bindings, { INPUT_CHECK_BINDINGS: "true", FIRMWARE_REHEARSAL_BINDINGS_CHECK_COMMIT: "" }, 2],
  ["binding-check rejects absent preflight source", bindings, { INPUT_CHECK_BINDINGS: "true", FIRMWARE_REHEARSAL_BINDINGS_CHECK_METADATA_PATH: "" }, 2],
  ["binding-check rejects absent preflight hash", bindings, { INPUT_CHECK_BINDINGS: "true", FIRMWARE_REHEARSAL_BINDINGS_CHECK_METADATA_SHA256: "" }, 2],
  ["binding-check rejects invalid preflight hash", bindings, { INPUT_CHECK_BINDINGS: "true", FIRMWARE_REHEARSAL_BINDINGS_CHECK_METADATA_SHA256: "A".repeat(64) }, 2],
  ["binding-check rejects changed source", bindings, { INPUT_CHECK_BINDINGS: "true", GITHUB_SHA: "b".repeat(40) }, 2],
  ["binding-check rejects another repository", bindings, { INPUT_CHECK_BINDINGS: "true", GITHUB_REPOSITORY: "Eitan-S-23/Trace" }, 2]
];
for (const [label, job, override, expected] of cases) test(`actual shell gate: ${label}`, async () => {
  const parent = outputPath(root, path.join(root, ".cache/firmware-workflow-tests"));
  await mkdir(parent, { recursive: true });
  const dir = await mkdtemp(path.join(parent, "gate-"));
  const output = outputPath(root, path.join(dir, "github-output.txt"));
  await writeOutput(root, output, "");
  const environment = { ...process.env, OTA_BOOT_CHAIN_READY: "false", INPUT_PUBLISH: "false", INPUT_REHEARSAL: "false",
    INPUT_CHECK_BINDINGS: "false", GITHUB_EVENT_NAME: "workflow_dispatch", GITHUB_REPOSITORY: "Eitan-S-23/E-Track",
    GITHUB_SHA: "a".repeat(40), FIRMWARE_REHEARSAL_BINDINGS_CHECK_COMMIT: "a".repeat(40),
    FIRMWARE_REHEARSAL_BINDINGS_CHECK_METADATA_PATH: "reviewed/preflight.json",
    FIRMWARE_REHEARSAL_BINDINGS_CHECK_METADATA_SHA256: "b".repeat(64),
    INPUT_APPROVED_REHEARSAL_RUN_ID: "9001", OTA_APPROVED_REHEARSAL_RUN_ID: "9001", OTA_APPROVED_REHEARSAL_ATTEMPT: "1",
    GITHUB_RUN_ID: "9001", GITHUB_RUN_ATTEMPT: "1", GITHUB_OUTPUT: output.replaceAll("\\", "/"), ...override };
  const result = spawnSync(bash, ["--noprofile", "--norc", "-c", job.steps[0].run],
    { cwd: root, env: environment, encoding: "utf8", windowsHide: true, timeout: 15000 });
  await writeOutput(root, path.join(dir, "result.json"), JSON.stringify({ label, exitCode: result.status,
    stdout: result.stdout, stderr: result.stderr, output: await readFile(output, "utf8") }, null, 2) + "\n");
  assert.equal(result.status, expected, result.stderr);
  if (expected !== 0) assert.equal(await readFile(output, "utf8"), "");
  if (label.includes("retry")) assert.match(await readFile(output, "utf8"), /reference_attempt=1/);
  process.stdout.write(`GATE_CASE ${JSON.stringify({ label, exitCode: result.status })}\n`);
});

test("actual execute CLI rejects a checks context with exit 2 before any cloud path", async () => {
  const parent = outputPath(root, path.join(root, ".cache/firmware-workflow-tests"));
  await mkdir(parent, { recursive: true });
  const dir = await mkdtemp(path.join(parent, "cli-"));
  const manifest = path.join(dir, "inputs.json"); await writeOutput(root, manifest, "{}");
  const args = [path.join(root, ".github/scripts/firmware-release.mjs"), "execute", "--app", path.join(dir, "X-Track-App-GCC.bin"),
    "--boot", path.join(dir, "X-Track-Boot.bin"), "--build-inputs", manifest, "--output-dir", path.join(dir, "not-created")];
  const result = spawnSync(process.execPath, args, { cwd: root, encoding: "utf8", windowsHide: true,
    env: { ...process.env, GITHUB_EVENT_NAME: "push", FIRMWARE_RELEASE_MODE: "rehearsal" }, timeout: 15000 });
  assert.equal(result.status, 2, result.stderr); assert.equal(JSON.parse(result.stderr).errorCode, "INVALID_PARAMETER");
  await writeOutput(root, path.join(dir, "rejected.stderr.txt"), result.stderr);
});
