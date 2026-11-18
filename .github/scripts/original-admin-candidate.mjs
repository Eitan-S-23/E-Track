import { execFileSync } from "node:child_process";
import { appendFile, readFile } from "node:fs/promises";
import path from "node:path";
import { pathToFileURL } from "node:url";
import { createHash } from "node:crypto";
import { CliError, failure, outputPath, projectRoot, writeOutput } from "../../app/bluetooth_flutter_Trace/cloudflare/update-service/scripts/firmware-cli.mjs";
import { versionCodeFor } from "../../app/bluetooth_flutter_Trace/cloudflare/update-service/scripts/firmware-schema.mjs";

export const CANDIDATE_BRANCH = "main";
export const ORIGINAL_APP_WORKFLOW_BRANCH = "release/candidates";
export const FIRMWARE_CANDIDATE_BRANCH = "main";
export const INTEGRATED_SOURCE = "a377846c1dbf966ca3f03a46872f905eb28b87a4";
export const APP_PUBSPEC = "app/bluetooth_flutter_Trace/pubspec.yaml";
export const RELEASE_CONFIG = "Tools/ota/original-admin-release.json";
const sha = value => /^[0-9a-f]{40}$/.test(value ?? "");
const git = (root, args) => execFileSync("git", args, { cwd: root, encoding: "utf8", windowsHide: true }).trim();

function automaticPushAdmission(env, branch) {
  if (env.GITHUB_ACTIONS !== "true" || env.GITHUB_REPOSITORY !== "Eitan-S-23/E-Track"
      || env.GITHUB_EVENT_NAME !== "push" || env.GITHUB_REF !== `refs/heads/${branch}`
      || !sha(env.GITHUB_SHA) || !/^[1-9][0-9]*$/.test(env.GITHUB_RUN_ID ?? "") || env.GITHUB_RUN_ATTEMPT !== "1") {
    throw new CliError(`Automatic candidates require a first-attempt push to E-Track ${branch}`);
  }
}

export function automaticCandidateAdmission(env) {
  automaticPushAdmission(env, CANDIDATE_BRANCH);
}

export function automaticFirmwareCandidateAdmission(env) {
  automaticPushAdmission(env, FIRMWARE_CANDIDATE_BRANCH);
}

export function appVersion(text) {
  const matches = [...text.matchAll(/^version:\s*(0|[1-9]\d*)\.(0|[1-9]\d*)\.(0|[1-9]\d*)\+([1-9]\d*)\s*$/gm)];
  if (matches.length !== 1) throw new CliError("App version must be one canonical name+versionCode");
  const [, major, minor, patch, code] = matches[0];
  if (!Number.isSafeInteger(Number(code)) || Number(code) > 2100000000) throw new CliError("Invalid Android versionCode");
  return { versionName: `${major}.${minor}.${patch}`, versionCode: Number(code) };
}

export function releaseConfig(value) {
  if (value?.schema !== "original-admin-automatic-candidates-v1"
      || typeof value.firmware?.releaseNotes !== "string" || !value.firmware.releaseNotes.trim()
      || value.firmware.releaseNotes.length > 8000) throw new CliError("Invalid original Admin release configuration");
  return { ...value.firmware, versionCode: versionCodeFor(value.firmware.versionName) };
}

export function appCandidateRequired(beforeText, afterText) {
  const before = appVersion(beforeText), after = appVersion(afterText);
  const previousParts = before.versionName.split(".").map(Number);
  const parts = after.versionName.split(".").map(Number);
  const difference = parts.findIndex((part, i) => part !== previousParts[i]);
  const nameAdvanced = difference >= 0 && parts[difference] > previousParts[difference];
  if (after.versionCode < before.versionCode || after.versionCode < 102
      || (difference >= 0 && !nameAdvanced)) throw new CliError("Candidate versions must never move backward");
  const required = after.versionCode !== before.versionCode || after.versionName !== before.versionName;
  if (required && (after.versionCode <= before.versionCode || !nameAdvanced)) {
    throw new CliError("App release: increment both pubspec version name and code; existing APKs are immutable");
  }
  return required;
}

