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
