#!/usr/bin/env node

import { createHash, createPrivateKey, sign } from "node:crypto";
import { readFile, stat, writeFile } from "node:fs/promises";
import path from "node:path";

const DEFAULT_CAPABILITIES = ["patch", "full", "fallback", "errorCode", "payloadSignature", "vcdiff"];

const options = parseArgs(process.argv.slice(2));
const assetsDir = requiredOption(options, "assets-dir", "TRACE_RELEASE_ASSETS_DIR");
const releaseTag = requiredOption(options, "release-tag", "GITHUB_REF_NAME");
const runId = requiredOption(options, "run-id", "GITHUB_RUN_ID");
const commitSha = requiredOption(options, "commit-sha", "GITHUB_SHA");
const repository = requiredOption(options, "repository", "GITHUB_REPOSITORY");
const output = options.output ?? process.env.TRACE_RELEASE_METADATA_JSON;
const fixedSigningConfigured = parseBoolean(
  options["fixed-signing-configured"] ?? process.env.TRACE_FIXED_SIGNING_CONFIGURED
);
const releaseNotes = await resolveReleaseNotes(options, runId, commitSha);
const minClientVersionCode = parseInteger(
  options["min-client-version-code"] ?? process.env.TRACE_MIN_CLIENT_VERSION_CODE ?? "0",
  "min-client-version-code"
);
const capabilities = parseCapabilities(options.capabilities ?? process.env.TRACE_RELEASE_CAPABILITIES);
const allowPlaceholderSignature = parseBoolean(
  options["allow-placeholder-signature"] ?? process.env.TRACE_ALLOW_PLACEHOLDER_SIGNATURE
);

if (!output) {
  fail("Missing --output or TRACE_RELEASE_METADATA_JSON");
}

const manifestPath = path.join(assetsDir, "ble-monitor-update.json");
const manifest = JSON.parse(await readFile(manifestPath, "utf8"));
const apkAssetName = stringField(manifest, "apkAssetName", "ble-monitor-android.apk");
assertSafeFileName(apkAssetName);
const apkPath = path.join(assetsDir, apkAssetName);
const apkInfo = await fileInfo(apkPath);

if (apkInfo.sha256 !== stringField(manifest, "apkSha256").toLowerCase()) {
  fail(`APK sha256 does not match ${manifestPath}`);
}
if (apkInfo.sizeBytes !== integerField(manifest, "apkSize")) {
  fail(`APK size does not match ${manifestPath}`);
}

const manifestInfo = await fileInfo(manifestPath);
const githubUrlFor = (fileName) =>
  `https://github.com/${repository}/releases/download/${encodeURIComponent(releaseTag)}/${encodeURIComponent(fileName)}`;

const assets = [
  asset("apk", apkAssetName, apkInfo, githubUrlFor(apkAssetName)),
  asset("manifest", "ble-monitor-update.json", manifestInfo, githubUrlFor("ble-monitor-update.json"))
];

const patches = [];
const manifestPatches = Array.isArray(manifest.patches) ? manifest.patches : [];
for (const patch of manifestPatches) {
  const patchAssetName = stringField(patch, "assetName");
  assertSafeFileName(patchAssetName);
  const patchPath = path.join(assetsDir, patchAssetName);
  const patchInfo = await fileInfo(patchPath);
  const patchSha256 = stringField(patch, "sha256").toLowerCase();
  const patchSizeBytes = integerField(patch, "size");

  if (patchInfo.sha256 !== patchSha256) {
    fail(`Patch sha256 does not match manifest for ${patchAssetName}`);
  }
  if (patchInfo.sizeBytes !== patchSizeBytes) {
    fail(`Patch size does not match manifest for ${patchAssetName}`);
  }

  assets.push(asset("patch", patchAssetName, patchInfo, githubUrlFor(patchAssetName)));
  patches.push({
    fromVersionCode: integerField(patch, "fromVersionCode"),
    oldSha256: stringField(patch, "oldSha256").toLowerCase(),
    patchFormat: patchFormatFor(patch, patchAssetName),
    patchAssetName,
    patchSha256,
    patchSizeBytes,
    outputSha256: stringField(patch, "newSha256").toLowerCase(),
    outputSizeBytes: apkInfo.sizeBytes
  });
}

patches.sort((left, right) => {
  if (right.fromVersionCode !== left.fromVersionCode) {
    return right.fromVersionCode - left.fromVersionCode;
  }
  const oldShaCompare = left.oldSha256.localeCompare(right.oldSha256);
  if (oldShaCompare !== 0) return oldShaCompare;
  const formatCompare = patchFormatPriority(left.patchFormat) - patchFormatPriority(right.patchFormat);
  if (formatCompare !== 0) return formatCompare;
  return left.patchAssetName.localeCompare(right.patchAssetName);
});

const securityPayload = {
  appId: "trace",
  platform: "android",
  versionName: stringField(manifest, "versionName"),
  versionCode: integerField(manifest, "versionCode"),
  releaseTag,
  apkAssetName,
  apkSha256: apkInfo.sha256,
  apkSize: apkInfo.sizeBytes,
  patches: patches.map((patch) => ({
    fromVersionCode: patch.fromVersionCode,
    toVersionCode: integerField(manifest, "versionCode"),
    assetName: patch.patchAssetName,
    sha256: patch.patchSha256,
    size: patch.patchSizeBytes,
    oldSha256: patch.oldSha256,
    newSha256: patch.outputSha256
  })),
  assetHashes: assets.map((entry) => ({
    assetType: entry.assetType,
    fileName: entry.fileName,
    sha256: entry.sha256,
    size: entry.sizeBytes
  })),
  minClientVersionCode,
  capabilities
};

