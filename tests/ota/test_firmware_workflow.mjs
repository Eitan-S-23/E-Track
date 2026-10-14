import assert from "node:assert/strict";
import { execFileSync, spawnSync } from "node:child_process";
import { mkdir, mkdtemp, readFile } from "node:fs/promises";
import path from "node:path";
import { fileURLToPath } from "node:url";
import { test } from "node:test";
import { outputPath, writeOutput } from "../../app/bluetooth_flutter_Trace/cloudflare/update-service/scripts/firmware-cli.mjs";

const root = fileURLToPath(new URL("../../", import.meta.url));
const python = process.env.PYTHON ?? (process.platform === "win32" ? "python" : "python3");
const text = await readFile(path.join(root, ".github/workflows/firmware-build.yml"), "utf8");
// BaseLoader preserves YAML's "on" key rather than YAML 1.1's boolean alias.
const workflow = JSON.parse(execFileSync(python, ["-B", "-c",
  "import json,sys,yaml; print(json.dumps(yaml.load(sys.stdin, Loader=yaml.BaseLoader)))"],
  { cwd: root, input: text, encoding: "utf8", windowsHide: true }));
const production = workflow.jobs["register-cloudflare"];
const rehearsal = workflow.jobs["rehearse-cloudflare"];
const normalize = value => value.trim().replace(/\s+/g, " ");

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
    assert.equal(job.steps.filter(step => JSON.stringify(step.env ?? {}).includes("secrets.")).length, 1);
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
  ["production wrong approval", production, { OTA_BOOT_CHAIN_READY: "true", INPUT_APPROVED_REHEARSAL_RUN_ID: "9002" }, 2],
  ["production approved shell gate only", production, { OTA_BOOT_CHAIN_READY: "true" }, 0],
  ["rehearsal locked", rehearsal, { OTA_BOOT_CHAIN_READY: "false" }, 0],
  ["rehearsal unlocked", rehearsal, { OTA_BOOT_CHAIN_READY: "true" }, 1],
  ["rehearsal cannot publish", rehearsal, { OTA_BOOT_CHAIN_READY: "false", INPUT_PUBLISH: "true" }, 1],
  ["rehearsal retry binds original attempt", rehearsal, { OTA_BOOT_CHAIN_READY: "false", GITHUB_RUN_ATTEMPT: "2" }, 0]
];
for (const [label, job, override, expected] of cases) test(`actual shell gate: ${label}`, async () => {
  const parent = outputPath(root, path.join(root, ".cache/firmware-workflow-tests"));
  await mkdir(parent, { recursive: true });
  const dir = await mkdtemp(path.join(parent, "gate-"));
  const output = outputPath(root, path.join(dir, "github-output.txt"));
  await writeOutput(root, output, "");
  const environment = { ...process.env, OTA_BOOT_CHAIN_READY: "false", INPUT_PUBLISH: "false", INPUT_REHEARSAL: "false",
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
