#!/usr/bin/env node

import { spawnSync } from "node:child_process";
import { existsSync } from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";

const scriptPath = fileURLToPath(import.meta.url);
const scriptsDir = path.dirname(scriptPath);
const serviceDir = path.dirname(scriptsDir);
const publicDir = path.join(serviceDir, "public");

const DEFAULTS = {
  projectName: "trace-update-public-staging",
  branch: "main",
  compatibilityDate: "2026-06-28",
  compatibilityFlag: "nodejs_compat",
  publicUrl: "https://trace-update-public-staging.pages.dev"
};

const REQUIRED_SECRET_NAMES = ["DOWNLOAD_HMAC_KEY_CURRENT"];
const OPTIONAL_SECRET_NAMES = ["DOWNLOAD_HMAC_KEY_PREVIOUS"];

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

  const projectName = args.projectName ?? process.env.TRACE_CF_PUBLIC_PROJECT_NAME ?? DEFAULTS.projectName;
  const branch = args.branch ?? process.env.TRACE_CF_PUBLIC_BRANCH ?? DEFAULTS.branch;
  const publicUrl = args.publicUrl ?? process.env.TRACE_PUBLIC_UPDATE_SERVICE_URL ?? DEFAULTS.publicUrl;
  const secrets = collectPagesSecrets();

  printPlan({ projectName, branch, publicUrl, args, secrets });

  if (args.dryRun || !args.yes) {
    writeOut(
      args.dryRun
        ? "\nDry run only. No Cloudflare Pages project, secrets, or deployment were changed.\n"
        : "\nNo changes were made. Re-run with --yes after reviewing the plan.\n"
    );
    return;
  }

  ensureWranglerInstalled();

  if (!args.skipCheck) {
    runCommand(process.execPath, [typescriptPath(), "--noEmit"], {
      cwd: publicDir,
      label: "tsc --noEmit"
    });
  }

  await ensurePagesProject(projectName);

  if (!args.skipSecrets) {
    requirePagesSecrets(secrets);
    for (const [name, value] of Object.entries(secrets)) {
      putPagesSecret(projectName, name, value);
    }
  }

  let deploymentUrl = "";
  if (!args.skipDeploy) {
    const deployOutput = runWrangler([
      "pages",
      "deploy",
      "./site",
      "--project-name",
      projectName,
      "--branch",
      branch,
      "--commit-dirty=true"
    ]);
    deploymentUrl = extractPagesUrl(deployOutput);
  }

  printSummary({ projectName, branch, publicUrl, deploymentUrl, skipped: args });
}

