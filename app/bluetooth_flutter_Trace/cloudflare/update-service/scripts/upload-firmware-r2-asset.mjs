#!/usr/bin/env node

import { createHash } from "node:crypto";
import { existsSync } from "node:fs";
import { mkdtemp, readFile, rm, stat, writeFile } from "node:fs/promises";
import { tmpdir } from "node:os";
import path from "node:path";
import { spawn } from "node:child_process";

const options = parseArgs(process.argv.slice(2));
const metadataPath = path.resolve(requiredOption(options, "metadata", "TRACE_FIRMWARE_METADATA_JSON"));
const assetsDir = path.resolve(requiredOption(options, "assets-dir", "TRACE_FIRMWARE_ASSETS_DIR"));
const bucket = requiredOption(options, "bucket", "TRACE_R2_BUCKET");
const outputPath = path.resolve(options.output ?? metadataPath);
const wranglerCwd = path.resolve(options["wrangler-cwd"] ?? "cloudflare/update-service/worker");
const wranglerEnv = options.env ?? "";
const dryRun = parseBoolean(options["dry-run"]);
const skipReadback = parseBoolean(options["skip-readback"]);
const r2Retries = parsePositiveInteger(options["r2-retries"] ?? process.env.TRACE_R2_UPLOAD_RETRIES ?? "3", "r2-retries");
const r2TimeoutMs = parsePositiveInteger(
  options["r2-timeout-ms"] ?? process.env.TRACE_R2_OPERATION_TIMEOUT_MS ?? "300000",
  "r2-timeout-ms"
);

const metadata = JSON.parse(await readFile(metadataPath, "utf8"));
validateMetadata(metadata);

const firmwarePath = path.join(assetsDir, metadata.fileName);
if (path.basename(firmwarePath) !== metadata.fileName) {
  fail(`Firmware fileName must be a plain file name: ${metadata.fileName}`);
}

const localInfo = await fileInfo(firmwarePath);
if (localInfo.sizeBytes !== metadata.sizeBytes) fail(`Local size mismatch for ${metadata.fileName}`);
if (localInfo.sha256 !== metadata.sha256) fail(`Local sha256 mismatch for ${metadata.fileName}`);

const r2Key = r2KeyForFirmware(metadata);
if (dryRun) {
  process.stdout.write(`[dry-run] ${metadata.fileName} -> r2://${bucket}/${r2Key}\n`);
} else {
  await wranglerWithRetry(
    [
      "r2",
      "object",
      "put",
      `${bucket}/${r2Key}`,
      "--file",
      firmwarePath,
      "--remote",
      "--content-type",
      "application/octet-stream",
      "--cache-control",
      "public, max-age=31536000, immutable",
      "--content-disposition",
      `attachment; filename="${contentDispositionFileName(metadata.fileName)}"`,
      "--force"
    ],
    `upload ${metadata.fileName}`
  );

  if (!skipReadback) {
    const tempDir = await mkdtemp(path.join(tmpdir(), "trace-firmware-r2-readback-"));
    const readbackPath = path.join(tempDir, metadata.fileName);
    try {
      await wranglerWithRetry(
        ["r2", "object", "get", `${bucket}/${r2Key}`, "--file", readbackPath, "--remote"],
        `read back ${metadata.fileName}`
      );
      const readbackInfo = await fileInfo(readbackPath);
      if (readbackInfo.sizeBytes !== metadata.sizeBytes) {
        fail(`R2 read-back size mismatch for ${metadata.fileName}`);
      }
      if (readbackInfo.sha256 !== metadata.sha256) {
        fail(`R2 read-back sha256 mismatch for ${metadata.fileName}`);
      }
    } finally {
      await rm(tempDir, { recursive: true, force: true });
    }
  }
}

metadata.r2Key = r2Key;
metadata.r2Verified = true;

await writeFile(outputPath, `${JSON.stringify(metadata, null, 2)}\n`, "utf8");
process.stdout.write(`Wrote R2-verified firmware metadata to ${outputPath}\n`);

async function wrangler(args) {
  const wranglerEntry = wranglerPath();
  const finalArgs = [wranglerEntry, ...args];
  if (wranglerEnv) finalArgs.push("--env", wranglerEnv);
  await run(process.execPath, finalArgs, {
    cwd: wranglerCwd,
    env: sanitizedWranglerEnv()
  });
}

