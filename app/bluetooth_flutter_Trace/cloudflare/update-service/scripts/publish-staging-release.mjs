#!/usr/bin/env node

import { randomUUID } from "node:crypto";
import { existsSync } from "node:fs";
import { mkdtemp, readFile, rm, writeFile } from "node:fs/promises";
import { tmpdir } from "node:os";
import path from "node:path";
import { spawn } from "node:child_process";
import { fileURLToPath } from "node:url";

const options = parseArgs(process.argv.slice(2));
const scriptDir = path.dirname(fileURLToPath(import.meta.url));
const releaseTag = requiredOption(options, "release-tag", "TRACE_RELEASE_TAG");
const appId = options["app-id"] ?? "trace";
const platform = options.platform ?? "android";
const channels = parseChannels(options.channels ?? "stable");
const wranglerEnv = options.env ?? "staging";
const database = options.database ?? "trace-update-staging";
const wranglerCwd = options["wrangler-cwd"] ?? "cloudflare/update-service/worker";
const bootstrapSummary = await loadBootstrapSummary(
  options["bootstrap-summary"] ?? path.join(scriptDir, "..", ".bootstrap", "staging-summary.json")
);
const serviceUrl =
  options["service-url"] ??
  process.env.TRACE_UPDATE_SERVICE_URL ??
  bootstrapSummary?.githubSecrets?.TRACE_UPDATE_SERVICE_URL ??
  bootstrapSummary?.workerUrl;
const deployToken = process.env.TRACE_DEPLOY_TOKEN ?? bootstrapSummary?.githubSecrets?.TRACE_DEPLOY_TOKEN;
const bucket =
  options.bucket ?? process.env.TRACE_R2_BUCKET ?? bootstrapSummary?.r2BucketName ?? "trace-update-staging-releases";
const repo = options.repo ?? options.repository ?? process.env.GITHUB_REPOSITORY ?? "";
const dryRun = parseBoolean(options["dry-run"]);
const yes = parseBoolean(options.yes);
const skipBackfill = parseBoolean(options["skip-backfill"]);
const skipPublish = parseBoolean(options["skip-publish"]);
const skipVerify = parseBoolean(options["skip-verify"]);
const skipReadback = parseBoolean(options["skip-readback"]);
const keepAssets = parseBoolean(options["keep-assets"] ?? options["keep-work-dir"]);
const allowPartialR2 = parseBoolean(options["allow-partial-r2"]);
const rollback = parseBoolean(options.rollback);
const releaseNotesOverride = options["release-notes"];
const actorEmail = options["actor-email"] ?? process.env.TRACE_STAGING_ACTOR_EMAIL ?? "staging-script";
const verifyFromVersionCode = parseNonNegativeInteger(
  options["verify-from-version-code"] ?? "31",
  "verify-from-version-code"
);

if (platform !== "android") fail("publish-staging-release currently supports android only");
if (wranglerEnv !== "staging" || database !== "trace-update-staging") {
  fail("This script is staging-only. Use --env staging and --database trace-update-staging.");
}

const tempDir = options["assets-dir"]
  ? null
  : await mkdtemp(path.join(tmpdir(), "trace-staging-publish-"));
const assetsDir = path.resolve(options["assets-dir"] ?? path.join(tempDir, "assets"));
const metadataPath = path.resolve(options.output ?? path.join(assetsDir, "cloudflare-r2-backfill-metadata.json"));

