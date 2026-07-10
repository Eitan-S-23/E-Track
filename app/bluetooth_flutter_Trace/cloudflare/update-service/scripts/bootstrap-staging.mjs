#!/usr/bin/env node

import { spawnSync } from "node:child_process";
import { createHash, randomBytes } from "node:crypto";
import { existsSync } from "node:fs";
import { mkdir, readFile, writeFile } from "node:fs/promises";
import path from "node:path";
import { fileURLToPath } from "node:url";

const scriptPath = fileURLToPath(import.meta.url);
const scriptsDir = path.dirname(scriptPath);
const serviceDir = path.dirname(scriptsDir);
const repoRoot = path.dirname(path.dirname(serviceDir));
const workerDir = path.join(serviceDir, "worker");
const wranglerConfigPath = path.join(workerDir, "wrangler.jsonc");

const DEFAULTS = {
  envName: "staging",
  appId: "trace",
  d1Name: "trace-update-staging",
  kvTitle: "trace-update-staging-manifest-cache",
  r2BucketName: "trace-update-staging-releases"
};

main().catch((error) => {
  writeErr(`\nERROR: ${error instanceof Error ? error.message : String(error)}\n`);
  process.exitCode = 1;
});

async function main() {
  const args = parseArgs(process.argv.slice(2));
  if (args.help) {
    writeOut(usage());
    return;
  }

  const envName = args.envName ?? process.env.TRACE_CF_BOOTSTRAP_ENV ?? DEFAULTS.envName;
  if (envName !== "staging") {
    throw new Error("This bootstrap is intentionally limited to --env staging.");
  }

  const names = {
    d1Name: process.env.TRACE_CF_STAGING_D1_NAME ?? DEFAULTS.d1Name,
    kvTitle: process.env.TRACE_CF_STAGING_KV_TITLE ?? DEFAULTS.kvTitle,
    r2BucketName: process.env.TRACE_CF_STAGING_R2_BUCKET ?? DEFAULTS.r2BucketName
  };
  const accountId = process.env.CLOUDFLARE_ACCOUNT_ID ?? "";
  const apiToken = process.env.CLOUDFLARE_API_TOKEN ?? "";
  const deployToken = process.env.TRACE_DEPLOY_TOKEN ?? `trace_staging_${randomSecret(32)}`;
  const downloadHmacKey = process.env.TRACE_DOWNLOAD_HMAC_KEY_CURRENT ?? randomSecret(48);
  const deployTokenSha256 = sha256Hex(deployToken);

  printPlan({ envName, names, hasAccountId: Boolean(accountId), hasApiToken: Boolean(apiToken), args });

  if (args.dryRun || !args.yes) {
    writeOut(
      args.dryRun
        ? "\nDry run only. No Cloudflare resources were created.\n"
        : "\nNo changes were made. Re-run with --yes after reviewing the plan.\n"
    );
    return;
  }

  if (!accountId || !apiToken) {
    throw new Error("Set CLOUDFLARE_ACCOUNT_ID and CLOUDFLARE_API_TOKEN before running with --yes.");
  }
  ensureWranglerInstalled();

  const d1 = await ensureD1Database(accountId, apiToken, names.d1Name);
  const kv = await ensureKvNamespace(accountId, apiToken, names.kvTitle);
  const r2 = await ensureR2Bucket(accountId, apiToken, names.r2BucketName);

  await updateWranglerConfig(envName, {
    d1DatabaseName: names.d1Name,
    d1DatabaseId: d1.id,
    kvNamespaceId: kv.id,
    r2BucketName: r2.name
  });

  if (!args.skipMigrations) {
    runWrangler(["d1", "migrations", "apply", names.d1Name, "--env", envName, "--remote"]);
  }

  let workerUrl = process.env.TRACE_CF_STAGING_WORKER_URL ?? "";
  if (!args.skipDeploy) {
    const deployOutput = runWrangler(["deploy", "--env", envName]);
    workerUrl = workerUrl || extractWorkerUrl(deployOutput);
  }

  if (!args.skipSecrets) {
    putWorkerSecret(envName, "DEPLOY_TOKEN_SHA256", deployTokenSha256);
    putWorkerSecret(envName, "DOWNLOAD_HMAC_KEY_CURRENT", downloadHmacKey);
  }

  if (!args.skipSmoke) {
    if (!workerUrl) {
      writeErr(
        "\nWARN: Worker URL could not be inferred from wrangler output. Set TRACE_CF_STAGING_WORKER_URL and re-run smoke checks manually.\n"
      );
    } else {
      await smokeTest(workerUrl);
    }
  }

  await writeSummaryIfRequested(args.outputPath, {
    envName,
    workerUrl,
    d1DatabaseName: names.d1Name,
    d1DatabaseId: d1.id,
    kvNamespaceTitle: names.kvTitle,
    kvNamespaceId: kv.id,
    r2BucketName: r2.name,
    githubSecrets: {
      TRACE_UPDATE_SERVICE_URL: workerUrl,
      TRACE_DEPLOY_TOKEN: deployToken
    },
    workerSecretsWritten: args.skipSecrets
      ? []
      : ["DEPLOY_TOKEN_SHA256", "DOWNLOAD_HMAC_KEY_CURRENT"]
  });

  printSummary({
    envName,
    workerUrl,
    d1,
    kv,
    r2,
    deployToken,
    skipped: {
      deploy: args.skipDeploy,
      migrations: args.skipMigrations,
      secrets: args.skipSecrets,
      smoke: args.skipSmoke
    }
  });
}