async function wranglerWithRetry(args, label) {
  let lastError;
  for (let attempt = 1; attempt <= r2Retries; attempt += 1) {
    try {
      await wrangler(args);
      return;
    } catch (error) {
      lastError = error;
      if (attempt >= r2Retries) break;
      const delayMs = 2000 * attempt;
      process.stderr.write(`${label} failed on attempt ${attempt}; retrying in ${delayMs}ms...\n`);
      await sleep(delayMs);
    }
  }
  throw lastError;
}

function wranglerPath() {
  const entry = path.join(wranglerCwd, "node_modules", "wrangler", "bin", "wrangler.js");
  if (!existsSync(entry)) {
    fail(`Wrangler is not installed at ${entry}. Run npm ci in ${wranglerCwd} first.`);
  }
  return entry;
}

function run(command, args, options) {
  return new Promise((resolve, reject) => {
    let timedOut = false;
    const child = spawn(command, args, {
      ...options,
      stdio: "inherit",
      shell: false
    });
    const timeout = setTimeout(() => {
      timedOut = true;
      process.stderr.write(`${command} ${args.join(" ")} timed out after ${r2TimeoutMs}ms\n`);
      killProcessTree(child);
    }, r2TimeoutMs);
    child.on("error", reject);
    child.on("exit", (code) => {
      clearTimeout(timeout);
      if (code === 0) {
        resolve();
      } else {
        const reason = timedOut ? `timed out after ${r2TimeoutMs}ms` : `failed with exit code ${code}`;
        reject(new Error(`${command} ${args.join(" ")} ${reason}`));
      }
    });
  });
}

function sanitizedWranglerEnv() {
  const env = { ...process.env };
  for (const name of ["CLOUDFLARE_ACCOUNT_ID", "CLOUDFLARE_API_TOKEN"]) {
    if (typeof env[name] === "string") env[name] = stripBomAndWhitespace(env[name]);
  }
  return env;
}

function stripBomAndWhitespace(value) {
  return value.replace(/^\uFEFF/, "").trim();
}

function killProcessTree(child) {
  if (!child.pid) return;
  if (process.platform === "win32") {
    spawn("taskkill.exe", ["/pid", String(child.pid), "/T", "/F"], {
      stdio: "ignore",
      shell: false
    });
    return;
  }
  child.kill("SIGTERM");
  setTimeout(() => child.kill("SIGKILL"), 5000).unref();
}

function sleep(ms) {
  return new Promise((resolve) => {
    setTimeout(resolve, ms);
  });
}

function validateMetadata(value) {
  if (!value || typeof value !== "object") fail("metadata must be an object");
  if (value.appId !== "trace") fail("only appId trace is supported by this script");
  if (typeof value.deviceModel !== "string" || value.deviceModel.trim() === "") {
    fail("metadata.deviceModel is required");
  }
  if (!Number.isInteger(value.versionCode) || value.versionCode < 0) {
    fail("metadata.versionCode must be a non-negative integer");
  }
  assertSafePathPart(value.appId, "appId");
  assertSafePathPart(value.deviceModel, "deviceModel");
  assertSafePathPart(value.releaseTag, "releaseTag");
  assertSafeFileName(value.fileName);
}

function r2KeyForFirmware(metadata) {
  return `${metadata.appId}/firmware/${metadata.deviceModel}/${metadata.versionCode}-${metadata.releaseTag}/${metadata.fileName}`;
}

async function fileInfo(filePath) {
  const [bytes, metadata] = await Promise.all([readFile(filePath), stat(filePath)]);
  return {
    sha256: createHash("sha256").update(bytes).digest("hex"),
    sizeBytes: metadata.size
  };
}

function contentDispositionFileName(fileName) {
  return fileName.replace(/["\\\r\n]/g, "_");
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
    if (!arg.startsWith("--")) fail(`Unexpected argument: ${arg}`);
    const key = arg.slice(2);
    if (key === "dry-run" || key === "skip-readback") {
      parsed[key] = "true";
      continue;
    }
    const value = args[index + 1];
    if (!value || value.startsWith("--")) fail(`Missing value for --${key}`);
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

function parsePositiveInteger(value, fieldName) {
  const parsed = Number.parseInt(value, 10);
  if (!Number.isInteger(parsed) || parsed < 1 || String(parsed) !== String(value)) {
    fail(`${fieldName} must be a positive integer`);
  }
  return parsed;
}

function fail(message) {
  process.stderr.write(`${message}\n`);
  process.exit(1);
}
