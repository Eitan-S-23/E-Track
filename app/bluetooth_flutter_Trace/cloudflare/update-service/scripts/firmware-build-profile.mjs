import { readFile } from "node:fs/promises";
import path from "node:path";
import { CliError } from "./firmware-cli.mjs";
import { canonicalJson } from "./firmware-schema.mjs";

const fail = () => new CliError("Firmware build profile/options/compile provenance mismatch", "INVALID_PARAMETER", 1);
const disabled = ["P1_6_TEST_ENABLE", "P2_1_TEST_ENABLE", "P2_2_TEST_ENABLE", "P2_3_TEST_ENABLE", "P2_6_TEST_ENABLE",
  "BOOT_HANDOFF_TEST_INJECT_PENDING", "BOOT_HANDOFF_TEST_CLEAR_BCB"];

export function firmwareBuildProfile(value = "baseline") {
  if (!["baseline", "p34-v2-candidate"].includes(value)) throw new CliError("Unknown firmware build profile");
  return value;
}

export function firmwareCMakeOptions(profile) {
  const candidate = firmwareBuildProfile(profile) === "p34-v2-candidate";
  return { P34_OTA_CANDIDATE: candidate ? "ON" : "OFF", P34_EARLY_FAULT_VECTORS: candidate ? "ON" : "OFF",
    P3_4_LINK_PROFILE: "OFF", P34_OTA_UART_BAUD: "921600",
    ...Object.fromEntries(disabled.map(key => [key, "OFF"])) };
}

function validateDefinitions(definitions, profile) {
  if (!Array.isArray(definitions) || !definitions.length
    || definitions.some(value => typeof value !== "string" || !/^[A-Za-z_]\w*(?:=[^\s"]+)?$/.test(value))
    || new Set(definitions.map(value => value.split("=")[0])).size !== definitions.length) throw fail();
  const values = new Map(definitions.map(value => { const [key, ...rest] = value.split("="); return [key, rest.join("=")]; }));
  if (!values.has("OTA_TARGET_APP") || disabled.some(key => values.has(key))
    || [...values.keys()].some(key => /^OTA_AES_KEY_1_WORD/.test(key))) throw fail();
  for (const key of ["CONFIG_BT_BAUD_EXPERIMENT", "CONFIG_OTA_BLE_PROFILE", "CONFIG_RTT_DEBUG_CMD_ENABLE",
    "CONFIG_OTA_INSTALL_PROFILE", "CONFIG_OTA_INSTALL_COST"]) {
    if (values.has(key) && values.get(key) !== "0") throw fail();
  }
  const candidate = profile === "p34-v2-candidate";
  // These are admission invariants, not another set of compiler flags. CMake
  // remains the sole owner of all candidate tuning definitions.
  for (const key of ["P34_OTA_FIXED_CONFIG", "P34_OTA_PIPELINE", "P34_OTA_PIPELINE_SYNC",
    "P34_OTA_PIPELINE_ACK_BIND", "P34_OTA_PIPELINE_WAIT_RX", "P34_EARLY_FAULT_VECTORS"]) {
    if (candidate ? values.get(key) !== "1" : values.has(key)) throw fail();
  }
  if (candidate && (values.get("CONFIG_BT_FIXED_BAUD") !== "921600u"
    || ["CONFIG_BT_BAUD_EXPERIMENT", "CONFIG_OTA_BLE_PROFILE", "CONFIG_RTT_DEBUG_CMD_ENABLE",
      "CONFIG_OTA_INSTALL_PROFILE", "CONFIG_OTA_INSTALL_COST"].some(key => values.get(key) !== "0"))) throw fail();
}

export function validateBuildConfiguration(value, requestedProfile) {
  const profile = firmwareBuildProfile(requestedProfile ?? value?.requestedProfile);
  if (!value || canonicalJson(Object.keys(value).sort()) !== canonicalJson([
    "schemaVersion", "requestedProfile", "actualProfile", "cmakeOptions", "appCompileDefinitions"].sort())
    || value.schemaVersion !== 1 || value.requestedProfile !== profile || value.actualProfile !== profile
    || canonicalJson(value.cmakeOptions) !== canonicalJson(firmwareCMakeOptions(profile))) throw fail();
  validateDefinitions(value.appCompileDefinitions, profile);
  if (canonicalJson(value.appCompileDefinitions) !== canonicalJson([...value.appCompileDefinitions].sort())) throw fail();
  return value;
}

export function captureBuildConfiguration({ profile, cache, commands }) {
  profile = firmwareBuildProfile(profile);
  const text = cache.toString();
  const option = key => {
    const lines = [...text.matchAll(new RegExp(`^${key}:[^=\\r\\n]+=(.*)\\r?$`, "gm"))];
    if (lines.length !== 1) throw fail();
    return lines[0][1].replace(/\r$/, "");
  };
  if (option("CMAKE_BUILD_TYPE") !== "Release" || option("KEIL_GCC_COMPILER_CACHE") !== "OFF") throw fail();
  const cmakeOptions = Object.fromEntries(Object.keys(firmwareCMakeOptions(profile)).map(key => [key, option(key)]));
  if (!Array.isArray(commands)) throw fail();
  const app = commands.filter(entry => typeof entry.command === "string"
    && entry.command.replaceAll("\\", "/").includes("CMakeFiles/X_Track_App_GCC.dir/"));
  if (!app.length) throw fail();
  const definitions = app.map(entry => {
    const matches = [...entry.command.matchAll(/(?:^|\s)-D([A-Za-z_]\w*(?:=[^\s"]+)?)(?=\s|$)/g)];
    if (matches.length !== [...entry.command.matchAll(/(?:^|\s)-D/g)].length) throw fail();
    return matches.map(match => match[1]).sort();
  });
  for (const list of definitions) {
    validateDefinitions(list, profile);
    if (canonicalJson(list) !== canonicalJson(definitions[0])) throw fail();
  }
  return validateBuildConfiguration({ schemaVersion: 1, requestedProfile: profile,
    actualProfile: cmakeOptions.P34_OTA_CANDIDATE === "ON" ? "p34-v2-candidate" : "baseline",
    cmakeOptions, appCompileDefinitions: definitions[0] }, profile);
}

export async function readBuildConfiguration(directory, profile) {
  return captureBuildConfiguration({ profile, cache: await readFile(path.join(directory, "CMakeCache.txt")),
    commands: JSON.parse(await readFile(path.join(directory, "compile_commands.json"), "utf8")) });
}

export function verifyBuildConfiguration(build, profile) {
  if (!build?.buildConfiguration) throw fail();
  return validateBuildConfiguration(build.buildConfiguration, profile);
}