function parseArgs(argv) {
  const args = {
    yes: false,
    dryRun: false,
    skipDeploy: false,
    skipSecrets: false,
    skipMigrations: false,
    skipSmoke: false,
    envName: undefined,
    outputPath: undefined,
    help: false
  };

  for (let index = 0; index < argv.length; index += 1) {
    const arg = argv[index];
    switch (arg) {
      case "--yes":
      case "-y":
        args.yes = true;
        break;
      case "--dry-run":
        args.dryRun = true;
        break;
      case "--skip-deploy":
        args.skipDeploy = true;
        break;
      case "--skip-secrets":
        args.skipSecrets = true;
        break;
      case "--skip-migrations":
        args.skipMigrations = true;
        break;
      case "--skip-smoke":
        args.skipSmoke = true;
        break;
      case "--env":
        args.envName = requiredValue(argv, index, arg);
        index += 1;
        break;
      case "--output":
        args.outputPath = requiredValue(argv, index, arg);
        index += 1;
        break;
      case "--help":
      case "-h":
        args.help = true;
        break;
      default:
        throw new Error(`Unknown argument: ${arg}`);
    }
  }

  return args;
}

function requiredValue(argv, index, flag) {
  const value = argv[index + 1];
  if (!value || value.startsWith("--")) {
    throw new Error(`${flag} requires a value.`);
  }
  return value;
}

async function ensureD1Database(accountId, apiToken, name) {
  const existing = findByName(await listD1Databases(accountId, apiToken), name);
  if (existing) {
    writeStep(`Using existing D1 database ${name}`);
    return { id: d1Id(existing), name };
  }

  writeStep(`Creating D1 database ${name}`);
  try {
    const created = await cfApi(accountId, apiToken, "POST", "/d1/database", { name });
    return { id: d1Id(created), name };
  } catch (error) {
    if (!isConflict(error)) throw error;
    const afterConflict = findByName(await listD1Databases(accountId, apiToken), name);
    if (!afterConflict) throw error;
    return { id: d1Id(afterConflict), name };
  }
}

async function ensureKvNamespace(accountId, apiToken, title) {
  const existing = findByTitle(await listKvNamespaces(accountId, apiToken), title);
  if (existing) {
    writeStep(`Using existing KV namespace ${title}`);
    return { id: existing.id, title };
  }

  writeStep(`Creating KV namespace ${title}`);
  try {
    const created = await cfApi(accountId, apiToken, "POST", "/storage/kv/namespaces", { title });
    return { id: created.id, title };
  } catch (error) {
    if (!isConflict(error)) throw error;
    const afterConflict = findByTitle(await listKvNamespaces(accountId, apiToken), title);
    if (!afterConflict) throw error;
    return { id: afterConflict.id, title };
  }
}

async function ensureR2Bucket(accountId, apiToken, name) {
  const existing = findByName(await listR2Buckets(accountId, apiToken), name);
  if (existing) {
    writeStep(`Using existing R2 bucket ${name}`);
    return { name };
  }

  writeStep(`Creating R2 bucket ${name}`);
  try {
    await cfApi(accountId, apiToken, "POST", "/r2/buckets", { name });
    return { name };
  } catch (error) {
    if (!isConflict(error)) throw error;
    const afterConflict = findByName(await listR2Buckets(accountId, apiToken), name);
    if (!afterConflict) throw error;
    return { name };
  }
}