export function candidatePlan({ changed, beforeApp, afterApp, beforeFirmware, afterFirmware, source, component = "both" }) {
  if (!sha(source)) throw new CliError("Exact candidate source required");
  if (!["app", "firmware", "both"].includes(component)) throw new CliError("Unknown candidate component");
  const app = appVersion(afterApp), appVersionChanged = appCandidateRequired(beforeApp, afterApp);
  const firmware = releaseConfig(afterFirmware), previousFirmware = releaseConfig(beforeFirmware);
  const firmwareChanged = changed.some(name => /^(?:USER|ArduinoAPI|Libraries|MDK-ARM_F435|boot|cmake|vendor|bsdiff_lzma_AES128-main|segger_rtt)\//.test(name));
  if (firmware.versionCode < previousFirmware.versionCode || firmware.versionCode < 30324) {
    throw new CliError("Candidate versions must never move backward");
  }
  const appRequired = component !== "firmware" && appVersionChanged;
  const firmwareRequired = component !== "app" && (firmwareChanged || firmware.versionCode !== previousFirmware.versionCode);
  if (firmwareRequired && firmware.versionCode <= previousFirmware.versionCode) {
    throw new CliError("Firmware changed: increment Tools/ota/original-admin-release.json firmware.versionName");
  }
  return { source, branch: component === "firmware" ? FIRMWARE_CANDIDATE_BRANCH : CANDIDATE_BRANCH, app: { ...app, required: appRequired },
    firmware: { ...firmware, required: firmwareRequired }, channelPublished: false, automaticDeltas: false };
}

export async function planFromCheckout(root, env = process.env) {
  automaticCandidateAdmission(env);
  if (git(root, ["rev-parse", "HEAD"]) !== env.GITHUB_SHA) throw new CliError("Checkout differs from push source");
  if (/^0{40}$/.test(env.BEFORE_SHA ?? "")) throw new CliError("Main candidates require an existing versioned baseline");
  const before = env.BEFORE_SHA;
  if (!sha(before)) throw new CliError("Push before-SHA is required; do not guess a comparison base");
  git(root, ["merge-base", "--is-ancestor", before, env.GITHUB_SHA]);
  const afterFirmware = JSON.parse(await readFile(path.join(root, RELEASE_CONFIG)));
  const beforeFirmware = JSON.parse(git(root, ["show", `${before}:${RELEASE_CONFIG}`]));
  return candidatePlan({ changed: git(root, ["diff", "--name-only", "--no-renames", before, env.GITHUB_SHA, "--"]).split(/\r?\n/),
    beforeApp: git(root, ["show", `${before}:${APP_PUBSPEC}`]), afterApp: await readFile(path.join(root, APP_PUBSPEC), "utf8"),
    beforeFirmware, afterFirmware, source: env.GITHUB_SHA });
}

export async function githubJson(route, token, { method = "GET", body, fetcher = fetch } = {}) {
  const response = await fetcher(`https://api.github.com/repos/${route}`, { method, redirect: "error",
    headers: { Accept: "application/vnd.github+json", Authorization: `Bearer ${token}`,
      "X-GitHub-Api-Version": "2022-11-28", "Content-Type": "application/json" },
    body: body === undefined ? undefined : JSON.stringify(body), signal: AbortSignal.timeout(30000) });
  if (!response.ok) throw new CliError(`GitHub ${method} failed (${response.status}); reconcile before retrying a dispatch`);
  return response.status === 204 ? null : response.json();
}

export async function dispatchApp(plan, env, request = githubJson) {
  automaticCandidateAdmission(env);
  if (plan.source !== env.GITHUB_SHA || plan.branch !== CANDIDATE_BRANCH || plan.app?.required !== true
      || plan.app.versionCode <= 102 || !env.ORIGINAL_ADMIN_ACTIONS_TOKEN) throw new CliError("New App candidate and existing dispatcher credential required");
  const name = `candidate:${plan.source}:${env.GITHUB_RUN_ID}`;
  const route = "Eitan-S-23/Trace/actions/workflows/build.yml";
  const runs = await request(`${route}/runs?branch=${ORIGINAL_APP_WORKFLOW_BRANCH}&event=workflow_dispatch&per_page=100`, env.ORIGINAL_ADMIN_ACTIONS_TOKEN);
  if (runs.workflow_runs.some(run => run.display_title === name)) throw new CliError("Candidate request already exists; do not dispatch twice");
  const ref = await request(`Eitan-S-23/Trace/git/ref/heads/${ORIGINAL_APP_WORKFLOW_BRANCH}`, env.ORIGINAL_ADMIN_ACTIONS_TOKEN);
  if (!sha(ref.object?.sha)) throw new CliError("Original App workflow identity is unavailable");
  await request(`${route}/dispatches`, env.ORIGINAL_ADMIN_ACTIONS_TOKEN, { method: "POST", body: {
    ref: ORIGINAL_APP_WORKFLOW_BRANCH, inputs: { source_sha: plan.source, source_run: env.GITHUB_RUN_ID, check_only: "false" } } });
  return { source: plan.source, workflowCommit: ref.object.sha, request: name, accepted: true, completed: false, channelPublished: false };
}

async function observeApp(receipt, env) {
  const end = Date.now() + 90 * 60 * 1000;
  while (Date.now() < end) {
    const value = await githubJson(`Eitan-S-23/Trace/actions/workflows/build.yml/runs?branch=${ORIGINAL_APP_WORKFLOW_BRANCH}&event=workflow_dispatch&per_page=100`, env.ORIGINAL_ADMIN_ACTIONS_TOKEN);
    const matches = value.workflow_runs.filter(run => run.display_title === receipt.request);
    if (matches.length > 1) throw new CliError("Ambiguous duplicate candidate runs");
    const run = matches[0];
    if (run && run.head_sha !== receipt.workflowCommit) throw new CliError("Dispatched App workflow changed; reconcile the remote run");
    if (run?.status === "completed") {
      if (run.conclusion !== "success") throw new CliError(`Original App candidate failed: ${run.html_url}`);
      return { ...receipt, completed: true, runId: run.id, url: run.html_url };
    }
    if (run) process.stdout.write(`Original App candidate: ${run.status} ${run.html_url}\n`);
    await new Promise(resolve => setTimeout(resolve, 30000));
  }
  throw new CliError("Original App candidate still unresolved; do not repeat the request");
}

async function freshFirmwareSource(root, out, env) {
  const { adminCandidateAdmission } = await import("./firmware-admin-context.mjs");
  const owner = adminCandidateAdmission(env);
  automaticFirmwareCandidateAdmission(env);
  const plan = await planFromCheckout(root, env);
  if (!plan.firmware.required || plan.firmware.versionName !== owner.versionName) throw new CliError("Firmware is not a new planned version");
  const { buildKeyedFirmware } = await import("./firmware-gcc-keyed-build.mjs");
  const source = path.join(out, "source");
  await buildKeyedFirmware({ root, buildDir: path.join(out, "private-build"), evidenceDir: source,
    versionName: owner.versionName, commitSha: env.GITHUB_SHA,
    buildTimestamp: Number(git(root, ["show", "-s", "--format=%ct", "HEAD"])), env, profile: "p34-v2-candidate" });
  const names = ["gcc-build-inputs.json", "keyed-build-evidence.json", "steps.json", "CMakeCache.txt", "compile_commands.json",
    "compiler-launchers.ninja", "app/X-Track-App-GCC.bin", "app/X-Track-App-GCC.elf", "app/X-Track-App-GCC.map", "boot/X-Track-Boot.bin"];
  const files = [];
  for (const name of names) {
    const file = outputPath(root, path.join(source, name)), raw = await readFile(file);
    files.push({ path: path.relative(root, file).split(path.sep).join("/"), bytes: raw.length, sha256: createHash("sha256").update(raw).digest("hex") });
  }
  await writeOutput(root, path.join(source, "source-proof.json"), JSON.stringify({ schema: "original-admin-normal-source-proof-v1",
    config: { schema: "original-admin-normal-source-v1", sourceCommit: env.GITHUB_SHA, profile: "p34-v2-candidate" },
    sourceCommit: env.GITHUB_SHA, verifiedAgainst: env.GITHUB_SHA, sourceMatches: true,
    importedBenchmarkPackages: 0, sourceCompilations: 1, keyedBuildStage: "PASS", files }, null, 2) + "\n");
}

async function main() {
  const [action, before, after] = process.argv.slice(2), root = projectRoot();
  const out = outputPath(root, ".cache/original-admin-candidate/run");
  if (action === "app-candidate-needed") {
    if (!sha(before) || !sha(after) || git(root, ["rev-parse", "HEAD"]) !== after) {
      throw new CliError("Exact before/current checkout commits required");
    }
    process.stdout.write(String(appCandidateRequired(git(root, ["show", `${before}:${APP_PUBSPEC}`]),
      git(root, ["show", `${after}:${APP_PUBSPEC}`]))) + "\n");
  } else if (action === "plan") {
    const plan = await planFromCheckout(root);
    await writeOutput(root, path.join(out, "plan.json"), JSON.stringify(plan, null, 2) + "\n");
    if (process.env.GITHUB_OUTPUT) await appendFile(process.env.GITHUB_OUTPUT,
      `app=${plan.app.required}\nfirmware=${plan.firmware.required}\nfirmware_version=${plan.firmware.versionName}\n`);
    process.stdout.write(JSON.stringify(plan) + "\n");
  } else if (action === "dispatch-app") {
    const plan = await planFromCheckout(root);
    const receipt = await dispatchApp(plan, process.env);
    await writeOutput(root, path.join(out, "app-dispatch.json"), JSON.stringify(receipt) + "\n");
    const complete = await observeApp(receipt, process.env);
    await writeOutput(root, path.join(out, "app-complete.json"), JSON.stringify(complete) + "\n");
    process.stdout.write(JSON.stringify(complete) + "\n");
  } else if (action === "firmware-source") await freshFirmwareSource(root, out, process.env);
  else throw new CliError("Expected plan, app-candidate-needed, dispatch-app or firmware-source");
}
if (process.argv[1] && import.meta.url === pathToFileURL(path.resolve(process.argv[1])).href) main().catch(failure);