try {
  printPlan();

  if (dryRun) {
    if (!skipBackfill) {
      await runInherit("node", [
        scriptPath("backfill-r2-release.mjs"),
        "--release-tag",
        releaseTag,
        "--dry-run",
        "--bucket",
        bucket,
        "--assets-dir",
        assetsDir,
        "--output",
        metadataPath,
        "--wrangler-cwd",
        wranglerCwd,
        ...(repo ? ["--repo", repo] : []),
        ...(options["bootstrap-summary"] ? ["--bootstrap-summary", options["bootstrap-summary"]] : [])
      ]);
    }
    process.stdout.write("\nDry run only. No GitHub, R2, D1, channel, or manifest writes were performed.\n");
    process.exit(0);
  }

  if (!yes) {
    fail("Pass --yes to backfill R2 assets, register D1, publish channels, and verify latest/download.");
  }
  if (!serviceUrl) {
    fail("Missing staging Worker URL. Set TRACE_UPDATE_SERVICE_URL or keep .bootstrap/staging-summary.json.");
  }
  if (!skipBackfill && !deployToken) {
    fail("Missing TRACE_DEPLOY_TOKEN. Set it in the shell or keep .bootstrap/staging-summary.json.");
  }

  if (!skipBackfill) {
    await runBackfill();
    await registerBackfill(metadataPath);
  }

  const release = await loadRelease();
  const notes = releaseNotesOverride ?? release.release_notes ?? "";
  if (notes.trim() === "") {
    await updateReleaseNotes(
      release,
      `Staging test release ${release.release_tag} (${release.version_name}+${release.version_code}).`
    );
  } else if (releaseNotesOverride !== undefined && releaseNotesOverride !== release.release_notes) {
    await updateReleaseNotes(release, releaseNotesOverride);
  }

  await ensureR2Completeness(release.id);

  if (!skipPublish) {
    for (const channel of channels) {
      await publishChannel(release, channel);
    }
  }

  if (!skipVerify) {
    for (const channel of channels) {
      await verifyLatestAndPatch(release, channel);
    }
  }

  process.stdout.write("\nStaging release publish complete.\n");
  process.stdout.write(`- Release: ${release.release_tag} (${release.version_name}+${release.version_code})\n`);
  process.stdout.write(`- Channels: ${channels.join(", ")}\n`);
  process.stdout.write(`- Worker: ${serviceUrl}\n`);
} finally {
  if (tempDir && !keepAssets) {
    await rm(tempDir, { recursive: true, force: true });
  } else if (keepAssets) {
    process.stdout.write(`\nKept assets directory: ${assetsDir}\n`);
  }
}

function printPlan() {
  process.stdout.write("Cloudflare staging release publish plan\n");
  process.stdout.write(`- Release tag: ${releaseTag}\n`);
  process.stdout.write(`- App/platform: ${appId}/${platform}\n`);
  process.stdout.write(`- Channels: ${channels.join(", ")}\n`);
  process.stdout.write(`- Environment: ${wranglerEnv}\n`);
  process.stdout.write(`- D1 database: ${database}\n`);
  process.stdout.write(`- R2 bucket: ${bucket}\n`);
  process.stdout.write(`- Worker URL set: ${serviceUrl ? "yes" : "no"}\n`);
  process.stdout.write(`- Deploy token set: ${deployToken ? "yes" : "no"}\n`);
  process.stdout.write(`- Assets dir: ${assetsDir}\n`);
  process.stdout.write(`- R2 backfill: ${skipBackfill ? "no" : "yes"}\n`);
  process.stdout.write(`- R2 readback verification: ${skipReadback ? "no" : "yes"}\n`);
  process.stdout.write(`- Require all Android R2 assets: ${allowPartialR2 ? "no" : "yes"}\n`);
  process.stdout.write(`- Publish channels: ${skipPublish ? "no" : "yes"}\n`);
  process.stdout.write(`- Verify public latest/download: ${skipVerify ? "no" : "yes"}\n`);
  process.stdout.write(`- Verify patch from versionCode: ${verifyFromVersionCode}\n`);
  process.stdout.write(`- Dry run: ${dryRun ? "yes" : "no"}\n`);
}

async function runBackfill() {
  const env = {
    ...process.env,
    TRACE_R2_OPERATION_TIMEOUT_MS: process.env.TRACE_R2_OPERATION_TIMEOUT_MS ?? "900000",
    TRACE_R2_UPLOAD_RETRIES: process.env.TRACE_R2_UPLOAD_RETRIES ?? "3",
    TRACE_REGISTER_TIMEOUT_MS: process.env.TRACE_REGISTER_TIMEOUT_MS ?? "60000"
  };
  await runInherit(
    "node",
    [
      scriptPath("backfill-r2-release.mjs"),
      "--release-tag",
      releaseTag,
      "--yes",
      "--skip-register",
      "--bucket",
      bucket,
      "--assets-dir",
      assetsDir,
      "--output",
      metadataPath,
      "--wrangler-cwd",
      wranglerCwd,
      ...(repo ? ["--repo", repo] : []),
      ...(skipReadback ? ["--skip-readback"] : []),
      ...(keepAssets ? ["--keep-assets"] : []),
      ...(options["bootstrap-summary"] ? ["--bootstrap-summary", options["bootstrap-summary"]] : [])
    ],
    { env }
  );
}

