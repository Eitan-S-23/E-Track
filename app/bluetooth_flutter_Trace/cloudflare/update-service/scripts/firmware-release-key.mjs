import { createHash } from "node:crypto";
import { readFileSync } from "node:fs";
import { CliError } from "./firmware-cli.mjs";

const hash = bytes => createHash("sha256").update(bytes).digest("hex");
const keySource = readFileSync(new URL("../../../../../Libraries/OTA/ota_keys.c", import.meta.url));
const defaults = [...keySource.toString("utf8").matchAll(/^#define OTA_AES_KEY_1_WORD([0-3]) 0x([0-9a-fA-F]{8})u\r?$/gm)]
  .sort((a, b) => Number(a[1]) - Number(b[1]));
if (defaults.length !== 4 || defaults.some((value, index) => Number(value[1]) !== index)) {
  throw new CliError("Cannot establish the compiled development-key definition");
}
const knownDevelopmentKeys = new Set([defaults.map(value => value[2]).join("").toLowerCase(), "00".repeat(16), "01".repeat(16)]);
export const DEVELOPMENT_PACKAGING_KEY = "01".repeat(16);

export function firmwareKeyHeader(key) {
  if (!/^[0-9a-fA-F]{32}$/.test(key ?? "")) throw new CliError("OTA_AES_KEY must contain exactly 32 hex characters");
  return Array.from({ length: 4 }, (_, index) =>
    `#define OTA_AES_KEY_1_WORD${index} 0x${key.slice(index * 8, index * 8 + 8).toLowerCase()}u\n`).join("");
}

export function firmwareKeyBinding(key, source) {
  const header = firmwareKeyHeader(key);
  if (!["approved-ci-key-v1", "development-ci-key-v1"].includes(source)) throw new CliError("Unknown firmware key provenance");
  if (source === "approved-ci-key-v1" && knownDevelopmentKeys.has(key.toLowerCase())) {
    throw new CliError("Known development or example AES keys are forbidden in rehearsal and production");
  }
  return { schemaVersion: 1, keyId: 1, source, keySha256: hash(Buffer.from(key, "hex")),
    headerSha256: hash(Buffer.from(header)), keySourceSha256: hash(keySource) };
}

export function validateKeyBinding(value) {
  const keys = ["schemaVersion", "keyId", "source", "keySha256", "headerSha256", "keySourceSha256"];
  if (!value || JSON.stringify(Object.keys(value).sort()) !== JSON.stringify(keys.sort())
    || value.schemaVersion !== 1 || value.keyId !== 1 || !["approved-ci-key-v1", "development-ci-key-v1"].includes(value.source)
    || [value.keySha256, value.headerSha256, value.keySourceSha256].some(v => !/^[0-9a-f]{64}$/.test(v ?? ""))) {
    throw new CliError("Invalid compiled firmware key provenance");
  }
  return value;
}

export function approvedFirmwareKey(env) {
  // Approval belongs to the existing protected environment/secret, not a second hash variable.
  return firmwareKeyBinding(env.OTA_AES_KEY, "approved-ci-key-v1");
}

export function verifyBuildKeyBinding(build, env) {
  const expected = approvedFirmwareKey(env);
  const observed = validateKeyBinding(build.keyBinding);
  if (Object.keys(expected).some(key => observed[key] !== expected[key])) {
    throw new CliError("Compiled App key and packaging key provenance differ or are development-only");
  }
  return expected;
}
