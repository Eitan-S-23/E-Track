#!/usr/bin/env node

import { mkdtemp, mkdir, readFile, rm, writeFile } from "node:fs/promises";
import { tmpdir } from "node:os";
import path from "node:path";
import { spawn } from "node:child_process";
import { fileURLToPath } from "node:url";

const options = parseArgs(process.argv.slice(2));
const releaseTag = requiredOption(options, "release-tag", "TRACE_RELEASE_TAG");
const repo =
  options.repo ?? options.repository ?? process.env.GITHUB_REPOSITORY ?? (await gitHubRepositoryFromRemote());
const scriptDir = path.dirname(fileURLToPath(import.meta.url));
const bootstrapSummary = await loadBootstrapSummary(
  options["bootstrap-summary"] ?? path.join(scriptDir, "..", ".bootstrap", "staging-summary.json")
);
const bucket =
  options.bucket ?? process.env.TRACE_R2_BUCKET ?? bootstrapSummary?.r2BucketName ?? "trace-update-staging-releases";
const wranglerCwd = options["wrangler-cwd"] ?? "cloudflare/update-service/worker";
const wranglerEnv = options.env ?? "";
const dryRun = parseBoolean(options["dry-run"]);
const yes = parseBoolean(options.yes);
const skipDownload = parseBoolean(options["skip-download"]);
const skipUpload = parseBoolean(options["skip-upload"]);
const skipReadback = parseBoolean(options["skip-readback"]);
const skipRegister = parseBoolean(options["skip-register"]);
const keepAssets = parseBoolean(options["keep-assets"] ?? options["keep-work-dir"]);
const providedAssetsDir = options["assets-dir"];
const serviceUrl =
  options["service-url"] ??
  process.env.TRACE_UPDATE_SERVICE_URL ??
  bootstrapSummary?.githubSecrets?.TRACE_UPDATE_SERVICE_URL ??
  bootstrapSummary?.workerUrl;
const deployToken = process.env.TRACE_DEPLOY_TOKEN ?? bootstrapSummary?.githubSecrets?.TRACE_DEPLOY_TOKEN;

if (!repo) fail("Missing --repo, GITHUB_REPOSITORY, or parseable origin remote");

const tempDir = providedAssetsDir
  ? null
  : await mkdtemp(path.join(tmpdir(), "trace-r2-backfill-"));
const assetsDir = path.resolve(providedAssetsDir ?? path.join(tempDir, "assets"));
const metadataPath = path.resolve(
  options.output ?? options.metadata ?? path.join(assetsDir, "cloudflare-r2-backfill-metadata.json")
);

try {
  const releaseInfo = dryRun
    ? { tagName: releaseTag, targetCommitish: options["commit-sha"] ?? "<release target>" }
    : await getReleaseInfo(repo, releaseTag);
  const commitSha = dryRun
    ? options["commit-sha"] ?? releaseInfo.targetCommitish
    : await resolveCommitSha(repo, options["commit-sha"] ?? releaseInfo.targetCommitish);
  const runId =
    options["run-id"] ?? `r2-backfill-${releaseTag.replace(/[^a-zA-Z0-9_.-]/g, "_")}-${Date.now()}`;

  printPlan({
    releaseTag,
    repo,
    bucket,
    assetsDir,
    metadataPath,
    wranglerCwd,
    wranglerEnv,
    commitSha,
    skipDownload,
    skipUpload,
    skipRegister,
    dryRun,
    serviceUrlSet: Boolean(serviceUrl),
    deployTokenSet: Boolean(deployToken)
  });

  if (dryRun) {
    process.stdout.write("\nDry run only. No GitHub, R2, or D1 writes were performed.\n");
    process.exit(0);
  }
  if (!yes) {
    fail("Pass --yes to download GitHub assets, upload R2 objects, and register the D1 R2 backfill.");
  }
  if (!skipUpload) {
    warnIfMissingCloudflareAuth();
  }
  if (!skipRegister) {
    if (!serviceUrl) {
      fail("Missing TRACE_UPDATE_SERVICE_URL or --service-url");
    }
    if (!deployToken) {
      fail("Missing TRACE_DEPLOY_TOKEN. Set it in the shell or keep the staging bootstrap summary file.");
    }
  }

  await mkdir(assetsDir, { recursive: true });

  if (!skipDownload) {
    await downloadAndroidAssets(repo, releaseTag, assetsDir, releaseInfo.assets);
  }

  await run("node", [
    scriptPath("build-github-release-metadata.mjs"),
    "--assets-dir",
    assetsDir,
    "--release-tag",
    releaseTag,
    "--run-id",
    runId,
    "--commit-sha",
    commitSha,
    "--repository",
    repo,
    "--fixed-signing-configured",
    "true",
    "--output",
    metadataPath,
    "--allow-placeholder-signature"
  ]);

  if (!skipUpload) {
    const uploadArgs = [
      scriptPath("upload-r2-assets.mjs"),
      "--assets-dir",
      assetsDir,
      "--metadata",
      metadataPath,
      "--bucket",
      bucket,
      "--wrangler-cwd",
      wranglerCwd,
      "--output",
      metadataPath
    ];
    if (wranglerEnv) {
      uploadArgs.push("--env", wranglerEnv);
    }
    if (skipReadback) {
      uploadArgs.push("--skip-readback");
    }
    await run("node", uploadArgs);
  }

  const metadata = JSON.parse(await readFile(metadataPath, "utf8"));
  if (skipUpload && !skipRegister) {
    fail("Cannot register R2 backfill when --skip-upload is used.");
  }
  if (!skipUpload) {
    assertR2Metadata(metadata);
  }
  metadata.r2Backfill = true;
  await writeFile(metadataPath, `${JSON.stringify(metadata, null, 2)}\n`, "utf8");

  if (!skipRegister) {
    await run("node", [scriptPath("register-release.mjs"), metadataPath], {
      env: {
        ...process.env,
        TRACE_UPDATE_SERVICE_URL: serviceUrl,
        TRACE_DEPLOY_TOKEN: deployToken
      }
    });
  }

  process.stdout.write(
    skipUpload || skipRegister ? "\nR2 backfill preparation complete.\n" : "\nR2 backfill complete.\n"
  );
  if (tempDir && !keepAssets) {
    process.stdout.write("- Metadata was generated in a temporary directory and removed after validation.\n");
  } else {
    process.stdout.write(`- Metadata: ${metadataPath}\n`);
  }
  process.stdout.write(`- Release: ${releaseTag}\n`);
  process.stdout.write(`- Bucket: ${bucket}\n`);
} finally {
  if (tempDir && !keepAssets) {
    await rm(tempDir, { recursive: true, force: true });
  }
}