async function registerBackfill(filePath) {
  const metadata = JSON.parse(await readFile(filePath, "utf8"));
  metadata.r2Backfill = true;
  await writeFile(filePath, `${JSON.stringify(metadata, null, 2)}\n`, "utf8");

  const body = JSON.stringify(metadata);
  try {
    const response = await fetchWithTimeout(new URL("/api/ci/releases", serviceUrl), {
      method: "POST",
      headers: {
        Authorization: `Bearer ${deployToken}`,
        "Content-Type": "application/json"
      },
      body
    });
    const text = await response.text();
    if (!response.ok) {
      fail(`Cloudflare R2 backfill registration failed: HTTP ${response.status}\n${text}`);
    }
    process.stdout.write(`${text}\n`);
    return;
  } catch (error) {
    const message = error instanceof Error ? error.message : String(error);
    process.stderr.write(`Node registration failed; trying PowerShell fallback. Reason: ${message}\n`);
  }

  if (process.platform !== "win32") {
    fail("Node registration failed and PowerShell fallback is only available on Windows.");
  }

  const psScript = `
$ErrorActionPreference = "Stop"
$headers = @{
  Authorization = "Bearer $env:TRACE_DEPLOY_TOKEN"
  "Content-Type" = "application/json"
}
$body = Get-Content -LiteralPath $env:TRACE_RELEASE_METADATA_JSON -Raw
$response = Invoke-RestMethod -Uri "$env:TRACE_UPDATE_SERVICE_URL/api/ci/releases" -Method Post -Headers $headers -Body $body -TimeoutSec 180
$response | ConvertTo-Json -Depth 10
`;
  const output = await runCapture("powershell.exe", ["-NoProfile", "-Command", psScript], {
    env: {
      ...process.env,
      TRACE_UPDATE_SERVICE_URL: serviceUrl,
      TRACE_DEPLOY_TOKEN: deployToken,
      TRACE_RELEASE_METADATA_JSON: filePath
    }
  });
  process.stdout.write(`${output.trim()}\n`);
}

async function loadRelease() {
  const rows = await d1Rows(
    `
      SELECT id, app_id, platform, version_name, version_code, release_tag, state, archived, release_notes
      FROM releases
      WHERE app_id = ${sqlString(appId)}
        AND platform = ${sqlString(platform)}
        AND release_tag = ${sqlString(releaseTag)}
      LIMIT 1
    `
  );
  const release = rows[0];
  if (!release) fail(`Release ${releaseTag} is not registered in D1.`);
  if (release.state === "disabled") fail(`Release ${releaseTag} is disabled.`);
  if (release.archived === 1) fail(`Release ${releaseTag} is archived.`);
  return release;
}

async function updateReleaseNotes(release, releaseNotes) {
  if (releaseNotes.length > 8000) fail("release notes are longer than 8000 characters");
  const requestId = requestIdFor("notes");
  const beforeJson = canonicalJson({ releaseNotes: release.release_notes ?? "" });
  const afterJson = canonicalJson({ releaseNotes });
  await d1Rows(
    `
      UPDATE releases
      SET release_notes = ${sqlString(releaseNotes)}, updated_at = datetime('now')
      WHERE id = ${sqlString(release.id)};
      INSERT INTO audit_logs (
        id,
        app_id,
        actor,
        actor_type,
        action,
        target_type,
        target_id,
        request_id,
        before_json,
        after_json
      )
      VALUES (
        'audit_' || lower(hex(randomblob(16))),
        ${sqlString(release.app_id)},
        ${sqlString(actorEmail)},
        'system',
        'edit_notes',
        'release',
        ${sqlString(release.id)},
        ${sqlString(requestId)},
        ${sqlString(beforeJson)},
        ${sqlString(afterJson)}
      );
      UPDATE channels
      SET
        revision = revision + 1,
        last_action = 'edit_notes',
        last_actor = ${sqlString(actorEmail)},
        last_actor_type = 'system',
        last_request_id = ${sqlString(requestId)},
        last_before_json = ${sqlString(beforeJson)},
        last_after_json = ${sqlString(afterJson)},
        updated_at = datetime('now')
      WHERE current_release_id = ${sqlString(release.id)}
    `
  );
  release.release_notes = releaseNotes;
  process.stdout.write(`Updated release notes for ${release.release_tag}.\n`);
}