async function listD1Databases(accountId, apiToken) {
  return asArray(await cfApi(accountId, apiToken, "GET", "/d1/database"));
}

async function listKvNamespaces(accountId, apiToken) {
  return asArray(await cfApi(accountId, apiToken, "GET", "/storage/kv/namespaces"));
}

async function listR2Buckets(accountId, apiToken) {
  return asArray(await cfApi(accountId, apiToken, "GET", "/r2/buckets"));
}

async function cfApi(accountId, apiToken, method, accountPath, body) {
  const response = await fetch(
    `https://api.cloudflare.com/client/v4/accounts/${accountId}${accountPath}`,
    {
      method,
      headers: {
        Authorization: `Bearer ${apiToken}`,
        "Content-Type": "application/json"
      },
      body: body === undefined ? undefined : JSON.stringify(body)
    }
  );
  const payload = await response.json().catch(() => null);
  if (!response.ok || payload?.success === false) {
    const message = payload?.errors?.map((entry) => entry.message).join("; ") || response.statusText;
    const error = new Error(`Cloudflare API ${method} ${accountPath} failed: ${message}`);
    error.status = response.status;
    error.payload = payload;
    throw error;
  }
  return payload?.result;
}

async function updateWranglerConfig(envName, resources) {
  writeStep(`Updating ${path.relative(repoRoot, wranglerConfigPath)}`);
  const raw = await readFile(wranglerConfigPath, "utf8");
  const config = JSON.parse(raw);
  const envConfig = config.env?.[envName];
  if (!envConfig) {
    throw new Error(`wrangler.jsonc is missing env.${envName}.`);
  }

  const d1 = firstBinding(envConfig.d1_databases, "DB", "d1_databases");
  d1.database_name = resources.d1DatabaseName;
  d1.database_id = resources.d1DatabaseId;
  d1.migrations_dir = "../migrations";

  const kv = firstBinding(envConfig.kv_namespaces, "MANIFEST_CACHE", "kv_namespaces");
  kv.id = resources.kvNamespaceId;

  const r2 = firstBinding(envConfig.r2_buckets, "RELEASES_BUCKET", "r2_buckets");
  r2.bucket_name = resources.r2BucketName;

  normalizeLocalDurableObjectBindings(envConfig);

  await writeFile(wranglerConfigPath, `${JSON.stringify(config, null, 2)}\n`, "utf8");
}

function firstBinding(bindings, bindingName, fieldName) {
  if (!Array.isArray(bindings)) {
    throw new Error(`wrangler.jsonc field ${fieldName} must be an array.`);
  }
  const binding = bindings.find((candidate) => candidate.binding === bindingName);
  if (!binding) {
    throw new Error(`wrangler.jsonc ${fieldName} is missing binding ${bindingName}.`);
  }
  return binding;
}

function normalizeLocalDurableObjectBindings(envConfig) {
  const bindings = envConfig.durable_objects?.bindings;
  if (!Array.isArray(bindings)) return;
  for (const binding of bindings) {
    if (binding && typeof binding === "object" && !binding.script_name) {
      delete binding.environment;
    }
  }
}

function runWrangler(args, options = {}) {
  writeStep(`wrangler ${args.join(" ")}`);
  // Run Wrangler's JS entrypoint directly. This avoids Windows .cmd spawn limits.
  const result = spawnSync(process.execPath, [wranglerPath(), ...args], {
    cwd: workerDir,
    env: { ...process.env, CI: process.env.CI ?? "1" },
    input: options.input,
    encoding: "utf8",
    windowsHide: true
  });

  if (result.stdout) writeOut(result.stdout);
  if (result.stderr) writeErr(result.stderr);
  if (result.error) {
    throw new Error(
      `wrangler ${args.join(" ")} failed to spawn: ${result.error.code ?? result.error.message}`
    );
  }
  if (result.status !== 0) {
    throw new Error(`wrangler ${args.join(" ")} failed with exit code ${result.status}.`);
  }
  return `${result.stdout ?? ""}\n${result.stderr ?? ""}`;
}

function putWorkerSecret(envName, name, value) {
  writeStep(`Setting Worker secret ${name}`);
  runWrangler(["secret", "put", name, "--env", envName], { input: `${value}\n` });
}