const metadata = {
  appId: "trace",
  platform: "android",
  releaseTag,
  runId,
  commitSha,
  versionName: securityPayload.versionName,
  versionCode: securityPayload.versionCode,
  releaseNotes,
  minClientVersionCode,
  capabilities,
  payloadSignature: payloadSignature(securityPayload, allowPlaceholderSignature),
  isFormalRelease: true,
  fixedSigningConfigured,
  assets,
  patches
};

await writeFile(output, `${JSON.stringify(metadata, null, 2)}\n`, "utf8");
process.stdout.write(`Wrote Cloudflare release metadata to ${output}\n`);

function asset(assetType, fileName, info, githubUrl) {
  return {
    assetType,
    fileName,
    sha256: info.sha256,
    sizeBytes: info.sizeBytes,
    githubUrl
  };
}

async function fileInfo(filePath) {
  const [bytes, metadata] = await Promise.all([readFile(filePath), stat(filePath)]);
  return {
    sha256: createHash("sha256").update(bytes).digest("hex"),
    sizeBytes: metadata.size
  };
}

async function resolveReleaseNotes(options, runId, commitSha) {
  if (options["release-notes"] !== undefined) {
    return options["release-notes"];
  }
  const releaseNotesFile = options["release-notes-file"] ?? process.env.TRACE_RELEASE_NOTES_FILE;
  if (releaseNotesFile) {
    return readFile(releaseNotesFile, "utf8");
  }
  if (process.env.TRACE_RELEASE_NOTES !== undefined) {
    return process.env.TRACE_RELEASE_NOTES;
  }
  return `Automated build from workflow run ${runId} for commit ${commitSha}.`;
}

function payloadSignature(securityPayload, allowPlaceholder) {
  const privateKeyBase64 = process.env.TRACE_UPDATE_PAYLOAD_ED25519_PRIVATE_KEY_BASE64;
  const keyVersion = process.env.TRACE_UPDATE_PAYLOAD_KEY_VERSION ?? "default";
  if (privateKeyBase64) {
    const privateKey = createPrivateKey({
      key: Buffer.from(privateKeyBase64, "base64"),
      format: "der",
      type: "pkcs8"
    });
    const signature = sign(null, Buffer.from(canonicalJson(securityPayload), "utf8"), privateKey);
    return {
      algorithm: "ed25519",
      keyVersion,
      signature: signature.toString("base64")
    };
  }

  if (!allowPlaceholder) {
    fail(
      "Missing TRACE_UPDATE_PAYLOAD_ED25519_PRIVATE_KEY_BASE64. " +
        "Pass --allow-placeholder-signature only for staging candidate registration."
    );
  }

  return {
    algorithm: "candidate-placeholder",
    keyVersion: "staging",
    signature: "staging-candidate-registration-only"
  };
}

function canonicalJson(value) {
  if (Array.isArray(value)) {
    return `[${value.map((entry) => canonicalJson(entry)).join(",")}]`;
  }
  if (value && typeof value === "object") {
    return `{${Object.entries(value)
      .filter(([, entryValue]) => entryValue !== undefined)
      .sort(([left], [right]) => left.localeCompare(right))
      .map(([key, entryValue]) => `${JSON.stringify(key)}:${canonicalJson(entryValue)}`)
      .join(",")}}`;
  }
  return JSON.stringify(value);
}

function parseArgs(args) {
  const parsed = {};
  for (let index = 0; index < args.length; index += 1) {
    const arg = args[index];
    if (!arg.startsWith("--")) {
      fail(`Unexpected argument: ${arg}`);
    }
    const key = arg.slice(2);
    if (key === "allow-placeholder-signature") {
      parsed[key] = "true";
      continue;
    }
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

function parseBoolean(value) {
  if (value === true || value === "true") return true;
  if (value === false || value === "false" || value === undefined || value === "") return false;
  fail(`Invalid boolean value: ${value}`);
}

function parseInteger(value, fieldName) {
  const parsed = Number(value);
  if (!Number.isInteger(parsed) || parsed < 0) {
    fail(`${fieldName} must be a non-negative integer`);
  }
  return parsed;
}

function parseCapabilities(value) {
  if (!value) return DEFAULT_CAPABILITIES;
  return value
    .split(",")
    .map((entry) => entry.trim())
    .filter(Boolean);
}

function assertSafeFileName(fileName) {
  if (
    typeof fileName !== "string" ||
    fileName.includes("/") ||
    fileName.includes("\\") ||
    /[\x00-\x1F\x7F]/u.test(fileName) ||
    fileName === "." ||
    fileName === ".." ||
    fileName.trim() === ""
  ) {
    fail(`Invalid asset fileName: ${fileName}`);
  }
}

function stringField(object, fieldName, defaultValue) {
  const value = object[fieldName] ?? defaultValue;
  if (typeof value !== "string" || value.length === 0) {
    fail(`${fieldName} must be a non-empty string`);
  }
  return value;
}

function integerField(object, fieldName) {
  return parseInteger(object[fieldName], fieldName);
}

function patchFormatFor(patch, patchAssetName) {
  const raw = patch.patchFormat ?? patch.algorithm ?? patch.format;
  const value = typeof raw === "string" ? raw.toLowerCase() : "";
  if (value === "vcdiff" || value === "xdelta3") return "vcdiff";
  if (value === "tracepatch" || value === "trace") return "tracepatch";
  if (patchAssetName.endsWith(".vcdiff") || patchAssetName.endsWith(".xdelta")) return "vcdiff";
  return "tracepatch";
}

function patchFormatPriority(value) {
  return value === "tracepatch" ? 0 : 1;
}

function fail(message) {
  process.stderr.write(`${message}\n`);
  process.exit(1);
}