async function ensureR2Completeness(releaseId) {
  const assets = await d1Rows(
    `
      SELECT asset_type, file_name, r2_state, r2_key
      FROM release_assets
      WHERE release_id = ${sqlString(releaseId)}
        AND platform = ${sqlString(platform)}
        AND disabled = 0
      ORDER BY asset_type, file_name
    `
  );
  if (!assets.some((asset) => asset.asset_type === "apk")) {
    fail(`Release ${releaseTag} is missing the Android APK asset row.`);
  }
  const unavailable = assets.filter((asset) => asset.r2_state !== "available" || !asset.r2_key);
  if (unavailable.length > 0) {
    const list = unavailable.map((asset) => `${asset.asset_type}:${asset.file_name}:${asset.r2_state}`).join(", ");
    if (!allowPartialR2) {
      fail(`Not all Android assets are R2 available. Re-run without --skip-backfill or pass --allow-partial-r2. Missing: ${list}`);
    }
    process.stderr.write(`WARN: publishing with partial R2 availability: ${list}\n`);
  }
}

async function publishChannel(release, channelName) {
  const channel = (
    await d1Rows(
      `
        SELECT *
        FROM channels
        WHERE app_id = ${sqlString(appId)}
          AND platform = ${sqlString(platform)}
          AND name = ${sqlString(channelName)}
        LIMIT 1
      `
    )
  )[0];
  if (!channel) fail(`Channel ${channelName} does not exist.`);
  if (channel.disable_latest === 1) fail(`Channel ${channelName} has latest disabled.`);
  if (channel.current_release_id === release.id) {
    process.stdout.write(`Channel ${channelName} already points to ${release.release_tag}.\n`);
    return;
  }

  if (channel.current_release_id && !rollback) {
    const current = (
      await d1Rows(
        `
          SELECT version_code
          FROM releases
          WHERE id = ${sqlString(channel.current_release_id)}
          LIMIT 1
        `
      )
    )[0];
    if (current && release.version_code <= current.version_code) {
      fail(
        `Publishing ${release.release_tag} to ${channelName} would not increase versionCode. ` +
          "Pass --rollback only for an intentional rollback."
      );
    }
  }

  const beforeSnapshot = channelAuditSnapshot(channel);
  const afterSnapshot = { ...beforeSnapshot, current_release_id: release.id };
  const beforeJson = canonicalJson(beforeSnapshot);
  const afterJson = canonicalJson(afterSnapshot);
  const requestId = requestIdFor(`publish_${channelName}`);
  const rows = await d1Rows(
    `
      UPDATE channels
      SET
        current_release_id = ${sqlString(release.id)},
        revision = revision + 1,
        last_action = ${sqlString(rollback ? "rollback" : "publish")},
        last_actor = ${sqlString(actorEmail)},
        last_actor_type = 'system',
        last_request_id = ${sqlString(requestId)},
        last_before_json = ${sqlString(beforeJson)},
        last_after_json = ${sqlString(afterJson)},
        updated_at = datetime('now')
      WHERE id = ${sqlString(channel.id)}
        AND revision = ${Number(channel.revision)}
        AND disable_latest = 0
      RETURNING revision
    `
  );
  if (!rows[0]) {
    const refreshed = (
      await d1Rows(
        `
          SELECT current_release_id, revision
          FROM channels
          WHERE id = ${sqlString(channel.id)}
          LIMIT 1
        `
      )
    )[0];
    if (
      !refreshed ||
      refreshed.current_release_id !== release.id ||
      Number(refreshed.revision) <= Number(channel.revision)
    ) {
      fail(`CAS conflict while publishing ${release.release_tag} to ${channelName}.`);
    }
    process.stdout.write(
      `Published ${release.release_tag} to ${channelName}; revision ${refreshed.revision}.\n`
    );
    return;
  }
  process.stdout.write(
    `Published ${release.release_tag} to ${channelName}; revision ${rows[0].revision}.\n`
  );
}

