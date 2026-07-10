#!/usr/bin/env node

import { spawnSync } from "node:child_process";
import { existsSync } from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";

const scriptPath = fileURLToPath(import.meta.url);
const scriptsDir = path.dirname(scriptPath);
const serviceDir = path.dirname(scriptsDir);
const adminDir = path.join(serviceDir, "admin");

const DEFAULTS = {
  projectName: "trace-update-admin-staging",
  branch: "main",
  compatibilityDate: "2026-06-28",
  compatibilityFlag: "nodejs_compat"
};

const REQUIRED_ACCESS_SECRETS = [
  "ACCESS_JWT_ISSUER",
  "ACCESS_JWT_AUD",
  "ADMIN_OWNER_EMAILS"
];

const OPTIONAL_ACCESS_SECRETS = [
  "ADMIN_VIEWER_EMAILS",
  "ADMIN_PUBLISHER_EMAILS",
  "ADMIN_ALLOWED_ORIGINS"
];

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

  const projectName = args.projectName ?? process.env.TRACE_CF_ADMIN_PROJECT_NAME ?? DEFAULTS.projectName;
  const branch = args.branch ?? process.env.TRACE_CF_ADMIN_BRANCH ?? DEFAULTS.branch;
  const accessSecrets = collectAccessSecrets();

  printPlan({ projectName, branch, args, accessSecrets });

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
      cwd: adminDir,
      label: "tsc --noEmit"
    });
  }

  await ensurePagesProject(projectName);

  if (!args.skipSecrets) {
    requireAccessSecrets(accessSecrets);
    for (const [name, value] of Object.entries(accessSecrets)) {
      putPagesSecret(projectName, name, value);
    }
  }

  let deploymentUrl = "";
  if (!args.skipDeploy) {
    const deployOutput = runWrangler([
      "pages",
      "deploy",
      "./public",
      "--project-name",
      projectName,
      "--branch",
      branch,
      "--commit-dirty=true"
    ]);
    deploymentUrl = extractPagesUrl(deployOutput);
  }

  printSummary({ projectName, branch, deploymentUrl, skipped: args });
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

function collectAccessSecrets() {
  const secrets = {};
  for (const name of [...REQUIRED_ACCESS_SECRETS, ...OPTIONAL_ACCESS_SECRETS]) {
    const value = process.env[name] ?? "";
    if (value) {
      secrets[name] = value;
    }
  }
  return secrets;
}

function requireAccessSecrets(secrets) {
  const missing = REQUIRED_ACCESS_SECRETS.filter((name) => !secrets[name]);
  if (missing.length > 0) {
    throw new Error(
      `Missing required Access environment variables: ${missing.join(", ")}. ` +
        "Set them in the current shell or re-run with --skip-secrets."
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
    cwd: adminDir,
    input: options.input,
    quiet: options.quiet
  });
}

function runCommand(command, args, options = {}) {
  if (!options.quiet) {
    writeStep(options.label ?? `${displayCommand(command)} ${args.join(" ")}`);
  }
  const result = spawnSync(command, args, {
    cwd: options.cwd ?? adminDir,
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
  if (command === "npm" || command === "npm.cmd") return "npm";
  return command === process.execPath ? "wrangler" : command;
}

function typescriptPath() {
  return path.join(adminDir, "node_modules", "typescript", "bin", "tsc");
}

function ensureWranglerInstalled() {
  const wrangler = wranglerPath();
  if (!existsSync(wrangler)) {
    throw new Error(
      `Wrangler is not installed at ${wrangler}. Run "npm ci" from cloudflare/update-service/admin first.`
    );
  }
}

function wranglerPath() {
  return path.join(adminDir, "node_modules", "wrangler", "bin", "wrangler.js");
}

function extractPagesUrl(output) {
  const combined = `${output.stdout}\n${output.stderr}`;
  const match = combined.match(/https:\/\/[a-zA-Z0-9.-]+\.pages\.dev[^\s]*/);
  return match?.[0] ?? "";
}

function printPlan({ projectName, branch, args, accessSecrets }) {
  writeOut("Cloudflare update admin staging deploy plan\n");
  writeOut(`- Pages project: ${projectName}\n`);
  writeOut(`- Branch: ${branch}\n`);
  writeOut("- Create project if missing: yes\n");
  writeOut(`- Run admin typecheck: ${args.skipCheck ? "no" : "yes"}\n`);
  writeOut(`- Write Access Pages secrets: ${args.skipSecrets ? "no" : "yes"}\n`);
  writeOut(`- Deploy Pages admin: ${args.skipDeploy ? "no" : "yes"}\n`);
  for (const name of REQUIRED_ACCESS_SECRETS) {
    writeOut(`- ${name} set: ${accessSecrets[name] ? "yes" : "no"}\n`);
  }
  for (const name of OPTIONAL_ACCESS_SECRETS) {
    writeOut(`- ${name} set: ${accessSecrets[name] ? "yes" : "no"}\n`);
  }
  writeOut(`- CLOUDFLARE_API_TOKEN set: ${process.env.CLOUDFLARE_API_TOKEN ? "yes" : "no"}\n`);
}

function printSummary({ projectName, branch, deploymentUrl, skipped }) {
  writeOut("\nCloudflare admin staging deploy complete.\n");
  writeOut(`- Pages project: ${projectName}\n`);
  writeOut(`- Branch: ${branch}\n`);
  writeOut(`- Deployment URL: ${deploymentUrl || "not deployed or not detected"}\n`);
  if (skipped.skipCheck || skipped.skipSecrets || skipped.skipDeploy) {
    writeOut(
      `- Skipped: ${Object.entries(skipped)
        .filter(([key, value]) => key.startsWith("skip") && value)
        .map(([key]) => key)
        .join(", ")}\n`
    );
  }
  writeOut("\nProtect the Pages project domain with the matching Cloudflare Access application before using admin mutations.\n");
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
  node cloudflare/update-service/scripts/deploy-admin-staging.mjs [options]

Options:
  --yes, -y              Create/update the staging Pages admin project.
  --dry-run             Print the plan and exit without remote changes.
  --skip-check          Do not run npm run check in admin.
  --skip-secrets        Do not write Pages Access secrets.
  --skip-deploy         Create project/secrets but do not deploy Pages.
  --project-name <name> Override the staging Pages project name.
  --branch <branch>     Override the deployed branch name.
  --help, -h            Show this help.

Required environment variables unless using --skip-secrets:
  ACCESS_JWT_ISSUER
  ACCESS_JWT_AUD
  ADMIN_OWNER_EMAILS

Optional environment variables:
  ADMIN_VIEWER_EMAILS
  ADMIN_PUBLISHER_EMAILS
  ADMIN_ALLOWED_ORIGINS
  TRACE_CF_ADMIN_PROJECT_NAME
  TRACE_CF_ADMIN_BRANCH
`;
}
