import assert from "node:assert/strict";
import { mkdir, mkdtemp, readFile, access } from "node:fs/promises";
import path from "node:path";
import { fileURLToPath } from "node:url";
import { spawnSync } from "node:child_process";
import { test } from "node:test";
import { candidateAdmission, cleanupCandidate, redactCandidate, verifyCandidateCheckout, buildSourceCandidate } from "../../.github/scripts/firmware-candidate.mjs";
import { candidateMode, UI_BASELINE } from "../../.github/scripts/firmware-candidate-context.mjs";
import { buildKeyedFirmware, cleanupPrivateBuildKey } from "../../.github/scripts/firmware-gcc-keyed-build.mjs";
import { firmwareCMakeOptions } from "../../app/bluetooth_flutter_Trace/cloudflare/update-service/scripts/firmware-build-profile.mjs";
import { outputPath, writeOutput } from "../../app/bluetooth_flutter_Trace/cloudflare/update-service/scripts/firmware-cli.mjs";
import { firmwareKeyBinding, verifyBuildKeyBinding } from "../../app/bluetooth_flutter_Trace/cloudflare/update-service/scripts/firmware-release-key.mjs";

const root = fileURLToPath(new URL("../../", import.meta.url));
const fixtures = outputPath(root, path.resolve(root, process.env.P51_TEST_AREA || ".cache/p51-packaging-impl-20261104-01/node-tests"));
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
  assert.doesNotMatch(job, /firmware-release.mjs|wrangler|TRACE_|CLOUDFLARE_|needs:/);
  assert.match(job, /Install contained Arm GNU Toolchain for new-source only\n        if: github.event.inputs.candidate_mode == 'new-source'/);
  assert.match(job, /sha256sum --check/);
  const upload = job.split("name: p51-candidate-")[1];
  assert.match(upload, /candidate-metadata.json/);
  assert.doesNotMatch(upload, /private|key\.h|decoder|path: \.cache\/p51-candidate\/\s*$/m);
  assert.match(job, /always\(\) && steps.cleanup.outcome == 'success'/);
});

const sourceEnv = () => ({ ...env(), INPUT_CANDIDATE_MODE: "new-source",
  INPUT_CANDIDATE_BASE_VERSION: "3.4.1", INPUT_VERSION_NAME: "3.4.2",
  FIRMWARE_RELEASE_MODE: "artifact-candidate",
  FIRMWARE_CANDIDATE_CONTEXT: "firmware-rehearsal/artifact-only-new-source-v1",
  GITHUB_REF: "refs/heads/fixture-only",
  GITHUB_WORKFLOW_SHA: "a".repeat(40),
  GITHUB_WORKFLOW_REF: "Eitan-S-23/E-Track/.github/workflows/firmware-build.yml@refs/heads/fixture-only" });
const config = JSON.parse(await readFile(path.join(root, "Tools/ota/p51-new-source-inputs.json")));
const gitDouble = argv => argv[0] === "rev-parse" ? "a".repeat(40)
  : argv[0] === "show" ? "1790000000" : "";

const supplementEnv = () => ({ ...sourceEnv(), INPUT_CANDIDATE_MODE: "start-state-supplement",
  INPUT_VERSION_NAME: "3.3.19", INPUT_CANDIDATE_BASE_VERSION: "",
  FIRMWARE_RELEASE_MODE: "artifact-candidate-supplement",
  FIRMWARE_CANDIDATE_CONTEXT: "firmware-rehearsal/artifact-only-start-state-v1" });