async function verifyLatestAndPatch(release, channelName) {
  const latestUrl = new URL("/api/public/latest", serviceUrl);
  latestUrl.searchParams.set("appId", appId);
  latestUrl.searchParams.set("platform", platform);
  latestUrl.searchParams.set("channel", channelName);
  latestUrl.searchParams.set("versionCode", String(verifyFromVersionCode));
  latestUrl.searchParams.set("schemaVersion", "2");
  latestUrl.searchParams.set("capabilities", "patch,full,payloadSignature");

  const manifest = await httpGetJson(latestUrl);
  if (manifest.updateAvailable !== true) {
    fail(`Latest API for ${channelName} did not return updateAvailable=true.`);
  }
  if (manifest.releaseTag !== release.release_tag || manifest.versionCode !== release.version_code) {
    fail(
      `Latest API for ${channelName} returned ${manifest.releaseTag}/${manifest.versionCode}, ` +
        `expected ${release.release_tag}/${release.version_code}.`
    );
  }

  const patches = Array.isArray(manifest.patches) ? manifest.patches : [];
  const patch = patches.find((item) => item.fromVersionCode === verifyFromVersionCode);
  if (!patch?.downloadUrl) {
    fail(`Latest manifest for ${channelName} does not include a patch from versionCode ${verifyFromVersionCode}.`);
  }

  const downloaded = await curlDownload(patch.downloadUrl, Number(patch.size), String(patch.sha256));
  const source = headerValue(downloaded.headers, "x-trace-asset-source");
  if (source?.toLowerCase() !== "r2") {
    fail(`Primary patch download for ${channelName} did not come from R2.`);
  }

  if (patch.fallbackUrl) {
    const fallback = await curlHeadersOnlyGet(patch.fallbackUrl);
    const location = headerValue(fallback.headers, "location") ?? "";
    if (location.includes("/latest/download/") || !location.includes(`/releases/download/${release.release_tag}/`)) {
      fail(`Fallback URL for ${channelName} is not a gated immutable GitHub release redirect.`);
    }
  }

  process.stdout.write(
    `Verified ${channelName}: manifest ${release.release_tag}, patch ${verifyFromVersionCode}->${release.version_code}, source=r2.\n`
  );
}

async function httpGetJson(url) {
  try {
    const response = await fetchWithTimeout(url, { method: "GET" });
    const text = await response.text();
    if (!response.ok) fail(`GET ${url.origin}${url.pathname} failed: HTTP ${response.status}\n${text}`);
    return JSON.parse(text);
  } catch (error) {
    const message = error instanceof Error ? error.message : String(error);
    process.stderr.write(`Node fetch failed for latest API; trying curl fallback. Reason: ${message}\n`);
  }

  const output = await runCapture(curlCommand(), ["-sS", "--max-time", "90", url.toString()]);
  return JSON.parse(output);
}

async function curlDownload(url, expectedSize, expectedSha256) {
  const targetDir = await mkdtemp(path.join(tmpdir(), "trace-patch-verify-"));
  const targetPath = path.join(targetDir, "asset.bin");
  try {
    const output = await runCapture(curlCommand(), [
      "-sS",
      "--max-time",
      "180",
      "-D",
      "-",
      "-o",
      targetPath,
      url
    ]);
    const headers = parseHeaders(output);
    const status = statusCode(headers);
    if (status !== 200) fail(`Primary patch download returned HTTP ${status}.`);
    const info = await fileInfo(targetPath);
    if (info.sizeBytes !== expectedSize) {
      fail(`Downloaded patch size mismatch: ${info.sizeBytes} != ${expectedSize}.`);
    }
    if (info.sha256 !== expectedSha256) {
      fail(`Downloaded patch SHA-256 mismatch.`);
    }
    return { headers };
  } finally {
    await rm(targetDir, { recursive: true, force: true });
  }
}

async function curlHeadersOnlyGet(url) {
  const targetDir = await mkdtemp(path.join(tmpdir(), "trace-fallback-verify-"));
  const targetPath = path.join(targetDir, "fallback.bin");
  try {
    const output = await runCapture(curlCommand(), [
      "-sS",
      "--max-time",
      "90",
      "-D",
      "-",
      "-o",
      targetPath,
      url
    ]);
    const headers = parseHeaders(output);
    const status = statusCode(headers);
    if (status !== 302) fail(`Fallback endpoint returned HTTP ${status}, expected 302.`);
    return { headers };
  } finally {
    await rm(targetDir, { recursive: true, force: true });
  }
}

