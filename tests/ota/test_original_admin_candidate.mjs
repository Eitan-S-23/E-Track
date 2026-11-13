import test from "node:test";
import assert from "node:assert/strict";
import { readFile, mkdir, mkdtemp, access } from "node:fs/promises";
import path from "node:path";
import { fileURLToPath } from "node:url";
import { appVersion, automaticCandidateAdmission, candidatePlan, CANDIDATE_BRANCH, dispatchApp,
  githubJson } from "../../.github/scripts/original-admin-candidate.mjs";
import { adminCandidateAdmission } from "../../.github/scripts/firmware-admin-context.mjs";
import { buildKeyedFirmware } from "../../.github/scripts/firmware-gcc-keyed-build.mjs";
import { firmwareCMakeOptions } from "../../app/bluetooth_flutter_Trace/cloudflare/update-service/scripts/firmware-build-profile.mjs";
import { writeOutput, outputPath } from "../../app/bluetooth_flutter_Trace/cloudflare/update-service/scripts/firmware-cli.mjs";

const config = name => ({ schema: "original-admin-automatic-candidates-v1", firmware: { versionName: name, releaseNotes: "Normal full-only candidate" } });
const inputs = () => ({ changed: [], beforeApp: "version: 1.0.76+102\n", afterApp: "version: 1.0.76+102\n",
  beforeFirmware: config("3.3.24"), afterFirmware: config("3.3.24"), source: "a".repeat(40) });
const env = () => ({ GITHUB_ACTIONS: "true", GITHUB_REPOSITORY: "Eitan-S-23/E-Track", GITHUB_EVENT_NAME: "push",
  GITHUB_REF: `refs/heads/${CANDIDATE_BRANCH}`, GITHUB_SHA: "a".repeat(40), GITHUB_RUN_ID: "123", GITHUB_RUN_ATTEMPT: "1" });
const firmware = () => ({ ...env(), FIRMWARE_RELEASE_MODE: "original-admin-candidate", INPUT_PREPARE_ADMIN_CANDIDATE: "true",
  OTA_BOOT_CHAIN_READY: "false", INPUT_FIRMWARE_BUILD_PROFILE: "p34-v2-candidate", INPUT_CANDIDATE_REVIEWED_COMMIT: "a".repeat(40),
  INPUT_PUBLISH: "false", INPUT_REHEARSAL: "false", INPUT_CHECK_BINDINGS: "false", INPUT_PACKAGE_CANDIDATE: "false",
  INPUT_STAGE_CANDIDATE: "false", INPUT_VERSION_NAME: "3.3.25", INPUT_RELEASE_NOTES: "A real new source version" });