const supplementConfig = JSON.parse(await readFile(path.join(root, "Tools/ota/p51-start-state-inputs.json")));
test("supplement is explicit and distinguishes immutable original compilation from actual workflow", async () => {
  const e = supplementEnv();
  assert.equal(candidateMode(e), "start-state-supplement");
  assert.equal(candidateAdmission(e).commitSha, e.GITHUB_SHA);
  assert.notEqual(e.GITHUB_SHA, supplementConfig.sourceCommit);
  verifyCandidateCheckout(root, e, supplementConfig, gitDouble);
  let calls = 0;
  await assert.rejects(buildSourceCandidate({ root, env: e, config: supplementConfig, git: gitDouble,
    build: async () => { calls++; } }), /Only new-source/);
  assert.equal(calls, 0);
  assert.throws(() => verifyCandidateCheckout(root, e, supplementConfig, () => "wrong checkout"));
});
for (const [name,value] of [["INPUT_PUBLISH","true"],["INPUT_REHEARSAL","true"],["INPUT_CHECK_BINDINGS","true"],
  ["OTA_BOOT_CHAIN_READY","true"],["INPUT_VERSION_NAME","3.3.18"],["INPUT_CANDIDATE_BASE_VERSION","3.3.18"],
  ["INPUT_CANDIDATE_FULL_BASE_VERSION","3.3.17"],["FIRMWARE_RELEASE_MODE","production"],
  ["FIRMWARE_CANDIDATE_CONTEXT","firmware-rehearsal/artifact-only-new-source-v1"],
  ["GITHUB_WORKFLOW_SHA",supplementConfig.sourceCommit],["GITHUB_WORKFLOW_REF","wrong/workflow"],
  ["GITHUB_EVENT_NAME","push"],["GITHUB_TOKEN","fixture"],["INPUT_CANDIDATE_REVIEWED_COMMIT","b".repeat(40)]]) {
  test(`supplement rejects mixed/unbound input ${name}`, () => {
    assert.throws(() => candidateAdmission({ ...supplementEnv(), [name]:value }));
  });
}
test("supplement uploads only explicit new FULL assets, metadata and safe evidence after cleanup", async () => {
  const text=await readFile(path.join(root,".github/workflows/firmware-build.yml"),"utf8");
  const job=text.split("  package-candidate:\n")[1].split("  release-development-checks:\n")[0];
  const upload=job.split("      - name: Preserve only supplemental initialization assets and receipts\n")[1];
  assert.ok(upload);
  assert.match(upload,/steps.cleanup.outcome == 'success'/);
  assert.match(upload,/candidate_mode == 'start-state-supplement'/);
  const paths=upload.split("          path: |\n")[1].split("          include-hidden-files:")[0].trim().split("\n").map(s=>s.trim());
  assert.deepEqual(paths,[".cache/p51-candidate/prepared/initialize-30317-full.etu",
    ".cache/p51-candidate/prepared/initialize-30318-full.etu",".cache/p51-candidate/prepared/supplement-metadata.json",
    ".cache/p51-candidate/evidence/",".cache/p51-candidate/inputs/manifest.json",
    ".cache/p51-candidate/inputs/supplement-build.json",".cache/p51-candidate/inputs/supplement-source.json"]);
  assert.doesNotMatch(paths.join("\n"),/private|decoder|key\.h|keyed-build/);
});

