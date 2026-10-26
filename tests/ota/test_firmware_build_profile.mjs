import assert from "node:assert/strict";
import { spawnSync } from "node:child_process";
import { readFile } from "node:fs/promises";
import { fileURLToPath } from "node:url";
import path from "node:path";
import { test } from "node:test";
import { captureBuildConfiguration, firmwareBuildProfile, firmwareCMakeOptions, validateBuildConfiguration,
  verifyBuildConfiguration } from "../../app/bluetooth_flutter_Trace/cloudflare/update-service/scripts/firmware-build-profile.mjs";
import { verifyReferenceBuild } from "../../app/bluetooth_flutter_Trace/cloudflare/update-service/scripts/prepare-firmware-release.mjs";

const root = fileURLToPath(new URL("../../", import.meta.url));
const source = await readFile(path.join(root, "MDK-ARM_F435/cmake-generated/CMakeLists.txt"), "utf8");
const block = source.match(/if\(P34_OTA_CANDIDATE\)([\s\S]*?)\nendif\(\)/)[1];
// Use the existing CMake-owned tuning definitions, not a parallel profile table.
const candidateDefinitions = block.match(/target_compile_definitions\(X_Track_App_GCC PRIVATE([\s\S]*?)\n\s*\)/)[1]
  .trim().split(/\s+/).map(value => value.replace("${P34_OTA_UART_BAUD}", "921600"));

function inputs(profile = "baseline") {
  const options = firmwareCMakeOptions(profile);
  const cache = "CMAKE_BUILD_TYPE:STRING=Release\nKEIL_GCC_COMPILER_CACHE:STRING=OFF\n" +
    Object.entries(options).map(([key, value]) => `${key}:STRING=${value}\n`).join("");
  const defs = ["OTA_TARGET_APP", ...(profile === "baseline" ? [] : [...candidateDefinitions, "P34_EARLY_FAULT_VECTORS=1"])];
  const command = file => `arm-none-eabi-gcc ${defs.map(value => "-D" + value).join(" ")} ` +
    `-include "fixture/private-key.h" -o CMakeFiles/X_Track_App_GCC.dir/${file}.obj`;
  return { profile, cache, commands: [{ file: "ota_keys.c", command: command("ota_keys.c") },
    { file: "HAL_Bluetooth.cpp", command: command("HAL_Bluetooth.cpp") }] };
}