function parseArgs(argv) {
  const args = {
    yes: false,
    dryRun: false,
    skipCheck: false,
    skipSecrets: false,
    skipDeploy: false,
    projectName: undefined,
    branch: undefined,
    publicUrl: undefined,
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
      case "--skip-check":
        args.skipCheck = true;
        break;
      case "--skip-secrets":
        args.skipSecrets = true;
        break;
      case "--skip-deploy":
        args.skipDeploy = true;
        break;
      case "--project-name":
        args.projectName = requiredValue(argv, index, arg);
        index += 1;
        break;
      case "--branch":
        args.branch = requiredValue(argv, index, arg);
        index += 1;
        break;
      case "--public-url":
        args.publicUrl = requiredValue(argv, index, arg);
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

function collectPagesSecrets() {
  const secrets = {};
  const current =
    process.env.TRACE_PUBLIC_DOWNLOAD_HMAC_KEY_CURRENT ??
    process.env.TRACE_DOWNLOAD_HMAC_KEY_CURRENT ??
    process.env.DOWNLOAD_HMAC_KEY_CURRENT ??
    "";
  const previous =
    process.env.TRACE_PUBLIC_DOWNLOAD_HMAC_KEY_PREVIOUS ??
    process.env.TRACE_DOWNLOAD_HMAC_KEY_PREVIOUS ??
    process.env.DOWNLOAD_HMAC_KEY_PREVIOUS ??
    "";

  if (current) secrets.DOWNLOAD_HMAC_KEY_CURRENT = current;
  if (previous) secrets.DOWNLOAD_HMAC_KEY_PREVIOUS = previous;
  return secrets;
}

function requirePagesSecrets(secrets) {
  const missing = REQUIRED_SECRET_NAMES.filter((name) => !secrets[name]);
  if (missing.length > 0) {
    throw new Error(
      `Missing required Pages secret environment variables: ${missing.join(", ")}. ` +
        "Set TRACE_PUBLIC_DOWNLOAD_HMAC_KEY_CURRENT, or re-run with --skip-secrets if it already exists in Pages."
    );
  }
}

async function ensurePagesProject(projectName) {
  const projects = await listPagesProjects();
  const existing = projects.find((project) => project["Project Name"] === projectName);
  if (existing) {
    writeStep(`Using existing Pages project ${projectName}`);
    return;
  }

  writeStep(`Creating Pages project ${projectName}`);
  runWrangler([
    "pages",
    "project",
    "create",
    projectName,
    "--production-branch",
    DEFAULTS.branch,
    "--compatibility-date",
    DEFAULTS.compatibilityDate,
    "--compatibility-flag",
    DEFAULTS.compatibilityFlag
  ]);
}

async function listPagesProjects() {
  const output = runWrangler(["pages", "project", "list", "--json"], { quiet: true });
  return JSON.parse(output.stdout || "[]");
}

function putPagesSecret(projectName, name, value) {
  writeStep(`Setting Pages secret ${name}`);
  runWrangler(["pages", "secret", "put", name, "--project-name", projectName], {
    input: `${value}\n`
  });
}

function runWrangler(args, options = {}) {
  return runCommand(process.execPath, [wranglerPath(), ...args], {
    cwd: publicDir,
    input: options.input,
    quiet: options.quiet
  });
}

function runCommand(command, args, options = {}) {
  if (!options.quiet) {
    writeStep(options.label ?? `${displayCommand(command)} ${args.join(" ")}`);
  }
  const result = spawnSync(command, args, {
    cwd: options.cwd ?? publicDir,
    env: { ...process.env, CI: process.env.CI ?? "1" },
    input: options.input,
    encoding: "utf8",
    windowsHide: true
  });

  if (!options.quiet && result.stdout) writeOut(result.stdout);
  if (!options.quiet && result.stderr) writeErr(result.stderr);
  if (result.error) {
    throw new Error(`${options.label ?? `${displayCommand(command)} ${args.join(" ")}`} failed to spawn: ${result.error.message}`);
  }
  if (result.status !== 0) {
    if (options.quiet) {
      if (result.stdout) writeOut(result.stdout);
      if (result.stderr) writeErr(result.stderr);
    }
    const authHint = process.env.CLOUDFLARE_API_TOKEN
      ? " CLOUDFLARE_API_TOKEN is set, so Wrangler is using that token; make sure it has Cloudflare Pages permissions or unset it to use wrangler login."
      : "";
    throw new Error(`${options.label ?? `${displayCommand(command)} ${args.join(" ")}`} failed with exit code ${result.status}.${authHint}`);
  }
  return { stdout: result.stdout ?? "", stderr: result.stderr ?? "" };
}

function displayCommand(command) {
  return command === process.execPath ? "wrangler" : command;
}

function typescriptPath() {
  return path.join(publicDir, "node_modules", "typescript", "bin", "tsc");
}

function ensureWranglerInstalled() {
  const wrangler = wranglerPath();
  if (!existsSync(wrangler)) {
    throw new Error(
      `Wrangler is not installed at ${wrangler}. Run "npm ci" from cloudflare/update-service/public first.`
    );
  }
}

function wranglerPath() {
  return path.join(publicDir, "node_modules", "wrangler", "bin", "wrangler.js");
}

function extractPagesUrl(output) {
  const combined = `${output.stdout}\n${output.stderr}`;
  const match = combined.match(/https:\/\/[a-zA-Z0-9.-]+\.pages\.dev[^\s]*/);
  return match?.[0] ?? "";
}

function printPlan({ projectName, branch, publicUrl, args, secrets }) {
  writeOut("Cloudflare update public staging deploy plan\n");
  writeOut(`- Pages project: ${projectName}\n`);
  writeOut(`- Branch: ${branch}\n`);
  writeOut(`- Public update base URL: ${publicUrl}\n`);
  writeOut("- Create project if missing: yes\n");
  writeOut(`- Run public typecheck: ${args.skipCheck ? "no" : "yes"}\n`);
  writeOut(`- Write Pages download secrets: ${args.skipSecrets ? "no" : "yes"}\n`);
  writeOut(`- Deploy Pages public endpoint: ${args.skipDeploy ? "no" : "yes"}\n`);
  for (const name of REQUIRED_SECRET_NAMES) {
    writeOut(`- ${name} environment value set: ${secrets[name] ? "yes" : "no"}\n`);
  }
  for (const name of OPTIONAL_SECRET_NAMES) {
    writeOut(`- ${name} environment value set: ${secrets[name] ? "yes" : "no"}\n`);
  }
  writeOut(`- CLOUDFLARE_API_TOKEN set: ${process.env.CLOUDFLARE_API_TOKEN ? "yes" : "no"}\n`);
}

function printSummary({ projectName, branch, publicUrl, deploymentUrl, skipped }) {
  writeOut("\nCloudflare public staging deploy complete.\n");
  writeOut(`- Pages project: ${projectName}\n`);
  writeOut(`- Branch: ${branch}\n`);
  writeOut(`- Public update base URL: ${publicUrl}\n`);
  writeOut(`- Deployment URL: ${deploymentUrl || "not deployed or not detected"}\n`);
  if (skipped.skipCheck || skipped.skipSecrets || skipped.skipDeploy) {
    writeOut(
      `- Skipped: ${Object.entries(skipped)
        .filter(([key, value]) => key.startsWith("skip") && value)
        .map(([key]) => key)
        .join(", ")}\n`
    );
  }
  writeOut("\nSet GitHub Actions variable TRACE_PUBLIC_UPDATE_SERVICE_URL to this public base URL for future APK builds.\n");
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

function usage() {
  return `Usage:
  node cloudflare/update-service/scripts/deploy-public-staging.mjs [options]

Options:
  --yes, -y              Create/update the staging public Pages project.
  --dry-run             Print the plan and exit without remote changes.
  --skip-check          Do not run npm run check in public.
  --skip-secrets        Do not write Pages download secrets.
  --skip-deploy         Create project/secrets but do not deploy Pages.
  --project-name <name> Override the staging Pages project name.
  --branch <branch>     Override the deployed branch name.
  --public-url <url>    Override the public update base URL printed in the summary.
  --help, -h            Show this help.

Required environment variables unless using --skip-secrets:
  TRACE_PUBLIC_DOWNLOAD_HMAC_KEY_CURRENT
  or TRACE_DOWNLOAD_HMAC_KEY_CURRENT
  or DOWNLOAD_HMAC_KEY_CURRENT

Optional environment variables:
  TRACE_PUBLIC_DOWNLOAD_HMAC_KEY_PREVIOUS
  TRACE_CF_PUBLIC_PROJECT_NAME
  TRACE_CF_PUBLIC_BRANCH
  TRACE_PUBLIC_UPDATE_SERVICE_URL
`;
}