async function smokeTest(workerUrl) {
  const baseUrl = workerUrl.replace(/\/+$/, "");
  const healthUrl = `${baseUrl}/healthz`;
  writeStep(`Smoke test ${healthUrl}`);
  const health = await fetchForSmoke(healthUrl);
  if (!health) {
    warnManualSmoke(baseUrl);
    return;
  }
  if (!health.ok) {
    throw new Error(`/healthz failed with HTTP ${health.status}: ${health.body}`);
  }

  writeStep("Smoke test public latest no-update response");
  const latestUrl = new URL("/api/public/latest", baseUrl);
  latestUrl.searchParams.set("appId", DEFAULTS.appId);
  latestUrl.searchParams.set("platform", "android");
  latestUrl.searchParams.set("channel", "stable");
  latestUrl.searchParams.set("versionCode", "1");
  latestUrl.searchParams.set("schemaVersion", "2");
  latestUrl.searchParams.set("capabilities", "patch,full,payloadSignature");
  const latest = await fetchForSmoke(latestUrl);
  if (!latest) {
    warnManualSmoke(baseUrl);
    return;
  }
  const body = latest.body;
  if (!latest.ok) {
    throw new Error(`/api/public/latest failed with HTTP ${latest.status}: ${body}`);
  }
  if (!body.includes("NO_UPDATE") && !body.includes("CHANNEL_STOPPED")) {
    throw new Error(`/api/public/latest returned an unexpected body: ${body}`);
  }
}

async function fetchForSmoke(url) {
  const target = String(url);
  let lastError;
  for (let attempt = 1; attempt <= 3; attempt += 1) {
    try {
      const response = await fetch(target);
      return {
        ok: response.ok,
        status: response.status,
        body: await response.text()
      };
    } catch (error) {
      lastError = error;
      await delay(1000 * attempt);
    }
  }

  const message = lastError instanceof Error ? lastError.message : String(lastError);
  const cause = lastError?.cause?.code ? ` (${lastError.cause.code})` : "";
  writeErr(`\nWARN: Node smoke test could not reach ${target}: ${message}${cause}\n`);
  return null;
}

function warnManualSmoke(baseUrl) {
  writeErr("WARN: Remote setup completed, but local Node smoke checks were inconclusive.\n");
  writeErr("WARN: Run these manual checks from PowerShell:\n");
  writeErr(`Invoke-RestMethod "${baseUrl}/healthz"\n`);
  writeErr(
    `Invoke-RestMethod "${baseUrl}/api/public/latest?appId=trace&platform=android&channel=stable&versionCode=1&schemaVersion=2&capabilities=patch,full,payloadSignature"\n`
  );
}

function delay(milliseconds) {
  return new Promise((resolve) => setTimeout(resolve, milliseconds));
}

async function writeSummaryIfRequested(outputPath, summary) {
  if (!outputPath) return;
  const resolvedPath = path.resolve(repoRoot, outputPath);
  await mkdir(path.dirname(resolvedPath), { recursive: true });
  await writeFile(resolvedPath, `${JSON.stringify(summary, null, 2)}\n`, "utf8");
  writeStep(`Wrote local summary ${path.relative(repoRoot, resolvedPath)}`);
}

function ensureWranglerInstalled() {
  const wrangler = wranglerPath();
  if (!existsSync(wrangler)) {
    throw new Error(
      `Wrangler is not installed at ${wrangler}. Run "npm ci" from cloudflare/update-service/worker first.`
    );
  }
}

// Avoid npm's generated .bin shim. On Windows, Node.js can reject .cmd spawning
// without a shell and return EINVAL with a null status.
function wranglerPath() {
  return path.join(workerDir, "node_modules", "wrangler", "bin", "wrangler.js");
}

function extractWorkerUrl(output) {
  const match = output.match(/https:\/\/[a-zA-Z0-9.-]+\.workers\.dev[^\s]*/);
  return match?.[0] ?? "";
}

function asArray(value) {
  if (Array.isArray(value)) return value;
  if (Array.isArray(value?.databases)) return value.databases;
  if (Array.isArray(value?.namespaces)) return value.namespaces;
  if (Array.isArray(value?.buckets)) return value.buckets;
  if (Array.isArray(value?.items)) return value.items;
  return [];
}

function findByName(items, name) {
  return items.find((item) => item.name === name || item.database_name === name);
}