test("new and archived modes are explicit; synthetic new-source context binds workflow separately", () => {
  assert.equal(candidateMode(env()), "archived-original");
  assert.equal(candidateMode(sourceEnv()), "new-source");
  assert.equal(candidateAdmission(sourceEnv()).commitSha, "a".repeat(40));
  assert.equal(candidateAdmission({ ...sourceEnv(), INPUT_CANDIDATE_FULL_BASE_VERSION: "3.4.0" }).runId, "123");
  for (const full of ["3.3.16", "3.4.1", "3.4.2", "3.4.3", "3.4.0-x"]) {
    assert.throws(() => candidateAdmission({ ...sourceEnv(), INPUT_CANDIDATE_FULL_BASE_VERSION: full }));
  }
  assert.throws(() => candidateAdmission({ ...env(), INPUT_CANDIDATE_MODE: "new-source" }));
  assert.throws(() => candidateAdmission({ ...sourceEnv(), INPUT_CANDIDATE_MODE: "archived-original" }));
});
for (const [name, value] of [
  ["INPUT_CANDIDATE_MODE", "unknown"], ["INPUT_PUBLISH", "true"], ["INPUT_REHEARSAL", "true"],
  ["INPUT_CHECK_BINDINGS", "true"], ["OTA_BOOT_CHAIN_READY", "true"],
  ["FIRMWARE_RELEASE_MODE", "rehearsal"], ["FIRMWARE_RELEASE_MODE", "production"],
  ["FIRMWARE_CANDIDATE_CONTEXT", ""], ["GITHUB_ACTIONS", "false"], ["GITHUB_REPOSITORY", "fork/repo"],
  ["GITHUB_WORKFLOW_SHA", "b".repeat(40)], ["GITHUB_WORKFLOW_REF", "other/workflow@main"],
  ["INPUT_CANDIDATE_REVIEWED_COMMIT", "b".repeat(40)], ["INPUT_FIRMWARE_BUILD_PROFILE", "baseline"],
  ["INPUT_CANDIDATE_BASE_VERSION", "3.3.16"], ["INPUT_CANDIDATE_BASE_VERSION", "3.4.2"],
  ["INPUT_VERSION_NAME", "3.4.0"], ["INPUT_VERSION_NAME", "3.4.2-extra"],
  ["INPUT_VERSION_NAME", "3.100.1"], ["INPUT_VERSION_NAME", "429496.99.99"],
  ["CF_API_TOKEN", "fixture"], ["GH_TOKEN", "fixture"]]) {
  test(`new-source rejects ${name}=${value} before compilation`, () => {
    assert.throws(() => candidateAdmission({ ...sourceEnv(), [name]: value }));
  });
}
test("source validation rejects different checkout, dirty product, unreviewed changes and wrong baseline", () => {
  verifyCandidateCheckout(root, sourceEnv(), config, gitDouble);
  for (const verb of ["rev-parse", "diff", "status", "merge-base"]) {
    assert.throws(() => verifyCandidateCheckout(root, sourceEnv(), config, argv => {
      if (argv[0] === verb) {
        if (verb === "merge-base") throw Error("not ancestor");
        return "different source";
      }
      return gitDouble(argv);
    }));
  }
  assert.throws(() => verifyCandidateCheckout(root, sourceEnv(), { ...config, reviewedProductBaseline: "b".repeat(40) }, gitDouble));
  assert.equal(config.reviewedProductBaseline, UI_BASELINE);
});
test("new-source orchestration actually calls the existing keyed compiler once, not archived input resolution", async () => {
  let calls = 0;
  const key = "bc".repeat(16), keyBinding = firmwareKeyBinding(key, "approved-ci-key-v1");
  const fake = { keyBinding, buildConfiguration: null };
  await assert.rejects(buildSourceCandidate({ root, env: { ...sourceEnv(), OTA_AES_KEY: key }, config,
    git: gitDouble, execute: async () => {}, build: async options => {
      calls++; assert.equal(options.commitSha, "a".repeat(40)); assert.equal(options.versionName, "3.4.2");
      assert.equal(options.profile, "p34-v2-candidate"); assert.equal(options.buildTimestamp, 1790000000);
      return fake;
    } }), /provenance mismatch/);
  assert.equal(calls, 1);
});