async function getReleaseInfo(repoName, tagName) {
  const output = await runCapture("gh", [
    "release",
    "view",
    tagName,
    "-R",
    repoName,
    "--json",
    "tagName,targetCommitish,isDraft,isPrerelease,assets"
  ]);
  const info = JSON.parse(output);
  if (info.isDraft) {
    fail(`Release ${tagName} is a draft and cannot be backfilled.`);
  }
  if (!info.targetCommitish || typeof info.targetCommitish !== "string") {
    fail(`Release ${tagName} does not expose targetCommitish.`);
  }
  return info;
}

async function downloadAndroidAssets(repoName, tagName, targetDir, assets) {
  const assetNames = Array.isArray(assets)
    ? assets.map((asset) => asset.name).filter((name) => typeof name === "string")
    : [];
  const required = ["ble-monitor-android.apk", "ble-monitor-update.json"];
  for (const name of required) {
    if (!assetNames.includes(name)) {
      fail(`Release ${tagName} is missing required Android asset ${name}.`);
    }
  }
  const names = [
    ...required,
    ...assetNames.filter((name) => name.endsWith(".tpatch") || name.endsWith(".vcdiff"))
  ];
  process.stdout.write(`Downloading ${names.length} Android update asset(s) from ${tagName}.\n`);
  for (const name of names) {
    await runWithRetry(
      "gh",
      [
        "release",
        "download",
        tagName,
        "-R",
        repoName,
        "--dir",
        targetDir,
        "--clobber",
        "--pattern",
        name
      ],
      `download ${name}`
    );
  }
}

async function resolveCommitSha(repoName, targetCommitish) {
  if (isCommitSha(targetCommitish)) return targetCommitish;
  const output = await runCapture("gh", ["api", `repos/${repoName}/commits/${targetCommitish}`]);
  const commit = JSON.parse(output);
  if (isCommitSha(commit.sha)) return commit.sha;
  fail(`Could not resolve commit SHA for ${targetCommitish}. Pass --commit-sha explicitly.`);
}

async function gitHubRepositoryFromRemote() {
  try {
    const remote = (await runCapture("git", ["config", "--get", "remote.origin.url"])).trim();
    const https = remote.match(/github\.com[:/](?<owner>[^/]+)\/(?<repo>[^/.]+)(?:\.git)?$/i);
    if (https?.groups) {
      return `${https.groups.owner}/${https.groups.repo}`;
    }
  } catch {
    return "";
  }
  return "";
}

function assertR2Metadata(metadata) {
  if (!metadata || typeof metadata !== "object" || !Array.isArray(metadata.assets)) {
    fail("Generated metadata is missing assets.");
  }
  for (const asset of metadata.assets) {
    if (!asset.r2Key || asset.r2Verified !== true) {
      fail(`Asset ${asset.fileName ?? "<unknown>"} is missing verified R2 metadata.`);
    }
  }
}