async function d1Rows(sql) {
  const wranglerEntry = wranglerPath();
  const compact = compactSql(sql);
  const args = [
    wranglerEntry,
    "d1",
    "execute",
    database,
    "--remote",
    "--env",
    wranglerEnv
  ];
  const cwd = path.resolve(wranglerCwd);
  let tempDirForSql = "";
  try {
    if (commandLineLength([process.execPath, ...args, "--command", compact]) > 7000) {
      tempDirForSql = await mkdtemp(path.join(tmpdir(), "trace-d1-sql-"));
      const sqlPath = path.join(tempDirForSql, "query.sql");
      await writeFile(sqlPath, `${compact}\n`, "utf8");
      args.push("--file", sqlPath);
    } else {
      args.push("--command", compact);
    }

    const output = await runCapture(process.execPath, args, { cwd });
    const parsed = parseWranglerJson(output);
    if (!Array.isArray(parsed) || parsed.length === 0) return [];
    const failed = parsed.find((entry) => entry.success === false);
    if (failed) fail(`D1 command failed: ${JSON.stringify(failed)}`);
    const last = parsed[parsed.length - 1];
    return Array.isArray(last.results) ? last.results : [];
  } finally {
    if (tempDirForSql) {
      await rm(tempDirForSql, { recursive: true, force: true });
    }
  }
}

function commandLineLength(parts) {
  return parts.reduce((total, part) => total + String(part).length + 3, 0);
}

function channelAuditSnapshot(channel) {
  return {
    id: channel.id,
    app_id: channel.app_id,
    platform: channel.platform,
    name: channel.name,
    current_release_id: channel.current_release_id,
    revision: channel.revision,
    disable_latest: channel.disable_latest,
    disable_downloads: channel.disable_downloads,
    maintenance_message: channel.maintenance_message ?? ""
  };
}

function wranglerPath() {
  const entry = path.join(path.resolve(wranglerCwd), "node_modules", "wrangler", "bin", "wrangler.js");
  if (!existsSync(entry)) {
    fail(`Wrangler is not installed at ${entry}. Run npm ci in ${wranglerCwd}.`);
  }
  return entry;
}

async function fileInfo(filePath) {
  const { createHash } = await import("node:crypto");
  const { stat, readFile: readFileBytes } = await import("node:fs/promises");
  const [bytes, metadata] = await Promise.all([readFileBytes(filePath), stat(filePath)]);
  return {
    sha256: createHash("sha256").update(bytes).digest("hex"),
    sizeBytes: metadata.size
  };
}

async function fetchWithTimeout(url, init) {
  const controller = new AbortController();
  const timeout = setTimeout(() => controller.abort(), 90000);
  try {
    return await fetch(url, { ...init, signal: controller.signal });
  } finally {
    clearTimeout(timeout);
  }
}

function scriptPath(fileName) {
  return path.join(scriptDir, fileName);
}

function runInherit(command, args, optionsForRun = {}) {
  return new Promise((resolve, reject) => {
    const child = spawn(commandForPlatform(command), args, {
      ...optionsForRun,
      stdio: "inherit",
      shell: false
    });
    child.on("error", reject);
    child.on("exit", (code) => {
      if (code === 0) resolve();
      else reject(new Error(`${command} ${args.join(" ")} failed with exit code ${code}`));
    });
  });
}

function runCapture(command, args, optionsForRun = {}) {
  return new Promise((resolve, reject) => {
    const child = spawn(commandForPlatform(command), args, {
      ...optionsForRun,
      stdio: ["ignore", "pipe", "pipe"],
      shell: false
    });
    let stdout = "";
    let stderr = "";
    child.stdout.on("data", (chunk) => {
      stdout += chunk;
    });
    child.stderr.on("data", (chunk) => {
      stderr += chunk;
    });
    child.on("error", reject);
    child.on("exit", (code) => {
      if (code === 0) resolve(stdout);
      else reject(new Error(`${command} ${args.join(" ")} failed with exit code ${code}\n${stderr}`));
    });
  });
}

function commandForPlatform(command) {
  if (process.platform !== "win32") return command;
  if (command === "node") return "node.exe";
  if (command === "git") return "git.exe";
  return command;
}

function curlCommand() {
  return process.platform === "win32" ? "curl.exe" : "curl";
}

async function loadBootstrapSummary(filePath) {
  try {
    const content = await readFile(filePath, "utf8");
    const summary = JSON.parse(content);
    return summary && typeof summary === "object" ? summary : null;
  } catch {
    return null;
  }
}