test("baseline default and CMake candidate invariants stay explicit", () => {
  assert.equal(firmwareBuildProfile(), "baseline");
  assert.equal(firmwareCMakeOptions().P34_OTA_CANDIDATE, "OFF");
  assert.match(source, /option\(P34_OTA_CANDIDATE[^\n]* OFF\)/);
  assert.match(block, /P3_4_LINK_PROFILE OR NOT P34_EARLY_FAULT_VECTORS/);
  assert.match(block, /message\(FATAL_ERROR/);
  for (const value of ["P34_OTA_PIPELINE_WAIT_RX=1", "CONFIG_BT_BAUD_EXPERIMENT=0", "CONFIG_RTT_DEBUG_CMD_ENABLE=0"]) {
    assert.ok(candidateDefinitions.includes(value));
  }
  const baseline = captureBuildConfiguration(inputs());
  assert.equal(baseline.actualProfile, "baseline");
  assert.deepEqual(baseline.appCompileDefinitions, ["OTA_TARGET_APP"]);
});

test("actual cache and every App recipe establish the candidate configuration", () => {
  const observed = captureBuildConfiguration(inputs("p34-v2-candidate"));
  assert.equal(observed.requestedProfile, "p34-v2-candidate");
  assert.equal(observed.actualProfile, "p34-v2-candidate");
  assert.equal(observed.cmakeOptions.P34_EARLY_FAULT_VECTORS, "ON");
  assert.equal(observed.cmakeOptions.P3_4_LINK_PROFILE, "OFF");
  assert.deepEqual(validateBuildConfiguration(observed), observed);
  assert.ok(observed.appCompileDefinitions.includes("P34_EARLY_FAULT_VECTORS=1"));
});

for (const value of ["", "unknown", "p34-qualified-v1", "p34-v2-candidate --development", null, 1]) {
  test(`unknown profile rejects (${JSON.stringify(value)})`, () => {
    assert.throws(() => firmwareBuildProfile(value), /Unknown firmware/);
  });
}

for (const [key, value] of [["P34_OTA_CANDIDATE", "OFF"], ["P34_EARLY_FAULT_VECTORS", "OFF"],
  ["P3_4_LINK_PROFILE", "ON"], ["P34_OTA_UART_BAUD", "460800"], ["P34_OTA_UART_BAUD", "invalid"],
  ["P2_6_TEST_ENABLE", "ON"], ["BOOT_HANDOFF_TEST_CLEAR_BCB", "ON"], ["CMAKE_BUILD_TYPE", "Debug"],
  ["KEIL_GCC_COMPILER_CACHE", "ccache"]]) {
  test(`contradictory CMake ${key}=${value} rejects`, () => {
    const input = inputs("p34-v2-candidate");
    input.cache = input.cache.replace(new RegExp(`^${key}:.*$`, "m"), `${key}:STRING=${value}`);
    assert.throws(() => captureBuildConfiguration(input), /provenance mismatch/);
  });
}

test("missing or duplicated CMake evidence cannot be replaced by a workflow label", () => {
  const input = inputs("p34-v2-candidate");
  for (const cache of ["", input.cache + "P34_OTA_CANDIDATE:BOOL=ON\n",
    input.cache.replace(/P34_EARLY_FAULT_VECTORS:.*\n/, "")]) {
    assert.throws(() => captureBuildConfiguration({ ...input, cache }));
  }
  assert.throws(() => captureBuildConfiguration({ ...input, commands: [] }));
  assert.throws(() => captureBuildConfiguration({ ...input, commands: inputs().commands }));
});

for (const change of ["-DP34_OTA_PIPELINE_WAIT_RX=0", "-DCONFIG_BT_BAUD_EXPERIMENT=1",
  "-DCONFIG_RTT_DEBUG_CMD_ENABLE=1", "-DP2_6_TEST_ENABLE=1", "-DOTA_AES_KEY_1_WORD0=1",
  '-D"CONFIG_BT_BAUD_EXPERIMENT=1"']) {
  test(`a conflicting recipe flag rejects (${change})`, () => {
    const input = inputs("p34-v2-candidate"); input.commands[1].command += " " + change;
    assert.throws(() => captureBuildConfiguration(input));
  });
}

test("a per-source App definition change cannot be hidden by checking only ota_keys.c", () => {
  const input = inputs("p34-v2-candidate"); input.commands[1].command += " -DFIXTURE_DIFFERENCE=1";
  assert.throws(() => captureBuildConfiguration(input));
});

test("same-source profile changes, old unbound builds and preparation run drift reject reference reuse", () => {
  const baseline = { commitSha: "a".repeat(40), versionName: "3.2.90", keyBinding: "fixture-only",
    buildConfiguration: captureBuildConfiguration(inputs()) };
  const candidate = { ...baseline, buildConfiguration: captureBuildConfiguration(inputs("p34-v2-candidate")) };
  const reference = JSON.stringify({ build: baseline, runId: "123" });
  verifyReferenceBuild(baseline, reference, "123");
  assert.throws(() => verifyReferenceBuild(candidate, reference, "123"), /differs/);
  assert.throws(() => verifyReferenceBuild(baseline, reference, "124"), /differs/);
  assert.throws(() => verifyReferenceBuild(baseline, JSON.stringify({ build: { commitSha: baseline.commitSha }, runId: "123" }), "123"));
  assert.throws(() => verifyBuildConfiguration({}, "p34-v2-candidate"));
  assert.throws(() => verifyBuildConfiguration(baseline, "p34-v2-candidate"));
});

test("real protected build CLI rejects an unknown selector before any native compile or key use", () => {
  const result = spawnSync(process.execPath, [path.join(root, ".github/scripts/firmware-gcc-keyed-build.mjs"),
    "--profile", "unknown", "--version", "3.2.90", "--build-dir", ".cache/never-created-build",
    "--evidence-dir", ".cache/never-created-evidence"], { cwd: root, encoding: "utf8", windowsHide: true,
    env: { ...process.env, GITHUB_SHA: "a".repeat(40), GITHUB_RUN_ID: "123", GITHUB_RUN_ATTEMPT: "1" }, timeout: 15000 });
  assert.equal(result.status, 2, result.stderr);
  assert.match(JSON.parse(result.stderr).message ?? JSON.parse(result.stderr).error, /Unknown firmware/);
});