function printPlan(plan) {
  process.stdout.write("Cloudflare R2 release backfill plan\n");
  process.stdout.write(`- Release tag: ${plan.releaseTag}\n`);
  process.stdout.write(`- GitHub repo: ${plan.repo}\n`);
  process.stdout.write(`- R2 bucket: ${plan.bucket}\n`);
  process.stdout.write(`- Assets dir: ${plan.assetsDir}\n`);
  process.stdout.write(`- Metadata path: ${plan.metadataPath}\n`);
  process.stdout.write(`- Wrangler cwd: ${plan.wranglerCwd}\n`);
  process.stdout.write(`- Wrangler env: ${plan.wranglerEnv || "(none)"}\n`);
  process.stdout.write(`- Commit SHA/target: ${plan.commitSha}\n`);
  process.stdout.write(`- Download GitHub assets: ${plan.skipDownload ? "no" : "yes"}\n`);
  process.stdout.write(`- Upload R2 assets: ${plan.skipUpload ? "no" : "yes"}\n`);
  process.stdout.write(`- Register D1 backfill: ${plan.skipRegister ? "no" : "yes"}\n`);
  process.stdout.write(`- Dry run: ${plan.dryRun ? "yes" : "no"}\n`);
  process.stdout.write(`- CLOUDFLARE_ACCOUNT_ID set: ${process.env.CLOUDFLARE_ACCOUNT_ID ? "yes" : "no"}\n`);
  process.stdout.write(`- CLOUDFLARE_API_TOKEN set: ${process.env.CLOUDFLARE_API_TOKEN ? "yes" : "no"}\n`);
  process.stdout.write(`- TRACE_UPDATE_SERVICE_URL set: ${plan.serviceUrlSet ? "yes" : "no"}\n`);
  process.stdout.write(`- TRACE_DEPLOY_TOKEN set: ${plan.deployTokenSet ? "yes" : "no"}\n`);
}

function scriptPath(fileName) {
  return path.join(scriptDir, fileName);
}

function run(command, args, optionsForRun = {}) {
  return new Promise((resolve, reject) => {
    const child = spawn(commandForPlatform(command), args, {
      ...optionsForRun,
      stdio: "inherit",
      shell: false
    });
    child.on("error", reject);
    child.on("exit", (code) => {
      if (code === 0) {
        resolve();
      } else {
        reject(new Error(`${command} ${args.join(" ")} failed with exit code ${code}`));
      }
    });
  });
}

async function runWithRetry(command, args, label, attempts = 3) {
  let lastError;
  for (let attempt = 1; attempt <= attempts; attempt += 1) {
    try {
      await run(command, args);
      return;
    } catch (error) {
      lastError = error;
      if (attempt === attempts) break;
      process.stderr.write(`${label} failed on attempt ${attempt}; retrying...\n`);
      await sleep(1500 * attempt);
    }
  }
  throw lastError;
}

function sleep(ms) {
  return new Promise((resolve) => {
    setTimeout(resolve, ms);
  });
}

function runCapture(command, args) {
  return new Promise((resolve, reject) => {
    const child = spawn(commandForPlatform(command), args, {
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
      if (code === 0) {
        resolve(stdout);
      } else {
        reject(new Error(`${command} ${args.join(" ")} failed with exit code ${code}\n${stderr}`));
      }
    });
  });
}

function commandForPlatform(command) {
  if (process.platform !== "win32") return command;
  if (command === "node") return "node.exe";
  if (command === "gh") return "gh.exe";
  if (command === "git") return "git.exe";
  return command;
}

async function loadBootstrapSummary(filePath) {
  try {
    const content = await readFile(filePath, "utf8");
    const summary = JSON.parse(content);
    if (!summary || typeof summary !== "object") {
      return null;
    }
    return summary;
  } catch {
    return null;
  }
}

function warnIfMissingCloudflareAuth() {
  if (process.env.CLOUDFLARE_ACCOUNT_ID && process.env.CLOUDFLARE_API_TOKEN) {
    return;
  }
  process.stdout.write(
    "WARN: CLOUDFLARE_ACCOUNT_ID/CLOUDFLARE_API_TOKEN are not both set. " +
      "Wrangler will use the current login if available.\n"
  );
}

function parseArgs(args) {
  const parsed = {};
  for (let index = 0; index < args.length; index += 1) {
    const arg = args[index];
    if (!arg.startsWith("--")) {
      fail(`Unexpected argument: ${arg}`);
    }
    const key = arg.slice(2);
    if (
      key === "yes" ||
      key === "dry-run" ||
      key === "skip-download" ||
      key === "skip-upload" ||
      key === "skip-readback" ||
      key === "skip-register" ||
      key === "keep-assets" ||
      key === "keep-work-dir"
    ) {
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

function isCommitSha(value) {
  return typeof value === "string" && /^[0-9a-f]{40}$/i.test(value);
}

function fail(message) {
  process.stderr.write(`${message}\n`);
  process.exit(1);
}