function findByTitle(items, title) {
  return items.find((item) => item.title === title || item.name === title);
}

function d1Id(database) {
  const id = database.uuid ?? database.database_id ?? database.id;
  if (!id) {
    throw new Error("Cloudflare D1 response did not include a database id.");
  }
  return id;
}

function isConflict(error) {
  return error && typeof error === "object" && error.status === 409;
}

function sha256Hex(value) {
  return createHash("sha256").update(value).digest("hex");
}

function randomSecret(bytes) {
  return randomBytes(bytes).toString("base64url");
}

function writeStep(message) {
  writeOut(`\n==> ${message}\n`);
}

function writeOut(message) {
  process.stdout.write(message);
}

function writeErr(message) {
  process.stderr.write(message);
}

function printPlan({ envName, names, hasAccountId, hasApiToken, args }) {
  writeOut(`Cloudflare update-service bootstrap plan\n`);
  writeOut(`- Environment: ${envName}\n`);
  writeOut(`- D1 database: ${names.d1Name}\n`);
  writeOut(`- KV namespace: ${names.kvTitle}\n`);
  writeOut(`- R2 bucket: ${names.r2BucketName}\n`);
  writeOut(`- Update wrangler env: ${path.relative(repoRoot, wranglerConfigPath)}\n`);
  writeOut(`- Apply D1 migrations: ${args.skipMigrations ? "no" : "yes"}\n`);
  writeOut(`- Deploy Worker: ${args.skipDeploy ? "no" : "yes"}\n`);
  writeOut(`- Write Worker secrets: ${args.skipSecrets ? "no" : "yes"}\n`);
  writeOut(`- Smoke test: ${args.skipSmoke ? "no" : "yes"}\n`);
  writeOut(`- CLOUDFLARE_ACCOUNT_ID set: ${hasAccountId ? "yes" : "no"}\n`);
  writeOut(`- CLOUDFLARE_API_TOKEN set: ${hasApiToken ? "yes" : "no"}\n`);
}

function printSummary({ envName, workerUrl, d1, kv, r2, deployToken, skipped }) {
  writeOut("\nCloudflare staging bootstrap complete.\n");
  writeOut(`- Environment: ${envName}\n`);
  writeOut(`- Worker URL: ${workerUrl || "not detected"}\n`);
  writeOut(`- D1: ${d1.name} (${d1.id})\n`);
  writeOut(`- KV: ${kv.title} (${kv.id})\n`);
  writeOut(`- R2: ${r2.name}\n`);
  if (skipped.deploy || skipped.migrations || skipped.secrets || skipped.smoke) {
    writeOut(
      `- Skipped: ${Object.entries(skipped)
        .filter(([, value]) => value)
        .map(([key]) => key)
        .join(", ")}\n`
    );
  }
  writeOut("\nAdd these GitHub Secrets when CI registration is enabled:\n");
  writeOut(`TRACE_UPDATE_SERVICE_URL=${workerUrl || "<worker-url>"}\n`);
  writeOut(`TRACE_DEPLOY_TOKEN=${deployToken}\n`);
  writeOut("\nDo not commit the deploy token. Worker stores only DEPLOY_TOKEN_SHA256.\n");
}

function usage() {
  return `Usage:
  node cloudflare/update-service/scripts/bootstrap-staging.mjs [options]

Options:
  --yes, -y           Create/update Cloudflare staging resources.
  --dry-run          Print the plan and exit without remote changes.
  --env staging      Target environment. Only staging is allowed.
  --skip-deploy      Create resources and update config, but do not deploy.
  --skip-secrets     Do not write Worker secrets.
  --skip-migrations  Do not apply D1 migrations.
  --skip-smoke       Do not call deployed Worker smoke-test endpoints.
  --output <path>    Write a local JSON summary. Use an ignored path.
  --help, -h         Show this help.

Required environment variables when using --yes:
  CLOUDFLARE_ACCOUNT_ID
  CLOUDFLARE_API_TOKEN

Optional environment variables:
  TRACE_DEPLOY_TOKEN
  TRACE_DOWNLOAD_HMAC_KEY_CURRENT
  TRACE_CF_STAGING_WORKER_URL
  TRACE_CF_STAGING_D1_NAME
  TRACE_CF_STAGING_KV_TITLE
  TRACE_CF_STAGING_R2_BUCKET
`;
}
