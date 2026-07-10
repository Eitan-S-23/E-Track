#!/usr/bin/env node

import { createHash } from "node:crypto";
import { readdir, readFile, stat, writeFile } from "node:fs/promises";
import path from "node:path";

const options = parseArgs(process.argv.slice(2));
const assetsDir = path.resolve(requiredOption(options, "assets-dir", "TRACE_FIRMWARE_ASSETS_DIR"));
const firmwareFile = await resolveFirmwareFile(assetsDir, options["firmware-file"]);
const releaseTag = requiredOption(options, "release-tag", "GITHUB_REF_NAME");
const runId = requiredOption(options, "run-id", "GITHUB_RUN_ID");
const commitSha = requiredOption(options, "commit-sha", "GITHUB_SHA");
const repository = options.repository ?? process.env.GITHUB_REPOSITORY ?? "Eitan-S-23/Trace";
const appId = options["app-id"] ?? process.env.TRACE_APP_ID ?? "trace";
const deviceModel = normalizeDeviceModel(requiredOption(options, "device-model", "TRACE_FIRMWARE_DEVICE_MODEL"));
const versionName = normalizeVersionName(requiredOption(options, "version-name", "TRACE_FIRMWARE_VERSION_NAME"));
const versionCode = parseNonNegativeInteger(
  requiredOption(options, "version-code", "TRACE_FIRMWARE_VERSION_CODE"),
  "version-code"
);
const releaseNotes =
  options["release-notes"] ?? process.env.TRACE_FIRMWARE_RELEASE_NOTES ?? process.env.GITHUB_RELEASE_BODY ?? "";
const targetHardware = options["target-hardware"] ?? process.env.TRACE_FIRMWARE_TARGET_HARDWARE ?? "";
const transport = options.transport ?? process.env.TRACE_FIRMWARE_TRANSPORT ?? "ble";
const minAppVersionCode = parseNonNegativeInteger(
  options["min-app-version-code"] ?? process.env.TRACE_FIRMWARE_MIN_APP_VERSION_CODE ?? "0",
  "min-app-version-code"
);
const output = path.resolve(options.output ?? path.join(assetsDir, "cloudflare-firmware-release-metadata.json"));

assertSafePathPart(appId, "appId");
assertSafePathPart(deviceModel, "deviceModel");
assertSafePathPart(releaseTag, "releaseTag");

const info = await fileInfo(firmwareFile);
const fileName = path.basename(firmwareFile);
assertSafeFileName(fileName);

const metadata = {
  appId,
  deviceModel,
  releaseTag,
  runId,
  commitSha,
  versionName,
  versionCode,
  releaseNotes,
  fileName,
  sha256: info.sha256,
  sizeBytes: info.sizeBytes,
  githubUrl: githubReleaseAssetUrl(repository, releaseTag, fileName),
  targetHardware: targetHardware || undefined,
  transport,
  minAppVersionCode,
  isFormalRelease: true,
  r2Backfill: false
};

await writeFile(output, `${JSON.stringify(metadata, null, 2)}\n`, "utf8");
process.stdout.write(`Wrote Cloudflare firmware metadata to ${output}\n`);

async function resolveFirmwareFile(assetsDir, configured) {
  if (configured) {
    const resolved = path.resolve(configured);
    if (path.dirname(resolved) !== assetsDir && !resolved.startsWith(`${assetsDir}${path.sep}`)) {
      fail("--firmware-file must be inside --assets-dir");
    }
    return resolved;
  }

  const entries = await readdir(assetsDir, { withFileTypes: true });
  const candidates = entries
    .filter((entry) => entry.isFile())
    .map((entry) => entry.name)
    .filter((name) => /\.(bin|hex|uf2|dfu)$/i.test(name))
    .sort();
  if (candidates.length !== 1) {
    fail(`Expected exactly one firmware file in ${assetsDir}; found ${candidates.length}`);
  }
  return path.join(assetsDir, candidates[0]);
}

async function fileInfo(filePath) {
  const [bytes, metadata] = await Promise.all([readFile(filePath), stat(filePath)]);
  return {
    sha256: createHash("sha256").update(bytes).digest("hex"),
    sizeBytes: metadata.size
  };
}

function githubReleaseAssetUrl(repository, releaseTag, fileName) {
  return `https://github.com/${repository}/releases/download/${encodeURIComponent(releaseTag)}/${encodeURIComponent(fileName)}`;
}

function normalizeDeviceModel(value) {
  return value.trim().toLowerCase().replace(/\s+/g, "-");
}

function normalizeVersionName(value) {
  return value.trim().replace(/^v/i, "");
}

function parseNonNegativeInteger(value, fieldName) {
  const parsed = Number.parseInt(value, 10);
  if (!Number.isInteger(parsed) || parsed < 0 || String(parsed) !== String(value)) {
    fail(`${fieldName} must be a non-negative integer`);
  }
  return parsed;
}

function assertSafeFileName(fileName) {
  if (
    typeof fileName !== "string" ||
    fileName.includes("/") ||
    fileName.includes("\\") ||
    fileName === "." ||
    fileName === ".." ||
    fileName.trim() === ""
  ) {
    fail(`Invalid firmware fileName: ${fileName}`);
  }
}

function assertSafePathPart(value, fieldName) {
  if (
    typeof value !== "string" ||
    value.includes("/") ||
    value.includes("\\") ||
    value.includes("..") ||
    value.trim() === ""
  ) {
    fail(`${fieldName} contains invalid R2 path characters`);
  }
}

function parseArgs(args) {
  const parsed = {};
  for (let index = 0; index < args.length; index += 1) {
    const arg = args[index];
    if (!arg.startsWith("--")) {
      fail(`Unexpected argument: ${arg}`);
    }
    const key = arg.slice(2);
    const value = args[index + 1];
    if (!value || value.startsWith("--")) {
      fail(`Missing value for --${key}`);
    }
    parsed[key] = value;
    index += 1;
  }
  return parsed;
}

function requiredOption(options, key, envName) {
  const value = options[key] ?? process.env[envName];
  if (!value) fail(`Missing --${key} or ${envName}`);
  return value;
}

function fail(message) {
  process.stderr.write(`${message}\n`);
  process.exit(1);
}