function parseWranglerJson(output) {
  const text = stripAnsi(output);
  for (let index = 0; index < text.length; index += 1) {
    if (text[index] !== "[") continue;
    const candidate = extractJsonArray(text, index);
    if (!candidate) continue;
    try {
      return JSON.parse(candidate);
    } catch {
      // Keep scanning; Wrangler warnings also contain square brackets.
    }
  }
  fail(`Could not parse Wrangler JSON output:\n${text}`);
}

function extractJsonArray(text, start) {
  let depth = 0;
  let inString = false;
  let escaped = false;
  for (let index = start; index < text.length; index += 1) {
    const char = text[index];
    if (inString) {
      if (escaped) {
        escaped = false;
      } else if (char === "\\") {
        escaped = true;
      } else if (char === "\"") {
        inString = false;
      }
      continue;
    }
    if (char === "\"") {
      inString = true;
      continue;
    }
    if (char === "[") depth += 1;
    if (char === "]") {
      depth -= 1;
      if (depth === 0) return text.slice(start, index + 1);
    }
  }
  return "";
}

function stripAnsi(value) {
  return value.replace(/\u001b\[[0-9;]*m/g, "");
}

function compactSql(sql) {
  return sql
    .split("\n")
    .map((line) => line.trim())
    .filter(Boolean)
    .join(" ");
}

function sqlString(value) {
  return `'${String(value).replace(/'/g, "''")}'`;
}

function canonicalJson(value) {
  if (Array.isArray(value)) return `[${value.map((item) => canonicalJson(item)).join(",")}]`;
  if (value && typeof value === "object") {
    return `{${Object.keys(value)
      .sort()
      .map((key) => `${JSON.stringify(key)}:${canonicalJson(value[key])}`)
      .join(",")}}`;
  }
  return JSON.stringify(value);
}

function requestIdFor(action) {
  return `staging_${action}_${randomUUID()}`;
}

function parseHeaders(output) {
  const blocks = output.replace(/\r/g, "").split(/\n\n+/).filter(Boolean);
  const last = blocks[blocks.length - 1] ?? "";
  return last
    .split("\n")
    .map((line) => line.trim())
    .filter(Boolean);
}

function statusCode(headers) {
  const statusLine = headers.find((line) => /^HTTP\//i.test(line));
  const match = statusLine?.match(/^HTTP\/\S+\s+(\d{3})/i);
  return match ? Number(match[1]) : 0;
}

function headerValue(headers, name) {
  const prefix = `${name.toLowerCase()}:`;
  const line = headers.find((item) => item.toLowerCase().startsWith(prefix));
  return line ? line.slice(line.indexOf(":") + 1).trim() : "";
}

function parseChannels(value) {
  const parsed = String(value)
    .split(",")
    .map((item) => item.trim())
    .filter(Boolean);
  if (parsed.length === 0) fail("At least one channel is required.");
  for (const channel of parsed) {
    if (channel !== "stable" && channel !== "beta") {
      fail(`Invalid channel: ${channel}`);
    }
  }
  return [...new Set(parsed)];
}

function parseArgs(args) {
  const parsed = {};
  const booleans = new Set([
    "yes",
    "dry-run",
    "skip-backfill",
    "skip-publish",
    "skip-verify",
    "skip-readback",
    "keep-assets",
    "keep-work-dir",
    "allow-partial-r2",
    "rollback"
  ]);
  for (let index = 0; index < args.length; index += 1) {
    const arg = args[index];
    if (!arg.startsWith("--")) fail(`Unexpected argument: ${arg}`);
    const key = arg.slice(2);
    if (booleans.has(key)) {
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

function requiredOption(parsed, key, envName) {
  const value = parsed[key] ?? process.env[envName];
  if (!value) fail(`Missing --${key} or ${envName}`);
  return value;
}

function parseBoolean(value) {
  if (value === true || value === "true") return true;
  if (value === false || value === "false" || value === undefined || value === "") return false;
  fail(`Invalid boolean value: ${value}`);
}

function parseNonNegativeInteger(value, fieldName) {
  const parsed = Number.parseInt(value, 10);
  if (!Number.isInteger(parsed) || parsed < 0 || String(parsed) !== String(value)) {
    fail(`${fieldName} must be a non-negative integer`);
  }
  return parsed;
}

function fail(message) {
  process.stderr.write(`${message}\n`);
  process.exit(1);
}