test("existing keyed builder supports strict candidate context, captured configuration and private cleanup", async () => {
  await mkdir(fixtures, { recursive: true });
  const dir = await mkdtemp(path.join(fixtures, "source-keyed-"));
  const buildDir = path.join(dir, "gcc"), evidenceDir = path.join(dir, "evidence");
  const e = { ...sourceEnv(), OTA_AES_KEY: "bc".repeat(16) };
  const state = { calls: 0 };
  const execute = async (tool, argv, options) => {
    state.calls++;
    assert.equal(options.env.OTA_AES_KEY, undefined);
    assert.equal(options.env.TEMP, path.join(buildDir, "tmp"));
    if (argv[0] === "-S") {
      assert.equal(tool, "cmake");
      assert.ok(argv.includes("-DP34_OTA_CANDIDATE:BOOL=ON"));
      await writeOutput(root, path.join(buildDir, "CMakeCache.txt"),
        "KEIL_GCC_COMPILER_CACHE:STRING=OFF\nCMAKE_BUILD_TYPE:STRING=Release\n" +
        Object.entries(firmwareCMakeOptions("p34-v2-candidate")).map(([k,v]) => `${k}:STRING=${v}\n`).join(""));
      await writeOutput(root, path.join(buildDir, "CMakeFiles/rules.ninja"), "command = arm-none-eabi-gcc\n");
      const defs = "OTA_TARGET_APP P34_OTA_FIXED_CONFIG=1 P34_OTA_PIPELINE=1 P34_OTA_PIPELINE_SYNC=1 " +
        "P34_OTA_PIPELINE_ACK_BIND=1 P34_OTA_PIPELINE_WAIT_RX=1 P34_EARLY_FAULT_VECTORS=1 CONFIG_BT_FIXED_BAUD=921600u " +
        "CONFIG_BT_BAUD_EXPERIMENT=0 CONFIG_OTA_BLE_PROFILE=0 CONFIG_RTT_DEBUG_CMD_ENABLE=0 CONFIG_OTA_INSTALL_PROFILE=0 CONFIG_OTA_INSTALL_COST=0";
      await writeOutput(root, path.join(buildDir, "compile_commands.json"), JSON.stringify([{
        file: path.join(root, "Libraries/OTA/ota_keys.c"), command: "arm-none-eabi-gcc " +
          defs.split(" ").map(d => "-D" + d).join(" ") + ` -include "${path.join(buildDir,"private-key.h").replaceAll("\\", "/")}" -o CMakeFiles/X_Track_App_GCC.dir/keys.o`
      }]));
    } else if (argv[0] === "--build") {
      assert.equal(await readFile(path.join(buildDir, "private-key.h"), "utf8"),
        Array.from({length:4}, (_,i) => `#define OTA_AES_KEY_1_WORD${i} 0xbcbcbcbcu\n`).join(""));
      for (const [d,n] of [["app-gcc","X-Track-App-GCC"],["boot","X-Track-Boot"]])
        for (const ext of ["elf","map","bin","hex"]) await writeOutput(root, path.join(buildDir,d,n+"."+ext), "compiler double, not firmware");
    }
    return { status: 0, stdout: "", stderr: "", treeCleanupComplete: true };
  };
  const result = await buildSourceCandidate({ root, env: e, config, git: gitDouble, execute,
    build: options => buildKeyedFirmware({ ...options, buildDir, evidenceDir }) });
  assert.equal(state.calls, 3);
  verifyBuildKeyBinding(result, e);
  assert.equal(result.buildConfiguration.actualProfile, "p34-v2-candidate");
  await assert.rejects(access(path.join(buildDir, "private-key.h")));
  const evidence = await readFile(path.join(evidenceDir, "keyed-build-evidence.json"), "utf8");
  assert.ok(!evidence.includes(e.OTA_AES_KEY));
  await assert.rejects(buildKeyedFirmware({ root, buildDir, evidenceDir, env: e,
    versionName: e.INPUT_VERSION_NAME, commitSha: e.GITHUB_SHA, buildTimestamp: 1790000000 }), /bounded executor/);
  for (const mode of ["production", "rehearsal"]) {
    await assert.rejects(buildKeyedFirmware({ root, buildDir, evidenceDir,
      env: { ...e, FIRMWARE_RELEASE_MODE: mode, INPUT_REHEARSAL: mode === "rehearsal" ? "true" : "false",
        INPUT_PUBLISH: mode === "production" ? "true" : "false", OTA_BOOT_CHAIN_READY: mode === "production" ? "true" : "false" },
      versionName: e.INPUT_VERSION_NAME, commitSha: e.GITHUB_SHA, buildTimestamp: 1790000000, execute }), /protected release context/);
  }
});
test("unconfirmed key-build trees block header cleanup and candidate upload cleanup", async () => {
  const dir = await mkdtemp(path.join(fixtures, "active-keyed-"));
  const buildDir = path.join(dir, ".cache/p51cg");
  await writeOutput(dir, path.join(buildDir, "private-key.h"), "fixture");
  await writeOutput(dir, path.join(buildDir, "key-build-active.json"), "{}");
  await assert.rejects(cleanupPrivateBuildKey({ root: dir, buildDir, env: sourceEnv() }), /unconfirmed/);
  await assert.rejects(cleanupCandidate(dir, sourceEnv()), /unconfirmed/);
  await access(path.join(buildDir, "private-key.h"));
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