test("bootstrap and tooling/docs-only pushes do not rebuild delivered candidates", () => {
  const plan = candidatePlan({ ...inputs(), changed: ["docs/original-admin-candidates.md", ".github/workflows/original-admin-candidate.yml",
    "Simulator/LVGL.Simulator/LVGL.Simulator.vcxproj", "app/bluetooth_flutter_Trace/cloudflare/update-service/scripts/original-app-candidate.template.yml"] });
  assert.equal(plan.app.required, false);
  assert.equal(plan.firmware.required, false);
  assert.equal(plan.channelPublished, false);
  assert.equal(plan.automaticDeltas, false);
});
test("a versioned App edit requests only an App candidate", () => {
  const plan = candidatePlan({ ...inputs(), afterApp: "version: 1.0.77+103\r\n", changed: ["app/bluetooth_flutter_Trace/lib/main.dart"] });
  assert.equal(plan.app.required, true);
  assert.equal(plan.app.versionCode, 103);
  assert.equal(plan.firmware.required, false);
});
test("a versioned firmware edit requests a fresh firmware build", () => {
  const plan = candidatePlan({ ...inputs(), afterFirmware: config("3.3.25"), changed: ["Libraries/OTA/ota_ble_session.c"] });
  assert.equal(plan.firmware.required, true);
  assert.equal(plan.app.required, false);
});
for (const name of ["app/bluetooth_flutter_Trace/lib/main.dart", "app/bluetooth_flutter_Trace/pubspec.lock", "Tools/flutter/ota_link_profile.py", "Libraries/OTA/ota_ble_frame.c", "USER/HAL/HAL_Bluetooth.cpp", "boot/main.c"]) {
  test(`changed build input requires an explicit version increment: ${name}`, () => assert.throws(() => candidatePlan({ ...inputs(), changed: [name] })));
}
for (const change of [{ afterApp: "version: 1.0.75+101\n" }, { afterApp: "version: 1.0.77+102\n" },
  { afterApp: "version: 1.0.76+103\n" }, { afterFirmware: config("3.3.23") }]) {
  test(`reject reused or backward identity: ${JSON.stringify(change)}`, () => assert.throws(() => candidatePlan({ ...inputs(), ...change })));
}
for (const value of ["version: 1.2.3", "version: 1.2.3+01", "version: 1.2.3+999999999999", "version: 1.2.3+103\nversion: 1.2.4+104"]) {
  test(`invalid App version: ${value}`, () => assert.throws(() => appVersion(value)));
}
for (const change of [{ GITHUB_EVENT_NAME: "pull_request" }, { GITHUB_REF: "refs/heads/main" },
  { GITHUB_REPOSITORY: "someone/fork" }, { GITHUB_RUN_ATTEMPT: "2" }, { GITHUB_SHA: "main" }]) {
  test(`untrusted automatic context is rejected: ${JSON.stringify(change)}`, () => assert.throws(() => automaticCandidateAdmission({ ...env(), ...change })));
}
test("new firmware path retains locked production and V2-only admission", () => {
  assert.equal(adminCandidateAdmission(firmware()).versionCode, 30325);
  for (const change of [{ INPUT_VERSION_NAME: "3.3.24" }, { INPUT_CANDIDATE_BASE_VERSION: "3.3.23" },
    { OTA_BOOT_CHAIN_READY: "true" }, { INPUT_PUBLISH: "true" }, { INPUT_FIRMWARE_BUILD_PROFILE: "baseline" }]) {
    assert.throws(() => adminCandidateAdmission({ ...firmware(), ...change }));
  }
});
test("App dispatch sends the exact source to Trace, with no signing secrets or channel", async () => {
  const plan = candidatePlan({ ...inputs(), afterApp: "version: 1.0.77+103" });
  const calls = [];
  const result = await dispatchApp(plan, { ...env(), ORIGINAL_ADMIN_ACTIONS_TOKEN: "test-credential" }, async (route, token, options) => {
    calls.push({ route, token, options });
    return options ? null : route.includes('/git/ref/') ? { object: { sha: "b".repeat(40) } } : { workflow_runs: [] };
  });
  assert.equal(calls.length, 3);
  assert.equal(calls[2].route, "Eitan-S-23/Trace/actions/workflows/build.yml/dispatches");
  assert.deepEqual(calls[2].options.body, { ref: CANDIDATE_BRANCH, inputs: { source_sha: plan.source, source_run: "123", check_only: "false" } });
  assert.equal(result.workflowCommit, "b".repeat(40));
  assert.equal(result.completed, false);
  assert.equal(result.channelPublished, false);
});
test("an existing dispatch is reconciled, never sent twice", async () => {
  const plan = candidatePlan({ ...inputs(), afterApp: "version: 1.0.77+103" });
  let calls = 0;
  await assert.rejects(dispatchApp(plan, { ...env(), ORIGINAL_ADMIN_ACTIONS_TOKEN: "test" }, async () => {
    calls++;
    return { workflow_runs: [{ display_title: `candidate:${plan.source}:123` }] };
  }), /already exists/);
  assert.equal(calls, 1);
});
test("failed or ambiguous HTTP dispatch is not retried and does not expose credentials", async () => {
  let calls = 0;
  await assert.rejects(githubJson("Eitan-S-23/Trace/actions/workflows/build.yml/dispatches", "private-value", {
    method: "POST", body: {}, fetcher: async () => { calls++; return new Response("private-value", { status: 403 }); }
  }), error => !error.message.includes("private-value") && error.message.includes("403"));
  assert.equal(calls, 1);
});
test("both workflow routes keep publication and original secret stores separate", async () => {
  const source = await readFile(new URL("../../.github/workflows/original-admin-candidate.yml", import.meta.url), "utf8");
  const app = await readFile(new URL("../../app/bluetooth_flutter_Trace/cloudflare/update-service/scripts/original-app-candidate.template.yml", import.meta.url), "utf8");
  assert.match(source, /environment: firmware-rehearsal/);
  assert.match(source, /ORIGINAL_ADMIN_ACTIONS_TOKEN/);
  assert.doesNotMatch(source, /ANDROID_RELEASE_KEYSTORE_BASE64/);
  assert.match(app, /repository: Eitan-S-23\/E-Track/);
  assert.match(app, /flutter-version: ["']?3\.47\.9/);
  assert.match(app, /node-version: ["']?24/);
  assert.match(app, /--prerelease --latest=false/);
  assert.equal((app.match(/ota_link_profile\.py --build-profile adaptive-v2-candidate/g) ?? []).length, 2);
  assert.doesNotMatch(app, /dart-define=TRACE_OTA_LINK_PROFILE/);
  assert.doesNotMatch(app, /--clobber|ETRACK_DEV_SIGNING_KEYSTORE|generate-delta|api\/admin\/.*publish/);
  const android = app.slice(app.indexOf("\n  android:"));
  assert.match(android, /sparse-checkout-cone-mode: false/);
  assert.match(android, /minimum=12\*1024\*\*3/);
  assert.match(android, /cache-disabled: true/);
  assert.doesNotMatch(android, /sudo|rm -rf \/usr/);
  assert.match(android, /needs\.windows\.result == 'success' \|\| needs\.admission\.outputs\.resume_android == 'true'/);
});

function resumeFixture() {
  const source = "a".repeat(40), workflow = "b".repeat(40);
  return { source, resume: "456", checkOnly: "false", sourceRun: "123",
    previous: { id: 456, status: "completed", conclusion: "failure", event: "workflow_dispatch", run_attempt: 1,
      head_branch: CANDIDATE_BRANCH, path: ".github/workflows/build.yml", head_sha: workflow,
      display_title: `candidate:${source}:123` },
    jobs: [{ name: "admission", conclusion: "success" }, { name: "windows", conclusion: "success" },
      { name: "android", conclusion: "failure", steps: [{ name: "Build original-backend, original-package, BLE V2 APK",
        status: "in_progress", conclusion: null }] }],
    releases: [{ id: 789, tag_name: "v1.0.77", draft: true, prerelease: true, target_commitish: workflow,
      body: `Original Admin candidate from Eitan-S-23/E-Track@${source}. Not channel publication.`,
      assets: ["ble-monitor-windows.exe", "ble-monitor-windows.zip"].map((name, index) => ({
        id: 100 + index, name, size: 200 + index, state: "uploaded", digest: "sha256:" + String(index).repeat(64) })) }] };
}

async function runAppAdmission(fixture) {
  const template = await readFile(new URL("../../app/bluetooth_flutter_Trace/cloudflare/update-service/scripts/original-app-candidate.template.yml", import.meta.url), "utf8");
  const block = template.match(/          script: \|\n([\s\S]*?)\n      - uses: actions\/checkout@v4/);
  assert.ok(block, "Execute the actual pre-checkout admission script");
  const script = block[1].split("\n").map(line => line.replace(/^            /, "")).join("\n");
  const AsyncFunction = Object.getPrototypeOf(async function () {}).constructor;
  const outputs = {};
  const listReleases = Symbol("list-releases"), listJobs = Symbol("list-jobs");
  const github = { rest: { repos: { listReleases,
    compareCommitsWithBasehead: async () => ({ data: { status: "ahead" } }),
    getContent: async () => ({ data: { content: Buffer.from("version: 1.0.77+103\n").toString("base64") } }) },
    actions: { listJobsForWorkflowRun: listJobs, getWorkflowRun: async ({ repo }) => ({ data: repo === "E-Track"
      ? { event: "push", head_branch: CANDIDATE_BRANCH, head_sha: fixture.source, path: ".github/workflows/original-admin-candidate.yml" }
      : fixture.previous }) } },
    paginate: async operation => operation === listReleases ? fixture.releases : operation === listJobs ? fixture.jobs
      : assert.fail("Unexpected API operation") };
  await new AsyncFunction("github", "context", "core", "process", script)(github,
    { repo: { owner: "Eitan-S-23", repo: "Trace" }, ref: `refs/heads/${CANDIDATE_BRANCH}`, sha: "c".repeat(40) },
    { setOutput: (key, value) => { outputs[key] = value; }, info: () => {} },
    { env: { SOURCE_SHA: fixture.source, SOURCE_RUN: fixture.sourceRun, CHECK_ONLY: fixture.checkOnly,
      RESUME_ANDROID_RUN: fixture.resume, GITHUB_RUN_ATTEMPT: "1" } });
  return outputs;
}

test("Android-only continuation preserves the exact successful Windows draft", async () => {
  const fixture = resumeFixture();
  const outputs = await runAppAdmission(fixture);
  assert.equal(outputs.resume_android, "true");
  assert.equal(outputs.draft_target, fixture.previous.head_sha);
  assert.equal(outputs.draft_id, "789");
  assert.deepEqual(JSON.parse(outputs.windows_assets), fixture.releases[0].assets);
});

test("normal fresh admission remains fresh, and existing unpublished drafts reject it", async () => {
  const fixture = resumeFixture(); fixture.resume = "";
  await assert.rejects(runAppAdmission(fixture), /Version already exists/);
  fixture.releases = [];
  const outputs = await runAppAdmission(fixture);
  assert.equal(outputs.resume_android, "false");
  assert.equal(outputs.draft_target, "c".repeat(40));
});

for (const [name, mutate] of [
  ["checks-only", fixture => { fixture.checkOnly = "true"; }],
  ["invalid run ID", fixture => { fixture.resume = "1e3"; }],
  ["different source", fixture => { fixture.previous.display_title = "candidate:" + "d".repeat(40) + ":123"; }],
  ["different source request", fixture => { fixture.previous.display_title = "candidate:" + fixture.source + ":124"; }],
  ["wrong branch", fixture => { fixture.previous.head_branch = "main"; }],
  ["repeated original run", fixture => { fixture.previous.run_attempt = 2; }],
  ["already successful run", fixture => { fixture.previous.conclusion = "success"; }],
  ["failed Windows build", fixture => { fixture.jobs[1].conclusion = "failure"; }],
  ["successful APK build", fixture => { fixture.jobs[2].steps[0].conclusion = "success"; }],
  ["published draft", fixture => { fixture.releases[0].draft = false; }],
  ["different workflow", fixture => { fixture.releases[0].target_commitish = "e".repeat(40); }],
  ["different draft source", fixture => { fixture.releases[0].body = "unrelated"; }],
  ["already retained APK", fixture => { fixture.releases[0].assets.push({ name: "ble-monitor-android.apk" }); }],
  ["missing Windows digest", fixture => { delete fixture.releases[0].assets[0].digest; }],
  ["duplicate Windows asset", fixture => { fixture.releases[0].assets[1].name = fixture.releases[0].assets[0].name; }],
  ["multiple drafts", fixture => { fixture.releases.push(structuredClone(fixture.releases[0])); }]
]) {
  test(`reject unsafe Android continuation: ${name}`, async () => {
    const fixture = resumeFixture(); mutate(fixture);
    await assert.rejects(runAppAdmission(fixture));
  });
}

test("new protected firmware owner uses the existing keyed GCC builder and cleans its private header", async () => {
  const root = fileURLToPath(new URL("../../", import.meta.url));
  const area = outputPath(root, path.join(root, ".cache/original-admin-tests"));
  await mkdir(area, { recursive: true });
  const dir = await mkdtemp(path.join(area, "keyed-"));
  const buildDir = path.join(dir, "build"), evidenceDir = path.join(dir, "evidence");
  const cmake = await readFile(path.join(root, "MDK-ARM_F435/cmake-generated/CMakeLists.txt"), "utf8");
  const block = cmake.match(/if\(P34_OTA_CANDIDATE\)([\s\S]*?)\nendif\(\)/)[1];
  const defs = ["OTA_TARGET_APP", "P34_EARLY_FAULT_VECTORS=1", ...block.match(/target_compile_definitions\(X_Track_App_GCC PRIVATE([\s\S]*?)\n\s*\)/)[1]
    .trim().split(/\s+/).map(value => value.replace("${P34_OTA_UART_BAUD}", "921600"))];
  let calls = 0;
  const execute = async (tool, argv, options) => {
    calls++;
    assert.equal(options.env.OTA_AES_KEY, undefined);
    if (argv[0] === "-S") {
      await writeOutput(root, path.join(buildDir, "CMakeCache.txt"), "KEIL_GCC_COMPILER_CACHE:STRING=OFF\nCMAKE_BUILD_TYPE:STRING=Release\n"
        + Object.entries(firmwareCMakeOptions("p34-v2-candidate")).map(([k,v]) => `${k}:STRING=${v}\n`).join(""));
      await writeOutput(root, path.join(buildDir, "CMakeFiles/rules.ninja"), "command = arm-none-eabi-gcc\n");
      await writeOutput(root, path.join(buildDir, "compile_commands.json"), JSON.stringify([{
        file: path.join(root, "Libraries/OTA/ota_keys.c"), command: "arm-none-eabi-gcc " + defs.map(v => "-D" + v).join(" ")
          + ` -include "${path.join(buildDir, "private-key.h").replaceAll("\\", "/")}" -o CMakeFiles/X_Track_App_GCC.dir/keys.o` }]));
    } else if (argv[0] === "--build") {
      for (const [dir, name] of [["app-gcc", "X-Track-App-GCC"], ["boot", "X-Track-Boot"]]) {
        for (const ext of ["bin", "hex", "map", "elf"]) await writeOutput(root, path.join(buildDir, dir, name + "." + ext), "Compiler double, never installable firmware");
      }
    }
    return { status: 0, stdout: "", stderr: "" };
  };
  const result = await buildKeyedFirmware({ root, buildDir, evidenceDir, versionName: "3.3.25",
    commitSha: "a".repeat(40), buildTimestamp: 1786320000, env: { ...firmware(), OTA_AES_KEY: "ab".repeat(16) },
    profile: "p34-v2-candidate", execute });
  assert.equal(calls, 3);
  assert.equal(result.buildConfiguration.actualProfile, "p34-v2-candidate");
  assert.equal(result.keyBinding.source, "approved-ci-key-v1");
  await assert.rejects(access(path.join(buildDir, "private-key.h")));
});
